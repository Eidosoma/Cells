"""Current metadata callers versus their original disassembly transport."""

import ast
import builtins
import dis
import json
import statistics
import sys
import time
import unittest
from pathlib import Path
from types import FunctionType, SimpleNamespace

import pytest

from tests.unit import test_betse_native_bytecode_bindings as support

ROOT = Path(__file__).resolve().parents[2]
PREFIX = ROOT / "src/cells/processes/betse_native_parameter_yaml_prefix.py"


@pytest.mark.parametrize(
    "case", unittest.defaultTestLoader.getTestCaseNames(support.BytecodeBindingsTests)
)
def test_decoder_contract(case):
    # Each original unittest method remains one guarded pytest case. Its
    # subTest outcomes belong to this explicit result, rather than creating
    # extra same-nodeid pytest reports in the established three-report runner.
    result = unittest.TestResult()
    support.BytecodeBindingsTests(case).run(result)
    assert result.testsRun == 1
    assert not result.skipped
    assert result.wasSuccessful(), (result.failures, result.errors)


def _atoms(value):
    # Explicit metadata adapter shared by both callers, not an owner validator.
    if type(value) is FunctionType:
        return (
            value,
            value.__code__,
            value.__defaults__,
            value.__kwdefaults__,
            *(cell.cell_contents for cell in value.__closure__ or ()),
        )
    return (value,)


def _lookup_oracle(code):
    return tuple(
        (instruction.opname, instruction.argval)
        for instruction in dis.get_instructions(code)
        if instruction.opname in ("LOAD_GLOBAL", "IMPORT_NAME")
    )


def _extract(path, name, helper):
    tree = ast.parse(path.read_bytes(), str(path))
    node = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    tissue = SimpleNamespace(aliases=SimpleNamespace(_atoms=_atoms), _surface=lambda cls: (cls,))
    namespace = {
        "builtins": builtins,
        "dis": dis,
        "FunctionType": FunctionType,
        "bytecode_bindings": helper,
        "parameters": SimpleNamespace(inherited=SimpleNamespace(tissue=tissue)),
        "simulator": SimpleNamespace(tissue=tissue, _chain=lambda fn: (fn,)),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def _same(actual, expected):
    assert actual[0] == expected[0]
    assert len(actual[1]) == len(expected[1])
    assert all(value is old for value, old in zip(actual[1], expected[1], strict=True))


def _function(*, wide=False):
    result = support.function(
        "def sample(value=None, *, option=None):\n"
        " import math\n"
        + (" marker = len(value), live\n" * 80 if wide else "")
        + " return len(value), live, len(value), option, math\n"
    )
    result.__globals__["live"] = object()
    result.__defaults__ = (object(),)
    result.__kwdefaults__ = {"option": object()}
    result.__annotations__ = {"value": object()}
    return result


@pytest.mark.parametrize(
    "change",
    ("unchanged", "global", "builtin", "shadow", "defaults", "keywords", "code", "closure"),
)
@pytest.mark.parametrize("wide", (False, True))
def test_current_yaml_binding_keeps_exact_order_objects_and_live_changes(change, wide):
    helper = support.helper_namespace()
    current = _extract(PREFIX, "_function_bindings", helper)
    original = _extract(PREFIX, "_function_bindings", SimpleNamespace(lookup_names=_lookup_oracle))
    fn = _function(wide=wide)
    before = current(fn)
    if change == "global":
        fn.__globals__["live"] = object()
    elif change == "builtin":
        fn.__builtins__["len"] = object()
    elif change == "shadow":
        fn.__globals__["len"] = fn.__builtins__["len"]
    elif change == "defaults":
        fn.__defaults__ = (object(),)
    elif change == "keywords":
        fn.__kwdefaults__ = {"option": object()}
    elif change == "code":
        fn.__code__ = fn.__code__.replace(co_filename="<changed-current-code>")
    elif change == "closure":
        value = object()

        def closed():
            return value

        fn = closed
        fn.__closure__[0].cell_contents = object()
    actual = current(fn)
    _same(actual, original(fn))
    if change != "unchanged":
        assert (
            actual[0] != before[0]
            or len(actual[1]) != len(before[1])
            or any(value is not old for value, old in zip(actual[1], before[1], strict=False))
        )


@pytest.mark.parametrize("wide", (False, True))
def test_current_binding_preserves_original_missing_lookup_failure(wide):
    helper = support.helper_namespace()
    fn = _function(wide=wide)
    operation = _extract(PREFIX, "_function_bindings", helper)
    del fn.__globals__["live"]
    with pytest.raises(KeyError, match="live"):
        operation(fn)


@pytest.mark.parametrize("wide", (False, True))
def test_small_function_keeps_original_path_and_large_function_uses_decoder(wide):
    calls = []

    def lookup(code):
        calls.append(code)
        return _lookup_oracle(code)

    fn = _function(wide=wide)
    assert (len(fn.__code__.co_code) >= 512) is wide
    _extract(PREFIX, "_function_bindings", SimpleNamespace(lookup_names=lookup))(fn)
    assert calls == ([fn.__code__] if wide else [])


def test_lookup_measurement_with_and_without_inherited_line_tracing(tmp_path):
    """Bounded metadata timing; speed is reported, never a correctness gate."""
    helper = support.helper_namespace()
    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
    events = [0]

    def trace(frame, event, value):
        events[0] += 1
        return trace

    if previous_trace is not None:
        raise AssertionError("Dedicated metadata child requires an empty incoming trace")
    rows = []
    try:
        for size in (10, 100, 600):
            code = support.function(
                "def sample():\n return ("
                + ",".join("name_" + str(index) for index in range(size))
                + ")\n"
            ).__code__
            expected = _lookup_oracle(code)
            for traced in (False, True):
                sys.settrace(trace if traced else None)
                for repeat in range(5):
                    for label in (
                        ("original", "compact") if repeat % 2 == 0 else ("compact", "original")
                    ):
                        operation = _lookup_oracle if label == "original" else helper.lookup_names
                        events[0] = 0
                        started = time.perf_counter_ns()
                        for _ in range(20):
                            actual = operation(code)
                        elapsed = time.perf_counter_ns() - started
                        assert actual == expected
                        rows.append(
                            dict(
                                globals=size,
                                code_bytes=len(code.co_code),
                                traced=traced,
                                repeat=repeat,
                                version=label,
                                iterations=20,
                                wall_ns=elapsed,
                                trace_events=events[0],
                            )
                        )
    finally:
        sys.settrace(previous_trace)
    assert sys.getprofile() is previous_profile and sys.gettrace() is previous_trace
    summaries = []
    for size in (10, 100, 600):
        for traced in (False, True):
            medians = {
                label: statistics.median(
                    row["wall_ns"]
                    for row in rows
                    if (row["globals"], row["traced"], row["version"]) == (size, traced, label)
                )
                for label in ("original", "compact")
            }
            summaries.append(
                dict(
                    globals=size,
                    traced=traced,
                    speed_ratio=medians["original"] / medians["compact"],
                )
            )
    (tmp_path / "bytecode-measurement.json").write_text(
        json.dumps(
            dict(
                scope="Synthetic lookup metadata under inherited line tracing; no owner or phase",
                projections_equal=True,
                rows=rows,
                summaries=summaries,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
