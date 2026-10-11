"""NUM-010 independent implicit references and separately formulated explicit RK4.

All inventories and interface histories are integrated. Only numerical derivative
directions are conservation-tangent; actual state and derivatives are never projected.
"""

import math
from time import monotonic

import numpy as np
from scipy.integrate import BDF, Radau

from tests import spatial_extracellular_fields as fields
from tests import spatial_extracellular_numerical_checks as checks
from tests import spatial_extracellular_numerical_data as data


class ResourceLimit(RuntimeError):
    pass


class Budget:
    def __init__(self, *, deadline=math.inf, max_calls=100000):
        self.deadline, self.max_calls = deadline, max_calls
        self.calls = self.jacobian_evaluations = self.jacobian_rhs_calls = 0
        self.central_columns = self.one_sided_columns = self.zero_tangent_columns = 0
        self.minimum_amount = math.inf
        self.max_x = self.max_current = self.max_current_A = self.max_charge = 0.0
        self.rejection = None
        self.trace = None

    def check(self):
        if monotonic() >= self.deadline:
            raise ResourceLimit("Spatial session wall-time budget exhausted")
        if self.calls >= self.max_calls:
            raise ResourceLimit("Spatial RHS budget exhausted")

    def rhs(self, function, case, control, value, time, label, *, jacobian=False):
        self.check()
        self.calls += 1
        if jacobian:
            self.jacobian_rhs_calls += 1
        try:
            rate, metrics = function(case, control, value)
        except fields.DomainViolation as exc:
            self.rejection = {
                "reason": str(exc),
                "stage": label,
                "time_s": float(time),
                "control_time_s": control.time_s,
                "availability": list(control.availability),
                "state": [float(v) if math.isfinite(v) else str(float(v)) for v in value],
            }
            raise
        self.minimum_amount = min(self.minimum_amount, metrics["minimum_amount_fmol"])
        self.max_x = max(self.max_x, metrics["max_membrane_abs_x"])
        self.max_current = max(self.max_current, metrics["current_normalized"])
        self.max_current_A = max(self.max_current_A, metrics["max_current_residual_A"])
        self.max_charge = max(
            self.max_charge, metrics["max_component_charge_C"], metrics["max_capacitor_residual_C"]
        )
        return rate

    def summary(self):
        return {
            "rhs_calls": self.calls,
            "jacobian_evaluations": self.jacobian_evaluations,
            "jacobian_rhs_calls": self.jacobian_rhs_calls,
            "central_columns": self.central_columns,
            "one_sided_columns": self.one_sided_columns,
            "zero_tangent_columns": self.zero_tangent_columns,
            "minimum_trial_amount_fmol": self.minimum_amount
            if math.isfinite(self.minimum_amount)
            else None,
            "maximum_trial_abs_x": self.max_x,
            "maximum_current_normalized": self.max_current,
            "maximum_current_residual_A": self.max_current_A,
            "maximum_charge_C": self.max_charge,
            "rejected_trial": self.rejection,
        }


def amount_projector(case):
    g = case.g
    count, species = len(g.ids), len(g.z)
    global_average = np.ones((count, count)) / count
    group_average = (g.p / np.sum(g.p, axis=0)) @ g.p.T
    valence = np.outer(g.z, g.z) / float(g.z @ g.z)
    return (
        np.eye(count * species)
        - np.kron(global_average, np.eye(species))
        - np.kron(group_average, valence)
        + np.kron(global_average, valence)
    )


def directional_bounds(case, value, direction):
    _, amount, _, _, voltage, _ = fields.state_domain(case, value)
    g = case.g
    delta = direction[: case.layout.amount_count].reshape(g.initial.shape)
    lower, upper = -math.inf, math.inf

    def intersect(values, slopes, lo, hi):
        nonlocal lower, upper
        for value, slope in zip(np.ravel(values), np.ravel(slopes), strict=True):
            if slope:
                left, right = (lo - value) / slope, (hi - value) / slope
                lower, upper = max(lower, min(left, right)), min(upper, max(left, right))

    intersect(amount, delta, 0, math.inf)
    dv = np.asarray(
        [
            data.QF / cap * math.fsum(g.z * delta[u])
            for cap, (u, _) in zip(g.capacitance, g.membrane_pairs, strict=True)
        ]
    )
    factor = data.F * g.z / (data.R * g.temperature)
    intersect(voltage[:, None] * factor, dv[:, None] * factor, -50, 50)
    if not lower <= 0 <= upper:
        raise fields.DomainViolation("No admissible tangent probe interval")
    return float(lower), float(upper)


