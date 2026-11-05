"""Blocked orchestration protocols, never native parameter/phase/SIM owners."""

import os
import sys
from contextlib import contextmanager
from types import CodeType, FunctionType, ModuleType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_native_seed_demo as prior
from tests.unit import test_native_sim_demo_observation as observed
from validation.betse import native_seed_demo as demo
from validation.betse import native_sim_demo as stage
from validation.betse import native_sim_demo_software as software


@pytest.fixture(autouse=True)
def blocked(tmp_path):
    if os.environ.get(software.RELEASE) != "1":
        pytest.skip("Explicit blocked SIM orchestration software required")
    with software.blocked(tmp_path):
        yield


@contextmanager
def _import_context(model, role, enabled):
    assert enabled is True
    proof = model.proofs[role]
    model.point(role + ".enter")
    proof.active = True
    try:
        yield proof
    except BaseException as error:
        proof.primary = error
        raise
    finally:
        proof.active = False
        model.point(role + ".exit")
    proof.record = object()
    proof.published = True
    model.point(role + ".published")


# Public stdlib-decorated shape with source-corresponding, isolated bodies.
# Clone globals are explicitly synthetic and cannot issue native authority.
@contextmanager
def observing_runner_import(*, enabled=False):
    with _import_context(_model, "preparation", enabled) as context:
        yield context


@contextmanager
def observing_phase_import(*, enabled=False):
    with _import_context(_model, "assembly", enabled) as proof:
        yield proof


@contextmanager
def observing_runtime_import(*, enabled=False):
    with _import_context(_model, "run", enabled) as proof:
        yield proof


_model = None


