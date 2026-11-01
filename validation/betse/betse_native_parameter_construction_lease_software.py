"""Prepare held same-p construction/numeric claims and native-blocked controls."""

import argparse
import json
import os
import runpy
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_native_phase_callbacks_software as callbacks
from validation.betse import betse_native_simulator_construction_software as inherited

FILE = "validation/betse/betse_native_parameter_construction_lease_software.py"
TEST = "tests/unit/test_betse_native_parameter_construction_lease.py"
NUMERIC_TEST = "tests/unit/test_betse_native_parameter_numeric_prefix.py"
OWNED = (
    "src/cells/processes/betse_native_parameter_construction_lease.py",
    "src/cells/processes/betse_native_parameter_numeric_prefix.py",
    FILE,
    TEST,
    NUMERIC_TEST,
)


def prepare(repository, directory):
    from cells.processes import betse_native_parameter_construction_lease as stage
    from cells.processes import betse_native_parameter_numeric_prefix as numeric

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare current Git source only")
    directory = inherited.separate(
        directory, repo, stage.previous.paths.prefix.parameters.inherited.tissue.aliases.NATIVE
    )
    directory.mkdir(parents=True, exist_ok=False)
    plan = dict(
        lease=stage.source_plan(),
        numeric=numeric.source_plan(),
        predecessor_source_sha256=stage.PARENT_SHA256,
        numerical_release=False,
    )
    files = runpy.run_path(str(repo / inherited.CLOSURE_TOOL))["closure"](repo, list(OWNED))
    for name in ("pyproject.toml", "tests/__init__.py", inherited.CLOSURE_TOOL):
        files[name] = snapshot.digest(repo / name)
    manifest = snapshot.freeze(repo, directory / "source", {n: n for n in files})
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            law=stage.LAW_ID,
            held=True,
            automatic_launch=False,
            snapshot=inherited.ref(directory / "source/SNAPSHOT.json"),
            source_plan=inherited.ref(directory / "source-plan.json"),
            repository=str(repo),
            git_revision=manifest["git_revision"],
            owned_files={n: manifest["files"][n]["sha256"] for n in OWNED},
            external_runtime_paths=[
                str(Path(p).resolve())
                for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(repo)
            ],
            actual_constructor_or_phase_or_INIT_release=False,
            remains=(
                "Genuine same-p authority, explicit release and unchanged runtime are required; "
                "the constructor leaf is not phase/dyna/INIT admission"
            ),
            resources=dict(
                cpu=0,
                threads=1,
                metadata_bytes=512 * 2**20,
                software_bytes=2**30,
                wall_seconds=480,
                host_reserve_bytes=8 * 2**30,
            ),
        ),
    )
    return dict(
        inputs=inherited.ref(directory / "inputs.json"), files=len(manifest["files"]), held=True
    )


def child(output):
    import pytest

    from validation.betse.betse_normal_channel_join_runtime import inventory
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import identity

    output = Path(output)
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
                NUMERIC_TEST,
                "--basetemp",
                str(output / "pytest"),
                "--junitxml",
                str(output / "junit.xml"),
            ]
        )
    finally:
        snapshot.write_json(
            output / "runtime.json",
            dict(child=identity(), loaded=inventory(), pytest_status=int(status)),
        )
    return int(status)


def software(packet, output):
    return callbacks.delegate(inherited.software, FILE=FILE)(packet, output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path)
    p.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--software", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    a = p.parse_args()
    if a.child:
        return child(a.child)
    if a.prepare and not a.software:
        print(json.dumps(prepare(a.repository, a.prepare)))
        return 0
    if a.software and a.output and not a.prepare:
        result = software(a.software, a.output)
        print(json.dumps(result))
        return int(result["returncode"])
    p.error("Choose --prepare or --software with --output")


if __name__ == "__main__":
    raise SystemExit(main())
