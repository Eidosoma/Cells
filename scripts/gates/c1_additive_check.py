"""G1's record c1 against a renewal of it: additive, and each new final state checked (D410).

An additive renewal re-saves G1's worlds (validation/results_baseline.py, merged as gate_steps.py
g1-merge merges them) where the tool or a world gained arrays and none may change: D307's renewal
(global-charge-bound-20261122/tools/g1_renewal.py's checks), the side saves of 26 November (FR-43's
counts, FR-52's cohorts) and D410's final states. It reads saved outputs only. Its rules:

A. Additive, world by world (every world of NEW; with --all, NEW holds every world OLD holds):
   - every array OLD holds is in NEW with the same dtype, shape and bytes, and NEW's manifest digest
     of it is OLD's; none is missing, and NEW's digests name exactly its arrays;
   - the refusal is the same (its type, and its message read through TABLE);
   - the definition is the same, OLD's read through TABLE (a save --from BASELINE --map TABLE
     writes the translated one), and channel_activity's static is the same;
   - the added keys are counted by prefix, and an added key that is not a final state fails.
   The record's other differences are listed, not judged: seconds, a refusal's traceback, and
   channel_activity's masks (null in every record saved before D410's fix).
B. Each added final state is its own run's last history row, bit for bit (dtype, shape, bytes):
   - a world's first window: final.state.F against history.F[-1];
   - run-paths: run:final.state.F against run:history.F[-1], run_batch:worldW.final.state.F against
     run_batch:worldW.history.F[-1], and run_windowed's (it saves no history) against runner.run's;
   - and final.time against the last time, a first window's step index against the record's steps.
C. Run-paths, the paths against each other: run, run_windowed, run_batch's two worlds and
   run_batch_windowed's two worlds hold the same final state bit for bit, and run_vector_windowed's
   two worlds the same as each other. The vector path's differences from the scalar paths are
   reported, not judged (c1 holds them already: about 8e-11 of the largest magnitude at most).
Exceptions are listed by world. No rule takes a tolerance.

Usage: python -I -B scripts/gates/c1_additive_check.py OLD NEW OUT_JSON [--map TABLE] [--all]
  TABLE (a renamed_ids.py or a JSON {old: new}) is read by this tree's validation/id_table.py.
Exit 0 when A, B and C hold, 1 otherwise.
"""

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SCALAR_PATHS = ("run_windowed:final.state", "run_batch:world1.final.state",
                "run_batch:world2.final.state", "run_batch_windowed:world1.final.state",
                "run_batch_windowed:world2.final.state")


def bits(a):
    return (str(a.dtype), a.shape, np.ascontiguousarray(a).tobytes())


def stem(name):
    return name.replace("/", "__")


