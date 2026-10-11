"""Model-free comparison of actual probes with independent full-state mathematics."""

import math

import history_context as ctx
import history_math as independent

c, ind = ctx.c, independent.ind


def values(record):
    ctx.prior.pilot.audit.preparation.validate_array_record(record)
    return record["values"]


def compare_native(data, plan, result, ledger):
    expected_keys = {
        name + f"/dt_{step:.8g}" for name in plan["histories"] for step in plan["native_steps_s"]
    }
    c.require(set(result["rows"]) == expected_keys, "Native row membership")
    voltages = data["native_voltage_V"]
    c.require(
        result["native_gate_batch_updates"] == len(expected_keys)
        and result["native_scalar_gate_updates"] == len(expected_keys) * len(voltages),
        "Native update counts",
    )
    for key, row in result["rows"].items():
        gates = plan["histories"][key.split("/")[0]]
        c.require(
            row["voltage_V"] == voltages
            and row["input_unchanged"] is True
            and key.endswith(f"/dt_{row['dt_s']:.8g}"),
            "Native input or step differs",
        )
        c.require(row["before"] == [[g] * len(voltages) for g in gates], "Native fixture differs")
        for field in ("before", "after", "target", "tau_s", "equilibrium_gate"):
            c.require(
                len(row[field]) == 2 and all(len(a) == len(voltages) for a in row[field]),
                "Native gate array shape",
            )
        c.require(
            all(
                len(row[field]) == len(voltages)
                for field in ("initial_open_derived", "open_after_native")
            ),
            "Native open shape",
        )
        for i, voltage in enumerate(voltages):
            target, tau = ind.kinetics(voltage)
            after = ind.gate_values(voltage, gates, row["dt_s"])
            for j in range(2):
                ledger.compare(f"native/{key}/{i}/gate{j}", row["after"][j][i], after[j], "gate")
                ledger.compare(
                    f"native/{key}/{i}/target{j}", row["target"][j][i], float(target[j]), "gate"
                )
                ledger.compare(
                    f"native/{key}/{i}/tau{j}", row["tau_s"][j][i], float(tau[j]), "tau_s"
                )
                ledger.compare(
                    f"native/{key}/{i}/equilibrium{j}",
                    row["equilibrium_gate"][j][i],
                    float(target[j]),
                    "gate",
                )
            ledger.compare(
                f"native/{key}/{i}/initial_P",
                row["initial_open_derived"][i],
                gates[0] * gates[1],
                "gate",
            )
            ledger.compare(
                f"native/{key}/{i}/final_P",
                row["open_after_native"][i],
                after[0] * after[1],
                "gate",
            )


def compare_cells(data, plan, result, ledger):
    c.require(
        set(result["rows"])
        == {key + "/" + backend for key in data["definitions"] for backend in plan["backends"]}
        and set(result["candidates"]) == set(data["definitions"]),
        "Cells row membership",
    )
    c.require(result["initial_rhs_evaluations"] == len(result["rows"]), "Cells rate counts")
    c.require(result["cells_trajectory_runs"] == 0, "Unexpected Cells trajectory")
    for identifier, definition in data["definitions"].items():
        variant, history = identifier.split("/")
        par, gates = data["parameters"][variant], plan["histories"][history]
        oracle = independent.initial_rates(par, gates)
        expected_state, expected_rhs = independent.expected_arrays(definition, oracle)
        n = len(par["volume_pL"])
        nc, nk = (definition["execution"][key] for key in ("capacity", "channel_capacity"))
        for backend in plan["backends"]:
            key = identifier + "/" + backend
            row = result["rows"][key]
            c.require(row["integration_executed"] is False, "Unexpected rollout")
            c.require(set(row["state"]) == set(row["rhs"]) == set(expected_state), "State fields")
            c.require(
                set(row["channel"])
                == {
                    "open_probability",
                    "effective_permeability_m_per_s",
                    "flux_fmol_per_s",
                    "dissipation_rate_pJ_per_s",
                },
                "Channel readout fields",
            )
            for field, expected in expected_state.items():
                c.require(values(row["state"][field]) == expected, "Full initial state differs")
                actual = values(row["rhs"][field])
                unit = (
                    "gate_rate_per_s"
                    if field == "gate"
                    else ("power_pJ_per_s" if "energy" in field else "flux_fmol_per_s")
                )
                ledger.compare(key + "/rhs/" + field, actual, expected_rhs[field], unit)

                # Absent contributions and padding must be exactly zero, not just small.
                def exact_zero(a, b):
                    if isinstance(b, list):
                        for av, bv in zip(a, b, strict=True):
                            exact_zero(av, bv)
                    elif b == 0:
                        c.require(a == 0, "Inactive/blocked rate is not exactly zero")

                exact_zero(actual, expected_rhs[field])
            for field, expected, unit in (
                ("open_probability", [gates[0] * gates[1]] * n, "gate"),
                (
                    "effective_permeability_m_per_s",
                    oracle["permeability_m_per_s"],
                    "permeability_m_per_s",
                ),
                ("flux_fmol_per_s", oracle["inward_K_fmol_per_s"], "flux_fmol_per_s"),
                ("dissipation_rate_pJ_per_s", oracle["dissipation_pJ_per_s"], "power_pJ_per_s"),
            ):
                actual = values(row["channel"][field])
                ledger.compare(key + "/" + field, actual, expected + [0.0] * (nk - n), unit)
                c.require(all(v == 0 for v in actual[n:]), "Channel readout padding")
            ledger.compare(
                key + "/voltage",
                values(row["voltage"]),
                oracle["voltage_V"] + [0.0] * (nc - n),
                "voltage_V",
            )
            c.require(all(v == 0 for v in values(row["voltage"])[n:]), "Voltage padding")
            actual_open_rate = [
                independent.open_rate(gates, [row["rhs"]["gate"]["values"][j][i] for j in range(2)])
                for i in range(n)
            ]
            expected_open_rate = [
                independent.open_rate(gates, [oracle["gate_rate_per_s"][j][i] for j in range(2)])
                for i in range(n)
            ]
            ledger.compare(
                key + "/open_rate", actual_open_rate, expected_open_rate, "open_rate_per_s"
            )
        candidates = result["candidates"][identifier]
        c.require(
            [v["dt_s"] for v in candidates] == plan["candidate_cells_steps_s"], "Candidate panel"
        )
        for candidate in candidates:
            grid, steps = candidate["grid_s"], candidate["steps"]
            c.require(
                grid[0] == 0
                and grid[-1] == plan["candidate_duration_s"]
                and len(grid) == steps + 1
                and all(a < b for a, b in zip(grid[:-1], grid[1:], strict=True))
                and max(b - a for a, b in zip(grid[:-1], grid[1:], strict=True))
                <= candidate["dt_s"] * (1 + 1e-12)
                and 0 < steps <= definition["execution"]["max_steps"]
                and 0
                < candidate["estimated_trace_bytes"]
                <= candidate["max_trace_bytes"]
                == definition["execution"]["max_trace_bytes"],
                "Candidate resource/grid contract",
            )


