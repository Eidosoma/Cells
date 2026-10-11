"""Independent native/Cells numerical verdict from sealed saved values only."""

import gc
import sys
import time

import review_context as ctx

sys.path.insert(0, str(ctx.HERE.parent / "pump_coupled_audit"))
import coupled_audit as physics  # noqa: E402
import native_energy  # noqa: E402
import native_read  # noqa: E402
import native_records  # noqa: E402

c, e, d = ctx.c, ctx.e, ctx.original.diagnostic


def primary(name, plan):
    source = (
        ctx.path("reference") / "reference" / name / plan["reference"]["primary"] / "result.json"
    )
    return d.sample(c.read(source, None), plan["common_times_s"])


def state_checks(points, reference, plan, *, cells=False, cross=False):
    limits = plan["trajectory"]
    if cells:
        result = d.state_checks(
            points,
            reference,
            (
                limits["cells_state_atol"],
                limits["cells_state_atol"],
                limits["cells_voltage_V"],
                limits["cells_state_rtol"],
            ),
        )
        result["voltage"] = d.discrepancy(
            points["voltage_V"], reference["voltage_V"], limits["cells_voltage_V"]
        )
        return result
    factor = limits["cross_engine_budget_multiplier"] if cross else 1
    return d.state_checks(
        points,
        reference,
        (
            factor * limits["native_amount_fmol"],
            factor * limits["native_energy_pJ"],
            factor * limits["native_voltage_V"],
            limits["relative"],
        ),
    )


def native_row(link, preparation, baseline):
    began = time.monotonic()
    reference, old = preparation
    plan, name, step = reference["protocol"], link["case"], link["dt_s"]
    directory = c.child(ctx.ROOT, link["directory"])
    capture = c.read(directory / "capture.json", None)
    c.need(
        capture["id"] == name
        and capture["mode"] == "observed"
        and capture["steps"] == capture["observed_updates"] == round(0.01 / step)
        and capture["history_samples"] == capture["steps"] - 1,
        "Native capture extent",
    )
    c.exact.Exact().match(
        capture["stream"], c.read(directory / "stream/manifest.json", None), "Native capture stream"
    )
    row, format_check = native_read.read(directory / "stream")
    variant = next(v for v in old["native_preparation"]["protocol"]["variants"] if v["id"] == name)
    native_records.identity(row, baseline[name + "/observed"], step, 0.01, "observed")
    ledger = e.Ledger()
    physical = native_records.inspect(row, baseline[name + "/observed"], plan, variant, ledger)
    points = native_energy.reconstruct(row, variant, plan["common_times_s"], ledger)
    saved = c.read(directory / "comparison.json", None)
    c.need(saved["dt_s"] == step, "Producer row timestep")
    for field in ("states", "voltage_V"):
        ledger.compare(
            "producer_common_" + field, saved["common_points"][field], points[field], 2e-12, 0.0
        )
    c.need(
        len(points["times_s"]) == 41
        and all(
            abs(a - b) < 1e-15
            for a, b in zip(points["times_s"], plan["common_times_s"], strict=True)
        ),
        "Native observation grid",
    )
    checks = state_checks(points, primary(name, plan), plan)
    for field in checks:
        ledger.compare(
            "producer_reference_error_" + field,
            saved["reference_errors"][field],
            checks[field]["max_error"],
            2e-12,
            0.0,
        )
    ledger.compare(
        "producer_energy_defect",
        saved["accounting"]["energy_pJ"],
        points["energy"]["max_defect_pJ"],
        2e-12,
        0.0,
    )
    energy = d.discrepancy(
        points["energy"]["max_defect_pJ"], 0.0, plan["accounting"]["native_finest_energy_pJ"]
    )
    del row
    gc.collect()
    observer = None
    if link["quiet"]:
        observer = native_read.pair(
            directory / "stream", c.child(ctx.ROOT, link["quiet"]) / "stream"
        )
        c.need(observer["records"] == round(0.01 / step) + 1, "Finest observer extent")
    return dict(
        case=name,
        index=link["index"],
        dt_s=step,
        physical=physical,
        format_check=format_check,
        points=points,
        reference_checks=checks,
        finest_energy_check=energy,
        observer_pair=observer,
        independent_comparisons=ledger.count,
        independent_maxima=ledger.maxima,
        elapsed_seconds=time.monotonic() - began,
    )


