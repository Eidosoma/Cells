"""Evaluate the pre-registered stationary-analysis criteria (protocol stationary_analysis_e_v1).

Reads a run's saved driver JSON (validation/stationary/targets.py parts default,
heredity, mg0b, tissue and default_run) and evaluates every criterion E1.1-E4.2
exactly as validation/stationary/protocols/stationary_analysis_e_v1.json states
it, with its budget factor and formulas; nothing is re-run. Budgets are
recomputed here from the saved components (engine and reference error
estimates, saved matrices for the eigenvalue bounds) and the driver's own
budgets are recorded beside them, so a driver error in a budget shows up as a
mismatch instead of being trusted.

Each criterion gets its protocol text, the values used, the budget, and
"pass", "fail" or "not evaluable" (with the missing field). The verdict is
"pass" when every judged criterion passes, "fail" when any fails, otherwise
"incomplete". E4.3 (slow tissue: no independent reference, reported per the
protocol's status) and the reported-not-judged items are listed separately;
D1 is a diagnostic.

Usage: python -m validation.stationary.judge RESULTS_DIR [--output FILE]
(default RESULTS_DIR/../judgement.json; never overwritten).
"""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

PROTOCOL = Path(__file__).resolve().parent / "protocols" / "stationary_analysis_e_v1.json"
PARTS = ("default", "heredity", "mg0b", "tissue", "default_run")
EPS = float(np.finfo(float).eps)
MOBILE = ("Na", "K", "M")
QUANTITIES = ("vm_V", *MOBILE)
ROOT_TOLERANCE_V = 1e-15  # error_budget.state: "+ 1e-15 V root tolerance for voltages"
CORRECTOR_TOLERANCE = 1e-10  # error_budget.folds
STATES = ("H", "U", "D")


class Missing(Exception):
    """A field the criterion needs is absent from the saved JSON."""


def field(data, *path):
    value = data
    for key in path:
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError) as error:
            raise Missing("/".join(str(p) for p in path)) from error
    return value


def _float(value):
    return None if value is None else float(value)


# ------------------------------------------------------------------ budgets


def state_budget(comparison):
    """error_budget.state for a slow-state comparison (V, Na, K, M), from saved parts."""
    factor = 10.0
    engine = field(comparison, "engine_error_estimate")
    reference = field(comparison, "reference_error_estimate")
    budget = {}
    for q in QUANTITIES:
        value = (
            field(comparison, "reference_vm_V")
            if q == "vm_V"
            else field(comparison, "reference_composition_mM", q)
        )
        extra = ROOT_TOLERANCE_V if q == "vm_V" else 0.0
        budget[q] = factor * (abs(engine[q]) + abs(reference[q]) + extra) + 64 * EPS * abs(value)
    return budget


def eigen_bounds(jac, error):
    """First-order bounds kappa_i ||dJ||_2 (the reduced reference's formula)."""
    import scipy.linalg

    jac, error = np.asarray(jac, dtype=float), np.asarray(error, dtype=float)
    values, left, right = scipy.linalg.eig(jac, left=True, right=True)
    left = left / np.linalg.norm(left, axis=0)
    right = right / np.linalg.norm(right, axis=0)
    kappa = 1 / np.abs(np.sum(np.conj(left) * right, axis=0))
    bound = kappa * np.linalg.norm(error, 2)
    order = np.argsort(-values.real)
    return values[order], bound[order]


def eigen_budget(comparison):
    """error_budget.eigenvalues: reference bound + engine bound, matched by distance."""
    engine, ref = (
        np.asarray(field(comparison, k), dtype=float)
        for k in ("adiabatic_jacobian_engine", "adiabatic_jacobian_reference")
    )
    error = field(comparison, "adiabatic_jacobian_reference_error")
    ref_values, ref_bounds = eigen_bounds(ref, error)
    eng_values, eng_bounds = eigen_bounds(engine, 64 * EPS * np.abs(engine))
    matched = [int(np.argmin(np.abs(eng_values - v))) for v in ref_values]
    difference = np.abs(eng_values[matched] - ref_values)
    budget = ref_bounds + eng_bounds[matched]
    return dict(
        engine=[[v.real, v.imag] for v in eng_values[matched]],
        reference=[[v.real, v.imag] for v in ref_values],
        difference=difference.tolist(),
        budget=budget.tolist(),
        within=bool(np.all(difference <= budget)),
        driver_budget=field(comparison, "adiabatic_eigenvalue_budget"),
    )


