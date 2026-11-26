"""The engine tables (TABLE.md), read by the judge.

One code path reads the format sample and the registered tables: `read_folder(..., structure_only=True)` stops at
the hashes, the strict parse, the keys and the types (no number is compared, and no grid, echo or reference is
read), and lists the entry kinds found; the judged mode adds the faults of CRITERIA.md §4 that need numbers.

Every fault found is an `Issue` naming its row of CRITERIA.md §4 and its effect:
- `nothing`: nothing of the run is judged (the echo departs; the table's hash departs);
- `refused`: refused by another row (E and R compared on what it holds; S and the pair not compared);
- `provenance`, `shared`: refused, and all its entries compared all the same (a miss fails);
- `not_complete`: the run did not complete (a refusal with its kind);
- `leaf`: the entries that read the leaf unform, the rest of the run is judged;
- `flag`: recorded for the checker, refuses nothing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from . import strictjson as sj
from .registry import SERIES

TABLE_KIND = "fr43 part 3 co-writers engine table, version 2"
UNITS = {"amount": "fmol", "volume": "pL", "time": "s"}
REFUSAL_KINDS = ("domain", "definition", "check", "harness")
LIE_PATCH_ID = "second_halves_declared_order"
RECORDED_ONLY = ("definition", "checks", "pools_at_event", "samples_echo", "steps")
SOURCE_STRINGS = ("engine_revision", "snapshot", "snapshot_patch_sha256", "python", "numpy", "scipy", "jax", "machine")
ENTRY_KEYS = ("status", "world", "first", "copy", "step_s", "steps", "variant", "seed", "t", "series", "events",
              "events_total", "trace_capacity", "integer_ledger", "samples_echo", "operators", "inputs", "definition",
              "checks", "pools_at_event", "restart", "host_patch", "refusal", "source", "record", "record_sha256")
EVENT_LISTS = ("time_s", "channel", "counts_after")


@dataclass
class Issue:
    row: str
    effect: str
    where: str
    message: str
    kind: str | None = None

    def as_dict(self) -> dict:
        out = {"row": self.row, "effect": self.effect, "where": self.where, "message": self.message}
        if self.kind:
            out["kind"] = self.kind
        return out


@dataclass
class Entry:
    """One run entry of one table, as read: the raw object, its issues and the leaves the judge can use."""

    name: str
    table: str
    raw: Any
    issues: list[Issue] = field(default_factory=list)
    bad_leaves: set[str] = field(default_factory=set)
    status: str | None = None
    t: list[float] | None = None
    series: dict[str, list[float]] = field(default_factory=dict)
    times: list[float] | None = None
    channels: list[str] | None = None
    counts: list[tuple[int, ...]] | None = None
    first_index: int | None = None
    events_total: int | None = None
    trace_capacity: int | None = None
    ledger: list[int] | None = None
    restart: dict | None = None
    host_patch: dict | None = None
    refusal: dict | None = None
    record_sha256: str | None = None

    def add(self, row: str, effect: str, where: str, message: str, kind: str | None = None) -> None:
        self.issues.append(Issue(row, effect, where, message, kind))

    def effects(self) -> set[str]:
        return {i.effect for i in self.issues}


@dataclass
class TableFile:
    path: str
    name: str
    world: str | None
    sha256: str | None
    data: Any = None
    issues: list[Issue] = field(default_factory=list)  # table-level: effect 'nothing', 'refused' or 'flag'
    entries: list[Entry] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def effect(self) -> str | None:
        effects = {i.effect for i in self.issues}
        if "nothing" in effects:
            return "nothing"
        if "refused" in effects:
            return "refused"
        return None


def world_of_file(file_name: str, worlds: list[str]) -> str | None:
    """`table_W5.json` and `table_W5-retry.json` are W5's."""
    stem = file_name[len("table_"):-len(".json")] if file_name.startswith("table_") and file_name.endswith(
        ".json") else None
    if stem is None:
        return None
    if stem.endswith("-retry"):
        stem = stem[:-len("-retry")]
    return stem if stem in worlds else None


