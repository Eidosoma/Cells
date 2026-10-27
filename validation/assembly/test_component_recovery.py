"""Resource-stop recovery must never mix source versions or hide missing checks."""

import copy
import json
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from validation.assembly import component_recovery as recovery
from validation.assembly import qualify_cell as runner
from validation.assembly.component_process import ProcessBudgetExceeded
from validation.assembly.test_component_qualification import prepared  # noqa: F401

REPLAY_SOURCE = """def test_complete_saved_restart_branch_and_windows():
    commands = [
        (
            "prepare", [],
            900,
        )
    ]
    commands.append(
        (
            "fresh", [],
            600,
        )
    )
    assert True
"""


@pytest.fixture
def interrupted(prepared, monkeypatch, request):  # noqa: F811 - imported pytest fixture.
    output, record, started, execute = prepared
    protocol = record["component_protocol"]
    protocol["automatic_followup"] = False
    protocol["tests"].append("tests/unit/test_second.py")
    protocol["resources"]["max_worker_rss_bytes"] = 16 * 1024**2
    protocol["resources"]["min_available_host_memory_bytes"] = 0
    record["test_nodes"].append("tests/unit/test_second.py::test_second")
    replay = getattr(request, "param", False)
    if replay:
        protocol["tests"][0] = recovery.REPLAY_TEST
        record["test_nodes"][0] = recovery.REPLAY_TEST + "::test_root"
    source = output / "source"
    for name in ["src/model.py", *protocol["tests"], *recovery.CONTROLLERS]:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Original frozen input\n")
    if replay:
        (source / recovery.REPLAY_TEST).write_text(REPLAY_SOURCE)
    for name in ("pyproject.toml", "requirements-lock.txt"):
        (source / name).write_text("")
    record["sources_sha256"] = runner.files(source)
    runner.write_json(output / "component-protocol.json", protocol, replace=True)
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    record["test_groups"] = runner.component_groups(protocol, record["test_nodes"])
    runner.write_json(output / "registration.json", record, replace=True)
    (output / "collection.log").write_text("\n".join(record["test_nodes"]))

    def grouped(command, **kwargs):
        resources = execute(command, **kwargs) | {"status": "completed", "returncode": 0}
        directory = kwargs["directory"]
        if replay and directory.name == "part-01":
            path = directory / "tests.xml"
            path.write_text(
                path.read_text().replace("test_field", "test_surface_mobile_pump_repair")
            )
        if directory.name == "part-02":
            path = directory / "tests.xml"
            path.write_text(
                path.read_text()
                .replace("test_field", "test_second")
                .replace("test_root", "test_second")
            )
        runner.write_json(directory / "result.json", resources)
        return resources

    def stop(command, **kwargs):
        directory = kwargs["directory"]
        if kwargs["env"]["CELLS_COMPONENT_BACKEND"] == "gpu" and directory.name == "part-02":
            runner.write_json(
                directory / "resource-stop.json", {"reasons": ["available_host_memory_reserve"]}
            )
            runner.write_json(
                directory / "failure.json", {"status": "failed", "cleanup_traceback": None}
            )
            raise ProcessBudgetExceeded("available_host_memory_reserve")
        return grouped(command, **kwargs)

    monkeypatch.setattr(runner, "run_bounded", stop)
    with pytest.raises(ProcessBudgetExceeded):
        runner.component_worker(output, record)
    started.clear()
    return output, record, started, grouped


def child(tmp_path, parent, original):
    output = tmp_path / "recovery"
    shutil.copytree(parent / "source", output / "source")
    (output / "cache").mkdir()
    for name in recovery.CONTROLLERS:
        (output / "source" / name).write_text("# Updated controller only\n")
    record = copy.deepcopy(original)
    record["component_recovery"] = recovery.parent_binding(parent)
    recovery.copy_groups(output, record["component_recovery"])
    record["sources_sha256"] = runner.files(output / "source")
    runner.write_json(output / "component-protocol.json", record["component_protocol"])
    runner.write_json(output / "registration.json", record)
    return output, record


