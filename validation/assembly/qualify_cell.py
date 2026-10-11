"""Detach bounded CPU/GPU coupling qualification with frozen tests and complete logs."""

import argparse
import importlib.util
import json
import math
import os
import resource
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from cells.assembly.cli import output_path, utc
from cells.assembly.io import digest, write_json

ROOT = Path(__file__).resolve().parents[2]
DRIVER = "validation/assembly/qualify_cell.py"
CPU_REUSE_CASES = ("plasma", "gated", "ip3")


def cpu_reuse_requirements(case):
    """Bind every family's CPU arrays and exact GPU-only comparison deferral."""
    if case not in CPU_REUSE_CASES:
        raise ValueError("CPU reuse supports plasma, gated and IP3 chemistry panels")
    groups = [
        ("plasma", "plasma_calcium"),
        ("calcium", "spatial_calcium"),
        ("er", "er_calcium"),
        ("chemistry", "compartment_reactions"),
    ]
    if case in ("gated", "ip3"):
        groups.insert(0, ("cav", "gated_calcium"))
    if case == "ip3":
        groups.insert(0, ("ip3", "ip3_calcium"))
    return groups, {f"tests/unit/test_{module}.py::test_cpu_gpu_agreement" for _, module in groups}


def chemistry_wall_seconds(protocol, cpu_parent, retry_seconds):
    """Keep the frozen protocol; register a separate GPU-retry wall allowance."""
    original = protocol["resources"]["max_wall_seconds"]
    if retry_seconds is None:
        return original
    if (
        not cpu_parent
        or type(retry_seconds) is not int
        or retry_seconds < original
        or retry_seconds <= 0
    ):
        raise ValueError(
            "GPU retry wall allowance requires CPU reuse and cannot shorten the protocol limit"
        )
    return retry_seconds


def cluster_budget(output, protocol):
    limits = protocol["resources"]
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    if size > limits["artifact_and_cache_bytes"]:
        raise ValueError("Qualification artifact/cache allowance exceeded")
    if shutil.disk_usage(output).free < limits["free_disk_reserve_bytes"]:
        raise ValueError("Qualification disk reserve exceeded")
    return size


def cluster_tests(backend):
    paths = [
        "tests/unit/test_assembly_cluster.py",
        "tests/unit/test_assembly_pool.py",
        "tests/unit/test_assembly_cell.py",
    ]
    if backend == "gpu":
        paths.append("tests/integration/test_assembly_cluster_gpu.py")
    return paths


def chemistry_tests(case="reactions"):
    if case == "ip3":
        return ["tests/unit/test_ip3_calcium.py", *chemistry_tests("gated")]
    if case == "gated":
        return ["tests/unit/test_gated_calcium.py", *chemistry_tests("plasma")]
    if case == "plasma":
        return ["tests/unit/test_plasma_calcium.py", *chemistry_tests("spatial")]
    added = []
    if case == "spatial":
        added = ["tests/unit/test_spatial_calcium.py"] + [
            "tests/unit/test_assembly_cluster.py::" + name
            for name in (
                "test_definition_owner_order_and_separate_streams",
                "test_corrupt_state_and_cross_cell_material_transfer_rejected",
                "test_simultaneous_events_at_grid_boundary_use_preceding_assembly",
                "test_one_cell_no_spatial_faces_reduces_to_previous_composition",
            )
        ]
    return (
        added
        + (["tests/unit/test_er_calcium.py"] if case in ("er", "spatial") else [])
        + [
            "tests/unit/test_compartment_reactions.py",
            "tests/unit/test_reaction_transport.py",
            "tests/unit/test_batch_identity.py",
        ]
    )


def chemistry_grid_preflight(path, protocol):
    """Check the default and every registered refinement grid without integration."""
    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.specs import ConfigError, load_spec

    spec = load_spec(path)
    steps = protocol["steps_s"]
    if (
        not isinstance(steps, list)
        or not steps
        or any(type(dt) not in (int, float) or not math.isfinite(dt) or dt <= 0 for dt in steps)
    ):
        raise ValueError("Require explicit positive finite refinement timesteps")
    grids = []
    for dt in dict.fromkeys([spec.execution.dt, *steps]):
        candidate = replace(spec, execution=replace(spec.execution, dt=dt))
        try:
            grid = timeline(candidate)
        except ConfigError as exc:
            raise ConfigError(f"Chemistry grid preflight at dt={dt:g} s: {exc}") from exc
        grids.append(
            {
                "dt_s": dt,
                "steps": len(grid) - 1,
                "trace_working_bytes": trace_bytes(candidate, len(grid) - 1),
                "max_trace_bytes": candidate.execution.max_trace_bytes,
            }
        )
    return {
        "status": "passed",
        "definition_sha256": digest(path),
        "model": spec.to_dict()["model"]["id"],
        "duration_s": spec.experiment.end_time,
        "grids": grids,
        "scope": (
            "Host-only trace budget, event grid and numerical-domain preflight; no integration"
        ),
    }


