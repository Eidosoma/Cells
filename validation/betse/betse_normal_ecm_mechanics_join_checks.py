"""Pure saved-row budget verification and exact source-boundary checks."""

import math

from validation.betse.betse_mechanics_join_checks import numeric


def verify_rows(rows):
    reports = {}
    for name, row in rows.items():
        shape, actual = numeric(row["actual"])
        target_shape, target = numeric(row["target"])
        lower_shape, lower = numeric(row["lower"])
        budget_shape, budget = numeric(row["budget"])
        if not shape == target_shape == lower_shape == budget_shape or any(b <= 0 for b in budget):
            raise ValueError("Invalid complete conditional comparison row: " + name)
        errors = [abs(a - b) for a, b in zip(actual, target, strict=True)]
        _, saved_errors = numeric(row["error"])
        if errors != saved_errors:
            raise ValueError("Changed full saved error vector: " + name)
        fractions = [error / b for error, b in zip(errors, budget, strict=True)]
        resolution = [abs(a - b) / c for a, b, c in zip(lower, target, budget, strict=True)]
        maximum, refined = max(fractions, default=0.0), max(resolution, default=0.0)
        if not math.isfinite(maximum + refined):
            raise ValueError("Nonfinite normalized conditional error")
        reports[name] = dict(
            shape=list(shape),
            errors_flat=errors,
            budgets_flat=budget,
            normalized_errors_flat=fractions,
            normalized_resolution_flat=resolution,
            maximum_error_over_budget=maximum,
            maximum_resolution=refined,
        )
    if not reports:
        raise ValueError("Missing complete conditional comparison rows")
    return reports


def assert_rows(reports):
    assert max(row["maximum_error_over_budget"] for row in reports.values()) <= 1
    assert max(row["maximum_resolution"] for row in reports.values()) <= 0.1
