"""Blocked source/ordinal/ancestry controls; no positive owner is fabricated."""

import ast
import builtins
import sys
from dataclasses import replace
from pathlib import Path
from types import FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_init_dynamics_completion as completion
from cells.processes import betse_native_init_molecule_short_runtime as stage
from cells.processes import betse_native_init_retained_world as retained
from cells.processes import betse_native_init_short_history as consumer
from tests.unit import test_betse_native_init_molecule_wrapper_authority as inherited
from validation.betse import betse_native_init_molecule_short_runtime_software as runner


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    original = inherited.inherited.inherited.inherited._blocked_generator
    generator = FunctionType(
        original.__code__,
        dict(original.__globals__, stage=NS(_ACTIVE=[], _FAILED=[]), runner=runner),
    )(request, tmp_path, monkeypatch)
    before, entered, primary = (sys.getprofile(), sys.gettrace()), False, None
    try:
        next(generator)
        entered = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        drain = inherited.inherited.inherited.inherited.cleanup._drain_guard
        FunctionType(
            drain.__code__, dict(drain.__globals__, _write_failure_diagnostics=lambda *args: None)
        )(generator, entered, (), tmp_path, required_hooks=before, primary=primary)


@pytest.mark.parametrize("count", (0, -1, 65, True, 1.0, None))
def test_exact_finite_integer_budget_is_not_a_parent_or_numeric_state(count):
    with pytest.raises(ValueError):
        stage._Iterations(count)
    assert not stage._RUNTIME and not stage._BOUND


def test_reused_prepare_resolves_this_exact_runner_and_its_owned_snapshot_scope():
    namespace = runner._namespace()
    assert namespace["_scope"] is runner._scope
    selected = namespace["_scope"]()
    assert selected["FILE"] == runner.FILE
    assert selected["SOURCE"] == runner.SOURCE and selected["TEST"] == runner.TEST
    assert selected["OWNED"] == runner.OWNED and selected["SOFTWARE_CPU"] == 5


def test_real_source_preparation_remains_before_any_foreign_parent_access():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("An unadopted source cannot inspect a supplied parent")

    foreign = Foreign()
    with pytest.raises(stage.ShortRuntimeRejected) as caught:
        stage.bind_short_history(
            foreign,
            completion=foreign,
            storage=foreign,
            electrical=foreign,
            child=foreign,
            iterations=2,
        )
    assert caught.value.stage == "held"
    assert not stage._RUNTIME and not stage._BOUND


@pytest.mark.parametrize(
    "name",
    (
        "session_of",
        "session_provider",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "validate_runtime_active",
        "validate_runtime",
    ),
)
def test_records_and_dictionaries_are_not_actual_runtime_claims(name):
    function = vars(stage)[name]
    with pytest.raises(stage.ShortRuntimeRejected) as caught:
        if name in ("runtime_members", "runtime_codes", "runtime_permissions"):
            function({})
        else:
            function({}, child={})
    assert caught.value.stage == "claim"


@pytest.mark.parametrize("count", (1, 2, 64))
def test_metadata_ledger_preserves_contiguous_absolute_ordinals_and_objects(count):
    ledger, records = stage._Iterations(count), []
    frame = object()
    for ordinal in range(count):
        label = float(ordinal)
        sampled = ordinal % 2 == 0
        key = (float, stage.struct.pack("!d", label))
        ledger.begin(ordinal, label, key, frame, sampled, (0, 0, 0))
        record = stage.IterationEvidence(
            ordinal, label, frame, sampled, (), (), (), (), "local-probe"
        )
        ledger.end(record)
        records.append(record)
    assert ledger.current is None and not ledger.invalid
    assert all(a is b for a, b in zip(ledger.records, records, strict=True))
    with pytest.raises(ValueError):
        ledger.begin(count, float(count), (), frame, False, (0, 0, 0))
    assert ledger.invalid
    assert not stage._RUNTIME and not stage._BOUND


