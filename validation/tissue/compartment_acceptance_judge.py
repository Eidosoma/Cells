"""fr1-closed-compartment-v1's judge: it reads records and never runs (FR-1, D216).

The protocol is validation/tissue/compartment_acceptance_protocol.json. The judge reads the
generator's records (validation/tissue/compartment_acceptance_qualification: one results.json per
unit), merges the units (each part in exactly one, all from one source: MG0c's form), derives the
metrics below under the protocol's `judge.derivation`, and evaluates its machine criteria
(`judge.criteria`) with MG0c's evaluator (validation/morphogenesis/mg0a_gradient.evaluate: a
missing metric fails its criterion) into OUT_DIR/verdict.json.

**The arithmetic is FR-4's and FR-5's,** imported read-only from validation/tissue/
compartment_ph_judge.py (that judge serves registered protocols and is never edited): the classes
rule for orders with each difference's floor N eps max|q|, the ladder, the Richardson error
(4/3) D(dt, dt/2), max-norm differences on shared records, admission, the merge and its refusals,
and compare. That judge keys records by round(t), integer seconds; FR-1's ladder and reference
parts record every 10 ms, so they reach it with their record times in units of RECORD_UNIT_S
(on_record_grid). The every-step parts (C10, C11) are read record by record here.

The FR-1 derivations, fixed before any run:
* **Budgets** (declared first): B_split, for the items with a splitting error (C4's closed form, C6,
  C7, C8), is 1e-3 of the world's initial S (and P) content, a declared number. The rounding
  budget of an exact item is ROUNDING_FACTOR x N eps max|q| over the run's N steps (FR-4's floor
  times 10); C5 adds its Newton tolerance, N NEWTON_RTOL max|q|.
* **Against the references:** each observable's largest difference over the shared records, in
  its budget.
* **C4's step map:** at every rung, the engine against R-step-map's iterated map in the rounding
  budget; the engine's last-record x = n_c / N against R-step-map's x* in the rounding budget; and
  the splitting term identified: (x/x_eq - 1) over -a(a + 2b) dt^2 / 96, within 1e-3 of 1.
* **Reconciliation (C3):** each loading route's cumulative moved amount against the
  compartment's gain, in the rounding budget.
* **Energy (C10):** C6's summed work against R-energy's change of both nodes' G, over RT B_split
  sum_i max_t |ln c_i| (energy_against_reference); each world's summed route work (and C6's
  clearance work) against the free-energy change of its nodes on the engine's own trajectory,
  G = RT sum n (ln(n/V) - 1) (Appendix A.10, exact SI constants), in ROUNDING_FACTOR x 2N eps
  times the largest size of G's terms, RT sum |n (ln(n/V) - 1)| (each booked change is a
  difference of such terms); C10's RK4 world and C11's rows through their energy ratio
  (|residual| / bound); the IMEX worlds' energy residual over the integrated flows; C11's
  trajectories against R-energy's at rounding (against_by_step).
* **Silence (C9):** S1 bitwise, S2 and S3 at most 1, the owner live, in every program.
* **Comparisons** (C2, C12): the generator's identity and bit-for-bit results, read as 1 or 0; the
  batch within 1e-12 relative of its scalar runs (its bitwise equality to them reported).
* **Plants (C13, K3):** exactly the planted rows flagged and nothing else (plant_verdict,
  planted_rows), each detection margin over its bound reported for its criterion (at least 10).
* **Refusals (C1):** a class passes (1) when its representative is refused with the check the
  protocol names, and its neighbour is admitted and runs.
* **Undefined values are None, never NaN;** a None fails its criterion.

The references part (parts["references"], the FR references agent's, through its adapter) holds
worlds: {name: {record_s, series: {amount_S_cell_0, ...}}} for C3_flux, C3_first_order, C4, C5,
C6, C7 and C8 (each with NAME_floor); step_map: {C4 rung part: {record_s, series, x_star, x_eq}};
and energy: {part: {record_s, dG_pJ, series}} for each C11 part and C6's declared rung.

Usage:
  python -m validation.tissue.compartment_acceptance_judge dev PROTOCOL OUT_DIR RESULTS [...]
  python -m validation.tissue.compartment_acceptance_judge judged PROTOCOL OUT_DIR RESULTS [...]
  python -m validation.tissue.compartment_acceptance_judge compare RESULTS_A RESULTS_B OUT_JSON
"""

import json
import math
import sys
from pathlib import Path

from validation.morphogenesis.mg0a_gradient import evaluate
from validation.tissue import compartment_ph_judge as base