def sim_chain(monkeypatch, *, mode="original", count=3, fail=None, mutate=None):
    synthetic_observer = observed.protocol(monkeypatch, mode=mode, count=count)
    model = prior.short_history_chain(mode=mode, count=2, natural=True)
    model.state.endpoint = model.plan["endpoint"] = "sim_terminal"
    model.sim_calls, model.sim_owners, model.proofs = [], {}, {}
    model.current_p = NS(sim_tsteps=count)
    model.current_owner = NS(parameters=model.current_p)
    model.current_pair = model.current_owner, model.current_p
    model.fail, model.mutate = fail, mutate
    model.secondary = OSError("secondary import failure")

    def point(name):
        model.sim_calls.append(name)
        if model.mutate is not None:
            model.mutate(model, name)
        if name == model.fail:
            raise model.primary

    model.point = point

    class Owner:
        def __init__(self, label, trial):
            self.label, self._trial, self.consumed = label, trial, False

        @property
        def trial(self):
            assert not self.consumed, "Consumed prior SIM owner reopened"
            point(self.label + ".trial")
            return self._trial

    def current(packet, output, *, packet_sha256, previous_owner, previous_parameters, enabled):
        point("current_parameters")
        assert enabled and packet == model.plan["parameter_packet"]
        assert packet_sha256 == model.plan["parameter_sha256"]
        assert previous_owner is model.ready and previous_parameters is model.p
        assert output.name == "current_parameters"
        assert model.state.init_terminal_completed
        assert all(row.published and not row.active for row in model.proofs.values())
        return model.current_pair

    parameter_api = ModuleType("metadata_parameter_api")
    vars(parameter_api).update(vars(model.modules["parameters"]))
    model.modules["parameters"] = parameter_api
    parameter_api.acquire_current_world_ready = current
    model.apis = {}
    for (role, public), template in zip(
        stage.IMPORTS,
        (observing_runner_import, observing_phase_import, observing_runtime_import),
        strict=True,
    ):
        module = ModuleType("metadata_SIM_" + role)
        module.__file__, module._model = __file__, model
        module._import_context = _import_context
        inner = FunctionType(template.__wrapped__.__code__, vars(module))
        inner.__kwdefaults__ = {"enabled": False}
        setattr(module, public, contextmanager(inner))
        module.LAW_ID = role
        model.apis[role] = module
        model.proofs[role] = NS(
            active=False,
            published=False,
            primary=None,
            capture_error=None,
            hooks_restored=True,
            monitor_restored=True,
            record=None,
        )

    def preparation_request(parent, *, current_parameters_owner, law_id):
        point("preparation.request")
        assert parent is model.history_objects[0][0]
        assert current_parameters_owner is model.current_owner and law_id == "preparation"
        assert model.state.sim_init_trial is model.history_objects[0][2]
        return NS(parent=parent, parameters=current_parameters_owner)

    def preparation(request, *, enabled):
        point("preparation.source")
        assert enabled and request.parent is model.state.sim_init_owner
        trial = NS(identity="a" * 64, source_completed=True, parameters_identity="b" * 64)
        owner = model.sim_owners["preparation"] = Owner("preparation", trial)
        return owner

    def assembly_request(parent, *, law_id):
        point("assembly.request")
        assert parent is model.sim_owners["preparation"] and not parent.consumed
        assert law_id == "assembly"
        return NS(parent=parent)

    def assembly(request, *, enabled):
        point("assembly.source")
        assert enabled
        request.parent.consumed = True
        trial = NS(
            identity="c" * 64,
            constructor_completed=True,
            preparation_identity=model.state.sim_preparation_trial.identity,
            terminal_identity=model.state.sim_init_trial.identity,
            parameters_identity="b" * 64,
        )
        owner = model.sim_owners["assembly"] = Owner("assembly", trial)
        return owner

    def run_request(parent, *, maximum, law_id):
        point("run.request")
        assert parent is model.sim_owners["assembly"] and not parent.consumed
        assert maximum == 512 and law_id == "run"
        request = NS(
            parent=parent,
            maximum=maximum,
            iterations=count,
            operator_mode=demo.HISTORY_OPERATOR_MODES[mode],
            init_identity=model.state.sim_init_trial.identity,
            assembly_identity=model.state.sim_assembly_trial.identity,
            parameters_identity="b" * 64,
            identity="d" * 64,
        )
        model.run_request = request
        point("run.request.return")
        return request

    def run(request, *, enabled):
        point("run.source")
        assert enabled
        request.parent.consumed = True
        rows = tuple(
            NS(
                ordinal=i,
                source_time=-0.0 if i == 0 else i * 0.0001,
                sampled=i % 2 == 0,
                after=prior.StepSnapshot(f"{i + 20:064x}", (i, b"\x80")),
                rng=(prior.StepSnapshot(f"{i + 1000:064x}", (i,)),),
                work_end=i + 1,
            )
            for i in range(count)
        )
        cache = prior.StepSnapshot("f" * 64, (-0.0, b"raw"))
        trial = NS(
            identity="e" * 64,
            request_identity=request.identity,
            assembly_identity=request.assembly_identity,
            init_identity=request.init_identity,
            current_parameters_identity=request.parameters_identity,
            operator_mode=request.operator_mode,
            iterations=rows,
            work=tuple(range(count)),
            report_returned=True,
            loop_returned=True,
            context_returned=True,
            before_native_pickle=True,
            before=cache,
            ready=(cache, object(), ()),
            after=(rows[-1].after, object(), ()),
            calendar=cache,
            sampled=cache,
            dt=0.0001,
            rng_before=(cache,),
            rng_after=(cache,),
        )
        owner = model.sim_owners["run"] = Owner("run", trial)
        _, cells, sim, _, callback, _ = model.state.init_links
        phase = NS(p=model.current_p, cells=cells, sim=sim, callbacks=callback)
        model.surface = dict(
            owner=owner,
            trial=trial,
            completed_INIT=model.state.sim_init_trial,
            constructor=model.state.sim_assembly_trial,
            old_p=model.p,
            current_p=model.current_p,
            sim=sim,
            cells=cells,
            callback=callback,
            phase=phase,
            before_native_pickle=True,
            operator_mode=request.operator_mode,
        )
        point("run.source.return")
        return owner

    def completed(owner):
        point("run.completed")
        assert owner is model.sim_owners["run"]
        return model.surface

    model.apis["preparation"].from_init = preparation_request
    model.apis["preparation"].prepare = preparation
    model.apis["preparation"].trial_record = lambda trial: dict(source_completed=True)
    model.apis["preparation"]._entry_guard = lambda function: function
    model.apis["assembly"].from_preparation = assembly_request
    model.apis["assembly"].prepare = assembly
    model.apis["assembly"].record_document = lambda trial: dict(constructor_completed=True)
    model.apis["run"].from_assembly = run_request
    model.apis["run"].prepare = run
    model.apis["run"].record_document = lambda trial: dict(iterations=len(trial.iterations))
    model.apis["run"].completed_sim = completed
    model.apis["run"].validate_sim = lambda owner: owner.trial
    original_bind = stage.observation.bind

    def bind(state, run_sha):
        original_bind(state, "c" * 64)
        synthetic_observer.state = state

    monkeypatch.setattr(stage.observation, "bind", bind)
    old_produce = synthetic_observer.produce

    def produce(owner, enabled, capture):
        synthetic_observer.owner = owner
        synthetic_observer.trial = model.state.sim_trial
        model.point("observation.source")
        return old_produce(owner, enabled, capture)

    synthetic_observer.produce = produce
    model.observation = synthetic_observer
    monkeypatch.setattr(stage, "_modules", lambda: model.apis)
    monkeypatch.setattr(stage, "_parameter_api", lambda module: module)
    monkeypatch.setattr(demo, "_sim_producer", lambda: stage)
    return model


