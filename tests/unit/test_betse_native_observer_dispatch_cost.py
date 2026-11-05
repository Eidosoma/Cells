"""Isolated observer dispatch contracts; no production or native imports.

OLD_ACCOUNT contains the unchanged selected definition from each source SHA
in BASELINE. The oracle is not reconstructed from the candidate definition.
Both definitions are compiled into metadata-only namespaces during the guarded
software suite. Real profile/trace hooks cover delegation and restoration;
fake frames are confined to deterministic attribute-read counters.
"""

import ast
import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
NATIVE = Path("/synthetic-observer-native")

BASELINE = {
    "handler": (
        "betse_native_tissue_handler_attachment.py",
        "200c2cb87989a245afcc7f4acc3689c6422b2a5cc5f8ac77ab2f5891e1e31aa2",
        "c3c63068c7f11aa3185c37fa5acfcef53e1ccdb27d2f04c86e26972ea0d15790",
    ),
    "configuration": (
        "betse_native_tissue_configuration.py",
        "65959faa0352293d9af7e4fbab022fcfccd3dcc038e5cbd85ee3fce8b7b57ca4",
        "6dc2f96664e3c11343644761f71b71520d65d690cca3dbca025a731618b9c3ba",
    ),
    "tail": (
        "betse_native_phase_tail.py",
        "539ba4363317707d4731f102d20b67ed86ea4dc813cccac013314291641dcd42",
        "2a944df876213695e483be044930fcc8ef1273c5a7271619c6290e9a10d3f00e",
    ),
}

