"""Independent resistor-network/current checks for homogeneous rectangular slabs."""

from fractions import Fraction

import numpy as np
import pytest

from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_conduction as conduction
from tests.unit.test_rectangular_environment import exact_four, spec
from tests.unit.test_rectangular_environment import save as save_arrays


def save(name, result, **data):
    def flatten(prefix, value):
        if hasattr(value, "_asdict"):
            for key, part in value._asdict().items():
                flatten(prefix + "_" + key, part)
        else:
            data[prefix] = np.asarray(value)

    flatten("result", result)
    data["usable"] = np.asarray(result.usable)
    save_arrays("conduction-" + name, **data)


def resistor_reference(values, shape, dx, dy, sigma, depth):
    """Exact edge conductance/node balance; no production stencil or solver."""
    ny, nx = shape
    dx, dy, sigma, depth = map(Fraction, (dx, dy, sigma, depth))
    voltage = list(map(Fraction, values))
    currents = [Fraction(0)] * len(values)
    face_x = [[Fraction(0)] * (nx + 1) for _ in range(ny)]
    face_y = [[Fraction(0)] * nx for _ in range(ny + 1)]
    power = Fraction(0)
    for i in range(ny):
        for j in range(nx):
            src = i * nx + j
            for r, c, conductance, faces, a, b in (
                (i, j + 1, sigma * dy * depth / dx, face_x, i, j + 1),
                (i + 1, j, sigma * dx * depth / dy, face_y, i + 1, j),
            ):
                if r >= ny or c >= nx:
                    continue
                dst = r * nx + c
                drop = voltage[src] - voltage[dst]
                current = conductance * drop
                currents[src] += current
                currents[dst] -= current
                faces[a][b] = current
                power += current * drop
    return currents, [i / (dx * dy * depth) for i in currents], face_x, face_y, power


@pytest.mark.parametrize(
    "dx,dy,sigma,depth", [(1.0, 1.0, 2.0, 3.0), (2.0, 0.5, 0.25, 2.0), (0.5, 1.25, 1.5, 0.25)]
)
def test_readout_matches_exact_resistor_network_and_power(dx, dy, sigma, depth):
    grid = field.bind_metric(spec((2, 3), dx=dx, dy=dy))
    phi = np.array([-2, 1, 3, 4, -1, -5], dtype=np.float64)
    current, divergence, face_x, face_y, power = resistor_reference(
        phi.tolist(), grid.shape, dx, dy, sigma, depth
    )
    result = conduction.evaluate(phi, grid, conductivity_S_m=sigma, depth_m=depth)
    save(
        f"exact-{dx}-{dy}-{sigma}-{depth}",
        result,
        reference_divergence=np.array(list(map(float, divergence))),
        reference_power=str(power),
        reference_currents=list(map(str, current)),
    )
    assert result.usable and sum(current) == 0
    np.testing.assert_allclose(
        result.divergence_A_m3, list(map(float, divergence)), rtol=2e-15, atol=1e-15
    )
    np.testing.assert_allclose(
        result.face_current_A.x, np.array(face_x, dtype=float), rtol=2e-15, atol=1e-15
    )
    np.testing.assert_allclose(
        result.face_current_A.y, np.array(face_y, dtype=float), rtol=2e-15, atol=1e-15
    )
    assert float(result.dissipation_W) == pytest.approx(float(power), rel=2e-15)
    assert result.boundary_current_A == 0 and abs(result.conservation_error_A) <= 1e-13


@pytest.mark.parametrize(
    "dx,dy,sigma,depth", [(1.0, 1.0, 2.0, 3.0), (2.0, 0.5, 0.25, 2.0), (0.5, 1.25, 1.5, 0.25)]
)
def test_solve_matches_independent_four_node_potential_and_continuity(dx, dy, sigma, depth):
    grid = field.bind_metric(spec(dx=dx, dy=dy))
    source = np.array([1.0, -1.0, 2.0, -2.0])
    exact = exact_four(
        1 / Fraction(dx) ** 2,
        1 / Fraction(dy) ** 2,
        [-Fraction(v) / Fraction(sigma) for v in source.tolist()],
    )
    result = conduction.solve(
        source, grid, conductivity_S_m=sigma, depth_m=depth, max_iterations=16, rtol=2e-12
    )
    save(f"solve-{dx}-{dy}-{sigma}-{depth}", result, reference_potential=list(map(str, exact)))
    assert result.converged and result.total_source_A == 0
    np.testing.assert_allclose(
        result.fields.potential_V, list(map(float, exact)), rtol=2e-13, atol=2e-14
    )
    np.testing.assert_allclose(result.fields.divergence_A_m3, source, rtol=2e-12, atol=1e-14)
    assert np.max(abs(result.continuity_residual_A_m3)) <= result.continuity_tolerance_A_m3
    assert abs(result.power_defect_W) <= 2e-12 * result.fields.dissipation_W


