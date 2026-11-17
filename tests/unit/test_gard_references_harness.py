"""The comparison harness end to end on stand-in records, and its loud failure.

Every row runs against a stand-in record set from the host oracle. Then each required
record is removed in turn, and the row that needs it must fail with a ``MISSING`` status
naming it. A planted error in the records must fail its row.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from validation.gard.references import harness
from validation.gard.references.records import MissingRecord, load_bundle
from validation.gard.references.standin import build_standin

LINEAGE_RECORDS = ("assembly_count", "joined_total", "left_total", "discarded_total", "exchange_heat_kT",
                   "fission_work_kT", "discarded_free_energy_kT", "log_weight", "ledger_residual_kT", "row_event",
                   "fission_split", "fission_followed", "fission_similarity", "event_channel", "events_per_growth",
                   "event_time")


@pytest.fixture(scope="module")
def standin(tmp_path_factory):
    root = tmp_path_factory.mktemp("gard_g2")
    roles = build_standin(root / "records", n_fissions=8)
    return root, roles


def test_every_row_passes_on_the_standin(standin):
    _, roles = standin
    report = harness.run_rows(roles)
    failed = {n: e for n, e in report["rows"].items() if not e["passed"]}
    assert report["status"] == 0, json.dumps(failed, indent=1)[:4000]


def _without(src: str, dst: Path, drop: str) -> str:
    shutil.copytree(src, dst)
    with np.load(dst / "records.npz") as npz:
        arrays = {k: npz[k] for k in npz.files if k != drop}
    np.savez(dst / "records.npz", **arrays)
    return str(dst)


@pytest.mark.parametrize("record", LINEAGE_RECORDS)
def test_a_missing_lineage_record_fails_loudly(standin, tmp_path, record):
    _, roles = standin
    r = dict(roles, lineage=_without(roles["lineage"], tmp_path / "lineage", record))
    report = harness.run_rows(r, rows=[7, 8, 10])
    assert report["status"] == 2
    errors = [e.get("error", "") for e in report["rows"].values()]
    assert any(record in err for err in errors), errors


@pytest.mark.parametrize("role", sorted({r for _, needs in harness.ROWS.values() for r in needs}))
def test_a_missing_role_fails_loudly(standin, role):
    _, roles = standin
    rows = [n for n, (_, needs) in harness.ROWS.items() if role in needs]
    r = {k: v for k, v in roles.items() if k != role}
    report = harness.run_rows(r, rows=rows)
    assert report["status"] == 2
    assert all(not e["passed"] and role in e.get("error", "") for e in report["rows"].values())


def test_an_incomplete_bundle_is_refused(standin, tmp_path):
    _, roles = standin
    dst = tmp_path / "partial"
    shutil.copytree(roles["lineage"], dst)
    (dst / "manifest.json").unlink()
    with pytest.raises(MissingRecord):
        load_bundle(dst)


def test_a_missing_world_field_fails_loudly(standin, tmp_path):
    _, roles = standin
    dst = tmp_path / "noworld"
    shutil.copytree(roles["lineage"], dst)
    world = json.loads((dst / "world.json").read_text())
    del world["rules"]["fission"]["mass"]
    (dst / "world.json").write_text(json.dumps(world))
    report = harness.run_rows(dict(roles, lineage=str(dst)), rows=[8])
    assert report["status"] == 2 and "rules.fission.mass" in report["rows"]["8"]["error"]


def test_a_run_without_ssa_convention_is_refused(standin, tmp_path):
    _, roles = standin
    dst = tmp_path / "noconv"
    shutil.copytree(roles["lineage_diagnostic"], dst)
    run = json.loads((dst / "run.json").read_text())
    del run["ssa_convention"]
    (dst / "run.json").write_text(json.dumps(run))
    report = harness.run_rows(dict(roles, lineage_diagnostic=str(dst)), rows=[5])
    assert report["status"] == 2 and "convention" in report["rows"]["5"]["error"]


def test_a_planted_heat_sign_error_fails_row_8(standin, tmp_path):
    _, roles = standin
    dst = tmp_path / "signerr"
    shutil.copytree(roles["lineage"], dst)
    with np.load(dst / "records.npz") as npz:
        arrays = {k: npz[k] for k in npz.files}
    arrays["exchange_heat_kT"] = -arrays["exchange_heat_kT"]
    np.savez(dst / "records.npz", **arrays)
    report = harness.run_rows(dict(roles, lineage=str(dst)), rows=[8])
    assert report["status"] == 1 and not report["rows"]["8"]["passed"]


def test_cli_make_probes_and_run(standin, tmp_path, capsys):
    root, roles = standin
    assert harness.main(["make-probes", str(tmp_path / "probes")]) == 0
    assert (tmp_path / "probes" / "kernel_probe_inputs.npz").is_file()
    roles_file = tmp_path / "roles.json"
    roles_file.write_text(json.dumps(roles))
    status = harness.main(["run", "--roles", str(roles_file), "--rows", "7,10", "--out", str(tmp_path / "r.json")])
    assert status == 0 and json.loads((tmp_path / "r.json").read_text())["status"] == 0
