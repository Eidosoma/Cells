"""Entry points: the references on one law, state, system or node, as doubles (see the usage note).

Every value is computed in 60-digit decimals from the registered inputs (read as their doubles)
and rounded once to the nearest double here.
"""

from __future__ import annotations

import copy
import math
from decimal import Decimal

from . import binding as Bd
from . import cycles as C
from . import diagrams as D
from . import exact
from .exact import context, dec, fl


def _f(x):
    if isinstance(x, dict):
        return {str(k) if not isinstance(k, tuple) else "|".join(map(str, k)): _f(v)
                for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_f(v) for v in x]
    if isinstance(x, (Decimal, exact.Dual)):
        return fl(x)
    return x


# --------------------------------------------------------------------------------------------
# Seam A
# --------------------------------------------------------------------------------------------

def dG_terms_abs(nu, registry, law_state) -> float:
    """Σ |terms| of ΔG/RT in doubles: the scale of its rounding."""
    F, R = float(exact.FARADAY), float(exact.GAS_CONSTANT)
    T = float(registry["temperature_K"])
    c0 = float(registry["standard_concentration_mM"])
    out = 0.0
    for s, e, n in nu:
        sp = registry["species"][s]
        out += abs(n * float(sp["mu0_RT"]))
        out += abs(n * math.log(float(law_state["c_mM"][e][s]) / c0))
        out += abs(n * sp["valence"] * F * float(law_state["phi_V"][e]) / (R * T))
    return out


def cycle_state(law, population, registry, host_state, volumes_pL, with_slopes=True) -> dict:
    """Everything the probes record at one registered state, and the population's rates."""
    ls = C.law_state(population, host_state)
    out = {"tag": host_state.get("tag")}
    with context():
        pr = C.population_rates(law, population, registry, host_state)
        fl_ = pr["modes"]
        modes = {}
        for m in C.modes(law):
            q = fl_[m["id"]]
            row = {"dG_RT": q["dG_RT"], "J": q["J"],
                   "dG_RT_terms_abs": dG_terms_abs(m["nu"], registry, ls)}
            for key in ("S", "J_plus", "J_minus", "J_scale", "J_minus_diagram", "Pi_plus",
                        "Pi_minus", "sigma_share"):
                if key in q:
                    row[key] = q[key]
            modes[m["id"]] = row
        out["modes"] = modes
        if law["kind"] == "diagram":
            rates = fl_["_rates"]
            p = fl_["_p"]
            ef = D.edge_fluxes(law, rates, p)
            scale = (dec(population["capacity_fmol_per_s"]) *
                     dec(population.get("availability", 1.0)) / dec(law["rate_scale_per_s"]))
            out["edges"] = {e: {"alpha_fwd_per_s": rates[e][0], "alpha_bwd_per_s": rates[e][1],
                                "oneway_fwd_per_carrier_per_s": ef[e][0],
                                "oneway_bwd_per_carrier_per_s": ef[e][1],
                                "net_fmol_per_s": ef[e][2] * scale} for e in ef}
            out["occupancy"] = p
            out["carrier_scale_fmol"] = scale
        total, _terms = C.population_total_JdG(law, population, registry, host_state)
        out["guard_total_pJ_per_s"] = total
        for key in ("rows_fmol_per_s", "held_supply_fmol_per_s", "heat_pJ_per_s",
                    "work_pJ_per_s", "stored_standard_pJ_per_s", "charge_a_to_b_fmol_per_s",
                    "current_a_to_b_pA"):
            out[key] = pr[key]
        if with_slopes and law["kind"] != "net_flow":
            sl = C.slopes(law, population, registry, host_state, volumes_pL)
            out["slopes"] = sl
    return _f(out)


def method_agreement(law, population, registry, host_state) -> dict:
    """The diagram's two routes and the edge-cycle consistency at one state (relative)."""
    ls = C.law_state(population, host_state)
    with context():
        rates = D.edge_rates(law, ls, registry)
        a = D.cycle_fluxes(law, rates, "trees")
        b = D.cycle_fluxes(law, rates, "minors")
        p = D.steady_state(law, rates)
        worst_j = Decimal(0)
        for c in law["cycles"]:
            for k in ("j_plus", "j_minus"):
                x, y = a[c["id"]][k], b[c["id"]][k]
                if x != 0:
                    worst_j = max(worst_j, abs(x - y) / abs(x))
        worst_p = max(abs(x - y) for x, y in zip(a["_p"], p, strict=True))
        cons = D.hill_consistency(law, rates, a, p)
        return {"trees_vs_minors_rel": fl(worst_j), "occupancy_trees_vs_solve_abs": fl(worst_p),
                "edge_cycle_consistency_rel": fl(cons)}