OLD_ACCOUNT = {
    "handler": r"""@contextmanager
def _account(context):
    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
    selected = {fn.__code__ for fn in (*_NATIVE.values(), _acquire, _namespace)}
    root = str(aliases.NATIVE) + "/"

    def profile(frame, event, arg):
        reached = frame.f_code in selected or frame.f_code.co_filename.startswith(root)
        if reached and event == "call":
            if len(context.work) >= 100000:
                raise ValueError("Bounded handler work log exhausted")
            context.work.append(
                dict(
                    sequence=len(context.work),
                    layer="observed_native_or_literal_entry",
                    phase=context.stage,
                    method=frame.f_code.co_qualname,
                    entry_is_case=False,
                )
            )
        if event in ("call", "c_call") and previous_profile is not None:
            previous_profile(frame, event, arg)
        if reached and event == "return":
            try:
                context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(
                    frame.f_locals
                )
            except Exception as error:
                captures._remember_observation_error(context, error, origin="raw_locals", raw=frame)
        if event not in ("call", "c_call") and previous_profile is not None:
            try:
                previous_profile(frame, event, arg)
            except Exception as error:
                captures._remember_observation_error(
                    context, error, origin="prior_profile_" + event, raw=(frame, event, arg)
                )

    sys.setprofile(profile)
    try:
        yield
        _stop(context)
    finally:
        sys.setprofile(previous_profile)
        sys.settrace(previous_trace)
""",
    "configuration": r'''@contextmanager
def _account(context):
    """One ordered work ledger; wrapper/body layers are not additive cases."""
    previous, trace = sys.getprofile(), sys.gettrace()
    native_root = str(aliases.NATIVE) + "/"
    selected = {
        f.__code__ for f in (*_NATIVE.values(), *_STORES.values(), _native_setup, _lazy_factory)
    }

    def profile(frame, event, arg):
        reached = frame.f_code.co_filename.startswith(native_root) or frame.f_code in selected
        if reached and event == "call":
            if len(context.work) >= 100000:
                raise ValueError("Bounded tissue work ledger exhausted")
            context.work.append(
                dict(
                    sequence=len(context.work),
                    layer="actual_native_body"
                    if frame.f_code.co_filename.startswith(native_root)
                    else "selected_source_body",
                    phase=context.stage,
                    method=frame.f_code.co_qualname,
                    source_file=frame.f_code.co_filename,
                    status="entered_not_success_credit",
                )
            )
        if (
            reached
            and event == "return"
            and (
                frame.f_code in selected
                or frame.f_code.co_name in ("__init__", "load", "make_list", "__get__", *_NATIVE)
            )
        ):
            try:
                context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(
                    frame.f_locals
                )
            except Exception as capture:
                captures._remember_observation_error(
                    context, capture, origin="raw_locals", raw=frame
                )
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
''',
    "tail": r"""@contextmanager
def _account(context):
    get_profile, get_trace = sys.getprofile, sys.gettrace
    set_profile, set_trace = sys.setprofile, sys.settrace
    prior_profile, prior_trace = get_profile(), get_trace()
    codes = {fn.__code__ for fn in context.bodies.values()}
    traces = {}
    frame_errors = {}
    primary, setup_stage = None, None
    context.hook_states = (("before", prior_profile, prior_trace),)
    context.hook_attempts = ()
    context.hook_secondary_errors = ()

    def remember(error, origin, raw):
        previous.handler.captures._remember_observation_error(
            context, error, origin=origin, raw=raw
        )

    def profile(frame, event, arg):
        selected = frame.f_code in codes
        if selected and event == "call":
            attempt = _admit_body(context, frame)
            attempt["hooks"] = (*attempt.get("hooks", ()), "profile")
            _guard(context)
            _check(context)
        if prior_profile is not None:
            if event in ("call", "c_call"):
                prior_profile(frame, event, arg)
            else:
                try:
                    prior_profile(frame, event, arg)
                except BaseException as error:
                    remember(error, "prior_profile_" + event, (frame, event, arg))
        if selected and event == "call":
            _guard(context)
            _check(context)

    def trace(frame, event, arg):
        selected = frame.f_code in codes
        if selected and event == "call":
            # Trace may be delivered before profile. Both share this exact
            # frame's reservation, before either inherited observer runs.
            attempt = _admit_body(context, frame)
            attempt["hooks"] = (*attempt.get("hooks", ()), "trace")
            _guard(context)
            _check(context)
        if selected and event == "exception":
            frame_errors[id(frame)] = arg[1]
            if context.pending_source_error is None and not (
                isinstance(arg[1], literal._CaptureStop) and context.observation_error is not None
            ):
                context.pending_source_error = arg[1]
        if selected and event in ("line", "return", "exception"):
            try:
                _capture_state(context, frame, event)
            except BaseException as error:
                remember(error, "tail_state_" + event, frame)
        if selected and event == "line":
            _guard(context)
            _check(context)
        delegate = prior_trace if event == "call" else traces.get(id(frame))
        if delegate is not None:
            if event in ("return", "exception"):
                try:
                    returned = delegate(frame, event, arg)
                    if returned is not None:
                        traces[id(frame)] = returned
                except BaseException as error:
                    remember(error, "prior_trace_" + event, (frame, event, arg))
            else:
                returned = delegate(frame, event, arg)
                if event == "call" or returned is not None:
                    traces[id(frame)] = returned
        if event == "call" and not selected and traces.get(id(frame)) is None:
            return None
        if event == "return":
            traces.pop(id(frame), None)
            if selected and id(frame) in context.admitted_frames:
                attempt = context.admitted_frames[id(frame)]
                status = "failed" if id(frame) in frame_errors else "returned"
                attempt["status"] = attempt["work"]["admission"] = status
        if selected and event in ("call", "line"):
            _guard(context)
            _check(context)
            if event == "line":
                attempt = context.admitted_frames[id(frame)]
                attempt["body_started"] = attempt["work"]["body_started"] = True
        return trace

    try:
        _guard(context)
        setup_stage = "profile_install"
        context.hook_attempts += ((setup_stage, profile),)
        set_profile(profile)
        setup_stage = "trace_install"
        context.hook_attempts += ((setup_stage, trace),)
        set_trace(trace)
        setup_stage = None
        yield
        _guard(context)
    except BaseException as error:
        if setup_stage is not None:
            context.hook_setup_error = error
        primary = (
            context.entry_error
            if context.entry_error is not None
            else context.pending_source_error
            if context.pending_source_error is not None
            else error
        )
        context.hook_primary = primary
        failure_state = {}
        try:
            failure_state["profile"] = get_profile()
        except BaseException as capture:
            context.hook_secondary_errors += (("profile_failure_state", capture),)
        try:
            failure_state["trace"] = get_trace()
        except BaseException as capture:
            context.hook_secondary_errors += (("trace_failure_state", capture),)
        context.hook_states += (("failure", failure_state),)
        if primary is not error:
            context.hook_secondary_errors += (("observer_execution", error),)
            raise primary  # noqa: B904 -- Preserve the original primary's explicit cause.
        raise
    finally:
        # Setters may install and then raise. Never rely on a successful
        # return to decide whether either previous hook needs restoration.
        cleanup = ()
        try:
            try:
                context.hook_attempts += (("trace_restore", prior_trace),)
                set_trace(prior_trace)
            except BaseException as error:
                cleanup += (("trace_restore", error),)
            finally:
                try:
                    context.hook_attempts += (("profile_restore", prior_profile),)
                    set_profile(prior_profile)
                except BaseException as error:
                    cleanup += (("profile_restore", error),)
            state = {}
            try:
                state["profile"] = get_profile()
            except BaseException as error:
                cleanup += (("profile_state", error),)
            try:
                state["trace"] = get_trace()
            except BaseException as error:
                cleanup += (("trace_state", error),)
            context.hook_states += (("after_restore", state),)
            # One bounded recovery attempt for a setter/observer which refused
            # before changing state. Both recoveries remain independent.
            try:
                if "trace" not in state or state["trace"] is not prior_trace:
                    context.hook_attempts += (("trace_restore_retry", prior_trace),)
                    set_trace(prior_trace)
            except BaseException as error:
                cleanup += (("trace_restore_retry", error),)
            finally:
                try:
                    if "profile" not in state or state["profile"] is not prior_profile:
                        context.hook_attempts += (("profile_restore_retry", prior_profile),)
                        set_profile(prior_profile)
                except BaseException as error:
                    cleanup += (("profile_restore_retry", error),)
            final_state = {}
            try:
                final_state["profile"] = get_profile()
            except BaseException as error:
                cleanup += (("profile_final_state", error),)
            try:
                final_state["trace"] = get_trace()
            except BaseException as error:
                cleanup += (("trace_final_state", error),)
            context.hook_states += (("final", final_state),)
            if final_state.get("profile", object()) is not prior_profile or (
                final_state.get("trace", object()) is not prior_trace
            ):
                cleanup += (("hook_restoration_incomplete", ValueError("Hooks were not restored")),)
        except BaseException as error:
            cleanup += (("hook_cleanup_observation", error),)
        context.hook_cleanup_errors = cleanup
        # Retain failures without invoking a possibly still-installed observer
        # again while recording its own cleanup failure.
        for origin, error in (*context.hook_secondary_errors, *cleanup):
            if context.observation_error is None:
                context.observation_error = error
                context.observation_origin = origin
                context.observation_raw = context.hook_states
            context.observation_errors += ((origin, error),)
        if primary is None:
            _guard(context)
""",
}


