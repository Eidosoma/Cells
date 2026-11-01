"""Actual CPU JIT checks of the rectangular solve; no GPU/native qualification."""

import os
from fractions import Fraction

import jax
import jax.numpy as jnp
import jaxlib
import numpy as np
import pytest

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_iterative as iterative
from tests.unit.test_rectangular_environment import exact_four, spec
from tests.unit.test_rectangular_environment import save as save_arrays


@pytest.fixture(scope="module", autouse=True)
def cpu_runtime():
    assert os.environ.get("JAX_PLATFORMS") == "cpu"
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    assert not jax.config.jax_disable_jit
    assert all(d.platform == "cpu" for d in jax.devices())
    save_arrays(
        "jax-runtime",
        jax_version=jax.__version__,
        jaxlib_version=jaxlib.__version__,
        devices=[str(d) for d in jax.devices()],
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        x64=True,
        disable_jit=False,
        requested_disable_jit=os.environ.get("JAX_DISABLE_JIT"),
        scope="CPU compiled numerical fixtures; no GPU or original BETSE execution",
    )


def host(result):
    ready = jax.block_until_ready(result)
    assert all(v.device.platform == "cpu" for v in ready)
    converted = iterative.SolveResult(*(np.asarray(v) for v in ready))
    assert converted.potential.dtype == converted.residual.dtype == np.float64
    assert converted.iterations.dtype == converted.loop_iterations.dtype == np.int32
    return converted


def save(name, grid, actual, expected=None, **data):
    data.update(
        metric_identity=grid.identity,
        shape=grid.shape,
        spacing_xy_m=grid.spacing_xy_m,
        coordinates=grid.coordinates_m,
        x_vertices=grid.vertices_x_m,
        y_vertices=grid.vertices_y_m,
    )
    for prefix, result in (("jax", actual), ("numpy", expected)):
        if result is not None:
            data.update({prefix + "_" + k: np.asarray(v) for k, v in result._asdict().items()})
            data[prefix + "_converged"] = np.asarray(result.converged)
    save_arrays("jax-" + name, **data)


def compare_flags(actual, expected):
    for name in ("rhs_compatible", "residual_ok", "finite_result", "gauge_ok", "breakdown"):
        np.testing.assert_array_equal(getattr(actual, name), getattr(expected, name))
    np.testing.assert_array_equal(actual.converged, expected.converged)


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (1.0, 1.25)])
def test_compiled_small_system_matches_independent_fraction_reference(dx, dy):
    grid = field.bind_metric(spec(dx=dx, dy=dy))
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    exact = exact_four(1 / Fraction(dx) ** 2, 1 / Fraction(dy) ** 2, (1, -1, 2, -2))
    expected = iterative.solve(rhs, grid, max_iterations=12, rtol=2e-12)
    solver = iterative.compile_jax_solver(grid, max_iterations=12, rtol=2e-12)
    actual = host(solver(jax.device_put(rhs, jax.devices("cpu")[0])))
    save(f"rational-{dx}-{dy}", grid, actual, expected, rhs=rhs, exact=[str(v) for v in exact])
    assert actual.converged
    compare_flags(actual, expected)
    np.testing.assert_allclose(actual.potential, list(map(float, exact)), rtol=2e-13, atol=2e-14)
    assert actual.residual_inf <= actual.tolerance


def test_compiled_mixed_batch_preserves_refusal_and_active_counts():
    grid = field.bind_metric(spec(dx=2.0, dy=1.0))
    rhs = np.array(
        [
            [1.0, -1.0, 1.0, -1.0],
            [1.0, -1.0, 2.0, -2.0],
            [0.0] * 4,
            [1.0] * 4,
            [np.nan] * 4,
            [np.inf] * 4,
        ]
    )
    before = rhs.tobytes()
    with np.errstate(all="ignore"):
        expected = iterative.solve(rhs, grid, max_iterations=1, rtol=2e-12)
    solver = iterative.compile_jax_solver(grid, max_iterations=1, rtol=2e-12)
    actual = host(solver(jnp.asarray(rhs)))
    save("mixed", grid, actual, expected, rhs=rhs)
    compare_flags(actual, expected)
    np.testing.assert_array_equal(actual.converged, [True, False, True, False, False, False])
    np.testing.assert_array_equal(actual.iterations, [1, 1, 0, 0, 0, 0])
    assert actual.loop_iterations == 1 and rhs.tobytes() == before
    np.testing.assert_array_equal(actual.residual[3], -np.ones(4))
    assert np.isnan(actual.residual[4]).all() and np.isneginf(actual.residual[5]).all()


