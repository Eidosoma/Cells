"""Six-control 10 ms comparison using the qualified native and public Cells paths."""

import copy
import gc
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import matched_job as job
import refined_recording as recording
import refined_work

c, ctx = job.c, job.ctx
sys.path.insert(0, str(job.HERE.parent / "pump_pilot_refinement"))
import refinement_check as checker  # noqa: E402


def prepared():
    original = ctx.inherited()
    reference = c.read(job.old.old.REFERENCE / "registration.json", None)
    result = copy.deepcopy(original)
    result["cases"] = reference["cases"]
    result["protocol"] = copy.deepcopy(reference["protocol"])
    result["protocol"].update(
        schema="cells.pump_relaxation_matched_protocol@1",
        scope="Six-control 10 ms numerical comparison; no biological or steady-state claim",
        native_steps_s=job.STEPS,
        native_runs=24,
        observer_pairs=6,
    )
    return result


def cells_adapter(plan):
    """Private dependency: change the observation grid, not any production function."""
    path = job.HERE.parent / "pump_matched_pilot/pilot_cells.py"
    spec = importlib.util.spec_from_file_location("_matched_relaxation_cells", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.ctx

    def definition(case, step, *, jit=True):
        return original.definition(case, step, jit=jit, times=plan["common_times_s"])

    module.ctx = SimpleNamespace(**(vars(original) | {"definition": definition}))
    return module


def refinement(rows, plan):
    return {
        name: checker.refinement(
            [r["reference_errors"][name] for r in rows],
            plan["refinement"][floor],
            plan["refinement"]["contraction_max"],
        )
        for name, floor in (
            ("amount", "floor_amount_fmol"),
            ("energy", "floor_energy_pJ"),
            ("voltage", "floor_voltage_V"),
        )
    }


def primary(identifier, plan):
    directory = job.old.old.REFERENCE / "reference" / identifier / plan["reference"]["primary"]
    return checker.selected(c.read(directory / "result.json", None), plan["common_times_s"])


def ledger_result(ledger):
    return dict(
        comparisons=ledger.comparisons,
        failed_comparisons=ledger.failed_comparisons,
        failed_groups=ledger.failed_groups,
        failure_examples=ledger.examples,
        maxima=ledger.maxima,
    )


def cells_checks(packet, preparation):
    plan, rows = preparation["protocol"], packet["records"]
    steps, eager_step = plan["cells_steps_s"], plan["cells_eager_step_s"]
    key = checker.ctx.base.key
    expected = {
        key(v, h) + "/" + mode
        for v in job.VARIANTS
        for mode, h in [("jax_jit", h) for h in steps] + [("jax_eager", eager_step)]
    }
    c.need(set(rows) == expected, "Cells record coverage")
    c.need(
        set(packet["resumes"])
        == {key(v, plan["restart_step_s"]) + "/jax_jit" for v in job.VARIANTS}
        and all(
            r["full_state_bitwise_equal"] is True
            and r["start_step"] == round(plan["restart_time_s"] / plan["restart_step_s"])
            for r in packet["resumes"].values()
        ),
        "Cells restart coverage",
    )
    ledger, refinements, errors = checker.Ledger(), {}, {}
    limits = plan["trajectory"]
    for identifier in job.VARIANTS:
        target, ladder = primary(identifier, plan), []
        for mode, step in [("jax_jit", h) for h in steps] + [("jax_eager", eager_step)]:
            label = key(identifier, step) + "/" + mode
            row = rows[label]
            c.need(
                row["case"] == identifier
                and row["step_s"] == step
                and row["jit"] is (mode == "jax_jit")
                and row["times_s"] == plan["common_times_s"],
                "Cells identity/grid",
            )
            ledger.scope = label
            ledger.compare(
                "reference_state",
                row["states"],
                target["states"],
                limits["cells_state_atol"],
                limits["cells_state_rtol"],
            )
            ledger.compare(
                "reference_voltage",
                row["voltage_V"],
                target["voltage_V"],
                limits["cells_voltage_V"],
            )
            errors[label] = checker.differences(row, target)
            if mode == "jax_jit":
                ladder.append(dict(reference_errors=errors[label]))
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
                    plan["accounting"][budget],
                )
        refinements[identifier] = refinement(ladder, plan)
        eager, jit = (rows[key(identifier, eager_step) + "/" + n] for n in ("jax_eager", "jax_jit"))
        ledger.scope = "backends/" + identifier
        ledger.compare("state", eager["states"], jit["states"], 2e-12, 2e-11)
        ledger.compare("voltage", eager["voltage_V"], jit["voltage_V"], 2e-10, 2e-11)
    return dict(
        **ledger_result(ledger),
        reference_errors=errors,
        refinement=refinements,
        passed=ledger.failed_comparisons == 0
        and all(v["passed"] for fields in refinements.values() for v in fields.values()),
    )


