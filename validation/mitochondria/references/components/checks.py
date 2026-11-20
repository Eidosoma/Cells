"""Checks of the physics, at exact high-precision states (no float64 rounding).

Each function returns a JSON-ready dict of measured values and verdicts. ``design.py`` writes
them to interface/checks.json; the fast test runs a few of them at a few states.
"""
from __future__ import annotations

from decimal import Decimal

from . import hp, laws, states
from .hp import DEC, precision

TOL_EXACT = Decimal("1e-45")  # identities that hold exactly, at 60 digits
FD_STEP = Decimal("1e-20")  # central differences at 60 digits: error about 1e-38
TOL_FD = Decimal("1e-30")


def _f(x, digits=6):
    return hp.fmt(x, digits)


def params_for(law):
    return hp.parameters(law.column)


def place_at_x(law, P, C, s, x_target):
    """Move a state along one input so that law.x = x_target (exactly, at 60 digits)."""
    x_target = DEC.n(x_target)
    q = law.q(P)
    if q != 0:
        s0 = dict(s, dpsi_mV=Decimal(0))
        x0 = law.x(DEC, P, C, s0)
        return dict(s, dpsi_mV=(x_target - x0) / (q * C["F_RT_per_mV"]))
    # A neutral law: split the move between the two sides, half each, to keep both moderate.
    half = ((x_target - law.x(DEC, P, C, s)) / 2).exp()
    if law.key == "phosphate_carrier":
        t = states.set_phosphate(P, s, "N", s["HPO4_N"] * half)
        return states.set_phosphate(P, t, "P", s["HPO4_P"] / half)
    if law.key == "k_h_exchange":
        return dict(s, K_N=s["K_N"] * half, K_P=s["K_P"] / half)
    if law.key == "nadh_supply":
        # Move [NADH]/[NAD] at the fixed pool: x changes by ln of the ratio's factor.
        rho = s["NADH_N"] / s["NAD_N"] * (half * half)
        tot = s["NADH_N"] + s["NAD_N"]
        return dict(s, NADH_N=tot * rho / (1 + rho), NAD_N=tot / (1 + rho))
    if law.key == "adenylate_kinase":
        # Split between AMP and the Mg-free ATP (both nu = +1), binding kept.
        t = states.set_atp_free(P, s, "P", s["ATP4_P"] * half)
        t["AMP_P"] = s["AMP_P"] * half
        return t
    raise ValueError(law.key)


