"""Compare finite-well wash events with an independent inventory and dilution calculation."""

import argparse
import json
import math
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import parse_spec
from cells.execution import runner
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.execution.schedule import control_values
from cells.execution.state import initialise
from cells.operators import site_occupancy, wash_schedule
from cells.registry.models import get_model
from validation.tissue import wash_schedule_fixtures as well


def prepared(fractions, free, volume, buffer, *, sites):
    dt = 1 / 64
    raw = well.well(free=free, volume=volume, sites=sites, dt=dt, end=(len(fractions) + 2) * dt)
    times = [(i + 1) * dt for i in range(len(fractions))]
    events = [(t, "well", f, {well.TRACER: buffer}) for f, t in zip(fractions, times, strict=True)]
    return parse_spec(well.with_wash(raw, ["well"], events)), times


def exchanges(fractions):
    free, volume, buffer = 60.0, well.V_WELL, well.TRACE_mM
    spec, times = prepared(fractions, free, volume, buffer, sites=True)
    model = get_model(spec.model)
    initial, p = model.initial_values(spec)
    state = initial
    op = next(op for op in model.events if op.LAW_ID == wash_schedule.LAW_ID)
    event = jax.jit(lambda row, ctrl: op.event(row, ctrl, p, xp=jnp))
    s = spec.model.species_ids.index(well.TRACER)
    w = [node.id for node in spec.model.extracellular].index("well")
    ions = np.array(spec.model.valence) != 0
    target = buffer * volume
    sample = supply = 0.0
    retained = 1.0
    errors = []
    for t, f in zip(times, fractions, strict=True):
        control = model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [t])))
        before = target + retained * (free - target)
        sample += f * before
        supply += f * target
        retained *= 1 - f
        state, valid = event(state, control)
        assert bool(valid)
        amount = float(p.extracellular_amount_reference[s, w] + state.extracellular_amount_increment[s, w])
        expected = target + retained * (free - target)
        errors.extend((abs(amount - expected), abs(float(state.wash_collected_fmol[s, w]) - sample),
                       abs(float(state.wash_supplied_fmol[s, w]) - supply),
                       abs(amount + sample - supply - free)))
        np.testing.assert_array_equal(state.wash_collected_fmol[ions, w], state.wash_supplied_fmol[ions, w])
        np.testing.assert_array_equal(state.extracellular_amount_increment[ions, w],
                                      initial.extracellular_amount_increment[ions, w])
        for field in site_occupancy.STATE_AXES:
            np.testing.assert_array_equal(getattr(state, field), getattr(initial, field))
        heat = float(state.wash_last_mixing_heat_pJ[w])
        assert heat == 0.0 if f == 1 else math.isfinite(heat) and heat >= 0
    assert max(errors) <= 8 * np.spacing(free)
    return dict(fractions=fractions, final_free_fmol=amount, collected_fmol=sample,
                supplied_fmol=supply, max_amount_error_fmol=max(errors))


def whole_wash(exponent):
    # Exactly representable binary values probe the host's documented anchor limit.
    free, volume = 64.0, float(2**20)
    buffer = math.ldexp(free / volume, -exponent)
    spec, _ = prepared([1.0], free, volume, buffer, sites=False)
    s = spec.model.species_ids.index(well.TRACER)
    w = [node.id for node in spec.model.extracellular].index("well")
    expected = volume * buffer
    row = dict(initial_fmol=free, target_fmol=expected, initial_to_target=2**exponent)
    try:
        result = run(spec)
    except NumericalError as exc:
        if exponent != 60:
            raise
        return dict(row, completed=False, refusal=str(exc))
    actual = float(free + result.history.extracellular_amount_increment[-1, s, w])
    assert actual == expected
    return dict(row, completed=True, stored_fmol=actual)


