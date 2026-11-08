"""Written, unrun coordinator controls; no stand-in grants source ownership."""

import ast
import contextlib
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_world_phase_construction as stage
from validation.betse import betse_native_world_phase_construction_software as software

SOFTWARE_RELEASE = "BETSE_NATIVE_WORLD_PHASE_CONSTRUCTION_SOFTWARE_RELEASED"
_BLOCKADE_FAILURES = ()


def _ancestry_metadata(monkeypatch, depth, mutation=None):
    """Actual recursive code with explicit metadata seams, never an issued owner."""

    class Token:
        pass

    request, world = Token(), Token()
    request.world_parameters, request.callbacks = world, object()
    transition = NS(
        invalid=False,
        entry_error=None,
        request=request,
        claim=object(),
        p=object(),
        thread=stage.get_ident(),
    )
    events, contexts, modules = [], [], []

    def same(left, right):
        assert left == right

    for index in range(depth):
        parent = None if index == 0 else contexts[-1]
        predecessor = None if parent is None else NS(authority=parent)
        binding = ("binding", index)
        module = NS(_WORLD={})

        def bindings(index=index, binding=binding):
            events.append(("binding", index))
            return binding

        module._bindings = bindings
        context = NS(
            world_transition=transition,
            world_module=module,
            world_index=index,
            world_mode=stage.MODE,
            invalid=False,
            thread=transition.thread,
            parent=parent,
            world_predecessor=predecessor,
            world_ticket=(
                transition,
                world,
                transition.claim,
                request.callbacks,
                transition.p,
                predecessor,
            ),
            world_source_files={},
            bindings=binding,
            runtime_types={},
            runtime_bindings={},
            objects=[],
            world_before=NS(identity="state" + str(index)),
            world_before_graph=(("objects", index), ("edges", index)),
            evidence=None,
            active=False,
        )
        module._WORLD[request] = context
        modules.append(module)
        contexts.append(context)
    transition.api = NS(stages=modules, helpers=NS(literal=NS(_same=same)))
    monkeypatch.setattr(stage, "_CONSUMED", {request: transition})
    monkeypatch.setattr(stage, "_CLAIMED", {world: transition})

    def parameter(actual):
        assert actual is transition
        events.append(("parameter", depth - 1))

    def aliases(actual):
        assert actual is transition
        events.append(("aliases", sys._getframe(1).f_locals["context"].world_index))

    def state(context, *, baseline=False):
        assert baseline is True
        events.append(("state", context.world_index))
        return context.world_before, context.world_before_graph

    monkeypatch.setattr(stage, "_world_parameter_authority", parameter)
    monkeypatch.setattr(stage, "_world_live_aliases", aliases)
    monkeypatch.setattr(stage, "_world_state", state)
    if mutation is not None:
        assert depth >= 2
        child = contexts[-1]
        child.scope_bindings = ("unchanged scope",)

        def after_parent(context):
            assert context is child
            events.append(("after_parent_callback", child.world_index))
            if mutation == "invalid":
                contexts[0].invalid = True
            else:
                modules[0]._WORLD[request] = object()
            return child.scope_bindings

        modules[-1]._scope_bindings = after_parent
    return NS(context=contexts[-1], contexts=contexts, transition=transition, events=events)


@pytest.mark.parametrize("depth", [1, 2, 3, 4])
def test_ancestry_measurement_counts_actual_recursive_metadata_checks(tmp_path, monkeypatch, depth):
    model = _ancestry_metadata(monkeypatch, depth)
    stage._world_stage_runtime(model.context)
    expected = [index for top in range(depth - 1, -1, -1) for index in range(top, -1, -1)]
    assert [index for kind, index in model.events if kind == "parameter"] == [depth - 1] * 2
    assert [index for kind, index in model.events if kind == "binding"] == expected
    assert [index for kind, index in model.events if kind == "state"] == list(range(depth))
    software.snapshot.write_json(
        tmp_path / "ancestry-measurement.json",
        dict(
            depth=depth,
            authority_checks=len(expected),
            parameter_checks=2,
            expected_triangular_count=depth * (depth + 1) // 2,
            runtime_state_checks=depth,
            ordered_events=model.events,
            actual_parameter_native_or_owner_calls=0,
            scope=(
                "actual private recursive driver code with explicitly replaced "
                "metadata dependencies"
            ),
            successful_issued_owner_or_scientific_credit=0,
        ),
    )


@pytest.mark.parametrize("mutation", ["invalid", "registry"])
def test_ancestry_measurement_recheck_after_child_callback_preserves_refusal(
    tmp_path, monkeypatch, mutation
):
    model = _ancestry_metadata(monkeypatch, 2, mutation)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage._world_stage_runtime(model.context)
    assert model.transition.invalid
    assert caught.value is model.transition.entry_error
    assert not any(kind == "state" for kind, _ in model.events)
    assert model.events.index(("after_parent_callback", 1)) > model.events.index(("binding", 0))
    software.snapshot.write_json(
        tmp_path / "ancestry-mutation-refusal.json",
        dict(
            mutation=mutation,
            ordered_events=model.events,
            primary=type(caught.value).__qualname__,
            message=str(caught.value),
            original_entry_error_retained=True,
            runtime_state_calls=0,
            mutation_occurs_after_earlier_parent_authentication=True,
            removing_later_parent_recheck_would_drop_this_authority_check=True,
            actual_parameter_native_or_owner_calls=0,
            scientific_or_owner_credit=0,
        ),
    )


@pytest.mark.parametrize("boundary", ("_world_stage_runtime", "_world_stage_authority"))
@pytest.mark.parametrize("location", ("binding", "state"))
def test_ancestry_parameter_change_during_pass_refuses_before_resume(
    monkeypatch, boundary, location
):
    model = _ancestry_metadata(monkeypatch, 3)
    original_parameter = stage._world_parameter_authority
    checks, resumed = [], []
    changed = False
    primary = ValueError("actual parameter/claim changed during metadata callback")

    def parameter(transition):
        checks.append(changed)
        if changed:
            raise primary
        original_parameter(transition)

    def mutate(*args, **kwargs):
        nonlocal changed
        changed = True
        if location == "binding":
            return model.context.bindings
        return model.context.world_before, model.context.world_before_graph

    monkeypatch.setattr(stage, "_world_parameter_authority", parameter)
    if location == "binding":
        monkeypatch.setattr(model.context.world_module, "_bindings", mutate)
    else:
        original_state = stage._world_state

        def state(context, **kwargs):
            if context is model.context:
                return mutate()
            return original_state(context, **kwargs)

        monkeypatch.setattr(stage, "_world_state", state)
        # Authority-only calls do not observe state, so mutate their last live
        # binding instead; both public boundaries must bracket callbacks.
        if boundary == "_world_stage_authority":
            monkeypatch.setattr(model.context.world_module, "_bindings",
                                lambda: (mutate(), model.context.bindings)[1])
    with pytest.raises(ValueError) as caught:
        getattr(stage, boundary)(model.context)
        resumed.append(True)
    assert caught.value is primary and checks == [False, True] and not resumed


@pytest.mark.parametrize("boundary", ("_world_stage_runtime", "_world_stage_authority"))
def test_ancestry_pass_rejects_foreign_transition_without_admitting_it(monkeypatch, boundary):
    model = _ancestry_metadata(monkeypatch, 2)
    model.contexts[0].world_transition = NS(**vars(model.transition))
    with pytest.raises(stage.WorldPhaseRejected, match="Foreign transition"):
        getattr(stage, boundary)(model.context)
    assert model.transition.invalid
    assert not any(kind == "state" for kind, _ in model.events)


def test_ancestry_each_pass_revalidates_shared_history_without_a_result_cache(monkeypatch):
    model = _ancestry_metadata(monkeypatch, 4)
    stage._world_stage_runtime(model.context)
    stage._world_stage_runtime(model.context)
    assert sum(kind == "parameter" for kind, _ in model.events) == 4
    original = stage._world_parameter_authority
    primary = ValueError("changed history on the next validation")

    def fail(transition):
        original(transition)
        raise primary

    monkeypatch.setattr(stage, "_world_parameter_authority", fail)
    before = tuple(model.events)
    with pytest.raises(ValueError) as caught:
        stage._world_stage_runtime(model.context)
    assert caught.value is primary and len(model.events) == len(before) + 1


def construction_interface_metadata():
    """Actual pinned generator code; no module, factory or generator execution."""
    path = stage._module_file(stage.KEY_MODULE)
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == stage.KEY_SOURCE_SHA256
    module = ModuleType(stage.KEY_MODULE)
    module.__file__, module.contextmanager = str(path), contextlib.contextmanager
    code = compile(raw, str(path), "exec", dont_inherit=True)
    original = next(
        value
        for value in code.co_consts
        if type(value) is CodeType and value.co_name == "construction"
    )
    generator = FunctionType(original, vars(module))
    generator.__kwdefaults__ = {"enabled": False}
    module.construction = contextlib.contextmanager(generator)
    return module, raw, path, generator


def check_construction_interface(model):
    module, raw, path, _ = model
    stage._source_interface(module, raw, path, ("construction",), contextmanagers=("construction",))
    stage._contextmanager_bindings()


def test_constructor_interface_actual_key_contextmanager_metadata_passes():
    model = construction_interface_metadata()
    check_construction_interface(model)
    check_construction_interface(model)  # Warm metadata cache still checks live objects.
    module, _, _, generator = model
    assert module.construction.__globals__ is vars(contextlib)
    assert generator.__globals__ is vars(module)
    assert module.construction.__closure__[0].cell_contents is generator
    assert not stage._ACTIVE and not stage._CLAIMED


def test_constructor_interface_dependency_gate_accepts_actual_decorated_shape(monkeypatch):
    model = construction_interface_metadata()
    key, raw, path, _ = model
    key.WORLD_CONSTRUCTION_LAW = stage.KEY_LAW
    modules = {stage.KEY_MODULE: key}
    names = {
        stage.KEY_MODULE: ("validate_closed_seed",),
        stage.PARAMETER_MODULE: ("validate_completed_history",),
        stage.CALLBACK_MODULE: (),
        **dict.fromkeys(stage.STAGE_MODULES, (stage.CONSTRUCT_HOOK, stage.CHECK_HOOK)),
    }
    names[stage.STAGE_MODULES[-1]] += (stage.SEAL_HOOK, stage.CHECK_SEAL_HOOK)
    for name, functions in names.items():
        module = modules.setdefault(name, ModuleType(name))
        module.WORLD_MODE = stage.MODE
        source_path = stage._module_file(name)
        codes = compile(source_path.read_bytes(), str(source_path), "exec", dont_inherit=True)
        for function in functions:
            code = next(
                value
                for value in codes.co_consts
                if type(value) is CodeType and value.co_name == function
            )
            setattr(module, function, FunctionType(code, vars(module)))
    helper = object()
    monkeypatch.setattr(stage, "_import_helper_bound", lambda expected: helper)
    monkeypatch.setattr(stage, "_import_bound", lambda name, expected: modules[name])
    result = stage._dependencies()
    assert result.key is key and result.helpers is helper
    assert result.key.construction is key.construction
    assert result.stages == tuple(modules[name] for name in stage.STAGE_MODULES)
    assert raw == path.read_bytes() and not stage._CLAIMED


