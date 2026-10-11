"""Fresh-process source pair uses the ordinary validate/run/resume/branch CLI."""

import json

import numpy as np

from tests.integration.test_cli import cli
from tests.source_pair_fixtures import definition


def test_source_pair_cli_replay_and_independent_branch(tmp_path):
    data = definition()
    data["experiment"].update(end_time=0.03, observation_times=[0, 0.01, 0.02, 0.03])
    config = tmp_path / "pair.json"
    config.write_text(json.dumps(data))
    assert cli("validate", config).returncode == 0
    first = cli("run", config, "--output", tmp_path / "fresh", "--checkpoint-at", 0.01)
    assert first.returncode == 0, first.stderr
    checkpoint = tmp_path / "fresh/snapshots/step-000001"
    resumed = cli("resume", checkpoint, "--output", tmp_path / "resumed")
    assert resumed.returncode == 0, resumed.stderr
    with (
        np.load(tmp_path / "fresh/trajectory.npz") as a,
        np.load(tmp_path / "resumed/trajectory.npz") as b,
    ):
        for key in (
            "ions",
            "regulation",
            "leak_history",
            "pump_history",
            "ion_transferred",
            "local_regulation",
            "mirna_transferred",
        ):
            np.testing.assert_array_equal(a[key][1:], b[key])
    data["experiment"]["contact_controls"][1]["schedule"].append({"time": 0.01, "multiplier": 0})
    config.write_text(json.dumps(data))
    branch = cli("branch", checkpoint, config, "--output", tmp_path / "branch")
    assert branch.returncode == 0, branch.stderr
    assert (
        json.loads(branch.stdout)["final_regulation"]
        != json.loads(first.stdout)["final_regulation"]
    )
    assert cli("run", config, "--output", tmp_path / "fresh").returncode == 2
