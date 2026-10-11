"""Source-frozen response pilot: separate bounded workers, detached launch, no polling."""

import argparse
import hashlib
import json
import os
import resource
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import contact as c
import dispatch_preflight as files
import full_loop_bridge as budget
import held_response_check as check
import held_response_context as ctx
import held_response_native as native
import trajectory as runner
import trajectory_context as old
import trajectory_evidence as evidence

STAGES = ("native", "cells", "comparison")


def capsule(output, registered):
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) and set(names) == set(registered["sources"]),
            "Response capsule coverage differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == registered["sources"][n]
                for n in names
            ),
            "Response capsule content differs",
        )


def register(output):
    ctx.preservation_check()
    plan, prior = c.read(ctx.PLAN), evidence.trusted_registration()
    ctx.validate_plan(plan)
    registered = {
        "schema": "cells.betse_held_response_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "plan": plan,
        "native_rows": ctx.native_rows(plan),
        "cells_rows": ctx.cells_rows(plan),
        "cells_definitions": ctx.definitions(plan),
        "common_times_s": ctx.common_times(plan),
        "cells_export_shapes": ctx.export_shapes(),
        "sources": old.sources(),
        "upstream": c.inspect_source(),
        "prior_handoff_sha256": ctx.PRIOR_SHA,
        "prelaunch_sha256": c.sha(ctx.PRELAUNCH),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "criteria": prior["protocol"],
        **{k: prior[k] for k in ("base_protocol", "geometry", "settings", "cells_runtime")},
    }
    ctx.validate_registration(registered)
    c.require(
        output.is_relative_to(c.ROOT / "runs") and output != c.ROOT / "runs",
        "Use a fresh run subdirectory",
    )
    output.mkdir(parents=True, exist_ok=False)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    capsule(output, registered)
    return registered


def cells_worker(registered, output):
    results, metadata = {}, None
    (output / "cells-started").mkdir(exist_ok=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("error", RuntimeWarning)
        for index, row in enumerate(registered["cells_rows"]):
            identifier = row["id"]
            c.write(
                output / "cells-started" / f"{index:02d}.json",
                {"row": row, "started_utc": datetime.now(UTC).isoformat()},
            )
            # Narrow only the execution list passed to the unchanged exporter.
            # Its definition is the exact registered input, never fitted to BETSE output.
            subset = registered | {
                "cells_definitions": {identifier: registered["cells_definitions"][identifier]}
            }
            saved = runner.cells_worker(subset, output)
            current = {k: v for k, v in saved.items() if k != "results"}
            c.require(
                metadata is None or current == metadata, "Cells engine/runtime changed between rows"
            )
            metadata = current
            c.require(set(saved["results"]) == {identifier}, "Cells exporter coverage differs")
            results |= saved["results"]
            budget.check_budget(output, registered["plan"])
        c.require(not caught, "Cells response emitted Python warnings")
    c.require(len(results) == registered["plan"]["cells_runs"], "Incomplete Cells panel")
    return {
        "schema": "cells.betse_held_response_cells_worker@1",
        "status": "exported_pending_comparison",
        "results": results,
        "warnings": [],
        **metadata,
    }


def worker(stage, output):
    c.require(stage in STAGES, "Unknown response stage")
    started = time.monotonic()
    try:
        registered = c.read(output / "registration.json")
        ctx.validate_registration(registered)
        capsule(output, registered)
        c.require(sorted(os.sched_getaffinity(0)) == [0, 1, 2, 3], "Worker CPU affinity differs")
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (registered["plan"]["max_worker_file_bytes"],) * 2
        )
        result = {"native": native.worker, "cells": cells_worker, "comparison": check.run}[stage](
            registered, output
        )
        result |= {
            "registration_sha256": c.sha(output / "registration.json"),
            "sources": registered["sources"],
            "elapsed_seconds": time.monotonic() - started,
        }
        # Numerical failure is a durable comparison result, not a swallowed exception.
        c.write(output / (stage + ".json"), result)
    except BaseException:
        c.write(
            output / (stage + "-failure.json"),
            {
                "status": "failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "trajectory_qualified": False,
            },
        )
        raise


