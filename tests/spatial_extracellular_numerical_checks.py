"""NUM-010 data-only replay, physical accounting and prospective verdicts.

No integrator imports. Reconstruct fields from full inventory, not interpolated
voltages or saved success flags. The independent outside-node equations are used
only as an instantaneous field evaluator, never to rerun a trajectory.
"""

import math

import numpy as np

from tests import spatial_extracellular_fields as fields
from tests import spatial_extracellular_numerical_data as data


def require(condition, message):
    if not condition:
        raise ValueError(message)


def maximum(value):
    return float(np.max(np.abs(value), initial=0))


def replay(case, arrays, kind, times):
    sample = np.asarray(times, dtype=float)
    native = arrays["native_times_s"]
    require(
        sample.ndim == 1 and np.all(np.isfinite(sample)) and np.all(np.diff(sample) >= 0),
        "Invalid dense query times",
    )
    require(len(sample) <= 50000, "Dense query budget exceeded")
    require(
        not len(sample) or (sample[0] >= native[0] and sample[-1] <= native[-1]),
        "Dense query outside saved interval",
    )
    if len(native) == 1:
        require(np.all(sample == native[0]), "No dense interval in empty prefix")
        return np.broadcast_to(arrays["native_state"][0], (len(sample), case.size)).copy()
    slots = np.clip(np.searchsorted(native, sample, side="right") - 1, 0, len(native) - 2)
    result = np.empty((len(sample), case.size))
    for slot in np.unique(slots):
        selected = np.flatnonzero(slots == slot)
        ts, degree = sample[selected], int(arrays["degree"][slot])
        c = arrays["coefficients"][slot, :, : degree + 1]
        if kind == "BDF":
            x = (ts - arrays["shift"][slot, :degree, None]) / arrays["denominator"][
                slot, :degree, None
            ]
            values = c[:, 0, None] + c[:, 1:] @ np.cumprod(x, axis=0)
        elif kind in {"RK4", "Radau"}:
            theta = (ts - native[slot]) / (native[slot + 1] - native[slot])
            values = c[:, -1, None] * np.ones((1, len(ts)))
            for power in range(degree - 1, -1, -1):
                values = c[:, power, None] + theta * values
        else:
            raise ValueError("Unknown recorded dense basis")
        result[selected] = values.T
    at = np.searchsorted(native, sample)
    exact = native[at] == sample
    result[exact] = arrays["native_state"][at[exact]]
    return result


