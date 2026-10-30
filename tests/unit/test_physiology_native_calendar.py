"""Source dispatch, rational elapsed-time checks and non-rebased resume inputs."""

import json
import math
import os
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_native_calendar as clock
from validation.perturbations import permeability_schedule_native as native_pulse
from validation.perturbations import physiology_calendar_native as native
from validation.perturbations import physiology_calendar_reference as reference

CASES = (
    (0, 0.125, 1.0),
    (1, 0.125, 1.0),
    (2, 0.125, 1.0),
    (3, 0.1, 1.0),
    (7, 0.1, 2.5),
    (17, 2.0**-20, 3.75),
    (257, 1e-12, 10.0),
    (19, 0.2, float(np.nextafter(2.0, 0.0))),
    (5, float(np.nextafter(0.0, 1.0)), 1.0),
)


def evidence(name, payload):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "calendar"
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / (name + ".json")).open("x") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")


def build(count=7, dt=0.1, stride=2.5, phase="SIM"):
    return clock.bind(
        phase=phase,
        step_count=count,
        dt_s=dt,
        sample_stride=stride,
        provenance="Explicit synthetic phase calendar for pinned-source comparison",
    )


@pytest.mark.parametrize("phase", ("INIT", "SIM"))
@pytest.mark.parametrize("count,dt,stride", CASES)
def test_source_calendar_guards_and_independent_rational_boundaries(count, dt, stride, phase):
    calendar = build(count, dt, stride, phase)
    saved = clock.record(calendar)
    actual = clock.window(calendar)
    expected = reference.evaluate(saved)
    fractions = []
    for index, (observed, wanted) in enumerate(
        zip(actual.event_label_s, expected["event_label_s"], strict=True)
    ):
        assert clock.event_label_s(calendar, index) == observed
        # Four binary64 ULPs cover span/division/product rounding; no physical
        # tolerance or absolute floor is used to hide a clock mismatch.
        limit = 4 * math.ulp(wanted)
        error = abs(float(observed) - wanted)
        assert error <= limit, (index, observed, wanted, limit)
        fractions.append(error / limit)
    with pytest.raises(ValueError, match="no remaining"):
        clock.event_label_s(calendar, count)
    for name in actual._fields:
        if name != "event_label_s":
            np.testing.assert_array_equal(getattr(actual, name), expected[name])
    source = {}
    for solver in ("normal", "fast"):
        wanted = native.evaluate(saved, solver=solver)
        np.testing.assert_array_equal(actual.event_label_s, wanted["event_label_s"])
        np.testing.assert_array_equal(actual.sampled, wanted["sampled"])
        np.testing.assert_array_equal(
            actual.event_label_s[actual.events_enabled], wanted["event_call_labels_s"]
        )
        source[solver] = wanted
    assert all(not value.flags.writeable for value in actual)
    evidence(
        f"calendar-{phase}-{count}",
        dict(
            parameters=saved,
            actual={name: value.tolist() for name, value in actual._asdict().items()},
            reference=expected,
            native=source,
            label_error_budget_ulps=4,
            maximum_reference_error_fraction=max(fractions, default=0.0),
            full_native_evolution=False,
        ),
    )


@pytest.mark.parametrize("duration,dt", ((0.3, 0.1), (0.7, 0.1), (1.0, 0.125), (0.01, 1.0)))
def test_requested_duration_retains_pinned_binary64_truncation(duration, dt):
    calendar = clock.from_duration(
        phase="SIM", requested_duration_s=duration, dt_s=dt, provenance="Duration truncation"
    )
    saved = clock.record(calendar)
    source = native.evaluate(saved, solver="normal")
    independent = reference.evaluate(saved)
    assert source["configured_counts"] == dict(INIT=calendar.step_count, SIM=calendar.step_count)
    assert independent["requested_duration_count"] == calendar.step_count
    if duration == 0.3:
        assert calendar.step_count == 2
    evidence(
        "duration-" + str(duration),
        dict(parameters=saved, native=source, reference=independent),
    )


def test_resume_preserves_original_phase_and_does_not_recreate_remaining_calendar():
    calendar = build()
    full = clock.window(calendar)
    for split in range(calendar.step_count + 1):
        saved = json.loads(json.dumps(clock.record(calendar)))
        restored = clock.restore(saved, expected_identity=calendar.identity)
        tail = clock.window(restored, start=split)
        for original, resumed in zip(full, tail, strict=True):
            np.testing.assert_array_equal(resumed, original[split:])
            with pytest.raises(ValueError):
                resumed.setflags(write=True)
    remaining = build(count=calendar.step_count - 2)
    assert remaining.identity != calendar.identity
    assert (
        clock.window(calendar, start=2).event_label_s[0]
        != clock.window(remaining).event_label_s[0]
    )
    with pytest.raises(ValueError, match="original phase"):
        clock.restore(clock.record(remaining), expected_identity=calendar.identity)


