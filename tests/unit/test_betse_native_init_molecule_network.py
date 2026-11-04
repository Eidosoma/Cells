"""Original source preparation and closed declaration controls; no native work."""

import ast
import builtins
import sys
from abc import ABCMeta
from collections.abc import MutableMapping
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_molecule_network as stage
from tests.unit import test_betse_native_init_dynamics_completion as inherited
from validation.betse import betse_native_init_molecule_network_software as runner


@pytest.fixture(autouse=True)
def native_blocked(request, tmp_path, monkeypatch):
    original = inherited.inherited._blocked_generator
    guard = FunctionType(
        original.__code__,
        dict(original.__globals__, stage=NS(**vars(stage), _ACTIVE=[]), runner=runner),
    )
    generator = guard(request, tmp_path, monkeypatch)
    before, started, primary = (sys.getprofile(), sys.gettrace()), False, None
    failed = len(stage._FAILED)
    try:
        next(generator)
        started = True
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        # This family has no execution mode in its blocked runner. No source
        # body/constructor/session is made by any of these controls.
        drain = inherited.inherited.cleanup._drain_guard
        FunctionType(
            drain.__code__, dict(drain.__globals__, _write_failure_diagnostics=lambda *args: None)
        )(generator, started, (), tmp_path, required_hooks=before, primary=primary)
        assert len(stage._FAILED) == failed


def test_every_original_method_compiles_in_whole_module_context_without_evaluation(tmp_path):
    plan = stage.source_plan()
    assert plan["original"]["whole_module_context"]
    assert plan["original"]["methods"]["MasterOfMolecules.__init__"] == (32, 40)
    assert plan["original"]["methods"]["MasterOfMolecules.read_mol_config"] == (113, 198)
    assert plan["original"]["methods"]["MasterOfNetworks.__init__"] == (64, 117)
    assert plan["original"]["methods"]["MasterOfNetworks.read_substances"] == (120, 303)
    for role, name in stage.source.SITES:
        code = stage.source.code(role, name)
        assert type(code) is CodeType and code.co_name == name
        assert code.co_filename == str(stage.source.NATIVE / stage.source.SITES[(role, name)])
        assert code.co_qualname == (name if role is None else role + "." + name)
        assert type(stage.source.defaults(role, name)) is tuple
    runner.snapshot.write_json(tmp_path / "original-source-plan.json", plan)


def test_original_constructor_read_and_native_nested_setup_order_are_preserved():
    node = stage.source.node("MasterOfMolecules", "read_mol_config")
    text = ast.unparse(node)
    assert text.index("self.core = MasterOfNetworks") < text.index("self.core.time_dila")
    assert text.index("self.core.read_substances") < text.index("self.core.tissue_init")
    assert text.index("self.core.tissue_init") < text.index("self.core.read_reactions")
    assert text.index("self.core.read_reactions") < text.index("self.core.read_transporters")
    assert text.index("self.core.read_transporters") < text.index("self.core.read_channels")
    assert text.index("self.core.read_channels") < text.index("self.core.read_modulators")
    assert text.index("self.core.read_modulators") < text.index("set_net_opts")
    assert "config_dic = p.network_config" in text


def test_original_constructor_only_joins_path_without_creating_storage():
    node = stage.source.node("MasterOfMolecules", "__init__")
    text = ast.unparse(node)
    assert "pathnames.join(p.init_pickle_dirname, 'GeneralNetwork.betse')" in text
    assert not any(
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in ("open", "eval", "exec")
        for value in ast.walk(node)
    )


def test_unbound_source_route_refuses_before_foreign_claim_or_owner_inspection():
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("Unreviewed source cannot inspect a supplied owner")

    with pytest.raises(stage.MoleculeNetworkRejected) as caught:
        stage.bind_completion(Foreign(), original_owner=Foreign())
    assert caught.value.stage == "held"


def test_runtime_storage_fields_are_derived_from_the_original_clear_cache():
    fields = stage._runtime_field_table("storage")
    assert fields["MasterOfNetworks"] == {"chi_time", "vmit_time"}
    assert fields["Molecule"] == {"c_mems_time", "c_cells_time", "c_env_time", "c_mit_time"}
    assert fields["Transporter"] == {"flux_time"}
    assert fields["Reaction"] == {"rate_time"}
    assert "Simulator" not in fields


def test_runtime_step_fields_include_native_material_and_sampled_histories():
    fields = stage._runtime_field_table("first_step")
    assert {"c_cells", "c_env", "cc_at_mem", "f_mem", "f_gj", "flux_intra"} <= fields["Molecule"]
    assert {"c_cells_time", "c_env_time", "c_mems_time"} <= fields["Molecule"]
    assert {"extra_rho_cells", "extra_rho_env", "extra_J_mem", "delta_conc", "chi"} <= fields[
        "MasterOfNetworks"
    ]
    assert {"cc_cells", "cc_env", "extra_rho_cells", "extra_Jenv_x"} <= fields["Simulator"]
    assert "dt" not in fields["Simulator"]


@pytest.mark.parametrize("kind", (None, "reload", "first_step ", True))
def test_runtime_unknown_epoch_refuses_before_source_or_owner_access(kind):
    with pytest.raises(ValueError, match="Exact molecular runtime epoch"):
        stage._runtime_field_table(kind)


