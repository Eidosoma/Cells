"""Data-only NUM-006 diagnostics shared by qualification and read-only replay audit.

No integrator or transport RHS imports. Recompute verdicts from saved states,
dense coefficients and literal material/energy identities, not saved summaries.
"""

import math

import numpy as np

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
QF = F * 1e-15


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parameters(case):
    p = case["parameters"]
    ids = p["species_ids"]
    nu = np.zeros(len(ids))
    if p["pump_roles"] is not None:
        nu[ids.index(p["pump_roles"][0])] = -3
        nu[ids.index(p["pump_roles"][1])] = 2
    return p, np.asarray(p["valence"]), np.asarray(p["initial_amount_fmol"]), nu


def canonical_native(case, arrays, kind):
    values = arrays["native_state"].copy()
    if kind == "RK4":
        values[:, : len(case["parameters"]["species_ids"])] -= case["parameters"][
            "initial_amount_fmol"
        ]
    return values


def voltage(case, delta):
    p, z, _, _ = parameters(case)
    capacitance = p["area_m2"] * p["specific_capacitance_F_per_m2"]
    return p["initial_voltage_V"] + QF / capacitance * np.sum(delta * z, axis=-1)


def errors(case, actual, expected, limits, *, factor=1.0):
    require(
        actual.shape == expected.shape
        and np.isfinite(actual).all()
        and np.isfinite(expected).all(),
        "Invalid comparison arrays",
    )
    ids = case["parameters"]["species_ids"]
    count = len(ids)
    result, scores = {}, []
    for key, start in (("amount_fmol", 0), ("passive_fmol", count)):
        result[key] = {}
        for slot, species in enumerate(ids):
            error = float(
                np.max(np.abs(actual[:, start + slot] - expected[:, start + slot]), initial=0)
            )
            result[key][species] = error
            limit = limits["species_overrides"].get(species, {}).get(key, limits[key])
            scores.append(error / (limit * factor))
    for key, value in (
        ("pump_cycles_fmol", actual[:, 2 * count] - expected[:, 2 * count]),
        ("dissipation_pJ", actual[:, 2 * count + 1] - expected[:, 2 * count + 1]),
        ("voltage_V", voltage(case, actual[:, :count]) - voltage(case, expected[:, :count])),
    ):
        result[key] = float(np.max(np.abs(value), initial=0))
        scores.append(result[key] / (limits[key] * factor))
    return {"errors": result, "max_normalized_error": max(scores), "pass": max(scores) <= 1}


def inspect_samples(case, times, values, limits):
    p, z, initial, nu = parameters(case)
    count = len(initial)
    require(
        values.shape == (len(times), 2 * count + 2) and np.isfinite(values).all(),
        "Invalid finite canonical state array",
    )
    require(
        len(times) > 1 and np.isfinite(times).all() and np.all(np.diff(times) > 0),
        "Inspected times must be finite and strictly increasing",
    )
    delta, leak, cycles, dissipation = (
        values[:, :count],
        values[:, count : 2 * count],
        values[:, 2 * count],
        values[:, 2 * count + 1],
    )
    amount = initial + delta
    v = voltage(case, delta)
    max_x = float(np.max(np.abs(z[None, :] * F * v[:, None] / (R * p["temperature_K"]))))
    require(np.all(amount > 0) and max_x <= 50, "Observed amount/voltage outside physical domain")
    material = delta - leak - cycles[:, None] * nu
    material_errors = {
        s: float(np.max(np.abs(material[:, i]))) for i, s in enumerate(p["species_ids"])
    }
    capacitance = p["area_m2"] * p["specific_capacitance_F_per_m2"]
    charge = QF / capacitance * np.sum(material * z, axis=1)
    # Independent stable ideal-solution and capacitor energy *difference*, in pJ.
    chemical = (
        1e-3
        * R
        * p["temperature_K"]
        * np.sum(
            delta * (np.log(initial / p["volume_pL"] / p["bath_mM"]) - 1)
            + amount * np.log1p(delta / initial),
            axis=1,
        )
    )
    dv = QF / capacitance * np.sum(delta * z, axis=1)
    electric = 0.5e12 * capacitance * dv * (2 * p["initial_voltage_V"] + dv)
    supplied = -1e-3 * p["drive_J_per_mol"] * cycles
    energy_error = float(np.max(np.abs(chemical + electric + dissipation - supplied)))
    charge_error = float(np.max(np.abs(charge)))
    decrease = max(0.0, -float(np.min(np.diff(dissipation), initial=0)))
    scores = [
        charge_error / limits["charge_as_voltage_V"],
        energy_error / limits["energy_pJ"],
        decrease / limits["dissipation_decrease_pJ"],
    ]
    scores.extend(
        error / limits["species_material_overrides_fmol"].get(s, limits["material_fmol"])
        for s, error in material_errors.items()
    )
    return {
        "material_residual_fmol": material_errors,
        "charge_residual_V": charge_error,
        "energy_residual_pJ": energy_error,
        "dissipation_decrease_pJ": decrease,
        "minimum_amount_fmol": float(np.min(amount)),
        "max_abs_x": max_x,
        "voltage_range_V": [float(np.min(v)), float(np.max(v))],
        "max_normalized_residual": max(scores),
        "pass": max(scores) <= 1,
    }


