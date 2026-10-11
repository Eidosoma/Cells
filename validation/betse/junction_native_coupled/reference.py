"""Matched physical-time and measured native-clock continuous limits."""

import importlib.util
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

_spec = importlib.util.spec_from_file_location(
    "coupled_junction_equations", Path(__file__).parents[1] / "junction_coupled/reference.py"
)
physical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(physical)


def integrate(c, protocol, times, method, *, calls_per_step=1):
    """Multiplier is native measured calling semantics, never production physics."""
    settings = protocol["reference"]
    count = c["initial_amount_fmol"].size + c["permeability_m_s"].size + len(c["initial_gate"])
    initial = np.r_[np.zeros(count), c["initial_gate"]]
    if calls_per_step != 1 and c["block"] != 1:
        raise ValueError("Fractional stored-state blocking has no such continuous limit")
    availability = c["opening"] * c["block"]

    def rhs(t, y):
        derivative = physical.rhs(c, availability, y)
        derivative[-len(c["initial_gate"]) :] *= calls_per_step
        return derivative

    answer = solve_ivp(
        rhs,
        (0, protocol["duration_s"]),
        initial,
        method=method,
        rtol=settings["rtol"],
        atol=settings["atol"],
        max_step=settings["max_step_s"],
        dense_output=True,
    )
    if not answer.success or not np.isfinite(answer.y).all():
        raise ValueError("Coupled native-clock reference failed: " + answer.message)
    return answer.sol(times).T, len(answer.t) - 1


def native_difference(c, actual, expected):
    errors = physical.difference(c, actual, expected)
    mask = c["opening"] > 0
    count = len(mask)
    errors["gate"] = physical.transport.maximum(
        actual[..., -count:][..., mask] - expected[..., -count:][..., mask]
    )
    return errors
