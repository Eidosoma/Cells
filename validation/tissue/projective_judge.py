"""Evaluate the pre-registered projective-mode criteria (protocol projective-c-qualification-v1).

Reads a qualification directory's saved driver results (validation/tissue/
projective_study.py --protocol: <case>-projective.json, <case>-reference.json,
<case>-reference-rates.npz, or their -failure.json) and the burst-growth check
(spectrum/spectrum.json from validation/tissue/projective_spectrum.py), and
evaluates every criterion exactly as validation/tissue/protocols/
projective_c_qualification_v1.json states it, with the readings of amendment 1
(fallback fine rows, transient end, switch times) and amendment 2 (F2's switch
onset, Q2's 5-cell fallback); nothing is re-run. Errors, allowances and caps
are recomputed here from the two runs' saved error coordinates and the saved
jump, rejection and fallback logs.

A case's projective run is paired with the reference run whose fine definition
(the same definition without execution.projective) has the same digest, so
cases with one fine definition (Q1, Q1L) share a reference.

Each criterion gets its protocol text, the values used, the bound, and "pass",
"fail" or "not evaluable" (with the reason); "reported" items carry values
only. The verdict is "pass" when every judged criterion of every case passes,
"fail" when any fails, otherwise "incomplete" (for example while F2, the second
step, has not run).

Usage: python -m validation.tissue.projective_judge RESULTS_DIR [--output FILE]
(default RESULTS_DIR/judgement.json; never overwritten).
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

PROTOCOL = Path(__file__).resolve().parent / "protocols" / "projective_c_qualification_v1.json"
COORDINATES = ("concentration_mM", "membrane_voltage_V", "gate")
S = 2.0  # criteria.accuracy: S = 2.
FLOOR = 1e-9  # criteria.accuracy: floor_q = 1e-9 (mM, V, fraction).
VOLTAGE_CAP_V = 20e-6  # criteria.absolute_caps: |dVm| <= 20 uV.
CONCENTRATION_CAP = 2e-4  # criteria.absolute_caps: |dc|/c <= 2e-4.
GROWTH_CAP = 0.1  # projective_parameters.burst_basis: "below the pre-registered 0.1".
FALLBACK_REASONS = frozenset(  # criteria.fallback, by the runner's reason names.
    {
        "voltage_rate",
        "gate_distance",
        "error_estimate",
        "event_in_slope_rows",
        "correction",
        "a_posteriori_estimate",
    }
)
CUE_WINDOW_S = 10.0  # criteria.fallback: within 10 s after the cue.
RESUME_WINDOW_S = 120.0  # criteria.fallback: jumps resume within 120 s.
H_BELOW_V, D_ABOVE_V = -0.060, -0.035  # near_fold_accuracy (a): branches.
SWITCH_SHARE = 0.05  # near_fold_accuracy (b): 5 % of the fine lingering time.
PHASES = {  # criteria.speedup: Q1, Q1L phases.
    "Q1-relax-pair": [(10.0, 600.0), (600.0, 1800.0)],
    "Q1L-relax-pair-loose": [(10.0, 600.0), (600.0, 1800.0)],
}
FALLBACK_CASES = ("F1-cue-in-window", "F2-near-fold")
NEAR_FOLD = "F2-near-fold"
Q2, Q2_FIVE = "Q2-relax-world", "Q2-relax-world-5cell"  # amendment 2: Q2's fallback run.


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(results, name):
    """(data, path, failed) of a saved part, or (None, None, None) if absent."""
    for suffix, failed in (("", False), ("-failure", True)):
        path = results / f"{name}{suffix}.json"
        if path.exists():
            return json.loads(path.read_text()), path, failed
    return None, None, None


def _changes(definition):
    """Scheduled input-change times (s) of a definition's experiment, after t = 0."""
    times = set()
    for key, value in definition["experiment"].items():
        if key.endswith("_controls"):
            for group in value:
                times.update(c["time"] for c in group["schedule"] if c["time"] > 0)
    return sorted(times)


def _cue_onset(definition):
    """The first scheduled change after t = 0 (F1: the cue channel switched on)."""
    changes = _changes(definition)
    return changes[0] if changes else None


def f2_onset(rates, window_start, threshold):
    """Amendment 2: the first reference row at or after the window start above the
    voltage-rate threshold (None if none: the F2 fallback criterion then fails)."""
    times, rate = rates["times_s"], rates["max_abs_dvm_dt_V_per_s"]
    hits = np.flatnonzero((times >= window_start) & (rate > threshold))
    return float(times[hits[0]]) if len(hits) else None


