"""New component phases retain strict collection, source and failure boundaries."""

import json
import subprocess
import xml.etree.ElementTree as ET

import pytest

from validation.assembly import qualify_cell as runner
from validation.ensemble import qualification_metrics


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    output = tmp_path / "run"
    (output / "source").mkdir(parents=True)
    (output / "cache").mkdir()
    protocol = {
        "tests": ["tests/unit/test_field.py"],
        "expected_cpu_skip_nodes": [],
        "required_evidence": ["root"],
        "required_gpu_evidence": [],
        "scope": "Synthetic harness control",
        "scope_exclusions": [],
        "resources": {
            "max_wall_seconds": 60,
            "max_worker_rss_bytes": 16 * 1024**3,
            "artifact_and_cache_bytes": 1024**3,
            "free_disk_reserve_bytes": 0,
            "gpu_memory_fraction": 0.15,
        },
    }
    runner.write_json(output / "component-protocol.json", protocol)
    record = {
        "component_protocol": protocol,
        "component_protocol_sha256": runner.digest(output / "component-protocol.json"),
        "sources_sha256": {},
        "cpu_affinity": [4, 5],
        "workspace": str(tmp_path),
        "gpu": {"uuid": "gpu"},
        "gpu_metrics": {},
        "max_wall_seconds": 60,
        "test_nodes": ["tests/unit/test_field.py::test_root"],
    }
    runner.write_json(output / "registration.json", record)
    monkeypatch.setattr(runner.os, "sched_setaffinity", lambda *args: None)
    monkeypatch.setattr(runner.subprocess, "check_output", lambda *args, **kwargs: "{}")
    started = []

    class Observer:
        def __init__(self, directory, settings):
            self.directory = directory

        def start(self):
            started.append("gpu")
            self.directory.mkdir()

        def finish(self, **kwargs):
            result = {"whole_job": {"gpu_busy": {"seconds": 0.1}}}
            runner.write_json(self.directory / "result.json", result)
            return result

        def close(self):
            pass

    monkeypatch.setattr(qualification_metrics, "GpuQualificationMetrics", Observer)

    def execute(command, **kwargs):
        backend = kwargs["env"]["CELLS_COMPONENT_BACKEND"]
        suites = ET.Element("testsuites")
        suite = ET.SubElement(suites, "testsuite", tests="1", failures="0", errors="0", skipped="0")
        ET.SubElement(suite, "testcase", classname="tests.unit.test_field", name="test_root")
        ET.ElementTree(suites).write(output / f"{backend}.xml")
        evidence = output / "evidence" / backend
        evidence.mkdir(parents=True)
        runner.write_json(evidence / "root.json", {"status": "passed"})

    monkeypatch.setattr(runner.subprocess, "run", execute)
    return output, record, started, execute


def test_component_records_completed_phase_evidence_and_metrics(prepared):
    output, record, started, _ = prepared
    runner.component_worker(output, record)
    assert started == ["gpu"]
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "completed" and result["automatic_followup"] is False
    assert result["gpu_metrics"]["whole_job"]["gpu_busy"]["seconds"] == 0.1
    done = json.loads((output / "completion.json").read_text())
    assert done["result_sha256"] == runner.digest(output / "result.json")
    for path, expected in done["evidence_sha256"].items():
        assert runner.digest(output / path) == expected


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_failed_phase_keeps_failure_and_prevents_followup(prepared, monkeypatch, backend):
    output, record, started, execute = prepared

    def fail(command, **kwargs):
        if kwargs["env"]["CELLS_COMPONENT_BACKEND"] == backend:
            raise subprocess.CalledProcessError(1, command)
        return execute(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        runner.component_worker(output, record)
    assert started == ([] if backend == "cpu" else ["gpu"])
    assert (output / "failure.json").is_file() and not (output / "completion.json").exists()
    if backend == "gpu":
        assert (output / "gpu-metrics/result.json").is_file()


def test_changed_protocol_stops_before_any_gpu_work(prepared):
    output, record, started, _ = prepared
    (output / "component-protocol.json").write_text("{}")
    with pytest.raises(ValueError, match="input changed"):
        runner.component_worker(output, record)
    assert not started


def test_equal_test_count_cannot_hide_a_missing_registered_test(prepared, monkeypatch):
    output, record, started, execute = prepared

    def wrong_name(command, **kwargs):
        execute(command, **kwargs)
        path = output / "cpu.xml"
        path.write_text(path.read_text().replace("test_root", "test_unregistered"))

    monkeypatch.setattr(runner.subprocess, "run", wrong_name)
    with pytest.raises(ValueError, match="omitted"):
        runner.component_worker(output, record)
    assert not started
