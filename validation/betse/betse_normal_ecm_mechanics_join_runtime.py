"""Separate full-evidence prefix and imported immutable runtime utilities."""

import os
from pathlib import Path

from validation.betse import betse_mechanics_join_runtime as base

PREFIX = "betse-normal-ecm-mechanics-join"
plain, arrays, typed_inventory = base.plain, base.arrays, base.typed_inventory
write, read, restore, capture = base.write, base.read, base.restore, base.capture


def root(name):
    return Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / PREFIX / name


def guard(mode):
    base.guard("native" if mode in ("native", "produce-native", "raw") else "reference")


def pytest_sessionfinish(session, exitstatus):
    write(
        Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "runtime.json",
        capture() | dict(exitstatus=int(exitstatus)),
    )
