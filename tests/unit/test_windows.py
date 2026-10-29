"""Windowing is storage partitioning, not different physics or a different clock."""

import json
from dataclasses import replace

import numpy as np
import pytest

from cells.core import runner, windows
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows, plan_windows, run_windowed
from cells.io import _sha256, load_snapshot
from cells.models.registry import get_model
from cells.window_io import write_windowed_run
from tests.batch_fixtures import MODELS, short_spec, synthetic_pair


def assert_windows(parts, full):
    for name, values in zip(full.history._fields, full.history, strict=True):
        np.testing.assert_array_equal(
            np.concatenate(
                [getattr(w.history, name)[0 if i == 0 else 1 :] for i, w in enumerate(parts)]
            ),
            values,
        )
    np.testing.assert_array_equal(
        np.concatenate([w.times[0 if i == 0 else 1 :] for i, w in enumerate(parts)]), full.times
    )
    for name, value in vars(full.observations).items():
        np.testing.assert_array_equal(
            np.concatenate([getattr(w.observations, name) for w in parts]), value
        )
    assert parts[-1].final.step_index == full.final.step_index
    for a, b in zip(parts[-1].final.state, full.final.state, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("name", MODELS)
@pytest.mark.parametrize("width", [1, 7, 1000])
def test_seven_models_exact_full_parity_and_read_only(name, width):
    spec = short_spec(name, 0.123)
    full = run(spec)
    parts = list(iter_windows(spec, WindowPolicy(width)))
    assert_windows(parts, full)
    assert len(parts) == plan_windows(spec, WindowPolicy(width)).window_count
    aggregate = {}
    for part in parts:
        assert len(part.times) <= width + 1
        for a in (*part.history, part.times, *vars(part.observations).values()):
            assert not a.flags.writeable
        windows.merge_diagnostics(aggregate, part.diagnostics)
    assert aggregate == full.diagnostics


@pytest.mark.parametrize("name", MODELS)
def test_eager_windows_exact_parity(name):
    spec = short_spec(name, 0.0073, jit=False)
    assert_windows(list(iter_windows(spec, WindowPolicy(1))), run(spec))


@pytest.mark.parametrize("name", MODELS)
def test_complete_resume_can_change_window_and_recording_policy(name, tmp_path):
    spec = short_spec(name, 0.073)
    full = run(spec)
    boundary = float(full.times[len(full.times) // 2])
    root = tmp_path / "original"
    write_windowed_run(root, spec, WindowPolicy(7, "checkpoints"), checkpoint_times=[boundary])
    step = full.checkpoint_at(boundary).step_index
    saved = load_snapshot(root / f"snapshots/step-{step:010d}")
    suffix = run(spec, saved.checkpoint)
    parts = list(iter_windows(saved.spec, WindowPolicy(2, "full"), saved.checkpoint))
    assert_windows(parts, suffix)
    zero = list(iter_windows(spec, WindowPolicy(2), full.final))
    assert len(zero) == len(zero[0].times) == 1
    assert_windows(zero, run(spec, full.final))


@pytest.mark.parametrize("name", MODELS)
@pytest.mark.parametrize("remaining", [0, 1])
@pytest.mark.parametrize("width", [1, 7])
def test_late_restart_preflight_checks_the_complete_clock_in_bounded_chunks(
    monkeypatch, name, remaining, width
):
    import jax

    from cells.core.schedule import control_values

    spec = short_spec(name, 0.073)
    full = run(spec)
    point = full.checkpoint_at(float(full.times[-1 - remaining]))
    model = get_model(spec.model)
    original = model.check_steps
    checked = []

    def check(definition, steps, controls):
        original(definition, steps, controls)
        checked.append((steps.copy(), jax.tree.map(np.copy, controls)))

    monkeypatch.setattr(model, "check_steps", check)
    plan = plan_windows(spec, WindowPolicy(width), point)
    assert plan.start_step == point.step_index
    assert plan.window_count == 1
    # These short complete clocks fit one storage-capped validation chunk.
    # Tiny execution windows must not repeat whole-model admission per step.
    assert len(checked) == 1
    np.testing.assert_array_equal(np.concatenate([s for s, _ in checked]), np.diff(full.times))
    actual_controls = jax.tree.map(
        lambda *arrays: np.concatenate(arrays), *(controls for _, controls in checked)
    )
    for actual, expected in zip(
        jax.tree.leaves(actual_controls),
        jax.tree.leaves(control_values(spec, full.times[:-1])),
        strict=True,
    ):
        np.testing.assert_array_equal(actual, expected)


def test_completed_restart_still_refuses_an_invalid_historical_step(monkeypatch):
    from cells.core.resources import trace_bytes

    raw = synthetic_pair().worlds[0].simulation.to_dict()
    raw["experiment"]["source"]["schedule"].append({"time": 0.5, "rate": 0})
    spec = parse_spec(raw)
    full = run(spec)
    model = get_model(spec.model)
    original = model.check_steps
    calls = []

    def check(definition, steps, controls):
        original(definition, steps, controls)
        calls.append(len(steps))
        if np.any(controls > 0):
            raise ConfigError("Rejected historical control")

    monkeypatch.setattr(model, "check_steps", check)
    # A large requested chunk must still obey the existing storage cap. The
    # terminal checkpoint itself fits; earlier nonzero controls remain checked.
    base = trace_bytes(spec, 0, 0)
    per_step = trace_bytes(spec, 1, 0) - base
    terminal_storage = 2 * trace_bytes(spec, 0, 2) + 2 * base
    spec = replace(
        spec, execution=replace(spec.execution, max_trace_bytes=terminal_storage + per_step)
    )
    with pytest.raises(ConfigError, match="Rejected historical control"):
        plan_windows(spec, WindowPolicy(1000), full.final)
    assert max(calls) <= (spec.execution.max_trace_bytes - base) // per_step


@pytest.mark.parametrize("width", [1, 2, 7, 256])
def test_events_observations_boundaries_and_future_branch(width):
    spec = synthetic_pair().worlds[0].simulation
    data = spec.to_dict()
    data["experiment"]["observation_times"] = [0, 0.071, 0.1, 0.137, 0.2, 0.5, 1]
    spec = parse_spec(data)
    full = run(spec)
    assert_windows(list(iter_windows(spec, WindowPolicy(width))), full)
    checkpoint = full.checkpoint_at(0.5)
    changed = spec.to_dict()
    changed["experiment"]["source"]["schedule"].append({"time": 0.5, "rate": 4})
    changed["experiment"]["end_time"] = 1.37
    changed["experiment"]["observation_times"].append(1.37)
    changed = parse_spec(changed)
    branched = branch_checkpoint(spec, checkpoint, changed)
    assert_windows(
        list(iter_windows(changed, WindowPolicy(width), branched)), run(changed, branched)
    )
    changed = changed.to_dict()
    changed["experiment"]["source"]["schedule"][0]["rate"] = 99
    with pytest.raises(ConfigError, match="rewrite"):
        branch_checkpoint(spec, checkpoint, parse_spec(changed))


@pytest.mark.parametrize(
    "scale", [float.fromhex("0x0.0000000000001p-1022"), 2**-30, 0.03, 0.1, 2.0**400]
)
def test_lazy_grid_exact_float_products_events_and_near_collisions(scale, config_data):
    config_data["model"]["parameters"]["decay_rate"] = 0
    end = 13 * scale
    config_data["execution"]["dt"] = scale
    config_data["experiment"].update(end_time=end, observation_times=[0, end])
    points = sorted(
        {
            0.0,
            2 * scale,
            3.13 * scale,
            np.nextafter(4 * scale, 0),
            np.nextafter(4 * scale, end),
            end,
        }
    )
    config_data["experiment"]["source"]["schedule"] = [
        {"time": float(t), "rate": 0} for t in points
    ]
    spec = parse_spec(config_data)
    old, new = timeline(spec), EventGrid(spec)
    np.testing.assert_array_equal(np.asarray(new), old)
    for index, time in enumerate(old):
        assert new.exact_index(time) == index
    assert new[-1] == end
    with pytest.raises(TypeError):
        new[:2]
    with pytest.raises(IndexError):
        _ = new[len(new)]


def test_large_lazy_grid_has_only_event_sized_metadata(config_data):
    config_data["execution"].update(dt=1, max_steps=2**31 - 1)
    config_data["experiment"].update(end_time=2**31 - 3, observation_times=[0])
    config_data["experiment"]["source"]["schedule"] = [
        {"time": 0, "rate": 0},
        {"time": 0.137, "rate": 1},
    ]
    grid = EventGrid(parse_spec(config_data))
    assert len(grid) == 2**31 - 1
    assert len(grid.extras) == 1
    assert grid.exact_index(2**31 - 3) == len(grid) - 1
    assert grid[1000000] == 999999.0


def test_time_ratio_underflow_preserves_zero_and_end(config_data):
    config_data["execution"]["dt"] = 1e200
    config_data["experiment"].update(end_time=1e-200, observation_times=[0])
    config_data["experiment"]["source"]["schedule"] = [{"time": 0, "rate": 0}]
    spec = parse_spec(config_data)
    np.testing.assert_array_equal(np.asarray(EventGrid(spec)), timeline(spec))
    assert len(EventGrid(spec)) == 2


@pytest.mark.parametrize("name", ["source_pair_controls", "bioelectric_pair_baseline"])
def test_observation_accounting_comparison_spans_windows(monkeypatch, name):
    spec = short_spec(name, 0.004)
    data = spec.to_dict()
    data["execution"]["dt"] = 0.001
    data["experiment"]["observation_times"] = [0.0003, 0.0013, 0.0023, 0.0033]
    spec = parse_spec(data)
    full = run(spec)
    model = get_model(spec.model)
    original = model.check_values
    compared = []

    def check(state, definition):
        if state[0].ndim == 3 and len(state[0]) == 2:
            compared.append(state[0].copy())
        return original(state, definition)

    monkeypatch.setattr(model, "check_values", check)
    run_windowed(spec, WindowPolicy(1))
    values = getattr(full.observations, model.STATE_TYPE._fields[0])
    for i in range(len(values) - 1):
        assert any(np.array_equal(v, values[i : i + 2]) for v in compared)


@pytest.mark.parametrize("recording", ["full", "observations", "checkpoints"])
def test_unrecorded_invalid_numerical_state_is_refused(monkeypatch, recording, tmp_path):
    import jax.numpy as jnp

    spec = synthetic_pair().worlds[0].simulation
    model = get_model(spec.model)
    original = model.rhs

    def invalid(state, control, params, active):
        slope = original(state, control, params, active)
        return type(slope)(
            jnp.where(control > 0, jnp.nan, slope.amount), slope.supplied, slope.degraded
        )

    monkeypatch.setattr(model, "rhs", invalid)
    root = tmp_path / recording
    with pytest.raises(NumericalError, match="Non-finite"):
        write_windowed_run(root, spec, WindowPolicy(2, recording))
    assert not (root / "manifest.json").exists()


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "2", 2**31])
def test_invalid_window_sizes(value):
    with pytest.raises(ConfigError, match="window_steps"):
        WindowPolicy(value)


@pytest.mark.parametrize("value", ["none", "Full", "", None, True, []])
def test_invalid_recording(value):
    with pytest.raises(ConfigError, match="recording"):
        WindowPolicy(recording=value)


def test_peak_observation_count_matches_real_windows_and_continuations():
    spec = synthetic_pair().worlds[0].simulation
    data = spec.to_dict()
    data["experiment"]["observation_times"] = sorted(
        set(timeline(spec).tolist() + [0.013, 0.0131, 0.0132])
    )
    spec = parse_spec(data)
    full = run(spec)
    for width in [1, 2, 3, 11, 100]:
        for cp in [None, full.checkpoint_at(0.137), full.final]:
            plan = plan_windows(spec, WindowPolicy(width), cp)
            parts = list(iter_windows(spec, WindowPolicy(width), cp))
            assert plan.max_observations == max(len(p.observations.times) for p in parts)


def test_small_window_budget_runs_and_restores_when_full_trace_is_refused(monkeypatch, tmp_path):
    data = short_spec("single_cell_pulse", 2).to_dict()
    data["execution"].update(dt=0.001, max_trace_bytes=10000)
    spec = parse_spec(data)
    with pytest.raises(ConfigError, match="trace working storage"):
        run(spec)

    def forbidden(*args, **kwargs):
        raise AssertionError("A full timeline was requested")

    monkeypatch.setattr(runner, "timeline", forbidden)
    first = tmp_path / "first"
    write_windowed_run(first, spec, WindowPolicy(8, "checkpoints"), checkpoint_times=[1.0])
    saved = load_snapshot(first / "snapshots/step-0000001000")
    resumed = run_windowed(spec, WindowPolicy(11), saved.checkpoint)
    final = load_snapshot(first / "checkpoint_final")
    for a, b in zip(final.checkpoint.state, resumed.final.state, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("setting", ["window", "capacity", "observations", "steps"])
def test_resource_refusal_precedes_model_capacity_allocation(monkeypatch, setting):
    data = short_spec("single_cell_pulse", 1).to_dict()
    data["execution"]["max_trace_bytes"] = 5000
    width = 10000 if setting == "window" else 2
    if setting == "window":
        data["execution"]["dt"] = 0.0001
    if setting == "capacity":
        data["execution"]["capacity"] = 1000000
    if setting == "observations":
        data["experiment"]["observation_times"] = np.linspace(0, 0.01, 200).tolist()
    if setting == "steps":
        data["execution"]["max_steps"] = 1
    spec = parse_spec(data)

    def forbidden(*args):
        raise AssertionError("Capacity allocation before resource refusal")

    monkeypatch.setattr(get_model(spec.model), "initial_values", forbidden)
    with pytest.raises(ConfigError, match="max_steps|max_trace_bytes"):
        plan_windows(spec, WindowPolicy(width))


@pytest.mark.parametrize("name", ["source_pair_controls", "bioelectric_pair_baseline"])
@pytest.mark.parametrize("recording", ["full", "observations", "checkpoints"])
def test_all_cubic_intervals_checked_even_when_not_recorded(monkeypatch, name, recording, tmp_path):
    spec = short_spec(name, 0.041)
    data = spec.to_dict()
    data["experiment"]["observation_times"] = [0.0]
    spec = parse_spec(data)
    model = get_model(spec.model)
    original = model.check_interpolants
    intervals = []

    def checked(times, *args):
        intervals.extend(zip(times[:-1], times[1:], strict=True))
        return original(times, *args)

    monkeypatch.setattr(model, "check_interpolants", checked)
    write_windowed_run(tmp_path / "run", spec, WindowPolicy(2, recording))
    grid = timeline(spec)
    np.testing.assert_array_equal(intervals, np.column_stack((grid[:-1], grid[1:])))


def test_unrecorded_cubic_failure_and_sink_failure_never_publish_complete(monkeypatch, tmp_path):
    spec = short_spec("source_pair_controls", 0.081)
    data = spec.to_dict()
    data["experiment"]["observation_times"] = [0.0]
    spec = parse_spec(data)
    model = get_model(spec.model)
    original = model.check_interpolants

    def checked(times, *args):
        if times[0] > 0:
            raise NumericalError("injected hidden cubic failure")
        return original(times, *args)

    monkeypatch.setattr(model, "check_interpolants", checked)
    root = tmp_path / "failure"
    with pytest.raises(NumericalError, match="hidden cubic"):
        write_windowed_run(root, spec, WindowPolicy(2, "checkpoints"))
    assert (root / "checkpoint_initial/manifest.json").exists()
    assert not (root / "manifest.json").exists()
    assert not (root / "checkpoint_final").exists()

    def failed_sink(window):
        raise OSError("injected sink failure")

    with pytest.raises(OSError, match="sink failure"):
        run_windowed(spec, WindowPolicy(2), sink=failed_sink)


@pytest.mark.parametrize("recording", ["full", "observations", "checkpoints"])
def test_index_payloads_selection_hashes_and_summary(recording, tmp_path):
    spec = synthetic_pair().worlds[0].simulation
    root = tmp_path / recording
    full = run(spec)
    summary = write_windowed_run(
        root, spec, WindowPolicy(2, recording), checkpoint_times=[0, 0.137, 1, 0.137]
    )
    assert summary["max_balance_error_fmol"] == full.max_balance_error
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["kind"] == "cells_windowed_run"
    assert len(manifest["files_sha256"]) == 7
    for name, checksum in manifest["files_sha256"].items():
        assert _sha256(root / name) == checksum
    accepted, observed, snapshots = [], [], 0
    for line in (root / "windows.jsonl").read_text().splitlines():
        entry = json.loads(line)
        if entry["kind"] == "checkpoint":
            snapshots += 1
            for name in ("state", "manifest"):
                assert (
                    _sha256(
                        root / entry["path"] / ("state.npz" if name == "state" else "manifest.json")
                    )
                    == entry[f"{name}_sha256"]
                )
            load_snapshot(root / entry["path"])
        elif entry["path"]:
            assert _sha256(root / entry["path"]) == entry["sha256"]
            with np.load(root / entry["path"], allow_pickle=False) as arrays:
                if recording == "full":
                    accepted.extend(arrays["accepted_times"])
                else:
                    assert "accepted_times" not in arrays
                    assert not set(full.history._fields) & set(arrays.files)
                if "observation_times" in arrays:
                    observed.extend(arrays["observation_times"])
    assert snapshots == 3
    assert accepted == (full.times.tolist() if recording == "full" else [])
    assert observed == (full.observations.times.tolist() if recording != "checkpoints" else [])
    if recording == "checkpoints":
        assert not (root / "chunks").exists()
    final = load_snapshot(root / "checkpoint_final")
    for a, b in zip(final.checkpoint.state, full.final.state, strict=True):
        np.testing.assert_array_equal(a, b)
    with pytest.raises(ConfigError, match="already exists"):
        write_windowed_run(root, spec)


@pytest.mark.parametrize("time", [-1, True, float("nan"), 0.071, 2])
def test_invalid_checkpoint_request_leaves_no_output(time, tmp_path):
    with pytest.raises(ConfigError):
        write_windowed_run(
            tmp_path / "bad",
            synthetic_pair().worlds[0].simulation,
            WindowPolicy(2),
            checkpoint_times=[time],
        )
    assert not (tmp_path / "bad").exists()


def test_clock_validation_still_rejects_tampering_and_new_reducers_require_contract():
    spec = short_spec("single_cell_pulse")
    cp = run(spec).final
    for changed in [
        replace(cp, time=cp.time - 0.001),
        replace(cp, step_index=True),
        replace(cp, event_index=99),
    ]:
        with pytest.raises(ConfigError):
            validate_checkpoint(spec, changed)
    with pytest.raises(ConfigError, match="reducers"):
        windows.merge_diagnostics({}, {"sum_work": 1.0})
    with pytest.raises(ConfigError, match="fields"):
        windows.merge_diagnostics({"max_error": 1.0}, {"max_new": 1.0})
