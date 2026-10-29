"""One scalar executable retains real clocks and never evaluates padded biology."""

import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import runner
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, iter_windows, plan_windows
from tests.batch_fixtures import MODELS, short_spec
from tests.unit.test_windows import assert_windows


class Lowerings:
    def __init__(self, original):
        self.original = original
        self.widths = []

    def lower(self, *args):
        self.widths.append(int(args[1].shape[0]))
        return self.original.lower(*args)


@pytest.mark.parametrize("name", MODELS)
def test_short_tail_reuses_one_executable_with_exact_complete_history(name, monkeypatch):
    spec = short_spec(name, 0.073)
    full = run(spec)
    count = len(full.times) - 1
    width = 2 if count % 2 else count - 1
    assert count > width and count % width
    lowerings = Lowerings(runner._compiled_window_rollout)
    monkeypatch.setattr(runner, "_compiled_window_rollout", lowerings)
    parts = list(iter_windows(spec, WindowPolicy(width)))
    assert lowerings.widths == [width]
    assert_windows(parts, full)
    assert len(parts[-1].times) - 1 == count % width
    assert sum(len(part.times) - 1 for part in parts) == count
    assert parts[-1].final.time == spec.experiment.end_time
    assert parts[-1].timings["compile_or_cache_seconds"] == 0


@pytest.mark.parametrize("mode", ["rk4", "checked_rk4", "discrete"])
def test_padding_never_evaluates_rhs_or_checked_step_with_poisoned_inputs(mode):
    calls = []

    def record(value):
        calls.append(float(value))

    def rhs(state, control, parameters, active):
        jax.debug.callback(record, control, ordered=True)
        return jnp.full_like(state, control)

    def domain(state, parameters, active):
        return jnp.all(jnp.isfinite(state))

    def discrete(state, dt, control, parameters, active):
        jax.debug.callback(record, control, ordered=True)
        updated = state + dt * control
        return updated, jnp.all(jnp.isfinite(updated))

    args = (
        jnp.asarray([1.0]),
        jnp.asarray([0.1, 0.1, np.nan, np.nan]),
        jnp.asarray([1.0, 2.0, np.nan, np.nan]),
        jnp.asarray(0.0),
        jnp.asarray([True]),
        jnp.asarray([True, True, False, False]),
    )
    compiled = runner._compiled_window_rollout.lower(
        *args,
        rhs,
        domain if mode == "checked_rk4" else None,
        discrete if mode == "discrete" else None,
    ).compile()
    final, history, valid = compiled(*args)
    jax.block_until_ready((final, history, valid))
    jax.effects_barrier()
    assert calls == ([1.0, 2.0] if mode == "discrete" else [1.0] * 4 + [2.0] * 4)
    np.testing.assert_allclose(final, [1.3], atol=1e-15, rtol=0)
    np.testing.assert_array_equal(history[1:], np.broadcast_to(history[1], (3, 1)))
    np.testing.assert_array_equal(valid, [True] * 4)


@pytest.mark.parametrize("mode", ["checked_rk4", "discrete"])
def test_failed_real_step_stops_following_model_evaluations(mode):
    calls = []

    def record(value):
        calls.append(float(value))

    def rhs(state, control, parameters, active):
        jax.debug.callback(record, control, ordered=True)
        return jnp.full_like(state, control)

    def domain(state, parameters, active):
        return jnp.all(jnp.isfinite(state) & (state <= 1.15))

    def discrete(state, dt, control, parameters, active):
        jax.debug.callback(record, control, ordered=True)
        updated = state + dt * control
        valid = domain(updated, parameters, active)
        return jnp.where(valid, updated, state), valid

    args = (
        jnp.asarray([1.0]),
        jnp.full(4, 0.1),
        jnp.asarray([1.0, 2.0, 999.0, np.nan]),
        jnp.asarray(0.0),
        jnp.asarray([True]),
        jnp.asarray([True, True, True, False]),
    )
    compiled = runner._compiled_window_rollout.lower(
        *args,
        rhs,
        domain if mode == "checked_rk4" else None,
        discrete if mode == "discrete" else None,
    ).compile()
    final, history, valid = compiled(*args)
    jax.block_until_ready((final, history, valid))
    jax.effects_barrier()
    assert calls and all(value in (1.0, 2.0) for value in calls)
    np.testing.assert_array_equal(valid, [True, False, False, False])
    np.testing.assert_array_equal(final, history[0])


def test_single_step_restart_uses_only_its_remaining_width_and_terminal_never_compiles(monkeypatch):
    spec = short_spec("single_cell_pulse", 0.073)
    full = run(spec)
    point = full.checkpoint_at(float(full.times[-2]))
    lowerings = Lowerings(runner._compiled_window_rollout)
    monkeypatch.setattr(runner, "_compiled_window_rollout", lowerings)
    plan = plan_windows(spec, WindowPolicy(4096), point)
    parts = list(iter_windows(spec, plan.policy, point))
    assert lowerings.widths == [1]
    assert_windows(parts, run(spec, point))
    terminal = list(iter_windows(spec, plan.policy, full.final))
    assert lowerings.widths == [1]
    assert_windows(terminal, run(spec, full.final))


@pytest.mark.parametrize("kind", ["guarded_physical", "native_discrete"])
def test_complete_physical_state_and_native_step_tail(kind, monkeypatch, tmp_path):
    """Execution equivalence at five real steps, not a new biological qualification."""
    if kind == "guarded_physical":
        from validation.tissue.surface_dynamics_fixtures import definition

        raw = definition("open")
    else:
        path = Path(__file__).resolve().parents[2] / "configs/betse_spatial_active.json"
        raw = json.loads(path.read_text())
    raw["execution"]["backend"] = "cpu"
    dt = raw["execution"]["dt"]
    raw["experiment"]["end_time"] = 5 * dt
    raw["experiment"]["observation_times"] = [0.0, 2 * dt, 5 * dt]
    spec = parse_spec(raw)
    full = run(spec)
    assert len(full.times) == 6
    lowerings = Lowerings(runner._compiled_window_rollout)
    monkeypatch.setattr(runner, "_compiled_window_rollout", lowerings)
    parts = list(iter_windows(spec, WindowPolicy(3)))
    assert lowerings.widths == [3]
    assert [len(part.times) - 1 for part in parts] == [3, 2]
    # Save all arrays before comparison, including any failed equivalence.
    arrays = {"times": full.times}
    for name, values in zip(full.history._fields, full.history, strict=True):
        arrays["ordinary__" + name] = values
        arrays["windowed__" + name] = np.concatenate(
            [getattr(part.history, name)[0 if i == 0 else 1 :] for i, part in enumerate(parts)]
        )
    for name, values in vars(full.observations).items():
        arrays["ordinary_observed__" + name] = values
        arrays["windowed_observed__" + name] = np.concatenate(
            [getattr(part.observations, name) for part in parts]
        )
    (tmp_path / "definition.json").write_text(json.dumps(spec.to_dict(), indent=2) + "\n")
    np.savez(tmp_path / "complete-arrays.npz", **arrays)
    assert_windows(parts, full)
    assert parts[-1].final.event_index == full.final.event_index
    assert parts[-1].timings["compile_or_cache_seconds"] == 0
