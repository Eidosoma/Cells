"""Detached, matched width-32/64 measurement using the ordinary ensemble runner.

Each configuration runs the same 1024 worlds in full 64-world tasks. The first
128 endpoints retain the scalar reference; every width-64 endpoint must match
width 32 exactly. This extends endpoint evidence, not full-trajectory coverage.
"""

import argparse
import copy
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
from functools import partial
from pathlib import Path
from unittest.mock import patch

from cells.assembly.io import write_json
from cells.core.output_paths import within_output_root
from cells.ensemble import cli
from cells.ensemble.telemetry import devices

if __package__:
    from . import profile_cluster as profile
else:
    import profile_cluster as profile

need = profile.need
WIDTHS = (32, 64)
WORLDS = 1024
BATCH = 64
WALL_SECONDS = 3600
TREE_RSS = 16 * 1024**3
RESERVE = 4 * 1024**3
CACHE_ALLOWANCE = 1024**3


def definition_for(parent):
    definition = copy.deepcopy(parent["definition"])
    need(definition["kind"] == "assembly_cluster_ensemble@1", "Require the cluster family")
    raw = definition["arms"][0]["definition"]
    need(all(a["definition"] == raw for a in definition["arms"]), "Require one physical condition")
    definition["arms"] = [
        {
            "id": "dynamic-" + group,
            "definition": copy.deepcopy(raw),
            "worlds": WORLDS // 2,
            "batch_worlds": BATCH,
            "seconds_per_world": None,
        }
        for group in ("a", "b")
    ]
    definition["execution"].update(
        max_wall_seconds=WALL_SECONDS,
        max_output_bytes=8 * 1024**3,
        workers_per_gpu=2,
        worker_threads=1,
    )
    planned = cli.plan(definition, 1)
    need(planned["worlds"] == WORLDS and len(planned["tasks"]) == 16, "Unexpected full-batch plan")
    return definition, planned


def compare_arrays(left, right):
    need(set(left) == set(right), "Checkpoint fields differ")
    count = 0
    for name, expected in left.items():
        actual = right[name]
        need(
            expected.shape == actual.shape
            and expected.dtype == actual.dtype
            and expected.tobytes() == actual.tobytes(),
            "Checkpoint state differs: " + name,
        )
        count += expected.size
    return count


def authenticate(root):
    record = cli.read(root / "registration.json")
    need(cli.sources() == record["production_sources_sha256"], "Production changed")
    for name, digest in record["inputs_sha256"].items():
        need(cli.sha(root / name) == digest, "Frozen benchmark input changed: " + name)
    parent = Path(record["parent"])
    need(cli.sha(parent / "result.json") == record["parent_result_sha256"], "Scalar parent changed")
    _, origin = profile.authenticate_parent(parent)
    definition, planned = definition_for(origin)
    need(
        cli.read(root / "definition.json") == definition
        and cli.read(root / "plan.json") == planned,
        "Matched workload changed",
    )
    need(record["width_order"] == list(WIDTHS), "Benchmark order changed")
    need(
        record["memory_limits"] == {"tree_rss_bytes": TREE_RSS, "available_memory_bytes": RESERVE},
        "Memory guard changed",
    )
    for width in WIDTHS:
        candidate = record["qualifications"][str(width)]
        need(candidate["tile_width"] == width, "Qualification width changed")
        for name in ("result", "registration", "completion"):
            need(
                cli.sha(Path(candidate["path"]) / (name + ".json")) == candidate[name + "_sha256"],
                "Candidate qualification changed",
            )
    return record


def completed_phase(root, width):
    directory = root / f"width-{width}"
    result, done = (cli.read(directory / name) for name in ("result.json", "completion.json"))
    need(
        result["status"] == done["status"] == "completed"
        and done["result_sha256"] == cli.sha(directory / "result.json"),
        "Phase incomplete or changed",
    )
    need(
        result["registration_sha256"] == cli.sha(root / "registration.json")
        and result["campaign_result_sha256"] == cli.sha(directory / "campaign/result.json"),
        "Phase provenance changed",
    )
    for name, digest in result["evidence_sha256"].items():
        need(cli.sha(directory / name) == digest, "Phase evidence changed: " + name)
    return result


