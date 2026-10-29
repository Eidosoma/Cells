"""Public checked execution/restart/planning in a patched frozen source copy.

The bounded runner selects disjoint phases in fresh processes. No test imports
the 46-check component suite or substitutes a numerical/public execution hook.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

OUT = Path(os.environ.get("CELLS_REGULATED_PUBLIC_OUTPUT", "/tmp/cells-public-output-required"))
MODEL_ID = "resolved_calcium_energy_regulated@1"


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, allow_nan=False, default=lambda v: v.tolist()) + "\n"
    )


def report(name, **data):
    write(OUT / "evidence" / (name + ".json"), dict(status="passed", **data))


def raw(world=1, refinement=1):
    result = read(OUT / "inputs" / ("world-" + str(world) + ".json"))
    result["execution"]["dt"] /= refinement
    return result


def identity():
    from cells.io import runtime_identity, source_hashes

    current = dict(runtime=runtime_identity("cpu"), source_hashes=source_hashes())
    assert current == read(OUT / "public_identity.json")
    return current


def state_error(c, actual, expected):
    from validation.regulation.integrated_network_regulation_reference import flatten

    budget = flatten(
        c,
        {
            k: np.full(shape, 3e-23 if k.endswith("_C") else 2e-11)
            for k, shape in c["shapes"].items()
        },
    ) + 3e-8 * np.abs(expected)
    ratio = float(np.max(np.abs(actual - expected) / budget, initial=0))
    assert ratio <= 1, ratio
    return ratio


def check_reference(result, world=1):
    from validation.regulation import integrated_network_regulation_reference as reference

    c = reference.bind(result.spec.to_dict())
    with np.load(
        OUT / "references" / ("world-" + str(world) + ".npz"), allow_pickle=False
    ) as target:
        state_key = "state" if "state" in target.files else "reference_state"
        positions = [
            int(np.flatnonzero(result.times == t)[0])
            for t in target["times"]
            if t >= result.times[0]
        ]
        expected = target[state_key][
            [i for i, t in enumerate(target["times"]) if t >= result.times[0]]
        ]
        actual = reference.flatten(c, result.history._asdict())[positions]
    return state_error(c, actual, expected)


def merge_windows(records):
    """Concatenate accepted public results; no integration step is introduced."""
    from cells.core.runner import RunResult
    from cells.core.windows import merge_diagnostics

    first = records[0]
    times = np.concatenate([r.times if i == 0 else r.times[1:] for i, r in enumerate(records)])
    history = type(first.history)(
        *(
            np.concatenate([v if i == 0 else v[1:] for i, v in enumerate(values)], axis=0)
            for values in zip(*(r.history for r in records), strict=True)
        )
    )
    observations = type(first.observations)(
        *(
            np.concatenate([getattr(r.observations, k) for r in records], axis=0)
            for k in vars(first.observations)
        )
    )
    diagnostics, timings = {}, {}
    for r in records:
        merge_diagnostics(diagnostics, r.diagnostics)
        for k, v in r.timings.items():
            timings[k] = timings.get(k, 0.0) + v
    return RunResult(
        first.spec,
        records[-1].final,
        first.start_step,
        times,
        history,
        observations,
        timings,
        diagnostics,
    )


def save_trace(path, result):
    np.savez_compressed(path, times=result.times, **result.history._asdict())


def scalar_run(spec, checkpoint=None):
    from cells.core.windows import WindowPolicy, iter_windows

    records = []
    for window in iter_windows(spec, WindowPolicy(1, "full"), checkpoint):
        records.append(window)
        print("accepted scalar", window.final.step_index, window.final.time, flush=True)
    return merge_windows(records)


def test_contracts_public_dispatch_absolute_controls_and_refusals():
    from cells.core.batch import BatchSpec, WorldSpec, parse_batch
    from cells.core.runner import timeline
    from cells.core.schedule import control_values, event_index
    from cells.core.specs import ConfigError, parse_spec
    from cells.core.windows import WindowPolicy, plan_windows
    from cells.io import runtime_identity, source_hashes
    from cells.models import surface_calcium_energy_regulated as model
    from cells.models.registry import get_model

    spec = parse_spec(raw())
    assert spec == parse_spec(spec.to_dict()) and get_model(spec.model) is model
    assert len(model.STATE_TYPE._fields) == 38
    grid = timeline(spec)
    assert all(t in grid for t in (3.3e-6, 6.25e-6, 7.1e-6))
    controls = control_values(spec, [0.0, 3.3e-6, 6.25e-6, 7.1e-6, 10e-6])
    assert controls.pump[0, 0] == 0.8 and controls.pump[1, 0] == 0.0
    assert controls.pump[3, 0] == 0.6 and controls.regeneration[2, 0] == 0.0
    assert event_index(spec, 6.25e-6) > event_index(spec, 0.0)
    batch = BatchSpec((WorldSpec(23, spec), WorldSpec(71, parse_spec(raw(2)))), 2, 128, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    refusals = []
    changed = spec.to_dict()
    changed["execution"]["max_trace_bytes"] = 1
    with pytest.raises(ConfigError):
        plan_windows(parse_spec(changed), WindowPolicy(1, "full"))
    refusals.append("scalar_trace_budget")
    changed = batch.to_dict()
    changed["execution"]["max_working_bytes"] = 1
    from cells.core.batch_windows import plan_batch_windows

    with pytest.raises(ConfigError):
        plan_batch_windows(parse_batch(changed), WindowPolicy(1, "full"))
    refusals.append("cohort_working_budget")
    current = dict(runtime=runtime_identity("cpu"), source_hashes=source_hashes())
    write(OUT / "public_identity.json", current)
    report(
        "contracts",
        definition=spec.to_dict(),
        grid=grid,
        refusals=refusals,
        state_fields=list(model.STATE_TYPE._fields),
        identity=current,
    )


def test_plans_offline_one_four_sixteen_gpu_preserve_regulation_and_worlds():
    from cells.ensemble.plan import jupiter_plan, plan

    identity()
    definition = raw()
    definition["execution"]["backend"] = "gpu"
    experiment = dict(
        kind="ionic_ensemble@1",
        seed=321,
        arms=[
            dict(
                id="regulated",
                definition=dict(model="ionic_worlds@1", simulation=definition, window_steps=1),
                worlds=16,
                batch_worlds=1,
                seconds_per_world=None,
            )
        ],
        execution=dict(
            max_wall_seconds=600,
            max_output_bytes=4 * 2**30,
            target_gpu_utilization_pct=70,
            worker_threads=1,
        ),
    )
    original = deepcopy(experiment)
    # Each public planner validates every emitted task. Avoid repeating the
    # same 16-GPU construction and reparsing each complete physical model in
    # the verification loop. Compare every emitted definition with the public
    # canonical definition already checked by the contracts phase instead.
    plans, timings = {}, {}
    for key, builder in (
        ("1", lambda: plan(experiment, 1)),
        ("4", lambda: jupiter_plan(experiment, 1)),
        ("16", lambda: jupiter_plan(experiment, 4)),
    ):
        began = time.monotonic()
        plans[key] = builder()
        timings[key] = time.monotonic() - began
        write(
            OUT / "evidence/offline-plan-progress.json", dict(status="running", completed=timings)
        )
        print("planned GPU slots", key, "seconds", timings[key], flush=True)
    canonical = read(OUT / "evidence/contracts.json")["definition"]
    canonical["execution"]["backend"] = "gpu"
    for candidate in plans.values():
        ids = []
        for task in candidate["tasks"]:
            group = task["definition"]
            assert group["simulation"] == canonical
            assert group["simulation"]["model"]["id"] == MODEL_ID
            assert len(group["simulation"]["model"]["network_regulation"]["rules"]) == 4
            assert group["seed"] == 321 and group["worlds"] == 1
            ids.extend(range(group["world_id_start"], group["world_id_start"] + group["worlds"]))
        assert sorted(ids) == list(range(16))
    assert experiment == original
    assert plans["1"]["tasks"] == plans["4"]["tasks"] == plans["16"]["tasks"]
    remote = plans["16"]["deployment"]
    assert (
        not remote["remote_execution_qualified"] and not remote["interacting_tissue_partitioning"]
    )
    report(
        "offline-plans",
        inputs=experiment,
        plans=plans,
        planner_wall_seconds=timings,
        world_ids=list(range(16)),
        scope="Offline plans only; no GPU execution or utilization claim",
    )
    write(OUT / "evidence/offline-plan-progress.json", dict(status="passed", completed=timings))


def test_reference_independent_world_two_capture():
    root = Path(__file__).resolve().parents[2]
    script = (
        root
        / "agent-work/cells-worker-01/workfiles"
        / "capture_surface_calcium_energy_regulated_reference.py"
    )
    completed = subprocess.run(
        [sys.executable, "-B", str(script), "--output", str(OUT)],
        cwd=root,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
    )
    write(
        OUT / "evidence/oracle-launch.json",
        dict(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            parent_pid=os.getpid(),
        ),
    )
    assert completed.returncode == 0, completed.stderr
    proof = read(OUT / "evidence/independent-world-two.json")
    assert proof["status"] == "passed" and len(proof["fields"]) == 38
    assert proof["execution"]["pid"] != os.getpid()
    assert not proof["execution"]["pytest_imported"]
    assert not proof["production_imported"] and not proof["jax_imported"]
    assert all(not values for values in proof["independence_guards"].values())


@pytest.mark.parametrize("refinement", [1, 2], ids=["base", "fine"])
def test_scalar_checked_bounded_full_transient_and_public_checkpoint(refinement):
    from cells.core.specs import parse_spec
    from cells.io import write_run

    identity()
    spec = parse_spec(raw(refinement=refinement))
    result = scalar_run(spec)
    ratio = check_reference(result)
    folder = OUT / ("scalar-" + ("base" if refinement == 1 else "fine"))
    folder.mkdir()
    summary = write_run(
        folder / "run",
        result,
        checkpoint_times=(6.25e-6,),
        provenance=dict(operation="frozen_public_execution_qualification", refinement=refinement),
    )
    save_trace(folder / "complete_trace.npz", result)
    assert summary["model"] == MODEL_ID and len(result.history) == 38
    manifest = read(folder / "run/checkpoint_final/manifest.json")
    assert dict(runtime=manifest["runtime"], source_hashes=manifest["source_hashes"]) == identity()
    observed = result.observations
    at = int(np.flatnonzero(observed.times == 6.25e-6)[0])
    assert (
        observed.nak_scheduled_availability[at, 0] == 0
        and observed.regeneration_availability[at, 0] == 0
    )
    report(
        "scalar-" + str(refinement),
        error_over_budget=ratio,
        summary=summary,
        timings=result.timings,
        diagnostics=result.diagnostics,
        complete_fields=list(result.history._fields),
        source_runtime_identity=identity(),
    )


def test_restore_scalar_fresh_process_complete_suffix_and_identity_refusals():
    from cells.core.specs import ConfigError, digest
    from cells.io import load_snapshot

    identity()
    baseline = OUT / "scalar-base"
    candidates = list((baseline / "run/snapshots").glob("step-*"))
    assert len(candidates) == 1
    snapshot = load_snapshot(candidates[0])
    assert snapshot.checkpoint.time == 6.25e-6
    result = scalar_run(snapshot.spec, snapshot.checkpoint)
    with np.load(baseline / "complete_trace.npz", allow_pickle=False) as original:
        offset = int(np.flatnonzero(original["times"] == snapshot.checkpoint.time)[0])
        np.testing.assert_array_equal(result.times, original["times"][offset:])
        for key in result.history._fields:
            np.testing.assert_array_equal(getattr(result.history, key), original[key][offset:])
    ratio = check_reference(result)
    folder = OUT / "scalar-restored"
    folder.mkdir()
    save_trace(folder / "complete_trace.npz", result)
    refused = []
    for fault in ("source", "runtime", "event", "state-checksum"):
        destination = folder / ("rejected-" + fault)
        shutil.copytree(candidates[0], destination)
        manifest = read(destination / "manifest.json")
        if fault == "source":
            manifest["source_hashes"][next(iter(manifest["source_hashes"]))] = "0" * 64
        if fault == "runtime":
            manifest["runtime"]["numerical_environment"]["XLA_FLAGS"] = "changed"
        if fault == "event":
            manifest["clock"]["event_index"] += 1
        if fault == "state-checksum":
            manifest["state_sha256"] = "0" * 64
        manifest.pop("manifest_sha256")
        manifest["manifest_sha256"] = digest(manifest)
        write(destination / "manifest.json", manifest)
        with pytest.raises(ConfigError):
            load_snapshot(destination)
        refused.append(fault)
    report(
        "fresh-scalar-restore",
        checkpoint_time=snapshot.checkpoint.time,
        exact_complete_suffix=True,
        fields=38,
        error_over_budget=ratio,
        refused_identity_changes=refused,
        source_runtime_identity=identity(),
    )


def cohort():
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.specs import parse_spec

    return BatchSpec(
        (WorldSpec(23, parse_spec(raw())), WorldSpec(71, parse_spec(raw(2)))), 2, 128, 2**32
    )


def batch_run(spec, checkpoints=None, save_midpoint=False):
    from cells.batch_io import write_batch_snapshot
    from cells.core.batch_windows import iter_batch_windows
    from cells.core.windows import WindowPolicy

    records = {23: [], 71: []}
    saved = False
    for window in iter_batch_windows(spec, WindowPolicy(1, "full"), checkpoints):
        for world, result in window.worlds.items():
            records[world].append(result)
        if (
            save_midpoint
            and not saved
            and all(cp.time >= 6.25e-6 for cp in window.checkpoints.values())
        ):
            write_batch_snapshot(OUT / "batch-midpoint", spec, window.checkpoints)
            saved = True
        print(
            "accepted cohort",
            window.index,
            {i: cp.time for i, cp in window.checkpoints.items()},
            flush=True,
        )
    assert not save_midpoint or saved
    return {world: merge_windows(rows) for world, rows in records.items()}


def test_batch_checked_two_worlds_absolute_clocks_and_independent_reference():
    from cells.batch_io import write_batch_snapshot

    identity()
    spec = cohort()
    results = batch_run(spec, save_midpoint=True)
    folder = OUT / "batch"
    folder.mkdir()
    checks = []
    for world, result in results.items():
        save_trace(folder / (str(world) + ".npz"), result)
        ratio = check_reference(result, 1 if world == 23 else 2)
        assert len(result.history) == 38
        checks.append(
            dict(
                world_id=world,
                error_over_budget=ratio,
                steps=len(result.times) - 1,
                diagnostics=result.diagnostics,
                timings=result.timings,
            )
        )
    write_batch_snapshot(
        folder / "checkpoint_final", spec, {i: r.final for i, r in results.items()}
    )
    assert not np.array_equal(results[23].times, results[71].times)
    assert not np.array_equal(
        results[23].final.state.pump_cycles, results[71].final.state.pump_cycles
    )
    report(
        "two-world-execution",
        worlds=checks,
        complete_fields=38,
        independent_clocks=True,
        source_runtime_identity=identity(),
    )


def test_batch_restore_fresh_process_complete_cohort_suffix():
    from cells.batch_io import load_batch_snapshot

    identity()
    saved = load_batch_snapshot(OUT / "batch-midpoint")
    results = batch_run(saved.spec, saved.checkpoints)
    folder = OUT / "batch-restored"
    folder.mkdir()
    checks = []
    for world, result in results.items():
        with np.load(OUT / "batch" / (str(world) + ".npz"), allow_pickle=False) as original:
            offset = int(np.flatnonzero(original["times"] == saved.checkpoints[world].time)[0])
            np.testing.assert_array_equal(result.times, original["times"][offset:])
            for key in result.history._fields:
                np.testing.assert_array_equal(getattr(result.history, key), original[key][offset:])
        save_trace(folder / (str(world) + ".npz"), result)
        ratio = check_reference(result, 1 if world == 23 else 2)
        checks.append(
            dict(
                world_id=world,
                checkpoint_time=saved.checkpoints[world].time,
                exact_complete_suffix=True,
                error_over_budget=ratio,
            )
        )
    report("fresh-cohort-restore", worlds=checks, fields=38, source_runtime_identity=identity())