# ------------------------------------------------------------------ shared checks


def _newton(record):
    history = field(record, "newton_history")
    last = history[-1] if history else {}
    checks = dict(
        converged=bool(field(record, "converged")),
        method=field(record, "method"),
        last_full_step=_float(field(record, "last_correction")),
        last_damping=_float(last.get("damping")) if last else None,
        error_estimate=_float(field(record, "error_estimate")),
    )
    ok = (
        checks["converged"]
        and checks["method"] == "newton"
        and checks["last_damping"] == 1.0
        and checks["last_full_step"] <= 1e-10
        and checks["error_estimate"] <= 1e-10
    )
    return checks, ok


def _state_within(comparison):
    budget = state_budget(comparison)
    diff = field(comparison, "engine_minus_reference")
    values = {
        q: dict(
            difference=diff[q],
            budget=budget[q],
            driver_budget=field(comparison, "budget", q),
            within=bool(abs(diff[q]) <= budget[q]),
        )
        for q in QUANTITIES
    }
    return values, all(v["within"] for v in values.values())


def _step_map(record, agreement):
    consistency = field(record, "consistency")
    values = {}
    for k in ("step_map_1", "step_map_2"):
        c, floor = field(consistency, k, "correction"), field(consistency, k, "rounding_floor")
        values[k] = dict(correction=c, rounding_floor=floor, within=bool(c <= floor))
    difference, floor = field(agreement, "max_u_difference"), field(agreement, "floor")
    values["rhs_vs_step_map_solution"] = dict(
        max_u_difference=difference,
        floor=floor,
        limit=2 * floor,
        within=bool(difference <= 2 * floor),
    )
    return values, all(v["within"] for v in values.values())


def _neutral_is_p(stability, cells=("cell_0",)):
    laws = field(stability, "neutral_directions")
    expected = [dict(kind="closed_species_total", species="P", nodes=[c]) for c in cells]
    got = [dict(kind=v.get("kind"), species=v.get("species"), nodes=v.get("nodes")) for v in laws]
    return got, got == expected


# ------------------------------------------------------------------ criteria


def e1(r):
    d = r["default"]

    def c1():
        checks, ok = _newton(field(d, "rhs"))
        return checks, "full step <= 1e-10, error estimate <= 1e-10, method newton", ok

    def c2():
        states = field(d, "theory_states")
        values, ok = _state_within(field(d, "theory_comparison"))
        values["reference_states"] = len(states)
        return values, "state budget (error_budget.state)", ok and len(states) == 1

    def c3():
        return _e1_3(d)

    def c4():
        values, ok = _step_map(field(d, "rhs"), field(d, "step_map_agreement"))
        return values, "rounding floors (error_budget.step_map); 2 x floor", ok

    return {"E1.1": c1, "E1.2": c2, "E1.3": c3, "E1.4": c4}


def _e1_3(d):
    st = field(d, "rhs", "stability")
    neutral, neutral_ok = _neutral_is_p(st)
    eig = eigen_budget(field(d, "theory_comparison"))
    values = dict(
        classification=field(st, "classification"),
        eigenvalue_count=len(field(st, "eigenvalues_per_s")),
        marginal_count=field(st, "marginal_count"),
        neutral_directions=neutral,
        eigenvalues=eig,
    )
    ok = (
        values["classification"] == "stable"
        and values["eigenvalue_count"] == 3
        and values["marginal_count"] == 0
        and neutral_ok
        and eig["within"]
    )
    return values, "eigenvalue budget (error_budget.eigenvalues)", ok


