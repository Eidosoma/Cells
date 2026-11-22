"""Generate the release references (sheet §9: R1) and their interface files.

    python -m validation.gene_regulation.references.release_run --out DIR

Writes DIR/interface_release/{release_inputs,release_r1}.json, and DIR/invocations/ with each
invocation's receipt (run.py's provenance: the snapshot, revision, status and patch). About a
minute on one core. Run it from a source snapshot (validation/source_snapshot.py).

What it runs (sheet §9.9), each at the numeric test instance, by DOP853 at rtol 2.5e-12, and again
at 2.5e-14 for the sheet's 100× convergence check (§6):
- R1 at p ∈ {0, 0.25, 0.75, 1} and its matched blank (H(0) = 0), with `returned` and `held`:
  - with one class (the reference, with the exact trackers);
  - with two classes labelled at release (§9.8's route 1), the blanks included;
- R1 at p = 0.75 with A1's recharging added and its blank, a variant reported for reading R1.

R2 (A1 with the release step) is held until the sheet's addendum on R2's translation is tagged.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np

from . import release as R
from . import sheet
from .assemble import _clean, _sig
from .run import provenance

PRIMARY_RTOL = 2.5e-12
CHECK_RTOL = 2.5e-14
FPC = R.FPC
R1_TIMES = np.arange(0.0, 14400.0 + 1, R.GRID_R1)
COUNTERS = ("hold_tx", "int_Q_tx", "int_Qf_d1", "int_Qf_s1", "n_Rd1", "n_Rs1", "int_D_Rd1",
            "int_D_Rs1")


def convergence(a: dict, b: dict) -> dict:
    out = {}
    for k, x in a.items():
        if k == "t":
            continue
        x, y = np.asarray(x, float), np.asarray(b[k], float)
        s = float(np.max(np.abs(x)))
        out[k] = float(np.max(np.abs(x - y)) / s) if s > 0 else float(np.max(np.abs(x - y)))
    return out


def solve(world_fn, decl: R.ReleaseDecl, times, check: bool = True) -> dict:
    sysm = R.ReleaseSystem(world_fn(decl), sheet.TEST_INSTANCE, decl)
    t0 = time.time()
    scales = R.state_scales(sysm, times)
    sol = R.integrate(sysm, times, PRIMARY_RTOL, scales)
    ro = R.readouts(sysm, sol)
    ids = R.identities(sysm, ro)
    rec = {"decl": decl, "world": sysm.world.name, "ro": ro, "ids": ids,
           "levels": R.levels(ids), "domain": sol["domain"],
           "heat_min_increment": {h: v / ro[h][-1] if ro[h][-1] else v
                                  for h, v in sol["heat_min_increment"].items()},
           "steps": sol["steps"]}
    if check:
        tight = R.integrate(sysm, times, CHECK_RTOL, scales, track=False)
        rec["convergence"] = convergence(ro, R.readouts(sysm, tight))
        rec["steps_check"] = tight["steps"]
    rec["seconds"] = time.time() - t0
    return rec


def _pick(ro: dict, idx) -> dict:
    return {k: [float(np.asarray(v)[i]) for i in idx] for k, v in ro.items()}


def _per_output_residuals(ids: dict, idx) -> dict:
    return {k: [float(np.asarray(r)[i]) for i in idx] for k, (r, s) in ids.items()
            if k in ("hold", "per_producer") or k.startswith("fate_")}


def _dec(x) -> Decimal:
    return Decimal(repr(float(x)))


def limit_check(case: dict, blank: dict, p: float, idx) -> dict:
    """§9.10: the run against the requester's limit, in copies, at the given outputs."""
    times = [float(case["ro"]["t"][i]) for i in idx]
    lim = R.limit(p, times)
    ro, bl = case["ro"], blank["ro"]
    rows = []
    for j, i in enumerate(idx):
        row = {"t": times[j], "hold": {"run": ro["hold_tx"][i] / FPC, "limit": lim["hold"][j]},
               "released": {"run": (ro["int_Qf_d1"][i] + ro["int_Qf_s1"][i]) / FPC,
                            "limit": lim["released"][j]}}
        for f in R.FATES:
            L = Decimal(lim[f"survivors_{f}"][j])
            run_f = {"released_into": ro[f"int_Qf_{f}1"][i] / FPC,
                     "n_F": ro[f"n_R{f}1"][i] / FPC,
                     "n_F_minus_blank": (ro[f"n_R{f}1"][i] - bl[f"n_R{f}1"][i]) / FPC,
                     "released_still_present": ro[f"LR_{f}"][i] / FPC,
                     "distance_integrated": ro[f"DL_{f}"][i] / FPC}
            ab, rel = {}, {}
            for k in ("n_F", "n_F_minus_blank", "released_still_present"):
                ab[k] = float(_dec(run_f[k]) - L)
            ab["distance_integrated"] = float(run_f["distance_integrated"])
            if L != 0:
                rel = {k: float(_dec(v) / L) for k, v in ab.items()}
            row[f"fate_{f}"] = {"run": run_f, "limit_survivors": lim[f"survivors_{f}"][j],
                                "limit_released_into": lim[f"released_{f}"][j],
                                "absolute_distance_copies": ab, "relative_distance": rel}
        for k in ("hold", "released"):
            Lk = Decimal(row[k]["limit"])
            row[k]["absolute_distance_copies"] = float(_dec(row[k]["run"]) - Lk)
            if Lk != 0:
                row[k]["relative_distance"] = float((_dec(row[k]["run"]) - Lk) / Lk)
        rows.append(row)
    return {"p": p, "rows": rows}


