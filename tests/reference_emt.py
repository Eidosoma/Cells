"""Independent NumPy polynomial form for integration cross-checks.

No Cells model/kernel imports. Direct upstream-gate comparisons live in the
optional captured-source validation; this oracle also runs without that checkout.
"""

import numpy as np
from scipy.integrate import solve_ivp


def reference_rhs(time, state, snail=72):
    mir, mrna, protein = state
    s = (snail / 72) ** 2
    z3 = (protein * 9 / 100) ** 3
    z2 = (protein * 9 / 25) ** 2
    r = mir / 40
    translation_polynomial = (
        1 + 3 * r + 3 * r**2 + 0.4 * r**3 + 0.3 * r**4 + 0.12 * r**5 + 0.02 * r**6
    )
    return np.array(
        [
            6 * (1 + 0.4 * s) / (1 + s) * (1 + 0.1 * z3) / (1 + z3) - 0.05 * mir,
            (5 / 12) * (1 + 10 * s) / (1 + s) * (1 + 15 * z2) / (1 + z2) - 0.5 * mrna,
            (mrna / 6) * translation_polynomial / (1 + r) ** 6 - 0.1 * protein,
        ]
    )


def reference_solution(initial, end_time, *, method="Radau", snail=72):
    solution = solve_ivp(
        reference_rhs,
        (0, end_time),
        initial,
        args=(snail,),
        method=method,
        rtol=1e-11,
        atol=1e-12,
        dense_output=True,
    )
    if not solution.success or solution.t[-1] != end_time or not np.isfinite(solution.y).all():
        raise AssertionError(f"Reference integration failed: {solution.message}")
    return solution