@pytest.mark.parametrize(
    "change",
    (
        "wrapper_code",
        "wrapper_defaults",
        "wrapper_keywords",
        "wrapper_name",
        "wrapped",
        "closure",
        "generator_code",
        "generator_globals",
        "generator_defaults",
        "generator_keywords",
        "decorator_alias",
        "raw_generator",
    ),
)
def test_constructor_interface_live_drift_refuses_after_warm_metadata(change):
    model = construction_interface_metadata()
    check_construction_interface(model)
    module, _, _, generator = model
    function = module.construction
    if change == "wrapper_code":
        function.__code__ = function.__code__.replace(co_name="retargeted")
    elif change == "wrapper_defaults":
        function.__defaults__ = (None,)
    elif change == "wrapper_keywords":
        function.__kwdefaults__ = {"enabled": False}
    elif change == "wrapper_name":
        function.__name__ = "other"
    elif change == "wrapped":
        function.__wrapped__ = FunctionType(generator.__code__, vars(module))
    elif change == "closure":
        function.__closure__[0].cell_contents = FunctionType(generator.__code__, vars(module))
    elif change == "generator_code":
        generator.__code__ = generator.__code__.replace(co_name="retargeted")
    elif change == "generator_globals":
        foreign = FunctionType(generator.__code__, dict(vars(module)))
        foreign.__kwdefaults__ = {"enabled": False}
        module.construction = contextlib.contextmanager(foreign)
    elif change == "generator_defaults":
        generator.__defaults__ = (None,)
    elif change == "generator_keywords":
        generator.__kwdefaults__["enabled"] = 0
    elif change == "decorator_alias":
        module.contextmanager = lambda value: value
    elif change == "raw_generator":
        module.construction = generator
    with pytest.raises(ValueError):
        check_construction_interface(model)


@pytest.mark.parametrize("change", ("class", "base", "init", "enter", "exit"))
def test_constructor_interface_stdlib_dispatch_drift_refuses(monkeypatch, change):
    model = construction_interface_metadata()
    check_construction_interface(model)
    if change in ("class", "base"):
        name = "_GeneratorContextManager" if change == "class" else "_GeneratorContextManagerBase"
        original = getattr(contextlib, name)
        replacement = type(original)(original.__name__, original.__bases__, dict(vars(original)))
        monkeypatch.setattr(contextlib, name, replacement)
    else:
        cls = (
            contextlib._GeneratorContextManagerBase
            if change == "init"
            else contextlib._GeneratorContextManager
        )
        function = getattr(cls, "__" + change + "__")
        monkeypatch.setattr(function, "__code__", function.__code__.replace(co_name="retargeted"))
    with pytest.raises(ValueError, match="contextmanager"):
        check_construction_interface(model)


def test_constructor_interface_undecorated_hook_remains_strict():
    model = construction_interface_metadata()
    module, raw, path, _ = model
    with pytest.raises(ValueError, match="source function"):
        stage._source_interface(module, raw, path, ("construction",))


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        pytest.skip("Source preparation only; no software execution released")
    with _blockade(request, tmp_path):
        yield


@contextmanager
def _blockade(request, tmp_path):
    global _BLOCKADE_FAILURES
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)
    prior, trace = getters[0](), getters[1]()
    attempted = []
    state = software.reuse._run_state()
    state.hook_before = (prior, trace)
    state.restore_setters, state.restore_getters = setters, getters

    def profile(frame, event, arg):
        if event == "call" and software.is_forbidden_frame(frame):
            attempted.append((frame.f_code.co_filename, frame.f_code.co_qualname))
            raise AssertionError("Actual phase/parameter/native source entry forbidden")
        if prior is not None:
            prior(frame, event, arg)

    before = tuple(stage._ISSUED.items())
    try:
        setters[0](profile)
        yield state
        assert not attempted and tuple(stage._ISSUED.items()) == before
        assert getters[0]() is profile and getters[1]() is trace
        state.status = 0
    except BaseException as error:
        state.primary, state.primary_stage = error, "fixture_body_or_guard"
        raise
    finally:
        try:
            software.reuse._restore_hooks(state, (prior, trace), (profile, trace), setters, getters)
        except BaseException as error:
            state.cleanup_errors = (*state.cleanup_errors, ("fixture_restore_entry", error, None))
            for index in (1, 0):
                try:
                    setters[index]((prior, trace)[index])
                except BaseException as capture:
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("fixture_emergency", capture, index),
                    )
        # Receipt is independent of either restoration's success. It logs
        # attempts/partial cleanup; final identity sampling follows the writer.
        try:
            software.snapshot.write_json(
                tmp_path / "native-blocked.json",
                dict(
                    nodeid=request.node.nodeid,
                    attempted=attempted,
                    source_native_or_scientific_credit=0,
                    primary=software.reuse._error_record(state.primary),
                    secondary_cleanup=[
                        software.reuse._error_record(row[1]) for row in state.cleanup_errors
                    ],
                    final_cleanup_pending=True,
                    final_hook_restoration_claimed=False,
                ),
            )
        except BaseException as error:
            state.evidence_errors = (*state.evidence_errors, ("fixture_receipt", error, tmp_path))
        if state.primary is not None:
            try:
                state.primary.world_phase_blockade = state
            except BaseException as error:
                state.secondary = (
                    *state.secondary,
                    ("fixture_primary_attachment", error, state.primary),
                )
        try:
            software.reuse._restore_hooks(
                state,
                (prior, trace),
                (prior, trace),
                setters,
                getters,
                record_active=False,
            )
        except BaseException as error:
            state.cleanup_errors = (
                *state.cleanup_errors,
                ("fixture_final_restore_entry", error, None),
            )
            for index in (1, 0):
                try:
                    setters[index]((prior, trace)[index])
                except BaseException as capture:
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("fixture_final_emergency", capture, index),
                    )
        first, second = [None, None], [None, None]
        for values, order in ((first, (0, 1)), (second, (1, 0))):
            for index in order:
                try:
                    values[index] = getters[index]()
                except BaseException as error:
                    values[index] = error
                    state.cleanup_errors = (
                        *state.cleanup_errors,
                        ("fixture_final_read", error, index),
                    )
        state.hook_samples = ((first[0], first[1]), (second[0], second[1]))
        state.hook_after = state.hook_samples[-1]
        state.hooks_restored = (
            first[0] is prior and first[1] is trace and second[0] is prior and second[1] is trace
        )
        if not state.hooks_restored:
            state.cleanup_errors = (
                *state.cleanup_errors,
                ("fixture_final_identity_mismatch", None, state.hook_samples),
            )
        failed = (
            state.primary is not None
            or state.cleanup_errors
            or state.evidence_errors
            or state.secondary
            or not state.guard_active_on_cleanup
            or not state.hooks_restored
        )
        if failed:
            _BLOCKADE_FAILURES = (*_BLOCKADE_FAILURES, state)
        if state.primary is None and failed:
            raise AssertionError("Native-blocked fixture cleanup/evidence incomplete")


def test_preparation_declares_one_claim_and_no_intermediate_closed_record():
    plan = stage.source_plan()
    assert plan["mode"] == stage.MODE
    assert plan["stages"] == ("phase_prefix", "caches", "dyna", "seed_tail")
    assert plan["construction_before_any_phase_allocation"] is True
    assert plan["one_active_claim_through_all_stages"] is True
    assert plan["phase_sealing_inside_claim"] is True
    assert plan["public_closed_records_between_stages"] is False
    assert plan["key_source"] is None and plan["key_review"] is None
    assert all(value is None for value in plan["stage_sources"])


def test_preparation_unbound_contract_refuses_before_any_import(monkeypatch):
    calls = []

    def forbidden(name):
        calls.append(name)
        raise AssertionError("No unsealed producer import may supply authority")

    monkeypatch.setattr(stage.importlib, "import_module", forbidden)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage._dependencies()
    assert caught.value.stage == "unbound_contract" and calls == []


@pytest.mark.parametrize("mode", [None, "prepared_callback_seven_load_seed_prefix", "SEED"])
def test_preparation_legacy_mode_never_relabels_a_world_owner(mode):
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage.from_world_ready(object(), object(), law_id=stage.LAW_ID, mode=mode)
    assert caught.value.stage == "law"


def test_preparation_selected_mode_is_still_gated_by_missing_real_producers():
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage.from_world_ready(object(), object(), law_id=stage.LAW_ID, mode=stage.MODE)
    assert caught.value.stage == "unbound_contract"


@pytest.mark.parametrize("enabled", [False, None, 1])
def test_preparation_release_precedes_any_claim_or_stage_hook(monkeypatch, enabled):
    monkeypatch.setenv(stage.RELEASE, "1")

    def forbidden():
        raise AssertionError("No constructor authority at source preparation")

    monkeypatch.setattr(stage, "_dependencies", forbidden)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage.prepare(None, enabled=enabled)
    assert caught.value.stage == "release"


def test_preparation_plain_record_and_manually_created_request_are_not_authority():
    request = stage.Request(object(), object(), "parameter", "callback", "source", stage.MODE, "id")
    assert request not in stage._REQUESTS
    with pytest.raises(TypeError):
        request.__reduce_ex__(5)
    with pytest.raises(TypeError):
        stage.WorldPhaseOwner()
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage._validate(object())
    assert caught.value.stage == "owner"


class FalseFailure(ValueError):
    def __bool__(self):
        return False


