"""Freeze the guarded original four-store continuation and run native-blocked software controls."""

import argparse
import json
import os
import runpy
from pathlib import Path
from types import SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import betse_native_phase_callbacks_software as callbacks
from validation.betse import betse_native_simulator_construction_software as inherited

FILE = "validation/betse/betse_native_parameter_colormap_load_software.py"
TEST = "tests/unit/test_betse_native_parameter_colormap_load.py"
OWNED = (
    "src/cells/processes/betse_native_parameter_colormap_runtime.py",
    "src/cells/processes/betse_native_parameter_colormap_load.py",
    FILE,
    TEST,
)
TARGETS = (
    "test_pinned_reference_is_present_without_import_or_factory",
    "test_gates_hold_before_any_parent_runtime_or_work",
    "test_complete_guarded_conditional_four_stores_same_p_and_real_return_transport",
    "test_source_capture_failures_keep_actual_prefix_primary_and_returns",
    "test_current_successor_rejects_parameter_return_and_evidence_drift",
    "test_reentrant_attempt_cannot_double_enter_or_publish_success",
    "test_inherited_return_unwind_failure_preserves_original_source_cause",
    "test_lazy_missing_runtime_refuses_before_original_invocation",
)


def prepare(repository, directory):
    from cells.processes import betse_native_parameter_colormap_load as stage

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare current Git checkout only")
    directory = inherited.separate(
        directory, repo, stage.prefix.parameters.inherited.tissue.aliases.NATIVE
    )
    directory.mkdir(parents=True, exist_ok=False)
    plan = stage.source_plan()
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
            actual_colormap_lookup_or_constructor_or_INIT_release=False,
            remains=(
                "Actual registry owner and original retained runtime; "
                "original four calls require release; "
                "source is implemented behind release; "
                "next contiguous options/constants/ions remain separate"
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


def _target(target):
    if type(target) is not str or target not in TARGETS:
        raise ValueError("Choose one declared bounded software target")
    return TEST + "::" + target


def child(output, *, target):
    return callbacks.delegate(inherited.child, TEST=_target(target))(output)


def software(packet, output, *, target):
    _target(target)  # Refuse before directories or a worker can be created.

    def run_bounded(command, **kwargs):
        return inherited.guard.run_bounded([*command, "--target", target], **kwargs)

    return callbacks.delegate(
        inherited.software, FILE=FILE, guard=SimpleNamespace(run_bounded=run_bounded)
    )(packet, output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepare", type=Path)
    p.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--software", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    p.add_argument("--target", choices=TARGETS)
    a = p.parse_args()
    if a.child:
        if not a.target:
            p.error("--child requires one bounded --target")
        return child(a.child, target=a.target)
    if a.prepare and not a.software:
        print(json.dumps(prepare(a.repository, a.prepare)))
        return 0
    if a.software and a.output and not a.prepare:
        if not a.target:
            p.error("--software requires one bounded --target")
        result = software(a.software, a.output, target=a.target)
        print(json.dumps(result))
        return int(result["returncode"])
    p.error("Choose --prepare or --software with --output")


if __name__ == "__main__":
    raise SystemExit(main())
