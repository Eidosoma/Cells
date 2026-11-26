"""The scorer's self-tests on fabricated tables of the invented set (tests/fabricate.py; no engine).

CRITERIA.md §6.3's five self-tests, every row of §4's fault table, the S statistic's outcomes, the pair, W5-exact's
rungs and running check, the plants, the retry flow and the structure-only read; and one row for each ruling of the
lead's RULINGS-2026-11-26.md that changed the scorer (2b, 2c, 6b and 6c with CRITERIA:321, 7, 15, 16, 19; 3b and 8
are in test_echo.py) and for its records (14). About 90 s on one core (a case is one judge pass of about 1 s).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import struct
import sys

import pytest

JUDGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, JUDGE)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fabricate  # noqa: E402
from cowriter_judge.api import format_sample, judge_pass, references_through_c0, retry_owed_file  # noqa: E402
from cowriter_judge.registry import Inputs  # noqa: E402

OUT = os.path.join(JUDGE, "..", "references", "out")
SPEC = os.path.join(JUDGE, "..", "spec")


@pytest.fixture(scope="module")
def base() -> dict:
    inputs = Inputs(os.path.join(OUT, "inputs_invented.json"))
    refs, _ = references_through_c0(inputs, {}, os.path.join(OUT, "draws_invented.json"),
                                    os.path.join(OUT, "reference_invented.json"))
    assert all(refs.values())
    raw = json.load(open(os.path.join(OUT, "reference_invented.json")))
    fab = fabricate.fabricate(inputs, raw, retry_families=("W5 reactions-first",))
    return {"inputs": inputs, "refs": refs, "raw": raw, "fab": fab}


def next_up(x: float) -> float:
    return math.nextafter(x, math.inf)


class Scenario:
    def __init__(self, base: dict) -> None:
        self.inputs: Inputs = base["inputs"]
        self.refs = base["refs"]
        self.raw = base["raw"]
        self.tables = copy.deepcopy(base["fab"]["tables"])
        self.retry_tables = copy.deepcopy(base["fab"]["retry"])
        self.operators = base["fab"]["operators"]
        self.raw_text: dict[str, str] = {}
        self.drop_sums = False
        self.sums_edit: dict[str, str] = {}
        self.lead_record: dict | None = None
        self.sample_hashes: set[str] = set()
        self.rehearsal = True
        self.revision: str | None = None

    def name(self, family: str, rung: int, copy_: int) -> str:
        fam = self.inputs.families[family]
        return self.inputs.judged_run(family, fam.rungs[rung], copy_)

    def table_of(self, name: str) -> dict:
        for table in self.tables.values():
            if name in table["runs"]:
                return table
        raise KeyError(name)

    def entry(self, name: str) -> dict:
        return self.table_of(name)["runs"][name]

    def run(self, tmp_path, retry_owed: dict | None = None, with_retry_tables: bool = False) -> dict:
        folder = os.path.join(tmp_path, "table")
        sums = fabricate.write(folder, self.tables, self.raw_text)
        if self.sums_edit or self.drop_sums:
            path = os.path.join(folder, "SHA256SUMS")
            if self.drop_sums:
                os.remove(path)
            else:
                with open(path, "w") as handle:
                    for name, digest in sorted({**sums, **self.sums_edit}.items()):
                        if digest:
                            handle.write(f"{digest}  {name}\n")
        retry_dir = None
        if with_retry_tables:
            retry_dir = os.path.join(tmp_path, "table-retry")
            fabricate.write(retry_dir, self.retry_tables)
        return judge_pass(self.inputs, self.refs, folder, self.operators, self.revision, self.rehearsal,
                          self.lead_record, self.sample_hashes, retry_dir, retry_owed)


def outcome(record: dict, run: str | None, entry: str) -> list[str]:
    return [e["outcome"] for e in record["entries"] if e["run"] == run and e["entry"] == entry]


def s_outcome(record: dict, family: str, readout: str) -> dict:
    found = [e for e in record["entries"] if e["family"] == family and e["entry"] == f"S {readout}"]
    assert len(found) == 1
    return found[0]


def issues(record: dict, run: str) -> set[str]:
    return {r["row"] for r in record["refusals_and_flags"] if r.get("run") == run}


def fam(record: dict, family: str) -> str:
    return record["families"][family]["verdict"]


# ---- the honest tables ----

def test_honest_invented_tables_pass(base, tmp_path) -> None:
    record = Scenario(base).run(str(tmp_path))
    assert record["claim"] == "pass", record["arms"]
    assert all(e["outcome"] == "pass" for e in record["entries"])
    assert all(p["score"] == "caught" for p in record["plants"].values())
    assert record["retry_owed"]["families"] == []


def test_honest_registered_tables_pass(tmp_path) -> None:
    inputs = Inputs(os.path.join(SPEC, "inputs.json"))
    paths = {w: os.path.join(OUT, f"reference_{w}.json") for w in inputs.worlds}
    refs, _ = references_through_c0(inputs, paths, os.path.join(SPEC, "draws.json"))
    raw = {w: json.load(open(p)) for w, p in paths.items()}
    fab = fabricate.fabricate(inputs, raw)
    fabricate.write(str(tmp_path / "table"), fab["tables"])
    record = judge_pass(inputs, refs, str(tmp_path / "table"), fab["operators"], fabricate.REVISION, False)
    assert record["claim"] == "pass", record["arms"]
    assert all(p["score"] == "caught" for p in record["plants"].values())


# ---- CRITERIA.md §6.3: the judge's five self-tests ----

def test_self_test_an_E_value_moved_one_ulp(base, tmp_path) -> None:
    sc = Scenario(base)
    restart = [s.name for s in sc.inputs.run_list if s.variant == "restart" and s.world == "W5"][0]
    ev = sc.entry(restart)["events"]
    ev["time_s"][0] = next_up(ev["time_s"][0])
    record = sc.run(str(tmp_path))
    unint = sc.inputs.data["restart"]["W5"]["run"]
    assert outcome(record, unint, "E restart") == ["fail"]
    assert fam(record, "W5 reactions-first") == "fail"


def test_self_test_a_count_moved_one_unit(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W6 population-first", 2, 1)
    sc.entry(name)["events"]["counts_after"][3][0] += 1
    record = sc.run(str(tmp_path))
    assert outcome(record, name, "E trace") == ["fail"]
    assert fam(record, "W6 population-first") == "fail"


def test_self_test_a_resumed_row_moved_one_ulp(base, tmp_path) -> None:
    sc = Scenario(base)
    restart = [s.name for s in sc.inputs.run_list if s.variant == "restart" and s.world == "W6"][0]
    series = sc.entry(restart)["series"]["n_R_o"]
    series[-1] = next_up(series[-1])
    record = sc.run(str(tmp_path))
    unint = sc.inputs.data["restart"]["W6"]["run"]
    assert outcome(record, unint, "E restart") == ["fail"]
    assert record["arms"]["W6"]["verdict"] == "fail"


def test_self_test_an_event_out_of_order(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5 population-first", 0, 2)
    times = sc.entry(name)["events"]["time_s"]
    times[4], times[5] = times[5], times[4]
    record = sc.run(str(tmp_path))
    assert outcome(record, name, "E trace") == ["fail"]
    assert s_outcome(record, "W5 population-first", "t_events")["outcome"] == "unformed"
    assert fam(record, "W5 population-first") == "fail"


def test_self_test_an_echo_that_departs(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5 reactions-first", 3, 0)
    sc.entry(name)["inputs"]["cell_pL"] *= 1 + 1e-9
    record = sc.run(str(tmp_path))
    assert "echo" in issues(record, name)
    assert set(outcome(record, name, "E trace")) == {"unformed"}
    assert fam(record, "W5 reactions-first") == "inconclusive"
    assert record["claim"] == "inconclusive"


def test_self_test_a_record_hash_shared_by_two_runs(base, tmp_path) -> None:
    sc = Scenario(base)
    a, b = sc.name("W6 gene-first", 1, 0), sc.name("W6 population-first", 4, 3)
    sc.entry(b)["record_sha256"] = sc.entry(a)["record_sha256"]
    record = sc.run(str(tmp_path))
    assert "shared record hash" in issues(record, a) and "shared record hash" in issues(record, b)
    assert fam(record, "W6 gene-first") == "inconclusive" and fam(record, "W6 population-first") == "inconclusive"


# ---- CRITERIA.md §4: the fault table, row by row ----

def _table_name(sc: Scenario, world: str) -> str:
    return f"table_{world}.json"


@pytest.mark.parametrize("how", ["departs", "no line", "lead record", "format sample"])
def test_a_table_hash_that_departs_judges_nothing(base, tmp_path, how) -> None:
    sc = Scenario(base)
    name = _table_name(sc, "W5-exact")
    if how == "departs":
        sc.sums_edit[name] = "0" * 64
    elif how == "no line":
        sc.sums_edit[name] = ""
    elif how == "lead record":
        sc.lead_record = {n: hashlib.sha256(json.dumps(t).encode()).hexdigest() for n, t in sc.tables.items()}
        sc.lead_record[name] = "1" * 64
    else:
        sc.sample_hashes = {hashlib.sha256(json.dumps(sc.tables[name]).encode()).hexdigest()}
    record = sc.run(str(tmp_path))
    assert record["arms"]["W5-exact"]["verdict"] == "inconclusive"
    assert record["arms"]["W5"]["verdict"] == "pass"
    run = sc.name("W5-exact reactions-first", 0, 0)
    assert set(outcome(record, run, "R t_events")) == {"unformed"}


def test_an_absent_sha256sums_is_flagged_only(base, tmp_path) -> None:
    sc = Scenario(base)
    sc.drop_sums = True
    record = sc.run(str(tmp_path))
    assert record["claim"] == "pass"
    assert any(r.get("row") == "hash" and r.get("effect") == "flag" for r in record["refusals_and_flags"])


@pytest.mark.parametrize("key, value", [("units", None), ("kind", "another table"), ("arm", 3)])
def test_a_top_level_key_refuses_every_run(base, tmp_path, key, value) -> None:
    sc = Scenario(base)
    table = sc.tables["table_W5.json"]
    if value is None:
        del table[key]
    else:
        table[key] = value
    record = sc.run(str(tmp_path))
    assert fam(record, "W5 reactions-first") == "inconclusive" and fam(record, "W5 population-first") == "inconclusive"
    assert record["arms"]["W6"]["verdict"] == "pass"


@pytest.mark.parametrize("key, value, row", [
    ("trace_capacity", None, "entry key"),
    ("trace_capacity", "many", "entry key"),
    ("integer_ledger", {}, "entry key"),
    ("host_patch", {"id": "second_halves_declared_order", "change": "x"}, "host_patch/restart"),
    ("restart", {"time_s": 1.0, "step_index": 3, "through": "x"}, "host_patch/restart"),
    ("refusal", {"kind": "domain", "message": "x", "time_s": 1.0}, "status"),
])
def test_an_entry_fault_refuses_the_run(base, tmp_path, key, value, row) -> None:
    sc = Scenario(base)
    name = sc.name("W6 gene-first", 2, 2)
    if value is None:
        del sc.entry(name)[key]
    else:
        sc.entry(name)[key] = value
    record = sc.run(str(tmp_path))
    assert row in issues(record, name)
    assert fam(record, "W6 gene-first") == "inconclusive"
    assert s_outcome(record, "W6 gene-first", "lost")["outcome"] == "unformed"


def test_a_refused_run_without_a_refusal_and_a_truncated_trace(base, tmp_path) -> None:
    sc = Scenario(base)
    a, b = sc.name("W5 reactions-first", 1, 1), sc.name("W5 population-first", 5, 0)
    sc.entry(a)["status"] = "refused"
    sc.entry(b)["trace_capacity"] = 3
    record = sc.run(str(tmp_path))
    kinds = {r.get("kind") for r in record["refusals_and_flags"] if r.get("run") in (a, b)}
    assert kinds == {"harness", None} or "harness" in kinds
    assert "truncated" in issues(record, b) and "status" in issues(record, a)
    assert record["arms"]["W5"]["verdict"] == "inconclusive"


def test_a_completed_run_whose_t_departs(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5-exact population-first", 1, 3)
    sc.entry(name)["t"][4] *= 1 + 1e-9
    record = sc.run(str(tmp_path))
    assert "samples" in issues(record, name)
    assert fam(record, "W5-exact population-first") == "inconclusive"


def test_a_t_within_1e12_is_the_registered_sample(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5-exact population-first", 1, 3)
    sc.entry(name)["t"][4] *= 1 + 1e-13
    record = sc.run(str(tmp_path))
    assert "samples" not in issues(record, name) and record["claim"] == "pass"


@pytest.mark.parametrize("how", ["missing name", "nan", "short", "missing list"])
def test_the_missing_leaf_unforms_only_what_reads_it(base, tmp_path, how) -> None:
    sc = Scenario(base)
    name = sc.name("W5 reactions-first", 4, 2)
    entry = sc.entry(name)
    if how == "missing name":
        del entry["series"]["xi_2"]
    elif how == "nan":
        entry["series"]["xi_2"][3] = float("nan")
    elif how == "short":
        entry["series"]["xi_2"] = entry["series"]["xi_2"][:-1]
    else:
        del entry["events"]["channel"]
    if how == "nan":
        sc.raw_text["table_W5.json"] = json.dumps(sc.tables["table_W5.json"])
    record = sc.run(str(tmp_path))
    assert "missing leaf" in issues(record, name)
    if how == "missing list":
        assert outcome(record, name, "E trace") == ["unformed"]
        assert s_outcome(record, "W5 reactions-first", "t_events")["outcome"] == "unformed"
        assert s_outcome(record, "W5 reactions-first", "xi_2")["outcome"] == "pass"
    else:
        assert s_outcome(record, "W5 reactions-first", "xi_2")["outcome"] == "unformed"
        assert outcome(record, name, "R identity Y") == ["unformed"]
        assert outcome(record, name, "R identity X") == ["pass"]
        assert s_outcome(record, "W5 reactions-first", "t_events")["outcome"] == "pass"
    assert fam(record, "W5 reactions-first") == "inconclusive"


@pytest.mark.parametrize("how", ["counts", "total", "few"])
def test_a_record_that_contradicts_itself(base, tmp_path, how) -> None:
    sc = Scenario(base)
    name = sc.name("W6 population-first", 0, 3)
    ev = sc.entry(name)["events"]
    if how == "counts":
        ev["counts_after"][2] = list(ev["counts_after"][1])
    elif how == "total":
        sc.entry(name)["events_total"] += 1
    else:
        for key in ("time_s", "channel", "counts_after"):
            ev[key] = ev[key][:5]
        sc.entry(name)["events_total"] = 5
    record = sc.run(str(tmp_path))
    assert outcome(record, name, "E trace") == ["fail"]
    assert s_outcome(record, "W6 population-first", "t_events")["outcome"] == "unformed"
    assert fam(record, "W6 population-first") == "fail"


@pytest.mark.parametrize("how", ["time", "first_index", "samples", "events"])
def test_a_resumed_run_at_another_checkpoint_is_refused(base, tmp_path, how) -> None:
    sc = Scenario(base)
    restart = [s.name for s in sc.inputs.run_list if s.variant == "restart" and s.world == "W5"][0]
    entry = sc.entry(restart)
    if how == "time":
        entry["restart"]["time_s"] *= 1 + 1e-9
    elif how == "first_index":
        entry["events"]["first_index"] += 1
    elif how == "samples":
        entry["t"] = entry["t"][1:]
        entry["series"] = {k: v[1:] for k, v in entry["series"].items()}
        entry["integer_ledger"] = entry["integer_ledger"][1:]
    else:
        for key in ("time_s", "channel", "counts_after"):
            entry["events"][key] = entry["events"][key][:-1]
    record = sc.run(str(tmp_path))
    assert "resumed run" in issues(record, restart)
    unint = sc.inputs.data["restart"]["W5"]["run"]
    assert outcome(record, unint, "E restart")[0] in ("unformed", "fail")
    assert fam(record, "W5 reactions-first") in ("inconclusive", "fail")
    if how == "time":
        assert fam(record, "W5 reactions-first") == "inconclusive"


def test_provenance_refuses_but_a_miss_still_fails(base, tmp_path) -> None:
    sc = Scenario(base)
    family = "W6 population-first"
    dirty = sc.name(family, 5, 0)
    sc.entry(dirty)["source"]["checkout_dirty"] = True
    record = sc.run(str(tmp_path))
    assert "provenance" in issues(record, dirty)
    assert s_outcome(record, family, "lost")["outcome"] == "unformed"
    assert fam(record, family) == "inconclusive"
    # the same refusal beside a size miss: compared all the same, and the miss fails
    sc2 = Scenario(base)
    sc2.entry(dirty)["source"]["checkout_dirty"] = True
    for c in range(sc2.inputs.worlds["W6"].copies):
        for rung in range(6):
            e = sc2.entry(sc2.name(family, rung, c))
            e["events"]["time_s"] = [t + 3e-4 for t in e["events"]["time_s"]]
    record = sc2.run(str(tmp_path / "b"))
    assert s_outcome(record, family, "t_events")["outcome"] == "fail"
    assert fam(record, family) == "fail"


def test_the_engine_revision_outside_the_rehearsal(base, tmp_path) -> None:
    sc = Scenario(base)
    sc.rehearsal = False
    sc.revision = "e" * 40
    record = sc.run(str(tmp_path))
    assert record["claim"] == "inconclusive"
    sc.revision = fabricate.REVISION
    assert sc.run(str(tmp_path / "b"))["claim"] == "pass"


@pytest.mark.parametrize("kind, verdict", [("check", "fail"), ("domain", "inconclusive"), ("harness", "inconclusive")])
def test_a_judged_run_refused_with_a_kind(base, tmp_path, kind, verdict) -> None:
    sc = Scenario(base)
    name = sc.name("W5 population-first", 3, 1)
    sc.entry(name)["status"] = "refused"
    sc.entry(name)["refusal"] = {"kind": kind, "message": "fabricated", "time_s": 7.0}
    record = sc.run(str(tmp_path))
    assert fam(record, "W5 population-first") == verdict
    assert outcome(record, name, "D") == (["fail"] if kind == "check" else ["unformed"])


@pytest.mark.parametrize("how", ["in missing", "in neither", "missing and runs", "two tables", "twice in runs"])
def test_missing_and_doubled_names(base, tmp_path, how) -> None:
    sc = Scenario(base)
    name = sc.name("W5-exact reactions-first", 0, 1)
    table = sc.table_of(name)
    if how == "in missing":
        del table["runs"][name]
        table["missing"].append(name)
    elif how == "in neither":
        del table["runs"][name]
    elif how == "missing and runs":
        table["missing"].append(name)
    elif how == "two tables":
        sc.tables["table_W6.json"]["runs"][name] = copy.deepcopy(table["runs"][name])
    else:  # the same name twice in one runs, the first entry with a miss: each is judged and its fail stands
        text = json.dumps(table)
        shadowed = copy.deepcopy(table["runs"][name])
        shadowed["events"]["time_s"][2] += 1e-9
        key = json.dumps(name)
        sc.raw_text["table_W5-exact.json"] = text.replace(f"{key}: ", f"{key}: {json.dumps(shadowed)}, {key}: ", 1)
    record = sc.run(str(tmp_path))
    rows = issues(record, name)
    assert ("missing" in rows) if how in ("in missing", "in neither") else ("listed twice" in rows or "echo" in rows)
    if how == "twice in runs":
        assert outcome(record, name, "R t_events") == ["fail", "unformed"]
        assert fam(record, "W5-exact reactions-first") == "fail"
    else:
        assert fam(record, "W5-exact reactions-first") == "inconclusive"


def test_unregistered_names_and_an_unowed_retry(base, tmp_path) -> None:
    sc = Scenario(base)
    sc.tables["table_W5.json"]["runs"]["W5 sideways-first h=1 c0"] = {}
    retry_name = next(iter(sc.retry_tables["table_W5-retry.json"]["runs"]))
    sc.tables["table_W5.json"]["runs"][retry_name] = sc.retry_tables["table_W5-retry.json"]["runs"][retry_name]
    record = sc.run(str(tmp_path))
    rows = {(r.get("run"), r.get("row")) for r in record["refusals_and_flags"]}
    assert ("W5 sideways-first h=1 c0", "unregistered") in rows and (retry_name, "unowed retry") in rows
    assert record["claim"] == "pass"


def test_a_missing_support_run_unforms_the_restart_alone(base, tmp_path) -> None:
    sc = Scenario(base)
    restart = [s.name for s in sc.inputs.run_list if s.variant == "restart" and s.world == "W6"][0]
    del sc.table_of(restart)["runs"][restart]
    record = sc.run(str(tmp_path))
    unint = sc.inputs.data["restart"]["W6"]["run"]
    assert outcome(record, unint, "E restart") == ["unformed"]
    assert fam(record, "W6 gene-first") == "inconclusive" and fam(record, "W6 population-first") == "pass"


def test_recorded_only_leaves_are_flagged_only(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W6 gene-first", 0, 0)
    sc.entry(name)["steps"] = 7
    sc.entry(name)["samples_echo"] = [1.0]
    sc.entry(name)["definition"] = {"note": float("nan")}
    sc.raw_text["table_W6.json"] = json.dumps(sc.tables["table_W6.json"])
    record = sc.run(str(tmp_path))
    assert record["claim"] == "pass"
    flags = [r for r in record["refusals_and_flags"] if r.get("run") == name]
    assert {r["where"] for r in flags} >= {"definition/note", "steps", "samples_echo"}


@pytest.mark.parametrize("key, value, refused", [
    ("definition", "delete", True), ("checks", "delete", True), ("pools_at_event", "delete", True),
    ("samples_echo", "delete", True), ("steps", "delete", True), ("checks", 5, True), ("checks", None, True),
    ("samples_echo", {"t": 1.0}, True), ("definition", [1, 2], True),
    ("pools_at_event", None, False), ("steps", "seven", False),
])
def test_ruling_2b_a_recorded_only_key_itself(base, tmp_path, key, value, refused) -> None:
    sc = Scenario(base)
    name = sc.name("W5 population-first", 2, 3)
    if value == "delete":
        del sc.entry(name)[key]
    else:
        sc.entry(name)[key] = value
    record = sc.run(str(tmp_path))
    if refused:
        assert "entry key" in issues(record, name)
        assert fam(record, "W5 population-first") == "inconclusive"
    else:
        assert "entry key" not in issues(record, name) and record["claim"] == "pass"


def test_ruling_2c_a_null_definition_in_a_completed_run(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W6 population-first", 1, 2)
    sc.entry(name)["definition"] = None
    record = sc.run(str(tmp_path))
    assert "entry key" in issues(record, name) and fam(record, "W6 population-first") == "inconclusive"
    # refused by its key: compared all the same, and a miss fails
    sc.entry(name)["series"]["n_Pi"][3] *= 1 + 1e-6
    record = sc.run(str(tmp_path / "miss"))
    assert outcome(record, name, "R identity Pi") == ["fail"] and fam(record, "W6 population-first") == "fail"


@pytest.mark.parametrize("key, value", [("snapshot_patch_sha256", ""), ("python", ""), ("machine", None),
                                        ("jax", 3), ("blas_threads", "1"), ("numpy", "delete")])
def test_ruling_15_provenance_incomplete(base, tmp_path, key, value) -> None:
    sc = Scenario(base)
    name = sc.name("W5 reactions-first", 5, 1)
    if value == "delete":
        del sc.entry(name)["source"][key]
    else:
        sc.entry(name)["source"][key] = value
    record = sc.run(str(tmp_path))
    assert "provenance" in issues(record, name)
    assert fam(record, "W5 reactions-first") == "inconclusive"


def test_a_duplicate_key_in_an_entry_and_a_non_finite_elsewhere(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5 reactions-first", 2, 3)
    text = json.dumps(sc.tables["table_W5.json"])
    entry_key = json.dumps(name)
    position = text.index(entry_key)
    text = text[:position] + text[position:].replace('"status": ', '"status": "completed", "status": ', 1)
    sc.raw_text["table_W5.json"] = text
    sc.tables["table_W6.json"]["note"] = float("nan")
    sc.raw_text["table_W6.json"] = json.dumps(sc.tables["table_W6.json"])
    record = sc.run(str(tmp_path))
    assert "duplicate key" in issues(record, name)
    assert fam(record, "W5 reactions-first") == "inconclusive"
    assert record["arms"]["W6"]["verdict"] == "inconclusive"
    assert record["arms"]["W5-exact"]["verdict"] == "pass"


# ---- S: size, order, the zero difference, and the retry ----

def test_a_wrong_law_misses_its_size(base, tmp_path) -> None:
    sc = Scenario(base)
    family = "W5 population-first"
    for c in range(4):
        for rung in range(6):
            e = sc.entry(sc.name(family, rung, c))
            e["events"]["time_s"] = [t + 2e-6 for t in e["events"]["time_s"]]
    record = sc.run(str(tmp_path))
    entry = s_outcome(record, family, "t_events")
    assert entry["outcome"] == "fail" and 1.5 <= entry["q"] <= 2.5
    assert fam(record, family) == "fail"


def test_a_named_entry_is_judged_by_its_size_alone(base, tmp_path) -> None:
    sc = Scenario(base)
    family = "W6 gene-first"
    for c in range(4):
        for rung in range(6):
            e = sc.entry(sc.name(family, rung, c))
            # made, with every row that reads it, moved alike (the identities stay closed)
            delta = 1e-12
            e["series"]["made"] = [v + (delta if i else 0.0) for i, v in enumerate(e["series"]["made"])]
            e["series"]["n_R_c"] = [v + (delta if i else 0.0) for i, v in enumerate(e["series"]["n_R_c"])]
            e["series"]["engaged"] = [v - (delta if i else 0.0) for i, v in enumerate(e["series"]["engaged"])]
            e["series"]["free"] = [v + (delta if i else 0.0) for i, v in enumerate(e["series"]["free"])]
            r, big_l = sc.inputs.gene_r_and_l("W6")
            e["series"]["transit"] = [v - (big_l * delta if i else 0.0) for i, v in enumerate(e["series"]["transit"])]
    record = sc.run(str(tmp_path))
    entry = s_outcome(record, family, "made")
    assert entry["outcome"] == "fail" and entry["q"] is None
    assert all(o == "pass" for o in outcome(record, sc.name(family, 0, 0), "R identity engaged"))


def test_a_first_order_family_owes_the_retry_and_the_retry_scores_it(base, tmp_path) -> None:
    sc = Scenario(base)
    family = "W5 reactions-first"
    world = sc.inputs.worlds["W5"]
    # the coarsest rung alone perturbed (CRITERIA.md §10's rehearsal input): its order leaves the window
    for c in range(world.copies):
        e = sc.entry(sc.name(family, 0, c))
        e["events"]["time_s"] = [t + (2e-4 if k % 2 else -2e-4) for k, t in enumerate(e["events"]["time_s"])]
    first = sc.run(str(tmp_path))
    entry = s_outcome(first, family, "t_events")
    assert entry["outcome"] == "inconclusive" and entry["owes_retry"]
    owed = retry_owed_file(first)
    assert owed["families"] == [family] and len(owed["runs"]) == world.copies
    assert first["plants"]["P4"]["score"] == "unscorable"
    second = sc.run(str(tmp_path / "retry"), retry_owed=owed, with_retry_tables=True)
    entry = s_outcome(second, family, "t_events")
    assert entry["outcome"] == "pass" and entry["retried"] and entry["rungs"][-1] == sc.inputs.families[
        family].retry_rung
    assert second["claim"] == "pass"
    assert second["plants"]["P4"]["score"] == "caught"
    # a missing owed retry run leaves its entries inconclusive
    del sc.retry_tables["table_W5-retry.json"]["runs"][owed["runs"][0]]
    third = sc.run(str(tmp_path / "retry2"), retry_owed=owed, with_retry_tables=True)
    assert s_outcome(third, family, "t_events")["outcome"] == "unformed"


def test_a_zero_step_difference_is_inconclusive_and_owes_nothing(base, tmp_path) -> None:
    sc = Scenario(base)
    family = "W6 population-first"
    for c in range(4):
        sc.entry(sc.name(family, 3, c))["events"]["time_s"] = list(sc.entry(sc.name(family, 2, c))["events"]["time_s"])
    record = sc.run(str(tmp_path))
    entry = s_outcome(record, family, "t_events")
    assert entry["outcome"] == "inconclusive" and not entry["owes_retry"]
    assert record["retry_owed"]["families"] == []


def test_a_copied_family_does_not_differ(base, tmp_path) -> None:
    sc = Scenario(base)
    for c in range(4):
        a = sc.entry(sc.name("W5 reactions-first", 0, c))
        b = sc.entry(sc.name("W5 population-first", 0, c))
        b["events"]["time_s"] = list(a["events"]["time_s"])
    record = sc.run(str(tmp_path))
    pair = [e for e in record["entries"] if e["entry"] == "pair t_events" and "W5 reactions-first" in e["families"]]
    assert pair[0]["outcome"] == "inconclusive"
    assert fam(record, "W5 reactions-first") == "inconclusive" and fam(record, "W5 population-first") == "inconclusive"


def test_w5_exact_rungs_that_are_one(base, tmp_path) -> None:
    sc = Scenario(base)
    family = "W5-exact population-first"
    for c in range(4):
        fine = sc.entry(sc.name(family, 1, c))
        coarse = sc.entry(sc.name(family, 0, c))
        fine["series"] = copy.deepcopy(coarse["series"])
    record = sc.run(str(tmp_path))
    rungs = [e for e in record["entries"] if e["entry"] == "rungs n_S_c" and e["family"] == family]
    assert rungs[0]["outcome"] == "inconclusive"
    assert fam(record, family) == "inconclusive" and fam(record, "W5-exact reactions-first") == "pass"


def test_w5_exact_times_off_by_more_than_rounding(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5-exact reactions-first", 1, 2)
    sc.entry(name)["events"]["time_s"][3] += 1e-10
    record = sc.run(str(tmp_path))
    assert outcome(record, name, "R t_events") == ["fail"]
    assert record["arms"]["W5-exact"]["verdict"] == "fail"


def test_w5_exact_running_check_unforms_the_identities(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5-exact population-first", 0, 0)
    entry = sc.entry(name)
    start = {k: entry["series"][k][0] for k in entry["series"]}
    books = {k: [0.4 * v for v in entry["series"][k]] for k in ("xi_1", "xi_2", "moved")}
    entry["series"] = fabricate._rows_from_books(sc.inputs, "W5-exact", start, books, {})
    record = sc.run(str(tmp_path))
    assert set(outcome(record, name, "R identity X")) == {"unformed"}
    assert fam(record, "W5-exact population-first") == "inconclusive"


# ---- plants ----

def test_a_second_order_lie_run_is_not_caught(base, tmp_path) -> None:
    sc = Scenario(base)
    lie = [s for s in sc.inputs.run_list if s.variant == "second halves in declared order"]
    for spec in lie:
        honest = sc.entry(spec.name.replace(" lie", ""))
        sc.entry(spec.name)["events"]["time_s"] = list(honest["events"]["time_s"])
    record = sc.run(str(tmp_path))
    assert record["plants"]["P3"]["score"] == "not caught"
    assert record["arms"]["W5"]["verdict"] == "fail"


def test_a_missing_lie_run_leaves_p3_unscorable(base, tmp_path) -> None:
    sc = Scenario(base)
    lie = [s.name for s in sc.inputs.run_list if s.variant == "second halves in declared order"][0]
    del sc.table_of(lie)["runs"][lie]
    record = sc.run(str(tmp_path))
    assert record["plants"]["P3"]["score"] == "unscorable"
    assert record["arms"]["W5"]["verdict"] == "inconclusive"


def test_p4_is_not_caught_when_the_honest_tolerance_exceeds_its_shift(base, tmp_path) -> None:
    sc = Scenario(base)
    family = "W5 population-first"
    world = sc.inputs.worlds["W5"]
    ref = sc.raw["W5"]["copies"]
    for c in range(world.copies):
        for rung in range(6):
            e = sc.entry(sc.name(family, rung, c))
            e["events"]["time_s"] = [r + 40 * (t - r) for t, r in zip(e["events"]["time_s"], ref[c]["events"]["time_s"])]
    record = sc.run(str(tmp_path))
    assert s_outcome(record, family, "t_events")["outcome"] == "pass"
    p4 = [r for r in record["plants"]["P4"]["entries"] if r["family"] == family][0]
    assert p4["score"] == "not caught"
    assert record["arms"]["W5"]["verdict"] == "fail"


def test_a_record_plant_needs_its_honest_entry(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W6 gene-first", 0, 0)
    sc.entry(name)["series"]["n_Pi"][4] *= 1 + 1e-6
    record = sc.run(str(tmp_path))
    assert record["plants"]["P13"]["score"] == "unscorable"
    assert outcome(record, name, "R identity Pi") == ["fail"]


# ---- the structure-only read (TABLE.md §5) and the engine boundary ----

def _meaningless(value):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return 7
    if isinstance(value, float):
        return 0.123
    if isinstance(value, list):
        return [_meaningless(v) for v in value]
    return {k: _meaningless(v) for k, v in value.items()}


def test_the_structure_only_read(base, tmp_path) -> None:
    sc = Scenario(base)
    sample = {name: _meaningless(t) for name, t in sc.tables.items()}
    for name, t in sample.items():
        t["arm"] = sc.tables[name]["arm"]
    retry = {name: _meaningless(t) for name, t in sc.retry_tables.items()}
    for name, t in retry.items():
        t["arm"] = sc.retry_tables[name]["arm"]
    fabricate.write(str(tmp_path / "table"), sample)
    fabricate.write(str(tmp_path / "table-retry"), retry)
    report = format_sample(str(tmp_path), sc.inputs)
    assert report["passes"], report["folders"]["table"]["departures"][:3]
    kinds = report["folders"]["table"]["entry_kinds"]
    assert any("refusal definition" in k for k in kinds) and any("host_patch" in k for k in kinds)
    first = next(iter(sample["table_W5.json"]["runs"]))
    sample["table_W5.json"]["runs"][first]["copy"] = "zero"
    del sample["table_W5.json"]["runs"][first]["series"]["xi_1"]
    fabricate.write(str(tmp_path / "table"), sample)
    report = format_sample(str(tmp_path), sc.inputs)
    wheres = {d["where"] for d in report["folders"]["table"]["departures"]}
    assert not report["passes"] and {"copy", "series/xi_1"} <= wheres


def test_nothing_of_the_engine_is_imported(base, tmp_path) -> None:
    Scenario(base).run(str(tmp_path))
    assert not [m for m in sys.modules if m == "cells" or m.startswith("cells.")]


# ---- the lead's rulings of 26 November: 6b and 6c with CRITERIA:321, 16, 19, 14 and 7 ----

def test_ruling_6c_a_lie_run_whose_t_events_cannot_be_formed(base, tmp_path) -> None:
    sc = Scenario(base)
    lie = [s.name for s in sc.inputs.run_list if s.variant == "second halves in declared order"][5]
    entry = sc.entry(lie)
    for key in ("time_s", "channel", "counts_after"):
        entry["events"][key] = entry["events"][key][:4]
    entry["events_total"] = 4
    record = sc.run(str(tmp_path))
    assert record["plants"]["P3"]["score"] == "unscorable"
    assert record["arms"]["W5"]["verdict"] == "inconclusive"


def _make_inconclusive(sc: Scenario, family: str) -> None:
    """Two rungs that are one series: the family's t_events is inconclusive and owes nothing."""
    for c in range(sc.inputs.worlds[sc.inputs.families[family].world].copies):
        sc.entry(sc.name(family, 3, c))["events"]["time_s"] = list(sc.entry(sc.name(family, 2, c))["events"]["time_s"])