def _controller(monkeypatch):
    """Abstract ordering tokens only: no phase, real p, owner or issuer mock.

    This exercises the private coordinator's lifetime/failure plumbing. It
    never calls public prepare/from_world_ready, opens real Key permission,
    or manufactures native stage evidence. Positive source tests stay held.
    """
    log, claim_state = [], NS(active=False, closed=False, error=None, record_error=None)
    record, parameter_token, world_token = object(), object(), object()

    class MetadataClaim:
        @property
        def record(self):
            if claim_state.active or not claim_state.closed:
                raise AssertionError("No intermediate public record")
            if claim_state.record_error is not None:
                raise claim_state.record_error
            log.append("closed record")
            return record

    claim = MetadataClaim()

    @contextmanager
    def construction(owner, *, law_id, enabled):
        assert owner is world_token and law_id == stage.KEY_LAW and enabled is True
        claim_state.active = True
        log.append("claim enter before any phase")
        try:
            yield claim
        except BaseException as error:
            claim_state.error = error
            raise
        finally:
            claim_state.active, claim_state.closed = False, True
            log.append("claim exit")

    context = NS(
        request=NS(world_parameters=world_token),
        parents=(object(), parameter_token),
        api=NS(key=NS(construction=construction)),
        p=parameter_token,
        stage="construction_claim_before_phase_birth",
        invalid=False,
        entry_error=None,
        primary=None,
        capture_error=None,
        capture_errors=(),
        claim_errors=(),
        claim=None,
        parameter_record=None,
        failed_claim=None,
        failed_claim_partial=None,
        failed_stages=(),
        stage_partials=(),
        evidence=[],
        last_returned=None,
        raw_seal=None,
        seal=None,
        trial=None,
        work=[],
        executing=None,
        driver_frame=None,
        step_frame=None,
        dispatch_ticket=None,
    )

    def active(actual):
        assert actual is context and claim_state.active and actual.claim is claim
        if actual.entry_error is not None:
            raise actual.entry_error

    def step(actual, index):
        active(actual)
        assert index == len(actual.evidence)
        assert actual.dispatch_ticket == (index, actual.driver_frame)
        actual.dispatch_ticket = None
        log.append(stage.STAGES[index])
        actual.evidence.append(object())

    def seal(actual):
        active(actual)
        assert len(actual.evidence) == 4
        log.append("fallible phase seal inside claim")
        actual.raw_seal = actual.seal = object()
        actual.trial = object()  # Ordering token, never a source trial or owner.

    def closed(actual):
        assert not claim_state.active and claim_state.closed
        assert actual.claim is claim and actual.parameter_record is record
        log.append("exact closed validation")
        return record

    monkeypatch.setattr(stage, "_active_claim", active)
    monkeypatch.setattr(stage, "_step", step)
    monkeypatch.setattr(stage, "_seal_active", seal)
    monkeypatch.setattr(stage, "_check_bindings", lambda actual: None)
    monkeypatch.setattr(stage, "_closed", closed)
    return NS(
        context=context,
        log=log,
        state=claim_state,
        claim=claim,
        record=record,
        active=active,
        step=step,
        seal=seal,
    )


def test_ordering_claim_spans_all_stages_and_fallible_sealing_before_closed_validation(monkeypatch):
    metadata = _controller(monkeypatch)
    before = tuple(stage._ISSUED.items())
    stage._coordinate(metadata.context)
    assert metadata.log == [
        "claim enter before any phase",
        *stage.STAGES,
        "fallible phase seal inside claim",
        "claim exit",
        "closed record",
        "exact closed validation",
    ]
    assert metadata.context.primary is None and metadata.context.capture_error is None
    assert tuple(stage._ISSUED.items()) == before  # Private ordering is never publication.


@pytest.mark.parametrize("index", range(4))
def test_ordering_stage_failure_keeps_primary_cause_and_never_continues(monkeypatch, index):
    metadata = _controller(monkeypatch)
    primary, cause, partial = FalseFailure("original stage"), KeyError("cause"), object()
    primary.partial = partial

    def step(context, reached):
        metadata.active(context)
        if reached == index:
            context.stage = stage.STAGES[index]
            raise primary from cause
        metadata.step(context, reached)

    monkeypatch.setattr(stage, "_step", step)
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.state.error is primary
    assert len(metadata.context.evidence) == index
    assert metadata.context.stage_partials[-1] == (stage.STAGES[index], partial)
    assert "fallible phase seal inside claim" not in metadata.log
    assert "exact closed validation" not in metadata.log


def test_ordering_fallible_phase_seal_fails_inside_claim_as_capture_not_new_source(monkeypatch):
    metadata = _controller(monkeypatch)
    capture, raw = OSError("phase capture"), object()

    def seal(context):
        metadata.active(context)
        context.raw_seal = raw
        raise capture

    monkeypatch.setattr(stage, "_seal_active", seal)
    stage._coordinate(metadata.context)
    assert metadata.state.error is capture and metadata.context.raw_seal is raw
    assert metadata.context.primary is None and metadata.context.capture_error is capture
    assert metadata.context.invalid and metadata.context.trial is None
    assert "exact closed validation" not in metadata.log


def test_ordering_closed_record_failure_keeps_original_source_and_secondary_capture(monkeypatch):
    metadata = _controller(monkeypatch)
    primary, cause, capture = FalseFailure("original"), KeyError("cause"), OSError("record")
    metadata.state.record_error = capture

    def step(context, index):
        raise primary from cause

    monkeypatch.setattr(stage, "_step", step)
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.capture_error is capture
    assert metadata.context.capture_errors[-1] == (
        "closed_parameter_record",
        capture,
        metadata.claim,
    )


def test_ordering_closed_authentication_refusal_cannot_publish_private_seal(monkeypatch):
    metadata = _controller(monkeypatch)
    refusal = ValueError("actual closed ancestry differs")

    def closed(context):
        assert context.parameter_record is metadata.record and not metadata.state.active
        raise refusal

    monkeypatch.setattr(stage, "_closed", closed)
    before = tuple(stage._ISSUED.items())
    stage._coordinate(metadata.context)
    assert metadata.context.primary is refusal and metadata.context.seal is not None
    assert tuple(stage._ISSUED.items()) == before


def test_ordering_claim_entry_failure_retains_failed_claim_parent_and_primary(monkeypatch):
    metadata = _controller(monkeypatch)
    primary, cause, failed, partial = (
        FalseFailure("claim entry"),
        KeyError("cause"),
        object(),
        object(),
    )
    primary.world_construction_claim, primary.partial = failed, partial

    @contextmanager
    def construction(*args, **kwargs):
        raise primary from cause
        yield  # No claim was entered; required only for the metadata generator shape.

    metadata.context.api.key.construction = construction
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.claim is None and metadata.context.trial is None
    assert metadata.context.failed_claim is failed
    assert metadata.context.failed_claim_partial is partial
    assert metadata.context.evidence == [] and metadata.log == []


def test_ordering_claim_exit_failure_retains_in_claim_seal_without_publication(monkeypatch):
    metadata = _controller(monkeypatch)
    original = metadata.context.api.key.construction
    failure = ValueError("parameter closure rejected")

    @contextmanager
    def construction(*args, **kwargs):
        with original(*args, **kwargs) as claim:
            yield claim
        raise failure

    metadata.context.api.key.construction = construction
    before = tuple(stage._ISSUED.items())
    stage._coordinate(metadata.context)
    assert metadata.context.primary is failure
    assert metadata.context.raw_seal is metadata.context.seal
    assert metadata.context.seal is not None and metadata.context.trial is not None
    assert "exact closed validation" not in metadata.log
    assert tuple(stage._ISSUED.items()) == before


def test_failure_envelope_retains_actual_primary_capture_and_partial_without_truthiness(
    monkeypatch,
):
    metadata = _controller(monkeypatch)
    primary, cause, capture, partial = (
        FalseFailure("source"),
        KeyError("cause"),
        OSError("capture"),
        object(),
    )
    primary.__cause__ = cause
    error = NS(source_error=primary, capture_error=capture, partial=partial)
    stage._retain_failure(metadata.context, error, "actual stage")
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.capture_error is capture and metadata.context.invalid
    assert metadata.context.stage_partials == (("actual stage", partial),)


def test_failure_recording_rejection_keeps_original_primary_and_claim_exit(monkeypatch):
    metadata = _controller(monkeypatch)
    primary, cause, capture = FalseFailure("source"), KeyError("cause"), OSError("recorder entry")

    def step(context, index):
        raise primary from cause

    def retain(*args):
        raise capture

    monkeypatch.setattr(stage, "_step", step)
    monkeypatch.setattr(stage, "_retain_failure", retain)
    stage._coordinate(metadata.context)
    assert metadata.context.primary is primary and primary.__cause__ is cause
    assert metadata.context.capture_error is capture and metadata.state.closed
    assert metadata.context.capture_errors[-1] == ("stage_failure_recording", capture, primary)


@pytest.mark.parametrize("next_index", [0, 1])
def test_step_claim_precedes_hook_and_caught_reentry_stays_poisoned(monkeypatch, next_index):
    # Only the private stage-call controller is exercised. No real phase,
    # parameter claim, stage evidence or public child is manufactured.
    context = NS(
        work=[],
        evidence=[],
        executing=None,
        entry_error=None,
        invalid=False,
        stage="metadata",
        request=NS(world_parameters=object(), callbacks=object()),
        claim=object(),
        last_returned=None,
        p=NS(),
        dispatch_ticket=None,
        driver_frame=None,
        step_frame=None,
        capture_errors=(),
        capture_error=None,
    )
    delegates = []
    raw = object()

    def active(actual):
        if actual.entry_error is not None:
            raise actual.entry_error

    def construct(actual, **kwargs):
        delegates.append("outer only")
        with pytest.raises(stage.WorldPhaseRejected):
            stage._step(actual, next_index)
        return raw

    context.api = NS(stages=(NS(**{stage.CONSTRUCT_HOOK: construct}),))
    monkeypatch.setattr(stage, "_active_claim", active)
    monkeypatch.setattr(stage, "_check_evidence", lambda *args: None)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        _dispatch_metadata_step(context, 0)
    assert context.entry_error is caught.value and context.invalid
    assert delegates == ["outer only"] and context.evidence == []
    assert context.last_returned is raw and len(context.work) == 2


def test_step_raw_return_precedes_any_failed_result_observation(monkeypatch):
    raw, refusal = object(), ValueError("stage evidence refused")
    context = NS(
        work=[],
        evidence=[],
        executing=None,
        entry_error=None,
        invalid=False,
        stage="metadata",
        request=NS(world_parameters=object(), callbacks=object()),
        claim=object(),
        last_returned=None,
        p=NS(),
        dispatch_ticket=None,
        driver_frame=None,
        step_frame=None,
        capture_errors=(),
        capture_error=None,
        api=NS(stages=(NS(**{stage.CONSTRUCT_HOOK: lambda *args, **kwargs: raw}),)),
    )

    def check(*args):
        assert context.last_returned is raw
        raise refusal

    monkeypatch.setattr(stage, "_active_claim", lambda actual: None)
    monkeypatch.setattr(stage, "_check_evidence", check)
    with pytest.raises(ValueError) as caught:
        _dispatch_metadata_step(context, 0)
    assert caught.value is refusal and context.last_returned is raw
    assert context.evidence == [] and context.executing is None
    assert context.work[-1]["error"] is refusal