def environment(output):
    env = os.environ | {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(output / "matplotlib-cache"),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "JAX_ENABLE_X64": "1",
        "JAX_PLATFORMS": "cpu",
    }
    for name in ("PYTHONPATH", "JAX_DISABLE_JIT"):
        env.pop(name, None)
    return env


def stage_command(stage, output, plan):
    c.require(stage in STAGES, "Unknown response stage")
    interpreter = c.REFERENCE_PYTHON if stage == "native" else c.CELLS_PYTHON
    return [
        "taskset",
        "-c",
        plan["cpu_affinity"],
        str(interpreter),
        "-B",
        str(Path(__file__).resolve()),
        stage,
        str(output),
    ]


def execute(output):
    started, stage = time.monotonic(), "validation"
    try:
        registered = c.read(output / "registration.json")
        ctx.validate_registration(registered)
        capsule(output, registered)
        plan = registered["plan"]
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        for stage in STAGES:
            remaining = plan["total_timeout_seconds"] - (time.monotonic() - started)
            c.require(remaining > 0, "Response wall budget exhausted")
            with (output / (stage + ".log")).open("x") as log:
                subprocess.run(
                    stage_command(stage, output, plan),
                    cwd=c.ROOT,
                    env=environment(output),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=min(remaining, plan["stage_timeout_seconds"][stage]),
                    check=True,
                )
            budget.check_budget(output, plan)
        comparison = c.read(output / "comparison.json")
        c.require(
            comparison["status"] == "pass_pending_independent_audit"
            and comparison["failed_comparisons"] == 0,
            "Response comparison failed; preserve all results without retry or tolerance changes",
        )
        ctx.preservation_check()
        ctx.validate_registration(registered)
        capsule(output, registered)
        budget.check_budget(output, plan)
        c.require(
            time.monotonic() - started < plan["total_timeout_seconds"],
            "Response total wall budget exhausted",
        )
        c.write(
            output / "capture.json",
            {
                "schema": "cells.betse_held_response_capture@1",
                "status": "response_checks_pass_pending_independent_audit",
                "elapsed_seconds": time.monotonic() - started,
                "finished_utc": datetime.now(UTC).isoformat(),
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": files.manifest(output, budget.OPERATIONAL),
                "artifact_bytes_before_receipt": budget.artifact_bytes(output),
                "native_runs": 8,
                "cells_runs": 24,
                "observed_native_steps": 160,
                "trajectory_run": True,
                "trajectory_qualified": False,
                "native_convergence_qualified": False,
                "forcing_convergence_qualified": False,
                "independent_audit_run": False,
                "biology_validated": False,
                "gpu_tested": False,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "schema": "cells.betse_held_response_failure@1",
                "status": "failed_not_qualified",
                "stage": stage,
                "elapsed_seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
                "files_sha256": files.manifest(output, budget.OPERATIONAL),
                "trajectory_qualified": False,
                "automatic_retry": False,
                "automatic_expansion": False,
            },
        )
        raise


def launch(output):
    registered = register(output)
    with (
        (output / "runner.stdout.log").open("x") as out,
        (output / "runner.stderr.log").open("x") as err,
    ):
        process = subprocess.Popen(
            [
                "taskset",
                "-c",
                registered["plan"]["cpu_affinity"],
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
        "stage_timeout_seconds": registered["plan"]["stage_timeout_seconds"],
        "total_timeout_seconds": registered["plan"]["total_timeout_seconds"],
        "automatic_polling": False,
        "automatic_retry": False,
        "independent_audit": "await_user_instruction",
    }
    c.write(output / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "execute", *STAGES))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    destination = args.output.resolve()
    if args.command == "launch":
        launch(destination)
    elif args.command == "execute":
        execute(destination)
    else:
        worker(args.command, destination)
