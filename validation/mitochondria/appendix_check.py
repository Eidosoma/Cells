"""The appendix's own check: every law of docs/MITOCHONDRIA_LAWS_APPENDIX.md against Beard 2005 as
printed, in 50-digit decimal arithmetic, with its numbers read from beard2005_cardiac.py.

It is the lane's check of its own algebra, not an independent reference: the component
references are written by an agent that reads neither this file nor the engine. What it shows,
over a random grid of potentials, both sides' pH and concentrations, and states placed next to
each turnover's equilibrium:
- every declared law is J = S (1 - e^x) with S > 0, so J x <= 0 and J = 0 at x = 0;
- each printed law that factors (Eqs. 3, 7, 9, 14 and 21) equals its declared form at every
  state (relative difference below 1e-40);
- each printed law that does not (Eqs. 1, 11, 16, 18 and 24) has a mismatch d = ln(B/A)/kappa - x
  equal to the appendix's closed form at every state, not constant, and runs against its own free
  energy at some states; the declared forms are D236's (frame B; Eq. 24 as phi_Pi x Eq. 7; the
  supply on a held reductant pair; adenylate kinase in base forms);
- two planted errors are caught: complex I's charge with the wrong sign, and the exchanger's
  voltage shares not summing to one;
- the appendix's typed parameters equal the organism file's; its free-energy table, potentials
  table and band terms equal those computed at the temperature the appendix states; the potential
  convention reproduces the binding owner's values at 310.15 K and the source's entries;
- every turnover's integer counts conserve charge with the declared valences and move the charge
  q the appendix states (planted: one count changed);
- the kinase's declared law, with the source's rate prefactor (1 + [Mg2+]_P/K_MgATP), equals the
  source's form on totals with K_tot(Mg) at every state, K_tot is K_AK at the matched Mg2+, and the
  form without the prefactor is caught; the supply's held ratio reproduces its reduced x, and
  holding the printed r shifts x by -0.10 ln 10;
- each law's S in the family proposed for the engine's form, anchored on the turnover's own
  affinity (and, for every law with a standard free energy, on its forward term), equals the
  declared S at every state. The affinity-anchored form agrees only because the free energies here
  use Table 2's values: with other standard potentials it keeps the backward term instead.

Run: PYTHONPATH=src:. python validation/mitochondria/appendix_check.py [--out FILE]. Seconds.
"""

import argparse
import json
import random
import re
import sys
from decimal import Decimal, getcontext
from pathlib import Path

from validation.mitochondria import beard2005_cardiac as source

getcontext().prec = 50
D = Decimal
APPENDIX = Path(__file__).resolve().parents[2] / "docs" / "MITOCHONDRIA_LAWS_APPENDIX.md"
ONE = D(1)
LN1E7 = D(10) ** 7
LN1E7 = LN1E7.ln()
TOLERANCE = D("1e-40")


def ln(v):
    return D(v).ln()


def exp(v):
    return D(v).exp()


def rt_units(kj_mol):
    return D(str(kj_mol)) * 1000 / D(repr(source.RT_J_mol()))


F_OVER_RT_PER_MV = (
    D(repr(source.DECLARED["faraday_C_mol"]))
    / (D(repr(source.DECLARED["gas_constant_J_mol_K"])) * D(repr(source.DECLARED["temperature_K"])))
    / 1000
)

P = {
    name: D(repr(source.parameter(name)))
    for name in source.TABLE_1
    if source.parameter(name) is not None
}
MM = D("1e-3")  # mM -> M
G_PH7 = {name: rt_units(r.dG0_kJ_mol) for name, r in source.TABLE_2.items()}
G_1M = {name: G_PH7[name] + r.scalar_protons * LN1E7 for name, r in source.TABLE_2.items()}
K_DH = P["k_dH"]
G_F_BASE = G_PH7["ATP"] - LN1E7 - (ONE + D("1e-7") / K_DH).ln()  # the appendix's law 2 entry
N_A = int(P["n_A"])


# ------------------------------------------------------------------ the laws (appendix, in M)


def c1(s, *, charge_sign=1):
    """Complex I, Eq. 3: (printed J, declared J, x, kappa)."""
    u, hn, hp = s["u"], s["H_N"], s["H_P"]
    x = (G_1M["C1"] + ln(s["NAD"] * s["QH2"] / (s["NADH"] * s["Q"])) - ln(hn)
         + 4 * ln(hp / hn) + charge_sign * 4 * u)  # fmt: skip
    dgh = u + ln(hp / hn)
    a = (
        P["X_C1"]
        * exp(-(G_PH7["C1"] + 4 * dgh - ln(hn / D("1e-7")) - ln(s["Q"] / s["QH2"])))
        * s["NADH"]
    )
    b = P["X_C1"] * s["NAD"]
    return a - b, a * (ONE - exp(x)), x, ONE, a, b


def _c3_x(s):
    u, hn, hp = s["u"], s["H_N"], s["H_P"]
    return (G_1M["C3"] + ln(s["Q"] * s["cred"] ** 2 / (s["QH2"] * s["cox"] ** 2)) + 2 * ln(hn)
            + 4 * ln(hp / hn) + 2 * u)  # fmt: skip


