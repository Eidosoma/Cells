"""Same numerical criteria, durable non-fail-fast mismatch reporting; no ODE runs."""

import math
import sys

import refinement_context as ctx
from pilot_compare import differences, native_points, selected
from pilot_math import flat

c = ctx.c


class Ledger:
    def __init__(self, limit=64):
        self.scope = ""
        self.limit = limit
        self.comparisons = 0
        self.failed_comparisons = 0
        self.maxima = {}
        self.failed_groups = {}
        self.examples = []

    def compare(self, name, actual, expected, atol, rtol=0.0):
        a, b = list(flat(actual)), list(flat(expected))
        c.require(len(a) == len(b) and a, "Comparison extent: " + name)
        group = self.scope + "/" + name
        for index, (x, y) in enumerate(zip(a, b, strict=True)):
            c.require(math.isfinite(x) and math.isfinite(y), "Nonfinite comparison: " + group)
            error, budget = abs(x - y), atol + rtol * abs(y)
            c.require(math.isfinite(budget) and budget >= 0, "Invalid comparison budget")
            self.comparisons += 1
            self.maxima[group] = max(self.maxima.get(group, 0.0), error)
            if error > budget:
                self.failed_comparisons += 1
                self.failed_groups[group] = self.failed_groups.get(group, 0) + 1
                if len(self.examples) < self.limit:
                    self.examples.append(
                        dict(
                            group=group,
                            index=index,
                            actual=x,
                            expected=y,
                            error=error,
                            budget=budget,
                        )
                    )


def refinement(errors, floor, ratio):
    c.require(
        len(errors) == 3 and all(math.isfinite(v) and v >= 0 for v in errors),
        "Invalid refinement errors",
    )
    return dict(
        errors=errors,
        floor=floor,
        passed=all(
            a <= floor or b <= ratio * a for a, b in zip(errors[:-1], errors[1:], strict=True)
        ),
        roundoff_or_reference_limited=all(v <= floor for v in errors),
    )


def state_checks(ledger, prefix, actual, expected, amount, energy, voltage, relative):
    for field, start, stop, tolerance in (("amount", 0, 52, amount), ("energy", 52, 59, energy)):
        ledger.compare(
            prefix + "_" + field,
            [v[start:stop] for v in actual["states"]],
            [v[start:stop] for v in expected["states"]],
            tolerance,
            relative,
        )
    ledger.compare(
        prefix + "_voltage", actual["voltage_V"], expected["voltage_V"], voltage, relative
    )


def row_identity(row, identifier, mode, step, duration):
    c.require(
        row["id"] == identifier
        and row["mode"] == mode
        and row["dt_s"] == step
        and row["steps"] == round(duration / step)
        and (row["trace"] is None) == (mode == "unobserved"),
        "Native row identity or registered timestep changed",
    )