@pytest.mark.parametrize("pss", [False, True])
@pytest.mark.parametrize("allocator", [False, True])
def test_recovery_executes_only_missing_gpu_group_and_binds_full_panel(
    interrupted, tmp_path, monkeypatch, pss, allocator
):
    parent, original, started, execute = interrupted
    before = recovery.parent_binding(parent)
    output, record = child(tmp_path, parent, original)
    if allocator:
        monkeypatch.delenv("LD_PRELOAD", raising=False)
        monkeypatch.delenv("GLIBC_TUNABLES", raising=False)
        record["component_protocol"]["resources"]["host_allocator_policy"] = "glibc_two_arenas_128k"
        monkeypatch.setattr(
            runner.subprocess,
            "check_output",
            lambda *args, **kwargs: json.dumps(
                {
                    "qualification_host_allocator": {
                        "libc": ["glibc", "2.41"],
                        "MALLOC_ARENA_MAX": kwargs["env"]["MALLOC_ARENA_MAX"],
                        "MALLOC_MMAP_THRESHOLD_": kwargs["env"]["MALLOC_MMAP_THRESHOLD_"],
                        "MALLOC_TRIM_THRESHOLD_": kwargs["env"]["MALLOC_TRIM_THRESHOLD_"],
                        "GLIBC_TUNABLES": None,
                        "LD_PRELOAD": None,
                    }
                }
            ),
        )
    if pss:
        record["component_protocol"]["resources"]["process_tree_memory_metric"] = "pss"
    if pss or allocator:
        runner.write_json(
            output / "component-protocol.json", record["component_protocol"], replace=True
        )
        record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
        runner.write_json(output / "registration.json", record, replace=True)
    calls = []

    def remaining(command, **kwargs):
        calls.append((kwargs["env"]["CELLS_COMPONENT_BACKEND"], kwargs["directory"].name))
        assert calls == [("gpu", "part-02")]
        assert kwargs["process_tree_memory_metric"] == ("pss" if pss else "rss")
        if allocator:
            assert kwargs["env"]["MALLOC_ARENA_MAX"] == "2"
        assert (
            kwargs["min_available_bytes"]
            == original["component_protocol"]["resources"]["min_available_host_memory_bytes"]
        )
        resources = execute(command, **kwargs)
        if pss:
            resources.update(
                process_tree_memory_metric="pss", sampled_peak_charged_memory_bytes=6000
            )
            runner.write_json(kwargs["directory"] / "result.json", resources, replace=True)
        return resources

    monkeypatch.setattr(runner, "run_bounded", remaining)
    runner.component_worker(output, record)
    assert started == ["gpu"] and calls == [("gpu", "part-02")]
    result = recovery.read(output / "result.json")
    assert result["status"] == "completed"
    assert all(
        row == dict(tests=2, errors=0, failures=0, skipped=0) for row in result["suites"].values()
    )
    assert result["recovery"]["executed_groups"] == {"cpu": [], "gpu": ["part-02"]}
    assert result["recovery"]["scientific_sources_and_protocol_unchanged"] is (
        not pss and not allocator
    )
    changes = {}
    if pss:
        changes["process_tree_memory_metric"] = {"before": "rss", "after": "pss"}
    if allocator:
        changes["host_allocator_policy"] = {"before": None, "after": "glibc_two_arenas_128k"}
    assert result["recovery"]["resource_policy_change"] == (changes or None)
    memory = result["process_tree_memory_by_group"]
    assert memory["cpu/part-01"] == {
        "metric": "rss",
        "sampled_peak_charged_memory_bytes": 8192,
        "reused": True,
    }
    assert memory["gpu/part-02"]["metric"] == ("pss" if pss else "rss")
    assert result["recovery"]["reused_groups"] == {
        "cpu": ["part-01", "part-02"],
        "gpu": ["part-01"],
    }
    done = recovery.read(output / "completion.json")
    for name, checksum in done["evidence_sha256"].items():
        assert runner.digest(output / name) == checksum
    assert recovery.parent_binding(parent) == before
    assert (parent / "failure.json").exists() and not (parent / "completion.json").exists()
    for filename in ("cpu-inputs.json", "evidence/cpu/root.json"):
        assert (output / "groups/gpu/part-01" / filename).read_bytes() == (
            parent / "groups/gpu/part-01" / filename
        ).read_bytes()


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "group_payload",
        "published_payload",
        "case_name",
        "failed_case",
        "partial_group",
        "cleanup",
        "assertion_failure",
        "collection",
        "gpu_cpu_input",
    ],
)
def test_parent_rejects_changed_or_incomplete_evidence(interrupted, fault):
    parent, _, _, _ = interrupted
    first = parent / "groups/cpu/part-01"
    if fault == "source":
        (parent / "source/src/model.py").write_text("# Changed science\n")
    elif fault in ("group_payload", "published_payload"):
        path = (first if fault == "group_payload" else parent) / "evidence/cpu/root.json"
        path.write_text('{"status":"passed","altered":true}')
    elif fault in ("case_name", "failed_case"):
        path = first / "tests.xml"
        text = path.read_text()
        text = (
            text.replace("test_root", "test_wrong")
            if fault == "case_name"
            else text.replace(" />", "><failure /></testcase>", 1)
        )
        path.write_text(text)
    elif fault == "partial_group":
        shutil.copyfile(first / "qualified.json", parent / "groups/gpu/part-02/qualified.json")
    elif fault == "cleanup":
        path = parent / "groups/gpu/part-02/failure.json"
        path.write_text(json.dumps({"status": "failed", "cleanup_traceback": "worker still alive"}))
    elif fault == "collection":
        (parent / "collection.log").write_text("tests/unit/test_field.py::test_root\n")
    elif fault == "gpu_cpu_input":
        (parent / "groups/gpu/part-01/evidence/cpu/root.json").write_text("{}")
    else:
        path = parent / "failure.json"
        value = recovery.read(path)
        value["traceback"] = "AssertionError: physical tolerance failed"
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        recovery.parent_binding(parent)


