"""Real shared GPU queue keeps complete interacting worlds and separate cell owners."""

import json
import os
import subprocess
import sys

import pytest

from cells.assembly.io import digest
from tests.unit.test_assembly_cluster import ensemble_definition

pytestmark = pytest.mark.skipif(
    os.environ.get("CELLS_TEST_GPU") != "1", reason="explicit CUDA qualification"
)


def test_two_workers_complete_cluster_worlds(tmp_path):
    definition = ensemble_definition()
    definition["execution"]["workers_per_gpu"] = 2
    definition["execution"]["max_wall_seconds"] = 900
    definition["execution"]["max_output_bytes"] = 512 * 1024**2
    definition["arms"][0].update(worlds=4, batch_worlds=2)
    definition["arms"][0]["definition"]["ionic"]["execution"]["backend"] = "gpu"
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(definition))
    output = tmp_path / "run"
    command = [
        sys.executable,
        "-B",
        "-m",
        "cells.ensemble",
        "run",
        str(config),
        "--output",
        str(output),
        "--devices",
        "0",
        "--allocated-gpus",
        "1",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=960)
    (tmp_path / "queue.stdout.log").write_text(result.stdout)
    (tmp_path / "queue.stderr.log").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "completed" and report["completed_worlds"] == 4
    assert len(report["result_records"]) == 2
    assert len(list(output.glob("worker-*-started.json"))) == 2
    assert report["throughput"]["world_steps_per_allocated_gpu_hour"] > 0
    assert report["throughput"]["events_per_allocated_gpu_hour"] > 0
    arm = report["arms"]["cluster"]
    assert arm["worlds"] == 4 and "completion_probability" not in arm
    assert arm["ionic_accounting"]["max_global_balance_error_fmol"] <= 2e-11
    assert arm["integrated_world_steps"] == 1600
    for name, cell in arm["assembly_cells"].items():
        assert name in ("cell_0", "cell_1")
        assert cell["worlds"] == 4 and sum(cell["final_size_histogram"]) == 4
        assert cell["material_residual_trimers"] == 0
    for path in (output / "tasks").glob("task-*/checkpoint"):
        manifest = json.loads((path / "manifest.json").read_text())
        assert manifest["format"] == "cells_assembly_cluster_checkpoint@1"
        assert manifest["state_sha256"] == digest(path / "state.npz")
    evidence = os.environ.get("CELLS_CLUSTER_EVIDENCE")
    if evidence:
        from pathlib import Path

        from cells.assembly.io import write_json

        write_json(
            Path(evidence) / "gpu/queue.json",
            {
                "status": "passed",
                "result_path": str(output / "result.json"),
                "result_sha256": digest(output / "result.json"),
                "worlds": 4,
                "workers": 2,
                "throughput": report["throughput"],
                "utilization": report["full_job_utilization"],
                "scope": "Correctness workload; no minimum utilization or multi-GPU scaling claim",
            },
        )