def c3_eq7(s):
    """Complex III without phosphate control, Eq. 7 (kappa 1/2, per QH2)."""
    u, hn, hp, x = s["u"], s["H_N"], s["H_P"], _c3_x(s)
    dgh = u + ln(hp / hn)
    expo = G_PH7["C3"] + 4 * dgh + 2 * ln(hn / D("1e-7")) - 2 * u + ln(s["Q"] / s["QH2"])
    a = P["X_C3"] * exp(-expo / 2) * s["cox"]
    b = P["X_C3"] * s["cred"]
    return a - b, a * (ONE - exp(x / 2)), x, D("0.5"), a, b


def phi_pi(s):
    """Eq. 24's phosphate activation, on total matrix Pi."""
    pi_tot = s["HPO4_N"] * (ONE + s["H_N"] / K_DH)
    return (ONE + pi_tot / (P["k_Pi3"] * MM)) / (ONE + pi_tot / (P["k_Pi4"] * MM))


def c3_eq24(s):
    """Complex III with phosphate control. Printed (Eq. 24): the 2RT ln([H+]_x/1e-7) term is
    dropped, and its two terms (a, b) give the mismatch. Declared (D236): Eq. 24 restored as
    phi_Pi x Eq. 7, the model as the source ran it."""
    u, hn, hp, x = s["u"], s["H_N"], s["H_P"], _c3_x(s)
    dgh = u + ln(hp / hn)
    phi = phi_pi(s)
    expo = G_PH7["C3"] + 4 * dgh - 2 * u + ln(s["Q"] / s["QH2"])
    a = P["X_C3"] * phi * exp(-expo / 2) * s["cox"]
    b = P["X_C3"] * phi * s["cred"]
    a7 = phi * c3_eq7(s)[4]
    return a - b, a7 * (ONE - exp(x / 2)), x, D("0.5"), a, b


def c4(s):
    """Complex IV, Eq. 9; the declared turnover is one O2 (four electrons), printed per 1/2 O2."""
    u, hn, hp = s["u"], s["H_N"], s["H_P"]
    x_half = (G_1M["C4"] + ln(s["cox"] ** 2 / (s["cred"] ** 2 * s["O2"].sqrt())) - 2 * ln(hn)
              + 2 * ln(hp / hn) + 4 * u)  # fmt: skip
    x = 2 * x_half  # per O2
    dgh = u + ln(hp / hn)
    pre = P["X_C4"] / (ONE + P["k_O2"] / s["O2"]) * s["cred"] / (s["cox"] + s["cred"])
    expo = G_PH7["C4"] + 2 * dgh - 2 * ln(hn / D("1e-7")) - ln(s["O2"]) / 2
    a = pre * exp(-expo / 2) * s["cred"]
    b = pre * exp(u) * s["cox"]
    printed_per_o2 = (a - b) / 2  # each printed turnover uses 1/2 O2
    return printed_per_o2, a / 2 * (ONE - exp(x / 4)), x, D("0.25"), a, b


def _mg(s):
    return s["ATP_N"] * s["Mg_N"] / P["K_MgATP"], s["ADP_N"] * s["Mg_N"] / P["K_MgADP"]


def f1(s, *, own_frame=False):
    """F1F0, Eq. 11, with Table 2's +36.03 kJ/mol. x in base forms (the declared entry), or in the
    source's own frame (total Pi, one scalar proton) when own_frame is set."""
    u, hn, hp = s["u"], s["H_N"], s["H_P"]
    pi_tot = s["HPO4_N"] * (ONE + hn / K_DH)
    if own_frame:
        x = (G_PH7["ATP"] + ln(s["ATP_N"] / (s["ADP_N"] * pi_tot)) - ln(hn / D("1e-7"))
             - N_A * (ln(hp / hn) + u))  # fmt: skip
    else:
        x = G_F_BASE + ln(s["ATP_N"] / (s["ADP_N"] * s["HPO4_N"] * hn)) - N_A * (ln(hp / hn) + u)
    mg_atp, mg_adp = _mg(s)
    dgh = u + ln(hp / hn)
    a = P["X_F1"] * exp(-(G_PH7["ATP"] - N_A * dgh)) * P["K_MgADP"] / P["K_MgATP"] * mg_adp * pi_tot
    b = P["X_F1"] * ONE * mg_atp
    return a - b, a * (ONE - exp(x)), x, ONE, a, b


SHARES = (D("0.35"), D("0.65"))  # Eq. 14's theta_P and theta_N


def ant(s, *, shares=SHARES):
    """The nucleotide exchanger, Eq. 14 (Mg-free ATP4- and ADP3-)."""
    u, (sp, sn) = s["u"], shares
    x = ln(s["ATP_P"] * s["ADP_N"] / (s["ATP_N"] * s["ADP_P"])) - u
    sigma = ONE / (ONE + P["k_mADP"] / s["ADP_P"])
    ap, bp = s["ADP_P"], s["ATP_P"] * exp(-sp * u)
    an, bn = s["ADP_N"], s["ATP_N"] * exp(sn * u)
    printed = P["X_ANT"] * (ap / (ap + bp) - an / (an + bn)) * sigma
    s_ = P["X_ANT"] * sigma * ap * bn / ((ap + bp) * (an + bn))
    return printed, s_ * (ONE - exp(x)), x, ONE, s_, s_ * exp(x)


