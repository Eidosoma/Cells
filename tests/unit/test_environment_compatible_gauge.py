"""Small independent rational checks of the separate saved-grid convention."""

import os
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from validation.betse import betse_native_membrane_initialization_archive as archive
from validation.betse import environment_compatible_gauge as gauge


def evidence(name, value):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        archive.write(Path(root) / (name + ".json"), value)


def fixture(shape=(2, 2), delta=1.0):
    ny, nx = shape
    coords = np.array([[(j + 0.5) * delta, (i + 0.5) * delta] for i, j in np.ndindex(shape)])
    spec = gauge.geometry.GridSpec(
        tuple(f"cell:{i}" for i in range(ny * nx)),
        shape,
        (0.0, nx * delta, 0.0, ny * delta),
        delta,
        coords,
        dict.fromkeys(("N", "S", "E", "W"), "flux"),
        {"origin": "explicit small algebra fixture, not native geometry"},
    )
    if shape == (2, 2):
        matrix = [[-2, 1, 1, 0], [1, -2, 0, 1], [1, 0, -2, 1], [0, 1, 1, -2]]
    else:
        assert shape == (2, 3)
        matrix = [
            [-2, 1, 0, 1, 0, 0],
            [1, -3, 1, 0, 1, 0],
            [0, 1, -2, 0, 0, 1],
            [1, 0, 0, -2, 1, 0],
            [0, 1, 0, 1, -3, 1],
            [0, 0, 1, 0, 1, -2],
        ]
    operator = np.array(matrix, dtype=np.float64) / delta**2
    # Deliberately poor stand-in for a retained inverse: it must stay separate.
    native = np.eye(ny * nx, dtype=np.float64)
    return spec, dict(indices=list(np.ndindex(shape)), operator=operator, native_inverse=native)


def rational_solution(operator, rhs):
    # Independent constrained linear system: replace one redundant equation
    # with the zero-sum gauge, then exact Fraction Gauss-Jordan elimination.
    n = len(rhs)
    matrix = [
        [Fraction(int(x)) for x in row] + [Fraction(int(b))]
        for row, b in zip(operator, rhs, strict=True)
    ]
    matrix[-1] = [Fraction(1)] * n + [Fraction(0)]
    for j in range(n):
        p = next(i for i in range(j, n) if matrix[i][j])
        matrix[j], matrix[p] = matrix[p], matrix[j]
        scale = matrix[j][j]
        matrix[j] = [x / scale for x in matrix[j]]
        for i in range(n):
            if i != j:
                scale = matrix[i][j]
                matrix[i] = [x - scale * y for x, y in zip(matrix[i], matrix[j], strict=True)]
    return np.array([float(row[-1]) for row in matrix])


@pytest.mark.parametrize("shape", [(2, 2), (2, 3)])
def test_small_independent_rational_solution_and_both_operator_products(shape):
    spec, inputs = fixture(shape)
    rhs = np.zeros(np.prod(shape), dtype=np.float64)
    rhs[0], rhs[2] = 1.0, -1.0
    before = {k: v.tobytes() for k, v in inputs.items() if type(v) is np.ndarray}
    report = gauge.diagnose(spec, rhs=rhs, **inputs)
    expected = rational_solution(inputs["operator"], rhs)
    evidence(
        "rational-" + str(shape[1]),
        dict(spec=spec, inputs=inputs, rhs=rhs, report=report, expected=expected),
    )
    np.testing.assert_allclose(report["solutions"][0], expected, rtol=0, atol=2e-15)
    checks = report["compatible_algebra"]
    assert checks["operator_inverse_residual_inf"] < 2e-14
    assert checks["inverse_operator_residual_inf"] < 2e-14
    assert checks["constant_mode"]["inverse_row_sum_inf"] < 2e-15
    assert checks["constant_mode"]["inverse_column_sum_inf"] < 2e-15
    assert report["native_algebra"]["constant_mode"]["inverse_row_sum_inf"] == 1.0
    assert report["numerical_acceptance"] is False
    assert report["rhs_reports"][0]["status"] == "diagnosed"
    assert all(inputs[k].tobytes() == v for k, v in before.items())


