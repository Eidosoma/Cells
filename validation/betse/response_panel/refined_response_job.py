"""Source-frozen response pilot: separate bounded workers, detached launch, no polling."""

import argparse
import hashlib
import importlib
import json
import os
import resource
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import refined_response_check as check
import refined_response_context as ctx
import refined_response_native as native

c = ctx.c
files = importlib.import_module("dispatch_preflight")
budget = importlib.import_module("full_loop_bridge")
runner = importlib.import_module("trajectory")
evidence = importlib.import_module("trajectory_evidence")

STAGES = ("native", "cells", "comparison")
SOFTWARE_PLAN = {
    "schema": "cells.betse_refined_response_software_plan@1",
    "cpu_affinity": "0-3",
    "regression_timeout_seconds": 180,
    "total_timeout_seconds": 300,
    "max_artifact_bytes": 16777216,
    "max_worker_file_bytes": 8388608,
    "expected_tests": 114,
    "automatic_polling": False,
    "automatic_retry": False,
    "automatic_trajectory_launch": False,
}
TEST_MODULES = {
    "validation.betse.response_panel.test_refined_response",
    "validation.betse.response_panel.test_refined_response_check",
}


def capsule(output, registered):
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(registered["sources"]),
            "Response capsule coverage differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == registered["sources"][n]
                for n in names
            ),
            "Response capsule content differs",
        )


def register(output):
    ctx.preservation_check()
    plan, prior = c.read(ctx.PLAN), evidence.trusted_registration()
    ctx.validate_plan(plan)
    registered = {
        "schema": "cells.betse_refined_response_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "native_rows": ctx.native_rows(plan),
        "cells_rows": ctx.cells_rows(plan),
        "cells_definitions": ctx.definitions(plan),
        "common_times_s": ctx.common_times(plan),
        "cells_export_shapes": ctx.export_shapes(),
        "sources": ctx.sources(),
        "upstream": c.inspect_source(),
        "dispatch_anchors": ctx.ANCHORS,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "criteria": prior["protocol"],
        **{k: prior[k] for k in ("base_protocol", "geometry", "settings", "cells_runtime")},
    }
    ctx.validate_registration(registered)
    c.require(
        output.is_relative_to(c.ROOT / "runs") and output != c.ROOT / "runs",
        "Use a fresh run subdirectory",
    )
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    capsule(output, registered)
    return registered


def cells_worker(registered, output):
    results, metadata = {}, None
    (output / "cells-started").mkdir(exist_ok=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error", RuntimeWarning)
        for index, row in enumerate(registered["cells_rows"]):
            identifier = row["id"]
            c.write(
                output / "cells-started" / f"{index:02d}.json",
                {"row": row, "started_utc": datetime.now(UTC).isoformat()},
            )
            # Narrow only the execution list passed to the unchanged exporter.
            # Its definition is the exact registered input, never fitted to BETSE output.
            subset = registered | {
                "cells_definitions": {identifier: registered["cells_definitions"][identifier]}
            }
            saved = runner.cells_worker(subset, output)
            current = {k: v for k, v in saved.items() if k != "results"}
            c.require(
                metadata is None or current == metadata, "Cells engine/runtime changed between rows"
            )
            metadata = current
            c.require(set(saved["results"]) == {identifier}, "Cells exporter coverage differs")
            results |= saved["results"]
            budget.check_budget(output, registered["plan"])
        c.require(not caught, "Cells response emitted Python warnings")
    c.require(len(results) == registered["plan"]["cells_runs"], "Incomplete Cells panel")
    return {
        "schema": "cells.betse_refined_response_cells_worker@1",
        "status": "exported_pending_comparison",
        "results": results,
        "warnings": [],
        **metadata,
    }


def worker(stage, output):
    c.require(stage in STAGES, "Unknown response stage")
    started = time.monotonic()
    try:
        registered = c.read(output / "registration.json")
        ctx.validate_registration(registered)
        capsule(output, registered)
        c.require(sorted(os.sched_getaffinity(0)) == [0, 1, 2, 3], "Worker CPU affinity differs")
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (registered["plan"]["max_worker_file_bytes"],) * 2
        )
        result = {"native": native.worker, "cells": cells_worker, "comparison": check.run}[stage](
            registered, output
        )
        result |= {
            "registration_sha256": c.sha(output / "registration.json"),
            "sources": registered["sources"],
            "elapsed_seconds": time.monotonic() - started,
        }
        # Numerical failure is a durable comparison result, not a swallowed exception.
        c.write(output / (stage + ".json"), result)
    except BaseException:
        c.write(
            output / (stage + "-failure.json"),
            {
                "status": "failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "trajectory_qualified": False,
            },
        )
        raise


