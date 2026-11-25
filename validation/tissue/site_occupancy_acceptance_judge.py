"""fr3-site-occupancy-v1's judge: it reads records and never runs (FR-3, D216).

The protocol is validation/tissue/site_occupancy_acceptance_protocol.json. The judge reads the
generator's records (validation/tissue/site_occupancy_acceptance_qualification: one results.json
per unit), merges the units (each part in exactly one, all from one source: MG0c's form), derives
the metrics below under the protocol's `judge.derivation`, and evaluates its machine criteria
(`judge.criteria`) with MG0c's evaluator (validation/morphogenesis/mg0a_gradient.evaluate: a
missing metric fails its criterion) into OUT_DIR/verdict.json.

**The arithmetic is FR-4's and FR-5's where it applies,** imported read-only from validation/
tissue/compartment_ph_judge.py (that judge serves registered protocols. On 18 November 2026, at
9a67ce89, it gained harness 1.1's entry checks only, incomplete() and harnessed() called by its
main(); an AST diff shows its arithmetic unchanged, and the v1 verdicts are read from the frozen
judged snapshots): the
classes rule for orders, admission, the merge and its refusals, and compare. Records align on
integer milliseconds (record_ms), never by float equality.

The FR-3 derivations, fixed before any run (the budgets declared first, confirmed by the lead):
* **B_state** = F_STATE x S_world, S_world the references' declared accessible sites summed over
  the world's populations. Every amount (amount_NODE, B_POP, R_POP, internalised_POP) against a
  reference series is judged at each shared record by |engine - reference| / (B_state + 10 x the
  reference's floor of that quantity at that record); the largest over records and quantities.
* **B_energy** = F_ENERGY x the largest |reference| of the heat (or the work) over the world's
  run, plus 10 x its floor: the same form on heat_pJ and work_pJ. A zero budget with a zero
  difference is 0 (a passive world books no work); a nonzero difference against it is None.
* **R-closed:** the Riccati form wherever the references give it, at every record, in B_state +
  10 x R-ode's floor of the same quantity. **R-eq** at the last record (Q2), in B_state; the
  depletion quadratic's r- in B_state; the heat to equilibrium in F_ENERGY x |G(start) - G(eq)|.
* **Orders** (q1_fast's ladder): each rung's error against R-ode (the max norm over the shared
  records), its floor the reference's largest floor plus N eps max|q| (N the rung's steps); both
  successive pairs classed by FR-4's rule in the declared band.
* **The closure** (the guard of record, §3.4): |energy residual| / (CLOSURE_ROUNDING x eps x
  steps x the energy magnitude) at every record (0 where the residual is 0; None where the
  allowance is 0 and the residual is not). **The heat:** every heat field at least -a and its
  increments at least -a, a that record's closure allowance, as a violation ratio.
* **Ledgers:** the engine's ratios to its own bounds (every ledger but the energy's, whose guard
  is the closure). **The system total:** sum of the free ligand at every cell and finite node and
  every B, against its first record, over the ligand's declared floor + N eps max |total| (FR-4's
  allowance from the records).
* **Q4:** |B(alpha, t) / B(1, t) - alpha| over M_Q4 at every shared record t > 0; the (K) and (A)
  controls' departures the same way, over M_Q4.
* **Controls:** a control run's ratio against its arm's reference in the arm's own tolerance (the
  state form, or the work's energy form); caught at 10 or more.
* **The background guard:** the changes from t = 0 of every amount in the two background worlds
  against each other, over B_state.
* **Plants:** exactly the planted row flagged: every prefix row within the closure, the ledgers
  and the heat's sign; the planted row's checks (a ledger's ratio, the closure's, the heat's
  sign) flagged, the plant's passing ledgers within their bounds there; the margin the smallest
  ratio of its ratio checks. The engine's verdict on resuming: judged for the material plants
  (refused naming the ledger), reported for the energy plants (FR-18).
* **Undefined values are None, never NaN;** a None fails its criterion.

Usage:
  python -m validation.tissue.site_occupancy_acceptance_judge dev PROTOCOL OUT_DIR RESULTS [...]
  python -m validation.tissue.site_occupancy_acceptance_judge judged PROTOCOL OUT_DIR RESULTS [...]
  python -m validation.tissue.site_occupancy_acceptance_judge compare RESULTS_A RESULTS_B OUT_JSON
"""

