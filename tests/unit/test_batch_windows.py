"""Cohort rounds are a bounded execution policy, not a shared biological clock."""

import json
from dataclasses import replace

import jax.numpy as jnp
import numpy as np
import pytest

from cells import batch_window_io
from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.batch_window_io import write_windowed_batch
from cells.core import batch_windows, runner
from cells.core.batch import branch_batch_checkpoints, run_batch
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows, run_batch_windowed
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import run, timeline
from cells.core.specs import ConfigError, InputChange, parse_spec
from cells.core.windows import WindowPolicy, iter_windows, merge_diagnostics
from cells.io import _sha256
from cells.models.registry import get_model
from tests.batch_fixtures import MODELS, definition, short_spec, synthetic_pair
from tests.unit.test_windows import assert_windows


def local_parts(rounds, identity):
    return [r.worlds[identity] for r in rounds if identity in r.worlds]


@pytest.mark.parametrize("name", MODELS)
@pytest.mark.parametrize("width", [1, 7, 1000])
def test_all_models_exact_scalar_batch_window_parity(name, width):
    spec = definition([short_spec(name, 0.073), short_spec(name, 0.041)])
    full = run_batch(spec)
    rounds = list(iter_batch_windows(spec, WindowPolicy(width)))
    assert len(rounds) == max(
        p.window_count for p in plan_batch_windows(spec, WindowPolicy(width)).worlds
    )
    for world in spec.worlds:
        identity = world.world_id
        parts = local_parts(rounds, identity)
        assert_windows(parts, full.worlds[identity])
        assert_windows(parts, run(world.simulation))
        scalar_parts = list(iter_windows(world.simulation, WindowPolicy(width)))
        assert len(parts) == len(scalar_parts)
        maxima = {}
        for part, scalar in zip(parts, scalar_parts, strict=True):
            np.testing.assert_array_equal(part.times, scalar.times)
            for a, b in zip(part.history, scalar.history, strict=True):
                np.testing.assert_array_equal(a, b)
            merge_diagnostics(maxima, part.diagnostics)
            for value in (
                *part.history,
                part.times,
                *vars(part.observations).values(),
                *part.final.state,
            ):
                assert not value.flags.writeable
            for endpoint, history in zip(part.final.state, part.history, strict=True):
                assert not np.shares_memory(endpoint, history)
        assert maxima == full.worlds[identity].diagnostics
    for index, round_ in enumerate(rounds):
        assert round_.index == index and set(round_.checkpoints) == {10, 11}
        assert round_.resources["prepared_parameter_sets"] == (2 if index == 0 else 0)
        assert round_.resources["compiled_executables"] == 1
    assert (
        sum(r.resources["executed_world_steps"] for r in rounds)
        == full.resources["executed_world_steps"]
    )


@pytest.mark.parametrize("name", MODELS)
def test_eager_complete_cohorts(name):
    spec = definition([short_spec(name, 0.0037, jit=False), short_spec(name, 0.0021, jit=False)])
    rounds = list(iter_batch_windows(spec, WindowPolicy(1)))
    for world in spec.worlds:
        assert_windows(local_parts(rounds, world.world_id), run(world.simulation))
    assert all(r.resources["compiled_executables"] == 0 for r in rounds)


