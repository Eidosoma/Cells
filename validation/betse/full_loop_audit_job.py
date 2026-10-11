"""Detached saved-pilot audit and focused regression; no model or expanded capture."""

import argparse
import json
import os
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import contact as c
import full_loop_audit_context as ctx

OPERATIONAL = {"launch.json", "runner.stdout.log", "runner.stderr.log"}


def payloads(output):
    return {
        str(p.relative_to(output)): c.sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and str(p.relative_to(output)) not in OPERATIONAL
    }


def validate_registration(registered):
    preflight = c.read(ctx.PRELAUNCH)
    c.require(
        registered["schema"] == "cells.betse_full_loop_audit_registration@1"
        and registered["job_plan"] == ctx.JOB_PLAN
        and registered["pilot_anchors"] == ctx.ANCHORS
        and registered["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and registered["preservation_sha256"] == c.sha(ctx.PRESERVATION),
        "Audit job registration changed",
    )
    c.require(
        preflight["status"] == "pass"
        and preflight["job_plan"] == ctx.JOB_PLAN
        and preflight["sources"] == ctx.sources()
        and preflight["test_receipt_sha256"] == c.sha(c.ROOT / preflight["test_receipt"]),
        "Audit preflight changed",
    )
    c.require(
        registered["sources"]
        == c.read(ctx.SESSION / "registration.json")["sources"] | ctx.sources()
        and all(c.sha(c.HERE / n) == h for n, h in registered["sources"].items())
        and registered["expected_tests"] == 100 + preflight["tests"]["tests"],
        "Audit source/test coverage changed",
    )


def stage_commands(output):
    return [
        (
            "audit",
            [
                str(c.CELLS_PYTHON),
                "-B",
                str(c.HERE / "full_loop_audit.py"),
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
                *[str(c.HERE / name) for name in ctx.JOB_PLAN["test_modules"]],
                "--junitxml=" + str(output / "regression.xml"),
            ],
        ),
    ]


def finish(output, registered, started, stage_seconds):
    validate_registration(registered)
    preserved = ctx.preservation_check()
    audit = c.read(output / "audit.json")
    counts, modules = ctx.test_counts(output / "regression.xml")
    c.require(
        audit["status"] == "pass"
        and audit["anchors"] == ctx.ANCHORS
        and audit["comparisons"] == 88956
        and audit["failed_comparisons"] == 0
        and audit["observed_steps"] == 240
        and audit["controls"] == {"observer_pairs": 6, "variant_comparisons": 4}
        and audit["model_imports"] == []
        and audit["production_calls"] == 0
        and audit["driver_sha256"] == registered["sources"]["full_loop_audit.py"],
        "Independent audit incomplete",
    )
    c.require(
        counts["tests"] == registered["expected_tests"]
        and modules == {"validation.betse." + Path(n).stem for n in ctx.JOB_PLAN["test_modules"]},
        "Focused regression incomplete",
    )
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    manifest = payloads(output)
    elapsed = time.monotonic() - started
    c.require(
        size < ctx.JOB_PLAN["max_artifact_bytes"] - 65536
        and elapsed < ctx.JOB_PLAN["total_timeout_seconds"],
        "Audit job resource budget exhausted",
    )
    c.write(
        output / "completion.json",
        {
            "schema": "cells.betse_full_loop_pilot_closeout@1",
            "status": "pass",
            "finished_utc": datetime.now(UTC).isoformat(),
            "elapsed_seconds": elapsed,
            "stage_seconds": stage_seconds,
            "scope": audit["scope"],
            "tests": counts,
            "comparisons": audit["comparisons"],
            "maximum_normalized_error": audit["maximum_normalized_error"],
            "registration_sha256": c.sha(output / "registration.json"),
            "files_sha256": manifest,
            "artifact_bytes_before_receipt": size,
            "capture_seconds": audit["capture_seconds"],
            "trajectory_qualified": True,
            "pilot_trajectory_qualified": True,
            "expanded_bridge_qualified": False,
            "nonzero_intervention": False,
            "restart_qualified": False,
            "biology_validated": False,
            "gpu_tested": False,
            "production_changed": False,
            "capture_rerun": False,
            "production_matrix_rerun": False,
            "prior_full_adapter_suite_rerun": False,
            "focused_d075_tests_rerun": True,
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
            c.require(remaining > 0, "Audit total wall budget exhausted")
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
                "Audit artifact cap exceeded",
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
                "files_sha256": payloads(output),
                "capture_rerun": False,
                "automatic_retry": False,
            },
        )
        raise


def launch(output):
    ctx.preservation_check()
    preflight = c.read(ctx.PRELAUNCH)
    registered = {
        "schema": "cells.betse_full_loop_audit_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "job_plan": ctx.JOB_PLAN,
        "pilot_anchors": ctx.ANCHORS,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "sources": c.read(ctx.SESSION / "registration.json")["sources"] | ctx.sources(),
        "expected_tests": 100 + preflight["tests"]["tests"],
    }
    validate_registration(registered)
    c.require(
        output.is_relative_to(c.ROOT / "runs") and output != c.ROOT / "runs",
        "Use a fresh audit run subdirectory",
    )
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
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
                "files_sha256": payloads(output),
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
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (launch if args.command == "launch" else execute)(args.output.resolve())
