"""Independent Decimal geometry and power/square-root reference; no Cells/NumPy.

Budgets are arithmetic comparison limits for the declared, well-conditioned
fixtures. They do not certify every real exponent or near-singular geometry.
"""

from decimal import Decimal, localcontext


def d(value):
    return Decimal.from_float(float(value))


def evaluate(saved):
    with localcontext() as context:
        context.prec = 125
        offset, scale, shift = (d(saved[k]) for k in ("x_offset", "slope", "z_offset"))
        if saved["kind"] == "gradient_r":
            centre = [d(x) for x in saved["centre_m"]]
            radii = []
            for name, point in zip(
                saved["membrane_ids"], saved["membrane_midpoints_m"], strict=True
            ):
                radius = sum((d(point[j]) - centre[j] - offset) ** 2 for j in (0, 1)).sqrt()
                radii.append(radius if name in saved["target_ids"] else Decimal(0))
            span = max(radii)
            factors = [r / span * scale + shift for r in radii]
        else:
            points = (
                saved["membrane_midpoints_m"]
                if saved["target_domain"] == "membranes"
                else saved["cell_centres_m"]
            )
            index = 0 if saved["kind"] == "gradient_x" else 1
            values = [d(row[index]) for row in points]
            low, high = min(values), max(values)
            span = high - low
            midpoint, exponent = Decimal(".5") + offset, d(saved["exponent"])
            factors = []
            for value in values:
                base = (value - low) / span / midpoint
                loading = Decimal(1) if exponent == 0 else base**exponent
                factors.append(loading / (1 + loading) * scale + shift)
        # Explicit fixture budgets; geometry degeneracy and overflow are separate refusals.
        eps = Decimal(2) ** -52
        factor_budget = 64 * eps * max(Decimal(1), abs(scale) + abs(shift))
        span_budget = 16 * eps * abs(span)
        return dict(
            factor=[float(x) for x in factors],
            normalization_m=float(span),
            factor_budget=float(factor_budget),
            normalization_budget_m=float(span_budget),
        )
