"""Complete finite-energy execution contracts; compiled tests run only when coordinated."""

import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.runner import timeline
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.ensemble.families import parse_definition, population
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_energy_water as model
from tests.unit.test_integrated_ensemble import experiment
from validation.tissue import surface_energy_water_fixtures as fixtures
from validation.tissue import surface_energy_water_replay as replay

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, value):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / ("energy-water-execution-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )


def artifacts(root):
    return {str(p.relative_to(root)): replay.digest(p) for p in sorted(root.rglob("*.npz"))}


def worker(root, phase):
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.tissue.surface_energy_water_replay",
        str(root),
        "--backend",
        BACKEND,
        "--phase",
        phase,
    ]
    with (
        (root / (phase + ".stdout.log")).open("x") as out,
        (root / (phase + ".stderr.log")).open("x") as err,
    ):
        subprocess.run(command, stdout=out, stderr=err, timeout=900, check=True)
    return json.loads((root / (phase + ".json")).read_text())


def test_complete_saved_restart_branch_and_windows(tmp_path):
    # Keep this coordinator free of compiled graphs. Workers and the ordinary
    # CLI execute sequentially in the qualification controller's process group.
    reports = {phase: worker(tmp_path, phase) for phase in ("prepare", "resume_branch", "windows")}
    command = [
        sys.executable,
        "-B",
        "-m",
        "cells",
        "resume",
        str(tmp_path / "checkpoint"),
        "--output",
        str(tmp_path / "fresh"),
    ]
    with (
        (tmp_path / "fresh.stdout.log").open("x") as out,
        (tmp_path / "fresh.stderr.log").open("x") as err,
    ):
        subprocess.run(command, stdout=out, stderr=err, timeout=600, check=True)
    target = load_snapshot(tmp_path / "expected").checkpoint
    actual = load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint
    replay.save_checkpoint_arrays(tmp_path / "fresh_actual_final.npz", actual)
    for phase, report in reports.items():
        assert report["status"] == ("prepared" if phase == "prepare" else "passed")
        assert report["backend"] == BACKEND
        assert report["comparison"] == "bitwise"
        assert report["state_fields"] == list(model.STATE_TYPE._fields)
    assert reports["prepare"]["disk"]
    assert reports["resume_branch"]["branch"] and reports["resume_branch"]["terminal"]
    assert reports["windows"]["window_steps"] != reports["windows"]["resumed_window_steps"]
    replay.exact_checkpoint(actual, target)
    with (
        np.load(tmp_path / "expected_history.npz", allow_pickle=False) as expected,
        np.load(tmp_path / "fresh/trajectory.npz", allow_pickle=False) as fresh,
    ):
        assert set(expected.files) == {"accepted_times", *model.STATE_TYPE._fields}
        replay.exact((fresh[k] for k in expected.files), (expected[k] for k in expected.files))
    evidence(
        "replay",
        dict(
            status="passed",
            backend=BACKEND,
            comparison="bitwise",
            phases=reports,
            state_fields=list(model.STATE_TYPE._fields),
            disk=True,
            fresh_process=True,
            terminal=True,
            future_regeneration_and_water_branch=True,
            changed_windows=True,
            complete_layout_and_clock=True,
            fresh_complete_history=True,
            sequential_workers=True,
            artifact_root=str(tmp_path),
            arrays_sha256=artifacts(tmp_path),
        ),
    )


def test_independent_world_partition_reorder_and_restart(tmp_path):
    report = worker(tmp_path, "worlds")
    assert report["status"] == "passed" and report["backend"] == BACKEND
    assert report["state_fields"] == list(model.STATE_TYPE._fields)
    assert len(report["state_fields"]) == 28
    for key in (
        "scalar",
        "partitions",
        "reordered",
        "disk",
        "terminal_world_retained",
        "changed_windows",
    ):
        assert report[key]
    assert set(report["world_ids"]) == set(replay.WORLD_ARMS)
    assert len(set(report["independent_restart_times"].values())) == 2
    evidence(
        "worlds",
        report
        | dict(
            artifact_root=str(tmp_path),
            arrays_sha256=artifacts(tmp_path),
        ),
    )


