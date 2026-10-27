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


@pytest.mark.parametrize("enabled", [False, True])
def test_registered_cache_policy_overrides_ambient_environment(prepared, monkeypatch, enabled):
    output, record, _, execute = prepared
    protocol = record["component_protocol"]
    protocol["resources"]["persistent_compilation_cache"] = enabled
    runner.write_json(output / "component-protocol.json", protocol, replace=True)
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    runner.write_json(output / "registration.json", record, replace=True)
    monkeypatch.setenv("JAX_ENABLE_COMPILATION_CACHE", str(not enabled).lower())
    checked = []

    def probe(command, **kwargs):
        assert "jax.config.jax_enable_compilation_cache" in command[-1]
        assert kwargs["env"]["JAX_ENABLE_COMPILATION_CACHE"] == str(enabled).lower()
        return json.dumps({"qualification_jax_flags": {"enable_compilation_cache": enabled}})

    def worker(command, **kwargs):
        assert kwargs["env"]["JAX_ENABLE_COMPILATION_CACHE"] == str(enabled).lower()
        checked.append(kwargs["env"]["CELLS_COMPONENT_BACKEND"])
        return execute(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "check_output", probe)
    monkeypatch.setattr(runner, "run_bounded", worker)
    runner.component_worker(output, record)
    assert checked == ["cpu", "gpu"]
    for backend in checked:
        saved = json.loads((output / f"{backend}.runtime.json").read_text())
        assert saved["qualification_jax_flags"]["enable_compilation_cache"] is enabled


def test_mismatched_runtime_cache_policy_stops_before_tests(prepared, monkeypatch):
    output, record, started, _ = prepared
    protocol = record["component_protocol"]
    protocol["resources"]["persistent_compilation_cache"] = False
    runner.write_json(output / "component-protocol.json", protocol, replace=True)
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    runner.write_json(output / "registration.json", record, replace=True)
    monkeypatch.setattr(
        runner.subprocess,
        "check_output",
        lambda *args, **kwargs: '{"qualification_jax_flags":{"enable_compilation_cache":true}}',
    )
    with pytest.raises(ValueError, match="cache policy differs"):
        runner.component_worker(output, record)
    assert not started and not (output / "groups").exists()
    assert (output / "failure.json").is_file() and not (output / "completion.json").exists()


@pytest.mark.parametrize("value", [None, 0, 1, "false", {}, []])
def test_cache_policy_rejects_ambiguous_values(value):
    with pytest.raises(ValueError, match="must be a boolean"):
        runner.component_cache_environment({"resources": {"persistent_compilation_cache": value}})


@pytest.mark.parametrize("fault", [None, "flags", "device", "missing", "initialization"])
def test_gpu_policy_is_registered_gpu_only_and_verified_before_tests(prepared, monkeypatch, fault):
    output, record, started, execute = prepared
    protocol = record["component_protocol"]
    protocol["resources"]["gpu_execution_policy"] = "deterministic"
    runner.write_json(output / "component-protocol.json", protocol, replace=True)
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    runner.write_json(output / "registration.json", record, replace=True)
    monkeypatch.setenv("XLA_FLAGS", "--ambient-policy")
    flags = "--xla_gpu_exclude_nondeterministic_ops=true --xla_gpu_autotune_level=0"
    calls = []

    def probe(command, **kwargs):
        environment = kwargs["env"]
        if environment["CELLS_COMPONENT_BACKEND"] == "cpu":
            assert environment["XLA_FLAGS"] == "--ambient-policy"
            assert "qualification_gpu_execution" not in command[-1]
            return "{}"
        assert environment["XLA_FLAGS"] == flags
        # Initializing the requested GPU also makes XLA reject unsupported flags.
        assert "jax.devices('gpu')" in command[-1]
        if fault == "initialization":
            raise subprocess.CalledProcessError(1, command)
        value = {"policy": "deterministic", "xla_flags": flags, "device_platforms": ["gpu"]}
        if fault == "flags":
            value["xla_flags"] = "--xla_gpu_autotune_level=4"
        elif fault == "device":
            value["device_platforms"] = ["cpu"]
        return json.dumps({} if fault == "missing" else {"qualification_gpu_execution": value})

    def worker(command, **kwargs):
        backend = kwargs["env"]["CELLS_COMPONENT_BACKEND"]
        assert kwargs["env"]["XLA_FLAGS"] == (flags if backend == "gpu" else "--ambient-policy")
        calls.append(backend)
        return execute(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "check_output", probe)
    monkeypatch.setattr(runner, "run_bounded", worker)
    if fault:
        error = subprocess.CalledProcessError if fault == "initialization" else ValueError
        with pytest.raises(error):
            runner.component_worker(output, record)
        assert calls == ["cpu"] and started == ["gpu"]
        assert (output / "failure.json").is_file()
        assert not (output / "completion.json").exists()
        assert not (output / "groups/gpu").exists()
    else:
        runner.component_worker(output, record)
        assert calls == ["cpu", "gpu"]
        assert (output / "completion.json").is_file()
        assert "qualification_gpu_execution" not in json.loads(
            (output / "cpu.runtime.json").read_text()
        )
        saved = json.loads((output / "gpu.runtime.json").read_text())
        assert saved["qualification_gpu_execution"]["xla_flags"] == flags


