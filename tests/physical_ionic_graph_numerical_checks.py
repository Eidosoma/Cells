"""NUM-008 data-only trajectory/domain/accounting checks; never run an ODE.

Physics identities are expressed on saved coordinates, not by calling either
transport evaluator. The importer below resolves data and layout only.
"""

import math

import numpy as np

from tests import multispecies_numerical_checks as old
from tests import physical_ionic_graph_numerical_data as data

require = old.require


def geometry(case):
    cells = case["graph"]["cells"]
    ids = [p["cell_id"] for p in cells]
    return {
        "initial": np.asarray([p["initial_amount_fmol"] for p in cells]),
        "z": np.asarray(cells[0]["valence"]),
        "v0": np.asarray([p["initial_voltage_V"] for p in cells]),
        "cap": np.asarray([p["area_m2"] * p["specific_capacitance_F_per_m2"] for p in cells]),
        "volume": np.asarray([p["volume_pL"] for p in cells]),
        "bath": np.asarray(cells[0]["bath_mM"]),
        "rt": data.R * cells[0]["temperature_K"],
        "channel_cells": [ids.index(c["assembly"]["cell_id"]) for c in case["graph"]["channels"]],
        "endpoints": [
            (ids.index(e["from_cell"]), ids.index(e["to_cell"])) for e in case["graph"]["junctions"]
        ],
    }


def voltage(case, delta):
    g = geometry(case)
    return g["v0"] + data.QF / g["cap"] * np.sum(delta * g["z"], axis=-1)


def canonical_native(case, arrays, kind):
    result = arrays["native_state"].copy()
    if kind == "RK4":
        result[:, : data.layout(case).amount_count] -= geometry(case)["initial"].ravel()
    return result


def maximum(value):
    return float(np.max(np.abs(value), initial=0))


def errors(case, actual, expected, limits, *, factor=1.0):
    require(
        actual.shape == expected.shape
        and np.isfinite(actual).all()
        and np.isfinite(expected).all(),
        "Invalid comparison arrays",
    )
    layout = data.layout(case)
    a, b = layout.split(actual), layout.split(expected)
    result, scores = {}, []
    for field, key in (
        ("amount", "amount_fmol"),
        ("leak_transferred", "leak_fmol"),
        ("junction_transferred", "junction_fmol"),
    ):
        result[key] = {}
        for s, species in enumerate(case["graph"]["cells"][0]["species_ids"]):
            error = maximum(a[field][..., s] - b[field][..., s])
            result[key][species] = error
            limit = limits["species_overrides"].get(species, {}).get(key, limits[key])
            scores.append(error / (factor * limit))
    for field, key in (
        ("pump_cycles", "pump_cycles_fmol"),
        ("membrane_dissipated_energy_pJ", "membrane_dissipation_pJ"),
        ("membrane_gate", "membrane_gate"),
        ("channel_transferred", "channel_fmol"),
        ("junction_gate", "junction_gate"),
        ("junction_dissipated_energy_pJ", "junction_dissipation_pJ"),
    ):
        result[key] = maximum(a[field] - b[field])
        scores.append(result[key] / (factor * limits[key]))
    result["voltage_V"] = maximum(voltage(case, a["amount"]) - voltage(case, b["amount"]))
    result["open_fraction"] = maximum(
        np.prod(a["membrane_gate"], axis=-1) - np.prod(b["membrane_gate"], axis=-1)
    )
    for key in ("voltage_V", "open_fraction"):
        scores.append(result[key] / (factor * limits[key]))
    return {"errors": result, "max_normalized_error": max(scores), "pass": max(scores) <= 1}


