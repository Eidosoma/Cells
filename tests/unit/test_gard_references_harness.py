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


@pytest.mark.parametrize("row", [5, 7, 8])
def test_a_run_without_a_channel_table_is_refused(standin, tmp_path, row):
    _, roles = standin
    role = "lineage_diagnostic" if row == 5 else "lineage"
    dst = tmp_path / f"nochannels{row}"
    shutil.copytree(roles[role], dst)
    run = json.loads((dst / "run.json").read_text())
    del run["channels"]
    (dst / "run.json").write_text(json.dumps(run))
    report = harness.run_rows(dict(roles, **{role: str(dst)}), rows=[row])
    assert report["status"] == 2 and "channel table" in report["rows"][str(row)]["error"]


def test_mismatched_time_units_are_refused(standin, tmp_path):
    _, roles = standin
    dst = tmp_path / "units"
    shutil.copytree(roles["lineage"], dst)
    run = json.loads((dst / "run.json").read_text())
    run["time"]["unit"] = "s"
    (dst / "run.json").write_text(json.dumps(run))
    report = harness.run_rows(dict(roles, lineage=str(dst)), rows=[7])
    assert report["status"] == 2 and "time unit" in report["rows"]["7"]["error"]


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


def _edit_arrays(src: str, dst: Path, **changes) -> str:
    shutil.copytree(src, dst)
    with np.load(dst / "records.npz") as npz:
        arrays = {k: npz[k] for k in npz.files}
    arrays.update(changes)
    np.savez(dst / "records.npz", **arrays)
    return str(dst)


def _edit_run(src: str, dst: Path, **changes) -> str:
    shutil.copytree(src, dst)
    run = json.loads((dst / "run.json").read_text())
    run.update(changes)
    (dst / "run.json").write_text(json.dumps(run))
    return str(dst)


def test_malformed_but_present_records_fail_loudly(standin, tmp_path):
    _, roles = standin
    lin = load_bundle(roles["lineage"])
    # a 1/2 encoding shows up as a 2 (all-ones would read as "second daughter" and fail row 7 instead)
    one_two = _edit_arrays(roles["lineage"], tmp_path / "followed12", fission_followed=lin.arrays["fission_followed"] + 2)
    flat = _edit_arrays(roles["lineage"], tmp_path / "flat", assembly_count=lin.arrays["assembly_count"][:, :, 0])
    junk = _edit_arrays(roles["lineage"], tmp_path / "junk", row_event=np.zeros(3, dtype=np.int64))
    for path, needle in ((one_two, "fission_followed"), (flat, "assembly_count"), (junk, "row_event")):
        report = harness.run_rows(dict(roles, lineage=path), rows=[7, 8, 10])
        assert report["status"] == 2, report
        assert all(needle in e.get("error", "") for e in report["rows"].values() if not e["passed"])


def test_replay_identity_fields_decide_and_other_fields_are_listed(standin, tmp_path):
    _, roles = standin
    renamed = _edit_run(roles["replay"], tmp_path / "renamed", run_id="another", finished="later")
    report = harness.run_rows(dict(roles, replay=renamed), rows=[9])
    assert report["status"] == 0
    detail = report["rows"]["9"]["checks"][0]["detail"]
    assert detail["other_run_fields_differ"] == ["finished", "run_id"]
    rekeyed = _edit_run(roles["replay"], tmp_path / "rekeyed", stream={"seed": 1, "branch": 0})
    report = harness.run_rows(dict(roles, replay=rekeyed), rows=[9])
    assert report["status"] == 1


def test_lineage_splits_must_obey_the_declared_rule(standin, tmp_path):
    _, roles = standin
    lin = load_bundle(roles["lineage"])
    split = lin.arrays["fission_split"].copy()
    count = lin.arrays["assembly_count"]
    i = int(np.flatnonzero(count[1, :, 0] - split[0] > 0)[0])
    split[0, i] += 1  # one molecule too many in the first daughter: size floor(N/2) + 1
    bad = _edit_arrays(roles["lineage"], tmp_path / "split", fission_split=split)
    report = harness.run_rows(dict(roles, lineage=bad), rows=[6])
    assert report["status"] == 1
    failing = [c["name"] for c in report["rows"]["6"]["checks"] if not c["passed"]]
    assert failing == ["lineage_partition_exact"]


def test_an_undeclared_boundary_rule_is_surfaced(standin, tmp_path):
    _, roles = standin
    dst = tmp_path / "noboundary"
    shutil.copytree(roles["lineage"], dst)
    world = json.loads((dst / "world.json").read_text())
    del world["rules"]["boundary"]
    (dst / "world.json").write_text(json.dumps(world))
    report = harness.run_rows(dict(roles, lineage=str(dst)), rows=[7])
    detail = report["rows"]["7"]["checks"][0]["detail"]
    assert detail["boundary_rule_declared"] is False and detail["boundary_rule"] == "extinction_uncatalysed"


def test_transfer_constants_must_agree_with_the_basal_constants(standin, tmp_path):
    _, roles = standin
    dst = tmp_path / "kmismatch"
    shutil.copytree(roles["lineage"], dst)
    world = json.loads((dst / "world.json").read_text())
    ratio = world["constants"]["k_join"][0] / world["constants"]["k_leave"][0]
    world["types"] = [{"name": n, "K": ratio} for n in world["types"]]
    (dst / "world.json").write_text(json.dumps(world))
    assert harness.run_rows(dict(roles, lineage=str(dst)), rows=[7])["status"] == 0
    world["types"][3]["K"] = ratio * 1.01
    (dst / "world.json").write_text(json.dumps(world))
    report = harness.run_rows(dict(roles, lineage=str(dst)), rows=[7])
    assert report["status"] == 2 and "transfer constants" in report["rows"]["7"]["error"]