def cells(r, output, write, budget):
    preparation = prepared()
    result = cells_adapter(preparation["protocol"]).worker(preparation, output)
    result["checks"] = cells_checks(result, preparation)
    result["status"] = "matched_cells_completed"
    # The reused writer's provenance label is historical. Bind this campaign's
    # actual horizon, preparation and registration explicitly in the phase receipt.
    result["registration_sha256"] = c.sha(output / "registration.json")
    result["duration_s"] = preparation["protocol"]["duration_s"]
    budget(output)
    return result


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
            preparation = refined_work.preparation(original, row)
            variant = next(v for v in preparation["protocol"]["variants"] if v["id"] == row["id"])
            directory = c.child(output, "native/" + row["role"])
            captured = native.run_row(
                preparation, variant, row["mode"], directory, package, template
            )
            c.need(
                captured["steps"] == round(row["duration_s"] / row["dt_s"])
                and captured["id"] == row["id"]
                and captured["mode"] == row["mode"]
                and captured["stream"]["max_output_bytes"] == recording.STREAM_BYTES,
                "Matched capture identity/clock/recorder",
            )
            records.append(
                dict(
                    **row,
                    directory=str(directory.relative_to(output)),
                    capture_sha256=c.sha(directory / "capture.json"),
                )
            )
            budget(output)
            print("Matched native captured: " + row["role"], flush=True)
            gc.collect()
    c.need(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native imported Cells",
    )
    return dict(
        status="matched_native_captured",
        records=records,
        native_runs=len(records),
        installed_python_sha256=installed,
        environment=runtime,
        native_memory_bounded=False,
    )


def compare_row(directory, link, preparation, variant, write):
    sys.path.insert(0, str(ctx.HERE.parent / "native_recording"))
    import native_row

    c.need(c.sha(directory / "capture.json") == link["capture_sha256"], "Capture link")
    row = native_row.restore(recording.stream(directory / "stream"))
    checker.row_identity(row, variant["id"], "observed", link["dt_s"], 0.01)
    ledger = checker.Ledger()
    ledger.scope = link["role"]
    points, balances = checker.native_points(preparation, row, variant, ledger)
    plan = preparation["protocol"]
    picked = checker.selected(points, plan["common_times_s"])
    target = primary(variant["id"], plan)
    within = refined_work.prior.assess(checker, ledger, picked, target, balances, plan)
    result = dict(
        dt_s=link["dt_s"],
        reference_errors=checker.differences(picked, target),
        accounting=balances,
        within_finest_limits=within,
        **ledger_result(ledger),
        common_points=picked,
    )
    write(directory / "comparison.json", result)
    return result


def required_native_pass(row, finest):
    c.need(
        sum(row["failed_groups"].values()) == row["failed_comparisons"],
        "Native failure summary extent",
    )
    if finest:
        return row["within_finest_limits"] and row["failed_comparisons"] == 0
    # Coarse trajectory/energy misses remain diagnostics. Live rate/transfer
    # mapping failures are NEVER excused by their place in the step ladder.
    optional = (
        "/energy_balance",
        "/finest_limits_amount",
        "/finest_limits_energy",
        "/finest_limits_voltage",
    )
    return not any(
        count for group, count in row["failed_groups"].items() if not group.endswith(optional)
    )


