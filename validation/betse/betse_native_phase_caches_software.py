"""Freeze cache-constructor software from Git; native entry stays forbidden."""

import argparse
import hashlib
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
from types import FunctionType

from validation.betse import betse_native_phase_assembly_software as phase

inherited = phase.inherited
snapshot = inherited.snapshot
ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/betse_native_phase_caches_software.py"
TEST = "tests/unit/test_betse_native_phase_caches.py"
SOURCE = "src/cells/processes/betse_native_phase_caches.py"
LITERAL = "src/cells/processes/betse_native_phase_cache_source.py"
HOOK = "src/cells/processes/betse_native_phase_assembly.py"
MODULE = "validation.betse.betse_native_phase_caches_software"
OWNED = (SOURCE, LITERAL, TEST, FILE, HOOK)
GROUPS = {
    "g00": (
        "test_preparation_literal_bodies_weak_helper_and_boundary",
        *(
            "test_preparation_constructor_metadata_preserves_original_class_cell[" + name + "]"
            for name in (
                "SimPhaseCaches-betse/science/math/cache/cacheabc.py-freevars0",
                "SimPhaseCacheABC-betse/science/math/cache/cacheabc.py-freevars1",
                "SimPhaseCacheVectorCells-betse/science/math/cache/cachevec.py-freevars2",
            )
        ),
        *(
            "test_preparation_release_precedes_all_constructor_work[" + name + "]"
            for name in ("False-1", "True-0", "1-1")
        ),
        "test_preparation_requires_actual_issued_request",
        "test_preparation_wrong_mode_cannot_gain_cache_authority",
        "test_preparation_missing_hook_keeps_real_prefix_unconsumed",
    ),
    "g01": (
        "test_same_live_phase_subcache_order_and_real_weak_links",
        "test_later_owner_cannot_reopen_retired_phase_prefix",
        "test_complete_phase_remains_unavailable",
    ),
    **{
        name: tuple(
            "test_retained_issuance_links_cannot_disappear[" + label + "]" for label in labels
        )
        for name, labels in (
            (
                "g02",
                (
                    "phase_issuance",
                    "phase_retirement",
                    "phase_retirement_marker",
                    "parameter_claim",
                ),
            ),
            ("g03", ("cache_object", "parameter_issuance", "callback_issuance")),
            ("g04", ("prefix_request_claim", "prefix_parameter_claim", "prefix_raw_object")),
        )
    },
    "g05": tuple(
        "test_constructor_failure_keeps_actual_parent_and_partial_objects[" + name + "]"
        for name in ("top", "abc", "vector", "proxy")
    ),
    "g06": (
        *(
            "test_inherited_callable_or_private_helper_drift_with_unchanged_values[" + name + "]"
            for name in ("caller_method", "cache_method", "weak_helper")
        ),
        "test_retirement_link_drift_stops_before_the_next_factory",
        "test_cache_assignment_cannot_precede_constructor_completion",
    ),
    "g07": (
        *(
            "test_raw_lazy_and_constructor_entry_stays_blocked[" + name + "]"
            for name in ("upscaled", "layer", "field", "constructor")
        ),
        *(
            "test_equal_looking_reference_retarget_refuses[" + name + "]"
            for name in ("_phase", "layer")
        ),
    ),
    "g08": (
        "test_entry_capture_failure_prevents_any_delegate",
        "test_reentrant_enter_cannot_be_swallowed_into_a_constructor",
        "test_early_parent_refusal_has_no_fabricated_baseline_or_trial",
        "test_return_capture_stops_before_the_next_factory",
        "test_unwind_capture_preserves_primary_and_failed_raw_entry_guard",
        "test_failed_sealing_preserves_native_primary_and_cause",
    ),
}


def prepare(output, select):
    from cells.processes import betse_native_phase_caches as stage

    if Path(__file__).resolve() != ROOT / FILE or (output / "source").exists():
        raise ValueError("New cache software snapshots must come from the checkout")
    plan = stage.source_plan()
    files = runpy.run_path(str(ROOT / inherited.CLOSURE))["closure"](ROOT, list(OWNED))
    for name in (inherited.CLOSURE, "tests/__init__.py", "pyproject.toml"):
        files[name] = snapshot.digest(ROOT / name)
    frozen = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    snapshot.write_json(
        output / "inputs.json",
        dict(
            source_plan=plan,
            source_sha256={name: frozen["files"][name]["sha256"] for name in (FILE, TEST, SOURCE)},
            owned_files={name: frozen["files"][name]["sha256"] for name in OWNED},
            snapshot_sha256=snapshot.digest(output / "source/SNAPSHOT.json"),
            git_revision=frozen["git_revision"],
            selection=select,
            cpu=6,
            threads=1,
            metadata_rss_bytes=512 * 2**20,
            metadata_address_space_bytes=2**30,
            software_bytes=2**30,
            wall_seconds=480,
            reserve_bytes=8 * 2**30,
            phase_retirement_hook_available=callable(
                getattr(stage.previous, "_claim_for_caches", None)
            ),
            actual_source_release=False,
        ),
    )
    snapshot.assert_checkout_unchanged(output / "source")


