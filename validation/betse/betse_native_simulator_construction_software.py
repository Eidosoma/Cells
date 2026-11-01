"""Immutable source preparation and CPU0 blocked Simulator ownership controls."""

import argparse
import json
import os
import runpy
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_qualification_resources as guard
from validation.betse.betse_native_single_cell_dec_parent_software import CLOSURE_TOOL

FILE = "validation/betse/betse_native_simulator_construction_software.py"
TEST = "tests/unit/test_betse_native_simulator_construction.py"
OWNED = ("src/cells/processes/betse_native_simulator_construction.py", FILE, TEST)
BASE = Path("/mnt/workspaces/Cells")


def ref(path):
    return dict(path=str(path), sha256=snapshot.digest(path))


def separate(path, *parents):
    path = Path(path).resolve()
    if not path.is_relative_to(BASE) or any(
        path.is_relative_to(p) or p.is_relative_to(path) for p in parents
    ):
        raise ValueError("Fresh isolated output below /mnt/workspaces/Cells required")
    return path


def prepare(repository, directory):
    from cells.processes import betse_native_simulator_construction as stage

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare current Git source only")
    directory = separate(directory, repo, stage.tissue.aliases.NATIVE)
    directory.mkdir(parents=True, exist_ok=False)
    plan = stage.source_plan()
    closure = runpy.run_path(str(repo / CLOSURE_TOOL))["closure"]
    files = closure(repo, list(OWNED))
    files.update(
        {name: snapshot.digest(repo / name) for name in ("pyproject.toml", "tests/__init__.py")}
    )
    files[CLOSURE_TOOL] = snapshot.digest(repo / CLOSURE_TOOL)
    manifest = snapshot.freeze(repo, directory / "source", {name: name for name in files})
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            law=stage.LAW_ID,
            held=True,
            automatic_launch=False,
            snapshot=ref(directory / "source/SNAPSHOT.json"),
            source_plan=ref(directory / "source-plan.json"),
            git_revision=manifest["git_revision"],
            repository=str(repo),
            external_runtime_paths=[
                str(Path(p).resolve())
                for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(repo)
            ],
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            resources=dict(
                cpu=0,
                threads=1,
                metadata_bytes=512 * 2**20,
                software_bytes=2**30,
                wall_seconds=480,
                host_reserve_bytes=8 * 2**30,
            ),
            actual_constructor_or_phase_or_INIT_release=False,
            remains=plan["phase_prerequisites"],
        ),
    )
    return dict(inputs=ref(directory / "inputs.json"), files=len(manifest["files"]), held=True)


def child(directory):
    import pytest

    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import identity

    status = 2
    try:
        status = pytest.main(
            [
                "-c",
                "pyproject.toml",
                "--noconftest",
                "-p",
                "no:cacheprovider",
                "--import-mode=importlib",
                "-q",
                TEST,
                "--basetemp",
                str(directory / "pytest"),
                "--junitxml",
                str(directory / "junit.xml"),
            ]
        )
    finally:
        snapshot.write_json(
            directory / "runtime.json",
            dict(child=identity(), loaded=inventory(), pytest_status=int(status)),
        )
    return int(status)


def software(packet, directory):
    packet = Path(packet).resolve(strict=True)
    inputs = json.loads((packet / "inputs.json").read_text())
    source = packet / "source"
    manifest = snapshot.verify(source, manifest_sha256=inputs["snapshot"]["sha256"])
    if snapshot.digest(packet / "source-plan.json") != inputs["source_plan"]["sha256"]:
        raise ValueError("Prepared source plan changed")
    repository = Path(manifest["repository"]).resolve()
    directory = separate(directory, packet, repository, Path("/mnt/workspaces/Cells/betse-v1.5.0"))
    if sorted(os.sched_getaffinity(0)) != [0]:
        raise ValueError("CPU0 required")
    directory.mkdir(parents=True, exist_ok=False)
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CELLS_", "PYTEST_"))}
    environment.update(
        PYTHONPATH=os.pathsep.join(
            [str(source / "src"), str(source), *inputs["external_runtime_paths"]]
        ),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONOPTIMIZE="0",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED="0",
        CELLS_ECM_MOLECULE_EVENTS_RELEASED="0",
    )
    process_dir = directory / "process"
    process_dir.mkdir()
    try:
        result = guard.run_bounded(
            [sys.executable, "-B", "-m", FILE[:-3].replace("/", "."), "--child", str(directory)],
            directory=process_dir,
            cwd=source,
            env=environment,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
        )
    except subprocess.CalledProcessError:
        result = json.loads((process_dir / "failure.json").read_text())
    receipts = sorted((directory / "pytest").rglob("native-blocked.json"))
    attempts = sum(len(json.loads(path.read_text())["attempted"]) for path in receipts)
    cases = (
        list(ET.parse(directory / "junit.xml").iter("testcase"))
        if (directory / "junit.xml").is_file()
        else []
    )
    complete_guards = bool(cases) and len(cases) == len(receipts) and attempts == 0
    snapshot.write_json(
        directory / "result.json",
        dict(
            result,
            packet=ref(packet / "inputs.json"),
            actual_native_entries=0 if complete_guards else None,
            guard_receipts=len(receipts),
            guard_attempts=attempts,
            complete_guards=complete_guards,
            software_only=True,
            actual_constructor_or_INIT_release=False,
            note=(
                "Guard receipts, JUnit and actual child inventory require result review; "
                "pytest count alone grants no authority."
            ),
        ),
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--software", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        return child(args.child)
    if args.prepare and not args.software:
        print(json.dumps(prepare(args.repository, args.prepare)))
        return 0
    if args.software and args.output and not args.prepare:
        result = software(args.software, args.output)
        print(json.dumps(result))
        return int(result["returncode"])
    parser.error("Choose --prepare or --software with --output")


if __name__ == "__main__":
    raise SystemExit(main())