def control_checks(case, times, values):
    count = len(case["parameters"]["species_ids"])
    results = []
    for i, control in enumerate(case["controls"]):
        end = (
            case["controls"][i + 1]["time_s"]
            if i + 1 < len(case["controls"])
            else case["horizon_s"]
        )
        if end == control["time_s"]:
            continue
        subset = values[(times >= control["time_s"]) & (times <= end)]
        require(len(subset) >= 2, "Control interval missing its endpoints")
        selected = [count + s for s, u in enumerate(control["leak"]) if u == 0]
        if control["pump"] == 0:
            selected.append(2 * count)
        unchanged = np.array_equal(
            subset[:, selected], np.broadcast_to(subset[0, selected], (len(subset), len(selected)))
        )
        if control["pump"] == 0 and all(u == 0 for u in control["leak"]):
            unchanged = unchanged and np.array_equal(
                subset, np.broadcast_to(subset[0], subset.shape)
            )
        results.append(
            {"start_s": control["time_s"], "end_s": end, "disabled_ledgers_exact": unchanged}
        )
    return {"intervals": results, "pass": all(item["disabled_ledgers_exact"] for item in results)}


def candidate_polynomial_domain(case, arrays):
    p, z, initial, _ = parameters(case)
    count, capacitance = len(initial), p["area_m2"] * p["specific_capacitance_F_per_m2"]
    minimum, max_voltage, extrema_checked = math.inf, 0.0, 0
    for coeff in arrays["coefficients"]:
        v_coeff = QF / capacitance * np.sum(z[:, None] * coeff[:count, :4], axis=0)
        # Use anchor increments in the constant coefficient to limit cancellation.
        v_coeff[0] = p["initial_voltage_V"] + QF / capacitance * np.sum(
            z * (coeff[:count, 0] - initial)
        )
        for slot, row in enumerate([*coeff[:count, :4], v_coeff]):
            roots = np.polynomial.polynomial.polyroots([row[1], 2 * row[2], 3 * row[3]])
            nodes = [0.0, 1.0] + [
                float(r.real) for r in roots if abs(r.imag) <= 1e-12 and 0 < r.real < 1
            ]
            extrema_checked += len(nodes)
            values = np.polynomial.polynomial.polyval(nodes, row)
            require(np.isfinite(values).all(), "Nonfinite cubic domain bound")
            if slot == count:
                max_voltage = max(max_voltage, float(np.max(np.abs(values))))
            else:
                minimum = min(minimum, float(np.min(values)))
    max_x = float(max(abs(z)) * F * max_voltage / (R * p["temperature_K"]))
    return {
        "minimum_amount_fmol": minimum,
        "max_abs_x": max_x,
        "extrema_checked": extrema_checked,
        "pass": minimum > 0 and max_x <= 50,
    }


def validate_record(case, arrays, kind):
    required = {
        "native_times_s",
        "native_state",
        "coefficients",
        "degree",
        "shift",
        "denominator",
        "sample_times_s",
        "sample_state",
    }
    require(set(arrays) == required, "Unexpected recorded array members")
    require(
        all(
            v.dtype == (np.dtype("int64") if name == "degree" else np.dtype("float64"))
            for name, v in arrays.items()
        ),
        "Records require float64 state and int64 degrees",
    )
    require(all(np.isfinite(a).all() for a in arrays.values()), "Nonfinite recorded array")
    times = arrays["native_times_s"]
    steps, size = len(times) - 1, 2 * len(case["parameters"]["species_ids"]) + 2
    require(
        0 < steps <= 100000
        and np.all(np.diff(times) > 0)
        and times[0] == 0
        and times[-1] == case["horizon_s"],
        "Incomplete native trajectory",
    )
    require(
        arrays["native_state"].shape == (steps + 1, size)
        and arrays["coefficients"].shape == (steps, size, 6)
        and arrays["degree"].shape == (steps,)
        and arrays["degree"].dtype.kind in "iu"
        and arrays["shift"].shape == (steps, 5)
        and arrays["denominator"].shape == (steps, 5),
        "Invalid dense record shape",
    )
    degree = arrays["degree"]
    require(np.all((degree >= 1) & (degree <= 5)), "Invalid polynomial degree")
    if kind != "BDF":
        require(
            kind in ("Radau", "RK4") and np.all(degree == 3), "Invalid cubic record kind/degree"
        )
    require(np.all(arrays["denominator"] > 0), "Invalid interpolation denominator")
    sample = arrays["sample_times_s"]
    require(
        sample.ndim == 1
        and 1 < len(sample) <= 100000
        and np.all(np.diff(sample) > 0)
        and sample[0] == 0
        and sample[-1] == case["horizon_s"],
        "Invalid comparison times",
    )
    require(arrays["sample_state"].shape == (len(sample), size), "Invalid comparison state shape")
    initial = np.zeros(size)
    if kind == "RK4":
        initial[: len(case["parameters"]["species_ids"])] = case["parameters"][
            "initial_amount_fmol"
        ]
    require(
        np.array_equal(arrays["native_state"][0], initial),
        "Initial state/ledgers do not match case",
    )
    for control in case["controls"]:
        require(control["time_s"] in times and control["time_s"] in sample, "Control boundary lost")


