"""Transcription-site readers: explicit denominators, named ratios and per-copy detection.

Pure NumPy and SciPy; no world is compiled. The per-copy expectations are checked against
probabilities summed directly with the math module.
"""

import math

import numpy as np
import pytest

from cells.assays.transcription_sites import (
    IncompleteObservation,
    called_sites_from_counts,
    expected_called_sites,
    summarize_called_sites,
    two_channel_ratios,
)

# The requester's spot example: three spots of 10, one of 50 and a confirmed zero-site cell.
ROSTER = [("s1", "c1", 3), ("s1", "c2", 1), ("s1", "c3", 0)]
SPOTS = [("s1", "c1", f"p{i}", 10) for i in range(3)] + [("s1", "c2", "p0", 50)]
MEANS, COPIES = [0.0, 0.2, 5.0, 12.0], [1, 4, 2, 0.5]


def _plain(value):
    """Only int, finite float, str and None, inside dicts and tuples: no NumPy scalar, no NaN."""
    if isinstance(value, dict):
        return all(_plain(v) for v in value.values())
    if isinstance(value, tuple):
        return all(_plain(v) for v in value)
    return type(value) in (int, str, type(None)) or (type(value) is float and math.isfinite(value))


def test_spot_averaging_example_keeps_ids_and_the_zero_site_cell():
    record = summarize_called_sites(ROSTER, SPOTS)["s1"]
    assert record["mean_brightness_per_called_site"] == 20
    assert record["mean_of_positive_cell_mean_brightness"] == 30
    assert record["called_signal_per_roster_cell"] == 80 / 3
    counts = ("roster_cells", "positive_cells", "zero_site_cells", "called_sites")
    assert [record[key] for key in counts] == [3, 2, 1, 4]
    assert record["called_sites_per_roster_cell"] == 4 / 3
    assert record["sample"] == "s1" and record["undefined"] == {}
    assert [cell["spot_ids"] for cell in record["cells"]] == [("p0", "p1", "p2"), ("p0",), ()]
    assert record["cells"][2] == dict(
        cell="c3", called_sites=0, spot_ids=(), called_signal=0.0, mean_brightness=None
    )
    assert _plain(record)


def test_two_channel_example_names_each_statistic():
    result = two_channel_ratios(["a", "b"], {"a": 2, "b": 6}, {"a": 1, "b": 9})
    assert result["ratio_of_pooled_means"] == 0.8
    assert result["mean_of_within_cell_ratios"] == 4 / 3
    assert round(result["mean_of_within_cell_ratios"], 4) == 1.3333
    assert (result["numerator_mean"], result["denominator_mean"]) == (4.0, 5.0)
    assert result["undefined"] == {} and _plain(result)


def test_samples_stay_separate_and_row_order_does_not_matter():
    # s2 reuses s1's cell and spot IDs and has a negative background-corrected spot;
    # sample 0 holds only confirmed zero-site cells.
    roster = ROSTER + [("s2", "c1", 1), ("s2", "c9", 2), (0, 7, 0), (0, 8, 0)]
    spots = SPOTS + [("s2", "c1", "p0", -2.5), ("s2", "c9", "p0", 4), ("s2", "c9", "p1", 1)]
    result = summarize_called_sites(roster, spots)
    assert list(result) == [0, "s1", "s2"]
    assert result["s1"] == summarize_called_sites(ROSTER, SPOTS)["s1"]
    other = result["s2"]
    assert other["mean_brightness_per_called_site"] == 2.5 / 3
    assert other["called_signal_per_roster_cell"] == 1.25
    assert other["mean_of_positive_cell_mean_brightness"] == 0.0
    empty = result[0]
    assert empty["roster_cells"] == 2 and empty["called_signal_per_roster_cell"] == 0.0
    assert empty["mean_brightness_per_called_site"] is None
    assert empty["mean_of_positive_cell_mean_brightness"] is None
    assert set(empty["undefined"]) == {
        "mean_brightness_per_called_site",
        "mean_of_positive_cell_mean_brightness",
    }
    assert summarize_called_sites(roster[::-1], spots[::-1]) == result
    assert _plain(result[0]) and _plain(other)
    # NumPy-typed tables, as real tables often arrive, give the same plain record.
    i = np.int64
    typed = summarize_called_sites([(i(0), i(7), i(1))], [(i(0), i(7), i(3), np.float64(2.5))])
    assert typed == summarize_called_sites([(0, 7, 1)], [(0, 7, 3, 2.5)]) and _plain(typed[0])


