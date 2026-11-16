"""The vector path's seams for packed planners (docs/WINDOW_DEVICE_CHECKS_DESIGN.md §5).

- window_arguments gives a cohort's first window as the program receives it: abstractly (no
  device placement) with the same compile key as the real launch, whose executable a probe
  compiled from the abstract arguments serves.
- Every refusal of one world carries its WorldRefusal as exc.refusal; the exception's class and
  message are unchanged (admission and start here; step, check and observation refusals in
  test_vector_window_world_mode.py).
- max_working_bytes refusals are MemoryRefusal, a ConfigError with the same messages.
- Carried refusals (refusals="world") are checked before planning.
"""

from dataclasses import replace

import jax
import pytest

from cells.core import vector_windows
from cells.core.batch import (
    BatchSpec,
    MemoryRefusal,
    WorldRefusal,
    checkpoint_batch_limits,
    plan_batch,
)
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.specs import ConfigError
from cells.core.vector_windows import (
    compile_window,
    iter_vector_windows,
    plan_vector_windows,
    run_vector_windowed,
    window_arguments,
    window_key,
)
from tests.unit.test_vector_windows import POLICY, cohort, definition


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_window_arguments_share_the_launch_key_and_executable():
    spec = cohort([definition(), definition(scale=1.1)])
    plan = plan_vector_windows(spec, POLICY)
    abstract = window_arguments(plan, abstract=True)
    real = window_arguments(plan)
    assert all(isinstance(v, jax.ShapeDtypeStruct) for v in jax.tree.leaves(abstract.args))
    assert all(isinstance(v, jax.Array) for v in jax.tree.leaves(real.args))
    assert abstract.rows == real.rows == plan.observation_rows
    assert set(abstract.starts) == {1, 2}
    key = window_key(abstract.model, abstract.args, abstract.rows)
    assert key == window_key(real.model, real.args, real.rows)
    vector_windows._EXECUTABLES.clear()
    _, seconds, _ = compile_window(abstract.model, abstract.args, abstract.rows)
    assert seconds > 0
    result = run_vector_windowed(spec, POLICY)  # The probe's executable serves the run.
    assert result.timings["compile_seconds"] == 0.0


def test_carried_refusals_are_checked():
    spec = cohort([definition(), definition(scale=1.1)])
    record = WorldRefusal(2, "check", "WorldCheckError", "World 2: planted")
    with pytest.raises(ConfigError, match="require"):
        iter_vector_windows(spec, POLICY, refused={2: record})
    with pytest.raises(ConfigError, match="WorldRefusal"):
        iter_vector_windows(spec, POLICY, refusals="world", refused={3: record})
    with pytest.raises(ConfigError, match="batch or world"):
        run_vector_windowed(spec, POLICY, refusals="worlds")


def test_admission_and_start_refusals_carry_their_world(monkeypatch):
    spec = cohort([definition(), definition(scale=1.1)])
    starts = dict(next(iter_vector_windows(spec, POLICY)).checkpoints)
    starts[2] = replace(starts[2], step_index=starts[2].step_index + 1)
    with pytest.raises(ConfigError) as caught:
        plan_vector_windows(spec, POLICY, starts)
    record = caught.value.refusal
    assert (record.world_id, record.stage, record.error) == (2, "admission", "ConfigError")
    assert record.message == str(caught.value) and record.message.startswith("World 2: ")
    plan = plan_vector_windows(spec, POLICY)

    def refuse(*args, **kwargs):
        raise NumericalError("planted start refusal")

    monkeypatch.setattr(vector_windows, "validate_checkpoint", refuse)
    with pytest.raises(NumericalError) as caught:
        window_arguments(plan)
    record = caught.value.refusal
    assert (record.world_id, record.stage, record.error) == (1, "start", "NumericalError")
    assert str(caught.value) == record.message == "World 1: planted start refusal"


def test_memory_refusals_are_typed_with_unchanged_messages(monkeypatch):
    spec = cohort([definition(), definition(scale=1.1)])
    small = replace(spec, max_working_bytes=1)
    with pytest.raises(MemoryRefusal, match="^Checkpoint aggregate arrays exceed batch") as caught:
        plan_vector_windows(small, POLICY)
    assert isinstance(caught.value, ConfigError) and caught.value.stage == "checkpoints"
    assert caught.value.required_bytes > caught.value.limit_bytes == 1
    assert not hasattr(caught.value, "refusal")  # The batch's size, never a world's refusal.
    storage = 2 * sum(trace_bytes(w.simulation, 0, 0) for w in spec.worlds)
    estimate = plan_vector_windows(spec, POLICY).estimated_working_bytes
    assert storage < estimate
    with pytest.raises(MemoryRefusal, match="^Estimated vectorized rows exceed batch") as caught:
        plan_vector_windows(replace(spec, max_working_bytes=storage), POLICY)
    assert caught.value.stage == "estimate" and caught.value.required_bytes == estimate

    real = vector_windows.compile_window

    def inflated(model, args, rows):
        compiled, seconds, memory = real(model, args, rows)
        sizes = {"argument_size_in_bytes": 0, "output_size_in_bytes": 0, **(memory or {})}
        return compiled, seconds, sizes | {"temp_size_in_bytes": 2**52}

    monkeypatch.setattr(vector_windows, "compile_window", inflated)
    with pytest.raises(MemoryRefusal, match="^Compiled vectorized window needs") as caught:
        run_vector_windowed(spec, POLICY)
    assert caught.value.stage == "compiled" and caught.value.required_bytes > 2**52
    # The guarded batch path's max_working_bytes refusals are MemoryRefusal too.
    guarded = BatchSpec(spec.worlds, 2, 10**6, 1)
    with pytest.raises(MemoryRefusal, match="^Checkpoint aggregate arrays exceed batch"):
        checkpoint_batch_limits(guarded)
    with pytest.raises(MemoryRefusal, match="^Estimated aggregate arrays exceed batch"):
        plan_batch(guarded)
