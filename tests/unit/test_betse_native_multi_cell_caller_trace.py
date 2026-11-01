"""Selected caller observer controls; no native source or scientific imports."""

import ast
import hashlib
import importlib.abc
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType, SimpleNamespace

import pytest

SOURCE = (
    Path(__file__).resolve().parents[2] / "src/cells/processes/betse_native_multi_cell_caller.py"
)


@pytest.fixture(autouse=True)
def blocked_science(tmp_path):
    attempts = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "PIL", "jax"}:
                attempts.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    block = Block()
    sys.meta_path.insert(0, block)
    try:
        yield
    finally:
        sys.meta_path.remove(block)
        (tmp_path / "native-entry-guard.json").write_text(
            json.dumps(
                dict(
                    attempts=attempts, source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
                )
            )
        )
    assert attempts == []


def selected_capture(*, system=sys):
    """Compile only the actual observer, with explicitly synthetic dependencies."""
    text = SOURCE.read_text()
    selected = [
        n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == "_capture"
    ]
    assert len(selected) == 1

    def remember(context, error, **where):
        context.failures.append((error, where))

    namespace = dict(
        sys=system,
        contextmanager=contextmanager,
        FunctionType=FunctionType,
        captures=SimpleNamespace(_remember_observation_error=remember),
        _mask_record=lambda context: dict(xpts_m=[0, 10], ypts_m=[0, 10]),
    )
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["_capture"]


@pytest.mark.parametrize("event", ["line", "opcode"])
@pytest.mark.parametrize("inherited", [False, True])
def test_irrelevant_events_bypass_observation_but_forward_inherited_trace(event, inherited):
    forwarded = []

    def previous(*args):
        forwarded.append(args)
        return previous

    state = SimpleNamespace(trace=previous if inherited else None)
    system = SimpleNamespace(
        gettrace=lambda: state.trace, settrace=lambda fn: setattr(state, "trace", fn)
    )

    class UnavailableContext:
        def __getattr__(self, name):
            raise AssertionError("Irrelevant event inspected context: " + name)

    before = state.trace
    frame, value = object(), object()
    with selected_capture(system=system)(UnavailableContext()):
        active = state.trace
        assert active(frame, event, value) is active
    assert state.trace is before
    assert forwarded == ([(frame, event, value)] if inherited else [])


@pytest.mark.parametrize("event", ["line", "opcode"])
def test_inherited_guard_rejection_is_immediate_and_restores_trace(event):
    cause = ValueError("synthetic inherited cause")
    error = RuntimeError("synthetic inherited rejection")

    def previous(*args):
        raise error from cause

    state = SimpleNamespace(trace=previous)
    system = SimpleNamespace(
        gettrace=lambda: state.trace, settrace=lambda fn: setattr(state, "trace", fn)
    )
    with pytest.raises(RuntimeError) as caught, selected_capture(system=system)(object()):
        state.trace(object(), event, None)
    assert caught.value is error and error.__cause__ is cause
    assert state.trace is previous


@pytest.mark.parametrize("unwind", [False, True])
@pytest.mark.parametrize("inherited", [False, True])
def test_real_trace_keeps_source_events_locals_primary_and_inherited_lines(
    unwind, inherited, tmp_path
):
    primary, cause = RuntimeError("synthetic source"), ValueError("synthetic cause")

    def source_body():
        first = 3
        second = first + 4
        if unwind:
            raise primary from cause
        return second

    selected, observed, image, outer = source_body.__code__, [], [], []

    def tape(frame, event, arg):
        observed.append((event, dict(frame.f_locals), arg))

    def image_tape(frame, event, arg):
        assert event in ("call", "return", "exception")
        if frame.f_code is selected:
            image.append(event)

    def previous(frame, event, arg):
        if frame.f_code is selected:
            outer.append(event)
        return previous

    context = SimpleNamespace(
        tape=SimpleNamespace(codes={selected}, trace=tape),
        image_tape=SimpleNamespace(trace=image_tape),
        local_codes={selected},
        locals={},
        observer=None,
        mask=None,
        failures=[],
    )
    capture = selected_capture()
    original, profiler = sys.gettrace(), sys.getprofile()
    prior = previous if inherited else None
    sys.settrace(prior)
    try:
        with capture(context):
            if unwind:
                with pytest.raises(RuntimeError) as caught:
                    source_body()
                assert caught.value is primary and primary.__cause__ is cause
            else:
                assert source_body() == 7
        assert sys.gettrace() is prior and sys.getprofile() is profiler
    finally:
        sys.settrace(original)
    expected = ["call", "exception", "return"] if unwind else ["call", "return"]
    assert [event for event, _, _ in observed] == image == expected
    assert context.locals[selected.co_qualname]["second"] == 7 and not context.failures
    if inherited:
        assert "line" in outer
        assert [event for event in outer if event != "line"] == expected
    else:
        assert outer == []
    (tmp_path / "events.json").write_text(json.dumps(dict(events=image, inherited_events=outer)))


@pytest.mark.parametrize("unwind", [False, True])
def test_capture_error_remains_separate_from_source_primary(unwind):
    primary, cause, capture_error = RuntimeError("source"), ValueError("cause"), OSError("capture")

    def source_body():
        retained = object()
        if unwind:
            raise primary from cause
        return retained

    def broken(frame, event, arg):
        if event == "return":
            raise capture_error

    context = SimpleNamespace(
        tape=SimpleNamespace(codes={source_body.__code__}, trace=broken),
        image_tape=SimpleNamespace(trace=lambda *args: None),
        local_codes=set(),
        locals={},
        observer=None,
        mask=None,
        failures=[],
    )
    before, profiler = sys.gettrace(), sys.getprofile()
    with selected_capture()(context):
        if unwind:
            with pytest.raises(RuntimeError) as caught:
                source_body()
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert source_body() is not None
    assert sys.gettrace() is before and sys.getprofile() is profiler
    assert len(context.failures) == 1 and context.failures[0][0] is capture_error
    assert context.failures[0][1]["raw"].f_code is source_body.__code__


def test_dynamic_mask_predicate_keeps_both_query_roles_and_coordinates(tmp_path):
    rows = []

    def predicate(x, y):
        return x < y

    observer = SimpleNamespace(
        current_cell=4, query_count=0, add=lambda kind, row: rows.append((kind, row))
    )
    context = SimpleNamespace(
        tape=SimpleNamespace(codes=set(), trace=lambda *args: None),
        image_tape=SimpleNamespace(trace=lambda *args: None),
        local_codes=set(),
        locals={},
        observer=observer,
        mask=None,
        failures=[],
    )
    with selected_capture()(context):
        context.mask = SimpleNamespace(clipping_function=predicate)
        assert predicate(2, 3) is True
        assert predicate(4, 1) is False
    assert [r[1]["role"] for r in rows] == ["centre", "vertex"]
    assert [(r[1]["x"], r[1]["y"], r[1]["result"]) for r in rows] == [(2, 3, True), (4, 1, False)]
    assert observer.query_count == 2 and not context.failures
    (tmp_path / "queries.json").write_text(json.dumps(rows))
