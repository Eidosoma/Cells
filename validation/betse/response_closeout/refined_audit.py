"""Offline replay and independent surface audit; never import or execute either simulator."""

import argparse
import importlib
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import refined_audit_context as ctx
import refined_audit_surfaces as independent

c = ctx.c
replay = importlib.import_module("trace_resume_check")
probe = importlib.import_module("trace_resume_probe")
fence = replay.old.fence
SCOPE = {
    "geometry": "seven_cell_finite_well_mixed_bath",
    "duration_s": 0.001,
    "constant_profile": "matched_constants",
    "finest_input_hold_s": 0.00000625,
    "conditions": ["baseline", "zero_amplitude", "static_blocked", "suppression_recovery"],
    "Cells_backends": ["jax_eager", "jax_jit"],
    "Cells_subdivisions": [1, 2, 4],
    "internal_solver_backend_holds_s": [0.000025, 0.0000125, 0.00000625],
    "native_vs_Cells": "fixed_finest_held_input_only",
    "across_hold_differences": "diagnostic_not_native_or_forcing_convergence",
}
FALSE_FLAGS = (
    "trajectory_qualified",
    "native_convergence_qualified",
    "forcing_convergence_qualified",
    "independent_audit_run",
    "biology_validated",
    "gpu_tested",
)