@pytest.mark.parametrize("value", [None, False, True, 0, 1, "fast", {}, []])
def test_gpu_policy_rejects_unknown_or_ambiguous_values(value):
    with pytest.raises(ValueError, match="Unknown component GPU execution policy"):
        runner.component_gpu_environment({"resources": {"gpu_execution_policy": value}})


def test_unregistered_gpu_policy_preserves_other_protocols():
    assert runner.component_gpu_environment({"resources": {}}) == {}


@pytest.mark.parametrize("fault", [None, "wrong_limit", "wrong_threshold", "wrong_libc", "missing"])
def test_allocator_policy_is_inherited_recorded_and_checked(prepared, monkeypatch, fault):
    output, record, _, execute = prepared
    monkeypatch.delenv("LD_PRELOAD", raising=False)
    monkeypatch.delenv("GLIBC_TUNABLES", raising=False)
    monkeypatch.setenv("MALLOC_ARENA_MAX", "64")
    protocol = record["component_protocol"]
    protocol["resources"]["host_allocator_policy"] = "glibc_two_arenas_128k"
    runner.write_json(output / "component-protocol.json", protocol, replace=True)
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    runner.write_json(output / "registration.json", record, replace=True)
    calls = []

    def probe(command, **kwargs):
        assert kwargs["env"]["MALLOC_ARENA_MAX"] == "2"
        assert "platform.libc_ver()" in command[-1]
        allocator = {
            "libc": ["musl" if fault == "wrong_libc" else "glibc", "2.41"],
            "MALLOC_ARENA_MAX": "64" if fault == "wrong_limit" else "2",
            "MALLOC_MMAP_THRESHOLD_": "33554432" if fault == "wrong_threshold" else "131072",
            "MALLOC_TRIM_THRESHOLD_": "131072",
            "GLIBC_TUNABLES": None,
            "LD_PRELOAD": None,
        }
        return json.dumps({} if fault == "missing" else {"qualification_host_allocator": allocator})

    def worker(command, **kwargs):
        assert kwargs["env"]["MALLOC_ARENA_MAX"] == "2"
        assert kwargs["env"]["MALLOC_MMAP_THRESHOLD_"] == "131072"
        assert kwargs["env"]["MALLOC_TRIM_THRESHOLD_"] == "131072"
        calls.append(kwargs["env"]["CELLS_COMPONENT_BACKEND"])
        return execute(command, **kwargs)

    monkeypatch.setattr(runner.subprocess, "check_output", probe)
    monkeypatch.setattr(runner, "run_bounded", worker)
    if fault:
        with pytest.raises(ValueError, match="runtime host allocator policy differs"):
            runner.component_worker(output, record)
        assert calls == [] and not (output / "completion.json").exists()
        return
    runner.component_worker(output, record)
    assert calls == ["cpu", "gpu"]
    done = json.loads((output / "completion.json").read_text())
    for backend in calls:
        # Numerical runtime still compares exactly with earlier qualifications.
        assert json.loads((output / f"{backend}.runtime.json").read_text()) == {}
        path = output / f"{backend}.host-allocator.json"
        assert json.loads(path.read_text())["MALLOC_ARENA_MAX"] == "2"
        assert done["evidence_sha256"][path.name] == runner.digest(path)


