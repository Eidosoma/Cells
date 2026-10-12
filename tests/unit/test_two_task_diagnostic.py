"""Known-answer controls for the post-hoc diagnosis, without local run artifacts."""

import copy

import numpy as np
import pytest

from validation.assays import two_task as assay
from validation.assays import two_task_diagnostic as diagnostic


@pytest.fixture
def encoded_panel():
    rows = [r for r in assay.cases(assay.protocol()) if r["arm"] == "joint"]
    features = {}
    for r in rows:
        value = np.ones((3, 7))
        value[2 * r["timing"], (0, 3)[r["location"]]] -= r["amplitude"]
        features[r["world_id"]] = value.reshape(-1)
    return rows, features


def test_omitted_one_hot_support_has_analytically_wrong_centroid(encoded_panel):
    rows, features = encoded_panel
    # Calibration mean pulse strength is 0.6. The omitted support is orthogonal
    # to every training pulse. Its own class center has one pulse of size 0.6;
    # the other averages two pulses of size 0.3, and is therefore closer.
    records = diagnostic.input_geometry(rows, features)
    by_id = {r["world_id"]: r for r in rows}
    assert len(records) == 16  # Eight actual test cases, two tasks each.
    for r in records:
        a = by_id[r["world_id"]]["amplitude"]
        target = r["target"]
        assert r["class_counts"][target] == 2
        assert r["class_counts"][1 - target] == 4
        assert r["max_abs_training_dot"] == 0
        np.testing.assert_allclose(r["squared_distances"][target], a * a + 0.36)
        np.testing.assert_allclose(r["squared_distances"][1 - target], a * a + 0.18)
        assert r["nearest_class"] == 1 - target
    original = assay.evaluate(rows, features, margin=1e-9)["arms"]["joint"]
    for task in diagnostic.TASKS:
        assert original["tasks"][task]["metrics"]["forced_accuracy"] == 0
        assert original["tasks"][task]["metrics"]["resolved_fraction"] == 1


def test_balancing_restores_known_input_but_changes_generalization(encoded_panel):
    rows, features = encoded_panel
    scores = diagnostic.balanced(rows, features, 1e-9)
    for task in diagnostic.TASKS:
        report = scores[task]
        assert report["metrics"]["cases"] == 8
        assert report["metrics"]["resolved_correct_fraction_of_all_cases"] == 1
        training = set(report["calibration"][0]["calibration_world_ids"])
        testing = set(report["calibration"][0]["heldout_world_ids"])
        assert len(training) == len(testing) == 8 and training.isdisjoint(testing)
        assert {(r["location"], r["timing"]) for r in rows if r["world_id"] in training} == {
            (0, 0),
            (0, 1),
            (1, 0),
            (1, 1),
        }
    changed_rows = copy.deepcopy(rows)
    changed_features = {k: v.copy() for k, v in features.items()}
    for r in changed_rows:
        if r["split"] == "heldout":
            r["location"] = 1 - r["location"]
            r["timing"] = 1 - r["timing"]
            changed_features[r["world_id"]] += 100
    changed = diagnostic.balanced(changed_rows, changed_features, 1e-9)
    assert all(changed[t]["calibration"] == scores[t]["calibration"] for t in diagnostic.TASKS)


def test_input_marginalization_uses_axes_not_labels(encoded_panel):
    rows, features = encoded_panel
    before = {k: v.copy() for k, v in features.items()}
    marginal = diagnostic.input_marginals(features, times=3, cells=7)
    for r in rows:
        expected_location, expected_timing = np.zeros(7), np.zeros(3)
        expected_location[(0, 3)[r["location"]]] = r["amplitude"]
        expected_timing[2 * r["timing"]] = r["amplitude"]
        np.testing.assert_allclose(marginal["location"][r["world_id"]], expected_location)
        np.testing.assert_allclose(marginal["timing"][r["world_id"]], expected_timing)
        np.testing.assert_array_equal(features[r["world_id"]], before[r["world_id"]])
    for task in diagnostic.TASKS:
        result = diagnostic.score_task(assay.folds(rows, "joint"), marginal[task], task, 1e-9)
        assert result["metrics"]["cases"] == 8
        assert result["metrics"]["resolved_correct_fraction_of_all_cases"] == 1
    with pytest.raises(ValueError, match="time-major"):
        diagnostic.input_marginals({1: np.zeros((3, 7))}, times=3, cells=7)


def test_no_cue_stays_unresolved_in_both_diagnostics(encoded_panel):
    rows, features = encoded_panel
    features = {k: np.ones_like(v) for k, v in features.items()}
    marginal = diagnostic.input_marginals(features, times=3, cells=7)
    balanced = diagnostic.balanced(rows, features, 1e-9)
    for task in diagnostic.TASKS:
        summed = diagnostic.score_task(assay.folds(rows, "joint"), marginal[task], task, 1e-9)
        for report in (balanced[task], summed):
            assert report["metrics"]["forced_accuracy"] == 0.5
            assert report["metrics"]["resolved_fraction"] == 0
            assert report["metrics"]["accuracy_on_resolved"] is None


def test_paired_effects_separate_known_factors_and_keep_all_pairs(encoded_panel):
    rows, _ = encoded_panel
    features = {
        r["world_id"]: np.array([100 * r["location"], r["amplitude"], 0.001 * r["timing"]])
        for r in rows
    }
    effects = diagnostic.paired_effects(rows, features)
    for name, count, size in (
        ("timing_pairs", 8, 0.001),
        ("location_pairs", 8, 100),
        ("amplitude_pairs", 4, 0.4),
    ):
        assert len(effects[name]) == count
        np.testing.assert_allclose([r["l2_V"] for r in effects[name]], size)
        np.testing.assert_allclose([r["max_abs_V"] for r in effects[name]], size)
    assert effects["calibration_task_contrast_cosine"] == 0
    null = diagnostic.paired_effects(rows, {k: np.zeros(3) for k in features})
    assert null["calibration_task_contrast_cosine"] is None


def test_replay_rejects_changed_decisions_and_scores():
    expected = {
        "score": [2e-9],
        "prediction": 0,
        "resolved": True,
        "metrics": {"forced_accuracy": 0.5},
    }
    assert diagnostic.compare_replay(copy.deepcopy(expected), expected) == 0
    with pytest.raises(ValueError, match="decision"):
        diagnostic.compare_replay(expected | {"prediction": 1}, expected)
    with pytest.raises(AssertionError):
        diagnostic.compare_replay(expected | {"score": [2.1e-9]}, expected)
    with pytest.raises(ValueError, match="metrics"):
        diagnostic.compare_replay(
            expected | {"metrics": {"forced_accuracy": 0.5 + 1e-14}}, expected
        )
