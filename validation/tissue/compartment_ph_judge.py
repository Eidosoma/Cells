"""The judge of FR-4's and FR-5's qualification protocols: it reads records and never runs.

docs/COMPARTMENT_PH_TRANSFER_DESIGN.md §13-§14; the protocols fr4_acidification_v1.json and
fr5_transfer_v1.json under validation/compartment_ph/protocols/. The judge reads the generator's
results (validation/tissue/compartment_ph_qualification: records only, one results.json per
unit), merges the units (each part in exactly one, all from one source: MG0c's form), derives the
metrics below under the protocol's `judge.derivation`, and evaluates the protocol's machine
criteria (`judge.criteria`) with MG0c's evaluator (validation/morphogenesis/mg0a_gradient.evaluate:
a missing metric fails its criterion) into OUT_DIR/verdict.json. It imports nothing from the
generator.

The arithmetic, fixed before any run (the same on engine and reference records):
* **Records** are keyed by integer second; every series is aligned with its part's `record_s`.
* **Differences:** D(a, b) = max over shared records of |q_a - q_b| (the max norm).
* **J4's pH** (the lead's ruling of 15 November 2026, a dated pre-run correction): the pH of every
  buffered node, the lumen's and the cytosol's (the derivation's `ph_nodes`), the largest D over
  those nodes; None when any node's series is missing. K2's catch reads the same maximum, and so
  do J3's pH state error and J4_start's pH (the lead's later ruling, the same day).
* **Floors:** each rung difference has its floor F = N eps max|q| (N the finer rung's steps, max|q|
  over the finer rung's records): below it, the difference is accumulated rounding.
* **Orders, by class** (the lead's ruling of 15 November 2026), on the two differences of the three
  finest rungs, D1 (coarser) and D2: *resolved* (both at or above their floors) when log2(D1/D2)
  lies in the band; *at rounding* (both under) passes; *mixed* (D1 at or above, D2 under) passes
  unless the implied lower bound log2(D1/F2) exceeds the band's upper edge; *reversed* (D1 under,
  D2 at or above) fails. Every pair's class is reported. An exactly integrated quantity (FR-5's d)
  is expected at rounding on every pair. The energy residual takes the same classes with no upper
  edge, on every successive pair of rungs.
* **The Richardson error** at the declared dt is (4/3) D(dt, dt/2): the fixed nominal order p = 2,
  the scheme's (ARS(2,2,2)); the observed-order estimate is reported beside it.
* **Crossings** of a level (pH50): the first record where the series rises above the level, then
  the first after it where it falls below, each linearly interpolated between its two records.
* **Mean rates** of a cumulative transfer M (fmol, c to L positive) over [t0, t1]:
  |M(t1) - M(t0)| / (t1 - t0), with M linearly interpolated between records.
* **Material allowance** (the lead's ruling): per species, the declared floor plus N eps max over
  the records of the species' total over the conserved nodes (N the run's steps), computed here
  from the records and never read from the engine; the residual is |total(t) - total(0)|, and
  the route ledgers (FR-5's J6 and J8) use the same allowance. The charge check still reads the
  engine's residual and tolerance.
* **Refusals** (the lead's rulings of 15 November 2026): the engine's envelope check refuses the
  step at the first stage beyond the budget, so a completed part has no envelope refusal and J5
  reads the engine's running maximum of the lag estimate; K3 is caught by its refusal through the
  envelope (the generator's `refusal_reason`), and J1's admission leaves it out.
* **Undefined values are None, never NaN:** records compare bitwise, and a None fails.

Usage:
  python -m validation.tissue.compartment_ph_judge dev PROTOCOL OUT_DIR RESULTS [RESULTS ...]
  python -m validation.tissue.compartment_ph_judge judged PROTOCOL OUT_DIR RESULTS [RESULTS ...]
  python -m validation.tissue.compartment_ph_judge compare RESULTS_A RESULTS_B OUT_JSON
A judged verdict is refused, before anything is written, unless the protocol is registered (its
status and a registration record matching it), every results file is a complete judged run of it
from one clean execution snapshot with no stand-in and no quick horizon, the parts are exactly
the protocol's judged parts (each in one run), FR-5's start is one extract written by its own
`start` part, and OUT_DIR is new. `compare` checks two runs' records bit for bit, run times
apart (`wall_s`, `seconds` and `timings` at any depth: the rehearsal against the development run).
"""

import hashlib
import json
import math
import sys
from pathlib import Path

from validation import id_table
from validation.morphogenesis.mg0a_gradient import evaluate
from validation.tissue.regulated_availability_judge import differences

