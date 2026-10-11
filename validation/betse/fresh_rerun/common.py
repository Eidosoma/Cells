"""Fresh-machine evidence utilities; historical registrations are never rewritten."""

import hashlib
import importlib.util
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
VARIANTS = ("pump_leak", "pump_only", "leak_only", "all_blocked", "half_density", "closed_boundary")
RANGES = {
    name: [6.25e-6, 3.125e-6, 1.5625e-6]
    if name == "pump_only"
    else [1.5625e-6, 7.8125e-7, 3.90625e-7]
    for name in VARIANTS
}


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def utc():
    return datetime.now(UTC).isoformat()


def runtime():
    import platform

    return dict(
        python=sys.version,
        machine=platform.machine(),
        packages={d.metadata["Name"]: d.version for d in metadata.distributions()},
    )


def module_path(name):
    path = ROOT / "validation/betse" / name
    sys.path.insert(0, str(path))
    return path


def private(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sources(root=ROOT):
    paths = []
    for name in ("src", "validation/betse", "configs"):
        paths.extend(p for p in (root / name).rglob("*") if p.suffix in (".py", ".json"))
    paths.extend(
        root / p
        for p in (
            "pyproject.toml",
            "requirements-lock.txt",
            "validation/betse/requirements-lock.txt",
        )
    )
    return {str(p.relative_to(root)): sha(p) for p in sorted(paths)}


def inventory(path):
    result = {}
    for p in sorted(path.rglob("*")):
        need(not p.is_symlink(), "Linked evidence: " + str(p))
        if p.is_file():
            result[str(p.relative_to(path))] = sha(p)
    return result


def authenticate_stage(path):
    done = read(path / "completion.json")
    need(
        done["registration_sha256"] == sha(path / "registration.json"), "Stage registration changed"
    )
    for name, expected in done["files_sha256"].items():
        item = path / name
        need(item.resolve().is_relative_to(path.resolve()), "Unsafe stage artifact")
        need(not item.is_symlink() and sha(item) == expected, "Changed stage artifact: " + name)
    return sha(path / "completion.json")


def budget(path):
    sizes = [p.stat().st_size for p in path.rglob("*") if p.is_file()]
    need(max(sizes, default=0) <= 512 * 1024**2, "512 MiB per-file limit")
    need(sum(sizes) <= 8 * 1024**3, "8 GiB campaign artifact limit")
    need(shutil.disk_usage(path).free >= 4 * 1024**3, "4 GiB disk reserve")
    return sum(sizes)


def plan(duration=0.01):
    p = read(ROOT / "validation/betse/pump_matched_pilot/protocol.json")
    for name in (
        "decision",
        "prior_completion_sha256",
        "native_steps_s",
        "native_runs",
        "observer_pairs",
        "gate_order",
        "held_states",
        "mapping_backends",
    ):
        p.pop(name)
    p["resources"] = {k: p["resources"][k] for k in ("max_cells_steps", "max_cells_trace_bytes")}
    p.update(
        schema="cells.fresh_machine_pump_rerun@1",
        scope="Fresh numerical reproduction; no historical artifacts or inherited acceptance",
        duration_s=duration,
        restart_time_s=duration / 2,
        common_times_s=[i * 0.00025 for i in range(round(duration / 0.00025) + 1)],
        native_step_ranges_s=RANGES,
    )
    return p


def env(workspace, cache, *, gpu=False):
    cache.mkdir(parents=True, exist_ok=True)
    result = dict(os.environ)
    result.update(
        PYTHONPATH=str(ROOT / "src"),
        PYTHONDONTWRITEBYTECODE="1",
        TMPDIR=str(cache),
        MPLCONFIGDIR=str(cache / "matplotlib"),
        XDG_CACHE_HOME=str(cache / "xdg"),
        CUDA_CACHE_PATH=str(cache / "cuda"),
        JAX_COMPILATION_CACHE_DIR=str(cache / "jax"),
        JAX_PLATFORMS="cuda,cpu" if gpu else "cpu",
        JAX_ENABLE_X64="1",
        XLA_PYTHON_CLIENT_PREALLOCATE="false",
        XLA_PYTHON_CLIENT_MEM_FRACTION="0.65",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        MPLBACKEND="Agg",
        CELLS_WORKSPACE=str(workspace),
    )
    result.pop("JAX_DISABLE_JIT", None)
    return result
