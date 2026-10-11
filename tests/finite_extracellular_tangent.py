"""Reference-only conservation-tangent Newton linearization; no state repair.

J approximates Df P, not the unconstrained ambient Jacobian. For A v = 0,
P v = v, so it has the physical directional derivative on conserved-species
Newton corrections. See the v2 numerical amendment for the derivation.
"""

import math

import numpy as np

from tests import finite_extracellular_numerical_data as data
from tests import reference_finite_extracellular_dynamics as v1

RELATIVE_STEP = np.cbrt(np.finfo(float).eps)
AMOUNT_SCALE_FMOL, GATE_SCALE = 0.001, 1.0
BOUND_FRACTION, CENTRAL_FRACTION = 0.25, 0.1


class Budget(v1.Budget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.jacobian_evaluations = self.jacobian_rhs_calls = 0
        self.central_columns = self.one_sided_columns = 0

    def jacobian_rhs(self, case, control, value):
        self.jacobian_rhs_calls += 1
        return self.rhs(v1.hyperbolic_rhs, case, control, value)

    def summary(self):
        return {
            **super().summary(),
            "jacobian_evaluations": self.jacobian_evaluations,
            "jacobian_rhs_calls": self.jacobian_rhs_calls,
            "central_columns": self.central_columns,
            "one_sided_columns": self.one_sided_columns,
        }


def amount_indices(case):
    return np.r_[
        np.arange(case.layout.amount_count),
        np.arange(case.layout.slices["extracellular_amount"].start, case.size),
    ].reshape(case.layout.n + 1, case.layout.s)


def gate_indices(case):
    return np.concatenate(
        [
            np.arange(case.layout.slices[name].start, case.layout.slices[name].stop)
            for name in ("membrane_gate", "junction_gate")
        ]
    )


def projector(case):
    """Equal-status compartment owners; identity on gates and histories."""
    result = np.eye(case.size)
    for indices in amount_indices(case).T:
        result[np.ix_(indices, indices)] -= 1 / len(indices)
    return result


def directional_bounds(case, state, direction):
    """Signed distances to affine physical-domain boundaries, before any RHS."""
    amount, outside, voltage, xs, edge_x, gates, _ = v1.domain(case, state)
    d = case.layout.split(direction)
    w = case.world
    dv = np.array(
        [
            data.QF
            / m.capacitance_F
            * math.fsum(z * a for z, a in zip(w.valence, row, strict=True))
            for m, row in zip(w.membranes, d["amount"], strict=True)
        ]
    )
    factor = np.asarray(w.valence) * data.F / (data.R * w.temperature_K)
    edge_dv = np.asarray([dv[a] - dv[b] for a, b in case.endpoints])
    lower, upper = -math.inf, math.inf

    def intersect(values, slopes, lo, hi):
        nonlocal lower, upper
        for value, slope in zip(np.ravel(values), np.ravel(slopes), strict=True):
            if slope:
                a, b = (lo - value) / slope, (hi - value) / slope
                lower, upper = max(lower, min(a, b)), min(upper, max(a, b))

    intersect(amount, d["amount"], 0, math.inf)
    intersect(outside, d["extracellular_amount"], 0, math.inf)
    intersect(gates, np.r_[d["membrane_gate"].ravel(), d["junction_gate"]], 0, 1)
    intersect(xs, dv[:, None] * factor, -50, 50)
    intersect(edge_x, edge_dv[:, None] * factor, -50, 50)
    for i in case.channel_cells:
        intersect([voltage[i]], [dv[i]], -0.120, 0.060)
    if not lower <= 0 <= upper:
        raise v1.DomainViolation("Jacobian base has no admissible directional interval")
    return float(lower), float(upper)


def difference_rule(nominal, lower, upper):
    symmetric = min(nominal, -BOUND_FRACTION * lower, BOUND_FRACTION * upper)
    if symmetric >= CENTRAL_FRACTION * nominal:
        return symmetric, True
    positive, negative = BOUND_FRACTION * upper, -BOUND_FRACTION * lower
    step = min(nominal, positive) if positive >= negative else -min(nominal, negative)
    if not math.isfinite(step) or step == 0:
        raise v1.DomainViolation("No representable admissible Jacobian step")
    return step, False


def jacobian(case, control, state, *, budget):
    """Two admissible, counted RHS probes per active column, plus one base."""
    budget.check()
    budget.jacobian_evaluations += 1
    base = budget.jacobian_rhs(case, control, state)
    result = np.zeros((case.size, case.size))
    tangent = projector(case)
    amounts = amount_indices(case).ravel()
    for j in np.r_[amounts, gate_indices(case)]:
        direction = tangent[:, j]
        scale = AMOUNT_SCALE_FMOL if j in amounts else GATE_SCALE
        nominal = RELATIVE_STEP * max(abs(state[j]), scale)
        step, central = difference_rule(nominal, *directional_bounds(case, state, direction))
        first = state + step * direction
        second = state + (-step if central else 2 * step) * direction
        if np.array_equal(first, state) or np.array_equal(first, second):
            raise v1.DomainViolation("Jacobian direction rounded to an unchanged probe")
        # Never project the actual solver state, either RHS probe or its output.
        f1 = budget.jacobian_rhs(case, control, first)
        f2 = budget.jacobian_rhs(case, control, second)
        result[:, j] = (f1 - f2) / (2 * step) if central else (-3 * base + 4 * f1 - f2) / (2 * step)
        if central:
            budget.central_columns += 1
        else:
            budget.one_sided_columns += 1
    if not np.isfinite(result).all():
        raise v1.DomainViolation("Nonfinite conservation-tangent Jacobian")
    return result