@pytest.mark.parametrize(
    "roster,spots,issues",
    [
        (ROSTER, SPOTS + [("s1", "c4", "p0", 5)], [("unmatched_spot", "s1", "c4", "p0")]),
        (ROSTER, SPOTS + [("s9", "c1", "p0", 5)], [("unmatched_spot", "s9", "c1", "p0")]),
        (ROSTER + [("s1", "c3", 0)], SPOTS, [("duplicated_cell", "s1", "c3")]),
        (ROSTER, SPOTS + [("s1", "c2", "p0", 50)], [("duplicated_spot", "s1", "c2", "p0")]),
        (ROSTER, SPOTS[:3] + [("s1", "c2", "p0", None)], [("unmeasured_spot", "s1", "c2", "p0")]),
        (ROSTER, SPOTS[1:], [("count_mismatch", "s1", "c1", 3, 2)]),
        (ROSTER, SPOTS + [("s1", "c3", "p0", 7)], [("count_mismatch", "s1", "c3", 0, 1)]),
    ],
    ids=[
        "unrostered-cell",
        "unrostered-sample",
        "duplicated-cell",
        "duplicated-spot",
        "unmeasured-spot",
        "counted-site-without-spot",
        "spot-beyond-count",
    ],
)
def test_incomplete_tables_are_refused_naming_the_offending_ids(roster, spots, issues):
    with pytest.raises(IncompleteObservation) as caught:
        summarize_called_sites(roster, spots)
    assert [tuple(issue.values()) for issue in caught.value.issues] == issues


def test_one_incomplete_sample_refuses_the_whole_call_listing_every_issue():
    roster = ROSTER + [("s2", "c1", 2)]
    spots = SPOTS + [("s2", "c1", "p0", None), ("s2", "c5", "p0", 3)]
    with pytest.raises(IncompleteObservation) as caught:
        summarize_called_sites(roster, spots)
    kinds = [issue["kind"] for issue in caught.value.issues]
    assert kinds == ["unmeasured_spot", "unmatched_spot", "count_mismatch"]
    assert caught.value.issues[2] == dict(
        kind="count_mismatch", sample="s2", cell="c1", declared_sites=2, spot_records=1
    )
    assert "cell='c5'" in str(caught.value)


@pytest.mark.parametrize(
    "roster,spots",
    [
        ([("s1", "c1", True)], []),
        ([("s1", "c1", -1)], []),
        ([("s1", "c1", 1.0)], [("s1", "c1", "p0", 5)]),
        ([("s1", "", 0)], []),
        ([(" ", "c1", 0)], []),
        ([(True, "c1", 0)], []),
        ([(1.5, "c1", 0)], []),
        ([(None, "c1", 0)], []),
        ([("s1", "c1")], []),
        ([], []),
        (ROSTER, SPOTS[:3] + [("s1", "c2", "p0", math.nan)]),
        (ROSTER, SPOTS[:3] + [("s1", "c2", "p0", math.inf)]),
        (ROSTER, SPOTS[:3] + [("s1", "c2", "p0", True)]),
        (ROSTER, SPOTS[:3] + [("s1", "c2", "p0", "50")]),
        (ROSTER, SPOTS[:3] + [("s1", "c2", 50)]),
        (ROSTER, SPOTS[:3] + [("s1", "c2", np.bool_(True), 50)]),
    ],
)
def test_malformed_tables_are_invalid_not_incomplete(roster, spots):
    with pytest.raises(ValueError) as caught:
        summarize_called_sites(roster, spots)
    assert not isinstance(caught.value, IncompleteObservation)


def test_two_channel_statistics_without_a_positive_denominator_are_none_with_a_reason():
    cells, top = [3, 1, 2], {1: 2.0, 2: -1.0, 3: 4.0}
    zero = two_channel_ratios(cells, top, {1: 1.0, 2: 0.0, 3: 3.0})
    assert zero["ratio_of_pooled_means"] == 5 / 4 and zero["mean_of_within_cell_ratios"] is None
    assert zero["undefined"] == {
        "mean_of_within_cell_ratios": "1 cell(s) have a nonpositive denominator signal: (2,)"
    }
    assert zero["cell_ids"] == (1, 2, 3) and zero["cells_with_positive_denominator"] == 2
    negative = two_channel_ratios(cells, top, {1: 1.0, 2: -5.0, 3: 3.0})
    assert negative["ratio_of_pooled_means"] is None
    assert set(negative["undefined"]) == {"ratio_of_pooled_means", "mean_of_within_cell_ratios"}
    signed = two_channel_ratios(cells, top, {1: 1.0, 2: 4.0, 3: 3.0})
    assert signed["mean_of_within_cell_ratios"] == pytest.approx((2 - 1 / 4 + 4 / 3) / 3)
    assert signed["ratio_of_pooled_means"] == 5 / 8


