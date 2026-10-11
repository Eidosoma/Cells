"""Single-use detached native preflight, with durable failures and no follow-up."""

import argparse
import importlib
import json
import os
import resource
import signal
import subprocess
import sys
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import release_context as ctx

c, io = ctx.c, ctx.io
environment_of = importlib.import_module("runtime_context").worker_environment


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Use a fresh preflight output directory",
    )
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    prerequisite = ctx.design.prerequisite()
    r = {
        "schema": "cells.betse_channel_release_preflight_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "prerequisite": prerequisite,
        "design_evidence": ctx.design_evidence(),
        "data": ctx.data(),
        "sources_sha256": ctx.sources(),
        "historical_reports_sha256": ctx.reports(),
        "tests": ctx.test_receipt(tests),
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


def worker(output):
    r = ctx.authenticate(output)
    budget = r["plan"]["resources"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
    c.require(Path(sys.executable) == c.REFERENCE_PYTHON, "Wrong native interpreter")
    c.require(
        sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Wrong native CPU affinity"
    )
    numerical = {key: os.environ.get(key) for key in ("XLA_FLAGS", "JAX_DISABLE_JIT")}
    expected = r["data"]["a"]["preparation_registration"]["cells_runtime"]["numerical_environment"]
    c.require(numerical == expected, "Unregistered worker numerical environment")
    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import release_native

        result = release_native.worker(r, output)
    io.write(
        output / "betse.json",
        result
        | {
            "registration_sha256": c.sha(output / "registration.json"),
            "elapsed_seconds": time.monotonic() - began,
            "environment": c.environment(),
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "numerical_environment": numerical,
            "warnings": [
                {"category": w.category.__name__, "message": str(w.message)} for w in caught
            ],
        },
    )


def validate_worker(r, output):
    row = c.read(output / "betse.json")
    budget = r["plan"]["resources"]
    prep = r["data"]["a"]["preparation_registration"]
    c.require(
        row["registration_sha256"] == c.sha(output / "registration.json") and row["warnings"] == [],
        "Worker registration or warning failure",
    )
    c.require(
        row["environment"]["packages"] == c.locked_reference_packages()
        and Path(row["environment"]["executable"]) == c.REFERENCE_PYTHON,
        "Native worker environment differs",
    )
    c.require(
        row["cpu_affinity"] == budget["cpu_affinity"]
        and row["numerical_environment"] == prep["cells_runtime"]["numerical_environment"],
        "Native worker resource identity differs",
    )
    c.require(
        0 < row["elapsed_seconds"] < budget["worker_timeout_seconds"], "Native worker deadline"
    )
    c.require(
        row["installed_python_sha256"]
        == {
            n: h
            for n, h in prep["upstream"]["files_sha256"].items()
            if n.startswith("betse/") and n.endswith(".py")
        },
        "Native installed sources differ",
    )
    c.require(
        row["test_only_subset"] is False
        and row["full_simulator_loop_executed"] is False
        and row["release_response_qualified"] is False,
        "Worker scope differs",
    )
    return row


def alarm(signum, frame):
    raise TimeoutError("Release preflight deadline exceeded")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        budget = c.read(ctx.PLAN)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
        r = ctx.authenticate(output)
        c.require(
            sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Controller CPU affinity"
        )
        io.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        stage = "native_preparation_input_and_single_updates"
        io.write(output / "betse-started.json", {"started_utc": datetime.now(UTC).isoformat()})
        environment = environment_of(r["data"]["a"]["preparation_registration"], output)
        remaining = budget["total_timeout_seconds"] - (time.monotonic() - began) - 2
        c.require(remaining > 0, "No worker time remaining")
        with (output / "betse.log").open("x") as stream:
            subprocess.run(
                [
                    str(c.REFERENCE_PYTHON),
                    "-B",
                    str(Path(__file__).resolve()),
                    "worker",
                    str(output),
                ],
                cwd=ctx.ROOT,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=min(remaining, budget["worker_timeout_seconds"]),
            )
        native = validate_worker(r, output)
        print(
            "Native input applications and single updates completed; checking saved records",
            flush=True,
        )
        stage = "independent_boundary_comparison"
        with ctx.audit.model_fence():
            from release_check import check

            compared = check(r, output, native)
        io.write(output / "comparison.json", compared)
        c.require(compared["status"] == "pass", "Release native preflight comparisons rejected")
        stage = "final_authentication"
        ctx.authenticate(output)
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used + 1048576 < budget["max_artifact_bytes"], "Preflight artifact cap")
        elapsed = time.monotonic() - began
        c.require(elapsed < budget["total_timeout_seconds"], "Preflight total deadline")
        io.write(
            output / "completion.json",
            compared
            | {
                "schema": "cells.betse_channel_release_preflight@1",
                "status": "release_input_preflight_pass_pending_review",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": elapsed,
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": {
                    n: h
                    for n, h in ctx.audit.packet_hashes(output).items()
                    if n not in ctx.audit.OPERATIONAL
                },
                "artifact_bytes_before_receipt": used,
                "tests": r["tests"],
                "production_changed": False,
                "prior_evidence_rewritten": False,
                "automatic_retry": False,
                "automatic_followup": False,
                "scope": "Fresh native objects, parameter-only input prefixes and two single "
                "updates per phase. Query times are not simulated release times; "
                "not a 2 ms response, native restart, biology or GPU qualification.",
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "release_input_preflight_failed_not_qualified",
                "stage": stage,
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
            "automatic_polling": False,
            "automatic_retry": False,
            "automatic_followup": False,
        }
        io.write(output / "launch.json", receipt)
        return receipt
    except BaseException:
        io.write(
            output / "launch-failure.json",
            {"status": "launch_failed", "traceback": traceback.format_exc()},
        )
        raise


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("launch")
    start.add_argument("output", type=Path)
    start.add_argument("--tests", type=Path, required=True)
    for action in ("execute", "worker"):
        part = sub.add_parser(action)
        part.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), indent=2))
    else:
        (execute if args.action == "execute" else worker)(args.output.resolve())


if __name__ == "__main__":
    main()
