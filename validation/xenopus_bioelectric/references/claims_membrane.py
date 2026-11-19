"""Rows for C0-C5 and the membrane part of C7 (see DESIGN.md section 4)."""

from __future__ import annotations

from decimal import Decimal

from . import model as M
from .exact import dec, fmt, sign
from .rows import floor_closed, floor_root

TOL_V_ZERO = 1e-6        # C1/C2: 1e-6 V on the zero / crossing
TOL_V_C4 = 1e-5          # C4: 1e-5 V
BORROWED_V = "borrowed from C1's 1e-6 V (DESIGN.md gives C0 no tolerance: arithmetic)"
D = dec


def split_key(key):
    ionset, ext, t = key.split("|")
    return ionset, ext, t[1:]


def c0_c1_c2(R):
    R.family("C0.E_K", "C0", "Nernst potential of K", "V", "abs", TOL_V_ZERO, 0, BORROWED_V)
    R.family("C0.E_Na", "C0", "Nernst potential of Na", "V", "abs", TOL_V_ZERO, 0, BORROWED_V)
    R.family("C0.E_Cl", "C0", "Nernst potential of Cl (z = -1)", "V", "abs", TOL_V_ZERO, 0, BORROWED_V)
    for r, label in (("area", "area-weighted permeabilities (the declared patches; primary)"),
                     ("unit", "whole-membrane permeabilities without area weights (the reading that reproduces DESIGN.md's quoted -70.5 and -26.7 mV)")):
        R.family(f"C0.V_ghk_{r}", "C0", f"GHK zero-current voltage, {label}", "V", "abs", TOL_V_ZERO, 0, BORROWED_V,
                 note="alternative reading, labelled; the lead rules by dated note" if r == "unit" else "")
        R.family(f"C0.cl_effect_sign_{r}", "C0", f"sign of the voltage change of an open Cl- patch at V_rest ({r}): +1 depolarises (E_Cl > V_rest), -1 hyperpolarises", "1", "sign", TOL_V_ZERO, 0, BORROWED_V,
                 note="aux = E_Cl - V_rest (V); compared only when |aux| exceeds the band")
        R.family(f"C0.k_effect_sign_{r}", "C0", f"sign of the voltage change of an open K patch at V_rest ({r}): +1 depolarises (E_K > V_rest), -1 hyperpolarises", "1", "sign", TOL_V_ZERO, 0, BORROWED_V,
                 note="aux = E_K - V_rest (V); compared only when |aux| exceeds the band")
        R.family(f"C0.cl_bound_{r}", "C0", f"bound |E_Cl - V_rest| on any change by an open Cl- patch ({r})", "V", "abs", TOL_V_ZERO, 0, BORROWED_V)
        R.family(f"C0.cl_i_critical_{r}", "C0", f"Cl_i below which an open Cl- patch hyperpolarises at V_rest = Cl_o exp(F V_rest/RT) ({r})", "mM", "abs", 0, 1e-6, "borrowed: relative 1e-6")
        R.family(f"C0.feasible_19p4_{r}", "C0", f"is a hyperpolarisation of 19.4 mV (T2) allowed by the bound ({r}): V_rest - E_Cl >= 0.0194 V", "bool", "flag")
    for v in ("-0.01", "-0.03", "-0.05"):
        R.family(f"C0.cl_i_threshold_V{v}", "C0", f"Cl_i threshold Cl_o exp(F V/RT) at V = {v} V", "mM", "abs", 0, 1e-6, "borrowed: relative 1e-6")
    R.family("C1.zero_K", "C1", "zero of the K current of the K-only patch m_kleak (= E_K)", "V", "abs", TOL_V_ZERO, 0, "DESIGN C1: 1e-6 V on the zero")
    R.family("C1.zero_Cl", "C1", "zero of the Cl current of the Cl-only patch m_glycine (= E_Cl)", "V", "abs", TOL_V_ZERO, 0, "DESIGN C1: 1e-6 V on the zero")
    for ion in ("K", "Cl"):
        for d in ("-0.01", "-0.001", "0.001", "0.01"):
            R.family(f"C1.sign_I_{ion}_dV{d}", "C1", f"sign of the outward charge current of the {ion}-only patch at V = E_{ion} + {d} V (pos = positive charge leaves; for Cl the net Cl flux has the opposite sign)", "1", "sign", 1e-30, 0, "DESIGN C1: flux sign exact", note="aux = the current (A); m_glycine at P_GlyR 1e-8 m/s, availability 1")
    for u in ("-0.05", "-0.02", "0.02", "0.05", "0.1"):
        R.family(f"C1.kir_I_u{u}", "C1", f"Kir route current at u = V - E_K = {u} V (g_ref 1 S/m2, availability 1)", "A", "abs", 0, 1e-6, "proposed: relative 1e-6 (DESIGN.md gives no value for the current itself)")
        R.family(f"C1.kir_slope_u{u}", "C1", f"Kir slope conductance dI/dV at u = {u} V", "S", "abs", 0, 1e-6, "proposed: relative 1e-6")
    R.family("C1.kir_zero_at_EK", "C1", "Kir route current at V = E_K (zero for any parameters)", "A", "abs", 0, 0, "DESIGN C1: zero; the band is the float64 floor of u = V - E_K", note="reference 0")
    R.family("C1.kir_sqrtKo_ratio", "C1", "Kir current at fixed u = 0.02 V, local over bath = sqrt(K_o,local / K_o,bath)", "1", "abs", 0, 1e-9, "proposed: relative 1e-9")
    R.family("C2.V_ghk_area", "C2", "GHK zero-current voltage of the multi-ion membrane, area-weighted (primary)", "V", "abs", TOL_V_ZERO, 0, "DESIGN C2: 1e-6 V on the crossing")
    R.family("C2.V_ghk_unit", "C2", "GHK zero-current voltage, whole-membrane permeabilities (alternative reading)", "V", "abs", TOL_V_ZERO, 0, "DESIGN C2: 1e-6 V on the crossing")
    for d in ("-0.001", "0.001"):
        R.family(f"C2.sign_dVdt_dV{d}", "C2", f"sign of dV/dt (pump off, fixed amounts) at V = V_GHK + {d} V; dV/dt = -I_total/C_total", "1", "sign", 1e-30, 0, "DESIGN C2: crossing", note="aux = dV/dt (V/s)")

    for key in M.state_keys():
        ionset, ext, T = split_key(key)
        p = M.build(ionset, ext, T)
        pu = M.build(ionset, ext, T, weights="unit")
        EK, ENa, ECl = (M.E(i, p) for i in ("K", "Na", "Cl"))
        for ion, fam in (("K", "C0.E_K"), ("Na", "C0.E_Na"), ("Cl", "C0.E_Cl")):
            R.add(fam, key, M.E(ion, p), floor_closed(lambda q, i=ion: M.E(i, q), p))
        R.add("C1.zero_K", key, EK, floor_closed(lambda q: M.E("K", q), p))
        R.add("C1.zero_Cl", key, ECl, floor_closed(lambda q: M.E("Cl", q), p))
        for r, pp in (("area", p), ("unit", pu)):
            Vr = M.V_ghk(pp)
            fl = floor_closed(M.V_ghk, pp)
            R.add(f"C0.V_ghk_{r}", key, Vr, fl)
            R.add(f"C2.V_ghk_{r}", key, Vr, fl)
            dK = EK - Vr
            R.add(f"C0.k_effect_sign_{r}", key, sign(dK), aux=dK)
            R.floors[f"C0.k_effect_sign_{r}"][key] = float(floor_closed(lambda q: M.E("K", q) - M.V_ghk(q), pp))
            dE = ECl - Vr
            R.add(f"C0.cl_effect_sign_{r}", key, sign(dE), aux=dE)
            R.floors[f"C0.cl_effect_sign_{r}"][key] = float(floor_closed(lambda q: M.E("Cl", q) - M.V_ghk(q), pp))
            R.add(f"C0.cl_bound_{r}", key, abs(dE), floor_closed(lambda q: abs(M.E("Cl", q) - M.V_ghk(q)), pp))
            f = M.f_of(pp)
            R.add(f"C0.cl_i_critical_{r}", key, pp["cCl_o"] * (f * Vr).exp(), floor_closed(lambda q: q["cCl_o"] * (M.f_of(q) * M.V_ghk(q)).exp(), pp))
            R.add(f"C0.feasible_19p4_{r}", key, Vr - ECl >= D("0.0194"))
        for v in ("-0.01", "-0.03", "-0.05"):
            R.add(f"C0.cl_i_threshold_V{v}", key, p["cCl_o"] * (M.f_of(p) * D(v)).exp(),
                  floor_closed(lambda q: q["cCl_o"] * (M.f_of(q) * D(v)).exp(), p))
        # single-ion current signs (K on m_kleak; Cl on m_glycine, availability 1, P_GlyR 1e-8)
        pg = M.build(ionset, ext, T, aG=1)
        for ion, E0, pp, AP in (("K", EK, p, p["A_kleak"] * p["PK"]), ("Cl", ECl, pg, pg["A_gly"] * pg["P_gly"])):
            for d in ("-0.01", "-0.001", "0.001", "0.01"):
                I = M.ghk_I(AP, M.Z[ion], E0 + D(d), pp[f"c{ion}_i"], pp[f"c{ion}_o"], pp)
                R.add(f"C1.sign_I_{ion}_dV{d}", key, sign(I), aux=I)
                R.floors[f"C1.sign_I_{ion}_dV{d}"][key] = 0.0
        # the Kir route
        pk = M.build(ionset, ext, T, aK=1, g_ref=1)
        R.add("C1.kir_zero_at_EK", key, D(0), kir_zero_floor(pk))
        for u in ("-0.05", "-0.02", "0.02", "0.05", "0.1"):
            fI = lambda q, uu=D(u): M.kir_I(M.E("K", q) + uu, q)
            fg = lambda q, uu=D(u): M.kir_g(M.E("K", q) + uu, q)
            R.add(f"C1.kir_I_u{u}", key, fI(pk), floor_closed(fI, pk))
            R.add(f"C1.kir_slope_u{u}", key, fg(pk), floor_closed(fg, pk))
        # rectification relative to E_K: the u-dependence is independent of the compartment (tested via the ratio)
        if ext == "bath":
            pl = M.build(ionset, "local", T, aK=1, g_ref=1)
            u = D("0.02")
            fb = lambda q: M.kir_I(M.E("K", q) + u, q)
            Ib, Il = fb(pk), fb(pl)
            ratio = Il / Ib
            R.add("C1.kir_sqrtKo_ratio", f"{ionset}|T{T}", ratio,
                  ratio * (floor_closed(fb, pl) / abs(Il) + floor_closed(fb, pk) / abs(Ib)))
        # C2: dV/dt around the crossing
        Vr = M.V_ghk(p)
        for d in ("-0.001", "0.001"):
            dv = -M.I_total(Vr + D(d), p) / M.C_total(p)
            R.add(f"C2.sign_dVdt_dV{d}", key, sign(dv), aux=dv)
            R.floors[f"C2.sign_dVdt_dV{d}"][key] = 0.0