@pytest.mark.parametrize(
    "drift", ("skip", "duplicate", "time_copy", "frame", "sample", "ordinal_type")
)
def test_metadata_iteration_pairing_cannot_omit_duplicate_or_replace_authorities(drift):
    ledger, label, frame = stage._Iterations(2), float("0.125"), object()
    record = stage.IterationEvidence(0, label, frame, False, (), (), (), (), "local-probe")
    if drift == "skip":
        with pytest.raises(ValueError):
            ledger.begin(1, label, (), frame, False, (0, 0, 0))
    else:
        ledger.begin(0, label, (), frame, False, (0, 0, 0))
        if drift == "duplicate":
            with pytest.raises(ValueError):
                ledger.begin(0, label, (), frame, False, (0, 0, 0))
        else:
            changes = {
                "time_copy": dict(source_time=float("0.125")),
                "frame": dict(source_frame=object()),
                "sample": dict(sampled=True),
                "ordinal_type": dict(ordinal=False),
            }
            with pytest.raises(ValueError):
                ledger.end(replace(record, **changes[drift]))
    assert ledger.invalid and not ledger.records


@pytest.mark.parametrize("value", (float("nan"), float("inf"), -float("inf"), True, 0, object()))
def test_original_time_metadata_rejects_nonfinite_or_foreign_scalar_types(value):
    runtime = NS(completion=NS(numpy=np), primary=None, invalid=False)
    with pytest.raises(stage.base.MoleculeNetworkRejected):
        stage._time_key(runtime, value)
    assert runtime.invalid


def test_time_metadata_keeps_numpy_category_and_signed_zero_bits():
    runtime = NS(completion=NS(numpy=np), primary=None, invalid=False)
    assert stage._time_key(runtime, 0.0) != stage._time_key(runtime, -0.0)
    assert stage._time_key(runtime, np.float64(0.0)) != stage._time_key(runtime, 0.0)


def test_observer_and_ion_bodies_are_reused_without_equation_or_type_alias_changes():
    names = (
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "observe_runtime",
        "observes_runtime_frame",
        "runtime_wrapper_guard",
        "runtime_dispatch",
    )
    for name in names:
        current, original = vars(stage)[name], vars(stage.base)[name]
        assert current is not original and current.__code__ is not original.__code__
        assert current.__globals__ is vars(stage) and original.__globals__ is vars(stage.base)
        assert stage._BODIES[name].__code__ is original.__code__
    assert stage.ShortMoleculeRuntimeClaim is not stage.base.MoleculeRuntimeClaim
    assert consumer.RUNTIME_SOURCE_SHA256 is None and consumer.RUNTIME_BEGIN is None
    assert stage.MAX_WORK == stage.base.MAX_WORK


def test_current_public_api_has_exact_local_function_definitions_for_source_proof():
    path = Path(stage.__file__)
    names = (
        "bind_short_history",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "observe_runtime",
        "observes_runtime_frame",
        "runtime_wrapper_guard",
        "runtime_dispatch",
        "begin_iteration",
        "finish_iteration",
        "finish_runtime",
        "validate_iteration",
        "validate_runtime_active",
        "validate_runtime",
        "session_of",
        "session_provider",
        "runtime_failed_context",
    )
    definitions = {
        node.name for node in ast.parse(path.read_bytes()).body if isinstance(node, ast.FunctionDef)
    }
    assert set(names) <= definitions
    stage.interfaces._source_interface(stage, path.read_bytes(), path, names)


@pytest.mark.parametrize("slot", stage.CONSUMER_BACK_REFERENCE_SLOTS)
def test_consumer_exact_byte_interface_excludes_only_declared_literal_backrefs(slot):
    raw = Path(consumer.__file__).read_bytes()
    identity, before = stage.consumer_binding(raw)
    tree = ast.parse(raw)
    node = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == slot
    )
    assert isinstance(node.value, ast.Constant) and node.value.value is None
    lines = raw.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    start, end = (
        offsets[node.value.lineno - 1] + node.value.col_offset,
        offsets[node.value.end_lineno - 1] + node.value.end_col_offset,
    )
    changed = raw[:start] + repr("a" * 64).encode() + raw[end:]
    after_identity, after = stage.consumer_binding(changed)
    assert after_identity == identity
    assert dict(before)[slot] is None and dict(after)[slot] == "a" * 64
    assert stage.consumer_binding(raw + b"\n# byte-drift-control\n")[0] != identity


