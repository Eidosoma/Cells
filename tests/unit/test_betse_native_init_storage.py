"""Source/observer metadata only; actual constructor/RNG/operator entry held."""

import ast
import os
import sys
from contextlib import contextmanager
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_storage as stage
from tests.unit import test_betse_native_init_dynamics_completion as completion_model
from tests.unit import test_betse_native_init_retained_world as retained_guards
from validation.betse import betse_native_init_storage_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit native-blocked software release required")
    if (
        request.node.originalname == software.ISSUED_CHAIN_TEST
        and os.environ.get(software.ISSUED_CHAIN_RELEASE) != "1"
    ):
        pytest.skip("Explicit immutable issued-chain software mode required before setup")
    namespace = dict(vars(retained_guards), software=software, _RAW_GUARDS=[])
    function = FunctionType(retained_guards.blocked.__wrapped__.__code__, namespace)
    with contextmanager(function)(request, tmp_path, monkeypatch):
        yield


@pytest.fixture
def synthetic_init_inputs(monkeypatch, tmp_path):
    """Configure the declared source-test seams BEFORE any real issuer runs."""
    h = completion_model.synthetic_init_inputs.__wrapped__(monkeypatch, tmp_path)

    def namespace(context):
        original = h.factories["Simulator"].clear_storage

        def forbidden_zeros(*args, **kwargs):
            pytest.fail("The issued transport model cannot execute an actual zeros operator")

        context.original, context.numpy = original, context.parent.numpy
        context.zeros = context.numpy.zeros
        context.zero_wrapper = forbidden_zeros
        context.numpy_view = NS(zeros=forbidden_zeros)
        context.namespace = {
            "__name__": __name__,
            "__builtins__": __builtins__,
            "np": context.numpy_view,
        }
        context.namespace_keys = tuple(context.namespace)
        context.method = FunctionType(
            original.__code__,
            context.namespace,
            original.__name__,
            original.__defaults__,
            original.__closure__,
        )
        context.expected_body = context.method.__code__
        context.allowed_codes = frozenset((context.expected_body,))
        context.runtime_functions = (type(context.sim).clear_storage,)

    # Readiness/acquisition are declared synthetic fixture seams. The public
    # issuers, retirement, ancestor checks, original runtime wrapper, dispatch,
    # sealing and owner registries remain the production implementations.
    monkeypatch.setattr(stage, "_ready", lambda: stage.previous)
    monkeypatch.setattr(stage, "_namespace", namespace)
    monkeypatch.setattr(stage.previous, "_storage_api", lambda: stage)
    monkeypatch.setenv(stage.RELEASE, "1")
    return h


issued_synthetic_completion = completion_model.issued_synthetic_completion


def test_issued_dynamics_to_storage_public_chain(issued_synthetic_completion, tmp_path):
    h = issued_synthetic_completion
    original = h.completion_context
    parent_trial = original.trial
    sim, phase, cells, p = original.sim, original.phase, original.cells, original.p
    prior = dict(vars(sim))
    request = stage.from_dynamics(h.completion_owner, law_id=stage.LAW_ID)
    owner = stage.prepare(request, enabled=True)
    child = stage._authority(owner)
    assert type(owner) is stage.StorageOwner and stage._ISSUED[owner][0] is child
    assert child.parent is original and original.trial is parent_trial
    assert child.phase is phase and child.sim is sim and child.cells is cells and child.p is p
    assert stage.previous._STORAGE_FORWARDED[h.completion_owner] is child
    assert original.init_parent.storage_initial_lease.transition is child
    assert original.init_parent.storage_initial_lease.original_lease is (
        original.init_parent.completion_initial_lease
    )
    assert child.dispatched and child.body_returned and len(child.work) == 1
    assert child.wrapper_claim.f_back is child.driver_frame
    assert child.body_frame.f_back is child.body_driver
    assert sim.vm_time == [] and "vm_time" not in prior
    assert all(vars(sim)[name] is value for name, value in prior.items())
    assert child.trial.source_completed and child.trial.stores == ()
    assert not child.helper_calls  # This synthetic body exercises no original zeros.
    with pytest.raises(stage.previous.CompletionRejected) as consumed:
        stage.previous._authority(h.completion_owner)
    assert consumed.value.stage == "storage_forwarded"
    with pytest.raises(stage.StorageRejected) as repeated:
        stage.prepare(request, enabled=True)
    assert repeated.value.stage == "consumed"
    software.snapshot.write_json(
        tmp_path / "public-issued-storage.json",
        dict(
            public_issuers=(
                "INIT.from_seed/prepare",
                "Prelude.from_init/prepare",
                "Completion.from_prelude/prepare",
                "Storage.from_dynamics/prepare",
            ),
            actual_owner_and_original_runtime_dispatch=True,
            actual_phase_p_cells_sim_handler_cache_preserved=True,
            original_trials_and_irreversible_ancestor_leases_preserved=True,
            no_manual_owner_or_registry_insertion=True,
            explicit_seams=(
                *h.seams,
                "Key synthetic tissue provider/body and stream labels",
                "pre-birth declared storage readiness/acquisition",
                "synthetic clear_storage creates one empty history only",
            ),
            original_52_stores_zeros_RNG_or_native_source_executions=0,
            physical_checkpoint_or_completed_INIT_credit=False,
        ),
    )


