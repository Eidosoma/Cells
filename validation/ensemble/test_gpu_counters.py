"""Counter semantics: interval alignment, missing data and incompatible domains."""

import pytest

from validation.ensemble import gpu_counters as counters


def sample(timestamp, reading, **changes):
    return {
        "type": "sample",
        "fields": {
            str(field): {
                "timestamp_usec": int(timestamp * 1e6),
                "status": 0,
                "field_type": ord("d"),
                "value": reading,
                **changes,
            }
            for field in counters.FIELDS
        },
    }


def test_interval_ending_counters_are_time_weighted_and_clipped():
    rows = [
        {"type": "started", "fields": {str(k): v for k, v in counters.FIELDS.items()}},
        sample(1, 0.9),
        sample(2, 0.2),
        sample(3, 0.8),
        {"type": "finished"},
    ]
    report = counters.summarize(rows, 1.5, 3)
    assert report["coverage_pass"]
    for row in report["fields"].values():
        assert row["mean_pct_over_covered_time"] == pytest.approx(60)
        assert row["max_interval_pct"] == 80
        assert row["covered_seconds"] == 1.5
        assert row["valid_intervals"] == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"status": -1},
        {"value": None},
        {"value": float("nan")},
        {"value": float("inf")},
        {"value": 140737488355328.0},
        {"value": -0.1},
        {"value": 1.01},
        {"field_type": ord("i")},
    ],
)
def test_blank_and_invalid_counters_are_not_zero_activity(changes):
    report = counters.summarize([sample(1, 0.2), sample(2, 0.2, **changes), sample(3, 0.8)], 1, 3)
    assert not report["coverage_pass"]
    for row in report["fields"].values():
        assert row["mean_pct_over_covered_time"] == 80
        assert row["coverage_fraction"] == 0.5
        assert row["invalid_samples"] == 1


def test_stale_duplicates_and_missing_intervals_are_not_extended():
    report = counters.summarize([sample(1, 0), sample(2, 0.5), sample(2, 0.5), sample(5, 1)], 1, 5)
    for row in report["fields"].values():
        assert row["coverage_fraction"] == 0.25
        assert row["mean_pct_over_covered_time"] == 50
        assert row["duplicate_samples"] == 1


def test_zero_activity_is_valid_but_missing_counter_is_not():
    first, second = sample(1, 0), sample(2, 0)
    del second["fields"]["1003"]
    report = counters.summarize([first, second], 1, 2)
    assert report["fields"]["sm_active"]["mean_pct_over_covered_time"] == 0
    assert report["fields"]["sm_active"]["coverage_pass"]
    assert report["fields"]["sm_occupancy"]["mean_pct_over_covered_time"] is None
    assert not report["coverage_pass"]


def test_backwards_timestamps_are_rejected():
    with pytest.raises(ValueError, match="backwards"):
        counters.summarize([sample(3, 0.2), sample(2, 0.4)], 1, 4)


def test_zero_timestamp_is_unavailable_and_does_not_extend_coverage():
    report = counters.summarize([sample(1, 0.5), sample(0, 0), sample(3, 0.5)], 1, 3)
    assert report["fields"]["sm_active"]["mean_pct_over_covered_time"] is None


def test_counter_selection_avoids_multiplexing_with_alternative_groups():
    groups = [
        {"major": 0, "minor": 1, "fields": [1002]},
        {"major": 0, "minor": 2, "fields": [1002, 1003]},
        {"major": 1, "minor": 0, "fields": [1005]},
    ]
    assert counters.compatible_groups(groups, [1002, 1003, 1005]) == [(0, 2), (1, 0)]


@pytest.mark.parametrize("wanted", [[1002, 1003], [9999]])
def test_unsupported_or_multiplexed_counters_are_rejected(wanted):
    groups = [
        {"major": 0, "minor": 1, "fields": [1002]},
        {"major": 0, "minor": 2, "fields": [1003]},
    ]
    with pytest.raises(ValueError, match="unsupported or multiplexed"):
        counters.compatible_groups(groups, wanted)
