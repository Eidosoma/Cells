"""Measure exact extracted parameter metadata; never execute original bodies."""

import argparse
import ast
import hashlib
import json
import os
import runpy
import sys
import time
from pathlib import Path
from types import CodeType

ROOT = Path(__file__).resolve().parents[2]
PARAMETERS = "src/cells/processes/betse_native_phase_parameters.py"
REUSED_TEST = "tests/unit/test_betse_native_source_compilation_cache.py"
TEST = "tests/unit/test_betse_native_parameter_ast_metadata.py"
ORIGINAL = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse/science/parameters.py")
ORIGINAL_SHA256 = "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"


def _write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def measure(directory, *, baseline_source=None, baseline_manifest_sha256=None):
    """Measure current warm checks against full dump on pinned real source."""
    directory.mkdir()
    raw = ORIGINAL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("Exact pinned original Parameters source required")
    node = next(
        n for n in ast.parse(raw).body if type(n) is ast.ClassDef and n.name == "Parameters"
    )
    reuse = runpy.run_path(str(ROOT / REUSED_TEST))
    parameters, producer = reuse["_load"](
        ROOT / PARAMETERS, reuse["PARAMETER_FUNCTIONS"], "_COMPILATION_"
    )
    baseline = baseline_pin = None
    if (baseline_source is None) is not (baseline_manifest_sha256 is None):
        raise ValueError("Complete immutable baseline binding required")
    if baseline_source is not None:
        from validation import source_snapshot

        manifest = source_snapshot.verify(baseline_source, manifest_sha256=baseline_manifest_sha256)
        baseline_path = baseline_source / PARAMETERS
        names = {
            n.name
            for n in ast.parse(baseline_path.read_bytes()).body
            if isinstance(n, ast.FunctionDef)
        }
        functions = tuple(n for n in reuse["PARAMETER_FUNCTIONS"] if n in names)
        baseline, baseline_pin = reuse["_load"](baseline_path, functions, "_COMPILATION_")
        if baseline_pin != manifest["files"][PARAMETERS]["sha256"]:
            raise ValueError("Baseline metadata source changed")
    calls, attempted, samples = {}, [], []
    prior, trace = sys.getprofile(), sys.gettrace()

    def guard(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call":
            name = frame.f_globals.get("__name__", "")
            if name.startswith(("cells.", "betse.", "numpy.", "scipy.")) or (
                frame.f_code.co_filename == str(ORIGINAL)
            ):
                attempted.append((name, frame.f_code.co_qualname))
                raise AssertionError("Native/owner/compiled source execution held")
            if frame.f_code is ast.dump.__code__:
                calls["ast.dump"] = calls.get("ast.dump", 0) + 1

    try:
        sys.setprofile(guard)
        start = time.perf_counter_ns()
        code = parameters._method_code(
            node, "_load_ion_profile", str(ORIGINAL), native_context=True
        )
        cold_ns = time.perf_counter_ns() - start
        _, classes, _, _, _ = parameters._compiled_source(raw, str(ORIGINAL))
        expected_dump, plan = next(
            (dump, plan) for name, dump, plan in classes if name == node.name
        )
        assert plan is not None
        independent = compile(raw, str(ORIGINAL), "exec", dont_inherit=True)
        pending, found = [independent], []
        while pending:
            current = pending.pop()
            if current.co_qualname == "Parameters._load_ion_profile":
                found.append(current)
            pending.extend(c for c in current.co_consts if type(c) is CodeType)
        assert len(found) == 1 and code == found[0]
        legacy = None
        if baseline is not None:
            legacy = baseline._method_code(
                node, "_load_ion_profile", str(ORIGINAL), native_context=True
            )
            assert legacy == code
        start_dump_count = calls.get("ast.dump", 0)
        operations = [
            (
                "native_method_check",
                lambda: parameters._method_code(
                    node, "_load_ion_profile", str(ORIGINAL), native_context=True
                ),
            ),
            ("complete_class_dump", lambda: ast.dump(node, include_attributes=True)),
            ("closed_selector_match", lambda: parameters._compilation_class_matches(node, plan)),
        ]
        if baseline is not None:
            operations.append(
                (
                    "baseline_native_check",
                    lambda: baseline._method_code(
                        node, "_load_ion_profile", str(ORIGINAL), native_context=True
                    ),
                )
            )
        operation_calls = {name: 0 for name, _ in operations}
        for index in range(7):
            for name, function in operations if index % 2 == 0 else reversed(operations):
                before_calls = calls.get("ast.dump", 0)
                wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                value = function()
                elapsed = time.perf_counter_ns() - wall
                cpu = time.process_time_ns() - cpu
                if name == "native_method_check":
                    assert value is code
                    assert calls.get("ast.dump", 0) == before_calls
                elif name == "baseline_native_check":
                    assert value is legacy
                elif name == "complete_class_dump":
                    assert value == expected_dump
                else:
                    assert value is True
                samples.append(dict(operation=name, repeat=index, wall_ns=elapsed, cpu_ns=cpu))
                operation_calls[name] += calls.get("ast.dump", 0) - before_calls
        assert calls.get("ast.dump", 0) - start_dump_count == (14 if baseline else 7)
        assert not attempted
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)
    _write(
        directory / "measurement.json",
        dict(
            phase_parameters_sha256=producer,
            baseline_source_sha256=baseline_pin,
            baseline_manifest_sha256=baseline_manifest_sha256,
            operation_dump_calls=operation_calls,
            original_source_sha256=ORIGINAL_SHA256,
            original_source_bytes=len(raw),
            class_plan_rows=len(plan[0]),
            cold_method_ns=cold_ns,
            samples=samples,
            ast_dump_calls=calls,
            forbidden_entries=attempted,
            hooks_restored=sys.getprofile() is prior and sys.gettrace() is trace,
            independent_full_module_code_match=True,
            compiled_native_source_entries=0,
            numerical_or_owner_work=0,
            warm_native_calls=7,
            warm_native_dump_calls=0,
            scope=(
                "Source metadata under a minimal rejecting profiler; "
                "not total runtime attribution or actual parent validation."
            ),
            scientific_credit=0,
        ),
    )


def controls(directory, *, select=None):
    """Reuse original compiler drift/refusal controls alongside new AST cases."""
    import pytest

    directory.mkdir()
    argv = [
        "-q",
        "-c",
        "/dev/null",
        "--noconftest",
        "-p",
        "no:cacheprovider",
        str(ROOT / TEST),
        str(ROOT / REUSED_TEST),
        "--basetemp",
        str(directory / "pytest"),
        "--junitxml",
        str(directory / "tests.xml"),
    ]
    if select is not None:
        if type(select) is not str or not select:
            raise ValueError("Explicit nonempty metadata control selector required")
        argv.extend(("-k", select))
    result = int(pytest.main(argv))
    _write(
        directory / "software-result.json",
        dict(
            returncode=result, actual_native_owner_or_RNG_work_requested=False, scientific_credit=0
        ),
    )
    if result:
        raise SystemExit(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--measure", type=Path)
    mode.add_argument("--controls", type=Path)
    parser.add_argument("--baseline-source", type=Path)
    parser.add_argument("--baseline-manifest-sha256")
    parser.add_argument("--select")
    args = parser.parse_args()
    if args.measure:
        measure(
            args.measure,
            baseline_source=args.baseline_source,
            baseline_manifest_sha256=args.baseline_manifest_sha256,
        )
    else:
        controls(args.controls, select=args.select)


if __name__ == "__main__":
    main()