def verify_endpoints(root, width, record):
    import numpy as np

    parallel, _ = profile.candidate_helpers()
    directory = root / f"width-{width}"
    _, registered = profile.authenticate_parent(directory / "campaign")
    need(registered["plan"] == cli.read(root / "plan.json"), "Campaign changed task identities")
    scalar_parent = Path(record["parent"])
    profile.authenticate_parent(scalar_parent)
    if width == 64:
        completed_phase(root, 32)
        _, previous = profile.authenticate_parent(root / "width-32/campaign")
        need(previous["plan"] == registered["plan"], "Compared campaigns changed workload")
    counts, anchors = {}, {}
    for task in registered["plan"]["tasks"]:
        folder = directory / "campaign/tasks" / task["id"]
        spec = parallel.parse_spec(task["definition"])
        checkpoint = folder / "checkpoint"
        marker = profile.candidate_execution(record["qualifications"][str(width)])
        provenance = cli.read(checkpoint / "manifest.json")["provenance"]
        need(
            provenance["execution"]["experimental_candidate"] == marker
            and provenance["parent"] is None
            and cli.read(folder / "result.json")["experimental_candidate"] == marker,
            "Candidate checkpoint or task provenance changed",
        )
        if spec.pool.world_id_start < 128:
            slices = parallel.qualified_slices(scalar_parent, spec)
            pieces = []
            for part in slices:
                with np.load(Path(part["checkpoint"]) / "state.npz", allow_pickle=False) as saved:
                    first, stop = part["slice_start"], part["slice_start"] + part["worlds"]
                    pieces.append({k: saved[k][first:stop] for k in saved.files})
            expected = {k: np.concatenate([piece[k] for piece in pieces]) for k in pieces[0]}
            with np.load(checkpoint / "state.npz", allow_pickle=False) as saved:
                anchors[task["id"]] = compare_arrays(expected, {k: saved[k] for k in saved.files})
        if width == 64:
            counts[task["id"]] = profile.compare_states(
                root / "width-32/campaign/tasks" / task["id"] / "checkpoint/state.npz",
                checkpoint / "state.npz",
            )
    need(len(anchors) == 2 and sum(anchors.values()) == 52736, "Missing scalar anchor worlds")
    if width == 64:
        need(len(counts) == 16, "Missing matched endpoint comparisons")
    return {
        "scalar_anchor_worlds": 128,
        "scalar_anchor_scalars": anchors,
        "matched_width_worlds": WORLDS if width == 64 else 0,
        "matched_width_scalars": counts,
    }


