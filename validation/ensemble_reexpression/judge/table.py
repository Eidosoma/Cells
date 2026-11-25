"""The engine tables as the judge reads them (`spec/TABLE.md`, with `AMENDMENT-1-2026-11-25.md`).

This module parses a folder of tables and says what each run is: present, refused and why, stopped,
or a departing echo. It opens no capture. What a run's rows hold is read through `RunRows`, which
raises `NotFormed` where a judged leaf is missing, mistyped or not finite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import constants as c
from . import identities
from .registration import Registration, StringsNote, World, changes
from .strictjson import DuplicateKey, is_finite, is_integer, is_number, loads, sha256


class NotFormed(Exception):
    """An entry that cannot be formed, and why."""


# ----- files -----


@dataclass
class TableFile:
    """One consumer's table: its state, its sha256 and its parsed content."""

    consumer: str
    name: str
    sha256: str | None = None
    data: dict | None = None
    refusals: list = field(default_factory=list)
    flags: list = field(default_factory=list)

    @property
    def absent(self) -> bool:
        """True where the folder has no such file."""
        return self.sha256 is None and not self.refusals and self.data is None


def read_sums(folder: Path):
    """The folder's SHA256SUMS as name to digest, with its faults. None where the file is absent."""
    path = Path(folder) / "SHA256SUMS"
    if not path.is_file():
        return None, []
    out, faults = {}, []
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (\S.*)", line)
        if match is None:
            faults.append(f"SHA256SUMS: the line {line!r} is not a digest, two spaces and a name")
        elif match.group(2) in out:
            faults.append(f"SHA256SUMS: {match.group(2)} stands twice")
        else:
            out[match.group(2)] = match.group(1)
    return out, faults


def contract_faults(data, consumer: str, part: int) -> list:
    """What makes a parsed file not this consumer's table: its top-level keys (TABLE section 2)."""
    if not isinstance(data, dict):
        return ["the file is not an object"]
    out = [
        f"the top-level key {key} is missing"
        for key in ("kind", "part", "consumer", "runs", "missing", "units")
        if key not in data
    ]
    if out:
        return out
    if data["kind"] != c.TABLE_KIND:
        out.append("kind is not the contract's")
    if data["part"] != part or isinstance(data["part"], bool):
        out.append("part is not the registered one")
    if data["consumer"] != consumer:
        out.append(f"consumer is {data['consumer']!r}")
    if data["units"] != c.UNITS:
        out.append("units are not the contract's")
    if not isinstance(data["runs"], dict):
        out.append("runs is not an object")
    if not isinstance(data["missing"], list) or not all(
        isinstance(name, str) for name in data["missing"]
    ):
        out.append("missing is not a list of names")
    return out


class TableSet:
    """The tables of a folder: one file per consumer, and every run's entry by name."""

    def __init__(self, files: dict, flags=(), retry: bool = False):
        self.files = files
        self.flags = list(flags)
        self.retry = retry
        self.runs = {}  # (consumer, name) -> entry
        self.missing = {}  # consumer -> names
        for consumer, file in files.items():
            self.missing[consumer] = set()
            if file.data is None or file.refusals:
                continue
            for name, entry in file.data["runs"].items():
                self.runs[consumer, name] = entry
            self.missing[consumer] = set(file.data["missing"])

    @classmethod
    def read(cls, folder, consumers, part: int = c.PART, retry: bool = False):
        """Read `table_<consumer>.json` of a folder. A file refused whole keeps its reasons and no
        content.
        """
        folder = Path(folder)
        sums, faults = read_sums(folder)
        flags = [["SHA256SUMS", fault] for fault in faults]
        if sums is None:
            flags.append(
                [
                    "SHA256SUMS",
                    "absent from the folder (recorded and flagged, it refuses nothing by itself)",
                ]
            )
        for path in sorted(folder.glob("table_*.json")):
            if path.name[len("table_") : -len(".json")] not in consumers:
                flags.append(["a file of no consumer", f"{path.name}: not read"])
        files = {}
        for consumer in consumers:
            name = f"table_{consumer}.json"
            file = TableFile(consumer, name)
            files[consumer] = file
            path = folder / name
            if not path.is_file():
                continue
            data = path.read_bytes()
            file.sha256 = sha256(data)
            if sums is not None and sums.get(name) is None:
                file.refusals.append("its sha256 is missing from SHA256SUMS")
            elif sums is not None and sums[name] != file.sha256:
                file.refusals.append("its sha256 departs from SHA256SUMS")
            try:
                parsed = loads(data)
            except DuplicateKey as error:
                file.refusals.append(f"a duplicate key: {error}")
                continue
            except ValueError as error:
                file.refusals.append(str(error))
                continue
            file.refusals += contract_faults(parsed, consumer, part)
            file.data = parsed
        return cls(files, flags, retry)

    @classmethod
    def from_data(cls, tables: dict, part: int = c.PART, retry: bool = False):
        """The same from parsed tables (the judge's own plants)."""
        files = {}
        for consumer, data in tables.items():
            file = TableFile(consumer, f"table_{consumer}.json", "in memory", data)
            file.refusals += contract_faults(data, consumer, part)
            files[consumer] = file
        return cls(files, (), retry)


