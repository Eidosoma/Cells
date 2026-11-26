"""CRITERIA 3.3's pooled statistics and LAWS section 7's rounding bounds, in decimal arithmetic.

A series here is, per copy, a list of numbers: the judged events' times, or a row or a book at the samples
with t > 0.  The statistic pools the copies' entries.
"""

from __future__ import annotations

from decimal import Context, Decimal, localcontext

PRECISION = 40
UNIT = Decimal(2) ** -53
OPERATIONS = {"event": 4, "row": 16}
RESOLUTION = 10  # times the two rungs' rounding bounds: a difference below is not resolved
NEEDED = 3  # used differences
ZERO = Decimal(0)


def rounding(kind, steps, scale):
    """e_round = m (S + 1) u s."""
    return OPERATIONS[kind] * (steps + 1) * UNIT * scale


def rms(left, right):
    """The pooled root mean square of the difference of two series of the same copies."""
    with localcontext(Context(prec=PRECISION)):
        total, count = ZERO, 0
        for one, other in zip(left, right, strict=True):
            for a, b in zip(one, other, strict=True):
                total += (a - b) ** 2
                count += 1
        if not count:
            raise ValueError("no entry to pool")
        return (total / count).sqrt()


def slope(points, values):
    """The least-squares slope of ln(values) against ln(points)."""
    with localcontext(Context(prec=PRECISION)):
        x = [point.ln() for point in points]
        y = [value.ln() for value in values]
        mean_x, mean_y = sum(x, ZERO) / len(x), sum(y, ZERO) / len(y)
        above = sum(((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=True)), ZERO)
        return above / sum(((a - mean_x) ** 2 for a in x), ZERO)


def statistics(rungs, kind, end, scale, p, runs, reference, accuracy):
    """One readout of one family over its rungs, coarse to fine, against the reference.

    `runs` is the readout's series at each rung.  Returns the differences, the number of used ones, the
    fitted order (None where fewer than three are used), the finest rung's error, the estimate, the
    tolerance, and the reported coarse errors and pairwise orders.
    """
    with localcontext(Context(prec=PRECISION)):
        steps = [end / rung for rung in rungs]
        bounds = [rounding(kind, s, scale) for s in steps]
        differences = [rms(runs[j + 1], runs[j]) for j in range(len(rungs) - 1)]
        used = 0
        for j, difference in enumerate(differences):
            if difference > RESOLUTION * (bounds[j] + bounds[j + 1]):
                used = j + 1
            else:
                break
        order = slope(rungs[:used], differences[:used]) if used >= NEEDED else None
        errors = [rms(run, reference) for run in runs]
        gain = 2**p - 1
        estimate = max(differences[-1] / gain, differences[-2] / (2**p * gain))
        return {
            "d": differences,
            "used": used,
            "q": order,
            "E": errors[-1],
            "est": estimate,
            "tau": 3 * estimate + accuracy + bounds[-1],
            "coarse_errors": errors[:-1],
            "pairwise": [
                (a / b).ln() / (rungs[j] / rungs[j + 1]).ln() if a > 0 and b > 0 else None
                for j, (a, b) in enumerate(zip(differences[:-1], differences[1:], strict=True))
            ],
        }
