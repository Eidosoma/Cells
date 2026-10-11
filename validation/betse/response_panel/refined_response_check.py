"""Fixed-input response comparison, without importing either model or an array library."""

import copy
import importlib
import math
import sys

import refined_response_cells_check as local
import refined_response_context as ctx
import refined_response_native as native

c = ctx.c
legacy = importlib.import_module("held_response_check")
cluster, fence, links, old, evidence = (
    legacy.cluster,
    legacy.fence,
    legacy.links,
    legacy.old,
    legacy.evidence,
)
arrays = importlib.import_module("trajectory_check")
Checks, difference, numbers, rate_by_cell, shaped, unpack = (
    arrays.Checks,
    arrays.difference,
    arrays.numbers,
    arrays.rate_by_cell,
    arrays.shaped,
    arrays.unpack,
)

UNITS = ("voltage_V", "amount_fmol", "transfer_fmol", "flux_fmol_per_s", "current_A")


def native_record(registered, packet, row, checks):
    p, b, g = registered["criteria"], registered["base_protocol"], registered["geometry"]
    record, dt = packet["result"]["numerical"], row["dt_s"]
    count = ctx.count(dt)
    label = "native/" + row["condition"]
    limits, constants = p["instantaneous_tolerances"], b["profiles"][row["profile"]]
    c.require(
        record["id"] == old.key(row["case"]["id"], row["profile"], dt)
        and record["dt_s"] == dt
        and record["constants"] == constants
        and record["configured_steps"] == count,
        "Native numerical identity differs",
    )
    c.require(
        record["geometry"] == {k: g[k] for k in cluster.GEOMETRY_FIELDS}
        and record["settings"] == registered["settings"]
        and record["rho_channel"] == 1,
        "Native physical geometry/mechanisms differ",
    )
    c.require(
        record["species"] == b["expected_species"] and record["valence"] == b["expected_valence"],
        "Native ion table differs",
    )
    trace, events = record["trace"], packet["events"]["events"]
    c.require(
        len(trace["steps"]) == len(events) == count
        and len(registered["common_times_s"]) == count + 1,
        "Native arithmetic coverage differs",
    )
    initial = trace["initial"]
    vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
    zs, zero = b["expected_valence"], [[0.0] * 30 for _ in range(6)]
    cumul = [[0.0] * 7 for _ in range(6)]
    states, transfers, rates = [initial], [[[0.0] * 7 for _ in range(3)]], []

    def state(name, saved, density):
        shaped(saved["inside_mM"], [6, 7])
        shaped(saved["outside_mM"], [6, 30])
        c.require(
            all(v > 0 for v in numbers(saved["inside_mM"]) + numbers(saved["outside_mM"])),
            "Nonpositive native inventory",
        )
        c.require(
            all(all(v == a[0] for v in a) for a in saved["outside_mM"]),
            "Native bath is not well mixed",
        )
        shaped(saved["voltage_V"], [30])
        shaped(saved["rho_C_per_m3"], [7])
        shaped(saved["inward_current_A"], [30])
        c.require(
            shaped(saved["boundary_voltage_V"], [100]) == [0.0] * 100,
            "Native boundary voltage changed",
        )
        cell_rates = rate_by_cell(density, g)
        for i in range(7):
            rho = constants["F"] * math.fsum(zs[s] * saved["inside_mM"][s][i] for s in range(6))
            voltage = rho * g["cell_volumes_m3"][i] / (0.01 * g["cell_areas_m2"][i])
            checks.compare(
                f"{name}/rho/{i}", saved["rho_C_per_m3"][i], rho, "charge_density_C_per_m3", limits
            )
            for j, owner in enumerate(g["membrane_owners"]):
                if owner == i:
                    checks.compare(
                        f"{name}/voltage/{j}", saved["voltage_V"][j], voltage, "voltage_V", limits
                    )
            current = math.fsum(
                saved["inward_current_A"][j]
                for j, owner in enumerate(g["membrane_owners"])
                if owner == i
            )
            expected = (
                constants["F"] * 1e-15 * math.fsum(zs[s] * cell_rates[s][i] for s in range(6))
            )
            checks.compare(f"{name}/current/{i}", current, expected, "current_A", limits)

    state(label + "/initial", initial, zero)
    for s in range(6):
        for field, item_count, expected in (
            ("inside_mM", 7, b["inside_mM"][s]),
            ("outside_mM", 30, b["outside_mM"][s]),
        ):
            for i in range(item_count):
                checks.compare(
                    f"{label}/initial/{field}/{s}/{i}",
                    initial[field][s][i],
                    expected,
                    "concentration_mM",
                    limits,
                )
    previous_density = zero
    cumulative = limits | {"amount_fmol": p["cumulative_amount_atol_fmol"]}
    for k, (step, event) in enumerate(zip(trace["steps"], events, strict=True)):
        name = f"{label}/step/{k}"
        before, after, density = step["before"], step["after"], step["density_mol_per_m2_s"]
        c.require(
            before["inside_mM"] == states[-1]["inside_mM"]
            and before["outside_mM"] == states[-1]["outside_mM"],
            "Native material history is discontinuous",
        )
        state(name + "/before", before, previous_density)
        state(name + "/after", after, density)
        c.require(
            shaped(step["junction_density_mol_per_m2_s"], [6, 30]) == [0.0] * 180,
            "Native junction transported",
        )
        # Actual per-interval effective Dm, already checked independently against
        # the declared input. The final Dm export is NOT a trajectory parameter.
        dm = unpack(event["after"]["arrays"]["Dm_cells"])
        shaped(dm, [6, 30])
        cell_rates = rate_by_cell(density, g)
        for s in range(6):
            if s >= 3 or row["condition"] == "static_blocked":
                c.require(all(v == 0 for v in density[s]), "Disabled native route transported")
            for j, owner in enumerate(g["membrane_owners"]):
                point = {
                    "inside_mM": before["inside_mM"][s][owner],
                    "outside_mM": before["outside_mM"][s][j],
                    "voltage_V": before["voltage_V"][j],
                    "valence": zs[s],
                    "temperature_K": 310.15,
                    "area_m2": g["membrane_areas_m2"][j],
                    "permeability_m_per_s": dm[s][j] / b["thickness_m"],
                }
                checks.compare(
                    f"{name}/GHK/{s}/{j}",
                    density[s][j] * point["area_m2"] / 1e-15,
                    c.oracle(point, constants),
                    "flux_fmol_per_s",
                    limits,
                )
            for i in range(7):
                checks.compare(
                    f"{name}/step_amount/{s}/{i}",
                    (after["inside_mM"][s][i] - before["inside_mM"][s][i]) * vi[i],
                    cell_rates[s][i] * dt,
                    "amount_fmol",
                    limits,
                )
                cumul[s][i] += cell_rates[s][i] * dt
                checks.compare(
                    f"{name}/integrated_amount/{s}/{i}",
                    (after["inside_mM"][s][i] - initial["inside_mM"][s][i]) * vi[i],
                    cumul[s][i],
                    "amount_fmol",
                    cumulative,
                )
            checks.compare(
                f"{name}/outside_step/{s}",
                (after["outside_mM"][s][0] - before["outside_mM"][s][0]) * vo,
                -math.fsum(cell_rates[s]) * dt,
                "amount_fmol",
                limits,
            )
            checks.compare(
                f"{name}/outside_integral/{s}",
                (after["outside_mM"][s][0] - initial["outside_mM"][s][0]) * vo,
                -math.fsum(cumul[s]),
                "amount_fmol",
                cumulative,
            )
        if row["condition"] == "static_blocked":
            c.require(
                all(after[k] == initial[k] for k in ("inside_mM", "outside_mM", "voltage_V")),
                "Blocked native state changed",
            )
        states.append(after)
        transfers.append([list(a) for a in cumul[:3]])
        rates.append(cell_rates[:3])
        previous_density = density
    ordinary = {name: unpack(v) for name, v in record["ordinary"].items()}
    c.require(ordinary["time"] == trace["labels_s"][1:], "Native stored clock differs")
    for field, name in (
        ("inside_mM", "cc_time"),
        ("outside_mM", "cc_env_time"),
        ("voltage_V", "vm_time"),
        ("inward_current_A", "I_mem_time"),
        ("rho_C_per_m3", "rho_cells_time"),
    ):
        c.require(
            ordinary[name] == [s["after"][field] for s in trace["steps"][1:]],
            "Native storage/observer differs",
        )
    c.require(
        ordinary["dd_time"] == [e["after"]["arrays"]["Dm_cells"]["values"] for e in events[1:]],
        "Stored dynamic permeability differs",
    )
    c.require(
        all(v == 0 for v in numbers(ordinary["rate_NaKATP_time"]))
        and all(v == 1 for v in numbers(ordinary["gjopen_time"])),
        "Native inactive storage differs",
    )
    canonical = []
    for k, t in enumerate(registered["common_times_s"]):
        c.require(math.isclose(t, k * dt, rel_tol=0, abs_tol=1e-18), "Common time off native grid")
        saved = states[k]
        canonical.append(
            {
                "voltage_V": [saved["voltage_V"][g["membrane_owners"].index(i)] for i in range(7)],
                "amount_fmol": [
                    (saved["inside_mM"][s][i] - initial["inside_mM"][s][i]) * vi[i]
                    for s in range(3)
                    for i in range(7)
                ]
                + [
                    (saved["outside_mM"][s][0] - initial["outside_mM"][s][0]) * vo for s in range(3)
                ],
                "transfer_fmol": numbers(transfers[k]),
                "flux_fmol_per_s": numbers(rates[k]) if k < count else [],
                "current_A": [
                    constants["F"] * 1e-15 * math.fsum(zs[s] * rates[k][s][i] for s in range(3))
                    for i in range(7)
                ]
                if k < count
                else [],
            }
        )
    return canonical


