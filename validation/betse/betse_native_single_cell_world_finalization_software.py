"""Immutable CPU6 native-blocked controls for the single-cell data tail."""

import argparse
import json
import os
import resource
import runpy
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from validation.betse import betse_native_multi_cell_poisson_software as inherited

runner = inherited.runner
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_single_cell_world_finalization_software.py"
TEST = "tests/unit/test_betse_native_single_cell_world_finalization.py"
GROUPS = {
    "smoke": "software_same_caller or software_literal or software_multi_owner",
    "registry": "software_registry",
    "ownership": "software_ownership",
    "retention": "software_retention",
    "contracts": "software and not full_default",
    "capacity": "software_full_default",
    "registry_env": "software_registry_every and (environment or ecm or geometry)",
    "registry_caller": "software_registry_every and (completion or mesh or image)",
    "registry_parents": "software_registry_every and (caller or parameter)",
    "registry_entry": "software_registry_before",
    "ownership_values": "software_ownership and (cell_i_alias or old_list or operator or RNG)",
    "ownership_code": "software_ownership and (observer or helper or namespace or descriptor)",
    "retention_source": "software_retention_source",
    "retention_capture": "software_retention_capture",
}
OWNED = (
    "src/cells/processes/betse_native_single_cell_world_finalization.py",
    "src/cells/processes/betse_native_single_cell_poisson.py",
    TEST,
    OWN,
)
BATCH_GROUPS = (
    "smoke",
    "ownership_values",
    "ownership_code",
    "retention_source",
    "retention_capture",
    "registry_env",
    "registry_caller",
    "registry_parents",
    "registry_entry",
    "capacity",
)


def _closure():
    closure = runpy.run_path(str(ROOT / runner.CLOSURE_TOOL))["closure"]
    paths = closure(
        ROOT,
        [
            OWN,
            TEST,
            "tests/unit/test_betse_native_single_cell_poisson.py",
            "tests/unit/test_betse_native_single_cell_environment.py",
            "tests/unit/test_betse_native_single_cell_make_ecm.py",
            "tests/unit/test_betse_native_single_cell_initial_geometry.py",
            "tests/unit/test_betse_native_single_cell_caller_completion.py",
        ],
    )
    paths[runner.CLOSURE_TOOL] = runner.source_snapshot.digest(ROOT / runner.CLOSURE_TOOL)
    return paths


def _worker_environment(source_root):
    value = dict(os.environ)
    paths = [str(source_root), str(source_root / "src")]
    paths += [
        path
        for path in value.get("PYTHONPATH", "").split(os.pathsep)
        if path and not Path(path).resolve().is_relative_to(ROOT)
    ]
    value.update(
        PYTHONPATH=os.pathsep.join(paths),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    value.pop("PYTEST_ADDOPTS", None)
    return value


def launch_batch(output):
    """Detach one metadata controller; every software group keeps its own guard/image."""
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "controller-source"
    snapshot = runner.source_snapshot.freeze(ROOT, frozen, {name: name for name in _closure()})
    manifest = runner.source_snapshot.digest(frozen / "SNAPSHOT.json")
    runner.write(
        output / "batch-inputs.json",
        dict(
            kind="single_cell_data_tail_blocked_software_batch",
            repository=str(ROOT),
            git_revision=snapshot["git_revision"],
            snapshot_manifest_sha256=manifest,
            owned_source_sha256={name: snapshot["files"][name]["sha256"] for name in OWNED},
            groups=list(BATCH_GROUPS),
            selectors={name: GROUPS[name] for name in BATCH_GROUPS},
            synthetic_only=True,
            numerical_or_native_release=False,
            per_worker_limits=dict(
                cpu=6, threads=1, memory_bytes=2**30, wall_seconds=480, host_reserve_bytes=8 * 2**30
            ),
        ),
    )
    runner.source_snapshot.assert_checkout_unchanged(frozen)
    with (
        (output / "controller.stdout.log").open("x") as out,
        (output / "controller.stderr.log").open("x") as err,
    ):
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_native_single_cell_world_finalization_software",
                "--output",
                str(output),
                "--_batch-child",
            ],
            cwd=frozen,
            env=_worker_environment(frozen),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
    launch = dict(
        status="detached_software_only",
        pid=process.pid,
        process_group=process.pid,
        utc=datetime.now(timezone.utc).isoformat(),
        controller_snapshot_sha256=manifest,
        automatic_retry=False,
        result_path=str(output / "BATCH-RESULT.json"),
        failure_path=str(output / "BATCH-FAILURE.json"),
    )
    runner.write(output / "LAUNCH.json", launch)
    print(
        json.dumps(dict(status=launch["status"], output=str(output), result=launch["result_path"]))
    )
    return 0


