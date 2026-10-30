"""Arithmetic/override isolation checks, without trajectory qualification credit."""

from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest

from validation.tissue.open_calcium_bath_energy_upstream import (
    decimal_solve,
    exact_products,
    program_identity,
    rational,
    wider_arithmetic,
)


def test_exact_products_keep_bits_lost_by_float64_product_then_sum():
    a = np.array([1 + 2**-27, 1.0])
    b = np.array([1 - 2**-27, -1.0])
    assert np.sum(a * b) == 0
    assert exact_products(a, b) == -Fraction(1, 2**54)
    high = np.longdouble(1) + np.longdouble(2) ** -60
    assert rational(high) == Fraction(1) + Fraction(1, 2**60)
    assert rational(float(high)) != rational(high)


def test_decimal_solve_preserves_extra_bits_and_inputs():
    a = np.array([[3.0, 0.0], [0.0, 7.0]])
    b = np.ones(2)
    original_a, original_b = a.copy(), b.copy()
    answer = decimal_solve(a, b)
    assert answer.dtype == np.longdouble
    assert abs(rational(answer[0]) - Fraction(1, 3)) < Fraction(1, 2**63)
    assert abs(rational(answer[1]) - Fraction(1, 7)) < Fraction(1, 2**64)
    assert rational(answer[0]) != rational(np.float64(1 / 3))
    np.testing.assert_array_equal(a, original_a)
    np.testing.assert_array_equal(b, original_b)


def test_decimal_partial_pivot_and_singular_refusal():
    np.testing.assert_array_equal(
        decimal_solve(np.array([[0.0, 2.0], [3.0, 1.0]]), np.array([4.0, 5.0])), [1, 2]
    )
    with pytest.raises(np.linalg.LinAlgError):
        decimal_solve(np.ones((2, 2)), np.ones(2))


@pytest.mark.parametrize(
    "a,b",
    [
        (np.ones((2, 3)), np.ones(2)),
        (np.eye(2), np.ones((2, 1))),
        (np.array([[np.nan]]), np.ones(1)),
        (np.eye(1), np.array([np.inf])),
    ],
)
def test_invalid_linear_system_refuses(a, b):
    with pytest.raises(ValueError):
        decimal_solve(a, b)


def test_overrides_restore_after_failure_and_keep_exact_constants():
    from cells.processes import electrochemistry as physical

    solve, r = np.linalg.solve, physical.R
    with pytest.raises(RuntimeError, match="intentional"):
        with wider_arithmetic(constants=True) as names:
            assert np.linalg.solve is decimal_solve
            assert "cells.processes.electrochemistry.R" in names
            assert rational(physical.R) == rational(r)
            assert isinstance(physical.R, np.longdouble)
            raise RuntimeError("intentional")
    assert np.linalg.solve is solve and physical.R is r


def test_program_identity_splits_intermediate_and_final_rounding():
    c, e = np.array([1e16, 0.0, -1e16]), np.array([1.0, 4.0, 1.0])
    s = SimpleNamespace(
        chemical_power_pJ_s=c, electrochemical_power_pJ_s=c + e, electrode_power_pJ_s=-e
    )
    rows = program_identity(s)
    assert [r["observed_residual_pJ_s"] for r in rows] == [1, 0, 1]
    assert all(
        r["observed_residual_pJ_s"]
        == -r["intermediate_addition_error_pJ_s"] + r["final_reduction_error_pJ_s"]
        for r in rows
    )
    s.electrochemical_power_pJ_s = np.zeros(3)
    with pytest.raises(ValueError, match="Unexpected"):
        program_identity(s)
