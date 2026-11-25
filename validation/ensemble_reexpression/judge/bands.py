"""Bands, estimates and the order rule (CRITERIA sections 1, 4.3 and 4.5)."""

from __future__ import annotations

import math

import numpy as np

from . import constants as c


def largest(array) -> float:
    """max |array|, as a float."""
    return float(np.max(np.abs(array)))


def estimate(first, second, third, order: int):
    """(d2, d1, U): the two step-halving differences and the larger of the two error estimates."""
    d2, d1 = largest(second - first), largest(third - second)
    gain = 2**order
    return d2, d1, max(d1 / (gain - 1), d2 / (gain * (gain - 1)))


def extrapolate(second, third, order: int):
    """Y* = Y3 + (Y3 - Y2) / (2^p - 1)."""
    return third + (third - second) / (2**order - 1)


def observed_order(d2: float, d1: float):
    """q = log2(d2 / d1), or None where a difference is zero or not finite."""
    if not (d1 > 0 and d2 > 0 and math.isfinite(d1) and math.isfinite(d2)):
        return None
    ratio = d2 / d1
    return math.log2(ratio) if 0 < ratio < math.inf else math.log2(d2) - math.log2(d1)


def classify(d2: float, d1: float, theta: float, order: int) -> str:
    """The order rule's class: unresolved, mixed, resolved, or resolved outside its window ("not
    finite" where the rows overflow).
    """
    if not (math.isfinite(d1) and math.isfinite(d2)):
        return "not finite"
    below = (d1 <= theta, d2 <= theta)
    if all(below):
        return "unresolved"
    if any(below):
        return "mixed"
    q = observed_order(d2, d1)
    return "resolved" if order - 0.5 <= q <= c.ORDER_TOP else "resolved outside its window"


def band(entry, U_c: float, U_l: float, steps_c: int, steps_l: int | None) -> dict:
    """The parts of beta, and beta with and without e_store. `steps_l` None: an identity, which has
    no captured side.
    """
    round_c = entry.e_round(steps_c)
    round_l = 0.0 if steps_l is None else entry.e_round(steps_l)
    close = entry.e_close()
    store = entry.e_store(steps_c)
    without = 2 * (U_l + U_c) + round_c + round_l + close
    return {
        "U_c": U_c,
        "U_l": U_l,
        "e_round_c": round_c,
        "e_round_l": round_l,
        "e_close": close,
        "e_store": store,
        "beta": without + store,
        "beta_without_store": without,
        "theta": c.THRESHOLD * (round_c + store),
    }


def legacy_threshold(entry, steps_l: int) -> float:
    """The legacy side's threshold: e_store is 0, since legacy stores increments (CRITERIA section
    4.3).
    """
    return c.THRESHOLD * entry.e_round(steps_l)


def score(statistic: float, beta: float, order_class: str) -> str:
    """The outcome of a class S entry (CRITERIA section 4.3)."""
    if order_class == "resolved outside its window":
        return c.INCONCLUSIVE
    if order_class == "not finite" or not math.isfinite(statistic) or statistic > beta:
        return c.FAIL
    return c.INCONCLUSIVE if order_class == "mixed" else c.PASS
