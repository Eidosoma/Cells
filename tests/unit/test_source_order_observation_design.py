"""Geometry ground truths and strict calibration/evaluation isolation."""

import copy
import json

import numpy as np
import pytest

from validation.assays import source_order_observation_design as design
from validation.assays.template_readout import TemplateReader


@pytest.mark.parametrize(
    "points,expected",
    [
        ([[-1, 0], [1, 0], [0, -1], [0, 1]], 0),  # crossing interiors
        ([[0, 0], [2, 0], [1, 1], [3, 1]], 1),  # parallel overlapping projections
        ([[0, 0], [1, 0], [2, 0], [3, 0]], 1),  # parallel disjoint projections
        ([[-1, 0, 0], [1, 0, 0], [0, -1, 2], [0, 1, 2]], 2),  # skew
        ([[0, 0], [1, 0], [2, 1], [2, 2]], np.sqrt(2)),  # both endpoints
        ([[0, 0], [0, 0], [-1, 2], [1, 2]], 2),  # one point
        ([[0, 0], [0, 0], [3, 4], [3, 4]], 5),  # two points
        ([[0, 0], [0, 0], [0, 0], [0, 0]], 0),
        ([[0, 0], [1, 0], [1, -1], [1, 1]], 0),  # endpoint/interior contact
        ([[-1, 0], [1, 0], [-1, -1e-10], [1, 1e-10]], 0),  # almost parallel
    ],
)
def test_closed_segment_ground_truth_and_orientation(points, expected):
    points = np.asarray(points, dtype=float)
    for order in ([0, 1, 2, 3], [1, 0, 2, 3], [0, 1, 3, 2], [2, 3, 0, 1]):
        p0, p1, q0, q1 = points[order]
        result = design.segment_distance(p0, p1, q0, q1)
        assert result["distance_V"] == pytest.approx(expected, abs=2e-14)
        s, t = result["coordinates"]
        assert 0 <= s <= 1 and 0 <= t <= 1
        residual = (p0 - q0) + s * (p1 - p0) - t * (q1 - q0)
        assert np.linalg.norm(residual) == pytest.approx(result["distance_V"], abs=2e-14)


@pytest.mark.parametrize(
    "scale,offset",
    [
        (2.0**-30, [0.03125, -0.0625, 0.125]),  # nV contrasts on a voltage baseline
        (1e-100, [0, 0, 0]),
        (1e100, [0, 0, 0]),
        (3.5, [1024, 2048, -4096]),
    ],
)
def test_distance_preserves_metric_under_scale_offset_and_rotation(scale, offset):
    points = np.array([[-1, 0, 0], [1, 0, 0], [0, -1, 2], [0, 1, 2]])
    transformed = scale * points + offset
    answer = design.segment_distance(*transformed)
    assert answer["distance_V"] == pytest.approx(2 * scale, rel=2e-13, abs=0)
    np.testing.assert_allclose(answer["coordinates"], [0.5, 0.5], atol=2e-13)
    # An exact orthogonal permutation also changes axis orientation and sign.
    rotated = transformed[:, [2, 0, 1]] * [-1, 1, -1]
    other = design.segment_distance(*rotated)
    assert other["distance_V"] == pytest.approx(answer["distance_V"], rel=2e-13, abs=0)
    moved = transformed.copy()
    moved[2:, 2] += scale
    assert design.segment_distance(*moved)["distance_V"] == pytest.approx(
        3 * scale,
        rel=2e-13,
        abs=0,
    )


@pytest.mark.parametrize(
    "points",
    [
        [[0], [1], [np.nan], [1]],
        [[0], [1], [np.inf], [1]],
        [[], [], [], []],
        [0, 1, 2, 3],
    ],
)
def test_invalid_segment_input_is_rejected(points):
    with pytest.raises(ValueError):
        design.segment_distance(*points)


