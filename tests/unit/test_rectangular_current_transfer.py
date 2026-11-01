"""Exact current/power pairing and refusal checks for declared site transfers."""

from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest

from cells.processes import rectangular_current_transfer as transfer
from cells.processes import rectangular_environment as field
from cells.processes import rectangular_environment_conduction as conduction
from tests.unit.test_rectangular_environment import exact_four, spec
from tests.unit.test_rectangular_environment_conduction import save


def mapping(grid, targets):
    return transfer.bind(
        grid,
        source_ids=tuple(f"site:{i}" for i in range(len(targets))),
        target_environment_ids=tuple(grid.environment_ids[i] for i in targets),
    )


@pytest.mark.parametrize("dx,dy,depth", [(1.0, 1.0, 1.0), (2.0, 0.5, 0.25), (0.5, 1.25, 2.0)])
def test_duplicate_assignments_match_exact_conservation_and_adjoint_power(dx, dy, depth):
    grid = field.bind_metric(spec((2, 3), dx=dx, dy=dy))
    targets = (0, 0, 2, 3, 5, 5)
    link = mapping(grid, targets)
    currents = np.array([1.0, 0.5, -1.0, 2.0, -0.5, -2.0])
    voltage = np.array([-2.0, 8.0, 1.0, 3.0, -5.0, 4.0])
    expected = [Fraction(0)] * 6
    for i, value in zip(targets, currents, strict=True):
        expected[i] += Fraction(float(value))
    volume = Fraction(dx) * Fraction(dy) * Fraction(depth)
    source = [v / volume for v in expected]
    exact_power = sum(v * Fraction(float(phi)) for v, phi in zip(expected, voltage, strict=True))
    result = transfer.deposit(currents, link, grid, depth_m=depth, rtol=2e-12)
    readout = transfer.gather_potential(voltage, link, grid)
    save(
        f"transfer-exact-{dx}-{dy}-{depth}",
        result,
        gathered=readout,
        reference_cells=list(map(str, expected)),
        reference_source=list(map(str, source)),
        reference_power=str(exact_power),
    )
    assert result.usable and result.total_input_A == result.total_grid_A == 0
    np.testing.assert_array_equal(result.cell_current_A, list(map(float, expected)))
    np.testing.assert_allclose(result.source_A_m3, list(map(float, source)), rtol=2e-15, atol=0)
    np.testing.assert_array_equal(readout, voltage[list(targets)])
    assert float(np.dot(currents, readout)) == float(exact_power)
    assert np.dot(result.source_A_m3, voltage) * float(volume) == pytest.approx(
        float(exact_power), rel=2e-15
    )


def test_composition_solves_original_injected_current_and_keeps_unbalanced_refusal():
    grid = field.bind_metric(spec(dx=2.0, dy=0.5))
    link = mapping(grid, (0, 0, 1, 3, 2))
    currents = np.array([1.0, 2.0, -1.0, -2.0, 0.0])
    deposited = transfer.deposit(currents, link, grid, depth_m=0.25, rtol=2e-12)
    result = conduction.solve(
        deposited.source_A_m3,
        grid,
        conductivity_S_m=2.0,
        depth_m=0.25,
        max_iterations=16,
        rtol=2e-12,
    )
    expected = exact_four(Fraction(1, 4), Fraction(4), [-6, 2, 0, 4])
    readout = transfer.gather_potential(result.fields.potential_V, link, grid)
    save("transfer-composed-deposit", deposited)
    save(
        "transfer-composed-solve",
        result,
        site_voltage=readout,
        exact_potential=list(map(str, expected)),
    )
    assert deposited.usable and result.usable
    np.testing.assert_allclose(
        result.fields.potential_V, list(map(float, expected)), rtol=2e-13, atol=2e-14
    )
    assert np.dot(currents, readout) == pytest.approx(float(result.fields.dissipation_W), rel=2e-12)
    unbalanced = transfer.deposit(np.ones(5), link, grid, depth_m=0.25, rtol=2e-12)
    refused = conduction.solve(
        unbalanced.source_A_m3,
        grid,
        conductivity_S_m=2.0,
        depth_m=0.25,
        max_iterations=16,
        rtol=2e-12,
    )
    save("transfer-unbalanced-deposit", unbalanced)
    save("transfer-unbalanced-solve", refused)
    assert unbalanced.usable and unbalanced.total_grid_A == 5
    assert not refused.source_compatible and not refused.usable
    np.testing.assert_array_equal(refused.source_A_m3, unbalanced.source_A_m3)


def test_batch_axes_duplicates_and_gather_preserve_inputs():
    grid = field.bind_metric(spec())
    link = mapping(grid, (0, 3, 3))
    current = np.array(
        [[[1.0, -0.5, -0.5], [0.0, 0.0, 0.0]], [[1.0, 2.0, 3.0], [np.nan, 0.0, 0.0]]]
    )
    raw = current.tobytes()
    potential = np.arange(16, dtype=np.float64).reshape(2, 2, 4)
    with np.errstate(all="ignore"):
        deposited = transfer.deposit(current, link, grid, depth_m=2.0, rtol=2e-12)
    gathered = transfer.gather_potential(potential, link, grid)
    save("transfer-batched", deposited, gathered=gathered)
    np.testing.assert_array_equal(deposited.usable, [[True, True], [True, False]])
    np.testing.assert_array_equal(gathered, potential[..., [0, 3, 3]])
    assert current.tobytes() == raw
    assert deposited.source_A_m3.shape == (2, 2, 4)


