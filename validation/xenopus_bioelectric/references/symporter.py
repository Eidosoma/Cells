"""Rows for C6 (the Na+-coupled monocarboxylate symporter, versions 1 and 2) and C7's symporter and pump parts.

The only constraint used on the net rate is J-/J+ = exp(dG_cyc/RT) with

    dG_cyc = n RT ln(a_Na,N/a_Na,P) + RT ln(a_B,N/a_B,P) + (n - 1) F V,    V = phi_N - phi_P (inside - outside).

A forward cycle imports n Na+ and one B- and is favourable when dG_cyc < 0. Version 1 has J+ = k S and
J- = k S exp(x), x = dG_cyc/RT. Version 2 is the eight-state diagram of DESIGN.md 3.4 solved by King-Altman.
No sign convention of the engine's affinity is assumed.
"""

from __future__ import annotations

from decimal import Decimal

from . import model as M
from .exact import U64, dec, fmt, sign
from .rows import G_OPS, floor_closed

D = dec
import json

IN = M.INPUTS
V1 = IN["symporter_v1"]
# the diagram's constants are read as decimal values (0.2, not the double nearest 0.2), so that the
# declared charge and detailed-balance sums are exact: 0.2+0.2-0.1+0.4-0.5+0.4+0.4+0 = 1 and 2.16e25 = 2.16e25
IN_DEC = json.loads((M.HERE / "reference_inputs.json").read_text(), parse_float=Decimal)
V2 = IN_DEC["symporter_v2"]
K_NA, K_B = D(V1["parameters"]["K_Na_mM"]), D(V1["parameters"]["K_B_mM"])
HILL_NA, HILL_B = int(V1["parameters"]["hill_Na"]), int(V1["parameters"]["hill_B"])
K0 = D(V1["capacity_fmol_per_s"]["base"])
N_NA = int(V1["parameters"]["n_Na"])


def s_params(n=N_NA, NaN="21", NaP="9.9", BN="1", BP="1", T="291.15", V="-0.07", k=K0):
    return {"R": D(IN["conventions"]["R_J_per_mol_K"]), "F": D(IN["conventions"]["F_C_per_mol"]), "T": D(T),
            "NaN": D(NaN), "NaP": D(NaP), "BN": D(BN), "BP": D(BP), "V": D(V), "k": D(k),
            "K_Na": K_NA, "K_B": K_B, "n": n, "hill_Na": HILL_NA, "hill_B": HILL_B}


def f_(s):
    return s["F"] / (s["R"] * s["T"])


def sat(s):
    return 1 / ((1 + (s["K_Na"] / s["NaP"]) ** s["hill_Na"]) * (1 + (s["K_B"] / s["BP"]) ** s["hill_B"]))


def x_cyc(s):
    """dG_cyc / RT."""
    n = s["n"]
    return n * (s["NaN"] / s["NaP"]).ln() + (s["BN"] / s["BP"]).ln() + (n - 1) * f_(s) * s["V"]


def J_net(s):
    return s["k"] * sat(s) * (1 - x_cyc(s).exp())


def J_plus(s):
    return s["k"] * sat(s)


def J_minus(s):
    return s["k"] * sat(s) * x_cyc(s).exp()


def V_stall(s):
    n = s["n"]
    return -((n * (s["NaN"] / s["NaP"]).ln() + (s["BN"] / s["BP"]).ln()) / ((n - 1) * f_(s)))


def ratio_eq(s):
    """(B_in/B_out) at dG_cyc = 0."""
    n = s["n"]
    return (s["NaP"] / s["NaN"]) ** n * (-(n - 1) * f_(s) * s["V"]).exp()


def x_floor_at_zero(s):
    """float64 floor of x when its terms cancel to 0: G u sum |terms| (the engine is given V as a double)."""
    n = s["n"]
    terms = n * abs((s["NaN"] / s["NaP"]).ln()) + abs((s["BN"] / s["BP"]).ln()) + (n - 1) * abs(f_(s) * s["V"])
    return G_OPS * U64 * terms


# ---------------------------------------------------------------- version 2: King-Altman on the 8-state ring
EDGES = V2["edges"]
NE = 8


