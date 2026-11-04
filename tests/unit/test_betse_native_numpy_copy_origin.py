"""Stdlib observer controls and one actual fresh NumPy definition import.

Synthetic frames exercise refusal/retention only. They do not issue an origin
token. The final test observes the real pinned import without calling copy,
its argument dispatcher, array operators, solvers or RNG as a probe.
"""

import gc
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from cells.processes import betse_native_numpy_copy_origin as original


class Falsey(BaseException):
    def __bool__(self):
        return False

    def __str__(self):
        raise AssertionError("Original errors must not be rendered in a hook gap")


@pytest.fixture
def api(request):
    # Isolate one-shot metadata state. No NumPy module is created, removed or
    # reloaded by this fixture, and no synthetic session can reach the real API.
    module = ModuleType("_isolated_numpy_copy_origin")
    module.__file__ = original.__file__
    exec(compile(Path(original.__file__).read_bytes(), original.__file__, "exec"), vars(module))
    yield module
    target = os.environ.get("CELLS_NUMPY_COPY_ORIGIN_EVIDENCE")
    if target:
        path = Path(target) / (hashlib.sha256(request.node.nodeid.encode()).hexdigest() + ".json")
        path.write_text(json.dumps(module.record(), indent=2) + "\n")


def test_record_is_metadata_not_authority(api):
    assert api.record() == dict(
        kind="cells.original_numpy_copy_import_origin@1",
        completed=False,
        hooks_restored=False,
        source_error=None,
        capture_errors=[],
        cleanup_errors=[],
        source_files={},
    )
    with pytest.raises(api.OriginRejected, match="No original"):
        api.require_copy(object(), object(), object())
    with pytest.raises(TypeError):
        api.capture(api.record())


@pytest.mark.parametrize("name", ["numpy", "numpy.incomplete"])
def test_existing_or_incomplete_numpy_refuses_before_hook_setup(api, monkeypatch, name):
    before = sys.getprofile(), sys.gettrace()
    monkeypatch.setitem(sys.modules, name, ModuleType(name))
    with pytest.raises(api.OriginRejected, match="precede every"):
        with api.capture():
            pytest.fail("Existing NumPy cannot be witnessed retrospectively")
    assert (sys.getprofile(), sys.gettrace()) == before
    assert api.record()["completed"] is False


def test_caught_reentry_irreversibly_poisoned(api):
    session = api.capture()
    with pytest.raises(api.OriginRejected, match="reentry"):
        api.capture()
    with pytest.raises(api.OriginRejected, match="One-shot"):
        session.__enter__()
    assert session.invalid and not api.record()["completed"]
    with pytest.raises(TypeError, match="hydrated"):
        pickle.dumps(session)


