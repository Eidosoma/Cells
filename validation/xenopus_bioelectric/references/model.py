"""The membrane physics of XC0's claims C0-C5 and C7's closed forms, from DESIGN.md and the inputs.

Conventions (declared_inputs conventions): V = phi_inside - phi_outside; currents are outward
positive; concentrations in mM (= mol/m3); areas m2; permeabilities m/s; F, R the declared doubles.
Constant-field (GHK) current of one ion through one patch:

    I = A P z F x (c_i - c_o e^-x) / (1 - e^-x),    x = z F V / (R T),    I(x=0) = A P z F (c_i - c_o)

Positive I is positive charge leaving the cell (an anion entering is a positive current).
Every function takes explicit parameters (a dict ``prm`` of Decimals) so that the plants can change
one thing at a time.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from .exact import dec, find_roots, logmean, rk4_richardson

HERE = Path(__file__).resolve().parent
INPUTS = json.loads((HERE / "reference_inputs.json").read_text())

ION_SETS = ("primary", "bracket_Cl_high", "bracket_second_hand_table")
EXTERIORS = ("bath", "local", "bath70_Na", "bath70_inert", "bath_Cl10", "bath_Cl11p1")
TEMPERATURES = ("291.15", "287.15")
P_GLYR_GRID = ("1e-9", "3e-9", "1e-8", "3e-8")
G_REF_GRID = ("0.1", "0.3", "1", "3")
AVAIL_LEVELS = ("0", "0.5", "1")
AVAIL_FULL = ("0", "0.25", "0.5", "0.75", "1")
IONS = ("Na", "K", "Cl")
Z = {"Na": 1, "K": 1, "Cl": -1}


def _cytosol(name):
    return {k: dec(float(v)) for k, v in INPUTS["ion_sets"][name]["cytosol_mM"].items()}


def exterior_mM(name):
    """Outside concentrations (mM) of Na, K, Cl for a named exterior."""
    bath = {k: dec(v / 1000.0) for k, v in INPUTS["nodes"]["bath"]["node"]["initial_amount_fmol"].items()}
    # fmol / pL = mM; the bath volume is 1000 pL
    loc = INPUTS["nodes"]["local"]["node"]
    loc_c = {k: dec(v) / dec(loc["volume_pL"]) for k, v in loc["initial_amount_fmol"].items()}
    b70 = INPUTS["nodes"]["bath_70Cl"]["node"]["initial_amount_fmol"]
    if name == "bath":
        return {k: bath[k] for k in IONS}
    if name == "local":
        return {k: loc_c[k] for k in IONS}
    if name == "bath70_Na":
        return {k: dec(b70[k]) / dec(1000) for k in IONS}
    if name == "bath70_inert":      # an inert cation carries the extra charge; Na stays at the 0.1x MMR value
        return {"Na": bath["Na"], "K": dec(b70["K"]) / 1000, "Cl": dec(b70["Cl"]) / 1000}
    if name == "bath_Cl10":
        return {"Na": bath["Na"], "K": bath["K"], "Cl": dec("10.0")}
    if name == "bath_Cl11p1":
        return {"Na": bath["Na"], "K": bath["K"], "Cl": dec("11.1")}
    raise KeyError(name)


def state_keys():
    return [f"{i}|{e}|T{t}" for i in ION_SETS for e in EXTERIORS for t in TEMPERATURES]


def build(ionset="primary", ext="bath", T="291.15", **over):
    """Parameters of one registered state; ``over`` replaces any entry (used by plants and sweeps)."""
    mem = {m["id"]: m for m in INPUTS["membranes"]}
    ci, co = _cytosol(ionset), exterior_mM(ext)
    prm = {
        "R": dec(INPUTS["conventions"]["R_J_per_mol_K"]), "F": dec(INPUTS["conventions"]["F_C_per_mol"]),
        "T": dec(T),
        "A_main": dec(mem["m_main"]["area_m2"]), "A_kleak": dec(mem["m_kleak"]["area_m2"]),
        "A_kir": dec(mem["m_kir"]["area_m2"]), "A_gly": dec(mem["m_glycine"]["area_m2"]),
        "C_main": dec(mem["m_main"]["capacitance_F"]), "C_kleak": dec(mem["m_kleak"]["capacitance_F"]),
        "C_kir": dec(mem["m_kir"]["capacitance_F"]), "C_gly": dec(mem["m_glycine"]["capacitance_F"]),
        "PNa": dec(mem["m_main"]["permeability_m_per_s"]["Na"]),
        "PCl": dec(mem["m_main"]["permeability_m_per_s"]["Cl"]),
        "PK": dec(mem["m_kleak"]["permeability_m_per_s"]["K"]),
        "P_gly": dec("1e-8"), "aG": dec(0), "aK": dec(0), "g_ref": dec(1),
        "k_ref": dec(INPUTS["kir_route"]["entry"]["k_ref_mM"]), "Vh": dec(INPUTS["kir_route"]["entry"]["v_half_V"]),
        "s": dec(INPUTS["kir_route"]["entry"]["slope_V"]),
        "cNa_i": ci["Na"], "cK_i": ci["K"], "cCl_i": ci["Cl"],
        "cNa_o": co["Na"], "cK_o": co["K"], "cCl_o": co["Cl"],
        "weights": "area",       # "area": permeabilities enter as A_patch * P; "unit": whole-membrane values (design-text reading)
    }
    for k, v in over.items():
        prm[k] = v if k == "weights" else dec(v)
    return prm


def C_total(p):
    return p["C_main"] + p["C_kleak"] + p["C_kir"] + p["C_gly"]


def f_of(p):
    return p["F"] / (p["R"] * p["T"])


def RT_over_F(p):
    return p["R"] * p["T"] / p["F"]


def nernst(z, c_out, c_in, p):
    """E = (RT / (z F)) ln(c_out / c_in); z is explicit (a sign-flip or a swapped valence is a plant)."""
    return RT_over_F(p) / dec(z) * (c_out / c_in).ln()


def E(ion, p):
    return nernst(Z[ion], p[f"c{ion}_o"], p[f"c{ion}_i"], p)


def ghk_I(A_P, z, V, c_i, c_o, p):
    """GHK current for the permeance-area product A_P (m3/s)."""
    x = dec(z) * f_of(p) * V
    if x == 0:
        return A_P * dec(z) * p["F"] * (c_i - c_o)
    e = (-x).exp()
    return A_P * dec(z) * p["F"] * x * (c_i - c_o * e) / (1 - e)


def ghk_g(A_P, z, V, c_i, c_o, p):
    """dI/dV of the GHK current (analytic)."""
    f = f_of(p)
    x = dec(z) * f * V
    if x == 0:
        # limit of phi'(x) at 0 is (c_i + c_o)/2 ... derived by series: phi = (c_i - c_o) + x (c_i + c_o)/2 + ...
        return A_P * dec(z) * p["F"] * dec(z) * f * (c_i + c_o) / 2
    e = (-x).exp()
    N, Dn = c_i - c_o * e, 1 - e
    phi_p = N / Dn + x * (c_o * e / Dn - N * e / Dn ** 2)
    return A_P * dec(z) * p["F"] * dec(z) * f * phi_p


def perm_products(p):
    """A*P (m3/s) per ion of the passive constant-field patches, the glycine patch's Cl included."""
    if p["weights"] == "unit":      # the design text's reading: whole-membrane values, no area weighting
        return {"Na": p["PNa"], "K": p["PK"], "Cl": p["PCl"] + p["aG"] * p["P_gly"]}
    return {"Na": p["A_main"] * p["PNa"], "K": p["A_kleak"] * p["PK"],
            "Cl": p["A_main"] * p["PCl"] + p["aG"] * p["A_gly"] * p["P_gly"]}


