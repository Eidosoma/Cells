"""The repeat after the ID move (the protocol's §5, step 13; Part 2's Amendment 1, item 1): a run
made again on the final head has its registered table's entry, leaf by leaf.

    python -m validation.ensemble_reexpression.repeat --registered TABLE_DIR --new TABLE_DIR
        --runs NAME [NAME ...] --move MOVE_TABLE

It reads every `table_*.json` of the two folders (each against its `SHA256SUMS`, where the folder
has one), takes each named run's entry from each, and compares them by the classes below. It prints
one line for each run, `NAME: equal` or `NAME: unequal`, and under an unequal one the path of each
leaf that differs, and never a value. A sealed table is read by this program alone, so what a person
hears of it is equal or not, and where. Exit 0 only if every run is equal, 1 if one is not, 2 where
it cannot compare (a folder, a table or the move's table that it cannot read). A fault of its own is
told by its class alone, without a traceback, which could quote a value.

**The move's table** is scripts/id_moves.py's map (`cells.id_moves.map@1`, final: each row's old
spellings to its new ID), or a plain JSON object {old spelling: new ID}. `{}` is the identity.

**The leaf classes:**
- **Through the move's table:** every string, as a value or as a map's key, wherever it stands
  (`strings`, `declared_strings`, `definition`, `checks`, `inputs`, the refusal's message and the
  rest). The registered entry's string is read with every old spelling that the table names replaced
  by its new ID, as a whole token, the longest first: the move's own rule. A token here is not one
  that a letter, a digit, `_`, `@` or a `.` joins to more of an ID. An ID that the table does not
  name is compared as it stands. `declared_strings` is compared as a set. The keys of `strings` are
  the spec's labels, which do not move (`rk4` is both a label and a registered string), and are
  compared as they stand; its values are IDs.
- **Bit for bit:** every other leaf, by its JSON type and value, a double by its bits: `status`,
  `world`, `variant`, `seed_index`, `world_id`, `step_s`, `steps`, `t`, `rows`, `potential_t`,
  `potentials`, `pool`, `path`, `restart`, `host_patch`, `off_grid`, the refusal's kind and time,
  every number of `inputs` and `definition`, and `checks`: the ledgers' maxima and the engine's
  counts and simulated times, and a pool's events, histograms, dwell times, horizon, `backend`,
  `device` and `device_kind`.
- **Never:** `record_sha256`, `record` and `source` (NEVER below); `inputs.assembly.
  composed_file_fingerprint`; the fingerprints of what a driven run was made from, whose bytes hold
  IDs: `definition.made_from`'s `composed_file_sha256`, `composed_sha256`, `ionic_sha256`,
  `pools[].pool_sha256` and `worlds[].definition_sha256`; and in a pool run's `checks.<cell>`, the
  clocks that the exporter copies from each pool's result (`compile_seconds`, `elapsed_seconds`,
  `execute_seconds`, `total_seconds`, and the time of day `finished_utc`) and
  `checkpoint_manifest_sha256`, whose manifest holds the pool's definition and, for a restart's
  second leg, its parent's path. No other leaf of the exporter's is a clock.
"""

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

MAP_KIND = "cells.id_moves.map@1"
SUMS = "SHA256SUMS"
ANY = "*"  # In NEVER, any key or index.
NEVER = (
    ("record_sha256",),
    ("record",),
    ("source",),
    ("inputs", "assembly", "composed_file_fingerprint"),
    *(("definition", "made_from", name) for name in ("composed_file_sha256", "composed_sha256")),
    ("definition", "made_from", "ionic_sha256"),
    ("definition", "made_from", "pools", ANY, "pool_sha256"),
    ("definition", "made_from", "worlds", ANY, "definition_sha256"),
    *(
        ("checks", ANY, name)
        for name in (
            "compile_seconds",
            "elapsed_seconds",
            "execute_seconds",
            "total_seconds",
            "finished_utc",
            "checkpoint_manifest_sha256",
        )
    ),
)
HEADS = {rule[0] for rule in NEVER}  # A path that begins elsewhere is compared.
AS_A_SET = ("declared_strings",)  # The one leaf compared as a set.
LABELLED = ("strings",)  # The one map whose keys are labels, which do not move.
SHOWN = 200  # The paths shown for one run; the rest are counted.


class Refused(Exception):
    """What makes a comparison impossible (exit 2)."""


# ------------------------------------------------------------------ what is read