def domain_summary(case, values):
    p, g = data.layout(case).split(values), geometry(case)
    amount = p["amount"] + g["initial"]
    volts = voltage(case, p["amount"])
    edge_v = (
        np.stack([volts[:, a] - volts[:, b] for a, b in g["endpoints"]], axis=1)
        if g["endpoints"]
        else np.empty((len(values), 0))
    )
    local_x = maximum(volts[..., None] * g["z"] * data.F / g["rt"])
    edge_x = maximum(edge_v[..., None] * g["z"] * data.F / g["rt"])
    gates = np.concatenate(
        (p["membrane_gate"].reshape(len(values), -1), p["junction_gate"]), axis=1
    )
    gate_lo, gate_hi = float(np.min(gates, initial=1)), float(np.max(gates, initial=0))
    channel_v = volts[:, g["channel_cells"]]
    channel_range = [float(np.min(channel_v)), float(np.max(channel_v))] if channel_v.size else None
    finite = bool(
        np.isfinite(values).all() and np.isfinite(amount).all() and np.isfinite(volts).all()
    )
    absent_pump = all(
        c["pump_id"] is not None or np.all(p["pump_cycles"][:, i] == 0)
        for i, c in enumerate(case["graph"]["cells"])
    )
    passed = (
        finite
        and bool(np.all(amount > 0))
        and local_x <= 50
        and edge_x <= 50
        and gate_lo >= 0
        and gate_hi <= 1
        and absent_pump
    )
    if channel_range is not None:
        passed = passed and -0.120 <= channel_range[0] <= channel_range[1] <= 0.060
    return {
        "pass": passed,
        "minimum_amount_fmol": float(np.min(amount)),
        "max_abs_x": local_x,
        "max_edge_abs_x": edge_x,
        "gate_range": [min(gate_lo, gate_hi), gate_hi],
        "voltage_range_V": [float(np.min(volts)), float(np.max(volts))],
        "channel_voltage_range_V": channel_range,
    }


def inspect_samples(case, times, values, limits):
    require(
        values.shape == (len(times), data.layout(case).size) and np.isfinite(values).all(),
        "Invalid finite graph samples",
    )
    require(
        len(times) > 1 and np.isfinite(times).all() and np.all(np.diff(times) > 0),
        "Invalid inspected times",
    )
    dom = domain_summary(case, values)
    if not dom["pass"]:
        return {"pass": False, "domain": dom}
    p, g = data.layout(case).split(values), geometry(case)
    local = p["leak_transferred"].copy()
    for i, cell in enumerate(case["graph"]["cells"]):
        if cell["pump_roles"] is not None:
            a, b = (cell["species_ids"].index(s) for s in cell["pump_roles"])
            local[:, i, a] -= 3 * p["pump_cycles"][:, i]
            local[:, i, b] += 2 * p["pump_cycles"][:, i]
    for k, c in enumerate(case["graph"]["channels"]):
        s = c["assembly"]["species_ids"].index(c["channel"]["species_id"])
        local[:, g["channel_cells"][k], s] += p["channel_transferred"][:, k]
    internal = np.zeros_like(local)
    for e, (a, b) in enumerate(g["endpoints"]):
        internal[:, a] -= p["junction_transferred"][:, e]
        internal[:, b] += p["junction_transferred"][:, e]
    material = p["amount"] - local - internal
    global_material = np.sum(p["amount"] - local, axis=1)
    species = case["graph"]["cells"][0]["species_ids"]
    cell_error = {s: maximum(material[..., i]) for i, s in enumerate(species)}
    global_error = {s: maximum(global_material[:, i]) for i, s in enumerate(species)}
    charge = maximum(data.QF / g["cap"] * np.sum(material * g["z"], axis=-1))
    dv = data.QF / g["cap"] * np.sum(p["amount"] * g["z"], axis=-1)
    global_charge = maximum(
        np.sum(g["cap"] * dv, axis=1) - data.QF * np.sum(local * g["z"], axis=(1, 2))
    )
    amount, delta = g["initial"] + p["amount"], p["amount"]
    chemical = (
        1e-3
        * g["rt"]
        * np.sum(
            delta * (np.log(g["initial"] / g["volume"][:, None] / g["bath"]) - 1)
            + amount * np.log1p(delta / g["initial"]),
            axis=(1, 2),
        )
    )
    electric = 0.5e12 * np.sum(g["cap"] * dv * (2 * g["v0"] + dv), axis=1)
    work = -1e-3 * np.sum(
        p["pump_cycles"] * [c["drive_J_per_mol"] for c in case["graph"]["cells"]], axis=1
    )
    dissipations = np.concatenate(
        (p["membrane_dissipated_energy_pJ"], p["junction_dissipated_energy_pJ"]), axis=1
    )
    energy = maximum(chemical + electric + np.sum(dissipations, axis=1) - work)
    decrease = max(
        0.0,
        -float(
            np.min(
                np.diff(dissipations, axis=0, prepend=np.zeros((1, dissipations.shape[1]))),
                initial=0,
            )
        ),
    )
    scores = [
        charge / limits["charge_as_voltage_V"],
        global_charge / limits["global_charge_C"],
        energy / limits["energy_pJ"],
        decrease / limits["dissipation_decrease_pJ"],
    ]
    for group in (cell_error, global_error):
        scores.extend(
            error / limits["species_material_overrides_fmol"].get(s, limits["material_fmol"])
            for s, error in group.items()
        )
    return {
        "domain": dom,
        "material_residual_fmol": cell_error,
        "global_material_residual_fmol": global_error,
        "charge_residual_V": charge,
        "global_charge_residual_C": global_charge,
        "energy_residual_pJ": energy,
        "dissipation_decrease_pJ": decrease,
        "max_internal_sum_fmol": maximum(np.sum(internal, axis=1)),
        "max_normalized_residual": max(scores),
        "pass": max(scores) <= 1,
    }


