"""Summarize an FR-5 reading: the judge's verdict and each engine part's run, as text.

    python -m validation.compartment_ph_engine.summarize_reading_fr5 VERDICT_JSON
        [RESULTS_JSON ...]

VERDICT_JSON is the judge's verdict.json (validation/tissue/compartment_ph_judge.py: a dt study's
development reading or a judged run's verdict); each RESULTS_JSON is one unit's results.json from
the generator. The summary goes to stdout: the verdict and every criterion, each arm's derived
metrics, then one line per engine part (admission, steps, wall, compile and execution time, and
the execution's cost per step). The results are read in sorted path order, whatever order the
shell gives.

Moved into the checkout from the lane's run folder at the lead's ruling of 16 November 2026 (the
copy that ran, fr45/pipeline/summarize_reading_fr5.py with OUT/reading/verdict.json and
OUT/*/results.json fixed, stays there as a frozen run input). The text is unchanged; the paths are
now arguments. Standard library only.
"""

import json
import sys
from pathlib import Path


def short(value, n=160):
    return json.dumps(value, allow_nan=True)[:n]


def ms_per_step(record):
    """The execution's cost per step (ms): execute_seconds over the steps taken; None without
    either."""
    t = record.get("timings") or {}
    steps = record.get("steps") or 0
    return (1e3 * t["execute_seconds"] / steps) if steps and "execute_seconds" in t else None


def verdict_lines(v):
    out = [f"{v['kind']} {'passed' if v['passed'] else 'FAILED'}"]
    for c in v["criteria"]:
        mark = "ok " if c["passed"] else "NO "
        out.append(f"  {c['id']:34s} {'judged' if c.get('judged') else 'report'} {mark} "
                   f"{short(c.get('values'), 120)}")
    for arm, d in v["derived"].items():
        out.append(f"arm {arm}: budget {d.get('budget_fmol')} fmol; admission "
                   f"{short(d.get('admission'))}")
        for name, order in (d.get("orders") or {}).items():
            out.append(f"  order {name}: class {order.get('judged_class')} passes "
                       f"{order.get('passes')} differences {short(order.get('differences'), 90)} "
                       f"floors {short(order.get('floors'), 90)}")
        for key in ("state_error", "reference", "start", "envelope", "protons", "cargo", "bands",
                    "control"):
            out.append(f"  {key}: {short(d.get(key), 400)}")
        energy = d.get("energy") or {}
        out.append(f"  energy: over flows at declared {energy.get('over_flows_at_declared')}; "
                   f"ladder {short(energy.get('ladder'), 300)}")
        out.append(f"  claims: {short(d.get('claims'), 600)}")
    return out


def part_lines(results):
    out = []
    for name, r in results["parts"].items():
        if r.get("kind") != "engine":
            continue
        t = r.get("timings") or {}
        rate = ms_per_step(r)
        out.append(f"{name}: admitted {r['admitted']} completed {r['completed']} steps "
                   f"{r.get('steps') or 0} reason {r.get('refusal_reason')} wall "
                   f"{round(r.get('wall_s', 0))} s compile "
                   f"{round(t.get('compile_seconds', 0), 1)} s execute "
                   f"{round(t.get('execute_seconds', 0), 1)} s "
                   f"({None if rate is None else round(rate, 3)} ms per step) refusal "
                   f"{(r.get('refusal') or '')[:100]}")
    return out


def summary(verdict_path, results_paths):
    lines = verdict_lines(json.loads(Path(verdict_path).read_text()))
    for path in sorted(str(p) for p in results_paths):
        lines += part_lines(json.loads(Path(path).read_text()))
    return lines


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        raise SystemExit(__doc__)
    print("\n".join(summary(argv[0], argv[1:])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
