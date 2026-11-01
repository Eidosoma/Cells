"""Independent algebra and failure gates for the matrix-free rectangular solve."""

from fractions import Fraction

import numpy as np
import pytest

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_iterative as iterative
from cells.processes import rectangular_environment_stencil as stencil
from tests.unit.test_rectangular_environment import exact_four, spec
from tests.unit.test_rectangular_environment import save as save_arrays


def save(name, grid=None, result=None, **data):
    if grid is not None:
        data.update(
            metric_identity=grid.identity,
            shape=grid.shape,
            spacing_xy_m=grid.spacing_xy_m,
            coordinates=grid.coordinates_m,
            x_vertices=grid.vertices_x_m,
            y_vertices=grid.vertices_y_m,
        )
    if result is not None:
        data.update({key: np.asarray(value) for key, value in result._asdict().items()})
        data["converged"] = np.asarray(result.converged)
    save_arrays("iterative-" + name, **data)


def forbid_dense(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Iterative solve must not construct or use dense operators")

    for name in ("inv", "pinv", "solve", "lstsq", "eig", "eigh"):
        monkeypatch.setattr(np.linalg, name, forbidden)
    for name in ("matmul", "dot", "eye", "diag"):
        monkeypatch.setattr(np, name, forbidden)


def rational_action(values, shape, dx, dy):
    """Independent node balance, without production face/operator helpers."""
    ny, nx = shape
    total = []
    for row in range(ny):
        for col in range(nx):
            v = Fraction(values[row * nx + col])
            value = Fraction(0)
            for r, c, spacing in (
                (row, col - 1, dx),
                (row, col + 1, dx),
                (row - 1, col, dy),
                (row + 1, col, dy),
            ):
                if 0 <= r < ny and 0 <= c < nx:
                    value += (Fraction(values[r * nx + c]) - v) / Fraction(spacing) ** 2
            total.append(value)
    return total


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (1.0, 1.25)])
def test_matches_independent_exact_four_node_system(dx, dy, monkeypatch):
    forbid_dense(monkeypatch)
    grid = field.bind_metric(spec(dx=dx, dy=dy))
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    exact = exact_four(1 / Fraction(dx) ** 2, 1 / Fraction(dy) ** 2, (1, -1, 2, -2))
    result = iterative.solve(rhs, grid, max_iterations=12, rtol=2e-13)
    expected = np.array([float(v) for v in exact])
    save(f"four-{dx}-{dy}", grid, result, rhs=rhs, exact=[str(v) for v in exact])
    assert result.converged and 0 < result.iterations <= 12
    np.testing.assert_allclose(result.potential, expected, rtol=2e-13, atol=2e-14)
    assert result.residual_inf <= result.tolerance
    assert abs(result.gauge_mean) <= 64 * np.finfo(float).eps * np.max(abs(expected))


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (2e-6, 1e-6)])
def test_dense_comparison_and_independent_rational_balance(dx, dy):
    incoming = spec((3, 4), dx=dx, dy=dy)
    metric, dense = field.bind_metric(incoming), field.bind(incoming)
    integers = [1, -2, 5, 3, -1, 4, 0, 2, 6, -3, -4, -11]
    assert sum(integers) == 0
    exact = rational_action(integers, metric.shape, dx, dy)
    rhs = np.array([float(v) for v in exact])
    expected = np.array(integers, dtype=np.float64)
    result = iterative.solve(rhs, metric, max_iterations=100, rtol=2e-12)
    existing = field.solve(rhs, dense)
    save(
        f"balance-{dx}-{dy}",
        metric,
        result,
        rhs=rhs,
        expected=expected,
        exact_rhs=[str(v) for v in exact],
        dense_potential=existing.potential,
    )
    assert result.converged and existing.usable
    np.testing.assert_allclose(result.potential, expected, rtol=0, atol=5e-11)
    np.testing.assert_allclose(result.potential, existing.potential, rtol=0, atol=5e-11)


