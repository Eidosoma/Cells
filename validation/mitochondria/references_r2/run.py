"""R2's run: the start state, the four worlds, the convergence ladder and the trace check.

Usage (from a frozen snapshot of the checkout, on a light CPU):
    python -m validation.mitochondria.references_r2.run --out DIR [--quick]

Writes into DIR:
- interface.json: every declared readout at the protocol's output times, for each world, at the
  delivered tolerance; the start state and its anchor; the plateaus and the drift rule; the
  ledgers; the uncoupler's stall; the convergence ladder; the trace check;
- full.npz: every state at every output time, for every tolerance and method of the ladder;
- RECEIPT.json: the code's provenance (the snapshot's Git revision and patch digest), the
  environment, the command, the times and each output's digest.
"""

import argparse
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.integrate import solve_ivp

from . import constants, model, protocol, steady

WORLDS = ("a", "b", "c", "d")
DELIVERED_RTOL = 1e-11
LADDER = (1e-6, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11, 1e-12)
BDF_RTOLS = (1e-10,)
READOUTS = (
    "dpsi_mV", "pH_N", "pH_P", "NADH_fraction", "cytc_reduced_fraction", "QH2_fraction",
    "O2_flux", "ATP_export_exchange", "ATP_export_outer", "outer_potential_mV",
    "K_N", "Pi_N", "ATP_N", "K_P", "Pi_P", "ATP_P", "ADP_P", "AMP_P", "Mg_free_N", "Mg_free_P",
    "O2_N", "O2_P", "O2_node",
    "J_C1", "J_C3", "J_F1", "J_PiHt", "J_KH", "J_Supply", "J_AK", "J_Leak", "J_Uncoupler",
    "J_O2_IM",
)
UNITS = {
    "dpsi_mV": "mV, phi_P - phi_N", "pH_N": "-log10 free [H+]_N/M", "pH_P": "-log10 free [H+]_P/M",
    "NADH_fraction": "NADH/(NADH + NAD)", "cytc_reduced_fraction": "c2+/(c2+ + c3+)",
    "QH2_fraction": "QH2/(QH2 + Q)",
    "O2_flux": "mol O2 s-1 (L mito)-1 (complex IV's J, per O2)",
    "ATP_export_exchange": "mol s-1 (L mito)-1 (the exchange's J, ATP out of N)",
    "ATP_export_outer": "mol s-1 (L mito)-1 (net ATP forms from the IMS to the bath)",
    "outer_potential_mV": "mV, phi_IMS - phi_bath",
    "J_*": "mol s-1 (L mito)-1, each law's turnover as the appendix writes it",
    "concentrations": "M, per litre of that compartment's water; Mg_free_* free Mg2+",
}


def judged_error(key, a, b, bands):
    band_key, kind = protocol.JUDGED[key]
    band = bands[band_key]
    if kind == "absolute":
        return np.abs(a - b) / band
    return np.abs(a - b) / np.maximum(np.abs(b), 1e-300) / band


def settle_and_start(world, rule, log):
    """R2's guesses, settled at state 4, then the anchored start state (G7)."""
    ctl = model.Controls(world, bath="trace")
    y = world.guess_state(ctl)
    sol = solve_ivp(lambda t, q: world.rhs(t, q, ctl), (0.0, 3000.0), y, method="Radau",
                    rtol=1e-8, atol=protocol.atol_vector(1e-8),
                    jac=lambda t, q: world.jac(t, q, ctl))
    if sol.status != 0:
        raise RuntimeError("settling failed: " + sol.message)
    limits = world.declaration["anchor"]["Pi_e_limit"]["value"]
    target = world.declaration["anchor"]["pH_N"]["value"]
    res = steady.start_state(world, sol.y[:, -1], target, limits, rule=rule)
    log("start state: I_N %.15e, I_NP %.15e, outer potential %.3e mV" % (
        res["I_N"], res["I_NP"], res["outer_potential_mV"]))
    return res


def check_start_is_steady(world, start, rtol):
    """Integrate 600 s at state 4 from the start state: it must not move."""
    ctl = model.Controls(world, bath="trace")
    sol, st = protocol.integrate(world, start, 0.0, 600.0, ctl, np.array([0.0, 600.0]), rtol)
    a = world.readouts(sol.y[:, 0], ctl)
    b = world.readouts(sol.y[:, -1], ctl)
    bands = world.declaration["bands"]
    return {k: float(judged_error(k, np.array(b[k]), np.array(a[k]), bands))
            for k in protocol.JUDGED}


def table(rows, keys):
    return {k: np.array([r["readouts"][k] for r in rows]) for k in keys}


