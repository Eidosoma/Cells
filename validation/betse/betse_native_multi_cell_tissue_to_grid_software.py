"""Immutable CPU6 mapping controls; actual conversion/interpolation stays blocked."""

import argparse
import json
import os
import resource
import runpy
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from validation.betse import betse_native_multi_cell_post_world_operators_software as inherited

runner = inherited.runner
metadata = inherited.parent.inherited._metadata
ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/betse_native_multi_cell_tissue_to_grid_software.py"
TEST = "tests/unit/test_betse_native_multi_cell_tissue_to_grid.py"
OWNED = (
    "src/cells/processes/betse_native_tissue_to_grid_source.py",
    "src/cells/processes/betse_native_multi_cell_tissue_to_grid.py",
    "src/cells/processes/betse_native_multi_cell_caller.py",
    TEST,
    OWN,
)
GROUPS = {
    "pilot": "software_profile_unit",
    "audit": ("software_source_ast or software_cached_proof or software_missing_world"),
    "smoke": "software_readonly_same_caller",
    "lease": "software_raw_entry or software_lease_requires",
    "write": "software_readonly_attr",
    "callback": "software_lease_callback",
    "failure": "software_helper_failure or software_enter_capture",
    "d1": "software_completed_stale and (input or helper)",
    "d2": "software_completed_stale and (equal_result_identity or observer_code)",
    "capture": "software_profile_owner",
}
BATCH_GROUPS = tuple(GROUPS)
EXPECTED = {
    "pilot": (
        "test_software_profile_unit_return_failure_is_deferred[success]",
        "test_software_profile_unit_return_failure_is_deferred[unwind]",
        "test_software_profile_unit_return_failure_is_deferred[falsey]",
        "test_software_profile_unit_entry_guard_is_immediate[python]",
        "test_software_profile_unit_entry_guard_is_immediate[c]",
        "test_software_profile_unit_c_exception_keeps_original_error",
        "test_software_profile_unit_retains_both_local_and_prior_failures",
        "test_software_profile_unit_unchanged_observer_restores_chain",
    ),
    "audit": (
        "test_software_source_ast_exact_methods_and_helper_roster",
        "test_software_cached_proof_requires_exact_current_bytes",
        "test_software_missing_world_authority_retains_unsealed_request",
    ),
    "smoke": ("test_software_readonly_same_caller_zero_mask_probe_results",),
    "lease": (
        "test_software_raw_entry_without_lease_never_enters_source[grids]",
        "test_software_raw_entry_without_lease_never_enters_source[points]",
        "test_software_lease_requires_issued_mapping_request",
    ),
    "write": ("test_software_readonly_attr_write_and_reentry_are_blocked",),
    "callback": (
        "test_software_lease_callback_code_drift_stops_before_callback[check]",
        "test_software_lease_callback_code_drift_stops_before_callback[invoke]",
    ),
    "failure": (
        "test_software_helper_failure_keeps_primary_and_releases_parent",
        "test_software_enter_capture_failure_stops_delegate",
    ),
    "d1": (
        "test_software_completed_stale_authority_refuse[input]",
        "test_software_completed_stale_authority_refuse[helper]",
    ),
    "d2": (
        "test_software_completed_stale_authority_refuse[equal_result_identity]",
        "test_software_completed_stale_authority_refuse[observer_code]",
    ),
    "capture": (
        "test_software_profile_owner_keeps_primary_and_partial_return[success]",
        "test_software_profile_owner_keeps_primary_and_partial_return[unwind]",
        "test_software_profile_owner_keeps_primary_and_partial_return[falsey]",
    ),
}


