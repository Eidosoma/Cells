"""fr6-a5pp-v1's judge: it reads records and never runs (FR-6 A5'', D216).

The protocol is validation/tissue/a5pp_acceptance_protocol.json. The judge reads the generator's
records (validation/tissue/a5pp_acceptance_qualification: one results.json per unit), merges the
units (each part in exactly one, all from one source: MG0c's form, FR-4's and FR-5's merge and
refusal imported read-only from validation/tissue/compartment_ph_judge.py), derives the metrics
below under the protocol's `judge.derivation`, and evaluates its machine criteria with MG0c's
evaluator into OUT_DIR/verdict.json. Records align on integer milliseconds.

**The orders are A5's, by the coupling protocol's own arithmetic,** imported read-only from
validation/tissue/regulated_availability_judge.derive_arm (that judge serves a registered protocol
and is never edited): each rung's error is the largest |engine - reference| over the records and
the cells (and the species, for the amounts); a pair of successive rungs is resolved when its finer
error is at least floor_factor x the reference's floor and its rounding scale; every resolved
pair's order log2(e(dt)/e(dt/2)) in the band; the resolved count reported beside it (the lead's
ruling 5).

The FR-6 derivations, fixed before any comparison (the lead's rulings of 18 November 2026):
* **Start:** row 0's largest relative difference from the references' row 0 (V, the amounts, s).
* **Controls** (ruling 1): a control's departure is the largest |control - reference| over the
  records and cells at one rung (R-cell's registered world as the reference); the honest error is
  the registered world's own at that rung; the ratio departure / honest, per observable and rung.
  The prior, bypass and rate controls are judged in V and the amounts on all four rungs; the basal
  control as the protocol's derivation lists (`basal`).
* **delta** (ruling 2, reported in a development verdict): the coupling protocol's rule, the delta
  whose basal control's V departure plateaus at 10 x the finest rung's honest V error, from the
  development run's basal control at its own delta (the departure linear in delta), rounded up on a
  1-2-5 grid.
* **The state budget** (ruling 1, reported only): each rung's error over B(dt) = B(1 ms) x
  (dt / 1 ms)^2, derived from the references' stand-in.
* **Undefined values are None, never NaN;** a None fails its criterion.

Usage:
  python -m validation.tissue.a5pp_acceptance_judge dev PROTOCOL OUT_DIR RESULTS [...]
  python -m validation.tissue.a5pp_acceptance_judge judged PROTOCOL OUT_DIR RESULTS [...]
  python -m validation.tissue.a5pp_acceptance_judge compare RESULTS_A RESULTS_B OUT_JSON
"""

import json
import math
import sys
from pathlib import Path

from validation import id_table
from validation.morphogenesis.mg0a_gradient import evaluate
from validation.tissue import compartment_ph_judge as base
from validation.tissue import judge_harness as harness
from validation.tissue import regulated_availability_judge as coupling

# The code-blind references' registered inputs and world (a5pp_acceptance_fixtures' INPUTS and
# WORLD_ID), read directly: the judge reads records and registered files only.
INPUTS = (Path(__file__).resolve().parents[2] / "validation" / "fr6" / "references"
          / "reference_inputs.json")
WORLD = "a5pp_prior"

SPECIES = ("Na", "K", "Cl")


def completed(part):
    return isinstance(part, dict) and part.get("completed") is True


def names(observable, cells):
    if observable == "amounts":
        return [f"amount_{c}_{s}" for c in cells for s in SPECIES]
    return [f"{observable}_{c}" for c in cells]


def by_ms(part, name):
    if not isinstance(part, dict) or name not in (part.get("series") or {}):
        return None
    return dict(zip(part["record_ms"], part["series"][name], strict=True))


def record_errors(part, reference, observable):
    """[record] the largest |part - reference| over the observable's cells (and species), on the
    shared records from the first step on (row 0 is the start criterion's); None if missing."""
    if not completed(part) or not reference:
        return None
    series = [(by_ms(part, n), by_ms(reference, n)) for n in names(observable,
                                                                    reference["cells"])]
    if any(a is None or b is None for a, b in series):
        return None
    shared = sorted(set(series[0][0]) & set(series[0][1]) - {0})
    if not shared:
        return None
    out = []
    for t in shared:
        values = [(a[t], b[t]) for a, b in series]
        if any(x is None or y is None for x, y in values):
            return None
        out.append(max(abs(x - y) for x, y in values))
    return out


def magnitude(reference, observable):
    return max(abs(v) for n in names(observable, reference["cells"])
               for v in reference["series"][n])


def row0(part, reference):
    """Row 0's largest relative difference from the references' row 0 (V, the amounts, s)."""
    if not completed(part) or not reference:
        return None
    worst = 0.0
    for x in ("V", "amounts", "s"):
        for n in names(x, reference["cells"]):
            a, b = by_ms(part, n).get(0), by_ms(reference, n).get(0)
            if a is None or b is None:
                return None
            worst = max(worst, abs(a - b) / max(abs(b), 1e-300))
    return worst


def arm_of(runs, reference, d):
    """The coupling judge's arm (derive_arm's input) from the engine runs in ladder order."""
    floor = reference["floor"]
    out = dict(runs=[], floor={x: floor.get(x, 0.0) for x in d["observables"]},
               magnitudes={x: magnitude(reference, x) for x in d["observables"]})
    for run in runs:
        errors = {x: record_errors(run, reference, x) for x in d["observables"]}
        if any(v is None for v in errors.values()):
            return None
        out["runs"].append(dict(errors=errors, steps=run["steps"], dt=run["dt_s"],
                                gate_held_at_1=True, row0_V_difference=0.0))
    return out