class FalseyError(Exception):
    def __bool__(self):
        return False


class CaptureStop(Exception):
    pass


def _unused():
    raise AssertionError("Unselected metadata placeholder executed")


def _helper():
    return sum((4, 5))


def _body(*, native=False):
    namespace = dict(__name__="observer_dispatch_metadata", helper=_helper, entered=[])
    source = """def observed(error=None):
    entered.append('body')
    local = 17
    size = len((1, 2, 3))
    total = helper()
    if error is not None:
        raise error
    return local + size + total
"""
    if native:
        source = source.replace("def observed(", "def load(")
    filename = str(NATIVE / "fixture.py") if native else "observer-dispatch-selected"
    exec(compile(source, filename, "exec"), namespace)
    return namespace["load" if native else "observed"]


def _node(role, old):
    if old:
        text = OLD_ACCOUNT[role]
        assert hashlib.sha256(text.encode()).hexdigest() == BASELINE[role][2]
    else:
        text = (ROOT / "src/cells/processes" / BASELINE[role][0]).read_text()
    return next(
        node
        for node in ast.parse(text).body
        if isinstance(node, ast.FunctionDef) and node.name == "_account"
    )


def _remember(context, error, *, origin, raw):
    if context.observation_error is None:
        context.observation_error = error
    context.observation_errors += ((origin, error),)
    context.raw_errors.append((error, raw))
    context.timeline.append(("capture_error", origin, id(error)))


