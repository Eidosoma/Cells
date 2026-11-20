"""States for the component references: the appendix's section 10 grid, interior points,
states next to each turnover's equilibrium, and the binding closure from totals to forms.

A state spec gives dpsi_mV, pH_N and pH_P, the reduced fractions (f_NAD, f_Q, f_c) of pools
whose totals are Table 1's unless given, ATP/ADP total ratios R_N and R_P, total phosphate
Pi_N and Pi_P, O2, free Mg_N and Mg_P, and K_N and K_P. ``full_state`` turns it into every form a
law reads, with Mg2+ and H+ binding at equilibrium (appendix section 0's binding set: Mg2+ binds
ATP and ADP; H+ binds phosphate only).

Engine rows are float64: every value of an exact state is rounded to the nearest double, and the
references are then evaluated at those doubles' exact values (``exact_from_floats``), so input
rounding never enters a comparison.
"""
from __future__ import annotations

from decimal import Decimal
from itertools import product

from .hp import DEC, precision

# Section 10's grid ranges ("lin" or "log" spacing for interior points).
RANGES = {
    "dpsi_mV": ("0", "250", "lin"),
    "pH_N": ("6.8", "8.2", "lin"),
    "pH_P": ("6.5", "7.6", "lin"),
    "f_NAD": ("0.01", "0.99", "lin"),
    "f_Q": ("0.01", "0.99", "lin"),
    "f_c": ("0.01", "0.99", "lin"),
    "R_N": ("1e-3", "1e3", "log"),
    "R_P": ("1e-3", "1e3", "log"),
    "Pi_N": ("1e-4", "2e-2", "log"),
    "Pi_P": ("1e-4", "2e-2", "log"),
    "O2": ("1e-7", "3e-4", "log"),
    "Mg_N": ("1e-4", "5e-3", "log"),
    "Mg_P": ("1e-4", "5e-3", "log"),
    "K_N": ("1e-2", "2e-1", "log"),
    "K_P": ("1e-2", "2e-1", "log"),
    # Section 10 of the second tag: AMP 1e-3 to 1 mM; free Mg2+ at each end. The external side
    # (E) takes the IMS's ranges, pH_P's 6.5-7.6 included (a reading of the tag, accepted).
    "AMP_P": ("1e-6", "1e-3", "log"),
    "AMP_E": ("1e-6", "1e-3", "log"),
    "R_E": ("1e-3", "1e3", "log"),
    "Pi_E": ("1e-4", "2e-2", "log"),
    "Mg_E": ("1e-4", "5e-3", "log"),
    "pH_E": ("6.5", "7.6", "lin"),
}
# Pool totals: Table 1's (M) at the corners; varied at interior points so that, for example,
# [c2+] + [c3+] differs from cytC_tot.
POOLS = {"NAD_tot": "2.97e-3", "Q_tot": "1.35e-3", "c_tot": "2.70e-3", "A_tot_N": "10e-3",
         "A_tot_P": "10e-3", "A_tot_E": "10e-3"}
POOL_RANGES = {
    "NAD_tot": ("1e-3", "5e-3", "log"),
    "Q_tot": ("0.5e-3", "3e-3", "log"),
    "c_tot": ("1e-3", "5e-3", "log"),
    "A_tot_N": ("2e-3", "15e-3", "log"),
    "A_tot_P": ("2e-3", "15e-3", "log"),
    "A_tot_E": ("2e-3", "15e-3", "log"),
}

BASE = {"dpsi_mV": "160", "pH_N": "7.4", "pH_P": "7.1", "f_NAD": "0.3", "f_Q": "0.4",
        "f_c": "0.3", "R_N": "3", "R_P": "30", "Pi_N": "5e-3", "Pi_P": "2e-3", "O2": "2.6e-5",
        "Mg_N": "1e-3", "Mg_P": "1e-3", "K_N": "0.13", "K_P": "0.14",
        "AMP_P": "1e-4", "AMP_E": "1e-5", "R_E": "10", "Pi_E": "5e-3", "Mg_E": "2e-3",
        "pH_E": "7.2", **POOLS}
