"""Prepared blocked SEED-tail controls; no claim/owner stand-ins grant entry."""

import json
import sys
import time
from contextlib import contextmanager
from enum import Enum
from types import CellType, CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_phase_tail as stage
from tests.unit import test_betse_native_phase_dyna as dyna_controls
from validation.betse import betse_native_phase_tail_software as software
from validation.betse.betse_native_single_cell_core_synthetic import save


@pytest.fixture(autouse=True)
def blocked(monkeypatch, request, tmp_path):
    # Retain the established upstream native/import/RNG blockade as well as
    # this module's three actual source bodies. No test executes those bodies.
    upstream = dyna_controls.blocked.__wrapped__(monkeypatch, request, tmp_path)
    next(upstream)
    original, trace = sys.getprofile(), sys.gettrace()
    attempted = []
    codes = {
        stage._acquire.__code__,
        stage._TAIL.__code__,
        *(fn.__code__ for fn in stage._METHODS.values()),
    }

    try:
        adapted = software.adapt_upstream_guard(original, dyna_controls.blocked.__wrapped__)
        profile = software.native_profile(
            codes, stage, attempted, adapted, "Actual source/native tail work forbidden"
        )
        sys.setprofile(profile)
        yield
        assert not attempted and sys.getprofile() is profile and sys.gettrace() is trace
    finally:
        # The original generator still owns imports/RNG and its own guard
        # receipt. Restore its exact profile object before its normal exit.
        sys.setprofile(original)
        sys.settrace(trace)
        (tmp_path / "tail-native-blocked.json").write_text(
            json.dumps(
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempted,
                    actual_source_credit=0,
                    native_root_formatting="once_per_guard_with_live_identity_check",
                )
            )
        )
        try:
            next(upstream)
        except StopIteration:
            pass


def test_cost_native_guard_preserves_all_inherited_events_and_blockade(tmp_path):
    received, attempted = [], []
    native = NS(aliases=NS(NATIVE="/exact/native"))
    code = test_cost_native_guard_preserves_all_inherited_events_and_blockade.__code__
    frame = NS(f_code=code)

    def prior(actual, event, value):
        received.append((actual, event, value))

    profile = software.native_profile({code}, native, attempted, prior, "blocked native")
    for event in ("return", "c_call", "c_return", "c_exception"):
        profile(frame, event, None)
    with pytest.raises(AssertionError, match="blocked native"):
        profile(frame, "call", None)
    assert [event for _, event, _ in received] == ["return", "c_call", "c_return", "c_exception"]
    assert attempted == [code.co_qualname]
    save(
        tmp_path,
        "cost-event-delegation",
        dict(events=[event for _, event, _ in received], attempted=attempted, native_credit=0),
    )


def test_cost_native_root_identity_drift_refuses_before_inherited_callback():
    received, attempted = [], []
    native = NS(aliases=NS(NATIVE="/exact/native"))
    profile = software.native_profile(
        set(), native, attempted, lambda *args: received.append(args), "blocked"
    )
    native.aliases = NS(NATIVE=native.aliases.NATIVE)
    frame = NS(
        f_code=test_cost_native_root_identity_drift_refuses_before_inherited_callback.__code__
    )
    with pytest.raises(AssertionError, match="root changed"):
        profile(frame, "call", None)
    assert received == [] and attempted == ["native_root_identity_changed"]


def test_cost_guard_adapter_rejects_foreign_code_before_installing_it():
    def foreign(frame, event, arg):
        raise AssertionError("foreign delegate must not run")

    before = sys.getprofile()
    with pytest.raises(ValueError, match="guard code"):
        software.adapt_upstream_guard(foreign, dyna_controls.blocked.__wrapped__)
    assert sys.getprofile() is before


def test_cost_guard_formats_native_root_once_without_caching_a_source_result(tmp_path):
    class Root:
        def __init__(self):
            self.calls = 0

        def __str__(self):
            self.calls += 1
            return "/exact/native"

    root = Root()
    native = NS(aliases=NS(NATIVE=root))
    frame = NS(
        f_code=test_cost_guard_formats_native_root_once_without_caching_a_source_result.__code__
    )
    repeats = 20000
    started = time.monotonic()
    for _ in range(repeats):
        assert not frame.f_code.co_filename.startswith(str(native.aliases.NATIVE) + "/")
    old_seconds, old_calls = time.monotonic() - started, root.calls
    profile = software.native_profile(set(), native, [], None, "blocked")
    initial_calls = root.calls
    started = time.monotonic()
    for _ in range(repeats):
        profile(frame, "call", None)
    seconds = time.monotonic() - started
    assert old_calls == repeats and initial_calls == old_calls + 1 and root.calls == initial_calls
    save(
        tmp_path,
        "cost-root-formatting",
        dict(
            metadata_events=repeats,
            baseline_seconds=old_seconds,
            successor_seconds=seconds,
            baseline_root_formats=old_calls,
            successor_root_formats=1,
            whole_chain_performance_claim=False,
            native_credit=0,
        ),
    )


def test_cost_finalization_boundary_failure_is_retained_without_raising_primary(
    monkeypatch, tmp_path
):
    error = OSError("timing receipt")

    def rejected(path, value):
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(software.snapshot, "write_json", rejected)
        assert software.boundary(tmp_path, "probe", time.monotonic()) is error


def _cost_adapter_metadata():
    """Actual upstream code/cells, with no constructor or native body entry."""
    source = dyna_controls.blocked.__wrapped__
    namespace = dict(source.__globals__)
    namespace["stage"] = NS(aliases=NS(NATIVE="/exact/native"))
    source = FunctionType(source.__code__, namespace)
    code = next(
        value
        for value in source.__code__.co_consts
        if type(value) is CodeType and value.co_name == "profile"
    )
    calls, attempts = [], []

    def previous(*args):
        calls.append(args)

    values = dict(
        codes={test_cost_guard_adapter_rejects_foreign_code_before_installing_it.__code__},
        attempts=attempts,
        previous=previous,
    )
    cells = {name: CellType(value) for name, value in values.items()}
    original = FunctionType(
        code, namespace, closure=tuple(cells[name] for name in code.co_freevars)
    )
    return NS(
        source=source,
        original=original,
        cells=cells,
        calls=calls,
        attempts=attempts,
        namespace=namespace,
    )