def test_large_batched_analytic_modes_without_dense_storage(monkeypatch):
    forbid_dense(monkeypatch)
    grid = field.bind_metric(spec((48, 64), dx=2.0, dy=0.5))
    ny, nx = grid.shape
    n = ny * nx
    original_zeros = np.zeros

    def linear_zeros(shape, *args, **kwargs):
        assert int(np.prod(shape)) <= 8 * n, "Quadratic array allocation"
        return original_zeros(shape, *args, **kwargs)

    monkeypatch.setattr(np, "zeros", linear_zeros)
    # Independently known eigenvectors/eigenvalues of a Neumann path product.
    x = np.cos(3 * np.pi * (np.arange(nx) + 0.5) / nx)[None, :]
    y = np.cos(2 * np.pi * (np.arange(ny) + 0.5) / ny)[:, None]
    ex = 4 * np.sin(3 * np.pi / (2 * nx)) ** 2 / 2.0**2
    ey = 4 * np.sin(2 * np.pi / (2 * ny)) ** 2 / 0.5**2
    potentials = np.stack((np.broadcast_to(x, grid.shape), x * y, x + 0.25 * y))
    rhs = np.stack(
        (np.broadcast_to(-ex * x, grid.shape), -(ex + ey) * x * y, -ex * x - 0.25 * ey * y)
    )
    potentials, rhs = potentials.reshape(1, 3, n), rhs.reshape(1, 3, n)
    result = iterative.solve(rhs, grid, max_iterations=1024, rtol=2e-10)
    save(
        "large-modes",
        grid,
        result,
        rhs=rhs,
        expected=potentials,
        eigenvalues=[float(ex), float(ey)],
        max_iterations=1024,
        scope="3072-cell manufactured fields, not a general performance benchmark",
    )
    assert np.all(result.converged)
    np.testing.assert_allclose(result.potential, potentials, rtol=0, atol=3e-9)
    assert result.iterations.shape == (1, 3)
    assert 0 < result.loop_iterations <= 1024
    assert np.max(result.iterations) == result.loop_iterations
    assert not hasattr(grid, "laplacian") and not hasattr(grid, "compatible_inverse")


def test_batch_members_stop_independently_and_raw_bad_inputs_remain():
    grid = field.bind_metric(spec((3, 4)))
    one_mode = np.tile([1.0, -1.0], 6)
    rhs = np.stack(
        (
            one_mode,
            np.zeros(12),
            np.ones(12),
            np.full(12, np.nan),
            np.full(12, np.inf),
            np.arange(12, dtype=float) - 5.5,
        )
    )
    before = rhs.tobytes()
    with np.errstate(all="ignore"):
        result = iterative.solve(rhs, grid, max_iterations=80, rtol=2e-12)
    separate = iterative.solve(rhs[0], grid, max_iterations=80, rtol=2e-12)
    save("batch", grid, result, rhs=rhs, separate_potential=separate.potential)
    np.testing.assert_array_equal(result.converged, [True, True, False, False, False, True])
    np.testing.assert_array_equal(result.iterations[1:5], np.zeros(4, dtype=np.int32))
    assert result.iterations[0] == separate.iterations
    np.testing.assert_array_equal(result.potential[0], separate.potential)
    np.testing.assert_array_equal(result.residual[2], -np.ones(12))
    assert np.isnan(result.residual[3]).all() and np.isneginf(result.residual[4]).all()
    assert rhs.tobytes() == before


@pytest.mark.parametrize("budget", [0, 1])
def test_iteration_budget_returns_unconverged_candidate(budget):
    grid = field.bind_metric(spec((3, 4)))
    rhs = np.arange(12, dtype=np.float64) - 5.5
    result = iterative.solve(rhs, grid, max_iterations=budget, rtol=1e-13)
    save(f"budget-{budget}", grid, result, rhs=rhs)
    assert not result.converged and not result.breakdown
    assert result.iterations == result.loop_iterations == budget
    assert result.residual_inf > result.tolerance
    np.testing.assert_array_equal(result.residual, stencil.apply(result.potential, grid) - rhs)
    if budget == 0:
        np.testing.assert_array_equal(result.potential, np.zeros(12))


