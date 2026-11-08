#!/usr/bin/env python3
"""GPU platform check and pause/resume ensemble smoke (L4 locally, GH200 on JUPITER).

check       GPU inventory, CPU/GPU affinity, float64, a small JIT benchmark and a
            short spatial_extracellular@2 CPU/GPU screen. Prints one JSON record.
smoke       plan -> run -> SIGUSR1 pause -> resume -> status for a small
            spatial_extracellular@2 GPU ensemble through the ordinary runner.
definition  write that ensemble definition, e.g. larger, for scheduler tests.

Run from any directory on a GPU node, for example:

    python validation/ensemble/jupiter_check.py check --output "$CELLS_OUTPUT_ROOT/check.json"
    python validation/ensemble/jupiter_check.py smoke --output "$CELLS_OUTPUT_ROOT/smoke-01"

The smoke freezes the checkout source with validation/source_snapshot.py and runs
the runner from that snapshot. Records are descriptive platform evidence; a new
device still needs the established numerical qualification.
"""

import argparse
import copy
import csv
import io
import json
import math
import os
import platform
import re
import signal
import socket
import statistics
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT, ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

# CPU/GPU agreement used by the qualified L4 spatial panel and tests/unit/test_gpu_execution.py.
CPU_GPU_ATOL = 2e-12
CPU_GPU_RTOL = 2e-11
SPATIAL_CONFIG = "configs/spatial_kinetic_cluster.json"
QUERY = "index,uuid,name,driver_version,memory.total,compute_cap,pci.bus_id"
ENVIRONMENT = (
    "CELLS_OUTPUT_ROOT",
    "CUDA_VISIBLE_DEVICES",
    "SLURM_JOB_ID",
    "SLURM_JOB_NUM_NODES",
    "SLURM_GPUS_ON_NODE",
    "SLURM_CPUS_ON_NODE",
    "SLURM_JOB_PARTITION",
    "SLURM_JOB_RESERVATION",
    "XLA_FLAGS",
    "XLA_PYTHON_CLIENT_PREALLOCATE",
    "XLA_PYTHON_CLIENT_MEM_FRACTION",
    "XLA_PYTHON_CLIENT_ALLOCATOR",
    "JAX_PLATFORMS",
    "JAX_COMPILATION_CACHE_DIR",
    "LD_LIBRARY_PATH",
    "LOADEDMODULES",
    "OMP_NUM_THREADS",
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def utc():
    return datetime.now(UTC).isoformat()


def clean(value):
    """JSON-safe copy: non-finite floats become strings instead of invalid JSON."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if hasattr(value, "item") and getattr(value, "shape", None) == ():
        return clean(value.item())
    return value


def write_json(path, value):
    with Path(path).open("x") as stream:
        json.dump(clean(value), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def command(arguments, timeout=60):
    try:
        done = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"error": str(exc)}
    return {"returncode": done.returncode, "stdout": done.stdout, "stderr": done.stderr[-4000:]}


def git_provenance():
    def git(*arguments):
        done = command(["git", "-C", str(ROOT), *arguments], timeout=30)
        return done["stdout"] if done.get("returncode") == 0 else None

    status = git("status", "--porcelain=v1", "--untracked-files=all")
    revision, branch = git("rev-parse", "HEAD"), git("rev-parse", "--abbrev-ref", "HEAD")
    return {
        "checkout": str(ROOT),
        "revision": revision.strip() if revision else None,
        "branch": branch.strip() if branch else None,
        "dirty": None if status is None else bool(status.strip()),
        "status_porcelain": status,
    }


def cpulist(values):
    """Compress sorted CPU ids to a Linux cpulist string."""
    ranges, values = [], sorted(values)
    for value in values:
        if ranges and value == ranges[-1][1] + 1:
            ranges[-1][1] = value
        else:
            ranges.append([value, value])
    return ",".join(f"{a}-{b}" if a != b else str(a) for a, b in ranges)


def parse_cpulist(text):
    if not text or not re.fullmatch(r"[0-9,\-]+", text):
        return None
    result = set()
    for part in text.split(","):
        low, _, high = part.partition("-")
        result.update(range(int(low), int(high or low) + 1))
    return result


def meminfo(field):
    try:
        for row in Path("/proc/meminfo").read_text().splitlines():
            if row.startswith(field + ":"):
                return int(row.split()[1]) * 1024
    except OSError:
        pass
    return None


def host():
    affinity = sorted(os.sched_getaffinity(0))
    return {
        "hostname": socket.gethostname(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "libc": "-".join(platform.libc_ver()),
        "python": sys.version,
        "executable": sys.executable,
        "cpu_count": os.cpu_count(),
        "cpu_affinity": cpulist(affinity),
        "cpu_affinity_count": len(affinity),
        "memory_total_bytes": meminfo("MemTotal"),
        "memory_available_bytes": meminfo("MemAvailable"),
    }


def environment():
    return {name: os.environ.get(name) for name in ENVIRONMENT}


def packages():
    from importlib import metadata

    found = {}
    for dist in metadata.distributions():
        name = (dist.metadata.get("Name") or "").lower().replace("_", "-")
        if name in {"jax", "jaxlib", "numpy", "scipy", "ml-dtypes", "opt-einsum", "pytest"}:
            found[name] = dist.version
        elif name.startswith(("jax-cuda", "nvidia-")):
            found[name] = dist.version
    return dict(sorted(found.items()))


def topology_affinity(text):
    """CPU/NUMA affinity per GPU from ``nvidia-smi topo -m`` (tab separated)."""
    lines = [ANSI.sub("", line) for line in text.splitlines()]
    header = next((line.split("\t") for line in lines if "CPU Affinity" in line), None)
    if header is None:
        return {}
    columns = {name.strip(): i for i, name in enumerate(header)}
    rows = {}
    for line in lines:
        fields = line.split("\t")
        if not re.fullmatch(r"GPU\d+", fields[0].strip()):
            continue

        def field(name, fields=fields):
            index = columns.get(name)
            value = fields[index].strip() if index is not None and index < len(fields) else ""
            return value or None

        cpus = field("CPU Affinity")
        rows[fields[0].strip()] = {
            "cpu_affinity": cpus if parse_cpulist(cpus) is not None else None,
            "numa_affinity": field("NUMA Affinity"),
        }
    return rows


def gpu_inventory():
    listed = command(["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"])
    topology = command(["nvidia-smi", "topo", "-m"])
    record = {"gpus": [], "topology_text": topology.get("stdout")}
    if listed.get("returncode") != 0:
        record["error"] = listed.get("error") or listed.get("stderr")
        return record
    affinity = topology_affinity(topology.get("stdout") or "")
    for row in csv.reader(io.StringIO(listed["stdout"])):
        if row:
            gpu = dict(zip(QUERY.split(","), (value.strip() for value in row), strict=True))
            gpu.update(affinity.get(f"GPU{gpu['index']}", {}))
            record["gpus"].append(gpu)
    return record


def visible_gpus(inventory):
    """GPUs in the order the ensemble runner selects them with ``--devices all``."""
    rows = inventory["gpus"]
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visible is None:
        return rows
    selected = []
    for token in visible.split(","):
        matches = [r for r in rows if token.strip() in (r["uuid"], r["index"])]
        if len(matches) == 1:
            selected.append(matches[0])
    return selected


def affinity_plan(inventory, workers_per_gpu=1, worker_threads=1):
    """Compare the runner's per-GPU CPU groups (cells.ensemble.cli) with GPU topology."""
    gpus = visible_gpus(inventory)
    affinity = sorted(os.sched_getaffinity(0))
    rows, matches = [], []
    for i, gpu in enumerate(gpus):
        group = affinity[i * len(affinity) // len(gpus) : (i + 1) * len(affinity) // len(gpus)]
        local = parse_cpulist(gpu.get("cpu_affinity"))
        match = None if local is None else set(group) <= local
        matches.append(match)
        rows.append(
            {
                "gpu_index": gpu["index"],
                "runner_cpu_group": cpulist(group),
                "topology_cpu_affinity": gpu.get("cpu_affinity"),
                "group_within_topology": match,
                "fits_workers": len(group) >= workers_per_gpu * worker_threads,
            }
        )
    known = [m for m in matches if m is not None]
    return {
        "gpus": rows,
        "all_groups_within_topology": all(known) if known else None,
        "rule": "runner splits sorted process affinity evenly across selected GPUs",
    }


def timed(function, *arguments, repeats=5):
    import jax

    started = time.perf_counter()
    output = jax.block_until_ready(function(*arguments))
    first = time.perf_counter() - started
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        output = jax.block_until_ready(function(*arguments))
        samples.append(time.perf_counter() - started)
    return output, {"first_call_seconds": first, "warm_median_seconds": statistics.median(samples)}


def device_check(device, *, elements, matrix, repeats):
    import jax
    import jax.numpy as jnp
    import numpy as np

    row = {"id": device.id, "kind": device.device_kind, "platform": device.platform}
    try:
        stats = device.memory_stats() or {}
        row["memory_bytes_limit"] = stats.get("bytes_limit")
    except Exception as exc:  # Not all PJRT builds expose memory statistics.
        row["memory_stats_error"] = str(exc)
    one = jax.device_put(np.float64(1.0), device)
    nudged = float(jax.jit(lambda v, e: v + e)(one, jax.device_put(np.float64(2.0**-52), device)))
    tenths = jax.device_put(np.full(1_000_000, 0.1), device)
    total = float(jax.jit(jnp.sum)(tenths))
    exact = math.fsum([0.1] * 1_000_000)
    row["float64"] = {
        "x64_enabled": bool(jax.config.jax_enable_x64),
        "default_float_dtype": str(jnp.asarray(1.0).dtype),
        "unit_roundoff_preserved": nudged == 1.0 + 2.0**-52,
        "sum_relative_error": abs(total - exact) / exact,
        "array_on_device": one.devices() == {device},
    }
    row["float64"]["pass"] = (
        row["float64"]["x64_enabled"]
        and row["float64"]["default_float_dtype"] == "float64"
        and row["float64"]["unit_roundoff_preserved"]
        and row["float64"]["sum_relative_error"] < 1e-12
        and row["float64"]["array_on_device"]
    )
    rng = np.random.default_rng(20261108)
    start = rng.uniform(0.0, 1.0, elements)
    steps = 64

    @jax.jit
    def relax(values):
        return jax.lax.fori_loop(0, steps, lambda _, v: v + 1e-3 * jnp.sin(v), values)

    began = time.perf_counter()
    on_device = jax.block_until_ready(jax.device_put(start, device))
    upload = time.perf_counter() - began
    relaxed, stream = timed(relax, on_device, repeats=repeats)
    began = time.perf_counter()
    relaxed_host = np.asarray(relaxed)
    download = time.perf_counter() - began
    reference = start[:4096].copy()
    for _ in range(steps):
        reference = reference + 1e-3 * np.sin(reference)
    stream_error = float(np.max(np.abs(relaxed_host[:4096] - reference) / np.abs(reference)))
    a = jax.device_put(rng.standard_normal((matrix, matrix)), device)
    b = jax.device_put(rng.standard_normal((matrix, matrix)), device)
    product = jax.jit(lambda x, y: jnp.matmul(x, y, precision="highest"))
    result, gemm = timed(product, a, b, repeats=repeats)
    expected = np.asarray(a)[:128] @ np.asarray(b)
    gemm_error = float(
        np.linalg.norm(np.asarray(result)[:128] - expected) / np.linalg.norm(expected)
    )
    nbytes = start.nbytes
    row["benchmark"] = {
        "stream": stream
        | {
            "elements": elements,
            "fused_steps": steps,
            "effective_GBps": 2 * steps * nbytes / stream["warm_median_seconds"] / 1e9,
            "max_relative_error_vs_numpy": stream_error,
        },
        "dgemm": gemm
        | {
            "n": matrix,
            "GFLOPs": 2 * matrix**3 / gemm["warm_median_seconds"] / 1e9,
            "relative_error_vs_numpy": gemm_error,
        },
        "transfer": {
            "bytes": nbytes,
            "host_to_device_GBps": nbytes / upload / 1e9,
            "device_to_host_GBps": nbytes / download / 1e9,
        },
    }
    row["benchmark"]["pass"] = stream_error < 1e-12 and gemm_error < 1e-12
    return row


def spatial_definitions(root=ROOT):
    """Qualified finest-step GPU arms of the spatial CPU/L4 panel (spatial_matrix.py inputs)."""
    base = json.loads((Path(root) / SPATIAL_CONFIG).read_text())
    if base["model"]["id"] != "spatial_extracellular@2":
        raise ValueError(f"{SPATIAL_CONFIG} no longer defines spatial_extracellular@2")
    base["execution"].update(backend="gpu", dt=2.5e-5)
    release = copy.deepcopy(base)
    for control in release["experiment"]["membrane_controls"]:
        control["pump"] = [
            {"multiplier": 1.0, "time": 0.0},
            {"multiplier": 0.0, "time": 0.005},
            {"multiplier": 1.0, "time": 0.01},
        ]
    return {"baseline": base, "pump_release": release}


def compare_arrays(actual, expected, atol=CPU_GPU_ATOL, rtol=CPU_GPU_RTOL):
    import numpy as np

    actual, expected = np.asarray(actual), np.asarray(expected)
    if actual.shape != expected.shape or actual.dtype != expected.dtype:
        return {"comparable": False, "within_tolerance": False, "bitwise_equal": False}
    if actual.size == 0:
        return {"comparable": True, "within_tolerance": True, "bitwise_equal": True}
    if actual.dtype.kind not in "fc":
        equal = bool(np.array_equal(actual, expected))
        return {"comparable": True, "within_tolerance": equal, "bitwise_equal": equal}
    difference = np.abs(actual - expected)
    scale = np.abs(expected)
    relative = np.divide(difference, scale, out=np.zeros_like(difference), where=scale > 0)
    return {
        "comparable": True,
        "within_tolerance": bool(np.all(difference <= atol + rtol * scale)),
        "bitwise_equal": bool(np.array_equal(actual, expected, equal_nan=True)),
        "max_abs": float(difference.max()),
        "max_rel": float(relative.max()),
    }


def merge(rows):
    rows = list(rows)
    return {
        "arrays": len(rows),
        "comparable": all(r["comparable"] for r in rows),
        "within_tolerance": all(r["within_tolerance"] for r in rows),
        "bitwise_equal": all(r["bitwise_equal"] for r in rows),
        "max_abs": max((r.get("max_abs", 0.0) for r in rows), default=0.0),
        "max_rel": max((r.get("max_rel", 0.0) for r in rows), default=0.0),
    }


def model_screen():
    """Short qualified spatial definition on CPU and GPU in one process; not qualification."""
    import jax
    import numpy as np

    from cells.core.runner import run
    from cells.core.specs import parse_spec

    raw = spatial_definitions()["pump_release"]
    runs = {}
    for backend in ("cpu", "gpu"):
        data = copy.deepcopy(raw)
        data["execution"]["backend"] = backend
        began = time.perf_counter()
        result = run(parse_spec(data))
        jax.block_until_ready(result.final.state)
        runs[backend] = (result, time.perf_counter() - began)
    cpu, gpu = runs["cpu"][0], runs["gpu"][0]
    history = merge(
        compare_arrays(np.asarray(g), np.asarray(c))
        for g, c in zip(gpu.history, cpu.history, strict=True)
    )
    final = merge(
        compare_arrays(np.asarray(g), np.asarray(c))
        for g, c in zip(gpu.final.state, cpu.final.state, strict=True)
    )
    platforms = sorted(
        {d.platform for x in gpu.final.state for d in getattr(x, "devices", lambda: ())()}
    )
    return {
        "model": raw["model"]["id"],
        "definition": f"{SPATIAL_CONFIG} pump_release arm, dt 2.5e-05 s, end 0.02 s",
        "steps": int(gpu.final.step_index),
        "seconds_including_compile": {k: v[1] for k, v in runs.items()},
        "gpu_state_platforms": platforms,
        "history_gpu_vs_cpu": history,
        "final_state_gpu_vs_cpu": final,
        "tolerance": {"atol": CPU_GPU_ATOL, "rtol": CPU_GPU_RTOL},
        "diagnostics": {
            k: {"cpu": cpu.diagnostics.get(k), "gpu": v} for k, v in gpu.diagnostics.items()
        },
        "pass": history["within_tolerance"]
        and final["within_tolerance"]
        and platforms in (["cuda"], ["gpu"]),
        "scope": "One short CPU/GPU screen on this host; not numerical qualification",
    }


def check(args):
    from cells.core.output_paths import configure_caches

    began = time.time()
    if args.output is not None and args.output.exists():
        raise SystemExit("--output must name a new file")
    if os.environ.get("CELLS_OUTPUT_ROOT"):
        configure_caches()
    inventory = gpu_inventory()
    record = {
        "kind": "cells.gpu_platform_check@1",
        "started_utc": utc(),
        "provenance": git_provenance(),
        "host": host(),
        "environment": environment(),
        "packages": packages(),
        "nvidia": inventory,
        "runner_affinity": affinity_plan(inventory, args.workers_per_gpu, args.worker_threads),
        "warnings": [],
    }
    library_path = os.environ.get("LD_LIBRARY_PATH", "")
    if re.search(r"cuda|cudnn|nccl", library_path, re.IGNORECASE):
        record["warnings"].append(
            "LD_LIBRARY_PATH names CUDA libraries; they can override the pip CUDA wheels"
        )
    import jax

    jax.config.update("jax_enable_x64", True)
    record["jax_environment"] = jax.print_environment_info(return_string=True)
    try:
        gpus = jax.devices("gpu")
    except RuntimeError as exc:
        gpus, record["jax_gpu_error"] = [], str(exc)
    record["devices"] = []
    for device in gpus:
        try:
            row = device_check(
                device, elements=args.elements, matrix=args.matrix, repeats=args.repeats
            )
        except Exception as exc:
            row = {"id": device.id, "error": repr(exc), "traceback": traceback.format_exc()}
            row |= {"float64": {"pass": False}, "benchmark": {"pass": False}}
        record["devices"].append(row)
    record["model_screen"] = None
    if gpus and not args.skip_model:
        try:
            record["model_screen"] = model_screen()
        except Exception as exc:
            record["model_screen"] = {"pass": False, "error": repr(exc)}
            record["model_screen"]["traceback"] = traceback.format_exc()
    checks = {
        "gpus_visible": bool(gpus),
        "gpu_count_matches_nvidia_smi": len(gpus) == len(visible_gpus(inventory)),
        "float64": bool(gpus) and all(d["float64"]["pass"] for d in record["devices"]),
        "benchmark_agrees_with_numpy": bool(gpus)
        and all(d["benchmark"]["pass"] for d in record["devices"]),
        "model_screen": None if record["model_screen"] is None else record["model_screen"]["pass"],
        "runner_affinity_within_topology": record["runner_affinity"]["all_groups_within_topology"],
    }
    if args.expect_gpus is not None:
        checks["expected_gpu_count"] = len(gpus) == args.expect_gpus
    record["checks"] = checks
    record["status"] = "pass" if all(v is not False for v in checks.values()) else "fail"
    record["elapsed_seconds"] = time.time() - began
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.output, record)
    print(json.dumps(clean(record), indent=2, sort_keys=True, allow_nan=False))
    return 0 if record["status"] == "pass" else 1


# --------------------------------------------------------------------------- smoke


def smoke_definition(source, *, worlds_per_arm, batch_worlds, workers_per_gpu, max_wall_seconds):
    arms = []
    for name, simulation in spatial_definitions(source).items():
        arms.append(
            {
                "id": name,
                "definition": {
                    "model": "ionic_worlds@1",
                    "simulation": simulation,
                    "window_steps": 200,
                    "max_working_bytes": 2 * 1024**3,
                    "max_output_bytes": 256 * 1024**2,
                    "max_wall_seconds": 600,
                },
                "worlds": worlds_per_arm,
                "batch_worlds": batch_worlds,
                "seconds_per_world": None,
            }
        )
    return {
        "kind": "ionic_ensemble@1",
        "seed": 20261108,
        "arms": arms,
        "execution": {
            "max_wall_seconds": max_wall_seconds,
            "max_output_bytes": 4 * 1024**3,
            "target_gpu_utilization_pct": 70,
            "worker_threads": 1,
            "workers_per_gpu": workers_per_gpu,
        },
    }


def snapshot_files():
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        + ["--", "src/cells", SPATIAL_CONFIG, "validation/ensemble/jupiter_check.py"],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    names = sorted({os.fsdecode(n) for n in listed.split(b"\0") if n})
    names = [n for n in names if (ROOT / n).is_file() and "__pycache__" not in n]
    return {name: name for name in names}


def leg_summary(directory):
    path = directory / "result.json"
    if not path.exists():
        return {"result": None}
    result = json.loads(path.read_text())
    keys = ("full_job_utilization", "after_all_workers_warmed")
    return {
        "status": result["status"],
        "elapsed_seconds": result["elapsed_seconds"],
        "started_time": result["started_time"],
        "finished_time": result["finished_time"],
        "allocated_gpu_hours": result["allocated_gpu_hours"],
        "completed_tasks": len(result["result_records"]),
        "checkpointed_tasks": len(result["parent_checkpoints"]),
        "missing_tasks": len(result["missing_tasks"]),
        "failed_tasks": result["failed_tasks"],
        "worker_abnormal_exits": result["worker_abnormal_exits"],
        "completed_worlds": result["completed_worlds"],
        "registered_worlds": result["registered_worlds"],
        "throughput": result["throughput"],
        **{k: result[k] for k in keys},
    }


def busy_samples(directory, minimum=10):
    """Every selected GPU has numeric busy samples in at least 90% of the runner's rows."""
    path = directory / "gpu-utilization.jsonl"
    if not path.exists():
        return False
    uuids = [
        g["uuid"] for g in json.loads((directory / "registration.json").read_text())["devices"]
    ]
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    numeric = [
        all(isinstance(r["gpus"].get(u, {}).get("utilization_pct"), (int, float)) for u in uuids)
        for r in rows
    ]
    return len(rows) >= minimum and sum(numeric) >= 0.9 * len(rows)


def cohort(task_directory):
    """World id -> (arrays, clock) for a completed task checkpoint, numpy only."""
    import numpy as np

    root = task_directory / "checkpoint/cohort"
    manifest = json.loads((root / "manifest.json").read_text())
    worlds = {}
    for row in manifest["worlds"]:
        clock = json.loads((root / row["path"] / "manifest.json").read_text())["clock"]
        with np.load(root / row["path"] / "state.npz", allow_pickle=False) as data:
            worlds[row["world_id"]] = ({k: data[k] for k in data.files}, clock)
    return worlds


def compare_worlds(candidate, reference):
    arrays, clock = candidate
    expected, expected_clock = reference
    if set(arrays) != set(expected):
        return {"comparable": False, "within_tolerance": False, "bitwise_equal": False}
    row = merge(compare_arrays(arrays[k], expected[k]) for k in sorted(arrays))
    row["clock_equal"] = clock == expected_clock
    row["within_tolerance"] &= row["clock_equal"]
    return row


def exactness(first, second):
    """Deterministic replicas of one arm must agree across uninterrupted and resumed tasks."""
    registration = json.loads((second / "registration.json").read_text())
    arm_of = {t["id"]: t["arm"] for t in registration["plan"]["tasks"]}
    resumed = set(registration["parent_checkpoints"])
    inherited = set(registration["inherited_results"])
    groups = {"leg1_uninterrupted": {}, "leg2_uninterrupted": {}, "paused_then_resumed": {}}
    for task, arm in arm_of.items():
        if task in inherited:
            groups["leg1_uninterrupted"].setdefault(arm, []).append(first / "tasks" / task)
        elif task in resumed:
            groups["paused_then_resumed"].setdefault(arm, []).append(second / "tasks" / task)
        else:
            groups["leg2_uninterrupted"].setdefault(arm, []).append(second / "tasks" / task)
    report = {"tolerance": {"atol": CPU_GPU_ATOL, "rtol": CPU_GPU_RTOL}, "arms": {}}
    for arm in sorted(set(arm_of.values())):
        references = groups["leg1_uninterrupted"].get(arm) or groups["leg2_uninterrupted"].get(arm)
        if not references:
            report["arms"][arm] = {"reference": None}
            continue
        reference_worlds = cohort(references[0])
        reference = reference_worlds[min(reference_worlds)]
        row = {"reference_task": references[0].name}
        for group, folders in groups.items():
            worlds = [w for folder in folders.get(arm, []) for w in cohort(folder).values()]
            if worlds:
                row[group] = merge(compare_worlds(w, reference) for w in worlds) | {
                    "tasks": len(folders.get(arm, [])),
                    "worlds": len(worlds),
                }
        report["arms"][arm] = row
    rows = [report["arms"][a][g] for a in report["arms"] for g in groups if g in report["arms"][a]]
    paused = [
        r for a in report["arms"].values() for g, r in a.items() if g == "paused_then_resumed"
    ]
    report["resumed_tasks_compared"] = sum(r["tasks"] for r in paused)
    report["within_tolerance"] = bool(paused) and all(r["within_tolerance"] for r in rows)
    report["bitwise_equal"] = bool(paused) and all(r["bitwise_equal"] for r in rows)
    return report


class Legs:
    """Run runner commands in the foreground and forward scheduler stop signals."""

    def __init__(self, out, env):
        self.out, self.env, self.child, self.external = out, env, None, None
        for number in (signal.SIGUSR1, signal.SIGTERM):
            signal.signal(number, self.forward)

    def forward(self, number, _frame):
        self.external = signal.Signals(number).name
        if self.child is not None and self.child.poll() is None:
            self.child.send_signal(signal.SIGUSR1)

    def start(self, name, arguments):
        with (
            (self.out / f"{name}.stdout.json").open("x") as stdout,
            (self.out / f"{name}.stderr.log").open("x") as stderr,
        ):
            self.child = subprocess.Popen(
                arguments, env=self.env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr
            )
        return self.child

    def finish(self, timeout):
        try:
            return self.child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.child.send_signal(signal.SIGUSR1)
            try:
                return self.child.wait(timeout=120)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait()
                raise RuntimeError(f"Runner exceeded {timeout} s and was killed") from None


def run_smoke(args, out, record):
    from validation import source_snapshot

    deadline = time.monotonic() + args.timeout
    snapshot = source_snapshot.freeze(ROOT, out / "source", snapshot_files())
    record["snapshot"] = {
        "path": str(out / "source"),
        "git_revision": snapshot["git_revision"],
        "files": len(snapshot["files"]),
    }
    allocated = args.allocated_gpus
    definition = smoke_definition(
        out / "source",
        worlds_per_arm=args.worlds_per_arm or 16 * allocated,
        batch_worlds=args.batch_worlds,
        workers_per_gpu=args.workers_per_gpu,
        max_wall_seconds=args.max_wall_seconds,
    )
    write_json(out / "definition.json", definition)
    env = os.environ.copy()
    env.pop("JAX_PLATFORMS", None)
    env.update(PYTHONPATH=str(out / "source/src"), PYTHONDONTWRITEBYTECODE="1")
    runner = [sys.executable, "-B", "-m", "cells.ensemble"]
    planned = subprocess.run(
        runner + ["plan", str(out / "definition.json"), "--allocated-gpus", str(allocated)],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    (out / "plan.stderr.log").write_text(planned.stderr)
    if planned.returncode:
        raise RuntimeError("Plan refused: " + planned.stderr[-2000:])
    (out / "plan.json").write_text(planned.stdout)
    plan = json.loads(planned.stdout)
    tasks = plan["task_count"]
    nodes_plan = None
    if tasks >= 4 * args.workers_per_gpu:
        offline = subprocess.run(
            runner + ["plan", str(out / "definition.json"), "--jupiter-nodes", "1"],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        (out / "jupiter-plan.json").write_text(offline.stdout or offline.stderr)
        nodes_plan = {"returncode": offline.returncode, "path": str(out / "jupiter-plan.json")}
    counters = None
    if args.dcgm_root is not None:
        from validation.ensemble.qualification_metrics import (
            GpuQualificationMetrics,
            registration,
        )

        uuid = visible_gpus(gpu_inventory())[0]["uuid"]
        settings = registration(args.dcgm_root.resolve(), uuid, args.timeout + 300)
        counters = GpuQualificationMetrics(out / "telemetry", settings)
        counters.start()
    legs, first, second = Legs(out, env), out / "first", out / "resumed"
    timeline = {"first_started": time.time()}
    try:
        legs.start(
            "first",
            runner
            + ["run", str(out / "definition.json"), "--output", str(first)]
            + ["--devices", args.devices, "--allocated-gpus", str(allocated)],
        )
        while legs.child.poll() is None and time.monotonic() < deadline:
            folders = [p for p in (first / "tasks").glob("task-*")] if first.exists() else []
            done = [p for p in folders if (p / "result.json").exists()]
            running = [p for p in folders if (p / "status.json").exists() and p not in done]
            if len(done) >= args.pause_after_results and running and legs.external is None:
                if len(folders) < tasks or len(done) + len(running) == tasks:
                    timeline["pause_signal"] = time.time()
                    timeline["pause_state"] = {
                        "completed": len(done),
                        "running": len(running),
                        "unstarted": tasks - len(folders),
                    }
                    legs.child.send_signal(signal.SIGUSR1)
                    break
            time.sleep(0.25)
        timeline["first_exit_code"] = legs.finish(max(60, deadline - time.monotonic()))
        timeline["first_exited"] = time.time()
        if "pause_signal" not in timeline:
            raise RuntimeError("Run finished or timed out before a pause could be exercised")
        if legs.external is not None:
            raise RuntimeError(f"Stopped by {legs.external}; resume leg not started")
        timeline["resume_started"] = time.time()
        legs.start(
            "resumed",
            runner
            + ["resume", str(first), "--output", str(second)]
            + ["--devices", args.devices, "--allocated-gpus", str(allocated)],
        )
        timeline["resume_exit_code"] = legs.finish(max(60, deadline - time.monotonic()))
        timeline["resume_exited"] = time.time()
    finally:
        telemetry = None
        if counters is not None:
            warms = [json.loads(p.read_text())["time"] for p in first.glob("worker-*-warm.json")]
            telemetry = counters.finish(
                warm_time=max(warms) if warms else None,
                warm_unavailable_reason=None if warms else "no worker warmed in the first leg",
            )
    status = subprocess.run(
        runner + ["status", str(second)], env=env, capture_output=True, text=True, timeout=120
    )
    (out / "status.json").write_text(status.stdout)
    first_leg, second_leg = leg_summary(first), leg_summary(second)
    first_leg["pause_signal_to_exit_seconds"] = timeline["first_exited"] - timeline["pause_signal"]
    paused = (
        json.loads((first / "paused.json").read_text())
        if (first / "paused.json").exists()
        else None
    )
    report = exactness(first, second) if (second / "completion.json").exists() else None
    if telemetry is not None:
        from validation.ensemble.gpu_counters import summarize
        from validation.ensemble.qualification_metrics import busy_summary

        samples = [
            json.loads(line)
            for line in (out / "telemetry/gpu-utilization.jsonl").read_text().splitlines()
        ]
        rows = [
            json.loads(line)
            for line in (out / "telemetry/gpu-counters.jsonl").read_text().splitlines()
        ]
        for leg, summary in (("first", first_leg), ("resumed", second_leg)):
            directory = out / leg
            warm = [json.loads(p.read_text())["time"] for p in directory.glob("worker-*-warm.json")]
            began, ended = summary["started_time"], summary["finished_time"]
            began = max(began, telemetry["started_time"])
            summary["dcgm"] = summarize(rows, began, ended)
            summary["gpu_busy_observed"] = busy_summary(
                samples, telemetry["gpu_uuid"], began, ended
            )
            if warm and max(warm) < ended:
                summary["dcgm_after_warm"] = summarize(rows, max(warm), ended)
    checks = {
        "plan": tasks >= allocated * args.workers_per_gpu,
        "jupiter_one_node_plan": None if nodes_plan is None else nodes_plan["returncode"] == 0,
        "first_leg_paused": first_leg.get("status") == "paused"
        and paused is not None
        and first_leg["checkpointed_tasks"] > 0
        and first_leg["completed_tasks"] > 0,
        "resume_completed": second_leg.get("status") == "completed"
        and second_leg["completed_worlds"] == second_leg["registered_worlds"] == plan["worlds"],
        "status_command": status.returncode == 0
        and json.loads(status.stdout or "{}").get("status") == "completed",
        "gpu_busy_recorded": all(busy_samples(out / leg) for leg in ("first", "resumed")),
        "sm_active_recorded": None
        if telemetry is None
        else telemetry["whole_job"]["hardware"]["fields"]["sm_active"]["coverage_pass"],
        "resume_within_tolerance": report is not None and report["within_tolerance"],
    }
    return {
        "kind": "cells.gpu_ensemble_smoke@1",
        "status": "pass" if all(v is not False for v in checks.values()) else "fail",
        "checks": checks,
        "resume_bitwise_equal": None if report is None else report["bitwise_equal"],
        "physical_model": "spatial_extracellular@2",
        "arms": [a["id"] for a in definition["arms"]],
        "allocated_gpus": allocated,
        "plan": {
            k: plan[k] for k in ("task_count", "worlds", "worker_processes", "output_bytes_bound")
        },
        "jupiter_one_node_plan": nodes_plan,
        "timeline": timeline,
        "first_leg": first_leg,
        "resume_leg": second_leg,
        "allocated_gpu_hours_total": sum(
            leg.get("allocated_gpu_hours") or 0 for leg in (first_leg, second_leg)
        ),
        "resume_exactness": report,
        "dcgm_telemetry": telemetry,
        "scope": (
            "Runner pause/resume and telemetry smoke on deterministic replicas of the qualified "
            "spatial arms; not a throughput benchmark or numerical qualification"
        ),
    }


def smoke(args):
    from cells.core.output_paths import within_output_root

    out = args.output.resolve()
    if out.exists() or not within_output_root(out):
        raise SystemExit("--output must be a new directory inside CELLS_OUTPUT_ROOT")
    if args.allocated_gpus is None:
        args.allocated_gpus = int(os.environ.get("SLURM_GPUS_ON_NODE") or 0) or len(
            visible_gpus(gpu_inventory())
        )
    out.mkdir(parents=True)
    record = {
        "kind": "cells.gpu_ensemble_smoke_inputs@1",
        "started_utc": utc(),
        "argv": sys.argv,
        "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "provenance": git_provenance(),
        "host": host(),
        "environment": environment(),
        "packages": packages(),
    }
    write_json(out / "inputs.json", record)
    began = time.time()
    try:
        result = run_smoke(args, out, record)
    except BaseException as exc:
        write_json(
            out / "failure.json",
            {
                "status": "failed",
                "error": repr(exc),
                "traceback": traceback.format_exc(),
                "snapshot": record.get("snapshot"),
                "elapsed_seconds": time.time() - began,
            },
        )
        raise
    result |= {
        "provenance": record["provenance"] | {"snapshot": record["snapshot"]},
        "elapsed_seconds": time.time() - began,
        "finished_utc": utc(),
    }
    result["provenance"].pop("status_porcelain", None)
    write_json(out / "result.json", result)
    if result["status"] != "pass":
        write_json(out / "failure.json", {"status": "failed", "checks": result["checks"]})
    print(json.dumps(clean({k: result[k] for k in ("status", "checks", "resume_bitwise_equal")})))
    return 0 if result["status"] == "pass" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    probe = commands.add_parser("check", help="devices, float64, JIT benchmark, model screen")
    probe.add_argument("--output", type=Path, help="also write the JSON record to this new file")
    probe.add_argument("--elements", type=int, default=2**24)
    probe.add_argument("--matrix", type=int, default=4096)
    probe.add_argument("--repeats", type=int, default=5)
    probe.add_argument("--skip-model", action="store_true")
    probe.add_argument("--expect-gpus", type=int)
    probe.add_argument("--workers-per-gpu", type=int, default=2)
    probe.add_argument("--worker-threads", type=int, default=1)
    trial = commands.add_parser("smoke", help="plan, run, SIGUSR1 pause, resume and status")
    trial.add_argument("--output", type=Path, required=True)
    trial.add_argument("--allocated-gpus", type=int)
    trial.add_argument("--devices", default="all")
    trial.add_argument("--worlds-per-arm", type=int, help="default 16 per allocated GPU")
    trial.add_argument("--batch-worlds", type=int, default=4)
    trial.add_argument("--workers-per-gpu", type=int, default=2, choices=(1, 2))
    trial.add_argument("--pause-after-results", type=int, default=1)
    trial.add_argument("--max-wall-seconds", type=int, default=480)
    trial.add_argument("--timeout", type=int, default=570, help="whole smoke, seconds")
    trial.add_argument("--dcgm-root", type=Path, help="extracted DCGM bundle for SM activity")
    template = commands.add_parser("definition", help="write the smoke ensemble definition")
    template.add_argument("--output", type=Path, required=True)
    template.add_argument("--worlds-per-arm", type=int, default=16)
    template.add_argument("--batch-worlds", type=int, default=4)
    template.add_argument("--workers-per-gpu", type=int, default=2, choices=(1, 2))
    template.add_argument("--max-wall-seconds", type=int, default=1800)
    template.add_argument("--seed", type=int, default=20261108)
    args = parser.parse_args(argv)
    if args.command == "definition":
        data = smoke_definition(
            ROOT,
            worlds_per_arm=args.worlds_per_arm,
            batch_worlds=args.batch_worlds,
            workers_per_gpu=args.workers_per_gpu,
            max_wall_seconds=args.max_wall_seconds,
        )
        write_json(args.output, data | {"seed": args.seed})
        print(args.output)
        return 0
    return check(args) if args.command == "check" else smoke(args)


if __name__ == "__main__":
    raise SystemExit(main())