def piht(s):
    """The phosphate carrier, Eq. 16, as printed ([H+]_x forward, [H+]_e backward)."""
    hn, hp = s["H_N"], s["H_P"]
    x = ln(s["HPO4_N"] * hn**2 / (s["HPO4_P"] * hp**2))
    h2_p, h2_n = hp * s["HPO4_P"] / K_DH, hn * s["HPO4_N"] / K_DH
    den = h2_p + P["k_PiHt"] * MM
    a = P["X_PiHt"] * h2_p * hn / den
    b = P["X_PiHt"] * h2_n * hp / den
    return a - b, a * (ONE - exp(x)), x, ONE, a, b


def kh(s):
    """The K+/H+ exchanger, Eq. 21."""
    hn, hp = s["H_N"], s["H_P"]
    x = ln(s["K_N"] * hp / (s["K_P"] * hn))
    a = P["X_KH"] * s["K_P"] * hn
    b = P["X_KH"] * s["K_N"] * hp
    return a - b, a * (ONE - exp(x)), x, ONE, a, b


H_REF = D(10) ** D(repr(-source.RULED["supply_reference_pH_N"]))  # the supply's reference h_N


def supply(s):
    """The NADH supply. Printed (Eq. 1): X phi (r [NAD] - [NADH]), relaxing to r at every pH.
    Declared (D236): S_red + NAD -> S_ox + NADH + H+ with a held neutral pair at [S_ox]/[S_red] =
    10^(pH_ref - 7)/r, so x = ln([NADH]/(r [NAD])) + ln(h_N/h_ref), and J = A (1 - e^x) with A the
    printed forward term."""
    pi_tot = s["HPO4_N"] * (ONE + s["H_N"] / K_DH)
    phi = (ONE + pi_tot / (P["k_Pi1"] * MM)) / (ONE + pi_tot / (P["k_Pi2"] * MM))
    x = ln(s["NADH"] / (P["r"] * s["NAD"])) + ln(s["H_N"] / H_REF)
    a = P["X_DH"] * phi * P["r"] * s["NAD"]
    b = P["X_DH"] * phi * s["NADH"]
    return a - b, a * (ONE - exp(x)), x, ONE, a, b


K_BASE = D(repr(source.ak_base_constant()))


def ak(s, *, prefactor=True):
    """Adenylate kinase at P. Printed (Eq. 18): on totals with K_AK. Declared (D236): in base
    forms with the source's rate, X_AK (1 + [Mg2+]_P/K_MgATP) (K_base [ADP3-]^2 - [AMP2-][ATP4-]),
    K_base matched at the state-3 buffer's free Mg2+ (prefactor=False: the planted form without
    the rate's prefactor)."""
    mg = s["Mg_P"]
    atp_tot = s["ATP_P"] * (ONE + mg / P["K_MgATP"])
    adp_tot = s["ADP_P"] * (ONE + mg / P["K_MgADP"])
    x = ln(s["ATP_P"] * s["AMP_P"] / (K_BASE * s["ADP_P"] ** 2))
    a = P["X_AK"] * P["K_AK"] * adp_tot**2
    b = P["X_AK"] * s["AMP_P"] * atp_tot
    rate = (ONE + mg / P["K_MgATP"]) if prefactor else ONE
    declared_a = P["X_AK"] * rate * K_BASE * s["ADP_P"] ** 2
    return a - b, declared_a * (ONE - exp(x)), x, ONE, a, b


def ak_totals(s):
    """The declared kinase in the source's form on totals: X_AK (K_tot [ADP]_tot^2 - [AMP]
    [ATP]_tot), K_tot = K_base (1 + m/K_MgATP)/(1 + m/K_MgADP)^2 at the IMS free Mg2+ m."""
    mg = s["Mg_P"]
    p_atp, p_adp = ONE + mg / P["K_MgATP"], ONE + mg / P["K_MgADP"]
    k_tot = K_BASE * p_atp / p_adp**2
    return P["X_AK"] * (k_tot * (s["ADP_P"] * p_adp) ** 2 - s["AMP_P"] * s["ATP_P"] * p_atp)


# The appendix's closed forms of each failing law's mismatch, d = ln(B/A)/kappa - x.
def d_eq24(s):
    return -2 * ln(s["H_N"] / D("1e-7"))


def d_eq11(s):
    hn = s["H_N"]
    return ln(hn / D("1e-7")) - ln((ONE + hn / K_DH) / (ONE + D("1e-7") / K_DH))


def d_eq11_own_frame(s):
    return ln(s["H_N"] / D("1e-7"))


def d_eq16(s):
    return 2 * ln(s["H_P"] / s["H_N"])


def d_eq1(s):
    return -ln(s["H_N"] / H_REF)


def d_eq18(s):
    mg = s["Mg_P"]
    return ln((ONE + mg / P["K_MgATP"]) / (ONE + mg / P["K_MgADP"]) ** 2) + ln(K_BASE / P["K_AK"])


PASSING = {"C1 (Eq. 3)": c1, "C3 (Eq. 7)": c3_eq7, "C4 (Eq. 9)": c4, "ANT (Eq. 14)": ant,
           "KH (Eq. 21)": kh}  # fmt: skip
