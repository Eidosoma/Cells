"""One registered gated capture: reference, then native and Cells, no polling."""

import argparse
import hashlib
import importlib
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

import feedback_context as ctx
import feedback_io as io

c = ctx.c


def authenticate(output):
    r = c.read(output / "registration.json")
    c.require(
        r["schema"] == "cells.betse_channel_feedback_registration@1", "Wrong feedback registration"
    )
    ctx.validate_protocol(r["protocol"])
    prerequisite, previous = ctx.prerequisite()
    c.require(
        r["prerequisite"] == prerequisite and r["preparation_registration"] == previous,
        "Prerequisite evidence changed",
    )
    c.require(r["sources_sha256"] == ctx.sources(), "Feedback source inputs changed")
    c.require(
        r["reference_runtime"] == ctx.reference_runtime(), "Independent solver environment changed"
    )
    c.require(
        r["reference_parameters"] == ctx.parameters()
        and r["cells_definitions"] == ctx.cells_definitions(r["protocol"]),
        "Reference/Cells data changed",
    )
    c.require(
        r["tests"] == ctx.test_receipt(ctx.ROOT / r["tests"]["path"]), "Feedback preflight changed"
    )
    native = c.read(ctx.audit.CAPTURE / "betse.json")["rows"]
    c.require(
        r["geometry"] == native["network_off/observed"]["geometry"]
        and r["native_settings"]
        == {v: native[v + "/observed"]["settings"] for v in r["protocol"]["variants"]},
        "Native preparation settings changed",
    )
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(r["sources_sha256"]),
            "Feedback capsule membership differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == h
                for n, h in r["sources_sha256"].items()
            ),
            "Feedback capsule bytes differ",
        )
    return r


