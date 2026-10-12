"""Known geometry distinguishes strength ambiguity from curved calibration."""

import copy

import numpy as np
import pytest

from validation.assays import template_diagnostic as diagnostic
from validation.assays import template_readout as assay


def panel(function, *, arm="joint", margin=0.006):
    rows = [r for r in assay.cases(assay.protocol()) if r["arm"] == arm]
    values = {r["world_id"]: np.asarray(function(r)) for r in rows}
    report = assay.evaluate(rows, values, margin=margin)["arms"][arm]
    before = copy.deepcopy(report)
    result = diagnostic.diagnose_arm(rows, values, arm, report, margin=margin)
    assert report == before
    return result


def test_projection_known_parallel_perpendicular_and_null():
    actual = diagnostic.decompose([3, 4], [2, 0])
    assert actual["contrast_l2"] == 5
    assert actual["parallel_l2"] == 3 and actual["perpendicular_l2"] == 4
    assert actual["parallel_squared_norm_fraction"] == pytest.approx(9 / 25)
    assert actual["equivalent_strength_change"] == 1.5
    null = diagnostic.decompose([0, 0], [2, 0])
    assert null["parallel_squared_norm_fraction"] is None
    zero_tangent = diagnostic.decompose([3, 4], [0, 0])
    assert not zero_tangent["tangent_nonzero"]
    assert zero_tangent["perpendicular_l2"] == 5


def test_projection_and_interval_reject_invalid_support():
    for delta, tangent in (([], []), ([0, 1], [1]), ([np.nan], [1]), ([[1]], [[1]])):
        with pytest.raises(ValueError):
            diagnostic.decompose(delta, tangent)
    for levels, strength in (([0.8, 0.4], 0.6), ([0.4, 0.8], 0.9), ([0.4, np.nan], 0.5)):
        with pytest.raises(ValueError):
            diagnostic.interval(levels, strength)
    assert diagnostic.interval([0.4, 0.6, 0.8], 0.8) == (1, 1)


def test_exact_linear_curves_can_still_have_strength_timing_ambiguity():
    result = panel(
        lambda r: [100 * r["amplitude"] + 0.2 * r["timing"], 20 * r["location"], 0.01 * r["timing"]]
    )
    assert result["cases"] == 16 and result["unique_timing_pairs"] == 8
    assert result["original_correct_and_resolved"] == 0
    assert result["on_true_curve_correct_and_above_margin"] == 0
    assert result["same_strength_calibration_residual_l2_range"][1] < 2e-14
    np.testing.assert_allclose(result["perpendicular_contrast_l2_range"], 0.01, rtol=1e-12)
    np.testing.assert_allclose(
        result["parallel_squared_norm_fraction_range"], 400 / 401, rtol=1e-12
    )
    np.testing.assert_allclose(
        result["opposite_curve_absolute_strength_shift_range"], 0.002, rtol=1e-11
    )
    assert result["opposite_curve_endpoint_cases"] == 0
    assert result["nearest_wrong_curve_matches_other_labels"]


def test_orthogonal_timing_survives_strength_changes():
    result = panel(lambda r: [100 * r["amplitude"], 20 * r["location"], 0.2 * r["timing"]])
    assert result["original_correct_and_resolved"] == 16
    assert result["on_true_curve_correct_and_above_margin"] == 16
    np.testing.assert_array_equal(result["parallel_squared_norm_fraction_range"], 0)
    np.testing.assert_allclose(result["perpendicular_contrast_l2_range"], 0.2)


def test_curvature_residual_is_distinguished_from_strength_alignment():
    def curved(row):
        a = row["amplitude"]
        bend = 500 * (a - 0.4) * (a - 0.6) * (a - 0.8)
        return [a, 20 * row["location"], 4 * row["timing"] + bend]

    result = panel(curved, margin=1.5)
    assert result["original_correct_and_resolved"] == 8
    assert result["on_true_curve_correct_and_above_margin"] == 16
    np.testing.assert_array_equal(result["parallel_squared_norm_fraction_range"], 0)
    np.testing.assert_allclose(
        result["same_strength_calibration_residual_l2_range"], [0.9375, 1.3125]
    )
    assert result["maximum_absolute_score_change_to_true_curve"] == pytest.approx(1.3125)


def test_no_cue_and_unused_labels_cannot_create_timing_evidence():
    result = panel(lambda r: np.zeros(3), arm="no_cue")
    assert result["original_correct_and_resolved"] == 0
    assert result["on_true_curve_correct_and_above_margin"] == 0
    assert result["parallel_squared_norm_fraction_range"] is None
    np.testing.assert_array_equal(result["observed_matched_contrast_l2_range"], 0)
    assert not panel(lambda r: np.zeros(3), arm="location_only")["has_timing_task"]


def test_changed_saved_score_cannot_be_silently_diagnosed():
    rows = [r for r in assay.cases(assay.protocol()) if r["arm"] == "joint"]
    values = {r["world_id"]: np.array([r["amplitude"], r["location"], r["timing"]]) for r in rows}
    report = assay.evaluate(rows, values, margin=0.001)["arms"]["joint"]
    report["tasks"]["timing"]["predictions"][0]["score"] += 0.01
    with pytest.raises(AssertionError):
        diagnostic.diagnose_arm(rows, values, "joint", report, margin=0.001)