def hash_folder(folder) -> dict:
    """The sha256 of every table of a folder, and of its SHA256SUMS, from the bytes alone (nothing
    is parsed).
    """
    folder = Path(folder)
    names = sorted(p.name for p in folder.glob("table_*.json")) + (
        ["SHA256SUMS"] if (folder / "SHA256SUMS").is_file() else []
    )
    return {
        "kind": c.HASHES_KIND,
        "files": {name: sha256((folder / name).read_bytes()) for name in names},
    }


# ----- the echo -----


class Echo:
    """What an echo's comparison found: departures, and keys that the inputs do not hold."""

    def __init__(self):
        self.departures, self.extras = [], []

    def depart(self, path, why=""):
        self.departures.append(f"{path}{': ' + why if why else ''}")


SETS = ("cells", "outside", "membranes", "channels", "junctions", "faces")
DEFAULT_EMPTY = ("channels", "junctions", "faces")
CONTROLS = ("leak", "pump", "channel", "junction")
POOL_DEFAULTS = {"root_node": 10, "world_id_start": 0}


def close(expected, got, tolerance=None) -> bool:
    """SPEC section 2.4: a number to 1e-12 of its own value, a declared zero exactly, an integer
    exactly.
    """
    if not is_finite(got):
        return False
    if tolerance is not None:
        return abs(got - expected) <= tolerance
    if isinstance(expected, int) or expected == 0:
        return got == expected
    return abs(got - expected) <= c.ECHO_RTOL * abs(expected)


def compare(expected, got, path: str, out: Echo):
    """One leaf or map of the echo. Maps by key; lists by position; an extra key is recorded."""
    if expected is None or isinstance(expected, (bool, str)):
        if type(got) is not type(expected) or got != expected:
            out.depart(path, f"{got!r} and not {expected!r}")
    elif is_number(expected):
        if not close(expected, got):
            out.depart(path, f"{got!r} and not {expected!r}")
    elif isinstance(expected, dict):
        if not isinstance(got, dict):
            out.depart(path, "not an object")
            return
        for key, value in expected.items():
            if key not in got:
                out.depart(f"{path}/{key}", "missing")
            else:
                compare(value, got[key], f"{path}/{key}", out)
        out.extras += [f"{path}/{key}" for key in got if key not in expected]
    elif isinstance(expected, list):
        if not isinstance(got, list) or len(got) != len(expected):
            out.depart(path, "not the same list")
            return
        for i, (a, b) in enumerate(zip(expected, got, strict=True)):
            compare(a, b, f"{path}/{i}", out)


def parse_schedule(value):
    """A schedule or a path as a list of [time, value] of finite numbers, or None where it is not
    one.
    """
    if not isinstance(value, list):
        return None
    for item in value:
        if not isinstance(item, list) or len(item) != 2 or not all(is_finite(v) for v in item):
            return None
    return value


def same_schedule(expected, got) -> bool:
    """Two schedules by their changes (SPEC section 3.2), times and values to 1e-12 relative."""
    a, b = changes(expected), changes(got)
    return len(a) == len(b) and all(
        close(float(x[0]), y[0]) and close(float(x[1]), y[1]) for x, y in zip(a, b, strict=True)
    )


def as_map(value):
    """A set of entities as a map. An empty list is the empty set. None where it is neither."""
    if isinstance(value, dict):
        return value
    return {} if value == [] and isinstance(value, list) else None


def compare_block(expected: dict, got, world: World, out: Echo):
    """An ionic run's block against the inputs' (SPEC section 2.4)."""
    if not isinstance(got, dict):
        out.depart("inputs", "not an object")
        return
    for key, value in expected.items():
        if key == "controls":
            compare_controls(value, got.get("controls", {}), world, out)
        elif key in SETS:
            compare_set(key, value, got, world, out)
        elif key == "species":
            compare(value, got.get(key), f"inputs/{key}", out)
            if isinstance(got.get(key), dict):
                extra_entities(f"inputs/{key}", got[key], value, out)
        elif key not in got:
            out.depart(f"inputs/{key}", "missing")
        else:
            compare(value, got[key], f"inputs/{key}", out)
    out.extras += [f"inputs/{key}" for key in got if key not in expected and key != "assembly"]


