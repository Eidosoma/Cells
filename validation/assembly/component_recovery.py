"""Reuse complete component groups after a resource stop, with unchanged science."""

import copy
import hashlib
import json
import shutil
from pathlib import Path

from cells.assembly.io import digest

CONTROLLERS = {
    "validation/assembly/qualify_cell.py",
    "validation/assembly/component_recovery.py",
    "validation/assembly/component_process.py",
}
REPLAY_TEST = "tests/unit/test_surface_mobile_pump_repair.py"


def validate_replay_timeout(protocol):
    resources = protocol["resources"]
    if "replay_subprocess_timeout_seconds" not in resources:
        return
    value = resources["replay_subprocess_timeout_seconds"]
    if type(value) is not int or value != 1800 or REPLAY_TEST not in protocol.get("tests", []):
        raise ValueError("Unknown component replay subprocess timeout policy")


def replay_timeout_adjustment(source, parent_protocol, candidate_protocol):
    """Permit only two wall-clock literals to change in this replay test.

    Reconstruct the candidate from the frozen source; never trust arbitrary
    checkout test edits when reusing numerical evidence. Assertions, commands,
    scientific inputs and the outer job/memory limits remain byte-for-byte.
    """
    validate_replay_timeout(candidate_protocol)
    before = parent_protocol["resources"].get("replay_subprocess_timeout_seconds")
    after = candidate_protocol["resources"].get("replay_subprocess_timeout_seconds")
    if before == after:
        return {}, {}
    if (
        before is not None
        or type(after) is not int
        or after != 1800
        or REPLAY_TEST not in parent_protocol["tests"]
    ):
        raise ValueError("Recovery cannot change this replay subprocess timeout")
    original = (source / REPLAY_TEST).read_bytes().decode("utf-8")
    changed = original
    for seconds in (900, 600):
        old = f"            {seconds},\n"
        if changed.count(old) != 1:
            raise ValueError("Recovery replay timeout source no longer matches")
        changed = changed.replace(old, "            1800,\n", 1)
    report = {
        REPLAY_TEST: {
            "before_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "after_sha256": hashlib.sha256(changed.encode()).hexdigest(),
            "phase_timeout_seconds": {"before": 900, "after": 1800},
            "fresh_cli_timeout_seconds": {"before": 600, "after": 1800},
            "assertions_commands_and_inputs_unchanged": True,
        }
    }
    return {REPLAY_TEST: changed}, report


def protocol_change(parent, candidate):
    """Allow narrow allocator/replay-clock policies; science and outer limits stay fixed."""
    validate_replay_timeout(candidate)
    if parent == candidate:
        return None
    original_metric = parent["resources"].get("process_tree_memory_metric", "rss")
    normalized = copy.deepcopy(candidate)
    resources = normalized["resources"]
    changes = {}
    if original_metric == "rss" and resources.get("process_tree_memory_metric") == "pss":
        resources.pop("process_tree_memory_metric")
        if "process_tree_memory_metric" in parent["resources"]:
            resources["process_tree_memory_metric"] = original_metric
        changes["process_tree_memory_metric"] = {"before": "rss", "after": "pss"}
    if (
        "host_allocator_policy" not in parent["resources"]
        and resources.get("host_allocator_policy") == "glibc_two_arenas_128k"
    ):
        resources.pop("host_allocator_policy")
        changes["host_allocator_policy"] = {"before": None, "after": "glibc_two_arenas_128k"}
    if (
        "replay_subprocess_timeout_seconds" not in parent["resources"]
        and type(resources.get("replay_subprocess_timeout_seconds")) is int
        and resources["replay_subprocess_timeout_seconds"] == 1800
    ):
        resources.pop("replay_subprocess_timeout_seconds")
        changes["replay_subprocess_timeout_seconds"] = {
            "before": {"phases": 900, "fresh_cli": 600},
            "after": 1800,
        }
    if changes and normalized == parent:
        return changes
    raise ValueError("Recovery cannot change scientific protocol or outer resource limits")