@pytest.mark.parametrize("name", MODELS)
def test_independent_restart_clocks_finished_worlds_and_new_policy(name, tmp_path):
    spec = definition([short_spec(name, 0.073), short_spec(name, 0.041)])
    full = run_batch(spec)
    starts = full.checkpoint_at({10: float(full.worlds[10].times[2]), 11: 0.041})
    write_batch_snapshot(tmp_path / "start", spec, starts)
    saved = load_batch_snapshot(tmp_path / "start")
    root = tmp_path / "resumed"
    write_windowed_batch(
        root, saved.spec, WindowPolicy(2, "full"), saved.checkpoints, checkpoint_every_windows=1
    )
    parts = list(iter_batch_windows(spec, WindowPolicy(3), saved.checkpoints))
    assert len(local_parts(parts, 11)) == 1
    for round_ in parts:
        assert round_.checkpoints[11].time == 0.041
        assert round_.checkpoints[11].step_index == full.worlds[11].final.step_index
    for world in spec.worlds:
        assert_windows(
            local_parts(parts, world.world_id), run(world.simulation, starts[world.world_id])
        )
    final = load_batch_snapshot(root / "checkpoint_final")
    zero = list(iter_batch_windows(spec, WindowPolicy(17), final.checkpoints))
    assert len(zero) == 1
    assert zero[0].resources["executed_world_steps"] == 0
    assert zero[0].resources["compiled_executables"] == 0
    for world in spec.worlds:
        assert_windows(
            local_parts(zero, world.world_id),
            run(world.simulation, final.checkpoints[world.world_id]),
        )
    for path in sorted(root.glob("snapshots/*")):
        cp = load_batch_snapshot(path)
        replay = run_batch_windowed(spec, WindowPolicy(5, "checkpoints"), cp.checkpoints)
        for identity, checkpoint in replay.checkpoints.items():
            for a, b in zip(checkpoint.state, final.checkpoints[identity].state, strict=True):
                np.testing.assert_array_equal(a, b)


def test_ids_order_parameters_events_and_future_branch():
    spec = synthetic_pair()
    full = run_batch(spec)
    starts = full.checkpoint_at({10: 0.5, 11: 0.173})
    first = spec.worlds[0].simulation
    changed = replace(
        first,
        experiment=replace(
            first.experiment, source=first.experiment.source + (InputChange(0.5, 0),)
        ),
    )
    branch = replace(spec, worlds=(spec.worlds[1], replace(spec.worlds[0], simulation=changed)))
    carry = branch_batch_checkpoints(spec, starts, branch)
    rounds = list(iter_batch_windows(branch, WindowPolicy(2), carry))
    for world in branch.worlds:
        assert_windows(
            local_parts(rounds, world.world_id), run(world.simulation, carry[world.world_id])
        )
    reverse = list(
        iter_batch_windows(replace(spec, worlds=tuple(reversed(spec.worlds))), WindowPolicy(3))
    )
    rename = replace(spec, worlds=tuple(replace(w, world_id=w.world_id + 30) for w in spec.worlds))
    renamed = list(iter_batch_windows(rename, WindowPolicy(3)))
    for identity in (10, 11):
        assert_windows(local_parts(reverse, identity), full.worlds[identity])
        assert_windows(local_parts(renamed, identity + 30), full.worlds[identity])
    assert 0.173 not in full.worlds[10].times and 0.137 not in full.worlds[11].times
    altered = replace(
        spec,
        worlds=(
            replace(
                spec.worlds[0],
                simulation=replace(first, model=replace(first.model, initial_amount=20)),
            ),
            spec.worlds[1],
        ),
    )
    assert_windows(
        local_parts(list(iter_batch_windows(altered, WindowPolicy(2))), 11), full.worlds[11]
    )


@pytest.mark.parametrize("name", MODELS)
def test_independent_dt_and_inactive_capacity_padding(name):
    original = short_spec(name, 0.014)
    padded = replace(
        original,
        execution=replace(
            original.execution,
            capacity=original.execution.capacity + 2,
            edge_capacity=original.execution.edge_capacity + 2
            if original.execution.edge_capacity
            else 0,
            membrane_capacity=original.execution.membrane_capacity + 2
            if original.execution.membrane_capacity
            else 0,
        ),
    )
    shorter_step = replace(padded, execution=replace(padded.execution, dt=padded.execution.dt / 2))
    cohort = definition([padded, shorter_step])
    rounds = list(iter_batch_windows(cohort, WindowPolicy(2)))
    for world in cohort.worlds:
        assert_windows(local_parts(rounds, world.world_id), run(world.simulation))
    assert rounds[0].checkpoints[10].time != rounds[0].checkpoints[11].time


