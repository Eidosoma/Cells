"""Independent exact binary arithmetic checks for the saved-row diagnostic."""

import math
import sys
from fractions import Fraction

import pytest

from validation.tissue.open_calcium_bath_energy_diagnostic import reduction_record


@pytest.mark.parametrize(
    "terms",
    [
        [1e16, 1.0, -1e16],
        [10.0, 0.25, -7.0, 0.01, -3.0, -0.26, 2e-16],
        [0.0] * 7,
        [1.0, -1.0, 1e-14, 2e-14, -3e-14, 4e-16, -4e-16],
    ],
)
def test_exact_binary_term_sum_and_error_decomposition(terms):
    observed = terms[0]
    for term in terms[1:]:
        observed += term
    result = reduction_record(terms, observed)
    encoded = result["exact_sum_of_rounded_terms"]
    exact = Fraction(int(encoded["numerator"]), int(encoded["denominator"]))
    independently_scaled = sum(Fraction(*v.as_integer_ratio()) for v in terms)
    assert exact == independently_scaled
    assert result["fsum_pJ_s"] == float(exact)
    assert result["final_reduction_error_pJ_s"] == float(Fraction(observed) - exact)
    assert result["terms_float_hex"] == [v.hex() for v in terms]
    assert result["reduction_error_within_bound"]
    assert not result["upstream_rounding_or_equation_error_bounded"]


def test_large_cancellation_does_not_hide_a_nonzero_exact_input_sum():
    result = reduction_record([1e16, 1.0, -1e16], 0.0)
    assert result["exact_sum_rounded_to_binary64_pJ_s"] == 1.0
    assert result["final_reduction_error_pJ_s"] == -1.0
    assert result["sum_absolute_terms_pJ_s"] == 2e16


@pytest.mark.parametrize(
    "terms,observed",
    [
        ([1.0], 1.0),
        ([math.nan, 0.0], 0.0),
        ([math.inf, -math.inf], 0.0),
        ([1.0, -1.0], 1e-14),
        ([sys.float_info.min / 2, 0.0], sys.float_info.min / 2),
        ([sys.float_info.max, sys.float_info.max, -sys.float_info.max], math.inf),
    ],
)
def test_mismatched_or_unsupported_arithmetic_refuses(terms, observed):
    with pytest.raises(ValueError):
        reduction_record(terms, observed)