@pytest.mark.parametrize(
    "entry",
    (
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "finish_runtime",
        "validate_runtime",
    ),
)
def test_runtime_record_dictionary_or_unissued_handle_is_never_authority(entry):
    function = getattr(stage, entry)
    with pytest.raises(stage.MoleculeNetworkRejected) as caught:
        if entry in ("finish_runtime", "validate_runtime"):
            function({}, child={})
        else:
            function({})
    assert caught.value.stage == "runtime_claim"


@pytest.fixture
def runtime_entry_model():
    """Private source-frame control only; no issued claim or owner is made."""
    entered = []

    class Core:
        def clear_cache(self):
            entered.append("clear_cache")

        def clear_run_loop(self, sim):
            entered.append("clear_run_loop")

        def run_loop(self, phase, t):
            entered.append("run_loop")

    core = Core()
    original = NS(
        core=core,
        sim=NS(),
        phase=NS(),
        p=NS(),
        cells=NS(),
        mom=NS(transporters=None, channels=None),
        dynamic_callbacks=(),
        source_functions=(Core.clear_cache, Core.clear_run_loop, Core.run_loop),
        functions={
            ("MasterOfNetworks", name): getattr(Core, name)
            for name in ("clear_cache", "clear_run_loop", "run_loop")
        },
        objects=(("MasterOfNetworks", core),),
    )
    child = NS(loop_frame=None, body_frame=None, frames={}, methods={})
    runtime = NS(
        original=original,
        child=child,
        kind="first_step",
        top_calls=[],
        frames={},
        expressions=[],
        invalid=False,
        primary=None,
    )

    def execute(sequence, *, phase=None, clock=None, foreign_parent=False):
        # These are actual profiled Python frames for explicitly synthetic
        # no-arithmetic functions, not stand-ins in a production registry.
        prior = sys.getprofile()

        def profile(frame, event, arg):
            if prior is not None:
                prior(frame, event, arg)
            if event == "call" and any(
                frame.f_code is fn.__code__ for fn in original.source_functions
            ):
                stage._runtime_entry(runtime, frame)

        def intermediary(function, *args):
            return function(*args)

        def source_root(t):
            child.body_frame = child.loop_frame = sys._getframe()
            for name in sequence:
                method = getattr(core, name)
                args = (
                    (original.sim,)
                    if name == "clear_run_loop"
                    else (
                        (original.phase if phase is None else phase, t if clock is None else clock)
                        if name == "run_loop"
                        else ()
                    )
                )
                if foreign_parent:
                    intermediary(method, *args)
                else:
                    method(*args)

        try:
            sys.setprofile(profile)
            source_root(object())
        finally:
            sys.setprofile(prior)

    return runtime, entered, execute


def test_runtime_actual_profiled_source_order_and_exact_arguments(runtime_entry_model):
    runtime, entered, execute = runtime_entry_model
    execute(("clear_run_loop", "run_loop"))
    assert runtime.top_calls == entered == ["clear_run_loop", "run_loop"]
    assert not runtime.invalid and runtime.primary is None


@pytest.mark.parametrize(
    "sequence",
    (
        ("run_loop",),
        ("clear_run_loop", "clear_run_loop"),
        ("clear_run_loop", "run_loop", "run_loop"),
    ),
)
def test_runtime_duplicate_or_omitted_top_level_source_stops_before_body(
    runtime_entry_model, sequence
):
    runtime, entered, execute = runtime_entry_model
    with pytest.raises(stage.MoleculeNetworkRejected, match="Duplicate, omitted") as caught:
        execute(sequence)
    assert entered == list(sequence[:-1])
    assert runtime.invalid and runtime.primary is caught.value


@pytest.mark.parametrize("drift", ("phase", "clock", "parent"))
def test_runtime_foreign_phase_clock_or_parent_refuses_before_delegate(runtime_entry_model, drift):
    runtime, entered, execute = runtime_entry_model
    kwargs = (
        {"phase": object()}
        if drift == "phase"
        else {"clock": object()}
        if drift == "clock"
        else {"foreign_parent": True}
    )
    with pytest.raises(stage.MoleculeNetworkRejected) as caught:
        execute(("clear_run_loop", "run_loop"), **kwargs)
    assert caught.value is runtime.primary
    assert entered == ([] if drift == "parent" else ["clear_run_loop"])


def test_runtime_storage_profiled_duplicate_cannot_reset_cache_twice(runtime_entry_model):
    runtime, entered, execute = runtime_entry_model
    runtime.kind = "storage"
    with pytest.raises(stage.MoleculeNetworkRejected, match="Duplicate, omitted"):
        execute(("clear_cache", "clear_cache"))
    assert runtime.top_calls == entered == ["clear_cache"]