def _refused_on_global_charge(entry):
    """Whether a judged case entry failed because a run was refused on global charge."""
    return entry["outcome"] == "fail" and any(
        "global_charge" in str(c.get("reason", "")) for c in entry["criteria"]
    )


def _effort(jump):
    """criteria.accuracy: max(estimate_normalized, a_posteriori_normalized) of a jump."""
    return max(float(jump["estimate_normalized"]), float(jump.get("a_posteriori_normalized", 0.0)))


def accuracy_table(projective, reference, *, after=None):
    """Per observation: error, allowance and ratio per class (criteria.accuracy).

    after: count only jumps ending after this time and observations from it on
    (near_fold_accuracy (c)).
    """
    tolerance = projective["definition"]["execution"]["projective"]["tolerance"]
    jumps = projective["report"]["jump_log"]
    fine = {o["time_s"]: o for o in reference["observations"]}
    table = []
    for mine in projective["observations"]:
        t = mine["time_s"]
        if after is not None and t < after:
            continue
        theirs = fine.get(t)
        if theirs is None:
            raise KeyError(f"reference has no observation at {t} s")
        effort = sum(
            _effort(j)
            for j in jumps
            if j["to_time_s"] <= t and (after is None or j["to_time_s"] > after)
        )
        entry = dict(time_s=t, effort=effort)
        for q in COORDINATES:
            a, b = np.asarray(mine[q], dtype=float), np.asarray(theirs[q], dtype=float)
            error = float(np.max(np.abs(a - b), initial=0.0))
            bound = S * tolerance[q] * effort + FLOOR
            entry[q] = dict(error=error, bound=bound, ratio=error / bound)
        table.append(entry)
    return table


def caps_table(projective, reference, *, after=None):
    """Per observation: criteria.absolute_caps values."""
    fine = {o["time_s"]: o for o in reference["observations"]}
    table = []
    for mine in projective["observations"]:
        t = mine["time_s"]
        if after is not None and t < after:
            continue
        theirs = fine[t]
        dv = np.max(
            np.abs(np.subtract(mine["membrane_voltage_V"], theirs["membrane_voltage_V"])),
            initial=0.0,
        )
        c = np.asarray(theirs["concentration_mM"], dtype=float)
        dc = np.max(np.abs(np.asarray(mine["concentration_mM"]) - c) / np.abs(c), initial=0.0)
        table.append(dict(time_s=t, voltage_V=float(dv), relative_concentration=float(dc)))
    return table


def _criterion(protocol, key, outcome, **values):
    return dict(id=key, protocol_text=protocol["criteria"][key], outcome=outcome, **values)


def judge_accuracy(protocol, projective, reference):
    table = accuracy_table(projective, reference)
    worst = {q: max((e[q]["ratio"] for e in table), default=0.0) for q in COORDINATES}
    passed = all(e[q]["error"] <= e[q]["bound"] for e in table for q in COORDINATES)
    return _criterion(
        protocol,
        "accuracy",
        "pass" if passed else "fail",
        worst_ratio=worst,
        observations=len(table),
        table=table,
    )


def judge_caps(protocol, projective, reference, *, judged, after=None):
    table = caps_table(projective, reference, after=after)
    worst = dict(
        voltage_V=max((e["voltage_V"] for e in table), default=0.0),
        relative_concentration=max((e["relative_concentration"] for e in table), default=0.0),
    )
    within = worst["voltage_V"] <= VOLTAGE_CAP_V and (
        worst["relative_concentration"] <= CONCENTRATION_CAP
    )
    outcome = ("pass" if within else "fail") if judged else "reported"
    return _criterion(
        protocol,
        "absolute_caps",
        outcome,
        judged=judged,
        caps=dict(voltage_V=VOLTAGE_CAP_V, relative_concentration=CONCENTRATION_CAP),
        worst=worst,
        within=within,
        table=table,
    )


def judge_energy(protocol, projective):
    jumps = projective["report"]["jump_log"]
    ratios = [j["energy_defect_pJ"] / j["energy_bound_pJ"] for j in jumps]
    passed = all(j["energy_defect_pJ"] <= j["energy_bound_pJ"] for j in jumps)
    return _criterion(
        protocol,
        "energy",
        "pass" if passed else "fail",
        jumps=len(jumps),
        max_ratio=max(ratios, default=0.0),
    )


