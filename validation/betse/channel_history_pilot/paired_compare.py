"""Per-history convergence and explicit contrasts, preserving coarse rejections."""

import math

import feedback_compare as old
import paired_cells_check as cells_check
import paired_context as ctx
import paired_native_check as native_check
import paired_reference_check as reference_check
from feedback_audit_cells import checkpoint

c, io = ctx.c, ctx.io


def difference(left, right):
    if isinstance(left, list):
        c.require(isinstance(right, list) and len(left) == len(right), "Contrast axes")
        return [difference(a, b) for a, b in zip(left, right, strict=True)]
    c.require(
        type(left) in (int, float)
        and type(right) in (int, float)
        and math.isfinite(left)
        and math.isfinite(right),
        "Contrast scalar",
    )
    return left - right


def contrast_points(first, second):
    c.require(len(first) == len(second), "Contrast clocks/length")
    result = []
    for a, b in zip(first, second, strict=True):
        c.require(set(a) == set(b), "Contrast fields")
        result.append({k: difference(a[k], b[k]) for k in a})
    return result


def reference_signal(protocol, reference):
    c.require(set(reference) == {"a", "b"}, "Paired reference membership")
    c.require(
        all(
            v["status"] == "pass" and v["reference_convergence_checked"] for v in reference.values()
        ),
        "References must converge before selecting the candidate horizon",
    )
    signal = {}
    for variant in protocol["variants"]:
        a, b = (reference[n]["reference_solutions"][variant] for n in ("a", "b"))
        c.require(
            a["times_s"] == b["times_s"] and a["times_s"][-1] == protocol["candidate_duration_s"],
            "Paired reference clocks",
        )
        for field in a["readouts"][0]:
            if field != "gate":
                c.require(
                    a["readouts"][0][field] == b["readouts"][0][field], "Initial reference confound"
                )
        first, second = a["readouts"][-1], b["readouts"][-1]
        voltage = difference(first["voltage_V"], second["voltage_V"])
        opened = difference(
            [m * h for m, h in zip(*first["gate"], strict=True)],
            [m * h for m, h in zip(*second["gate"], strict=True)],
        )
        if variant == "active_channel":
            c.require(
                min(map(abs, voltage)) >= protocol["minimum_final_voltage_contrast_V"]
                and min(map(abs, opened)) >= protocol["minimum_final_open_fraction_contrast"],
                "Candidate horizon has insufficient resolved history signal",
            )
        else:
            c.require(all(v == 0 for v in voltage), "Blocked voltage contrast is not zero")
        signal[variant] = {"voltage_contrast_V": voltage, "open_fraction_contrast": opened}
    return signal


def references(r, output, aggregate):
    c.require(set(aggregate["by_history"]) == set(r["views"]), "Reference history coverage")
    results = {
        name: reference_check.check(view, output / name, aggregate["by_history"][name])
        for name, view in r["views"].items()
    }
    # Each history's complete reference gate is durable even if the signal screen fails.
    try:
        signal = reference_signal(r["protocol"], results)
    except ValueError as error:
        io.write(
            output / "reference-gate.json",
            {
                "status": "fail",
                "reason": str(error),
                "simulators_allowed": False,
                "history_status": {k: v["status"] for k, v in results.items()},
            },
        )
        raise
    io.write(
        output / "reference-gate.json",
        {
            "status": "pass",
            "simulators_allowed": True,
            "selected_duration_s": r["protocol"]["candidate_duration_s"],
            "reference_solves": sum(v["reference_solves"] for v in results.values()),
            "history_status": {k: v["status"] for k, v in results.items()},
            "signal": signal,
            "history_gate_sha256": {
                name: c.sha(output / name / "reference-gate.json.gz") for name in results
            },
            "integration_precision": "float64",
            "rhs_precision_digits": 80,
            "scope": "Registered samples and method/tolerance agreement; "
            "not a rigorous all-times ODE bound.",
        },
    )
    return results


def checkpoints(view, output, aggregate, sources):
    count = arrays = 0
    for key, path in aggregate["records"].items():
        record = io.read_compressed(output / path)
        selected = [("final-checkpoint", record, len(record["times"]["values"]) - 1)]
        if key in aggregate["resumed"]:
            resumed = io.read_compressed(output / aggregate["resumed"][key])
            index = round(view["protocol"]["restart_time_s"] / view["protocol"]["restart_step_s"])
            selected += [
                ("midpoint-checkpoint", record, index),
                ("resumed-checkpoint", resumed, len(resumed["times"]["values"]) - 1),
            ]
        for name, row, index in selected:
            arrays += checkpoint(output / "cells" / key / name, row, index, sources, c.read, c.sha)
            count += 1
    return {"checkpoints": count, "checkpoint_arrays": arrays}


