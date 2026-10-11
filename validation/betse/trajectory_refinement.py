"""Detached v2 harness using the frozen v1 actual-model workers, without patching them."""

import argparse
import json
import os
import subprocess
import time
import traceback
import warnings
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import contact as c
import trajectory as frozen
import trajectory_context as original
import trajectory_failure as prior
import trajectory_refinement_context as ctx


def register(output):
    output.mkdir(parents=True, exist_ok=False)
    parent = ctx.authenticate()
    protocol = c.read(ctx.PROTOCOL)
    ctx.validate_protocol(protocol)
    upstream = c.inspect_source()
    c.require(upstream == parent["upstream"], "Pinned upstream source changed")
    registered = {
        name: parent[name]
        for name in (
            "base_protocol",
            "geometry",
            "settings",
            "cells_runtime",
            "cells_definitions",
            "upstream",
        )
    }
    registered |= {
        "schema": "cells.betse_trajectory_refinement_registration@1",
        "registered_utc": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "sources": original.sources(),
        "parent_registration_sha256": prior.ANCHORS["registration.json"],
        "failure_audit_sha256": c.sha(prior.AUDIT),
        "preservation_sha256": c.sha(ctx.PRESERVATION),
        "amendment": ctx.AMENDMENT,
        "overlap_requirement": (
            "All ordinary/final/trace fields of repeated native 25 us runs and all Cells "
            "history/readout arrays must reproduce v1 exactly; timings excluded"
        ),
    }
    ctx.validate_registration(registered)
    c.write(output / "registration.json", registered)
    with zipfile.ZipFile(output / "sources.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in registered["sources"]:
            archive.write(c.HERE / name, arcname=name)
    return registered


def execute(output):
    started = time.monotonic()
    try:
        registered = c.read(output / "registration.json")
        ctx.validate_registration(registered)
        c.write(
            output / "started.json",
            {"pid": os.getpid(), "started_utc": datetime.now(UTC).isoformat()},
        )
        protocol = registered["protocol"]
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(output / "matplotlib-cache"),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "JAX_PLATFORMS": "cpu",
            "JAX_ENABLE_X64": "true",
        }
        env.pop("PYTHONPATH", None)
        worker_times = {}
        for kind, python in (("betse", c.REFERENCE_PYTHON), ("cells", c.CELLS_PYTHON)):
            remaining = protocol["total_timeout_seconds"] - (time.monotonic() - started)
            c.require(remaining > 0, "Panel wall budget exhausted")
            worker_started = time.monotonic()
            with (
                (output / f"{kind}.stdout.log").open("x") as out,
                (output / f"{kind}.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        "taskset",
                        "-c",
                        protocol["cpu_affinity"],
                        str(python),
                        "-B",
                        str(Path(__file__).resolve()),
                        "worker",
                        kind,
                        str(output),
                    ],
                    cwd=c.ROOT,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    timeout=min(remaining, protocol["worker_timeout_seconds"]),
                    check=True,
                )
            worker_times[kind] = time.monotonic() - worker_started
            c.require(
                sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
                < protocol["max_artifact_bytes"],
                "Artifact budget exhausted",
            )
        from trajectory_refinement_check import audit_data

        comparison = audit_data(registered, output)
        c.write(output / "comparison.json", comparison)
        c.require(
            comparison["status"] == "pass",
            "Refined trajectory comparison failed; retain full packet",
        )
        ctx.validate_registration(registered)
        preservation = ctx.preservation_check()
        c.require(
            time.monotonic() - started < protocol["total_timeout_seconds"],
            "Panel wall budget exhausted",
        )
        artifact_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        c.require(
            artifact_bytes < protocol["max_artifact_bytes"] - 65536, "Artifact budget exhausted"
        )
        payloads = {
            str(p.relative_to(output)): c.sha(p)
            for p in output.rglob("*")
            if p.is_file()
            and p.name not in ("runner.stdout.log", "runner.stderr.log", "launch.json")
        }
        c.write(
            output / "verification.json",
            {
                "schema": "cells.betse_trajectory_refinement_capture@1",
                "status": "pass",
                "seconds": time.monotonic() - started,
                "worker_seconds": worker_times,
                "finished_utc": datetime.now(UTC).isoformat(),
                "artifact_bytes_before_receipt": artifact_bytes,
                "registration_sha256": c.sha(output / "registration.json"),
                "files_sha256": payloads,
                "preservation": preservation,
                "trajectory_run": True,
                "biological_validation": False,
            },
        )
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "seconds": time.monotonic() - started,
                "traceback": traceback.format_exc(),
            },
        )
        raise


def launch(output):
    registered = register(output)
    try:
        with (
            (output / "runner.stdout.log").open("x") as out,
            (output / "runner.stderr.log").open("x") as err,
        ):
            process = subprocess.Popen(
                [
                    "taskset",
                    "-c",
                    registered["protocol"]["cpu_affinity"],
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
    except BaseException:
        c.write(
            output / "failure.json",
            {
                "status": "failed_not_qualified",
                "stage": "launch",
                "traceback": traceback.format_exc(),
            },
        )
        raise
    result = {
        "status": "launched_detached",
        "pid": process.pid,
        "launched_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": c.sha(output / "registration.json"),
    }
    c.write(output / "launch.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("launch", "execute"):
        sub.add_parser(action).add_argument("output", type=Path)
    worker = sub.add_parser("worker")
    worker.add_argument("kind", choices=("betse", "cells"))
    worker.add_argument("output", type=Path)
    preflight = sub.add_parser("prelaunch")
    preflight.add_argument("tests", type=Path)
    preflight.add_argument("expected_tests", type=int)
    preflight.add_argument("receipt", type=Path)
    args = parser.parse_args()
    if args.action == "prelaunch":
        print(json.dumps(ctx.prelaunch(args.tests, args.expected_tests, args.receipt)))
    elif args.action == "launch":
        launch(args.output.resolve())
    elif args.action == "execute":
        execute(args.output.resolve())
    else:
        output = args.output.resolve()
        registered = c.read(output / "registration.json")
        ctx.validate_registration(registered)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = (frozen.native_worker if args.kind == "betse" else frozen.cells_worker)(
                registered, output
            )
        result["warnings"] = [
            {"category": w.category.__name__, "message": str(w.message)} for w in caught
        ]
        result["registration_sha256"] = c.sha(output / "registration.json")
        c.write(output / f"{args.kind}.json", result)
