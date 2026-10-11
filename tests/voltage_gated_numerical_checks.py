"""Data-only NUM-007 accounting, gate-domain and method-selection rules.

No integrator, production or gate/transport evaluator imports. Use existing
ionic diagnostics only after explicitly adding the separately retained channel
ledger to the material projection; never relabel the saved baseline ledger.
"""

import math

import numpy as np

from tests import multispecies_numerical_checks as old

require = old.require
parameters = old.parameters
voltage = old.voltage
canonical_native = old.canonical_native
expected_grid = old.expected_grid


def errors(case, actual, expected, limits, *, factor=1.0):
    base = old.errors(case, actual, expected, limits, factor=factor)
    g = 2 * len(case["parameters"]["species_ids"]) + 2
    extra = {
        "m": float(np.max(np.abs(actual[:, g] - expected[:, g]))),
        "h": float(np.max(np.abs(actual[:, g + 1] - expected[:, g + 1]))),
        "open_fraction": float(
            np.max(np.abs(actual[:, g] * actual[:, g + 1] - expected[:, g] * expected[:, g + 1]))
        ),
        "channel_fmol": float(np.max(np.abs(actual[:, -1] - expected[:, -1]))),
    }
    scores = [base["max_normalized_error"]]
    scores.extend(
        value / (factor * limits["gate" if key in ("m", "h") else key])
        for key, value in extra.items()
    )
    return {
        "errors": base["errors"] | extra,
        "max_normalized_error": max(scores),
        "pass": max(scores) <= 1,
    }


def inspect_samples(case, times, values, limits):
    n = len(case["parameters"]["species_ids"])
    g = 2 * n + 2
    require(values.shape == (len(times), g + 3), "Invalid coupled state shape")
    require(np.isfinite(values).all(), "Nonfinite coupled state")
    gates = values[:, g : g + 2]
    lo, hi = float(np.min(gates)), float(np.max(gates))
    amount = np.asarray(case["parameters"]["initial_amount_fmol"]) + values[:, :n]
    volts = voltage(case, values[:, :n])
    v = [float(np.min(volts)), float(np.max(volts))]
    if not (np.all(amount > 0) and 0 <= lo <= hi <= 1 and -0.120 <= v[0] <= v[1] <= 0.060):
        return {
            "pass": False,
            "domain_pass": False,
            "gate_range": [lo, hi],
            "voltage_range_V": v,
            "minimum_amount_fmol": float(np.min(amount)),
        }
    ionic = values[:, :g].copy()
    index = case["parameters"]["species_ids"].index(case["channel"]["species_id"])
    ionic[:, n + index] += values[:, -1]
    result = old.inspect_samples(case, times, ionic, limits)
    return result | {"gate_range": [lo, hi], "domain_pass": True}


def control_checks(case, times, values, gate_limit):
    n = len(case["parameters"]["species_ids"])
    g, results = 2 * n + 2, []
    channel = case["channel"]
    for i, control in enumerate(case["controls"]):
        end = (
            case["controls"][i + 1]["time_s"]
            if i + 1 < len(case["controls"])
            else case["horizon_s"]
        )
        if end == control["time_s"]:
            continue
        selected_times = (times >= control["time_s"]) & (times <= end)
        subset, ts = values[selected_times], times[selected_times]
        require(
            len(subset) >= 2 and ts[0] == control["time_s"] and ts[-1] == end,
            "Control interval missing endpoints",
        )
        selected = [n + s for s, u in enumerate(control["leak"]) if u == 0]
        if control["pump"] == 0:
            selected.append(2 * n)
        channel_off = (
            control["availability"] == 0
            or channel["max_permeability_m_per_s"] == 0
            or channel["abundance"] == 0
        )
        if channel_off:
            selected.append(g + 2)
        unchanged = np.array_equal(
            subset[:, selected], np.broadcast_to(subset[0, selected], (len(subset), len(selected)))
        )
        analytic_error = None
        if channel_off and control["pump"] == 0 and all(u == 0 for u in control["leak"]):
            unchanged = unchanged and np.array_equal(
                subset[:, :g], np.broadcast_to(subset[0, :g], subset[:, :g].shape)
            )
            v = float(voltage(case, subset[0, :n])) * 1000
            targets = (1 / (1 + math.exp(-(v + 6) / 6.4)), 1 / (1 + math.exp((v + 25.3) / 3.5)))
            taus = ((8.33 - 0.1163 * v) / 1000, (1620 - 15.5 * v) / 1000)
            expected = np.array(
                [
                    target + (subset[0, g + k] - target) * np.exp(-(ts - ts[0]) / taus[k])
                    for k, target in enumerate(targets)
                ]
            ).T
            analytic_error = float(np.max(np.abs(subset[:, g : g + 2] - expected)))
        results.append(
            {
                "start_s": control["time_s"],
                "end_s": end,
                "disabled_ledgers_exact": unchanged,
                "held_gate_max_error": analytic_error,
                "pass": unchanged and (analytic_error is None or analytic_error <= gate_limit),
            }
        )
    return {"intervals": results, "pass": all(r["pass"] for r in results)}