def validate_record(case, arrays, stats, *, start=0.0):
    require(
        type(stats["rhs_calls"]) is int
        and 0 <= stats["rhs_calls"] <= 100000
        and math.isfinite(stats["seconds"])
        and stats["seconds"] >= 0
        and stats["minimum_trial_amount_fmol"] > 0
        and 0 <= stats["maximum_trial_abs_x"] <= 50
        and 0 <= stats["maximum_current_normalized"] <= 1
        and 0 <= stats["maximum_charge_C"] <= 1e-20
        and stats["maximum_current_residual_A"] >= 0,
        "Invalid actual-trial or attempt resource summary",
    )
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
        "Record fields changed",
    )
    require(all(np.isfinite(a).all() for a in arrays.values()), "Nonfinite saved data")
    require(
        all(
            a.dtype == (np.dtype("int64") if k == "degree" else np.dtype("float64"))
            for k, a in arrays.items()
        ),
        "Saved coordinate dtype changed",
    )
    times, state = arrays["native_times_s"], arrays["native_state"]
    steps = len(times) - 1
    require(
        0 <= steps <= 100000 and times[0] == start and np.all(np.diff(times) > 0),
        "Invalid native mesh",
    )
    require(
        state.shape == (steps + 1, case.size)
        and arrays["coefficients"].shape == (steps, case.size, 6)
        and arrays["degree"].shape == (steps,)
        and arrays["shift"].shape == arrays["denominator"].shape == (steps, 5),
        "Incomplete native/dense coordinates",
    )
    require(stats["accepted_steps"] == steps, "Native step count changed")
    require(times[-1] <= case.horizon_s, "Native mesh exceeds horizon")
    require(
        all(c.time_s in times for c in case.controls if start <= c.time_s <= times[-1]),
        "A native step crossed a control event",
    )
    if start == 0:
        require(np.array_equal(state[0], data.initial_state(case)), "Initial state changed")
    degree, method = arrays["degree"], stats["method"]
    require(
        method in {"RK4", "Radau", "BDF"} and np.all((degree >= 1) & (degree <= 5)),
        "Invalid dense degree or method",
    )
    if method != "BDF":
        require(np.all(degree == 3), "Expected cubic dense basis")
        require(
            np.all(arrays["shift"] == 0) and np.all(arrays["denominator"] == 1),
            "Unexpected cubic basis metadata",
        )
    else:
        require(np.all(arrays["denominator"] > 0), "Invalid Newton denominators")
    for i, deg in enumerate(degree):
        require(np.all(arrays["coefficients"][i, :, deg + 1 :] == 0), "Nonzero unused coefficients")
        if method == "BDF":
            require(
                np.all(arrays["shift"][i, deg:] == 0)
                and np.all(arrays["denominator"][i, deg:] == 1),
                "Unexpected unused Newton metadata",
            )
            x = (times[i : i + 2] - arrays["shift"][i, :deg, None]) / arrays["denominator"][
                i, :deg, None
            ]
            c = arrays["coefficients"][i, :, : deg + 1]
            endpoints = (c[:, 0, None] + c[:, 1:] @ np.cumprod(x, axis=0)).T
        else:
            c = arrays["coefficients"][i]
            endpoints = np.stack([c[:, 0], np.sum(c, axis=1)])
        scale = np.maximum(1.0, np.sum(np.abs(arrays["coefficients"][i]), axis=1))
        require(
            np.all(np.abs(endpoints - state[i : i + 2]) <= 64 * np.finfo(float).eps * scale),
            "Saved dense polynomial disagrees with native endpoints",
        )
    if method == "RK4":
        grid = data.candidate_grid(case, stats["dt_s"], start=start)
        require(np.array_equal(times, grid[: len(times)]), "Candidate grid changed")
        require(
            stats["rhs_calls"] == 5 * steps + stats["rejected_rhs_calls"],
            "Candidate stage accounting changed",
        )
    else:
        require(
            np.all(np.diff(times) <= stats["max_step_s"] + 2 * np.finfo(float).eps),
            "Implicit step cap exceeded",
        )
        require(
            stats["rhs_calls"] == stats["nfev"] + stats["jacobian_rhs_calls"],
            "Implicit RHS/Jacobian accounting changed",
        )
        columns = stats["central_columns"] + stats["one_sided_columns"]
        require(
            stats["jacobian_rhs_calls"] == stats["jacobian_evaluations"] + 2 * columns,
            "Missing tangent derivative probes",
        )
        require(
            columns + stats["zero_tangent_columns"]
            == stats["jacobian_evaluations"] * case.layout.amount_count,
            "Missing tangent columns",
        )
    samples = arrays["sample_times_s"]
    require(
        samples.ndim == 1
        and len(samples) <= 50000
        and np.all(np.diff(samples) > 0)
        and arrays["sample_state"].shape == (len(samples), case.size),
        "Invalid observation shape",
    )
    require(
        np.array_equal(replay(case, arrays, method, samples), arrays["sample_state"]),
        "Observation does not replay exactly",
    )
    if stats["status"] == "complete":
        require(times[-1] == case.horizon_s, "Incomplete successful trajectory")
        expected = data.observations(case)
        require(np.array_equal(samples, expected[expected >= start]), "Common sample grid changed")
        require(stats["rejected_trial"] is None, "Complete trajectory has a rejected trial")
    else:
        require(
            stats["status"] == "rejected" and method == "RK4" and not len(samples),
            "Unexpected rejected record",
        )
        require(
            stats["rejected_trial"] is not None and times[-1] < case.horizon_s,
            "Missing rejection evidence",
        )
    require(
        stats["maximum_current_normalized"] <= 1 and stats["maximum_charge_C"] <= 1e-20,
        "Accepted actual trial exceeded constraints",
    )