@pytest.mark.parametrize("event", ["call", "return", "c_call", "c_return", "c_exception"])
def test_cost_adapter_unchanged_actual_cells_preserve_event_and_reference_identity(event):
    metadata = _cost_adapter_metadata()
    closure = metadata.original.__closure__
    adapted = software.adapt_upstream_guard(metadata.original, metadata.source)
    frame = NS(
        f_code=test_cost_adapter_unchanged_actual_cells_preserve_event_and_reference_identity.__code__
    )
    adapted(frame, event, None)
    assert metadata.original.__closure__ is closure
    assert metadata.cells["attempts"].cell_contents is metadata.attempts
    assert metadata.calls == [(frame, event, None)] and metadata.attempts == []


@pytest.mark.parametrize("event", ["call", "return"])
@pytest.mark.parametrize(
    "mutation",
    [
        "original_code",
        "source_code",
        "codes_cell",
        "roster",
        "attempts_cell",
        "previous_cell",
        "stage",
    ],
)
def test_cost_adapter_live_rebinding_refuses_before_any_captured_or_foreign_delegate(
    event, mutation
):
    metadata, foreign = _cost_adapter_metadata(), []
    adapted = software.adapt_upstream_guard(metadata.original, metadata.source)
    if mutation == "original_code":
        metadata.original.__code__ = metadata.original.__code__.replace(co_name="retargeted")
    elif mutation == "source_code":
        metadata.source.__code__ = metadata.source.__code__.replace(co_name="retargeted")
    elif mutation == "codes_cell":
        old = metadata.cells["codes"].cell_contents
        metadata.cells["codes"].cell_contents = set(old)
        assert old == metadata.cells["codes"].cell_contents
    elif mutation == "roster":
        metadata.cells["codes"].cell_contents.clear()
    elif mutation == "attempts_cell":
        metadata.cells["attempts"].cell_contents = []
    elif mutation == "previous_cell":
        metadata.cells["previous"].cell_contents = lambda *args: foreign.append(args)
    else:
        owner = metadata.namespace["stage"]
        metadata.namespace["stage"] = NS(aliases=owner.aliases)
    frame = NS(
        f_code=(
            test_cost_adapter_live_rebinding_refuses_before_any_captured_or_foreign_delegate.__code__
        )
    )
    with pytest.raises(AssertionError, match="upstream guard authority"):
        adapted(frame, event, None)
    assert metadata.calls == foreign == []
    assert metadata.attempts == ["upstream_guard_authority_changed"]


@pytest.mark.parametrize("event", ["call", "return"])
@pytest.mark.parametrize("mutation", ["holder", "root"])
def test_cost_adapter_root_and_holder_drift_refuse_before_inherited_callback(event, mutation):
    metadata = _cost_adapter_metadata()
    adapted = software.adapt_upstream_guard(metadata.original, metadata.source)
    owner = metadata.namespace["stage"]
    if mutation == "holder":
        owner.aliases = NS(NATIVE=owner.aliases.NATIVE)
    else:
        old = owner.aliases.NATIVE
        replacement = (" " + old).lstrip()
        assert replacement == old and replacement is not old
        owner.aliases.NATIVE = replacement
    frame = NS(
        f_code=test_cost_adapter_root_and_holder_drift_refuse_before_inherited_callback.__code__
    )
    with pytest.raises(AssertionError, match="root changed"):
        adapted(frame, event, None)
    assert not metadata.calls and metadata.attempts == ["native_root_identity_changed"]


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("target", ["stamp", "boundary"])
@pytest.mark.parametrize("falsey", [False, True])
def test_cost_marker_entry_rejection_on_unwind_keeps_primary_cause_and_exact_hooks(
    monkeypatch, tmp_path, hook, target, falsey
):
    class Primary(ValueError):
        def __bool__(self):
            return not falsey

    primary, cause, secondary = (
        Primary("source primary"),
        KeyError("cause"),
        OSError("marker entry"),
    )
    attempts, body, inventory_calls = [], [], []
    before = (sys.getprofile(), sys.gettrace())
    code = getattr(software, target).__code__
    index = 0 if hook == "profile" else 1

    def observer(frame, event, arg):
        if (
            event == "call"
            and frame.f_code is code
            and frame.f_locals.get("name") == "pytest-finished"
            and not attempts
        ):
            attempts.append(frame)
            raise secondary
        previous = before[index]
        if previous is not None:
            previous(frame, event, arg)
        return observer if hook == "trace" else None

    def failing_pytest(*args, **kwargs):
        body.append("synthetic pytest body")
        raise primary from cause

    def inventory():
        inventory_calls.append("metadata inventory")
        return dict(synthetic_metadata_only=True)

    directory = tmp_path / "marker-child"
    directory.mkdir()
    try:
        with monkeypatch.context() as patch:
            patch.setattr(pytest, "main", failing_pytest)
            patch.setattr(software.inherited.runtime, "inventory", inventory)
            (sys.setprofile if index == 0 else sys.settrace)(observer)
            with pytest.raises(Primary) as caught:
                software.child(directory, "unused synthetic metadata dispatch")
            assert caught.value is primary and primary.__cause__ is cause
            state = primary.tail_software
            assert len(attempts) == 1 and body == ["synthetic pytest body"]
            assert inventory_calls == ["metadata inventory"]
            assert len(state.timing_errors) == 1 and state.timing_errors[0][1] is secondary
            assert state.final_hooks_restored is True and state.cleanup_errors == []
            expected = list(before)
            expected[index] = observer
            assert sys.getprofile() is expected[0] and sys.gettrace() is expected[1]
            assert not (directory / "boundary-pytest-finished.json").exists()
    finally:
        sys.settrace(before[1])
        sys.setprofile(before[0])


@pytest.fixture(scope="module")
def plans():
    return dyna_controls.plans.__wrapped__()


@pytest.fixture
def cache_parent(monkeypatch, tmp_path, plans):
    cache_controls = dyna_controls.cache_controls
    phase_controls = cache_controls.phase_controls
    h = phase_controls.controlled.__wrapped__(monkeypatch, tmp_path, plans)
    assembly = stage.previous.caches.previous

    class Kind(Enum):
        SEED = 1
        INIT = 2
        SIM = 3

    def unselected(self, *args):
        raise AssertionError("Unselected synthetic phase body must remain guarded")

    # Complete the synthetic source class BEFORE any phase object is born.
    # Neither a live phase nor a parameter/claim/owner is fabricated or edited.
    for name in ("_init_kludge_time", "die_unless_kind_seed", "die_unless_kind_init_or_sim"):
        setattr(h.classes["phase"], name, unselected)
    original = assembly._acquire

    def acquire(context):
        original(context)
        context.kind = Kind.SEED

    monkeypatch.setattr(assembly, "_acquire", acquire)
    owner = assembly.prepare(h.request, enabled=True)
    parent = NS(h=h, owner=owner, context=assembly._ISSUED[owner])
    prepared = cache_controls.controlled.__wrapped__(monkeypatch, parent)
    owner = stage.previous.caches.prepare(prepared.request, enabled=True)
    return NS(owner=owner, context=stage.previous.caches._ISSUED[owner], controlled=prepared)


