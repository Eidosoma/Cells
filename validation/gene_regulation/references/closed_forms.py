"""The sheet's closed forms (§5.1, §5.2), in decimal arithmetic at a chosen precision.

- A1's phase-1 limit (§5.1): every factor frozen at A1's initial state, machines abundant. The
  whole state y = (C_tx,1..m, n_R, C_tl,1..m, n_P) obeys ẏ = A y + b, solved exactly as
  y(t) = e^(At)(y(0) + A⁻¹b) − A⁻¹b, with e^(At) by scaling and squaring of its Taylor series.
  n_R(t) and E_tx(t) are also evaluated by the sheet's scalar formulas through
  P(j, y) = 1 − e^(−y) Σ_{i<j} y^i/i!, as an independent check of the matrix route.
- A1-M's steady state (§5.2): J*_g = λ_g M/(1 + Σ_h λ_h τ₀,h), E*_g = J*_g τ₀,g,
  F* = M/(1 + Σ_h λ_h τ₀,h), with τ₀ frozen at the world's start.

Everything is in fmol, s and fmol/s. The standard library's decimal module is used (no mpmath in
the environment); the precision is a parameter, and the references compare two precisions.
"""

from __future__ import annotations

from decimal import Decimal as D
from decimal import localcontext

from . import sheet


def _c(text) -> D:
    return D(str(text))


class Frozen:
    """The constants and the initial-state factors, at the context's precision."""

    def __init__(self, pot: sheet.Potentials):
        a = sheet.A1
        NA = D(sheet.N_A)
        self.RT = NA * D(sheet.K_B) * D(sheet.T_KELVIN) / 1000
        self.V = _c(a["V"])
        self.fmol_per_copy = D(10) ** 15 / NA
        self.c1 = self.fmol_per_copy / self.V
        g = _c(pot.G_ATP) / self.RT
        self.mu0 = {"ADP": D(0), "Pi": D(0), "M": D(0), "A": D(0)}
        self.mu0["ATP"] = self.mu0["ADP"] + self.mu0["Pi"] - g
        self.mu0["N"] = _c(pot.E_rc_RT) + self.mu0["M"] + 2 * self.mu0["ATP"] - 2 * self.mu0["ADP"]
        self.mu0["R_res"] = self.mu0["M"] - _c(pot.E_pd) / self.RT
        self.mu0["P_res"] = self.mu0["A"] - _c(pot.E_pep) / self.RT

    def lna(self, c_mM) -> D:
        return (_c(c_mM) / sheet.C_STANDARD_mM).ln()

    def x_tx(self, c: dict) -> D:
        m = self.mu0
        return m["R_res"] + 2 * (m["Pi"] + self.lna(c["Pi"])) - (m["N"] + self.lna(c["N"]))

    def x_tl(self, c: dict) -> D:
        m = self.mu0
        return (m["P_res"] + 4 * (m["ADP"] + self.lna(c["ADP"])) + 4 * (m["Pi"] + self.lna(c["Pi"]))
                - (m["A"] + self.lna(c["A"])) - 4 * (m["ATP"] + self.lna(c["ATP"])))

    def y_deg(self, L: int, monomer: str, residue: str, c_mono, c_poly) -> D:
        """ΔG_deg/(L RT) per residue: (L μ_monomer − μ_polymer)/L."""
        m = self.mu0
        return (L * (m[monomer] + self.lna(c_mono)) - (L * m[residue] + self.lna(c_poly))) / L

    @staticmethod
    def sat(c, K) -> D:
        return _c(c) / (_c(K) + _c(c))


def _expm(A: list, prec: int) -> list:
    """e^A for a small decimal matrix: Taylor series of A/2^s, then s squarings."""
    n = len(A)
    norm = max(sum(abs(x) for x in row) for row in A)
    s = 0
    while norm > D("0.5"):
        norm /= 2
        s += 1
    scale = D(2) ** s
    B = [[x / scale for x in row] for row in A]
    E = [[D(1) if i == j else D(0) for j in range(n)] for i in range(n)]
    T = [row[:] for row in E]
    eps = D(10) ** (-(prec + 5))
    k = 0
    while True:
        k += 1
        T = [[sum(T[i][q] * B[q][j] for q in range(n)) / k for j in range(n)] for i in range(n)]
        E = [[E[i][j] + T[i][j] for j in range(n)] for i in range(n)]
        if max(abs(x) for row in T for x in row) < eps:
            break
    for _ in range(s):
        E = [[sum(E[i][q] * E[q][j] for q in range(n)) for j in range(n)] for i in range(n)]
    return E


