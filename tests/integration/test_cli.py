import json
import subprocess
import sys

import jax.numpy as jnp
import numpy as np

import cells.__main__ as command_line
from cells import __version__
from cells.models import reaction_transport


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "cells", *map(str, args)], capture_output=True, text=True, timeout=60
    )


def test_cli_fresh_resume_branch(config_data, tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps(config_data))
    valid = cli("validate", config)
    assert valid.returncode == 0, valid.stderr
    assert json.loads(valid.stdout)["status"] == "valid"
    original = tmp_path / "original"
    fresh = cli("run", config, "--output", original, "--checkpoint-at", 6.0)
    assert fresh.returncode == 0, fresh.stderr
    assert "NVIDIA" not in fresh.stderr
    manifest = json.loads((original / "manifest.json").read_text())
    snapshot = original / manifest["snapshots"][0]
    resumed = tmp_path / "resumed"
    restored = cli("resume", snapshot, "--output", resumed)
    assert restored.returncode == 0, restored.stderr
    with (
        np.load(original / "trajectory.npz", allow_pickle=False) as a,
        np.load(resumed / "trajectory.npz", allow_pickle=False) as b,
    ):
        for field in ("amount", "transferred", "converted"):
            np.testing.assert_array_equal(a[field][-1], b[field][-1])
        at_the_branch = b["transferred"][0]
    config_data["experiment"]["contact"]["schedule"].append({"time": 6.0, "open_fractions": [0]})
    branch_config = tmp_path / "branch.json"
    branch_config.write_text(json.dumps(config_data))
    branched = tmp_path / "branched"
    branch = cli("branch", snapshot, branch_config, "--output", branched)
    assert branch.returncode == 0, branch.stderr
    # The closed contact moves nothing after 6; the open one, on the resumed run, does.
    final = json.loads(branch.stdout)["final_signed_transferred_fmol"]
    np.testing.assert_array_equal(final, at_the_branch)
    assert json.loads(fresh.stdout)["final_signed_transferred_fmol"] != final
    branch_manifest = json.loads((branched / "manifest.json").read_text())
    assert branch_manifest["provenance"]["operation"] == "branch"
    assert branch_manifest["provenance"]["parent_snapshot_sha256"]
    duplicate = cli("run", config, "--output", original)
    assert duplicate.returncode == 2
    assert "already exists" in duplicate.stderr


def test_cli_invalid_input_does_not_create_output(config_data, tmp_path):
    config_data["execution"]["backend"] = "gpu"
    config = tmp_path / "bad.json"
    config.write_text(json.dumps(config_data))
    output = tmp_path / "should_not_exist"
    result = cli("run", config, "--output", output)
    assert result.returncode == 2
    assert "backend" in result.stderr
    assert not output.exists()


def test_cli_help_and_version():
    assert cli("--help").returncode == 0
    assert cli("--version").stdout.strip() == f"Cells {__version__}"


def test_cli_reaction_transport_composition(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    definition = root / "configs/reaction_transport_chain.json"
    released = root / "configs/reaction_transport_release.json"
    first = cli("run", definition, "--output", tmp_path / "chain", "--checkpoint-at", 6)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["species"] == ["A", "B"]
    parent = tmp_path / "chain/snapshots/step-000122"
    resumed = cli("resume", parent, "--output", tmp_path / "resumed")
    branch = cli("branch", parent, released, "--output", tmp_path / "released")
    assert resumed.returncode == branch.returncode == 0, (resumed.stderr, branch.stderr)
    with (
        np.load(tmp_path / "chain/trajectory.npz", allow_pickle=False) as a,
        np.load(tmp_path / "resumed/trajectory.npz", allow_pickle=False) as b,
        np.load(tmp_path / "released/trajectory.npz", allow_pickle=False) as c,
    ):
        for field in ("amount", "transferred", "converted"):
            np.testing.assert_array_equal(a[field][122:], b[field])
            np.testing.assert_array_equal(a[field][122], c[field][0])
        np.testing.assert_array_equal(c["transferred"][0], c["transferred"][-1])
        assert not np.array_equal(c["amount"][0], c["amount"][-1])
    invalid = json.loads(definition.read_text())
    invalid["experiment"]["contact"]["contact_ids"] = [7, 7]
    config = tmp_path / "invalid.json"
    config.write_text(json.dumps(invalid))
    failed = cli("run", config, "--output", tmp_path / "invalid")
    assert failed.returncode == 2 and not (tmp_path / "invalid").exists()
    single = cli(
        "run", root / "configs/reaction_transport_single.json", "--output", tmp_path / "single"
    )
    assert single.returncode == 0, single.stderr
    assert json.loads(single.stdout)["physical_contacts"] == 0


def test_cli_failed_step_leaves_no_output(config_data, tmp_path, monkeypatch, capsys):
    """A definition that parses and starts, whose step then leaves its model's domain (planted:
    the first cell may convert 1 fmol), exits 2, names the interval and leaves no output."""

    def domain(state, parameters, active):
        return jnp.all(state.amount >= 0) & (state.converted[0] < 1.0)

    monkeypatch.setattr(reaction_transport, "domain_valid", domain, raising=False)
    config = tmp_path / "config.json"
    config.write_text(json.dumps(config_data))
    output = tmp_path / "should-not-exist"
    assert command_line.main(["run", str(config), "--output", str(output)]) == 2
    assert "trial/endpoint domain failure on [" in capsys.readouterr().err
    assert not output.exists()
