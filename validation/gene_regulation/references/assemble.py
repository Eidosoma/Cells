"""Write the interface files (interface/*.json) from a run's scratch directory (run.py).

Every number is a JSON float (17 significant digits) or a decimal string where it came from the
closed forms' decimal arithmetic. Units: amounts fmol, time s, free energies kJ/mol, heats pJ,
R-noise in molecules.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import closed_forms, model, plants, sheet
from .run import (
    CHECK,
    COARSE_RTOL,
    CROSS,
    EDGE_READOUT_PREFIXES,
    PRIMARY,
    RADAU_NEWTON_TOL,
    STRIDE,
    _load,
    git,
    kind_of,
    n_edge,
    slug,
    world_by_name,
    world_names,
)

UNITS = {"n_*, F_*, C_*, E_*, W_*": "fmol (residues in transit: fmol of residues)",
         "int_*": "fmol (cumulative extents from t = 0; int_J_C signed)",
         "G_minus_G0, H_*": "pJ", "dG_*": "kJ/mol per unit of progress", "t": "s",
         "J_bar_*": "fmol/s", "u": "1"}


def _clean(x):
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return _clean(x.tolist())
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, float) and not math.isfinite(x):
        return None if math.isnan(x) else ("inf" if x > 0 else "-inf")
    return x


def _write(path: Path, obj) -> int:
    text = json.dumps(_clean(obj), separators=(",", ":"))
    path.write_text(text + "\n")
    return len(text)


def _sig(x, n: int = 4):
    """A diagnostic number (a level, a margin, a change) to n significant digits."""
    if isinstance(x, dict):
        return {k: _sig(v, n) for k, v in x.items()}
    if x is None or not math.isfinite(x) or x == 0:
        return x
    return float(f"{x:.{n}g}")


def _round_up_1sig(x: float) -> float:
    e = math.floor(math.log10(x))
    return math.ceil(x / 10 ** e) * 10 ** e


def _readouts_for_json(ro: dict, stride: int = 1, prefixes=None) -> dict:
    out = {}
    for k, v in ro.items():
        if k == "t" or k.startswith("rate_"):
            continue
        if prefixes and not k.startswith(prefixes):
            continue
        v = np.asarray(v, float)
        out[k] = v.tolist() if k.startswith("J_bar_") else v[::stride].tolist()
    return out


def write_interface(out: Path, sets: list, prov: dict) -> None:
    out = Path(out)
    iface = out / "interface"
    iface.mkdir(parents=True, exist_ok=True)
    wn = world_names()
    ne = n_edge(sets)
    refs = {(i, w): _load(out / "refs" / f"{i:02d}_{slug(w)}.pkl")
            for i in range(len(sets)) for w in wn}
    closed = {i: _load(out / "closed" / f"{i:02d}.pkl") for i in range(len(sets))}
    sizes = {}

    # ---- inputs.json ----------------------------------------------------------------------
    derived = closed_forms.derived_values(sheet.TEST_INSTANCE)
    worlds = []
    for w in wn:
        W = world_by_name(w)
        worlds.append({"name": w, "t_end": W.t_end, "dt": W.dt, "window": W.window, "V_pL": W.V,
                       "rows0_fmol": W.rows0, "held": list(W.held), "pools_fmol": W.pools,
                       "routes": [r.__dict__ for r in W.routes],
                       "degradations": [d.__dict__ for d in W.degradations],
                       "recharging": W.recharging, "regulator": W.regulator,
                       "phases": [[a, None if math.isinf(b) else b, p] for a, b, p in W.phases],
                       "lengths": W.lengths})
    inputs = {
        "kind": "cells.gene_regulation.references.inputs@1",
        "sheet": {"tag": sheet.SHEET_TAG, "path": sheet.SHEET_PATH,
                  "commit": git("rev-parse", sheet.SHEET_TAG + "^{commit}") or None},
        "provenance": prov,
        "declared": {"A1": sheet.A1, "A1M": sheet.A1M, "SWEEP_T": sheet.SWEEP_T,
                     "SWEEP_NR": sheet.SWEEP_NR, "moieties": sheet.MOIETIES},
        "constants": {"RT_kJ_mol": derived["RT_kJ_mol"], "c_1_mM": derived["c_1"],
                      "fmol_per_copy": repr(model.FMOL_PER_COPY), "c0_mM": sheet.C_STANDARD_mM},
        "potential_sets": [dict(index=i, **p.as_dict()) for i, p in enumerate(sets)],
        "edge_sets": list(range(ne)),
        "worlds": worlds,
        "methods": {
            "judge": {"method": PRIMARY[0], "rtol": PRIMARY[1],
                      "atol": "rtol × each state's largest magnitude in a coarse solve"},
            "check": {"method": CHECK[0], "rtol": CHECK[1], "atol": "100× tighter, same rule"},
            "cross": {"method": CROSS[0], "rtol": CROSS[1], "newton_tol": RADAU_NEWTON_TOL,
                      "at": "the edge sets"},
            "coarse_rtol_for_scales": COARSE_RTOL,
            "states": "deviations from the initial state; outputs hit exactly (restart each)",
            "closed_forms": "decimal arithmetic, 50 digits, checked at 70",
            "edits": model.ALL_EDITS},
        "tolerances": {"trajectory": sheet.TOL_TRAJECTORY, "closed_form": sheet.TOL_CLOSED_FORM,
                       "identity": sheet.TOL_IDENTITY, "eps_A1": sheet.EPS_A1,
                       "eps_M": sheet.EPS_M, "x_dom": sheet.X_DOM},
        "noise": {"replicates": sheet.NOISE_REPLICATES, "band_se": sheet.NOISE_BAND_SE,
                  "floor": f"{sheet.NOISE_FLOOR}/N", "master_seed": sheet.NOISE_MASTER_SEED,
                  "streams": "numpy SeedSequence(master).spawn(2)[w].spawn(1000)[i], PCG64; "
                             "w = 0 for A1, 1 for T = 10", "se_ddof": 1},
        "transcription_check": closed_forms.typed_digit_check(derived),
    }
    sizes["inputs.json"] = _write(iface / "inputs.json", inputs)

    # ---- trajectories ---------------------------------------------------------------------
    traj = {"kind": "cells.gene_regulation.references.trajectories@1", "set": 0,
            "potentials": sets[0].as_dict(), "units": UNITS, "worlds": {}}
    for w in wn:
        ro = refs[(0, w)]["readouts"]
        traj["worlds"][w] = {"t": ro["t"].tolist(), "readouts": _readouts_for_json(ro)}
    sizes["trajectories_test_instance.json"] = _write(iface / "trajectories_test_instance.json",
                                                      traj)
    edge = {"kind": "cells.gene_regulation.references.trajectories_edge@1", "units": UNITS,
            "stride": STRIDE, "readout_prefixes": list(EDGE_READOUT_PREFIXES), "sets": {}}
    for i in range(1, ne):
        edge["sets"][str(i)] = {"potentials": sets[i].as_dict(), "worlds": {}}
        for w in wn:
            ro = refs[(i, w)]["readouts"]
            st = STRIDE[kind_of(w)[0]]
            edge["sets"][str(i)]["worlds"][w] = {
                "t": ro["t"][::st].tolist(),
                "readouts": _readouts_for_json(ro, st, EDGE_READOUT_PREFIXES)}
    sizes["trajectories_edge_sets.json"] = _write(iface / "trajectories_edge_sets.json", edge)
    ends = {"kind": "cells.gene_regulation.references.endpoints@1", "units": UNITS,
            "note": "every readout at t_end (and A1's at t_off) at the interior sets; the edge "
                    "sets' are in the trajectory files", "sets": []}
    for i, p in enumerate(sets):
        if i < ne:
            continue
        row = {"set": i, "potentials": p.as_dict(), "worlds": {}}
        for w in wn:
            ro = refs[(i, w)]["readouts"]
            row["worlds"][w] = {k: float(np.asarray(v)[-1]) for k, v in ro.items()
                                if k != "t" and not k.startswith("rate_")}
            if w == "A1":
                k_off = int(sheet.A1["t_off"] // sheet.A1["dt_out"])
                row["worlds"]["A1 at t_off"] = {k: float(np.asarray(v)[k_off])
                                                for k, v in ro.items()
                                                if k != "t"
                                                and not k.startswith(("rate_", "J_bar"))}
        ends["sets"].append(row)
    sizes["endpoints.json"] = _write(iface / "endpoints.json", ends)

    # ---- R-chain ----------------------------------------------------------------------------
    eps = sheet.EPS_A1
    chain_sets, gap_rows = [], []
    for i, p in enumerate(sets):
        lim = closed[i]["a1"]
        g = plants.a1_gaps(refs[(i, "A1")]["readouts"], lim)
        gap_rows.append((i, g))
        chain_sets.append({"set": i, "label": p.label, "steady": lim["steady"],
                           "frozen": lim["frozen"], "gaps": g, "gap_max": max(g.values()),
                           "within_eps_A1": max(g.values()) <= eps,
                           "precision": closed[i]["precision"]})
    lim0 = closed[0]["a1"]
    chain = {"kind": "cells.gene_regulation.references.r_chain@1", "eps_A1": eps,
             "gap_definition": "max over the outputs on [0, t_off) of |closed form − ODE| over "
                               "the limit's steady state",
             "test_instance": {"times": [float(t) for t in lim0["times"]],
                               "closed_form": {k: lim0["series"][k] for k in
                                               ("n_R", "n_P", "E_tx", "E_tl")},
                               "steady": lim0["steady"], "frozen": lim0["frozen"]},
             "sets": chain_sets}
    # ---- R-machine --------------------------------------------------------------------------
    epsm = sheet.EPS_M
    mach_sets = []
    for i, p in enumerate(sets):
        row = {"set": i, "label": p.label, "worlds": {}}
        for w in wn:
            if w == "A1":
                continue
            W = world_by_name(w)
            ro = refs[(i, w)]["readouts"]
            cf = closed[i]["machine"][w]
            routes = [r.name for r in W.routes]
            pool = next(iter(W.pools))
            g = plants.machine_gaps(ro, cf, routes, pool)
            cfj = cf if i == 0 else {k: float(v) for k, v in cf.items() if k != "prec"}
            row["worlds"][w] = {"closed": cfj, "ode": {
                **{f"J_bar_{r}": float(ro[f"J_bar_{r}"][0]) for r in routes},
                **{f"E_{r}": float(ro[f"E_{r}"][-1]) for r in routes},
                f"F_{pool}": float(ro[f"F_{pool}"][-1])}, "gaps": g,
                "within_eps_M": max(g.values()) <= epsm}
        mach_sets.append(row)
    machine = {"kind": "cells.gene_regulation.references.r_machine@1", "eps_M": epsm,
               "gap_definition": "|ODE − closed form| / closed form, J̄ over the final window, "
                                 "E and F at t_end", "sets": mach_sets}

    # ---- §5.6 reproduced --------------------------------------------------------------------
    def best(items):
        return max(items, key=lambda t: t[0]) if items else (None, None)

    rep = {}
    for key in ("n_R", "n_P", "E_tx", "E_tl"):
        v, i = best([(g[key], i) for i, g in gap_rows if i < ne])
        rep[f"A1 {key}"] = {"value": v, "where": sets[i].label}
    for item, prefix in (("J", "J_bar_"), ("E", "E_"), ("F", "F_")):
        v, where = best([(gv, f"{w}, {sets[r['set']].label}") for r in mach_sets[:ne]
                         for w, d in r["worlds"].items() for gk, gv in d["gaps"].items()
                         if gk.startswith(prefix)])
        rep[f"A1-M {item}"] = {"value": v, "where": where}
    if len(sets) > ne:
        v, i = best([(max(g.values()), i) for i, g in gap_rows if i >= ne])
        rep["A1 interior"] = {"value": v, "where": sets[i].label}
        v, where = best([(gv, f"{w}, {sets[r['set']].label}") for r in mach_sets[ne:]
                         for w, d in r["worlds"].items() for gv in d["gaps"].values()])
        rep["A1-M interior"] = {"value": v, "where": where}
    dom = [(val, f"{w}, {sets[i].label}, {key} at t = {t:g} s")
           for (i, w), rec in refs.items() for key, (val, t) in rec["domain_steps"].items()]
    v, where = best(dom)
    rep["x_max"] = {"value": v, "where": where}
    a1_all = max(max(g.values()) for _, g in gap_rows)
    m_all = max(gv for r in mach_sets for d in r["worlds"].values() for gv in d["gaps"].values())
    rep["eps_A1"] = {"value": _round_up_1sig(2 * a1_all), "rule": "twice the largest A1 gap, "
                     "rounded up to one significant digit", "largest_gap": a1_all}
    rep["eps_M"] = {"value": _round_up_1sig(2 * m_all), "rule": "twice the largest A1-M gap, "
                    "rounded up to one significant digit", "largest_gap": m_all}
    for k, d in rep.items():
        if k in sheet.SHEET_BOUNDS:
            sv = float(sheet.SHEET_BOUNDS[k][0])
            d["sheet"] = {"value": sv, "where": sheet.SHEET_BOUNDS[k][1]}
            d["relative_difference"] = (None if d["value"] is None
                                        else (d["value"] - sv) / abs(sv))
        if k in ("eps_A1", "eps_M"):
            d["sheet"] = {"value": sheet.EPS_A1 if k == "eps_A1" else sheet.EPS_M}
            d["equal"] = d["value"] == d["sheet"]["value"]
    chain["bounds_reproduction"] = {k: v for k, v in rep.items() if k.startswith("A1 ")
                                    or k in ("x_max", "eps_A1")}
    machine["bounds_reproduction"] = {k: v for k, v in rep.items() if k.startswith("A1-M")
                                      or k == "eps_M"}
    sizes["r_chain.json"] = _write(iface / "r_chain.json", chain)
    sizes["r_machine.json"] = _write(iface / "r_machine.json", machine)

    # ---- R-account --------------------------------------------------------------------------
    acc_rows, worst = [], (0.0, None)
    rad_worst = (0.0, None)
    for (i, w), rec in sorted(refs.items(), key=lambda kv: (kv[0][0], wn.index(kv[0][1]))):
        lv = rec["identity_levels"]
        ro = rec["readouts"]
        rate_min = {k[5:]: float(np.min(v)) for k, v in ro.items() if k.startswith("rate_")}
        row = {"set": i, "world": w, "identity_levels": _sig(lv),
               "heat_min_increment": _sig(rec["heat_min_increment"]),
               "heat_rate_min_at_outputs": _sig(min(rate_min.values())),
               "domain_max": {k: _sig(v, 6) for k, (v, t) in rec["domain_steps"].items()}}
        if i == 0:
            row["identity_scales"] = rec["identity_scales"]
            row["domain_max_t"] = {k: t for k, (v, t) in rec["domain_steps"].items()}
        m = row["identity_levels"][max(lv, key=lv.get)]
        if m > worst[0]:
            worst = (m, f"{w}, set {i}, {max(lv, key=lv.get)}")
        if "radau" in rec:
            rl = _sig(rec["radau"]["identity_levels"])
            row["radau_identity_levels"] = rl
            if max(rl.values()) > rad_worst[0]:
                rad_worst = (max(rl.values()), f"{w}, set {i}, {max(rl, key=rl.get)}")
        acc_rows.append(row)
    heats_ok = all(min(r["heat_min_increment"].values()) >= 0 for r in acc_rows) and all(
        r["heat_rate_min_at_outputs"] >= 0 for r in acc_rows)
    dom_ok = all(v <= sheet.X_DOM for r in acc_rows for v in r["domain_max"].values())
    account = {"kind": "cells.gene_regulation.references.r_account@1",
               "judge": f"{PRIMARY[0]} rtol {PRIMARY[1]}",
               "identity_scales": "machines and moieties: the conserved total; residues: r∫S at "
                                  "t_end; products: n(0) + ∫Q at t_end; energy: ΣH at t_end; "
                                  "W's definition (§1.2): r∫S at t_end",
               "tolerance": sheet.TOL_IDENTITY,
               "summary": {"worst_identity_level": worst[0], "where": worst[1],
                           "all_within_tolerance": worst[0] <= sheet.TOL_IDENTITY,
                           "heats_nonnegative_nondecreasing": heats_ok,
                           "domain_respected": dom_ok, "x_max": rep["x_max"],
                           "radau": {"worst_identity_level": rad_worst[0], "where": rad_worst[1],
                                     "newton_tol": RADAU_NEWTON_TOL,
                                     "within_tolerance": rad_worst[0] <= sheet.TOL_IDENTITY}},
               "rows": acc_rows}
    sizes["r_account.json"] = _write(iface / "r_account.json", account)

    # ---- R-noise ----------------------------------------------------------------------------
    nz = _load(out / "noise" / "report.pkl")
    noise_out = {"kind": "cells.gene_regulation.references.r_noise@1",
                 "band": "|sample mean − deterministic mean| ≤ 4.5 SE + 10/N", "worlds": {}}
    for w, d in nz.items():
        r = d["report"]
        names = ("F_pol", "F_rib", "E_tx", "E_tl", "n_R", "n_P") if w == "A1" else ("F", "E", "n_R")
        noise_out["worlds"][w] = {
            "params": {k: v for k, v in d["params"].items()}, "N": r["N"],
            "readouts": {nm: {"mean": r["mean"][:, j], "se": r["se"][:, j], "det": r["det"][:, j],
                              "gap": r["gap"][:, j], "band": r["band"][:, j]}
                         for j, nm in enumerate(names)},
            "outside": r["outside"], "comparisons": r["comparisons"],
            "max_ratio": float(np.max(r["ratio"])),
            "judged": w == "T10", "passes": r["outside"] == 0,
            "seconds": d["seconds"], "det_convergence": d["det_convergence"],
            "scalar_equals_batch_first_3": d["scalar_equals_batch_first_3"]}
    sizes["r_noise.json"] = _write(iface / "r_noise.json", noise_out)

    # ---- plants -----------------------------------------------------------------------------
    prow = []
    for path in sorted((out / "plants").glob("*.pkl")):
        rec = _load(path)
        named = {n for _, n in rec["plant"]["named"]}
        ch = rec["changes"]
        if rec["set"] == 0:  # every readout's change at the test instance
            changes = {k: (v if k in named else _sig(v)) for k, v in ch.items()}
        else:  # elsewhere the named readouts and the five largest
            top = sorted(ch, key=lambda k: -ch[k])[:5]
            changes = {k: (ch[k] if k in named else _sig(ch[k])) for k in ch
                       if k in named or k in top}
        il = rec["identity_levels"]
        prow.append({"id": rec["plant"]["id"], "edits": rec["plant"]["edits"],
                     "source": rec["plant"]["source"], "set": rec["set"], "world": rec["world"],
                     "changes": changes, "missing": rec["missing"],
                     "identity_levels": {k: (v if k in named else _sig(v)) for k, v in il.items()
                                         if k in named or v > sheet.TOL_IDENTITY},
                     "gaps": rec["gaps"], "verdicts": rec["verdicts"], "F_min": rec["F_min"]})
    summary = {}
    for r in prow:
        key = f"{r['id']} {'+'.join(r['edits'])}"
        s = summary.setdefault(key, {"source": r["source"], "named": {}, "largest_change": {},
                                     "identity_failures": {}, "gap_ratio_max": 0.0,
                                     "worlds": set(), "sets": set()})
        s["worlds"].add(r["world"])
        s["sets"].add(r["set"])
        for v in r["verdicts"]:
            n = s["named"].setdefault(v["item"], {"fails_everywhere": True, "min_margin": math.inf,
                                                  "min_measure": math.inf})
            n["fails_everywhere"] &= bool(v["fails"])
            if v["margin"] is not None:
                n["min_margin"] = min(n["min_margin"], v["margin"])
                n["min_measure"] = min(n["min_measure"], v["measure"])
        top = sorted(r["changes"].items(), key=lambda kv: -kv[1])[:3]
        for k, c in top:
            s["largest_change"][k] = max(s["largest_change"].get(k, 0.0), c)
        for k, lvl in r["identity_levels"].items():
            if lvl > sheet.TOL_IDENTITY:
                s["identity_failures"][k] = max(s["identity_failures"].get(k, 0.0), lvl)
        eps_ = sheet.EPS_A1 if r["world"] == "A1" else sheet.EPS_M
        s["gap_ratio_max"] = max(s["gap_ratio_max"], max(r["gaps"].values()) / eps_)
    for s in summary.values():
        s["worlds"] = sorted(s["worlds"])
        s["sets"] = sorted(s["sets"])
        s["caught"] = any(n["fails_everywhere"] for n in s["named"].values())
        s["named_items_that_hold"] = sorted(k for k, n in s["named"].items()
                                            if not n["fails_everywhere"])
    plants_out = {"kind": "cells.gene_regulation.references.plants@1",
                  "margins": "trajectory: change/scale over the references' resolution 1e-9 (and "
                             "over ε_A1, for scale); identity: level over 1e-12; closed form: gap "
                             "over ε_A1 or ε_M", "summary": summary, "rows": prow}
    sizes["plants.json"] = _write(iface / "plants.json", plants_out)

    # ---- convergence ------------------------------------------------------------------------
    conv_rows, cw, rw = [], (0.0, None), (0.0, None)
    for (i, w), rec in sorted(refs.items(), key=lambda kv: (kv[0][0], wn.index(kv[0][1]))):
        c = rec["convergence"]
        k = max(c, key=c.get)
        row = {"set": i, "world": w, "worst": c[k], "worst_readout": k, "steps": rec["steps"],
               "steps_tight": rec["steps_tight"], "nfev": rec["nfev"],
               "seconds": rec["seconds_total"]}
        if c[k] > cw[0]:
            cw = (c[k], f"{w}, set {i}, {k}")
        if "radau" in rec:
            rc = rec["radau"]["vs_tight"]
            kr = max(rc, key=rc.get)
            row["radau_vs_tight"] = {"worst": rc[kr], "worst_readout": kr,
                                     "steps": rec["radau"]["steps"]}
            if rc[kr] > rw[0]:
                rw = (rc[kr], f"{w}, set {i}, {kr}")
        if i == 0:
            row["per_readout"] = c
        conv_rows.append(row)
    prec = {k: max(closed[i]["precision"][k] for i in closed)
            for k in closed[0]["precision"]}
    conv = {"kind": "cells.gene_regulation.references.convergence@1",
            "trajectory_rule": "a second solve at 100× tighter rtol and atol changes no readout by "
                               "more than 1e-9 of its scale (its largest magnitude)",
            "summary": {"worst": cw[0], "where": cw[1], "within": cw[0] <= sheet.TOL_TRAJECTORY,
                        "radau_vs_tight_worst": rw[0], "radau_where": rw[1],
                        "closed_forms": prec,
                        "closed_forms_within": max(prec.values()) <= sheet.TOL_CLOSED_FORM,
                        "noise_det_convergence": {w: nz[w]["det_convergence"] for w in nz}},
            "rows": conv_rows}
    sizes["convergence.json"] = _write(iface / "convergence.json", conv)
    (out / "interface_sizes.json").write_text(json.dumps(sizes, indent=1))
    print("interface written:", json.dumps(sizes))