def compare_set(key, expected, got, world: World, out: Echo):
    """A set of entities, by ID."""
    if key not in got and key in DEFAULT_EMPTY:
        found = {}
    else:
        found = as_map(got.get(key))
    wanted = as_map(expected)
    if found is None:
        out.depart(f"inputs/{key}", "missing or not a map")
        return
    if not wanted and found:
        out.depart(f"inputs/{key}", "not empty")
        return
    for name, value in wanted.items():
        path = f"inputs/{key}/{name}"
        if name not in found:
            out.depart(path, "missing")
            continue
        entity = found[name]
        if not isinstance(entity, dict):
            out.depart(path, "not an object")
            continue
        if key == "membranes" and "pump" not in entity and value.get("pump") is None:
            entity = dict(entity, pump=None)
        if key == "membranes" and "pump" not in value:
            value = dict(value, pump=None)
        if key == "outside":
            charges = [
                abs(world.block["cells"][m["inside"]]["initial_charge_C"])
                for m in world.block["membranes"].values()
                if m["outside"] == name
            ]
            rest = {k: v for k, v in value.items() if k != "initial_charge_C"}
            compare(rest, {k: v for k, v in entity.items() if k != "initial_charge_C"}, path, out)
            charge = value.get("initial_charge_C")
            if charge is not None and not close(
                charge, entity.get("initial_charge_C"), c.ECHO_RTOL * sum(charges)
            ):
                out.depart(
                    f"{path}/initial_charge_C",
                    f"{entity.get('initial_charge_C')!r} and not {charge!r}",
                )
            continue
        compare(value, entity, path, out)
    extra_entities(f"inputs/{key}", found, wanted, out)


def extra_entities(path, found, wanted, out: Echo):
    """An entity that the registered block does not have is a departing echo (the lead's ruling,
    Amendment 2).
    """
    for name in found:
        if name not in wanted:
            out.extras = [extra for extra in out.extras if extra != f"{path}/{name}"]
            out.depart(f"{path}/{name}", "an entity that the registered block does not have")


def compare_controls(expected, got, world: World, out: Echo):
    """The schedules, by their changes. `controls.channel` of an assembly world is class E and no
    echo.
    """
    if not isinstance(got, dict):
        out.depart("inputs/controls", "not an object")
        return
    for group in CONTROLS:
        if group == "channel" and world.assembly:
            continue
        path = f"inputs/controls/{group}"
        wanted, found = as_map(expected.get(group, {})), as_map(got.get(group, {}))
        if found is None:
            out.depart(path, "not a map")
            continue
        known = {
            "leak": world.membranes,
            "pump": world.membranes,
            "channel": world.channels,
            "junction": world.junctions,
        }[group]
        extra_entities(path, found, known, out)
        for name in [*wanted, *(n for n in found if n not in wanted and n in known)]:
            a = wanted.get(name, [[0.0, 1.0]])
            b = parse_schedule(found.get(name, [[0.0, 1.0]]))
            if b is None or not same_schedule(a, b):
                out.depart(f"{path}/{name}", "not the registered schedule")
            elif name not in wanted:
                out.extras.append(f"{path}/{name}")
    out.extras += [f"inputs/controls/{group}" for group in got if group not in CONTROLS]


def compare_pools(world: World, got, out: Echo):
    """A pool run's inputs. The seed is class E and no echo."""
    if not isinstance(got, dict):
        out.depart("inputs", "not an object")
        return
    for cell, pool in world.pools.items():
        path = f"inputs/{cell}"
        mine = got.get(cell)
        if not isinstance(mine, dict):
            out.depart(path, "missing or not an object")
            continue
        for key in ("channel", "stream_id"):
            compare(pool[key], mine.get(key), f"{path}/{key}", out)
        block = mine.get("pool")
        if not isinstance(block, dict):
            out.depart(f"{path}/pool", "missing or not an object")
            continue
        wanted, found = dict(pool["pool"]), dict(block)
        for key, value in POOL_DEFAULTS.items():
            wanted.setdefault(key, value)
            found.setdefault(key, value)
        if "initial_bond_indices" not in wanted or "initial_bond_indices" not in found:
            wanted.pop("initial_bond_indices", None)
            found.pop("initial_bond_indices", None)
        compare(wanted, found, f"{path}/pool", out)
        out.extras += [
            f"{path}/{key}" for key in mine if key not in ("channel", "stream_id", "seed", "pool")
        ]
    extra_entities("inputs", got, world.pools, out)


