"""FR-43 part 3's co-writers registration: the format sample (spec/TABLE.md §5; the builder's).

    python -m validation.fr43_part3_cowriters.sample make --inputs FILE --out RUNS --cpus 6,7
    python -m validation.fr43_part3_cowriters.sample scrub --runs RUNS --out SAMPLE
    python -m validation.fr43_part3_cowriters.sample keys --folder SAMPLE

`make` runs RUNS (the invented runs below, one process each, through run.launch) and exports
their tables with the registered exporter (table.py), the retry folder from an owed list of this
file's (OWED: the invented set's listed retry runs). `scrub` writes SAMPLE: those tables with every
number replaced by a meaningless one of its type, their SHA256SUMS, and README.md, which lists
every key and type to the leaf (`keys`). Run it from a frozen snapshot of the builder's head, so
that each run's `source` is the registered runs' kind.

**What the sample covers** (TABLE.md §5), from the references' invented inputs
(inputs_invented.json): a completed run of each world, in each declared order; each kind of
variant: a restart (W5's and W6's, with their uninterrupted runs) and the Lie plant (with its
honest run); a refused run of each kind: `domain` at parse (the invented `refused` run) and at
run time (the invented `stopped` run), and `definition`, `check` and `harness` (run.py's fault
switches on one W5 run: the format sample's own runs, never registered); a stopped run; and the
retry folder (one W5 retry run, the rest of its family's listed in `missing`).

**The scrub:** an integer becomes 7 and a float 0.5, but `t`, `samples_echo` and `events.time_s`,
whose items become 0.5, 1.0, 1.5 and on, so they still increase. A boolean, a string and null are
kept, and so is the top-level `arm`, whose value TABLE.md §2 makes part of its type (1, 2 or 3).
Nothing of a run's numbers survives, and no length, order or equality of the sample means
anything (TABLE.md §5).
"""

import argparse
import hashlib
import json
from pathlib import Path

from validation.fr43_part3_cowriters import run as driver
from validation.fr43_part3_cowriters import table as exporter
from validation.fr43_part3_cowriters import worlds

RUNS = (
    "W5 reactions-first h=0.0244140625 c0",
    "W5 population-first h=0.0244140625 c1",
    "W5-exact reactions-first h=0.0244140625 c0",
    "W5-exact population-first h=0.0244140625 c2",
    "W6 gene-first h=0.46875 c0",
    "W6 population-first h=0.46875 c1",
    "W5-exact reactions-first h=0.78125 c0 refused",
    "W6 gene-first h=0.46875 c0 stopped",
    "W5 reactions-first h=0.006103515625 c0",
    "W5 reactions-first h=0.006103515625 c0 restart",
    "W6 gene-first h=0.1171875 c0",
    "W6 gene-first h=0.1171875 c0 restart",
    "W5 reactions-first h=0.0030517578125 c0",
    "W5 reactions-first h=0.0030517578125 c0 lie",
    "W5 reactions-first h=0.0003814697265625 c0 retry",
)
FAULT_RUN = "W5 reactions-first h=0.0244140625 c0"
OWED = dict(
    kind="fr43 part 3 co-writers retry, version 2",
    families=["W5 reactions-first"],
    runs=[f"W5 reactions-first h=0.0003814697265625 c{c} retry" for c in range(4)],
)
INCREASING = ("t", "samples_echo", "time_s")
KINDS = {  # The key lists of the README, by the kind of world: their tables.
    "reactions (W5 and W5-exact)": ("table_W5.json", "table_W5-exact.json", "table_W5-retry.json"),
    "gene (W6)": ("table_W6.json", "table_W6-retry.json"),
}
INTEGER, FLOAT = 7, 0.5


# ------------------------------------------------------------------ make


def make(inputs_path, runs_dir, cpus):
    """The sample's runs and their tables under runs_dir (module docstring)."""
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    inputs = worlds.read_inputs(inputs_path)
    for name in RUNS:
        worlds.find_run(inputs, name)  # Every sample run is an invented run.
    faults = [(FAULT_RUN, fault) for fault in driver.FAULTS]
    done = driver.launch(inputs_path, runs_dir, cpus, list(RUNS), faults=faults)
    owed = runs_dir / "retry_owed_sample.json"
    owed.write_text(json.dumps(OWED, indent=1) + "\n")
    main, retry = exporter.tables(inputs_path, runs_dir, owed)
    exporter.write(runs_dir / "table", main)
    exporter.write(runs_dir / "table-retry", retry)
    return done