def q_kir(u, p):
    return 1 / (1 + ((u - p["Vh"]) / p["s"]).exp())


def kir_I(V, p):
    """The Kir route's outward current: a A g_ref sqrt(K_o / K_ref) q(u) u,  u = V - E_K."""
    u = V - E("K", p)
    return p["aK"] * p["A_kir"] * p["g_ref"] * (p["cK_o"] / p["k_ref"]).sqrt() * q_kir(u, p) * u


def kir_g(V, p):
    u = V - E("K", p)
    q = q_kir(u, p)
    return p["aK"] * p["A_kir"] * p["g_ref"] * (p["cK_o"] / p["k_ref"]).sqrt() * q * (1 - u * (1 - q) / p["s"])


def ion_I(ion, V, p):
    return ghk_I(perm_products(p)[ion], Z[ion], V, p[f"c{ion}_i"], p[f"c{ion}_o"], p)


def I_leak(V, p):
    return sum(ion_I(i, V, p) for i in IONS)


def I_total(V, p):
    return I_leak(V, p) + kir_I(V, p)


def g_total(V, p):
    ap = perm_products(p)
    return sum(ghk_g(ap[i], Z[i], V, p[f"c{i}_i"], p[f"c{i}_o"], p) for i in IONS) + kir_g(V, p)


