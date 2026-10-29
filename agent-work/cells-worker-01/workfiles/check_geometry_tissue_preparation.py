"""Bounded initial geometry-to-passive-tissue preparation and physical checks."""

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
    "src/cells/core/geometry_tissue_preparation.py",
    "tests/unit/test_geometry_tissue_preparation.py",
    "validation/geometry/geometry_tissue_preparation_reference.py",
    "validation/geometry/geometry_tissue_preparation_fixtures.py",
    "validation/geometry/geometry_tissue_preparation_protocol.json",
    "agent-work/cells-worker-01/workfiles/check_geometry_tissue_preparation.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select", help="Optional targeted pytest expression")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "geometry-tissue-preparation-development-"
    ):
        parser.error(
            "Use a fresh /mnt/workspaces/Cells/geometry-tissue-preparation-development-* directory"
        )
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache"):
        (output / name).mkdir()
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
        CELLS_GEOMETRY_PREPARATION_NATIVE=str(output / "native-inputs"),
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
    for name, selection in (("host", "not jax"),):
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
                    OWNED[1],
                    "-k",
                    selection,
                ],
            )
        )
    protocol = json.loads((ROOT / OWNED[4]).read_text())
    (output / "native-inputs").mkdir()
    for name, expected in protocol["native_input_sha256"].items():
        original = Path(protocol["native_input_directory"]) / name
        if digest(original) != expected:
            raise ValueError("Qualified native capture changed: " + name)
        shutil.copyfile(original, output / "native-inputs" / name)
    files = sorted(
        set(OWNED)
        | set(protocol["readonly_source_sha256"])
        | {
            "validation/assembly/component_process.py",
            "validation/ensemble/profile_cluster.py",
            "src/cells/assembly/cli.py",
            "src/cells/assembly/io.py",
            "agent-work/cells-worker-01/workfiles/check_morris_lecar_channels.py",
            "agent-work/cells-worker-01/workfiles/check_water_schema.py",
            "pyproject.toml",
        }
    )
    inputs = dict(
        phase="complete-component",
        started_utc=datetime.now(UTC).isoformat(),
        cwd=str(ROOT),
        affinity=sorted(os.sched_getaffinity(0)),
        environment=environment,
        python=sys.version,
        versions={
            name: importlib.metadata.version(name)
            for name in ("numpy", "jax", "jaxlib", "pytest", "scipy")
        },
        commands=[dict(name=name, argv=argv) for name, argv in steps],
        initial_source_sha256=snapshot(output, "initial_sources", files),
        max_command_seconds=480,
        max_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 1024**3,
        scope=(
            "Initial native geometry to ordinary passive tissue with independent physical "
            "equations; no state remap, cuts, moving geometry, native generation rerun "
            "or trajectory qualification"
        ),
    )
    write_json(output / "inputs.json", inputs)
    results, source_hashes, error = [], {}, None
    try:
        if inputs["affinity"] != [7]:
            raise ValueError("Require CPU7 affinity")
        sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
        from validation.assembly.component_process import run_bounded

        for name, argv in steps:
            if name == "lint":
                source_hashes = snapshot(output, "sources", files)
            directory = output / (name + "-guard")
            directory.mkdir()
            began, code = time.monotonic(), 0
            try:
                run_bounded(
                    argv,
                    directory=directory,
                    cwd=ROOT,
                    env=env,
                    timeout=480,
                    max_rss_bytes=2**30,
                    min_available_bytes=8 * 1024**3,
                )
            except subprocess.CalledProcessError as exception:
                code = exception.returncode
            finally:
                (output / (name + ".log")).write_text(
                    "".join(
                        (directory / file).read_text()
                        for file in ("stdout.log", "stderr.log")
                        if (directory / file).is_file()
                    )
                )
            results.append(dict(name=name, exit_code=code, wall_seconds=time.monotonic() - began))
            if code:
                break
    except Exception as exception:
        error = dict(
            type=type(exception).__name__, message=str(exception), traceback=traceback.format_exc()
        )
    changed = [
        relative for relative, sha in source_hashes.items() if digest(ROOT / relative) != sha
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
        and not counts.get("skipped")
    )
    result = dict(
        status="passed" if passed else "failed",
        checks=results,
        tests=counts,
        source_sha256=source_hashes,
        sources_changed_during_checks=changed,
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