import json
import math
import sys
from pathlib import Path

from validation import id_table
from validation.morphogenesis.mg0a_gradient import evaluate
from validation.tissue import compartment_ph_judge as base
from validation.tissue import judge_harness as harness

# The code-blind references' registered inputs (site_occupancy_acceptance_fixtures.INPUTS), read
# directly: the judge reads records and registered files only.
INPUTS = (Path(__file__).resolve().parents[2] / "validation" / "fr3" / "references"
          / "reference_inputs.json")

EPS = base.EPS
AMOUNT_PREFIXES = ("amount_", "B_", "R_", "internalised_")
ENERGY_SERIES = ("heat_pJ", "work_pJ")


def flag(value):
    return None if value is None else int(bool(value))


def max_or_none(values):
    return base.max_or_none(list(values))


def min_or_none(values):
    values = list(values)
    return None if not values or any(v is None for v in values) else min(values)


def completed(part):
    return isinstance(part, dict) and part.get("completed") is True


def by_ms(part, name):
    """{record_ms: value} of a series, or None."""
    if not isinstance(part, dict) or name not in (part.get("series") or {}):
        return None
    return dict(zip(part["record_ms"], part["series"][name], strict=True))


def s_world(reference):
    return math.fsum(reference["sites_fmol"].values())


def amounts_of(reference):
    return [k for k in reference["series"] if k.startswith(AMOUNT_PREFIXES)]


def tolerance_ratio(part, reference, name, budget):
    """max over shared records of |engine - reference| / (budget + 10 x the reference's floor),
    with `budget` a number; None when either series is missing or no record is shared."""
    if not completed(part) or not reference:
        return None
    eng, ref = by_ms(part, name), by_ms(reference, name)
    floor = by_ms(reference, "floor_" + name) or {}
    if eng is None or ref is None:
        return None
    shared = sorted(set(eng) & set(ref))
    if not shared:
        return None
    worst = 0.0
    for t in shared:
        difference = abs(eng[t] - ref[t])
        allowed = budget + 10.0 * floor.get(t, 0.0)
        if difference == 0.0:
            continue
        if allowed <= 0.0:
            return None
        worst = max(worst, difference / allowed)
    return worst


def state_ratio(part, reference, f_state):
    """The largest amount ratio of a run against its reference, in B_state."""
    if not reference:
        return None
    budget = f_state * s_world(reference)
    return max_or_none(tolerance_ratio(part, reference, name, budget)
                       for name in amounts_of(reference))


def energy_ratio(part, reference, name, f_energy):
    """heat_pJ or work_pJ against the reference, in F_ENERGY x its largest |value|."""
    if not reference or name not in reference["series"]:
        return None
    scale = max((abs(v) for v in reference["series"][name]), default=0.0)
    return tolerance_ratio(part, reference, name, f_energy * scale)


def against_series(part, series, floors, budget):
    """A run against a given closed-form series {name: {ms: value}} in budget + 10 x floors."""
    if not completed(part) or not series:
        return None
    out = []
    for name, values in series.items():
        eng = by_ms(part, name)
        if eng is None:
            return None
        floor = floors.get(name) or {}
        worst = 0.0
        shared = sorted(set(eng) & set(values))
        if not shared:
            return None
        for t in shared:
            difference = abs(eng[t] - values[t])
            allowed = budget + 10.0 * floor.get(t, 0.0)
            if difference:
                if allowed <= 0:
                    return None
                worst = max(worst, difference / allowed)
        out.append(worst)
    return max_or_none(out)


