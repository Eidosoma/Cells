"""R2's declared constants, derived at 50 digits and rounded once.

Everything here follows the laws appendix at tag mito-laws-appendix-2026-11-20b:
- section 0: T = 298.15 K, and R and F exact SI (R = N_A k_B, F = N_A e);
- section 2: the synthesis entry,
  Delta G deg_F = Delta G deg_ATP + RT ln 1e-7 - RT ln(1 + 1e-7 M/k_dH);
- section 7: the matched free Mg2+ m and K_base = K_AK (1 + m/K_MgADP)^2/(1 + m/K_MgATP);
- section 9: the potential convention (each reaction fixes one species, in the stated order) and
  the free-energy entries;
- section 10: the band term M.

``printed()`` holds the appendix's printed values, which ``check_printed`` compares with these
derivations (the fast test runs it). Nothing here reads engine code.
"""

import json
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 50

HERE = Path(__file__).resolve().parent
DECLARATION = HERE / "declaration.json"

N_A = Decimal("6.02214076e23")
K_B = Decimal("1.380649e-23")
E_CHARGE = Decimal("1.602176634e-19")
R_EXACT = N_A * K_B
F_EXACT = N_A * E_CHARGE


def load_declaration(path=DECLARATION):
    with open(path) as stream:
        return json.load(stream)


def _d(value):
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


def _ln(x):
    return Decimal(x).ln()


def derived(declaration=None):
    """The declared derivations at 50 digits, as Decimals."""
    decl = declaration or load_declaration()
    p = {k: v["value"] for k, v in decl["parameters"].items()}
    T = _d(decl["temperature_K"]["value"])
    RT = R_EXACT * T  # J mol-1
    f_mV = F_EXACT / RT / 1000  # F/RT per mV
    ln1e7 = _ln(Decimal("1e7"))
    K_MgATP = _d(p["K_MgATP"])
    K_MgADP = _d(p["K_MgADP"])
    k_dH = _d(p["k_dH"])
    # Section 7: the positive root of m^2 + (K_MgADP + 1.3 - 5.0) m - 5.0 K_MgADP = 0, in mM.
    kd_mM = K_MgADP * 1000
    mg = _d(p["state3_Mg_tot_match"])
    adp = _d(p["state3_ADP_tot_match"])
    b = kd_mM + adp - mg
    m_mM = (-b + (b * b + 4 * mg * kd_mM).sqrt()) / 2
    m = m_mM / 1000
    prefactor = 1 + m / K_MgATP
    K_base = _d(p["K_AK"]) * (1 + m / K_MgADP) ** 2 / prefactor
    # Section 2: the synthesis entry matched to the base form at pH 7.
    dG0_ATP = _d(p["dG0_ATP_pH7"]) * 1000
    dG0_F = dG0_ATP + RT * _ln(Decimal("1e-7")) - RT * _ln(1 + Decimal("1e-7") / k_dH)
    # Section 9: the species' potentials (mu deg/RT at 1 M), each reaction fixing one species.
    x0_C4 = 1000 * 2 * _d(p["dG0_C4_pH7_per_half_O2"]) / RT + (-4) * ln1e7
    zero = ("H", "K", "Mg", "O2", "NAD", "Q", "cytc_ox", "ADP", "HPO4", "S_ox")
    mu = {k: Decimal(0) for k in zero}
    # O2 + 4 c2+ + 4 H+ -> 4 c3+ + 2 H2O: x0 = -4 mu(c2+)
    mu["cytc_red"] = -x0_C4 / 4
    # QH2 + 2 c3+ -> Q + 2 c2+ + 2 H+: x0 = 2 mu(c2+) - mu(QH2)
    x0_C3 = 1000 * _d(p["dG0_C3_pH7"]) / RT + 2 * ln1e7
    mu["QH2"] = 2 * mu["cytc_red"] - x0_C3
    # NADH + Q + H+ -> NAD + QH2: x0 = mu(QH2) - mu(NADH)
    x0_C1 = 1000 * _d(p["dG0_C1_pH7"]) / RT + (-1) * ln1e7
    mu["NADH"] = mu["QH2"] - x0_C1
    # ADP3- + HPO4 2- + H+ -> ATP4-: x0 = mu(ATP), with total Pi's term (section 2).
    mu["ATP"] = dG0_F / RT
    # S_red + NAD -> S_ox + NADH + H+: Delta G deg_S = 0 at pH 7, nu_H = +1.
    x0_S = Decimal(0) + 1 * ln1e7
    mu["S_red"] = mu["NADH"] - x0_S
    # 2 ADP3- -> ATP4- + AMP2-: x0 = -ln K_base.
    mu["AMP"] = -_ln(K_base) - mu["ATP"]
    # Forms: mu deg_f = mu deg_base + sum n mu deg_L + ln K_d.
    mu["MgATP"] = mu["ATP"] + mu["Mg"] + _ln(K_MgATP)
    mu["MgADP"] = mu["ADP"] + mu["Mg"] + _ln(K_MgADP)
    mu["H2PO4"] = mu["HPO4"] + mu["H"] + _ln(k_dH)
    entries = {  # sum nu mu deg/RT per law (section 9's free-energy entries, in RT)
        "C1": x0_C1,
        "C3": x0_C3,
        "C4": x0_C4,
        "QO": 2 * (x0_C3) + x0_C4,
        "F1": mu["ATP"],
        "Supply": x0_S,
        "AK": -_ln(K_base),
    }
    return {
        "T": T, "RT": RT, "f_mV": f_mV, "ln1e7": ln1e7,
        "m": m, "m_mM": m_mM, "prefactor": prefactor, "K_base": K_base,
        "dG0_F": dG0_F, "mu": mu, "entries": entries,
    }