def environment(output):
    env = os.environ | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(output / "matplotlib-cache"),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "JAX_ENABLE_X64": "1",
        "JAX_PLATFORMS": "cpu",
    }
    for name in ("PYTHONPATH", "JAX_DISABLE_JIT"):
        env.pop(name, None)
    return env


def stage_command(stage, output, plan):
    c.require(stage in STAGES, "Unknown response stage")
    interpreter = c.REFERENCE_PYTHON if stage == "native" else c.CELLS_PYTHON
    return [
        "taskset",
        "-c",
        plan["cpu_affinity"],
        str(interpreter),
        "-B",
        str(Path(__file__).resolve()),
        stage,
        str(output),
    ]


def execute(output):
    started, stage = time.monotonic(), "validation"
    try:
        registered = c.read(output / "registration.json")
        ctx.validate_registration(registered)
        capsule(output, registered)
        plan = registered["plan"]
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        for stage in STAGES:
            remaining = plan["total_timeout_seconds"] - (time.monotonic() - started)
            c.require(remaining > 0, "Response wall budget exhausted")
            with (output / (stage + ".log")).open("x") as log:
                subprocess.run(
                    stage_command(stage, output, plan),
                    cwd=c.ROOT,
                    env=environment(output),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=min(remaining, plan["stage_timeout_seconds"][stage]),
                    check=True,
                )
            budget.check_budget(output, plan)
        comparison = c.read(output / "comparison.json")
        c.require(
            comparison["status"]
            == "finest_held_response_gates_pass_with_coarse_rejections_pending_audit"
            and comparison["required_gates"]["failed_comparisons"] == 0
            and comparison["coarse_rejection_replayed_exactly"] is True
            and comparison["coarse_failed_comparisons"] == 150,
            "Response comparison failed; preserve all results without retry or tolerance changes",
        )
        ctx.preservation_check()
        ctx.validate_registration(registered)
        capsule(output, registered)
        budget.check_budget(output, plan)
        c.require(
            time.monotonic() - started < plan["total_timeout_seconds"],
            "Response total wall budget exhausted",
        )
        c.write(
            output / "capture.json",
            {
                "schema": "cells.betse_refined_response_capture@1",
                "status": "finest_held_response_gates_pass_with_coarse_rejections_pending_audit",
                "elapsed_seconds": time.monotonic() - started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": files.manifest(output, budget.OPERATIONAL),
                "artifact_bytes_before_receipt": budget.artifact_bytes(output),
                "native_runs": 16,
                "cells_runs": 48,
                "observed_native_steps": 960,
                "trajectory_run": True,
                "failed_comparisons": comparison["failed_comparisons"],
                "required_failed_comparisons": comparison["required_gates"]["failed_comparisons"],
                "coarse_failed_comparisons": 150,
                "trajectory_qualified": False,
                "native_convergence_qualified": False,
                "forcing_convergence_qualified": False,
                "independent_audit_run": False,
                "biology_validated": False,
                "gpu_tested": False,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "schema": "cells.betse_refined_response_failure@1",
                "status": "failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "files_sha256": files.manifest(output, budget.OPERATIONAL),
                "trajectory_qualified": False,
                "automatic_retry": False,
                "automatic_expansion": False,
            },
        )
        raise


def launch(output):
    registered = register(output)
    spawn_detached(output, registered["plan"], "execute")


def spawn_detached(output, plan, command):
    """One detached process and durable launch/failure receipt; no poll or wait."""
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    plan["cpu_affinity"],
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    command,
                    str(output),
                ],
                cwd=c.ROOT,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "launch_failed_not_started",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
                "trajectory_qualified": False,
            },
        )
        raise
    receipt = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "registration_sha256": c.sha(output / "registration.json"),
        "total_timeout_seconds": plan["total_timeout_seconds"],
        "automatic_polling": False,
        "automatic_retry": False,
        "independent_audit": "await_user_instruction",
    }
    if command == "execute":
        receipt["stage_timeout_seconds"] = plan["stage_timeout_seconds"]
    else:
        receipt["regression_timeout_seconds"] = plan["regression_timeout_seconds"]
        receipt["automatic_trajectory_launch"] = False
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


