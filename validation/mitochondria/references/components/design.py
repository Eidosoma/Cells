"""Writes the component references' interface files; ``--check`` regenerates and compares.

    python -m validation.mitochondria.references.components.design [--check]

Files (interface/):
- inputs.json: constants, parameters, conventions, the band rule, every law's stoichiometry, and
  every state as float64 inputs. A kernel under test reads only this file.
- rows.json: per law and form, per state, the reference values (25 significant digits) and
  their bands, flags, and the binding closure's sensitivities.
- plants.json: per plant, its margins over the rows.
- checks.json: the physics checks, the appendix's numbers, the float64 calibration of the bands
  and the references' own precision (60 against 80 digits).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from . import checks, hp, laws, plants, states
from .hp import DEC, F64, precision

HERE = Path(__file__).resolve().parent
IFACE = HERE / "interface"

CB = Decimal(16)  # the band factor, in units of eps64 times each quantity's scale
EPS = Decimal(hp.EPS64)
OWN_REL = Decimal("1e-19")  # the references' own error: 20-digit storage (computation < 1e-50)
POWER = Decimal(3)  # a plant is caught at a row when some quantity misses by 3 bands or more
DIGITS = 20

# Each law's forms, from its FORMS: "declared" where the printed law passes; for Eqs. 11, 16 and
# 24, "balanced" (the appendix's, keeping the printed forward term), "printed", and the
# alternative repairs (the lead, 20 November): Eq. 24 "restored"; Eq. 11 "proton_restored" and
# "base_form_restored"; Eq. 16 "subscripts_swapped".
FORMS = {law.key: tuple(law.FORMS) for law in laws.CYCLE_LAWS}
FORMS["nadh_supply"] = ("declared",)
INPUT_KEYS = {
    "complex_I": ("dpsi_mV", "h_N", "h_P", "NADH_N", "NAD_N", "Q_N", "QH2_N"),
    "complex_III_eq7": ("dpsi_mV", "h_N", "h_P", "QH2_N", "Q_N", "c3_P", "c2_P"),
    "complex_III_eq24": ("dpsi_mV", "h_N", "h_P", "QH2_N", "Q_N", "c3_P", "c2_P", "Pi_N"),
    "complex_IV": ("dpsi_mV", "h_N", "h_P", "O2_N", "c2_P", "c3_P"),
    "lumped_QO": ("dpsi_mV", "h_N", "h_P", "QH2_N", "Q_N", "O2_N"),
    "atp_synthase": ("dpsi_mV", "h_N", "h_P", "ATP4_N", "ADP3_N", "HPO4_N", "MgADP_N", "MgATP_N",
                     "Pi_N", "H2PO4_N", "ATPtot_N", "ADPtot_N", "Mg_N"),
    "nucleotide_exchange": ("dpsi_mV", "ATP4_N", "ADP3_N", "ATP4_P", "ADP3_P", "MgATP_N",
                            "MgADP_N", "MgATP_P", "MgADP_P", "ATPtot_N", "ADPtot_N", "ATPtot_P",
                            "ADPtot_P", "Mg_N", "Mg_P"),
    "phosphate_carrier": ("dpsi_mV", "h_N", "h_P", "HPO4_N", "HPO4_P", "H2PO4_N", "H2PO4_P",
                          "Pi_N", "Pi_P"),
    "k_h_exchange": ("dpsi_mV", "h_N", "h_P", "K_N", "K_P"),
    "nadh_supply": ("NAD_N", "NADH_N", "Pi_N", "h_N"),
}
BINDING_SIDES = {"atp_synthase": ("N",), "nucleotide_exchange": ("N", "P"),
                 "phosphate_carrier": ("N", "P")}
SCALARS = ("x", "dG_J_per_mol", "affinity_J_per_mol", "static_head_mV", "S", "J_minus", "J",
           "A_term", "B_term", "lnB_over_A", "I_A_per_L", "dissipation_W_per_L",
           "dI_ddpsi_A_per_L_per_mV", "J_plus", "dG_conc_J_per_mol")
DICTS = ("slopes_lnS", "slopes_lnA", "slopes_lnB", "slopes_J")


# ============================================================================================
# States
# ============================================================================================
def law_states(law):
    """(id, kind, meta, exact state) for every row of ``law``."""
    P = hp.parameters(law.column)
    C = hp.constants(DEC)
    out = [("center", "center", {}, states.full_state(P, {}))]
    for sid, spec in states.corner_specs(law.key):
        out.append((sid, "corner", {}, states.full_state(P, spec)))
    for sid, spec in states.interior_specs(law.key):
        out.append((sid, "interior", {}, states.full_state(P, spec)))
    if law.key == "nadh_supply":
        return out
    nb = states.NEAR_EQ_BASE.get(law.key, {})
    bases = (("A", {**states.BASE, **nb}), ("B", {**states.BASE_B, **nb}))
    for bname, base in bases:
        s0 = states.full_state(P, base)
        for t in states.NEAR_EQ_TARGETS:
            out.append((f"near_eq:{bname}:x={t}", "near_eq", {"target_x": t},
                        checks.place_at_x(law, P, C, s0, Decimal(t))))
    if law.printed_fails:
        failing = [f for f in FORMS[law.key] if law.form_kind(f) == "two_term"]
        for form in failing:
            for bname, base in bases:
                s0 = states.full_state(P, base)
                d = law.form_d_closed(form, DEC, P, C, s0)
                out.append((f"stall:{form}:{bname}", "stall",
                            {"form": form, "target_x": hp.fmt(-d, 20)},
                            checks.place_at_x(law, P, C, s0, -d)))
        spec = {"pH_N": "7.2", "pH_P": "7.2"} if law.key == "phosphate_carrier" else {"pH_N": "7.0"}
        s0 = states.full_state(P, spec)
        for t in ("-0.5", "0.5"):
            out.append((f"coincidence:x={t}", "coincidence", {"target_x": t, **spec},
                        checks.place_at_x(law, P, C, s0, Decimal(t))))
    return out


def row_state(law, exact_state):
    """The float64 inputs of a row, and the exact state the references use (their values)."""
    keys = INPUT_KEYS[law.key]
    fl = {k: float(exact_state[k]) for k in keys}
    return fl, {k: Decimal(v) for k, v in fl.items()}


# ============================================================================================
# Bands
# ============================================================================================
def _ratio(diff: Decimal, band: Decimal) -> Decimal:
    """|diff|/band; a quantity that is exactly zero (I when q = 0) has band 0 and must match."""
    diff = abs(diff)
    if diff == 0:
        return Decimal(0)
    return diff / band if band > 0 else Decimal("Infinity")


def _up(d: Decimal) -> float:
    """A band rounded up to 3 significant digits."""
    if d == 0:
        return 0.0
    e = d.adjusted()
    q = Decimal(1).scaleb(e - 2)
    return float(d.quantize(q, rounding=ROUND_CEILING))


def _scale_ln(term, slopes, s, u):
    lin = Decimal(0)
    tot = Decimal(0)
    for v, sl in slopes.items():
        if v == "u":
            lin += sl * u
            tot += abs(sl * u) + abs(sl)
        else:
            lin += sl * s[v].ln()
            tot += abs(sl * s[v].ln()) + abs(sl)
    return abs(term.ln() - lin) + tot + 1


def bands_cycle(law, P, C, s, form, ref, extra_scale_x=Decimal(0)):
    """The bands of one row. ``extra_scale_x`` (M, default 0) widens x's scale for a kernel that
    builds dG0 by summing species potentials: M = sum |nu_s mu0_s|/RT over its legs."""
    nu = law.nu(P)
    q = law.q(P)
    xt = law.x_terms(DEC, P, C, s)
    scale_x = (sum(abs(v) for _k, v in xt) + sum(abs(Decimal(v)) for v in nu.values()) + abs(q) + 1
               + extra_scale_x)
    dx = CB * EPS * scale_x
    b = {"x": dx, "dG_J_per_mol": C["RT"] * dx, "affinity_J_per_mol": C["RT"] * dx}
    if q != 0:
        b["static_head_mV"] = dx / (abs(q) * C["F_RT_per_mV"]) + CB * EPS * abs(s["dpsi_mV"])
    if law.has_flux:
        u = C["F_RT_per_mV"] * s["dpsi_mV"]
        sA = law.form_slopes_A(form, DEC, P, C, s)
        dlnA = CB * EPS * _scale_ln(ref["A_term"], sA, s, u)
        J = ref["J"]
        if law.form_kind(form) == "two_term":
            sB = law.form_slopes_B(form, DEC, P, C, s)
            dlnB = CB * EPS * _scale_ln(ref["B_term"], sB, s, u)
            bA, bB = ref["A_term"] * dlnA, ref["B_term"] * dlnB
            b.update(S=bA, A_term=bA, J_minus=bB, B_term=bB, J=bA + bB, lnB_over_A=dlnA + dlnB)
            b["slopes_lnA"] = {v: CB * EPS * (1 + abs(sv)) for v, sv in ref["slopes_lnA"].items()}
            b["slopes_lnB"] = {v: CB * EPS * (1 + abs(sv)) for v, sv in ref["slopes_lnB"].items()}
            b["slopes_J"] = {
                v: abs(ref["slopes_lnA"][v]) * bA + ref["A_term"] * b["slopes_lnA"][v]
                + abs(ref["slopes_lnB"][v]) * bB + ref["B_term"] * b["slopes_lnB"][v]
                for v in ref["slopes_J"]}
        else:
            n = law.kappa_inv
            _E, _Z, w, dw = laws.kappa_parts(DEC, n, ref["x"])
            dlnS = dlnA + w * dx
            S, Jm = ref["S"], ref["J_minus"]
            bS, bJm, bJ = S * dlnS, Jm * (dlnS + dx), abs(J) * dlnS + Jm * dx
            b.update(S=bS, J_minus=bJm, J=bJ, A_term=ref["A_term"] * dlnA,
                     B_term=ref["B_term"] * (dlnA + dx / n))
            nu_u = {**nu, "u": q}
            b["slopes_lnS"] = {
                v: CB * EPS * (1 + abs(sA.get(v, Decimal(0))) + w * abs(Decimal(nu_u.get(v, 0))))
                + abs(Decimal(nu_u.get(v, 0))) * dw * dx
                for v in ref["slopes_lnS"]}
            b["slopes_J"] = {
                v: abs(ref["slopes_lnS"][v]) * bJ + abs(J) * b["slopes_lnS"][v]
                + abs(Decimal(nu_u.get(v, 0))) * bJm
                for v in ref["slopes_J"]}
        b["I_A_per_L"] = abs(q) * C["F"] * b["J"]
        # -J RT x is quadratic next to x = 0: the band carries the second-order term too.
        b["dissipation_W_per_L"] = C["RT"] * (abs(ref["x"]) * b["J"] + abs(J) * dx + b["J"] * dx)
        b["dI_ddpsi_A_per_L_per_mV"] = (abs(q) * C["F"] * C["F_RT_per_mV"] * b["slopes_J"]["u"]
                                        + CB * EPS * abs(ref["dI_ddpsi_A_per_L_per_mV"]))
    return _add_own(b, ref)


def bands_supply(P, C, s, ref):
    ops = Decimal(8)
    bJp = CB * EPS * ops * ref["J_plus"]
    bJm = CB * EPS * ops * ref["J_minus"]
    k1 = DEC.n(P["k_Pi1_mM"]) / 1000
    k2 = DEC.n(P["k_Pi2_mM"]) / 1000
    Pi = s["Pi_N"]
    sl = abs(Pi / (k1 + Pi) - Pi / (k2 + Pi))
    b = {
        "J": bJp + bJm, "J_plus": bJp, "J_minus": bJm,
        "dG_conc_J_per_mol": C["RT"] * CB * EPS * (abs(s["NADH_N"].ln()) + abs(s["h_N"].ln())
                                                   + abs(s["NAD_N"].ln()) + 1),
        "slopes_J": {"NAD_N": bJp, "NADH_N": bJm,
                     "Pi_N": sl * (bJp + bJm) + abs(ref["J"]) * CB * EPS * ops},
    }
    return _add_own(b, ref)


def _add_own(b, ref):
    out = {}
    for k, v in b.items():
        if isinstance(v, dict):
            out[k] = {kk: vv + OWN_REL * abs(ref[k][kk]) for kk, vv in v.items()}
        else:
            out[k] = v + OWN_REL * abs(ref[k])
    return out


# ============================================================================================
# Rows
# ============================================================================================
def reference(law, P, C, s, form):
    if law.key == "nadh_supply":
        return law.evaluate(DEC, P, C, s)
    return laws.evaluate(law, DEC, P, C, s, form)


def _ser(v):
    if isinstance(v, dict):
        return {k: hp.fmt(vv, DIGITS) for k, vv in v.items()}
    return hp.fmt(v, DIGITS)


def build_rows():
    """Every law's states and rows at PREC, with the PREC_CHECK re-run's largest differences."""
    out_states, out_rows, exact, refs = {}, {}, {}, {}
    own = {}
    for law in list(laws.CYCLE_LAWS) + [laws.SUPPLY]:
        P = hp.parameters(law.column)
        with precision():
            C = hp.constants(DEC)
            sts = law_states(law)
        out_states[law.key] = []
        exact[law.key] = sts
        out_rows[law.key] = {}
        refs[law.key] = {}
        worst_own = Decimal(0)
        for form in FORMS[law.key]:
            rows = []
            refs[law.key][form] = []
            for sid, kind, meta, s_exact in sts:
                fl, s = row_state(law, s_exact)
                if form == FORMS[law.key][0]:
                    out_states[law.key].append({"id": sid, "kind": kind, **meta, "inputs": fl})
                with precision():
                    ref = reference(law, P, C, s, form)
                    band = (bands_supply(P, C, s, ref) if law.key == "nadh_supply"
                            else bands_cycle(law, P, C, s, form, ref))
                with precision(hp.PREC_CHECK):
                    C80 = hp.constants(DEC)
                    ref80 = reference(law, P, C80, s, form)
                with precision(hp.PREC_CHECK):
                    for k, v in ref.items():
                        if isinstance(v, dict):
                            for kk, vv in v.items():
                                worst_own = max(worst_own, _ratio(vv - ref80[k][kk], band[k][kk]))
                        else:
                            worst_own = max(worst_own, _ratio(v - ref80[k], band[k]))
                flags = []
                if "J" in ref and abs(ref["J"]) <= band["J"]:
                    flags.append("sign_not_judged")
                if "x" in ref and ref["x"] < -80:
                    flags.append("x_below_minus_80")
                row = {"id": sid, "ref": {k: _ser(v) for k, v in ref.items()},
                       "band": {k: ({kk: _up(vv) for kk, vv in v.items()} if isinstance(v, dict)
                                    else _up(v)) for k, v in band.items()}}
                if flags:
                    row["flags"] = flags
                if law.key in BINDING_SIDES:
                    with precision():
                        sens = states.binding_sensitivities(P, s_binding(law, s))
                    row["binding"] = {side: {k: hp.fmt(v, 20) for k, v in sens[side].items()
                                             if _binding_key_applies(law.key, k)}
                                      for side in BINDING_SIDES[law.key]}
                rows.append(row)
                refs[law.key][form].append((sid, s, ref, band))
            out_rows[law.key][form] = rows
        own[law.key] = hp.fmt(worst_own, 3)
    return out_states, out_rows, exact, refs, own


def _binding_key_applies(law_key, k):
    """Mg2+ pairs for the adenylate laws, H+ pairs for the phosphate laws."""
    phosphate = "PO4" in k
    if law_key == "nucleotide_exchange":
        return not phosphate
    if law_key == "phosphate_carrier":
        return phosphate
    return True


def s_binding(law, s):
    """The free ligands a row's binding sensitivities need (Mg and h, with a default where the
    law does not read one)."""
    t = dict(s)
    for side in ("N", "P"):
        t.setdefault(f"Mg_{side}", Decimal("1e-3"))
        t.setdefault(f"h_{side}", Decimal("1e-7"))
    return t


# ============================================================================================
# The float64 calibration
# ============================================================================================
def _f64_orders(law, P, fl, form):
    C64 = hp.constants(F64)
    s = dict(fl)
    if law.key == "nadh_supply":
        return {"generic": law.evaluate(F64, P, C64, s)}
    res = {"generic": laws.evaluate(law, F64, P, C64, s, form)}
    if not law.has_flux:
        x2 = 0.0
        for _k, v in reversed(law.x_terms(F64, P, C64, s)):
            x2 += v
        res["reversed_sum"] = {"x": x2}
        res["appendix_dG"] = {"x": law.dG_appendix(F64, P, C64, s) / C64["RT"]}
        return res
    if law.form_kind(form) == "two_term":
        A_l, B_l = law.literal_terms(form, F64, P, C64, s)
        res["literal"] = {"J": A_l - B_l, "A_term": A_l, "B_term": B_l}
        return res
    if form in ("declared", "balanced"):
        x = law.dG_appendix(F64, P, C64, s) / C64["RT"]
        S = law.S_closed(F64, P, C64, s)
        res["closed"] = {"x": x, "S": S, "J": S * (1.0 - math.exp(x)), "J_minus": S * math.exp(x)}
    x2 = 0.0
    for _k, v in reversed(law.x_terms(F64, P, C64, s)):
        x2 += v
    A = law.literal_terms(form, F64, P, C64, s)[0]
    n = law.kappa_inv
    Bt = A * math.exp(x2 / n)
    Z = sum(math.exp(j * x2 / n) for j in range(n))
    res["two_term"] = {"x": x2, "J": A - Bt, "S": A / Z, "J_minus": A / Z * math.exp(x2),
                       "A_term": A, "B_term": Bt}
    return res


def calibrate(refs):
    """Worst |float64 - reference| / band per law, form, order and quantity."""
    out = {}
    worst_all = Decimal(0)
    for key, forms in refs.items():
        law = laws.LAWS_BY_KEY[key]
        P = hp.parameters(law.column)
        out[key] = {}
        for form, rows in forms.items():
            agg = {}
            for sid, s, ref, band in rows:
                fl = {k: float(v) for k, v in s.items()}
                for order, vals in _f64_orders(law, P, fl, form).items():
                    for k, v in vals.items():
                        if k not in ref:
                            continue
                        if isinstance(v, dict):
                            for kk, vv in v.items():
                                if kk not in ref[k]:
                                    continue
                                r = _ratio(Decimal(vv) - ref[k][kk], band[k][kk])
                                name = f"{order}:{k}"
                                agg[name] = max(agg.get(name, Decimal(0)), r)
                        else:
                            r = _ratio(Decimal(v) - ref[k], band[k])
                            name = f"{order}:{k}"
                            agg[name] = max(agg.get(name, Decimal(0)), r)
            out[key][form] = {k: hp.fmt(v, 3) for k, v in sorted(agg.items())}
            worst_all = max([worst_all] + list(agg.values()))
    return {"worst_ratio_to_band": hp.fmt(worst_all, 3), "passes": worst_all <= 1,
            "by_law": out}


# ============================================================================================
# Plants
# ============================================================================================
def _margins(v, ref, band):
    m = {}
    for k in SCALARS:
        if k in ref and k in v:
            m[k] = _ratio(v[k] - ref[k], band[k])
    for dk in DICTS:
        if dk in ref and dk in v:
            for var, rv in ref[dk].items():
                if var in v[dk]:
                    m[f"{dk}.{var}"] = _ratio(v[dk][var] - rv, band[dk][var])
    return m


def measure_plants(refs):
    out = {}
    for pl in plants.PLANTS:
        law = laws.LAWS_BY_KEY[pl.law_key]
        entry = {"law": pl.law_key, "kind": pl.kind, "description": pl.description,
                 "section_8_named": pl.named, "by_form": {}}
        for form, rows in refs[pl.law_key].items():
            if pl.forms is not None and form not in pl.forms:
                continue
            n = caught = caught_J = 0
            zero = []
            zero_values = []
            no_J = []
            best = None
            min_caught = None
            by_q = {}
            for sid, s, ref, band in rows:
                with precision():
                    v = pl.values(s, form)
                    m = _margins(v, ref, band)
                excl = pl.exclude_for(form)
                m = {k: val for k, val in m.items() if k.split(".")[0] not in excl}
                n += 1
                if "J" in m:
                    if m["J"] >= POWER:
                        caught_J += 1
                    if m["J"] < 1:
                        no_J.append(sid)
                top_q, top = max(m.items(), key=lambda kv: kv[1])
                for k, val in m.items():
                    fam = k.split(".")[0]
                    cur = by_q.setdefault(fam, [0, Decimal(0)])
                    if val >= POWER:
                        cur[0] += 1
                    cur[1] = max(cur[1], val)
                if top >= POWER:
                    caught += 1
                    if min_caught is None or top < min_caught[0]:
                        min_caught = (top, sid, top_q)
                if top < 1:
                    zero.append(sid)
                if max((val for k, val in m.items() if not k.startswith("slopes")), default=0) < 1:
                    zero_values.append(sid)
                if best is None or top > best[0]:
                    best = (top, sid, top_q)
            entry["by_form"][form] = {
                "rows": n, "caught": caught, "zero_power": zero,
                "zero_power_values_only": zero_values,
                "caught_by_J_alone": caught_J if law.has_flux else None,
                "no_power_on_J": no_J if law.has_flux else None,
                "excluded_quantities": list(pl.exclude_for(form)),
                "max_margin": hp.fmt(best[0], 3), "max_at": best[1], "max_quantity": best[2],
                "min_margin_where_caught": None if min_caught is None else hp.fmt(min_caught[0], 3),
                "min_at": None if min_caught is None else min_caught[1],
                "by_quantity": {k: {"caught": c, "max_margin": hp.fmt(mx, 3)}
                                for k, (c, mx) in sorted(by_q.items())},
            }
        entry["caught"] = all(f["caught"] > 0 for f in entry["by_form"].values())
        out[pl.pid] = entry
    return out


# ============================================================================================
# Checks
# ============================================================================================
def run_checks(exact, refs):
    out = {"appendix_numbers": checks.appendix_numbers(), "laws": {}}
    for law in laws.CYCLE_LAWS:
        sts = [(sid, s) for sid, _k, _m, s in exact[law.key]]
        res = checks.law_checks(law, sts)
        P = hp.parameters(law.column)
        if law.has_flux:
            nb = states.NEAR_EQ_BASE.get(law.key, {})
            bases = [("A", states.full_state(P, {**states.BASE, **nb})),
                     ("B", states.full_state(P, {**states.BASE_B, **nb}))]
            res["equilibrium"] = {f: checks.equilibrium_checks(law, bases, f)
                                  for f in FORMS[law.key] if law.form_kind(f) == "kappa"}
            if law.printed_fails:
                grid = [(sid, s) for sid, k, _m, s in exact[law.key] if k in ("corner", "interior", "center")]
                res["violation"] = {f: checks.printed_violation(law, grid, bases, f)
                                    for f in FORMS[law.key] if law.form_kind(f) == "two_term"}
        form0 = FORMS[law.key][0]
        xs = [r[2]["x"] for r in refs[law.key][form0]]
        grid_x = [r[2]["x"] for r, (sid, k, _m, _s) in zip(refs[law.key][form0], exact[law.key])
                  if k in ("corner", "center", "interior")]
        res["x_range_rows"] = {"min": hp.fmt(min(xs), 6), "max": hp.fmt(max(xs), 6)}
        res["x_range_grid"] = {"min": hp.fmt(min(grid_x), 6), "max": hp.fmt(max(grid_x), 6)}
        res["rows_below_x_minus_80"] = [sid for (sid, _s, ref, _b) in refs[law.key][form0]
                                       if ref["x"] < -80]
        res["extremes_x_below_minus_80"] = checks.extremes(
            law, [(sid, s) for (sid, s, _r, _b) in refs[law.key][form0]])
        out["laws"][law.key] = res
    out["supply"] = checks.supply_checks([(sid, s) for sid, _k, _m, s in exact["nadh_supply"]])
    out["planted_controls"] = checks.planted_controls()
    qo_states = [(sid, s) for sid, _k, _m, s in exact["lumped_QO"]]
    out["lumped_identity"] = checks.lumped_identity(qo_states)
    out["form_identities"] = checks.form_identities(
        {k: [(sid, s) for sid, _kk, _m, s in v] for k, v in exact.items()})
    out["binding_chain"] = checks.binding_chain_check(
        [(sid, s) for sid, _k, _m, s in exact["atp_synthase"]][:12])
    return out


# ============================================================================================
# Files
# ============================================================================================
def law_meta():
    meta = {}
    with precision():
        C = hp.constants(DEC)
        for law in laws.CYCLE_LAWS:
            P = hp.parameters(law.column)
            m = {
                "law": law.law_id, "section": law.section, "title": law.title,
                "parameter_column": law.column,
                "legs": [{"species": k or "H2O", "side": side, "nu": nu, "z": z}
                         for k, side, nu, z in law.legs_(P)],
                "q": law.q(P),
                "dG0_pH7_J_per_mol": hp.fmt(law.dG0_pH7(DEC, P), 12),
                "scalar_protons": law.scalar_protons,
                "dG0_1M_J_per_mol": hp.fmt(law.dG0_1M(DEC, P, C), DIGITS),
                "dG0_1M_in_RT": hp.fmt(law.dG0_1M(DEC, P, C) / C["RT"], DIGITS),
                "reads_S": list(law.reads_S), "reads_x": list(law.reads_x),
                "has_flux": law.has_flux, "kappa": f"1/{law.kappa_inv}",
                "printed": law.printed_eq, "printed_fails": law.printed_fails,
                "forms": {f: {"kind": law.form_kind(f),
                              "balanced": True if f == "declared" else law.form_balanced(f),
                              "reads": law.form_reads(f)}
                          for f in FORMS[law.key]},
            }
            meta[law.key] = m
        sp = laws.SUPPLY
        meta[sp.key] = {"law": sp.law_id, "section": sp.section, "title": sp.title,
                        "parameter_column": sp.column,
                        "legs": [{"species": k, "side": side, "nu": nu, "z": z}
                                 for k, side, nu, z in sp.legs],
                        "q": sp.q(None), "reads": list(sp.reads), "has_flux": True,
                        "printed": sp.printed_eq, "forms": ["declared"],
                        "work": "W = J (dG0_DH + RT ln(NADH h_N/NAD)); dG0_DH is the world's input"}
    return meta


def inputs_doc(st):
    with precision():
        C = hp.constants(DEC)
        consts = {k: hp.fmt(v, 30) for k, v in C.items()}
    return {
        "kind": "cells.mito_component_reference_inputs@1",
        "status": "proposed, not registered",
        "source": "docs/MITOCHONDRIA_LAWS_APPENDIX.md at tag mito-laws-appendix-2026-11-20",
        "units": {"concentrations": "M (h_N, h_P free H+)", "dpsi": "mV, phi_P - phi_N",
                  "J": "mol s-1 (L mito)-1", "dG": "J mol-1", "I": "A (L mito)-1",
                  "dissipation": "W (L mito)-1"},
        "constants": {"T_K": hp.T_KELVIN, "N_A": hp.N_A, "k_B": hp.K_B, "e": hp.E_CHARGE,
                      **consts},
        "parameters": {"with_pi_control": hp.parameters("with"),
                       "without_pi_control_X_C3": hp.PARAMS_WITHOUT_PI_CONTROL["X_C3"]},
        "band_rule": {
            "eps64": hp.fmt(EPS, 17), "factor": str(CB), "own_rel": str(OWN_REL),
            "power_margin": str(POWER),
            "statement": ("band = factor * eps64 * scale + own_rel * |value|; the scales are in "
                          "README.md and design.bands_cycle"),
        },
        "laws": law_meta(),
        "states": st,
    }


def _dump_rows(doc):
    """JSON with one row per line."""
    lines = ["{"]
    head = {k: v for k, v in doc.items() if k != "laws"}
    for k, v in head.items():
        lines.append(f" {json.dumps(k)}: {json.dumps(v, sort_keys=True)},")
    lines.append(' "laws": {')
    law_items = list(doc["laws"].items())
    for i, (lk, forms) in enumerate(law_items):
        lines.append(f"  {json.dumps(lk)}: {{")
        form_items = list(forms.items())
        for j, (fk, rows) in enumerate(form_items):
            lines.append(f"   {json.dumps(fk)}: [")
            for r, row in enumerate(rows):
                comma = "," if r < len(rows) - 1 else ""
                lines.append("    " + json.dumps(row, sort_keys=True, separators=(",", ":")) + comma)
            lines.append("   ]" + ("," if j < len(form_items) - 1 else ""))
        lines.append("  }" + ("," if i < len(law_items) - 1 else ""))
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _dump_states(doc):
    """inputs.json: the states one per line, the rest indented."""
    st = doc["states"]
    body = {k: v for k, v in doc.items() if k != "states"}
    text = json.dumps(body, indent=1, sort_keys=True)
    lines = [text[:-2] + ",", ' "states": {']
    keys = list(st)
    for i, lk in enumerate(keys):
        lines.append(f"  {json.dumps(lk)}: [")
        for r, row in enumerate(st[lk]):
            comma = "," if r < len(st[lk]) - 1 else ""
            lines.append("   " + json.dumps(row, sort_keys=True, separators=(",", ":")) + comma)
        lines.append("  ]" + ("," if i < len(keys) - 1 else ""))
    lines.append(" }")
    lines.append("}")
    return "\n".join(lines) + "\n"


def generate():
    st, rows, exact, refs, own = build_rows()
    files = {}
    files["inputs.json"] = _dump_states(inputs_doc(st))
    files["rows.json"] = _dump_rows({
        "kind": "cells.mito_component_reference_rows@1", "status": "proposed, not registered",
        "digits": DIGITS, "inputs": "interface/inputs.json", "laws": rows})
    files["plants.json"] = json.dumps({
        "kind": "cells.mito_component_reference_plants@1", "status": "proposed, not registered",
        "power_margin": str(POWER), "plants": measure_plants(refs)}, indent=1, sort_keys=True) + "\n"
    chk = run_checks(exact, refs)
    chk["own_precision_worst_diff_60_vs_80_digits_over_band"] = own
    chk["float64_calibration"] = calibrate(refs)
    files["checks.json"] = json.dumps({"kind": "cells.mito_component_reference_checks@1", **chk},
                                      indent=1, sort_keys=True) + "\n"
    return files


def _strip_calibration(text):
    d = json.loads(text)
    cal = d.pop("float64_calibration")
    return d, cal


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="regenerate and compare")
    args = ap.parse_args(argv)
    files = generate()
    if args.check:
        bad = []
        for name, text in files.items():
            old = (IFACE / name).read_text()
            if name == "checks.json":
                d_new, cal_new = _strip_calibration(text)
                d_old, _cal_old = _strip_calibration(old)
                if d_new != d_old or not cal_new["passes"]:
                    bad.append(name)
            elif old != text:
                bad.append(name)
        print("check:", "identical" if not bad else f"differs: {bad}")
        return 1 if bad else 0
    IFACE.mkdir(exist_ok=True)
    for name, text in files.items():
        (IFACE / name).write_text(text)
        print(f"wrote interface/{name} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
