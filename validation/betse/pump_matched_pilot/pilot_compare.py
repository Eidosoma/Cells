"""Saved producer-side pilot checks; a later independent review is still required."""

import math

import pilot_context as ctx
from pilot_math import Ledger, contraction, native_rates, native_state
from pilot_reference import equations

c = ctx.c


def selected(record, times):
    result = {name: [] for name in ("states", "voltage_V")}
    for t in times:
        i = min(range(len(record["times_s"])), key=lambda i: abs(record["times_s"][i] - t))
        c.require(abs(record["times_s"][i] - t) < 1e-15, "Observation not on registered grid")
        for name in result:
            result[name].append(record[name][i])
    return result


def native_points(r, row, variant, ledger):
    p, case = r["protocol"], r["cases"][variant["id"]]
    trace = row["trace"]
    step = row["dt_s"]
    count = round(p["duration_s"] / step)
    c.require(
        row["steps"] == len(trace["steps"]) == len(trace["raw_steps"]) == count,
        "Native step coverage",
    )
    c.require(
        row["geometry"] == r["native_geometry"]
        and row["hook_restored"]
        and trace["pending"] is None,
        "Native geometry/lifecycle",
    )
    g = row["geometry"]
    initial = trace["initial"]["physical"]
    baseline = r["native_initial"][variant["id"]]
    c.require(initial == baseline, "Refined native initialization changed")
    inventory = max(
        math.fsum(
            [
                x * v / 1e-15
                for x, v in zip(initial["inside_mM"][s], g["cell_volumes_m3"], strict=True)
            ]
            + [initial["outside_mM"][s][0] * g["effective_bath_volume_m3"] / 1e-15]
        )
        for s in range(6)
    )
    state = [0.0] * 59
    first, voltage = native_state(row, 0, state)
    result = dict(times_s=[0.0], states=[first], voltage_V=[voltage])
    maxima = dict(material_fmol=0.0, energy_pJ=0.0, charge_C=0.0)
    for index, (boundary, raw) in enumerate(zip(trace["steps"], trace["raw_steps"], strict=True)):
        c.require(
            boundary["index"] == raw["index"] == index
            and boundary["before_elapsed_s"] == index * step
            and boundary["after_elapsed_s"] == (index + 1) * step,
            "Native elapsed clock",
        )
        previous = trace["initial"] if index == 0 else trace["steps"][index - 1]["after_voltage"]
        for field in ("inside_mM", "outside_mM", "at_membrane_mM", "voltage_V"):
            c.require(
                raw["before"]["physical"][field] == previous["physical"][field],
                "Disconnected native interval",
            )
        c.require(
            raw["before"]["rho_pump"] == variant["rho_pump"] and raw["before"]["pump_block"] == 1.0,
            "Changed pump controls",
        )
        rate = native_rates(row, variant, raw)
        before_state, before_voltage = native_state(row, index, state)
        expected = equations.rhs(case, before_state, (1.0, 1.0))
        tol = p["mapping"]
        ledger.compare(
            "native_live_rate_fmol_s", rate[:52], expected[:52], tol["flux_fmol_s"], tol["relative"]
        )
        ledger.compare(
            "native_live_dissipation_pJ_s",
            rate[52:],
            expected[52:],
            tol["power_pJ_s"],
            tol["relative"],
        )
        ledger.compare(
            "native_charge_voltage_V",
            before_voltage,
            equations.read_state(case, before_state)[2],
            tol["voltage_V"],
            tol["relative"],
        )
        state = [a + step * b for a, b in zip(state, rate, strict=True)]
        actual, voltage = native_state(row, index + 1, state)
        for s in range(3):
            # Both intracellular and shared-outside increments are checked;
            # the cumulative tolerance below is for floating accumulation only.
            predicted = [before_state[3 * i + s] + step * rate[3 * i + s] for i in range(7)]
            ledger.compare(
                "native_single_transfer_fmol",
                [actual[3 * i + s] for i in range(7)],
                predicted,
                tol["amount_fmol"],
                tol["relative"],
            )
            ledger.compare(
                "native_single_bath_transfer_fmol",
                actual[21 + s],
                before_state[21 + s] + step * rate[21 + s],
                tol["amount_fmol"],
                tol["relative"],
            )
        accounting = equations.accounting(case, actual)
        budget = (
            p["accounting"]["native_base_material_fmol"]
            + p["accounting"]["native_roundoff_multiplier"]
            * math.ulp(1.0)
            * (index + 1)
            * inventory
        )
        c.require(
            accounting["material_residual_fmol"] <= budget
            and accounting["charge_residual_C"] <= ctx.F * 1e-15 * 3 * budget,
            "Native accumulated conservation",
        )
        c.require(all(v >= -1e-14 for v in rate[52:]), "Negative native dissipation rate")
        maxima["material_fmol"] = max(maxima["material_fmol"], accounting["material_residual_fmol"])
        maxima["charge_C"] = max(maxima["charge_C"], accounting["charge_residual_C"])
        maxima["energy_pJ"] = max(maxima["energy_pJ"], accounting["energy_residual_pJ"])
        result["times_s"].append((index + 1) * step)
        result["states"].append(actual)
        result["voltage_V"].append(voltage)
    c.require(row["final"] == trace["steps"][-1]["after_voltage"], "Native final-state link")
    c.require(
        trace["sampled_indices"] == list(range(1, count))
        and row["histories"]["time"]["values"] == trace["labels_s"][1:],
        "Native storage coverage",
    )
    for history, field in (
        ("cc_time", "inside_mM"),
        ("cc_env_time", "outside_mM"),
        ("vm_time", "voltage_V"),
    ):
        c.require(
            row["histories"][history]["values"]
            == [trace["steps"][i]["after_voltage"]["physical"][field] for i in range(1, count)],
            "Native history misaligned",
        )
    return result, maxima