@pytest.mark.parametrize(
    "environment",
    [
        {"LD_PRELOAD": "/different-malloc.so"},
        {"GLIBC_TUNABLES": "glibc.malloc.arena_max=64"},
        {"GLIBC_TUNABLES": "glibc.malloc.mmap_threshold=33554432"},
        {"GLIBC_TUNABLES": "glibc.malloc.trim_threshold=33554432"},
    ],
)
def test_allocator_policy_rejects_overriding_ambient_settings(monkeypatch, environment):
    for key in ("LD_PRELOAD", "GLIBC_TUNABLES"):
        monkeypatch.delenv(key, raising=False)
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="Component glibc"):
        runner.component_allocator_environment(
            {"resources": {"host_allocator_policy": "glibc_two_arenas_128k"}}
        )
    assert runner.component_allocator_environment({"resources": {}}) == {}


@pytest.mark.parametrize("value", [None, False, 2, "unknown"])
def test_allocator_policy_rejects_unregistered_values(value):
    with pytest.raises(ValueError, match="Unknown component host allocator policy"):
        runner.component_allocator_environment({"resources": {"host_allocator_policy": value}})


SLOW_COMPILE = (
    "E1024 22:08:35.453988 3769309 slow_operation_alarm.cc:73] \n"
    "********************************\n"
    "[Compiling module jit__checked_rollout for CPU] Very slow compile? "
    "If you want to file a bug, run with envvar XLA_FLAGS=--xla_dump_to=/tmp/foo "
    "and attach the results.\n********************************\n"
)


def test_registered_slow_compile_notices_remain_in_authenticated_logs(prepared, monkeypatch):
    output, record, _, execute = prepared
    protocol = record["component_protocol"]
    protocol["allowed_stderr_notices"] = ["xla_slow_compilation"]
    runner.write_json(output / "component-protocol.json", protocol, replace=True)
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    runner.write_json(output / "registration.json", record, replace=True)
    completed = SLOW_COMPILE.replace(".cc:73] \n", ".cc:140] The operation took 3m12.5s\n\n")
    log = SLOW_COMPILE + completed

    def worker(command, **kwargs):
        result = execute(command, **kwargs)
        (kwargs["directory"] / "stderr.log").write_text(log)
        return result

    monkeypatch.setattr(runner, "run_bounded", worker)
    runner.component_worker(output, record)
    receipt = json.loads((output / "completion.json").read_text())
    for backend in ("cpu", "gpu"):
        directory = output / "groups" / backend / "part-01"
        assert (
            json.loads((directory / "qualified.json").read_text())["slow_compilation_notices"] == 2
        )
        path = directory / "stderr.log"
        assert path.read_text() == log
        assert runner.digest(path) == receipt["evidence_sha256"][str(path.relative_to(output))]


