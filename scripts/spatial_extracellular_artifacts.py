"""Bounded append-only NUM-010 evidence storage and complete source identities.

No integrator or production imports; read-only auditors may use the manifest
helpers without constructing an output directory.
"""

import hashlib
import importlib.metadata
import io
import json
import os
import platform
import sys
import zipfile
from pathlib import Path, PurePosixPath

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "docs/SPATIAL_EXTRACELLULAR_NUMERICS.md",
    "configs/reference/spatial_extracellular_trajectories_v1.json",
    "tests/spatial_extracellular_numerical_data.py",
    "tests/spatial_extracellular_fields.py",
    "tests/spatial_extracellular_numerical_checks.py",
    "tests/reference_spatial_extracellular_dynamics.py",
    "tests/unit/test_spatial_extracellular_dynamics.py",
    "tests/unit/test_spatial_extracellular_artifact_audit.py",
    "scripts/spatial_extracellular_artifacts.py",
    "scripts/qualify_spatial_extracellular_reference.py",
    "scripts/audit_spatial_extracellular_reference.py",
    "tests/__init__.py",
    "docs/SPATIAL_EXTRACELLULAR_SPEC.md",
    "configs/reference/spatial_extracellular_v1.json",
    "tests/reference_spatial_extracellular.py",
    "tests/reference_multispecies.py",
    "reports/spec-009-design-check.json",
    "runs/core-009-2026-09-10/acceptance-02/verification.json",
    "pyproject.toml",
    "requirements-lock.txt",
    "requirements-reference.txt",
)
THREAD_VARIABLES = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
SCIPY_FILES = tuple(
    f"scipy/integrate/_ivp/{name}.py" for name in ("base", "common", "radau", "bdf")
)


def runtime():
    """Inspect distributions without importing an integrator or production module."""
    distribution = importlib.metadata.distribution("scipy")
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": distribution.version,
        "machine": platform.machine(),
        "executable": sys.executable,
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "threads": {key: os.environ.get(key) for key in THREAD_VARIABLES},
        "scipy_implementation_sha256": {
            name: file_sha(distribution.locate_file(name)) for name in SCIPY_FILES
        },
    }


def validate_runtime(saved):
    if (
        saved["python"] != "3.13.5"
        or saved["numpy"] != "2.5.3"
        or saved["scipy"] != "1.18.1"
        or len(saved["cpu_affinity"]) != 1
        or saved["threads"] != dict.fromkeys(THREAD_VARIABLES, "1")
    ):
        raise ValueError("NUM-010 requires its pinned single-CPU reference runtime")
    present = runtime()
    for key in ("python", "numpy", "scipy", "machine", "scipy_implementation_sha256"):
        if saved[key] != present[key]:
            raise ValueError("Pinned numerical dependency or implementation changed")


def attempts(plan):
    return list(plan["references"]) + [
        {"id": f"rk4_{dt:g}", "method": "RK4", "dt_s": dt} for dt in plan["candidate"]["steps_s"]
    ]


def record_names(case_id, attempt_id, *, restart=False):
    base = f"restart/{case_id}" if restart else f"cases/{case_id}/{attempt_id}"
    return base + ".npz", base + ".json"


def load_record(root, case_id, attempt_id, *, restart=False):
    array_name, stats_name = record_names(case_id, attempt_id, restart=restart)
    return load_arrays(Path(root) / array_name), json.loads((Path(root) / stats_name).read_text())


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def sources():
    buffer, hashes = io.BytesIO(), {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in SOURCE_FILES:
            body = (ROOT / name).read_bytes()
            hashes[name] = sha(body)
            archive.writestr(name, body)
    return buffer.getvalue(), hashes


def safe_relative(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or str(p) != name or "\\" in name:
        raise ValueError("Unsafe evidence path")
    return p


class Artifacts:
    def __init__(self, destination, limit):
        self.path = Path(destination)
        self.limit, self.used, self.hashes = limit, 0, {}
        if type(limit) is not int or limit <= 1048576:
            raise ValueError("Invalid evidence budget")
        self.path.mkdir(parents=True, exist_ok=False)

    def write(self, name, payload, *, closing=False):
        safe_relative(name)
        allowed = self.limit if closing else self.limit - 1048576
        if self.used + len(payload) > allowed:
            raise RuntimeError("Spatial artifact budget exhausted")
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(payload)
        self.used += len(payload)
        self.hashes[name] = sha(payload)

    def json(self, name, value, *, closing=False):
        body = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
        self.write(name, body, closing=closing)

    def arrays(self, name, values):
        buffer = io.BytesIO()
        np.savez_compressed(buffer, **values)
        self.write(name, buffer.getvalue())


def load_arrays(path):
    with np.load(path, allow_pickle=False) as saved:
        return {key: saved[key] for key in saved.files}


def authenticate(path, receipt):
    root = Path(path)
    expected = set(receipt["files_sha256"]) | {"verification.json"}
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if expected != actual or any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Evidence member set or link policy changed")
    for name, digest in receipt["files_sha256"].items():
        safe_relative(name)
        if file_sha(root / name) != digest:
            raise ValueError("Evidence payload hash mismatch")
    size = sum((root / name).stat().st_size for name in receipt["files_sha256"])
    if (
        size != receipt["artifact_bytes_before_receipt"]
        or size + (root / "verification.json").stat().st_size
        > receipt["resources"]["artifact_bytes"]
    ):
        raise ValueError("Evidence byte accounting changed")
    with zipfile.ZipFile(root / "sources.zip") as archive:
        if len(archive.namelist()) != len(SOURCE_FILES) or set(archive.namelist()) != set(
            SOURCE_FILES
        ):
            raise ValueError("Source capsule members changed")
        if set(receipt["source_sha256"]) != set(SOURCE_FILES):
            raise ValueError("Source manifest members changed")
        for name in SOURCE_FILES:
            digest = receipt["source_sha256"][name]
            if sha(archive.read(name)) != digest or file_sha(ROOT / name) != digest:
                raise ValueError("Captured or current numerical source changed")