@pytest.mark.parametrize(
    "values",
    (
        dict(phase="SEED"),
        dict(step_count=True),
        dict(step_count=1.5),
        dict(step_count=-1),
        dict(step_count=clock.MAX_PHASE_CALLS + 1),
        dict(dt_s=0.0),
        dict(dt_s=-1.0),
        dict(dt_s=math.inf),
        dict(dt_s=math.nan),
        dict(dt_s=True),
        dict(dt_s=1e308),
        dict(sample_stride=0.5),
        dict(sample_stride=math.inf),
        dict(provenance=""),
        dict(requested_duration_s=1.0),
    ),
)
def test_refuses_ambiguous_nonterminating_or_unrepresentable_inputs(values):
    inputs = dict(phase="SIM", step_count=7, dt_s=0.1, sample_stride=1.0, provenance="Declared")
    with pytest.raises(ValueError):
        clock.bind(**(inputs | values))


@pytest.mark.parametrize("defect", ("seal", "phase", "clock", "missing", "extra", "source"))
def test_saved_calendar_cannot_change_original_phase(defect):
    calendar = build()
    saved = clock.record(calendar)
    if defect == "seal":
        saved["identity"] = "0" * 64
    elif defect == "phase":
        saved = clock.record(build(phase="INIT"))
    elif defect == "clock":
        saved = clock.record(build(dt=0.2))
    elif defect == "missing":
        saved.pop("dt_s")
    elif defect == "extra":
        saved["origin"] = 3
    else:
        saved["native_revision"] = "unknown"
    with pytest.raises(ValueError):
        clock.restore(saved, expected_identity=calendar.identity)
    with pytest.raises(ValueError):
        clock.window(replace(calendar, step_count=4))


@pytest.mark.parametrize(
    "bounds", (dict(start=-1), dict(start=8), dict(stop=8), dict(start=5, stop=2))
)
def test_window_cannot_escape_original_phase(bounds):
    with pytest.raises(ValueError):
        clock.window(build(), **bounds)


def test_labels_are_not_update_durations_or_accepted_observation_times():
    single = clock.window(build(count=1, dt=0.125, stride=1))
    np.testing.assert_array_equal(single.event_label_s, [0.0])
    np.testing.assert_array_equal(single.elapsed_end_s, [0.125])
    assert not single.sampled.any()
    full = clock.window(build(count=3, dt=0.1, stride=1))
    np.testing.assert_array_equal(full.duration_s, [0.1, 0.1, 0.1])
    assert np.all(np.diff(full.event_label_s) != 0.1)
    assert full.event_label_s[-1] == full.elapsed_end_s[-1]
    assert full.event_label_s[1] != full.elapsed_end_s[1]
    assert not full.sampled[0] and full.sampled[-1]


def test_clock_choice_changes_actual_native_pulse_even_with_equal_call_durations():
    calendar = build(count=3, dt=0.1, stride=1)
    arrays = clock.window(calendar)
    source = native_pulse.capture()["pulse"]
    on, off, width = 0.12, 0.24, 0.02
    native_values = source(arrays.event_label_s, on, off, width)
    elapsed_values = source(arrays.elapsed_start_s, on, off, width)
    expected = []
    with localcontext() as context:
        context.prec = 100
        for label in arrays.event_label_s:
            t = Decimal.from_float(float(label))
            gain = Decimal(10) / Decimal.from_float(width)
            a = 1 / (1 + (-gain * (t - Decimal.from_float(on))).exp())
            b = 1 / (1 + (-gain * (t - Decimal.from_float(off))).exp())
            expected.append(float(a - b))
    np.testing.assert_allclose(native_values, expected, rtol=3e-14, atol=3e-16)
    assert native_values[1] > 0.99 and elapsed_values[1] < 0.001
    assert native_values[2] < 0.001 and elapsed_values[2] > 0.99
    evidence(
        "pulse-clock-witness",
        dict(
            parameters=clock.record(calendar),
            pulse=dict(on_s=on, off_s=off, change_s=width),
            native_labels=arrays.event_label_s.tolist(),
            elapsed_starts=arrays.elapsed_start_s.tolist(),
            native_pulse=native_values.tolist(),
            elapsed_pulse=elapsed_values.tolist(),
            decimal_reference=expected,
            scope="Source pulse at two explicitly different clocks; no evolved tissue trajectory",
        ),
    )