def phase(root, width):
    directory = root / f"width-{width}"
    counters = monitor = None
    try:
        record = authenticate(root)
        need(width in WIDTHS, "Unknown benchmark width")
        need(profile.memory_available() >= TREE_RSS + RESERVE, "Insufficient host reserve")
        candidate = record["qualifications"][str(width)]
        counters = profile.gpu_counters.CounterMonitor(directory, record["gpu_counters"])
        counters.start()
        monitor = profile.ResourceMonitor(directory, limits=record["memory_limits"])
        monitor.thread.start()
        observer = partial(
            profile.profile_worker, trace_enabled=False, experimental_candidate=candidate
        )
        with patch("cells.ensemble.worker.worker", observer):
            campaign = cli.register(
                argparse.Namespace(
                    command="run",
                    input=root / "definition.json",
                    output=directory / "campaign",
                    devices="0",
                    allocated_gpus=1,
                    detach=False,
                )
            )
        counters.finish()
        monitor.finish()
        need(monitor.violation is None, "Memory guard requested checkpoint pause")
        need(campaign["status"] == "completed", "Ordinary campaign did not complete")
        comparison = verify_endpoints(root, width, record)
        warms = [cli.read(p)["time"] for p in (directory / "campaign").glob("worker-*-warm.json")]
        finishes = [
            cli.read(p)["time"] for p in (directory / "campaign").glob("worker-*-finished.json")
        ]
        resources = [
            cli.read(p) for p in (directory / "campaign").glob("worker-*-profile/resources.json")
        ]
        need(len(warms) == len(finishes) == len(resources) == 2, "Missing worker observations")
        summaries = {
            interval: profile.gpu_counters.summarize(
                counters.rows, start, campaign["finished_time"]
            )
            for interval, start in (
                ("whole_job", campaign["started_time"]),
                ("after_all_workers_warmed", max(warms)),
            )
        }
        need(all(row["coverage_pass"] for row in summaries.values()), "Counter coverage below 98%")
        cli.write(directory / "gpu-counter-summary.json", summaries)
        samples = [
            json.loads(line)
            for line in (directory / "host-resources.jsonl").read_text().splitlines()
        ]
        rows = [cli.read(row["path"]) for row in campaign["result_records"].values()]
        arms = {
            name: max(row["wall_end"] for row in rows if row["arm"] == name)
            for name in {row["arm"] for row in rows}
        }
        evidence = [
            *directory.glob("*.jsonl"),
            directory / "gpu-counter-summary.json",
            directory / "gpu-counters.stderr.log",
            directory / "dcgm.log",
            directory / "campaign/gpu-utilization.jsonl",
            *(directory / "campaign").glob("worker-*.json"),
            *(p for p in (directory / "campaign").glob("worker-*-profile/**/*") if p.is_file()),
        ]
        need(
            sum(p.stat().st_size for p in evidence if p.is_file())
            <= profile.RESOURCE_OBSERVER_ALLOWANCE,
            "Resource/counter observations exceeded their output allowance",
        )
        result = {
            "status": "completed",
            "tile_width": width,
            "worlds": WORLDS,
            "registration_sha256": cli.sha(root / "registration.json"),
            "campaign_result_sha256": cli.sha(directory / "campaign/result.json"),
            "experimental_candidate": candidate,
            "endpoint_comparisons": comparison,
            "elapsed_seconds": campaign["elapsed_seconds"],
            "throughput": campaign["throughput"],
            "full_job_utilization": campaign["full_job_utilization"],
            "after_all_workers_warmed": campaign["after_all_workers_warmed"],
            "gpu_hardware_counters": summaries,
            "worker_resources": resources,
            "worker_finish_gap_seconds": max(finishes) - min(finishes),
            "arm_finish_gap_seconds": max(arms.values()) - min(arms.values()),
            "seconds_until_all_workers_warmed": max(warms) - campaign["started_time"],
            "compile_seconds_by_task": {row["task"]: row["compile_seconds"] for row in rows},
            "sampled_peak_tree_rss_bytes": max(s["tree_rss_bytes"] for s in samples),
            "minimum_available_memory_bytes": min(s["available_memory_bytes"] for s in samples),
            "memory_guard_triggered": False,
            "evidence_sha256": {
                str(p.relative_to(directory)): cli.sha(p) for p in evidence if p.is_file()
            },
            "scope": (
                "Includes compile, checks, I/O and counter overhead; 65-world trajectory evidence, "
                "128 scalar anchor endpoints and matched-width endpoints as recorded"
            ),
        }
        cli.write(directory / "result.json", result)
        cli.write(
            directory / "completion.json",
            {"status": "completed", "result_sha256": cli.sha(directory / "result.json")},
        )
    except BaseException:
        error = traceback.format_exc()
        if counters:
            try:
                counters.finish()
            except Exception:
                error += "\nCounter cleanup:\n" + traceback.format_exc()
        if monitor and monitor.thread.is_alive():
            monitor.stop.set()
            monitor.thread.join(timeout=10)
        cli.write(
            directory / "failure.json",
            {"status": "failed", "traceback": error, "time": time.time()},
        )
        raise