def riccati_ratio(part, reference, f_state):
    r = (reference or {}).get("riccati")
    if not r:
        return None
    series = {k: dict(zip(r["record_ms"], v, strict=True)) for k, v in r["series"].items()}
    floors = {k: by_ms(reference, "floor_" + k) or {} for k in series}
    return against_series(part, series, floors, f_state * s_world(reference))


def last(part, name):
    if not completed(part) or name not in part["series"]:
        return None
    return part["series"][name][-1]


def equilibrium_ratio(part, reference, f_state):
    """Q2: the last record's B of each population and free ligand at the facing node against
    R-eq, in B_state."""
    e = (reference or {}).get("equilibrium")
    if not e or not completed(part):
        return None
    budget = f_state * s_world(reference)
    out = []
    for pid, b in e["B_fmol"].items():
        value = last(part, f"B_{pid}")
        out.append(None if value is None else abs(value - b) / budget)
    for node in sorted(set(reference["facing"].values())):
        value = last(part, f"amount_{node}")
        n = e["c_mM"] * reference["volumes_pL"][node]
        out.append(None if value is None else abs(value - n) / budget)
    return max_or_none(out)


def quadratic_ratio(part, reference, f_state):
    r = (reference or {}).get("riccati")
    if not r or not completed(part):
        return None
    value = last(part, f"B_{r['population']}")
    return None if value is None else abs(value - r["B_eq_fmol"]) / (f_state * s_world(reference))


def heat_to_equilibrium_ratio(part, reference, f_energy):
    e = (reference or {}).get("equilibrium")
    value = last(part, "heat_pJ")
    if not e or value is None or not e["heat_to_equilibrium_pJ"]:
        return None
    target = e["heat_to_equilibrium_pJ"]
    return abs(value - target) / (f_energy * abs(target))


def steps_at(part, t_ms):
    return int(round(t_ms * 1e-3 / part["dt_s"]))


def closure(part, rounding):
    """The largest |energy residual| / (rounding x eps x steps x energy magnitude)."""
    if not completed(part):
        return None
    s = part["series"]
    worst = 0.0
    for t, r, m in zip(part["record_ms"], s["energy_residual_pJ"], s["energy_magnitude_pJ"],
                       strict=True):
        if r == 0.0:
            continue
        allowance = rounding * EPS * max(1, steps_at(part, t)) * m
        if allowance <= 0.0:
            return None
        worst = max(worst, abs(r) / allowance)
    return worst


def heat_violation(part, rounding):
    """The largest of -h / a and -(h_{j+1} - h_j) / a over every heat field, a that record's
    closure allowance: at most 1 when every heat is non-negative and non-decreasing to rounding."""
    if not completed(part):
        return None
    s = part["series"]
    names = [k for k in s if k.startswith("heat_") and k != "heat_pJ"]
    worst = 0.0
    for name in names:
        h = s[name]
        for j, t in enumerate(part["record_ms"]):
            allowance = rounding * EPS * max(1, steps_at(part, t)) * s["energy_magnitude_pJ"][j]
            fall = -h[j] if j == 0 else max(-h[j], h[j - 1] - h[j])
            if fall <= 0.0:
                continue
            if allowance <= 0.0:
                return None
            worst = max(worst, fall / allowance)
    return worst


def ledger_max(part, ledgers):
    if not completed(part):
        return None
    out = []
    for name in ledgers:
        values = part["series"].get(f"ratio_{name}")
        if values is None:
            return None
        out.append(max(values))
    return max_or_none(out)


