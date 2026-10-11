"""Short real scheduler interruption/resume test; never a utilization benchmark."""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CELLS_TEST_GPU") != "1", reason="explicit CUDA test"
)
ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("family", ["paper", "finite"])
def test_two_gpu_workers_and_measured_balance_command(tmp_path, family):
    if family == "finite":
        from tests.unit.test_pool_ensemble import experiment
    else:
        from tests.unit.test_ensemble import experiment

    definition = experiment()
    definition["execution"].update(workers_per_gpu=2, worker_threads=1)
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(definition))
    output = tmp_path / "run"
    command = [sys.executable, "-B", "-m", "cells.ensemble"]
    subprocess.run(
        command
        + ["run", str(config), "--output", str(output), "--devices", "0", "--allocated-gpus", "1"],
        capture_output=True,
        text=True,
        check=True,
        timeout=35,
    )
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "completed"
    assert result["completed_worlds"] == (32 if family == "finite" else 64)
    assert len(result["result_records"]) == (4 if family == "finite" else 8)
    assert len(list(output.glob("worker-*-started.json"))) == 2
    assert len(result["full_job_utilization"]["per_gpu_mean_pct"]) == 1
    assert result["throughput"]["worlds_per_allocated_gpu_hour"] == pytest.approx(
        result["completed_worlds"] / result["allocated_gpu_hours"]
    )
    tuned = tmp_path / "balanced.json"
    subprocess.run(
        command
        + [
            "balance",
            str(config),
            "--profile",
            str(output / "cost-profile.json"),
            "--output",
            str(tuned),
            "--allocated-gpus",
            "1",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    assert [a["worlds"] for a in json.loads(tuned.read_text())["arms"]] == (
        [16, 16] if family == "finite" else [32, 32]
    )


def wait_for(path, seconds=35):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists():
            return json.loads(path.read_text())
        if (path.parent / "failure.json").exists():
            raise AssertionError((path.parent / "failure.json").read_text())
        time.sleep(0.05)
    raise AssertionError(f"Bounded integration test timed out waiting for {path}")


@pytest.mark.parametrize("family", ["paper", "finite"])
def test_gpu_scheduler_signal_checkpoint_resume_and_exact_result(tmp_path, family):
    from cells.assembly.graph import OPEN_CHAIN

    if family == "finite":
        from cells.assembly_pool.engine import run
        from cells.assembly_pool.io import load_checkpoint
    else:
        from cells.assembly.engine import run
        from cells.assembly.io import load_checkpoint

    definition = {
        "kind": "assembly_ensemble@1",
        "seed": 478,
        "arms": [
            {
                "id": "open",
                "definition": {
                    "initial_nodes": list(OPEN_CHAIN),
                    "free_trimer_M": 5.6e-9,
                    "end_time_s": 3000.0,
                    "event_chunk_size": 8,
                    "max_events_per_world": 200000,
                },
                "worlds": 256,
                "batch_worlds": 256,
                "seconds_per_world": None,
            }
        ],
        "execution": {
            "max_wall_seconds": 120,
            "max_output_bytes": 256 * 1024**2,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 2,
        },
    }
    if family == "finite":
        definition["kind"] = "finite_bond_ensemble@1"
        arm = definition["arms"][0]["definition"]
        arm.pop("free_trimer_M")
        arm["model"] = "finite_bond_assembly@1"
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(definition))

    def launch(command, source, destination):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "cells.ensemble",
                command,
                str(source),
                "--output",
                str(destination),
                "--devices",
                "0",
                "--allocated-gpus",
                "1",
                "--detach",
            ],
            env=environment,
            text=True,
            capture_output=True,
            check=True,
            timeout=15,
        )
        return json.loads(result.stdout)

    first, resumed = tmp_path / "first", tmp_path / "resumed"
    receipt = launch("run", config, first)
    wait_for(first / "tasks/task-00000/status.json")
    os.kill(receipt["pid"], signal.SIGUSR1)
    paused = wait_for(first / "paused.json")
    assert paused["status"] == "paused"
    assert (first / "tasks/task-00000/checkpoint-paused/manifest.json").exists()
    launch("resume", first, resumed)
    complete = wait_for(resumed / "completion.json", seconds=45)
    assert complete["status"] == "completed"
    final = json.loads((resumed / "result.json").read_text())
    assert final["completed_worlds"] == final["registered_worlds"] == 256
    assert final["allocated_gpu_hours"] > 0
    assert final["throughput"]["worlds_per_allocated_gpu_hour"] is None
    spec, saved, _ = load_checkpoint(resumed / "tasks/task-00000/checkpoint")
    fresh, _ = run(spec, backend="gpu")
    for actual, expected in zip(saved, fresh, strict=True):
        np.testing.assert_array_equal(actual, expected)
