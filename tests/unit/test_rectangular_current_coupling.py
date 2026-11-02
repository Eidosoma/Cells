"""Independent small-network checks of complete current-to-voltage coupling."""

import hashlib
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import rectangular_current_coupling as coupling
from cells.processes import rectangular_environment as field
from tests.unit.test_rectangular_current_transfer import mapping
from tests.unit.test_rectangular_environment import exact_four, spec
from tests.unit.test_rectangular_environment_conduction import save
from validation.betse import betse_normal_channel_join_runtime as runtime_inventory


def policy():
    return dict(
        conductivity_S_m=2.0,
        depth_m=0.25,
        max_iterations=32,
        field_rtol=2e-12,
        transfer_rtol=2e-12,
    )


def test_evidence_inventory_hashes_full_files_without_read_bytes(tmp_path, monkeypatch):
    payload = bytes(range(256)) * 8192
    library = tmp_path / "library.bin"
    executable = tmp_path / "interpreter.bin"
    library.write_bytes(payload)
    executable.write_bytes(b"declared interpreter bytes")
    monkeypatch.setattr(
        runtime_inventory,
        "sys",
        SimpleNamespace(
            modules={
                "compiled": SimpleNamespace(__file__=str(library)),
                "alias": SimpleNamespace(__file__=str(library)),
                "builtin": SimpleNamespace(),
                "missing": SimpleNamespace(__file__=str(tmp_path / "absent")),
            },
            executable=str(executable),
        ),
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Runtime evidence hashing must stream, never read a whole file")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    observed = runtime_inventory.inventory()
    assert observed["loaded_files"]["compiled"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert observed["loaded_files"]["alias"] == observed["loaded_files"]["compiled"]
    assert (
        observed["executable"]["sha256"]
        == hashlib.sha256(b"declared interpreter bytes").hexdigest()
    )
    assert observed["modules_without_files"] == ["builtin"]
    assert observed["loaded_files"]["missing"]["unavailable"] is True


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (0.5, 1.25)])
def test_complete_coupling_matches_exact_network_potential_and_power(dx, dy):
    grid = field.bind_metric(spec(dx=dx, dy=dy))
    targets = (0, 0, 1, 3, 2)
    link = mapping(grid, targets)
    current = np.array([1.0, 2.0, -1.0, -2.0, 0.0])
    volume = Fraction(dx) * Fraction(dy) * Fraction(1, 4)
    rhs = [-Fraction(i) / (2 * volume) for i in (3, -1, 0, -2)]
    exact = exact_four(1 / Fraction(dx) ** 2, 1 / Fraction(dy) ** 2, rhs)
    expected_sites = [exact[i] for i in targets]
    exact_power = sum(Fraction(float(i)) * v for i, v in zip(current, expected_sites, strict=True))
    result = coupling.solve(current, link, grid, **policy())
    save(
        f"coupled-exact-{dx}-{dy}",
        result,
        exact_potential=list(map(str, exact)),
        exact_power=str(exact_power),
    )
    assert result.usable
    np.testing.assert_allclose(
        result.site_potential_V, list(map(float, expected_sites)), rtol=2e-12
    )
    np.testing.assert_allclose(result.field.fields.potential_V, list(map(float, exact)), rtol=2e-12)
    assert result.site_power_W == pytest.approx(float(exact_power), rel=2e-12)
    assert result.deposited_power_W == pytest.approx(float(exact_power), rel=2e-12)
    assert result.field.fields.dissipation_W == pytest.approx(float(exact_power), rel=2e-12)
    assert abs(result.transfer_power_defect_W) <= 2e-14 * float(exact_power)
    np.testing.assert_array_equal(result.deposition.site_current_A, current)
    np.testing.assert_array_equal(result.field.source_A_m3, result.deposition.source_A_m3)


def test_deposition_refusal_survives_a_successful_balanced_field_solve():
    grid = field.bind_metric(spec(dy=1.0))
    link = mapping(grid, (0, 1, 0, 2))
    values = np.array([1e16, 1.0, -1e16, -1.0])
    options = policy()
    options.update(depth_m=1.0, transfer_rtol=0.0)
    result = coupling.solve(values, link, grid, **options)
    save("coupled-refused-transfer-valid-field", result)
    # Independent exact sum is zero. Two floating reduction orders disagree;
    # this strict transfer budget must remain binding even though the scattered
    # current balances and the field solve converges.
    assert sum(map(Fraction, values.tolist())) == 0
    assert result.deposition.total_input_A == -1 and result.deposition.total_grid_A == 0
    assert result.deposition.finite_result and result.deposition.conversion_ok
    assert not result.deposition.conservation_ok
    assert result.field.usable and not result.usable


