"""Independent Decimal trigonometry and rational source-slope preparation.

No Cells, NumPy, JAX or external trigonometric library. The oracle's declared
comparison domain is |phase| <= 16384 radians; larger phases require a separate
precision analysis, even when source floating arithmetic remains finite.
"""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction
from functools import lru_cache


def d(value):
    return Decimal.from_float(float(value))


@lru_cache(maxsize=1)
def pi():
    with localcontext() as context:
        context.prec = 130

        def atan_inverse(n):
            x = Decimal(1) / n
            power, total, k = x, x, 1
            while True:
                power *= -(x * x)
                term = power / (2 * k + 1)
                total += term
                if abs(term) < Decimal("1e-125"):
                    return total
                k += 1

        return 16 * atan_inverse(5) - 4 * atan_inverse(239)


def sine(value):
    p = pi()
    if abs(value) > 16384:
        raise ValueError("Independent trigonometric comparison phase is out of scope")
    reduced = value - (value / (2 * p)).to_integral_value(rounding=ROUND_HALF_EVEN) * (2 * p)
    term = total = reduced
    k = 1
    while True:
        term *= -(reduced * reduced) / ((2 * k) * (2 * k + 1))
        total += term
        if abs(term) < Decimal("1e-100"):
            return total
        k += 1


def resolved_slope(program):
    if not program["automatic_slope"]:
        return program["slope_Hz_s"]
    # Source rounds the subtraction before dividing by the original duration.
    difference = float(Fraction(program["requested_stop_Hz"]) - Fraction(program["frequency_Hz"]))
    return float(Fraction(difference) / Fraction(program["original_duration_s"]))


def evaluate(program, time_s):
    """Higher-precision sine and phase, with forward-rounding comparison budgets."""
    if isinstance(time_s, list):
        return [evaluate(program, value) for value in time_s]
    with localcontext() as context:
        context.prec = 115
        t, frequency = d(time_s), d(program["frequency_Hz"])
        if program["kind"] == "periodic":
            phase = t * pi() * frequency + d(program["phase_rad"])
            scale = abs(t * pi() * frequency) + abs(d(program["phase_rad"]))
        else:
            slope = d(resolved_slope(program))
            phase = pi() * (slope * t + frequency) * t
            scale = pi() * abs(t) * (abs(slope * t) + abs(frequency))
        factor = sine(phase) ** 2
        epsilon = Decimal(2) ** -52
        # Conservative operation-count allowance, including pi rounding and
        # final sin/square. This is a fixture comparison budget, not a certified
        # error bound for every vendor's transcendental implementation.
        phase_budget = 16 * epsilon * max(Decimal(1), scale)
        factor_budget = phase_budget + 16 * epsilon
        return dict(
            phase_rad=float(phase),
            factor=float(factor),
            phase_budget_rad=float(phase_budget),
            factor_budget=float(factor_budget),
        )