# A second base with an acid matrix against the IMS, so the printed forms fail the other way.
BASE_B = {**BASE, "pH_N": "6.8", "pH_P": "7.0", "f_NAD": "0.6", "f_Q": "0.7", "f_c": "0.15",
          "R_N": "0.5", "R_P": "5", "Mg_N": "0.5e-3", "Mg_P": "2e-3", "Pi_N": "10e-3",
          "Pi_P": "1e-3", "O2": "1e-4", "K_N": "0.05", "K_P": "0.15", "AMP_P": "3e-4",
          "AMP_E": "3e-6", "R_E": "1", "Pi_E": "1e-2", "Mg_E": "0.3e-3", "pH_E": "7.5"}
# Per-law changes to the bases of the states next to equilibrium, so that Delta-psi there
# stays near the physiological range (complex III with half-reduced cytochrome c, complex IV
# with mostly oxidized).
NEAR_EQ_BASE = {"complex_III_eq7": {"f_c": "0.5"}, "complex_III_eq24": {"f_c": "0.5"},
                "complex_IV": {"f_c": "0.05"}}

CORNER_VARS = {
    "complex_I": ("dpsi_mV", "pH_N", "pH_P", "f_NAD", "f_Q"),
    "complex_III_eq7": ("dpsi_mV", "pH_N", "pH_P", "f_Q", "f_c"),
    "complex_III_eq24": ("dpsi_mV", "pH_N", "pH_P", "f_Q", "f_c", "Pi_N"),
    "complex_IV": ("dpsi_mV", "pH_N", "pH_P", "f_c", "O2"),
    "lumped_QO": ("dpsi_mV", "pH_N", "pH_P", "f_Q", "O2"),
    "atp_synthase": ("dpsi_mV", "pH_N", "pH_P", "R_N", "Pi_N", "Mg_N"),
    "nucleotide_exchange": ("dpsi_mV", "R_N", "R_P", "Mg_N", "Mg_P"),
    "phosphate_carrier": ("pH_N", "pH_P", "Pi_N", "Pi_P"),
    "k_h_exchange": ("pH_N", "pH_P", "K_N", "K_P"),
    "nadh_supply": ("Pi_N", "f_NAD", "pH_N"),
    "adenylate_kinase": ("R_P", "AMP_P", "Mg_P"),
    "outer_membrane": ("Mg_E", "Mg_P", "pH_E", "pH_P", "R_E", "R_P"),
}
INTERIOR_POOLS = {
    "complex_I": ("NAD_tot", "Q_tot"),
    "complex_III_eq7": ("Q_tot", "c_tot"),
    "complex_III_eq24": ("Q_tot", "c_tot"),
    "complex_IV": ("c_tot",),
    "lumped_QO": ("Q_tot",),
    "atp_synthase": ("A_tot_N",),
    "nucleotide_exchange": ("A_tot_N", "A_tot_P"),
    "phosphate_carrier": (),
    "k_h_exchange": (),
    "nadh_supply": ("NAD_tot",),
    "adenylate_kinase": ("A_tot_P",),
    "outer_membrane": ("A_tot_E", "A_tot_P", "AMP_E", "AMP_P", "Pi_E", "Pi_P"),
}
N_INTERIOR = 6
NEAR_EQ_TARGETS = ("-3", "-1", "-0.1", "-1e-3", "-1e-6", "0", "1e-6", "1e-3", "0.1", "1", "3")
PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def _halton(i: int, p: int) -> Decimal:
    """The radical inverse of i in base p, exactly as a Decimal at the working precision."""
    f, r = Decimal(1), Decimal(0)
    while i > 0:
        f = f / p
        r += f * (i % p)
        i //= p
    return r