@pytest.mark.parametrize("mode", demo.FLUX_MODES)
@pytest.mark.parametrize("count", (1, 3, 350, 512))
def test_sim_demo_complete_calendar_same_tissue_distinct_parameters(
    monkeypatch, tmp_path, mode, count
):
    model = sim_chain(monkeypatch, mode=mode, count=count)
    evidence = prior.Evidence()
    state = prior.execute(model, tmp_path, evidence)
    assert state.methods_completed and state.evidence_completed and state.sim_completed
    assert state.sim_time_steps_completed == count and state.init_time_steps_completed == 2
    assert state.init_terminal_completed and state.sim_init_trial is state.terminal_trial
    assert state.sim_current_pair is model.current_pair and state.parameters is model.p
    assert state.sim_phase is not state.init_phase
    assert (
        state.sim_phase.sim is state.init_phase.sim
        and state.sim_phase.cells is state.init_phase.cells
    )
    assert state.sim_phase.p is model.current_p and model.current_p is not model.p
    assert state.sim_imports_complete and state.sim_cleanup_complete
    calls = model.sim_calls
    assert calls[:3] == [role + ".enter" for role, _ in stage.IMPORTS]
    assert calls.index("preparation.published") < calls.index("current_parameters")
    assert calls.index("current_parameters") < calls.index("preparation.source")
    assert calls.index("assembly.source") < calls.index("run.source")
    saved = dict(evidence.values)
    assert saved["sim_run.linkage"]["configured_iterations"] == count
    assert saved["sim_run.linkage"]["operator_mode"] == demo.HISTORY_OPERATOR_MODES[mode]
    assert saved[f"sim_run.iteration.{count - 1:04d}.after"] is state.sim_trial.iterations[-1].after
    assert saved["sim_run.stream_after"] is state.sim_trial.rng_after
    assert all(row["generator"].gi_frame is None for row in state.sim_imports)


@pytest.mark.parametrize(
    "where",
    (
        "current_parameters",
        "preparation.request",
        "preparation.source",
        "assembly.request",
        "assembly.source",
        "run.request",
        "run.source",
        "run.completed",
    ),
)
@pytest.mark.parametrize("falsey", (False, True))
def test_sim_demo_stage_failures_keep_complete_INIT_and_original_error(
    monkeypatch, tmp_path, where, falsey
):
    model = sim_chain(monkeypatch, fail=where)
    primary = prior.Falsey("original") if falsey else ValueError("original")
    cause = OSError("original cause")
    primary.__cause__ = cause
    model.primary = primary
    evidence = prior.Evidence()
    with pytest.raises(type(primary)) as raised:
        prior.execute(model, tmp_path, evidence)
    state = model.state
    assert raised.value is primary and primary.__cause__ is cause
    assert state.primary is primary and not state.sim_completed and not state.methods_completed
    assert state.sim_time_steps_completed == 0
    assert state.sim_init_trial is state.terminal_trial and state.sim_init_trial.source_completed
    assert state.sim_init_owner is model.history_objects[0][0]
    assert model.sim_calls[-1] == where
    assert dict(evidence.values)["sim_failure.INIT.identity"] == state.terminal_trial.identity


@pytest.mark.parametrize("where", ("preparation", "assembly", "run"))
def test_sim_demo_trial_survives_record_capture_failure(monkeypatch, tmp_path, where):
    model = sim_chain(monkeypatch)
    evidence = prior.Evidence(fail="sim_" + where + ".record")
    with pytest.raises(ValueError, match="Typed observation refused"):
        prior.execute(model, tmp_path, evidence)
    attr = "sim_trial" if where == "run" else "sim_" + where + "_trial"
    assert getattr(model.state, attr) is model.sim_owners[where]._trial
    assert not model.state.sim_completed
    assert not any(name == "run.completed" for name in model.sim_calls)


