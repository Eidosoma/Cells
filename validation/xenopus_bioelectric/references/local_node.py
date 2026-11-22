"""Rows for C8: (a) the bath against the local compartment, (b) the local node relaxing through the face.

Model of (b), primary ("bare"): the finite local node (10 pL, quasi-neutral) and the held bath joined by the
face. Each permeant ion's flux (local to bath) is the log-mean electrodiffusion flux

    J_i = (D_i A/L) [ (c_l,i - c_b,i) + z_i (F/RT) c_log,i psi ],   psi = phi_local - phi_bath,

and psi follows from zero net face current (the node stays electroneutral). A (36 mM) cannot cross the face
(D_A = 0), so the end state is a Donnan state with a potential, not the bath. At zero flux the log-mean law is
exactly c_l = c_b exp(-z F psi/RT), so the end state is analytic. Variants (information only): the constant-field
(GHK) flux in place of the log-mean one, and the cell coupled through its passive membrane.
"""

from __future__ import annotations

from decimal import Decimal

from . import model as M
from .exact import dec, find_roots, logmean, rk4_richardson, sign
from .rows import G_OPS, floor_closed
from .exact import U64

D = dec
IN = M.INPUTS
FACE = IN["face"]
IONS = M.IONS
VOL_L = D(IN["nodes"]["local"]["node"]["volume_pL"])
AMT_L = {k: D(v) for k, v in IN["nodes"]["local"]["node"]["initial_amount_fmol"].items()}
A_FIX = AMT_L["A"]
T_REF = "291.15"


def face_a():
    return {i: D(FACE["diffusivity_m2_per_s"][i]) * D(FACE["area_m2"]) / D(FACE["length_m"]) for i in IONS}


def psi_logmean(cl, cb, f, a, extra_current_over_F=D(0)):
    num = extra_current_over_F - sum(a[i] * D(M.Z[i]) * (cl[i] - cb[i]) for i in IONS)
    den = f * sum(a[i] * D(M.Z[i]) ** 2 * logmean(cl[i], cb[i]) for i in IONS)
    return num / den


def flux_logmean(cl, cb, f, a, psi):
    return {i: a[i] * ((cl[i] - cb[i]) + D(M.Z[i]) * f * logmean(cl[i], cb[i]) * psi) for i in IONS}


def flux_ghk(cl, cb, f, a, psi):
    out = {}
    for i in IONS:
        x = D(M.Z[i]) * f * psi
        out[i] = a[i] * ((cl[i] - cb[i]) if x == 0 else x * (cl[i] - cb[i] * (-x).exp()) / (1 - (-x).exp()))
    return out


def psi_ghk(cl, cb, f, a, guess):
    """Zero net face current with the GHK flux: secant from the log-mean value."""
    g = lambda ps: sum(D(M.Z[i]) * v for i, v in flux_ghk(cl, cb, f, a, ps).items())
    x0, x1 = guess, guess * D("1.01") + D("1e-6")
    f0, f1 = g(x0), g(x1)
    for _ in range(40):
        if f1 == f0:
            break
        x2 = x1 - f1 * (x1 - x0) / (f1 - f0)
        x0, f0, x1, f1 = x1, f1, x2, g(x2)
        if abs(x1 - x0) < D("1e-40"):
            break
    return x1


def donnan_final(cb, A_mM):
    """Electroneutral end state with the impermeant anion A trapped: x = exp(-F psi/RT), (Na+K) x - Cl/x = A."""
    cat = cb["Na"] + cb["K"]
    an = cb["Cl"]
    x = (A_mM + (A_mM ** 2 + 4 * cat * an).sqrt()) / (2 * cat)
    return x, {"Na": cb["Na"] * x, "K": cb["K"] * x, "Cl": cb["Cl"] / x}


