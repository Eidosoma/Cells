"""Immutable CPU6 synthetic controls; no actual vectors or operator execution."""

import argparse
import json
import os
import resource
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from validation.betse import betse_native_multi_cell_world_finalization_software as parent

runner = parent.runner
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_multi_cell_post_world_operators_software.py"
TEST = "tests/unit/test_betse_native_multi_cell_post_world_operators.py"
GROUPS = {
    "contract": "software_ast or software_capture_and_sealing or software_reentrant",
    "ast": "software_ast",
    "smoke": "software_smoke",
    "requests": "software_request_refusal",
    "failures": "software_source_failure",
    "authority-registry": (
        "software_completed_authority and "
        "(world_registry or world_claim or caller_registry or caller_claim)"
    ),
    "authority-live": "software_completed_authority and (observer or rng_observer or binding)",
    "authority-output": "software_completed_authority and (output_value or output_identity)",
    "observation": "software_observation_failure",
    "sealing": "software_capture_and_sealing",
    "reentry": "software_reentrant",
}


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    from cells.processes import betse_native_multi_cell_post_world_operators as stage

    functions = tuple(stage._NATIVE.values())
    codes = {function.__code__: function.__qualname__ for function in functions}
    actual_helpers = (*stage._HELPERS.values(), stage._LOG)
    attempted = []
    previous, trace = sys.getprofile(), sys.gettrace()

    def setprofile(delegate):
        if delegate is None:
            sys.setprofile(previous)
            return

        def profile(frame, event, arg):
            if event == "call" and (
                frame.f_code in codes
                or frame.f_globals.get("__name__") == stage.__name__
                and frame.f_code.co_name == "_helper"
                and any(frame.f_locals.get("delegate") is value for value in actual_helpers)
            ):
                attempted.append(codes.get(frame.f_code, frame.f_code.co_qualname))
                raise AssertionError("Actual native post-world body/helper forbidden")
            delegate(frame, event, arg)
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)

    facade = SimpleNamespace(**dict(vars(sys), setprofile=setprofile))
    try:
        code = parent.inherited._metadata(
            parent.child, ROOT=ROOT, TEST=TEST, GROUPS=GROUPS, sys=facade
        )(output, group)
    finally:
        restored = sys.getprofile() is previous and sys.gettrace() is trace
        sys.setprofile(previous)
        sys.settrace(trace)
        runner.write(
            output / "post-world-native-entry-guard.json",
            dict(
                attempted=attempted,
                blocked_native_methods=list(codes.values()),
                actual_helpers_blocked_before_delegate=True,
                prior_trace_and_profile_restored=restored,
                scientific_credit=False,
            ),
        )
    if attempted:
        raise RuntimeError("A control attempted actual post-world source")
    stage._verify_sources()
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=GROUPS, required=True)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if not output.is_relative_to(runner.BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and a fresh output below /mnt/workspaces/Cells")
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
            "tests/unit/test_betse_native_multi_cell_world_finalization.py",
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
        CELLS_POST_WORLD_EVIDENCE=str(output / "evidence"),
        CELLS_WORLD_DATA_EVIDENCE=str(output / "evidence"),
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
    )
    try:
        process = runner.guard.run_bounded(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_native_multi_cell_post_world_operators_software",
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
    except subprocess.CalledProcessError:
        # The bounded runner has already sealed the failed process outcome.
        # Authenticate its frozen producers and guards without granting passes.
        process = json.loads((output / "process/failure.json").read_text())
    try:
        authority = parent.inherited._metadata(
            parent.inherited.inherited.verify_frozen_execution, TEST=TEST
        )(frozen, manifest_sha, output / "runtime-producers.json")
    except Exception as error:
        runner.write(
            output / "execution-verification-failure.json",
            dict(
                status="failed",
                error=dict(type=type(error).__name__, message=str(error)),
                snapshot_manifest_sha256=manifest_sha,
            ),
        )
        raise
    runner.write(output / "execution-verification.json", authority)
    integration = parent.inherited.inherited.checkout_integration_status(frozen, output)
    runner.write(output / "checkout-integration.json", integration)
    guards = {
        name: json.loads((output / name).read_text())
        for name in (
            "native-entry-guard.json",
            "tail-native-entry-guard.json",
            "post-world-native-entry-guard.json",
        )
    }
    if any(record["attempted"] for record in guards.values()):
        raise RuntimeError("Native source entry guard reported an attempted body")
    if not guards["post-world-native-entry-guard.json"]["prior_trace_and_profile_restored"]:
        raise RuntimeError("Outer source guard was not restored")
    result = dict(
        process,
        synthetic_only=True,
        actual_source_replay_released=False,
        software_group=args.group,
        snapshot_manifest_sha256=manifest_sha,
        git_revision=snapshot["git_revision"],
        junit_sha256=runner.source_snapshot.digest(output / "tests.xml"),
        runtime_producers_sha256=runner.source_snapshot.digest(output / "runtime-producers.json"),
        guard_pins={name: runner.source_snapshot.digest(output / name) for name in guards},
        frozen_execution_authority=authority,
        checkout_integration=integration,
        all11_owners_remain_invalid=True,
        physical_phase_field_checkpoint_admitted=False,
    )
    runner.write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