def test_depth_scales_currents_power_and_integrals_without_changing_voltage():
    grid = field.bind_metric(spec())
    source = np.array([1.0, -1.0, 2.0, -2.0])
    a = conduction.solve(
        source, grid, conductivity_S_m=2.0, depth_m=0.25, max_iterations=16, rtol=2e-12
    )
    b = conduction.solve(
        source, grid, conductivity_S_m=2.0, depth_m=1.0, max_iterations=16, rtol=2e-12
    )
    save("depth-small", a)
    save("depth-large", b)
    assert a.usable and b.usable
    np.testing.assert_array_equal(a.fields.potential_V, b.fields.potential_V)
    np.testing.assert_array_equal(a.fields.current_density_A_m2.x, b.fields.current_density_A_m2.x)
    np.testing.assert_array_equal(4 * a.fields.face_current_A.x, b.fields.face_current_A.x)
    assert 4 * a.source_power_W == b.source_power_W
    assert 4 * a.fields.dissipation_W == b.fields.dissipation_W


def test_readout_gauge_invariance_and_power_of_unbalanced_sources_is_visible():
    grid = field.bind_metric(spec(dy=1.0))
    phi = np.array([-0.5, 0.0, 0.0, 0.5])
    shifted = phi + 8.0
    a = conduction.evaluate(phi, grid, conductivity_S_m=2.0, depth_m=3.0)
    b = conduction.evaluate(shifted, grid, conductivity_S_m=2.0, depth_m=3.0)
    save("gauge-zero", a)
    save("gauge-shift", b)
    for key in conduction.Fields._fields[1:]:
        left, right = getattr(a, key), getattr(b, key)
        if hasattr(left, "_asdict"):
            for x, y in zip(left, right, strict=True):
                np.testing.assert_array_equal(x, y)
        else:
            np.testing.assert_array_equal(left, right)
    balanced, unbalanced = np.array([-2.0, 0.0, 0.0, 2.0]), np.ones(4)
    assert 3 * np.dot(phi, balanced) == 3 * np.dot(shifted, balanced)
    assert 3 * np.dot(shifted, unbalanced) - 3 * np.dot(phi, unbalanced) == 8 * 3 * np.sum(
        unbalanced
    )


def test_multiple_batch_axes_keep_good_and_refused_rows_independent():
    grid = field.bind_metric(spec(dy=1.0))
    source = np.array([[[1.0, -1.0, 2.0, -2.0], [0.0] * 4], [[1.0] * 4, [np.nan] * 4]])
    before = source.tobytes()
    with np.errstate(all="ignore"):
        result = conduction.solve(
            source, grid, conductivity_S_m=2.0, depth_m=1.0, max_iterations=16, rtol=2e-12
        )
    save("mixed-batch", result)
    np.testing.assert_array_equal(result.usable, [[True, True], [False, False]])
    assert result.fields.electric_V_m.x.shape == (2, 2, 2, 3)
    assert source.tobytes() == before
    np.testing.assert_array_equal(result.continuity_residual_A_m3[1, 0], -np.ones(4))
    assert np.isnan(result.continuity_residual_A_m3[1, 1]).all()


def test_warm_reuse_and_exhausted_iteration_budget_keep_all_gates():
    grid = field.bind_metric(spec())
    source = np.array([1.0, -1.0, 2.0, -2.0])
    cold = conduction.solve(
        source, grid, conductivity_S_m=1.0, depth_m=1.0, max_iterations=16, rtol=2e-12
    )
    before = cold.fields.potential_V.tobytes()
    warm = conduction.solve(
        source,
        grid,
        conductivity_S_m=1.0,
        depth_m=1.0,
        max_iterations=0,
        rtol=2e-12,
        initial_potential_V=cold.fields.potential_V,
    )
    stopped = conduction.solve(
        source, grid, conductivity_S_m=1.0, depth_m=1.0, max_iterations=0, rtol=2e-12
    )
    save("warm-cold", cold)
    save("warm-repeat", warm)
    save("zero-budget", stopped)
    assert cold.usable and warm.usable and warm.linear_solve.iterations == 0
    assert cold.fields.potential_V.tobytes() == before
    assert not stopped.usable and not stopped.continuity_ok
    np.testing.assert_array_equal(stopped.continuity_residual_A_m3, -source)