def _stop(context):
    if context.observation_error is not None:
        raise CaptureStop("Retained metadata observation error")


def _guard(context):
    context.timeline.append(("guard",))
    _stop(context)


def _check(context):
    context.timeline.append(("check", context.live_ok))
    if not context.live_ok:
        raise context.drift_error


def _admit_body(context, frame):
    key = id(frame)
    record = context.admitted_frames.get(key)
    if record is None:
        record = dict(frame=frame, work={}, status="admitted")
        context.admitted_frames[key] = record
        context.timeline.append(("admit",))
    else:
        assert record["frame"] is frame
    return record


def _capture_state(context, frame, event):
    context.states.append((event, dict(frame.f_locals)))


class Work(list):
    def __init__(self, timeline):
        super().__init__()
        self.timeline = timeline

    def append(self, value):
        self.timeline.append(("work", value["layer"], value["method"]))
        super().append(value)


def _account(role, body, *, old=False, system=sys, native=False):
    context = SimpleNamespace(
        stage="metadata",
        timeline=[],
        locals={},
        raw_errors=[],
        states=[],
        observation_error=None,
        observation_errors=(),
        admitted_frames={},
        pending_source_error=None,
        entry_error=None,
        live_ok=True,
        drift_error=FalseyError("live metadata binding drift"),
        bodies={"selected": body},
    )
    context.work = Work(context.timeline)
    captures = SimpleNamespace(_remember_observation_error=_remember)
    namespace = dict(
        __name__="observer_dispatch_metadata",
        contextmanager=contextmanager,
        sys=system,
        aliases=SimpleNamespace(NATIVE=NATIVE),
        _NATIVE={"selected": _unused if native else body},
        _STORES={},
        _acquire=_unused,
        _namespace=_unused,
        _native_setup=_unused,
        _lazy_factory=_unused,
        captures=captures,
        previous=SimpleNamespace(handler=SimpleNamespace(captures=captures)),
        literal=SimpleNamespace(_CaptureStop=CaptureStop),
        _stop=_stop,
        _guard=_guard,
        _check=_check,
        _admit_body=_admit_body,
        _capture_state=_capture_state,
    )
    node = _node(role, old)
    exec(
        compile(
            ast.Module(body=[node], type_ignores=[]),
            "observer_dispatch_metadata:" + role,
            "exec",
        ),
        namespace,
    )
    return namespace["_account"], context


def _plain(value):
    if isinstance(value, BaseException):
        return dict(type=type(value).__name__, identity=id(value), cause=id(value.__cause__))
    if type(value) is dict:
        return {str(key): _plain(item) for key, item in value.items()}
    if type(value) in (tuple, list):
        return [_plain(item) for item in value]
    return value


@pytest.fixture
def evidence(tmp_path):
    record = dict(metadata_only=True, production_imports=False, actual_owner_credit=False)
    yield record
    (tmp_path / "observer-dispatch.json").write_text(json.dumps(record, sort_keys=True, indent=2))