def _dispatch_metadata_step(context, index):
    # A private control-flow ticket, never an issued parameter/source epoch.
    context.driver_frame = sys._getframe()
    context.dispatch_ticket = (index, context.driver_frame)
    return stage._step(context, index)


def _checker_controller():
    """Helper references only; this cannot produce an issued source owner."""
    counts = []

    def function(tag):
        def delegate(*args, **kwargs):
            counts.append(tag + " delegate")

        def wrapper(*args, __delegate=delegate, **kwargs):
            counts.append(tag)
            return __delegate(*args, **kwargs)

        wrapper.__wrapped__ = delegate
        wrapper._implementation = delegate
        return wrapper

    helpers = NS(
        _atoms=function("atoms"),
        literal=NS(
            _surface=function("surface"),
            _same=function("same"),
        ),
    )
    context = NS(api=NS(helpers=helpers), invalid=False, bindings=())
    context.helper_authority = stage._helper_authority(context.api)
    return context, counts


@pytest.mark.parametrize("boundary", ["active", "closed"])
@pytest.mark.parametrize("name", ["atoms", "surface", "same"])
@pytest.mark.parametrize(
    "mutation", ["replace", "code", "wrapped_code", "implementation", "keyword"]
)
def test_helper_mutation_refuses_before_any_changed_helper_or_delegate(
    monkeypatch, boundary, name, mutation
):
    context, counts = _checker_controller()
    container, attribute = (
        (context.api.helpers, "_atoms")
        if name == "atoms"
        else (context.api.helpers.literal, "_" + name)
    )
    original = getattr(container, attribute)
    delegate = original.__wrapped__
    code, delegated_code = original.__code__, delegate.__code__

    def foreign(*args, **kwargs):
        counts.append("altered helper ran")

    monkeypatch.setattr(stage, "_guard", lambda actual: None)
    monkeypatch.setattr(stage, "_same_dependencies", lambda actual: None)
    try:
        if mutation == "replace":
            setattr(container, attribute, foreign)
        elif mutation == "code":
            original.__code__ = code.replace(co_name="accepting_changed_checker")
        elif mutation == "wrapped_code":
            delegate.__code__ = delegated_code.replace(co_name="changed_wrapped_checker")
        elif mutation == "implementation":
            original._implementation = foreign
        else:
            original.__kwdefaults__["__delegate"] = foreign
            assert original.__wrapped__ is delegate and original.__code__ is code
        with pytest.raises(ValueError, match="helper"):
            if boundary == "active":
                stage._check_bindings(context)
            else:
                with stage._validation_scope(object(), context):
                    stage._compare_bindings(context)
        assert counts == []
        assert stage._VALIDATION.current is None
    finally:
        original.__code__, delegate.__code__ = code, delegated_code


def test_unchanged_helper_bootstrap_does_not_invoke_any_comparator_or_atom_helper():
    context, counts = _checker_controller()
    stage._check_helpers(context)
    assert counts == []


def test_original_global_atom_delegate_is_authenticated_without_calling_it(monkeypatch):
    context, counts = _checker_controller()
    namespace = dict(aliases=NS(_atoms=lambda value: counts.append("old atoms")))
    exec("def helper(*args):\n    return aliases._atoms(args)\n", namespace)
    context.api.helpers._atoms = namespace["helper"]
    context.helper_authority = stage._helper_authority(context.api)

    def altered(value):
        counts.append("changed atoms")

    monkeypatch.setattr(namespace["aliases"], "_atoms", altered)
    with pytest.raises(ValueError, match="helper"):
        stage._compare_bindings(context)
    assert counts == []


@pytest.mark.parametrize("boundary", ["pre_key", "post_key"])
@pytest.mark.parametrize("entry", ["owner_read", "prepare", "declare"])
def test_validation_reservation_is_sticky_before_and_after_parameter_checker(
    monkeypatch, boundary, entry
):
    # A private reservation on metadata tokens, never a fabricated source owner.
    context = NS(invalid=False)
    owner, log = object(), []

    def recursive():
        with pytest.raises(stage.WorldPhaseRejected):
            if entry == "owner_read":
                with stage._validation_scope(owner, context):
                    log.append("forbidden recursive body")
            elif entry == "prepare":
                stage.prepare(None, enabled=False)
            else:
                stage.from_world_ready(None, None, law_id=stage.LAW_ID, mode=stage.MODE)

    def compare(actual):
        if boundary == "pre_key":
            recursive()

    def key_check(*args, **kwargs):
        log.append("Key metadata checker")
        if boundary == "post_key":
            recursive()
        return object()  # Refusal must precede any interpretation of this token.

    context.api = NS(key=NS(validate_closed_seed=key_check))
    context.request, context.claim = NS(world_parameters=object()), object()
    monkeypatch.setattr(stage, "_closed_lineage", lambda actual: None)
    monkeypatch.setattr(stage, "_same_dependencies", lambda actual: None)
    monkeypatch.setattr(stage, "_compare_bindings", compare)
    monkeypatch.setattr(stage, "_check_evidence", lambda *args, **kwargs: log.append("late stage"))
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        with stage._validation_scope(owner, context) as reservation:
            stage._validate_reserved(context, reservation)
    assert caught.value is reservation.rejection
    assert context.invalid and reservation.attempts
    assert log == ([] if boundary == "pre_key" else ["Key metadata checker"])
    assert stage._VALIDATION.current is None and reservation.active is False
    assert context.validation_failures[-1] is reservation


@pytest.mark.parametrize("has_primary", [False, True])
def test_validation_release_rejection_retains_primary_and_retires_exact_scope(
    monkeypatch, has_primary
):
    context, owner = NS(invalid=False), object()
    primary, cause, capture = (
        FalseFailure("original checker"),
        KeyError("cause"),
        OSError("release"),
    )

    def reject(reservation):
        raise capture

    monkeypatch.setattr(stage, "_release_validation", reject)
    expected = FalseFailure if has_primary else stage.WorldPhaseRejected
    with pytest.raises(expected) as caught:
        with stage._validation_scope(owner, context) as reservation:
            if has_primary:
                raise primary from cause
    if has_primary:
        assert caught.value is primary and primary.__cause__ is cause
    else:
        assert caught.value.capture_error is capture
    assert reservation.cleanup_errors == (capture,)
    assert context.validation_failures[-1] is reservation
    assert stage._VALIDATION.current is None and reservation.active is False


def test_reserved_source_failure_cleans_scope_without_reopening_any_claim():
    context, owner = NS(invalid=False), object()
    primary, cause = FalseFailure("post-Key failure"), LookupError("cause")
    with pytest.raises(FalseFailure) as caught:
        with stage._validation_scope(owner, context) as reservation:
            raise primary from cause
    assert caught.value is primary and primary.__cause__ is cause
    assert reservation.primary is primary and not reservation.cleanup_errors
    assert stage._VALIDATION.current is None


def test_actual_validation_reports_callback_is_allowed_by_exact_native_guard(tmp_path):
    directory = tmp_path / "allowed_callback"
    directory.mkdir()
    request = NS(node=NS(nodeid="metadata::actual_reports_callback"))
    state = software.reuse._run_state()
    plugin = software.Reports(directory, state, "", [])
    call = NS(excinfo=None, when="call")
    with _blockade(request, directory):
        plugin.pytest_runtest_makereport(None, call)
        plugin.pytest_runtest_logreport(
            NS(
                skipped=False,
                nodeid="metadata::report",
                when="call",
                outcome="passed",
                duration=0.0,
                longrepr="",
            )
        )
    assert not state.evidence_errors and state.primary is None
    assert len(list((directory / "reports").iterdir())) == 1
    receipt = directory / "native-blocked.json"
    saved = json.loads(receipt.read_text())
    assert saved["nodeid"] == "metadata::actual_reports_callback"
    assert saved["attempted"] == []
    receipt.rename(directory / "callback-control-guard.json")


@pytest.mark.parametrize("policy", ["native_path", "forbidden_module", "misleading_path"])
def test_exact_guard_distinguishes_native_root_from_metadata_labels(tmp_path, policy):
    directory = tmp_path / policy
    directory.mkdir()
    request = NS(node=NS(nodeid="metadata::exact_guard::" + policy))
    filename = {
        "native_path": software.NATIVE_ROOT + "/betse/controlled_guard_probe.py",
        "forbidden_module": "/tmp/metadata_only.py",
        "misleading_path": "/tmp/project/validation/betse/metadata_only.py",
    }[policy]
    calls = []
    namespace = dict(
        calls=calls,
        __name__=(
            "betse.science.cells"
            if policy == "forbidden_module"
            else "validation.betse.metadata_probe"
        ),
    )
    module_code = compile("def probe():\n    calls.append('body')\n", filename, "exec")
    function_code = next(value for value in module_code.co_consts if type(value) is CodeType)
    probe = FunctionType(function_code, namespace)
    if policy == "misleading_path":
        with _blockade(request, directory):
            probe()
        assert calls == ["body"]
    else:
        with pytest.raises(AssertionError, match="entry forbidden"):
            with _blockade(request, directory):
                probe()
        assert calls == []
    # These nested generated-code controls are not ordinary per-case source
    # guard receipts. Validate their exact known attempt before classifying;
    # an unknown attempt stays an ordinary receipt and fails this test.
    receipt = directory / "native-blocked.json"
    saved = json.loads(receipt.read_text())
    expected_attempts = [] if policy == "misleading_path" else [[filename, "probe"]]
    assert saved["attempted"] == expected_attempts
    assert saved["nodeid"] == "metadata::exact_guard::" + policy
    assert saved["source_native_or_scientific_credit"] == 0
    receipt = receipt.rename(
        directory
        / (
            "policy-control-guard.json"
            if policy == "misleading_path"
            else "synthetic-policy-attempt.json"
        )
    )
    (directory / "policy-classification.json").write_text(
        json.dumps(
            dict(
                generated_metadata_code=True,
                policy=policy,
                original_native_body_loaded_or_executed=False,
                delegate_calls=calls,
                guard_attempt_receipt=receipt.name,
                expected_attempts=0 if policy == "misleading_path" else 1,
            )
        )
    )