def ion_counters(fraction):
    """Follow the counters through the public compiled run, including the final accumulation."""
    times = [0.02, 0.04, 0.06]
    raw = well.well(sites=False, volume=1e6, dt=0.01, end=0.08)
    events = [(t, "well", fraction, {well.TRACER: well.TRACE_mM}) for t in times]
    spec = parse_spec(well.with_wash(raw, ["well"], events))
    start = initialise(spec)
    layout = start.layout
    refusal = None
    try:
        hist = run(spec, start).history
    except NumericalError as exc:
        if str(exc) != "Resolved pump accounting failed: outside":
            raise
        # The normal host ledger refused these rows. Retain the same compiled scan's
        # pre-ledger counters for diagnosis, with all per-step domain checks enabled.
        refusal = str(exc)
        model = get_model(spec.model)
        grid = runner.timeline(spec)
        _, rows, valid = runner._compiled_discrete_rollout(
            start.state, runner.integration_steps(spec, grid), control_values(spec, grid[:-1]),
            model.parameters(spec, layout), layout.active, model.checked_step)
        assert np.all(valid)
        hist = jax.tree_util.tree_map(
            lambda first, rest: np.concatenate((np.asarray(first)[None], np.asarray(rest))),
            start.state, rows)
    w = [node.id for node in spec.model.extracellular].index("well")
    ions = np.flatnonzero(spec.model.valence)
    amounts = np.asarray(hist.extracellular_amount_increment)[:, ions, w]
    np.testing.assert_array_equal(amounts, np.broadcast_to(amounts[0], amounts.shape))
    initial = np.asarray(layout.extracellular_amount_reference)[ions, w] + amounts[0]
    collected = np.asarray(hist.wash_collected_fmol)[:, ions, w]
    supplied = np.asarray(hist.wash_supplied_fmol)[:, ions, w]
    # The fixture changes no ions and delivers the same fraction at each of three events.
    count = np.asarray(hist.wash_applied)[:, w]
    np.testing.assert_array_equal(np.unique(count), np.arange(len(times) + 1))
    assert np.all(np.diff(count) >= 0)
    expected = count[:, None] * fraction * initial
    for booked in (collected, supplied):
        np.testing.assert_allclose(booked, expected, rtol=8 * np.finfo(float).eps, atol=0)
    residual = collected - supplied
    return dict(fraction=fraction, event_count=int(count[-1]), inventories_unchanged=True,
                run_completed=refusal is None, refusal=refusal,
                max_abs_counter_difference_fmol=float(np.max(abs(residual))),
                final_collected_minus_supplied_fmol=dict(zip(
                    [spec.model.species_ids[i] for i in ions], residual[-1].tolist(), strict=True)),
                counters_equal_at_every_row=bool(np.array_equal(collected, supplied)))


def dilution_data():
    data = json.loads(Path(__file__).with_name("data").joinpath("vloemans2024_dilution.json").read_text())
    rows = []
    for case in data["single_exchange"] + data["repeated_exchange"]:
        f, measured = case["fraction"], case["measured"]
        prediction = [measured[0] * (1 - f) ** i for i in range(len(measured))]
        rows.append(dict(fraction=f, measured=measured, predicted=prediction))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("all", "ion-counters", "dilution"), default="all")
    args = parser.parse_args()
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    report = {}
    if args.case in ("all", "dilution"):
        report.update(compiled_events=[exchanges(fs) for fs in ([0.5, 0.25], [0.8] * 3, [0.9] * 3, [1.0])],
                      whole_wash_runs=[whole_wash(e) for e in (1, 50, 60)],
                      fluorescein_ug_per_mL=dilution_data())
    if args.case in ("all", "ion-counters"):
        report["ion_counters"] = [ion_counters(f) for f in (1 / 2, 3 / 7)]
    print(json.dumps(report, indent=2, allow_nan=False))
    ok = all(row["run_completed"] and row["counters_equal_at_every_row"] for row in report.get("ion_counters", []))
    raise SystemExit(int(not ok))
