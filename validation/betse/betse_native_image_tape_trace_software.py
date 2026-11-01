"""Immutable stdlib controls for the selected image observer AST only.

No image, caller, native source, numerical library or operator is imported or
executed. The old observer is a pinned comparison input, never live authority.
"""

import argparse
import ast
import importlib.abc
import importlib.util
import json
import os
import resource
import sys
import traceback
import unittest
from pathlib import Path

from validation import source_snapshot
from validation.betse import betse_mesh_lifecycle_preparation_guard as guard
from validation.betse import betse_native_grid_metric_audit_software as saved
from validation.betse import betse_normal_channel_join_runtime as runtime

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("/mnt/workspaces/Cells")
OWN = "validation/betse/betse_native_image_tape_trace_software.py"
TEST = "tests/unit/test_betse_native_image_tape_trace.py"
SOURCE = "src/cells/processes/betse_native_single_cell_image_mask.py"
CALLER = "src/cells/processes/betse_native_multi_cell_caller.py"
MAPPING_TEST = "tests/unit/test_betse_native_multi_cell_tissue_to_grid.py"
MAPPING = "src/cells/processes/betse_native_multi_cell_tissue_to_grid.py"
FILES = (
    OWN,
    TEST,
    SOURCE,
    CALLER,
    MAPPING_TEST,
    MAPPING,
    "validation/source_snapshot.py",
    "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "validation/betse/betse_normal_channel_join_runtime.py",
    "validation/betse/betse_native_grid_metric_audit_software.py",
)
BASELINE = BASE / (
    "native-multi-cell-tissue-to-grid-20261101-01/s1-repair-01/pilot-03/"
    "tested-source/src/cells/processes/betse_native_single_cell_image_mask.py"
)
BASELINE_SHA256 = "11927f53f029f444f47e7d0283dbcf36887e287d58293f9ac5eaa7d8b41bc334"
FORBIDDEN = {"cells", "betse", "numpy", "scipy", "PIL", "jax"}
write = saved.write


