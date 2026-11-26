"""The rehearsal's inputs (CRITERIA.md §10; SPEC.md §8), made from an honest invented table set.

- `catalog()` plants every fault of CRITERIA.md §4's table, each in its own copy of the honest tables, with what §4
  says the judge must do (`expect`). `check()` compares a judge record with it, against the honest record.
- `perturb_coarsest_rung()` makes the copy in which one family's coarsest rung is perturbed so that its order leaves
  the window, so that the retry is owed and its scoring path is run (SPEC.md §8, CRITERIA.md §7 and §10). Every event
  time of that family's runs at h_1 moves by one constant, which keeps each trace's order, channels and counts, and
  touches no row, book or identity.

Targets are chosen by their registered names in the inputs file; nothing here reads the engine or a reference value
beyond K_c. The honest copies are deep-copied: the inputs to this module are never changed.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from .registry import Inputs
from .stats import ladder
from .table import LIE_PATCH_ID

LIE = "second halves in declared order"


@dataclass
class Planted:
    id: str
    row: str  # CRITERIA.md §4's row, in short
    lines: str  # CRITERIA.md lines
    change: str
    tables: dict
    retry_tables: dict = field(default_factory=dict)
    raw_text: dict = field(default_factory=dict)  # table file name -> exact text (parse-level faults)
    sums_edit: dict = field(default_factory=dict)  # table file name -> digest ("" drops its line)
    drop_sums: bool = False
    lead_record_edit: dict | None = None  # table file name -> digest; the honest digests for the rest
    sample_table: str | None = None  # a table whose own sha256 the driver passes as a format sample's
    expect: dict = field(default_factory=dict)

    def manifest(self) -> dict:
        return {"id": self.id, "row": self.row, "lines": self.lines, "change": self.change, "expect": self.expect,
                "driver": {"lead_record": self.lead_record_edit is not None, "sample_table": self.sample_table,
                           "retry_tables": bool(self.retry_tables)}}


def _text(table: dict) -> str:
    return json.dumps(table)


def write_tables(folder: str, tables: dict, raw_text: dict | None = None, sums_edit: dict | None = None,
                 drop_sums: bool = False) -> dict[str, str]:
    """Each table as JSON (or its exact planted text) and SHA256SUMS; returns the honest digests of what was written."""
    os.makedirs(folder, exist_ok=True)
    digests = {}
    for name, table in tables.items():
        text = (raw_text or {}).get(name, _text(table))
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(text)
        digests[name] = hashlib.sha256(text.encode()).hexdigest()
    if not drop_sums:
        lines = {**digests, **(sums_edit or {})}
        with open(os.path.join(folder, "SHA256SUMS"), "w", encoding="utf-8") as handle:
            for name in sorted(lines):
                if lines[name]:
                    handle.write(f"{lines[name]}  {name}\n")
    return digests


def write_planted(planted: Planted, folder: str) -> dict:
    """The planted copy in `folder` (table/, table-retry/, driver.json); returns the driver's extra inputs."""
    digests = write_tables(os.path.join(folder, "table"), planted.tables, planted.raw_text, planted.sums_edit,
                           planted.drop_sums)
    if planted.retry_tables:
        write_tables(os.path.join(folder, "table-retry"), planted.retry_tables)
    driver: dict[str, Any] = {"lead_record": None, "sample_hashes": []}
    if planted.lead_record_edit is not None:
        driver["lead_record"] = {**digests, **planted.lead_record_edit}
    if planted.sample_table is not None:
        driver["sample_hashes"] = [digests[planted.sample_table]]
    with open(os.path.join(folder, "driver.json"), "w", encoding="utf-8") as handle:
        json.dump({**driver, "manifest": planted.manifest()}, handle, indent=1, sort_keys=True)
    return driver


# ---- the catalog of CRITERIA.md §4's faults ----