def test_consumer_nonliteral_or_duplicate_backref_never_becomes_a_source_interface():
    raw = Path(consumer.__file__).read_bytes()
    slot = stage.CONSUMER_BACK_REFERENCE_SLOTS[0]
    for changed in (
        raw.replace((slot + " = None").encode(), (slot + " = str(None)").encode(), 1),
        raw + ("\n" + slot + " = None\n").encode(),
    ):
        assert changed != raw
        with pytest.raises(ValueError):
            stage.consumer_binding(changed)


def _rewrite_literals(payload, **values):
    """Metadata image editing only; every other source byte stays exact."""
    for name, value in values.items():
        tree = ast.parse(payload)
        assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ]
        assert len(assignments) == 1
        node = assignments[0].value
        assert isinstance(node, ast.Constant) and node.lineno == node.end_lineno
        lines = payload.splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        start = offsets[node.lineno - 1] + node.col_offset
        stop = offsets[node.end_lineno - 1] + node.end_col_offset
        payload = payload[:start] + repr(value).encode() + payload[stop:]
    return payload


def _literal(payload, name):
    matches = [
        node.value
        for node in ast.parse(payload).body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == name
    ]
    assert len(matches) == 1
    return ast.literal_eval(matches[0])


def _topological_metadata_images():
    """No import/adoption: close the reported edges using declared source bytes."""

    def digest(payload):
        return stage.hashlib.sha256(payload).hexdigest()

    # These labels are synthetic review tokens, never real review/admission.
    reviews = {
        name: digest(("metadata-only-unaccepted-" + name).encode())
        for name in ("network", "runtime", "completion", "consumer", "electrical")
    }
    network = _rewrite_literals(
        Path(stage.base.__file__).read_bytes(),
        CONTRACT=stage.base.PROPOSED_CONTRACT,
        COMPLETION_REVIEW_SHA256=reviews["completion"],
    )
    child = _rewrite_literals(Path(consumer.__file__).read_bytes(), RUNTIME_CONTRACT=stage.LAW_ID)
    network_identity = stage.base_binding(network)[0]
    runtime = _rewrite_literals(
        Path(stage.__file__).read_bytes(),
        BASE_INTERFACE_SHA256=network_identity,
        BASE_REVIEW_SHA256=reviews["network"],
        CONSUMER_INTERFACE_SHA256=stage.consumer_binding(child)[0],
        CONSUMER_REVIEW_SHA256=reviews["consumer"],
    )
    complete = _rewrite_literals(
        Path(completion.__file__).read_bytes(),
        MOLECULE_INTERFACE_SHA256=network_identity,
        MOLECULE_REVIEW_SHA256=reviews["network"],
        SHORT_RUNTIME_SHA256=digest(runtime),
        SHORT_RUNTIME_REVIEW_SHA256=reviews["runtime"],
    )
    network = _rewrite_literals(network, COMPLETION_SOURCE_SHA256=digest(complete))
    child = _rewrite_literals(
        child,
        PARENT_SOURCE_SHA256=digest(Path(consumer.base.previous.__file__).read_bytes()),
        PARENT_REVIEW_SHA256=reviews["electrical"],
        RUNTIME_SOURCE_SHA256=digest(runtime),
        RUNTIME_REVIEW_SHA256=reviews["runtime"],
    )
    return network, runtime, complete, child, reviews


