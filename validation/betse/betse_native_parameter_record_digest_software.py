"""Reuse frozen resource/guard accounting for the metadata digest only."""

import argparse
import ast
import hashlib
import importlib
import json
import os
import resource
import struct
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from threading import get_ident
from types import CodeType, FunctionType, SimpleNamespace
from typing import TYPE_CHECKING

from validation.betse import native_init_terminal_reference_software as base

if TYPE_CHECKING:
    from cells.processes import betse_native_parameter_yaml_prefix as _yaml_metadata  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "src/cells/processes/betse_native_parameter_record_digest.py"
TEST = "tests/unit/test_betse_native_parameter_record_digest.py"
FILE = "validation/betse/betse_native_parameter_record_digest_software.py"
MODULE = "validation.betse.betse_native_parameter_record_digest_software"
PREFIX = "src/cells/processes/betse_native_parameter_yaml_prefix.py"
ORIGINAL = "src/cells/processes/betse_normal_current.py"
OWNED = (SOURCE, TEST, FILE)
RELEASE = "CELLS_PARAMETER_RECORD_DIGEST_BLOCKED_SOFTWARE"
POLICY = dict(base.POLICY, cpu=4)
snapshot, guard, runtime = base.snapshot, base.guard, base.runtime
BASE, CLOSURE, Reports = base.BASE, base.CLOSURE, base.Reports
_RECORD_CODES = frozenset()
_CAPTURE_FAILURES = []


def forbidden(frame):
    module, filename = frame.f_globals.get("__name__", ""), frame.f_code.co_filename
    if filename.startswith(base.NATIVE_ROOT + os.sep):
        return True
    if module == "cells.processes.betse_native_parameter_record_digest":
        return False
    if module == "cells.processes.betse_normal_current":
        return frame.f_code not in _RECORD_CODES
    return base.forbidden(frame)


@contextmanager
def blocked(folder):
    global _RECORD_CODES
    module = sys.modules["cells.processes.betse_native_parameter_record_digest"]
    pending, codes = [module._RECORD.__code__, module._DIGEST.__code__], set()
    while pending:
        code = pending.pop()
        codes.add(code)
        pending.extend(item for item in code.co_consts if type(item) is CodeType)
    _RECORD_CODES = frozenset(codes)
    delegate = contextmanager(
        FunctionType(base.blocked.__wrapped__.__code__, dict(vars(base), forbidden=forbidden))
    )
    with delegate(folder):
        yield


def _namespace():
    return dict(
        vars(base),
        **{
            name: globals()[name]
            for name in ("ROOT", "SOURCE", "TEST", "FILE", "MODULE", "OWNED", "RELEASE", "POLICY")
        },
        __file__=__file__,
    )


def prepare(output, select):
    FunctionType(base.prepare.__code__, _namespace())(output, select)
    inputs = json.loads((output / "inputs.json").read_text())
    manifest = snapshot.verify(output / "source", manifest_sha256=inputs["snapshot_sha256"])
    for path in (PREFIX, ORIGINAL):
        if path not in manifest["files"]:
            raise ValueError("Read-only original serializer/YAML metadata absent from snapshot")


def software(output, select):
    return FunctionType(base.software.__code__, _namespace())(output, select)