class _Names:
    def __init__(self, inputs: Inputs, tables: dict) -> None:
        self.inputs = inputs
        self.tables = tables

    def judged(self, family: str, rung: int, copy_: int) -> str:
        fam = self.inputs.families[family]
        return self.inputs.judged_run(family, fam.rungs[rung], copy_)

    def restart(self, world: str) -> tuple[str, str]:
        resumed = [s.name for s in self.inputs.run_list if s.variant == "restart" and s.world == world][0]
        return resumed, self.inputs.data["restart"][world]["run"]

    def lie(self, index: int) -> str:
        return [s.name for s in self.inputs.run_list if s.variant == LIE][index]

    @staticmethod
    def table_of(tables: dict, name: str) -> str:
        for file_name, table in tables.items():
            if name in table.get("runs", {}):
                return file_name
        raise KeyError(name)


def _entry(tables: dict, name: str) -> dict:
    return tables[_Names.table_of(tables, name)]["runs"][name]


def _issue(run: str, row: str, effect: str) -> list:
    return [run, row, effect]


def catalog(inputs: Inputs, honest_tables: dict, honest_retry: dict | None = None,
            k_c: Callable[[str, int], int] | None = None) -> list[Planted]:
    """Every fault of CRITERIA.md §4 in its own copy. `k_c(world, copy)` is the reference's K_c (for the fault of
    fewer than K_c events; without it the record is cut to 3 events)."""
    names = _Names(inputs, honest_tables)
    f5r, f5p = "W5 reactions-first", "W5 population-first"
    x_r, x_p = "W5-exact reactions-first", "W5-exact population-first"
    f6g, f6p = "W6 gene-first", "W6 population-first"
    out: list[Planted] = []

    def add(fid: str, row: str, lines: str, change: str, mutate: Callable[[Planted], None], expect: dict,
            with_retry: bool = False) -> None:
        planted = Planted(id=fid, row=row, lines=lines, change=change, tables=copy.deepcopy(honest_tables),
                          retry_tables=copy.deepcopy(honest_retry) if (with_retry and honest_retry) else {},
                          expect=expect)
        mutate(planted)
        out.append(planted)

    def edit(name: str, fn: Callable[[dict], None]) -> Callable[[Planted], None]:
        return lambda p: fn(_entry(p.tables, name))

    # --- the echo, and the table's hash: nothing of the run is judged (CRITERIA.md:180-181) ---
    r = names.judged(f5r, 3, 0)
    add("echo departs", "The echo departs from the registered run", "180",
        f"{r}: inputs.cell_pL x (1 + 1e-9)",
        edit(r, lambda e: e["inputs"].__setitem__("cell_pL", e["inputs"]["cell_pL"] * (1 + 1e-9))),
        {"issues": [_issue(r, "echo", "nothing")], "families": {f5r: "not pass"},
         "entries": [{"run": r, "entry": "E trace", "outcome": "unformed"}]})
    some_x = names.judged(x_r, 0, 0)
    for fid, how in (("hash departs from SHA256SUMS", "departs"), ("hash has no line in SHA256SUMS", "no line"),
                     ("hash departs from the lead's record", "lead"), ("hash is one of the format sample's", "sample")):
        def mutate(p: Planted, how: str = how) -> None:
            if how == "departs":
                p.sums_edit["table_W5-exact.json"] = "0" * 64
            elif how == "no line":
                p.sums_edit["table_W5-exact.json"] = ""
            elif how == "lead":
                p.lead_record_edit = {"table_W5-exact.json": "1" * 64}
            else:
                p.sample_table = "table_W5-exact.json"
        add(fid, "A table's hash departs", "181", f"table_W5-exact.json: {how}", mutate,
            {"issues": [_issue(some_x, "hash", "nothing")], "families": {x_r: "not pass", x_p: "not pass"},
             "entries": [{"run": some_x, "entry": "R t_events", "outcome": "unformed"}]})
    add("SHA256SUMS absent", "An absent SHA256SUMS is recorded and flagged", "181", "SHA256SUMS not written",
        lambda p: setattr(p, "drop_sums", True),
        {"table_issues": [["table_W5.json", "hash", "flag"]], "families": {f: "unchanged" for f in (f5r, x_r, f6g)}})

    # --- the top level of a table (CRITERIA.md:182) ---
    some5, some6 = names.judged(f5p, 0, 0), names.judged(f6g, 0, 0)
    add("top-level units missing", "A top-level key of a table is missing", "182", "table_W5.json: units removed",
        lambda p: p.tables["table_W5.json"].pop("units"),
        {"issues": [_issue(some5, "top-level key", "refused")], "families": {f5r: "not pass", f5p: "not pass"}})
    add("top-level kind of another value", "A top-level key of another value", "182",
        "table_W6.json: kind 'another table'",
        lambda p: p.tables["table_W6.json"].__setitem__("kind", "another table"),
        {"issues": [_issue(some6, "top-level key", "refused")], "families": {f6g: "not pass", f6p: "not pass"}})
    add("top-level arm of another value", "A top-level key of another value", "182", "table_W5-exact.json: arm 3",
        lambda p: p.tables["table_W5-exact.json"].__setitem__("arm", 3),
        {"issues": [_issue(some_x, "top-level key", "refused")], "families": {x_r: "not pass", x_p: "not pass"}})

    # --- a key of an entry (CRITERIA.md:183; the lead's rulings 2b, 15) ---
    r = names.judged(f6g, 2, 2)
    add("entry key missing", "A key of an entry is missing", "183", f"{r}: trace_capacity removed",
        edit(r, lambda e: e.pop("trace_capacity")),
        {"issues": [_issue(r, "entry key", "refused")], "families": {f6g: "not pass"}})
    add("entry key of another type", "A key of an entry of another type", "183", f"{r}: trace_capacity 'many'",
        edit(r, lambda e: e.__setitem__("trace_capacity", "many")),
        {"issues": [_issue(r, "entry key", "refused")], "families": {f6g: "not pass"}})
    add("recorded-only key missing", "A key of an entry is missing (ruling 2b)", "183", f"{r}: checks removed",
        edit(r, lambda e: e.pop("checks")),
        {"issues": [_issue(r, "entry key", "refused")], "families": {f6g: "not pass"}})

    # --- status against refusal; a truncated trace (CRITERIA.md:184-185) ---
    r = names.judged(f6p, 1, 1)
    add("completed with a refusal", "A completed run with a non-null refusal", "184",
        f"{r}: refusal domain on a completed run",
        edit(r, lambda e: e.__setitem__("refusal", {"kind": "domain", "message": "planted", "time_s": 1.0})),
        {"issues": [_issue(r, "status", "not_complete")], "families": {f6p: "not pass"}})
    r2 = names.judged(f5r, 1, 1)
    add("refused without a refusal", "A refused run without a refusal", "184", f"{r2}: status refused",
        edit(r2, lambda e: e.__setitem__("status", "refused")),
        {"issues": [_issue(r2, "status", "not_complete")], "families": {f5r: "not pass"}})
    r3 = names.judged(f5p, 5, 0)
    add("truncated trace", "events_total above trace_capacity", "185", f"{r3}: trace_capacity 1",
        edit(r3, lambda e: e.__setitem__("trace_capacity", 1)),
        {"issues": [_issue(r3, "truncated", "not_complete")], "families": {f5p: "not pass"}})

    # --- the sample times; host_patch and restart (CRITERIA.md:186-187) ---
    r = names.judged(x_p, 1, 3)
    add("t departs", "A completed run whose t is not the registered samples_s", "186", f"{r}: t[4] x (1 + 1e-9)",
        edit(r, lambda e: e["t"].__setitem__(4, e["t"][4] * (1 + 1e-9))),
        {"issues": [_issue(r, "samples", "refused")], "families": {x_p: "not pass"}})
    r = names.judged(f5p, 2, 1)
    add("host_patch on another run", "A host_patch on a run that is not the Lie plant's", "187",
        f"{r}: a host_patch", edit(r, lambda e: e.__setitem__("host_patch", {"id": LIE_PATCH_ID, "change": "x"})),
        {"issues": [_issue(r, "host_patch/restart", "refused")], "families": {f5p: "not pass"}})
    lie0 = names.lie(0)
    add("Lie run with another patch id", "Another id on the Lie plant's run", "187", f"{lie0}: host_patch.id 'x'",
        edit(lie0, lambda e: e["host_patch"].__setitem__("id", "x")),
        {"issues": [_issue(lie0, "host_patch/restart", "refused")], "plants": {"P3": "unscorable"}})
    r = names.judged(f6p, 3, 0)
    add("restart on another run", "A restart on a run that is not a resumed one", "187", f"{r}: a restart",
        edit(r, lambda e: e.__setitem__("restart", {"time_s": 1.0, "step_index": 1, "through": "planted"})),
        {"issues": [_issue(r, "host_patch/restart", "refused")], "families": {f6p: "not pass"}})
    resumed6, unint6 = names.restart("W6")
    add("resumed run with a null restart", "A null restart on a resumed run", "187", f"{resumed6}: restart null",
        edit(resumed6, lambda e: e.__setitem__("restart", None)),
        {"issues": [_issue(resumed6, "host_patch/restart", "refused")], "families": {f6g: "not pass"},
         "entries": [{"run": unint6, "entry": "E restart", "outcome": "unformed"}]})

    # --- the missing leaf (CRITERIA.md:188) ---
    r = names.judged(f5r, 4, 2)
    leaf_expect = {"issues": [_issue(r, "missing leaf", "leaf")], "families": {f5r: "not pass"},
                   "entries": [{"family": f5r, "entry": "S xi_2", "outcome": "unformed"},
                               {"run": r, "entry": "R identity X", "outcome": "pass"}]}
    add("missing leaf: a series name", "A judged leaf is missing", "188", f"{r}: series.xi_2 removed",
        edit(r, lambda e: e["series"].pop("xi_2")), leaf_expect)

    def nan_leaf(p: Planted) -> None:
        _entry(p.tables, r)["series"]["xi_2"][3] = float("nan")
        p.raw_text["table_W5.json"] = json.dumps(p.tables["table_W5.json"])
    add("missing leaf: a NaN", "A judged leaf non-finite", "188", f"{r}: series.xi_2[3] NaN", nan_leaf, leaf_expect)
    add("missing leaf: short", "A judged leaf not as long as t", "188", f"{r}: series.xi_2 one short",
        edit(r, lambda e: e["series"].__setitem__("xi_2", e["series"]["xi_2"][:-1])), leaf_expect)
    add("missing leaf: an events list", "A list missing from events", "183, 188", f"{r}: events.channel removed",
        edit(r, lambda e: e["events"].pop("channel")),
        {"issues": [_issue(r, "missing leaf", "leaf")], "families": {f5r: "not pass"},
         "entries": [{"run": r, "entry": "E trace", "outcome": "unformed"},
                     {"family": f5r, "entry": "S t_events", "outcome": "unformed"}]})

    # --- a record that contradicts itself, or too few events (CRITERIA.md:189) ---
    r = names.judged(f6p, 0, 3)
    trace_expect = {"families": {f6p: "fail"}, "entries": [{"run": r, "entry": "E trace", "outcome": "fail"},
                                                           {"family": f6p, "entry": "S t_events",
                                                            "outcome": "unformed"}]}
    add("counts against the channel", "A record that contradicts itself", "189", f"{r}: counts_after[2] = [1]",
        edit(r, lambda e: e["events"]["counts_after"].__setitem__(2, list(e["events"]["counts_after"][1]))),
        trace_expect)
    add("events_total against its list", "A record that contradicts itself", "189", f"{r}: events_total + 1",
        edit(r, lambda e: e.__setitem__("events_total", e["events_total"] + 1)), trace_expect)

    def swap(e: dict) -> None:
        t = e["events"]["time_s"]
        t[4], t[5] = t[5], t[4]
    add("an event out of order", "A record that contradicts itself", "189", f"{r}: events 4 and 5 swapped",
        edit(r, swap), trace_expect)
    keep = 3 if k_c is None else max(0, k_c("W6", 3) - 1)

    def cut(e: dict) -> None:
        for key in ("time_s", "channel", "counts_after"):
            e["events"][key] = e["events"][key][:keep]
        e["events_total"] = e["events"]["first_index"] + keep
    add("fewer than K_c events", "A record with fewer than K_c events", "189", f"{r}: cut to {keep} events",
        edit(r, cut), trace_expect)

    # --- the resumed run (CRITERIA.md:190) ---
    resumed5, unint5 = names.restart("W5")
    restart_expect = {"issues": [_issue(resumed5, "resumed run", "refused")], "families": {f5r: "not pass"},
                      "entries": [{"run": unint5, "entry": "E restart", "outcome": ("unformed", "fail")}]}
    add("resumed run at another time", "A resumed run whose restart.time_s departs", "190",
        f"{resumed5}: restart.time_s x (1 + 1e-9)",
        edit(resumed5, lambda e: e["restart"].__setitem__("time_s", e["restart"]["time_s"] * (1 + 1e-9))),
        {**restart_expect, "entries": [{"run": unint5, "entry": "E restart", "outcome": "unformed"}]})
    add("resumed run with another first_index", "A resumed run whose first_index departs", "190",
        f"{resumed5}: first_index + 1", edit(resumed5, lambda e: e["events"].__setitem__(
            "first_index", e["events"]["first_index"] + 1)), restart_expect)

    def drop_first_sample(e: dict) -> None:
        e["t"] = e["t"][1:]
        e["series"] = {k: v[1:] for k, v in e["series"].items()}
        e["integer_ledger"] = e["integer_ledger"][1:]
    add("resumed run without a later sample", "A resumed run that does not list each later sample", "190",
        f"{resumed5}: its first sample removed", edit(resumed5, drop_first_sample), restart_expect)

    # --- a shared record hash; provenance (CRITERIA.md:191-192; ruling 15) ---
    a, b = names.judged(f6g, 1, 0), names.judged(f6p, 4, 3)

    def share(p: Planted) -> None:
        _entry(p.tables, b)["record_sha256"] = _entry(p.tables, a)["record_sha256"]
    add("a shared record hash", "Two runs with the same record_sha256", "191", f"{b}: {a}'s record_sha256", share,
        {"issues": [_issue(a, "shared record hash", "shared"), _issue(b, "shared record hash", "shared")],
         "families": {f6g: "not pass", f6p: "not pass"}})
    r = names.judged(x_r, 0, 2)
    for fid, fn in (("provenance: a dirty checkout", lambda e: e["source"].__setitem__("checkout_dirty", True)),
                    ("provenance: an empty source key", lambda e: e["source"].__setitem__("snapshot_patch_sha256",
                                                                                         "")),
                    ("provenance: record_sha256 missing", lambda e: e.pop("record_sha256"))):
        add(fid, "Provenance missing or incomplete, or a dirty checkout", "192", f"{r}: {fid[len('provenance: '):]}",
            edit(r, fn), {"issues": [_issue(r, "provenance", "provenance")], "families": {x_r: "not pass"}})

    # --- refusals by kind (CRITERIA.md:193-194) ---
    r = names.judged(f5p, 3, 1)
    add("a judged run refused with kind check", "A judged run refused with kind check", "193",
        f"{r}: refused, kind check",
        edit(r, lambda e: (e.__setitem__("status", "refused"),
                           e.__setitem__("refusal", {"kind": "check", "message": "planted", "time_s": 1.0}))),
        {"issues": [_issue(r, "refused run", "not_complete")], "families": {f5p: "fail"},
         "entries": [{"run": r, "entry": "D", "outcome": "fail"}]})
    add("a judged run refused with kind domain", "A run refused with kind domain, definition or harness", "194",
        f"{r}: refused, kind domain",
        edit(r, lambda e: (e.__setitem__("status", "refused"),
                           e.__setitem__("refusal", {"kind": "domain", "message": "planted", "time_s": 1.0}))),
        {"issues": [_issue(r, "refused run", "not_complete")], "families": {f5p: "not pass"}})
    lie1 = names.lie(1)
    add("a plant run refused", "A plant run whose status is refused", "194", f"{lie1}: refused, kind harness",
        edit(lie1, lambda e: (e.__setitem__("status", "refused"),
                              e.__setitem__("refusal", {"kind": "harness", "message": "planted", "time_s": 1.0}))),
        {"issues": [_issue(lie1, "refused run", "not_complete")], "plants": {"P3": "unscorable"}})

    # --- missing and doubled names (CRITERIA.md:195-197; the lead's ruling 19) ---
    r = names.judged(x_r, 0, 1)

    def in_missing(p: Planted) -> None:
        table = p.tables[_Names.table_of(p.tables, r)]
        table["runs"].pop(r)
        table["missing"].append(r)
    add("a run in missing", "A run in missing", "195", f"{r}: moved to missing", in_missing,
        {"issues": [_issue(r, "missing", "missing")], "families": {x_r: "not pass"}})
    add("a run in neither", "A run in neither list", "195", f"{r}: removed",
        lambda p: p.tables[_Names.table_of(p.tables, r)]["runs"].pop(r),
        {"issues": [_issue(r, "missing", "missing")], "families": {x_r: "not pass"}})
    add("a run in missing and in runs", "A run in missing and in runs", "196", f"{r}: also in missing",
        lambda p: p.tables[_Names.table_of(p.tables, r)]["missing"].append(r),
        {"issues": [_issue(r, "listed twice", "refused")], "families": {x_r: "not pass"}})
    add("a name in two tables", "A run name listed twice (in two tables)", "196", f"{r}: also in table_W6.json",
        lambda p: p.tables["table_W6.json"]["runs"].__setitem__(r, copy.deepcopy(_entry(p.tables, r))),
        {"issues": [_issue(r, "listed twice", "refused")], "families": {x_r: "not pass"}})

    def twice_in_runs(p: Planted) -> None:
        table = p.tables["table_W5-exact.json"]
        key = json.dumps(r)
        p.raw_text["table_W5-exact.json"] = _text(table).replace(f"{key}: ", f"{key}: {json.dumps(table['runs'][r])}, "
                                                                            f"{key}: ", 1)
    add("a name twice in one runs", "A run name listed twice in one runs", "196", f"{r}: twice in runs",
        twice_in_runs, {"issues": [_issue(r, "listed twice", "refused")], "families": {x_r: "not pass"}})

    def elsewhere(p: Planted) -> None:
        p.tables["table_W6.json"]["runs"][r] = p.tables[_Names.table_of(p.tables, r)]["runs"].pop(r)
    add("a run only in another world's table", "A run found only in another world's table (ruling 19)",
        "195; ruling 19", f"{r}: moved to table_W6.json", elsewhere,
        {"issues": [_issue(r, "missing", "missing"), _issue(r, "another world's table", "flag")],
         "families": {x_r: "not pass"}})
    add("an unregistered name", "A run name that no inputs list", "197", "W5 sideways-first h=1 c0 added",
        lambda p: p.tables["table_W5.json"]["runs"].__setitem__("W5 sideways-first h=1 c0", {}),
        {"issues": [_issue("W5 sideways-first h=1 c0", "unregistered", "ignored")],
         "families": {f5r: "unchanged", f5p: "unchanged"}})
    if honest_retry:
        retry_name = next(iter(next(iter(honest_retry.values()))["runs"]))
        add("an unowed retry run", "An unowed retry run", "198", f"{retry_name}: present, not owed",
            lambda p: None, {"issues": [_issue(retry_name, "unowed retry", "flag")],
                             "families": {f5r: "unchanged"}}, with_retry=True)

    # --- support runs, recorded-only leaves (CRITERIA.md:199-200) ---
    add("a support run missing", "A support run missing", "199", f"{resumed6}: removed",
        lambda p: p.tables[_Names.table_of(p.tables, resumed6)]["runs"].pop(resumed6),
        {"families": {f6g: "not pass", f6p: "unchanged"},
         "entries": [{"run": unint6, "entry": "E restart", "outcome": "unformed"}]})
    add("a support run refused", "A support run refused", "199", f"{resumed5}: refused, kind harness",
        edit(resumed5, lambda e: (e.__setitem__("status", "refused"),
                                  e.__setitem__("refusal", {"kind": "harness", "message": "planted", "time_s": 1.0}))),
        {"issues": [_issue(resumed5, "refused run", "not_complete")], "families": {f5r: "not pass"},
         "entries": [{"run": unint5, "entry": "E restart", "outcome": "unformed"}]})
    r = names.judged(f6g, 0, 0)
    add("a recorded-only leaf", "A leaf inside a recorded-only key", "200", f"{r}: steps 7",
        edit(r, lambda e: e.__setitem__("steps", 7)),
        {"issues": [_issue(r, "recorded-only leaf", "flag")], "families": {f6g: "unchanged"}})

    def nan_recorded(p: Planted) -> None:
        _entry(p.tables, r)["definition"] = {"planted": float("nan")}
        p.raw_text["table_W6.json"] = json.dumps(p.tables["table_W6.json"])
    add("a NaN in a recorded-only key", "A non-finite value inside a recorded-only key", "200, 202",
        f"{r}: definition.planted NaN", nan_recorded,
        {"issues": [_issue(r, "recorded-only leaf", "flag")], "families": {f6g: "unchanged"}})

    # --- duplicate keys and non-finite values (CRITERIA.md:201-202) ---
    r = names.judged(f5r, 2, 3)

    def dup_in_entry(p: Planted) -> None:
        key = json.dumps(r) + ": {"
        text = _text(p.tables["table_W5.json"])
        p.raw_text["table_W5.json"] = text.replace(key, key + '"status": "completed", ', 1)
    add("a duplicate key in an entry", "A JSON object with a duplicate key (in an entry)", "201",
        f"{r}: status given twice", dup_in_entry,
        {"issues": [_issue(r, "duplicate key", "refused")], "families": {f5r: "not pass"}})

    def dup_elsewhere(p: Planted) -> None:
        text = _text(p.tables["table_W5-exact.json"])
        p.raw_text["table_W5-exact.json"] = "{" + '"kind": "x", ' + text[1:]
    add("a duplicate key elsewhere in a table", "A duplicate key elsewhere in a table", "201",
        "table_W5-exact.json: kind given twice", dup_elsewhere,
        {"issues": [_issue(some_x, "top-level key", "refused")], "families": {x_r: "not pass", x_p: "not pass"}})

    def nan_elsewhere(p: Planted) -> None:
        p.tables["table_W6.json"]["planted"] = float("nan")
        p.raw_text["table_W6.json"] = json.dumps(p.tables["table_W6.json"])
    add("a NaN elsewhere in a table", "A NaN elsewhere in a table", "202", "table_W6.json: a NaN beside the runs",
        nan_elsewhere,
        {"issues": [_issue(some6, "top-level key", "refused")], "families": {f6g: "not pass", f6p: "not pass"}})
    return out


