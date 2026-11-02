"""Prepared dyna controls; only actual Key public claims can enable the path."""

import builtins
import json
import sys
from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_phase_dyna as stage
from tests.unit import test_betse_native_phase_caches as cache_controls
from validation.betse.betse_native_single_cell_core_synthetic import save


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    previous, trace, imported = sys.getprofile(), sys.gettrace(), builtins.__import__
    attempts = []
    codes = {
        stage._acquire.__code__,
        stage._ATTACH.__code__,
        *(fn.__code__ for fn in stage._NATIVE.values()),
        stage.caches._acquire.__code__,
        stage.caches._import_native.__code__,
        *(fn.__code__ for fn in stage.caches._METHODS.values()),
        stage.caches.previous._acquire.__code__,
        stage.caches.previous._PREFIX.__code__,
        stage.caches.previous._import_native.__code__,
        stage.handler._acquire.__code__,
        stage.handler.previous._load.__code__,
        stage.handler.previous.paths._upgrade.__code__,
        stage.handler.previous.paths._reload.__code__,
        stage.caches.previous.callbacks._acquire.__code__,
        stage.handler.previous.paths.prefix.parameters._acquire.__code__,
        stage.handler.previous.paths.prefix.parameters._invoke.__code__,
    }

    def profile(frame, event, arg):
        if event == "call" and (
            frame.f_code in codes
            or frame.f_code.co_filename.startswith(str(stage.aliases.NATIVE) + "/")
        ):
            attempts.append(frame.f_code.co_qualname)
            raise AssertionError("Actual source/native dyna/phase work forbidden")
        if previous is not None:
            previous(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith(("betse.", "ruamel")):
            attempts.append(name)
            raise AssertionError("Actual native import forbidden")
        return imported(name, *args, **kwargs)

    def rng(*args, **kwargs):
        attempts.append("RNG")
        raise AssertionError("Actual RNG forbidden")

    monkeypatch.setattr(builtins, "__import__", imports)
    for name in ("RandomState", "default_rng", "seed", "random", "uniform", "normal", "choice"):
        monkeypatch.setattr(stage.literal.callers.np.random, name, rng)
    sys.setprofile(profile)
    try:
        yield
        assert attempts == [] and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)
        (tmp_path / "native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempts,
                    actual_source_or_scientific_credit=0,
                )
            )
        )


@pytest.fixture(scope="module")
def plans():
    return cache_controls.plans.__wrapped__()


@pytest.fixture
def cache_parent(monkeypatch, tmp_path, plans):
    parent = cache_controls.parent.__wrapped__(monkeypatch, tmp_path, plans)
    prepared = cache_controls.controlled.__wrapped__(monkeypatch, parent)
    owner = stage.caches.prepare(prepared.request, enabled=True)
    return NS(owner=owner, context=stage.caches._ISSUED[owner], controlled=prepared)


@pytest.fixture
def ready(monkeypatch, request):
    # Never monkeypatch a claim issuer, inspection permission or Key producer.
    # Synthetic native providers run through the real issued API once supplied.
    try:
        api = stage._key_api()
        stage._cache_api()
    except stage.DynaRejected as error:
        pytest.skip("Real constructor/cache contract is not yet bound: " + error.stage)
    cache_parent = request.getfixturevalue("cache_parent")

    class Handler:
        def __init__(self, p):
            raise AssertionError("Unselected original constructor forbidden")

        def init_profiles(self, phase):
            raise AssertionError("Profiles forbidden")

        def redo_gj(self, *args):
            raise AssertionError("Gap-junction rebuild forbidden")

    def unselected_method(self, p):
        raise AssertionError("Original synthetic method must be privately delegated")

    for name in stage.METHODS:
        if name != "__init__":
            setattr(Handler, name, unselected_method)

    delegate_counts = {name: 0 for name in stage.METHODS}
    space = dict(delegate_counts=delegate_counts)
    exec(
        compile(
            """
def attach(self,p):
    self.dyna=TissueHandler(p=p)
def init(self,p):
    delegate_counts['__init__']+=1
    self.event_cut=None
    self._event_voltage=None
    self._wound_channel=None
    self._init_tissues(p)
    self._init_cuts(p)
    self._init_events(p)
def tissues(self,p):
    delegate_counts['_init_tissues']+=1
    self.parameter_argument=p
    self.tissue_name_to_profile=OrderedDict()
def cuts(self,p):
    delegate_counts['_init_cuts']+=1
    self.cut_name_to_profile=OrderedDict()
def events(self,p):
    delegate_counts['_init_events']+=1
    self._init_events_global(p)
def global_events(self,p):
    delegate_counts['_init_events_global']+=1
    self.global_parameter_argument=p
""",
            "<synthetic-phase-dyna>",
            "exec",
        ),
        space,
    )
    methods = dict(
        zip(
            stage.METHODS,
            (space[name] for name in ("init", "tissues", "cuts", "events", "global_events")),
            strict=True,
        )
    )

    def acquire(context):
        context.native_handler = Handler
        context.factories = {}
        context.symbols = {}
        context.modules = {}

    monkeypatch.setattr(stage, "_acquire", acquire)
    monkeypatch.setattr(stage, "_NATIVE", methods)
    monkeypatch.setattr(stage, "_ATTACH", space["attach"])
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setenv(api.RELEASE, "1")
    request = stage.from_cache(cache_parent.owner, law_id=stage.LAW_ID)
    return NS(parent=cache_parent, request=request, native=Handler, delegate_counts=delegate_counts)