def test_whole_original_52_store_body_and_duplicate_are_retained():
    plan = stage.source_plan()
    assert plan["lines"] == (1680, 1786)
    assert len(plan["stores"]) == 52
    assert len({name for _, name in plan["stores"]}) == 51
    assert sum(name == "vm_ave_time" for _, name in plan["stores"]) == 2
    assert plan["parameter_reads"] == (
        "Ca_dyn",
        "deformation",
        "grn_enabled",
        "is_ecm",
        "molecules_enabled",
    )
    assert plan["actual_source_RNG_operator_reference_or_scientific_release"] is False


def test_original_code_is_whole_module_compiled_without_execution():
    code = stage._code()
    assert type(code) is CodeType
    assert code.co_name == "clear_storage" and code.co_qualname == "Simulator.clear_storage"
    assert code.co_filename == str(stage.NATIVE / stage.SIM_FILE)


def test_optional_ca_guard_is_not_repaired_into_ion_conditional():
    node = stage._node()
    branch = next(
        n for n in ast.walk(node) if isinstance(n, ast.If) and ast.unparse(n.test) == "p.Ca_dyn"
    )
    assert ast.unparse(branch.body[0]) == "self.endo_retic.clear_cache()"
    assert "ions_dict" not in ast.unparse(branch.test)


def test_two_unconditional_flux_zeros_keep_native_call_and_return_defaults():
    node = stage._node()
    first = [n for n in node.body if isinstance(n, ast.Assign)][:2]
    assert [ast.unparse(n) for n in first] == [
        "self.fluxes_mem = np.zeros(self.fluxes_mem.shape)",
        "self.fluxes_gj = np.zeros(self.fluxes_gj.shape)",
    ]
    assert all(not n.value.keywords for n in first)


@pytest.mark.parametrize("entry", ("ready", "request", "prepare"))
def test_unavailable_real_parent_contract_refuses_before_foreign_owner_read(entry, monkeypatch):
    monkeypatch.setattr(stage, "PARENT_REVIEW_SHA256", None)

    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No foreign owner inspection before actual producer adoption")

    with pytest.raises(stage.StorageRejected) as caught:
        if entry == "ready":
            stage._ready()
        elif entry == "request":
            stage.from_dynamics(Foreign(), law_id=stage.LAW_ID)
        else:
            monkeypatch.setenv(stage.RELEASE, "1")
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "held"


def test_raw_storage_owner_cannot_be_constructed_or_hydrated():
    with pytest.raises(TypeError):
        stage.StorageOwner()
    with pytest.raises(TypeError):
        stage.StorageOwner.__reduce_ex__(object.__new__(stage.StorageOwner), 4)


@pytest.mark.parametrize("name", ("phase", "trial"))
def test_raw_unissued_storage_handle_has_no_usable_owner_access(name):
    owner = object.__new__(stage.StorageOwner)
    with pytest.raises(stage.StorageRejected) as caught:
        getattr(owner, name)
    assert caught.value.stage == "owner"