def kir_zero_floor(pk):
    """float64 floor of the Kir current at V = E_K: G u |E_K| g_kir (the uncertainty of u times the slope)."""
    from .exact import U64
    from .rows import G_OPS
    EK = M.E("K", pk)
    return G_OPS * U64 * abs(EK) * M.kir_g(EK, pk)


def _root_row(R, fam, key, p, root):
    fl = floor_root(lambda v, q: M.I_total(v, q), lambda v, q: M.g_total(v, q), root, p)
    R.add(fam, key, root, fl)


def c4(R):
    R.family("C4.V_zero_glycine", "C4", "zero-current voltage with the Cl- patch at availability a and P_GlyR (GHK, closed form)", "V", "abs", TOL_V_C4, 0, "DESIGN C4: 1e-5 V")
    R.family("C4.V_zero_kir", "C4", "zero-current voltage with the Kir route at availability a and g_ref (root of I_total = 0, leaks included)", "V", "abs", TOL_V_C4, 0, "DESIGN C4: 1e-5 V")
    R.family("C4.V_zero_both", "C4", "zero-current voltage with both the Kir route (g_ref 3, a 1) and the Cl- patch (P_GlyR 3e-8, a 1)", "V", "abs", TOL_V_C4, 0, "DESIGN C4: 1e-5 V")
    R.family("C4.shift_kir", "C4", "voltage shift of the Kir route, V_zero(a, g_ref) - V_GHK", "V", "abs", TOL_V_C4, 0, "DESIGN C4: 1e-5 V", note="most are far below the band: see effect_size in bands (zero power)")
    R.family("C4.shift_glycine_sign", "C4", "sign of the shift by the Cl- patch at availability 1: +1 depolarises", "1", "sign", TOL_V_C4, 0, "DESIGN C4", note="aux = shift (V)")
    R.family("C4.monotone_kir", "C4", "V_zero is monotone in the Kir availability (0, .25, .5, .75, 1) and moves toward E_K (true) at each g_ref", "bool", "flag")
    R.family("C4.monotone_glycine", "C4", "V_zero is monotone in the Cl- patch availability and moves toward E_Cl, never past it", "bool", "flag")
    R.family("C4.T1_reachable", "C4", "can the Kir route at g_ref 3 S/m2, availability 1 (the grid's largest) shift V_zero by -11 mV (T1's calibration target)", "bool", "flag", note="a derived conclusion about the declared grid, not an engine observable")
    R.family("C4.flux_at_a0", "C4", "ionic current of the Kir route and of the Cl- patch at availability 0, at V = -0.1, -0.04, 0.02 V", "A", "exact_zero", tol_source="DESIGN C4: exact zero flux at availability 0")
    for key in M.state_keys():
        ionset, ext, T = split_key(key)
        p0 = M.build(ionset, ext, T)
        V0 = M.V_ghk(p0)
        for P in M.P_GLYR_GRID:
            for a in ("0.5", "1"):
                p = M.build(ionset, ext, T, aG=a, P_gly=P)
                R.add("C4.V_zero_glycine", f"{key}|P{P}|a{a}", M.V_ghk(p), floor_closed(M.V_ghk, p))
        pg = M.build(ionset, ext, T, aG=1, P_gly="1e-8")
        dsh = M.V_ghk(pg) - V0
        R.add("C4.shift_glycine_sign", key, sign(dsh), aux=dsh)
        R.floors["C4.shift_glycine_sign"][key] = float(floor_closed(M.V_ghk, pg))
        # monotone toward E_Cl for all four P_GlyR
        ECl = M.E("Cl", p0)
        ok = True
        for P in M.P_GLYR_GRID:
            seq = [M.V_ghk(M.build(ionset, ext, T, aG=a, P_gly=P)) for a in M.AVAIL_FULL]
            d = [b - a for a, b in zip(seq, seq[1:])]
            tow = sign(ECl - V0)
            ok = ok and all(sign(x) == tow for x in d) and all((x - ECl) * tow <= 0 for x in seq)
        R.add("C4.monotone_glycine", key, ok)
        ok = True
        EK = M.E("K", p0)
        for g in M.G_REF_GRID:
            seq = []
            for a in M.AVAIL_FULL:
                p = M.build(ionset, ext, T, aK=a, g_ref=g)
                (root,) = M.V_zero(p)
                seq.append(root)
                if (g, a) == ("3", "1"):
                    R.add("C4.T1_reachable", key, root - V0 <= D("-0.011"))
                if a in ("0.25", "0.5", "1"):
                    _root_row(R, "C4.V_zero_kir", f"{key}|g{g}|a{a}", p, root)
                    R.add("C4.shift_kir", f"{key}|g{g}|a{a}", root - V0, R.floors["C4.V_zero_kir"][f"{key}|g{g}|a{a}"])
            d = [b - a for a, b in zip(seq, seq[1:])]
            ok = ok and all(x < 0 for x in d) and all(x >= EK for x in seq)
        R.add("C4.monotone_kir", key, ok)
        pb = M.build(ionset, ext, T, aK=1, g_ref=3, aG=1, P_gly="3e-8")
        (root,) = M.V_zero(pb)
        _root_row(R, "C4.V_zero_both", key, pb, root)
        pz = M.build(ionset, ext, T, aK=0, g_ref=3, aG=0, P_gly="3e-8")
        for V in ("-0.1", "-0.04", "0.02"):
            R.add("C4.flux_at_a0", f"{key}|V{V}", M.kir_I(D(V), pz) + M.ghk_I(pz["A_gly"] * pz["P_gly"] * pz["aG"], -1, D(V), pz["cCl_i"], pz["cCl_o"], pz))


