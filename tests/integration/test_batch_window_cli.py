import json

import numpy as np

from tests.batch_fixtures import synthetic_pair
from tests.integration.test_cli import cli


def test_bounded_cohort_cli_validate_run_resume_branch_and_refusals(tmp_path):
    data = synthetic_pair().to_dict()
    config = tmp_path / "batch.json"
    config.write_text(json.dumps(data))
    validated = cli("batch", "windowed", "validate", config, "--window-steps", 2)
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["rounds"] > 1
    root = tmp_path / "fresh"
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
    )
    assert fresh.returncode == 0, fresh.stderr
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
    data["worlds"][0]["simulation"]["experiment"]["source"]["schedule"].append(
        {"time": time, "rate": 4}
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
    assert (
        got["world_summaries"]["10"]["final_amount_fmol"]
        > initial["world_summaries"]["10"]["final_amount_fmol"]
    )
    assert (
        got["world_summaries"]["11"]["final_amount_fmol"]
        == initial["world_summaries"]["11"]["final_amount_fmol"]
    )
    for flags in (
        ("--window-steps", 0),
        ("--checkpoint-every-windows", -1),
        ("--checkpoint-at", 0.5),
    ):
        invalid = cli("batch", "windowed", "run", config, "--output", tmp_path / "bad", *flags)
        assert invalid.returncode == 2 and not (tmp_path / "bad").exists()
    duplicate = cli("batch", "windowed", "run", config, "--output", root)
    assert duplicate.returncode == 2 and "already exists" in duplicate.stderr
