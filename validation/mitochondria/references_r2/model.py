"""R2: an independent integration of MT-1b's declared equations (D280).

Written from the declared documents only, without reading engine code, engine output, a source
paper or the earlier references' code:
- the laws appendix at tag mito-laws-appendix-2026-11-20b (sections 0-10; section 12's items are
  declared with the world);
- docs/MITOCHONDRIA_DESIGN.md at tag mito-mt1b-face-design-2026-11-22 (section 7, the MT-1b draft,
  the outer-membrane face note);
- docs/MITOCHONDRIA_DESIGN.md at tag mito-mt1b-world-declaration-2026-11-22 (the world declaration,
  G1-G7, and the face note's section 6 erratum).
Every number comes from declaration.json, which names its place in those documents.

The model, in the appendix's frame B:
- Three places: the matrix N and the IMS P (finite nodes) and the held bath e; in world (d) also
  a finite O2 node. Concentrations are mol per litre of that compartment's water; every flux J is
  mol s-1 per litre of mitochondria.
- Rows hold totals. The binding closure (rapid equilibrium) gives the free forms at N and P: H+ on
  HPO4 2- (k_dH) and on the matrix buffer B_x; Mg2+ on ATP4- and ADP3-; nothing on AMP.
- The nine declared laws, each J = S (1 - e^x) (complexes I, III with phosphate control, IV per O2,
  synthesis, the exchange, the phosphate carrier, the K+/H+ exchange, the held-pair supply, the
  IMS kinase); the leak and the uncoupler patch as constant-field H+ (G1); O2 across the inner
  membrane by neutral permeation (G6 (ii)).
- The outer membrane: each binding form, the free H+, K+ and Mg2+ and O2, by log-mean
  electrodiffusion between the bath (or W3(d)'s O2 node) and the IMS,
  J_f = G_f [(c_e - c_P) + z_f v L(c_e, c_P)], with v = F(phi_e - phi_P)/RT set by zero net
  outer-membrane current (G5).
- dPsi = phi_P - phi_N from C_IM dPsi/dt = sum_k q_k J_k.

Ledgers ride in the same integration as quadrature states: each process's dissipation -J x (in RT
units), the held pair's work, the bath's supply valued at the free potentials (option (a)), the
outer membrane's inflow per row, the O2 that complex IV uses and the supply's turnovers.
"""

import math

import numpy as np

from . import constants

PHYS = (
    "dpsi", "H_N", "K_N", "Mg_N", "ATP_N", "ADP_N", "Pi_N", "NADH", "NAD", "QH2", "Q", "O2_N",
    "H_P", "K_P", "Mg_P", "ATP_P", "ADP_P", "AMP_P", "Pi_P", "O2_P", "c2", "c3", "O2_node",
)
N_ROWS = ("H_N", "K_N", "Mg_N", "ATP_N", "ADP_N", "Pi_N", "NADH", "NAD", "QH2", "Q", "O2_N")
P_ROWS = ("H_P", "K_P", "Mg_P", "ATP_P", "ADP_P", "AMP_P", "Pi_P", "O2_P", "c2", "c3")
VALENCE = {  # each row's reference (base) form (design 1.3; appendix 0)
    "H": 1, "K": 1, "Mg": 2, "ATP": -4, "ADP": -3, "AMP": -2, "Pi": -2, "NADH": -2, "NAD": -1,
    "QH2": 0, "Q": 0, "O2": 0, "c2": 2, "c3": 3,
}
PROCESSES = ("C1", "C3", "C4", "F1", "ANT", "PiHt", "KH", "Supply", "AK", "Leak", "Uncoupler",
             "O2_IM")
FACE_FORMS = (  # name, valence, rows carried into P per unit, permeability key
    ("ATP4", -4, {"ATP_P": 1}, "p_A"),
    ("MgATP", -2, {"ATP_P": 1, "Mg_P": 1}, "p_A"),
    ("ADP3", -3, {"ADP_P": 1}, "p_A"),
    ("MgADP", -1, {"ADP_P": 1, "Mg_P": 1}, "p_A"),
    ("AMP", -2, {"AMP_P": 1}, "p_A"),
    ("HPO4", -2, {"Pi_P": 1}, "p_Pi"),
    ("H2PO4", -1, {"Pi_P": 1, "H_P": 1}, "p_Pi"),
    ("H", 1, {"H_P": 1}, "p_H_free"),
    ("K", 1, {"K_P": 1}, "p_K_free"),
    ("Mg", 2, {"Mg_P": 1}, "p_Mg_free"),
    ("O2", 0, {"O2_P": 1}, "p_O2_face"),
)
FACE_NAMES = tuple(f[0] for f in FACE_FORMS)
IN_ROWS = ("H", "K", "Mg", "ATP", "ADP", "AMP", "Pi", "O2")
LEDGER = tuple("D_" + k for k in PROCESSES) + ("D_face", "W_held", "W_bath") + tuple(
    "In_" + r for r in IN_ROWS) + ("O2_used", "S_used")
STATE = PHYS + LEDGER
IDX = {name: i for i, name in enumerate(STATE)}
NPHYS = len(PHYS)
BATHS = ("trace", "state3", "atp_bath")


