"""Known shared background shifts versus changes in the cue response."""

import copy

import numpy as np
import pytest

from validation.assays import baseline_transfer_diagnostic as diagnostic


def panel():
    rows = diagnostic.assay.cases()
    background = np.array([0.03, 0.02, -0.01])
    values = {}
    for row in rows:
        response = np.array([row["amplitude"] * 1e-5, row["location"] * 4e-8, row["timing"] * 3e-8])
        if row["arm"] in ("no_cue", "disconnected"):
            response[:] = 0
        elif row["arm"] == "location_only":
            response[2] = 0
        elif row["arm"] == "timing_only":
            response[1] = 0
        values[row["world_id"]] = background + response
    return rows, values


def evaluate(rows, source, target, a=0, b=0):
    return diagnostic.transfer(
        rows, source, target, source_reference=a, target_reference=b, margin=2e-9
    )


def test_shared_background_translation_restores_transfer_without_refitting_responses():
    rows, old = panel()
    shift = np.array([0, 1e-6, -2e-6])
    new = {identity: value + shift for identity, value in old.items()}
    before = {k: v.copy() for k, v in old.items()}
    a, info_a = diagnostic.no_cue_reference(rows, old)
    b, _ = diagnostic.no_cue_reference(rows, new)
    source = evaluate(rows, old, old)
    raw = evaluate(rows, old, new)
    centered = evaluate(rows, old, new, a, b)
    assert source["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    assert not raw["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    assert centered["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    assert not info_a["stimulated_or_evaluation_data_fit_the_baseline"]
    assert (
        diagnostic.translation_check(source, evaluate(rows, old, old, a, a))["status"] == "passed"
    )
    diagnostic.translation_check(evaluate(rows, new, new), evaluate(rows, new, new, b, b))
    difference = diagnostic.drift(rows, old, new, a, b)
    np.testing.assert_allclose(difference["background_drift_V"], shift, atol=1e-17, rtol=0)
    assert max(r["referenced_drift_l2_V"] for r in difference["cases"]) < 1e-17
    changes = diagnostic.transfer_changes(evaluate(rows, old, old, a, a), centered)
    assert not any(r["prediction_changed_world_ids"] for r in changes)
    assert not any(r["resolution_changed_world_ids"] for r in changes)
    for identity, value in old.items():
        np.testing.assert_array_equal(value, before[identity])


def test_background_reference_cannot_hide_cue_dependent_drift():
    rows, old = panel()
    shift = np.array([0, 1e-6, -2e-6])
    new = {identity: value + shift for identity, value in old.items()}
    changed = [r for r in rows if r["arm"] == "joint" and r["timing"] == 1]
    for row in changed:
        new[row["world_id"]][2] -= 2e-8
    a, _ = diagnostic.no_cue_reference(rows, old)
    b, _ = diagnostic.no_cue_reference(rows, new)
    transferred = evaluate(rows, old, new, a, b)
    assert not transferred["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    changes = diagnostic.transfer_changes(evaluate(rows, old, old, a, a), transferred)
    timing = next(r for r in changes if r["arm"] == "joint" and r["task"] == "timing")
    assert timing["correct_and_resolved"] == 8
    assert len(timing["prediction_changed_world_ids"]) == 8
    residual = diagnostic.drift(rows, old, new, a, b)
    ids = {r["world_id"] for r in changed}
    np.testing.assert_allclose(
        [r["referenced_drift_l2_V"] for r in residual["cases"] if r["world_id"] in ids],
        2e-8,
        atol=1e-17,
        rtol=0,
    )
    # Matched translation must still be invariant even though transfer fails.
    diagnostic.translation_check(evaluate(rows, new, new), evaluate(rows, new, new, b, b))


@pytest.mark.parametrize("split", ["calibration", "heldout"])
def test_inconsistent_duplicate_controls_are_rejected(split):
    rows, values = panel()
    row = next(r for r in rows if r["arm"] == "no_cue" and r["split"] == split)
    values[row["world_id"]][0] += 1e-8
    with pytest.raises(AssertionError):
        diagnostic.no_cue_reference(rows, values)


def test_reference_does_not_depend_on_stimulated_labels_strengths_or_responses():
    rows, values = panel()
    reference, metadata = diagnostic.no_cue_reference(rows, values)
    changed_rows = copy.deepcopy(rows)
    for row in changed_rows:
        if row["arm"] != "no_cue":
            row.update(amplitude=-999, location=999, timing=-999)
            values[row["world_id"]] = np.array([99.0, 98.0, 97.0])
    actual, report = diagnostic.no_cue_reference(changed_rows, values)
    np.testing.assert_array_equal(actual, reference)
    assert report == metadata
    without_training = [
        r for r in rows if not (r["arm"] == "no_cue" and r["split"] == "calibration")
    ]
    with pytest.raises(ValueError, match="calibration reference"):
        diagnostic.no_cue_reference(without_training, values)


def test_translation_checks_reject_changed_scores_and_decisions():
    rows, features = panel()
    report = evaluate(rows, features, features)
    broken = copy.deepcopy(report)
    broken["arms"]["joint"]["tasks"]["timing"]["predictions"][0]["score"] += 1e-9
    with pytest.raises(AssertionError):
        diagnostic.translation_check(report, broken)
    broken = copy.deepcopy(report)
    broken["arms"]["joint"]["tasks"]["timing"]["predictions"][0]["resolved"] = False
    with pytest.raises(ValueError, match="resolved decision"):
        diagnostic.translation_check(report, broken)


def test_zero_drift_has_no_spurious_relative_fraction():
    rows, features = panel()
    reference, _ = diagnostic.no_cue_reference(rows, features)
    result = diagnostic.drift(rows, features, features, reference, reference)
    assert result["background_drift_l2_V"] == 0
    assert all(
        r["raw_drift_l2_V"] == r["referenced_drift_l2_V"] == 0
        and r["remaining_l2_fraction"] is None
        for r in result["cases"]
    )