RECORD_UNIT_S = 0.01
EPS = base.EPS
ROUNDING_FACTOR = 10.0
NEWTON_RTOL = 1e-12
RT_PJ_PER_FMOL = 6.02214076e23 * 1.380649e-23 * 310.0 * 1e-3  # N_A k_B T, J/mol to pJ/fmol


def on_record_grid(part):
    """The part with its record times in units of RECORD_UNIT_S (the base arithmetic's keys)."""
    if not isinstance(part, dict) or "record_s" not in part:
        return part
    return dict(part, record_s=[t / RECORD_UNIT_S for t in part["record_s"]])


def flag(value):
    return None if value is None else int(bool(value))


def max_or_none(values):
    return base.max_or_none(list(values))


def completed(part):
    return isinstance(part, dict) and part.get("completed") is True


def rounding(part, name, *, newton=False):
    """ROUNDING_FACTOR x N eps max|q| (plus N NEWTON_RTOL max|q| for a Newton solve), N the
    part's steps, q the observable's series; None without it."""
    s = base.series(part, name) if completed(part) else None
    if s is None:
        return None
    scale = max(abs(v) for v in s)
    steps = max(1, part.get("steps") or 1)
    out = ROUNDING_FACTOR * steps * EPS * scale
    return out + (steps * NEWTON_RTOL * scale if newton else 0.0)


def total_content(part, species=("S", "P")):
    """The world's initial content of the tracked species (fmol), from row 0 of its records."""
    if not completed(part):
        return None
    return sum(v[0] for k, v in part["series"].items()
               if k.startswith("amount_") and k.split("_")[1] in species)


def against(part, reference, observables, budget):
    """The largest of each observable's max-norm difference from the reference over the shared
    records, in `budget` (a number, or a callable of the observable); None when any is missing."""
    g, r = on_record_grid(part), on_record_grid(reference)
    out = []
    for x in observables:
        b = budget(x) if callable(budget) else budget
        out.append(base.ratio(base.max_abs_difference(g, r, x), b))
    return max_or_none(out)


def free_energy(part, j):
    """G at record j of the part's finite nodes (pJ): RT sum n (ln(n/V) - 1), A.10."""
    total = 0.0
    for k, v in part["series"].items():
        if not k.startswith("amount_"):
            continue
        node = k.split("_", 2)[2]
        n = v[j]
        volume = part["volumes_pL"][node]
        if n <= 0:
            return None
        total += n * (math.log(n / volume) - 1.0)
    return RT_PJ_PER_FMOL * total


def free_energy_terms(part, j):
    """RT sum |n (ln(n/V) - 1)| at record j (pJ): the size of the terms G is made of, the scale
    of each booked change's rounding (a change of G is a difference of such terms)."""
    total = 0.0
    for k, v in part["series"].items():
        if k.startswith("amount_"):
            n, volume = v[j], part["volumes_pL"][k.split("_", 2)[2]]
            total += abs(n * (math.log(n / volume) - 1.0)) if n > 0 else 0.0
    return RT_PJ_PER_FMOL * total


def energy_closure(part, *, with_clearance=False):
    """|summed route work (+ clearance work) - (G(t) - G(0))| over ROUNDING_FACTOR x 2N eps times
    the largest size of G's terms over the run (free_energy_terms: N steps of two half-steps, each
    booking exact changes of those terms), the largest over the records; None for an incomplete
    part."""
    if not completed(part):
        return None
    s, routes = part["series"], part.get("routes", [])
    g0, steps = free_energy(part, 0), max(1, part.get("steps") or 1)
    if g0 is None:
        return None
    records = range(len(part["record_s"]))
    bound = ROUNDING_FACTOR * 2 * steps * EPS * max(free_energy_terms(part, j) for j in records)
    worst = 0.0
    for j in records:
        work = sum(s[f"work_{r}_pJ"][j] for r in routes)
        if with_clearance:
            work += sum(v[j] for k, v in s.items() if k.startswith("cleared_work_"))
        g = free_energy(part, j)
        if g is None:
            return None
        error = abs(work - (g - g0))
        if error == 0.0:
            continue
        if bound == 0.0:
            return None
        worst = max(worst, error / bound)
    return worst