def test_three_producer_backrefs_fill_topologically_without_fixed_point_or_live_adoption():
    network, runtime, complete, child, reviews = _topological_metadata_images()
    identity, backrefs = stage.base_binding(network)
    stage._check_base_backrefs(backrefs, complete, reviews["completion"])
    assert identity == _literal(runtime, "BASE_INTERFACE_SHA256")
    assert identity == _literal(complete, "MOLECULE_INTERFACE_SHA256")
    assert _literal(complete, "SHORT_RUNTIME_SHA256") == stage.hashlib.sha256(runtime).hexdigest()
    assert (
        _literal(network, "COMPLETION_SOURCE_SHA256") == stage.hashlib.sha256(complete).hexdigest()
    )
    assert _literal(runtime, "BASE_REVIEW_SHA256") == _literal(complete, "MOLECULE_REVIEW_SHA256")
    assert stage.consumer_binding(child)[0] == _literal(runtime, "CONSUMER_INTERFACE_SHA256")
    assert _literal(child, "RUNTIME_SOURCE_SHA256") == _literal(complete, "SHORT_RUNTIME_SHA256")
    assert _literal(child, "RUNTIME_REVIEW_SHA256") == _literal(
        complete, "SHORT_RUNTIME_REVIEW_SHA256"
    )
    # Completion's wrapper first enters its held ancestor readiness chain. The
    # exact recipe it selects is this existing pure byte binder; no ancestor
    # or native readiness is supplied/executed for a metadata proof.
    assert stage.BASE_BINDING_KIND == completion.MOLECULE_BINDING_KIND
    assert stage.BASE_BACK_REFERENCE_SLOTS == completion.MOLECULE_BACK_REFERENCE_SLOTS
    original_recipe = FunctionType(
        stage.interfaces._helper_binding.__code__,
        dict(
            vars(stage.interfaces),
            HELPER_BINDING_KIND=completion.MOLECULE_BINDING_KIND,
            HELPER_BACK_REFERENCE_SLOTS=completion.MOLECULE_BACK_REFERENCE_SLOTS,
        ),
    )
    assert original_recipe(network) == (identity, backrefs)
    assert stage.BASE_INTERFACE_SHA256 is completion.SHORT_RUNTIME_SHA256 is None
    assert stage.base.COMPLETION_SOURCE_SHA256 is consumer.RUNTIME_SOURCE_SHA256 is None
    assert not stage._RUNTIME and not stage._BOUND


@pytest.mark.parametrize("drift", ("source", "review", "body_byte"))
def test_excluded_network_values_still_require_full_actual_parent_and_review(drift):
    network, _, complete, _, reviews = _topological_metadata_images()
    identity, _ = stage.base_binding(network)
    if drift == "body_byte":
        changed = network + b"\n# non-excluded-byte\n"
        assert stage.base_binding(changed)[0] != identity
    else:
        slot = "COMPLETION_SOURCE_SHA256" if drift == "source" else "COMPLETION_REVIEW_SHA256"
        changed = _rewrite_literals(network, **{slot: "f" * 64})
        changed_identity, changed_backrefs = stage.base_binding(changed)
        assert changed_identity == identity
        with pytest.raises(ValueError, match="Exact full constructor source/review"):
            stage._check_base_backrefs(changed_backrefs, complete, reviews["completion"])


@pytest.mark.parametrize("slot", stage.BASE_BACK_REFERENCE_SLOTS)
@pytest.mark.parametrize("drift", ("expression", "duplicate"))
def test_network_interface_refuses_nonliteral_or_duplicated_backrefs(slot, drift):
    raw = Path(stage.base.__file__).read_bytes()
    if drift == "expression":
        changed = raw.replace((slot + " = None").encode(), (slot + " = str(None)").encode(), 1)
    else:
        changed = raw + ("\n" + slot + " = None\n").encode()
    assert changed != raw
    with pytest.raises(ValueError):
        stage.base_binding(changed)


@pytest.mark.parametrize("mode", ("direct", "foreign", "capture_error"))
def test_real_observer_adapter_stack_keeps_raw_return_before_fallible_audit(monkeypatch, mode):
    """Private registry/frame model only; no parent/source capability is issued."""
    claim = object.__new__(stage.ShortMoleculeRuntimeClaim)
    frame = sys._getframe()
    child = NS(observer_namespace={})
    runtime = NS(
        claim=claim,
        child=child,
        active=True,
        invalid=False,
        primary=None,
        primary_origin=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        raw_returns=[],
        work=[],
        c_calls=[],
        pending={},
        source_exceptions=[],
        frames={id(frame): dict(frame=frame, returned=False)},
        original=NS(initial=NS(_normal_return=lambda frame: True)),
    )
    monkeypatch.setitem(stage._RUNTIME, claim, runtime)
    failure = KeyError("independent source audit")

    def route(value):
        if mode == "capture_error":
            raise failure
        return value

    monkeypatch.setattr(stage, "_route", route)

    def child_observer(context, frame, event, arg):
        return stage.observe_runtime(claim, child=context, frame=frame, event=event, arg=arg)

    def foreign_reporter(context, frame, event, arg):
        return stage.observe_runtime(claim, child=context, frame=frame, event=event, arg=arg)

    child.observer_namespace["_observe"] = child_observer
    reporter = foreign_reporter if mode == "foreign" else child_observer
    if mode == "direct":
        reporter(child, frame, "return", None)
        assert runtime.raw_returns == [(frame, None)]
        assert runtime.frames[id(frame)]["returned"] is True
    else:
        with pytest.raises(stage.CaptureStop):
            reporter(child, frame, "return", None)
        assert runtime.last_raw == (frame, None)
        assert runtime.capture_error is not None
        if mode == "capture_error":
            assert runtime.capture_error is failure
    assert runtime.report is None