def child(output, select):
    import pytest

    from cells.processes import betse_native_phase_caches as stage

    original, trace = sys.getprofile(), sys.gettrace()
    attempts = []
    codes = {
        stage._acquire.__code__,
        stage._import_native.__code__,
        *(method.__code__ for method in stage._METHODS.values()),
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native phase/cache/source work forbidden")
        if original is not None:
            original(frame, event, arg)

    class Reports:
        def pytest_collection_modifyitems(self, config, items):
            if select not in GROUPS:
                return
            declared = [name for names in GROUPS.values() for name in names]
            if len(declared) != len(set(declared)) or set(declared) != {
                item.name for item in items
            }:
                raise ValueError("Exact disjoint batch roster does not cover collection")
            expected = GROUPS[select]
            selected = [item for item in items if item.name in expected]
            if {item.name for item in selected} != set(expected):
                raise ValueError("Explicit cache software roster differs from collection")
            removed = [item for item in items if item not in selected]
            items[:] = selected
            config.hook.pytest_deselected(items=removed)

        def pytest_runtest_logreport(self, report):
            directory = output / "reports"
            directory.mkdir(exist_ok=True)
            name = hashlib.sha256(report.nodeid.encode()).hexdigest() + "." + report.when + ".json"
            snapshot.write_json(
                directory / name,
                dict(
                    nodeid=report.nodeid,
                    when=report.when,
                    outcome=report.outcome,
                    duration=report.duration,
                    longrepr=str(report.longrepr),
                ),
            )

        def pytest_exception_interact(self, node, call, report):
            from validation.betse.betse_native_single_cell_core_synthetic import save

            error = call.excinfo.value
            if not isinstance(error, stage.CacheConstructionRejected):
                return
            directory = output / "unexpected-failures"
            directory.mkdir(exist_ok=True)
            name = hashlib.sha256(node.nodeid.encode()).hexdigest()
            raw = error.partial
            if type(raw) is not dict:
                raw = vars(raw) if hasattr(raw, "__dict__") else {}
            try:
                save(
                    directory,
                    name,
                    dict(
                        stage=error.stage,
                        request=error.request,
                        trial=error.trial,
                        source_error=error.source_error,
                        capture_error=error.capture_error,
                        cause=error.__cause__,
                        parent_trial=raw.get("parent_trial"),
                        phase=raw.get("phase"),
                        objects=raw.get("objects"),
                        proxies=raw.get("proxies", raw.get("proxy_returns")),
                        attempts=raw.get("attempts", raw.get("factory_attempts")),
                        returns=raw.get("returns", raw.get("factory_returns")),
                        last_completed=raw.get("last_completed"),
                    ),
                )
            except Exception as capture:
                snapshot.write_json(
                    directory / (name + ".capture-error.json"),
                    dict(
                        type=type(capture).__name__,
                        traceback=traceback.format_exc(),
                        primary_test_failure_preserved=True,
                    ),
                )

    status = 2
    try:
        sys.setprofile(profile)
        args = [
            "-q",
            "-c",
            "/dev/null",
            "--noconftest",
            "-p",
            "no:cacheprovider",
            str(ROOT / TEST),
            "--basetemp",
            str(output / "pytest"),
            "--junitxml",
            str(output / "tests.xml"),
        ]
        if select and select not in GROUPS:
            args += ["-k", select]
        status = pytest.main(args, plugins=[Reports()])
    finally:
        restored = sys.getprofile() is profile and sys.gettrace() is trace
        sys.setprofile(original)
        sys.settrace(trace)
        snapshot.write_json(
            output / "native-entry-guard.json",
            dict(
                attempted=attempts,
                prior_profile_trace_restored=restored,
                actual_source_or_scientific_credit=0,
            ),
        )
        snapshot.write_json(output / "runtime.json", inherited.runtime.inventory())
    return int(status) if not attempts and restored else 1


def software(output, select):
    scope = dict(vars(inherited), ROOT=ROOT, FILE=FILE, TEST=TEST, SOURCE=SOURCE, MODULE=MODULE)
    return FunctionType(inherited.software.__code__, scope)(output, select)


def _environment(root):
    env = {
        key: value for key, value in os.environ.items() if not key.startswith(("CELLS_", "PYTEST_"))
    }
    env.update(
        PYTHONPATH=os.pathsep.join(
            [
                str(root),
                str(root / "src"),
                *(
                    part
                    for part in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                    if part and not Path(part).resolve().is_relative_to(ROOT)
                ),
            ]
        ),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    return env


def _write_progress(path, value):
    """Replace only mutable progress, leaving every terminal receipt exclusive."""
    if path.is_symlink() or path.exists() and not path.is_file():
        raise ValueError("Progress target must be an ordinary file")
    temporary = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    # A failed write leaves its temporary evidence intact; it is not retried.
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remaining_groups(groups, completed):
    if any(name not in groups for name in completed):
        raise ValueError("Unknown completed group")
    return {name: ids for name, ids in groups.items() if name not in completed}


def _resume_plan(prior):
    """Resume reviewed never-launched groups; do not retry an executed group."""
    prior = prior.resolve(strict=True)
    files = {
        name: prior / name
        for name in ("batch-inputs.json", "BATCH-FAILURE.json", "local-review-01.json")
    }
    original, failure, review = (json.loads(files[name].read_text()) for name in files)
    if (
        review["status"] != "reviewed_terminal_batch_failure"
        or failure["error_type"] != "FileExistsError"
        or any(row["returncode"] != 0 for row in failure["outcomes"])
    ):
        raise ValueError(
            "Reviewed controller-only failure required for remaining-only continuation"
        )
    completed = {row["group"] for row in failure["outcomes"]}
    remaining = _remaining_groups(original["groups"], completed)
    if not remaining or remaining != review["unrun_groups"]:
        raise ValueError("Reviewed never-launched roster changed")
    for name, ids in remaining.items():
        if name not in GROUPS or list(GROUPS[name]) != ids or (prior / name).exists():
            raise ValueError("Original unrun controls changed or already launched")
    for name, expected in original["owned_source_sha256"].items():
        if name != FILE and snapshot.digest(ROOT / name) != expected:
            raise ValueError("Non-controller source drift; remaining-only plan is not valid")
    return remaining, dict(
        path=str(prior),
        receipts={str(path): snapshot.digest(path) for path in files.values()},
        prior_owned_source_sha256=original["owned_source_sha256"],
        excluded_completed_groups=sorted(completed),
        excluded_prior_passes=review["distinct_passed_software_controls"],
        selected_unrun_controls=sum(map(len, remaining.values())),
    )


def metadata_controls(output):
    """Small stdlib-only regression; no source fixture/native entry occurs."""
    output.mkdir(parents=True, exist_ok=False)
    progress = output / "completed-groups.json"
    _write_progress(progress, [dict(group="g00", passed=10)])
    assert json.loads(progress.read_text()) == [dict(group="g00", passed=10)]
    snapshot.write_json(output / "g00.terminal.json", dict(group="g00", status="passed"))
    first = snapshot.digest(output / "g00.terminal.json")
    _write_progress(progress, [dict(group="g00", passed=10), dict(group="g01", passed=3)])
    assert len(json.loads(progress.read_text())) == 2
    snapshot.write_json(output / "g01.terminal.json", dict(group="g01", status="passed"))
    assert snapshot.digest(output / "g00.terminal.json") == first
    try:
        snapshot.write_json(output / "g00.terminal.json", dict(status="overwrite"))
    except FileExistsError:
        pass
    else:
        raise AssertionError("Terminal receipts must remain exclusive")
    assert snapshot.digest(output / "g00.terminal.json") == first
    remaining = _remaining_groups(GROUPS, {"g00", "g01"})
    assert sum(map(len, remaining.values())) == 31
    assert not set(remaining) & {"g00", "g01"}
    snapshot.write_json(
        output / "result.json",
        dict(
            status="passed_metadata_only",
            progress_updates=2,
            distinct_terminal_receipts=2,
            repeated_terminal_write_refused=True,
            remaining_original_controls=31,
            prior_completed_controls_excluded=13,
            native_or_scientific_entries=0,
        ),
    )
    return 0


def launch_batch(output, remaining_from=None):
    """Detach a frozen controller; each software group retains its own image."""
    if (
        Path(__file__).resolve() != ROOT / FILE
        or output.exists()
        or not output.absolute().is_relative_to(inherited.BASE)
        or any(path.is_symlink() for path in (output, *output.parents))
        or os.sched_getaffinity(0) != {6}
    ):
        raise ValueError("Fresh canonical CPU6 cache batch output required")
    groups, continuation = GROUPS, None
    if remaining_from is not None:
        groups, continuation = _resume_plan(remaining_from)
    output.mkdir(parents=True)
    paths = runpy.run_path(str(ROOT / inherited.CLOSURE))["closure"](ROOT, list(OWNED))
    for name in (inherited.CLOSURE, "tests/__init__.py", "pyproject.toml"):
        paths[name] = snapshot.digest(ROOT / name)
    frozen = output / "controller-source"
    manifest = snapshot.freeze(ROOT, frozen, {name: name for name in paths})
    snapshot.write_json(
        output / "batch-inputs.json",
        dict(
            repository=str(ROOT),
            git_revision=manifest["git_revision"],
            controller_snapshot_sha256=snapshot.digest(frozen / "SNAPSHOT.json"),
            owned_source_sha256={name: manifest["files"][name]["sha256"] for name in OWNED},
            groups=groups,
            continuation=continuation,
            cpu=6,
            threads=1,
            per_group=dict(software_rss_bytes=2**30, wall_seconds=480, reserve_bytes=8 * 2**30),
            metadata=dict(rss_bytes=512 * 2**20, wall_seconds=120),
            actual_source_release=False,
            automatic_retry=False,
        ),
    )
    snapshot.assert_checkout_unchanged(frozen)
    inputs_sha = snapshot.digest(output / "batch-inputs.json")
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
                MODULE,
                "--batch-child",
                str(output),
                "--batch-inputs-sha256",
                inputs_sha,
            ],
            cwd=frozen,
            env=_environment(frozen),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
    snapshot.write_json(
        output / "LAUNCH.json",
        dict(
            status="detached_native_blocked_software_only",
            pid=process.pid,
            process_group=process.pid,
            utc=datetime.now(timezone.utc).isoformat(),
            controller_snapshot_sha256=snapshot.digest(frozen / "SNAPSHOT.json"),
            batch_inputs_sha256=inputs_sha,
            result_path=str(output / "BATCH-RESULT.json"),
            failure_path=str(output / "BATCH-FAILURE.json"),
            cpu=6,
            threads=1,
            automatic_retry=False,
        ),
    )
    print(json.dumps(dict(status="detached_native_blocked_software_only", output=str(output))))
    return 0


def batch_child(output, inputs_sha):
    outcomes, step, expected = [], "inputs", None
    try:
        if (
            os.sched_getaffinity(0) != {6}
            or snapshot.digest(output / "batch-inputs.json") != inputs_sha
        ):
            raise ValueError("Batch CPU or sealed inputs changed")
        inputs = json.loads((output / "batch-inputs.json").read_text())
        if not inputs["groups"] or any(
            name not in GROUPS or ids != list(GROUPS[name])
            for name, ids in inputs["groups"].items()
        ):
            raise ValueError("Bounded exact software selectors changed")
        continuation = inputs.get("continuation")
        if continuation is not None:
            if any(
                snapshot.digest(Path(path)) != sha for path, sha in continuation["receipts"].items()
            ):
                raise ValueError("Prior failed batch/review binding changed")
            if set(inputs["groups"]) & set(continuation["excluded_completed_groups"]):
                raise ValueError(
                    "Completed controls must not be rerun by remaining-only continuation"
                )
        canonical, expected = Path(inputs["repository"]), inputs["owned_source_sha256"]
        snapshot.verify(
            output / "controller-source", manifest_sha256=inputs["controller_snapshot_sha256"]
        )
        all_names = []
        for group, names in inputs["groups"].items():
            step = group
            snapshot._selected(canonical, sorted(expected))
            if any(snapshot.digest(canonical / name) != sha for name, sha in expected.items()):
                raise ValueError("Selected owned source drift; no next worker launched")
            directory = output / group
            with (
                (output / (group + ".stdout.log")).open("x") as out,
                (output / (group + ".stderr.log")).open("x") as err,
            ):
                process = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(canonical / FILE),
                        "--software",
                        str(directory),
                        "--select",
                        group,
                    ],
                    cwd=canonical,
                    env=_environment(canonical),
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    check=False,
                )
            artifacts = [
                directory / name
                for name in (
                    "result.json",
                    "FAILURE.json",
                    "metadata/failure.json",
                    "process/failure.json",
                )
                if (directory / name).is_file()
            ]
            row = dict(
                group=group,
                output=str(directory),
                returncode=process.returncode,
                terminal_artifacts={str(path): snapshot.digest(path) for path in artifacts},
            )
            outcomes.append(row)
            snapshot.write_json(output / (group + ".terminal.json"), row)
            if process.returncode or not artifacts:
                raise ValueError("Software group failed; original result retained and no retry")
            result = json.loads((directory / "result.json").read_text())
            frozen = snapshot.verify(
                directory / "source", manifest_sha256=result["snapshot_sha256"]
            )
            if any(frozen["files"][name]["sha256"] != sha for name, sha in expected.items()):
                raise ValueError("Group selected another owned source version")
            producers = json.loads((directory / "producer-bindings.json").read_text())
            if any(producers.get(name) != sha for name, sha in expected.items()):
                raise ValueError("Selected loaded producer binding missing/different")
            cases = list(ET.parse(directory / "tests.xml").iter("testcase"))
            case_names = [case.get("name") for case in cases]
            if (
                result["status"] != "passed"
                or not result["complete_guards"]
                or result["actual_native_entries"] != 0
                or set(case_names) != set(names)
                or len(case_names) != len(names)
                or any(
                    case.find(tag) is not None
                    for case in cases
                    for tag in ("failure", "error", "skipped")
                )
            ):
                raise ValueError("Saved guarded outcome/explicit case roster mismatch")
            row.update(
                passed=len(cases),
                case_names=case_names,
                snapshot_sha256=result["snapshot_sha256"],
                integration_pending=result["integration_pending"],
            )
            all_names.extend(case_names)
            _write_progress(output / "completed-groups.json", outcomes)
        if len(all_names) != len(set(all_names)):
            raise ValueError("Selectors overlap; no additive distinct-control credit")
        drift = {
            name: snapshot.digest(canonical / name)
            for name, sha in expected.items()
            if snapshot.digest(canonical / name) != sha
        }
        snapshot.write_json(
            output / "BATCH-RESULT.json",
            dict(
                status="completed_native_blocked_software_only",
                outcomes=outcomes,
                owned_source_sha256=expected,
                distinct_passed_controls=len(all_names),
                continuation=continuation,
                integration_pending=bool(drift)
                or any(row["integration_pending"] for row in outcomes),
                current_selected_drift=drift,
                biological_cases=0,
                native_or_scientific_credit=0,
                actual_source_result_review_required=True,
                automatic_retry=False,
            ),
        )
        return 0
    except BaseException as error:
        snapshot.write_json(
            output / "BATCH-FAILURE.json",
            dict(
                status="failed_software_or_binding",
                stage=step,
                outcomes=outcomes,
                error_type=type(error).__name__,
                traceback=traceback.format_exc(),
                owned_source_sha256=expected,
                native_or_scientific_credit=0,
                automatic_retry=False,
            ),
        )
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "software",
        "prepare",
        "child",
        "launch-batch",
        "batch-child",
        "metadata-controls",
    ):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="")
    parser.add_argument("--batch-inputs-sha256", default="")
    parser.add_argument("--remaining-from", type=Path)
    args = parser.parse_args()
    if args.child:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    if args.prepare:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        prepare(args.prepare, args.select)
        return 0
    if args.batch_child:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return batch_child(args.batch_child, args.batch_inputs_sha256)
    if args.metadata_controls:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        return metadata_controls(args.metadata_controls)
    if args.launch_batch:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        try:
            return launch_batch(args.launch_batch, args.remaining_from)
        except BaseException as error:
            if args.launch_batch.is_dir():
                snapshot.write_json(
                    args.launch_batch / "LAUNCH-FAILURE.json",
                    dict(
                        status="launch_preparation_or_receipt_failed",
                        type=type(error).__name__,
                        traceback=traceback.format_exc(),
                        native_or_scientific_credit=0,
                        automatic_retry=False,
                    ),
                )
            raise
    if args.software:
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        try:
            return software(args.software, args.select)
        except Exception as error:
            if args.software.is_dir():
                snapshot.write_json(
                    args.software / "FAILURE.json",
                    dict(
                        status="preparation_or_verification_failed",
                        type=type(error).__name__,
                        message=str(error),
                        traceback=traceback.format_exc(),
                        scientific_credit=0,
                    ),
                )
            raise
    parser.error("Choose software, prepare or child")


if __name__ == "__main__":
    raise SystemExit(main())
