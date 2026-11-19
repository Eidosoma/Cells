"""Plants: deliberately wrong inputs or bookings that the comparison must refuse.

Each plant recomputes the affected rows with one thing wrong. Its deviation is compared with the row's band:
margin = |plant - reference| / band (sign rows: |aux|/band when the sign is wrong; flag and exact-zero rows
cap at 1e9). A row with margin < 1 cannot see the plant (zero power); margin < 10 is weak. ``expect_zero`` says,
with a reason, which rows are zero power by construction; any other row below 10 is reported as weak.
"""

from __future__ import annotations

from decimal import Decimal

from . import claims_c5
from . import model as M
from . import symporter as S
from .exact import dec, sign

D = dec
CAP = 1e9


def _split(key):
    return key.split("|")


def s_from_key(key, **over):
    """Symporter state of a stall/offset/eq key."""
    parts = _split(key)
    kw = {}
    n = 2
    s = None
    for part in parts:
        if part.startswith("Nain"):
            kw["NaN"] = part[4:]
        elif part.startswith("Naout"):
            kw["NaP"] = part[5:]
        elif part.startswith("BP"):
            kw["BP"] = part[2:]
        elif part.startswith("rB"):
            kw["_rb"] = part[2:]
        elif part.startswith("T") and part[1:2].isdigit():
            kw["T"] = part[1:]
        elif part.startswith("Vrest_"):
            kw["V"] = M.V_ghk(M.build("primary", part[6:], "291.15"))
        elif part.startswith("V") and part[1:2] in "-0123456789":
            kw["V"] = part[1:]
        elif part.startswith("n") and part[1:].isdigit():
            n = int(part[1:])
    rb = kw.pop("_rb", None)
    if rb is not None:
        kw["BN"] = str(D(kw["BP"]) * D(rb))
    s = S.s_params(n=n, **kw)
    s.update(over)
    return s


class Plant:
    def __init__(self, name, description, size):
        self.name, self.description, self.size = name, description, size
        self.entries = []          # (family, key, wrong value, expected-zero-power reason or None)
        self.proportional = False  # the plant scales the reference: rows with a reference near 0 cannot show it

    def add(self, fam, key, wrong, zero_reason=None):
        self.entries.append((fam, key, wrong, zero_reason))


def margin(R, fam, key, wrong):
    kind = R.meta[fam]["kind"]
    ref = R.values[fam][key]
    band = R.band(fam, key)
    if kind == "flag":
        return CAP if ("true" if wrong else "false") != ref else 0.0
    if kind == "exact_zero":
        return CAP if wrong != 0 else 0.0
    if kind == "sign":
        aux = abs(Decimal(R.aux[fam][key]))
        if sign(wrong) == int(ref):
            return 0.0
        return float(min(aux / D(band), D(CAP))) if band > 0 else CAP
    dev = abs(Decimal(wrong) - Decimal(ref))
    if band == 0:
        return CAP if dev != 0 else 0.0
    return float(min(dev / D(band), D(CAP)))