def test_zero_source_and_absolute_tolerance_take_no_steps():
    grid = field.bind_metric(spec())
    rhs = np.array([[0.0] * 4, [1e-9, -1e-9, 1e-9, -1e-9]])
    result = iterative.solve(rhs, grid, max_iterations=100, rtol=0.0, atol=2e-9)
    save("absolute", grid, result, rhs=rhs)
    assert np.all(result.converged) and result.loop_iterations == 0
    np.testing.assert_array_equal(result.potential, np.zeros((2, 4)))
    np.testing.assert_array_equal(result.residual, -rhs)


def test_one_iteration_budget_mixes_success_refusal_and_exhaustion():
    grid = field.bind_metric(spec(dx=2.0, dy=1.0))
    x_mode = np.array([1.0, -1.0, 1.0, -1.0])
    y_mode = np.array([1.0, 1.0, -1.0, -1.0])
    rhs = np.stack((x_mode, x_mode + 2 * y_mode, np.zeros(4), np.ones(4), np.full(4, np.nan)))
    with np.errstate(all="ignore"):
        result = iterative.solve(rhs, grid, max_iterations=1, rtol=2e-13)
    save("mixed-budget", grid, result, rhs=rhs)
    np.testing.assert_array_equal(result.converged, [True, False, True, False, False])
    np.testing.assert_array_equal(result.iterations, [1, 1, 0, 0, 0])
    assert result.loop_iterations == 1 and not np.any(result.breakdown)
    assert result.residual_inf[1] > result.tolerance[1]


def test_extreme_anisotropy_refuses_before_an_axis_weight_is_lost():
    grid = field.bind_metric(spec(dx=1e150, dy=1e-150))
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    with pytest.raises(ValueError, match="anisotropy") as caught:
        iterative.solve(rhs, grid, max_iterations=12, rtol=2e-12)
    save("anisotropy-underflow", grid, rhs=rhs, error=str(caught.value))


@pytest.mark.parametrize("spacing,amplitude", [(1e-150, 1e-200), (1e150, 1e200)])
def test_unrepresentable_physical_candidate_cannot_pass_scaled_residual(spacing, amplitude):
    grid = field.bind_metric(spec(dx=spacing, dy=spacing))
    rhs = np.array([1.0, -1.0, 1.0, -1.0]) * amplitude
    with np.errstate(all="ignore"):
        result = iterative.solve(rhs, grid, max_iterations=12, rtol=2e-12)
    save(f"unrepresentable-{spacing}", grid, result, rhs=rhs)
    assert not result.converged and result.iterations == 1
    if spacing < 1:
        assert result.finite_result and not result.residual_ok
        np.testing.assert_array_equal(result.potential, np.zeros(4))
        np.testing.assert_array_equal(result.residual, -rhs)
    else:
        assert not result.finite_result
        assert not np.all(np.isfinite(result.potential))


def test_overflowed_physical_tolerance_is_not_an_automatic_pass():
    grid = field.bind_metric(spec())
    rhs = np.array([2.0, -2.0, 2.0, -2.0])
    with np.errstate(all="ignore"):
        result = iterative.solve(rhs, grid, max_iterations=12, rtol=1e308)
    save("tolerance-overflow", grid, result, rhs=rhs)
    assert np.isinf(result.tolerance) and not result.converged and not result.finite_result
    assert result.iterations == result.loop_iterations == 0
    np.testing.assert_array_equal(result.residual, -rhs)


@pytest.mark.parametrize("amplitude", [1e-200, 1.0, 1e200])
def test_amplitude_scaling_keeps_dot_products_resolved(amplitude):
    grid = field.bind_metric(spec(dx=2.0, dy=0.5))
    rhs = np.array([1.0, -1.0, 2.0, -2.0]) * amplitude
    exact = exact_four(Fraction(1, 4), Fraction(4), (1, -1, 2, -2))
    result = iterative.solve(rhs, grid, max_iterations=12, rtol=2e-13)
    save(f"amplitude-{amplitude}", grid, result, rhs=rhs, amplitude=amplitude)
    assert result.converged
    np.testing.assert_allclose(
        result.potential / amplitude, list(map(float, exact)), rtol=2e-13, atol=2e-14
    )