@pytest.mark.parametrize("budget", [0, 1])
def test_compiled_budget_reports_unconverged_raw_candidate(budget):
    grid = field.bind_metric(spec())
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    expected = iterative.solve(rhs, grid, max_iterations=budget, rtol=1e-13)
    actual = host(iterative.compile_jax_solver(grid, max_iterations=budget, rtol=1e-13)(rhs))
    save(f"budget-{budget}", grid, actual, expected, rhs=rhs)
    compare_flags(actual, expected)
    assert not actual.converged and actual.iterations == actual.loop_iterations == budget
    np.testing.assert_allclose(actual.potential, expected.potential, rtol=0, atol=2e-14)


def test_compiled_warm_guesses_retain_bad_input_gates():
    grid = field.bind_metric(spec(dy=1.0))
    rhs = np.array([[-2.0, 2.0, -2.0, 2.0]] * 4)
    initial = np.array(
        [[1.0, -1.0, 1.0, -1.0], [2.0, 0.0, -2.0, 0.0], [np.nan, 0, 0, 0], [np.inf, 0, 0, 0]]
    )
    before = initial.tobytes()
    with np.errstate(all="ignore"):
        expected = iterative.solve(
            rhs, grid, max_iterations=12, rtol=2e-12, initial_potential=initial
        )
    solver = iterative.compile_jax_solver(grid, max_iterations=12, rtol=2e-12)
    actual = host(solver(rhs, initial))
    save("warm-batch", grid, actual, expected, rhs=rhs, initial=initial)
    compare_flags(actual, expected)
    np.testing.assert_array_equal(actual.converged, [True, True, False, False])
    np.testing.assert_array_equal(actual.iterations[[0, 2, 3]], [0, 0, 0])
    assert initial.tobytes() == before
    np.testing.assert_allclose(actual.potential[:2], expected.potential[:2], rtol=0, atol=2e-13)


