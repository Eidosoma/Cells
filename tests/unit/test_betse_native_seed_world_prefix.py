"""Written source-only prefix controls; no actual phase/native path is enabled."""

import json
import os
import sys
from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_seed_world_prefix as stage

SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_WORLD_PREFIX_SOFTWARE_RELEASED"


@pytest.fixture(autouse=True)
def native_blocked(tmp_path, request):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        pytest.skip("Prepared source-only controls; focused software release is still held")
    prior, trace = sys.getprofile(), sys.gettrace()
    attempted = []
    codes = {
        stage._acquire.__code__,
        *(fn.__code__ for fn in stage._BODIES.values()),
        stage.previous.prepare.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempted.append(frame.f_code.co_qualname)
            raise AssertionError("Actual source/phase/RNG/native prefix entry is forbidden")
        if prior is not None:
            prior(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
        assert not attempted
        assert sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempted,
                    source_native_or_scientific_credit=0,
                )
            )
        )


def test_preparation_exact_literal_entry_helpers_and_readonly_lattice():
    plan = stage.source_plan()
    assert plan["order"] == (stage.CALLBACK, "genuine SEED guard", "same Cells non-SVG lattice")
    assert plan["caller_fields"] == stage.STORES
    assert plan["next_method"] == "make_voronoi"
    assert plan["lattice_lines"] == (692, 842)
    assert plan["progress_ranged_before_phase_birth_outside_boundary"] is True
    assert plan["world_ready_parameter_parent_bound"] is False
    assert plan["accepted_key_api"] is None
    assert plan["no_rng_reset_or_new_stream"] is True


@pytest.mark.parametrize("owner", [None, {}, NS(), object()])
def test_preparation_supplied_state_is_never_a_typed_phase_parent(owner):
    with pytest.raises(stage.WorldPrefixRejected) as caught:
        stage.from_phase(owner, law_id=stage.LAW_ID)
    assert caught.value.stage == "phase_parent"


@pytest.mark.parametrize("law", [None, "INIT", "SIM", "normalized_world"])
def test_preparation_exact_method_boundary_law_is_required(law):
    with pytest.raises(stage.WorldPrefixRejected) as caught:
        stage.from_phase(None, law_id=law)
    assert caught.value.stage == "law"


