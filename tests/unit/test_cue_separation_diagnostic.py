"""Known archive seams and timestep attribution; no response simulation."""

import copy
import json

import numpy as np
import pytest

from cells.core.betse_junction_spec import definition_arrays
from cells.core.specs import parse_spec
from validation.assays import cue_separation_diagnostic as diagnostic
from validation.assays import template_diagnostic as geometry
from validation.assays import template_readout as reader


def archive(tmp_path):
    raw = json.loads((diagnostic.ROOT / diagnostic.assay.protocol()["template"]).read_text())
    state, _ = definition_arrays(parse_spec(raw).model)
    dt = 1e-6
    raw["execution"]["dt"] = dt
    raw["experiment"]["end_time"] = 8 * dt
    raw["experiment"]["observation_times"] = (np.array([2, 4, 6, 8]) * dt).tolist()
    concentration = np.stack(
        [state.active.tissue.cell_concentration + step * 1e-8 for step in range(9)]
    )
    patch, cell = diagnostic.history.voltage_history(concentration, raw["model"]["tissue"])
    record = dict(status="passed", input=raw, windows=[])
    for start, observed in ((0, [2, 4]), (4, [6, 8])):
        name = f"window-{start}.npz"
        np.savez_compressed(
            tmp_path / name,
            state__step_count=np.arange(start, start + 5),
            state__elapsed_s=np.arange(start, start + 5) * dt,
            state__cell_concentration=concentration[start : start + 5],
            observed__vm=patch[observed],
        )
        record["windows"].append(
            dict(
                file=name,
                start_step=start,
                stop_step=start + 4,
                observation_times=(np.array(observed) * dt).tolist(),
            )
        )
    return record, cell


def test_voltage_windows_count_shared_endpoint_once(tmp_path):
    record, cell = archive(tmp_path)
    before = copy.deepcopy(record)
    times, actual, report = diagnostic.window_history(tmp_path, record)
    np.testing.assert_array_equal(actual, cell)
    np.testing.assert_array_equal(times, np.arange(9) * 1e-6)
    assert report["states"] == 9 and report["windows"] == 2
    assert report["maximum_saved_patch_voltage_difference_V"] == 0
    assert record == before
    for window in (1, 0):
        broken = copy.deepcopy(record)
        broken["windows"][window]["start_step"] += 1
        with pytest.raises(ValueError, match="Noncontiguous"):
            diagnostic.window_history(tmp_path, broken)


@pytest.mark.parametrize(
    "key,index",
    [
        ("state__cell_concentration", 0),
        ("state__elapsed_s", 0),
        ("observed__vm", 0),
    ],
)
def test_corrupted_shared_state_clock_or_observation_is_rejected(tmp_path, key, index):
    record, _ = archive(tmp_path)
    path = tmp_path / record["windows"][1]["file"]
    with np.load(path, allow_pickle=False) as saved:
        values = dict(saved)
    values[key][index] += 1e-5
    np.savez_compressed(path, **values)
    with pytest.raises(AssertionError):
        diagnostic.window_history(tmp_path, record)


def synthetic_panel(*, feature_only):
    rows = [r for r in diagnostic.assay.cases() if r["arm"] == "joint"]
    old = {
        r["world_id"]: np.array([r["amplitude"], 20 * r["location"], 4 * r["timing"]]) for r in rows
    }
    new = {identity: values.copy() for identity, values in old.items()}
    for row in rows:
        if feature_only:
            if row["split"] != "calibration":
                new[row["world_id"]][-1] += (1 - 2 * row["timing"]) * 0.2
        else:
            new[row["world_id"]][-1] += 0.2
    arms = [
        reader.evaluate(rows, features, margin=1.95)["arms"]["joint"] for features in (old, new)
    ]
    return rows, old, new, arms


@pytest.mark.parametrize("feature_only", [True, False])
def test_separate_feature_drift_from_common_calibration_shift(feature_only):
    rows, old, new, arms = synthetic_panel(feature_only=feature_only)
    before = copy.deepcopy(arms)
    result = diagnostic.resolution_attribution(rows, old, new, *arms, margin=1.95)
    timing = [r for r in result["details"] if r["task"] == "timing"]
    assert len(timing) == 16 and arms == before
    for row in result["details"]:
        assert row["score_change_V"] == pytest.approx(
            row["feature_change_with_old_reader_V"] + row["reader_change_at_new_features_V"]
        )
        assert row["score_change_V"] == pytest.approx(
            row["reader_change_at_old_features_V"] + row["feature_change_with_new_reader_V"]
        )
        assert abs(row["feature_change_with_old_reader_V"]) <= 0.2 + 1e-14
    if feature_only:
        assert all(r["resolution_changed"] and not r["prediction_changed"] for r in timing)
        np.testing.assert_allclose([abs(r["score_change_V"]) for r in timing], 0.2)
        np.testing.assert_allclose([r["reader_change_at_new_features_V"] for r in timing], 0)
        levels = [
            geometry.diagnose_arm(rows, features, "joint", arm, margin=1.95)
            for features, arm in zip((old, new), arms, strict=True)
        ]
        summary = diagnostic.case_summary(
            rows, [levels[0], levels[0], levels[1]], [result], margin=1.95
        )
        assert len(summary["unresolved_world_ids"]) == 16
        assert len(summary["finest_pair_borderline_world_ids"]) == 16
        assert summary["correct_and_resolved_at_all_three_steps"] == 0
    else:
        np.testing.assert_allclose([r["score_change_V"] for r in timing], 0, atol=1e-14)
        early = [r for r in timing if r["target"] == 0]
        np.testing.assert_allclose([r["feature_change_with_old_reader_V"] for r in early], 0.2)
        np.testing.assert_allclose([r["reader_change_at_new_features_V"] for r in early], -0.2)
        assert not any(r["resolution_changed"] for r in timing)


def test_attribution_rejects_changed_saved_scores():
    rows, old, new, arms = synthetic_panel(feature_only=True)
    arms[1]["tasks"]["timing"]["predictions"][0]["score"] += 0.01
    with pytest.raises(AssertionError):
        diagnostic.resolution_attribution(rows, old, new, *arms, margin=1.95)