@pytest.mark.parametrize(
    "field,value",
    (
        ("iterations", True),
        ("iterations", 2),
        ("maximum", 513),
        ("init_identity", "0" * 64),
        ("assembly_identity", "0" * 64),
        ("parameters_identity", "0" * 64),
        ("operator_mode", "repaired_flux"),
    ),
)
def test_sim_demo_request_drift_refuses_before_any_loop(monkeypatch, tmp_path, field, value):
    def mutate(model, name):
        if name == "run.request.return":
            setattr(model.run_request, field, value)

    model = sim_chain(monkeypatch, mutate=mutate)
    with pytest.raises(ValueError, match="Entire original SIM"):
        prior.execute(model, tmp_path)
    assert "run.source" not in model.sim_calls and model.state.sim_assembly_trial is not None


@pytest.mark.parametrize(
    "field",
    (
        "owner",
        "trial",
        "completed_INIT",
        "constructor",
        "old_p",
        "current_p",
        "sim",
        "cells",
        "callback",
        "phase",
        "before_native_pickle",
        "operator_mode",
    ),
)
def test_sim_demo_completed_surface_drift_never_promotes(monkeypatch, tmp_path, field):
    def mutate(model, name):
        if name == "run.completed":
            model.surface[field] = object()

    model = sim_chain(monkeypatch, mutate=mutate)
    with pytest.raises((ValueError, AttributeError)):
        prior.execute(model, tmp_path)
    assert model.state.sim_trial is model.sim_owners["run"]._trial
    assert not model.state.sim_completed


@pytest.mark.parametrize("role", ("preparation", "assembly", "run"))
@pytest.mark.parametrize("boundary", ("enter", "exit"))
def test_sim_demo_import_failure_unwinds_all_entered_contexts(
    monkeypatch, tmp_path, role, boundary
):
    model = sim_chain(monkeypatch, fail=role + "." + boundary)
    hooks = sys.getprofile(), sys.gettrace()
    with pytest.raises(type(model.primary)) as caught:
        prior.execute(model, tmp_path)
    assert caught.value is model.primary
    assert not model.state.sim_imports_complete and model.state.sim_cleanup_complete
    assert "current_parameters" not in model.sim_calls
    assert all(row["generator"].gi_frame is None for row in model.state.sim_imports)
    assert all(not proof.active for proof in model.proofs.values())
    assert (sys.getprofile(), sys.gettrace()) == hooks
    if boundary == "exit":
        index = [name for name, _ in stage.IMPORTS].index(role)
        assert all(model.proofs[name].published is False for name, _ in stage.IMPORTS[:index])


@pytest.mark.parametrize("drift", ("code", "defaults", "wrapper", "equal_code"))
def test_sim_demo_original_import_binding_changes_refuse_publication(monkeypatch, tmp_path, drift):
    def mutate(model, name):
        if name != "run.published":
            return
        wrapper = model.apis["preparation"].observing_runner_import
        inner = wrapper.__wrapped__
        if drift == "code":
            inner.__code__ = (lambda: None).__code__
        elif drift == "defaults":
            inner.__kwdefaults__["enabled"] = True
        elif drift == "wrapper":
            model.apis["preparation"].observing_runner_import = contextmanager(inner)
        else:
            inner.__code__ = inner.__code__.replace()

    model = sim_chain(monkeypatch, mutate=mutate)
    with pytest.raises(ValueError, match="SIM import"):
        prior.execute(model, tmp_path)
    assert not model.state.sim_imports_complete
    assert "current_parameters" not in model.sim_calls
    assert all(row["generator"].gi_frame is None for row in model.state.sim_imports)


def test_sim_demo_import_enter_return_failure_retains_and_closes_actual_generator(
    monkeypatch, tmp_path
):
    model = sim_chain(monkeypatch)
    original = demo._call

    def call(state, label, function, *args, **kwargs):
        result = original(state, label, function, *args, **kwargs)
        if label == "sim_imports.assembly.enter":
            raise model.primary
        return result

    monkeypatch.setattr(demo, "_call", call)
    with pytest.raises(type(model.primary)):
        prior.execute(model, tmp_path)
    row = model.state.sim_imports[-1]
    assert row["entered"] is False and row["partial_proof"] is model.proofs["assembly"]
    assert row["generator"].gi_frame is None and model.state.sim_cleanup_complete
    assert not model.state.sim_imports_complete and not model.proofs["assembly"].published