def intervals(canonical):
    c.require(
        len(canonical) in (41, 81, 161) and all(len(r["transfer_fmol"]) == 21 for r in canonical),
        "Interval transfer coverage differs",
    )
    return [
        {
            unit: [b - a for a, b in zip(left[unit], right[unit], strict=True)]
            if unit == "transfer_fmol"
            else []
            for unit in UNITS
        }
        for left, right in zip(canonical[:-1], canonical[1:], strict=True)
    ]


def summary(checks):
    return copy.deepcopy(
        {
            "comparisons": checks.count,
            "failed_comparisons": checks.failed_count,
            "maximum_normalized_error": checks.maximum,
            "worst": checks.worst,
            "first_failures": checks.failures[:100],
        }
    )


def combine(records):
    c.require(bool(records), "Empty comparison summary")
    worst = max(records, key=lambda r: r["maximum_normalized_error"])
    return copy.deepcopy(
        {
            "comparisons": sum(r["comparisons"] for r in records),
            "failed_comparisons": sum(r["failed_comparisons"] for r in records),
            "maximum_normalized_error": worst["maximum_normalized_error"],
            "worst": worst["worst"],
            "first_failures": [v for r in records for v in r["first_failures"]][:100],
        }
    )


def compare_scope(label, left, right, limits, required):
    checks = Checks()
    maxima = difference(label, left, right, limits, checks)
    transfers = difference(label + "/intervals", intervals(left), intervals(right), limits, checks)
    return summary(checks) | {
        "required": required,
        "status": "pass" if checks.failed_count == 0 else "rejected",
        "maximum_absolute_errors": maxima,
        "maximum_interval_transfer_error_fmol": transfers["transfer_fmol"],
    }


