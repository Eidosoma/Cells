"""The registered references of R-chain and R-clear, their bands, plants and zero-power list.

python -m validation.fr7.references.design [--check] [--worlds W1_...,W2_...]

Writes interface/rows.json, plants.json, zero_power.json and clearance.json from
interface/inputs.json (worlds.py). --check regenerates and compares: each row's value, bound and
band to 1e-3 of its band, margins to 1e-3, and statuses, clearance rows and the zero-power rows
exactly (the last bits change between environments). The whole design
takes about 2.5 minutes of one CPU.
"""

import argparse
import json
import math
import sys
import time

import numpy as np

from validation.fr7.references import chain, clearance, worlds

IFACE = worlds.HERE / "interface"
ROWS_FILE = IFACE / "rows.json"
PLANTS_FILE = IFACE / "plants.json"
ZERO_FILE = IFACE / "zero_power.json"
CLEAR_FILE = IFACE / "clearance.json"

EPS = float(np.finfo(float).eps)
UNAFFECTED = 0.05  # a plant that moves no compared row of a quantity by 5% of a band does not
#                    act on it
CLOSED_BOUND = 16.0 * EPS  # relative bound of a closed form's float64 evaluation
MATERIAL_PLANTS = ("nu_off_by_one", "cu_without_1e-15", "maturation_stage_skipped",
                   "removal_on_increment_only", "route_on_precursor_clearance",
                   "factor_from_amount")
CHAIN_PLANT_NAMES = (*MATERIAL_PLANTS, "factor_held_from_step_start",
                     "releasing_compartment_left_out")
TEMPLATE_QUANTITIES = ("n_T_fmol", "D")
# Rows outside the compared core (units, conductance, material): compared only where at least one
# plant has power on them (the lead's rule for V, D231's brief); V has its own, stricter rule
NON_CORE = ("n_T_fmol", "D", "F_T", "Na_fmol", "K_fmol")
NO_CELL = {"cu_without_1e-15": (
    "Its units are about 1e15 times the reference's, so its K conductance shorts the cell to E_K "
    "(a membrane time constant near 1e-17 s); its V and amount rows are not integrated and it is "
    "left out of V's rule. Its power is carried by every unit, conductance and material row, by "
    "margins near 1e15.")}
CALIBRATION_SCHEMES = ("held_mid", "trapezoid", "strang")

UNITS = dict(n_T_fmol="fmol", D="1", F_T="1", n_P_fmol="fmol", N_units="units", PA_m3_s="m^3/s",
             W_fmol="fmol", R_units="units", C_P_fmol="fmol", total_fmol="fmol", V_V="V",
             Na_fmol="fmol", K_fmol="fmol", c_mM="mM", U_s="s", Cl_fmol="fmol", I_pop_A="A",
             template_produced_fmol="fmol", template_cleared_fmol="fmol", supplied_fmol="fmol",
             dV_dlnN_V="V per e-fold")


def band(rule, values, bounds):
    """bound + max(rel max(|x|, floor scale), abs), scale = max |x| over the world's rows."""
    v = np.abs(np.asarray(values, dtype=float))
    scale = float(v.max()) if v.size else 0.0
    return np.asarray(bounds, dtype=float) + np.maximum(
        rule["rel"] * np.maximum(v, rule["floor"] * scale), rule["abs"])


def rule_of(inputs, quantity):
    for name, rule in inputs["band_rules"].items():
        if name != "note" and quantity in rule["quantities"]:
            return rule
    return None


def power_union(plant_margins, compared, n_rows, margin_min):
    """Per compared quantity and row: does at least one plant move it by margin_min bands?"""
    out = {}
    for k in compared:
        hit = np.zeros(n_rows, dtype=bool)
        for pm in plant_margins.values():
            if k in pm:
                hit |= np.asarray(pm[k]) >= margin_min
        out[k] = hit
    return out


