"""Physical face calculus: independent exact fixtures and conservation identities."""

from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_stencil as stencil
from tests.unit.test_rectangular_environment import save as save_arrays
from tests.unit.test_rectangular_environment import spec


def save(name, **data):
    save_arrays(
        name,
        **{
            key: value.item() if isinstance(value, np.generic) else value
            for key, value in data.items()
        },
    )


def test_independent_fraction_fixture_gradient_action_and_formal_energy():
    grid = field.bind(spec(dx=2.0, dy=0.5))
    value = np.array([0.0, 1.0, 2.0, 4.0])
    faces = stencil.gradient(value, grid)
    result = stencil.divergence(faces, grid)
    expected = (Fraction(33, 4), Fraction(47, 4), Fraction(-15, 2), Fraction(-25, 2))
    energy = -grid.cell_area_m2 * np.dot(value, result.values)
    save(
        "fraction-faces",
        grid=grid,
        value=value,
        x=faces.x,
        y=faces.y,
        divergence=result.values,
        exact=[str(v) for v in expected],
        boundary=result.boundary_integral,
        balance=result.balance_residual,
        formal_energy=float(energy),
        exact_energy="213/4",
    )
    np.testing.assert_array_equal(faces.x, [[0, 0.5, 0], [0, 1, 0]])
    np.testing.assert_array_equal(faces.y, [[0, 0], [4, 6], [0, 0]])
    np.testing.assert_array_equal(result.values, [float(v) for v in expected])
    assert result.usable and result.cell_integral == result.boundary_integral == 0
    assert result.balance_residual == 0 and Fraction(float(energy)) == Fraction(213, 4)


def test_linear_physical_coordinates_have_correct_faces_and_boundary_signs():
    grid = field.bind(spec((2, 3), dx=2.0, dy=4.0))
    value = 3 * grid.coordinates_m[:, 0] - 2 * grid.coordinates_m[:, 1] + 5
    faces = stencil.gradient(value, grid)
    result = stencil.divergence(faces, grid)
    save("linear-faces", grid=grid, value=value, x=faces.x, y=faces.y, action=result.values)
    np.testing.assert_array_equal(faces.x, [[0, 3, 3, 0], [0, 3, 3, 0]])
    np.testing.assert_array_equal(faces.y, [[0, 0, 0], [-2, -2, -2], [0, 0, 0]])
    np.testing.assert_array_equal(result.values, [1, -0.5, -2, 2, 0.5, -1])
    assert -grid.cell_area_m2 * np.dot(value, result.values) == 384


def test_quadratic_interior_is_analytic_and_outer_faces_remain_zero():
    grid = field.bind(spec((4, 5), dx=0.5, dy=0.25))
    x, y = grid.coordinates_m.T
    value = x * x + 2 * y * y
    faces = stencil.gradient(value, grid)
    result = stencil.divergence(faces, grid)
    save("quadratic-interior", grid=grid, value=value, x=faces.x, y=faces.y, action=result.values)
    np.testing.assert_array_equal(faces.x[:, 1:-1], np.tile(2 * grid.vertices_x_m[1:-1], (4, 1)))
    np.testing.assert_array_equal(faces.y[1:-1], np.tile(4 * grid.vertices_y_m[1:-1, None], (1, 5)))
    np.testing.assert_array_equal(result.values.reshape(4, 5)[1:-1, 1:-1], np.full((2, 3), 6.0))
    assert result.usable and result.balance_residual == 0
    assert np.all(faces.x[:, (0, -1)] == 0) and np.all(faces.y[(0, -1), :] == 0)


def test_independent_nonzero_boundary_fixture_is_retained_but_unusable():
    grid = field.bind(spec(dx=2.0, dy=0.5))
    faces = stencil.Faces(
        np.array([[1.0, 3.0, 2.0], [0.0, -1.0, 4.0]]),
        np.array([[2.0, -2.0], [1.0, 3.0], [-1.0, 5.0]]),
    )
    before = (faces.x.tobytes(), faces.y.tobytes())
    result = stencil.divergence(faces, grid)
    expected = [Fraction(-1), Fraction(19, 2), Fraction(-9, 2), Fraction(13, 2)]
    save(
        "boundary-flux",
        grid=grid,
        x=faces.x,
        y=faces.y,
        action=result.values,
        boundary=result.boundary_integral,
        cell_integral=result.cell_integral,
        usable=result.usable,
        exact=[str(v) for v in expected],
    )
    np.testing.assert_array_equal(result.values, [float(v) for v in expected])
    assert result.boundary_integral == result.cell_integral == 10.5
    assert result.balance_residual == 0 and result.finite_result and not result.usable
    assert (faces.x.tobytes(), faces.y.tobytes()) == before