def e2(r):
    h = r["heredity"]

    def states():
        return {k: field(h, "states", k) for k in STATES}

    def c1():
        s = states()
        voltages = {k: field(s[k], "rhs_cell", "vm_V") for k in STATES}
        converged = {k: bool(field(s[k], "rhs", "converged")) for k in STATES}
        gaps = [abs(voltages[a] - voltages[b]) for a, b in (("H", "U"), ("U", "D"), ("H", "D"))]
        values = dict(converged=converged, vm_V=voltages, separations_V=gaps)
        return values, "separations > 1 mV", all(converged.values()) and min(gaps) > 1e-3

    def c2():
        s, values, ok = states(), {}, True
        for k in STATES:
            values[k], good = _state_within(field(s[k], "theory_comparison"))
            ok &= good
        return values, "state budget (error_budget.state)", ok

    def c3():
        s, values, ok = states(), {}, True
        for k in STATES:
            st = field(s[k], "rhs", "stability")
            neutral, neutral_ok = _neutral_is_p(st)
            values[k] = dict(
                classification=field(st, "classification"),
                unstable_count=field(st, "unstable_count"),
                marginal_count=field(st, "marginal_count"),
                neutral_directions=neutral,
            )
            expected = ("unstable", 1) if k == "U" else ("stable", 0)
            ok &= (values[k]["classification"], values[k]["unstable_count"]) == expected
            ok &= values[k]["marginal_count"] == 0 and neutral_ok
        return values, "H, D stable; U one unstable; none marginal; P neutral", ok

    def c4():
        s = states()
        values = {k: eigen_budget(field(s[k], "theory_comparison")) for k in STATES}
        ok = all(v["within"] for v in values.values())
        return values, "eigenvalue budget (error_budget.eigenvalues)", ok

    def c5():
        s, values, ok = states(), {}, True
        for k in STATES:
            values[k], good = _step_map(field(s[k], "rhs"), field(s[k], "step_map_agreement"))
            ok &= good
        return values, "as E1.4", ok

    return {"E2.1": c1, "E2.2": c2, "E2.3": c3, "E2.4": c4, "E2.5": c5}


def _folds(m):
    c = field(m, "continuation")
    folds = sorted(
        (s for s in field(c, "special_points") if s.get("kind") == "fold"),
        key=lambda s: s["parameter_value"],
    )
    return c, folds


def _fold_values(m):
    c, folds = _folds(m)
    refined = field(m, "theory_window_refined")
    values = []
    if len(folds) == 2 and len(refined) == 2:
        for s, ref in zip(folds, refined, strict=True):
            engine_error = field(s, "parameter_error_estimate")
            budget = 10.0 * (engine_error + field(ref, "error"))
            difference = field(s, "parameter_value") - field(ref, "u")
            values.append(
                dict(
                    engine_u=s["parameter_value"],
                    reference_u=ref["u"],
                    difference=difference,
                    engine_error=engine_error,
                    reference_error=ref["error"],
                    budget=budget,
                    within=bool(abs(difference) <= budget),
                )
            )
    return c, folds, refined, values


