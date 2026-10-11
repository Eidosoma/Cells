"""BIO-002 arithmetic and data separation; no biological acceptance threshold."""

import copy
import csv
import hashlib
import json
import math
import shutil
from dataclasses import FrozenInstanceError, replace
from xml.etree import ElementTree

import pytest

from scripts import evaluate_conditioned_voltage as driver
from tests import reference_conditioned_voltage as ref

TEMPERATURE = 298.15
DOMAIN = (5.0, 65.0)


def synthetic_pair(a=0.3, b=0.004, bound=1.0):
    curve = ref.Curve(a, b, TEMPERATURE, DOMAIN)
    return tuple(
        ref.Reading(identity, dose, curve.voltage_at(dose), bound)
        for identity, dose in (("fit_one", 10.0), ("fit_two", 35.0))
    )


@pytest.fixture(scope="module")
def analysis():
    return driver.build_analysis()


@pytest.mark.parametrize("a,b", [(0.3, 0.004), (1.0, -0.005), (0.5, 0.0)])
def test_synthetic_curve_recovery_without_slope_sign_filter(a, b):
    first, second = synthetic_pair(a, b)
    curve = ref.fit_two_points(first, second, TEMPERATURE, DOMAIN)
    assert curve.a_dimensionless == pytest.approx(a, abs=1e-15)
    assert curve.b_per_mM == pytest.approx(b, abs=1e-15)
    expected = ref.thermal_voltage_mV(TEMPERATURE) * math.log(a + b * 60)
    assert curve.voltage_at(60) == pytest.approx(expected, abs=1e-12)


def test_temperature_and_millivolt_units():
    assert ref.thermal_voltage_mV(TEMPERATURE) == pytest.approx(25.692579121, abs=1e-9)
    assert ref.thermal_voltage_mV(2 * TEMPERATURE) == 2 * ref.thermal_voltage_mV(TEMPERATURE)


@pytest.mark.parametrize("temperature", [0, -1, True, "298.15", math.nan, math.inf])
def test_invalid_temperature(temperature):
    with pytest.raises(ValueError):
        ref.thermal_voltage_mV(temperature)


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity", " "),
        ("potassium_mM", -1),
        ("voltage_mV", math.nan),
        ("voltage_mV", True),
        ("reading_bound_mV", -1),
        ("reading_bound_mV", math.inf),
    ],
)
def test_invalid_reading(field, value):
    first, _ = synthetic_pair()
    with pytest.raises(ValueError):
        replace(first, **{field: value})


@pytest.mark.parametrize("domain", [(5.0, 5.0), (65.0, 5.0), (-1.0, 65.0), [5.0, 65.0]])
def test_invalid_or_mutable_domain(domain):
    with pytest.raises(ValueError):
        ref.Curve(1.0, 0.0, TEMPERATURE, domain)


@pytest.mark.parametrize("a,b", [(0.0, 0.0), (1.0, -0.1), (math.inf, 0.0)])
def test_invalid_curve_is_not_clipped(a, b):
    with pytest.raises(ValueError):
        ref.Curve(a, b, TEMPERATURE, DOMAIN)


def test_query_and_fit_doses_must_be_in_domain():
    first, second = synthetic_pair()
    curve = ref.fit_two_points(first, second, TEMPERATURE, DOMAIN)
    with pytest.raises(ValueError, match="outside declared domain"):
        curve.voltage_at(DOMAIN[1] + 1)
    with pytest.raises(ValueError, match="outside declared domain"):
        ref.fit_two_points(first, second, TEMPERATURE, (20.0, 65.0))


@pytest.mark.parametrize("kind", ["same_id", "same_dose", "reversed"])
def test_fit_requires_distinct_increasing_readings(kind):
    first, second = synthetic_pair()
    if kind == "same_id":
        second = replace(second, identity=first.identity)
    elif kind == "same_dose":
        second = replace(second, potassium_mM=first.potassium_mM)
    else:
        first, second = second, first
    with pytest.raises(ValueError, match="distinct, increasing-dose"):
        ref.fit_two_points(first, second, TEMPERATURE, DOMAIN)


@pytest.mark.parametrize("voltage", [-1e6, 1e6])
def test_fitting_exponent_underflow_or_overflow_refused(voltage):
    first, second = synthetic_pair()
    with pytest.raises(ValueError, match="exponent outside"):
        ref.fit_two_points(replace(first, voltage_mV=voltage), second, TEMPERATURE, DOMAIN)


