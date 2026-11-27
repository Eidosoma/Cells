"""FR-45's exporter: the engine table (validation/fr45/spec/TABLE.md §1 to §4) from the driver's run records alone.

It forms no value: each run's entry is its record's, the record kept beside the table (`table/records/<run>.json`,
TABLE §4's `record`, with its sha256). A run with no record goes in `missing`.

Usage: python -B -m validation.fr45.exporter RECORDS_DIR TABLE_DIR RUN [RUN ...] [--invented TEXT]
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

KIND = "fr45 site-competition engine table, version 1"
PROTOCOL = "fr45-site-competition-v1"
UNITS = {"amount": "fmol", "volume": "pL", "concentration": "mM", "k_on": "per mM per s", "k_off": "per s",
         "time": "s", "heat": "pJ", "fraction": "1", "load": "per s", "copies": "copies"}  # fmt: skip
ENTRY = ("status", "world", "plant", "dt_s", "steps", "backend", "driver", "rows", "capacities", "free_sites",
         "events", "event_map", "step_report", "refusal", "checks", "operators", "inputs", "definition", "source")  # fmt: skip


def export(records, table, runs, *, invented=None):
    """Write TABLE/table.json and TABLE/SHA256SUMS from RECORDS/<run>.json; returns the table."""
    records, table = Path(records), Path(table)
    (table / "records").mkdir(parents=True, exist_ok=True)
    doc = {"INVENTED": invented} if invented else {}
    doc |= dict(kind=KIND, protocol=PROTOCOL, runs={}, missing=[], units=dict(UNITS))
    for run in runs:
        source = records / f"{run}.json"
        if not source.exists():
            doc["missing"].append(run)
            continue
        target = table / "records" / f"{run}.json"
        shutil.copyfile(source, target)
        record = json.loads(target.read_text())
        entry = {key: record[key] for key in ENTRY}
        entry["record"] = f"records/{run}.json"
        entry["record_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        doc["runs"][run] = entry
    text = json.dumps(doc, indent=1, allow_nan=False) + "\n"
    (table / "table.json").write_text(text)
    (table / "SHA256SUMS").write_text(f"{hashlib.sha256(text.encode()).hexdigest()}  table.json\n")
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("records")
    parser.add_argument("table")
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--invented")
    args = parser.parse_args(argv)
    doc = export(args.records, args.table, args.runs, invented=args.invented)
    print(f"{len(doc['runs'])} runs, {len(doc['missing'])} missing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