def judge_conservation(protocol, projective, reference):
    """Both runs completed (every accepted row checked); ledger records reported."""
    ledgers = {}
    for jump in projective["report"]["jump_log"]:
        for name, value in jump["ledgers"].items():
            entry = ledgers.setdefault(
                name, dict(max_after=0.0, max_carried_fine_drift=0.0, max_affine_excess=0.0)
            )
            entry["max_after"] = max(entry["max_after"], value["after"])
            entry["max_carried_fine_drift"] = max(
                entry["max_carried_fine_drift"], value["carried_fine_drift"]
            )
            entry["max_affine_excess"] = max(entry["max_affine_excess"], value["affine_excess"])
    return _criterion(
        protocol,
        "conservation",
        "pass",
        projective_diagnostics=projective["diagnostics"],
        reference_diagnostics=reference["diagnostics"],
        jump_ledgers_reported=ledgers,
    )


def judge_fallback(protocol, projective, reference, rates, *, onset):
    """criteria.fallback with amendment 1: the fine rows are the reference's."""
    params = protocol["projective_parameters"]
    threshold = params["safety"]["max_membrane_voltage_rate_V_per_s"]
    burst_s = params["burst_steps"] * projective["definition"]["execution"]["dt"]
    report = projective["report"]
    times, rate = rates["times_s"], rates["max_abs_dvm_dt_V_per_s"]
    changes = _changes(projective["definition"])
    crossings = []
    for jump in report["jump_log"]:
        start, end = jump["from_time_s"], jump["to_time_s"] + burst_s
        inside = (times >= start) & (times <= end)
        fast = int(np.count_nonzero(inside & (rate > threshold)))
        events = [t for t in changes if start <= t < end]
        if fast or events:
            crossings.append(dict(from_time_s=start, end_s=end, fast_rows=fast, changes=events))
    if onset is None:
        return _criterion(protocol, "fallback", "not evaluable", reason="no onset time")
    window = (onset, onset + CUE_WINDOW_S)
    reacted = [
        dict(time_s=f["time_s"], reason=f["reason"], kind="fallback")
        for f in report["fallback_log"]
        if f["reason"] in FALLBACK_REASONS and window[0] <= f["time_s"] <= window[1]
    ] + [
        dict(time_s=r["from_time_s"], reason=r["reason"], kind="rejection")
        for r in report["rejection_log"]
        if r["reason"] in FALLBACK_REASONS and window[0] <= r["from_time_s"] <= window[1]
    ]
    after = np.flatnonzero((times >= onset) & (rate > threshold))
    transient_end = float(times[after[-1]]) if len(after) else float(onset)
    resumed = [
        j["from_time_s"]
        for j in report["jump_log"]
        if transient_end < j["from_time_s"] <= transient_end + RESUME_WINDOW_S
    ]
    passed = not crossings and bool(reacted) and bool(resumed)
    return _criterion(
        protocol,
        "fallback",
        "pass" if passed else "fail",
        onset_s=onset,
        rate_threshold_V_per_s=threshold,
        jumps_crossing_changes_or_fast_rows=crossings,
        reactions_within_10_s=reacted,
        transient_end_s=transient_end,
        jumps_resumed_at_s=resumed,
    )


def judge_near_fold(protocol, projective, reference):
    """near_fold_accuracy (a)-(c) with the switch times recorded at fine-row resolution."""
    fine_switch = [t for t in reference["switch_below_m50mV_s"] if t is not None]
    mine_switch = [t for t in projective["switch_below_m50mV_s"] if t is not None]
    if not fine_switch or not mine_switch:
        return _criterion(
            protocol, "near_fold_accuracy", "fail", reason="a run did not switch", values={}
        )
    fine_t, mine_t = min(fine_switch), min(mine_switch)
    later = max(fine_t, mine_t)
    fine = {o["time_s"]: o for o in reference["observations"]}
    branches = []
    for mine in projective["observations"]:
        t = mine["time_s"]
        if t < later:
            continue
        a, b = np.asarray(mine["membrane_voltage_V"]), np.asarray(fine[t]["membrane_voltage_V"])
        same = bool(
            (np.all(a < H_BELOW_V) and np.all(b < H_BELOW_V))
            or (np.all(a > D_ABOVE_V) and np.all(b > D_ABOVE_V))
        )
        branches.append(dict(time_s=t, same_branch=same))
    lingering = fine_t  # The fine reference's switch time from t = 0 (amendment 1).
    switch_ok = abs(mine_t - fine_t) <= SWITCH_SHARE * lingering
    table = accuracy_table(projective, reference, after=later)
    accurate = all(e[q]["error"] <= e[q]["bound"] for e in table for q in COORDINATES)
    passed = all(b["same_branch"] for b in branches) and switch_ok and accurate
    return _criterion(
        protocol,
        "near_fold_accuracy",
        "pass" if passed else "fail",
        fine_switch_s=fine_t,
        projective_switch_s=mine_t,
        lingering_s=lingering,
        switch_difference_s=abs(mine_t - fine_t),
        same_branch=branches,
        accuracy_after_switch=table,
    )