@pytest.mark.parametrize("field", ("calendar", "after", "linkage"))
def test_sim_demo_post_loop_capture_failure_keeps_trial_not_completion(
    monkeypatch, tmp_path, field
):
    model = sim_chain(monkeypatch)
    evidence = prior.Evidence(fail="sim_run." + field)
    with pytest.raises(ValueError, match="Typed observation refused"):
        prior.execute(model, tmp_path, evidence)
    assert model.state.sim_trial.loop_returned and model.state.sim_trial.context_returned
    assert not model.state.sim_completed and model.state.sim_time_steps_completed == 0
    assert dict(evidence.values)["sim_failure.run.after"] is model.state.sim_trial.after


def test_sim_demo_unadopted_api_and_source_gate_before_any_factory(monkeypatch):
    monkeypatch.setattr(stage, "SOURCE_PINS", dict.fromkeys(stage.MODULES))
    monkeypatch.setattr(stage, "REVIEW_PINS", dict.fromkeys(stage.MODULES))
    with pytest.raises(demo.DemoRejected, match="unadopted"):
        stage.preflight()
    value = demo.source_plan(endpoint="sim_terminal")
    assert value["kind"] == demo.SIM_KIND
    assert value["optional_sim_terminal"]["acquisition_sequence"] == stage.ACQUISITION_SEQUENCE
    assert demo.source_plan(endpoint="init_terminal")["kind"] == demo.KIND
    assert stage.source_plan()["flux_repair"] is False


def test_sim_demo_full_INIT_failure_never_enters_fresh_parameter_stage(monkeypatch, tmp_path):
    model = sim_chain(monkeypatch)

    def fail(request, *, enabled):
        raise model.primary

    model.modules["init_terminal"].prepare = fail
    with pytest.raises(type(model.primary)):
        prior.execute(model, tmp_path)
    assert "current_parameters" not in model.sim_calls
    assert model.state.sim_init_trial is None and model.state.sim_trial is None


@pytest.mark.parametrize("count", (0, -1, 513, True))
def test_sim_demo_original_calendar_bound_refuses_without_truncation(monkeypatch, tmp_path, count):
    model = sim_chain(monkeypatch, count=count)
    with pytest.raises(ValueError, match="Entire original SIM"):
        prior.execute(model, tmp_path)
    assert "run.source" not in model.sim_calls and model.state.sim_time_steps_completed == 0
    assert model.current_p.sim_tsteps is count


@pytest.mark.parametrize("drift", ("old_owner", "old_p", "owner_p"))
def test_sim_demo_fresh_parameter_pair_must_be_distinct_and_associated(
    monkeypatch, tmp_path, drift
):
    model = sim_chain(monkeypatch)
    if drift == "old_owner":
        model.current_pair = model.ready, model.current_p
    elif drift == "old_p":
        model.current_pair = model.current_owner, model.p
    else:
        model.current_owner.parameters = object()
    with pytest.raises(ValueError, match="Distinct genuine"):
        prior.execute(model, tmp_path)
    assert "preparation.request" not in model.sim_calls
    assert model.state.sim_current_pair is model.current_pair


@pytest.mark.parametrize(
    "label", ("current_parameters", "sim_preparation", "sim_assembly", "sim_run")
)
def test_sim_demo_return_observation_failure_keeps_last_actual_return(monkeypatch, tmp_path, label):
    model = sim_chain(monkeypatch)
    original = demo._call
    returned = []

    def call(state, name, function, *args, **kwargs):
        value = original(state, name, function, *args, **kwargs)
        if name == label:
            returned.append(value)
            raise model.primary
        return value

    monkeypatch.setattr(demo, "_call", call)
    with pytest.raises(type(model.primary)) as caught:
        prior.execute(model, tmp_path)
    assert caught.value is model.primary and returned
    assert model.state.last_return is returned[0]
    assert not model.state.sim_completed and "run.completed" not in model.sim_calls