def v2_rates(s):
    """Forward (i -> i+1) and backward (i+1 -> i) rate of each edge at the state s (units 1/s; omega = 1)."""
    psi = f_(s) * s["V"]
    a = {("Na", "P"): s["NaP"] / D(V2["standard_state_mM"]), ("Na", "N"): s["NaN"] / D(V2["standard_state_mM"]),
         ("B", "P"): s["BP"] / D(V2["standard_state_mM"]), ("B", "N"): s["BN"] / D(V2["standard_state_mM"])}
    fw, bw = [], []
    for e in EDGES:
        q = e["q"]
        rf, rb = e["forward"]["k0_per_s"], e["backward"]["k0_per_s"]
        for sp, side, order in e["forward"]["orders"]:
            rf *= a[(sp, side)] ** order
        for sp, side, order in e["backward"]["orders"]:
            rb *= a[(sp, side)] ** order
        fw.append(rf * (-q / 2 * psi).exp())      # zeta_forward = -0.5 q
        bw.append(rb * (q / 2 * psi).exp())       # zeta_backward = +0.5 q
    return fw, bw


def _prod(xs):
    r = D(1)
    for x in xs:
        r *= x
    return r


def v2_ka(s):
    """King-Altman: (J+, J-, J_net) per carrier per omega, plus the state occupancies."""
    fw, bw = v2_rates(s)
    Dst = []
    for st in range(NE):
        tot = D(0)
        for k in range(NE):                     # the removed edge
            term = D(1)
            j = (k + 1) % NE
            while j != st:                      # edges k+1 .. st-1, oriented forward (toward st)
                term *= fw[j]
                j = (j + 1) % NE
            j = st
            while j != k:                       # edges st .. k-1, oriented backward (toward st)
                term *= bw[j]
                j = (j + 1) % NE
            tot += term
        Dst.append(tot)
    sumD = sum(Dst)
    Pf, Pb = _prod(fw), _prod(bw)
    return Pf / sumD, Pb / sumD, (Pf - Pb) / sumD, [d / sumD for d in Dst]


def v2_master(s):
    """Independent check: the net flux across edge 0 from a Gaussian solve of the master equation."""
    fw, bw = v2_rates(s)
    n = NE
    A = [[D(0)] * n for _ in range(n)]
    for i in range(n):
        j = (i + 1) % n
        A[i][i] -= fw[i]
        A[j][i] += fw[i]
        A[j][j] -= bw[i]
        A[i][j] += bw[i]
    A[-1] = [D(1)] * n
    b = [D(0)] * (n - 1) + [D(1)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(A[r][c]))
        A[c], A[piv] = A[piv], A[c]
        b[c], b[piv] = b[piv], b[c]
        for r in range(c + 1, n):
            m = A[r][c] / A[c][c]
            for cc in range(c, n):
                A[r][cc] -= m * A[c][cc]
            b[r] -= m * b[c]
    p = [D(0)] * n
    for r in range(n - 1, -1, -1):
        p[r] = (b[r] - sum(A[r][c] * p[c] for c in range(r + 1, n))) / A[r][r]
    return p[0] * fw[0] - p[1] * bw[0]


def v2_ratio(s):
    Jp, Jm, J, _ = v2_ka(s)
    return Jm / Jp


def v2_floor(fn, s, keys=("R", "F", "T", "NaN", "NaP", "BN", "BP", "V")):
    return floor_closed(fn, s, keys)


def v2_stall_root(s):
    """Root of the King-Altman net flux in V (bisection to 1e-40 then secant); J is monotone in V (n = 2)."""
    lo, hi = D("-0.5"), D("0.5")
    s = dict(s)
    s["V"] = lo
    flo = v2_ka(s)[2]
    s["V"] = hi
    assert flo * v2_ka(s)[2] < 0
    for _ in range(140):
        m = (lo + hi) / 2
        s["V"] = m
        fm = v2_ka(s)[2]
        if flo * fm <= 0:
            hi = m
        else:
            lo, flo = m, fm
    return (lo + hi) / 2


