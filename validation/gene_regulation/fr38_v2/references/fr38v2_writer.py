"""FR-38's second comparison, the code-blind references: the writer (SPEC.md section 7).

Usage (BLAS pinned to one thread; see README.md):

    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \\
        python -B fr38v2_writer.py --out DIR [--families AF,AN,B,C,D,invented]

Writes one JSON file per family (reference_<family>.json) and the sidecar run_times.json, which
holds wall times and is excluded from the bitwise check. Every value is computed here from the
spec folder's inputs; nothing imports, runs or reads the engine.
"""

import argparse
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from decimal import Decimal, localcontext

import numpy as np

import fr38v2_integrate as In
import fr38v2_model as Mo
import fr38v2_worlds as Wd

LD = np.longdouble
WRITER_VERSION = "fr38v2-references 1"
HASH_SEEDS_CHECKED = [0, 1, 4242]
SAFETY_FACTOR = 4
REQUIREMENT = 1e-11            # SPEC.md section 3: accuracy <= 1e-11 x scale for judged values
SPEC_REVISION = ("efb311fd: the tagged criteria fr38-v2-criteria-2026-11-24 (707014e4) with "
                 "AMENDMENT-2026-11-24.md and AMENDMENT-2-2026-11-24.md")

# step sizes (s): Gauss-Legendre primary, the tighter Gauss-Legendre solve, the GBS second
STEPS = {
    "AF": (1.0, 0.5, 2.0),
    "AN": (1.0, 0.5, 2.0),
    "B": (1.0, 0.5, 2.0),
    "C": (1.0, 0.5, 2.0),
    "D": (1.0, 0.5, 2.0),
    "invented": (4.0, 2.0, 8.0),
}

FATES = (("durable", "R", "R"), ("short_lived", "R_s", "Rs"))   # (fate, row, state prefix)
CLASSES5 = ("resyn", "pool0", "pre", "win", "post")


def _require_pinned_blas():
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        if os.environ.get(v) != "1":
            raise SystemExit(f"refused: {v} must be 1 (SPEC: BLAS pinned to one thread)")


def f64(x):
    """The nearest double of a long double, as a Python float."""
    return float(x)


def up(x):
    """A long-double error bound as a double that is not below it."""
    a = float(x)
    if LD(a) < x:
        a = float(np.nextafter(a, np.inf))
    return a


# --------------------------------------------------------------------------------------------
# Readouts from one method's states
# --------------------------------------------------------------------------------------------

