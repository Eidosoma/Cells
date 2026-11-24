"""FR-51's laws (references/spec/LAWS.md) as closed forms in 60-digit decimal arithmetic, written by
the builder from the spec alone. They read cases.json and never a reference result.

This is an independent reference solution for the tests' host rows and the development checks. It
is not the code-blind references, which the judge reads after its tag.

case_values(case_id, voltages) gives, at each voltage (decimal strings or Decimals) as floats:
- I_free and I_blocked (A), u, and slope_part [mode, voltage];
- dI_blocked/dV (S);
- dJ_blocked/dc_o and dJ_blocked/dc_i (fmol/s per mM);
- and the case's E_ion (V).
"""

import json
from decimal import Decimal as D
from decimal import localcontext

import numpy as np

from validation.fr51 import judge

F = D("6.02214076e23") * D("1.602176634e-19")
R = D("6.02214076e23") * D("1.380649e-23")


def _b(x):
    return 1 - x / 2 + x * x / 12 if abs(x) < D("1e-15") else x / (x.exp() - 1)


def _db(x):
    if abs(x) < D("1e-15"):
        return D(-1) / 2 + x / 6
    e = x.exp()
    return (e - 1 - x * e) / (e - 1) ** 2


def spec():
    return json.loads(judge.SPEC.read_text())


def reversal(case_id):
    """The case's E_ion (V), as a Decimal."""
    s = spec()
    case = next(c for c in s["cases"] if c["id"] == case_id)
    pop = s["populations"][case["population"]]
    with localcontext() as context:
        context.prec = 60
        z, t = D(pop["valence"]), D(s["constants"]["T_K"])
        return R * t / (z * F) * (D(case["c_o_mM"]) / D(case["c_i_mM"])).ln()


def case_values(case_id, voltages):
    s = spec()
    case = next(c for c in s["cases"] if c["id"] == case_id)
    pop = s["populations"][case["population"]]
    out = {k: [] for k in ("I_free", "I_blocked", "u", "dI", "dco", "dci", "slope_part")}
    with localcontext() as context:
        context.prec = 60
        t, z = D(s["constants"]["T_K"]), D(pop["valence"])
        area, perm = D(pop["area_m2"]), D(pop["permeability_m_per_s"])
        a = D(case.get("abundance", pop["abundance"]))
        if "units" in case:
            a = D(case["units"]["count"]) / (area * D(case["units"]["reference_density_per_m2"]))
        ci, co = D(case["c_i_mM"]), D(case["c_o_mM"])
        g = D("1e15") * area * perm * a
        e_ion = R * t / (z * F) * (co / ci).ln()
        block = s["blocks"][case["block"]] if case["block"] else None
        for value in voltages:
            v = D(str(value)) if not isinstance(value, D) else value
            x = z * F * v / (R * t)
            j = g * (ci * _b(-x) - co * _b(x))
            dj = g * (z * F / (R * t)) * (-ci * _db(-x) - co * _db(x))
            u, du, parts, rev = D(1), D(0), [], False
            if block:
                zb = int(block["blocker"]["valence"])
                side = 1 if block["blocker"]["side"] == "outside" else -1
                cb = D(block["blocker"]["concentration_mM"])
                rev = block["reference"] != "membrane_voltage"
                vref = v - e_ion if rev else v
                num = den = dnum = D(0)
                for mode in block["modes"]:
                    if "electrical_distance" in mode:
                        m = abs(zb) * D(mode["electrical_distance"])
                    else:
                        m = D(mode["effective_valence"])
                    ak = side * (1 if zb > 0 else -1) * m * F / (R * t)
                    k = D(mode["k0_mM"]) * (ak * vref).exp()
                    theta, free, w = cb / (cb + k), k / (cb + k), D(mode["weight"])
                    num, den, dnum = num + w * free, den + w, dnum + w * ak * theta * free
                    parts.append(theta * free)
                u, du = num / den, dnum / den
            i_free = D("1e-15") * F * z * j
            out["I_free"].append(i_free)
            out["I_blocked"].append(u * i_free)
            out["u"].append(u)
            out["dI"].append(D("1e-15") * F * z * (u * dj + j * du))
            dvo = -R * t / (z * F * co) if rev else D(0)
            dvi = R * t / (z * F * ci) if rev else D(0)
            out["dco"].append(u * (-g * _b(x)) + j * du * dvo)
            out["dci"].append(u * (g * _b(-x)) + j * du * dvi)
            out["slope_part"].append(parts)
    values = {k: np.array([float(q) for q in vals]) for k, vals in out.items() if k != "slope_part"}
    values["slope_part"] = np.array([[float(q) for q in row] for row in out["slope_part"]]).T
    values["E_ion"] = float(e_ion)
    return values