def test_opposite_label_separation_includes_interiors_not_just_vertices():
    reader = TemplateReader(
        [[[-1, 0], [1, 0], [2, 0]], [[0, -1], [0, 1], [0, 2]]],
        [[0], [1]],
        2e-9,
    )
    vertices_only = np.linalg.norm(
        reader.vertices[0, :, None] - reader.vertices[1, None, :],
        axis=-1,
    ).min()
    assert vertices_only > 1
    result = design.task_separation(reader, 0, [0.4, 0.6, 0.8])
    assert result["half_distance_V"] < 1e-14
    np.testing.assert_allclose(result["coordinates"], [0.5, 0.5], atol=1e-14)
    np.testing.assert_allclose(result["inferred_strengths"], [0.5, 0.5], atol=1e-14)


def test_opposite_label_comparison_includes_different_other_task_labels():
    reader = TemplateReader(
        [
            [[0, 0], [1, 0], [2, 0]],
            [[0, 100], [1, 100], [2, 100]],
            [[0, 101], [1, 101], [2, 101]],
            [[0, 2], [1, 2], [2, 2]],
        ],
        [[0, 0], [0, 1], [1, 0], [1, 1]],
        2e-9,
    )
    for task in (0, 1):
        result = design.task_separation(reader, task, [0.4, 0.6, 0.8])
        assert result["half_distance_V"] == pytest.approx(0.5)
        assert result["curve_labels"] == [[0, 1], [1, 0]]


def fixture_data():
    rule = design.assay.protocol()
    spec = json.loads(design.PLAN.read_text())["design"]
    rows = design.assay.cases(rule)
    saved = {}
    for level in range(3):
        for r in rows:
            if r["split"] != "calibration":
                continue
            for panel in ("middle128", "long256", "long512", "spanning512"):
                parts = []
                for time in rule["observation_times_us"][panel]:
                    # Analytic separable features, no simulation and no observed outcomes.
                    point = (
                        np.array(
                            [
                                r["amplitude"],
                                r["location"] * time * 1e-3,
                                r["timing"] * (600 - time) * 1e-3,
                                level,
                                0,
                            ]
                        )
                        * 1e-8
                    )
                    if r["arm"] in ("no_cue", "disconnected"):
                        point[:] = 0
                    parts.extend(point)
                saved[f"{level}__{panel}__voltage__{r['world_id']}"] = np.array(parts)
    return rule, spec, rows, saved


class NoHeldoutMetadata(dict):
    def __getitem__(self, key):
        if key != "split":
            raise AssertionError("Held-out metadata was read: " + key)
        return "heldout"


class CalibrationArraysOnly(dict):
    def __iter__(self):
        raise AssertionError("Archive keys must not be enumerated")

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if not isinstance(value, np.ndarray):
            raise AssertionError("Held-out array was read: " + key)
        return value


def test_heldout_changes_and_removal_leave_all_candidate_scores_unchanged():
    rule, spec, rows, saved = fixture_data()
    training = [r for r in rows if r["split"] == "calibration"]
    poisoned = CalibrationArraysOnly(saved)
    for row in rows:
        if row["split"] != "calibration":
            for panel in ("middle128", "long256", "long512", "spanning512"):
                for level in range(3):
                    poisoned[f"{level}__{panel}__voltage__{row['world_id']}"] = object()
    poisoned_rows = [r if r["split"] == "calibration" else NoHeldoutMetadata() for r in rows]
    outputs = []
    for records, arrays in ((rows, saved), (poisoned_rows, poisoned), (training, saved)):
        selected, observations, accessed = design.load_calibration(arrays, records, rule, spec)
        outputs.append(design.rank_schedules(records, observations, rule, spec))
        assert len(selected) == 60
        assert len(accessed) == 720 == len(set(accessed))
        assert all(
            int(key.split("__")[-1]) in {r["world_id"] for r in training} for key in accessed
        )
    assert outputs[0] == outputs[1] == outputs[2]
    result = outputs[0]
    assert len(result["candidates"]) == 35
    for candidate in result["candidates"]:
        assert candidate["feature_count"] == 15
        assert len(candidate["task_groups"]) == 12
        assert {r["arm"] for r in candidate["task_groups"]} == {
            "location_only",
            "timing_only",
            "joint",
        }
        assert candidate["score_V"] == min(r["half_distance_V"] for r in candidate["task_groups"])
        assert candidate["score_V"] > 0  # Zero-distance nulls must not cap the objective.
        assert len(candidate["calibration_null_controls"]) == 6
        assert all(
            value["resolved_cases"] == 0
            for r in candidate["calibration_null_controls"]
            for value in r["tasks"].values()
        )
    assert design.backend_comparison(result, copy.deepcopy(result)) == dict(
        winners_agree=True,
        maximum_candidate_score_difference_V=0.0,
        selected_times_us=result["selection"]["times_us"],
        reproducible_improvement=result["improvement_over_incumbent_V"] > design.TIE_ATOL_V,
    )


