"""Exact tensor-product weights, owner ordering and inherited error categories."""

from fractions import Fraction
from itertools import product

import numpy as np
import pytest

from cells.processes.betse_deformation import quartic_display_interpolator
from validation.betse.betse_mechanics_join_checks import budget


def exact_weights(target):
    """Six-node quartic least squares, using the exact degree-five null vector.

    Fifth finite differences annihilate degrees 0..4 on nodes 0..5. Project
    the degree-five cardinal weights off that null vector, without fitting
    polynomials, calling a numerical solver or using the production basis.
    """
    target = max(Fraction(0), min(Fraction(5), target))
    cardinal = []
    for i in range(6):
        value = Fraction(1)
        for j in range(6):
            if j != i:
                value *= (target - j) / (i - j)
        cardinal.append(value)
    null = (-1, 5, -10, 10, -5, 1)
    dot = sum(value * n for value, n in zip(cardinal, null, strict=True))
    return [value - dot * n / 252 for value, n in zip(cardinal, null, strict=True)]


@pytest.mark.parametrize("micrometre_scale", [False, True])
@pytest.mark.parametrize("reorder", [False, True])
def test_all_quartic_weights_against_exact_tensor_product(micrometre_scale, reorder):
    centres = list(product(range(6), repeat=2))
    targets = [
        (Fraction(x) + dx, Fraction(y) + dy)
        for x, y in centres
        for dx, dy in product((Fraction(-3, 8), Fraction(3, 8)), repeat=2)
    ]
    expected = np.asarray(
        [
            [float(wx[x] * wy[y]) for x, y in centres]
            for wx, wy in [(exact_weights(x), exact_weights(y)) for x, y in targets]
        ]
    )
    coordinates, vertices = np.asarray(centres, float), np.asarray(targets, float)
    if micrometre_scale:
        # Dyadic units/offsets preserve the rational problem exactly in binary64.
        scale, offset = np.asarray([2.0**-17, 2.0**-18]), np.asarray([2.0**-12, -3 * 2.0**-13])
        coordinates, vertices = coordinates * scale + offset, vertices * scale + offset
    if reorder:
        order = (13 * np.arange(36)) % 36
        coordinates, expected = coordinates[order], expected[:, order]
    saved_centres, saved_vertices = coordinates.copy(), vertices.copy()
    actual = quartic_display_interpolator(coordinates, vertices)
    np.testing.assert_allclose(actual, expected, rtol=8e-12, atol=2e-14)
    np.testing.assert_array_equal(coordinates, saved_centres)
    np.testing.assert_array_equal(vertices, saved_vertices)


@pytest.mark.parametrize("invalid", ["too_few", "flat_axis", "line", "nonfinite", "vertex_axis"])
def test_quartic_map_retains_explicit_domain_refusals(invalid):
    centres = np.asarray(list(product(range(6), repeat=2)), float)
    vertices = np.asarray([[0.25, 0.75]])
    if invalid == "too_few":
        centres = centres[:24]
    elif invalid == "flat_axis":
        centres[:, 0] = 1.0
    elif invalid == "line":
        centres[:, 1] = centres[:, 0]
    elif invalid == "nonfinite":
        centres[0, 0] = np.nan
    else:
        vertices = np.zeros((2, 3))
    with pytest.raises(ValueError):
        quartic_display_interpolator(centres, vertices)


@pytest.mark.parametrize(
    ("name", "absolute"),
    [
        (".0.auxiliaries.steady.divergence_numeric", 3e-14),
        (".0.auxiliaries.steady.displacement_m", 3e-20),
        (".0.sample.interpolation", 2e-14),
        (".0.sample.vertices_m", 3e-17),
        (".0.auxiliaries.steady.pressure_gradient_Pa_m", 3e-9),
    ],
)
def test_inherited_mechanics_budget_categories(name, absolute):
    assert budget(name, 0.0) == absolute
    assert budget(name, -0.125) == absolute + 8e-12 * 0.125
