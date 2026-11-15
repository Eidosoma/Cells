"""The judge of the coupling operator's qualification protocol: it reads records and never runs.

docs/INVENTORY_COUPLING_DESIGN.md §10. The judge reads a generator run's results.json
(validation/tissue/regulated_availability_dt_study: records only) and the protocol
(validation/tissue/regulated_availability_protocol.json). It derives the observed orders under the
protocol's resolution rule and evaluates the protocol's criteria with MG0c's evaluator
(validation/morphogenesis/mg0a_gradient.evaluate), into OUT/verdict.json. It imports nothing from
the generator.

Derived metrics, at `derived.<world>.<arm>.<observable>`:
* `errors`: the largest |engine - reference| over the records at each dt of the ladder;
* `pairs`: for each successive pair, the order log2(e(dt) / e(dt/2)) and whether it is resolved:
  the finer error at least `floor_factor` times the arm's floor, and at least the observable's
  rounding scale (`rounding`: an absolute value, or "steps_eps_max": N eps max|X|, N the finer
  dt's steps, for a running sum);
* `resolved`: the number of resolved pairs; `in_band`: 1 when every resolved pair's order lies in
  the band, else 0; `max_error`: the largest error over the ladder; `at_first_dt`: the error at
  the ladder's first dt.
Also `derived.<world>.<arm>.gates_held` (1 when every run kept every contact gate at 1) and
`row0_max` (the largest |V| difference of row 0 from the reference's start).
A control, at `derived.controls.<control>.caught`, is 1 when on its records some observable its
arm judges has a resolved pair out of the band.

Usage:
  python -m validation.tissue.regulated_availability_judge dev PROTOCOL RESULTS OUT_DIR
  python -m validation.tissue.regulated_availability_judge judged PROTOCOL RESULTS OUT_DIR
A judged verdict is refused unless the protocol is registered, the results are a complete judged
run of it from a clean execution snapshot, and OUT_DIR is new.
"""

import hashlib
import json
import math
import sys
from pathlib import Path

from validation.morphogenesis.mg0a_gradient import evaluate

EPS = 2.0**-52


def rounding_scale(rule, observable, magnitude, steps):
    value = rule.get(observable, 0.0)
    if value == "steps_eps_max":
        return steps * EPS * magnitude
    return float(value)


def derive_arm(arm, protocol, judged):
    """The derived metrics of one arm's records (module docstring)."""
    band = protocol["band"]
    rule = protocol["resolution"]
    runs = arm["runs"]
    out = dict(
        gates_held=int(all(r["gate_held_at_1"] for r in runs)),
        row0_max=max(r["row0_V_difference"] for r in runs),
    )
    for x in protocol["observables"]:
        errors = [max(r["errors"][x]) for r in runs]
        pairs = []
        for i in range(len(runs) - 1):
            coarse, fine = errors[i], errors[i + 1]
            needed = max(
                rule["floor_factor"] * arm["floor"].get(x, 0.0),
                rounding_scale(rule["rounding"], x, arm["magnitudes"][x], runs[i + 1]["steps"]),
            )
            resolved = fine > 0 and fine >= needed
            order = math.log2(coarse / fine) if coarse > 0 and fine > 0 else None
            in_band = order is not None and band[0] <= order <= band[1]
            pairs.append(
                dict(
                    dt=runs[i]["dt"],
                    order=order,
                    resolved=bool(resolved),
                    in_band=bool(in_band),
                    needed=needed,
                )
            )
        resolved = [p for p in pairs if p["resolved"]]
        out[x] = dict(
            errors=errors,
            pairs=pairs,
            resolved=len(resolved),
            in_band=int(all(p["in_band"] for p in resolved)),
            max_error=max(errors),
            at_first_dt=errors[0],
            judged=x in judged,
        )
    return out


def derive(results, protocol):
    parts = results["parts"]
    derived = {}
    for key, judged in protocol["judged_observables"].items():
        world, arm = key.split(".")
        if world in parts:
            derived.setdefault(world, {})[arm] = derive_arm(parts[world][arm], protocol, judged)
    if "controls" in parts:
        derived["controls"] = {}
        for name, arm_key in protocol["control_arms"].items():
            judged = protocol["judged_observables"][arm_key]
            metrics = derive_arm(parts["controls"][name], protocol, judged)
            caught = any(metrics[x]["in_band"] == 0 for x in judged)
            derived["controls"][name] = dict(
                caught=int(caught),
                arm=arm_key,
                orders={x: [p["order"] for p in metrics[x]["pairs"]] for x in judged},
                resolved={x: metrics[x]["resolved"] for x in judged},
                delta=parts["controls"][name].get("delta"),
            )
    return derived


def verdict(results, protocol):
    derived = derive(results, protocol)
    evaluated = evaluate(protocol, dict(parts=results["parts"], derived=derived))
    return derived, evaluated


def refusal(protocol, results, out_dir):
    status = protocol.get("status")
    if not (isinstance(status, str) and status.lower().startswith("registered")):
        return "the protocol is not registered (its status does not begin 'registered')"
    record = protocol.get("registration")
    if not (isinstance(record, dict) and record.get("status") == status):
        return "the protocol's registration record is missing or does not match its status"
    if results.get("status") != "Judged run of " + protocol["id"]:
        return "the results are not a judged run of this protocol"
    source = results.get("source", {})
    clean = source.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if source.get("kind") != "snapshot" or source.get("status") != "complete" or not clean:
        return "the judged run did not come from a clean, complete execution snapshot"
    if not results.get("complete") or sorted(results["parts"]) != sorted(protocol["judged_parts"]):
        return "the judged run is incomplete (an infrastructure ending: rerun it once)"
    if Path(out_dir).exists():
        return "the output directory exists (each attempt writes its own)"
    return None


def main(argv):
    mode, protocol_path, results_path, out_dir = argv
    protocol = json.loads(Path(protocol_path).read_text())
    results = json.loads(Path(results_path).read_text())
    if mode == "judged":
        why = refusal(protocol, results, out_dir)
        if why:
            raise SystemExit("Refused: " + why)
        label = "Judged verdict"
    elif mode == "dev":
        if Path(out_dir).exists():
            raise SystemExit("Refused: the output directory exists")
        label = "Development verdict (not a judgement: the protocol is not registered)"
    else:
        raise SystemExit("Usage: dev|judged PROTOCOL RESULTS OUT_DIR")
    derived, evaluated = verdict(results, protocol)
    record = dict(
        kind=label,
        protocol_id=protocol["id"],
        protocol_status=protocol["status"],
        results=str(results_path),
        results_status=results.get("status"),
        source=results.get("source"),
        passed=evaluated["passed"],
        criteria=evaluated["criteria"],
        derived=derived,
    )
    Path(out_dir).mkdir(parents=True)
    (Path(out_dir) / "verdict.json").write_text(json.dumps(record, indent=1) + "\n")
    failed = [c["id"] for c in evaluated["criteria"] if c["judged"] and not c["passed"]]
    print(label, "passed" if evaluated["passed"] else f"FAILED: {failed}")
    return record


if __name__ == "__main__":
    main(sys.argv[1:])
