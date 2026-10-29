"""Complete only the remaining repair trajectory, retaining 45 finalized checks."""

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
    "src/cells/core/surface_calcium_energy_water_hcn_extra_spec.py",
    "src/cells/core/surface_calcium_energy_water_repair_hcn_extra_spec.py",
    "src/cells/models/surface_calcium_energy_water_hcn_extra.py",
    "src/cells/models/surface_calcium_energy_water_repair_hcn_extra.py",
)
TESTS = (
    "tests/unit/test_surface_calcium_energy_water_hcn_extra.py",
    "tests/unit/test_surface_calcium_energy_water_repair_hcn_extra.py",
)
PROTOCOL = "validation/tissue/joint_water_hcn_protocol.json"
OWNED = (
    *RUNTIME,
    "agent-work/cells-worker-01/workfiles/complete_joint_water_hcn.py",
    *TESTS,
    PROTOCOL,
    "tests/owned_joint_water_hcn_helpers.py",
    "validation/tissue/calcium_energy_water_hcn_extra_reference.py",
    "validation/tissue/calcium_energy_water_repair_hcn_extra_reference.py",
    "validation/tissue/calcium_energy_water_hcn_extra_fixtures.py",
    "validation/tissue/calcium_energy_water_repair_hcn_extra_fixtures.py",
    "agent-work/cells-worker-01/workfiles/check_joint_water_hcn.py",
    "agent-work/cells-worker-01/workfiles/prepare_joint_water_hcn_qualification.py",
    "agent-work/cells-worker-01/workfiles/joint_water_hcn_test_dispatch.patch",
    "agent-work/cells-worker-01/workfiles/joint_water_hcn_test_dispatch.json",
)