@pytest.mark.parametrize("drift", ("none", "sim", "cells", "p", "phase", "t", "parent"))
def test_runtime_profiled_reached_helper_binds_positional_and_keyword_owners(drift):
    """NR-2: actual Python helper frames, no native or numerical bodies."""
    entered = []
    owners = NS(sim=object(), cells=object(), p=object(), phase=object())

    def molecule_mover(sim, cells, p, *, phase, t):
        entered.append((sim, cells, p, phase, t))

    original = NS(
        sim=owners.sim,
        cells=owners.cells,
        p=owners.p,
        phase=owners.phase,
        source_functions=(molecule_mover,),
        dynamic_callbacks=(),
        functions={},
    )
    child = NS(loop_frame=None, frames={}, methods={})
    runtime = NS(
        kind="first_step",
        original=original,
        child=child,
        frames={},
        expressions=[],
        primary=None,
        invalid=False,
    )
    before = sys.getprofile()

    def profile(frame, event, arg):
        if before is not None:
            before(frame, event, arg)
        if event == "call" and frame.f_code is molecule_mover.__code__:
            stage._runtime_entry(runtime, frame)

    def intermediary(args, kwargs):
        molecule_mover(*args, **kwargs)

    def source_root(t):
        child.loop_frame = sys._getframe()
        values = dict(sim=owners.sim, cells=owners.cells, p=owners.p, phase=owners.phase, t=t)
        if drift in values:
            values[drift] = object()
        args = values["sim"], values["cells"], values["p"]
        kwargs = dict(phase=values["phase"], t=values["t"])
        if drift == "parent":
            intermediary(args, kwargs)
        else:
            molecule_mover(*args, **kwargs)

    try:
        sys.setprofile(profile)
        if drift == "none":
            source_root(object())
            assert len(entered) == 1 and not runtime.invalid
        else:
            with pytest.raises(stage.MoleculeNetworkRejected):
                source_root(object())
            assert not entered and runtime.invalid
    finally:
        sys.setprofile(before)


def test_configured_transporter_refuses_before_any_source_work(declaration, monkeypatch):
    assert stage._configuration(declaration) is declaration.p.network_config
    rows = [{"name": "declared-transporter", "reactant": "X", "product": "Y"}]
    declaration.p.network_config["transporters"] = rows
    monkeypatch.setattr(
        stage, "_actual_functions", lambda *args: pytest.fail("No native acquisition")
    )
    with pytest.raises(stage.MoleculeNetworkRejected) as caught:
        stage._configuration(declaration)
    assert caught.value.stage == "transporter_owner"
    assert declaration.p.network_config["transporters"] is rows
    assert declaration.p.molecules_enabled is True


@pytest.mark.parametrize("unwind", (False, True))
@pytest.mark.parametrize("falsey", (False, True))
def test_runtime_raw_none_precedes_secondary_audit_capture(monkeypatch, unwind, falsey):
    class Marker:
        pass

    class Falsey(ValueError):
        def __bool__(self):
            return False

    claim, child, frame = Marker(), object(), sys._getframe()
    primary = (Falsey if falsey else ValueError)("original synthetic unwind")
    primary.__cause__ = LookupError("original cause")
    capture = OSError("separate observer failure")
    runtime = NS(
        child=child,
        active=True,
        original=NS(initial=NS(_normal_return=lambda f: not unwind)),
        primary=None,
        pending={id(frame): primary} if unwind else {},
        capture_error=None,
        capture_errors=(),
        last_raw=None,
    )
    monkeypatch.setattr(stage, "MoleculeRuntimeClaim", Marker)
    monkeypatch.setattr(stage, "_RUNTIME", {claim: runtime})
    monkeypatch.setattr(stage, "_runtime_observer", lambda *args: None)

    def audit(value):
        assert value is runtime and value.last_raw == (frame, None)
        raise capture

    monkeypatch.setattr(stage, "_runtime_route", audit)
    if unwind:
        stage.observe_runtime(claim, child=child, frame=frame, event="return", arg=None)
        assert runtime.primary is primary and primary.__cause__.args == ("original cause",)
    else:
        with pytest.raises(stage.CaptureStop) as caught:
            stage.observe_runtime(claim, child=child, frame=frame, event="return", arg=None)
        assert caught.value.__cause__ is capture
        assert runtime.primary is None
    assert runtime.last_raw == (frame, None) and runtime.capture_error is capture


@pytest.mark.parametrize("event", ("c_call", "c_return", "c_exception"))
def test_runtime_c_event_model_retains_descriptor_without_calling_it(monkeypatch, event):
    class Marker:
        pass

    claim, child, frame = Marker(), object(), sys._getframe()
    runtime = NS(
        child=child,
        active=True,
        frames={id(frame): dict(frame=frame)},
        work=[],
        c_calls=[],
        primary=None,
        capture_error=None,
        capture_errors=(),
    )
    monkeypatch.setattr(stage, "MoleculeRuntimeClaim", Marker)
    monkeypatch.setattr(stage, "_RUNTIME", {claim: runtime})
    monkeypatch.setattr(stage, "_runtime_observer", lambda *args: None)
    monkeypatch.setattr(stage, "_runtime_route", lambda value: value)
    stage.observe_runtime(claim, child=child, frame=frame, event=event, arg=len)
    assert runtime.c_calls == [(frame, event, len)]
    assert not runtime.work and runtime.primary is None


def test_runtime_observation_rejects_foreign_reporting_frame_before_work():
    runtime = NS(child=NS(observer_namespace={}), invalid=False, primary=None)
    with pytest.raises(stage.MoleculeNetworkRejected, match="actual original child observer"):
        stage._runtime_observer(runtime, sys._getframe(), sys._getframe(), "call", None)
    assert runtime.invalid and runtime.primary is not None