def derive(world, st):
    """Every readout of READOUTS.md, and the plant-sizing extras, from a state array."""
    I, y0 = world.ix, world.y0
    full = y0[None, :, :] + st
    RT = Mo.RT_KJ

    def dv(n):
        return st[:, I[n], :]

    def fv(n):
        return full[:, I[n], :]

    o = {}
    o["n_N"], o["n_M"], o["n_Pi"] = fv("N"), fv("M"), fv("Pi")
    o["n_R"], o["n_R_s"] = fv("R"), fv("Rs")
    if world.store:
        o["n_Mx"] = fv("Mx")
    if world.arm == "B":
        for s in ("X", "A", "ATP", "ADP", "P"):
            o["n_" + s] = fv(s)
    o["H_tx_release"] = fv("H")
    C = [dv(f"C{j}") for j in range(1, 9)]
    for j in range(8):
        o[f"C_tx_{j + 1}"] = C[j]
    sumC = C[0] + C[1] + C[2] + C[3] + C[4] + C[5] + C[6] + C[7]
    held = world.held[None, :]
    o["E_tx"] = sumC + np.where(held, fv("H"), LD(0))
    W_tx = world.r * (C[1] + 2 * C[2] + 3 * C[3] + 4 * C[4] + 5 * C[5] + 6 * C[6] + 7 * C[7])
    o["W_tx"] = W_tx
    o["F_pol"] = fv("F")
    o["int_J_I_tx"], o["int_S_tx"], o["int_Q_tx"] = dv("iJI"), dv("iS"), dv("iQ")
    o["int_Q_tx_release_durable"] = dv("iQd")
    o["int_Q_tx_release_short_lived"] = dv("iQs")
    o["int_D_R"], o["int_D_R_s"] = dv("iDR"), dv("iDRs")
    o["H_tx"], o["H_deg_R"], o["H_deg_R_s"] = dv("Htx"), dv("HdegR"), dv("HdegRs")
    o["H_rel_tx_release_durable"] = dv("HrelD")
    o["H_rel_tx_release_short_lived"] = dv("HrelS")
    heats = ["H_tx", "H_deg_R", "H_deg_R_s", "H_rel_tx_release_durable",
             "H_rel_tx_release_short_lived"]
    if world.store:
        o["H_store"] = dv("Hstore")
        heats.append("H_store")
    if world.water:
        o["V"] = fv("V")
        o["H_water"] = dv("Hwater")
        o["W_bath"] = dv("Wbath")
        heats.append("H_water")
    if world.arm == "B":
        o["F_rib"] = fv("Frib")
        for chain, pre in (("tl", "Ctl"), ("tl_s", "Ctls")):
            Ct = [dv(f"{pre}{j}") for j in range(1, 9)]
            for j in range(8):
                o[f"C_{chain}_{j + 1}"] = Ct[j]
            o[f"E_{chain}"] = Ct[0] + Ct[1] + Ct[2] + Ct[3] + Ct[4] + Ct[5] + Ct[6] + Ct[7]
            o[f"W_{chain}"] = world.rtl * (Ct[1] + 2 * Ct[2] + 3 * Ct[3] + 4 * Ct[4]
                                           + 5 * Ct[5] + 6 * Ct[6] + 7 * Ct[7])
        o["int_J_I_tl"], o["int_S_tl"], o["int_Q_tl"] = dv("iJItl"), dv("iStl"), dv("iQtl")
        o["int_J_I_tl_s"], o["int_S_tl_s"] = dv("iJItls"), dv("iStls")
        o["int_Q_tl_s"] = dv("iQtls")
        o["int_D_P"], o["int_J_C"] = dv("iDP"), dv("iJC")
        o["H_tl"], o["H_deg_P"], o["H_rc"] = dv("Htl"), dv("HdegP"), dv("Hrc")
        heats += ["H_tl", "H_deg_P", "H_rc"]
    for fate, row, pre in FATES:
        o[f"label_{row}_pool0"] = fv(pre + "_pool0")
        for c in ("resyn", "pre", "win", "post"):
            o[f"label_{row}_{c}"] = dv(f"{pre}_{c}")
        o[f"released_present_gross_{fate}"] = (o[f"label_{row}_pre"] + o[f"label_{row}_win"]
                                               + o[f"label_{row}_post"])

    # G - G(0), LAWS.md section 5, in deviation form row by row
    if world.water:
        V = fv("V")
        lnV = np.log1p(dv("V") / world.V0)
    else:
        V = world.V0
        lnV = LD(0)
    g_rows = [("N", world.muN), ("M", world.muM), ("Pi", world.muPi), ("R", world.muR),
              ("Rs", world.muRs)]
    if world.store:
        g_rows.append(("Mx", world.muMx))
    if world.arm == "B":
        g_rows += [("A", world.muA), ("ATP", world.muATP), ("ADP", world.muADP), ("P", world.muP)]
    total = LD(0)
    scale_rows = LD(0)
    for name, mu0 in g_rows:
        n0 = y0[I[name]][None, :]
        dn = dv(name)
        n = n0 + dn
        lnc = np.log(n / (V * Mo.C_STD))
        total = total + (dn * (mu0 + lnc - 1) + n0 * (np.log1p(dn / n0) - lnV))
        moves = np.any(dn != 0, axis=0)[None, :] | (world.water)
        scale_rows = scale_rows + np.where(moves, n * RT * (abs(mu0) + np.abs(lnc) + 1), LD(0))
    if world.water:
        # K and Y: amounts constant, terms move by dilution (amendment 1, item 7); mu° = 0
        for n0 in (world.nK, world.nY):
            total = total + n0 * (-lnV)
            lnc = np.log(n0 / (V * Mo.C_STD))
            scale_rows = scale_rows + n0 * RT * (np.abs(lnc) + 1)
    hold_term = world.mures * (W_tx + world.L * dv("H"))
    res_scale = abs(world.mures) * (W_tx + world.L * fv("H"))
    if world.arm == "B":
        hold_term = hold_term + world.muresP * (o["W_tl"] + o["W_tl_s"])
        res_scale = res_scale + abs(world.muresP) * (o["W_tl"] + o["W_tl_s"])
    o["G_minus_G0"] = RT * (total + hold_term)

    x = {"heats": heats,
         "G_scale_rows": scale_rows,
         "G_scale_res": RT * res_scale,
         "G_hold_standard_term": RT * world.mures * world.L * dv("H")}
    heat_sum = LD(0)
    for h in heats:
        heat_sum = heat_sum + o[h]
    if world.water:
        heat_sum = heat_sum - o["W_bath"]
    x["G_identity"] = o["G_minus_G0"] + heat_sum
    abs_heats = LD(0)
    for h in heats:
        abs_heats = abs_heats + np.abs(o[h])
    if world.water:
        abs_heats = abs_heats + np.abs(o["W_bath"])
    x["heat_abs_sum"] = abs_heats
    if world.has_blank:
        x["excess_durable"] = dv("XR")
        x["excess_short_lived"] = dv("XRs")
    x["cohort_net_durable"] = dv("netR")
    x["cohort_net_short_lived"] = dv("netRs")
    if world.p3:
        x["P3a_durable"], x["P3a_short_lived"] = dv("p3aR"), dv("p3aRs")
        x["P3b_durable"], x["P3b_short_lived"] = dv("p3bR"), dv("p3bRs")
    x["P4_durable"], x["P4_short_lived"] = dv("KR"), dv("KRs")
    return o, x


