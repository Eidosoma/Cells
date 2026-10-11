"""Reference arithmetic must retain diffusion/drift at nearly equal concentrations."""

import math
from decimal import Decimal, localcontext

import numpy as np
import pytest

from validation.tissue import surface_calcium_fixtures as fixtures
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue.surface_reference import logarithmic_mean


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


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("probe_dt", [1e-12, 1e-10, 1e-8, 1e-6])
def test_reference_current_balance_at_small_initial_probes(arm, probe_dt):
    context = calcium.bind(fixtures.definition(arm))
    state = calcium.initial(context)
    derivative, _, _ = calcium.evaluate(context, state, 0.0)
    trial, phi, proof = calcium.evaluate(context, state + probe_dt * derivative, 0.0)
    # evaluate enforces the unchanged per-node capacitor/current assertions.
    assert np.isfinite(trial).all() and np.isfinite(phi).all()
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