def compare(r, output):
    p = r["protocol"]
    t = p["trajectory"]
    reference = c.read(output / "reference.json")["records"]
    native = c.read(output / "betse.json")["records"]
    cells_packet = c.read(output / "cells.json")
    cells = cells_packet["records"]
    previous = c.read(ctx.PRIOR / "betse.json")["records"]
    c.require(
        len(native) == 36 and len(cells) == 24 and len(reference) == 18, "Comparison coverage"
    )
    ledger = Ledger(r["amendment"]["failure_examples_limit"])
    ladders, balances, refinements, overlap_records = {}, {}, {}, {}
    for variant in r["native_preparation"]["protocol"]["variants"]:
        identifier = variant["id"]
        primary = selected(
            reference[identifier + "/" + p["reference"]["primary"]], p["common_times_s"]
        )
        native_ladder = []
        native_finest = None
        for dt in p["native_steps_s"]:
            key = ctx.base.key(identifier, dt)
            observed, quiet = (
                c.read(output / native[key + "/" + mode]) for mode in ("observed", "unobserved")
            )
            row_identity(observed, identifier, "observed", dt, p["duration_s"])
            row_identity(quiet, identifier, "unobserved", dt, p["duration_s"])
            c.require(
                set(observed) == set(quiet)
                and all(observed[n] == quiet[n] for n in observed if n not in ("mode", "trace")),
                "Observer interference",
            )
            if dt == r["amendment"]["overlap_step_s"]:
                for mode, row in (("observed", observed), ("unobserved", quiet)):
                    overlap_records[key + "/" + mode] = ctx.overlap(
                        row, c.read(ctx.PRIOR / previous[key + "/" + mode])
                    )
            ledger.scope = "native/" + key
            points, accounting = native_points(r, observed, variant, ledger)
            picked = selected(points, p["common_times_s"])
            errors = differences(picked, primary)
            ladders[ledger.scope] = errors
            balances[key] = accounting
            native_ladder.append(errors)
            if dt == p["native_steps_s"][-1]:
                native_finest = picked
                state_checks(
                    ledger,
                    "finest_reference",
                    picked,
                    primary,
                    t["native_amount_fmol"],
                    t["native_energy_pJ"],
                    t["native_voltage_V"],
                    t["relative"],
                )
                ledger.compare(
                    "energy_balance",
                    accounting["energy_pJ"],
                    0.0,
                    p["accounting"]["native_finest_energy_pJ"],
                )
            path = output / "comparison_rows" / key / "result.json"
            path.parent.mkdir(parents=True, exist_ok=False)
            c.write(
                path,
                dict(
                    points=points,
                    accounting=accounting,
                    reference_errors=errors,
                    cumulative_failed_comparisons=ledger.failed_comparisons,
                    cumulative_failed_groups=ledger.failed_groups,
                    first_failure_examples=ledger.examples,
                ),
            )
            print("native comparison saved: " + key, flush=True)
        cells_ladder = []
        for dt in p["cells_steps_s"]:
            key = ctx.base.key(identifier, dt) + "/jax_jit"
            row = cells[key]
            c.require(row["times_s"] == p["common_times_s"], "Cells common grid changed")
            ledger.scope = "reused_cells/" + key
            error = differences(row, primary)
            ladders[ledger.scope] = error
            cells_ladder.append(error)
            ledger.compare(
                "reference_state",
                row["states"],
                primary["states"],
                t["cells_state_atol"],
                t["cells_state_rtol"],
            )
            ledger.compare(
                "reference_voltage", row["voltage_V"], primary["voltage_V"], t["cells_voltage_V"]
            )
            if dt == p["cells_steps_s"][-1]:
                factor = t["cross_engine_budget_multiplier"]
                state_checks(
                    ledger,
                    "cross_engine",
                    native_finest,
                    row,
                    factor * t["native_amount_fmol"],
                    factor * t["native_energy_pJ"],
                    factor * t["native_voltage_V"],
                    t["relative"],
                )
        for engine, values in (("native", native_ladder), ("cells", cells_ladder)):
            for name, floor in (
                ("amount", "floor_amount_fmol"),
                ("energy", "floor_energy_pJ"),
                ("voltage", "floor_voltage_V"),
            ):
                refinements[identifier + "/" + engine + "/" + name] = refinement(
                    [v[name] for v in values],
                    p["refinement"][floor],
                    p["refinement"]["contraction_max"],
                )
        key = ctx.base.key(identifier, p["cells_eager_step_s"])
        eager, jit = (cells[key + "/" + name] for name in ("jax_eager", "jax_jit"))
        ledger.scope = "reused_backends/" + identifier
        ledger.compare("state", eager["states"], jit["states"], 2e-12, 2e-11)
        ledger.compare("voltage", eager["voltage_V"], jit["voltage_V"], 2e-10, 2e-11)
    for key, row in cells.items():
        ledger.scope = "reused_accounting/" + key
        for names, budget in (
            (
                (
                    "max_balance_error_fmol",
                    "max_extracellular_balance_error_fmol",
                    "max_global_balance_error_fmol",
                ),
                "cells_material_fmol",
            ),
            (("max_countercharge_error_C",), "cells_charge_C"),
            (("max_energy_balance_error_pJ",), "cells_energy_pJ"),
        ):
            ledger.compare(
                budget,
                [row["diagnostics"][k] for k in names],
                [0.0] * len(names),
                p["accounting"][budget],
            )
    c.require(
        len(overlap_records) == 12
        and len(cells_packet["resumes"]) == 6
        and all(v["full_state_bitwise_equal"] for v in cells_packet["resumes"].values()),
        "Overlap/reused restart coverage",
    )
    success = ledger.failed_comparisons == 0 and all(v["passed"] for v in refinements.values())
    c.require(
        not any(
            n == "cells" or n.startswith("cells.") or n == "betse" or n.startswith("betse.")
            for n in sys.modules
        ),
        "Comparator imported a simulator",
    )
    return dict(
        status="refined_pump_pilot_pass_pending_independent_review"
        if success
        else "refined_pump_pilot_failed_not_qualified",
        comparisons=ledger.comparisons,
        failed_comparisons=ledger.failed_comparisons,
        failed_groups=ledger.failed_groups,
        first_failure_examples=ledger.examples,
        failure_examples_truncated=ledger.failed_comparisons > len(ledger.examples),
        maxima=ledger.maxima,
        reference_errors=ladders,
        refinement=refinements,
        native_accounting=balances,
        exact_overlap_records=overlap_records,
        native_runs=36,
        observer_pairs=18,
        reused_cells_trajectories=24,
        reused_reference_solves=18,
        reused_restart_suffixes=6,
        new_cells_trajectories=0,
        new_reference_solves=0,
        production_changed=False,
        scientific_tolerances_changed=False,
        biology_validated=False,
        gpu_tested=False,
        automatic_followup=False,
    )