def stoichiometry(n_A=3):
    """Each turnover's rows at their ends, and q, the charge moved from N to P (appendix 1-7)."""
    return {
        "C1": ({"NADH": -1, "Q": -1, "NAD": 1, "QH2": 1, "H_N": -5, "H_P": 4}, 4),
        "C3": ({"QH2": -1, "Q": 1, "c3": -2, "c2": 2, "H_N": -2, "H_P": 4}, 2),
        "C4": ({"O2_N": -1, "c2": -4, "c3": 4, "H_N": -8, "H_P": 4}, 8),
        "F1": ({"ADP_N": -1, "Pi_N": -1, "ATP_N": 1, "H_N": n_A - 1, "H_P": -n_A}, -n_A),
        "ANT": ({"ATP_N": -1, "ATP_P": 1, "ADP_P": -1, "ADP_N": 1}, -1),
        "PiHt": ({"Pi_P": -1, "Pi_N": 1, "H_P": -2, "H_N": 2}, 0),
        "KH": ({"K_P": -1, "K_N": 1, "H_N": -1, "H_P": 1}, 0),
        "Supply": ({"NAD": -1, "NADH": 1, "H_N": 1}, 0),  # and the held pair: S_red -1, S_ox +1
        "AK": ({"ADP_P": -2, "ATP_P": 1, "AMP_P": 1}, 0),
        "Leak": ({"H_P": -1, "H_N": 1}, -1),
        "Uncoupler": ({"H_P": -1, "H_N": 1}, -1),
        "O2_IM": ({"O2_P": -1, "O2_N": 1}, 0),
    }


def row_valence(row):
    return VALENCE[row.split("_")[0]]


def logmean(a, b):
    """L(a, b) = (a - b)/ln(a/b), L(a, a) = a, and 0 when either end is 0; accurate near a = b."""
    if a <= 0.0 or b <= 0.0:
        return 0.0
    d = (b - a) / a
    if d == 0.0:
        return a
    return a * d / math.log1p(d)


def free_ligand(total, binders, guess=None):
    """The free ligand x > 0 with x + sum_i B_i x/(K_i + x) = total (one site per binder).

    Safeguarded Newton in ln x, bracketed by total/(1 + sum B/K), below the root since each
    binding term is concave, and total, above it. It takes one more step after the Newton step
    falls below 1e-13 in ln x, so the root is converged to rounding whatever the start.
    """
    if not total > 0.0:
        raise ValueError("a closure total must be positive")
    capacity = 1.0
    for B, K in binders:
        capacity += B / K
    if capacity == 1.0:
        return total
    s_lo = math.log(total / capacity)
    s_hi = math.log(total)
    if guess is not None and guess > 0.0:
        s = math.log(guess)
        if not s_lo < s < s_hi:
            s = 0.5 * (s_lo + s_hi)
    else:
        s = s_lo
    done = False
    for _ in range(200):
        x = math.exp(s)
        f = x - total
        fp = 1.0
        for B, K in binders:
            d = K + x
            f += B * x / d
            fp += B * K / (d * d)
        if f > 0.0:
            s_hi = s
        elif f < 0.0:
            s_lo = s
        else:
            return x
        s_new = s - f / (x * fp)
        if not s_lo <= s_new <= s_hi:
            s_new = 0.5 * (s_lo + s_hi)
        if done:
            return math.exp(s_new)
        if abs(s_new - s) < 1e-13:
            done = True
        s = s_new
    raise RuntimeError("closure did not converge")


class Controls:
    """Piecewise-constant settings of one protocol segment."""

    def __init__(self, world, bath="trace", a_C4=1.0, a_ANT=1.0, a_unc=0.0, o2="bath",
                 Pi_e=None):
        if bath not in BATHS or o2 not in ("bath", "node"):
            raise ValueError("unknown bath or O2 mode")
        self.bath_name = bath
        self.a_C4 = float(a_C4)
        self.a_ANT = float(a_ANT)
        self.a_unc = float(a_unc)
        self.o2 = o2
        self.Pi_e = Pi_e
        self.bath = world.bath(bath, Pi_e)

    def describe(self):
        d = dict(bath=self.bath_name, a_C4=self.a_C4, a_ANT=self.a_ANT, a_unc=self.a_unc,
                 o2=self.o2)
        if self.Pi_e is not None:
            d["Pi_e"] = self.Pi_e
        return d