# Section 10's band term: each row counted at each end, |nu| (|mu deg|/RT + ln 1000).
TURNOVER_ROWS = {
    "C1": {"NADH": -1, "Q": -1, "NAD": 1, "QH2": 1, "H_N": -5, "H_P": 4},
    "C3": {"QH2": -1, "Q": 1, "cytc_ox": -2, "cytc_red": 2, "H_N": -2, "H_P": 4},
    "C4": {"O2": -1, "cytc_red": -4, "cytc_ox": 4, "H_N": -8, "H_P": 4},
    "QO": {"QH2": -2, "Q": 2, "O2": -1, "H_N": -12, "H_P": 12},
    "F1": {"ADP": -1, "HPO4": -1, "ATP": 1, "H_N": 2, "H_P": -3},
    "ANT": {"ATP_N": -1, "ATP_P": 1, "ADP_P": -1, "ADP_N": 1},
    "PiHt": {"HPO4_P": -1, "HPO4_N": 1, "H_P": -2, "H_N": 2},
    "KH": {"K_P": -1, "K_N": 1, "H_N": -1, "H_P": 1},
    "Supply": {"S_red": -1, "NAD": -1, "S_ox": 1, "NADH": 1, "H_N": 1},
    "AK": {"ADP": -2, "ATP": 1, "AMP": 1},
}


def band_terms(d=None):
    d = d or derived()
    ln1000 = _ln(Decimal(1000))
    out = {}
    for name, rows in TURNOVER_ROWS.items():
        total = Decimal(0)
        for row, nu in rows.items():
            whole = ("cytc_ox", "cytc_red", "S_red", "S_ox")
            species = row if row in whole else row.split("_")[0]
            total += abs(nu) * (abs(d["mu"][species]) + ln1000)
        out[name] = total
    return out