@pytest.mark.parametrize(
    "top,bottom,issues",
    [
        ({"a": 2}, {"a": 1, "b": 9}, [("missing_signal", "numerator", "b")]),
        ({"a": 2, "b": 6, "z": 1}, {"a": 1, "b": 9}, [("unrostered_signal", "numerator", "z")]),
        ({"a": 2, "b": 6}, {"a": None, "b": 9}, [("unmeasured_signal", "denominator", "a")]),
    ],
)
def test_channels_must_cover_exactly_the_roster(top, bottom, issues):
    with pytest.raises(IncompleteObservation) as caught:
        two_channel_ratios(["a", "b"], top, bottom)
    assert [tuple(issue.values()) for issue in caught.value.issues] == issues


@pytest.mark.parametrize(
    "cells,top,bottom",
    [
        (["a", "a"], {"a": 1}, {"a": 1}),
        ([], {}, {}),
        (["a"], {"a": math.nan}, {"a": 1}),
        (["a"], {"a": 1}, {"a": False}),
        (["a"], [("a", 1)], {"a": 1}),
    ],
)
def test_malformed_channels_are_invalid_not_incomplete(cells, top, bottom):
    with pytest.raises(ValueError) as caught:
        two_channel_ratios(cells, top, bottom)
    assert not isinstance(caught.value, IncompleteObservation)


def _poisson(mean, size=400):
    if not mean:
        return [1.0] + [0.0] * (size - 1)
    return [math.exp(n * math.log(mean) - mean - math.lgamma(n + 1)) for n in range(size)]


def _negative_binomial(mean, fano, size=400):
    if not mean:
        return [1.0] + [0.0] * (size - 1)
    shape, success = mean / (fano - 1), 1 / fano
    return [
        math.exp(
            math.lgamma(n + shape)
            - math.lgamma(shape)
            - math.lgamma(n + 1)
            + shape * math.log(success)
            + n * math.log1p(-success)
        )
        for n in range(size)
    ]


@pytest.mark.parametrize("threshold", [1, 2, 3, 6])
@pytest.mark.parametrize("fano", [None, 1.5, 4.0])
def test_per_copy_threshold_matches_directly_summed_probabilities(threshold, fano):
    family = "poisson" if fano is None else "negative_binomial"
    record = expected_called_sites(
        MEANS, COPIES, threshold=threshold, distribution=family, fano_factor=fano
    )
    pmfs = [_poisson(m) if fano is None else _negative_binomial(m, fano) for m in MEANS]
    pairs = list(zip(COPIES, pmfs, strict=True))
    called = math.fsum(w * math.fsum(p[threshold:]) for w, p in pairs)
    visible = math.fsum(w * math.fsum(n * p[n] for n in range(threshold, len(p))) for w, p in pairs)
    assert record["called_sites_per_cell"] == pytest.approx(called, rel=1e-11)
    assert record["visible_chains_per_cell"] == pytest.approx(visible, rel=1e-11)
    assert record["chains_per_called_site"] == pytest.approx(visible / called, rel=1e-11)
    assert record["all_chains_per_cell"] == pytest.approx(16.8)
    assert (record["distribution"], record["threshold"]) == (family, threshold)
    assert record["parameters"] == ({} if fano is None else {"fano_factor": fano})
    assert len(record["assumptions"]) == 2 and _plain(record)


def test_negative_binomial_tends_to_poisson_as_the_fano_factor_tends_to_one():
    poisson = expected_called_sites(MEANS, COPIES, threshold=3, distribution="poisson")
    near = expected_called_sites(
        np.array(MEANS),
        np.array(COPIES),
        threshold=np.int64(3),
        distribution="negative_binomial",
        fano_factor=np.float64(1 + 1e-9),
    )
    for key in ("called_sites_per_cell", "visible_chains_per_cell"):
        assert near[key] == pytest.approx(poisson[key], rel=1e-7)
    assert _plain(near)


