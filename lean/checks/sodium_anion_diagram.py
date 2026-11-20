"""Check the eight-state cotransporter against its master equation and fixed-voltage dose law."""

import argparse
import json
from decimal import Decimal, localcontext
from itertools import product
from math import prod
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.execution.runner import run
from cells.kinds import transporter
from cells.laws.cycles import forms
from cells.laws.cycles import na2_anion_symport_diagram as law
from tests.unit import test_na2_anion_symport_diagram as fixture
from tests.unit.test_cycle_forms import master_equation
from validation.core_seams.references import exact

DATA = Path(__file__).with_name("data")
RETURN_CHARGE = fixture.rates() | dict.fromkeys(fixture.ZETA, 0.0) | {"z_empty_b": 1.0}


def readouts(state, layout, control, v, opening, xp):
    phi = xp.concatenate(
        (xp.reshape(v, (1,)), xp.zeros(layout.active.size + layout.outside_active.size - 1))
    )
    ctl = control._replace(cycle_availability=xp.full_like(control.cycle_availability, opening))
    r = transporter.probe(state, phi, ctl, layout, xp=xp)
    m = r.modes
    return dict(
        p=r.occupancy[:, 0],
        edge=r.edges.net_fmol_s[:, 0],
        j=m.j[0, 0],
        plus=m.j_plus[0, 0],
        minus=m.j_minus[0, 0],
        diagram_minus=m.j_minus_diagram[0, 0],
        slope=m.d_j_d_v[0, 0],
        rows=r.rows.rate[:, 0],
        heat=r.populations.heat_pJ_s[0],
        valid=r.populations.valid[0],
    )


compiled = jax.jit(
    lambda state, layout, ctl, v, opening: readouts(state, layout, ctl, v, opening, jnp)
)


def root_weight(rates):
    """Trees directed to state zero, by successive choices of the omitted edge."""
    suffix, weight = Decimal(1), Decimal(0)
    for f, b in reversed(rates):
        weight = suffix + b * weight
        suffix *= f
    return weight


def one_way_rates(probs, rates):
    # The independent master-equation occupancy fixes the overall tree normalization.
    with localcontext(prec=50):
        total = root_weight(rates) / probs[0]
        return float(prod(f for f, _ in rates) / total), float(prod(b for _, b in rates) / total)


def master_panel():
    cases = 0
    max_p_error, max_stall_slope_error = 0.0, 0.0
    iv_ratios = {}
    for name, values in (("outer_well", fixture.VALUES), ("empty_return", RETURN_CHARGE)):
        form = forms.resolved(law.CYCLE, values)
        for end in ("a", "b"):
            raw = fixture.world(values)
            pop = raw["model"][transporter.MODEL_KEY][0]
            pop["orientation"] = {"N": end}
            spec, _, state, layout, control = fixture.bound(raw)
            c = fixture.concentrations(spec)  # the fixture reports N=cell, P=bath
            sign = 1 if end == "a" else -1
            opposite = {"N": "P", "P": "N"}
            ln_c = np.log(
                [c[ion, side if end == "a" else opposite[side]] for ion, side in form.rows]
            )
            f_rt = float(exact.F_over_RT(spec.model.temperature_K))
            stall = -(2 * (ln_c[0] - ln_c[1]) + ln_c[2] - ln_c[3]) / f_rt
            for offset in (-0.075, -0.005, 0, 0.005, 0.075):
                psi = (stall + offset) * f_rt
                probs, rates, nets = master_equation(form, ln_c, psi)
                plus, minus = one_way_rates(probs, rates)
                with localcontext(prec=50):
                    traffic = np.array(
                        [
                            float(probs[i] * f + probs[(i + 1) % 8] * b)
                            for i, (f, b) in enumerate(rates)
                        ]
                    )
                for opening in (0.0, 0.25, 1.0):
                    r = compiled(state, layout, control, sign * (stall + offset), opening)
                    count = pop["capacity_fmol_s"] * opening  # rate scale is 1/s
                    j = count * float(nets[0])
                    assert bool(r["valid"]) and r["j"].dtype == np.float64
                    np.testing.assert_allclose(r["p"], list(map(float, probs)), rtol=4e-13, atol=0)
                    max_p_error = max(
                        max_p_error, float(np.abs(r["p"] - np.array(probs, float)).max())
                    )
                    np.testing.assert_allclose(
                        [r["plus"], r["minus"], r["diagram_minus"]],
                        count * np.array([plus, minus, minus]),
                        rtol=4e-13,
                        atol=0,
                    )
                    assert np.all(
                        np.abs(r["edge"] - count * np.array(nets, float)) <= 4e-13 * count * traffic
                    )
                    assert abs(r["j"] - j) <= 4e-13 * count * (plus + minus)
                    np.testing.assert_allclose(
                        r["rows"], r["j"] * np.array([2, -2, 1, -1]), rtol=3e-15, atol=0
                    )
                    assert r["heat"] >= 0
                    if offset == 0 and count:
                        reference = -sign * f_rt * plus * count
                        error = abs(float(r["slope"]) / reference - 1)
                        assert error < 4e-13
                        max_stall_slope_error = max(max_stall_slope_error, error)
                    cases += 1
            if end == "a":
                j50, j150 = (
                    float(compiled(state, layout, control, v, 1.0)["j"]) for v in (-0.05, -0.15)
                )
                iv_ratios[name] = j150 / j50
    return dict(
        cases=cases,
        max_occupancy_error=max_p_error,
        max_relative_stall_slope_error=max_stall_slope_error,
        current_magnitude_ratio_at_minus150_to_minus50_mV_in_fixture=iv_ratios,
    )