# ------------------------------------------------------------------------------------------- the rows
CYTOSOL_NA = ("21", "38")
NA_OUT = ("9.9", "19.9", "69.8", "91")
B_P_SET = ("0.1", "10")
R_B = ("0.01", "0.1", "1", "10", "100")
V_OFFSETS = ("-0.04", "-0.01", "-0.001", "0.001", "0.01", "0.04")
V_EQ = ("-0.09", "-0.0705", "-0.04", "0", "0.02")


def c6_c7(R, report):
    TOLV = 1e-5        # DESIGN C6: stall within 0.01 mV
    REL = 1e-6         # DESIGN C6: ratios within 1e-6 relative
    R.family("C6.S_hill", "C6", "saturation S = [1+(K_Na/c_Na,P)^2]^-1 [1+K_B/c_B,P]^-1 on the grid", "1", "abs", 0, REL, "DESIGN C6: 1e-6 relative")
    R.family("C6.J_over_k_grid", "C6", "J/k at V = -0.1 V, Na_in 21, B_in 1e-4 mM, T 291.15 K (aux x = dG/RT; equals S when x << 0)", "1", "abs", 0, REL, "DESIGN C6: 1e-6 relative")
    R.family("C6.S_half", "C6", "S at c_Na = K_Na with c_B = 1e12 mM, and at c_B = K_B with c_Na = 1e12 mM (half saturation)", "1", "abs", 0, REL, "DESIGN C6: 1e-6 relative")
    R.family("C6.v1_V_stall", "C6", "stall voltage V_stall = -(RT/((n-1)F)) [n ln(Na_in/Na_out) + ln(B_in/B_out)]", "V", "abs", TOLV, 0, "DESIGN C6: stall within 0.01 mV")
    R.family("C6.v1_J_at_stall", "C6", "J at V_stall (zero)", "fmol/s", "abs", 0, 0, "DESIGN C6: J = 0 exactly; band = float64 floor of x", note="reference 0")
    R.family("C6.v1_dJdV_at_stall", "C6", "dJ/dV at the stall = -k S (n-1) F/(RT) (negative: J is monotone through the stall)", "fmol/s/V", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C6.v1_x_offset", "C6", "x = dG_cyc/RT at V_stall + offset", "1", "abs", REL, 0, "DESIGN C6: ratios within 1e-6 (relative on J-/J+; x absolute 1e-6)")
    R.family("C6.v1_J_offset", "C6", "J (fmol/s, k = 0.01) at V_stall + offset", "fmol/s", "abs", 0, REL, "DESIGN C6: 1e-6 relative")
    R.family("C6.v1_sign_J_offset", "C6", "sign of J at V_stall + offset (+1 import, i.e. hyperpolarised of the stall)", "1", "sign", 0, 0, "DESIGN C6: sign change at the stall", note="aux = J (fmol/s)")
    R.family("C6.v1_ratio_Jm_Jp", "C6", "J-/J+ at V_stall + offset = exp(dG_cyc/RT)", "1", "abs", 0, REL, "DESIGN C6: 1e-6 relative")
    R.family("C6.v1_eq_ratio", "C6", "(B_in/B_out)_eq = (Na_out/Na_in)^n exp(-(n-1) F V/RT)", "1", "abs", 0, REL, "DESIGN C6: ratios within 1e-6 relative")
    R.family("C6.v1_eq_x", "C6", "x at the equilibrium ratio (zero)", "1", "abs", REL, 0, "DESIGN C6: 1e-6 on the ratio is 1e-6 on x", note="reference 0")
    R.family("C6.v1_n1_J", "C6", "n = 1: J (fmol/s) at V in {-0.12,-0.07,0,0.05} V; identical at all V", "fmol/s", "abs", 0, REL, "DESIGN C6: voltage-independent; 1e-6 relative")
    R.family("C6.v1_n1_dJ_over_V", "C6", "n = 1: J(V) - J(V = -0.07) (zero)", "fmol/s", "abs", 0, 0, "DESIGN C6: rate voltage independent; band = floor", note="reference 0")
    R.family("C6.v1_capacity_ratio", "C6", "J(capacity f k0)/J(k0) at a state, f = 0, .25, .5, .75, 1 (equals f; V_stall and the equilibrium ratio do not move)", "1", "abs", 0, REL, "DESIGN C6: scales at every state")
    R.family("C6.v2_ratio_Jm_Jp", "C6", "version 2: J-/J+ (King-Altman) = exp(dG_cyc/RT)", "1", "abs", 0, REL, "DESIGN C6: 1e-6 relative")
    R.family("C6.v2_J_over_k", "C6", "version 2: King-Altman net cycle rate per carrier per omega (J/k)", "1", "abs", 0, REL, "DESIGN C6: 1e-6 relative")
    R.family("C6.v2_V_stall", "C6", "version 2: the zero of the King-Altman net rate in V (equals version 1's V_stall)", "V", "abs", TOLV, 0, "DESIGN C6: stall within 0.01 mV")
    R.family("C6.v2_early_ratio", "C6", "version 2 early uptake (B_in = 0): J(V = -0.0899)/J(V = -0.0705); version 1 has exactly 1", "1", "abs", 0, REL, "DESIGN 3.4/C6: King-Altman value, 1e-6 relative")
    R.family("C6.v2_early_ratio_rest", "C6", "version 2 early uptake (B_in = 0) at the corrected rest voltage: J(V_rest - 0.0194 V)/J(V_rest), V_rest the area-weighted 0.1x MMR zero-current voltage", "1", "abs", 0, REL, "DESIGN 3.4/C6 with the erratum's rest voltage: King-Altman, 1e-6 relative")
    R.family("C6.v2_alt_set_ratio", "C6", "a second consistent constant set (e1 rates x3, e4 rates x0.5, q = 0.1,.3,-.2,.5,-.4,.4,.3,0): J-/J+ = exp(dG_cyc/RT) still", "1", "abs", 0, REL, "DESIGN C6.7: every consistent set")
    R.family("C6.T3_inverse", "C6", "T3's inverse check at quasi-equilibrium, n = 2: voltage difference RT/F ln(ratio) for a B ratio, and the ratio for 19.4 mV (information)", "V or 1", "info", note="the 1.45 is DESIGN's rounding of 253/175; no pass or fail in XC0")
    R.family("C7.sym_dG_chem", "C7", "symporter, per mole of cycles: chemical part n RT ln(Na_N/Na_P) + RT ln(B_N/B_P)", "J/mol", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C7.sym_dU_cap", "C7", "symporter, per mole of cycles: capacitor energy V (n-1) F (charge moved inward per cycle (n-1) e)", "J/mol", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C7.sym_heat_per_cycle", "C7", "heat per mole of cycles = -dG_cyc = -(dG_chem + dU_cap)", "J/mol", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C7.sym_heat_power", "C7", "heat power J (-dG_cyc) (fmol/s x J/mol = fW), k = 0.01 fmol/s", "fW", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C7.sym_heat_nonneg", "C7", "heat never negative (J and -dG_cyc share a sign)", "bool", "flag")
    R.family("C7.sym_cycle_counts", "C7", "per cycle: dNa_in, dB_in, dNa_out, dB_out, charge inward (e), in that order, as n, 1, -n, -1, n-1", "1", "abs", 1e-9, 0, "DESIGN C7: material 1e-9 (borrowed absolute)")
    R.family("C7.pump_cycle_counts", "C7", "pump, per cycle: dNa_cell, dK_cell, outward charge, as -3, +2, +1", "1", "abs", 1e-9, 0, "DESIGN C7: pump moves 3 Na out, 2 K in, net outward charge one")
    R.family("C7.pump_cell_charge_per_fmol", "C7", "pump: ionic charge change of the cell per fmol of cycles = -CHARGE_PER_FMOL", "C/fmol", "abs", 0, 1e-12, "DESIGN C7: charge 1e-9 C; relative 1e-12 proposed")
    R.family("C7.pump_dG_atp", "C7", "pump, J per mole of cycles: dG_ATP = delta_g0 + RT [ln c_ADP + ln c_Pi - ln c_ATP - ln 1000 mM] (1 M standard state, DESIGN erratum item 4)", "J/mol", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C7.pump_heat", "C7", "pump, J per mole of cycles, heat = -dG_ATP - dG_chem - dU_cap (1 M standard state)", "J/mol", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C7.pump_heat_nonneg", "C7", "pump heat nonnegative", "bool", "flag")
    R.family("C7.pump_dG_chem", "C7", "pump, per mole of cycles: 3 RT ln(Na_o/Na_i) + 2 RT ln(K_i/K_o)", "J/mol", "abs", 0, REL, "proposed: relative 1e-6")
    R.family("C7.pump_dU_cap", "C7", "pump, per mole of cycles: -F V (the cell loses one positive charge per cycle)", "J/mol", "abs", 0, REL, "proposed: relative 1e-6")

    pT = M.build()
    kT = RT_F = pT["R"] * pT["T"] / pT["F"]
    R.add("C6.T3_inverse", "dV_for_ratio_1.45", RT_F * D("1.45").ln())
    R.add("C6.T3_inverse", "dV_for_ratio_253_over_175", RT_F * (D(253) / D(175)).ln())
    R.add("C6.T3_inverse", "ratio_for_dV_0.0194", (D("0.0194") / RT_F).exp())
    # saturation grid
    for NaP in ("1", "3", "10", "30", "100", "300"):
        for BP in ("0.01", "0.03", "0.1", "0.3", "1", "10"):
            s = s_params(NaP=NaP, BP=BP, NaN="21", BN="0.0001", V="-0.1")
            key = f"NaP{NaP}|BP{BP}"
            R.add("C6.S_hill", key, sat(s), floor_closed(sat, s))
            R.add("C6.J_over_k_grid", key, J_net(s) / s["k"], floor_closed(lambda q: J_net(q) / q["k"], s), aux=x_cyc(s))
    for key, kw in (("NaP=K_Na,BP=1e12", dict(NaP="30", BP="1e12")), ("NaP=1e12,BP=K_B", dict(NaP="1e12", BP="0.1"))):
        s = s_params(**kw)
        R.add("C6.S_half", key, sat(s), floor_closed(sat, s))

    # stall states
    for n in (2, 3, 4):
        for Tt in ("291.15", "287.15"):
            if n != 2 and Tt != "291.15":
                continue
            for Nai in CYTOSOL_NA:
                for Nao in NA_OUT:
                    for BP in B_P_SET:
                        for rb in R_B:
                            key = f"n{n}|Nain{Nai}|Naout{Nao}|BP{BP}|rB{rb}|T{Tt}"
                            BN = D(BP) * D(rb)
                            s = s_params(n=n, NaN=Nai, NaP=Nao, BN=str(BN), BP=BP, T=Tt)
                            Vs = V_stall(s)
                            R.add("C6.v1_V_stall", key, Vs, floor_closed(V_stall, s))
                            s["V"] = Vs
                            R.add("C6.v1_J_at_stall", key, D(0), s["k"] * sat(s) * x_floor_at_zero(s))
                            R.add("C6.v1_dJdV_at_stall", key, -s["k"] * sat(s) * (n - 1) * f_(s),
                                  floor_closed(lambda q: -q["k"] * sat(q) * (q["n"] - 1) * f_(q), s))
                            assert abs(x_cyc(s)) < D("1e-45")
                            if n == 2 and Nai == "21" and Tt == "291.15":
                                for off in V_OFFSETS:
                                    so = dict(s)
                                    so["V"] = Vs + D(off)
                                    ko = f"{key}|off{off}"
                                    xo, Jo = x_cyc(so), J_net(so)
                                    R.add("C6.v1_x_offset", ko, xo, floor_closed(x_cyc, so))
                                    R.add("C6.v1_J_offset", ko, Jo, floor_closed(J_net, so))
                                    R.add("C6.v1_sign_J_offset", ko, sign(Jo), aux=Jo)
                                    R.floors["C6.v1_sign_J_offset"][ko] = float(floor_closed(J_net, so))
                                    R.add("C6.v1_ratio_Jm_Jp", ko, J_minus(so) / J_plus(so), floor_closed(lambda q: J_minus(q) / J_plus(q), so))
                                    Jp = J_plus(so)
                                    assert abs(J_net(so) - (Jp - J_minus(so))) < abs(Jp) * D("1e-50")
                                    # C7 energy
                                    RTv = so["R"] * so["T"]
                                    dGc = so["n"] * RTv * (so["NaN"] / so["NaP"]).ln() + RTv * (so["BN"] / so["BP"]).ln()
                                    dUc = so["V"] * (so["n"] - 1) * so["F"]
                                    R.add("C7.sym_dG_chem", ko, dGc, floor_closed(lambda q: q["n"] * q["R"] * q["T"] * (q["NaN"] / q["NaP"]).ln() + q["R"] * q["T"] * (q["BN"] / q["BP"]).ln(), so))
                                    R.add("C7.sym_dU_cap", ko, dUc, floor_closed(lambda q: q["V"] * (q["n"] - 1) * q["F"], so))
                                    R.add("C7.sym_heat_per_cycle", ko, -(dGc + dUc), floor_closed(lambda q: -(q["n"] * q["R"] * q["T"] * (q["NaN"] / q["NaP"]).ln() + q["R"] * q["T"] * (q["BN"] / q["BP"]).ln() + q["V"] * (q["n"] - 1) * q["F"]), so))
                                    hp = lambda q: J_net(q) * (-(q["n"] * q["R"] * q["T"] * (q["NaN"] / q["NaP"]).ln() + q["R"] * q["T"] * (q["BN"] / q["BP"]).ln() + q["V"] * (q["n"] - 1) * q["F"]))
                                    R.add("C7.sym_heat_power", ko, hp(so), floor_closed(hp, so))
                                    R.add("C7.sym_heat_nonneg", ko, hp(so) >= 0)
    # equilibrium accumulation
    for n in (1, 2, 3, 4):
        for Nai in CYTOSOL_NA:
            for Nao in NA_OUT:
                for V in V_EQ:
                    s = s_params(n=n, NaN=Nai, NaP=Nao, V=V, BP="1")
                    rq = ratio_eq(s)
                    key = f"n{n}|Nain{Nai}|Naout{Nao}|V{V}"
                    R.add("C6.v1_eq_ratio", key, rq, floor_closed(ratio_eq, s))
                    s["BN"] = rq * s["BP"]
                    R.add("C6.v1_eq_x", key, D(0), x_floor_at_zero(s))
                    assert abs(x_cyc(s)) < D("1e-45")
    # the C6 illustrations at the corrected (area-weighted) rest voltage (DESIGN erratum item 1)
    for n in (1, 2, 3, 4):
        for ext, Nao in (("bath", "9.9"), ("local", "91"), ("bath70_Na", "69.8")):
            Vr = M.V_ghk(M.build("primary", ext, "291.15"))
            s = s_params(n=n, NaN="21", NaP=Nao, V=Vr, BP="1")
            key = f"n{n}|Nain21|Naout{Nao}|Vrest_{ext}"
            rq = ratio_eq(s)
            R.add("C6.v1_eq_ratio", key, rq, floor_closed(ratio_eq, s))
            s["BN"] = rq * s["BP"]
            R.add("C6.v1_eq_x", key, D(0), x_floor_at_zero(s))
    # n = 1: no voltage dependence
    for Nao in NA_OUT:
        for bn in ("0.0001", "1", "30"):
            sref = s_params(n=1, NaN="21", NaP=Nao, BN=bn, BP="1", V="-0.07")
            for V in ("-0.12", "-0.07", "0", "0.05"):
                s = dict(sref)
                s["V"] = D(V)
                key = f"Naout{Nao}|BN{bn}|V{V}"
                R.add("C6.v1_n1_J", key, J_net(s), floor_closed(J_net, s))
                R.add("C6.v1_n1_dJ_over_V", key, J_net(s) - J_net(sref), s["k"] * sat(s) * D(2) * G_OPS * U64 * (abs(x_cyc(s)) + 1))
                assert J_net(s) == J_net(sref)
    # capacity factor
    for key, kw in (("a", dict(NaN="21", NaP="9.9", BN="1", BP="1", V="-0.06")), ("b", dict(NaN="21", NaP="19.9", BN="0.0001", BP="10", V="-0.0899"))):
        base = J_net(s_params(**kw))
        for fcap in ("0", "0.25", "0.5", "0.75", "1"):
            s = s_params(**kw, k=K0 * D(fcap))
            if D(fcap) == 0:
                R.add("C6.v1_capacity_ratio", f"{key}|f{fcap}", D(0), D(0))
            else:
                R.add("C6.v1_capacity_ratio", f"{key}|f{fcap}", J_net(s) / base, floor_closed(lambda q: J_net(q) / J_net(dict(q, k=K0)), s))
    # version 2
    for NaP in ("9.9", "19.9", "69.8"):
        for BP in ("0.1", "1", "10"):
            for bn in ("0", "0.0001", "0.1", "1"):
                for V in ("-0.12", "-0.0899", "-0.0705", "-0.04", "0", "0.04"):
                    s = s_params(NaP=NaP, BP=BP, BN=bn, NaN="21", V=V)
                    key = f"NaP{NaP}|BP{BP}|BN{bn}|V{V}"
                    Jp, Jm, J, occ = v2_ka(s)
                    assert abs(J - v2_master(s)) <= abs(Jp) * D("1e-45") + D("1e-60"), (key, J, v2_master(s))
                    R.add("C6.v2_J_over_k", key, J, v2_floor(lambda q: v2_ka(q)[2], s))
                    if bn != "0":
                        ratio = Jm / Jp
                        xs = x_cyc(s)
                        assert abs(ratio / xs.exp() - 1) < D("1e-40")
                        R.add("C6.v2_ratio_Jm_Jp", key, ratio, v2_floor(v2_ratio, s))
                    else:
                        assert Jm == 0
    for NaP in ("9.9", "19.9", "69.8"):
        for BP in ("0.1", "1", "10"):
            s1 = s_params(NaP=NaP, BP=BP, BN="0", NaN="21", V="-0.0899")
            s2 = dict(s1, V=D("-0.0705"))
            rr = v2_ka(s1)[2] / v2_ka(s2)[2]
            R.add("C6.v2_early_ratio", f"NaP{NaP}|BP{BP}", rr, v2_floor(lambda q: v2_ka(dict(q, V=D("-0.0899")))[2] / v2_ka(dict(q, V=D("-0.0705")))[2], s1))
    Vrest_bath = M.V_ghk(M.build("primary", "bath", "291.15"))
    for NaP in ("9.9", "19.9", "69.8"):
        for BP in ("0.1", "1", "10"):
            s1 = s_params(NaP=NaP, BP=BP, BN="0", NaN="21", V=Vrest_bath - D("0.0194"))
            s2 = dict(s1, V=Vrest_bath)
            R.add("C6.v2_early_ratio_rest", f"NaP{NaP}|BP{BP}", v2_ka(s1)[2] / v2_ka(s2)[2],
                  v2_floor(lambda q: v2_ka(dict(q, V=Vrest_bath - D("0.0194")))[2] / v2_ka(dict(q, V=Vrest_bath))[2], s1))
    for NaP in ("9.9", "19.9", "69.8"):
        for BP in ("0.1", "1", "10"):
            for bn in ("0.0001", "0.1", "1"):
                s = s_params(NaP=NaP, BP=BP, BN=bn, NaN="21")
                Vf = V_stall(s)
                Vr = v2_stall_root(s)
                assert abs(Vf - Vr) < D("1e-30"), (Vf, Vr)
                R.add("C6.v2_V_stall", f"NaP{NaP}|BP{BP}|BN{bn}", Vr, floor_closed(V_stall, s))
    # alternate consistent constant set
    alt_q = [D(x) for x in ("0.1", "0.3", "-0.2", "0.5", "-0.4", "0.4", "0.3", "0")]
    saved = [dict(e) for e in EDGES]
    try:
        for i, e in enumerate(EDGES):
            e["q"] = alt_q[i]
        EDGES[0]["forward"] = dict(EDGES[0]["forward"], k0_per_s=EDGES[0]["forward"]["k0_per_s"] * 3)
        EDGES[0]["backward"] = dict(EDGES[0]["backward"], k0_per_s=EDGES[0]["backward"]["k0_per_s"] * 3)
        EDGES[3]["forward"] = dict(EDGES[3]["forward"], k0_per_s=EDGES[3]["forward"]["k0_per_s"] * D("0.5"))
        EDGES[3]["backward"] = dict(EDGES[3]["backward"], k0_per_s=EDGES[3]["backward"]["k0_per_s"] * D("0.5"))
        for NaP, BP, bn, V in (("9.9", "1", "0.1", "-0.0705"), ("19.9", "10", "0.0001", "-0.0899"), ("69.8", "0.1", "1", "0.02")):
            s = s_params(NaP=NaP, BP=BP, BN=bn, NaN="21", V=V)
            Jp, Jm, J, _ = v2_ka(s)
            assert abs(Jm / Jp / x_cyc(s).exp() - 1) < D("1e-40")
            R.add("C6.v2_alt_set_ratio", f"NaP{NaP}|BP{BP}|BN{bn}|V{V}", Jm / Jp, v2_floor(v2_ratio, s))
    finally:
        for i, e in enumerate(saved):
            EDGES[i].clear()
            EDGES[i].update(e)
    for n in (2, 3):
        R.add("C7.sym_cycle_counts", f"n{n}|dNa_in", D(n))
        R.add("C7.sym_cycle_counts", f"n{n}|dB_in", D(1))
        R.add("C7.sym_cycle_counts", f"n{n}|dNa_out", D(-n))
        R.add("C7.sym_cycle_counts", f"n{n}|dB_out", D(-1))
        R.add("C7.sym_cycle_counts", f"n{n}|charge_inward", D(n - 1))
    for k, v in (("dNa_cell", -3), ("dK_cell", 2), ("outward_charge", 1)):
        R.add("C7.pump_cycle_counts", k, D(v))
    R.add("C7.pump_cell_charge_per_fmol", "cell", -D(IN["conventions"]["CHARGE_PER_FMOL_C"]))
    # the pump's energy partition at the baseline states
    pm = IN["membranes"][0]["pump"]["metabolism"]
    for st in ("primary|bath|T291.15", "primary|local|T291.15"):
        ionset, ext, T = st.split("|")[0], st.split("|")[1], st.split("|")[2][1:]
        p = M.build(ionset, ext, T)
        for Vtag, V in (("Vghk", M.V_ghk(p)), ("V-0.04", D("-0.04"))):
            key = f"{st}|{Vtag}"
            RT = p["R"] * p["T"]
            dGc = 3 * RT * (p["cNa_o"] / p["cNa_i"]).ln() + 2 * RT * (p["cK_i"] / p["cK_o"]).ln()
            dUc = -p["F"] * V
            fn = lambda q, VV=V: 3 * q["R"] * q["T"] * (q["cNa_o"] / q["cNa_i"]).ln() + 2 * q["R"] * q["T"] * (q["cK_i"] / q["cK_o"]).ln()
            R.add("C7.pump_dG_chem", key, dGc, floor_closed(fn, p))
            R.add("C7.pump_dU_cap", key, dUc, floor_closed(lambda q, VV=V: -q["F"] * VV, p))
            q_mM = D(pm["adp_mM"]) * D(pm["pi_mM"]) / D(pm["atp_mM"])
            pq = dict(p, dg0=D(pm["delta_g0_J_per_mol"]), qatp=q_mM, Vv=V)

            def dG_atp(q):
                return q["dg0"] + q["R"] * q["T"] * (q["qatp"] / D(1000)).ln()

            def heat_fn(q):
                return -dG_atp(q) - (3 * q["R"] * q["T"] * (q["cNa_o"] / q["cNa_i"]).ln() + 2 * q["R"] * q["T"] * (q["cK_i"] / q["cK_o"]).ln()) + q["F"] * q["Vv"]
            R.add("C7.pump_dG_atp", key, dG_atp(pq), floor_closed(dG_atp, pq))
            R.add("C7.pump_heat", key, heat_fn(pq), floor_closed(heat_fn, pq))
            R.add("C7.pump_heat_nonneg", key, heat_fn(pq) >= 0)
