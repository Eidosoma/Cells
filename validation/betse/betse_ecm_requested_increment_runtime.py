"""Durable evidence and explicit fresh-worker import boundaries."""

import json
import os
from pathlib import Path

from validation.geometry import stable_geometry_primitives_runtime as inventory

PREFIX = "betse-ecm-requested-increment"


def guard(mode):
    inventory.BLOCKED = (
        {"cells", "betse", "jax", "jaxlib", "torch"}
        if mode == "native"
        else inventory.SCIENTIFIC | {"cells"}
    )
    inventory.deny_production()


def write(path, value):
    """Compact full payloads remain sidecars, separate from bounded summaries."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode()) > 16 * 2**20:
        raise ValueError("Oversize evidence sidecar; split complete payload without truncation")
    with path.open("x") as handle:
        handle.write(encoded + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read(path):
    path = Path(path)
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Oversize evidence sidecar")
    return json.loads(path.read_text())


def root(name):
    return Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / PREFIX / name


def capture():
    return inventory.capture()


def pytest_sessionfinish(session, exitstatus):
    write(
        Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json",
        capture() | dict(exitstatus=int(exitstatus)),
    )