def checks_of(world, st, o, x, r, times):
    """SPEC.md section 3, item 7 and 8: each check's largest residual, for row r."""
    I, y0 = world.ix, world.y0
    dv = lambda n: st[:, I[n], r]
    c = {}
    nmax = {}
    worst = LD(0)
    for fate, row, pre in FATES:
        s5 = sum(o[f"label_{row}_{k}"][:, r] for k in CLASSES5)
        nmax[fate] = np.max(np.abs(o[f"n_{row}"][:, r]))
        worst = max(worst, np.max(np.abs(s5 - o[f"n_{row}"][:, r])) / nmax[fate])
    c["membership_sum_largest_relative"] = f64(worst)
    held = bool(world.held[r])
    c["hold_identity_largest_fmol"] = f64(np.max(np.abs(dv("iQ") - dv("H") - dv("iQd")
                                                        - dv("iQs"))))
    c["producer_identity_largest_fmol"] = f64(np.max(np.abs(
        dv("iQ") - dv("H") - dv("R") - dv("Rs") - dv("iDR") - dv("iDRs"))))
    c["fate_row_identity_largest_fmol"] = f64(max(
        np.max(np.abs(dv("R") - dv("iQd") + dv("iDR"))),
        np.max(np.abs(dv("Rs") - dv("iQs") + dv("iDRs")))))
    sumC = sum(dv(f"C{j}") for j in range(1, 9))
    mach = dv("F") + sumC + (dv("H") if held else LD(0))
    c["machine_identity_largest_fmol"] = f64(np.max(np.abs(mach)))
    c["residue_identity_largest_fmol"] = f64(np.max(np.abs(
        world.r * dv("iS") - o["W_tx"][:, r] - world.L * dv("iQ"))))
    L = world.L
    W = o["W_tx"][:, r]
    phos = 3 * dv("N") + dv("M") + dv("Pi") + L * dv("R") + L * dv("Rs") + W + L * dv("H")
    nucl = dv("N") + dv("M") + L * dv("R") + L * dv("Rs") + W + L * dv("H")
    if world.store:
        phos = phos + dv("Mx")
        nucl = nucl + dv("Mx")
    if world.arm == "B":
        phos = phos + 3 * dv("ATP") + 2 * dv("ADP")
        aden = dv("ATP") + dv("ADP")
        amino = dv("A") + world.LP * dv("P") + o["W_tl"][:, r] + o["W_tl_s"][:, r]
        c["moiety_adenine_largest_fmol"] = f64(np.max(np.abs(aden)))
        c["moiety_amino_acid_largest_fmol"] = f64(np.max(np.abs(amino)))
        ribs = dv("Frib") + o["E_tl"][:, r] + o["E_tl_s"][:, r]
        c["ribosome_identity_largest_fmol"] = f64(np.max(np.abs(ribs)))
        c["residue_identity_tl_largest_fmol"] = f64(max(
            np.max(np.abs(world.rtl * dv("iStl") - o["W_tl"][:, r] - world.LP * dv("iQtl"))),
            np.max(np.abs(world.rtl * dv("iStls") - o["W_tl_s"][:, r]
                          - world.LP * dv("iQtls")))))
        c["product_P_identity_largest_fmol"] = f64(np.max(np.abs(
            dv("P") - dv("iQtl") - dv("iQtls") + dv("iDP"))))
    c["moiety_phosphorus_largest_fmol"] = f64(np.max(np.abs(phos)))
    c["moiety_nucleoside_largest_fmol"] = f64(np.max(np.abs(nucl)))
    c["G_identity_largest_pJ"] = f64(np.max(np.abs(x["G_identity"][:, r])))
    # item 8: pool0 against its closed form P(0) exp(-k t), in 50-digit decimal arithmetic
    worst_abs = Decimal(0)
    worst_rel = Decimal(0)
    with localcontext() as ctx:
        ctx.prec = 50
        for fate, row, pre in FATES:
            k = Decimal(float(world.kR[r] if fate == "durable" else world.kRs[r]))
            P0 = _exact_decimal(y0[I[pre + "_pool0"], r])
            for i, t in enumerate(times):
                exact = P0 * (-(k * Decimal(t))).exp()
                got = _exact_decimal(o[f"label_{row}_pool0"][i, r])
                worst_abs = max(worst_abs, abs(got - exact))
                worst_rel = max(worst_rel, abs(got - exact) / exact)
    c["pool0_closed_form_largest_fmol"] = float(worst_abs)
    c["pool0_closed_form_largest_relative"] = float(worst_rel)
    if world.has_blank and world.rows[r]["blank"] is not None:
        b = world.blank[r]
        e = max(np.max(np.abs(x["excess_durable"][:, r] - (o["n_R"][:, r] - o["n_R"][:, b]))),
                np.max(np.abs(x["excess_short_lived"][:, r]
                              - (o["n_R_s"][:, r] - o["n_R_s"][:, b]))))
        c["excess_route_vs_subtraction_largest_fmol"] = f64(e)
    return c