@pytest.mark.parametrize("which", ("setup", "runtime"))
def test_source_call_refusal_stays_latched_before_a_caller_could_catch_it(monkeypatch, which):
    primary = ValueError("declared channel entry refusal")
    context = NS(invalid=False, entry_error=None, primary=None)

    def rejected(*args):
        raise primary

    def call():
        if which == "setup":
            return stage.observe(
                object(), completion_claim=object(), frame=sys._getframe(), event="call", arg=None
            )
        return stage.observe_runtime(
            claim, child=object(), frame=sys._getframe(), event="call", arg=None
        )

    if which == "setup":
        monkeypatch.setattr(stage, "_context", lambda *args: context)
        monkeypatch.setattr(stage, "_observe_event", rejected)
    else:
        claim = object.__new__(stage.MoleculeRuntimeClaim)
        monkeypatch.setitem(stage._RUNTIME, claim, context)
        monkeypatch.setattr(stage, "_runtime_observer", rejected)
    with pytest.raises(ValueError) as caught:
        call()
    assert caught.value is primary
    assert context.invalid and context.entry_error is primary and context.primary is primary


@pytest.mark.parametrize("falsey", (False, True))
def test_runtime_exception_ledger_failure_retains_source_primary_and_cause(monkeypatch, falsey):
    class Marker:
        pass

    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary = (Falsey if falsey else ValueError)("actual exception event")
    primary.__cause__ = OSError("original cause")
    capture = MemoryError("pending ledger")

    class Ledger(dict):
        def __setitem__(self, key, value):
            raise capture

    claim, child, frame = Marker(), object(), sys._getframe()
    runtime = NS(
        child=child,
        active=True,
        primary=None,
        pending=Ledger(),
        source_exceptions=[],
        capture_error=None,
        capture_errors=(),
    )
    monkeypatch.setattr(stage, "MoleculeRuntimeClaim", Marker)
    monkeypatch.setattr(stage, "_RUNTIME", {claim: runtime})
    stage.observe_runtime(
        claim, child=child, frame=frame, event="exception", arg=(type(primary), primary, None)
    )
    assert runtime.last_source_error == (frame, primary)
    assert runtime.primary is primary and primary.__cause__.args == ("original cause",)
    assert runtime.capture_error is capture


def test_runtime_c_unwind_capture_defers_then_preserves_original_exception(monkeypatch):
    class Marker:
        pass

    primary, capture = ValueError("original C failure"), OSError("observer I/O failure")
    primary.__cause__ = LookupError("original cause")
    claim, child, frame = Marker(), object(), sys._getframe()
    runtime = NS(
        child=child,
        active=True,
        primary=None,
        primary_origin=None,
        pending={},
        source_exceptions=[],
        capture_error=None,
        capture_errors=(),
    )
    monkeypatch.setattr(stage, "MoleculeRuntimeClaim", Marker)
    monkeypatch.setattr(stage, "_RUNTIME", {claim: runtime})
    monkeypatch.setattr(stage, "_runtime_observer", lambda *args: None)

    def audit(value):
        raise capture

    monkeypatch.setattr(stage, "_runtime_route", audit)
    stage.observe_runtime(claim, child=child, frame=frame, event="c_exception", arg=len)
    assert runtime.primary is None and runtime.capture_error is capture
    stage.observe_runtime(
        claim, child=child, frame=frame, event="exception", arg=(ValueError, primary, None)
    )
    assert runtime.primary is primary and primary.__cause__.args == ("original cause",)


def test_runtime_capture_loss_stops_the_next_source_callback(monkeypatch):
    class Marker:
        pass

    claim, child, frame = Marker(), object(), sys._getframe()
    primary, capture = ValueError("retained native error"), OSError("lost capture")
    runtime = NS(
        child=child,
        active=True,
        primary=primary,
        primary_origin="source",
        capture_error=capture,
        capture_errors=(),
    )
    monkeypatch.setattr(stage, "MoleculeRuntimeClaim", Marker)
    monkeypatch.setattr(stage, "_RUNTIME", {claim: runtime})
    monkeypatch.setattr(stage, "_runtime_observer", lambda *args: None)
    monkeypatch.setattr(stage, "_runtime_route", lambda value: value)
    with pytest.raises(stage.CaptureStop):
        stage.observe_runtime(claim, child=child, frame=frame, event="line", arg=None)
    assert runtime.primary is primary and runtime.capture_error is capture


@pytest.mark.parametrize(
    "drift", ("none", "builtin_shadow", "helper_copy", "code", "missing", "text")
)
def test_runtime_expression_metadata_binds_effective_globals_without_evaluation(drift):
    def forbidden(*args, **kwargs):
        pytest.fail("No original/generated expression or helper execution")

    library = ModuleType("declared_no_call_expression_library")
    library.zeros = forbidden
    namespace = dict(__builtins__=vars(builtins), np=library)
    method = FunctionType((lambda: None).__code__, namespace)
    text = "np.zeros(1) + float(2)"
    code = compile(text, "<string>", "eval", dont_inherit=True)
    probe = FunctionType(code, namespace)
    owner = NS(gad_eval_string=text)
    runtime = NS(
        original=NS(
            functions={("MasterOfNetworks", "run_loop"): method},
            initial=NS(
                core=NS(previous=NS(_same=inherited.stage.previous.previous.core.previous._same))
            ),
        ),
        expressions=((owner, "gad_eval_string", text, code),),
        expression_bindings=((probe, stage._function_bindings(probe)),),
    )
    stage._runtime_expressions(runtime)
    if drift == "none":
        return
    if drift == "builtin_shadow":
        namespace["float"] = forbidden
    elif drift == "helper_copy":
        library.zeros = FunctionType(forbidden.__code__, forbidden.__globals__)
    elif drift == "code":
        probe.__code__ = compile("np.zeros(2)", "<string>", "eval", dont_inherit=True)
    elif drift == "missing":
        runtime.expression_bindings = ()
    else:
        owner.gad_eval_string = text + " "
    with pytest.raises(ValueError):
        stage._runtime_expressions(runtime)


