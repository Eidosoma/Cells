"""Rows for C5, two coupled cells (and the supplementary asymmetric scenario C5x, outside DESIGN.md)."""

from __future__ import annotations

from decimal import Decimal

from . import model as M
from .exact import dec, find_roots, rk4_richardson
from .rows import floor_closed, floor_root

D = dec
MULT = ("1", "10", "100", "10000")


def cells_for(scn):
    """Parameters of cell 1 and cell 2 in each scenario."""
    base = dict(ionset="primary", ext="bath", T="291.15")
    if scn == "sym":
        return M.build(**base), M.build(**base)
    if scn.startswith("kir_g"):
        return M.build(**base), M.build(**base, aK=1, g_ref=scn[5:])
    if scn.startswith("x_gly"):          # supplementary: the Cl- patch open in cell 2 only
        return M.build(**base), M.build(**base, aG=1, P_gly=scn[5:])
    raise KeyError(scn)


SCENARIOS = ("sym", "kir_g0.1", "kir_g0.3", "kir_g1", "kir_g3", "x_gly1e-8", "x_gly3e-8")


def steady(p1, p2, gJ):
    """Steady voltages with the ohmic junction: Newton in 2D, cross-checked by a nested 1D root."""
    V1, V2 = M.V_ghk(p1), M.V_ghk(p2)
    for _ in range(80):
        Ij = gJ * (V1 - V2)
        r1, r2 = M.I_total(V1, p1) + Ij, M.I_total(V2, p2) - Ij
        a, b, c = M.g_total(V1, p1) + gJ, -gJ, M.g_total(V2, p2) + gJ
        det = a * c - b * b
        d1, d2 = (c * r1 - b * r2) / det, (a * r2 - b * r1) / det
        V1, V2 = V1 - d1, V2 - d2
        if max(abs(d1), abs(d2)) < Decimal("1e-52"):
            break
    # independent check: eliminate V2 and root-find in V1
    def f(v1):
        v2 = v1 + M.I_total(v1, p1) / gJ
        return M.I_total(v2, p2) + M.I_total(v1, p1)
    roots = find_roots(f, lambda v: (f(v + Decimal("1e-25")) - f(v - Decimal("1e-25"))) / Decimal("2e-25"),
                       min(V1, V2) - D("0.1"), max(V1, V2) + D("0.1"), 100)
    assert any(abs(r - V1) < Decimal("1e-30") for r in roots), (roots, V1)
    return V1, V2