@pytest.mark.parametrize("primary_kind", ["none", "normal", "falsey"])
@pytest.mark.parametrize("failure", ["trace", "profile", "receipt", "all"])
def test_fixture_cleanup_receipt_failures_preserve_primary_and_attempt_both_hooks(
    monkeypatch, tmp_path, primary_kind, failure
):
    directory = tmp_path / "cleanup"
    directory.mkdir()
    request = NS(node=NS(nodeid="metadata::fixture_cleanup"))
    getters, setters = (sys.getprofile, sys.gettrace), (sys.setprofile, sys.settrace)
    before = (getters[0](), getters[1]())
    primary = (
        None
        if primary_kind == "none"
        else (
            FalseFailure("falsey original") if primary_kind == "falsey" else ValueError("original")
        )
    )
    cause, capture = KeyError("original cause"), OSError("cleanup observer")
    attempted, once = [], set()
    original_writer = software.snapshot.write_json

    def setter(index, value):
        if value is before[index]:
            attempted.append(index)
            name = ("profile", "trace")[index]
            if failure in (name, "all") and index not in once:
                once.add(index)
                raise capture
        setters[index](value)

    def writer(path, value):
        if failure in ("receipt", "all") and path.parent == directory:
            raise capture
        original_writer(path, value)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "setprofile", lambda value: setter(0, value))
            patch.setattr(sys, "settrace", lambda value: setter(1, value))
            patch.setattr(software.snapshot, "write_json", writer)
            expected = AssertionError if primary is None else type(primary)
            with pytest.raises(expected) as caught:
                with _blockade(request, directory) as state:
                    if primary is not None:
                        raise primary from cause
        if primary is not None:
            assert caught.value is primary and primary.__cause__ is cause
            assert primary.world_phase_blockade is state
        assert 0 in attempted and 1 in attempted
        assert state.hooks_restored is True
        assert state.cleanup_errors or state.evidence_errors
        assert getters[0]() is before[0] and getters[1]() is before[1]
        receipt = directory / "native-blocked.json"
        if failure not in ("receipt", "all"):
            saved = json.loads(receipt.read_text())
            assert saved["nodeid"] == "metadata::fixture_cleanup"
            assert saved["attempted"] == []
            receipt.rename(directory / "cleanup-control-guard.json")
        else:
            assert not receipt.exists()
        (directory / "cleanup-classification.json").write_text(
            json.dumps(
                dict(
                    metadata_cleanup_control=True,
                    primary_kind=primary_kind,
                    injected_failure=failure,
                    original_primary_preserved=(primary is None or caught.value is primary),
                    final_hooks_restored=state.hooks_restored,
                    cleanup_or_capture_errors_retained=True,
                    native_source_credit=0,
                )
            )
        )
    finally:
        setters[1](before[1])
        setters[0](before[0])


@pytest.mark.parametrize("boundary", ["active", "closed"])
@pytest.mark.parametrize("shadow", ["len", "any", "zip", "ValueError"])
def test_residual_resolved_comparator_shadow_refuses_equal_length_drift(
    monkeypatch, boundary, shadow
):
    context, calls = _checker_controller()
    namespace = {"__name__": "metadata_comparator"}
    exec(
        "def compare(actual, retained):\n"
        "    if len(actual) != len(retained) or any(\n"
        "        a is not b for a,b in zip(actual,retained,strict=True)):\n"
        "        raise ValueError('binding drift')\n",
        namespace,
    )
    comparator = namespace["compare"]
    context.api.helpers.literal._same = comparator
    context.helper_authority = stage._helper_authority(context.api)
    old_code, old_namespace = comparator.__code__, comparator.__globals__
    context.bindings = (object(), object())
    changed = (context.bindings[0], object())

    def accepting(*args, **kwargs):
        calls.append("changed resolved comparator dependency")
        return False

    namespace[shadow] = accepting
    monkeypatch.setattr(stage, "_bindings", lambda actual: changed)
    monkeypatch.setattr(stage, "_guard", lambda actual: None)
    monkeypatch.setattr(stage, "_same_dependencies", lambda actual: None)
    assert comparator.__code__ is old_code and comparator.__globals__ is old_namespace
    assert len(changed) == len(context.bindings)
    with pytest.raises(ValueError, match="helper"):
        if boundary == "active":
            stage._check_bindings(context)
        else:
            with stage._validation_scope(object(), context):
                stage._compare_bindings(context)
    assert calls == [] and stage._VALIDATION.current is None


def test_residual_independent_binding_comparison_precedes_accepting_checker(monkeypatch):
    calls = []

    def accepting(*args):
        calls.append("accepting comparator")

    retained = (object(), object())
    context = NS(bindings=retained, api=NS(helpers=NS(literal=NS(_same=accepting))))
    monkeypatch.setattr(stage, "_check_helpers", lambda actual: None)
    monkeypatch.setattr(stage, "_bindings", lambda actual: (retained[0], object()))
    with pytest.raises(ValueError, match="Independent coordinator"):
        stage._compare_bindings(context)
    assert calls == []


@pytest.mark.parametrize("entry", ["prepare", "owner_read"])
@pytest.mark.parametrize("has_primary", [False, True])
def test_residual_release_entry_reentry_cannot_return_poisoned_authority(entry, has_primary):
    context, owner, later = NS(invalid=False), object(), []
    primary, cause = FalseFailure("original validation"), KeyError("cause")
    prior, trace = sys.getprofile(), sys.gettrace()
    release_code = stage._release_validation.__code__
    attempted = []

    def observer(frame, event, arg):
        if event == "call" and frame.f_code is release_code and not attempted:
            attempted.append("release entry")
            with pytest.raises(stage.WorldPhaseRejected):
                if entry == "prepare":
                    stage.prepare(None, enabled=False)
                else:
                    with stage._validation_scope(owner, context):
                        later.append("recursive body must not run")
        if prior is not None:
            prior(frame, event, arg)

    try:
        sys.setprofile(observer)
        expected = FalseFailure if has_primary else stage.WorldPhaseRejected
        with pytest.raises(expected) as caught:
            with stage._validation_scope(owner, context) as reservation:
                if has_primary:
                    raise primary from cause
            later.append("poisoned read returned")
        if has_primary:
            assert caught.value is primary and primary.__cause__ is cause
        else:
            assert caught.value is reservation.rejection
        assert context.invalid and reservation.attempts and attempted == ["release entry"]
        assert later == [] and stage._VALIDATION.current is None and not reservation.active
        assert context.validation_failures[-1] is reservation
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)


def test_residual_reservation_return_observer_failure_retires_its_published_token():
    context, owner, yielded = NS(invalid=False), object(), []
    original, cause = FalseFailure("reservation return observer"), KeyError("original cause")
    prior, trace = sys.getprofile(), sys.gettrace()
    reserve_code = stage._reserve_validation.__code__
    attempts = []

    def observer(frame, event, arg):
        if event == "return" and frame.f_code is reserve_code and not attempts:
            assert stage._VALIDATION.current is arg
            attempts.append(arg)
            raise original from cause
        if prior is not None:
            prior(frame, event, arg)

    try:
        sys.setprofile(observer)
        with pytest.raises(FalseFailure) as caught:
            with stage._validation_scope(owner, context):
                yielded.append("must never yield")
        assert caught.value is original and original.__cause__ is cause
        reservation = attempts[0]
        assert context.last_validation is reservation and reservation.primary is original
        assert not reservation.active and stage._VALIDATION.current is None and not yielded
        assert context.validation_failures[-1] is reservation
    finally:
        sys.settrace(trace)
        sys.setprofile(prior)


def test_residual_failed_reservation_does_not_retire_another_acquisition(monkeypatch):
    context, owner, foreign = NS(invalid=False), object(), NS(acquisition=object())
    original = FalseFailure("failed before own token returned")

    def reserve(actual_owner, actual_context, *, acquisition):
        stage._VALIDATION.current = foreign
        raise original

    monkeypatch.setattr(stage, "_reserve_validation", reserve)
    try:
        with pytest.raises(FalseFailure) as caught:
            with stage._validation_scope(owner, context):
                raise AssertionError("no body after failed acquisition")
        assert caught.value is original and stage._VALIDATION.current is foreign
    finally:
        stage._VALIDATION.current = None


def _world_integration_tree(module):
    path = software.ROOT / ("src/" + module.replace(".", "/") + ".py")
    return ast.parse(path.read_bytes())


def test_world_integration_declares_explicit_fresh_mode_without_provider_adoption():
    plan = stage.source_plan()
    assert plan["mode"] == "fresh_world_ready_prephase_single_claim_seed_constructor"
    assert plan["private_same_claim_stage_hooks_implemented"] is True
    assert plan["exact_same_instance_seed_and_world_dispatch_prepared"] is True
    assert plan["public_closed_records_between_stages"] is False
    assert plan["helper_source"] is None
    assert plan["key_source"] is None and plan["parameter_source"] is None
    assert plan["stage_sources"] == plan["stage_reviews"] == (None,) * 4
    assert plan["source_native_scientific_release"] is False


@pytest.mark.parametrize("index", range(4))
def test_world_integration_source_hooks_keep_one_actual_claim_and_exact_surface(index):
    tree = _world_integration_tree(stage.STAGE_MODULES[index])
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    construct = functions[stage.CONSTRUCT_HOOK]
    check = functions[stage.CHECK_HOOK]
    assert [v.arg for v in construct.args.args] == ["transition"]
    assert [v.arg for v in construct.args.kwonlyargs] == [
        "world_owner",
        "construction_claim",
        "callback_owner",
        "predecessor",
    ]
    assert [v.arg for v in check.args.kwonlyargs] == [
        "transition",
        "world_owner",
        "construction_claim",
        "predecessor",
        "closed_record",
    ]
    starts = [
        node
        for node in ast.walk(construct)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_world_stage_begin"
    ]
    assert len(starts) == 1 and ast.literal_eval(starts[0].args[1]) == index
    # Only the coordinator may enter construction. There is no new legacy
    # Lease/d9/47 claim and no closure/record synthesized between stages.
    forbidden = {"construction", "continuation", "seed_tail", "inspection", "_claim"}
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in forbidden)
            or (isinstance(node.func, ast.Attribute) and node.func.attr in forbidden)
        )
        for node in ast.walk(construct)
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_world_stage_finish"
        for node in ast.walk(construct)
    )
    if index < 2:
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_world_body_scope"
            for node in ast.walk(construct)
        )
        assert any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute) and target.attr == "driver_frame"
                for target in node.targets
            )
            for node in ast.walk(construct)
        )


def test_world_integration_execution_closure_explicitly_selects_all_eight_paths():
    expected = {
        "src/cells/processes/betse_native_phase_assembly.py",
        "src/cells/processes/betse_native_phase_caches.py",
        "src/cells/processes/betse_native_phase_dyna.py",
        "src/cells/processes/betse_native_phase_tail.py",
        "src/cells/processes/betse_native_seed_world_prefix.py",
        software.SOURCE,
        software.TEST,
        software.FILE,
    }
    assert len(software.OWNED) == 8 and set(software.OWNED) == expected
    assert "cells.processes.betse_native_seed_world_prefix_source" in software.FORBIDDEN_MODULES