def _exact_decimal(v):
    """A long double's exact value as a Decimal (its significand and exponent)."""
    m, e = np.frexp(v)
    mi = int(np.ldexp(m, 64))
    return Decimal(mi) * (Decimal(2) ** (int(e) - 64))


# --------------------------------------------------------------------------------------------
# Classes (SPEC.md section 4 and amendment 1, item 2), from the model's structure
# --------------------------------------------------------------------------------------------

def run_kind(row):
    if row["is_blank"]:
        return "blank"
    return row["name"].split(" ")[0]


def idle_fate(row):
    k = run_kind(row)
    if k == "p=0":
        return "durable"
    if k == "p=1":
        return "short_lived"
    return None


BLANK_CONSTANT = {"H_tx_release", "int_Q_tx_release_durable", "int_Q_tx_release_short_lived",
                  "H_rel_tx_release_durable", "H_rel_tx_release_short_lived", "int_Q_tx",
                  "int_J_I_tx", "int_S_tx", "E_tx", "W_tx", "H_tx"} | {
    f"C_tx_{j}" for j in range(1, 9)}


def series_fate(name):
    if name.endswith("_durable") or name.startswith("label_R_") and not name.startswith(
            "label_R_s_"):
        return "durable"
    if name.endswith("_short_lived") or name.startswith("label_R_s_"):
        return "short_lived"
    return None


def classes_for(name, row, times, t1, t2):
    kind = run_kind(row)
    idle = idle_fate(row)
    fate = series_fate(name)
    is_ppw = name.split("_")[-1] in ("pre", "win", "post") and name.startswith("label_")
    is_gross = name.startswith("released_present_gross_")
    out = []
    for t in times:
        c = "stepped"
        if kind == "blank" and (name in BLANK_CONSTANT or is_ppw or is_gross):
            c = "constant"
        elif idle is not None and fate == idle and (
                name.startswith("int_Q_tx_release_") or name.startswith("H_rel_tx_release_")
                or is_ppw or is_gross):
            c = "constant"
        elif is_ppw:
            cls = name.split("_")[-1]
            if (cls == "win" and t <= t1) or (cls == "post" and t <= t2) or (
                    cls == "pre" and t == 0.0):
                c = "constant"
        elif is_gross and t == 0.0:
            c = "constant"
        out.append(c)
    return out


# --------------------------------------------------------------------------------------------
# The judged sets (READOUTS.md section 4)
# --------------------------------------------------------------------------------------------

def judged(world, name):
    if world.arm == "B":
        if name in ("H_tx_release", "int_Q_tx_release_durable", "int_Q_tx_release_short_lived",
                    "n_R", "n_R_s", "int_D_R", "int_D_R_s", "H_deg_R", "H_deg_R_s",
                    "H_rel_tx_release_durable", "H_rel_tx_release_short_lived"):
            return True
        return name.startswith("label_") or name.startswith("released_present_gross_")
    if name.startswith("C_tx_") or name == "W_tx":
        return False
    return True


# --------------------------------------------------------------------------------------------
# One family
# --------------------------------------------------------------------------------------------

