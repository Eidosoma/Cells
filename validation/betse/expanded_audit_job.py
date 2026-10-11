"""Detached expanded saved-data audit/regression closeout; no simulation or retry."""

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import contact as c
import expanded_audit as audit
import expanded_audit_context as ctx
import full_loop_audit_job as common


def validate_registration(registered):
    preflight = c.read(ctx.PRELAUNCH)
    c.require(
        registered["schema"] == "cells.betse_expanded_audit_registration@1"
        and registered["job_plan"] == ctx.JOB_PLAN
        and registered["capture_anchors"] == ctx.ANCHORS
        and registered["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and registered["preservation_sha256"] == c.sha(ctx.PRESERVATION),
        "Expanded audit registration changed",
    )
    c.require(
        preflight["status"] == "pass"
        and preflight["job_plan"] == ctx.JOB_PLAN
        and preflight["sources"] == ctx.sources()
        and preflight["test_receipt_sha256"] == c.sha(c.ROOT / preflight["test_receipt"])
        and registered["expected_tests"] == 290 + preflight["tests"]["tests"],
        "Expanded audit preflight/test coverage changed",
    )
    c.require(
        registered["sources"]
        == c.read(ctx.SESSION / "registration.json")["sources"] | ctx.sources()
        and all(c.sha(c.HERE / n) == h for n, h in registered["sources"].items()),
        "Expanded audit source coverage changed",
    )
    for n, h in preflight["new_files_sha256_before_prelaunch"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen audit preflight source/evidence changed: " + n)


def check_capsule(output, registered):
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(registered["sources"]),
            "Audit capsule coverage differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == registered["sources"][n]
                for n in names
            ),
            "Audit capsule bytes differ",
        )


def stage_commands(output):
    return [
        (
            "audit",
            [
                str(c.CELLS_PYTHON),
                "-B",
                str(c.HERE / "expanded_audit.py"),
                "--receipt",
                str(output / "audit.json"),
            ],
        ),
        (
            "regression",
            [
                str(c.CELLS_PYTHON),
                "-B",
                "-m",
                "pytest",
                "-q",
                *[str(c.HERE / n) for n in ctx.JOB_PLAN["test_modules"]],
                "--junitxml=" + str(output / "regression.xml"),
            ],
        ),
    ]


def validate_audit(result, registered):
    c.require(
        result["schema"] == "cells.betse_expanded_bridge_audit@1"
        and result["status"] == "pass"
        and result["scope"] == audit.SCOPE
        and result["anchors"] == ctx.ANCHORS
        and result["comparisons"] == ctx.COMPARISONS
        and result["failed_comparisons"] == 0
        and math.isfinite(result["maximum_normalized_error"])
        and 0 <= result["maximum_normalized_error"] <= 1
        and result["failures"] == []
        and result["observed_steps"] == 3360
        and result["controls"] == audit.CONTROLS
        and result["enabled_target_event_dispatches"] == 1120
        and result["payload_files"] == 798
        and result["capsule_sources"] == 67
        and result["row_summaries"]
        == [{"row": r, "comparisons": 266 + 364 * audit.count(r)} for r in audit.expected_rows()]
        and result["model_imports"] == []
        and result["production_calls"] == 0
        and result["criteria_registration_sha256"] == audit.previous.ANCHORS["registration.json"]
        and result["driver_sha256"] == registered["sources"]["expanded_audit.py"]
        and result["qualification_pending_regression_closeout"] is True
        and all(
            result[k] is False
            for k in (
                "trajectory_qualified",
                "expanded_bridge_qualified",
                "capture_rerun",
                "nonzero_intervention",
                "restart_qualified",
                "biology_validated",
                "gpu_tested",
            )
        )
        and result["cells_runs"] == 0,
        "Independent expanded audit incomplete or overclaims",
    )


