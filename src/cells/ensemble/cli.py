"""Plan, launch, resume and inspect bounded GPU ensembles without assistant polling."""

import argparse
import hashlib
import json
import math
import multiprocessing
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path

from cells.core.output_paths import configure_caches, within_output_root
from cells.ensemble.plan import balance, plan
from cells.ensemble.telemetry import Monitor, devices, utilization


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def sources():
    root = Path(__file__).parents[1]
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*.py"))}


def wilson(successes, n):
    z = 1.959963984540054
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [
        0.0 if successes == 0 else max(0.0, centre - radius),
        1.0 if successes == n else min(1.0, centre + radius),
    ]


def aggregate(rows):
    clusters = [row for row in rows if row.get("model") == "assembly_regulated_cluster@1"]
    if clusters:
        if len(clusters) != len(rows):
            raise ValueError("An ensemble cannot mix cluster and other result families")
        from cells.ensemble.cluster import aggregate as aggregate_cluster

        return aggregate_cluster(clusters)
    ionic = [row for row in rows if row.get("model") == "ionic_worlds@1"]
    assembly = [row for row in rows if row.get("model") != "ionic_worlds@1"]
    if ionic and assembly:
        raise ValueError("An ensemble cannot mix ionic and assembly result families")
    if ionic:
        return aggregate_ionic(ionic)
    groups = {}
    for row in rows:
        arm = groups.setdefault(
            row["arm"],
            {
                "worlds": 0,
                "completed_shells": 0,
                "committed_events": 0,
                "restricted_wait_sum_s": 0.0,
                "task_wall_seconds": [],
                "task_seconds_per_world": [],
                "execute_seconds": 0.0,
                "survival_times_s": row["survival_times_s"],
                "not_completed_counts": [0] * len(row["survival_times_s"]),
                "final_size_histogram": [0] * 21,
                "dwell_by_size_total_s": [0.0] * 21,
            },
        )
        for key in (
            "worlds",
            "completed_shells",
            "committed_events",
            "restricted_wait_sum_s",
            "execute_seconds",
        ):
            arm[key] += row[key]
        wall = row["wall_end"] - row["wall_start"]
        arm["task_wall_seconds"].append(wall)
        arm["task_seconds_per_world"].append(wall / row["worlds"])
        if arm["survival_times_s"] != row["survival_times_s"]:
            raise ValueError("An arm changed its registered observation grid")
        for key in ("not_completed_counts", "final_size_histogram", "dwell_by_size_total_s"):
            arm[key] = [a + b for a, b in zip(arm[key], row[key], strict=True)]
        if row.get("model") in ("finite_bond_assembly@1", "assembly_regulated_cell@1"):
            arm["model"] = row["model"]
            arm["completion_event"] = row["completion_event"]
            for key in (
                "currently_full_cages",
                "full_cage_dwell_total_s",
                "final_free_trimers",
                "final_attached_trimers",
                "final_fragment_trimers",
                "initial_total_trimers",
                "material_residual_trimers",
            ):
                arm[key] = arm.get(key, 0) + row[key]
            reaction = arm.setdefault("reaction_counts", dict.fromkeys(row["reaction_counts"], 0))
            for key, count in row["reaction_counts"].items():
                reaction[key] += count
        if row.get("model") == "assembly_regulated_cell@1":
            add_ionic_observables(arm, row)
    for arm in groups.values():
        n = arm["worlds"]
        arm["completion_probability"] = arm["completed_shells"] / n
        arm["completion_probability_wilson_95"] = wilson(arm["completed_shells"], n)
        arm["restricted_mean_wait_s"] = arm["restricted_wait_sum_s"] / n
        arm["not_completed_fraction"] = [v / n for v in arm["not_completed_counts"]]
    return groups