class _BlockedImports(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempted = []

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in FORBIDDEN:
            self.attempted.append(fullname)
            raise ImportError("Isolated observer controls forbid import: " + fullname)
        return None


def _baseline():
    if (
        not BASELINE.is_file()
        or BASELINE.resolve(strict=True) != BASELINE
        or BASELINE.stat().st_nlink != 1
        or source_snapshot.digest(BASELINE) != BASELINE_SHA256
    ):
        raise ValueError("Changed or unavailable pinned historical observer")


def child(output):
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    before, profile, trace = tuple(sys.meta_path), sys.getprofile(), sys.gettrace()
    blocker = _BlockedImports()
    completed = False
    try:
        if any(name.split(".")[0] in FORBIDDEN for name in sys.modules):
            raise RuntimeError("Scientific/native library loaded before isolated controls")
        _baseline()
        sys.meta_path.insert(0, blocker)
        spec = importlib.util.spec_from_file_location("cells_image_tape_trace_tests", ROOT / TEST)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.ImageTapeTraceTests)
        outcome = unittest.TextTestRunner(verbosity=2, resultclass=saved._SavedResult).run(suite)
        write(
            output / "software-outcome.json",
            dict(
                tests_run=outcome.testsRun,
                failures=len(outcome.failures),
                errors=len(outcome.errors),
                skipped=len(outcome.skipped),
                success=outcome.wasSuccessful(),
                selected_ast_only=True,
                native_or_scientific_credit=0,
            ),
        )
        write(output / "runtime-producers.json", runtime.inventory())
        _baseline()
        completed = True
        return int(not outcome.wasSuccessful() or bool(outcome.skipped or blocker.attempted))
    except BaseException as error:
        write(
            output / "child-failure.json",
            dict(
                error=dict(type=type(error).__name__, message=str(error)),
                traceback=traceback.format_exc(),
                native_or_scientific_credit=0,
            ),
        )
        raise
    finally:
        present = blocker in sys.meta_path
        if present:
            sys.meta_path.remove(blocker)
        imports_restored = tuple(sys.meta_path) == before
        observers_restored = sys.getprofile() is profile and sys.gettrace() is trace
        sys.setprofile(profile)
        sys.settrace(trace)
        write(
            output / "native-entry-guard.json",
            dict(
                attempted=blocker.attempted,
                completed_final_certification=completed,
                guard_present_at_finish=present,
                import_chain_restored=imports_restored,
                prior_trace_and_profile_restored=observers_restored,
                selected_observer_and_capture_ast_only=True,
                production_image_caller_or_native_module_imported=False,
                native_or_scientific_credit=0,
            ),
        )


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    _baseline()
    frozen = output / "tested-source"
    snap = source_snapshot.freeze(ROOT, frozen, {name: name for name in FILES})
    manifest = source_snapshot.digest(frozen / "SNAPSHOT.json")
    tree = ast.parse((frozen / TEST).read_text())
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ImageTapeTraceTests"
    )
    expected = sorted(
        n.name for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
    )
    write(
        output / "inputs.json",
        dict(
            git_revision=snap["git_revision"],
            snapshot_manifest_sha256=manifest,
            selected_source_sha256={n: row["sha256"] for n, row in snap["files"].items()},
            baseline=dict(path=str(BASELINE), sha256=BASELINE_SHA256),
            expected_control_methods=expected,
            execution="selected observer/capture AST with stdlib stand-ins",
            cpu=6,
            threads=1,
            memory_bytes=2**30,
            wall_seconds=480,
            reserve_bytes=8 * 2**30,
            native_source_or_scientific_release=False,
        ),
    )
    source_snapshot.assert_checkout_unchanged(frozen)
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
        CELLS_TAPE_TRACE_EVIDENCE=str(output / "evidence"),
        CELLS_TAPE_BASELINE_SOURCE=str(BASELINE),
        CELLS_TAPE_BASELINE_SHA256=BASELINE_SHA256,
        TMPDIR=str(output / "tmp"),
    )
    try:
        result = guard.run_bounded(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_native_image_tape_trace_software",
                "--output",
                str(output),
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
        path = output / "process/failure.json"
        result = (
            json.loads(path.read_text())
            if path.is_file()
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
                native_or_scientific_credit=0,
            ),
        )
        return 1
    source_snapshot.verify(frozen, manifest_sha256=manifest)
    _baseline()
    outcome = json.loads((output / "software-outcome.json").read_text())
    entry = json.loads((output / "native-entry-guard.json").read_text())
    if (
        outcome["tests_run"] != len(expected)
        or entry["attempted"]
        or not all(
            entry[name]
            for name in (
                "completed_final_certification",
                "guard_present_at_finish",
                "import_chain_restored",
                "prior_trace_and_profile_restored",
            )
        )
    ):
        raise RuntimeError("Incomplete isolated observer control/guard closure")
    loaded = {}
    inventory = json.loads((output / "runtime-producers.json").read_text())
    for module, row in inventory["loaded_files"].items():
        path = Path(row["path"])
        if path.is_relative_to(frozen):
            name = str(path.relative_to(frozen))
            if name not in snap["files"] or row.get("sha256") != snap["files"][name]["sha256"]:
                raise RuntimeError("Unbound immutable runtime producer: " + module)
            loaded[module] = row
        elif path.is_relative_to(ROOT):
            raise RuntimeError("Mutable checkout producer loaded: " + module)
    for name in (OWN, TEST, "validation/betse/betse_native_grid_metric_audit_software.py"):
        if not any(Path(row["path"]) == frozen / name for row in loaded.values()):
            raise RuntimeError("Expected actual runtime producer missing: " + name)
    revision, drift, integration_error = None, [], None
    try:
        repository = Path(snap["repository"])
        source_snapshot._selected(
            repository, [row["checkout_path"] for row in snap["files"].values()]
        )
        drift = [
            name
            for name, row in snap["files"].items()
            if source_snapshot.digest(repository / row["checkout_path"]) != row["sha256"]
        ]
        revision = source_snapshot.git_state(repository, list(snap["files"]))["revision"]
    except Exception as error:
        integration_error = dict(type=type(error).__name__, message=str(error))
    result.update(
        software_outcome=outcome,
        snapshot_manifest_sha256=manifest,
        actual_frozen_runtime_producers=loaded,
        selected_ast_source_sha256={
            name: snap["files"][name]["sha256"] for name in (SOURCE, CALLER, MAPPING_TEST, MAPPING)
        },
        historical_observer_sha256=BASELINE_SHA256,
        output_pins={
            name: source_snapshot.digest(output / name)
            for name in (
                "software-outcome.json",
                "runtime-producers.json",
                "native-entry-guard.json",
            )
        },
        checkout_integration=dict(
            current_revision=revision,
            frozen_revision=snap["git_revision"],
            selected_source_drift=drift,
            policy_error=integration_error,
            pending=bool(drift or integration_error or revision != snap["git_revision"]),
            frozen_result_changed=False,
        ),
        selected_ast_only=True,
        scientific_credit=0,
    )
    write(output / "result.json", result)
    return int(
        result["status"] != "completed" or not outcome["success"] or bool(outcome["skipped"])
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
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
        return child(output)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    try:
        return prepare(output)
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