def system_total(part):
    """|total(t) - total(0)| over the ligand's floor + N eps max |total| (FR-4's allowance), the
    total the free ligand at every cell and finite node plus every B."""
    if not completed(part):
        return None
    s = part["series"]
    names = [f"amount_{n}" for n in (*part["cells"], *part["finite_nodes"])]
    names += [f"B_{p}" for p in part["populations"]]
    if any(n not in s for n in names):
        return None
    totals = [math.fsum(s[n][j] for n in names) for j in range(len(part["record_ms"]))]
    scale = max(abs(v) for v in totals)
    worst = 0.0
    for j, t in enumerate(part["record_ms"]):
        allowance = part["ligand_floor_fmol"] + max(1, steps_at(part, t)) * EPS * scale
        worst = max(worst, abs(totals[j] - totals[0]) / allowance)
    return worst


def ids_within(part, declared):
    if not completed(part):
        return None
    return int(set(part.get("ids") or []) <= set(declared))


def engine_records(parts, d):
    """{name: engine record} of every engine run: the world and ladder parts, and each control
    run (as PART/VARIANT)."""
    out = {}
    for name in d["engine_parts"]:
        out[name] = parts.get(name)
    for name in d["control_parts"]:
        runs = (parts.get(name) or {}).get("runs") or {}
        if not runs:
            out[name] = None
        for variant, record in runs.items():
            out[f"{name}/{variant}"] = record
    return out


def classes_of(errors, floors, band):
    pairs = [dict(difference=e, floor=f, above=None if e is None or f is None
                  else bool(e > 0 and e >= f)) for e, f in zip(errors, floors, strict=True)]
    return [base.classify(a, b, band) for a, b in zip(pairs, pairs[1:], strict=False)]


def ladder_errors(parts, references, rungs, name):
    """Each rung's max-norm error against the reference and its floor (the reference's largest
    floor + N eps max|q|)."""
    errors, floors = [], []
    for part_name in rungs:
        part = parts.get(part_name)
        eng, ref = by_ms(part, name), by_ms(references, name)
        floor = by_ms(references, "floor_" + name) or {}
        if not completed(part) or eng is None or ref is None:
            errors.append(None)
            floors.append(None)
            continue
        shared = sorted(set(eng) & set(ref))
        errors.append(max(abs(eng[t] - ref[t]) for t in shared) if shared else None)
        floors.append(max(floor.values(), default=0.0)
                      + part["steps"] * EPS * max(abs(eng[t]) for t in shared))
    return errors, floors


def orders(parts, reference, d):
    out = {}
    for name in d["order_observables"] + d["order_reported"]:
        errors, floors = ladder_errors(parts, reference, d["ladder_parts"], name)
        band = d["band"] if name in d["order_observables"] else d["band_reported"]
        classes = classes_of(errors, floors, band)
        out[name] = dict(errors=errors, floors=floors, classes=classes,
                         orders=[c["order"] for c in classes],
                         passes=int(bool(classes) and all(c["passes"] for c in classes)))
    return out


def ratio_departure(numerator, denominator, alpha):
    """max over shared records t > 0 of |B_num(t) / B_den(t) - alpha|, None when undefined."""
    if numerator is None or denominator is None:
        return None
    shared = sorted(t for t in set(numerator) & set(denominator) if t > 0)
    if not shared or any(denominator[t] <= 0 for t in shared):
        return None
    return max(abs(numerator[t] / denominator[t] - alpha) for t in shared)


def q4(parts, d):
    m = d["Q4"]["margin"]
    out = dict(ratio={}, K={}, A={})
    for regime in d["Q4"]["regimes"]:
        one = by_ms(parts.get(f"q4_alpha_1_{regime}"), "B_r0")
        for alpha, world in d["Q4"]["worlds"][regime].items():
            a = float(alpha)
            key = f"{regime}_{alpha}".replace(".", "p")  # No dot: a metric path's separator.
            value = ratio_departure(by_ms(parts.get(world), "B_r0"), one, a)
            out["ratio"][key] = None if value is None else value / m
            for form, part in (("K", "Q4_kinetic"), ("A", "Q4_affinity")):
                run = ((parts.get(part) or {}).get("runs") or {}).get(f"{regime}_{alpha}")
                value = ratio_departure(by_ms(run, "B_r0"), one, a)
                out[form][key] = None if value is None else value / m
    out["ratio_max"] = max_or_none(out["ratio"].values())
    out["K_min"] = min_or_none(out["K"].values())
    out["A_high_min"] = min_or_none(v for k, v in out["A"].items() if k.startswith("high"))
    out["A_low_reported"] = {k: v for k, v in out["A"].items() if k.startswith("low")}
    return out