def inspect_metadata(r, output):
    closed = ctx.verify_manifest(output, r)
    p = r["continuation_plan"]
    ctx.prior.validate_plan(p)
    expected_counts = {
        "new_native_runs": 0,
        "reused_native_runs": 16,
        "new_cells_runs": 22,
        "reused_cells_runs": 26,
    }
    c.require(
        closed["schema"] == "cells.betse_trace_resume_capture@1"
        and closed["status"]
        == "finest_held_response_gates_pass_with_coarse_rejections_pending_audit"
        and closed["registration_sha256"] == ctx.ANCHORS["registration.json"]
        and closed["failed_capture_anchors"] == ctx.prior.ANCHORS
        and all(closed[k] == v for k, v in expected_counts.items())
        and all(closed[k] is False for k in FALSE_FLAGS)
        and closed["trajectory_run"] is True
        and closed["comparisons"] == 2494936
        and closed["failed_comparisons"] == 4173
        and closed["required_failed_comparisons"] == 0
        and closed["coarse_failed_comparisons"] == 150
        and 0 < closed["elapsed_seconds"] < p["total_timeout_seconds"],
        "Completed response verdict/scope differs",
    )
    launch, started = c.read(output / "launch.json"), c.read(output / "started.json")
    c.require(
        launch["status"] == "launched_detached"
        and launch["registration_sha256"] == ctx.ANCHORS["registration.json"]
        and type(launch["pid"]) is int
        and launch["pid"] == started["pid"] > 0
        and all(launch[k] == v for k, v in expected_counts.items())
        and launch["automatic_polling"] is launch["automatic_retry"] is False
        and launch["independent_audit"] == "await_user_instruction"
        and all(launch[k] == p[k] for k in ("stage_timeout_seconds", "total_timeout_seconds")),
        "Continuation launch identity/resources differ",
    )
    instant = independent.base.instant
    ordered = [
        instant(r["registered_utc"]),
        instant(launch["launched_utc"]),
        instant(started["started_utc"]),
    ]
    workers = {name: c.read(output / (name + ".json")) for name in ("cells", "comparison")}
    for name, worker in workers.items():
        c.require(
            worker["registration_sha256"] == ctx.ANCHORS["registration.json"]
            and worker["sources"] == r["sources"]
            and 0 < worker["elapsed_seconds"] < p["stage_timeout_seconds"][name],
            "Continuation worker identity/resources differ",
        )
    c.require(
        sum(v["elapsed_seconds"] for v in workers.values()) < closed["elapsed_seconds"],
        "Continuation worker/total timings differ",
    )
    cells, comparison = workers["cells"], workers["comparison"]
    c.require(
        cells["schema"] == "cells.betse_trace_resume_cells_worker@1"
        and cells["status"] == "exported_pending_comparison"
        and cells["new_cells_runs"] == 22
        and cells["reused_cells_runs"] == 26
        and cells["engine"] == "unchanged_cells_checked_rk4_runner"
        and cells["accepted_runtime"] == r["cells_runtime"]
        and cells["warnings"] == []
        and cells["device"] == "cpu"
        and cells["x64_enabled"] is True
        and cells["jit_disabled"] is False
        and cells["trajectory_run"] is True
        and cells["source_path"] == str(c.ROOT / "src/cells/models/finite_extracellular.py")
        and cells["source_sha256"] == c.sha(cells["source_path"])
        and cells["runtime_resource_probe_sha256"] == c.sha(output / "runtime-resource-probe.json")
        and cells["results"]
        == {row["id"]: "cells/" + row["id"] + "/result.json" for row in r["new_cells_rows"]},
        "Continuation Cells provenance differs",
    )
    probe.validate(c.read(output / "runtime-resource-probe.json"), r)
    c.require(
        not (ctx.prior.FAILED / "cells.json").exists(), "Invented old aggregate Cells receipt"
    )
    c.require(
        len(r["reused_cells"]) == 26 and r["new_cells_rows"] == r["cells_rows"][26:],
        "Wrong split-provenance coverage",
    )
    for index, row in enumerate(r["new_cells_rows"]):
        entry = c.read(output / f"cells-started/{index:02d}.json")
        c.require(entry["row"] == row, "Continuation started-row identity differs")
        ordered.append(instant(entry["started_utc"]))
    ordered.append(instant(closed["finished_utc"]))
    c.require(ordered == sorted(ordered), "Continuation chronology differs")
    c.require(
        all(comparison[k] is False for k in FALSE_FLAGS)
        and comparison["criteria_unchanged"] is True
        and comparison["coarse_rejection_replayed_exactly"] is True
        and comparison["resource_failure_preserved"] is True
        and comparison["terminal_native_rate_invented"] is False
        and comparison["terminal_Cells_rate_validated"] is True
        and comparison["comparisons"] == 2494936
        and comparison["failed_comparisons"] == 4173
        and comparison["required_gates"]["comparisons"] == 2298936
        and comparison["required_gates"]["failed_comparisons"] == 0
        and comparison["internal_laws"]["comparisons"] == 1373032
        and comparison["internal_laws"]["failed_comparisons"] == 0,
        "Saved numerical verdict/qualification differs",
    )
    native = c.read(ctx.prior.FAILED / "native.json")
    installed = {
        n: h
        for n, h in r["upstream"]["files_sha256"].items()
        if n.startswith("betse/") and n.endswith(".py")
    }
    c.require(
        len(installed) == 332
        and native["installed_python_sha256"] == installed
        and native["environment"]["executable"] == str(c.REFERENCE_PYTHON)
        and native["environment"]["packages"]["betse"] == "1.5.0"
        and Path(native["package_path"]).is_relative_to(c.REFERENCE_PYTHON.parent.parent)
        and all(c.sha(Path(native["package_path"]).parent / n) == h for n, h in installed.items()),
        "Retained native installed-source provenance differs",
    )
    retained = ctx.prior.old_job.budget.artifact_bytes(ctx.prior.FAILED)
    new = sum(
        pth.stat().st_size
        for pth in output.rglob("*")
        if pth.is_file() and pth.name != "capture.json"
    )
    c.require(
        retained + new == closed["combined_artifact_bytes_before_receipt"] < p["max_artifact_bytes"]
        and all(
            pth.stat().st_size < p["max_worker_file_bytes"]
            for pth in output.rglob("*")
            if pth.is_file()
        ),
        "Completed response artifact accounting differs",
    )
    return {
        "capture_seconds": closed["elapsed_seconds"],
        "combined_capture_bytes_before_receipt": retained + new,
        "capture_files": 56,
        "resource_failure_files": 241,
        **expected_counts,
        "additional_coarse_native_runs_reused": 8,
        "additional_coarse_Cells_runs_reused": 24,
        "original_cells_worker_receipt_invented": False,
        "new_worker_warnings": [],
        "retained_native_installed_python_files": 332,
    }


