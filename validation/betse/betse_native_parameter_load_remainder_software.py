"""Source-only preparation; software workers require a separate Root release."""

import argparse
import json
import os
import runpy
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_native_phase_callbacks_software as callbacks
from validation.betse import betse_native_simulator_construction_software as inherited

FILE = "validation/betse/betse_native_parameter_load_remainder_software.py"
TEST = "tests/unit/test_betse_native_parameter_load_remainder.py"
OWNED = ("src/cells/processes/betse_native_parameter_load_remainder.py", FILE, TEST)
SOFTWARE_RELEASE = "CELLS_NATIVE_PARAMETER_LOAD_REMAINDER_SOFTWARE_RELEASED"


def prepare_sources(repository, directory, *, file, owned, plan):
    repo = Path(repository).resolve(strict=True)
    caller = Path(file)
    if not (repo / caller).is_file():
        raise ValueError("Actual owned runner/source checkout required")
    directory = inherited.separate(directory, repo, Path("/mnt/workspaces/Cells/betse-v1.5.0"))
    directory.mkdir(parents=True, exist_ok=False)
    files = runpy.run_path(str(repo / inherited.CLOSURE_TOOL))["closure"](repo, list(owned))
    for name in ("pyproject.toml", "tests/__init__.py", inherited.CLOSURE_TOOL):
        files[name] = snapshot.digest(repo / name)
    manifest = snapshot.freeze(repo, directory / "source", {name: name for name in files})
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            law=plan["law"],
            source_only=True,
            held=True,
            automatic_launch=False,
            repository=str(repo),
            git_revision=manifest["git_revision"],
            snapshot=inherited.ref(directory / "source/SNAPSHOT.json"),
            source_plan=inherited.ref(directory / "source-plan.json"),
            owned_files={name: manifest["files"][name]["sha256"] for name in owned},
            external_runtime_paths=[
                str(Path(p).resolve())
                for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(repo)
            ],
            actual_source_native_parser_RNG_phase_or_science_release=False,
            software_executed=False,
            source_or_API_adoption_inferred=False,
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
        inputs=inherited.ref(directory / "inputs.json"),
        source_files=len(manifest["files"]),
        held=True,
    )


def prepare(repository, directory):
    from cells.processes import betse_native_parameter_load_remainder as stage

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare the actual single editable checkout only")
    return prepare_sources(repo, directory, file=FILE, owned=OWNED, plan=stage.source_plan())


def child(output):
    return callbacks.delegate(inherited.child, TEST=TEST)(output)


def software(packet, output):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        raise ValueError("Software execution remains held for Root; source preparation only")
    return callbacks.delegate(inherited.software, FILE=FILE)(packet, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", type=Path)
    mode.add_argument("--software", type=Path)
    mode.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child:
        return child(args.child)
    if args.prepare:
        print(json.dumps(prepare(args.repository, args.prepare)))
        return 0
    if args.software and args.output:
        result = software(args.software, args.output)
        print(json.dumps(result))
        return int(result["returncode"])
    parser.error("--software requires --output")


if __name__ == "__main__":
    raise SystemExit(main())