@pytest.mark.parametrize("drift", ("none", "backing", "value", "order", "missing", "key"))
def test_runtime_mapping_model_preserves_original_backing_order_and_shared_slots(drift):
    first, second = object(), object()
    mapping = dict(Na=first, K=second, duplicate=first)
    owner = NS(_key_to_dynamic_value=mapping)
    runtime = NS(dynamic_maps=((owner, mapping, tuple(mapping.items())),))
    stage._runtime_mappings(runtime)
    if drift == "none":
        assert mapping["Na"] is mapping["duplicate"]
        return
    if drift == "backing":
        owner._key_to_dynamic_value = dict(mapping)
    elif drift == "value":
        mapping["Na"] = second
    elif drift == "order":
        value = mapping.pop("Na")
        mapping["Na"] = value
    elif drift == "missing":
        mapping.pop("K")
    else:
        mapping["other"] = mapping.pop("Na")
    with pytest.raises(ValueError, match="dynamic keys/order/slot aliases"):
        stage._runtime_mappings(runtime)


@pytest.fixture
def declaration():
    config = {
        "implement network": True,
        "biomolecules": [],
        "reactions": None,
        "transporters": None,
        "channels": None,
        "modulators": None,
    }
    p = NS(
        _run_sim=False,
        molecules_enabled=True,
        network_config=config,
        _conf={"general network": config},
    )
    return NS(
        p=p,
        phase=NS(kind=NS(name="INIT")),
        sim=NS(molecules=None),
        request=NS(native_molecules=True),
    )


def test_actual_configuration_association_contract_accepts_declared_shape_without_owner(
    declaration,
):
    assert stage._configuration(declaration) is declaration.p.network_config
    assert declaration.sim.molecules is None


@pytest.mark.parametrize(
    "drift", ["copied_config", "flag", "route", "phase", "run_sim", "existing"]
)
def test_foreign_route_and_configuration_refuse_after_valid_declaration_baseline(
    declaration, drift
):
    assert stage._configuration(declaration) is declaration.p.network_config
    if drift == "copied_config":
        declaration.p.network_config = dict(declaration.p.network_config)
    elif drift == "flag":
        declaration.p.network_config["implement network"] = False
    elif drift == "route":
        declaration.request.native_molecules = False
    elif drift == "phase":
        declaration.phase.kind.name = "SIM"
    elif drift == "run_sim":
        declaration.p._run_sim = True
    else:
        declaration.sim.molecules = object()
    with pytest.raises(stage.MoleculeNetworkRejected):
        stage._configuration(declaration)


@pytest.mark.parametrize(
    "branch", ["channels", "transporters", "modulators", "optimizer", "asymmetry", "growth"]
)
def test_unowned_declared_branch_is_refused_without_toggle_or_default_substitution(
    declaration, branch
):
    config = declaration.p.network_config
    if branch == "channels":
        config[branch] = [{"channel class": "Ca", "channel type": "unowned", "apply to": "all"}]
    elif branch in ("modulators", "transporters"):
        config[branch] = [{"declared": True}]
    elif branch == "optimizer":
        config["optimization"] = {"optimize network": True}
    elif branch == "asymmetry":
        config["biomolecules"] = [{"initial asymmetry": "gradient_x"}]
    else:
        config["biomolecules"] = [{"growth and decay": {"modulator function": "periodic"}}]
    with pytest.raises(stage.MoleculeNetworkRejected):
        stage._configuration(declaration)
    assert declaration.p.molecules_enabled is True
    assert (
        declaration.p.network_config is config and config is declaration.p._conf["general network"]
    )


def test_missing_original_configuration_field_keeps_raw_failure(declaration):
    del declaration.p.network_config["biomolecules"]
    with pytest.raises(KeyError) as caught:
        stage._configuration(declaration)
    assert caught.value.args == ("biomolecules",)


def test_slots_and_records_do_not_supply_live_session_authority():
    for value in (None, {}, NS(), object.__new__(stage.MoleculeSession)):
        with pytest.raises(stage.MoleculeNetworkRejected) as caught:
            stage.validate_active(value, completion_claim=None)
        assert caught.value.stage == "session"


def test_native_mutable_mapping_uses_the_original_abc_metaclass_without_instantiation():
    class DeclaredMapping(MutableMapping):
        pass

    assert type(DeclaredMapping) is ABCMeta
    stage._class_header(DeclaredMapping, "DynamicValueDict")


def test_original_entry_requires_no_outer_wrapper_and_never_invokes_a_function():
    def body():
        pytest.fail("No helper/source/factory execution")

    assert stage._source_entry(body, body) is body


