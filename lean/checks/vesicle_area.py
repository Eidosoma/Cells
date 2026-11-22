"""Synthetic FR-31 holds with scaled areas and initial vesicle counts."""

import json
from decimal import Decimal, localcontext
from fractions import Fraction


def check(areas, counts, exposure, expected):
    """Compare the exponential formula to independently specified rational results."""
    weights = [Decimal(n) / sum(counts) for n in counts]
    mean = sum(w * a for w, a in zip(weights, areas, strict=True))
    low, high = min(areas), max(areas)

    def survival(a):
        return (-exposure * a).exp()

    lower = survival(mean)
    mixture = sum(w * survival(a) for w, a in zip(weights, areas, strict=True))
    upper = (
        lower
        if low == high
        else ((high - mean) * survival(low) + (mean - low) * survival(high)) / (high - low)
    )
    tolerance = Decimal("1e-48")
    for computed, exact in zip((lower, mixture, upper), expected, strict=True):
        oracle = Decimal(exact.numerator) / exact.denominator
        assert abs(computed - oracle) <= tolerance, (areas, computed, exact)
    assert lower <= mixture + tolerance and mixture <= upper + tolerance
    return dict(
        areas=areas,
        counts=counts,
        mean_area=str(mean.normalize()),
        lower=float(lower),
        population=float(mixture),
        upper=float(upper),
    )


def run():
    with localcontext() as ctx:
        ctx.prec = 60
        q = Decimal(2).ln()
        return {
            "endpoints": check(
                [1, 3], [1, 1], q, (Fraction(1, 4), Fraction(5, 16), Fraction(5, 16))
            ),
            "interior": check(
                [1, 2, 3], [1, 2, 1], q, (Fraction(1, 4), Fraction(9, 32), Fraction(5, 16))
            ),
            "one_area": check([2, 2], [1, 3], q, (Fraction(1, 4),) * 3),
            "zero_exposure": check([1, 3], [1, 3], Decimal(0), (Fraction(1),) * 3),
        }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
