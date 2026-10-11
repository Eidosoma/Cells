"""One detached, matched baseline/candidate benchmark using the existing ensemble runner."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
import zipfile
from pathlib import Path

import numpy as np

from cells.assembly.kernel import AssemblyState
from cells.assembly.spec import parse_spec
from cells.core.output_paths import within_output_root
from cells.ensemble.cli import read, sha, write
from cells.ensemble.plan import plan
from cells.ensemble.telemetry import devices


def tree(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob("*.py"))}


def compare_checkpoints(left, right):
    """Authenticate both containers, then compare every complete array byte."""
    manifests = [read(p / "manifest.json") for p in (left, right)]
    for key in ("format", "definition", "definition_sha256", "runtime", "rng", "world_ids"):
        if manifests[0][key] != manifests[1][key]:
            raise ValueError(f"Matched checkpoints differ in {key}")
    spec = parse_spec(manifests[0]["definition"])
    if manifests[0]["definition_sha256"] != spec.fingerprint:
        raise ValueError("Checkpoint definition digest mismatch")
    for path, manifest in zip((left, right), manifests, strict=True):
        if sha(path / "state.npz") != manifest["state_sha256"]:
            raise ValueError("Checkpoint payload changed")
        with zipfile.ZipFile(path / "state.npz") as archive:
            if sum(i.file_size for i in archive.infolist()) > spec.worlds * 1024 + 65536:
                raise ValueError("Checkpoint uncompressed budget exceeded")
    total = 0
    with (
        np.load(left / "state.npz", allow_pickle=False) as a,
        np.load(right / "state.npz", allow_pickle=False) as b,
    ):
        if set(a.files) != set(b.files) or set(a.files) != set(AssemblyState._fields):
            raise ValueError("Complete checkpoint fields differ")
        for name in AssemblyState._fields:
            x, y = a[name], b[name]
            if x.shape != y.shape or x.dtype != y.dtype or x.tobytes() != y.tobytes():
                raise ValueError(f"Matched final state differs: {name}")
            total += x.nbytes
    return {"worlds": spec.worlds, "identical_array_bytes": total}


def completed(path):
    result = read(path / "result.json")
    if read(path / "completion.json")["result_sha256"] != sha(path / "result.json"):
        raise ValueError("Completion result changed")
    if result["status"] != "completed" or result["registration_sha256"] != sha(
        path / "registration.json"
    ):
        raise ValueError("Benchmark child did not complete its registered work")
    return result


def compare_runs(root):
    paths = [root / label for label in ("baseline", "candidate")]
    results = [completed(p) for p in paths]
    definitions = [read(p / "registration.json")["definition"] for p in paths]
    if definitions[0] != definitions[1]:
        raise ValueError("Scientific workload or execution definition changed")
    if set(results[0]["result_records"]) != set(results[1]["result_records"]):
        raise ValueError("Matched task sets differ")
    comparisons = {}
    for task in sorted(results[0]["result_records"]):
        rows = []
        for path, result in zip(paths, results, strict=True):
            record = result["result_records"][task]
            task_path = path / "tasks" / task
            if sha(task_path / "result.json") != record["sha256"]:
                raise ValueError("Task result changed")
            row = read(task_path / "result.json")
            if sha(task_path / "checkpoint/manifest.json") != row["checkpoint_manifest_sha256"]:
                raise ValueError("Task checkpoint changed")
            rows.append(row)
        for key in (
            "definition",
            "arm",
            "backend",
            "gpu_uuid",
            "worlds",
            "faulted_worlds",
            "completed_shells",
            "committed_events",
            "final_size_histogram",
            "dwell_by_size_total_s",
            "not_completed_counts",
            "survival_times_s",
            "restricted_wait_sum_s",
        ):
            if rows[0][key] != rows[1][key]:
                raise ValueError(f"Matched observations differ: {task}/{key}")
        comparisons[task] = compare_checkpoints(
            paths[0] / "tasks" / task / "checkpoint",
            paths[1] / "tasks" / task / "checkpoint",
        )
    metrics = {}
    for label, result in zip(("baseline", "candidate"), results, strict=True):
        hours = result["allocated_gpu_hours"]
        metrics[label] = {
            "elapsed_seconds": result["elapsed_seconds"],
            "allocated_gpu_hours": hours,
            "worlds_per_allocated_gpu_hour": result["completed_worlds"] / hours,
            "full_job_utilization": result["full_job_utilization"],
            "after_all_workers_warmed": result["after_all_workers_warmed"],
        }
    return {
        "status": "matched_complete_state_pass",
        "metrics": metrics,
        "wall_time_speedup": results[0]["elapsed_seconds"] / results[1]["elapsed_seconds"],
        "comparisons": comparisons,
        "single_pair_not_a_scaling_qualification": True,
    }


def execute(root):
    registration = read(root / "registration.json")
    started = time.time()
    deadline = started + registration["max_wall_seconds"]
    try:
        if sha(__file__) != registration["runner_sha256"]:
            raise ValueError("Benchmark runner changed")
        if sha(root / "definition.json") != registration["definition_sha256"]:
            raise ValueError("Benchmark definition changed")
        os.sched_setaffinity(0, registration["cpu_affinity"])
        for label in ("baseline", "candidate"):
            source = root / f"{label}-source"
            if tree(source / "cells") != registration["sources_sha256"][label]:
                raise ValueError("Frozen benchmark source changed")
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(source)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            # Both runner versions select indices within CUDA visibility.
            # Bind the physical UUID here, then address its sole visible slot.
            environment["CUDA_VISIBLE_DEVICES"] = registration["device"]["uuid"]
            for key, suffix in (
                ("XDG_CACHE_HOME", "cache"),
                ("CUDA_CACHE_PATH", "cuda"),
                ("JAX_COMPILATION_CACHE_DIR", "jax"),
                ("TMPDIR", "tmp"),
            ):
                environment[key] = str(root / f"{label}-cache" / suffix)
            remaining = deadline - time.time() - 90
            if remaining <= 0:
                raise TimeoutError("Insufficient remaining paired-benchmark budget")
            with (
                (root / f"{label}.stdout.log").open("x") as stdout,
                (root / f"{label}.stderr.log").open("x") as stderr,
            ):
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "cells.ensemble",
                        "run",
                        str(root / "definition.json"),
                        "--output",
                        str(root / label),
                        "--devices",
                        "0",
                        "--allocated-gpus",
                        "1",
                    ],
                    env=environment,
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=True,
                )
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    process.send_signal(signal.SIGUSR1)
                    try:
                        process.wait(timeout=90)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    raise TimeoutError("Paired-benchmark wall budget exceeded") from None
            if process.returncode:
                raise RuntimeError(f"{label} runner exited {process.returncode}; see retained logs")
            completed(root / label)
            write(root / f"{label}-finished.json", {"time": time.time()})
        result = compare_runs(root)
        result.update(
            registration_sha256=sha(root / "registration.json"),
            benchmark_wall_seconds=time.time() - started,
            automatic_followup=False,
        )
        write(root / "result.json", result)
        write(
            root / "completion.json",
            {"status": result["status"], "result_sha256": sha(root / "result.json")},
        )
    except BaseException as exc:
        write(
            root / "failure.json",
            {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()},
        )
        raise


def launch(baseline, output, max_wall):
    if os.environ.get("SLURM_JOB_ID"):
        raise ValueError("This local paired benchmark is not a JUPITER submission tool")
    root = output.resolve()
    if not within_output_root(root) or root.exists() or not 180 <= max_wall <= 1800:
        raise ValueError("Require a new workspace output and a 180–1800 s wall budget")
    completed(baseline)
    prior = read(baseline / "registration.json")
    definition = prior["definition"]
    bound = 2 * plan(definition, 1)["output_bytes_bound"] + 512 * 1024**2
    if shutil.disk_usage(root.parent).free < bound + 4 * 1024**3:
        raise ValueError("Paired checkpoint bounds plus the 4 GiB reserve do not fit")
    affinity = sorted(os.sched_getaffinity(0))[:4]
    if len(affinity) != 4:
        raise ValueError("Matched local benchmark requires four available CPU cores")
    selected = devices("0", 1)[0]
    candidate = Path(__file__).resolve().parents[2] / "src/cells"
    if tree(baseline / "source/cells") != prior["sources_sha256"]:
        raise ValueError("Baseline frozen source differs from its original registration")
    root.mkdir()
    for label, source in (("baseline", baseline / "source/cells"), ("candidate", candidate)):
        shutil.copytree(
            source,
            root / f"{label}-source/cells",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    shutil.copyfile(__file__, root / "runner.py")
    write(root / "definition.json", definition)
    write(
        root / "registration.json",
        {
            "baseline_parent": str(baseline),
            "baseline_result_sha256": sha(baseline / "result.json"),
            "definition_sha256": sha(root / "definition.json"),
            "runner_sha256": sha(root / "runner.py"),
            "sources_sha256": {
                k: tree(root / f"{k}-source/cells") for k in ("baseline", "candidate")
            },
            "cpu_affinity": affinity,
            "device": selected,
            "max_wall_seconds": max_wall,
            "output_bytes_bound": bound,
            "free_space_reserve_bytes": 4 * 1024**3,
            "order": ["baseline", "candidate"],
            "cache_policy": "separate initially empty directories",
            "qualification": "same device, input, complete state bytes and observations",
            "automatic_followup": False,
        },
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "candidate-source")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with (root / "stdout.log").open("x") as out, (root / "stderr.log").open("x") as err:
        process = subprocess.Popen(
            [sys.executable, "-B", str(root / "runner.py"), "execute", "--output", str(root)],
            env=environment,
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    receipt = {"pid": process.pid, "output": str(root), "launched_time": time.time()}
    write(root / "launch.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "execute"))
    parser.add_argument("--baseline-run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-wall-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.command == "launch":
        if args.baseline_run is None:
            parser.error("launch requires --baseline-run")
        launch(args.baseline_run.resolve(), args.output, args.max_wall_seconds)
    else:
        execute(args.output.resolve())