EPS = 2.0**-52
RICHARDSON = 4.0 / 3.0  # 1 / (1 - 2^-p) at the nominal p = 2


# ------------------------------------------------------------------------ the arithmetic


def aligned(part_a, part_b, name):
    """The two series of `name` on the records the two parts share (integer seconds)."""
    a = dict(zip((round(t) for t in part_a["record_s"]), part_a["series"][name], strict=True))
    b = dict(zip((round(t) for t in part_b["record_s"]), part_b["series"][name], strict=True))
    shared = sorted(set(a) & set(b))
    return [a[t] for t in shared], [b[t] for t in shared]


def max_abs_difference(part_a, part_b, name):
    """D(a, b): the largest |a - b| over shared records; None when either part lacks the series
    or they share no record."""
    if not usable(part_a, name) or not usable(part_b, name):
        return None
    a, b = aligned(part_a, part_b, name)
    return max(abs(x - y) for x, y in zip(a, b, strict=True)) if a else None


def usable(part, name):
    return bool(part) and part.get("completed") is not False and name in part.get("series", {})


def rounding_scale(part, name):
    """N eps max|q|: the finer rung's accumulated rounding (N its steps)."""
    values = part["series"][name]
    return part["steps"] * EPS * max(abs(v) for v in values)


def log2_ratio(a, b):
    return math.log2(a / b) if a is not None and b is not None and a > 0 and b > 0 else None


def classify(coarser, finer, band):
    """The class of two successive differences, each with its floor, and whether it passes
    (band (low, high); high None for no upper edge)."""
    low, high = band
    if coarser["difference"] is None or finer["difference"] is None:
        return dict(cls=None, order=None, lower_bound=None, passes=0)
    if coarser["above"] and finer["above"]:
        order = log2_ratio(coarser["difference"], finer["difference"])
        ok = order is not None and order >= low and (high is None or order <= high)
        return dict(cls="resolved", order=order, lower_bound=None, passes=int(ok))
    if not coarser["above"] and not finer["above"]:
        return dict(cls="at_rounding", order=None, lower_bound=None, passes=1)
    if coarser["above"]:
        bound = log2_ratio(coarser["difference"], finer["floor"])
        ok = high is None or bound is None or bound <= high
        return dict(cls="mixed", order=None, lower_bound=bound, passes=int(ok))
    return dict(cls="reversed", order=None, lower_bound=None, passes=0)


def ladder(parts, names, observable, band):
    """Successive differences down a ladder of rung parts (coarse to fine), each with its floor,
    every pair of successive differences classified, and the judged class on the three finest
    rungs (`passes`, `order_finest`); `at_rounding_every_pair` is 1 when every difference is
    under its floor."""
    rungs = [parts.get(n) for n in names]
    pairs = []
    for coarse, fine in zip(rungs, rungs[1:], strict=False):
        d = max_abs_difference(coarse, fine, observable)
        floor = rounding_scale(fine, observable) if d is not None else None
        pairs.append(dict(difference=d, floor=floor,
                          above=None if d is None else bool(d > 0 and d >= floor)))
    classes = [classify(a, b, band) for a, b in zip(pairs, pairs[1:], strict=False)]
    judged = classes[-1] if classes else dict(cls=None, order=None, lower_bound=None, passes=0)
    return dict(differences=[q["difference"] for q in pairs], floors=[q["floor"] for q in pairs],
                classes=classes, judged_class=judged["cls"], passes=judged["passes"],
                order_finest=judged["order"], lower_bound=judged["lower_bound"],
                at_rounding_every_pair=int(bool(pairs) and all(q["above"] is False
                                                                for q in pairs)))


def richardson(parts, declared, half, observable):
    """(4/3) D(dt, dt/2) at the declared dt (the nominal p = 2)."""
    d = max_abs_difference(parts.get(declared), parts.get(half), observable)
    return None if d is None else RICHARDSON * d


def richardson_observed(parts, declared, half, observable, order):
    """D(dt, dt/2) / (1 - 2^-p) at the observed order p (reported beside the nominal one)."""
    d = max_abs_difference(parts.get(declared), parts.get(half), observable)
    return None if d is None or order is None or order <= 0 else d / (1.0 - 2.0**-order)


def crossings(times, values, level):
    """(t_up, t_down): the first up-crossing of `level`, then the first down-crossing after it,
    each linearly interpolated between its two records; None where there is none."""

    def interpolate(i):
        t0, t1, v0, v1 = times[i - 1], times[i], values[i - 1], values[i]
        return t0 + (level - v0) / (v1 - v0) * (t1 - t0)

    up = next((i for i in range(1, len(values))
               if values[i - 1] <= level < values[i]), None)
    if up is None:
        return None, None
    down = next((i for i in range(up + 1, len(values))
                 if values[i - 1] >= level > values[i]), None)
    return interpolate(up), (None if down is None else interpolate(down))