def e3(r):
    m = r["mg0b"]

    def c1():
        reference = sorted(field(m, "theory_fast_states_recomputed_V"))
        if len(reference) != 3:
            raise Missing("theory_fast_states_recomputed_V (three states)")
        values, ok = {}, True
        for k, v_ref in zip(STATES, reference, strict=True):
            rec = field(m, "states", k)
            v = field(rec, "state", "membrane_voltage_V", "membrane_0")
            engine, ref_err = field(rec, "engine_error_V"), field(rec, "reference_error_V")
            budget = 10.0 * (abs(engine) + abs(ref_err)) + 64 * EPS * abs(v_ref)
            values[k] = dict(
                engine_V=v,
                reference_V=v_ref,
                theory_json_V=field(m, "theory", "fast_states_V", k),
                difference_V=v - v_ref,
                engine_error_V=engine,
                reference_error_V=ref_err,
                budget_V=budget,
                driver_budget_V=field(rec, "budget_V"),
                within=bool(field(rec, "converged") and abs(v - v_ref) <= budget),
            )
            ok &= values[k]["within"]
        return values, "state budget (error_budget.state, fast)", ok

    def c2():
        values, ok = {}, True
        for k in STATES:
            st = field(m, "states", k, "stability")
            values[k] = dict(
                classification=field(st, "classification"),
                unstable_count=field(st, "unstable_count"),
            )
            expected = ("unstable", 1) if k == "U" else ("stable", 0)
            ok &= (values[k]["classification"], values[k]["unstable_count"]) == expected
        return values, "H, D stable; U one unstable", ok

    def c3():
        c, folds, refined, values = _fold_values(m)
        points = field(c, "points")
        reached = (
            field(c, "termination") == "parameter_bound"
            and field(c, "bounds")[1] == 1.0
            and bool(points)
            and field(points[-1], "tangent_parameter_component") > 0
        )
        ok = reached and len(folds) == 2 and len(values) == 2 and all(v["within"] for v in values)
        values = dict(
            termination=c["termination"],
            reached_upper_bound=reached,
            fold_count=len(folds),
            folds=values,
        )
        return values, "fold budget (error_budget.folds)", ok

    def c4():
        _, _, _, folds = _fold_values(m)
        window = field(m, "theory_window_grid")
        misses = field(m, "theory_grid_miss_bound")
        edges, ok = [], len(folds) == 2
        if ok:
            inside = (window[0] - folds[0]["engine_u"], folds[1]["engine_u"] - window[1])
            for k in range(2):
                limit = misses[k] + folds[k]["budget"]
                edges.append(
                    dict(inside_by=inside[k], limit=limit, within=bool(0 <= inside[k] <= limit))
                )
                ok &= edges[-1]["within"]
        values = dict(grid_window=window, miss_bounds=misses, edges=edges)
        return values, "grid miss bound + fold budget", ok

    def c5():
        _, folds = _folds(m)
        values, ok = [], len(folds) == 2
        for s in folds:
            aug = field(s, "augmented_sigma_min_relative")
            fz = field(s, "jacobian_sigma_min_relative")
            values.append(
                dict(
                    parameter=s["parameter_value"],
                    augmented_sigma_min_relative=aug,
                    jacobian_sigma_min_relative=fz,
                    unstable_count=field(s, "unstable_count"),
                    within=bool(aug > 1e3 * fz and s["unstable_count"] == 0),
                )
            )
            ok &= values[-1]["within"]
        return values, "augmented sigma_min > 1e3 x F_z's; unstable count 0", ok

    return {"E3.1": c1, "E3.2": c2, "E3.3": c3, "E3.4": c4, "E3.5": c5}


def e4(r):
    def fast():
        return field(r["tissue"], "fast_mg0b")

    def c1():
        f = fast()
        start, ref = field(f, "start"), field(f, "reference")
        voltages = field(start, "state", "membrane_voltage_V")
        engine = np.asarray(list(voltages.values()), dtype=float)
        v_ref = np.asarray(field(ref, "state_V"), dtype=float)
        dv_engine = 0.01 * field(start, "error_estimate")  # u units: 10 mV
        budget = 10.0 * (dv_engine + field(ref, "correction_V")) + 64 * EPS * np.abs(v_ref)
        difference = engine - v_ref
        disc = field(start, "disc")
        values = dict(
            theta=field(start, "parameter_value"),
            converged=bool(field(start, "converged")),
            d_cells_inside=field(disc, "d_cells_inside"),
            d_cells_outside=field(disc, "d_cells_outside"),
            max_abs_difference_V=float(np.max(np.abs(difference))),
            max_difference_over_budget=float(np.max(np.abs(difference) / budget)),
            driver_within_budget=field(ref, "within_budget"),
            classification=field(start, "stability", "classification"),
            reference_leading_rate_per_s=field(ref, "leading_rate_per_s"),
        )
        ok = (
            values["theta"] == 0.01
            and values["converged"]
            and (values["d_cells_inside"], values["d_cells_outside"]) == (7, 0)
            and bool(np.all(np.abs(difference) <= budget))
            and values["classification"] == "stable"
            and values["reference_leading_rate_per_s"] < 0
        )
        return values, "graph state budget (error_budget.state, graph)", ok

    def c2():
        f = fast()
        ref, c = field(f, "reference"), field(f, "continuation")
        fold = next((s for s in field(c, "special_points") if s.get("kind") == "fold"), None)
        rising = []
        for p in field(c, "points"):
            if field(p, "tangent_parameter_component") <= 0:
                break
            rising.append(p)
        values = dict(fold_found=fold is not None, points_below_fold=len(rising))
        if fold is None:
            return values, "fold budget; E3.5 fold test; stable below", False
        engine_error, ref_error = field(fold, "parameter_error_estimate"), field(ref, "fold_error")
        budget = 10.0 * (engine_error + ref_error)
        difference = fold["parameter_value"] - field(ref, "fold_coupling")
        aug = field(fold, "augmented_sigma_min_relative")
        fz = field(fold, "jacobian_sigma_min_relative")
        unstable_below = [p["unstable_count"] for p in rising]
        values.update(
            engine_fold=fold["parameter_value"],
            reference_fold=ref["fold_coupling"],
            difference=difference,
            engine_error=engine_error,
            reference_error=ref_error,
            budget=budget,
            driver_budget=field(ref, "fold_budget"),
            augmented_sigma_min_relative=aug,
            jacobian_sigma_min_relative=fz,
            fold_unstable_count=field(fold, "unstable_count"),
            max_unstable_below_fold=max(unstable_below, default=None),
        )
        ok = (
            abs(difference) <= budget
            and aug > 1e3 * fz
            and fold["unstable_count"] == 0
            and bool(rising)
            and all(u == 0 for u in unstable_below)
        )
        return values, "fold budget; E3.5 fold test; stable below", ok

    return {"E4.1": c1, "E4.2": c2}