def test_spoofed_wrapped_attribute_cannot_authenticate_foreign_outer_factory_code():
    def original():
        pytest.fail("No source entry")

    def foreign():
        pytest.fail("No foreign wrapper entry")

    foreign.__wrapped__ = original
    with pytest.raises(stage.MoleculeNetworkRejected) as caught:
        stage._source_entry(foreign, original)
    assert caught.value.stage == "wrapper_prerequisite"


@pytest.mark.parametrize("drift", ["plain_mapping", "wrong_base", "foreign_metaclass"])
def test_wrong_native_constructor_header_refuses_without_allocating_any_instance(drift):
    role = "DynamicValueDict"
    if drift == "plain_mapping":
        cls = type("Plain", (), {})
    elif drift == "wrong_base":

        class WrongBase(dict):
            pass

        cls = WrongBase
    else:

        class Foreign(type):
            pass

        cls, role = Foreign("Foreign", (), {}), "Molecule"
    with pytest.raises(ValueError, match="base/metaclass"):
        stage._class_header(cls, role)


def _synthetic_reader(sim, self):
    # Only this test function creates these synthetic metadata closures. Their
    # getters/setters are NEVER called and grant no original source authority.
    return (
        lambda index=0: sim.buffer[index],
        lambda value, index=0: sim.buffer.__setitem__(index, value),
    )


def _synthetic_context():
    initial = inherited.stage.previous.previous
    sim, core = NS(buffer=[1, 2]), NS()
    get, set_ = _synthetic_reader(sim, core)
    context = NS(
        sim=sim,
        core=core,
        initial=initial,
        functions={("MasterOfNetworks", "read_substances"): _synthetic_reader},
        frames={},
        dynamic_callbacks=[],
        dynamic_maps=[],
    )
    return context, get, set_


def test_closure_association_and_cached_lookup_bindings_are_read_without_calling():
    context, get, set_ = _synthetic_context()
    before = list(context.sim.buffer)
    bindings = stage._callback_pair(context, (get, set_))
    assert len(bindings) == 2 and bindings[0][0] is get and bindings[1][0] is set_
    assert context.sim.buffer == before


@pytest.mark.parametrize("drift", ["owner", "code", "globals", "builtins"])
def test_foreign_callback_authority_refuses_without_evaluating_the_callback(drift):
    context, get, set_ = _synthetic_context()
    assert stage._callback_pair(context, (get, set_))
    if drift == "owner":
        get, _ = _synthetic_reader(NS(buffer=context.sim.buffer), context.core)
    elif drift == "code":
        get.__code__ = get.__code__.replace(co_consts=(None, "foreign"))
    else:
        namespace = dict(get.__globals__)
        if drift == "builtins":
            namespace["__builtins__"] = dict(get.__builtins__)
            foreign = FunctionType(get.__code__, namespace, closure=get.__closure__)
            # Restoring the module dictionary cannot replace FunctionType's
            # cached builtins association.
            namespace["__builtins__"] = get.__builtins__
        else:
            foreign = FunctionType(get.__code__, namespace, closure=get.__closure__)
        get = foreign
    with pytest.raises(ValueError):
        stage._callback_pair(context, (get, set_))


@pytest.mark.parametrize("drift", ["builtin_shadow", "defaults", "closure"])
def test_effective_function_binding_drift_is_observable_without_calling(drift, monkeypatch):
    def declared(owner):
        return lambda item=1: len(owner.items[item])

    fn = declared(NS(items=[1, 2]))
    fn = FunctionType(
        fn.__code__, dict(fn.__globals__), argdefs=fn.__defaults__, closure=fn.__closure__
    )
    before = stage._function_bindings(fn)
    if drift == "builtin_shadow":
        monkeypatch.setitem(fn.__globals__, "len", lambda *args: pytest.fail("must not call"))
        with pytest.raises(ValueError, match="builtin was shadowed"):
            stage._function_bindings(fn)
        return
    elif drift == "defaults":
        fn.__defaults__ = tuple([1])
    else:
        fn.__closure__[0].cell_contents = NS(items=[1, 2])
    after = stage._function_bindings(fn)
    assert len(before) != len(after) or any(a is not b for a, b in zip(before, after, strict=True))


def test_cached_foreign_builtins_refuse_after_the_original_namespace_value_is_restored():
    def source():
        return len(())

    namespace = dict(source.__globals__, __builtins__=dict(vars(builtins)))
    private = FunctionType(source.__code__, namespace)
    namespace["__builtins__"] = vars(builtins)
    with pytest.raises(ValueError, match="cached builtin/namespace"):
        stage._function_bindings(private)


@pytest.mark.parametrize(
    "lookup",
    [
        "Molecule",
        "Reaction",
        "Transporter",
        "DynamicValue",
        "DynamicValueDict",
        "numpy",
        "set_net_opts",
    ],
)
def test_source_factory_lookup_is_bound_to_actual_class_and_helper_objects(lookup):
    # Isolated association contract, without constructor/owner issuance.
    classes = {
        name: type(name, (), {})
        for name in (
            "MasterOfMolecules",
            "MasterOfNetworks",
            "Molecule",
            "Reaction",
            "Transporter",
            "DynamicValue",
            "DynamicValueDict",
        )
    }

    def body():
        pytest.fail("No source function body may run")

    namespace = dict(body.__globals__, **classes, np=object(), set_net_opts=body)
    funcs = {(role, "__init__"): FunctionType(body.__code__, namespace) for role in classes}
    funcs[("MasterOfMolecules", "read_mol_config")] = FunctionType(body.__code__, namespace)
    funcs[(None, "set_net_opts")] = body
    context = NS(classes=classes, functions=funcs, completion=NS(numpy=namespace["np"]))
    stage._class_associations(context)
    namespace["np" if lookup == "numpy" else lookup] = object()
    with pytest.raises(ValueError):
        stage._class_associations(context)


