"""Source-only pytest import guard and actual runtime provenance capture."""

import builtins
import hashlib
import importlib.abc
import json
import os
import sys
from importlib import metadata
from pathlib import Path

BLOCKED = {"cells", "jax", "jaxlib", "betse"}
ORIGINAL_IMPORT = builtins.__import__


def guarded(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise ImportError("Production numerical import denied: " + name)
    return ORIGINAL_IMPORT(name, *args, **kwargs)


class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED:
            raise ImportError("Production numerical import denied: " + fullname)


builtins.__import__ = guarded
sys.meta_path.insert(0, Guard())


def capture(exitstatus):
    loaded = sorted(name for name in sys.modules if name.split(".")[0] in BLOCKED)
    if loaded:
        raise ValueError("Unexpected loaded production packages: " + repr(loaded))
    files = {}
    for module in tuple(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name and Path(name).is_file():
            path = Path(name).resolve()
            with path.open("rb") as handle:
                files[str(path)] = hashlib.file_digest(handle, "sha256").hexdigest()
    executable = Path(sys.executable).resolve()
    files[str(executable)] = hashlib.sha256(executable.read_bytes()).hexdigest()
    return dict(
        files=files,
        exitstatus=int(exitstatus),
        python=sys.version,
        affinity=sorted(os.sched_getaffinity(0)),
        backend="numpy_and_isolated_native_ast",
        packages={name: metadata.version(name) for name in ("numpy", "scipy", "pytest")},
        threads={
            name: os.environ.get(name)
            for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
        },
        production_imports_denied=sorted(BLOCKED),
        loaded_production_modules=loaded,
    )


def pytest_sessionfinish(session, exitstatus):
    path = Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json"
    path.write_text(json.dumps(capture(exitstatus), indent=2, allow_nan=False) + "\n")