def energy_change(case, values):
    p, g = case.layout.split(values), case.g
    delta, initial = p["amount"], g.initial
    chemical = (
        1e-3
        * data.R
        * g.temperature
        * np.sum(
            delta * (np.log(initial / g.volume[:, None]) - 1)
            + (initial + delta) * np.log1p(delta / initial),
            axis=(-2, -1),
        )
    )
    inside = [u for u, _ in g.membrane_pairs]
    dv = data.QF * np.sum(delta[..., inside, :] * g.z, axis=-1) / g.capacitance
    v0 = np.asarray([m["initial_voltage_V"] for m in case.raw["world"]["membranes"]])
    electric = 0.5e12 * np.sum(g.capacitance * dv * (2 * v0 + dv), axis=-1)
    return chemical + electric


def potential_values(case, times, values):
    result, current, charge = [], 0.0, 0.0
    for t, y in zip(times, values, strict=True):
        _, metrics = fields.independent(case, case.control_at(float(t)), y)
        result.append(metrics["potential_V"])
        current = max(current, metrics["current_normalized"])
        charge = max(charge, metrics["max_component_charge_C"], metrics["max_capacitor_residual_C"])
    return np.asarray(result).reshape(len(values), len(case.g.ids)), current, charge


def inspect(case, times, values, limits):
    require(
        values.shape == (len(times), case.size) and np.all(np.isfinite(values)),
        "Invalid inspected states",
    )
    p, g = case.layout.split(values), case.g
    amount = g.initial + p["amount"]
    if not np.all(amount > 0):
        raise fields.DomainViolation("Nonpositive inspected inventory")
    material = p["amount"] + np.einsum("nm,tms->tns", g.bm, p["membrane_transfer"])
    material += np.einsum("ne,tes->tns", g.bf, p["face_transfer"])
    material_residual = max(maximum(material), maximum(np.sum(p["amount"], axis=1)))
    dissipation = np.concatenate([p["membrane_dissipation"], p["face_dissipation"]], axis=1)
    energy_residual = maximum(energy_change(case, values) + np.sum(dissipation, axis=1))
    decrease = max(0.0, -float(np.min(np.diff(dissipation, axis=0), initial=0)))
    phi, current, charge = potential_values(case, times, values)
    score = max(
        material_residual / limits["material_fmol"],
        charge / limits["charge_C"],
        current,
        energy_residual / limits["energy_pJ"],
        decrease / limits["dissipation_decrease_pJ"],
    )
    return {
        "pass": score <= 1,
        "maximum_normalized_residual": score,
        "material_residual_fmol": material_residual,
        "charge_residual_C": charge,
        "maximum_current_normalized": current,
        "energy_residual_pJ": energy_residual,
        "dissipation_decrease_pJ": decrease,
        "minimum_amount_fmol": float(np.min(amount)),
    }, phi


def errors(case, actual, expected, actual_phi, expected_phi, limits, factor=1.0):
    require(
        actual.shape == expected.shape
        and np.all(np.isfinite(actual))
        and np.all(np.isfinite(expected)),
        "Invalid comparison coordinates",
    )
    p, g = case.layout.split(actual - expected), case.g
    actual_vm, expected_vm = actual_phi @ g.bm, expected_phi @ g.bm
    result = {
        "amount_and_transfer_fmol": max(
            maximum(p[k]) for k in ("amount", "membrane_transfer", "face_transfer")
        ),
        "concentration_mM": maximum(p["amount"] / g.volume[:, None]),
        "potential_V": max(maximum(actual_phi - expected_phi), maximum(actual_vm - expected_vm)),
        "dissipation_pJ": max(maximum(p["membrane_dissipation"]), maximum(p["face_dissipation"])),
    }
    score = max(value / (limits[key] * factor) for key, value in result.items())
    return {"errors": result, "maximum_normalized_error": score, "pass": score <= 1}


def blocked_checks(case, times, values):
    results, g = [], case.g
    for i, control in enumerate(case.controls):
        end = case.controls[i + 1].time_s if i + 1 < len(case.controls) else case.horizon_s
        if end == control.time_s:
            continue
        subset = values[(times >= control.time_s) & (times <= end)]
        require(len(subset) >= 2, "Blocked interval missing endpoints")
        p = case.layout.split(subset)
        valid = True
        for e, available in enumerate(control.availability):
            if available == 0:
                u = g.membrane_pairs[e][0]
                for array in (
                    p["amount"][:, u],
                    p["membrane_transfer"][:, e],
                    p["membrane_dissipation"][:, e],
                ):
                    valid = valid and np.array_equal(array, np.broadcast_to(array[0], array.shape))
        if not g.face_pairs and all(a == 0 for a in control.availability):
            valid = valid and np.array_equal(subset, np.broadcast_to(subset[0], subset.shape))
        results.append({"start_s": control.time_s, "end_s": end, "exact": bool(valid)})
    return {"pass": all(r["exact"] for r in results), "intervals": results}


