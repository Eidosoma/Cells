"""Register one bounded preparation/readiness capture, detach, and do not poll."""

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

import loop_context as ctx

c = ctx.c


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_loop_preparation_registration@1", "Wrong registration"
    )
    ctx.validate_protocol(r["protocol"])
    c.require(r["prior_closeout"] == ctx.prior_closeout(), "Prior evidence changed")
    previous = ctx.old.authenticate(ctx.audit.CAPTURE)
    for key in ("base_protocol", "expected_geometry", "upstream", "cells_runtime"):
        c.require(r[key] == previous[key], "Changed prior mapping/runtime: " + key)
    c.require(r["transport_protocol"] == previous["protocol"], "Transport laws/tolerances changed")
    c.require(r["sources_sha256"] == ctx.sources(), "Registered sources changed")
    c.require(r["tests"] == ctx.test_receipt(c.ROOT / r["tests"]["path"]), "Test evidence changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Source capsule membership changed",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Source capsule bytes changed",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(c.ROOT / "runs")
        and output != c.ROOT / "runs"
        and not output.exists(),
        "Use a fresh single-use capture directory",
    )
    protocol = c.read(ctx.PROTOCOL)
    ctx.validate_protocol(protocol)
    prerequisite = ctx.prior_closeout()
    previous = ctx.old.authenticate(ctx.audit.CAPTURE)
    r = {
        "schema": "cells.betse_channel_loop_preparation_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "transport_protocol": previous["protocol"],
        "prior_closeout": prerequisite,
        "sources_sha256": ctx.sources(),
        "tests": ctx.test_receipt(tests),
    }
    r |= {
        key: previous[key]
        for key in ("base_protocol", "expected_geometry", "upstream", "cells_runtime")
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


def worker(kind, output):
    r = authenticate(output)
    budget = r["protocol"]["resources"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_worker_file_bytes"],) * 2)
    c.require(sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Wrong worker CPUs")
    numerical_env = {k: os.environ.get(k) for k in ctx.old.ctx.NUMERICAL_NAMES}
    c.require(
        numerical_env == r["cells_runtime"]["numerical_environment"], "Worker environment changed"
    )
    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if kind == "betse":
            from loop_native import worker as run
        else:
            from pilot_readiness import worker as run
        result = run(r, output)
    result |= {
        "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in caught],
        "elapsed_seconds": time.monotonic() - began,
        "registration_sha256": c.sha(output / "registration.json"),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "numerical_environment": numerical_env,
    }
    c.write(output / f"{kind}.json", result)


def validate_worker(r, output, kind):
    result = c.read(output / f"{kind}.json")
    c.require(
        result["registration_sha256"] == c.sha(output / "registration.json")
        and result["warnings"] == []
        and result["cpu_affinity"] == r["protocol"]["resources"]["cpu_affinity"]
        and result["numerical_environment"] == r["cells_runtime"]["numerical_environment"],
        "Worker provenance/warnings differ",
    )
    c.require(
        0 < result["elapsed_seconds"] < r["protocol"]["resources"]["worker_timeout_seconds"][kind],
        "Worker duration outside limit",
    )
    if kind == "betse":
        expected = {
            k: h
            for k, h in r["upstream"]["files_sha256"].items()
            if k.startswith("betse/") and k.endswith(".py")
        }
        c.require(
            result["installed_python_sha256"] == expected
            and result["environment"]["packages"] == c.locked_reference_packages()
            and Path(result["environment"]["executable"]) == c.REFERENCE_PYTHON,
            "Native source/runtime mismatch",
        )
        for key, row in result["rows"].items():
            directory = output / "native" / key
            c.require(c.read(directory / "result.json") == row, "Native aggregate/partial mismatch")
            for name, field in (
                ("core.json", "core_initial"),
                ("fixture.json", "fixture"),
                ("geometry.json", "geometry"),
            ):
                c.require(
                    c.read(directory / name) == row[field], "Native preparation partial mismatch"
                )
            c.require((directory / row["native_pickle"]).is_file(), "Native restart missing")
    else:
        c.require(
            result["accepted_runtime"] == r["cells_runtime"]
            and result["cells_trajectory_runs"] == 0
            and len(result["records"]) == 12,
            "Wrong Cells readiness coverage/runtime",
        )
        c.require(
            all(
                row["integration_executed"] is False and row["convergence_qualified"] is False
                for row in result["records"]
            ),
            "Readiness overclaims execution",
        )
    return result


def alarm(_signum, _frame):
    raise TimeoutError("Registered preparation/readiness wall-clock cap exceeded")


def execute(output):
    began = time.monotonic()
    try:
        budget = c.read(ctx.PROTOCOL)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_worker_file_bytes"],) * 2)
        r = authenticate(output)
        c.require(
            sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Wrong controller CPUs"
        )
        c.write(
            output / "started.json",
            {"started_utc": datetime.now(UTC).isoformat(), "pid": os.getpid()},
        )
        env = ctx.old.ctx.worker_environment(r, output)
        comparison = None
        for kind, interpreter in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "No remaining execution budget")
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
            result = validate_worker(r, output, kind)
            if kind == "betse":
                from loop_check import evaluate

                comparison = evaluate(r, result)
                c.write(output / "loop-comparisons.json", comparison)
                c.require(
                    comparison["status"] == "pass",
                    "Native lifecycle checks failed; retain evidence",
                )
            else:
                c.require(
                    result["status"] == "readiness_pass" and result["failed_comparisons"] == 0,
                    "Cells readiness rejected; retain evidence",
                )
        authenticate(output)
        used = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        c.require(
            used + 65536 < budget["max_artifact_bytes"], "Preparation artifact budget exhausted"
        )
        files = {
            n: h
            for n, h in ctx.audit.packet_hashes(output).items()
            if n not in ctx.audit.OPERATIONAL
        }
        c.write(
            output / "completion.json",
            {
                "schema": "cells.betse_channel_loop_preparation_capture@1",
                "status": "preparation_readiness_pass_pending_audit",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "registration_sha256": c.sha(output / "registration.json"),
                "prior_completion_sha256": ctx.PRIOR_SHA,
                "files_sha256": files,
                "artifact_bytes_before_receipt": used,
                "native_runs": 8,
                "native_updates": 64,
                "observed_steps": comparison["observed_steps"],
                "observer_pairs_checked": 4,
                "loop_comparisons": comparison["comparison_count"],
                "failed_comparisons": 0,
                "candidate_definitions_checked": 12,
                "initial_rate_comparisons": len(result["comparisons"]),
                "tests": r["tests"],
                "cells_trajectory_runs": 0,
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
                    ",".join(map(str, r["protocol"]["resources"]["cpu_affinity"])),
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
    launcher = sub.add_parser("launch")
    launcher.add_argument("output", type=Path)
    launcher.add_argument("--tests", type=Path, required=True)
    sub.add_parser("execute").add_argument("output", type=Path)
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), sort_keys=True))
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())