def closure():
    tool = runpy.run_path(str(ROOT / runner.CLOSURE_TOOL))["closure"]
    files = tool(
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
    return files


def environment(source_root):
    env = dict(os.environ)
    paths = [str(source_root), str(source_root / "src")] + [
        p
        for p in env.get("PYTHONPATH", "").split(os.pathsep)
        if p and not Path(p).resolve().is_relative_to(ROOT)
    ]
    env.update(
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
    env.pop("PYTEST_ADDOPTS", None)
    return env


def child(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    from cells.processes import betse_native_multi_cell_tissue_to_grid as mapping

    original = (*mapping._NATIVE.values(), mapping._FROM, mapping._SEQUENCE)
    codes = {fn.__code__: fn.__qualname__ for fn in original}
    delegates = (mapping._ASARRAY, mapping._GRIDDATA)
    attempted = []
    previous, trace = sys.getprofile(), sys.gettrace()

    def setprofile(delegate):
        if delegate is None:
            sys.setprofile(previous)
            return

        def profile(frame, event, arg):
            if event == "call" and (
                frame.f_code in codes
                or frame.f_globals.get("__name__") == mapping.__name__
                and frame.f_code.co_name == "_helper"
                and any(frame.f_locals.get("delegate") is value for value in delegates)
            ):
                attempted.append(frame.f_code.co_qualname)
                raise AssertionError(
                    "Actual mapping/helper/conversion/interpolation execution forbidden"
                )
            delegate(frame, event, arg)
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)

    facade = SimpleNamespace(**dict(vars(sys), setprofile=setprofile))
    previous_addopts = os.environ.get("PYTEST_ADDOPTS")
    os.environ["PYTEST_ADDOPTS"] = "--tb=short"
    try:
        code = metadata(inherited.child, ROOT=ROOT, TEST=TEST, GROUPS=GROUPS, sys=facade)(
            output, group
        )
    finally:
        if previous_addopts is None:
            os.environ.pop("PYTEST_ADDOPTS", None)
        else:
            os.environ["PYTEST_ADDOPTS"] = previous_addopts
        restored = sys.getprofile() is previous and sys.gettrace() is trace
        sys.setprofile(previous)
        sys.settrace(trace)
        runner.write(
            output / "mapping-native-entry-guard.json",
            dict(
                attempted=attempted,
                blocked_codes=list(codes.values()),
                actual_conversion_and_griddata_blocked=True,
                prior_trace_and_profile_restored=restored,
                scientific_credit=0,
            ),
        )
    if attempted:
        raise RuntimeError("A control attempted actual mapping work")
    mapping._verify_sources()
    return code


def run_group(output, group):
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    (output / "process").mkdir()
    frozen = output / "tested-source"
    snap = runner.source_snapshot.freeze(ROOT, frozen, {name: name for name in closure()})
    manifest = runner.source_snapshot.digest(frozen / "SNAPSHOT.json")
    expected = json.loads(os.environ.get("CELLS_MAPPING_EXPECTED_OWNED", "null"))
    if expected is not None and (
        set(expected) != set(OWNED)
        or any(snap["files"][name]["sha256"] != expected[name] for name in OWNED)
    ):
        raise RuntimeError("Selected mapping bytes changed before worker freeze; no child launched")
    runner.write(
        output / "inputs.json",
        dict(
            git_revision=snap["git_revision"],
            snapshot_manifest_sha256=manifest,
            source_sha256={name: row["sha256"] for name, row in snap["files"].items()},
            expected_owned_source_sha256=expected,
            software_group=group,
            pytest_selection=GROUPS[group],
            synthetic_only=True,
            native_release=False,
        ),
    )
    env = environment(frozen)
    env["CELLS_MAPPING_EVIDENCE"] = str(output / "evidence")
    try:
        result = runner.guard.run_bounded(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_native_multi_cell_tissue_to_grid_software",
                "--output",
                str(output),
                "--group",
                group,
                "--_child",
            ],
            directory=output / "process",
            cwd=frozen,
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
            process_tree_memory_metric="rss",
        )
    except Exception:
        failure = output / "process/failure.json"
        result = (
            json.loads(failure.read_text())
            if failure.is_file()
            else dict(
                status="failed_guard_without_terminal",
                returncode=None,
                traceback=traceback.format_exc(),
            )
        )
    guard_names = (
        "native-entry-guard.json",
        "tail-native-entry-guard.json",
        "post-world-native-entry-guard.json",
        "mapping-native-entry-guard.json",
    )
    missing = [
        n
        for n in ("tests.xml", "runtime-producers.json", *guard_names)
        if not (output / n).is_file()
    ]
    if missing:
        runner.write(
            output / "result.json",
            dict(
                result,
                status="failed_incomplete_software",
                missing=missing,
                snapshot_manifest_sha256=manifest,
                scientific_credit=0,
            ),
        )
        return 1
    tools = inherited.parent.inherited.inherited
    executed = [n.attrib["name"] for n in ET.parse(output / "tests.xml").iter("testcase")]
    if sorted(executed) != sorted(EXPECTED[group]):
        raise RuntimeError("Unexpected mapping control selection: " + repr(executed))
    authority = metadata(tools.verify_frozen_execution, TEST=TEST)(
        frozen, manifest, output / "runtime-producers.json"
    )
    integration = tools.checkout_integration_status(frozen, output)
    guards = {n: json.loads((output / n).read_text()) for n in guard_names}
    if any(g["attempted"] for g in guards.values()):
        raise RuntimeError("Native mapping/source entry attempted")
    if not guards["mapping-native-entry-guard.json"]["prior_trace_and_profile_restored"]:
        raise RuntimeError("Outer guard not restored")
    result.update(
        snapshot_manifest_sha256=manifest,
        executed_control_ids=executed,
        frozen_execution_authority=authority,
        checkout_integration=integration,
        guard_pins={n: runner.source_snapshot.digest(output / n) for n in guards},
        junit_sha256=runner.source_snapshot.digest(output / "tests.xml"),
        runtime_producers_sha256=runner.source_snapshot.digest(output / "runtime-producers.json"),
        synthetic_only=True,
        native_release=False,
        all11_owners_invalid=True,
        all12_postcut_science_held=True,
        physical_phase_field_checkpoint_admitted=False,
    )
    runner.write(output / "result.json", result)
    print(json.dumps(dict(status=result["status"], output=str(output))))
    return int(result["returncode"])


def launch_batch(output, groups=None):
    groups = BATCH_GROUPS if groups is None else tuple(groups)
    if not groups or len(set(groups)) != len(groups) or any(g not in GROUPS for g in groups):
        raise ValueError("Declare unique bounded software groups")
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "controller-source"
    snap = runner.source_snapshot.freeze(ROOT, frozen, {name: name for name in closure()})
    manifest = runner.source_snapshot.digest(frozen / "SNAPSHOT.json")
    runner.write(
        output / "batch-inputs.json",
        dict(
            repository=str(ROOT),
            git_revision=snap["git_revision"],
            snapshot_manifest_sha256=manifest,
            owned_source_sha256={n: snap["files"][n]["sha256"] for n in OWNED},
            groups=groups,
            selectors={g: GROUPS[g] for g in groups},
            expected_control_ids={g: EXPECTED[g] for g in groups},
            synthetic_only=True,
            native_release=False,
            cpu=6,
            threads=1,
            memory_bytes=2**30,
            wall_per_group_seconds=480,
            reserve_bytes=8 * 2**30,
        ),
    )
    runner.source_snapshot.assert_checkout_unchanged(frozen)
    inputs_sha = runner.source_snapshot.digest(output / "batch-inputs.json")
    (output / "batch-inputs.json").chmod(0o444)
    with (
        (output / "controller.stdout.log").open("x") as out,
        (output / "controller.stderr.log").open("x") as err,
    ):
        process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_native_multi_cell_tissue_to_grid_software",
                "--output",
                str(output),
                "--_batch-child",
                "--_batch-inputs-sha256",
                inputs_sha,
            ],
            cwd=frozen,
            env=environment(frozen),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
    runner.write(
        output / "LAUNCH.json",
        dict(
            status="detached_blocked_software_only",
            pid=process.pid,
            process_group=process.pid,
            utc=datetime.now(timezone.utc).isoformat(),
            controller_snapshot_sha256=manifest,
            batch_inputs_sha256=inputs_sha,
            result_path=str(output / "BATCH-RESULT.json"),
            failure_path=str(output / "BATCH-FAILURE.json"),
            automatic_retry=False,
        ),
    )
    print(
        json.dumps(
            dict(
                status="detached_blocked_software_only",
                output=str(output),
                result=str(output / "BATCH-RESULT.json"),
            )
        )
    )
    return 0