def extrema(row):
    roots = np.polynomial.polynomial.polyroots([row[1], 2 * row[2], 3 * row[3]])
    nodes = [0.0, 1.0] + [float(r.real) for r in roots if abs(r.imag) <= 1e-12 and 0 < r.real < 1]
    values = np.polynomial.polynomial.polyval(nodes, row)
    require(np.all(np.isfinite(values)), "Nonfinite cubic extremum")
    return float(np.min(values)), float(np.max(values)), len(nodes)


def cubic_domain(case, arrays):
    minimum, max_x, max_charge, count, constant = math.inf, 0.0, 0.0, 0, True
    g, layout = case.g, case.layout
    for i, c in enumerate(arrays["coefficients"]):
        rows = c[: layout.amount_count, :4].reshape(len(g.ids), len(g.z), 4).copy()
        rows[:, :, 0] += g.initial
        for row in rows.reshape(-1, 4):
            lo, _, checked = extrema(row)
            minimum, count = min(minimum, lo), count + checked
        delta = c[: layout.amount_count, :4].reshape(len(g.ids), len(g.z), 4)
        for m, (u, _) in zip(case.raw["world"]["membranes"], g.membrane_pairs, strict=True):
            row = data.QF / m["capacitance_F"] * np.sum(delta[u] * g.z[:, None], axis=0)
            row[0] += m["initial_voltage_V"]
            lo, hi, checked = extrema(row)
            max_x = max(
                max_x, max(abs(lo), abs(hi)) * max(abs(g.z)) * data.F / (data.R * g.temperature)
            )
            count += checked
        q = data.QF * np.einsum("kn,nsp,s->kp", g.p.T, delta, g.z)
        q[:, 0] += g.p.T @ g.initial_charge
        for row in q:
            lo, hi, checked = extrema(row)
            max_charge, count = max(max_charge, abs(lo), abs(hi)), count + checked
        control = case.control_at(float(arrays["native_times_s"][i]))
        for e, availability in enumerate(control.availability):
            if availability == 0:
                u, s = g.membrane_pairs[e][0], len(g.z)
                indices = [
                    *range(u * s, (u + 1) * s),
                    *range(
                        layout.slices["membrane_transfer"].start + e * s,
                        layout.slices["membrane_transfer"].start + (e + 1) * s,
                    ),
                    layout.slices["membrane_dissipation"].start + e,
                ]
                constant = constant and np.all(c[indices, 1:] == 0)
    return {
        "pass": bool(minimum > 0 and max_x <= 50 and max_charge <= 1e-20 and constant),
        "minimum_amount_fmol": minimum if count else None,
        "maximum_abs_x": float(max_x),
        "maximum_component_charge_C": max_charge,
        "extrema_checked": count,
        "blocked_polynomials_constant": bool(constant),
    }


