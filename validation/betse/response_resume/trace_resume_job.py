"""Source-frozen remaining-row capture; never rerun native or completed Cells rows."""

import argparse
import json
import os
import resource
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import trace_resume_check as check
import trace_resume_context as ctx
import trace_resume_probe as probe

c, old = ctx.c, ctx.old_job
STAGES = ("cells", "comparison")


def bytes_used(output):
    return old.budget.artifact_bytes(ctx.FAILED) + old.budget.artifact_bytes(output)


def check_budget(output, plan):
    c.require(
        bytes_used(output) < plan["max_artifact_bytes"] - 1024**2,
        "Combined retained/new artifact budget exhausted",
    )


def register(output):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists()
        and not output.is_relative_to(ctx.FAILED),
        "Use a fresh continuation directory",
    )
    r = ctx.inputs() | {
        "schema": "cells.betse_trace_resume_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "sources": ctx.sources(),
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
    }
    ctx.validate_registration(r)
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", r)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in r["sources"]:
            archive.write(c.HERE / name, arcname=name)
    old.capsule(output, r)
    return r


def cells_worker(r, output):
    # Re-exercise the production timeline guard for every declared row before
    # the first rollout, including rows not about to execute in this process.
    result = probe.probe(r)
    probe.validate(result, r)
    c.write(output / "runtime-resource-probe.json", result)
    fresh = r["new_cells_rows"]
    c.require(
        len(fresh) == 22 and not ({row["id"] for row in fresh} & set(r["reused_cells"])),
        "Repeated or incomplete remaining-row execution",
    )
    remaining_bytes = r["continuation_plan"]["max_artifact_bytes"] - old.budget.artifact_bytes(
        ctx.FAILED
    )
    # Execution-only list/aggregate-budget selection. Registered model
    # definitions, physics, solver and controls are passed through exactly.
    subset = r | {
        "cells_rows": fresh,
        "cells_definitions": {row["id"]: r["cells_definitions"][row["id"]] for row in fresh},
        "plan": r["plan"] | {"cells_runs": 22, "max_artifact_bytes": remaining_bytes},
    }
    saved = old.cells_worker(subset, output)
    return saved | {
        "schema": "cells.betse_trace_resume_cells_worker@1",
        "new_cells_runs": 22,
        "reused_cells_runs": 26,
        "runtime_resource_probe_sha256": c.sha(output / "runtime-resource-probe.json"),
    }


def worker(stage, output):
    c.require(stage in STAGES, "Unknown continuation stage")
    began = time.monotonic()
    try:
        r = c.read(output / "registration.json")
        ctx.validate_registration(r)
        old.capsule(output, r)
        p = r["continuation_plan"]
        c.require(sorted(os.sched_getaffinity(0)) == [0, 1, 2, 3], "Worker CPU affinity differs")
        resource.setrlimit(resource.RLIMIT_FSIZE, (p["max_worker_file_bytes"],) * 2)
        result = (cells_worker if stage == "cells" else check.run)(r, output)
        c.write(
            output / (stage + ".json"),
            result
            | {
                "registration_sha256": c.sha(output / "registration.json"),
                "sources": r["sources"],
                "elapsed_seconds": time.monotonic() - began,
            },
        )
    except BaseException:
        c.write(
            output / (stage + "-failure.json"),
            {
                "status": "failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "trajectory_qualified": False,
            },
        )
        raise


def execute(output):
    began, stage = time.monotonic(), "validation"
    try:
        r = c.read(output / "registration.json")
        ctx.validate_registration(r)
        old.capsule(output, r)
        p = r["continuation_plan"]
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        for stage in STAGES:
            remaining = p["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "Continuation total deadline exhausted")
            with (output / (stage + ".log")).open("x") as log:
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        p["cpu_affinity"],
                        str(c.CELLS_PYTHON),
                        "-B",
                        str(Path(__file__).resolve()),
                        stage,
                        str(output),
                    ],
                    cwd=c.ROOT,
                    env=old.environment(output),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=min(remaining, p["stage_timeout_seconds"][stage]),
                )
            check_budget(output, p)
        compared = c.read(output / "comparison.json")
        c.require(
            compared["status"]
            == "finest_held_response_gates_pass_with_coarse_rejections_pending_audit"
            and compared["required_gates"]["failed_comparisons"] == 0
            and compared["coarse_rejection_replayed_exactly"] is True
            and compared["coarse_failed_comparisons"] == 150,
            "Continuation required gates failed; preserve results without automatic retry",
        )
        preserved = ctx.preservation_check()
        ctx.validate_registration(r)
        check_budget(output, p)
        c.require(
            time.monotonic() - began < p["total_timeout_seconds"],
            "Continuation total deadline exhausted",
        )
        c.write(
            output / "capture.json",
            {
                "schema": "cells.betse_trace_resume_capture@1",
                "status": compared["status"],
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": old.files.manifest(output, old.budget.OPERATIONAL),
                "failed_capture_anchors": ctx.ANCHORS,
                "new_native_runs": 0,
                "reused_native_runs": 16,
                "new_cells_runs": 22,
                "reused_cells_runs": 26,
                "combined_artifact_bytes_before_receipt": bytes_used(output),
                "comparisons": compared["comparisons"],
                "failed_comparisons": compared["failed_comparisons"],
                "required_failed_comparisons": compared["required_gates"]["failed_comparisons"],
                "coarse_failed_comparisons": 150,
                "trajectory_run": True,
                "trajectory_qualified": False,
                "native_convergence_qualified": False,
                "forcing_convergence_qualified": False,
                "independent_audit_run": False,
                "biology_validated": False,
                "gpu_tested": False,
                **preserved,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "schema": "cells.betse_trace_resume_failure@1",
                "status": "failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "files_sha256": old.files.manifest(output, old.budget.OPERATIONAL),
                "failed_capture_anchors": ctx.ANCHORS,
                "automatic_retry": False,
                "automatic_expansion": False,
                "trajectory_qualified": False,
            },
        )
        raise


def launch(output):
    r = register(output)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    r["continuation_plan"]["cpu_affinity"],
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
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
            },
        )
        raise
    receipt = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": c.sha(output / "registration.json"),
        "new_native_runs": 0,
        "new_cells_runs": 22,
        "reused_native_runs": 16,
        "reused_cells_runs": 26,
        "stage_timeout_seconds": r["continuation_plan"]["stage_timeout_seconds"],
        "total_timeout_seconds": r["continuation_plan"]["total_timeout_seconds"],
        "automatic_polling": False,
        "automatic_retry": False,
        "independent_audit": "await_user_instruction",
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute", *STAGES))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    if args.action == "launch":
        launch(destination)
    elif args.action == "execute":
        execute(destination)
    else:
        worker(args.action, destination)