def controller(root):
    began = time.time()
    try:
        record = authenticate(root)
        for width in WIDTHS:
            directory = root / f"width-{width}"
            directory.mkdir()
            (directory / "source").symlink_to(root / "source", target_is_directory=True)
            env = os.environ.copy()
            for key, folder in (
                ("TMPDIR", "tmp"),
                ("XDG_CACHE_HOME", "cache"),
                ("CUDA_CACHE_PATH", "cache/cuda"),
                ("JAX_COMPILATION_CACHE_DIR", "cache/jax"),
            ):
                (directory / folder).mkdir(parents=True, exist_ok=True)
                env[key] = str(directory / folder)
            write_json(
                root / "status.json",
                {"status": "running", "tile_width": width, "time": time.time()},
                replace=True,
            )
            with (
                (directory / "stdout.log").open("x") as out,
                (directory / "stderr.log").open("x") as err,
            ):
                child = subprocess.Popen(
                    [
                        record["python"],
                        "-B",
                        str(root / "source/tile_benchmark.py"),
                        "_phase",
                        str(root),
                        "--width",
                        str(width),
                    ],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                )
                try:
                    need(child.wait(timeout=WALL_SECONDS + 180) == 0, "Benchmark phase failed")
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=10)
                    raise
            completed_phase(root, width)
        results = {str(width): completed_phase(root, width) for width in WIDTHS}
        result = {
            "status": "completed",
            "finished_time": time.time(),
            "elapsed_seconds": time.time() - began,
            "registration_sha256": cli.sha(root / "registration.json"),
            "phase_result_sha256": {
                str(w): cli.sha(root / f"width-{w}/result.json") for w in WIDTHS
            },
            "worlds_per_configuration": WORLDS,
            "distinct_worlds": WORLDS,
            "total_world_executions": WORLDS * 2,
            "width_order": list(WIDTHS),
            "complete_pair_allocated_gpu_hours": (time.time() - began) / 3600,
            "width64_over_width32_throughput": results["64"]["throughput"][
                "worlds_per_allocated_gpu_hour"
            ]
            / results["32"]["throughput"]["worlds_per_allocated_gpu_hour"],
            "all_matched_width_endpoints_bitwise_equal": True,
            "scalar_anchor_worlds_per_configuration": 128,
            "automatic_followup": False,
            "production_default_changed": False,
            "scope": "One ordered local pair; same seeds, worlds, full tasks, device and counters. "
            "Per-phase timing includes compilation; pair allocation includes setup and checks. "
            "SM activity and occupancy include stalled warps, not arithmetic throughput. "
            "No general speedup, multi-GPU scaling or new full-trajectory qualification.",
        }
        cli.write(root / "result.json", result)
        cli.write(
            root / "completion.json",
            {"status": "completed", "result_sha256": cli.sha(root / "result.json")},
        )
        write_json(root / "status.json", {"status": "completed", "time": time.time()}, replace=True)
    except BaseException:
        cli.write(
            root / "failure.json",
            {
                "status": "failed",
                "traceback": traceback.format_exc(),
                "elapsed_seconds": time.time() - began,
            },
        )
        raise