def e4_3_reported(r):
    """E4.3's internal checks and findings (reported, not judged: no reference)."""
    s = field(r["tissue"], "slow_heredity")
    start = field(s, "start")
    st = field(start, "stability")
    laws = field(st, "neutral_directions")
    consistency = field(start, "consistency")
    specials = field(s, "continuation", "special_points")
    first = next(
        (p for p in specials if p.get("kind") in ("fold", "hopf", "stability_change")), None
    )
    return dict(
        theta=field(start, "parameter_value"),
        converged=bool(field(start, "converged")),
        disc=field(start, "disc"),
        classification=field(st, "classification"),
        neutral_directions=len(laws),
        neutral_all_p=all(v.get("species") == "P" for v in laws),
        step_map={
            k: dict(
                correction=consistency[k]["correction"],
                rounding_floor=consistency[k]["rounding_floor"],
                within=bool(consistency[k]["correction"] <= consistency[k]["rounding_floor"]),
            )
            for k in ("step_map_1", "step_map_2")
            if k in consistency
        },
        rhs_vs_step_map_solution="not evaluable: no step-map solve of the slow disc is saved",
        first_special_point=None
        if first is None
        else {
            k: first.get(k)
            for k in (
                "kind",
                "parameter_value",
                "parameter_error_estimate",
                "unstable_count",
                "frequency_hz",
                "crossing_multiplicity",
                "leading_eigenvalues_per_s",
            )
        },
        special_points=[(p.get("kind"), p.get("parameter_value")) for p in specials],
        termination=field(s, "continuation", "termination"),
    )


def reported(r):
    out = {}
    try:
        out["prescreen_03_default"] = field(r["default"], "prescreen_comparison")
    except Missing as error:
        out["prescreen_03_default"] = f"not evaluable: missing {error}"
    try:
        out["prescreen_06_heredity"] = {
            k: field(r["heredity"], "states", k, "prescreen_comparison") for k in STATES
        }
    except Missing as error:
        out["prescreen_06_heredity"] = f"not evaluable: missing {error}"
    try:
        out["full_spectra_leading"] = dict(
            default=field(r["default"], "rhs", "stability", "eigenvalues_per_s"),
            heredity={
                k: field(r["heredity"], "states", k, "rhs", "stability", "eigenvalues_per_s")
                for k in STATES
            },
        )
    except Missing as error:
        out["full_spectra_leading"] = f"not evaluable: missing {error}"
    diagrams = {}
    for name, path in (
        ("mg0b", ("mg0b", "continuation")),
        ("tissue_fast", ("tissue", "fast_mg0b", "continuation")),
        ("tissue_slow", ("tissue", "slow_heredity", "continuation")),
    ):
        try:
            c = field(r, *path)
            diagrams[name] = dict(
                points=len(c["points"]),
                termination=c["termination"],
                special_points=[
                    (p.get("kind"), p.get("parameter_value")) for p in c["special_points"]
                ],
            )
        except (Missing, KeyError) as error:
            diagrams[name] = f"not evaluable: missing {error}"
    out["continuation_diagrams"] = diagrams
    try:
        out["E4.3"] = e4_3_reported(r)
    except Missing as error:
        out["E4.3"] = f"not evaluable: missing {error}"
    return out