def compare_panel(registered, natives, cells, finest):
    p, plan = registered["criteria"], registered["plan"]
    h = plan["hold_step_s"]
    c.require(
        set(natives) == set(plan["conditions"])
        and set(cells) == set(registered["cells_definitions"]),
        "Comparison coverage differs",
    )
    scopes = {}

    def identifier(condition, backend, factor):
        matches = [
            r["id"]
            for r in registered["cells_rows"]
            if (r["condition"], r["backend"], r["subdivision"]) == (condition, backend, factor)
        ]
        c.require(len(matches) == 1, "Ambiguous Cells panel identity")
        return matches[0]

    def compare(label, left, right, limits, required=True):
        key = f"{h:.8f}/" + label
        scopes[key] = compare_scope(key, left, right, limits, required) | {"hold_step_s": h}

    for condition in plan["conditions"]:
        for backend in plan["cells_backends"]:
            for a, b in ((1, 2), (2, 4)):
                compare(
                    f"fixed_input_solver/{condition}/{backend}/{a}-{b}",
                    cells[identifier(condition, backend, a)],
                    cells[identifier(condition, backend, b)],
                    p["instantaneous_tolerances"],
                )
            compare(
                f"cross_engine/{condition}/{backend}",
                natives[condition],
                cells[identifier(condition, backend, 4)],
                p["trajectory_tolerances"],
                required=h == finest,
            )
        for factor in plan["cells_subdivisions"]:
            compare(
                f"backend/{condition}/{factor}",
                cells[identifier(condition, "jax_eager", factor)],
                cells[identifier(condition, "jax_jit", factor)],
                p["instantaneous_tolerances"],
            )
    c.require(len(scopes) == 36, "Incomplete fixed-input surface")
    return scopes


