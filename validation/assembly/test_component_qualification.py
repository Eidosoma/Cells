"""New component phases retain strict collection, source and failure boundaries."""

import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

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
        directory = kwargs["directory"]
        ET.ElementTree(suites).write(directory / "tests.xml")
        (directory / "stdout.log").write_text("1 passed\n")
        (directory / "stderr.log").write_text("")
        evidence = Path(kwargs["env"]["CELLS_COMPONENT_EVIDENCE"]) / backend
        evidence.mkdir(parents=True)
        runner.write_json(evidence / "root.json", {"status": "passed"})
        return {
            "observed_process_high_water_bytes": 4096,
            "sampled_peak_process_tree_rss_bytes": 8192,
        }

    monkeypatch.setattr(runner, "run_bounded", execute)
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

    monkeypatch.setattr(runner, "run_bounded", fail)
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
        result = execute(command, **kwargs)
        path = kwargs["directory"] / "tests.xml"
        path.write_text(path.read_text().replace("test_root", "test_unregistered"))
        return result

    monkeypatch.setattr(runner, "run_bounded", wrong_name)
    with pytest.raises(ValueError, match="omitted"):
        runner.component_worker(output, record)
    assert not started


@pytest.mark.parametrize("fault", ["duplicate", "missing", "unknown", "overlap", "name", "skip"])
def test_groups_reject_omissions_duplicates_and_unregistered_skips(fault):
    nodes = ["tests/test_a.py::test_one[a]", "tests/test_a.py::test_one[b]"]
    groups = [
        {"name": "first", "tests": [nodes[0]]},
        {"name": "second", "tests": [nodes[1]]},
    ]
    protocol = {"test_groups": groups, "expected_cpu_skip_nodes": []}
    if fault == "duplicate":
        groups[1]["tests"] = [nodes[0]]
    elif fault == "missing":
        groups.pop()
    elif fault == "unknown":
        groups[1]["tests"] = ["tests/test_a.py::test_unknown"]
    elif fault == "overlap":
        groups[0]["tests"].append("tests/test_a.py")
    elif fault == "name":
        groups[0]["name"] = "../escape"
    else:
        protocol["expected_cpu_skip_nodes"] = ["tests/test_a.py::test_unknown"]
    with pytest.raises(ValueError):
        runner.component_groups(protocol, nodes)


def test_groups_resolve_parametrized_tests_without_prefix_collisions():
    nodes = [
        "tests/test_a.py::test_one[a]",
        "tests/test_a.py::test_one[b]",
        "tests/test_a.py::test_one_more",
        "tests/test_b.py::test_two",
    ]
    protocol = {
        "test_groups": [
            {"name": "first", "tests": ["tests/test_a.py::test_one"]},
            {"name": "second", "tests": [nodes[2], "tests/test_b.py"]},
        ],
        "expected_cpu_skip_nodes": [nodes[-1]],
    }
    groups = runner.component_groups(protocol, nodes)
    assert groups[0]["test_nodes"] == nodes[:2] and groups[1]["test_nodes"] == nodes[2:]


@pytest.mark.parametrize("fault", ["hidden_failure", "hidden_error", "hidden_skip", "duplicate"])
def test_suite_checks_cases_instead_of_trusting_summary(prepared, fault):
    output, record, _, _ = prepared
    suites = ET.Element("testsuites")
    suite = ET.SubElement(suites, "testsuite", tests="1", failures="0", errors="0", skipped="0")
    case = ET.SubElement(suite, "testcase", classname="tests.unit.test_field", name="test_root")
    if fault == "duplicate":
        suite.append(case)
    else:
        ET.SubElement(
            case,
            {"hidden_failure": "failure", "hidden_error": "error", "hidden_skip": "skipped"}[fault],
        )
    path = output / "test.xml"
    ET.ElementTree(suites).write(path)
    with pytest.raises(ValueError, match="omitted or failed"):
        runner.component_suite(path, record["test_nodes"], [])


def test_groups_preserve_earlier_evidence_and_aggregate_exact_coverage(prepared, monkeypatch):
    output, record, _, execute = prepared
    protocol = record["component_protocol"]
    protocol["tests"].append("tests/unit/test_second.py")
    record["test_nodes"].append("tests/unit/test_second.py::test_second")
    runner.write_json(output / "component-protocol.json", protocol, replace=True)
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    record["test_groups"] = runner.component_groups(protocol, record["test_nodes"])
    runner.write_json(output / "registration.json", record, replace=True)

    def grouped(command, **kwargs):
        resources = execute(command, **kwargs)
        directory = kwargs["directory"]
        if directory.name == "part-02":
            path = directory / "tests.xml"
            path.write_text(
                path.read_text()
                .replace("test_field", "test_second")
                .replace("test_root", "test_second")
            )
            backend = kwargs["env"]["CELLS_COMPONENT_BACKEND"]
            evidence = Path(kwargs["env"]["CELLS_COMPONENT_EVIDENCE"]) / backend / "root.json"
            runner.write_json(
                evidence, {"status": "passed", "repeated_fixture": True}, replace=True
            )
        return resources

    monkeypatch.setattr(runner, "run_bounded", grouped)
    runner.component_worker(output, record)
    for backend in ("cpu", "gpu"):
        row, _ = runner.component_suite(output / f"{backend}.xml", record["test_nodes"], [])
        assert row == dict(tests=2, errors=0, failures=0, skipped=0)
        assert json.loads((output / "evidence" / backend / "root.json").read_text()) == {
            "status": "passed"
        }
        local = output / "groups" / backend / "part-02" / "evidence" / backend / "root.json"
        assert json.loads(local.read_text())["repeated_fixture"]
        done = json.loads((output / "completion.json").read_text())
        assert str(local.relative_to(output)) in done["evidence_sha256"]