@contextmanager
def _inherited_hooks(body, context, *, reject=None, error=None, mutation=None, local_none=False):
    """Install real chained hooks; injections target only synthetic body frames."""
    outer_profile, outer_trace = sys.getprofile(), sys.gettrace()
    codes = (body.__code__, _helper.__code__)
    trace_delegates = {}
    fired = False
    local_lines = 0

    def profile(frame, event, arg):
        nonlocal fired
        if outer_profile is not None:
            outer_profile(frame, event, arg)
        if frame.f_code not in codes:
            return
        context.timeline.append(
            (
                "prior_profile",
                frame.f_code.co_name,
                event,
                getattr(arg, "__name__", None) if event.startswith("c_") else None,
            )
        )
        if frame.f_code is body.__code__:
            if mutation == ("profile", event):
                context.live_ok = False
                context.timeline.append(("mutation", "profile", event))
            if not fired and reject == ("profile", event):
                fired = True
                raise error

    def trace(frame, event, arg):
        nonlocal fired, local_lines
        delegate = outer_trace if event == "call" else trace_delegates.get(id(frame))
        if delegate is not None:
            returned = delegate(frame, event, arg)
            if event == "call" or returned is not None:
                trace_delegates[id(frame)] = returned
        target = frame.f_code in codes
        if target:
            context.timeline.append(("prior_trace", frame.f_code.co_name, event))
        if frame.f_code is body.__code__:
            if mutation == ("trace", event):
                context.live_ok = False
                context.timeline.append(("mutation", "trace", event))
            if event == "line":
                local_lines += 1
            if not fired and reject == ("trace", event) and (not local_none or local_lines > 1):
                fired = True
                raise error
        if event == "return":
            trace_delegates.pop(id(frame), None)
        if local_none and frame.f_code is body.__code__ and event == "line" and local_lines == 1:
            return None
        if target or trace_delegates.get(id(frame)) is not None:
            return trace
        return None

    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        yield profile, trace
    finally:
        try:
            sys.settrace(outer_trace)
        finally:
            sys.setprofile(outer_profile)
        assert sys.getprofile() is outer_profile
        assert sys.gettrace() is outer_trace


def _run(role, body, *, old, source_error=None, observer_error=None, **hooks):
    account, context = _account(role, body, old=old, native=hooks.pop("native", False))
    body.__globals__["entered"].clear()
    returned = False
    value = caught = None
    before = sys.getprofile(), sys.gettrace()
    with _inherited_hooks(body, context, error=observer_error, **hooks) as installed:
        try:
            with account(context):
                value = body(source_error)
                returned = True
        except BaseException as error:
            caught = error
        assert sys.getprofile() is installed[0]
        assert sys.gettrace() is installed[1]
    assert sys.getprofile() is before[0]
    assert sys.gettrace() is before[1]
    summary = dict(
        work=list(context.work),
        locals=_plain(context.locals),
        states=_plain(context.states),
        timeline=_plain(context.timeline),
        returned=returned,
        value=value,
        error_type=None if caught is None else type(caught).__name__,
        error_identity=None if caught is None or isinstance(caught, CaptureStop) else id(caught),
        error_cause=None if caught is None else id(caught.__cause__),
        observation_errors=_plain(context.observation_errors),
        entered=list(body.__globals__["entered"]),
        attempts=[
            {key: item[key] for key in ("status", "hooks", "body_started") if key in item}
            for item in context.admitted_frames.values()
        ],
        hooks_restored=True,
    )
    return summary, caught, context


@pytest.mark.parametrize("role", tuple(BASELINE))
def test_old_oracle_is_pinned_and_outer_account_body_is_unchanged(role, evidence):
    old, current = _node(role, True), _node(role, False)
    for node in (old, current):
        node.body = [
            item
            for item in node.body
            if not (isinstance(item, ast.FunctionDef) and item.name == "profile")
        ]
    evidence.update(role=role, baseline_source=BASELINE[role][1], oracle_sha256=BASELINE[role][2])
    assert ast.dump(old, include_attributes=False) == ast.dump(current, include_attributes=False)


