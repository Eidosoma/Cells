"""OL5 references, the harness: end to end on the stand-in, and loud on what is missing.

On the complete stand-in every OL1 row passes (exit 0). A planted form in one role fails its row
(exit 1). A missing role, a missing manifest, an undeclared token or a changed probe echo stops
the row (exit 2).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from validation.ool.references import harness as H
from validation.ool.references import standin as S
from validation.ool.references.design import (
    CLOSED_WORLD_FILE,
    KERNEL_PROBE_FILE,
    PROBED_CONVENTIONS,
)
from validation.ool.references.registered import DESIGN_DIR
from validation.ool.references.world import Conventions


@pytest.fixture(scope="module")
def standin(tmp_path_factory):
    out = tmp_path_factory.mktemp("ool-standin") / "records"
    return out, S.build_standin(out)


def test_every_row_passes_on_the_standin(standin):
    _, roles = standin
    status, report = H.run_rows(roles)
    assert status == 0, {k: v for k, v in report.items() if not v["passed"]}
    assert set(report) == set(H.ROWS)


def _planted_probe(base: Path, world: str, states_file: str, form: str) -> list:
    paths = []
    for i, pair in enumerate(PROBED_CONVENTIONS):
        conv = Conventions(**pair)
        states = np.asarray(json.loads((DESIGN_DIR / states_file).read_text())["states"], dtype=np.int64)
        paths.append(str(S.write_probe(base / f"{form}-{i}", world, conv, states, form,
                                       dict(step="r3", place="D@membrane", lam=1))))
    return paths


def test_planted_forms_fail_their_rows(standin, tmp_path):
    _, roles = standin
    bad = dict(roles, kernel_probe=_planted_probe(tmp_path, "ol1_wa", KERNEL_PROBE_FILE, "at_state_factor"))
    status, report = H.run_rows(bad, ["OL1-1"])
    assert status == 1 and not report["OL1-1"]["passed"]
    bad = dict(roles, closed_world=_planted_probe(tmp_path, "ol1_wa_closed", CLOSED_WORLD_FILE,
                                                  "forward_only_catalysis"))
    status, report = H.run_rows(bad, ["OL1-2"])
    assert status == 1 and not report["OL1-2"]["passed"]
    refusals = S.write_refusals(tmp_path / "refusals", accept=("refuse_coefficient",))
    status, report = H.run_rows(dict(roles, refusals=str(refusals)), ["OL1-4"])
    assert status == 1


def test_missing_or_malformed_records_exit_2(standin, tmp_path):
    _, roles = standin
    status, report = H.run_rows({k: v for k, v in roles.items() if k != "ledger_run"}, ["OL1-5"])
    assert status == 2 and "ledger_run" in report["OL1-5"]["missing_or_malformed"]
    # a probe without its manifest
    probe = Path(roles["kernel_probe"][0])
    copy = tmp_path / "probe-copy"
    shutil.copytree(probe, copy)
    (copy / "manifest.json").unlink()
    status, _ = H.run_rows(dict(roles, kernel_probe=[str(copy)]), ["OL1-1"])
    assert status == 2
    # an undeclared token
    shutil.copyfile(probe / "manifest.json", copy / "manifest.json")
    meta = json.loads((copy / "probe.json").read_text())
    del meta["conventions"]["last_molecule"]
    (copy / "probe.json").write_text(json.dumps(meta))
    status, report = H.run_rows(dict(roles, kernel_probe=[str(copy)]), ["OL1-1"])
    assert status == 2 and "last_molecule" in report["OL1-1"]["missing_or_malformed"]
    # a changed echo of the registered states
    meta["conventions"]["last_molecule"] = "kept"
    (copy / "probe.json").write_text(json.dumps(meta))
    arrays = dict(np.load(copy / "probe.npz"))
    arrays["input_states"] = arrays["input_states"].copy()
    arrays["input_states"][3, 0] += 1
    np.savez(copy / "probe.npz", **arrays)
    status, report = H.run_rows(dict(roles, kernel_probe=[str(copy)]), ["OL1-1"])
    assert status == 2 and "echoed" in report["OL1-1"]["missing_or_malformed"]


def test_make_probes_writes_every_registered_input(tmp_path):
    out = H.make_probes(tmp_path / "inputs")
    names = {p.relative_to(out).as_posix() for p in out.rglob("*.json")}
    assert {"ol1_conventions.json", "ol1_design.json", "ol1_kernel_probe_states.json",
            "ol1_closed_world_states.json", "ol1_wa.world.json", "refusals/refuse_coefficient.world.json"} <= names
    assert (out / KERNEL_PROBE_FILE).read_bytes() == (DESIGN_DIR / KERNEL_PROBE_FILE).read_bytes()
