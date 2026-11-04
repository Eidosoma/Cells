"""Source/transport metadata only: all actual native bodies remain blocked."""

import ast
import dis
import io
import logging
import os
import sys
import time
from contextlib import contextmanager
from types import CodeType, FunctionType, MappingProxyType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_init_first_step as stage
from cells.processes import betse_native_single_cell_grid_alias as callable_graph
from cells.processes import betse_native_single_cell_poisson_observation as observation
from tests.unit import test_betse_native_init_retained_world as retained_guards
from validation.betse import betse_native_init_first_step_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit immutable native-blocked software release required")
    if (
        request.node.originalname == software.ISSUED_CHAIN_TEST
        and os.environ.get(software.ISSUED_CHAIN_RELEASE) != "1"
    ):
        pytest.skip("Explicit immutable single issued-chain mode required before setup")
    guard = software
    if request.node.originalname == software.ISSUED_CHAIN_TEST:
        # ``python -m`` executes the runner as __main__, while collection also
        # imports its canonical name. Only the authenticated running copy has
        # armed the frozen real-driver roster; the passive import stays shut.
        active = sys.modules.get("__main__")
        spec = None if active is None else vars(active).get("__spec__")
        if (
            getattr(spec, "name", None) != software.MODULE
            or software.snapshot.digest(active.__file__)
            != software.snapshot.digest(software.__file__)
            or not vars(active).get("_MODEL_RUN_BINDINGS")
        ):
            pytest.fail("Actual immutable issued-chain runner/driver binding required")
        guard = active
    namespace = dict(vars(retained_guards), software=guard, _RAW_GUARDS=[])
    function = FunctionType(retained_guards.blocked.__wrapped__.__code__, namespace)
    with contextmanager(function)(request, tmp_path, monkeypatch):
        yield


def test_first_step_entire_original_closure_compiles_without_executing_source():
    definitions = stage._definitions()
    assert len(definitions) == 28
    assert all(type(code) is CodeType for _, code in definitions.values())
    assert stage.PARENT_SOURCE_SHA256 is stage.PARENT_REVIEW_SHA256 is None
    assert stage.previous.FIRST_STEP_INTERFACE_SHA256 is None
    assert stage.previous.storage.FIRST_STEP_ANCESTOR_CLAIM is None


@pytest.mark.parametrize(
    "name",
    (
        "_plot_loop",
        "_run_sim_core_loop",
        "update_gj",
        "update_ecm",
        "update_intra",
        "update_all_concs",
        "ca_handler",
        "write2storage",
        "_log_solver_time_estimate",
        "electroflux",
        "pumpNaKATP",
        "pumpCaATP",
        "nernst_planck_flux",
        "update_Co",
        "div_env",
        "no_negs",
        "check_v",
        "integrator",
        "gj_run",
        "noop_context",
    ),
)
def test_first_step_exact_original_whole_module_code_and_body_roster(name):
    node, code = stage._definitions()[name]
    assert code.co_name == ("run" if name == "gj_run" else name)
    assert code.co_filename.startswith(str(stage.NATIVE) + "/")
    assert node.body and code.co_code


def test_first_step_original_full_calendar_and_native_sampling_are_retained():
    definitions = stage._definitions()
    clock = definitions["_plot_loop"][0]
    text = ast.unparse(clock)
    assert "np.linspace(0, phase_time_len, phase_time_step_count)" in text
    assert "i += phase.p.t_resample" in text and "i = int(i)" in text
    assert "time_steps_sampled.add(time_steps[i])" in text
    assert "arange" not in text
    assert "phase.p.anim.is_while_sim" in text
    assert "phase_deformed = SimPhase(" in text
    assert "solver_context = noop_context()" in text
    assert not any(
        isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
        for node in ast.walk(clock)
    )


def test_first_step_normal_transport_and_pump_order_is_literal():
    loop = stage._definitions()["_run_sim_core_loop"][0]
    text = ast.unparse(loop)
    names = [
        "self.fluxes_mem.fill(0)",
        "stb.pumpNaKATP(",
        "stb.electroflux(",
        "self.update_gj(",
        "self.update_ecm(",
        "self.update_intra(",
        "self.ca_handler(",
        "self.update_all_concs(",
        "self.update_V(",
        "stb.check_v(",
    ]
    positions = [text.index(name) for name in names]
    assert positions == sorted(positions)
    assert "phase.kind is SimPhaseKind.SIM" in text
    assert "self.molecules.core.run_loop(" in text
    assert "self.grn.core.run_loop(" in text
    assert "t in time_steps_sampled" in text
    assert "self.write2storage(t, cells, p)" in text


def test_first_step_post_electrical_caller_has_original_order_and_no_pickle():
    caller = stage._definitions()["setup"][0]
    assert len(caller.body) == 4
    assert ast.unparse(caller.body[0]).startswith(
        "time_steps, time_steps_sampled, solver_context = self._plot_loop(phase)"
    )
    assert "phase.callbacks.progress_ranged(progress_max=len(time_steps_sampled))" == ast.unparse(
        caller.body[1]
    )
    assert ast.unparse(caller.body[2]) == "exception_instability = None"
    text = ast.unparse(caller)
    assert "with solver_context:" in text
    assert "_pickle_phase" not in text and "self.init_dynamics" not in text


def test_first_step_flux_inverse_and_native_dt_are_not_repaired_or_disabled():
    plan = stage.source_plan()
    assert plan["full_calendar_and_sampled_set_retained"]
    assert plan["native_dt_and_sampling_unchanged"]
    assert plan["actual_source_RNG_operator_reference_or_scientific_release"] is False
    names = {
        node.attr
        for definition, _ in stage._definitions().values()
        for node in ast.walk(definition)
        if isinstance(node, ast.Attribute)
    }
    assert "lapENVinv" in names and "lapENV_P_inv" not in names
    assert "init_tsteps" in names and "t_resample" in names and "dt" in names


@pytest.mark.parametrize(
    "text,expected",
    (
        ("self.cc_cells[i] += value", {"cc_cells"}),
        ("self.fluxes_mem.fill(0)", {"fluxes_mem"}),
        ("self.vm_time.append(self.vm * 1)", {"vm_time"}),
        ("self.update_gj(cells, p, t, i)", set()),
        ("value = self.cc_cells[i]", set()),
    ),
)
def test_first_step_independent_store_and_inplace_effect_extraction(text, expected):
    assert stage._effects(ast.parse(text).body, "self") == expected