@pytest.fixture
def dyna_parent(monkeypatch, request):
    prepared = dyna_controls.ready.__wrapped__(monkeypatch, request)
    owner = stage.previous.prepare(prepared.request, enabled=True)
    return NS(owner=owner, prepared=prepared, context=stage.previous._ISSUED[owner])


@pytest.fixture
def ready(monkeypatch, request):
    try:
        api = stage._key_api()
        stage._parent_api()
    except stage.TailRejected as error:
        pytest.skip("Real new mutation/dispatch prerequisite unavailable: " + error.stage)
    parent = request.getfixturevalue("dyna_parent")
    counters = dict(complete=0, _init_kludge=0, _init_kludge_time=0)
    faults = NS(
        method=None, error=AttributeError("original tail failure"), cause=KeyError("native cause")
    )
    namespace = dict(counters=counters, faults=faults)
    exec(
        compile(
            """
def complete(self,kind,p):
    counters['complete']+=1
    self._init_kludge()
    if faults.method=='export':
        raise faults.error from faults.cause
    if kind is SimPhaseKind.SEED:
        self.export_dirname=p.init_export_dirname
    elif kind is SimPhaseKind.INIT:
        self.export_dirname=p.init_export_dirname
    elif kind is SimPhaseKind.SIM:
        self.export_dirname=p.sim_export_dirname
    else:
        raise BetseSimPhaseException(kind.name)
def kludge(self):
    counters['_init_kludge']+=1
    self.sim.dyna=self.dyna
    if faults.method=='after_sim':
        raise faults.error from faults.cause
    self.p._run_sim=self.kind is SimPhaseKind.SIM
    if faults.method=='after_parameter':
        raise faults.error from faults.cause
    self._init_kludge_time()
def time(self):
    counters['_init_kludge_time']+=1
    if faults.method=='time':
        raise faults.error from faults.cause
    if self.kind is SimPhaseKind.SEED:
        return
    raise AssertionError('No INIT/SIM temporal body allowed')
""",
            "<synthetic-seed-tail>",
            "exec",
        ),
        namespace,
    )

    def acquire(context):
        context.native_phase = context.refs[8].factories["SimPhase"]
        context.enum = type(context.phase.kind)
        context.exception = ValueError
        context.native_bindings = stage._native_bindings(context)

    monkeypatch.setattr(stage, "_acquire", acquire)
    monkeypatch.setattr(stage, "_TAIL", namespace["complete"])
    monkeypatch.setattr(
        stage,
        "_METHODS",
        {
            "_init_kludge": namespace["kludge"],
            "_init_kludge_time": namespace["time"],
        },
    )
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setenv(api.RELEASE, "1")
    declaration = stage.from_dyna(parent.owner, law_id=stage.LAW_ID)
    return NS(parent=parent, request=declaration, api=api, counters=counters, faults=faults)


@pytest.fixture
def refused(tmp_path):
    @contextmanager
    def check():
        with pytest.raises(stage.TailRejected) as caught:
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
                stores=partial.get("stores"),
                stages=partial.get("stages"),
                attempts=partial.get("attempts"),
                entries=partial.get("method_entries"),
                entry_attempts=partial.get("entry_attempts"),
                entry_error=partial.get("entry_error"),
                raw_state=partial.get("raw_state"),
                claim_error=partial.get("claim_error"),
                claim_record=partial.get("claim_record"),
                last_completed=partial.get("last_completed"),
                hook_setup_error=partial.get("hook_setup_error"),
                hook_attempts=partial.get("hook_attempts"),
                hook_states=partial.get("hook_states"),
                hook_cleanup_errors=partial.get("hook_cleanup_errors"),
            ),
        )

    return check


def test_preparation_retains_full_original_tail_helpers_and_seed_boundary():
    plan = stage.source_plan()
    assert plan["constructor_lines"] == (189, 204)
    assert plan["helper_lines"] == {"_init_kludge": (208, 259), "_init_kludge_time": (262, 330)}
    assert plan["native_store_order"] == stage.STORES
    assert plan["parameter_fields_allowed"] == ("_run_sim",)
    assert plan["temporal_stores_allowed"] == () and plan["path_creation"] is False
    assert plan["INIT_SIM_full_Parameters_world_physics_or_checkpoint_admitted"] is False


@pytest.mark.parametrize("enabled,flag", [(False, "1"), (True, "0"), (1, "1")])
def test_preparation_release_precedes_all_parameter_or_parent_entry(
    monkeypatch, refused, enabled, flag
):
    def forbidden():
        raise AssertionError("No authority work before release")

    monkeypatch.setattr(stage, "_key_api", forbidden)
    monkeypatch.setattr(stage, "_parent_api", forbidden)
    monkeypatch.setenv(stage.RELEASE, flag)
    with refused() as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release" and caught.value.trial is None


def test_preparation_unbound_new_claim_never_uses_readonly_d9_or_inspection(monkeypatch, refused):
    def forbidden(*args, **kwargs):
        raise AssertionError("Read-only APIs cannot authorize the _run_sim store")

    monkeypatch.setattr(stage, "KEY_SHA256", None)
    monkeypatch.setattr(stage.previous, "_key_api", forbidden)
    monkeypatch.setattr(stage.previous.handler.claims, "inspection", forbidden)
    monkeypatch.setenv(stage.RELEASE, "1")
    with refused() as caught:
        stage.prepare(None, enabled=True)
    assert caught.value.stage == "key_contract" and caught.value.trial is None


def test_preparation_missing_parent_hook_is_an_explicit_refusal(monkeypatch, refused):
    monkeypatch.delattr(stage.previous, "_claim_for_tail", raising=False)
    with refused() as caught:
        stage._parent_api()
    assert caught.value.stage == "dyna_contract" and caught.value.trial is None


@pytest.mark.parametrize("law", ["INIT", "SIM", "supplied_phase", None])
def test_preparation_no_kind_retrofit_or_supplied_phase_law(refused, law):
    with refused() as caught:
        stage.from_dyna(None, law_id=law)
    assert caught.value.stage == "law"