def read(path):
    return json.loads(path.read_text())


def payloads(root):
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Recovery payload must not be a symbolic link")
        if path.is_file():
            result[str(path.relative_to(root))] = digest(path)
    return result


def parent_binding(path):
    """Authenticate the full CPU phase and the completed prefix of GPU groups."""
    from validation.assembly.qualify_cell import (
        collection_nodes,
        component_groups,
        component_suite,
        files,
        verify_component_cpu_inputs,
    )

    path = path.resolve()
    record, failure = read(path / "registration.json"), read(path / "failure.json")
    protocol = read(path / "component-protocol.json")
    if (
        record.get("component_recovery")
        or failure.get("status") != "failed"
        or failure.get("phase") != "gpu"
        or read(path / "status.json").get("status") != "failed"
        or (path / "completion.json").exists()
        or protocol != record["component_protocol"]
        or digest(path / "component-protocol.json") != record["component_protocol_sha256"]
        or files(path / "source") != record["sources_sha256"]
        or collection_nodes(path / "collection.log") != record["test_nodes"]
        or protocol.get("automatic_followup") is not False
    ):
        raise ValueError("Recovery requires an unchanged original component GPU resource stop")
    groups = component_groups(protocol, record["test_nodes"])
    if groups != record["test_groups"]:
        raise ValueError("Recovery test groups changed")
    names = [g["name"] for g in groups]
    if failure.get("group") not in names:
        raise ValueError("Recovery failure must identify a registered group")
    stopped = path / "groups/gpu" / failure["group"]
    stop = read(stopped / "resource-stop.json")
    resource_failure = read(stopped / "failure.json")
    reasons = {
        "available_host_memory_reserve",
        "process_tree_rss_allowance",
        "wall_time_allowance",
        "process_tree_pss_allowance",
        "individual_process_rss_allowance",
    }
    if (
        not stop.get("reasons")
        or not set(stop["reasons"]) <= reasons
        or resource_failure.get("status") != "failed"
        or resource_failure.get("cleanup_traceback")
        or "ProcessBudgetExceeded" not in failure.get("traceback", "")
    ):
        raise ValueError("Recovery requires a resource interruption with completed cleanup")
    reused = {"cpu": names, "gpu": names[: names.index(failure["group"])]}
    artifacts, copied = {}, {}
    metadata = [
        path / name
        for name in (
            "registration.json",
            "failure.json",
            "status.json",
            "component-protocol.json",
            "collection.log",
            "cpu.xml",
            "cpu.runtime.json",
            "gpu.runtime.json",
            "gpu-metrics/result.json",
        )
    ] + [stopped / "resource-stop.json", stopped / "failure.json"]
    for backend in ("cpu", "gpu"):
        published = {}
        for group in groups:
            directory = path / "groups" / backend / group["name"]
            if group["name"] not in reused[backend]:
                if (directory / "qualified.json").exists():
                    raise ValueError("Recovery cannot reuse groups after the interrupted group")
                continue
            receipt = read(directory / "qualified.json")
            resources = read(directory / "result.json")
            expected = [n for n in protocol["expected_cpu_skip_nodes"] if n in group["test_nodes"]]
            row, _ = component_suite(
                directory / "tests.xml", group["test_nodes"], expected if backend == "cpu" else []
            )
            if (
                receipt.get("status") != "passed"
                or receipt["test_nodes"] != group["test_nodes"]
                or receipt["suite"] != row
                or receipt["resources"] != resources
                or resources.get("status") != "completed"
                or resources.get("returncode") != 0
                or (directory / "stderr.log").stat().st_size
                or (directory / "failure.json").exists()
                or (directory / "resource-stop.json").exists()
            ):
                raise ValueError("Recovery group receipt, results or logs disagree")
            evidence = payloads(directory / "evidence" / backend)
            if evidence != receipt["evidence_sha256"]:
                raise ValueError("Recovery group evidence changed")
            for name, checksum in evidence.items():
                published.setdefault(name, checksum)
                copied[str((directory / "evidence" / backend / name).relative_to(path))] = checksum
            if "cpu_inputs_sha256" in receipt:
                inputs = directory / "cpu-inputs.json"
                if backend != "gpu" or digest(inputs) != receipt["cpu_inputs_sha256"]:
                    raise ValueError("Recovery CPU input binding changed")
                verify_component_cpu_inputs(path, directory, read(inputs))
                for name, checksum in payloads(directory / "evidence/cpu").items():
                    copied[str((directory / "evidence/cpu" / name).relative_to(path))] = checksum
            for file in directory.iterdir():
                if file.is_file():
                    copied[str(file.relative_to(path))] = digest(file)
        if payloads(path / "evidence" / backend) != published:
            raise ValueError("Recovery published evidence differs from completed group receipts")
        copied.update({f"evidence/{backend}/{n}": v for n, v in published.items()})
    component_suite(path / "cpu.xml", record["test_nodes"], protocol["expected_cpu_skip_nodes"])
    for name in protocol["required_evidence"]:
        if read(path / "evidence/cpu" / (name + ".json")).get("status") != "passed":
            raise ValueError("Recovery CPU evidence is incomplete")
    for file in metadata:
        artifacts[str(file.relative_to(path))] = digest(file)
    # Bind the old measurements as old measurements; the new GPU phase gets its own sampler.
    for name, checksum in read(path / "gpu-metrics/result.json").get("evidence_sha256", {}).items():
        file = path / "gpu-metrics" / name
        if not file.resolve().is_relative_to(path / "gpu-metrics") or digest(file) != checksum:
            raise ValueError("Recovery parent GPU measurements changed")
        artifacts[str(file.relative_to(path))] = checksum
    return {
        "path": str(path),
        "sources_sha256": record["sources_sha256"],
        "parent_files_sha256": artifacts | copied,
        "copied_files_sha256": copied,
        "groups": reused,
        "pending_gpu_groups": names[len(reused["gpu"]) :],
        "runtime": {backend: read(path / f"{backend}.runtime.json") for backend in ("cpu", "gpu")},
        "gpu": record["gpu"],
    }


