"""Test a pre-existing pump-only step range; retain the failed tighter range."""

import gc
import importlib
import sys

import range_job as job

c = job.c
matched = importlib.import_module("matched_work")
# The qualified capture accepts explicit case/step/mode rows. No new native
# stepping, recorder, observer, transport or preparation implementation is needed.
capture = matched.capture


def conclude(rows, pair, previous, cells_row, plan):
    c.need([v["dt_s"] for v in rows] == job.STEPS, "Prospective range coverage")
    refinement = matched.refinement(rows, plan)
    cross = matched.cross_check(rows[-1]["common_points"], cells_row, plan)
    pump_passed = (
        all(matched.required_native_pass(row, i == 2) for i, row in enumerate(rows))
        and all(v["passed"] for v in refinement.values())
        and cross["failed_comparisons"] == pair["failed_comparisons"] == 0
    )
    c.need(set(previous["cases"]) == set(job.prior.VARIANTS), "Previous case coverage")
    c.need(
        previous["producer_passed"] is False and previous["cases"]["pump_only"]["passed"] is False,
        "The common tighter range remains failed",
    )
    c.need(previous["cells_checks"]["passed"] is True, "Reused Cells checks")
    cases = {
        name: dict(passed=row["passed"], reused=True, native_steps_s=job.prior.STEPS)
        for name, row in previous["cases"].items()
        if name != "pump_only"
    }
    c.need(
        all(row["passed"] is True for row in cases.values()), "Other controls need separate work"
    )
    cases["pump_only"] = dict(
        passed=pump_passed,
        reused=False,
        native_steps_s=job.STEPS,
        rows=[{k: v for k, v in row.items() if k != "common_points"} for row in rows],
        refinement=refinement,
        observer_pair=pair,
        cross_engine=cross,
    )
    return dict(
        status="case_specific_range_completed",
        producer_passed=pump_passed,
        cases=cases,
        reused_cells_checks=previous["cells_checks"],
        acceptance_basis=(
            "Separate pump-only range chosen from the pre-existing 1 ms ladder "
            "after arithmetic diagnosis"
        ),
        native_runs=3,
        new_native_observed_rows=2,
        reused_native_observed_rows=16,
        cells_runs=0,
        reused_cells_trajectories=24,
        reused_restart_suffixes=6,
        new_reference_solves=0,
        reused_reference_solves=18,
        finest_observer_pairs=6,
        original_common_range_passed=False,
        original_verdict_changed=False,
        original_pump_only_amount_refinement=previous["cases"]["pump_only"]["refinement"]["amount"],
        physics_changed=False,
        production_changed=False,
        scientific_tolerances_changed=False,
        independent_review_pending=True,
        matched_10ms_qualified=False,
        biology_validated=False,
        gpu_tested=False,
        automatic_followup=False,
    )


def compare(r, output, write, budget):
    native = c.read(output / "native.json", None)
    job.gate("native", native)
    links = {v["role"]: v for v in native["records"]}
    preparation = matched.prepared()
    plan = preparation["protocol"]
    variant = next(
        v
        for v in preparation["native_preparation"]["protocol"]["variants"]
        if v["id"] == "pump_only"
    )
    rows = []
    for role in ("pump_only/coarse", "pump_only/medium"):
        link = links[role]
        rows.append(
            matched.compare_row(
                c.child(output, link["directory"]), link, preparation, variant, write
            )
        )
        gc.collect()
        budget(output)
        print("Pump-only range compared: " + role, flush=True)
    fine = c.read(job.CAPTURE / "native/pump_only/0/comparison.json", None)
    rows.append(fine)
    quiet = links["pump_only/fine_quiet"]
    directory = c.child(output, quiet["directory"])
    c.need(c.sha(directory / "capture.json") == quiet["capture_sha256"], "Quiet capture link")
    pair = matched.recording.pair(job.CAPTURE / "native/pump_only/0/stream", directory / "stream")
    c.need(pair["records"] == round(0.01 / job.STEPS[-1]) + 1, "Observer pair step coverage")
    cells = c.read(job.CAPTURE / "cells.json", None)
    key = matched.checker.ctx.base.key("pump_only", plan["cells_steps_s"][-1]) + "/jax_jit"
    c.need(cells["records"][key]["times_s"] == plan["common_times_s"], "Reused Cells grid")
    result = conclude(
        rows, pair, c.read(job.CAPTURE / "comparison.json", None), cells["records"][key], plan
    )
    c.need(
        not any(n in ("cells", "betse") or n.startswith(("cells.", "betse.")) for n in sys.modules),
        "Comparator imported a simulator",
    )
    return result