def c3_scenarios():
    S = {
        "S1_leaks_bath": dict(ionset="primary", ext="bath", T="291.15"),
        "S2_glycine1e-8_bath": dict(ionset="primary", ext="bath", T="291.15", aG=1, P_gly="1e-8"),
        "S3_glycine3e-8_bath": dict(ionset="primary", ext="bath", T="291.15", aG=1, P_gly="3e-8"),
        "S4_glycine1e-8_bath70Na": dict(ionset="primary", ext="bath70_Na", T="291.15", aG=1, P_gly="1e-8"),
        "S5_glycine1e-8_bath70inert": dict(ionset="primary", ext="bath70_inert", T="291.15", aG=1, P_gly="1e-8"),
        "S6_kir3_bath": dict(ionset="primary", ext="bath", T="291.15", aK=1, g_ref=3),
        "S7_leaks_bath_Clhigh": dict(ionset="bracket_Cl_high", ext="bath", T="291.15"),
        "S8_leaks_bath_secondhand": dict(ionset="bracket_second_hand_table", ext="bath", T="291.15"),
        "S9_leaks_bath_T287": dict(ionset="primary", ext="bath", T="287.15"),
    }
    return S


DELTAS = ("0.002", "-0.002", "0.001")
C7_SCENARIOS = ("S1_leaks_bath", "S2_glycine1e-8_bath", "S4_glycine1e-8_bath70Na")