def _place(lo: str, hi: str, kind: str, t: Decimal) -> Decimal:
    a, b = Decimal(lo), Decimal(hi)
    if kind == "lin":
        return a + t * (b - a)
    return a * ((t * (b / a).ln()).exp())


def full_state(P: dict, spec: dict) -> dict:
    """An exact state (Decimals) with every form, from a spec of strings or Decimals. Sides N
    (matrix), P (IMS) and E (the external buffer, for the outer membrane)."""
    n = DEC.n
    sp = {**BASE, **spec}
    s = {"dpsi_mV": n(sp["dpsi_mV"])}
    ln10 = n(10).ln()
    for side in ("N", "P", "E"):
        s[f"h_{side}"] = n(sp[f"h_{side}"]) if f"h_{side}" in spec else (-n(sp[f"pH_{side}"]) * ln10).exp()
    NAD_tot, Q_tot, c_tot = n(sp["NAD_tot"]), n(sp["Q_tot"]), n(sp["c_tot"])
    s["NADH_N"] = n(sp["f_NAD"]) * NAD_tot
    s["NAD_N"] = NAD_tot - s["NADH_N"]
    s["QH2_N"] = n(sp["f_Q"]) * Q_tot
    s["Q_N"] = Q_tot - s["QH2_N"]
    s["c2_P"] = n(sp["f_c"]) * c_tot
    s["c3_P"] = c_tot - s["c2_P"]
    s["O2_N"] = n(sp["O2"])
    # The supply's held pair (section 6): S_ox held at P's S_ox_held, S_red = 10^-0.10 r S_ox.
    s["S_ox_N"] = n(P["S_ox_held"])
    s["S_red_N"] = (-n("0.10") * ln10).exp() * n(P["r"]) * s["S_ox_N"]
    KATP, KADP, kdH = n(P["K_MgATP"]), n(P["K_MgADP"]), n(P["k_dH"])
    for side in ("N", "P", "E"):
        R = n(sp[f"R_{side}"])
        Atot = n(sp[f"A_tot_{side}"])
        Mg = n(sp[f"Mg_{side}"])
        s[f"Mg_{side}"] = Mg
        s[f"ATPtot_{side}"] = Atot * R / (1 + R)
        s[f"ADPtot_{side}"] = Atot - s[f"ATPtot_{side}"]
        s[f"ATP4_{side}"] = s[f"ATPtot_{side}"] / (1 + Mg / KATP)
        s[f"MgATP_{side}"] = s[f"ATP4_{side}"] * Mg / KATP
        s[f"ADP3_{side}"] = s[f"ADPtot_{side}"] / (1 + Mg / KADP)
        s[f"MgADP_{side}"] = s[f"ADP3_{side}"] * Mg / KADP
        Pi = n(sp[f"Pi_{side}"])
        h = s[f"h_{side}"]
        s[f"Pi_{side}"] = Pi
        s[f"HPO4_{side}"] = Pi * kdH / (kdH + h)
        s[f"H2PO4_{side}"] = Pi * h / (kdH + h)
        if side != "E":
            s[f"K_{side}"] = n(sp[f"K_{side}"])
        if side != "N":
            s[f"AMP_{side}"] = n(sp[f"AMP_{side}"])
    return s


def set_atp_free(P: dict, s: dict, side: str, atp4: Decimal) -> dict:
    """Return a copy of ``s`` with one side's Mg-free ATP set, its Mg-bound form and total kept
    at binding equilibrium."""
    KATP = DEC.n(P["K_MgATP"])
    t = dict(s)
    t[f"ATP4_{side}"] = atp4
    t[f"MgATP_{side}"] = atp4 * s[f"Mg_{side}"] / KATP
    t[f"ATPtot_{side}"] = t[f"ATP4_{side}"] + t[f"MgATP_{side}"]
    return t


