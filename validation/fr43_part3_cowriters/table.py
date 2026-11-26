"""FR-43 part 3's co-writers registration: the engine table from the runs' records alone (the
builder's exporter; spec/TABLE.md, the protocol's §6, step 6).

    python -m validation.fr43_part3_cowriters.table --inputs FILE --out DIR [--owed retry_owed.json]

Reads every record under DIR/records/ (run.py's, one per run) and writes:
- DIR/table/table_<world>.json for each world of the inputs: `kind`, `arm`, `units`, `runs` (each
  record's entry under its run's name, with `record`, the record's path under DIR, and
  `record_sha256`, its file's sha256) and `missing` (the world's registered runs with no record);
- DIR/table-retry/table_<world>-retry.json, only with --owed: the owed families' retry runs
  (CRITERIA.md §7's names) in the same shape;
- a SHA256SUMS in each folder: one line per table file, its sha256, two spaces, its name.

A record that is not a retry run's goes to its world's table, whatever its name (a name that no
inputs file registers is the judge's to ignore). Every entry is held to TABLE.md §3's shape
(run.validate) before anything is written, and a departure stops the export: it is a fault of the
driver, never a run's refusal. The exporter forms no difference, ratio, estimate or error, and
reads no reference.
"""

import argparse
import hashlib
import json
from pathlib import Path

from validation.fr43_part3_cowriters import run as driver
from validation.fr43_part3_cowriters import worlds

KIND = "fr43 part 3 co-writers engine table, version 2"
UNITS = {"amount": "fmol", "volume": "pL", "time": "s"}
RETRY_SUFFIX = " retry"


def records(out):
    """{run name: (record, its path under out, its file's sha256)} of every record under out."""
    found = {}
    for path in sorted((Path(out) / "records").glob("*.json")):
        data = path.read_bytes()
        record = json.loads(data)
        if record.get("kind") != driver.RECORD:
            raise ValueError(f"{path} is not a run record ({record.get('kind')!r})")
        name = record["name"]
        if name in found:
            raise ValueError(f"two records name the run {name!r}")
        found[name] = (record, path.relative_to(out).as_posix(), hashlib.sha256(data).hexdigest())
    return found


def entry_of(record, relative, digest):
    """A run's table entry: its record's entry, with `record` and `record_sha256`."""
    return dict(record["entry"], record=relative, record_sha256=digest)


def owed_runs(inputs, owed_path):
    """The owed retry runs' names: retry_owed.json's `runs` (CRITERIA.md §7), each a retry run of
    the inputs (its listed retry runs, or the rule's)."""
    owed = json.loads(Path(owed_path).read_text())
    known = worlds.runs(inputs, retry=True)
    names = list(owed["runs"])
    unknown = [n for n in names if n not in known]
    if unknown:
        raise ValueError(f"owed runs that are no retry run of the inputs: {unknown}")
    return {n: known[n] for n in names}


def tables(inputs_path, out, owed_path=None):
    """({file name: table} of table/, {file name: table} of table-retry/) (module docstring)."""
    inputs = worlds.read_inputs(inputs_path)
    arms = {world: int(arm) for arm, world in inputs["arms"].items()}
    found = records(out)
    faults = {}
    for name, (record, relative, digest) in found.items():
        entry = entry_of(record, relative, digest)
        kind = inputs["worlds"][entry["world"]]["kind"]
        bad = driver.validate(entry, kind)
        if bad:
            faults[name] = bad
    if faults:
        raise ValueError(f"entries that depart from TABLE.md §3: {faults}")
    registered = worlds.runs(inputs)
    owed = {} if owed_path is None else owed_runs(inputs, owed_path)
    main, retry = {}, {}
    for world in inputs["worlds"]:
        names = [n for n, r in registered.items() if r["world"] == world]
        held = {
            name: entry_of(*found[name])
            for name, (record, _, _) in found.items()
            if record["entry"]["world"] == world and not name.endswith(RETRY_SUFFIX)
        }
        main[f"table_{world}.json"] = dict(
            kind=KIND,
            arm=arms[world],
            units=dict(UNITS),
            runs=held,
            missing=sorted(n for n in names if n not in found),
        )
        wanted = [n for n, r in owed.items() if r["world"] == world]
        if wanted:
            retry[f"table_{world}-retry.json"] = dict(
                kind=KIND,
                arm=arms[world],
                units=dict(UNITS),
                runs={n: entry_of(*found[n]) for n in wanted if n in found},
                missing=sorted(n for n in wanted if n not in found),
            )
    return main, retry


def write(folder, files):
    """Each table as JSON (run.dumps: sorted keys, no NaN or infinity), and its SHA256SUMS."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    lines = []
    for name in sorted(files):
        text = driver.dumps(files[name])
        (folder / name).write_text(text)
        lines.append(f"{hashlib.sha256(text.encode()).hexdigest()}  {name}")
    (folder / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    return folder


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--owed", type=Path, help="retry_owed.json (CRITERIA.md §7)")
    args = parser.parse_args(argv)
    main_tables, retry_tables = tables(args.inputs, args.out, args.owed)
    write(args.out / "table", main_tables)
    if retry_tables:
        write(args.out / "table-retry", retry_tables)
    print(json.dumps({
        "table": {n: dict(runs=len(t["runs"]), missing=len(t["missing"]))
                  for n, t in main_tables.items()},
        "table-retry": {n: dict(runs=len(t["runs"]), missing=len(t["missing"]))
                        for n, t in retry_tables.items()},
    }))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