# --------------------------------------------------------------------------------------------
def appendix_numbers():
    """Reproduce the second tag's own numbers and compare each to its printed rounding."""
    out = {}
    with precision():
        C = hp.constants(DEC)
        P = hp.parameters("with")

        def at(display, value, quantum):
            v = value.quantize(Decimal(quantum))
            return {"display": display, "exact": _f(value, 12), "rounded": str(v),
                    "agrees": str(v) == display}

        out["RT_J_per_mol"] = at("2478.9570", C["RT"], "0.0001")
        out["F_over_RT_per_mV"] = at("0.0389217", C["F_RT_per_mV"], "0.0000001")
        out["RT_ln_1e7_kJ_per_mol"] = at("39.9561", C["RT_ln_1e7"] / 1000, "0.0001")
        entries = {
            "complex_I": ("-109.326", "-44.1016"),
            "complex_III_eq24": ("47.382", "19.1137"),
            "complex_IV": ("-405.704", "-163.6593"),
            "lumped_QO": ("-310.940", "-125.4318"),
            "atp_synthase": ("-5.032", "-2.0299"),
            "nadh_supply": ("39.956", "16.1181"),
            "adenylate_kinase": ("2.341", "0.9443"),
        }
        fe = {}
        for key, (kj, inrt) in entries.items():
            law = laws.LAWS_BY_KEY[key]
            g = law.dG0_1M(DEC, P, C)
            fe[key] = {"kJ_per_mol": at(kj, g / 1000, "0.001"),
                       "in_RT": at(inrt, g / C["RT"], "0.0001")}
        out["free_energy_entries_1M"] = fe
        # The first tag's complex III entry at 310.15 K, corrected (+50.598452).
        C310 = hp.constants(DEC, T="310.15")
        out["complex_III_at_310.15K_kJ_per_mol"] = at(
            "50.598452", laws.LAWS_BY_KEY["complex_III_eq24"].dG0_1M(DEC, P, C310) / 1000, "0.000001")
        # Stalls and slopes: dimensionless, unchanged by the temperature.
        ln10 = Decimal(10).ln()
        h74 = (-Decimal("7.4") * ln10).exp()
        h71 = (-Decimal("7.1") * ln10).exp()
        s = {"h_N": h74, "h_P": h71}
        c3 = laws.LAWS_BY_KEY["complex_III_eq24"]
        f1 = laws.LAWS_BY_KEY["atp_synthase"]
        pc = laws.LAWS_BY_KEY["phosphate_carrier"]
        k = DEC.n(P["k_dH"])
        out["eq24_stall_x_at_pH_N_7.4"] = at("-1.84", -c3.d_closed(DEC, P, C, s), "0.01")
        out["eq11_stall_x_at_pH_N_7.4"] = at("0.68", -f1.d_closed(DEC, P, C, s), "0.01")
        out["eq11_stall_x_source_frame_at_pH_N_7.4"] = at(
            "0.92", -f1.d_closed_source_frame(DEC, P, C, s), "0.01")
        out["eq11_mismatch_slope_in_ln_h_N_at_7.4"] = at("0.82", k / (k + h74), "0.01")
        out["eq16_stall_x_at_pH_P_7.1_pH_N_7.4"] = at("-1.38", -pc.d_closed(DEC, P, C, s), "0.01")
        # Section 6: the held ratio and the planted control's shift.
        r_with, r_without = DEC.n(P["r"]), DEC.n(hp.parameters("without")["r"])
        f01 = (-Decimal("0.10") * ln10).exp()
        out["supply_held_ratio_factor"] = at("0.794328", f01, "0.000001")
        out["supply_S_red_over_S_ox_with"] = at("3.63858", f01 * r_with, "0.00001")
        out["supply_S_red_over_S_ox_without"] = at("3.37828", f01 * r_without, "0.00001")
        out["supply_S_ox_over_S_red_with"] = at("0.274833", 1 / (f01 * r_with), "0.000001")
        out["supply_S_ox_over_S_red_without"] = at("0.296009", 1 / (f01 * r_without), "0.000001")
        out["supply_planted_x_shift"] = at("0.2303", Decimal("0.10") * ln10, "0.0001")
        # Section 7: the match.
        m, K_base = hp.ak_match(DEC, P)
        out["ak_m_mM"] = at("3.808553529", m, "0.000000001")
        out["ak_K_base"] = at("0.388964538", K_base, "0.000000001")
        out["ak_prefactor_at_matched_m"] = at("159.69", 1 + m / (DEC.n(P["K_MgATP"]) * 1000), "0.01")
        ak = laws.LAWS_BY_KEY["adenylate_kinase"]
        out["ak_K_tot_at_matched_m"] = at("0.4331", ak.K_tot(DEC, P, m / 1000), "0.0001")
        # Section 9's potentials (9 decimals) and section 10's M (3 decimals).
        mu = hp.potentials(DEC, P, C)
        table = {"cytc_red": "40.914814298", "QH2": "62.715891459", "NADH": "106.817529855",
                 "ATP": "-2.029938769", "S_red": "90.699434204", "AMP": "2.974205870",
                 "MgATP": "-12.667395497", "MgADP": "-7.966185778", "H2PO4": "-15.542437799"}
        out["potentials"] = {k: at(v, mu[k], "0.000000001") for k, v in table.items()}
        mt = {"complex_I": "259.334", "complex_III_eq24": "227.439", "complex_IV": "308.722",
              "lumped_QO": "325.757", "atp_synthase": "57.292", "nucleotide_exchange": "31.691",
              "phosphate_carrier": "41.447", "k_h_exchange": "27.631", "nadh_supply": "232.056",
              "adenylate_kinase": "32.635"}
        out["band_M"] = {}
        for key, disp in mt.items():
            law = laws.LAWS_BY_KEY[key]
            out["band_M"][key] = at(disp, hp.band_M(DEC, law.legs_(P), mu, C), "0.001")
        # Each law's entry equals sum nu mu0/RT over the potentials.
        w = Decimal(0)
        for law in laws.CYCLE_LAWS:
            Pl = hp.parameters(law.column)
            mu_l = hp.potentials(DEC, Pl, C)
            g = sum(DEC.n(nu) * mu_l[hp.species_of(k)] for k, _sd, nu, _z in law.legs_(Pl) if k is not None)
            w = max(w, abs(g - law.dG0_1M(DEC, Pl, C) / C["RT"]))
        out["entries_equal_sum_nu_mu0"] = {"worst_abs": _f(w, 3), "agrees": w <= TOL_EXACT}
    out["all_agree"] = all(v.get("agrees", True) for v in _leaves(out))
    return out


def _leaves(d):
    for v in d.values():
        if isinstance(v, dict) and "agrees" in v:
            yield v
        elif isinstance(v, dict):
            yield from _leaves(v)


# --------------------------------------------------------------------------------------------
def numeric_slopes(law, P, C, s, which, form="declared"):
    """Central differences of ln S (a kappa form) or of ln A / ln B (a two-term form's terms),
    in ln(input) and in u, from paths 1 and 2 only."""

    def lnval(t):
        if which == "S":
            x = law.x(DEC, P, C, t)
            A = law.form_forward(form, DEC, P, C, t)
            _E, Z, _w, _dw = laws.kappa_parts(DEC, law.kappa_inv, x)
            return (A / Z).ln()
        A, Bp = law.form_terms(form, DEC, P, C, t)
        return A.ln() if which == "A" else Bp.ln()

    keys = set(law.reads())
    if which == "A":
        keys |= set(law.form_slopes_A(form, DEC, P, C, s))
    if which == "B":
        keys |= set(law.form_slopes_B(form, DEC, P, C, s))
    keys.discard("u")
    out = {}
    for v in sorted(keys):
        hp_ = dict(s)
        hm = dict(s)
        hp_[v] = s[v] * FD_STEP.exp()
        hm[v] = s[v] * (-FD_STEP).exp()
        out[v] = (lnval(hp_) - lnval(hm)) / (2 * FD_STEP)
    du = FD_STEP / C["F_RT_per_mV"]
    out["u"] = (lnval(dict(s, dpsi_mV=s["dpsi_mV"] + du)) - lnval(dict(s, dpsi_mV=s["dpsi_mV"] - du))) / (
        2 * FD_STEP)
    return out