def cells(preparation):
    reference, old = preparation
    plan = reference["protocol"]
    r = c.read(ctx.path("matched") / "registration.json", None)
    sources = {
        n.removeprefix("src/cells/"): h
        for n, h in r["sources_sha256"].items()
        if n.startswith("src/cells/")
    }
    packet = c.read(ctx.path("matched") / "cells.json", None)
    c.need(
        packet["duration_s"] == 0.01 and packet["registration_sha256"] == ctx.PACKETS["matched"][1],
        "Cells campaign binding",
    )
    records = ctx.cells_reader().cells_records(packet, sources)
    expected = {
        d_key(name, h, mode)
        for name in ctx.VARIANTS
        for mode, h in [("jax_jit", h) for h in plan["cells_steps_s"]]
        + [("jax_eager", plan["cells_eager_step_s"])]
    }
    c.need(
        set(records) == expected
        and set(packet["resumes"]) == {d_key(n, plan["restart_step_s"]) for n in ctx.VARIANTS},
        "Cells row/restart membership",
    )
    ledger, results = e.Ledger(), {}
    constants = old["native_preparation"]["protocol"]["constants"]
    for key, row in records.items():
        case = reference["cases"][row["case"]]
        c.need(
            key == d_key(row["case"], row["step_s"], "jax_jit" if row["jit"] else "jax_eager")
            and row["times_s"] == plan["common_times_s"],
            "Cells identity/clock",
        )
        e.shape(row["states"], [41, 59])
        e.shape(row["voltage_V"], [41, 7])
        for index, state in enumerate(row["states"]):
            accounting = physics.physical(case, state, constants)
            c.need(min(state[52:]) >= -1e-14, "Negative Cells dissipation")
            ledger.compare(
                "charge_voltage",
                row["voltage_V"][index],
                accounting["voltage_V"],
                plan["mapping"]["voltage_V"],
                0.0,
            )
            for field, limit in (
                ("material_residual_fmol", "cells_material_fmol"),
                ("charge_residual_C", "cells_charge_C"),
                ("energy_residual_pJ", "cells_energy_pJ"),
            ):
                ledger.compare(field, accounting[field], 0.0, plan["accounting"][limit], 0.0)
        for names, limit in (
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
                "saved_diagnostics/" + limit,
                [row["diagnostics"][n] for n in names],
                [0.0] * len(names),
                plan["accounting"][limit],
                0.0,
            )
        results[key] = state_checks(row, primary(row["case"], plan), plan, cells=True)
    for name in ctx.VARIANTS:
        eager = records[d_key(name, plan["cells_eager_step_s"], "jax_eager")]
        jit = records[d_key(name, plan["cells_eager_step_s"])]
        ledger.compare("backends/state", eager["states"], jit["states"], 2e-12, 2e-11)
        ledger.compare("backends/voltage", eager["voltage_V"], jit["voltage_V"], 2e-10, 2e-11)
        resume = packet["resumes"][d_key(name, plan["restart_step_s"])]
        c.need(
            resume["start_step"] == round(plan["restart_time_s"] / plan["restart_step_s"]),
            "5 ms restart position",
        )
    return dict(
        rows=results,
        decoded_trajectories=24,
        restart_suffixes=6,
        checkpoint_links=6,
        independent_accounting_states=984,
        independent_comparisons=ledger.count,
        independent_maxima=ledger.maxima,
    ), records


def d_key(name, step, mode="jax_jit"):
    return name + "/dt_" + format(step, ".8g") + "/" + mode