def echo(registration: Registration, note: StringsNote, run: dict, entry: dict) -> Echo:
    """A run's whole echo: world, seed_index, world_id, step_s, inputs, strings and declared_strings
    (CRITERIA section 5).
    """
    out = Echo()
    world = registration.worlds[run["world"]]
    for key in ("world", "seed_index", "world_id"):
        compare(run[key], entry.get(key), key, out)
    if run["step_s"] is None:
        compare(None, entry.get("step_s"), "step_s", out)
    elif not close(float(run["step_s"]), entry.get("step_s")):
        out.depart("step_s", f"{entry.get('step_s')!r} and not {run['step_s']!r}")
    inputs = entry.get("inputs")
    if registration.is_pool(run):
        compare_pools(world, inputs, out)
    else:
        compare_block(registration.expected_block(run), inputs, world, out)
        if world.assembly and isinstance(inputs, dict):
            assembly = inputs.get("assembly")
            if not isinstance(assembly, dict):
                out.depart("inputs/assembly", "missing or not an object")
            else:
                compare(
                    world.data["coupling"]["law"],
                    assembly.get("assembly_observable"),
                    "inputs/assembly/assembly_observable",
                    out,
                )
                out.extras += [
                    f"inputs/assembly/{key}" for key in assembly if key not in c.ASSEMBLY_KEYS
                ]
                for key, known in (("pool_seeds", world.pools), ("switch_list", world.channels)):
                    if isinstance(assembly.get(key), dict):
                        extra_entities(f"inputs/assembly/{key}", assembly[key], known, out)
            controls = inputs.get("controls")
            if isinstance(controls, dict) and isinstance(controls.get("channel"), dict):
                extra_entities("inputs/controls/channel", controls["channel"], world.channels, out)
    expected = note.expected(note_name(registration, run))
    strings = entry.get("strings")
    if not isinstance(strings, dict):
        out.depart("strings", "missing or not an object")
    else:
        for label in sorted(set(expected) | set(strings)):
            if label not in strings:
                out.depart(f"strings/{label}", "a missing label")
            elif label not in expected:
                out.depart(f"strings/{label}", "an extra label")
            elif strings[label] != expected[label]:
                out.depart(f"strings/{label}", "not the registered string")
    declared = entry.get("declared_strings")
    if not isinstance(declared, list) or not all(isinstance(s, str) for s in declared):
        out.depart("declared_strings", "missing or not a list of strings")
    elif set(declared) != set(expected.values()):
        out.depart("declared_strings", "an extra or a missing string")
    return out


def note_name(registration: Registration, run: dict) -> str:
    """The run whose labels a run has: its own, or its family's finest for a retry run."""
    return registration.families[run["family"]].finest if run["role"] == "retry" else run["name"]


# ----- what a run is -----


@dataclass
class RunState:
    """What a registered run is, in the tables that were read."""

    name: str
    run: dict
    consumer: str
    entry: dict | None = None
    missing: str | None = None  # why it is missing
    file_refused: list = field(default_factory=list)
    echo: list = field(default_factory=list)
    provenance: list = field(default_factory=list)  # [reason, detail]
    guard: list = field(default_factory=list)  # [comparison, detail]
    refusal_kind: str | None = None
    refusal_message: str | None = None
    completed: bool = False
    flags: list = field(default_factory=list)  # [what, detail]

    @property
    def judgable(self) -> bool:
        """True where its readouts are judged: it is there, its file stands and its echo is the
        registered run's.
        """
        return self.entry is not None and not self.file_refused and not self.echo

    @property
    def stopped(self) -> bool:
        """True for a stop by the engine's own check."""
        return self.judgable and self.refusal_kind == "check"

    @property
    def refused(self) -> bool:
        """True where it is refused or missing, whatever the cause."""
        kind = self.refusal_kind in ("definition", "domain", "harness")
        return bool(
            self.missing or self.file_refused or self.echo or self.provenance or self.guard or kind
        )

    @property
    def partial(self) -> bool:
        """True for a refused or stopped run whose echo stands: it is judged on the rows that it
        holds (CRITERIA section 5).
        """
        return self.judgable and bool(
            self.refusal_kind is not None or self.provenance or self.guard
        )

    def causes(self) -> list:
        """Every cause of its refusal, stop or absence."""
        out = []
        if self.missing:
            out.append(f"missing: {self.missing}")
        out += [f"its file is refused: {reason}" for reason in self.file_refused]
        out += [f"a departing echo: {path}" for path in self.echo]
        out += [f"provenance, {reason}: {detail}" for reason, detail in self.provenance]
        out += [f"the copy guard ({which}): {detail}" for which, detail in self.guard]
        if self.refusal_kind == "check":
            out.append(f"stopped by the engine's own check: {self.refusal_message}")
        elif self.refusal_kind:
            out.append(f"refused, kind {self.refusal_kind}: {self.refusal_message}")
        return out

    def record(self) -> dict:
        """The state as JSON."""
        return {
            "consumer": self.consumer,
            "role": self.run["role"],
            "present": self.entry is not None,
            "judged": self.judgable,
            "refused": self.refused,
            "stopped": self.stopped,
            "completed": self.completed,
            "causes": self.causes(),
            "reasons": [reason for reason, _ in self.provenance],
            "flags": self.flags,
        }