def numeric_J_slopes(law, P, C, s, form, keys):
    """Central differences of J in ln(input) and in u, computed from paths 1 and 2 only."""

    def J_of(t):
        if law.form_kind(form) == "two_term":
            A, Bp = law.form_terms(form, DEC, P, C, t)
            return A - Bp
        x = law.x(DEC, P, C, t)
        A = law.form_forward(form, DEC, P, C, t)
        _E, Z, _w, _dw = laws.kappa_parts(DEC, law.kappa_inv, x)
        return -(A / Z) * DEC.expm1(x)

    out = {}
    for v in keys:
        if v == "u":
            du = FD_STEP / C["F_RT_per_mV"]
            out[v] = (J_of(dict(s, dpsi_mV=s["dpsi_mV"] + du))
                      - J_of(dict(s, dpsi_mV=s["dpsi_mV"] - du))) / (2 * FD_STEP)
        else:
            out[v] = (J_of(dict(s, **{v: s[v] * FD_STEP.exp()}))
                      - J_of(dict(s, **{v: s[v] * (-FD_STEP).exp()}))) / (2 * FD_STEP)
    return out


def supply_checks(exact_states):
    """Section 6: the held ratio puts the supply's equilibrium at [NADH]/[NAD] = r at pH_N 7.10;
    the balanced J is X_DH phi (r[NAD] - [NADH] h_N/10^-7.10); it equals Eq. 1 at pH_N 7.10."""
    sp = laws.LAWS_BY_KEY["nadh_supply"]
    P = hp.parameters(sp.column)
    out = {}
    w_closed = w_eq1 = Decimal(0)
    with precision():
        C = hp.constants(DEC)
        r = DEC.n(P["r"])
        for _sid, s in exact_states:
            ref = laws.evaluate(sp, DEC, P, C, s, "balanced")
            Xphi = DEC.n(P["X_DH"]) * sp.phi(DEC, P, s)
            closed = Xphi * (r * s["NAD_N"] - s["NADH_N"] * s["h_N"] / sp.h_ref(DEC, P))
            w_closed = max(w_closed, abs(ref["J"] - closed) / (ref["A_term"] + ref["B_term"]))
        # At pH_N 7.10 and [NADH] = r[NAD]: x = 0, and the balanced J equals Eq. 1's.
        s0 = states.full_state(P, {"h_N": sp.h_ref(DEC, P)})
        tot = s0["NADH_N"] + s0["NAD_N"]
        at = dict(s0, NADH_N=tot * r / (1 + r), NAD_N=tot / (1 + r))
        x_at = sp.x(DEC, P, C, at)
        for frac in ("0.3", "0.5", "0.9"):
            t_ = dict(s0, NADH_N=tot * DEC.n(frac), NAD_N=tot * (1 - DEC.n(frac)))
            A, Bp = sp.printed(DEC, P, C, t_)
            b = laws.evaluate(sp, DEC, P, C, t_, "balanced")
            w_eq1 = max(w_eq1, abs(b["J"] - (A - Bp)) / (A + Bp))
    # The upkeep's work is the heat plus the work delivered to the NAD pool:
    # -J (mu_S_ox - mu_S_red) = -J dG + J (mu_NADH + mu_H - mu_NAD), from section 9's potentials.
    w_bal = Decimal(0)
    with precision():
        C = hp.constants(DEC)
        mu = hp.potentials(DEC, P, C)
        for _sid, s in exact_states:
            ref = laws.evaluate(sp, DEC, P, C, s, "balanced")
            J = ref["J"]
            y_del = mu["NADH"] + mu["H"] - mu["NAD"] + (s["NADH_N"] * s["h_N"] / s["NAD_N"]).ln()
            delivered = J * C["RT"] * y_del
            lhs = ref["upkeep_work_W_per_L"]
            rhs = ref["dissipation_W_per_L"] + delivered
            # Scaled by J+ RT and the terms' sizes, which never vanish (J does, at x = 0).
            scale = ref["S"] * C["RT"] * (abs(sp.upkeep_y(DEC, P, C, s)) + abs(y_del) + abs(ref["x"]) + 1)
            w_bal = max(w_bal, abs(lhs - rhs) / scale)
    out["upkeep_equals_heat_plus_delivered_rel"] = _f(w_bal, 3)
    out["balanced_J_closed_form_rel"] = _f(w_closed, 3)
    out["x_at_r_and_pH_7.10"] = _f(x_at, 3)
    out["balanced_equals_eq1_at_pH_7.10_rel"] = _f(w_eq1, 3)
    out["passes"] = (w_closed <= TOL_EXACT and abs(x_at) <= TOL_EXACT and w_eq1 <= TOL_EXACT
                     and w_bal <= TOL_EXACT)
    return out


