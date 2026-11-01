"""Actual compiled CPU conduction checks; no GPU or biological qualification."""

import os

import jax
import jaxlib
import numpy as np
import pytest

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_conduction as conduction
from tests.unit.test_rectangular_environment import spec
from tests.unit.test_rectangular_environment_conduction import save, tiny_readout


@pytest.fixture(scope="module", autouse=True)
def runtime():
    assert os.environ["JAX_PLATFORMS"] == "cpu" and jax.default_backend() == "cpu"
    assert jax.config.x64_enabled and not jax.config.jax_disable_jit
    assert all(d.platform == "cpu" for d in jax.devices())
    from tests.unit.test_rectangular_environment import save as save_arrays

    save_arrays(
        "conduction-jax-runtime",
        jax=jax.__version__,
        jaxlib=jaxlib.__version__,
        x64=True,
        disable_jit=False,
        devices=[str(d) for d in jax.devices()],
        requested_jit_setting=os.environ.get("JAX_DISABLE_JIT"),
    )


def host(result):
    ready = jax.block_until_ready(result)
    leaves = jax.tree_util.tree_leaves(ready)
    assert all(a.device.platform == "cpu" for a in leaves)
    return jax.tree_util.tree_map(np.asarray, ready)


@pytest.mark.parametrize("sigma,depth", [(1.0, 1.0), (0.25, 2.0), (2.0, 0.25)])
def test_compiled_currents_match_numpy_and_original_continuity(sigma, depth):
    grid = field.bind_metric(spec((4, 6), dx=0.5, dy=1.25))
    source = np.stack([np.arange(24, dtype=np.float64) - 11.5, np.ones(24), np.zeros(24)])
    before = source.tobytes()
    expected = conduction.solve(
        source, grid, conductivity_S_m=sigma, depth_m=depth, max_iterations=96, rtol=2e-12
    )
    solver = conduction.compile_jax_solver(
        grid, conductivity_S_m=sigma, depth_m=depth, max_iterations=96, rtol=2e-12
    )
    lowered = solver.lower(source)
    ir = str(lowered.compiler_ir(dialect="stablehlo"))
    assert "stablehlo.while" in ir and "callback" not in ir
    actual = host(lowered.compile()(source))
    save(f"jax-{sigma}-{depth}", actual, stablehlo=ir)
    save(f"jax-numpy-{sigma}-{depth}", expected)
    np.testing.assert_array_equal(actual.usable, [True, False, True])
    np.testing.assert_array_equal(actual.usable, expected.usable)
    np.testing.assert_allclose(
        actual.fields.potential_V, expected.fields.potential_V, rtol=2e-12, atol=2e-12
    )
    np.testing.assert_allclose(
        actual.fields.face_current_A.x, expected.fields.face_current_A.x, rtol=2e-11, atol=2e-11
    )
    assert actual.linear_solve.potential.dtype == actual.fields.face_current_A.x.dtype == np.float64
    assert source.tobytes() == before


def test_compiled_warm_reuse_keeps_original_source_and_current_tolerance():
    grid = field.bind_metric(spec())
    source = np.array([1.0, -1.0, 2.0, -2.0])
    solver = conduction.compile_jax_solver(
        grid, conductivity_S_m=2.0, depth_m=3.0, max_iterations=16, rtol=2e-12, atol_A_m3=1e-14
    )
    cold = host(solver(source))
    warm = host(solver(source, cold.fields.potential_V))
    save("jax-cold", cold)
    save("jax-warm", warm)
    assert cold.usable and warm.usable and warm.linear_solve.iterations == 0
    assert warm.continuity_tolerance_A_m3 == max(1e-14, 2e-12 * 2)
    np.testing.assert_array_equal(warm.source_A_m3, source)


@pytest.mark.parametrize("sigma", [1.0, 1e300])
def test_compiled_underflow_retains_failed_conversion_even_with_inner_success(sigma):
    grid = field.bind_metric(spec())
    source = np.array([1e-320, -1e-320, 0.0, 0.0])
    actual = host(
        conduction.compile_jax_solver(
            grid, conductivity_S_m=sigma, depth_m=1.0, max_iterations=4, rtol=2e-12, atol_A_m3=1.0
        )(source)
    )
    save(f"jax-underflow-{sigma}", actual)
    assert actual.linear_solve.converged
    assert not actual.conversion_ok and not actual.usable
    np.testing.assert_array_equal(actual.source_A_m3.view(np.uint64), source.view(np.uint64))


def test_compiled_factory_requires_x64_and_enabled_jit():
    grid = field.bind_metric(spec())
    original_x64, original_disabled = jax.config.x64_enabled, jax.config.jax_disable_jit
    try:
        jax.config.update("jax_enable_x64", False)
        with pytest.raises(ValueError, match="binary64"):
            conduction.compile_jax_solver(
                grid, conductivity_S_m=1.0, depth_m=1.0, max_iterations=4, rtol=2e-12
            )
        jax.config.update("jax_enable_x64", original_x64)
        jax.config.update("jax_disable_jit", True)
        with pytest.raises(ValueError, match="JIT"):
            conduction.compile_jax_solver(
                grid, conductivity_S_m=1.0, depth_m=1.0, max_iterations=4, rtol=2e-12
            )
    finally:
        jax.config.update("jax_enable_x64", original_x64)
        jax.config.update("jax_disable_jit", original_disabled)
    assert jax.config.x64_enabled == original_x64
    assert jax.config.jax_disable_jit == original_disabled


@pytest.mark.parametrize("kind", ["face_current", "power_density", "scaled_power", "gradient"])
def test_compiled_readout_refuses_lost_or_subnormal_arithmetic(kind):
    import jax.numpy as jnp

    grid, phi, sigma, depth = tiny_readout(kind)
    evaluate = jax.jit(
        lambda value: conduction.evaluate(
            value, grid, conductivity_S_m=sigma, depth_m=depth, xp=jnp
        )
    )
    actual = host(evaluate.lower(phi).compile()(phi))
    save("jax-range-" + kind, actual, input_potential=phi)
    assert actual.finite_result and not actual.arithmetic_representable and not actual.usable
    np.testing.assert_array_equal(actual.potential_V.view(np.uint64), phi.view(np.uint64))


@pytest.mark.parametrize("kind", ["conductivity", "depth", "volume"])
def test_compiled_factory_refuses_subnormal_medium_or_derived_measures(kind):
    sigma, depth = 1.0, 1.0
    grid = field.bind_metric(spec(dy=1.0))
    if kind == "conductivity":
        sigma = 2.0**-1030
    elif kind == "depth":
        depth = 2.0**-1030
    else:
        grid = field.bind_metric(spec(dx=0.5, dy=0.5))
        depth = 2.0**-1021
    with pytest.raises(ValueError, match="conductivity and slab depth|slab volume or face area"):
        conduction.compile_jax_solver(
            grid, conductivity_S_m=sigma, depth_m=depth, max_iterations=4, rtol=2e-12
        )