@pytest.mark.parametrize("failure", ("setter", "read", "identity"))
def test_sim_demo_hook_recovery_failure_stops_all_later_metadata(monkeypatch, tmp_path, failure):
    model = sim_chain(monkeypatch)
    original = stage.sys
    adapter = NS(**vars(original))
    calls = []

    def setter(value):
        calls.append("setter")
        if failure == "setter":
            raise model.primary
        return original.setprofile(value)

    def getter():
        calls.append("getter")
        if failure == "read":
            raise model.primary
        if failure == "identity":
            return object()
        return original.getprofile()

    def mutate(_model, name):
        if name == "run.enter":
            # The real inherited blockade remains installed. Only the metadata
            # restoration adapter is faulted; no native opportunity is opened.
            monkeypatch.setattr(stage, "sys", adapter)
            adapter.setprofile, adapter.getprofile = setter, getter

    model.mutate = mutate
    evidence = prior.Evidence()
    hooks = sys.getprofile(), sys.gettrace()
    with pytest.raises((ValueError, type(model.primary))):
        prior.execute(model, tmp_path, evidence)
    state = model.state
    assert calls and state.sim_metadata_stopped and not state.evidence_completed
    assert not state.sim_imports_complete and not state.sim_completed
    assert "current_parameters" not in model.sim_calls
    assert not any(label.startswith("sim_") for label, _ in evidence.values)
    assert (sys.getprofile(), sys.gettrace()) == hooks
    # Actual suspended managers remain retained if restoration cannot be
    # confirmed. The test closes those exact metadata generators only after
    # restoring the adapter; production never treats this as successful proof.
    monkeypatch.setattr(stage, "sys", original)
    for row in reversed(state.sim_imports):
        if row["generator"].gi_frame is not None:
            row["generator"].close()


def test_sim_demo_failed_SIM_retains_original_partial_and_independent_fields(monkeypatch, tmp_path):
    model = sim_chain(monkeypatch, fail="run.source")
    primary = model.primary
    primary.partial = NS(
        before=object(),
        ready=object(),
        after=None,
        calendar=object(),
        sampled=object(),
        source_error=OSError("source"),
    )
    primary.__cause__ = primary.partial.source_error
    evidence = prior.Evidence(fail="sim_failure.partial.ready")
    with pytest.raises(type(primary)) as caught:
        prior.execute(model, tmp_path, evidence)
    assert caught.value is primary and primary.__cause__ is primary.partial.source_error
    assert model.state.sim_failure_partial is primary.partial
    saved = dict(evidence.values)
    assert saved["sim_failure.partial.before"] is primary.partial.before
    assert saved["sim_failure.partial.sampled"] is primary.partial.sampled
    assert model.state.sim_secondary and not model.state.sim_completed


def prepare(request, *, enabled=False):
    """Compile-authenticated metadata template; this body is never invoked."""
    raise AssertionError("Metadata inspection cannot execute an issuer")


@pytest.mark.parametrize("drift", ("none", "code", "globals", "defaults", "kwdefaults"))
def test_sim_demo_compiles_original_public_function_metadata_without_entry(drift):
    module = ModuleType("isolated_public_metadata")
    module.__file__ = __file__
    function = module.prepare = FunctionType(prepare.__code__, vars(module))
    function.__kwdefaults__ = {"enabled": False}
    if drift == "code":
        function.__code__ = (lambda *args, **kwargs: pytest.fail("foreign delegate")).__code__
    elif drift == "globals":
        module.prepare = FunctionType(prepare.__code__, dict(vars(module)))
        module.prepare.__kwdefaults__ = {"enabled": False}
    elif drift == "defaults":
        function.__defaults__ = (object(),)
    elif drift == "kwdefaults":
        function.__kwdefaults__["enabled"] = True
    if drift == "none":
        stage._original_apis(module, ("prepare",))
    else:
        with pytest.raises((ValueError, demo.DemoRejected)):
            stage._original_apis(module, ("prepare",))