def test_site_permutation_keeps_declared_assignments_and_power():
    grid = field.bind_metric(spec())
    targets = (0, 0, 3, 2, 3)
    current = np.array([1.0, 2.0, -1.0, -4.0, 2.0])
    order = (4, 2, 0, 3, 1)
    link = mapping(grid, targets)
    reordered = transfer.bind(
        grid,
        source_ids=tuple(link.source_ids[i] for i in order),
        target_environment_ids=tuple(grid.environment_ids[targets[i]] for i in order),
    )
    a = transfer.deposit(current, link, grid, depth_m=1.0, rtol=2e-12)
    b = transfer.deposit(current[list(order)], reordered, grid, depth_m=1.0, rtol=2e-12)
    save("transfer-order-original", a)
    save("transfer-order-permuted", b)
    assert a.usable and b.usable and link.identity != reordered.identity
    np.testing.assert_array_equal(a.cell_current_A, b.cell_current_A)


def test_finite_conversion_does_not_override_strict_aggregate_conservation():
    grid = field.bind_metric(spec(dy=1.0))
    link = mapping(grid, (0, 1, 0))
    currents = np.array([1e16, 1.0, -1e16])
    result = transfer.deposit(currents, link, grid, depth_m=1.0, rtol=0.0, atol_A=0.0)
    exact_total = sum(map(Fraction, currents.tolist()))
    save("transfer-reduction-disagreement", result, exact_total=str(exact_total))
    # The original reduction loses the unit term; scattering cancels the two
    # large values first. A strict requested budget must expose that difference.
    assert exact_total == result.total_grid_A == 1 and result.total_input_A == 0
    assert result.finite_result and result.conversion_ok
    assert result.conservation_error_A == 1 and not result.conservation_ok and not result.usable
    np.testing.assert_array_equal(result.site_current_A, currents)


@pytest.mark.parametrize(
    "ids,targets",
    [
        ((), ()),
        (("a", "a"), ("cell:0", "cell:1")),
        (("",), ("cell:0",)),
        (("a",), ("absent",)),
        (("a",), ("cell:0", "cell:1")),
        (["a"], ("cell:0",)),
    ],
)
def test_invalid_declared_assignments_refuse(ids, targets):
    grid = field.bind_metric(spec())
    with pytest.raises(ValueError):
        transfer.bind(grid, source_ids=ids, target_environment_ids=targets)


@pytest.mark.parametrize("kind", ["grid", "retarget", "boolean_index", "source_order"])
def test_different_grid_or_changed_mapping_refuses(kind):
    grid = field.bind_metric(spec())
    link = mapping(grid, (0, 3))
    if kind == "grid":
        grid = field.bind_metric(spec(dx=2.0))
    elif kind == "retarget":
        link = replace(link, target_indices=(1, 3))
    elif kind == "boolean_index":
        link = replace(link, target_indices=(False, 3))
    else:
        link = replace(link, source_ids=tuple(reversed(link.source_ids)))
    with pytest.raises(ValueError, match="Current map"):
        transfer.deposit(np.ones(2), link, grid, depth_m=1.0, rtol=2e-12)
    with pytest.raises(ValueError, match="Current map"):
        transfer.gather_potential(np.ones(4), link, grid)


@pytest.mark.parametrize("kind", ["subnormal", "overflow", "division_underflow", "nonfinite"])
def test_failed_conversion_retains_original_currents_and_raw_outputs(kind):
    grid = field.bind_metric(spec(dy=1.0))
    link = mapping(grid, (0, 1))
    depth = 1.0
    values = np.array([1.0, -1.0])
    if kind == "subnormal":
        values *= 1e-320
    elif kind == "overflow":
        values *= 1e300
        depth = 1e-300
    elif kind == "division_underflow":
        values *= 1e-300
        depth = 1e300
    else:
        values[0] = np.nan
    with np.errstate(all="ignore"):
        result = transfer.deposit(values, link, grid, depth_m=depth, rtol=2e-12)
    save("transfer-refusal-" + kind, result)
    assert not result.conversion_ok and not result.usable
    np.testing.assert_array_equal(result.site_current_A.view(np.uint64), values.view(np.uint64))


@pytest.mark.parametrize("name", ["rtol", "atol_A"])
@pytest.mark.parametrize("bad", [-1.0, float("inf"), float("nan"), True])
def test_explicit_conservation_policy_refuses_invalid_values(name, bad):
    grid = field.bind_metric(spec())
    link = mapping(grid, (0,))
    kw = dict(rtol=2e-12, atol_A=0.0)
    kw[name] = bad
    with pytest.raises(ValueError, match="current tolerances"):
        transfer.deposit(np.ones(1), link, grid, depth_m=1.0, **kw)


@pytest.mark.parametrize("value", [np.zeros(2, dtype=np.float32), np.zeros(3), np.array(0.0)])
def test_declared_axis_and_binary64_are_required(value):
    grid = field.bind_metric(spec())
    link = mapping(grid, (0, 1))
    with pytest.raises(ValueError, match="binary64 site currents"):
        transfer.deposit(value, link, grid, depth_m=1.0, rtol=2e-12)


def test_transfer_uses_no_dense_operator_or_solver(monkeypatch):
    def forbidden(*args, **kw):
        pytest.fail("No dense construction or solve is part of current transfer")

    for name in ("pinv", "inv", "solve", "lstsq"):
        monkeypatch.setattr(np.linalg, name, forbidden)
    monkeypatch.setattr(field, "bind", forbidden)
    grid = field.bind_metric(spec((4, 6)))
    link = mapping(grid, (0, 0, 23))
    result = transfer.deposit(np.array([1.0, 2.0, -3.0]), link, grid, depth_m=0.5, rtol=2e-12)
    save("transfer-linear-storage", result)
    assert result.usable