def candidate_polynomial_domain(case, arrays):
    base = old.candidate_polynomial_domain(case, arrays)
    p, z, initial, _ = parameters(case)
    n, g = len(initial), 2 * len(initial) + 2
    capacitance = p["area_m2"] * p["specific_capacitance_F_per_m2"]
    ranges = [[math.inf, -math.inf] for _ in range(3)]
    inspected = 0
    for coeff in arrays["coefficients"]:
        vc = old.QF / capacitance * np.sum(z[:, None] * coeff[:n, :4], axis=0)
        vc[0] = float(voltage(case, coeff[:n, 0] - initial))
        for slot, row in enumerate([vc, coeff[g, :4], coeff[g + 1, :4]]):
            roots = np.polynomial.polynomial.polyroots([row[1], 2 * row[2], 3 * row[3]])
            nodes = [0.0, 1.0] + [
                float(r.real) for r in roots if abs(r.imag) <= 1e-12 and 0 < r.real < 1
            ]
            vals = np.polynomial.polynomial.polyval(nodes, row)
            require(np.isfinite(vals).all(), "Nonfinite cubic gate/voltage bound")
            ranges[slot][0] = min(ranges[slot][0], float(min(vals)))
            ranges[slot][1] = max(ranges[slot][1], float(max(vals)))
            inspected += len(nodes)
    valid = -0.120 <= ranges[0][0] <= ranges[0][1] <= 0.060 and all(
        0 <= lo <= hi <= 1 for lo, hi in ranges[1:]
    )
    return base | {
        "voltage_range_V": ranges[0],
        "m_range": ranges[1],
        "h_range": ranges[2],
        "gate_voltage_extrema_checked": inspected,
        "pass": base["pass"] and valid,
    }


def validate_record(case, arrays, kind, *, complete=True):
    require(
        set(arrays)
        == {
            "native_times_s",
            "native_state",
            "coefficients",
            "degree",
            "shift",
            "denominator",
            "sample_times_s",
            "sample_state",
        },
        "Unexpected recorded array members",
    )
    require(
        all(
            v.dtype == np.dtype("int64" if key == "degree" else "float64") and np.isfinite(v).all()
            for key, v in arrays.items()
        ),
        "Invalid finite recorded dtype",
    )
    times = arrays["native_times_s"]
    n = len(case["parameters"]["species_ids"])
    size, steps = 2 * n + 5, len(times) - 1
    require(
        times.ndim == 1 and 0 <= steps <= 100000 and times[0] == 0 and np.all(np.diff(times) > 0),
        "Invalid native mesh",
    )
    require(
        times[-1] == case["horizon_s"] if complete else times[-1] < case["horizon_s"],
        "Incomplete or overrun trajectory",
    )
    for key, shape in {
        "native_state": (steps + 1, size),
        "coefficients": (steps, size, 6),
        "degree": (steps,),
        "shift": (steps, 5),
        "denominator": (steps, 5),
    }.items():
        require(arrays[key].shape == shape, f"Invalid {key} shape")
    require(kind in ("Radau", "BDF", "RK4"), "Unknown dense kind")
    require(np.all((arrays["degree"] >= 1) & (arrays["degree"] <= 5)), "Invalid dense degree")
    if kind != "BDF":
        require(np.all(arrays["degree"] == 3), "Invalid cubic degree")
    require(np.all(arrays["denominator"] > 0), "Invalid dense denominator")
    initial = np.zeros(size)
    initial[2 * n + 2 : 2 * n + 4] = [case["channel"]["initial_gate"][key] for key in ("m", "h")]
    if kind == "RK4":
        initial[:n] = case["parameters"]["initial_amount_fmol"]
    require(np.array_equal(initial, arrays["native_state"][0]), "Initial state/history mismatch")
    for control in case["controls"]:
        if control["time_s"] <= times[-1]:
            require(control["time_s"] in times, "Control boundary lost")
    sample = arrays["sample_times_s"]
    require(
        sample.ndim == 1
        and len(sample) <= 100000
        and arrays["sample_state"].shape == (len(sample), size),
        "Invalid comparison shape",
    )
    if complete:
        require(
            len(sample) > 1
            and sample[0] == 0
            and sample[-1] == case["horizon_s"]
            and np.all(np.diff(sample) > 0),
            "Invalid complete observation mesh",
        )
    else:
        require(len(sample) == 0 and kind == "RK4", "Rejected prefix must not fabricate a suffix")