FAILING = {"F1 (Eq. 11)": (f1, d_eq11, "H_N"), "PiHt (Eq. 16)": (piht, d_eq16, "H_N"),
           "C3 (Eq. 24)": (c3_eq24, d_eq24, "H_N"), "Supply (Eq. 1)": (supply, d_eq1, "H_N"),
           "AK (Eq. 18)": (ak, d_eq18, "Mg_P")}  # fmt: skip


# ------------------------------------------------------------------ the turnovers' counts

# The appendix's turnovers: {law: ({(species, end): nu}, q)}, water left out (neutral). F1 at the
# source's n_A = 3; complex IV per O2.
TURNOVERS = {
    "C1": ({("NADH", "N"): -1, ("Q", "N"): -1, ("NAD", "N"): 1, ("QH2", "N"): 1, ("H", "N"): -5,
            ("H", "P"): 4}, 4),
    "C3": ({("QH2", "N"): -1, ("Q", "N"): 1, ("cytc_ox", "P"): -2, ("cytc_red", "P"): 2,
            ("H", "N"): -2, ("H", "P"): 4}, 2),
    "C4": ({("O2", "N"): -1, ("cytc_red", "P"): -4, ("cytc_ox", "P"): 4, ("H", "N"): -8,
            ("H", "P"): 4}, 8),
    "QO": ({("QH2", "N"): -2, ("Q", "N"): 2, ("O2", "N"): -1, ("H", "N"): -12, ("H", "P"): 12}, 12),
    "F1": ({("ADP", "N"): -1, ("HPO4", "N"): -1, ("ATP", "N"): 1, ("H", "N"): N_A - 1,
            ("H", "P"): -N_A}, -N_A),
    "ANT": ({("ATP", "N"): -1, ("ATP", "P"): 1, ("ADP", "P"): -1, ("ADP", "N"): 1}, -1),
    "PiHt": ({("HPO4", "P"): -1, ("HPO4", "N"): 1, ("H", "P"): -2, ("H", "N"): 2}, 0),
    "KH": ({("K", "P"): -1, ("K", "N"): 1, ("H", "N"): -1, ("H", "P"): 1}, 0),
    "Supply": ({("S_red", "N"): -1, ("NAD", "N"): -1, ("S_ox", "N"): 1, ("NADH", "N"): 1,
                ("H", "N"): 1}, 0),
    "AK": ({("ADP", "P"): -2, ("ATP", "P"): 1, ("AMP", "P"): 1}, 0),
}  # fmt: skip


def turnover_errors(turnovers=TURNOVERS):
    """Each turnover's charge sum (zero) and its charge moved N to P (the appendix's q)."""
    z, out = source.DECLARED["valence"], []
    for law, (nu, q) in turnovers.items():
        total = sum(n * z[s] for (s, _), n in nu.items())
        moved = sum(n * z[s] for (s, end), n in nu.items() if end == "P")
        if total != 0 or moved != q:
            out.append(f"{law}: charge sum {total}, charge moved {moved} (appendix q = {q})")
    return out


# ------------------------------------------------------------------ the engine form's instances


def _logistic(z):
    return ONE / (ONE + z)


def _share(x, n):
    """The affinity-share factor 1 / sum_{i<n} e^(i x / n): (1 - e^(x/n)) / (1 - e^x)."""
    return ONE / sum(exp(D(i) * x / n) for i in range(n))