def test_first_raw_store_survives_failed_observation_append():
    old, new = object(), object()
    failure = OSError("metadata append refused")

    class Fails:
        def append(self, value):
            raise failure

    context = NS(
        pending_store=(1, "time", old, True),
        sim=NS(time=new),
        stores=Fails(),
        capture_error=None,
        capture_errors=(),
    )
    stage._finish_pending_store(context)
    assert context.last_store == (1, "time", old, new, True, True)
    assert context.capture_error is failure
    assert context.capture_errors[0][2] is context.last_store


def test_unwind_store_witness_keeps_original_raw_fields_without_completed_claim():
    old = object()
    context = NS(pending_store=(1, "time", old, True), sim=NS(time=old), stores=[])
    stage._finish_pending_store(context, normal=False)
    assert context.stores[0] == (1, "time", old, old, True, False)


def test_missing_native_optional_attribute_stays_missing_for_original_failure():
    context = NS(optional_lines={12: "endo_retic"}, sim=NS())
    stage._optional_line(context, NS(f_lineno=12))
    assert not hasattr(context.sim, "endo_retic")


@pytest.mark.parametrize("field", ("molecules", "grn", "endo_retic"))
def test_present_unowned_optional_cache_cannot_execute_a_supplied_delegate(field):
    calls = []

    class Foreign:
        def clear_cache(self):
            calls.append("foreign")

    context = NS(
        optional_lines={12: field},
        sim=NS(**{field: Foreign()}),
        entry_error=None,
        invalid=False,
        stage="metadata",
        request=None,
    )
    with pytest.raises(stage.StorageRejected) as caught:
        stage._optional_line(context, NS(f_lineno=12))
    assert caught.value is context.entry_error and context.invalid
    assert calls == []


def test_capture_error_is_separate_from_existing_primary_cause():
    primary = ValueError("original")
    cause = RuntimeError("cause")
    primary.__cause__ = cause
    capture = OSError("metadata")
    context = NS(primary=primary, capture_error=None, capture_errors=())
    stage._capture(context, "metadata", capture, primary)
    assert context.primary is primary and context.primary.__cause__ is cause
    assert context.capture_error is capture


def test_storage_boundary_does_not_add_voltage_time_vector_or_serialization_calls():
    code = stage._code()
    assert not {
        "update_V",
        "_plot_loop",
        "run_sim_core",
        "pickle",
        "linspace",
        "init_dynamics",
    } & set(code.co_names)


def test_source_run_still_uses_the_actual_original_simulator_method():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_run")
    assert ast.unparse(run.body[-1]) == "return context.sim.clear_storage(context.cells, context.p)"


def test_native_body_remains_blocked_in_the_reused_runner():
    frame = NS(f_globals={"__name__": "cells.processes.betse_native_init_storage_source"})
    assert software.is_forbidden_frame(frame)


def test_closed_validation_reserves_before_callbacks_and_caught_reentry_stays_poisoned():
    context = NS(active=False, invalid=False, validating=False)
    stage._reserve_validation(context)
    assert context.validating
    with pytest.raises(stage.StorageRejected) as caught:
        stage._reserve_validation(context)
    assert context.invalid and caught.value.partial is context
    context.validating = False  # model cleanup only, never a real owner reset
    with pytest.raises(stage.StorageRejected):
        stage._reserve_validation(context)


def test_failed_raw_holder_capture_retains_attempt_not_previous_store():
    failure = RuntimeError("dictionary observation refused")

    class Holder:
        @property
        def __dict__(self):
            raise failure

    prior = object()
    context = NS(
        pending_store=(1, "time", None, False),
        sim=Holder(),
        stores=[],
        last_store=prior,
        capture_error=None,
        capture_errors=(),
    )
    stage._finish_pending_store(context, normal=False)
    assert context.last_store is prior
    assert context.capture_error is failure
    assert context.last_capture[2] is context.last_store_attempt
    assert context.last_store_attempt[2] is False