def batch_child(output, inputs_sha):
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    rows = []
    try:
        if runner.source_snapshot.digest(output / "batch-inputs.json") != inputs_sha:
            raise RuntimeError("Detached mapping preparation changed")
        inputs = json.loads((output / "batch-inputs.json").read_text())
        repo = Path(inputs["repository"])
        runner.source_snapshot.verify(
            output / "controller-source", manifest_sha256=inputs["snapshot_manifest_sha256"]
        )
        for group in inputs["groups"]:
            runner.source_snapshot._selected(repo, list(inputs["owned_source_sha256"]))
            if any(
                runner.source_snapshot.digest(repo / n) != sha
                for n, sha in inputs["owned_source_sha256"].items()
            ):
                raise RuntimeError("Owned source drift; no next worker launched")
            directory = output / group
            env = environment(repo)
            env["CELLS_MAPPING_EXPECTED_OWNED"] = json.dumps(inputs["owned_source_sha256"])
            with (
                (output / (group + ".stdout.log")).open("x") as out,
                (output / (group + ".stderr.log")).open("x") as err,
            ):
                p = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(repo / OWN),
                        "--output",
                        str(directory),
                        "--group",
                        group,
                    ],
                    cwd=repo,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=False,
                )
            artifact = directory / "result.json"
            row = dict(
                group=group,
                path=str(directory),
                returncode=p.returncode,
                result_sha256=runner.source_snapshot.digest(artifact)
                if artifact.is_file()
                else None,
            )
            rows.append(row)
            runner.write(output / (group + ".terminal.json"), row)
            if p.returncode:
                raise RuntimeError("Blocked group failed: " + group)
        pending = any(
            runner.source_snapshot.digest(repo / n) != sha
            for n, sha in inputs["owned_source_sha256"].items()
        )
        runner.write(
            output / "BATCH-RESULT.json",
            dict(
                status="completed_blocked_software_only",
                outcomes=rows,
                integration_pending=pending,
                owned_source_sha256=inputs["owned_source_sha256"],
                frozen_test_results_changed=False,
                local_saved_result_review_pending=True,
                native_or_scientific_credit=0,
                automatic_retry=False,
            ),
        )
        return 0
    except Exception as error:
        runner.write(
            output / "BATCH-FAILURE.json",
            dict(
                status="failed_software_or_binding",
                error=dict(type=type(error).__name__, message=str(error)),
                traceback=traceback.format_exc(),
                outcomes=rows,
                owned_source_sha256=inputs.get("owned_source_sha256")
                if "inputs" in locals()
                else None,
                native_or_scientific_credit=0,
                automatic_retry=False,
            ),
        )
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", choices=GROUPS)
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--groups", nargs="+", choices=GROUPS)
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_batch-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_batch-inputs-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.groups and not args.batch:
        parser.error("--groups is only for an explicitly selected detached batch")
    output = args.output.absolute()
    if not output.is_relative_to(runner.BASE) or os.sched_getaffinity(0) != {6}:
        parser.error("Require CPU6 and fresh /mnt output")
    if args._batch_child:
        return batch_child(output, args._batch_inputs_sha256)
    if args._child:
        return child(output, args.group)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    try:
        if args.batch:
            return launch_batch(output, args.groups)
        if args.group is None:
            parser.error("Require --group or --batch")
        return run_group(output, args.group)
    except Exception as error:
        if output.is_dir():
            runner.write(
                output / "PREPARATION-FAILURE.json",
                dict(
                    status="failed_software_preparation_or_postcheck",
                    error=dict(type=type(error).__name__, message=str(error)),
                    traceback=traceback.format_exc(),
                    automatic_retry=False,
                    scientific_credit=0,
                ),
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
