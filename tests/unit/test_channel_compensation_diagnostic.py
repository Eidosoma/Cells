"""Analytic decomposition and calibration-isolation checks for saved voltages."""

import numpy as np
import pytest

from validation.assays import channel_compensation as source
from validation.assays import channel_compensation_diagnostic as diagnostic


def test_factorial_separates_cancellation_and_interaction():
    location = np.zeros(15)
    order = np.zeros(15)
    interaction = np.zeros(15)
    location[0], order[0], interaction[1] = 4e-9, 3e-9, 2e-9
    grid = {(a, b): a * location + b * order + a * b * interaction for a in (0, 1) for b in (0, 1)}
    result = diagnostic.factorial(grid)
    np.testing.assert_allclose(result["location_effect_V"], location + interaction / 2, atol=1e-24)
    np.testing.assert_allclose(result["order_effect_V"], order + interaction / 2, atol=1e-24)
    np.testing.assert_allclose(result["interaction_V"], interaction, atol=1e-24)
    assert result["opposed_label_pair"]["distance_V"] == pytest.approx(1e-9, abs=1e-24)
    assert result["aligned_label_pair"]["distance_V"] == pytest.approx(
        np.sqrt(53) * 1e-9, abs=1e-24
    )
    assert result["opposed_pair_identity_error_V"] < 1e-24
    assert result["aligned_pair_identity_error_V"] < 1e-24


def test_spatial_temporal_contributions_and_zero_signal():
    delta = np.zeros((3, 5))
    delta[0, 1], delta[2, 4] = 3e-9, -4e-9
    result = diagnostic.distance_parts(delta.reshape(-1))
    assert result["distance_V"] == pytest.approx(5e-9, abs=1e-24)
    np.testing.assert_allclose(result["by_cell_squared_fraction"], [0, 0.36, 0, 0, 0.64])
    np.testing.assert_allclose(result["by_time_squared_fraction"], [0.36, 0, 0.64])
    zero = diagnostic.distance_parts(np.zeros(15))
    assert zero["distance_V"] == 0 and zero["by_cell_squared_fraction"] is None
    assert (
        diagnostic.factorial({(a, b): np.zeros(15) for a in (0, 1) for b in (0, 1)})[
            "effect_cosine"
        ]
        is None
    )


def test_calibration_only_named_loading():
    rows = source.cases(source.condition_rule(source.protocol(), "sham"))

    class PoisonHeldout(dict):
        def __getitem__(self, key):
            if key != "split":
                raise AssertionError("Held-out metadata accessed")
            return "evaluation"

    class NamedOnly:
        def __init__(self):
            self.accessed = []

        def __getitem__(self, key):
            assert key.split("__")[1] in source.PANELS
            assert int(key.split("__")[-1]) in {r["world_id"] for r in rows}
            self.accessed.append(key)
            return np.arange(15) * 1e-9

        def __iter__(self):
            raise AssertionError("Archive enumeration attempted")

    saved = NamedOnly()
    training, maps, accessed = diagnostic.load_maps(saved, rows + [PoisonHeldout()])
    assert len(training) == 60 and len(maps) == 9
    assert len(accessed) == len(set(accessed)) == 540
    assert accessed == saved.accessed


def test_closest_pair_interpolation_preserves_small_difference():
    rows = source.cases(source.condition_rule(source.protocol(), "sham"))
    values = {}
    for row in rows:
        value = np.zeros(15)
        value[0] = 0.03 + (row["amplitude"] - 0.4) * 1e-6
        value[1] = row["location"] * 4e-9
        values[row["world_id"]] = value
    group = dict(
        arm="joint", curve_labels=[[0, 0], [1, 1]], segments=[0, 0], coordinates=[0.25, 0.25]
    )
    delta = diagnostic.closest_delta(rows, values, group)
    expected = np.zeros(15)
    expected[1] = -4e-9
    np.testing.assert_array_equal(delta, expected)
    with pytest.raises(ValueError, match="segment"):
        diagnostic.closest_delta(rows, values, group | dict(coordinates=[-0.1, 0]))


def test_common_background_shift_is_not_a_cue_or_pair_improvement():
    rows = source.cases(source.condition_rule(source.protocol(), "sham"))
    original, changed, panels = {}, {}, {}
    background = np.arange(15) * 2.0**-10
    for panel in source.PANELS:
        groups = []
        for level in range(3):
            values = {}
            for row in rows:
                value = np.full(15, 1 / 32)
                if row["arm"] not in ("no_cue", "disconnected"):
                    value[0] += row["location"] * 2.0**-30
                    value[1] += row["timing"] * 2.0**-29
                values[row["world_id"]] = value
            original[level, panel] = dict(voltage=values)
            changed[level, panel] = dict(
                voltage={key: val + background for key, val in values.items()}
            )
            groups.append(
                dict(
                    level=level,
                    arm="joint",
                    task="location",
                    curve_labels=[[0, 1], [1, 0]],
                    segments=[0, 0],
                    coordinates=[0.25, 0],
                )
            )
        panels[panel] = dict(task_groups=groups)
    report = diagnostic.paired_changes(
        rows, changed, rows, original, dict(geometry=dict(panels=panels))
    )
    for levels in report.values():
        for level in levels:
            assert level["no_cue_change"]["distance_V"] > 0
            assert all(
                r["cue_relative_change_l2_V"] == 0 for r in level["calibration_case_effect_changes"]
            )
            assert level["same_sham_pair"]["squared_distance_change_V2"] == 0
            assert level["same_sham_pair"]["reconstruction_error_V2"] == 0


@pytest.mark.parametrize("value", [np.zeros(14), np.full(15, np.nan), np.full(15, np.inf)])
def test_bad_features_rejected(value):
    with pytest.raises(ValueError, match="Fifteen finite"):
        diagnostic.feature(value)
