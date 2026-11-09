"""Projective forward Euler: coarse outer steps around a qualified fine integrator.

projective_forward_euler@1 follows Gear and Kevrekidis, "Projective methods for
stiff differential equations: problems with gaps in their eigenvalue spectrum"
(SIAM J Sci Comput 24:1091-1106, 2003). A burst of K fine steps lets the fast
modes decay; the slow derivative is the chord of the last m fine steps,

    v = (y_K - y_{K-m}) / (t_K - t_{K-m}),

and the projective step of length D extrapolates the complete state,

    y_J = y_K + (D / (t_K - t_{K-m})) * (y_K - y_{K-m}).

Gear and Kevrekidis use m = 1; a longer chord divides the per-step rounding of
the inner integrator, which the ratio D / (t_K - t_{K-m}) multiplies, by m.
The extrapolation is an affine combination (coefficients 1 + r and -r), so any
linear identity L(y) = c that both rows satisfy holds for y_J up to rounding:
L(y_J) = L(y_K) + r (L(y_K) - L(y_{K-m})). Nonlinear identities (energy) are
not preserved and are measured per jump by the caller.

Error estimate (per jump, in tolerance-normalized coordinates, see
admissible_jump): the slope carries a fast remainder bounded by the change
between the last two chords, |v_1 - v_0| (settling), and the slow
curvature y'' gives the forward-Euler term (1/2) y'' D (D + m h) for a slope
taken at the chord midpoint. Stability of the fast modes is linear-mode
amplification (cycle_amplification); the caller verifies every jump with the
following fine burst.
"""

import math

import numpy as np

METHOD_ID = "projective_forward_euler@1"


def extrapolate(last, base, ratio):
    """last + ratio * (last - base) for every leaf of two equal state tuples (host NumPy).

    Coefficients 1 + ratio and -ratio sum to one. Equal leaves (padding, held
    values) stay bitwise unchanged.
    """
    if not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("Projective ratio must be positive and finite")
    leaves = []
    for a, b in zip(last, base, strict=True):
        a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
        leaves.append(a + ratio * (a - b))
    return type(last)(*leaves) if hasattr(last, "_fields") else type(last)(leaves)


def normalized(difference, tolerance):
    """max over classes of max |difference| / tolerance; both dicts share keys."""
    worst = 0.0
    for key, value in difference.items():
        value = np.asarray(value, dtype=np.float64)
        if value.size:
            worst = max(worst, float(np.max(np.abs(value))) / tolerance[key])
    return worst


def chord(rows, times, first, last):
    """Per-class chord slope between two coordinate rows (dicts of arrays)."""
    span = times[last] - times[first]
    return {k: (rows[last][k] - rows[first][k]) / span for k in rows[last]}


def error_estimate(duration, settle, curvature, chord_span):
    """Normalized local error of a jump of the given duration (s).

    settle: |v_1 - v_0| (1/s); curvature: |y''| (1/s^2); both normalized by
    the tolerances. The slope is taken at the chord midpoint, chord_span / 2
    before the jump starts.
    """
    return settle * duration + 0.5 * curvature * duration * (duration + chord_span)


def admissible_jump(settle, curvature, chord_span, target):
    """Largest duration whose error_estimate does not exceed target (inf if unbounded)."""
    if target <= 0:
        return 0.0
    b = settle + 0.5 * curvature * chord_span
    if curvature <= 0:
        return math.inf if b <= 0 else target / b
    # 0.5 c D^2 + b D - target = 0, written without cancellation.
    return 2 * target / (b + math.sqrt(b * b + 2 * curvature * target))


def cycle_amplification(rho, burst, slope, ratio):
    """Linear-mode growth factor of one burst plus jump.

    rho: the fine step's amplification of the mode (complex allowed); burst K
    steps, chord over the last `slope` = m steps, jump ratio r = D / (m h).
    After K steps the mode is rho^K; the jump maps it to
    rho^K + r (rho^K - rho^(K - m)). A mode with |result| > 1 grows from cycle
    to cycle. Slow modes (rho near 1) give 1 + r m (rho - 1) + ... per cycle.
    """
    rho = np.asarray(rho, dtype=np.complex128)
    last, base = rho**burst, rho ** (burst - slope)
    return last + ratio * (last - base)