def control_checks(case, times, values, limits, *, factor=1):
    layout, g = data.layout(case), geometry(case)
    results = []
    for i, row in enumerate(case["controls"]):
        end = (
            case["controls"][i + 1]["time_s"]
            if i + 1 < len(case["controls"])
            else case["horizon_s"]
        )
        if end == row["time_s"]:
            continue
        selected = (times >= row["time_s"]) & (times <= end)
        ts, subset = times[selected], values[selected]
        require(
            len(ts) >= 2 and ts[0] == row["time_s"] and ts[-1] == end,
            "Control interval missing endpoints",
        )
        p, control = layout.split(subset), row["value"]
        frozen, membrane_off, edge_off = [], [], []
        for c, cell in enumerate(case["graph"]["cells"]):
            off = [
                u == 0 or perm == 0
                for u, perm in zip(control["leak"][c], cell["permeability_m_per_s"], strict=True)
            ]
            frozen.extend(p["leak_transferred"][:, c, s] for s, b in enumerate(off) if b)
            pump_off = (
                control["pump"][c] == 0
                or cell["capacity_fmol_per_s"] == 0
                or cell["pump_id"] is None
            )
            if pump_off:
                frozen.append(p["pump_cycles"][:, c])
            membrane_off.append(all(off) and pump_off)
        for k, binding in enumerate(case["graph"]["channels"]):
            channel = binding["channel"]
            off = (
                control["channel"][k] == 0
                or channel["abundance"] == 0
                or channel["max_permeability_m_per_s"] == 0
            )
            membrane_off[g["channel_cells"][k]] &= off
            if off:
                frozen.append(p["channel_transferred"][:, k])
        for e, edge in enumerate(case["graph"]["junctions"]):
            off = [
                control["junction"][e] == 0 or perm == 0 for perm in edge["permeability_m_per_s"]
            ]
            frozen.extend(p["junction_transferred"][:, e, s] for s, b in enumerate(off) if b)
            edge_off.append(all(off))
            if all(off):
                frozen.append(p["junction_dissipated_energy_pJ"][:, e])
        fixed = membrane_off.copy()
        for c, off in enumerate(membrane_off):
            if off:
                frozen.append(p["membrane_dissipated_energy_pJ"][:, c])
        for e, (a, b) in enumerate(g["endpoints"]):
            fixed[a] &= edge_off[e]
            fixed[b] &= edge_off[e]
        for c, off in enumerate(fixed):
            if off:
                frozen.extend(p["amount"][:, c, s] for s in range(layout.s))
        unchanged = all(np.array_equal(a, np.full(a.shape, a[0])) for a in frozen)
        membrane_error, edge_error = 0.0, 0.0
        v = voltage(case, p["amount"][0])
        for k, c in enumerate(g["channel_cells"]):
            if fixed[c]:
                mv = v[c] * 1000
                targets = (
                    1 / (1 + math.exp(-(mv + 6) / 6.4)),
                    1 / (1 + math.exp((mv + 25.3) / 3.5)),
                )
                taus = ((8.33 - 0.1163 * mv) / 1000, (1620 - 15.5 * mv) / 1000)
                expected = np.array(
                    [
                        target
                        + (p["membrane_gate"][0, k, s] - target) * np.exp(-(ts - ts[0]) / taus[s])
                        for s, target in enumerate(targets)
                    ]
                ).T
                membrane_error = max(membrane_error, maximum(p["membrane_gate"][:, k] - expected))
        for e, (a, b) in enumerate(g["endpoints"]):
            if fixed[a] and fixed[b]:
                edge = case["graph"]["junctions"][e]
                target = 1 / (
                    1
                    + math.exp(edge["sensitivity_per_V"] * (-v[a] + v[b] - edge["half_voltage_V"]))
                    + math.exp(edge["sensitivity_per_V"] * (v[a] - v[b] - edge["half_voltage_V"]))
                )
                expected = target + (p["junction_gate"][0, e] - target) * np.exp(
                    -(ts - ts[0]) / edge["tau_s"]
                )
                edge_error = max(edge_error, maximum(p["junction_gate"][:, e] - expected))
        passed = (
            unchanged
            and membrane_error <= factor * limits["membrane_gate"]
            and edge_error <= factor * limits["junction_gate"]
        )
        results.append(
            {
                "start_s": row["time_s"],
                "end_s": end,
                "disabled_ledgers_exact": unchanged,
                "constant_voltage_cells": fixed,
                "analytic_membrane_gate_error": membrane_error,
                "analytic_junction_gate_error": edge_error,
                "pass": passed,
            }
        )
    return {"intervals": results, "pass": all(r["pass"] for r in results)}