def test_prepared_parameters_and_compiled_widths_are_reused(monkeypatch):
    spec = synthetic_pair()
    model = get_model(spec.worlds[0].simulation.model)
    original = model.parameters
    calls, widths = [], []

    def parameters(*args):
        calls.append(args[0].fingerprint)
        return original(*args)

    compiled = batch_windows._compiled_batch

    class CountCompilations:
        def lower(self, inputs, rhs, domain, checked_step=None):
            widths.append(inputs[1].shape[1])
            return compiled.lower(inputs, rhs, domain, checked_step)

    monkeypatch.setattr(model, "parameters", parameters)
    monkeypatch.setattr(batch_windows, "_compiled_batch", CountCompilations())
    result = run_batch_windowed(spec, WindowPolicy(2))
    assert calls == [w.simulation.fingerprint for w in spec.worlds]
    assert widths == [2]
    assert result.resources["rounds"] > len(widths)
    assert result.resources["peak_compiled_executables"] == len(widths)
    assert (
        result.resources["padded_step_slots"] <= result.resources["conservative_padded_step_bound"]
    )


def test_tail_padding_respects_the_existing_padded_work_budget():
    from cells.core.batch import checkpoint_batch_limits

    spec = synthetic_pair()
    _, bound = checkpoint_batch_limits(spec)
    remaining = max(len(timeline(w.simulation)) - 1 for w in spec.worlds)
    policy = WindowPolicy(remaining - 1)
    assert remaining > 4
    roomy = plan_batch_windows(spec, policy)
    assert roomy.fixed_kernel_width == policy.window_steps
    assert roomy.padded_step_bound > bound
    tight = replace(spec, max_padded_steps=bound)
    planned = plan_batch_windows(tight, policy)
    assert planned.fixed_kernel_width is None and planned.padded_step_bound == bound
    rounds = list(iter_batch_windows(tight, policy))
    assert sum(r.resources["padded_step_slots"] for r in rounds) <= bound
    assert rounds[-1].resources["compiled_executables"] == 2
    for world in tight.worlds:
        assert_windows(local_parts(rounds, world.world_id), run(world.simulation))


def test_finished_world_never_evaluates_its_rhs(monkeypatch):
    spec = synthetic_pair()
    full = run_batch(spec)
    starts = full.checkpoint_at({10: 0.5, 11: 0.7})
    model = get_model(spec.worlds[0].simulation.model)
    original = model.rhs

    def fail_finished(state, control, parameters, active):
        value = original(state, control, parameters, active)
        return value._replace(amount=jnp.where(parameters > 0.5, jnp.inf, value.amount))

    monkeypatch.setattr(model, "rhs", fail_finished)
    rounds = list(iter_batch_windows(spec, WindowPolicy(2), starts))
    assert_windows(local_parts(rounds, 10), run(spec.worlds[0].simulation, starts[10]))
    assert len(local_parts(rounds, 11)) == 1
    for part in rounds:
        for a, b in zip(part.checkpoints[11].state, starts[11].state, strict=True):
            np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("name", ["source_pair_controls", "bioelectric_pair_baseline"])
def test_sampled_state_accounting_continuity_crosses_rounds(name, monkeypatch):
    spec = short_spec(name, 0.004)
    spec = replace(
        spec,
        execution=replace(spec.execution, dt=0.001),
        experiment=replace(spec.experiment, observation_times=(0.0003, 0.0013, 0.0023, 0.0033)),
    )
    full = run(spec)
    model = get_model(spec.model)
    original = model.check_values
    compared = []

    def check(state, definition):
        if state[0].ndim == 3 and len(state[0]) == 2:
            compared.append(state[0].copy())
        return original(state, definition)

    monkeypatch.setattr(model, "check_values", check)
    run_batch_windowed(definition([spec, spec]), WindowPolicy(1))
    values = getattr(full.observations, model.STATE_TYPE._fields[0])
    for index in range(len(values) - 1):
        assert sum(np.array_equal(v, values[index : index + 2]) for v in compared) == 2


