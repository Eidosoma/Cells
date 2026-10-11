"""Scalar finite-bath equations and independent adaptive reference integrators.

No Cells, JAX, pump prototype or native BETSE imports. Material and energy state
are assembled explicitly from the registered fixture, in cell-major coordinates.
"""

import math
import sys

from coupled_plan import F, R


def size(case):
    return 8 * len(case["volume_pL"]) + 3


def read_state(case, state):
    n = len(case["volume_pL"])
    inside = [
        [
            case["initial_inside_mM"][i][s] + state[3 * i + s] / case["volume_pL"][i]
            for s in range(3)
        ]
        for i in range(n)
    ]
    outside = [
        case["initial_outside_mM"][s] + state[3 * n + s] / case["outside_volume_pL"]
        for s in range(3)
    ]
    voltage = [
        case["initial_voltage_V"][i]
        + F
        * 1e-15
        / (case["area_m2"][i] * case["specific_capacitance_F_m2"][i])
        * math.fsum(case["valence"][s] * state[3 * i + s] for s in range(3))
        for i in range(n)
    ]
    if not all(math.isfinite(v) and v > 0 for row in inside + [outside] for v in row):
        raise ValueError("Reference trial depleted or nonfinite")
    return inside, outside, voltage


def chemistry(case, i):
    return case["delta_g0_J_mol"][i] + R * case["temperature_K"] * math.log(
        case["adp_mM"][i] * case["pi_mM"][i] / (1000 * case["atp_mM"][i])
    )


def flux(z, inside, outside, voltage, rt, area, permeability):
    x = z * F * voltage / rt
    if abs(x) > 50:
        raise ValueError("Reference voltage domain")
    # Symmetric sinh form is distinct from the candidate Bernoulli function.
    ratio = 1.0 if x == 0 else x / (2 * math.sinh(x / 2))
    return (
        area * permeability * 1e15 * ratio * (outside * math.exp(-x / 2) - inside * math.exp(x / 2))
    )


def rhs(case, state, control):
    n, rt = len(case["volume_pL"]), R * case["temperature_K"]
    inside, outside, volts = read_state(case, state)
    rate = [0.0] * size(case)
    a, b = case["sodium_index"], case["potassium_index"]
    for i in range(n):
        ci, co, v = inside[i], outside, volts[i]
        mu = [rt * math.log(ci[s] / co[s]) + case["valence"][s] * F * v for s in range(3)]
        q = (
            case["adp_mM"][i]
            * case["pi_mM"][i]
            / (1000 * case["atp_mM"][i])
            * (co[a] / ci[a]) ** 3
            * (ci[b] / co[b]) ** 2
        )
        equilibrium = math.exp((F * v - case["delta_g0_J_mol"][i]) / rt)
        na, k, atp = (
            ci[a] / case["km_na_mM"][i],
            co[b] / case["km_k_mM"][i],
            case["atp_mM"][i] / case["km_atp_mM"][i],
        )
        saturation = na**3 * k**2 * atp / ((1 + na**3) * (1 + k**2) * (1 + atp))
        cycles = (
            case["area_m2"][i]
            * 1e15
            * case["alpha_mol_m2_s"][i]
            * control[0]
            * saturation
            * (1 - q / equilibrium)
        )
        affinity = chemistry(case, i) + sum(
            x * y for x, y in zip(case["pump_stoichiometry"], mu, strict=True)
        )
        if abs(affinity / rt) > 80:
            raise ValueError("Reference pump affinity domain")
        leak = [
            flux(
                case["valence"][s],
                ci[s],
                co[s],
                v,
                rt,
                case["area_m2"][i],
                control[1] * case["permeability_m_s"][i][s],
            )
            for s in range(3)
        ]
        for s in range(3):
            transfer = leak[s] + case["pump_stoichiometry"][s] * cycles
            rate[3 * i + s] = transfer
            rate[3 * n + s] -= transfer
            rate[3 * n + 3 + 3 * i + s] = leak[s]
        rate[6 * n + 3 + i] = cycles
        rate[7 * n + 3 + i] = -0.001 * (
            sum(x * y for x, y in zip(leak, mu, strict=True)) + cycles * affinity
        )
    return rate


