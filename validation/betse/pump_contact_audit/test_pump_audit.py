"""Saved-data and corruption checks; no model runtime needed."""

import copy
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
a = importlib.import_module("pump_audit")


@pytest.fixture(scope="module")
def saved():
    return a.authenticate(), *(
        a.read(a.CAPTURE / f"{n}.json") for n in ("native", "prototype", "comparison")
    )


def test_all_saved_columns_reconstruct_independently(saved):
    result = a.audit_saved(*saved)
    assert result["comparisons"] == 1240
    assert result["raw_triplets_checked"] == 248
    assert result["independent_column_mismatches"] == 0
    assert not result["coupled_trajectory_qualified"]
    assert not result["production_pump_implemented"]


@pytest.mark.parametrize(
    "change",
    [
        "expected",
        "actual",
        "budget",
        "pass",
        "duplicate",
        "raw",
        "third",
        "met",
        "registration",
        "engine",
        "warning",
    ],
)
def test_rehashed_content_corruption_is_rejected(saved, change):
    registration, native, prototype, comparison = copy.deepcopy(saved)
    if change in ("expected", "actual", "budget"):
        comparison["rows"][0][change] += 1e-8
    elif change == "pass":
        comparison["rows"][0]["pass"] = False
    elif change == "duplicate":
        comparison["rows"][1] = comparison["rows"][0]
    elif change in ("raw", "third"):
        native["raw_density_mol_m2_s"]["source_constants"][0][2 if change == "third" else 0] *= 2
    elif change == "met":
        native["met_ignored"] = False
    elif change == "registration":
        prototype["registration_sha256"] = "wrong"
    elif change == "engine":
        prototype["results"]["native"] = {}
    else:
        native["warnings"] = ["unexpected"]
    with pytest.raises(ValueError):
        a.audit_saved(registration, native, prototype, comparison)


def test_import_fence_without_model_environment():
    code = (
        "import pump_audit as a\n"
        "with a.model_fence():\n"
        " for name in a.FORBIDDEN:\n"
        "  try: __import__(name)\n"
        "  except ImportError: pass\n"
        "  else: raise AssertionError(name)\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=Path(__file__).resolve().parent,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_no_import_of_original_numerical_checker():
    source = Path(a.__file__).read_text()
    assert "import pump_reference" not in source
    assert "import pump_job" not in source
    assert "import pump_array" not in source


@pytest.mark.parametrize("field", ["pass", "comparisons"])
def test_capture_fields_are_not_a_substitute_for_rebuilding(saved, field):
    data = copy.deepcopy(saved)
    if field == "pass":
        data[3]["rows"][0]["expected"] = 123
        data[3]["rows"][0]["pass"] = True
    else:
        data[3]["comparisons"] -= 1
    with pytest.raises(ValueError):
        a.audit_saved(*data)


def test_existing_output_refused_without_write(tmp_path):
    before = list(tmp_path.iterdir())
    with pytest.raises(ValueError, match="fresh"):
        a.run(tmp_path)
    assert list(tmp_path.iterdir()) == before
