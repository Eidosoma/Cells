"""Compiled CPU coupling; numerical fixture evidence only."""

import numpy as np
import pytest

from cells.processes import rectangular_current_coupling as coupling
from cells.processes import rectangular_environment as field
from tests.unit.test_rectangular_current_coupling import policy
from tests.unit.test_rectangular_current_transfer import mapping
from tests.unit.test_rectangular_environment import spec
from tests.unit.test_rectangular_environment_conduction import save
from tests.unit.test_rectangular_environment_conduction_jax import host, runtime  # noqa: F401


def test_compiled_composition_matches_numpy_and_retains_mixed_row_gates():
    grid = field.bind_metric(spec(dx=2.0, dy=0.5))
    link = mapping(grid, (0, 0, 1, 3, 2))
    values = np.array([[1, 2, -1, -2, 0], [1, 1, 1, 1, 1], [0, 0, 0, 0, 0]], dtype=np.float64)
    solver = coupling.compile_jax_solver(link, grid, **policy())
    lowered = solver.lower(values)
    ir = str(lowered.compiler_ir(dialect="stablehlo"))
    assert "stablehlo.scatter" in ir and "stablehlo.while" in ir and "callback" not in ir
    actual = host(lowered.compile()(values))
    expected = coupling.solve(values, link, grid, **policy())
    save("coupled-jax-batch", actual, stablehlo=ir)
    save("coupled-jax-numpy", expected)
    np.testing.assert_array_equal(actual.usable, [True, False, True])
    np.testing.assert_array_equal(actual.usable, expected.usable)
    np.testing.assert_allclose(
        actual.site_potential_V, expected.site_potential_V, rtol=2e-12, atol=2e-14
    )
    np.testing.assert_allclose(actual.site_power_W, expected.site_power_W, rtol=2e-12, atol=2e-14)
    np.testing.assert_array_equal(actual.deposition.site_current_A, values)


def test_compiled_warm_reuse_keeps_current_and_no_retry_on_bad_guess():
    grid = field.bind_metric(spec())
    link = mapping(grid, (0, 3))
    values = np.array([1.0, -1.0])
    solver = coupling.compile_jax_solver(link, grid, **policy())
    cold = host(solver(values))
    warm = host(solver(values, cold.field.fields.potential_V))
    bad = host(solver(values, np.full(4, np.nan)))
    save("coupled-jax-cold", cold)
    save("coupled-jax-warm", warm)
    save("coupled-jax-invalid-warm", bad)
    assert cold.usable and warm.usable and warm.field.linear_solve.iterations == 0
    assert not bad.usable and bad.field.linear_solve.iterations == 0
    np.testing.assert_array_equal(warm.deposition.site_current_A, values)


@pytest.mark.parametrize("kind", ["subnormal", "lost_conversion"])
def test_compiled_conversion_refusal_preserves_original_site_bits(kind):
    grid = field.bind_metric(spec(dy=1.0))
    link = mapping(grid, (0, 1))
    values = np.array([1e-320, -1e-320])
    options = policy()
    if kind == "lost_conversion":
        values = np.array([1e-300, -1e-300])
        options["depth_m"] = 1e300
    actual = host(coupling.compile_jax_solver(link, grid, **options)(values))
    save("coupled-jax-refused-" + kind, actual)
    assert not actual.deposition.conversion_ok and not actual.usable
    np.testing.assert_array_equal(
        actual.deposition.site_current_A.view(np.uint64), values.view(np.uint64)
    )