def run_all(world, start, rtol, method, worlds, log):
    out = {}
    for name in worlds:
        t0 = time.process_time()
        res = protocol.run_world(world, name, start, rtol, method)
        rows, ref = protocol.evaluate_records(world, res)
        out[name] = dict(result=res, rows=rows, ref=ref)
        log("world %s, %s rtol %.0e: %d outputs, %d RHS calls, %.1f s CPU" % (
            name, method, rtol, len(rows), sum(s["nfev"] for s in res["stats"]),
            time.process_time() - t0))
    return out


def convergence(runs, ref_key, keys, bands):
    """Each run's largest error against the reference run, per world and readout."""
    ref = runs[ref_key]
    report = {}
    for key, run in runs.items():
        if key == ref_key:
            continue
        per_world = {}
        for name in ref:
            a = table(run[name]["rows"], keys)
            b = table(ref[name]["rows"], keys)
            entry = {}
            for k in keys:
                if k in protocol.JUDGED:
                    entry[k] = {"max_error_over_band": float(np.max(judged_error(k, a[k], b[k],
                                                                                bands)))}
                else:
                    scale = max(float(np.max(np.abs(b[k]))), 1e-300)
                    err = float(np.max(np.abs(a[k] - b[k])) / scale)
                    entry[k] = {"max_error_over_max_abs": err}
            per_world[name] = entry
        report[key] = per_world
    return report


def worst_judged(conv):
    out = {}
    for key, per_world in conv.items():
        worst = 0.0
        for entry in per_world.values():
            for v in entry.values():
                if "max_error_over_band" in v:
                    worst = max(worst, v["max_error_over_band"])
        out[key] = worst
    return out


def fmt(x):
    return float("%.10g" % x)


def world_payload(world, run):
    rows = run["rows"]
    parts = []
    keys = []
    for r in rows:
        k = (r["branch"], r["segment"])
        if k not in keys:
            keys.append(k)
    for branch, seg in keys:
        rs = [r for r in rows if r["segment"] == seg and r["branch"] == branch]
        part = {"segment": seg, "branch": branch, "controls": rs[0]["controls"],
                "t0": rs[0]["t"], "t1": rs[-1]["t"], "t": [fmt(r["t"]) for r in rs],
                "readouts": {k: [fmt(r["readouts"][k]) for r in rs] for k in READOUTS},
                "ledgers": {
                    "energy_residual": [fmt(r["energy_residual"]) for r in rs],
                    "dissipation_cumulative": [fmt(r["D"]) for r in rs],
                    "charge_N_drift": [fmt(r["invariants"]["charge_N"]
                                           - run["ref"]["inv"]["charge_N"]) for r in rs],
                    "charge_NP_drift": [fmt(r["invariants"]["charge_NP"]
                                            - run["ref"]["inv"]["charge_NP"]) for r in rs],
                },
                "synthase_stall_mV": [fmt(r["stall_mV"]) for r in rs]}
        parts.append(part)
    plateaus = protocol.plateau_drift(world, rows)
    ledgers = protocol.ledger_closure(rows, run["ref"])
    return {"parts": parts, "plateaus": plateaus,
            "plateaus_against_newton": plateau_newton_check(world, run, world.declaration["bands"]),
            "ledgers": ledgers, "cost": run["result"]["stats"]}


def plateau_newton_check(world, run, bands):
    """Each plateau's end against the Newton steady state with the same seven inventories.

    The steady state is algebraic (steady.solve), so this checks the integration and the drift
    rule independently. World (d)'s plateaus are skipped: its O2 node is finite, so they are not
    steady states.
    """
    out = {}
    for r, rec in zip(run["rows"], run["result"]["records"], strict=True):
        if r["side"] != "end" or rec["controls"].get("o2") == "node":
            continue
        y = rec["y"]
        ctl = model.Controls(world, **rec["controls"])
        I_N = world.charge_inventory(y)
        I_NP = sum(world.row_charge(y))
        try:
            ys, info = steady.solve(world, ctl, y, I_N, ("inventory", I_NP))
        except steady.NoConvergence as error:
            out[r["segment"]] = {"error": str(error)}
            continue
        a = world.readouts(y, ctl)
        b = world.readouts(ys, ctl)
        errs = {k: float(judged_error(k, np.array(a[k]), np.array(b[k]), bands))
                for k in protocol.JUDGED}
        out[r["segment"]] = {"worst_over_band": max(errs.values()), "per_readout": errs,
                             "newton_iterations": info["iterations"]}
    return out


