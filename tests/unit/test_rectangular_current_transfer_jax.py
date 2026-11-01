"""Actual CPU-JIT scatter/transpose checks; no GPU or native-tissue credit."""

import os

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.processes import rectangular_current_transfer as transfer
from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_conduction as conduction
from tests.unit.test_rectangular_current_transfer import mapping
from tests.unit.test_rectangular_environment import spec
from tests.unit.test_rectangular_environment_conduction import save
from tests.unit.test_rectangular_environment_conduction_jax import host, runtime  # noqa: F401


def test_actual_compiled_scatter_transpose_and_mixed_batches():
    grid = field.bind_metric(spec((2, 3), dx=2.0, dy=0.5))
    link = mapping(grid, (0, 0, 2, 3, 5, 5))
    current = np.array([[1.0, 0.5, -1.0, 2.0, -0.5, -2.0], [1.0] * 6, [0.0] * 6])
    voltage = np.arange(18, dtype=np.float64).reshape(3, 6)

    @jax.jit
    def run(values, potential):
        return (
            transfer.deposit(values, link, grid, depth_m=0.25, rtol=2e-12, xp=jnp),
            transfer.gather_potential(potential, link, grid, xp=jnp),
        )

    lowered = run.lower(current, voltage)
    ir = str(lowered.compiler_ir(dialect="stablehlo"))
    assert "stablehlo.scatter" in ir and "callback" not in ir
    actual, gathered = host(lowered.compile()(current, voltage))
    expected = transfer.deposit(current, link, grid, depth_m=0.25, rtol=2e-12)
    save("transfer-jax", actual, gathered=gathered, stablehlo=ir)
    save("transfer-jax-numpy", expected)
    np.testing.assert_array_equal(actual.source_A_m3, expected.source_A_m3)
    np.testing.assert_array_equal(actual.usable, [True, True, True])
    np.testing.assert_array_equal(gathered, transfer.gather_potential(voltage, link, grid))
    np.testing.assert_array_equal(
        np.sum(current * gathered, axis=-1), np.sum(actual.cell_current_A * voltage, axis=-1)
    )


def test_compiled_transfer_then_conduction_keeps_current_and_power_pairing():
    grid = field.bind_metric(spec(dx=2.0, dy=0.5))
    link = mapping(grid, (0, 0, 1, 3, 2))
    current = np.array([1.0, 2.0, -1.0, -2.0, 0.0])
    solver = conduction.compile_jax_solver(
        grid, conductivity_S_m=2.0, depth_m=0.25, max_iterations=16, rtol=2e-12
    )

    @jax.jit
    def run(values):
        deposited = transfer.deposit(values, link, grid, depth_m=0.25, rtol=2e-12, xp=jnp)
        solution = solver(deposited.source_A_m3)
        return (
            deposited,
            solution,
            transfer.gather_potential(solution.fields.potential_V, link, grid, xp=jnp),
        )

    deposited, solution, gathered = host(run.lower(current).compile()(current))
    save("transfer-jax-composed", deposited, gathered=gathered)
    save("transfer-jax-field", solution)
    assert deposited.usable and solution.usable
    assert np.dot(current, gathered) == pytest.approx(
        float(solution.fields.dissipation_W), rel=2e-12
    )
    assert os.environ["JAX_PLATFORMS"] == "cpu"


@pytest.mark.parametrize("kind", ["source_subnormal", "conversion_flush", "nan_row"])
def test_compiled_transfer_retains_refused_rows(kind):
    grid = field.bind_metric(spec(dy=1.0))
    link = mapping(grid, (0, 1))
    values = np.array([[1.0, -1.0], [1.0, -1.0]])
    depth = 1.0
    if kind == "source_subnormal":
        values[1] *= 1e-320
    elif kind == "conversion_flush":
        values[1] *= 1e-300
        depth = 1e300
    else:
        values[1, 0] = np.nan
    run = jax.jit(lambda a: transfer.deposit(a, link, grid, depth_m=depth, rtol=2e-12, xp=jnp))
    result = host(run.lower(values).compile()(values))
    save("transfer-jax-refusal-" + kind, result)
    np.testing.assert_array_equal(result.usable, [True, False])
    np.testing.assert_array_equal(result.site_current_A.view(np.uint64), values.view(np.uint64))