def max_error(run, reference, observable):
    errors = record_errors(run, reference, observable)
    return None if errors is None else max(errors)


def ratio(a, b):
    return None if a is None or b is None or b <= 0 else a / b


def round_up_125(x):
    """The smallest value of the 1-2-5 grid at or above x."""
    if not x or x <= 0:
        return None
    exponent = math.floor(math.log10(x))
    for k in (exponent, exponent + 1):
        for m in (1.0, 2.0, 5.0):
            value = m * 10.0**k
            if value >= x * (1 - 1e-12):
                return value
    return None


def derive(parts, protocol):
    d = protocol["judge"]["derivation"]
    ref = parts.get("references") or {}
    reference = ref if completed(ref) else None
    out = dict(admission=base.admission(parts, d["run_parts"]))
    rungs = [parts.get(n) for n in d["rung_parts"]]
    out["ids"] = (None if not all(completed(r) for r in rungs) else
                  int(all(set(r.get("ids") or []) <= set(d["engine_ids"]) for r in rungs)))
    out["start"] = max((row0(r, reference) for r in rungs), default=None) if all(
        row0(r, reference) is not None for r in rungs) else None
    arm = arm_of(rungs, reference, d) if reference else None
    rules = dict(band=d["band"], resolution=d["resolution"], observables=d["observables"])
    orders = coupling.derive_arm(arm, rules, d["judged_observables"]) if arm else {}
    out["orders"] = {x: orders.get(x) for x in d["observables"]}
    for x in d["judged_observables"]:
        o = orders.get(x) or {}
        out["orders"][f"{x}_in_band"] = o.get("in_band")
        out["orders"][f"{x}_resolved"] = o.get("resolved")
    honest = {x: [max_error(r, reference, x) for r in rungs] for x in d["observables"]}
    out["honest"] = honest
    out["controls"] = {}
    for name, judged in d["controls"].items():
        runs = (parts.get(name) or {}).get("runs") or {}
        each = {}
        for k, key in enumerate(d["rung_keys"]):
            run = runs.get(key)
            each[key] = {x: ratio(max_error(run, reference, x), honest[x][k])
                         for x in ("V", "amounts")}
        judged_values = [each[key][x] for key, xs in judged.items() for x in xs]
        out["controls"][name] = dict(
            rungs=each, min=None if not judged_values or any(v is None for v in judged_values)
            else min(judged_values))
    # K_basal_rule's own detection (the coupling protocol's): a resolved pair of a judged
    # observable outside the band, on its own records against the same reference.
    basal = parts.get("K_basal_rule") or {}
    basal_runs = [(basal.get("runs") or {}).get(key) for key in d["rung_keys"]]
    basal_arm = arm_of(basal_runs, reference, d) if reference and all(
        completed(r) for r in basal_runs) else None
    detection = (coupling.derive_arm(basal_arm, rules, d["judged_observables"])
                 if basal_arm else None)
    out["basal_rule_detection"] = None if detection is None else dict(
        caught=int(any(not p["in_band"] for x in d["judged_observables"]
                       for p in detection[x]["pairs"] if p["resolved"])),
        pairs={x: detection[x]["pairs"] for x in d["judged_observables"]})
    delta_dev = basal.get("delta")
    finest = d["rung_keys"][-1]
    departure = max_error((basal.get("runs") or {}).get(finest), reference, "V")
    sensitivity = None if departure is None or not delta_dev else departure / delta_dev
    rule = (None if sensitivity is None or honest["V"][-1] is None
            else 10.0 * honest["V"][-1] / sensitivity)
    out["delta_rule"] = dict(at_delta=delta_dev, finest_departure_V=departure,
                             sensitivity_V_per_delta=sensitivity, rule_delta=rule,
                             registered_value=round_up_125(rule))
    budget = d["state_budget"]
    out["state_budget_reported"] = {
        x: [ratio(e, budget[x] * (dt / 1e-3) ** 2) for e, dt in zip(honest[x], d["ladder_dt_s"],
                                                                     strict=True)]
        for x in ("V", "amounts")}
    return out


def verdict(parts, protocol):
    derived = derive(parts, protocol)
    evaluated = evaluate(dict(criteria=protocol["judge"]["criteria"]),
                         dict(parts=parts, derived=derived))
    return derived, evaluated


def incomplete(parts, protocol):
    """The harness's completeness check (judge_harness, the external review's finding 4). Every
    rung part, every control's run at each rung and the references must hold the registered
    world's full record grid: the code-blind references' record_times_s, in the derivation's
    record units."""
    d = protocol["judge"]["derivation"]
    world = json.loads(INPUTS.read_text())["worlds"][WORLD]
    registered = [int(round(t / d["record_unit_s"])) for t in world["record_times_s"]]
    problems = []
    for name in (*d["rung_parts"], "references"):
        problems += harness.grid(name, (parts.get(name) or {}).get("record_ms"), registered)
    for name in d["controls"]:
        runs = (parts.get(name) or {}).get("runs") or {}
        for key in d["rung_keys"]:
            problems += harness.grid(f"{name}/{key}", (runs.get(key) or {}).get("record_ms"),
                                     registered)
    return problems


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