def files(root):
    return {
        str(p.relative_to(root)): digest(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix in (".py", ".json", ".toml", ".txt")
    }


def collection_nodes(path):
    return [line for line in path.read_text().splitlines() if "::test_" in line]


def launch_component(output, protocol_path, dcgm_root):
    """Use the same frozen-source CPU/L4 runner for a new numerical component."""
    from cells.ensemble.telemetry import devices
    from validation.ensemble.qualification_metrics import registration

    protocol = json.loads(protocol_path.read_text())
    limits = protocol["resources"]
    if protocol.get("automatic_followup") is not False or not protocol["tests"]:
        raise ValueError("Component protocol must name its tests and prohibit automatic followup")
    for name in protocol["tests"]:
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError("Component tests must be real repository files")
    workspace = Path("/mnt/workspaces/Cells")
    available = next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )
    if available < limits["max_worker_rss_bytes"] + 4 * 1024**3:
        raise ValueError("Component qualification host-memory reserve")
    if (
        shutil.disk_usage(workspace).free
        < limits["artifact_and_cache_bytes"] + limits["free_disk_reserve_bytes"]
    ):
        raise ValueError("Component qualification disk reserve")
    gpu = devices("0", 1)[0]
    subprocess.run(["sudo", "-n", "true"], check=True, timeout=10)
    settings = registration(dcgm_root, gpu["uuid"], limits["max_wall_seconds"] + 120)
    output = output_path(output)
    output.mkdir(parents=True)
    source = output / "source"
    for folder in ("src", "tests", "validation", "configs"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and path.suffix in (".py", ".json", ".toml", ".txt"):
                target = source / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    for name in ("pyproject.toml", "requirements-lock.txt"):
        shutil.copyfile(ROOT / name, source / name)
    (output / "cache").mkdir()
    write_json(output / "component-protocol.json", protocol)
    environment = dict(
        os.environ,
        PYTHONPATH=f"{source / 'src'}:{source}",
        PYTHONDONTWRITEBYTECODE="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="1",
        TMPDIR=str(output / "cache"),
        XDG_CACHE_HOME=str(output / "cache"),
    )
    collected = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *protocol["tests"],
        ],
        cwd=source,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    (output / "collection.log").write_text(collected.stdout + collected.stderr)
    nodes = collection_nodes(output / "collection.log")
    if len(nodes) < 1 or len(nodes) != len(set(nodes)):
        raise ValueError("Incomplete component test collection")
    record = {
        "component_protocol": protocol,
        "component_protocol_sha256": digest(output / "component-protocol.json"),
        "sources_sha256": files(source),
        "test_nodes": nodes,
        "workspace": str(workspace),
        "cpu_affinity": [4, 5],
        "gpu": gpu,
        "gpu_metrics": settings,
        "created_utc": utc(),
        "max_wall_seconds": limits["max_wall_seconds"],
        "automatic_followup": False,
    }
    write_json(output / "registration.json", record)
    cluster_budget(output, protocol)
    with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
        child = subprocess.Popen(
            [sys.executable, "-B", str(source / DRIVER), "_component_worker", str(output)],
            cwd=source,
            env=environment,
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    receipt = {"status": "launched", "pid": child.pid, "output": str(output), "utc": utc()}
    write_json(output / "launch.json", receipt)
    return receipt


def component_worker(output, record):
    """Bounded correctness phases; GPU metrics are observations, not speed gates."""
    from validation.ensemble.qualification_metrics import GpuQualificationMetrics

    began = time.monotonic()
    protocol = record["component_protocol"]
    observer = None
    try:
        if (
            files(output / "source") != record["sources_sha256"]
            or digest(output / "component-protocol.json") != record["component_protocol_sha256"]
            or json.loads((output / "component-protocol.json").read_text()) != protocol
        ):
            raise ValueError("Component qualification frozen input changed")
        os.sched_setaffinity(0, record["cpu_affinity"])
        write_json(output / "started.json", {"pid": os.getpid(), "utc": utc()})
        rows, metrics = {}, None
        for backend in ("cpu", "gpu"):
            cluster_budget(output, protocol)
            write_json(
                output / "status.json",
                {"status": "running", "phase": backend, "utc": utc()},
                replace=True,
            )
            cache = output / "cache" / backend
            cache.mkdir()
            source = output / "source"
            environment = dict(
                os.environ,
                PYTHONPATH=f"{source / 'src'}:{source}",
                PYTHONDONTWRITEBYTECODE="1",
                TMPDIR=str(cache),
                XDG_CACHE_HOME=str(cache),
                JAX_COMPILATION_CACHE_DIR=str(cache / "jax"),
                CUDA_CACHE_PATH=str(cache / "cuda"),
                JAX_PLATFORMS="cpu" if backend == "cpu" else "cuda,cpu",
                JAX_ENABLE_X64="1",
                CELLS_COMPONENT_BACKEND=backend,
                CELLS_COMPONENT_EVIDENCE=str(output / "evidence"),
                XLA_PYTHON_CLIENT_PREALLOCATE="false",
                XLA_PYTHON_CLIENT_MEM_FRACTION=str(protocol["resources"]["gpu_memory_fraction"]),
                CUDA_VISIBLE_DEVICES=record["gpu"]["uuid"],
                OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1",
                MKL_NUM_THREADS="1",
            )
            python = str(Path(record["workspace"]) / f"venv-{backend}/bin/python")
            if backend == "gpu":
                observer = GpuQualificationMetrics(output / "gpu-metrics", record["gpu_metrics"])
                observer.start()
            try:
                runtime = subprocess.check_output(
                    [
                        python,
                        "-B",
                        "-c",
                        "import json; from cells.assembly.io import runtime; "
                        "print(json.dumps(runtime()))",
                    ],
                    env=environment,
                    text=True,
                    timeout=30,
                )
                write_json(output / f"{backend}.runtime.json", json.loads(runtime))
                with (
                    (output / f"{backend}.stdout.log").open("x") as out,
                    (output / f"{backend}.stderr.log").open("x") as err,
                ):
                    subprocess.run(
                        [
                            python,
                            "-B",
                            "-m",
                            "pytest",
                            "-x",
                            "-q",
                            "-p",
                            "no:cacheprovider",
                            *protocol["tests"],
                            "--basetemp=" + str(output / f"{backend}-tmp"),
                            "--junitxml=" + str(output / f"{backend}.xml"),
                        ],
                        cwd=source,
                        env=environment,
                        stdout=out,
                        stderr=err,
                        stdin=subprocess.DEVNULL,
                        timeout=max(1, record["max_wall_seconds"] - (time.monotonic() - began)),
                        check=True,
                    )
            finally:
                if observer is not None:
                    metrics = observer.finish(
                        warm_unavailable_reason=(
                            "Correctness suite compiles different kernels throughout; "
                            "no single fully warmed interval is defined"
                        )
                    )
                    observer = None
            suite = ET.parse(output / f"{backend}.xml").getroot().find("testsuite")
            row = {k: int(suite.attrib[k]) for k in ("tests", "failures", "errors", "skipped")}
            actual_nodes = [
                c.attrib["classname"].replace(".", "/") + ".py::" + c.attrib["name"]
                for c in suite.findall("testcase")
            ]
            skipped = [
                c.attrib["classname"].replace(".", "/") + ".py::" + c.attrib["name"]
                for c in suite.findall("testcase")
                if c.find("skipped") is not None
            ]
            expected = protocol["expected_cpu_skip_nodes"] if backend == "cpu" else []
            if (
                sorted(actual_nodes) != sorted(record["test_nodes"])
                or row["tests"] != len(record["test_nodes"])
                or row["failures"]
                or row["errors"]
                or sorted(skipped) != sorted(expected)
            ):
                raise ValueError("Component suite omitted or failed a registered check")
            if (output / f"{backend}.stderr.log").stat().st_size:
                raise ValueError("Unexpected component stderr")
            for name in protocol["required_evidence"] + (
                protocol["required_gpu_evidence"] if backend == "gpu" else []
            ):
                if (
                    json.loads((output / "evidence" / backend / (name + ".json")).read_text())[
                        "status"
                    ]
                    != "passed"
                ):
                    raise ValueError("Missing passing component evidence: " + name)
            rows[backend] = row
            peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
            if peak > protocol["resources"]["max_worker_rss_bytes"]:
                raise ValueError("Component peak child memory allowance exceeded")
            cluster_budget(output, protocol)
        if files(source) != record["sources_sha256"]:
            raise ValueError("Component source changed during execution")
        result = {
            "status": "completed",
            "scope": protocol["scope"],
            "scope_exclusions": protocol["scope_exclusions"],
            "suites": rows,
            "gpu_metrics": metrics,
            "gpu_phase_gpu_hours": metrics["whole_job"]["gpu_busy"]["seconds"] / 3600,
            "peak_child_rss_bytes": peak,
            "elapsed_seconds": time.monotonic() - began,
            "registration_sha256": digest(output / "registration.json"),
            "finished_utc": utc(),
            "automatic_followup": False,
            "artifact_and_cache_bytes": cluster_budget(output, protocol),
        }
        write_json(output / "result.json", result)
        evidence_paths = list((output / "evidence").rglob("*"))
        evidence_paths += [
            output / name
            for name in (
                "component-protocol.json",
                "cpu.xml",
                "gpu.xml",
                "cpu.stdout.log",
                "cpu.stderr.log",
                "gpu.stdout.log",
                "gpu.stderr.log",
                "cpu.runtime.json",
                "gpu.runtime.json",
                "gpu-metrics/result.json",
            )
        ]
        write_json(
            output / "completion.json",
            {
                "status": "completed",
                "result_sha256": digest(output / "result.json"),
                "evidence_sha256": {
                    str(p.relative_to(output)): digest(p) for p in evidence_paths if p.is_file()
                },
            },
        )
        write_json(output / "status.json", {"status": "completed", "utc": utc()}, replace=True)
    except BaseException:
        failure = traceback.format_exc()
        if observer is not None:
            try:
                observer.close()
            except Exception:
                failure += "\nObserver cleanup:\n" + traceback.format_exc()
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "traceback": failure,
                "elapsed_seconds": time.monotonic() - began,
                "utc": utc(),
                "automatic_retry": False,
            },
        )
        write_json(output / "status.json", {"status": "failed", "utc": utc()}, replace=True)
        raise


