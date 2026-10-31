"""Inventory and fresh-process import boundaries for active ECM checks."""

import os
from pathlib import Path

from validation.geometry import active_polygon_physiology_runtime as raw_capture
from validation.geometry import stable_geometry_primitives_runtime as inventory


def guard(mode):
    inventory.BLOCKED = (
        {"cells", "betse", "jax", "jaxlib", "torch", "PIL"}
        if mode in ("initial-field", "field-corruption")
        else inventory.SCIENTIFIC | {"cells"}
    )
    inventory.deny_production()


def capture():
    return inventory.capture()


def write(path, value):
    return raw_capture.write(path, value)


def pytest_sessionfinish(session, exitstatus):
    write(
        Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json",
        capture() | dict(exitstatus=int(exitstatus)),
    )