def uncoupler_stall(run):
    out = {}
    for r in run["rows"]:
        if r["branch"] in ("uncoupler", "inhibitor") and r["side"] == "end":
            rd = r["readouts"]
            out[r["branch"]] = {"t": r["t"], "dpsi_mV": rd["dpsi_mV"], "stall_mV": r["stall_mV"],
                                "dpsi_minus_stall_mV": rd["dpsi_mV"] - r["stall_mV"],
                                "J_F1": rd["J_F1"], "J_ANT": rd["J_ANT"],
                                "synthase_reversed": bool(rd["J_F1"] < 0.0)}
    return out


def provenance():
    here = Path(__file__).resolve()
    root = here.parents[3]
    snap = root / "SNAPSHOT.json"
    if snap.is_file():
        meta = json.loads(snap.read_text())
        return {"kind": "snapshot", "snapshot": str(root), "git_revision": meta["git_revision"],
                "patch_sha256": meta["patch_sha256"],
                "clean": meta["patch_sha256"] == hashlib.sha256(b"").hexdigest(),
                "files": sorted(meta["files"])}
    rev = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--",
                            "validation/mitochondria/references_r2"], capture_output=True,
                           text=True).stdout
    return {"kind": "checkout (development run)", "git_revision": rev, "dirty": dirty}