@pytest.mark.parametrize("recording", ["full", "observations", "checkpoints"])
def test_incremental_index_rows_checksums_summaries_and_round_snapshots(recording, tmp_path):
    spec = synthetic_pair()
    full = run_batch(spec)
    root = tmp_path / recording
    summary = write_windowed_batch(
        root, spec, WindowPolicy(2, recording), checkpoint_every_windows=3
    )
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["kind"] == "cells_windowed_independent_world_run"
    assert len(manifest["files_sha256"]) == 5 + 4 * len(spec.worlds)
    assert manifest["resources"]["prepared_parameter_sets"] == len(spec.worlds)
    for name, checksum in manifest["files_sha256"].items():
        assert _sha256(root / name) == checksum
    accepted = {10: [], 11: []}
    observed = {10: [], 11: []}
    entries = [json.loads(line) for line in (root / "windows.jsonl").read_text().splitlines()]
    snapshots = []
    for entry in entries:
        if entry["kind"] == "cohort_checkpoint":
            snapshots.append(entry)
            assert entry["completed_rounds"] % 3 == 0
            assert entry["completed_rounds"] < summary["rounds"]
            assert _sha256(root / entry["path"] / "manifest.json") == entry["manifest_sha256"]
            saved = load_batch_snapshot(root / entry["path"])
            prior = [
                e
                for e in entries
                if e["kind"] == "world_window" and e["round"] < entry["completed_rounds"]
            ]
            for identity, cp in saved.checkpoints.items():
                last = [e for e in prior if e["world_id"] == identity][-1]
                assert cp.time == last["end_time"] and cp.step_index == last["end_step"]
            continue
        identity = entry["world_id"]
        if entry["path"] is not None:
            assert _sha256(root / entry["path"]) == entry["sha256"]
            with np.load(root / entry["path"], allow_pickle=False) as arrays:
                if recording == "full":
                    start = entry["start_step"] + (entry["index"] > 0)
                    stop = entry["end_step"] + 1
                    np.testing.assert_array_equal(
                        arrays["accepted_times"], full.worlds[identity].times[start:stop]
                    )
                    accepted[identity].extend(arrays["accepted_times"])
                    for name, values in zip(
                        full.worlds[identity].history._fields,
                        full.worlds[identity].history,
                        strict=True,
                    ):
                        np.testing.assert_array_equal(arrays[name], values[start:stop])
                else:
                    assert "accepted_times" not in arrays
                if "observation_times" in arrays:
                    start = len(observed[identity])
                    stop = start + len(arrays["observation_times"])
                    observed[identity].extend(arrays["observation_times"])
                    for name, values in vars(full.worlds[identity].observations).items():
                        key = "observation_times" if name == "times" else f"observed_{name}"
                        np.testing.assert_array_equal(arrays[key], values[start:stop])
        else:
            assert entry["sha256"] is None
    assert len(snapshots) == manifest["resources"]["periodic_snapshots"]
    for identity in (10, 11):
        assert accepted[identity] == (
            full.worlds[identity].times.tolist() if recording == "full" else []
        )
        assert observed[identity] == (
            full.worlds[identity].observations.times.tolist() if recording != "checkpoints" else []
        )
        assert (
            summary["world_summaries"][str(identity)]["max_balance_error_fmol"]
            == full.worlds[identity].max_balance_error
        )
    if recording == "checkpoints":
        assert not (root / "worlds").exists()
    with pytest.raises(ConfigError, match="already exists"):
        write_windowed_batch(root, spec)


@pytest.mark.parametrize(
    "setting",
    ["aggregate", "padded_aggregate", "work", "capacity", "observations", "per_world_steps"],
)
def test_resource_refusal_precedes_control_and_capacity_allocation(setting, monkeypatch):
    spec = synthetic_pair()
    policy = WindowPolicy(8)
    if setting == "aggregate":
        spec = replace(spec, max_working_bytes=1)
    elif setting == "padded_aggregate":
        tiny = short_spec("single_cell_pulse", 0.0001)
        spec = definition([spec.worlds[0].simulation, tiny])
        plan = plan_batch_windows(spec, policy)
        unpadded = sum(p.estimated_working_bytes for p in plan.worlds)
        assert unpadded < plan.estimated_working_bytes
        spec = replace(spec, max_working_bytes=unpadded)
    elif setting == "work":
        spec = replace(spec, max_padded_steps=1)
    else:
        data = spec.worlds[0].simulation.to_dict()
        if setting == "capacity":
            data["execution"].update(capacity=1000000, max_trace_bytes=10000)
        elif setting == "observations":
            data["execution"]["max_trace_bytes"] = 10000
            data["experiment"]["observation_times"] = np.linspace(0, 0.01, 200).tolist()
        else:
            data["execution"]["max_steps"] = 1
        changed = parse_spec(data)
        spec = definition([changed, changed])

    def forbidden(*args, **kwargs):
        pytest.fail("Array allocation before refusal")

    monkeypatch.setattr(batch_windows, "control_values", forbidden)
    monkeypatch.setattr(get_model(spec.worlds[0].simulation.model), "initial_values", forbidden)
    with pytest.raises(
        ConfigError, match="max_working_bytes|max_padded_steps|max_trace_bytes|max_steps"
    ):
        plan_batch_windows(spec, policy)