def controls(parts, refs, d):
    out = {}
    for name, spec in d["controls"].items():
        runs = (parts.get(name) or {}).get("runs") or {}
        found = {}
        for variant, quantity in spec.items():
            run = runs.get(variant)
            arm = (run or {}).get("arm")
            ref = refs.get(arm)
            if quantity == "state":
                found[variant] = state_ratio(run, ref, d["F_state"])
            else:
                found[variant] = energy_ratio(run, ref, quantity, d["F_energy"])
        out[name] = dict(runs=found, min=min_or_none(found.values()))
    return out


def background(parts, d):
    a, b = (parts.get(w) for w in d["background"]["pair"])
    reference = d["background"].get("S_world_fmol")
    if not completed(a) or not completed(b) or not reference:
        return dict(ratio=None, each={}, absolute={})
    budget = d["F_state"] * reference
    each, absolute = {}, {}
    for name in a["series"]:
        if not name.startswith(AMOUNT_PREFIXES) or name not in b["series"]:
            continue
        x, y = by_ms(a, name), by_ms(b, name)
        shared = sorted(set(x) & set(y))
        if not shared:
            each[name] = None
            continue
        t0 = shared[0]
        each[name] = max(abs((x[t] - x[t0]) - (y[t] - y[t0])) for t in shared) / budget
        absolute[name] = max(abs(x[t] - y[t]) for t in shared)
    ratio = max_or_none(each.values())
    return dict(ratio=ratio, margin=None if not ratio else 1.0 / ratio, each=each,
                absolute_fmol=absolute)


def plant_verdict(bundle, d):
    """Exactly the planted row flagged (module docstring); None without the bundle."""
    if not bundle or "planted" not in bundle:
        return dict(exact=None, margin=None, engine_refused=None, engine_names=None)
    rounding, ledgers = d["closure_rounding"], d["ledgers"]
    prefix = dict(bundle["prefix"], completed=True)
    worst = [closure(prefix, rounding), heat_violation(prefix, rounding),
             ledger_max(prefix, ledgers)]
    clean = all(v is not None and v <= 1.0 for v in worst)
    row = bundle["planted"]["series"]
    t = bundle["planted"]["record_ms"]
    one = dict(prefix, completed=True, record_ms=[t],
               series={k: [v] for k, v in row.items()})
    ratios, flagged = [], True
    for check in bundle["plant"]["checks"]:
        if check == "closure":
            value = closure(one, rounding)
        elif check == "dissipation":
            heats = [v for k, v in row.items() if k.startswith("heat_") and k != "heat_pJ"]
            flagged &= any(h < 0 for h in heats)
            continue
        else:
            value = row.get(f"ratio_{check.split(':', 1)[1]}")
        if value is None:
            return dict(exact=None, margin=None, engine_refused=None, engine_names=None)
        ratios.append(value)
        flagged &= value > 1.0
    passing = all(row.get(f"ratio_{name}", math.inf) <= 1.0 for name in bundle["plant"]["passing"])
    engine = bundle.get("engine") or {}
    names = [c.split(":", 1)[1] for c in bundle["plant"]["checks"] if c.startswith("ledger:")]
    named = (bool(engine.get("refused")) and bool(names)
             and all(("accounting failed: " + n) in (engine.get("message") or "")
                     for n in names))
    return dict(exact=int(clean and flagged and passing), margin=min_or_none(ratios),
                prefix_clean=int(clean), flagged=int(flagged), passing=int(passing),
                engine_refused=flag(engine.get("refused")), engine_names=int(named),
                engine_message=engine.get("message"))