def difference_rule(nominal, lower, upper):
    central = min(nominal, -0.25 * lower, 0.25 * upper)
    if central >= 0.1 * nominal:
        return central, True
    positive, negative = 0.25 * upper, -0.25 * lower
    step = min(nominal, positive) if positive >= negative else -min(nominal, negative)
    if not math.isfinite(step) or step == 0:
        raise fields.DomainViolation("No representable tangent derivative probe")
    return step, False


def jacobian(case, control, value, time, budget, tangent=None):
    budget.jacobian_evaluations += 1
    base = budget.rhs(
        fields.independent, case, control, value, time, "jacobian_base", jacobian=True
    )
    result = np.zeros((case.size, case.size))
    tangent = amount_projector(case) if tangent is None else tangent
    for j in range(case.layout.amount_count):
        direction = np.zeros(case.size)
        direction[: case.layout.amount_count] = tangent[:, j]
        if not np.any(direction):
            budget.zero_tangent_columns += 1
            continue
        nominal = np.cbrt(np.finfo(float).eps) * max(abs(value[j]), 0.001)
        step, central = difference_rule(nominal, *directional_bounds(case, value, direction))
        first, second = (
            value + step * direction,
            value + (-step if central else 2 * step) * direction,
        )
        if np.array_equal(first, value) or np.array_equal(first, second):
            raise fields.DomainViolation("Tangent probe rounded to an unchanged state")
        f1 = budget.rhs(
            fields.independent, case, control, first, time, "jacobian_first", jacobian=True
        )
        f2 = budget.rhs(
            fields.independent, case, control, second, time, "jacobian_second", jacobian=True
        )
        result[:, j] = (f1 - f2) / (2 * step) if central else (-3 * base + 4 * f1 - f2) / (2 * step)
        if central:
            budget.central_columns += 1
        else:
            budget.one_sided_columns += 1
    if not np.all(np.isfinite(result)):
        raise fields.DomainViolation("Nonfinite tangent Jacobian")
    return result


def recorded(case, times, states, coefficients, degrees, shifts, denominators):
    steps = len(times) - 1
    return {
        "native_times_s": np.asarray(times, dtype=float),
        "native_state": np.asarray(states, dtype=float).reshape(steps + 1, case.size),
        "coefficients": np.asarray(coefficients, dtype=float).reshape(steps, case.size, 6),
        "degree": np.asarray(degrees, dtype=np.int64),
        "shift": np.asarray(shifts, dtype=float).reshape(steps, 5),
        "denominator": np.asarray(denominators, dtype=float).reshape(steps, 5),
    }


def with_samples(case, arrays, stats):
    times = data.observations(case)
    times = (
        times[times >= arrays["native_times_s"][0]]
        if stats["status"] == "complete"
        else np.empty(0)
    )
    return arrays | {
        "sample_times_s": times,
        "sample_state": checks.replay(case, arrays, stats["method"], times),
    }


def integrate_reference(case, settings, *, budget=None):
    method = settings["method"]
    if method not in {"Radau", "BDF"}:
        raise ValueError("Unsupported independent method")
    budget = Budget() if budget is None else budget
    started, y = monotonic(), data.initial_state(case)
    times, states, coefficients, degrees, shifts, denoms = [0.0], [y.copy()], [], [], [], []
    totals = {"nfev": 0, "njev": 0, "nlu": 0}
    budget.trace = (times, states, coefficients, degrees, shifts, denoms)
    tangent = amount_projector(case)
    for i, control in enumerate(case.controls):
        end = case.controls[i + 1].time_s if i + 1 < len(case.controls) else case.horizon_s
        if end == control.time_s:
            continue

        def rhs(t, value, held=control):
            return budget.rhs(fields.independent, case, held, value, t, "implicit_rhs")

        solver = (Radau if method == "Radau" else BDF)(
            rhs,
            control.time_s,
            y,
            end,
            rtol=settings["rtol"],
            atol=settings["atol"],
            max_step=settings["max_step_s"],
            jac=lambda t, value, held=control: jacobian(case, held, value, t, budget, tangent),
        )
        while solver.status == "running":
            budget.check()
            message = solver.step()
            if solver.status == "failed":
                raise fields.DomainViolation(f"Independent solver failed: {message}")
            if len(times) > 100000:
                raise ResourceLimit("Accepted spatial step budget exceeded")
            fields.state_domain(case, solver.y)
            polynomial = solver.dense_output()
            c, shift, denominator = np.zeros((case.size, 6)), np.zeros(5), np.ones(5)
            if method == "Radau":
                degree = polynomial.Q.shape[1]
                c[:, 0], c[:, 1 : degree + 1] = polynomial.y_old, polynomial.Q
            else:
                degree = polynomial.order
                c[:, : degree + 1] = polynomial.D.T
                shift[:degree], denominator[:degree] = polynomial.t_shift, polynomial.denom
            if not 1 <= degree <= 5:
                raise ValueError("Unqualified native dense degree")
            times.append(float(solver.t))
            states.append(solver.y.copy())
            coefficients.append(c)
            degrees.append(degree)
            shifts.append(shift)
            denoms.append(denominator)
        if solver.t != end:
            raise fields.DomainViolation("Incomplete implicit control interval")
        y = solver.y.copy()
        for key in totals:
            totals[key] += getattr(solver, key)
    arrays = recorded(case, times, states, coefficients, degrees, shifts, denoms)
    stats = {
        "status": "complete",
        **settings,
        **budget.summary(),
        **totals,
        "accepted_steps": len(times) - 1,
        "seconds": monotonic() - started,
    }
    return with_samples(case, arrays, stats), stats