class World:
    """MT-1b's declared world, as R2 reads it."""

    def __init__(self, declaration=None, overrides=None):
        decl = declaration or constants.load_declaration()
        self.declaration = decl
        values = {}
        for group in ("parameters", "world", "bath", "finite_O2"):
            for key, entry in decl[group].items():
                values[key] = entry["value"]
        for key, value in (overrides or {}).items():
            if key not in values:
                raise KeyError("unknown override " + key)
            values[key] = value
        self.values = values
        c = constants.floats(decl)
        self.c = c
        self.RT = c["RT"]
        self.f_mV = c["f_mV"]
        self.ln1e7 = c["ln1e7"]
        self.K_base = c["K_base"]
        self.mu = c["mu"]
        v = values
        mM = 1e-3
        self.n_A = int(v["n_A"])
        self.stoich = stoichiometry(self.n_A)
        self.X_C1, self.X_C3, self.X_C4 = v["X_C1"], v["X_C3"], v["X_C4"]
        self.k_Pi3, self.k_Pi4 = v["k_Pi3"] * mM, v["k_Pi4"] * mM
        self.k_O2 = v["k_O2"]
        self.X_F1 = v["X_F1"]
        self.K_T, self.K_D, self.k_dH = v["K_MgATP"], v["K_MgADP"], v["k_dH"]
        self.X_ANT, self.k_mADP = v["X_ANT"], v["k_mADP"]
        self.theta_P, self.theta_N = v["theta_P"], v["theta_N"]
        self.exchange_form = v["exchange_form"]
        if self.exchange_form not in ("declared", "printed"):
            raise ValueError("exchange_form is 'declared' or 'printed' (plant P-a only)")
        # The error control is relative above the smallest declared trace (erratum 2's rule).
        self.concentration_floor = min(v["ADP_trace"], v["ATP_trace"], v["AMP_trace"])
        self.X_PiHt, self.k_PiHt = v["X_PiHt"], v["k_PiHt"] * mM
        self.X_KH = v["X_KH"]
        self.X_DH, self.r = v["X_DH"], v["r"]
        self.k_Pi1, self.k_Pi2 = v["k_Pi1"] * mM, v["k_Pi2"] * mM
        self.X_AK = v["X_AK"]
        RT_kJ = self.RT / 1000.0
        self.g0_C1 = v["dG0_C1_pH7"] / RT_kJ
        self.g0_C3 = v["dG0_C3_pH7"] / RT_kJ
        self.g0_C4 = v["dG0_C4_pH7_per_half_O2"] / RT_kJ
        self.g0_ATP = v["dG0_ATP_pH7"] / RT_kJ
        self.g0_F = c["dG0_F_RT"]
        self.ln_ref_supply = -v["supply_reference_pH"] * math.log(10.0)  # ln(10^-7.10 M)
        self.ln_Sred_over_Sox = v["supply_pair_exponent"] * math.log(10.0) + math.log(self.r)
        self.mu_Sox_minus_Sred = (self.mu["S_ox"] - self.mu["S_red"]) - self.ln_Sred_over_Sox
        self.W_x, self.W_i = v["W_x"], v["W_i"]
        self.C_IM = v["C_IM"]
        # Eq. 19 as G1 quotes it: J = X_Hle dPsi (h_P e^u - h_N)/(e^u - 1) = P u (h_P - h_N e^-u)
        # /(1 - e^-u), so P = X_Hle RT/F (mV), per litre of mitochondria.
        self.P_leak = v["X_Hle"] / self.f_mV
        self.P_unc = v["uncoupler_factor"] * self.P_leak
        self.B_N, self.KB_N = v["buffer_N_total"], 10.0 ** (-v["buffer_N_pK"])
        self.B_P, self.KB_P = v["buffer_P_total"], 10.0 ** (-v["buffer_P_pK"])
        gamma = v["gamma"]
        self.face_G = tuple(gamma * v[f[3]] for f in FACE_FORMS)  # s-1 (um-1 x um s-1)
        self.face_z = tuple(f[1] for f in FACE_FORMS)
        # O2 across the inner membrane: P_O2 A_IM per litre of mitochondria, with A_IM = C/(C per
        # area) and C = C_IM F (1000 mV/V) farad per litre; times 1000 L m-3 gives s-1.
        F = float(constants.F_EXACT)
        area_per_L = self.C_IM * F * 1000.0 / v["C_area"]  # m2 (L mito)-1
        self.k_O2_IM = v["P_O2_inner"] * area_per_L * 1000.0
        self.node_water = v["node_water"]
        self.NAD_tot = v["NAD_tot"] * mM
        self.Q_tot = v["Q_tot"] * mM
        self.cytC_tot = v["cytC_tot"] * mM
        self.A_tot = v["A_tot"] * mM
        self.Mg_tot_N = v["Mg_tot_N"] * mM
        mu = self.mu
        self.face_mu0 = {
            "ATP4": mu["ATP"], "MgATP": mu["MgATP"], "ADP3": mu["ADP"], "MgADP": mu["MgADP"],
            "AMP": mu["AMP"], "HPO4": mu["HPO4"], "H2PO4": mu["H2PO4"], "H": mu["H"],
            "K": mu["K"], "Mg": mu["Mg"], "O2": mu["O2"],
        }
        self._guess = [None, None, None, None]
        self.jac_floor = np.array([1e-6] + [1e-18] * (NPHYS - 1))

    # ----------------------------------------------------------------- the held bath, option (a)
    def bath(self, name, Pi_e=None):
        v = self.values
        adp, atp = {
            "trace": (v["ADP_trace"], v["ATP_trace"]),
            "state3": (v["ADP_state3"], v["ATP_trace"]),
            "atp_bath": (v["ADP_atp_bath"], v["ATP_atp_bath"]),
        }[name]
        h = 10.0 ** (-v["pH"])
        amp, mg_tot, k, o2 = v["AMP_trace"], v["Mg_tot"], v["K"], v["O2"]
        pi = v["Pi_tot"] if Pi_e is None else Pi_e
        m = free_ligand(mg_tot, ((atp, self.K_T), (adp, self.K_D)))
        atp4 = atp / (1.0 + m / self.K_T)
        adp3 = adp / (1.0 + m / self.K_D)
        hpo4 = pi / (1.0 + h / self.k_dH)
        c = {
            "ATP4": atp4, "MgATP": atp4 * m / self.K_T, "ADP3": adp3, "MgADP": adp3 * m / self.K_D,
            "AMP": amp, "HPO4": hpo4, "H2PO4": hpo4 * h / self.k_dH, "H": h, "K": k, "Mg": m,
            "O2": o2,
        }
        mu_e = {f: (self.face_mu0[f] + math.log(c[f])) if c[f] > 0.0 else -math.inf
                for f in FACE_NAMES}
        return {
            "name": name, "c": c, "c_tuple": tuple(c[f] for f in FACE_NAMES),
            "mu": mu_e, "mu_tuple": tuple(mu_e[f] for f in FACE_NAMES),
            "totals": {"ATP": atp, "ADP": adp, "AMP": amp, "Pi": pi, "Mg": mg_tot, "K": k,
                       "O2": o2, "pH": v["pH"], "Mg_free": m},
        }

    # ----------------------------------------------------------------- the closure
    def speciate(self, y, remember=True):
        """Free H+ and Mg2+ at N and P from the totals (rapid equilibrium)."""
        g = self._guess
        hN = free_ligand(y[1], ((y[6], self.k_dH), (self.B_N, self.KB_N)), g[0])
        mN = free_ligand(y[3], ((y[4], self.K_T), (y[5], self.K_D)), g[1])
        hP = free_ligand(y[12], ((y[18], self.k_dH), (self.B_P, self.KB_P)), g[2])
        mP = free_ligand(y[14], ((y[15], self.K_T), (y[16], self.K_D)), g[3])
        if remember:
            self._guess = [hN, mN, hP, mP]
        return hN, mN, hP, mP

    # ----------------------------------------------------------------- the laws
    def evaluate(self, y, ctl):
        """Everything at one state: free forms, each process's J, S and x, and the face."""
        (dpsi, H_N, K_N, Mg_N, ATP_N, ADP_N, Pi_N, NADH, NAD, QH2, Q, O2_N,
         H_P, K_P, Mg_P, ATP_P, ADP_P, AMP_P, Pi_P, O2_P, c2, c3, O2_node) = y[:NPHYS]
        hN, mN, hP, mP = self.speciate(y)
        log, exp, expm1 = math.log, math.exp, math.expm1
        K_T, K_D, k_dH = self.K_T, self.K_D, self.k_dH
        u = dpsi * self.f_mV
        ATP4_N = ATP_N / (1.0 + mN / K_T)
        ADP3_N = ADP_N / (1.0 + mN / K_D)
        MgADP_N = ADP3_N * mN / K_D
        HPO4_N = Pi_N / (1.0 + hN / k_dH)
        ATP4_P = ATP_P / (1.0 + mP / K_T)
        MgATP_P = ATP4_P * mP / K_T
        ADP3_P = ADP_P / (1.0 + mP / K_D)
        MgADP_P = ADP3_P * mP / K_D
        HPO4_P = Pi_P / (1.0 + hP / k_dH)
        H2PO4_P = HPO4_P * hP / k_dH
        lhN, lhP = log(hN), log(hP)
        lN7 = lhN + self.ln1e7  # ln(h_N/1e-7 M)
        g = u + lhP - lhN  # Delta G_H/RT
        lQ = log(Q / QH2)
        J, S, X = {}, {}, {}
        # Complex I (1.1): S = X_C1 exp[-(dG/RT + 4 g - ln(h_N/1e-7) - ln(Q/QH2))] [NADH].
        x = self.g0_C1 + log(NAD / NADH) - lQ - lN7 + 4.0 * g
        s = self.X_C1 * exp(-(self.g0_C1 + 4.0 * g - lN7 - lQ)) * NADH
        X["C1"], S["C1"], J["C1"] = x, s, -s * expm1(x)
        # Complex III with phosphate control (1.2): J = phi_Pi A7 (1 - e^{x/2}).
        x = self.g0_C3 + lQ + 2.0 * log(c2 / c3) + 2.0 * lN7 + 4.0 * g - 2.0 * u
        phi_Pi = (1.0 + Pi_N / self.k_Pi3) / (1.0 + Pi_N / self.k_Pi4)
        a7 = self.X_C3 * exp(-0.5 * (self.g0_C3 + 4.0 * g + 2.0 * lN7 - 2.0 * u + lQ)) * c3
        X["C3"], J["C3"] = x, -phi_Pi * a7 * expm1(0.5 * x)
        S["C3"] = phi_Pi * a7 / (1.0 + exp(0.5 * x))
        # Complex IV per O2 (1.3): half the printed per-pair flux, (A9/2)(1 - e^{x/4}).
        lO2 = log(O2_N)
        x = 2.0 * self.g0_C4 + 4.0 * log(c3 / c2) - lO2 - 4.0 * lN7 + 4.0 * g + 4.0 * u
        a9 = (self.X_C4 / (1.0 + self.k_O2 / O2_N) * (c2 / (c2 + c3))
              * exp(-0.5 * (self.g0_C4 + 2.0 * g - 2.0 * lN7 - 0.5 * lO2)) * c2)
        e4 = exp(0.25 * x)
        X["C4"] = x
        J["C4"] = -ctl.a_C4 * 0.5 * a9 * expm1(0.25 * x)
        S["C4"] = ctl.a_C4 * 0.5 * a9 / (1.0 + e4 + e4 * e4 + e4 * e4 * e4)
        # Synthesis (2), balanced in frame B: S = A11.
        x = self.g0_F + log(ATP4_N / (ADP3_N * HPO4_N)) - lhN - self.n_A * g
        s = self.X_F1 * exp(-(self.g0_ATP - self.n_A * g)) * (K_D / K_T) * MgADP_N * Pi_N
        X["F1"], S["F1"], J["F1"] = x, s, -s * expm1(x)
        # The exchange (3), shares theta_P + theta_N = 1. Plant P-a only: Eq. 14's printed
        # two-fraction form, which is balanced only when the shares sum to one.
        a, b = ADP3_P, ATP4_P * exp(-self.theta_P * u)
        cc, d = ADP3_N, ATP4_N * exp(self.theta_N * u)
        s = ctl.a_ANT * self.X_ANT * a * d / ((a + b) * (cc + d)) / (1.0 + self.k_mADP / a)
        x = log(ATP4_P * ADP3_N / (ATP4_N * ADP3_P)) - u
        if self.exchange_form == "printed":
            j = (ctl.a_ANT * self.X_ANT * (a / (a + b) - cc / (cc + d))
                 / (1.0 + self.k_mADP / a))
        else:
            j = -s * expm1(x)
        X["ANT"], S["ANT"], J["ANT"] = x, s, j
        # The phosphate carrier (4), balanced in frame B: S = A16.
        s = self.X_PiHt * H2PO4_P * hN / (H2PO4_P + self.k_PiHt)
        x = log(HPO4_N / HPO4_P) + 2.0 * (lhN - lhP)
        X["PiHt"], S["PiHt"], J["PiHt"] = x, s, -s * expm1(x)
        # The K+/H+ exchange (5).
        s = self.X_KH * K_P * hN
        x = log(K_N / K_P) + lhP - lhN
        X["KH"], S["KH"], J["KH"] = x, s, -s * expm1(x)
        # The held-pair supply (6): J = X_DH phi_DH (r [NAD] - [NADH] h_N/10^-7.10).
        phi_DH = (1.0 + Pi_N / self.k_Pi1) / (1.0 + Pi_N / self.k_Pi2)
        s = self.X_DH * phi_DH * self.r * NAD
        x = log(NADH / (self.r * NAD)) + lhN - self.ln_ref_supply
        X["Supply"], S["Supply"], J["Supply"] = x, s, -s * expm1(x)
        # The IMS kinase (7), in base forms with the source's rate.
        s = self.X_AK * (1.0 + mP / K_T) * self.K_base * ADP3_P * ADP3_P
        x = log(ATP4_P * AMP_P / (self.K_base * ADP3_P * ADP3_P))
        X["AK"], S["AK"], J["AK"] = x, s, -s * expm1(x)
        # The leak and the uncoupler patch: constant-field H+ from P to N (G1).
        ghk = u / (-expm1(-u)) if abs(u) > 1e-12 else 1.0 + 0.5 * u
        x = lhN - lhP - u
        e = expm1(x)
        s = self.P_leak * ghk * hP
        X["Leak"], S["Leak"], J["Leak"] = x, s, -s * e
        s = ctl.a_unc * self.P_unc * ghk * hP
        X["Uncoupler"], S["Uncoupler"], J["Uncoupler"] = x, s, -s * e
        # O2 across the inner membrane (G6 (ii)): neutral permeation from P to N.
        X["O2_IM"] = log(O2_N / O2_P)
        S["O2_IM"] = self.k_O2_IM * O2_P
        J["O2_IM"] = self.k_O2_IM * (O2_P - O2_N)
        # The outer membrane, per form, at zero net current (face note 2; G4, G5).
        cP = (ATP4_P, MgATP_P, ADP3_P, MgADP_P, AMP_P, HPO4_P, H2PO4_P, hP, K_P, mP, O2_P)
        ce = ctl.bath["c_tuple"]
        if ctl.o2 == "node":
            ce = ce[:-1] + (O2_node,)
        num = 0.0
        den = 0.0
        Ls = []
        for G, z, a_e, a_p in zip(self.face_G, self.face_z, ce, cP, strict=True):
            L = logmean(a_e, a_p)
            Ls.append(L)
            if z:
                num += z * G * (a_e - a_p)
                den += z * z * G * L
        v = -num / den
        Jf = [G * ((a_e - a_p) + z * v * L)
              for G, z, a_e, a_p, L in zip(self.face_G, self.face_z, ce, cP, Ls, strict=True)]
        return {"free": (hN, mN, hP, mP), "u": u, "J": J, "S": S, "x": X, "Jf": Jf, "v": v,
                "cP": cP, "ce": ce}

    def face_x(self, ev):
        """Each face form's x = ln(c_P/c_e) - z v (transport from e into P)."""
        return [math.log(a_p / a_e) - z * ev["v"]
                for z, a_e, a_p in zip(self.face_z, ev["ce"], ev["cP"], strict=True)]

    # ----------------------------------------------------------------- the right-hand side
    def rhs(self, t, y, ctl):
        yl = y.tolist() if isinstance(y, np.ndarray) else list(y)
        try:
            ev = self.evaluate(yl, ctl)
        except (ValueError, ZeroDivisionError):
            # A non-positive concentration is outside the laws' domain: NaN makes the implicit
            # solver reject the stage and retry with a smaller step.
            return np.full(len(STATE), np.nan)
        J, X, Jf = ev["J"], ev["x"], ev["Jf"]
        jC1, jC3, jC4, jF1, jANT = J["C1"], J["C3"], J["C4"], J["F1"], J["ANT"]
        jPi, jKH, jS, jAK, jO2 = J["PiHt"], J["KH"], J["Supply"], J["AK"], J["O2_IM"]
        jH = J["Leak"] + J["Uncoupler"]
        n_A = self.n_A
        (fATP4, fMgATP, fADP3, fMgADP, fAMP, fHPO4, fH2PO4, fH, fK, fMg, fO2) = Jf
        in_H = fH + fH2PO4
        in_Mg = fMg + fMgATP + fMgADP
        in_ATP = fATP4 + fMgATP
        in_ADP = fADP3 + fMgADP
        in_Pi = fHPO4 + fH2PO4
        Wx, Wi = self.W_x, self.W_i
        dy = [0.0] * len(STATE)
        dy[0] = (4.0 * jC1 + 2.0 * jC3 + 8.0 * jC4 - n_A * jF1 - jANT - jH) / self.C_IM
        dy[1] = (-5.0 * jC1 - 2.0 * jC3 - 8.0 * jC4 + (n_A - 1) * jF1 + 2.0 * jPi - jKH + jS
                 + jH) / Wx
        dy[2] = jKH / Wx
        dy[4] = (jF1 - jANT) / Wx
        dy[5] = (-jF1 + jANT) / Wx
        dy[6] = (-jF1 + jPi) / Wx
        dy[7] = (-jC1 + jS) / Wx
        dy[8] = (jC1 - jS) / Wx
        dy[9] = (jC1 - jC3) / Wx
        dy[10] = (-jC1 + jC3) / Wx
        dy[11] = (jO2 - jC4) / Wx
        dy[12] = (4.0 * jC1 + 4.0 * jC3 + 4.0 * jC4 - n_A * jF1 - 2.0 * jPi + jKH - jH + in_H) / Wi
        dy[13] = (-jKH + fK) / Wi
        dy[14] = in_Mg / Wi
        dy[15] = (jANT + jAK + in_ATP) / Wi
        dy[16] = (-jANT - 2.0 * jAK + in_ADP) / Wi
        dy[17] = (jAK + fAMP) / Wi
        dy[18] = (-jPi + in_Pi) / Wi
        dy[19] = (fO2 - jO2) / Wi
        dy[20] = (2.0 * jC3 - 4.0 * jC4) / Wi
        dy[21] = (-2.0 * jC3 + 4.0 * jC4) / Wi
        dy[22] = -fO2 / self.node_water if ctl.o2 == "node" else 0.0
        k = NPHYS
        for name in PROCESSES:
            dy[k] = -J[name] * X[name]
            k += 1
        Xf = self.face_x(ev)
        dy[k] = -sum(j * x for j, x in zip(Jf, Xf, strict=True))
        dy[k + 1] = -jS * self.mu_Sox_minus_Sred
        mus = ctl.bath["mu_tuple"]
        n_bath = len(Jf) - (1 if ctl.o2 == "node" else 0)
        dy[k + 2] = sum(Jf[i] * mus[i] for i in range(n_bath))
        dy[k + 3:k + 11] = [in_H, fK, in_Mg, in_ATP, in_ADP, fAMP, in_Pi, fO2]
        dy[k + 11] = jC4
        dy[k + 12] = jS
        return np.array(dy)

    def jac(self, t, y, ctl):
        """Forward differences over the physical columns; the ledger columns are exactly zero."""
        y = np.asarray(y, dtype=float)
        f0 = self.rhs(t, y, ctl)
        n = len(y)
        out = np.zeros((n, n))
        for j in range(NPHYS):
            if j == 22 and ctl.o2 != "node":
                continue
            yj = y[j]
            h = 1e-7 * max(abs(yj), self.jac_floor[j])
            y2 = y.copy()
            y2[j] = yj + h
            out[:, j] = (self.rhs(t, y2, ctl) - f0) / (y2[j] - yj)
        return out

    # ----------------------------------------------------------------- states and ledgers
    def guess_state(self, ctl):
        """R2's first guesses (declaration 'start_guess'); they reach no output."""
        s = self.declaration["start_guess"]
        y = np.zeros(len(STATE))
        bath = ctl.bath
        c = bath["c"]
        tot = bath["totals"]
        y[0] = s["dpsi_mV"]
        hN = 10.0 ** (-s["pH_N"])
        Pi_N = s["Pi_N"]
        y[1] = hN + Pi_N * hN / (self.k_dH + hN) + self.B_N * hN / (self.KB_N + hN)
        y[2] = s["K_N"]
        y[3] = self.Mg_tot_N
        y[4] = self.A_tot * s["ATP_N_fraction"]
        y[5] = self.A_tot - y[4]
        y[6] = Pi_N
        y[7] = self.NAD_tot * s["NADH_fraction"]
        y[8] = self.NAD_tot - y[7]
        y[9] = self.Q_tot * s["QH2_fraction"]
        y[10] = self.Q_tot - y[9]
        y[11] = tot["O2"]
        hP = c["H"]
        y[12] = hP + c["H2PO4"] + self.B_P * hP / (self.KB_P + hP)
        y[13] = tot["K"]
        y[14] = tot["Mg"]
        y[15] = tot["ATP"]
        y[16] = tot["ADP"]
        y[17] = tot["AMP"]
        y[18] = tot["Pi"]
        y[19] = tot["O2"]
        y[20] = self.cytC_tot * s["cytc_red_fraction"]
        y[21] = self.cytC_tot - y[20]
        y[22] = self.values["O2_start"]
        return y

    def forms(self, y):
        """Every form's concentration at N and P (mol per litre of that water)."""
        hN, mN, hP, mP = self.speciate(y, remember=False)
        g = lambda name: float(y[IDX[name]])  # noqa: E731
        K_T, K_D, k_dH = self.K_T, self.K_D, self.k_dH

        def node(h, m, ATP, ADP, Pi, B, KB):
            atp4 = ATP / (1.0 + m / K_T)
            adp3 = ADP / (1.0 + m / K_D)
            hpo4 = Pi / (1.0 + h / k_dH)
            base = B / (1.0 + h / KB) if B > 0 else 0.0
            return {"H": h, "Mg": m, "ATP4": atp4, "MgATP": atp4 * m / K_T, "ADP3": adp3,
                    "MgADP": adp3 * m / K_D, "HPO4": hpo4, "H2PO4": hpo4 * h / k_dH,
                    "Buf": base, "HBuf": B - base if B > 0 else 0.0}

        N = node(hN, mN, g("ATP_N"), g("ADP_N"), g("Pi_N"), self.B_N, self.KB_N)
        N.update(K=g("K_N"), NADH=g("NADH"), NAD=g("NAD"), QH2=g("QH2"), Q=g("Q"), O2=g("O2_N"))
        P = node(hP, mP, g("ATP_P"), g("ADP_P"), g("Pi_P"), self.B_P, self.KB_P)
        P.update(K=g("K_P"), AMP=g("AMP_P"), O2=g("O2_P"), c2=g("c2"), c3=g("c3"))
        return N, P

    def form_mu0(self, name, side):
        mu = self.mu
        table = {
            "H": 0.0, "Mg": 0.0, "K": 0.0, "ATP4": mu["ATP"], "MgATP": mu["MgATP"], "ADP3": 0.0,
            "MgADP": mu["MgADP"], "HPO4": 0.0, "H2PO4": mu["H2PO4"], "AMP": mu["AMP"],
            "NADH": mu["NADH"], "NAD": 0.0, "QH2": mu["QH2"], "Q": 0.0, "O2": 0.0,
            "c2": mu["cytc_red"], "c3": 0.0, "Buf": 0.0,
            # mu deg_f = mu deg_base + mu deg_L + ln K_d (appendix 9); the buffer's base is 0.
            "HBuf": math.log(self.KB_N if side == "N" else self.KB_P),
        }
        return table[name]

    def free_energy(self, y, o2):
        """A = sum over forms of n (mu deg + ln c - 1) + C_IM f dPsi^2 / 2, RT mol (L mito)-1.

        The held pair and the held bath are reservoirs outside A; W3(d)'s O2 node is inside it.
        """
        N, P = self.forms(y)
        total = 0.0
        for side, forms, water in (("N", N, self.W_x), ("P", P, self.W_i)):
            for name, c in forms.items():
                if c > 0.0:
                    total += water * c * (self.form_mu0(name, side) + math.log(c) - 1.0)
        if o2 == "node":
            c = float(y[IDX["O2_node"]])
            total += self.node_water * c * (math.log(c) - 1.0)
        total += 0.5 * self.C_IM * self.f_mV * float(y[0]) ** 2
        return total

    def row_charge(self, y):
        qN = sum(row_valence(r) * float(y[IDX[r]]) for r in N_ROWS) * self.W_x
        qP = sum(row_valence(r) * float(y[IDX[r]]) for r in P_ROWS) * self.W_i
        return qN, qP

    def charge_inventory(self, y):
        """The matrix charge inventory I = C_IM dPsi + W_x sum_N z c (mol (L mito)-1)."""
        return self.C_IM * float(y[0]) + self.row_charge(y)[0]

    def invariants(self, y, o2="bath"):
        """The conserved quantities that the material and charge ledgers close on."""
        g = lambda name: float(y[IDX[name]])  # noqa: E731
        Wx, Wi = self.W_x, self.W_i
        qN, qP = self.row_charge(y)
        o2_total = Wx * g("O2_N") + Wi * g("O2_P") + g("O2_used")
        o2_total += self.node_water * g("O2_node") if o2 == "node" else -g("In_O2")
        return {
            "NAD_tot": g("NADH") + g("NAD"),
            "Q_tot": g("QH2") + g("Q"),
            "cytc_tot": g("c2") + g("c3"),
            "A_N": g("ATP_N") + g("ADP_N"),
            "Mg_N": g("Mg_N"),
            "adenine_P": Wi * (g("ATP_P") + g("ADP_P") + g("AMP_P"))
            - g("In_ATP") - g("In_ADP") - g("In_AMP"),
            "K": Wx * g("K_N") + Wi * g("K_P") - g("In_K"),
            "Mg_P": Wi * g("Mg_P") - g("In_Mg"),
            "phosphorus": Wx * (3 * g("ATP_N") + 2 * g("ADP_N") + g("Pi_N"))
            + Wi * (3 * g("ATP_P") + 2 * g("ADP_P") + g("AMP_P") + g("Pi_P"))
            - (3 * g("In_ATP") + 2 * g("In_ADP") + g("In_AMP") + g("In_Pi")),
            "electrons": Wx * (2 * g("NADH") + 2 * g("QH2")) + Wi * g("c2")
            + 4 * g("O2_used") - 2 * g("S_used"),
            "O2": o2_total,
            "charge_N": self.C_IM * g("dpsi") + qN,
            "charge_NP": qN + qP,
        }

    def invariant_scales(self, y, o2="bath"):
        """The magnitude of each invariant's terms, against which its drift is judged."""
        g = lambda name: abs(float(y[IDX[name]]))  # noqa: E731
        Wx, Wi = self.W_x, self.W_i
        absN = sum(abs(row_valence(r)) * g(r) for r in N_ROWS) * Wx
        absP = sum(abs(row_valence(r)) * g(r) for r in P_ROWS) * Wi
        o2 = Wx * g("O2_N") + Wi * g("O2_P") + g("O2_used") + self.node_water * g("O2_node") \
            + g("In_O2")
        return {
            "NAD_tot": g("NADH") + g("NAD"), "Q_tot": g("QH2") + g("Q"),
            "cytc_tot": g("c2") + g("c3"), "A_N": g("ATP_N") + g("ADP_N"), "Mg_N": g("Mg_N"),
            "adenine_P": Wi * (g("ATP_P") + g("ADP_P") + g("AMP_P")) + g("In_ATP") + g("In_ADP")
            + g("In_AMP"),
            "K": Wx * g("K_N") + Wi * g("K_P") + g("In_K"),
            "Mg_P": Wi * g("Mg_P") + g("In_Mg"),
            "phosphorus": Wx * (3 * g("ATP_N") + 2 * g("ADP_N") + g("Pi_N"))
            + Wi * (3 * g("ATP_P") + 2 * g("ADP_P") + g("AMP_P") + g("Pi_P"))
            + 3 * g("In_ATP") + 2 * g("In_ADP") + g("In_AMP") + g("In_Pi"),
            "electrons": Wx * (2 * g("NADH") + 2 * g("QH2")) + Wi * g("c2") + 4 * g("O2_used")
            + 2 * g("S_used"),
            "O2": o2,
            "charge_N": self.C_IM * g("dpsi") + absN,
            "charge_NP": absN + absP,
        }

    def energy_terms(self, y, o2):
        A = self.free_energy(y, o2)
        D = sum(float(y[IDX["D_" + k]]) for k in PROCESSES) + float(y[IDX["D_face"]])
        W = float(y[IDX["W_held"]]) + float(y[IDX["W_bath"]])
        return A, D, W

    # ----------------------------------------------------------------- readouts
    def synthase_stall_mV(self, y):
        """The dPsi at which the synthase's x is zero at this state's concentrations."""
        N, P = self.forms(y)
        lhs = self.g0_F + math.log(N["ATP4"] / (N["ADP3"] * N["HPO4"] * N["H"]))
        u = lhs / self.n_A - math.log(P["H"] / N["H"])
        return u / self.f_mV

    def readouts(self, y, ctl):
        yl = [float(v) for v in y]
        ev = self.evaluate(yl, ctl)
        hN, mN, hP, mP = ev["free"]
        J, X = ev["J"], ev["x"]
        Jf = dict(zip(FACE_NAMES, ev["Jf"], strict=True))
        g = lambda name: yl[IDX[name]]  # noqa: E731
        out = {
            "dpsi_mV": yl[0],
            "pH_N": -math.log10(hN),
            "pH_P": -math.log10(hP),
            "NADH_fraction": g("NADH") / (g("NADH") + g("NAD")),
            "cytc_reduced_fraction": g("c2") / (g("c2") + g("c3")),
            "QH2_fraction": g("QH2") / (g("QH2") + g("Q")),
            "O2_flux": J["C4"],
            "ATP_export_exchange": J["ANT"],
            "ATP_export_outer": -(Jf["ATP4"] + Jf["MgATP"]),
            "outer_potential_mV": -ev["v"] / self.f_mV,
            "K_N": g("K_N"), "Pi_N": g("Pi_N"), "ATP_N": g("ATP_N"), "ADP_N": g("ADP_N"),
            "ATP_P": g("ATP_P"), "ADP_P": g("ADP_P"), "AMP_P": g("AMP_P"), "Pi_P": g("Pi_P"),
            "K_P": g("K_P"), "O2_N": g("O2_N"), "O2_P": g("O2_P"), "O2_node": g("O2_node"),
            "Mg_free_N": mN, "Mg_free_P": mP,
        }
        for k in PROCESSES:
            out["J_" + k] = J[k]
            out["x_" + k] = X[k]
        Xf = self.face_x(ev)
        for name, j, x in zip(FACE_NAMES, ev["Jf"], Xf, strict=True):
            out["J_face_" + name] = j
            out["dissipation_face_" + name] = -j * x
        for k in PROCESSES:
            out["dissipation_" + k] = -J[k] * X[k]
        return out