def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--rule", default=None,
                    choices=("zero_potential_each", "held_from_anchor", "held_from_start"),
                    help="I_NP's closure; the declared rule (G5 erratum) unless given")
    ap.add_argument("--quick", action="store_true", help="delivered tolerance only (a check)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    started_utc = datetime.now(timezone.utc).isoformat()
    t_start = time.time()
    cpu_start = time.process_time()
    logf = open(out / "run.log", "w")

    def log(msg):
        line = "%s %s" % (datetime.now(timezone.utc).strftime("%H:%M:%S"), msg)
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    try:
        decl = constants.load_declaration()
        declared_rule = decl["anchor"]["I_NP_rule"]["value"]
        if a.rule is None:
            a.rule = declared_rule
        failures = constants.check_printed()
        log("appendix values reproduced: %s" % (not failures))
        world = model.World(decl)
        bands = decl["bands"]
        start_res = settle_and_start(world, a.rule, log)
        start = start_res["start"]
        steady_check = check_start_is_steady(world, start, DELIVERED_RTOL)
        log("start state held over 600 s: worst %.2e of a band" % max(steady_check.values()))
        ladder = (DELIVERED_RTOL,) if a.quick else LADDER
        runs = {}
        ladder_failures = {}
        required = {"Radau %.0e" % DELIVERED_RTOL, "Radau %.0e" % min(LADDER)}
        plan = [("Radau", rtol) for rtol in ladder]
        if not a.quick:
            plan += [("BDF", rtol) for rtol in BDF_RTOLS]
        for method, rtol in plan:
            key = "%s %.0e" % (method, rtol)
            try:
                runs[key] = run_all(world, start, rtol, method, WORLDS, log)
            except RuntimeError as error:
                if key in required:
                    raise
                ladder_failures[key] = repr(error)
                log("%s failed, recorded: %r" % (key, error))
        delivered = runs["Radau %.0e" % DELIVERED_RTOL]
        keys = list(READOUTS)
        conv = {}
        if not a.quick:
            ref_key = "Radau %.0e" % min(LADDER)
            conv = convergence(runs, ref_key, keys, bands)
            # The delivered run's own error: against the tighter run, and against BDF.
            log("ladder, worst judged error over band: %s" % json.dumps(
                {k: "%.2e" % v for k, v in worst_judged(conv).items()}))
        # The trace check (G3): traces 1,000 times smaller, the whole chain again.
        small = {k: decl["bath"][k]["value"] / 1000.0 for k in ("ADP_trace", "ATP_trace",
                                                                 "AMP_trace")}
        world_small = model.World(decl, overrides=small)
        start_small = settle_and_start(world_small, a.rule, log)["start"]
        small_runs = run_all(world_small, start_small, DELIVERED_RTOL, "Radau", WORLDS, log)
        trace = {}
        worst_trace = 0.0
        for name in WORLDS:
            rows_a = delivered[name]["rows"]
            A = table(rows_a, protocol.JUDGED)
            B = table(small_runs[name]["rows"], protocol.JUDGED)
            entry = {}
            for k in protocol.JUDGED:
                err = judged_error(k, B[k], A[k], bands)
                i = int(np.argmax(err))
                entry[k] = {"worst_over_band": float(err[i]), "segment": rows_a[i]["segment"],
                            "t": rows_a[i]["t"], "value_1nM": float(A[k][i]),
                            "value_small": float(B[k][i])}
                worst_trace = max(worst_trace, float(err[i]))
            trace[name] = entry
        log("trace check: worst change %.3e of a band (must stay below 0.1)" % worst_trace)
        # The interface.
        N, P = world.forms(start)
        ctl4 = model.Controls(world, bath="trace")
        interface = {
            "schema": "cells.mito_r2_interface@1",
            "what": "R2, MT-1b's judged reference (D280): an independent integration of the "
                    "declared equations, code-blind",
            "provisional": a.rule != declared_rule,
            "documents": decl["documents"],
            "readings": decl["readings"],
            "provenance": provenance(),
            "receipt": "RECEIPT.json",
            "integrator": {
                "method": "scipy.integrate.solve_ivp Radau (implicit Runge-Kutta Radau IIA, "
                          "order 5), SciPy %s" % scipy.__version__,
                "rtol": DELIVERED_RTOL,
                "atol": "rtol x 1e-9 M for every concentration (relative control above 1e-9 "
                        "M), rtol x 1 mV for dPsi; the ledger states are quadratures outside the "
                        "error control (atol 1), their accuracy the physical steps' own",
                "jacobian": "forward differences over the physical columns (model.World.jac)",
                "restarts": "one solve_ivp call per protocol segment, in the segment's own time "
                            "t - t0: the solver restarts at every scheduled step",
                "closure": "free H+ and Mg2+ by safeguarded Newton in ln x, converged to rounding "
                           "at every right-hand-side evaluation",
                "outputs": "dense output (t_eval) at the declared output times",
            },
            "units": UNITS,
            "bands": bands,
            "start_state": {
                "rule_for_I_NP": a.rule,
                "rule_status": decl["anchor"]["I_NP_rule"]["source"] if a.rule == declared_rule
                else "an alternative reading, recorded and not used",
                "I_N_check": {"declared": decl["anchor"]["I_N_check"]["value"],
                              "relative_difference": abs(start_res["I_N"]
                                                         - decl["anchor"]["I_N_check"]["value"])
                              / decl["anchor"]["I_N_check"]["value"]},
                "I_N_mol_per_L_mito": start_res["I_N"],
                "I_NP_mol_per_L_mito": start_res["I_NP"],
                "anchor": [{k: v for k, v in rec.items() if k != "continuation"}
                           for rec in start_res["limits"]],
                "outer_potential_mV": start_res["outer_potential_mV"],
                "rows": {name: float(start[model.IDX[name]]) for name in model.PHYS},
                "free_forms_N": N, "free_forms_P": P,
                "readouts": world.readouts(start, ctl4),
                "held_600s_worst_over_band": steady_check,
            },
            "worlds": {name: world_payload(world, delivered[name]) for name in WORLDS},
            "uncoupler_stall": uncoupler_stall(delivered["a"]),
            "convergence": {
                "reference": None if a.quick else "Radau %.0e" % min(LADDER),
                "failed_runs": ladder_failures,
                "worst_judged_error_over_band": worst_judged(conv) if conv else {},
                "per_run": conv,
            },
            "trace_check": {"traces_M": small, "worst_over_band": worst_trace,
                            "passes": bool(worst_trace < 0.1), "per_world": trace},
            "appendix_values_reproduced": not failures,
        }
        with open(out / "interface.json", "w") as stream:
            json.dump(interface, stream, separators=(",", ":"), allow_nan=False)
            stream.write("\n")
        arrays = {}
        for key, run in runs.items():
            for name in WORLDS:
                tag = key.replace(" ", "_") + "_" + name
                arrays[tag + "_t"] = np.array([r["t"] for r in run[name]["result"]["records"]])
                arrays[tag + "_y"] = np.array([r["y"] for r in run[name]["result"]["records"]])
        for name in WORLDS:
            recs = small_runs[name]["result"]["records"]
            arrays["small_traces_" + name + "_t"] = np.array([r["t"] for r in recs])
            arrays["small_traces_" + name + "_y"] = np.array([r["y"] for r in recs])
        arrays["start"] = start
        arrays["start_small_traces"] = start_small
        np.savez_compressed(out / "full.npz", **arrays)
        status = "complete"
    except BaseException as error:
        status = "failed: %r" % (error,)
        log(status)
        raise
    finally:
        receipt = {
            "kind": "cells.mito_r2_run_receipt@1",
            "status": status,
            "command": [sys.executable, "-m", "validation.mitochondria.references_r2.run"]
                       + list(argv if argv is not None else sys.argv[1:]),
            "provenance": provenance(),
            "started_utc": started_utc,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "wall_s": time.time() - t_start,
            "cpu_s": time.process_time() - cpu_start,
            "host": socket.gethostname(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "python": sys.version,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "outputs": {p.name: digest(p) for p in sorted(out.iterdir())
                        if p.is_file() and p.name not in ("RECEIPT.json", "run.log")},
        }
        logf.close()
        with open(out / "RECEIPT.json", "w") as stream:
            json.dump(receipt, stream, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
