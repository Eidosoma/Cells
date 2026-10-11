"""Smaller native timesteps, preserving all physical and numerical acceptance laws."""

import gc
import sys
from pathlib import Path

import probe_native as prior
import refined_recording as recording

c, ctx = prior.c, prior.ctx


def preparation(original, row):
    prepared = prior.preparation(original, row["dt_s"])
    prepared["protocol"].update(
        duration_s=row["duration_s"], steps=round(row["duration_s"] / row["dt_s"])
    )
    return prepared


def capture(r, output, write, budget):
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
        "Pinned native source",
    )
    runtime = native.prior.c.environment()
    c.need(runtime["packages"] == native.prior.c.locked_reference_packages(), "Native runtime")
    with (native.prior.c.SOURCE / "betse/data/yaml/sim_config.yaml").open() as handle:
        template = YAML(typ="safe").load(handle)
    records = []
    with np.errstate(over="raise", invalid="raise", divide="raise"), recording.writer_limit(native):
        for row in r["scope"]["rows"]:
            budget(output)
            prepared = preparation(original, row)
            variant = next(v for v in prepared["protocol"]["variants"] if v["id"] == "pump_leak")
            directory = c.child(output, "native/" + row["role"])
            captured = native.run_row(prepared, variant, row["mode"], directory, package, template)
            c.need(
                captured["steps"] == prepared["protocol"]["steps"]
                and captured["stream"]["max_output_bytes"] == recording.STREAM_BYTES,
                "Refined capture clock/recorder",
            )
            records.append(
                dict(
                    **row,
                    directory=str(directory.relative_to(output)),
                    capture_sha256=c.sha(directory / "capture.json"),
                )
            )
            budget(output)
            print("Refined native captured: " + row["role"], flush=True)
            gc.collect()
    c.need(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native imported Cells",
    )
    return dict(
        status="refined_native_captured",
        records=records,
        native_runs=4,
        installed_python_sha256=installed,
        environment=runtime,
        native_memory_bounded=False,
    )


def conclusion(results, plan, checker):
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
        refinement=refinements,
        main_case_ladder_adequate=adequate,
        six_control_ladder_qualified=False,
        matched_10ms_qualified=False,
    )


def compare(r, output, write, budget):
    sys.path.insert(0, str(ctx.HERE.parent / "native_recording"))
    sys.path.insert(0, str(ctx.HERE.parent / "pump_pilot_refinement"))
    import native_row
    import refinement_check as checker

    native = c.read(output / "native.json", None)
    c.need(
        [{k: v[k] for k in ("role", "dt_s", "duration_s", "mode")} for v in native["records"]]
        == r["scope"]["rows"],
        "Refined row coverage",
    )
    links = {v["role"]: v for v in native["records"]}
    for link in links.values():
        c.need(
            c.sha(c.child(output, link["directory"]) / "capture.json") == link["capture_sha256"],
            "Capture link",
        )
    old = c.child(c.ROOT, r["prior"]["directory"])
    coarse = c.read(old / "native/2/comparison.json", None)
    results = [{k: v for k, v in coarse.items() if k != "common_points"}]
    reference = c.child(c.ROOT, r["reference_directory"])
    ref = c.read(reference / "registration.json", None)
    original = ctx.inherited()
    prepared = dict(original, cases=ref["cases"], protocol=ref["protocol"])
    plan = ref["protocol"]
    primary = checker.selected(
        c.read(reference / "reference/pump_leak/dop853_tight/result.json", None),
        plan["common_times_s"],
    )
    variant = next(
        v for v in original["native_preparation"]["protocol"]["variants"] if v["id"] == "pump_leak"
    )
    prefix = None
    for role in ("medium", "fine"):
        link = links[role]
        directory = c.child(output, link["directory"])
        row = native_row.restore(recording.stream(directory / "stream"))
        checker.row_identity(row, "pump_leak", "observed", link["dt_s"], 0.01)
        ledger = checker.Ledger()
        ledger.scope = role
        points, balances = checker.native_points(prepared, row, variant, ledger)
        picked = checker.selected(points, plan["common_times_s"])
        adequate = prior.assess(checker, ledger, picked, primary, balances, plan)
        if role == "fine":
            prefix = prior.prefix(row, recording.stream(output / "native/fine_1ms/stream"))
        result = dict(
            dt_s=link["dt_s"],
            reference_errors=checker.differences(picked, primary),
            accounting=balances,
            within_finest_limits=adequate,
            comparisons=ledger.comparisons,
            failed_comparisons=ledger.failed_comparisons,
            failed_groups=ledger.failed_groups,
            failure_examples=ledger.examples,
        )
        write(directory / "comparison.json", dict(**result, common_points=picked))
        results.append(result)
        del row, points
        gc.collect()
        budget(output)
        print("Refined native compared: " + role, flush=True)
    pair = recording.pair(output / "native/fine/stream", output / "native/fine_quiet/stream")
    return dict(
        status="refined_probe_completed",
        rows=results,
        fine_physical_prefix=prefix,
        observer_pair=pair,
        **conclusion(results, plan, checker),
        reused_native_comparisons=1,
        native_runs=4,
        cells_runs=0,
        new_reference_solves=0,
        physics_changed=False,
        scientific_tolerances_changed=False,
        biology_validated=False,
        automatic_followup=False,
    )