@pytest.mark.parametrize("role", tuple(BASELINE))
@pytest.mark.parametrize("scenario", ("success", "source", "prior_call", "prior_return"))
def test_installed_hooks_preserve_old_work_locals_and_inherited_order(role, scenario, evidence):
    body = _body()
    source, observer = FalseyError("source"), FalseyError("observer")
    source.__cause__, observer.__cause__ = (
        LookupError("source cause"),
        LookupError("observer cause"),
    )
    kwargs = dict(source_error=source if scenario == "source" else None, observer_error=observer)
    if scenario.startswith("prior_"):
        kwargs["reject"] = ("profile", scenario.removeprefix("prior_"))
    old, old_error, old_context = _run(role, body, old=True, **kwargs)
    current, current_error, context = _run(role, body, old=False, **kwargs)
    evidence.update(role=role, scenario=scenario, old=old, current=current)
    assert current == old
    if scenario == "success":
        assert current_error is old_error is None and current["value"] == 29
        events = [row[2] for row in current["timeline"] if row[0] == "prior_profile"]
        assert {"call", "return", "c_call", "c_return"}.issubset(events)
        assert current["work"] if role != "tail" else current["attempts"]
    elif scenario == "source":
        assert current_error is old_error is source
        assert current_error.__cause__ is source.__cause__
    elif scenario == "prior_call":
        assert current_error is old_error is observer and not current["entered"]
    elif role == "configuration":
        assert current_error is old_error is observer
    else:
        assert context.observation_error is old_context.observation_error is observer
        assert isinstance(current_error, CaptureStop)


@pytest.mark.parametrize("role", ("handler", "configuration"))
def test_native_filename_roster_preserves_work_and_return_locals(role, evidence):
    body = _body(native=True)
    old, _, _ = _run(role, body, old=True, native=True)
    current, error, _ = _run(role, body, old=False, native=True)
    evidence.update(role=role, old=old, current=current)
    assert error is None and current == old
    assert len(current["work"]) == 1 and current["locals"]


@pytest.mark.parametrize("mutation", (("profile", "call"), ("trace", "call"), ("trace", "line")))
def test_tail_preserves_live_checks_on_both_sides_of_prior_callback(mutation, evidence):
    body = _body()
    old, old_error, old_context = _run("tail", body, old=True, mutation=mutation)
    current, error, context = _run("tail", body, old=False, mutation=mutation)
    # The distinct fixtures issue distinct drift exceptions; compare all other events.
    old["error_identity"] = current["error_identity"] = "fixture drift error"
    evidence.update(mutation=mutation, old=old, current=current)
    assert current == old
    assert error is context.drift_error and old_error is old_context.drift_error
    assert not current["entered"] and not current["returned"]
    assert ["check", True] in current["timeline"] and ["check", False] in current["timeline"]


def test_unchanged_tail_trace_retains_local_none_delegate_until_later_refusal(evidence):
    body, error = _body(), FalseyError("later inherited local trace")
    error.__cause__ = LookupError("local trace cause")
    kwargs = dict(observer_error=error, reject=("trace", "line"), local_none=True)
    old, old_error, _ = _run("tail", body, old=True, **kwargs)
    current, current_error, _ = _run("tail", body, old=False, **kwargs)
    evidence.update(old=old, current=current)
    assert current == old and current_error is old_error is error
    assert current_error.__cause__ is error.__cause__ and not current["returned"]
    lines = [
        row
        for row in current["timeline"]
        if row[:2] == ["prior_trace", "observed"] and row[2] == "line"
    ]
    assert len(lines) == 2


class HookSlots:
    """Deterministic callback access only; no installed-hook coverage claim."""

    def __init__(self, inherited):
        self.profile, self.trace = inherited, None

    def getprofile(self):
        return self.profile

    def gettrace(self):
        return self.trace

    def setprofile(self, value):
        self.profile = value

    def settrace(self, value):
        self.trace = value


class CountingFrame:
    def __init__(self, code):
        self.code, self.code_reads, self.f_locals = code, 0, {"raw": 17}

    @property
    def f_code(self):
        self.code_reads += 1
        return self.code


def _manual(role, event, *, old, failure=None):
    body, calls = _body(), []
    frame, argument = CountingFrame(body.__code__), object()

    def inherited(actual_frame, actual_event, actual_argument):
        calls.append((actual_frame, actual_event, actual_argument))
        if failure is not None:
            raise failure

    system = HookSlots(inherited)
    account, context = _account(role, body, old=old, system=system)
    caught = None
    try:
        with account(context):
            system.profile(frame, event, argument)
    except BaseException as error:
        caught = error
    assert system.profile is inherited and system.trace is None
    assert calls == [(frame, event, argument)]
    return frame.code_reads, caught, context