def printed():
    """The appendix's printed values (sections 0, 7, 9 and 10), for ``check_printed``."""
    return {
        "RT": ("2478.9570", 5e-5),
        "f_mV": ("0.0389217", 5e-8),
        "RT_ln1e7_kJ": ("39.9561", 5e-5),
        "m_mM": ("3.808553529", 5e-10),
        "K_base": ("0.388964538", 5e-10),
        "prefactor": ("159.6897303699056", 5e-13),
        "dG0_F_kJ": ("-5.032", 5e-4),
        "mu": {
            "cytc_red": "40.914814298", "QH2": "62.715891459", "NADH": "106.817529855",
            "ATP": "-2.029938769", "S_red": "90.699434204", "AMP": "2.974205870",
            "MgATP": "-12.667395497", "MgADP": "-7.966185778", "H2PO4": "-15.542437799",
        },
        "entries_RT": {
            "C1": "-44.1016", "C3": "19.1137", "C4": "-163.6593", "QO": "-125.4318",
            "F1": "-2.0299", "Supply": "16.1181", "AK": "0.9443",
        },
        "bands": {
            "C1": "259.334", "C3": "227.439", "C4": "308.722", "QO": "325.757", "F1": "57.292",
            "ANT": "31.691", "PiHt": "41.447", "KH": "27.631", "Supply": "232.056", "AK": "32.635",
        },
    }


def check_printed(d=None):
    """Compare the 50-digit derivations with the appendix's printed values.

    Returns a list of (name, derived, printed, |difference|, allowed) for every failure; an
    empty list means every printed value is reproduced to its last printed digit.
    """
    d = d or derived()
    pr = printed()
    failures = []

    def compare(name, value, text, allowed=None):
        target = Decimal(text)
        if allowed is None:
            exponent = target.as_tuple().exponent
            allowed = Decimal(5) * Decimal(10) ** (exponent - 1)  # half a unit in the last digit
        diff = abs(Decimal(value) - target)
        if diff > Decimal(allowed):
            failures.append((name, str(value), text, str(diff), str(allowed)))

    compare("RT", d["RT"], pr["RT"][0], pr["RT"][1])
    compare("f_mV", d["f_mV"], pr["f_mV"][0], pr["f_mV"][1])
    compare("RT_ln1e7_kJ", d["RT"] * d["ln1e7"] / 1000, pr["RT_ln1e7_kJ"][0], pr["RT_ln1e7_kJ"][1])
    compare("m_mM", d["m_mM"], pr["m_mM"][0], pr["m_mM"][1])
    compare("K_base", d["K_base"], pr["K_base"][0], pr["K_base"][1])
    compare("prefactor", d["prefactor"], pr["prefactor"][0], pr["prefactor"][1])
    compare("dG0_F_kJ", d["dG0_F"] / 1000, pr["dG0_F_kJ"][0], pr["dG0_F_kJ"][1])
    for name, text in pr["mu"].items():
        compare("mu." + name, d["mu"][name], text)
    for name, text in pr["entries_RT"].items():
        compare("entry." + name, d["entries"][name], text)
    bands = band_terms(d)
    for name, text in pr["bands"].items():
        compare("band." + name, bands[name], text)
    return failures


def floats(declaration=None):
    """The derived constants as floats, rounded once from 50 digits."""
    d = derived(declaration)
    return {
        "RT": float(d["RT"]),
        "f_mV": float(d["f_mV"]),
        "ln1e7": float(d["ln1e7"]),
        "K_base": float(d["K_base"]),
        "m_match": float(d["m"]),
        "dG0_F_RT": float(d["dG0_F"] / d["RT"]),
        "mu": {k: float(v) for k, v in d["mu"].items()},
        "bands": {k: float(v) for k, v in band_terms(d).items()},
        "RT_exact_str": str(d["RT"]),
    }


if __name__ == "__main__":
    fails = check_printed()
    d = derived()
    print("K_base", d["K_base"])
    print("m_mM", d["m_mM"])
    print("prefactor", d["prefactor"])
    print("dG0_F kJ", d["dG0_F"] / 1000)
    for k, v in d["mu"].items():
        print("mu", k, round(v, 9))
    for k, v in band_terms(d).items():
        print("band", k, round(v, 3))
    print("failures:", fails)
    raise SystemExit(1 if fails else 0)