@pytest.mark.parametrize(
    "fault", ["source", "protocol", "copied_payload", "runtime", "late_payload", "late_protocol"]
)
def test_recovery_rejects_mixed_inputs_before_completion(interrupted, tmp_path, monkeypatch, fault):
    parent, original, started, execute = interrupted
    output, record = child(tmp_path, parent, original)
    if fault == "source":
        (output / "source/src/model.py").write_text("# Different scientific implementation\n")
        record["sources_sha256"] = runner.files(output / "source")
    elif fault == "protocol":
        record["component_protocol"]["resources"]["max_worker_rss_bytes"] *= 2
        runner.write_json(
            output / "component-protocol.json", record["component_protocol"], replace=True
        )
        record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    elif fault == "copied_payload":
        (output / "evidence/cpu/root.json").write_text('{"status":"passed","altered":true}')
    elif fault == "runtime":
        monkeypatch.setattr(
            runner.subprocess, "check_output", lambda *args, **kwargs: '{"changed":true}'
        )
    else:

        def changed(command, **kwargs):
            result = execute(command, **kwargs)
            target = (
                output / "component-protocol.json"
                if fault == "late_protocol"
                else output / "groups/gpu/part-01/evidence/gpu/root.json"
            )
            target.write_text('{"status":"passed","altered":true}')
            return result

        monkeypatch.setattr(runner, "run_bounded", changed)
    with pytest.raises(ValueError, match="Recovery|recovery"):
        runner.component_worker(output, record)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()
    assert started == (["gpu"] if fault in ("late_payload", "late_protocol") else [])


@pytest.mark.parametrize("pss", [False, True])
def test_launcher_uses_parent_science_and_new_controller_only(
    interrupted, tmp_path, monkeypatch, pss
):
    from cells.ensemble import telemetry
    from validation.ensemble import qualification_metrics

    parent, original, _, _ = interrupted
    checkout = tmp_path / "checkout"
    shutil.copytree(parent / "source", checkout)
    (checkout / "src/model.py").write_text("# New development must not enter this recovery\n")
    for name in recovery.CONTROLLERS:
        (checkout / name).write_text("# Current controller\n")
    monkeypatch.setattr(runner, "ROOT", checkout)
    monkeypatch.setattr(telemetry, "devices", lambda *args: [original["gpu"]])
    monkeypatch.setattr(qualification_metrics, "registration", lambda *args: {})
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, "\n".join(original["test_nodes"]), ""
        ),
    )
    launched = []

    def detach(command, **kwargs):
        assert kwargs["start_new_session"] and kwargs["stdin"] is subprocess.DEVNULL
        launched.append(command)
        return SimpleNamespace(pid=123456)

    monkeypatch.setattr(runner.subprocess, "Popen", detach)
    output = tmp_path / "launched"
    protocol_path = parent / "component-protocol.json"
    if pss:
        protocol = recovery.read(protocol_path)
        protocol["resources"]["process_tree_memory_metric"] = "pss"
        protocol_path = tmp_path / "pss-protocol.json"
        runner.write_json(protocol_path, protocol)
    receipt = runner.launch_component(output, protocol_path, tmp_path, parent=parent)
    assert len(launched) == 1 and receipt["status"] == "launched"
    assert (output / "source/src/model.py").read_bytes() == (
        parent / "source/src/model.py"
    ).read_bytes()
    for name in recovery.CONTROLLERS:
        assert (output / "source" / name).read_bytes() == (checkout / name).read_bytes()
    record = recovery.read(output / "registration.json")
    recovery.verify(output, record)
    assert record["component_recovery"]["pending_gpu_groups"] == ["part-02"]