@pytest.mark.parametrize("role", tuple(BASELINE))
@pytest.mark.parametrize("event", ("c_call", "c_return", "c_exception"))
def test_irrelevant_C_events_delegate_once_with_zero_own_frame_code_reads(role, event, evidence):
    old, old_error, before = _manual(role, event, old=True)
    current, error, after = _manual(role, event, old=False)
    evidence.update(role=role, event=event, old_code_reads=old, current_code_reads=current)
    assert old > 0 and current == 0
    assert error is old_error is None
    assert list(after.work) == list(before.work) == [] and after.locals == before.locals == {}


@pytest.mark.parametrize("role", tuple(BASELINE))
@pytest.mark.parametrize("event", ("call", "return"))
def test_own_Python_work_reads_code_once_and_preserves_old_rows(role, event, evidence):
    old, old_error, before = _manual(role, event, old=True)
    current, error, after = _manual(role, event, old=False)
    expected = 0 if role == "tail" and event == "return" else 1
    evidence.update(role=role, event=event, old_code_reads=old, current_code_reads=current)
    assert current == expected and old >= current
    assert error is old_error is None
    assert list(after.work) == list(before.work) and after.locals == before.locals


@pytest.mark.parametrize("role", tuple(BASELINE))
@pytest.mark.parametrize("event", ("c_call", "c_return", "c_exception"))
def test_inherited_C_refusals_keep_original_falsey_error_and_cause(role, event, evidence):
    failure = FalseyError("inherited C observer")
    failure.__cause__ = LookupError("C observer cause")
    old_reads, old_error, before = _manual(role, event, old=True, failure=failure)
    reads, error, after = _manual(role, event, old=False, failure=failure)
    evidence.update(
        role=role,
        event=event,
        old_code_reads=old_reads,
        current_code_reads=reads,
        old_error_type=type(old_error).__name__,
        current_error_type=type(error).__name__,
        old_retained=_plain(before.observation_errors),
        current_retained=_plain(after.observation_errors),
    )
    assert reads == 0 and type(error) is type(old_error)
    if event == "c_call" or role == "configuration":
        assert error is old_error is failure and error.__cause__ is failure.__cause__
    else:
        assert after.observation_error is before.observation_error is failure
        assert after.observation_errors == before.observation_errors
        assert isinstance(error, CaptureStop)


@pytest.mark.parametrize("role", ("handler", "tail"))
def test_source_unwind_and_return_observer_failure_remain_separate(role, evidence):
    body = _body()
    source, observer = FalseyError("original unwind"), FalseyError("secondary return observer")
    source.__cause__, observer.__cause__ = LookupError("source cause"), LookupError("capture cause")
    kwargs = dict(source_error=source, observer_error=observer, reject=("profile", "return"))
    old, old_error, before = _run(role, body, old=True, **kwargs)
    current, error, after = _run(role, body, old=False, **kwargs)
    evidence.update(role=role, old=old, current=current)
    assert current == old and error is old_error is source
    assert error.__cause__ is source.__cause__
    assert after.observation_error is before.observation_error is observer
    assert any(raw_error is observer for raw_error, raw in after.raw_errors)


