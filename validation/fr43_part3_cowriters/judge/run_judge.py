"""The judge's passes over the engine tables (CRITERIA.md §3 to §8).

First pass:  python -I run_judge.py --inputs spec/inputs.json --references references/out --tables RUN/table
                 --operators OPS.json (--revision REV | --rehearsal) --out DIR [--lead-hashes F] [--sample-hashes F]
Retry pass:  the same, plus --retry-tables RUN/table-retry --retry-owed DIR/retry_owed.json
Format sample (structure only, TABLE.md §5):
             python -I run_judge.py --inputs ... --format-sample SAMPLE_DIR --out DIR [--sample-note F]

--operators is a JSON object, family id to the declared operator IDs in declared order (the strings note's; at the
rehearsal, the builder README's). --references with --invented reads reference_invented.json and
inputs_invented.json's draws. Writes record.json (and at the first pass retry_owed.json) to --out.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cowriter_judge import strictjson as sj  # noqa: E402
from cowriter_judge.api import (format_sample, judge_pass, read_retry_owed, references_through_c0,  # noqa: E402
                                retry_owed_file)
from cowriter_judge.registry import Inputs  # noqa: E402


def _dump(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--references", help="the references' out/ folder")
    parser.add_argument("--invented", action="store_true", help="read reference_invented.json")
    parser.add_argument("--draws", help="the draws table (default: beside --inputs, or draws_invented.json)")
    parser.add_argument("--tables")
    parser.add_argument("--retry-tables")
    parser.add_argument("--retry-owed")
    parser.add_argument("--operators")
    parser.add_argument("--revision", help="the registration tag's revision (source.engine_revision)")
    parser.add_argument("--rehearsal", action="store_true", help="the engine_revision check is not applied")
    parser.add_argument("--lead-hashes", help="JSON: table file name to the lead's recorded sha256")
    parser.add_argument("--sample-hashes", help="JSON: a list of the format sample's sha256 (refused in judgement)")
    parser.add_argument("--format-sample", help="read a format sample folder in structure-only mode")
    parser.add_argument("--sample-note", help="JSON: the lead's note of the format sample's sha256 by file")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    inputs = Inputs(args.inputs)
    if args.format_sample:
        note = sj.load_file(args.sample_note).data if args.sample_note else None
        report = format_sample(args.format_sample, inputs, note)
        _dump(os.path.join(args.out, "format_sample.json"), report)
        print(f"format sample: {'no fault' if report['passes'] else 'FAULT'}")
        for sub, rep in report["folders"].items():
            for dep in rep.get("departures", []):
                print(f"  {sub}: {dep}")
            print(f"  {sub}: entry kinds {rep.get('entry_kinds')}")
        return 0 if report["passes"] else 1
    if not (args.references and args.tables and args.operators) or not (args.revision or args.rehearsal):
        parser.error("--references, --tables, --operators and one of --revision or --rehearsal are needed")
    if args.invented:
        draws = args.draws or os.path.join(args.references, "draws_invented.json")
        refs, c0 = references_through_c0(inputs, {}, draws, os.path.join(args.references, "reference_invented.json"))
    else:
        draws = args.draws or os.path.join(os.path.dirname(os.path.abspath(args.inputs)), "draws.json")
        paths = {w: os.path.join(args.references, f"reference_{w}.json") for w in inputs.worlds}
        refs, c0 = references_through_c0(inputs, paths, draws)
    operators = sj.load_file(args.operators).data
    lead = sj.load_file(args.lead_hashes).data if args.lead_hashes else None
    sample = set(sj.load_file(args.sample_hashes).data) if args.sample_hashes else set()
    owed = read_retry_owed(args.retry_owed) if args.retry_owed else None
    record = judge_pass(inputs, refs, args.tables, operators, args.revision, args.rehearsal, lead, sample,
                        args.retry_tables, owed)
    record["c0"] = {name: {"refused": r["refused"]} for name, r in c0.items()}
    _dump(os.path.join(args.out, "record.json"), record)
    if owed is None:
        _dump(os.path.join(args.out, "retry_owed.json"), retry_owed_file(record))
    print(f"claim: {record['claim']} ({record['pass']} pass)")
    for world, arm in record["arms"].items():
        print(f"  {world}: {arm['verdict']}  families {arm['families']}")
        print(f"      plants {arm['plants']}")
    print(f"  retry owed: {record['retry_owed']['families'] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