def zero_power_kinds(pname, pm, status, compared, margin_min):
    """Per compared quantity a plant was evaluated on: "upstream" (the template, and the factor
    for every plant but factor_from_amount), "unaffected" (the plant moves no compared row by
    UNAFFECTED bands: it does not act there), "rows" (it acts, but some compared rows move by
    under margin_min bands) or "power" (every compared row has power)."""
    out = {}
    for k in compared:
        if k not in pm:
            continue
        if k in TEMPLATE_QUANTITIES or (k == "F_T" and pname != "factor_from_amount"):
            out[k] = "upstream"
            continue
        cm = [pm[k][r] for r in range(len(status[k])) if status[k][r] == "compared"]
        if not cm:
            continue
        if max(cm) < UNAFFECTED:
            out[k] = "unaffected"
        elif min(cm) < margin_min:
            out[k] = "rows"
        else:
            out[k] = "power"
    return out


def margins(plant_values, values, bands):
    return np.abs(np.asarray(plant_values) - np.asarray(values)) / np.asarray(bands)


def _closed(x):
    x = np.asarray(x, dtype=float)
    return CLOSED_BOUND * np.abs(x)


def _arr(records, key, j=None):
    if j is None:
        return np.array([r[key] for r in records], dtype=float)
    return np.array([r[key][j] for r in records], dtype=float)


def _has_template(w):
    return w.template.n0 > 0.0 or bool(np.any(w.template.rates > 0.0))


def applicability(w, plant):
    if plant == "maturation_stage_skipped" and w.m_declared == 0:
        return "no maturation stage to skip (m = 0)"
    if plant in ("factor_held_from_step_start", "factor_from_amount") and not _has_template(w):
        return "no template: the factor is b throughout, so how it is read cannot matter"
    if plant == "releasing_compartment_left_out":
        return ("no R-chain world has a releasing compartment (none is admitted in a U2 world "
                "today); the plant is shown on R-clear's synthetic trajectories")
    return None


def chain_quantities(w, ref, prefix=""):
    """Map a reference or plant result onto the registered quantity names."""
    out = {"n_P_fmol": ref["n_P"], "N_units": ref["N"], "W_fmol": ref["W"],
           "R_units": ref["R"], "C_P_fmol": ref["C_P"], "total_fmol": ref["total"]}
    for j in range(w.m_declared):
        out[f"M{j + 1}_units"] = ref["M"][j] if j < len(ref["M"]) else np.zeros_like(ref["N"])
    return out


