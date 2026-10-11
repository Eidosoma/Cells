"""A bounded local finite-pool run using the public runner and existing GPU telemetry."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

from cells.assembly.cli import output_path, utc
from cells.assembly.io import digest, runtime, write_json
from cells.assembly_pool.io import source_identity
from cells.assembly_pool.spec import load_spec
from cells.core.output_paths import configure_caches
from cells.ensemble.telemetry import Monitor, devices, utilization


def sources():
    return {
        "pool": source_identity(),
        "runner": digest(__file__),
        "telemetry": digest(Path(sys.modules[Monitor.__module__].__file__)),
    }


def worker(output):
    registration = json.loads((output / "registration.json").read_text())
    monitor = None
    try:
        if registration["sources_sha256"] != sources() or registration["runtime"] != runtime():
            raise ValueError("Registered finite-pool measurement source/runtime mismatch")
        if registration["definition_sha256"] != digest(output / "definition.json"):
            raise ValueError("Registered finite-pool definition changed")
        gpu = registration["gpu"]
        monitor = Monitor(output / "gpu-telemetry.jsonl", [gpu["uuid"]])
        monitor.start()
        start = time.time()
        write_json(output / "started.json", {"pid": os.getpid(), "utc": utc(), "time": start})
        environment = os.environ.copy()
        environment["CUDA_VISIBLE_DEVICES"] = gpu["uuid"]
        environment["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
        with (
            (output / "run.stdout.log").open("x") as out,
            (output / "run.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "cells.assembly_pool",
                    "run",
                    str(output / "definition.json"),
                    "--backend",
                    "gpu",
                    "--device-index",
                    "0",
                    "--output",
                    str(output / "run"),
                ],
                stdout=out,
                stderr=err,
                stdin=subprocess.DEVNULL,
                env=environment,
                timeout=registration["max_wall_seconds"],
                check=True,
            )
        end = time.time()
        monitor.finish()
        monitor = None
        done = json.loads((output / "run/completion.json").read_text())
        if done["result_sha256"] != digest(output / "run/result.json"):
            raise ValueError("Finite-pool run result digest mismatch")
        result = json.loads((output / "run/result.json").read_text())
        if registration["sources_sha256"] != sources():
            raise ValueError("Finite-pool measurement source changed during execution")
        samples = [
            json.loads(line) for line in (output / "gpu-telemetry.jsonl").read_text().splitlines()
        ]
        hours = (end - start) / 3600
        result |= {
            "whole_job_seconds": end - start,
            "allocated_gpus": 1,
            "allocated_gpu_hours": hours,
            "worlds_per_allocated_gpu_hour": result["worlds"] / hours,
            "events_per_allocated_gpu_hour": result["committed_events"] / hours,
            "gpu_utilization": utilization(samples, [gpu["uuid"]], start, end, 70.0),
            "utilization_target_is_advisory": True,
            "scope": "One local L4 run; no multi-GPU scaling qualification or biological fit",
        }
        write_json(output / "result.json", result)
        write_json(
            output / "completion.json",
            {
                "status": "completed",
                "utc": utc(),
                "result_sha256": digest(output / "result.json"),
                "registration_sha256": digest(output / "registration.json"),
                "run_completion_sha256": digest(output / "run/completion.json"),
                "telemetry_sha256": digest(output / "gpu-telemetry.jsonl"),
            },
        )
    except BaseException as exc:
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "utc": utc(),
            },
        )
        raise
    finally:
        if monitor is not None:
            monitor.finish()


def main():
    configure_caches()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "_worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.command == "_worker":
        worker(output)
        return
    spec = load_spec(args.config)
    gpu = devices("0", 1)[0]
    output = output_path(output)
    if shutil.disk_usage(output.parent).free < spec.max_output_bytes + 4 * 1024**3:
        raise ValueError("Finite-pool measurement disk reserve")
    output.mkdir()
    write_json(output / "definition.json", spec.to_dict())
    write_json(
        output / "registration.json",
        {
            "sources_sha256": sources(),
            "runtime": runtime(),
            "gpu": gpu,
            "created_utc": utc(),
            "max_wall_seconds": spec.max_wall_seconds + 60,
            "definition_sha256": digest(output / "definition.json"),
            "allocated_gpus": 1,
        },
    )
    source = output / "source"
    shutil.copytree(
        Path(__file__).resolve().parents[2] / "src",
        source / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(__file__, source / "measure_pool.py")
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(source / "src"), PYTHONDONTWRITEBYTECODE="1")
    with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
        child = subprocess.Popen(
            [sys.executable, "-B", str(source / "measure_pool.py"), "_worker", str(output)],
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
            close_fds=True,
        )
    launch = {"pid": child.pid, "utc": utc(), "output": str(output)}
    write_json(output / "launch.json", launch)
    print(json.dumps(launch, indent=2))


if __name__ == "__main__":
    main()