def run(output):
    c.require(
        not any(n.split(".")[0] in fence.FORBIDDEN for n in sys.modules),
        "Audit imported a model/array runtime",
    )
    sys.meta_path.insert(0, fence.ImportFence())
    r = ctx.authenticate()
    metadata = inspect_metadata(r, ctx.SESSION)
    original = c.read(ctx.SESSION / "comparison.json")
    frozen = replay.run(r, ctx.SESSION)
    c.require(
        frozen == {k: v for k, v in original.items() if k not in independent.base.WORKER_FIELDS},
        "Frozen complete numerical replay differs",
    )
    scopes, failures = independent.rebuild(r, independent.load_panels(r))
    surfaces, required = independent.compare_rebuild(original, scopes)
    ledger = independent.classify(failures, scopes)
    c.write(
        output / "independent-surfaces.json",
        {
            "schema": "cells.betse_refined_response_independent_surfaces@1",
            "scope": SCOPE,
            "source_comparison_sha256": ctx.ANCHORS["comparison.json"],
            "all_surfaces": surfaces,
            "required_surfaces": required,
            "comparisons_by_scope": scopes,
            "reconstruction": (
                "D082 direct saved-array readers and fsum prefix transfers; variable full grids"
            ),
            "physical_criteria_unchanged": True,
            "diagnostic_reconstruction_roundoff": {"relative": 2e-11, "absolute": 2e-20},
            "roundoff_allowance_applies_to": (
                "reconstructed values/maxima only, never physical pass/fail"
            ),
        },
    )
    c.write(
        output / "failure-ledger.json",
        {"schema": "cells.betse_refined_response_failure_ledger@1", **ledger},
    )
    preserved = ctx.preservation_check()
    c.require(
        not any(n.split(".")[0] in fence.FORBIDDEN for n in sys.modules),
        "Audit loaded a model/array runtime",
    )
    return {
        "schema": "cells.betse_refined_response_saved_audit@1",
        "status": "saved_data_audit_pass_pending_regression",
        "audited_utc": datetime.now(UTC).isoformat(),
        "scope": SCOPE,
        "anchors": ctx.ANCHORS,
        "driver_sha256": c.sha(Path(__file__)),
        "frozen_comparisons_replayed": 2494936,
        "internal_laws_replayed": frozen["internal_laws"],
        "required_gates_replayed": frozen["required_gates"],
        "independent_surfaces": surfaces,
        "independent_required_surfaces": required,
        "independent_surface_scopes": len(scopes),
        "failure_classification": ledger["by_family"],
        "independent_surfaces_sha256": c.sha(output / "independent-surfaces.json"),
        "failure_ledger_sha256": c.sha(output / "failure-ledger.json"),
        "finest_held_response_qualified": False,
        "native_convergence_qualified": False,
        "forcing_convergence_qualified": False,
        "capture_rerun": False,
        "original_packets_rewritten": False,
        "biology_validated": False,
        "gpu_tested": False,
        "model_calls": 0,
        "model_imports": [],
        "capture_metadata": metadata,
        **preserved,
    }