def energy_against_reference(part, reference, budget_fraction):
    """C10 for C6: the summed route and clearance work against R-energy's change of both nodes' G
    (dG_pJ), over RT x B_split x sum_i max_t |ln c_i| (B_split carried through dG/dn_i =
    RT ln c_i), the largest over the shared records; None without either side."""
    if not completed(part) or not reference or "dG_pJ" not in reference:
        return None
    s, routes = part["series"], part.get("routes", [])
    keys = {round(t / RECORD_UNIT_S): j for j, t in enumerate(part["record_s"])}
    content = total_content(part)
    logs = 0.0
    for k, v in s.items():
        if k.startswith("amount_S_"):
            volume = part["volumes_pL"][k.split("_", 2)[2]]
            logs += max(abs(math.log(n / volume)) for n in v)
    budget = RT_PJ_PER_FMOL * budget_fraction * content * logs
    worst = None
    for t, g in zip(reference["record_s"], reference["dG_pJ"], strict=True):
        j = keys.get(round(t / RECORD_UNIT_S))
        if j is None:
            continue
        work = sum(s[f"work_{r}_pJ"][j] for r in routes)
        work += sum(v[j] for k, v in s.items() if k.startswith("cleared_work_"))
        ratio = abs(work - g) / budget
        worst = ratio if worst is None else max(worst, ratio)
    return worst


def reconciliation(part, route, node):
    """|moved_ROUTE(t) - (n_node(t) - n_node(0))| over the rounding budget of the node's S."""
    if not completed(part):
        return None
    s = part["series"]
    moved, n = s.get(f"moved_{route}_fmol"), s.get(f"amount_S_{node}")
    budget = rounding(part, f"amount_S_{node}")
    if moved is None or n is None or not budget:
        return None
    return max(abs(m - (x - n[0])) for m, x in zip(moved, n, strict=True)) / budget


def ratio_max(part, name):
    if not completed(part):
        return None
    s = part["series"].get(f"ratio_{name}")
    return max(s) if s else None


def step_map(part, reference, a, b, dt):
    """C4 at one rung: the engine against R-step-map at rounding; its last x against x*; and the
    splitting term's ratio to -a(a + 2b) dt^2 / 96."""
    out = dict(map=None, x_star=None, splitting_ratio=None)
    if not completed(part) or not reference:
        return out
    budget = max(rounding(part, "amount_S_cell_0") or 0, rounding(part, "amount_S_ecs_0") or 0)
    out["map"] = against(part, reference, ["amount_S_cell_0", "amount_S_ecs_0"], budget or None)
    s = part["series"]
    total = s["amount_S_cell_0"][-1] + s["amount_S_ecs_0"][-1]
    x = s["amount_S_cell_0"][-1] / total
    x_star, x_eq = reference.get("x_star"), reference.get("x_eq")
    if x_star is None or x_eq is None:
        return out
    out["x_star"] = abs(x - x_star) * total / budget if budget else None
    out["splitting_ratio"] = (x / x_eq - 1.0) / (-a * (a + 2 * b) * dt * dt / 96.0)
    return out


def against_by_step(part, reference, observables):
    """An every-step part against its reference record by record (both recorded at every step,
    so keyed by index), each observable over its rounding budget; None when either is missing or
    their record times differ (by more than 1e-12 s)."""
    if not completed(part) or not reference:
        return None
    times = reference.get("record_s") or []
    if len(times) != len(part["record_s"]) or any(
            abs(a - b) > 1e-12 for a, b in zip(times, part["record_s"], strict=True)):
        return None
    out = []
    for x in observables:
        a, b = base.series(part, x), (reference.get("series") or {}).get(x)
        budget = rounding(part, x)
        if a is None or b is None or not budget:
            return None
        out.append(max(abs(u - v) for u, v in zip(a, b, strict=True)) / budget)
    return max_or_none(out)


def plant_verdict(bundle, ledger, passing):
    """C13: exactly the planted row flagged. Every unplanted row before the plant within every
    bound, the planted row refused by the engine naming the plant's ledger, the `passing`
    ledgers within their bounds there; and the detection margin, the planted row's ratio of the
    plant's ledger to its bound. None without the bundle."""
    if not bundle or "engine" not in bundle:
        return dict(exact=None, margin=None)
    clean = all(v <= 1.0 for v in bundle["prefix_max_ratio"].values())
    engine = bundle["engine"]
    named = bool(engine.get("refused")) and (
        "accounting failed: " + ledger) in (engine.get("message") or "")
    ratios = bundle["planted_ratios"]
    others = all(ratios.get(name, math.inf) <= 1.0 for name in passing)
    return dict(exact=int(clean and named and others), margin=ratios.get(ledger))