def histories(r, output, reference, results):
    comparisons = {}
    for variant in r["protocol"]["variants"]:
        primary = []
        for name in ("a", "b"):
            ref = reference[name]["reference_solutions"][variant]
            tick = r["views"][name]["protocol"]["reference"]["sample_dt_s"]
            primary.append(
                [ref["readouts"][round(t / tick)] for t in r["protocol"]["common_times_s"]]
            )
        expected = contrast_points(*primary)
        engine_points = {}
        for engine, backend, step_key in (
            ("native", None, "native_steps_s"),
            ("cells", "jax_jit", "cells_steps_s"),
        ):
            paired = [
                results[name][engine]["points"][
                    ctx.feedback.key(variant, r["protocol"][step_key][-1], backend)
                ]
                for name in ("a", "b")
            ]
            for field in paired[0][0]:
                if field != "gate":
                    c.require(
                        paired[0][0][field] == paired[1][0][field],
                        "Initial simulator pair confound",
                    )
            actual = contrast_points(*paired)
            engine_points[engine] = actual
            comparisons[variant + "/" + engine] = old.compare_points(
                "history_contrast/" + variant + "/" + engine,
                actual,
                expected,
                r["views"]["a"]["protocol"],
                output,
                energy=engine == "cells",
                multiplier=r["protocol"]["contrast_budget_multiplier"],
            )
        comparisons[variant + "/cross_engine"] = old.compare_points(
            "history_contrast/" + variant + "/cross_engine",
            engine_points["native"],
            engine_points["cells"],
            r["views"]["a"]["protocol"],
            output,
            energy=False,
            multiplier=r["protocol"]["cross_engine_contrast_budget_multiplier"],
        )
    failed = sum(v["failed_comparisons"] for v in comparisons.values())
    return {
        "status": "pass" if failed == 0 else "fail",
        "failed_comparisons": failed,
        "comparisons": comparisons,
    }


def check(r, output, reference, native, cells):
    results = {}
    source_hashes = c.read(
        ctx.previous.prior.CAPTURE
        / "cells/active_channel/jax_jit/dt_5e-05/final-checkpoint/manifest.json"
    )["source_hashes"]
    for name, view in r["views"].items():
        directory = output / name
        a = native_check.native_checks(view, directory, native["by_history"][name])
        io.write_compressed(directory / "native-accounting.json.gz", a)
        b = cells_check.cells_checks(view, directory, cells["by_history"][name])
        io.write_compressed(directory / "cells-accounting.json.gz", b)
        dynamic = old.dynamic_checks(view, directory, reference[name], a, b)
        io.write(directory / "trajectory-comparison.json", dynamic)
        stored = checkpoints(view, directory, cells["by_history"][name], source_hashes)
        results[name] = {"native": a, "cells": b, "dynamic": dynamic, "stored": stored}
    paired = histories(r, output, reference, results)
    io.write(output / "history-contrasts.json", paired)
    passed = paired["status"] == "pass" and all(
        row[field]["status"] == "pass"
        for row in results.values()
        for field in ("native", "cells", "dynamic")
    )
    return {
        "status": "paired_capture_pass_pending_audit"
        if passed
        else "paired_capture_failed_not_qualified",
        "native_boundary_comparisons": sum(
            v["comparisons"]
            for row in results.values()
            for v in row["native"]["boundary_checks"].values()
        ),
        "native_boundary_failures": sum(
            row["native"]["failed_comparisons"] for row in results.values()
        ),
        "cells_accounting_failures": sum(
            row["cells"]["failed_comparisons"] for row in results.values()
        ),
        "required_trajectory_failures": sum(
            row["dynamic"]["required_failed_comparisons"] for row in results.values()
        ),
        "coarse_diagnostic_failures": sum(
            row["dynamic"]["coarse_diagnostic_failures"] for row in results.values()
        ),
        "failed_refinement_groups": sum(
            row["dynamic"]["failed_refinement_groups"] for row in results.values()
        ),
        "history_contrast_failures": paired["failed_comparisons"],
        "native_direct_charge_snapshots": sum(
            row["native"]["direct_charge_snapshots_checked"] for row in results.values()
        ),
        "observer_pairs": sum(row["native"]["observer_pairs"] for row in results.values()),
        "restart_pairs": sum(len(row["cells"]["restarts"]) for row in results.values()),
        "backend_pairs": sum(len(row["cells"]["backends"]) for row in results.values()),
        "checkpoints": sum(row["stored"]["checkpoints"] for row in results.values()),
        "checkpoint_arrays": sum(row["stored"]["checkpoint_arrays"] for row in results.values()),
        "reference_convergence_checked": True,
        "independent_audit_complete": False,
        "coupled_history_qualified": False,
        "biology_validated": False,
        "gpu_tested": False,
    }