# ------------------------------------------------------------------ scrub


def scrubbed(value, key=None):
    """value with every number replaced (module docstring); `key` is its parent key."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return INTEGER
    if isinstance(value, float):
        return FLOAT
    if isinstance(value, list):
        if key in INCREASING and all(isinstance(v, float) for v in value):
            return [0.5 * (i + 1) for i in range(len(value))]
        return [scrubbed(v) for v in value]
    return {k: scrubbed(v, k) for k, v in value.items()}


def scrub(runs_dir, sample_dir):
    """SAMPLE from RUNS' tables (module docstring); returns the README's key list."""
    runs_dir, sample_dir = Path(runs_dir), Path(sample_dir)
    for folder in ("table", "table-retry"):
        files = {}
        for path in sorted((runs_dir / folder).glob("table_*.json")):
            made = json.loads(path.read_text())
            out = scrubbed(made)
            out["arm"] = made["arm"]  # Its value is its type (TABLE.md §2).
            files[path.name] = out
        exporter.write(sample_dir / folder, files)
    listed = {kind: keys(sample_dir, files) for kind, files in KINDS.items()}
    (sample_dir / "README.md").write_text(readme(sample_dir, listed))
    return listed


# ------------------------------------------------------------------ keys and types


# Maps keyed by an identifier, each printed as a placeholder: {key: its keys' placeholder}.
MAPS = {
    "runs": "<run name>",
    "initial_amount_fmol": "<species>",
    "permeability_m_per_s": "<species>",
    "material_balance_atol_fmol": "<species>",
    "diffusivity_m2_per_s": "<species>",
    "moieties": "<moiety>",
    "weights": "<species>",
    "draws": "<species>",
    "releases": "<species>",
    "saturation_mM": "<species>",
    "mu_RT": "<species>",
    "monomers": "<species>",
    "reactants": "<species or unit state>",
    "products": "<species or unit state>",
    "conductance_pL_per_s": "<unit state>",
    "initial_counts": "<unit state>",
}


def keys(folder, tables=None):
    """{key path: sorted type names} over a folder's tables (table/ and table-retry/; only the
    files named in `tables` where given), to the
    leaf: `table.<key>` for a table's top level and `entry.<key>` for a run's entry; `[]` an item
    of a list; the keys of a map keyed by an identifier (MAPS) as its placeholder. The types are
    JSON's: object, array, string, integer, number (with a fraction), boolean, null."""
    found = {}
    names = {dict: "object", list: "array", str: "string", int: "integer", float: "number",
             bool: "boolean", type(None): "null"}  # fmt: skip

    def walk(path, value, parent, item=False):
        found.setdefault(path, set()).add(names[type(value)])
        if isinstance(value, dict):
            placeholder = None if item else MAPS.get(parent)
            for k, v in value.items():
                walk(f"{path}.{placeholder or k}", v, k)
        elif isinstance(value, list):
            for v in value:
                walk(f"{path}[]", v, parent, item=True)

    for sub in ("table", "table-retry"):
        for path in sorted((Path(folder) / sub).glob("table_*.json")):
            if tables is not None and path.name not in tables:
                continue
            made = json.loads(path.read_text())
            entries = made.pop("runs")
            found.setdefault("table.runs", set()).add(names[type(entries)])
            for entry in entries.values():
                found.setdefault("table.runs.<run name>", set()).add(names[type(entry)])
                for k, v in entry.items():
                    walk(f"entry.{k}", v, k)
            for k, v in made.items():
                walk(f"table.{k}", v, k)
    return {p: sorted(t) for p, t in sorted(found.items())}


def kinds_found(folder):
    """What the sample's entries are, by status, refusal kind, variant and restart/plant."""
    out = {}
    for sub in ("table", "table-retry"):
        for path in sorted((Path(folder) / sub).glob("table_*.json")):
            for name, entry in json.loads(path.read_text())["runs"].items():
                refusal = entry["refusal"]
                label = (
                    f"{sub}/{path.name}: {entry['status']}"
                    + (f" (kind {refusal['kind']})" if refusal else "")
                    + (f", variant {entry['variant']!r}" if entry["variant"] else "")
                    + (", restart" if entry["restart"] else "")
                    + (", host_patch" if entry["host_patch"] else "")
                )
                out.setdefault(label, []).append(name)
    return out