@pytest.mark.parametrize(
    "fault",
    ["unregistered", "warning", "traceback", "changed_message", "injected", "unknown_policy"],
)
def test_compile_notice_exception_does_not_hide_other_diagnostics(fault):
    protocol = {"allowed_stderr_notices": ["xla_slow_compilation"]}
    text = SLOW_COMPILE
    if fault == "unregistered":
        protocol = {}
    elif fault == "warning":
        text += "RuntimeWarning: invalid value encountered in log\n"
    elif fault == "traceback":
        text += "Traceback (most recent call last):\nNumericalError: balance failed\n"
    elif fault == "changed_message":
        text = text.replace("Very slow compile?", "Compilation failed:")
    elif fault == "injected":
        text = text.replace("and attach the results.", "and attach the results.\nNaN in state")
    else:
        protocol["allowed_stderr_notices"] = ["all_warnings"]
    with pytest.raises(ValueError):
        runner.component_stderr_notices(text, protocol)


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
        directory = kwargs["directory"]
        backend = kwargs["env"]["CELLS_COMPONENT_BACKEND"]
        if backend == "gpu":
            selected = json.loads((directory / "evidence/cpu/root.json").read_text())
            assert selected == (
                {"status": "passed", "repeated_fixture": True}
                if directory.name == "part-02"
                else {"status": "passed"}
            )
        resources = execute(command, **kwargs)
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


@pytest.fixture
def reference_view(tmp_path):
    output = tmp_path / "run"
    shared, local = output / "evidence/cpu", output / "groups/cpu/refinement/evidence/cpu"
    hashes = {}
    for root, label in ((shared, "trajectory"), (local, "refinement")):
        root.mkdir(parents=True)
        for filename in ("reference.json", "reference.npz"):
            path = root / filename
            path.write_text(label + filename)
            hashes[str(path.relative_to(output))] = runner.digest(path)
    history = shared / "history.npz"
    history.write_text("shared scalar history")
    hashes[str(history.relative_to(output))] = runner.digest(history)
    directory = output / "groups/gpu/refinement"
    (directory / "evidence").mkdir(parents=True)
    return output, directory, hashes


def test_cpu_input_view_keeps_group_pairs_and_shared_fallbacks(reference_view):
    output, directory, hashes = reference_view
    binding = runner.component_cpu_inputs(output, directory, "refinement", hashes)
    selected = directory / "evidence/cpu"
    assert (selected / "reference.json").read_text() == "refinementreference.json"
    assert (selected / "reference.npz").read_text() == "refinementreference.npz"
    assert (selected / "history.npz").read_text() == "shared scalar history"
    assert binding["files"]["reference.json"]["source"].startswith("groups/cpu/refinement/")
    assert binding["files"]["history.npz"]["source"].startswith("evidence/cpu/")
    for name, item in binding["files"].items():
        assert (selected / name).stat().st_ino != (output / item["source"]).stat().st_ino
    runner.verify_component_cpu_inputs(output, directory, binding)


@pytest.mark.parametrize("fault", ["source", "copy", "missing", "extra", "binding", "symlink"])
def test_cpu_input_view_rejects_changed_pairs(reference_view, fault):
    output, directory, hashes = reference_view
    binding = runner.component_cpu_inputs(output, directory, "refinement", hashes)
    target = directory / "evidence/cpu/reference.npz"
    if fault == "source":
        (output / binding["files"]["reference.npz"]["source"]).write_text("corrupt source")
    elif fault == "copy":
        target.write_text("corrupt copy")
    elif fault == "missing":
        target.unlink()
    elif fault == "extra":
        (target.parent / "extra.npz").write_text("unexpected")
    elif fault == "binding":
        (directory / "cpu-inputs.json").write_text("{}")
    else:
        target.unlink()
        target.symlink_to(output / binding["files"]["reference.npz"]["source"])
    with pytest.raises(ValueError, match="CPU input"):
        runner.verify_component_cpu_inputs(output, directory, binding)


def test_cpu_input_selection_rejects_cross_group_report_array_pair(reference_view):
    output, directory, hashes = reference_view
    (output / "groups/cpu/refinement/evidence/cpu/reference.npz").unlink()
    with pytest.raises(ValueError, match="different groups"):
        runner.component_cpu_inputs(output, directory, "refinement", hashes)


def test_cpu_input_selection_rejects_preexisting_source_mutation(reference_view):
    output, directory, hashes = reference_view
    (output / "groups/cpu/refinement/evidence/cpu/reference.npz").write_text("changed")
    with pytest.raises(ValueError, match="CPU evidence changed"):
        runner.component_cpu_inputs(output, directory, "refinement", hashes)