def instances(s):
    """{law: (declared S, [S of each instance])}: the proposed family's instances of each law,
    S = k prod c^o e^(zeta u) prod (1 + K prod c^q e^(eta u))^(-s) e^(-theta x) / sum_{i<n}
    e^(i x/n), the affinity-anchored one first, then the forward-anchored one where it differs."""
    u, hn, hp = s["u"], s["H_N"], s["H_P"]
    out = {}
    _, _, x, _, a, _ = c1(s)
    fwd = (P["X_C1"] * exp(-G_PH7["C1"]) * D(10) ** 7 * s["NADH"] * s["Q"] / s["QH2"]
           * hn**5 / hp**4 * exp(-4 * u))  # fmt: skip
    out["C1"] = (a, [P["X_C1"] * s["NAD"] * exp(-x), fwd])
    _, _, x, _, a, _ = c3_eq7(s)
    fwd = (P["X_C3"] * exp(-G_PH7["C3"] / 2) * D("1e-7") * s["cox"] * hn / hp**2
           * (s["QH2"] / s["Q"]).sqrt() * exp(-u))  # fmt: skip
    out["C3 (Eq. 7)"] = (a * _share(x, 2), [P["X_C3"] * s["cred"] * exp(-x / 2) * _share(x, 2),
                                            fwd * _share(x, 2)])  # fmt: skip
    _, declared, x, _, _, _ = c3_eq24(s)
    phi = phi_pi(s)
    out["C3 (Eq. 24 as phi x Eq. 7)"] = (
        declared / (ONE - exp(x)),
        [phi * P["X_C3"] * s["cred"] * exp(-x / 2) * _share(x, 2),
         phi * c3_eq7(s)[4] * _share(x, 2)],
    )  # fmt: skip
    _, _, x, _, a, _ = c4(s)
    sat = _logistic(P["k_O2"] / s["O2"]) * _logistic(s["cox"] / s["cred"])
    fwd = (P["X_C4"] * sat * exp(-G_PH7["C4"] / 2) * D(10) ** 7 * s["cred"] * hn**2 / hp
           * s["O2"] ** D("0.25") * exp(-u))  # fmt: skip
    out["C4 (per O2)"] = (a / 2 * _share(x, 4),
                          [P["X_C4"] / 2 * sat * s["cox"] * exp(u) * exp(-x / 4) * _share(x, 4),
                           fwd / 2 * _share(x, 4)])  # fmt: skip
    _, _, x, _, a, _ = f1(s)
    mg_atp, mg_adp = _mg(s)
    pi_tot = s["HPO4_N"] * (ONE + hn / K_DH)
    anchored = (P["X_F1"] * mg_atp * D("1e-7") / hn * (ONE + hn / K_DH)
                / (ONE + D("1e-7") / K_DH) * exp(-x))  # fmt: skip
    fwd = (P["X_F1"] * exp(-G_PH7["ATP"]) * P["K_MgADP"] / P["K_MgATP"] * mg_adp * pi_tot
           * (hp / hn) ** N_A * exp(N_A * u))  # fmt: skip
    out["F1 (balanced)"] = (a, [anchored, fwd])
    _, _, x, _, a, _ = ant(s)
    th_p, th_n = D("0.35"), D("0.65")
    out["ANT"] = (a, [P["X_ANT"] * _logistic(P["k_mADP"] / s["ADP_P"])
                      * _logistic(s["ATP_P"] / s["ADP_P"] * exp(-th_p * u))
                      * _logistic(s["ADP_N"] / s["ATP_N"] * exp(-th_n * u))])  # fmt: skip
    _, _, x, _, a, _ = piht(s)
    h2_p = hp * s["HPO4_P"] / K_DH
    out["PiHt (balanced)"] = (a, [P["X_PiHt"] * hn * _logistic(P["k_PiHt"] * MM / h2_p)])
    _, _, x, _, a, _ = kh(s)
    out["KH"] = (a, [P["X_KH"] * s["K_P"] * hn])
    _, _, x, _, a, _ = supply(s)
    pi_tot = s["HPO4_N"] * (ONE + hn / K_DH)
    act = (ONE + pi_tot / (P["k_Pi1"] * MM)) * _logistic(pi_tot / (P["k_Pi2"] * MM))
    out["Supply (held pair)"] = (a, [P["X_DH"] * act * s["NADH"] * hn / H_REF * exp(-x)])
    _, declared, x, _, _, _ = ak(s)
    rate = ONE + s["Mg_P"] / P["K_MgATP"]
    out["AK (base forms)"] = (declared / (ONE - exp(x)),
                              [P["X_AK"] * rate * s["AMP_P"] * s["ATP_P"] * exp(-x)])  # fmt: skip
    return out


# ------------------------------------------------------------------ the grid


def _log_uniform(rng, low, high):
    return D(repr(low * (high / low) ** rng.random()))


def state(rng):
    """One random state (concentrations in M, u = F dPsi / RT) over the screen's domain
    (docs/CORE_SEAMS_STEP0.md §1.2's Beard ranges)."""

    def fraction():
        return D(repr(0.01 + 0.98 * rng.random()))

    nad_tot, q_tot, c_tot = (P[k] * MM for k in ("NAD_tot", "Q_tot", "cytC_tot"))
    f_nadh, f_qh2, f_red = fraction(), fraction(), fraction()
    s = dict(
        u=D(repr(250.0 * rng.random())) * F_OVER_RT_PER_MV,
        H_N=D(10) ** D(repr(-(6.8 + 1.4 * rng.random()))),
        H_P=D(10) ** D(repr(-(6.5 + 1.1 * rng.random()))),
        NADH=nad_tot * f_nadh, NAD=nad_tot * (ONE - f_nadh),
        QH2=q_tot * f_qh2, Q=q_tot * (ONE - f_qh2),
        cred=c_tot * f_red, cox=c_tot * (ONE - f_red),
        O2=_log_uniform(rng, 1e-7, 3e-4),
        Mg_N=_log_uniform(rng, 1e-4, 5e-3),
        HPO4_N=_log_uniform(rng, 1e-4, 2e-2), HPO4_P=_log_uniform(rng, 1e-4, 2e-2),
        K_N=_log_uniform(rng, 1e-2, 2e-1), K_P=_log_uniform(rng, 1e-2, 2e-1),
        Mg_P=_log_uniform(rng, 1e-4, 5e-3), AMP_P=_log_uniform(rng, 1e-6, 1e-3),
    )  # fmt: skip
    for side in ("N", "P"):
        total = _log_uniform(rng, 1e-4, 1e-2)
        ratio = _log_uniform(rng, 1e-3, 1e3)  # ATP/ADP
        s[f"ATP_{side}"] = total * ratio / (ONE + ratio)
        s[f"ADP_{side}"] = total / (ONE + ratio)
    return s


def near_equilibrium(law, s, target):
    """s with one concentration moved so that the law's declared x equals target (an exact
    solve: x is linear in the moved log concentration with coefficient nu)."""
    moved = {c1: ("NAD", 1), c3_eq7: ("Q", 1), c3_eq24: ("Q", 1), c4: ("O2", -1), f1: ("ATP_N", 1),
             ant: ("ATP_P", 1), piht: ("HPO4_N", 1), kh: ("K_N", 1), supply: ("NADH", 1),
             ak: ("AMP_P", 1)}[law]  # fmt: skip
    key, nu = moved
    out = dict(s)
    x = law(out)[2]
    out[key] = out[key] * exp((D(target) - x) / nu)
    return out