def at_time(times, values, t):
    """The series at t, linearly interpolated between the records that bracket it."""
    if t is None or not times[0] <= t <= times[-1]:
        return None
    i = next(k for k in range(1, len(times)) if times[k] >= t) if t > times[0] else 1
    t0, t1 = times[i - 1], times[i]
    return values[i - 1] + (values[i] - values[i - 1]) * (t - t0) / (t1 - t0)


def mean_rate(times, cumulative, t0, t1):
    """|M(t1) - M(t0)| / (t1 - t0); None when undefined."""
    a, b = at_time(times, cumulative, t0), at_time(times, cumulative, t1)
    if a is None or b is None or t1 is None or t0 is None or not t1 > t0:
        return None
    return abs(b - a) / (t1 - t0)


def ratio(a, b):
    return a / b if a is not None and b is not None and b > 0 else None


def max_or_none(values):
    values = list(values)
    return None if not values or any(v is None for v in values) else max(values)


def richardson_ph(parts, declared, half, nodes):
    """J3's pH state error: the largest Richardson error over every buffered node's pH series
    (`nodes`); None when any is missing."""
    return max_or_none(richardson(parts, declared, half, x) for x in nodes)


def row0_ph(part_a, part_b, nodes):
    """J4_start's pH: the largest row-0 difference over every buffered node's pH series."""
    return max_or_none(row0(part_a, part_b, x) for x in nodes)


def ph_max_abs(part_a, part_b, nodes):
    """J4's pH difference: the largest D(a, b) over every buffered node's pH series (`nodes`)
    and the shared records; None when any node's series is missing (a missing value fails)."""
    return max_or_none(max_abs_difference(part_a, part_b, x) for x in nodes)


def series(part, name):
    return part["series"][name] if usable(part, name) else None


def times_of(part):
    return [float(round(t)) for t in part["record_s"]]


def drop(part, name="pH_L"):
    """The fall of a series from its first record to its last."""
    s = series(part, name)
    return None if s is None else s[0] - s[-1]


# ------------------------------------------------------------------------ shared derivations


def admission(parts, names):
    """1 when every named part was admitted and ran to its end; per part beside it."""
    each = {n: int(bool(parts.get(n)) and parts[n].get("admitted") is True
                   and parts[n].get("completed") is True) for n in names}
    return dict(all_admitted=int(all(each.values())), parts=each)


def envelope(parts, names):
    """The closure's largest estimated lag over every stage of the named parts, and the count of
    stages beyond the budget (the engine's per-stage diagnostics)."""
    lags, beyond = [], []
    for n in names:
        stage = (parts.get(n) or {}).get("stage") or {}
        lags.append(stage.get("envelope_max_lag_ph"))
        beyond.append(stage.get("envelope_stages_beyond"))
    return dict(max_lag_ph=max_or_none(lags),
                stages_beyond=None if any(b is None for b in beyond) else sum(beyond))


def envelope_refusal(part):
    """K3's catch (the lead's ruling, 15 November 2026): 1 when the engine refused the part
    through the envelope check (the generator's attributed `refusal_reason`), 0 when it ran to its
    end, else None (a refusal for another reason is not the catch)."""
    if not part:
        return None
    if part.get("refusal_reason") == "envelope":
        return 1
    return 0 if part.get("completed") is True else None


def cytosol_band(parts, names, centre):
    """The cytosol's largest |pH_c - centre| over every stage of the named parts."""
    out = []
    for n in names:
        stage = (parts.get(n) or {}).get("stage") or {}
        low, high = stage.get("cytosol_pH_min"), stage.get("cytosol_pH_max")
        out.append(None if low is None or high is None else max(abs(low - centre),
                                                                  abs(high - centre)))
    return max_or_none(out)


def totals(part, species, nodes):
    """The species' total over the conserved nodes at every record, or None."""
    amounts = (part or {}).get("amounts_fmol")
    if not amounts or part.get("completed") is False:
        return None
    try:
        columns = [amounts[node][species] for node in nodes]
    except KeyError:
        return None
    return [math.fsum(values) for values in zip(*columns, strict=True)]


def allowance(part, species, nodes, floors):
    """The declared floor plus N eps max over the records of the species' total (N the steps)."""
    total = totals(part, species, nodes)
    if total is None or part.get("steps") is None:
        return None
    return floors[species] + part["steps"] * EPS * max(abs(t) for t in total)


