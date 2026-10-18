"""Preserve gains, regressions and threshold borderlines when joining reports."""

import copy

import numpy as np
import pytest

from validation.assays import source_order_selected_diagnostic as diagnostic


def example():
    rows = [
        dict(
            world_id=i,
            arm="joint",
            split="heldout",
            preparation=f"p{i}",
            amplitude=0.4 + i / 10,
            location=i % 2,
            timing=1 - i % 2,
        )
        for i in (1, 2, 3, 4)
    ]
    # Gain, regression, unresolved on both schedules, resolved on both.
    scores = {1: (3, 1), 2: (1, 3), 3: (1, 1), 4: (3, 3)}
    levels = []
    for level in range(3):
        reports = []
        for side in range(2):
            tasks = {}
            for task in diagnostic.TASKS:
                predictions = []
                for row in rows:
                    score = 5 if task == "location" else scores[row["world_id"]][side]
                    # Case 4 is a timestep borderline, retained even though fine steps resolve.
                    if row["world_id"] == 4 and task == "timing" and side == 0 and level == 0:
                        score = 2
                    predictions.append(
                        dict(
                            world_id=row["world_id"],
                            target=row[task],
                            prediction=row[task],
                            resolved=score > 2,
                            score=(2 * row[task] - 1) * score,
                        )
                    )
                tasks[task] = dict(predictions=predictions)
            reports.append(
                dict(
                    feature_count=15,
                    arms=dict(joint=dict(tasks=tasks, calibration=dict(world_ids=[100, 101, 102]))),
                )
            )
        paired = diagnostic.assay.paired_report(
            *reports, primary_name="selected320", comparator_name="spanning512"
        ) | dict(level=level)
        levels.append(paired)
    return rows, levels


def test_paired_gain_regression_and_borderline_join_uses_identity_without_mutation():
    rows, levels = example()
    before = copy.deepcopy((rows, levels))
    result = diagnostic.paired_case_summary(rows, levels, margin=2)
    assert (rows, levels) == before
    by_id = {r["world_id"]: r for r in result["cases"]}
    assert by_id[1]["categories_by_level"] == ["primary_only"] * 3
    assert by_id[2]["categories_by_level"] == ["comparator_only"] * 3
    assert by_id[3]["categories_by_level"] == ["neither"] * 3
    assert by_id[4]["categories_by_level"] == ["comparator_only", "both", "both"]
    assert result["focus_world_ids"] == [1, 2, 3, 4]
    assert result["counts_by_level"][-1] == dict(
        primary_only=1, comparator_only=1, both=1, neither=1
    )
    for identity, delta, deficit in ((1, 2, -1), (2, -2, 1), (3, 0, 1)):
        task = by_id[identity]["tasks"]["timing"]
        np.testing.assert_array_equal(task["primary_minus_comparator_scores_V"], [delta] * 3)
        np.testing.assert_array_equal(task["margin_deficits_V"]["primary"], [deficit] * 3)
    assert by_id[4]["primary_unresolved_at_any_level"]
    assert by_id[4]["tasks"]["timing"]["margin_deficits_V"]["primary"] == [0, -1, -1]
    assert result["original_results_unchanged"]
    assert result["combines_neither_predictions_nor_scores_across_panels"]
    for level in levels:
        level["cases"].reverse()
    assert diagnostic.paired_case_summary(rows, levels, margin=2) == result


@pytest.mark.parametrize(
    "corruption",
    [
        "duplicate_row",
        "duplicate_case",
        "missing_case",
        "missing_level",
        "level_order",
        "panel",
        "prediction_id",
        "target",
    ],
)
def test_incomplete_or_mismatched_pairings_are_rejected(corruption):
    rows, levels = example()
    if corruption == "duplicate_row":
        rows.append(rows[0].copy())
    elif corruption == "duplicate_case":
        levels[0]["cases"].append(copy.deepcopy(levels[0]["cases"][0]))
    elif corruption == "missing_case":
        levels[0]["cases"].pop()
    elif corruption == "missing_level":
        levels.pop()
    elif corruption == "level_order":
        levels.reverse()
    elif corruption == "panel":
        levels[1]["comparator_panel"] = "long512"
    elif corruption == "prediction_id":
        levels[0]["cases"][0]["primary"]["timing"]["world_id"] += 100
    else:
        value = levels[0]["cases"][0]["comparator"]["timing"]
        value["target"] = 1 - value["target"]
    with pytest.raises(ValueError):
        diagnostic.paired_case_summary(rows, levels, margin=2)
