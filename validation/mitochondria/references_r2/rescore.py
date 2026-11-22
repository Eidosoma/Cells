"""Re-score a run of record from its saved states, integrating nothing again.

Usage (from a frozen snapshot of the checkout):
    python -m validation.mitochondria.references_r2.rescore RUN_DIR --out RESCORE.json

It rebuilds every output record of the run's delivered integration and of its trace-check
integration from RUN_DIR/full.npz, replaying each world's schedule and output grid. It then
re-evaluates the readouts under the committed declaration (its scoring window and bands) and
recomputes the trace check: at every scored output time, at plateau ends, and for the focus
classes. With the declaration's scoring unchanged it reproduces the run's own trace check, and
it says whether it does.

It also reports the O2 window check: the O2 flux where the matrix O2 crosses the window's floor,
against 0.1% of the state-3 flux. That is erratum 2's stated reason for the window. It is
log-linear interpolation between the two saved outputs around the crossing.
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from . import constants, model, protocol, run

DELIVERED = "Radau_1e-11"


def rebuild(world, name, t, Y):
    """The run's records for world ``name``, from its saved times and states."""
    out = world.declaration["protocol"]["output"]
    records = []
    k = 0
    for seg, branch, t0, t1, kwargs in protocol.schedule(world, name):
        ctl = model.Controls(world, **kwargs)
        grid = protocol.output_grid(t0, t1, out)
        n = len(grid)
        if not np.allclose(t[k:k + n], grid, rtol=0.0, atol=1e-9):
            raise ValueError("saved times do not match the schedule for world %s, %s" % (name, seg))
        for j in range(n):
            side = "start" if j == 0 else ("end" if j == n - 1 else "inside")
            records.append(dict(segment=seg, branch=branch, t=float(grid[j]), side=side,
                                controls=ctl.describe(), y=Y[k + j]))
        k += n
    if k != len(t):
        raise ValueError("world %s holds %d saved records, its schedule %d" % (name, len(t), k))
    rows, ref = protocol.evaluate_records(world, {"records": records})
    return {"rows": rows, "ref": ref, "result": {"records": records}}


def o2_window_check(world, rows, state3_flux):
    """The O2 flux where O2_N crosses the window's floor, against 0.1% of the state-3 flux."""
    window = world.declaration["scoring"]["excluded_window"]
    floor = window["below_M"]
    t = np.array([r["t"] for r in rows])
    o2 = np.array([r["readouts"]["O2_N"] for r in rows])
    flux = np.array([r["readouts"]["O2_flux"] for r in rows])
    i = int(np.argmax(o2 < floor))
    if not o2[i] < floor:
        return None
    a, b = math.log(o2[i - 1]), math.log(o2[i])
    w = (a - math.log(floor)) / (a - b)
    f_cross = math.exp(math.log(flux[i - 1]) + w * (math.log(flux[i]) - math.log(flux[i - 1])))
    below = np.nonzero((t > t[i - 1]) & (flux < 1e-3 * state3_flux))[0]
    return {
        "window_floor_M": floor,
        "crossing_s": float(t[i - 1] + w * (t[i] - t[i - 1])),
        "O2_flux_at_floor": f_cross,
        "state3_O2_flux": state3_flux,
        "fraction_of_state3": f_cross / state3_flux,
        "below_0p1_percent_of_state3": bool(f_cross < 1e-3 * state3_flux),
        "first_output_below_0p1_percent": None if not len(below) else {
            "t": float(t[below[0]]), "O2_N": float(o2[below[0]]),
            "O2_N_over_P50": float(o2[below[0]]) / 0.373e-6},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    run_dir = Path(a.run_dir)
    interface = json.loads((run_dir / "interface.json").read_text())
    z = np.load(run_dir / "full.npz")
    decl = constants.load_declaration()
    world = model.World(decl)
    small = interface["trace_check"]["traces_M"]
    world_small = model.World(decl, overrides=small)
    delivered, small_runs = {}, {}
    for name in run.WORLDS:
        delivered[name] = rebuild(world, name, z["%s_%s_t" % (DELIVERED, name)],
                                  z["%s_%s_y" % (DELIVERED, name)])
        small_runs[name] = rebuild(world_small, name, z["small_traces_%s_t" % name],
                                   z["small_traces_%s_y" % name])
    bands = decl["bands"]
    trace, worst = run.compare_runs(world, delivered, small_runs, bands)
    ends, worst_ends = run.compare_runs(world, delivered, small_runs, bands,
                                        where=lambda n, r: r["side"] == "end")
    focus = {
        "a_inhibitor_branch": run.compare_runs(
            world, {"a": delivered["a"]}, {"a": small_runs["a"]}, bands,
            where=lambda n, r: r["branch"] == "inhibitor")[0].get("a"),
        "b_first_2_s": run.compare_runs(
            world, {"b": delivered["b"]}, {"b": small_runs["b"]}, bands,
            where=lambda n, r: r["t"] <= 2.0)[0].get("b"),
    }
    state3 = interface["worlds"]["a"]["plateaus"]["state3"]["readouts"]["O2_flux"]["value"]
    old = interface["trace_check"]
    result = {
        "schema": "cells.mito_r2_rescore@1",
        "run": run_dir.name,
        "run_revision": interface["provenance"]["git_revision"],
        "run_interface_sha256": hashlib.sha256(
            (run_dir / "interface.json").read_bytes()).hexdigest(),
        "documents": decl["documents"],
        "scoring": decl["scoring"],
        "bands": bands,
        "trace_check": {"traces_M": small, "worst_over_band": worst,
                        "passes": bool(worst < 0.1), "per_world": trace,
                        "at_plateau_ends": {"worst_over_band": worst_ends,
                                            "passes": bool(worst_ends < 0.1),
                                            "per_world": ends},
                        "focus": focus},
        "reproduces_run": {
            "worst_over_band": [old["worst_over_band"], worst],
            "at_plateau_ends": [old["at_plateau_ends"]["worst_over_band"], worst_ends],
            "same": bool(old["worst_over_band"] == worst
                         and old["at_plateau_ends"]["worst_over_band"] == worst_ends),
        },
        "o2_window_check": o2_window_check(world, delivered["d"]["rows"], state3),
    }
    Path(a.out).write_text(json.dumps(result, indent=1, allow_nan=False) + "\n")
    print(json.dumps({"worst_over_band": worst, "at_plateau_ends": worst_ends,
                      "reproduces_run": result["reproduces_run"]["same"],
                      "o2_window_check": result["o2_window_check"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