def child(output, select):
    import pytest

    inputs = json.loads((output / "inputs.json").read_text())
    if inputs["software_release_requested"] is not True or inputs["policy"] != POLICY:
        raise ValueError("Explicit immutable CPU4 metadata digest software required")
    manifest = snapshot.verify(ROOT, manifest_sha256=inputs["snapshot_sha256"])
    for name in OWNED:
        if snapshot.digest(ROOT / name) != inputs["owned_files"][name]:
            raise ValueError("Selected metadata digest producer changed")
    code, primary, failures = 1, None, []
    try:
        module = importlib.import_module("cells.processes.betse_native_parameter_record_digest")
        if Path(module.__file__).resolve() != ROOT / SOURCE:
            raise ValueError("Actual frozen metadata digest required")
        snapshot.write_json(
            output / "source-plan.json",
            dict(
                original_serializer_sha256=module.ORIGINAL_SHA256,
                fresh_hash_every_call=True,
                recursive_original_fallback=True,
                input_or_digest_cache=False,
                optimized_limits=module._LIMITS,
                metadata_read_files={
                    name: manifest["files"][name]["sha256"] for name in (PREFIX, ORIGINAL)
                },
                actual_native_source_or_owner_execution=False,
            ),
        )
        os.environ[RELEASE] = "1"
        reports = Reports(output / "reports")
        code = pytest.main(
            [
                "--noconftest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "-o",
                "addopts=",
                "--basetemp=" + str(output / "pytest"),
                "--junitxml=" + str(output / "tests.xml"),
                str(ROOT / TEST),
                "-k",
                select,
            ],
            plugins=[reports],
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            snapshot.write_json(output / "runtime.json", runtime.inventory())
        except BaseException as error:
            failures.append(error)
        try:
            snapshot.write_json(
                output / "loaded-selected.json",
                {name: manifest["files"][name]["sha256"] for name in OWNED},
            )
        except BaseException as error:
            failures.append(error)
        if failures:
            _CAPTURE_FAILURES.append((primary, failures))
            if primary is None:
                raise failures[0]
    return int(code)


def measure_tree(output, *, baseline_source=None, baseline_manifest_sha256=None):
    """Compare exact before/current metadata functions, splitting encoding."""
    if os.environ.get(RELEASE) != "1" or os.sched_getaffinity(0) != {3}:
        raise ValueError("Explicit CPU3 metadata measurement required")
    output.mkdir()
    source = ROOT / SOURCE
    raw = source.read_bytes()
    if baseline_source is None or baseline_manifest_sha256 is None:
        raise ValueError("Exact immutable pre-change metadata source required")
    manifest = snapshot.verify(baseline_source, manifest_sha256=baseline_manifest_sha256)
    before_raw = (baseline_source / SOURCE).read_bytes()
    if hashlib.sha256(before_raw).hexdigest() != manifest["files"][SOURCE]["sha256"]:
        raise ValueError("Before metadata source changed")
    fallback, exit_ = object(), object()
    functions = {}
    for name, payload in (("before", before_raw), ("current", raw)):
        node = next(
            n
            for n in ast.parse(payload).body
            if type(n) is ast.FunctionDef and n.name == "_metadata_tree"
        )
        namespace = dict(_EXIT=exit_, _FALLBACK=fallback, _PACK=struct.pack)
        exec(
            compile(
                ast.Module(body=[node], type_ignores=[]),
                "<extracted-metadata-tree-" + name + ">",
                "exec",
            ),
            namespace,
        )
        functions[name] = namespace["_metadata_tree"]
    audit_path = ROOT / "src/cells/processes/betse_native_parameter_paths.py"
    audit_raw = audit_path.read_bytes()
    audit = next(
        n for n in ast.parse(audit_raw).body if type(n) is ast.FunctionDef and n.name == "_audit"
    )
    active = []
    audit_namespace = dict(_ACTIVE=active, get_ident=get_ident, os=os)
    exec(
        compile(
            ast.Module(body=[audit], type_ignores=[]),
            "<extracted-readonly-parameter-audit>",
            "exec",
        ),
        audit_namespace,
    )
    context = SimpleNamespace(
        thread=get_ident(), audit_ready=False, directory_depth=0, directory_calls=0
    )
    sys.addaudithook(audit_namespace["_audit"])
    active.append(context)
    try:
        sys.audit("cells.native_parameter_paths.guard_probe", context)
        if not context.audit_ready:
            raise ValueError("Actual metadata audit installation acknowledgement required")
    finally:
        active.clear()
    corpora = {
        "nested_metadata": {
            f"row{i:03d}": [(i, j, -0.0, {"name": str(j)}) for j in range(16)] for i in range(32)
        },
        "wide_metadata": [
            {"id": i, "labels": ("cell", "membrane", "environment")} for i in range(1024)
        ],
    }
    limits = (131072, 128, 8 * 2**20)
    prior, trace = sys.getprofile(), sys.gettrace()
    counts, samples, attempted = {}, [], []
    code_set = {fn.__code__ for fn in functions.values()}

    def guard(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_globals.get("__name__", "").startswith(
            ("cells.", "betse.", "numpy.", "scipy.")
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual native/model/owner/RNG execution held")
        if event == "c_call" and frame.f_code in code_set:
            counts["c_calls"] = counts.get("c_calls", 0) + 1
            if arg is id:
                counts["id"] = counts.get("id", 0) + 1

    try:
        sys.setprofile(guard)
        for audit_enabled in (False, True):
            if audit_enabled:
                active.append(context)
            for corpus, value in corpora.items():
                expected = functions["before"](value, limits)
                canonical = json.dumps(
                    expected, sort_keys=True, separators=(",", ":"), allow_nan=False
                )
                for index in range(7):
                    for name in ("before", "current") if index % 2 == 0 else ("current", "before"):
                        counts.clear()
                        wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                        result = functions[name](value, limits)
                        elapsed, cpu = time.perf_counter_ns() - wall, time.process_time_ns() - cpu
                        work = dict(counts)
                        if result != expected:
                            raise ValueError("Fresh metadata projection changed")
                        samples.append(
                            dict(
                                corpus=corpus,
                                audit=audit_enabled,
                                operation=name,
                                repeat=index,
                                wall_ns=elapsed,
                                cpu_ns=cpu,
                                **work,
                            )
                        )
                    wall, cpu = time.perf_counter_ns(), time.process_time_ns()
                    encoded = json.dumps(
                        expected, sort_keys=True, separators=(",", ":"), allow_nan=False
                    )
                    samples.append(
                        dict(
                            corpus=corpus,
                            audit=audit_enabled,
                            operation="encoding",
                            repeat=index,
                            wall_ns=time.perf_counter_ns() - wall,
                            cpu_ns=time.process_time_ns() - cpu,
                        )
                    )
                    if encoded != canonical:
                        raise ValueError("Canonical metadata bytes changed")
            active.clear()
    finally:
        active.clear()
        sys.settrace(trace)
        sys.setprofile(prior)
    snapshot.write_json(
        output / "measurement.json",
        dict(
            source_sha256=hashlib.sha256(raw).hexdigest(),
            audit_source_sha256=hashlib.sha256(audit_raw).hexdigest(),
            baseline_source_sha256=hashlib.sha256(before_raw).hexdigest(),
            baseline_manifest_sha256=baseline_manifest_sha256,
            samples=samples,
            forbidden_entries=attempted,
            hooks_restored=sys.getprofile() is prior and sys.gettrace() is trace,
            audit_is_original_metadata_body_with_synthetic_readonly_context=True,
            no_actual_owner_or_program_RNG_execution=True,
            scientific_credit=0,
        ),
    )


def main():
    global POLICY
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepare", "software", "child", "measure-tree"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--select", default="record_digest")
    parser.add_argument("--software-cpu", type=int, choices=(4, 6), default=4)
    parser.add_argument("--measurement-cpu", type=int, choices=(3,), default=3)
    parser.add_argument("--baseline-source", type=Path)
    parser.add_argument("--baseline-manifest-sha256")
    args = parser.parse_args()
    POLICY = dict(POLICY, cpu=args.software_cpu)
    if args.measure_tree is not None:
        POLICY = dict(POLICY, cpu=args.measurement_cpu)
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
        measure_tree(
            args.measure_tree,
            baseline_source=args.baseline_source,
            baseline_manifest_sha256=args.baseline_manifest_sha256,
        )
        return 0
    if args.child is not None:
        resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
        return child(args.child, args.select)
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
    if args.prepare is not None:
        prepare(args.prepare, args.select)
        return 0
    if args.software is not None:
        return software(args.software, args.select)
    parser.error("Choose prepare, software or child")


if __name__ == "__main__":
    raise SystemExit(main())