def build_family(fam):
    name = fam["family"]
    world = Mo.World(fam)
    hp, ht, hs = STEPS[name]
    t_start = time.time()
    gp, gt, gs = In.Gauss(5), In.Gauss(5), In.GBS(8)
    st = {"p": In.integrate(world, gp, hp, grade_min_steps=4),
          "t": In.integrate(world, gt, ht, grade_min_steps=8),
          "s": In.integrate(world, gs, hs, grade_min_steps=4)}
    run_time = time.time() - t_start
    times = In.output_times(world)
    der = {k: derive(world, v) for k, v in st.items()}
    o, x = der["p"]
    inp = world.inp
    t1, t2 = float(world.t1), float(world.t2)
    samples = list(inp["samples_s"])
    ti = {t: i for i, t in enumerate(times)}

    # the domain (sheet 9.6; CRITERIA.md section 5): a fate row above 1 M, or a fate's loss
    # with y_f above X_DOM = -1, is refused, never repaired
    for k in ("p", "t", "s"):
        oo = der[k][0]
        if world.water:
            Vg = np.where(world.geneV0[None, :], world.V0, oo["V"])
        else:
            Vg = world.V0
        lnaM = np.log(oo["n_M"] / (Vg * Mo.C_STD))
        for row, mu in (("R", world.muR), ("R_s", world.muRs)):
            lna = np.log(oo[f"n_{row}"] / (Vg * Mo.C_STD))
            if not np.all(lna <= 0):
                raise SystemExit(f"refused: {row} above 1 M")
            y = world.muM + lnaM - (mu + lna) / world.L
            if not np.all(y <= -1):
                raise SystemExit(f"refused: y_f of {row} above X_DOM = -1")

    method_diff = {}
    tight_diff = {}
    runs = {}
    req_fail = []
    for r, row in enumerate(world.rows):
        if not row["publish"]:
            continue
        series = {}
        for qn in o:
            classes = classes_for(qn, row, times, t1, t2)
            vp, vt, vs = o[qn][:, r], der["t"][0][qn][:, r], der["s"][0][qn][:, r]
            scale = _scale(world, qn, o, x, r)
            ent = _series_entry(vp, vt, vs, classes, scale)
            series[qn] = ent
            _track(method_diff, qn, vp, vs, scale)
            _track(tight_diff, qn, vp, vt, scale)
            if judged(world, qn):
                _require(req_fail, row["name"], qn, ent["accuracy"], scale)
        run = {"series": series}
        run["checks"] = checks_of(world, st["p"], o, x, r, times)
        if not row["is_blank"]:
            run["survival"] = _survival(world, row, r, der, times, ti, samples, req_fail)
            run["route2"] = _route2(world, row, r, der, ti, samples, req_fail)
            run["not_compared"] = {f"cohort_net_{f}": [f64(v) for v in x[f"cohort_net_{f}"][:, r]]
                                   for f, _, _ in FATES}
            if row["blank"] is not None:
                b = world.blank[r]
                eob = {}
                for fate, rowname, _ in FATES:
                    key = f"excess_{fate}"
                    vp, vt, vs = x[key][:, r], der["t"][1][key][:, r], der["s"][1][key][:, r]
                    sc = np.max(o[f"n_{rowname}"][:, r] + o[f"n_{rowname}"][:, b])
                    ent = _series_entry(vp, vt, vs, ["stepped"] * len(times), sc)
                    eob[fate] = ent
                    _track(method_diff, "excess_over_blank_" + fate, vp, vs, sc)
                    _track(tight_diff, "excess_over_blank_" + fate, vp, vt, sc)
                    _require(req_fail, row["name"], "excess_over_blank_" + fate,
                             ent["accuracy"], sc)
                run["excess_over_blank"] = eob
        runs[row["name"]] = run
    if req_fail:
        raise SystemExit("refused: a judged accuracy exceeds its requirement: "
                         + "; ".join(req_fail[:10]))

    doc = {
        "kind": "cells.fr38_v2.reference@1",
        "family": name,
        "inputs": inp,
        "units": {"amount": "fmol", "energy": "pJ", "time": "s", "volume": "pL",
                  "copy_fmol": Wd.COPY_FMOL},
        "times_s": [float(t) for t in times],
        "samples_s": [float(t) for t in samples],
        "runs": runs,
        "plants": _plants(world, der, times, samples),
        "method": {
            "primary": gp.describe() + f"; step h = {hp} s",
            "tighter": gt.describe() + f"; step h = {ht} s (truncation error 2^10 = 1024 times "
                                       f"smaller than the primary's: at least 100 times tighter)",
            "second": gs.describe() + f"; macro step H = {hs} s",
            "tolerances": ("fixed steps that divide every span between restarts; the solve "
                           "restarts at every output time and every switch, and no output is "
                           "interpolated; the first output interval is graded, with restarts at "
                           "dt_out * 2^-k (k = 1..12) and at least 4 steps per piece (8 in the "
                           "refinement, 4 macro steps in the second method); numpy long double "
                           "(x86 80-bit extended, 64-bit significand), deviation-form state"),
            "safety_factor": float(SAFETY_FACTOR),
            "accuracy_rule": ("accuracy = safety_factor x max(|primary - tighter|, "
                              "|primary - second|) + |written double - primary|, rounded up"),
            "largest_difference_between_methods": method_diff,
            "largest_difference_primary_vs_tighter": tight_diff,
            "rhs_evaluations": {"primary": gp.rhs_calls, "tighter": gt.rhs_calls,
                                "second": gs.rhs_calls},
            "gauss_stage_iterations_max": max(gp.max_iterations_used, gt.max_iterations_used),
            "run_time_s": "out/run_times.json",
        },
        "provenance": _provenance(),
    }
    return doc, run_time


def _series_entry(vp, vt, vs, classes, scale):
    values, accs = [], []
    for i, c in enumerate(classes):
        if c == "constant":
            if not (vp[i] == 0 and vt[i] == 0 and vs[i] == 0):
                raise AssertionError("a constant entry is not exactly zero")
            values.append(0.0)
            accs.append(None)
        else:
            v = f64(vp[i])
            if not np.isfinite(v):
                raise AssertionError("non-finite value")
            err = SAFETY_FACTOR * max(abs(vp[i] - vt[i]), abs(vp[i] - vs[i])) + abs(LD(v) - vp[i])
            values.append(v)
            accs.append(up(err))
    return {"class": list(classes), "value": values, "accuracy": accs, "scale": f64(scale)}


