"""Bounded scheduled-profile qualification in an isolated dispatch-enabled copy."""

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
OWNED = (
    "src/cells/core/surface_profile_interventions_spec.py",
    "src/cells/models/surface_profile_interventions.py",
    "tests/unit/test_surface_profile_interventions.py",
    "validation/topology/surface_profile_interventions_fixtures.py",
    "validation/topology/surface_profile_interventions_reference.py",
    "validation/topology/surface_profile_interventions_protocol.json",
    "agent-work/cells-worker-01/workfiles/check_surface_profile_interventions.py",
    "agent-work/cells-worker-01/workfiles/surface_profile_interventions_dispatch.patch",
    "agent-work/cells-worker-01/workfiles/surface_profile_interventions_dispatch.json",
)


def prepare_workspace(output, metadata):
    workspace = output / "workspace"
    shutil.copytree(
        ROOT / "src", workspace / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    before = {
        str(p.relative_to(workspace)): digest(p)
        for p in sorted((workspace / "src").rglob("*"))
        if p.is_file()
    }
    for name, row in metadata["files"].items():
        if before[name] != row["base_sha256"]:
            raise ValueError("Refresh isolated patch base: " + name)
    patch = ROOT / OWNED[7]
    if digest(patch) != metadata["patch_sha256"]:
        raise ValueError("Stale isolated dispatch patch")
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
    for name, row in metadata["files"].items():
        if after[name] != row["patched_sha256"]:
            raise ValueError("Unexpected test dispatch: " + name)
    manifest = dict(
        status="frozen",
        base_sha256=before,
        patched_sha256=after,
        only_metadata_dispatch_changed=changed,
        shared_files_written=False,
    )
    write_json(output / "workspace-manifest.json", manifest)
    return workspace, after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select")
    parser.add_argument("--host-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "scheduled-membrane-profiles-development-"
    ):
        parser.error(
            "Use a fresh /mnt/workspaces/Cells/scheduled-membrane-profiles-development-* directory"
        )
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache"):
        (output / name).mkdir()
    protocol = json.loads((ROOT / OWNED[5]).read_text())
    metadata = json.loads((ROOT / OWNED[8]).read_text())
    environment = dict.fromkeys(
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
    )
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=str(ROOT / "src") + os.pathsep + str(ROOT),
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
        CELLS_SCHEDULED_JOINED_SOURCE=str(output / "qualified-source"),
    )
    env = os.environ.copy()
    env.update(environment)
    source = protocol["joined_source"]
    (output / "qualified-source").mkdir()
    for name in ("definition.json", "provenance.json"):
        original = Path(source["path"]) / name
        if digest(original) != source["files_sha256"][name]:
            raise ValueError("Qualified joined source changed: " + name)
        shutil.copyfile(original, output / "qualified-source" / name)
    python_files = [p for p in OWNED if p.endswith(".py")]
    ruff = str(Path(sys.executable).parent / "ruff")
    steps = [
        ("imports", [ruff, "check", "--no-cache", "--select", "I", "--fix", *python_files]),
        ("format", [ruff, "format", "--no-cache", *python_files]),
        ("lint", [ruff, "check", "--no-cache", *python_files]),
    ]
    for name, selection in (
        ("host", "not cpu_jax and not public_short"),
        *(() if args.host_only else (("jax-rhs", "cpu_jax"), ("public", "public_short"))),
    ):
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
                    str(ROOT / OWNED[2]),
                    "-k",
                    selection,
                ],
            )
        )
    files = sorted(
        set(OWNED)
        | set(protocol["readonly_source_sha256"])
        | {
            "configs/resolved_tissue_excision_source.json",
            "configs/resolved_tissue.json",
            "validation/assembly/component_process.py",
            "validation/ensemble/profile_cluster.py",
            "src/cells/assembly/cli.py",
            "src/cells/assembly/io.py",
            "src/cells/__init__.py",
            "pyproject.toml",
            "agent-work/cells-worker-01/workfiles/check_morris_lecar_channels.py",
            "agent-work/cells-worker-01/workfiles/check_water_schema.py",
        }
    )
    inputs = dict(
        started_utc=datetime.now(UTC).isoformat(),
        phase="host-only" if args.host_only else "complete-component",
        affinity=sorted(os.sched_getaffinity(0)),
        environment=environment,
        python=sys.version,
        versions={
            name: importlib.metadata.version(name)
            for name in ("numpy", "jax", "jaxlib", "pytest", "scipy")
        },
        commands=[dict(name=n, argv=a) for n, a in steps],
        initial_source_sha256=snapshot(output, "initial_sources", files),
        test_dispatch=metadata,
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
        sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
        from validation.assembly.component_process import run_bounded

        for name, argv in steps:
            if name == "lint":
                source_hashes = snapshot(output, "sources", files)
            if name == "host":
                workspace, workspace_hashes = prepare_workspace(output, metadata)
                env["PYTHONPATH"] = str(workspace / "src") + os.pathsep + str(ROOT)
            local = env.copy()
            if name == "jax-rhs":
                local.update(JAX_DISABLE_JIT="false", CELLS_COMPONENT_PHASE="jax")
            if name == "public":
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
    result = dict(
        status="passed" if passed else "failed",
        checks=results,
        tests=counts,
        source_sha256=source_hashes,
        sources_changed_during_checks=changed,
        workspace_sources_changed_during_checks=workspace_changed,
        workspace_manifest_sha256=digest(output / "workspace-manifest.json")
        if (output / "workspace-manifest.json").is_file()
        else None,
        error=error,
        output_sha256={
            str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
    )
    write_json(output / "result.json", result)
    if not passed:
        write_json(output / "failure.json", result)
    print(json.dumps(dict(output=str(output), status=result["status"], tests=counts)))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
