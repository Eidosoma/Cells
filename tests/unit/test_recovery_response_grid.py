"""A full recovery convergence panel must retain its declared local resolution."""

import numpy as np
import pytest

from cells.core.grid import EventGrid
from cells.core.specs import parse_spec
from validation.tissue import surface_cotransport_water_response as panel


def boundaries():
    return [panel.INTERVENTION_TIME, panel.INTERVENTION_TIME + 2.0**-40, 20001 * panel.DT]


@pytest.mark.parametrize("stop", [None, 20040 * panel.DT])
def test_local_refinement_preserves_original_physics_clocks_and_nested_boundaries(stop):
    points = boundaries()
    if stop is not None:
        points += [20002 * panel.DT, 20004 * panel.DT, stop]
    original_points = points.copy()
    previous = None
    for factor in (1, 2, 4):
        raw = panel.refined_recovery_definition(points, factor=factor, stop_time_s=stop)
        assert points == original_points
        original = panel.definition("supply_recovery", dt=panel.DT / factor)
        assert raw["model"] == original["model"]
        assert raw["experiment"] == original["experiment"]
        assert {k: v for k, v in raw["execution"].items() if k != "refinement_times"} == (
            original["execution"]
        )
        declared = np.asarray([points[0], *raw["execution"]["refinement_times"], points[-1]])
        if previous is not None:
            np.testing.assert_array_equal(declared[::2], previous)
            np.testing.assert_array_equal(declared[1::2], (previous[:-1] + previous[1:]) / 2)
        previous = declared
        spec = parse_spec(raw)
        assert spec == parse_spec(spec.to_dict())
        grid, baseline = EventGrid(spec), EventGrid(parse_spec(original))
        assert grid.exact_index(panel.INTERVENTION_TIME) == baseline.exact_index(
            panel.INTERVENTION_TIME
        )
        for time in (*declared, *spec.experiment.observation_times):
            assert grid[grid.exact_index(float(time))] == time
        assert grid[-1] == 0.5 and len(spec.experiment.changes) == len(
            parse_spec(original).experiment.changes
        )


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