@pytest.fixture
def refused(tmp_path):
    @contextmanager
    def check():
        with pytest.raises(stage.DynaRejected) as caught:
            yield caught
        error = caught.value
        partial = error.partial if type(error.partial) is dict else {}
        save(
            tmp_path,
            "refusal",
            dict(
                stage=error.stage,
                source=error.source_error,
                capture=error.capture_error,
                cause=error.__cause__,
                trial=error.trial,
                parent_trial=partial.get("parent_trial"),
                phase=partial.get("phase"),
                parameters=partial.get("parameters"),
                handler=partial.get("handler"),
                objects=partial.get("objects"),
                stages=partial.get("stages"),
                last_completed=partial.get("last_completed"),
                constructor_claim_error=partial.get("constructor_claim_error"),
                constructor_claim_record=partial.get("constructor_claim_record"),
                failed_constructor_claim_record=partial.get("failed_constructor_claim_record"),
                method_attempts=partial.get("method_attempts"),
                method_entries=partial.get("method_entries"),
                entry_error=partial.get("entry_error"),
            ),
        )

    return check


def test_preparation_literal_dyna_store_and_held_boundary():
    plan = stage.source_plan()
    assert plan["phase_store_lines"] == (186, 186)
    assert plan["handler_methods"] == stage.handler.METHODS
    assert plan["original_missing_event_stores_are_failures"] is True
    assert plan["full_phase_parameters_world_or_physical_or_checkpoint_admitted"] is False


@pytest.mark.parametrize("enabled,flag", [(False, "1"), (True, "0"), (1, "1")])
def test_preparation_release_precedes_claim_or_owner_work(monkeypatch, refused, enabled, flag):
    monkeypatch.setenv(stage.RELEASE, flag)
    with refused() as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release" and caught.value.trial is None


def test_preparation_unbound_key_contract_cannot_enter_inspection_or_native(monkeypatch, refused):
    def forbidden(*args, **kwargs):
        raise AssertionError("Inspection must never authorize a constructor")

    monkeypatch.setattr(stage, "KEY_SHA256", None)
    monkeypatch.setattr(stage.handler.claims, "inspection", forbidden)
    monkeypatch.setenv(stage.RELEASE, "1")
    with refused() as caught:
        stage.prepare(None, enabled=True)
    assert caught.value.stage == "key_contract" and caught.value.trial is None


def test_preparation_requires_exact_same_phase_law(refused):
    with refused() as caught:
        stage.from_cache(None, law_id="supplied_phase")
    assert caught.value.stage == "law"


def test_fresh_handler_uses_actual_phase_parameter_and_preserves_cache(ready, tmp_path):
    h = ready
    phase = h.parent.owner.partial_phase
    before = tuple(vars(phase).items())
    cache = phase.cache
    child = stage.prepare(h.request, enabled=True)
    assert child.partial_phase is phase and phase.dyna is child.dyna
    assert isinstance(child.dyna, h.native)
    assert child.dyna.parameter_argument is child.dyna.global_parameter_argument is phase.p
    assert phase.cache is cache and all(vars(phase)[name] is value for name, value in before)
    assert child.trial.completed
    assert all(count == 1 for count in h.delegate_counts.values())
    assert len(child.trial.method_entries) == len(stage.METHODS)
    assert all(row["status"] == "returned" for row in child.trial.method_entries)
    save(tmp_path, "trial", child.trial)