def test_compiled_general_forcing_and_warm_reuse_have_independent_accuracy():
    grid = field.bind_metric(spec((6, 8), dx=1.0, dy=0.5))
    ny, nx = grid.shape
    half = (np.arange(ny * nx // 2) * 5) % 11 - 5
    exact = np.concatenate((half, -half)).astype(np.float64)
    rhs_exact = []
    for i, value in enumerate(exact):
        row, col = divmod(i, nx)
        action = Fraction(0)
        for r, c, coefficient in (
            (row, col - 1, 1),
            (row, col + 1, 1),
            (row - 1, col, 4),
            (row + 1, col, 4),
        ):
            if 0 <= r < ny and 0 <= c < nx:
                action += coefficient * (Fraction(exact[r * nx + c]) - Fraction(value))
        rhs_exact.append(action)
    rhs = np.asarray(list(map(float, rhs_exact)))
    assert sum(rhs_exact) == 0
    solver = iterative.compile_jax_solver(grid, max_iterations=200, rtol=2e-11)
    expected = iterative.solve(rhs, grid, max_iterations=200, rtol=2e-11)
    actual = host(solver(rhs))
    warm = host(solver(rhs, actual.potential))
    save(
        "general",
        grid,
        actual,
        expected,
        rhs=rhs,
        exact=exact,
        rational_rhs=[str(v) for v in rhs_exact],
        warm_potential=warm.potential,
        warm_residual=warm.residual,
        warm_iterations=warm.iterations,
        warm_converged=np.asarray(warm.converged),
    )
    assert actual.converged and warm.converged and expected.converged
    assert warm.iterations == 0
    np.testing.assert_allclose(actual.potential, exact, rtol=0, atol=3e-9)
    np.testing.assert_allclose(warm.potential, exact, rtol=0, atol=3e-9)
    np.testing.assert_allclose(actual.potential, expected.potential, rtol=0, atol=3e-9)


def test_reused_compiled_callable_has_one_loop_without_python_step_callbacks(monkeypatch):
    grid = field.bind_metric(spec())
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    calls = []
    original = iterative.solve

    def observed(*args, **kwargs):
        calls.append("trace")
        return original(*args, **kwargs)

    monkeypatch.setattr(iterative, "solve", observed)
    solver = iterative.compile_jax_solver(grid, max_iterations=12, rtol=2e-12)
    lowered = solver.lower(jnp.asarray(rhs))
    text = lowered.as_text()
    executable = lowered.compile()
    actual = host(executable(rhs))
    second = host(executable(rhs * 0.5))
    save(
        "compiled-loop",
        grid,
        actual,
        rhs=rhs,
        second_potential=second.potential,
        compiler_ir=text,
        source_trace_calls=len(calls),
    )
    assert actual.converged and second.converged and calls == ["trace"]
    assert "stablehlo.while" in text
    assert "callback" not in text and "host_callback" not in text
    np.testing.assert_allclose(second.potential, actual.potential * 0.5, rtol=0, atol=2e-14)


def test_compiled_factory_requires_x64_and_does_not_change_precision_setting():
    grid = field.bind_metric(spec())
    before = jax.config.x64_enabled
    try:
        jax.config.update("jax_enable_x64", False)
        with pytest.raises(ValueError, match="binary64") as caught:
            iterative.compile_jax_solver(grid, max_iterations=12, rtol=2e-12)
        assert not jax.config.x64_enabled
        save_arrays("jax-x64-refusal", error=str(caught.value))
    finally:
        jax.config.update("jax_enable_x64", before)
    assert jax.config.x64_enabled == before


def test_compiled_factory_and_existing_callable_refuse_disabled_jit(monkeypatch):
    grid = field.bind_metric(spec())
    solver = iterative.compile_jax_solver(grid, max_iterations=12, rtol=2e-12)
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("unexpected solver entry")
        pytest.fail("Disabled JIT must refuse before any solver entry")

    monkeypatch.setattr(iterative, "solve", forbidden)
    before = jax.config.jax_disable_jit
    errors = []
    try:
        jax.config.update("jax_disable_jit", True)
        with pytest.raises(ValueError, match="JIT") as caught:
            iterative.compile_jax_solver(grid, max_iterations=12, rtol=2e-12)
        errors.append(str(caught.value))
        with pytest.raises(ValueError, match="JIT") as caught:
            solver(np.zeros(4))
        errors.append(str(caught.value))
        assert jax.config.jax_disable_jit and attempts == []
        save_arrays("jax-disabled-jit-refusal", errors=errors, attempted_solver_entries=attempts)
    finally:
        jax.config.update("jax_disable_jit", before)
    assert jax.config.jax_disable_jit == before


@pytest.mark.parametrize("case", ["float32", "shape", "warm_broadcast", "budget"])
def test_compiled_input_contracts_refuse_during_tracing(case):
    grid = field.bind_metric(spec())
    rhs, initial = np.zeros((2, 4)), None
    budget = 12
    if case == "float32":
        rhs = rhs.astype(np.float32)
    elif case == "shape":
        rhs = np.zeros((2, 5))
    elif case == "warm_broadcast":
        initial = np.zeros(4)
    else:
        budget = True
    solver = iterative.compile_jax_solver(grid, max_iterations=budget, rtol=2e-12)
    with pytest.raises(ValueError) as caught:
        solver(rhs, initial)
    save_arrays("jax-invalid-" + case, error=str(caught.value))