def test_seed_tail_preserves_every_actual_parent_and_three_native_store_aliases(ready, tmp_path):
    parent = ready.parent.context
    phase, p, sim = parent.phase, parent.p, parent.phase.sim
    original = (phase, p, sim, phase.cells, phase.cache, phase.dyna, phase.callbacks, type(phase))
    names = tuple(vars(p))
    path = vars(p)["init_export_dirname"]
    try:
        child = stage.prepare(ready.request, enabled=True)
    except stage.TailRejected as error:
        partial = error.partial if type(error.partial) is dict else {}
        save(
            tmp_path,
            "pilot-refusal",
            dict(
                stage=error.stage,
                source=error.source_error,
                capture=error.capture_error,
                cause=error.__cause__,
                stores=partial.get("stores"),
                stages=partial.get("stages"),
                entries=partial.get("entry_attempts"),
                claim_error=partial.get("claim_error"),
                hook_errors=partial.get("hook_cleanup_errors"),
                full_raw_owner_serialization_claimed=False,
            ),
        )
        raise
    assert child.partial_phase is phase
    assert (
        phase,
        p,
        sim,
        phase.cells,
        phase.cache,
        phase.dyna,
        phase.callbacks,
        type(phase),
    ) == original
    assert sim.dyna is phase.dyna and p._run_sim is False and phase.export_dirname is path
    assert tuple(vars(p)) == (*names, "_run_sim")
    assert all(name not in vars(p) for name in ("dt", "resample", "total_time", "t_resample"))
    assert ready.counters == dict(complete=1, _init_kludge=1, _init_kludge_time=1)
    assert child.trial.completed and child.trial.stages == stage.RETURN_ORDER
    assert [(row["role"], row["field"]) for row in stage._ISSUED[child].stores] == list(
        stage.STORES
    )
    assert parent.trial is stage._ISSUED[child].refs[1]
    context = stage._ISSUED[child]
    stage.literal._same(stage._registry_links(context), stage._registry_links(context))
    assert child.partial_phase is phase  # completed-child authority is checked again
    save(tmp_path, "trial", child.trial)


@pytest.mark.parametrize(
    "failure,store_count",
    [
        ("after_sim", 1),
        ("after_parameter", 2),
        ("time", 2),
        ("export", 2),
    ],
)
def test_source_failure_retains_ordered_partial_stores_and_identical_primary_chain(
    ready, refused, failure, store_count
):
    ready.faults.method = failure
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    assert error.source_error is ready.faults.error and error.__cause__ is ready.faults.error
    assert error.source_error.__cause__ is ready.faults.cause
    assert error.capture_error is None
    partial = error.partial
    assert len(partial["stores"]) == store_count
    assert [(row["role"], row["field"]) for row in partial["stores"]] == list(
        stage.STORES[:store_count]
    )
    assert partial["sim"].dyna is partial["handler"]
    assert partial["parameters"] is partial["phase"].p
    assert "export_dirname" not in vars(partial["phase"])
    assert partial["claim_error"] is ready.faults.error
    assert not partial["usable_child_available"] and not hasattr(partial["context"], "owner")
    with pytest.raises(stage.TailRejected, match="consumed"):
        stage.prepare(ready.request, enabled=True)


def test_early_refusal_preserves_parent_and_does_not_fabricate_baseline(ready, refused):
    phase = ready.parent.context.phase
    phase.p = NS()
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    assert error.trial is None and error.source_error is not None
    assert (
        error.partial["phase"] is phase
        and error.partial["parent_trial"] is ready.parent.context.trial
    )
    assert not hasattr(error.partial["context"], "before")
    assert error.partial["claim"] is None


def test_trial_capture_failure_keeps_actual_three_stores_but_never_issues_child(
    ready, monkeypatch, refused
):
    capture = OSError("tail trial capture")

    def fail(context):
        raise capture

    monkeypatch.setattr(stage, "_snapshot", fail)
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    assert error.source_error is None and error.capture_error is capture and error.trial is None
    assert len(error.partial["stores"]) == 3
    assert error.partial["sim"].dyna is error.partial["handler"]
    assert error.partial["phase"].export_dirname is error.partial["parameters"].init_export_dirname
    assert not error.partial["usable_child_available"]


@pytest.mark.parametrize("source_fails", [False, True])
def test_helper_return_capture_preserves_completed_raw_fields_or_original_unwind(
    ready, monkeypatch, refused, source_fails
):
    capture = OSError("tail helper return observation")
    original = stage._capture_state
    code = stage._METHODS["_init_kludge"].__code__
    prior, trace = sys.getprofile(), sys.gettrace()
    if source_fails:
        ready.faults.method = "after_sim"

    def observe(context, frame, event):
        original(context, frame, event)
        if frame.f_code is code and event == "return":
            raise capture

    monkeypatch.setattr(stage, "_capture_state", observe)
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    assert sys.getprofile() is prior and sys.gettrace() is trace
    assert error.capture_error is capture
    assert error.source_error is (ready.faults.error if source_fails else None)
    if source_fails:
        assert error.__cause__ is ready.faults.error
        assert ready.faults.error.__cause__ is ready.faults.cause
    partial = error.partial
    assert partial["sim"].dyna is partial["handler"]
    assert len(partial["stores"]) == (1 if source_fails else 2)
    assert partial["raw_state"] is not None
    assert "export_dirname" not in vars(partial["phase"])
    assert not partial["usable_child_available"]