def world_design(inputs, name, log=print):
    started = time.perf_counter()
    dt = inputs["step"]["dt_s"]
    margin_min = inputs["power"]["margin"]
    w = chain.World(inputs, name)
    rows = np.array(w.rows, dtype=float)
    q = chain.reference_chain(w, rows, panel_s=chain.PANEL_S / 2.0)
    qc = chain.reference_chain(w, rows, panel_s=chain.PANEL_S)
    ode, _ = chain.simulate(w, rows, ions=False)
    cell12, steps12 = chain.simulate(w, rows, rtol=1e-12)
    cell10, _ = chain.simulate(w, rows, rtol=1e-10)
    log(f"  {name}: reference runs {time.perf_counter() - started:.1f} s")

    values, bounds, classes = {}, {}, {}

    def put(qname, value, bound, cls):
        values[qname] = np.asarray(value, dtype=float)
        bounds[qname] = np.asarray(bound, dtype=float)
        classes[qname] = cls

    # the template: closed forms
    put("n_T_fmol", q["n_T"], _closed(q["n_T"]), "compared")
    put("D", q["D"], _closed(q["D"]), "compared")
    put("F_T", q["F_T"], _closed(q["F_T"]), "compared")
    put("c_mM", q["c"], _closed(q["c"]), "information")
    put("U_s", q["U"], _closed(q["U"]), "information")
    put("template_produced_fmol", q["template_produced"], _closed(q["template_produced"]),
        "information")
    put("template_cleared_fmol", q["template_cleared"],
        CLOSED_BOUND * (w.template.n0 + np.abs(q["template_produced"])), "information")
    # the chain: quadrature, bounded by the coarse panels, the DOP853 chain and the Radau cell
    others = {"coarse": chain_quantities(w, qc),
              "dop853": chain_quantities(w, {k: (_arr(ode, k) if k != "M" else [
                  _arr(ode, "M", j) for j in range(w.m)]) for k in
                  ("n_P", "N", "W", "R", "C_P", "total", "M")}),
              "radau": chain_quantities(w, {k: (_arr(cell12, k) if k != "M" else [
                  _arr(cell12, "M", j) for j in range(w.m)]) for k in
                  ("n_P", "N", "W", "R", "C_P", "total", "M")})}
    for qname, value in chain_quantities(w, q).items():
        diffs = [np.abs(value - o[qname]) for o in others.values()]
        bound = np.maximum.reduce([*diffs, _closed(value)])
        cls = "compared"
        if qname == "C_P_fmol" and w.kP == 0.0:
            cls = "information"  # identically 0 in a finite pool
        put(qname, value, bound, cls)
    put("PA_m3_s", w.P * q["N"] / w.rho, w.P / w.rho * bounds["N_units"]
        + _closed(w.P * q["N"] / w.rho), "compared")
    # the cell: Radau at rtol 1e-12, bounded by its difference from rtol 1e-10
    V12, V10 = _arr(cell12, "V"), _arr(cell10, "V")
    put("V_V", V12, np.abs(V12 - V10) + _closed(V12), "compared")
    for s, sp in enumerate(w.species):
        a12, a10 = _arr(cell12, "amounts", s), _arr(cell10, "amounts", s)
        cls = "compared" if (w.leak[s] > 0.0 or w.rel[s] > 0.0) else "information"
        put(f"{sp}_fmol", a12, np.abs(a12 - a10) + _closed(a12), cls)
    I12, I10 = _arr(cell12, "I_pop"), _arr(cell10, "I_pop")
    put("I_pop_A", I12, np.abs(I12 - I10) + _closed(I12), "information")
    put("supplied_fmol", w.S * rows, _closed(w.S * rows), "information")
    sens = []
    for rec in cell12:
        mM = [x / w.volume for x in rec["amounts"]]
        sens.append(chain.quasi_steady_sensitivity(w, rec["N"], mM))
    put("dV_dlnN_V", sens, np.zeros(rows.size), "information")
    checks = dict(
        U_closed_vs_quadrature=float(np.max(np.abs(q["U"] - _U_quadrature(w, rows)))),
        material_total_spread_rel=float(np.ptp(q["total"]) / abs(q["total"][0])),
        follower_spread_fmol=float(np.ptp(values["Cl_fmol"])),
        radau_steps=steps12)

    # a compared quantity that is identically zero in this world (the template without one) is
    # information: a relative band has nothing to scale with
    for qname, cls in list(classes.items()):
        if cls == "compared" and not np.any(values[qname]):
            classes[qname] = "information"

    # bands and statuses
    bands, status = {}, {}
    for qname, cls in classes.items():
        st = ["information"] * rows.size
        if cls == "compared":
            rule = rule_of(inputs, qname)
            bands[qname] = band(rule, values[qname], bounds[qname])
            st = ["information"] + ["compared"] * (rows.size - 1)  # row 0 is the declared start
        status[qname] = st

    # plants
    plants, plant_margins = {}, {}
    variants = chain.plant_variants(dt)
    compared = [k for k in bands]
    for pname in CHAIN_PLANT_NAMES:
        reason = applicability(w, pname)
        if reason:
            plants[pname] = dict(applicable=False, reason=reason)
            continue
        t0 = time.perf_counter()
        wp = chain.World(inputs, name, variants[pname])
        ions = pname not in NO_CELL
        recs, _ = chain.simulate(wp, rows, ions=ions, rtol=1e-12 if ions else None)
        pv = chain_quantities(w, {k: (_arr(recs, k) if k != "M" else [
            _arr(recs, "M", j) for j in range(wp.m)]) for k in
            ("n_P", "N", "W", "R", "C_P", "total", "M")})
        how = ("the cell with the chain under the plant: Radau at rtol 1e-12" if ions else
               "the chain under the plant: DOP853 at rtol 1e-13. " + NO_CELL[pname])
        if pname == "factor_held_from_step_start":
            st = chain.stepped(w, dt, rows, "held_start")
            pv = chain_quantities(w, st)
            how = ("chain rows: the exact step-by-step emulation at dt (factor held from each "
                   "step's start); V and amounts: the cell with the factor read at t - dt/2 "
                   "(equal to the held factor to O(dt^2) at step ends)")
        pv["PA_m3_s"] = w.P * pv["N_units"] / w.rho
        pv["F_T"] = _arr(recs, "F_T")
        pv["n_T_fmol"], pv["D"] = values["n_T_fmol"], values["D"]
        if ions:
            pv["V_V"] = _arr(recs, "V")
            for s, sp in enumerate(w.species):
                if f"{sp}_fmol" in bands:
                    pv[f"{sp}_fmol"] = _arr(recs, "amounts", s)
        pm = {k: margins(pv[k], values[k], bands[k]) for k in compared if k in pv}
        plants[pname] = dict(applicable=True, how=how,
                             values={k: pv[k] for k in compared if k in pv},
                             margin=pm)
        plant_margins[pname] = pm
        log(f"    {pname}: {time.perf_counter() - t0:.1f} s")

    # V: compared at a row only where every applicable material plant has power on it
    applicable_material = [p for p in MATERIAL_PLANTS if plants[p]["applicable"]
                           and p not in NO_CELL]
    v_ok = np.ones(rows.size, dtype=bool)
    for p in applicable_material:
        v_ok &= plant_margins[p]["V_V"] >= margin_min
    status["V_V"] = ["compared" if (r > 0 and v_ok[r]) else "information"
                     for r in range(rows.size)]
    # every other non-core row: compared only where at least one plant has power on it
    union = power_union(plant_margins, compared, rows.size, margin_min)
    for k in NON_CORE:
        if k in status and k in bands:
            status[k] = ["compared" if (r > 0 and union[k][r]) else "information"
                         for r in range(rows.size)]
    core_gaps = {k: [float(rows[r]) for r in range(rows.size)
                     if status[k][r] == "compared" and not union[k][r]]
                 for k in compared if k not in NON_CORE and k != "V_V"}
    core_gaps = {k: v for k, v in core_gaps.items() if v}

    # zero power: compared rows where an applicable plant moves the row by under `margin` bands
    zero_rows, unaffected = {}, {}
    for pname, pm in plant_margins.items():
        entry, quiet = {}, {}
        for k, kind in zero_power_kinds(pname, pm, status, compared, margin_min).items():
            if kind == "unaffected":
                quiet[k] = float(max(pm[k][r] for r in range(rows.size)
                                     if status[k][r] == "compared"))
            elif kind == "rows":
                entry[k] = [[float(rows[r]), float(pm[k][r])] for r in range(rows.size)
                            if status[k][r] == "compared" and pm[k][r] < margin_min]
        zero_rows[pname], unaffected[pname] = entry, quiet
    upstream = dict(
        quantities=list(TEMPLATE_QUANTITIES) + ["F_T"],
        reason="the template and its factor are upstream of the chain: no chain plant changes "
               "n_T or D, and only factor_from_amount changes the factor's rows",
        plants=[p for p in plant_margins if p != "factor_from_amount"],
        plants_for_n_T_and_D=list(plant_margins))
    power_summary = {}
    for pname, pm in plant_margins.items():
        power_summary[pname] = {k: int(sum(1 for r in range(rows.size)
                                           if status[k][r] == "compared"
                                           and pm[k][r] >= margin_min)) for k in compared
                                if k in pm}

    # clearance of the world's own template (R-clear on the reference's saved D)
    eps = inputs["clearance"]["epsilon"]
    times = [float(t) for t in rows]
    tc = clearance.t_clear(times, values["D"], eps)
    clear = dict(t_clear_s=tc, bracket=clearance.bracket(times, values["D"], eps, tc),
                 t_epsilon_s=_t_epsilon(w, eps),
                 horizon_after_clear_s=None if tc is None else w.horizon - tc,
                 unit_half_lives_after_clear=None if tc is None else
                 (w.horizon - tc) * w.kr / math.log(2.0))
    clear["plants"] = {
        "first_crossing_no_fall_back": clearance.t_clear(times, values["D"], eps,
                                                         rule="first_crossing"),
        "threshold_on_the_factor": clearance.t_clear(times, values["D"], eps, basal=w.b),
        "strict_inequality": clearance.t_clear(times, values["D"], eps, strict=True),
        "end_time_if_not_cleared": clearance.t_clear(times, values["D"], eps,
                                                     end_if_not_cleared=True),
    }
    clear["plants_with_power"] = sorted(p for p, t in clear["plants"].items() if t != tc)

    # calibration: correct second-order treatments, emulated exactly, against the bands
    calibration = {}
    for scheme in CALIBRATION_SCHEMES:
        st = chain_quantities(w, chain.stepped(w, dt, rows, scheme))
        st["PA_m3_s"] = w.P * st["N_units"] / w.rho
        calibration[scheme] = {k: float(np.max(margins(st[k], values[k], bands[k])[1:]))
                               for k in st if k in bands}
    # the held factor's two models: exact steps against the shift model's chain rows
    lag = {}
    if plants["factor_held_from_step_start"].get("applicable"):
        wl = chain.World(inputs, name, variants["factor_held_from_step_start"])
        shift, _ = chain.simulate(wl, rows, ions=False)
        sv = chain_quantities(w, {k: (_arr(shift, k) if k != "M" else [
            _arr(shift, "M", j) for j in range(w.m)]) for k in
            ("n_P", "N", "W", "R", "C_P", "total", "M")})
        exact = plants["factor_held_from_step_start"]["values"]
        for k in sv:
            if k not in bands:
                continue
            dev = np.abs(exact[k] - values[k])
            sel = dev > bands[k]
            lag[k] = (float(np.max(np.abs(sv[k] - exact[k])[sel] / dev[sel])) if sel.any()
                      else None)
    log(f"  {name}: done in {time.perf_counter() - started:.1f} s")

    row_doc = dict(rows_s=times, quantities={}, clearance=clear, checks=checks)
    for k in values:
        entry = dict(cls=classes[k], unit=UNITS.get(k, "units" if k.endswith("_units") else ""),
                     status=status[k], value=values[k].tolist(), bound=bounds[k].tolist())
        if k in bands:
            entry["band"] = bands[k].tolist()
        row_doc["quantities"][k] = entry
    plant_doc = dict(plants={}, calibration_max_band_fraction=calibration,
                     held_factor_shift_model_vs_exact=lag)
    for pname, p in plants.items():
        if not p["applicable"]:
            plant_doc["plants"][pname] = p
            continue
        plant_doc["plants"][pname] = dict(
            applicable=True, how=p["how"],
            values={k: np.asarray(v, dtype=float).tolist() for k, v in p["values"].items()},
            margin={k: np.asarray(v, dtype=float).tolist() for k, v in p["margin"].items()})
    zero_doc = dict(inapplicable={p: plants[p]["reason"] for p in plants
                                  if not plants[p]["applicable"]},
                    not_evaluated={p: dict(quantities=[k for k in compared
                                                       if k not in plant_margins[p]],
                                           reason=NO_CELL[p])
                                   for p in plant_margins if p in NO_CELL},
                    upstream=upstream, unaffected=unaffected, rows_without_power=zero_rows,
                    core_rows_without_any_plant=core_gaps,
                    compared_rows_with_power=power_summary)
    return row_doc, plant_doc, zero_doc


