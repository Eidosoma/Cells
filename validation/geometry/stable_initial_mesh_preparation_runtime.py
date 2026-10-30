"""Bridge runtime inventory and fresh-worker production import denial."""

import builtins
import importlib.abc
import os
import sys
from pathlib import Path

from validation.geometry import stable_geometry_primitives_runtime as inventory

BLOCKED = {"cells", "betse", "jax", "jaxlib", "torch"}


def deny_production(*, extra=()):
    blocked = BLOCKED | set(extra)
    assert not any(name.split(".")[0] in blocked for name in sys.modules)
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Stable initial mesh production import denied: " + name)
        return original(name, *args, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Stable initial mesh production import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())


def capture():
    value = inventory.capture()
    value["denied_production_modules_loaded"] = sorted(
        name for name in sys.modules if name.split(".")[0] in BLOCKED
    )
    return value


def pytest_sessionfinish(session, exitstatus):
    value = capture()
    value["exitstatus"] = int(exitstatus)
    inventory.write(Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json", value)