def test_preparation_unbound_world_parent_never_uses_old_claim_or_inspection(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No old parameter/cache validation or accepted API may be guessed")

    monkeypatch.setattr(stage.previous, "_validate", forbidden)
    monkeypatch.setattr(stage, "_parent_hooks", forbidden)
    with pytest.raises(stage.WorldPrefixRejected) as caught:
        stage._world_parent(None)
    assert caught.value.stage == "world_ready_parameter_parent"
    assert caught.value.partial["accepted_key_api"] is None


def test_preparation_missing_original_dispatch_hook_refuses():
    with pytest.raises(stage.WorldPrefixRejected) as caught:
        stage._parent_hooks()
    assert caught.value.stage == "phase_dispatch"
    assert caught.value.partial["missing"] in stage.PARENT_HOOKS


@pytest.mark.parametrize("enabled,flag", [(False, "1"), (True, "0"), (1, "1")])
def test_preparation_release_precedes_dispatch_parent_and_source(monkeypatch, enabled, flag):
    def forbidden(*args, **kwargs):
        raise AssertionError("Held preparation may not enter parent, hooks or source")

    monkeypatch.setattr(stage, "_parent_hooks", forbidden)
    monkeypatch.setattr(stage, "_world_parent", forbidden)
    monkeypatch.setenv(stage.RELEASE, flag)
    with pytest.raises(stage.WorldPrefixRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


def test_preparation_request_cannot_be_hydrated_or_owner_constructed():
    with pytest.raises(TypeError):
        stage.SeedWorldPrefixOwner()
    request = stage.Request(None, "not-an-owner", "not-an-authority", "unissued")
    with pytest.raises(TypeError):
        request.__reduce_ex__(5)
    assert request not in stage._REQUESTS


def _controller():
    """Observer mechanics only; these tokens never enter an issuance registry."""
    return NS(
        request=None,
        active=True,
        invalid=False,
        thread=stage.get_ident(),
        entry_error=None,
        observation_error=None,
        observation_errors=(),
        capture_failures=(),
        capture_reporting_errors=(),
        cleanup_phase=None,
        observer_bindings=stage._observer_bindings(),
        pending_source_error=None,
        work=[],
        stack=[],
        admitted={},
        stages=[],
        events=[],
        locals={},
        draws=[],
        body_codes={},
        callback_chain=(),
        callback_codes=frozenset(),
        callback_occurrence=None,
        callback=object(),
        forbidden_callback_codes=set(),
        cells=NS(),
        p=NS(),
        rand=object(),
        draw_active=False,
    )


@contextmanager
def _active(context):
    before = tuple(stage._ISSUED.items())
    stage._ACTIVE.append(context)
    try:
        yield
    finally:
        assert stage._ACTIVE.pop() is context
        context.active = False
        assert tuple(stage._ISSUED.items()) == before


@pytest.fixture
def observer_control(monkeypatch):
    context = _controller()

    def check(actual):
        assert actual is context and not stage._ISSUED
        stage._guard(actual)

    # These metadata sentinels exercise only hook plumbing, not source-owner
    # authorization. No public prepare/from_phase/claim function is replaced.
    monkeypatch.setattr(stage, "_check", check)
    monkeypatch.setattr(stage, "_epoch", lambda actual: ("metadata-state",))
    monkeypatch.setattr(stage, "_same_epoch", lambda actual, value: None)
    return context


@pytest.mark.parametrize("name", stage.METHODS)
def test_isolated_unclaimed_raw_body_retains_zero_body_attempt(observer_control, name):
    context = observer_control
    counts = []

    def body(actual):
        counts.append(actual)

    context.body_codes = {body.__code__: name}
    prior, trace = sys.getprofile(), sys.gettrace()
    with _active(context), pytest.raises(stage.WorldPrefixRejected) as caught:
        with stage._account(context):
            body(context.cells)
    assert counts == [] and context.entry_error is caught.value
    row = context.last_rejected_attempt
    assert row["frame"].f_code is body.__code__
    assert row["admission"] == "rejected" and row["body_started"] is False
    assert row["entry_is_case"] is False
    assert sys.getprofile() is prior and sys.gettrace() is trace


def test_isolated_trace_and_profile_share_one_admission_before_observers(observer_control):
    context = observer_control
    values, delivered = [], []

    def body(actual):
        values.append(actual)

    context.body_codes = {body.__code__: stage.METHODS[0]}
    prior, outer_trace = sys.getprofile(), sys.gettrace()
    delegates = {}

    def profile(frame, event, arg):
        if frame.f_code is body.__code__ and event == "call":
            assert context.admitted[id(frame)]["frame"] is frame
            delivered.append("profile")
        if prior is not None:
            prior(frame, event, arg)

    def trace(frame, event, arg):
        if frame.f_code is body.__code__ and event == "call":
            assert context.admitted[id(frame)]["frame"] is frame
            delivered.append("trace")
        delegate = outer_trace if event == "call" else delegates.get(id(frame))
        if delegate is not None:
            delegates[id(frame)] = delegate(frame, event, arg)
        if event == "return":
            delegates.pop(id(frame), None)
        return trace

    def driver():
        record = dict(name=stage.METHODS[0], body=None, next_child=0, body_caller=sys._getframe())
        context.stack.append(record)
        return body(context.cells)

    sys.setprofile(profile)
    sys.settrace(trace)
    try:
        with _active(context), stage._account(context):
            driver()
        assert values == [context.cells] and sorted(delivered) == ["profile", "trace"]
        assert len(context.admitted) == 1 and len(context.work) == 1
        assert context.work[0]["body_started"] is True
        assert sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.settrace(outer_trace)
        sys.setprofile(prior)


@pytest.mark.parametrize("origin", ["profile", "trace"])
@pytest.mark.parametrize("target", ["same", "next"])
def test_isolated_observer_cannot_seize_guarded_body_slot(observer_control, origin, target):
    context = observer_control
    values, errors = [], []

    def body(actual):
        values.append(actual)

    context.body_codes = {body.__code__: stage.METHODS[0]}
    prior, prior_trace = sys.getprofile(), sys.gettrace()
    fired = False

    def probe(frame, event):
        nonlocal fired
        if not fired and frame.f_code is body.__code__ and event == "call":
            fired = True
            name = stage.METHODS[0] if target == "same" else stage.METHODS[1]
            try:
                stage._body_call(context, name, body, context.cells, (), sys._getframe())
            except stage.WorldPrefixRejected as error:
                errors.append(error)
            else:
                raise AssertionError("Observer acquired a source-body slot")

    def profile(frame, event, arg):
        if origin == "profile":
            probe(frame, event)
        if prior is not None:
            prior(frame, event, arg)

    delegates = {}

    def trace(frame, event, arg):
        if origin == "trace":
            probe(frame, event)
        delegate = prior_trace if event == "call" else delegates.get(id(frame))
        if delegate is not None:
            delegates[id(frame)] = delegate(frame, event, arg)
        if event == "return":
            delegates.pop(id(frame), None)
        return trace

    def driver():
        context.stack.append(
            dict(
                name=stage.METHODS[0],
                body=None,
                next_child=0,
                body_caller=sys._getframe(),
                invocation=sys._getframe(),
            )
        )
        body(context.cells)

    sys.setprofile(profile)
    sys.settrace(trace)
    try:
        with _active(context), pytest.raises(stage.WorldPrefixRejected) as caught:
            with stage._account(context):
                driver()
        assert fired and len(errors) == 1 and caught.value is errors[0]
        assert values == [] and context.entry_error is errors[0]
        assert context.last_rejected_attempt["body_started"] is False
    finally:
        sys.settrace(prior_trace)
        sys.setprofile(prior)


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("installed_first", [False, True])
def test_isolated_partial_setup_restores_both_and_preserves_cause(
    observer_control, monkeypatch, hook, installed_first
):
    context = observer_control
    prior, trace = sys.getprofile(), sys.gettrace()
    original = dict(profile=sys.setprofile, trace=sys.settrace)
    error, cause = OSError("partial observer setup"), KeyError("setup cause")
    calls, failed = [], set()

    def setter(name, value):
        old = prior if name == "profile" else trace
        calls.append((name, value is old))
        if name == hook and value is not old and not failed:
            failed.add(name)
            if installed_first:
                original[name](value)
            raise error from cause
        original[name](value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "setprofile", lambda value: setter("profile", value))
            patch.setattr(sys, "settrace", lambda value: setter("trace", value))
            with _active(context), pytest.raises(OSError) as caught:
                with stage._account(context):
                    raise AssertionError("Failed setup must not reach body")
        assert caught.value is error and error.__cause__ is cause
        assert ("profile", True) in calls and ("trace", True) in calls
        assert sys.getprofile() is prior and sys.gettrace() is trace
        assert context.hook_after == (prior, trace)
    finally:
        original["trace"](trace)
        original["profile"](prior)


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("hook", ["profile", "trace", "both"])
def test_isolated_cleanup_failures_cannot_replace_primary(
    observer_control, monkeypatch, source_fails, hook
):
    context = observer_control
    prior, trace = sys.getprofile(), sys.gettrace()
    setters = dict(profile=sys.setprofile, trace=sys.settrace)
    source, cause = ArithmeticError("primary source"), KeyError("primary cause")
    errors = {name: OSError(name + " cleanup") for name in setters}
    failed, calls = set(), []

    def setter(name, value):
        old = prior if name == "profile" else trace
        calls.append((name, value is old))
        if value is old and name not in failed and hook in (name, "both"):
            failed.add(name)
            raise errors[name]
        setters[name](value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "setprofile", lambda value: setter("profile", value))
            patch.setattr(sys, "settrace", lambda value: setter("trace", value))
            expected = ArithmeticError if source_fails else stage.literal._CaptureStop
            with _active(context), pytest.raises(expected) as caught:
                with stage._account(context):
                    if source_fails:
                        raise source from cause
        if source_fails:
            assert caught.value is source and source.__cause__ is cause
        assert context.observation_error in errors.values() and context.cleanup_errors
        assert ("profile", True) in calls and ("trace", True) in calls
        assert sys.getprofile() is prior and sys.gettrace() is trace
    finally:
        setters["trace"](trace)
        setters["profile"](prior)


@pytest.mark.parametrize("source_fails", [False, True])
def test_isolated_return_capture_keeps_completed_fields_or_original_unwind(
    observer_control, monkeypatch, source_fails
):
    context = observer_control
    source, cause, capture = ValueError("source"), KeyError("cause"), OSError("locals")

    def body(actual):
        actual.partial = object()
        if source_fails:
            raise source from cause

    context.body_codes = {body.__code__: stage.METHODS[0]}
    original = stage._capture

    def observe(actual, frame, event):
        original(actual, frame, event)
        if frame.f_code is body.__code__ and event == "return":
            raise capture

    monkeypatch.setattr(stage, "_capture", observe)
    context.observer_bindings = stage._observer_bindings()

    def driver():
        context.stack.append(
            dict(name=stage.METHODS[0], body=None, next_child=0, body_caller=sys._getframe())
        )
        body(context.cells)

    expected = ValueError if source_fails else stage.literal._CaptureStop
    with _active(context), pytest.raises(expected) as caught:
        with stage._account(context):
            driver()
    assert hasattr(context.cells, "partial") and context.observation_error is capture
    if source_fails:
        assert caught.value is source and source.__cause__ is cause
    assert context.locals and context.last_caller_fields["partial"] is context.cells.partial


def test_isolated_callable_atoms_retain_wrapped_implementation_and_closed_delegate():
    def inner():
        return None

    def close(delegate):
        def wrapper():
            return delegate()

        return wrapper

    wrapped = close(inner)
    before = stage._atoms(wrapped)
    old = inner.__code__
    try:
        inner.__code__ = old.replace(co_name="changed_implementation")
        with pytest.raises(ValueError):
            stage.literal._same(stage._atoms(wrapped), before)
    finally:
        inner.__code__ = old


@pytest.mark.parametrize("outcome", ["success", "source_failure", "capture_failure"])
def test_isolated_original_rng_wrapper_retains_actual_result_and_failure(
    observer_control, monkeypatch, outcome
):
    context = observer_control
    result, calls = object(), []
    primary, cause, capture = ValueError("native rand"), KeyError("cause"), OSError("MT capture")

    def state(actual):
        assert actual is context
        if calls and outcome == "capture_failure":
            raise capture
        return NS(identity="after" if calls else "before")

    def native(*shape):
        calls.append(shape)
        if outcome == "source_failure":
            raise primary from cause
        return result

    monkeypatch.setattr(stage, "_rng_state", state)
    context.expected_rng = state(context)
    view = stage._Random(context, native)

    def driver():
        context.stack.append(dict(name=stage.METHODS[3], body=sys._getframe()))
        return view.rand(2, 3)

    if outcome == "success":
        with _active(context):
            assert driver() is result
        assert context.draws[0]["raw_result"] is result
        assert context.expected_rng.identity == "after"
    else:
        expected = ValueError if outcome == "source_failure" else stage.literal._CaptureStop
        with _active(context), pytest.raises(expected) as caught:
            driver()
        if outcome == "source_failure":
            assert caught.value is primary and primary.__cause__ is cause
            assert context.draws[0]["source_error"] is primary
        else:
            assert context.observation_error is capture
            assert context.draws[0]["raw_result"] is result
    assert calls == [(2, 3)] and context.draw_active is False
    assert not stage._ISSUED  # Metadata stand-ins never issued a native source owner.


def test_isolated_runner_selection_never_matches_ancestor_directory():
    from validation.betse import betse_native_seed_world_prefix_software as runner

    owner = NS(name="test_owner", nodeid="isolated-01::test_owner")
    isolated = NS(name="test_isolated_hooks", nodeid="anywhere::test_isolated_hooks")
    assert runner.select_items([owner, isolated], "isolated") == ([isolated], [owner])
    with pytest.raises(ValueError):
        runner.select_items([owner], "isolated")


@pytest.mark.parametrize("name", ["_admit", "_remember"])
@pytest.mark.parametrize("mutation", ["replace", "code"])
def test_isolated_live_admission_and_recorder_drift_precedes_body(
    observer_control, monkeypatch, name, mutation
):
    context = observer_control
    counts = dict(body=0, altered_helper=0)

    def body(actual):
        counts["body"] += 1

    def replacement(*args, **kwargs):
        counts["altered_helper"] += 1

    context.body_codes = {body.__code__: stage.METHODS[0]}
    original = getattr(stage, name)
    old_code = original.__code__

    def driver():
        context.stack.append(dict(
            name=stage.METHODS[0], body=None, next_child=0,
            body_caller=sys._getframe(),
        ))
        body(context.cells)

    try:
        if mutation == "replace":
            monkeypatch.setattr(stage, name, replacement)
        else:
            original.__code__ = old_code.replace(co_name="changed_live_guard")
        with _active(context), pytest.raises(ValueError, match="binding"):
            with stage._account(context):
                driver()
        assert counts == dict(body=0, altered_helper=0)
    finally:
        original.__code__ = old_code


def _binding_context():
    """Callable atoms only; no phase, parameter, claim or owner is issued."""
    calls = []

    def helper(*args, **kwargs):
        calls.append("unexpected helper")

    class Callback:
        def progress_stated(self, status):
            calls.append("unexpected callback")

    def implementation(*args, **kwargs):
        calls.append("unexpected implementation")

    def log(*args, **kwargs):
        calls.append("unexpected log")

    log.__wrapped__ = helper
    log._implementation = implementation
    random = NS(mtrand=NS(_rand=object()), rand=helper, get_state=helper)
    numpy = NS(random=random, **{name: helper for name in stage.NUMPY_HELPERS})
    context = _controller()
    context.prefix, context.native_types = object(), {}
    context.native_numpy, context.rng, context.rand = numpy, random.mtrand._rand, helper
    context.native_logs, context.native_math = NS(log_info=log), object()
    context.conf_exception, context.exception = ValueError, ValueError
    context.enum, context.lattice_enum = NS(SEED=object()), object()
    context.strjoin = NS(join_as_disconjunction_double_quoted=helper)
    context.callback = Callback()
    context.callback_method = Callback.progress_stated
    context.callback_chain = (Callback.progress_stated,)
    context.callback_functions = context.callback_chain
    context.native_methods, context.wrappers = {}, {}
    context.chain = lambda function: [function]
    return context, calls, log, helper, implementation


@pytest.mark.parametrize("mutation", ["replace", "code", "wrapped_code", "implementation_code"])
def test_isolated_reached_log_binding_stops_before_later_helper(monkeypatch, mutation):
    context, calls, log, wrapped, implementation = _binding_context()
    before = stage._native_bindings(context)

    def check(actual):
        assert actual is context
        stage._guard(context)
        stage.literal._same(stage._native_bindings(context), before)

    monkeypatch.setattr(stage, "_check", check)
    view = stage._Numpy(context, context.native_numpy)
    target = {"code": log, "wrapped_code": wrapped,
              "implementation_code": implementation}.get(mutation)
    old_code = None if target is None else target.__code__
    try:
        if mutation == "replace":
            context.native_logs.log_info = lambda *args: calls.append("changed log")
        else:
            target.__code__ = old_code.replace(co_name="retargeted_log_delegate")
        with _active(context), pytest.raises(ValueError, match="binding"):
            _ = view.min
        assert calls == []
    finally:
        if target is not None:
            target.__code__ = old_code


@pytest.mark.parametrize("source_fails", [False, True])
def test_isolated_recorder_entry_rejection_keeps_primary_and_both_restores(
    observer_control, monkeypatch, source_fails
):
    context = observer_control
    prior, trace = sys.getprofile(), sys.gettrace()
    original_setters = dict(profile=sys.setprofile, trace=sys.settrace)
    source, cause = ArithmeticError("original source"), KeyError("cause")
    cleanup, reporting = OSError("trace restoration"), LookupError("recorder entry")
    restored, failed = [], False

    def inherited(frame, event, arg):
        if event == "call" and frame.f_code is stage._remember.__code__:
            raise reporting
        if prior is not None:
            prior(frame, event, arg)

    def setter(name, value):
        nonlocal failed
        old = inherited if name == "profile" else trace
        if value is old:
            restored.append(name)
            if name == "trace" and not failed:
                failed = True
                raise cleanup
        original_setters[name](value)

    sys.setprofile(inherited)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "setprofile", lambda value: setter("profile", value))
            patch.setattr(sys, "settrace", lambda value: setter("trace", value))
            expected = ArithmeticError if source_fails else stage.literal._CaptureStop
            with _active(context), pytest.raises(expected) as caught:
                with stage._account(context):
                    if source_fails:
                        raise source from cause
        if source_fails:
            assert caught.value is source and source.__cause__ is cause
        assert "profile" in restored and "trace" in restored
        assert context.observation_error is cleanup and context.cleanup_errors
        assert context.capture_failures
        assert any(row[1] is reporting for row in context.capture_reporting_errors)
        assert context.hook_identities_restored is True
        assert sys.getprofile() is inherited and sys.gettrace() is trace
    finally:
        original_setters["trace"](trace)
        original_setters["profile"](prior)


@pytest.mark.parametrize("source_fails", [False, True])
def test_isolated_persistent_hook_mismatch_refuses_even_when_setter_returns(
    observer_control, monkeypatch, source_fails
):
    context = observer_control
    prior, trace = sys.getprofile(), sys.gettrace()
    setters = dict(profile=sys.setprofile, trace=sys.settrace)
    source, cause = RuntimeError("source primary"), KeyError("cause")
    attempted = []

    def trace_setter(value):
        if value is trace:
            attempted.append("ignored trace restore")
            return
        setters["trace"](value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "settrace", trace_setter)
            expected = RuntimeError if source_fails else stage.literal._CaptureStop
            with _active(context), pytest.raises(expected) as caught:
                with stage._account(context):
                    if source_fails:
                        raise source from cause
        if source_fails:
            assert caught.value is source and source.__cause__ is cause
        assert attempted and context.hook_identities_restored is False
        assert context.invalid and context.observation_error is not None
        assert "profile_restore" in context.hook_attempts
    finally:
        setters["trace"](trace)
        setters["profile"](prior)


class _FalseFailure(ValueError):
    def __bool__(self):
        return False


@pytest.mark.parametrize("role", ["primary", "capture"])
def test_isolated_falsey_failure_retains_failed_stage_and_exact_cause(role):
    context = NS(stage="actual failed stage")
    error, cause = _FalseFailure("falsey failure"), KeyError("cause")
    try:
        raise error from cause
    except _FalseFailure as caught:
        primary = caught if role == "primary" else None
        capture = caught if role == "capture" else None
        assert stage._failure_stage(context, primary, capture) == context.stage
        assert not (primary is None and capture is None)
        assert caught is error and error.__cause__ is cause
    assert stage._failure_stage(context, None, None) is None


@pytest.mark.parametrize(
    "shape", ["direct", "wrapped_args", "wrapped_keyword", "wrapped_hidden_keyword"]
)
def test_isolated_actual_callback_chain_is_one_occurrence(observer_control, shape):
    context = observer_control
    calls, outer_locals = [], []

    def native(receiver, status):
        calls.append((receiver, status))

    def native_keyword(receiver, *, status):
        calls.append((receiver, status))

    if shape == "direct":
        method, chain = native, (native,)
    else:
        delegate = native_keyword if shape == "wrapped_keyword" else native

        if shape == "wrapped_hidden_keyword":
            def wrapper(*arguments, __beartype_func=delegate, **keywords):
                outer_locals.append(dict(locals()))
                return __beartype_func(*arguments, **keywords)
        else:
            def wrapper(*arguments, **keywords):
                outer_locals.append(dict(locals()))
                if shape == "wrapped_keyword":
                    return delegate(arguments[0], status=arguments[1])
                return delegate(*arguments, **keywords)

        wrapper.__wrapped__ = delegate
        method, chain = wrapper, (wrapper, delegate)
    callback_type = type("MetadataCallback", (), {"progress_stated": method})
    context.callback = callback_type()  # Class/method fixed before this metadata object exists.
    context.callback_chain = chain
    context.callback_codes = frozenset(fn.__code__ for fn in chain)

    def body(actual):
        context.callback.progress_stated(stage.CALLBACK_STATUS)

    context.body_codes = {body.__code__: stage.METHODS[0]}

    def driver():
        context.stack.append(dict(name=stage.METHODS[0], body=None, next_child=0,
                                  body_caller=sys._getframe()))
        body(context.cells)

    with _active(context), stage._account(context):
        driver()
    assert calls == [(context.callback, stage.CALLBACK_STATUS)]
    assert context.stages == [stage.CALLBACK]
    occurrence = context.callback_occurrence
    assert len(occurrence["frames"]) == len(chain)
    assert occurrence["returned"] == tuple(reversed(range(len(chain))))
    assert occurrence["state"] == "returned"
    rows = [row for row in context.work if "callback_index" in row]
    assert len(rows) == len(chain) and sum(row["layer"] == "native_callback_body" for row in rows) == 1
    if shape != "direct":
        assert outer_locals and "self" not in outer_locals[0]
    assert not stage._ISSUED  # No native parent/phase/owner was manufactured.


@pytest.mark.parametrize("mode", ["wrong_receiver", "bypass_wrapper", "skip_native"])
def test_isolated_callback_chain_retarget_or_incomplete_body_refuses(observer_control, mode):
    context = observer_control
    calls = []

    def native(receiver, status):
        calls.append(receiver)

    other = object()

    def wrapper(*arguments, **keywords):
        if mode == "skip_native":
            return None
        return native(other, arguments[1])

    wrapper.__wrapped__ = native
    callback_type = type("MetadataCallback", (), {"progress_stated": wrapper})
    context.callback = callback_type()
    context.callback_chain = (wrapper, native)
    context.callback_codes = frozenset(fn.__code__ for fn in context.callback_chain)

    def body(actual):
        if mode == "bypass_wrapper":
            native(context.callback, stage.CALLBACK_STATUS)
        else:
            context.callback.progress_stated(stage.CALLBACK_STATUS)

    context.body_codes = {body.__code__: stage.METHODS[0]}

    def driver():
        context.stack.append(dict(name=stage.METHODS[0], body=None, next_child=0,
                                  body_caller=sys._getframe()))
        body(context.cells)

    expected = stage.literal._CaptureStop if mode == "skip_native" else stage.WorldPrefixRejected
    with _active(context), pytest.raises(expected):
        with stage._account(context):
            driver()
    assert calls == [] and context.stages == []
    assert context.entry_error is not None or context.observation_error is not None


@pytest.mark.parametrize("failed_write", ["guard", "runtime", "fallback", "all"])
def test_isolated_runner_independent_evidence_failure_preserves_primary(
    monkeypatch, tmp_path, failed_write
):
    from validation.betse import betse_native_seed_world_prefix_software as runner

    state = runner._run_state()
    primary, cause = _FalseFailure("original failure"), KeyError("cause")
    try:
        raise primary from cause
    except _FalseFailure:
        pass
    state.primary, state.primary_stage = primary, "original software stage"
    state.status, state.hooks_restored, state.guard_active_on_cleanup = 1, True, True
    writes, inventory_calls = [], []
    recording = OSError("writer entry")

    def inventory():
        inventory_calls.append("runtime")
        return {"metadata": True}

    def write(path, value):
        tag = {"native-entry-guard.json": "guard", "runtime.json": "runtime"}.get(
            path.name, "fallback"
        )
        writes.append(tag)
        if failed_write in (tag, "all"):
            raise recording

    monkeypatch.setattr(runner.inherited.runtime, "inventory", inventory)
    monkeypatch.setattr(runner.snapshot, "write_json", write)
    runner._write_evidence(tmp_path, state, [], [])
    assert writes == ["guard", "runtime", "fallback"] and inventory_calls == ["runtime"]
    assert state.evidence_errors and all(row[1] is recording for row in state.evidence_errors)
    with pytest.raises(_FalseFailure) as caught:
        runner._finish(state, [], [])
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.seed_world_software is state


def test_isolated_runner_persistent_identity_mismatch_is_failed():
    from validation.betse import betse_native_seed_world_prefix_software as runner

    state = runner._run_state()
    before, current = (object(), object()), [object(), object()]
    calls = []

    def set_profile(value):
        calls.append("profile")
        current[0] = value

    def set_trace(value):
        calls.append("trace")  # Deliberately return without restoring.

    runner._restore_hooks(state, before, tuple(current),
                          (set_profile, set_trace),
                          (lambda: current[0], lambda: current[1]))
    assert "profile" in calls and "trace" in calls
    assert state.hooks_restored is False and state.cleanup_errors
    assert runner._finish(state, [], []) == 1


def test_isolated_main_fallback_write_cannot_replace_primary(monkeypatch, tmp_path):
    from validation.betse import betse_native_seed_world_prefix_software as runner

    primary, recording = _FalseFailure("primary"), OSError("fallback")

    def fail(*args, **kwargs):
        raise recording

    monkeypatch.setattr(runner.snapshot, "write_json", fail)
    runner._main_failure(tmp_path, primary)
    assert runner._RAW_FAILURES[-1][1:3] == (primary, recording)


def test_isolated_runner_inventory_entry_failure_still_writes_guard_and_fallback(
    monkeypatch, tmp_path
):
    from validation.betse import betse_native_seed_world_prefix_software as runner

    state = runner._run_state()
    primary, capture = _FalseFailure("primary"), OSError("inventory entry")
    state.primary, state.primary_stage = primary, "original failure"
    state.status, state.hooks_restored, state.guard_active_on_cleanup = 1, True, True
    writes, attempted = [], []

    def inventory():
        attempted.append("inventory")
        raise capture

    monkeypatch.setattr(runner.inherited.runtime, "inventory", inventory)
    monkeypatch.setattr(runner.snapshot, "write_json", lambda path, value: writes.append(path.name))
    runner._write_evidence(tmp_path, state, [], [])
    assert writes == ["native-entry-guard.json", "child-failure.json"]
    assert attempted == ["inventory"] and state.evidence_errors[0][1] is capture
    with pytest.raises(_FalseFailure) as caught:
        runner._finish(state, [], [])
    assert caught.value is primary


def test_isolated_runner_first_restore_failure_keeps_second_attempt_and_primary():
    from validation.betse import betse_native_seed_world_prefix_software as runner

    state = runner._run_state()
    primary, capture = _FalseFailure("original primary"), OSError("trace entry")
    state.primary = primary
    before, actual, calls = (object(), object()), [object(), object()], []

    def profile(value):
        calls.append("profile")
        actual[0] = value

    def trace(value):
        calls.append("trace")
        if calls.count("trace") == 1:
            raise capture
        actual[1] = value

    runner._restore_hooks(state, before, tuple(actual), (profile, trace),
                          (lambda: actual[0], lambda: actual[1]))
    assert calls == ["trace", "trace", "profile"]
    assert state.hooks_restored is True and state.cleanup_errors[0][1] is capture
    assert state.primary is primary


def test_isolated_wrapped_callback_source_failure_retains_original_cause(observer_control):
    context = observer_control
    primary, cause, called = _FalseFailure("callback source"), KeyError("cause"), []

    def native(receiver, status):
        called.append(receiver)
        raise primary from cause

    def wrapper(*arguments, **keywords):
        return native(*arguments, **keywords)

    wrapper.__wrapped__ = native
    callback_type = type("MetadataCallback", (), {"progress_stated": wrapper})
    context.callback = callback_type()
    context.callback_chain = (wrapper, native)
    context.callback_codes = frozenset(fn.__code__ for fn in context.callback_chain)

    def body(actual):
        context.callback.progress_stated(stage.CALLBACK_STATUS)

    context.body_codes = {body.__code__: stage.METHODS[0]}

    def driver():
        context.stack.append(dict(name=stage.METHODS[0], body=None, next_child=0,
                                  body_caller=sys._getframe()))
        body(context.cells)

    with _active(context), pytest.raises(_FalseFailure) as caught:
        with stage._account(context):
            driver()
    assert caught.value is primary and primary.__cause__ is cause
    assert called == [context.callback] and context.stages == []
    assert context.callback_occurrence["source_error"] is primary
    assert context.callback_occurrence["state"] == "failed"


def test_isolated_callback_log_globals_cannot_retarget_with_lattice_logs_unchanged(monkeypatch):
    context, calls, _, _, _ = _binding_context()
    original_logs = NS(log_info=lambda *args: calls.append("callback log"))
    namespace = {"logs": original_logs}
    exec("def progress_stated(receiver, status):\n    logs.log_info(status)\n", namespace)
    callback_type = type("MetadataCallback", (), {"progress_stated": namespace["progress_stated"]})
    context.callback = callback_type()
    context.callback_method = callback_type.progress_stated
    context.callback_chain = (context.callback_method,)
    context.callback_functions = context.callback_chain
    lattice_logs = context.native_logs
    before = stage._native_bindings(context)
    namespace["logs"] = NS(log_info=original_logs.log_info)  # Equal callable, distinct live module.

    def check(actual):
        assert actual is context
        stage._guard(context)
        stage.literal._same(stage._native_bindings(context), before)

    monkeypatch.setattr(stage, "_check", check)
    view = stage._Numpy(context, context.native_numpy)
    with _active(context), pytest.raises(ValueError, match="binding"):
        _ = view.min
    assert context.native_logs is lattice_logs and calls == []


def test_isolated_runner_restores_outer_hooks_before_next_evidence_capture(monkeypatch, tmp_path):
    from validation.betse import betse_native_seed_world_prefix_software as runner

    state = runner._run_state()
    outer, actual, observed = (object(), object()), [object(), object()], []

    def set_profile(value):
        actual[0] = value

    def set_trace(value):
        actual[1] = value

    runner._restore_hooks(state, outer, tuple(actual),
                          (set_profile, set_trace),
                          (lambda: actual[0], lambda: actual[1]))
    state.status = 0
    failure = OSError("guard recorder entry disabled profiler")

    def write(path, value):
        observed.append(path.name)
        if path.name == "native-entry-guard.json":
            actual[0] = None
            raise failure

    def inventory():
        assert actual[0] is outer[0] and actual[1] is outer[1]
        observed.append("inventory with exact outer hooks")
        return {"metadata": True}

    monkeypatch.setattr(runner.snapshot, "write_json", write)
    monkeypatch.setattr(runner.inherited.runtime, "inventory", inventory)
    runner._write_evidence(tmp_path, state, [], [])
    assert observed == ["native-entry-guard.json", "inventory with exact outer hooks",
                        "runtime.json", "child-failure.json"]
    assert state.evidence_errors[0][1] is failure
    assert actual[0] is outer[0] and actual[1] is outer[1]


@pytest.mark.parametrize("mutation", ["delegate", "delegate_code", "mapping", "key"])
def test_isolated_hidden_keyword_delegate_binding_precedes_all_bodies(
    observer_control, monkeypatch, mutation
):
    context = observer_control
    counts = dict(native=0, hidden=0, foreign=0, body=0)

    def native(receiver, status):
        counts["native"] += 1

    def hidden(receiver, status):
        counts["hidden"] += 1
        return native(receiver, status)

    def foreign(receiver, status):
        counts["foreign"] += 1

    def wrapper(*arguments, __beartype_func=hidden, **keywords):
        return __beartype_func(*arguments, **keywords)

    wrapper.__wrapped__ = native
    callback_type = type("MetadataKeywordCallback", (), {"progress_stated": wrapper})
    context.callback = callback_type()
    context.callback_chain = (wrapper, native)
    context.callback_codes = frozenset(fn.__code__ for fn in context.callback_chain)
    outer_code, wrapped = wrapper.__code__, wrapper.__wrapped__
    defaults, hidden_code = wrapper.__kwdefaults__, hidden.__code__
    key = next(iter(defaults))
    before = stage._atoms(wrapper)

    def check(actual):
        assert actual is context
        stage._guard(actual)
        stage.literal._same(stage._atoms(type(context.callback).progress_stated), before)

    def body(actual):
        counts["body"] += 1
        context.callback.progress_stated(stage.CALLBACK_STATUS)

    context.body_codes = {body.__code__: stage.METHODS[0]}

    def driver():
        context.stack.append(dict(name=stage.METHODS[0], body=None, next_child=0,
                                  body_caller=sys._getframe()))
        body(context.cells)

    monkeypatch.setattr(stage, "_check", check)
    try:
        if mutation == "delegate":
            defaults[key] = foreign
        elif mutation == "delegate_code":
            # This delegate is reachable only via the keyword default; the
            # ordinary __wrapped__ function and its code remain unchanged.
            hidden.__code__ = hidden_code.replace(co_name="retargeted_hidden_delegate")
        elif mutation == "mapping":
            wrapper.__kwdefaults__ = dict(defaults)
        else:
            new_key = "".join(("__beartype", "_func"))
            assert new_key == key and new_key is not key
            value = defaults.pop(key)
            defaults[new_key] = value
        assert wrapper.__code__ is outer_code and wrapper.__wrapped__ is wrapped
        if mutation != "mapping":
            assert wrapper.__kwdefaults__ is defaults
        with _active(context), pytest.raises(ValueError, match="binding"):
            with stage._account(context):
                driver()
        assert counts == dict(native=0, hidden=0, foreign=0, body=0)
        assert not stage._ISSUED
    finally:
        wrapper.__kwdefaults__ = defaults
        hidden.__code__ = hidden_code


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("late_failure", ["read", "restore"])
def test_isolated_recovered_post_recorder_error_still_closes_completion(
    observer_control, monkeypatch, source_fails, late_failure
):
    context = observer_control
    getters, setters = (sys.getprofile, sys.gettrace), (sys.setprofile, sys.settrace)
    before = (getters[0](), getters[1]())
    primary, cause = ArithmeticError("source primary"), KeyError("source cause")
    capture = OSError("late cleanup failure despite recovered hooks")
    injected = []

    def get_profile():
        if context.cleanup_phase == "post_record_restore" and not injected:
            injected.append("read")
            if late_failure == "read":
                raise capture
            return object()  # Force a real, independently protected restore.
        return getters[0]()

    def set_profile(value):
        setters[0](value)
        if context.cleanup_phase == "post_record_restore" and late_failure == "restore":
            injected.append("restore")
            raise capture  # Identity recovered, observation still failed.

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "getprofile", get_profile)
            patch.setattr(sys, "setprofile", set_profile)
            expected = ArithmeticError if source_fails else stage.literal._CaptureStop
            with _active(context), pytest.raises(expected) as caught:
                with stage._account(context):
                    if source_fails:
                        raise primary from cause
        if source_fails:
            assert caught.value is primary and primary.__cause__ is cause
        assert injected and context.invalid and context.observation_error is capture
        assert any(row[1] is capture for row in context.cleanup_errors)
        assert context.hook_identities_restored is True
        assert context.hook_samples == (before, before)
        assert getters[0]() is before[0] and getters[1]() is before[1]
    finally:
        setters[1](before[1])
        setters[0](before[0])


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("late_action", ["restore", "final_read"])
def test_isolated_last_trace_action_cannot_leave_stale_profile_success(
    observer_control, monkeypatch, source_fails, late_action
):
    context = observer_control
    getters, setters = (sys.getprofile, sys.gettrace), (sys.setprofile, sys.settrace)
    before = (getters[0](), getters[1]())
    primary, cause = ArithmeticError("primary"), KeyError("cause")
    forced, retargeted = [], []

    def get_trace():
        if (context.cleanup_phase == "post_record_restore" and not forced
                and late_action == "restore"):
            forced.append("trace read requires restore")
            return object()
        value = getters[1]()
        if (context.cleanup_phase == "final_sample" and not retargeted
                and late_action == "final_read"):
            setters[0](None)
            retargeted.append("trace getter disabled earlier sampled profile")
        return value

    def set_trace(value):
        setters[1](value)
        if context.cleanup_phase == "post_record_restore" and late_action == "restore":
            setters[0](None)
            retargeted.append("trace setter disabled earlier restored profile")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "gettrace", get_trace)
            patch.setattr(sys, "settrace", set_trace)
            expected = ArithmeticError if source_fails else stage.literal._CaptureStop
            with _active(context), pytest.raises(expected) as caught:
                with stage._account(context):
                    if source_fails:
                        raise primary from cause
        if source_fails:
            assert caught.value is primary and primary.__cause__ is cause
        assert retargeted and context.hook_identities_restored is False
        if late_action == "final_read":
            assert context.hook_samples[0] == before  # First pair alone is misleading.
        else:
            assert forced
        assert context.invalid and context.hook_after[0] is None
        assert any(row[0] == "final_hook_identity_mismatch" for row in context.cleanup_errors)
    finally:
        setters[1](before[1])
        setters[0](before[0])


