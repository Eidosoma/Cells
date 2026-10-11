"""One bounded detached saved-data audit; no numerical simulation commands."""

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

import transport_audit_context as ctx

c = ctx.c


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_transport_audit_registration@1",
        "Wrong audit registration",
    )
    ctx.validate_plan(r["plan"])
    c.require(r["model_imports_forbidden"] == list(ctx.FORBIDDEN), "Audit import boundary changed")
    c.require(
        r["capture"] == str(ctx.CAPTURE.relative_to(c.ROOT)) and r["anchors"] == ctx.ANCHORS,
        "Wrong audit capture",
    )
    c.require(
        r["capture_sha256"] == ctx.packet_hashes(ctx.CAPTURE),
        "Capture changed after audit registration",
    )
    c.require(r["sources_sha256"] == ctx.sources(), "Audit sources changed")
    c.require(
        ctx.test_receipt(c.ROOT / r["tests"]["path"]) == r["tests"],
        "Audit preflight evidence changed",
    )
    for name, digest in r["historical_reports_sha256"].items():
        c.require(c.sha(c.ROOT / name) == digest, "Historical handoff changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Audit capsule membership changed",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(name)).hexdigest() == digest
                for name, digest in r["sources_sha256"].items()
            ),
            "Audit capsule bytes changed",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists()
        and not output.is_relative_to(ctx.CAPTURE),
        "Use a fresh audit directory",
    )
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    with ctx.model_fence():
        data = ctx.load_capture()
    r = {
        "schema": "cells.betse_channel_transport_audit_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "capture": str(ctx.CAPTURE.relative_to(c.ROOT)),
        "anchors": ctx.ANCHORS,
        "capture_sha256": data["hashes"],
        "sources_sha256": ctx.sources(),
        "tests": ctx.test_receipt(tests),
        "historical_reports_sha256": {
            name: c.sha(c.ROOT / name)
            for name in (
                "reports/REF004B_RUNTIME_FIX_HANDOFF.md",
                "reports/REF004B_SETUP_FIX_HANDOFF.md",
                "reports/REF004B_TRANSPORT_PREFLIGHT_HANDOFF.md",
            )
        },
        "model_imports_forbidden": list(ctx.FORBIDDEN),
    }
    output.mkdir(parents=True, exist_ok=False)
    try:
        c.write(output / "registration.json", r)
        with zipfile.ZipFile(
            output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for name in r["sources_sha256"]:
                archive.write(c.ROOT / name, arcname=name)
        authenticate(output)
    except BaseException:
        c.write(
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
    raise TimeoutError("Registered saved-data audit deadline exceeded")


def execute(output):
    began = time.monotonic()
    try:
        plan = c.read(ctx.PLAN)
        ctx.validate_plan(plan)
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, plan["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (plan["max_file_bytes"],) * 2)
        with ctx.model_fence():
            r = authenticate(output)
            c.require(sorted(os.sched_getaffinity(0)) == plan["cpu_affinity"], "Wrong audit CPUs")
            c.write(
                output / "started.json",
                {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
            )
            data = ctx.load_capture()
            summary, rebuilt = ctx.numerical_audit(data)
            c.write(output / "independent-comparisons.json", rebuilt)
            c.write(
                output / "audit.json",
                summary
                | {
                    "status": "pass" if summary["failed_comparisons"] == 0 else "fail",
                    "frozen_comparisons_replayed": 37068,
                    "model_imports": [],
                    "simulators_rerun": False,
                },
            )
            c.require(
                summary["failed_comparisons"] == 0,
                "Independent reconstruction rejected; retain failures",
            )
            authenticate(output)
            checked = ctx.load_capture()
            c.require(checked["hashes"] == data["hashes"], "Capture changed during audit")
            used = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
            c.require(used + 65536 < plan["max_artifact_bytes"], "Audit artifact budget exceeded")
            payloads = {
                name: digest
                for name, digest in ctx.packet_hashes(output).items()
                if name not in ctx.OPERATIONAL
            }
            elapsed = time.monotonic() - began
            c.require(elapsed < plan["total_timeout_seconds"], "Audit deadline exceeded")
            c.write(
                output / "completion.json",
                {
                    "schema": "cells.betse_channel_transport_closeout@1",
                    "status": "single_transfer_audit_closed",
                    "finished_utc": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": elapsed,
                    "registration_sha256": c.sha(output / "registration.json"),
                    "capture_completion_sha256": ctx.ANCHORS["completion.json"],
                    "files_sha256": payloads,
                    "artifact_bytes_before_receipt": used,
                    "scope": plan["scope"],
                    "frozen_comparisons_replayed": 37068,
                    "independent_comparisons": summary["independent_comparisons"],
                    "failed_comparisons": 0,
                    "maximum_independent_scaled_error": summary["maximum_independent_scaled_error"],
                    "definition_contracts_checked": summary["definition_contracts_checked"],
                    "hidden_state_controls_checked": summary["hidden_state_controls_checked"],
                    "tests": r["tests"],
                    "capture_files_unchanged": len(data["hashes"]),
                    "capture_source_inputs_unchanged": len(data["registration"]["sources_sha256"]),
                    "accepted_implementation_files_unchanged": 352,
                    "production_modules_unchanged": 51,
                    "provenance": data["provenance"],
                    "native_preparations": 4,
                    "native_single_updates": 12,
                    "cells_matched_transfers_per_backend": 12,
                    "cells_backends": list(ctx.independent.BACKENDS),
                    "fixture_temperature_K": 298.15,
                    "single_transfer_qualified": True,
                    "coupled_trajectory_qualified": False,
                    "production_integrator_compared": False,
                    "biology_validated": False,
                    "gpu_tested": False,
                    "model_imports": [],
                    "simulators_rerun": False,
                    "original_evidence_rewritten": False,
                    "automatic_retry": False,
                    "automatic_followup": False,
                },
            )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        c.write(
            output / "failure.json",
            {
                "status": "audit_failed_not_qualified",
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
                "simulators_rerun": False,
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
                    ",".join(map(str, r["plan"]["cpu_affinity"])),
                    str(c.CELLS_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "execute",
                    str(output),
                ],
                cwd=c.ROOT,
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
            "total_timeout_seconds": r["plan"]["total_timeout_seconds"],
            "max_artifact_bytes": r["plan"]["max_artifact_bytes"],
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
            "simulators_rerun": False,
        }
        c.write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        c.write(
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