def cpu_baseline_binding(path):
    """Retain a completed CPU phase after a bounded calcium-panel GPU timeout."""
    path = path.resolve()
    record = json.loads((path / "registration.json").read_text())
    failure = json.loads((path / "failure.json").read_text())
    protocol = json.loads((path / "chemistry-protocol.json").read_text())
    if (
        not record.get("chemistry")
        or record.get("chemistry_case") not in CPU_REUSE_CASES
        or record.get("cpu_baseline")
        or failure.get("status") != "failed"
        or "subprocess.TimeoutExpired" not in failure.get("traceback", "")
        or failure.get("elapsed_seconds", 0) < record["max_wall_seconds"]
        or (path / "completion.json").exists()
        or protocol != record["chemistry_protocol"]
        or files(path / "source") != record["sources_sha256"]
    ):
        raise ValueError("CPU reuse requires an unchanged registered calcium-panel timeout")
    groups, deferrals = cpu_reuse_requirements(record["chemistry_case"])
    # The old worker reaches GPU runtime capture only after its CPU phase's
    # XML, RSS, disk and stderr checks. Preserve that phase transition evidence.
    json.loads((path / "gpu.runtime.json").read_text())
    suite = ET.parse(path / "cpu.xml").getroot().find("testsuite")
    nodes = collection_nodes(path / "cpu.collection.log")
    cases = suite.findall("testcase")
    case_nodes = [
        c.attrib["classname"].replace(".", "/") + ".py::" + c.attrib["name"] for c in cases
    ]
    skipped = {
        node
        for node, case in zip(case_nodes, cases, strict=True)
        if case.find("skipped") is not None
    }
    if (
        case_nodes != nodes
        or len(nodes) != len(set(nodes))
        or len(nodes) != record["chemistry_test_counts"]["cpu"]
        or int(suite.attrib["tests"]) != len(nodes)
        or int(suite.attrib["failures"])
        or int(suite.attrib["errors"])
        or int(suite.attrib["skipped"]) != len(deferrals)
        or skipped != deferrals
        or any(c.find("failure") is not None or c.find("error") is not None for c in cases)
        or (path / "cpu.stderr.log").stat().st_size
        or collection_nodes(path / "gpu.collection.log") != nodes
    ):
        raise ValueError("CPU baseline report is incomplete, failed or has unexpected deferrals")
    evidence = {
        name: digest(path / name)
        for name in ("cpu.xml", "cpu.stdout.log", "cpu.stderr.log", "cpu.runtime.json")
    }
    for group, _ in groups:
        directory = path / (group + "-evidence/cpu")
        baseline = json.loads((directory / "baseline.json").read_text())
        if baseline.get("status") != "passed" or not (directory / "baseline.npz").is_file():
            raise ValueError("Missing saved CPU baseline arrays/evidence")
        if group in ("ip3", "cav", "plasma", "calcium"):
            coupled = json.loads((directory / "assembly-baseline.json").read_text())
            if (
                coupled.get("status") != "passed"
                or not (directory / "assembly-baseline.npz").is_file()
            ):
                raise ValueError("Missing saved CPU assembly baseline arrays/evidence")
        evidence.update(
            {str(p.relative_to(path)): digest(p) for p in directory.rglob("*") if p.is_file()}
        )
    return {
        "path": str(path),
        "chemistry_case": record["chemistry_case"],
        "registration_sha256": digest(path / "registration.json"),
        "failure_sha256": digest(path / "failure.json"),
        "gpu_runtime_sha256": digest(path / "gpu.runtime.json"),
        "source_files_sha256": record["sources_sha256"],
        "cpu_files_sha256": evidence,
        "test_nodes": nodes,
        "cpu_suite": dict(suite.attrib),
    }


def verify_cpu_baseline(output, binding):
    if cpu_baseline_binding(Path(binding["path"])) != binding:
        raise ValueError("Registered CPU parent changed")
    expected = {k: v for k, v in binding["source_files_sha256"].items() if k != DRIVER}
    actual = {k: v for k, v in files(output / "source").items() if k != DRIVER}
    if actual != expected:
        raise ValueError("CPU reuse requires identical simulation, tests, inputs and native source")
    if json.loads((output / "chemistry-protocol.json").read_text()) != json.loads(
        (Path(binding["path"]) / "chemistry-protocol.json").read_text()
    ):
        raise ValueError("CPU reuse requires an unchanged scientific and resource protocol")
    if any(
        digest(output / name) != expected for name, expected in binding["cpu_files_sha256"].items()
    ):
        raise ValueError("Copied CPU baseline evidence changed")
    if any(
        collection_nodes(output / f"{backend}.collection.log") != binding["test_nodes"]
        for backend in ("cpu", "gpu")
    ):
        raise ValueError("CPU reuse changed the registered test identities or order")


def baseline_profiles(path):
    """Authenticate the completed pilot used to define the larger local workload."""
    path = path.resolve()
    done = json.loads((path / "completion.json").read_text())
    result = json.loads((path / "result.json").read_text())
    record = json.loads((path / "registration.json").read_text())
    if (
        done["status"] != "completed"
        or done["result_sha256"] != digest(path / "result.json")
        or result["status"] != "integrated_ensemble_qualification_and_profile_pass"
        or files(path / "source") != record["sources_sha256"]
    ):
        raise ValueError("Require an authenticated completed integrated baseline")
    for name, expected in done["files_sha256"].items():
        if digest(path / name) != expected:
            raise ValueError("Baseline qualification artifact changed: " + name)
    definitions = {}
    for name, expected in record["profile_definitions_sha256"].items():
        definition = path / f"{name}.definition.json"
        if digest(definition) != expected:
            raise ValueError("Baseline profile definition changed")
        definitions[name] = json.loads(definition.read_text())
        profile = path / (name + "-profile")
        row = json.loads((profile / "result.json").read_text())
        complete = json.loads((profile / "completion.json").read_text())
        if (
            row["status"] != "completed"
            or digest(profile / "result.json") != result["profiles"][name]["result_sha256"]
            or complete["result_sha256"] != digest(profile / "result.json")
            or row["registration_sha256"] != digest(profile / "registration.json")
        ):
            raise ValueError("Baseline profile receipt changed")
    if set(definitions) != {"assembly_cell", "ionic"}:
        raise ValueError("Baseline profile families differ")
    return definitions, {
        "path": str(path),
        "completion_sha256": digest(path / "completion.json"),
        "result_sha256": digest(path / "result.json"),
        "registration_sha256": digest(path / "registration.json"),
        "profile_definitions_sha256": record["profile_definitions_sha256"],
        "profiles": result["profiles"],
    }