@pytest.mark.parametrize(
    "bad", [0.0, -1.0, float("inf"), float("nan"), True, np.float64(1.0), 2.0**-1030]
)
@pytest.mark.parametrize("name", ["conductivity_S_m", "depth_m"])
def test_material_parameters_require_explicit_positive_host_scalars(bad, name):
    grid = field.bind_metric(spec())
    kw = dict(conductivity_S_m=1.0, depth_m=1.0)
    kw[name] = bad
    with pytest.raises(ValueError, match="conductivity and slab depth"):
        conduction.evaluate(np.zeros(4), grid, **kw)


@pytest.mark.parametrize(
    "shape,dx,dy,depth",
    [
        ((2, 2), 1e150, 1e-150, 1e170),
        ((2, 2), 1e150, 1e-150, 1e-180),
        ((2, 2), 1e150, 1e-150, 1e-170),
        ((2, 2), 1.0, 1.0, 2.0**-1021),
    ],
)
def test_unrepresentable_slab_measures_refuse(shape, dx, dy, depth):
    grid = field.bind_metric(spec(shape, dx=dx, dy=dy))
    if dx == dy == 1.0:
        # Normal host depth, but the derived quarter-volume is subnormal.
        grid = field.bind_metric(spec(shape, dx=0.5, dy=0.5))
    with pytest.raises(ValueError, match="slab volume or face area"):
        conduction.evaluate(np.zeros(4), grid, conductivity_S_m=1.0, depth_m=depth)


def tiny_readout(kind):
    grid = field.bind_metric(spec(dy=1.0))
    phi, sigma, depth = np.array([-0.5, 0.0, 0.0, 0.5]), 1.0, 1.0
    if kind == "face_current":
        depth = conduction.MIN_NORMAL_BINARY64
    elif kind == "power_density":
        phi *= 1e-200
    elif kind == "scaled_power":
        phi *= 1e-150
        depth = 1e-100
    elif kind == "gradient":
        phi[:] = conduction.MIN_NORMAL_BINARY64
        phi[0] = np.nextafter(phi[0], np.inf)
    else:
        raise AssertionError("Unknown synthetic range case")
    return grid, phi, sigma, depth


@pytest.mark.parametrize("kind", ["face_current", "power_density", "scaled_power", "gradient"])
def test_lost_or_subnormal_readout_arithmetic_remains_unusable(kind):
    grid, phi, sigma, depth = tiny_readout(kind)
    with np.errstate(all="ignore"):
        result = conduction.evaluate(phi, grid, conductivity_S_m=sigma, depth_m=depth)
    save("range-" + kind, result, input_potential=phi)
    assert result.finite_result and not result.arithmetic_representable and not result.usable
    np.testing.assert_array_equal(result.potential_V.view(np.uint64), phi.view(np.uint64))


def test_source_underflow_cannot_be_readmitted_by_inner_or_absolute_tolerance():
    grid = field.bind_metric(spec())
    source = np.array([1e-320, -1e-320, 0.0, 0.0])
    result = conduction.solve(
        source,
        grid,
        conductivity_S_m=1e300,
        depth_m=1.0,
        max_iterations=4,
        rtol=2e-12,
        atol_A_m3=1.0,
    )
    save("source-underflow", result)
    assert result.linear_solve.converged and result.continuity_ok and result.source_compatible
    assert not result.conversion_ok and not result.usable
    assert source[0] != 0 and result.poisson_rhs_V_m2[0] == 0


def test_representable_subnormal_forcing_remains_outside_portable_boundary():
    grid = field.bind_metric(spec())
    source = np.array([1e-320, -1e-320, 0.0, 0.0])
    with np.errstate(all="ignore"):
        result = conduction.solve(
            source,
            grid,
            conductivity_S_m=1.0,
            depth_m=1.0,
            max_iterations=4,
            rtol=2e-12,
            atol_A_m3=1.0,
        )
    save("source-subnormal", result)
    assert not result.conversion_ok and not result.usable
    np.testing.assert_array_equal(result.source_A_m3.view(np.uint64), source.view(np.uint64))


