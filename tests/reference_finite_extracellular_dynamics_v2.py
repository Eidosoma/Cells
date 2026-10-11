"""NUM-009 v2 explicit inventories with conservation-tangent implicit references."""

from time import monotonic

import numpy as np
from scipy.integrate import solve_ivp

from tests import reference_finite_extracellular_dynamics as v1
from tests.finite_extracellular_tangent import Budget, jacobian

spec, ionic = v1.spec, v1.ionic
initial_state, domain, recorded = v1.initial_state, v1.domain, v1.recorded
sample_record, comparison_grid = v1.sample_record, v1.comparison_grid
integrate_candidate, ResourceLimit = v1.integrate_candidate, v1.ResourceLimit


def integrate_reference(case, settings, *, budget=None):
    if settings["method"] not in ("Radau", "BDF"):
        raise ValueError("Unsupported independent solver")
    for name in ("rtol", "atol", "max_step_s"):
        spec.ion.number(settings[name], name, positive=True)
    budget = Budget() if budget is None else budget
    started = monotonic()
    state = initial_state(case)
    times, states, coeffs, degrees, shifts, denominators = (
        [0.0],
        [state.copy()],
        [],
        [],
        [],
        [],
    )
    totals = {"nfev": 0, "njev": 0, "nlu": 0}
    for slot, control in enumerate(case.controls):
        end = case.controls[slot + 1].time_s if slot + 1 < len(case.controls) else case.horizon_s
        if end == control.time_s:
            continue

        def rhs(time, value, held=control):
            return budget.rhs(v1.hyperbolic_rhs, case, held, value)

        result = solve_ivp(
            rhs,
            (control.time_s, end),
            state,
            method=settings["method"],
            rtol=settings["rtol"],
            atol=settings["atol"],
            max_step=settings["max_step_s"],
            dense_output=True,
            jac=lambda time, value, held=control: jacobian(case, held, value, budget=budget),
        )
        if not result.success or result.t[-1] != end:
            raise ValueError(f"Independent solver failed: {result.message}")
        if len(times) + len(result.t) - 2 > ionic.MAX_STEPS:
            raise ResourceLimit("Accepted-step budget exhausted")
        full = result.y.T
        for value in full:
            domain(case, value)
        times.extend(result.t[1:])
        states.extend(full[1:])
        for polynomial in result.sol.interpolants:
            c = np.zeros((case.size, 6))
            shift, denominator = np.zeros(5), np.ones(5)
            if settings["method"] == "Radau":
                degree = polynomial.Q.shape[1]
                c[:, 0], c[:, 1 : degree + 1] = polynomial.y_old, polynomial.Q
            else:
                degree = polynomial.order
                c[:, : degree + 1] = polynomial.D.T
                shift[:degree], denominator[:degree] = polynomial.t_shift, polynomial.denom
            if not 1 <= degree <= 5:
                raise ValueError("Unexpected pinned SciPy dense degree")
            coeffs.append(c)
            degrees.append(degree)
            shifts.append(shift)
            denominators.append(denominator)
        for key in totals:
            totals[key] += getattr(result, key)
        state = result.y[:, -1].copy()
    arrays = recorded(case, times, states, coeffs, degrees, shifts, denominators)
    return arrays, {
        "status": "complete",
        **settings,
        **totals,
        **budget.summary(),
        "accepted_steps": len(times) - 1,
        "seconds": monotonic() - started,
    }