@pytest.mark.parametrize("drift", ("none", "copy", "time_copy", "mutated_identity"))
def test_closed_iteration_validation_returns_only_the_original_record_without_reopening(
    monkeypatch, drift
):
    label, child, frame = float("0.125"), object(), object()
    ledger = stage._Iterations(1)
    row = stage.IterationEvidence(0, label, frame, False, (), (), (), (), "")

    def digest(value):
        return repr(value)

    row = replace(row, identity=digest(stage._iteration_data(row)))
    ledger.begin(0, label, (float, stage.struct.pack("!d", label)), frame, False, (0, 0, 0))
    ledger.end(row)
    runtime = NS(
        child=child,
        original=NS(api=NS(_digest=digest)),
        ledger=ledger,
        completion=NS(numpy=np),
        invalid=False,
        primary=None,
        active=False,
    )
    monkeypatch.setattr(stage, "_runtime_context", lambda claim: runtime)
    actual, clock = row, label
    if drift == "copy":
        actual = replace(row)
    elif drift == "time_copy":
        clock = float("0.125")
    elif drift == "mutated_identity":
        object.__setattr__(row, "identity", "foreign")
    if drift == "none":
        assert (
            stage.validate_iteration(None, actual, child=child, ordinal=0, source_time=clock) is row
        )
        assert runtime.active is False and len(ledger.records) == 1
    else:
        with pytest.raises(stage.base.MoleculeNetworkRejected):
            stage.validate_iteration(None, actual, child=child, ordinal=0, source_time=clock)
        assert runtime.active is False and runtime.invalid


@pytest.mark.parametrize(
    "drift", ("table_copy", "member", "same_code_copy", "body_code", "original_export")
)
def test_delegate_table_retarget_refuses_before_any_delegate_or_parent_access(monkeypatch, drift):
    calls = []
    original = stage._BODIES["runtime_members"]

    def foreign(*args, **kwargs):
        calls.append("foreign")
        pytest.fail("Retargeted runtime body must not execute")

    if drift == "table_copy":
        monkeypatch.setattr(stage, "_BODIES", dict(stage._BODIES))
    elif drift == "member":
        monkeypatch.setitem(stage._BODIES, "runtime_members", foreign)
    elif drift == "same_code_copy":
        copied = FunctionType(original.__code__, original.__globals__)
        monkeypatch.setitem(stage._BODIES, "runtime_members", copied)
    elif drift == "body_code":
        monkeypatch.setattr(original, "__code__", (lambda *args: None).__code__)
    else:
        monkeypatch.setattr(stage.base, "runtime_members", foreign)
    with pytest.raises(stage.ShortRuntimeRejected) as caught:
        stage.runtime_members(object())
    assert caught.value.stage == "delegate" and not calls


@pytest.mark.parametrize("event", ("return", "exception", "c_exception"))
def test_retargeted_observer_never_runs_and_keeps_raw_or_original_unwind(monkeypatch, event):
    claim = object.__new__(stage.ShortMoleculeRuntimeClaim)
    primary = ValueError("actual toy source error")
    primary.__cause__ = KeyError("source cause")
    frame = sys._getframe()
    runtime = NS(
        claim=claim,
        child=object(),
        active=True,
        invalid=False,
        primary=None,
        primary_origin=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        original=NS(initial=NS(_normal_return=lambda frame: True)),
        pending={},
    )
    monkeypatch.setitem(stage._RUNTIME, claim, runtime)

    def foreign(*args, **kwargs):
        pytest.fail("Retargeted observer must not execute")

    monkeypatch.setitem(stage._BODIES, "observe_runtime", foreign)
    arg = (
        (type(primary), primary, None)
        if event == "exception"
        else (len if event == "c_exception" else None)
    )
    if event == "return":
        with pytest.raises(stage.CaptureStop):
            stage.observe_runtime(claim, child=runtime.child, frame=frame, event=event, arg=arg)
        assert runtime.last_raw == (frame, None)
    else:
        stage.observe_runtime(claim, child=runtime.child, frame=frame, event=event, arg=arg)
        if event == "exception":
            assert runtime.primary is primary and primary.__cause__.args == ("source cause",)
    assert runtime.invalid and runtime.capture_error is not None and runtime.report is None


