import json
import subprocess
import sys

import numpy as np

from cells import __version__


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
        for field in ("amount", "supplied", "degraded"):
            np.testing.assert_array_equal(a[field][-1], b[field][-1])
    config_data["experiment"]["source"]["schedule"].append({"time": 6.0, "rate": 0.5})
    branch_config = tmp_path / "branch.json"
    branch_config.write_text(json.dumps(config_data))
    branched = tmp_path / "branched"
    branch = cli("branch", snapshot, branch_config, "--output", branched)
    assert branch.returncode == 0, branch.stderr
    assert (
        json.loads(branch.stdout)["final_amount_fmol"]
        > json.loads(fresh.stdout)["final_amount_fmol"]
    )
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


def test_cli_regulatory_model(tmp_path):
    from pathlib import Path

    data = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/emt_isolated_e.json").read_text()
    )
    data["experiment"].update(end_time=20, observation_times=[0, 10, 20])
    config = tmp_path / "emt.json"
    config.write_text(json.dumps(data))
    assert cli("validate", config).returncode == 0
    original = tmp_path / "original"
    first = cli("run", config, "--output", original, "--checkpoint-at", 10)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["final_label"] == "E"
    restored = cli("resume", original / "snapshots/step-000100", "--output", tmp_path / "resumed")
    assert restored.returncode == 0, restored.stderr
    assert (
        json.loads(restored.stdout)["final_scaled_state"]
        == json.loads(first.stdout)["final_scaled_state"]
    )


def test_cli_contact_run_resume_release_and_refusal(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    active = root / "configs/pair_exchange_active.json"
    release = root / "configs/pair_exchange_release.json"
    original = tmp_path / "active"
    assert cli("validate", active).returncode == 0
    fresh = cli("run", active, "--output", original, "--checkpoint-at", 6)
    assert fresh.returncode == 0, fresh.stderr
    assert json.loads(fresh.stdout)["active_cells"] == 2
    snapshot = original / "snapshots/step-000120"
    resumed = cli("resume", snapshot, "--output", tmp_path / "resumed")
    assert resumed.returncode == 0, resumed.stderr
    branch = cli("branch", snapshot, release, "--output", tmp_path / "release")
    assert branch.returncode == 0, branch.stderr
    assert (
        json.loads(branch.stdout)["final_signed_transferred_fmol"]
        < json.loads(resumed.stdout)["final_signed_transferred_fmol"]
    )
    with (
        np.load(original / "trajectory.npz", allow_pickle=False) as a,
        np.load(tmp_path / "resumed/trajectory.npz", allow_pickle=False) as b,
    ):
        for field in ("amount", "transferred"):
            np.testing.assert_array_equal(a[field][120:], b[field])
    invalid = json.loads(active.read_text())
    invalid["model"]["parameters"]["contact"]["to_cell_id"] = 999
    config = tmp_path / "bad-contact.json"
    config.write_text(json.dumps(invalid))
    failed = cli("run", config, "--output", tmp_path / "invalid")
    assert failed.returncode == 2 and not (tmp_path / "invalid").exists()


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


def test_cli_physical_cell_fresh_resume_branch_and_failed_trial(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    config = root / "configs/bioelectric_baseline.json"
    branch_config = root / "configs/bioelectric_branch.json"
    assert cli("validate", config).returncode == 0
    first = cli("run", config, "--output", tmp_path / "cell", "--checkpoint-at", 6)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["physical_membranes"] == 1
    parent = tmp_path / "cell/snapshots/step-001200"
    resumed = cli("resume", parent, "--output", tmp_path / "resumed")
    branch = cli("branch", parent, branch_config, "--output", tmp_path / "branch")
    assert resumed.returncode == branch.returncode == 0, (resumed.stderr, branch.stderr)
    with (
        np.load(tmp_path / "cell/trajectory.npz") as a,
        np.load(tmp_path / "resumed/trajectory.npz") as b,
        np.load(tmp_path / "branch/trajectory.npz") as c,
    ):
        for field in ("amount", "leak_transferred", "pump_cycles"):
            np.testing.assert_array_equal(a[field][1200:], b[field])
            np.testing.assert_array_equal(a[field][1200], c[field][0])
        for field in (
            "amount_reference",
            "voltage_reference",
            "fixed_charge",
            "bath_concentration",
        ):
            np.testing.assert_array_equal(a[field], c[field])
        assert not np.array_equal(b["amount"][-1], c["amount"][-1])
    data = json.loads(config.read_text())
    data["model"]["parameters"]["membrane"]["pump_capacity_fmol_per_s"] = 1000
    bad_config = tmp_path / "bad.json"
    bad_config.write_text(json.dumps(data))
    failed = cli("run", bad_config, "--output", tmp_path / "invalid")
    assert failed.returncode == 2 and "trial/endpoint" in failed.stderr
    assert not (tmp_path / "invalid").exists()


def test_cli_physical_pair_complete_replay_branch_and_gate_failure(tmp_path):
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    config = root / "configs/bioelectric_pair_baseline.json"
    branch_config = root / "configs/bioelectric_pair_branch.json"
    assert cli("validate", config).returncode == 0
    first = cli("run", config, "--output", tmp_path / "pair", "--checkpoint-at", 6)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["physical_contacts"] == 1
    parent = tmp_path / "pair/snapshots/step-006000"
    resumed = cli("resume", parent, "--output", tmp_path / "resumed")
    branched = cli("branch", parent, branch_config, "--output", tmp_path / "branched")
    assert resumed.returncode == branched.returncode == 0, (resumed.stderr, branched.stderr)
    with (
        np.load(tmp_path / "pair/trajectory.npz") as a,
        np.load(tmp_path / "resumed/trajectory.npz") as b,
        np.load(tmp_path / "branched/trajectory.npz") as c,
    ):
        for field in (
            "amount",
            "leak_transferred",
            "pump_cycles",
            "transferred",
            "gate",
            "dissipated_energy_pJ",
        ):
            np.testing.assert_array_equal(a[field][6000:], b[field])
            np.testing.assert_array_equal(a[field][6000], c[field][0])
        for field in (
            "amount_reference",
            "voltage_reference",
            "fixed_charge",
            "gate_tau",
            "contact_permeability",
            "owners",
            "senders",
            "receivers",
        ):
            np.testing.assert_array_equal(a[field], c[field])
        assert not np.array_equal(c["transferred"][-1], b["transferred"][-1])
        assert c["gate"][0, 0] != 0.25
    bad = json.loads(config.read_text())
    bad["model"]["parameters"]["contact"]["tau_s"] = 1e-6
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(bad))
    failure = cli("run", invalid, "--output", tmp_path / "should-not-exist")
    assert failure.returncode == 2 and "trial/endpoint" in failure.stderr
    assert not (tmp_path / "should-not-exist").exists()