@pytest.mark.parametrize("entry", ("ready", "request", "prepare"))
def test_first_step_unbound_real_parent_refuses_before_foreign_inspection(entry, monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No supplied owner or state may be consulted")

    with pytest.raises(stage.FirstStepRejected) as caught:
        if entry == "ready":
            stage._ready()
        elif entry == "request":
            stage.from_electrical(Foreign(), law_id=stage.LAW_ID)
        else:
            monkeypatch.setenv(stage.RELEASE, "1")
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "held" and caught.value.trial is None


@pytest.mark.parametrize("which", ("electrical", "Key"))
def test_first_step_new_outgoing_ancestor_names_remain_real_unavailable_prerequisites(which):
    if which == "electrical":
        with pytest.raises(stage.previous.ElectricalRejected) as caught:
            stage.previous._first_step_api()
        assert caught.value.stage == "first_step_held"
    else:
        with pytest.raises(stage.previous.storage.StorageRejected) as caught:
            stage.previous.storage._first_step_key_api()
        assert caught.value.stage == "first_step_ancestor_held"


def test_first_step_handle_constructor_and_hydration_do_not_supply_an_owner():
    with pytest.raises(TypeError):
        stage.FirstStepOwner()
    with pytest.raises(stage.FirstStepRejected):
        stage._authority(object())


@pytest.mark.parametrize("falsey", (False, True))
def test_first_step_sticky_entry_rejection_precedes_secondary_capture(falsey):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary = (Falsey if falsey else ValueError)("actual earlier rejection")
    primary.__cause__ = TypeError("retained source cause")
    context = NS(entry_error=primary, capture_error=OSError("secondary capture"))
    with pytest.raises(ValueError) as caught:
        stage._guard(context)
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__


@pytest.mark.parametrize("change", ("same", "slot", "code", "keyword"))
def test_first_step_parent_callback_proof_refuses_retarget_without_invocation(change, monkeypatch):
    module, calls = ModuleType("explicit_callback_metadata_only"), []

    def template(value):
        value.append("called")

    claim = FunctionType(template.__code__, vars(module), "claim")
    check = FunctionType(template.__code__, vars(module), "check")
    module.claim, module.check = claim, check
    module._parent_atoms = stage.previous._parent_atoms
    binding = stage._ParentBinding(
        module,
        claim,
        check,
        (stage.previous._parent_atoms(claim), stage.previous._parent_atoms(check)),
    )
    checker = FunctionType(
        stage._check_parent.__code__,
        dict(vars(stage), previous=module, PARENT_CLAIM="claim", PARENT_CHECK="check"),
    )
    checker(binding)
    if change == "slot":
        module.claim = FunctionType(claim.__code__, vars(module), "claim")
    elif change == "code":
        monkeypatch.setattr(claim, "__code__", claim.__code__.replace(co_name="retargeted"))
    elif change == "keyword":
        monkeypatch.setattr(claim, "__kwdefaults__", {"hidden_delegate": object()})
    if change == "same":
        checker(binding)
    else:
        with pytest.raises(ValueError):
            checker(binding)
    assert calls == []


@pytest.mark.parametrize("event", ("first", "stop", "wrong_frame", "wrong_offset"))
def test_first_step_boundary_retains_original_t0_without_advancing_a_second_label(event):
    # Isolated boundary decision; these metadata records are not a native frame
    # or an issued owner and are never accepted by the public source API.
    frame = NS(f_code=object(), f_lasti=8, f_locals={"t": 0.0})
    context = NS(
        loop_frame=frame,
        loop_code=frame.f_code,
        loop_offset=8,
        loop_visits=1 if event == "stop" else 0,
        source_time_label=None,
        stop_frame=None,
        selected_stop=stage._SelectedStop("test boundary"),
    )
    actual = frame
    if event == "wrong_frame":
        actual = NS(f_code=frame.f_code, f_lasti=8)
    elif event == "wrong_offset":
        frame.f_lasti = 10
    if event == "stop":
        with pytest.raises(stage._SelectedStop) as caught:
            stage._loop_boundary(context, actual)
        assert caught.value is context.selected_stop and context.source_time_label == 0.0
        assert context.stop_frame is frame and context.loop_visits == 2
    else:
        stage._loop_boundary(context, actual)
        assert context.loop_visits == int(event == "first")
        assert context.stop_frame is None and context.source_time_label is None


@pytest.mark.parametrize("seconds", (True, 481, 7200, None))
def test_first_step_software_guard_cannot_gain_a_long_or_unknown_mode(seconds):
    with pytest.raises(ValueError):
        software._integration_policy("test_first_step", seconds)


def test_first_step_source_entry_blockade_keeps_actual_namespace_and_body_closed():
    for name in ("_namespace", "_run"):
        frame = NS(
            f_globals={"__name__": "cells.processes.betse_native_init_first_step"},
            f_code=NS(co_name=name),
        )
        assert software.is_forbidden_frame(frame)
    assert not any(name == "betse" or name.startswith("betse.") for name in sys.modules)


@pytest.mark.parametrize("source_failure", (False, True))
def test_first_step_raw_return_and_original_error_precede_local_capture_failure(
    source_failure, monkeypatch
):
    frame, returned = sys._getframe(), object()
    primary = ValueError("original selected source error")
    primary.__cause__ = RuntimeError("original source cause")
    capture = OSError("metadata local capture refused")

    class FailingLocals(dict):
        def __setitem__(self, key, value):
            raise capture

    row = dict(frame=frame, returned=False)
    context = NS(
        frames={id(frame): row},
        setup_frame=frame,
        pending={id(frame): primary} if source_failure else {},
        primary=None,
        raw_returns=[],
        locals=FailingLocals(),
        capture_error=None,
        capture_errors=(),
        selected_stop=stage._SelectedStop("not source failure"),
    )
    initial = stage.previous.storage.previous.previous.previous
    monkeypatch.setattr(initial, "_normal_return", lambda actual: not source_failure)
    stage._observe(context, frame, "return", returned)
    assert context.last_raw == (frame, returned) and context.raw_returns == [(frame, returned)]
    assert context.capture_error is capture and not row["returned"]
    assert context.primary is (primary if source_failure else None)
    if source_failure:
        assert context.primary.__cause__ is primary.__cause__


@pytest.mark.parametrize("retarget", (False, True))
def test_first_step_projection_graph_is_stable_and_keeps_equal_reference_edges(
    retarget, monkeypatch
):
    scope = observation.Scope()
    first, second = [1, 2], [1, 2]
    actual = NS(first=first, second=second, repeated=first)
    objects = (("declared_metadata_only", actual),)
    fields = [{}]
    context = NS(
        objects=objects,
        permissions=(),
        parent=object(),
        graph_fields=fields,
        graph_view=NS(objects=objects, fields=fields),
        graph_tape=NS(rng=object(), events=(), draws=(), locals={}),
    )
    monkeypatch.setattr(stage.previous.storage.previous, "_scope", lambda ignored: scope)
    before = stage._graph(context, stable=True)
    if retarget:
        actual.repeated = second
    after = stage._graph(context, stable=True)
    assert fields[0] is context.graph_fields[0]
    assert actual.first == actual.second == actual.repeated == [1, 2]
    if retarget:
        assert after[1] != before[1]
    else:
        stage._same(after[0], before[0])
        assert after[1] == before[1]


@pytest.mark.parametrize("change", ("same", "retarget", "value"))
def test_first_step_paused_local_witness_detects_observer_changes_without_an_owner(
    change, monkeypatch
):
    scope = observation.Scope()
    monkeypatch.setattr(stage.previous.storage.previous, "_scope", lambda ignored: scope)

    def declared_paused_metadata():
        first, second = [10, 20], [10, 20]
        active = first
        yield sys._getframe()
        return active, second

    generator = declared_paused_metadata()
    frame = next(generator)
    context = NS(
        parent=object(),
        objects=(),
        numpy=retained_guards.np,
        work=[dict(frame=frame)],
        transport_frames=[],
        wrapper_claims={},
    )
    before = stage._local_state(context)
    if change == "retarget":
        frame.f_locals["active"] = frame.f_locals["second"]
        assert frame.f_locals["first"] == frame.f_locals["second"] == frame.f_locals["active"]
    elif change == "value":
        frame.f_locals["first"][0] = 99
    after = stage._local_state(context)
    if change == "same":
        stage._same(after[0], before[0])
        assert after[1] == before[1]
    else:
        assert (
            len(before[0]) != len(after[0])
            or any(a is not b for a, b in zip(before[0], after[0], strict=True))
            or before[1] != after[1]
        )
    generator.close()


@pytest.mark.parametrize("case", ("headless", "animation", "FAST", "wrong_kind", "no_ECM"))
def test_first_step_domain_schema_never_retrofits_native_input_or_supplies_a_context(case):
    init, sim, full, fast = object(), object(), object(), object()

    def template():
        pass

    function = FunctionType(
        template.__code__,
        {"SimPhaseKind": NS(INIT=init, SIM=sim), "SolverType": NS(FULL=full, FAST=fast)},
    )
    parameters = NS(
        solver_type=fast if case == "FAST" else full,
        is_ecm=case != "no_ECM",
        anim=NS(is_while_sim=case == "animation"),
    )
    context = NS(
        originals={"setup": function},
        phase=NS(kind=sim if case == "wrong_kind" else init),
        p=parameters,
        cells=NS(lapENV_P_inv=None),
        request=NS(operator_mode="original_value_only_flux_omitted"),
    )
    before, animation = dict(vars(parameters)), dict(vars(parameters.anim))
    if case == "headless":
        stage._domain(context)
    else:
        with pytest.raises(stage.FirstStepRejected) as caught:
            stage._domain(context)
        assert caught.value.stage == ("animation_prerequisite" if case == "animation" else "domain")
        assert caught.value.partial is context
    assert vars(parameters) == before and vars(parameters.anim) == animation
    assert not hasattr(context, "solver_context")


@pytest.mark.parametrize("change", ("same", "profile_code", "trace_code"))
def test_first_step_observer_binding_rejects_live_code_drift_without_touching_outer_hooks(change):
    def template(frame, event, arg):
        return None

    profile, trace = (FunctionType(template.__code__, {}) for _ in range(2))
    getter_profile, getter_trace = lambda: profile, lambda: trace
    setter_profile, setter_trace, call_tracing = object(), object(), object()
    api = NS(
        setprofile=setter_profile,
        settrace=setter_trace,
        getprofile=getter_profile,
        gettrace=getter_trace,
        call_tracing=call_tracing,
    )
    context = NS(
        entry_error=None,
        capture_error=None,
        inherited=False,
        active=True,
        invalid=False,
        thread=stage.get_ident(),
        observing=True,
        setters=(setter_profile, setter_trace),
        getters=(getter_profile, getter_trace),
        call_tracing=call_tracing,
        observers=(profile, trace),
        observer_code_binding=tuple(
            (fn, fn.__code__, fn.__globals__, fn.__closure__) for fn in (profile, trace)
        ),
        stage="declared_observer_metadata_only",
        request=None,
    )
    guard = FunctionType(stage._guard.__code__, dict(vars(stage), sys=api, _ACTIVE=[context]))
    if change != "same":
        function = profile if change == "profile_code" else trace
        function.__code__ = function.__code__.replace(co_name="changed_observer_code")
        with pytest.raises(stage.FirstStepRejected) as caught:
            guard(context)
        assert caught.value is context.entry_error and context.invalid
    else:
        guard(context)
        assert context.entry_error is None and not context.invalid


@pytest.fixture
def installed_iteration_model(tmp_path):
    """Real hook/admission/dispatch code, synthetic METADATA authority only.

    No public owner or issuer registry is fabricated. Parent binding/epochs
    alone are replaced to isolate the interpreter and dual-hook mechanism.
    """
    original_initial = stage.previous.storage.previous.previous.previous
    api = ModuleType("declared_interpreter_dispatch_not_an_owner")
    api.core, api._normal_return = original_initial.core, original_initial._normal_return
    prefix = ModuleType("declared_prelude_metadata_namespace")
    vars(prefix).update(vars(stage.previous.storage.previous.previous))
    prefix.previous = api
    completion = ModuleType("declared_completion_metadata_namespace")
    vars(completion).update(vars(stage.previous.storage.previous))
    completion.previous = prefix
    storage = ModuleType("declared_storage_metadata_namespace")
    vars(storage).update(vars(stage.previous.storage))
    storage.previous = completion
    # This isolated interpreter model has no issued participant or parent.
    # Its parent/binding metadata seam must not impersonate Key's validator.
    storage._molecule_runtime_bindings = lambda current: (
        getattr(current, "molecule", None),
        getattr(current, "molecule_claim", None),
        current.molecule_codes,
    )
    electrical = ModuleType("declared_electrical_metadata_namespace")
    vars(electrical).update(vars(stage.previous))
    electrical.storage = storage

    class Calendar:
        def __init__(self):
            self.next_calls = 0

        def __iter__(self):
            return self

        def __next__(self):
            self.next_calls += 1
            if self.next_calls > 2:
                raise AssertionError("Bounded synthetic iterator advanced beyond the probe limit")
            return self.next_calls - 1

    calendar = Calendar()
    phase = NS(
        steps=calendar,
        sampled=set(),
        bodies=[],
        source_error=None,
        source_cause=None,
        logger=None,
        callbacks=None,
        progress_max=10**25,
        status="callback" + " status",
    )

    def source_loop(self, phase, time_steps, time_steps_sampled, anim_cells):
        for t in time_steps:
            phase.bodies.append(t)
            phase.body_count = len(phase.bodies)
            if phase.source_error is not None:
                raise phase.source_error from phase.source_cause
            if phase.callbacks is not None:
                phase.callbacks.progressed_next(status=phase.status)

    def source_setup(self, phase):
        if phase.logger is not None:
            phase.logger("declared log message")
        if phase.callbacks is not None:
            phase.callbacks.progress_ranged(progress_max=phase.progress_max)
        return self._run_sim_core_loop(phase, phase.steps, phase.sampled, None)

    source_loop = FunctionType(source_loop.__code__, dict(source_loop.__globals__))
    source_setup = FunctionType(source_setup.__code__, dict(source_setup.__globals__))

    factory = type("DeclaredLoopBodyNotNativeSimulator", (), {"_run_sim_core_loop": source_loop})
    initial = NS(factories={"Simulator": factory})
    context = NS(
        entry_error=None,
        capture_error=None,
        capture_errors=(),
        primary=None,
        source_error=None,
        source_chain=None,
        first_failure=None,
        observer_errors=(),
        capture_stop=None,
        stopping=False,
        invalid=False,
        active=True,
        inherited=False,
        observing=False,
        thread=stage.get_ident(),
        stage="declared_interpreter_model",
        request=None,
        required_hooks=(sys.getprofile(), sys.gettrace()),
        setters=(sys.setprofile, sys.settrace),
        getters=(sys.getprofile, sys.gettrace),
        call_tracing=sys.call_tracing,
        cleanup_errors=(),
        hooks_safe=False,
        bindings=(),
        initial=initial,
        phase=phase,
        cells=object(),
        p=object(),
        frames={},
        work=[],
        helper_calls=[],
        c_calls=[],
        raw_returns=[],
        locals={},
        pending={},
        molecule_codes=frozenset(),
        molecule_admissions={},
        molecule_returns={},
        wrapper_attempts=[],
        wrapper_claims={},
        invocations=[],
        transport_frames=[],
        setup_frame=None,
        loop_frame=None,
        body_driver=None,
        driver_frame=None,
        calendar_raw=(calendar, phase.sampled, None),
        time_steps=None,
        sampled=None,
        solver_context=None,
        noop_frame=None,
        noop_entries=0,
        operation=None,
        loop_code=source_loop.__code__,
        loop_visits=0,
        stop_frame=None,
        source_time_label=None,
        selected_stop=stage._SelectedStop("declared first iteration"),
        selected_stopped=False,
        iteration_complete=False,
        loop_returned=False,
    )
    context.loop_offset = next(
        item.offset for item in dis.get_instructions(source_loop) if item.opname == "FOR_ITER"
    )
    namespace = dict(
        vars(stage),
        previous=electrical,
        _ACTIVE=[context],
        _binding=lambda ignored: (),
        _epoch=lambda ignored: ("declared-metadata-only", ((), ()), "no-RNG"),
    )
    for name in (
        "_guard",
        "_reject",
        "_capture",
        "_is_observer_error",
        "_source_error",
        "_pending_exception",
        "_pending_observer_abort",
        "_primary",
        "_admission_error",
        "_callback_sites",
        "_callback_bindings",
        "_callback_arguments",
        "_callback_enter",
        "_callback_frame",
        "_callback_event",
        "_callbacks_complete",
        "_logging_policy",
        "_logging_epoch",
        "_logging_bindings",
        "_logging_entry",
        "_logging_frame",
        "_inherited",
        "_source_row",
        "_helper",
        "_operation",
        "_claim_wrapper",
        "_dispatch",
        "_admit",
        "_loop_boundary",
        "_observe",
        "name_is_yield",
        "_observer_recipe",
    ):
        function = getattr(stage, name)
        namespace[name] = FunctionType(
            function.__code__, namespace, name, function.__defaults__, function.__closure__
        )
    observed = namespace["_observe"]
    context.observed_loop_events = []

    def observe(current, frame, event, arg):
        if frame.f_code is current.loop_code:
            current.observed_loop_events.append((event, frame.f_lasti, frame.f_trace_opcodes))
        return observed(current, frame, event, arg)

    namespace["_observe"] = observe

    def check(current, **kwargs):
        namespace["_guard"](current)
        stage._same(namespace["_binding"](current), current.bindings)

    namespace["_check"] = check
    account = stage._account.__wrapped__
    context.account = contextmanager(
        FunctionType(
            account.__code__, namespace, account.__name__, account.__defaults__, account.__closure__
        )
    )

    def invoke(context, label, delegate, actual, *args, **kwargs):
        return child_dispatch(  # noqa: F821
            declared_child,  # noqa: F821
            context,
            label,
            delegate,
            actual,
            args,
            kwargs,
            sys._getframe(),
        )

    vars(api).update(declared_child=context, child_dispatch=namespace["_dispatch"], sys=sys)
    api._invoke = FunctionType(invoke.__code__, vars(api), "_invoke")
    method, name, delegate, child = "_run_sim_core_loop", "Simulator", source_loop, context
    context_original = initial

    def wrapper(actual, *args, **kwargs):
        context = context_original
        namespace["_claim_wrapper"](child, context, sys._getframe())
        return api._invoke(context, name + "." + method, delegate, actual, *args, **kwargs)

    runtime = type("DeclaredRuntimeNotIssued", (), {"_run_sim_core_loop": wrapper})
    context.sim = runtime()
    context.sim_wrappers = {"_run_sim_core_loop": wrapper}
    context.methods = {"setup": source_setup, "_run_sim_core_loop": source_loop}
    context.originals, context.callback_methods, context.logger_chains = {}, {}, {}
    context.exception_origins, context.exception_events = {}, []
    context.callback_owner = context.callback_type = context.callback_mro = None
    context.callback_chains, context.callback_lookups, context.callback_sites = {}, {}, {}
    context.callback_calls = []
    context.callback_claimed_sites, context.callback_roots = set(), set()
    context.log_configuration = None
    context.log_support, context.log_protocol, context.log_module_members, context.log_surfaces = (
        (),
        (),
        (),
        (),
    )
    context.log_support_codes, context.log_closed_epoch = {}, None
    context.source_files = {}
    context.external, context.wrappers = {}, {}
    context.original_members, context.namespaces, context.facades = [], [], ()
    context.class_surfaces, context.noop_methods = (), ()
    context.noop_object = None
    context.allowed_codes = frozenset(function.__code__ for function in context.methods.values())
    context.body_names = {function.__code__: key for key, function in context.methods.items()}
    namespace["_observer_recipe"](context)

    def drive():
        context.driver_frame = sys._getframe()
        context.transport_frames.append(context.driver_frame)
        with context.account(context):
            source_setup(context.sim, phase)

    def bind_callables():
        # Only private callable transport is exercised. These inert tokens are
        # not issuers, parents, requests, trials, or public owner authority.
        context.parent_binding = context.handler = context.cache = context.entries = object()
        context.electrical_parent = NS(trial=object())
        context.atoms = callable_graph._atoms
        namespace["_bootstrap"] = lambda ignored: None
        fn = stage._binding
        namespace["_binding"] = FunctionType(fn.__code__, namespace)
        context.bindings = namespace["_binding"](context)

    @contextmanager
    def inherited(layer, event, callback, target_code=None):
        required = sys.getprofile(), sys.gettrace()
        local = {}
        target = source_loop.__code__ if target_code is None else target_code

        def profile(frame, actual, arg):
            if required[0] is not None:
                required[0](frame, actual, arg)
            if frame.f_code is target and actual == event:
                callback(frame, actual, arg)

        def trace(frame, actual, arg):
            prior = required[1] if actual == "call" else local.get(id(frame))
            if prior is not None:
                value = prior(frame, actual, arg)
                if callable(value):
                    local[id(frame)] = value
            if frame.f_code is target and actual == event:
                callback(frame, actual, arg)
            if actual == "return":
                local.pop(id(frame), None)
            return trace

        hooks = (profile, required[1]) if layer == "profile" else (required[0], trace)
        try:
            sys.setprofile(hooks[0])
            sys.settrace(hooks[1])
            context.required_hooks = hooks
            yield hooks
            assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
        finally:
            try:
                sys.settrace(required[1])
            finally:
                sys.setprofile(required[0])
                context.required_hooks = required

    return NS(
        context=context,
        phase=phase,
        calendar=calendar,
        drive=drive,
        namespace=namespace,
        bind_callables=bind_callables,
        inherited=inherited,
        loop=source_loop,
        directory=tmp_path,
    )


def test_first_step_installed_dual_hooks_complete_one_body_before_second_iterator_advance(
    installed_iteration_model,
):
    h = installed_iteration_model
    required = sys.getprofile(), sys.gettrace()
    try:
        h.drive()
    except BaseException as error:
        raise AssertionError(
            (h.context.loop_visits, h.context.loop_offset, h.context.observed_loop_events)
        ) from error
    assert h.phase.bodies == [0] and h.calendar.next_calls == 1
    assert h.context.loop_visits == 2 and h.context.source_time_label == 0
    assert h.context.selected_stopped and h.context.iteration_complete
    assert not h.context.loop_returned and h.context.primary is None
    assert h.context.entry_error is None and h.context.capture_error is None
    assert h.context.hooks_safe and h.context.cleanup_errors == ()
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]


