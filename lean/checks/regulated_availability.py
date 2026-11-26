"""Pulse and washout through both regulatory operators and a fixed-voltage SK2 comparison."""

import argparse
import json
import math
from itertools import pairwise, product
from pathlib import Path

import jax
import numpy as np
from scipy.optimize import brentq

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import species_regulated_availability as regulation
from cells.registry.inventory_species import add_inventory_species
from validation.coupling import state_reference as reference
from validation.tissue import regulated_availability_fixtures as gates
from validation.tissue import secreted_species_fixtures as pools

DT = 1 / 512
END = 1 / 16
C0, K, HILL_N = 0.001, 0.002, 2.0  # mM, mM, dimensionless in a 1 pL cell.
ON, OFF, S0 = 32.0, 8.0, 0.25
BASAL, SCHEDULED = 0.125, 0.75
REPORTER_RATE = 0.125  # fmol/s
SEGMENTS = ((0.0, 64 * C0, 64.0), (1 / 128, 64 * 0.008, 64.0), (1 / 32, 0.0, 64.0))


def reporter_coupling(half_mM, exponent, basal, operating_range):
    return dict(
        id="reporter_gate",
        source=dict(species=pools.SPECIES),
        law="hill_activation",
        basal=basal,
        half_saturation_mM=half_mM,
        hill_coefficient=exponent,
        target=dict(
            operator=pools.TURNOVER,
            control="turnover_rate",
            ids=["make_Y"],
            evaluation="target_half_steps",
            operating_range=operating_range,
        ),
    )


def with_reporter_turnover(raw, routes, controls):
    raw = pools.with_turnover(raw, routes, controls, species=gates.identities([pools.SPECIES, "Y"]))
    reporter = next(r for r in raw["model"]["operators"][-1]["routes"] if r["id"] == "make_Y")
    reporter["species"] = "Y"
    return parse_spec(raw)