def read_sums(folder: str) -> tuple[dict[str, str] | None, list[str]]:
    """SHA256SUMS: one line per file, the sha256, two spaces, the name. None where the file is absent."""
    path = os.path.join(folder, "SHA256SUMS")
    if not os.path.exists(path):
        return None, []
    sums: dict[str, str] = {}
    problems = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle.read().splitlines(), 1):
            if not line.strip():
                continue
            digest, sep, name = line.partition("  ")
            if not sep or not sj.is_hex64(digest) or not name:
                problems.append(f"line {number} is not 'sha256  name'")
                continue
            if name in sums:
                problems.append(f"{name} has two lines")
            sums[name] = digest.lower()
    return sums, problems


def read_folder(folder: str, worlds: list[str], lead_record: dict[str, str] | None,
                sample_hashes: set[str], structure_only: bool, arms: dict[int, str]) -> list[TableFile]:
    """Every `table_*.json` of a folder, with its hash checked (TABLE.md §1) and its top level and entries read."""
    sums, sum_problems = read_sums(folder)
    tables = []
    for file_name in sorted(os.listdir(folder)):
        if not (file_name.startswith("table_") and file_name.endswith(".json")):
            continue
        path = os.path.join(folder, file_name)
        table = TableFile(path=path, name=file_name, world=world_of_file(file_name, worlds), sha256=None)
        tables.append(table)
        digest = sj.sha256_file(path)
        table.sha256 = digest
        if sums is None:
            table.issues.append(Issue("hash", "flag", file_name, "SHA256SUMS is absent: recorded and flagged"))
        elif file_name not in sums:
            table.issues.append(Issue("hash", "nothing", file_name, "no line in SHA256SUMS"))
        elif sums[file_name] != digest:
            table.issues.append(Issue("hash", "nothing", file_name, f"{digest} departs from SHA256SUMS"))
        for problem in sum_problems:
            table.issues.append(Issue("hash", "flag", "SHA256SUMS", problem))
        if lead_record is not None:
            recorded = lead_record.get(file_name)
            if recorded is None or recorded.lower() != digest:
                table.issues.append(Issue("hash", "nothing", file_name, "departs from the lead's record"))
        if digest in sample_hashes:
            table.issues.append(Issue("hash", "nothing", file_name, "one of the format sample's tables"))
        if table.world is None:
            table.issues.append(Issue("top-level key", "refused", file_name, "not a table of a registered world"))
        try:
            loaded = sj.load_file(path)
        except (OSError, sj.StrictJSONError) as exc:
            table.issues.append(Issue("top-level key", "refused", file_name, f"unreadable: {exc}"))
            continue
        table.data = loaded.data
        _read_top(table, arms)
    return tables


def _read_top(table: TableFile, arms: dict[int, str]) -> None:
    data = table.data
    if not isinstance(data, dict):
        table.issues.append(Issue("top-level key", "refused", "<top>", "the table is not an object"))
        return
    for path, kind in sj.problems(data):
        if len(path) >= 2 and path[0] == "runs" and not str(path[1]).startswith("<duplicate"):
            if len(path) == 2 and kind == "duplicate key":
                continue  # a run name twice in one runs: the name's own row (CRITERIA.md §4)
            if len(path) >= 3:
                continue  # inside an entry: that entry's
        row = "duplicate key" if kind == "duplicate key" else "non-finite"
        table.issues.append(Issue(row, "refused", sj.path_text(path), f"a {kind} outside a run's entry"))
    kind = data.get("kind")
    if "kind" not in data or not isinstance(kind, str) or kind != TABLE_KIND:
        table.issues.append(Issue("top-level key", "refused", "kind", f"{kind!r} is not {TABLE_KIND!r}"))
    arm = data.get("arm")
    expected_arm = [a for a, w in arms.items() if w == table.world]
    if "arm" not in data or not sj.is_integer(arm) or int(arm) not in arms or (
            expected_arm and int(arm) != expected_arm[0]):
        table.issues.append(Issue("top-level key", "refused", "arm", f"{arm!r} is not this table's arm"))
    units = data.get("units")
    if not isinstance(units, dict) or any(units.get(k) != v for k, v in UNITS.items()):
        table.issues.append(Issue("top-level key", "refused", "units", f"{units!r} is not {UNITS!r}"))
    missing = data.get("missing")
    if not isinstance(missing, list) or not all(isinstance(x, str) for x in missing):
        table.issues.append(Issue("top-level key", "refused", "missing", "not a list of run names"))
    else:
        table.missing = list(missing)
    runs = data.get("runs")
    if not isinstance(runs, dict):
        table.issues.append(Issue("top-level key", "refused", "runs", "not an object"))
        return
    for name, value in runs.items():
        values = runs.duplicates.get(name, [value]) if isinstance(runs, sj.JObject) else [value]
        for raw in values:
            table.entries.append(Entry(name=name, table=table.name, raw=raw))


