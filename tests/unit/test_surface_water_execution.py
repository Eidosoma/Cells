"""Complete water execution contracts; compiled tests run only when coordinated."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.ensemble.families import parse_definition, population
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot
from cells.models import surface_water as model
from tests.unit.test_integrated_ensemble import experiment
from validation.tissue import surface_water_fixtures as fixtures
from validation.tissue import surface_water_replay as replay

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, value):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        (path / ("water-execution-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )


def artifacts(root):
    return {str(p.relative_to(root)): replay.digest(p) for p in sorted(root.rglob("*.npz"))}


def worker(root, phase):
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.tissue.surface_water_replay",
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
            future_water_branch=True,
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
    assert len(report["state_fields"]) == 16
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
        for arm in ("release", "coupled", "sealed"):
            raw = fixtures.definition(arm, backend=backend, padded=True)
            spec = parse_spec(raw)
            state, layout = model.initial_values(spec)
            times = timeline(spec)
            controls = control_values(spec, times)
            assert len(state) == len(model.STATE_TYPE._fields) == 16
            assert len(layout) == len(model.LAYOUT_TYPE._fields)
            assert all(np.asarray(v).dtype == np.float64 for v in state)
            assert spec.execution.backend == backend
            assert controls._fields == ("membrane", "junction", "water")
            assert controls.water.shape == (len(times), spec.execution.membrane_capacity)
            assert not np.any(controls.water[:, len(spec.model.membranes) :])
            if arm == "release":
                assert all(t in times for t in (0.00037, 0.00073, 0.00113, 0.00151))
            assert parse_spec(spec.to_dict()) == spec
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
    changed = history._replace(water_transferred_pL=np.ones_like(history.water_transferred_pL))
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


def test_one_to_sixteen_gpu_planning_preserves_water_worlds(tmp_path):
    raw = experiment("ionic", backend="gpu", worlds=16, width=1)
    raw["arms"][0]["id"] = "release"
    raw["arms"][0]["definition"]["simulation"] = fixtures.definition(
        "release", backend="gpu", padded=True
    )
    second = deepcopy(raw["arms"][0])
    second["id"] = "sealed"
    second["definition"]["simulation"] = fixtures.definition("sealed", backend="gpu", padded=True)
    raw["arms"].append(second)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    original = deepcopy(raw)
    replay.write_json(tmp_path / "planning_inputs.json", raw)
    baseline = plan(raw, 1)
    plans = {}
    for gpus in range(1, 17):
        actual = plan(raw, gpus)
        name = f"local-{gpus:02d}.json"
        replay.write_json(tmp_path / name, actual)
        plans[name] = replay.digest(tmp_path / name)
        assert actual["tasks"] == baseline["tasks"]
        assert actual["allocated_gpus"] == gpus
    for nodes in range(1, 5):
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
    assert counts == {"release": 16, "sealed": 16}
    assert sorted(ids) == list(range(32))
    evidence(
        "planning",
        dict(
            status="passed",
            scope="Offline planning; remote execution remains unqualified",
            local_gpu_counts=list(range(1, 17)),
            jupiter_nodes=[1, 2, 3, 4],
            worlds=32,
            arm_worlds=counts,
            world_ids=sorted(ids),
            registered_seed=raw["seed"],
            state_fields=list(model.STATE_TYPE._fields),
            inputs=original,
            artifact_root=str(tmp_path),
            plan_files_sha256=plans,
        ),
    )