def V_ghk(p):
    """The closed-form zero-current voltage of the passive patches (glycine included, Kir not)."""
    ap = perm_products(p)
    num = ap["K"] * p["cK_o"] + ap["Na"] * p["cNa_o"] + ap["Cl"] * p["cCl_i"]
    den = ap["K"] * p["cK_i"] + ap["Na"] * p["cNa_i"] + ap["Cl"] * p["cCl_o"]
    return RT_over_F(p) * (num / den).ln()


def V_zero(p):
    """Zero-current voltage of the full membrane (Kir included): a root finder, with the roots found."""
    if p["aK"] == 0:
        return [V_ghk(p)]
    roots = find_roots(lambda v: I_total(v, p), lambda v: g_total(v, p), dec("-0.35"), dec("0.35"), 70)
    return [r for r in roots if g_total(r, p) > 0]     # stable roots (dI/dV > 0)


def V_rest(p):
    r = V_zero(p)
    assert len(r) == 1, ("not a unique stable zero", r)
    return r[0]


def tau_lin(p, V):
    return C_total(p) / g_total(V, p)


def step_ode(p, V_start, V_inf, tau, with_amounts=False, steps_per_tau=20, tau_span=4, record_per_tau=4):
    """V(t) after a step, fixed amounts (or amounts evolving): RK4 with Richardson estimate.

    Returns [(t, V, err_V, extras)]; extras (amounts case) = (dn_Na, dn_K, dn_Cl) in fmol.
    The cell volume is 65.45 pL: 1 mM there is 65.45 fmol.
    """
    Ct = C_total(p)
    vol_pL = dec(INPUTS["geometry"]["volume_pL"])
    if not with_amounts:
        rhs = lambda t, y: [-I_total(y[0], p) / Ct]
        y0 = [V_start]
    else:
        def rhs(t, y):
            q = dict(p)
            for k, i in enumerate(IONS):
                q[f"c{i}_i"] = p[f"c{i}_i"] + y[1 + k] / vol_pL
            v = y[0]
            out = [-I_total(v, q) / Ct]
            for i in IONS:
                out.append(-ion_I(i, v, q) / (dec(Z[i]) * p["F"]) * dec("1e15"))   # fmol/s
            return out
        y0 = [V_start, dec(0), dec(0), dec(0)]
    steps = int(steps_per_tau * tau_span)
    pts, errs = rk4_richardson(rhs, y0, tau * tau_span, steps, steps_per_tau // record_per_tau)
    return pts, errs


def junction_g(p, c_mean):
    """Ohmic conductance of the constant-field junction between equal cytosols (declared P, A)."""
    jn = INPUTS["junction"]
    A = dec(jn["area_m2"])
    return sum(A * dec(jn["permeability_m_per_s"][i]) * dec(Z[i]) ** 2 * p["F"] ** 2 / (p["R"] * p["T"]) * c_mean[i]
               for i in IONS)