@pytest.mark.parametrize("entry", ["request", "prepare", "private_stage"])
def test_world_integration_unbound_gate_precedes_any_claim_or_foreign_object_inspection(
    monkeypatch, entry
):
    class Unavailable:
        def __getattribute__(self, name):
            raise AssertionError("An unadopted predecessor must not be inspected")

    unavailable = Unavailable()
    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        if entry == "request":
            stage.from_world_ready(unavailable, unavailable, law_id=stage.LAW_ID, mode=stage.MODE)
        elif entry == "prepare":
            stage.prepare(unavailable, enabled=True)
        else:
            stage._world_stage_begin(
                None, 0, unavailable, unavailable, unavailable, unavailable, unavailable, None
            )
    assert caught.value.stage == "unbound_contract"
    assert not stage._ACTIVE and not stage._ISSUED


@pytest.mark.parametrize("captured", [False, True])
def test_world_integration_failed_stage_retains_entry_primary_and_capture_separately(captured):
    # Private failure-flow metadata only: no owner, p, source class or claim
    # is fabricated, issued or accepted by these controls.
    original, cause = FalseFailure("original entry rejection"), KeyError("original cause")
    try:
        raise original from cause
    except FalseFailure:
        pass
    capture = OSError("observation") if captured else None
    transition = NS(invalid=False, entry_error=None)
    module = NS(_ACTIVE=[])
    context = NS(
        world_transition=transition,
        world_module=module,
        entry_error=original,
        observation_error=capture,
        primary=None,
        invalid=False,
        active=True,
        stage="metadata_only_failed_stage",
    )
    module._ACTIVE.append(context)
    with pytest.raises(stage.WorldPhaseRejected) as caught:
        stage._world_stage_finish(context, primary=None)
    assert caught.value.source_error is original and original.__cause__ is cause
    assert caught.value.capture_error is capture and caught.value.partial is context
    assert transition.entry_error is original and context.primary is original
    assert not context.active and context.invalid and not module._ACTIVE
    assert not stage._ISSUED


def test_world_integration_prepares_only_exact_same_instance_phase_world_dispatch():
    assembly = _world_integration_tree(stage.STAGE_MODULES[0])
    tail = _world_integration_tree(stage.STAGE_MODULES[-1])
    helpers = _world_integration_tree(stage.HELPER_MODULE)
    tail_functions = {node.name for node in tail.body if isinstance(node, ast.FunctionDef)}
    assert {
        "_claim_for_seed_world",
        "_check_world_authority",
        "_dispatch_seed_world",
    } <= tail_functions
    assert {stage.SEAL_HOOK, stage.CHECK_SEAL_HOOK} <= tail_functions
    parent = next(
        node
        for node in helpers.body
        if isinstance(node, ast.FunctionDef) and node.name == "_world_parent"
    )
    assert "WorldPhaseOwner" in ast.unparse(parent)
    assert "PhaseTailOwner" not in ast.unparse(parent)
    # No phase class or per-instance method replacement is an integration tool.
    for tree in (assembly, tail, helpers):
        assert not any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Attribute) and target.attr == "__class__"
                for target in node.targets
            )
            for node in ast.walk(tree)
        )


def _field_epoch_metadata():
    """Private code seams only: no Request, claim, issued parent or native body.

    The real seal/check code runs against field witnesses with authentication
    and capture replaced by explicit metadata seams. This proves the field
    transition, not that any genuine producer or phase has been admitted.
    """
    callback, cells, kind, cache, handler, export = (object() for _ in range(6))
    p, sim = NS(init_export_dirname=export, _run_sim=False), NS(dyna=handler)
    phase = NS(
        callbacks=callback,
        cells=cells,
        kind=kind,
        p=p,
        sim=sim,
        cache=cache,
        dyna=handler,
        export_dirname=export,
    )
    authority = NS()
    evidence = [
        stage.StageEvidence(
            name,
            authority,
            phase,
            p,
            cells,
            sim,
            callback,
            kind,
            None if index == 0 else cache,
            None if index < 2 else handler,
            "metadata trial " + name,
            (),
            str(index),
        )
        for index, name in enumerate(stage.STAGES)
    ]
    checks = []
    context = NS(
        request=NS(world_parameters=object(), identity="metadata request"),
        claim=object(),
        p=p,
        parents=(None, p, None, callback),
        evidence=evidence,
        executing=None,
        parameter_record=None,
        work=[],
        stage="before metadata seal",
        metadata_authenticated=True,
    )

    def authenticate(actual):
        assert actual is context and actual.parameter_record is None
        if not actual.metadata_authenticated:
            raise ValueError("Metadata authentication seam refused")
        checks.append("active metadata seam; no closed record")

    def issued_witness(actual, **kwargs):
        assert kwargs["closed_record"] is None
        assert kwargs["transition"] is context
        checks.append(actual.stage)
        return actual

    namespace = dict(vars(stage))
    namespace.update(
        __name__=__name__,
        _ready=lambda: None,
        _active_claim=authenticate,
        _guard=authenticate,
        _world_parameter_authority=authenticate,
        _world_state=lambda actual: (NS(identity="metadata cache"), ((), ())),
        _bindings=lambda actual: (),
    )
    for name in ("_seal_active", "_world_seal", "_check_evidence"):
        original = getattr(stage, name)
        fn = FunctionType(original.__code__, namespace, name, original.__defaults__)
        fn.__kwdefaults__ = dict(original.__kwdefaults__ or {})
        namespace[name] = fn

    def seal_hook(actual, *, transition, world_owner, construction_claim, stages):
        return namespace["_world_seal"](actual, transition, world_owner, construction_claim, stages)

    context.api = NS(stages=tuple(NS(_world_phase_check=issued_witness) for _ in stage.STAGES))
    context.api.stages[-1]._world_phase_seal = seal_hook
    context.api.stages[-1]._world_phase_check_seal = lambda actual, **kwargs: actual
    return context, namespace, checks


def test_interface_final_in_claim_seal_accepts_historical_witnesses_without_closed_record():
    context, code, checks = _field_epoch_metadata()
    before = tuple(stage._ISSUED.items())
    code["_seal_active"](context)
    assert type(context.seal) is stage.PhaseSeal and type(context.trial) is stage.Trial
    assert context.seal.stages == tuple(context.evidence)
    assert context.parameter_record is None and context.p._run_sim is False
    assert [name for name in checks if name in stage.STAGES] == list(stage.STAGES)
    assert tuple(stage._ISSUED.items()) == before


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("premature", ["later_fields", "seed_flag"])
def test_interface_immediate_epoch_still_refuses_premature_fields_and_seed_flag(index, premature):
    context, code, _ = _field_epoch_metadata()
    if premature == "seed_flag":
        allowed = stage._evidence_fields(index)
        for name in tuple(vars(context.evidence[index].phase)):
            if name not in allowed:
                delattr(context.evidence[index].phase, name)
    with pytest.raises(ValueError, match="field order|before its literal tail"):
        code["_check_evidence"](context, context.evidence[index], index)


@pytest.mark.parametrize("index", range(4))
def test_interface_unchanged_immediate_epoch_keeps_original_stage_semantics(index):
    context, code, _ = _field_epoch_metadata()
    for name in tuple(vars(context.evidence[index].phase)):
        if name not in stage._evidence_fields(index):
            delattr(context.evidence[index].phase, name)
    if index < 3:
        del context.p._run_sim
    assert (
        code["_check_evidence"](context, context.evidence[index], index) is context.evidence[index]
    )


@pytest.mark.parametrize("change", ["extra", "flag", "cache", "handler", "callback", "auth"])
def test_interface_final_in_claim_epoch_keeps_exact_fields_aliases_and_flag(change):
    context, code, _ = _field_epoch_metadata()
    if change == "extra":
        context.evidence[0].phase.extra = None
    elif change == "flag":
        context.p._run_sim = True
    elif change == "cache":
        context.evidence[0].phase.cache = object()
    elif change == "handler":
        context.evidence[0].sim.dyna = object()
    elif change == "callback":
        context.evidence[0].phase.callbacks = object()
    else:
        context.metadata_authenticated = False
    with pytest.raises(ValueError):
        code["_seal_active"](context)
    assert not hasattr(context, "seal") and context.parameter_record is None


def test_interface_completed_active_flag_cannot_authorize_an_outside_check():
    context, code, checks = _field_epoch_metadata()
    context.stage = "phase_sealing_inside_claim"
    with pytest.raises(ValueError, match="reserved for the actual full-phase seal"):
        code["_check_evidence"](context, context.evidence[0], 0, final_active=True)
    assert not checks and context.parameter_record is None


def _helper_image(source=None, review=None, *, extra=b""):
    return (
        ("CONSTRUCTION_SOURCE_SHA256 = " + repr(source) + "\n").encode()
        + ("CONSTRUCTION_REVIEW_SHA256 = " + repr(review) + "\n").encode()
        + b"OTHER = 3\ndef helper():\n    return OTHER\n"
        + extra
    )


def _module_record_fixture(tmp_path, monkeypatch):
    from cells.processes import betse_native_single_cell_grid_alias as aliases

    root = tmp_path / "native"
    root.mkdir()
    source = root / "module.py"
    source.write_bytes(b"VALUE = 1\n")
    module = ModuleType("betse.metadata_only")
    module.__file__ = str(source)
    modules = {module.__name__: module, "betse_unrelated": NS(__file__=None)}
    monkeypatch.setattr(aliases, "NATIVE", root)
    monkeypatch.setattr(aliases, "sys", NS(modules=modules))
    monkeypatch.setattr(aliases, "_MODULE_AUTH", {})
    return aliases, root, source, module, modules


@pytest.mark.parametrize(
    "form", ["ordinary", "pathlike", "relative_file", "dot_segments", "internal_symlink"]
)
def test_module_records_canonical_origins_retain_exact_paths_bytes_and_modules(
    tmp_path, monkeypatch, form
):
    aliases, root, source, module, _ = _module_record_fixture(tmp_path, monkeypatch)
    if form == "pathlike":
        module.__file__ = source
    elif form == "relative_file":
        monkeypatch.chdir(tmp_path)
        module.__file__ = "native/module.py"
    elif form == "dot_segments":
        (root / "sub").mkdir()
        module.__file__ = str(root / "sub/../module.py")
    elif form == "internal_symlink":
        link = root / "inside.py"
        link.symlink_to(source)
        module.__file__ = str(link)
    rows = aliases._module_records()
    assert rows == {
        module.__name__: (module, source, hashlib.sha256(source.read_bytes()).hexdigest())
    }
    assert rows[module.__name__][0] is module
    assert rows[module.__name__][1].is_relative_to(root)