@pytest.mark.parametrize("target", ["same", "next"])
@pytest.mark.parametrize("capture_failure", [False, True])
@pytest.mark.parametrize("origin", ["event", "profile", "trace"])
def test_enter_callback_cannot_reenter_or_seize_time_slot_even_if_refusal_is_caught(
    ready, monkeypatch, refused, target, capture_failure, origin
):
    original = stage._namespace
    errors, counters = [], []
    capture = OSError("enter capture after caught tail reentry")

    def probe(context):
        counters.append(dict(ready.counters))
        name = "_init_kludge" if target == "same" else "_init_kludge_time"
        try:
            getattr(context.phase, name)()
        except stage.TailRejected as error:
            errors.append(error)
        else:
            raise AssertionError("Observer acquired a tail body slot")

    def namespace(context):
        original(context)

        class Events(list):
            def append(self, row):
                super().append(row)
                if origin == "event" and row[0] == "_init_kludge_enter":
                    probe(context)
                if capture_failure and row[0] == (
                    "_init_kludge_enter" if origin == "event" else "_init_kludge_unwind"
                ):
                    raise capture

        context.events = Events()
        context.tape.events = context.events

    monkeypatch.setattr(stage, "_namespace", namespace)
    prior, trace = sys.getprofile(), sys.gettrace()
    code = stage._METHODS["_init_kludge"].__code__
    if origin == "profile":

        def profile(frame, event, arg):
            if event == "call" and frame.f_code is code:
                probe(stage._ACTIVE[-1])
            if prior is not None:
                prior(frame, event, arg)

        sys.setprofile(profile)
    if origin == "trace":
        delegates = {}

        def inherited_trace(frame, event, arg):
            if event == "call" and frame.f_code is code:
                context = stage._ACTIVE[-1]
                assert context.admitted_frames[id(frame)]["frame"] is frame
                probe(context)
            delegate = trace if event == "call" else delegates.get(id(frame))
            if delegate is not None:
                delegates[id(frame)] = delegate(frame, event, arg)
            if event == "return":
                delegates.pop(id(frame), None)
            return inherited_trace

        sys.settrace(inherited_trace)
    try:
        with refused() as caught:
            stage.prepare(ready.request, enabled=True)
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)
    error = caught.value
    assert len(errors) == 1 and error.source_error is error.__cause__ is errors[0]
    assert error.capture_error is (capture if capture_failure else None)
    assert ready.counters == counters[0]
    assert error.partial["entry_error"] is errors[0] and error.partial["context"].invalid
    assert error.partial["claim_error"] is errors[0]
    assert not error.partial["usable_child_available"]


@pytest.mark.parametrize("target", ["complete", "helper"])
def test_trace_observer_raw_callable_reentry_never_reaches_another_delegate(ready, refused, target):
    before, errors = [], []
    prior, outer_profile = sys.gettrace(), sys.getprofile()
    code = stage._METHODS["_init_kludge"].__code__
    delegates = {}

    def trace(frame, event, arg):
        if event == "call" and frame.f_code is code:
            context = stage._ACTIVE[-1]
            before.append(dict(ready.counters))
            try:
                if target == "complete":
                    context.complete(context.phase, context.enum.SEED, context.p)
                else:
                    context.methods["_init_kludge"](context.phase)
            except stage.TailRejected as error:
                errors.append(error)
            else:
                raise AssertionError("Raw callable reentry entered a delegate")
        delegate = prior if event == "call" else delegates.get(id(frame))
        if delegate is not None:
            delegates[id(frame)] = delegate(frame, event, arg)
        if event == "return":
            delegates.pop(id(frame), None)
        return trace

    sys.settrace(trace)
    try:
        with refused() as caught:
            stage.prepare(ready.request, enabled=True)
        error = caught.value
        assert len(errors) == 1 and error.source_error is error.__cause__ is errors[0]
        assert ready.counters == before[0]
        assert error.partial["last_rejected_attempt"]["frame"] is not None
        assert error.partial["last_rejected_attempt"]["body_started"] is False
        assert not error.partial["usable_child_available"]
    finally:
        sys.settrace(prior)
        sys.setprofile(outer_profile)


def _controller_context():
    """Metadata-only observer controller; never a parameter/phase/owner issuer."""
    return NS(
        bodies={},
        request=None,
        entry_error=None,
        pending_source_error=None,
        observation_error=None,
        observation_errors=(),
        observation_origin=None,
        observation_raw=None,
        active=True,
        invalid=False,
        thread=stage.get_ident(),
        stage="isolated_observer_control",
        work=[],
        attempts=[],
        admitted_frames={},
        complete_frame=None,
        complete_invocation=None,
        claims={},
        stack=[],
        phase=NS(),
        p=NS(),
        enum=NS(SEED=object()),
        exception=ValueError,
    )


def test_isolated_runner_selection_uses_item_names_and_refuses_empty_or_unknown(monkeypatch):
    from validation.betse import betse_native_phase_tail_software as runner

    isolated = NS(name="test_isolated_observer[trace]", nodeid="isolated-01::observer")
    owner = NS(name="test_seed_tail_owner", nodeid="isolated-01::test_seed_tail_owner")
    chosen, remaining = runner.select_items([isolated, owner], "isolated")
    assert chosen == [isolated] and remaining == [owner]
    assert runner.select_items([isolated, owner], "")[0] == [isolated, owner]
    assert runner.select_items([isolated, owner], "isolated,seed_tail")[0] == [isolated, owner]
    with pytest.raises(ValueError, match="No test item names"):
        runner.select_items([owner], "isolated")
    with pytest.raises(ValueError, match="Nonempty"):
        runner.select_items([isolated, owner], "isolated,")
    declared = [name for names in runner.GROUPS.values() for name in names]
    assert declared and len(declared) == len(set(declared))
    actual = NS(name=declared[0], nodeid="wrong-ancestor::" + declared[0])
    group = next(iter(runner.GROUPS))
    assert runner.select_items([owner, actual], group) == ([actual], [owner])
    with pytest.raises(ValueError, match="group roster"):
        runner.select_items([owner], group)
    scope = runner._batch_scope()
    assert scope["OWNED"] == runner.OWNED and scope["GROUPS"] is runner.GROUPS
    assert scope["MODULE"] == runner.MODULE and scope["ROOT"] == runner.ROOT
    assert scope["__file__"] == runner.__file__

    def launch(output, remaining_from=None):
        return output, remaining_from

    def child(output, inputs_sha):
        return output, inputs_sha

    monkeypatch.setattr(runner.batch, "launch_batch", launch)
    monkeypatch.setattr(runner.batch, "batch_child", child)
    assert runner.launch_batch("fresh-output") == ("fresh-output", None)
    assert runner.batch_child("fresh-output", "exact-input-sha") == (
        "fresh-output",
        "exact-input-sha",
    )


@contextmanager
def _active_controller(context):
    # An active metadata controller is not inserted in any issuance registry.
    issued = tuple(stage._ISSUED.items())
    stage._ACTIVE.append(context)
    try:
        yield
    finally:
        assert stage._ACTIVE.pop() is context
        context.active = False
        assert tuple(stage._ISSUED.items()) == issued


