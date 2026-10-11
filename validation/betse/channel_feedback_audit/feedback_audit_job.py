"""Register/detach one model-free coupled-pilot audit; no polling or follow-up."""

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
import traceback
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import feedback_audit_context as ctx

c, io = ctx.c, ctx.io


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_feedback_audit_registration@1",
        "Wrong feedback audit registration",
    )
    ctx.validate_plan(r["plan"])
    c.require(
        r["anchors"] == ctx.ANCHORS and r["capture"] == str(ctx.CAPTURE.relative_to(ctx.ROOT)),
        "Audit target changed",
    )
    c.require(
        r["sources_sha256"] == ctx.sources()
        and r["capture_sha256"] == ctx.packet_hashes(ctx.CAPTURE),
        "Audit source/capture bytes changed",
    )
    c.require(
        r["tests"] == ctx.test_receipt(ctx.ROOT / r["tests"]["path"]),
        "Audit software receipt changed",
    )
    c.require(
        r["historical_reports_sha256"] == ctx.historical_reports(),
        "Historical software/handoff changed",
    )
    c.require(r["forbidden_imports"] == list(ctx.FORBIDDEN), "Audit model boundary changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Audit source capsule membership",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(name)).hexdigest() == digest
                for name, digest in r["sources_sha256"].items()
            ),
            "Audit source capsule bytes",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists()
        and not output.is_relative_to(ctx.CAPTURE),
        "Use a fresh feedback audit directory",
    )
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    with ctx.model_fence():
        data = ctx.load_capture()  # Read-only provenance, not numerical audit.
    registration = {
        "schema": "cells.betse_channel_feedback_audit_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "capture": str(ctx.CAPTURE.relative_to(ctx.ROOT)),
        "plan": plan,
        "anchors": ctx.ANCHORS,
        "capture_sha256": data["hashes"],
        "sources_sha256": ctx.sources(),
        "historical_reports_sha256": ctx.historical_reports(),
        "tests": ctx.test_receipt(tests),
        "forbidden_imports": list(ctx.FORBIDDEN),
    }
    output.mkdir(parents=True, exist_ok=False)
    try:
        io.write(output / "registration.json", registration)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in registration["sources_sha256"]:
                archive.write(ctx.ROOT / name, arcname=name)
        authenticate(output)
    except BaseException:
        io.write(
            output / "registration-failure.json",
            {
                "status": "registration_failed_not_launched",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    return registration


def alarm(_signum, _frame):
    raise TimeoutError("Registered coupled-pilot audit deadline exceeded")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        plan = c.read(ctx.PLAN)
        ctx.validate_plan(plan)
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, plan["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (plan["max_file_bytes"],) * 2)
        with ctx.model_fence():
            registration = authenticate(output)
            c.require(
                sorted(os.sched_getaffinity(0)) == plan["cpu_affinity"], "Wrong audit CPU affinity"
            )
            io.write(
                output / "started.json",
                {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
            )
            data = ctx.load_capture()
            from feedback_audit_replay import Audit

            stage = "independent_state_checkpoint_preparation"
            audit = Audit(data, output)
            stage = "frozen_and_independent_reconstruction"
            result = audit.run()
            status = "pass" if result["independent_column_mismatches"] == 0 else "fail"
            io.write(
                output / "audit.json",
                result
                | {
                    "status": status,
                    "model_imports": [],
                    "simulators_rerun": False,
                    "reference_integrator_rerun": False,
                },
            )
            c.require(status == "pass", "Independent identity reconstruction rejected")
            stage = "final_authentication"
            authenticate(output)
            checked = ctx.load_capture()
            c.require(checked["hashes"] == data["hashes"], "Pilot changed during audit")
            used = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
            c.require(used + 131072 < plan["max_artifact_bytes"], "Audit artifact limit")
            elapsed = time.monotonic() - began
            c.require(elapsed < plan["total_timeout_seconds"], "Audit total deadline")
            summary = {k: v for k, v in result.items() if k not in ("groups", "refinements")}
            io.write(
                output / "completion.json",
                summary
                | {
                    "schema": "cells.betse_channel_feedback_closeout@1",
                    "status": "coupled_feedback_pilot_audit_closed",
                    "finished_utc": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": elapsed,
                    "registration_sha256": c.sha(output / "registration.json"),
                    "capture_completion_sha256": ctx.ANCHORS["completion.json"],
                    "files_sha256": {
                        name: digest
                        for name, digest in ctx.packet_hashes(output).items()
                        if name not in ctx.OPERATIONAL
                    },
                    "artifact_bytes_before_receipt": used,
                    "scope": plan["scope"],
                    "tests": registration["tests"],
                    "provenance": data["provenance"],
                    "capture_files_unchanged": 284,
                    "capture_source_inputs_unchanged": 112,
                    "accepted_implementation_files_unchanged": 352,
                    "production_modules_unchanged": 51,
                    "coupled_trajectory_qualified": True,
                    "reference_solution_at_registered_samples_qualified": True,
                    "cells_checkpoint_replay_qualified": True,
                    "native_restart_replay_qualified": False,
                    "biology_validated": False,
                    "gpu_tested": False,
                    "model_imports": [],
                    "simulators_rerun": False,
                    "reference_integrator_rerun": False,
                    "production_changed": False,
                    "original_evidence_rewritten": False,
                    "automatic_retry": False,
                    "automatic_followup": False,
                },
            )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "audit_failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
                "automatic_followup": False,
                "simulators_rerun": False,
                "reference_integrator_rerun": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests):
    registration = register(output, tests)
    try:
        with (
            (output / "runner.stdout.log").open("x") as stdout,
            (output / "runner.stderr.log").open("x") as stderr,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ",".join(map(str, registration["plan"]["cpu_affinity"])),
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=ctx.ROOT,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
        receipt = {
            "status": "launched_detached",
            "pid": process.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": c.sha(output / "registration.json"),
            "resources": {
                k: registration["plan"][k]
                for k in (
                    "cpu_affinity",
                    "total_timeout_seconds",
                    "max_file_bytes",
                    "max_artifact_bytes",
                )
            },
            "simulators_rerun": False,
            "reference_integrator_rerun": False,
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
        }
        io.write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        io.write(
            output / "launch-failure.json",
            {
                "status": "launch_failed",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    launcher = sub.add_parser("launch")
    launcher.add_argument("output", type=Path)
    launcher.add_argument("--tests", type=Path, required=True)
    sub.add_parser("execute").add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), sort_keys=True))
    else:
        execute(args.output.resolve())