def refusal_class(rows, expected):
    if not rows:
        return None
    if expected is None:  # The run-time refusal: refused at run time, not at the definition.
        refused = all(r.get("refused") and r.get("admitted") for r in rows["refused"])
    else:
        refused = all(r["refused"] and r["check"] == expected for r in rows["refused"])
    admitted = all(r["admitted"] and (r["ran"] is True or not r["needs_run"])
                   for r in rows["admitted"])
    return int(refused and admitted)


def q6(parts, d):
    out = {}
    restart = parts.get("Q6_restart") or {}
    restarts = restart.get("restarts") or {}
    out["restart"] = (int(len(restarts) == d["Q6"]["restarts"]
                          and all(r["equal"] for r in restarts.values()))
                      if completed(restart) else None)
    planted = restart.get("planted")
    out["K4_moved_switch_differs"] = (flag(not planted["equal"])
                                      if completed(restart) and planted else None)
    batch = (parts.get("Q6_batch") or {}).get("worlds") or {}
    full = len(batch) == d["Q6"]["batch_worlds"]
    out["batch_relative"] = (max_or_none(w["scalar_relative"] for w in batch.values())
                             if full else None)
    out["batch_reversed"] = (int(all(w["reversed_equal"] and w["final_reversed_equal"]
                                     for w in batch.values())) if full else None)
    out["batch_scalar_bitwise"] = (int(all(w["scalar_bitwise"] for w in batch.values()))
                                   if full else None)
    idle = parts.get("Q6_idle") or {}
    out["idle"] = (int(idle["zero_multipliers"] == [] and idle["no_populations"] == []
                       and idle["zero_world_fields_moved"] == []
                       and idle.get("no_populations_statically_idle") is True)
                   if completed(idle) else None)
    twins = parts.get("Q6_twins") or {}
    programs = twins.get("programs") or {}
    out["twins"] = (int(bool(programs) and all(p["text_equal"] and p["constants_equal"]
                                               for p in programs.values())
                        and twins["bindings_same_names_dtypes_shapes"]
                        and bool(twins["bindings_differing"]))
                    if completed(twins) else None)
    cases = (parts.get("Q6_signature") or {}).get("cases") or {}
    expected = d["Q6"]["signature"]
    out["signature"] = (int(set(cases) == set(expected) and all(
        (cases[c]["refused"] and "matching model array axes" in (cases[c]["message"] or ""))
        if want else not cases[c]["refused"] for c, want in expected.items()))
        if cases else None)
    classes = (parts.get("Q6_refusals") or {}).get("classes") or {}
    out["refusals"] = {cls: refusal_class(classes.get(cls), check)
                       for cls, check in d["Q6"]["refusal_checks"].items()}
    out["refusals_all"] = (None if any(v is None for v in out["refusals"].values())
                           else int(all(out["refusals"].values())))
    return out


def qss_order(refs, worlds):
    """The order in eps of R-ode against R-qss (reference side, reported)."""
    points = [(refs.get(w) or {}).get("qss") for w in worlds]
    if any(p is None for p in points):
        return None
    out = []
    for a, b in zip(points, points[1:], strict=False):
        out.append(math.log(a["relative_error_over_uptake"] / b["relative_error_over_uptake"])
                   / math.log(a["epsilon"] / b["epsilon"]))
    return dict(epsilon=[p["epsilon"] for p in points],
                relative_error_over_uptake=[p["relative_error_over_uptake"] for p in points],
                orders=out)