def test_near_compatible_forcing_is_never_silently_repaired():
    grid = field.bind_metric(spec(dy=1.0))
    rhs = np.array([1.0, -1.0, 2.0, -2.0 + 1e-13])
    before = rhs.tobytes()
    result = iterative.solve(rhs, grid, max_iterations=8, rtol=0.0, atol=1e-15)
    save("near-compatible", grid, result, rhs=rhs, uncorrected_sum=float(rhs.sum()))
    assert result.rhs_compatible and not result.converged
    assert result.residual_inf > result.tolerance
    assert rhs.tobytes() == before
    np.testing.assert_array_equal(result.residual, stencil.apply(result.potential, grid) - rhs)


def test_dense_binding_can_supply_geometry_without_inverse_access():
    dense = field.bind(spec())
    metric = field.bind_metric(spec())
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    a = iterative.solve(rhs, dense, max_iterations=12, rtol=2e-12)
    b = iterative.solve(rhs, metric, max_iterations=12, rtol=2e-12)
    save("dense-geometry", metric, b, rhs=rhs, dense_potential=a.potential)
    for left, right in zip(a, b, strict=True):
        np.testing.assert_array_equal(left, right)


def test_functional_loop_exit_fixed_state_and_per_member_counts():
    grid = field.bind_metric(spec())
    rhs = np.array([[1.0, -1.0, 2.0, -2.0], [0.0] * 4])
    seen = []

    def loop(condition, body, initial):
        schema = tuple((v.shape, v.dtype) for v in initial)
        current = initial
        while condition(current):
            following = body(current)
            assert tuple((v.shape, v.dtype) for v in following) == schema
            seen.append(following.iterations.copy())
            current = following
        return current

    result = iterative.solve(rhs, grid, max_iterations=12, rtol=2e-12, iteration_loop=loop)
    save("functional-loop", grid, result, rhs=rhs, observed_counts=np.asarray(seen))
    assert np.all(result.converged) and len(seen) == result.loop_iterations
    assert all(row[1] == 0 for row in seen)
    assert result.iterations.dtype == result.loop_iterations.dtype == np.int32


def test_recomputed_original_stencil_rejects_incorrect_loop_result():
    grid = field.bind_metric(spec())
    rhs = np.array([1.0, -1.0, 2.0, -2.0])

    def falsely_finished(condition, body, state):
        return state._replace(r=np.zeros_like(rhs), rr=np.asarray(0.0), active=np.asarray(False))

    result = iterative.solve(
        rhs, grid, max_iterations=12, rtol=1e-12, iteration_loop=falsely_finished
    )
    save("incorrect-loop", grid, result, rhs=rhs)
    assert not result.converged and not result.residual_ok
    np.testing.assert_array_equal(result.residual, -rhs)


def test_zero_curvature_is_explicit_breakdown(monkeypatch):
    grid = field.bind_metric(spec())
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    monkeypatch.setattr(iterative, "_positive_action", lambda values, *args: np.zeros_like(values))
    result = iterative.solve(rhs, grid, max_iterations=12, rtol=1e-12)
    save("breakdown", grid, result, rhs=rhs)
    assert result.breakdown and not result.converged
    assert result.iterations == result.loop_iterations == 1
    np.testing.assert_array_equal(result.potential, np.zeros(4))


def test_empty_batch_is_valid_without_loop_work():
    grid = field.bind_metric(spec())
    rhs = np.empty((0, 4), dtype=np.float64)
    result = iterative.solve(rhs, grid, max_iterations=8, rtol=1e-12)
    save("empty-batch", grid, result, rhs=rhs)
    assert result.potential.shape == (0, 4) and result.converged.shape == (0,)
    assert result.loop_iterations == 0


@pytest.mark.parametrize(
    "options",
    [
        {"max_iterations": -1},
        {"max_iterations": True},
        {"max_iterations": 2**31},
        {"max_iterations": 1.5},
        {"max_iterations": np.int64(3)},
        {"rtol": -1.0},
        {"rtol": float("nan")},
        {"rtol": float("inf")},
        {"rtol": True},
        {"atol": -1.0},
        {"atol": float("inf")},
        {"iteration_loop": 7},
    ],
)
def test_invalid_solver_contracts_refuse_before_iteration(options):
    grid = field.bind_metric(spec())
    supplied = dict(max_iterations=12, rtol=1e-12)
    supplied.update(options)
    with pytest.raises(ValueError) as caught:
        iterative.solve(np.zeros(4, dtype=np.float64), grid, **supplied)
    # repr retains NaN/Inf/options without forcing them into JSON numbers.
    save(
        "invalid-" + next(iter(options)) + "-" + repr(next(iter(options.values()))),
        options=repr(options),
        error=str(caught.value),
    )


