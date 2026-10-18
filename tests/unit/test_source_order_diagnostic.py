"""Known joint-label collisions, strength ambiguity and timestep-borderline cases."""

import copy

import numpy as np
import pytest

from validation.assays import source_order_diagnostic as diagnostic
from validation.assays import template_readout as reader


def panel(function, *, margin=0.006):
    rows = [r for r in diagnostic.assay.cases() if r["arm"] == "joint"]
    values = {r["world_id"]: np.asarray(function(r), dtype=float) for r in rows}
    report = reader.evaluate(rows, values, margin=margin)["arms"]["joint"]
    return rows, values, report


def test_both_label_collision_is_distinct_from_single_task_separation():
    rows, values, report = panel(
        lambda r: [
            100 * r["amplitude"],
            r["location"] + r["timing"],
            0.001 * (r["location"] - r["timing"]),
        ]
    )
    before, saved = copy.deepcopy(report), {k: v.copy() for k, v in values.items()}
    result = diagnostic.competing_curves(rows, values, report, margin=0.006)
    assert report == before
    for identity in values:
        np.testing.assert_array_equal(values[identity], saved[identity])
    for task in diagnostic.TASKS:
        summary = result["per_task"][task]
        assert summary["original_correct_and_resolved"] == 8
        assert summary["both_label_competitor_cases"] == 8
        assert summary["true_other_label_oracle_resolved"] == 16
        assert summary["true_strength_oracle_resolved"] == 8
    weak = [r for r in result["details"] if not r["original_resolved"]]
    assert len(weak) == 16 and all(r["nearest_wrong_flips_both"] for r in weak)
    np.testing.assert_allclose([r["original_correct_signed_score_V"] for r in weak], 0.001)
    for shape in diagnostic.joint_geometry(rows, values):
        assert shape["crossed_label_01_to_10_l2_V"] == pytest.approx(0.002)
        assert shape["aligned_label_00_to_11_l2_V"] == pytest.approx(2)
        assert shape["interaction_l2_V"] < 1e-14
        assert shape["main_contrast_cosine"] == pytest.approx((1 - 1e-6) / (1 + 1e-6))
        assert shape["smaller_to_larger_singular_ratio"] == pytest.approx(0.001)


def test_known_strength_probe_exposes_strength_ambiguity_without_fixing_other_label():
    rows, values, report = panel(
        lambda r: [
            100 * r["amplitude"] + 0.2 * r["timing"],
            20 * r["location"],
            0.001 * r["timing"],
        ]
    )
    result = diagnostic.competing_curves(rows, values, report, margin=0.006)
    timing = result["per_task"]["timing"]
    assert timing["original_correct_and_resolved"] == 0
    assert timing["both_label_competitor_cases"] == 0
    assert timing["true_other_label_oracle_resolved"] == 0
    assert timing["true_strength_oracle_resolved"] == 16
    assert result["per_task"]["location"]["original_correct_and_resolved"] == 16
    assert all(r["main_contrast_cosine"] == 0 for r in diagnostic.joint_geometry(rows, values))


def test_orthogonal_tasks_remain_resolved_without_oracle_information():
    rows, values, report = panel(
        lambda r: [100 * r["amplitude"], 20 * r["location"], 4 * r["timing"]]
    )
    result = diagnostic.competing_curves(rows, values, report, margin=0.006)
    for task in result["per_task"].values():
        assert task["original_correct_and_resolved"] == 16
        assert task["true_other_label_oracle_resolved"] == 16
        assert task["true_strength_oracle_resolved"] == 16
        assert task["both_label_competitor_cases"] == 0