def c3_c7_relaxation(R, report):
    R.family("C3.V_inf", "C3", "zero-current voltage of the scenario", "V", "abs", TOL_V_ZERO, 0, "DESIGN C2/C3: 1e-6 V")
    R.family("C3.g", "C3", "slope conductance dI/dV at V_inf (analytic constant-field currents, Kir included)", "S", "abs", 0, 1e-6, "proposed: relative 1e-6")
    R.family("C3.tau_lin", "C3", "tau = C_total / g", "s", "abs", 0, 0.02, "DESIGN C3: tau within 2 %")
    R.family("C3.tau_fit", "C3", "tau fitted from the nonlinear step ODE (fixed amounts) at t = tau_lin: -tau_lin / ln(ratio), ratio = (V - V_inf)/(V_0 - V_inf)", "s", "abs", 0, 0.02, "DESIGN C3: tau within 2 %", note="the key's delta is the step V_0 - V_inf (V); the centre of the 2 % band for an engine fit of a 2 mV step")
    R.family("C3.ratio_t", "C3", "(V(t) - V_inf)/(V_0 - V_inf) from the fixed-amount nonlinear ODE at t = k tau_lin/4", "1", "abs", 0.0, 0.0, "DESIGN C3's 2 % on tau carried to the decay: tol_abs = 0.02 (t/tau) ratio per row")
    R.family("C3.ratio_exp", "C3", "the linear prediction exp(-t/tau_lin) at the same times", "1", "info")
    R.family("C3.tau_doubling", "C3", "tau(2 C_total)/tau(C_total) at fixed g", "1", "abs", 0.0, 0.02, "DESIGN C3: tau within 2 %")
    R.family("C3.Q_over_CV_error", "C3", "charge identity Q - C_total V at every observation", "C", "abs", 1e-9, 0, "DESIGN C3: charge identity 1e-9 C", note="reference 0; ZERO POWER: C_total x 100 mV = 7.9e-12 C is 100 times below the band")
    R.family("C3.drift_amounts", "C3", "|V(t) - V_inf| with amounts evolving minus with amounts fixed, relative to the step, at t = 4 tau_lin", "1", "info")
    R.family("C7.relax_ratio_t", "C7", "relaxation from V_0 = -0.04 V (the baseline): (V(t) - V_inf)/(V_0 - V_inf), amounts evolving, t = k tau_lin/4, pump off", "1", "info", note="information: C7 is a set of identities over records and DESIGN gives no tolerance for a trajectory; the lead rules")
    R.family("C7.relax_dn", "C7", "amount change of a species in the cell during that relaxation (fmol), t = k tau_lin/4; the bath is held", "fmol", "info", note="information: DESIGN gives no tolerance for a trajectory; the lead rules")
    R.family("C7.relax_charge_identity", "C7", "Q change C_total (V - V_0) minus CHARGE_PER_FMOL sum_i z_i dn_i (fmol of charge)", "fmol", "abs", 1e-9, 0, "DESIGN C7: 1e-9 (material/charge) ", note="reference 0")
    R.family("C7.relax_dQ", "C7", "ionic charge change of the cell C_total (V - V_0)", "C", "abs", 1e-9, 0, "DESIGN C7: 1e-9 C", note="ZERO POWER for any plant: |dQ| <= 3e-12 C")
    R.family("C7.relax_integrated_current", "C7", "integral of -I_total dt from 0 to t equals the charge change (by the ODE: identical)", "C", "info")
    for name, kw in c3_scenarios().items():
        p = M.build(kw["ionset"], kw["ext"], kw["T"], **{k: v for k, v in kw.items() if k not in ("ionset", "ext", "T")})
        (Vinf,) = M.V_zero(p)
        g = M.g_total(Vinf, p)
        tau = M.tau_lin(p, Vinf)
        resid = lambda v, q: M.I_total(v, q)
        R.add("C3.V_inf", name, Vinf, floor_root(resid, lambda v, q: M.g_total(v, q), Vinf, p))
        R.add("C3.g", name, g, floor_closed(lambda q: M.g_total(Vinf, q), p))
        R.add("C3.tau_lin", name, tau, floor_closed(lambda q: M.C_total(q) / M.g_total(Vinf, q), p))
        R.add("C3.tau_doubling", name, D(2))
        for dl in DELTAS:
            pts, errs = M.step_ode(p, Vinf + D(dl), Vinf, tau)
            ratios = [(v[0] - Vinf) / D(dl) for _, v in pts]
            for k, (t, v) in enumerate(pts):
                if k == 0:
                    continue
                R.add("C3.ratio_t", f"{name}|d{dl}|k{k}", ratios[k], D(0), tol_abs=D("0.02") * D(k) / 4 * abs(ratios[k]))
                if dl == "0.002":
                    R.add("C3.ratio_exp", f"{name}|d{dl}|k{k}", (-t / tau).exp())
                    R.add("C3.Q_over_CV_error", f"{name}|d{dl}|k{k}", D(0))
            r4 = ratios[4]
            R.add("C3.tau_fit", f"{name}|d{dl}", -tau / r4.ln(), D(0))
            report["ode_error_estimate"][f"C3|{name}|{dl}"] = max(float(e[0]) for e in errs) / float(abs(D(dl)))
        if name not in C7_SCENARIOS:
            continue
        # amounts evolving (the drift of the fixed-amount assumption)
        pts_a, errs_a = M.step_ode(p, Vinf + D("0.002"), Vinf, tau, with_amounts=True)
        pts_f, _ = M.step_ode(p, Vinf + D("0.002"), Vinf, tau)
        R.add("C3.drift_amounts", name, abs(pts_a[-1][1][0] - pts_f[-1][1][0]) / D("0.002"))
        # C7: relaxation from the baseline V0 = -0.04 V, amounts evolving, 6 tau
        V0 = D("-0.04")
        pts, errs = M.step_ode(p, V0, Vinf, tau, with_amounts=True, tau_span=6)
        Ct = M.C_total(p)
        cpf = p["F"] * D("1e-15")
        for k, (t, y) in enumerate(pts):
            if k == 0:
                continue
            key = f"{name}|k{k}"
            R.add("C7.relax_ratio_t", key, (y[0] - Vinf) / (V0 - Vinf), D(0))
            for i, ion in enumerate(M.IONS):
                R.add("C7.relax_dn", f"{key}|{ion}", y[1 + i], D(0))
            dq = Ct * (y[0] - V0)
            R.add("C7.relax_dQ", key, dq, D(0))
            ident = dq / cpf - sum(D(M.Z[ion]) * y[1 + i] for i, ion in enumerate(M.IONS))
            R.add("C7.relax_charge_identity", key, D(0))
            report["identity_residual"][key] = float(ident)
        report["ode_error_estimate"][f"C7|{name}"] = max(float(max(e)) for e in errs)