class FalseSourceError(ValueError):
    def __bool__(self):
        return False


@pytest.mark.parametrize("layer,event", (("trace", "exception"), ("profile", "return")))
@pytest.mark.parametrize("kind", (ValueError, FalseSourceError))
def test_first_step_installed_source_primary_precedes_inherited_failure(
    installed_iteration_model, layer, event, kind
):
    h = installed_iteration_model
    original, cause, observer = (
        kind("source primary"),
        OSError("original cause"),
        RuntimeError("inherited observer"),
    )
    h.phase.source_error, h.phase.source_cause = original, cause

    def fail(frame, actual, arg):
        raise observer

    with h.inherited(layer, event, fail) as hooks:
        with pytest.raises(kind) as caught:
            h.drive()
        assert caught.value is original and original.__cause__ is cause
        assert h.context.primary is original and h.context.source_error is original
        assert h.context.source_chain[0] is original and h.context.source_chain[1] is cause
        assert any(error is observer for error in h.context.observer_errors)
        assert h.context.source_origin == (h.context.loop_frame, original)
        assert h.phase.bodies == [0] and h.calendar.next_calls == 1
        assert not h.context.iteration_complete
        assert h.context.hooks_safe
        assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]


@pytest.mark.parametrize("layer,event", (("trace", "call"), ("profile", "return")))
def test_first_step_installed_observer_failure_has_no_fabricated_source_primary(
    installed_iteration_model, layer, event
):
    h, observer = installed_iteration_model, RuntimeError("observer only")

    def fail(frame, actual, arg):
        raise observer

    with h.inherited(layer, event, fail) as hooks:
        with pytest.raises(BaseException) as caught:
            h.drive()
        assert caught.value is observer or caught.value is h.context.capture_stop
        assert h.context.primary is None and h.context.source_error is None
        assert any(error is observer for error in h.context.observer_errors)
        assert h.context.capture_error is observer and not h.context.iteration_complete
        assert h.context.hooks_safe
        assert sys.getprofile() is hooks[0] and sys.gettrace() is hooks[1]
        if event == "call":
            assert h.phase.bodies == [] and h.calendar.next_calls == 0


@pytest.mark.parametrize("journal_failure", (False, True))
def test_first_step_installed_exception_record_failure_retains_raw_primary_and_capture(
    installed_iteration_model, journal_failure
):
    h = installed_iteration_model
    original, cause, capture = (
        FalseSourceError("raw source"),
        OSError("cause"),
        RuntimeError("pending write failed"),
    )

    class FailedPending(dict):
        def __setitem__(self, key, value):
            raise capture

    journal = OSError("capture journal failed")

    class FailedJournal:
        def __add__(self, value):
            raise journal

    h.phase.source_error, h.phase.source_cause = original, cause
    h.context.pending = FailedPending()
    if journal_failure:
        h.context.capture_errors = FailedJournal()
    required = sys.getprofile(), sys.gettrace()
    with pytest.raises(FalseSourceError) as caught:
        h.drive()
    assert caught.value is original and original.__cause__ is cause
    assert h.context.source_chain[0] is original and h.context.source_chain[1] is cause
    assert h.context.source_origin == (h.context.loop_frame, original)
    assert h.context.capture_error is capture and h.context.capture_errors
    if journal_failure:
        assert h.context.capture_append_error[0] is journal
    assert h.phase.bodies == [0] and h.calendar.next_calls == 1
    assert not h.context.iteration_complete and h.context.hooks_safe
    assert sys.getprofile() is required[0] and sys.gettrace() is required[1]