def polynomial_range(row):
    roots = np.polynomial.polynomial.polyroots([row[1], 2 * row[2], 3 * row[3]])
    nodes = [0.0, 1.0] + [float(r.real) for r in roots if abs(r.imag) <= 1e-12 and 0 < r.real < 1]
    values = np.polynomial.polynomial.polyval(nodes, row)
    require(np.isfinite(values).all(), "Nonfinite cubic range")
    return float(min(values)), float(max(values)), len(nodes)


def candidate_polynomial_domain(case, arrays):
    layout, g = data.layout(case), geometry(case)
    minimum, max_x, max_edge_x, checked = math.inf, 0.0, 0.0, 0
    gate_lo, gate_hi, valid = 1.0, 0.0, True
    factor = max(abs(g["z"])) * data.F / g["rt"]
    for coeff in arrays["coefficients"]:
        amounts = coeff[: layout.amount_count, :4].reshape(layout.n, layout.s, 4)
        vc = data.QF / g["cap"][:, None] * np.sum(g["z"][None, :, None] * amounts, axis=1)
        vc[:, 0] = voltage(case, amounts[..., 0] - g["initial"])
        for row in amounts.reshape(-1, 4):
            lo, _, count = polynomial_range(row)
            minimum, checked = min(minimum, lo), checked + count
        for i, row in enumerate(vc):
            lo, hi, count = polynomial_range(row)
            max_x, checked = max(max_x, factor * max(abs(lo), abs(hi))), checked + count
            if i in g["channel_cells"]:
                valid &= -0.120 <= lo <= hi <= 0.060
        for a, b in g["endpoints"]:
            lo, hi, count = polynomial_range(vc[a] - vc[b])
            max_edge_x, checked = max(max_edge_x, factor * max(abs(lo), abs(hi))), checked + count
        for field in ("membrane_gate", "junction_gate"):
            for row in coeff[layout.slices[field], :4]:
                lo, hi, count = polynomial_range(row)
                gate_lo, gate_hi, checked = min(gate_lo, lo), max(gate_hi, hi), checked + count
    return {
        "minimum_amount_fmol": minimum,
        "max_abs_x": max_x,
        "max_edge_abs_x": max_edge_x,
        "gate_range": [min(gate_lo, gate_hi), gate_hi],
        "extrema_checked": checked,
        "pass": bool(
            valid
            and minimum > 0
            and max_x <= 50
            and max_edge_x <= 50
            and gate_lo >= 0
            and gate_hi <= 1
        ),
    }


def expected_grid(case, candidate):
    pieces = []
    for dt in candidate["steps_s"]:
        mesh = native_mesh(case, dt)
        pieces.append(mesh)
        pieces.extend(
            mesh[:-1] + fraction * np.diff(mesh) for fraction in candidate["comparison_fractions"]
        )
    return np.unique(np.concatenate(pieces))