def _U_quadrature(w, rows):
    """U at the rows by Gauss-Legendre panels of 1 s on the closed-form template (a check of the
    closed-form exposure)."""
    edges = chain.grid(w, rows, panel_s=1.0)
    tau, wt = chain._panels(edges)
    h = chain.hill_activation(w.template.amount(tau) / w.volume, w.K, w.n)
    cum = np.concatenate([[0.0], np.cumsum(np.sum(wt * h, axis=1))])
    return cum[np.searchsorted(edges, rows)]


def _t_epsilon(w, eps):
    """The continuous time after the template's peak at which D falls to epsilon (information)."""
    c_eps = clearance.trace_level(eps, w.K, w.n)
    n_eps = c_eps * w.volume
    peak_t = max([0.0, *w.template.breakpoints()], key=lambda t: float(w.template.amount(t)))
    if float(w.template.amount(peak_t)) <= n_eps:
        return None
    hi = w.horizon
    if float(w.template.amount(hi)) > n_eps:
        return None
    from scipy.optimize import brentq
    return float(brentq(lambda t: float(w.template.amount(t)) - n_eps, peak_t, hi,
                        xtol=1e-12, rtol=4 * EPS))


def clearance_design(inputs, row_docs, log=print):
    cl = inputs["clearance"]
    w5 = inputs["worlds"]["W5_supplied_dose_m3_t60"]
    eps_doc = clearance.epsilon_computation(
        worlds.BASAL, cl["resolution_relative"],
        supplied=(w5["units"]["assembly_per_s"], w5["precursor"]["clearance_per_s"]))
    if eps_doc["epsilon"] != cl["epsilon"]:
        raise RuntimeError("the registered epsilon is not the computation's")
    eps = cl["epsilon"]
    K, n = worlds.K_MM, worlds.HILL_N
    V = inputs["cell"]["volume_pL"]
    c_eps = clearance.trace_level(eps, K, n)
    avogadro = inputs["constants"]["avogadro_per_mol"]
    lo, hi = cl["operating_range_mM"]
    mean_field_floor = 100.0 / (avogadro * chain.FMOL) / V  # 10^2 molecules in V, in mM
    sens = []
    for name, doc in row_docs.items():
        st = doc["quantities"]["V_V"]["status"]
        s = doc["quantities"]["dV_dlnN_V"]["value"]
        sens += [(abs(s[r]), name, doc["rows_s"][r]) for r in range(len(s)) if st[r] == "compared"]
    worst = max(sens) if sens else (math.nan, None, None)
    out = dict(
        epsilon=eps_doc,
        computation=[
            "held precursor: N* = c_u k_a F n_P/k_r, so D = epsilon moves N* by (1 - b) epsilon/b",
            "supplied precursor: N* = c_u S_P k_a F/(k_r (k_P + k_a F)), a smaller move",
            "epsilon_max = resolution b/(1 - b); epsilon is epsilon_max rounded down to one "
            "significant digit",
            "the conductance P N/rho_ref is linear in N, so it moves by the same relative amount"],
        trace_level=dict(c_mM=c_eps, n_fmol=c_eps * V,
                         molecules=c_eps * V * avogadro * chain.FMOL,
                         note="the template concentration at which D = epsilon, K (epsilon/"
                              "(1 - epsilon))^(1/n), in the 2 pL cell"),
        operating_range=dict(
            declared_mM=[lo, hi], includes_trace_level=lo <= c_eps <= hi,
            amendment=cl.get("operating_range_amendment"),
            mean_field_floor_mM=mean_field_floor,
            factor_above_basal_at_floor=float((1.0 - worlds.BASAL) * clearance.hill_drive(
                mean_field_floor, K, n)),
            note="the coupling's declared range on the template, which includes the trace level "
                 "and reaches 0, where F_T is b exactly. D150's mean-field floor of about 10^2 "
                 "molecules per cell is a stated limit, not a refusal: below it F_T is b to "
                 "within factor_above_basal_at_floor"),
        voltage_equivalent=dict(
            max_abs_dV_dlnN_V=worst[0], world=worst[1], row_s=worst[2],
            resolution_in_V=worst[0] * cl["resolution_relative"],
            note="information: the quasi-steady potential's sensitivity to ln N at a compared "
                 "V row's composition, times the resolution; the response that clause 2 "
                 "resolves is the units and the conductance"),
        worlds={name: doc["clearance"] for name, doc in row_docs.items()},
    )
    # the synthetic trajectories
    common = dict(inputs["clearance_cases"])
    common["epsilon"] = eps
    times = common["rows_s"]
    cases = {}
    for cname, case in inputs["clearance_cases"]["cases"].items():
        tc, D, cs = clearance.evaluate_case(case, common, times)
        entry = dict(t_clear_s=tc, bracket=clearance.bracket(times, D, eps, tc),
                     D=D.tolist(), c_star_mM=cs.tolist(), plants={})
        for plant in clearance.PLANTS:
            tp, _, _ = clearance.evaluate_case(case, common, times, plant)
            entry["plants"][plant] = dict(t_clear_s=tp, power=tp != tc)
        cases[cname] = entry
    for cname, case in inputs["clearance_cases"]["definitional"].items():
        tc = clearance.t_clear(case["rows_s"], case["D"], eps)
        entry = dict(t_clear_s=tc, plants={})
        for plant, spec in clearance.PLANTS.items():
            kw = dict(spec.get("t_clear", {}))
            if "c_star" in spec:
                continue
            if kw.get("basal") is True:
                kw["basal"] = common["basal"]
            tp = clearance.t_clear(case["rows_s"], case["D"], eps, **kw)
            entry["plants"][plant] = dict(t_clear_s=tp, power=tp != tc)
        cases[cname] = entry
    out["synthetic_cases"] = cases
    out["synthetic_power"] = {
        plant: sorted(c for c, e in cases.items() if e["plants"].get(plant, {}).get("power"))
        for plant in clearance.PLANTS}
    return out


