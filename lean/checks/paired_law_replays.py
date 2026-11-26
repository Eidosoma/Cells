"""Replay independently measured responses using the registered Cells laws on CPU."""

import json
import math
from functools import partial
from pathlib import Path

import charged_permeation
import jax
import jax.numpy as jnp
import kv15_ph
import numpy as np
import population_units
from scipy.optimize import curve_fit
from scipy.special import expit

from cells.laws.routes import inward_rectifier_linear_driving_force as kir
from cells.numerics.exponential_gates import advance
from cells.operators import membrane_state
from cells.registry import laws
from validation.fr7 import unit_turnover_fixtures as turnover

DATA = Path(__file__).with_name("data")


def read(name):
    return json.loads((DATA / name).read_text())


def carrier_current():
    rows = charged_permeation.biology()
    for key, units in (("red_cell_chloride", "mA_per_g_Hb"), ("bilayer_potassium", "nA")):
        row = rows[key]
        # The flux is linear in P. This is the P needed at evaluation divided by the fitted P.
        row["evaluation_over_calibration_P"] = row[f"observed_{units}"] / row[f"predicted_{units}"]
    return rows


def kir_slopes(data):
    def ratio(inside, high, low, temperature, drive, half, slope):
        def conductance(outside):
            e = kir.reversal_V(inside, outside, temperature)
            return kir.slope_conductance_S(
                inside, outside, e + drive, temperature, 1.0, 1.0, high, half, slope, 1.0
            )

        return conductance(low) / conductance(high)

    compare = jax.jit(ratio)
    rows = {}
    for study, column in (
        ("ishihara2018_kir21_unitary@1", "slope_pS_approx"),
        ("matsuda1991_ventricular_unitary@1", "slope_pS"),
    ):
        entry = data[study]
        high, *others = entry["external_K_mM"]
        slopes = entry[column]
        temp = 273.15 + np.mean(entry["temperature_range_C"])
        ratios = []
        for i, low in enumerate(others, 1):
            if "internal_K_mM" in entry and entry["internal_K_mM"][i] != entry["internal_K_mM"][0]:
                continue
            # Compare the inward slope at the same V-E on each side. Its ratio is independent
            # of the unknown internal K, area, absolute gain and common rectification parameters.
            panel = [
                float(compare(inside, high, low, temp, drive, half, slope))
                for inside in (100.0, 150.0)
                for drive in (-0.08, -0.04)
                for half, slope in ((0.0, 0.01), (0.04, 0.05))
            ]
            np.testing.assert_allclose(panel, math.sqrt(low / high), rtol=3e-15)
            ratios.append(
                dict(
                    low_K_mM=low,
                    high_K_mM=high,
                    external_Na_mM=entry.get("external_Na_mM", [None] * len(slopes))[i],
                    measured_slope_ratio=slopes[i] / slopes[0],
                    native_equal_drive_slope_ratio=panel[0],
                    predicted_low_pS=slopes[0] * panel[0],
                )
            )
        rows[study] = ratios
    return rows


def bath_specimen(protocol, pH):
    host, state, control, layout = kv15_ph.specimen(protocol, external_pH=pH)
    free_H = layout.extracellular_amount_reference[-1, 0] / layout.extracellular_volume[0]
    np.testing.assert_allclose(free_H, 10 ** (3 - pH), rtol=2e-15)
    return host, state, control, layout