def native_mesh(case, dt):
    return np.unique(
        np.r_[
            np.arange(math.ceil(case["horizon_s"] / dt)) * dt,
            [c["time_s"] for c in case["controls"]],
            case["horizon_s"],
        ]
    )


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
    times, layout = arrays["native_times_s"], data.layout(case)
    steps = len(times) - 1
    require(
        times.ndim == 1 and 0 <= steps <= 100000 and times[0] == 0 and np.all(np.diff(times) > 0),
        "Invalid native mesh",
    )
    require(
        times[-1] == case["horizon_s"] if complete else times[-1] < case["horizon_s"],
        "Incomplete or overrun trajectory",
    )
    for key, shape in {
        "native_state": (steps + 1, layout.size),
        "coefficients": (steps, layout.size, 6),
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
    initial = np.zeros(layout.size)
    p = layout.split(initial)
    p["membrane_gate"][:] = np.asarray(
        [[c["channel"]["initial_gate"][k] for k in ("m", "h")] for c in case["graph"]["channels"]]
    ).reshape(layout.k, 2)
    p["junction_gate"][:] = [e["initial_gate"] for e in case["graph"]["junctions"]]
    if kind == "RK4":
        p["amount"][:] = geometry(case)["initial"]
    require(np.array_equal(initial, arrays["native_state"][0]), "Initial state/history mismatch")
    for c in case["controls"]:
        if c["time_s"] <= times[-1]:
            require(c["time_s"] in times, "Control boundary lost")
    sample = arrays["sample_times_s"]
    require(
        sample.ndim == 1
        and len(sample) <= 100000
        and arrays["sample_state"].shape == (len(sample), layout.size),
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
    mesh, steps = native_mesh(case, stats["dt_s"]), stats["accepted_steps"]
    require(
        steps < len(mesh) - 1 and np.array_equal(arrays["native_times_s"], mesh[: steps + 1]),
        "Rejected prefix differs from mesh",
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
        "Rejected time/call mismatch",
    )
    held = next(c for c in reversed(case["controls"]) if c["time_s"] <= mesh[steps])
    require(trial["control"] == held, "Rejected held control mismatch")
    state = np.asarray(trial["absolute_state"], dtype=float)[None, :]
    require(state.shape == (1, data.layout(case).size), "Invalid rejected state shape")
    state[:, : data.layout(case).amount_count] -= geometry(case)["initial"].ravel()
    require(
        not np.isfinite(state).all() or not domain_summary(case, state)["pass"],
        "Claimed rejection does not violate domain",
    )
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
    grid, oracle = expected_grid(case, plan["candidate"]), records["refined"]["sample_state"]
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
                plan["trajectory_limits"],
                factor=1 if kind == "RK4" else plan["trajectory_limits"]["reference_factor"],
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


def reduction_comparison(case, oracle, components, limits):
    layout, g = data.layout(case), geometry(case)
    require(
        layout.e == 0 and len(components) == layout.n, "Incomplete independent component reduction"
    )
    combined = np.zeros_like(oracle)
    p = layout.split(combined)
    for c, values in enumerate(components):
        p["amount"][:, c] = values[:, : layout.s]
        p["leak_transferred"][:, c] = values[:, layout.s : 2 * layout.s]
        p["pump_cycles"][:, c] = values[:, 2 * layout.s]
        p["membrane_dissipated_energy_pJ"][:, c] = values[:, 2 * layout.s + 1]
        if c in g["channel_cells"]:
            k = g["channel_cells"].index(c)
            p["membrane_gate"][:, k] = values[:, 2 * layout.s + 2 : 2 * layout.s + 4]
            p["channel_transferred"][:, k] = values[:, -1]
    return errors(case, oracle, combined, limits, factor=limits["reference_factor"])


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
            for key, floor in (
                ("voltage_V", candidate["voltage_refinement_floor_V"]),
                ("membrane_gate", candidate["gate_refinement_floor"]),
                ("junction_gate", candidate["gate_refinement_floor"]),
            ):
                pair = [
                    item["observed_comparison"]["errors"][key]
                    if "observed_comparison" in item
                    else math.inf
                    for item in (first, second)
                ]
                refinements[key] = all(math.isfinite(v) for v in pair) and (
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


def final_summary(case, arrays, stats):
    parts = data.layout(case).split(arrays["sample_state"][-1])
    return {
        "samples": len(arrays["sample_times_s"]),
        "final_amount_fmol": (geometry(case)["initial"] + parts["amount"]).tolist(),
        "final_voltage_V": voltage(case, parts["amount"]).tolist(),
        "final_state": {k: v.tolist() for k, v in parts.items()},
        "attempts": stats,
    }