def test_small_budget_full_refused_window_restart_and_branch_succeed(monkeypatch, tmp_path):
    specs = []
    for end in (1.0, 0.7):
        data = short_spec("single_cell_pulse", end).to_dict()
        data["execution"].update(dt=0.001, max_trace_bytes=10000)
        specs.append(parse_spec(data))
    spec = replace(definition(specs), max_working_bytes=20000)
    with pytest.raises(ConfigError, match="max_working_bytes|max_trace_bytes"):
        run_batch(spec)

    def forbidden(*args, **kwargs):
        pytest.fail("Full timeline requested")

    monkeypatch.setattr(runner, "timeline", forbidden)
    root = tmp_path / "bounded"
    write_windowed_batch(root, spec, WindowPolicy(8, "checkpoints"), checkpoint_every_windows=25)
    saved = load_batch_snapshot(root / "snapshots/round-0000000050")
    assert saved.checkpoints[10].time == saved.checkpoints[11].time == 0.4
    resumed = run_batch_windowed(spec, WindowPolicy(11), saved.checkpoints)
    final = load_batch_snapshot(root / "checkpoint_final")
    for identity, cp in resumed.checkpoints.items():
        for a, b in zip(cp.state, final.checkpoints[identity].state, strict=True):
            np.testing.assert_array_equal(a, b)
    changed = replace(
        spec,
        worlds=tuple(
            replace(
                w,
                simulation=replace(
                    w.simulation,
                    experiment=replace(
                        w.simulation.experiment,
                        source=w.simulation.experiment.source + (InputChange(0.4, 4),),
                    ),
                ),
            )
            for w in spec.worlds
        ),
    )
    carry = branch_batch_checkpoints(spec, saved.checkpoints, changed)
    future = run_batch_windowed(changed, WindowPolicy(8), carry)
    assert future.checkpoints[10].state.amount[0] > resumed.checkpoints[10].state.amount[0]
    with pytest.raises(ConfigError, match="max_padded_steps"):
        plan_batch_windows(replace(spec, max_padded_steps=1), WindowPolicy(8), final.checkpoints)


@pytest.mark.parametrize("name", ["source_pair_controls", "bioelectric_pair_baseline"])
@pytest.mark.parametrize("recording", ["full", "observations", "checkpoints"])
def test_every_unobserved_cubic_interval_is_checked(name, recording, monkeypatch, tmp_path):
    spec = short_spec(name, 0.041)
    spec = replace(spec, experiment=replace(spec.experiment, observation_times=(0.0,)))
    cohort = definition([spec, spec])
    model = get_model(spec.model)
    original = model.check_interpolants
    intervals = []

    def checked(times, *args):
        intervals.extend(zip(times[:-1], times[1:], strict=True))
        return original(times, *args)

    monkeypatch.setattr(model, "check_interpolants", checked)
    write_windowed_batch(tmp_path / "run", cohort, WindowPolicy(2, recording))
    grid = timeline(spec)
    expected = list(zip(grid[:-1], grid[1:], strict=True)) * 2
    assert sorted(intervals) == sorted(expected)