def material(parts, names, d):
    """The judge's material check: per part and species, max |total(t) - total(0)| over the
    allowance; the largest ratio, and each part's per-species record."""
    report, ratios = {}, []
    for n in names:
        part, per = parts.get(n), {}
        for species in d["species"]:
            total = totals(part, species, d["conserved_nodes"])
            if total is None:
                per[species] = None
                ratios.append(None)
                continue
            residual = max(abs(t - total[0]) for t in total)
            room = allowance(part, species, d["conserved_nodes"], d["material_floors_fmol"])
            per[species] = dict(residual_fmol=residual, allowance_fmol=room,
                                ratio=residual / room)
            ratios.append(residual / room)
        report[n] = per
    return dict(max_over_allowance=max_or_none(ratios), parts=report)


def charge(parts, names):
    out = []
    for n in names:
        ledgers = (parts.get(n) or {}).get("ledgers") or {}
        out.append(ratio(ledgers.get("charge_residual_C"), ledgers.get("charge_tolerance_C")))
    return max_or_none(out)


def energy_over_flows(part):
    """max over records with flows of |stored change + heat - work| / the integrated flows."""
    residual, flows = series(part, "energy_residual_pJ"), series(part, "energy_flows_pJ")
    if residual is None or flows is None:
        return None
    values = [abs(r) / f for r, f in zip(residual, flows, strict=True) if f > 0]
    return max(values) if values else None


def energy_ladder(parts, names, low):
    """The energy residual over flows down the ladder, each value with its floor N eps (N its
    rung's steps), every successive pair classified with no upper edge and `low` as its lower
    edge (the lead's ruling): `passes` when every pair passes; the smallest resolved order
    reported."""
    values = [energy_over_flows(parts.get(n) or {}) for n in names]
    points = []
    for n, v in zip(names, values, strict=True):
        steps = (parts.get(n) or {}).get("steps")
        floor = None if steps is None else steps * EPS
        points.append(dict(difference=v, floor=floor,
                           above=None if v is None or floor is None else bool(v > 0 and
                                                                               v >= floor)))
    classes = [classify(a, b, (low, None))
               for a, b in zip(points, points[1:], strict=False)]
    resolved = [c["order"] for c in classes if c["cls"] == "resolved" and c["order"] is not None]
    return dict(values=values, floors=[q["floor"] for q in points], classes=classes,
                passes=int(bool(classes) and all(c["passes"] for c in classes)),
                smallest_resolved_order=min(resolved) if resolved else None)


def heat_increments(part, routes):
    """Each route's smallest increase of its cumulative heat between successive records, and the
    smallest over the routes (None when a route's series is missing)."""
    each = {}
    for route in routes:
        s = series(part, f"heat_{route}_pJ")
        each[route] = None if s is None else min((b - a for a, b in zip(s, s[1:], strict=False)),
                                                default=None)
    values = list(each.values())
    smallest = None if not values or any(v is None for v in values) else min(values)
    return dict(each=each, smallest=smallest)


def route_ledger(part, node_series, transfers, *, sign, tolerance):
    """Per record: |(q(t) - q(0)) - sign x the routes' cumulative transfers| over the tolerance
    (sign +1 for the lumen, which the c-to-L transfers fill; -1 for the cytosol)."""
    q = series(part, node_series)
    moved = [series(part, m) for m in transfers]
    if q is None or any(m is None for m in moved) or tolerance is None:
        return None
    out = []
    for i, value in enumerate(q):
        total = math.fsum(m[i] for m in moved)
        out.append(abs((value - q[0]) - sign * total) / tolerance)
    return max(out)


def row0(part_a, part_b, name):
    a, b = series(part_a, name), series(part_b, name)
    return None if a is None or b is None else abs(a[0] - b[0])


# ------------------------------------------------------------------------ FR-4