def worker(output):
    began = time.monotonic()
    try:
        record = json.loads((output / "registration.json").read_text())
        if files(output / "source") != record["sources_sha256"]:
            raise ValueError("Coupled qualification frozen source mismatch")
        cpu_parent = record.get("cpu_baseline")
        if cpu_parent:
            verify_cpu_baseline(output, cpu_parent)
        os.sched_setaffinity(0, record["cpu_affinity"])
        write_json(output / "started.json", {"pid": os.getpid(), "utc": utc()})
        rows = {}
        integrated = record.get("ensemble_profile", False)
        cluster = record.get("cluster", False)
        chemistry = record.get("chemistry", False)
        ip3 = record.get("chemistry_case") == "ip3"
        cav = record.get("chemistry_case") in ("gated", "ip3")
        plasma = record.get("chemistry_case") in ("plasma", "gated", "ip3")
        calcium = record.get("chemistry_case") in ("spatial", "plasma", "gated", "ip3")
        er = record.get("chemistry_case") in ("er", "spatial", "plasma", "gated", "ip3")
        bounded = cluster or chemistry
        protocol = record.get("chemistry_protocol") if chemistry else record.get("cluster_protocol")
        if chemistry and json.loads((output / "chemistry-protocol.json").read_text()) != protocol:
            raise ValueError("Registered chemistry protocol changed")
        if chemistry and record["max_wall_seconds"] != chemistry_wall_seconds(
            protocol, cpu_parent, record.get("gpu_retry_wall_seconds")
        ):
            raise ValueError("Registered chemistry wall allowance changed")
        if cpu_parent and record["chemistry_case"] != cpu_parent["chemistry_case"]:
            raise ValueError("CPU baseline belongs to a different chemistry panel")
        if chemistry and (
            json.loads((output / "chemistry-preflight.json").read_text())
            != record["chemistry_preflight"]
        ):
            raise ValueError("Registered chemistry grid preflight changed")
        if (
            cluster
            and json.loads((output / "cluster-protocol.json").read_text())
            != record["cluster_protocol"]
        ):
            raise ValueError("Registered cluster protocol changed")
        partition_parent = record.get("partition_parent")
        if partition_parent:
            environment = dict(
                os.environ,
                PYTHONPATH=str(Path(partition_parent["path"]) / "source/src"),
                PYTHONDONTWRITEBYTECODE="1",
                JAX_PLATFORMS="cpu",
                JAX_ENABLE_X64="1",
                OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1",
                TMPDIR=str(output / "cache"),
                XDG_CACHE_HOME=str(output / "cache"),
                JAX_COMPILATION_CACHE_DIR=str(output / "cache/parent-replay-jax"),
            )
            with (
                (output / "partition-parent.stdout.log").open("x") as out,
                (output / "partition-parent.stderr.log").open("x") as err,
            ):
                subprocess.run(
                    [
                        str(Path(record["workspace"]) / "venv-cpu/bin/python"),
                        "-B",
                        str(output / "source/validation/assembly/cluster_partition_replay.py"),
                        str(output),
                    ],
                    env=environment,
                    stdout=out,
                    stderr=err,
                    stdin=subprocess.DEVNULL,
                    check=True,
                    timeout=record["partition_replay_max_seconds"],
                )
            if (output / "partition-parent.stderr.log").stat().st_size:
                raise ValueError("Unexpected parent partition replay stderr")
        for backend in ("cpu", "gpu"):
            if bounded:
                cluster_budget(output, protocol)
            if backend == "gpu" and record["gpu_after"] is not None:
                predecessor = Path(record["gpu_after"]["path"])
                if (
                    digest(predecessor / "registration.json")
                    != record["gpu_after"]["registration_sha256"]
                ):
                    raise ValueError("Registered preceding GPU workload changed")
                write_json(
                    output / "gpu-wait.json", {"utc": utc(), "predecessor": str(predecessor)}
                )
                while not any(
                    (predecessor / name).exists()
                    for name in ("completion.json", "failure.json", "paused.json")
                ):
                    if time.monotonic() - began > record["max_wall_seconds"]:
                        raise TimeoutError(
                            "Coupled GPU qualification wait exceeded its registered budget"
                        )
                    time.sleep(1)
            environment = os.environ.copy()
            environment.update(
                PYTHONDONTWRITEBYTECODE="1",
                PYTHONPATH=str(output / "source/src"),
                TMPDIR=str(output / "cache"),
                XDG_CACHE_HOME=str(output / "cache"),
                JAX_COMPILATION_CACHE_DIR=str(output / "cache/jax"),
                CUDA_CACHE_PATH=str(output / "cache/cuda"),
                JAX_PLATFORMS="cpu" if backend == "cpu" else "cuda,cpu",
                CELLS_COUPLED_TEST_BACKEND=backend,
                JAX_ENABLE_X64="1",
                XLA_PYTHON_CLIENT_PREALLOCATE="false",
                OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1",
            )
            if chemistry:
                environment.update(
                    CELLS_CHEMISTRY_TEST_BACKEND=backend,
                    CELLS_CHEMISTRY_EVIDENCE=str(output / "chemistry-evidence"),
                    XLA_PYTHON_CLIENT_MEM_FRACTION=str(
                        protocol["resources"]["gpu_memory_fraction"]
                    ),
                )
                if er:
                    environment.update(
                        CELLS_ER_TEST_BACKEND=backend,
                        CELLS_ER_EVIDENCE=str(output / "er-evidence"),
                        CELLS_ER_NATIVE_SOURCE=str(output / "source/validation/chemistry/native"),
                    )
                if calcium:
                    environment.update(
                        CELLS_CALCIUM_TEST_BACKEND=backend,
                        CELLS_CALCIUM_EVIDENCE=str(output / "calcium-evidence"),
                    )
                if plasma:
                    environment.update(
                        CELLS_PLASMA_TEST_BACKEND=backend,
                        CELLS_PLASMA_EVIDENCE=str(output / "plasma-evidence"),
                    )
                if cav:
                    environment.update(
                        CELLS_CAV_TEST_BACKEND=backend,
                        CELLS_CAV_EVIDENCE=str(output / "cav-evidence"),
                        CELLS_CAV_NATIVE_SOURCE=str(output / "source/validation/chemistry/native"),
                    )
                if ip3:
                    environment.update(
                        CELLS_IP3_TEST_BACKEND=backend,
                        CELLS_IP3_EVIDENCE=str(output / "ip3-evidence"),
                    )
                tests = [
                    str(output / "source" / p)
                    for p in chemistry_tests(record.get("chemistry_case", "reactions"))
                ]
            elif cluster:
                environment.update(
                    CELLS_POOL_TEST_BACKEND=backend,
                    CELLS_TEST_GPU="1" if backend == "gpu" else "0",
                    CELLS_CLUSTER_EVIDENCE=str(output / "cluster-evidence"),
                    XLA_PYTHON_CLIENT_MEM_FRACTION=str(
                        record["cluster_protocol"]["resources"]["gpu_memory_fraction"]
                    ),
                )
                tests = [str(output / "source" / p) for p in cluster_tests(backend)]
            elif integrated:
                environment.update(
                    CELLS_TEST_GPU="1" if backend == "gpu" else "0",
                    CELLS_INTEGRATED_EVIDENCE=str(output / "parity"),
                )
                tests = [
                    str(output / "source/tests/unit/test_integrated_ensemble.py"),
                    str(output / "source/tests/unit/test_batch_identity.py"),
                ]
                if backend == "gpu":
                    tests.extend(
                        [
                            str(
                                output / "source/tests/integration/test_integrated_ensemble_gpu.py"
                            ),
                            str(output / "source/tests/integration/test_ensemble_gpu.py")
                            + "::test_two_gpu_workers_and_measured_balance_command",
                        ]
                    )
            else:
                tests = [str(output / "source/tests/unit/test_assembly_cell.py")]
            python = str(Path(record["workspace"]) / f"venv-{backend}/bin/python")
            runtime = subprocess.check_output(
                [
                    python,
                    "-B",
                    "-c",
                    "import json; from cells.assembly.io import runtime; "
                    "print(json.dumps(runtime()))",
                ],
                text=True,
                env=environment,
                timeout=30,
            )
            current_runtime = json.loads(runtime)
            if cpu_parent and backend == "cpu":
                if current_runtime != json.loads((output / "cpu.runtime.json").read_text()):
                    raise ValueError("Saved CPU baseline runtime differs from the current runtime")
                rows["cpu"] = cpu_parent["cpu_suite"]
                write_json(
                    output / "cpu-reuse.json",
                    {
                        "status": "authenticated_cpu_phase_reused",
                        "parent": cpu_parent["path"],
                        "parent_registration_sha256": cpu_parent["registration_sha256"],
                        "cpu_report_sha256": digest(output / "cpu.xml"),
                        "identical_source_except_runner": True,
                        "runtime_unchanged": True,
                        "gpu_phase": "fresh_full_panel",
                        "gpu_retry_wall_seconds": record["max_wall_seconds"],
                        "frozen_protocol_wall_seconds": protocol["resources"]["max_wall_seconds"],
                        "utc": utc(),
                    },
                )
                continue
            write_json(output / f"{backend}.runtime.json", current_runtime)
            with (
                (output / f"{backend}.stdout.log").open("x") as out,
                (output / f"{backend}.stderr.log").open("x") as err,
            ):
                monitor = None
                if bounded and backend == "gpu":
                    with (output / "gpu-utilization.csv").open("x") as telemetry:
                        monitor = subprocess.Popen(
                            [
                                "nvidia-smi",
                                "--query-gpu=timestamp,utilization.gpu,memory.used",
                                "--format=csv,noheader,nounits",
                                "--loop-ms=1000",
                            ],
                            stdout=telemetry,
                            stderr=err,
                            stdin=subprocess.DEVNULL,
                        )
                try:
                    subprocess.run(
                        [
                            python,
                            "-B",
                            "-m",
                            "pytest",
                            *(["-x"] if bounded else []),
                            *tests,
                            *(["-v", "--durations=12"] if cpu_parent or cav else ["-q"]),
                            "--basetemp=" + str(output / f"{backend}-tmp"),
                            "-o",
                            "cache_dir=" + str(output / "cache/pytest"),
                            "--junitxml=" + str(output / f"{backend}.xml"),
                        ],
                        stdout=out,
                        stderr=err,
                        env=environment,
                        cwd=output / "source",
                        timeout=max(1, record["max_wall_seconds"] - (time.monotonic() - began)),
                        check=True,
                    )
                finally:
                    if monitor is not None:
                        monitor.terminate()
                        monitor.wait(timeout=10)
            suite = ET.parse(output / f"{backend}.xml").getroot().find("testsuite")
            row = dict(suite.attrib)
            if (
                int(row["failures"])
                or int(row["errors"])
                or int(row["skipped"])
                != (
                    (
                        (
                            6
                            if ip3
                            else 5
                            if cav
                            else 4
                            if plasma
                            else 3
                            if calcium
                            else 2
                            if er
                            else 1
                        )
                        if backend == "cpu"
                        else 0
                    )
                    if chemistry
                    else (3 if backend == "cpu" else 0)
                    if cluster
                    else (0 if integrated else backend == "cpu")
                )
                or (
                    int(row["tests"]) != record["chemistry_test_counts"][backend]
                    if chemistry
                    else int(row["tests"]) != record["cluster_test_counts"][backend]
                    if cluster
                    else int(row["tests"])
                    != ((12 if backend == "cpu" else 18) if integrated else 6)
                )
            ):
                raise ValueError("Qualification failed or skipped a required coupling check")
            rows[backend] = row
            if bounded:
                cluster_budget(output, protocol)
                peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
                if peak > protocol["resources"]["max_worker_rss_bytes"]:
                    raise ValueError("Qualification host memory allowance exceeded")
                if (output / f"{backend}.stderr.log").stat().st_size:
                    raise ValueError("Unexpected qualification stderr")
        profiles = {}
        if integrated:
            write_json(
                output / "qualification.json",
                {
                    "status": "integrated_ensemble_cpu_gpu_pass",
                    "suites": rows,
                    "elapsed_seconds": time.monotonic() - began,
                },
            )
            for name, expected in record["profile_definitions_sha256"].items():
                definition = output / f"{name}.definition.json"
                if digest(definition) != expected:
                    raise ValueError("Registered integrated profile definition changed")
                directory = output / (name + "-profile")
                with (
                    (output / f"{name}.stdout.log").open("x") as out,
                    (output / f"{name}.stderr.log").open("x") as err,
                ):
                    subprocess.run(
                        [
                            python,
                            "-B",
                            "-m",
                            "cells.ensemble",
                            "run",
                            str(definition),
                            "--output",
                            str(directory),
                            "--devices",
                            "0",
                            "--allocated-gpus",
                            "1",
                        ],
                        env=environment,
                        stdout=out,
                        stderr=err,
                        check=True,
                        timeout=min(
                            960, max(1, record["max_wall_seconds"] - (time.monotonic() - began))
                        ),
                    )
                complete = json.loads((directory / "completion.json").read_text())
                if complete["result_sha256"] != digest(directory / "result.json"):
                    raise ValueError("Integrated profile result hash changed")
                result = json.loads((directory / "result.json").read_text())
                if result["status"] != "completed":
                    raise ValueError("Integrated throughput pilot did not complete")
                profiles[name] = {
                    "path": str(directory),
                    "result_sha256": digest(directory / "result.json"),
                    "elapsed_seconds": result["elapsed_seconds"],
                    "throughput": result["throughput"],
                    "full_job_utilization": result["full_job_utilization"],
                    "after_all_workers_warmed": result["after_all_workers_warmed"],
                }
        if files(output / "source") != record["sources_sha256"]:
            raise ValueError("Qualification source changed during execution")
        if cpu_parent:
            verify_cpu_baseline(output, cpu_parent)
        cluster_result = {}
        chemistry_result = {}
        if chemistry:
            evidence = output / "chemistry-evidence"
            for backend in ("cpu", "gpu"):
                for name in (
                    "baseline",
                    "independent-reference",
                    "controls",
                    "replay",
                    "public-cli",
                ):
                    if (
                        json.loads((evidence / backend / (name + ".json")).read_text())["status"]
                        != "passed"
                    ):
                        raise ValueError("Missing required chemistry evidence")
            comparison = json.loads((evidence / "gpu/cpu-gpu.json").read_text())
            if comparison["status"] != "passed":
                raise ValueError("Chemical CPU/GPU comparison did not pass")
            chemistry_result = {
                "chemistry_protocol_sha256": digest(output / "chemistry-protocol.json"),
                "cpu_gpu": comparison,
                "artifact_and_cache_bytes": cluster_budget(output, protocol),
                "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
                * 1024,
                "automatic_followup": False,
                "finished_utc": utc(),
            }
            if er:
                er_evidence = output / "er-evidence"
                for backend in ("cpu", "gpu"):
                    for name in (
                        "baseline",
                        "independent-reference",
                        "controls",
                        "replay",
                        "public-cli",
                        "native-laws",
                    ):
                        if (
                            json.loads((er_evidence / backend / (name + ".json")).read_text())[
                                "status"
                            ]
                            != "passed"
                        ):
                            raise ValueError("Missing required ER numerical/source evidence")
                er_comparison = json.loads((er_evidence / "gpu/cpu-gpu.json").read_text())
                if er_comparison["status"] != "passed":
                    raise ValueError("ER CPU/GPU comparison failed")
                chemistry_result["er_cpu_gpu"] = er_comparison
            if calcium:
                calcium_evidence = output / "calcium-evidence"
                for backend in ("cpu", "gpu"):
                    for name in (
                        "baseline",
                        "ownership",
                        "independent-reference",
                        "replay",
                        "public-cli",
                        "control-plasma_ca_off",
                        "control-release_switch",
                        "control-internal_off",
                        "control-external_off",
                        "assembly-baseline",
                        "assembly-reference",
                        "assembly-replay",
                        "ensemble",
                    ):
                        if (
                            json.loads((calcium_evidence / backend / (name + ".json")).read_text())[
                                "status"
                            ]
                            != "passed"
                        ):
                            raise ValueError("Missing required spatial calcium/assembly evidence")
                comparison = json.loads((calcium_evidence / "gpu/cpu-gpu.json").read_text())
                if comparison["status"] != "passed":
                    raise ValueError("Spatial calcium CPU/GPU correspondence failed")
                chemistry_result["spatial_calcium_cpu_gpu"] = comparison
            if plasma:
                plasma_evidence = output / "plasma-evidence"
                for backend in ("cpu", "gpu"):
                    for name in (
                        "baseline",
                        "native-laws",
                        "ncx-law",
                        "ownership",
                        "independent-reference",
                        "replay",
                        "public-cli",
                        "control-pump_off",
                        "control-exchanger_off",
                        "control-both_off",
                        "control-absent",
                        "control-zero_capacity",
                        "control-switch",
                        "assembly-baseline",
                        "assembly-reference",
                        "assembly-replay",
                        "ensemble",
                    ):
                        row = json.loads((plasma_evidence / backend / (name + ".json")).read_text())
                        if row["status"] != "passed":
                            raise ValueError("Missing required plasma transport/assembly evidence")
                comparison = json.loads((plasma_evidence / "gpu/cpu-gpu.json").read_text())
                if comparison["status"] != "passed":
                    raise ValueError("Plasma calcium CPU/GPU correspondence failed")
                chemistry_result["plasma_calcium_cpu_gpu"] = comparison
            if cav:
                cav_evidence = output / "cav-evidence"
                for backend in ("cpu", "gpu"):
                    for name in (
                        "baseline",
                        "native-laws",
                        "ownership",
                        "independent-reference",
                        "replay",
                        "public-cli",
                        "control-blocked",
                        "control-zero_permeability",
                        "control-zero_abundance",
                        "control-switch",
                        "assembly-baseline",
                        "assembly-reference",
                        "assembly-replay",
                        "ensemble",
                    ):
                        row = json.loads((cav_evidence / backend / (name + ".json")).read_text())
                        if row["status"] != "passed":
                            raise ValueError("Missing required gated calcium/assembly evidence")
                comparison = json.loads((cav_evidence / "gpu/cpu-gpu.json").read_text())
                if comparison["status"] != "passed":
                    raise ValueError("Gated calcium CPU/GPU correspondence failed")
                chemistry_result["gated_calcium_cpu_gpu"] = comparison
            if ip3:
                ip3_evidence = output / "ip3-evidence"
                for backend in ("cpu", "gpu"):
                    for name in (
                        "baseline",
                        "native-laws",
                        "ownership",
                        "independent-reference",
                        "replay",
                        "public-cli",
                        "control-blocked",
                        "control-binding_off",
                        "control-switch",
                        "assembly-baseline",
                        "assembly-reference",
                        "assembly-replay",
                        "ensemble",
                    ):
                        row = json.loads((ip3_evidence / backend / (name + ".json")).read_text())
                        if row["status"] != "passed":
                            raise ValueError("Missing required IP3 calcium/assembly evidence")
                comparison = json.loads((ip3_evidence / "gpu/cpu-gpu.json").read_text())
                if comparison["status"] != "passed":
                    raise ValueError("IP3 calcium CPU/GPU correspondence failed")
                chemistry_result["ip3_calcium_cpu_gpu"] = comparison
        if cluster:
            evidence = output / "cluster-evidence"
            required = (
                "baseline",
                "independent-reference",
                "neighbour-response",
                "replay",
                "simultaneous-grid-events",
                "one-cell-reduction",
                "scheduler-adapter",
                "expected-event-budget-fault",
            )
            for backend in ("cpu", "gpu"):
                for name in required:
                    row = json.loads((evidence / backend / (name + ".json")).read_text())
                    expected = (
                        "expected_refusal" if name == "expected-event-budget-fault" else "passed"
                    )
                    if name != "baseline" and row["status"] != expected:
                        raise ValueError("Missing required cluster numerical evidence")
            for name in ("cpu-gpu-comparison", "queue"):
                if (
                    json.loads((evidence / "gpu" / (name + ".json")).read_text())["status"]
                    != "passed"
                ):
                    raise ValueError("Cluster GPU validation did not complete")
            samples = [
                float(line.split(",")[1])
                for line in (output / "gpu-utilization.csv").read_text().splitlines()
            ]
            if not samples:
                raise ValueError("Missing GPU phase telemetry")
            cluster_result = {
                "cluster_protocol_sha256": digest(output / "cluster-protocol.json"),
                "neighbour_response": {
                    backend: json.loads(
                        (evidence / backend / "neighbour-response.json").read_text()
                    )
                    for backend in ("cpu", "gpu")
                },
                "cpu_gpu": json.loads((evidence / "gpu/cpu-gpu-comparison.json").read_text()),
                "queue": json.loads((evidence / "gpu/queue.json").read_text()),
                "gpu_utilization": {
                    "scope": "Whole GPU correctness phase including compilation and host checks",
                    "samples": len(samples),
                    "mean_percent": sum(samples) / len(samples),
                    "max_percent": max(samples),
                    "advisory_target_pct": 70,
                    "qualification_requires_target": False,
                },
                "artifact_and_cache_bytes": cluster_budget(output, record["cluster_protocol"]),
                "peak_child_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
                * 1024,
                "automatic_followup": False,
                "finished_utc": utc(),
                "partition_parent_replay": (
                    json.loads((output / "partition-parent-replay/result.json").read_text())
                    if partition_parent
                    else None
                ),
            }
        write_json(
            output / "result.json",
            {
                "status": "ip3_calcium_assembly_cpu_gpu_qualification_pass"
                if ip3
                else "gated_calcium_assembly_cpu_gpu_qualification_pass"
                if cav
                else "plasma_calcium_assembly_cpu_gpu_qualification_pass"
                if plasma
                else "spatial_calcium_assembly_cpu_gpu_qualification_pass"
                if calcium
                else "er_calcium_cpu_gpu_qualification_pass"
                if er
                else "compartment_chemistry_cpu_gpu_qualification_pass"
                if chemistry
                else "assembly_cluster_cpu_gpu_qualification_pass"
                if cluster
                else "integrated_ensemble_qualification_and_profile_pass"
                if integrated
                else "coupled_cpu_gpu_qualification_pass",
                "suites": rows,
                "profiles": profiles,
                "profile_scale": record.get("profile_scale", "pilot"),
                "baseline": record.get("baseline"),
                "cpu_baseline": (
                    json.loads((output / "cpu-reuse.json").read_text()) if cpu_parent else None
                ),
                "elapsed_seconds": time.monotonic() - began,
                "experimental_validation": False,
                "scope": (
                    "Pinned BETSE IP3 release factor with finite owned ligand chemistry on the "
                    "CaV/plasma/ER/spatial/assembly model; synthetic IP3 buffering, independent "
                    "references and CPU/L4 replay; no native full trajectory or biological claim"
                    if ip3
                    else "Pinned Cav1.2 gate equations and finite calcium transport on the owned "
                    "plasma/ER/spatial/assembly model; independent references and complete "
                    "CPU/L4 replay; no native full trajectories, biological or multi-GPU claim"
                    if cav
                    else "Owned plasma/ER/spatial/assembly coupling with native positive-domain "
                    "PMCA function correspondence and synthetic reversible 3-Na/1-Ca exchange; "
                    "no native BETSE trajectories, biological calibration or multi-GPU claim"
                    if plasma
                    else "Owned buffered cytosol/ER stores coupled to spatial ionic transport and "
                    "assembly-controlled potassium channels; independent references and complete "
                    "CPU/L4 replay; no biological, native BETSE lifecycle or multi-GPU claim"
                    if calcium
                    else "Finite buffered cytosol/ER with capacitive transport, maintained "
                    "metabolic "
                    "work and pinned BETSE pump/release function correspondence; no native "
                    "lifecycle, biological, plasma-membrane/assembly or multi-GPU claim"
                    if er
                    else "Closed fixed-volume reaction networks and synthetic calcium buffering; "
                    "no ER transport, ionic feedback, biology, native BETSE parity "
                    "or multi-GPU claim"
                    if chemistry
                    else "Two-cell assembly-controlled spatial cluster; independent references, "
                    "restart and CPU/L4 correspondence; no biological or multi-GPU qualification"
                    if cluster
                    else "Integrated scheduler correctness and two local throughput pilots; "
                    "70% utilization is advisory; no four-GPU scaling or biology qualification"
                    if integrated
                    else "One-way cycle-dependent channel availability on the event/grid solver"
                ),
                **cluster_result,
                **chemistry_result,
            },
        )
        write_json(
            output / "completion.json",
            {
                "status": "completed",
                "utc": utc(),
                "result_sha256": digest(output / "result.json"),
                "files_sha256": {
                    name: digest(output / name)
                    for name in (
                        "registration.json",
                        "cpu.xml",
                        "gpu.xml",
                        "cpu.stdout.log",
                        "cpu.stderr.log",
                        "gpu.stdout.log",
                        "gpu.stderr.log",
                        "cpu.runtime.json",
                        "gpu.runtime.json",
                    )
                }
                | {
                    str(p.relative_to(output)): digest(p)
                    for p in sorted((output / "parity").glob("*.npz"))
                }
                | ({"cpu-reuse.json": digest(output / "cpu-reuse.json")} if cpu_parent else {})
                | (
                    {
                        str(p.relative_to(output)): digest(p)
                        for p in sorted((output / "ip3-evidence").rglob("*"))
                        if p.is_file()
                    }
                    if ip3
                    else {}
                )
                | (
                    {
                        str(p.relative_to(output)): digest(p)
                        for p in sorted((output / "cav-evidence").rglob("*"))
                        if p.is_file()
                    }
                    if cav
                    else {}
                )
                | (
                    {
                        str(p.relative_to(output)): digest(p)
                        for p in sorted((output / "plasma-evidence").rglob("*"))
                        if p.is_file()
                    }
                    if plasma
                    else {}
                )
                | (
                    {
                        str(p.relative_to(output)): digest(p)
                        for p in sorted((output / "calcium-evidence").rglob("*"))
                        if p.is_file()
                    }
                    if calcium
                    else {}
                )
                | (
                    {
                        str(p.relative_to(output)): digest(p)
                        for p in sorted((output / "er-evidence").rglob("*"))
                        if p.is_file()
                    }
                    if er
                    else {}
                )
                | (
                    {
                        str(p.relative_to(output)): digest(p)
                        for p in sorted((output / "chemistry-evidence").rglob("*"))
                        if p.is_file()
                    }
                    | {
                        "chemistry-protocol.json": digest(output / "chemistry-protocol.json"),
                        "chemistry-preflight.json": digest(output / "chemistry-preflight.json"),
                        "gpu-utilization.csv": digest(output / "gpu-utilization.csv"),
                    }
                    if chemistry
                    else {}
                )
                | (
                    {"qualification.json": digest(output / "qualification.json")}
                    if integrated
                    else {}
                )
                | (
                    {
                        str(p.relative_to(output)): digest(p)
                        for p in sorted((output / "cluster-evidence").rglob("*"))
                        if p.is_file()
                    }
                    | {
                        "gpu-utilization.csv": digest(output / "gpu-utilization.csv"),
                        "cluster-protocol.json": digest(output / "cluster-protocol.json"),
                    }
                    | (
                        {
                            str(p.relative_to(output)): digest(p)
                            for p in sorted((output / "partition-parent-replay").iterdir())
                            if p.is_file()
                        }
                        if partition_parent
                        else {}
                    )
                    if cluster
                    else {}
                ),
            },
        )
    except BaseException as exc:
        write_json(
            output / "failure.json",
            {
                "status": "failed",
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "utc": utc(),
                "elapsed_seconds": time.monotonic() - began,
            },
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("launch", "_worker", "_component_worker"))
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--component-protocol",
        type=Path,
        help="Bounded new-component CPU/L4 checks using the existing frozen-source runner",
    )
    parser.add_argument(
        "--dcgm-root", type=Path, default=Path("/mnt/workspaces/Cells/tools/dcgm-4.7.0")
    )
    parser.add_argument("--gpu-after", type=Path)
    parser.add_argument("--ensemble-profile", action="store_true")
    parser.add_argument("--cluster", action="store_true")
    parser.add_argument("--chemistry", action="store_true")
    parser.add_argument(
        "--chemistry-case",
        choices=("reactions", "er", "spatial", "plasma", "gated", "ip3"),
        default="reactions",
    )
    parser.add_argument("--cluster-partition-parent", type=Path)
    parser.add_argument("--profile-scale", choices=("pilot", "throughput"), default="pilot")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument(
        "--cpu-baseline",
        type=Path,
        help="Reuse a completed CPU phase from a registered plasma/gated/IP3-panel timeout",
    )
    parser.add_argument(
        "--gpu-retry-wall-seconds",
        type=int,
        help="Separate wall allowance for --cpu-baseline; cannot shorten the frozen protocol limit",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if args.command == "_component_worker":
        component_worker(output, json.loads((output / "registration.json").read_text()))
        return
    if args.command == "_worker":
        worker(output)
        return
    if args.component_protocol:
        if any(
            (
                args.gpu_after,
                args.ensemble_profile,
                args.cluster,
                args.chemistry,
                args.cluster_partition_parent,
                args.baseline,
                args.cpu_baseline,
                args.gpu_retry_wall_seconds,
                args.chemistry_case != "reactions",
                args.profile_scale != "pilot",
            )
        ):
            parser.error("Component protocol is a separate qualification mode")
        print(
            json.dumps(
                launch_component(
                    output, args.component_protocol.resolve(), args.dcgm_root.resolve()
                ),
                indent=2,
            )
        )
        return
    if args.chemistry_case != "reactions" and not args.chemistry:
        parser.error("--chemistry-case er/spatial/plasma/gated/ip3 requires --chemistry")
    if args.cpu_baseline and (not args.chemistry or args.chemistry_case not in CPU_REUSE_CASES):
        parser.error("--cpu-baseline requires --chemistry --chemistry-case plasma/gated/ip3")
    if args.gpu_retry_wall_seconds is not None and not args.cpu_baseline:
        parser.error("--gpu-retry-wall-seconds requires --cpu-baseline")
    if args.chemistry and (
        args.cluster or args.ensemble_profile or args.gpu_after or args.baseline
    ):
        parser.error("Chemistry qualification has its own bounded CPU/GPU panel")
    if args.cluster and (args.ensemble_profile or args.gpu_after or args.baseline):
        parser.error("Cluster qualification has its own bounded CPU/GPU panel")
    if args.cluster_partition_parent and not args.cluster:
        parser.error("Partition replay requires --cluster")
    partition_parent = None
    if args.cluster_partition_parent:
        from cluster_partition_replay import parent_binding

        partition_parent = parent_binding(args.cluster_partition_parent)
    if args.profile_scale == "throughput" and (not args.ensemble_profile or args.baseline is None):
        parser.error("Throughput profiles require --ensemble-profile and --baseline")
    if args.baseline is not None and args.profile_scale != "throughput":
        parser.error("--baseline is for the throughput profile")
    baseline, baseline_receipt = (
        baseline_profiles(args.baseline) if args.baseline is not None else (None, None)
    )
    cpu_parent = cpu_baseline_binding(args.cpu_baseline) if args.cpu_baseline else None
    if cpu_parent and cpu_parent["chemistry_case"] != args.chemistry_case:
        parser.error("--cpu-baseline must belong to the requested chemistry case")
    source_input = Path(cpu_parent["path"]) / "source" if cpu_parent else ROOT
    output = output_path(output)
    cluster_protocol, cluster_counts, chemistry_protocol, chemistry_counts = None, None, None, None
    chemistry_preflight = None
    chemistry_wall = None
    if args.cluster or args.chemistry:
        protocol_path = (
            (
                source_input
                / (
                    "validation/chemistry/ip3_protocol.json"
                    if args.chemistry_case == "ip3"
                    else "validation/chemistry/gated_protocol.json"
                    if args.chemistry_case == "gated"
                    else "validation/chemistry/plasma_protocol.json"
                    if args.chemistry_case == "plasma"
                    else "validation/chemistry/spatial_protocol.json"
                    if args.chemistry_case == "spatial"
                    else "validation/chemistry/er_protocol.json"
                    if args.chemistry_case == "er"
                    else "validation/chemistry/protocol.json"
                )
            )
            if args.chemistry
            else Path(__file__).with_name("cluster_protocol.json")
        )
        protocol = json.loads(protocol_path.read_text())
        if args.chemistry:
            chemistry_protocol = protocol
            chemistry_wall = chemistry_wall_seconds(
                protocol, cpu_parent, args.gpu_retry_wall_seconds
            )
        else:
            cluster_protocol = protocol
        limits = protocol["resources"]
        if shutil.disk_usage(output.parent).free < (
            limits["artifact_and_cache_bytes"] + limits["free_disk_reserve_bytes"]
        ):
            raise ValueError("Qualification allowance would consume the workspace reserve")
        available = next(
            int(row.split()[1]) * 1024
            for row in Path("/proc/meminfo").read_text().splitlines()
            if row.startswith("MemAvailable:")
        )
        if available < limits["max_worker_rss_bytes"] + 4 * 1024**3:
            raise ValueError("Qualification requires its host memory allowance plus 4 GiB reserve")
    if args.ensemble_profile and shutil.disk_usage(output.parent).free < 9 * 1024**3:
        raise ValueError("Integrated qualification/profile needs 5 GiB allowance and 4 GiB reserve")
    output.mkdir()
    (output / "cache").mkdir()
    source = output / "source"
    for name in ("src", "tests", "configs"):
        shutil.copytree(
            source_input / name,
            source / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    (source / "validation/assembly").mkdir(parents=True)
    shutil.copy2(__file__, source / "validation/assembly/qualify_cell.py")
    if args.chemistry:
        (source / "validation/chemistry").mkdir(parents=True)
        shutil.copy2(
            protocol_path,
            source / "validation/chemistry" / protocol_path.name,
        )
        if args.chemistry_case in ("er", "spatial", "plasma", "gated", "ip3"):
            native = (
                source_input / "validation/chemistry/native"
                if cpu_parent
                else Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science")
            )
            target = source / "validation/chemistry/native"
            target.mkdir()
            for name, expected in chemistry_protocol["native_sources_sha256"].items():
                original = native / (
                    "organelles/endo_retic.py"
                    if name == "endo_retic.py" and not cpu_parent
                    else "channels/" + name
                    if name in ("vg_ca.py", "channelsabc.py") and not cpu_parent
                    else name
                )
                if digest(original) != expected:
                    raise ValueError("Pinned ER reference source changed")
                shutil.copy2(original, target / name)
            license_file = native / "LICENSE.txt" if cpu_parent else native.parents[1] / "LICENSE"
            shutil.copy2(license_file, target / "LICENSE.txt")
        if args.chemistry_case in ("spatial", "plasma", "gated", "ip3"):
            reference_path = Path("validation/betse/spatial_cluster/reference.py")
            (source / reference_path.parent).mkdir(parents=True)
            shutil.copy2(source_input / reference_path, source / reference_path)
        write_json(output / "chemistry-protocol.json", chemistry_protocol)
        chemistry_preflight = chemistry_grid_preflight(
            source
            / "configs"
            / (
                "ip3_calcium_cluster.json"
                if args.chemistry_case == "ip3"
                else "gated_calcium_cluster.json"
                if args.chemistry_case == "gated"
                else "plasma_calcium_cluster.json"
                if args.chemistry_case == "plasma"
                else "spatial_calcium_cluster.json"
                if args.chemistry_case == "spatial"
                else "er_calcium_buffered.json"
                if args.chemistry_case == "er"
                else "calcium_buffer_compartments.json"
            ),
            chemistry_protocol,
        )
        write_json(output / "chemistry-preflight.json", chemistry_preflight)
        chemistry_counts = {}
        for backend in ("cpu", "gpu"):
            collected = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    "--collect-only",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    *chemistry_tests(args.chemistry_case),
                ],
                cwd=source,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
                env=dict(
                    os.environ,
                    PYTHONPATH=str(source / "src"),
                    PYTHONDONTWRITEBYTECODE="1",
                    JAX_PLATFORMS="cpu",
                ),
            )
            (output / f"{backend}.collection.log").write_text(collected.stdout + collected.stderr)
            chemistry_counts[backend] = sum(
                "::test_" in line for line in collected.stdout.splitlines()
            )
            if chemistry_counts[backend] < 100:
                raise ValueError("Chemistry/regression test collection is incomplete")
    if args.cluster:
        for name in (
            "validation/assembly/cluster_reference.py",
            "validation/assembly/cluster_partition_replay.py",
            "validation/assembly/cluster_protocol.json",
            "validation/betse/spatial_cluster/reference.py",
        ):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        write_json(output / "cluster-protocol.json", cluster_protocol)
        from cells.assembly_cluster.spec import load_spec

        load_spec(source / "configs/assembly_regulated_cluster.json")
        cluster_counts = {}
        for backend in ("cpu", "gpu"):
            command = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                *cluster_tests(backend),
            ]
            collected = subprocess.run(
                command,
                cwd=source,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
                env=dict(
                    os.environ,
                    PYTHONPATH=str(source / "src"),
                    PYTHONDONTWRITEBYTECODE="1",
                    JAX_PLATFORMS="cpu",
                ),
            )
            (output / f"{backend}.collection.log").write_text(collected.stdout + collected.stderr)
            cluster_counts[backend] = sum(
                "::test_" in line for line in collected.stdout.splitlines()
            )
            if cluster_counts[backend] < 40:
                raise ValueError("Cluster test collection is incomplete")
    profiles, profile_plans = {}, {}
    if args.ensemble_profile:
        (source / "validation/ensemble").mkdir()
        matrix_path = ROOT / "validation/ensemble/integrated_matrix.py"
        shutil.copy2(matrix_path, source / "validation/ensemble/integrated_matrix.py")
        module_spec = importlib.util.spec_from_file_location("integrated_matrix", matrix_path)
        matrix = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(matrix)
        from cells.ensemble.plan import plan

        definitions = (
            matrix.throughput_definitions(baseline)
            if args.profile_scale == "throughput"
            else matrix.definitions()
        )
        for name, definition in definitions.items():
            planned = plan(definition, 1)
            profile_plans[name] = {
                k: planned[k] for k in ("worlds", "worker_processes", "output_bytes_bound")
            } | {"tasks": len(planned["tasks"])}
            path = output / f"{name}.definition.json"
            write_json(path, definition)
            profiles[name] = digest(path)
        required_bytes = sum(p["output_bytes_bound"] for p in profile_plans.values()) + 5 * 1024**3
        if shutil.disk_usage(output).free < required_bytes:
            raise ValueError(
                "Profile plans plus qualification allowance would consume the disk reserve"
            )
    for name in ("pyproject.toml", "requirements-lock.txt"):
        shutil.copy2(source_input / name, source / name)
    cache_reuse = None
    if cpu_parent:
        parent = Path(cpu_parent["path"])
        for name in cpu_parent["cpu_files_sha256"]:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(parent / name, target)
        verify_cpu_baseline(output, cpu_parent)
        # Copy, never hardlink, so JAX can update this run's caches independently.
        cache_reuse = {}
        for name in ("jax", "cuda"):
            origin = parent / "cache" / name
            if origin.exists():
                shutil.copytree(origin, output / "cache" / name)
                cached = [p for p in origin.rglob("*") if p.is_file()]
                cache_reuse[name] = {
                    "files": len(cached),
                    "bytes": sum(p.stat().st_size for p in cached),
                }
        cluster_budget(output, chemistry_protocol)
    write_json(
        output / "registration.json",
        {
            "sources_sha256": files(source),
            "utc": utc(),
            "workspace": "/mnt/workspaces/Cells",
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "max_wall_seconds": chemistry_wall
            if args.chemistry
            else cluster_protocol["resources"]["max_wall_seconds"]
            if args.cluster
            else 3600
            if args.ensemble_profile
            else 1800,
            "cluster": args.cluster,
            "chemistry": args.chemistry,
            "chemistry_case": args.chemistry_case,
            "chemistry_protocol": chemistry_protocol,
            "chemistry_preflight": chemistry_preflight,
            "chemistry_test_counts": chemistry_counts,
            "cluster_protocol": cluster_protocol,
            "cluster_test_counts": cluster_counts,
            "partition_parent": partition_parent,
            "partition_replay_max_seconds": 600 if partition_parent else None,
            "ensemble_profile": args.ensemble_profile,
            "profile_scale": args.profile_scale,
            "profile_plans": profile_plans,
            "baseline": baseline_receipt,
            "cpu_baseline": cpu_parent,
            "gpu_retry_wall_seconds": args.gpu_retry_wall_seconds,
            "copied_compilation_caches": cache_reuse,
            "profile_definitions_sha256": profiles,
            "gpu_after": None
            if args.gpu_after is None
            else {
                "path": str(args.gpu_after.resolve()),
                "registration_sha256": digest(args.gpu_after / "registration.json"),
            },
            "checks": (
                chemistry_protocol["checks"]
                if args.chemistry
                else cluster_protocol["checks"]
                if args.cluster
                else "Integrated CPU/GPU scalar/partition/checkpoint comparisons, two workers, "
                "signal pause/resume, old assembly scheduling, then two fixed local profiles"
                if args.ensemble_profile
                else "Scalar event/ODE reference; organization and disabled coupling; "
                "complete restart/window/world partition; CPU/GPU; CLI; refinement; "
                "corrupt-state refusal"
            ),
        },
    )
    environment = dict(os.environ, PYTHONPATH=str(source / "src"), PYTHONDONTWRITEBYTECODE="1")
    with (output / "stdout.log").open("x") as out, (output / "stderr.log").open("x") as err:
        child = subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(source / "validation/assembly/qualify_cell.py"),
                "_worker",
                str(output),
            ],
            stdout=out,
            stderr=err,
            stdin=subprocess.DEVNULL,
            env=environment,
            start_new_session=True,
            close_fds=True,
        )
    launch = {"status": "launched", "pid": child.pid, "utc": utc(), "output": str(output)}
    write_json(output / "launch.json", launch)
    print(json.dumps(launch, indent=2))


if __name__ == "__main__":
    main()