def test_incomplete_capture_chains_local_trace_and_restores_both(api):
    previous, trace = sys.getprofile(), sys.gettrace()
    seen = []

    def marker():
        return "metadata"

    def local(frame, event, arg):
        if frame.f_code is marker.__code__:
            seen.append(("local", event))
        return local

    def traced(frame, event, arg):
        inherited = trace(frame, event, arg) if trace is not None else None
        if frame.f_code is marker.__code__:
            seen.append(("trace", event))
            return local
        return inherited

    def profiled(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if frame.f_code is marker.__code__:
            seen.append(("profile", event))

    try:
        sys.setprofile(profiled)
        sys.settrace(traced)
        with pytest.raises(api.OriginRejected, match="No complete"):
            with api.capture():
                assert marker() == "metadata"
        assert sys.getprofile() is profiled and sys.gettrace() is traced
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
    assert ("profile", "call") in seen and ("profile", "return") in seen
    assert ("trace", "call") in seen and ("local", "line") in seen and ("local", "return") in seen
    assert api.record()["hooks_restored"] and not api.record()["completed"]


@pytest.mark.parametrize("which", ["profile", "trace"])
def test_actual_inherited_entry_rejection_preserves_falsey_primary(api, which):
    previous, trace = sys.getprofile(), sys.gettrace()
    error, cause = Falsey(), KeyError("original cause")
    error.__cause__ = cause
    armed = True

    def marker():
        pytest.fail("Inherited entry rejection must precede the delegate")

    def guarded(frame, event, arg):
        nonlocal armed
        prior = previous if which == "profile" else trace
        result = prior(frame, event, arg) if prior is not None else None
        if armed and event == "call" and frame.f_code is marker.__code__:
            armed = False
            raise error
        return guarded if which == "trace" else result

    try:
        (sys.setprofile if which == "profile" else sys.settrace)(guarded)
        with pytest.raises(Falsey) as caught:
            with api.capture():
                marker()
        assert caught.value is error and error.__cause__ is cause
        assert sys.getprofile() is (guarded if which == "profile" else previous)
        assert sys.gettrace() is (guarded if which == "trace" else trace)
    finally:
        armed = False
        sys.setprofile(previous)
        sys.settrace(trace)
    assert any(row["error"]["id"] == id(error) for row in api.record()["capture_errors"])
    assert api.record()["source_error"] is None
    assert api.record()["scope_error"]["id"] == id(error)


def test_local_none_keeps_inherited_trace_until_later_refusal(api):
    before = sys.getprofile(), sys.gettrace()
    rejected = Falsey()
    seen = []

    def marker():
        value = 1
        return value

    def local(frame, event, arg):
        seen.append(event)
        if event == "return":
            raise rejected
        return None

    def traced(frame, event, arg):
        inherited = before[1](frame, event, arg) if before[1] is not None else None
        return local if frame.f_code is marker.__code__ else inherited

    try:
        sys.settrace(traced)
        with pytest.raises(Falsey) as caught:
            with api.capture():
                marker()
        assert caught.value is rejected
        assert sys.getprofile() is before[0] and sys.gettrace() is traced
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert seen == ["line", "line", "return"]
    assert api.record()["last_capture_error"]["error"]["id"] == id(rejected)


@pytest.mark.parametrize("reject_capture", [False, True])
def test_exception_event_retains_interrupted_source_and_secondary_capture_entry(
    api, reject_capture
):
    before = sys.getprofile(), sys.gettrace()
    source, observer, secondary, cause = Falsey(), Falsey(), Falsey(), KeyError("raw source cause")
    source.__cause__ = cause
    holder, seen = {}, []

    def source_call():
        holder["session"].root_frame = sys._getframe()
        raise source

    def traced(frame, event, arg):
        if before[1] is not None:
            before[1](frame, event, arg)
        if (
            frame.f_code is source_call.__code__ or frame is holder.get("direct_frame")
        ) and event == "exception":
            seen.append("source_exception")
            raise observer
        return traced

    def profiled(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if (
            reject_capture
            and event == "call"
            and frame.f_code is api._Observation._capture.__code__
            and frame.f_locals.get("stage") == "inherited_trace"
        ):
            seen.append("capture_entry")
            raise secondary

    try:
        sys.setprofile(profiled)
        sys.settrace(traced)
        with pytest.raises(Falsey) as caught:
            with api.capture() as session:
                holder["session"] = session
                if reject_capture:
                    # A callback suppresses recursive profiling in this
                    # interpreter. Exercise the same exception-event entry
                    # directly with an actual metadata frame so the installed
                    # other hook can reject _capture before its body.
                    frame = sys._getframe()
                    holder["direct_frame"] = session.root_frame = frame
                    session.trace_delegates[frame] = traced
                    session._trace(frame, "exception", (type(source), source, None))
                else:
                    source_call()
        assert caught.value is observer
        assert sys.getprofile() is profiled and sys.gettrace() is traced
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    result = api.record()
    assert result["source_error"] is None and not result["completed"]
    assert session.interrupted_source_error is source and source.__cause__ is cause
    assert result["interrupted_source_error"]["id"] == id(source)
    assert result["interrupted_source_cause"]["id"] == id(cause)
    assert not result["interrupted_exception_is_completed_unwind"]
    assert result["last_capture_error"]["error"]["id"] == id(observer)
    assert seen == (
        ["source_exception", "capture_entry"] if reject_capture else ["source_exception"]
    )
    if reject_capture:
        assert result["capture_entry_error"]["error"]["id"] == id(secondary)


def test_profile_capture_entry_rejection_retains_first_error(api):
    # Exercise the profile boundary under a real other-hook entry refusal.
    # This isolated metadata session never claims an imported construction.
    before = sys.getprofile(), sys.gettrace()
    first, secondary = Falsey(), Falsey()
    session = api._Observation()
    seen = []

    def inherited(frame, event, arg):
        raise first

    def traced(frame, event, arg):
        result = before[1](frame, event, arg) if before[1] is not None else None
        if frame.f_code is api._Observation._capture.__code__ and event == "call":
            seen.append("entry")
            raise secondary
        return result

    session.previous = (inherited, None)
    try:
        sys.settrace(traced)
        with pytest.raises(Falsey) as caught:
            session._profile(sys._getframe(), "call", None)
        assert caught.value is first
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    assert seen == ["entry"]
    assert session.last_capture_error == ("inherited_profile", first)
    assert session.capture_entry_error == ("inherited_profile", secondary)
    assert session.invalid and not session.completed


@pytest.mark.parametrize("failure", ["restore_entry", "trace_setter"])
def test_cleanup_entry_or_setter_rejection_attempts_both_hooks_without_rendering(api, failure):
    previous, trace = sys.getprofile(), sys.gettrace()
    primary, cause, cleanup = Falsey(), LookupError("cause"), Falsey()
    primary.__cause__ = cause
    armed = False
    seen = []

    def guarded(frame, event, arg):
        nonlocal armed
        if previous is not None:
            previous(frame, event, arg)
        entry = event == "call" and frame.f_code is api._Observation._restore.__code__
        setter = event == "c_call" and arg is sys.settrace
        if armed and (entry if failure == "restore_entry" else setter):
            armed = False
            seen.append("rejected")
            raise cleanup

    try:
        sys.setprofile(guarded)
        with pytest.raises(Falsey) as caught:
            with api.capture():
                armed = True
                raise primary
        assert caught.value is primary and primary.__cause__ is cause
        assert sys.getprofile() is guarded and sys.gettrace() is trace
    finally:
        armed = False
        sys.setprofile(previous)
        sys.settrace(trace)
    record = api.record()
    assert seen == ["rejected"] and record["hooks_restored"] and not record["completed"]
    assert record["source_error"] is None
    assert record["scope_error"]["id"] == id(primary)
    assert any(row["error"]["id"] == id(cleanup) for row in record["cleanup_errors"])


def test_own_baseexception_during_unwind_does_not_replace_raw_source(api):
    source, capture, cause = Falsey(), Falsey(), KeyError("cause")
    source.__cause__ = cause
    session = api._Observation()
    session.previous, session.hooks = (None, None), (None, None)
    session.owns_hooks = True
    session.source_error = source

    def observe(*args):
        raise capture

    session._observe = observe
    session._opcode_scope = lambda *args: None
    frame = SimpleNamespace(f_code=observe.__code__)
    api.FrameType, api._FRAME = type(frame), lambda depth: frame
    with pytest.raises(Falsey) as caught:
        session._trace(frame, "call", None)
    assert caught.value is source and source.__cause__ is cause
    assert session.capture_errors == [("observation", capture)]


def test_constructor_assignment_is_retained_before_inherited_callback(api):
    session = api._Observation()
    original_return, replacement = object(), object()

    class Frame:
        f_lasti = 42
        f_locals = {"public_api": original_return}

    frame = Frame()
    session.decorator_frame = frame
    session.after_assignment = 42
    session.hooks = (None, None)
    session.owns_hooks = True

    def inherited(*args):
        frame.f_locals["public_api"] = replacement
        return inherited

    def inspect(*args):
        assert session.assignment_raw is original_return
        api._require(frame.f_locals["public_api"] is session.assignment_raw, "return replaced")

    session.previous = (None, inherited)
    session.trace_delegates[frame] = inherited
    session._observe = inspect
    api.FrameType, api._FRAME = type(frame), lambda depth: frame
    with pytest.raises(api.OriginRejected, match="return replaced"):
        session._trace(frame, "opcode", None)
    assert session.invalid and session.assignment_raw is original_return


@pytest.mark.parametrize(
    "mutation", ["code", "defaults", "global", "builtins", "closure", "kwdefaults"]
)
def test_live_function_atoms_detect_resolved_mutation_without_calling_helper(api, mutation):
    namespace = {"__builtins__": dict(vars(__import__("builtins"))), "delegate": object()}
    exec("def helper(a=1, *, k=2):\n return delegate(a)\n", namespace)
    function = namespace["helper"]
    if mutation == "closure":

        def factory():
            held = object()

            def closure():
                return held

            return closure

        function = factory()
    before = api._function_atoms(function)
    if mutation == "code":
        function.__code__ = function.__code__.replace(co_name="foreign")
    elif mutation == "defaults":
        function.__defaults__ = tuple([1])
    elif mutation == "global":
        namespace["delegate"] = object()
    elif mutation == "builtins":
        namespace["__builtins__"]["delegate"] = object()
    elif mutation == "closure":
        function.__closure__[0].cell_contents = object()
    else:
        function.__kwdefaults__["k"] = 3
    assert not api._same(before, api._function_atoms(function))


@pytest.mark.parametrize("left,right", [(True, 1), (False, 0), (0.0, -0.0), ((True,), (1,))])
def test_code_and_constant_comparison_preserves_typed_bits(api, left, right):
    assert api._constant(left) != api._constant(right)
    code = compile("value = None", "original.py", "exec")
    a = code.replace(co_consts=(left, None))
    b = code.replace(co_consts=(right, None))
    assert api._code(a) != api._code(b)


def test_opaque_or_python_dispatcher_type_is_not_original(api):
    class Pretender:
        _implementation = property(lambda self: None)

    with pytest.raises(api.OriginRejected, match="immutable non-heap"):
        api._class(Pretender)


@pytest.mark.parametrize("mutation", ["source_pin", "digest_delegate"])
def test_source_and_record_pin_drift_refuse_before_import(api, monkeypatch, mutation):
    if mutation == "source_pin":
        monkeypatch.setitem(api.PINS, api.RECORD, "0" * 64)
    else:
        monkeypatch.setattr(api, "_digest", lambda path: "0" * 64)
    with pytest.raises(api.OriginRejected, match="Origin"):
        with api.capture():
            pytest.fail("Changed producer must not reach import")
    assert not any(name == "numpy" or name.startswith("numpy.") for name in sys.modules)


def test_event_journal_bound_refuses_without_issuing_authority(api):
    session = api._Observation()
    session.events = [None] * api.MAX_EVENTS
    with pytest.raises(api.OriginRejected, match="Bounded"):
        session._event("overflow")
    assert len(session.events) == api.MAX_EVENTS and not session.completed


def test_forged_completed_flag_and_supplied_objects_cannot_supply_exports(api):
    session = api.capture()
    session.completed = session.hooks_restored = True
    values = object(), object(), object()
    with pytest.raises(api.OriginRejected, match="not the observed"):
        api.require_copy(*values)
    assert session.invalid and not api.record()["completed"]


@pytest.mark.parametrize(
    "mutation",
    [
        "session",
        "method",
        "instance_method",
        "method_code",
        "helper",
        "helper_code",
        "helper_default",
        "helper_global",
        "validator",
        "validator_code",
        "class_slot",
    ],
)
def test_issued_session_and_live_api_atoms_refuse_retargeting(api, monkeypatch, mutation):
    session = api.capture()
    entries = []

    def forbidden(*args, **kwargs):
        entries.append("forged delegate")
        return session.token

    if mutation == "session":
        monkeypatch.setattr(api, "_SESSION", api._Observation())
    elif mutation == "method":
        monkeypatch.setattr(api._Observation, "require", forbidden)
    elif mutation == "instance_method":
        monkeypatch.setattr(session, "require", forbidden)
    elif mutation == "method_code":
        code = (lambda self, value, core, argument: None).__code__
        monkeypatch.setattr(api._Observation.require, "__code__", code)
    elif mutation == "helper":
        monkeypatch.setattr(api, "_require", forbidden)
    elif mutation == "helper_code":
        monkeypatch.setattr(api._files, "__code__", (lambda: {}).__code__)
    elif mutation == "helper_default":
        monkeypatch.setattr(api._files, "__defaults__", (None,))
    elif mutation == "helper_global":
        monkeypatch.setattr(api, "SITE", Path("/tmp/foreign-numpy-origin"))
    elif mutation == "validator":
        monkeypatch.setattr(api, "_api_check", forbidden)
    elif mutation == "validator_code":
        monkeypatch.setattr(api._api_check, "__code__", (lambda session=None: None).__code__)
    else:
        monkeypatch.setattr(api._Observation, "new_slot", forbidden, raising=False)
    with pytest.raises(api.OriginRejected):
        api.require_copy(object(), object(), object())
    assert entries == [] and not session.completed


def test_actual_fresh_numpy_import_observes_constructor_without_probe(monkeypatch):
    # This is the one actual library-definition import, after all isolated
    # metadata cases. No numerical operation is used to validate the witness.
    assert not any(name == "numpy" or name.startswith("numpy.") for name in sys.modules)
    before = sys.getprofile(), sys.gettrace()
    downstream, cause = Falsey(), KeyError("downstream demo source cause")
    downstream.__cause__ = cause
    with pytest.raises(Falsey) as caught:
        with original.capture() as observation:
            import numpy as np

            module = sys.modules["numpy.lib._function_base_impl"]
            core = object.__getattribute__(np.copy, "_implementation")
            argument = vars(module)["_copy_dispatcher"]
            token = original.require_copy(np.copy, core, argument)
            assert token is original.require_copy(np.copy, core, argument)
            assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
            assert (
                observation.value is np.copy
                and observation.core is core
                and observation.argument is argument
            )
            raise downstream
    assert caught.value is downstream and downstream.__cause__ is cause
    result = original.record()
    assert result["completed"] and result["hooks_restored"]
    assert (
        result["source_error"] is None
        and result["capture_errors"] == result["cleanup_errors"] == []
    )
    assert result["scope_error"]["id"] == id(downstream)
    assert result["numerical_probe_calls"] == 0
    assert 0 < result["constructor_opcode_events"] <= original.MAX_EVENTS
    assert result["primed_code_frames"] > 2
    assert result["constructor_opcode_events"] <= result["import_opcode_events"]
    assert [row["name"] for row in result["events"]] == [
        "numpy_enter",
        "factory_enter",
        "factory_return",
        "decorator_enter",
        "constructor_call",
        "constructor_assignment",
        "decorator_return",
        "module_copy_assignment",
        "numpy_return",
    ]
    output = os.environ.get("CELLS_NUMPY_COPY_ORIGIN_EVIDENCE")
    if output:
        (Path(output) / "actual-import-origin.json").write_text(json.dumps(result, indent=2) + "\n")
    from cells.processes import betse_native_parameter_colormap_runtime as consumer

    with monkeypatch.context() as adoption:
        # Test-only adoption of these exact frozen producer bytes;
        # production remains held and no token/object is substituted.
        adoption.setattr(
            consumer,
            "ORIGIN_SOURCE_SHA256",
            hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(),
        )
        selected, bindings, edges = consumer._copy_delegates(np.copy, core, module)
        reference = consumer.inspect_reference()
        full = consumer._numpy_copy(np, reference)
    integration = dict(
        consumer_sha256=hashlib.sha256(Path(consumer.__file__).read_bytes()).hexdigest(),
        origin_sha256=hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(),
        gc_tracked=gc.is_tracked(np.copy),
        gc_direct_references=len(gc.get_referents(np.copy)),
        argument=id(argument),
        core=id(core),
        token=id(token),
        returned=[id(item) for item in edges],
        bindings=len(bindings),
        full_returned=[id(full[i]) for i in (0, 1, 2)],
        full_edges=[id(item) for item in full[4]],
        verified_library_files=reference["verified_files"],
        numerical_probe_calls=0,
    )
    if output:
        (Path(output) / "actual-consumer-integration.json").write_text(
            json.dumps(integration, indent=2) + "\n"
        )
    assert selected is argument and bindings
    assert edges[0] is argument and edges[1] is core and edges[2] is token
    assert full[0] is np.copy and full[1] is core and full[2] is argument
    assert full[4][0] is argument and full[4][1] is core and full[4][2] is token
    assert integration["gc_tracked"] is False and integration["gc_direct_references"] == 0
    # A meaningful live-export drift witness uses the observed objects; no
    # second import, reset, supplied owner, numerical probe or new proof.
    with monkeypatch.context() as patch:
        patch.setattr(np, "copy", object())
        with pytest.raises(original.OriginRejected, match="exports changed"):
            observation._verify_exports()
    assert original.require_copy(np.copy, core, argument) is token
