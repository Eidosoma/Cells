"""Distinguish weak signals from strength ambiguity without erasing failures."""

import copy

import numpy as np
import pytest

from validation.assays import source_order_spanning_diagnostic as diagnostic
from validation.assays import template_readout as reader


@pytest.mark.parametrize("confounded", [False, True])
def test_unresolved_cases_preserve_failures_and_diagnostic_oracles(confounded):
    rule = diagnostic.assay.protocol()
    rule["reader"]["voltage_margin_V"] = 0.006
    rows = [r for r in diagnostic.assay.cases(rule) if r["arm"] == "joint"]
    features = {
        r["world_id"]: np.array(
            [
                100 * r["amplitude"] + (0.2 * r["timing"] if confounded else 0),
                20 * r["location"],
                0.001 * r["timing"],
            ]
        )
        for r in rows
    }
    report = reader.evaluate(rows, features, margin=0.006)
    result = diagnostic.previous.panel_diagnosis(rows, [features] * 3, [report] * 3, rule)
    before = copy.deepcopy(result)
    unresolved = diagnostic.unresolved_cases(result, margin=0.006)
    assert result == before
    assert len(unresolved) == 32
    assert {r["world_id"] for r in unresolved} == {
        r["world_id"] for r in rows if r["split"] == "heldout"
    }
    for case in unresolved:
        assert case["task"] == "timing"
        assert case["original_case_remains_unresolved"]
        assert case["original_resolved_by_level"] == [False] * 3
        assert case["finest_margin_shortfall_V"] > 0.005
        assert case["finest_signed_score_change_V"] == 0
        assert not case["finest_pair_resolution_changed"]
        probe = case["finest_competitors"]
        assert probe["true_strength_oracle_resolved"] == confounded
        assert not probe["true_other_label_oracle_resolved"]
        assert not probe["nearest_wrong_flips_both"]
        assert all(
            not r["on_true_curve_correct_and_resolved"] for r in case["interpolation_by_level"]
        )
        assert case["oracle_probes_are_not_new_reader_results"]


def test_resolved_cases_are_not_mislabeled_as_failures():
    rule = diagnostic.assay.protocol()
    rows = [r for r in diagnostic.assay.cases(rule) if r["arm"] == "joint"]
    features = {
        r["world_id"]: np.array([100 * r["amplitude"], 20 * r["location"], 4 * r["timing"]])
        for r in rows
    }
    report = reader.evaluate(rows, features, margin=rule["reader"]["voltage_margin_V"])
    result = diagnostic.previous.panel_diagnosis(rows, [features] * 3, [report] * 3, rule)
    assert diagnostic.unresolved_cases(result, margin=rule["reader"]["voltage_margin_V"]) == []