def dump(obj):
    """Top-level keys on their own lines, each value compact."""
    if not isinstance(obj, dict):
        return json.dumps(obj) + "\n"
    parts = [f" {json.dumps(k)}: {json.dumps(v, separators=(',', ':'))}" for k, v in obj.items()]
    return "{\n" + ",\n".join(parts) + "\n}\n"


def build(inputs, names=None, log=print):
    names = names or list(inputs["worlds"])
    rows, plants, zero = {}, {}, {}
    head = dict(kind=None, registered=inputs["registered"],
                inputs_sha_note="the inputs are interface/inputs.json, regenerated by worlds.py",
                dt_s=inputs["step"]["dt_s"], power_margin=inputs["power"]["margin"])
    for name in names:
        r, p, z = world_design(inputs, name, log=log)
        rows[name], plants[name], zero[name] = r, p, z
    clear = clearance_design(inputs, rows, log=log)
    return (dict(head, kind="cells.fr7_reference_rows@1", worlds=rows),
            dict(head, kind="cells.fr7_reference_plants@1", worlds=plants),
            dict(head, kind="cells.fr7_reference_zero_power@1", worlds=zero,
                 clearance_cases={c: sorted(p for p, e in v["plants"].items() if not e["power"])
                                  for c, v in clear["synthetic_cases"].items()}),
            dict(head, kind="cells.fr7_reference_clearance@1", **clear))