def rejection_check(case, arrays, stats):
    trial = stats["rejected_trial"]
    require(stats["status"] == "rejected" and isinstance(trial, dict), "Missing rejection evidence")
    dt, horizon = stats["dt_s"], case["horizon_s"]
    mesh = np.unique(
        np.r_[
            np.arange(math.ceil(horizon / dt)) * dt,
            [c["time_s"] for c in case["controls"]],
            horizon,
        ]
    )
    steps = stats["accepted_steps"]
    require(
        steps < len(mesh) - 1 and np.array_equal(arrays["native_times_s"], mesh[: steps + 1]),
        "Rejected prefix differs from candidate mesh",
    )
    require(
        trial["interval_left_s"] == mesh[steps] and trial["interval_right_s"] == mesh[steps + 1],
        "Rejected stage not bound to prefix",
    )
    labels = {"k1": (0, 1), "k2": (0.5, 2), "k3": (0.5, 3), "k4": (1, 4), "endpoint": (1, 5)}
    require(trial["stage"] in labels, "Unknown rejected stage")
    fraction, call = labels[trial["stage"]]
    require(
        trial["time_s"] == mesh[steps] + fraction * (mesh[steps + 1] - mesh[steps])
        and stats["rhs_calls"] == 5 * steps + call,
        "Rejected time/call count mismatch",
    )
    held = next(c for c in reversed(case["controls"]) if c["time_s"] <= mesh[steps])
    require(trial["control"] == held, "Rejected held control mismatch")
    state = np.asarray(trial["absolute_state"], dtype=float)
    n = len(case["parameters"]["species_ids"])
    require(state.shape == (2 * n + 5,), "Invalid rejected state shape")
    delta = state[:n] - case["parameters"]["initial_amount_fmol"]
    v = float(voltage(case, delta))
    xs = (
        np.asarray(case["parameters"]["valence"])
        * old.F
        * v
        / (old.R * case["parameters"]["temperature_K"])
    )
    gates = state[2 * n + 2 : 2 * n + 4]
    violates = (
        not np.isfinite(state).all()
        or np.any(state[:n] <= 0)
        or not -0.120 <= v <= 0.060
        or np.max(np.abs(xs)) > 50
        or np.any(gates < 0)
        or np.any(gates > 1)
    )
    require(violates, "Claimed rejection does not violate the physical/gate domain")
    return {
        "pass": False,
        "status": "rejected",
        "retained_steps": steps,
        "reason": trial["reason"],
        "rejection_domain_confirmed": True,
    }