def add_ionic_observables(arm, row):
    arm["integrated_world_steps"] = (
        arm.get("integrated_world_steps", 0) + row["integrated_world_steps"]
    )
    # Report per-cell aggregate voltage and material/charge/energy maxima; all
    # individual states are retained in the complete task checkpoints.
    voltages = row["final_voltage_V"]
    if voltages and not isinstance(voltages[0], list):
        voltages = [[v] for v in voltages]
    totals = [math.fsum(world[i] for world in voltages) for i in range(len(voltages[0]))]
    if "final_voltage_sum_V" not in arm:
        arm["final_voltage_sum_V"] = [0.0] * len(totals)
    arm["final_voltage_sum_V"] = [
        a + b for a, b in zip(arm["final_voltage_sum_V"], totals, strict=True)
    ]
    arm["final_voltage_mean_V"] = [v / arm["worlds"] for v in arm["final_voltage_sum_V"]]
    maxima = arm.setdefault("ionic_accounting", {})
    for key, value in row["ionic_accounting"].items():
        maxima[key] = max(maxima.get(key, 0.0), value)
    for source, destination in (
        ("channel_transferred_fmol", "channel_transferred_total_fmol"),
        ("availability_exposure_s", "availability_exposure_total_s"),
    ):
        if source in row:
            arm[destination] = arm.get(destination, 0.0) + math.fsum(row[source])


def aggregate_ionic(rows):
    groups = {}
    for row in rows:
        arm = groups.setdefault(
            row["arm"],
            {
                "model": "ionic_worlds@1",
                "physical_model": row["physical_model"],
                "deterministic_replicas": True,
                "worlds": 0,
                "task_wall_seconds": [],
                "task_seconds_per_world": [],
                "execute_seconds": 0.0,
            },
        )
        if arm["physical_model"] != row["physical_model"]:
            raise ValueError("Ionic arm changed its physical model")
        arm["worlds"] += row["worlds"]
        arm["execute_seconds"] += row["execute_seconds"]
        wall = row["wall_end"] - row["wall_start"]
        arm["task_wall_seconds"].append(wall)
        arm["task_seconds_per_world"].append(wall / row["worlds"])
        add_ionic_observables(arm, row)
    return groups