def speedup(projective, reference, case_id):
    """criteria.speedup (reported)."""
    report = projective["report"]
    jumps = report["jump_log"]
    seconds = sorted(j["to_time_s"] - j["from_time_s"] for j in jumps)
    entry = dict(
        fine_steps=report["fine_steps"],
        discarded_fine_steps=report["discarded_fine_steps"],
        executed_fine_steps=report["fine_steps"] + report["discarded_fine_steps"],
        traversed_steps=report["traversed_steps"],
        step_speedup=report["step_speedup"],
        jumps=len(jumps),
        jump_seconds=dict(
            min=seconds[0] if seconds else None,
            median=float(np.median(seconds)) if seconds else None,
            max=seconds[-1] if seconds else None,
        ),
        projective_wall_s=projective["wall_s"],
        reference_wall_s=reference["wall_s"],
        wall_speedup=reference["wall_s"] / projective["wall_s"],
    )
    dt = projective["definition"]["execution"]["dt"]
    phases = []
    for start, stop in PHASES.get(case_id, []):
        jumped = sum(j["steps"] for j in jumps if start <= j["from_time_s"] < stop)
        discarded = sum(
            r["steps"] for r in report["rejection_log"] if start <= r["from_time_s"] < stop
        )
        traversed = round((stop - start) / dt)
        executed = traversed - jumped + discarded
        phases.append(
            dict(
                phase_s=[start, stop],
                traversed_steps=traversed,
                executed_fine_steps_approx=executed,
                step_speedup_approx=traversed / max(1, executed),
                jumps=sum(1 for j in jumps if start <= j["from_time_s"] < stop),
            )
        )
    entry["phases"] = phases
    return entry


def burst_growth(protocol, spectrum):
    """projective_parameters.burst_basis: fast-mode cycle growth below 0.1 at the revision."""
    params = protocol["projective_parameters"]
    longest = params["jump"]["max_steps"] * 1e-3  # dt = 1 ms (engine_models).
    if spectrum is None:
        return dict(outcome="not evaluable", reason="spectrum/spectrum.json absent")
    if spectrum.get("burst_steps") != params["burst_steps"]:
        return dict(outcome="fail", reason="spectrum burst length is not the protocol's")
    worst = {
        name: max(
            (c["fast_max_growth"] for c in state["cycles"] if c["jump_s"] <= longest),
            default=None,
        )
        for name, state in spectrum["states"].items()
    }
    passed = all(v is not None and v < GROWTH_CAP for v in worst.values())
    return dict(
        protocol_text=params["burst_basis"],
        outcome="pass" if passed else "fail",
        max_fast_growth=worst,
        cap=GROWTH_CAP,
        longest_jump_s=longest,
    )


