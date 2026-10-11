"""A registered-environment successor; numerical workers and strict identity stay frozen."""

import argparse
import hashlib
import json
import os
import resource
import signal
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import runtime_context as ctx
import startup_contract as startup_check

setup, previous_job = ctx.setup, ctx.previous_job
c, t = ctx.c, ctx.t
NEW_NAMES = (
    "amendment.json",
    "runtime_context.py",
    "runtime_job.py",
    "startup_contract.py",
    "test_transport_runtime_fix.py",
)


def source_hashes():
    names = (
        set(previous_job.source_hashes())
        | {f"validation/betse/channel_transport_runtime_fix/{name}" for name in NEW_NAMES}
        | {"docs/BETSE_CHANNEL_RUNTIME_FIX.md"}
    )
    return {name: c.sha(c.ROOT / name) for name in sorted(names)}


def software_receipt(path):
    receipt = setup.base_job.software_receipt(path)
    prefixes = (
        "channel_transport_preflight.test_transport::",
        "channel_transport_setup_fix.test_transport_setup_fix::",
        "channel_transport_runtime_fix.test_transport_runtime_fix::",
    )
    counts = [sum(prefix in name for name in receipt["identities"]) for prefix in prefixes]
    c.require(
        counts[:2] == [76, 31] and counts[2] >= 25 and sum(counts) == receipt["tests"],
        "Require original 107 tests and the runtime-correction regression suite",
    )
    return receipt | {"original_tests": 107, "new_tests": counts[2]}


def startup_contract(path, previous):
    c.require(
        path.is_dir() and path.is_relative_to(c.ROOT / "reports"),
        "Missing worker startup packet",
    )
    startup_check.validate_packet(path, previous)
    return {
        "path": str(path.relative_to(c.ROOT)),
        "files_sha256": setup.packet_hashes(path),
        "result_sha256": c.sha(path / "result.json"),
        "probes": len(startup_check.MODES),
        "transport_executed": False,
    }


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_transport_preflight_registration@3", "Wrong stage"
    )
    ctx.validate_amendment(r["runtime_amendment"])
    previous = ctx.authenticate_preservation()
    added = {"runtime_amendment", "runtime_failure_preservation_sha256", "startup_contract"}
    c.require(set(r) == set(previous) | added, "Registration membership changed")
    for key in previous:
        if key not in {"schema", "registered_utc", "sources_sha256", "software_preflight"}:
            c.require(r[key] == previous[key], f"Unapproved scientific/provenance change: {key}")
    c.require(
        r["runtime_failure_preservation_sha256"] == c.sha(ctx.PRESERVED),
        "Runtime failure preservation changed",
    )
    c.require(r["sources_sha256"] == source_hashes(), "Runtime-correction sources changed")
    c.require(
        software_receipt(c.ROOT / r["software_preflight"]["path"]) == r["software_preflight"],
        "Runtime-correction test receipt changed",
    )
    c.require(
        startup_contract(c.ROOT / r["startup_contract"]["path"], previous) == r["startup_contract"],
        "Real worker startup evidence changed",
    )
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Runtime-correction capsule membership changed",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(name)).hexdigest() == digest
                for name, digest in r["sources_sha256"].items()
            ),
            "Runtime-correction capsule bytes changed",
        )
    return r


def validate_workers(r, native, cells, output):
    previous_job.validate_workers(r, native, cells, output)
    for result in (native, cells):
        c.require(
            result["runtime_amendment_sha256"] == c.sha(ctx.AMENDMENT),
            "Wrong runtime amendment",
        )
        c.require(
            result["numerical_environment"] == r["cells_runtime"]["numerical_environment"],
            "Worker environment differs from registration",
        )


def worker(kind, output):
    r = authenticate(output)
    cap = r["protocol"]["resources"]["max_worker_file_bytes"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (cap, cap))
    from native_setup_fix import native_worker
    from transport_workers import cells_worker

    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = native_worker(r, output) if kind == "betse" else cells_worker(r, output)
    result.update(
        {
            "warnings": [
                {"category": w.category.__name__, "message": str(w.message)} for w in caught
            ],
            "registration_sha256": c.sha(output / "registration.json"),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "elapsed_seconds": time.monotonic() - began,
        }
    )
    result["configuration_amendment_sha256"] = c.sha(setup.AMENDMENT)
    result["runtime_amendment_sha256"] = c.sha(ctx.AMENDMENT)
    result["numerical_environment"] = {name: os.environ.get(name) for name in ctx.NUMERICAL_NAMES}
    c.write(output / f"{kind}.json", result)