def integrate(case, plan, method):
    import numpy as np
    from scipy.integrate import solve_ivp

    times = np.linspace(0, case["end_time_s"], round(case["end_time_s"] / plan["sample_dt_s"]) + 1)
    samples, state, segments = [np.zeros(size(case))], np.zeros(size(case)), []
    for index, row in enumerate(case["controls"]):
        start = row["time_s"]
        end = (
            case["controls"][index + 1]["time_s"]
            if index + 1 < len(case["controls"])
            else case["end_time_s"]
        )
        control = [row["pump"], row["leak"]]
        solution = solve_ivp(
            lambda _t, y, control=control: rhs(case, y, control),
            (start, end),
            state,
            method=method,
            rtol=plan["reference_rtol"],
            atol=plan["reference_atol"],
            max_step=plan["reference_max_step_s"],
            dense_output=True,
        )
        if not solution.success:
            raise ValueError(solution.message)
        selected = times[(times > start + 1e-14) & (times <= end + 1e-14)]
        samples.extend(solution.sol(selected).T)
        state = solution.y[:, -1].copy()
        segments.append(
            {
                "start_s": start,
                "end_s": end,
                "nfev": solution.nfev,
                "end_state": state.tolist(),
                "last_solver_time_s": float(solution.t[-1]),
            }
        )
    if any(
        name == "cells" or name.startswith(("cells.", "betse.", "jax.")) for name in sys.modules
    ):
        raise ValueError("Reference imported a model runtime")
    return {"times_s": times.tolist(), "state": np.asarray(samples).tolist(), "segments": segments}


def accounting(case, state):
    n, rt = len(case["volume_pL"]), R * case["temperature_K"]
    inside, outside, volts = read_state(case, state)
    cycles = state[6 * n + 3 : 7 * n + 3]
    transfers = [
        [state[3 * n + 3 + 3 * i + s] + case["pump_stoichiometry"][s] * cycles[i] for s in range(3)]
        for i in range(n)
    ]
    material = [state[3 * i + s] - transfers[i][s] for i in range(n) for s in range(3)]
    material += [state[3 * n + s] + math.fsum(transfers[i][s] for i in range(n)) for s in range(3)]
    charge = (
        F
        * 1e-15
        * math.fsum(
            case["valence"][s] * (state[3 * n + s] + math.fsum(state[3 * i + s] for i in range(n)))
            for s in range(3)
        )
    )
    energy = 0.0
    for i in range(n + 1):
        initial = case["initial_inside_mM"][i] if i < n else case["initial_outside_mM"]
        volume = case["volume_pL"][i] if i < n else case["outside_volume_pL"]
        for s in range(3):
            dn = state[3 * i + s]
            n0 = initial[s] * volume
            energy += (
                0.001 * rt * (dn * math.log(initial[s]) + (n0 + dn) * math.log1p(dn / n0) - dn)
            )
    for i in range(n):
        v0, dv = case["initial_voltage_V"][i], volts[i] - case["initial_voltage_V"][i]
        energy += (
            case["area_m2"][i] * case["specific_capacitance_F_m2"][i] * 1e12 * (v0 * dv + dv**2 / 2)
        )
    work = -0.001 * math.fsum(chemistry(case, i) * cycles[i] for i in range(n))
    residual = energy + math.fsum(state[7 * n + 3 :]) - work
    return {
        "material_residual_fmol": max(map(abs, material)),
        "charge_residual_C": abs(charge),
        "energy_residual_pJ": abs(residual),
        "voltage_V": volts,
        "min_concentration_mM": min(v for row in inside + [outside] for v in row),
    }