def batch_child(output):
    """Verify each exact frozen execution; stop on failure without retry or promotion."""
    import xml.etree.ElementTree as ET

    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    inputs = json.loads((output / "batch-inputs.json").read_text())
    canonical = Path(inputs["repository"])
    expected = inputs["owned_source_sha256"]
    outcomes = []
    stage = "controller_verification"
    try:
        runner.source_snapshot.verify(
            output / "controller-source", manifest_sha256=inputs["snapshot_manifest_sha256"]
        )
        for group in inputs["groups"]:
            stage = group
            runner.source_snapshot._selected(canonical, sorted(expected))
            if any(
                runner.source_snapshot.digest(canonical / name) != sha
                for name, sha in expected.items()
            ):
                raise RuntimeError("Selected owned source drifted; no later worker launched")
            directory = output / group
            with (
                (output / (group + ".launch.stdout.log")).open("x") as out,
                (output / (group + ".launch.stderr.log")).open("x") as err,
            ):
                process = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(canonical / OWN),
                        "--output",
                        str(directory),
                        "--group",
                        group,
                    ],
                    cwd=canonical,
                    env=_worker_environment(canonical),
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=False,
                )
            artifact = directory / (
                "result.json" if process.returncode == 0 else "process/failure.json"
            )
            row = dict(
                group=group,
                path=str(directory),
                returncode=process.returncode,
                terminal_artifact=str(artifact),
                terminal_artifact_sha256=runner.source_snapshot.digest(artifact)
                if artifact.is_file()
                else None,
            )
            outcomes.append(row)
            runner.write(output / (group + ".terminal.json"), row)
            if process.returncode:
                raise RuntimeError("Focused software group failed: " + group)
            data = json.loads((directory / "inputs.json").read_text())
            selected = runner.source_snapshot.verify(
                directory / "tested-source", manifest_sha256=data["snapshot_manifest_sha256"]
            )
            if any(selected["files"][name]["sha256"] != sha for name, sha in expected.items()):
                raise RuntimeError("Worker executed another selected source version")
            authority = inherited._metadata(inherited.inherited.verify_frozen_execution, TEST=TEST)(
                directory / "tested-source",
                data["snapshot_manifest_sha256"],
                directory / "runtime-producers.json",
            )
            for name in ("native-entry-guard.json", "tail-native-entry-guard.json"):
                if json.loads((directory / name).read_text())["attempted"]:
                    raise RuntimeError("Native entry attempted")
            cases = ET.parse(directory / "tests.xml").findall(".//testcase")
            if any(
                case.find("failure") is not None
                or case.find("error") is not None
                or case.find("skipped") is not None
                for case in cases
            ):
                raise RuntimeError("Saved software case failed or skipped")
            row.update(
                software_passes=len(cases),
                case_names=[case.get("name") for case in cases],
                immutable_authority=authority,
                snapshot_sha256=data["snapshot_manifest_sha256"],
                junit_sha256=runner.source_snapshot.digest(directory / "tests.xml"),
            )
        if any(
            runner.source_snapshot.digest(canonical / name) != sha for name, sha in expected.items()
        ):
            raise RuntimeError(
                "Current owned source changed after frozen executions; integration pending"
            )
        names = [name for row in outcomes for name in row["case_names"]]
        if len(names) != len(set(names)):
            raise RuntimeError(
                "Focused selectors overlap; preserve outcomes without additive credit"
            )
        runner.write(
            output / "BATCH-RESULT.json",
            dict(
                status="completed_blocked_software_only",
                utc=datetime.now(timezone.utc).isoformat(),
                owned_source_sha256=expected,
                controller_snapshot_sha256=inputs["snapshot_manifest_sha256"],
                distinct_passed_controls=len(names),
                outcomes=outcomes,
                native_or_numerical_credit=0,
                all11_owners_invalid=True,
                all12_postcut_science_held=True,
                physical_checkpoint_full_world_admitted=False,
                automatic_retry=False,
                source_result_review_required=True,
            ),
        )
        return 0
    except Exception as error:
        runner.write(
            output / "BATCH-FAILURE.json",
            dict(
                status="failed_software_or_binding",
                utc=datetime.now(timezone.utc).isoformat(),
                stage=stage,
                error_type=type(error).__name__,
                message=str(error),
                outcomes=outcomes,
                owned_source_sha256=expected,
                native_or_numerical_credit=0,
                automatic_retry=False,
            ),
        )
        return 1


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    from cells.processes import betse_native_single_cell_world_finalization as finalization

    actual_methods = tuple(finalization._NATIVE.values())
    codes = {function.__code__: function.__qualname__ for function in actual_methods}
    source_path = str(Path(finalization.source.__file__).resolve())
    actual_helpers = (finalization._ASARRAY, finalization._ONES)
    attempted = []
    previous = sys.getprofile()

    def setprofile(delegate):
        if delegate is None:
            sys.setprofile(previous)
            return

        def profile(frame, event, arg):
            if event == "call" and (
                frame.f_code in codes
                or frame.f_code.co_filename == source_path
                and frame.f_code.co_name in finalization.METHODS
                or frame.f_globals.get("__name__") == finalization.__name__
                and frame.f_code.co_name == "_helper"
                and any(frame.f_locals.get("delegate") is helper for helper in actual_helpers)
            ):
                attempted.append(codes.get(frame.f_code, frame.f_code.co_qualname))
                raise AssertionError("Actual data-tail body/helper execution forbidden")
            delegate(frame, event, arg)
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)

    # Only the reusable metadata runner's sys lookup is adapted. The real sys
    # module and every production/kernel namespace stay unchanged. Nested
    # source observers keep chaining this combined native-entry guard.
    namespace = SimpleNamespace(**dict(vars(sys), setprofile=setprofile))
    try:
        code = inherited._metadata(
            inherited.inherited.child, ROOT=ROOT, TEST=TEST, GROUPS=GROUPS, sys=namespace
        )(output, group)
    finally:
        restored = sys.getprofile() is previous
        sys.setprofile(previous)
        runner.write(
            output / "tail-native-entry-guard.json",
            dict(
                attempted=attempted,
                blocked_methods=[function.__qualname__ for function in actual_methods],
                production_helpers_blocked_before_delegate=["asarray", "ones"],
                previous_profiler_restored=restored,
                numerical_credit=False,
            ),
        )
    if attempted:
        raise RuntimeError("A control attempted actual data-tail source work")
    finalization._verify_sources()
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=tuple(GROUPS))
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--_batch-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if not output.is_relative_to(runner.BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and a fresh /mnt/workspaces/Cells output")
    if args._batch_child:
        return batch_child(output)
    if args.batch:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return launch_batch(output)
    if args.group is None:
        parser.error("Require --group or --batch")
    if args._child:
        return child(output, args.group)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    closure = runpy.run_path(str(ROOT / runner.CLOSURE_TOOL))["closure"]
    files = closure(
        ROOT,
        [
            OWN,
            TEST,
            "tests/unit/test_betse_native_single_cell_poisson.py",
            "tests/unit/test_betse_native_single_cell_environment.py",
            "tests/unit/test_betse_native_single_cell_make_ecm.py",
            "tests/unit/test_betse_native_single_cell_initial_geometry.py",
            "tests/unit/test_betse_native_single_cell_caller_completion.py",
        ],
    )
    files[runner.CLOSURE_TOOL] = runner.source_snapshot.digest(ROOT / runner.CLOSURE_TOOL)
    frozen = output / "tested-source"
    snapshot = runner.source_snapshot.freeze(ROOT, frozen, {name: name for name in files})
    manifest_sha = runner.source_snapshot.digest(frozen / "SNAPSHOT.json")
    runner.write(
        output / "inputs.json",
        dict(
            git_revision=snapshot["git_revision"],
            snapshot_manifest_sha256=manifest_sha,
            source_sha256={name: row["sha256"] for name, row in snapshot["files"].items()},
            selected_tests=[TEST],
            software_group=args.group,
            pytest_selection=GROUPS[args.group],
            synthetic_only=True,
            actual_source_replay_released=False,
        ),
    )
    environment = dict(os.environ)
    paths = [str(frozen), str(frozen / "src")]
    paths += [
        path
        for path in environment.get("PYTHONPATH", "").split(os.pathsep)
        if path and not Path(path).resolve().is_relative_to(ROOT)
    ]
    environment.update(
        PYTHONPATH=os.pathsep.join(paths),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CELLS_WORLD_DATA_EVIDENCE=str(output / "evidence"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    result = runner.guard.run_bounded(
        [
            sys.executable,
            "-B",
            "-m",
            "validation.betse.betse_native_single_cell_world_finalization_software",
            "--output",
            str(output),
            "--group",
            args.group,
            "--_child",
        ],
        directory=output / "process",
        cwd=frozen,
        env=environment,
        timeout=480,
        max_rss_bytes=2**30,
        min_available_bytes=8 * 2**30,
        process_tree_memory_metric="rss",
    )
    try:
        authority = inherited._metadata(inherited.inherited.verify_frozen_execution, TEST=TEST)(
            frozen, manifest_sha, output / "runtime-producers.json"
        )
    except Exception as error:
        runner.write(
            output / "execution-verification-failure.json",
            dict(
                status="frozen_execution_evidence_invalid",
                error_type=type(error).__name__,
                message=str(error),
                snapshot_manifest_sha256=manifest_sha,
                numerical_credit=False,
            ),
        )
        raise
    runner.write(output / "execution-verification.json", authority)
    integration = inherited.inherited.checkout_integration_status(frozen, output)
    runner.write(output / "checkout-integration.json", integration)
    attempted = json.loads((output / "native-entry-guard.json").read_text())["attempted"]
    tail = json.loads((output / "tail-native-entry-guard.json").read_text())
    if attempted or tail["attempted"] or not tail["previous_profiler_restored"]:
        raise RuntimeError("Native-entry/profiler guard failed")
    result.update(
        synthetic_only=True,
        actual_source_replay_released=False,
        native_entry_attempts=attempted,
        tail_native_entry_attempts=tail["attempted"],
        software_group=args.group,
        all11_owners_remain_invalid=True,
        full_world_physical_checkpoint_admitted=False,
        git_revision=snapshot["git_revision"],
        snapshot_manifest_sha256=manifest_sha,
        junit_sha256=runner.source_snapshot.digest(output / "tests.xml"),
        runtime_producers_sha256=runner.source_snapshot.digest(output / "runtime-producers.json"),
        execution_verification_sha256=runner.source_snapshot.digest(
            output / "execution-verification.json"
        ),
        tail_native_guard_sha256=runner.source_snapshot.digest(
            output / "tail-native-entry-guard.json"
        ),
        checkout_integration_sha256=runner.source_snapshot.digest(
            output / "checkout-integration.json"
        ),
        integration_pending=integration["integration_pending"],
        explicit_later_integration_check_required=integration[
            "explicit_later_integration_check_required"
        ],
    )
    runner.write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