def test_execution_host_contracts():
    rows = []
    for backend in ("cpu", "gpu"):
        for arm in ("release", "coupled", "supply_off"):
            raw = fixtures.definition(arm, backend=backend, padded=True)
            spec = parse_spec(raw)
            state, layout = model.initial_values(spec)
            times = timeline(spec)
            controls = control_values(spec, times)
            assert len(state) == len(model.STATE_TYPE._fields) == 28
            assert len(layout) == len(model.LAYOUT_TYPE._fields)
            assert all(np.asarray(v).dtype == np.float64 for v in state)
            assert spec.execution.backend == backend
            assert controls._fields == (
                "membrane",
                "junction",
                "channel",
                "pump",
                "regeneration",
                "water",
            )
            assert controls.regeneration.shape == (len(times), spec.execution.regeneration_capacity)
            assert not np.any(controls.regeneration[:, len(spec.model.regeneration_ports) :])
            if arm == "release":
                event_times = {
                    entry["time"]
                    for family in (
                        "regeneration_controls",
                        "channel_controls",
                        "pump_controls",
                        "water_controls",
                    )
                    for group in raw["experiment"][family]
                    for entry in group["schedule"]
                }
                assert len(event_times) > 3
                assert all(time in times for time in event_times)
            serialized = spec.to_dict()
            assert {
                patch["pump"]["metabolism"]["kind"]
                for patch in serialized["model"]["membranes"]
                if patch["pump"]
            } == {"finite_energy_pool@1"}
            assert serialized["model"]["energy_pools"]
            assert parse_spec(serialized) == spec
            rows.append(dict(arm=arm, configured_backend=backend, accepted_steps=len(times) - 1))
    evidence(
        "host-contracts",
        dict(
            status="passed",
            scope="Host definition/grid/layout checks; no trajectory or device launch",
            state_fields=list(model.STATE_TYPE._fields),
            cases=rows,
        ),
    )


def test_execution_history_capture_retains_complete_fields(tmp_path):
    spec = parse_spec(fixtures.definition("release", backend="cpu", padded=True))
    state, _ = model.initial_values(spec)
    history = model.STATE_TYPE(*(np.stack((v, v)) for v in state))
    times = np.array([0.0, replay.CHECKPOINT_TIME])
    path = tmp_path / "host_capture.npz"
    replay.save_history(path, times, history)
    changed = history._replace(pool_volume_work_pJ=np.ones_like(history.pool_volume_work_pJ))
    with pytest.raises(AssertionError):
        replay.exact(history, changed)
    with np.load(path, allow_pickle=False) as saved:
        assert set(saved.files) == {"accepted_times", *model.STATE_TYPE._fields}
        replay.exact((saved["accepted_times"],), (times,))
        replay.exact((saved[k] for k in model.STATE_TYPE._fields), history)
    evidence(
        "capture-contract",
        dict(
            status="passed",
            scope="Synthetic host buffers; no integrated trajectory",
            retained_after_failed_comparison=True,
            state_fields=list(model.STATE_TYPE._fields),
            artifact_root=str(tmp_path),
            arrays_sha256=artifacts(tmp_path),
        ),
    )


def test_regeneration_controls_keep_their_clock_and_padding():
    raw = fixtures.definition("release", backend="cpu", padded=True)
    spec = parse_spec(raw)
    groups = raw["experiment"]["regeneration_controls"]
    events = {row["time"] for group in groups for row in group["schedule"]}
    times = np.array(sorted({0.0, *events, *(np.nextafter(t, 0.0) for t in events if t > 0.0)}))
    controls = control_values(spec, times)
    by_id = {group["regeneration_id"]: group["schedule"] for group in groups}
    expected = np.zeros((len(times), spec.execution.regeneration_capacity))
    for slot, port in enumerate(spec.model.regeneration_ports):
        schedule = by_id[port.id]
        for index, time in enumerate(times):
            expected[index, slot] = next(
                row["availability"] for row in reversed(schedule) if row["time"] <= time
            )
    replay.exact((controls.regeneration,), (expected,))
    assert set(events) <= set(timeline(spec))

    # No external regeneration port is a valid finite, consuming energy system.
    raw["model"]["regeneration_ports"] = []
    raw["experiment"]["regeneration_controls"] = []
    raw["execution"]["regeneration_capacity"] = 0
    closed = parse_spec(raw)
    closed_controls = control_values(closed, times)
    assert closed_controls.regeneration.shape == (len(times), 0)
    assert control_values(closed, np.array([])).regeneration.shape == (0, 0)
    assert parse_spec(closed.to_dict()) == closed
    evidence(
        "regeneration-clock",
        dict(
            status="passed",
            right_continuous=True,
            padded=True,
            absent_ports=True,
            event_times=sorted(events),
            scope="Host schedules only; no device trajectory",
        ),
    )


def test_batch_rejects_mismatched_regeneration_capacity():
    original = parse_spec(fixtures.definition("coupled", backend="cpu", padded=True))
    changed = replace(
        original,
        execution=replace(
            original.execution,
            regeneration_capacity=original.execution.regeneration_capacity + 1,
        ),
    )
    batch = BatchSpec((WorldSpec(101, original), WorldSpec(707, changed)), 2, 128, 2**29)
    with pytest.raises(ConfigError, match="equal regeneration_capacity"):
        parse_batch(batch.to_dict())