def validate_result(result, output, registration):
    c.require(
        result["schema"] == "cells.betse_refined_response_saved_audit@1"
        and result["status"] == "saved_data_audit_pass_pending_regression"
        and result["scope"] == SCOPE
        and result["anchors"] == ctx.ANCHORS
        and result["driver_sha256"] == registration["sources"]["response_closeout/refined_audit.py"]
        and result["frozen_comparisons_replayed"] == 2494936
        and result["internal_laws_replayed"]["comparisons"] == 1373032
        and result["internal_laws_replayed"]["failed_comparisons"] == 0
        and result["required_gates_replayed"]["comparisons"] == 2298936
        and result["required_gates_replayed"]["failed_comparisons"] == 0
        and result["independent_surfaces"]["comparisons"] == 1121904
        and result["independent_surfaces"]["failed_comparisons"] == 4173
        and result["independent_required_surfaces"]["comparisons"] == 925904
        and result["independent_required_surfaces"]["failed_comparisons"] == 0
        and result["independent_surface_scopes"] == 132,
        "Independent audit identity/coverage/verdict differs",
    )
    c.require(
        result["model_calls"] == 0
        and result["model_imports"] == []
        and all(
            result[k] is False
            for k in (
                "finest_held_response_qualified",
                "native_convergence_qualified",
                "forcing_convergence_qualified",
                "capture_rerun",
                "original_packets_rewritten",
                "biology_validated",
                "gpu_tested",
            )
        )
        and result["capture_metadata"]["original_cells_worker_receipt_invented"] is False,
        "Audit overclaims its scope",
    )
    c.require(
        result["independent_surfaces_sha256"] == c.sha(output / "independent-surfaces.json")
        and result["failure_ledger_sha256"] == c.sha(output / "failure-ledger.json"),
        "Independent audit output digest differs",
    )
    surface = c.read(output / "independent-surfaces.json")
    ledger = c.read(output / "failure-ledger.json")
    c.require(
        surface["scope"] == SCOPE
        and surface["all_surfaces"] == result["independent_surfaces"]
        and surface["required_surfaces"] == result["independent_required_surfaces"]
        and len(surface["comparisons_by_scope"]) == 132
        and ledger["by_family"] == result["failure_classification"]
        and len(ledger["all_failures"]) == len({v["id"] for v in ledger["all_failures"]}) == 4173
        and all(
            v["required"] is False
            and math.isfinite(v["normalized_error"])
            and v["normalized_error"] > 1
            for v in ledger["all_failures"]
        ),
        "Independent audit ledger/surface linkage differs",
    )
    scopes = surface["comparisons_by_scope"]
    required = [v for v in scopes.values() if v["required"]]
    c.require(
        sum(v["comparisons"] for v in scopes.values()) == 1121904
        and sum(v["failed_comparisons"] for v in scopes.values()) == 4173
        and sum(v["comparisons"] for v in required) == 925904
        and sum(v["failed_comparisons"] for v in required) == 0
        and max(v["maximum_normalized_error"] for v in scopes.values())
        == surface["all_surfaces"]["maximum_normalized_error"]
        and max(v["maximum_normalized_error"] for v in required)
        == surface["required_surfaces"]["maximum_normalized_error"],
        "Independent summary does not account for its scopes",
    )
    classified = independent.classify(ledger["all_failures"], scopes)
    c.require(
        all(ledger[k] == v for k, v in classified.items()), "Stored ledger classification differs"
    )
    counts = dict(Counter(v["scope"] for v in ledger["all_failures"]))
    c.require(
        counts
        == {n: v["failed_comparisons"] for n, v in scopes.items() if v["failed_comparisons"]},
        "Full failure ledger does not account for every scope",
    )
    columns = ("id", "actual", "expected", "normalized_error")
    for name, scope in scopes.items():
        detailed = [
            {k: v[k] for k in columns} for v in ledger["all_failures"] if v["scope"] == name
        ]
        c.require(
            scope["first_failures"] == detailed[:100],
            "Scope failure examples disagree with full ledger",
        )
    c.require(
        surface["all_surfaces"]["first_failures"]
        == [{k: v[k] for k in columns} for v in ledger["all_failures"][:100]],
        "Aggregate failure examples disagree with full ledger",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    c.require(
        destination.is_dir()
        and destination.is_relative_to(c.ROOT / "runs")
        and destination not in (ctx.SESSION, ctx.prior.FAILED, ctx.prior.prior.COARSE),
        "Use the registered audit output directory",
    )
    job = importlib.import_module("refined_audit_job")
    registration = c.read(destination / "registration.json")
    job.validate_registration(registration)
    ctx.prior.old_job.capsule(destination, registration)
    c.write(destination / "audit.json", run(destination))