# ---- one entry: keys, types and leaves (TABLE.md §3), the same in both modes ----


def _type_ok(value: Any, kind: str) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return sj.is_integer(value)
    if kind == "number":
        return sj.is_number(value)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "list":
        return isinstance(value, list)
    raise ValueError(kind)


ENTRY_TYPES = {
    "status": ("string", False), "world": ("string", False), "first": ("string", False), "copy": ("integer", False),
    "step_s": ("number", False), "variant": ("string", True), "seed": ("integer", False), "t": ("list", False),
    "series": ("object", False), "events": ("object", False), "events_total": ("integer", False),
    "trace_capacity": ("integer", False), "integer_ledger": ("list", False), "operators": ("list", False),
    "inputs": ("object", True), "restart": ("object", True), "host_patch": ("object", True),
    "refusal": ("object", True), "source": ("object", False), "record": ("string", False),
    "record_sha256": ("string", False),
}
PROVENANCE_KEYS = ("source", "record", "record_sha256")


def read_entry(entry: Entry, world_kind: str | None) -> None:
    """Keys, types and leaves; fills the parsed fields. `world_kind` names the series the world asks for."""
    raw = entry.raw
    if not isinstance(raw, dict):
        entry.add("entry key", "refused", entry.name, "the entry is not an object")
        return
    for path, kind in sj.problems(raw):
        top = str(path[0]) if path else ""
        if kind == "duplicate key":
            entry.add("duplicate key", "refused", sj.path_text(path), "a duplicate key in the entry")
        elif top in RECORDED_ONLY:
            entry.add("recorded-only leaf", "flag", sj.path_text(path), "a non-finite number in a recorded-only key")
        elif top in ("series", "events", "integer_ledger", "events_total"):
            pass  # the missing leaf's case, found with the leaf below
        elif top in PROVENANCE_KEYS:
            entry.add("provenance", "provenance", sj.path_text(path), "a non-finite number in the provenance")
        elif top in ("t",):
            pass  # the sample times' row, judged below (a departing t refuses the run)
        else:
            entry.add("entry key", "refused", sj.path_text(path), "a non-finite number in the entry")
    for key in ENTRY_KEYS:
        if key in RECORDED_ONLY:
            continue
        kind, nullable = ENTRY_TYPES[key]
        row, effect = ("provenance", "provenance") if key in PROVENANCE_KEYS else ("entry key", "refused")
        if key not in raw:
            entry.add(row, effect, key, "missing")
            continue
        value = raw[key]
        if value is None:
            if not nullable:
                entry.add(row, effect, key, "null where the table does not allow it")
            continue
        if not _type_ok(value, kind):
            entry.add(row, effect, key, f"not a {kind}")
    for key in RECORDED_ONLY:
        if key not in raw:
            entry.add("recorded-only leaf", "flag", key, "missing")
    if "steps" in raw and not sj.is_integer(raw["steps"]):
        entry.add("recorded-only leaf", "flag", "steps", "not an integer")
    if "samples_echo" in raw and not (isinstance(raw["samples_echo"], list) and all(
            sj.is_number(x) for x in raw["samples_echo"])):
        entry.add("recorded-only leaf", "flag", "samples_echo", "not a list of numbers")
    if "pools_at_event" in raw and raw["pools_at_event"] is not None and not isinstance(raw["pools_at_event"],
                                                                                          (dict, list)):
        entry.add("recorded-only leaf", "flag", "pools_at_event", "neither an object, a list nor null")
    status = raw.get("status")
    if isinstance(status, str):
        if status not in ("completed", "refused"):
            entry.add("entry key", "refused", "status", f"{status!r} is neither completed nor refused")
        else:
            entry.status = status
    _read_sub_objects(entry, raw)
    _read_source(entry, raw)
    _read_t(entry, raw)
    _read_series(entry, raw, world_kind)
    _read_events(entry, raw)
    _read_ledger(entry, raw)
    if isinstance(raw.get("operators"), list) and not all(isinstance(x, str) for x in raw["operators"]):
        entry.add("entry key", "refused", "operators", "a member that is not a string")
    if sj.is_integer(raw.get("events_total")):
        entry.events_total = int(raw["events_total"])
    else:
        entry.bad_leaves.add("events_total")
    if sj.is_integer(raw.get("trace_capacity")):
        entry.trace_capacity = int(raw["trace_capacity"])