def dose_panel():
    output = []
    # Increase both anion binding rates equally to put the half-response inside the dose series.
    # The forward and reverse cycle products acquire the same factor.
    values = fixture.VALUES.copy()
    for key in ("k_b_P_f", "k_b_N_b"):
        values[key] *= 8192
    spec, _, _, _, _ = fixture.bound(fixture.world(values))
    form = forms.resolved(law.CYCLE, values)
    c = fixture.concentrations(spec)
    assert c["B", "P"] == 1  # scale forward edge 2 relative to this 1 mM bath
    for voltage in (-0.05, -0.15):
        _, rates, _ = master_equation(
            form,
            np.log([c[row] for row in form.rows]),
            voltage * float(exact.F_over_RT(spec.model.temperature_K)),
        )
        with localcontext(prec=50):
            blank = rates.copy()
            blank[2] = Decimal(0), rates[2][1]

            def total(edges):
                return sum(root_weight(edges[i:] + edges[:i]) for i in range(8))

            d = total(blank)
            slope = total(rates) - d
            j0 = -prod(b for _, b in rates) / d
            amplitude = prod(f for f, _ in rates) / slope - j0
            half_mM = d / slope
        max_error = 0.0
        levels = (0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float(half_mM))
        assert min(levels) < half_mM < max(levels)
        for level in levels:
            raw = fixture.world(values)
            pop = raw["model"][transporter.MODEL_KEY][0]
            bath = raw["model"]["extracellular"][0]
            amount = level * bath["volume_pL"]
            bath["fixed_charge_equivalent_fmol"] += (
                amount - bath["initial_amount_fmol"][fixture.ANION]
            )
            bath["initial_amount_fmol"][fixture.ANION] = amount
            _, _, state, layout, ctl = fixture.bound(raw)
            flux = float(compiled(state, layout, ctl, voltage, 1.0)["j"])
            induced = flux / pop["capacity_fmol_s"] - float(j0)
            predicted = float(amplitude) * level / (float(half_mM) + level)
            error = abs(induced / predicted - 1)
            assert error < 2e-11
            max_error = max(error, max_error)
        output.append(
            dict(
                voltage_V=voltage,
                half_mM=float(half_mM),
                positive_doses=len(levels),
                max_relative_response_error=max_error,
            )
        )
    return output


def host_run():
    raw = fixture.world()
    # Isolate the two material rows. Keep the other declared mechanisms present with zero flux.
    for membrane in raw["model"]["membranes"]:
        membrane["permeability_m_per_s"] = dict.fromkeys(membrane["permeability_m_per_s"], 0.0)
    for control in raw["experiment"]["pump_controls"] + raw["experiment"]["channel_controls"]:
        for event in control["schedule"]:
            event["availability"] = 0.0
    spec, _, _, _, _ = fixture.bound(raw)
    result = run(spec)
    final = result.final.state
    cycles = float(np.sum(final.cycle_count))
    gains = [
        float(final.amount_increment[spec.model.species_ids.index(s), 0])
        for s in ("Na", fixture.ANION)
    ]
    np.testing.assert_allclose(gains, [2 * cycles, cycles], rtol=32 * exact.EPS, atol=0)
    heat = float(np.sum(final.cycle_dissipated_energy_pJ))
    assert cycles != 0 and heat > 0
    return dict(
        steps=int(result.final.step_index),
        cycles_fmol=cycles,
        cell_gains_fmol=gains,
        heat_pJ=heat,
        max_global_charge_error_C=float(result.diagnostics["max_global_charge_error_C"]),
    )