def _scale(world, qn, o, x, r):
    if qn.startswith("label_") or qn.startswith("released_present_gross_"):
        row = "R_s" if (qn.startswith("label_R_s_") or qn.endswith("short_lived")) else "R"
        return np.max(np.abs(o[f"n_{row}"][:, r]))
    if qn in x["heats"] or qn == "W_bath":
        return np.max(x["heat_abs_sum"][:, r])
    if qn == "G_minus_G0":
        return (np.max(x["heat_abs_sum"][:, r]) + np.max(x["G_scale_rows"][:, r])
                + np.max(x["G_scale_res"][:, r]))
    return np.max(np.abs(o[qn][:, r]))


def _track(store, qn, va, vb, scale):
    d = np.max(np.abs(va - vb))
    rel = d / scale if scale > 0 else LD(0)
    cur = store.get(qn)
    if cur is None or d > LD(cur["absolute"]):
        store[qn] = {"absolute": up(d), "relative_to_scale": up(rel)}


def _require(fails, run, qn, accs, scale):
    lim = REQUIREMENT * float(scale)
    worst = max([a for a in accs if a is not None], default=0.0)
    if worst > lim:
        fails.append(f"{run} {qn}: {worst!r} > {lim!r}")


def _survival(world, row, r, der, times, ti, samples, fails):
    idle = idle_fate(row)
    t2 = float(world.t2)
    out = []
    for fate, rowname, _ in FATES:
        key = f"label_{rowname}_win"
        scale = np.max(np.abs(der["p"][0][f"n_{rowname}"][:, r]))
        for ts in samples:
            if ts <= t2:
                continue
            if fate == idle:
                out.append({"fate": fate, "t2_s": t2, "ts_s": float(ts), "alive_t2": 0.0,
                            "alive_ts": 0.0, "ratio": None, "accuracy": [None, None, None]})
                continue
            vals = {k: (der[k][0][key][ti[t2], r], der[k][0][key][ti[ts], r])
                    for k in ("p", "t", "s")}
            ratio = {k: vals[k][1] / vals[k][0] for k in vals}
            accs = []
            for idx in (0, 1):
                vp = vals["p"][idx]
                accs.append(up(SAFETY_FACTOR * max(abs(vp - vals["t"][idx]),
                                                   abs(vp - vals["s"][idx]))
                               + abs(LD(f64(vp)) - vp)))
            rp = ratio["p"]
            accs.append(up(SAFETY_FACTOR * max(abs(rp - ratio["t"]), abs(rp - ratio["s"]))
                           + abs(LD(f64(rp)) - rp)))
            for a, lim in ((accs[0], scale), (accs[1], scale), (accs[2], LD(1))):
                if a > REQUIREMENT * float(lim):
                    fails.append(f"{row['name']} survival {fate} {ts}")
            out.append({"fate": fate, "t2_s": t2, "ts_s": float(ts), "alive_t2": f64(vals["p"][0]),
                        "alive_ts": f64(vals["p"][1]), "ratio": f64(rp), "accuracy": accs})
    return out


def _route2(world, row, r, der, ti, samples, fails):
    idle = idle_fate(row)
    out = []
    for fate, rowname, _ in FATES:
        key = f"label_{rowname}_win"
        counter = der["p"][0][f"int_Q_tx_release_{fate}"][:, r]
        scale = f64(np.max(np.abs(counter)))
        for ts in samples:
            if fate == idle:
                out.append({"fate": fate, "ts_s": float(ts), "class": "constant", "value": 0.0,
                            "accuracy": None, "scale": scale})
                continue
            vp = der["p"][0][key][ti[ts], r]
            acc = up(SAFETY_FACTOR * max(abs(vp - der["t"][0][key][ti[ts], r]),
                                         abs(vp - der["s"][0][key][ti[ts], r]))
                     + abs(LD(f64(vp)) - vp))
            if acc > REQUIREMENT * scale:
                fails.append(f"{row['name']} route2 {fate} {ts}")
            out.append({"fate": fate, "ts_s": float(ts), "class": "stepped", "value": f64(vp),
                        "accuracy": acc, "scale": scale})
    return out


# --------------------------------------------------------------------------------------------
# The plants' predicted effects (SPEC.md section 6)
# --------------------------------------------------------------------------------------------

def _entry(plant, run, qn, times, honest, planted, scale, mask=None):
    d = np.abs(planted - honest)
    if mask is not None:
        d = np.where(mask, d, LD(-1))
    i = int(np.argmax(d))
    sc = LD(scale)
    return {"plant": plant, "run": run, "quantity": qn, "time_s": float(times[i]),
            "honest": f64(honest[i]), "planted": f64(planted[i]),
            "relative_distance": f64(abs(planted[i] - honest[i]) / sc) if sc > 0 else None,
            "scale": f64(sc)}


def known_rate(times, A, k, t1, t2, ts, idx):
    total = LD(0)
    for a, b in zip(idx[:-1], idx[1:]):
        ta, tb = times[a], times[b]
        if t1 <= ta < t2:
            h = LD(tb) - LD(ta)
            kh = k * h
            total = total + (A[b] - A[a]) * np.exp(-k * (LD(ts) - LD(tb))) * (-np.expm1(-kh)) / kh
    return total