def test_zero_net_boundary_does_not_admit_nonzero_boundary_faces():
    grid = field.bind(spec(dx=2.0, dy=0.5))
    faces = stencil.Faces(np.ones((2, 3)), np.zeros((3, 2)))
    result = stencil.divergence(faces, grid)
    save(
        "balanced-nonzero-boundary",
        grid=grid,
        x=faces.x,
        y=faces.y,
        action=result.values,
        boundary=result.boundary_integral,
        zero_boundary=result.zero_boundary,
    )
    assert result.cell_integral == result.boundary_integral == 0 and result.finite_result
    assert not result.zero_boundary and not result.usable
    np.testing.assert_array_equal(result.values, np.zeros(4))


def test_discrete_integration_by_parts_includes_physical_face_weights():
    grid = field.bind(spec((2, 3), dx=2.0, dy=0.5))
    value = np.array([0.0, 1.0, -2.0, 4.0, 3.0, 6.0])
    faces = stencil.Faces(
        np.array([[0.0, 2.0, -1.0, 0.0], [0.0, 3.0, 4.0, 0.0]]),
        np.array([[0.0, 0.0, 0.0], [1.0, -2.0, 5.0], [0.0, 0.0, 0.0]]),
    )
    gradient = stencil.gradient(value, grid)
    result = stencil.divergence(faces, grid)
    left = grid.cell_area_m2 * np.dot(value, result.values)
    right = -grid.cell_area_m2 * (np.sum(gradient.x * faces.x) + np.sum(gradient.y * faces.y))
    save(
        "summation-by-parts",
        grid=grid,
        value=value,
        x=faces.x,
        y=faces.y,
        gradient_x=gradient.x,
        gradient_y=gradient.y,
        action=result.values,
        left=float(left),
        right=float(right),
    )
    assert left == right and result.cell_integral == 0 and result.usable


@pytest.mark.parametrize("constant", [0.0, 1.0, float(2**40), 1e300])
def test_finite_constant_is_annihilated_without_dense_products(constant):
    grid = field.bind(spec((3, 4), dx=1.0, dy=1.25))
    value = np.full(12, constant)
    result = stencil.apply(value, grid)
    save("constant-" + constant.hex(), grid=grid, value=value, action=result)
    np.testing.assert_array_equal(result, np.zeros(12))


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (1.0, 1.25)])
def test_dense_and_face_actions_agree_with_explicit_roundoff_bound(dx, dy):
    grid = field.bind(spec((3, 4), dx=dx, dy=dy))
    value = np.array([1, -2, 5, 3, -1, 4, 0, 2, 6, -3, -4, -2], dtype=np.float64)
    dense, result = field.apply(value, grid), stencil.apply(value, grid)
    # Distinct evaluation orders of the same bounded-degree stencil. This is
    # an explicit small-fixture roundoff bound, not a native comparison budget.
    bound = 64 * np.finfo(float).eps * np.max(np.abs(value)) * (1 / dx**2 + 1 / dy**2)
    save(
        f"dense-face-{dx}-{dy}",
        grid=grid,
        value=value,
        dense=dense,
        action=result,
        roundoff_bound=float(bound),
    )
    assert np.max(np.abs(dense - result)) <= bound


def test_multiple_batch_axes_do_not_mix_worlds_and_refuse_only_invalid_rows():
    grid = field.bind(spec(dx=2.0, dy=0.5))
    x, y = np.zeros((2, 2, 2, 3)), np.zeros((2, 2, 3, 2))
    x[0, 1] = 1
    x[1, 0, 0, 1] = np.nan
    y[1, 1, 1, 0] = np.inf
    before = (x.tobytes(), y.tobytes())
    with np.errstate(invalid="ignore"):
        result = stencil.divergence(stencil.Faces(x, y), grid)
    save(
        "batch-refusals",
        grid=grid,
        x=x,
        y=y,
        action=result.values,
        boundary=result.boundary_integral,
        cell_integral=result.cell_integral,
        balance=result.balance_residual,
        usable=result.usable,
        finite=result.finite_result,
    )
    assert result.values.shape == (2, 2, 4)
    np.testing.assert_array_equal(result.usable, [[True, False], [False, False]])
    np.testing.assert_array_equal(result.finite_result, [[True, True], [False, False]])
    np.testing.assert_array_equal(result.values[0], np.zeros((2, 4)))
    assert (x.tobytes(), y.tobytes()) == before