@pytest.mark.parametrize("case", ["float32", "shape", "scalar", "unbound", "backend"])
def test_invalid_geometry_field_or_backend_refuses(case):
    grid = field.bind_metric(spec())
    rhs, options = np.zeros(4), {}
    if case == "float32":
        rhs = rhs.astype(np.float32)
    elif case == "shape":
        rhs = np.zeros(5)
    elif case == "scalar":
        rhs = np.asarray(0.0)
    elif case == "unbound":
        grid = spec()
    else:
        options["xp"] = object()
    with pytest.raises(ValueError) as caught:
        iterative.solve(rhs, grid, max_iterations=12, rtol=1e-12, **options)
    save("invalid-field-" + case, error=str(caught.value))


def test_warm_exact_guess_removes_only_voltage_reference_without_iteration():
    grid = field.bind_metric(spec(dy=1.0))
    expected = np.array([1.0, -2.0, 3.0, -2.0])
    rhs = np.array(list(map(float, rational_action(expected, grid.shape, 1.0, 1.0))))
    initial = expected + 128.0
    before = initial.tobytes(), rhs.tobytes()
    result = iterative.solve(rhs, grid, max_iterations=0, rtol=2e-12, initial_potential=initial)
    save("warm-exact", grid, result, rhs=rhs, initial=initial, expected=expected)
    assert result.converged and result.iterations == result.loop_iterations == 0
    np.testing.assert_allclose(result.potential, expected, rtol=0, atol=2e-13)
    assert before == (initial.tobytes(), rhs.tobytes())


def test_warm_wrong_guess_with_zero_budget_retains_uncorrected_residual():
    grid = field.bind_metric(spec(dy=1.0))
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    initial = np.array([2.0, 0.0, -2.0, 0.0])
    result = iterative.solve(rhs, grid, max_iterations=0, rtol=2e-12, initial_potential=initial)
    save("warm-budget", grid, result, rhs=rhs, initial=initial)
    assert not result.converged and result.iterations == 0 and not result.breakdown
    np.testing.assert_array_equal(result.potential, initial)
    np.testing.assert_array_equal(result.residual, stencil.apply(initial, grid) - rhs)


def test_warm_batch_separates_bad_guesses_and_incompatible_original_source():
    grid = field.bind_metric(spec(dy=1.0))
    rhs = np.array([[1.0, -1.0, 2.0, -2.0]] * 5)
    rhs[3] = 1.0
    initial = np.array(
        [
            [3.0, 0.0, -1.0, -2.0],
            [np.nan, 0, 0, 0],
            [np.inf, 0, 0, 0],
            [2.0, -2.0, 2.0, -2.0],
            [0.0] * 4,
        ]
    )
    before = initial.tobytes(), rhs.tobytes()
    with np.errstate(all="ignore"):
        result = iterative.solve(
            rhs, grid, max_iterations=20, rtol=2e-12, initial_potential=initial
        )
    save("warm-batch", grid, result, rhs=rhs, initial=initial)
    np.testing.assert_array_equal(result.converged, [True, False, False, False, True])
    np.testing.assert_array_equal(result.rhs_compatible, [True, True, True, False, True])
    np.testing.assert_array_equal(result.iterations[1:4], [0, 0, 0])
    assert not result.finite_result[1] and not result.finite_result[2]
    assert np.isnan(result.potential[1]).any() and np.isnan(result.potential[2]).any()
    np.testing.assert_array_equal(result.potential[3], initial[3])
    np.testing.assert_array_equal(result.residual[3], stencil.apply(initial[3], grid) - rhs[3])
    assert before == (initial.tobytes(), rhs.tobytes())


