"""Read-only observation of already accepted numerical states."""

from dataclasses import dataclass

import numpy as np

from cells.core.errors import NumericalError


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount: np.ndarray
    concentration: np.ndarray
    supplied: np.ndarray
    degraded: np.ndarray


def sample_history(times, values, requested):
    """Interpolate on the time axis without assigning meaning to trailing axes."""
    shape = (len(requested), *values.shape[1:])
    columns = int(np.prod(values.shape[1:]))
    if not len(requested) or not columns:
        return np.empty(shape, dtype=np.float64)
    flat = values.reshape((len(times), columns))
    sampled = np.stack([np.interp(requested, times, flat[:, i]) for i in range(columns)], axis=1)
    return sampled.reshape(shape)


def sample_hermite_history(times, values, requested, left_slopes, right_slopes):
    """Read-only cubic sampling using separately supplied interval-local slopes.

    The caller owns physics and must hold the SAME control for both endpoint
    slopes of an interval. Stored endpoints and constant intervals remain exact.
    This interpolant is not universally positivity preserving: validate outputs.
    """
    shape = (len(requested), *values.shape[1:])
    if not len(requested):
        return np.empty(shape, dtype=np.float64)
    if len(times) == 1:
        return np.broadcast_to(values[0], shape).copy()
    indices = np.minimum(np.searchsorted(times, requested, side="right") - 1, len(times) - 2)
    axes = (-1,) + (1,) * (values.ndim - 1)
    h = (times[indices + 1] - times[indices]).reshape(axes)
    theta = (requested - times[indices]).reshape(axes) / h
    y0, y1 = values[indices], values[indices + 1]
    a, b = left_slopes[indices], right_slopes[indices]
    delta = y1 - y0
    sampled = y0 + theta * (
        h * a + theta * (3 * delta - h * (2 * a + b) + theta * (-2 * delta + h * (a + b)))
    )
    sampled = np.where(theta == 0, y0, sampled)
    return np.where(theta == 1, y1, sampled)


def hermite_bounds(times, values, left_slopes, right_slopes):
    """Componentwise floating cubic bounds over each complete accepted interval.

    Inspect endpoints and every real derivative root in (0, 1). Normalize the
    derivative coefficients before the discriminant; use the stable quadratic
    root pair and an explicit linear limit. This checks the interpolant's domain,
    not its error against the ODE or a rigorous interval-arithmetic enclosure.
    """
    h = np.diff(times).reshape((-1,) + (1,) * (values.ndim - 1))
    y0, y1 = values[:-1], values[1:]
    with np.errstate(over="ignore", invalid="ignore"):
        delta = y1 - y0
        b = h * left_slopes
        c = 3 * delta - h * (2 * left_slopes + right_slopes)
        d = -2 * delta + h * (left_slopes + right_slopes)
    if not all(np.isfinite(v).all() for v in (y0, y1, b, c, d)):
        raise NumericalError("Nonfinite cubic coefficients; domain cannot be checked")
    lo, hi = np.minimum(y0, y1), np.maximum(y0, y1)
    scale = np.maximum.reduce([np.abs(d), np.abs(c), np.abs(b)])
    scale = np.where(scale == 0, 1.0, scale)
    aa, bb, cc = 3 * (d / scale), 2 * (c / scale), b / scale
    discriminant = bb * bb - 4 * aa * cc
    root = np.sqrt(np.maximum(discriminant, 0))
    q = -0.5 * (bb + np.copysign(root, bb))
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        candidates = (
            np.where((aa != 0) & (discriminant >= 0), q / aa, np.nan),
            np.where((aa != 0) & (discriminant >= 0) & (q != 0), cc / q, np.nan),
            np.where((aa == 0) & (bb != 0), -cc / bb, np.nan),
        )
    for candidate in candidates:
        inside = np.isfinite(candidate) & (candidate > 0) & (candidate < 1)
        theta = np.where(inside, candidate, 0.0)
        value = y0 + theta * (b + theta * (c + theta * d))
        lo = np.minimum(lo, np.where(inside, value, y0))
        hi = np.maximum(hi, np.where(inside, value, y0))
    return lo, hi


def observe(times, amount, supplied, degraded, volume, requested) -> Observations:
    """Linear interpolation is an observer approximation, never a solver step.

    All accepted numerical states remain available separately. Exact accepted
    times return their exact values; off-grid measurements are explicitly linear.
    """
    requested = np.asarray(requested, dtype=np.float64)

    def sample(values):
        return sample_history(times, values, requested)

    sampled = sample(amount)
    return Observations(requested, sampled, sampled / volume, sample(supplied), sample(degraded))