@pytest.mark.parametrize(
    "fault", ["limit", "reserve", "scope", "cache", "gpu_policy", "reverse", "unknown"]
)
@pytest.mark.parametrize("allocator", [False, True])
def test_accounting_adjustment_cannot_hide_other_protocol_changes(fault, allocator):
    parent = {
        "scope": "fixed",
        "resources": {
            "max_worker_rss_bytes": 4096,
            "min_available_host_memory_bytes": 8192,
            "persistent_compilation_cache": False,
        },
    }
    candidate = copy.deepcopy(parent)
    candidate["resources"]["process_tree_memory_metric"] = "pss"
    if allocator:
        candidate["resources"]["host_allocator_policy"] = "glibc_two_arenas_128k"
    if fault == "limit":
        candidate["resources"]["max_worker_rss_bytes"] *= 2
    elif fault == "reserve":
        candidate["resources"]["min_available_host_memory_bytes"] = 0
    elif fault == "scope":
        candidate["scope"] = "changed science"
    elif fault == "cache":
        candidate["resources"]["persistent_compilation_cache"] = True
    elif fault == "gpu_policy":
        candidate["resources"]["gpu_execution_policy"] = "deterministic"
    elif fault == "reverse":
        parent["resources"]["process_tree_memory_metric"] = "pss"
        candidate["resources"]["process_tree_memory_metric"] = "rss"
    else:
        candidate["resources"]["process_tree_memory_metric"] = "uss"
    with pytest.raises(ValueError, match="protocol"):
        recovery.protocol_change(parent, candidate)


@pytest.mark.parametrize(
    "before,after",
    [
        (None, "unregistered"),
        ("glibc_two_arenas_128k", None),
        ("glibc_two_arenas_128k", "unregistered"),
    ],
)
def test_recovery_cannot_replace_or_remove_registered_allocator_policy(before, after):
    parent, candidate = {"resources": {}}, {"resources": {}}
    if before is not None:
        parent["resources"]["host_allocator_policy"] = before
    if after is not None:
        candidate["resources"]["host_allocator_policy"] = after
    with pytest.raises(ValueError, match="protocol"):
        recovery.protocol_change(parent, candidate)


def timed_child(tmp_path, parent, original):
    output, record = child(tmp_path, parent, original)
    record["component_protocol"]["resources"]["replay_subprocess_timeout_seconds"] = 1800
    replacements, report = recovery.replay_timeout_adjustment(
        parent / "source", original["component_protocol"], record["component_protocol"]
    )
    for name, changed in replacements.items():
        (output / "source" / name).write_bytes(changed.encode())
    record["test_resource_adjustments"] = report
    record["sources_sha256"] = runner.files(output / "source")
    runner.write_json(
        output / "component-protocol.json", record["component_protocol"], replace=True
    )
    record["component_protocol_sha256"] = runner.digest(output / "component-protocol.json")
    runner.write_json(output / "registration.json", record, replace=True)
    return output, record


@pytest.mark.parametrize("interrupted", [True], indirect=True)
def test_replay_timer_recovery_preserves_all_checks_and_outer_limits(
    interrupted, tmp_path, monkeypatch
):
    parent, original, _, execute = interrupted
    before = recovery.parent_binding(parent)
    output, record = timed_child(tmp_path, parent, original)
    original_test = (parent / "source" / recovery.REPLAY_TEST).read_bytes()
    changed_test = (output / "source" / recovery.REPLAY_TEST).read_bytes()
    assert changed_test == original_test.replace(b"900,", b"1800,").replace(b"600,", b"1800,")
    calls = []

    def remaining(command, **kwargs):
        calls.append((kwargs["env"]["CELLS_COMPONENT_BACKEND"], kwargs["directory"].name))
        assert (
            kwargs["max_rss_bytes"]
            == original["component_protocol"]["resources"]["max_worker_rss_bytes"]
        )
        assert (
            kwargs["min_available_bytes"]
            == original["component_protocol"]["resources"]["min_available_host_memory_bytes"]
        )
        return execute(command, **kwargs)

    monkeypatch.setattr(runner, "run_bounded", remaining)
    runner.component_worker(output, record)
    assert calls == [("gpu", "part-02")]
    result = recovery.read(output / "result.json")
    assert result["recovery"]["test_resource_adjustments"] == record["test_resource_adjustments"]
    assert result["recovery"]["resource_policy_change"] == {
        "replay_subprocess_timeout_seconds": {
            "before": {"phases": 900, "fresh_cli": 600},
            "after": 1800,
        }
    }
    assert record["max_wall_seconds"] == original["max_wall_seconds"]
    assert record["test_nodes"] == original["test_nodes"]
    assert recovery.parent_binding(parent) == before