# ------------------------------------------------------------------ the checks


def check(n_states=400, seed=20261120):
    rng = random.Random(seed)
    states = [state(rng) for _ in range(n_states)]
    targets = ("-3", "-0.5", "-0.01", "0", "0.01", "0.5", "3")
    report, ok = {}, True
    all_laws = {**PASSING, **{k: v[0] for k, v in FAILING.items()}}
    for name, law in all_laws.items():
        grid = states + [near_equilibrium(law, s, t) for s in states[:60] for t in targets]
        worst_sign, at_zero, wrong_printed = D(0), D(0), 0
        for s in grid:
            printed, declared, x, kappa, a, b = law(s)
            if declared * x > 0:
                worst_sign = max(worst_sign, declared * x)
            if abs(x) < D("1e-30"):  # Relative to the one-way flux: J vanishes at x = 0.
                at_zero = max(at_zero, abs(declared) / max(abs(a), abs(b)))
            if printed * x > 0 and abs(x) > D("1e-9"):
                wrong_printed += 1
        entry = dict(
            states=len(grid),
            declared_wrong_sign=str(worst_sign),
            declared_at_zero=f"{at_zero:.3e}",
            printed_wrong_sign_states=wrong_printed,
        )
        ok &= worst_sign == 0 and at_zero < TOLERANCE
        if name in PASSING:  # Relative to the one-way fluxes, so no cancellation near x = 0.
            worst = max(abs(p - d) / max(abs(a), abs(b))
                        for p, d, _, _, a, b in map(law, grid))  # fmt: skip
            entry["printed_vs_declared"] = f"{worst:.3e}"
            ok &= worst < TOLERANCE and wrong_printed == 0
        else:
            _, closed, _ = FAILING[name]
            mismatch, values = D(0), []
            for s in grid:
                _, _, x, kappa, a, b = law(s)
                d = ln(b / a) / kappa - x
                values.append(d)
                mismatch = max(mismatch, abs(d - closed(s)))
            spread = max(values) - min(values)
            entry |= dict(mismatch_vs_closed_form=f"{mismatch:.3e}", d_spread=f"{spread:.4f}")
            ok &= mismatch < TOLERANCE and spread > D("0.1") and wrong_printed > 0
        report[name] = entry
    # Eq. 11 in the source's own frame (total Pi as one species): the mismatch is one proton.
    own = max(abs(_own_frame_d(s) - d_eq11_own_frame(s)) for s in states)
    report["F1 (Eq. 11), the source's frame"] = dict(mismatch_vs_closed_form=f"{own:.3e}")
    ok &= own < TOLERANCE
    # Planted errors, each must be caught.
    planted_c1 = max(abs(p - d) / max(abs(a), abs(b))
                     for p, d, _, _, a, b in (c1(s, charge_sign=-1) for s in states))  # fmt: skip
    bad = (D("0.35"), D("0.60"))
    planted_ant = max(abs(p - d) / max(abs(a), abs(b))
                      for p, d, _, _, a, b in (ant(s, shares=bad) for s in states))  # fmt: skip
    report["planted"] = dict(
        c1_charge_sign=f"{planted_c1:.3e}", ant_shares_0_95=f"{planted_ant:.3e}"
    )
    ok &= planted_c1 > D("1e-3") and planted_ant > D("1e-3")
    errors = appendix_errors()
    report["appendix_numbers"] = errors or "agree"
    ok &= not errors
    errors = turnover_errors()
    planted = dict(TURNOVERS)
    planted["F1"] = ({**TURNOVERS["F1"][0], ("H", "N"): N_A}, -N_A)  # the consumed proton dropped
    report["turnovers"] = errors or "every count conserves charge and moves the appendix's q"
    report["turnovers_planted"] = turnover_errors(planted) or "NOT CAUGHT"
    ok &= not errors and bool(turnover_errors(planted))
    worst = {}
    for st in states:
        for law, (declared, forms) in instances(st).items():
            for k, value in enumerate(forms):
                key = f"{law}, instance {k + 1}"
                worst[key] = max(worst.get(key, D(0)), abs(value - declared) / declared)
    report["engine_form_instances"] = {k: f"{v:.3e}" for k, v in worst.items()}
    ok &= all(v < TOLERANCE for v in worst.values())
    t_world, t_appendix = source.DECLARED["temperature_K"], appendix_temperature_K()
    report["temperatures_K"] = dict(organism_file=t_world, appendix=t_appendix)
    entries = entries_RT(t_world)
    report[f"entries_RT_at_{t_world}_K"] = {k: f"{v:.6f}" for k, v in entries.items()}
    direct = direct_entries_RT(t_world)
    gap = max(abs(entries[k] - direct[k]) for k in entries)
    report["entries_convention_vs_source"] = f"{gap:.3e}"
    ok &= gap < D("1e-9")
    # The kinase's rate (D236): the declared law equals the source's form on totals with K_tot(Mg)
    # at every state, and at the matched Mg2+ K_tot is K_AK; the form without the prefactor is a
    # plant that must differ (by the factor 1 + [Mg2+]/K_MgATP).
    worst, planted = D(0), D(1)
    for st in states:
        _, declared, _, _, a, b = ak(st)
        worst = max(worst, abs(declared - ak_totals(st)) / max(abs(a), abs(b)))
        no_prefactor = ak(st, prefactor=False)[1]
        if declared != 0:
            planted = min(planted, abs(no_prefactor / declared - ONE))
    m = D(repr(source.ak_match_free_Mg_mM())) * MM
    k_tot_match = K_BASE * (ONE + m / P["K_MgATP"]) / (ONE + m / P["K_MgADP"]) ** 2
    report["kinase_rate"] = dict(
        declared_vs_totals_form=f"{worst:.3e}",
        k_tot_at_match_minus_K_AK=f"{abs(k_tot_match - P['K_AK']):.3e}",
        rate_factor_at_match=f"{ONE + m / P['K_MgATP']:.13f}",
        planted_without_prefactor_least_relative_difference=f"{planted:.3e}",
    )
    ok &= worst < TOLERANCE and abs(k_tot_match - P["K_AK"]) < D("1e-15") and planted > D("0.5")
    # The supply's anchor (option A): with the convention's potentials (doubles) and the held ratio
    # S_red/S_ox = 10^-0.10 r, x equals the reduced form; holding the printed r shifts it.
    mu, x_gap, x_shift = potentials(t_world), D(0), set()
    held = D(repr(source.held_pair_ratio()))  # S_ox/S_red
    for st in states:
        nu = ENTRIES["§6, per NADH"]
        base = sum(n * mu[sp] for sp, n in nu.items()) + ln(st["NADH"] / st["NAD"]) + ln(st["H_N"])
        x_gap = max(x_gap, abs(base + ln(held) - supply(st)[2]))
        x_shift.add(f"{base + ln(ONE / P['r']) - supply(st)[2]:.12f}")
    report["supply_anchor"] = dict(
        x_vs_reduced_form=f"{x_gap:.3e}", planted_r_shift=sorted(x_shift)
    )
    ok &= x_gap < D("1e-12") and x_shift == {f"{-D('0.1') * D(10).ln():.12f}"}
    mu310 = potentials(310.15)
    gap = max(abs(mu310[k] - D(v)) for k, v in CONVENTION_310.items())
    report["convention_file_at_310.15_K"] = f"{gap:.3e}"
    ok &= gap < D("1e-9")
    report[f"potentials_RT_at_{t_world}_K"] = {
        k: f"{v:.9f}" for k, v in potentials(t_world).items()
    }
    report[f"band_terms_at_{t_world}_K"] = {k: f"{v:.3f}" for k, v in band_terms(t_world).items()}
    return ok, report


