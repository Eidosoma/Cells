"""FR-10's comparison harness on stand-in bundles: the honest one passes every row, each
planted one fails its row, and missing or malformed inputs give status 2.
"""

from __future__ import annotations

import json
import shutil

import pytest

from validation.fr10.references import harness, standin


@pytest.fixture(scope="module")
def honest(tmp_path_factory):
    return standin.build_standin(tmp_path_factory.mktemp("honest"), "honest")


def test_the_honest_standin_passes_every_row(honest):
    status, report = harness.run_roles(honest)
    assert status == 0, [r for r in report.get("rows", []) if not r["passed"]] or report
    names = [r["name"] for r in report["rows"]]
    assert sum(n.startswith("faces@") for n in names) == 4
    assert sum(n.startswith("ion@") for n in names) == 4
    assert {"records_W1@1", "records_W1@2", "records_W2@0.5", "records_W3@0.002",
            "K_W1_own_supply", "K_W1_reference_supply", "K_W3_own_supply"} <= set(names)


@pytest.mark.parametrize("variant, rows, must_fail", [
    ("late", "faces,ion", {"faces@0.001", "ion@0.000125", "order"}),
    ("first_order", "faces,ion", {"faces@0.001", "ion@0.001", "order"}),
    ("null", "faces", {"faces@0.001", "faces@0.000125"}),
    ("dG_sign", "records", {"records_W1@1", "records_W2@0.5", "records_W3@0.002"}),
    ("K_without_B", "K", {"K_W1_own_supply", "K_W1_reference_supply"}),
    ("counterion", "records", {"records_W2@0.5"}),
])
def test_each_planted_standin_fails_its_row(tmp_path, variant, rows, must_fail):
    roles = standin.build_standin(tmp_path / variant, variant)
    status, report = harness.run_roles(roles, rows=rows.split(","))
    assert status == 1
    failed = {r["name"] for r in report["rows"] if not r["passed"]}
    assert must_fail <= failed, failed


def test_missing_or_malformed_inputs_give_status_2(honest, tmp_path):
    root = tmp_path / "copy"
    shutil.copytree(honest.parent, root)
    roles = root / "roles.json"
    # a tolerance above the registered ceiling has no power
    status, report = harness.run_roles(roles, tolerances={"W1": {"0.001": 1.0}}, rows=["faces"])
    assert status == 2 and "no power" in report["error"]
    # a bundle without its manifest is incomplete
    (root / "W1_dt0.0005" / "manifest.json").unlink()
    status, report = harness.run_roles(roles, rows=["faces"])
    assert status == 2 and "manifest" in report["error"]
    # a missing role
    r = json.loads(roles.read_text())
    del r["records_W3"]
    roles.write_text(json.dumps(r))
    status, report = harness.run_roles(roles, rows=["records"])
    assert status == 2 and "records_W3" in report["error"]