def derive(parts, protocol):
    """The protocol's derived metrics (module docstring)."""
    d = protocol["judge"]["derivation"]
    refs = (parts.get("references") or {}).get("worlds") or {}
    out = dict(admission=base.admission(parts, d["run_parts"]))
    engines = engine_records(parts, d)
    out["ids"] = dict(each={n: ids_within(p, d["engine_ids"]) for n, p in engines.items()})
    out["ids"]["all"] = (None if any(v is None for v in out["ids"]["each"].values())
                         else int(all(out["ids"]["each"].values())))
    # Every world part and ladder rung against R-ode (the state and energy budgets).
    worlds = {}
    for name, world in d["world_of"].items():
        part, ref = parts.get(name), refs.get(world)
        worlds[name] = dict(state=state_ratio(part, ref, d["F_state"]),
                            heat=energy_ratio(part, ref, "heat_pJ", d["F_energy"]),
                            work=energy_ratio(part, ref, "work_pJ", d["F_energy"]),
                            riccati=riccati_ratio(part, ref, d["F_state"]),
                            trace_independent=int(world in d["trace_independent"]))
    out["worlds"] = worlds
    for item, names in d["items"].items():
        out[item] = dict(
            state=max_or_none(worlds[n]["state"] for n in names),
            energy=max_or_none(v for n in names for v in (worlds[n]["heat"], worlds[n]["work"])))
    riccati_worlds = [n for n, w in d["world_of"].items() if (refs.get(w) or {}).get("riccati")]
    out["riccati"] = max_or_none(worlds[n]["riccati"] for n in riccati_worlds) if refs else None
    out["Q2_equilibrium"] = max_or_none(equilibrium_ratio(parts.get(w), refs.get(w),
                                                          d["F_state"]) for w in d["Q2"])
    out["Q2_quadratic"] = quadratic_ratio(parts.get(d["Q2_quadratic"]),
                                          refs.get(d["Q2_quadratic"]), d["F_state"])
    out["Q2_heat_to_equilibrium"] = max_or_none(heat_to_equilibrium_ratio(
        parts.get(w), refs.get(w), d["F_energy"]) for w in d["Q2"])
    out["orders"] = orders(parts, refs.get(d["ladder_world"]), d)
    out["Q1_eps_reported"] = qss_order(refs, d["qss_worlds"])
    out["Q4_accessibility"] = q4(parts, d)
    # Q5: the closure, the heat, the ledgers and the system total over every engine run.
    rounding = d["closure_rounding"]
    out["closure"] = {n: closure(p, rounding) for n, p in engines.items()}
    out["closure_max"] = max_or_none(out["closure"].values())
    out["heat"] = {n: heat_violation(p, rounding) for n, p in engines.items()}
    out["heat_max"] = max_or_none(out["heat"].values())
    out["ledgers"] = max_or_none(ledger_max(p, d["ledgers"]) for p in engines.values())
    out["system_total"] = max_or_none(system_total(p) for p in engines.values())
    out["background"] = background(parts, d)
    out["energy_margins_reported"] = {
        n: dict(heat=v["heat"], work=v["work"], trace_independent=v["trace_independent"])
        for n, v in worlds.items()}
    out["controls"] = controls(parts, refs, d)
    plants = {}
    for part, names in d["plants"].items():
        bundles = (parts.get(part) or {}).get("plants") or {}
        for plant in names:
            plants[plant] = plant_verdict(bundles.get(plant), d)
    out["plants"] = plants
    material = [plants.get(p) or {} for p in d["material_plants"]]
    out["plants_material_engine"] = (None if any(p.get("engine_names") is None for p in material)
                                     else int(all(p["engine_names"] for p in material)))
    out["plants_energy_engine_reported"] = {
        p: dict(refused=(plants.get(p) or {}).get("engine_refused"),
                message=(plants.get(p) or {}).get("engine_message"))
        for p in d["energy_plants"]}
    out["Q6"] = q6(parts, d)
    return out


def verdict(parts, protocol):
    derived = derive(parts, protocol)
    evaluated = evaluate(dict(criteria=protocol["judge"]["criteria"]),
                         dict(parts=parts, derived=derived))
    return derived, evaluated