def test_first_step_builtin_return_observer_shadow_refuses_before_source(
    installed_iteration_model,
):
    h = installed_iteration_model
    required = sys.getprofile(), sys.gettrace()
    shadow_calls = []

    def shadow(value):
        shadow_calls.append(value)
        raise AssertionError("Builtin shadow must never execute")

    def profile(frame, event, arg):
        if required[0] is not None:
            required[0](frame, event, arg)
        if (
            event == "return"
            and frame.f_code is stage.previous._builtin_bindings.__code__
            and frame.f_locals.get("function") is h.loop
        ):
            h.loop.__globals__["len"] = shadow

    try:
        sys.setprofile(profile)
        stage.previous._builtin_bindings(h.loop)
    finally:
        sys.setprofile(required[0])
    assert h.loop.__globals__["len"] is shadow
    # The post-check namespace baseline contains the attacker change. Fresh
    # builtin validation must reject it even though that baseline is equal.
    h.context.namespaces = [(h.loop.__globals__, tuple(h.loop.__globals__.items()))]
    with pytest.raises(ValueError, match="builtin was shadowed: len"):
        h.bind_callables()
    assert shadow_calls == [] and h.phase.bodies == [] and h.calendar.next_calls == 0


def _install_logger_model(h):
    messages, foreign = [], []

    def body(message, *args, **kwargs):
        messages.append(message)

    def wrapper(message, *args, __delegate=body, **kwargs):
        return __delegate(message, *args, **kwargs)

    wrapper.__wrapped__ = body
    h.context.external["log_info"] = wrapper
    h.context.logger_chains["log_info"] = (wrapper, body)
    h.context.wrappers["log_info"] = h.namespace["_helper"](h.context, "log_info")
    h.phase.logger = h.context.wrappers["log_info"]
    for index, member in enumerate((wrapper, body)):
        h.context.allowed_codes |= frozenset((member.__code__,))
        h.context.body_names[member.__code__] = "logger:log_info:" + str(index)
    h.bind_callables()
    return NS(body=body, wrapper=wrapper, messages=messages, foreign=foreign)


@pytest.mark.parametrize("mutation", ("unchanged", "callable", "body_code", "hidden_delegate"))
def test_first_step_installed_logger_original_chain_and_drift(installed_iteration_model, mutation):
    h = installed_iteration_model
    model = _install_logger_model(h)

    def foreign(*args, **kwargs):
        model.foreign.append((args, kwargs))
        raise AssertionError("Foreign logger delegate must not execute")

    if mutation == "callable":
        h.context.external["log_info"] = foreign
    elif mutation == "body_code":
        model.body.__code__ = model.body.__code__.replace(co_name="changed_logger_body")
    elif mutation == "hidden_delegate":
        model.wrapper.__kwdefaults__["__delegate"] = foreign
    if mutation == "unchanged":
        h.drive()
        assert model.messages == ["declared log message"] and h.phase.bodies == [0]
        rows = [row for row in h.context.work if row["name"].startswith("logger:")]
        assert [row["name"] for row in rows] == ["logger:log_info:0", "logger:log_info:1"]
        assert all(row["body_started"] and row["returned"] for row in rows)
    else:
        with pytest.raises(ValueError, match="reference changed"):
            h.drive()
        assert model.messages == [] and h.phase.bodies == [] and h.calendar.next_calls == 0
    assert model.foreign == [] and h.context.hooks_safe


def test_first_step_callback_transport_plan_keeps_actual_native_execution_held():
    plan = stage.source_plan()
    assert "Actual issued callback" in plan["callback_transport"]
    assert "unqualified" in plan["callback_transport"]
    assert plan["callback_source"] == stage.CALLBACK_SOURCE_PINS
    assert plan["actual_source_RNG_operator_reference_or_scientific_release"] is False


@pytest.mark.parametrize("kind", (ValueError, FalseSourceError))
def test_first_step_outgoing_electrical_guard_keeps_recorded_source_primary(kind):
    original, cause = kind("first-step source"), OSError("original source cause")
    original.__cause__ = cause
    child = NS(
        invalid=False,
        entry_error=None,
        first_failure=("source", original),
        capture_error=RuntimeError("secondary capture"),
    )
    with pytest.raises(kind) as caught:
        stage.previous._first_step_reject(child, "secondary entry refusal")
    assert caught.value is original and original.__cause__ is cause
    assert child.invalid and child.entry_error is not original


@pytest.mark.parametrize("mutation", ("callable", "body_code", "hidden_delegate"))
def test_first_step_installed_logger_binding_drift_after_completed_observation(
    installed_iteration_model, mutation
):
    h = installed_iteration_model
    model = _install_logger_model(h)
    h.drive()
    before = tuple(model.messages), tuple(h.phase.bodies), h.calendar.next_calls

    def foreign(*args, **kwargs):
        model.foreign.append((args, kwargs))
        raise AssertionError("No changed logger may run after the completed metadata proof")

    if mutation == "callable":
        h.context.external["log_info"] = foreign
    elif mutation == "body_code":
        model.body.__code__ = model.body.__code__.replace(co_name="changed_logger_body")
    else:
        model.wrapper.__kwdefaults__["__delegate"] = foreign
    with pytest.raises(ValueError, match="reference changed"):
        stage._same(h.namespace["_binding"](h.context), h.context.bindings)
    assert (tuple(model.messages), tuple(h.phase.bodies), h.calendar.next_calls) == before
    assert model.foreign == []


def _definition_for(function):
    tree = ast.parse(stage.Path(__file__).read_bytes())
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.lineno == function.__code__.co_firstlineno
    )


def _wrapped_metadata(function, depth, behavior="normal"):
    """Declared beartype-shaped forwarding; never import/execute native bodies."""
    original = function
    for index in range(depth):

        def wrapper(*args, __beartype_func=function, **kwargs):
            value = __beartype_func(*args, **kwargs)
            if behavior == "twice":
                __beartype_func(*args, **kwargs)
            if behavior == "replace_return":
                return object()
            return value

        code = wrapper.__code__.replace(co_name=function.__name__ + "_layer" + str(index))
        outer = FunctionType(
            code, wrapper.__globals__, code.co_name, wrapper.__defaults__, wrapper.__closure__
        )
        outer.__kwdefaults__ = wrapper.__kwdefaults__
        outer.__wrapped__ = function
        function = outer
    return function, original


def _install_callback_model(h, depth, *, nested=False, behavior="normal"):
    events, result = [], object()
    failure = NS(error=None, cause=None)

    class DeclaredCallbacks:
        def progress_ranged(self, progress_max, progress_min=0):
            events.append(("progress_ranged", self, progress_max, progress_min))
            if failure.error is not None:
                raise failure.error from failure.cause
            return result

        def progressed_next(self, status=None):
            events.append(("progressed_next", self, status))
            if nested:
                self.child_callback(status=status)
            return result

        def child_callback(self, status=None):
            events.append(("child_callback", self, status))
            return result

    callbacks = DeclaredCallbacks()
    h.phase.callbacks = h.context.initial.callback = callbacks
    h.context.callback_owner, h.context.callback_type = callbacks, type(callbacks)
    h.context.callback_mro = type(callbacks).__mro__
    selected = (
        ("progress_ranged", "progressed_next", "child_callback")
        if nested
        else ("progress_ranged", "progressed_next")
    )
    for name in selected:
        body = vars(DeclaredCallbacks)[name]
        outer, _ = _wrapped_metadata(
            body, depth, behavior if name == "progress_ranged" else "normal"
        )
        setattr(DeclaredCallbacks, name, outer)
        chain = []
        member = outer
        while True:
            chain.append(member)
            if not hasattr(member, "__wrapped__"):
                break
            member = member.__wrapped__
        h.context.callback_chains[name] = tuple(chain)
        h.context.callback_lookups[name] = DeclaredCallbacks, outer
        h.context.callback_methods[name] = body
        for index, member in enumerate(chain):
            assert member.__code__ not in h.context.body_names
            h.context.allowed_codes |= frozenset((member.__code__,))
            h.context.body_names[member.__code__] = "callback:" + name + ":" + str(index)
        for method, sites in stage._callback_sites(_definition_for(body), ("self",)).items():
            h.context.callback_sites[("callback:" + name, method)] = sites
    for name, function in h.context.methods.items():
        for method, sites in stage._callback_sites(
            _definition_for(function), ("phase", "callbacks")
        ).items():
            h.context.callback_sites[(name, method)] = sites
    h.bind_callables()
    return NS(callbacks=callbacks, events=events, result=result, failure=failure)


@pytest.mark.parametrize("depth", (0, 1, 2))
@pytest.mark.parametrize("nested", (False, True))
def test_first_step_wrapped_callback_installed_exact_arguments_returns_and_order(
    installed_iteration_model, depth, nested
):
    h = installed_iteration_model
    model = _install_callback_model(h, depth, nested=nested)
    h.drive()
    h.namespace["_callbacks_complete"](h.context)
    expected = ["progress_ranged", "progressed_next", *(["child_callback"] if nested else [])]
    assert [row[0] for row in model.events] == expected
    assert model.events[0][1] is model.callbacks and model.events[0][2] is h.phase.progress_max
    assert model.events[1][2] is h.phase.status
    assert [claim["name"] for claim in h.context.callback_calls] == expected
    for claim in h.context.callback_calls:
        assert len(claim["frames"]) == depth + 1 and claim["complete"]
        assert claim["return_order"] == list(reversed(range(depth + 1)))
        assert all(row["callback_result"] is model.result for row in claim["frames"])
    assert h.context.iteration_complete and h.calendar.next_calls == 1


@pytest.mark.parametrize(
    "mutation", ("class_lookup", "wrapper_code", "hidden_delegate", "body_code")
)
def test_first_step_wrapped_callback_drift_refuses_before_any_body(
    installed_iteration_model, mutation
):
    h = installed_iteration_model
    model = _install_callback_model(h, 1)
    outer, body = h.context.callback_chains["progress_ranged"]
    foreign_calls = []

    def foreign(*args, **kwargs):
        foreign_calls.append((args, kwargs))
        raise AssertionError("Retargeted callback must not execute")

    if mutation == "class_lookup":
        type(model.callbacks).progress_ranged = foreign
    elif mutation == "wrapper_code":
        outer.__code__ = outer.__code__.replace(co_name="retargeted_callback_wrapper")
    elif mutation == "hidden_delegate":
        outer.__kwdefaults__["__beartype_func"] = foreign
    else:
        body.__code__ = body.__code__.replace(co_name="retargeted_callback_body")
    with pytest.raises(ValueError):
        h.drive()
    assert model.events == [] and foreign_calls == [] and h.calendar.next_calls == 0
    assert h.context.hooks_safe


