"""Held synthetic field-policy checks using the established source/resource guard.

Preparation is the default. --run explicitly requests the small synthetic suite;
it never launches BETSE, a retained grid, INIT/SIM, or a real SVD/RNG operation.
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
OWN = "validation/betse/betse_environment_field_demo_software.py"
TEST = "tests/unit/test_betse_environment_field_demo.py"
CONSUMER_TEST = "tests/unit/test_betse_environment_field_demo_consumers.py"
FILES = (
    OWN,
    TEST,
    "src/cells/processes/betse_environment_field.py",
    "src/cells/processes/betse_normal_current.py",
    "src/cells/core/errors.py",
    "src/cells/core/__init__.py",
    "src/cells/__init__.py",
    "src/cells/processes/__init__.py",
    "validation/source_snapshot.py",
    "validation/betse/betse_mesh_lifecycle_preparation_guard.py",
    "validation/betse/betse_normal_channel_join_runtime.py",
)
LIMITS = dict(timeout=480, max_rss_bytes=2**30, min_available_bytes=8 * 2**30)
EXPECTED_CASES = 19
CONSUMER_CASES = 45
CONSUMER_FILES = (
    CONSUMER_TEST,
    "src/cells/processes/betse_ecm_transport.py",
    "src/cells/processes/betse_ecm_sim_grn.py",
    "src/cells/processes/betse_normal_ecm_molecule_lifecycle.py",
    "src/cells/processes/betse_normal_ecm_initialization.py",
    "src/cells/processes/betse_normal_ecm_molecule_checkpoint.py",
    "src/cells/processes/betse_normal_ecm_molecule_checkpoint_codec.py",
    "src/cells/processes/betse_normal_ecm_molecule_checkpoint_records.py",
    "src/cells/core/specs.py",
    "src/cells/physiology_checkpoint.py",
)


def selection(suite):
    if suite == "field":
        return TEST, EXPECTED_CASES, FILES, FILES
    if suite == "consumers":
        # Remaining pinned sources are read/compiled as disclosed literal
        # metadata predicates/codec definitions, not imported phase producers.
        required = FILES + (
            CONSUMER_TEST,
            "src/cells/processes/betse_ecm_transport.py",
            "src/cells/core/specs.py",
        )
        return CONSUMER_TEST, CONSUMER_CASES, FILES + CONSUMER_FILES, required
    raise ValueError("Unknown focused field-policy software suite")


def write(path, value):
    snapshot.write_json(path, value)


def verify_runtime(frozen, manifest, producers, cpu, suite="field"):
    _, _, _, required = selection(suite)
    if producers["measured_cpu_affinity"] != [cpu]:
        raise ValueError("Worker affinity differs from its explicit singleton plan")
    executable = producers["executable"]
    if (
        Path(executable["path"]) != Path(sys.executable).resolve()
        or snapshot.digest(executable["path"]) != executable["sha256"]
    ):
        raise ValueError("Changed worker executable")
    loaded = set()
    for name, row in producers["loaded_files"].items():
        path = Path(row["path"])
        if row.get("unavailable") or snapshot.digest(path) != row.get("sha256"):
            raise ValueError("Changed/unavailable loaded runtime file: " + name)
        if path.is_relative_to(frozen):
            rel = str(path.relative_to(frozen))
            if rel not in manifest["files"] or row["sha256"] != manifest["files"][rel]["sha256"]:
                raise ValueError("Unbound loaded source: " + name)
            loaded.add(rel)
        elif name.split(".")[0] in ("cells", "validation") or name in (
            "__main__",
            Path(TEST).stem,
            Path(CONSUMER_TEST).stem,
        ):
            raise ValueError("Project producer outside immutable image: " + name)
    if set(required) - loaded:
        raise ValueError("Missing actual frozen producers: " + repr(sorted(set(required) - loaded)))
    return sorted(loaded)


def child(output, cpu, manifest_sha256, suite="field"):
    test, expected_cases, files, _ = selection(suite)
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    if os.sched_getaffinity(0) != {cpu}:
        raise ValueError("Worker singleton affinity mismatch")
    snapshot.verify(ROOT, manifest_sha256=manifest_sha256)
    inputs = json.loads((output / "inputs.json").read_text())
    if (
        inputs["cpu"] != cpu
        or inputs["source_manifest_sha256"] != manifest_sha256
        or inputs["limits"] != LIMITS
        or inputs["selected_test"] != test
        or inputs["expected_cases"] != expected_cases
        or inputs.get("suite", "field") != suite
        or set(inputs["source_sha256"]) != set(files)
    ):
        raise ValueError("Changed worker declaration")
    attempted, operations, restore_errors = [], {}, []
    previous, previous_trace = sys.getprofile(), sys.gettrace()
    code = None

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] == "betse":
                attempted.append(dict(kind="native_import", name=fullname))
                raise AssertionError("Original BETSE imports forbidden in field demo software")

    class Reports:
        def pytest_collection_finish(self, session):
            ids = [item.nodeid for item in session.items]
            write(output / "collected.json", dict(nodeids=ids, count=len(ids)))
            if len(ids) != expected_cases or len(ids) != len(set(ids)):
                raise ValueError("Unexpected synthetic field-policy case roster")

        def pytest_runtest_logreport(self, report):
            if report.when == "call" or report.failed:
                name = hashlib.sha256((report.nodeid + report.when).encode()).hexdigest()
                write(
                    output / "case-reports" / (name + ".json"),
                    dict(
                        nodeid=report.nodeid,
                        when=report.when,
                        outcome=report.outcome,
                        traceback=str(report.longrepr) if report.failed else None,
                    ),
                )

    block = Block()
    sys.meta_path.insert(0, block)
    saved_random = {}
    literal_files = frozenset(str(ROOT / path) for path in CONSUMER_FILES[2:])
    try:
        import numpy as np
        import pytest

        # Import-only startup precedes the test guard. No real SVD or NumPy RNG
        # invocation is allowed during collection or selected test execution.
        if any(name == "betse" or name.startswith("betse.") for name in sys.modules):
            raise ValueError("Native package was already loaded")
        real_pinv = np.linalg.pinv
        functions, seen, codes = [real_pinv], set(), set()
        while functions:
            function = functions.pop()
            if id(function) in seen:
                continue
            seen.add(id(function))
            if hasattr(function, "__code__"):
                codes.add(function.__code__)
            for name in ("__wrapped__", "_implementation"):
                value = getattr(function, name, None)
                if value is not None:
                    functions.append(value)

        def forbidden(*args, **kwargs):
            attempted.append(dict(kind="real_SVD_or_numpy_RNG"))
            raise AssertionError("Synthetic field policy controls cannot call real SVD/RNG")

        np.linalg.pinv = forbidden
        for name in ("RandomState", "default_rng", "seed", "rand", "randn", "random", "normal"):
            saved_random[name] = getattr(np.random, name)
            setattr(np.random, name, forbidden)

        def profile(frame, event, arg):
            if previous is not None:
                previous(frame, event, arg)
            if event == "call":
                module = frame.f_globals.get("__name__", "")
                if (
                    frame.f_code in codes
                    or module == "betse"
                    or module.startswith("betse.")
                    or "/betse/science/" in frame.f_code.co_filename
                    or module.startswith("numpy.random")
                    or (
                        suite == "consumers"
                        and module == "cells.processes.betse_ecm_transport"
                        and frame.f_code.co_name
                        in ("step", "_step_source", "_electroflux", "_smooth")
                    )
                ):
                    attempted.append(dict(kind="forbidden_body", name=frame.f_code.co_qualname))
                    raise AssertionError("Original native/SVD/RNG body forbidden")
                if (
                    module
                    in (
                        "cells.processes.betse_environment_field",
                        "cells.processes.betse_normal_current",
                        "cells.processes.betse_ecm_transport",
                        "_field_demo_consumer_literals",
                    )
                    or frame.f_code.co_filename in literal_files
                ):
                    key = module + "." + frame.f_code.co_name
                    operations[key] = operations.get(key, 0) + 1
            elif event == "c_call" and (getattr(arg, "__module__", "") or "").startswith(
                "numpy.random"
            ):
                attempted.append(dict(kind="numpy_RNG_C_call"))
                raise AssertionError("NumPy RNG call forbidden")

        sys.setprofile(profile)
        try:
            code = pytest.main(
                [
                    "-q",
                    "--noconftest",
                    "-c",
                    "/dev/null",
                    "-p",
                    "no:cacheprovider",
                    str(ROOT / test),
                    "--junitxml=" + str(output / "junit.xml"),
                    "--basetemp=" + str(output / "tmp"),
                ],
                plugins=[Reports()],
            )
        finally:
            primary = sys.exception()
            for setter, target in ((sys.setprofile, previous), (sys.settrace, previous_trace)):
                try:
                    setter(target)
                except BaseException as error:
                    restore_errors.append(error)
            restored = sys.getprofile() is previous and sys.gettrace() is previous_trace
            np.linalg.pinv = real_pinv
            for name, value in saved_random.items():
                setattr(np.random, name, value)
            if restore_errors or not restored:
                if primary is None:
                    raise RuntimeError("Field software guard restoration incomplete")
                primary.add_note("Field software guard restoration incomplete")
    finally:
        if block in sys.meta_path:
            sys.meta_path.remove(block)
        write(
            output / "native-entry-guard.json",
            dict(
                attempted=attempted,
                actual_entries=operations,
                pytest_completed=code is not None,
                hooks_restored=sys.getprofile() is previous and sys.gettrace() is previous_trace,
                cleanup_error_count=len(restore_errors),
                scope="Selected synthetic tests; NumPy import startup is outside RNG accounting",
                real_pinv_allowed=False,
                native_execution=False,
                scientific_acceptance=False,
            ),
        )
        write(output / "runtime-producers.json", runtime.inventory())
    write(output / "pytest-exit.json", dict(returncode=int(code)))
    return int(code) if not attempted and not restore_errors else 1


def prepare(output, cpu, *, run=False, suite="field"):
    test, expected_cases, files, _ = selection(suite)
    base = Path("/mnt/workspaces/Cells")
    output = output.absolute()
    if (
        output == base
        or not output.is_relative_to(base)
        or output.resolve() != output
        or type(cpu) is not int
        or cpu < 0
        or os.sched_getaffinity(0) != {cpu}
    ):
        raise ValueError("Require explicit singleton CPU and a fresh regular /mnt output")
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "source"
    manifest = snapshot.freeze(ROOT, frozen, {name: name for name in files})
    digest = snapshot.digest(frozen / "SNAPSHOT.json")
    command = [
        sys.executable,
        "-B",
        "-m",
        "validation.betse.betse_environment_field_demo_software",
        "--output",
        str(output),
        "--cpu",
        str(cpu),
        "--suite",
        suite,
        "--child",
        "--manifest-sha256",
        digest,
    ]
    write(
        output / "inputs.json",
        dict(
            kind="cells.environment_field_demo_software@1",
            cpu=cpu,
            threads=1,
            limits=LIMITS,
            source_manifest_sha256=digest,
            suite=suite,
            selected_test=test,
            expected_cases=expected_cases,
            source_sha256={name: row["sha256"] for name, row in manifest["files"].items()},
            command=command,
            held=not run,
            synthetic_only=True,
            actual_native_or_INIT_execution_released=False,
            scientific_acceptance=False,
            runtime_scope="Loaded Python/extension origins; not a complete BLAS library inventory",
            consumer_scope=(
                "Real field/material bindings; literal grid/lifecycle/owner/codec controls, "
                "closed existing record subset; no complete INIT or checkpoint admission"
                if suite == "consumers"
                else None
            ),
        ),
    )
    if not run:
        return 0
    for name in ("process", "case-reports", "tmp", "evidence"):
        (output / name).mkdir()
    environment = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join((str(frozen / "src"), str(frozen))),
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONNOUSERSITE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        NUMEXPR_NUM_THREADS="1",
        VECLIB_MAXIMUM_THREADS="1",
        CUDA_VISIBLE_DEVICES="",
        CELLS_FIELD_DEMO_EVIDENCE=str(output / "evidence"),
        TMPDIR=str(output / "tmp"),
    )
    try:
        process = guard.run_bounded(
            command,
            directory=output / "process",
            cwd=frozen,
            env=environment,
            process_tree_memory_metric="rss",
            **LIMITS,
        )
        snapshot.verify(frozen, manifest_sha256=digest)
        producers = json.loads((output / "runtime-producers.json").read_text())
        loaded = verify_runtime(frozen, manifest, producers, cpu, suite)
        check = json.loads((output / "native-entry-guard.json").read_text())
        exit_record = json.loads((output / "pytest-exit.json").read_text())
        passed = (
            not check["attempted"]
            and check["pytest_completed"]
            and check["hooks_restored"]
            and not check["cleanup_error_count"]
            and exit_record["returncode"] == process["returncode"] == 0
        )
        pins = {
            str(path.relative_to(output)): snapshot.digest(path)
            for name in ("case-reports", "evidence")
            for path in sorted((output / name).rglob("*"))
            if path.is_file()
        }
        for name in (
            "junit.xml",
            "collected.json",
            "pytest-exit.json",
            "native-entry-guard.json",
            "runtime-producers.json",
        ):
            pins[name] = snapshot.digest(output / name)
        write(
            output / "result.json",
            dict(
                status="passed_synthetic_controls" if passed else "failed_synthetic_controls",
                process=process,
                source_manifest_sha256=digest,
                loaded_source=loaded,
                evidence_sha256=pins,
                native_entry_attempts=check["attempted"],
                scientific_acceptance=False,
                actual_INIT_SIM_or_native_execution=False,
            ),
        )
        return 0 if passed else 1
    except BaseException as error:
        write(
            output / "failure.json",
            dict(
                status="failed",
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                source_manifest_sha256=digest,
                scientific_acceptance=False,
                automatic_retry=False,
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--suite", choices=("field", "consumers"), default="field")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--manifest-sha256", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        if not args.manifest_sha256 or args.run:
            parser.error("Frozen child requires its manifest and cannot prepare/launch")
        return child(args.output.absolute(), args.cpu, args.manifest_sha256, args.suite)
    if args.manifest_sha256:
        parser.error("Manifest belongs only to the frozen child")
    return prepare(args.output, args.cpu, run=args.run, suite=args.suite)


if __name__ == "__main__":
    raise SystemExit(main())
