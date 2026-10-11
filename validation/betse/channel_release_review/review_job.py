"""One detached saved-data review; never run a simulator or rewrite old evidence."""

import argparse
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

import review_context as ctx

c, io = ctx.c, ctx.io


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.is_relative_to(ctx.CAPTURE)
        and not output.exists(),
        "Use a fresh saved-review output directory",
    )
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    with ctx.model_fence():
        _, _, hashes = ctx.load_capture()
    r = {
        "schema": "cells.betse_channel_release_review_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "capture": str(ctx.CAPTURE.relative_to(ctx.ROOT)),
        "anchors": ctx.ANCHORS,
        "capture_sha256": hashes,
        "sources_sha256": ctx.sources(),
        "historical_reports_sha256": ctx.reports(),
        "tests": ctx.test_receipt(tests),
        "reduction_sources": ctx.reduction_sources(),
        "forbidden_imports": list(ctx.previous.audit.FORBIDDEN),
    }
    output.mkdir(parents=True, exist_ok=False)
    try:
        io.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(ctx.ROOT / name, arcname=name)
        ctx.authenticate(output)
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
    return r


def alarm(_signum, _frame):
    raise TimeoutError("Saved release-input review deadline exceeded")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        plan = c.read(ctx.PLAN)
        ctx.validate_plan(plan)
        budget = plan["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
        with ctx.model_fence():
            registration = ctx.authenticate(output)
            c.require(
                sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Review CPU affinity"
            )
            io.write(
                output / "started.json",
                {
                    "pid": os.getpid(),
                    "started_utc": datetime.now(UTC).isoformat(),
                },
            )
            original, native, hashes = ctx.load_capture()
            c.require(hashes == registration["capture_sha256"], "Capture changed before review")
            stage = "source_order_and_unchanged_physical_checks"
            from review_check import check

            compared = check(original, ctx.CAPTURE, native)
            means = compared.pop("zero_flux_mean_evidence")
            rejections = compared.pop("original_guard_rejections")
            io.write_compressed(output / "zero-flux-means.json.gz", means)
            io.write(output / "preserved-original-rejections.json", rejections)
            io.write(output / "comparison.json", compared)
            c.require(compared["status"] == "pass", "Saved input review comparisons rejected")
            c.require(
                len(means) == plan["zero_flux_mean_rows"], "Incomplete zero-flux mean coverage"
            )
            c.require(
                bool(rejections) and all(r["changed_fields"] == ["outside_mM"] for r in rejections),
                "Unexpected old guard rejection",
            )
            stage = "final_authentication"
            ctx.authenticate(output)
            c.require(ctx.load_capture()[2] == hashes, "Original capture changed during review")
            used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
            c.require(used + 131072 < budget["max_artifact_bytes"], "Review artifact cap")
            elapsed = time.monotonic() - began
            c.require(elapsed < budget["total_timeout_seconds"], "Review elapsed limit")
            io.write(
                output / "completion.json",
                compared
                | {
                    "schema": "cells.betse_channel_release_review@1",
                    "decision": "D103",
                    "status": "release_input_preflight_review_closed",
                    "finished_utc": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": elapsed,
                    "registration_sha256": c.sha(output / "registration.json"),
                    "files_sha256": {
                        n: h
                        for n, h in ctx.packet_hashes(output).items()
                        if n not in ctx.previous.audit.OPERATIONAL
                    },
                    "artifact_bytes_before_receipt": used,
                    "tests": registration["tests"],
                    "capture_files_unchanged": len(hashes),
                    "capture_source_inputs_unchanged": 165,
                    "original_guard_rejections_preserved": len(rejections),
                    "original_capture_status": "release_input_preflight_failed_not_qualified",
                    "native_input_single_update_scope_qualified": True,
                    "simulators_rerun": False,
                    "reference_integrator_rerun": False,
                    "captured_values_changed": False,
                    "physical_tolerances_changed": False,
                    "production_changed": False,
                    "original_receipt_rewritten": False,
                    "automatic_retry": False,
                    "automatic_followup": False,
                    "model_imports": [],
                    "scope": "Saved native input application and two single updates per phase; "
                    "exact source-order zero-flux remixing and unchanged physical budgets. "
                    "Not a full-loop timed input, 2 ms response, restart, biology or GPU result.",
                },
            )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "saved_input_review_failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "simulators_rerun": False,
                "automatic_retry": False,
                "automatic_followup": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def launch(output, tests):
    r = register(output, tests)
    try:
        with (
            (output / "runner.stdout.log").open("x") as stdout,
            (output / "runner.stderr.log").open("x") as stderr,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ",".join(map(str, r["plan"]["resources"]["cpu_affinity"])),
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
            "resources": r["plan"]["resources"],
            "simulators_rerun": False,
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
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("launch")
    start.add_argument("output", type=Path)
    start.add_argument("--tests", type=Path, required=True)
    run = sub.add_parser("execute")
    run.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), indent=2))
    else:
        execute(args.output.resolve())


if __name__ == "__main__":
    main()
