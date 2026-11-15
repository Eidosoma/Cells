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
* **Resolution:** a rung difference is resolved when it is at least N eps max|q| (N the finer
  rung's steps, max|q| over the finer rung's records): below that it is accumulated rounding.
* **Orders** come from the three finest rungs: log2(D(dt1, dt2) / D(dt2, dt3)), defined when both
  differences are resolved (else None). Every successive pair's order is reported beside it.
* **The Richardson error** at the declared dt is (4/3) D(dt, dt/2): the fixed nominal order p = 2,
  the scheme's (ARS(2,2,2)); the observed-order estimate is reported beside it.
* **Crossings** of a level (pH50): the first record where the series rises above the level, then
  the first after it where it falls below, each linearly interpolated between its two records.
* **Mean rates** of a cumulative transfer M (fmol, c to L positive) over [t0, t1]:
  |M(t1) - M(t0)| / (t1 - t0), with M linearly interpolated between records.
* **Ledgers:** a residual over its tolerance, the tolerance the engine's own check uses and records
  (`material_tolerance_fmol`: the declared floor plus the engine's rounding allowance).
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
apart (the rehearsal against the development run).
"""

import hashlib
import json
import math
import sys
from pathlib import Path

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


def ladder(parts, names, observable):
    """Successive differences down a ladder of rung parts (coarse to fine), their resolution, the
    successive orders, and the order on the three finest rungs."""
    rungs = [parts.get(n) for n in names]
    pairs = []
    for coarse, fine in zip(rungs, rungs[1:], strict=False):
        d = max_abs_difference(coarse, fine, observable)
        needed = rounding_scale(fine, observable) if d is not None else None
        pairs.append(dict(difference=d, needed=needed,
                          resolved=bool(d is not None and d > 0 and d >= needed)))
    orders = []
    for p, q in zip(pairs, pairs[1:], strict=False):
        both = p["resolved"] and q["resolved"]
        orders.append(log2_ratio(p["difference"], q["difference"]) if both else None)
    return dict(differences=[p["difference"] for p in pairs], needed=[p["needed"] for p in pairs],
                resolved=[p["resolved"] for p in pairs], orders=orders,
                order_finest=orders[-1] if orders else None)


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


def cytosol_band(parts, names, centre):
    """The cytosol's largest |pH_c - centre| over every stage of the named parts."""
    out = []
    for n in names:
        stage = (parts.get(n) or {}).get("stage") or {}
        low, high = stage.get("cytosol_pH_min"), stage.get("cytosol_pH_max")
        out.append(None if low is None or high is None else max(abs(low - centre),
                                                                  abs(high - centre)))
    return max_or_none(out)


def material(parts, names):
    """The engine's material check: the largest residual over its tolerance, per species and
    record, over the named parts."""
    out = []
    for n in names:
        ledgers = (parts.get(n) or {}).get("ledgers") or {}
        residual, tolerance = ledgers.get("material_residual_fmol"), ledgers.get(
            "material_tolerance_fmol")
        if residual is None or tolerance is None:
            out.append(None)
            continue
        out.append(max(r / tolerance[s] for s, r in residual.items()))
    return max_or_none(out)


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


def energy_ladder(parts, names):
    """The energy residual over flows down the ladder: its successive orders where the finer
    value is above rounding (N eps), and the smallest of them."""
    values = [energy_over_flows(parts.get(n) or {}) for n in names]
    orders = []
    for i in range(len(names) - 1):
        a, b = values[i], values[i + 1]
        steps = (parts.get(names[i + 1]) or {}).get("steps")
        resolved = b is not None and steps is not None and b >= steps * EPS
        orders.append(log2_ratio(a, b) if resolved else None)
    defined = [o for o in orders if o is not None]
    return dict(values=values, orders=orders, smallest_order=min(defined) if defined else None)


def heat_increments(part, routes):
    """The smallest increase of each route's cumulative heat between successive records."""
    out = []
    for route in routes:
        s = series(part, f"heat_{route}_pJ")
        if s is None:
            return None
        out += [b - a for a, b in zip(s, s[1:], strict=False)]
    return min(out) if out else None


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
    engine_parts = list(rungs) + list(d["control_parts"])
    out = dict(admission=admission(parts, engine_parts + ["reference"]))
    out["orders"] = {x: ladder(parts, rungs, x) for x in d["order_observables"]}
    v_b = series(parts.get(declared), "V_b")
    v_range = None if v_b is None else max(v_b) - min(v_b)
    out["state_error"] = dict(
        pH_L=richardson(parts, declared, half, "pH_L"),
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
        start_pH_L=row0(eng, ref, "pH_L"), start_V_b=row0(eng, ref, "V_b"),
        floor_pH_L=max_abs_difference(ref, floor, "pH_L"))
    out["envelope"] = envelope(parts, rungs)
    out["ledgers"] = dict(
        material_over_tolerance=material(parts, rungs),
        charge_over_tolerance=charge(parts, rungs),
        energy_over_flows_at_declared=energy_over_flows(eng or {}),
        energy=energy_ladder(parts, rungs),
    )
    out["bands"] = dict(cytosol_pH_max_deviation=cytosol_band(parts, rungs, d["cytosol_pH"]))
    k1_name, k2_name, k3_name = d["control_parts"]
    k3 = envelope(parts, [k3_name])
    out["controls"] = dict(
        k1=dict(control_drop_ph=drop(parts.get(k1_name)), declared_drop_ph=drop(eng),
                reference_control_drop_ph=drop(worlds.get("control_k1"))),
        k2=dict(pH_L_max_abs_vs_reference=max_abs_difference(parts.get(k2_name), ref, "pH_L")),
        k3=dict(engine_max_lag_ph=k3["max_lag_ph"], engine_stages_beyond=k3["stages_beyond"],
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
    out["orders"] = {x: ladder(parts, rungs, x) for x in d["order_observables"]}
    out["state_error"] = dict(
        X_L_over_budget=ratio(richardson(parts, declared, half, "X_L"), budget),
        pH_L=richardson(parts, declared, half, "pH_L"))
    transfer = a["conditioned_transfer"]
    out["reference"] = dict(
        X_L_over_budget=ratio(max_abs_difference(eng, ref, "X_L"), budget),
        transfer_over_budget=ratio(max_abs_difference(eng, ref, transfer), budget),
        pH_L_max_abs=max_abs_difference(eng, ref, "pH_L"),
        floor_X_L_over_budget=ratio(max_abs_difference(ref, ref_floor, "X_L"), budget),
        floor_pH_L=max_abs_difference(ref, ref_floor, "pH_L"),
    )
    starts = [eng] + [parts.get(n) for n in rungs if n != declared] + [ctl]
    out["start"] = dict(
        pH_L=max_or_none([row0(p, ref, "pH_L") for p in starts]),
        V_b=max_or_none([row0(p, ref, "V_b") for p in starts]),
        X_L_over_budget=ratio(max_or_none([row0(p, ref, "X_L") for p in starts]), budget))
    out["envelope"] = envelope(parts, list(rungs) + [control])
    tolerance = ((eng or {}).get("ledgers") or {}).get("material_tolerance_fmol") or {}
    protons = list(d["proton_transfers"])
    cargo = list(a["cargo_transfers"])
    out["protons"] = dict(
        lumen_over_tolerance=route_ledger(eng or {}, "Heq_L", protons, sign=1,
                                          tolerance=tolerance.get("H")),
        cytosol_over_tolerance=route_ledger(eng or {}, "Heq_c", protons, sign=-1,
                                            tolerance=tolerance.get("H")))
    out["protons"]["max_over_tolerance"] = max_or_none(list(out["protons"].values()))
    out["energy"] = dict(
        over_flows_at_declared=energy_over_flows(eng or {}),
        ladder=energy_ladder(parts, rungs),
        smallest_route_heat_increment_pJ=heat_increments(eng or {}, a["passive_routes"]))
    out["cargo"] = dict(
        material_over_tolerance=material(parts, [declared]),
        lumen_over_tolerance=route_ledger(eng or {}, "X_L", cargo, sign=1,
                                          tolerance=tolerance.get("X")),
        cytosol_over_tolerance=route_ledger(eng or {}, "X_c", cargo, sign=-1,
                                            tolerance=tolerance.get("X")))
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
            out_of_lumen = at_time(t, moved, w0) - at_time(t, moved, w1)
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


def compare(path_a, path_b, out_json):
    """Two runs' records bit for bit, run times apart (Track R's `differences`)."""
    a = json.loads(Path(path_a).read_text())
    b = json.loads(Path(path_b).read_text())
    parts = {}
    for name in sorted(set(a["parts"]) | set(b["parts"])):
        if name not in a["parts"] or name not in b["parts"]:
            parts[name] = "in one run only"
            continue
        found = differences(a["parts"][name], b["parts"][name])
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
    derived, evaluated = verdict(parts, protocol)
    record = dict(kind=label, protocol_id=protocol["id"], protocol_status=protocol["status"],
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