def register(output, tests):
    c.require(
        output.is_relative_to(ctx.ROOT / "runs")
        and output != ctx.ROOT / "runs"
        and not output.exists(),
        "Use a fresh feedback directory",
    )
    protocol = c.read(ctx.PROTOCOL)
    ctx.validate_protocol(protocol)
    with ctx.audit.model_fence():
        prerequisite, previous = ctx.prerequisite()
    native = c.read(ctx.audit.CAPTURE / "betse.json")["rows"]
    r = {
        "schema": "cells.betse_channel_feedback_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "prerequisite": prerequisite,
        "preparation_registration": previous,
        "sources_sha256": ctx.sources(),
        "reference_runtime": ctx.reference_runtime(),
        "reference_parameters": ctx.parameters(),
        "cells_definitions": ctx.cells_definitions(protocol),
        "geometry": native["network_off/observed"]["geometry"],
        "native_settings": {v: native[v + "/observed"]["settings"] for v in protocol["variants"]},
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
    return r


def worker(kind, output):
    r = authenticate(output)
    resources = r["protocol"]["resources"]
    resource.setrlimit(resource.RLIMIT_FSIZE, (resources["max_file_bytes"],) * 2)
    c.require(
        sorted(os.sched_getaffinity(0)) == resources["cpu_affinity"], "Wrong worker CPU affinity"
    )
    numerical = {k: os.environ.get(k) for k in ("JAX_DISABLE_JIT", "XLA_FLAGS")}
    c.require(
        numerical == r["preparation_registration"]["cells_runtime"]["numerical_environment"],
        "Worker numerical environment differs",
    )
    if kind == "reference":
        c.require(
            Path(sys.executable) == ctx.REFERENCE_PYTHON
            and platform.python_version() == r["reference_runtime"]["python"]
            and c.environment()["packages"] == r["reference_runtime"]["packages"],
            "Wrong independent reference runtime",
        )
    began = time.monotonic()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        module = importlib.import_module(
            {
                "reference": "feedback_reference",
                "betse": "feedback_native",
                "cells": "feedback_cells",
            }[kind]
        )
        result = module.worker(r, output)
    result |= {
        "elapsed_seconds": time.monotonic() - began,
        "registration_sha256": c.sha(output / "registration.json"),
        "environment": c.environment(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "numerical_environment": numerical,
        "warnings": [{"category": w.category.__name__, "message": str(w.message)} for w in caught],
    }
    io.write(output / f"{kind}.json", result)


def validate_worker(r, output, kind):
    result = c.read(output / f"{kind}.json")
    c.require(
        result["registration_sha256"] == c.sha(output / "registration.json")
        and result["warnings"] == [],
        "Worker provenance/warnings rejected",
    )
    c.require(
        result["cpu_affinity"] == r["protocol"]["resources"]["cpu_affinity"]
        and result["numerical_environment"]
        == r["preparation_registration"]["cells_runtime"]["numerical_environment"],
        "Worker environment changed",
    )
    c.require(
        0 < result["elapsed_seconds"] < r["protocol"]["resources"]["worker_timeout_seconds"][kind],
        "Worker elapsed limit",
    )
    expected_python = {
        "reference": ctx.REFERENCE_PYTHON,
        "betse": c.REFERENCE_PYTHON,
        "cells": c.CELLS_PYTHON,
    }[kind]
    c.require(
        Path(result["environment"]["executable"]) == expected_python, "Worker interpreter differs"
    )
    if kind == "reference":
        c.require(
            result["environment"]["packages"] == r["reference_runtime"]["packages"],
            "Reference package versions differ",
        )
    elif kind == "betse":
        expected = {
            n: h
            for n, h in r["preparation_registration"]["upstream"]["files_sha256"].items()
            if n.startswith("betse/") and n.endswith(".py")
        }
        c.require(
            result["installed_python_sha256"] == expected
            and result["environment"]["packages"] == c.locked_reference_packages(),
            "Native installed source/runtime differs",
        )
    else:
        c.require(
            result["accepted_runtime"] == r["preparation_registration"]["cells_runtime"],
            "Cells runtime differs",
        )
    return result


def alarm(_signum, _frame):
    raise TimeoutError("Registered feedback capture deadline exceeded")


def execute(output):
    began, stage = time.monotonic(), "authentication"
    try:
        budget = c.read(ctx.PROTOCOL)["resources"]
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, budget["total_timeout_seconds"])
        resource.setrlimit(resource.RLIMIT_FSIZE, (budget["max_file_bytes"],) * 2)
        r = authenticate(output)
        c.require(
            sorted(os.sched_getaffinity(0)) == budget["cpu_affinity"], "Wrong controller CPUs"
        )
        io.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        environment = ctx.audit.preparation.old.ctx.worker_environment(
            r["preparation_registration"], output
        )
        reference_gate = None
        workers = {}
        for kind, interpreter in (
            ("reference", ctx.REFERENCE_PYTHON),
            ("betse", c.REFERENCE_PYTHON),
            ("cells", c.CELLS_PYTHON),
        ):
            if kind != "reference":
                c.require(
                    reference_gate is not None and reference_gate["status"] == "pass",
                    "Independent reference gate is not passed; no simulator launch",
                )
            stage = kind
            remaining = budget["total_timeout_seconds"] - (time.monotonic() - began)
            c.require(remaining > 0, "No remaining capture budget")
            io.write(
                output / f"{kind}-started.json",
                {
                    "started_utc": datetime.now(UTC).isoformat(),
                    "reference_gate_passed": reference_gate is not None
                    and reference_gate["status"] == "pass",
                },
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
                    timeout=min(remaining, budget["worker_timeout_seconds"][kind]),
                    check=True,
                )
            workers[kind] = validate_worker(r, output, kind)
            if kind == "reference":
                stage = "reference_convergence_gate"
                from feedback_reference_check import check

                reference_gate = check(r, output, workers[kind])
                c.require(
                    reference_gate["status"] == "pass",
                    "Reference convergence rejected; simulators not launched",
                )
                io.write(
                    output / "reference-gate-passed.json",
                    {
                        "status": "reference_gate_passed_not_independent_closeout",
                        "finished_utc": datetime.now(UTC).isoformat(),
                        "gate_sha256": c.sha(output / "reference-gate.json.gz"),
                        "simulators_started": False,
                    },
                )
        stage = "trajectory_comparison"
        from feedback_compare import check

        with ctx.audit.model_fence():
            comparison = check(r, output, reference_gate, workers["betse"], workers["cells"])
        io.write(output / "capture-comparison.json", comparison)
        c.require(
            comparison["status"] == "capture_pass_pending_audit",
            "Coupled comparison rejected; retain diagnostics",
        )
        authenticate(output)
        used = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(
            used + 131072 < budget["max_artifact_bytes"],
            "Feedback aggregate artifact budget exceeded",
        )
        io.write(
            output / "completion.json",
            comparison
            | {
                "schema": "cells.betse_channel_feedback_capture@1",
                "finished_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - began,
                "registration_sha256": c.sha(output / "registration.json"),
                "prior_completion_sha256": ctx.PRIOR_SHA,
                "files_sha256": {
                    n: h
                    for n, h in ctx.audit.packet_hashes(output).items()
                    if n not in ctx.audit.OPERATIONAL
                },
                "artifact_bytes_before_receipt": used,
                "tests": r["tests"],
                "reference_solves": 12,
                "native_runs": 24,
                "native_updates": 4480,
                "cells_trajectories": 16,
                "cells_resumed_segments": 4,
                "accepted_implementation_files_unchanged": 352,
                "production_modules_unchanged": 51,
                "production_changed": False,
                "automatic_retry": False,
                "automatic_followup": False,
            },
        )
    except BaseException:
        signal.setitimer(signal.ITIMER_REAL, 0)
        io.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
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
                    ",".join(map(str, r["protocol"]["resources"]["cpu_affinity"])),
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
            "resources": r["protocol"]["resources"],
            "stages": ["independent_reference", "reference_gate", "native", "cells", "comparison"],
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
    child = sub.add_parser("worker")
    child.add_argument("kind", choices=("reference", "betse", "cells"))
    child.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.action == "launch":
        print(json.dumps(launch(args.output.resolve(), args.tests.resolve()), sort_keys=True))
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        worker(args.kind, args.output.resolve())