def slope_agreement(law, population, registry, host_state, volumes_pL) -> float:
    """max relative difference between the exact (dual) slopes and central differences."""
    with context():
        ex = C.slopes(law, population, registry, host_state, volumes_pL)
        fd = C.slopes_by_differences(law, population, registry, host_state, volumes_pL)
        worst = Decimal(0)
        pairs = [(ex["conductance_pS"], fd["conductance_pS"])]
        for m in ex["dJ_dV"]:
            pairs.append((ex["dJ_dV"][m], fd["dJ_dV"][m]))
        for k in ex["material"]:
            pairs.append((ex["material"][k]["row_self_slope_per_s"],
                          fd["material"][k]["row_self_slope_per_s"]))
        for x, y in pairs:
            if x != 0:
                worst = max(worst, abs(x - y) / abs(x))
        return fl(worst)


def wegscheider(law, registry, law_states) -> dict:
    """Per declared cycle: the affine residual's exact coefficients, its value at every state
    (50 digits), and the honest float64 stand-in relative to its terms' absolute sum (in eps)."""
    out = {}
    for c in law["cycles"]:
        aff = D.affine_residual(law, c, registry)
        rs, rel_exact, rel_logs, rel_ratio = [], [], [], []
        for st in law_states:
            r = D.residual(law, c, registry, st)
            f = D.residual_float(law, c, registry, st)
            rs.append(fl(r))
            rel_exact.append(abs(fl(r)) / (f["terms_abs_sum"] * exact.EPS))
            rel_logs.append(abs(f["r_sum_of_logs"]) / (f["terms_abs_sum"] * exact.EPS))
            rel_ratio.append(abs(f["r_log_of_ratio"]) / (f["terms_abs_sum"] * exact.EPS))
        out[c["id"]] = {
            "r0": fl(aff["r0"]),
            "b": {f"{s}@{e}": int(v) for (s, e), v in sorted(aff["b"].items())},
            "b_psi": float(aff["b_psi"]), "b_psi_exact": str(aff["b_psi"]), "n_q": aff["n_q"],
            "structurally_zero": not aff["b"] and aff["b_psi"] == 0,
            "residual_at_states": rs,
            "residual_over_terms_eps": rel_exact,
            "standin_sum_of_logs_eps": rel_logs, "standin_log_of_ratio_eps": rel_ratio,
        }
    return out


def law_states_of(population, host_states) -> list:
    return [C.law_state(population, st) for st in host_states]


def oneway_plants(law, population, registry, host_state) -> dict:
    """Relative deviations of four planted one-way fluxes from the reference, per cycle."""
    ls = C.law_state(population, host_state)
    out = {}
    with context():
        k = dec(population["capacity_fmol_per_s"]) * dec(population.get("availability", 1.0))
        omega = dec(law["rate_scale_per_s"])
        rates = D.edge_rates(law, ls, registry)
        cyc = D.cycle_fluxes(law, rates, "trees")
        p = cyc["_p"]
        ef = D.edge_fluxes(law, rates, p)
        D_ = D.directional_sums(law, rates)
        total = sum(D_, Decimal(0))
        for c in law["cycles"]:
            q = cyc[c["id"]]
            g = D.mode_dG_RT(c["nu"], registry, ls)
            Jp, Jm = k * q["j_plus"] / omega, k * q["j_minus"] / omega
            row = {}
            # (i) the exponent's sign flipped
            row["exponent_flipped"] = abs(Jp * (-g).exp() - Jm) / Jm if Jm != 0 else None
            # (iii) the cycle's first edge's one-way fluxes in place of the cycle's
            eid, d = c["edges"][0]
            f_, b_, _n = ef[eid]
            ep = (f_ if int(d) == 1 else b_) * k / omega
            row["edge_in_place_of_cycle"] = abs(ep - Jp) / Jp
            # (iv) Σ_κ omitted
            sig = q["sigma_share"] * total
            row["sigma_omitted"] = abs(1 / sig - 1) if sig != 0 else None
            out[c["id"]] = row
        # (ii) the basis's one-way fluxes (D2: {A, B}, C = A − B; D4: {K1, K2}, K3 = K1 − K2)
        basis = {"d2_slip_exchanger": ("A", "B", "C"), "d4_parallel_branches": ("K1", "K2", "K3")}
        if law["id"] in basis:
            a_, b2, c_ = basis[law["id"]]
            Jp = {x: k * cyc[x]["j_plus"] / omega for x in (a_, b2, c_)}
            Jm = {x: k * cyc[x]["j_minus"] / omega for x in (a_, b2, c_)}
            out[a_]["basis_in_place_of_hill"] = abs((Jp[a_] + Jp[c_]) - Jp[a_]) / Jp[a_]
            out[b2]["basis_in_place_of_hill"] = abs((Jp[b2] + Jm[c_]) - Jp[b2]) / Jp[b2]
        return _f(out)