def launch(parent, qualifications, root, dcgm_root):
    need(within_output_root(root) and not root.exists(), "Require a fresh workspace output")
    _, origin = profile.authenticate_parent(parent)
    need(origin["plan"]["worlds"] == 128, "Require the complete 128-world scalar anchor")
    definition, planned = definition_for(origin)
    candidates = {
        str(width): profile.authenticate_candidate(qualifications[width], {"plan": planned})
        for width in WIDTHS
    }
    need(all(candidates[str(w)]["tile_width"] == w for w in WIDTHS), "Qualification widths swapped")
    need(
        candidates["32"]["helpers_sha256"] == candidates["64"]["helpers_sha256"],
        "Implementations differ",
    )
    gpu = devices("0", 1)[0]
    subprocess.run(["sudo", "-n", "true"], check=True, timeout=5)
    counters = {
        "tool_root": str(dcgm_root),
        "tool_sha256": profile.gpu_counters.tool_identity(dcgm_root),
        "driver_sha256": cli.sha(Path(profile.gpu_counters.__file__)),
        "uuid": gpu["uuid"],
        "timeout_seconds": WALL_SECONDS + 180,
        "field_ids": profile.gpu_counters.FIELDS,
        "period_seconds": profile.gpu_counters.PERIOD,
        "minimum_coverage_fraction": profile.gpu_counters.MIN_COVERAGE,
    }
    need(
        profile.memory_available() >= TREE_RSS + RESERVE,
        "Require worker allowance and host reserve",
    )
    need(set((4, 5)).issubset(os.sched_getaffinity(0)), "CPU cores 4 and 5 unavailable")
    need(
        shutil.disk_usage(root.parent).free
        >= 2 * (planned["output_bytes_bound"] + CACHE_ALLOWANCE) + RESERVE,
        "Insufficient output/cache space and disk reserve",
    )
    root.mkdir()
    source = root / "source"
    source.mkdir()
    shutil.copytree(
        Path(cli.__file__).parents[1],
        source / "cells",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    helpers = profile.candidate_helpers()[1] | {
        "profile_cluster.py": Path(profile.__file__),
        "gpu_counters.py": Path(profile.gpu_counters.__file__),
        "tile_benchmark.py": Path(__file__),
    }
    for name, helper in helpers.items():
        shutil.copyfile(helper, source / name)
    cli.write(root / "definition.json", definition)
    cli.write(root / "plan.json", planned)
    environment = os.environ.copy()
    environment.pop("JAX_PLATFORMS", None)
    environment.update(
        PYTHONPATH=str(source),
        PYTHONDONTWRITEBYTECODE="1",
        JAX_ENABLE_X64="1",
        XLA_PYTHON_CLIENT_PREALLOCATE="false",
        XLA_PYTHON_CLIENT_MEM_FRACTION="0.2",
    )
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        environment[key] = "1"
    for key, folder in (
        ("TMPDIR", "tmp"),
        ("XDG_CACHE_HOME", "cache"),
        ("CUDA_CACHE_PATH", "cache/cuda"),
        ("JAX_COMPILATION_CACHE_DIR", "cache/jax"),
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)
        environment[key] = str(root / folder)
    command = [
        "taskset",
        "-c",
        "4,5",
        sys.executable,
        "-B",
        str(source / "tile_benchmark.py"),
        "_run",
        str(root),
    ]
    cli.write(
        root / "registration.json",
        {
            "created_time": time.time(),
            "parent": str(parent),
            "parent_result_sha256": cli.sha(parent / "result.json"),
            "qualifications": candidates,
            "production_sources_sha256": cli.sources(),
            "inputs_sha256": {
                str(p.relative_to(root)): cli.sha(p)
                for p in [
                    root / "definition.json",
                    root / "plan.json",
                    *sorted(source.rglob("*.py")),
                ]
            },
            "gpu_counters": counters,
            "device": gpu,
            "width_order": list(WIDTHS),
            "memory_limits": {"tree_rss_bytes": TREE_RSS, "available_memory_bytes": RESERVE},
            "memory_scope": (
                "One-second sampled cooperative guard; previous two-worker peak 4.08 GiB "
                "and 65-world width-64 qualification peak 2.98 GiB; full-task concurrency is new"
            ),
            "python": sys.executable,
            "command": command,
            "environment_overrides": {
                k: v for k, v in environment.items() if os.environ.get(k) != v
            },
            "cold_cache_per_configuration": True,
            "automatic_followup": False,
            "comparison_policy": (
                "All 1024 endpoints exactly width-matched; first 128 also exactly scalar-matched. "
                "The two scheduling groups use the same physical condition and disjoint world IDs."
            ),
        },
    )
    with (root / "stdout.log").open("x") as out, (root / "stderr.log").open("x") as err:
        child = subprocess.Popen(
            command,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
            close_fds=True,
        )
    receipt = {
        "status": "launched",
        "pid": child.pid,
        "time": time.time(),
        "output": str(root),
        "maximum_campaign_seconds_each": WALL_SECONDS,
        "width_order": list(WIDTHS),
    }
    cli.write(root / "launch.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("launch")
    for name in ("parent", "qualification-32", "qualification-64", "output", "dcgm-root"):
        start.add_argument("--" + name, type=Path, required=True)
    sub.add_parser("_run").add_argument("output", type=Path)
    run = sub.add_parser("_phase")
    run.add_argument("output", type=Path)
    run.add_argument("--width", type=int, choices=WIDTHS, required=True)
    args = parser.parse_args()
    if args.command == "launch":
        print(
            json.dumps(
                launch(
                    args.parent.resolve(),
                    {32: args.qualification_32.resolve(), 64: args.qualification_64.resolve()},
                    args.output.resolve(),
                    args.dcgm_root.resolve(),
                ),
                indent=2,
            )
        )
    elif args.command == "_run":
        controller(args.output.resolve())
    else:
        phase(args.output.resolve(), args.width)