def _P(j: int, y: D) -> D:
    """The regularized lower incomplete gamma function at integer j (§5.1)."""
    term, total = D(1), D(0)
    for i in range(j):
        if i:
            term = term * y / i
        total += term
    return 1 - (-y).exp() * total


def a1_limit(pot: sheet.Potentials, times: list, prec: int = 50) -> dict:
    """A1's phase-1 limit at the given times (s), as decimal strings and steady states."""
    a = sheet.A1
    with localcontext() as ctx:
        ctx.prec = prec
        f = Frozen(pot)
        c = {s: a["c_" + s] for s in ("N", "M", "A", "ATP", "ADP", "Pi", "R", "P")}
        x_tx, x_tl = f.x_tx(c), f.x_tl(c)
        y_R = f.y_deg(a["L_R"], "M", "R_res", c["M"], c["R"])
        y_P = f.y_deg(a["L_P"], "A", "P_res", c["A"], c["P"])
        phi_tx = f.sat(c["N"], a["K_N_tx"]) * (1 - x_tx.exp())
        phi_tl = f.sat(c["A"], a["K_A_tl"]) * f.sat(c["ATP"], a["K_ATP_tl"]) * (1 - x_tl.exp())
        m_tx, m_tl = a["m_tx"], a["m_tl"]
        r_tx, r_tl = a["L_R"] // m_tx, a["L_P"] // m_tl
        k_tx = _c(a["v_tx"]) / r_tx * phi_tx
        k_tl = _c(a["v_tl"]) / r_tl * phi_tl
        k0_R = _c(a["k_R"]) * (1 - y_R.exp())
        k0_P = _c(a["k_P"]) * (1 - y_P.exp())
        cX, KX, nX, bX = _c(a["c_X"]), _c(a["K_X"]), a["n_X"], _c(a["b_X"])
        u1 = bX + (1 - bX) * cX ** nX / (KX ** nX + cX ** nX)
        lam_tx = u1 * _c(a["k_I_tx"]) * f.c1 * a["T_copies"]
        J = lam_tx * _c(a["M_pol"]) * f.fmol_per_copy  # J^I_tx = λ_tx M_pol, fmol/s
        beta = _c(a["k_I_tl"]) * _c(a["M_rib"]) * f.c1  # s⁻¹
        n = m_tx + 1 + m_tl + 1
        iR, iP = m_tx, n - 1
        A = [[D(0)] * n for _ in range(n)]
        for j in range(m_tx):
            A[j][j] = -k_tx
            if j:
                A[j][j - 1] = k_tx
        A[iR][m_tx - 1], A[iR][iR] = k_tx, -k0_R
        A[iR + 1][iR] = beta
        for j in range(m_tl):
            A[iR + 1 + j][iR + 1 + j] = -k_tl
            if j:
                A[iR + 1 + j][iR + j] = k_tl
        A[iP][iP - 1], A[iP][iP] = k_tl, -k0_P
        b = [D(0)] * n
        b[0] = J
        # A is lower triangular: A⁻¹b by forward substitution.
        Ainvb = [D(0)] * n
        for i in range(n):
            Ainvb[i] = (b[i] - sum(A[i][q] * Ainvb[q] for q in range(i))) / A[i][i]
        y0 = [D(0)] * n
        y0[iR] = _c(a["c_R"]) * f.V
        y0[iP] = _c(a["c_P"]) * f.V
        steps = [_c(t) for t in times]
        dts = {steps[k + 1] - steps[k] for k in range(len(steps) - 1)}
        if len(dts) != 1 or steps[0] != 0:
            raise ValueError("a1_limit expects a uniform grid from 0")
        dt = dts.pop()
        E = _expm([[x * dt for x in row] for row in A], prec)
        z = [y0[i] + Ainvb[i] for i in range(n)]
        out = {"n_R": [], "n_P": [], "E_tx": [], "E_tl": [], "n_R_scalar": [], "E_tx_scalar": []}
        for k, t in enumerate(steps):
            if k:
                z = [sum(E[i][q] * z[q] for q in range(n)) for i in range(n)]
            y = [z[i] - Ainvb[i] for i in range(n)]
            out["n_R"].append(y[iR])
            out["n_P"].append(y[iP])
            out["E_tx"].append(sum(y[:m_tx]))
            out["E_tl"].append(sum(y[iR + 1:iP]))
            # §5.1's scalar formulas, an independent route for n_R and E_tx.
            dk = k_tx - k0_R
            nR = y0[iR] * (-k0_R * t).exp() + J / k0_R * (
                _P(m_tx, k_tx * t) - (-k0_R * t).exp() * (k_tx / dk) ** m_tx * _P(m_tx, dk * t))
            out["n_R_scalar"].append(nR)
            out["E_tx_scalar"].append(J / k_tx * sum(_P(j, k_tx * t) for j in range(1, m_tx + 1)))
        nR_star = J / k0_R
        steady = {"n_R": nR_star, "n_P": beta * nR_star / k0_P, "E_tx": J * m_tx / k_tx,
                  "E_tl": beta * nR_star * m_tl / k_tl}
        frozen = {"x_tx": x_tx, "x_tl": x_tl, "y_R": y_R, "y_P": y_P, "phi_tx": phi_tx,
                  "phi_tl": phi_tl, "kappa0_tx": k_tx, "kappa0_tl": k_tl, "k0_R": k0_R,
                  "k0_P": k0_P, "u_1": u1, "lambda_tx": lam_tx, "J_I_tx": J, "beta_tl": beta,
                  "tau0_tx": a["L_R"] / (_c(a["v_tx"]) * phi_tx),
                  "tau0_tl": a["L_P"] / (_c(a["v_tl"]) * phi_tl)}
        return {"times": [str(t) for t in steps],
                "series": {k: [str(+v) for v in vals] for k, vals in out.items()},
                "steady": {k: str(+v) for k, v in steady.items()},
                "frozen": {k: str(+v) for k, v in frozen.items()}, "prec": prec}