def derive_fr4(parts, derivation):
    """FR-4's derived metrics (the protocol's J1-J7)."""
    d = derivation
    rungs, declared, half = d["ladder_parts"], d["declared_part"], d["half_part"]
    reference = parts.get("reference") or {}
    worlds = reference.get("worlds", {})
    ref, floor = worlds.get("declared"), worlds.get("floor")
    k1_name, k2_name, k3_name = d["control_parts"]
    # J1 (the lead's ruling, 15 November 2026): K3 is refused by design, so it leaves admission.
    out = dict(admission=admission(parts, list(rungs) + [k1_name, k2_name, "reference"]))
    out["orders"] = {x: ladder(parts, rungs, x, d["band"]) for x in d["order_observables"]}
    v_b = series(parts.get(declared), "V_b")
    v_range = None if v_b is None else max(v_b) - min(v_b)
    out["state_error"] = dict(
        pH=richardson_ph(parts, declared, half, d["ph_nodes"]),
        pH_L=richardson(parts, declared, half, "pH_L"),
        pH_c=richardson(parts, declared, half, "pH_c"),
        V_b=richardson(parts, declared, half, "V_b"),
        V_b_range=v_range,
        V_b_over_range=ratio(richardson(parts, declared, half, "V_b"), v_range),
        observed_order=dict(
            pH_L=richardson_observed(parts, declared, half, "pH_L",
                                     out["orders"]["pH_L"]["order_finest"]),
            V_b=richardson_observed(parts, declared, half, "V_b",
                                    out["orders"]["V_b"]["order_finest"])),
    )
    eng = parts.get(declared)
    out["reference"] = {f"{x}_max_abs": max_abs_difference(eng, ref, x)
                        for x in d["reference_observables"]}
    out["reference"].update(
        pH_max_abs=ph_max_abs(eng, ref, d["ph_nodes"]),
        start_pH=row0_ph(eng, ref, d["ph_nodes"]), start_pH_L=row0(eng, ref, "pH_L"),
        start_pH_c=row0(eng, ref, "pH_c"), start_V_b=row0(eng, ref, "V_b"),
        floor_pH_L=max_abs_difference(ref, floor, "pH_L"),
        floor_pH=ph_max_abs(ref, floor, d["ph_nodes"]))
    out["envelope"] = envelope(parts, rungs)
    out["ledgers"] = dict(
        material=material(parts, rungs, d),
        charge_over_tolerance=charge(parts, rungs),
        energy_over_flows_at_declared=energy_over_flows(eng or {}),
        energy=energy_ladder(parts, rungs, d["energy_order_low"]),
    )
    out["bands"] = dict(cytosol_pH_max_deviation=cytosol_band(parts, rungs, d["cytosol_pH"]))
    k3 = envelope(parts, [k3_name])
    out["controls"] = dict(
        k1=dict(control_drop_ph=drop(parts.get(k1_name)), declared_drop_ph=drop(eng),
                reference_control_drop_ph=drop(worlds.get("control_k1"))),
        k2=dict(pH_max_abs_vs_reference=ph_max_abs(parts.get(k2_name), ref, d["ph_nodes"]),
                **{f"{x}_max_abs_vs_reference": max_abs_difference(parts.get(k2_name), ref, x)
                   for x in d["ph_nodes"]}),
        k3=dict(engine_max_lag_ph=k3["max_lag_ph"],
                engine_stages_beyond=envelope_refusal(parts.get(k3_name)),
                kinetic_departure_ph=max_abs_difference(worlds.get("kinetic_outside"), ref,
                                                        "pH_L")),
    )
    return out


# ------------------------------------------------------------------------ FR-5