def readme(folder, listed):
    """The sample's README: what it is, what it covers, the scrub, and every key and type."""
    folder = Path(folder)
    sums = {
        sub: (folder / sub / "SHA256SUMS").read_text().strip().splitlines()
        for sub in ("table", "table-retry")
    }
    lines = [
        "# The format sample (TABLE.md §5)",
        "",
        "The builder's table code (validation/fr43_part3_cowriters: run.py's records, table.py's "
        "export) run on the references' invented worlds (`inputs_invented.json`), then every "
        "number replaced by a meaningless one of its type (sample.py's scrub): an integer by "
        f"{INTEGER}, a number with a fraction by {FLOAT}, and the items of `t`, `samples_echo` and "
        "`events.time_s` by 0.5, 1.0, 1.5 and on. Booleans, strings and nulls are kept, and so is "
        "the top-level `arm`, whose value TABLE.md §2 makes part of its type. **Nothing may be "
        "taken from it but keys and types:** no number, length, order or equality (TABLE.md §5).",
        "",
        "## Files",
        "",
        "- `table/`: `table_W5.json`, `table_W5-exact.json`, `table_W6.json` and `SHA256SUMS` "
        "(of these files, as scrubbed);",
        "- `table-retry/`: `table_W5-retry.json` (the invented set's one owed family, "
        "`W5 reactions-first`: one retry run made, the other three in `missing`) and its "
        "`SHA256SUMS`.",
        "",
        "SHA256SUMS as written:",
        "",
        "```text",
        *[f"{sub}/ {line}" for sub, rows in sums.items() for line in rows],
        "```",
        "",
        "## What the entries are",
        "",
        "Each run's entry by its status, its refusal's kind, its variant, and whether it holds a "
        "`restart` or a `host_patch`. The runs named `... fault <kind>` are the sample's own "
        "(run.py's fault switches: `definition`, a misspelt channel key; `check`, the co-writer's "
        "books raised at a checkpoint, which the engine's row checks refuse; `harness`, a trace "
        "shorter than the run's events): no inputs file registers them. Every other name is an "
        "invented run's. The invented set's other runs are in `missing`.",
        "",
    ]
    for label, names in sorted(kinds_found(folder).items()):
        lines.append(f"- {label}: " + "; ".join(f"`{n}`" for n in sorted(names)))
    lines += [
        "",
        "## Keys and types, to the leaf",
        "",
        "`table.<key>` is a table's top level and `entry.<key>` a run's entry (every run's, of "
        "every table): `table.runs.<run name>` is an entry, whose keys are listed as "
        "`entry.<key>`. `[]` is an item of a list. A map keyed by an identifier shows its keys as "
        "a placeholder: " + ", ".join(sorted(set(MAPS.values()))) + ". A path with several types "
        "holds one of them by the kind of run (a null `refusal` in a completed run, for "
        "instance). JSON's types: object, array, string, integer, number (with a fraction), "
        "boolean, null. What stands under `entry.definition`, `entry.checks` and "
        "`entry.pools_at_event` is the engine's own, recorded and never judged.",
        "",
    ]
    for kind, paths in listed.items():
        files = ", ".join(f"`{name}`" for name in KINDS[kind])
        lines += [f"### The {kind} worlds' tables ({files})", "", "```text"]
        lines += [f"{path}: {', '.join(types)}" for path, types in paths.items()]
        lines += ["```", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("make")
    c.add_argument("--inputs", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    c.add_argument("--cpus", required=True)
    c = commands.add_parser("scrub")
    c.add_argument("--runs", required=True, type=Path)
    c.add_argument("--out", required=True, type=Path)
    c = commands.add_parser("keys")
    c.add_argument("--folder", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "make":
        done = make(args.inputs, args.out, [int(x) for x in args.cpus.split(",")])
        print(json.dumps(dict(runs=len(done), failed=[d for d in done if d["exit"] != 0])))
        return 0 if all(d["exit"] == 0 for d in done) else 1
    if args.command == "scrub":
        listed = scrub(args.runs, args.out)
        count = sum(len(paths) for paths in listed.values())
        digest = {
            path.relative_to(args.out).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(args.out.rglob("*"))
            if path.is_file()
        }
        print(json.dumps(dict(paths=count, files=digest), indent=1))
        return 0
    for path, types in keys(args.folder).items():
        print(f"{path}: {', '.join(types)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
