"""Bounded joint water/repair epoch contracts with frozen tests and references."""

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from check_morris_lecar_channels import snapshot
from check_water_schema import digest, write_json

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = (
    "src/cells/core/joint_water_profile_phase_handoff.py",
    "src/cells/core/surface_calcium_energy_water_profile_epoch_spec.py",
    "src/cells/core/surface_calcium_energy_water_repair_profile_epoch_spec.py",
    "src/cells/models/surface_calcium_energy_water_profile_epoch.py",
    "src/cells/models/surface_calcium_energy_water_repair_profile_epoch.py",
)
TESTS = ("tests/unit/test_joint_water_profile_phase_handoff.py",)
PROTOCOL = "validation/topology/joint_water_profile_phase_handoff_protocol.json"
OWNED = (
    *RUNTIME,
    "agent-work/cells-worker-01/workfiles/complete_joint_water_phase_contracts.py",
    *TESTS,
    PROTOCOL,
    "validation/topology/joint_water_profile_phase_handoff_reference.py",
    "validation/topology/joint_water_profile_phase_handoff_fixtures.py",
    "agent-work/cells-worker-01/workfiles/check_joint_water_profile_phase_handoff.py",
    "agent-work/cells-worker-01/workfiles/prepare_joint_water_phase_qualification.py",
    "agent-work/cells-worker-01/workfiles/joint_water_profile_phase_handoff_test_dispatch.patch",
    "agent-work/cells-worker-01/workfiles/joint_water_profile_phase_handoff_test_dispatch.json",
)


SEED = Path("/mnt/workspaces/Cells/joint-water-phase-development-20261029-04")


