"""Single-use detached preparation; durable results/failures and no polling."""

import argparse
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

import history_context as ctx

c, io = ctx.c, ctx.io


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Use a fresh history output directory",
    )
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    r = {
        "schema": "cells.betse_channel_history_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "prerequisite": ctx.prerequisite(),
        "data": ctx.data(plan),
        "sources_sha256": ctx.sources(),
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


def worker(kind, output):
    r = ctx.authenticate(output)
    plan, data = r["plan"], r["data"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (plan["resources"]["max_file_bytes"],) * 2)
    c.require(sorted(os.sched_getaffinity(0)) == plan["resources"]["cpu_affinity"], "Worker CPUs")
    numerical = {name: os.environ.get(name) for name in ("XLA_FLAGS", "JAX_DISABLE_JIT")}
    c.require(numerical == data["cells_runtime"]["numerical_environment"], "Worker numerical flags")
    expected_python = c.REFERENCE_PYTHON if kind == "betse" else c.CELLS_PYTHON
    c.require(Path(sys.executable) == expected_python, "Worker interpreter")
    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import history_workers

        result = (history_workers.native if kind == "betse" else history_workers.cells)(data, plan)
    io.write(
        output / f"{kind}.json",
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


def validate_worker(output, r, kind):
    row = c.read(output / f"{kind}.json")
    expected_python = c.REFERENCE_PYTHON if kind == "betse" else c.CELLS_PYTHON
    c.require(
        row["registration_sha256"] == c.sha(output / "registration.json")
        and row["warnings"] == []
        and Path(row["environment"]["executable"]) == expected_python
        and row["cpu_affinity"] == r["plan"]["resources"]["cpu_affinity"]
        and row["numerical_environment"] == r["data"]["cells_runtime"]["numerical_environment"]
        and 0 < row["elapsed_seconds"] < r["plan"]["resources"]["worker_timeout_seconds"],
        "Worker provenance, warning or resource failure",
    )
    if kind == "betse":
        c.require(
            row["installed_python_sha256"]
            == {
                n: h
                for n, h in r["data"]["upstream"]["files_sha256"].items()
                if n.startswith("betse/") and n.endswith(".py")
            }
            and row["environment"]["packages"] == c.locked_reference_packages(),
            "Native identity",
        )
        c.require(
            row["native_world_preparations"] == row["native_transport_updates"] == 0,
            "Unexpected native transport",
        )
    else:
        c.require(
            row["accepted_runtime"] == r["data"]["cells_runtime"]
            and row["cells_trajectory_runs"] == 0,
            "Cells identity or scope",
        )
    return row


def alarm(_signum, _frame):
    raise TimeoutError("History preparation deadline exceeded")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        budget = c.read(ctx.PLAN)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
        r = ctx.authenticate(output)
        c.require(sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Controller CPUs")
        io.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        environment = ctx.prior.pilot.audit.preparation.old.ctx.worker_environment(
            r["data"], output
        )
        results = {}
        for kind, interpreter in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            stage = kind
            remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "No remaining preparation budget")
            io.write(
                output / f"{kind}-started.json", {"started_utc": datetime.now(UTC).isoformat()}
            )
            with (output / f"{kind}.log").open("x") as stream:
                subprocess.run(
                    [
                        str(interpreter),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        kind,
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
            results[kind] = validate_worker(output, r, kind)
            print(f"Completed {kind} initial-history probes", flush=True)
        stage = "independent_comparison"
        with ctx.prior.model_fence():
            from history_check import check

            compared = check(r["data"], r["plan"], results["betse"], results["cells"])
        io.write(output / "comparison.json", compared)
        c.require(compared["status"] == "pass", "History preparation comparisons rejected")
        stage = "final_authentication"
        ctx.authenticate(output)
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(used + 131072 < budget["max_artifact_bytes"], "History artifact cap")
        elapsed = time.monotonic() - began
        c.require(elapsed < budget["total_timeout_seconds"], "History deadline")
        io.write(
            output / "completion.json",
            compared
            | {
                "status": "history_preflight_pass_pending_review",
                "schema": "cells.history_preflight@1",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": elapsed,
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": {
                    n: h
                    for n, h in ctx.prior.packet_hashes(output).items()
                    if n not in ctx.prior.OPERATIONAL
                },
                "artifact_bytes_before_receipt": used,
                "tests": r["tests"],
                "production_changed": False,
                "prior_evidence_rewritten": False,
                "automatic_followup": False,
                "automatic_retry": False,
                "scope": "Initial-state/RHS and isolated fresh native gate steps only; "
                "no new coupled trajectory.",
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "history_preflight_failed_not_qualified",
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
    start.add_argument("--tests", required=True, type=Path)
    run = sub.add_parser("execute")
    run.add_argument("output", type=Path)
    probe = sub.add_parser("worker")
    probe.add_argument("kind", choices=("betse", "cells"))
    probe.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), indent=2))
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())


if __name__ == "__main__":
    main()