def test_execution_rejects_incomplete_energy_checkpoint(tmp_path):
    spec = parse_spec(fixtures.definition("release", backend="cpu", padded=True))
    state, layout = model.initial_values(spec)
    checkpoint = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    complete = tmp_path / "complete"
    write_snapshot(complete, spec, checkpoint)
    loaded = load_snapshot(complete)
    replay.exact_checkpoint(loaded.checkpoint, checkpoint)
    assert loaded.spec == spec
    for name in ("energy_amount_increment_fmol", *replay.REGENERATION_LEDGERS, *model.EXTRA_AXES):
        incomplete = tmp_path / name
        shutil.copytree(complete, incomplete)
        path = incomplete / "state.npz"
        with np.load(path, allow_pickle=False) as saved:
            arrays = {k: saved[k] for k in saved.files if k != name}
        np.savez(path, **arrays)
        manifest_path = incomplete / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["state_sha256"] = replay.digest(path)
        del manifest["manifest_sha256"]
        manifest["manifest_sha256"] = digest(manifest)
        manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        with pytest.raises(ConfigError, match="Invalid checkpoint state fields"):
            load_snapshot(incomplete)
    evidence(
        "checkpoint-contract",
        dict(
            status="passed",
            missing_fields_rejected=[
                "energy_amount_increment_fmol",
                *replay.REGENERATION_LEDGERS,
                *model.EXTRA_AXES,
            ],
            complete_initial_checkpoint=True,
            scope="Initial host state serialization; integrated replay remains separate",
            state_fields=list(model.STATE_TYPE._fields),
            artifact_root=str(tmp_path),
            arrays_sha256=artifacts(tmp_path),
        ),
    )


def test_one_to_sixteen_gpu_planning_preserves_energy_worlds(tmp_path):
    # Representative plans cover one GPU, one four-GPU node and the 16-GPU
    # target. Generic placement already tests intermediate counts; repeating
    # expensive full biological schema validation adds no new placement case.
    # Scheduled release is covered by the execution/replay contracts; planning
    # uses two constant-control arms to avoid repeating event-stage field solves.
    raw = experiment("ionic", backend="gpu", worlds=8, width=1)
    raw["arms"][0]["id"] = "coupled"
    raw["arms"][0]["definition"]["simulation"] = fixtures.definition(
        "coupled", backend="gpu", padded=True
    )
    second = deepcopy(raw["arms"][0])
    second["id"] = "supply_off"
    second["definition"]["simulation"] = fixtures.definition(
        "supply_off", backend="gpu", padded=True
    )
    raw["arms"].append(second)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    original = deepcopy(raw)
    replay.write_json(tmp_path / "planning_inputs.json", raw)
    baseline = plan(raw, 1)
    plans = {}
    for gpus in (1, 4, 16):
        actual = plan(raw, gpus)
        name = f"local-{gpus:02d}.json"
        replay.write_json(tmp_path / name, actual)
        plans[name] = replay.digest(tmp_path / name)
        assert actual["tasks"] == baseline["tasks"]
        assert actual["allocated_gpus"] == gpus
    for nodes in (1, 4):
        actual = jupiter_plan(raw, nodes)
        name = f"jupiter-{nodes}.json"
        replay.write_json(tmp_path / name, actual)
        plans[name] = replay.digest(tmp_path / name)
        assert actual["tasks"] == baseline["tasks"]
        deployment = actual["deployment"]
        assert actual["allocated_gpus"] == nodes * 4
        assert len(deployment["ranks"]) == nodes * 4
        assert deployment["maximum_target_gpus"] == 16
        assert not deployment["remote_execution_qualified"]
        assert not deployment["interacting_tissue_partitioning"]
        assigned = [t for rank in deployment["ranks"] for t in rank["tasks"]]
        assert len(assigned) == len(set(assigned)) == len(actual["tasks"])
        assert set(assigned) == {t["id"] for t in actual["tasks"]}
    expected = {a["id"]: parse_spec(a["definition"]["simulation"]) for a in raw["arms"]}
    ids, counts = [], dict.fromkeys(expected, 0)
    for task in baseline["tasks"]:
        parsed = parse_definition(task["definition"])
        group = population(parsed)
        assert parsed.simulation == expected[task["arm"]]
        assert group.seed == raw["seed"]
        assert group.recording == "summary"
        counts[task["arm"]] += group.worlds
        ids.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert raw == original
    assert counts == {"coupled": 8, "supply_off": 8}
    assert sorted(ids) == list(range(16))
    evidence(
        "planning",
        dict(
            status="passed",
            scope="Offline planning; remote execution remains unqualified",
            local_gpu_counts=[1, 4, 16],
            jupiter_nodes=[1, 4],
            worlds=16,
            arm_worlds=counts,
            world_ids=sorted(ids),
            registered_seed=raw["seed"],
            state_fields=list(model.STATE_TYPE._fields),
            inputs=original,
            artifact_root=str(tmp_path),
            plan_files_sha256=plans,
        ),
    )
