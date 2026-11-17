"""Shared result type and registered statistical constants for the references."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ALPHA = 1e-3
"""Family-wise significance level of every statistical check, registered in advance."""

MIN_POWER = 0.99
"""A statistical check whose design cannot reach this power against its planted
control fails as underpowered instead of passing vacuously."""

UNIT_ROUNDOFF = 2.0 ** -53


@dataclass
class CheckResult:
    """A check's verdict with the numbers that decided it."""

    name: str
    passed: bool
    detail: dict

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": bool(self.passed), "detail": jsonable(self.detail)}

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return bool(self.passed)


def jsonable(obj):
    """Convert NumPy scalars and arrays to plain JSON types, recursively."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return jsonable(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj
