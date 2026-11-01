"""Metric-only binding: exact small algebra and bounded larger-grid storage."""

from dataclasses import fields, replace
from fractions import Fraction

import numpy as np
import pytest

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_stencil as stencil
from tests.unit.test_rectangular_environment import save as save_arrays
from tests.unit.test_rectangular_environment import spec


def save(name, grid=None, **data):
    if grid is not None:
        data.update(
            metric_identity=grid.identity,
            shape=grid.shape,
            spacing_xy_m=grid.spacing_xy_m,
            coordinates=grid.coordinates_m,
            x_vertices=grid.vertices_x_m,
            y_vertices=grid.vertices_y_m,
        )
    save_arrays(
        "metric-" + name,
        **{
            key: value.item() if isinstance(value, np.generic) else value
            for key, value in data.items()
        },
    )


def forbid_dense(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Metric/stencil path must not build or solve a dense system")

    for name in ("inv", "pinv", "solve", "lstsq"):
        monkeypatch.setattr(np.linalg, name, forbidden)
    monkeypatch.setattr(np, "matmul", forbidden)


def exact_action(shape, dx, dy, values):
    """Independent rational node-balance law, without face kernels or matrices."""
    ny, nx = shape
    answer = []
    for row in range(ny):
        for col in range(nx):
            value = Fraction(values[row * nx + col])
            total = Fraction(0)
            for r, c, distance in (
                (row, col - 1, dx),
                (row, col + 1, dx),
                (row - 1, col, dy),
                (row + 1, col, dy),
            ):
                if 0 <= r < ny and 0 <= c < nx:
                    total += (Fraction(values[r * nx + c]) - value) / Fraction(distance) ** 2
            answer.append(total)
    return tuple(answer)


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (1.0, 1.25)])
def test_metric_action_matches_independent_fraction_balance(dx, dy, monkeypatch):
    forbid_dense(monkeypatch)
    grid = field.bind_metric(spec((2, 3), dx=dx, dy=dy))
    value = np.array([1, -3, 4, 0, 2, -4], dtype=np.float64)
    expected = exact_action(grid.shape, dx, dy, [int(x) for x in value])
    result = stencil.divergence(stencil.gradient(value, grid), grid)
    exact = np.array([float(x) for x in expected])
    bound = 64 * np.finfo(float).eps * np.max(np.abs(value)) * (1 / dx**2 + 1 / dy**2)
    save(
        f"rational-{dx}-{dy}",
        grid,
        value=value,
        action=result.values,
        rational=[str(x) for x in expected],
        roundoff_bound=float(bound),
        cell_integral=result.cell_integral,
        balance=result.balance_residual,
    )
    assert np.max(np.abs(result.values - exact)) <= bound
    assert result.usable and sum(expected) == 0
    assert abs(result.cell_integral) <= grid.cell_area_m2 * len(value) * bound


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (2e-6, 1e-6)])
def test_dense_and_metric_routes_share_exact_geometry_and_stencil_outputs(dx, dy):
    incoming = spec((3, 4), dx=dx, dy=dy)
    dense, metric = field.bind(incoming), field.bind_metric(incoming)
    before = incoming.coordinates_m.tobytes()
    for name in (
        "environment_ids",
        "shape",
        "bounds_m",
        "spacing_xy_m",
        "cell_area_m2",
        "provenance_json",
    ):
        assert getattr(dense, name) == getattr(metric, name)
    for name in ("coordinates_m", "vertices_x_m", "vertices_y_m"):
        assert getattr(dense, name).tobytes() == getattr(metric, name).tobytes()
    values = np.arange(24, dtype=np.float64).reshape(2, 12) - 7
    a, b = stencil.gradient(values, dense), stencil.gradient(values, metric)
    x, y = stencil.divergence(a, dense), stencil.divergence(b, metric)
    save(
        f"dense-agreement-{dx}-{dy}",
        metric,
        value=values,
        action=x.values,
        dense_identity=dense.identity,
    )
    for left, right in zip((*a, *x), (*b, *y), strict=True):
        assert left.dtype == right.dtype and left.shape == right.shape
        assert left.tobytes() == right.tobytes()
    assert incoming.coordinates_m.tobytes() == before
    assert dense.identity != metric.identity


def test_larger_binding_and_batched_action_need_only_linear_storage(monkeypatch):
    incoming = spec((48, 64), dx=2.0, dy=0.5)
    n = len(incoming.environment_ids)
    forbid_dense(monkeypatch)
    original_zeros = np.zeros

    def bounded_zeros(shape, *args, **kwargs):
        assert int(np.prod(shape)) <= 8 * n, "Quadratic allocation is outside this binding"
        return original_zeros(shape, *args, **kwargs)

    monkeypatch.setattr(np, "zeros", bounded_zeros)
    grid = field.bind_metric(incoming)
    assert n > field.MAX_POINTS
    arrays = [getattr(grid, item.name) for item in fields(grid)]
    arrays = [value for value in arrays if type(value) is np.ndarray]
    total_entries = sum(value.size for value in arrays)
    assert total_entries == 2 * n + 65 + 49
    assert not hasattr(grid, "laplacian") and not hasattr(grid, "compatible_inverse")
    x, y = grid.coordinates_m.T
    value = 3 * x - 2 * y
    values = np.stack((value, 2 * value, np.ones(n))).reshape(1, 3, n)
    result = stencil.divergence(stencil.gradient(values, grid), grid)
    ny, nx = grid.shape
    expected = original_zeros(grid.shape)
    expected[:, 0] += 3 / 2
    expected[:, -1] -= 3 / 2
    expected[0, :] -= 2 / 0.5
    expected[-1, :] += 2 / 0.5
    energy = -grid.cell_area_m2 * np.dot(value, result.values[0, 0])
    independent_energy = grid.cell_area_m2 * (ny * (nx - 1) * 9 + (ny - 1) * nx * 4)
    save(
        "larger-linear-storage",
        grid,
        input=values,
        action=result.values,
        expected=expected,
        stored_array_entries=total_entries,
        stored_array_bytes=sum(a.nbytes for a in arrays),
        energy=float(energy),
        independent_energy=float(independent_energy),
        integrated=result.cell_integral,
        balance=result.balance_residual,
    )
    np.testing.assert_array_equal(result.values[0, 0], expected.reshape(-1))
    np.testing.assert_array_equal(result.values[0, 1], 2 * expected.reshape(-1))
    np.testing.assert_array_equal(result.values[0, 2], np.zeros(n))
    np.testing.assert_array_equal(result.balance_residual, np.zeros((1, 3)))
    assert np.all(result.usable) and energy == independent_energy
    with pytest.raises(ValueError, match="at most625"):
        field.bind(incoming)
    for operation in (field.apply, field.solve):
        with pytest.raises(ValueError, match="binding"):
            operation(value, grid)