def _widen(sc: Scenario, family: str, factor: float) -> None:
    """The family's errors in t_events multiplied (order unchanged): its tau grows past P4's shift."""
    world = sc.inputs.families[family].world
    ref = sc.raw[world]["copies"]
    for c in range(sc.inputs.worlds[world].copies):
        for rung in range(6):
            e = sc.entry(sc.name(family, rung, c))
            e["events"]["time_s"] = [r + factor * (t - r) for t, r in zip(e["events"]["time_s"],
                                                                           ref[c]["events"]["time_s"])]


@pytest.mark.parametrize("other, expected", [("honest", "unscorable"), ("widened", "not caught")])
def test_criteria_321_on_a_plant_with_an_unscorable_entry(base, tmp_path, other, expected) -> None:
    sc = Scenario(base)
    _make_inconclusive(sc, "W5 reactions-first")
    if other == "widened":
        _widen(sc, "W5 population-first", 40.0)
    record = sc.run(str(tmp_path))
    rows = {r["family"]: r["score"] for r in record["plants"]["P4"]["entries"]}
    assert rows["W5 reactions-first"] == "unscorable"
    assert rows["W5 population-first"] == ("caught" if other == "honest" else "not caught")
    assert record["plants"]["P4"]["score"] == expected


def _p5_planted_as_honest(sc: Scenario, family: str, shift: float | None) -> None:
    """P5's planted reference of a family set to the honest one, with one event moved by `shift` if given."""
    sc.refs = copy.deepcopy(sc.refs) if not getattr(sc, "_refs_copied", False) else sc.refs
    sc._refs_copied = True
    ref = sc.refs["W5-exact"]
    for c, pc in zip(ref.copies, ref.planted["P5"][family]):
        pc.times, pc.channels, pc.counts = list(c.times), list(c.channels), list(c.counts)
        pc.K, pc.K_all = c.K, c.K_all
        if shift is not None and c.copy == 0:
            pc.times[3] += shift