def expected_grid(case, candidate):
    pieces = []
    for dt in candidate["steps_s"]:
        times = np.unique(
            np.r_[
                np.arange(math.ceil(case["horizon_s"] / dt)) * dt,
                [c["time_s"] for c in case["controls"]],
                case["horizon_s"],
            ]
        )
        pieces.append(times)
        pieces.extend(
            times[:-1] + fraction * np.diff(times) for fraction in candidate["comparison_fractions"]
        )
    return np.unique(np.concatenate(pieces))


def analyze_case(case, records, plan):
    names = [s["id"] for s in plan["references"]] + [
        f"rk4_{dt:g}" for dt in plan["candidate"]["steps_s"]
    ]
    require(set(records) == set(names), "Missing or unexpected numerical attempts")
    grid = expected_grid(case, plan["candidate"])
    output = {"attempts": {}, "reference_comparisons": {}}
    oracle = records["refined"]["sample_state"]
    for name, arrays in records.items():
        kind = (
            "RK4"
            if name.startswith("rk4_")
            else next(s["method"] for s in plan["references"] if s["id"] == name)
        )
        validate_record(case, arrays, kind)
        require(
            np.array_equal(grid, arrays["sample_times_s"]),
            "Comparison grid differs from frozen plan",
        )
        native = canonical_native(case, arrays, kind)
        native_check = inspect_samples(
            case, arrays["native_times_s"], native, plan["accounting_limits"]
        )
        sampled_check = inspect_samples(
            case, grid, arrays["sample_state"], plan["accounting_limits"]
        )
        controls = control_checks(case, grid, arrays["sample_state"])
        entry = {
            "native_accounting": native_check,
            "sampled_accounting": sampled_check,
            "controls": controls,
        }
        entry["pass"] = native_check["pass"] and sampled_check["pass"] and controls["pass"]
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
                entry[key]["pass"]
                for key in ("accepted_comparison", "observed_comparison", "polynomial_domain")
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
    ) and all(v["pass"] for v in output["reference_comparisons"].values())
    return output


def select_candidate(analyses, plan):
    references_pass = len(analyses) == len(plan["cases"]) and all(
        a["references_pass"] for a in analyses.values()
    )
    steps, candidate = plan["candidate"]["steps_s"], plan["candidate"]
    eligible, selected = [], None
    for coarse, fine in zip(steps[:-1], steps[1:], strict=True):
        checks = []
        for name, analysis in analyses.items():
            first, second = (analysis["attempts"][f"rk4_{dt:g}"] for dt in (coarse, fine))
            e1, e2 = (
                entry["observed_comparison"]["errors"]["voltage_V"] for entry in (first, second)
            )
            refinement = (
                e1 <= candidate["voltage_refinement_floor_V"]
                or e2 <= candidate["maximum_refined_voltage_error_ratio"] * e1
            )
            checks.append(
                {
                    "case": name,
                    "coarse_pass": first["pass"],
                    "fine_pass": second["pass"],
                    "voltage_refinement_pass": refinement,
                }
            )
        passed = references_pass and all(
            c["coarse_pass"] and c["fine_pass"] and c["voltage_refinement_pass"] for c in checks
        )
        eligible.append({"dt_s": coarse, "refined_dt_s": fine, "pass": passed, "cases": checks})
        if passed and selected is None:
            selected = coarse
    return {
        "status": "pass" if selected is not None else "not_qualified",
        "references_pass": references_pass,
        "selected_dt_s": selected,
        "eligibility": eligible,
    }
