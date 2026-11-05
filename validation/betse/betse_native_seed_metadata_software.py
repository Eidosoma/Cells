"""Immutable, native-blocked controls for SEED metadata and observer costs.

Only selected metadata definitions are exercised by the tests. Complete native
modules, numerical libraries, owners and scientific bodies remain unavailable.
Snapshots and resource/runtime accounting use the existing shared utilities.
"""

import argparse
import hashlib
import importlib.abc
import json
import os
import resource
import sys
import traceback
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
FILE = "validation/betse/betse_native_seed_metadata_software.py"
TESTS = (
    "tests/unit/test_betse_native_source_compilation_cache.py",
    "tests/unit/test_betse_native_observer_dispatch_cost.py",
)
SOURCES = (
    "src/cells/processes/betse_native_phase_parameters.py",
    "src/cells/processes/betse_native_parameter_colormaps.py",
    "src/cells/processes/betse_native_tissue_handler_attachment.py",
    "src/cells/processes/betse_native_tissue_configuration.py",
    "src/cells/processes/betse_native_phase_tail.py",
    "src/cells/processes/betse_native_world_phase_construction.py",
)
FILES = (
    FILE,
    *TESTS,
    *SOURCES,
    "src/cells/processes/betse_native_parameter_world_construction.py",
    "validation/source_snapshot.py",
    "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "validation/betse/betse_normal_channel_join_runtime.py",
    "tests/__init__.py",
)
ADOPTION_TESTS = ("tests/unit/test_native_init_demo_adoption.py",)
ADOPTION_FILES = (
    FILE,
    *ADOPTION_TESTS,
    "validation/betse/native_init_demo_adoption.py",
    "validation/source_snapshot.py",
    "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "validation/betse/betse_normal_channel_join_runtime.py",
    "tests/__init__.py",
)
NATIVE_ROOT = "/mnt/workspaces/Cells/betse-v1.5.0/"
BLOCKED_IMPORTS = frozenset(("cells", "betse", "numpy", "scipy", "jax"))
_RAW_FAILURES = []


def _error_record(error):
    try:
        return dict(type=type(error).__qualname__, message=str(error))
    except BaseException as capture:
        _RAW_FAILURES.append(("error_format", error, capture))
        return dict(type=type(error).__qualname__, message_unavailable=True)


class _BlockImports(importlib.abc.MetaPathFinder):
    def __init__(self, attempts):
        self.attempts = attempts

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in BLOCKED_IMPORTS:
            self.attempts.append(dict(kind="import", name=fullname))
            raise ImportError("Metadata controls forbid production/numerical imports: " + fullname)
        return None


def _roster(suite):
    if suite == "metadata":
        return TESTS, FILES
    if suite == "adoption":
        return ADOPTION_TESTS, ADOPTION_FILES
    raise ValueError("Unknown metadata software suite")


