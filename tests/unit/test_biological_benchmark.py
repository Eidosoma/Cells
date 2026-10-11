"""Test the small experimental-data contract, not biological prediction."""

import csv
import json
import shutil

import pytest

from scripts import check_biological_benchmark as check


@pytest.fixture
def dataset(tmp_path):
    target = tmp_path / "data"
    shutil.copytree(check.DATA, target)
    return target


def change_manifest(directory, field, key, value):
    path = directory / "manifest.json"
    data = json.loads(path.read_text())
    data[field][key] = value
    path.write_text(json.dumps(data))


def change_csv(directory, filename, condition, field, value):
    path = directory / filename
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["condition_id"] == condition:
            row[field] = value
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_integrity_is_not_biological_acceptance():
    result = check.verify()
    assert result["integrity_status"] == "pass"
    assert result["source_figures_checked"] == 2
    assert result["conditions_checked"] == 5
    assert result["approximate_endpoints_checked"] == 3
    assert result["fit"] == ["C1", "C2"]
    assert result["evaluation"] == ["C3"]
    assert result["quarantined"] == ["C4", "C5"]
    assert result["figure2b_charge_residual_mM_equivalents"] == {
        "C1": 0,
        "C2": 0,
        "C3": 0,
        "C4": 10,
        "C5": 10,
    }
    assert result["approximate_endpoint_voltage_V"]["C1"] == -0.039
    assert result["biological_acceptance"] == "not_assessable"
    assert result["numerical_simulation"] == result["model_fit"] == "not_run"
    assert result["mean_extraction_independently_verified"] is False


@pytest.mark.parametrize(
    "key", ["model_fitted", "simulation_run", "biologically_validated", "production_config"]
)
def test_no_premature_result_claims(dataset, key):
    change_manifest(dataset, "claims", key, True)
    with pytest.raises(ValueError, match="Unestablished result"):
        check.verify(dataset)


@pytest.mark.parametrize("key", ["blinded", "prospective"])
def test_retrospective_split_is_not_blinded(dataset, key):
    change_manifest(dataset, "split", key, True)
    with pytest.raises(ValueError, match="Retrospective"):
        check.verify(dataset)


def test_no_quarantine_promotion(dataset):
    change_csv(dataset, "conditions.csv", "C4", "role", "evaluation")
    with pytest.raises(ValueError, match="role"):
        check.verify(dataset)


def test_no_silent_input_repair(dataset):
    change_csv(dataset, "conditions.csv", "C4", "figure2b_K_mM", "100.4")
    with pytest.raises(ValueError, match="Source recipe"):
        check.verify(dataset)


def test_divalent_chloride_is_not_dropped(dataset):
    change_csv(dataset, "conditions.csv", "C1", "figure2b_Cl_mM", "145.4")
    with pytest.raises(ValueError, match="Source recipe"):
        check.verify(dataset)


def test_unknown_sem_is_not_zero(dataset):
    change_csv(dataset, "voltage_endpoints.csv", "C1", "published_sem_mV", "0")
    with pytest.raises(ValueError, match="Unknown SEM"):
        check.verify(dataset)


def test_voltage_units_cannot_silently_change(dataset):
    change_csv(dataset, "voltage_endpoints.csv", "C1", "mean_voltage_mV_approx", "-0.039")
    with pytest.raises(ValueError, match="endpoint changed"):
        check.verify(dataset)


def test_source_asset_corruption(dataset):
    path = dataset / "sources/biolopen-9-048553-g2.jpg"
    path.write_bytes(path.read_bytes() + b"corruption")
    with pytest.raises(ValueError, match="bytes changed"):
        check.verify(dataset)


def test_temperature_conversion(dataset):
    change_manifest(dataset, "recording", "temperature_K", 25)
    with pytest.raises(ValueError, match="Temperature units"):
        check.verify(dataset)


def test_nonfinite_data(dataset):
    change_csv(dataset, "voltage_endpoints.csv", "C1", "mean_voltage_mV_approx", "nan")
    with pytest.raises(ValueError, match="Nonfinite"):
        check.verify(dataset)
