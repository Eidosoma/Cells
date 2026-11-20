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
    raise ValueError(law.key)


# --------------------------------------------------------------------------------------------
def appendix_numbers():
    """Reproduce the appendix's own numbers and compare each to its printed rounding."""
    out = {}
    with precision():
        C = hp.constants(DEC)
        P = hp.parameters("with")

        def at(display, value, quantum):
            v = value.quantize(Decimal(quantum))
            return {"display": display, "exact": _f(value, 12), "rounded": str(v),
                    "agrees": str(v) == display}

        out["RT_J_per_mol"] = at("2578.7306", C["RT"], "0.0001")
        out["F_over_RT_per_mV"] = at("0.0374158", C["F_RT_per_mV"], "0.0000001")
        out["RT_ln_1e7_kJ_per_mol"] = at("41.5642", C["RT_ln_1e7"] / 1000, "0.0001")
        entries = {
            "complex_I": ("-110.934", "-43.0189"),
            "complex_III_eq24": ("50.599", "19.6215"),
            "complex_IV": ("-412.137", "-159.8216"),
            "lumped_QO": ("-310.940", "-120.5787"),
            "atp_synthase": ("-6.685", "-2.5923"),
        }
        fe = {}
        for key, (kj, inrt) in entries.items():
            law = laws.LAWS_BY_KEY[key]
            g = law.dG0_1M(DEC, P, C)
            fe[key] = {"kJ_per_mol": at(kj, g / 1000, "0.001"),
                       "in_RT": at(inrt, g / C["RT"], "0.0001")}
        out["free_energy_entries_1M"] = fe
        # Stalls of the printed forms and the slope of Eq. 11's mismatch, at the appendix's pHs.
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
        out["eq24_mismatch_range_over_section8_pH_N"] = {
            "pH_N_6.8": _f(-2 * (Decimal("0.2") * ln10)),
            "pH_N_8.2": _f(-2 * (Decimal("-1.2") * ln10)),
        }
        dvals = {}
        for pH in ("6.8", "7.0", "7.4", "8.2"):
            h = (-Decimal(pH) * ln10).exp()
            dvals[f"pH_N_{pH}"] = _f(f1.d_closed(DEC, P, C, {"h_N": h}))
        out["eq11_mismatch_over_section8_pH_N"] = dvals
        out["eq16_mismatch_range_over_section8"] = {
            "min_pH_N_6.8_pH_P_7.6": _f(2 * (Decimal("6.8") - Decimal("7.6")) * ln10),
            "max_pH_N_8.2_pH_P_6.5": _f(2 * (Decimal("8.2") - Decimal("6.5")) * ln10),
        }
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
    """Central differences of ln S (declared) or ln A / ln B (printed terms) in ln(input), u."""

    def lnval(t):
        if which == "S":
            x = law.x(DEC, P, C, t)
            A, _ = law.printed(DEC, P, C, t)
            _E, Z, _w, _dw = laws.kappa_parts(DEC, law.kappa_inv, x)
            return (A / Z).ln()
        A, Bp = law.printed(DEC, P, C, t)
        return A.ln() if which == "A" else Bp.ln()

    out = {}
    keys = set(law.reads())
    if which == "A":
        keys |= set(law.slopes_lnA(DEC, P, C, s))
    if which == "B":
        keys |= set(law.slopes_lnB(DEC, P, C, s))
    keys.discard("u")
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