def test_gradient_and_action_keep_two_leading_batch_axes_independent():
    grid = field.bind(spec(dx=2.0, dy=0.5))
    scales = np.array([[1.0, -2.0, 3.0], [4.0, 0.0, 1.5]])[..., None]
    offsets = np.arange(6, dtype=np.float64).reshape(2, 3, 1) * 10
    value = scales * np.array([0.0, 1.0, 2.0, 4.0]) + offsets
    before = value.tobytes()
    faces = stencil.gradient(value, grid)
    result = stencil.divergence(faces, grid)
    expected = scales * np.array([8.25, 11.75, -7.5, -12.5])
    save(
        "batch-gradient",
        grid=grid,
        value=value,
        x=faces.x,
        y=faces.y,
        action=result.values,
        expected=expected,
        usable=result.usable,
    )
    assert faces.x.shape == (2, 3, 2, 3) and faces.y.shape == (2, 3, 3, 2)
    np.testing.assert_array_equal(result.values, expected)
    np.testing.assert_array_equal(result.balance_residual, np.zeros((2, 3)))
    assert np.all(result.usable) and value.tobytes() == before


def test_finite_input_overflow_is_retained_and_marked_unusable():
    grid = field.bind(spec(dx=2.0, dy=0.5))
    largest = np.finfo(float).max
    value = np.array([-largest, largest, largest, -largest])
    before = value.tobytes()
    with np.errstate(over="ignore", invalid="ignore"):
        faces = stencil.gradient(value, grid)
        result = stencil.divergence(faces, grid)
    save(
        "overflow",
        grid=grid,
        value=value,
        x=faces.x,
        y=faces.y,
        action=result.values,
        usable=result.usable,
    )
    assert value.tobytes() == before and result.zero_boundary
    assert not result.finite_result and not result.usable
    assert not np.all(np.isfinite(result.values))


def test_metric_units_and_exact_representable_gauge_shift():
    original = field.bind(spec(dx=2.0, dy=0.5))
    scale = float(2**-20)
    small = field.bind(spec(dx=2 * scale, dy=0.5 * scale))
    value = np.array([0.0, 1.0, 2.0, 4.0])
    a, b = stencil.gradient(value, original), stencil.gradient(value, small)
    shifted = stencil.gradient(value + 2**40, original)
    save("units-gauge", grid=small, value=value, x=b.x, y=b.y, action=stencil.apply(value, small))
    np.testing.assert_array_equal(b.x, a.x / scale)
    np.testing.assert_array_equal(b.y, a.y / scale)
    np.testing.assert_array_equal(
        stencil.apply(value, small), stencil.apply(value, original) / scale**2
    )
    np.testing.assert_array_equal(shifted.x, a.x)
    np.testing.assert_array_equal(shifted.y, a.y)


def test_action_never_reads_dense_operators_or_calls_an_inverse(monkeypatch):
    grid = field.bind(spec(dx=2.0, dy=0.5))
    # The fixture poisons unrelated numerical buffers; it is not a new binding
    # or proof of authority. Only the existing physical metric is exercised.
    unused = object()
    metadata_only = replace(grid, laplacian=unused, compatible_inverse=unused)
    monkeypatch.setattr(np.linalg, "inv", lambda *a: pytest.fail("No inverse during action"))
    monkeypatch.setattr(np, "matmul", lambda *a: pytest.fail("No dense matrix product"))
    result = stencil.apply(np.array([0.0, 1.0, 2.0, 4.0]), metadata_only)
    save("no-dense-action", action=result, dense_buffers_unread=True)
    np.testing.assert_array_equal(result, [8.25, 11.75, -7.5, -12.5])


@pytest.mark.parametrize(
    "case",
    [
        "faces_type",
        "x_shape",
        "y_shape",
        "batch",
        "x_dtype",
        "y_dtype",
        "grid",
        "cell_dtype",
        "cell_shape",
    ],
)
def test_incomplete_or_implicitly_broadcast_fields_refuse(case):
    grid = field.bind(spec(dx=2.0, dy=0.5))
    faces = stencil.Faces(np.zeros((2, 3)), np.zeros((3, 2)))
    if case == "faces_type":
        faces = (faces.x, faces.y)
    elif case == "x_shape":
        faces = faces._replace(x=np.zeros((2, 2)))
    elif case == "y_shape":
        faces = faces._replace(y=np.zeros((2, 3)))
    elif case == "batch":
        faces = faces._replace(x=np.zeros((1, 2, 3)))
    elif case == "x_dtype":
        faces = faces._replace(x=faces.x.astype(np.float32))
    elif case == "y_dtype":
        faces = faces._replace(y=faces.y.astype(np.float32))
    elif case == "grid":
        grid = object()
    with pytest.raises(ValueError) as caught:
        if case == "cell_dtype":
            stencil.gradient(np.ones(4, dtype=np.float32), grid)
        elif case == "cell_shape":
            stencil.gradient(np.zeros(3), grid)
        else:
            stencil.divergence(faces, grid)
    save("schema-" + case, error=str(caught.value))