def test_body_entry_capture_failure_stops_before_any_source_admission(monkeypatch):
    frame = sys._getframe()
    capture = OSError("attempt append refused")
    sentinel = RuntimeError("stop before body")

    class Fails:
        def append(self, value):
            raise capture

    context = NS(work=Fails(), capture_error=None, capture_errors=())

    def check(actual):
        assert actual.capture_error is capture
        raise sentinel

    monkeypatch.setattr(stage, "_check", check)
    with pytest.raises(RuntimeError) as caught:
        stage._observe(context, frame, "call", None)
    assert caught.value is sentinel
    assert context.last_attempt["frame"] is frame
    assert context.last_attempt["body_started"] is False


def test_unwind_exception_retention_failure_preserves_original_primary_and_cause():
    frame = sys._getframe()
    primary = ValueError("actual source primary")
    primary.__cause__ = TypeError("original cause")
    capture = OSError("pending capture refused")

    class Fails:
        def __setitem__(self, key, value):
            raise capture

    context = NS(
        frames={id(frame): dict(frame=frame)},
        pending=Fails(),
        primary=None,
        capture_error=None,
        capture_errors=(),
    )
    stage._observe(context, frame, "exception", (type(primary), primary, None))
    assert context.primary is primary and context.primary.__cause__ is primary.__cause__
    assert context.capture_error is capture
    assert context.last_source_error == (frame, primary)


def test_storage_private_observer_preserves_exact_reused_functions_and_namespace():
    context = NS()
    stage._observer_recipe(context)
    before = stage._observer_bindings(context)
    stage.previous._same_refs(stage._observer_bindings(context), before)
    assert context.observer_namespace is not vars(stage.previous.previous)
    assert context.observer_namespace["_guard"] is stage._guard
    assert context.observer_namespace["_check"] is stage._check
    assert context.observer_namespace["_ACTIVE"] is stage._ACTIVE
    assert context.account is context.observer_account


@pytest.mark.parametrize(
    "change",
    ("check", "guard", "epoch", "recover_hooks", "drop", "extra", "account", "code", "keyword"),
)
def test_storage_private_observer_drift_refuses_before_any_foreign_callback(change, monkeypatch):
    context, calls = NS(), []
    stage._observer_recipe(context)
    before = stage._observer_bindings(context)

    def foreign(*args, **kwargs):
        calls.append((args, kwargs))

    namespace = context.observer_namespace
    if change in ("check", "guard", "epoch", "recover_hooks"):
        namespace["_" + change] = foreign
    elif change == "drop":
        del namespace["_epoch"]
    elif change == "extra":
        namespace["foreign"] = foreign
    elif change == "account":
        context.account = foreign
    elif change == "code":
        function = namespace["_inherited"]
        monkeypatch.setattr(function, "__code__", function.__code__.replace(co_name="retargeted"))
    else:
        function = namespace["_inherited"]
        monkeypatch.setattr(function, "__kwdefaults__", {"hidden_delegate": foreign})
    with pytest.raises(ValueError):
        stage.previous._same_refs(stage._observer_bindings(context), before)
    assert calls == []


@pytest.mark.parametrize("change", ("same", "helper", "code", "keyword", "checker"))
def test_storage_original_checker_authenticates_live_helper_atoms_before_use(change, monkeypatch):
    # Independent metadata checker only; this is not an issued owner context.
    atoms = retained_guards.guards.stage._independent_atoms
    original = stage._optional_line
    context = NS(
        atoms=atoms,
        checker=(atoms, atoms.__code__, atoms.__globals__),
        metadata=(("_optional_line", original, atoms(original)),),
    )
    calls = []

    def foreign(*args, **kwargs):
        calls.append((args, kwargs))

    if change == "helper":
        monkeypatch.setattr(stage, "_optional_line", foreign)
    elif change == "code":
        monkeypatch.setattr(original, "__code__", original.__code__.replace(co_name="retargeted"))
    elif change == "keyword":
        monkeypatch.setattr(original, "__kwdefaults__", {"hidden_delegate": foreign})
    elif change == "checker":
        context.atoms = foreign
    if change == "same":
        stage._bootstrap(context)
    else:
        with pytest.raises(ValueError):
            stage._bootstrap(context)
    assert calls == []