@pytest.mark.parametrize("source_fails", [False, True])
def test_isolated_rejected_attempt_append_cannot_skip_either_restore(
    observer_control, monkeypatch, source_fails
):
    context = observer_control
    getters, setters = (sys.getprofile, sys.gettrace), (sys.setprofile, sys.settrace)
    before = (getters[0](), getters[1]())
    primary, cause, recording = ArithmeticError("primary"), KeyError("cause"), OSError("append")
    restored = []

    class RejectedAttempts(list):
        def append(self, value):
            raise recording

    def setter(index, value):
        if value is before[index]:
            restored.append(index)
        setters[index](value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "setprofile", lambda value: setter(0, value))
            patch.setattr(sys, "settrace", lambda value: setter(1, value))
            expected = ArithmeticError if source_fails else stage.literal._CaptureStop
            with _active(context), pytest.raises(expected) as caught:
                with stage._account(context):
                    context.hook_attempts = RejectedAttempts(context.hook_attempts)
                    if source_fails:
                        raise primary from cause
        if source_fails:
            assert caught.value is primary and primary.__cause__ is cause
        assert 0 in restored and 1 in restored
        assert context.hook_identities_restored is True and context.invalid
        assert context.observation_error is recording
        names = {row[0] for row in context.cleanup_errors if row[1] is recording}
        assert {"trace_restore_attempt", "profile_restore_attempt"} <= names
    finally:
        setters[1](before[1])
        setters[0](before[0])


