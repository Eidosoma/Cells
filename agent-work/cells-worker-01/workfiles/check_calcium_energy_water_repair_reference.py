"""Bounded independent finite-fuel/water prescribed-repair checks."""

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
    "validation/tissue/calcium_energy_water_repair_reference.py",
    "validation/tissue/test_calcium_energy_water_repair_reference.py",
    "validation/tissue/calcium_energy_water_repair_fixtures.py",
    "agent-work/cells-worker-01/workfiles/check_calcium_energy_water_repair_reference.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--select", help="Optional pytest expression for a corrected failing case")
    parser.add_argument("--max-command-seconds", type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.max_command_seconds <= 540:
        parser.error("Attached command allowance must be between 1 and 540 seconds")
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        "calcium-energy-water-repair-reference-"
    ):
        parser.error(
            "Use a fresh /mnt/workspaces/Cells/calcium-energy-water-repair-reference-* directory"
        )
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache"):
        (output / name).mkdir()
    overrides = dict.fromkeys(
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
    )
    overrides.update(
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
    )
    import shutil

    serialized = output / "serialized-inputs"
    shutil.copytree(args.inputs.resolve(), serialized)
    overrides["CELLS_CALCIUM_ENERGY_WATER_REPAIR_INPUTS"] = str(serialized)
    overrides["CELLS_REFERENCE_EVIDENCE"] = str(output / "evidence")
    env = os.environ.copy()
    env.update(overrides)
    ruff = str(Path(sys.executable).parent / "ruff")
    python_files = [relative for relative in OWNED if relative.endswith(".py")]
    steps = [
        ("imports", [ruff, "check", "--no-cache", "--select", "I", "--fix", *python_files]),
        ("format", [ruff, "format", "--no-cache", *python_files]),
        ("lint", [ruff, "check", "--no-cache", *python_files]),
        (
            "pytest",
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp=" + str(output / "tmp/pytest"),
                "--junitxml=" + str(output / "tests.xml"),
                OWNED[1],
            ],
        ),
    ]
    if args.select:
        steps[-1][1].extend(["-k", args.select])
    files = sorted(
        set(OWNED)
        | {
            str(p.relative_to(ROOT))
            for directory in (ROOT / "src", ROOT / "validation")
            for p in directory.rglob("*.py")
        }
        | {
            "tests/unit/test_surface_catalog.py",
            "tests/unit/test_surface_kinetic.py",
            "agent-work/cells-worker-01/workfiles/check_water_schema.py",
            "agent-work/cells-worker-01/workfiles/check_morris_lecar_channels.py",
            "pyproject.toml",
        }
    )
    inputs = dict(
        started_utc=datetime.now(UTC).isoformat(),
        cwd=str(ROOT),
        affinity=sorted(os.sched_getaffinity(0)),
        scope="calcium-energy-water-independent-reference",
        selected_tests=args.select or "all",
        environment=overrides,
        versions={
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "jax", "jaxlib", "pytest")
        },
        python=sys.version,
        commands=[dict(name=name, argv=argv) for name, argv in steps],
        initial_source_sha256=snapshot(output, "initial_sources", files),
        serialized_input_sha256={p.name: digest(p) for p in sorted(serialized.glob("*.json"))},
        max_command_seconds=args.max_command_seconds,
        max_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 1024**3,
        scope_limits=(
            "Independent CPU reference only; no GPU, full-model settling or qualification"
        ),
    )
    write_json(output / "inputs.json", inputs)
    results, source_hashes, error = [], {}, None
    try:
        if inputs["affinity"] != [7]:
            raise ValueError("This wrapper requires CPU7 affinity")
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
                    timeout=args.max_command_seconds,
                    max_rss_bytes=2**30,
                    min_available_bytes=8 * 1024**3,
                )
            except subprocess.CalledProcessError as exc:
                code = exc.returncode
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
    except Exception as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    changed = [relative for relative, h in source_hashes.items() if digest(ROOT / relative) != h]
    if changed:
        snapshot(output, "changed-sources", changed)
    counts = {}
    if (output / "tests.xml").is_file():
        suites = list(ET.parse(output / "tests.xml").getroot().iter("testsuite"))
        counts = {
            key: sum(int(s.get(key, "0")) for s in suites)
            for key in ("tests", "errors", "failures", "skipped")
        }
    passed = (
        error is None
        and len(results) == len(steps)
        and not any(r["exit_code"] for r in results)
        and not set(changed) & set(OWNED)
    )
    report = dict(
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
    write_json(output / "result.json", report)
    if not passed:
        write_json(output / "failure.json", report)
    print(json.dumps(dict(output=str(output), status=report["status"], tests=counts)))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