def judge_case(protocol, results, case, label=None):
    """Every criterion of one protocol case from its saved parts (run label: files)."""
    case_id, label = case["id"], label or case["id"]
    projective, ppath, pfailed = _load(results, f"{label}-projective")
    out = dict(id=case_id, run=label, files={}, criteria=[])
    if projective is None:
        out.update(outcome="not evaluable", reason="no projective result")
        return out
    out["files"]["projective"] = dict(path=str(ppath), sha256=_digest(ppath))
    if pfailed:
        out["criteria"].append(
            _criterion(protocol, "conservation", "fail", reason=projective.get("error"))
        )
        out.update(outcome="fail")
        return out
    reference, rpath, rfailed = None, None, None
    for candidate in sorted(results.glob("*-reference*.json")):
        data = json.loads(candidate.read_text())
        if data.get("fine_definition_sha256") == projective["fine_definition_sha256"]:
            reference, rpath, rfailed = data, candidate, data.get("status") == "failed"
            break
    if reference is None:
        out.update(outcome="not evaluable", reason="no reference with this fine definition")
        return out
    out["files"]["reference"] = dict(path=str(rpath), sha256=_digest(rpath))
    if rfailed:
        out["criteria"].append(
            _criterion(protocol, "conservation", "fail", reason=reference.get("error"))
        )
        out.update(outcome="fail")
        return out
    criteria = out["criteria"]
    criteria.append(judge_conservation(protocol, projective, reference))
    criteria.append(judge_energy(protocol, projective))
    if case_id == NEAR_FOLD:
        criteria.append(judge_near_fold(protocol, projective, reference))
        fine = [t for t in reference["switch_below_m50mV_s"] if t is not None]
        mine = [t for t in projective["switch_below_m50mV_s"] if t is not None]
        after = max(min(fine), min(mine)) if fine and mine else math.inf
        criteria.append(
            judge_caps(
                protocol, projective, reference, judged=projective["caps_judged"], after=after
            )  # fmt: skip
        )
    else:
        criteria.append(judge_accuracy(protocol, projective, reference))
        criteria.append(
            judge_caps(protocol, projective, reference, judged=projective["caps_judged"])
        )
    if case_id in FALLBACK_CASES:
        rates_path = Path(str(rpath).replace("-reference.json", "-reference-rates.npz"))
        if not rates_path.exists():
            criteria.append(
                _criterion(protocol, "fallback", "not evaluable", reason="rates file absent")
            )
        else:
            with np.load(rates_path) as rates:
                arrays = {k: rates[k] for k in rates.files}
            out["files"]["rates"] = dict(path=str(rates_path), sha256=_digest(rates_path))
            if case_id == NEAR_FOLD:
                threshold = protocol["projective_parameters"]["safety"][
                    "max_membrane_voltage_rate_V_per_s"
                ]
                onset = f2_onset(arrays, case["windows"][0][0], threshold)
            else:
                onset = _cue_onset(projective["definition"])
            if onset is None and case_id == NEAR_FOLD:
                criteria.append(
                    _criterion(
                        protocol,
                        "fallback",
                        "fail",
                        reason="amendment 2: no reference row at or after the window start "
                        "exceeds the voltage-rate threshold",
                    )
                )
            else:
                criteria.append(
                    judge_fallback(protocol, projective, reference, arrays, onset=onset)
                )
    out["speedup_reported"] = speedup(projective, reference, case_id)
    outcomes = [c["outcome"] for c in criteria if c["outcome"] != "reported"]
    out["outcome"] = (
        "fail"
        if "fail" in outcomes
        else "pass"
        if all(o == "pass" for o in outcomes)
        else "incomplete"
    )
    return out


def judge(results, protocol_path=PROTOCOL):
    results = Path(results)
    protocol = json.loads(Path(protocol_path).read_text())
    spectrum_path = results / "spectrum" / "spectrum.json"
    spectrum = json.loads(spectrum_path.read_text()) if spectrum_path.exists() else None
    growth = burst_growth(protocol, spectrum)
    cases = []
    for case in protocol["cases"]:
        entry = judge_case(protocol, results, case)
        if case["id"] == Q2 and _refused_on_global_charge(entry):
            # amendment 2: judged on the 5-cell run; the 7-cell refusal is reported.
            five = judge_case(protocol, results, case, label=Q2_FIVE)
            if five["outcome"] == "not evaluable" and five.get("reason") == "no projective result":
                five.update(reason="7-cell Q2 refused on global charge; 5-cell run absent")
            five["seven_cell_refusal_reported"] = entry
            entry = five
        cases.append(entry)
    outcomes = [growth["outcome"], *(c["outcome"] for c in cases)]
    verdict = (
        "fail"
        if "fail" in outcomes
        else "pass"
        if all(o == "pass" for o in outcomes)
        else "incomplete"
    )
    return dict(
        kind="cells.projective_qualification_judgement@1",
        protocol=dict(
            id=protocol["id"],
            path=str(protocol_path),
            sha256=_digest(protocol_path),
            amendments=[a["id"] for a in protocol.get("amendments", [])],
        ),
        readings="amendment-1: fallback fine rows are the checked reference's; a transient "
        "ends at the last reference row above the voltage-rate threshold after the onset; "
        "switch times at fine-row resolution in both runs; judged runs on CPU float64. "
        "amendment-2: F2's switch onset is the first reference row at or after the window "
        "start above that threshold (none: F2's fallback fails); Q2 is judged on its 5-cell "
        "run if the 7-cell run was refused on global charge",
        burst_growth=growth,
        cases=cases,
        verdict=verdict,
        passed=outcomes.count("pass"),
        failed=outcomes.count("fail"),
        not_evaluable_or_incomplete=sum(o not in ("pass", "fail") for o in outcomes),
    )


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    args = parser.parse_args(argv)
    output = args.output or args.results / "judgement.json"
    result = judge(args.results, args.protocol)
    with open(output, "x") as stream:
        json.dump(_clean(result), stream, indent=1)
    print(
        json.dumps(
            dict(
                verdict=result["verdict"],
                burst_growth=result["burst_growth"]["outcome"],
                cases={c["id"]: c["outcome"] for c in result["cases"]},
                output=str(output),
            ),
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