def build_plants(R):
    P = []
    keys36 = M.state_keys()

    def sp(key):
        i, e, t = key.split("|")
        return i, e, t[1:]

    # 1 swapped valence of Cl
    p1 = Plant("valence_swap_Cl", "Cl- treated as a cation (z = +1) in the Nernst term and the GHK sum", "E_Cl sign flips: 2|E_Cl| (about 40-120 mV)")
    for key in keys36:
        i, e, t = sp(key)
        p = M.build(i, e, t)
        w = M.nernst(1, p["cCl_o"], p["cCl_i"], p)
        p1.add("C0.E_Cl", key, w)
        p1.add("C1.zero_Cl", key, w)
        ap = M.perm_products(p)
        num = ap["K"] * p["cK_o"] + ap["Na"] * p["cNa_o"] + ap["Cl"] * p["cCl_o"]
        den = ap["K"] * p["cK_i"] + ap["Na"] * p["cNa_i"] + ap["Cl"] * p["cCl_i"]
        p1.add("C2.V_ghk_area", key, M.RT_over_F(p) * (num / den).ln())
    P.append(p1)
    # 2 sign-flipped Nernst
    p2 = Plant("nernst_sign_flipped", "E = -(RT/zF) ln(c_out/c_in) for K, Na and Cl", "2|E| for each ion (22-306 mV)")
    for key in keys36:
        i, e, t = sp(key)
        p = M.build(i, e, t)
        for ion, fam in (("K", "C0.E_K"), ("Na", "C0.E_Na"), ("Cl", "C0.E_Cl")):
            p2.add(fam, key, -M.E(ion, p))
    P.append(p2)
    # 3 n = 3 in place of 2
    p3 = Plant("n3_for_n2", "n_Na = 3 where the declared value is 2 (stall, equilibrium ratio, J offsets)", "stall shifts by about -37 to -190 mV")
    for fam in ("C6.v1_V_stall", "C6.v1_eq_ratio", "C6.v1_J_offset", "C6.v1_x_offset", "C6.v1_ratio_Jm_Jp"):
        for key in R.values[fam]:
            if not key.startswith("n2|"):
                continue
            s = s_from_key(key)
            if fam == "C6.v1_V_stall":
                w = S.V_stall(dict(s, n=3))
            elif fam == "C6.v1_eq_ratio":
                w = S.ratio_eq(dict(s, n=3))
            else:
                base = s_from_key(key.rsplit("|off", 1)[0])
                so = dict(s, n=3, V=S.V_stall(base) + D(key.rsplit("|off", 1)[1]))
                w = {"C6.v1_J_offset": S.J_net, "C6.v1_x_offset": S.x_cyc,
                     "C6.v1_ratio_Jm_Jp": lambda q: S.J_minus(q) / S.J_plus(q)}[fam](so)
            p3.add(fam, key, w)
    P.append(p3)
    # 4 capacitance split
    for name, factor, desc, size in (("capacitance_main_patch_only", D(M.build()["C_main"] / M.C_total(M.build())), "tau from the main patch's 60 % of the capacitance only", "tau x 0.6 (-40 %)"),
                                    ("capacitance_full_on_each_patch", D(4), "every patch given the full capacitance (the split missing)", "tau x 4 (+300 %)")):
        pl = Plant(name, desc, size)
        pl.proportional = True
        for fam in ("C3.tau_lin", "C3.tau_fit", "C5.tau_common", "C5.tau_diff", "C5.tau_fit_common", "C5.tau_fit_diff"):
            for key in R.values[fam]:
                if fam.startswith("C5") and key.split("|")[-1].startswith("x") and key.split("|")[-1] != "x1":
                    continue
                pl.add(fam, key, Decimal(R.values[fam][key]) * factor)
        P.append(pl)
    # 5 Kir without sqrt(K_o/K_ref)
    p5 = Plant("kir_without_sqrt_Ko", "Kir current without the sqrt(K_o/K_ref) factor", "current x sqrt(K_ref/K_o): x5.0 (bath), x1.1 (local)")
    for u in ("-0.05", "-0.02", "0.02", "0.05", "0.1"):
        for key in keys36:
            i, e, t = sp(key)
            pk = M.build(i, e, t, aK=1, g_ref=1)
            w = M.kir_I(M.E("K", pk) + D(u), pk) / (pk["cK_o"] / pk["k_ref"]).sqrt()
            p5.add(f"C1.kir_I_u{u}", key, w, "K_o = K_ref has no effect: not in these states" if pk["cK_o"] == pk["k_ref"] else None)
    for key in R.values["C1.kir_sqrtKo_ratio"]:
        p5.add("C1.kir_sqrtKo_ratio", key, D(1))
    P.append(p5)
    # 6 rectification on the absolute voltage
    p6 = Plant("kir_rectifies_on_absolute_V", "u = V instead of V - E_K in the Kir law", "I(E_K) no longer zero")
    for key in keys36:
        i, e, t = sp(key)
        pk = M.build(i, e, t, aK=1, g_ref=1)
        EK = M.E("K", pk)
        p6.add("C1.kir_zero_at_EK", key, pk["A_kir"] * pk["g_ref"] * (pk["cK_o"] / pk["k_ref"]).sqrt() * M.q_kir(EK, pk) * EK)
        for u in ("-0.05", "-0.02", "0.02", "0.05", "0.1"):
            V = EK + D(u)
            p6.add(f"C1.kir_I_u{u}", key, pk["A_kir"] * pk["g_ref"] * (pk["cK_o"] / pk["k_ref"]).sqrt() * M.q_kir(V, pk) * V)
    P.append(p6)
    p7 = Plant("kir_current_sign_flipped", "Kir route current with the wrong sign (inward positive)", "I -> -I (2|I|)")
    for u in ("-0.05", "-0.02", "0.02", "0.05", "0.1"):
        for key in keys36:
            i, e, t = sp(key)
            pk = M.build(i, e, t, aK=1, g_ref=1)
            p7.add(f"C1.kir_I_u{u}", key, -M.kir_I(M.E("K", pk) + D(u), pk))
    P.append(p7)
    # 8 availability not applied
    p8 = Plant("availability_ignored", "the Cl- patch and Kir route at availability 1 whenever they exist (a = 0 and 0.5 not applied)", "a = 0 -> 1; a = 0.5 -> 1")
    for key in keys36:
        i, e, t = sp(key)
        for P_ in M.P_GLYR_GRID:
            p = M.build(i, e, t, aG=1, P_gly=P_)
            p8.add("C4.V_zero_glycine", f"{key}|P{P_}|a0.5", M.V_ghk(p))
        for V in ("-0.1", "-0.04", "0.02"):
            pz = M.build(i, e, t, aK=1, g_ref=3, aG=1, P_gly="3e-8")
            p8.add("C4.flux_at_a0", f"{key}|V{V}", M.kir_I(D(V), pz) + M.ghk_I(pz["A_gly"] * pz["P_gly"], -1, D(V), pz["cCl_i"], pz["cCl_o"], pz))
    P.append(p8)
    p8b = Plant("kir_route_inert", "the Kir route acts as if its availability were 0 (route off)", "shift of V_zero by the route (microvolts; the route is rectified shut at these states)")
    for key in keys36:
        i, e, t = sp(key)
        V0 = M.V_ghk(M.build(i, e, t))
        for g in M.G_REF_GRID:
            for a in ("0.25", "0.5", "1"):
                p8b.add("C4.V_zero_kir", f"{key}|g{g}|a{a}", V0, "the route shifts V_zero by less than the 1e-5 V band at these states")
        p8b.add("C4.V_zero_both", key, M.V_ghk(M.build(i, e, t, aG=1, P_gly="3e-8")), "the Cl- patch dominates; the route adds microvolts")
    P.append(p8b)
    # 9 local node replaced by the bath
    p9 = Plant("local_values_replaced_by_bath", "the local compartment's membranes silently take the bath's values", "E_K -78.1 -> -153.3 mV; V_GHK shifts by tens of mV")
    for key in keys36:
        i, e, t = sp(key)
        if e != "local":
            continue
        pb = M.build(i, "bath", t)
        p9.add("C0.E_K", key, M.E("K", pb))
        p9.add("C2.V_ghk_area", key, M.V_ghk(pb))
    for i in M.ION_SETS:
        for t in M.TEMPERATURES:
            p9.add("C8.a_dE_K", f"{i}|T{t}", D(0))
            p9.add("C8.a_dV_ghk_area", f"{i}|T{t}", D(0))
    P.append(p9)
    # 10 junction conductance
    for name, fac, desc in (("junction_conductance_x2", D(2), "g_J doubled (counted from both ends)"), ("junction_conductance_x0.5", D("0.5"), "g_J halved"), ("junction_absent", D(0), "no junction in the difference mode")):
        pl = Plant(name, desc, "tau_diff changes by a factor (g+2gJ)/(g+2 f gJ)")
        for scn in claims_c5.SCENARIOS:
            key = f"{scn}|x1"
            p1_, p2_ = claims_c5.cells_for(scn)
            c_mean = {i: p1_[f"c{i}_i"] for i in M.IONS}
            gJ = M.junction_g(p1_, c_mean)
            V1, V2 = claims_c5.steady(p1_, p2_, gJ)
            ga, gb = M.g_total(V1, p1_), M.g_total(V2, p2_)
            gJf = gJ * fac
            disc = ((ga - gb) ** 2 + 4 * gJf ** 2).sqrt()
            Ct = M.C_total(p1_)
            pl.add("C5.tau_diff", key, 2 * Ct / ((ga + gb + 2 * gJf) + disc))
        P.append(pl)
    # 11 symporter charge term
    p11 = Plant("symporter_charge_n_not_n_minus_1", "the electrical term n F V in dG_cyc where (n - 1) F V is declared", "stall x (n-1)/n = x 0.5 (n = 2)")
    for key in R.values["C6.v1_V_stall"]:
        if key.startswith("n2|"):
            s = s_from_key(key)
            p11.add("C6.v1_V_stall", key, -(2 * (s["NaN"] / s["NaP"]).ln() + (s["BN"] / s["BP"]).ln()) / (2 * S.f_(s)))
    for key in R.values["C6.v1_eq_ratio"]:
        if key.startswith("n2|"):
            s = s_from_key(key)
            p11.add("C6.v1_eq_ratio", key, (s["NaP"] / s["NaN"]) ** 2 * (-(2) * S.f_(s) * s["V"]).exp(), "V = 0: the electrical term vanishes" if s["V"] == 0 else None)
    P.append(p11)
    p12 = Plant("symporter_voltage_sign_flipped", "V -> -V in dG_cyc (the wrong inside/outside convention)", "stall -> -stall; equilibrium ratio exponent flips")
    for key in R.values["C6.v1_V_stall"]:
        p12.add("C6.v1_V_stall", key, -Decimal(R.values["C6.v1_V_stall"][key]), "stall = 0 for this key" if Decimal(R.values["C6.v1_V_stall"][key]) == 0 else None)
    for key in R.values["C6.v1_eq_ratio"]:
        s = s_from_key(key)
        p12.add("C6.v1_eq_ratio", key, (s["NaP"] / s["NaN"]) ** s["n"] * ((s["n"] - 1) * S.f_(s) * s["V"]).exp(), "V = 0 or n = 1: no electrical term" if (s["V"] == 0 or s["n"] == 1) else None)
    P.append(p12)
    # 13 temperature
    p13 = Plant("temperature_298", "T = 298.15 K in place of 291.15 K", "RT/F x 1.024")
    p13.proportional = True
    for key in keys36:
        i, e, t = sp(key)
        if t != "291.15":
            continue
        p = M.build(i, e, "298.15")
        for ion, fam in (("K", "C0.E_K"), ("Na", "C0.E_Na"), ("Cl", "C0.E_Cl")):
            p13.add(fam, key, M.E(ion, p))
        p13.add("C2.V_ghk_area", key, M.V_ghk(p))
    for key in R.values["C6.v1_V_stall"]:
        if key.endswith("T291.15"):
            s = s_from_key(key)
            p13.add("C6.v1_V_stall", key, S.V_stall(dict(s, T=D("298.15"))))
    P.append(p13)
    # 14 heat sign
    p14 = Plant("symporter_heat_sign", "heat booked as +dG_cyc per cycle (negative for a favourable cycle)", "sign of the heat reversed")
    for key in R.values["C7.sym_heat_per_cycle"]:
        p14.add("C7.sym_heat_per_cycle", key, -Decimal(R.values["C7.sym_heat_per_cycle"][key]), "heat = 0 at the stall" if "off" not in key else None)
        p14.add("C7.sym_heat_nonneg", key, False)
    P.append(p14)
    # 15 pump stoichiometry
    for name, w, desc in (("pump_2Na_3K", (-2, 3, 1), "pump moves 2 Na out and 3 K in"), ("pump_3Na_3K_neutral", (-3, 3, 0), "pump moves 3 Na out and 3 K in (electroneutral)")):
        pl = Plant(name, desc, "counts differ by 1")
        for k, v in zip(("dNa_cell", "dK_cell", "outward_charge"), w):
            pl.add("C7.pump_cycle_counts", k, D(v))
        pl.entries = [(f, k, v, ("this count is the same as the declared one" if (k == "dNa_cell" and w[0] == -3) or (k == "dK_cell" and w[1] == 2) or (k == "outward_charge" and w[2] == 1) else None)) for f, k, v, _ in pl.entries]
        pl.add("C7.pump_cell_charge_per_fmol", "cell", D(0) if w[2] == 0 else -D(M.INPUTS["conventions"]["CHARGE_PER_FMOL_C"]) * D(w[2]), "the same charge per cycle" if w[2] == 1 else None)
        P.append(pl)
    # 16 Vito-C factor on the forward rate only
    p16 = Plant("vito_c_factor_on_forward_rate_only", "capacity factor f multiplies J+ but not J-", "J(f)/J(1) = (f - e^x)/(1 - e^x) in place of f")
    for key, kw in (("a", dict(NaN="21", NaP="9.9", BN="1", BP="1", V="-0.06")), ("b", dict(NaN="21", NaP="19.9", BN="0.0001", BP="10", V="-0.0899"))):
        s1 = S.s_params(**kw)
        for fc in ("0.25", "0.5", "0.75"):
            w = (D(fc) - S.x_cyc(s1).exp()) / (1 - S.x_cyc(s1).exp())
            p16.add("C6.v1_capacity_ratio", f"{key}|f{fc}", w, "x << 0: J- is negligible against J+, so f on J+ only equals f on both" if key == "b" else None)
    P.append(p16)
    # 17/18 inconsistent diagram
    def v2_wrong(name, desc, size, edit, restore):
        pl = Plant(name, desc, size)
        saved = [dict(e) for e in S.EDGES]
        try:
            edit()
            for key in R.values["C6.v2_ratio_Jm_Jp"]:
                NaPk, BPk, BNk, Vk = key.split("|")
                s = S.s_params(NaP=NaPk[3:], BP=BPk[2:], BN=BNk[2:], NaN="21", V=Vk[1:])
                pl.add("C6.v2_ratio_Jm_Jp", key, S.v2_ratio(s), "V = 0: the charge-sum error multiplies exp(0 x psi)" if (name == "diagram_charge_sum_0p9" and s["V"] == 0) else None)
        finally:
            for i, e in enumerate(saved):
                S.EDGES[i].clear()
                S.EDGES[i].update(e)
        return pl

    def edit17():
        S.EDGES[0]["backward"] = dict(S.EDGES[0]["backward"], k0_per_s=S.EDGES[0]["backward"]["k0_per_s"] * D("1.1"))

    def edit18():
        S.EDGES[7]["q"] = D("-0.1")
    P.append(v2_wrong("diagram_detailed_balance_broken", "one backward constant (e1) 10 % too large: the loop product no longer balances", "J-/J+ x 1.1", edit17, None))
    P.append(v2_wrong("diagram_charge_sum_0p9", "electric distances summing to 0.9 (e8 q = -0.1) in place of 1.0", "J-/J+ x exp(-0.1 psi)", edit18, None))
    # 19 bath Cl
    p19 = Plant("bath_Cl_11p1_for_10p1", "bath Cl 11.1 mM in place of 10.1 mM (the 2016 table value)", "E_Cl shifts by -2.4 mV; V_GHK by about -0.3 mV")
    for key in keys36:
        i, e, t = sp(key)
        if e != "bath":
            continue
        p = M.build(i, e, t, cCl_o=D("11.1"))
        p19.add("C0.E_Cl", key, M.E("Cl", p))
        p19.add("C1.zero_Cl", key, M.E("Cl", p))
        p19.add("C2.V_ghk_area", key, M.V_ghk(p))
    P.append(p19)
    # 20 face geometry (time scales with L/A)
    for name, fac, desc, size in (("face_length_doubled", D(2), "face length 2e-4 m in place of 1e-4 m", "every t_1/e x 2"),
                                  ("face_area_10pct_large", 1 / D("1.1"), "face area 1.1e-10 m2 in place of 1e-10 m2", "every t_1/e x 0.909 (-9 %)")):
        pl = Plant(name, desc, size)
        for fam in ("C8.bc_t_e",):
            for key in R.values[fam]:
                pl.add(fam, key, Decimal(R.values[fam][key]) * fac)
        P.append(pl)
    # 22 charge booked on the main patch's capacitance only (the identity band is 1e-14 C, erratum item 3)
    p22 = Plant("charge_on_main_patch_capacitance_only", "Q = C_main V (60 % of the capacitance) in the charge identities", "Q - C_total V = -0.4 C_total V (1e-13 to 1e-12 C)")
    cm_frac = D(M.build()["C_main"] / M.C_total(M.build()))
    for key in R.values["C3.Q_over_CV_error"]:
        scn, dl, k = key.split("|")
        Vt = Decimal(R.values["C3.V_inf"][scn]) + Decimal(R.values["C3.ratio_t"][key]) * D(dl[1:])
        p22.add("C3.Q_over_CV_error", key, -(1 - cm_frac) * M.C_total(M.build()) * Vt)
    for key in R.values["C7.relax_dQ"]:
        scn = key.split("|")[0]
        Vt = Decimal(R.values["C3.V_inf"][scn]) + Decimal(R.values["C7.relax_ratio_t"][key]) * (D("-0.04") - Decimal(R.values["C3.V_inf"][scn]))
        wrong = cm_frac * M.C_total(M.build()) * (Vt - D("-0.04"))
        p22.add("C7.relax_dQ", key, wrong, "dQ tiny: the early observation changes by less than the band" if abs(wrong - Decimal(R.values["C7.relax_dQ"][key])) < 1e-14 else None)
    P.append(p22)
    p23 = Plant("pump_standard_state_mM", "the pump's ATP hydrolysis free energy with the log argument in mM (no 1 M factor)", "dG_ATP shifted by RT ln 1000 = 16.7 kJ/mol")
    for key in R.values["C7.pump_heat"]:
        p23.add("C7.pump_dG_atp", key, Decimal(R.values["C7.pump_dG_atp"][key]) + M.build()["R"] * M.build()["T"] * D(1000).ln())
        p23.add("C7.pump_heat", key, Decimal(R.values["C7.pump_heat"][key]) - M.build()["R"] * M.build()["T"] * D(1000).ln())
    P.append(p23)
    p21 = Plant("local_final_state_is_bath", "the node's end state taken as the bath (the trapped A ignored)", "Na 37.9 -> 9.9 mM and so on")
    for i, cb in M.exterior_mM("bath").items():
        p21.add("C8.b_final_c", i, cb)
    p21.add("C8.b_final_is_bath", "bath", True)
    P.append(p21)
    return P