LOOSE = ("margin", "unaffected", "calibration", "held_factor_shift", "rows_without_power")


def _loose(path):
    """Ratios to a band, which carry noise when the deviation is at rounding level."""
    return any(f"/{k}" in path for k in LOOSE)


def _close(a, b, path, problems, rtol=1e-6, band=None):
    """Regeneration within noise. A row's value, bound and band agree to 1e-3 of its band, or for
    information to 1e-6 of the values' scale (bounds are differences of nearly equal numbers, so
    they are compared on that scale); ratios to a band (margins) to 1e-4 absolute plus 1e-3
    relative, as the band itself; other arrays to rtol of the array's scale; text, statuses and
    clearance rows exactly. Importing the engine package (as tests/conftest.py does) changes the
    last bits of these computations, which is why nothing is compared bit for bit."""
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            problems.append(f"{path}: keys differ")
            return
        if "value" in a and "bound" in a and isinstance(a["value"], list):
            # a row quantity: compared on its band's scale, or on its values' for information
            if "band" in a:
                tol = 1e-3 * np.maximum(np.abs(np.array(a["band"], dtype=float)),
                                        np.abs(np.array(b["band"], dtype=float)))
            else:
                tol = 1e-6 * max(float(np.max(np.abs(np.array(a["value"], dtype=float)))),
                                 float(np.max(np.abs(np.array(b["value"], dtype=float)))))
            for k in ("value", "bound", "band"):
                if k not in a:
                    continue
                x, y = np.array(a[k], dtype=float), np.array(b[k], dtype=float)
                if x.shape != y.shape or np.any(np.abs(x - y) > tol):
                    problems.append(f"{path}/{k}: beyond tolerance")
            for k in a:
                if k not in ("value", "bound", "band"):
                    _close(a[k], b[k], f"{path}/{k}", problems, rtol)
            return
        for k in a:
            if k == "checks":
                continue  # diagnostics at rounding level, not registered values
            _close(a[k], b[k], f"{path}/{k}", problems, rtol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            problems.append(f"{path}: lengths differ")
            return
        if a and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in a + b):
            x, y = np.array(a, dtype=float), np.array(b, dtype=float)
            if _loose(path):
                tol = 1e-4 + 1e-3 * np.abs(y)
            else:
                tol = rtol * np.maximum(np.abs(y), 1e-6 * float(np.max(np.abs(y))))
            if np.any(np.abs(x - y) > tol):
                problems.append(f"{path}: beyond tolerance")
            return
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _close(x, y, f"{path}[{i}]", problems, rtol)
    elif isinstance(a, bool) or isinstance(b, bool) or a is None or b is None \
            or isinstance(a, str) or isinstance(b, str):
        if a != b:
            problems.append(f"{path}: {a!r} != {b!r}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        tol = (1e-4 + 1e-3 * abs(b)) if _loose(path) else rtol * max(abs(a), abs(b))
        if abs(a - b) > tol:
            problems.append(f"{path}: {a!r} != {b!r}")
    elif a != b:
        problems.append(f"{path}: {a!r} != {b!r}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--worlds", default="")
    args = ap.parse_args(argv)
    inputs = json.loads(worlds.INPUTS.read_text())
    if worlds.INPUTS.read_text() != worlds.text():
        print("inputs.json differs from worlds.build(): run worlds.py first")
        return 1
    names = [n for n in args.worlds.split(",") if n] or None
    started = time.perf_counter()
    docs = build(inputs, names)
    files = (ROWS_FILE, PLANTS_FILE, ZERO_FILE, CLEAR_FILE)
    if args.check:
        problems = []
        for path, doc in zip(files, docs, strict=True):
            stored = json.loads(path.read_text())
            fresh = json.loads(dump(doc))
            if names:
                stored = dict(stored, worlds={n: stored["worlds"][n] for n in names}) \
                    if "worlds" in stored and isinstance(stored["worlds"], dict) else stored
            _close(fresh, stored, path.name, problems)
        print(f"check: {len(problems)} differences ({time.perf_counter() - started:.0f} s)")
        for p in problems[:40]:
            print("  ", p)
        return 1 if problems else 0
    for path, doc in zip(files, docs, strict=True):
        path.write_text(dump(doc))
        print(f"wrote {path} ({path.stat().st_size} bytes)")
    print(f"design: {time.perf_counter() - started:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
