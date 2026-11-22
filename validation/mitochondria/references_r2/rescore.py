"""Re-score a run of record from its saved states, integrating nothing of it again.

Usage (from a frozen snapshot of the checkout):
    python -m validation.mitochondria.references_r2.rescore RUN_DIR --out RESCORE.json [--plants]

**The trace check.**
- It rebuilds every output record of the run's delivered integration and its trace-check
  integration from RUN_DIR/full.npz, replaying each world's schedule and output grid.
- It checks the rebuilt readouts against those the run stored in its interface.json.
- It then re-scores under the committed declaration's scoring (erratum 3: W3(d)'s window on the
  O2 flux, and the anoxic collapse on transient bands, each fixed from this reference alone):
  at every scored output, at plateau ends, and for the focus classes.

**The plants (``--plants``).**
- The run saved its plants' scores, not their trajectories.
- Erratum 3 changes only world (d)'s scoring, so each plant's world (d) is recomputed from its
  own anchored start, with the run's code and tolerance.
- The recomputation must reproduce the run's saved plateau-end scores for world (d) within 1e-6
  of a band. The run computed (d) after (a)-(c) in one process, so its closure's Newton started
  elsewhere; agreement is to the integration's tolerance, not bit for bit.
- It is then scored under erratum 3, collapse rows apart. The other worlds' scores stand as the
  run saved them.

**The O2 window check.** The O2 flux where the matrix O2 crosses erratum 2's superseded threshold,
against 0.1% of the state-3 flux; log-linear between the two saved outputs around the crossing.
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
    """The O2 flux where O2_N crosses erratum 2's superseded threshold, against 0.1% of state 3."""
    floor = world.declaration["scoring"]["superseded"]["excluded_window_erratum_2"]["below_M"]
    t = np.array([r["t"] for r in rows])
    o2 = np.array([r["readouts"]["O2_N"] for r in rows])
    flux = np.array([r["readouts"]["O2_flux"] for r in rows])
    i = int(np.argmax(o2 < floor))
    if not o2[i] < floor:
        return None
    a, b = math.log(o2[i - 1]), math.log(o2[i])
    w = (a - math.log(floor)) / (a - b)
    f_cross = math.exp(math.log(flux[i - 1]) + w * (math.log(flux[i]) - math.log(flux[i - 1])))
    return {
        "superseded_threshold_M": floor,
        "crossing_s": float(t[i - 1] + w * (t[i] - t[i - 1])),
        "O2_flux_at_threshold": f_cross,
        "state3_O2_flux": state3_flux,
        "fraction_of_state3": f_cross / state3_flux,
    }