def conclude(native, cells_result, records, preparation, producer, original):
    plan = preparation[0]["protocol"]
    c.need(
        set(native) == {v["case"] + "/" + str(v["index"]) for v in ctx.rows()},
        "Native review membership",
    )
    constraints, refinements = {}, {}
    for name in ctx.VARIANTS:
        rows = [native[name + "/" + str(i)] for i in range(3)]
        c.need([r["dt_s"] for r in rows] == ctx.RANGES[name], "Reviewed step ranges")
        constraints.update(
            {name + "/native/" + k: v for k, v in rows[-1]["reference_checks"].items()}
        )
        constraints[name + "/native/energy_closure"] = rows[-1]["finest_energy_check"]
        cell_rows = [cells_result["rows"][d_key(name, h)] for h in plan["cells_steps_s"]]
        for engine, values in (
            ("native", [r["reference_checks"] for r in rows]),
            ("cells", cell_rows),
        ):
            for field, unit in (("amount", "fmol"), ("energy", "pJ"), ("voltage", "V")):
                key = name + "/" + engine + "/" + field
                refinements[key] = d.refinement(
                    [v[field]["max_error"] for v in values],
                    plan["refinement"][f"floor_{field}_{unit}"],
                    plan["refinement"]["contraction_max"],
                )
                reported = (
                    (
                        producer["cases"][name]["refinement"]
                        if name == "pump_only"
                        else original["cases"][name]["refinement"]
                    )
                    if engine == "native"
                    else (original["cells_checks"]["refinement"][name])
                )
                c.need(
                    refinements[key]["passed"] == reported[field]["passed"],
                    "Independent/producer refinement verdict",
                )
        cross = state_checks(
            rows[-1]["points"], records[d_key(name, plan["cells_steps_s"][-1])], plan, cross=True
        )
        constraints.update({name + "/cross/" + k: v for k, v in cross.items()})
        c.need(
            rows[-1]["observer_pair"]["failed_comparisons"] == 0
            and rows[-1]["observer_pair"]["records"] == round(0.01 / ctx.RANGES[name][-1]) + 1,
            "Observer review coverage",
        )
    for name, checks in cells_result["rows"].items():
        constraints.update({name + "/reference/" + k: v for k, v in checks.items()})
    c.need(
        original["producer_passed"] is False and producer["original_common_range_passed"] is False,
        "Original failure preservation",
    )
    failed = sum(len(v["failures"]) for v in constraints.values())
    passed = failed == 0 and all(v["passed"] for v in refinements.values())
    c.need(sum(r["physical"]["steps"] for r in native.values()) == 235200, "Update coverage")
    return dict(
        status="case_specific_saved_review_pass" if passed else "saved_review_numerical_miss",
        passed=passed,
        failed_comparisons=failed,
        constraints=constraints,
        refinements=refinements,
        comparisons=sum(v["comparisons"] for v in constraints.values()),
        native_observed_steps=235200,
        native_rows=18,
        finest_observer_pairs=6,
        native_physical_records=sum(r["physical"]["physical_records"] for r in native.values()),
        native_independent_comparisons=sum(r["independent_comparisons"] for r in native.values()),
        cells=cells_result,
        original_common_range_passed=False,
        original_verdict_changed=False,
        matched_10ms_qualified=passed,
        qualification_scope="case-specific native timesteps",
        reference_review_reused=True,
        native_memory_bounded=False,
        cells_every_accepted_state_accounting_independently_recomputed=False,
        biology_validated=False,
        gpu_tested=False,
        steady_state_qualified=False,
        full_betse_parity=False,
        physics_rerun=False,
        production_changed=False,
        scientific_tolerances_changed=False,
        automatic_followup=False,
    )


def run(output, write, budget):
    preparation = ctx.preparation()
    baseline = c.read(e.CAPTURE / "betse.json", None)["rows"]
    native = {}
    for link in ctx.rows():
        label = link["case"] + "/" + str(link["index"])
        native[label] = native_row(link, preparation, baseline)
        directory = output / "native" / link["case"]
        directory.mkdir(parents=True, exist_ok=True)
        write(directory / (str(link["index"]) + ".json"), native[label])
        budget(output)
        print("Independently reviewed native: " + label, flush=True)
        gc.collect()
    cells_result, records = cells(preparation)
    write(output / "cells.json", cells_result)
    result = conclude(
        native,
        cells_result,
        records,
        preparation,
        c.read(ctx.path("range") / "comparison.json", None),
        c.read(ctx.path("matched") / "comparison.json", None),
    )
    write(output / "review.json", result)
    budget(output)
    return result