def kv15_tail(protocol, pH, tail_mV, pulse_ms, select_peak, commands_mV):
    law = laws.active().lookup("cells.channel.kv1p5_mh@1")
    host, state, control, layout = bath_specimen(protocol, pH)
    voltage = np.asarray(commands_mV) / 1000
    lo, hi = law.voltage_domain_V
    assert lo <= voltage.min() and voltage.max() <= hi and lo <= tail_mV / 1000 <= hi
    initial = law.kinetics(jnp.array([-0.080]))[0]
    times = jnp.linspace(0.0, pulse_ms / 1000, 1001)

    def tail(v):
        targets, clocks = law.kinetics(jnp.array([v]))
        gates = advance(initial, targets, clocks, targets, clocks, times, xp=jnp)
        tick = jnp.argmax(law.opening(gates, xp=jnp)) if select_peak else -1
        held = state._replace(channel_gate=gates[:, tick, None])
        return host.clamped_channel_flux(held, control, layout, tail_mV / 1000, xp=jnp)[1][0]

    curve = np.asarray(jax.jit(jax.vmap(tail))(voltage))
    assert np.max(np.abs(curve)) > 0
    return curve


def rising_half(curve, volts):
    end = np.argmax(curve) + 1
    assert np.all(np.diff(curve[:end]) > 0)
    return np.interp(0.5, curve[:end], volts[:end])


def boltzmann(voltage, maximum, midpoint, slope):
    return maximum * expit((voltage - midpoint) / slope)


def kv15(data):
    paired = read("paired_calibration_measurements.json")
    trapani = read("trapani2003_kv15_ph.json")["trapani2003_kv15_ph"]
    native = laws.active().lookup("cells.channel.kv1p5_mh@1")
    mids = trapani["panel_F"]["midpoint_mV"]
    measured = [
        mids["acid"] - mids["control"],
        np.diff(paired["longobardo2001_kv15_controls@1"]["midpoint_mV"])[0],
    ]
    rows = {}
    for study, k_in, k_out, pHi, pHs, tails, elapsed, select_peak, shift, spacing in (
        ("trapani", 100, 10, 7.3, [7.3, 6.8], [-90, -90], 150, True, measured[0], 5),
        ("longobardo", 150, 4, 7.25, [7.4, 6.5], [-40, -30], 250, False, measured[1], 10),
    ):
        # Trapani adjusted prepulse duration to the step peak. Search over the first 150 ms;
        # an altered peak time or finite recording delay is outside this direction comparison.
        protocol = {"inside_K_mM": k_in, "outside_K_mM": k_out, "inside_pH": pHi}
        volts = np.arange(-80, 61, spacing)
        curves = [
            kv15_tail(protocol, pH, tail, elapsed, select_peak, volts)
            for pH, tail in zip(pHs, tails, strict=True)
        ]
        normal, acid = [c / c[np.argmax(np.abs(c))] for c in curves]
        np.testing.assert_allclose(normal, acid, atol=2e-14, rtol=2e-14)
        rows[study] = dict(
            native_normalized_midpoint_change_mV=rising_half(acid, volts)
            - rising_half(normal, volts),
            observed_midpoint_change_mV=shift,
            tail_mV=tails,
            bath_pH=pHs,
            maximum_normalized_tail_difference=float(np.max(np.abs(acid - normal))),
        )

    study = data["jager2001_kv15_potassium@1"]

    def peak_current(ko, pH):
        protocol = {"inside_K_mM": study["internal_KF_mM"], "outside_K_mM": ko, "inside_pH": 7.2}
        voltage = study["test_mV"]
        return float(kv15_tail(protocol, pH, voltage, study["pulse_ms"], True, [voltage])[0])

    small = []
    for pH in study["outside_pH"]:
        anchor = peak_current(study["external_K_mM"][1], pH)
        estimates = [peak_current(ko, pH) / anchor for ko in (1e-3, 1e-6)]
        assert abs(estimates[0] - estimates[1]) < 1e-5 and anchor > 0
        small.append(estimates)
    rows["jager"] = dict(
        pH=study["outside_pH"],
        positive_low_K_mM=[1e-3, 1e-6],
        native_low_over_4p5_by_pH=small,
        observed_zero_over_4p5_by_pH=study["zero_over_4p5_peak_approx"],
    )
    kehl = paired["kehl2002_kv15_potassium@1"]
    # Fit the instantaneous native tails on each pair's common prepulse grid.
    # Kehl estimated onset currents by extrapolation. The acid 3.5 mM series
    # extends to +65 mV, beyond the law's ceiling; 140 mM has a fully shared grid.
    rows["kehl"] = {}
    for ko, obs in zip(kehl["external_K_mM"][1:], kehl["relative_gmax"][1:], strict=True):
        grids = data["kehl2002_tail_protocol"]["prepulse_range_mV"][str(ko)]
        volts = np.arange(max(g[0] for g in grids), min(g[1] for g in grids) + 1, 5)
        protocol = {"inside_K_mM": 130, "inside_pH": 7.4, "outside_K_mM": ko}
        normal, acid = [
            kv15_tail(protocol, pH, -50, 300, False, volts) for pH in kehl["outside_pH"]
        ]
        scale = normal[np.argmax(np.abs(normal))]
        assert np.sign(scale) == (1 if ko == 3.5 else -1)
        maxima = [
            curve_fit(
                boltzmann, volts, c / scale, p0=(1, -5, 5), bounds=([0, -100, 0.1], [5, 100, 50])
            )[0][0]
            for c in (normal, acid)
        ]
        np.testing.assert_allclose(normal / scale, acid / scale, atol=2e-14, rtol=2e-14)
        rows["kehl"][ko] = dict(
            native_acid_over_control_fitted_max=maxima[1] / maxima[0],
            shared_prepulse_range_mV=[int(volts[0]), int(volts[-1])],
            full_grid_both_pH=grids[0] == grids[1],
            native_tail_sign=int(np.sign(scale)),
            measured_relative_gmax=obs,
        )
    high = paired["trapani2003_kv15_high_voltage@1"]["test_mV"]
    assert high / 1000 > native.voltage_domain_V[1]
    rows["omitted_trapani_step_mV"] = high
    return rows