@pytest.mark.parametrize(
    "case",
    (
        "ordinary",
        "issued_chain",
        "ordinary_long",
        "chain_without_long",
        "bool_seconds",
        "too_long",
        "unknown_seconds",
        "empty_selector",
        "foreign_selector",
    ),
)
def test_storage_explicit_software_mode_cannot_widen_unknown_work_or_ordinary_limits(case):
    class Foreign:
        def __eq__(self, other):
            pytest.fail("A foreign selector cannot authorize the long mode")

    requests = {
        "ordinary": ("test_storage_private_observer", 480, True),
        "issued_chain": (software.ISSUED_CHAIN_TEST, 7200, True),
        "ordinary_long": ("test_storage_private_observer", 7200, False),
        "chain_without_long": (software.ISSUED_CHAIN_TEST, 480, False),
        "bool_seconds": (software.ISSUED_CHAIN_TEST, True, False),
        "too_long": (software.ISSUED_CHAIN_TEST, 7201, False),
        "unknown_seconds": (software.ISSUED_CHAIN_TEST, 1800, False),
        "empty_selector": ("", 480, False),
        "foreign_selector": (Foreign(), 7200, False),
    }
    selector, seconds, allowed = requests[case]
    if allowed:
        assert software._integration_policy(selector, seconds) == seconds
    else:
        with pytest.raises(ValueError):
            software._integration_policy(selector, seconds)


def test_storage_chain_mode_does_not_allow_an_unissued_or_inspection_transport_frame(monkeypatch):
    monkeypatch.setenv(software.ISSUED_CHAIN_RELEASE, "1")
    frame = NS(
        f_globals={"__name__": "cells.processes.betse_native_init_storage"},
        f_code=NS(co_name="_run"),
    )
    assert software.is_forbidden_frame(frame)


def test_storage_chain_mode_keeps_actual_acquisition_and_literal_bodies_blocked(monkeypatch):
    monkeypatch.setenv(software.ISSUED_CHAIN_RELEASE, "1")
    for module, name in (
        ("cells.processes.betse_native_init_storage", "_namespace"),
        ("cells.processes.betse_native_init_storage_source", "clear_storage"),
    ):
        frame = NS(f_globals={"__name__": module}, f_code=NS(co_name=name))
        assert software.is_forbidden_frame(frame)


def test_storage_chain_mode_needs_the_actual_retained_transport_function_frame(monkeypatch):
    monkeypatch.setenv(software.ISSUED_CHAIN_RELEASE, "1")
    monkeypatch.setattr(
        software, "_MODEL_RUN_BINDING", (stage._run, stage._run.__code__, vars(stage))
    )
    assert software._issued_model_driver(sys._getframe()) is False


@pytest.mark.parametrize("normal", (True, False), ids=("normal", "unwind"))
@pytest.mark.parametrize("site", ("witness", "store_capture"))
def test_storage_return_capture_entry_failure_retains_raw_primary_and_cause(
    normal, site, monkeypatch
):
    frame = sys._getframe()
    primary, cause = ValueError("source error"), TypeError("source cause")
    primary.__cause__ = cause
    capture = OSError("return observation entry refused")

    def fail(*args, **kwargs):
        raise capture

    monkeypatch.setattr(stage.previous.previous.previous, "_normal_return", lambda f: normal)
    if site == "store_capture":
        monkeypatch.setattr(stage, "_finish_pending_store", fail)
    context = NS(
        frames={id(frame): dict(frame=frame, returned=False)},
        primary=None,
        pending={} if normal else {id(frame): primary},
        observer_namespace={"_witness": fail if site == "witness" else lambda *a: None},
        pending_store=None,
        raw_returns=[],
        locals={},
        capture_error=None,
        capture_errors=(),
    )
    stage._observe(context, frame, "return", None)
    assert context.last_raw == (frame, None)
    assert context.raw_returns == [(frame, None)] and id(frame) in context.locals
    assert context.capture_error is capture
    assert context.primary is (None if normal else primary)
    if not normal:
        assert context.primary.__cause__ is cause
        assert context.pending[id(frame)] is primary
    assert context.body_returned is normal
    assert context.return_classification is normal


