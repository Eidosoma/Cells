"""Bounded matched CPU/L4 engineering check; not a biological-data comparison."""

import argparse
import json
import shutil
import time
import traceback
from pathlib import Path

import numpy as np

from cells.assembly.cli import output_path, utc
from cells.assembly.engine import run
from cells.assembly.graph import OPEN_CHAIN, RING
from cells.assembly.io import (
    digest,
    load_checkpoint,
    runtime,
    source_identity,
    write_checkpoint,
    write_json,
)
from cells.assembly.spec import parse_spec


def check(output, worlds=16):
    output = output_path(output)
    output.mkdir()
    start = time.monotonic()
    sources = source_identity()
    shutil.copytree(
        Path(__file__).resolve().parents[2] / "src/cells",
        output / "source/cells",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    write_json(
        output / "registration.json",
        {
            "created_utc": utc(),
            "sources_sha256": sources,
            "runtime": runtime(),
            "runner_sha256": digest(__file__),
            "worlds_per_case": worlds,
            "horizon_s": 30.0,
            "free_trimer_M": 115e-9,
            "clock_atol_s": 2e-10,
            "clock_rtol": 2e-12,
            "scope": "CPU/GPU implementation comparison; no experimental fit or scaling claim",
        },
    )
    results = []
    try:
        for name, nodes in (("pentamer", RING), ("open_chain", OPEN_CHAIN), ("single", (10,))):
            case = output / name
            case.mkdir()
            spec = parse_spec(
                {
                    "initial_nodes": list(nodes),
                    "worlds": worlds,
                    "end_time_s": 30.0,
                    "free_trimer_M": 115e-9,
                    "event_chunk_size": 64,
                    "max_events_per_world": 10000,
                    "max_wall_seconds": 45.0,
                }
            )
            write_json(case / "definition.json", spec.to_dict())
            states, reports = {}, {}
            for backend in ("cpu", "gpu"):
                states[backend], reports[backend] = run(spec, backend=backend)
                write_checkpoint(case / backend, spec, states[backend], execution=reports[backend])
                write_json(case / f"{backend}.json", reports[backend])
            differences = {}
            for field in states["cpu"]._fields:
                expected, actual = getattr(states["cpu"], field), getattr(states["gpu"], field)
                if expected.dtype.kind == "f":
                    np.testing.assert_allclose(
                        actual, expected, atol=2e-10, rtol=2e-12, err_msg=field
                    )
                    finite = np.isfinite(expected) & np.isfinite(actual)
                    differences[field] = float(
                        np.max(abs(actual[finite] - expected[finite]), initial=0.0)
                    )
                else:
                    np.testing.assert_array_equal(actual, expected, err_msg=field)
            early, _ = run(spec, backend="gpu", until=0.013)
            write_checkpoint(case / "gpu-intermediate", spec, early, execution={"backend": "gpu"})
            saved_spec, restored, _ = load_checkpoint(case / "gpu-intermediate")
            resumed, _ = run(saved_spec, backend="gpu", state=restored)
            for field in resumed._fields:
                np.testing.assert_array_equal(
                    getattr(resumed, field),
                    getattr(states["gpu"], field),
                    err_msg=f"saved GPU restart: {field}",
                )
            result = {
                "case": name,
                "cpu": reports["cpu"],
                "gpu": reports["gpu"],
                "max_absolute_errors": differences,
                "saved_gpu_restart_exact": True,
            }
            write_json(case / "comparison.json", result)
            results.append(result)
            print(json.dumps({"case": name, "status": "pass", "gpu": reports["gpu"]}), flush=True)
            if time.monotonic() - start > 90:
                raise RuntimeError("Short comparison exceeded its 90-second total budget")
        if source_identity() != sources:
            raise RuntimeError("Assembly source changed during the check")
        completion = {
            "status": "passed",
            "elapsed_seconds": time.monotonic() - start,
            "finished_utc": utc(),
            "cases": results,
            "registration_sha256": digest(output / "registration.json"),
            "payloads_sha256": {
                str(p.relative_to(output)): digest(p)
                for p in sorted(output.rglob("*"))
                if p.is_file()
            },
        }
        write_json(output / "completion.json", completion)
        print(
            json.dumps({"status": "passed", "elapsed_seconds": completion["elapsed_seconds"]}),
            flush=True,
        )
    except BaseException as exc:
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.monotonic() - start,
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worlds", type=int, default=16)
    args = parser.parse_args()
    check(args.output, args.worlds)
