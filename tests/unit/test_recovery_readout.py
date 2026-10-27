"""Recovery observations must not mistake quiet controls or brief reentry for repair."""

from copy import deepcopy

import numpy as np
import pytest

from cells.assays.recovery import sampled_recovery


def inputs():
    times = np.arange(7, dtype=float)
    return dict(
        times=times,
        actual={"voltage_V": np.array([0, 2, 2, 0, 0, 0, 0], dtype=float)},
        reference={"voltage_V": np.zeros(7)},
        bands={"voltage_V": 1.0},
        uncertainty={"voltage_V": 0.1},
        intervention_s=1.0,
        release_s=2.0,
        hold_s=3.0,
        max_gap_s=1.0,
    )


def test_sampled_return_requires_resolved_departure_and_final_hold():
    data = inputs()
    result = sampled_recovery(**data)
    assert result["classification"] == "returned_with_hold"
    assert result["final_hold_start_s"] == 3.0 and result["sampled_hold_s"] == 3.0
    data["actual"]["voltage_V"][:] = 0
    result = sampled_recovery(**data)
    assert result["classification"] == "no_resolved_departure"
    assert not result["returned_with_hold"]


@pytest.mark.parametrize(
    "values,label",
    [
        ([0, 2, 2, 0, 0, 2, 0], "insufficient_hold"),
        ([0, 2, 2, 0, 0, 0, 2], "outside_at_end"),
        ([0, 2, 2, 0, 0, 0, 1], "unresolved_boundary"),
        ([0, 1, 0, 0, 0, 0, 0], "unresolved_departure"),
    ],
)
def test_reentry_excursion_and_boundary_uncertainty(values, label):
    data = inputs()
    data["actual"]["voltage_V"] = values
    assert sampled_recovery(**data)["classification"] == label


def test_return_must_be_simultaneous_for_voltage_and_ions():
    data = inputs()
    data["actual"]["ions_mM"] = np.array([0, 2, 2, 0, 2, 0, 0], dtype=float)[:, None]
    data["reference"]["ions_mM"] = np.zeros((7, 1))
    data["bands"]["ions_mM"], data["uncertainty"]["ions_mM"] = 1.0, 0.1
    report = sampled_recovery(**data)
    assert report["metrics"]["voltage_V"]["returned_with_hold"]
    assert report["classification"] == "insufficient_hold"
    assert report["final_hold_start_s"] == 5.0


def test_return_is_relative_to_matched_drifting_reference_and_after_release():
    data = inputs()
    data["actual"]["voltage_V"] += data["times"] * 3
    data["reference"]["voltage_V"] += data["times"] * 3
    data["release_s"] = 4.0
    before = deepcopy(data)
    result = sampled_recovery(**data)
    assert result["classification"] == "insufficient_hold"
    assert result["final_hold_start_s"] == 4.0
    assert result["metrics"]["voltage_V"]["reference_drift_from_initial"] == 18.0
    np.testing.assert_array_equal(data["actual"]["voltage_V"], before["actual"]["voltage_V"])


def test_off_grid_release_does_not_credit_unobserved_hold_time():
    data = inputs()
    data.update(intervention_s=1.2, release_s=3.2, hold_s=2.5)
    result = sampled_recovery(**data)
    assert result["first_resolved_departure_s"] == 2.0
    assert result["first_sample_at_or_after_intervention_s"] == 2.0
    assert result["first_sample_at_or_after_release_s"] == 4.0
    assert result["final_hold_start_s"] == 4.0
    assert result["sampled_hold_s"] == 2.0
    assert result["classification"] == "insufficient_hold"


@pytest.mark.parametrize(
    "fault",
    ["nan", "shape", "empty", "keys", "band", "uncertainty", "time", "gap", "release", "hold"],
)
def test_invalid_or_insufficient_observation_contracts_reject(fault):
    data = inputs()
    if fault == "nan":
        data["actual"]["voltage_V"][2] = np.nan
    elif fault == "shape":
        data["reference"]["voltage_V"] = np.zeros((7, 1))
    elif fault == "empty":
        data["actual"], data["reference"], data["bands"], data["uncertainty"] = {}, {}, {}, {}
    elif fault == "keys":
        data["bands"]["unknown"] = 1.0
    elif fault == "band":
        data["bands"]["voltage_V"] = -1.0
    elif fault == "uncertainty":
        data["uncertainty"]["voltage_V"] = 1.0
    elif fault == "time":
        data["times"][3] = data["times"][2]
    elif fault == "gap":
        data["times"][-1] = 8.0
    elif fault == "release":
        data["release_s"] = 7.0
    elif fault == "hold":
        data["hold_s"] = 0.0
    with pytest.raises(ValueError):
        sampled_recovery(**data)