def _metadata_slots():
    class Slot:
        __slots__ = ("get_value", "set_value")

    class Mapping:
        pass

    context, get, set_ = _synthetic_context()
    slot = Slot()
    slot.get_value, slot.set_value = get, set_
    frame = NS()
    mapping = Mapping()
    raw = {"Na": slot, "duplicate": slot}
    mapping._key_to_dynamic_value = raw
    context.frames[id(frame)] = dict(returned=True)
    context.dynamic_callbacks = [
        (slot, get, set_, frame, stage._callback_pair(context, (get, set_)))
    ]
    context.dynamic_maps = [(mapping, raw, frame)]
    context.classes = dict(DynamicValue=Slot, DynamicValueDict=Mapping)
    context.objects = [("DynamicValue", slot), ("DynamicValueDict", mapping)]
    context.raw_returns = []
    return context, slot, mapping


def test_slot_mapping_projection_and_live_graph_keep_actual_aliases_without_getter(monkeypatch):
    context, slot, mapping = _metadata_slots()
    monkeypatch.setattr(stage, "_context", lambda *args: context)
    stage._dynamic_associations(context)
    roots = stage.graph_roots(None)
    assert roots["dynamic_slots"][0][0] is slot
    assert roots["mapping_edges"][0] == (mapping, mapping._key_to_dynamic_value)
    assert roots["mapping_edges"][0][1]["Na"] is roots["mapping_edges"][0][1]["duplicate"]
    values = stage.project_state(None, [mapping, slot])
    assert values[0]["original_dynamic_mapping"] == (
        ("Na", {"original_dynamic_value": 0}),
        ("duplicate", {"original_dynamic_value": 0}),
    )
    assert context.sim.buffer == [1, 2]


def test_repeated_graph_reads_keep_all_actual_graph_container_identities(monkeypatch):
    context, _, _ = _metadata_slots()
    monkeypatch.setattr(stage, "_context", lambda *args: context)
    roots = stage.graph_roots(None)
    view = NS(molecular=roots)
    tape = NS(rng=None, events=(), draws=(), locals={})
    graph = inherited.observation.callers._graph
    first = graph(view, view, tape)
    assert stage.graph_roots(None) is roots
    second = graph(view, view, tape)
    assert first[1] == second[1]
    assert len(first[0]) == len(second[0])
    assert all(a is b for a, b in zip(first[0], second[0], strict=True))


@pytest.mark.parametrize("kind", ["callback_rows", "mapping_rows"])
@pytest.mark.parametrize("change", ["replace", "omit"])
def test_graph_cannot_drop_or_replace_the_original_observed_constructor_rows(
    monkeypatch, kind, change
):
    context, _, _ = _metadata_slots()
    monkeypatch.setattr(stage, "_context", lambda *args: context)
    stage.graph_roots(None)
    rows = context.dynamic_callbacks if kind == "callback_rows" else context.dynamic_maps
    if change == "replace":
        rows[0] = tuple(list(rows[0]))
    else:
        rows.pop()
    with pytest.raises(ValueError, match="observation row was replaced or omitted"):
        stage.graph_roots(None)


@pytest.mark.parametrize("drift", ["getter", "setter", "backing", "defaults", "closure"])
def test_original_slots_map_and_callback_edges_reject_metadata_drift(drift):
    context, slot, mapping = _metadata_slots()
    stage._dynamic_associations(context)
    if drift == "getter":
        slot.get_value = lambda: pytest.fail("must not evaluate")
    elif drift == "setter":
        slot.set_value = lambda value: pytest.fail("must not evaluate")
    elif drift == "backing":
        mapping._key_to_dynamic_value = dict(mapping._key_to_dynamic_value)
    elif drift == "defaults":
        slot.get_value.__defaults__ = tuple([0])
    else:
        slot.get_value.__closure__[0].cell_contents = NS(buffer=context.sim.buffer)
    with pytest.raises(ValueError):
        stage._dynamic_associations(context)


@pytest.mark.parametrize("unwind", [False, True])
@pytest.mark.parametrize("returned", [None, "retained-success"])
def test_direct_raw_return_precedes_failing_capture_and_preserves_source_primary(
    monkeypatch, unwind, returned
):
    source_error, capture_error = LookupError("original source"), OSError("return capture")
    source_error.__cause__ = TypeError("original cause")

    class BrokenAppend(list):
        def append(self, value):
            raise capture_error

    frame = NS(f_globals={}, f_code=None)
    row = dict(frame=frame, globals=frame.f_globals, returned=False)
    context = NS(
        frames={id(frame): row},
        pending={id(frame): source_error} if unwind else {},
        initial=NS(_normal_return=lambda frame: not unwind),
        primary=None,
        raw_returns=BrokenAppend(),
        reader_frame=frame,
        reader_returned=False,
        last_raw=None,
        capture_error=None,
        capture_errors=(),
    )
    monkeypatch.setattr(stage, "_context", lambda *args: context)
    if unwind:
        stage.observe(None, completion_claim=None, frame=frame, event="return", arg=returned)
        assert context.primary is source_error
        assert context.primary.__cause__.args == ("original cause",)
    else:
        with pytest.raises(stage.CaptureStop) as caught:
            stage.observe(None, completion_claim=None, frame=frame, event="return", arg=returned)
        assert caught.value.__cause__ is capture_error
        assert context.primary is None
    assert context.last_raw == (frame, returned)
    assert context.capture_error is capture_error and row["returned"] is True


