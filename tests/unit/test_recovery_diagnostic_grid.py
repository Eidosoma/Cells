"""Local recovery diagnostics retain the declared horizon and exact boundaries."""

import numpy as np
import pytest

from validation.tissue.cotransport_recovery_diagnostic import diagnostic_grid


def test_unchanged_uniform_grid_and_explicit_binary_refinement():
    start, end = 0.25, 0.2500125
    inputs = dict(subdivisions=[2, 4])
    for n in inputs["subdivisions"]:
        np.testing.assert_array_equal(
            diagnostic_grid(inputs, n, start, end), np.linspace(start, end, n + 1)
        )
    interior = start + 2.0**-48
    coarse = [start, interior, end]
    fine = [start, (start + interior) / 2, interior, (interior + end) / 2, end]
    inputs["numerical_grids_s"] = {"2": coarse, "4": fine}
    np.testing.assert_array_equal(diagnostic_grid(inputs, 2, start, end), coarse)
    np.testing.assert_array_equal(diagnostic_grid(inputs, 4, start, end)[::2], coarse)


@pytest.mark.parametrize(
    "times",
    [
        [0.25, 0.25, 0.2500125],
        [0.25, float("nan"), 0.2500125],
        [0.25, True, 0.2500125],
        [0.25, 0.25002, 0.2500125],
        [0.24, 0.250001, 0.2500125],
        [0.25, 0.250001, 0.250013],
        [0.25, 0.2500125],
    ],
)
def test_bad_local_grids_are_refused(times):
    with pytest.raises(ValueError):
        diagnostic_grid(dict(subdivisions=[2], numerical_grids_s={"2": times}), 2, 0.25, 0.2500125)


def test_unused_or_duplicate_cases_are_refused():
    for counts, grids in (
        ([2, 2], {"2": [0.25, 0.250001, 0.2500125]}),
        ([2], {"2": [0.25, 0.250001, 0.2500125], "4": []}),
    ):
        with pytest.raises(ValueError):
            diagnostic_grid(dict(subdivisions=counts, numerical_grids_s=grids), 2, 0.25, 0.2500125)