def kinase_checks(exact_states):
    """Section 7: the balanced law equals the source's form on totals with
    K_tot = K_base (1 + m/K_MgATP)/(1 + m/K_MgADP)^2 at the IMS's free Mg2+; at the matched m,
    K_tot = K_AK and the printed Eq. 18 passes; the prefactor is the ratio of total to free ATP."""
    ak = laws.LAWS_BY_KEY["adenylate_kinase"]
    P = hp.parameters(ak.column)
    w_tot = w_pref = Decimal(0)
    with precision():
        C = hp.constants(DEC)
        X = DEC.n(P["X_AK"])
        for _sid, s in exact_states:
            b = laws.evaluate(ak, DEC, P, C, s, "balanced")
            Kt = ak.K_tot(DEC, P, s["Mg_P"])
            tot_form = X * (Kt * s["ADPtot_P"] ** 2 - s["AMP_P"] * s["ATPtot_P"])
            w_tot = max(w_tot, abs(b["J"] - tot_form) / (b["A_term"] + b["B_term"]))
            # The prefactor: the forward term over the no-prefactor form's is total/free ATP.
            no_pref_forward = X * hp.ak_match(DEC, P)[1] * s["ADP3_P"] ** 2
            w_pref = max(w_pref, abs(b["S"] / no_pref_forward / (s["ATPtot_P"] / s["ATP4_P"]) - 1))
        m, _K = hp.ak_match(DEC, P)
        s0 = states.full_state(P, {"Mg_P": m / 1000})
        d_m = ak.d_closed(DEC, P, C, s0)
    return {"balanced_equals_totals_form_rel": _f(w_tot, 3),
            "prefactor_is_total_over_free_ATP_rel": _f(w_pref, 3),
            "eq18_mismatch_at_matched_m": _f(d_m, 3),
            "passes": w_tot <= TOL_EXACT and w_pref <= TOL_EXACT and abs(d_m) <= TOL_EXACT}


def outer_membrane_checks(exact_states):
    """Section 8: each form's J dG <= 0, J = 0 where the form is equal on both sides and reverses
    past it; the class sums equal Eq. 13 on totals; the slopes against central differences."""
    om = laws.OUTER
    P = hp.parameters(om.column)
    w_sum = w_slope = Decimal(0)
    min_diss = None
    ok_rev = True
    with precision():
        C = hp.constants(DEC)
        for _sid, s in exact_states:
            r = om.evaluate(DEC, P, C, s)
            for f, _c, _z in om.OM_FORMS:
                d = r["dissipation_W_per_L"][f]
                min_diss = d if min_diss is None else min(min_diss, d)
                for side, sign in (("E", 1), ("P", -1)):
                    key = f"{f}_{side}"
                    up = om.evaluate(DEC, P, C, dict(s, **{key: s[key] * FD_STEP.exp()}))["J"][f]
                    dn = om.evaluate(DEC, P, C, dict(s, **{key: s[key] * (-FD_STEP).exp()}))["J"][f]
                    fd = (up - dn) / (2 * FD_STEP)
                    w_slope = max(w_slope, abs(fd - r["slopes_J"][key]) / (r["S"][f] + r["J_minus"][f]))
            for c in om.CLASS_TOTALS:
                scale = om.k(DEC, P, "Pi" if c == "Pi" else "A") * (
                    s[f"{om.CLASS_TOTALS[c][1]}_E"] + s[f"{om.CLASS_TOTALS[c][1]}_P"])
                w_sum = max(w_sum, abs(r["class_J"][c] - r["eq13_J"][c]) / scale)
        # Equal on both sides: every J = 0; scaled by e^{+-d}: each J reverses with the sign of d.
        s0 = states.full_state(P, {})
        same = states.scale_side(P, dict(s0, **{k.replace("_E", "_P"): v for k, v in s0.items()
                                               if k.endswith("_E")}), "P", Decimal(1))
        r0 = om.evaluate(DEC, P, C, same)
        zero = max(abs(v) for v in r0["J"].values())
        for dlt in ("-1e-3", "1e-3", "1"):
            t_ = states.scale_side(P, same, "P", DEC.n(dlt).exp())
            rr = om.evaluate(DEC, P, C, t_)
            for f, _c, _z in om.OM_FORMS:
                ok_rev = ok_rev and ((rr["J"][f] < 0) == (DEC.n(dlt) > 0)) and rr["dissipation_W_per_L"][f] > 0
    return {"class_sum_vs_eq13_rel": _f(w_sum, 3), "slopes_J_rel": _f(w_slope, 3),
            "min_dissipation_W_per_L": _f(min_diss, 6), "J_at_equal_sides": _f(zero, 3),
            "reversal": ok_rev,
            "passes": (w_sum <= TOL_EXACT and w_slope <= TOL_FD and min_diss >= 0
                       and zero <= TOL_EXACT and ok_rev)}