def test_foreign_entry_refusal_is_immediate_and_does_not_call_source_body(monkeypatch):
    error = PermissionError("entry refusal")
    context = NS(primary=None)
    monkeypatch.setattr(stage, "_context", lambda *args: context)

    def refuse(*args):
        raise error

    monkeypatch.setattr(stage, "_check", refuse)
    with pytest.raises(PermissionError) as caught:
        stage.observe(None, completion_claim=None, frame=NS(), event="call", arg=None)
    assert caught.value is error and context.primary is error
    assert context.invalid and context.entry_error is error


@pytest.mark.parametrize("name", ["sim", "cells", "p", "phase", "config_substances"])
def test_suspended_source_arguments_cannot_be_retargeted_by_an_inherited_observer(name):
    original = NS(epoch="actual retained association")
    row = dict(frame=NS(f_locals={name: original}), arguments=((name, original),), returned=False)
    stage._argument_links(None, row)
    row["frame"].f_locals[name] = NS(epoch=original.epoch)
    with pytest.raises(ValueError, match="argument/owner association"):
        stage._argument_links(None, row)


@pytest.mark.parametrize("where", ["reader", "factory", "reader_entry", "shared_outside"])
def test_shared_helpers_are_selected_by_actual_source_ancestry_only(where, monkeypatch):
    def reader():
        pytest.fail("No original source work")

    body, factory, reading = NS(f_back=None), NS(f_back=None), NS(f_back=None)
    frame = NS(f_back=None, f_code=(lambda: None).__code__)
    context = NS(
        reader_frame=reading,
        factory_frame=factory,
        completion=NS(body_frame=body),
        functions={("MasterOfMolecules", "read_mol_config"): reader},
    )
    if where == "reader":
        frame.f_back = reading
    elif where == "factory":
        frame.f_back = factory
    elif where == "reader_entry":
        frame.f_back, frame.f_code = body, reader.__code__
    monkeypatch.setattr(stage, "_context", lambda *args: context)
    assert stage.observes_source_frame(None, frame) is (where != "shared_outside")


@pytest.mark.parametrize("mode", ("outside", "source", "foreign_receiver", "returned_parent"))
def test_runtime_shared_helper_routing_uses_real_live_network_ancestry(monkeypatch, mode):
    observations, child = [], NS()

    def shared():
        return None

    class Core:
        def run_loop(self, phase, t):
            shared()

    core = Core()
    original = NS(
        core=core,
        source_functions=(Core.run_loop, shared),
        dynamic_callbacks=(),
        functions={("MasterOfNetworks", "run_loop"): Core.run_loop},
    )
    runtime = NS(original=original, frames={}, child=child)
    monkeypatch.setattr(stage, "_runtime_context", lambda claim: runtime)
    prior = sys.getprofile()

    def observe(frame, event, arg):
        if prior is not None:
            prior(frame, event, arg)
        if event == "call" and frame.f_code is Core.run_loop.__code__:
            admitted = stage.observes_runtime_frame(None, frame)
            observations.append(("master", admitted))
            if admitted:
                runtime.frames[id(frame)] = dict(frame=frame, returned=mode == "returned_parent")
        elif event == "call" and frame.f_code is shared.__code__:
            observations.append(("helper", stage.observes_runtime_frame(None, frame)))

    try:
        sys.setprofile(observe)
        if mode == "outside":
            shared()
            assert observations == [("helper", False)]
        else:
            Core.run_loop(Core() if mode == "foreign_receiver" else core, object(), object())
            assert observations == [
                ("master", mode != "foreign_receiver"),
                ("helper", mode == "source"),
            ]
    finally:
        sys.setprofile(prior)


@pytest.mark.parametrize("drift", (False, True))
def test_channel_constructor_lookup_is_bound_before_native_factory_work(drift):
    classes = {
        name: object()
        for name in (
            "MasterOfMolecules",
            "MasterOfNetworks",
            "Molecule",
            "Reaction",
            "Transporter",
            "DynamicValue",
            "DynamicValueDict",
            "Channel",
        )
    }

    def template():
        pytest.fail("No source body or constructor is released")

    namespace = dict(classes)
    if drift:
        namespace["Channel"] = object()
    reader = FunctionType(template.__code__, namespace)
    plot = FunctionType(template.__code__, {})
    original = FunctionType(
        template.__code__, dict(MasterOfNetworks=classes["MasterOfNetworks"], set_net_opts=plot)
    )
    context = NS(
        classes=classes,
        functions={
            ("MasterOfMolecules", "read_mol_config"): original,
            ("MasterOfNetworks", "read_channels"): reader,
            (None, "set_net_opts"): plot,
        },
    )
    if drift:
        with pytest.raises(ValueError, match="factory lookup changed: Channel"):
            stage._class_associations(context)
    else:
        stage._class_associations(context)