@pytest.mark.parametrize("case, expected", [("one event over its bound in each family", "caught"),
                                            ("no event over its bound in one family", "not caught"),
                                            ("one family unscorable, the other caught", "unscorable"),
                                            ("one family unscorable, the other not caught", "not caught")])
def test_ruling_16_p5(base, tmp_path, case, expected) -> None:
    sc = Scenario(base)
    a, b = "W5-exact reactions-first", "W5-exact population-first"
    if case == "one event over its bound in each family":
        _p5_planted_as_honest(sc, a, 1e-6)
        _p5_planted_as_honest(sc, b, 1e-6)
    elif case == "no event over its bound in one family":
        _p5_planted_as_honest(sc, b, None)
    else:
        sc.entry(sc.name(a, 1, 2))["events"]["time_s"][3] += 1e-10  # a's honest R t_events fails
        if case.endswith("not caught"):
            _p5_planted_as_honest(sc, b, None)
    record = sc.run(str(tmp_path))
    assert record["plants"]["P5"]["score"] == expected, record["plants"]["P5"]


def test_ruling_19_a_run_found_only_in_another_worlds_table(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5-exact population-first", 1, 0)
    sc.tables["table_W6.json"]["runs"][name] = sc.table_of(name)["runs"].pop(name)
    record = sc.run(str(tmp_path))
    assert "missing" in issues(record, name)
    assert any(r.get("row") == "another world's table" and r.get("run") == name for r in record["refusals_and_flags"])
    assert set(outcome(record, name, "R t_events")) == {"unformed"}
    assert fam(record, "W5-exact population-first") == "inconclusive" and record["arms"]["W6"]["verdict"] == "pass"


def test_ruling_14_every_negative_zero_r_accepts_is_listed(base, tmp_path) -> None:
    sc = Scenario(base)
    name = sc.name("W5 reactions-first", 0, 1)
    sc.entry(name)["series"]["xi_1"][0] = -0.0
    record = sc.run(str(tmp_path))
    assert outcome(record, name, "R start xi_1") == ["pass"] and record["claim"] == "pass"
    listed = {(r["run"], r["entry"], r["leaf"], r["index"]) for r in record["r_negative_zeros"]}
    assert (name, "R start xi_1", "xi_1", 0) in listed and (name, "R identity X", "xi_1", 0) in listed


def test_ruling_7_the_judge_stops_on_a_c0_finding(base, tmp_path) -> None:
    import shutil

    import run_judge

    refs = tmp_path / "refs"
    refs.mkdir()
    for name in ("inputs_invented.json", "draws_invented.json"):
        shutil.copy(os.path.join(OUT, name), refs / name)
    data = json.load(open(os.path.join(OUT, "reference_invented.json")))
    data["W5"]["scales"]["n_S_c"] *= 1.001  # the judge's recomputed scale disagrees: a finding
    (refs / "reference_invented.json").write_text(json.dumps(data))
    sc = Scenario(base)
    fabricate.write(str(tmp_path / "table"), sc.tables)
    (tmp_path / "operators.json").write_text(json.dumps(sc.operators))
    argv = ["--inputs", str(refs / "inputs_invented.json"), "--references", str(refs), "--invented",
            "--tables", str(tmp_path / "table"), "--operators", str(tmp_path / "operators.json"), "--rehearsal"]
    assert run_judge.main(argv + ["--out", str(tmp_path / "stopped")]) == 3
    assert (tmp_path / "stopped" / "c0_findings.json").exists()
    assert not (tmp_path / "stopped" / "record.json").exists()
    assert run_judge.main(argv + ["--out", str(tmp_path / "go"), "--proceed-after-findings"]) == 0
    assert json.load(open(tmp_path / "go" / "record.json"))["claim"] == "pass"


# ---- the rehearsal's tools (CRITERIA.md §10, SPEC.md §8): the planter, and the perturbed coarsest rung ----

def test_rehearsal_planter_every_fault_is_flagged_as_section_4_says(base, tmp_path) -> None:
    import re

    from cowriter_judge.rehearsal import catalog, check, write_planted

    sc = Scenario(base)
    honest = sc.run(str(tmp_path / "honest"))
    planted = catalog(sc.inputs, sc.tables, sc.retry_tables, lambda w, c: sc.refs[w].copies[c].K)
    misses, lines = {}, set()
    for item in planted:
        folder = tmp_path / re.sub(r"[^A-Za-z0-9]+", "_", item.id)
        driver = write_planted(item, str(folder))
        retry_dir = str(folder / "table-retry") if item.retry_tables else None
        record = judge_pass(sc.inputs, sc.refs, str(folder / "table"), sc.operators, None, True,
                            driver["lead_record"], set(driver["sample_hashes"]), retry_dir)
        found = check(record, honest, item.expect)
        if found:
            misses[item.id] = found
        if not check(honest, honest, item.expect):  # the expectation is not met by the honest record itself
            misses[item.id] = ["the expectation does not tell the planted record from the honest one"]
        lines |= {int(x) for x in re.findall(r"\d{3}", item.lines)}
    assert not misses, misses
    assert len(planted) == 53
    assert set(range(180, 203)) <= lines, sorted(set(range(180, 203)) - lines)


def test_rehearsal_perturbed_coarsest_rung_owes_the_retry(base, tmp_path) -> None:
    from cowriter_judge.rehearsal import perturb_coarsest_rung

    sc = Scenario(base)
    perturbed, info = perturb_coarsest_rung(sc.inputs, sc.refs, sc.tables)
    assert info["family"] == "W5 reactions-first" and 1.5 <= info["honest_q"] <= 2.5
    assert not 1.5 <= info["perturbed_q"] <= 2.5
    sc.tables = perturbed
    first = sc.run(str(tmp_path / "first"))
    owed = retry_owed_file(first)
    assert owed["families"] == ["W5 reactions-first"] and owed["runs"] == sorted(info["retry_runs"])
    second = sc.run(str(tmp_path / "retry"), retry_owed=owed, with_retry_tables=True)
    assert s_outcome(second, "W5 reactions-first", "t_events")["outcome"] == "pass" and second["claim"] == "pass"