def _child(output, suite="metadata"):
    import pytest

    tests, files = _roster(suite)
    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["suite"] != suite or inputs["selected_test_files"] != list(tests):
        raise ValueError("Frozen metadata software selection changed")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    if {name: manifest["files"][name]["sha256"] for name in files} != inputs["source_pins"]:
        raise ValueError("Frozen metadata source roster changed")
    attempts, reports, per_case = [], [], []
    get_profile, get_trace = sys.getprofile, sys.gettrace
    set_profile, set_trace = sys.setprofile, sys.settrace
    previous = (get_profile(), get_trace())
    importers = tuple(sys.meta_path)
    blocker = _BlockImports(attempts)
    primary, status, inventory = None, None, None
    cleanup = []

    def save(name, value):
        try:
            snapshot.write_json(output / name, value)
        except BaseException as error:
            cleanup.append(("write:" + str(name), error))

    def restore():
        for setter, value in ((set_trace, previous[1]), (set_profile, previous[0])):
            try:
                setter(value)
            except BaseException as error:
                cleanup.append(("restore", error))
        samples = []
        for order in ((0, 1), (1, 0)):
            state = [None, None]
            for index in order:
                try:
                    state[index] = (get_profile, get_trace)[index]()
                except BaseException as error:
                    cleanup.append(("sample", error))
            samples.append(state)
        return all(row[0] is previous[0] and row[1] is previous[1] for row in samples)

    def profile(frame, event, arg):
        if event == "call":
            module = frame.f_globals.get("__name__", "").split(".")[0]
            if module in BLOCKED_IMPORTS or frame.f_code.co_filename.startswith(NATIVE_ROOT):
                attempts.append(
                    dict(kind="entry", path=frame.f_code.co_filename, name=frame.f_code.co_qualname)
                )
                raise AssertionError("Actual production/native entry is forbidden")
        if previous[0] is not None:
            previous[0](frame, event, arg)

    class Reports:
        @pytest.hookimpl(tryfirst=True)
        def pytest_runtest_makereport(self, item, call):
            nonlocal primary
            if call.excinfo is not None and primary is None:
                primary = call.excinfo.value

        def pytest_runtest_logreport(self, report):
            row = dict(
                nodeid=report.nodeid,
                when=report.when,
                outcome=report.outcome,
                duration=report.duration,
                longrepr=str(report.longrepr) if report.failed else None,
            )
            reports.append(row)
            name = hashlib.sha256(report.nodeid.encode()).hexdigest()
            snapshot.write_json(output / "reports" / (name + "." + report.when + ".json"), row)
            if report.when == "teardown":
                check = dict(
                    nodeid=report.nodeid,
                    attempts=list(attempts),
                    profile_retained=get_profile() is profile,
                    trace_retained=get_trace() is previous[1],
                    import_blocker_retained=blocker in sys.meta_path,
                )
                per_case.append(check)
                snapshot.write_json(output / "guards" / (name + ".json"), check)
                if attempts or not all(
                    check[key]
                    for key in ("profile_retained", "trace_retained", "import_blocker_retained")
                ):
                    raise AssertionError("Metadata control changed inherited blockade")

    try:
        if any(name.split(".")[0] in BLOCKED_IMPORTS for name in sys.modules):
            raise ValueError("Production/numerical modules loaded before metadata blockade")
        sys.meta_path.insert(0, blocker)
        set_profile(profile)
        status = pytest.main(
            [
                "-q",
                "--noconftest",
                "-c",
                "/dev/null",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                "--basetemp",
                str(output / "pytest"),
                "--junitxml=" + str(output / "junit.xml"),
                *(str(ROOT / name) for name in tests),
            ],
            plugins=[Reports()],
        )
    except BaseException as error:
        if primary is None:
            primary = error
        elif error is not primary:
            cleanup.append(("pytest", error))
    finally:
        held = get_profile() is profile and get_trace() is previous[1] and blocker in sys.meta_path
        # Also retain a partial runtime on exceptional pytest exits when the
        # inherited blockade is intact. Missing authority never permits imports.
        if held:
            try:
                inventory = runtime.inventory()
                save("runtime.json", inventory)
                for name, row in inventory["loaded_files"].items():
                    path = Path(row["path"])
                    if path.is_relative_to(ROOT):
                        relative = str(path.relative_to(ROOT))
                        if (
                            relative not in manifest["files"]
                            or row["sha256"] != inputs["source_pins"][relative]
                        ):
                            raise ValueError("Actual loaded snapshot producer differs: " + name)
            except BaseException as error:
                cleanup.append(("runtime", error))
        restored = False
        try:
            restored = restore()
        except BaseException as error:
            cleanup.append(("restore_entry", error))
            for setter, value in ((set_trace, previous[1]), (set_profile, previous[0])):
                try:
                    setter(value)
                except BaseException as capture:
                    cleanup.append(("restore_entry_recovery", capture))
        try:
            if blocker in sys.meta_path:
                sys.meta_path.remove(blocker)
        except BaseException as error:
            cleanup.append(("importer_restore", error))
        restored = restored and tuple(sys.meta_path) == importers
        calls = [row for row in reports if row["when"] == "call"]
        passed = (
            primary is None
            and status == 0
            and held
            and restored
            and not cleanup
            and not attempts
            and bool(calls)
            and len(calls) == len(per_case)
            and len(reports) == 3 * len(calls)
            and all(row["outcome"] == "passed" for row in reports)
        )
        if primary is not None:
            try:
                description = "".join(traceback.format_exception(primary))
            except BaseException as error:
                cleanup.append(("traceback", error))
                description = None
            try:
                save(
                    "child-failure.json",
                    dict(primary=_error_record(primary), traceback=description),
                )
            except BaseException as error:
                cleanup.append(("failure_write_entry", error))
        try:
            save(
                "native-entry-guard.json",
                dict(
                    attempts=attempts,
                    held=held,
                    hooks_and_importers_restored=restored,
                    cleanup=[(stage, _error_record(error)) for stage, error in cleanup],
                ),
            )
        except BaseException as error:
            cleanup.append(("guard_write_entry", error))
        try:
            save(
                "result.json",
                dict(
                    status="passed" if passed and not cleanup else "failed",
                    cases=len(calls),
                    reports=len(reports),
                    pytest_status=status,
                    guard_receipts=len(per_case),
                    complete_runtime=inventory is not None,
                    final_clean_child_exit_required=True,
                    source_native_owner_or_scientific_credit=False,
                ),
            )
        except BaseException as error:
            cleanup.append(("result_write_entry", error))
        # No callbacks or recorders follow these final independent restores and
        # dual-order samples. The parent also requires a clean process outcome.
        try:
            restored = restore()
        except BaseException as error:
            cleanup.append(("final_restore_entry", error))
            restored = False
            for setter, value in ((set_trace, previous[1]), (set_profile, previous[0])):
                try:
                    setter(value)
                except BaseException as capture:
                    cleanup.append(("final_restore_entry_recovery", capture))
        final_states = []
        for order in ((0, 1), (1, 0)):
            state = [None, None]
            for index in order:
                try:
                    state[index] = (get_profile, get_trace)[index]()
                except BaseException as error:
                    cleanup.append(("final_identity", error))
            final_states.append(state)
        passed = (
            all(row[0] is previous[0] and row[1] is previous[1] for row in final_states)
            and restored
            and tuple(sys.meta_path) == importers
            and passed
            and not cleanup
        )
        if primary is not None or cleanup or not passed:
            _RAW_FAILURES.append((primary, tuple(cleanup), tuple(reports), inventory))
    if primary is not None:
        raise primary
    return 0 if passed else 1