def pulse_world(version, dt):
    raw = pools.world(
        nodes=(),
        contacts=(),
        faces=(),
        trace_mM=C0,
        dt=dt,
        end=END,
        observation_times=pools.grid_times(END, dt, dt),
    )
    raw = add_inventory_species(raw, "Y", trace_mM=C0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20)
    m = raw["model"]
    # A K gradient drives a measurable current through one gate-free channel.
    amounts = m["cells"][0]["initial_amount_fmol"]
    amounts["K"], amounts["Na"] = amounts["Na"], amounts["K"]
    m["channels"] = [
        dict(
            id="kleak",
            membrane_id="wall_cell_0",
            kinetic_law="cells.channel.kleak_always_open@1",
            max_permeability_m_per_s=1e-9,
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
    ]
    raw["execution"]["channel_capacity"] = 1
    raw["experiment"]["channel_controls"] = [
        dict(channel_id="kleak", schedule=[dict(time=0.0, availability=SCHEDULED)])
    ]
    cell, ligand = "cell_0", pools.SPECIES
    state = gates.state(
        "gate", [cell], [("hill_activation", ligand, K, HILL_N)], on=ON, off=OFF, initial=S0
    )
    channel = gates.coupling(
        "channel_gate", "channel", ["kleak"], ("state", "gate"), "state_fraction", basal=BASAL
    )
    couplings = [channel]
    if version == 2:
        channel["target"].update(evaluation="step_view", operating_range=[0.0, 1.0])
        couplings.append(reporter_coupling(K, HILL_N, BASAL, [0.0, 0.01]))
    raw = gates.with_coupling(raw, species=[ligand], states=[state], couplings=couplings)
    if version == 2:
        raw["model"]["operators"][-1]["law"] = regulation.LAW_ID_V2
    routes = [
        ("dose", cell, "production"),
        ("wash", cell, "clearance"),
        ("make_Y", cell, "production"),
    ]
    controls = [
        ("dose", cell, [(t, p) for t, p, _ in SEGMENTS]),
        ("wash", cell, [(0.0, 64.0)]),
        ("make_Y", cell, [(0.0, REPORTER_RATE)]),
    ]
    return with_reporter_turnover(raw, routes, controls)


def basal_factor(f):
    return BASAL + (1 - BASAL) * f


def pulse_comparison(version, dt):
    spec = pulse_world(version, dt)
    result = run(spec)
    times, hist, obs = result.times, result.history, result.observations
    np.testing.assert_array_equal(obs.times, times)
    ids = list(spec.model.species_ids)
    ligand_row, reporter_row = ids.index(pools.SPECIES), ids.index("Y")
    concentration = C0 + np.asarray(hist.amount_increment[:, ligand_row, 0])
    state = np.asarray(hist.regulatory_state[:, 0])
    booked = np.asarray(hist.turnover_produced_fmol[:, reporter_row, 0])
    np.testing.assert_allclose(
        hist.amount_increment[:, reporter_row, 0], booked, rtol=0, atol=2e-16
    )
    assert np.max(np.abs(obs.channel_flux_fmol_s)) > 0

    pool = reference.Turnover(C0, 1.0, SEGMENTS)
    source = reference.Input("hill_activation", pool, K, HILL_N)
    solution = reference.integrate([source], ON, OFF, S0, END, record=times)
    pool_error = float(np.max(np.abs(concentration - pool.concentration(times))))
    assert pool_error < 2e-16
    continuous = np.array([solution.s(t) for t in times])
    continuous_integral = np.array([solution.U(t) for t in times])

    # The regulatory operator surrounds the turnover operator, so the gate's two
    # half-steps see the start and end concentrations. The inner channel sees the first gate.
    def advance(s, c):
        a = ON * c**HILL_N / (K**HILL_N + c**HILL_N)
        target = a / (a + OFF)
        return target + (s - target) * math.exp(-(a + OFF) * dt / 2)

    expected_state, held = [S0], []
    for before, after in zip(times[:-1], times[1:], strict=True):
        mid_gate = advance(expected_state[-1], pool.concentration(before))
        held.append(basal_factor(mid_gate))
        expected_state.append(advance(mid_gate, pool.concentration(after)))
    split_error = float(np.max(np.abs(state - expected_state)))
    assert split_error < 2e-14 and np.all((0 <= state) & (state <= 1))
    # The public channel observation evaluates the control at the accepted row.
    np.testing.assert_allclose(
        obs.channel_availability[:, 0],
        SCHEDULED * basal_factor(np.array(expected_state)),
        atol=2e-14,
        rtol=0,
    )
    state_error = float(np.max(np.abs(state - continuous)))
    report = dict(
        version=version,
        dt_s=dt,
        rows=len(times),
        peak_ligand_mM=float(max(concentration)),
        final_ligand_mM=float(concentration[-1]),
        final_gate=float(state[-1]),
        final_channel_availability=float(obs.channel_availability[-1, 0]),
        final_cell_potassium_change_fmol=float(hist.amount_increment[-1, ids.index("K"), 0]),
        max_pool_error_mM=pool_error,
        max_gate_error_vs_split=split_error,
        max_gate_error_vs_continuous=state_error,
    )
    if version == 1:
        np.testing.assert_allclose(booked, REPORTER_RATE * times, rtol=1e-14, atol=0)
        return report
    # Turnover also moves this regulator. Its two target half-steps sample their
    # midpoints. The analytic ligand trajectory is independent of the engine predictor.
    starts = times[:-1]
    first = basal_factor(source.value(starts + dt / 4))
    second = basal_factor(source.value(starts + 3 * dt / 4))
    records = np.asarray(hist.coupling_applied_factor[1:])
    np.testing.assert_allclose(records[:, 0], held, atol=2e-14, rtol=0)
    np.testing.assert_allclose(records[:, 1], second, atol=2e-14, rtol=0)
    inferred_first = np.diff(booked) / (REPORTER_RATE * dt / 2) - records[:, 1]
    np.testing.assert_allclose(inferred_first, first, atol=2e-13, rtol=0)
    expected_booked = np.cumsum(REPORTER_RATE * dt / 2 * (first + second))
    np.testing.assert_allclose(booked[1:], expected_booked, atol=2e-16, rtol=0)
    endpoint_second = basal_factor(source.value(starts + dt / 2))
    endpoint_error = float(np.max(np.abs(records[:, 1] - endpoint_second)))
    assert endpoint_error > 2e-14
    stale = np.max(np.abs(np.diff(booked) - REPORTER_RATE * dt * first))
    assert stale > 1e-9
    exact_booked = REPORTER_RATE * (BASAL * times + (1 - BASAL) * continuous_integral)
    report.update(
        final_reporter_produced_fmol=float(booked[-1]),
        max_stale_step_error_fmol=float(stale),
        max_first_factor_error=float(np.max(np.abs(inferred_first - first))),
        max_second_factor_error=float(np.max(np.abs(records[:, 1] - second))),
        max_second_factor_error_at_left_endpoint=endpoint_error,
        max_booking_error_vs_midpoints_fmol=float(np.max(np.abs(booked[1:] - expected_booked))),
        max_reporter_error_vs_continuous_fmol=float(np.max(np.abs(booked - exact_booked))),
    )
    return report


def pulse_panel():
    panels = []
    for version in (1, 2):
        cases = [pulse_comparison(version, DT / d) for d in (1, 2, 4)]
        for coarse, fine in pairwise(cases):
            ratio = coarse["max_gate_error_vs_continuous"] / fine["max_gate_error_vs_continuous"]
            fine["gate_order"] = math.log2(ratio)
            assert 1.7 <= fine["gate_order"] <= 2.3
        panels.append(cases)
    for first, second in zip(*panels, strict=True):
        for key in ("final_gate", "final_channel_availability", "final_cell_potassium_change_fmol"):
            np.testing.assert_allclose(first[key], second[key], atol=2e-14, rtol=0)
    return panels[0] + panels[1]


def ramp_order():
    """An admitted Hill rate reads a regulator produced by the same turnover half-step."""
    rows = []
    exact = 1 - math.log1p(0.5)  # Integral from 0 to 1 of (1 + t) / (2 + t).
    for steps in (8, 16, 32, 64):
        dt = 1 / steps
        raw = pools.world(nodes=(), contacts=(), faces=(), trace_mM=1.0, dt=dt, end=1.0)
        raw = add_inventory_species(
            raw, "Y", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
        )
        source = reporter_coupling(1.0, 1.0, 0.0, [1.0, 2.0])
        raw = gates.with_coupling(raw, species=[pools.SPECIES], couplings=[source])
        raw["model"]["operators"][-1]["law"] = regulation.LAW_ID_V2
        routes = [(r, "cell_0", "production") for r in ("make_S", "make_Y")]
        controls = [(r, "cell_0", [(0.0, 1.0)]) for r, _, _ in routes]
        spec = with_reporter_turnover(raw, routes, controls)
        hist = run(spec).history
        ids = list(spec.model.species_ids)
        assert hist.amount_increment[-1, ids.index(pools.SPECIES), 0] == 1.0
        amount = float(hist.amount_increment[-1, ids.index("Y"), 0])
        booked = float(hist.turnover_produced_fmol[-1, ids.index("Y"), 0])
        assert abs(amount - booked) < 1e-14
        starts = np.arange(2 * steps) * dt / 2
        rectangles = float(np.sum((1 + starts) / (2 + starts)) * dt / 2)
        midpoints = starts + dt / 4
        midpoint_sum = float(np.sum((1 + midpoints) / (2 + midpoints)) * dt / 2)
        rows.append(
            dict(
                steps=steps,
                dt_s=dt,
                reporter_gain_fmol=amount,
                exact_gain_fmol=exact,
                left_sum_fmol=rectangles,
                midpoint_sum_fmol=midpoint_sum,
                absolute_error_fmol=abs(amount - exact),
            )
        )
    errors = [r["absolute_error_fmol"] for r in rows]
    for coarse, fine in zip(rows[:-1], rows[1:], strict=True):
        h = coarse["dt_s"] / 2
        assert fine["left_sum_fmol"] - coarse["left_sum_fmol"] >= h / 36
    orders = [
        math.log2(a / b) if min(a, b) > 1e-14 else None
        for a, b in zip(errors[:-1], errors[1:], strict=True)
    ]
    # Screen the finest pair at order 1.7, allowing roundoff-level agreement.
    return dict(
        worlds=rows,
        orders=orders,
        second_order=errors[-1] <= 1e-14 or (orders[-1] is not None and orders[-1] >= 1.7),
    )


def hill_fit(doses, observed):
    """At the correct ceiling, log odds lie on one straight line in log dose."""
    log_dose = np.log(doses)

    def slopes(ceiling):
        odds = np.log(observed / (ceiling - observed))
        return np.diff(odds) / np.diff(log_dose)

    def mismatch(ceiling):
        left, right = slopes(ceiling)
        return left - right

    ceiling = brentq(mismatch, np.nextafter(max(observed), np.inf), 1.0, xtol=1e-15)
    exponent = slopes(ceiling)[0]
    half = doses[0] * ((ceiling - observed[0]) / observed[0]) ** (1 / exponent)
    return ceiling, half, exponent


def calcium_clamps(high_mM, input_half_mM, exponent, on, off, plateau):
    """Read free divalent Ca through a regulatory state in two separately buffered cells."""
    dt = 1 / 1024
    times = [0.0, 8 * dt, 64 * dt]
    raw = pools.world(
        cells=(("on", 1.0), ("off", 1.0)),
        nodes=(),
        contacts=(),
        faces=(),
        dt=dt,
        end=times[-1],
        observation_times=times,
    )
    m = raw["model"]
    m["species"].append(dict(id="Ca", valence=2))
    wash_mM = 1e-12  # Positive trace for the zero-calcium washout limit.
    for node in m["cells"] + m["extracellular"]:
        c = high_mM if node["id"] == "on" else wash_mM
        n = c * node["volume_pL"]
        node["initial_amount_fmol"]["Ca"] = n
        node["fixed_charge_equivalent_fmol"] -= 2 * n
    for patch in m["membranes"]:
        patch["permeability_m_per_s"]["Ca"] = 0.0
    raw["execution"]["material_balance_atol_fmol"]["Ca"] = 1e-20
    state = gates.state(
        "sk2",
        ["on", "off"],
        [("hill_activation", "Ca", input_half_mM, exponent)],
        on=on,
        off=off,
        initial={"on": 0.0, "off": plateau},
    )
    spec = parse_spec(gates.with_coupling(raw, species=["Ca"], states=[state]))
    result = run(spec)
    s = np.asarray(result.observations.regulatory_state)
    # Bound slot order follows the declaration's cells.
    np.testing.assert_allclose(s[0], [0.0, plateau], atol=1e-15, rtol=0)
    return dict(
        rise_ms=-1000 * times[1] / math.log1p(-s[1, 0] / plateau),
        washout_ms=-1000 * times[2] / math.log(s[2, 1] / plateau),
        wash_calcium_mM=wash_mM,
    )


def sk2_comparison():
    data = json.loads((Path(__file__).parent / "data/hirschberg1998_sk2.json").read_text())
    readings = dict(zip(data["dose_uM"], data["open_probability"], strict=True))
    doses = np.asarray(data["fit_uM"])
    observed = np.array([readings[x] for x in doses])
    held, jump = data["held_out_uM"], data["jump_uM"]
    wash = data["fit_washout_ms"]

    def steady(c, fit):
        ceiling, half, exponent = fit
        return ceiling / (1 + (half / c) ** exponent)

    fit = hill_fit(doses, observed)
    ceiling, half, exponent = fit
    beta = 1000 / wash
    alpha = beta * ceiling / (1 - ceiling)
    input_half = half / (1 - ceiling) ** (1 / exponent)
    p_jump = steady(jump, fit)
    clamp = calcium_clamps(jump / 1000, input_half / 1000, exponent, alpha, beta, p_jump)
    rise = wash * (1 - p_jump)
    np.testing.assert_allclose(
        [clamp["rise_ms"], clamp["washout_ms"]], [rise, wash], atol=2e-11, rtol=0
    )
    delta = data["reading_precision_probability"]
    corners = [
        hill_fit(doses, observed + perturb) for perturb in product((-delta, delta), repeat=3)
    ]
    p_range = [steady(held, corner) for corner in corners]
    rise_range = [wash * (1 - steady(jump, corner)) for corner in corners]
    return dict(
        ceiling=ceiling,
        apparent_half_uM=half,
        hill_exponent=exponent,
        on_per_s=alpha,
        off_per_s=beta,
        input_half_uM=input_half,
        held_out_uM=held,
        observed_probability=readings[held],
        predicted_probability=steady(held, fit),
        probability_reading_sensitivity=[min(p_range), max(p_range)],
        predicted_plateau_at_jump=p_jump,
        predicted_rise_ms=rise,
        measured_rise_ms=data["held_out_activation_ms"],
        rise_reading_sensitivity_ms=[min(rise_range), max(rise_range)],
        charged_cell_clamps=clamp,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    panel = parser.add_mutually_exclusive_group()
    panel.add_argument(
        "--controls-only", action="store_true", help="omit the second-order claim on the ramp"
    )
    panel.add_argument("--ramp-only", action="store_true", help="only run the four self-regulated turnover worlds")
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        report = {} if args.ramp_only else dict(pulse=pulse_panel(), sk2=sk2_comparison())
        if not args.controls_only:
            report["ramp"] = ramp_order()
        print(json.dumps(report, indent=2, allow_nan=False))
        raise SystemExit(int("ramp" in report and not report["ramp"]["second_order"]))