def test_four_corner_contrasts_include_interaction_and_ignore_shared_background():
    rows, values, _ = panel(
        lambda r: (
            np.array([2 * r["location"], 4 * r["timing"], 3 * r["location"] * r["timing"]])
            * r["amplitude"]
        )
    )
    original = diagnostic.joint_geometry(rows, values)
    shifted = diagnostic.joint_geometry(
        list(reversed(rows)), {i: v + [17, -2, 8] for i, v in values.items()}
    )
    for shape in original:
        a = shape["strength"]
        np.testing.assert_allclose(shape["mean_location_contrast_V"], [2 * a, 0, 1.5 * a])
        np.testing.assert_allclose(shape["mean_order_contrast_V"], [0, 4 * a, 1.5 * a])
        np.testing.assert_allclose(shape["interaction_V"], [0, 0, 3 * a])
        other = next(r for r in shifted if r["preparation"] == shape["preparation"])
        for key in (
            "mean_location_contrast_V",
            "mean_order_contrast_V",
            "interaction_V",
            "main_contrast_cosine",
            "smaller_to_larger_singular_ratio",
        ):
            np.testing.assert_allclose(shape[key], other[key], atol=1e-14, rtol=1e-13)


def test_null_and_one_dimensional_geometry_have_no_spurious_second_direction():
    rows, values, _ = panel(lambda _: [0.0])
    for shape in diagnostic.joint_geometry(rows, values):
        assert shape["main_contrast_cosine"] is None
        assert shape["smaller_to_larger_singular_ratio"] is None
        assert shape["singular_values_V"] == [0.0, 0.0]
    for row in rows:
        values[row["world_id"]] = np.array([row["location"] + row["timing"]], dtype=float)
    for shape in diagnostic.joint_geometry(rows, values):
        assert shape["main_contrast_cosine"] == 1
        assert shape["smaller_to_larger_singular_ratio"] == 0


@pytest.mark.parametrize("corruption", ["duplicate", "strength", "nonfinite"])
def test_mismatched_joint_panels_are_rejected(corruption):
    rows, values, _ = panel(lambda r: [r["amplitude"], r["location"], r["timing"]])
    if corruption == "duplicate":
        rows.append(rows[0].copy())
    elif corruption == "strength":
        rows[0]["amplitude"] += 0.01
    else:
        values[rows[0]["world_id"]][0] = np.nan
    with pytest.raises(ValueError):
        diagnostic.joint_geometry(rows, values)


@pytest.mark.parametrize("task", diagnostic.TASKS)
def test_changed_saved_scores_and_identities_are_rejected(task):
    rows, values, report = panel(lambda r: [r["amplitude"], r["location"], r["timing"]])
    changed = copy.deepcopy(report)
    changed["tasks"][task]["predictions"][0]["score"] += 0.01
    with pytest.raises(AssertionError):
        diagnostic.competing_curves(rows, values, changed, margin=0.006)
    changed = copy.deepcopy(report)
    changed["tasks"][task]["predictions"][0]["world_id"] += 1
    with pytest.raises(ValueError, match="identity"):
        diagnostic.competing_curves(rows, values, changed, margin=0.006)


def test_summary_preserves_failures_and_timestep_borderlines_for_both_tasks():
    rows, old, old_arm = panel(
        lambda r: [r["amplitude"], 20 * r["location"], 4 * r["timing"]], margin=1.95
    )
    new = {i: v.copy() for i, v in old.items()}
    for row in rows:
        if row["split"] == "heldout":
            new[row["world_id"]][-1] += (1 - 2 * row["timing"]) * 0.2
    new_arm = reader.evaluate(rows, new, margin=1.95)["arms"]["joint"]
    probes = [
        diagnostic.competing_curves(rows, f, a, margin=1.95)
        for f, a in ((old, old_arm), (new, new_arm))
    ]
    attribution = diagnostic.saved_history.resolution_attribution(
        rows, old, new, old_arm, new_arm, margin=1.95
    )
    summary = diagnostic.case_summary(
        rows, [probes[0], probes[0], probes[1]], [attribution], margin=1.95
    )
    expected = [r["world_id"] for r in rows if r["split"] == "heldout"]
    assert summary["unresolved_joint_world_ids"] == expected
    assert summary["finest_pair_borderline_world_ids"] == expected
    assert summary["joint_correct_and_resolved_at_all_steps"] == 0
    assert all(
        r["tasks"]["location"]["resolved_by_level"] == [True, True, True] for r in summary["cases"]
    )
    assert all(
        r["tasks"]["timing"]["resolved_by_level"] == [True, True, False] for r in summary["cases"]
    )