def reader(table_path):
    """What reads a record through TABLE (this tree's id_table); unchanged without one."""
    if table_path is None:
        return lambda value: value
    spec = importlib.util.spec_from_file_location("id_table", ROOT / "validation" / "id_table.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    table = module.read_table(table_path)
    return lambda value: module.translate(value, table)


def prefix_of(key):
    """An added key's group: its path and the part up to final.state, else its first part."""
    path, _, rest = key.rpartition(":")
    if rest.startswith("final.state."):
        head = "final.state"
    elif ".final.state." in rest:
        head = rest.split(".final.state.")[0] + ".final.state"
    else:
        head = rest.split(".")[0]
    return f"{path}:{head}" if path else head


def additive(world, old, new, digests, through):
    """Rule A for one world: (row, NEW's arrays, NEW's record)."""
    set_name, name = world.split("/", 1)
    ro, rn = (json.loads((d / set_name / f"{stem(name)}.json").read_text()) for d in (old, new))
    problems = []
    fo, fn = ro.get("refusal"), rn.get("refusal")
    if bool(fo) != bool(fn) or (fo and (fo["type"], through(fo["message"])) != (fn["type"],
                                                                                  fn["message"])):
        problems.append(dict(refusal=[fo and fo["type"], fn and fn["type"]]))
    if through(ro.get("definition")) != rn.get("definition"):
        problems.append("the definition differs, read through the table")
    ao, an = ro.get("channel_activity") or {}, rn.get("channel_activity") or {}
    if ao.get("static") != an.get("static"):
        problems.append(dict(channel_activity_static=[ao.get("static"), an.get("static")]))
    x, y = (np.load(d / set_name / f"{stem(name)}.npz") for d in (old, new))
    missing = sorted(set(x.files) - set(y.files))
    differing = sorted(k for k in x.files if k in y.files and bits(x[k]) != bits(y[k]))
    if missing or differing:
        problems.append(dict(missing=missing[:20], differing=differing[:20],
                             counts=[len(missing), len(differing)]))
    old_d, new_d = digests
    wrong = sorted(k for k in x.files if old_d.get(k) != new_d.get(k))
    if wrong or set(new_d) != set(y.files):
        problems.append(dict(digests_not_old=wrong[:20], count=len(wrong),
                             digests_name_the_arrays=set(new_d) == set(y.files)))
    added = sorted(set(y.files) - set(x.files))
    not_final = [k for k in added if "final.state." not in k]
    if not_final:
        problems.append(dict(added_not_final_state=not_final[:20], count=len(not_final)))
    row = dict(
        old_arrays=len(x.files), new_arrays=len(y.files), added=len(added),
        added_by_prefix=dict(sorted(Counter(prefix_of(k) for k in added).items())),
        record_differs_in=sorted(k for k in set(ro) | set(rn)
                                 if k not in ("definition", "seconds") and ro.get(k) != rn.get(k)),
        channel_activity_masks=[an.get(k) is not None for k in ("initial", "final")],
        problems=problems,
    )
    return row, y, rn


def final_rows(world, y, record):
    """Rule B for one world: (problems, final states checked)."""
    problems, checked = [], 0
    if record.get("refusal"):
        return problems, checked
    runs = [("", "")]
    if world.startswith("run-paths/"):
        runs = [("run:", "run:"), ("run_windowed:", "run:")] + [
            (f"run_batch:world{w}.", f"run_batch:world{w}.") for w in (1, 2)]
    for final, own in runs:
        for key in sorted(k for k in y.files if k.startswith(f"{final}final.state.")):
            history = f"{own}history.{key[len(f'{final}final.state.'):]}"
            checked += 1
            if history not in y.files:
                problems.append(dict(key=key, problem=f"no {history}"))
            elif bits(y[key]) != bits(y[history][-1]):
                problems.append(dict(key=key, problem=f"not {history}[-1]"))
        times, end, step = f"{own}times", f"{final}final.time", f"{final}final.step_index"
        if not {times, end, step} <= set(y.files):
            problems.append(dict(key=end, problem=f"{times}, {end} or {step} missing"))
            continue
        if bits(y[end]) != bits(np.asarray(y[times][-1])):
            problems.append(dict(key=end, problem=f"not {times}[-1]"))
        if not own and int(y[step]) != record.get("steps"):
            problems.append(dict(key=step, problem="not the record's steps"))
    return problems, checked


def paths_agree(y):
    """Rule C for one run-paths world: (problems, the vector path's differences by field)."""
    head = "run:final.state."
    fields = sorted(k[len(head):] for k in y.files if k.startswith(head))
    if not fields:
        return [dict(problem="no run:final.state")], {}
    problems, vector = [], {}
    for f in fields:
        ref = y[f"run:final.state.{f}"]
        for path in SCALAR_PATHS:
            key = f"{path}.{f}"
            if key not in y.files or bits(y[key]) != bits(ref):
                problems.append(dict(key=key, problem="not run:final.state's"))
        v1, v2 = (f"run_vector_windowed:world{w}.final.state.{f}" for w in (1, 2))
        if v1 not in y.files or v2 not in y.files or bits(y[v1]) != bits(y[v2]):
            problems.append(dict(key=v2, problem=f"not {v1}"))
        elif bits(y[v1]) != bits(ref):
            a, b = y[v1].astype(float), ref.astype(float)
            d, scale = (float(np.max(np.abs(v), initial=0.0)) for v in (a - b, b))
            vector[f] = dict(max_abs=d, relative_to_largest=d / scale if scale else None,
                             elements=int(np.sum(a != b)), of=int(b.size))
    return problems, vector


def check(old, new, through, all_worlds=False):
    """The report of OLD against NEW: per world, and a summary whose rules all hold or not."""
    mo = json.loads((old / "manifest.json").read_text())["worlds"]
    mn = json.loads((new / "manifest.json").read_text())["worlds"]
    top = []
    if set(mn) - set(mo):
        top.append(dict(problem="worlds OLD does not hold", worlds=sorted(set(mn) - set(mo))))
    if all_worlds and set(mo) - set(mn):
        top.append(dict(problem="worlds NEW does not hold", worlds=sorted(set(mo) - set(mn))))
    rows, vector = {}, {}
    for world in sorted(set(mn) & set(mo)):
        digests = (mo[world].get("digests", {}), mn[world].get("digests", {}))
        row, y, record = additive(world, old, new, digests, through)
        row["final_rows"], row["final_states_checked"] = final_rows(world, y, record)
        if world.startswith("run-paths/") and not record.get("refusal"):
            row["paths"], vector[world] = paths_agree(y)
        rows[world] = row
    exceptions = dict(
        additive={w: r["problems"] for w, r in rows.items() if r["problems"]},
        final_rows={w: r["final_rows"] for w, r in rows.items() if r["final_rows"]},
        paths={w: r["paths"] for w, r in rows.items() if r.get("paths")},
        top=top,
    )
    summary = dict(
        old=str(old), new=str(new), worlds=len(rows),
        additive=not top and not exceptions["additive"],
        final_states_are_last_rows=not exceptions["final_rows"],
        paths_agree=not exceptions["paths"],
        old_arrays=sum(r["old_arrays"] for r in rows.values()),
        new_arrays=sum(r["new_arrays"] for r in rows.values()),
        added=sum(r["added"] for r in rows.values()),
        final_states_checked=sum(r["final_states_checked"] for r in rows.values()),
        added_by_prefix=dict(sorted(sum((Counter(r["added_by_prefix"]) for r in rows.values()),
                                        Counter()).items())),
        records_with_masks=sum(all(r["channel_activity_masks"]) for r in rows.values()),
        exceptions=exceptions,
        vector_path_differences=vector,
    )
    return dict(summary=summary, rows=rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("old", type=Path)
    p.add_argument("new", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--map", dest="table", type=Path, help="renamed IDs' table")
    p.add_argument("--all", action="store_true", help="NEW must hold every world OLD holds")
    a = p.parse_args(argv)
    if a.out.exists():
        sys.exit(f"Refused: {a.out} exists")
    report = check(a.old, a.new, reader(a.table), a.all)
    report["summary"]["table"] = str(a.table) if a.table else None
    a.out.write_text(json.dumps(report, indent=1, default=str) + "\n")
    s = report["summary"]
    ok = s["additive"] and s["final_states_are_last_rows"] and s["paths_agree"]
    print(f"{'additive' if ok else 'NOT ADDITIVE'}: {s['worlds']} worlds, {s['old_arrays']} arrays "
          f"of OLD equal, {s['added']} added, {s['final_states_checked']} final states checked; "
          f"exceptions in {sum(len(v) for v in s['exceptions'].values())} entries")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