@pytest.mark.parametrize(
    "origin,parent_method,target,capture_failure",
    [
        (origin, parent, target, False)
        for origin in ("event", "profile")
        for parent in ("__init__", "_init_events")
        for target in ("same", "next")
    ]
    + [
        ("event", "__init__", "next", True),
        ("profile", "__init__", "next", True),
    ],
)
def test_active_callback_cannot_reenter_or_seize_next_method_slot(
    ready, monkeypatch, refused, origin, parent_method, target, capture_failure
):
    errors, before = [], []
    fired = False
    capture = OSError("entry rejection unwind observation")
    next_method = {"__init__": "_init_tissues", "_init_events": "_init_events_global"}
    method = parent_method if target == "same" else next_method[parent_method]

    def probe(actual, p):
        nonlocal fired
        if fired:
            return
        fired = True
        before.append(dict(ready.delegate_counts))
        try:
            getattr(actual, method)(p)
        except stage.DynaRejected as error:
            errors.append(error)
        else:
            raise AssertionError("Observer acquired a source-body slot")

    previous = sys.getprofile()
    trace = sys.gettrace()
    if origin == "event" or capture_failure:
        original = stage._namespace

        def namespace(context):
            original(context)

            class Events(list):
                def append(self, row):
                    super().append(row)
                    if origin == "event" and row[0] == parent_method + "_enter":
                        probe(context.handler, context.p)
                    if capture_failure and row[0] == parent_method + "_unwind":
                        raise capture

            context.events = Events()
            context.tape.events = context.events

        monkeypatch.setattr(stage, "_namespace", namespace)
    if origin == "profile":
        code = stage._NATIVE[parent_method].__code__

        def profile(frame, event, arg):
            if event == "call" and frame.f_code is code:
                probe(frame.f_locals["self"], frame.f_locals["p"])
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)
    try:
        with refused() as caught:
            stage.prepare(ready.request, enabled=True)
        error = caught.value
        assert fired and len(errors) == 1 and errors[0].stage == "method_entry"
        assert ready.delegate_counts == before[0]
        assert error.source_error is errors[0]
        assert error.__cause__ is errors[0]
        assert error.capture_error is (capture if capture_failure else None)
        assert error.partial["context"].invalid
        assert error.partial["entry_error"] is errors[0]
        assert any(row["status"] == "rejected" for row in error.partial["method_attempts"])
        assert error.partial["method_entries"] and error.partial["work"]
        assert not error.partial["constructor_claim_record"].succeeded
        assert error.partial["constructor_claim_error"] is errors[0]
        assert not error.partial["usable_child_available"]
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)


def test_enter_reentry_remains_primary_when_same_enter_capture_fails(ready, monkeypatch, refused):
    errors = []
    capture = OSError("enter observation after caught entry rejection")
    before = dict(ready.delegate_counts)
    original = stage._namespace

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, row):
                super().append(row)
                if row[0] == "__init___enter":
                    try:
                        context.handler._init_tissues(context.p)
                    except stage.DynaRejected as error:
                        errors.append(error)
                    else:
                        raise AssertionError("Enter observer acquired the next body slot")
                    raise capture

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    assert len(errors) == 1 and errors[0].stage == "method_entry"
    assert error.source_error is error.__cause__ is errors[0]
    assert error.capture_error is capture
    assert ready.delegate_counts == before and all(count == 0 for count in before.values())
    partial = error.partial
    assert partial["entry_error"] is errors[0]
    assert partial["context"].invalid and partial["context"].observation_error is capture
    assert any(row["status"] == "rejected" for row in partial["method_attempts"])
    assert partial["method_entries"] and partial["work"]
    assert partial["constructor_claim_error"] is errors[0]
    assert not partial["constructor_claim_record"].succeeded
    assert partial["constructor_claim_record"].source_error_present
    assert not partial["usable_child_available"]
    assert not hasattr(partial["context"], "owner")


def test_retired_cache_owner_refuses_without_poisoning_dyna_child(ready):
    child = stage.prepare(ready.request, enabled=True)
    phase = child.partial_phase
    with pytest.raises(stage.caches.CacheConstructionRejected):
        _ = ready.parent.owner.partial_phase
    assert child.partial_phase is phase


