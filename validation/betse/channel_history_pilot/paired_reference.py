"""D099 explicit-fixture variant of D095 independent continuous integration.

The vector field is the frozen, independently checked Decimal formulation.
SciPy integrates float64 values; 80-digit RHS arithmetic is not an 80-digit ODE
solution. Neither simulator, comparator nor definition compiler is imported.
"""

import importlib
import math
import sys
import time
from pathlib import Path

import feedback_io as io

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "channel_loop_preparation"))
field = importlib.import_module("pilot_reference")


def axes(p):
    n = len(p["volume_pL"])
    io.require(
        n > 0
        and len(p["channel_enabled"]) == n
        and all(type(v) is bool for v in p["channel_enabled"]),
        "Invalid reference axes",
    )
    return n, [i for i, enabled in enumerate(p["channel_enabled"]) if enabled]


def initial_state(p, gates=(0.2, 0.6)):
    n, channels = axes(p)
    return [0.0] * n + [gates[0]] * len(channels) + [gates[1]] * len(channels) + [0.0] * n


def unpack(p, state):
    n, channels = axes(p)
    k = len(channels)
    io.require(
        len(state) == 2 * n + 2 * k
        and all(type(v) in (int, float) and math.isfinite(v) for v in state),
        "Reference state shape/precision",
    )
    m, h = [0.0] * n, [0.0] * n
    for j, i in enumerate(channels):
        m[i], h[i] = state[n + j], state[n + k + j]
    return state[:n], m, h, state[n + 2 * k :]


def derivative(p, state):
    q, m, h, _energy = unpack(p, state)
    value = field.rates(p, q, m, h)
    _, channels = axes(p)
    return (
        value["inward_K_fmol_per_s"]
        + [value["gate_rate_per_s"][0][i] for i in channels]
        + [value["gate_rate_per_s"][1][i] for i in channels]
        + value["dissipation_pJ_per_s"]
    )


def readout(p, state):
    q, m, h, energy = unpack(p, state)
    value = field.rates(p, q, m, h)
    return {
        "gate": [m, h],
        "voltage_V": value["voltage_V"],
        "cell_K_fmol": [a + b for a, b in zip(p["initial_K_fmol"], q, strict=True)],
        "bath_K_fmol": p["outside_K_fmol"] - math.fsum(q),
        "transfer_fmol": q,
        "flux_fmol_per_s": value["inward_K_fmol_per_s"],
        "permeability_m_per_s": value["permeability_m_per_s"],
        "inward_current_A": value["inward_current_A"],
        "energy_pJ": energy,
    }


def dense_record(polynomial, method):
    expected = "Dop853DenseOutput" if method == "DOP853" else "RadauDenseOutput"
    io.require(type(polynomial).__name__ == expected, "Pinned dense representation changed")
    coefficients = polynomial.F if method == "DOP853" else polynomial.Q
    return {
        "method": method,
        "left_s": float(polynomial.t_old),
        "right_s": float(polynomial.t),
        "y_left": polynomial.y_old.tolist(),
        "coefficients": coefficients.tolist(),
    }


def integrate(p, setting, protocol):
    import numpy as np
    from scipy.integrate import solve_ivp

    began = time.monotonic()
    n, channels = axes(p)
    counter = 0

    def rhs(_time, state):
        nonlocal counter
        counter += 1
        io.require(
            counter <= protocol["reference"]["max_rhs_calls_per_solve"],
            "Reference RHS budget exceeded",
        )
        return np.asarray(derivative(p, state.tolist()), dtype=np.float64)

    io.require(setting["method"] in ("DOP853", "Radau"), "Unregistered reference method")
    atol = (
        [setting["atol_q_fmol"]] * n
        + [setting["atol_gate"]] * (2 * len(channels))
        + [setting["atol_energy_pJ"]] * n
    )
    solution = solve_ivp(
        rhs,
        (0.0, protocol["duration_s"]),
        initial_state(p, protocol["initial_gate"]),
        method=setting["method"],
        rtol=setting["rtol"],
        atol=atol,
        max_step=setting["max_step_s"],
        dense_output=True,
    )
    io.require(
        solution.success and solution.status == 0 and solution.t[-1] == protocol["duration_s"],
        "Independent integrator did not finish",
    )
    io.require(
        len(solution.t) - 1 <= protocol["reference"]["max_accepted_steps_per_solve"],
        "Reference accepted-step budget",
    )
    dt = protocol["reference"]["sample_dt_s"]
    count = round(protocol["duration_s"] / dt)
    samples = np.array([i * dt for i in range(count)] + [protocol["duration_s"]], dtype=np.float64)
    values = solution.sol(samples).T
    io.require(
        all(
            a.dtype == np.float64 and np.isfinite(a).all()
            for a in (solution.t, solution.y, samples, values)
        ),
        "Reference nonfinite/non-float64 output",
    )
    accepted = solution.y.T.tolist()
    # Every accepted and requested state is domain checked by the independent RHS.
    for state in accepted + values.tolist():
        derivative(p, state)
    return {
        "initial_gate": list(protocol["initial_gate"]),
        "setting": setting,
        "state_axes": {
            "cell_count": n,
            "channel_cell_indices": channels,
            "order": ["q_fmol", "m_active", "h_active", "energy_pJ"],
        },
        "accepted_times_s": solution.t.tolist(),
        "accepted_states": accepted,
        "dense_intervals": [dense_record(v, setting["method"]) for v in solution.sol.interpolants],
        "sample_times_s": samples.tolist(),
        "sample_states": values.tolist(),
        "readouts": [readout(p, y) for y in values.tolist()],
        "stats": {
            "success": True,
            "status": int(solution.status),
            "message": solution.message,
            "nfev": int(solution.nfev),
            "njev": int(solution.njev),
            "nlu": int(solution.nlu),
            "rhs_calls_including_jacobian": counter,
            "accepted_steps": len(accepted) - 1,
            "elapsed_seconds": time.monotonic() - began,
        },
    }


def worker(r, output):
    result = {}
    for variant in r["protocol"]["variants"]:
        for setting in r["protocol"]["reference"]["solves"]:
            directory = output / "reference" / variant / setting["id"]
            directory.mkdir(parents=True, exist_ok=False)
            record = integrate(r["reference_parameters"][variant], setting, r["protocol"])
            io.write_compressed(directory / "result.json.gz", record)
            result[variant + "/" + setting["id"]] = str(
                (directory / "result.json.gz").relative_to(output)
            )
            print(f"reference completed: {variant}/{setting['id']}", flush=True)
    io.require(
        not any(name.split(".")[0] in ("cells", "betse", "jax", "jaxlib") for name in sys.modules),
        "Reference imported a simulator",
    )
    return {
        "engine": "independent_decimal_rhs_scipy_dop853_radau",
        "records": result,
        "integration_precision": "float64",
        "rhs_precision_digits": 80,
        "simulator_imports": [],
        "reference_solves": len(result),
    }