def run(output, cpu, suite="metadata"):
    tests, files = _roster(suite)
    output.mkdir(parents=True, exist_ok=False)
    for name in ("reports", "guards", "process"):
        (output / name).mkdir()
    manifest = snapshot.freeze(ROOT, output / "source", {name: name for name in files})
    manifest_sha256 = snapshot.digest(output / "source/SNAPSHOT.json")
    snapshot.write_json(
        output / "inputs.json",
        dict(
            snapshot_sha256=manifest_sha256,
            git_revision=manifest["git_revision"],
            source_pins={name: row["sha256"] for name, row in manifest["files"].items()},
            suite=suite,
            selected_test_files=tests,
            cpu=cpu,
            threads=1,
            worker_wall_seconds=480,
            worker_memory_bytes=2**30,
            reserve_bytes=8 * 2**30,
            parent_soft_as_bytes=512 * 2**20,
            parent_hard_as_bytes=2**30,
            producer_files_are_metadata_inputs_not_loaded_owner_authority=True,
            actual_source_or_scientific_release=False,
        ),
    )
    env = dict(
        os.environ,
        PYTHONPATH=str(output / "source"),
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
    )
    primary, outcome, secondary = None, None, []
    try:
        outcome = guard.run_bounded(
            [
                sys.executable,
                "-B",
                str(output / "source" / FILE),
                "--child",
                str(output),
                "--cpu",
                str(cpu),
                "--suite",
                suite,
            ],
            directory=output / "process",
            cwd=output / "source",
            env=env,
            timeout=480,
            max_rss_bytes=2**30,
            min_available_bytes=8 * 2**30,
        )
    except BaseException as error:
        primary = error
    for stage, operation in (
        (
            "immutable_postcheck",
            lambda: snapshot.verify(output / "source", manifest_sha256=manifest_sha256),
        ),
        (
            "checkout_integration",
            lambda: snapshot.write_json(
                output / "checkout-integration.json",
                dict(
                    changed_selected_files=[
                        name
                        for name, row in manifest["files"].items()
                        if snapshot.digest(ROOT / name) != row["sha256"]
                    ],
                    execution_source_immutable=True,
                    does_not_relabel_frozen_execution=True,
                ),
            ),
        ),
    ):
        try:
            operation()
        except BaseException as error:
            secondary.append((stage, error))
    if primary is not None or secondary:
        _RAW_FAILURES.append((primary, tuple(secondary), outcome))
        try:
            snapshot.write_json(
                output / "controller-failure.json",
                dict(
                    primary=None if primary is None else _error_record(primary),
                    secondary=[(stage, _error_record(error)) for stage, error in secondary],
                ),
            )
        except BaseException as error:
            _RAW_FAILURES.append(("controller_failure_write", error))
        if primary is not None:
            raise primary
        raise secondary[0][1]
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--run", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--cpu", type=int, default=4)
    parser.add_argument("--suite", choices=("metadata", "adoption"), default="metadata")
    args = parser.parse_args()
    os.sched_setaffinity(0, {args.cpu})
    resource.setrlimit(resource.RLIMIT_AS, (2**30 if args.child else 512 * 2**20, 2**30))
    if args.child:
        return _child(args.child.resolve(), args.suite)
    print(json.dumps(run(args.run.resolve(), args.cpu, args.suite)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
