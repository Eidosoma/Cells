"""Prepare stdlib metric controls; run only after CPU6 is available.

Default invocation prepares immutable checkout bytes without executing tests.
--run-software prepares a fresh image and runs the synthetic controls under the
existing resource guard. Neither mode runs native source or an operator solve.
"""

import argparse
import ast
import hashlib
import importlib.abc
import importlib.util
import json
import os
import resource
import sys
import time
import traceback
import unittest
from pathlib import Path

from validation import source_snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
OWN = "validation/betse/betse_native_grid_metric_audit_software.py"
HELPER = "src/cells/processes/betse_native_grid_metric_audit.py"
TEST = "tests/unit/test_betse_native_grid_metric_audit.py"
FILES = (
    OWN,
    HELPER,
    TEST,
    "src/cells/__init__.py",
    "src/cells/processes/__init__.py",
    "validation/source_snapshot.py",
    "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "validation/betse/betse_normal_channel_join_runtime.py",
)


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class _NoNumericalImports(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []

    def find_spec(self, fullname, path=None, target=None):
        if (
            fullname.split(".")[0] in {"numpy", "scipy", "jax", "betse"}
            or fullname.startswith("cells.processes.")
            and fullname != "cells.processes.betse_native_grid_metric_audit"
        ):
            self.attempted.append(fullname)
            raise ImportError("Metric controls require stdlib only: " + fullname)
        return None


class _SavedResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.started = time.monotonic()
        self.case_sequence = 0
        self.case_path = (
            Path(os.environ["CELLS_GRID_METRIC_EVIDENCE"])
            / hashlib.sha256(test.id().encode()).hexdigest()[:20]
        )
        self.case_path.mkdir(parents=True, exist_ok=True)
        write(self.case_path / "case.json", dict(test_id=test.id(), synthetic_only=True))

    def _save(self, test, status, error=None):
        name = "result.json" if self.case_sequence == 0 else f"result-{self.case_sequence:02}.json"
        self.case_sequence += 1
        write(
            self.case_path / name,
            dict(
                test_id=test.id(),
                status=status,
                elapsed_seconds=time.monotonic() - self.started,
                traceback=None if error is None else self._exc_info_to_string(error, test),
                source_or_scientific_credit=0,
            ),
        )

    def addSuccess(self, test):
        super().addSuccess(test)
        self._save(test, "passed")

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self._save(test, "failed", error)

    def addError(self, test, error):
        super().addError(test, error)
        self._save(test, "error", error)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._save(test, "skipped: " + reason)

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            name = "subtest-" + hashlib.sha256(subtest.id().encode()).hexdigest()[:20] + ".json"
            write(
                self.case_path / name,
                dict(
                    test_id=test.id(),
                    subtest_id=subtest.id(),
                    status="failed",
                    traceback=self._exc_info_to_string(error, test),
                    source_or_scientific_credit=0,
                ),
            )

    def stopTest(self, test):
        if not (self.case_path / "result.json").exists():
            self._save(test, "failed_subtests_or_interrupted")
        super().stopTest(test)


def child(output, native_root):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    blocker = _NoNumericalImports()
    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
    before = tuple(sys.meta_path)
    completed = False
    try:
        if any(name.split(".")[0] in {"numpy", "scipy", "jax", "betse"} for name in sys.modules):
            raise RuntimeError("Numerical/native package loaded before stdlib controls")
        sys.meta_path.insert(0, blocker)
        spec = importlib.util.spec_from_file_location("cells_grid_metric_tests", ROOT / TEST)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.GridMetricAuditTests)
        outcome = unittest.TextTestRunner(verbosity=2, resultclass=_SavedResult).run(suite)
        data = dict(
            tests_run=outcome.testsRun,
            failures=len(outcome.failures),
            errors=len(outcome.errors),
            skipped=len(outcome.skipped),
            success=outcome.wasSuccessful(),
            synthetic_only=True,
            source_native_reference_or_scientific_credit=0,
        )
        write(output / "software-outcome.json", data)
        write(output / "runtime-producers.json", runtime.inventory())
        completed = True
        return 0 if outcome.wasSuccessful() and not outcome.skipped and not blocker.attempted else 1
    except BaseException as error:
        write(
            output / "child-failure.json",
            dict(
                error=dict(type=type(error).__name__, message=str(error)),
                traceback=traceback.format_exc(),
                source_or_scientific_credit=0,
            ),
        )
        raise
    finally:
        guard_present = blocker in sys.meta_path
        if guard_present:
            sys.meta_path.remove(blocker)
        restored = tuple(sys.meta_path) == before
        observers_unchanged = (
            sys.getprofile() is previous_profile and sys.gettrace() is previous_trace
        )
        sys.setprofile(previous_profile)
        sys.settrace(previous_trace)
        write(
            output / "native-entry-guard.json",
            dict(
                attempted=blocker.attempted,
                completed_final_certification=completed,
                guard_present_at_finish=guard_present,
                import_chain_restored=restored,
                previous_trace_and_profile_restored=observers_unchanged,
                native_source_import_or_operator_execution=False,
                original_native_text_root=str(native_root),
                source_or_scientific_credit=0,
            ),
        )