def _read_sub_objects(entry: Entry, raw: dict) -> None:
    restart = raw.get("restart")
    if isinstance(restart, dict):
        ok = (sj.is_number(restart.get("time_s")) and sj.is_integer(restart.get("step_index"))
              and isinstance(restart.get("through"), str))
        if not ok:
            entry.add("entry key", "refused", "restart", "not {time_s: number, step_index: integer, through: string}")
        else:
            entry.restart = restart
    patch = raw.get("host_patch")
    if isinstance(patch, dict):
        if not (isinstance(patch.get("id"), str) and "change" in patch):
            entry.add("entry key", "refused", "host_patch", "not {id: string, change}")
        else:
            entry.host_patch = patch
    refusal = raw.get("refusal")
    if isinstance(refusal, dict):
        ok = (isinstance(refusal.get("kind"), str) and isinstance(refusal.get("message"), str)
              and "time_s" in refusal and (refusal["time_s"] is None or sj.is_number(refusal["time_s"])))
        if not ok:
            entry.add("entry key", "refused", "refusal", "not {kind: string, message: string, time_s: number|null}")
        else:
            entry.refusal = refusal


def _read_source(entry: Entry, raw: dict) -> None:
    source = raw.get("source")
    if isinstance(source, dict):
        for key in SOURCE_STRINGS:
            if key not in source or source[key] is None:
                entry.add("provenance", "provenance", f"source/{key}", "missing")
            elif not isinstance(source[key], str):
                entry.add("provenance", "provenance", f"source/{key}", "not a string")
            elif source[key] == "" and key in ("engine_revision", "snapshot"):
                entry.add("provenance", "provenance", f"source/{key}", "empty")
            elif source[key] == "":
                entry.add("provenance", "flag", f"source/{key}", "an empty string (recorded)")
        if "checkout_dirty" not in source or not isinstance(source["checkout_dirty"], bool):
            entry.add("provenance", "provenance", "source/checkout_dirty", "missing or not a boolean")
        if "blas_threads" not in source or not sj.is_integer(source["blas_threads"]):
            entry.add("provenance", "provenance", "source/blas_threads", "missing or not an integer")
    digest = raw.get("record_sha256")
    if isinstance(digest, str):
        if not sj.is_hex64(digest):
            entry.add("provenance", "provenance", "record_sha256", "not 64 hex digits")
        else:
            entry.record_sha256 = digest.lower()
    if isinstance(raw.get("record"), str) and raw["record"] == "":
        entry.add("provenance", "provenance", "record", "empty")


def _read_t(entry: Entry, raw: dict) -> None:
    t = raw.get("t")
    if isinstance(t, list):
        if all(sj.is_number(x) for x in t):
            entry.t = [float(x) for x in t]
        else:
            entry.add("samples", "refused", "t", "a sample time that is not a finite number")


def _read_series(entry: Entry, raw: dict, world_kind: str | None) -> None:
    series = raw.get("series")
    if not isinstance(series, dict) or world_kind is None:
        for name in SERIES.get(world_kind or "", []):
            entry.bad_leaves.add(f"series.{name}")
        return
    length = len(entry.t) if entry.t is not None else None
    for name in SERIES[world_kind]:
        value = series.get(name)
        if name not in series:
            entry.add("missing leaf", "leaf", f"series/{name}", "missing")
        elif not isinstance(value, list) or not all(sj.is_number(x) for x in value):
            entry.add("missing leaf", "leaf", f"series/{name}", "not a list of finite numbers")
        elif length is not None and len(value) != length:
            entry.add("missing leaf", "leaf", f"series/{name}", f"{len(value)} values for {length} sample times")
        else:
            entry.series[name] = [float(x) for x in value]
            continue
        entry.bad_leaves.add(f"series.{name}")