def c5(R, report):
    tol_v = 1e-4
    R.family("C5.g_J", "C5", "junction conductance from permeabilities and mean concentrations (ohmic: equal cytosols)", "S", "abs", 0, 1e-6, "proposed: relative 1e-6")
    R.family("C5.g_m", "C5", "membrane slope conductance of the cell at its uncoupled zero-current voltage", "S", "abs", 0, 1e-6, "proposed: relative 1e-6")
    R.family("C5.tau_common", "C5", "common-mode time constant: sym C/g_m; others -1/lambda_slow of the 2x2 matrix", "s", "abs", 0, 0.03, "DESIGN C5: 3 % on tau")
    R.family("C5.tau_diff", "C5", "difference-mode time constant: sym C/(g_m + 2 g_J); others -1/lambda_fast of the 2x2 matrix", "s", "abs", 0, 0.03, "DESIGN C5: 3 % on tau")
    R.family("C5.V1_ss", "C5", "steady (zero-net-current, fixed amounts) voltage of cell 1", "V", "abs", tol_v, 0, "DESIGN C5: 0.1 mV on voltages")
    R.family("C5.V2_ss", "C5", "steady voltage of cell 2", "V", "abs", tol_v, 0, "DESIGN C5: 0.1 mV on voltages")
    R.family("C5.V_limit", "C5", "large-g_J limit: the root of I_1(V) + I_2(V) = 0 (conductance-weighted average, nonlinear)", "V", "abs", tol_v, 0, "DESIGN C5: 0.1 mV on voltages")
    R.family("C5.V_wavg_lin", "C5", "linear conductance-weighted average (g_1 V_1inf + g_2 V_2inf)/(g_1 + g_2)", "V", "info")
    R.family("C5.tau_fit_common", "C5", "tau of the common mode from the nonlinear two-cell ODE at t = tau_common (2 mV step along the common eigenvector)", "s", "abs", 0, 0.03, "DESIGN C5: 3 % on tau")
    R.family("C5.tau_fit_diff", "C5", "tau of the difference mode from the ODE at t = tau_diff", "s", "abs", 0, 0.03, "DESIGN C5: 3 % on tau")
    R.family("C5.V_dev_t", "C5", "(V_1, V_2) deviation from the steady state at t = k tau_common/4, common-mode start: V_n(t) - V_n,ss (V)", "V", "abs", tol_v, 0, "DESIGN C5: 0.1 mV on voltages")
    R.family("C5.junction_charge_sum", "C5", "sum over the two cells of the ionic charge change through the junction (identity)", "C", "abs", 1e-9, 0, "DESIGN C5/C7: 1e-9 C", note="reference 0; ZERO POWER")
    for scn in SCENARIOS:
        p1, p2 = cells_for(scn)
        c_mean = {i: (p1[f"c{i}_i"] + p2[f"c{i}_i"]) / 2 for i in M.IONS}
        gJ1 = M.junction_g(p1, c_mean)
        R.add("C5.g_J", scn, gJ1, floor_closed(lambda q: M.junction_g(q, c_mean), p1))
        Ct = M.C_total(p1)
        V1i, V2i = M.V_zero(p1)[0], M.V_zero(p2)[0]
        g1, g2 = M.g_total(V1i, p1), M.g_total(V2i, p2)
        R.add("C5.g_m", f"{scn}|cell1", g1, floor_closed(lambda q: M.g_total(V1i, q), p1))
        R.add("C5.g_m", f"{scn}|cell2", g2, floor_closed(lambda q: M.g_total(V2i, q), p2))
        resid = lambda v, q: M.I_total(v, q)
        dres = lambda v, q: M.g_total(v, q)
        fl_pair = max(floor_root(resid, dres, V1i, p1), floor_root(resid, dres, V2i, p2))
        for m in MULT:
            gJ = gJ1 * D(m)
            V1, V2 = steady(p1, p2, gJ)
            key = f"{scn}|x{m}"
            R.add("C5.V1_ss", key, V1, fl_pair)
            R.add("C5.V2_ss", key, V2, fl_pair)
            ga, gb = M.g_total(V1, p1), M.g_total(V2, p2)
            disc = ((ga - gb) ** 2 + 4 * gJ ** 2).sqrt()
            lam_slow = (-(ga + gb + 2 * gJ) + disc) / (2 * Ct)
            lam_fast = (-(ga + gb + 2 * gJ) - disc) / (2 * Ct)
            if scn == "sym" and m == "1":      # DESIGN's closed forms for identical cells
                assert abs(-1 / lam_slow - Ct / g1) < Decimal("1e-45") and abs(-1 / lam_fast - Ct / (g1 + 2 * gJ)) < Decimal("1e-45")
            R.add("C5.tau_common", key, -1 / lam_slow, 0)
            R.add("C5.tau_diff", key, -1 / lam_fast, 0)
        # the large-g_J limit
        rl = find_roots(lambda v: M.I_total(v, p1) + M.I_total(v, p2), lambda v: M.g_total(v, p1) + M.g_total(v, p2),
                        min(V1i, V2i) - D("0.05"), max(V1i, V2i) + D("0.05"), 60)
        assert len(rl) == 1
        R.add("C5.V_limit", scn, rl[0], fl_pair)
        R.add("C5.V_wavg_lin", scn, (g1 * V1i + g2 * V2i) / (g1 + g2))
        # time domain, declared junction only
        if scn in ("sym", "kir_g3", "x_gly3e-8"):
            gJ = gJ1
            V1s, V2s = steady(p1, p2, gJ)
            ga, gb = M.g_total(V1s, p1), M.g_total(V2s, p2)
            disc = ((ga - gb) ** 2 + 4 * gJ ** 2).sqrt()
            lams = {"common": (-(ga + gb + 2 * gJ) + disc) / (2 * Ct), "diff": (-(ga + gb + 2 * gJ) - disc) / (2 * Ct)}
            Mx = [[-(ga + gJ) / Ct, gJ / Ct], [gJ / Ct, -(gb + gJ) / Ct]]
            tau_c, tau_d = -1 / lams["common"], -1 / lams["diff"]
            rhs = lambda t, y: [-(M.I_total(y[0], p1) + gJ * (y[0] - y[1])) / Ct, -(M.I_total(y[1], p2) - gJ * (y[0] - y[1])) / Ct]
            for mode in ("common", "diff"):
                lam = lams[mode]
                v = (Mx[0][1], lam - Mx[0][0])                  # right eigenvector
                w = (Mx[1][0], lam - Mx[0][0])                  # left eigenvector
                sc = D("0.002") / max(abs(v[0]), abs(v[1]))
                d0 = [sc * v[0], sc * v[1]]
                tau_m = -1 / lam
                span = tau_c * 4
                h = min(tau_c / 40, tau_d / 8)
                steps = int((span / h).to_integral_value()) // 4 * 4
                if mode == "common":
                    rec = steps // 16
                    pts, errs = rk4_richardson(rhs, [V1s + d0[0], V2s + d0[1]], span, steps, rec)
                    for k, (t, y) in enumerate(pts):
                        if k:
                            R.add("C5.V_dev_t", f"{scn}|k{k}|cell1", y[0] - V1s, D(0))
                            R.add("C5.V_dev_t", f"{scn}|k{k}|cell2", y[1] - V2s, D(0))
                    report["ode_error_estimate"][f"C5|{scn}"] = max(float(max(e)) for e in errs)
                # time of projection: integrate to tau_m with the same step
                nsteps = max(8, int((tau_m / h).to_integral_value()) // 2 * 2)
                pts, _ = rk4_richardson(rhs, [V1s + d0[0], V2s + d0[1]], tau_m, nsteps, nsteps)
                yT = pts[-1][1]
                a0 = w[0] * d0[0] + w[1] * d0[1]
                aT = w[0] * (yT[0] - V1s) + w[1] * (yT[1] - V2s)
                R.add(f"C5.tau_fit_{mode}", scn, -tau_m / (aT / a0).ln(), 0)
        R.add("C5.junction_charge_sum", scn, D(0))
