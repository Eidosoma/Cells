"""Independent reference adapter for the new array port; no Cells/JAX imports.

Reuse the qualified named-owner, full-matrix and high-precision functional
oracle without importing or consuming a production numeric layout or slot map.
Its stable-increment host counterpart is not used to compute this reference.
"""

from decimal import Decimal, localcontext

import numpy as np

from validation.tissue import physiology_protein_interval_accounting_reference as qualified


def evaluate(inputs):
    answer = qualified.evaluate(**inputs)
    model = inputs["raw"]["model"]["id"]
    answer["original_energy_tolerance_pJ"] = (
        1e-9 if model in ("resolved_calcium@11", "resolved_calcium_energy@5") else 2e-8
    )
    answer["reference_method"] = (
        "qualified independent named owners/full capacitance matrix/absolute chemical functionals"
    )
    return answer


def ideal_change(inputs):
    exact = qualified.ideal_change(**inputs)
    values = np.asarray([float(value) for value in exact.flat]).reshape(exact.shape)
    representable = np.asarray(
        [np.isfinite(float(value)) and (float(value) != 0 or value == 0) for value in exact.flat]
    ).reshape(exact.shape)
    return dict(
        value_pJ=values,
        exact_pJ=[[str(value) for value in row] for row in exact],
        representable=representable,
    )


def precision(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    budget = 3e-14 * np.abs(expected) + 4 * np.abs(np.spacing(expected))
    difference = np.abs(actual - expected)
    ratio = np.divide(difference, budget, out=np.zeros_like(difference), where=budget > 0)
    ratio = np.where((budget == 0) & (difference != 0), np.inf, ratio)
    return budget, ratio


def decimal_relative_error(actual, exact):
    with localcontext() as context:
        context.prec = 80
        error = abs(Decimal.from_float(float(actual)) - Decimal(exact))
        return float(error / abs(Decimal(exact))) if Decimal(exact) else float(error)
