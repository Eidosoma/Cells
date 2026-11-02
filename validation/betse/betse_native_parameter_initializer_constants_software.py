"""Freeze same-p initializer constants; select one bounded native-blocked target."""

import argparse
import json
import os
import runpy
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import betse_native_phase_callbacks_software as callbacks
from validation.betse import betse_native_simulator_construction_software as inherited

FILE = "validation/betse/betse_native_parameter_initializer_constants_software.py"
TEST = "tests/unit/test_betse_native_parameter_initializer_constants.py"
OWNED = ("src/cells/processes/betse_native_parameter_initializer_constants.py", FILE, TEST)
BASE_TARGETS = (
    "test_source_scope_stops_before_geometry_and_ions",
    "test_all_release_gates_precede_authority_or_work",
    "test_actual_source_compilation_is_metadata_only",
    "test_full_conditional_continuation_and_retirement",
    "test_conditional_primary_and_capture_failures_keep_prefix",
    "test_retained_successor_refuses_drift",
    "test_reentrant_attempt_cannot_issue_success",
    "test_runner_target_validation_precedes_worker",
)
BATCH = (
    *(
        (
            "failure-" + mode,
            "test_conditional_primary_and_capture_failures_keep_prefix[" + mode + "]",
        )
        for mode in ("primary", "capture", "combined", "skipped-store", "foreign-locals")
    ),
    *(
        ("drift-" + mode, "test_retained_successor_refuses_drift[" + mode + "]")
        for mode in ("old-data", "new-data", "record", "plot-descriptor")
    ),
    ("reentrant", "test_reentrant_attempt_cannot_issue_success"),
)
TARGETS = (*BASE_TARGETS, *(node for _, node in BATCH if node not in BASE_TARGETS))


def prepare(repository, directory):
    from cells.processes import betse_native_parameter_initializer_constants as stage

    repo = Path(repository).resolve(strict=True)
    if Path(__file__).resolve() != repo / FILE:
        raise ValueError("Prepare the single editable checkout only")
    directory = inherited.separate(
        directory, repo, stage.prefix.parameters.inherited.tissue.aliases.NATIVE
    )
    directory.mkdir(parents=True, exist_ok=False)
    plan = stage.source_plan()
    files = runpy.run_path(str(repo / inherited.CLOSURE_TOOL))["closure"](repo, list(OWNED))
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
            repository=str(repo),
            git_revision=manifest["git_revision"],
            owned_files={name: manifest["files"][name]["sha256"] for name in OWNED},
            external_runtime_paths=[
                str(Path(p).resolve())
                for p in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if p and not Path(p).resolve().is_relative_to(repo)
            ],
            actual_original_source_alias_float_Parameters_INIT_release=False,
            previous_source_review_inferred=False,
            resources=dict(
                cpu=0,
                threads=1,
                metadata_bytes=512 * 2**20,
                software_bytes=2**30,
                wall_seconds=480,
                host_reserve_bytes=8 * 2**30,
            ),
            remaining=(
                "Real actual colormap/plot wrapper authority and coordinated release; "
                "geometry1127 and ions1154 remain separate."
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
    _target(target)

    def run_bounded(command, **kwargs):
        return inherited.guard.run_bounded([*command, "--target", target], **kwargs)

    return callbacks.delegate(
        inherited.software, FILE=FILE, guard=SimpleNamespace(run_bounded=run_bounded)
    )(packet, output)


def batch(packet, output):
    """Sequential focused workers; each retains the existing independent cap.

    This controller does no native/model work. Runs over ten minutes must be
    launched detached by the caller. It never retries a failed worker.
    """
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import identity

    packet = Path(packet).resolve(strict=True)
    inputs = json.loads((packet / "inputs.json").read_text())
    manifest = snapshot.verify(packet / "source", manifest_sha256=inputs["snapshot"]["sha256"])
    output = inherited.separate(
        output, packet, Path(manifest["repository"]), Path("/mnt/workspaces/Cells/betse-v1.5.0")
    )
    if sorted(os.sched_getaffinity(0)) != [0]:
        raise ValueError("CPU0 required")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    snapshot.write_json(
        output / "started.json",
        dict(
            child=identity(),
            packet=inherited.ref(packet / "inputs.json"),
            targets=BATCH,
            retries=False,
            native_release=False,
            resources=dict(
                controller_metadata_bytes=512 * 2**20,
                worker_bytes=2**30,
                worker_wall_seconds=480,
                threads=1,
                cpu=0,
                host_reserve_bytes=8 * 2**30,
            ),
        ),
    )
    rows = []
    primary = None
    try:
        for label, node in BATCH:
            # Do not pass an address-space rlimit to NumPy/JAX subprocesses.
            rss = next(
                line.split()[1]
                for line in Path("/proc/self/status").read_text().splitlines()
                if line.startswith("VmRSS:")
            )
            memory = dict(
                line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
            )
            if (
                int(rss) * 1024 > 512 * 2**20
                or int(memory["MemAvailable"].split()[0]) * 1024 < 8 * 2**30
            ):
                raise ValueError("Metadata/controller memory or host reserve refused")
            if time.monotonic() - started > len(BATCH) * 480 + 120:
                raise ValueError("Controller total scheduling allowance exceeded")
            error = None
            try:
                result = software(packet, output / label, target=node)
            except BaseException as caught:
                error = dict(
                    type=type(caught).__module__ + "." + type(caught).__qualname__,
                    message=str(caught),
                    traceback="".join(traceback.format_exception(caught)),
                )
                failure = output / label / "process/failure.json"
                result = (
                    json.loads(failure.read_text())
                    if failure.is_file()
                    else dict(status="failed", returncode=None)
                )
            terminal = (
                output
                / label
                / "process"
                / ("result.json" if result.get("status") == "completed" else "failure.json")
            )
            row = dict(
                label=label,
                target=node,
                status=result.get("status"),
                returncode=result.get("returncode"),
                operation_error=error,
                terminal=inherited.ref(terminal) if terminal.is_file() else None,
            )
            rows.append(row)
            snapshot.write_json(output / (label + "-terminal.json"), row)
    except BaseException as error:
        primary = dict(
            type=type(error).__module__ + "." + type(error).__qualname__,
            message=str(error),
            traceback="".join(traceback.format_exception(error)),
        )
    failed = (
        primary is not None
        or len(rows) != len(BATCH)
        or any(row["status"] != "completed" for row in rows)
    )
    result = dict(
        status="failed" if failed else "completed",
        returncode=1 if failed else 0,
        primary=primary,
        rows=rows,
        unrun=[label for label, _ in BATCH[len(rows) :]],
        elapsed_seconds=time.monotonic() - started,
        native_or_science_release=False,
        saved_results_still_require_review=True,
    )
    snapshot.write_json(output / ("failure.json" if failed else "result.json"), result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--repository", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--software", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--target", choices=TARGETS)
    parser.add_argument(
        "--batch", type=Path, help="Held packet; launch this long software chain detached"
    )
    args = parser.parse_args()
    if args.child and args.target:
        return child(args.child, target=args.target)
    if args.prepare and not args.software:
        print(json.dumps(prepare(args.repository, args.prepare)))
        return 0
    if args.batch and args.output and not args.prepare and not args.software:
        result = batch(args.batch, args.output)
        print(json.dumps(result))
        return int(result["returncode"])
    if args.software and args.output and args.target and not args.prepare:
        result = software(args.software, args.output, target=args.target)
        print(json.dumps(result))
        return int(result["returncode"])
    parser.error("Choose --prepare or --software/--output/one --target")


if __name__ == "__main__":
    raise SystemExit(main())