def test_isolated_stable_ancestry_ignores_observation_growth_but_keeps_final_edges():
    first, second = ["same"], ["same"]
    phase = NS(left=first, right=second, keep_first=first, keep_second=second)
    context = NS(
        phase=phase,
        p=NS(),
        sim=NS(),
        objects=[("phase", phase)],
        stable_fields=[{}],
        all_fields=[{}],
        stable_tape=stage._AncestryTape(),
        tape=NS(rng=None, events=[], draws=(), locals={}),
    )
    context.stable_view = NS(objects=context.objects, fields=context.stable_fields)
    context.all_view = NS(objects=context.objects, fields=context.all_fields)
    before, full_before = stage._stable_graph(context), stage._graph(context)
    context.tape.events.append(("enter", phase))
    context.tape.locals["frame"] = dict(actual=phase, result=first)
    after, full_after = stage._stable_graph(context), stage._graph(context)
    stage.literal._same(before[0], after[0])
    assert before[1] == after[1] and full_before[1] != full_after[1]
    assert context.tape.events and context.tape.locals  # observations were not cleared
    phase.left = second  # both equal objects remain retained; only the edge changes
    drift = stage._stable_graph(context)
    assert drift[1] != before[1]


@pytest.mark.parametrize("target", ["complete", "_init_kludge", "_init_kludge_time"])
def test_isolated_direct_body_refusal_retains_frame_work_and_zero_body_status(target):
    context = _controller_context()
    counts = {target: 0}
    space = dict(counts=counts)
    exec(
        compile(
            """
def complete(actual,kind,p):
    counts['complete']+=1
def kludge(actual):
    counts['_init_kludge']+=1
def time(actual):
    counts['_init_kludge_time']+=1
""",
            "<isolated-rejected-tail-body>",
            "exec",
        ),
        space,
    )
    name = {"complete": "complete", "_init_kludge": "kludge", "_init_kludge_time": "time"}[target]
    function = space[name]
    context.bodies = {target: function}
    prior, trace = sys.getprofile(), sys.gettrace()
    with _active_controller(context):
        with pytest.raises(stage.TailRejected) as caught:
            with stage._account(context):
                if target == "complete":
                    function(context.phase, context.enum.SEED, context.p)
                else:
                    function(context.phase)
    assert counts[target] == 0 and context.entry_error is caught.value
    assert sys.getprofile() is prior and sys.gettrace() is trace
    assert len(context.attempts) == 1 and len(context.work) == 1
    attempt = context.attempts[0]
    assert attempt["frame"].f_code is function.__code__
    assert attempt["status"] == attempt["work"]["admission"] == "rejected"
    assert not attempt["body_started"] and not attempt["work"]["body_started"]
    assert attempt["work"]["entry_is_case"] is False


def test_isolated_trace_and_profile_share_admission_before_either_inherited_observer(monkeypatch):
    context = _controller_context()
    counts, deliveries = [], []

    def body(self, kind, p):
        counts.append(self)

    context.bodies = {"complete": body}

    # This isolated frame/controller test never invokes prepare or issues an
    # owner. The metadata check has no native/parameter permission to supply.
    def check(actual):
        assert actual is context

    monkeypatch.setattr(stage, "_check", check)
    prior, outer_trace = sys.getprofile(), sys.gettrace()

    def inherited_profile(frame, event, arg):
        if event == "call" and frame.f_code is body.__code__:
            assert context.admitted_frames[id(frame)]["frame"] is frame
            deliveries.append("profile")
        if prior is not None:
            prior(frame, event, arg)

    delegates = {}

    def inherited_trace(frame, event, arg):
        if event == "call" and frame.f_code is body.__code__:
            assert context.admitted_frames[id(frame)]["frame"] is frame
            deliveries.append("trace")
        delegate = outer_trace if event == "call" else delegates.get(id(frame))
        if delegate is not None:
            delegates[id(frame)] = delegate(frame, event, arg)
        if event == "return":
            delegates.pop(id(frame), None)
        return inherited_trace

    def driver():
        context.complete_invocation = sys._getframe()
        return body(context.phase, context.enum.SEED, context.p)

    sys.setprofile(inherited_profile)
    sys.settrace(inherited_trace)
    # Avoid state-capture work in this isolated admission-controller control.
    monkeypatch.setattr(stage, "_capture_state", lambda *args: None)
    try:
        with _active_controller(context), stage._account(context):
            driver()
        assert counts == [context.phase]
        assert sorted(deliveries) == ["profile", "trace"]
        assert len(context.attempts) == 1 and len(context.work) == 1
        assert sorted(context.attempts[0]["hooks"]) == ["profile", "trace"]
        assert context.attempts[0]["body_started"] is True
        assert sys.getprofile() is inherited_profile and sys.gettrace() is inherited_trace
    finally:
        sys.settrace(outer_trace)
        sys.setprofile(prior)


def test_isolated_guarded_complete_binds_the_actual_delegate_call_frame(monkeypatch):
    context = _controller_context()
    counts = []
    namespace = dict(counts=counts)
    exec(
        compile(
            "def complete(self,kind,p):\n    counts.append(self)\n"
            "def helper(self):\n    raise AssertionError('No helper call admitted here')\n",
            "<synthetic-isolated-tail>",
            "exec",
        ),
        namespace,
    )
    monkeypatch.setattr(stage, "_TAIL", namespace["complete"])
    monkeypatch.setattr(stage, "_METHODS", {name: namespace["helper"] for name in stage.METHODS})

    def check(actual):
        assert actual is context

    monkeypatch.setattr(stage, "_check", check)
    monkeypatch.setattr(stage, "_capture_state", lambda *args: None)
    stage._namespace(context)

    def driver():
        context.driver_frame = sys._getframe()
        return context.complete(context.phase, context.enum.SEED, context.p)

    with _active_controller(context), stage._account(context):
        driver()
    assert counts == [context.phase]
    assert context.complete_frame.f_back is context.complete_invocation
    assert context.complete_invocation.f_code is stage._complete_body.__code__
    assert [row["layer"] for row in context.work] == ["tail_body_wrapper", "literal_body_attempt"]
    assert len(context.admitted_frames) == 1


@pytest.mark.parametrize("hook", ["profile", "trace"])
@pytest.mark.parametrize("after_install", [False, True])
def test_isolated_partial_hook_setup_restores_both_and_keeps_original_error(
    monkeypatch, hook, after_install
):
    context = _controller_context()
    prior, trace = sys.getprofile(), sys.gettrace()
    set_profile, set_trace = sys.setprofile, sys.settrace
    error, cause = OSError("hook setup"), KeyError("setup cause")
    calls = []
    failed = False

    def setter(name, actual, restore, function):
        nonlocal failed
        calls.append((name, actual is restore))
        if name == hook and actual is not restore and not failed:
            failed = True
            if after_install:
                function(actual)
            raise error from cause
        function(actual)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                sys, "setprofile", lambda value: setter("profile", value, prior, set_profile)
            )
            patch.setattr(sys, "settrace", lambda value: setter("trace", value, trace, set_trace))
            with _active_controller(context), pytest.raises(OSError) as caught:
                with stage._account(context):
                    raise AssertionError("Partial setup must not reach its body")
        assert caught.value is error and caught.value.__cause__ is cause
        assert context.hook_setup_error is context.hook_primary is error
        failure = next(row[1] for row in context.hook_states if row[0] == "failure")
        assert (failure[hook] is not (prior if hook == "profile" else trace)) is after_install
        assert ("trace", True) in calls and ("profile", True) in calls
        assert sys.getprofile() is prior and sys.gettrace() is trace
        assert context.hook_states[-1][1] == dict(profile=prior, trace=trace)
    finally:
        set_trace(trace)
        set_profile(prior)


