"""Reuse immutable source/resource tooling for blocked native callback controls."""

import argparse
import hashlib
import json
import os
import runpy
from pathlib import Path
from types import FunctionType

from validation import source_snapshot as snapshot
from validation.betse import betse_native_simulator_construction_software as inherited

FILE = "validation/betse/betse_native_phase_callbacks_software.py"
TEST = "tests/unit/test_betse_native_phase_callbacks.py"
OWNED = ("src/cells/processes/betse_native_phase_callbacks.py", FILE, TEST)
INHERITED_SHA256 = "40327422020639cff68cd08ae6a7a7e7123f30a9d43e8f427b0f411712bcefd4"


def delegate(function, **changes):
    if hashlib.sha256(Path(inherited.__file__).read_bytes()).hexdigest() != INHERITED_SHA256:
        raise ValueError("Explicit original software-runner producer required")
    namespace = dict(function.__globals__, **changes)
    cached = function.__builtins__
    resolved = namespace["__builtins__"]
    if not isinstance(resolved, dict):
        resolved = vars(resolved)
    if resolved is not cached:
        raise ValueError("Inherited runner cached builtins mismatch")
    value = FunctionType(
        function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__
    )
    if value.__builtins__ is not cached:
        raise ValueError("Private runner cached builtins mismatch")
    return value


def prepare(repository, directory):
    from cells.processes import betse_native_phase_callbacks as stage

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare current checkout only")
    directory = inherited.separate(directory, repo, stage.simulator.tissue.aliases.NATIVE)
    directory.mkdir(parents=True, exist_ok=False)
    plan = stage.source_plan()
    closure = runpy.run_path(str(repo / inherited.CLOSURE_TOOL))["closure"]
    files = closure(repo, list(OWNED))
    for name in ("pyproject.toml", "tests/__init__.py", inherited.CLOSURE_TOOL):
        files[name] = snapshot.digest(repo / name)
    manifest = snapshot.freeze(repo, directory / "source", {name: name for name in files})
    snapshot.write_json(directory / "source-plan.json", plan)
    snapshot.write_json(
        directory / "inputs.json",
        dict(
            law=stage.LAW_ID,
            held=True,
            automatic_launch=False,
            snapshot=inherited.ref(directory / "source/SNAPSHOT.json"),
            source_plan=inherited.ref(directory / "source-plan.json"),
            git_revision=manifest["git_revision"],
            repository=str(repo),
            owned_files={n: manifest["files"][n]["sha256"] for n in OWNED},
            inherited_runner_sha256=INHERITED_SHA256,
            external_runtime_paths=[
                str(Path(p).resolve())
                for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(repo)
            ],
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
    return dict(
        inputs=inherited.ref(directory / "inputs.json"), files=len(manifest["files"]), held=True
    )


def child(output):
    return delegate(inherited.child, TEST=TEST)(output)


def software(packet, output):
    return delegate(inherited.software, FILE=FILE)(packet, output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path)
    p.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--software", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    args = p.parse_args()
    if args.child:
        return child(args.child)
    if args.prepare and not args.software:
        print(json.dumps(prepare(args.repository, args.prepare)))
        return 0
    if args.software and args.output and not args.prepare:
        result = software(args.software, args.output)
        print(json.dumps(result))
        return int(result["returncode"])
    p.error("Choose --prepare or --software with --output")


if __name__ == "__main__":
    raise SystemExit(main())
