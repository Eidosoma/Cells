"""Shared result type and the registered statistical constants of the OL5 references."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

ALPHA = 1e-3
"""Family-wise significance level of every statistical check, registered in advance."""

MIN_POWER = 0.99
"""A statistical design that cannot reach this power against its planted control fails as
underpowered instead of passing vacuously."""

UNIT_ROUNDOFF = 2.0 ** -53


class MissingRecord(Exception):
    """A record, role or declaration a check needs is absent (harness exit status 2)."""


class RecordFormatError(Exception):
    """A record is present but malformed, or declares a token outside the menu (status 2)."""


@dataclass
class CheckResult:
    """A check's verdict with the numbers that decided it."""

    name: str
    passed: bool
    detail: dict

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": bool(self.passed), "detail": jsonable(self.detail)}


def jsonable(obj):
    """Convert NumPy scalars and arrays (and Fractions) to plain JSON types, recursively."""
    from fractions import Fraction

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
    if isinstance(obj, Fraction):
        return str(obj)
    return obj