def a1m_closed(pot: sheet.Potentials, world: str, size: int | None = None, prec: int = 50) -> dict:
    """§5.2's steady state for a polymerase-limited world (size = T), the two-gene world
    (size None) or a ribosome-limited world (size = n_R), in fmol and fmol/s."""
    a, m = sheet.A1, sheet.A1M
    with localcontext() as ctx:
        ctx.prec = prec
        f = Frozen(pot)
        if world in ("pol", "two-gene"):
            c = {"N": m["c_N"], "Pi": a["c_Pi"]}
            phi = f.sat(c["N"], a["K_N_tx"]) * (1 - f.x_tx(c).exp())
            v, kI, M = _c(a["v_tx"]), _c(m["k_I_tx"]), _c(m["M_pol"]) * f.fmol_per_copy
            genes = ([("tx", a["L_R"], size)] if world == "pol"
                     else [("tx1", a["L_R"], m["T_1"]), ("tx2", m["L_2"], m["T_2"])])
        elif world == "rib":
            c = {"A": m["c_A"], "ATP": a["c_ATP"], "ADP": a["c_ADP"], "Pi": a["c_Pi"]}
            phi = (f.sat(c["A"], a["K_A_tl"]) * f.sat(c["ATP"], a["K_ATP_tl"])
                   * (1 - f.x_tl(c).exp()))
            v, kI, M = _c(a["v_tl"]), _c(m["k_I_tl"]), _c(m["M_rib"]) * f.fmol_per_copy
            genes = [("tl", a["L_P"], size)]
        else:
            raise ValueError(world)
        lam = {g: kI * f.c1 * n for g, _, n in genes}  # λ = k_I c₁ T (or k_I c₁ n_R), s⁻¹
        tau = {g: L / (v * phi) for g, L, _ in genes}
        denom = 1 + sum(lam[g] * tau[g] for g in lam)
        J = {g: lam[g] * M / denom for g in lam}
        out = {"phi": str(+phi), "M": str(+M), "F": str(+(M / denom))}
        for g in lam:
            out[f"lambda_{g}"] = str(+lam[g])
            out[f"tau0_{g}"] = str(+tau[g])
            out[f"J_{g}"] = str(+J[g])
            out[f"E_{g}"] = str(+(J[g] * tau[g]))
        out["prec"] = prec
        return out