@pytest.mark.parametrize(
    "change",
    [
        "ids",
        "centres",
        "vertices",
        "nonfinite",
        "dtype",
        "translation",
        "underflow",
        "provenance",
        "limit",
    ],
)
def test_metric_route_retains_all_geometry_gates(change, monkeypatch):
    incoming = spec()
    if change == "ids":
        incoming = replace(incoming, environment_ids=("duplicate",) * 4)
    elif change == "centres":
        incoming.coordinates_m[[0, 1]] = incoming.coordinates_m[[1, 0]]
    elif change == "vertices":
        incoming.vertices_x_m[1] += 0.01
    elif change == "nonfinite":
        incoming.coordinates_m[0, 0] = np.nan
    elif change == "dtype":
        incoming = replace(incoming, vertices_x_m=incoming.vertices_x_m.astype(np.float32))
    elif change == "translation":
        offset = float(2**50)
        incoming = replace(
            incoming,
            bounds_m=(offset, offset + 2, 0.0, 2.5),
            vertices_x_m=incoming.vertices_x_m + offset,
            coordinates_m=incoming.coordinates_m + [offset, 0],
        )
    elif change == "underflow":
        incoming = spec(dx=1e-200, dy=1e-200)
    elif change == "provenance":
        incoming = replace(incoming, provenance={})
    else:
        incoming = replace(incoming, shape=(1024, 1025))
    forbid_dense(monkeypatch)
    with pytest.raises(ValueError) as caught:
        field.bind_metric(incoming)
    save("refusal-" + change, error=str(caught.value))


def test_metric_arrays_cannot_be_rearmed_and_provenance_is_bound():
    incoming = spec()
    grid = field.bind_metric(incoming)
    original = (grid.identity, grid.coordinates_m.tobytes(), grid.provenance_json)
    for name in ("coordinates_m", "vertices_x_m", "vertices_y_m"):
        with pytest.raises(ValueError):
            getattr(grid, name).setflags(write=True)
    incoming.coordinates_m[0, 0] = -9
    incoming.provenance["changed"] = True
    assert original == (grid.identity, grid.coordinates_m.tobytes(), grid.provenance_json)
    same = field.bind_metric(spec())
    other = field.bind_metric(replace(spec(), provenance={"kind": "different declared origin"}))
    assert same.identity == grid.identity != other.identity
    save("immutability", grid, different_provenance_identity=other.identity)


def test_nonfinite_batch_row_retains_raw_arithmetic_without_contaminating_neighbors():
    grid = field.bind_metric(spec(dx=2.0, dy=0.5))
    values = np.array([[0.0, 1.0, 2.0, 4.0], [np.nan, 1, 2, 4], [1, 1, 1, 1]])
    before = values.tobytes()
    result = stencil.divergence(stencil.gradient(values, grid), grid)
    save("nonfinite-batch", grid, values=values, action=result.values, usable=result.usable)
    np.testing.assert_array_equal(result.usable, [True, False, True])
    np.testing.assert_array_equal(result.values[0], [8.25, 11.75, -7.5, -12.5])
    np.testing.assert_array_equal(result.values[2], np.zeros(4))
    assert values.tobytes() == before and np.isnan(result.values[1]).any()


@pytest.mark.parametrize(
    "change",
    ["value_shape", "value_dtype", "face_shape", "face_batch", "face_dtype", "foreign_grid"],
)
def test_metric_stencils_keep_explicit_field_shape_and_dtype_checks(change):
    grid = field.bind_metric(spec())
    faces = stencil.Faces(np.zeros((2, 3)), np.zeros((3, 2)))
    if change == "face_shape":
        faces = faces._replace(x=np.zeros((2, 2)))
    elif change == "face_batch":
        faces = faces._replace(x=np.zeros((1, 2, 3)))
    elif change == "face_dtype":
        faces = faces._replace(y=faces.y.astype(np.float32))
    elif change == "foreign_grid":
        grid = object()
    with pytest.raises(ValueError) as caught:
        if change == "value_shape":
            stencil.gradient(np.ones(3), grid)
        elif change == "value_dtype":
            stencil.gradient(np.ones(4, dtype=np.float32), grid)
        else:
            stencil.divergence(faces, grid)
    save("field-refusal-" + change, error=str(caught.value))