def derive_arm(parts, arm, d):
    """One FR-5 arm's derived metrics (the protocol's J1-J11)."""
    a = d["arms"][arm]
    rungs, declared, half, control = a["ladder_parts"], a["declared_part"], a["half_part"], a[
        "control_part"]
    worlds = (parts.get("reference") or {}).get("worlds", {})
    ref, ref_floor = worlds.get(arm), worlds.get(f"{arm}_floor")
    eng, ctl = parts.get(declared), parts.get(control)
    x_l = series(ref, "X_L")
    budget = None if x_l is None else d["x_budget_fraction"] * x_l[0]
    out = dict(budget_fmol=budget,
               admission=admission(parts, list(rungs) + [control, "start", "reference"]))
    out["orders"] = {x: ladder(parts, rungs, x, d["band"])
                     for x in [*d["order_observables"], *d.get("exact_observables", [])]}
    out["state_error"] = dict(
        X_L_over_budget=ratio(richardson(parts, declared, half, "X_L"), budget),
        pH=richardson_ph(parts, declared, half, d["ph_nodes"]),
        pH_L=richardson(parts, declared, half, "pH_L"),
        pH_c=richardson(parts, declared, half, "pH_c"))
    transfer = a["conditioned_transfer"]
    out["reference"] = dict(
        X_L_over_budget=ratio(max_abs_difference(eng, ref, "X_L"), budget),
        transfer_over_budget=ratio(max_abs_difference(eng, ref, transfer), budget),
        pH_L_max_abs=max_abs_difference(eng, ref, "pH_L"),
        pH_c_max_abs=max_abs_difference(eng, ref, "pH_c"),
        pH_max_abs=ph_max_abs(eng, ref, d["ph_nodes"]),
        floor_X_L_over_budget=ratio(max_abs_difference(ref, ref_floor, "X_L"), budget),
        floor_pH_L=max_abs_difference(ref, ref_floor, "pH_L"),
        floor_pH=ph_max_abs(ref, ref_floor, d["ph_nodes"]),
    )
    starts = [eng] + [parts.get(n) for n in rungs if n != declared] + [ctl]
    out["start"] = dict(
        pH=max_or_none([row0_ph(p, ref, d["ph_nodes"]) for p in starts]),
        pH_L=max_or_none([row0(p, ref, "pH_L") for p in starts]),
        pH_c=max_or_none([row0(p, ref, "pH_c") for p in starts]),
        V_b=max_or_none([row0(p, ref, "V_b") for p in starts]),
        X_L_over_budget=ratio(max_or_none([row0(p, ref, "X_L") for p in starts]), budget))
    out["envelope"] = envelope(parts, list(rungs) + [control])
    nodes, floors = d["conserved_nodes"], d["material_floors_fmol"]
    room_h, room_x = (allowance(eng, s_, nodes, floors) for s_ in ("H", "X"))
    protons = list(d["proton_transfers"])
    cargo = list(a["cargo_transfers"])
    out["protons"] = dict(
        allowance_fmol=room_h,
        lumen_over_allowance=route_ledger(eng or {}, "Heq_L", protons, sign=1, tolerance=room_h),
        cytosol_over_allowance=route_ledger(eng or {}, "Heq_c", protons, sign=-1,
                                            tolerance=room_h))
    out["protons"]["max_over_allowance"] = max_or_none(
        [out["protons"]["lumen_over_allowance"], out["protons"]["cytosol_over_allowance"]])
    heat = heat_increments(eng or {}, a["passive_routes"])
    out["energy"] = dict(
        over_flows_at_declared=energy_over_flows(eng or {}),
        ladder=energy_ladder(parts, rungs, d["energy_order_low"]),
        route_heat_increments_pJ=heat["each"],
        smallest_judged_route_heat_increment_pJ=heat_increments(
            eng or {}, a["judged_heat_routes"])["smallest"])
    material_report = material(parts, [declared], d)
    x_report = (material_report["parts"].get(declared) or {}).get("X")
    out["material"] = material_report
    out["cargo"] = dict(
        allowance_fmol=room_x,
        material_over_allowance=None if x_report is None else x_report["ratio"],
        lumen_over_allowance=route_ledger(eng or {}, "X_L", cargo, sign=1, tolerance=room_x),
        cytosol_over_allowance=route_ledger(eng or {}, "X_c", cargo, sign=-1, tolerance=room_x))
    d_series, f_series = series(eng, "d"), series(eng, "f")
    out["bands"] = dict(
        cytosol_pH_max_deviation=cytosol_band(parts, list(rungs) + [control], d["cytosol_pH"]),
        d_min=None if d_series is None else min(d_series),
        d_max=None if d_series is None else max(d_series),
        f_min=None if f_series is None else min(f_series),
        f_max=None if f_series is None else max(f_series))
    out["control"] = dict(
        name=a["control"],
        X_L_over_budget=ratio(max_abs_difference(eng, ctl, "X_L"), budget),
        transfer_over_budget=ratio(max_abs_difference(eng, ctl, transfer), budget),
        pH_L_max_abs=max_abs_difference(eng, ctl, "pH_L"))
    out["claims"] = claims(eng, ref, a, budget)
    return out


def claims(eng, ref, a, budget):
    """J11 on the declared rung and on the reference, with one arithmetic: the pH50 crossings, arm
    T's mean-rate ratio, arm R's release through the pore."""
    out = {}
    for label, part in (("engine", eng), ("reference", ref)):
        if not usable(part, "pH_L"):
            out[label] = None
            continue
        t, ph = times_of(part), part["series"]["pH_L"]
        up, down = crossings(t, ph, a["ph50"])
        entry = dict(up_s=up, down_s=down,
                     returns_before_end=int(down is not None and down < t[-1]))
        m = series(part, a["conditioned_transfer"])
        w0, w1 = a["injury_window_s"]
        if m is not None:
            before, above = mean_rate(t, m, 0.0, w0), mean_rate(t, m, up, down)
            entry.update(pre_damage_rate_per_budget=ratio(before, budget),
                         above_rate_per_budget=ratio(above, budget),
                         above_over_pre=ratio(above, before),
                         pre_over_above=ratio(before, above))
        pore = a.get("pore_transfer")
        if pore and usable(part, pore):
            x_l = part["series"]["X_L"]
            moved = part["series"][pore]
            # None where the records do not reach the window (a refused or quick part).
            at_start, at_end = at_time(t, moved, w0), at_time(t, moved, w1)
            out_of_lumen = None if at_start is None or at_end is None else at_start - at_end
            entry["released_in_window"] = ratio(out_of_lumen, x_l[0])
        out[label] = entry
    e, r = out.get("engine"), out.get("reference")
    out["down_crossing_difference_s"] = (
        abs(e["down_s"] - r["down_s"]) if e and r and e["down_s"] is not None
        and r["down_s"] is not None else None)
    out["up_crossing_difference_s"] = (
        abs(e["up_s"] - r["up_s"]) if e and r and e["up_s"] is not None
        and r["up_s"] is not None else None)
    return out


