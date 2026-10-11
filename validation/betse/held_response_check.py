"""Fixed-input response comparison, without importing either model or an array library."""

import math
import sys

import cluster_alignment as cluster
import contact as c
import full_loop_audit as fence
import full_loop_bridge_check as links
import held_response_cells_check as local
import held_response_context as ctx
import held_response_native as native
import trajectory_context as old
import trajectory_evidence as evidence
from trajectory_check import Checks, difference, numbers, rate_by_cell, shaped, unpack

UNITS = ("voltage_V", "amount_fmol", "transfer_fmol", "flux_fmol_per_s", "current_A")


def native_record(registered, packet, row, checks):
    p, b, g = registered["criteria"], registered["base_protocol"], registered["geometry"]
    record, dt = packet["result"]["numerical"], row["dt_s"]
    label = "native/" + row["condition"]
    limits, constants = p["instantaneous_tolerances"], b["profiles"][row["profile"]]
    c.require(
        record["id"] == old.key(row["case"]["id"], row["profile"], dt)
        and record["dt_s"] == dt
        and record["constants"] == constants
        and record["configured_steps"] == 40,
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
        len(trace["steps"]) == len(events) == 40 and len(registered["common_times_s"]) == 41,
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
        for field, count, expected in (
            ("inside_mM", 7, b["inside_mM"][s]),
            ("outside_mM", 30, b["outside_mM"][s]),
        ):
            for i in range(count):
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
                "flux_fmol_per_s": numbers(rates[k]) if k < 40 else [],
                "current_A": [
                    constants["F"] * 1e-15 * math.fsum(zs[s] * rates[k][s][i] for s in range(3))
                    for i in range(7)
                ]
                if k < 40
                else [],
            }
        )
    return canonical


