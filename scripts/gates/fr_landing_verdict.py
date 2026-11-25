"""FR's bitwise landing set's verdict (fr_landing_set.sh), read the way the earlier landing
verdicts were read (fr45/judged-20261117/landing-72409622/verdict.json; the FR HANDOFF's reading
rule). Read-only except OUT_JSON. Supersedes
/mnt/workspaces/Cells/d198-retire-20261117/tools/fr_landing_verdict.py, kept byte for byte since
recorded runs cite it. The logic is the same (rewrapped to the checkout's line length); the
record's kind no longer names a branch; and the planner's admission estimate is information (below).

  quick_20s  each of the queue's 9 compare-*.json (the 20 s quick parts against the earlier dry
             runs, renewed for D307 where their max_global_charge_bound_ratio fell:
             fr_landing_holder.sh's F4 and F5): identical, and its differences; FR-5's start may
             differ in `.extract_sha256` only
  windowed   FR-5's two arms over 10 s with the injury window at 2-6 s from START, against
             BEFORE_DIR/before-ARM.json (fr_landing_set.sh's BEFORE: the rehearsal's windowed-F,
             renewed for D307): the header and the records compared leaf by
             leaf with the judge's own helpers, run times apart
             (compartment_ph_judge.without_run_times, regulated_availability_judge.differences,
             imported from the gated SNAPSHOT); bitwise when neither differs; completed and steps
             from the record
  passed     every quick part identical (start: `.extract_sha256` only) and both arms bitwise and
             completed; anything else is listed under `unexpected`
  estimate   the planner's admission estimate, resources.estimated_working_bytes, is reported as
             information and not compared bit for bit, as run times are not: it sizes a run's
             admission and records nothing the run computed (the lead's ruling on the third
             review's finding 3, 19 November 2026, whose kind share changes it in FR-4's and
             FR-5's records). A quick part whose only other difference is allowed passes with
             its estimates reported; compare keeps 20 differences, so a full list excuses none

Usage: python -I fr_landing_verdict.py SNAPSHOT LANDING_DIR BEFORE_DIR OUT_JSON
"""

import json
import sys
from pathlib import Path

snapshot, landing, before, out = (Path(a) for a in sys.argv[1:5])
if out.exists():
    sys.exit(f"refused: {out} exists")
sys.path[:0] = [str(snapshot / "src"), str(snapshot)]
from validation import id_table  # noqa: E402
from validation.tissue.compartment_ph_judge import without_run_times  # noqa: E402
from validation.tissue.regulated_availability_judge import differences  # noqa: E402

ESTIMATE = "estimated_working_bytes"  # resources' admission estimate: information (docstring).


def is_estimate(path):
    return path.endswith(".resources." + ESTIMATE)


def without_estimate(value):
    """value with ESTIMATE dropped from every resources mapping, at any depth."""
    if isinstance(value, dict):
        return {k: without_estimate({e: x for e, x in v.items() if e != ESTIMATE}
                                    if k == "resources" and isinstance(v, dict) else v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [without_estimate(v) for v in value]
    return value


def estimates(value, path=""):
    """{path: value} of every resources mapping's ESTIMATE, for the report."""
    if isinstance(value, dict):
        held = value.get("resources")
        out = {f"{path}.resources.{ESTIMATE}": held[ESTIMATE]} if (
            isinstance(held, dict) and ESTIMATE in held) else {}
        for k, v in value.items():
            out |= estimates(v, f"{path}.{k}")
        return out
    if isinstance(value, list):
        out = {}
        for i, v in enumerate(value):
            out |= estimates(v, f"{path}[{i}]")
        return out
    return {}


def part_estimates(doc, name, side):
    """The part's estimates in compare's run `side` ("a" or "b"), or None where it is not read."""
    try:
        return estimates(json.loads(Path(doc[side]).read_text())["parts"][name])
    except (KeyError, OSError, TypeError, ValueError):
        return None


quick, unexpected = {}, {}
compares = sorted(landing.glob("compare-*.json"))
for path in compares:
    name = path.stem.removeprefix("compare-")
    doc = json.loads(path.read_text())
    parts = doc["parts"]
    found = sorted(
        {d for p in parts.values() if isinstance(p, dict) for d in p.get("differences", [])}
    )
    identical = all(isinstance(p, dict) and p.get("identical") for p in parts.values())
    quick[name] = dict(identical=identical, differences=found,
                       earlier=(doc.get("a_source") or {}).get("git_revision"),
                       this=(doc.get("b_source") or {}).get("git_revision"))
    rest = [d for d in found if not is_estimate(d)]
    if rest != found:  # The estimate differs: reported, not compared.
        quick[name]["estimate"] = dict(earlier=part_estimates(doc, name, "a"),
                                       this=part_estimates(doc, name, "b"))
    whole = all(isinstance(p, dict) for p in parts.values()) and 0 < len(found) < 20
    allowed = whole and rest in (([], [".extract_sha256"]) if name == "start" else ([],))
    if not identical and not allowed:
        unexpected["quick:" + name] = found or "not identical"
if len(compares) != 9:
    unexpected["quick_count"] = f"{len(compares)} compare files, 9 expected"
windowed = {}
for arm in ("T", "R"):
    new_path, old_path = landing / f"windowed-{arm}.json", before / f"before-{arm}.json"
    if not new_path.exists():
        unexpected["windowed:" + arm] = "no record"
        continue
    new, old = id_table.load(new_path), id_table.load(old_path)  # The baseline keeps its IDs.
    meta = differences(
        without_run_times(without_estimate({k: v for k, v in old.items() if k != "records"})),
        without_run_times(without_estimate({k: v for k, v in new.items() if k != "records"})))
    records = differences(without_run_times(without_estimate(old["records"])),
                          without_run_times(without_estimate(new["records"])))
    row = dict(meta_differences=list(meta)[:20], record_differences=list(records)[:20],
               bitwise=not meta and not records, completed=new["records"].get("completed"),
               steps=new["records"].get("steps"), before=str(old_path),
               estimate=dict(before=estimates(old), after=estimates(new)))
    windowed[arm] = row
    if not row["bitwise"] or row["completed"] is not True:
        unexpected["windowed:" + arm] = dict(meta=row["meta_differences"],
                                             records=row["record_differences"],
                                             completed=row["completed"])
doc = dict(
    kind="FR's bitwise landing set at " + (quick.get("start", {}).get("this") or "?")[:8]
    + " (lane B; development, not a verdict)",
    windowed=windowed,
    quick_20s=quick,
    unexpected=unexpected,
    passed=not unexpected,
)
out.write_text(json.dumps(doc, indent=1) + "\n")
print(json.dumps(dict(passed=doc["passed"], quick=len(quick),
                      windowed={a: r["bitwise"] for a, r in windowed.items()},
                      unexpected=unexpected)))
sys.exit(0 if doc["passed"] else 1)