def derive_fr5(parts, derivation):
    return {arm: derive_arm(parts, arm, derivation) for arm in derivation["arms"]}


DERIVE = {"fr4-acidification-v1": derive_fr4, "fr5-transfer-v1": derive_fr5}


def derive(parts, protocol):
    return DERIVE[protocol["id"]](parts, protocol["judge"]["derivation"])


def verdict(parts, protocol):
    derived = derive(parts, protocol)
    evaluated = evaluate(dict(criteria=protocol["judge"]["criteria"]),
                         dict(parts=parts, derived=derived))
    return derived, evaluated


def incomplete(parts, protocol):
    """The harness's completeness check (judge_harness, the external review's finding 4), added
    beside the arithmetic above, which is unchanged. Every part compared at shared records, and each
    references world compared with it, holds the grid of the reference's own world, keyed as the
    arithmetic keys records (round(t)). FR-4's and FR-5's protocols register no record list, so the
    code-blind reference's world defines the grid: FR-4's `declared` (with `floor` and
    `kinetic_outside`), and each FR-5 arm's own (with its floor)."""
    from validation.tissue import judge_harness as harness

    d = protocol["judge"]["derivation"]
    worlds = (parts.get("reference") or {}).get("worlds") or {}
    if protocol["id"] == "fr4-acidification-v1":
        groups = [("declared", ("floor", "kinetic_outside"),
                   (*d["ladder_parts"], d["declared_part"], d["half_part"], d["control_parts"][1]))]
    else:
        groups = [(arm, (f"{arm}_floor",),
                   (*a["ladder_parts"], a["declared_part"], a["half_part"], a["control_part"]))
                  for arm, a in d["arms"].items()]

    def keyed(times):
        return None if times is None else [round(t) for t in times]

    problems = []
    for world, others, names in groups:
        grid = keyed((worlds.get(world) or {}).get("record_s"))
        if not grid:
            problems.append(f"reference/{world}: no record grid")
            continue
        for other in others:
            problems += harness.grid(f"reference/{other}",
                                     keyed((worlds.get(other) or {}).get("record_s")), grid)
        for name in dict.fromkeys(names):
            problems += harness.grid(name, keyed((parts.get(name) or {}).get("record_s")), grid)
    return problems


def harnessed(parts, protocol):
    """verdict's derivation and evaluation with the harness's checks before scoring: refused,
    as a harness failure, when the evidence is incomplete."""
    from validation.tissue import judge_harness as harness

    harness.refuse(incomplete(parts, protocol))  # Before any derivation.
    derived = derive(parts, protocol)
    criteria = protocol["judge"]["criteria"]
    harness.refuse(harness.metrics(criteria, dict(parts=parts, derived=derived)))
    return derived, evaluate(dict(criteria=criteria), dict(parts=parts, derived=derived))


# ------------------------------------------------------------------------ merging and refusals


