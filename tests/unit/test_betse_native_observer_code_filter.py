"""Actual observer definitions in isolated metadata namespaces, never owners.

The shared runner blocks production, native and numerical imports. These
controllers exercise hook routing, work/capture retention and failure order;
their explicit metadata admission seams confer no scientific authority.
"""

import ast
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_betse_native_observer_dispatch_cost as helpers

ROOT = Path(__file__).resolve().parents[2]
SOURCES = {
    "handler": "src/cells/processes/betse_native_tissue_handler_attachment.py",
    "dyna": "src/cells/processes/betse_native_phase_dyna.py",
    "prefix": "src/cells/processes/betse_native_seed_world_prefix.py",
}
HOOKS = (("handler", "profile"), ("dyna", "profile"), ("prefix", "profile"), ("prefix", "trace"))


def _definition(role, namespace, root=ROOT):
    node = next(
        node
        for node in ast.parse((root / SOURCES[role]).read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "_account"
    )
    exec(
        compile(ast.Module(body=[node], type_ignores=[]), "observer_code_metadata:" + role, "exec"),
        namespace,
    )
    return namespace["_account"]


def _same(left, right):
    assert left == right


def controller(role, body, *, system=sys, root=ROOT):
    """No phase, parameter, caller, claim or issuance registry is constructed."""
    context = NS(
        stage="observer_metadata",
        work=[],
        locals={},
        states=[],
        raw_errors=[],
        timeline=[],
        observation_error=None,
        observation_errors=(),
        capture_failures=(),
        capture_reporting_errors=(),
        entry_error=None,
        pending_source_error=None,
        invalid=False,
        live_ok=True,
        drift_error=helpers.FalseyError("metadata binding changed"),
        methods={"body": body},
        bodies={"body": body},
        body_codes={body.__code__: "body"},
        callback_codes=frozenset(),
        forbidden_callback_codes=set(),
        callback=object(),
        rand=object(),
        draw_active=False,
        admitted={},
        admitted_frames={},
        observer_bindings=(),
        admit_error=None,
    )

    def admit(actual, frame):
        assert actual is context
        actual.timeline.append(("admit", frame.f_code.co_name))
        if actual.admit_error is not None:
            raise actual.admit_error
        if frame.f_code is not actual.methods["body"].__code__:
            actual.entry_error = ValueError("Unclaimed equal-code metadata frame")
            raise actual.entry_error
        row = actual.admitted.setdefault(id(frame), dict(frame=frame, body_started=False))
        return row

    def capture(actual, frame, event):
        assert actual is context
        actual.states.append((event, dict(frame.f_locals)))

    namespace = dict(
        __name__="observer_code_metadata",
        contextmanager=contextmanager,
        FunctionType=FunctionType,
        sys=system,
        _NATIVE={"body": body},
        _ATTACH=helpers._unused,
        _acquire=helpers._unused,
        _namespace=helpers._unused,
        aliases=NS(NATIVE=helpers.NATIVE),
        captures=NS(_remember_observation_error=helpers._remember),
        _stop=helpers._stop,
        _guard=helpers._guard,
        _check=helpers._check,
        _admit=admit,
        _admit_body=admit,
        _capture=capture,
        _capture_failure=helpers._remember,
        _observer_bindings=lambda: (),
        literal=NS(_same=_same, _CaptureStop=helpers.CaptureStop),
        _epoch=lambda actual: (),
        _same_epoch=lambda actual, old: _same((), old),
        _callback_return=lambda *args: None,
        _callback_receiver=lambda frame: frame.f_locals.get("self"),
        _Random=NS(rand=helpers._unused),
    )

    def reject(actual, unused, reason):
        assert actual is context
        actual.entry_error = ValueError(reason)
        raise actual.entry_error

    namespace["_reject"] = reject
    # Prefix's reporter accepts positional origin/raw; the helper's interface
    # is keyword-only. This adapter observes errors only, not source permission.
    namespace["_capture_failure"] = lambda actual, error, origin, raw: helpers._remember(
        actual, error, origin=origin, raw=raw
    )
    handler_space = dict(namespace)
    handler_space["_account"] = _definition("handler", handler_space, root)
    namespace["handler"] = NS(**handler_space)
    return _definition(role, namespace, root), context


@pytest.fixture
def evidence(tmp_path):
    value = dict(metadata_only=True, actual_owner_or_source_credit=False)
    yield value
    (tmp_path / "observer-control.json").write_text(json.dumps(value, indent=2, sort_keys=True))


@pytest.mark.parametrize(("role", "hook"), HOOKS)
@pytest.mark.parametrize(
    "event", ("call", "line", "return", "exception", "c_call", "c_return", "c_exception")
)
def test_unrelated_code_is_not_hashed_and_inherited_events_are_kept(role, hook, event, evidence):
    seen = []

    def inherited(frame, kind, value):
        seen.append((frame, kind, value))
        return inherited

    system = helpers.HookSlots(inherited)
    system.trace = inherited
    body = helpers._body()
    account, context = controller(role, body, system=system)

    class UnrelatedCode:
        co_name = "_metadata_tree"
        co_qualname = "_metadata_tree"
        co_filename = "metadata-only"

        def __hash__(self):
            raise AssertionError("Unrelated code must not be hashed")

    frame, value = NS(f_code=UnrelatedCode(), f_locals={}), object()
    with account(context):
        if hook == "trace" and event != "call":
            system.trace(frame, "call", None)
            seen.clear()
        getattr(system, hook)(frame, event, value)
    assert seen == [(frame, event, value)]
    assert not context.work and not context.locals and not context.admitted
    assert system.profile is inherited and system.trace is inherited
    evidence.update(role=role, hook=hook, event=event, code_hashes=0, inherited_events=1)


@pytest.mark.parametrize(("role", "hook"), HOOKS)
def test_matching_name_still_performs_full_membership_and_restores_hooks(role, hook, evidence):
    body = helpers._body()
    account, context = controller(role, body)
    primary = helpers.FalseyError("selected code hash error")
    primary.__cause__ = LookupError("original cause")

    class MatchingCode:
        co_name = body.__code__.co_name
        co_filename = "metadata-only"

        def __hash__(self):
            raise primary

    before = sys.getprofile(), sys.gettrace()
    with pytest.raises(helpers.FalseyError) as caught:
        with account(context):
            callback = sys.getprofile() if hook == "profile" else sys.gettrace()
            callback(NS(f_code=MatchingCode()), "call", None)
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    assert not context.admitted
    evidence.update(role=role, hook=hook, original_primary_and_cause=True, hooks_restored=True)


@pytest.mark.parametrize("role", tuple(SOURCES))
@pytest.mark.parametrize(
    "scenario", ("success", "source", "prior_call", "prior_return", "unwind_capture")
)
def test_real_hook_delivery_preserves_work_source_and_capture_failures(role, scenario, evidence):
    body = helpers._body()
    account, context = controller(role, body)
    primary, secondary = helpers.FalseyError("source"), helpers.FalseyError("observer")
    primary.__cause__, secondary.__cause__ = (
        LookupError("source cause"),
        LookupError("observer cause"),
    )
    source = primary if scenario in ("source", "unwind_capture") else None
    reject = (
        ("profile", "call" if scenario == "prior_call" else "return")
        if scenario in ("prior_call", "prior_return", "unwind_capture")
        else None
    )
    caught = value = None
    before = sys.getprofile(), sys.gettrace()
    with helpers._inherited_hooks(body, context, reject=reject, error=secondary) as installed:
        try:
            with account(context):
                value = body(source)
        except BaseException as error:
            caught = error
        assert sys.getprofile() is installed[0] and sys.gettrace() is installed[1]
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    if scenario == "success":
        assert caught is None and value == 29
        assert body.__globals__["entered"] == ["body"]
    elif scenario in ("source", "unwind_capture"):
        assert caught is primary and caught.__cause__ is primary.__cause__
    elif scenario == "prior_call":
        assert caught is secondary and not body.__globals__["entered"]
    else:
        assert isinstance(caught, helpers.CaptureStop)
    if scenario in ("prior_return", "unwind_capture"):
        assert context.observation_error is secondary
        assert any(error is secondary for error, raw in context.raw_errors)
    if scenario != "prior_call":
        assert context.work if role != "prefix" else context.states
    evidence.update(
        role=role,
        scenario=scenario,
        hooks_restored=True,
        original_cause_retained=True,
        raw_secondary_retained=scenario in ("prior_return", "unwind_capture"),
    )


@pytest.mark.parametrize("role", tuple(SOURCES))
def test_equal_code_different_filename_cannot_evade_selected_observation(role, evidence):
    body = helpers._body()
    account, context = controller(role, body)
    clone = FunctionType(
        body.__code__.replace(co_filename="another-metadata-path"),
        body.__globals__,
        argdefs=body.__defaults__,
    )
    assert clone.__code__ == body.__code__ and clone.__code__ is not body.__code__
    before = sys.getprofile(), sys.gettrace()
    if role == "handler":
        with account(context):
            assert clone() == 29
        assert len(context.work) == 1 and context.locals
    else:
        with pytest.raises(ValueError, match="Unclaimed equal-code"):
            with account(context):
                clone()
        assert not body.__globals__["entered"] and context.entry_error is not None
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    evidence.update(role=role, equal_code_observed=True, filename_not_used_as_equality_filter=True)


def test_handler_still_observes_unselected_native_descendant_filename(evidence):
    body = helpers._body(native=True)
    account, context = controller("handler", helpers._body())
    with account(context):
        assert body() == 29
    assert len(context.work) == 1
    assert context.locals[(body.__code__.co_filename, body.__code__.co_qualname)]["local"] == 17
    evidence.update(native_filename_is_synthetic=True, selected_names_do_not_drop_descendants=True)


def test_dyna_live_method_retarget_is_not_hidden_by_saved_names(evidence):
    original, replacement = helpers._body(), helpers._body(native=True)
    account, context = controller("dyna", original)
    primary = ValueError("live method retarget")
    before = sys.getprofile(), sys.gettrace()
    with pytest.raises(ValueError) as caught:
        with account(context):
            context.methods["body"] = replacement
            context.admit_error = primary
            replacement()
    assert caught.value is primary and replacement.__globals__["entered"] == []
    assert context.timeline[-1] == ("admit", replacement.__code__.co_name)
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    evidence.update(dynamic_method_identity_path_retained=True, replacement_body_calls=0)


def test_prefix_live_forbidden_callback_roster_still_refuses(evidence):
    body, callback = helpers._body(), helpers._body(native=True)
    system = helpers.HookSlots(None)
    account, context = controller("prefix", body, system=system)
    with pytest.raises(ValueError, match="Unselected native callback entry"):
        with account(context):
            # Mutate after names are prepared: forbidden callbacks must remain live.
            context.forbidden_callback_codes.add(callback.__code__)
            system.profile(
                NS(f_code=callback.__code__, f_locals={"self": context.callback}), "call", None
            )
    assert context.entry_error is not None and not callback.__globals__["entered"]
    assert system.profile is None and system.trace is None
    evidence.update(live_forbidden_roster_checked=True, callback_body_calls=0)


@pytest.mark.parametrize("role", ("dyna", "prefix"))
@pytest.mark.parametrize("mode", ("drift", "reentry"))
def test_selected_inherited_callback_cannot_bypass_fresh_admission(role, mode, evidence):
    body = helpers._body()
    account, context = controller(role, body)
    before = sys.getprofile(), sys.gettrace()
    primary = ValueError("caught reentry remains poisoned")
    entered = []

    def inherited(frame, event, arg):
        if before[0] is not None:
            before[0](frame, event, arg)
        if event == "call" and frame.f_code is body.__code__ and not entered:
            entered.append(True)
            context.live_ok = False
            context.drift_error = primary
            if mode == "reentry":
                context.admit_error = primary
                with pytest.raises(ValueError) as caught:
                    # Explicit rejected hook entry: Python suspends profiling
                    # inside an inherited profiler. No source-wrapper authority
                    # or actual recursively profiled execution is claimed here.
                    sys.getprofile()(NS(f_code=body.__code__), "call", None)
                assert caught.value is primary

    try:
        sys.setprofile(inherited)
        with pytest.raises(ValueError) as caught:
            with account(context):
                body()
        assert caught.value is primary and body.__globals__["entered"] == []
        assert sys.getprofile() is inherited
    finally:
        sys.setprofile(before[0])
        sys.settrace(before[1])
    evidence.update(role=role, mode=mode, no_delegate_after_mutation=True)