def test_warm_nonzero_guess_for_zero_source_uses_original_absolute_tolerance():
    grid = field.bind_metric(spec(dy=1.0))
    rhs = np.zeros(4)
    initial = np.array([2.0, -1.0, 3.0, -4.0])
    result = iterative.solve(
        rhs, grid, max_iterations=12, rtol=0.0, atol=1e-13, initial_potential=initial
    )
    save("warm-zero-source", grid, result, rhs=rhs, initial=initial)
    assert result.converged and result.iterations > 0 and result.tolerance == 1e-13
    np.testing.assert_allclose(result.potential, 0.0, rtol=0, atol=1e-13)


def test_warm_tolerance_is_based_on_original_forcing_not_correction():
    grid = field.bind_metric(spec(dy=1.0))
    exact = np.array([1.0, -1.0, 1.0, -1.0])
    rhs = np.array([-2.0, 2.0, -2.0, 2.0])
    initial = exact * (1 + 1e-8)
    result = iterative.solve(rhs, grid, max_iterations=0, rtol=2e-8, initial_potential=initial)
    save("warm-original-tolerance", grid, result, rhs=rhs, initial=initial)
    assert result.converged and result.iterations == 0
    assert result.tolerance == 2e-8 * max(abs(rhs))
    assert result.residual_inf > 0 and result.residual_inf <= result.tolerance


def test_warm_finite_guess_with_overflowed_operator_remains_failed():
    grid = field.bind_metric(spec(dy=1.0))
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    initial = np.array([1e308, -1e308, 1e308, -1e308])
    before = initial.tobytes()
    with np.errstate(all="ignore"):
        result = iterative.solve(
            rhs, grid, max_iterations=12, rtol=2e-12, initial_potential=initial
        )
    save("warm-operator-overflow", grid, result, rhs=rhs, initial=initial)
    assert result.rhs_compatible and not result.converged and not result.finite_result
    assert result.iterations == 0 and initial.tobytes() == before
    assert not np.all(np.isfinite(result.residual))


def test_warm_failed_setup_is_not_readmitted_by_finite_final_observation(monkeypatch):
    grid = field.bind_metric(spec())
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    initial = np.zeros(4)
    observations = []

    def action(values, grid, *, xp):
        result = np.full(4, np.inf) if not observations else rhs.copy()
        observations.append(result.copy())
        return result

    monkeypatch.setattr(stencil, "apply", action)
    with np.errstate(all="ignore"):
        result = iterative.solve(
            rhs, grid, max_iterations=12, rtol=2e-12, initial_potential=initial
        )
    save(
        "warm-setup-failure-retained",
        grid,
        result,
        rhs=rhs,
        initial=initial,
        observed_actions=np.stack(observations),
    )
    assert len(observations) == 2 and result.iterations == 0
    assert result.residual_ok and result.gauge_ok and result.rhs_compatible
    assert not result.finite_result and not result.converged


def test_warm_functional_loop_preserves_shapes_dtypes_and_batch_masks():
    grid = field.bind_metric(spec(dy=1.0))
    rhs = np.array([[-2.0, 2.0, -2.0, 2.0]] * 2)
    initial = np.array([[1.0, -1.0, 1.0, -1.0], [3.0, 0.0, -1.0, -2.0]])
    counts = []

    def loop(condition, body, state):
        schema = tuple((x.shape, x.dtype) for x in state)
        while condition(state):
            state = body(state)
            assert tuple((x.shape, x.dtype) for x in state) == schema
            counts.append(state.iterations.copy())
        return state

    result = iterative.solve(
        rhs, grid, max_iterations=12, rtol=2e-12, initial_potential=initial, iteration_loop=loop
    )
    save("warm-functional", grid, result, rhs=rhs, initial=initial, counts=np.asarray(counts))
    assert np.all(result.converged) and result.iterations[0] == 0
    assert len(counts) == result.loop_iterations == result.iterations[1]
    assert all(row[0] == 0 for row in counts)