def finish(output, registered, started, stage_seconds):
    validate_registration(registered)
    check_capsule(output, registered)
    preserved = ctx.preservation_check()
    result = c.read(output / "audit.json")
    validate_audit(result, registered)
    counts, modules = ctx.prior.test_counts(output / "regression.xml")
    c.require(
        counts["tests"] == registered["expected_tests"]
        and modules == {"validation.betse." + Path(n).stem for n in ctx.JOB_PLAN["test_modules"]},
        "Focused expanded regression incomplete",
    )
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    manifest = common.payloads(output)
    elapsed = time.monotonic() - started
    c.require(
        size < ctx.JOB_PLAN["max_artifact_bytes"] - 65536
        and elapsed < ctx.JOB_PLAN["total_timeout_seconds"],
        "Offline job budget exhausted",
    )
    c.require(
        set(stage_seconds) == {"audit", "regression"}
        and all(0 < t < ctx.JOB_PLAN["stage_timeout_seconds"] for t in stage_seconds.values()),
        "Incomplete stage timing",
    )
    c.write(
        output / "completion.json",
        {
            "schema": "cells.betse_expanded_bridge_closeout@1",
            "status": "pass",
            "finished_utc": datetime.now(UTC).isoformat(),
            "elapsed_seconds": elapsed,
            "stage_seconds": stage_seconds,
            "scope": result["scope"],
            "tests": counts,
            "comparisons": result["comparisons"],
            "maximum_normalized_error": result["maximum_normalized_error"],
            "observed_steps": result["observed_steps"],
            "controls": result["controls"],
            "registration_sha256": c.sha(output / "registration.json"),
            "files_sha256": manifest,
            "artifact_bytes_before_receipt": size,
            "capture_seconds": result["capture_seconds"],
            "trajectory_qualified": True,
            "expanded_bridge_qualified": True,
            "nonzero_intervention": False,
            "restart_qualified": False,
            "biology_validated": False,
            "gpu_tested": False,
            "production_changed": False,
            "capture_rerun": False,
            "production_matrix_rerun": False,
            "prior_full_adapter_suite_rerun": False,
            "focused_d075_d076_d077_tests_rerun": True,
            "automatic_expansion": False,
            "automatic_retry": False,
            "stable_version": "0.14.0",
            "development_version": "0.15.0.dev0",
            "stable_promotion": False,
            **preserved,
        },
    )


def execute(output):
    started, stage_seconds = time.monotonic(), {}
    try:
        registered = c.read(output / "registration.json")
        validate_registration(registered)
        check_capsule(output, registered)
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        env.pop("PYTHONPATH", None)
        for name, command in stage_commands(output):
            remaining = ctx.JOB_PLAN["total_timeout_seconds"] - (time.monotonic() - started)
            c.require(remaining > 0, "Offline total wall budget exhausted")
            stage_start = time.monotonic()
            with (output / (name + ".log")).open("x") as log:
                subprocess.run(
                    ["taskset", "-c", ctx.JOB_PLAN["cpu_affinity"], *command],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=min(remaining, ctx.JOB_PLAN["stage_timeout_seconds"]),
                )
            stage_seconds[name] = time.monotonic() - stage_start
            c.require(
                sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                < ctx.JOB_PLAN["max_artifact_bytes"] - 65536,
                "Offline artifact cap exceeded",
            )
            print(json.dumps({"completed_stage": name, "seconds": stage_seconds[name]}), flush=True)
        finish(output, registered, started, stage_seconds)
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "elapsed_seconds": time.monotonic() - started,
                "stage_seconds": stage_seconds,
                "traceback": traceback.format_exc(),
                "files_sha256": common.payloads(output),
                "capture_rerun": False,
                "expanded_bridge_qualified": False,
                "automatic_retry": False,
            },
        )
        raise


def register(output):
    ctx.preservation_check()
    preflight = c.read(ctx.PRELAUNCH)
    registered = {
        "schema": "cells.betse_expanded_audit_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "job_plan": ctx.JOB_PLAN,
        "capture_anchors": ctx.ANCHORS,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "sources": c.read(ctx.SESSION / "registration.json")["sources"] | ctx.sources(),
        "expected_tests": 290 + preflight["tests"]["tests"],
    }
    validate_registration(registered)
    c.require(
        output.is_relative_to(c.ROOT / "runs") and output != c.ROOT / "runs",
        "Use a fresh audit run subdirectory",
    )
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for n in registered["sources"]:
            archive.write(c.HERE / n, arcname=n)
    check_capsule(output, registered)
    return registered


def launch(output):
    register(output)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ctx.JOB_PLAN["cpu_affinity"],
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
                "files_sha256": common.payloads(output),
            },
        )
        raise
    receipt = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": c.sha(output / "registration.json"),
        "stage_timeout_seconds": ctx.JOB_PLAN["stage_timeout_seconds"],
        "total_timeout_seconds": ctx.JOB_PLAN["total_timeout_seconds"],
        "automatic_polling": False,
        "capture_rerun": False,
        "automatic_expansion": False,
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (launch if args.command == "launch" else execute)(args.output.resolve())