def copy_groups(output, binding):
    """Copy authenticated files to a fresh output; never link writable parent evidence."""
    parent = Path(binding["path"])
    for name, checksum in binding["copied_files_sha256"].items():
        target = output / name
        if target.exists() or digest(parent / name) != checksum:
            raise ValueError("Recovery copy changed or destination already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent / name, target)


def verify(output, record):
    """Check the parent, copied results and narrowly registered controller/timer changes."""
    from validation.assembly.qualify_cell import files

    binding = record["component_recovery"]
    if parent_binding(Path(binding["path"])) != binding:
        raise ValueError("Recovery parent changed after registration")
    parent = read(Path(binding["path"]) / "registration.json")
    protocol_change(parent["component_protocol"], record["component_protocol"])
    _, adjustments = replay_timeout_adjustment(
        Path(binding["path"]) / "source", parent["component_protocol"], record["component_protocol"]
    )
    expected_sources = dict(binding["sources_sha256"])
    for name, adjustment in adjustments.items():
        expected_sources[name] = adjustment["after_sha256"]
    if (
        {k: v for k, v in files(output / "source").items() if k not in CONTROLLERS}
        != {k: v for k, v in expected_sources.items() if k not in CONTROLLERS}
        or record.get("test_resource_adjustments", {}) != adjustments
        or record["test_nodes"] != parent["test_nodes"]
        or record["test_groups"] != parent["test_groups"]
        or record["gpu"] != binding["gpu"]
        or record["max_wall_seconds"] != parent["max_wall_seconds"]
        or digest(output / "component-protocol.json") != record["component_protocol_sha256"]
        or read(output / "component-protocol.json") != record["component_protocol"]
    ):
        raise ValueError(
            "Recovery requires identical science, device and tests except registered timers"
        )
    if any(digest(output / name) != v for name, v in binding["copied_files_sha256"].items()):
        raise ValueError("Recovery copied evidence changed")
