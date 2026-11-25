"""Reference arithmetic must retain diffusion/drift at nearly equal concentrations."""

import math
from decimal import Decimal, localcontext

import numpy as np
import pytest

from validation.tissue import surface_field_reference as electrical
from validation.tissue import surface_kinetic_fixtures as fixtures
from validation.tissue import surface_kinetic_reference as reference
from validation.tissue.surface_reference import F, R, logarithmic_mean


@pytest.mark.parametrize("right", [0.02, 1.0, 140.0, 1e-100, 1e100])
def test_reference_logarithmic_mean_against_decimal(right):
    # Include equal/adjacent floats, both orientations, and both sides of the
    # log1p branch. Decimal uses exact binary inputs and a direct quotient/log.
    lefts = [right, math.nextafter(right, 0), math.nextafter(right, math.inf)]
    lefts += [
        right * factor for factor in (0.01, 0.5, 0.501, 0.99999999, 1.00000001, 1.499, 1.5, 100)
    ]
    with localcontext() as context:
        context.prec = 90
        for left in lefts:
            a, b = Decimal.from_float(left), Decimal.from_float(right)
            log = (a / b).ln()
            mean = (a - b) / log if a != b else a
            actual_mean, actual_log = logarithmic_mean(left, right)
            np.testing.assert_allclose(actual_log, float(log), rtol=8e-14, atol=0)
            np.testing.assert_allclose(actual_mean, float(mean), rtol=8e-14, atol=0)
            # These are the concentrations responsible for the failed
            # reference initial-step probe; require near machine precision.
            if abs(left - right) < 0.49 * right:
                np.testing.assert_allclose(actual_log, float(log), rtol=5e-16, atol=0)
                np.testing.assert_allclose(actual_mean, float(mean), rtol=5e-16, atol=0)


def energy_balance(context, state, slope, phi):
    """The stored power and the heat less the work, in pJ/s, with the capacitors' voltage rates
    from the charge the rates move: zero for exact rates."""
    p, rates = context["layout"], reference.unpack(context, slope)
    raw = reference.base.stage(context, state, 0.0)
    matrix, active, reservoir, _, floating, _ = electrical.topology(raw)
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    moved = np.c_[rates["amount_increment"], rates["extracellular_amount_increment"]]
    current = 1e-15 * F * (np.asarray(p["valence"]).T @ moved)[0]
    dv = np.zeros_like(phi)
    dv[free] = np.linalg.solve(matrix[np.ix_(free, free)], current[free])
    n = len(context["qi"])
    electric = 1e12 * sum(
        capacitance * (phi[i] - phi[n + o]) * (dv[i] - dv[n + o])
        for i, o, capacitance in zip(
            p["membrane_cell"], p["membrane_outside"], p["membrane_capacitance"], strict=True
        )
    )
    logs = np.log(np.c_[raw["ci"], raw["co"]])
    chemical = 1e-3 * R * p["temperature"] * np.sum(logs * moved)
    heat = sum(np.sum(v) for k, v in rates.items() if k.endswith("_dissipated_energy_pJ"))
    work = sum(np.sum(v) for k, v in rates.items() if k.endswith("_work_pJ"))
    return float(chemical + electric + heat - work)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("probe_dt", [1e-12, 1e-10, 1e-8, 1e-6])
def test_reference_current_balance_at_small_initial_probes(arm, probe_dt):
    """The kinetic tissue's independent reference one small step from its initial state."""
    context = reference.bind(fixtures.definition(arm))
    state = reference.initial(context)
    derivative, _, _ = reference.evaluate(context, state, 0.0)
    probe = state + probe_dt * derivative
    # evaluate enforces the root's residuals and the per-node capacitor/current balance.
    trial, phi, _ = reference.evaluate(context, probe, 0.0)
    assert np.isfinite(trial).all() and np.isfinite(phi).all()
    assert abs(energy_balance(context, probe, trial, phi)) < 1e-10