def test_archived_time_cell_identity_and_incumbent_are_exact():
    rule, spec, rows, saved = fixture_data()
    for key, value in saved.items():
        panel = key.split("__")[1]
        value[:] = [
            t * 100 + cell for t in rule["observation_times_us"][panel] for cell in (2, 3, 5, 6, 7)
        ]
    _, observations, _ = design.load_calibration(saved, rows, rule, spec)
    expected = [[t * 100 + cell for cell in (2, 3, 5, 6, 7)] for t in design.TIME_SLICES]
    for value in observations.values():
        np.testing.assert_array_equal(value, expected)
        assert not value.flags.writeable


@pytest.mark.parametrize(
    "corruption",
    [
        "cell",
        "time",
        "width",
        "nonfinite",
        "incumbent",
        "duplicate",
        "missing",
        "margin",
    ],
)
def test_changed_support_or_calibration_is_rejected(corruption):
    rule, spec, rows, saved = fixture_data()
    first = next(iter(saved))
    if corruption == "cell":
        rule["readout"]["cell_ids"][0] = 1
    elif corruption == "time":
        rule["observation_times_us"]["middle128"][-1] = 112
    elif corruption == "width":
        saved[first] = np.zeros(21)
    elif corruption == "nonfinite":
        saved[first][0] = np.nan
    elif corruption == "incumbent":
        saved[first.replace("middle128", "spanning512")][0] += 1
    elif corruption == "duplicate":
        rows.append(rows[0])
    elif corruption == "missing":
        rows.pop(0)
    else:
        rule["reader"]["voltage_margin_V"] = 1e-9
    with pytest.raises(ValueError):
        design.load_calibration(saved, rows, rule, spec)


def test_ties_prefer_incumbent_then_lexicographic_schedule_with_fixed_tolerance():
    incumbent = [128, 256, 512]
    candidates = [
        dict(times_us=[160, 192, 256], score_V=4e-9),
        dict(times_us=incumbent, score_V=4e-9 - 0.5e-15),
        dict(times_us=[128, 160, 192], score_V=4e-9 - 0.25e-15),
    ]
    assert design.choose(candidates, incumbent)["times_us"] == incumbent
    candidates[1]["score_V"] -= 1e-15
    assert design.choose(candidates, incumbent)["times_us"] == [128, 160, 192]
    candidates[2]["score_V"] -= 1e-15
    assert design.choose(candidates, incumbent)["times_us"] == [160, 192, 256]


def test_backend_disagreement_is_recorded_without_claiming_reproducible_improvement():
    candidates = [
        dict(times_us=[128, 160, 192], score_V=4e-9),
        dict(times_us=[160, 192, 256], score_V=4e-9 + 2e-15),
    ]
    cpu = dict(
        candidates=candidates,
        selection=design.choose(candidates, [128, 256, 512]),
        improvement_over_incumbent_V=1e-9,
    )
    gpu = copy.deepcopy(cpu)
    gpu["candidates"][0]["score_V"] += 4e-15
    gpu["selection"] = design.choose(gpu["candidates"], [128, 256, 512])
    comparison = design.backend_comparison(cpu, gpu)
    assert not comparison["winners_agree"]
    assert not comparison["reproducible_improvement"]
    assert comparison["selected_times_us"] is None
    assert comparison["maximum_candidate_score_difference_V"] == pytest.approx(4e-15, abs=1e-24)