def test_general_forcing_and_repeated_perturbed_solve_keep_original_accuracy(monkeypatch):
    forbid_dense(monkeypatch)
    grid = field.bind_metric(spec((24, 32), dx=2.0, dy=0.5))
    ny, nx = grid.shape
    n = ny * nx
    half = ((np.arange(n // 2) * 37) % 101) - 50
    exact = np.concatenate((half, -half)).astype(np.float64)
    rhs_exact = rational_action(exact, grid.shape, 2.0, 0.5)
    rhs = np.array(list(map(float, rhs_exact)))
    assert sum(rhs_exact) == 0
    cold = iterative.solve(rhs, grid, max_iterations=800, rtol=2e-11)
    previous = cold.potential.copy()
    before = previous.tobytes()
    repeated = iterative.solve(
        rhs, grid, max_iterations=800, rtol=2e-11, initial_potential=previous
    )
    # A known smooth perturbation is superposed on a general rational fixture.
    mode = np.broadcast_to(np.cos(np.pi * (np.arange(nx) + 0.5) / nx), grid.shape).reshape(-1)
    eigenvalue = 4 * np.sin(np.pi / (2 * nx)) ** 2 / 2.0**2
    delta = 0.125 * mode
    changed_rhs = rhs - eigenvalue * delta
    warm = iterative.solve(
        changed_rhs, grid, max_iterations=800, rtol=2e-11, initial_potential=previous
    )
    changed_cold = iterative.solve(changed_rhs, grid, max_iterations=800, rtol=2e-11)
    # Spectral inverse bound for a connected rectangle: ||error||inf <=
    # sqrt(N)*||residual||inf/lambda_min, plus the independently bounded
    # binary64 construction roundoff of the small perturbation.
    lambda_min = min(eigenvalue, 4 * np.sin(np.pi / (2 * ny)) ** 2 / 0.5**2)
    forcing_roundoff = 8 * np.finfo(float).eps * max(abs(changed_rhs))
    bound = np.sqrt(n) * (warm.tolerance + forcing_roundoff) / lambda_min
    save(
        "warm-general",
        grid,
        warm,
        rhs=changed_rhs,
        original_rhs=rhs,
        initial=previous,
        expected=exact + delta,
        cold_potential=changed_cold.potential,
        cold_residual=changed_cold.residual,
        first_iterations=np.asarray(cold.iterations),
        repeated_iterations=np.asarray(repeated.iterations),
        repeated_residual=repeated.residual,
        changed_cold_iterations=np.asarray(changed_cold.iterations),
        spectral_error_bound=float(bound),
        minimum_eigenvalue=float(lambda_min),
        scope="768-cell deterministic forcing sequence; no general performance claim",
    )
    assert cold.converged and repeated.converged and warm.converged and changed_cold.converged
    assert repeated.iterations == 0
    assert warm.iterations < changed_cold.iterations  # This declared sequence only.
    assert previous.tobytes() == before
    assert np.max(abs(warm.potential - (exact + delta))) <= bound
    assert np.max(abs(changed_cold.potential - (exact + delta))) <= bound
    assert np.max(abs(warm.potential - changed_cold.potential)) <= 2 * bound


@pytest.mark.parametrize("kind", ["float32", "integer", "scalar", "last_axis", "broadcast"])
def test_warm_invalid_guess_contract_refuses(kind):
    grid = field.bind_metric(spec())
    rhs = np.array([[1.0, -1.0, 2.0, -2.0]] * 2)
    initial = np.zeros_like(rhs)
    if kind == "float32":
        initial = initial.astype(np.float32)
    elif kind == "integer":
        initial = initial.astype(np.int64)
    elif kind == "scalar":
        initial = np.asarray(0.0)
    elif kind == "last_axis":
        initial = np.zeros((2, 5))
    else:
        initial = np.zeros(4)
    with pytest.raises(ValueError) as caught:
        iterative.solve(rhs, grid, max_iterations=12, rtol=2e-12, initial_potential=initial)
    save("warm-invalid-" + kind, error=str(caught.value))


def test_warm_noncontiguous_readonly_input_is_never_mutated():
    grid = field.bind_metric(spec())
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    storage = np.arange(8, dtype=np.float64)
    initial = storage[6::-2]
    initial.setflags(write=False)
    before = storage.tobytes()
    result = iterative.solve(rhs, grid, max_iterations=12, rtol=2e-12, initial_potential=initial)
    save("warm-strided", grid, result, rhs=rhs, initial=initial)
    assert result.converged and storage.tobytes() == before and not initial.flags.writeable