def analytic_values(case, times, *, discrete=False):
    """Closed-form concentration and derived gauge potential, not an ODE solve."""
    g, ts = case.g, np.asarray(times)
    initial = g.initial / g.volume[:, None]
    concentration = np.broadcast_to(initial, (len(ts), *initial.shape)).copy()
    phi = np.zeros((len(ts), len(g.ids)))
    kind = case.raw["analytic_kind"]
    if kind == "binary_relaxation":
        require(
            len(g.face_pairs) == 1
            and tuple(g.z) == (1, -1)
            and all(all(a == 0 for a in c.availability) for c in case.controls),
            "Invalid binary analytic reduction",
        )
        u, v = g.face_pairs[0]
        face = case.raw["world"]["faces"][0]
        dp, dm = face["diffusivity_m2_per_s"]
        vu, vv = g.volume[u], g.volume[v]
        cu, cv = initial[u, 0], initial[v, 0]
        require(np.all(initial[u] == cu) and np.all(initial[v] == cv), "Not a binary salt state")
        coefficient = face["area_m2"] / (data.A * face["length_m"]) * 2 * dp * dm / (dp + dm)
        contrast = (cu - cv) * np.exp(-coefficient * (1 / vu + 1 / vv) * ts)
        mean = (vu * cu + vv * cv) / (vu + vv)
        concentration[:, u] = (mean + vv / (vu + vv) * contrast)[:, None]
        concentration[:, v] = (mean - vu / (vu + vv) * contrast)[:, None]
        phi[:, u] = (
            -data.R
            * g.temperature
            / data.F
            * (dp - dm)
            / (dp + dm)
            * np.log(concentration[:, u, 0] / concentration[:, v, 0])
        )
        for m, (inside, outside) in zip(
            case.raw["world"]["membranes"], g.membrane_pairs, strict=True
        ):
            phi[:, inside] = phi[:, outside] + m["initial_voltage_V"]
    elif kind == "cosine_line":
        mesh = case.raw["mesh_parameters"]
        count, length = mesh["volumes"], mesh["length_m"]
        dp, dm = mesh["diffusivities_m2_per_s"]
        diffusion, dx = 2 * dp * dm / (dp + dm), length / count
        eigenvalue = (
            4 * diffusion / dx**2 * math.sin(math.pi / (2 * count)) ** 2
            if discrete
            else diffusion * math.pi**2 / length**2
        )
        cell_average = np.sinc(1 / (2 * count)) * np.cos(math.pi * (np.arange(count) + 0.5) / count)
        profile = (
            mesh["mean_mM"]
            + mesh["amplitude_mM"] * np.exp(-eigenvalue * ts[:, None]) * cell_average
        )
        concentration[:] = profile[:, :, None]
        phi[:] = (
            -data.R
            * g.temperature
            / data.F
            * (dp - dm)
            / (dp + dm)
            * np.log(profile / profile[:, -1, None])
        )
    else:
        raise ValueError("No analytic trajectory is declared")
    phi -= phi[:, -1, None]
    return concentration, phi


def analytic_check(case, arrays, limits):
    kind = case.raw["analytic_kind"]
    if kind is None:
        return {"required": False, "pass": True}
    ts, y = arrays["sample_times_s"], arrays["sample_state"]
    actual = (case.g.initial + case.layout.split(y)["amount"]) / case.g.volume[:, None]
    phi, _, _ = potential_values(case, ts, y)
    exact, exact_phi = analytic_values(case, ts, discrete=kind == "cosine_line")
    error, voltage_error = maximum(actual - exact), maximum(phi - exact_phi)
    score = max(
        error / (limits["concentration_mM"] * limits["reference_factor"]),
        voltage_error / (limits["potential_V"] * limits["reference_factor"]),
    )
    result = {
        "required": True,
        "pass": score <= 1,
        "semidiscrete_or_two_volume_error_mM": error,
        "potential_error_V": voltage_error,
        "maximum_normalized_error": score,
    }
    if kind == "cosine_line":
        continuum, _ = analytic_values(case, ts)
        result["continuum_error_mM"] = maximum(actual - continuum)
    else:
        u, v = case.g.face_pairs[0]
        result["contrast_fraction_decrease"] = float(
            1 - (actual[-1, u, 0] - actual[-1, v, 0]) / (actual[0, u, 0] - actual[0, v, 0])
        )
    return result