def analyze_case(case, records, stats, plan):
    names = [s["id"] for s in plan["references"]] + [
        f"rk4_{dt:g}" for dt in plan["candidate"]["steps_s"]
    ]
    require(set(records) == set(stats) == set(names), "Missing numerical attempts")
    grid = expected_grid(case, plan["candidate"])
    oracle = records["refined"]["sample_state"]
    output = {"attempts": {}, "reference_comparisons": {}}
    for name, arrays in records.items():
        kind = (
            "RK4"
            if name.startswith("rk4_")
            else next(s["method"] for s in plan["references"] if s["id"] == name)
        )
        complete = stats[name]["status"] == "complete"
        validate_record(case, arrays, kind, complete=complete)
        if not complete:
            output["attempts"][name] = rejection_check(case, arrays, stats[name])
            continue
        require(
            np.array_equal(grid, arrays["sample_times_s"]),
            "Comparison mesh differs from frozen panel",
        )
        native = canonical_native(case, arrays, kind)
        entry = {
            "status": "complete",
            "native_accounting": inspect_samples(
                case, arrays["native_times_s"], native, plan["accounting_limits"]
            ),
            "sampled_accounting": inspect_samples(
                case, grid, arrays["sample_state"], plan["accounting_limits"]
            ),
            "controls": control_checks(
                case,
                grid,
                arrays["sample_state"],
                plan["trajectory_limits"]["gate"]
                * (1 if kind == "RK4" else plan["trajectory_limits"]["reference_factor"]),
            ),
        }
        entry["pass"] = all(
            entry[k]["pass"] for k in ("native_accounting", "sampled_accounting", "controls")
        )
        if kind == "RK4":
            positions = np.searchsorted(grid, arrays["native_times_s"])
            require(
                np.array_equal(grid[positions], arrays["native_times_s"]),
                "Missing candidate endpoints",
            )
            entry["accepted_comparison"] = errors(
                case, native, oracle[positions], plan["trajectory_limits"]
            )
            entry["observed_comparison"] = errors(
                case, arrays["sample_state"], oracle, plan["trajectory_limits"]
            )
            entry["polynomial_domain"] = candidate_polynomial_domain(case, arrays)
            entry["pass"] = entry["pass"] and all(
                entry[k]["pass"]
                for k in ("accepted_comparison", "observed_comparison", "polynomial_domain")
            )
        output["attempts"][name] = entry
    for name in ("radau", "bdf"):
        output["reference_comparisons"][name] = errors(
            case,
            records[name]["sample_state"],
            oracle,
            plan["trajectory_limits"],
            factor=plan["trajectory_limits"]["reference_factor"],
        )
    output["references_pass"] = all(
        output["attempts"][name]["pass"] for name in ("radau", "bdf", "refined")
    ) and all(r["pass"] for r in output["reference_comparisons"].values())
    return output


def select_candidate(analyses, plan):
    candidate, steps = plan["candidate"], plan["candidate"]["steps_s"]
    reference_pass = len(analyses) == len(plan["cases"]) and all(
        a["references_pass"] for a in analyses.values()
    )
    eligible, selected = [], None
    for coarse, fine in zip(steps[:-1], steps[1:], strict=True):
        results = []
        for name, analysis in analyses.items():
            first, second = (analysis["attempts"][f"rk4_{dt:g}"] for dt in (coarse, fine))
            refinements = {}
            for quantity, floor in (
                ("voltage_V", candidate["voltage_refinement_floor_V"]),
                ("gate", candidate["gate_refinement_floor"]),
            ):
                pair = []
                for item in (first, second):
                    if "observed_comparison" not in item:
                        pair.append(math.inf)
                    else:
                        e = item["observed_comparison"]["errors"]
                        pair.append(max(e["m"], e["h"]) if quantity == "gate" else e[quantity])
                refinements[quantity] = all(math.isfinite(v) for v in pair) and (
                    pair[0] <= floor
                    or pair[1] <= candidate["maximum_refined_error_ratio"] * pair[0]
                )
            results.append(
                {
                    "case": name,
                    "coarse_pass": first["pass"],
                    "fine_pass": second["pass"],
                    "refinement": refinements,
                    "pass": first["pass"] and second["pass"] and all(refinements.values()),
                }
            )
        passed = reference_pass and all(r["pass"] for r in results)
        eligible.append({"dt_s": coarse, "refined_dt_s": fine, "cases": results, "pass": passed})
        if passed and selected is None:
            selected = coarse
    return {
        "status": "pass" if selected is not None else "not_qualified",
        "references_pass": reference_pass,
        "selected_dt_s": selected,
        "eligibility": eligible,
    }