def differences(actual, target):
    return dict(
        amount=max(
            abs(x - y)
            for a, b in zip(actual["states"], target["states"], strict=True)
            for x, y in zip(a[:52], b[:52], strict=True)
        ),
        energy=max(
            abs(x - y)
            for a, b in zip(actual["states"], target["states"], strict=True)
            for x, y in zip(a[52:], b[52:], strict=True)
        ),
        voltage=max(
            abs(x - y)
            for a, b in zip(actual["voltage_V"], target["voltage_V"], strict=True)
            for x, y in zip(a, b, strict=True)
        ),
    )


def compare(r, output):
    plan = r["protocol"]
    reference = c.read(output / "reference.json")["records"]
    native = c.read(output / "betse.json")["records"]
    cells_packet = c.read(output / "cells.json")
    cells = cells_packet["records"]
    ledger = Ledger()
    error_rows, refinements, accounting = {}, {}, {}
    for variant in r["native_preparation"]["protocol"]["variants"]:
        identifier = variant["id"]
        primary = selected(
            reference[identifier + "/" + plan["reference"]["primary"]], plan["common_times_s"]
        )
        native_ladder = []
        native_finest = None
        for step in plan["native_steps_s"]:
            key = ctx.key(identifier, step)
            row = c.read(output / native[key + "/observed"])
            quiet = c.read(output / native[key + "/unobserved"])
            for field in set(row) - {"mode", "trace"}:
                c.require(row[field] == quiet[field], "Native observer pair mismatch")
            points, balances = native_points(r, row, variant, ledger)
            picked = selected(points, plan["common_times_s"])
            error = differences(picked, primary)
            error_rows["native/" + key] = error
            accounting[key] = balances
            native_ladder.append(error)
            if step == plan["native_steps_s"][-1]:
                native_finest = picked
                for part, start, stop, absolute in (
                    ("amount", 0, 52, "native_amount_fmol"),
                    ("energy", 52, 59, "native_energy_pJ"),
                ):
                    ledger.compare(
                        "native_finest_" + part,
                        [v[start:stop] for v in picked["states"]],
                        [v[start:stop] for v in primary["states"]],
                        plan["trajectory"][absolute],
                        plan["trajectory"]["relative"],
                    )
                ledger.compare(
                    "native_finest_voltage",
                    picked["voltage_V"],
                    primary["voltage_V"],
                    plan["trajectory"]["native_voltage_V"],
                    plan["trajectory"]["relative"],
                )
                c.require(
                    balances["energy_pJ"] <= plan["accounting"]["native_finest_energy_pJ"],
                    "Native finest energy closure",
                )
        cells_ladder = []
        for step in plan["cells_steps_s"]:
            key = ctx.key(identifier, step) + "/jax_jit"
            row = cells[key]
            c.require(row["times_s"] == plan["common_times_s"], "Cells common times")
            error = differences(row, primary)
            error_rows["cells/" + key] = error
            cells_ladder.append(error)
            ledger.compare(
                "cells_reference_state",
                row["states"],
                primary["states"],
                plan["trajectory"]["cells_state_atol"],
                plan["trajectory"]["cells_state_rtol"],
            )
            ledger.compare(
                "cells_reference_voltage",
                row["voltage_V"],
                primary["voltage_V"],
                plan["trajectory"]["cells_voltage_V"],
            )
            if step == plan["cells_steps_s"][-1]:
                factor = plan["trajectory"]["cross_engine_budget_multiplier"]
                ledger.compare(
                    "cross_engine_amount",
                    [v[:52] for v in native_finest["states"]],
                    [v[:52] for v in row["states"]],
                    factor * plan["trajectory"]["native_amount_fmol"],
                    plan["trajectory"]["relative"],
                )
                ledger.compare(
                    "cross_engine_energy",
                    [v[52:] for v in native_finest["states"]],
                    [v[52:] for v in row["states"]],
                    factor * plan["trajectory"]["native_energy_pJ"],
                    plan["trajectory"]["relative"],
                )
                ledger.compare(
                    "cross_engine_voltage",
                    native_finest["voltage_V"],
                    row["voltage_V"],
                    factor * plan["trajectory"]["native_voltage_V"],
                    plan["trajectory"]["relative"],
                )
        for engine, ladder in (("native", native_ladder), ("cells", cells_ladder)):
            for name, floor in (
                ("amount", "floor_amount_fmol"),
                ("energy", "floor_energy_pJ"),
                ("voltage", "floor_voltage_V"),
            ):
                refinements[identifier + "/" + engine + "/" + name] = contraction(
                    [v[name] for v in ladder],
                    plan["refinement"][floor],
                    plan["refinement"]["contraction_max"],
                )
        base = ctx.key(identifier, plan["cells_eager_step_s"])
        eager, jit = (cells[base + "/" + b] for b in ("jax_eager", "jax_jit"))
        ledger.compare("backend_state", eager["states"], jit["states"], 2e-12, 2e-11)
        ledger.compare("backend_voltage", eager["voltage_V"], jit["voltage_V"], 2e-10, 2e-11)
    for row in cells.values():
        diag = row["diagnostics"]
        c.require(
            max(
                diag[k]
                for k in (
                    "max_balance_error_fmol",
                    "max_extracellular_balance_error_fmol",
                    "max_global_balance_error_fmol",
                )
            )
            <= plan["accounting"]["cells_material_fmol"]
            and diag["max_countercharge_error_C"] <= plan["accounting"]["cells_charge_C"]
            and diag["max_energy_balance_error_pJ"] <= plan["accounting"]["cells_energy_pJ"],
            "Production accounting",
        )
    c.require(
        len(cells_packet["resumes"]) == 6
        and all(v["full_state_bitwise_equal"] for v in cells_packet["resumes"].values()),
        "Restart coverage",
    )
    return dict(
        status="matched_pump_pilot_pass_pending_independent_review",
        comparisons=ledger.comparisons,
        maxima=ledger.maxima,
        reference_errors=error_rows,
        refinement=refinements,
        native_accounting=accounting,
        observer_pairs=18,
        restart_suffixes=6,
        production_changed=False,
        biology_validated=False,
        gpu_tested=False,
        stable_release_promoted=False,
        automatic_followup=False,
    )