def test_one_invalid_reading_corner_refuses_whole_analysis():
    first = ref.Reading("one", 1.0, 0.0, 20.0)
    second = ref.Reading("two", 2.0, 0.0, 20.0)
    assert ref.fit_two_points(first, second, TEMPERATURE, (1.0, 3.0)).voltage_at(3.0) == 0
    with pytest.raises(ValueError, match="logarithm argument"):
        ref.forecast(first, second, 3.0, TEMPERATURE, (1.0, 3.0))


def test_fit_and_forecast_do_not_mutate_inputs():
    first, second = synthetic_pair()
    before = copy.deepcopy((first, second))
    curve = ref.fit_two_points(first, second, TEMPERATURE, DOMAIN)
    ref.forecast(first, second, 60.0, TEMPERATURE, DOMAIN)
    assert (first, second) == before
    with pytest.raises(FrozenInstanceError):
        first.voltage_mV = 0.0
    with pytest.raises(FrozenInstanceError):
        curve.a_dimensionless = 0.0


@pytest.mark.parametrize("dose", [10.0, 25.0, 60.0])
def test_corner_ranges_bound_interior_readings_and_shared_change(dose):
    first, second = synthetic_pair()
    result = ref.forecast(first, second, dose, TEMPERATURE, DOMAIN)
    voltage_low, voltage_high = result["prediction_reading_box_mV"]
    change_low, change_high = result["change_reading_box_mV"]
    for i in range(11):
        for j in range(11):
            one = replace(first, voltage_mV=first.voltage_mV - 1 + i / 5)
            two = replace(second, voltage_mV=second.voltage_mV - 1 + j / 5)
            predicted = ref.fit_two_points(one, two, TEMPERATURE, DOMAIN).voltage_at(dose)
            assert voltage_low - 1e-12 <= predicted <= voltage_high + 1e-12
            assert change_low - 1e-12 <= predicted - one.voltage_mV <= change_high + 1e-12
    if dose == first.potassium_mM:
        assert result["change_reading_box_mV"] == pytest.approx([0.0, 0.0], abs=1e-12)
        assert voltage_high - voltage_low == pytest.approx(2.0, abs=1e-12)


def test_extrapolation_extrema_use_opposite_corners():
    first, second = synthetic_pair()
    result = ref.forecast(first, second, 60.0, TEMPERATURE, DOMAIN)
    corners = result["reading_corners"]
    assert result["prediction_reading_box_mV"] == [
        corners[2]["prediction_mV"],  # First high, second low.
        corners[1]["prediction_mV"],  # First low, second high.
    ]


def test_evaluation_voltage_cannot_change_prediction_or_fit():
    first, second = synthetic_pair()
    prediction = ref.forecast(first, second, 60.0, TEMPERATURE, DOMAIN)
    saved = copy.deepcopy(prediction)
    one = driver.ref.compare_prediction(prediction, ref.Reading("test", 60.0, -18.0, 2.0))
    two = driver.ref.compare_prediction(prediction, ref.Reading("test", 60.0, 100.0, 2.0))
    assert prediction == saved
    assert one["signed_error_mV"] - two["signed_error_mV"] == pytest.approx(118.0)
    assert one["biological_acceptance"] == two["biological_acceptance"] == "not_assessable"


def test_evaluation_identity_and_dose_are_checked():
    first, second = synthetic_pair()
    prediction = ref.forecast(first, second, 60.0, TEMPERATURE, DOMAIN)
    with pytest.raises(ValueError, match="cannot be a fitting reading"):
        ref.compare_prediction(prediction, replace(first, potassium_mM=60.0))
    with pytest.raises(ValueError, match="dose does not match"):
        ref.compare_prediction(prediction, ref.Reading("test", 61.0, -18.0, 2.0))


def test_null_and_residual_reading_boxes(analysis):
    comparison = analysis["comparison"]
    low, high = analysis["prediction"]["prediction_reading_box_mV"]
    assert comparison["measured_reading_box_mV"] == [-20.0, -16.0]
    assert comparison["signed_error_reading_box_mV"] == [low + 16.0, high + 20.0]
    assert comparison["measured_change_reading_box_mV"] == [17.0, 25.0]
    null = comparison["no_response"]
    assert null["prediction_mV"] == -39.0
    assert null["prediction_reading_box_mV"] == [-41.0, -37.0]
    assert null["signed_error_reading_box_mV"] == [-25.0, -17.0]
    assert null["change_reading_box_mV"] == [0.0, 0.0]


