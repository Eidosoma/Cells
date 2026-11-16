"""refusals="world" on the vector path: observation refusals and replicas (§5.5).

A world refused by its host observations has already run the next window, whose outputs for it
are discarded; it is masked from the window after, and the other worlds run as without it. A
carried refusal masks one replica in a group of identical worlds while the group goes on. (Split
from test_vector_window_world_mode.py to keep each file under the tier cap.)
"""

import jax
import numpy as np
import pytest

from cells.core.batch import WorldRefusal
from cells.core.specs import ConfigError
from cells.core.vector_windows import plan_vector_windows, run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.models import surface_pump
from tests.unit.test_vector_windows import cohort, definition

SUFFIX = "; vectorized batch refused"
SHORT = WindowPolicy(2, "checkpoints")


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def same_state(a, b):
    return all(np.array_equal(np.asarray(x), np.asarray(y)) for x, y in zip(a, b, strict=True))


def test_an_observation_refusal_drops_the_next_window_and_masks_the_world_after(monkeypatch):
    policy = SHORT
    spec = cohort([definition(), definition(scale=1.1), definition(scale=1.2)])
    target, at = spec.worlds[2].simulation.fingerprint, 0.0007
    original = surface_pump.observe_history

    def observe(times, history, layout, requested, simulation):
        if simulation.fingerprint == target and at in list(requested):
            raise ConfigError("planted observation refusal")
        return original(times, history, layout, requested, simulation)

    reference = run_vector_windowed(spec, policy)
    monkeypatch.setattr(surface_pump, "observe_history", observe)
    windows = []
    result = run_vector_windowed(spec, policy, refusals="world", sink=windows.append)
    assert set(result.refusals) == {3} and set(result.worlds) == {1, 2}
    record = result.refusals[3]
    assert (record.stage, record.error) == ("observation", "ConfigError")
    assert record.message == "World 3: planted observation refusal"
    k = next(i for i, w in enumerate(windows) if 3 in w.refusals)
    assert record.checkpoint.step_index == windows[k - 1].checkpoints[3].step_index
    assert len(windows) >= k + 3, "the test needs a window after the dropped one"
    for window in windows[k:]:
        assert 3 not in window.diagnostics and 3 not in window.observations
        assert window.checkpoints[3].step_index == record.checkpoint.step_index
    # Window k + 1 ran it (launched before window k's observations); from k + 2 it is masked.
    steps = [w.resources["executed_world_steps"] for w in windows]
    assert steps[k + 2] < steps[k + 1]
    for identity in (1, 2):
        assert same_state(
            result.worlds[identity].final.state, reference.worlds[identity].final.state
        )
    with pytest.raises(ConfigError) as caught:  # Batch mode: today's refusal, with a record.
        run_vector_windowed(spec, policy)
    assert str(caught.value) == caught.value.refusal.message + SUFFIX
    assert caught.value.refusal.world_id == 3


def test_a_carried_refusal_masks_one_replica_while_its_group_goes_on():
    shared = definition()
    spec = cohort([shared, shared, definition(scale=1.2)])  # Worlds 1 and 2: one group.
    assert plan_vector_windows(spec, SHORT).groups[0] == (0, 1)
    record = WorldRefusal(2, "check", "WorldCheckError", "World 2: carried")
    windows, seen = [], []
    result = run_vector_windowed(
        spec, SHORT, refusals="world", refused={2: record}, sink=windows.append
    )
    reference = run_vector_windowed(spec, SHORT, sink=seen.append)
    assert reference.timings["compile_seconds"] == 0.0  # The same executable.
    assert set(result.worlds) == {1, 3} and dict(result.refusals) == {2: record}
    for identity in (1, 3):
        assert same_state(
            result.worlds[identity].final.state, reference.worlds[identity].final.state
        )
    start = reference.worlds[2].start_step
    for mine, theirs in zip(windows, seen, strict=True):
        assert 2 not in mine.diagnostics and 2 not in mine.observations
        assert mine.checkpoints[2].step_index == start
        assert (
            3 * mine.resources["executed_world_steps"]
            == 2 * theirs.resources["executed_world_steps"]
        )