@pytest.mark.parametrize("layer", ("trace", "profile"))
@pytest.mark.parametrize("method", ("progress_ranged", "progressed_next"))
def test_first_step_wrapped_callback_caught_observer_reentry_stays_poisoned(
    installed_iteration_model, layer, method
):
    h = installed_iteration_model
    model = _install_callback_model(h, 1)
    target = h.context.callback_chains["progress_ranged"][0].__code__
    previous = sys.getprofile(), sys.gettrace()
    rejected = []

    def observer(frame, event, arg):
        if frame.f_code is target and event == "call":
            try:
                if method == "progress_ranged":
                    model.callbacks.progress_ranged(progress_max=h.phase.progress_max)
                else:
                    model.callbacks.progressed_next(status=h.phase.status)
            except stage.FirstStepRejected as error:
                rejected.append(error)

    def profile(frame, event, arg):
        if previous[0] is not None:
            previous[0](frame, event, arg)
        observer(frame, event, arg)

    def trace(frame, event, arg):
        observer(frame, event, arg)
        return trace

    hooks = (profile, previous[1]) if layer == "profile" else (previous[0], trace)
    try:
        sys.setprofile(hooks[0])
        sys.settrace(hooks[1])
        h.context.required_hooks = hooks
        h.bind_callables()
        with pytest.raises(stage.FirstStepRejected) as caught:
            h.drive()
        assert rejected and caught.value is rejected[0]
        assert h.context.invalid and h.context.callback_calls
        assert model.events == [] and h.calendar.next_calls == 0
        assert h.context.hooks_safe
    finally:
        try:
            sys.settrace(previous[1])
        finally:
            sys.setprofile(previous[0])
            h.context.required_hooks = previous


@pytest.mark.parametrize("behavior", ("twice", "replace_return"))
def test_first_step_wrapped_callback_misforwarding_retains_first_result_and_no_second_body(
    installed_iteration_model, behavior
):
    h = installed_iteration_model
    model = _install_callback_model(h, 1, behavior=behavior)
    with pytest.raises(stage.FirstStepRejected):
        h.drive()
    assert len(model.events) == 1 and h.calendar.next_calls == 0
    claim = h.context.callback_calls[0]
    assert claim["frames"][-1]["callback_result"] is model.result
    assert not claim["complete"] and h.context.hooks_safe


@pytest.mark.parametrize("kind", (ValueError, FalseSourceError))
def test_first_step_wrapped_callback_source_error_and_cause_retained_once(
    installed_iteration_model, kind
):
    h = installed_iteration_model
    model = _install_callback_model(h, 1)
    error, cause = kind("declared callback source failure"), OSError("source cause")
    model.failure.error, model.failure.cause = error, cause
    with pytest.raises(kind) as caught:
        h.drive()
    assert caught.value is error and error.__cause__ is cause and h.context.primary is error
    assert len(model.events) == 1 and h.calendar.next_calls == 0
    assert not h.context.callback_calls[0]["complete"] and h.context.hooks_safe
    assert h.context.capture_error is None


@pytest.mark.parametrize("mutation", ("class_lookup", "hidden_delegate", "body_code"))
def test_first_step_wrapped_callback_completed_bindings_keep_original_lookup(
    installed_iteration_model, mutation
):
    h = installed_iteration_model
    model = _install_callback_model(h, 1)
    h.drive()
    h.namespace["_callbacks_complete"](h.context)
    before = tuple(model.events)
    outer, body = h.context.callback_chains["progress_ranged"]

    def foreign(*args, **kwargs):
        pytest.fail("No callback execution during a completed authority check")

    if mutation == "class_lookup":
        type(model.callbacks).progress_ranged = foreign
    elif mutation == "hidden_delegate":
        outer.__kwdefaults__["__beartype_func"] = foreign
    else:
        body.__code__ = body.__code__.replace(co_name="changed_closed_callback")
    with pytest.raises(ValueError):
        stage._same(h.namespace["_binding"](h.context), h.context.bindings)
    assert tuple(model.events) == before


@pytest.mark.parametrize("layer,event", (("trace", "call"), ("profile", "return")))
def test_first_step_wrapped_callback_equal_argument_retarget_refuses_before_next_delegate(
    installed_iteration_model, layer, event
):
    h = installed_iteration_model
    model = _install_callback_model(h, 1)
    function = h.context.callback_chains["progress_ranged"][0 if event == "call" else -1]
    equal = int(str(h.phase.progress_max))
    assert equal == h.phase.progress_max and equal is not h.phase.progress_max
    attempts = []

    def retarget(frame, actual, arg):
        attempts.append((frame, actual, arg))
        if event == "call":
            frame.f_locals["kwargs"]["progress_max"] = equal
        else:
            frame.f_locals["progress_max"] = equal

    with h.inherited(layer, event, retarget, function.__code__):
        h.bind_callables()
        with pytest.raises(ValueError):
            h.drive()
        assert attempts and h.context.invalid
        assert len(model.events) == int(event == "return") and h.calendar.next_calls == 0
        assert h.context.hooks_safe


def test_first_step_wrapped_callback_raw_result_survives_capture_refusal(installed_iteration_model):
    h = installed_iteration_model
    model = _install_callback_model(h, 1)
    original = h.namespace["_callback_frame"]
    capture = OSError("callback result observation refused")

    def failed_after_return(context, row):
        if row.get("callback_raw_seen"):
            raise capture
        return original(context, row)

    h.namespace["_callback_frame"] = failed_after_return
    h.bind_callables()
    with pytest.raises((OSError, stage._ObservationStop)):
        h.drive()
    claim = h.context.callback_calls[0]
    body = claim["frames"][-1]
    assert len(model.events) == 1 and body["callback_result"] is model.result
    assert body["callback_last_raw"] == (body["frame"], model.result)
    assert h.context.capture_error is capture and h.context.primary is None
    assert h.context.source_error is None and not claim["complete"] and h.calendar.next_calls == 0
    assert h.context.hooks_safe


def _install_configured_logging_model(h, wrapped):
    """Real stdlib dispatch/delayed pytest-file I/O; native-shaped stand-ins."""
    events, records, failed = (
        [],
        [],
        NS(
            error=None,
            cause=None,
            pending=[],
            retries=[],
            final_error=RuntimeError("retry exhausted"),
        ),
    )

    class MoreThanInfo(logging.Filter):
        def filter(self, record):
            events.append(("info_filter", self, record))
            return record.levelno <= logging.INFO

    class ThirdPartyDebug(logging.Filter):
        def filter(self, record):
            events.append(("debug_filter", self, record))
            return record.levelno > logging.DEBUG or record.name.startswith("declared")

    class FileLikeHandler(logging.handlers.RotatingFileHandler):
        def emit(self, record):
            events.append(("file_emit", self, record))
            records.append(record)
            if failed.error is not None:
                raise failed.error from failed.cause
            if failed.pending:
                try:
                    raise failed.pending.pop(0)
                except FileNotFoundError:
                    return self._emit_safely(record)
                except OSError as error:
                    if error.errno == 116:
                        return self._emit_safely(record)
                    raise
            return super().emit(record)

        def _emit_safely(self, record):
            last = None
            for attempt in range(2):
                failed.retries.append(attempt)
                try:
                    if failed.pending:
                        raise failed.pending.pop(0)
                    return super().emit(record)
                except FileNotFoundError as error:
                    last = error
                except OSError as error:
                    if error.errno != 116:
                        raise
                    last = error
            raise failed.final_error from last

    for cls, name in (
        (MoreThanInfo, "filter"),
        (ThirdPartyDebug, "filter"),
        (FileLikeHandler, "emit"),
        (FileLikeHandler, "_emit_safely"),
    ):
        original = vars(cls)[name]
        outer, _ = _wrapped_metadata(original, int(wrapped))
        setattr(cls, name, outer)
    root = logging.Logger("declared_root", level=logging.DEBUG)
    stdout, stderr, file = (
        logging.StreamHandler(io.StringIO()),
        logging.StreamHandler(io.StringIO()),
        FileLikeHandler(
            h.directory / "declared-logging.log",
            mode="a",
            encoding="utf-8",
            delay=True,
            maxBytes=2**20,
            backupCount=8,
        ),
    )
    formatter = logging.Formatter("%(message)s")
    for handler, level in ((stdout, logging.INFO), (stderr, logging.WARNING), (file, logging.INFO)):
        handler.setLevel(level)
        handler.setFormatter(formatter)
        root.addHandler(handler)
    low, debug_stdout, debug_stderr, debug_file = (
        MoreThanInfo(),
        ThirdPartyDebug(),
        ThirdPartyDebug(),
        ThirdPartyDebug(),
    )
    stdout.addFilter(low)
    stdout.addFilter(debug_stdout)
    stderr.addFilter(debug_stderr)
    file.addFilter(debug_file)
    config = NS(
        _logger_root=root,
        _logger_root_handler_stdout=stdout,
        _logger_root_handler_stderr=stderr,
        _logger_root_handler_file=file,
    )
    module = ModuleType("declared_config_not_native_issuance")
    module._log_conf = config
    facade = ModuleType("declared_stdlib_root_binding")
    vars(facade).update(vars(logging), root=root)
    h.namespace["logging"] = facade
    context = h.context
    handlers = (("stdout", stdout), ("stderr", stderr), ("file", file))
    context.log_configuration = (
        module,
        config,
        type(config),
        root,
        root.handlers,
        root.filters,
        handlers,
        {},
    )
    entries = []
    for role, handler in handlers:
        for index, actual in enumerate(handler.filters):
            outer = vars(type(actual))["filter"]
            chain = (outer, outer.__wrapped__) if wrapped else (outer,)
            entries.append(
                stage._LoggingMethod(
                    role + ".filter" + str(index), actual, type(actual), "filter", chain
                )
            )
        if role == "file":
            for name in ("emit", "_emit_safely"):
                outer = vars(type(handler))[name]
                chain = (outer, outer.__wrapped__) if wrapped else (outer,)
                entries.append(stage._LoggingMethod(role, handler, type(handler), name, chain))
    context.log_support = tuple(entries)
    context.log_protocol = tuple(
        (owner, name, vars(owner)[name])
        for owner, names in (
            (
                logging.Logger,
                ("info", "_log", "handle", "callHandlers", "isEnabledFor", "makeRecord"),
            ),
            (logging.Filterer, ("filter",)),
            (logging.Handler, ("handle", "format", "acquire", "release")),
            (logging.StreamHandler, ("emit", "flush")),
        )
        for name in names
    )
    context.log_module_members = tuple(
        (name, vars(facade)[name])
        for name in (
            "root",
            "Logger",
            "Filterer",
            "Handler",
            "LogRecord",
            "_logRecordFactory",
            "_lock",
            "raiseExceptions",
            "lastResort",
        )
    )
    context.log_surfaces = ()
    context.log_configuration_binding = h.namespace["_logging_policy"](context)
    choices = {}
    for entry in entries:
        for index, member in enumerate(entry.chain):
            choices.setdefault(member.__code__, []).append((entry, index))
            context.allowed_codes |= frozenset((member.__code__,))
            context.body_names[member.__code__] = "logging_support"
    context.log_support_codes = {code: tuple(value) for code, value in choices.items()}

    def log_body(message, *args, **kwargs):
        root.info(message, *args, **kwargs)

    context.external["log_info"] = log_body
    context.logger_chains["log_info"] = (log_body,)
    context.allowed_codes |= frozenset((log_body.__code__,))
    context.body_names[log_body.__code__] = "logger:log_info:0"
    context.wrappers["log_info"] = h.namespace["_helper"](context, "log_info")
    h.phase.logger = context.wrappers["log_info"]
    h.bind_callables()
    return NS(
        events=events,
        records=records,
        root=root,
        stdout=stdout,
        stderr=stderr,
        file=file,
        low=low,
        failed=failed,
        entries=entries,
    )