def stopped_reference(case, settings, budget, error):
    """Retain the accepted prefix even if construction, a probe or a step failed."""
    if budget.trace is None:
        arrays = recorded(case, [0.0], [data.initial_state(case)], [], [], [], [])
    else:
        arrays = recorded(case, *budget.trace)
    stats = {
        "status": "stopped",
        **settings,
        **budget.summary(),
        "accepted_steps": len(arrays["native_times_s"]) - 1,
        "error_type": type(error).__name__,
        "error": str(error),
    }
    return with_samples(case, arrays, stats), stats


def stopped_candidate(case, dt, budget, error, *, start=0.0, initial=None):
    """Keep actual accepted work on resource exhaustion; never invent a suffix."""
    if budget.trace is None:
        y = data.initial_state(case) if initial is None else initial
        arrays = recorded(case, [start], [y], [], [], [], [])
    else:
        arrays = recorded(case, *budget.trace)
    stats = {
        "status": "stopped",
        "method": "RK4",
        "dt_s": dt,
        **budget.summary(),
        "accepted_steps": len(arrays["native_times_s"]) - 1,
        "error_type": type(error).__name__,
        "error": str(error),
    }
    return with_samples(case, arrays, stats), stats


def integrate_candidate(case, dt, *, budget=None, start=0.0, initial=None):
    budget = Budget() if budget is None else budget
    mesh = data.candidate_grid(case, dt, start=start)
    if start != 0 and initial is None:
        raise ValueError("Continuation requires complete state")
    y = data.initial_state(case) if initial is None else np.asarray(initial, dtype=float).copy()
    fields.state_domain(case, y)
    started = monotonic()
    times, states, coefficients = [float(start)], [y.copy()], []
    degrees, shifts, denoms = [], [], []
    budget.trace = (times, states, coefficients, degrees, shifts, denoms)
    rejected_calls = 0
    for left, right in zip(mesh[:-1], mesh[1:], strict=True):
        step, control, before_calls = right - left, case.control_at(float(left)), budget.calls

        def rhs(value, t, label, held=control):
            return budget.rhs(fields.candidate, case, held, value, t, label)

        try:
            k1 = rhs(y, left, "k1")
            k2 = rhs(y + step * k1 / 2, left + step / 2, "k2")
            k3 = rhs(y + step * k2 / 2, left + step / 2, "k3")
            k4 = rhs(y + step * k3, right, "k4")
            following = y + step / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            endpoint = rhs(following, right, "endpoint")
        except fields.DomainViolation:
            rejected_calls = budget.calls - before_calls
            budget.rejection |= {"interval_left_s": float(left), "interval_right_s": float(right)}
            break
        change = following - y
        c = np.zeros((case.size, 6))
        c[:, 0], c[:, 1] = y, step * k1
        c[:, 2] = 3 * change - step * (2 * k1 + endpoint)
        c[:, 3] = -2 * change + step * (k1 + endpoint)
        coefficients.append(c)
        degrees.append(3)
        shifts.append(np.zeros(5))
        denoms.append(np.ones(5))
        y = following
        times.append(float(right))
        states.append(y.copy())
    steps = len(times) - 1
    arrays = recorded(case, *budget.trace)
    stats = {
        "status": "rejected" if budget.rejection else "complete",
        "method": "RK4",
        "dt_s": dt,
        **budget.summary(),
        "rejected_rhs_calls": rejected_calls,
        "accepted_steps": steps,
        "seconds": monotonic() - started,
    }
    return with_samples(case, arrays, stats), stats
