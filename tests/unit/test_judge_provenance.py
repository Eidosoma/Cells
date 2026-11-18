"""G2-Q1's judge records the numerical environment the engine's run records keep.

cell_replacement_judge.provenance() adds cells.records.io.runtime_identity's numerical_environment
(XLA_FLAGS and JAX_DISABLE_JIT), so an item run under an XLA setting (Q7 under the
deterministic GPU flag, D168) is identified by its record. Record only: the verdicts of
saved item records are unchanged. No engine run.
"""

import copy
import json
from pathlib import Path

import pytest

from cells.records.io import runtime_identity
from validation.tissue import cell_replacement_judge as judge

# The composite's L4 judged run C (14 November): every G2-Q1 item record, Q7 failed.
C = Path("/mnt/workspaces/Cells/composite-l4-agreement-20261114-01/c")
SAVED = sorted([*C.glob("g2-a/Q*.json"), *C.glob("g2-b/Q*.json")])


@pytest.mark.parametrize("flags", [None, "--xla_gpu_deterministic_ops=true"])
def test_the_record_keeps_the_numerical_environment(flags, monkeypatch):
    if flags is None:
        monkeypatch.delenv("XLA_FLAGS", raising=False)
    else:
        monkeypatch.setenv("XLA_FLAGS", flags)
    record = judge.provenance()
    assert record["numerical_environment"] == runtime_identity()["numerical_environment"]
    assert record["numerical_environment"]["XLA_FLAGS"] == flags
    assert set(record["numerical_environment"]) == {"XLA_FLAGS", "JAX_DISABLE_JIT"}
    # The fields recorded before are all still there.
    for key in ("argv", "host", "jax", "source_root", "revision", "dirty", "snapshot"):
        assert key in record


def test_the_verdict_rule_is_unchanged():
    """with_verdict is the rule the judge applied inline before (cases all pass, else fail;
    an item's own verdict kept)."""
    assert judge.with_verdict(dict(cases={"a": {"verdict": "pass"}}))["verdict"] == "pass"
    assert judge.with_verdict(dict(cases={"a": {"verdict": "fail"}}))["verdict"] == "fail"
    assert judge.with_verdict(dict(cases={}))["verdict"] == "fail"
    assert (
        judge.with_verdict(dict(verdict="fail", cases={"a": {"verdict": "pass"}}))["verdict"]
        == "fail"
    )


@pytest.mark.skipif(not SAVED, reason="the L4 judged run's records are not on this machine")
@pytest.mark.parametrize("path", SAVED, ids=lambda p: p.name)
def test_verdicts_on_existing_records_are_unchanged(path):
    """Each saved item record, with and without the new provenance field (and under another
    XLA setting), keeps its recorded verdict through the judge's verdict rule: an item that
    set its own verdict (Q6, Q7) keeps it; one judged by its cases recomputes the same."""
    saved = json.loads(path.read_text())
    for extra in ({}, dict(numerical_environment={"XLA_FLAGS": "--x", "JAX_DISABLE_JIT": None})):
        item = copy.deepcopy(saved)
        item.update(extra)
        assert judge.with_verdict(item)["verdict"] == saved["verdict"]
        if saved.get("cases"):  # Judged by its cases: recomputed without the stored verdict.
            item.pop("verdict")
            assert judge.with_verdict(item)["verdict"] == saved["verdict"]
