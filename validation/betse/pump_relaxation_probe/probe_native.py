"""Reuse the qualified native recorder and comparison for one longer-case probe."""

import copy
import gc
import sys
from pathlib import Path

import relax_context as ctx

c = ctx.c


def preparation(original, step):
    result = copy.deepcopy(original["native_preparation"])
    result["protocol"].update(dt_s=step, duration_s=0.01, steps=round(0.01 / step))
    return result


def capture(registration, output, write, budget):
    sys.path.insert(0, str(ctx.HERE.parent / "live_recording"))
    import betse
    import live_native as native
    import numpy as np
    from ruamel.yaml import YAML

    original = ctx.inherited()
    package = Path(betse.__file__).resolve().parent
    installed = {f"betse/{p.relative_to(package)}": c.sha(p) for p in package.rglob("*.py")}
    expected = {
        k: v
        for k, v in original["native_preparation"]["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.need(
        installed == expected and package.is_relative_to(native.ctx.NATIVE_PYTHON.parent.parent),
        "Pinned BETSE source",
    )
    runtime = native.prior.c.environment()
    c.need(runtime["packages"] == native.prior.c.locked_reference_packages(), "Native runtime")
    with (native.prior.c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = YAML(typ="safe").load(handle)
    records = []
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for index, row in enumerate(registration["scope"]["rows"]):
            budget(output)
            prepared = preparation(original, row["dt_s"])
            variant = next(v for v in prepared["protocol"]["variants"] if v["id"] == "pump_leak")
            directory = output / "native" / str(index)
            captured = native.run_row(prepared, variant, row["mode"], directory, package, template)
            c.need(captured["steps"] == round(0.01 / row["dt_s"]), "Native update count")
            records.append(
                dict(
                    **row,
                    directory=str(directory.relative_to(output)),
                    capture_sha256=c.sha(directory / "capture.json"),
                )
            )
            budget(output)
            print("Native probe captured: " + str(row), flush=True)
            gc.collect()
    c.need(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native worker imported Cells",
    )
    return dict(
        status="native_probe_captured",
        records=records,
        native_runs=4,
        installed_python_sha256=installed,
        environment=runtime,
        native_memory_bounded=False,
    )


def prefix(row, stream):
    """Only raw sample labels change with horizon; all physical prefix values must match."""
    match, steps, histories = c.exact.Exact(), 0, 0
    count = round(0.001 / row["dt_s"])
    for record in stream:
        kind = record["kind"]
        if kind == "native_header":
            c.need(
                record["row"]["dt_s"] == row["dt_s"]
                and record["row"]["steps"] == count
                and record["row"]["id"] == row["id"] == "pump_leak"
                and record["row"]["mode"] == "observed",
                "Physical prefix identity",
            )
            match.match(row["trace"]["initial"], record["trace"]["initial"], "Prefix initial")
        elif kind == "native_step":
            i = record["index"]
            c.need(i == steps < count, "Prefix update order")
            left, right = row["trace"]["steps"][i], record["step"]
            match.match(
                {k: v for k, v in left.items() if k != "raw_label_s"},
                {k: v for k, v in right.items() if k != "raw_label_s"},
                "Prefix step",
            )
            match.match(row["trace"]["raw_steps"][i], record["raw_step"], "Prefix raw calls")
            steps += 1
        elif kind == "native_history":
            c.need(record["index"] == histories, "Prefix history order")
            for name, value in record["values"].items():
                if name != "time":
                    match.match(
                        row["histories"][name]["values"][histories], value, "Prefix history/" + name
                    )
            histories += 1
        elif kind == "native_footer":
            match.match(
                row["trace"]["steps"][count - 1]["after_voltage"],
                record["row"]["final"],
                "Prefix endpoint",
            )
        else:
            raise ValueError("Unknown prefix record")
    c.need(steps == count and histories == count - 1 and stream.complete, "Incomplete prefix")
    return dict(steps=steps, exact_scalars=match.scalars, raw_sample_labels_excluded=True)


def assess(checker, ledger, picked, primary, accounting, plan):
    trajectory = plan["trajectory"]
    checker.state_checks(
        ledger,
        "finest_limits",
        picked,
        primary,
        trajectory["native_amount_fmol"],
        trajectory["native_energy_pJ"],
        trajectory["native_voltage_V"],
        trajectory["relative"],
    )
    ledger.compare(
        "energy_balance",
        accounting["energy_pJ"],
        0.0,
        plan["accounting"]["native_finest_energy_pJ"],
    )
    return ledger.failed_comparisons == 0


def compare(registration, output, write, budget):
    sys.path.insert(0, str(ctx.HERE.parent / "pump_pilot_refinement"))
    sys.path.insert(0, str(ctx.HERE.parent / "native_recording"))
    import native_review
    import native_row
    import refinement_check as checker

    native = c.read(output / "native.json", None)
    c.need(
        [{k: v[k] for k in ("dt_s", "mode")} for v in native["records"]]
        == registration["scope"]["rows"],
        "Captured row coverage",
    )
    original = ctx.inherited()
    reference_directory = c.child(c.ROOT, registration["reference_directory"])
    ref = c.read(reference_directory / "registration.json", None)
    prepared = dict(original, protocol=ref["protocol"], cases=ref["cases"])
    plan = prepared["protocol"]
    primary = checker.selected(
        c.read(reference_directory / "reference/pump_leak/dop853_tight/result.json", None),
        plan["common_times_s"],
    )
    variant = next(
        v for v in original["native_preparation"]["protocol"]["variants"] if v["id"] == "pump_leak"
    )
    old_rows = c.read(c.NATIVE / "native.json", None)["records"]
    results = []
    for link in native["records"][:3]:
        directory = c.child(output, link["directory"])
        c.need(c.sha(directory / "capture.json") == link["capture_sha256"], "Capture link")
        # Deliberately materialize one offline row at a time under the worker's
        # memory cap. This is not a bounded-memory or production execution claim.
        row = native_row.restore(c.wire.Stream(directory / "stream"))
        step = link["dt_s"]
        checker.row_identity(row, "pump_leak", "observed", step, 0.01)
        label = "pump_leak/dt_" + format(step, ".8g") + "/observed"
        old_stream = c.child(c.NATIVE, old_rows[label]["directory"]) / "stream"
        physical_prefix = prefix(row, c.wire.Stream(old_stream))
        ledger = checker.Ledger()
        ledger.scope = label
        points, balances = checker.native_points(prepared, row, variant, ledger)
        picked = checker.selected(points, plan["common_times_s"])
        error = checker.differences(picked, primary)
        within_limits = assess(checker, ledger, picked, primary, balances, plan)
        result = dict(
            dt_s=step,
            reference_errors=error,
            accounting=balances,
            within_finest_limits=within_limits,
            comparisons=ledger.comparisons,
            failed_comparisons=ledger.failed_comparisons,
            failed_groups=ledger.failed_groups,
            failure_examples=ledger.examples,
            physical_prefix=physical_prefix,
        )
        write(directory / "comparison.json", dict(**result, common_points=picked))
        results.append(result)
        del row, points
        gc.collect()
        budget(output)
        print("Native probe compared: " + str(step), flush=True)
    finest, quiet = native["records"][2:]
    pair = native_review.pair(
        c.child(output, finest["directory"]) / "stream",
        c.child(output, quiet["directory"]) / "stream",
    )
    refinements = {
        name: checker.refinement(
            [v["reference_errors"][name] for v in results],
            plan["refinement"][floor],
            plan["refinement"]["contraction_max"],
        )
        for name, floor in (
            ("amount", "floor_amount_fmol"),
            ("energy", "floor_energy_pJ"),
            ("voltage", "floor_voltage_V"),
        )
    }
    adequate = results[-1]["within_finest_limits"] and all(
        v["passed"] for v in refinements.values()
    )
    return dict(
        status="native_probe_completed",
        rows=results,
        observer_pair=pair,
        refinement=refinements,
        main_case_ladder_adequate=adequate,
        six_control_ladder_qualified=False,
        matched_10ms_qualified=False,
        physics_changed=False,
        scientific_tolerances_changed=False,
        biology_validated=False,
        automatic_followup=False,
    )
