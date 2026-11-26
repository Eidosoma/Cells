"""Compare ATP-cycle rates with frozen references and yeast vacuole reversal measurements."""

import json
import math
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import brentq

from cells.kinds import transporter
from cells.laws.electrochemistry import F, R
from cells.laws.pumps import proton_pump
from tests.unit import test_cycle_kind_references as fixture
from validation.core_seams.references import design, exact


@jax.jit
def evaluate(state, potentials, control, layout):
    probe = transporter.probe(state, potentials, control, layout, xp=jnp)
    rates = transporter.rates(state, potentials, control, layout, xp=jnp)
    values = jnp.stack(
        (
            probe.modes.x[0, 0],
            rates.derivatives["cycle_count"][0, 0],
            rates.heat_pJ_s[0],
            rates.work_pJ_s[0],
        )
    )
    return values, probe.modes.x_terms[0, 0], rates.valid


def host_inputs(ready, record):
    """Express both reference compartments in the tissue world's own amount coordinates."""
    spec, initial, layout, _ = ready

    def increments(end, initial_amounts, reference):
        amounts = np.array(initial_amounts)
        for species in fixture.REGISTRY["species"]:
            row = spec.model.species_ids.index(species)
            c = record["c_mM"][end].get(species, 1e-3)
            amounts[row, 0] = fixture.A["volumes_pL"][end] * c - reference[row, 0]
        return amounts

    state = initial._replace(
        amount_increment=increments("a", initial.amount_increment, layout.amount_reference),
        extracellular_amount_increment=increments(
            "b", initial.extracellular_amount_increment, layout.extracellular_amount_reference
        ),
    )
    potentials = np.zeros(layout.active.size + layout.outside_active.size)
    potentials[0], potentials[layout.active.size] = record["phi_V"]["a"], record["phi_V"]["b"]
    return state, potentials


def check_panel(law):
    key = law["id"]
    ready = fixture.prepared(law)
    spec, _, layout, control = ready
    rt_pj = float(exact.RT_J_per_mol(spec.model.temperature_K)) / 1000
    inputs = fixture.A["states"][key]
    references = fixture.VALUES["seam_a"]["laws"][key]["states"]
    counts = {"forward": 0, "reverse": 0, "within_stall_band": 0}
    worst_error, worst_floors = np.zeros(4), np.zeros(4)

    for record, expected in zip(inputs, references, strict=True):
        tag = record["tag"]
        assert tag == expected["tag"], key
        state, phi = host_inputs(ready, record)
        values, x_terms, valid = evaluate(state, phi, control, layout)
        values = np.asarray(values)
        x, j, heat, _ = values
        assert valid and values.dtype == np.float64 and heat >= 0, (key, tag, values)
        ref = expected["modes"]["cyc"]
        dx = design.rel_floor(ref["dG_RT_terms_abs"])
        dj = design.floor_J(ref)
        # The host comparison propagates both factors' roundoff into the heat and work.
        floors = np.array(
            [
                dx,
                dj,
                rt_pj * (dj * (abs(x) + dx) + abs(j) * dx),
                rt_pj * (dj * (float(x_terms) + dx) + abs(j) * dx),
            ]
        )
        error = np.abs(
            values - [ref["dG_RT"], ref["J"], expected["heat_pJ_per_s"], expected["work_pJ_per_s"]]
        )
        assert np.all(error <= fixture.FLOORS * floors), (key, tag, values, error, floors)
        worst_error = np.maximum(worst_error, error)
        worst_floors = np.maximum(worst_floors, error / floors)
        if abs(ref["J"]) <= fixture.FLOORS * dj:
            assert tag == "static_head_+0" and abs(j) <= fixture.FLOORS * dj, (key, tag, j)
            counts["within_stall_band"] += 1
        else:
            assert np.sign(j) == np.sign(ref["J"]) == -np.sign(x), (key, tag, values)
            counts["forward" if j > 0 else "reverse"] += 1

    # Test proton reversal near stall and voltage independence at a nonzero neutral flux.
    charged = law["law_id"] == "cells.cycle.proton_atp_mass_action_positive@1"
    voltage_input = (
        next(r for r in inputs if r["tag"] == "static_head_+0") if charged else inputs[0]
    )
    state, phi = host_inputs(ready, voltage_input)
    offset = np.zeros_like(phi)
    offset[0] = 0.01
    low, high = (
        np.asarray(evaluate(state, v, control, layout)[0]) for v in (phi - offset, phi + offset)
    )
    if charged:
        assert low[1] < 0 < high[1], (key, low, high)
    else:
        assert low[1] != 0, key
        np.testing.assert_array_equal(low, high)

    # Both off switches must suppress a cycle that would otherwise turn.
    state, phi = host_inputs(ready, inputs[0])
    on = np.asarray(evaluate(state, phi, control, layout)[0])
    assert on[1] != 0, key
    off = control._replace(cycle_availability=np.zeros_like(control.cycle_availability))
    empty = layout._replace(cycle_capacity_fmol_s=np.zeros_like(layout.cycle_capacity_fmol_s))
    for controls, params in ((off, layout), (control, empty)):
        values, _, valid = evaluate(state, phi, controls, params)
        assert valid, key
        np.testing.assert_array_equal(values, [on[0], 0, 0, 0])

    return {
        "states": len(references),
        **counts,
        "off_controls": 2,
        "max_abs_error": worst_error.tolist(),
        "max_error_in_floors": worst_floors.tolist(),
        "voltage_control_state": voltage_input["tag"],
        "flux_minus_plus_10mV_fmol_s": [float(low[1]), float(high[1])],
    }