def _number(text):
    return float(text.replace("\u2212", "-").replace("+", "").replace("\u2014", "nan"))


# Each entry's net conversion (the transport legs cancel; water is never a row).
ENTRIES = {
    "§1.1, per NADH": {"NADH": -1, "Q": -1, "H": -1, "NAD": 1, "QH2": 1},
    "§1.2, per QH₂": {"QH2": -1, "cytc_ox": -2, "Q": 1, "cytc_red": 2, "H": 2},
    "§1.3, per O₂": {"O2": -1, "cytc_red": -4, "H": -4, "cytc_ox": 4},
    "§1.4, per O₂": {"QH2": -2, "O2": -1, "Q": 2},
    "§2, per ATP": {"ADP": -1, "HPO4": -1, "H": -1, "ATP": 1},
    "§6, per NADH": {"S_red": -1, "NAD": -1, "S_ox": 1, "NADH": 1, "H": 1},
    "§7, per 2 ADP": {"ADP": -2, "ATP": 1, "AMP": 1},
}  # fmt: skip


def potentials(temperature_K):
    """The species' mu°/RT at 1 M (the organism file's convention), as Decimals."""
    return {k: D(repr(v)) for k, v in source.standard_potentials_RT(temperature_K).items()}


def entries_RT(temperature_K):
    """The appendix's free-energy entries (its §8 table, in RT, every species at 1 M) at a
    temperature in K, from the convention's potentials."""
    mu = potentials(temperature_K)
    return {key: sum(n * mu[sp] for sp, n in nu.items()) for key, nu in ENTRIES.items()}


def direct_entries_RT(temperature_K):
    """The same entries straight from the source's values (Table 2 at pH 7 moved to 1 M, the
    synthesis matched at pH 7 through k_dH, the supply's declared 0 at pH 7, K_base): the
    convention must reproduce them."""
    rt = D(repr(source.DECLARED["gas_constant_J_mol_K"])) * D(repr(temperature_K))
    g = {name: D(str(r.dG0_kJ_mol)) * 1000 / rt for name, r in source.TABLE_2.items()}
    g1 = {name: g[name] + r.scalar_protons * LN1E7 for name, r in source.TABLE_2.items()}
    return {"§1.1, per NADH": g1["C1"], "§1.2, per QH₂": g1["C3"], "§1.3, per O₂": 2 * g1["C4"],
            "§1.4, per O₂": 2 * (g["C3"] + g["C4"]),
            "§2, per ATP": g["ATP"] - LN1E7 - (ONE + D("1e-7") / K_DH).ln(),
            "§6, per NADH": LN1E7, "§7, per 2 ADP": -K_BASE.ln()}  # fmt: skip


