"""Class E and class R rules (CRITERIA.md §3.1, §3.2), in exact arithmetic.

Residuals and bounds are exact rationals of the doubles read, so that a miss is never the judge's own rounding.
E compares bit patterns (the sign of zero included).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Sequence

from .registry import M_ROW, START_ULPS, U, World


def bits(x: float) -> bytes:
    return struct.pack("<d", float(x))


def same_bits(a: Any, b: Any) -> bool:
    """E: bit for bit, the sign of zero included (an integer is read as its double)."""
    return bits(a) == bits(b)


def ratio(stat: Fraction | float, tol: Fraction | float) -> float:
    """statistic over tolerance; 0 where both are 0 (CRITERIA.md §8), inf where only the tolerance is 0."""
    if tol == 0:
        return 0.0 if stat == 0 else math.inf
    return float(Fraction(stat) / Fraction(tol))


@dataclass
class IdentityValue:
    """The residual, s_id and bound as doubles (for the record); `passes` is decided exactly."""

    residual: float
    s_id: float
    bound: float
    passes: bool

    @property
    def ratio(self) -> float:
        return ratio(abs(self.residual), self.bound)


def identity_at(terms: Sequence[tuple[str, float, str]], at_t: dict[str, float], at_0: dict[str, float],
                s_steps: Fraction) -> IdentityValue:
    """READOUTS.md §4: the sum of the identity's terms, and its bound 16 (S + 1) u s_id, s_id = Σ |coef × value|.

    The sums are formed in doubles (each product rounded once, fsum correctly rounded), which is within 4 u s_id of
    the exact sums; only where |residual| lies within that of the bound is the decision taken in exact rationals."""
    values = [(coefficient, at_t[readout] if when == "t" else at_0[readout]) for readout, coefficient, when in terms]
    products = [c * v for c, v in values]
    residual = math.fsum(products)
    s_id = math.fsum(abs(x) for x in products)
    bound = M_ROW * (float(s_steps) + 1.0) * 2.0**-53 * s_id
    slack = 4.0 * 2.0**-53 * s_id
    if abs(residual) <= bound - slack:
        passes = True
    elif abs(residual) > bound + slack:
        passes = False
    else:
        exact_terms = [Fraction(c) * Fraction(v) for c, v in values]
        exact_residual = sum(exact_terms, Fraction(0))
        exact_s_id = sum((abs(x) for x in exact_terms), Fraction(0))
        passes = abs(exact_residual) <= M_ROW * (Fraction(s_steps) + 1) * U * exact_s_id
    return IdentityValue(residual=residual, s_id=s_id, bound=bound, passes=passes)


@dataclass
class StartValue:
    value: float
    declared: float
    distance: Fraction
    bound: Fraction

    @property
    def passes(self) -> bool:
        if self.declared == 0:
            return self.value == 0  # exactly zero (-0.0 is zero)
        return self.distance <= self.bound


def start_at(value: float, declared: float) -> StartValue:
    """READOUTS.md §4: within 4 u |declared|, exactly zero where the declared value is 0."""
    distance = abs(Fraction(value) - Fraction(declared))
    return StartValue(value=value, declared=declared, distance=distance,
                      bound=START_ULPS * U * abs(Fraction(declared)))


@dataclass
class TraceResult:
    """CRITERIA.md §3.1's trace, for one run's listed events."""

    fails: list[str] = field(default_factory=list)  # every reason the trace fails E
    contradicts: bool = False  # the record contradicts itself (unforms t_events)
    too_few: bool = False  # fewer than K_c events (unforms t_events)
    differs_from_reference: int = 0  # judged events whose channel or counts differ from the reference's
    checked_events: int = 0

    @property
    def passes(self) -> bool:
        return not self.fails


def check_trace(world: World, times: Sequence[float], channels: Sequence[str], counts: Sequence[Sequence[int]],
                first_index: int, events_total: int | None, k_c: int, ref_channels: Sequence[str],
                ref_counts: Sequence[Sequence[int]], counts_before: Sequence[int] | None, completed: bool,
                starts_at_zero: bool) -> TraceResult:
    """The trace (CRITERIA.md §3.1). `counts_before` is None where the counts before the first event are unknown."""
    result = TraceResult()
    n = len(times)
    if starts_at_zero and first_index != 0:
        result.fails.append(f"first_index {first_index} in a run that starts at t = 0")
        result.contradicts = True
    for i in range(1, n):
        if not times[i] > times[i - 1]:
            result.fails.append(f"event {first_index + i} is not after event {first_index + i - 1}")
            result.contradicts = True
            break
    previous = tuple(counts_before) if counts_before is not None else None
    for i in range(n):
        index = first_index + i
        channel = channels[i]
        after = tuple(counts[i])
        if any(c < 0 for c in after):
            result.fails.append(f"event {index}: a negative count {list(after)}")
            result.contradicts = True
        if channel not in world.channels:
            result.fails.append(f"event {index}: channel {channel!r} is not declared")
            result.contradicts = True
        elif previous is not None:
            jump = world.channels[channel].jump
            expected = tuple(p + j for p, j in zip(previous, jump))
            if expected != after:
                result.fails.append(f"event {index}: counts {list(after)} against {channel} from {list(previous)}")
                result.contradicts = True
        previous = after
    if completed and events_total is not None:
        if events_total != first_index + n:
            result.fails.append(f"events_total {events_total} against first_index {first_index} + {n} listed")
            result.contradicts = True
        if events_total < k_c:
            result.fails.append(f"events_total {events_total} below K_c {k_c}")
            result.too_few = True
    for k in range(first_index, k_c):
        i = k - first_index
        if i >= n:
            if completed:
                result.fails.append(f"event {k} of the K_c = {k_c} judged events is not listed")
                result.too_few = True
            break
        result.checked_events += 1
        if channels[i] != ref_channels[k] or tuple(counts[i]) != tuple(ref_counts[k]):
            result.differs_from_reference += 1
    if result.differs_from_reference:
        result.fails.append(f"{result.differs_from_reference} judged events differ from the reference's")
    return result


def ledger_fails(world: World, integer_ledger: Sequence[int] | None, counts: Sequence[Sequence[int]]) -> list[str]:
    """E: Σ_k w_k n_k is the declared total at every sample and after every listed event."""
    total = world.ledger_total
    out = []
    if integer_ledger is not None:
        for i, value in enumerate(integer_ledger):
            if value != total:
                out.append(f"integer_ledger[{i}] = {value} against {total}")
    for i, after in enumerate(counts):
        value = sum(w * c for w, c in zip(world.weights, after))
        if value != total:
            out.append(f"the ledger after listed event {i} is {value} against {total}")
    return out