@pytest.mark.parametrize(
    "form",
    [
        "sibling",
        "outside_symlink",
        "relative_root",
        "double_root",
        "no_origin",
        "missing_file",
        "bytes_origin",
    ],
)
def test_module_records_unavailable_or_noncontained_origins_still_refuse(
    tmp_path, monkeypatch, form
):
    aliases, root, source, module, _ = _module_record_fixture(tmp_path, monkeypatch)
    if form in {"sibling", "outside_symlink"}:
        outside = tmp_path / "native_sibling.py"
        outside.write_bytes(source.read_bytes())
        if form == "sibling":
            module.__file__ = str(outside)
        else:
            source.unlink()
            source.symlink_to(outside)
    elif form == "relative_root":
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(aliases, "NATIVE", Path("native"))
    elif form == "double_root":
        monkeypatch.setattr(aliases, "NATIVE", Path("/" + str(root)))
    elif form == "no_origin":
        module.__file__ = None
    elif form == "missing_file":
        source.unlink()
    else:
        module.__file__ = bytes(source)
    with pytest.raises((ValueError, TypeError, FileNotFoundError)):
        aliases._module_records()


def test_module_records_root_and_fresh_file_roster_checks_are_not_cached(tmp_path, monkeypatch):
    aliases, _, source, module, modules = _module_record_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(aliases, "NATIVE", Path("/"))
    first = aliases._module_records()
    source.write_bytes(b"VALUE = 2\n")
    second = aliases._module_records()
    assert first[module.__name__][:2] == second[module.__name__][:2]
    assert first[module.__name__][2] != second[module.__name__][2]
    replacement = ModuleType(module.__name__)
    replacement.__file__ = str(source)
    modules[module.__name__] = replacement
    assert aliases._module_records()[module.__name__][0] is replacement
    modules.clear()
    assert aliases._module_records() == {}


@pytest.mark.parametrize("change", ["module", "code", "file"])
def test_module_records_issuance_guards_remain_live_on_every_scan(tmp_path, monkeypatch, change):
    aliases, _, source, module, modules = _module_record_fixture(tmp_path, monkeypatch)
    code = compile("def helper():\n    return 1\n", str(source), "exec")
    module.helper = FunctionType(
        next(c for c in code.co_consts if type(c) is CodeType), vars(module)
    )
    records = aliases._module_records()
    aliases._MODULE_AUTH[module.__name__] = (
        records[module.__name__],
        aliases._module_bindings(module),
    )
    aliases._check_modules()
    if change == "module":
        replacement = ModuleType(module.__name__)
        replacement.__file__, replacement.helper = module.__file__, module.helper
        modules[module.__name__] = replacement
    elif change == "code":
        module.helper.__code__ = module.helper.__code__.replace()
    else:
        source.write_bytes(b"VALUE = 2\n")
    with pytest.raises(ValueError):
        aliases._check_modules()


def test_module_records_each_scan_resolves_and_reads_without_ancestor_enumeration(
    tmp_path, monkeypatch
):
    aliases, root, source, module, _ = _module_record_fixture(tmp_path, monkeypatch)
    calls = []

    class ObservedPath(type(root)):
        def resolve(self, *args, **kwargs):
            calls.append("resolve")
            return super().resolve(*args, **kwargs)

        def read_bytes(self):
            calls.append("read")
            return super().read_bytes()

        def is_relative_to(self, *args):
            raise AssertionError("Parent traversal must not be used by the scan")

    monkeypatch.setattr(aliases, "Path", ObservedPath)
    for _ in range(3):
        assert (
            aliases._module_records()[module.__name__][2]
            == hashlib.sha256(source.read_bytes()).hexdigest()
        )
    assert calls == ["resolve", "read"] * 3