@pytest.mark.parametrize("drift", ("replace", "code", "equal_code", "kwdict", "kwvalue", "law"))
@pytest.mark.parametrize("boundary", ("current_parameters", "assembly.request"))
def test_sim_demo_live_public_binding_drift_refuses_before_replacement_delegate(
    monkeypatch, tmp_path, drift, boundary
):
    calls = []

    def foreign(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Foreign public function must never execute")

    def mutate(model, name):
        if name != boundary:
            return
        api = model.apis["run"]
        original = api.prepare
        if drift == "replace":
            api.prepare = foreign
        elif drift in ("code", "equal_code"):
            # Equal structure is insufficient after identity was retained.
            original.__code__ = original.__code__.replace(
                co_name="different" if drift == "code" else original.__code__.co_name
            )
        elif drift == "kwdict":
            original.__kwdefaults__ = dict(original.__kwdefaults__)
        elif drift == "kwvalue":
            original.__kwdefaults__["enabled"] = True
        else:
            api.LAW_ID = "changed law"

    model = sim_chain(monkeypatch, mutate=mutate)
    model.apis["run"].prepare.__kwdefaults__ = {"enabled": False}
    with pytest.raises(ValueError, match="SIM public API changed"):
        prior.execute(model, tmp_path)
    assert calls == [] and "run.source" not in model.sim_calls
    assert not model.state.sim_completed


def test_sim_demo_final_current_owner_check_must_return_same_trial(monkeypatch, tmp_path):
    model = sim_chain(monkeypatch)
    model.apis["run"].validate_sim = lambda owner: object()
    evidence = prior.Evidence()
    with pytest.raises(ValueError, match="Same completed SIM trial"):
        prior.execute(model, tmp_path, evidence)
    assert model.state.sim_trial.loop_returned and model.state.sim_linkage is not None
    assert not model.state.sim_completed and model.state.sim_time_steps_completed == 0


@pytest.mark.parametrize("event", ("call", "return"))
@pytest.mark.parametrize("source_failure", (False, True))
def test_sim_demo_binding_observer_failure_restores_hooks_inside_actual_exit(
    monkeypatch, tmp_path, event, source_failure
):
    model = sim_chain(monkeypatch)
    primary = prior.Falsey("original source")
    primary.__cause__ = OSError("source cause")
    capture = OSError("binding observer")
    if source_failure:

        def fail_callback(*args, **kwargs):
            raise primary

        model.modules["callback"].acquire_callback = fail_callback
    prior_profile, prior_trace = sys.getprofile(), sys.gettrace()
    active = [True]
    exits = []

    def observer(frame, actual_event, arg):
        if prior_profile is not None:
            prior_profile(frame, actual_event, arg)
        if (
            active[0]
            and frame.f_code is stage._check_import_binding.__code__
            and actual_event == event
        ):
            active[0] = False
            raise capture

    def at_exit(_model, name):
        if name.endswith(".exit"):
            exits.append((name, sys.getprofile(), sys.gettrace()))
            assert sys.getprofile() is observer and sys.gettrace() is prior_trace

    model.mutate = at_exit
    sys.setprofile(observer)
    try:
        with pytest.raises((prior.Falsey, OSError)) as caught:
            prior.execute(model, tmp_path)
        assert caught.value is (primary if source_failure else capture)
        assert not active[0] and len(exits) == 3
        assert sys.getprofile() is observer and sys.gettrace() is prior_trace
        assert model.state.sim_cleanup_complete and not model.state.sim_imports_complete
        if source_failure:
            assert primary.__cause__.args == ("source cause",)
            assert any(error is capture for _, error in model.state.sim_secondary)
    finally:
        sys.setprofile(prior_profile)
        sys.settrace(prior_trace)


@pytest.mark.parametrize(
    "drift", ("none", "dropped", "body_code", "guard_code", "delegate", "factory")
)
def test_sim_demo_actual_preparation_guard_code_is_authenticated_without_execution(drift):
    # Compile-only exact producer templates, never importing the actual module
    # or invoking its factory/body. This models the real guarded ABI, unlike an
    # undecorated stand-in. All candidate owner/source entry remains blocked.
    path = stage.ROOT / "src/cells/processes/betse_native_init_sim_preparation.py"
    codes = {
        value.co_name: value
        for value in compile(path.read_bytes(), str(path), "exec", dont_inherit=True).co_consts
        if type(value) is CodeType
    }
    module = ModuleType("metadata_actual_guard_code")
    module.__file__ = str(path)
    module._entry_guard = FunctionType(codes["_entry_guard"], vars(module))
    guard_code = next(
        c for c in codes["_entry_guard"].co_consts if type(c) is CodeType and c.co_name == "guarded"
    )
    for name in ("from_init", "prepare"):
        inner = FunctionType(codes[name], vars(module))
        inner.__kwdefaults__ = {"enabled": False} if name == "prepare" else None
        cell = (lambda value: lambda: value)(inner).__closure__[0]
        wrapper = FunctionType(guard_code, vars(module), closure=(cell,))
        wrapper.__wrapped__ = inner
        setattr(module, name, wrapper)
    if drift == "dropped":
        module.prepare = module.prepare.__wrapped__
    elif drift == "body_code":
        module.prepare.__wrapped__.__code__ = codes["from_init"]
    elif drift == "guard_code":
        module.prepare.__code__ = guard_code.replace(co_name="foreign")
    elif drift == "delegate":
        original = module.prepare.__wrapped__
        clone = FunctionType(original.__code__, vars(module))
        clone.__kwdefaults__ = {"enabled": False}
        module.prepare.__closure__[0].cell_contents = clone
    elif drift == "factory":
        module._entry_guard.__code__ = (lambda value: value).__code__
    if drift == "none":
        stage._original_apis(module, ("from_init", "prepare"), guarded=("from_init", "prepare"))
    else:
        with pytest.raises(ValueError):
            stage._original_apis(module, ("from_init", "prepare"), guarded=("from_init", "prepare"))


@pytest.mark.parametrize("drift", ("replace", "equal_code", "delegate_code", "wrapper_link"))
def test_sim_demo_retained_guard_and_delegate_atoms_cannot_be_retargeted(
    monkeypatch, tmp_path, drift
):
    calls = []

    def guard(function):
        def wrapped(*args, **kwargs):
            return function(*args, **kwargs)

        wrapped.__wrapped__ = function
        return wrapped

    def mutate(model, name):
        if name != "current_parameters":
            return
        wrapped = model.apis["preparation"].prepare
        if drift == "replace":
            model.apis["preparation"].prepare = lambda *a, **k: calls.append(True)
        elif drift == "equal_code":
            wrapped.__code__ = wrapped.__code__.replace()
        elif drift == "delegate_code":
            inner = wrapped.__wrapped__
            inner.__code__ = inner.__code__.replace()
        else:
            wrapped.__wrapped__ = lambda *a, **k: calls.append(True)

    model = sim_chain(monkeypatch, mutate=mutate)
    model.apis["preparation"].prepare = guard(model.apis["preparation"].prepare)
    with pytest.raises(ValueError, match="SIM public API changed"):
        prior.execute(model, tmp_path)
    assert not calls and "preparation.request" not in model.sim_calls


@pytest.mark.parametrize("drift", ("replace", "code", "equal_code", "defaults", "module"))
def test_sim_demo_current_parameter_api_drift_refuses_before_second_pipeline(
    monkeypatch, tmp_path, drift
):
    model = sim_chain(monkeypatch)
    original = model.modules["init_terminal"].prepare
    delegates = []

    def finish(request, *, enabled):
        owner = original(request, enabled=enabled)
        module = model.modules["parameters"]
        function = module.acquire_current_world_ready
        if drift == "replace":
            module.acquire_current_world_ready = lambda *a, **k: delegates.append(True)
        elif drift in ("code", "equal_code"):
            function.__code__ = function.__code__.replace(
                co_name="foreign" if drift == "code" else function.__code__.co_name
            )
        elif drift == "defaults":
            function.__kwdefaults__ = {"enabled": False}
        else:
            model.modules["parameters"] = NS(**vars(module))
        return owner

    model.modules["init_terminal"].prepare = finish
    with pytest.raises(ValueError, match="SIM public API changed|parameter module association"):
        prior.execute(model, tmp_path)
    assert not delegates and "current_parameters" not in model.sim_calls
    assert model.state.terminal_trial.source_completed and not model.state.sim_completed


@pytest.mark.parametrize("fault", ("observer_entry", "writer", "post_observation"))
def test_sim_demo_observation_failure_blocks_completion_and_keeps_trial(
    monkeypatch, tmp_path, fault
):
    model = sim_chain(monkeypatch, count=2)
    primary = prior.Falsey("observer transport failure")
    primary.__cause__ = OSError("source cause")
    if fault == "observer_entry":

        def reject(model, boundary):
            if boundary == "entry":
                raise primary

        model.observation.fault = reject
    elif fault == "writer":

        def fail(*args, **kwargs):
            raise primary

        monkeypatch.setattr(stage.observation.evidence.payload, "write", fail)
    else:
        original = model.apis["run"].validate_sim

        def validate(owner):
            if model.state.sim_observation.completed:
                raise primary
            return original(owner)

        model.apis["run"].validate_sim = validate
    with pytest.raises(type(primary)) as raised:
        prior.execute(model, tmp_path, prior.Evidence())
    assert raised.value is primary and primary.__cause__.args == ("source cause",)
    assert model.state.sim_trial is model.sim_owners["run"]._trial
    assert not model.state.sim_completed and model.state.sim_time_steps_completed == 0
    assert model.state.sim_observation.owner is model.sim_owners["run"]
    assert model.sim_calls.count("run.source") == 1
    assert model.state.primary is primary


def test_sim_demo_observer_binding_refusal_precedes_callback_and_parameters(monkeypatch, tmp_path):
    model = sim_chain(monkeypatch)

    def refuse(*args):
        raise ValueError("Observer is not adopted")

    monkeypatch.setattr(stage.observation, "bind", refuse)
    with pytest.raises(ValueError, match="not adopted"):
        prior.execute(model, tmp_path, prior.Evidence())
    assert not model.sim_calls and model.state.callback is None and model.state.parameters is None