def requester_figures(check: dict) -> dict:
    """The requester's six figures at p = 0.75, t = 1 h (§9.10), against the run."""
    row = next(r for r in check["rows"] if r["t"] == 3600.0)
    figs = {"held": ("40", row["hold"]["run"]), "released": ("40", row["released"]["run"]),
            "released_durable": ("30", row["fate_d"]["run"]["released_into"]),
            "released_short": ("10", row["fate_s"]["run"]["released_into"]),
            "surviving_durable": ("24.852814", row["fate_d"]["run"]["released_still_present"]),
            "surviving_short": ("5.000000", row["fate_s"]["run"]["released_still_present"])}
    out = {}
    for k, (fig, run) in figs.items():
        d = (_dec(run) - Decimal(fig)) / Decimal(fig)
        out[k] = {"requester": fig, "run_copies": run, "relative_distance": float(d)}
    out["exact_limit_survivors"] = {"durable": row["fate_d"]["limit_survivors"],
                                    "short": row["fate_s"]["limit_survivors"]}
    out["note"] = ("survivors are the released molecules still present (the tracker LR, equal to "
                   "n_F minus the matched blank); n_F itself also holds the trace's survivors")
    return out


def cohort(k1: dict, k2: dict, k2_blank: dict | None, p: float | None) -> dict:
    """§9.8 at T_SAMPLE: route 1 (label rows, K = 2) as the sheet writes it and against the
    matched blank; route 2's exact value (the tracker CO, K = 1); and, in R1, the first-order
    closed form. In copies."""
    t = list(k1["ro"]["t"])
    idx = [t.index(ts) for ts in R.T_SAMPLE]
    lim = R.limit(p, R.T_SAMPLE) if p is not None else None
    out = {}
    for f in R.FATES:
        rows = []
        for j, i in enumerate(idx):
            F2 = k2["ro"][f"n_R{f}2"]
            r1_sheet = (F2[i] - F2[0]) / FPC
            r2 = k1["ro"][f"CO_{f}"][i] / FPC
            row = {"ts": R.T_SAMPLE[j], "route1_sheet": r1_sheet, "route2_exact": r2,
                   "route1_sheet_minus_route2": r1_sheet - r2}
            if r2:
                row["route1_sheet_rel"] = (r1_sheet - r2) / r2
            if k2_blank is not None:
                r1_blank = (F2[i] - k2_blank["ro"][f"n_R{f}2"][i]) / FPC
                row["route1_blank"] = r1_blank
                row["route1_blank_minus_route2"] = r1_blank - r2
                if r2:
                    row["route1_blank_rel"] = (r1_blank - r2) / r2
            if lim is not None:
                L = Decimal(lim[f"cohort_{f}"][j])
                row["first_order_limit"] = lim[f"cohort_{f}"][j]
                if L != 0:
                    row["route2_vs_limit_rel"] = float((_dec(r2) - L) / L)
            rows.append(row)
        out[f] = rows
    return out