def law_checks(law, exact_states):
    """Every check of one cycle law, form by form, over a list of (id, exact state)."""
    P = params_for(law)
    res = {}
    with precision():
        C = hp.constants(DEC)
        legs = law.legs_(P)
        q = law.q(P)
        res["charge"] = {
            "q_from_legs": q,
            "sum_nu_z_all_legs": sum(nu * z for _k, _s, nu, z in legs),
            "q_N": law.q_N(P),
            "conserved": sum(nu * z for _k, _s, nu, z in legs) == 0 and law.q_N(P) == -q,
        }
        common = {"x_vs_appendix_dG": Decimal(0), "static_head_x": Decimal(0)}
        for _sid, s in exact_states:
            x = law.x(DEC, P, C, s)
            common["x_vs_appendix_dG"] = max(common["x_vs_appendix_dG"],
                                             abs(x - law.dG_appendix(DEC, P, C, s) / C["RT"]))
            if q != 0:
                sh = law.x(DEC, P, C, dict(s, dpsi_mV=s["dpsi_mV"] - x / (q * C["F_RT_per_mV"])))
                common["static_head_x"] = max(common["static_head_x"], abs(sh))
        res["n_states"] = len(exact_states)
        res["worst_common"] = {k: _f(v, 3) for k, v in common.items()}
        ok = bool(res["charge"]["conserved"]) and all(v <= TOL_EXACT for v in common.values())
        res["forms"] = {}
        if law.has_flux:
            forms = [f for f in law.FORMS] if law.printed_fails else ["declared"]
            for form in forms:
                fr = _form_checks(law, P, C, form, exact_states)
                res["forms"][form] = fr
                ok = ok and fr["passes"]
        res["passes"] = ok
    return res


def _form_checks(law, P, C, form, exact_states):
    """One form: its terms against their literal transcription, its balance (d = 0) or its
    closed-form mismatch, S's closed form, the slopes, J's slopes, q F dJ/dpsi, and (balanced
    forms) S > 0 and -J dG >= 0."""
    kind = law.form_kind(form)
    balanced = law.form_balanced(form) if form != "declared" else True
    w = {k: Decimal(0) for k in ("terms_vs_literal_rel", "d", "S_closed_rel", "slopes_S",
                                 "slopes_A", "slopes_B", "slopes_J", "dI_ddpsi_rel")}
    min_diss = min_S = None
    q = law.q(P)
    for _sid, s in exact_states:
        x = law.x(DEC, P, C, s)
        ref = laws.evaluate(law, DEC, P, C, s, form)
        A_l, B_l = law.literal_terms(form, DEC, P, C, s)
        if kind == "two_term":
            A, Bp = law.form_terms(form, DEC, P, C, s)
        else:
            A = law.form_forward(form, DEC, P, C, s)
            Bp = A * (x / law.kappa_inv).exp()
        w["terms_vs_literal_rel"] = max(w["terms_vs_literal_rel"], abs(A / A_l - 1), abs(Bp / B_l - 1))
        d = law.kappa_inv * (B_l / A_l).ln() - x
        if balanced:
            w["d"] = max(w["d"], abs(d))
        else:
            w["d"] = max(w["d"], abs(d - law.form_d_closed(form, DEC, P, C, s)))
        if form in ("declared", "balanced"):
            w["S_closed_rel"] = max(w["S_closed_rel"], abs(law.S_closed(DEC, P, C, s) / ref["S"] - 1))
        if kind == "kappa":
            num = numeric_slopes(law, P, C, s, "S", form)
            w["slopes_S"] = max(w["slopes_S"], max(abs(num[v] - ref["slopes_lnS"][v]) for v in num))
            min_diss = ref["dissipation_W_per_L"] if min_diss is None else min(min_diss, ref["dissipation_W_per_L"])
            min_S = ref["S"] if min_S is None else min(min_S, ref["S"])
        else:
            for which, key in (("A", "slopes_lnA"), ("B", "slopes_lnB")):
                numw = numeric_slopes(law, P, C, s, which, form)
                w[f"slopes_{which}"] = max(w[f"slopes_{which}"],
                                           max(abs(numw[v] - ref[key].get(v, Decimal(0))) for v in numw))
        numJ = numeric_J_slopes(law, P, C, s, form, ref["slopes_J"])
        w["slopes_J"] = max(w["slopes_J"], max(abs(numJ[v] - ref["slopes_J"][v]) for v in numJ)
                            / (ref["A_term"] + ref["B_term"]))
        if q != 0:
            h = FD_STEP
            Ip = laws.evaluate(law, DEC, P, C, dict(s, dpsi_mV=s["dpsi_mV"] + h), form)["I_A_per_L"]
            Im = laws.evaluate(law, DEC, P, C, dict(s, dpsi_mV=s["dpsi_mV"] - h), form)["I_A_per_L"]
            fd = (Ip - Im) / (2 * h)
            scale = abs(ref["dI_ddpsi_A_per_L_per_mV"]) + abs(q) * C["F"] * C["F_RT_per_mV"] * (
                ref["A_term"] + ref["B_term"])
            w["dI_ddpsi_rel"] = max(w["dI_ddpsi_rel"], abs(fd - ref["dI_ddpsi_A_per_L_per_mV"]) / scale)
    tol = {"terms_vs_literal_rel": TOL_EXACT, "d": TOL_EXACT, "S_closed_rel": TOL_EXACT,
           "slopes_S": TOL_FD, "slopes_A": TOL_FD, "slopes_B": TOL_FD, "slopes_J": TOL_FD,
           "dI_ddpsi_rel": TOL_FD}
    out = {"kind": kind, "balanced": balanced, "worst": {k: _f(v, 3) for k, v in w.items()}}
    ok = all(w[k] <= tol[k] for k in w)
    if kind == "kappa":
        out["min_S"] = _f(min_S, 6)
        out["min_dissipation_W_per_L"] = _f(min_diss, 6)
        ok = ok and min_S > 0 and min_diss >= 0
    out["passes"] = ok
    return out


