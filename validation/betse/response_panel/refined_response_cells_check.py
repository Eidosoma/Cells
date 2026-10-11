"""Saved Cells response arithmetic: fixed holds, inventories, charge and fresh rates."""

import importlib
import math

import refined_response_context as ctx

c, held = ctx.c, ctx.held
arrays = importlib.import_module("trajectory_check")
numbers, shaped, unpack = arrays.numbers, arrays.shaped, arrays.unpack


def cells_record(registered, record, row, checks):
    p, b, g = registered["criteria"], registered["base_protocol"], registered["geometry"]
    plan, identifier = registered["plan"], row["id"]
    c.require(
        row in registered["cells_rows"]
        and record["id"] == identifier
        and record["definition"] == registered["cells_definitions"][identifier],
        "Cells definition/identity differs",
    )
    count = ctx.count(plan["hold_step_s"])
    n, factor = count * row["subdivision"], row["subdivision"]
    dt = plan["hold_step_s"] / factor
    times = unpack(record["times"])
    c.require(
        times == [k * dt for k in range(n)] + [plan["duration_s"]]
        and type(record["final_step_index"]) is int
        and record["final_step_index"] == n,
        "Cells accepted clock differs",
    )
    exports = {}
    for group, length in (("history", n + 1), ("observations", count + 1)):
        expected = registered["cells_export_shapes"][group]
        c.require(set(record[group]) == set(expected), "Cells export coverage differs: " + group)
        exports[group] = {}
        for name, tail in expected.items():
            value = record[group][name]
            c.require(
                value["shape"] == [length, *tail]
                and set(value) == {"shape", "dtype", "values", "bytes_sha256"},
                "Cells export shape/fields differ: " + name,
            )
            exports[group][name] = unpack(value)
    history, obs = exports["history"], exports["observations"]
    for name in (
        "pump_cycles",
        "gate",
        "channel_transferred",
        "junction_gate",
        "junction_transferred",
        "junction_dissipated_energy_pJ",
    ):
        c.require(all(v == 0 for v in numbers(history[name])), "Inactive Cells history changed")
    c.require(
        all(all(v == 0 for v in numbers(series[0])) for series in history.values()),
        "Cells preparation differs",
    )
    if row["condition"] == "static_blocked":
        c.require(
            all(all(v == 0 for v in numbers(series)) for series in history.values()),
            "Blocked Cells history changed",
        )
    c.require(
        all(v >= 0 for v in numbers(history["dissipated_energy_pJ"])),
        "Negative passive energy ledger",
    )
    instant = p["instantaneous_tolerances"]
    cumulative = instant | {"amount_fmol": p["cumulative_amount_atol_fmol"]}
    constant = b["profiles"]["matched_constants"]
    vi, vo = [v / 1e-15 for v in g["cell_volumes_m3"]], g["effective_bath_volume_m3"] / 1e-15
    for k in range(n + 1):
        inside, outside, leak = (
            history[name][k]
            for name in ("amount_increment", "extracellular_amount_increment", "leak_transferred")
        )
        c.require(history["dissipated_energy_pJ"][k][7:] == [0, 0], "Padded energy ledger changed")
        for s in range(3):
            c.require(
                inside[s][7] == outside[s][1] == 0 and leak[s][7:] == [0, 0],
                "Padded Cells owner changed",
            )
            c.require(
                b["outside_mM"][s] * vo + outside[s][0] > 0, "Nonpositive Cells bath inventory"
            )
            for i in range(7):
                c.require(
                    b["inside_mM"][s] * vi[i] + inside[s][i] > 0,
                    "Nonpositive Cells intracellular inventory",
                )
                checks.compare(
                    f"{identifier}/owned_transfer/{k}/{s}/{i}",
                    inside[s][i],
                    leak[s][i],
                    "amount_fmol",
                    cumulative,
                )
            checks.compare(
                f"{identifier}/global_material/{k}/{s}",
                math.fsum(inside[s]) + outside[s][0],
                0,
                "amount_fmol",
                cumulative,
            )
    c.require(obs["times"] == registered["common_times_s"], "Cells observation times differ")
    for name, values in obs.items():
        if name.startswith(("pump_", "channel_", "junction_")) or name == "gate":
            c.require(
                all(v == 0 for v in numbers(values)),
                "Disabled mechanism observation changed: " + name,
            )
    schedule = held.held_schedule(c.read(held.PLAN), row["condition"], plan["hold_step_s"])
    canonical = []
    for j in range(count + 1):
        k = j * factor
        for name in history:
            c.require(
                obs[name][j] == history[name][k],
                "On-grid Cells history/observation linkage differs: " + name,
            )
        inside, outside = (
            history["amount_increment"][k],
            history["extracellular_amount_increment"][k],
        )
        availability = schedule[min(j, count - 1)]["multipliers"]["Na"]
        voltages, flux = obs["voltage_V"][j], obs["leak_flux_fmol_per_s"][j]
        c.require(
            voltages[7:] == obs["membrane_current_A"][j][7:] == [0, 0],
            "Padded voltage/current changed",
        )
        for s in range(3):
            c.require(
                obs["leak_multiplier"][j][s] == [availability] * 7 + [0, 0],
                "Cells held control or terminal hold differs",
            )
            c.require(
                flux[s][7:] == [0, 0]
                and obs["amount"][j][s][7] == obs["concentration_mM"][j][s][7] == 0,
                "Padded amount/flux changed",
            )
            for name in (
                "extracellular_amount",
                "extracellular_concentration_mM",
                "extracellular_rate_fmol_per_s",
            ):
                c.require(obs[name][j][s][1] == 0, "Padded bath readout changed")
            co = b["outside_mM"][s] + outside[s][0] / vo
            checks.compare(
                f"{identifier}/outside_amount/{j}/{s}",
                obs["extracellular_amount"][j][s][0],
                co * vo,
                "amount_fmol",
                cumulative,
            )
            checks.compare(
                f"{identifier}/outside_concentration/{j}/{s}",
                obs["extracellular_concentration_mM"][j][s][0],
                co,
                "concentration_mM",
                instant,
            )
            for i in range(7):
                amount = b["inside_mM"][s] * vi[i] + inside[s][i]
                checks.compare(
                    f"{identifier}/amount/{j}/{s}/{i}",
                    obs["amount"][j][s][i],
                    amount,
                    "amount_fmol",
                    cumulative,
                )
                checks.compare(
                    f"{identifier}/concentration/{j}/{s}/{i}",
                    obs["concentration_mM"][j][s][i],
                    amount / vi[i],
                    "concentration_mM",
                    instant,
                )
                point = {
                    "inside_mM": amount / vi[i],
                    "outside_mM": co,
                    "voltage_V": voltages[i],
                    "valence": b["expected_valence"][s],
                    "temperature_K": 310.15,
                    "area_m2": g["cell_areas_m2"][i],
                    "permeability_m_per_s": b["permeability_m_per_s"][s] * availability,
                }
                checks.compare(
                    f"{identifier}/GHK/{j}/{s}/{i}",
                    flux[s][i],
                    c.oracle(point, constant),
                    "flux_fmol_per_s",
                    instant,
                )
                if row["condition"] == "static_blocked":
                    c.require(flux[s][i] == 0, "Blocked Cells flux changed")
            checks.compare(
                f"{identifier}/outside_rate/{j}/{s}",
                obs["extracellular_rate_fmol_per_s"][j][s][0],
                -math.fsum(flux[s][:7]),
                "flux_fmol_per_s",
                instant,
            )
        for i in range(7):
            voltage = (
                constant["F"]
                * 1e-15
                * math.fsum(b["expected_valence"][s] * inside[s][i] for s in range(3))
                / (g["cell_areas_m2"][i] * 0.01)
            )
            current = (
                constant["F"]
                * 1e-15
                * math.fsum(b["expected_valence"][s] * flux[s][i] for s in range(3))
            )
            checks.compare(
                f"{identifier}/charge/{j}/{i}", voltages[i], voltage, "voltage_V", instant
            )
            checks.compare(
                f"{identifier}/current/{j}/{i}",
                obs["membrane_current_A"][j][i],
                current,
                "current_A",
                instant,
            )
        canonical.append(
            {
                "voltage_V": voltages[:7],
                "amount_fmol": [v for a in inside for v in a[:7]] + [a[0] for a in outside],
                "transfer_fmol": [v for a in obs["leak_transferred"][j] for v in a[:7]],
                "flux_fmol_per_s": [v for a in flux for v in a[:7]] if j < count else [],
                "current_A": obs["membrane_current_A"][j][:7] if j < count else [],
            }
        )
    # Diagnostics and auxiliary thermodynamic exports are retained/finite, not
    # independently re-derived here. Core inventory/charge/rate laws above are.
    c.require(
        record["diagnostics"]
        and all(v >= 0 for v in numbers(list(record["diagnostics"].values()))),
        "Invalid Cells diagnostic export",
    )
    shaped(record["timings"]["total_run_seconds"], [])
    c.require(record["timings"]["total_run_seconds"] > 0, "Invalid execution timing")
    return canonical