def provenance(
    registration: Registration, note: StringsNote, run: dict, entry: dict, shared: set
) -> list:
    """The provenance faults of CRITERIA section 5's table, as [reason, detail]."""
    out = []
    world = registration.worlds[run["world"]]
    pool = registration.is_pool(run)
    source = entry.get("source")
    if not isinstance(source, dict):
        out.append(["source incomplete", "missing or not an object"])
    else:
        for key in c.SOURCE_STRINGS:
            if not isinstance(source.get(key), str) or not source[key]:
                out.append(
                    ["source incomplete" if key != "snapshot" else "a missing snapshot", key]
                )
        if not isinstance(source.get("checkout_dirty"), bool):
            out.append(["source incomplete", "checkout_dirty"])
        elif source["checkout_dirty"]:
            out.append(["checkout_dirty", "true"])
        if not is_integer(source.get("blas_threads")):
            out.append(["source incomplete", "blas_threads"])
        if (
            isinstance(source.get("engine_revision"), str)
            and source["engine_revision"] != note.revision
        ):
            out.append(["engine_revision", "not the strings note's"])
        if (
            isinstance(source.get("snapshot_patch_sha256"), str)
            and source["snapshot_patch_sha256"] != c.EMPTY_SHA256
        ):
            out.append(["snapshot_patch_sha256", "not an empty file's"])
    digest = entry.get("record_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        out.append(["a missing record_sha256", repr(digest)])
    elif digest in shared:
        out.append(["a shared record_sha256", digest])
    if entry.get("host_patch") is not None:
        out.append(["host_patch", "not null"])
    t = entry.get("t")
    if (
        isinstance(t, list)
        and all(is_finite(v) for v in t)
        and any(b <= a for a, b in zip(t, t[1:], strict=False))
    ):
        out.append(["t", "does not strictly increase"])
    status, refusal = entry.get("status"), entry.get("refusal")
    if status not in ("completed", "refused") or (status == "completed") != (refusal is None):
        out.append(["status", f"{status!r} disagrees with refusal"])
    elif refusal is not None and (
        not isinstance(refusal, dict) or refusal.get("kind") not in c.REFUSAL_KINDS
    ):
        out.append(["status", "a refusal that has no kind of the contract"])
    if not pool and status == "completed":
        out += steps_faults(registration, run, entry, world)
    if pool:
        inputs, pools = entry.get("inputs"), entry.get("pool")
        for cell in world.pools:
            mine = inputs.get(cell) if isinstance(inputs, dict) else None
            other = pools.get(cell) if isinstance(pools, dict) else None
            if (
                isinstance(mine, dict)
                and isinstance(other, dict)
                and "seed" in mine
                and "seed" in other
                and mine["seed"] != other["seed"]
            ):
                out.append(["pool seed", f"pool.{cell}.seed differs from inputs.{cell}.seed"])
    return out


def steps_faults(registration: Registration, run: dict, entry: dict, world: World) -> list:
    """`steps` against its range (TABLE section 3)."""
    start = registration.restart_time(run) or 0.0
    least = round((world.end_s - start) / run["step_s"])
    most = least + (registration.events(run) if world.assembly else 0)
    steps = entry.get("steps")
    if not is_integer(steps):
        return [["steps", f"{steps!r} is no integer"]]
    if steps > most:
        return [
            [
                "off_grid_change" if not world.assembly else "steps",
                f"{steps} accepted steps, and at most {most}",
            ]
        ]
    if steps < least:
        return [["steps", f"{steps} accepted steps, and at least {least}"]]
    return []


def recorded_flags(registration: Registration, run: dict, entry: dict) -> list:
    """What the checker is told of a run's recorded-only leaves, as [what, detail]."""
    out = []
    world = registration.worlds[run["world"]]
    pool = registration.is_pool(run)
    out += [["a key is absent", key] for key in c.RUN_KEYS if key not in entry]
    extra = [key for key in entry if key not in c.RUN_KEYS and key != "off_grid"]
    if extra:
        out.append(
            [
                "extra keys",
                {
                    key: entry[key]
                    if isinstance(entry[key], (bool, int, float, str))
                    else "recorded"
                    for key in extra
                },
            ]
        )
    if entry.get("variant") != run["variant"]:
        out.append(["variant", f"{entry.get('variant')!r} and not {run['variant']!r}"])
    for key in ("definition", "checks"):
        if entry.get(key) is None or (entry.get("status") == "completed" and not entry[key]):
            out.append(["recorded leaf", f"{key} is missing or empty"])
        elif not all_finite(entry[key]):
            out.append(["recorded leaf", f"{key} holds a number that is not finite"])
    if not isinstance(entry.get("record"), str) or not entry.get("record"):
        out.append(["recorded leaf", "record is missing"])
    restart = entry.get("restart")
    if run["role"] != "support" and restart is not None:
        out.append(["restart", "not null in a run that is no restart"])
    refusal = entry.get("refusal")
    if isinstance(refusal, dict):
        known = ("kind", "message", "time_s", "second_pass_completed")
        more = {k: v for k, v in refusal.items() if k not in known}
        if more:
            out.append(["refusal, keys beyond the contract's", more])
        if refusal.get("second_pass_completed") not in (None, False):  # Amendment 2, item 7
            out.append(["second pass", "it completed where the run was refused"])
        if not isinstance(refusal.get("message"), str):
            out.append(["refusal", "its message is missing"])
        if (refusal.get("kind") == "check") != is_finite(refusal.get("time_s")):
            out.append(["refusal", "time_s is a number for `check` and null otherwise"])
    source = entry.get("source")
    if (
        isinstance(source, dict)
        and source.get("cpu_model") != registration.legacy["captures"]["cpu_model"]
    ):
        out.append(["cpu_model", "not the captures' machine, on which class E holds"])
    declared = entry.get("declared_strings")
    if (
        isinstance(declared, list)
        and all(isinstance(s, str) for s in declared)
        and declared != sorted(set(declared))
    ):
        out.append(["declared_strings", "not sorted, or a string stands twice"])
    if pool:
        if entry.get("steps") is not None:
            out.append(["steps", "not null in a pool run"])
        for key, empty in (("t", []), ("rows", {}), ("potential_t", []), ("potentials", {})):
            if entry.get(key) != empty:
                out.append(["recorded leaf", f"{key} is not empty in a pool run"])
        pools = entry.get("pool")
        for cell in world.pools:
            mine = pools.get(cell) if isinstance(pools, dict) else None
            if isinstance(mine, dict):
                out += [
                    ["recorded leaf", f"pool.{cell}.{key} is missing or mistyped"]
                    for key in ("seed", "stream_id")
                    if not is_integer(mine.get(key))
                ]
        return out
    t = entry.get("t")
    start = registration.restart_time(run)
    if isinstance(t, list) and t and is_finite(t[0]):
        if start is None and abs(t[0]) > c.TIME_TOL_S:
            out.append(["t", "its first time is not 0"])
        if start is not None and t[0] < start - c.TIME_TOL_S:
            out.append(["t", "a restart's first time is before its checkpoint's"])
    inputs = entry.get("inputs")
    if world.assembly and isinstance(inputs, dict) and isinstance(inputs.get("assembly"), dict):
        fingerprint = inputs["assembly"].get("composed_file_fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            out.append(
                [
                    "recorded leaf",
                    "inputs.assembly.composed_file_fingerprint is missing or mistyped",
                ]
            )
    out += absent_pump_flags(world, entry.get("rows"))
    out += [
        ["recorded leaf", f"{key} is not null in an ionic run"]
        for key in ("pool", "path")
        if entry.get(key) is not None
    ]
    held = entry.get("potential_t")
    if (
        start is None
        and isinstance(held, list)
        and held
        and is_finite(held[0])
        and abs(held[0]) > c.TIME_TOL_S
    ):
        out.append(["potential_t", "its first time is not 0"])
    for key, times, known in (
        ("rows", t, set(world.row_series())),
        ("potentials", held, {"voltage", "phi_out"}),
    ):
        values = entry.get(key)
        if not isinstance(values, dict):
            continue
        extra = sorted(set(values) - known)
        if extra:
            out.append(["extra series", extra])
        if not isinstance(times, list):
            continue
        bad = []
        for series, table in values.items():
            if isinstance(table, dict):
                for entity, listed in table.items():
                    if (
                        not isinstance(listed, list)
                        or len(listed) != len(times)
                        or not np.all(np.isfinite(column(listed)))
                    ):
                        bad.append(f"{series}/{entity}")
        if bad:
            out.append(
                [
                    key,
                    f"a list of another length, or a value that is missing, mistyped or not "
                    f"finite: {bad[:5]} ({len(bad)})",
                ]
            )
    return out


def absent_pump_flags(world: World, rows) -> list:
    """A pump's series may be written for a membrane that has none, as zeros. Others are flagged."""
    out = []
    for series in ("pump", "heat_pump", "work_pump"):
        table = rows.get(series) if isinstance(rows, dict) else None
        for membrane, values in table.items() if isinstance(table, dict) else ():
            if membrane in world.membranes and membrane not in world.pumps:
                if not isinstance(values, list) or not np.all(column(values) == 0.0):
                    out.append(["a pump's row without a pump", f"{series}/{membrane} is not zero"])
    return out


def column(values: list) -> np.ndarray:
    """A list of JSON values as doubles. What is no finite number (a boolean, a string, null, NaN,
    infinity) is NaN.
    """
    if set(map(type, values)) <= {float, int}:
        try:
            return np.array(values, dtype=float)
        except OverflowError:
            pass
    out = np.full(len(values), np.nan)
    for i, value in enumerate(values):
        if is_finite(value):
            try:
                out[i] = value
            except OverflowError:
                continue
    return out


def all_finite(value) -> bool:
    """True where no number within a JSON value is NaN or infinite."""
    if isinstance(value, dict):
        return all(all_finite(v) for v in value.values())
    if isinstance(value, list):
        return all(all_finite(v) for v in value)
    return not is_number(value) or is_finite(value)


def assess(
    registration: Registration,
    note: StringsNote,
    tables: TableSet,
    retry: TableSet | None = None,
    owed=(),
) -> tuple:
    """Every registered run's state, and what else the tables hold. A retry's runs are read from
    `retry`, when they are owed.
    """
    states, ignored = {}, []
    for consumer, names in tables.missing.items():
        for name in sorted(names - set(registration.runs)):
            ignored.append(
                {
                    "consumer": consumer,
                    "run": name,
                    "what": "a name in `missing` that the inputs do not list",
                }
            )
    sets = [tables] + ([retry] if retry is not None else [])
    digests = {}
    for table in sets:
        for (_, name), entry in table.runs.items():
            digest = entry.get("record_sha256") if isinstance(entry, dict) else None
            if isinstance(digest, str):
                digests.setdefault(digest, []).append(name)
    shared = {digest for digest, names in digests.items() if len(names) > 1}

    runs = dict(registration.runs)
    retried = {}
    for name in owed:
        retried[name] = registration.retry_run(name)
    for table in sets:
        for (consumer, name), _ in table.runs.items():
            known = runs.get(name) or retried.get(name)
            if known is None:
                rule = registration.retry_run(name)
                what = (
                    "a retry run that is not owed" if rule else "a run that the inputs do not list"
                )
                ignored.append(
                    {
                        "consumer": consumer,
                        "run": name,
                        "what": f"{what}: ignored, recorded and flagged",
                    }
                )
            elif known["consumer"] != consumer:
                ignored.append(
                    {
                        "consumer": consumer,
                        "run": name,
                        "what": f"a run of {known['consumer']}, in another's table: ignored",
                    }
                )

    for name, run in [*runs.items(), *retried.items()]:
        consumer = run["consumer"]
        table = retry if name in retried and retry is not None else tables
        state = RunState(name, run, consumer)
        states[name] = state
        file = table.files.get(consumer)
        if file is not None and file.refusals:
            state.file_refused = list(file.refusals)
            state.missing = None
            continue
        entry = table.runs.get((consumer, name))
        if entry is None:
            listed = name in table.missing.get(consumer, ())
            state.missing = "in the table's `missing`" if listed else "in neither list of any table"
            continue
        if name in table.missing.get(consumer, ()):
            state.flags.append(["missing", "the run stands in `runs` and in `missing`"])
        if not isinstance(entry, dict):
            state.entry = {}
            state.echo = ["the entry is not an object"]
            continue
        state.entry = entry
        found = echo(registration, note, run, entry)
        state.echo = found.departures
        if found.extras:
            state.flags.append(["echo, keys that the inputs do not hold", found.extras])
        state.provenance = provenance(registration, note, run, entry, shared)
        refusal = entry.get("refusal")
        if refusal is not None:
            kind = refusal.get("kind") if isinstance(refusal, dict) else None
            state.refusal_kind = kind if kind in c.REFUSAL_KINDS else "harness"
            state.refusal_message = refusal.get("message") if isinstance(refusal, dict) else None
        switch = entry.get("off_grid")
        if switch is True and name not in registration.profile.get("off_grid_runs", ()):
            if state.refusal_kind != "check":
                state.refusal_kind, state.refusal_message = (
                    "harness",
                    "the off-grid switch is on (Amendment 1, item 6)",
                )
            state.flags.append(["off_grid", "the switch is on"])
        elif switch not in (None, False, True):
            state.flags.append(["off_grid", f"{switch!r} is no boolean"])
        state.completed = entry.get("status") == "completed" and refusal is None
        state.flags += recorded_flags(registration, run, entry)
    return states, ignored


# ----- what a run's rows hold -----


class RunRows:
    """The rows and potentials of a run, at the times that an entry or an identity asks for."""

    def __init__(self, world: World, entry: dict):
        self.world, self.entry_ = world, entry
        self.rows = entry.get("rows")
        self.potentials = entry.get("potentials")
        self._index, self._held, self._columns = {}, {}, {}

    def _times(self, key):
        if key not in self._held:
            times = self.entry_.get(key)
            good = isinstance(times, list) and bool(np.all(np.isfinite(column(times))))
            self._held[key] = column(times) if good else None
        if self._held[key] is None:
            raise NotFormed(f"{key} is missing or mistyped")
        return self._held[key]

    def index(self, times, key="t") -> list:
        """The row of each compared time. Each needs exactly one (CRITERIA section 4.3)."""
        times = tuple(times)
        if (key, times) not in self._index:
            held = self._times(key)
            out = []
            for time in times:
                found = np.flatnonzero(np.abs(held - time) <= c.TIME_TOL_S)
                if len(found) != 1:
                    raise NotFormed(f"{len(found)} rows of {key} at {time!r} s")
                out.append(int(found[0]))
            self._index[key, times] = out
        return self._index[key, times]

    def held(self, times, key="t") -> tuple:
        """The compared times that have exactly one row."""
        out = []
        for time in times:
            try:
                self.index((time,), key)
            except NotFormed:
                continue
            out.append(time)
        return tuple(out)

    def _table(self, where, key, series, entities, rows, times_key):
        if not isinstance(where, dict) or not isinstance(where.get(series), dict):
            raise NotFormed(f"{key}.{series} is missing or mistyped")
        table = where[series]
        length = len(self._times(times_key))
        rows = list(rows)
        out = np.empty((len(rows), len(entities)))
        for i, entity in enumerate(entities):
            values = table.get(entity)
            if not isinstance(values, list) or len(values) != length:
                raise NotFormed(
                    f"{key}.{series}.{entity} is missing, mistyped or not as long as {times_key}"
                )
            where_ = (key, series, entity)
            if where_ not in self._columns:
                self._columns[where_] = column(values)
            out[:, i] = self._columns[where_][rows]
            if not np.all(np.isfinite(out[:, i])):
                bad = next(row for row in rows if not np.isfinite(self._columns[where_][row]))
                raise NotFormed(f"{key}.{series}.{entity} holds {values[bad]!r} at a compared time")
        return out

    def get(self, series: str, times) -> np.ndarray:
        """A series at given times, [time, entity]. `heat_membrane` is formed (READOUTS
        section 5).
        """
        if series == "heat_membrane":
            return self._heat_membrane(times)
        return self._table(
            self.rows, "rows", series, self.world.entities(series), self.index(times), "t"
        )

    def _heat_membrane(self, times):
        world = self.world
        out = np.zeros((len(times), len(world.membranes)))
        if not world.zero_routes:
            out += self.get("heat_leak", times)
        if world.pumps:
            values = self.get("heat_pump", times)
            for i, membrane in enumerate(world.pumps):
                out[:, world.membranes.index(membrane)] += values[:, i]
        if world.channels:
            values = self.get("heat_channel", times)
            for i, channel in enumerate(world.channels):
                out[:, world.membranes.index(world.block["channels"][channel]["membrane_id"])] += (
                    values[:, i]
                )
        return out

    def potential(self, name: str, times) -> np.ndarray:
        """A potential at given times, [time, entity]."""
        rows = self.index(times, "potential_t")
        return self._table(
            self.potentials, "potentials", name, self.world.entities(name), rows, "potential_t"
        )

    def entry(self, entry) -> np.ndarray:
        """An entry's array, [compared time, entity]."""
        if entry.where == "identity":
            with np.errstate(all="ignore"):
                value = identities.energy(self.world, self, entry.times)
            if not np.all(np.isfinite(value)):
                raise NotFormed("the energy identity is not finite on these rows")
            return value
        if entry.where == "potentials":
            return self.potential(entry.series, entry.times)
        return self.get(entry.series, entry.times)

    def voltage(self, times) -> np.ndarray:
        """The voltage by membrane."""
        return self.potential("voltage", times)

    def initial_voltage(self) -> np.ndarray:
        """V0: the run's own voltage at time 0."""
        return self.potential("voltage", (0.0,))[0]

    def heats(self) -> tuple:
        """The heat series that the energy identity sums."""
        return identities.heat_series(self.world)