def prepare(output, native_root, run):
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "tested-source"
    snap = source_snapshot.freeze(ROOT, frozen, {name: name for name in FILES})
    manifest = source_snapshot.digest(frozen / "SNAPSHOT.json")
    helper_tree = ast.parse((frozen / HELPER).read_text())
    pins = ast.literal_eval(
        next(
            n.value
            for n in helper_tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "SOURCE_PINS" for t in n.targets)
        )
    )
    native_pins = {str(source_snapshot.regular_file(native_root, name)): sha for name, sha in pins}
    if any(source_snapshot.digest(Path(name)) != sha for name, sha in native_pins.items()):
        raise ValueError("Pinned native metadata source changed")
    test_tree = ast.parse((frozen / TEST).read_text())
    cls = next(
        n
        for n in test_tree.body
        if isinstance(n, ast.ClassDef) and n.name == "GridMetricAuditTests"
    )
    expected = sorted(
        n.name for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    )
    write(
        output / "inputs.json",
        dict(
            status="prepared_for_blocked_software"
            if run
            else "prepared_held_no_software_controls_run",
            git_revision=snap["git_revision"],
            snapshot_manifest_sha256=manifest,
            selected_source_sha256={name: row["sha256"] for name, row in snap["files"].items()},
            native_metadata_pins=native_pins,
            expected_test_methods=expected,
            cpu=6,
            threads=1,
            wall_seconds=480,
            memory_bytes=2**30,
            reserve_bytes=8 * 2**30,
            native_source_or_operator_release=False,
        ),
    )
    source_snapshot.assert_checkout_unchanged(frozen)
    if not run:
        print(json.dumps(dict(status="prepared_held_no_software_controls_run", output=str(output))))
        return 0
    (output / "process").mkdir()
    (output / "tmp").mkdir()
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join((str(frozen), str(frozen / "src"))),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        JAX_PLATFORMS="cpu",
        CELLS_GRID_METRIC_EVIDENCE=str(output / "evidence"),
        CELLS_GRID_METRIC_NATIVE_ROOT=str(native_root),
        TMPDIR=str(output / "tmp"),
    )
    try:
        result = guard.run_bounded(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_native_grid_metric_audit_software",
                "--output",
                str(output),
                "--native-root",
                str(native_root),
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
            else dict(status="failed_without_process_terminal", traceback=traceback.format_exc())
        )
    missing = [
        name
        for name in ("software-outcome.json", "runtime-producers.json", "native-entry-guard.json")
        if not (output / name).is_file()
    ]
    if missing:
        write(
            output / "result.json",
            dict(
                result,
                status="failed_incomplete",
                missing=missing,
                snapshot_manifest_sha256=manifest,
                scientific_credit=0,
            ),
        )
        return 1
    source_snapshot.verify(frozen, manifest_sha256=manifest)
    outcome = json.loads((output / "software-outcome.json").read_text())
    entry_guard = json.loads((output / "native-entry-guard.json").read_text())
    if (
        outcome["tests_run"] != len(expected)
        or entry_guard["attempted"]
        or not entry_guard["completed_final_certification"]
        or not entry_guard["guard_present_at_finish"]
        or not entry_guard["import_chain_restored"]
        or not entry_guard["previous_trace_and_profile_restored"]
    ):
        raise RuntimeError("Incomplete stdlib control/guard closure")
    inventory = json.loads((output / "runtime-producers.json").read_text())
    loaded = {}
    for module, row in inventory["loaded_files"].items():
        path = Path(row["path"])
        if path.is_relative_to(frozen):
            name = str(path.relative_to(frozen))
            if name not in snap["files"] or row.get("sha256") != snap["files"][name]["sha256"]:
                raise RuntimeError("Unbound frozen runtime producer: " + module)
            loaded[module] = row
        elif path.is_relative_to(ROOT):
            raise RuntimeError("Mutable checkout producer loaded: " + module)
    for name in (HELPER, TEST, OWN):
        if not any(Path(row["path"]) == frozen / name for row in loaded.values()):
            raise RuntimeError("Expected actual runtime producer missing: " + name)
    if any(source_snapshot.digest(Path(name)) != sha for name, sha in native_pins.items()):
        raise RuntimeError("Native metadata source changed during controls")
    repository = Path(snap["repository"])
    changed = []
    integration_error = None
    current_revision = None
    try:
        source_snapshot._selected(repository, list(snap["files"]))
        changed = [
            name
            for name, row in snap["files"].items()
            if source_snapshot.digest(repository / row["checkout_path"]) != row["sha256"]
        ]
        current_revision = source_snapshot.git_state(repository, list(snap["files"]))["revision"]
    except Exception as error:
        integration_error = dict(type=type(error).__name__, message=str(error))
    result.update(
        snapshot_manifest_sha256=manifest,
        software_outcome=outcome,
        actual_frozen_runtime_producers=loaded,
        output_pins={
            name: source_snapshot.digest(output / name)
            for name in (
                "software-outcome.json",
                "runtime-producers.json",
                "native-entry-guard.json",
            )
        },
        integration=dict(
            current_revision=current_revision,
            frozen_revision=snap["git_revision"],
            selected_source_drift=changed,
            policy_error=integration_error,
            pending=bool(changed or integration_error or current_revision != snap["git_revision"]),
            frozen_result_changed=False,
        ),
        physical_or_source_admission=False,
        scientific_credit=0,
    )
    write(output / "result.json", result)
    return (
        0
        if result["status"] == "completed" and outcome["success"] and not outcome["skipped"]
        else 1
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=BASE / "betse-v1.5.0")
    parser.add_argument("--run-software", action="store_true")
    parser.add_argument("--_child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    output = args.output.absolute()
    if (
        not output.is_relative_to(BASE)
        or ".." in output.parts
        or any(p.is_symlink() for p in (output, *output.parents))
        or os.sched_getaffinity(0) != {6}
    ):
        parser.error("Use CPU6 and a fresh real /mnt/workspaces/Cells output")
    if args._child:
        return child(output, args.native_root.absolute())
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    try:
        return prepare(output, args.native_root.absolute(), args.run_software)
    except Exception as error:
        if output.is_dir():
            write(
                output / "PREPARATION-FAILURE.json",
                dict(
                    error=dict(type=type(error).__name__, message=str(error)),
                    traceback=traceback.format_exc(),
                    automatic_retry=False,
                    scientific_credit=0,
                ),
            )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