def basis_signs(law, population, registry, host_state) -> dict:
    """The basis modes' net fluxes J_A + J_C and J_B − J_C (D2; K1, K2 for D4) with their own
    ΔG: whether each runs against it (a readout), and the basis-independent total."""
    basis = {"d2_slip_exchanger": ("A", "B", "C"), "d4_parallel_branches": ("K1", "K2", "K3")}
    a_, b2, c_ = basis[law["id"]]
    ls = C.law_state(population, host_state)
    with context():
        fl_ = C.mode_fluxes(law, registry, ls, population["capacity_fmol_per_s"],
                            population.get("availability", 1.0))
        RT = exact.RT_J_per_mol(registry["temperature_K"])
        JA, JB = fl_[a_]["J"] + fl_[c_]["J"], fl_[b2]["J"] - fl_[c_]["J"]
        gA, gB = fl_[a_]["dG_RT"], fl_[b2]["dG_RT"]
        total_hill = sum((fl_[x]["J"] * fl_[x]["dG_RT"] for x in (a_, b2, c_)), Decimal(0))
        total_basis = JA * gA + JB * gB
        return {"mode_A_against_dG": bool(JA * gA > 0), "mode_B_against_dG": bool(JB * gB > 0),
                "total_hill_pJ_per_s": fl(total_hill * RT / 1000),
                "total_basis_pJ_per_s": fl(total_basis * RT / 1000),
                "basis_vs_hill_rel": fl(abs(total_basis - total_hill) / abs(total_hill))
                if total_hill != 0 else 0.0}


def guard_standin(law, population, registry, host_state) -> dict:
    """The honest float64 stand-in of Σ J ΔG for an admitted law: J by expm1 (exact sign) and by
    J⁺ − J⁻; its most positive value relative to Σ (J⁺ + J⁻)|ΔG| in eps."""
    with context():
        ls = C.law_state(population, host_state)
        fl_ = C.mode_fluxes(law, registry, ls, population["capacity_fmol_per_s"],
                            population.get("availability", 1.0))
    tot_expm1, tot_diff, scale = 0.0, 0.0, 0.0
    for m in C.modes(law):
        q = fl_[m["id"]]
        g = fl(q["dG_RT"])
        jp = fl(q["J_plus"])
        jm_ = jp * math.exp(g)
        tot_expm1 += (-jp * math.expm1(g)) * g
        tot_diff += (jp - jm_) * g
        scale += (abs(jp) + abs(jm_)) * abs(g)
    return {"expm1_total": tot_expm1, "difference_total": tot_diff,
            "difference_over_scale_eps": max(tot_diff, 0.0) / (scale * exact.EPS) if scale else 0.0}


# --------------------------------------------------------------------------------------------
# Seam C
# --------------------------------------------------------------------------------------------

