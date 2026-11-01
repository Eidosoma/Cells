"""Native-blocked multi-cell Poisson controls with the accepted immutable runner contract."""

import argparse
import json
import os
import resource
import runpy
import sys
from pathlib import Path
from types import FunctionType

from validation.betse import betse_native_multi_cell_environment_software as inherited

runner = inherited.runner
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_multi_cell_poisson_software.py"
TEST = "tests/unit/test_betse_native_multi_cell_poisson.py"
GROUPS = {
    "contracts": "software and not full_default",
    "capacity": "software_full_default",
}


def _metadata(function, **overrides):
    """Reuse metadata code with explicit test selection; no numerical namespace changes."""
    return FunctionType(
        function.__code__,
        dict(function.__globals__, **overrides),
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    from cells.processes import betse_native_multi_cell_poisson as poisson

    # The accepted inherited guard blocks the same read-only literal Poisson
    # bodies, source constructors, RNG, tree/image and pinv entries. Only this
    # new test module/selection changes; real numerical bodies stay forbidden.
    code = _metadata(inherited.child, ROOT=ROOT, TEST=TEST, GROUPS=GROUPS)(output, group)
    poisson._verify_sources()
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
        p
        for p in environment.get("PYTHONPATH", "").split(os.pathsep)
        if p and not Path(p).resolve().is_relative_to(ROOT)
    ]
    environment.update(
        PYTHONPATH=os.pathsep.join(paths),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        CELLS_POISSON_EVIDENCE=str(output / "evidence"),
        CELLS_MULTI_POISSON_EVIDENCE=str(output / "evidence"),
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
            "validation.betse.betse_native_multi_cell_poisson_software",
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
        authority = _metadata(inherited.verify_frozen_execution, TEST=TEST)(
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
    integration = inherited.checkout_integration_status(frozen, output)
    runner.write(output / "checkout-integration.json", integration)
    attempted = json.loads((output / "native-entry-guard.json").read_text())["attempted"]
    if attempted:
        raise RuntimeError("Actual native source entry was attempted")
    result.update(
        synthetic_only=True,
        actual_source_replay_released=False,
        native_entry_attempts=attempted,
        software_group=args.group,
        all11_owners_remain_invalid=True,
        multi_cell_Poisson_physical_checkpoint_admitted=False,
        git_revision=snapshot["git_revision"],
        snapshot_manifest_sha256=manifest_sha,
        junit_sha256=runner.source_snapshot.digest(output / "tests.xml"),
        runtime_producers_sha256=runner.source_snapshot.digest(output / "runtime-producers.json"),
        execution_verification_sha256=runner.source_snapshot.digest(
            output / "execution-verification.json"
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