def prepare_workspace(output, protocol):
    report = json.loads((SEED / "result.json").read_text())
    assert report["status"] == "passed"
    for name, expected in report["output_sha256"].items():
        assert digest(SEED / name) == expected, name
    workspace = output / "workspace"
    shutil.copytree(
        SEED / "workspace", workspace, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    for name, expected in report["executed_runtime_source_sha256"].items():
        assert digest(workspace / name) == expected, name
    for name, expected in report["executed_validation_source_sha256"].items():
        assert digest(workspace / name) == expected, name
    manifest = json.loads((SEED / "workspace-manifest.json").read_text())
    manifest["immutable_contract_seed"] = dict(
        receipt=str(SEED / "result.json"),
        receipt_sha256=digest(SEED / "result.json"),
        tests_and_references_frozen=True,
    )
    write_json(output / "workspace-manifest.json", manifest)
    return workspace, report["executed_runtime_source_sha256"]


def retain_completed(output):
    rows = []
    (output / "evidence").mkdir()
    seed = json.loads((SEED / "result.json").read_text())
    for number, expected_tests in (("03", 2), ("04", 4)):
        previous = Path("/mnt/workspaces/Cells/joint-water-phase-development-20261029-" + number)
        report = json.loads((previous / "result.json").read_text())
        assert report["status"] == "passed" and report["error"] is None
        assert report["tests"] == dict(tests=expected_tests, failures=0, errors=0, skipped=0)
        assert not report["sources_changed_during_checks"]
        assert not report["workspace_sources_changed_during_checks"]
        assert not report["frozen_validation_sources_changed_during_checks"]
        assert report["executed_runtime_source_sha256"] == seed["executed_runtime_source_sha256"]
        assert (
            report["executed_validation_source_sha256"] == seed["executed_validation_source_sha256"]
        )
        for name, expected in report["output_sha256"].items():
            assert digest(previous / name) == expected, name
        xml = previous / "host-tests.xml"
        shutil.copyfile(xml, output / ("retained-" + number + "-tests.xml"))
        for path in (previous / "evidence").iterdir():
            target = output / "evidence" / path.name
            assert not target.exists()
            shutil.copyfile(path, target)
        guards = {}
        for row in report["checks"]:
            value = json.loads((previous / (row["name"] + "-guard/result.json")).read_text())
            assert value["status"] == "completed" and row["exit_code"] == 0
            assert value["sampled_peak_process_tree_rss_bytes"] <= 2**30
            assert value["minimum_available_host_memory_bytes"] >= 8 * 2**30
            guards[row["name"]] = value
        rows.append(
            dict(
                receipt=str(previous / "result.json"),
                receipt_sha256=digest(previous / "result.json"),
                finalized_tests=expected_tests,
                rerun=False,
                junit_sha256=digest(xml),
                resources=guards,
                immutable_executing_sources_match_seed=True,
            )
        )
    write_json(output / "retained-passes.json", rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select")
    parser.add_argument("--host-only", action="store_true")
    args = parser.parse_args()
    if args.host_only or args.select:
        parser.error(
            "Fixed disjoint contract groups retain six completed checks; long refinements held"
        )
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "joint-water-phase-development-"
    ):
        parser.error("Use a fresh /mnt/workspaces/Cells/joint-water-phase-development-* directory")
    output.mkdir(exist_ok=False)
    retained = retain_completed(output)
    for name in ("tmp", "cache"):
        (output / name).mkdir()
    protocol = json.loads((ROOT / PROTOCOL).read_text())
    environment = dict.fromkeys(
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
    )
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        JAX_DISABLE_JIT="true",
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_COMPILATION_CACHE="false",
        XDG_CACHE_HOME=str(output / "cache"),
        JAX_COMPILATION_CACHE_DIR=str(output / "cache/jax"),
        MPLCONFIGDIR=str(output / "cache/matplotlib"),
        TMPDIR=str(output / "tmp"),
        MALLOC_ARENA_MAX="2",
        CELLS_COMPONENT_BACKEND="cpu",
        CELLS_COMPONENT_EVIDENCE=str(output / "evidence"),
        CELLS_COMPONENT_SOURCE_ROOT=str(ROOT),
        CELLS_COMPONENT_PHASE="host",
    )
    env = os.environ.copy()
    env.update(environment)
    python_files = [p for p in OWNED if p.endswith(".py")]
    ruff = str(Path(sys.executable).parent / "ruff")
    steps = [("lint", [ruff, "check", "--no-cache", *python_files])]
    ordinary = "not complete_INIT and not carried_SIM"
    phases = (
        [("host", ordinary)]
        if args.host_only
        else [
            ("host-preservation", "owner_arrays and not changed-controls"),
            ("host-stages", "complete_SIM_stage and not changed-controls"),
            ("host-portable", "interior_checkpoint"),
            ("host-source-refusals", "full_source_checkpoint"),
            ("host-target-refusals", "full_request"),
            ("host-exact-owner", "exact_scheduled_source_owner"),
            ("host-bounded-evolution", "bounded_epoch_steps"),
            ("host-reference", "independent_dependency_manifest"),
        ]
    )
    for name, selection in phases:
        if name.startswith("host"):
            selection = f"({ordinary}) and ({selection})"
        if args.select:
            selection = f"({selection}) and ({args.select})"
        steps.append(
            (
                name,
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    "-q",
                    "-x",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp=" + str(output / ("tmp/pytest-" + name)),
                    "--junitxml=" + str(output / (name + "-tests.xml")),
                    *(str(output / "workspace" / t) for t in TESTS),
                    "-k",
                    selection,
                ],
            )
        )
    files = sorted(
        set(OWNED)
        | set(protocol["readonly_source_sha256"])
        | {str(p.relative_to(ROOT)) for p in (ROOT / "configs").rglob("*") if p.is_file()}
        | {
            "agent-work/cells-worker-01/workfiles/check_morris_lecar_channels.py",
            "agent-work/cells-worker-01/workfiles/check_water_schema.py",
            "validation/assembly/component_process.py",
            "validation/ensemble/profile_cluster.py",
            "src/cells/assembly/cli.py",
            "src/cells/assembly/io.py",
            "pyproject.toml",
        }
    )
    metadata = json.loads((ROOT / protocol["test_dispatch_metadata"]).read_text())
    shared_routes = sorted(
        set(metadata["files"]) | {"src/cells/core/tissue_profile_composition_preparation.py"}
    )
    live_shared_hashes = snapshot(output, "live_shared_sources", shared_routes)
    inputs = dict(
        started_utc=datetime.now(UTC).isoformat(),
        phase="host-only" if args.host_only else "complete-component",
        affinity=sorted(os.sched_getaffinity(0)),
        environment=environment,
        python=sys.version,
        versions={
            n: importlib.metadata.version(n) for n in ("numpy", "jax", "jaxlib", "scipy", "pytest")
        },
        commands=[dict(name=n, argv=a) for n, a in steps],
        initial_source_sha256=snapshot(output, "initial_sources", files),
        live_shared_source_sha256=live_shared_hashes,
        executing_import_paths=dict(
            cells=str(output / "workspace/src/cells"),
            tests=str(output / "workspace/tests"),
            validation=str(output / "workspace/validation"),
        ),
        long_trajectory_launch_admitted=False,
        retained_finalized_runs=retained,
        frozen_workspace=protocol["frozen_workspace"],
        max_command_seconds=480,
        max_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 2**30,
        scope=protocol["scope"],
    )
    write_json(output / "inputs.json", inputs)
    results = []
    source_hashes = {}
    workspace_hashes = {}
    frozen_validation_hashes = {}
    error = None
    try:
        if inputs["affinity"] != [7]:
            raise ValueError("Require CPU7 affinity")
        source_hashes = snapshot(output, "sources", files)
        workspace, workspace_hashes = prepare_workspace(output, protocol)
        seed_report = json.loads((SEED / "result.json").read_text())
        frozen_validation_hashes = seed_report["executed_validation_source_sha256"]
        for name, expected in frozen_validation_hashes.items():
            assert digest(workspace / name) == expected, name
        write_json(output / "frozen-validation-manifest.json", frozen_validation_hashes)
        env["PYTHONPATH"] = str(workspace / "src") + os.pathsep + str(workspace)
        env["CELLS_COMPONENT_SOURCE_ROOT"] = str(workspace)
        sys.path[:0] = [str(workspace / "src"), str(workspace)]
        from validation.assembly.component_process import run_bounded

        for name, argv in steps:
            if name == "lint":
                source_hashes = snapshot(output, "sources", files)
            local = env.copy()
            if name.startswith("jax"):
                local.update(JAX_DISABLE_JIT="true", CELLS_COMPONENT_PHASE="jax")
            if name.startswith("public"):
                local.update(JAX_DISABLE_JIT="true", CELLS_COMPONENT_PHASE="public")
            directory = output / (name + "-guard")
            directory.mkdir()
            began = time.monotonic()
            code = 0
            try:
                run_bounded(
                    argv,
                    directory=directory,
                    cwd=ROOT if name == "lint" else workspace,
                    env=local,
                    timeout=480,
                    max_rss_bytes=2**30,
                    min_available_bytes=8 * 2**30,
                )
            except subprocess.CalledProcessError as exception:
                code = exception.returncode
            finally:
                (output / (name + ".log")).write_text(
                    "".join(
                        (directory / p).read_text()
                        for p in ("stdout.log", "stderr.log")
                        if (directory / p).is_file()
                    )
                )
            results.append(
                dict(
                    name=name,
                    exit_code=code,
                    wall_seconds=time.monotonic() - began,
                    JAX_DISABLE_JIT=local["JAX_DISABLE_JIT"],
                )
            )
            if code:
                break
    except Exception as exception:
        error = dict(
            type=type(exception).__name__, message=str(exception), traceback=traceback.format_exc()
        )
    live_source_changed = [
        name
        for name, sha in source_hashes.items()
        if name.startswith(("src/", "tests/", "validation/", "configs/"))
        and digest(ROOT / name) != sha
    ]
    driver_hashes = {
        name: sha
        for name, sha in source_hashes.items()
        if not name.startswith(("src/", "tests/", "validation/", "configs/"))
    }
    changed = [name for name, sha in driver_hashes.items() if digest(ROOT / name) != sha]
    live_shared_changed = [
        name for name, sha in live_shared_hashes.items() if digest(ROOT / name) != sha
    ]
    workspace_changed = [
        name for name, sha in workspace_hashes.items() if digest(output / "workspace" / name) != sha
    ]
    frozen_validation_changed = [
        name
        for name, sha in frozen_validation_hashes.items()
        if digest(output / "workspace" / name) != sha
    ]
    counts = {}
    for xml in output.glob("*-tests.xml"):
        suites = list(ET.parse(xml).getroot().iter("testsuite"))
        for key in ("tests", "errors", "failures", "skipped"):
            counts[key] = counts.get(key, 0) + sum(int(s.get(key, "0")) for s in suites)
    check_ids = [
        c.attrib["classname"] + "::" + c.attrib["name"]
        for path in output.glob("*-tests.xml")
        for c in ET.parse(path).getroot().iter("testcase")
    ]
    complete_coverage = (
        len(check_ids) == len(set(check_ids)) == protocol["expected_contract_checks"]
    )
    passed = (
        error is None
        and len(results) == len(steps)
        and not any(r["exit_code"] for r in results)
        and not changed
        and not workspace_changed
        and not frozen_validation_changed
        and not counts.get("skipped")
        and complete_coverage
    )
    report = dict(
        status="passed" if passed else "failed",
        checks=results,
        tests=counts,
        unique_check_ids=check_ids,
        complete_expected_contract_coverage=complete_coverage,
        retained_finalized_runs=retained,
        source_sha256=driver_hashes,
        captured_live_source_sha256=source_hashes,
        executed_runtime_source_sha256=workspace_hashes,
        executed_validation_source_sha256=frozen_validation_hashes,
        frozen_validation_sources_changed_during_checks=frozen_validation_changed,
        live_source_changes_during_checks=live_source_changed,
        live_shared_source_sha256=live_shared_hashes,
        live_shared_sources_changed_during_checks=live_shared_changed,
        live_shared_drift_affects_execution_integrity=False,
        long_trajectory_launch_admitted=False,
        sources_changed_during_checks=changed,
        workspace_sources_changed_during_checks=workspace_changed,
        error=error,
        workspace_manifest_sha256=digest(output / "workspace-manifest.json")
        if (output / "workspace-manifest.json").is_file()
        else None,
        output_sha256={
            str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
    )
    write_json(output / "result.json", report)
    if not passed:
        write_json(output / "failure.json", report)
    print(json.dumps(dict(output=str(output), status=report["status"], tests=counts)))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