def common_grid(canonical):
    c.require(len(canonical) in (41, 81, 161), "Unregistered common-grid projection")
    stride = (len(canonical) - 1) // 40
    # No interpolation: exact registered boundaries only. Terminal RHS remains absent.
    return copy.deepcopy(canonical[::stride])


def across_holds(registered, panels):
    scopes = {}
    for a, b in ((0.000025, 0.0000125), (0.0000125, 0.00000625)):
        for condition in registered["plan"]["conditions"]:
            for engine in ("native", "jax_eager", "jax_jit"):

                def select(h, engine=engine, condition=condition):
                    view, natives, cells = panels[h]
                    if engine == "native":
                        return natives[condition]
                    row = next(
                        r
                        for r in view["cells_rows"]
                        if (r["condition"], r["backend"], r["subdivision"])
                        == (condition, engine, 4)
                    )
                    return cells[row["id"]]

                label = f"across_hold/{a:.8f}-{b:.8f}/{condition}/{engine}"
                scopes[label] = compare_scope(
                    label,
                    common_grid(select(a)),
                    common_grid(select(b)),
                    registered["criteria"]["trajectory_tolerances"],
                    required=False,
                ) | {
                    "interpretation": "joint_native_integration_and_forcing_resampling"
                    if engine == "native"
                    else "finely_integrated_Cells_input_hold_sensitivity",
                    "native_convergence_qualified": False,
                    "forcing_convergence_qualified": False,
                }
    c.require(len(scopes) == 24, "Incomplete across-hold diagnostics")
    return scopes


def verdict(laws, scopes):
    required = combine(list(laws.values()) + [r for r in scopes.values() if r["required"]])
    total = combine(list(laws.values()) + list(scopes.values()))
    return {
        "status": "finest_held_response_gates_pass_with_coarse_rejections_pending_audit"
        if required["failed_comparisons"] == 0
        else "failed_not_qualified",
        **total,
        "required_gates": required,
        "internal_laws": combine(list(laws.values())),
        "internal_laws_by_hold": laws,
        "comparisons_by_scope": scopes,
        "native_convergence_qualified": False,
        "forcing_convergence_qualified": False,
        "trajectory_qualified": False,
        "independent_audit_run": False,
        "biology_validated": False,
        "gpu_tested": False,
    }


def read_panel(root, registered, view, coarse=False):
    """Check saved rows against their actual root registration and preparation."""
    checks, natives, cells, packets, records = Checks(), {}, {}, {}, {}
    native_rows, pairs = [], []
    context, gates = (ctx.legacy, legacy.native) if coarse else (ctx, native)
    prior = evidence.trusted_registration()
    for row in view["native_rows"]:
        pair = {}
        row_id = row["condition"] if coarse else ctx.prior.key(row)
        for mode in registered["plan"]["native_modes"]:
            directory = root / "native" / row_id / mode
            pair[mode] = links.read_packet(directory, mode)
            retained = (
                c.read(context.overlap_path(row, mode))
                if row["condition"] != "suppression_recovery"
                else None
            )
            checked = gates.check_row(
                row, mode, pair[mode], prior, registered["plan"], context.prepared(row), retained
            )
            c.require(checked == c.read(directory / "checks.json"), "Saved native checks differ")
            native_rows.append(
                {
                    "row": row,
                    "mode": mode,
                    "path": str((directory / "result.json").relative_to(root)),
                    "sha256": c.sha(directory / "result.json"),
                    **checked,
                }
            )
        pairs.append(
            ({"condition": row_id} if coarse else {"row_id": row_id}) | links.check_pair(pair)
        )
        packets[row["condition"]] = pair["observed"]
        natives[row["condition"]] = native_record(view, pair["observed"], row, checks)
    zero = native.check_zero(packets)
    for row in view["cells_rows"]:
        record = c.read(root / "cells" / row["id"] / "result.json")
        records[row["id"]] = record
        cells[row["id"]] = local.cells_record(view, record, row, checks)
    for backend in view["plan"]["cells_backends"]:
        for factor in view["plan"]["cells_subdivisions"]:
            control = [
                next(
                    records[r["id"]]
                    for r in view["cells_rows"]
                    if (r["condition"], r["backend"], r["subdivision"])
                    == (condition, backend, factor)
                )
                for condition in ("baseline", "zero_amplitude")
            ]
            c.require(
                all(
                    control[0][k] == control[1][k]
                    for k in ("times", "history", "observations", "diagnostics", "final_step_index")
                ),
                "Zero-amplitude changes Cells response",
            )
    return natives, cells, summary(checks), native_rows, pairs, zero


