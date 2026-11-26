"""The rehearsal's tools (CRITERIA.md §10), on the builder's honest invented tables.

Plant every fault of CRITERIA.md §4, one copy each, with what §4 says the judge must do:
    python -I run_rehearsal.py plant --inputs INV --references OUT --tables RUN/table [--retry-tables RUN/table-retry]
        --out DIR
Judge every planted copy, and the honest tables, and compare each record with what §4 says:
    python -I run_rehearsal.py check --inputs INV --references OUT --tables RUN/table [--retry-tables ...]
        --operators OPS.json --planted DIR --out DIR
Make the copy whose coarsest rung is perturbed, so that a family owes the retry (SPEC.md §8), and verify it:
    python -I run_rehearsal.py perturb --inputs INV --references OUT --tables RUN/table [--retry-tables ...]
        --operators OPS.json [--family F] [--factor 16] --out DIR

--references is the references' out/ folder holding reference_invented.json and draws_invented.json. Every judge pass
is the rehearsal's (no engine_revision check). Exit 0 where everything is as §4 and §7 say, else 1.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cowriter_judge import strictjson as sj  # noqa: E402
from cowriter_judge.api import judge_pass, references_through_c0, retry_owed_file  # noqa: E402
from cowriter_judge.registry import Inputs  # noqa: E402
from cowriter_judge.rehearsal import catalog, check, perturb_coarsest_rung, write_planted, write_tables  # noqa: E402


def _load_tables(folder: str | None) -> dict:
    if not folder:
        return {}
    out = {}
    for name in sorted(os.listdir(folder)):
        if name.startswith("table_") and name.endswith(".json"):
            out[name] = json.loads(open(os.path.join(folder, name), encoding="utf-8").read())
    return out


def _dump(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1, sort_keys=True, default=str)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["plant", "check", "perturb"])
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--references", required=True)
    parser.add_argument("--tables", required=True)
    parser.add_argument("--retry-tables")
    parser.add_argument("--operators")
    parser.add_argument("--planted")
    parser.add_argument("--family")
    parser.add_argument("--factor", type=float, default=16.0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    inputs = Inputs(args.inputs)
    refs, c0 = references_through_c0(inputs, {}, os.path.join(args.references, "draws_invented.json"),
                                     os.path.join(args.references, "reference_invented.json"))
    if not all(refs.values()) or any(w.get("findings") for r in c0.values() for w in r["worlds"].values()):
        print("C0 refuses or has findings on the invented reference: nothing is planted or judged")
        return 1
    tables = _load_tables(args.tables)
    retry = _load_tables(args.retry_tables)

    def k_c(world: str, copy_: int) -> int:
        return refs[world].copies[copy_].K

    if args.action == "plant":
        planted = catalog(inputs, tables, retry, k_c)
        manifest = []
        for item in planted:
            folder = os.path.join(args.out, item.id.replace(" ", "_").replace("'", "").replace(":", ""))
            write_planted(item, folder)
            manifest.append({**item.manifest(), "folder": os.path.basename(folder)})
        _dump(os.path.join(args.out, "manifest.json"), {"faults": manifest})
        print(f"planted {len(planted)} faults of CRITERIA.md §4 under {args.out}")
        return 0
    operators = sj.load_file(args.operators).data
    if args.action == "check":
        honest = judge_pass(inputs, refs, args.tables, operators, None, True)
        manifest = json.load(open(os.path.join(args.planted, "manifest.json")))["faults"]
        results = []
        for item in manifest:
            folder = os.path.join(args.planted, item["folder"])
            driver = json.load(open(os.path.join(folder, "driver.json")))
            retry_dir = os.path.join(folder, "table-retry") if os.path.isdir(os.path.join(folder, "table-retry")) \
                else None
            record = judge_pass(inputs, refs, os.path.join(folder, "table"), operators, None, True,
                                driver["lead_record"], set(driver["sample_hashes"]), retry_dir)
            misses = check(record, honest, item["expect"])
            results.append({"id": item["id"], "lines": item["lines"], "flagged_as_section_4_says": not misses,
                            "misses": misses})
            print(f"  {'ok ' if not misses else 'MISS'} {item['id']}" + (f": {misses}" if misses else ""))
        summary = {"honest_claim": honest["claim"], "faults": results,
                   "all_flagged": all(r["flagged_as_section_4_says"] for r in results)}
        _dump(os.path.join(args.out, "rehearsal_faults.json"), summary)
        print(f"honest claim: {honest['claim']}; {sum(r['flagged_as_section_4_says'] for r in results)} of "
              f"{len(results)} faults flagged as CRITERIA.md §4 says")
        return 0 if summary["all_flagged"] else 1
    perturbed, info = perturb_coarsest_rung(inputs, refs, tables, args.family, args.factor)
    write_tables(os.path.join(args.out, "table"), perturbed)
    first = judge_pass(inputs, refs, os.path.join(args.out, "table"), operators, None, True)
    owed = retry_owed_file(first)
    info["first_pass_retry_owed"] = owed
    ok = info["family"] in owed["families"] and sorted(info["retry_runs"]) == sorted(
        r for r in owed["runs"] if r.startswith(info["family"] + " "))
    if args.retry_tables:
        second = judge_pass(inputs, refs, os.path.join(args.out, "table"), operators, None, True,
                            retry_dir=args.retry_tables, retry_owed=owed)
        entry = [e for e in second["entries"] if e["family"] == info["family"] and e["entry"] == "S t_events"][0]
        info["retry_pass"] = {"outcome": entry["outcome"], "q": entry["q"], "rungs": entry["rungs"],
                              "claim": second["claim"]}
    _dump(os.path.join(args.out, "perturbation.json"), info)
    _dump(os.path.join(args.out, "retry_owed.json"), owed)
    print(f"perturbed {info['family']} at h_1 = {info['rung_s']!r} by {info['shift_s']!r} s (factor {info['factor']}): "
          f"q {info['honest_q']!r} -> {info['perturbed_q']!r}; retry owed: {owed['families']}"
          + (f"; after the retry: {info['retry_pass']}" if "retry_pass" in info else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