@pytest.mark.parametrize("recording", ["full", "observations", "checkpoints"])
def test_whole_round_failure_does_not_publish_any_world(recording, monkeypatch, tmp_path):
    cohort = synthetic_pair()
    model = get_model(cohort.worlds[0].simulation.model)
    original = model.observe_history

    def fail(times, history, layout, requested, spec):
        if spec.model.decay_rate > 0.5 and times[0] > 0:
            raise NumericalError("injected late second-world observer failure")
        return original(times, history, layout, requested, spec)

    monkeypatch.setattr(model, "observe_history", fail)
    root = tmp_path / recording
    with pytest.raises(NumericalError, match="World 11.*late second-world.*batch refused"):
        write_windowed_batch(root, cohort, WindowPolicy(2, recording), checkpoint_every_windows=1)
    entries = [json.loads(line) for line in (root / "windows.jsonl").read_text().splitlines()]
    assert {e["round"] for e in entries if e["kind"] == "world_window"} == {0}
    saved = load_batch_snapshot(root / "snapshots/round-0000000001")
    assert set(saved.checkpoints) == {10, 11}
    assert not (root / "manifest.json").exists()
    assert not (root / "checkpoint_final").exists()


def test_numerical_failure_names_world_and_sink_io_failure_not_complete(monkeypatch, tmp_path):
    cohort = synthetic_pair()
    model = get_model(cohort.worlds[0].simulation.model)
    original = model.rhs

    def fail(state, control, parameters, active):
        value = original(state, control, parameters, active)
        return value._replace(amount=jnp.where(parameters > 0.5, jnp.inf, value.amount))

    with monkeypatch.context() as patch:
        patch.setattr(model, "rhs", fail)
        with pytest.raises(NumericalError, match="World 11.*batch refused"):
            run_batch_windowed(
                cohort, WindowPolicy(2), sink=lambda r: pytest.fail("Partial round escaped")
            )

    def fail_io(*args):
        raise OSError("injected output failure")

    monkeypatch.setattr(batch_window_io, "_write_window_chunk", fail_io)
    with pytest.raises(OSError, match="output failure"):
        write_windowed_batch(tmp_path / "bad", cohort, WindowPolicy(2))
    assert not (tmp_path / "bad/manifest.json").exists()
    with pytest.raises(OSError, match="output failure"):
        run_batch_windowed(cohort, WindowPolicy(2), sink=fail_io)


@pytest.mark.parametrize("value", [-1, True, 1.5, "2", 2**31])
def test_invalid_checkpoint_cadence_leaves_no_output(value, tmp_path):
    with pytest.raises(ConfigError, match="checkpoint_every_windows"):
        write_windowed_batch(tmp_path / "bad", synthetic_pair(), checkpoint_every_windows=value)
    assert not (tmp_path / "bad").exists()


def test_invalid_policy_checkpoint_map_and_sink():
    spec = synthetic_pair()
    with pytest.raises(ConfigError, match="WindowPolicy"):
        plan_batch_windows(spec, {})
    with pytest.raises(ConfigError, match="world IDs"):
        iter_batch_windows(spec, checkpoints={})
    with pytest.raises(ConfigError, match="callable"):
        run_batch_windowed(spec, sink=[])
    full = run_batch(spec)
    starts = full.checkpoint_at(0.5)
    starts[11] = replace(starts[11], event_index=99)
    with pytest.raises(ConfigError, match="World 11.*event"):
        iter_batch_windows(spec, checkpoints=starts)


def test_working_estimate_horizon_independent_and_includes_observation_and_padding():
    a = short_spec("single_cell_pulse", 1)
    b = replace(a, experiment=replace(a.experiment, end_time=100, observation_times=(0.0, 100.0)))
    a = replace(a, experiment=replace(a.experiment, observation_times=(0.0, 1.0)))
    small = plan_batch_windows(definition([a, a]), WindowPolicy(3))
    large = plan_batch_windows(definition([b, b]), WindowPolicy(3))
    assert large.estimated_working_bytes == small.estimated_working_bytes
    assert large.padded_step_bound > small.padded_step_bound
    assert small.estimated_working_bytes == 2 * sum(
        trace_bytes(p.spec, 3, p.max_observations + 1) + trace_bytes(p.spec, 0, 0)
        for p in small.worlds
    )