def test_thresholding_a_copy_average_is_not_per_copy_detection():
    # One silent and one busy copy per cell. Pooled as two copies of mean 1.5 they carry the
    # same chains but give more calls; thresholding the mean itself would call none at all.
    per_copy = expected_called_sites([0.0, 3.0], [1, 1], threshold=2, distribution="poisson")
    pooled = expected_called_sites([1.5], [2], threshold=2, distribution="poisson")
    assert per_copy["all_chains_per_cell"] == pooled["all_chains_per_cell"] == 3.0
    assert per_copy["called_sites_per_cell"] == pytest.approx(1 - 4 * math.exp(-3), rel=1e-14)
    assert pooled["called_sites_per_cell"] == pytest.approx(2 - 5 * math.exp(-1.5), rel=1e-14)
    assert pooled["called_sites_per_cell"] - per_copy["called_sites_per_cell"] > 0.08


def test_supplied_counts_use_their_own_distribution():
    record = called_sites_from_counts([[0, 1, 2, 3], np.array([5])], [2, 1], threshold=2)
    assert record["called_sites_per_cell"] == 2.0
    assert record["visible_chains_per_cell"] == 7.5
    assert record["chains_per_called_site"] == 3.75
    assert record["all_chains_per_cell"] == 8.0
    assert record["parameters"] == dict(
        draws_per_copy_class=(4, 1), called_draws_per_copy_class=(2, 1)
    )
    assert record["distribution"] == "supplied_counts" and _plain(record)
    # Seeded draws from a Poisson count agree with the Poisson family.
    rng = np.random.default_rng(38)
    draws = [rng.poisson(mean, 100_000) for mean in (0.5, 2.0)]
    empirical = called_sites_from_counts(draws, [2, 1], threshold=2)
    family = expected_called_sites([0.5, 2.0], [2, 1], threshold=2, distribution="poisson")
    for key in ("called_sites_per_cell", "visible_chains_per_cell"):
        assert empirical[key] == pytest.approx(family[key], rel=0.02)


def test_no_called_site_leaves_the_conditional_none_never_nan():
    for record in (
        expected_called_sites([0.0, 0.0], [2, 1], threshold=1, distribution="poisson"),
        expected_called_sites(
            [0.0], [2], threshold=2, distribution="negative_binomial", fano_factor=3
        ),
        called_sites_from_counts([[0, 1, 1]], [2], threshold=2),
    ):
        assert record["chains_per_called_site"] is None
        assert record["called_sites_per_cell"] == 0.0
        assert set(record["undefined"]) == {"chains_per_called_site"} and _plain(record)


@pytest.mark.parametrize(
    "change",
    [
        dict(threshold=0),
        dict(threshold=True),
        dict(threshold=2.0),
        dict(distribution="gaussian"),
        dict(distribution=None),
        dict(fano_factor=2.0),
        dict(distribution="negative_binomial"),
        dict(distribution="negative_binomial", fano_factor=1.0),
        dict(distribution="negative_binomial", fano_factor=math.nan),
        dict(distribution="negative_binomial", fano_factor=True),
        dict(means=[-0.1, 1.0]),
        dict(means=[math.nan, 1.0]),
        dict(means=[True, 1.0]),
        dict(means=[None, 1.0]),
        dict(means=["1", 1.0]),
        dict(means=np.ones((1, 2))),
        dict(means=[]),
        dict(copies=[1.0]),
    ],
)
def test_expected_sites_refuse_an_unnamed_family_or_invalid_input(change):
    call = dict(means=[1.0, 2.0], copies=[2, 1], threshold=2, distribution="poisson") | change
    with pytest.raises(ValueError):
        expected_called_sites(call.pop("means"), call.pop("copies"), **call)


def test_the_copy_distribution_has_no_default():
    with pytest.raises(TypeError):
        expected_called_sites(np.array([1.0, 2.0]), np.array([2, 1]), threshold=2)


@pytest.mark.parametrize(
    "counts,copies",
    [
        ([[0, 1.0]], [1]),
        ([np.array([0.0, 2.0])], [1]),
        ([[True, 2]], [1]),
        ([[-1, 2]], [1]),
        ([[]], [1]),
        ([0, 1, 2], [1]),
        ([[1], [2]], [1]),
        ("12", [1]),
    ],
)
def test_supplied_counts_refuse_anything_but_whole_counts_per_class(counts, copies):
    with pytest.raises(ValueError):
        called_sites_from_counts(counts, copies, threshold=1)
