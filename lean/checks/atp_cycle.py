"""Compare the tissue transporter's compiled rates to the frozen ATP-cycle panels."""

import json

import jax
import jax.numpy as jnp
import numpy as np

from cells.kinds import transporter
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
    charged = law["law_id"] == "cells.proton_atp_mass_action_positive@1"
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
                "model": "resolved_pump_tissue@3",
                "backend": "cpu",
                "jax": jax.__version__,
                "dtype": "float64",
                "columns": ["dG_RT", "cycles_fmol_s", "heat_pJ_s", "work_pJ_s"],
                "allowed_floors": fixture.FLOORS,
                "panels": panels,
            },
            indent=2,
            allow_nan=False,
        )
    )
