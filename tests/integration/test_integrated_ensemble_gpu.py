"""Real GPU scheduling and exact resume for both integrated model families."""

import json
import os
import signal
import subprocess
import sys

import numpy as np
import pytest

from tests.integration.test_ensemble_gpu import wait_for
from tests.unit.test_integrated_ensemble import experiment

pytestmark = pytest.mark.skipif(
    os.environ.get("CELLS_TEST_GPU") != "1", reason="explicit CUDA test"
)


def invoke(arguments):
    result = subprocess.run(
        [sys.executable, "-B", "-m", "cells.ensemble", *map(str, arguments)],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("family", ["ionic", "assembly_cell"])
def test_two_workers_complete_integrated_worlds(tmp_path, family):
    definition = experiment(family, backend="gpu", worlds=4, width=2)
    definition["execution"]["workers_per_gpu"] = 2
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(definition))
    output = tmp_path / "run"
    result = invoke(["run", config, "--output", output, "--devices", "0", "--allocated-gpus", "1"])
    assert result["status"] == "completed" and result["completed_worlds"] == 4
    assert len(result["result_records"]) == 2
    assert len(list(output.glob("worker-*-started.json"))) == 2
    assert result["throughput"]["world_steps_per_allocated_gpu_hour"] > 0
    arm = result["arms"]["active"]
    assert arm["ionic_accounting"]["max_global_balance_error_fmol"] <= 2e-11
    if family == "ionic":
        assert "completion_probability" not in arm
        assert result["throughput"]["events_per_allocated_gpu_hour"] is None
    else:
        assert arm["material_residual_trimers"] == 0
        assert arm["availability_exposure_total_s"] >= 0
    balanced = tmp_path / "balanced.json"
    invoke(
        [
            "balance",
            config,
            "--profile",
            output / "cost-profile.json",
            "--output",
            balanced,
            "--allocated-gpus",
            "1",
            "--target-task-seconds",
            "1",
        ]
    )
    assert json.loads(balanced.read_text())["arms"][0]["worlds"] == 4


@pytest.mark.parametrize("family", ["ionic", "assembly_cell"])
def test_signal_pause_and_exact_integrated_resume(tmp_path, family):
    from cells.ensemble.families import failure_state, runtime_for

    definition = experiment(family, backend="gpu", worlds=2, width=2, end=0.2)
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(definition))
    first, second = tmp_path / "first", tmp_path / "second"
    launch = invoke(
        ["run", config, "--output", first, "--devices", "0", "--allocated-gpus", "1", "--detach"]
    )
    wait_for(first / "tasks/task-00000/status.json", seconds=120)
    os.kill(launch["pid"], signal.SIGUSR1)
    wait_for(first / "paused.json", seconds=120)
    invoke(
        ["resume", first, "--output", second, "--devices", "0", "--allocated-gpus", "1", "--detach"]
    )
    wait_for(second / "completion.json", seconds=240)
    result = json.loads((second / "result.json").read_text())
    assert result["status"] == "completed" and result["completed_worlds"] == 2
    assert result["throughput"]["worlds_per_allocated_gpu_hour"] is None
    from cells.ensemble.families import parse_definition

    task = json.loads((second / "registration.json").read_text())["plan"]["tasks"][0]
    run, load, _ = runtime_for(parse_definition(task["definition"]))
    spec, saved, _ = load(second / "tasks/task-00000/checkpoint")
    fresh, _ = run(spec, backend="gpu")
    a, b = failure_state(spec, saved), failure_state(spec, fresh)
    for key in a:
        np.testing.assert_array_equal(a[key], b[key])