def band_terms(temperature_K):
    """The band term M of each law's mode (the references' rounding scale for x): sum over its
    rows, each end counted, of |nu| (|mu°|/RT + ln 1000), at the convention's potentials."""
    mu, ln1000 = potentials(temperature_K), D(1000).ln()
    return {law: sum(abs(n) * (abs(mu[sp]) + ln1000) for (sp, _), n in nu.items())
            for law, (nu, _) in TURNOVERS.items()}  # fmt: skip


# The binding owner's convention file (cells.potential_set.beard2005@1, 20 November 2026), its values at 310.15 K.
CONVENTION_310 = dict(cytc_red="39.955405547706", QH2="60.289353662720", NADH="103.308282037566",
                      S_red="87.190186386608", ATP="-2.592286211096", MgATP="-13.229742938712",
                      MgADP="-7.966185778017", H2PO4="-15.542437799191")  # fmt: skip


def appendix_temperature_K(path=APPENDIX):
    """The temperature the appendix states (its §0: "T = ... K")."""
    return float(re.search(r"^- (?:\*\*)?T = ([0-9.]+) K", path.read_text(), re.M).group(1))


def appendix_errors(path=APPENDIX):
    """The appendix's typed numbers against this check's and the organism file's: every row of
    its parameter table (both columns), and the RT column of its free-energy table at the
    temperature the appendix itself states (the organism file's may differ between tags)."""
    text, out = path.read_text(), []
    block = text.split("<!-- parameters -->")[1].split("<!-- /parameters -->")[0]
    rows = re.findall(r"^\| `(\w+)` \| [^|]+ \| ([^|]+) \| ([^|]+) \|", block, re.M)
    for name, with_pi, without in rows:
        for column, typed in ((True, with_pi), (False, without)):
            value, typed = source.parameter(name, pi_control=column), _number(typed.strip())
            if value is None:
                if typed == typed:  # not nan
                    out.append(f"{name}: the appendix types {typed} where the source prints a dash")
            elif abs(typed - value) > 1e-12 * abs(value):
                out.append(f"{name} (pi_control={column}): appendix {typed}, organism file {value}")
    if len(rows) < 20:
        out.append(f"the parameter table has {len(rows)} rows")
    t = appendix_temperature_K(path)
    for key, value in entries_RT(t).items():
        line = next((ln_ for ln_ in text.splitlines() if ln_.startswith(f"| {key} |")), None)
        if line is None:
            out.append(f"the free-energy table has no row {key!r}")
            continue
        typed = _number(line.rstrip(" |").rsplit("|", 1)[1].strip())
        if abs(typed - float(value)) > 5e-5:
            out.append(f"free energy {key}: appendix {typed} RT, computed {float(value):.4f}")
    # The kinase's constant and its match (D236): printed in section 7 and section 9, each to 9
    # decimals or more, and equal to the derived one to its printed digits.
    for name, derived in (("K_base", K_BASE), ("m", D(repr(source.ak_match_free_Mg_mM())))):
        pattern = {
            "K_base": r"(?:K_base|K_MgATP\)) = \**([0-9]\.[0-9]+)",  # also "...K_MgATP) = **K**"
            "m": r"\bm = ([0-9]\.[0-9]+) mM",
        }[name]
        typed_values = re.findall(pattern, text)
        if len(typed_values) < 2:
            out.append(f"the appendix prints {name} {len(typed_values)} time(s), not in §7 and §9")
        short = [v for v in typed_values if len(v.split(".")[1]) < 9]
        if short:  # The binding owner's seam-E check admits only the derived value, not a rounding.
            out.append(f"the appendix prints {name} to fewer than 9 decimals: {short}")
        for v in typed_values:
            if abs(D(v) - derived) > D(5) * D(10) ** -(len(v.split(".")[1]) + 1):
                out.append(f"{name}: the appendix prints {v}, derived {derived}")
    if "<!-- potentials -->" in text:
        block = text.split("<!-- potentials -->")[1].split("<!-- /potentials -->")[0]
        typed_mu = dict(re.findall(r"^\| `(\w+)` \| ([^|]+) \|", block, re.M))
        mu = potentials(t)
        if set(typed_mu) != set(mu):
            out.append(f"the potentials table lists {sorted(typed_mu)}, not {sorted(mu)}")
        for sp, value in typed_mu.items():
            if sp in mu and abs(_number(value.strip()) - float(mu[sp])) > 2e-9:
                out.append(f"potential {sp}: appendix {value.strip()}, computed {float(mu[sp])}")
    if "<!-- bands -->" in text:
        block = text.split("<!-- bands -->")[1].split("<!-- /bands -->")[0]
        typed_m = dict(re.findall(r"^\| (\w+) \| ([0-9][0-9.]*) \|", block, re.M))
        bands = band_terms(t)
        for law, value in typed_m.items():
            if law not in bands or abs(_number(value.strip()) - float(bands[law])) > 5e-3:
                out.append(f"band M {law}: appendix {value.strip()}, computed {bands.get(law)}")
    return out


def _own_frame_d(s):
    _, _, x, _, a, b = f1(s, own_frame=True)
    return ln(b / a) - x


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="write the report as JSON here")
    parser.add_argument("--states", type=int, default=400)
    args = parser.parse_args(argv)
    ok, report = check(args.states)
    text = json.dumps(dict(passed=bool(ok), report=report), indent=1)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