def compare_pairs(data, plan, cells, ledger):
    witnesses = {}
    for variant in plan["variants"]:
        a, b = (data["definitions"][variant + "/" + name] for name in ("a", "b"))
        c.require(independent.without_gates(a) == independent.without_gates(b), "Pair confounds")
        witness = independent.witness(
            data["parameters"][variant], plan["histories"]["a"], plan["histories"]["b"]
        )
        c.require(
            min(map(abs, witness["open_rate_difference_per_s"]))
            >= plan["minimum_open_rate_separation_per_s"],
            "History signal too small",
        )
        witnesses[variant] = witness
        for backend in plan["backends"]:
            first, second = (cells["rows"][f"{variant}/{name}/{backend}"] for name in ("a", "b"))
            c.require(first["layout_sha256"] == second["layout_sha256"], "History changed layout")
            c.require(first["voltage"] == second["voltage"], "Initial voltages differ")
            for field in first["state"]:
                if field != "gate":
                    c.require(
                        first["state"][field] == second["state"][field], "Pair state confound"
                    )
                    # Equal gate product means equal initial material/energy/voltage rates.
                    c.require(
                        first["rhs"][field] == second["rhs"][field], "Initial visible rates differ"
                    )
            for field in ("open_probability", "effective_permeability_m_per_s", "flux_fmol_per_s"):
                c.require(
                    first["channel"][field] == second["channel"][field], "Initial current differs"
                )
            actual = []
            n = len(data["parameters"][variant]["volume_pL"])
            for i in range(n):
                rates = []
                for row, gates in (
                    (first, plan["histories"]["a"]),
                    (second, plan["histories"]["b"]),
                ):
                    rates.append(
                        independent.open_rate(
                            gates, [row["rhs"]["gate"]["values"][j][i] for j in range(2)]
                        )
                    )
                actual.append(math.fsum((rates[0], -rates[1])))
            ledger.compare(
                f"{variant}/{backend}/history_witness",
                actual,
                witness["open_rate_difference_per_s"],
                "open_rate_per_s",
            )
    return witnesses


def check(data, plan, native, cells):
    ledger = ctx.io.Ledger(plan["absolute"], relative=plan["relative"])
    compare_native(data, plan, native, ledger)
    compare_cells(data, plan, cells, ledger)
    witnesses = compare_pairs(data, plan, cells, ledger)
    return ledger.summary() | {
        "failures": ledger.failures,
        "history_witnesses": witnesses,
        "native_gate_batch_updates": native["native_gate_batch_updates"],
        "native_scalar_gate_updates": native["native_scalar_gate_updates"],
        "cells_initial_rhs_evaluations": cells["initial_rhs_evaluations"],
        "candidate_definitions": sum(len(v) for v in cells["candidates"].values()),
        "coupled_trajectories_run": False,
        "reference_integration_run": False,
        "history_trajectory_qualified": False,
        "gpu_tested": False,
        "biology_validated": False,
    }