def test_successful_Key_claim_does_not_issue_child_after_state_sealing_failure(
    ready, monkeypatch, refused
):
    capture = OSError("final dyna state sealing")

    def snapshot(context):
        raise capture

    monkeypatch.setattr(stage, "_snapshot", snapshot)
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    partial = error.partial
    assert error.stage == "capture" and error.trial is None
    assert error.source_error is None and error.capture_error is capture
    assert partial["phase"].dyna is partial["handler"]
    assert partial["parameters"] is partial["phase"].p
    assert partial["constructor_claim_record"].succeeded
    assert not partial["usable_child_available"]
    assert not hasattr(partial["context"], "owner")
    with pytest.raises(stage.caches.CacheConstructionRejected):
        _ = ready.parent.owner.partial_phase


def test_parent_refusal_preserves_actual_state_without_fabricating_before_or_claim(ready, refused):
    phase = ready.parent.context.phase
    changed = NS()
    phase.p = changed
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    partial = error.partial
    assert error.stage == "parent_preflight" and error.trial is None
    assert isinstance(error.source_error, stage.caches.CacheConstructionRejected)
    assert error.__cause__ is error.source_error
    assert partial["phase"] is phase and phase.p is changed
    assert partial["parent_trial"] is ready.parent.context.trial
    assert partial["handler"] is None and partial["objects"] == []
    assert partial["constructor_claim"] is None
    assert not hasattr(partial["context"], "before")
    assert ready.parent.owner not in stage.caches._FORWARDED


@pytest.mark.parametrize("capture_failure", [False, True])
def test_constructor_failure_keeps_actual_failed_Key_claim_and_primary_cause(
    ready, monkeypatch, refused, capture_failure
):
    primary, cause, capture = (
        AttributeError("original missing event store"),
        KeyError("cause"),
        OSError("seal"),
    )

    def failed(actual, p):
        raise primary from cause

    def snapshot(context):
        raise capture

    monkeypatch.setitem(stage._NATIVE, "__init__", failed)
    if capture_failure:
        monkeypatch.setattr(stage, "_snapshot", snapshot)
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    partial = error.partial
    assert (
        error.source_error is primary and error.__cause__ is primary and primary.__cause__ is cause
    )
    assert partial["constructor_claim_error"] is primary
    assert partial["constructor_claim_partial"] is primary.dyna_continuation
    assert partial["constructor_claim_record"] is partial["constructor_claim"].record
    assert not partial["constructor_claim_record"].succeeded
    assert partial["constructor_claim_record"].source_error_present
    assert partial["parameters"] is ready.parent.context.phase.p
    assert partial["parent_trial"] is ready.parent.context.trial
    assert not partial["usable_child_available"]
    assert error.capture_error is (capture if capture_failure else None)


@pytest.mark.parametrize("mutation", ["invalid", "consumed_link"])
def test_closed_record_does_not_replace_live_claim_ancestry_validation(ready, refused, mutation):
    child = stage.prepare(ready.request, enabled=True)
    context = stage._ISSUED[child]
    claim = context.constructor_claim
    key_context = context.key._ISSUED[claim]
    record = claim.record
    before = stage._snapshot(context).identity
    assert record is context.constructor_claim_record and record.succeeded
    if mutation == "invalid":
        key_context.invalid = True
    else:
        context.key._CONSUMED.pop(context.refs[4])
    # The recorded document and phase values have not changed. Ongoing use
    # must consult Key's real public live-registry/closed-claim checker.
    assert claim.record is record
    assert stage._snapshot(context).identity == before
    with refused() as caught:
        _ = child.dyna
    assert caught.value.stage == "owner_drift"
    assert isinstance(caught.value.source_error, context.key.ContinuationRejected)


@pytest.mark.parametrize("method", ["init_profiles", "redo_gj", "__init__"])
def test_unselected_or_reentered_handler_body_is_blocked(ready, refused, method):
    child = stage.prepare(ready.request, enabled=True)
    with refused():
        getattr(child.dyna, method)(child.partial_phase.p)


def test_full_phase_admission_remains_held(ready, refused):
    child = stage.prepare(ready.request, enabled=True)
    with refused() as caught:
        stage.require_phase(child)
    assert caught.value.stage == "phase_incomplete"