# ---- checking a record against what §4 says ----


def check(record: dict, honest: dict, expect: dict) -> list[str]:
    """Every way the record departs from `expect` (empty where the fault was flagged as CRITERIA.md §4 says)."""
    misses = []
    rows = record.get("refusals_and_flags", [])
    for run, row, effect in expect.get("issues", []):
        if not any(r.get("run") == run and r.get("row") == row and r.get("effect") == effect for r in rows):
            misses.append(f"no issue ({run!r}, {row!r}, {effect!r})")
    for table, row, effect in expect.get("table_issues", []):
        if not any(r.get("table") == table and r.get("row") == row and r.get("effect") == effect and "run" not in r
                   for r in rows):
            misses.append(f"no table issue ({table!r}, {row!r}, {effect!r})")
    for family, want in expect.get("families", {}).items():
        got = record["families"][family]["verdict"]
        base = honest["families"][family]["verdict"]
        if want == "not pass" and (got == "pass" or (base == "pass" and got not in ("inconclusive", "fail"))):
            misses.append(f"{family}: {got} (want not pass)")
        elif want == "fail" and got != "fail":
            misses.append(f"{family}: {got} (want fail)")
        elif want == "unchanged" and got != base:
            misses.append(f"{family}: {got} (honest {base})")
    for want in expect.get("entries", []):
        found = [e["outcome"] for e in record["entries"] if e["entry"] == want["entry"]
                 and (e["run"] == want["run"] if "run" in want else (e["family"] == want["family"] and e["run"] is None))]
        allowed = want["outcome"] if isinstance(want["outcome"], (list, tuple)) else (want["outcome"],)
        if not found or any(o not in allowed for o in found):
            misses.append(f"{want}: found {found}")
    for plant, score in expect.get("plants", {}).items():
        if record["plants"][plant]["score"] != score:
            misses.append(f"{plant}: {record['plants'][plant]['score']} (want {score})")
    return misses