def cross_check(native, cells_row, plan):
    ledger = checker.Ledger()
    limits, factor = plan["trajectory"], plan["trajectory"]["cross_engine_budget_multiplier"]
    checker.state_checks(
        ledger,
        "cross_engine",
        native,
        cells_row,
        factor * limits["native_amount_fmol"],
        factor * limits["native_energy_pJ"],
        factor * limits["native_voltage_V"],
        limits["relative"],
    )
    return ledger_result(ledger)


def compare(r, output, write, budget):
    preparation = prepared()
    plan = preparation["protocol"]
    native = c.read(output / "native.json", None)
    job.gate("native", native)
    links = {v["role"]: v for v in native["records"]}
    packet = c.read(output / "cells.json", None)
    job.gate("cells", packet)
    cells_checked = cells_checks(packet, preparation)
    results = {}
    for variant in preparation["native_preparation"]["protocol"]["variants"]:
        identifier = variant["id"]
        if identifier == "pump_leak":
            rows = [c.read(path, None) for path in job.reused_rows()]
            pair = c.read(job.PRIOR / "comparison.json", None)["observer_pair"]
        else:
            rows = []
            for index in range(3):
                role = identifier + "/" + str(index)
                link = links[role]
                rows.append(
                    compare_row(
                        c.child(output, link["directory"]), link, preparation, variant, write
                    )
                )
                gc.collect()
                budget(output)
                print("Matched native compared: " + role, flush=True)
            observed, quiet = (links[identifier + "/" + n] for n in ("2", "quiet"))
            c.need(
                c.sha(c.child(output, quiet["directory"]) / "capture.json")
                == quiet["capture_sha256"],
                "Quiet capture link",
            )
            pair = recording.pair(
                c.child(output, observed["directory"]) / "stream",
                c.child(output, quiet["directory"]) / "stream",
            )
        c.need([v["dt_s"] for v in rows] == job.STEPS, "Native ladder order")
        refinements = refinement(rows, plan)
        cells_key = checker.ctx.base.key(identifier, plan["cells_steps_s"][-1]) + "/jax_jit"
        cross = cross_check(rows[-1]["common_points"], packet["records"][cells_key], plan)
        accepted = (
            all(required_native_pass(row, i == 2) for i, row in enumerate(rows))
            and all(v["passed"] for v in refinements.values())
            and cross["failed_comparisons"] == pair["failed_comparisons"] == 0
        )
        result = dict(
            rows=[{k: v for k, v in row.items() if k != "common_points"} for row in rows],
            refinement=refinements,
            observer_pair=pair,
            cross_engine=cross,
            passed=accepted,
            reused=identifier == "pump_leak",
        )
        directory = output / "comparisons" / identifier
        directory.mkdir(parents=True)
        write(directory / "result.json", result)
        results[identifier] = result
        print("Matched case completed: " + identifier + " passed=" + str(accepted), flush=True)
    passed = cells_checked["passed"] and all(v["passed"] for v in results.values())
    c.need(set(results) == set(job.VARIANTS), "Comparison case coverage")
    c.need(
        not any(n in ("cells", "betse") or n.startswith(("cells.", "betse.")) for n in sys.modules),
        "Comparator imported a simulator",
    )
    return dict(
        status="matched_comparison_completed",
        producer_passed=passed,
        cases=results,
        cells_checks=cells_checked,
        native_runs=20,
        reused_native_observed_rows=3,
        finest_observer_pairs=6,
        cells_trajectories=24,
        restart_suffixes=6,
        new_reference_solves=0,
        independent_review_pending=True,
        matched_10ms_qualified=False,
        production_changed=False,
        physics_changed=False,
        scientific_tolerances_changed=False,
        biology_validated=False,
        gpu_tested=False,
        automatic_followup=False,
    )