def diagnostic_d1(r):
    d = r["default_run"]
    keys = (
        "runner_probe",
        "refused_at_s",
        "ledgers",
        "final_distance_mM",
        "predicted_final_distance_mM",
        "late_log_slope_per_s",
        "stationary_slowest_rate_per_s",
        "late_slope_vs_slowest_rate_relative",
        "step_wall_seconds",
    )
    return {k: d.get(k) for k in keys}


# ------------------------------------------------------------------ assembly


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def judge(results, protocol_path=PROTOCOL):
    results = Path(results)
    protocol = json.loads(Path(protocol_path).read_text())
    texts = {
        key: text
        for group in protocol["criteria"].values()
        for key, text in group.items()
        if key.startswith("E")
    }
    loaded, files = {}, {}
    for part in PARTS:
        path = results / f"{part}.json"
        if path.exists():
            loaded[part] = json.loads(path.read_text())
            files[part] = dict(path=str(path), sha256=_digest(path))
    judged = [k for k in texts if k != "E4.3"]
    criteria = []
    groups = dict(E1=e1, E2=e2, E3=e3, E4=e4)
    parts = dict(E1="default", E2="heredity", E3="mg0b", E4="tissue")
    for group, function in groups.items():
        names = [k for k in judged if k.startswith(group + ".")]
        checks = function(loaded) if parts[group] in loaded else {}
        for name in names:
            entry = dict(id=name, protocol_text=texts[name])
            if parts[group] not in loaded:
                entry.update(outcome="not evaluable", reason=f"{parts[group]}.json absent")
            elif name not in checks:
                entry.update(outcome="not evaluable", reason="no evaluation defined")
            else:
                try:
                    values, budget, passed = checks[name]()
                    outcome = "pass" if passed else "fail"
                    entry.update(values=values, budget=budget, outcome=outcome)
                except Missing as error:
                    entry.update(outcome="not evaluable", reason=f"missing field {error}")
            criteria.append(entry)
    outcomes = [c["outcome"] for c in criteria]
    verdict = (
        "fail"
        if "fail" in outcomes
        else "pass"
        if all(o == "pass" for o in outcomes)
        else "incomplete"
    )
    reported_items = reported(loaded) if all(p in loaded for p in PARTS[:4]) else {}
    return dict(
        kind="cells.stationary_analysis_judgement@1",
        protocol=dict(
            id=protocol.get("id"), path=str(protocol_path), sha256=_digest(protocol_path)
        ),
        results=files,
        criteria=criteria,
        verdict=verdict,
        passed=outcomes.count("pass"),
        failed=outcomes.count("fail"),
        not_evaluable=outcomes.count("not evaluable"),
        reported_not_judged=dict(
            protocol_items=protocol.get("reported_not_judged", []),
            E4_3_protocol_text=texts.get("E4.3"),
            values=reported_items,
        ),
        diagnostics=dict(
            D1_protocol_text=protocol.get("diagnostics_not_judged", {}).get("D1"),
            D1=diagnostic_d1(loaded) if "default_run" in loaded else "results absent",
        ),
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
    output = args.output or args.results.resolve().parent / "judgement.json"
    result = judge(args.results, args.protocol)
    with open(output, "x") as stream:
        json.dump(_clean(result), stream, indent=1)
    print(
        json.dumps(
            dict(
                verdict=result["verdict"],
                passed=result["passed"],
                failed=result["failed"],
                not_evaluable=result["not_evaluable"],
                failing=[c["id"] for c in result["criteria"] if c["outcome"] != "pass"],
                output=str(output),
            ),
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