def binding_state(system_spec, registry, totals, V, extra_checks=False) -> dict:
    """Speciation from the registered totals, conservation, charge, G*, its gradient, and the
    floors (the inputs' rounding, and a residual |g|/T ≤ 1e-13)."""
    sy = Bd.System(system_spec, registry)
    TL, TB = totals["ligands_fmol"], totals["binders_fmol"]
    with context():
        sp = Bd.solve(sy, TL, TB, V)
        sens = Bd.sensitivities(sy, sp, TL, TB, V)
        out = {"x_mM": sp["x_mM"], "forms_mM": sp["forms_mM"],
               "free_fmol": {L: dec(V) * sp["x_mM"][L] for L in sy.ligands},
               "residual_rel": {L: abs(sp["residual_fmol"][L]) / abs(dec(TL[L]))
                                for L in sy.ligands},
               "conservation_rel": Bd.conservation(sy, sp, TL, TB, V),
               "charge": Bd.charge(sy, sp, TL, TB, V),
               "G_star_pJ": Bd.free_energy(sy, sp, V),
               "own_terms_pJ": Bd.own_terms(sy, TL, TB, V),
               "potentials_J_per_mol": Bd.potentials(sy, sp),
               "floor_input_rounding": {"x": sens["input_rounding"]["x"],
                                        "forms": {f"{B}|{f}": v for (B, f), v in
                                                  sens["input_rounding"]["forms"].items()}},
               "floor_residual_1e-13": {"x": sens["residual_bound"]["x"],
                                        "forms": {f"{B}|{f}": v for (B, f), v in
                                                  sens["residual_bound"]["forms"].items()}}}
        positive = all(dec(TL[L]) > 0 for L in sy.ligands)
        # the speciation part G* − Σ own terms is defined only where every row is positive; a
        # form below its base can make a ligand's total equivalents ≤ 0 (a reading)
        out["speciation_part_pJ"] = (out["G_star_pJ"] - out["own_terms_pJ"]) if positive else None
        out["every_total_positive"] = positive
        if extra_checks:
            gd = Bd.gradient_by_differences(sy, TL, TB, V)
            pot = out["potentials_J_per_mol"]
            out["gradient_vs_differences_rel"] = max(abs(pot[r] - gd[r]) / abs(pot[r])
                                                     for r in pot)
            if len(sy.ligands) <= 2:
                bi = Bd.solve_bisection(sy, TL, TB, V)
                out["newton_vs_bisection_rel"] = max(abs(sp["x_mM"][L] / bi["x_mM"][L] - 1)
                                                     for L in sy.ligands)
        return _f(out), sp, sy


def binding_plants(system_spec, registry, totals, V, designated) -> dict:
    """Each planted variant's largest |δ ln c| over the free ligands and forms, against the
    reference, and the output where it is largest."""
    ref = Bd.solve(Bd.System(system_spec, registry), totals["ligands_fmol"],
                   totals["binders_fmol"], V)
    sy_ref = Bd.System(system_spec, registry)
    out = {}
    B_of = next(B for B in system_spec["binders"]
                if any(f["id"] == designated for f in registry["binders"][B]["forms"]))

    def variant(fn):
        reg = copy.deepcopy(registry)
        forms = reg["binders"][B_of]["forms"]
        k = [f["id"] for f in forms].index(designated)
        fn(forms, k)
        return reg

    def shift_K(by):
        def fn(fs, k):
            fs[k]["mu0_RT"] -= by          # β × e^{by}
        return fn

    def drop(fs, k):
        fs.pop(k)

    def count_plus_one(fs, k):
        first = next(iter(fs[k]["counts"]))
        fs[k]["counts"][first] += 1

    plants = {"K_1pct": variant(shift_K(math.log(1.01))),
              "K_1e-6": variant(shift_K(math.log1p(1e-6))),
              "form_dropped": variant(drop),
              "count_off_by_one": variant(count_plus_one)}
    with context():
        for name, reg in plants.items():
            sy = Bd.System(system_spec, reg)
            sp = Bd.solve(sy, totals["ligands_fmol"], totals["binders_fmol"], V)
            worst, where = Decimal(0), None
            for L in sy_ref.ligands:
                d = abs((sp["x_mM"][L] / ref["x_mM"][L]).ln())
                if d > worst:
                    worst, where = d, L
            for B in sy_ref.binders:
                for fid, c in ref["forms_mM"][B].items():
                    if fid in sp["forms_mM"][B] and c > 0 and sp["forms_mM"][B][fid] > 0:
                        d = abs((sp["forms_mM"][B][fid] / c).ln())
                        if d > worst:
                            worst, where = d, f"{B}|{fid}"
            out[name] = {"max_abs_dln": fl(worst), "where": where}
        # a solution whose ligand conservation is off by 1e-10 relative: δu = H⁻¹ δg
        Ls = sy_ref.ligands
        H = [[ref["hessian_fmol"][L][M] for M in Ls] for L in Ls]
        worst = Decimal(0)
        for j, M in enumerate(Ls):
            dg = [Decimal(0)] * len(Ls)
            dg[j] = Decimal("1e-10") * abs(dec(totals["ligands_fmol"][M]))
            du = exact.solve(H, dg)
            worst = max(worst, max(abs(x) for x in du))
        out["conservation_1e-10"] = {"max_abs_dln": fl(worst), "where": "free ligands"}
        return out