def test_successful_transfer_does_not_hide_unbalanced_field_refusal():
    grid = field.bind_metric(spec())
    link = mapping(grid, (0, 1, 2, 3))
    result = coupling.solve(np.ones(4), link, grid, **policy())
    save("coupled-valid-transfer-refused-field", result)
    assert result.deposition.usable and not result.field.source_compatible and not result.usable
    assert result.field.linear_solve.iterations == 0
    np.testing.assert_array_equal(result.field.source_A_m3, result.deposition.source_A_m3)


def test_mixed_batch_retains_each_original_source_and_independent_result():
    grid = field.bind_metric(spec())
    link = mapping(grid, (0, 0, 1, 3, 2))
    values = np.array(
        [[[1, 2, -1, -2, 0], [1, 1, 1, 1, 1]], [[np.nan, 0, 0, 0, 0], [0, 0, 0, 0, 0]]],
        dtype=np.float64,
    )
    before = values.tobytes()
    with np.errstate(all="ignore"):
        result = coupling.solve(values, link, grid, **policy())
    save("coupled-mixed-batch", result)
    np.testing.assert_array_equal(result.usable, [[True, False], [False, True]])
    np.testing.assert_array_equal(
        result.deposition.site_current_A.view(np.uint64), values.view(np.uint64)
    )
    assert result.site_potential_V.shape == values.shape and before == values.tobytes()


def test_failed_iteration_budget_and_warm_guess_do_not_retry():
    grid = field.bind_metric(spec())
    link = mapping(grid, (0, 3))
    values = np.array([1.0, -1.0])
    options = policy()
    options["max_iterations"] = 0
    limited = coupling.solve(values, link, grid, **options)
    save("coupled-zero-iteration-budget", limited)
    assert limited.deposition.usable and not limited.usable
    assert limited.field.linear_solve.iterations == 0
    guess = np.array([np.nan, 0.0, 0.0, 0.0])
    before = guess.tobytes()
    with np.errstate(all="ignore"):
        invalid = coupling.solve(values, link, grid, initial_potential_V=guess, **policy())
    save("coupled-invalid-warm", invalid)
    assert invalid.deposition.usable and not invalid.usable
    assert invalid.field.linear_solve.iterations == 0 and guess.tobytes() == before


def test_warm_reuse_and_voltage_reference_preserve_site_differences():
    grid = field.bind_metric(spec(dx=2.0, dy=0.5))
    link = mapping(grid, (0, 1, 2, 3))
    values = np.array([1.0, -1.0, 2.0, -2.0])
    cold = coupling.solve(values, link, grid, **policy())
    warm = coupling.solve(
        values, link, grid, initial_potential_V=cold.field.fields.potential_V + 8.0, **policy()
    )
    save("coupled-cold", cold)
    save("coupled-warm-shifted", warm)
    assert cold.usable and warm.usable and warm.field.linear_solve.iterations == 0
    np.testing.assert_allclose(warm.site_potential_V, cold.site_potential_V, rtol=2e-12, atol=2e-14)
    assert warm.site_power_W == pytest.approx(float(cold.site_power_W), rel=2e-12)


@pytest.mark.parametrize("kind", ["subnormal", "lost_conversion"])
def test_raw_failed_site_conversion_remains_refused(kind):
    grid = field.bind_metric(spec(dy=1.0))
    link = mapping(grid, (0, 1))
    values = np.array([1.0, -1.0])
    options = policy()
    if kind == "subnormal":
        values *= 1e-320
    else:
        values *= 1e-300
        options["depth_m"] = 1e300
    with np.errstate(all="ignore"):
        result = coupling.solve(values, link, grid, **options)
    save("coupled-raw-refusal-" + kind, result)
    assert not result.deposition.conversion_ok and not result.usable
    np.testing.assert_array_equal(
        result.deposition.site_current_A.view(np.uint64), values.view(np.uint64)
    )


def test_composition_does_not_construct_a_dense_operator(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No dense matrix/inverse may be introduced by coupling")

    for name in ("pinv", "inv", "solve", "lstsq"):
        monkeypatch.setattr(np.linalg, name, forbidden)
    grid = field.bind_metric(spec((3, 4)))
    link = mapping(grid, (0, 0, 11))
    result = coupling.solve(np.array([1.0, 2.0, -3.0]), link, grid, **policy())
    save("coupled-matrix-free", result)
    assert result.usable