def equilibrium_checks(law, base_states, form):
    """J = 0 at x = 0, reversal past it, and -J dG > 0, at exact states placed next to x = 0."""
    P = params_for(law)
    out = {"rows": []}
    ok = True
    with precision():
        C = hp.constants(DEC)
        for bname, s0 in base_states:
            for t in ("-3", "-1", "-1e-3", "-1e-9", "0", "1e-9", "1e-3", "1", "3"):
                s = place_at_x(law, P, C, s0, Decimal(t))
                r = laws.evaluate(law, DEC, P, C, s, form)
                J_over_S = r["J"] / r["S"]
                x = r["x"]
                if t == "0":
                    good = abs(J_over_S) <= TOL_EXACT
                else:
                    good = (J_over_S > 0) == (x < 0) and r["dissipation_W_per_L"] > 0
                ok = ok and good
                out["rows"].append({"base": bname, "x_target": t, "x": _f(x, 4),
                                    "J_over_S": _f(J_over_S, 6), "ok": good})
    out["passes"] = ok
    return out


def printed_violation(law, grid_states, base_states, form="printed"):
    """Quantify a failing two-term form: its mismatch d, where it stalls, and its uphill band."""
    P = params_for(law)
    out = {}
    with precision():
        C = hp.constants(DEC)
        n_up = 0
        n = 0
        worst = None
        worst_rel = None
        d_min = d_max = None
        for sid, s in grid_states:
            pr = laws.evaluate(law, DEC, P, C, s, form)
            d = law.form_d_closed(form, DEC, P, C, s)
            d_min = d if d_min is None else min(d_min, d)
            d_max = d if d_max is None else max(d_max, d)
            n += 1
            diss = pr["dissipation_W_per_L"]
            if diss < 0:
                n_up += 1
                rel = diss / (pr["S"] * C["RT"])
                if worst is None or diss < worst[0]:
                    worst = (diss, sid)
                if worst_rel is None or rel < worst_rel[0]:
                    worst_rel = (rel, sid)
        out["grid"] = {"n_states": n, "n_uphill": n_up,
                       "d_min": _f(d_min), "d_max": _f(d_max),
                       "most_negative_dissipation_W_per_L": None if worst is None else _f(worst[0]),
                       "at": None if worst is None else worst[1],
                       "most_negative_dissipation_over_Jplus_RT": None if worst_rel is None else _f(worst_rel[0]),
                       "at_rel": None if worst_rel is None else worst_rel[1]}
        # In the band between the form's zero (x = -d) and equilibrium, J dG > 0.
        rows = []
        for bname, s0 in base_states:
            d = law.form_d_closed(form, DEC, P, C, s0)
            for frac in ("0", "0.25", "0.5", "0.75", "1"):
                xt = -d * Decimal(frac)
                s = place_at_x(law, P, C, s0, xt)
                pr = laws.evaluate(law, DEC, P, C, s, form)
                bal = laws.evaluate(law, DEC, P, C, s, "balanced")
                rows.append({
                    "base": bname, "d": _f(d), "x": _f(pr["x"], 6),
                    "J_form_over_Jplus": _f(pr["J"] / pr["S"], 6),
                    "J_balanced_over_Jplus": _f(bal["J"] / bal["S"], 6),
                    "dissipation_form_W_per_L": _f(pr["dissipation_W_per_L"], 6),
                    "dissipation_balanced_W_per_L": _f(bal["dissipation_W_per_L"], 6),
                    "backward_ratio_form_over_balanced": _f(pr["B_term"] / bal["B_term"], 8),
                })
        out["band_between_zero_and_equilibrium"] = rows
    return out