def alarm(_signum, _frame):
    raise TimeoutError("Registered overall wall-clock budget exceeded")


def execute(output):
    began = time.monotonic()
    try:
        budget = c.read(t.PROTOCOL)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_worker_file_bytes"],) * 2)
        r = authenticate(output)
        c.require(c.inspect_source() == r["upstream"], "Native source changed")
        c.write(
            output / "started.json",
            {"started_utc": datetime.now(UTC).isoformat(), "pid": os.getpid()},
        )
        env = ctx.worker_environment(r, output)
        for kind, interpreter in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "No remaining worker budget")
            with (output / f"{kind}.log").open("x") as log:
                subprocess.run(
                    [
                        str(interpreter),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        kind,
                        str(output),
                    ],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=min(remaining, budget["worker_timeout_seconds"][kind]),
                )
        native, cells = c.read(output / "betse.json"), c.read(output / "cells.json")
        validate_workers(r, native, cells, output)
        from transport_check import evaluate

        comparison = evaluate(r, native, cells)
        c.write(output / "comparison.json", comparison)
        c.require(comparison["status"] == "pass", "Transport comparison rejected; retain failures")
        authenticate(output)
        c.require(c.inspect_source() == r["upstream"], "Native source changed during execution")
        excluded = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
        payload = {
            str(p.relative_to(output)): c.sha(p)
            for p in output.rglob("*")
            if p.is_file() and str(p.relative_to(output)) not in excluded
        }
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used + 65536 < budget["max_artifact_bytes"], "Artifact budget exceeded")
        c.write(
            output / "completion.json",
            {
                "schema": "cells.betse_channel_transport_preflight_capture@3",
                "configuration_amendment": r["configuration_amendment"],
                "runtime_amendment": r["runtime_amendment"],
                "runtime_failure_preservation_sha256": r["runtime_failure_preservation_sha256"],
                "failure_preservation_sha256": r["failure_preservation_sha256"],
                "status": "capture_pass_pending_audit",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "files_sha256": payload,
                "comparison_count": comparison["comparison_count"],
                "failed_comparisons": 0,
                "native_preparations": 4,
                "native_single_updates": 12,
                "cells_matched_transfers_per_backend": 12,
                "artifact_bytes_before_receipt": used,
                "independent_audit_complete": False,
                "coupled_trajectory_qualified": False,
                "biology_validated": False,
                "gpu_tested": False,
                "production_changed": False,
                "automatic_retry": False,
                "automatic_followup": False,
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def register(output, preflight, startup):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use a fresh run directory",
    )
    previous = ctx.authenticate_preservation()
    amendment = c.read(ctx.AMENDMENT)
    ctx.validate_amendment(amendment)
    c.require(c.inspect_source() == previous["upstream"], "Native checkout changed")
    r = previous | {
        "schema": "cells.betse_channel_transport_preflight_registration@3",
        "registered_utc": datetime.now(UTC).isoformat(),
        "runtime_amendment": amendment,
        "runtime_failure_preservation_sha256": c.sha(ctx.PRESERVED),
        "sources_sha256": source_hashes(),
        "software_preflight": software_receipt(preflight),
        "startup_contract": startup_contract(startup, previous),
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


def launch(output, preflight, startup):
    r = register(output, preflight, startup)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    ",".join(map(str, r["protocol"]["resources"]["cpu_affinity"])),
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
        receipt = {
            "status": "launched_detached",
            "pid": process.pid,
            "launched_utc": datetime.now(UTC).isoformat(),
            "registration_sha256": c.sha(output / "registration.json"),
            "resources": r["protocol"]["resources"],
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
        }
        c.write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        c.write(
            output / "launch-failure.json",
            {"status": "launch_failed", "traceback": traceback.format_exc()},
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("preserve")
    launcher = sub.add_parser("launch")
    launcher.add_argument("output", type=Path)
    launcher.add_argument("--preflight", type=Path, required=True)
    launcher.add_argument("--startup", type=Path, required=True)
    sub.add_parser("execute").add_argument("output", type=Path)
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "preserve":
        print(json.dumps(ctx.preserve(), sort_keys=True))
    elif args.action == "launch":
        print(
            json.dumps(
                launch(args.output.resolve(), args.preflight.resolve(), args.startup.resolve()),
                sort_keys=True,
            )
        )
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())