def capacity_check():
    # Keep all four compared rates normal binary64 numbers, even below the diagnostic's floor.
    values = {
        key: val * 1024 if key.startswith("k_") else val for key, val in fixture.VALUES.items()
    }
    spec, _, _, _, _ = fixture.bound(fixture.world(values))
    form = forms.resolved(law.CYCLE, values)
    c = fixture.concentrations(spec)
    probs, rates, nets = master_equation(
        form,
        np.log([c[row] for row in form.rows]),
        -0.05 * float(exact.F_over_RT(spec.model.temperature_K)),
    )
    _, reverse_per_carrier = one_way_rates(probs, rates)
    rows = []
    for k in (1e-299, 1e-300, 1e-302, 0.0):
        _, _, state, layout, ctl = fixture.bound(fixture.world(values, capacity=k))
        for backend in ("numpy", "compiled"):
            r = (
                readouts(state, layout, ctl, -0.05, 1.0, np)
                if backend == "numpy"
                else compiled(state, layout, ctl, -0.05, 1.0)
            )
            mode, edge, reverse, diagram_reverse = map(
                float, (r["j"], r["edge"][0], r["minus"], r["diagram_minus"])
            )
            assert bool(r["valid"]) and float(r["rows"][2]) == mode
            np.testing.assert_allclose(
                [mode, reverse],
                k * np.array([float(nets[0]), reverse_per_carrier]),
                rtol=4e-13,
                atol=0,
            )
            if k:
                assert min(mode, edge, reverse, diagram_reverse) > np.finfo(float).tiny
            ok = np.allclose([edge, diagram_reverse], [mode, reverse], rtol=1e-10, atol=0)
            rows.append(
                dict(
                    capacity_fmol_s=k,
                    backend=backend,
                    mode_flux_fmol_s=mode,
                    edge_flux_fmol_s=edge,
                    reverse_flux_fmol_s=reverse,
                    diagram_reverse_fmol_s=diagram_reverse,
                    consistent=bool(ok),
                )
            )
    return rows


def measured_dose(filename):
    data = json.loads((DATA / filename).read_text())
    observed = dict(
        zip(data["external_propionate_uM"], data["inward_current_magnitude_nA"], strict=True)
    )
    x1, x2 = data["fit_uM"]

    def fit(y1, y2):
        amplitude = (x2 - x1) / (x2 / y2 - x1 / y1)
        return amplitude, x1 * (amplitude / y1 - 1)

    amp, half = fit(observed[x1], observed[x2])
    prec = data["reading_precision_nA"]
    fits = [
        fit(observed[x1] + da, observed[x2] + db) for da, db in product((-prec, prec), repeat=2)
    ]
    held = []
    for x in data["evaluation_uM"]:
        limits = [a * x / (k + x) for a, k in fits]
        held.append(
            dict(
                propionate_uM=x,
                observed_nA=observed[x],
                predicted_nA=amp * x / (half + x),
                reading_sensitivity_nA=[min(limits), max(limits)],
            )
        )
    return dict(amplitude_nA=amp, half_uM=half, held_out=held)


def measured_response():
    iv = json.loads((DATA / "coady2007_lactate_voltage.json").read_text())
    low, high = iv["lactate_induced_current_uA"]
    return dict(
        **measured_dose("miyauchi2004_propionate.json"),
        observed_lactate_voltage_ratio=high / low,
        independent_propionate=measured_dose("paroder2006_propionate.json"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controls-only", action="store_true", help="run the ordinary cases and dose comparison"
    )
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        result = dict(
            master=master_panel(), dose=dose_panel(), tissue=host_run(), biology=measured_response()
        )
        if not args.controls_only:
            result["capacity"] = capacity_check()
        print(json.dumps(result, indent=2, allow_nan=False))
        raise SystemExit(int(any(not row["consistent"] for row in result.get("capacity", []))))