def test_independent_decimal_oracle_and_exact_fit_residuals(analysis):
    checked = analysis["numerical_crosscheck"]
    assert checked["status"] == "pass"
    assert checked["decimal_precision_digits"] == 60
    assert checked["scalar_comparisons"] == 12
    assert checked["maximum_absolute_error_mV"] <= checked["absolute_tolerance_mV"] == 1e-10
    assert checked["formal_interval_certificate"] is False


def test_crosscheck_rejects_wrong_prediction(analysis):
    prediction = copy.deepcopy(analysis["prediction"])
    first, second = (ref.Reading(**reading) for reading in prediction["fit_readings"])
    prediction["prediction_mV"] += 1.0
    with pytest.raises(ValueError, match="crosscheck failed"):
        driver.numerical_crosscheck(prediction, first, second, TEMPERATURE, 1e-10)


def test_driver_passes_only_fit_readings_and_target_dose_to_forecast(monkeypatch):
    original = ref.forecast
    calls = []

    def checked(first, second, target_dose, temperature, domain):
        calls.append((first.identity, second.identity, target_dose))
        return original(first, second, target_dose, temperature, domain)

    monkeypatch.setattr(ref, "forecast", checked)
    driver.build_analysis()
    assert calls == [("C1", "C2", 65.4)]


def test_analysis_keeps_quarantine_and_claim_limits(analysis):
    assert analysis["split"] == {
        "fit": ["C1", "C2"],
        "evaluation": ["C3"],
        "quarantined": ["C4", "C5"],
        "blinded": False,
        "prospective": False,
    }
    assert analysis["model_fit"] == "performed_on_C1_C2_only"
    for key in (
        "trajectory_integration",
        "production_model_changed",
        "physical_parameters_identified",
        "experimental_sem_available",
        "confidence_interval",
    ):
        assert analysis[key] is False
    assert analysis["biological_acceptance"] == "not_assessable"
    assert analysis["boundary"]["background_positive_charge_mM_equivalents"] == 5.6
    assert [row["condition"] for row in driver.condition_rows(analysis)] == ["C1", "C2", "C3"]


def test_changed_protocol_is_refused(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_bytes(driver.PLAN.read_bytes() + b" ")
    with pytest.raises(ValueError, match="protocol changed"):
        driver.build_analysis(plan)


def test_changed_dataset_is_refused(tmp_path):
    directory = tmp_path / "data"
    shutil.copytree(driver.data_check.DATA, directory)
    path = directory / "voltage_endpoints.csv"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="dataset changed"):
        driver.build_analysis(data_directory=directory)


def test_artifact_payloads_hashes_and_descriptive_plot(tmp_path, analysis):
    directory = tmp_path / "result"
    receipt = driver.write_artifacts(directory, analysis)
    assert receipt == json.loads((directory / "manifest.json").read_text())
    assert receipt["biological_acceptance"] == "not_assessable"
    assert set(receipt["payload_sha256"]) == {
        "analysis.json",
        "conditions.csv",
        "comparison.svg",
        "protocol.json",
    }
    for name, expected in receipt["payload_sha256"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected
    assert (directory / "protocol.json").read_bytes() == driver.PLAN.read_bytes()
    with (directory / "conditions.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["role"] for row in rows] == ["fit", "fit", "evaluation"]
    svg = ElementTree.fromstring((directory / "comparison.svg").read_text())
    labels = " ".join(svg.itertext())
    assert "not SEM or confidence intervals" in labels
    assert "C3 (evaluation)" in labels
    assert "No biological acceptance claim" in labels


def test_existing_output_is_refused_and_preserved(tmp_path, analysis):
    directory = tmp_path / "result"
    driver.write_artifacts(directory, analysis)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    with pytest.raises(FileExistsError, match="already exists"):
        driver.write_artifacts(directory, analysis)
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before


def test_output_not_created_on_protocol_mismatch(tmp_path, analysis):
    directory = tmp_path / "result"
    changed = copy.deepcopy(analysis)
    changed["protocol_sha256"] = "incorrect"
    with pytest.raises(ValueError, match="Protocol identity changed"):
        driver.write_artifacts(directory, changed)
    assert not directory.exists()


def test_output_not_created_for_nonfinite_payload(tmp_path, analysis):
    directory = tmp_path / "result"
    changed = copy.deepcopy(analysis)
    changed["comparison"]["signed_error_mV"] = math.nan
    with pytest.raises(ValueError):
        driver.write_artifacts(directory, changed)
    assert not directory.exists()