def analyze_case(case, records, stats, plan):
    reference = records["refined"]
    limits, accounting = plan["trajectory_limits"], plan["accounting_limits"]
    comparison, native, observed, controls, cubic = {}, {}, {}, {}, {}
    # The refined field trajectory is reconstructed from its saved inventories.
    reference_phi, _, _ = potential_values(
        case, reference["sample_times_s"], reference["sample_state"]
    )
    for name, arrays in records.items():
        settings = stats[name]
        validate_record(case, arrays, settings)
        if settings["status"] != "complete":
            comparison[name] = {"pass": False, "status": settings["status"]}
            continue
        try:
            native[name], native_phi = inspect(
                case, arrays["native_times_s"], arrays["native_state"], accounting
            )
            observed[name], sample_phi = inspect(
                case, arrays["sample_times_s"], arrays["sample_state"], accounting
            )
            controls[name] = {
                "native": blocked_checks(case, arrays["native_times_s"], arrays["native_state"]),
                "observed": blocked_checks(case, arrays["sample_times_s"], arrays["sample_state"]),
            }
            expected = replay(case, reference, "Radau", arrays["native_times_s"])
            expected_phi, _, _ = potential_values(case, arrays["native_times_s"], expected)
            factor = (
                limits["reference_factor"] if name in {s["id"] for s in plan["references"]} else 1.0
            )
            endpoint = errors(
                case, arrays["native_state"], expected, native_phi, expected_phi, limits, factor
            )
            observation = errors(
                case,
                arrays["sample_state"],
                reference["sample_state"],
                sample_phi,
                reference_phi,
                limits,
                factor,
            )
            cubic[name] = (
                cubic_domain(case, arrays)
                if settings["method"] == "RK4"
                else {"pass": True, "not_required": True}
            )
            valid = (
                native[name]["pass"]
                and observed[name]["pass"]
                and endpoint["pass"]
                and observation["pass"]
                and cubic[name]["pass"]
                and all(c["pass"] for c in controls[name].values())
            )
            comparison[name] = {
                "pass": bool(valid),
                "status": "complete",
                "native": endpoint,
                "observed": observation,
            }
        except fields.DomainViolation as exc:
            if settings["method"] != "RK4":
                raise
            comparison[name] = {
                "pass": False,
                "status": "completed_invalid_dense_domain",
                "reason": str(exc),
            }
    analytic = analytic_check(case, reference, limits)
    return {
        "references_pass": all(comparison[s["id"]]["pass"] for s in plan["references"])
        and analytic["pass"],
        "comparisons": comparison,
        "native_accounting": native,
        "observed_accounting": observed,
        "controls": controls,
        "cubic": cubic,
        "analytic": analytic,
    }


def select_candidate(analyses, plan):
    steps, decisions, selected = plan["candidate"]["steps_s"], [], None
    for coarse, fine in zip(steps[:-1], steps[1:], strict=True):
        a, b = f"rk4_{coarse:g}", f"rk4_{fine:g}"
        per_case = {}
        for name, analysis in analyses.items():
            first, second = analysis["comparisons"][a], analysis["comparisons"][b]
            valid = first["pass"] and second["pass"]
            ratios = {}
            if valid:
                for key, floor in (
                    ("concentration_mM", plan["candidate"]["concentration_floor_mM"]),
                    ("potential_V", plan["candidate"]["potential_floor_V"]),
                ):
                    c, f = first["observed"]["errors"][key], second["observed"]["errors"][key]
                    ratio = f / c if c else (0.0 if f == 0 else None)
                    ratios[key] = ratio
                    valid = valid and (
                        max(c, f) <= floor
                        or (ratio is not None and ratio <= plan["candidate"]["refinement_ratio"])
                    )
            per_case[name] = {"pass": bool(valid), "ratios": ratios}
        passed = all(v["pass"] for v in per_case.values())
        decisions.append(
            {"coarse_dt_s": coarse, "fine_dt_s": fine, "pass": passed, "cases": per_case}
        )
        if selected is None and passed:
            selected = coarse
    return {
        "status": "qualified" if selected is not None else "not_qualified",
        "selected_dt_s": selected,
        "selection_checks": decisions,
    }


def spatial_and_relaxation_checks(analyses, plan):
    errors = [analyses[f"line_{n}"]["analytic"]["continuum_error_mM"] for n in (8, 16, 32)]
    ratios = [b / a for a, b in zip(errors[:-1], errors[1:], strict=True)]
    spatial = {
        "errors_mM": errors,
        "ratios": ratios,
        "pass": max(ratios) <= plan["spatial_limits"]["refinement_ratio"]
        and errors[-1] <= plan["spatial_limits"]["finest_concentration_error_mM"],
    }
    witness = plan["relaxation_witness"]
    decrease = analyses[witness["case"]]["analytic"]["contrast_fraction_decrease"]
    return {
        "spatial": spatial,
        "salt_relaxation": {
            "contrast_fraction_decrease": decrease,
            "pass": decrease >= witness["minimum_contrast_fraction_decrease"],
        },
    }
