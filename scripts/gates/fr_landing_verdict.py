"""FR's bitwise landing set's verdict (fr_landing_set.sh), read the way the earlier landing
verdicts were read (fr45/judged-20261117/landing-72409622/verdict.json; the FR HANDOFF's reading
rule). Read-only except OUT_JSON. Supersedes
/mnt/workspaces/Cells/d198-retire-20261117/tools/fr_landing_verdict.py, kept byte for byte since
recorded runs cite it. The logic is the same (rewrapped to the checkout's line length); only the
record's kind no longer names a branch.

  quick_20s  each of the queue's 9 compare-*.json (the 20 s quick parts against the earlier dry
             runs): identical, and its differences; FR-5's start may differ in `.extract_sha256`
             only
  windowed   FR-5's two arms over 10 s with the injury window at 2-6 s from START, against the
             rehearsal's windowed-F/before-ARM.json: the header and the records compared leaf by
             leaf with the judge's own helpers, run times apart
             (compartment_ph_judge.without_run_times, regulated_availability_judge.differences,
             imported from the gated SNAPSHOT); bitwise when neither differs; completed and steps
             from the record
  passed     every quick part identical (start: `.extract_sha256` only) and both arms bitwise and
             completed; anything else is listed under `unexpected`

Usage: python -I fr_landing_verdict.py SNAPSHOT LANDING_DIR BEFORE_DIR OUT_JSON
"""

import json
import sys
from pathlib import Path

snapshot, landing, before, out = (Path(a) for a in sys.argv[1:5])
if out.exists():
    sys.exit(f"refused: {out} exists")
sys.path[:0] = [str(snapshot / "src"), str(snapshot)]
from validation.tissue.compartment_ph_judge import without_run_times  # noqa: E402
from validation.tissue.regulated_availability_judge import differences  # noqa: E402

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
    allowed = name == "start" and found == [".extract_sha256"]
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
    new, old = json.loads(new_path.read_text()), json.loads(old_path.read_text())
    meta = differences(without_run_times({k: v for k, v in old.items() if k != "records"}),
                       without_run_times({k: v for k, v in new.items() if k != "records"}))
    records = differences(without_run_times(old["records"]), without_run_times(new["records"]))
    row = dict(meta_differences=list(meta)[:20], record_differences=list(records)[:20],
               bitwise=not meta and not records, completed=new["records"].get("completed"),
               steps=new["records"].get("steps"), before=str(old_path))
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
