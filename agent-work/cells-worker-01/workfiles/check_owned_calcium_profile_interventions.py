"""Bounded explicit calcium/fuel profile qualification against an immutable qualified engine."""

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
    "src/cells/core/owned_calcium_profile_binding.py",
    "src/cells/core/surface_calcium_profile_interventions_spec.py",
    "src/cells/core/surface_calcium_energy_profile_interventions_spec.py",
    "src/cells/models/surface_calcium_profile_interventions.py",
    "src/cells/models/surface_calcium_energy_profile_interventions.py",
)
TEST = "tests/unit/test_owned_calcium_profile_interventions.py"
PROTOCOL = "validation/topology/owned_calcium_profile_interventions_protocol.json"
OWNED = (
    *RUNTIME,
    TEST,
    PROTOCOL,
    "agent-work/cells-worker-01/workfiles/prepare_owned_calcium_profile_qualification.py",
    "validation/topology/owned_calcium_profile_interventions_reference.py",
    "validation/topology/owned_calcium_profile_interventions_fixtures.py",
    "agent-work/cells-worker-01/workfiles/check_owned_calcium_profile_interventions.py",
    "agent-work/cells-worker-01/workfiles/owned_calcium_profile_interventions_test_dispatch.patch",
    "agent-work/cells-worker-01/workfiles/owned_calcium_profile_interventions_test_dispatch.json",
    "agent-work/cells-worker-01/workfiles/owned_calcium_profile_interventions_dispatch.patch",
    "agent-work/cells-worker-01/workfiles/owned_calcium_profile_interventions_dispatch.json",
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select")
    parser.add_argument("--host-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "owned-calcium-profiles-development-"
    ):
        parser.error(
            "Use a fresh /mnt/workspaces/Cells/owned-calcium-profiles-development-* directory"
        )
    output.mkdir(exist_ok=False)
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
    steps = [
        ("imports", [ruff, "check", "--no-cache", "--select", "I", "--fix", *python_files]),
        ("format", [ruff, "format", "--no-cache", *python_files]),
        ("lint", [ruff, "check", "--no-cache", *python_files]),
    ]
    ordinary = "not cpu_jax and not public_short"
    phases = (
        [("host", ordinary)]
        if args.host_only
        else [
            (
                "host-calcium-contracts",
                f"({ordinary}) and calcium6 and not short_complete and not closure_physics",
            ),
            (
                "host-fuel-contracts",
                f"({ordinary}) and fuel5 and not short_complete and not closure_physics",
            ),
            ("host-calcium-SIM", "short_complete and calcium6 and SIM"),
            (
                "host-calcium-closure",
                "(short_complete or closure_physics) and calcium6 and not SIM",
            ),
            ("host-fuel-SIM", "(short_complete and fuel5 and SIM) or finite_fuel_all_three"),
            ("host-fuel-closure", "(short_complete or closure_physics) and fuel5 and not SIM"),
            ("host-contract", f"({ordinary}) and critical_dependencies"),
            ("jax-calcium", "cpu_jax and calcium6"),
            ("jax-fuel", "cpu_jax and fuel5"),
            ("public-calcium", "public_short and calcium6"),
            ("public-fuel", "public_short and fuel5"),
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
                    str(ROOT / TEST),
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
