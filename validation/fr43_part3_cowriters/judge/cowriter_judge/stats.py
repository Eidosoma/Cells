"""CRITERIA.md §3.3: the pooled statistic, the step differences, the order and the tolerance.

    E_n = sqrt( mean over entries of (y_{h_n} - y_ref)^2 )
    d_j = sqrt( mean over entries of (y_{h_{j+1}} - y_{h_j})^2 ),  j = 1 .. n-1          (engine only)
    est = max( d_{n-1}/(2^p - 1),  d_{n-2}/(2^p (2^p - 1)) )
    tau = 3 est + e_ref + e_round(h_n)

A d_j is resolved where d_j > 10 (e_round(h_j) + e_round(h_{j+1})); the used differences are the longest run of
resolved ones from j = 1; with at least three used, q is the least-squares slope of ln d_j against ln h_j over them.
For a pooled statistic S is S_j = T/h_j (CRITERIA.md §1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .registry import RESOLVE_FACTOR, e_round, steps


def pooled_rms(differences: list[float]) -> float | None:
    """Root mean square of the differences; None where there is no entry (nothing passes empty)."""
    if not differences:
        return None
    return math.sqrt(math.fsum(d * d for d in differences) / len(differences))


def slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of ys against xs."""
    n = len(xs)
    mx = math.fsum(xs) / n
    my = math.fsum(ys) / n
    sxy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    return sxy / sxx


def log_slope(hs: list[float], values: list[float]) -> float:
    return slope([math.log(h) for h in hs], [math.log(v) for v in values])


def round_bound(m: int, end_s: float, h: float, scale: float) -> float:
    """e_round at rung h for a pooled statistic: S = T/h."""
    return e_round(m, steps(end_s, h), scale)


@dataclass
class Ladder:
    """The engine-only part of §3.3 for one readout of one family (rungs coarsest first)."""

    p: int
    rungs: list[float]
    d: list[float]
    resolved: list[bool] = field(default_factory=list)
    used: int = 0
    q: float | None = None
    est: float = 0.0
    any_zero: bool = False
    thresholds: list[float] = field(default_factory=list)

    @property
    def formed(self) -> bool:
        return self.used >= 3

    def in_window(self, half: float) -> bool | None:
        if self.q is None:
            return None
        return (self.p - half) <= self.q <= (self.p + half)

    def pairwise_orders(self) -> list[float | None]:
        """The reported orders of successive differences, log2(d_j / d_{j+1}) (judge nothing)."""
        out: list[float | None] = []
        for a, b in zip(self.d, self.d[1:]):
            out.append(math.log2(a / b) if a > 0 and b > 0 else None)
        return out

    def finest_triple_order(self) -> float | None:
        """The order of the finest three rungs, log2(d_{n-2}/d_{n-1}) (reported, judges nothing)."""
        if len(self.d) < 2 or self.d[-2] <= 0 or self.d[-1] <= 0:
            return None
        return math.log2(self.d[-2] / self.d[-1])


def ladder(p: int, rungs: list[float], d: list[float], m: int, end_s: float, scale: float) -> Ladder:
    """Resolve, count the used differences, fit q and form est (CRITERIA.md §3.3)."""
    if len(d) != len(rungs) - 1:
        raise ValueError("d needs one entry fewer than the rungs")
    bounds = [round_bound(m, end_s, h, scale) for h in rungs]
    thresholds = [RESOLVE_FACTOR * (bounds[j] + bounds[j + 1]) for j in range(len(d))]
    resolved = [d[j] > thresholds[j] for j in range(len(d))]
    used = 0
    for flag in resolved:
        if not flag:
            break
        used += 1
    q = None
    if used >= 3:
        q = log_slope(rungs[:used], d[:used])
    two_p = 2.0**p
    candidates = [d[-1] / (two_p - 1.0)]
    if len(d) >= 2:
        candidates.append(d[-2] / (two_p * (two_p - 1.0)))
    est = max(candidates)
    return Ladder(p=p, rungs=list(rungs), d=list(d), resolved=resolved, used=used, q=q, est=est,
                  any_zero=any(x == 0.0 for x in d), thresholds=thresholds)


def tau(est: float, e_ref: float, m: int, end_s: float, h_finest: float, scale: float) -> float:
    return 3.0 * est + e_ref + round_bound(m, end_s, h_finest, scale)
