"""One detached reference-only job. No simulator command or automatic follow-up."""

import argparse
import importlib.abc
import json
import os
import platform
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

import piecewise_context as ctx

c, io = ctx.c, ctx.io
FORBIDDEN = {"cells", "betse", "jax", "jaxlib"}


class SimulatorFence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in FORBIDDEN:
            raise RuntimeError("Simulator import forbidden in reference worker: " + fullname)
        return None


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Use a fresh reference output directory",
    )
    plan = c.read(ctx.PLAN)
    ctx.validate_plan(plan)
    with ctx.model_fence():
        prerequisite = ctx.prerequisite()
    r = {
        "schema": "cells.betse_release_reference_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "prerequisite": prerequisite,
        "inputs": ctx.inputs(plan),
        "reference_runtime": ctx.feedback.reference_runtime(),
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
    c.require(
        Path(sys.executable) == ctx.feedback.REFERENCE_PYTHON
        and platform.python_version() == r["reference_runtime"]["python"]
        and c.environment()["packages"] == r["reference_runtime"]["packages"]
        and sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"],
        "Reference worker runtime",
    )
    numerical = {key: os.environ.get(key) for key in ("JAX_DISABLE_JIT", "XLA_FLAGS")}
    expected = ctx.design.view("a")["preparation_registration"]["cells_runtime"][
        "numerical_environment"
    ]
    c.require(numerical == expected, "Reference numerical environment differs")
    c.require(
        not any(n.split(".")[0] in FORBIDDEN for n in sys.modules), "Simulator already imported"
    )
    fence = SimulatorFence()
    sys.meta_path.insert(0, fence)
    began = time.monotonic()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            from piecewise_reference import worker as calculate

            result = calculate(r, output)
        io.write(
            output / "reference.json",
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
    except BaseException:
        io.write(
            output / "worker-failure.json",
            {
                "status": "reference_worker_failed",
                "traceback": traceback.format_exc(),
                "automatic_retry": False,
            },
        )
        raise
    finally:
        sys.meta_path.remove(fence)


def validate_worker(r, output):
    row = c.read(output / "reference.json")
    c.require(
        row["registration_sha256"] == c.sha(output / "registration.json")
        and row["warnings"] == []
        and row["simulator_imports"] == []
        and row["environment"]["executable"] == str(ctx.feedback.REFERENCE_PYTHON)
        and row["environment"]["python"] == r["reference_runtime"]["python"]
        and row["environment"]["packages"] == r["reference_runtime"]["packages"]
        and row["cpu_affinity"] == r["plan"]["resources"]["cpu_affinity"]
        and row["numerical_environment"]
        == ctx.design.view("a")["preparation_registration"]["cells_runtime"][
            "numerical_environment"
        ]
        and 0 < row["elapsed_seconds"] < r["plan"]["resources"]["worker_timeout_seconds"]
        and row["engine"] == "piecewise_decimal_rhs_scipy_dop853_radau"
        and row["rhs_precision_digits"] == 80
        and row["integration_precision"] == "float64",
        "Reference worker provenance, warning or time budget",
    )
    return row


def alarm(_signum, _frame):
    raise TimeoutError("Piecewise reference job deadline exceeded")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        budget = c.read(ctx.PLAN)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
        with ctx.model_fence():
            r = ctx.authenticate(output)
            c.require(
                sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Controller affinity"
            )
            io.write(
                output / "started.json",
                {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
            )
            environment = ctx.feedback.audit.preparation.old.ctx.worker_environment(
                ctx.design.view("a")["preparation_registration"], output
            )
            stage = "piecewise_reference_integration"
            with (output / "reference.log").open("x") as stream:
                subprocess.run(
                    [
                        str(ctx.feedback.REFERENCE_PYTHON),
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
                    timeout=budget["worker_timeout_seconds"],
                )
            aggregate = validate_worker(r, output)
            stage = "saved_reference_domain_convergence_controls_and_signal"
            from piecewise_check import check

            result = check(r, output, aggregate)
            io.write(output / "reference-gate.json", result)
            c.require(result["status"] == "pass", "Piecewise reference gate rejected")
            stage = "final_authentication"
            ctx.authenticate(output)
            hashes = ctx.packet_hashes(output)
            expected = (
                {
                    "registration.json",
                    "sources.zip",
                    "started.json",
                    "reference.log",
                    "reference.json",
                    "reference-gate.json",
                }
                | ctx.OPERATIONAL
                | set(aggregate["records"].values())
            )
            c.require(set(hashes) == expected, "Unexpected reference output membership")
            used = sum((output / name).stat().st_size for name in hashes)
            c.require(used + 131072 < budget["max_artifact_bytes"], "Reference artifact cap")
            elapsed = time.monotonic() - began
            c.require(elapsed < budget["total_timeout_seconds"], "Reference deadline")
            io.write(
                output / "completion.json",
                result
                | {
                    "schema": "cells.betse_release_reference_capture@1",
                    "decision": "D104",
                    "status": "piecewise_reference_pass_pending_review",
                    "finished_utc": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": elapsed,
                    "registration_sha256": c.sha(output / "registration.json"),
                    "files_sha256": {n: h for n, h in hashes.items() if n not in ctx.OPERATIONAL},
                    "artifact_bytes_before_receipt": used,
                    "tests": r["tests"],
                    "production_changed": False,
                    "old_evidence_rewritten": False,
                    "automatic_polling": False,
                    "automatic_retry": False,
                    "automatic_followup": False,
                    "scope": "Independent piecewise reference only. Saved evidence review "
                    "and native/Cells timed trajectory registration require "
                    "a later user instruction.",
                },
            )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "piecewise_reference_failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - began,
                "traceback": traceback.format_exc(),
                "simulator_execution_allowed": False,
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
            "simulator_execution_allowed": False,
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("launch")
    start.add_argument("output", type=Path)
    start.add_argument("--tests", type=Path, required=True)
    for action in ("execute", "worker"):
        sub.add_parser(action).add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), indent=2))
    else:
        {"execute": execute, "worker": worker}[args.action](args.output.resolve())