def test_delegates_only_to_existing_compatible_solver_and_keeps_native_baseline(monkeypatch):
    spec, inputs = fixture(delta=1e-6)
    original_bind, original_solve = gauge.geometry.bind_grid, gauge.geometry.environment_poisson
    calls = []

    def bind(value):
        calls.append("bind")
        b = original_bind(value)
        return replace(b, kernel=b.kernel._replace(pseudoinverse=np.full((4, 4), np.nan)))

    def solve(value, binding, *, convention, xp):
        calls.append((convention, xp))
        return original_solve(value, binding, convention=convention, xp=xp)

    monkeypatch.setattr(gauge.geometry, "bind_grid", bind)
    monkeypatch.setattr(gauge.geometry, "environment_poisson", solve)
    rhs = np.array([[1.0, -1.0, 1.0, -1.0], [0.0] * 4])
    report = gauge.diagnose(spec, rhs=rhs, **inputs)
    evidence("existing-solver", dict(spec=spec, inputs=inputs, rhs=rhs, report=report))
    np.testing.assert_allclose(
        report["solutions"][0], np.array([-0.5, 0.5, -0.5, 0.5]) * 1e-12, rtol=1e-14, atol=0
    )
    assert np.array_equal(report["solutions"][1], np.zeros(4))
    assert calls == ["bind", ("compatible_gauge", np), ("compatible_gauge", np)]
    assert report["native_inverse"].tobytes() == inputs["native_inverse"].tobytes()
    assert report["legacy_bind_grid_pseudoinverse_used"] is False


def test_invalid_rhs_isolation_finite_reductions_and_no_implicit_centering(monkeypatch):
    spec, inputs = fixture()
    rhs = np.array(
        [
            [1.0, -1.0, 1.0, -1.0],
            [1.0, 0.0, 0.0, 0.0],
            [np.nan, 0.0, 0.0, 0.0],
            [1e308, 1e308, 1e308, 1e308],
            [1e308, -1e308, 1e308, -1e308],
        ]
    )
    old = gauge.geometry.environment_poisson
    calls = []

    def solve(values, *a, **k):
        calls.append(values.copy())
        return old(values, *a, **k)

    monkeypatch.setattr(gauge.geometry, "environment_poisson", solve)
    report = gauge.diagnose(spec, rhs=rhs, **inputs)
    evidence("rhs-isolation", dict(spec=spec, inputs=inputs, rhs=rhs, report=report))
    assert [r["status"] for r in report["rhs_reports"]] == ["diagnosed", *(["refused"] * 4)]
    assert len(calls) == 1 and np.array_equal(calls[0], rhs[0])
    assert report["rhs"].tobytes() == rhs.tobytes()
    assert all(r["input_mean_subtracted"] is False for r in report["rhs_reports"])
    assert report["rhs_reports"][1]["rhs_sum"] == 1.0
    assert all(value is None for value in report["solutions"][1:])


@pytest.mark.parametrize(
    "change", ["mapping", "coordinate", "boundary", "operator", "dtype", "probes"]
)
def test_declared_grid_and_input_refusals(change):
    spec, inputs = fixture()
    rhs = np.zeros(4)
    if change == "mapping":
        inputs["indices"][0], inputs["indices"][1] = inputs["indices"][1], inputs["indices"][0]
    elif change == "coordinate":
        spec.coordinates_m[0, 0] += 0.25
    elif change == "boundary":
        spec.boundaries["N"] = "value"
    elif change == "operator":
        inputs["operator"][0, 0] += 1
    elif change == "dtype":
        rhs = np.zeros(4, dtype=np.int64)
    else:
        rhs = np.zeros((33, 4))
    evidence("refusal-input-" + change, dict(spec=spec, inputs=inputs, rhs=rhs))
    with pytest.raises(ValueError) as caught:
        gauge.diagnose(spec, rhs=rhs, **inputs)
    evidence("refusal-" + change, dict(error=str(caught.value), type=type(caught.value).__name__))


def test_nonfinite_solver_return_is_retained_without_admission(monkeypatch):
    spec, inputs = fixture()
    monkeypatch.setattr(gauge.geometry, "environment_poisson", lambda *a, **k: np.full(4, np.inf))
    report = gauge.diagnose(spec, rhs=np.zeros(4), **inputs)
    evidence("nonfinite-output", dict(spec=spec, inputs=inputs, report=report))
    assert report["rhs_reports"][0]["status"] == "refused"
    assert report["rhs_reports"][0]["solve_attempted"] is True
    assert np.isinf(report["solutions"][0]).all() and not report["solutions"][0].flags.writeable