def gradient_plant(system_spec, registry, totals, V) -> dict:
    """The rows' own ideal potentials taken for the free forms' (a planted gradient): the largest
    |μ_own − μ_free| over rows (J/mol)."""
    sy = Bd.System(system_spec, registry)
    TL, TB = totals["ligands_fmol"], totals["binders_fmol"]
    with context():
        sp = Bd.solve(sy, TL, TB, V)
        pot = Bd.potentials(sy, sp)
        RT = exact.RT_J_per_mol(sy.T_K)
        worst, where = Decimal(0), None
        for L in sy.ligands:
            T = dec(TL[L])
            if T > 0:
                own = RT * (sy.mu0_L[L] + (T / (dec(V) * sy.c0)).ln())
                if abs(own - pot[L]) > worst:
                    worst, where = abs(own - pot[L]), L
        for B in sy.binders:
            own = RT * (sy.forms[B][0]["mu0_RT"] + (dec(TB[B]) / (dec(V) * sy.c0)).ln())
            if abs(own - pot[B]) > worst:
                worst, where = abs(own - pot[B]), B
        return {"max_abs_J_per_mol": fl(worst), "where": where}


def nonminimum_plant(system_spec, registry, totals, V, designated) -> dict:
    """G at the speciation a dropped form gives, evaluated with every form: above G* (pJ)."""
    sy = Bd.System(system_spec, registry)
    TL, TB = totals["ligands_fmol"], totals["binders_fmol"]
    reg = copy.deepcopy(registry)
    B_of = next(B for B in system_spec["binders"]
                if any(f["id"] == designated for f in registry["binders"][B]["forms"]))
    reg["binders"][B_of]["forms"] = [f for f in reg["binders"][B_of]["forms"]
                                     if f["id"] != designated]
    with context():
        ref = Bd.solve(sy, TL, TB, V)
        sp2 = Bd.solve(Bd.System(system_spec, reg), TL, TB, V)
        sp2["forms_mM"][B_of][designated] = Decimal(0)
        return {"excess_pJ": fl(Bd.free_energy(sy, sp2, V) - Bd.free_energy(sy, ref, V))}


def p1(node, registry) -> dict:
    sy = Bd.System(node["system"], registry)
    out = Bd.p1_thresholds(sy, node["ligand"], node["totals"]["ligands_fmol"],
                           node["totals"]["binders_fmol"], node["volume_pL"])
    return _f(out)


def mover_verdict(mover, registry) -> dict:
    """§5.2: a mover of a multi-form row is admitted when its law declares its stoichiometry in
    base forms with every ligand written out; charge then balances at the base valences."""
    rows = set(registry["species"]) | set(registry["binders"])
    forms = {f["id"] for b in registry["binders"].values() for f in b["forms"][1:]}
    reasons = []
    for s in dict.fromkeys(s for s, _e, _n in mover["nu"]):
        if s in forms:
            reasons.append(f"moves the form {s}, not a row")
        elif s not in rows:
            reasons.append(f"unknown row {s}")
    multi = {s for s, _e, _n in mover["nu"] if s in registry["binders"]}
    if multi and not mover.get("declares_base_forms"):
        reasons.append(f"moves the multi-form rows {sorted(multi)} without declaring its forms")
    if not reasons:
        z = {s: int(v["valence"]) for s, v in registry["species"].items()}
        z.update({b: int(v["base_valence"]) for b, v in registry["binders"].items()})
        charge = sum(z[s] * int(n) for s, _e, n in mover["nu"])
        if charge != 0:
            reasons.append(f"charge in base forms is {charge}, not 0")
    return {"verdict": "refused" if reasons else "admitted", "reasons": reasons}