def incomplete(parts, protocol):
    """The harness's completeness check (judge_harness, the external review's finding 4):
    - every world and ladder part, and its references world, holds the world's registered record
      grid (the code-blind references' record_times_s, in the derivation's record units);
    - every control run holds the grid of the references world it is judged against (its arm);
    - every registered refusal class of Q6 has a refused and an admitted example."""
    d = protocol["judge"]["derivation"]
    inputs = json.loads(INPUTS.read_text())["worlds"]
    refs = (parts.get("references") or {}).get("worlds") or {}
    problems, grids = [], {}
    for name in d["engine_parts"]:
        world = d["world_of"][name]
        if world not in grids:
            grids[world] = [int(round(t / d["record_unit_s"]))
                            for t in inputs[world]["record_times_s"]]
            found = (refs.get(world) or {}).get("record_ms")
            problems += harness.grid(f"references/{world}", found, grids[world])
        problems += harness.grid(name, (parts.get(name) or {}).get("record_ms"), grids[world])
    for name, spec in d["controls"].items():
        runs = (parts.get(name) or {}).get("runs") or {}
        for variant in spec:
            run = runs.get(variant) or {}
            arm = (refs.get(run.get("arm")) or {}).get("record_ms")
            problems += harness.grid(f"{name}/{variant}", run.get("record_ms"),
                                     arm if arm is not None else [None])
    classes = (parts.get("Q6_refusals") or {}).get("classes") or {}
    return problems + harness.classes(classes, d["Q6"]["refusal_checks"])


def harnessed(parts, protocol):
    """verdict's derivation and evaluation with the harness's checks before scoring: refused,
    as a harness failure, when the evidence is incomplete."""
    harness.refuse(incomplete(parts, protocol))  # Before any derivation.
    derived = derive(parts, protocol)
    criteria = protocol["judge"]["criteria"]
    harness.refuse(harness.metrics(criteria, dict(parts=parts, derived=derived)))
    return derived, evaluate(dict(criteria=criteria), dict(parts=parts, derived=derived))


def main(argv):
    if argv and argv[0] == "compare":
        return base.compare(*argv[1:])
    if len(argv) < 4 or argv[0] not in ("dev", "judged"):
        raise SystemExit(__doc__)
    mode, protocol_path, out_dir, paths = argv[0], argv[1], Path(argv[2]), argv[3:]
    # Both hold engine IDs (derivation.engine_ids, the parts' ids): both are read through the table.
    protocol = id_table.load(protocol_path)
    results_list = [(p, id_table.load(p)) for p in paths]
    if mode == "judged":
        why = base.refusal(protocol, results_list, out_dir)
        if why:
            raise SystemExit("Refused: " + why)
        label = "Judged verdict"
    else:
        if out_dir.exists():
            raise SystemExit("Refused: the output directory exists")
        label = "Development verdict (not a judgement: the protocol is not registered)"
    parts, origin = base.merge(results_list, protocol, judged=mode == "judged")
    if mode == "judged":
        derived, evaluated = harnessed(parts, protocol)  # Refused when the evidence is incomplete.
        gaps = []
    else:  # A development verdict records the harness's gaps (quick and partial runs are admitted).
        gaps = incomplete(parts, protocol)
        derived, evaluated = verdict(parts, protocol)
        gaps += harness.metrics(protocol["judge"]["criteria"],
                                dict(parts=parts, derived=derived))
    report = dict(version=harness.VERSION, gaps=gaps)
    record = dict(kind=label, harness=report,
                  protocol_id=protocol["id"], protocol_status=protocol["status"],
                  results=[str(p) for p in paths], part_sources=origin,
                  source=results_list[0][1].get("source"), passed=evaluated["passed"],
                  criteria=evaluated["criteria"], derived=derived)
    out_dir.mkdir(parents=True)
    (out_dir / "verdict.json").write_text(json.dumps(record, indent=1, allow_nan=False) + "\n")
    failed = [c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"]]
    print(label, "passed" if evaluated["passed"] else f"FAILED: {failed}")
    return record


if __name__ == "__main__":
    main(sys.argv[1:])