def pump_stall_mV(inputs, params, expected_mV):
    def flux(v):
        state = inputs._replace(voltage_V=v)
        assert proton_pump.domain_valid(state, params, 1, xp=np)
        return float(proton_pump.kinetics(state, params, 1, xp=np).cycles_fmol_s)

    center = expected_mV / 1000
    root = brentq(flux, center - 0.01, center + 0.01, xtol=1e-14)
    assert flux(root - 1e-6) < 0 < flux(root + 1e-6)
    assert abs(1000 * root - expected_mV) < 0.2
    return 1000 * root


def vacuole_reversals():
    data = json.loads((Path(__file__).parent / "data/kettner2003_vacuole.json").read_text())
    fuel = data["fuel_mM"]
    # The paper's rounded E_H column uses 59.2 mV per pH unit. At 25 °C it is 59.16.
    temperature = 298.15
    rt = R * temperature
    atp, adp, pi = (fuel[key] for key in ("ATP", "ADP", "Pi"))
    log_q = math.log(adp * pi / (atp * proton_pump.STANDARD_STATE_mM))
    output = []
    for cyt, lumen, e_atp, e_h, relation, observed, se, trials in data["rows"]:
        inputs = proton_pump.Inputs(
            10 ** (3 - cyt), 10 ** (3 - lumen), 0, atp, adp, pi, temperature
        )
        # Supply the paper's effective fuel energy. Its value is shared across a cytosolic pH
        # group and uses no observed reversal. The positive capacity and saturations set scale.
        dg0 = F * e_atp / 1000 - rt * log_q
        roots = []
        for n in range(1, 5):
            params = proton_pump.Parameters(1, n, 1e-4, 0.1, dg0, cyt, 0.1)
            roots.append(pump_stall_mV(inputs, params, e_atp / n + e_h))
        output.append(
            dict(
                cytosol_pH=cyt,
                lumen_pH=lumen,
                relation=relation,
                observed_mV=observed,
                SE_mV=se,
                trials=trials,
                E_H_mV=e_h,
                engine_stall_mV_by_n=roots,
            )
        )
    fixed_cytosol = {row["lumen_pH"]: row for row in output if row["cytosol_pH"] == 7.5}
    a, b = fixed_cytosol[4.1], fixed_cytosol[6.0]
    shifts = np.subtract(b["engine_stall_mV_by_n"], a["engine_stall_mV_by_n"])
    np.testing.assert_allclose(shifts, shifts[0], atol=1e-8, rtol=0)
    return dict(
        rows=output,
        measured_shift_mV=b["observed_mV"] - a["observed_mV"],
        table_E_H_shift_mV=b["E_H_mV"] - a["E_H_mV"],
        engine_shifts_mV=shifts.tolist(),
    )


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    laws = {law["id"]: law for law in fixture.LAWS}
    with jax.default_device(jax.devices("cpu")[0]):
        panels = {
            key: check_panel(laws[key])
            for key in ("v1_proton_n2", "v1_neutral_n1", "v1_neutral_n2", "ff_neutral_n1")
        }
    print(
        json.dumps(
            {
                "model": "cells.model.resolved_pump_tissue@3",
                "backend": "cpu",
                "jax": jax.__version__,
                "dtype": "float64",
                "columns": ["dG_RT", "cycles_fmol_s", "heat_pJ_s", "work_pJ_s"],
                "allowed_floors": fixture.FLOORS,
                "panels": panels,
                "yeast_vacuole": vacuole_reversals(),
            },
            indent=2,
            allow_nan=False,
        )
    )