def controller(root):
    from cells.ensemble.worker import worker

    root = Path(root)
    registration = read(root / "registration.json")
    if registration["sources_sha256"] != sources():
        raise ValueError("Worker source differs from frozen registration")
    execution = registration["definition"]["execution"]
    tasks = registration["plan"]["tasks"]
    inherited = registration["inherited_results"]
    for record in inherited.values():
        if sha(record["path"]) != record["sha256"]:
            raise ValueError("Inherited completed result changed")
    selected = registration["devices"]
    context = multiprocessing.get_context("spawn")
    stopping = context.Event()
    signal.signal(signal.SIGUSR1, lambda *_: stopping.set())
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    queue = context.Queue()
    for task in tasks:
        if task["id"] not in inherited:
            queue.put(task)
    worker_gpus = [gpu for gpu in selected for _ in range(execution.get("workers_per_gpu", 1))]
    for _ in worker_gpus:
        queue.put(None)
    processes, monitor = [], None
    began = registration["allocation_start_time"]
    write(
        root / "started.json", {"pid": os.getpid(), "time": began, "allocated_gpus": len(selected)}
    )
    try:
        monitor = Monitor(root / "gpu-utilization.jsonl", [r["uuid"] for r in selected])
        monitor.start()
        affinity = sorted(os.sched_getaffinity(0))
        threads = execution["worker_threads"]
        if len(affinity) < threads * len(worker_gpus):
            raise ValueError("CPU affinity cannot fit registered GPU worker threads")
        per_gpu = execution.get("workers_per_gpu", 1)
        for slot, gpu in enumerate(worker_gpus):
            gpu_index, local_worker = divmod(slot, per_gpu)
            group = affinity[
                gpu_index * len(affinity) // len(selected) : (gpu_index + 1)
                * len(affinity)
                // len(selected)
            ]
            worker_affinity = group[local_worker * threads : (local_worker + 1) * threads]
            process = context.Process(
                target=worker,
                args=(
                    str(root),
                    slot,
                    gpu,
                    worker_affinity,
                    queue,
                    stopping,
                    registration["parent_checkpoints"],
                ),
            )
            process.start()
            processes.append(process)
        notified, signal_time = False, None
        while any(p.is_alive() for p in processes):
            now = time.time()
            if now - began >= execution["max_wall_seconds"] - 60:
                stopping.set()
            if (
                registration["allocation_end_time"] is not None
                and now >= registration["allocation_end_time"] - 90
            ):
                stopping.set()
            size = sum(p.stat().st_size for p in (root / "tasks").rglob("*") if p.is_file())
            if size > execution["max_output_bytes"] or shutil.disk_usage(root).free < 4 * 1024**3:
                stopping.set()
                if not (root / "resource-stop.json").exists():
                    write(root / "resource-stop.json", {"time": now, "task_bytes": size})
            if stopping.is_set() and not notified:
                notified, signal_time = True, now
                # Workers share this Event. Sending another OS signal can hit
                # Python/JAX teardown after a valid checkpoint has been saved.
            if notified and now - signal_time > 55:
                for process in processes:
                    if process.is_alive():
                        process.kill()
            for process in processes:
                process.join(timeout=0.2)
            time.sleep(0.5)
        for process in processes:
            process.join()
    finally:
        if any(p.is_alive() for p in processes):
            stopping.set()
            deadline = time.monotonic() + 30
            for process in processes:
                process.join(timeout=max(0, deadline - time.monotonic()))
                if process.is_alive():
                    process.kill()
                    process.join()
        if monitor is not None:
            monitor.finish()
        queue.cancel_join_thread()
        queue.close()
    ended = time.time()
    records = dict(inherited)
    failures, paused = [], {}
    for task in tasks:
        folder = root / "tasks" / task["id"]
        if (folder / "result.json").exists():
            records[task["id"]] = {
                "path": str(folder / "result.json"),
                "sha256": sha(folder / "result.json"),
            }
        elif (folder / "paused.json").exists():
            saved = read(folder / "paused.json")
            paused[task["id"]] = {"path": saved["checkpoint"], "sha256": saved["sha256"]}
        elif (folder / "failure.json").exists():
            failures.append(task["id"])
    rows = [read(record["path"]) for record in records.values()]
    samples = [
        json.loads(line) for line in (root / "gpu-utilization.jsonl").read_text().splitlines()
    ]
    uuids = [gpu["uuid"] for gpu in selected]
    measured = utilization(samples, uuids, began, ended, execution["target_gpu_utilization_pct"])
    warms = [read(p)["time"] for p in root.glob("worker-*-warm.json")]
    steady = (
        utilization(samples, uuids, max(warms), ended, execution["target_gpu_utilization_pct"])
        if len(warms) == len(worker_gpus)
        else None
    )
    missing = [t["id"] for t in tasks if t["id"] not in records]
    abnormal = [p.exitcode for p in processes if p.exitcode != 0]
    status = (
        "completed"
        if not missing and not abnormal
        else "paused"
        if stopping.is_set() and not failures and not abnormal
        else "failed"
    )
    gpu_hours = len(selected) * (ended - began) / 3600
    fresh_complete = (
        status == "completed" and not inherited and not registration["parent_checkpoints"]
    )
    finished = {
        "status": status,
        "started_time": began,
        "finished_time": ended,
        "elapsed_seconds": ended - began,
        "allocated_gpu_hours": gpu_hours,
        "registration_sha256": sha(root / "registration.json"),
        "result_records": records,
        "parent_checkpoints": registration["parent_checkpoints"] | paused,
        "missing_tasks": missing,
        "failed_tasks": failures,
        "worker_abnormal_exits": abnormal,
        "completed_worlds": sum(r["worlds"] for r in rows),
        "registered_worlds": registration["plan"]["worlds"],
        "full_job_utilization": measured,
        "after_all_workers_warmed": steady,
        "ready_for_node_pilot": status == "completed" and measured["gate"] == "pass",
        "utilization_target_is_advisory": True,
        "throughput": {
            "scope": "fresh completed campaign; resumed work needs cumulative allocation cost",
            "worlds_per_allocated_gpu_hour": sum(r["worlds"] for r in rows) / gpu_hours
            if fresh_complete and gpu_hours > 0
            else None,
            "events_per_allocated_gpu_hour": sum(r["committed_events"] for r in rows) / gpu_hours
            if fresh_complete and gpu_hours > 0 and all("committed_events" in r for r in rows)
            else None,
            "world_steps_per_allocated_gpu_hour": sum(r["integrated_world_steps"] for r in rows)
            / gpu_hours
            if fresh_complete and gpu_hours > 0 and all("integrated_world_steps" in r for r in rows)
            else None,
        },
        "allocation_clock_source": registration["allocation_clock_source"],
        "gpu_hours_scope": (
            "allocation start through result aggregation; reconcile final charge with Slurm receipt"
        ),
        "arms": aggregate(rows),
        "experimental_validation": False,
        "automatic_followup": False,
    }
    write(root / "result.json", finished)
    write(
        root / "cost-profile.json",
        {
            "result_sha256": sha(root / "result.json"),
            "includes_compile_and_io": True,
            "seconds_per_world": {
                name: sorted(arm["task_seconds_per_world"])[len(arm["task_seconds_per_world"]) // 2]
                for name, arm in finished["arms"].items()
            },
            "automatic_reallocation": False,
        },
    )
    write(
        root
        / {"completed": "completion.json", "paused": "paused.json", "failed": "failure.json"}[
            status
        ],
        {
            "status": status,
            "finished_time": ended,
            "result_sha256": sha(root / "result.json"),
            "allocated_gpu_hours": finished["allocated_gpu_hours"],
            "utilization_gate": measured["gate"],
        },
    )
    return finished


def register(args):
    registered_start = time.time()
    configure_caches()
    if args.detach and os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Run in foreground inside Slurm; sbatch already detaches the allocation")
    selected = devices(args.devices, args.allocated_gpus)
    inherited, parents, parent = {}, {}, None
    if args.command == "resume":
        old = args.input.resolve()
        previous = read(old / "result.json")
        old_registration = read(old / "registration.json")
        if previous["registration_sha256"] != sha(old / "registration.json"):
            raise ValueError("Parent registration changed")
        terminal = next(
            (
                old / n
                for n in ("completion.json", "paused.json", "failure.json")
                if (old / n).exists()
            ),
            None,
        )
        if terminal is None or read(terminal).get("result_sha256") != sha(old / "result.json"):
            raise ValueError("Resume requires an authenticated terminal result")
        if previous["status"] != "paused":
            raise ValueError(
                "Only a checkpointed pause may resume; "
                "failed scientific tasks require a new explicit run"
            )
        if old_registration["sources_sha256"] != sources():
            raise ValueError("Resume using the parent's frozen source")
        definition = old_registration["definition"]
        inherited, parents = previous["result_records"], previous["parent_checkpoints"]
        parent = {"path": str(old), "result_sha256": sha(old / "result.json")}
    else:
        definition = read(args.input)
    planned = plan(definition, len(selected))
    for task in planned["tasks"]:
        raw = task["definition"]
        component = {
            "ionic_worlds@1": "simulation",
            "assembly_regulated_cell@1": "ionic",
            "assembly_regulated_cluster@1": "ionic",
        }.get(raw["model"])
        if component and raw[component]["execution"]["backend"] != "gpu":
            raise ValueError("GPU ensembles require an explicit GPU ionic definition")
    output = args.output.resolve()
    if not within_output_root(output) or output.exists():
        raise ValueError(
            "Require a new directory within CELLS_OUTPUT_ROOT (default /mnt/workspaces)"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < planned["output_bytes_bound"] + 4 * 1024**3:
        raise ValueError("Output bound would consume the 4 GiB disk reserve")
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) < planned["worker_processes"] * definition["execution"]["worker_threads"]:
        raise ValueError("Not enough allocated CPU cores for the requested workers")
    output.mkdir()
    (output / "tasks").mkdir()
    (output / "source").mkdir()
    shutil.copytree(
        Path(__file__).parents[1],
        output / "source/cells",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    registration = {
        "definition": definition,
        "plan": planned,
        "devices": selected,
        "created_time": time.time(),
        "sources_sha256": sources(),
        "parent": parent,
        "inherited_results": inherited,
        "parent_checkpoints": parents,
        "allocation_start_time": float(os.environ.get("SLURM_JOB_START_TIME", registered_start)),
        "allocation_end_time": float(os.environ["SLURM_JOB_END_TIME"])
        if os.environ.get("SLURM_JOB_END_TIME")
        else None,
        "allocation_clock_source": "SLURM_JOB_START_TIME"
        if os.environ.get("SLURM_JOB_START_TIME")
        else "local_launcher_start",
        "max_allocated_gpu_hours": len(selected)
        * definition["execution"]["max_wall_seconds"]
        / 3600,
    }
    if (
        not math.isfinite(registration["allocation_start_time"])
        or registration["allocation_start_time"] > time.time()
    ):
        raise ValueError("Invalid allocation start time")
    write(output / "registration.json", registration)
    if args.detach:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(output / "source")
        with (
            (output / "stdout.log").open("x") as stdout,
            (output / "stderr.log").open("x") as stderr,
        ):
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "cells.ensemble", "_controller", str(output)],
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
        receipt = {
            "status": "launched",
            "pid": process.pid,
            "output": str(output),
            "allocated_gpus": len(selected),
            "max_allocated_gpu_hours": registration["max_allocated_gpu_hours"],
        }
        write(output / "launch.json", receipt)
        return receipt
    return controller(output)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cells ensemble", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preview = commands.add_parser("plan")
    preview.add_argument("input", type=Path)
    preview.add_argument("--allocated-gpus", type=int, default=None)
    preview.add_argument("--jupiter-nodes", type=int, choices=range(1, 5))
    tune = commands.add_parser("balance")
    tune.add_argument("input", type=Path)
    tune.add_argument("--profile", type=Path, required=True)
    tune.add_argument("--output", type=Path, required=True)
    tune.add_argument("--target-task-seconds", type=float, default=30.0)
    tune.add_argument("--allocated-gpus", type=int, default=4)
    for name in ("run", "resume"):
        command = commands.add_parser(name)
        command.add_argument("input", type=Path)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--devices", default="all")
        command.add_argument("--allocated-gpus", type=int, required=True)
        command.add_argument("--detach", action="store_true")
    for name in ("status", "_controller"):
        command = commands.add_parser(name)
        command.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            if args.jupiter_nodes is not None:
                from cells.ensemble.plan import jupiter_plan

                if args.allocated_gpus not in (None, 4 * args.jupiter_nodes):
                    raise ValueError("JUPITER allocations must include all four GPUs per node")
                result = jupiter_plan(read(args.input), args.jupiter_nodes)
            else:
                result = plan(
                    read(args.input), 4 if args.allocated_gpus is None else args.allocated_gpus
                )
            result = {k: v for k, v in result.items() if k != "tasks"} | {
                "task_count": len(result["tasks"])
            }
        elif args.command == "balance":
            profile = read(args.profile)
            previous_path = args.profile.parent / "result.json"
            previous = read(previous_path)
            previous_registration = read(args.profile.parent / "registration.json")
            if profile["result_sha256"] != sha(previous_path) or previous["status"] != "completed":
                raise ValueError("Balance from an authenticated completed timing study")
            if previous["registration_sha256"] != sha(args.profile.parent / "registration.json"):
                raise ValueError("Timing study registration changed")
            expected_costs = {
                name: sorted(arm["task_seconds_per_world"])[len(arm["task_seconds_per_world"]) // 2]
                for name, arm in previous["arms"].items()
            }
            if profile["seconds_per_world"] != expected_costs:
                raise ValueError("Timing profile differs from the saved measurements")
            definition = read(args.input)
            old = {a["id"]: a["definition"] for a in previous_registration["definition"]["arms"]}
            if any(old.get(a["id"]) != a["definition"] for a in definition["arms"]):
                raise ValueError(
                    "Timing estimates must match the physical and recording definitions"
                )
            tuned = balance(definition, profile["seconds_per_world"], args.target_task_seconds)
            planned = plan(tuned, args.allocated_gpus)
            if not within_output_root(args.output) or args.output.exists():
                raise ValueError("Require a new balanced definition under the output root")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write(args.output, tuned)
            write(
                args.output.with_suffix(".balance.json"),
                {
                    "timing_profile_sha256": sha(args.profile),
                    "definition_sha256": sha(args.output),
                    "target_task_seconds": args.target_task_seconds,
                    "projected_tail_fraction": planned["projected_tail_fraction"],
                    "timings_are_estimates_at_new_batch_sizes": True,
                    "automatic_launch": False,
                },
            )
            result = {
                "status": "balanced_definition_written",
                "output": str(args.output),
                "tasks": len(planned["tasks"]),
                "projected_tail_fraction": planned["projected_tail_fraction"],
            }
        elif args.command == "status":
            result = next(
                (
                    read(args.output / n)
                    for n in ("result.json", "failure.json", "started.json", "launch.json")
                    if (args.output / n).exists()
                ),
                {"status": "not_started"},
            )
        elif args.command == "_controller":
            try:
                result = controller(args.output)
            except BaseException as exc:
                if not (args.output / "failure.json").exists():
                    write(
                        args.output / "failure.json",
                        {
                            "status": "failed",
                            "error": str(exc),
                            "traceback": traceback.format_exc(),
                        },
                    )
                raise
        else:
            result = register(args)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result.get("status") == "failed" else 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Ensemble error: {exc}", file=sys.stderr)
        return 2
