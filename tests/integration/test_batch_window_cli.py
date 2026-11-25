import json

import numpy as np

from tests.batch_fixtures import synthetic_pair
from tests.integration.test_cli import cli, given_inputs, recorded_inputs


def test_bounded_cohort_cli_validate_run_resume_branch_and_refusals(tmp_path):
    data = synthetic_pair().to_dict()
    config = tmp_path / "batch.json"
    config.write_text(json.dumps(data))
    validated = cli("batch", "windowed", "validate", config, "--window-steps", 2)
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["rounds"] > 1
    root = tmp_path / "fresh"
    inputs, value = given_inputs(tmp_path, validated.stdout)
    fresh = cli(
        "batch",
        "windowed",
        "run",
        config,
        "--output",
        root,
        "--window-steps",
        2,
        "--recording",
        "checkpoints",
        "--checkpoint-every-windows",
        1,
        "--inputs",
        inputs,
    )
    assert fresh.returncode == 0, fresh.stderr
    assert recorded_inputs(root) == value
    cp = root / "snapshots/round-0000000003"
    resumed = tmp_path / "resumed"
    result = cli(
        "batch",
        "windowed",
        "resume",
        cp,
        "--output",
        resumed,
        "--window-steps",
        3,
        "--recording",
        "full",
    )
    assert result.returncode == 0, result.stderr
    assert recorded_inputs(resumed) is None
    for identity in (10, 11):
        with (
            np.load(root / f"checkpoint_final/world-{identity}/state.npz") as a,
            np.load(resumed / f"checkpoint_final/world-{identity}/state.npz") as b,
        ):
            assert a.files == b.files
            for field in a.files:
                np.testing.assert_array_equal(a[field], b[field])
    child_manifest = json.loads((cp / "world-10/manifest.json").read_text())
    time = child_manifest["clock"]["time"]
    data["worlds"][0]["simulation"]["experiment"]["contact"]["schedule"].append(
        {"time": time, "open_fractions": [0]}
    )
    data["worlds"].reverse()
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(data))
    branch = cli(
        "batch",
        "windowed",
        "branch",
        cp,
        changed,
        "--output",
        tmp_path / "branch",
        "--window-steps",
        7,
    )
    assert branch.returncode == 0, branch.stderr
    got, initial = json.loads(branch.stdout), json.loads(fresh.stdout)
    assert got["world_ids"] == [11, 10]
    # World 10's contact is closed from its checkpoint: it moved what it had moved there. World 11
    # is the fresh run's.
    moved = "final_signed_transferred_fmol"
    with np.load(cp / "world-10/state.npz") as saved:
        np.testing.assert_array_equal(got["world_summaries"]["10"][moved], saved["transferred"])
    assert got["world_summaries"]["10"][moved] != initial["world_summaries"]["10"][moved]
    for key in ("final_amounts_fmol", moved, "final_signed_converted_fmol"):
        assert got["world_summaries"]["11"][key] == initial["world_summaries"]["11"][key]
    for flags in (
        ("--window-steps", 0),
        ("--checkpoint-every-windows", -1),
        ("--checkpoint-at", 0.5),
    ):
        invalid = cli("batch", "windowed", "run", config, "--output", tmp_path / "bad", *flags)
        assert invalid.returncode == 2 and not (tmp_path / "bad").exists()
    duplicate = cli("batch", "windowed", "run", config, "--output", root)
    assert duplicate.returncode == 2 and "already exists" in duplicate.stderr