def test_storage_delivered_parent_source_and_exact_callbacks_are_bound_without_calling_them():
    assert stage._ready() is stage.previous
    assert stage.PARENT_SOURCE_SHA256 == software.snapshot.digest(
        stage.Path(stage.previous.__file__)
    )
    assert stage.previous.STORAGE_INTERFACE_SHA256 is None
    assert stage.previous.STORAGE_REVIEW_SHA256 is None


@pytest.mark.parametrize("mutation", ("code", "keyword"))
def test_storage_parent_live_callback_drift_refuses_before_invocation(mutation, monkeypatch):
    original = stage.previous._claim_for_init_storage
    if mutation == "code":
        monkeypatch.setattr(original, "__code__", original.__code__.replace(co_name="retargeted"))
    else:
        monkeypatch.setattr(original, "__kwdefaults__", {"hidden_delegate": object()})
    with pytest.raises(stage.StorageRejected) as caught:
        stage._ready()
    assert caught.value.stage == "hook"


def test_storage_linked_provider_refuses_before_reading_its_target(tmp_path, monkeypatch):
    link = tmp_path / "linked-producer.py"
    link.symlink_to(stage.previous.__file__)
    original, reads = stage.Path.read_bytes, []

    def read(path):
        if path == link:
            reads.append(path)
            pytest.fail("A linked provider cannot be read as source authority")
        return original(path)

    with monkeypatch.context() as patch:
        patch.setattr(stage.previous, "__file__", str(link))
        patch.setattr(stage.Path, "read_bytes", read)
        with pytest.raises(stage.StorageRejected) as caught:
            stage._ready()
    assert caught.value.stage == "producer" and reads == []


@pytest.mark.parametrize("change", ("replace", "code"))
def test_storage_driver_guard_helper_retarget_refuses_before_a_foreign_callback(
    change, monkeypatch
):
    calls = []

    def foreign(frame):
        frame.f_globals["foreign_calls"].append(frame)
        return True

    monkeypatch.setenv(software.ISSUED_CHAIN_RELEASE, "1")
    monkeypatch.setattr(software, "_MODEL_RUN_BINDING", object())
    if change == "replace":
        monkeypatch.setattr(software, "_issued_model_driver", foreign)
    else:
        # Keep the same object and global holder while retargeting its code.
        monkeypatch.setattr(software._issued_model_driver, "__code__", foreign.__code__)
    frame = NS(
        f_globals={"__name__": "cells.processes.betse_native_init_storage", "foreign_calls": calls},
        f_code=NS(co_name="_run"),
    )
    assert software.is_forbidden_frame(frame)
    assert calls == []


def test_storage_actual_cli_blacklist_adapter_preserves_both_hooks_without_issuing(tmp_path):
    """The real -m runner globals/closures, with no owner or native entry."""
    before = sys.getprofile(), sys.gettrace()
    assert before[0] is not None
    with completion_model.monitored_public_model_guard(tmp_path) as monitor:
        assert sys.getprofile() is None and sys.gettrace() is None
        assert monitor.reserved
    assert sys.getprofile() is before[0] and sys.gettrace() is before[1]
    assert not stage._ACTIVE


def test_electrical_unbound_successor_refuses_before_any_foreign_owner_inspection():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No owner inspection or fabricated ancestor before actual adoption")

    with pytest.raises(stage.StorageRejected) as caught:
        stage._claim_for_electrical(
            Foreign(), expected=Foreign(), transition=Foreign(), entries=Foreign()
        )
    assert caught.value.stage == "electrical_held"


@pytest.mark.parametrize("change", ("allowed", "retained_history", "other_object", "signed_zero"))
def test_electrical_projection_excludes_only_selected_simulator_fields(change, monkeypatch):
    from cells.processes import betse_native_single_cell_poisson_observation as observation

    # A private codec model, never inserted into an owner or retirement registry.
    sim, other = NS(vm=-1.0, vm_time=[3], retained=-0.0), NS(vm=-1.0)
    objects = (("Simulator", sim), ("Other", other))
    lease = NS(
        objects=objects,
        holders=tuple(vars(actual) for _, actual in objects),
        names=tuple(tuple(vars(actual)) for _, actual in objects),
        fields=[{}, {}],
        allowed=frozenset(("vm",)),
    )
    lease.view = NS(objects=objects, fields=lease.fields)
    context = NS(sim=sim, parent=NS(init_parent=object()), electrical_lease=lease)
    scope = observation.Scope()
    monkeypatch.setattr(stage.previous, "_scope", lambda ignored: scope)
    monkeypatch.setattr(
        stage.previous.previous.previous, "_projector", lambda actual: NS(objects=list(objects))
    )
    before = stage._electrical_values(context)
    sim.vm = 2.0
    if change == "retained_history":
        sim.vm_time.append(4)
    elif change == "other_object":
        other.vm = 2.0
    elif change == "signed_zero":
        sim.retained = 0.0
    after = stage._electrical_values(context)
    assert (before.identity == after.identity) is (change == "allowed")


