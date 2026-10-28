"""Bounded CPU-only schema checks with durable source and failure evidence."""

import argparse
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OWNED = (
    "src/cells/core/surface_water_spec.py",
    "tests/unit/test_surface_water_spec.py",
    "configs/resolved_water_tissue.json",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
EXECUTION_FILES = (
    "validation/tissue/surface_water_replay.py",
    "tests/unit/test_surface_water_execution.py",
    "configs/resolved_water_tissue.json",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
ENERGY_FILES = (
    "src/cells/processes/finite_energy.py",
    "tests/unit/test_finite_energy.py",
    "validation/chemistry/finite_energy_reference.py",
    "validation/chemistry/finite_energy_protocol.json",
    "docs/FINITE_ENERGY_POOLS.md",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
ENERGY_TISSUE_FILES = (
    "src/cells/core/surface_energy_spec.py",
    "tests/unit/test_surface_energy_spec.py",
    "src/cells/models/surface_energy.py",
    "tests/unit/test_surface_energy.py",
    "validation/tissue/surface_energy_fixtures.py",
    "validation/tissue/surface_energy_reference.py",
    "configs/resolved_energy_tissue.json",
    "docs/FINITE_ENERGY_POOLS.md",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
COTRANSPORT_FILES = (
    "src/cells/processes/cotransport.py",
    "tests/unit/test_cotransport.py",
    "validation/transport/cotransport_reference.py",
    "validation/transport/cotransport_protocol.json",
    "docs/COTRANSPORT.md",
    "agent-work/cells-worker-01/workfiles/capture_cotransport_source.py",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
COTRANSPORT_TISSUE_FILES = (
    "src/cells/core/surface_cotransport_spec.py",
    "tests/unit/test_surface_cotransport_spec.py",
    "src/cells/models/surface_cotransport.py",
    "tests/unit/test_surface_cotransport.py",
    "validation/tissue/surface_cotransport_fixtures.py",
    "validation/tissue/surface_cotransport_reference.py",
    "configs/resolved_cotransport_tissue.json",
    "docs/TISSUE_COTRANSPORT.md",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
SODIUM_CATALOG_FILES = (
    "src/cells/processes/sodium_catalog.py",
    "tests/unit/test_sodium_catalog.py",
    "validation/channels/sodium_catalog_reference.py",
    "validation/channels/sodium_catalog_protocol.json",
    "docs/SODIUM_CHANNEL_CATALOG.md",
    "agent-work/cells-worker-01/workfiles/capture_sodium_catalog_source.py",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
POTASSIUM_CATALOG_FILES = (
    "src/cells/processes/potassium_catalog.py",
    "tests/unit/test_potassium_catalog.py",
    "validation/channels/potassium_catalog_reference.py",
    "validation/channels/potassium_catalog_protocol.json",
    "docs/POTASSIUM_CHANNEL_CATALOG.md",
    "agent-work/cells-worker-01/workfiles/capture_potassium_catalog_source.py",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
LEAK_CATALOG_FILES = (
    "src/cells/processes/leak_channels.py",
    "tests/unit/test_leak_channels.py",
    "validation/channels/leak_channels_reference.py",
    "validation/channels/leak_channels_protocol.json",
    "docs/LEAK_CHANNEL_CATALOG.md",
    "agent-work/cells-worker-01/workfiles/capture_leak_channels_source.py",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
FINITE_CALCIUM_FILES = (
    "src/cells/processes/finite_calcium_pumps.py",
    "tests/unit/test_finite_calcium_pumps.py",
    "validation/chemistry/finite_calcium_pump_reference.py",
    "validation/chemistry/finite_calcium_pump_protocol.json",
    "docs/FINITE_CALCIUM_PUMPS.md",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
CALCIUM_EXTRA_FILES = (
    "src/cells/processes/calcium_catalog_extra.py",
    "tests/unit/test_calcium_catalog_extra.py",
    "validation/channels/calcium_catalog_extra_reference.py",
    "validation/channels/calcium_catalog_extra_protocol.json",
    "docs/CALCIUM_CHANNEL_EXTRAS.md",
    "agent-work/cells-worker-01/workfiles/capture_calcium_catalog_extra_source.py",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)
CAGPOTASSIUM_FILES = (
    "src/cells/processes/calcium_activated_potassium.py",
    "tests/unit/test_calcium_activated_potassium.py",
    "validation/channels/calcium_activated_potassium_reference.py",
    "validation/channels/calcium_activated_potassium_protocol.json",
    "docs/CALCIUM_ACTIVATED_POTASSIUM.md",
    "agent-work/cells-worker-01/workfiles/capture_calcium_activated_potassium_source.py",
    "agent-work/cells-worker-01/workfiles/check_water_schema.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--scope",
        choices=(
            "schema",
            "execution-contracts",
            "finite-energy",
            "finite-energy-jax",
            "finite-energy-all",
            "finite-energy-tissue",
            "cotransport",
            "cotransport-jax",
            "cotransport-all",
            "cotransport-tissue",
            "cotransport-tissue-jax",
            "sodium-catalog",
            "sodium-catalog-jax",
            "sodium-catalog-all",
            "potassium-catalog",
            "potassium-catalog-jax",
            "potassium-catalog-all",
            "leak-catalog",
            "leak-catalog-jax",
            "leak-catalog-all",
            "finite-calcium",
            "finite-calcium-jax",
            "finite-calcium-all",
            "calcium-extra",
            "calcium-extra-jax",
            "calcium-extra-all",
            "cagpotassium",
            "cagpotassium-jax",
            "cagpotassium-all",
        ),
        default="schema",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != Path("/mnt/workspaces/Cells") or not output.name.startswith(
        (
            "water-volume-schema-20261028-",
            "water-volume-execution-20261028-",
            "finite-energy-contracts-20261028-",
            "finite-energy-tissue-development-20261028-",
            "cotransport-contracts-20261028-",
            "cotransport-tissue-development-20261028-",
            "sodium-catalog-contracts-20261028-",
            "potassium-catalog-contracts-20261028-",
            "leak-catalog-contracts-20261028-",
            "finite-calcium-contracts-20261028-",
            "calcium-extra-contracts-20261028-",
            "cagpotassium-contracts-20261028-",
        )
    ):
        parser.error(
            "Use a fresh assigned /mnt/workspaces/Cells/water-volume-*-20261028-* directory"
        )
    output.mkdir(exist_ok=False)
    for name in ("tmp", "cache", "sources"):
        (output / name).mkdir()
    env = os.environ.copy()
    overrides = dict.fromkeys(
        ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"), "1"
    ) | dict(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTHONPATH=str(ROOT / "src") + os.pathsep + str(ROOT),
        JAX_PLATFORMS="cpu",
        JAX_ENABLE_X64="true",
        CUDA_VISIBLE_DEVICES="",
        XDG_CACHE_HOME=str(output / "cache"),
        JAX_COMPILATION_CACHE_DIR=str(output / "cache" / "jax"),
        MPLCONFIGDIR=str(output / "cache" / "matplotlib"),
        TMPDIR=str(output / "tmp"),
        MALLOC_ARENA_MAX="2",
        CELLS_COMPONENT_BACKEND="cpu",
        CELLS_COMPONENT_EVIDENCE=str(output / "evidence"),
    )
    env.update(overrides)
    transport_scope = args.scope in ("cotransport", "cotransport-jax", "cotransport-all")
    cotransport_tissue_scope = args.scope in ("cotransport-tissue", "cotransport-tissue-jax")
    sodium_scope = args.scope.startswith("sodium-catalog")
    potassium_scope = args.scope.startswith("potassium-catalog")
    leak_scope = args.scope.startswith("leak-catalog")
    finite_calcium_scope = args.scope.startswith("finite-calcium")
    calcium_extra_scope = args.scope.startswith("calcium-extra")
    cagpotassium_scope = args.scope.startswith("cagpotassium")
    energy_scope = (
        args.scope.startswith("finite-energy")
        or transport_scope
        or cotransport_tissue_scope
        or sodium_scope
        or potassium_scope
        or leak_scope
        or finite_calcium_scope
        or calcium_extra_scope
        or cagpotassium_scope
    )
    if energy_scope:
        overrides["JAX_ENABLE_COMPILATION_CACHE"] = "false"
        env.update(overrides)
    ruff = str(Path(sys.executable).parent / "ruff")
    tissue_scope = args.scope in (
        "finite-energy-tissue",
        "cotransport-tissue",
        "cotransport-tissue-jax",
    )
    if cagpotassium_scope:
        owned = CAGPOTASSIUM_FILES
    elif calcium_extra_scope:
        owned = CALCIUM_EXTRA_FILES
    elif finite_calcium_scope:
        owned = FINITE_CALCIUM_FILES
    elif leak_scope:
        owned = LEAK_CATALOG_FILES
    elif potassium_scope:
        owned = POTASSIUM_CATALOG_FILES
    elif sodium_scope:
        owned = SODIUM_CATALOG_FILES
    elif cotransport_tissue_scope:
        owned = COTRANSPORT_TISSUE_FILES
    elif transport_scope:
        owned = COTRANSPORT_FILES
    elif tissue_scope:
        owned = ENERGY_TISSUE_FILES
    elif energy_scope:
        owned = ENERGY_FILES
    else:
        owned = OWNED if args.scope == "schema" else EXECUTION_FILES
    initial_sources = {}
    for relative in owned:
        target = output / "initial_sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
        initial_sources[relative] = digest(target)
    python_files = [p for p in owned if p.endswith(".py")]
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
                "--basetemp=" + str(output / "tmp" / "pytest"),
                "--junitxml=" + str(output / "tests.xml"),
                owned[1],
            ],
        ),
    ]
    if tissue_scope:
        steps[-1][1].append(owned[3])
    if args.scope == "execution-contracts" or energy_scope:
        steps.insert(
            -1,
            (
                "collect",
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "pytest",
                    "--collect-only",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--basetemp=" + str(output / "tmp" / "collect"),
                    "--junitxml=" + str(output / "collection.xml"),
                    owned[1],
                ],
            ),
        )
        if tissue_scope:
            steps[-2][1].append(owned[3])
        if not args.scope.endswith("-all"):
            selector = (
                ("jax" if args.scope.endswith("-jax") else "not jax")
                if energy_scope
                else "host_contracts or history_capture or planning"
            )
            steps[-1][1].extend(["-k", selector])
    if transport_scope and args.scope != "cotransport-jax":
        steps.insert(
            -1,
            (
                "source",
                [
                    sys.executable,
                    "-B",
                    str(
                        ROOT / "agent-work/cells-worker-01/workfiles/capture_cotransport_source.py"
                    ),
                    "--output",
                    str(output / "evidence" / "cpu" / "native-source"),
                ],
            ),
        )
    if sodium_scope and args.scope != "sodium-catalog-jax":
        steps.insert(
            -1,
            (
                "source",
                [
                    sys.executable,
                    "-B",
                    str(
                        ROOT
                        / "agent-work/cells-worker-01/workfiles/capture_sodium_catalog_source.py"
                    ),
                    "--output",
                    str(output / "evidence" / "cpu" / "native-source"),
                ],
            ),
        )
    if potassium_scope and args.scope != "potassium-catalog-jax":
        steps.insert(
            -1,
            (
                "source",
                [
                    sys.executable,
                    "-B",
                    str(
                        ROOT
                        / "agent-work/cells-worker-01/workfiles/capture_potassium_catalog_source.py"
                    ),
                    "--output",
                    str(output / "evidence" / "cpu" / "native-source"),
                ],
            ),
        )
    if leak_scope and args.scope != "leak-catalog-jax":
        steps.insert(
            -1,
            (
                "source",
                [
                    sys.executable,
                    "-B",
                    str(
                        ROOT
                        / "agent-work/cells-worker-01/workfiles/capture_leak_channels_source.py"
                    ),
                    "--output",
                    str(output / "evidence" / "cpu" / "native-source"),
                ],
            ),
        )
    if calcium_extra_scope and args.scope != "calcium-extra-jax":
        steps.insert(
            -1,
            (
                "source",
                [
                    sys.executable,
                    "-B",
                    str(
                        ROOT
                        / "agent-work/cells-worker-01/workfiles"
                        / "capture_calcium_catalog_extra_source.py"
                    ),
                    "--output",
                    str(output / "evidence" / "cpu" / "native-source"),
                ],
            ),
        )
    if cagpotassium_scope and args.scope != "cagpotassium-jax":
        steps.insert(
            -1,
            (
                "source",
                [
                    sys.executable,
                    "-B",
                    str(
                        ROOT
                        / "agent-work/cells-worker-01/workfiles"
                        / "capture_calcium_activated_potassium_source.py"
                    ),
                    "--output",
                    str(output / "evidence" / "cpu" / "native-source"),
                ],
            ),
        )
    inputs = dict(
        started_utc=datetime.now(UTC).isoformat(),
        cwd=str(ROOT),
        affinity=sorted(os.sched_getaffinity(0)),
        environment=overrides,
        commands=[dict(name=name, argv=command) for name, command in steps],
        max_command_seconds=180,
        target_peak_rss_bytes=2**30,
        scope=args.scope,
        min_available_host_memory_bytes=8 * 1024**3 if energy_scope else None,
        process_tree_guard=energy_scope,
        initial_source_sha256=initial_sources,
    )
    write_json(output / "inputs.json", inputs)
    results = []
    source_hashes = {}
    error = None
    try:
        if inputs["affinity"] != [7]:
            raise ValueError("Schema checks require exclusive affinity to CPU 7")
        for name, command in steps:
            if name == "lint":
                sources = (
                    set(ROOT.joinpath("src").rglob("*.py"))
                    | {ROOT / p for p in owned}
                    | {
                        ROOT / "validation/tissue" / (p + ".py")
                        for p in (
                            "surface_dynamics_fixtures",
                            "surface_field_fixtures",
                            "surface_fixtures",
                            "surface_water_fixtures",
                        )
                    }
                )
                for path in sorted(sources):
                    relative = path.relative_to(ROOT)
                    target = output / "sources" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                    source_hashes[str(relative)] = digest(target)
            start = time.monotonic()
            with (output / (name + ".log")).open("w") as stream:
                try:
                    if energy_scope:
                        sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
                        from validation.assembly.component_process import run_bounded

                        directory = output / (name + "-guard")
                        directory.mkdir()
                        try:
                            run_bounded(
                                command,
                                directory=directory,
                                cwd=ROOT,
                                env=env,
                                timeout=inputs["max_command_seconds"],
                                max_rss_bytes=inputs["target_peak_rss_bytes"],
                                min_available_bytes=inputs["min_available_host_memory_bytes"],
                            )
                            code = 0
                        except subprocess.CalledProcessError as exc:
                            code = exc.returncode
                        finally:
                            for filename in ("stdout.log", "stderr.log"):
                                path = directory / filename
                                if path.is_file():
                                    stream.write(path.read_text())
                    else:
                        completed = subprocess.run(
                            command,
                            cwd=ROOT,
                            env=env,
                            stdout=stream,
                            stderr=subprocess.STDOUT,
                            timeout=inputs["max_command_seconds"],
                            check=False,
                        )
                        code = completed.returncode
                except subprocess.TimeoutExpired:
                    code = 124
            results.append(dict(name=name, exit_code=code, wall_seconds=time.monotonic() - start))
            if code:
                break
    except Exception as exc:
        error = dict(type=type(exc).__name__, message=str(exc))
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    changed = [p for p, value in source_hashes.items() if digest(ROOT / p) != value]
    for relative in changed:
        target = output / "changed-sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    counts = {}
    if (output / "tests.xml").is_file():
        suites = list(ET.parse(output / "tests.xml").getroot().iter("testsuite"))
        counts = {
            k: sum(int(s.get(k, "0")) for s in suites)
            for k in (
                "tests",
                "errors",
                "failures",
                "skipped",
            )
        }
    passed = (
        error is None
        and len(results) == len(steps)
        and not any(r["exit_code"] for r in results)
        and peak <= inputs["target_peak_rss_bytes"]
    )
    report = dict(
        status="passed" if passed else "failed",
        checks=results,
        tests=counts,
        peak_child_rss_bytes=peak,
        source_sha256=source_hashes,
        shared_sources_changed_during_checks=changed,
        error=error,
        output_sha256={
            str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
    )
    write_json(output / "result.json", report)
    if not passed:
        write_json(output / "failure.json", report)
    print(
        json.dumps(dict(output=str(output), status=report["status"], tests=counts, peak_rss=peak))
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