def scale_side(P: dict, s: dict, side: str, factor: Decimal) -> dict:
    """Scale every adenylate and phosphate form and total on one side by ``factor``, binding kept
    (the same free Mg2+ and h)."""
    t = dict(s)
    for k in ("ATPtot", "ADPtot", "ATP4", "MgATP", "ADP3", "MgADP", "AMP", "Pi", "HPO4", "H2PO4"):
        t[f"{k}_{side}"] = s[f"{k}_{side}"] * factor
    return t


def set_phosphate(P: dict, s: dict, side: str, hpo4: Decimal) -> dict:
    """Return a copy of ``s`` with one side's phosphate set by its base form, binding kept."""
    kdH = DEC.n(P["k_dH"])
    t = dict(s)
    t[f"HPO4_{side}"] = hpo4
    t[f"H2PO4_{side}"] = hpo4 * s[f"h_{side}"] / kdH
    t[f"Pi_{side}"] = t[f"HPO4_{side}"] + t[f"H2PO4_{side}"]
    return t


def round_state(s: dict) -> dict:
    """Every value rounded to the nearest float64 (the engine's input)."""
    return {k: float(v) for k, v in s.items()}


def exact_from_floats(fs: dict) -> dict:
    return {k: Decimal(v) for k, v in fs.items()}


def binding_sensitivities(P: dict, s: dict) -> dict:
    """The binding closure's sensitivities at a state (lead's request of 20 November 2026).

    For each 1:1 binding pair, at fixed free ligand: d ln[form]/d ln[total] = 1 for both forms.
    At fixed total: d ln[form]/d ln[free ligand]. Mg2+ binds ATP4- and ADP3-; H+ binds HPO4(2-).
    """
    n = DEC.n
    KATP, KADP, kdH = n(P["K_MgATP"]), n(P["K_MgADP"]), n(P["k_dH"])
    out = {}
    for side in ("N", "P", "E"):
        if f"Mg_{side}" not in s or f"h_{side}" not in s:
            continue
        Mg, h = s[f"Mg_{side}"], s[f"h_{side}"]
        out[side] = {
            f"dln_ATP4_{side}/dln_ATPtot_{side}": n(1),
            f"dln_MgATP_{side}/dln_ATPtot_{side}": n(1),
            f"dln_ADP3_{side}/dln_ADPtot_{side}": n(1),
            f"dln_MgADP_{side}/dln_ADPtot_{side}": n(1),
            f"dln_HPO4_{side}/dln_Pi_{side}": n(1),
            f"dln_H2PO4_{side}/dln_Pi_{side}": n(1),
            f"dln_ATP4_{side}/dln_Mg_{side}": -Mg / (Mg + KATP),
            f"dln_MgATP_{side}/dln_Mg_{side}": KATP / (Mg + KATP),
            f"dln_ADP3_{side}/dln_Mg_{side}": -Mg / (Mg + KADP),
            f"dln_MgADP_{side}/dln_Mg_{side}": KADP / (Mg + KADP),
            f"dln_HPO4_{side}/dln_h_{side}": -h / (h + kdH),
            f"dln_H2PO4_{side}/dln_h_{side}": kdH / (h + kdH),
        }
    return out


def corner_specs(law_key: str):
    vars_ = CORNER_VARS[law_key]
    for combo in product((0, 1), repeat=len(vars_)):
        spec, tag = {}, []
        for v, hi in zip(vars_, combo):
            lo_s, hi_s, _ = RANGES[v]
            spec[v] = hi_s if hi else lo_s
            tag.append(f"{v}={spec[v]}")
        yield "corner:" + ",".join(tag), spec


def interior_specs(law_key: str):
    vars_ = CORNER_VARS[law_key] + INTERIOR_POOLS[law_key]
    with precision():
        for i in range(1, N_INTERIOR + 1):
            spec = {}
            for v, p in zip(vars_, PRIMES):
                lo, hi, kind = RANGES[v] if v in RANGES else POOL_RANGES[v]
                spec[v] = str(_place(lo, hi, kind, _halton(i, p)))
            yield f"interior:{i}", spec