@pytest.mark.parametrize(
    "change",
    (
        "none",
        "bindings",
        "foreign_type",
        "stale",
        "falsey",
        "foreign_p",
        "parent_p",
        "return_observer",
        "descriptor_subclass",
        "instance_getattribute",
        "getter_retarget",
    ),
)
def test_active_claim_uses_one_fresh_checked_public_parameter_read(change, evidence):
    """Actual public getter/controller ASTs, isolated metadata owner stand-ins."""
    coordinator = ROOT / "src/cells/processes/betse_native_world_phase_construction.py"
    provider = ROOT / "src/cells/processes/betse_native_parameter_world_construction.py"
    ct, kt = ast.parse(coordinator.read_bytes()), ast.parse(provider.read_bytes())
    expected = next(
        node.value.value
        for node in ct.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "KEY_SOURCE_SHA256" for t in node.targets)
    )
    assert hashlib.sha256(provider.read_bytes()).hexdigest() == expected
    native_class = next(
        node
        for node in kt.body
        if isinstance(node, ast.ClassDef) and node.name == "WorldConstructionClaim"
    )
    getter = next(
        node
        for node in native_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "parameters"
    )
    checker = next(
        node
        for node in native_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "check"
    )
    assert ast.unparse(getter.body[0]) == "return _checked(self).p" and len(getter.body) == 1
    assert ast.unparse(checker.body[0]) == "_checked(self)" and len(checker.body) == 1
    calls, p = [], object()
    original = (
        FalseyError("original checked-claim refusal")
        if change == "falsey"
        else ValueError("original checked-claim refusal")
    )
    original.__cause__ = LookupError("retained cause")

    def checked(claim):
        calls.append(("checked", claim))
        if change in ("stale", "falsey"):
            raise original
        return SimpleNamespace(p=object() if change == "foreign_p" else p)

    def bindings(context):
        calls.append(("bindings", context))
        if change == "bindings":
            raise original

    ns = dict(
        __name__="isolated_checked_claim_metadata", _checked=checked, _check_bindings=bindings
    )
    isolated_class = ast.ClassDef(
        name="WorldConstructionClaim",
        bases=[],
        keywords=[],
        body=[getter, checker],
        decorator_list=[],
    )
    active = next(
        node
        for node in ct.body
        if isinstance(node, ast.FunctionDef) and node.name == "_active_claim"
    )
    tree = ast.fix_missing_locations(ast.Module(body=[isolated_class, active], type_ignores=[]))
    exec(compile(tree, "<isolated-checked-claim-metadata>", "exec", dont_inherit=True), ns)
    cls = ns["WorldConstructionClaim"]
    retained_getter = cls.parameters.fget
    claim = object() if change == "foreign_type" else cls()
    context = SimpleNamespace(
        claim=claim,
        p=p,
        parents=(None, object() if change == "parent_p" else p),
        api=SimpleNamespace(key=SimpleNamespace(WorldConstructionClaim=cls)),
        bindings=(retained_getter, retained_getter.__code__),
    )
    delegates = []
    if change == "descriptor_subclass":

        class ForeignProperty(property):
            def __get__(self, instance, owner=None):
                if instance is None:
                    return self
                delegates.append("descriptor")
                return p

        cls.parameters = ForeignProperty(retained_getter)
        assert cls.parameters.fget is retained_getter
    elif change == "instance_getattribute":

        def foreign_getattribute(instance, name):
            if name == "parameters":
                delegates.append("attribute")
                return p
            return object.__getattribute__(instance, name)

        cls.__getattribute__ = foreign_getattribute
    elif change == "getter_retarget":

        def foreign_getter(instance):
            delegates.append("getter")
            return p

        cls.parameters = property(foreign_getter)
    prior = sys.getprofile()

    def observer(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if (
            change == "return_observer"
            and event == "return"
            and frame.f_code is cls.parameters.fget.__code__
        ):
            context.p = object()

    error = None
    try:
        sys.setprofile(observer)
        try:
            ns["_active_claim"](context)
        except BaseException as caught:
            error = caught
    finally:
        sys.setprofile(prior)
    assert calls[0][0] == "bindings"
    assert len([row for row in calls if row[0] == "checked"]) == (
        0 if change in ("bindings", "foreign_type", "descriptor_subclass", "getter_retarget") else 1
    )
    assert delegates == []
    if change in ("none", "instance_getattribute"):
        assert error is None
    elif change in ("bindings", "stale", "falsey"):
        assert error is original and error.__cause__ is original.__cause__
    else:
        assert type(error) is ValueError
    evidence.update(
        change=change,
        calls=[row[0] for row in calls],
        actual_owner_credit=False,
        public_property_and_checker_have_same_full_validator=True,
    )