def planted_controls():
    """Section 10's two planted controls (refused by the equilibrium check), and those sections 6
    and 7 name: the held ratio r (x smaller by 0.10 ln 10 at every state) and the kinase without
    its prefactor (the right equilibrium, a rate smaller by 1 + [Mg2+]_P/K_MgATP)."""
    from . import plants

    out = {}
    with precision():
        C = hp.constants(DEC)
        for pid in ("C1_q_reversed", "ANT_shares_0.35_0.60"):
            pl = plants.PLANTS_BY_ID[pid]
            law = laws.LAWS_BY_KEY[pl.law_key]
            P = params_for(law)
            rows = []
            refused = False
            for bname, spec in (("A", states.BASE), ("B", states.BASE_B)):
                s0 = states.full_state(P, spec)
                for t_ in ("-1", "0", "1"):
                    s = place_at_x(law, P, C, s0, Decimal(t_))
                    v = pl.values(s, "declared")
                    x_true = law.x(DEC, P, C, s)
                    J_over_S = v["J"] / v["S"]
                    wrong = (abs(J_over_S) > TOL_EXACT) if t_ == "0" else ((J_over_S > 0) != (x_true < 0))
                    refused = refused or wrong
                    rows.append({"base": bname, "x_true": _f(x_true, 4), "J_over_S": _f(J_over_S, 6),
                                 "violates": wrong})
            out[pid] = {"refused": refused, "rows": rows}
        sp = laws.LAWS_BY_KEY["nadh_supply"]
        P = params_for(sp)
        pl = plants.PLANTS_BY_ID["supply_held_ratio_r"]
        w = Decimal(0)
        for spec in (states.BASE, states.BASE_B, {"pH_N": "7.1"}):
            s = states.full_state(P, spec)
            w = max(w, abs(pl.values(s, "balanced")["x"] - sp.x(DEC, P, C, s) + Decimal("0.10") * Decimal(10).ln()))
        out["supply_held_ratio_r"] = {"x_shift_is_minus_0.10_ln10_worst": _f(w, 3),
                                      "refused": w <= TOL_EXACT}
        ak = laws.LAWS_BY_KEY["adenylate_kinase"]
        P = params_for(ak)
        pl = plants.PLANTS_BY_ID["AK_no_prefactor"]
        w = Decimal(0)
        for spec in (states.BASE, states.BASE_B):
            s = states.full_state(P, spec)
            ref = laws.evaluate(ak, DEC, P, C, s, "balanced")
            v = pl.values(s, "balanced")
            w = max(w, abs(ref["J"] / v["J"] / (1 + s["Mg_P"] / DEC.n(P["K_MgATP"])) - 1),
                    abs(v["x"] - ref["x"]))
        out["AK_no_prefactor"] = {"rate_ratio_is_1_plus_Mg_over_K_MgATP_worst": _f(w, 3),
                                  "refused": w <= TOL_EXACT}
    return out


def lumped_identity(exact_states):
    """x_QO = 2 x_III + x_IV: cytochrome c, the scalar protons and the electrons cancel."""
    qo = laws.LAWS_BY_KEY["lumped_QO"]
    c3 = laws.LAWS_BY_KEY["complex_III_eq24"]
    c4 = laws.LAWS_BY_KEY["complex_IV"]
    worst = Decimal(0)
    with precision():
        P = hp.parameters("with")
        C = hp.constants(DEC)
        for _sid, s in exact_states:
            worst = max(worst, abs(qo.x(DEC, P, C, s) - 2 * c3.x(DEC, P, C, s) - c4.x(DEC, P, C, s)))
    return {"worst_abs": _f(worst, 3), "passes": worst <= TOL_EXACT}


def form_identities(exact_states_by_law):
    """Identities between forms: Eq. 14 as printed equals A - B; Section 4's two dG forms agree;
    Section 2's mismatch in the source's own frame is exactly ln(h_N/1e-7)."""
    out = {}
    with precision():
        C = hp.constants(DEC)
        P = hp.parameters("with")
        ant = laws.LAWS_BY_KEY["nucleotide_exchange"]
        w = Decimal(0)
        for _sid, s in exact_states_by_law["nucleotide_exchange"]:
            A, Bp = ant.printed(DEC, P, C, s)
            w = max(w, abs(ant.printed_literal(DEC, P, C, s) - (A - Bp)) / (A + Bp))
        out["eq14_literal_vs_two_terms"] = {"worst_rel": _f(w, 3), "passes": w <= TOL_EXACT}
        pc = laws.LAWS_BY_KEY["phosphate_carrier"]
        w = Decimal(0)
        for _sid, s in exact_states_by_law["phosphate_carrier"]:
            w = max(w, abs(pc.dG_appendix(DEC, P, C, s) - pc.dG_appendix_H2PO4(DEC, P, C, s)) / C["RT"])
        out["section4_dG_base_vs_H2PO4_forms"] = {"worst_abs_x": _f(w, 3), "passes": w <= TOL_EXACT}
        f1 = laws.LAWS_BY_KEY["atp_synthase"]
        w = Decimal(0)
        for _sid, s in exact_states_by_law["atp_synthase"]:
            A, Bp = f1.printed(DEC, P, C, s)
            d_src = (Bp / A).ln() - f1.x_source_frame(DEC, P, C, s)
            w = max(w, abs(d_src - f1.d_closed_source_frame(DEC, P, C, s)))
        out["eq11_source_frame_mismatch_is_ln_h_N_over_1e-7"] = {"worst_abs": _f(w, 3),
                                                                 "passes": w <= TOL_EXACT}
        # Eq. 24 restored is phi_Pi times Eq. 7 (Eq. 7's own class at the With column's X_C3),
        # and its J is the balanced J times 1e-7/h_N.
        c24 = laws.LAWS_BY_KEY["complex_III_eq24"]
        c7 = laws.ComplexIIIEq7()
        w1 = w2 = Decimal(0)
        for _sid, s in exact_states_by_law["complex_III_eq24"]:
            phi = c24.phi(DEC, P, s)
            A7, B7 = c7.printed(DEC, P, C, s)
            r = laws.evaluate(c24, DEC, P, C, s, "restored")
            b = laws.evaluate(c24, DEC, P, C, s, "balanced")
            w1 = max(w1, abs(phi * (A7 - B7) - r["J"]) / (phi * (A7 + B7)))
            w2 = max(w2, abs(r["J"] - b["J"] * Decimal("1e-7") / s["h_N"]) / (r["A_term"] + r["B_term"]))
        out["eq24_restored_is_phi_times_eq7"] = {"worst_rel": _f(w1, 3), "passes": w1 <= TOL_EXACT}
        out["eq24_restored_is_balanced_times_1e-7_over_h_N"] = {"worst_rel": _f(w2, 3),
                                                               "passes": w2 <= TOL_EXACT}
    return out