def launch_checks(output):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use a fresh software-check directory",
    )
    ctx.preservation_check()
    earlier = {
        str(p.relative_to(c.ROOT)): c.sha(p)
        for p in sorted((c.ROOT / "reports").glob("ref-003e1-refined-response-checks-*.xml"))
    }
    c.require(bool(earlier), "Missing earlier software attempt evidence")
    # Freeze existing/new task files as well as Python; exclude only the seven
    # mutable status documents. The registration is not a trajectory registration.
    freeze = ctx.audit.files.worktree() | earlier
    freeze = {n: h for n, h in freeze.items() if n not in ctx.legacy.edits.ALLOWED_EDITS}
    registered = {
        "schema": "cells.betse_refined_response_software_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "software_plan": SOFTWARE_PLAN,
        "response_plan": c.read(ctx.PLAN),
        "sources": ctx.sources(),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "files_sha256": freeze,
        "earlier_test_receipts_sha256": earlier,
        "trajectory_run": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    validate_software_registration(registered, output)
    spawn_detached(output, SOFTWARE_PLAN, "checks")


def validate_software_registration(r, output):
    c.require(
        r["schema"] == "cells.betse_refined_response_software_registration@1"
        and r["software_plan"] == SOFTWARE_PLAN
        and r["response_plan"] == c.read(ctx.PLAN)
        and r["sources"] == ctx.sources()
        and len(r["sources"]) == 106
        and r["preservation_sha256"] == c.sha(ctx.PRESERVATION)
        and r["trajectory_run"] is False
        and all(c.sha(c.ROOT / n) == h for n, h in r["files_sha256"].items())
        and all(c.sha(c.HERE / n) == h for n, h in r["sources"].items())
        and all(
            r["files_sha256"].get(n) == h for n, h in r["earlier_test_receipts_sha256"].items()
        ),
        "Software preflight registration/source differs",
    )
    ctx.validate_plan(r["response_plan"])
    capsule(output, r)


def execute_checks(output):
    began, stage = time.monotonic(), "validation"
    try:
        registered = c.read(output / "registration.json")
        validate_software_registration(registered, output)
        c.require(sorted(os.sched_getaffinity(0)) == [0, 1, 2, 3], "Worker CPU affinity differs")
        resource.setrlimit(resource.RLIMIT_FSIZE, (SOFTWARE_PLAN["max_worker_file_bytes"],) * 2)
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        ctx.preservation_check()
        stage = "regression"
        remaining = SOFTWARE_PLAN["total_timeout_seconds"] - (time.monotonic() - began)
        c.require(remaining > 0, "Software total deadline exhausted")
        with (output / "regression.log").open("x") as log:
            subprocess.run(
                [
                    str(c.CELLS_PYTHON),
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-W",
                    "error",
                    str(ctx.HERE / "test_refined_response.py"),
                    str(ctx.HERE / "test_refined_response_check.py"),
                    "--junitxml=" + str(output / "regression.xml"),
                ],
                cwd=c.ROOT,
                env=environment(output),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=min(remaining, SOFTWARE_PLAN["regression_timeout_seconds"]),
            )
        stage = "quality_and_receipts"
        counts, modules = ctx.audit.receipts.test_counts(output / "regression.xml")
        c.require(
            counts["tests"] == SOFTWARE_PLAN["expected_tests"] and modules == TEST_MODULES,
            "Software regression coverage differs",
        )
        quality = {}
        for name, args in (("lint", ["check"]), ("format", ["format", "--check"])):
            quality[name] = subprocess.check_output(
                [str(c.ROOT / ".venv/bin/ruff"), *args, "src", "tests", "scripts", "validation"],
                cwd=c.ROOT,
                text=True,
                timeout=20,
            ).strip()
        validate_software_registration(registered, output)
        preserved = ctx.preservation_check()
        budget.check_budget(output, SOFTWARE_PLAN)
        c.require(
            time.monotonic() - began < SOFTWARE_PLAN["total_timeout_seconds"],
            "Software total deadline exhausted",
        )
        c.write(
            output / "completion.json",
            {
                "schema": "cells.betse_refined_response_software_completion@1",
                "status": "software_checks_pass_await_user_review_no_response_launch",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "registration_sha256": c.sha(output / "registration.json"),
                "test_receipt_sha256": c.sha(output / "regression.xml"),
                "sources": registered["sources"],
                "tests": counts,
                "quality": quality,
                "files_sha256": files.manifest(output, budget.OPERATIONAL),
                "trajectory_run": False,
                "trajectory_qualified": False,
                "independent_audit_run": False,
                "automatic_trajectory_launch": False,
                "automatic_retry": False,
                **preserved,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "software_checks_failed_no_response_launch",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "files_sha256": files.manifest(output, budget.OPERATIONAL),
                "trajectory_run": False,
                "trajectory_qualified": False,
                "automatic_retry": False,
                "automatic_trajectory_launch": False,
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("launch", "execute", "launch-checks", "checks", *STAGES)
    )
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    if args.command == "launch-checks":
        launch_checks(destination)
    elif args.command == "checks":
        execute_checks(destination)
    elif args.command == "launch":
        launch(destination)
    elif args.command == "execute":
        execute(destination)
    else:
        worker(args.command, destination)
