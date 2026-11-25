"""A full recovery convergence panel must retain its declared local resolution."""

import numpy as np
import pytest

from validation.tissue import surface_cotransport_water_response as panel


def boundaries():
    return [panel.INTERVENTION_TIME, panel.INTERVENTION_TIME + 2.0**-40, 20001 * panel.DT]


@pytest.mark.parametrize("stop", [True, float("nan"), float("inf"), 0.25, 0.24, 0.5001, 0.250013])
def test_extended_recovery_stop_requires_an_explicit_nominal_boundary(stop):
    with pytest.raises(ValueError, match="nominal boundary"):
        panel.refined_recovery_definition(boundaries(), stop_time_s=stop)


@pytest.mark.parametrize("factor", [True, 0, 3, 8, 2.0])
def test_unregistered_convergence_factor_is_refused(factor):
    with pytest.raises(ValueError):
        panel.refined_recovery_definition(boundaries(), factor=factor)


@pytest.mark.parametrize(
    "times",
    [
        [],
        [0.25, 0.2500125],
        [0.25, 0.25, 0.2500125],
        [0.25, float("nan"), 0.2500125],
        [0.25, True, 0.2500125],
        [0.24, 0.250001, 0.2500125],
        [0.25, 0.25002, 0.2500125],
        [0.25, 0.250001, 0.250013],
    ],
)
def test_wrong_interval_or_invalid_boundaries_are_refused(times):
    with pytest.raises(ValueError):
        panel.refined_recovery_definition(times)


def test_unrepresentable_finer_clock_is_refused_without_rounding_or_deduplication():
    points = [0.25, float(np.nextafter(0.25, 1)), 20001 * panel.DT]
    with pytest.raises(ValueError, match="float clock resolution"):
        panel.refined_recovery_definition(points, factor=2)