def derived_values(pot: sheet.Potentials = sheet.TEST_INSTANCE, prec: int = 50) -> dict:
    """§5.3's derived symbols, recomputed from the transcribed declared values (decimal strings)."""
    a = sheet.A1
    lim = a1_limit(pot, [0, 60], prec)["frozen"]
    with localcontext() as ctx:
        ctx.prec = prec
        f = Frozen(pot)
        c = {s: a["c_" + s] for s in ("N", "M", "A", "ATP", "ADP", "Pi")}
        lna = f.lna
        mu = f.mu0
        x_rc = (mu["N"] + lna(c["N"]) + 2 * (mu["ADP"] + lna(c["ADP"])) - (mu["M"] + lna(c["M"]))
                - 2 * (mu["ATP"] + lna(c["ATP"])))
        pol = a1m_closed(pot, "pol", 1, prec)
        rib = a1m_closed(pot, "rib", 1, prec)
        two = a1m_closed(pot, "two-gene", None, prec)
        r_tx, r_tl = a["L_R"] // a["m_tx"], a["L_P"] // a["m_tl"]
        out = {
            "RT_kJ_mol": f.RT, "c_1": f.c1, "mu_ATP": mu["ATP"], "mu_N": mu["N"],
            "mu_R_res": mu["R_res"], "mu_P_res": mu["P_res"], "r_tx": D(r_tx), "r_tl": D(r_tl),
            "kappa_tx": _c(a["v_tx"]) / r_tx, "kappa_tl": _c(a["v_tl"]) / r_tl,
            "x_tx": D(lim["x_tx"]), "x_tl": D(lim["x_tl"]), "y_R": D(lim["y_R"]),
            "y_P": D(lim["y_P"]), "x_rc": x_rc, "phi_tx": D(lim["phi_tx"]),
            "phi_tl": D(lim["phi_tl"]), "tau_tx": D(lim["tau0_tx"]), "tau_tl": D(lim["tau0_tl"]),
            "k0_R": D(lim["k0_R"]), "k0_P": D(lim["k0_P"]), "u_1": D(lim["u_1"]),
            "lambda_tx": D(lim["lambda_tx"]), "beta_tl": D(lim["beta_tl"]),
            "M_phi_tx": D(pol["phi"]), "M_tau_1": D(pol["tau0_tx"]), "M_tau_2": D(two["tau0_tx2"]),
            "M_lambda_1": D(pol["lambda_tx"]),
            "M_lambda_tau_1": D(pol["lambda_tx"]) * D(pol["tau0_tx"]),
            "M_phi_tl": D(rib["phi"]), "M_tau_rib": D(rib["tau0_tl"]),
            "M_lambda_rib": D(rib["lambda_tl"]),
            "M_lambda_tau_rib": D(rib["lambda_tl"]) * D(rib["tau0_tl"]),
        }
        return {k: str(+v) for k, v in out.items()}


def typed_digit_check(values: dict) -> dict:
    """Each recomputed value against §5.3's typed value, in units of the typed last digit."""
    out = {}
    for k, typed in sheet.TYPED_DERIVED.items():
        t = D(typed)
        digits = typed.lstrip("-").split("e")[0].replace(".", "").lstrip("0")
        unit = D(1).scaleb(t.adjusted() - len(digits) + 1)
        off = (D(values[k]) - t) / unit
        out[k] = {"typed": typed, "recomputed": values[k], "off_in_last_digit": float(off),
                  "agrees": abs(off) <= D("0.5") + D("1e-6")}
    return out