def local_D(i):
    return M.INPUTS["face"]["diffusivity_m2_per_s"][i]


def run_plants(R):
    out, zero, summary = {}, [], {}
    for pl in build_plants(R):
        rows = {}
        for fam, key, wrong, reason in pl.entries:
            m = margin(R, fam, key, wrong)
            if pl.proportional and reason is None and m < 1:
                reason = "reference near zero: a proportional error stays inside the band"
            if m >= 1:
                reason = None              # the plant is seen here: a reason is attached only where it is not
            rows.setdefault(fam, {})[key] = (m, reason)
        n = sum(len(v) for v in rows.values())
        marg = [m for f in rows.values() for m, _ in f.values()]
        seen = [m for f in rows.values() for m, r in f.values() if r is None]
        zp = {f: sorted(k for k, (m, r) in v.items() if m < 1) for f, v in rows.items()}
        zp = {f: k for f, k in zp.items() if k}
        weak = {f: sorted(k for k, (m, r) in v.items() if 1 <= m < 10) for f, v in rows.items()}
        weak = {f: k for f, k in weak.items() if k}
        reasons = sorted({r for f in rows.values() for m, r in f.values() if r is not None and m < 1})
        undeclared = {f: sorted(k for k, (m, r) in v.items() if m < 1 and r is None) for f, v in rows.items()}
        undeclared = {f: k for f, k in undeclared.items() if k}
        out[pl.name] = {
            "description": pl.description, "size": pl.size, "rows": n,
            "rows_ge_10_bands": sum(1 for m in marg if m >= 10), "rows_between_1_and_10": sum(1 for m in marg if 1 <= m < 10),
            "rows_below_1_band": sum(1 for m in marg if m < 1),
            "smallest_margin_all_rows": min(marg), "smallest_margin_expected_visible_rows": min(seen) if seen else None,
            "families": sorted(rows), "weak_rows": weak, "zero_power_rows": zp,
            "zero_power_declared_reasons": reasons, "zero_power_undeclared_rows": undeclared,
        }
        for f, keys in zp.items():
            zero.append({"plant": pl.name, "family": f, "rows": len(keys), "reason": "; ".join(reasons) or "see zero_power_undeclared_rows"})
    summary["plants"] = len(out)
    summary["rows_total"] = sum(v["rows"] for v in out.values())
    summary["smallest_margin_expected_visible"] = min((v["smallest_margin_expected_visible_rows"] for v in out.values() if v["smallest_margin_expected_visible_rows"] is not None))
    return {"plants": out, "zero_power": zero, "summary": summary}
