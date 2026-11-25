"""The legacy definitions through the frozen snapshot's own parser, with no run.

    PYTHONPATH=SNAPSHOT/src:SNAPSHOT parse_check.py ORIGIN

For every definition of a job list: that it parses, the accepted steps of its clock (EventGrid), the
events that the clock snaps and those it splits, whether the whole-run window is admitted, and for
an assembly world what `validate` says (ticks, worlds, working bytes). A world whose steps are not
its grid's, or that the parser refuses, is printed and the check exits 1.
"""

import contextlib
import io
import json
import sys
from pathlib import Path


def ionic(definition):
    from cells.definitions.specs import parse_spec
    from cells.execution.grid import EventGrid
    from cells.execution.windows import WindowPolicy, plan_windows

    spec = parse_spec(definition)
    grid = EventGrid(spec)
    steps = len(grid) - 1
    plan = "admitted"
    try:
        plan_windows(spec, WindowPolicy(min(256, steps), "checkpoints"))
    except Exception as error:
        plan = f"refused: {error}"[:120]
    return dict(
        steps=steps,
        snapped=list(grid.snapped),
        extras=list(grid.extras),
        windows=plan,
        end=spec.experiment.end_time,
    )


def assembly(command, path):
    from cells.__main__ import main

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([command, "validate", str(path)])
    if code:
        raise RuntimeError(err.getvalue()[:300])
    value = json.loads(out.getvalue())
    return {k: value[k] for k in ("ticks", "worlds", "working_bytes", "definition_sha256")}


def main(origin):
    origin, bad = Path(origin), 0
    for job in json.loads((origin / "jobs-science.json").read_text()):
        path = origin / job["definition"]
        data = json.loads(path.read_text())
        try:
            if job["kind"] == "ionic":
                row = ionic(data["definition"])
                note = ""
                if row["extras"]:
                    note = f" SPLITS {row['extras']}"
                if row["snapped"]:
                    note += f" snaps {row['snapped']}"
                print(job["job"], row["steps"], "steps", row["windows"], note)
            else:
                row = assembly(job["command"], path)
                print(
                    job["job"], row["ticks"], "ticks", row["worlds"], "worlds", row["working_bytes"]
                )
                if row["ticks"] != job["ticks"]:
                    bad += 1
                    print("   TICKS", row["ticks"], job["ticks"])
        except Exception as error:  # A refusal is a finding.
            bad += 1
            print(job["job"], "REFUSED", type(error).__name__, str(error)[:300])
    print("refusals or departures:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