@pytest.fixture
def electrical_callback_model():
    from types import ModuleType

    module, calls = ModuleType("declared_metadata_callbacks_not_an_owner"), []
    vars(module).update(calls=calls)

    # Independent callback bodies: source-identical replacement objects can
    # have equal code/global holders yet must never replace a proved slot.
    # Use a no-closure template with the module's retained call list.
    def template(value):
        value.append("called")

    claim = FunctionType(template.__code__, vars(module), "claim")
    check = FunctionType(template.__code__, vars(module), "check")
    module.claim, module.check = claim, check
    binding = stage._ElectricalBinding(
        object(),
        module,
        claim,
        check,
        (stage._electrical_atoms(claim), stage._electrical_atoms(check)),
    )
    function = FunctionType(
        stage._check_electrical_binding.__code__,
        dict(
            vars(stage),
            previous=module,
            ELECTRICAL_ANCESTOR_CLAIM="claim",
            ELECTRICAL_ANCESTOR_CHECK="check",
        ),
    )
    return NS(module=module, calls=calls, binding=binding, validate=function)


def test_electrical_proved_callback_binding_preserves_unchanged_invocation(
    electrical_callback_model,
):
    h = electrical_callback_model
    h.validate(h.binding)
    h.binding.claim(h.calls)
    h.validate(h.binding)
    assert h.calls == ["called"]


@pytest.mark.parametrize("target", ("claim", "check"))
@pytest.mark.parametrize("change", ("replace", "code", "keyword"))
def test_electrical_post_proof_callback_retarget_refuses_without_invocation(
    electrical_callback_model, target, change, monkeypatch
):
    h = electrical_callback_model
    h.validate(h.binding)
    function = getattr(h.module, target)
    if change == "replace":
        setattr(h.module, target, FunctionType(function.__code__, vars(h.module), target))
    elif change == "code":
        monkeypatch.setattr(function, "__code__", function.__code__.replace(co_name="retargeted"))
    else:
        monkeypatch.setattr(function, "__kwdefaults__", {"delegate": object()})
    with pytest.raises(ValueError):
        h.validate(h.binding)
    assert h.calls == []


@pytest.mark.parametrize("falsey", (False, True))
def test_electrical_binding_refusal_keeps_first_primary_and_secondary_capture(falsey):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary = (Falsey if falsey else ValueError)("original entry rejected")
    primary.__cause__ = RuntimeError("original cause")
    secondary = OSError("post-proof slot replaced")
    context, child = NS(entry_error=primary, invalid=False), NS(entry_error=None, invalid=False)
    assert stage._retain_electrical_failure(context, child, secondary) is primary
    assert context.electrical_error is primary
    assert context.electrical_error.__cause__ is primary.__cause__
    assert context.electrical_capture_error == (secondary, primary)
    assert context.invalid and child.invalid


def test_electrical_binding_rejects_an_inspection_object_before_attribute_callbacks():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("No foreign binding attribute or callback may be consulted")

    with pytest.raises(ValueError, match="ancestor slot changed"):
        stage._check_electrical_binding(Foreign())