def net_rate_form(times, A, D, n, t1, t2, ts):
    S = LD(0)
    for i in range(len(times) - 1):
        ta, tb = times[i], times[i + 1]
        if ta < t1:
            continue
        if tb > ts:
            break
        h = LD(tb) - LD(ta)
        ki = (D[i + 1] - D[i]) / ((n[i] + n[i + 1]) * h / 2)
        e = np.exp(-ki * h)
        if ta < t2:
            S = S * e + (A[i + 1] - A[i]) * (-np.expm1(-ki * h)) / (ki * h)
        else:
            S = S * e
    return S


def _plants(world, der, times, samples):
    o, x = der["p"]
    P = world.plants
    rows = world.rows
    ix = world.row_index
    t1, t2 = float(world.t1), float(world.t2)
    tarr = np.array(times)
    out = []

    def lscale(r, rowname):
        return np.max(np.abs(o[f"n_{rowname}"][:, r]))

    honest_runs = [i for i, rw in enumerate(rows) if rw["publish"] and not rw["is_blank"]]
    if "P1" in P:
        for r in honest_runs:
            for fate, rowname, _ in FATES:
                if idle_fate(rows[r]) == fate:
                    continue
                out.append(_entry("P1", rows[r]["name"], f"label_{rowname}_win", times,
                                  o[f"label_{rowname}_win"][:, r], x[f"cohort_net_{fate}"][:, r],
                                  lscale(r, rowname), mask=tarr > t1))
    if "P1p" in P:
        all_idx = list(range(len(times)))
        for r in honest_runs:
            for fate, rowname, _ in FATES:
                if idle_fate(rows[r]) == fate:
                    continue
                k = world.kR[r] if fate == "durable" else world.kRs[r]
                A = o[f"int_Q_tx_release_{fate}"][:, r]
                D = o[f"int_D_{rowname}"][:, r]
                n = o[f"n_{rowname}"][:, r]
                r2scale = np.max(np.abs(A))
                for ts in samples:
                    keep = {times.index(t1), times.index(t2), times.index(ts)}
                    coarse = sorted(set(all_idx[::2]) | keep)
                    g = abs(known_rate(times, A, k, t1, t2, ts, all_idx)
                            - known_rate(times, A, k, t1, t2, ts, coarse))
                    bound = 3 * g
                    honest = o[f"label_{rowname}_win"][times.index(ts), r]
                    planted = net_rate_form(times, A, D, n, t1, t2, ts)
                    dist = abs(planted - honest)
                    out.append({"plant": "P1′", "run": rows[r]["name"],
                                "quantity": f"route2_{fate}", "time_s": float(ts),
                                "honest": f64(honest), "planted": f64(planted),
                                "relative_distance": f64(dist / r2scale), "scale": f64(r2scale),
                                "route2_bound": f64(bound),
                                "distance_in_route2_bounds": f64(dist / bound)})
    if "P1pp" in P:
        for r in honest_runs:
            for fate, rowname, _ in FATES:
                if world.name in ("AF",) and idle_fate(rows[r]) != fate:
                    continue
                out.append(_entry("P1″", rows[r]["name"], f"released_present_gross_{fate}",
                                  times, o[f"released_present_gross_{fate}"][:, r],
                                  x[f"excess_{fate}"][:, r], lscale(r, rowname)))
    if "P2" in P:
        r = ix["p=1 returned"]
        q = ix[P["P2"]]
        for qn in ("int_Q_tx_release_short_lived", "H_rel_tx_release_short_lived",
                   "label_R_s_pre", "label_R_s_win", "label_R_s_post"):
            hon = o[qn][:, r]
            sc = _scale(world, qn, o, x, r)
            if sc == 0:
                sc = _scale(world, qn, o, x, q)     # the honest series is +0.0 throughout
            out.append(_entry("P2", "p=1 returned", qn, times, hon, o[qn][:, q], sc))
    for tag in ("P3a", "P3b"):
        if tag in P:
            r = ix["p_sched returned"]
            for fate, rowname, _ in FATES:
                out.append(_entry(tag, "p_sched returned", f"label_{rowname}_win", times,
                                  o[f"label_{rowname}_win"][:, r], x[f"{tag}_{fate}"][:, r],
                                  lscale(r, rowname)))
    if "P4" in P:
        r = ix["p_sched returned"] if world.arm == "A" else ix["p=0.55 returned"]
        for fate, rowname, _ in FATES:
            out.append(_entry("P4", rows[r]["name"], f"label_{rowname}_win", times,
                              o[f"label_{rowname}_win"][:, r], x[f"P4_{fate}"][:, r],
                              lscale(r, rowname)))
    if "P5" in P:
        r, q = ix["p_sched returned"], ix[P["P5"]]
        for qn in (["n_R_s", "int_D_R_s"] + [f"label_R_s_{c}" for c in CLASSES5]
                   + ["H_rel_tx_release_short_lived"]):
            out.append(_entry("P5", "p_sched returned", qn, times, o[qn][:, r], o[qn][:, q],
                              _scale(world, qn, o, x, r)))
    if "P6" in P:
        r = ix["p_sched returned"]
        out.append(_entry("P6", "p_sched returned", "G_minus_G0", times, o["G_minus_G0"][:, r],
                          o["G_minus_G0"][:, r] - x["G_hold_standard_term"][:, r],
                          _scale(world, "G_minus_G0", o, x, r)))
    if "P7" in P:
        r, q = ix["p_sched held"], ix["p_sched returned"]
        for qn in ("F_pol", "E_tx"):
            out.append(_entry("P7", "p_sched held", qn, times, o[qn][:, r], o[qn][:, q],
                              _scale(world, qn, o, x, r)))
    if "P8" in P:
        r, q = ix["p_sched returned"], ix[P["P8"]]
        for qn in ("n_M", "n_Mx"):
            out.append(_entry("P8", "p_sched returned", qn, times, o[qn][:, r], o[qn][:, q],
                              _scale(world, qn, o, x, r)))
        b = world.blank[r]
        for fate, rowname, _ in FATES:
            sc = np.max(o[f"n_{rowname}"][:, r] + o[f"n_{rowname}"][:, b])
            out.append(_entry("P8", "p_sched returned", f"excess_over_blank_{fate}", times,
                              x[f"excess_{fate}"][:, r], x[f"excess_{fate}"][:, q], sc))
        for rowname in ("R", "R_s"):
            for c in CLASSES5:
                qn = f"label_{rowname}_{c}"
                out.append(_entry("P8", "p_sched returned", qn, times, o[qn][:, r], o[qn][:, q],
                                  _scale(world, qn, o, x, r)))
    if "P9" in P:
        r, q = ix["p_sched returned"], ix[P["P9"]]
        qns = (["n_R", "n_R_s"] + [f"label_{rn}_{c}" for rn in ("R", "R_s") for c in CLASSES5]
               + ["H_rel_tx_release_durable", "H_rel_tx_release_short_lived", "G_minus_G0"])
        for qn in qns:
            out.append(_entry("P9", "p_sched returned", qn, times, o[qn][:, r], o[qn][:, q],
                              _scale(world, qn, o, x, r)))
    return out


