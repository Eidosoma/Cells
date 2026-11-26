"""C0 on the references (CRITERIA.md §4.2): `python -I run_c0.py --spec SPEC --references OUT --out DIR`.

Reads the spec folder and the references' `out/` only. Writes `c0_result.json` to --out and prints a summary.
--hashes names a JSON file of the lead's recorded sha256 by file name (the protocol's hashes), when one exists.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cowriter_judge import strictjson as sj  # noqa: E402
from cowriter_judge.c0 import run_c0  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--references", required=True, help="the references' out/ folder")
    parser.add_argument("--out", required=True)
    parser.add_argument("--hashes", default=None)
    args = parser.parse_args(argv)
    hashes = sj.load_file(args.hashes).data if args.hashes else None
    result = run_c0(args.spec, args.references, hashes)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "c0_result.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")
    verdict = "no fault" if result["passes"] else "FAULT"
    if result["passes"] and not result["hashes_compared"]:
        verdict += " (the protocol's hashes not compared: no record supplied)"
    print(f"C0: {verdict}  ({path})")
    for name, refused in sorted(result["refused"].items()):
        print(f"  {name}: {'refused' if refused else 'no fault'}")
    for block in [result["invented"], *result["files"].values()]:
        for fault in block["file_faults"]:
            print(f"  {block['file']}: {fault}")
        for world, wr in block["worlds"].items():
            for fault in wr["faults"]:
                print(f"  {block['file']} {world}: {fault['code']}: {fault['where']}: {fault['message']}")
            for flag in wr["flags"]:
                print(f"  {block['file']} {world}: flag {flag['code']}: {flag['where']}: {flag['message']}")
            for dis in wr["disagreements"]:
                print(f"  {block['file']} {world}: differs: {dis['what']}: published {dis['published']!r}, "
                      f"recomputed {dis['recomputed']!r}")
            print(f"  {block['file']} {world}: {len(wr['faults'])} faults, {wr['comparisons']} recomputed values")
    for fault in result["invented_rules"]["faults"]:
        print(f"  invented rules: {fault}")
    print(f"  invented numbers compared: {result['invented_rules']['numbers_compared']}")
    print(f"  hashes: {result['hashes'].get('note') or result['hashes']['faults']}")
    return 0 if result["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