def summary_levels(rec: dict) -> dict:
    lv = rec["levels"]
    k = max(lv, key=lv.get)
    c = rec.get("convergence", {})
    kc = max(c, key=c.get) if c else None
    return {"identity_worst": lv[k], "identity_where": k,
            "convergence_worst": c.get(kc) if kc else None, "convergence_where": kc,
            "heat_min_increment_rel": min(rec["heat_min_increment"].values()),
            "domain": {kk: v[0] for kk, v in rec["domain"].items()},
            "steps": rec["steps"], "seconds": rec["seconds"]}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    out = args.out
    (out / "invocations").mkdir(parents=True, exist_ok=True)
    (out / "interface_release").mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    receipt = {"argv": sys.argv[1:], "provenance": provenance()}
    (out / "invocations" / f"{stamp}.json").write_text(json.dumps(receipt, indent=1))
    t_start = time.time()
    i_out = [list(R1_TIMES).index(t) for t in R.T_OUT_R1]

    # ---- R1 ---------------------------------------------------------------------------------
    r1 = {"cases": [], "limit_checks": {}, "cohorts": {}, "variant_recharging": None}
    for machine in ("returned", "held"):
        blank1 = solve(R.r1_world, R.ReleaseDecl(p=0.75, machine=machine, H0_copies=0), R1_TIMES)
        blank2 = solve(R.r1_world, R.ReleaseDecl(p=0.75, machine=machine, H0_copies=0,
                                                 classes=2), R1_TIMES)
        r1["cases"].append(case_record("blank", blank1, i_out))
        for p in R.P_CASES:
            k1 = solve(R.r1_world, R.ReleaseDecl(p=p, machine=machine, H0_copies=R.H0_COPIES),
                       R1_TIMES)
            k2 = solve(R.r1_world, R.ReleaseDecl(p=p, machine=machine, H0_copies=R.H0_COPIES,
                                                 classes=2), R1_TIMES)
            rec = case_record("case", k1, i_out)
            rec["label_run"] = summary_levels(k2)
            r1["cases"].append(rec)
            key = f"p={p:g}, {machine}"
            r1["limit_checks"][key] = limit_check(k1, blank1, p, i_out)
            r1["cohorts"][key] = cohort(k1, k2, blank2, p)
            if p == 0.75 and machine == "returned":
                r1["requester_figures"] = requester_figures(r1["limit_checks"][key])
        print(f"R1 {machine}: done after {time.time() - t_start:.0f} s", flush=True)
    vb = solve(lambda d: R.r1_world(d, recharging=True),
               R.ReleaseDecl(p=0.75, H0_copies=0), R1_TIMES)
    vc = solve(lambda d: R.r1_world(d, recharging=True),
               R.ReleaseDecl(p=0.75, H0_copies=R.H0_COPIES), R1_TIMES)
    r1["variant_recharging"] = {"case": case_record("case", vc, i_out),
                                "limit_check": limit_check(vc, vb, 0.75, i_out)}

    inputs = {
        "kind": "cells.gene_regulation.references.release_inputs@1",
        "sheet": {"tag": R.SHEET_TAG_R, "sections": "§9, read against §0–§8"},
        "declared": {"H0_copies": R.H0_COPIES, "tau_s": R.TAU, "p_cases": R.P_CASES,
                     "k_durable": R.K_DURABLE, "k_short": R.K_SHORT, "t_out_R1": R.T_OUT_R1,
                     "window": R.WINDOW, "t_sample": R.T_SAMPLE, "p_R2": R.P_R2,
                     "trace_mM": R.TRACE_mM, "potentials": sheet.TEST_INSTANCE.as_dict()},
        "methods": {"judge": f"DOP853 rtol {PRIMARY_RTOL}, atol rtol × each state's largest "
                             "magnitude in a first solve at 1e-8; outputs hit exactly",
                    "check": f"DOP853 rtol {CHECK_RTOL} (100× tighter)",
                    "limit": "decimal arithmetic, 50 digits",
                    "R1_grid_s": R.GRID_R1},
        "held": "R2 waits for the sheet's addendum on R2's translation",
        "tolerances": {"trajectory": sheet.TOL_TRAJECTORY, "identity": sheet.TOL_IDENTITY,
                       "closed_form": sheet.TOL_CLOSED_FORM},
        "invocations": [json.loads(q.read_text())
                        for q in sorted((out / "invocations").glob("*.json"))],
        "seconds": time.time() - t_start,
    }
    sizes = {}
    for name, doc in (("release_inputs", inputs),
                      ("release_r1", {"kind": "cells.gene_regulation.references.release_r1@1",
                                      **r1})):
        text = json.dumps(_clean(doc), separators=(",", ":"))
        (out / "interface_release" / f"{name}.json").write_text(text + "\n")
        sizes[name] = len(text)
    print("release interface written:", json.dumps(sizes), f"in {time.time() - t_start:.0f} s")


def case_record(kind: str, rec: dict, idx) -> dict:
    d = rec["decl"]
    return {"kind": kind, "decl": d.__dict__, "world": rec["world"],
            "t": [float(rec["ro"]["t"][i]) for i in idx],
            "readouts": _pick(rec["ro"], idx),
            "per_output_residuals": _per_output_residuals(rec["ids"], idx),
            "identity_levels": _sig(rec["levels"]),
            "convergence": _sig(rec.get("convergence", {})),
            "summary": summary_levels(rec)}


if __name__ == "__main__":
    main()
