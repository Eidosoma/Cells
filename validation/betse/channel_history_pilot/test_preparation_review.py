"""Bounded saved-data review tests; no simulator or numerical-library imports."""

import copy
import importlib
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
review = importlib.import_module("preparation_review")


@pytest.fixture(scope="module")
def saved():
    return (
        review.c.read(review.CAPTURE / "registration.json"),
        review.c.read(review.CAPTURE / "cells.json"),
    )


def test_alternate_rates_and_every_layout_link(saved):
    result = review.independent_checks(*saved)
    assert result["failed_comparisons"] == 0
    assert result["full_layout_arrays"] == 528


@pytest.mark.parametrize(
    "field",
    [
        "gate",
        "amount_increment",
        "channel_transferred",
        "extracellular_amount_increment",
        "dissipated_energy_pJ",
    ],
)
def test_changed_rhs_bytes_are_rejected(saved, field):
    r, original = saved
    cells = copy.deepcopy(original)
    cells["rows"]["active_channel/a/numpy"]["rhs"][field]["bytes_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        review.independent_checks(r, cells)


@pytest.mark.parametrize(
    "field",
    [
        "owners",
        "channel_membranes",
        "outside_owners",
        "amount_reference",
        "initial_countercharge_C",
    ],
)
def test_common_layout_corruption_cannot_hide_behind_pair_equality(saved, field):
    r, original = saved
    cells = copy.deepcopy(original)
    for row in cells["rows"].values():
        row["layout_sha256"][field] = "0" * 64
    with pytest.raises(ValueError, match="layout"):
        review.independent_checks(r, cells)


def test_numeric_checkpoint_digest_rejects_unsafe_dtype():
    with pytest.raises(ValueError):
        review.numeric_digest({"dtype": "object", "values": [0]})