def planted_rows(bundle, first):
    """K3: exactly the planted rows flagged, rows from `first` on (S1 broken where the plant can
    act, S2 above 1), none before; and the smallest S2 ratio over the planted rows."""
    if not bundle or "s2_rows" not in bundle:
        return dict(exact=None, margin=None)
    s1, s2 = bundle["s1_rows"], bundle["s2_rows"]
    before = all(s1[k] and s2[k] <= 1.0 for k in range(first))
    planted = all(s2[k] > 1.0 for k in range(first, len(s2)))
    if bundle["plant"]["kind"] == "route":
        planted = planted and not any(s1[first:])
    return dict(exact=int(before and planted and len(s2) > first),
                margin=min(s2[first:]) if len(s2) > first else None)


def refusal_class(rows, expected):
    if not rows:
        return None
    refused = all(r["refused"] and r["check"] == expected for r in rows["refused"])
    admitted = all(r["admitted"] and r["ran"] is True for r in rows["admitted"])
    return int(refused and admitted)


def silence(programs):
    if not programs:
        return dict(s1=None, s2=None, s3=None, live=None)
    found = [v for k, v in programs.items() if k != "S4_reported" and isinstance(v, dict)]
    if not found:
        return dict(s1=None, s2=None, s3=None, live=None)
    return dict(
        s1=int(all(f["s1"] for f in found)),
        s2=max(f["s2"] for f in found), s3=max(f["s3"] for f in found),
        live=int(all(f["owner_ions_moved"] and f["max_phi_owner"] >= 0.05 for f in found)))