@pytest.mark.parametrize("mode", ("ordinary", "falsey", "cause", "handled_normal"))
def test_installed_trace_keeps_exact_unwind_before_return_delegate_audit(monkeypatch, mode):
    """Real CPython exception/return events, private frame model, no source body."""

    class FalseyError(ValueError):
        def __bool__(self):
            return False

    primary = FalseyError("falsey source") if mode == "falsey" else ValueError("source primary")
    cause = KeyError("source cause")
    if mode == "cause":
        primary.__cause__ = cause
    normal_value, observations, foreign_calls = object(), [], []

    def source():
        if mode == "handled_normal":
            try:
                raise primary
            except ValueError:
                return normal_value
        raise primary

    claim = object.__new__(stage.ShortMoleculeRuntimeClaim)
    child = NS(observer_namespace={})
    runtime = NS(
        claim=claim,
        child=child,
        active=True,
        invalid=False,
        primary=None,
        primary_origin=None,
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        raw_returns=[],
        work=[],
        c_calls=[],
        pending={},
        source_exceptions=[],
        frames={},
        original=NS(initial=NS(_normal_return=retained._normal_return)),
    )
    monkeypatch.setitem(stage._RUNTIME, claim, runtime)
    monkeypatch.setattr(stage, "_route", lambda value: value)

    def foreign(*args, **kwargs):
        foreign_calls.append(True)
        pytest.fail("Retargeted delegate must never execute")

    def child_observer(context, frame, event, arg):
        return stage.observe_runtime(claim, child=context, frame=frame, event=event, arg=arg)

    child.observer_namespace["_observe"] = child_observer
    prior_profile, prior_trace = sys.getprofile(), sys.gettrace()

    def trace(frame, event, arg):
        inherited_trace = None if prior_trace is None else prior_trace(frame, event, arg)
        if frame.f_code is not source.__code__:
            return inherited_trace
        assert event == "call"
        runtime.frames[id(frame)] = dict(frame=frame, returned=False)

        def local(frame, event, arg):
            nonlocal inherited_trace
            if inherited_trace is not None:
                inherited_trace = inherited_trace(frame, event, arg)
            if event == "return":
                observations.append((event, retained._normal_return(frame), arg))
                monkeypatch.setitem(stage._BODIES, "observe_runtime", foreign)
            if event in ("exception", "return"):
                child_observer(child, frame, event, arg)
            return local

        return local

    try:
        sys.settrace(trace)
        if mode == "handled_normal":
            with pytest.raises(stage.CaptureStop) as caught:
                source()
            assert runtime.primary is None and runtime.primary_origin is None
            assert caught.value.__cause__ is runtime.capture_error
        else:
            with pytest.raises(type(primary)) as caught:
                source()
            assert caught.value is runtime.primary is primary
            assert runtime.primary_origin == "source"
            if mode == "cause":
                assert primary.__cause__ is cause
    finally:
        sys.settrace(prior_trace)
        sys.setprofile(prior_profile)
    expected_return = normal_value if mode == "handled_normal" else None
    assert observations == [("return", mode == "handled_normal", expected_return)]
    assert runtime.pending[id(runtime.last_raw[0])] is primary
    assert runtime.last_raw[1] is expected_return
    assert runtime.source_exceptions == [(runtime.last_raw[0], primary)]
    assert isinstance(runtime.capture_error, stage.ShortRuntimeRejected)
    assert runtime.capture_errors[-1][0] == "observer_delegate"
    assert runtime.capture_errors[-1][1] is runtime.capture_error
    assert runtime.capture_errors[-1][2][0] is runtime.last_raw[0]
    assert runtime.report is None and runtime.invalid and not foreign_calls
    assert sys.getprofile() is prior_profile and sys.gettrace() is prior_trace


