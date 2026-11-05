"""Actual observer hooks on synthetic frames; no original/native body runs."""

import ast
import os
import sys
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace

import pytest

from validation.betse import native_init_terminal_reference as reference
from validation.betse import native_init_terminal_reference_boundaries_software as software

LOOP_PROBE = (
    "def _run_sim_core_loop(time_steps, buffer, history):\n"
    "    for t in time_steps:\n"
    "        history.append(t)\n"
    "        buffer.fill(0)\n"
    "        buffer[0] = t + 7\n"
)
RETURN_PROBE = (
    "def metadata_helper():\n"
    "    return None\n"
    "def metadata_outer(buffer):\n"
    "    metadata_helper(); buffer.fill(0)\n"
)
UNWIND_PROBE = (
    "def metadata_helper(primary):\n"
    "    raise primary\n"
    "def metadata_outer(buffer, primary):\n"
    "    try:\n"
    "        metadata_helper(primary)\n"
    "    finally:\n"
    "        buffer.fill(0)\n"
)


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit immutable native-blocked boundary software required")
    with software.blocked(tmp_path):
        yield


class FalseySourceError(ValueError):
    def __bool__(self):
        return False


def _code(text, path, *, offset=0):
    tree = ast.parse(text)
    ast.increment_lineno(tree, offset)
    unit = compile(tree, str(path), "exec", dont_inherit=True)
    codes = {node.co_name: node for node in unit.co_consts if type(node) is CodeType}
    namespace = {"__name__": "tests.synthetic_boundary_metadata"}
    functions = {name: FunctionType(code, namespace) for name, code in codes.items()}
    namespace.update(functions)
    return functions, tree


def _bits():
    import numpy as np

    return np.frombuffer(bytes.fromhex("010000000000f87f0000000000000080"), dtype="<f8").copy()


def _observer(tmp_path, *, capture=None, method=None):
    state = reference.State(stage="synthetic boundary probe")
    observer = reference.Observe(
        state,
        tmp_path,
        SimpleNamespace(save=lambda *a: None),
        None,
        reference._loop_line(reference.NATIVE_ROOT),
    )
    rows = []
    if method == "iteration":

        def iteration(frame):
            if "t" not in frame.f_locals:
                return
            row = dict(
                frame=frame,
                t=frame.f_locals["t"],
                buffer=frame.f_locals["buffer"],
                bytes=frame.f_locals["buffer"].tobytes(),
            )
            rows.append(row)
            state.raw["synthetic_iteration"] = row
            if capture is not None:
                raise capture

        observer._iteration = iteration
    if method == "return":
        original = observer._return

        def returned(frame, value):
            original(frame, value)
            if frame.f_code.co_name == "metadata_helper":
                state.raw["synthetic_helper_return"] = dict(frame=frame, value=value)
                if capture is not None:
                    raise capture

        observer._return = returned
    return observer, rows


def _loop(tmp_path):
    # Only this header/name/line correspond to original source. The entire
    # body is a declared synthetic data-buffer fixture, never a native body.
    line = reference._loop_line(reference.NATIVE_ROOT)
    functions, tree = _code(LOOP_PROBE, tmp_path / "metadata_loop.py", offset=line - 2)
    return functions["_run_sim_core_loop"], tree


def test_reference_boundary_actual_AST_header_and_synthetic_frame_mapping(tmp_path):
    source = reference.NATIVE_ROOT / "betse/science/sim.py"
    raw = source.read_bytes()
    assert reference._sha(raw) == reference.CRITICAL["betse/science/sim.py"]
    method = reference._method(ast.parse(raw), "Simulator", "_run_sim_core_loop")
    original = next(node for node in method.body if isinstance(node, ast.For))
    probe, tree = _loop(tmp_path)
    synthetic = tree.body[0].body[0]
    assert ast.dump(synthetic.target) == ast.dump(original.target)
    assert ast.dump(synthetic.iter) == ast.dump(original.iter)
    assert synthetic.lineno == original.lineno == reference._loop_line(reference.NATIVE_ROOT)
    assert probe.__code__.co_name == method.name
    assert not Path(probe.__code__.co_filename).is_relative_to(reference.NATIVE_ROOT)
    assert probe.__globals__["__name__"] == "tests.synthetic_boundary_metadata"
    assert ast.dump(
        ast.Module(body=synthetic.body, type_ignores=[]), include_attributes=False
    ) != ast.dump(ast.Module(body=original.body, type_ignores=[]), include_attributes=False)