def run_bare(flux="logmean", h_div=1, t_end=D(64), rec=D("0.5")):
    p = M.build("primary", "bath", T_REF)
    f = M.f_of(p)
    a = face_a()
    cb = M.exterior_mM("bath")
    n0 = [AMT_L[i] for i in IONS]

    def rhs(t, y):
        cl = {i: y[k] / VOL_L for k, i in enumerate(IONS)}
        ps = psi_logmean(cl, cb, f, a)
        J = flux_logmean(cl, cb, f, a, ps) if flux == "logmean" else flux_ghk(cl, cb, f, a, psi_ghk(cl, cb, f, a, ps))
        return [-J[i] * D("1e15") for i in IONS]
    steps = int(t_end / D("0.05")) // h_div
    per_rec = int((rec / (t_end / steps)).to_integral_value())
    return rk4_richardson(rhs, n0, t_end, steps, per_rec), f, a, cb


def run_coupled(t_end=D(64), rec=D("0.5")):
    pm = M.build("primary", "local", T_REF)       # the cell facing the local node's composition
    f = M.f_of(pm)
    a = face_a()
    cb = M.exterior_mM("bath")
    ap = M.perm_products(pm)
    Ct = M.C_total(pm)
    vol_c = D(IN["geometry"]["volume_pL"])
    y0 = [AMT_L[i] for i in IONS] + [D(IN["nodes"]["cell"]["initial_amount_fmol"][i]) for i in IONS] + [M.V_ghk(pm)]

    def rhs(t, y):
        cl = {i: y[k] / VOL_L for k, i in enumerate(IONS)}
        cc = {i: y[3 + k] / vol_c for k, i in enumerate(IONS)}
        Vm = y[6]
        Ii = {i: M.ghk_I(ap[i], M.Z[i], Vm, cc[i], cl[i], pm) for i in IONS}
        Im = sum(Ii.values())
        ps = psi_logmean(cl, cb, f, a, Im / pm["F"])
        J = flux_logmean(cl, cb, f, a, ps)
        dl = [(Ii[i] / (D(M.Z[i]) * pm["F"]) - J[i]) * D("1e15") for i in IONS]
        dc = [-Ii[i] / (D(M.Z[i]) * pm["F"]) * D("1e15") for i in IONS]
        return dl + dc + [-Im / Ct]
    steps = int(t_end / D("0.025"))
    per_rec = int((rec / (t_end / steps)).to_integral_value())
    return rk4_richardson(rhs, y0, t_end, steps, per_rec), f, a, cb


def t_e(times, vals, v0, vf):
    """First time the deviation ratio (v - vf)/(v0 - vf) falls to 1/e: quadratic interpolation."""
    target = D(1) / D(1).exp()
    r = [(v - vf) / (v0 - vf) for v in vals]
    for k in range(1, len(r)):
        if r[k] <= target < r[k - 1] or r[k] < target <= r[k - 1]:
            j = min(max(k - 1, 0), len(r) - 3)
            t0, t1, t2 = times[j], times[j + 1], times[j + 2]
            r0, r1, r2 = r[j], r[j + 1], r[j + 2]
            # Newton on the Lagrange quadratic from the linear estimate
            tt = times[k - 1] + (target - r[k - 1]) * (times[k] - times[k - 1]) / (r[k] - r[k - 1])
            for _ in range(30):
                L = lambda t: (r0 * (t - t1) * (t - t2) / ((t0 - t1) * (t0 - t2)) + r1 * (t - t0) * (t - t2) / ((t1 - t0) * (t1 - t2))
                               + r2 * (t - t0) * (t - t1) / ((t2 - t0) * (t2 - t1)))
                dL = (L(tt + D("1e-20")) - L(tt - D("1e-20"))) / D("2e-20")
                dt_ = (L(tt) - target) / dL
                tt -= dt_
                if abs(dt_) < D("1e-40"):
                    break
            return tt
    raise AssertionError("no 1/e crossing")