# --------------------------------------------------------------------------------------------
# Provenance and the file
# --------------------------------------------------------------------------------------------

def _git(*args):
    here = os.path.dirname(os.path.abspath(__file__))
    return subprocess.run(["git", *args], cwd=here, capture_output=True, text=True,
                          check=True).stdout


def _provenance():
    try:
        rev = _git("rev-parse", "HEAD").strip()
        dirty = sorted(line[3:] for line in _git("status", "--porcelain=v1",
                                                 "--untracked-files=all").splitlines()
                       if line.strip())
    except (OSError, subprocess.CalledProcessError):
        rev, dirty = "unknown", ["git unavailable"]

    def ver(pkg):
        try:
            return importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            return "not installed"

    return {
        "revision": rev,
        "dirty_paths": dirty,
        "writer_version": WRITER_VERSION,
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "scipy": ver("scipy"),
        "mpmath": ver("mpmath") + "; Python's decimal module is used instead (lead's approval)",
        "platform": (f"{platform.machine()}; numpy long double = x86 80-bit extended precision, "
                     f"{np.finfo(LD).nmant + 1}-bit significand"),
        "blas_threads": {v: os.environ.get(v) for v in ("OMP_NUM_THREADS",
                                                        "OPENBLAS_NUM_THREADS",
                                                        "MKL_NUM_THREADS")},
        "spec": SPEC_REVISION,
        "sha256_of_this_file_excluded": True,
    }


def dumps(doc):
    """Sorted keys, fixed separators, repr floats: the bytes depend only on the values."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=True) + "\n"


def write_family(fam, out_dir):
    doc, run_time = build_family(fam)
    path = os.path.join(out_dir, f"reference_{fam['family']}.json")
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write(dumps(doc))
    return path, run_time


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--families", default="AF,AN,B,C,D,invented")
    a = ap.parse_args(argv)
    _require_pinned_blas()
    os.makedirs(a.out, exist_ok=True)
    times = {}
    for name in a.families.split(","):
        path, rt = write_family(Wd.family(name), a.out)
        times[name] = round(rt, 1)
        print(f"wrote {path} in {rt:.1f} s", flush=True)
    with open(os.path.join(a.out, "run_times.json"), "w", encoding="ascii") as fh:
        fh.write(json.dumps({"wall_time_s_per_family": times,
                             "note": "excluded from the bitwise check"}, sort_keys=True,
                            indent=1) + "\n")


if __name__ == "__main__":
    main()
