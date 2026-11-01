"""Immutable CPU6 native-blocked controls for the multi-cell data tail."""

import argparse
import json
import os
import resource
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

from validation.betse import betse_native_multi_cell_poisson_software as inherited

runner = inherited.runner
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_multi_cell_world_finalization_software.py"
TEST = "tests/unit/test_betse_native_multi_cell_world_finalization.py"
GROUPS = {
    "smoke": "software_same_actual or software_early_failure or software_request_factory",
    "chain": "software_issued_multi_API_chain",
    "contracts": "software and not full_default",
    "capacity": "software_full_default",
}


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    from cells.processes import betse_native_multi_cell_world_finalization as finalization

    actual_methods = tuple(finalization._NATIVE.values())
    codes = {function.__code__: function.__qualname__ for function in actual_methods}
    source_path = str(Path(finalization.source.__file__).resolve())
    actual_helpers = (finalization._ASARRAY, finalization._ONES)
    attempted = []
    previous = sys.getprofile()

    def setprofile(delegate):
        if delegate is None or delegate is previous:
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
    parser.add_argument("--group", choices=tuple(GROUPS), required=True)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if not output.is_relative_to(runner.BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and a fresh /mnt/workspaces/Cells output")
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
            "tests/unit/test_betse_native_multi_cell_poisson.py",
            "tests/unit/test_betse_native_multi_cell_environment.py",
            "tests/unit/test_betse_native_multi_cell_caller.py",
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
            "validation.betse.betse_native_multi_cell_world_finalization_software",
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
