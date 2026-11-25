"""The judge's CLI.

    python -m validation.gene_regulation.fr38_v2.judge c0 --references DIR [--out FILE]
    python -m validation.gene_regulation.fr38_v2.judge sample --sample DIR --out FILE
    python -m validation.gene_regulation.fr38_v2.judge judge --engine DIR --references DIR \
        --out FILE

`c0` is the reader's first read alone: `reference_invented.json`, then each reference file.
`sample` is the reader's check on the registered format sample (amendment 5, §5): structure only.
`judge` adds the engine's export, the folder holding amendment 4, §8's `table/` (and
`table-retry/`), and writes the verdict per family, arm and criterion. DIR for the references is
their folder or its `out/`. The exit status is 0 when every read file is accepted (c0), the sample
check passes (sample) or a verdict is written (judge), else 1.
"""

import argparse
import json
import sys

from . import judge, sample


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m validation.gene_regulation.fr38_v2.judge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c0 = sub.add_parser("c0", help="read the reference files (invented first) and report C0")
    c0.add_argument("--references", required=True)
    c0.add_argument("--out")
    sm = sub.add_parser("sample", help="check the registered format sample's structure")
    sm.add_argument("--sample", required=True)
    sm.add_argument("--out", required=True)
    jd = sub.add_parser("judge", help="judge the engine's export against the references")
    jd.add_argument("--engine", required=True)
    jd.add_argument("--references", required=True)
    jd.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "c0":
        verdict = judge.judge(args.references, None)
        summary = {
            f: {"accepted": r["accepted"], "faults": r["faults"][:20]}
            for f, r in verdict["c0"]["references"].items()
        }
        print(json.dumps(summary, indent=1, ensure_ascii=False))
        if args.out:
            judge.write_verdict(verdict, args.out)
        return 0 if all(r["accepted"] for r in verdict["c0"]["references"].values()) else 1
    if args.cmd == "sample":
        report = {"provenance": judge.provenance(), **sample.check(args.sample)}
        judge.write_verdict(report, args.out)
        brief = ("passes", "stopped", "shapes_equal_readme", "coverage", "refused_entry",
                 "structural_faults", "unexpected_keys")  # fmt: skip
        print(json.dumps({k: report.get(k) for k in brief}, indent=1, ensure_ascii=False))
        return 0 if report["passes"] else 1
    verdict = judge.judge(args.references, args.engine)
    judge.write_verdict(verdict, args.out)
    print(
        json.dumps(
            verdict.get("comparison", {"refused": verdict.get("refused")}),
            indent=1,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