def derive(parts, protocol):
    """The protocol's derived metrics (module docstring)."""
    d = protocol["judge"]["derivation"]
    refs = (parts.get("references") or {}).get("worlds", {})
    maps = (parts.get("references") or {}).get("step_map", {})
    out = dict(admission=base.admission(parts, d["run_parts"]))
    # C3 and C5: exact against R-closed at rounding; C3's reconciliation.
    out["C3"] = {}
    for name in d["C3"]["parts"]:
        part = parts.get(name)
        out["C3"][name] = dict(
            reference=against(part, refs.get(name), d["observables"],
                              lambda x, p=part: rounding(p, x)),
            reconciliation=reconciliation(part, d["C3"]["route"], d["C3"]["node"]))
    out["C3"]["max"] = max_or_none(v for k, part in out["C3"].items() for v in part.values())
    c5 = parts.get(d["C5"]["part"])
    out["C5"] = dict(reference=against(c5, refs.get("C5"), d["observables"],
                                       lambda x: rounding(c5, x, newton=True)))
    # C4, C6, C7, C8: orders, Richardson and the reference against B_split.
    g = {name: on_record_grid(part) for name, part in parts.items()}
    out["orders"], out["state_error"], out["reference"], out["budgets"] = {}, {}, {}, {}
    for item in ("C4", "C6", "C7", "C8"):
        w = d[item]
        declared, half = w["ladder_parts"][0], w["ladder_parts"][1]
        content = total_content(parts.get(declared))
        budget = None if content is None else d["split_fraction"] * content
        out["budgets"][item] = budget
        for x in w["observables"]:
            out["orders"][f"{item}_{x}"] = base.ladder(g, w["ladder_parts"], x, d["band"])
            out["state_error"][f"{item}_{x}"] = base.ratio(base.richardson(g, declared, half, x),
                                                           budget)
        out["reference"][item] = against(parts.get(declared), refs.get(item), w["observables"],
                                         budget)
    out["state_error"]["max"] = max_or_none(
        v for k, v in out["state_error"].items() if k != "max")
    out["reference"]["max"] = max_or_none(v for k, v in out["reference"].items() if k != "max")
    w6 = d["C6"]
    out["C6_cleared"] = against(parts.get(w6["ladder_parts"][0]), refs.get("C6"),
                                [w6["cleared"]], out["budgets"]["C6"])
    # C4's step map at every rung.
    w4 = d["C4"]
    out["C4_map"] = {name: step_map(parts.get(name), maps.get(name), w4["a"], w4["b"], dt)
                     for name, dt in zip(w4["ladder_parts"], w4["dt_s"], strict=True)}
    for key in ("map", "x_star"):
        out["C4_map"][f"{key}_max"] = max_or_none(v[key] for k, v in out["C4_map"].items()
                                                  if isinstance(v, dict) and "map" in v)
    out["C4_map"]["splitting_worst"] = max_or_none(
        None if v["splitting_ratio"] is None else abs(v["splitting_ratio"] - 1.0)
        for k, v in out["C4_map"].items() if isinstance(v, dict) and "map" in v)
    # C9: silence.
    out["C9"] = silence((parts.get("C9_silence") or {}).get("programs"))
    # C10 and C11: energy.
    clearance = set(d["C10"]["clearance"])
    out["C10"] = {name: energy_closure(parts.get(name), with_clearance=name in clearance)
                  for name in d["C10"]["closure_parts"]}
    out["C10"]["closure_max"] = max_or_none(v for k, v in out["C10"].items())
    out["C10"]["rk4_energy"] = ratio_max(parts.get(d["C10"]["rk4_part"]), "energy")
    out["C10"]["imex_over_flows"] = max_or_none(
        base.energy_over_flows(parts.get(name) or {}) for name in d["C10"]["imex_parts"])
    energy_refs = (parts.get("references") or {}).get("energy", {})
    out["C10"]["C6_reference"] = energy_against_reference(
        parts.get(d["C10"]["c6_part"]), energy_refs.get(d["C10"]["c6_part"]), d["split_fraction"])
    out["C11"] = {name: ratio_max(parts.get(name), "energy") for name in d["C11"]["parts"]}
    out["C11"]["max"] = max_or_none(v for v in out["C11"].values())
    out["C11_trajectory"] = {name: against_by_step(parts.get(name), energy_refs.get(name),
                                                   d["observables"])
                             for name in d["C11"]["parts"]}
    out["C11_trajectory"]["max"] = max_or_none(
        v for k, v in out["C11_trajectory"].items() if k != "max")
    out["ledgers"] = max_or_none(
        ratio_max(parts.get(name), ledger) for name in d["ledger_parts"]
        for ledger in d["material_ledgers"])
    # C12: restart and batch.
    restart = parts.get("C12_restart") or {}
    restarts = restart.get("restarts") or {}
    out["C12_restart"] = (int(len(restarts) == d["C12"]["restarts"]
                              and all(r["equal"] for r in restarts.values()))
                          if completed(restart) else None)
    batch = (parts.get("C12_batch") or {}).get("worlds") or {}
    out["C12_batch_relative"] = (max_or_none(w["scalar_relative"] for w in batch.values())
                                 if len(batch) == d["C12"]["worlds"] else None)
    out["C12_batch_reversed"] = (int(all(w["reversed_equal"] and w["final_reversed_equal"]
                                         for w in batch.values()))
                                 if len(batch) == d["C12"]["worlds"] else None)
    # C1 and C2.
    classes = (parts.get("C1_refusals") or {}).get("classes", {})
    out["C1"] = {cls: refusal_class(classes.get(cls), check)
                 for cls, check in d["C1"]["checks"].items()}
    out["C1"]["all"] = (None if any(v is None for v in out["C1"].values())
                        else int(all(out["C1"].values())))
    pairs = (parts.get("C2_identity") or {}).get("pairs")
    out["C2"] = (int(len(pairs) == d["C2"]["pairs"] and all(v == [] for v in pairs.values()))
                 if pairs else None)
    # C13 and K3: the planted controls, each in its own process.
    plants = (parts.get("C13_controls") or {}).get("plants") or {}
    out["C13"] = dict(move=plant_verdict(plants.get("move"), "outside", ["local"]),
                      work=plant_verdict(plants.get("work"), "energy", d["material_ledgers"]))
    k3 = (parts.get("K3_planted") or {}).get("plants") or {}
    out["K3"] = dict(route=planted_rows(k3.get("route"), 1),
                     anchor=planted_rows(k3.get("anchor"), 0))
    out["C12_batch_scalar_bitwise"] = (
        int(all(w["scalar_relative"] == 0.0 for w in batch.values()))
        if len(batch) == d["C12"]["worlds"] else None)
    # The controls.
    out["controls"] = dict(
        K1_over_budget=against(parts.get("K1_one_way"), refs.get("C4"), w4["observables"],
                               out["budgets"]["C4"]),
        K2_over_budget=against(parts.get("K2_no_clearance"), refs.get("C6"), w6["observables"],
                               out["budgets"]["C6"]),
        K4_moved_change_differs=(flag(not (restart.get("planted") or {}).get("equal", True))
                                 if completed(restart) and restart.get("planted") else None))
    return out


def verdict(parts, protocol):
    derived = derive(parts, protocol)
    evaluated = evaluate(dict(criteria=protocol["judge"]["criteria"]),
                         dict(parts=parts, derived=derived))
    return derived, evaluated


def main(argv):
    if argv and argv[0] == "compare":
        return base.compare(*argv[1:])
    if len(argv) < 4 or argv[0] not in ("dev", "judged"):
        raise SystemExit(__doc__)
    mode, protocol_path, out_dir, paths = argv[0], argv[1], Path(argv[2]), argv[3:]
    protocol = json.loads(Path(protocol_path).read_text())
    results_list = [(p, json.loads(Path(p).read_text())) for p in paths]
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