@pytest.mark.parametrize("wrapped", (False, True))
def test_first_step_configured_logger_installed_real_stdlib_pipeline(
    installed_iteration_model, wrapped
):
    h = installed_iteration_model
    model = _install_configured_logging_model(h, wrapped)
    h.drive()
    assert len(model.records) == 1 and model.records[0].getMessage() == "declared log message"
    assert [row[0] for row in model.events] == [
        "info_filter",
        "debug_filter",
        "debug_filter",
        "file_emit",
    ]
    assert all(row[2] is model.records[0] for row in model.events)
    assert model.stdout.stream.getvalue() == "declared log message\n"
    model.file.flush()
    assert stage.Path(model.file.baseFilename).read_text() == "declared log message\n"
    assert model.stderr.stream.getvalue() == ""
    assert h.context.iteration_complete and h.calendar.next_calls == 1 and h.context.hooks_safe


@pytest.mark.parametrize(
    "mutation", ("receiver", "filter_code", "handler_code", "hidden_delegate", "protocol")
)
def test_first_step_configured_logger_drift_zero_foreign_or_io_delegate(
    installed_iteration_model, mutation
):
    h = installed_iteration_model
    model = _install_configured_logging_model(h, True)
    calls = []

    def foreign(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Foreign logging delegate must not execute")

    if mutation == "receiver":
        model.stdout.filters[0] = type(model.low)()
    elif mutation == "filter_code":
        fn = model.entries[0].chain[-1]
        fn.__code__ = fn.__code__.replace(co_name="changed_native_filter")
    elif mutation == "handler_code":
        fn = next(entry for entry in model.entries if entry.method == "emit").chain[-1]
        fn.__code__ = fn.__code__.replace(co_name="changed_native_emit")
    elif mutation == "hidden_delegate":
        model.entries[0].chain[0].__kwdefaults__["__beartype_func"] = foreign
    else:
        owner, name, fn = h.context.log_protocol[0]
        h.context.log_protocol = ((owner, name, foreign), *h.context.log_protocol[1:])
    with pytest.raises(ValueError):
        h.drive()
    assert model.events == [] and calls == [] and h.calendar.next_calls == 0
    assert model.stdout.stream.getvalue() == ""
    assert model.file.stream is None and not stage.Path(model.file.baseFilename).exists()
    assert h.context.hooks_safe


def test_first_step_configured_logger_native_shaped_error_retains_primary_and_record(
    installed_iteration_model,
):
    h = installed_iteration_model
    model = _install_configured_logging_model(h, True)
    error, cause = FalseSourceError("emit source error"), OSError("emit cause")
    model.failed.error, model.failed.cause = error, cause
    with pytest.raises(FalseSourceError) as caught:
        h.drive()
    assert caught.value is error and error.__cause__ is cause and h.context.primary is error
    assert len(model.records) == 1 and h.calendar.next_calls == 0
    assert (
        h.context.source_origin[0].f_code
        is next(entry for entry in model.entries if entry.method == "emit").chain[-1].__code__
    )
    assert h.context.hooks_safe
    assert h.context.capture_error is None


@pytest.mark.parametrize(
    "selector,seconds,allowed",
    (
        ("test_metadata", 480, True),
        (software.ISSUED_CHAIN_TEST, 7200, True),
        (software.ISSUED_CHAIN_TEST, 480, False),
        ("test_metadata", 7200, False),
        (software.ISSUED_CHAIN_TEST + ",test_metadata", 7200, False),
        (software.ISSUED_CHAIN_TEST, True, False),
        (software.ISSUED_CHAIN_TEST, 7201, False),
        ("", 480, False),
    ),
)
def test_first_step_chain_envelope_is_exact_single_item(selector, seconds, allowed):
    if allowed:
        assert software._integration_policy(selector, seconds) == seconds
    else:
        with pytest.raises(ValueError):
            software._integration_policy(selector, seconds)


@pytest.mark.parametrize("entry", ("foreign", "real_metadata_frame"))
def test_first_step_chain_driver_never_admits_unissued_or_unbound_frames(entry, monkeypatch):
    monkeypatch.setenv(software.ISSUED_CHAIN_RELEASE, "1")
    monkeypatch.setattr(software, "_MODEL_RUN_BINDINGS", None)
    candidate = object() if entry == "foreign" else sys._getframe()
    assert software._issued_model_driver(candidate) is False


@pytest.mark.parametrize("wrapped", (False, True))
@pytest.mark.parametrize("kind", ("missing", "stale"))
def test_first_step_configured_logger_handled_retry_preserves_success(
    installed_iteration_model, wrapped, kind
):
    h = installed_iteration_model
    model = _install_configured_logging_model(h, wrapped)
    errors = (
        [FileNotFoundError("initial"), FileNotFoundError("retry")]
        if kind == "missing"
        else [OSError(116, "initial"), OSError(116, "retry")]
    )
    model.failed.pending.extend(errors)
    h.drive()
    assert h.context.primary is None and h.context.source_error is None
    assert h.context.capture_error is None and h.context.entry_error is None
    assert model.failed.retries == [0, 1] and model.failed.pending == []
    assert h.context.iteration_complete and h.calendar.next_calls == 1
    assert all(any(event[1] is error for event in h.context.exception_events) for error in errors)
    model.file.flush()
    assert stage.Path(model.file.baseFilename).read_text() == "declared log message\n"
    assert h.context.hooks_safe


@pytest.mark.parametrize("wrapped", (False, True))
def test_first_step_configured_logger_exhausted_retry_keeps_final_source_cause(
    installed_iteration_model, wrapped
):
    h = installed_iteration_model
    model = _install_configured_logging_model(h, wrapped)
    errors = [FileNotFoundError("initial"), FileNotFoundError("retry0"), OSError(116, "retry1")]
    model.failed.pending.extend(errors)
    with pytest.raises(RuntimeError) as caught:
        h.drive()
    assert caught.value is model.failed.final_error and caught.value.__cause__ is errors[-1]
    assert h.context.primary is caught.value and h.context.source_chain[1] is errors[-1]
    assert model.failed.retries == [0, 1] and h.calendar.next_calls == 0
    assert not h.context.iteration_complete and h.context.hooks_safe


@pytest.mark.parametrize("layer", ("profile", "trace"))
@pytest.mark.parametrize("wrapped", (False, True))
def test_first_step_logging_nested_retry_entry_observer_keeps_caller_pending_original(
    installed_iteration_model, layer, wrapped
):
    h = installed_iteration_model
    model = _install_configured_logging_model(h, wrapped)
    original, cause = FileNotFoundError("native emit pending"), OSError("original cause")
    original.__cause__ = cause
    unused = FileNotFoundError("unattempted retry")
    observer = RuntimeError("observer rejected nested retry entry")
    model.failed.pending.extend((original, unused))
    retry = next(entry for entry in model.entries if entry.method == "_emit_safely")

    def reject(frame, event, arg):
        raise observer

    with h.inherited(layer, "call", reject, retry.chain[0].__code__):
        h.bind_callables()
        with pytest.raises(FileNotFoundError) as caught:
            h.drive()
        assert caught.value is original and original.__cause__ is cause
        assert h.context.primary is original and h.context.source_chain[1] is cause
        origin = h.context.source_origin[0]
        assert h.context.pending[id(origin)] is original
        assert any(error is observer for error in h.context.observer_errors)
        assert h.context.capture_error is observer
        assert model.failed.retries == [] and model.failed.pending == [unused]
        assert h.calendar.next_calls == 0 and not h.context.iteration_complete
        assert h.context.hooks_safe
        if layer == "profile":
            # Trace remains installed after profile rejection and observes the
            # subsequent observer exception in the caller. It must not replace
            # the pending native failure already selected as the primary.
            delivery = h.context.last_observer_exception_delivery
            assert delivery[1] is observer
            assert h.context.pending[id(origin)] is original


@pytest.mark.parametrize("shared", (False, True))
@pytest.mark.parametrize("empty", (False, True))
def test_enabled_runtime_permissions_union_by_actual_holder_without_shadowing(shared, empty):
    storage = stage.previous.storage
    first, second = NS(value=1), NS(value=1)
    owner = first if shared else second
    original = ((first, frozenset(("vm",))),)
    fields = frozenset() if empty else frozenset(("cc_cells", "extra_rho_cells"))
    rows = storage._merge_permissions(original, ((owner, fields),))
    assert original == ((first, frozenset(("vm",))),)
    assert len(rows) == (1 if shared else 2)
    assert rows[0][0] is first
    assert rows[0][1] == (original[0][1] | fields if shared else original[0][1])
    if not shared:
        assert rows[1][0] is second and rows[1][1] is fields


@pytest.mark.parametrize("fields", (("cc_cells",), {"cc_cells"}, frozenset((1,))))
def test_enabled_runtime_permissions_refuse_nonexact_field_authority(fields):
    with pytest.raises(ValueError, match="permissions"):
        stage.previous.storage._merge_permissions((), ((NS(), fields),))


@pytest.mark.parametrize("kind", ("storage", "first_step"))
def test_enabled_runtime_real_api_rejects_unissued_claim_before_source_or_permissions(kind):
    from cells.processes import betse_native_init_molecule_network as molecule

    storage, unissued = stage.previous.storage, object()
    lease = NS(molecule_claim=unissued)
    context = NS(
        parent=NS(
            request=NS(native_molecules=True),
            molecule=molecule,
            storage_lease=lease,
            first_step_descendant=lease,
        ),
        allowed_codes=frozenset(),
    )
    with pytest.raises(molecule.MoleculeNetworkRejected, match="issued"):
        storage._bind_molecule_runtime(context, kind=kind)
    assert context.molecule_claim is None and context.molecule_record is None
    assert context.molecule_permissions == () and context.allowed_codes == frozenset()


@pytest.mark.parametrize("event", ("call", "return"))
def test_enabled_runtime_storage_observer_delegates_only_to_actual_public_claim_check(event):
    from cells.processes import betse_native_init_molecule_network as molecule

    storage = stage.previous.storage

    def never_called():
        pytest.fail("Source body must remain blocked")

    context = NS(
        molecule_codes=frozenset((never_called.__code__,)),
        molecule=molecule,
        molecule_claim=object(),
        work=[],
    )
    frame = NS(f_code=never_called.__code__)
    with pytest.raises(molecule.MoleculeNetworkRejected, match="issued"):
        storage._observe(context, frame, event, None)
    assert context.work == []


def test_enabled_material_ancestor_refuses_foreign_entry_before_retirement(monkeypatch):
    from cells.processes import betse_native_init_molecule_network as molecule

    initial = stage.previous.storage.previous.previous.previous
    parent = NS()
    completion = NS(molecule=molecule, request=NS(native_molecules=True))
    monkeypatch.setattr(initial, "_completion_runtime", lambda value: (completion,))
    size = len(initial._MOLECULE_INITIAL_LEASES)
    with pytest.raises(ValueError, match="binder"):
        initial._claim_completion_molecule_ancestor(parent, completion, object())
    assert len(initial._MOLECULE_INITIAL_LEASES) == size
    assert not hasattr(parent, "molecule_initial_lease")


@pytest.mark.parametrize("layer", ("trace", "profile"))
def test_enabled_runtime_common_admission_refuses_before_inherited_callback(
    installed_iteration_model, layer
):
    """Isolated interpreter seam; no issued molecular owner is supplied."""
    h = installed_iteration_model
    calls, entered = [], []
    primary = ValueError("declared runtime source admission refused")

    def synthetic_network(message):
        entered.append("body")

    def observe(claim, *, child, frame, event, arg):
        assert child is h.context and frame.f_code is synthetic_network.__code__
        calls.append((frame, event, arg))
        raise primary

    h.context.molecule_codes = frozenset((synthetic_network.__code__,))
    h.context.allowed_codes |= h.context.molecule_codes
    h.context.molecule, h.context.molecule_claim = NS(observe_runtime=observe), object()
    h.phase.logger = synthetic_network
    inherited = []
    with h.inherited(
        layer, "call", lambda *args: inherited.append(args), synthetic_network.__code__
    ):
        h.bind_callables()
        with pytest.raises(ValueError) as caught:
            h.drive()
        assert caught.value is primary and len(calls) == 1
        assert entered == [] and inherited == [] and h.context.hooks_safe


def test_enabled_runtime_isolated_transcript_has_one_python_return_and_both_c_edges(
    installed_iteration_model,
):
    """Transcript wiring only; the provider here issues no public authority."""
    h = installed_iteration_model
    calls, entered = [], []

    def synthetic_network(message):
        entered.append(message)

    def observe(claim, *, child, frame, event, arg):
        assert child is h.context and frame.f_code is synthetic_network.__code__
        calls.append((frame, event, arg))

    h.context.molecule_codes = frozenset((synthetic_network.__code__,))
    h.context.allowed_codes |= h.context.molecule_codes
    h.context.molecule, h.context.molecule_claim = NS(observe_runtime=observe), object()
    h.phase.logger = synthetic_network
    h.bind_callables()
    h.drive()
    assert entered == ["declared log message"]
    assert sum(event == "call" for _, event, _ in calls) == 1
    assert sum(event == "return" for _, event, _ in calls) == 1
    c_calls = [arg for _, event, arg in calls if event == "c_call"]
    c_returns = [arg for _, event, arg in calls if event == "c_return"]
    assert len(c_calls) == len(c_returns) == 1
    assert c_calls[0].__self__ is entered and c_calls[0].__name__ == "append"
    assert c_returns[0].__self__ is entered and c_returns[0].__name__ == "append"
    assert h.context.hooks_safe and h.calendar.next_calls == 1


def _enabled_public_chain_inputs(monkeypatch, tmp_path):
    """Pre-birth acquisition only; all six public issuers/registries are real.

    The existing explicitly synthetic SEED/parameter predecessor is retained.
    Toy arithmetic and a two-label calendar prove ownership transport, never
    native correspondence, independent physics or a completed INIT history.
    """
    from tests.unit import test_betse_native_init_storage as storage_model

    h = storage_model.synthetic_init_inputs.__wrapped__(monkeypatch, tmp_path)
    storage, electrical, completion = (
        stage.previous.storage,
        stage.previous,
        stage.previous.storage.previous,
    )
    h.p.anim = NS(is_while_sim=False)
    h.p.init_tsteps = 2
    h.cells.lapENV_P_inv = None
    calendar, sampled = np.array([0.0, h.p.dt]), {0.0}
    namespace = dict(
        __name__=__name__,
        __builtins__=__builtins__,
        np=np,
        calendar=calendar,
        sampled=sampled,
    )
    text = """
class Callback:
    def progress_ranged(self, progress_max):
        return None
    def progressed_next(self, status=None):
        return None
def update_V(self, cells, p):
    self.vm = self.channel_noise_factor * 1.0
def _plot_loop(self, phase):
    return calendar, sampled, None
def _run_sim_core_loop(self, phase, time_steps, time_steps_sampled, anim_cells):
    for t in time_steps:
        self.molecules.core.clear_run_loop(self)
        self.molecules.core.run_loop(phase, t)
        self.update_V(phase.cells, phase.p)
        if t in time_steps_sampled:
            self.write2storage(t, phase.cells, phase.p)
            phase.callbacks.progressed_next(status="declared first-step sample")
def write2storage(self, t, cells, p):
    self.vm_time.append(self.vm * 1.0)
    self.molecules.core.write_data(self, cells, p)
    self.molecules.core.report(self, p)
def setup(self, phase):
    time_steps, time_steps_sampled, solver_context = self._plot_loop(phase)
    phase.callbacks.progress_ranged(progress_max=len(time_steps_sampled))
    self._run_sim_core_loop(phase, time_steps, time_steps_sampled, None)
"""
    tree = ast.parse(text)
    exec(compile(tree, __file__, "exec"), namespace)
    callback = namespace["Callback"]()
    # This predecessor has not issued an INIT, phase or parameter claim.
    # Supply its callback input coherently BEFORE every public declaration.
    old = h.callback
    assert not hasattr(h, "owner") and h.upstream.phase.callbacks is old
    h.callback = h.upstream.phase.callbacks = callback
    roots = h.upstream.world.parent.projector.objects
    index = next(i for i, (_, actual) in enumerate(roots) if actual is old)
    roots[index] = (roots[index][0], callback)
    # Preserve the real subconfiguration object and its attribute API. The
    # synthetic predecessor's old flat p-dictionary codec cannot encode an
    # object by itself: register this exact pre-birth root and capture both its
    # reference token and complete fields, using the existing typed projector.
    roots.append(("animation_configuration", h.p.anim))

    def predecessor_snapshot(parent):
        assert parent is h.upstream and parent.p is h.p and parent.cells is h.cells
        project = retained_guards.stage.core._LITERAL._project
        projector = NS(objects=roots)
        return h.scope.snapshot(
            dict(
                p=project(projector, vars(h.p)),
                cells=project(projector, vars(h.cells)),
                animation_configuration=project(projector, vars(h.p.anim)),
            )
        )

    h.predecessor._snapshot = predecessor_snapshot
    factory = h.factories["Simulator"]
    for name in ("update_V", "_plot_loop", "_run_sim_core_loop", "write2storage"):
        setattr(factory, name, namespace[name])
    factory.run_sim_core = namespace["setup"]
    h.first_step_namespace, h.first_step_tree = namespace, tree
    h.calendar, h.sampled = calendar, sampled

    def electrical_binding():
        functions = completion._claim_electrical_ancestor, completion._check_electrical_ancestor
        return storage._ElectricalBinding(
            electrical,
            completion,
            *functions,
            tuple(storage._electrical_atoms(fn) for fn in functions),
        )

    def electrical_ready():
        functions = storage._claim_for_electrical, storage._check_electrical_authority
        return electrical._ParentBinding(
            storage, *functions, tuple(electrical._parent_atoms(fn) for fn in functions)
        )

    def step_ready():
        functions = electrical._claim_for_first_step, electrical._check_first_step_authority
        return stage._ParentBinding(
            electrical, *functions, tuple(electrical._parent_atoms(fn) for fn in functions)
        )

    def step_binding():
        return electrical._StepBinding(
            stage,
            tuple(
                (name, fn, storage._electrical_atoms(fn))
                for name in (
                    "prepare",
                    "_ready",
                    "_claim_wrapper",
                    "_dispatch",
                    "_check_ancestor_metadata",
                    "_mutation_contract",
                )
                for fn in (vars(stage)[name],)
            ),
        )

    def electrical_namespace(context):
        method = factory.update_V
        context.methods = context.originals = {"update_V": method}
        context.expected_body = method.__code__
        context.allowed_codes = frozenset((method.__code__,))
        context.body_names = {method.__code__: "update_V"}
        context.store_instructions = {
            method.__code__: electrical._store_instructions(method.__code__)
        }
        context.wrappers, context.external = {}, {}
        context.namespaces = (("update_V", method.__globals__, tuple(method.__globals__.items())),)
        context.facades, context.external_members = (), ()

    def step_namespace(context):
        context.methods = {
            name: namespace[name]
            for name in ("setup", "_plot_loop", "_run_sim_core_loop", "update_V", "write2storage")
        }
        context.originals = dict(context.methods)
        context.numpy, context.gap = np, None
        context.sim_wrappers = {
            name: vars(type(context.sim))[name] for name in context.methods if name != "setup"
        }
        context.callback_owner, context.callback_type = callback, type(callback)
        context.callback_mro = type(callback).__mro__
        context.callback_methods = {
            name: vars(type(callback))[name] for name in ("progress_ranged", "progressed_next")
        }
        context.callback_chains = {name: (fn,) for name, fn in context.callback_methods.items()}
        context.callback_lookups = {
            name: (type(callback), fn) for name, fn in context.callback_methods.items()
        }
        context.callback_nodes = {
            node.name: node for node in tree.body[0].body if isinstance(node, ast.FunctionDef)
        }
        definitions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        context.callback_sites = {
            (name, method): positions
            for name in ("setup", "_run_sim_core_loop")
            for method, positions in stage._callback_sites(
                definitions[name], ("phase", "callbacks")
            ).items()
        }
        context.logger_chains, context.external, context.wrappers = {}, {}, {}
        context.noop_methods = ()
        context.namespaces = ((namespace, tuple(namespace.items())),)
        context.facades = ()
        context.allowed_codes = frozenset(
            code
            for fn in (*context.methods.values(), *context.callback_methods.values())
            for code in completion.previous.previous._code_tree(fn.__code__)
        )
        context.body_names = {fn.__code__: name for name, fn in context.methods.items()}
        context.body_names.update(
            (fn.__code__, "callback:" + name + ":0")
            for name, fn in context.callback_methods.items()
        )
        context.loop_code = context.methods["_run_sim_core_loop"].__code__
        context.loop_offset = next(
            item.offset
            for item in dis.get_instructions(context.loop_code)
            if item.opname == "FOR_ITER"
        )
        context.permissions = stage._mutation_contract(context)
        objects = list(completion._objects(context.parent))
        for role, actual in (*context.initial.seed_lease.objects, ("callback", callback)):
            if not any(value is actual for _, value in objects):
                objects.append((role, actual))
        context.objects = tuple(objects)
        context.graph_fields = [{} for _ in objects]
        context.graph_view = NS(objects=context.objects, fields=context.graph_fields)
        context.source_files = MappingProxyType({})

    # Explicit source-acquisition/readiness seams only; public claims, frames,
    # retired parent checks, dispatch, work observers and registries stay real.
    monkeypatch.setattr(storage, "_electrical_api", electrical_binding)
    monkeypatch.setattr(storage, "ELECTRICAL_ANCESTOR_CLAIM", "_claim_electrical_ancestor")
    monkeypatch.setattr(storage, "ELECTRICAL_ANCESTOR_CHECK", "_check_electrical_ancestor")
    monkeypatch.setattr(storage, "FIRST_STEP_ANCESTOR_CLAIM", "_claim_first_step_ancestor")
    monkeypatch.setattr(storage, "FIRST_STEP_ANCESTOR_CHECK", "_check_first_step_ancestor")
    monkeypatch.setattr(electrical, "_ready", electrical_ready)
    monkeypatch.setattr(electrical, "_namespace", electrical_namespace)
    monkeypatch.setattr(electrical, "_first_step_api", step_binding)
    monkeypatch.setattr(stage, "_ready", step_ready)
    monkeypatch.setattr(stage, "_namespace", step_namespace)
    for module in (electrical, stage):
        monkeypatch.setattr(
            module, "source_plan", lambda: dict(synthetic_owner_transport_only=True)
        )
        monkeypatch.setenv(module.RELEASE, "1")
    h.seams += (
        "pre-birth toy callbacks, update_V/calendar/loop/storage bodies and source acquisition",
        "synthetic predecessor projects the same pre-birth animation root and full fields",
        "toy two-label calendar retains first label and forbids second iterator advance",
        "public INIT/prelude/Completion/Storage/Electrical/FirstStep ownership APIs unchanged",
    )
    return h


def test_enabled_public_chain_prebirth_fixture_keeps_issuers_and_participant_apis(
    monkeypatch, tmp_path
):
    storage, electrical = stage.previous.storage, stage.previous
    functions = tuple(module.prepare for module in (storage, electrical, stage))
    registries = tuple(module._ISSUED for module in (storage, electrical, stage))
    h = _enabled_public_chain_inputs(monkeypatch, tmp_path)
    assert tuple(module.prepare for module in (storage, electrical, stage)) == functions
    assert all(
        module._ISSUED is value
        for module, value in zip((storage, electrical, stage), registries, strict=True)
    )
    assert not hasattr(h, "owner") and not hasattr(h, "completion_owner")
    assert h.upstream.phase.callbacks is h.callback
    assert type(h.callback).progress_ranged is h.first_step_namespace["Callback"].progress_ranged
    assert h.calendar.tolist() == [0.0, h.p.dt] and h.p.anim.is_while_sim is False


@pytest.mark.parametrize("mutation", ("unchanged", "flag", "equal_object"))
def test_enabled_public_chain_predecessor_projection_retains_real_subconfiguration(
    monkeypatch, tmp_path, mutation
):
    h = _enabled_public_chain_inputs(monkeypatch, tmp_path)
    original = h.p.anim
    before = h.predecessor._snapshot(h.upstream)
    graph = h.predecessor._graph(h.upstream)
    if mutation == "flag":
        original.is_while_sim = True
    elif mutation == "equal_object":
        h.p.anim = NS(is_while_sim=False)
    if mutation == "equal_object":
        # No registration/hydration of a replacement into the original roots.
        with pytest.raises(ValueError):
            h.predecessor._snapshot(h.upstream)
    else:
        after = h.predecessor._snapshot(h.upstream)
        assert (after.identity == before.identity) is (mutation == "unchanged")
    current = h.predecessor._graph(h.upstream)
    if mutation == "unchanged":
        assert h.p.anim is original
        assert all(a is b for a, b in zip(graph[0], current[0], strict=True))
        assert graph[1] == current[1]
    elif mutation == "equal_object":
        assert (
            len(graph[0]) != len(current[0])
            or any(a is not b for a, b in zip(graph[0], current[0], strict=True))
            or graph[1] != current[1]
        )
    assert not hasattr(h, "owner")


@pytest.mark.parametrize("exact_count", (0, 1, 2))
def test_enabled_chain_selector_requires_one_exact_item_and_excludes_embedded_names(exact_count):
    target = software.ISSUED_CHAIN_TEST
    exact = [NS(name=target, originalname=target) for _ in range(exact_count)]
    embedded = [
        NS(name="test_envelope[" + target + "]", originalname="test_envelope"),
        NS(name=target + "[parameter]", originalname=target),
        NS(name="prefix_" + target, originalname="prefix_" + target),
        NS(name=target, originalname="different_original"),
    ]
    items = [*embedded[:1], *exact, *embedded[1:]]
    if exact_count != 1:
        with pytest.raises(ValueError, match="Exactly one"):
            software._select_items(items, target)
    else:
        selected, removed = software._select_items(items, target)
        assert selected == exact and removed == embedded
        assert selected[0] is exact[0]


def _chain_checkpoint(directory, label, context, *, error=None):
    """Full completed typed caches; raw failure serialization remains bounded."""
    root = directory / label
    root.mkdir()
    caches = {}
    for name in ("before", "after", "stable"):
        value = getattr(context, name, None)
        if value is None:
            continue
        columns = []
        for index, column in enumerate(value.columns):
            path = root / (name + "-" + str(index) + ".npy")
            np.save(path, column.values, allow_pickle=False)
            columns.append(
                dict(name=column.name, path=str(path), sha256=software.snapshot.digest(path))
            )
        caches[name] = dict(
            descriptor=value.descriptor,
            identity=value.identity,
            all_finite=value.all_finite,
            columns=columns,
        )
    software.snapshot.write_json(
        root / "checkpoint.json",
        dict(
            label=label,
            stage=getattr(context, "stage", None),
            error=None if error is None else dict(type=type(error).__name__, message=str(error)),
            objects={
                name: id(getattr(context, name))
                for name in ("phase", "sim", "p", "cells", "handler", "cache")
                if hasattr(context, name)
            },
            caches=caches,
            work=len(getattr(context, "work", ())),
            helper_calls=len(getattr(context, "helper_calls", ())),
            full_raw_failed_owner_serialization_claimed=False,
        ),
    )


def test_first_step_issued_enabled_network_full_handoff(monkeypatch, tmp_path):
    """One changed-image issued-chain pilot; every numerical body is blocked."""
    from tests.unit import test_betse_native_init_dynamics_completion as completion_model

    h = _enabled_public_chain_inputs(monkeypatch, tmp_path)
    generator = completion_model.issued_synthetic_completion.__wrapped__(
        h, monkeypatch, tmp_path, native_molecules=True
    )
    started, prior, outcomes = time.monotonic(), None, []
    current, primary = None, None
    try:
        _chain_checkpoint(
            tmp_path,
            "prebirth-input",
            NS(
                stage="declared_synthetic_predecessor_inputs",
                before=h.predecessor._snapshot(h.upstream),
                p=h.p,
                cells=h.cells,
            ),
        )
        h = next(generator)
        original = h.completion_context
        phase, sim, cells, p, handler, cache = (
            original.phase,
            original.sim,
            original.cells,
            original.p,
            original.handler,
            original.phase.cache,
        )
        assert p.molecules_enabled is True and p.grn_enabled is False
        assert original.request.native_molecules and original.molecule_record.source_completed
        _chain_checkpoint(tmp_path, "completion", original)
        for name, api, owner, declaration in (
            ("storage", stage.previous.storage, h.completion_owner, "from_dynamics"),
            ("electrical", stage.previous, None, "from_storage"),
            ("first_step", stage, None, "from_electrical"),
        ):
            request = getattr(api, declaration)(
                owner if owner is not None else prior, law_id=api.LAW_ID
            )
            try:
                prior = api.prepare(request, enabled=True)
            except BaseException as error:
                current = api._CONSUMED.get(request)
                raise error
            current = api._authority(prior)
            assert all(
                getattr(current, field) is value
                for field, value in (
                    ("phase", phase),
                    ("sim", sim),
                    ("cells", cells),
                    ("p", p),
                    ("handler", handler),
                    ("cache", cache),
                )
            )
            _chain_checkpoint(tmp_path, name, current)
            outcomes.append(dict(stage=name, owner=id(prior), trial=current.trial.identity))
        assert current.iteration_complete and current.selected_stopped and not current.loop_returned
        assert (
            current.source_time_label is h.calendar[0] or current.source_time_label == h.calendar[0]
        )
        assert current.loop_visits == 2 and len(sim.vm_time) == 1
        assert (
            h.completion_context.molecule.validate_runtime(current.molecule_claim, child=current)
            is current.molecule_record
        )
        assert p.molecules_enabled is True and p.grn_enabled is False
        software.snapshot.write_json(
            tmp_path / "issued-chain.json",
            dict(
                status="completed",
                elapsed_seconds=time.monotonic() - started,
                outcomes=outcomes,
                seams=h.seams,
                native_or_scientific_credit=0,
                molecules_enabled=p.molecules_enabled,
                grn_enabled=p.grn_enabled,
                one_input=True,
                replay_work_is_not_independent_cases=True,
            ),
        )
    except BaseException as error:
        primary = error
        try:
            if current is None:
                # Recover only an actual request/consumption association from
                # our public issuers, never arbitrary error.partial metadata.
                for api, field in (
                    (completion_model.stage, "completion_request"),
                    (completion_model.stage.previous, "dynamics_request"),
                    (retained_guards.stage, "request"),
                ):
                    attempted = vars(h).get(field)
                    if type(attempted) is api.Request and attempted in api._REQUESTS:
                        retained = api._CONSUMED.get(attempted)
                        if retained is not None and retained.request is attempted:
                            current = retained
                            break
            if current is not None:
                _chain_checkpoint(tmp_path, "failure", current, error=error)
        except BaseException as capture:
            software.snapshot.write_json(
                tmp_path / "failure-capture.json",
                dict(
                    primary=dict(type=type(error).__name__, message=str(error)),
                    capture=dict(type=type(capture).__name__, message=str(capture)),
                    full_raw_failed_owner_serialization_claimed=False,
                ),
            )
        raise
    finally:
        try:
            generator.close()
        except BaseException as cleanup:
            if primary is None:
                raise
            software.snapshot.write_json(
                tmp_path / "fixture-cleanup-error.json",
                dict(
                    primary=dict(type=type(primary).__name__, message=str(primary)),
                    cleanup=dict(type=type(cleanup).__name__, message=str(cleanup)),
                ),
            )