@pytest.mark.parametrize("error_type", [OSError, FalseySourceError])
def test_reference_boundary_iteration_capture_stops_before_next_C_reset(tmp_path, error_type):
    probe, _ = _loop(tmp_path)
    buffer = _bits()
    history = []
    capture = error_type("original capture failure")
    capture.__cause__ = KeyError("capture cause")
    observer, rows = _observer(tmp_path, capture=capture, method="iteration")
    before = sys.getprofile(), sys.gettrace()
    with pytest.raises(reference.ReferenceRejected) as caught:
        with reference.observed(observer):
            probe((0, 1), buffer, history)
    assert caught.value.__cause__ is capture and capture.__cause__.args == ("capture cause",)
    assert history == [0] and len(rows) == 1
    assert rows[0]["buffer"] is buffer and rows[0]["bytes"] == buffer.tobytes()
    assert buffer.tolist() == [7.0, 0.0]
    assert observer.state.capture_error is capture
    assert observer.state.raw["synthetic_iteration"]["frame"].f_lineno == observer.loop_line
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    software.snapshot.write_json(
        tmp_path / "boundary-retention.json",
        dict(
            completed_synthetic_bodies=history,
            retained_bytes=buffer.tobytes().hex(),
            observation_line=observer.loop_line,
            original_native_bodies_executed=0,
        ),
    )


def test_reference_boundary_unchanged_synthetic_loop_completes_without_error(tmp_path):
    probe, _ = _loop(tmp_path)
    buffer = _bits()
    history = []
    observer, rows = _observer(tmp_path, method="iteration")
    with reference.observed(observer):
        probe((0, 1), buffer, history)
    assert history == [0, 1] and [row["t"] for row in rows] == [0, 1]
    assert buffer.tolist() == [8.0, 0.0] and observer.state.capture_error is None
    assert observer.state.hooks_restored


def test_reference_boundary_return_capture_stops_same_line_C_mutation(tmp_path):
    functions, _ = _code(
        RETURN_PROBE,
        tmp_path / "metadata_return.py",
    )
    buffer = _bits()
    before_bytes = buffer.tobytes()
    capture = OSError("normal-return observation failure")
    observer, _ = _observer(tmp_path, capture=capture, method="return")
    required = sys.getprofile(), sys.gettrace()
    with pytest.raises(reference.ReferenceRejected) as caught:
        with reference.observed(observer):
            functions["metadata_outer"](buffer)
    assert caught.value.__cause__ is capture and buffer.tobytes() == before_bytes
    boundary = observer.state.raw["blocked_native_boundary"]
    assert boundary["event"] == "c_call" and boundary["body_entered"] is False
    assert boundary["frame"].f_code is functions["metadata_outer"].__code__
    assert boundary["callable"].__self__ is buffer
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]


@pytest.mark.parametrize("error_type", [ValueError, FalseySourceError])
def test_reference_boundary_source_unwind_beats_capture_before_finally_mutation(
    tmp_path, error_type
):
    functions, _ = _code(
        UNWIND_PROBE,
        tmp_path / "metadata_unwind.py",
    )
    primary = error_type("original source primary")
    cause = KeyError("original cause")
    primary.__cause__ = cause
    capture = OSError("unwind observation failure")
    buffer = _bits()
    original = buffer.tobytes()
    observer, _ = _observer(tmp_path, capture=capture, method="return")
    required = sys.getprofile(), sys.gettrace()
    with pytest.raises(error_type) as caught:
        with reference.observed(observer):
            functions["metadata_outer"](buffer, primary)
    assert caught.value is primary and primary.__cause__ is cause
    assert observer.state.primary is primary and observer.state.capture_error is capture
    assert buffer.tobytes() == original
    assert observer.state.raw["blocked_native_boundary"]["body_entered"] is False
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]


