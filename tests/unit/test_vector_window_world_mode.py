"""refusals="world" on the vector path (docs/WINDOW_DEVICE_CHECKS_DESIGN.md §5.5): failed checks.

A failing world is refused alone: the other worlds continue on the same executable at the same
world count, bitwise as in a cohort where nothing is refused, and the refused world's last
accepted state is its checkpoint at the start of its refusing window (window granularity). Its
record (exc.refusal in batch mode, the result's refusals in world mode) has the same fields and
reason in both modes. Two worlds failing in one window are each refused alone. A carried refusal
keeps a resumed world masked. The refused-step kind is test_vector_window_world_mode_step.py;
observation refusals and replicas are test_vector_window_world_mode_observations.py (split to
keep each file under the tier cap).
"""

import jax
import numpy as np
import pytest

from cells.core.batch import WorldRefusal
from cells.core.vector_windows import WorldCheckError, run_vector_windowed
from cells.models import surface_pump
from tests.unit.test_vector_windows import POLICY, cohort, corrupted_step, definition

SUFFIX = "; vectorized batch refused"
# One function object per kind, so every cohort of one shape reuses one executable.
STEPS = {kind: corrupted_step(kind) for kind in ("ledger", "refuse")}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def same_state(a, b):
    return all(np.array_equal(np.asarray(x), np.asarray(y)) for x, y in zip(a, b, strict=True))


def failing_cohort(second, third=None):
    """The injected-failure cohort of test_vector_windows: a world refuses with availability 0.5
    after the change (corrupted_step) and runs on with any other value (a value twin)."""
    last = definition(arm="clamped", scale=1.1)
    if third is not None:
        last = definition(arm="clamped", scale=1.1, change=dict(availability=third))
    return cohort(
        [
            definition(arm="clamped"),
            definition(arm="clamped", change=dict(availability=second)),
            last,
        ]
    )


def assert_same_record(a, b):
    for name in ("world_id", "stage", "error", "message", "step_index", "time_interval", "checks"):
        assert getattr(a, name) == getattr(b, name), name
    assert a.checkpoint.step_index == b.checkpoint.step_index
    assert a.checkpoint.time == b.checkpoint.time
    assert same_state(a.checkpoint.state, b.checkpoint.state)


def refuses_one_world_and_the_others_run_as_unrefused(kind, monkeypatch):
    """A world refused alone (kind "ledger": a failed device check; "refuse": a refused step):
    its record is batch mode's, and the other worlds run bitwise as in a cohort where nothing
    is refused, on the same executable."""
    monkeypatch.setattr(surface_pump, "checked_step", STEPS[kind])
    refusing, twin = failing_cohort(0.5), failing_cohort(0.6)

    with pytest.raises(WorldCheckError) as caught:  # Batch mode: today's refusal, with a record.
        run_vector_windowed(refusing, POLICY)
    error, batch = caught.value, caught.value.refusal
    assert type(batch) is WorldRefusal and str(error) == batch.message + SUFFIX
    assert batch.world_id == error.world_id == 2
    assert batch.stage == ("step" if kind == "refuse" else "check")
    assert batch.error == "WorldCheckError" and batch.checks == error.checks
    assert (batch.step_index, batch.time_interval) == (error.step_index, error.time_interval)

    windows = []
    alone = run_vector_windowed(refusing, POLICY, refusals="world", sink=windows.append)
    assert set(alone.refusals) == {2} and set(alone.worlds) == {1, 3}
    assert_same_record(alone.refusals[2], batch)
    start = alone.refusals[2].checkpoint  # Window granularity: its refusing window's start.
    assert start.step_index < batch.step_index <= start.step_index + POLICY.window_steps

    seen = []
    unrefused = run_vector_windowed(twin, POLICY, sink=seen.append)
    assert unrefused.timings["compile_seconds"] == 0.0  # The same executable.
    assert not unrefused.refusals
    for identity in (1, 3):  # Bitwise as if nothing were refused.
        mine, theirs = alone.worlds[identity], unrefused.worlds[identity]
        assert mine.final.step_index == theirs.final.step_index
        assert same_state(mine.final.state, theirs.final.state)
        assert mine.diagnostics == theirs.diagnostics
        for a, b in zip(windows, seen, strict=True):
            if identity in b.observations:
                for x, y in zip(
                    vars(a.observations[identity]).values(),
                    vars(b.observations[identity]).values(),
                    strict=True,
                ):
                    np.testing.assert_array_equal(x, y)
    # Its last accepted checkpoint is the twin's at that window start (the same history so far).
    before = next(w for w in seen if w.checkpoints[2].step_index == start.step_index)
    assert same_state(start.state, before.checkpoints[2].state)
    for window in windows:
        if 2 in window.refusals:
            assert 2 not in window.diagnostics and 2 not in window.observations
            assert window.checkpoints[2].step_index == start.step_index
    if kind == "ledger":  # Carried refusals keep it masked across a resume.
        refused_at = next(w for w in windows if 2 in w.refusals)
        if refused_at is not windows[-1]:
            resumed = run_vector_windowed(
                refusing,
                POLICY,
                checkpoints=dict(refused_at.checkpoints),
                refusals="world",
                refused=dict(refused_at.refusals),
            )
            assert set(resumed.refusals) == {2} and set(resumed.worlds) == {1, 3}
            for identity in (1, 3):
                assert same_state(
                    resumed.worlds[identity].final.state, alone.worlds[identity].final.state
                )


def test_a_failed_check_refuses_one_world_and_the_others_run_as_unrefused(monkeypatch):
    refuses_one_world_and_the_others_run_as_unrefused("ledger", monkeypatch)


def test_two_worlds_failing_in_one_window_are_each_refused_alone(monkeypatch):
    monkeypatch.setattr(surface_pump, "checked_step", STEPS["ledger"])
    both, twin = failing_cohort(0.5, 0.5), failing_cohort(0.6, 0.6)
    with pytest.raises(WorldCheckError) as caught:
        run_vector_windowed(both, POLICY)
    assert caught.value.world_id == 2
    assert str(caught.value).endswith(SUFFIX + " (1 more failing worlds)")
    result = run_vector_windowed(both, POLICY, refusals="world")
    assert set(result.refusals) == {2, 3} and set(result.worlds) == {1}
    for identity in (2, 3):
        record = result.refusals[identity]
        assert (record.world_id, record.stage, record.error) == (
            identity,
            "check",
            "WorldCheckError",
        )
        assert record.message.startswith(f"World {identity}: ")
        assert (record.step_index, record.time_interval) == (
            caught.value.step_index,
            caught.value.time_interval,
        )
    assert result.refusals[2].message == caught.value.refusal.message
    unrefused = run_vector_windowed(twin, POLICY)
    assert unrefused.timings["compile_seconds"] == 0.0  # The same executable.
    assert same_state(result.worlds[1].final.state, unrefused.worlds[1].final.state)
