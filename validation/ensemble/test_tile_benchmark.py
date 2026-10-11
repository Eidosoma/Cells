"""Full-task identity, retained scalar anchors and failure isolation for the pair."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from validation.ensemble import cluster_matrix, parallel_cluster
from validation.ensemble import tile_benchmark as pair
from validation.ensemble.test_parallel_cluster import physical_spec


def origin():
    raw = cluster_matrix.arm_definition(physical_spec().to_dict())
    return {
        "definition": {
            "kind": "assembly_cluster_ensemble@1",
            "seed": 20260925,
            "arms": [
                {
                    "id": "dynamic",
                    "definition": raw,
                    "worlds": 128,
                    "batch_worlds": 32,
                    "seconds_per_world": None,
                }
            ],
            "execution": {
                "max_wall_seconds": 1800,
                "max_output_bytes": 2 * 1024**3,
                "target_gpu_utilization_pct": 70,
                "worker_threads": 1,
                "workers_per_gpu": 2,
            },
        }
    }


def test_paired_definition_keeps_physics_streams_and_full_unique_worlds():
    original = origin()
    before = original["definition"].copy()
    definition, plan = pair.definition_for(original)
    assert original["definition"] == before
    assert definition["seed"] == original["definition"]["seed"]
    assert plan["worlds"] == 1024 and plan["worker_processes"] == 2
    ids = []
    for task in plan["tasks"]:
        spec = parallel_cluster.parse_spec(task["definition"])
        assert spec.pool.worlds == 64
        assert all(b.pool.seed == (definition["seed"] + b.stream_id) % 2**32 for b in spec.pools)
        assert (
            cluster_matrix.arm_definition(spec.to_dict())
            == original["definition"]["arms"][0]["definition"]
        )
        ids.extend(range(spec.pool.world_id_start, spec.pool.world_id_start + 64))
    assert sorted(ids) == list(range(1024))
    assert [t["arm"] for t in plan["tasks"]] == ["dynamic-a", "dynamic-b"] * 8


@pytest.mark.parametrize("change", ["none", "signed_zero", "dtype", "shape", "missing"])
def test_regrouped_anchor_keeps_every_bit_and_field(change):
    expected = {"energy": np.array([[0.0], [1.0]]), "events": np.array([2, 3], np.uint32)}
    actual = {k: v.copy() for k, v in expected.items()}
    if change == "signed_zero":
        actual["energy"][0] = -0.0
    elif change == "dtype":
        actual["events"] = actual["events"].astype(np.int32)
    elif change == "shape":
        actual["energy"] = actual["energy"].ravel()
    elif change == "missing":
        del actual["events"]
    if change == "none":
        assert pair.compare_arrays(expected, actual) == 4
    else:
        with pytest.raises(ValueError, match="Checkpoint"):
            pair.compare_arrays(expected, actual)


def endpoint_fixture(tmp_path, monkeypatch):
    _, plan = pair.definition_for(origin())
    parent = tmp_path / "scalar"
    parent.mkdir()
    anchors = []
    for first, count in ((0, 16), (16, 16), (32, 16), (48, 16), (64, 32), (96, 32)):
        folder = parent / str(first)
        folder.mkdir()
        values = np.repeat(np.arange(first, first + count, dtype=float)[:, None], 412, axis=1)
        np.savez(folder / "state.npz", state=values)
        anchors.append(
            {"checkpoint": str(folder), "world_id_start": first, "worlds": count, "slice_start": 0}
        )

    def slices(parent_path, spec):
        assert parent_path == parent
        return [
            a
            for a in anchors
            if spec.pool.world_id_start
            <= a["world_id_start"]
            < spec.pool.world_id_start + spec.pool.worlds
        ]

    monkeypatch.setattr(
        pair.profile,
        "candidate_helpers",
        lambda: (
            SimpleNamespace(
                parse_spec=parallel_cluster.parse_spec,
                qualified_slices=slices,
            ),
            {},
        ),
    )
    monkeypatch.setattr(pair.profile, "authenticate_parent", lambda path: ({}, {"plan": plan}))
    monkeypatch.setattr(pair, "completed_phase", lambda root, width: {})
    candidates = {}
    for width in pair.WIDTHS:
        marker = {
            "variant": "tested",
            "tile_width": width,
            "result_sha256": "qualification",
            "helpers_sha256": {"kernel": "tested"},
        }
        candidates[str(width)] = marker
        for task in plan["tasks"]:
            folder = tmp_path / f"width-{width}/campaign/tasks" / task["id"]
            checkpoint = folder / "checkpoint"
            checkpoint.mkdir(parents=True)
            first = task["definition"]["pools"][0]["pool"]["world_id_start"]
            values = np.repeat(np.arange(first, first + 64, dtype=float)[:, None], 412, axis=1)
            np.savez(checkpoint / "state.npz", state=values)
            pair.cli.write(
                checkpoint / "manifest.json",
                {
                    "provenance": {
                        "execution": {"experimental_candidate": marker},
                        "parent": None,
                    }
                },
            )
            pair.cli.write(folder / "result.json", {"experimental_candidate": marker})
    pair.cli.write(tmp_path / "plan.json", plan)
    return {"parent": str(parent), "qualifications": candidates}, plan


@pytest.mark.parametrize(
    "width,change",
    [
        (32, "none"),
        (64, "none"),
        (32, "anchor"),
        (64, "anchor"),
        (64, "later_world"),
        (64, "provenance"),
    ],
)
def test_endpoints_compare_regrouped_scalar_anchors_and_all_new_worlds(
    tmp_path, monkeypatch, width, change
):
    record, plan = endpoint_fixture(tmp_path, monkeypatch)
    if change != "none":
        task = plan["tasks"][4 if change == "later_world" else 0]
        checkpoint = tmp_path / f"width-{width}/campaign/tasks" / task["id"] / "checkpoint"
        if change == "provenance":
            manifest = pair.cli.read(checkpoint / "manifest.json")
            manifest["provenance"]["execution"]["experimental_candidate"]["tile_width"] = 16
            (checkpoint / "manifest.json").write_text(pair.json.dumps(manifest))
        else:
            with np.load(checkpoint / "state.npz", allow_pickle=False) as data:
                values = data["state"].copy()
            values[0, 0] = np.nextafter(values[0, 0], np.inf)
            np.savez(checkpoint / "state.npz", state=values)
        with pytest.raises(ValueError, match="Checkpoint|provenance"):
            pair.verify_endpoints(tmp_path, width, record)
    else:
        checked = pair.verify_endpoints(tmp_path, width, record)
        assert sum(checked["scalar_anchor_scalars"].values()) == 52736
        assert checked["matched_width_worlds"] == (1024 if width == 64 else 0)
        assert sum(checked["matched_width_scalars"].values()) == (421888 if width == 64 else 0)


def test_controller_does_not_launch_second_width_after_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(pair, "authenticate", lambda root: {"python": "python"})
    process = Mock()
    process.wait.return_value = 1
    popen = Mock(return_value=process)
    monkeypatch.setattr(pair.subprocess, "Popen", popen)
    with pytest.raises(ValueError, match="phase failed"):
        pair.controller(tmp_path)
    popen.assert_called_once()
    assert (tmp_path / "failure.json").exists()
    assert not (tmp_path / "width-64").exists()
    assert not (tmp_path / "completion.json").exists()


def test_phase_uses_ordinary_observed_worker_and_cleans_counters_on_failure(tmp_path, monkeypatch):
    from cells.ensemble import worker

    folder = tmp_path / "width-32"
    folder.mkdir()
    marker = {
        "variant": "tested",
        "tile_width": 32,
        "result_sha256": "qualification",
        "helpers_sha256": {},
    }
    record = {
        "memory_limits": {"tree_rss_bytes": pair.TREE_RSS, "available_memory_bytes": pair.RESERVE},
        "qualifications": {"32": marker},
        "gpu_counters": {},
    }
    monkeypatch.setattr(pair, "authenticate", lambda root: record)
    monkeypatch.setattr(pair.profile, "memory_available", lambda: 32 * 1024**3)
    counters = Mock()
    monkeypatch.setattr(pair.profile.gpu_counters, "CounterMonitor", lambda *a: counters)

    def register(args):
        assert args.detach is False and args.allocated_gpus == 1
        assert worker.worker.func is pair.profile.profile_worker
        assert worker.worker.keywords == {"trace_enabled": False, "experimental_candidate": marker}
        return {"status": "failed"}

    original = worker.worker
    monkeypatch.setattr(pair.cli, "register", register)
    with pytest.raises(ValueError, match="campaign did not complete"):
        pair.phase(tmp_path, 32)
    counters.start.assert_called_once()
    counters.finish.assert_called()
    assert worker.worker is original
    assert (folder / "failure.json").exists() and not (folder / "completion.json").exists()


@pytest.mark.parametrize("coverage", [True, False])
def test_phase_completion_requires_counter_coverage_and_binds_results(
    tmp_path, monkeypatch, coverage
):
    folder = tmp_path / "width-32"
    folder.mkdir()
    pair.cli.write(tmp_path / "registration.json", {})
    record = {
        "memory_limits": {"tree_rss_bytes": pair.TREE_RSS, "available_memory_bytes": pair.RESERVE},
        "qualifications": {"32": {"tile_width": 32}},
        "gpu_counters": {},
    }
    monkeypatch.setattr(pair, "authenticate", lambda root: record)
    monkeypatch.setattr(pair.profile, "memory_available", lambda: 32 * 1024**3)
    counter = Mock()
    counter.rows = []
    monkeypatch.setattr(pair.profile.gpu_counters, "CounterMonitor", lambda *a: counter)
    monkeypatch.setattr(
        pair.profile.gpu_counters, "summarize", lambda *a: {"coverage_pass": coverage}
    )
    monitor = Mock()
    monitor.violation = None
    monitor.thread.is_alive.return_value = False
    monkeypatch.setattr(pair.profile, "ResourceMonitor", lambda *a, **kw: monitor)
    (folder / "host-resources.jsonl").write_text(
        pair.json.dumps(
            {
                "tree_rss_bytes": 100,
                "available_memory_bytes": pair.TREE_RSS + pair.RESERVE,
            }
        )
        + "\n"
    )
    monkeypatch.setattr(pair, "verify_endpoints", lambda *a: {"scalar_anchor_worlds": 128})

    def register(args):
        campaign = args.output
        campaign.mkdir()
        results = {}
        for slot in range(2):
            task = f"task-{slot}"
            path = campaign / (task + ".json")
            pair.cli.write(
                path,
                {"task": task, "arm": f"arm-{slot}", "wall_end": 13 + slot, "compile_seconds": 1.0},
            )
            results[task] = {"path": str(path)}
            pair.cli.write(campaign / f"worker-{slot}-warm.json", {"time": 11})
            pair.cli.write(campaign / f"worker-{slot}-finished.json", {"time": 13 + slot})
            directory = campaign / f"worker-{slot}-profile"
            directory.mkdir()
            pair.cli.write(directory / "resources.json", {"cpu_seconds": 2})
        result = {
            "status": "completed",
            "started_time": 10,
            "finished_time": 14,
            "elapsed_seconds": 4,
            "result_records": results,
            "throughput": {},
            "full_job_utilization": {},
            "after_all_workers_warmed": {},
        }
        pair.cli.write(campaign / "result.json", result)
        return result

    monkeypatch.setattr(pair.cli, "register", register)
    if coverage:
        pair.phase(tmp_path, 32)
        result = pair.completed_phase(tmp_path, 32)
        assert result["worker_finish_gap_seconds"] == 1
        assert result["arm_finish_gap_seconds"] == 1
        assert result["compile_seconds_by_task"] == {"task-0": 1, "task-1": 1}
        assert result["endpoint_comparisons"]["scalar_anchor_worlds"] == 128
        assert not (folder / "failure.json").exists()
    else:
        with pytest.raises(ValueError, match="coverage"):
            pair.phase(tmp_path, 32)
        assert not (folder / "completion.json").exists()
        assert (folder / "failure.json").exists()
    monitor.finish.assert_called_once()
    counter.finish.assert_called()