def _tissue_check_metadata(tmp_path, monkeypatch, count=4):
    """Run the exact checker with isolated metadata; this issues no live owner."""
    from threading import get_ident

    aliases, root, source, module, modules = _module_record_fixture(tmp_path, monkeypatch)
    modules.pop("betse_unrelated")
    for index in range(1, count):
        path = root / ("module_" + str(index) + ".py")
        path.write_bytes(b"VALUE = 1\n")
        extra = ModuleType("betse.metadata_" + str(index))
        extra.__file__ = str(path)
        modules[extra.__name__] = extra
    records = aliases._module_records()
    aliases._MODULE_AUTH.update(
        (name, (record, aliases._module_bindings(record[0]))) for name, record in records.items()
    )
    request = type("MetadataRequest", (), {"identity": "metadata"})()
    context = NS(
        request=request,
        thread=get_ident(),
        configuration={},
        configuration_cache=NS(identity="cache"),
        configuration_graph=((), ()),
        producers=(),
        bindings=(),
        runtime_types={},
        objects=(),
        modules=records,
    )
    path = stage._module_file("cells.processes.betse_native_tissue_configuration")
    node = next(
        n
        for n in ast.parse(path.read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_check"
    )
    scope = dict(
        __name__="tissue_metadata_only",
        _CONSUMED={request: context},
        _REQUESTS={request: request.identity},
        request_record=lambda actual: {},
        core=NS(
            records=NS(_digest=lambda _: "metadata"),
            caches=NS(snapshot=lambda _: NS(identity="cache")),
        ),
        get_ident=get_ident,
        _verify_sources=lambda: (),
        _configuration_graph=lambda actual: ((), ()),
        _same=lambda actual, retained: None,
        _bindings=lambda: (),
        aliases=aliases,
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope["_check"], context, aliases, modules, source


@pytest.mark.parametrize("count", [1, 4, 32])
def test_tissue_inventory_three_fresh_scans_per_check_independent_of_roster_size(
    tmp_path, monkeypatch, count
):
    check, context, aliases, _, _ = _tissue_check_metadata(tmp_path, monkeypatch, count)
    scans, reads = [], []
    original, original_read = aliases._module_records, Path.read_bytes

    def scan():
        result = original()
        scans.append(result)
        return result

    def read(path):
        reads.append(path)
        return original_read(path)

    monkeypatch.setattr(aliases, "_module_records", scan)
    monkeypatch.setattr(Path, "read_bytes", read)
    for _ in range(2):
        check(context)
    assert len(scans) == 6 and len(reads) == 6 * count
    assert len({id(value) for value in scans}) == 6


@pytest.mark.parametrize("change", ["remove", "replace", "file", "symlink", "last_retained_row"])
def test_tissue_inventory_detects_each_retained_row_and_mid_check_drift(
    tmp_path, monkeypatch, change
):
    check, context, aliases, modules, _ = _tissue_check_metadata(tmp_path, monkeypatch)
    last = next(reversed(context.modules))
    original, count = aliases._module_records, []
    if change == "last_retained_row":
        module, path, _ = context.modules[last]
        context.modules[last] = (module, path, "0" * 64)

    def scan():
        result = original()
        count.append(None)
        if len(count) == 2:
            if change == "remove":
                del modules[last]
            elif change == "replace":
                old = modules[last]
                modules[last] = ModuleType(last)
                modules[last].__file__ = old.__file__
            elif change == "file":
                Path(modules[last].__file__).write_bytes(b"VALUE = 2\n")
            elif change == "symlink":
                target = aliases.NATIVE / "new_target.py"
                target.write_bytes(b"VALUE = 1\n")
                path = Path(modules[last].__file__)
                path.unlink()
                path.symlink_to(target)
        return result

    monkeypatch.setattr(aliases, "_module_records", scan)
    with pytest.raises(ValueError, match="Native factory import changed"):
        check(context)
    assert len(count) == (2 if change == "last_retained_row" else 3)


def test_tissue_inventory_installed_observer_mutation_during_comparison_refuses(
    tmp_path, monkeypatch
):
    check, context, _, modules, _ = _tissue_check_metadata(tmp_path, monkeypatch)
    target = Path(modules[next(reversed(modules))].__file__)
    prior, changed = sys.getprofile(), []

    def observer(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if (
            frame.f_code is check.__code__
            and event == "c_return"
            and getattr(arg, "__name__", None) == "get"
            and "current" in frame.f_locals
            and getattr(arg, "__self__", None) is frame.f_locals["current"]
            and not changed
        ):
            target.write_bytes(b"VALUE = 2\n")
            changed.append(True)

    try:
        sys.setprofile(observer)
        with pytest.raises(ValueError, match="during validation"):
            check(context)
    finally:
        sys.setprofile(prior)
    assert changed == [True] and sys.getprofile() is prior


@pytest.mark.parametrize("scan_number", [2, 3])
@pytest.mark.parametrize("event", ["call", "return"])
def test_tissue_inventory_inherited_observer_refusal_preserves_primary(
    tmp_path, monkeypatch, scan_number, event
):
    check, context, aliases, _, _ = _tissue_check_metadata(tmp_path, monkeypatch)

    class FalseyError(RuntimeError):
        def __bool__(self):
            return False

    cause, primary = OSError("original observer cause"), FalseyError("stop metadata scan")
    primary.__cause__ = cause
    prior, visits = sys.getprofile(), []

    def observer(frame, actual, arg):
        if prior is not None:
            prior(frame, actual, arg)
        if frame.f_code is aliases._module_records.__code__:
            if actual == "call":
                visits.append(True)
            if len(visits) == scan_number and actual == event:
                raise primary

    try:
        sys.setprofile(observer)
        with pytest.raises(FalseyError) as captured:
            check(context)
        assert captured.value is primary and primary.__cause__ is cause
    finally:
        sys.setprofile(prior)
    assert len(visits) == scan_number and sys.getprofile() is prior


def test_byte_metadata_same_bytes_parse_once_without_hiding_changed_bytes(monkeypatch):
    stage._binding_metadata.cache_clear()
    parsed, original = [], stage.ast.parse

    def parse(payload, *args, **kwargs):
        parsed.append(payload)
        return original(payload, *args, **kwargs)

    monkeypatch.setattr(stage.ast, "parse", parse)
    image = _helper_image()
    expected = hashlib.sha256(stage.HELPER_BINDING_KIND.encode() + b"\0" + image).hexdigest()
    first = stage._helper_binding(image)
    for _ in range(20):
        assert stage._helper_binding(memoryview(image).tobytes()) == first
    assert first == (
        expected,
        (("CONSTRUCTION_SOURCE_SHA256", None), ("CONSTRUCTION_REVIEW_SHA256", None)),
    )
    changed = image.replace(b"OTHER = 3", b"OTHER = 4")
    assert len(changed) == len(image) and stage._helper_binding(changed)[0] != first[0]
    assert len(parsed) == 2
    assert stage._binding_metadata.cache_info().hits == 20


def test_byte_metadata_backrefs_recomputed_and_each_clone_has_its_own_key():
    stage._binding_metadata.cache_clear()
    image = _helper_image()
    first = stage._helper_binding(image)
    bound = _helper_image("a" * 64, "b" * 64)
    actual = stage._helper_binding(bound)
    assert actual[0] == first[0] and actual[1] != first[1]
    core = b"COORDINATOR_SOURCE_SHA256 = None\nCOORDINATOR_REVIEW_SHA256 = None\n"
    children = b"PARENT_SOURCE_SHA256 = None\nPARENT_REVIEW_SHA256 = None\n" + core
    for payload, names, kind, invoke in (
        (
            core,
            stage.SEED_INIT_CORE_BACK_REFERENCE_SLOTS,
            stage.SEED_INIT_CORE_BINDING_KIND,
            stage._seed_core_binding,
        ),
        (
            children,
            stage.SEED_CHILD_BACK_REFERENCE_SLOTS,
            stage.SEED_PROFILES_BINDING_KIND,
            lambda raw: stage._seed_child_binding(raw, kind=stage.SEED_PROFILES_BINDING_KIND),
        ),
        (
            children,
            stage.SEED_CHILD_BACK_REFERENCE_SLOTS,
            stage.SEED_JUNCTIONS_BINDING_KIND,
            lambda raw: stage._seed_child_binding(raw, kind=stage.SEED_JUNCTIONS_BINDING_KIND),
        ),
    ):
        expected = (
            hashlib.sha256(kind.encode() + b"\0" + payload).hexdigest(),
            tuple((name, None) for name in names),
        )
        assert invoke(payload) == expected
        assert invoke(payload) == expected
    info = stage._binding_metadata.cache_info()
    assert info.misses == 5 and info.hits == 3


@pytest.mark.parametrize("change", ["cache", "wrapped", "code", "defaults", "keywords"])
def test_byte_metadata_warm_cache_refuses_delegate_drift_before_use(monkeypatch, change):
    stage._binding_metadata.cache_clear()
    image = _helper_image()
    stage._helper_binding(image)
    calls = []

    def replacement(*args, **kwargs):
        calls.append((args, kwargs))
        return ("forged", ())

    body = stage._BINDING_METADATA_BODY
    if change == "cache":
        monkeypatch.setattr(stage, "_binding_metadata", replacement)
    elif change == "wrapped":
        monkeypatch.setattr(stage._binding_metadata, "__wrapped__", replacement)
    elif change == "code":
        monkeypatch.setattr(body, "__code__", body.__code__.replace())
    elif change == "defaults":
        monkeypatch.setattr(body, "__defaults__", (None,))
    else:
        monkeypatch.setattr(body, "__kwdefaults__", {"kind": None})
    with pytest.raises(ValueError, match="cache/delegate"):
        stage._helper_binding(image)
    assert not calls


@pytest.mark.parametrize("change", ["source", "module_origin", "module_identity", "backref"])
def test_byte_metadata_warm_cache_preserves_live_helper_checks(tmp_path, monkeypatch, change):
    # Only a metadata module: never execute its source or issue an owner.
    stage._binding_metadata.cache_clear()
    source_hash = hashlib.sha256(Path(stage.__file__).read_bytes()).hexdigest()
    raw = _helper_image(source_hash, "a" * 64)
    path = tmp_path / "helper.py"
    path.write_bytes(raw)
    module = ModuleType("metadata_helper")
    module.__file__ = str(path)
    module.CONSTRUCTION_SOURCE_SHA256 = source_hash
    module.CONSTRUCTION_REVIEW_SHA256 = "a" * 64
    monkeypatch.setattr(stage, "HELPER_MODULE", module.__name__)
    monkeypatch.setattr(stage, "HELPER_CONSTRUCTION_REVIEW_SHA256", "a" * 64)
    monkeypatch.setattr(stage, "_module_file", lambda name: path)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    original_import = stage.importlib.import_module
    monkeypatch.setattr(
        stage.importlib,
        "import_module",
        lambda name, *args, **kw: (
            module if name == module.__name__ else original_import(name, *args, **kw)
        ),
    )
    expected = stage._helper_binding(raw)[0]
    assert stage._import_helper_bound(expected) is module
    if change == "source":
        path.write_bytes(raw.replace(b"OTHER = 3", b"OTHER = 4"))
    elif change == "module_origin":
        module.__file__ = str(tmp_path / "retargeted.py")
    elif change == "module_identity":
        monkeypatch.setitem(sys.modules, module.__name__, ModuleType(module.__name__))
    else:
        module.CONSTRUCTION_REVIEW_SHA256 = "b" * 64
    with pytest.raises(ValueError):
        stage._import_helper_bound(expected)
    assert not stage._ACTIVE and not stage._CLAIMED


def test_byte_metadata_cache_is_bounded_and_rejects_mutable_or_oversize_input():
    stage._binding_metadata.cache_clear()
    first = stage._helper_binding(_helper_image())
    for index in range(20):
        stage._helper_binding(_helper_image(extra=("# image " + str(index)).encode()))
    assert stage._binding_metadata.cache_info().currsize == 16
    assert stage._helper_binding(_helper_image()) == first
    for invalid in (bytearray(_helper_image()), memoryview(_helper_image()), b" " * (2**21 + 1)):
        with pytest.raises(ValueError, match="Bounded exact"):
            stage._helper_binding(invalid)


@pytest.mark.parametrize(
    "change", ["bytes_subclass", "slots_subclass", "slot_subclass", "kind_subclass", "oversize"]
)
def test_byte_metadata_direct_miss_cannot_prime_a_later_exact_source_hit(change):
    stage._binding_metadata.cache_clear()
    invoked = []

    class MisleadingBytes(bytes):
        def decode(self, *args, **kwargs):
            invoked.append("decode")
            return super().decode(*args, **kwargs).replace("OTHER = 3", "OTHER = 4")

    class SlotTuple(tuple):
        pass

    class Word(str):
        pass

    image, names, kind = (
        _helper_image(),
        stage.HELPER_BACK_REFERENCE_SLOTS,
        stage.HELPER_BINDING_KIND,
    )
    payload, roster, label = image, names, kind
    if change == "bytes_subclass":
        payload = MisleadingBytes(image)
        assert payload == image and hash(payload) == hash(image)
    elif change == "slots_subclass":
        roster = SlotTuple(names)
    elif change == "slot_subclass":
        roster = (Word(names[0]), *names[1:])
    elif change == "kind_subclass":
        label = Word(kind)
    else:
        payload = b" " * (2**21 + 1)
    with pytest.raises(ValueError, match="Bounded exact"):
        stage._binding_metadata(payload, roster, label)
    assert not invoked and stage._binding_metadata.cache_info().currsize == 0
    result = stage._helper_binding(image)
    assert result[0] == hashlib.sha256(kind.encode() + b"\0" + image).hexdigest()


def test_interface_binding_topology_adopts_two_unequal_images_without_a_hash_fixed_point():
    unbound = _helper_image()
    interface, _ = stage._helper_binding(unbound)
    constructors = [
        (
            "HELPER_INTERFACE_SHA256 = "
            + repr(interface)
            + "\nHELPER_CONSTRUCTION_REVIEW_SHA256 = "
            + repr("a" * 64)
            + "\nREVISION = "
            + repr(value)
        ).encode()
        for value in ("first independent image", "second independent image")
    ]
    assert constructors[0] != constructors[1]
    bound_helpers = []
    for constructor in constructors:
        image = _helper_image(hashlib.sha256(constructor).hexdigest(), "a" * 64)
        actual, backrefs = stage._helper_binding(image)
        assert image != unbound and actual == interface
        stage._check_helper_backrefs(backrefs, constructor, "a" * 64)
        bound_helpers.append(image)
        with pytest.raises(ValueError, match="full constructor"):
            stage._check_helper_backrefs(
                backrefs, constructor + b"\n# exact byte drift\n", "a" * 64
            )
        with pytest.raises(ValueError, match="source/review"):
            stage._check_helper_backrefs(backrefs, constructor, "b" * 64)
    assert bound_helpers[0] != bound_helpers[1]
    assert stage.source_plan()["helper_interface"] is None
    assert stage.source_plan()["helper_constructor_review"] is None
    assert stage.source_plan()["helper_non_back_reference_bytes_exact"] is True


@pytest.mark.parametrize(
    "change",
    [
        lambda image: image.replace(b"return OTHER", b"return OTHER + 1"),
        lambda image: image.replace(b"OTHER = 3", b"OTHER = 4"),
        lambda image: image + b"# comment byte drift\n",
        lambda image: image.replace(b"    return OTHER", b"  return OTHER"),
        lambda image: image.replace(b"\n", b"\r\n"),
    ],
    ids=["body", "constant", "comment", "whitespace", "line_endings"],
)
def test_interface_helper_binding_preserves_every_non_back_reference_source_byte(change):
    original = _helper_image()
    baseline, _ = stage._helper_binding(original)
    changed = change(original)
    assert changed != original and stage._helper_binding(changed)[0] != baseline


@pytest.mark.parametrize(
    "image",
    [
        b"CONSTRUCTION_SOURCE_SHA256 = None\n",
        _helper_image() + b"CONSTRUCTION_REVIEW_SHA256 = None\n",
        _helper_image().replace(b"CONSTRUCTION_SOURCE_SHA256 = None", b"X = None"),
        _helper_image().replace(b"= None", b"= str(None)", 1),
        _helper_image().replace(b"= None", b"= 'not a pin'", 1),
        _helper_image().replace(b"= None", b"= r'" + b"a" * 64 + b"'", 1),
    ],
    ids=["missing", "duplicate", "renamed", "expression", "invalid_pin", "prefixed_literal"],
)
def test_interface_helper_binding_refuses_ambiguous_or_nonliteral_back_reference_slots(image):
    with pytest.raises(ValueError):
        stage._helper_binding(image)


@pytest.mark.parametrize("review", [None, "wrong", "A" * 64])
def test_interface_valid_constructor_bytes_do_not_substitute_for_a_review_binding(review):
    constructor = b"independent full constructor bytes"
    _, slots = stage._helper_binding(_helper_image(hashlib.sha256(constructor).hexdigest(), None))
    invalid = (slots[0], (slots[1][0], review))
    with pytest.raises(ValueError, match="source/review"):
        stage._check_helper_backrefs(invalid, constructor, "a" * 64)
