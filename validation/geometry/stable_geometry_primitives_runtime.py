"""Small runtime inventory and production-import guard for primitive workers."""

import builtins
import hashlib
import importlib.abc
import json
import os
import sys
from importlib import metadata
from pathlib import Path

SCIENTIFIC = {"numpy", "scipy", "betse", "jax", "jaxlib", "torch", "PIL"}
BLOCKED = SCIENTIFIC | {"cells"}


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def deny_production():
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("Primitive reference production import denied: " + name)
        return original(name, *args, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in BLOCKED:
                raise ImportError("Primitive reference production import denied: " + fullname)

    assert not any(name.split(".")[0] in BLOCKED for name in sys.modules)
    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())


def capture():
    paths = {str(Path(sys.executable).resolve())}
    for module in tuple(sys.modules.values()):
        if name := getattr(module, "__file__", None):
            if Path(name).is_file():
                paths.add(str(Path(name).resolve()))
    mapping_errors = []
    try:
        with Path("/proc/self/maps").open() as handle:
            for line in handle:
                fields = line.split(maxsplit=5)
                if len(fields) == 6 and fields[5].startswith("/"):
                    path = Path(fields[5].strip())
                    if path.is_file():
                        paths.add(str(path.resolve()))
                    else:
                        mapping_errors.append(str(path))
    except OSError as error:
        mapping_errors.append(str(error))
    files, errors = {}, {}
    assert len(paths) <= 20000
    for name in paths:
        try:
            files[name] = sha(name)
        except OSError as error:
            errors[name] = str(error)
    return dict(
        python=sys.version,
        executable=str(Path(sys.executable).resolve()),
        affinity=sorted(os.sched_getaffinity(0)),
        files=files,
        file_errors=errors,
        mapped_file_errors=mapping_errors,
        pytest_version=metadata.version("pytest"),
        scientific_modules_loaded=sorted(n for n in sys.modules if n.split(".")[0] in SCIENTIFIC),
        production_modules_loaded=sorted(n for n in sys.modules if n.split(".")[0] in BLOCKED),
        float_info=dict(
            radix=sys.float_info.radix,
            mant_dig=sys.float_info.mant_dig,
            max_exp=sys.float_info.max_exp,
            min_exp=sys.float_info.min_exp,
        ),
        threads={
            key: os.environ.get(key)
            for key in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
    )


def pytest_sessionfinish(session, exitstatus):
    value = capture()
    value["exitstatus"] = int(exitstatus)
    write(Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json", value)