def prepare_workspace(output, protocol):
    frozen = protocol["frozen_workspace"]
    manifest_path = Path(frozen["manifest"])
    if digest(manifest_path) != frozen["manifest_sha256"]:
        raise ValueError("Qualified engine workspace manifest changed")
    original = json.loads(manifest_path.read_text())[frozen["source_hash_key"]]
    source = Path(frozen["path"])
    for relative, expected in original.items():
        if digest(source / relative) != expected:
            raise ValueError("Qualified frozen engine source changed: " + relative)
    workspace = output / "workspace"
    shutil.copytree(
        source / "src", workspace / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    for relative in RUNTIME:
        shutil.copyfile(ROOT / relative, workspace / relative)
    before = {
        str(p.relative_to(workspace)): digest(p)
        for p in sorted((workspace / "src").rglob("*"))
        if p.is_file()
    }
    metadata = json.loads((ROOT / protocol["test_dispatch_metadata"]).read_text())
    patch = ROOT / protocol["test_dispatch_patch"]
    if digest(patch) != metadata["patch_sha256"]:
        raise ValueError("Stale isolated epoch dispatch patch")
    for relative, row in metadata["files"].items():
        if before[relative] != row["base_sha256"]:
            raise ValueError("Wrong isolated epoch dispatch base: " + relative)
    subprocess.run(
        ["git", "apply", str(patch)], cwd=workspace, check=True, capture_output=True, text=True
    )
    after = {
        str(p.relative_to(workspace)): digest(p)
        for p in sorted((workspace / "src").rglob("*"))
        if p.is_file()
    }
    changed = [name for name in before if before[name] != after[name]]
    if set(changed) != set(metadata["files"]):
        raise ValueError("Unexpected copied-source change")
    for relative, row in metadata["files"].items():
        if after[relative] != row["patched_sha256"]:
            raise ValueError("Unexpected test dispatch")
    record = dict(
        status="frozen",
        qualified_base_source_sha256=original,
        overlay_source_sha256={p: digest(ROOT / p) for p in RUNTIME},
        before_dispatch_sha256=before,
        source_sha256=after,
        only_test_dispatch_changed=changed,
        shared_files_written=False,
        current_shared_engine_used=False,
    )
    write_json(output / "workspace-manifest.json", record)
    return workspace, after


def retain_completed(output):
    runs = []
    (output / "evidence").mkdir()
    for number, expected_tests in (("02", 44), ("03", 1)):
        previous = Path("/mnt/workspaces/Cells/joint-water-hcn-development-20261029-" + number)
        report = json.loads((previous / "result.json").read_text())
        assert report["status"] == "passed" and report["error"] is None
        assert report["tests"] == dict(tests=expected_tests, errors=0, failures=0, skipped=0)
        assert (
            not report["sources_changed_during_checks"]
            and not report["workspace_sources_changed_during_checks"]
        )
        for name, expected in report["output_sha256"].items():
            assert digest(previous / name) == expected, name
        for name, expected in report["source_sha256"].items():
            assert digest(ROOT / name) == expected, name
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
        runs.append(
            dict(
                receipt=str(previous / "result.json"),
                receipt_sha256=digest(previous / "result.json"),
                finalized_tests=expected_tests,
                rerun=False,
                junit_sha256=digest(xml),
                resources=guards,
            )
        )
    write_json(output / "retained-passes.json", runs)
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select")
    parser.add_argument("--host-only", action="store_true")
    args = parser.parse_args()
    if args.select or args.host_only:
        parser.error("Completion retains 45 checks and runs only the repair trajectory")
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "joint-water-hcn-development-"
    ):
        parser.error("Use a fresh /mnt/workspaces/Cells/joint-water-hcn-development-* directory")
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
    ordinary = "not cpu_jax"
    phases = [("host-repair-trajectory", "complete_repair_trajectory")]
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
                    *(str(ROOT / t) for t in TESTS),
                    "-k",
                    selection,
                ],
            )
        )
    files = sorted(
        set(OWNED)
        | set(protocol["readonly_source_sha256"])
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
    inputs = dict(
        started_utc=datetime.now(UTC).isoformat(),
        retained_finalized_runs=retained,
        phase="host-only" if args.host_only else "complete-component",
        affinity=sorted(os.sched_getaffinity(0)),
        environment=environment,
        python=sys.version,
        versions={
            n: importlib.metadata.version(n) for n in ("numpy", "jax", "jaxlib", "scipy", "pytest")
        },
        commands=[dict(name=n, argv=a) for n, a in steps],
        initial_source_sha256=snapshot(output, "initial_sources", files),
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
    error = None
    try:
        if inputs["affinity"] != [7]:
            raise ValueError("Require CPU7 affinity")
        sys.path[:0] = [str(Path(protocol["frozen_workspace"]["path"]) / "src"), str(ROOT)]
        from validation.assembly.component_process import run_bounded

        for name, argv in steps:
            if name == "lint":
                source_hashes = snapshot(output, "sources", files)
            if name.startswith("host") and not workspace_hashes:
                workspace, workspace_hashes = prepare_workspace(output, protocol)
                env["PYTHONPATH"] = str(workspace / "src") + os.pathsep + str(ROOT)
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
                    cwd=ROOT,
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
    changed = [name for name, sha in source_hashes.items() if digest(ROOT / name) != sha]
    workspace_changed = [
        name for name, sha in workspace_hashes.items() if digest(output / "workspace" / name) != sha
    ]
    counts = {}
    for xml in output.glob("*-tests.xml"):
        suites = list(ET.parse(xml).getroot().iter("testsuite"))
        for key in ("tests", "errors", "failures", "skipped"):
            counts[key] = counts.get(key, 0) + sum(int(s.get(key, "0")) for s in suites)
    passed = (
        error is None
        and len(results) == len(steps)
        and not any(r["exit_code"] for r in results)
        and not changed
        and not workspace_changed
        and not counts.get("skipped")
    )
    report = dict(
        status="passed" if passed else "failed",
        checks=results,
        tests=counts,
        retained_finalized_runs=retained,
        source_sha256=source_hashes,
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