@pytest.mark.parametrize("which", ("network", "wrapper"))
def test_pilot_module_metadata_is_bound_as_module_metadata_without_executing_helper(which):
    def original():
        return __name__, __doc__, __package__, __loader__, __spec__

    namespace = dict(
        __builtins__=vars(builtins),
        __name__="declared_module",
        __doc__="declared documentation",
        __package__="declared_package",
        __loader__=object(),
        __spec__=object(),
    )
    function = FunctionType(original.__code__, namespace)
    binding = (
        stage.base._function_bindings
        if which == "network"
        else stage.base.wrapper_authority._function_state
    )
    before = binding(function)
    assert namespace["__name__"] is not vars(builtins)["__name__"]
    assert any(value is namespace["__name__"] for value in before)
    namespace["__name__"] = "foreign_module"
    with pytest.raises(ValueError):
        stage.base.wrapper_authority._same(binding(function), before)


@pytest.mark.parametrize("which", ("network", "wrapper"))
@pytest.mark.parametrize("drift", ("len", "cached_builtins"))
def test_module_metadata_exception_does_not_relax_callable_or_cached_builtin_checks(which, drift):
    def original(value):
        return len(value), __name__

    namespace = dict(__builtins__=vars(builtins), __name__="declared_module")
    function = FunctionType(original.__code__, namespace)
    binding = (
        stage.base._function_bindings
        if which == "network"
        else stage.base.wrapper_authority._function_state
    )
    binding(function)
    if drift == "len":
        namespace["len"] = lambda value: pytest.fail("Foreign builtin must not execute")
    else:
        namespace["__builtins__"] = dict(vars(builtins))
    with pytest.raises(ValueError):
        binding(function)


@pytest.mark.parametrize("mode", ("ordinary", "short", "both", "unissued_short"))
def test_completion_projection_selects_real_short_lease_without_casting_old_lease(
    monkeypatch, mode
):
    class Owner:
        pass

    owner, old, new = Owner(), object(), object()
    context = NS(owner=owner)
    if mode in ("ordinary", "both"):
        context.first_step_descendant = old
    if mode in ("short", "both", "unissued_short"):
        context.short_init_descendant = new
        if mode != "unissued_short":
            monkeypatch.setitem(completion._SHORT_INIT_DESCENDANTS, owner, new)
    if mode in ("both", "unissued_short"):
        with pytest.raises(ValueError):
            completion._advance_lease(context)
    else:
        assert completion._advance_lease(context) is (old if mode == "ordinary" else new)


@pytest.mark.parametrize("mode", ("none", "ordinary", "short", "both"))
def test_retained_dispatch_chooses_one_actual_child_without_rearming(mode, monkeypatch):
    old, new = object(), object()
    electrical = NS()
    if mode in ("ordinary", "both"):
        electrical.first_step_transition = old
    if mode in ("short", "both"):
        electrical.short_init_transition = new
    if mode == "both":

        def refuse(*args):
            raise ValueError("overlap")

        monkeypatch.setattr(retained, "_reject", refuse)
        with pytest.raises(ValueError, match="overlap"):
            retained._advance_child(NS(), electrical)
    else:
        actual, route = retained._advance_child(NS(), electrical)
        assert actual is ({"none": None, "ordinary": old, "short": new}[mode])
        assert route is (
            retained._short_init_runtime if mode == "short" else retained._first_step_runtime
        )


@pytest.mark.parametrize(
    "module",
    (
        stage.base,
        stage.base.channels,
        stage.base.channel_source,
        stage.base.wrapper_authority,
        stage,
    ),
)
def test_actual_provider_helper_namespaces_bind_without_executing_any_helper(module):
    """Real current definitions, including actual_functions, not a toy name list."""
    checked = []
    for name, function in vars(module).items():
        if type(function) is FunctionType and function.__globals__ is vars(module):
            namespace = stage.base._function_bindings(function)
            state = stage.base.wrapper_authority._function_state(function)
            assert namespace[0] is state[0] is function
            assert function.__globals__ is vars(module)
            checked.append(name)
    assert checked
    if module is stage.base.channels:
        assert "actual_functions" in checked
    if module is stage.base:
        assert "_actual_functions" in checked
