"""Detached saved-data audit and identity-bound focused regression; no simulation commands."""

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

import refined_audit as audit
import refined_audit_context as ctx

c = ctx.c


def validate_registration(r):
    pre = c.read(ctx.PRELAUNCH)
    ctx.validate_plan(c.read(ctx.PLAN))
    ctx.validate_plan(r["plan"])
    c.require(
        r["schema"] == "cells.betse_refined_response_audit_registration@1"
        and r["anchors"] == ctx.ANCHORS
        and r["prelaunch_sha256"] == c.sha(ctx.PRELAUNCH)
        and r["preservation_sha256"] == pre["preservation_sha256"] == c.sha(ctx.PRESERVATION)
        and r["sources"] == pre["sources"] == ctx.sources()
        and len(r["sources"]) == 118
        and all(c.sha(c.HERE / n) == h for n, h in r["sources"].items())
        and pre["status"] == "pass"
        and pre["plan"] == r["plan"]
        and pre["test_receipt_sha256"] == c.sha(c.ROOT / pre["test_receipt"])
        and r["expected_regression_identities"] == pre["expected_regression_identities"]
        and len(r["expected_regression_identities"]) == pre["tests"]["tests"] + 231,
        "Refined audit registration/source/preflight differs",
    )
    for n, h in pre["files_sha256"].items():
        c.require(c.sha(c.ROOT / n) == h, "Frozen refined audit preflight input changed: " + n)


def commands(output):
    python = [str(c.CELLS_PYTHON), "-B"]
    return [
        ("audit", [*python, str(ctx.HERE / "refined_audit.py"), str(output)]),
        (
            "regression",
            [
                *python,
                "-m",
                "pytest",
                "-q",
                "-W",
                "error",
                *(str(c.HERE / n) for n in ctx.EXPECTED["test_modules"]),
                "--junitxml=" + str(output / "regression.xml"),
            ],
        ),
    ]


def payloads(output):
    return {
        n: h
        for n, h in ctx.prior.audit.packet_hashes(output).items()
        if n not in ctx.prior.audit.OPERATIONAL
    }


def check_budget(output):
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    c.require(
        size < ctx.EXPECTED["max_artifact_bytes"] - 65536, "Refined audit artifact cap exceeded"
    )
    return size


def finish(output, r, began, stage_seconds):
    validate_registration(r)
    ctx.prior.old_job.capsule(output, r)
    preserved = ctx.preservation_check()
    result = c.read(output / "audit.json")
    audit.validate_result(result, output, r)
    tests = ctx.test_evidence(output / "regression.xml")
    c.require(
        tests["identities"] == r["expected_regression_identities"], "Regression identities differ"
    )
    size, elapsed = check_budget(output), time.monotonic() - began
    c.require(elapsed < r["plan"]["total_timeout_seconds"], "Refined audit total deadline exceeded")
    c.write(
        output / "completion.json",
        {
            "schema": "cells.betse_refined_response_closeout@1",
            "status": "finest_held_response_audit_closed_with_diagnostic_rejections",
            "finished_utc": datetime.now(UTC).isoformat(),
            "elapsed_seconds": elapsed,
            "stage_seconds": stage_seconds,
            "registration_sha256": c.sha(output / "registration.json"),
            "files_sha256": payloads(output),
            "artifact_bytes_before_receipt": size,
            "scope": audit.SCOPE,
            "frozen_comparisons_replayed": 2494936,
            "required_comparisons": 2298936,
            "required_failed_comparisons": 0,
            "independent_surface_comparisons": 1121904,
            "diagnostic_failed_comparisons": 4173,
            "failure_classification": result["failure_classification"],
            "tests": tests["counts"],
            "finest_held_response_qualified": True,
            "qualification_requires_this_scope": True,
            "native_convergence_qualified": False,
            "forcing_convergence_qualified": False,
            "capture_rerun": False,
            "original_packets_rewritten": False,
            "automatic_retry": False,
            "automatic_expansion": False,
            "biology_validated": False,
            "gpu_tested": False,
            **preserved,
        },
    )


def execute(output):
    began, stage, timings = time.monotonic(), "validation", {}
    try:
        r = c.read(output / "registration.json")
        validate_registration(r)
        ctx.prior.old_job.capsule(output, r)
        c.require(sorted(os.sched_getaffinity(0)) == [0, 1, 2, 3], "Audit CPU affinity differs")
        resource.setrlimit(resource.RLIMIT_FSIZE, (r["plan"]["max_worker_file_bytes"],) * 2)
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        env = ctx.prior.old_job.environment(output)
        for stage, command in commands(output):
            remaining = r["plan"]["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "Refined audit wall budget exhausted")
            start = time.monotonic()
            with (output / (stage + ".log")).open("x") as log:
                subprocess.run(
                    ["taskset", "-c", r["plan"]["cpu_affinity"], *command],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=min(remaining, r["plan"]["stage_timeout_seconds"][stage]),
                )
            timings[stage] = time.monotonic() - start
            check_budget(output)
            print(json.dumps({"completed_stage": stage, "seconds": timings[stage]}), flush=True)
        finish(output, r, began, timings)
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "schema": "cells.betse_refined_response_audit_failure@1",
                "status": "audit_failed_not_closed",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "stage_seconds": timings,
                "traceback": traceback.format_exc(),
                "files_sha256": payloads(output),
                "capture_rerun": False,
                "finest_held_response_qualified": False,
                "automatic_retry": False,
            },
        )
        raise


def register(output):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists()
        and not output.is_relative_to(ctx.SESSION)
        and not output.is_relative_to(ctx.prior.FAILED),
        "Use a fresh refined audit directory",
    )
    ctx.preservation_check()
    pre = c.read(ctx.PRELAUNCH)
    r = {
        "schema": "cells.betse_refined_response_audit_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": ctx.EXPECTED,
        "anchors": ctx.ANCHORS,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "sources": ctx.sources(),
        "expected_regression_identities": pre["expected_regression_identities"],
    }
    validate_registration(r)
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", r)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in r["sources"]:
            archive.write(c.HERE / name, arcname=name)
    ctx.prior.old_job.capsule(output, r)
    return r


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
                    ctx.EXPECTED["cpu_affinity"],
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
                "capture_rerun": False,
                "automatic_retry": False,
            },
        )
        raise
    receipt = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": c.sha(output / "registration.json"),
        "stage_timeout_seconds": ctx.EXPECTED["stage_timeout_seconds"],
        "total_timeout_seconds": ctx.EXPECTED["total_timeout_seconds"],
        "automatic_polling": False,
        "automatic_retry": False,
        "automatic_expansion": False,
        "capture_rerun": False,
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "execute"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    (launch if args.action == "launch" else execute)(args.output.resolve())
