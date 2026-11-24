"""FR-50 references: K2's ODE integration (SciPy Radau, binary64), the README's cross-check.

The state is (n_O, n_N, F, B): the cell's and the node's amounts and the two one-way records.
Radau runs at rtol 1e-12 and atol 1e-30, so its error control is relative in every component. The
thread variables are pinned before NumPy is imported.
"""

from __future__ import annotations

import os

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np  # noqa: E402
from fr50_spec import Case  # noqa: E402
from scipy.integrate import solve_ivp  # noqa: E402

RTOL = 1e-12
ATOL = 1e-30


def relaxation_radau(case: Case) -> dict:
    a = 1e15 * float(case["P_m_per_s"]) * float(case["A_m2"]) * float(case["opening"])
    V_O, V_N = float(case["V_cell_pL"]), float(case["V_node_pL"])
    M = np.array([[-a / V_O, a / V_N, 0.0, 0.0],
                  [a / V_O, -a / V_N, 0.0, 0.0],
                  [0.0, a / V_N, 0.0, 0.0],
                  [a / V_O, 0.0, 0.0, 0.0]])
    step = float(case.record_times.step)
    ts = [step * i for i in range(case.record_times.last + 1)]
    y0 = [V_O * float(case["c_cell_mM_at_0"]), V_N * float(case["c_node_mM_at_0"]), 0.0, 0.0]
    sol = solve_ivp(lambda _t, y: M @ y, (0.0, ts[-1]), y0, method="Radau", t_eval=ts,
                    rtol=RTOL, atol=ATOL, jac=lambda _t, y: M)
    if not sol.success:
        raise RuntimeError(f"Radau failed: {sol.message}")
    return {"c_cell": list(sol.y[0] / V_O), "c_node": list(sol.y[1] / V_N), "F": list(sol.y[2]),
            "B": list(sol.y[3])}