def test_source_overflow_keeps_raw_conversion_and_failed_flags():
    grid = field.bind_metric(spec())
    source = np.array([1e300, -1e300, 0.0, 0.0])
    with np.errstate(all="ignore"):
        result = conduction.solve(
            source, grid, conductivity_S_m=1e-300, depth_m=1.0, max_iterations=4, rtol=2e-12
        )
    save("source-overflow", result)
    assert not result.conversion_ok and not result.usable
    assert np.isneginf(result.poisson_rhs_V_m2[0]) and np.isposinf(result.poisson_rhs_V_m2[1])
    np.testing.assert_array_equal(result.source_A_m3, source)


@pytest.mark.parametrize("sigma,atol", [(1e300, 5e-324), (1e-300, 1e300)])
def test_absolute_tolerance_conversion_refuses_unrepresentable_values(sigma, atol):
    grid = field.bind_metric(spec())
    with pytest.raises(ValueError, match="tolerance conversion"):
        conduction.solve(
            np.zeros(4),
            grid,
            conductivity_S_m=sigma,
            depth_m=1.0,
            max_iterations=4,
            rtol=2e-12,
            atol_A_m3=atol,
        )


def test_current_residual_is_checked_against_original_source(monkeypatch):
    grid = field.bind_metric(spec(dy=1.0))
    source = np.array([1.0, -1.0, 2.0, -2.0])
    solve = conduction.iterative.solve

    def wrong(*args, **kw):
        good = solve(*args, **kw)
        return good._replace(potential=good.potential * 2)

    monkeypatch.setattr(conduction.iterative, "solve", wrong)
    result = conduction.solve(
        source, grid, conductivity_S_m=2.0, depth_m=1.0, max_iterations=16, rtol=2e-12
    )
    save("false-inner-success", result)
    assert result.linear_solve.converged and result.source_compatible
    assert not result.continuity_ok and not result.usable
    np.testing.assert_allclose(result.continuity_residual_A_m3, source, atol=2e-14)


def test_nonfinite_warm_guess_and_readout_are_retained():
    grid = field.bind_metric(spec())
    initial = np.array([np.nan, 0.0, 0.0, 0.0])
    with np.errstate(all="ignore"):
        result = conduction.solve(
            np.zeros(4),
            grid,
            conductivity_S_m=1.0,
            depth_m=1.0,
            max_iterations=4,
            rtol=2e-12,
            initial_potential_V=initial,
        )
        values = conduction.evaluate(initial, grid, conductivity_S_m=1.0, depth_m=1.0)
    save("nonfinite-warm", result)
    save("nonfinite-readout", values)
    assert not result.usable and not values.usable
    assert np.isnan(values.potential_V[0])


def test_nonfinite_joule_arithmetic_is_visible():
    grid = field.bind_metric(spec())
    with np.errstate(all="ignore"):
        result = conduction.evaluate(
            np.array([1e200, -1e200, 0.0, 0.0]), grid, conductivity_S_m=1.0, depth_m=1.0
        )
    save("power-overflow", result)
    assert np.isinf(result.dissipation_W) and not result.usable


def test_current_wrapper_never_uses_a_dense_solver(monkeypatch):
    def forbid(*args, **kw):
        pytest.fail("No dense solver or binding belongs in this path")

    for name in ("solve", "inv", "pinv", "lstsq"):
        monkeypatch.setattr(np.linalg, name, forbid)
    monkeypatch.setattr(field, "bind", forbid)
    grid = field.bind_metric(spec((4, 6), dx=0.5, dy=1.0))
    source = np.arange(24, dtype=np.float64) - 11.5
    result = conduction.solve(
        source, grid, conductivity_S_m=0.5, depth_m=0.25, max_iterations=96, rtol=2e-12
    )
    save("matrix-free", result)
    assert result.usable


@pytest.mark.parametrize("source", [np.zeros(4, dtype=np.float32), np.zeros(3), np.array(0.0)])
def test_input_shape_and_precision_are_explicit(source):
    grid = field.bind_metric(spec())
    with pytest.raises(ValueError, match="binary64"):
        conduction.solve(
            source, grid, conductivity_S_m=1.0, depth_m=1.0, max_iterations=4, rtol=2e-12
        )
