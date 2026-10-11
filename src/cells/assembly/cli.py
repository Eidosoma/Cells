"""Validate, run and resume the CPU/GPU stochastic assembly model."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from cells.assembly.engine import run
from cells.assembly.io import (
    digest,
    load_checkpoint,
    runtime,
    source_identity,
    write_checkpoint,
    write_json,
)
from cells.assembly.spec import AssemblyError, load_spec, parse_spec
from cells.core.output_paths import configure_caches, within_output_root


def utc():
    return datetime.now(timezone.utc).isoformat()


def parser():
    result = argparse.ArgumentParser(prog="cells assembly", description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate", help="validate model and resource bounds")
    check.add_argument("config", type=Path)
    for name in ("run", "resume"):
        command = commands.add_parser(name)
        command.add_argument("input", type=Path, help="definition JSON or complete checkpoint")
        command.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
        command.add_argument("--device-index", type=int, default=0)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--until", type=float)
        command.add_argument("--checkpoint-at", type=float, action="append", default=[])
        command.add_argument("--detach", action="store_true", help="freeze source and run detached")
    worker = commands.add_parser("_worker", help=argparse.SUPPRESS)
    worker.add_argument("output", type=Path)
    status = commands.add_parser("status", help="read saved status once")
    status.add_argument("output", type=Path)
    return result


def output_path(path):
    path = path.resolve()
    if not within_output_root(path):
        raise AssemblyError(
            "Generated assembly outputs must be under /mnt/workspaces or CELLS_OUTPUT_ROOT"
        )
    if path.exists():
        raise AssemblyError(f"Output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(path.parent).free < 4 * 1024**3:
        raise AssemblyError("Less than 4 GiB free disk reserve")
    return path


def execute(output):
    try:
        return _execute(output)
    except BaseException as exc:
        if not (output / "failure.json").exists():
            write_json(
                output / "failure.json",
                {
                    "status": "failed",
                    "error": str(exc),
                    "exception": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                    "finished_utc": utc(),
                },
            )
        raise


def _execute(output):
    began = time.monotonic()
    registration = json.loads((output / "registration.json").read_text())
    if registration["sources_sha256"] != source_identity() or registration["runtime"] != runtime():
        raise AssemblyError("Registered source/runtime does not match the worker")
    spec = parse_spec(registration["definition"])
    state = None
    parent = registration["parent"]
    if parent:
        parent_spec, state, parent_hash = load_checkpoint(parent["path"])
        if parent_hash != parent["sha256"] or parent_spec.fingerprint != spec.fingerprint:
            raise AssemblyError("Registered parent checkpoint changed")
    execution = {key: registration[key] for key in ("backend", "device_index")}
    write_json(output / "started.json", {"pid": os.getpid(), "started_utc": utc()})
    last = None
    parts = []
    bytes_written = 0
    try:
        for part, until in enumerate(registration["boundaries_s"]):

            def record(chunk, current, trace, *, part=part, until=until):
                nonlocal last, bytes_written
                last = current
                if trace is not None:
                    target = output / f"events-{part:03}-{chunk:07}.npz"
                    np.savez_compressed(
                        target,
                        time_s=np.asarray(trace[0]),
                        occupied=np.asarray(trace[1]),
                        event=np.asarray(trace[2]),
                    )
                    bytes_written += target.stat().st_size
                write_json(
                    output / "status.json",
                    {
                        "status": "running",
                        "part": part,
                        "chunk": chunk,
                        "min_time_s": float(current.time_s.min()),
                        "through_time_s": float(until),
                        "events": int(current.event_count.astype(np.int64).sum()),
                        "updated_utc": utc(),
                    },
                    replace=True,
                )
                if bytes_written > spec.max_output_bytes:
                    raise AssemblyError("Recorded event payload exceeds output budget")
                if time.monotonic() - began > spec.max_wall_seconds:
                    raise AssemblyError("Assembly wall-time budget exceeded")

            state, result = run(
                spec,
                backend=registration["backend"],
                device_index=registration["device_index"],
                state=state,
                until=until,
                callback=record,
            )
            parts.append(result)
            destination = output / (
                "checkpoint"
                if part == len(registration["boundaries_s"]) - 1
                else f"checkpoint-{part:03}"
            )
            write_checkpoint(destination, spec, state, execution=execution, provenance=parent)
        if source_identity() != registration["sources_sha256"]:
            raise AssemblyError("Assembly source changed during the run; frozen copy retained")
        result = parts[-1] | {
            "status": "completed",
            "finished_utc": utc(),
            "parts": parts,
            "elapsed_seconds": time.monotonic() - began,
            "registration_sha256": digest(output / "registration.json"),
            "checkpoint_manifest_sha256": digest(output / "checkpoint/manifest.json"),
        }
        write_json(output / "result.json", result)
        write_json(
            output / "completion.json",
            {
                "status": "completed",
                "finished_utc": utc(),
                "elapsed_seconds": time.monotonic() - began,
                "result_sha256": digest(output / "result.json"),
                "registration_sha256": digest(output / "registration.json"),
                "payloads_sha256": {
                    str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*.npz"))
                },
            },
        )
        write_json(
            output / "status.json", {"status": "completed", "updated_utc": utc()}, replace=True
        )
        return result
    except BaseException as exc:
        if last is not None:
            np.savez_compressed(output / "failure-state.npz", **last._asdict())
        failure = {
            "status": "failed",
            "error": str(exc),
            "exception": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "finished_utc": utc(),
            "elapsed_seconds": time.monotonic() - began,
        }
        write_json(output / "failure.json", failure)
        write_json(output / "status.json", failure, replace=True)
        raise


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        configure_caches()
        if args.command == "validate":
            spec = load_spec(args.config)
            result = {
                "status": "valid",
                "model": spec.model,
                "worlds": spec.worlds,
                "sha256": spec.fingerprint,
                "working_bytes_estimate": spec.working_bytes,
                "output_bytes_bound": spec.output_bound,
            }
        elif args.command == "status":
            for name in ("failure.json", "result.json", "status.json", "launch.json"):
                if (args.output / name).exists():
                    result = json.loads((args.output / name).read_text())
                    break
            else:
                raise AssemblyError("No saved assembly status")
        elif args.command == "_worker":
            result = execute(args.output)
        else:
            parent, state = None, None
            if args.command == "run":
                spec = load_spec(args.input)
            else:
                spec, state, fingerprint = load_checkpoint(args.input)
                parent = {"path": str(args.input.resolve()), "sha256": fingerprint}
            until = spec.end_time_s if args.until is None else args.until
            start = 0.0 if state is None else float(state.time_s.min())
            if not np.isfinite(until) or not start < until <= 86400:
                raise AssemblyError("Run horizon must advance the saved clock, within 86400 s")
            if any(not np.isfinite(t) or not start < t < until for t in args.checkpoint_at):
                raise AssemblyError(
                    "Intermediate checkpoint times must lie inside the run interval"
                )
            if args.device_index < 0:
                raise AssemblyError("Device index must be nonnegative")
            estimated = spec.output_bound + len(args.checkpoint_at) * (spec.worlds * 1024 + 65536)
            if estimated > spec.max_output_bytes:
                raise AssemblyError("Intermediate checkpoints exceed the declared output budget")
            output = output_path(args.output)
            output.mkdir()
            registration = {
                "created_utc": utc(),
                "definition": spec.to_dict(),
                "parent": parent,
                "backend": args.backend,
                "device_index": args.device_index,
                "boundaries_s": sorted(set(args.checkpoint_at)) + [until],
                "sources_sha256": source_identity(),
                "runtime": runtime(),
                "paper": "10.1038/s41586-026-10948-z, Supplementary Note 7",
                "qualification": "Implementation experiment; no experimental-data fit",
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
                environment["PYTHONPATH"] = str(source)
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                environment["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
                with (
                    (output / "stdout.log").open("x") as stdout,
                    (output / "stderr.log").open("x") as stderr,
                ):
                    child = subprocess.Popen(
                        [sys.executable, "-B", "-m", "cells.assembly", "_worker", str(output)],
                        stdin=subprocess.DEVNULL,
                        stdout=stdout,
                        stderr=stderr,
                        env=environment,
                        start_new_session=True,
                        close_fds=True,
                    )
                result = {
                    "status": "launched",
                    "pid": child.pid,
                    "launched_utc": utc(),
                    "output": str(output),
                    "source": str(source),
                }
                write_json(output / "launch.json", result)
            else:
                result = execute(output)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (AssemblyError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"Assembly error: {exc}", file=sys.stderr)
        return 2