def run(registered, output):
    c.require(
        not any(n.split(".")[0] in fence.FORBIDDEN for n in sys.modules),
        "Comparison imported simulator/array library",
    )
    guard = fence.ImportFence()
    sys.meta_path.insert(0, guard)
    try:
        return checked_run(registered, output)
    finally:
        sys.meta_path.remove(guard)


def checked_run(registered, output):
    ctx.validate_registration(registered)
    plan = registered["plan"]
    workers = {s: c.read(output / (s + ".json")) for s in ("native", "cells")}
    for w in workers.values():
        c.require(
            w["registration_sha256"] == c.sha(output / "registration.json")
            and w["sources"] == registered["sources"]
            and w["warnings"] == []
            and w["trajectory_run"] is True,
            "Worker provenance/context differs",
        )
    nw, cw = workers["native"], workers["cells"]
    c.require(
        nw["engine"] == "actual_betse_full_sim_loop"
        and cw["engine"] == "unchanged_cells_checked_rk4_runner"
        and cw["device"] == "cpu"
        and cw["x64_enabled"] is True
        and cw["jit_disabled"] is False
        and cw["accepted_runtime"] == registered["cells_runtime"],
        "Worker engine/runtime differs",
    )
    c.require(
        cw["results"]
        == {r["id"]: "cells/" + r["id"] + "/result.json" for r in registered["cells_rows"]}
        and len(nw["results"]) == plan["native_runs"],
        "Worker run coverage differs",
    )
    coarse = c.read(ctx.COARSE / "registration.json")
    # Reproduce the original checker INCLUDING its documented reporting alias;
    # do not rewrite its on-disk report or pretend this replay is independent.
    replay = legacy.run(coarse, ctx.COARSE)
    original = c.read(ctx.COARSE / "comparison.json")
    c.require(
        replay
        == {
            k: v
            for k, v in original.items()
            if k not in {"registration_sha256", "sources", "elapsed_seconds"}
        }
        and replay["failed_comparisons"] == 150
        and replay["comparisons"] == 345576,
        "Original rejection did not reproduce exactly",
    )
    panels, laws, scopes = {}, {}, {}
    new_rows, new_pairs, new_zero = [], [], {}
    for h in [plan["retained_hold_step_s"], *plan["hold_steps_s"]]:
        is_coarse = h == plan["retained_hold_step_s"]
        view = coarse if is_coarse else ctx.panel_view(registered, h)
        root = ctx.COARSE if is_coarse else output
        result = read_panel(root, coarse if is_coarse else registered, view, is_coarse)
        natives, cells, law, rows, pairs, zero = result
        c.require(
            law["comparisons"] == 4864 * ctx.count(h) + 3704,
            "Internal-law comparison coverage differs",
        )
        panels[h], laws[f"{h:.8f}"] = (view, natives, cells), law
        scopes |= compare_panel(view, natives, cells, min(plan["hold_steps_s"]))
        if not is_coarse:
            new_rows += rows
            new_pairs += pairs
            new_zero[f"{h:.8f}"] = zero
    c.require(
        new_rows == nw["results"] and new_pairs == nw["pairs"] and new_zero == nw["zero_control"],
        "Native worker receipt linkage differs",
    )
    scopes |= across_holds(registered, panels)
    result = verdict(laws, scopes)
    c.require(
        result["comparisons"] == 2494936
        and result["required_gates"]["comparisons"] == 2298936
        and len(scopes) == 132,
        "Registered comparison surface differs",
    )
    return result | {
        "schema": "cells.betse_refined_response_comparison@1",
        "native_runs": 16,
        "cells_runs": 48,
        "retained_native_runs": 8,
        "retained_cells_runs": 24,
        "coarse_rejection_replayed_exactly": True,
        "coarse_comparison_sha256": c.sha(ctx.COARSE / "comparison.json"),
        "coarse_failed_comparisons": replay["failed_comparisons"],
        "coarse_maximum_normalized_error": replay["maximum_normalized_error"],
        "state_times_by_hold": {"0.00002500": 41, "0.00001250": 81, "0.00000625": 161},
        "across_hold_common_state_times": 41,
        "terminal_Cells_rate_validated": True,
        "terminal_native_rate_invented": False,
        "criteria_unchanged": True,
    }