def _virtual_runner_child(monkeypatch, tmp_path):
    """Virtual hook records only; no test collection or prefix owner is issued."""
    from validation.betse import betse_native_seed_world_prefix_software as runner

    state, before, calls = runner._run_state(), (object(), object()), []
    actual = [before[0], before[1]]
    (tmp_path / "inputs.json").write_text(json.dumps(dict(
        software_release_requested=True, snapshot_sha256="metadata-only",
    )))
    manifest = {"files": {name: {"sha256": "metadata-only"} for name in runner.OWNED}}
    monkeypatch.setattr(runner.snapshot, "verify", lambda *args, **kwargs: manifest)
    monkeypatch.setattr(runner.snapshot, "digest", lambda path: "metadata-only")
    monkeypatch.setattr(runner, "_run_state", lambda: state)
    monkeypatch.setattr(runner, "_write_evidence", lambda *args: None)
    monkeypatch.setattr(pytest, "main", lambda *args, **kwargs: 0)
    monkeypatch.setenv(runner.SOFTWARE_RELEASE, "1")

    def setter(index, value):
        calls.append((state.cleanup_phase, index, value))
        actual[index] = value

    monkeypatch.setattr(sys, "getprofile", lambda: actual[0])
    monkeypatch.setattr(sys, "gettrace", lambda: actual[1])
    monkeypatch.setattr(sys, "setprofile", lambda value: setter(0, value))
    monkeypatch.setattr(sys, "settrace", lambda value: setter(1, value))
    return runner, state, before, actual, calls


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("late_failure", ["read", "restore"])
def test_isolated_runner_recovered_late_error_remains_failed(
    monkeypatch, tmp_path, source_fails, late_failure
):
    primary, cause, capture = _FalseFailure("primary"), KeyError("cause"), OSError("late cleanup")
    primary.__cause__ = cause
    issued = tuple(stage._ISSUED.items())
    with monkeypatch.context() as patch:
        runner, state, before, actual, calls = _virtual_runner_child(patch, tmp_path)
        if source_fails:
            state.primary, state.primary_stage = primary, "original software failure"
        injected = []

        def get_profile():
            if state.cleanup_phase == "post_evidence_restore" and not injected:
                injected.append("read")
                if late_failure == "read":
                    raise capture
                return object()
            return actual[0]

        def set_profile(value):
            calls.append((state.cleanup_phase, 0, value))
            actual[0] = value
            if state.cleanup_phase == "post_evidence_restore" and late_failure == "restore":
                raise capture  # Restored identity cannot erase the failed action.

        patch.setattr(sys, "getprofile", get_profile)
        patch.setattr(sys, "setprofile", set_profile)
        if source_fails:
            with pytest.raises(_FalseFailure) as caught:
                runner.child(tmp_path, "metadata-only")
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert runner.child(tmp_path, "metadata-only") == 1
        assert injected and any(row[1] is capture for row in state.cleanup_errors)
        assert state.hooks_restored is True and state.hook_samples == (before, before)
        assert actual[0] is before[0] and actual[1] is before[1]
    assert tuple(stage._ISSUED.items()) == issued


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("late_action", ["restore", "final_read"])
def test_isolated_runner_samples_profile_after_last_trace_action(
    monkeypatch, tmp_path, source_fails, late_action
):
    primary, cause = _FalseFailure("primary"), KeyError("cause")
    primary.__cause__ = cause
    with monkeypatch.context() as patch:
        runner, state, before, actual, calls = _virtual_runner_child(patch, tmp_path)
        if source_fails:
            state.primary, state.primary_stage = primary, "original software failure"
        retargeted = []

        def evidence(*args):
            if late_action == "restore":
                actual[1] = object()  # A late writer changed only the trace.

        def get_trace():
            value = actual[1]
            if (state.cleanup_phase == "post_evidence_final_sample" and not retargeted
                    and late_action == "final_read"):
                actual[0] = None
                retargeted.append("trace getter disabled earlier sampled profile")
            return value

        def set_trace(value):
            calls.append((state.cleanup_phase, 1, value))
            actual[1] = value
            if state.cleanup_phase == "post_evidence_restore" and late_action == "restore":
                actual[0] = None  # Invalidates the earlier profile identity.
                retargeted.append("trace setter disabled earlier restored profile")

        patch.setattr(runner, "_write_evidence", evidence)
        patch.setattr(sys, "gettrace", get_trace)
        patch.setattr(sys, "settrace", set_trace)
        if source_fails:
            with pytest.raises(_FalseFailure) as caught:
                runner.child(tmp_path, "metadata-only")
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert runner.child(tmp_path, "metadata-only") == 1
        assert retargeted and state.hooks_restored is False and state.hook_after[0] is None
        assert state.hook_after[1] is before[1]
        if late_action == "final_read":
            assert state.hook_samples[0] == before
        assert any(row[0] == "final_hook_identity_mismatch" for row in state.cleanup_errors)


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.parametrize("where", ["restore", "emergency_restore", "post_evidence_restore"])
def test_isolated_runner_attempt_record_rejection_cannot_skip_setters(
    monkeypatch, tmp_path, source_fails, where
):
    primary, cause = _FalseFailure("primary"), KeyError("cause")
    primary.__cause__ = cause
    recording, entry = OSError("attempt bookkeeping"), LookupError("restore helper entry")

    class RejectedAttempts:
        def __iter__(self):
            raise recording

    with monkeypatch.context() as patch:
        runner, state, before, actual, calls = _virtual_runner_child(patch, tmp_path)
        if source_fails:
            state.primary, state.primary_stage = primary, "original software failure"
        if where == "post_evidence_restore":
            def evidence(*args):
                state.hook_attempts = RejectedAttempts()
                actual[:] = [object(), object()]

            patch.setattr(runner, "_write_evidence", evidence)
        else:
            state.hook_attempts = RejectedAttempts()
            if where == "emergency_restore":
                def reject(*args, **kwargs):
                    raise entry

                patch.setattr(runner, "_restore_hooks", reject)
        if source_fails:
            with pytest.raises(_FalseFailure) as caught:
                runner.child(tmp_path, "metadata-only")
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert runner.child(tmp_path, "metadata-only") == 1
        attempted = {index for phase, index, value in calls
                     if phase == where and value is before[index]}
        assert attempted == {0, 1}
        assert actual[0] is before[0] and actual[1] is before[1]
        assert state.hooks_restored is True
        assert any(row[1] is recording for row in state.cleanup_errors)
        if where == "emergency_restore":
            assert any(row[1] is entry for row in state.cleanup_errors)
