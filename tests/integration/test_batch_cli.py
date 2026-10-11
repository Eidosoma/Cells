"""Fresh-process batch ownership and scalar-compatible child artifacts."""

import json
import os
import subprocess
import sys

import numpy as np

from cells.io import _write_json
from tests.batch_fixtures import ROOT, synthetic_pair


def test_batch_cli_validate_run_resume_branch_and_refusal(tmp_path):
    config = tmp_path / "batch.json"
    spec = synthetic_pair()
    _write_json(config, spec.to_dict())

    def cli(*args, ok=True):
        completed = subprocess.run(
            [sys.executable, "-W", "error", "-m", "cells", "batch", *map(str, args)],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert completed.returncode == (0 if ok else 2), completed.stdout + completed.stderr
        return json.loads(completed.stdout) if ok else completed.stderr

    assert cli("validate", config)["worlds"] == 2
    assert cli("run", config, "--output", tmp_path / "fresh", "--checkpoint-at", 0.5)[
        "world_ids"
    ] == [10, 11]
    saved = tmp_path / "fresh/snapshots/checkpoint-000000"
    cli("resume", saved, "--output", tmp_path / "resumed")
    branch = spec.to_dict()
    branch["worlds"][0]["simulation"]["experiment"]["source"]["schedule"].append(
        {"time": 0.5, "rate": 0}
    )
    _write_json(tmp_path / "branch.json", branch)
    cli("branch", saved, tmp_path / "branch.json", "--output", tmp_path / "branched")
    for identity in (10, 11):
        with (
            np.load(tmp_path / f"fresh/worlds/world-{identity}/trajectory.npz") as a,
            np.load(tmp_path / f"resumed/worlds/world-{identity}/trajectory.npz") as b,
        ):
            at = np.flatnonzero(a["accepted_times"] == 0.5)[0]
            for key in ("amount", "supplied", "degraded"):
                np.testing.assert_array_equal(a[key][at:], b[key])
    assert "already exists" in cli("run", config, "--output", tmp_path / "fresh", ok=False)
    assert "accepted time" in cli(
        "run", config, "--output", tmp_path / "invalid", "--checkpoint-at", 0.137, ok=False
    )
    assert not (tmp_path / "invalid").exists()