def _read_events(entry: Entry, raw: dict) -> None:
    events = raw.get("events")
    if not isinstance(events, dict):
        entry.bad_leaves |= {"events.time_s", "events.channel", "events.counts_after", "events.first_index"}
        return
    times = events.get("time_s")
    if "time_s" not in events:
        entry.add("missing leaf", "leaf", "events/time_s", "missing")
    elif not isinstance(times, list) or not all(sj.is_number(x) for x in times):
        entry.add("missing leaf", "leaf", "events/time_s", "not a list of finite numbers")
    else:
        entry.times = [float(x) for x in times]
    channels = events.get("channel")
    if "channel" not in events:
        entry.add("missing leaf", "leaf", "events/channel", "missing")
    elif not isinstance(channels, list) or not all(isinstance(x, str) for x in channels):
        entry.add("missing leaf", "leaf", "events/channel", "not a list of strings")
    else:
        entry.channels = list(channels)
    counts = events.get("counts_after")
    if "counts_after" not in events:
        entry.add("missing leaf", "leaf", "events/counts_after", "missing")
    elif not isinstance(counts, list) or not all(
            isinstance(c, list) and c and all(sj.is_integer(x) for x in c) for c in counts):
        entry.add("missing leaf", "leaf", "events/counts_after", "not a list of lists of integers")
    else:
        entry.counts = [tuple(int(x) for x in c) for c in counts]
    first = events.get("first_index")
    if "first_index" not in events:
        entry.add("missing leaf", "leaf", "events/first_index", "missing")
    elif not sj.is_integer(first):
        entry.add("missing leaf", "leaf", "events/first_index", "not an integer")
    else:
        entry.first_index = int(first)
    lengths = {len(x) for x in (entry.times, entry.channels, entry.counts) if x is not None}
    if len(lengths) > 1:
        entry.add("missing leaf", "leaf", "events", "lists of different lengths")
        entry.times = entry.channels = entry.counts = None
    for key, value in (("time_s", entry.times), ("channel", entry.channels), ("counts_after", entry.counts),
                       ("first_index", entry.first_index)):
        if value is None:
            entry.bad_leaves.add(f"events.{key}")


def _read_ledger(entry: Entry, raw: dict) -> None:
    ledger = raw.get("integer_ledger")
    if not isinstance(ledger, list):
        entry.bad_leaves.add("integer_ledger")
        return
    if not all(sj.is_integer(x) for x in ledger):
        entry.add("missing leaf", "leaf", "integer_ledger", "not a list of integers")
    elif entry.t is not None and len(ledger) != len(entry.t):
        entry.add("missing leaf", "leaf", "integer_ledger", f"{len(ledger)} values for {len(entry.t)} sample times")
    else:
        entry.ledger = [int(x) for x in ledger]
        return
    entry.bad_leaves.add("integer_ledger")


def structure_report(tables: list[TableFile], arms: dict[int, str], worlds_kind: dict[str, str]) -> dict:
    """The format sample's read (TABLE.md §5): keys, nesting and types; the entry kinds found; every departure."""
    report: dict[str, Any] = {"tables": {}, "departures": [], "entry_kinds": {}}
    for table in tables:
        kinds: dict[str, int] = {}
        for issue in table.issues:
            if issue.row != "hash" or issue.effect != "flag":
                report["departures"].append({"table": table.name, **issue.as_dict()})
        for entry in table.entries:
            read_entry(entry, worlds_kind.get(table.world or ""))
            for issue in entry.issues:
                if issue.row in ("provenance",) and issue.effect == "flag":
                    continue
                report["departures"].append({"table": table.name, "run": entry.name, **issue.as_dict()})
            raw = entry.raw if isinstance(entry.raw, dict) else {}
            label = [str(raw.get("status"))]
            if isinstance(raw.get("refusal"), dict):
                label.append(f"refusal {raw['refusal'].get('kind')}")
            if raw.get("variant") is not None:
                label.append(f"variant {raw.get('variant')}")
            if raw.get("restart") is not None:
                label.append("restart")
            if raw.get("host_patch") is not None:
                label.append("host_patch")
            key = ", ".join(label)
            kinds[key] = kinds.get(key, 0) + 1
        report["tables"][table.name] = {"sha256": table.sha256, "runs": len(table.entries), "missing": table.missing,
                                        "entry_kinds": kinds}
        for key, count in kinds.items():
            report["entry_kinds"][key] = report["entry_kinds"].get(key, 0) + count
    report["passes"] = not report["departures"]
    return report
