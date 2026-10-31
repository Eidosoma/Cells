"""Software checks for packaged held readers and complete event evidence.

These use manufactured metadata only; they neither run a scientific roster nor
grant scientific qualification credit.
"""

import ast
import importlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from validation.betse import archive_binding
from validation.betse import betse_normal_ecm_molecule_events_execution_evidence as events
from validation.betse import betse_normal_ecm_molecule_events_execution_reader as reader

ROOT = Path(__file__).resolve().parents[2]
PREFIXES = (
    "betse_normal_ecm_molecule_qualification",
    "betse_normal_ecm_molecule_phase_execution",
    "betse_normal_ecm_molecule_events_execution",
)


def _archive(folder, value):
    """Tiny original-format scalar archives; intentionally no numerical model."""
    folder.mkdir()

    def encode(value):
        if isinstance(value, dict):
            return {"mapping": [[key, encode(item)] for key, item in value.items()]}
        if isinstance(value, list):
            return {"sequence": [encode(item) for item in value]}
        if type(value) is float:
            return {"float64_bits": struct.pack("<d", value).hex()}
        return value

    with (folder / "data.json").open("x") as stream:
        json.dump(encode(value), stream, allow_nan=False)
    with zipfile.ZipFile(folder / "arrays.npz", "x"):
        pass
    with (folder / "manifest.json").open("x") as stream:
        json.dump(
            {
                "kind": archive_binding.KIND,
                "complete": True,
                "files": {
                    name: archive_binding.sha(folder / name) for name in ("data.json", "arrays.npz")
                },
            },
            stream,
        )


def _check_function(base):
    path = ROOT / "tests/unit/test_betse_normal_ecm_molecule_events_capture.py"
    function = next(
        node
        for node in ast.parse(path.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "check"
    )
    namespace = {
        "json": json,
        "archive": lambda tmp, name, value: _archive(base / name, value),
    }
    # Only the actual evidence-plumbing function is evaluated; no scientific import.
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["check"]


@pytest.mark.parametrize("prefix", PREFIXES)
def test_packaged_reader_rejects_duplicate_or_skipped_credit(prefix):
    module = importlib.import_module("validation.betse." + prefix + "_reader")
    node = "tests/unit/software.py::test_example"
    case = ET.Element("testcase", classname="tests.unit.software", name="test_example")
    assert module.verify_pytest_ids([case], [node]) == [node]
    with pytest.raises(ValueError, match="unique"):
        module.verify_pytest_ids([case, case], [node])
    ET.SubElement(case, "skipped")
    with pytest.raises(ValueError, match="skipped"):
        module.verify_pytest_ids([case], [node])


@pytest.mark.parametrize("prefix", PREFIXES)
def test_packaged_controller_requires_scientific_admission(prefix, tmp_path):
    contract = importlib.import_module("validation.betse." + prefix + "_contract")
    with pytest.raises(ValueError, match="[Hh]eld"):
        contract.verify_release(tmp_path, {})
    assert list(tmp_path.iterdir()) == []


def test_actual_event_evidence_and_reader_require_distinct_complete_records(tmp_path):
    name = "software-0-molecules-network"
    incoming = {"mode": "network", "complete_input": {"retained": [0.0, 1.0, 2.0]}}
    rows = {
        "field": {
            "metric": {"normalized_max_error": 0.0},
            "resolution": {"normalized_max_error": 0.0},
            "complete_metric_payload": {"before": [1.0], "after": [1.0]},
        }
    }
    _archive(tmp_path / name, incoming)
    reference = tmp_path / "reference"
    reference.mkdir()
    check = _check_function(tmp_path)
    check(tmp_path, name, reference, rows)
    _, saved_input = archive_binding.bind(tmp_path / name, decoded=True)
    _, saved_metric = archive_binding.bind(tmp_path / (name + "-comparison-metrics"), decoded=True)
    assert saved_input == incoming
    assert saved_metric == {"fields": rows, "physical_global_conservation_credit": False}
    archives = reader.Archives.__new__(reader.Archives)
    archives.binding = SimpleNamespace(core=archive_binding)
    archives.records, archives.locations = {}, {}
    consumer = events.Evidence.__new__(events.Evidence)
    consumer.archives, consumer.base, consumer.reader = archives, tmp_path, reader
    names = []

    def need(name):
        names.append(name)
        return archives.load(tmp_path / name)

    consumer.need = need
    consumer.report(name, "reference")
    assert names == [name + "-comparison-metrics"]
    consumer.need = lambda name: archives.load(tmp_path / "absent" / name)
    with pytest.raises(ValueError, match="archive directory"):
        consumer.report(name, "reference")
    before = {
        str(p.relative_to(tmp_path)): archive_binding.sha(p)
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    with pytest.raises(FileExistsError):
        check(tmp_path, name, reference, rows)
    assert before == {
        str(p.relative_to(tmp_path)): archive_binding.sha(p)
        for p in tmp_path.rglob("*")
        if p.is_file()
    }


def test_actual_comparison_report_refuses_overwrite_and_keeps_metric_prefix(tmp_path):
    reference = tmp_path / "reference"
    reference.mkdir()
    report = reference / "comparison.json"
    report.write_text("Preserve existing report.\n")
    rows = {
        "field": {
            "metric": {"normalized_max_error": 0.0},
            "resolution": {"normalized_max_error": 0.0},
        }
    }
    with pytest.raises(FileExistsError):
        _check_function(tmp_path)(tmp_path, "software", reference, rows)
    assert report.read_text() == "Preserve existing report.\n"
    _, metric = archive_binding.bind(tmp_path / "software-comparison-metrics", decoded=True)
    assert metric == {"fields": rows, "physical_global_conservation_credit": False}