def plants_world_d(world_decl, interface, scoring, reference_d, log):
    """Each plant's world (d), recomputed and checked against the run, then scored (erratum 3)."""
    out = {}
    for pname, plant in world_decl.declaration["plants"].items():
        if pname == "source":
            continue
        saved = interface["plants"][pname]
        pworld = model.World(world_decl.declaration, overrides=plant["overrides"])
        rule = world_decl.declaration["anchor"]["I_NP_rule"]["value"]
        pstart = run.settle_and_start(pworld, rule, log)["start"]
        prun = run.run_all(pworld, pstart, run.DELIVERED_RTOL, "Radau", ("d",), log)
        base = {"d": reference_d}
        ends, _ = run.compare_runs(world_decl, base, prun, scoring,
                                   where=lambda n, r: r["side"] == "end")
        # The run computed world (d) after (a)-(c) in one process. The closure's Newton starts at
        # its last root, so the two agree to rounding and, through step selection, to the
        # integration's own tolerance, not bit for bit.
        diff = max(abs(ends["d"][k]["worst_over_band"]
                       - saved["at_plateau_ends"]["per_world"]["d"][k]["worst_over_band"])
                   for k in protocol.JUDGED)
        same = diff <= 1e-6
        per_d, worst_d = run.compare_runs(world_decl, base, prun, scoring)
        coll, worst_coll = run.compare_runs(world_decl, base, prun, scoring,
                                            where=lambda n, r: bool(scoring.in_collapse(n, [r])[0]))
        others = max(v["worst_over_band"] for w, e in saved["per_world"].items() if w != "d"
                     for v in e.values())
        worst = max(worst_d, others)
        out[pname] = {
            "what": plant["what"],
            "reproduces_saved_plateau_ends_d": bool(same),
            "saved_plateau_ends_d_max_difference_bands": diff,
            "world_d": per_d["d"], "world_d_worst_over_band": worst_d,
            "collapse": coll.get("d"), "collapse_worst_over_band": worst_coll,
            "worlds_a_to_c_worst_over_band_saved": others,
            "worst_over_band": worst, "caught": bool(worst >= 3.0),
            "at_plateau_ends_saved": saved["at_plateau_ends"]["worst_over_band"],
        }
        log("plant %s: world (d) reproduces the run's plateau ends: %s (%.2g band); worst %.3g "
            "bands, collapse %.3g, worlds (a)-(c) %.3g" % (pname, same, diff, worst_d, worst_coll,
                                                         others))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--plants", action="store_true",
                    help="recompute each plant's world (d) and score it under the declaration")
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
    # The rebuilt readouts against the interface's stored ones (10 significant digits there).
    worst_rebuild = 0.0
    for name in run.WORLDS:
        stored = interface["worlds"][name]["parts"]
        rows = delivered[name]["rows"]
        k = 0
        for part in stored:
            for j in range(len(part["t"])):
                for key in run.READOUTS:
                    a_, b_ = part["readouts"][key][j], rows[k]["readouts"][key]
                    if b_ != 0.0:
                        worst_rebuild = max(worst_rebuild, abs(a_ - b_) / abs(b_))
                    elif a_ != 0.0:
                        worst_rebuild = max(worst_rebuild, 1.0)
                k += 1
    scoring = protocol.Scoring(world, delivered)
    trace, worst = run.compare_runs(world, delivered, small_runs, scoring)
    ends, worst_ends = run.compare_runs(world, delivered, small_runs, scoring,
                                        where=lambda n, r: r["side"] == "end")
    collapse, worst_collapse = run.compare_runs(
        world, delivered, small_runs, scoring,
        where=lambda n, r: bool(scoring.in_collapse(n, [r])[0]))
    focus = {
        "a_inhibitor_branch": run.compare_runs(
            world, {"a": delivered["a"]}, {"a": small_runs["a"]}, scoring,
            where=lambda n, r: r["branch"] == "inhibitor")[0].get("a"),
        "b_first_2_s": run.compare_runs(
            world, {"b": delivered["b"]}, {"b": small_runs["b"]}, scoring,
            where=lambda n, r: r["t"] <= 2.0)[0].get("b"),
    }
    state3 = scoring.state3_flux
    plants = None
    if a.plants:
        plants = plants_world_d(world, interface, scoring, delivered["d"],
                                lambda m: print(m, flush=True))
    result = {
        "schema": "cells.mito_r2_rescore@2",
        "provenance": run.provenance(),
        "run": run_dir.name,
        "run_revision": interface["provenance"]["git_revision"],
        "run_interface_sha256": hashlib.sha256(
            (run_dir / "interface.json").read_bytes()).hexdigest(),
        "documents": decl["documents"],
        "scoring": decl["scoring"],
        "scoring_fixed_from_reference": scoring.describe(),
        "bands": decl["bands"],
        "rebuild": {"worst_relative_difference_from_stored_readouts": worst_rebuild,
                    "note": "the interface stores readouts at 10 significant digits"},
        "trace_check": {"traces_M": small, "worst_over_band": worst,
                        "passes": bool(worst < 0.1), "per_world": trace,
                        "at_plateau_ends": {"worst_over_band": worst_ends,
                                            "passes": bool(worst_ends < 0.1),
                                            "per_world": ends},
                        "collapse": {"worst_over_band": worst_collapse,
                                     "per_world": collapse},
                        "focus": focus,
                        "run_scored_it_at": {
                            "worst_over_band": interface["trace_check"]["worst_over_band"],
                            "at_plateau_ends":
                                interface["trace_check"]["at_plateau_ends"]["worst_over_band"],
                            "rules": "erratum 2 (the run's own scoring)"}},
        "plants": plants,
        "o2_window_check": o2_window_check(world, delivered["d"]["rows"], state3),
    }
    Path(a.out).write_text(json.dumps(result, indent=1, allow_nan=False) + "\n")
    print(json.dumps({"rebuild": worst_rebuild, "scoring": scoring.describe(),
                      "trace_worst_over_band": worst, "at_plateau_ends": worst_ends,
                      "collapse": worst_collapse,
                      "plants": None if plants is None else {
                          k: {"worst": v["worst_over_band"],
                              "collapse": v["collapse_worst_over_band"],
                              "reproduces": v["reproduces_saved_plateau_ends_d"]}
                          for k, v in plants.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
