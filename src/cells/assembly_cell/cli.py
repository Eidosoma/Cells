"""Public bounded assembly-cell execution with complete checkpoints and detached logs."""

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
from cells.assembly_cell.io import (
    flatten,
    implementation,
    load_checkpoint,
    source_identity,
    write_checkpoint,
)
from cells.assembly_cell.spec import tick_at
from cells.core.output_paths import configure_caches


def execute(output, *, cluster=False):
    last, began = None, time.monotonic()
    try:
        engine, definitions = implementation(cluster)
        record = json.loads((output / "registration.json").read_text())
        if record["sources_sha256"] != source_identity() or record["runtime"] != runtime():
            raise AssemblyError("Registered coupled source/runtime changed")
        spec = definitions.parse_spec(record["definition"])
        state = None
        if record["parent"]:
            saved, state, sha = load_checkpoint(record["parent"]["path"], backend=record["backend"])
            if saved.fingerprint != spec.fingerprint or sha != record["parent"]["sha256"]:
                raise AssemblyError("Registered coupled parent changed")
        write_json(output / "started.json", {"pid": os.getpid(), "utc": utc()})
        observation_ticks = set()
        if cluster:
            observation_ticks = {
                tick_at(spec, t)
                for t in spec.ionic.experiment.observation_times
                if t <= record["until_s"]
            }
            (output / "observations").mkdir()
            initial = engine.initial_state(spec) if state is None else state
            if int(initial.tick[0]) in observation_ticks:
                write_json(
                    output / "observations" / f"tick-{int(initial.tick[0]):07d}.json",
                    engine.summary(spec, initial),
                )

        def progress(window, current):
            nonlocal last
            last = current
            write_json(
                output / "status.json",
                {
                    "status": "running",
                    "window": window,
                    "tick": int(current.tick[0]),
                    "through_time_s": float(current.pool.time_s.min()),
                    "events": int(current.pool.event_count.astype(np.uint64).sum()),
                    "utc": utc(),
                },
                replace=True,
            )
            if (
                cluster
                and int(current.tick[0]) in observation_ticks
                and not np.any(current.fault)
                and not np.any(current.pool.fault)
            ):
                write_json(
                    output / "observations" / f"tick-{int(current.tick[0]):07d}.json",
                    engine.summary(spec, current),
                )

        state, result = engine.run(
            spec,
            backend=record["backend"],
            device_index=record["device_index"],
            state=state,
            until=record["until_s"],
            callback=progress,
        )
        sha = write_checkpoint(
            output / "checkpoint",
            spec,
            state,
            backend=record["backend"],
            provenance=record["parent"],
        )
        if source_identity() != record["sources_sha256"]:
            raise AssemblyError("Coupled source changed during execution")
        payload_bytes = (output / "checkpoint/state.npz").stat().st_size
        if cluster:
            payload_bytes += sum(p.stat().st_size for p in (output / "observations").iterdir())
        if payload_bytes > spec.pool.max_output_bytes:
            raise AssemblyError("Coupled output budget exceeded")
        result.update(
            status="completed",
            checkpoint_manifest_sha256=sha,
            whole_job_seconds=time.monotonic() - began,
            finished_utc=utc(),
        )
        write_json(output / "result.json", result)
        write_json(
            output / "completion.json",
            {
                "status": "completed",
                "utc": utc(),
                "result_sha256": digest(output / "result.json"),
                "registration_sha256": digest(output / "registration.json"),
                "checkpoint_manifest_sha256": sha,
                "checkpoint_state_sha256": digest(output / "checkpoint/state.npz"),
                **(
                    {
                        "observations_sha256": {
                            p.name: digest(p) for p in sorted((output / "observations").iterdir())
                        }
                    }
                    if cluster
                    else {}
                ),
            },
        )
        return result
    except BaseException as exc:
        if last is not None:
            np.savez_compressed(output / "failure-state.npz", **flatten(last))
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


def main(argv=None, *, cluster=False):
    _, definitions = implementation(cluster)
    cli_name = "assembly-cluster" if cluster else "assembly-cell"
    parser = argparse.ArgumentParser(prog="cells " + cli_name, description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate").add_argument("input", type=Path)
    for name in ("status", "_worker"):
        commands.add_parser(name).add_argument("output", type=Path)
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
            spec = definitions.load_spec(args.input)
            result = {
                "status": "valid",
                "definition_sha256": spec.fingerprint,
                "worlds": spec.pool.worlds,
                "ticks": spec.ticks,
                "working_bytes": spec.working_bytes,
            }
        elif args.command == "_worker":
            result = execute(args.output.resolve(), cluster=cluster)
        elif args.command == "status":
            candidates = [
                args.output / n
                for n in ("failure.json", "result.json", "status.json", "launch.json")
            ]
            result = next((json.loads(p.read_text()) for p in candidates if p.exists()), None)
            if result is None:
                raise AssemblyError("No saved coupled status")
        else:
            parent, state = None, None
            if args.command == "resume":
                spec, state, sha = load_checkpoint(args.input, backend=args.backend)
                # A checkpoint cannot silently select another CLI/model family.
                spec = definitions.parse_spec(spec.to_dict())
                parent = {"path": str(args.input.resolve()), "sha256": sha}
            else:
                spec = definitions.load_spec(args.input)
            until = spec.pool.end_time_s if args.until is None else args.until
            target = tick_at(spec, until)
            if target <= (0 if state is None else int(state.tick[0])) or args.device_index < 0:
                raise AssemblyError("Require advancing coupled horizon and valid device index")
            output = output_path(args.output)
            if shutil.disk_usage(output.parent).free < spec.pool.max_output_bytes + 4 * 1024**3:
                raise AssemblyError("Coupled disk reserve")
            output.mkdir()
            write_json(
                output / "registration.json",
                {
                    "definition": spec.to_dict(),
                    "sources_sha256": source_identity(),
                    "runtime": runtime(),
                    "backend": args.backend,
                    "device_index": args.device_index,
                    "until_s": until,
                    "parent": parent,
                    "utc": utc(),
                },
            )
            source = output / "source"
            shutil.copytree(
                Path(__file__).resolve().parents[1],
                source / "cells",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            if args.detach:
                environment = dict(
                    os.environ,
                    PYTHONPATH=str(source),
                    PYTHONDONTWRITEBYTECODE="1",
                    XLA_PYTHON_CLIENT_PREALLOCATE="false",
                )
                with (
                    (output / "stdout.log").open("x") as out,
                    (output / "stderr.log").open("x") as err,
                ):
                    child = subprocess.Popen(
                        [
                            sys.executable,
                            "-B",
                            "-m",
                            "cells." + cli_name.replace("-", "_"),
                            "_worker",
                            str(output),
                        ],
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
                    "utc": utc(),
                    "output": str(output),
                }
                write_json(output / "launch.json", result)
            else:
                result = execute(output, cluster=cluster)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Assembly-cell error: {exc}", file=sys.stderr)
        return 2
