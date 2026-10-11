"""Evaluate saved complete-state candidate/reference columns; no trajectory calls."""

import math

import coupled_reference as ref
from coupled_plan import c


def compare(plan, reference, candidate):
    summaries, refinements, errors = [], [], {}
    expected = {case["id"] for case in plan["cases"]}
    c.require(set(reference) == set(candidate) == expected, "Case coverage changed")
    total = 0
    for case in plan["cases"]:
        name = case["id"]
        refs, trial = reference[name], candidate[name]
        c.require(set(refs) == set(plan["reference_methods"]), "Reference method coverage")
        n, width = len(case["volume_pL"]), ref.size(case)
        times, target = refs["Radau"]["times_s"], refs["Radau"]["state"]
        expected_times = [
            k * plan["sample_dt_s"]
            for k in range(round(case["end_time_s"] / plan["sample_dt_s"]) + 1)
        ]
        c.require(
            len(times) == len(expected_times)
            and all(abs(t - u) <= 1e-15 for t, u in zip(times, expected_times, strict=True)),
            "Reference times",
        )
        c.require(
            len(target) == len(times) and all(len(row) == width for row in target),
            "Reference shape",
        )
        sets = {"DOP853": refs["DOP853"]}
        expected_trials = {
            f"{engine}/{dt}" for engine in ("numpy", "jax_jit") for dt in plan["rk4_steps_s"]
        }
        c.require(set(trial["trajectories"]) == expected_trials, "Candidate trajectory coverage")
        sets.update(trial["trajectories"])
        for label, sample in sets.items():
            values = sample["state"]
            c.require(len(values) == len(target), "Incomplete samples")
            c.require(
                len(sample["times_s"]) == len(times)
                and all(abs(t - u) <= 1e-15 for t, u in zip(sample["times_s"], times, strict=True)),
                "Sample time mismatch",
            )
            scaled, max_v = 0.0, 0.0
            residuals = {
                "material_residual_fmol": 0.0,
                "charge_residual_C": 0.0,
                "energy_residual_pJ": 0.0,
            }
            if label != "DOP853":
                dt, full = sample["step_s"], sample["full_state"]
                c.require(
                    dt in plan["rk4_steps_s"] and len(full) == round(case["end_time_s"] / dt) + 1,
                    "Full endpoint coverage",
                )
                c.require(full[:: round(plan["sample_dt_s"] / dt)] == values, "Sample/full linkage")
                for full_row in full:
                    c.require(
                        len(full_row) == width and all(math.isfinite(v) for v in full_row),
                        "Invalid full state",
                    )
                    physical = ref.accounting(case, full_row)
                    for key in residuals:
                        residuals[key] = max(residuals[key], physical[key])
                    c.require(min(full_row[7 * n + 3 :]) >= -1e-14, "Negative full dissipation")
                    if name == "all_blocked":
                        c.require(all(v == 0 for v in full_row), "Blocked full state changed")
                if name == "pump_block_release":
                    blocked = full[round(0.004 / dt) : round(0.006 / dt) + 1]
                    c.require(
                        all(
                            row[6 * n + 3 : 7 * n + 3] == blocked[0][6 * n + 3 : 7 * n + 3]
                            for row in blocked
                        ),
                        "Pump cycle ledger changed during block",
                    )
            for row, wanted in zip(values, target, strict=True):
                c.require(
                    len(row) == width and all(math.isfinite(x) for x in row), "Invalid state row"
                )
                for actual, expected_value in zip(row, wanted, strict=True):
                    scaled = max(
                        scaled,
                        abs(actual - expected_value)
                        / (plan["state_atol"] + plan["state_rtol"] * abs(expected_value)),
                    )
                    total += 1
                physical, wanted_physical = ref.accounting(case, row), ref.accounting(case, wanted)
                max_v = max(
                    max_v,
                    *(
                        abs(a - b)
                        for a, b in zip(
                            physical["voltage_V"], wanted_physical["voltage_V"], strict=True
                        )
                    ),
                )
                for key in residuals:
                    residuals[key] = max(residuals[key], physical[key], wanted_physical[key])
                c.require(min(row[7 * n + 3 :]) >= -1e-14, "Negative dissipation ledger")
                if name == "all_blocked":
                    c.require(all(x == 0 for x in row), "Blocked state changed")
            limits = {
                "material_residual_fmol": plan["material_atol_fmol"],
                "charge_residual_C": plan["charge_atol_C"],
                "energy_residual_pJ": plan["energy_atol_pJ"],
            }
            passed = (
                scaled <= 1
                and max_v <= plan["voltage_atol_V"]
                and all(residuals[k] <= v for k, v in limits.items())
            )
            summaries.append(
                {
                    "case": name,
                    "method": label,
                    "max_scaled_state_error": scaled,
                    "max_voltage_error_V": max_v,
                    **residuals,
                    "pass": passed,
                }
            )
            errors[name, label] = scaled
        for engine in ("numpy", "jax_jit"):
            coarse, fine = [errors[name, f"{engine}/{dt}"] for dt in plan["rk4_steps_s"]]
            bound = max(
                plan["refinement_ratio_limit"] * coarse, plan["roundoff_scaled_error_floor"]
            )
            refinements.append(
                {
                    "case": name,
                    "engine": engine,
                    "coarse": coarse,
                    "fine": fine,
                    "bound": bound,
                    "pass": fine <= bound,
                    "roundoff_limited": coarse <= plan["roundoff_scaled_error_floor"],
                }
            )
        c.require(trial["restart_exact"] is True, "Complete-state restart mismatch")
        c.require(set(trial["checkpoints"]) == {"numpy", "jax_jit"}, "Restart coverage")
        for engine, checkpoint in trial["checkpoints"].items():
            dt = plan["rk4_steps_s"][-1]
            full = trial["trajectories"][f"{engine}/{dt}"]["full_state"]
            index = round(checkpoint["time_s"] / dt)
            c.require(
                checkpoint["time_s"] == 0.006
                and checkpoint["exact"] is True
                and checkpoint["complete_state"] == full[index]
                and checkpoint["suffix_state"] == full[index:],
                "Checkpoint byte-value linkage",
            )
    return {
        "status": "pass" if all(r["pass"] for r in summaries + refinements) else "failed",
        "state_comparisons": total,
        "groups": summaries,
        "refinement": refinements,
        "production_model_accepted": False,
        "native_betse_trajectory_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
        "independent_capture_audit_complete": False,
    }
