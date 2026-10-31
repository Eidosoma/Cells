"""Checker regressions, not additional physical or independent cases."""

from copy import deepcopy

import pytest

from validation.geometry.active_polygon_physiology_reference import (
    ENERGY_LIMITS,
    assert_energy,
    assert_initial_field,
    energy_evidence,
)


@pytest.mark.parametrize("model_id", ENERGY_LIMITS)
def test_energy_defects_are_rejected_even_when_state_and_potential_are_unchanged(model_id):
    actual_limit, independent_limit = ENERGY_LIMITS[model_id]
    good = energy_evidence(model_id, 0.0, {"physical_energy_balance_pJ_s": 0.0})
    assert_energy(model_id, good)
    for sign in (-1, 1):
        bad_actual = deepcopy(good)
        bad_actual["actual_energy_balance_pJ_s"] = sign * 2 * actual_limit
        with pytest.raises(AssertionError):
            assert_energy(model_id, bad_actual)
        if independent_limit is not None:
            bad_reference = deepcopy(good)
            bad_reference["independent_energy_balance_pJ_s"] = sign * 2 * independent_limit
            with pytest.raises(AssertionError):
                assert_energy(model_id, bad_reference)


@pytest.mark.parametrize("column", ["actual", "independent"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_residuals_cannot_pass(column, invalid):
    model_id = "resolved_calcium@1"
    record = energy_evidence(model_id, 0.0, {"physical_energy_balance_pJ_s": 0.0})
    record[column + "_energy_balance_pJ_s"] = invalid
    with pytest.raises(AssertionError):
        assert_energy(model_id, record)


def test_actual_and_independent_limits_remain_distinct():
    # Existing actual energy@2 allowance is 2e-8; its independent proof is 2e-10.
    model_id = "resolved_energy@2"
    record = energy_evidence(model_id, 1e-9, {"physical_energy_balance_pJ_s": 1e-10})
    assert_energy(model_id, record)
    record["independent_energy_balance_pJ_s"] = record["actual_energy_balance_pJ_s"]
    with pytest.raises(AssertionError):
        assert_energy(model_id, record)


def test_inapplicable_ionic_reference_identity_is_explicitly_unavailable():
    model_id = "resolved_tissue@2"
    record = energy_evidence(model_id, 0.0, {})
    assert_energy(model_id, record)
    assert record["independent_identity_available"] is False
    assert record["independent_energy_balance_pJ_s"] is None
    record["independent_energy_balance_pJ_s"] = 0.0
    with pytest.raises(AssertionError):
        assert_energy(model_id, record)


def test_missing_required_reference_identity_is_not_assumed_zero():
    with pytest.raises(KeyError, match="physical_energy_balance_pJ_s"):
        energy_evidence("resolved_calcium@1", 0.0, {})


def test_reported_budgets_cannot_silently_widen_the_check():
    model_id = "resolved_calcium@1"
    record = energy_evidence(model_id, 0.0, {"physical_energy_balance_pJ_s": 0.0})
    for field in ("actual_absolute_budget_pJ_s", "independent_absolute_budget_pJ_s"):
        changed = deepcopy(record)
        changed[field] = 2e-8
        with pytest.raises(AssertionError):
            assert_energy(model_id, changed)


def test_full_field_acceptance_enforces_the_energy_gate():
    model_id = "resolved_calcium@1"
    stage = dict(
        derivative_error_over_budget=0.0,
        potential_error_over_budget=0.0,
        intended_potential_error_over_budget=0.0,
        production_stage_valid=True,
        expected_potential_V=[-0.05],
        energy=energy_evidence(model_id, 1e-9, {"physical_energy_balance_pJ_s": 0.0}),
    )
    with pytest.raises(AssertionError):
        assert_initial_field(dict(model_id=model_id, stages=[stage]))