def intervals(canonical):
    c.require(
        len(canonical) == 41 and all(len(r["transfer_fmol"]) == 21 for r in canonical),
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
    return {
        "comparisons": checks.count,
        "failed_comparisons": checks.failed_count,
        "maximum_normalized_error": checks.maximum,
        "worst": checks.worst,
        "first_failures": checks.failures,
    }


def compare_panel(registered, natives, cells, checks):
    p, plan = registered["criteria"], registered["plan"]
    c.require(
        set(natives) == set(plan["conditions"])
        and set(cells) == set(registered["cells_definitions"]),
        "Comparison panel coverage differs",
    )
    comparisons = {}

    def compare(label, left, right, limits):
        before = checks.failed_count
        maxima = difference(label, left, right, limits, checks)
        transfer = difference(
            label + "/intervals", intervals(left), intervals(right), limits, checks
        )
        comparisons[label] = {
            "maximum_absolute_errors": maxima,
            "maximum_interval_transfer_error_fmol": transfer["transfer_fmol"],
            "failed_comparisons": checks.failed_count - before,
        }

    for condition in plan["conditions"]:

        def identifier(backend, factor, condition=condition):
            return f"{condition}/{backend}/subdivision-{factor}"

        for backend in plan["cells_backends"]:
            for a, b in ((1, 2), (2, 4)):
                compare(
                    f"fixed_input_solver/{condition}/{backend}/{a}-{b}",
                    cells[identifier(backend, a)],
                    cells[identifier(backend, b)],
                    p["instantaneous_tolerances"],
                )
            compare(
                f"cross_engine/{condition}/{backend}",
                natives[condition],
                cells[identifier(backend, 4)],
                p["trajectory_tolerances"],
            )
        for factor in plan["cells_subdivisions"]:
            compare(
                f"backend/{condition}/{factor}",
                cells[identifier("jax_eager", factor)],
                cells[identifier("jax_jit", factor)],
                p["instantaneous_tolerances"],
            )
    return comparisons


def run(registered, output):
    c.require(
        not any(n.split(".")[0] in fence.FORBIDDEN for n in sys.modules),
        "Comparison imported simulator/array library",
    )
    sys.meta_path.insert(0, fence.ImportFence())
    ctx.validate_registration(registered)
    prior = evidence.trusted_registration()
    plan = registered["plan"]
    native_worker, cells_worker = c.read(output / "native.json"), c.read(output / "cells.json")
    for worker in (native_worker, cells_worker):
        c.require(
            worker["registration_sha256"] == c.sha(output / "registration.json")
            and worker["sources"] == registered["sources"]
            and worker["warnings"] == []
            and worker["trajectory_run"] is True,
            "Worker provenance/context differs",
        )
    c.require(
        native_worker["engine"] == "actual_betse_full_sim_loop"
        and cells_worker["engine"] == "unchanged_cells_checked_rk4_runner"
        and cells_worker["device"] == "cpu"
        and cells_worker["x64_enabled"] is True
        and cells_worker["jit_disabled"] is False
        and cells_worker["accepted_runtime"] == registered["cells_runtime"],
        "Worker engine/runtime differs",
    )
    c.require(
        set(cells_worker["results"]) == set(registered["cells_definitions"])
        and len(native_worker["results"]) == 8,
        "Worker run coverage differs",
    )
    checks, natives, cells, packets, records = Checks(), {}, {}, {}, {}
    native_rows = []
    for row in registered["native_rows"]:
        pair = {}
        for mode in plan["native_modes"]:
            directory = output / "native" / row["condition"] / mode
            pair[mode] = links.read_packet(directory, mode)
            retained = (
                c.read(ctx.overlap_path(row, mode))
                if row["condition"] != "suppression_recovery"
                else None
            )
            checked = native.check_row(
                row, mode, pair[mode], prior, plan, ctx.prepared(row), retained
            )
            c.require(
                checked == c.read(directory / "checks.json"), "Saved native gate receipt differs"
            )
            native_rows.append(
                {
                    "row": row,
                    "mode": mode,
                    "path": str((directory / "result.json").relative_to(output)),
                    "sha256": c.sha(directory / "result.json"),
                    **checked,
                }
            )
        links.check_pair(pair)
        packets[row["condition"]] = pair["observed"]
        natives[row["condition"]] = native_record(registered, pair["observed"], row, checks)
    c.require(
        native_rows == native_worker["results"], "Native worker receipt coverage/linkage differs"
    )
    native.check_zero(packets)
    for row in registered["cells_rows"]:
        path = "cells/" + row["id"] + "/result.json"
        c.require(cells_worker["results"][row["id"]] == path, "Cells worker path differs")
        records[row["id"]] = c.read(output / path)
        cells[row["id"]] = local.cells_record(registered, records[row["id"]], row, checks)
    for backend in plan["cells_backends"]:
        for factor in plan["cells_subdivisions"]:
            a, b = (
                records[f"{condition}/{backend}/subdivision-{factor}"]
                for condition in ("baseline", "zero_amplitude")
            )
            c.require(
                all(
                    a[k] == b[k]
                    for k in ("times", "history", "observations", "diagnostics", "final_step_index")
                ),
                "Zero-amplitude changes Cells response",
            )
    laws = summary(checks)
    comparisons = compare_panel(registered, natives, cells, checks)
    return {
        "schema": "cells.betse_held_response_comparison@1",
        "status": "pass_pending_independent_audit"
        if checks.failed_count == 0
        else "failed_not_qualified",
        **summary(checks),
        "internal_laws": laws,
        "comparisons_by_scope": comparisons,
        "native_runs": 8,
        "cells_runs": 24,
        "common_state_times": 41,
        "rate_times": 40,
        "interval_transfers": 40,
        "terminal_Cells_rate_validated": True,
        "terminal_native_rate_invented": False,
        "native_convergence_qualified": False,
        "forcing_convergence_qualified": False,
        "trajectory_qualified": False,
        "independent_audit_run": False,
        "biology_validated": False,
        "gpu_tested": False,
        "criteria_unchanged": True,
    }