@pytest.mark.parametrize("failed_hook", ["profile", "trace", "both"])
@pytest.mark.parametrize("source_fails", [False, True])
def test_isolated_unwind_cleanup_attempts_both_and_never_replaces_primary(
    monkeypatch, failed_hook, source_fails
):
    context = _controller_context()
    prior, trace = sys.getprofile(), sys.gettrace()
    set_profile, set_trace = sys.setprofile, sys.settrace
    primary, cause = ArithmeticError("original source"), KeyError("source cause")
    captures = {name: OSError(name + " restore") for name in ("trace", "profile")}
    failed, calls = set(), []

    def setter(name, value, restore, function):
        calls.append((name, value is restore))
        if value is restore and name not in failed and failed_hook in (name, "both"):
            failed.add(name)
            raise captures[name]
        function(value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(
                sys, "setprofile", lambda value: setter("profile", value, prior, set_profile)
            )
            patch.setattr(sys, "settrace", lambda value: setter("trace", value, trace, set_trace))
            expected = ArithmeticError if source_fails else stage.literal._CaptureStop
            with _active_controller(context), pytest.raises(expected) as caught:
                with stage._account(context):
                    if source_fails:
                        raise primary from cause
        if source_fails:
            assert caught.value is primary and caught.value.__cause__ is cause
        assert ("trace", True) in calls and ("profile", True) in calls
        assert context.observation_error in captures.values()
        assert context.hook_cleanup_errors and context.observation_errors
        assert sys.getprofile() is prior and sys.gettrace() is trace
        assert context.hook_states[-1][1] == dict(profile=prior, trace=trace)
    finally:
        set_trace(trace)
        set_profile(prior)


def test_isolated_inherited_call_rejection_preserves_exact_hooks_and_primary():
    context = _controller_context()
    prior, trace = sys.getprofile(), sys.gettrace()
    primary, cause = ValueError("inherited call rejection"), KeyError("guard cause")

    def forbidden():
        raise AssertionError("Rejected call must not reach body")

    def inherited(frame, event, arg):
        if event == "call" and frame.f_code is forbidden.__code__:
            raise primary from cause
        if prior is not None:
            prior(frame, event, arg)

    sys.setprofile(inherited)
    try:
        with _active_controller(context), pytest.raises(ValueError) as caught:
            with stage._account(context):
                forbidden()
        assert caught.value is primary and caught.value.__cause__ is cause
        assert sys.getprofile() is inherited and sys.gettrace() is trace
        assert {name for name, _ in context.hook_attempts} >= {"trace_restore", "profile_restore"}
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)


def test_real_issued_cache_tuples_survive_tail_without_reconstruction(ready):
    cache = ready.parent.context.parent
    original = tuple(
        (role, actual, stage.previous.caches._OBJECTS[actual]) for role, actual in cache.objects
    )
    assert original
    for role, _actual, issued in original:
        assert type(issued) is tuple and len(issued) == 2
        assert issued[0] is cache and type(issued[1]) is type(role) and issued[1] == role
    child = stage.prepare(ready.request, enabled=True)
    context = stage._ISSUED[child]
    for _role, actual, issued in original:
        assert stage.previous.caches._OBJECTS[actual] is issued
        assert any(value is issued for value in context.inherited_links)
    stage.literal._same(stage._registry_links(context), context.inherited_links)
    assert child.partial_phase is cache.phase


@pytest.mark.parametrize(
    "mutation",
    [
        "remove",
        "equal_tuple",
        "direct_context",
        "wrong_context",
        "wrong_role",
    ],
)
@pytest.mark.parametrize("when", ["preflight", "before_helper", "completed_child"])
def test_real_cache_issuance_tuple_mutation_refuses_without_later_delegate(
    ready, monkeypatch, refused, mutation, when
):
    cache = ready.parent.context.parent
    role, actual = cache.objects[0]
    registry = stage.previous.caches._OBJECTS
    issued = registry[actual]
    assert type(issued) is tuple and issued[0] is cache and issued[1] == role

    def change():
        # All owners/objects originate from the real issued synthetic API
        # chain. Only this negative-control registry entry is then mutated.
        if mutation == "remove":
            registry.pop(actual)
        elif mutation == "equal_tuple":
            replacement = (issued[0], issued[1])
            assert replacement is not issued
            registry[actual] = replacement
        elif mutation == "direct_context":
            registry[actual] = cache
        elif mutation == "wrong_context":
            registry[actual] = (NS(), role)
        else:
            registry[actual] = (cache, "different-role")

    if when == "completed_child":
        child = stage.prepare(ready.request, enabled=True)
        context = stage._ISSUED[child]
        before = stage._snapshot(context).identity
        counters = dict(ready.counters)
        change()
        assert stage._snapshot(context).identity == before
        with refused() as caught:
            _ = child.partial_phase
        assert caught.value.stage == "owner_drift" and context.invalid
        assert ready.counters == counters
        return
    if when == "preflight":
        change()
    else:
        original = stage._namespace

        def namespace(context):
            original(context)

            class Events(list):
                def append(self, row):
                    super().append(row)
                    if row[0] == "_init_kludge_enter":
                        change()

            context.events = Events()
            context.tape.events = context.events

        monkeypatch.setattr(stage, "_namespace", namespace)
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    error = caught.value
    assert error.source_error is not None and error.capture_error is None
    assert ready.counters["_init_kludge"] == ready.counters["_init_kludge_time"] == 0
    assert not error.partial["usable_child_available"]
    if when == "preflight":
        assert ready.counters["complete"] == 0 and error.trial is None
    else:
        assert ready.counters["complete"] == 1