def c8(R, report):
    R.family("C8.a_dE_K", "C8", "E_K(local) - E_K(bath) (each membrane uses its own compartment)", "V", "abs", 1e-6, 0, "DESIGN C8a: analytic; 1e-6 V borrowed from C1")
    R.family("C8.a_dV_ghk_area", "C8", "V_GHK(local) - V_GHK(bath), area-weighted (primary)", "V", "abs", 1e-6, 0, "DESIGN C8a: analytic; 1e-6 V borrowed from C2")
    R.family("C8.a_dV_ghk_unit", "C8", "V_GHK(local) - V_GHK(bath), whole-membrane permeabilities (alternative reading)", "V", "abs", 1e-6, 0, "DESIGN C8a: analytic; 1e-6 V borrowed from C2")
    R.family("C8.a_cl_sign_bath_vs_local", "C8", "sign of the Cl- patch's effect at V_rest in the bath minus that in the local node as a pair (sign_bath, sign_local), area-weighted: +1 depolarises", "1", "sign", 1e-6, 0, "DESIGN C8a", note="aux = E_Cl - V_rest (V)")
    R.family("C8.b_tau_single", "C8", "tau = V_loc L/(D A) for one ion without a field (needs a single-species world; the declared mixture relaxes in about 4.9 s)", "s", "info", note="DESIGN's 'about 8 s for Na'; the mixture's rows are C8.b_t_e")
    R.family("C8.b_tau_ambipolar", "C8", "tau = V_loc L/(D_amb A), D_amb = 2 D+ D-/(D+ + D-): a neutral 1:1 salt alone in the node (needs a single-salt world)", "s", "info", note="the declared mixture's rows are C8.b_t_e")
    R.family("C8.b_final_c", "C8", "end state of the local node: Donnan equilibrium with the trapped A (36 mM)", "mM", "abs", 0, 1e-6, "proposed: relative 1e-6")
    R.family("C8.b_final_psi", "C8", "end potential of the local node against the bath (Donnan)", "V", "abs", 1e-6, 0, "proposed: 1e-6 V")
    R.family("C8.b_final_is_bath", "C8", "the end state equals the bath within 1 %", "bool", "flag", note="DESIGN C8b says 'the final state is the bath'; the trapped A makes it false (REFERENCES: an ambiguity reported)")
    R.family("C8.b_t_e", "C8", "time for the deviation of the species' concentration from its end state to fall to 1/e (bare node, log-mean flux)", "s", "info", note="information only: the bare node and face (DESIGN erratum 15:46 UTC, item 2)")
    R.family("C8.b_c_t", "C8", "concentration (mM) at t (bare node, log-mean flux)", "mM", "info", note="information only (erratum item 2)")
    R.family("C8.b_psi_t", "C8", "node potential against the bath (V) at t", "V", "info", note="information only (erratum item 2)")
    R.family("C8.bc_t_e", "C8", "t_1/e as C8.b_t_e, with the cell coupled through its passive membrane (the preparation P1LB has a cell); the compared reading for P1LB (erratum item 2)", "s", "abs", 0, 0.05, "DESIGN C8b: 5 % on the time constant")
    R.family("C8.bc_c_t", "C8", "concentration (mM) at t, cell coupled", "mM", "abs", 0, 0.05, "proposed: relative 5 %")
    R.family("C8.bc_psi_t", "C8", "node potential against the bath (V) at t, cell coupled", "V", "abs", 1e-3, 0, "proposed: 1 mV")
    R.family("C8.b_variant_ghk_t_e", "C8", "t_1/e with the constant-field flux in place of the log-mean one (model spread)", "s", "info")
    for ionset in M.ION_SETS:
        for T in M.TEMPERATURES:
            kb, kl = f"{ionset}|bath|T{T}", f"{ionset}|local|T{T}"
            pb, pl = M.build(ionset, "bath", T), M.build(ionset, "local", T)
            R.add("C8.a_dE_K", f"{ionset}|T{T}", M.E("K", pl) - M.E("K", pb), floor_closed(lambda q: M.E("K", q), pl) + floor_closed(lambda q: M.E("K", q), pb))
            for r in ("area", "unit"):
                ql, qb = M.build(ionset, "local", T, weights=r), M.build(ionset, "bath", T, weights=r)
                R.add(f"C8.a_dV_ghk_{r}", f"{ionset}|T{T}", M.V_ghk(ql) - M.V_ghk(qb), floor_closed(M.V_ghk, ql) + floor_closed(M.V_ghk, qb))
            for nm, pp in (("bath", pb), ("local", pl)):
                dE = M.E("Cl", pp) - M.V_ghk(pp)
                R.add("C8.a_cl_sign_bath_vs_local", f"{ionset}|T{T}|{nm}", sign(dE), aux=dE)
                R.floors["C8.a_cl_sign_bath_vs_local"][f"{ionset}|T{T}|{nm}"] = float(floor_closed(lambda q: M.E("Cl", q) - M.V_ghk(q), pp))
    a = face_a()
    for i in IONS:
        R.add("C8.b_tau_single", i, VOL_L * D("1e-15") / a[i])
    Dm = {i: D(FACE["diffusivity_m2_per_s"][i]) for i in IONS}
    for pair in (("Na", "Cl"), ("K", "Cl")):
        Dp, Dn = Dm[pair[0]], Dm[pair[1]]
        Damb = 2 * Dp * Dn / (Dp + Dn)
        tau = VOL_L * D("1e-15") * D(FACE["length_m"]) / (Damb * D(FACE["area_m2"]))
        R.add("C8.b_tau_ambipolar", "".join(pair), tau)
    cb = M.exterior_mM("bath")
    x, cf = donnan_final(cb, A_FIX / VOL_L)
    p = M.build("primary", "bath", T_REF)
    psi_f = -(x.ln()) / M.f_of(p)
    for i in IONS:
        R.add("C8.b_final_c", i, cf[i], G_OPS * U64 * cf[i])
    R.add("C8.b_final_psi", "psi", psi_f, G_OPS * U64 * abs(psi_f))
    R.add("C8.b_final_is_bath", "bath", all(abs(cf[i] / cb[i] - 1) < D("0.01") for i in IONS))
    report["donnan_x"] = float(x)
    # relaxation, bare, log-mean
    (pts, errs), f, a, cb = run_bare()
    times = [t for t, _ in pts]
    y_series = {i: [y[k] / VOL_L for _, y in pts] for k, i in enumerate(IONS)}
    c0 = {i: AMT_L[i] / VOL_L for i in IONS}
    report["ode_error_estimate"]["C8_bare_max_amount_fmol"] = float(max(max(e) for e in errs))
    for i in IONS:
        te = t_e(times, y_series[i], c0[i], cf[i])
        R.add("C8.b_t_e", i, te, 0)
    for k, t in enumerate(times):
        if t in (D(1), D(2), D(4), D(8), D(16), D(32), D(64)):
            cl = {i: y_series[i][k] for i in IONS}
            for i in IONS:
                R.add("C8.b_c_t", f"{i}|t{int(t)}", cl[i], G_OPS * U64 * cl[i])
            ps = psi_logmean(cl, cb, f, a)
            R.add("C8.b_psi_t", f"t{int(t)}", ps, G_OPS * U64 * abs(ps))
    # variants (information)
    (ptsg, _), _, _, _ = run_bare(flux="ghk", h_div=2)
    (ptsc, errsc), fc, ac, _ = run_coupled()
    report["ode_error_estimate"]["C8_coupled_max_amount_fmol"] = float(max(max(e[:3]) for e in errsc))
    tg = [t for t, _ in ptsg]
    tc = [t for t, _ in ptsc]
    for i, k in zip(IONS, range(3)):
        R.add("C8.b_variant_ghk_t_e", i, t_e(tg, [y[k] / VOL_L for _, y in ptsg], c0[i], cf[i]))
        R.add("C8.bc_t_e", i, t_e(tc, [y[k] / VOL_L for _, y in ptsc], c0[i], cf[i]), 0)
    # the coupled node's end state is the Donnan state only while the cell stays put; the t_1/e above refer to the bare Donnan state
    for k, t in enumerate(tc):
        if t in (D(1), D(2), D(4), D(8), D(16), D(32), D(64)):
            cl = {i: ptsc[k][1][j] / VOL_L for j, i in enumerate(IONS)}
            for i in IONS:
                R.add("C8.bc_c_t", f"{i}|t{int(t)}", cl[i])
            Vm = ptsc[k][1][6]
            pm = M.build("primary", "local", T_REF)
            cc = {i: ptsc[k][1][3 + j] / D(IN["geometry"]["volume_pL"]) for j, i in enumerate(IONS)}
            Im = sum(M.ghk_I(M.perm_products(pm)[i], M.Z[i], Vm, cc[i], cl[i], pm) for i in IONS)
            R.add("C8.bc_psi_t", f"t{int(t)}", psi_logmean(cl, cb, fc, ac, Im / pm["F"]))
