"""Run/resume a bounded finite-material assembly experiment on CPU or GPU."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from cells.assembly.cli import output_path, utc
from cells.assembly.io import digest, runtime, write_json
from cells.assembly.spec import AssemblyError
from cells.assembly_pool.engine import run
from cells.assembly_pool.io import load_checkpoint, source_identity, write_checkpoint
from cells.assembly_pool.spec import load_spec, parse_spec
from cells.core.output_paths import configure_caches


def execute(output):
    began, last, payload_bytes = time.monotonic(), None, 0
    try:
        registration = json.loads((output / "registration.json").read_text())
        if (
            registration["sources_sha256"] != source_identity()
            or registration["runtime"] != runtime()
        ):
            raise AssemblyError("Registered finite-pool source/runtime mismatch")
        spec = parse_spec(registration["definition"])
        parent, state = registration["parent"], None
        if parent:
            saved, state, sha = load_checkpoint(parent["path"])
            if sha != parent["sha256"] or saved.fingerprint != spec.fingerprint:
                raise AssemblyError("Registered parent checkpoint changed")
        write_json(output / "started.json", {"pid": os.getpid(), "started_utc": utc()})

        def record(chunk, current, trace):
            nonlocal last, payload_bytes
            last = current
            if trace is not None:
                target = output / f"events-{chunk:07}.npz"
                np.savez_compressed(
                    target,
                    **dict(
                        zip(
                            ("time_s", "occupied", "bonds", "free", "event"),
                            (np.asarray(x) for x in trace),
                            strict=True,
                        )
                    ),
                )
                payload_bytes += target.stat().st_size
            write_json(
                output / "status.json",
                {
                    "status": "running",
                    "chunk": chunk,
                    "min_time_s": float(current.time_s.min()),
                    "committed_events": int(current.event_count.astype(np.int64).sum()),
                    "updated_utc": utc(),
                },
                replace=True,
            )
            if (
                payload_bytes > spec.max_output_bytes
                or time.monotonic() - began > spec.max_wall_seconds
            ):
                raise AssemblyError("Finite-pool output/wall budget exceeded")

        state, result = run(
            spec,
            backend=registration["backend"],
            device_index=registration["device_index"],
            until=registration["until_s"],
            state=state,
            callback=record,
        )
        checkpoint = write_checkpoint(
            output / "checkpoint",
            spec,
            state,
            execution={k: registration[k] for k in ("backend", "device_index")},
            provenance=parent,
        )
        if registration["sources_sha256"] != source_identity():
            raise AssemblyError("Finite-pool source changed during execution")
        if sum(p.stat().st_size for p in output.rglob("*.npz")) > spec.max_output_bytes:
            raise AssemblyError("Finite-pool final payload budget exceeded")
        result |= {
            "status": "completed",
            "elapsed_seconds": time.monotonic() - began,
            "finished_utc": utc(),
            "checkpoint_manifest_sha256": checkpoint,
        }
        write_json(output / "result.json", result)
        write_json(
            output / "completion.json",
            {
                "status": "completed",
                "result_sha256": digest(output / "result.json"),
                "registration_sha256": digest(output / "registration.json"),
                "payloads_sha256": {
                    str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*.npz"))
                },
                "finished_utc": utc(),
            },
        )
        write_json(
            output / "status.json", {"status": "completed", "updated_utc": utc()}, replace=True
        )
        return result
    except BaseException as exc:
        if last is not None:
            np.savez_compressed(output / "failure-state.npz", **last._asdict())
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "finished_utc": utc(),
                "elapsed_seconds": time.monotonic() - began,
            },
        )
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cells assembly-pool", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate").add_argument("input", type=Path)
    commands.add_parser("status").add_argument("output", type=Path)
    commands.add_parser("_worker", help=argparse.SUPPRESS).add_argument("output", type=Path)
    for name in ("run", "resume"):
        command = commands.add_parser(name)
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
        command.add_argument("--device-index", type=int, default=0)
        command.add_argument("--until", type=float)
        command.add_argument("--detach", action="store_true")
    args = parser.parse_args(argv)
    try:
        configure_caches()
        if args.command == "validate":
            spec = load_spec(args.input)
            result = {
                "status": "valid",
                "definition": spec.to_dict(),
                "working_bytes_estimate": spec.working_bytes,
                "output_bytes_bound": spec.output_bound,
            }
        elif args.command == "status":
            result = None
            for name in ("failure.json", "result.json", "status.json", "launch.json"):
                if (args.output / name).exists():
                    result = json.loads((args.output / name).read_text())
                    break
            if result is None:
                raise AssemblyError("No saved finite-pool status")
        elif args.command == "_worker":
            result = execute(args.output.resolve())
        else:
            parent, state = None, None
            if args.command == "run":
                spec = load_spec(args.input)
            else:
                spec, state, sha = load_checkpoint(args.input)
                parent = {"path": str(args.input.resolve()), "sha256": sha}
            until = spec.end_time_s if args.until is None else args.until
            start = 0.0 if state is None else float(state.time_s.max())
            if not np.isfinite(until) or not start < until <= 86400 or args.device_index < 0:
                raise AssemblyError(
                    "Require an advancing horizon <= 86400 s and nonnegative device index"
                )
            output = output_path(args.output)
            if shutil.disk_usage(output.parent).free < spec.max_output_bytes + 4 * 1024**3:
                raise AssemblyError("Finite-pool budget would consume the disk reserve")
            output.mkdir()
            registration = {
                "definition": spec.to_dict(),
                "backend": args.backend,
                "device_index": args.device_index,
                "until_s": until,
                "parent": parent,
                "sources_sha256": source_identity(),
                "runtime": runtime(),
                "created_utc": utc(),
                "qualification": "New kinetic hypothesis; no fit to measured mi3 kinetics",
            }
            write_json(output / "registration.json", registration)
            source = output / "source"
            shutil.copytree(
                Path(__file__).resolve().parents[1],
                source / "cells",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            if args.detach:
                environment = os.environ.copy()
                environment.update(
                    PYTHONPATH=str(source),
                    PYTHONDONTWRITEBYTECODE="1",
                    XLA_PYTHON_CLIENT_PREALLOCATE="false",
                )
                with (
                    (output / "stdout.log").open("x") as out,
                    (output / "stderr.log").open("x") as err,
                ):
                    child = subprocess.Popen(
                        [sys.executable, "-B", "-m", "cells.assembly_pool", "_worker", str(output)],
                        stdout=out,
                        stderr=err,
                        stdin=subprocess.DEVNULL,
                        env=environment,
                        start_new_session=True,
                        close_fds=True,
                    )
                result = {
                    "status": "launched",
                    "pid": child.pid,
                    "output": str(output),
                    "launched_utc": utc(),
                }
                write_json(output / "launch.json", result)
            else:
                result = execute(output)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (AssemblyError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Finite-pool assembly error: {exc}", file=sys.stderr)
        return 2