def moves(path):
    """{old spelling: new ID} of the move's table."""
    try:
        doc = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise Refused(f"the move's table {path} cannot be read ({type(error).__name__})") from None
    if isinstance(doc, dict) and doc.get("kind") == MAP_KIND:
        if doc.get("final") is not True:
            raise Refused("the move's map is not final")
        table = {}
        for row in doc["rows"]:
            for old in row["old"]:
                if table.setdefault(old, row["new"]) != row["new"]:
                    raise Refused("the move's map renames one spelling twice")
        return table
    if isinstance(doc, dict) and all(isinstance(v, str) for v in doc.values()):
        return doc
    raise Refused("the move's table is neither the move's map nor an object of old and new IDs")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def entries(folder):
    """{run: its entry} of a folder of tables, each table held to the folder's SHA256SUMS."""
    folder = Path(folder)
    paths = sorted(folder.glob("table_*.json"))
    if not paths:
        raise Refused(f"{folder} holds no table")
    if (folder / SUMS).is_file():
        lines = (line.split("  ", 1) for line in (folder / SUMS).read_text().splitlines() if line)
        listed = {pair[-1]: pair[0] for pair in lines}
        if any(listed.get(path.name) != digest(path) for path in paths):
            raise Refused(f"{folder}: a table is not what its {SUMS} lists")
    out = {}
    for path in paths:
        try:
            runs = dict(json.loads(path.read_text())["runs"])
        except (ValueError, KeyError, TypeError) as error:
            raise Refused(f"{path} cannot be read ({type(error).__name__})") from None
        for name, entry in runs.items():
            if out.setdefault(name, entry) is not entry:
                raise Refused(f"{folder}: two tables hold {name!r}")
    return out


# ------------------------------------------------------------------ the comparison


def renamer(table):
    """A string with each old spelling that the table names replaced by its new ID: whole tokens,
    the longest first, none joined by a letter, a digit, `_`, `@` or a `.` to more of an ID."""
    if not table:
        return lambda text: text
    spellings = "|".join(re.escape(old) for old in sorted(table, key=len, reverse=True))
    token = re.compile(rf"(?<![\w@.])(?:{spellings})(?![\w@])(?!\.\w)", re.ASCII)
    return lambda text: token.sub(lambda match: table[match[0]], text)


def never(path):
    if not path or path[0] not in HEADS:
        return False
    return any(
        len(path) >= len(rule) and all(r == ANY or r == p for r, p in zip(rule, path, strict=False))
        for rule in NEVER
    )


def same(registered, new):
    """Bit for bit: the same JSON type and value, a double by its bits."""
    if type(registered) is not type(new):
        return False
    if isinstance(new, float):
        bits = struct.pack("<d", registered) == struct.pack("<d", new)
        return bits or (registered != registered and new != new)  # NaN, which JSON keeps unsigned.
    return registered == new


def differences(registered, new, rename, path=()):
    """The paths of the leaves at which a registered entry and a new one differ (the docstring)."""
    if never(path):
        return []
    if path == AS_A_SET:
        if not (isinstance(registered, list) and isinstance(new, list)):
            return [path]
        moved = {rename(s) if isinstance(s, str) else s for s in registered}
        return [] if moved == set(new) else [path]
    if isinstance(registered, dict) and isinstance(new, dict):
        moved = {(key if path == LABELLED else rename(key)): v for key, v in registered.items()}
        out = [path] if len(moved) != len(registered) else []  # Two old keys, one new.
        for key in sorted(set(moved) | set(new)):
            here = (*path, key)
            if never(here):
                continue
            if key in moved and key in new:
                out += differences(moved[key], new[key], rename, here)
            else:
                out.append(here)
        return out
    if isinstance(registered, list) and isinstance(new, list):
        if len(registered) != len(new):
            return [path]
        out = []
        for k, (a, b) in enumerate(zip(registered, new, strict=True)):
            out += differences(a, b, rename, (*path, k))
        return out
    if isinstance(registered, str) and isinstance(new, str):
        return [] if rename(registered) == new else [path]
    return [] if same(registered, new) else [path]


def shown(path):
    """A path, a map's key by its name and a list's index in brackets."""
    out = ""
    for part in path:
        if isinstance(part, int):
            out += f"[{part}]"
        elif re.fullmatch(r"[\w<>-]+", part, re.ASCII):
            out += f".{part}" if out else part
        else:
            out += f"[{json.dumps(part)}]"
    return out or "(the entry)"


def compare(registered, new, runs, table):
    """{run: the paths that differ}; [] where the run is equal."""
    rename, out = renamer(table), {}
    for name in runs:
        if name not in registered or name not in new:
            out[name] = [f"(no entry in --{'registered' if name not in registered else 'new'})"]
            continue
        out[name] = [shown(p) for p in differences(registered[name], new[name], rename)]
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registered", type=Path, required=True, help="the registered tables")
    parser.add_argument("--new", type=Path, required=True, help="the tables made again")
    parser.add_argument("--runs", nargs="+", required=True, help="the runs to compare")
    parser.add_argument("--move", type=Path, required=True, help="the move's table")
    args = parser.parse_args(argv)
    try:
        if len(set(args.runs)) != len(args.runs):
            raise Refused("a run is named twice")
        found = compare(entries(args.registered), entries(args.new), args.runs, moves(args.move))
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # Its own fault: by its class alone (the module's docstring).
        print(f"refused: a fault of the comparison's own, {type(error).__name__}", file=sys.stderr)
        return 2
    for name, paths in found.items():
        print(f"{name}: {'unequal' if paths else 'equal'}")
        for path in paths[:SHOWN]:
            print(f"    {path}")
        if len(paths) > SHOWN:
            print(f"    ({len(paths) - SHOWN} more)")
    return 1 if any(found.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