def receptor_cohorts(data):
    rows = {}
    for key, fast_pct, fast_half_days in (
        ("strack2011_achr_two_components@1", "fast_percent", "fast_half_life_days"),
        ("stanley1983_achr_turnover@1", "fast_percent_approx", "fast_half_life_h"),
    ):
        study = data[key]
        fast = study[fast_pct] / 100
        half = study[fast_half_days] / (24 if fast_half_days.endswith("_h") else 1)
        fractions = np.array([fast, 1 - fast])
        rates = math.log(2) / np.array([half, study["slow_half_life_days"]])
        raw = turnover.cell()
        for channel, weight in zip(raw["model"]["channels"], fractions, strict=True):
            channel["abundance"] = float(weight)
        routes = [turnover.route("fast", "kir_0"), turnover.route("slow", turnover.SECOND)]
        controls = {
            r["id"]: [(0.0, 0.0, rate / 86400)] for r, rate in zip(routes, rates, strict=True)
        }
        _, model, state, control, p = population_units.bound(
            turnover.with_producer(raw, routes, controls)
        )
        op = model.operators[-1]
        initial = np.asarray(membrane_state.units(state, p, xp=np))
        np.testing.assert_allclose(initial / initial.sum(), fractions)
        step = jax.jit(partial(op.half_step, xp=jnp))
        points = {}
        for day in range(1, 15):
            state, ok = step(state, 86400.0, control, p)
            assert ok
            actual = np.asarray(membrane_state.units(state, p, xp=np)) / initial.sum()
            np.testing.assert_allclose(
                actual, fractions * np.exp(-rates * day), rtol=3e-14, atol=8 * np.finfo(float).eps
            )
            if day in (1, 3, 7, 14):
                points[day] = float(actual.sum())
        rows[key] = points
    return rows


if __name__ == "__main__":
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    measured = read("paired_replay_measurements.json")
    print(
        json.dumps(
            dict(
                constant_field=carrier_current(),
                kir=kir_slopes(measured),
                kv15=kv15(measured),
                receptor_cohorts=receptor_cohorts(read("membrane_physiology_pairs.json")),
            ),
            indent=2,
            allow_nan=False,
        )
    )