def merge(results_list, protocol, *, judged):
    """The parts of several unit runs (MG0c's form): refused unless every run is of this protocol,
    from one source, complete, not quick and without stand-ins (judged), with each part in one
    run; FR-5's parts all on the extract its `start` part wrote."""
    parts, origin, sources = {}, {}, []
    for path, data in results_list:
        if data.get("protocol_id") != protocol["id"]:
            raise SystemExit(f"Refused: {path} is not a run of {protocol['id']}")
        if judged:
            if data.get("status") != "Judged run of " + protocol["id"]:
                raise SystemExit(f"Refused: {path} is not a judged run of {protocol['id']}")
            if data.get("quick") or data.get("stand_ins"):
                raise SystemExit(f"Refused: {path} ran a quick horizon or a stand-in")
            requested = data.get("requested_parts") or []
            if not data.get("complete") or sorted(data["parts"]) != sorted(requested):
                raise SystemExit(f"Refused: {path} is incomplete (an infrastructure ending: rerun "
                                 "its unit once from the same snapshot into a new directory)")
        sources.append(data.get("source"))
        for name, value in data["parts"].items():
            if name in parts:
                raise SystemExit(f"Refused: part {name} is in more than one run")
            parts[name], origin[name] = value, str(path)
    if any(s != sources[0] for s in sources):
        raise SystemExit("Refused: the runs come from more than one source")
    if protocol["id"] == "fr5-transfer-v1" and judged:
        written = (parts.get("start") or {}).get("extract_sha256")
        used = {n: (p.get("start") or {}).get("extract_sha256") for n, p in parts.items()
                if n != "start"}
        if written is None or any(v != written for v in used.values()):
            raise SystemExit("Refused: FR-5's parts do not all start from the extract its start "
                             "part wrote")
    return parts, origin


def refusal(protocol, results_list, out_dir):
    """Why a judged verdict may not be written (None: it may)."""
    status = protocol.get("status")
    if not (isinstance(status, str) and status.lower().startswith("registered")):
        return "the protocol is not registered (its status does not begin 'registered')"
    record = protocol.get("registration")
    if not (isinstance(record, dict) and record.get("status") == status):
        return "the protocol's registration record is missing or does not match its status"
    for path, data in results_list:
        source = data.get("source") or {}
        clean = source.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
        if source.get("kind") != "snapshot" or source.get("status") != "complete" or not clean:
            return f"{path} did not come from a clean, complete execution snapshot"
    named = sorted(n for _, data in results_list for n in data.get("parts", {}))
    if named != sorted(protocol["judged_parts"]):
        return "the runs' parts are not exactly the protocol's judged parts"
    if Path(out_dir).exists():
        return "the output directory exists (each attempt writes its own)"
    return None


RUN_TIME_KEYS = ("wall_s", "seconds", "timings")  # The generator's and the references' clocks.


def without_run_times(value):
    """A record without its run-time leaves (RUN_TIME_KEYS, at any depth): what compare checks."""
    if isinstance(value, dict):
        return {k: without_run_times(v) for k, v in value.items() if k not in RUN_TIME_KEYS}
    if isinstance(value, list):
        return [without_run_times(v) for v in value]
    return value


def compare(path_a, path_b, out_json):
    """Two runs' records bit for bit, run times apart (RUN_TIME_KEYS; Track R's `differences`),
    the renamed IDs of a saved one translated."""
    a = id_table.load(path_a)
    b = id_table.load(path_b)
    parts = {}
    for name in sorted(set(a["parts"]) | set(b["parts"])):
        if name not in a["parts"] or name not in b["parts"]:
            parts[name] = "in one run only"
            continue
        found = differences(without_run_times(a["parts"][name]),
                            without_run_times(b["parts"][name]))
        parts[name] = dict(identical=not found, differences=found[:20])
    report = dict(a=str(path_a), b=str(path_b), a_source=a.get("source"),
                  b_source=b.get("source"), parts=parts)
    Path(out_json).write_text(json.dumps(report, indent=1) + "\n")
    return report


def main(argv):
    if argv and argv[0] == "compare":
        return compare(*argv[1:])
    if len(argv) < 4 or argv[0] not in ("dev", "judged"):
        raise SystemExit(__doc__)
    mode, protocol_path, out_dir, paths = argv[0], argv[1], Path(argv[2]), argv[3:]
    protocol = json.loads(Path(protocol_path).read_text())
    results_list = [(p, json.loads(Path(p).read_text())) for p in paths]
    if mode == "judged":
        why = refusal(protocol, results_list, out_dir)
        if why:
            raise SystemExit("Refused: " + why)
        label = "Judged verdict"
    else:
        if out_dir.exists():
            raise SystemExit("Refused: the output directory exists")
        label = "Development verdict (not a judgement: the protocol is not registered)"
    parts, origin = merge(results_list, protocol, judged=mode == "judged")
    from validation.tissue import judge_harness

    if mode == "judged":
        derived, evaluated = harnessed(parts, protocol)  # Refused when the evidence is incomplete.
        gaps = []
    else:  # A development verdict records the harness's gaps (quick and partial runs are admitted).
        gaps = incomplete(parts, protocol)
        derived, evaluated = verdict(parts, protocol)
        gaps += judge_harness.metrics(protocol["judge"]["criteria"],
                                      dict(parts=parts, derived=derived))
    report = dict(version=judge_harness.VERSION, gaps=gaps)
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