def binding_chain_check(exact_states):
    """The binding sensitivities chain the slopes onto totals: for Section 2, compare
    d ln S/d ln(total ADP), d ln S/d ln Mg and dx/d ln h_N at fixed totals with central
    differences of S and x recomputed from totals."""
    f1 = laws.LAWS_BY_KEY["atp_synthase"]
    P = hp.parameters("with")
    worst = Decimal(0)
    with precision():
        C = hp.constants(DEC)
        for _sid, s in exact_states:
            sens = states.binding_sensitivities(P, s)["N"]
            ref = laws.evaluate(f1, DEC, P, C, s, "balanced")
            sS = ref["slopes_lnS"]
            nu = f1.nu(P)
            chained = {
                "ADPtot": sS["MgADP_N"] * sens["dln_MgADP_N/dln_ADPtot_N"],
                "Mg": sS["MgADP_N"] * sens["dln_MgADP_N/dln_Mg_N"],
                "x_hN": nu["h_N"] + nu["HPO4_N"] * sens["dln_HPO4_N/dln_h_N"],
            }

            def rebuild(t):
                kATP, kADP, kdH = DEC.n(P["K_MgATP"]), DEC.n(P["K_MgADP"]), DEC.n(P["k_dH"])
                r = dict(t)
                r["ATP4_N"] = t["ATPtot_N"] / (1 + t["Mg_N"] / kATP)
                r["MgATP_N"] = r["ATP4_N"] * t["Mg_N"] / kATP
                r["ADP3_N"] = t["ADPtot_N"] / (1 + t["Mg_N"] / kADP)
                r["MgADP_N"] = r["ADP3_N"] * t["Mg_N"] / kADP
                r["HPO4_N"] = t["Pi_N"] * kdH / (kdH + t["h_N"])
                r["H2PO4_N"] = t["Pi_N"] * t["h_N"] / (kdH + t["h_N"])
                return r

            def lnS(t):
                return laws.evaluate(f1, DEC, P, C, rebuild(t), "balanced")["S"].ln()

            def xx(t):
                return f1.x(DEC, P, C, rebuild(t))

            h = FD_STEP
            e_p, e_m = h.exp(), (-h).exp()
            num = {
                "ADPtot": (lnS(dict(s, ADPtot_N=s["ADPtot_N"] * e_p)) - lnS(dict(s, ADPtot_N=s["ADPtot_N"] * e_m))) / (2 * h),
                "Mg": (lnS(dict(s, Mg_N=s["Mg_N"] * e_p)) - lnS(dict(s, Mg_N=s["Mg_N"] * e_m))) / (2 * h),
                "x_hN": (xx(dict(s, h_N=s["h_N"] * e_p)) - xx(dict(s, h_N=s["h_N"] * e_m))) / (2 * h),
            }
            # h_N also enters S directly and through the Pi forms only via HPO4 in x (S reads
            # total Pi), so x's chained slope is nu_hN + nu_HPO4 dln HPO4/dln h.
            for k in num:
                worst = max(worst, abs(num[k] - chained[k]))
    return {"worst_abs": _f(worst, 3), "passes": worst <= TOL_FD}


def extremes(law, row_refs):
    """At rows with x < -80: J-/J+ = e^x (declared), and the printed terms' ratio is e^{x/n}."""
    out = {"n": 0, "worst_rel": "0"}
    if not law.has_flux:
        return out
    P = params_for(law)
    worst = Decimal(0)
    n = 0
    with precision():
        C = hp.constants(DEC)
        for _rid, s in row_refs:
            x = law.x(DEC, P, C, s)
            if x >= -80:
                continue
            n += 1
            form = "balanced" if law.printed_fails else "declared"
            r = laws.evaluate(law, DEC, P, C, s, form)
            worst = max(worst, abs(r["J_minus"] / r["S"] / x.exp() - 1))
            if not law.printed_fails:
                A, Bp = law.printed(DEC, P, C, s)
                worst = max(worst, abs((Bp / A) / (x / law.kappa_inv).exp() - 1))
    return {"n": n, "worst_rel": _f(worst, 3), "passes": worst <= TOL_EXACT}
