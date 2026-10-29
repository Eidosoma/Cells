"""Bounded native modulation captures and ordered control component checks."""

import argparse
import importlib.metadata
import json
import os
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
    "src/cells/processes/betse_network_modulation.py",
    "tests/unit/test_betse_network_modulation.py",
    "validation/regulation/betse_network_modulation_reference.py",
    "validation/regulation/betse_network_modulation_fixtures.py",
    "validation/regulation/betse_network_modulation_native.py",
    "validation/regulation/betse_network_modulation_protocol.json",
    "agent-work/cells-worker-01/workfiles/check_betse_network_modulation.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--select", help="Optional targeted pytest expression")
    parser.add_argument("--capture-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "betse-network-modulation-development-"
    ):
        parser.error(
            "Use a fresh /mnt/workspaces/Cells/betse-network-modulation-development-* directory"
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
        CUDA_VISIBLE_DEVICES="",
        JAX_ENABLE_COMPILATION_CACHE="false",
        XDG_CACHE_HOME=str(output / "cache"),
        JAX_COMPILATION_CACHE_DIR=str(output / "cache/jax"),
        MPLCONFIGDIR=str(output / "cache/matplotlib"),
        TMPDIR=str(output / "tmp"),
        MALLOC_ARENA_MAX="2",
        CELLS_COMPONENT_BACKEND="cpu",
        CELLS_COMPONENT_EVIDENCE=str(output / "evidence"),
        CELLS_BETSE_MODULATION_NATIVE_CAPTURE=str(output / "native-source"),
    )
    env = os.environ.copy()
    env.update(environment)
    selected_owned = (
        (OWNED[2], OWNED[3], OWNED[4], OWNED[5], OWNED[6]) if args.capture_only else OWNED
    )
    python_files = [p for p in selected_owned if p.endswith(".py")]
    ruff = str(Path(sys.executable).parent / "ruff")
    steps = [
        ("imports", [ruff, "check", "--no-cache", "--select", "I", "--fix", *python_files]),
        ("format", [ruff, "format", "--no-cache", *python_files]),
        ("lint", [ruff, "check", "--no-cache", *python_files]),
        (
            "native",
            [
                sys.executable,
                "-B",
                "-m",
                "validation.regulation.betse_network_modulation_native",
                "--output",
                str(output / "native-source"),
            ],
        ),
    ]
    for name, selection in () if args.capture_only else (("host", "not jax"), ("jax", "jax")):
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
    files = sorted(
        set(selected_owned)
        | {
            "src/cells/processes/electrochemistry.py",
            "src/cells/processes/betse_network_reactions.py",
            "src/cells/numerics/extracellular_field.py",
            "validation/assembly/component_process.py",
            "agent-work/cells-worker-01/workfiles/check_morris_lecar_channels.py",
            "agent-work/cells-worker-01/workfiles/check_water_schema.py",
            "pyproject.toml",
        }
    )
    inputs = dict(
        phase="source-capture-only" if args.capture_only else "complete-component",
        started_utc=datetime.now(UTC).isoformat(),
        cwd=str(ROOT),
        affinity=sorted(os.sched_getaffinity(0)),
        environment=environment,
        python=sys.version,
        versions={
            name: importlib.metadata.version(name) for name in ("numpy", "jax", "jaxlib", "pytest")
        },
        commands=[dict(name=name, argv=argv) for name, argv in steps],
        initial_source_sha256=snapshot(output, "initial_sources", files),
        max_command_seconds=180,
        max_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 1024**3,
        scope=(
            "Component/native isolated-class correspondence and CPU tests; "
            "no full native simulation or tissue integration"
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
                    timeout=180,
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