# ---- the copy with the coarsest rung perturbed (SPEC.md §8; CRITERIA.md §10) ----


def _ref_times(refs: dict, world: str, copy_: int) -> tuple[int, list[float]]:
    ref = refs[world]
    c = ref.copies[copy_]
    return c.K, c.times


def perturb_coarsest_rung(inputs: Inputs, refs: dict, tables: dict, family: str | None = None,
                          factor: float = 16.0) -> tuple[dict, dict]:
    """Move every event time of `family`'s runs at h_1 by one constant A = factor x d_1 (d_1: the honest pooled step
    difference between h_1 and h_2 over the judged events), so that the order of its t_events leaves the window.
    The factor doubles until the order fitted over the family's rungs leaves the window (at most 6 times).
    `family` defaults to the family whose retry runs the inputs list. Returns (tables, info)."""
    if family is None:
        listed = inputs.listed_retry_runs
        if not listed:
            raise ValueError("no family given and the inputs list no retry run")
        family = f"{listed[0]['world']} {listed[0]['first']}-first"
    fam = inputs.families[family]
    world = inputs.worlds[fam.world]
    names = _Names(inputs, tables)

    def times(tabs: dict, rung: int, c: int) -> list[float]:
        return _entry(tabs, names.judged(family, rung, c))["events"]["time_s"]

    def d_between(tabs: dict, j: int) -> float:
        diffs = []
        for c in range(world.copies):
            k_c, _ = _ref_times(refs, world.name, c)
            a, b = times(tabs, j, c), times(tabs, j + 1, c)
            diffs += [b[k] - a[k] for k in range(min(k_c, len(a), len(b)))]
        return math.sqrt(math.fsum(x * x for x in diffs) / len(diffs))

    honest_d = [d_between(tables, j) for j in range(len(fam.rungs) - 1)]
    ref = refs[world.name]
    p = world.order_of("t_events")
    honest_lad = ladder(p, fam.rungs, honest_d, 4, world.end_s, ref.scales["t_events"])
    used_factor = factor
    for _ in range(7):
        shift = used_factor * honest_d[0]
        out = copy.deepcopy(tables)
        for c in range(world.copies):
            e = _entry(out, names.judged(family, 0, c))
            e["events"]["time_s"] = [t + shift for t in e["events"]["time_s"]]
        d = [d_between(out, j) for j in range(len(fam.rungs) - 1)]
        lad = ladder(p, fam.rungs, d, 4, world.end_s, ref.scales["t_events"])
        if lad.q is not None and not (p - 0.5 <= lad.q <= p + 0.5):
            break
        used_factor *= 2.0
    else:
        raise ValueError("the perturbation did not move the order out of its window")
    retry_runs = [Inputs.retry_name(fam, c) for c in range(world.copies)]
    info = {"family": family, "readout": "t_events", "rung_s": fam.rungs[0], "factor": used_factor,
            "shift_s": shift, "honest_d": honest_d, "honest_q": honest_lad.q, "honest_used": honest_lad.used,
            "perturbed_d": d, "perturbed_q": lad.q, "perturbed_used": lad.used, "window": [p - 0.5, p + 0.5],
            "retry_runs": retry_runs}
    return out, info