@pytest.mark.parametrize("slot", ("claim", "check", "unchanged"))
def test_electrical_acquisition_rejects_foreign_slots_before_atom_inspection(slot, tmp_path):
    from types import ModuleType

    path = tmp_path / "declared_electrical_callback_metadata.py"
    path.write_text(
        "def claim(context):\n    calls.append('claim')\n    return context\n"
        "def check(context):\n    calls.append('check')\n    return context\n"
    )
    code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    module = ModuleType("declared_callback_metadata_not_an_issued_owner")
    module.__file__ = str(path)
    module.calls, module._pin = [], lambda value: type(value) is str and len(value) == 64
    for item in code.co_consts:
        if type(item) is CodeType:
            setattr(module, item.co_name, FunctionType(item, vars(module), item.co_name))
    inspected, sampled, proof = [], [], []

    class Foreign:
        def __getattribute__(self, name):
            inspected.append(name)
            raise AssertionError("Foreign callback attributes must not be inspected")

    if slot != "unchanged":
        setattr(module, slot, Foreign())

    def atoms(function):
        sampled.append(function)
        assert type(function) is FunctionType
        return stage._electrical_atoms(function)

    class ConsumerProofBoundary(Exception):
        pass

    def consumer_proof(payload):
        proof.append(payload)
        raise ConsumerProofBoundary("Admitted callbacks reached the separate consumer proof")

    # Only the acquisition function is cloned into declared metadata inputs.
    # Production pins stay closed; no owner, issuer, or registry is created.
    acquire = FunctionType(
        stage._electrical_api.__code__,
        dict(
            vars(stage),
            previous=module,
            _ready=lambda: module,
            _electrical_atoms=atoms,
            _electrical_binding=consumer_proof,
            ELECTRICAL_INTERFACE_SHA256="1" * 64,
            ELECTRICAL_REVIEW_SHA256="2" * 64,
            ELECTRICAL_PARENT_REVIEW_SHA256="3" * 64,
            ELECTRICAL_ANCESTOR_CLAIM="claim",
            ELECTRICAL_ANCESTOR_CHECK="check",
            # Existing frozen bytes only reach the stop-at-proof sentinel;
            # this does not construct or authenticate an electrical consumer.
            ELECTRICAL_MODULE=stage.source.__name__,
        ),
    )
    if slot == "unchanged":
        with pytest.raises(ConsumerProofBoundary):
            acquire()
        assert sampled == [module.claim, module.check] and len(proof) == 1
    else:
        with pytest.raises(stage.StorageRejected) as caught:
            acquire()
        assert caught.value.stage == "electrical_ancestor"
        assert sampled == ([] if slot == "claim" else [module.claim])
        assert proof == []
    assert inspected == [] and module.calls == []


def test_first_step_Key_contract_is_closed_without_inspecting_a_parent():
    assert stage.FIRST_STEP_ANCESTOR_CLAIM is stage.FIRST_STEP_ANCESTOR_CHECK is None
    with pytest.raises(stage.StorageRejected) as caught:
        stage._first_step_key_api()
    assert caught.value.stage == "first_step_ancestor_held"


@pytest.mark.parametrize("slot", ("claim", "check"))
def test_first_step_Key_acquisition_type_admission_precedes_atom_callbacks(slot, tmp_path):
    from types import ModuleType

    path = tmp_path / "declared_first_step_Key_metadata.py"
    path.write_text("def claim(*args):\n    pass\ndef check(*args):\n    pass\n")
    code = compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
    module = ModuleType("declared_Key_metadata_not_an_owner")
    module.__file__ = str(path)
    for item in code.co_consts:
        if type(item) is CodeType:
            setattr(module, item.co_name, FunctionType(item, vars(module), item.co_name))
    inspected, sampled = [], []

    class Foreign:
        def __getattribute__(self, name):
            inspected.append(name)
            raise AssertionError("No foreign Key slot inspection")

    setattr(module, slot, Foreign())

    def atoms(function):
        assert type(function) is FunctionType
        sampled.append(function)
        return stage._electrical_atoms(function)

    acquire = FunctionType(
        stage._first_step_key_api.__code__,
        dict(
            vars(stage),
            previous=module,
            _ready=lambda: module,
            FIRST_STEP_ANCESTOR_CLAIM="claim",
            FIRST_STEP_ANCESTOR_CHECK="check",
            _electrical_atoms=atoms,
        ),
    )
    with pytest.raises(ValueError, match="typed Key"):
        acquire()
    assert inspected == [] and len(sampled) == int(slot == "check")
