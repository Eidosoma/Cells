import json

import numpy as np

from tests.batch_fixtures import synthetic_pair
from tests.integration.test_cli import cli


def test_windowed_cli_run_resume_branch_validate_and_refusals(tmp_path):
    data = synthetic_pair().worlds[0].simulation.to_dict()
    config = tmp_path / "config.json"
    config.write_text(json.dumps(data))
    validated = cli("windowed", "validate", config, "--window-steps", 2)
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["windows"] > 1
    root = tmp_path / "fresh"
    fresh = cli(
        "windowed",
        "run",
        config,
        "--output",
        root,
        "--window-steps",
        2,
        "--recording",
        "checkpoints",
        "--checkpoint-at",
        0.5,
    )
    assert fresh.returncode == 0, fresh.stderr
    cp = root / "snapshots/step-0000000011"
    resumed = tmp_path / "resumed"
    result = cli(
        "windowed", "resume", cp, "--output", resumed, "--window-steps", 3, "--recording", "full"
    )
    assert result.returncode == 0, result.stderr
    for field in ("amount", "supplied", "degraded"):
        with (
            np.load(root / "checkpoint_final/state.npz") as a,
            np.load(resumed / "checkpoint_final/state.npz") as b,
        ):
            np.testing.assert_array_equal(a[field], b[field])
    data["experiment"]["source"]["schedule"].append({"time": 0.5, "rate": 4.0})
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(data))
    branch = cli(
        "windowed",
        "branch",
        cp,
        changed,
        "--output",
        tmp_path / "branch",
        "--recording",
        "observations",
        "--window-steps",
        7,
    )
    assert branch.returncode == 0, branch.stderr
    assert (
        json.loads(branch.stdout)["final_amount_fmol"]
        > json.loads(fresh.stdout)["final_amount_fmol"]
    )
    duplicate = cli("windowed", "run", config, "--output", root)
    assert duplicate.returncode == 2 and "already exists" in duplicate.stderr
    invalid = cli("windowed", "run", config, "--output", tmp_path / "bad", "--window-steps", 0)
    assert invalid.returncode == 2 and not (tmp_path / "bad").exists()
