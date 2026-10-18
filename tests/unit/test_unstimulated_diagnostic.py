"""Known voltage reconstruction and diagnostic geometry; no simulation."""

import copy
import json

import numpy as np
import pytest

from cells.core.betse_junction_spec import definition_arrays
from cells.core.specs import parse_spec
from cells.numerics import betse_spatial as passive
from validation.assays import template_readout as reader
from validation.assays import unstimulated_diagnostic as diagnostic
from validation.assays import unstimulated_readout as assay


def test_voltage_history_matches_field_and_area_weighting():
    raw = json.loads((diagnostic.ROOT / assay.protocol()["template"]).read_text())
    state, parameters = definition_arrays(parse_spec(raw).model)
    tissue = raw["model"]["tissue"]
    boundary = np.arange(100, dtype=float).reshape(10, 10) * 1e-5
    tissue["boundary_values"] = boundary.tolist()
    layout = parameters.active.tissue._replace(boundary_values=boundary)
    initial = state.active.tissue
    concentrations = np.stack([initial.cell_concentration + i * 1e-8 for i in range(3)])
    patch, weighted = diagnostic.voltage_history(concentrations, tissue)
    expected = [
        passive.field(initial._replace(cell_concentration=c), layout, xp=np) for c in concentrations
    ]
    np.testing.assert_array_equal(patch, np.stack([f.membrane_voltage_V for f in expected]))
    for i in range(7):
        mask = layout.cell_owner == i
        reference = (
            np.sum(patch[:, mask] * layout.membrane_area[mask], axis=1)
            / layout.membrane_area[mask].sum()
        )
        np.testing.assert_allclose(weighted[:, i], reference, atol=1e-16, rtol=0)
    assert np.max(abs(weighted - np.stack([f.cell_mean_voltage_V for f in expected]))) > 1e-6
    for bad in (
        concentrations[0],
        concentrations[:, :, :6],
        concentrations * np.nan,
        -concentrations,
    ):
        with pytest.raises(ValueError, match="concentrations"):
            diagnostic.voltage_history(bad, tissue)


def test_pair_separation_and_time_trends():
    times = np.arange(4, dtype=float)
    delta = np.arange(4)[:, None] * np.array([[3.0, 4.0]])
    result = diagnostic.pair_summary(times, delta, [1, 2, 3], margin=2)
    assert result["sampled_contrast_l2_V"] == pytest.approx(np.sqrt(350))
    assert result["per_readout_l2_V"] == [5, 10, 15]
    assert result["end_to_middle_ratio"] == 1.5
    assert result["final_interval_non_decreasing"]
    assert result["necessary_separation_for_both_margin_decisions"]
    assert result["separation_condition_is_not_sufficient"]
    equal = diagnostic.pair_summary(times, [[0], [0], [0], [4]], [1, 2, 3], margin=2)
    assert equal["sampled_half_separation_V"] == 2
    assert not equal["necessary_separation_for_both_margin_decisions"]
    decaying = diagnostic.pair_summary(times, delta[::-1], [1, 2, 3], margin=2)
    assert decaying["end_l2_V"] == 0 and decaying["first_maximum_time_s"] == 0
    assert decaying["final_interval_norm_change_V"] < 0
    assert not decaying["final_interval_non_decreasing"]


def test_pair_nulls_and_invalid_histories():
    times, delta, indices = np.arange(4), np.zeros((4, 2)), [1, 2, 3]
    result = diagnostic.pair_summary(times, delta, indices, margin=2)
    assert result["exactly_zero"] and result["end_to_middle_ratio"] is None
    assert not result["necessary_separation_for_both_margin_decisions"]
    for t, d, i, m in (
        (times, delta, [3, 2, 1], 2),
        (times, delta, indices, 0),
        (times[::-1], delta, indices, 2),
        (times, delta * np.nan, indices, 2),
    ):
        with pytest.raises(ValueError, match="Invalid paired"):
            diagnostic.pair_summary(t, d, i, margin=m)


def panel(function, task, *, margin=0.006):
    rows = [r for r in assay.cases(assay.protocol()) if r["arm"] == "joint"]
    values = {r["world_id"]: np.asarray(function(r)) for r in rows}
    report = reader.evaluate(rows, values, margin=margin)["arms"]["joint"]
    before = copy.deepcopy(report)
    actual = diagnostic.task_geometry(rows, values, "joint", task, report, margin=margin)
    assert before == report
    return actual, (rows, values, report)


@pytest.mark.parametrize("task", ["location", "timing"])
def test_both_tasks_distinguish_strength_alignment_from_weak_amplitude(task):
    other = next(t for t in diagnostic.TASKS if t != task)
    result, _ = panel(
        lambda r: [100 * r["amplitude"] + 0.2 * r[task], 20 * r[other], 0.01 * r[task]], task
    )
    assert result["cases"] == 16
    assert (
        result["original_correct_and_resolved"] == result["on_true_curve_correct_and_resolved"] == 0
    )
    np.testing.assert_allclose(result["perpendicular_contrast_l2_range_V"], 0.01)
    np.testing.assert_allclose(result["strength_parallel_squared_fraction_range"], 400 / 401)
    assert result["calibration_residual_l2_range_V"][1] < 2e-14
    assert result["max_score_change_to_true_curve_V"] < 2e-14


def test_true_curve_probe_exposes_calibration_curvature_without_retuning():
    def curved(row):
        a = row["amplitude"]
        bend = 500 * (a - 0.4) * (a - 0.6) * (a - 0.8)
        return [a, 20 * row["location"], 4 * row["timing"] + bend]

    result, _ = panel(curved, "timing", margin=1.5)
    assert result["original_correct_and_resolved"] < 16
    assert result["on_true_curve_correct_and_resolved"] == 16
    np.testing.assert_array_equal(result["strength_parallel_squared_fraction_range"], 0)
    assert result["max_score_change_to_true_curve_V"] > 0.5


def test_changed_saved_score_is_rejected():
    _, (rows, values, report) = panel(
        lambda r: [r["amplitude"], r["location"], r["timing"]], "location"
    )
    report["tasks"]["location"]["predictions"][0]["score"] += 0.01
    with pytest.raises(AssertionError):
        diagnostic.task_geometry(rows, values, "joint", "location", report, margin=0.006)