@pytest.mark.parametrize("interrupted", [True], indirect=True)
@pytest.mark.parametrize(
    "fault",
    ["assertion", "command", "timer", "missing_record", "wrong_record", "outer_wall", "memory"],
)
def test_replay_timer_change_cannot_hide_other_changes(interrupted, tmp_path, fault):
    parent, original, _, _ = interrupted
    output, record = timed_child(tmp_path, parent, original)
    path = output / "source" / recovery.REPLAY_TEST
    if fault in ("assertion", "command", "timer"):
        a, b = {
            "assertion": ("assert True", "assert False"),
            "command": ('"fresh"', '"skip"'),
            "timer": ("1800,", "3600,"),
        }[fault]
        path.write_text(path.read_text().replace(a, b))
        record["sources_sha256"] = runner.files(output / "source")
    elif fault == "missing_record":
        record.pop("test_resource_adjustments")
    elif fault == "wrong_record":
        record["test_resource_adjustments"][recovery.REPLAY_TEST]["after_sha256"] = "0" * 64
    else:
        key = "max_wall_seconds" if fault == "outer_wall" else "max_worker_rss_bytes"
        record["component_protocol"]["resources"][key] *= 2
    with pytest.raises(ValueError, match="Recovery|recovery"):
        recovery.verify(output, record)


@pytest.mark.parametrize("value", [None, True, 1800.0, 600, 900, 1200, 3600])
def test_unregistered_replay_time_budgets_are_rejected(value):
    protocol = {
        "tests": [recovery.REPLAY_TEST],
        "resources": {"replay_subprocess_timeout_seconds": value},
    }
    with pytest.raises(ValueError, match="timeout policy"):
        recovery.validate_replay_timeout(protocol)


@pytest.mark.parametrize(
    "fault", ["duplicate_literal", "missing_literal", "different_test", "replaced_policy"]
)
def test_replay_timer_patch_requires_exact_parent_shape(tmp_path, fault):
    path = tmp_path / recovery.REPLAY_TEST
    path.parent.mkdir(parents=True)
    text = REPLAY_SOURCE
    if fault == "duplicate_literal":
        text += "            600,\n"
    elif fault == "missing_literal":
        text = text.replace("600,", "601,")
    path.write_text(text)
    parent = {"tests": [recovery.REPLAY_TEST], "resources": {}}
    candidate = copy.deepcopy(parent)
    candidate["resources"]["replay_subprocess_timeout_seconds"] = 1800
    if fault == "different_test":
        candidate["tests"] = ["another/test.py"]
    elif fault == "replaced_policy":
        parent["resources"]["replay_subprocess_timeout_seconds"] = 900
    with pytest.raises(ValueError, match="timeout"):
        recovery.replay_timeout_adjustment(tmp_path, parent, candidate)


@pytest.mark.parametrize("interrupted", [True], indirect=True)
@pytest.mark.parametrize("tamper", [False, True])
def test_launcher_binds_only_registered_replay_timer_change(
    interrupted, tmp_path, monkeypatch, tamper
):
    from cells.ensemble import telemetry
    from validation.ensemble import qualification_metrics

    parent, original, _, _ = interrupted
    checkout = tmp_path / "checkout"
    shutil.copytree(parent / "source", checkout)
    protocol = copy.deepcopy(original["component_protocol"])
    protocol["resources"]["replay_subprocess_timeout_seconds"] = 1800
    replacements, adjustments = recovery.replay_timeout_adjustment(
        parent / "source", original["component_protocol"], protocol
    )
    for name, changed in replacements.items():
        (checkout / name).write_text(
            changed.replace("assert True", "assert False") if tamper else changed
        )
    protocol_path = tmp_path / "protocol.json"
    runner.write_json(protocol_path, protocol)
    monkeypatch.setattr(runner, "ROOT", checkout)
    monkeypatch.setattr(telemetry, "devices", lambda *args: [original["gpu"]])
    monkeypatch.setattr(qualification_metrics, "registration", lambda *args: {})
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 0, "\n".join(original["test_nodes"]), ""
        ),
    )
    launched = []

    def detach(command, **kwargs):
        launched.append(command)
        return SimpleNamespace(pid=123456)

    monkeypatch.setattr(runner.subprocess, "Popen", detach)
    output = tmp_path / "launched"
    if tamper:
        with pytest.raises(ValueError, match="differs beyond registered timers"):
            runner.launch_component(output, protocol_path, tmp_path, parent=parent)
        assert not launched
        return
    runner.launch_component(output, protocol_path, tmp_path, parent=parent)
    assert len(launched) == 1
    record = recovery.read(output / "registration.json")
    assert record["test_resource_adjustments"] == adjustments
    recovery.verify(output, record)