@pytest.mark.parametrize("error_type", [ValueError, FalseySourceError])
def test_reference_boundary_ordinary_source_finally_is_unchanged_without_capture(
    tmp_path, error_type
):
    functions, _ = _code(
        UNWIND_PROBE,
        tmp_path / "metadata_normal_unwind.py",
    )
    primary = error_type("ordinary source failure")
    cause = KeyError("ordinary cause")
    primary.__cause__ = cause
    buffer = _bits()
    observer, _ = _observer(tmp_path, method="return")
    with pytest.raises(error_type) as caught:
        with reference.observed(observer):
            functions["metadata_outer"](buffer, primary)
    assert caught.value is primary and primary.__cause__ is cause
    assert buffer.tolist() == [0.0, 0.0] and observer.state.capture_error is None
    assert observer.state.hooks_restored


@pytest.mark.parametrize("first", ["primary", "capture", "unwind"])
def test_reference_boundary_line_guard_precedes_inherited_observer(tmp_path, monkeypatch, first):
    seen = []

    def previous(frame, event, arg):
        seen.append(event)
        return previous

    fake = SimpleNamespace(
        getprofile=lambda: None,
        gettrace=lambda: previous,
        setprofile=lambda value: None,
        settrace=lambda value: None,
    )
    monkeypatch.setattr(reference, "sys", fake)
    observer, _ = _observer(tmp_path)
    observer.install()
    primary = FalseySourceError("source primary")
    primary.__cause__ = KeyError("source cause")
    capture = OSError("capture error")
    if first == "primary":
        observer.state.primary = primary
    elif first == "capture":
        observer.state.capture_error = capture
    else:
        observer.state.capture_error = capture
        observer.state.native_unwind = primary
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_filename=str(tmp_path / "probe.py"), co_name="metadata"),
        f_globals={"__name__": "tests.synthetic_boundary_metadata"},
        f_locals={},
        f_lineno=1,
    )
    with pytest.raises((reference.ReferenceRejected, FalseySourceError)) as caught:
        observer.trace(frame, "line", None)
    assert seen == [] and observer.state.raw["blocked_native_boundary"]["frame"] is frame
    if first != "capture":
        assert caught.value is primary and caught.value.__cause__ is primary.__cause__


def test_reference_boundary_probe_C_reset_is_nonvacuous_without_observer(tmp_path):
    functions, _ = _code(
        RETURN_PROBE,
        tmp_path / "metadata_control.py",
    )
    buffer = _bits()
    original = buffer.tobytes()
    functions["metadata_outer"](buffer)
    assert buffer.tobytes() != original and buffer.tolist() == [0.0, 0.0]


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("unwind", [False, True])
def test_reference_boundary_inherited_return_rejection_stops_C_mutation(tmp_path, hook, unwind):
    functions, _ = _code(
        UNWIND_PROBE if unwind else RETURN_PROBE, tmp_path / "metadata_inherited.py"
    )
    primary = FalseySourceError("original source primary")
    primary.__cause__ = KeyError("original source cause")
    capture = OSError("inherited return rejection")
    buffer = _bits()
    raw = buffer.tobytes()
    observer, _ = _observer(tmp_path)
    old_profile, old_trace = sys.getprofile(), sys.gettrace()
    rejected = []

    def inherited(frame, event, arg):
        previous = old_profile if hook == "profile" else old_trace
        result = previous(frame, event, arg) if previous is not None else None
        if (
            not rejected
            and event == "return"
            and frame.f_code is functions["metadata_helper"].__code__
        ):
            rejected.append(frame)
            raise capture
        return result if hook == "profile" else inherited

    try:
        (sys.setprofile if hook == "profile" else sys.settrace)(inherited)
        required = sys.getprofile(), sys.gettrace()
        with pytest.raises(FalseySourceError if unwind else reference.ReferenceRejected) as caught:
            with reference.observed(observer):
                if unwind:
                    functions["metadata_outer"](buffer, primary)
                else:
                    functions["metadata_outer"](buffer)
        assert rejected and buffer.tobytes() == raw
        assert observer.state.capture_error is capture and observer.state.hooks_restored
        if unwind:
            assert caught.value is primary and primary.__cause__.args == ("original source cause",)
        else:
            assert caught.value.__cause__ is capture
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    finally:
        sys.setprofile(old_profile)
        sys.settrace(old_trace)
