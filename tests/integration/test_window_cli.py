import json

import numpy as np

from tests.batch_fixtures import synthetic_pair
from tests.integration.test_cli import cli, given_inputs, recorded_inputs


def test_windowed_cli_run_resume_branch_validate_and_refusals(tmp_path):
    data = synthetic_pair().worlds[0].simulation.to_dict()
    config = tmp_path / "config.json"
    config.write_text(json.dumps(data))
    validated = cli("windowed", "validate", config, "--window-steps", 2)
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["windows"] > 1
    root = tmp_path / "fresh"
    inputs, value = given_inputs(tmp_path, validated.stdout)
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
        "--inputs",
        inputs,
    )
    assert fresh.returncode == 0, fresh.stderr
    assert recorded_inputs(root) == value
    cp = root / "snapshots/step-0000000011"
    resumed = tmp_path / "resumed"
    result = cli(
        "windowed", "resume", cp, "--output", resumed, "--window-steps", 3, "--recording", "full"
    )
    assert result.returncode == 0, result.stderr
    assert recorded_inputs(resumed) is None
    for field in ("amount", "transferred", "converted"):
        with (
            np.load(root / "checkpoint_final/state.npz") as a,
            np.load(resumed / "checkpoint_final/state.npz") as b,
        ):
            np.testing.assert_array_equal(a[field], b[field])
    data["experiment"]["contact"]["schedule"].append({"time": 0.5, "open_fractions": [0]})
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
    final = json.loads(branch.stdout)["final_signed_transferred_fmol"]
    with np.load(cp / "state.npz") as saved:  # Closed from its checkpoint, it moves nothing.
        np.testing.assert_array_equal(final, saved["transferred"])
    assert json.loads(fresh.stdout)["final_signed_transferred_fmol"] != final
    duplicate = cli("windowed", "run", config, "--output", root)
    assert duplicate.returncode == 2 and "already exists" in duplicate.stderr
    invalid = cli("windowed", "run", config, "--output", tmp_path / "bad", "--window-steps", 0)
    assert invalid.returncode == 2 and not (tmp_path / "bad").exists()