@pytest.mark.parametrize(
    "link",
    [
        "dyna_issuer",
        "dyna_retirement",
        "cache_issuer",
        "cache_retirement",
        "assembly_issuer",
        "assembly_retirement",
        "callback_issuer",
    ],
)
@pytest.mark.parametrize("mutation", ["remove", "replace"])
def test_completed_child_requires_actual_inherited_issuance_and_retirement_links(
    ready, refused, link, mutation
):
    child = stage.prepare(ready.request, enabled=True)
    context = stage._ISSUED[child]
    dyna, cache, prefix = context.parent, context.parent.parent, context.refs[8]
    caches, assembly = stage.previous.caches, stage.previous.caches.previous
    links = {
        "dyna_issuer": (stage.previous._ISSUED, ready.request.dyna_owner),
        "dyna_retirement": (stage.previous._FORWARDED, ready.request.dyna_owner),
        "cache_issuer": (caches._ISSUED, dyna.request.cache_owner),
        "cache_retirement": (caches._FORWARDED, dyna.request.cache_owner),
        "assembly_issuer": (assembly._ISSUED, cache.request.phase_owner),
        "assembly_retirement": (assembly._FORWARDED, cache.request.phase_owner),
        "callback_issuer": (assembly.callbacks._ISSUED, prefix.request.callbacks),
    }
    before = stage._snapshot(context).identity
    registry, key = links[link]
    if mutation == "remove":
        registry.pop(key)
    else:
        registry[key] = NS()  # Negative link mutation; never an authority input.
    assert stage._snapshot(context).identity == before
    with refused() as caught:
        _ = child.partial_phase
    assert caught.value.stage == "owner_drift" and context.invalid


@pytest.mark.parametrize("mutation", ["code", "delegate"])
def test_original_wrapper_and_delegate_links_stay_live_after_tail(ready, refused, mutation):
    child = stage.prepare(ready.request, enabled=True)
    context = stage._ISSUED[child]
    wrapper = vars(type(context.phase))["_init_kludge"]
    before = stage._snapshot(context).identity
    prior_code = wrapper.__code__
    cells = dict(zip(prior_code.co_freevars, wrapper.__closure__, strict=True))
    cell = cells["delegate"]
    delegate = cell.cell_contents
    try:
        if mutation == "code":
            wrapper.__code__ = prior_code.replace(co_name="retargeted_helper_wrapper")
        else:
            cell.cell_contents = type(delegate)(
                delegate.__code__,
                delegate.__globals__,
                delegate.__name__,
                delegate.__defaults__,
                delegate.__closure__,
            )
        assert stage._snapshot(context).identity == before
        with refused() as caught:
            _ = child.partial_phase
        assert caught.value.stage == "owner_drift" and context.invalid
    finally:
        wrapper.__code__ = prior_code
        cell.cell_contents = delegate


@pytest.mark.parametrize(
    "method",
    [
        "_init_kludge",
        "_init_kludge_time",
        "die_unless_kind_seed",
        "die_unless_kind_init_or_sim",
    ],
)
def test_raw_phase_methods_after_success_never_enter_another_body_or_observer(ready, method):
    child = stage.prepare(ready.request, enabled=True)
    phase = child.partial_phase
    context = stage._ISSUED[child]
    counters, events = dict(ready.counters), tuple(context.events)
    with pytest.raises(
        (
            stage.TailRejected,
            stage.previous.DynaRejected,
            stage.previous.caches.CacheConstructionRejected,
            stage.previous.caches.previous.AssemblyRejected,
        )
    ):
        getattr(phase, method)()
    assert ready.counters == counters and tuple(context.events) == events


@pytest.mark.parametrize("kind", ["INIT", "SIM"])
def test_issued_seed_owner_cannot_be_relabelled_before_tail(ready, refused, kind):
    phase = ready.parent.context.phase
    phase.kind = getattr(type(phase.kind), kind)
    counters = dict(ready.counters)
    with refused() as caught:
        stage.prepare(ready.request, enabled=True)
    assert caught.value.source_error is not None and caught.value.trial is None
    assert ready.counters == counters and "_run_sim" not in vars(phase.p)


def test_postmutation_use_calls_only_successor_validator_not_stale_parameter_epochs(ready):
    child = stage.prepare(ready.request, enabled=True)
    context = stage._ISSUED[child]
    old = stage.previous
    old_key = old._key_api()
    forbidden = {
        old._validate.__code__,
        old._closed_claim.__code__,
        old.caches._validate.__code__,
        getattr(old_key, old.KEY_CLOSED_CHECK).__code__,
    }
    reached, validations = [], []
    new = getattr(ready.api, stage.KEY_CLOSED_CHECK).__code__
    prior, trace = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        if event == "call":
            if frame.f_code in forbidden:
                reached.append(frame.f_code.co_qualname)
                raise AssertionError("A consumed pre-mutation validator was reopened")
            if frame.f_code is new:
                validations.append(frame.f_code.co_qualname)
        if prior is not None:
            prior(frame, event, arg)

    sys.setprofile(profile)
    try:
        assert child.partial_phase is context.phase and not reached and validations
    finally:
        sys.setprofile(prior)
        sys.settrace(trace)


def test_completed_tail_does_not_grant_full_phase_or_world_authority(ready, refused):
    child = stage.prepare(ready.request, enabled=True)
    with refused() as caught:
        stage.require_phase(child)
    assert caught.value.stage == "phase_incomplete"


@pytest.mark.parametrize(
    "origin,parent_method,target,capture_failure",
    [
        (origin, parent, target, False)
        for origin in ("event", "profile")
        for parent in ("__init__", "_init_events")
        for target in ("same", "next")
    ]
    + [("event", "__init__", "next", True), ("profile", "__init__", "next", True)],
)
def test_inherited_dyna_entry_guards_on_actual_cache_chain(
    monkeypatch, request, tmp_path, origin, parent_method, target, capture_failure
):
    # Execute the eleven previously written, unrun dyna controls unchanged
    # through the same genuine cache issuer used by the tail. These wrappers
    # are not additional independent cases or a second authority provider.
    prepared = dyna_controls.ready.__wrapped__(monkeypatch, request)
    refused = dyna_controls.refused.__wrapped__(tmp_path)
    dyna_controls.test_active_callback_cannot_reenter_or_seize_next_method_slot(
        prepared, monkeypatch, refused, origin, parent_method, target, capture_failure
    )


def test_inherited_dyna_simultaneous_entry_and_capture_keep_primary(monkeypatch, request, tmp_path):
    prepared = dyna_controls.ready.__wrapped__(monkeypatch, request)
    refused = dyna_controls.refused.__wrapped__(tmp_path)
    dyna_controls.test_enter_reentry_remains_primary_when_same_enter_capture_fails(
        prepared, monkeypatch, refused
    )