def law_checks(law, exact_states):
    """Every check of one cycle law over a list of (id, exact state)."""
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
        worst = {k: Decimal(0) for k in ("x_vs_appendix_dG", "S_closed_rel", "printed_vs_declared",
                                         "d_vs_closed", "backward_closed_rel", "slopes_S",
                                         "slopes_A", "slopes_B", "dI_ddpsi_rel", "static_head_x")}
        min_diss = None
        n_states = 0
        for sid, s in exact_states:
            n_states += 1
            x = law.x(DEC, P, C, s)
            worst["x_vs_appendix_dG"] = max(worst["x_vs_appendix_dG"],
                                            abs(x - law.dG_appendix(DEC, P, C, s) / C["RT"]))
            if q != 0:
                sh = law.x(DEC, P, C, dict(s, dpsi_mV=s["dpsi_mV"] - x / (q * C["F_RT_per_mV"])))
                worst["static_head_x"] = max(worst["static_head_x"], abs(sh))
            if not law.has_flux:
                continue
            form = "balanced" if law.printed_fails else "declared"
            ref = laws.evaluate(law, DEC, P, C, s, form)
            S = ref["S"]
            worst["S_closed_rel"] = max(worst["S_closed_rel"], abs(law.S_closed(DEC, P, C, s) / S - 1))
            A, Bp = law.printed(DEC, P, C, s)
            d = law.kappa_inv * (Bp / A).ln() - x
            if law.printed_fails:
                worst["d_vs_closed"] = max(worst["d_vs_closed"], abs(d - law.d_closed(DEC, P, C, s)))
                bc = law.backward_closed(DEC, P, C, s)
                worst["backward_closed_rel"] = max(worst["backward_closed_rel"],
                                                   abs(bc / ref["B_term"] - 1))
            else:
                worst["d_vs_closed"] = max(worst["d_vs_closed"], abs(d))
                worst["printed_vs_declared"] = max(worst["printed_vs_declared"],
                                                   abs((A - Bp) - ref["J"]) / (A + Bp))
            diss = ref["dissipation_W_per_L"] / (S * C["RT"])
            min_diss = diss if min_diss is None else min(min_diss, diss)
            num = numeric_slopes(law, P, C, s, "S")
            worst["slopes_S"] = max(worst["slopes_S"],
                                    max(abs(num[v] - ref["slopes_lnS"][v]) for v in num))
            if law.printed_fails:
                pr = laws.evaluate(law, DEC, P, C, s, "printed")
                for which, key in (("A", "slopes_lnA"), ("B", "slopes_lnB")):
                    numw = numeric_slopes(law, P, C, s, which)
                    worst[f"slopes_{which}"] = max(worst[f"slopes_{which}"],
                                                   max(abs(numw[v] - pr[key].get(v, Decimal(0)))
                                                       for v in numw))
            if q != 0:
                h = FD_STEP
                Ip = laws.evaluate(law, DEC, P, C, dict(s, dpsi_mV=s["dpsi_mV"] + h), form)["I_A_per_L"]
                Im = laws.evaluate(law, DEC, P, C, dict(s, dpsi_mV=s["dpsi_mV"] - h), form)["I_A_per_L"]
                fd = (Ip - Im) / (2 * h)
                scale = abs(ref["dI_ddpsi_A_per_L_per_mV"]) + abs(q) * C["F"] * C["F_RT_per_mV"] * (
                    abs(ref["J"]) + ref["J_minus"])
                worst["dI_ddpsi_rel"] = max(worst["dI_ddpsi_rel"],
                                            abs(fd - ref["dI_ddpsi_A_per_L_per_mV"]) / scale)
        res["n_states"] = n_states
        res["worst"] = {k: _f(v, 3) for k, v in worst.items()}
        if law.has_flux:
            res["min_dissipation_over_S_RT"] = _f(min_diss, 6)
        tol_ok = {
            "x_vs_appendix_dG": TOL_EXACT, "S_closed_rel": TOL_EXACT,
            "printed_vs_declared": TOL_EXACT, "d_vs_closed": TOL_EXACT,
            "backward_closed_rel": TOL_EXACT, "slopes_S": TOL_FD, "slopes_A": TOL_FD,
            "slopes_B": TOL_FD, "dI_ddpsi_rel": TOL_FD, "static_head_x": TOL_EXACT,
        }
        res["passes"] = bool(res["charge"]["conserved"]) and all(worst[k] <= tol_ok[k] for k in worst) and (
            min_diss is None or min_diss >= -TOL_EXACT)
    return res


def equilibrium_checks(law, base_states):
    """J = 0 at x = 0, reversal past it, and J dG <= 0, at exact states placed next to x = 0."""
    P = params_for(law)
    out = {"rows": []}
    ok = True
    with precision():
        C = hp.constants(DEC)
        form = "balanced" if law.printed_fails else "declared"
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


def printed_violation(law, grid_states, base_states):
    """Quantify a failing printed form: its mismatch d, where it stalls, and its uphill band."""
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
            pr = laws.evaluate(law, DEC, P, C, s, "printed")
            d = law.d_closed(DEC, P, C, s)
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
        # In the band between the printed zero (x = -d) and equilibrium, J_printed dG > 0.
        rows = []
        for bname, s0 in base_states:
            d = law.d_closed(DEC, P, C, s0)
            for frac in ("0", "0.25", "0.5", "0.75", "1"):
                xt = -d * Decimal(frac)
                s = place_at_x(law, P, C, s0, xt)
                pr = laws.evaluate(law, DEC, P, C, s, "printed")
                bal = laws.evaluate(law, DEC, P, C, s, "balanced")
                rows.append({
                    "base": bname, "d": _f(d), "x": _f(pr["x"], 6),
                    "J_printed_over_Jplus": _f(pr["J"] / pr["S"], 6),
                    "J_balanced_over_Jplus": _f(bal["J"] / bal["S"], 6),
                    "dissipation_printed_W_per_L": _f(pr["dissipation_W_per_L"], 6),
                    "dissipation_balanced_W_per_L": _f(bal["dissipation_W_per_L"], 6),
                    "backward_ratio_printed_over_balanced": _f(pr["B_term"] / bal["B_term"], 8),
                })
        out["band_between_printed_zero_and_equilibrium"] = rows
    return out


def planted_controls():
    """Section 8's two planted controls; the thermodynamic check must refuse both."""
    from . import plants

    out = {}
    with precision():
        for pid in ("C1_q_reversed", "ANT_shares_0.35_0.60"):
            pl = plants.PLANTS_BY_ID[pid]
            law = laws.LAWS_BY_KEY[pl.law_key]
            P = params_for(law)
            C = hp.constants(DEC)
            rows = []
            refused = False
            for bname, spec in (("A", states.BASE), ("B", states.BASE_B)):
                s0 = states.full_state(P, spec)
                for t in ("-1", "0", "1"):
                    s = place_at_x(law, P, C, s0, Decimal(t))
                    v = pl.values(s, "declared")
                    x_true = law.x(DEC, P, C, s)
                    J_over_S = v["J"] / v["S"]
                    wrong = (abs(J_over_S) > TOL_EXACT) if t == "0" else ((J_over_S > 0) != (x_true < 0))
                    refused = refused or wrong
                    rows.append({"base": bname, "x_true": _f(x_true, 4), "J_over_S": _f(J_over_S, 6),
                                 "violates": wrong})
            out[pid] = {"refused": refused, "rows": rows}
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
