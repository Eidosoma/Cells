"""Blocked orchestration controls; private protocol fakes never issue authority."""

import json
import os
import sys
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_demo as stage
from validation.betse import native_seed_demo_evidence as transport
from validation.betse import native_seed_demo_software as software
from validation.betse import native_seed_world_geometry_qualification as geometry

_RAW_GUARDS = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit native-blocked demonstration software release required")
    request.config.option.maxfail = 1
    adapter = NS(**dict(vars(software), reuse=software.base.reuse.reuse))
    namespace = dict(vars(guards), software=adapter, _BLOCKADE_FAILURES=())
    fn = FunctionType(guards._blockade.__wrapped__.__code__, namespace)
    try:
        with contextmanager(fn)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARDS.append(namespace["_BLOCKADE_FAILURES"])


class Evidence:
    def __init__(self, fail=None, forensic_error=None):
        self.rows, self.values = [], []
        self.fail, self.forensic_error = fail, forensic_error

    def save(self, label, value):
        self.values.append((label, value))
        self.rows.append(dict(label=label, status="failed" if label == self.fail else "saved"))
        return label != self.fail

    def failure(self, error):
        self.values.append(("failure", error))
        if self.forensic_error is not None:
            raise self.forensic_error


def test_demo_profile_images_empty_selection_needs_no_file_authority():
    state = stage.Execution("disabled")
    state.phase = NS(dyna=NS(tissue_name_to_profile={"all": NS(picker=object())}))
    assert stage._profile_image_inputs(state, object()) == ()
    assert state.operations == []


def test_demo_profile_images_issue_original_bytes_once_per_actual_filename(image_declarations):
    b = image_declarations
    b.profiles["shared"] = b.profiles["0"]
    values = stage._profile_image_inputs(b.state, b.module)
    assert len(values) == 2 and len(b.state.operations) == 2
    for name, value in zip(b.names, values, strict=True):
        assert type(value) is b.module.files.FileInput
        assert value.filename == str(b.root / name)
        assert value.sha256 == stage.snapshot.digest(b.root / name)
        b.module.files._verify_file(value)
    assert b.state.last_return is values[-1]


@pytest.mark.parametrize("mutation", ["outside", "unknown", "bits", "type"])
def test_demo_profile_images_refuse_unbound_or_changed_files(image_declarations, mutation):
    b = image_declarations
    picker = b.profiles["0"].picker
    path = b.root / b.names[0]
    if mutation == "outside":
        picker.filename = str(b.root.parent / "same.png")
    elif mutation == "unknown":
        picker.filename = str(b.root / "new.png")
    elif mutation == "type":
        picker.filename = path
    else:
        path.chmod(0o644)
        path.write_bytes(b"changed pixels, never decoded")
        path.chmod(0o444)
    with pytest.raises(ValueError):
        stage._profile_image_inputs(b.state, b.module)
    assert b.state.last_return is None


def test_demo_profile_images_second_failure_retains_first_actual_file_declaration(
    image_declarations,
):
    b = image_declarations
    path = b.root / b.names[1]
    path.chmod(0o644)
    path.write_bytes(b"changed second image")
    path.chmod(0o444)
    with pytest.raises(ValueError) as got:
        stage._profile_image_inputs(b.state, b.module)
    assert b.state.primary is got.value and b.state.delegate_error is got.value
    assert b.state.last_return.filename == str(b.root / b.names[0])
    assert [row["status"] for row in b.state.operations] == ["returned", "failed"]


def test_demo_profile_images_are_forwarded_to_the_actual_next_public_request(
    image_declarations, tmp_path
):
    b = image_declarations
    model = chain()
    model.state.input_root = b.root
    model.phase.dyna = b.state.phase.dyna
    module = model.modules["profiles"]
    module.files = b.module.files
    seen = []

    def request(parent, *, law_id, image_inputs):
        model.calls.append("profiles_request")
        assert law_id == "profiles" and not parent.consumed
        for value in image_inputs:
            module.files._verify_file(value)
        seen.extend(image_inputs)
        return NS(parent=parent)

    module.from_core = request
    assert execute(model, tmp_path).methods_completed
    assert [value.filename for value in seen] == [str(b.root / name) for name in b.names]


class Falsey(ValueError):
    def __bool__(self):
        return False


@pytest.fixture
def image_declarations(tmp_path):
    from cells.processes import betse_native_parameter_yaml_prefix as files
    from validation.betse import native_seed_demo_inputs as inputs

    root = tmp_path / "config"
    names = ("geo/circle/spot_2.png", "geo/circle/spot_3.png")
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((inputs.NATIVE / name).read_bytes())
        path.chmod(0o444)
    state = stage.Execution("original", input_root=root)
    profiles = {
        str(index): NS(picker=NS(filename=str(root / name))) for index, name in enumerate(names)
    }
    state.phase = NS(dyna=NS(tissue_name_to_profile=profiles))
    return NS(state=state, module=NS(files=files), root=root, names=names, profiles=profiles)


def chain(*, mode="original", fail=None, primary=None, mutate=None):
    """Stateful private protocol, with old-owner reads rejected after retirement."""
    p, calls, owners = NS(molecules_enabled=False), [], []
    phase = NS(
        p=p,
        cells=object(),
        sim=object(),
        dyna=NS(tissue_name_to_profile={}),
        callbacks=object(),
    )
    primary = primary if primary is not None else ValueError("same delegated failure")
    primary.__cause__ = KeyError("original cause")
    state = stage.Execution(mode)

    class Owner:
        def __init__(self, name):
            self.name, self.consumed = name, False
            self.saved = NS(source_completed=True, flux_operator=mode, cache=(name,), identity=name)
            if name == "profiles":
                del self.saved.cache
                self.saved.after = (name, "after")
            owners.append(self)

        @property
        def trial(self):
            assert not self.consumed, "Consumed numeric owner validator was reopened"
            calls.append(self.name + ".trial")
            return self.saved

        @property
        def phase(self):
            assert not self.consumed
            return phase

    ready = NS(parameters=p)
    callback = object()

    def check(name):
        calls.append(name)
        if fail == name:
            raise primary

    def acquire_callback(configuration, directory, **kwargs):
        check("callback")
        assert kwargs["enabled"] is True and configuration == {"declared": "auxiliary"}
        return callback

    def acquire_world_ready(packet, directory, **kwargs):
        check("parameters")
        assert kwargs["enabled"] is True
        return ready, p

    def evaluate_live(actual_ready, actual_callback, directory, **kwargs):
        check("geometry")
        assert actual_ready is ready and actual_callback is callback
        assert kwargs == dict(enabled=True, evidence_profile="seed_demo")
        result = Owner("geometry")
        if mutate is not None:
            mutate("geometry", result, phase)
        return result

    modules = dict(
        callback=NS(acquire_callback=acquire_callback),
        parameters=NS(acquire_world_ready=acquire_world_ready),
        geometry=NS(evaluate_live=evaluate_live),
    )
    for label, method in (
        ("poisson", "from_geometry"),
        ("core", "from_world"),
        ("profiles", "from_core"),
        ("junctions", "from_profiles"),
    ):

        def request(parent, *, law_id, label=label, **kwargs):
            check(label + "_request")
            assert law_id == label
            expected = dict(flux_operator=mode) if label == "poisson" else {}
            if label == "profiles":
                expected = dict(image_inputs=())
            assert kwargs == expected
            assert not parent.consumed
            return NS(parent=parent)

        def prepare(request, *, enabled, label=label):
            check(label)
            assert enabled is True
            request.parent.consumed = True
            result = Owner(label)
            if mutate is not None:
                mutate(label, result, phase)
            return result

        module = NS(
            LAW_ID=label, prepare=prepare, trial_record=lambda trial: dict(id=trial.identity)
        )
        setattr(module, method, request)
        modules[label] = module
    plan = dict(
        auxiliary_configuration={"declared": "auxiliary"},
        callback_bootstrap="bootstrap.json",
        callback_bootstrap_sha256="b" * 64,
        parameter_packet="parameter-packet",
        parameter_sha256="a" * 64,
    )
    return NS(
        state=state,
        modules=modules,
        plan=plan,
        calls=calls,
        owners=owners,
        phase=phase,
        p=p,
        primary=primary,
        ready=ready,
        callback=callback,
    )


def execute(model, output, evidence=None, session=None):
    return stage._run(
        model.state,
        model.modules,
        model.plan,
        output,
        evidence if evidence is not None else Evidence(),
        session if session is not None else nullcontext(),
    )


def test_demo_plan_explicit_whole_endpoint_two_modes_and_closed_producers(monkeypatch):
    monkeypatch.setattr(stage, "SOURCE_PINS", dict.fromkeys(stage.MODULES))
    monkeypatch.setattr(stage, "REVIEW_PINS", dict.fromkeys(stage.MODULES))
    monkeypatch.setattr(stage, "SESSION_REVIEW_SHA256", None)
    value = stage.source_plan()
    assert value["stages"] == (
        "callback",
        "parameters",
        "geometry",
        "poisson",
        "core",
        "profiles",
        "junctions",
    )
    assert value["flux_modes"] == ("original", "disabled")
    assert "membrane/junction" in value["flux_policy"]["disabled"]
    assert "graphLaplacian" in value["endpoint"]
    assert all(pin is None for pin in value["source_pins"].values())
    assert all(pin is None for pin in value["review_pins"].values())
    assert value["shared_log_session_review"] is None
    assert "process-lifetime" in value["shared_log_session_api"]
    assert value["native_policy"]["wall_seconds"] == 7200
    assert not value["evolving_SIM_or_restart_claim"]
    assert value["evidence_profile"] == "seed_demo"
    assert value["evidence_source"] == stage.EVIDENCE_SOURCE_SHA256


@pytest.mark.parametrize(
    "enabled,release", [(False, None), (True, None), (False, "1"), (True, "1")]
)
def test_demo_unbound_public_entry_refuses_before_inputs_or_imports(enabled, release, monkeypatch):
    monkeypatch.setattr(stage, "SESSION_REVIEW_SHA256", None)

    class Foreign:
        def __fspath__(self):
            raise AssertionError("No foreign input access")

    if release is None:
        monkeypatch.delenv(stage.RELEASE, raising=False)
    else:
        monkeypatch.setenv(stage.RELEASE, release)
    with pytest.raises(stage.DemoRejected) as caught:
        stage.run_demo(Foreign(), Foreign(), plan_sha256="x", enabled=enabled)
    assert caught.value.stage == ("unbound" if enabled and release == "1" else "release")
    assert stage._ACTIVE == [] and stage._ATTEMPT is None


@pytest.mark.parametrize("consumer", [stage, geometry], ids=["demo", "geometry"])
def test_demo_evidence_consumers_resolve_exact_writer_and_typed_capture(consumer, tmp_path):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    writer = (
        consumer._evidence_writer("seed_demo")
        if consumer is geometry
        else consumer._evidence_writer()
    )
    assert writer is transport.capture_writer
    recorder = Recorder(tmp_path, sidecars=True, capture_writer=writer)
    value = {"records": [("source", 3, False)], "negative_zero": -0.0, "raw": b"\x00\xff"}
    assert recorder.save("actual-recorder", value)
    row = recorder.rows[0]
    path = tmp_path / row["path"]
    saved = transport.read(path, expected_sha256=row["sha256"])
    assert saved == {
        "records": [["source", 3, False]],
        "negative_zero": {"float64_bits": "0000000000000080"},
        "raw": {"bytes_hex": "00ff"},
    }
    assert transport.files(path, expected_sha256=row["sha256"])


def test_demo_evidence_real_recorder_crosses_ordinary_tree_bound_without_truncation(tmp_path):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    work = [("literal", "entry", i) for i in range(70000)]
    recorder = Recorder(tmp_path, sidecars=True, capture_writer=stage._evidence_writer())
    assert recorder.save("full-ledger", {"work": work, "completed": False})
    row = recorder.rows[0]
    path = tmp_path / row["path"]
    index = json.loads(path.read_text())
    assert index["kind"] == transport.KIND and index["counts"]["nodes"] > 262144
    saved = transport.read(path, expected_sha256=row["sha256"])
    assert saved == {"work": [list(item) for item in work], "completed": False}
    assert len(transport.files(path, expected_sha256=row["sha256"])) > 1
    assert transport.payload.MAX_NODES == 262144


@pytest.mark.parametrize("profile", [None, 1, "implicit-large"])
def test_demo_evidence_unknown_geometry_profile_refuses_before_import(profile, monkeypatch):
    def forbidden(*args):
        raise AssertionError("No helper import for undeclared profile")

    monkeypatch.setattr(geometry, "_bound_module", forbidden)
    assert geometry._evidence_writer("ordinary") is None
    with pytest.raises(geometry.QualificationRejected) as got:
        geometry._evidence_writer(profile)
    assert got.value.stage == "evidence"


@pytest.mark.parametrize("consumer", [stage, geometry], ids=["demo", "geometry"])
@pytest.mark.parametrize("pin", [None, "0" * 64], ids=["unbound", "changed"])
def test_demo_evidence_missing_or_changed_producer_refuses_before_import(
    consumer, pin, monkeypatch
):
    def forbidden(*args):
        raise AssertionError("No import before exact source authentication")

    monkeypatch.setattr(consumer, "EVIDENCE_SOURCE_SHA256", pin)
    with monkeypatch.context() as patch:
        patch.setattr(consumer.importlib, "import_module", forbidden)
        with pytest.raises(ValueError):
            if consumer is geometry:
                consumer._evidence_writer("seed_demo")
            else:
                consumer._evidence_writer()


@pytest.mark.parametrize("consumer", [stage, geometry], ids=["demo", "geometry"])
def test_demo_evidence_foreign_loaded_writer_globals_refuse(consumer, monkeypatch):
    foreign = FunctionType(transport.capture_writer.__code__, dict(vars(transport)))
    monkeypatch.setattr(transport, "capture_writer", foreign)
    with pytest.raises(ValueError):
        if consumer is geometry:
            consumer._evidence_writer("seed_demo")
        else:
            consumer._evidence_writer()


@pytest.mark.parametrize("mode", stage.FLUX_MODES)
def test_demo_whole_order_same_objects_and_mode_without_reopening_consumed_owners(mode, tmp_path):
    model, evidence = chain(mode=mode), Evidence()
    returned = execute(model, tmp_path, evidence)
    assert returned is model.state
    assert returned.result is model.owners[-1]
    assert returned.phase is model.phase and returned.parameters is model.p
    assert returned.callback is model.callback and returned.world_ready is model.ready
    assert all(o.consumed for o in model.owners[:-1]) and not model.owners[-1].consumed
    assert model.calls == [
        "callback",
        "parameters",
        "geometry",
        "geometry.trial",
        "poisson_request",
        "poisson",
        "poisson.trial",
        "core_request",
        "core",
        "core.trial",
        "profiles_request",
        "profiles",
        "profiles.trial",
        "junctions_request",
        "junctions",
        "junctions.trial",
    ]
    assert [n for n, _ in returned.trials] == [
        "geometry",
        "poisson",
        "core",
        "profiles",
        "junctions",
    ]
    assert returned.methods_completed and returned.evidence_completed
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "completed" and outcome["flux_operator"] == mode
    assert outcome["scientific_or_physical_credit"] == 0
    assert outcome["original_flux_defect_repaired"] is False
    assert outcome["complete_seed_runner_or_INIT_SIM_restart_claim"] is False
    assert ("profiles.after", ("profiles", "after")) in evidence.values


@pytest.mark.parametrize(
    "failed",
    [
        "callback",
        "parameters",
        "geometry",
        "poisson_request",
        "poisson",
        "core_request",
        "core",
        "profiles_request",
        "profiles",
        "junctions_request",
        "junctions",
    ],
)
def test_demo_each_api_failure_stops_without_fallback_and_retains_exact_previous_trials(
    failed, tmp_path
):
    model = chain(fail=failed)
    with pytest.raises(ValueError) as caught:
        execute(model, tmp_path)
    assert caught.value is model.primary
    assert caught.value.__cause__.args == ("original cause",)
    assert model.calls[-1] == failed
    assert not model.state.methods_completed and model.state.result is None
    assert all(
        t is owner.saved for (_, t), owner in zip(model.state.trials, model.owners, strict=True)
    )
    assert model.state.delegate_error is model.primary
    assert json.loads((tmp_path / "outcome.json").read_text())["status"] == "failed"


def electrical_chain(*, mode="original", fail=None, mutate=None):
    """Synthetic consumer protocol; source, operator and actual owner entry stay blocked."""
    model = dynamics_chain(mode=mode)
    model.state.endpoint = model.plan["endpoint"] = "init_electrical"
    model.field_objects = {}
    dynamics = dict.__getitem__(model.modules, "init_dynamics")
    original = dynamics.prepare

    def completion(request, *, enabled):
        actual = original(request, enabled=enabled)
        _, phase, trial = model.dynamics_objects[-1]

        class Retirable:
            consumed = False

            @property
            def trial(self):
                assert not self.consumed, "Consumed dynamics owner reopened"
                return actual.trial

            @property
            def phase(self):
                assert not self.consumed, "Consumed dynamics owner reopened"
                return actual.phase

        child = Retirable()
        model.dynamics_objects[-1] = child, phase, trial
        return child

    dynamics.prepare = completion

    def module_for(name, parent_name, factory):
        def point(label):
            model.calls.append(name + "." + label)
            if fail == (name, label):
                raise model.primary

        def prior():
            return (
                model.dynamics_objects[0]
                if parent_name == "init_dynamics"
                else model.field_objects[parent_name]
            )

        def request(parent, *, law_id):
            point("request")
            assert parent is prior()[0] and parent.consumed is False
            assert law_id == name
            return NS(parent=parent)

        def prepare(request, *, enabled):
            assert enabled is True and request.parent is prior()[0]
            request.parent.consumed = True
            point("source")
            _, phase, parent_trial = prior()
            before, after = bytes.fromhex("0000000000000080"), [-0.0, 2.0]
            streams = ("a" * 64, "b" * 64)
            trial = NS(
                identity=name,
                parent_identity=parent_trial.identity,
                source_completed=True,
                completed=True,
                before=(name, "before"),
                after=(name, "after"),
                stream_before=streams,
                stream_after=tuple(streams),
                rng_before=streams,
                rng_after=tuple(streams),
                stores=((2007, "vm", before, after, True, True),),
                raw_returns=((sys._getframe(), None), (sys._getframe(), after)),
            )
            if mutate is not None:
                replacement = mutate(name, model, phase, trial)
                if replacement is not None:
                    phase = replacement

            class Child:
                consumed = False

                @property
                def trial(self):
                    assert not self.consumed, "Consumed storage owner reopened"
                    point("trial")
                    return trial

                @property
                def phase(self):
                    assert not self.consumed, "Consumed storage owner reopened"
                    point("phase")
                    return phase

            child = Child()
            model.field_objects[name] = child, phase, trial
            return child

        def record(trial):
            point("record")
            return dict(parent=trial.parent_identity, completed=True)

        return NS(LAW_ID=name, **{factory: request}, prepare=prepare, trial_record=record)

    model.modules["init_storage"] = module_for("init_storage", "init_dynamics", "from_dynamics")
    model.modules["init_electrical"] = module_for("init_electrical", "init_storage", "from_storage")
    return model


@pytest.mark.parametrize("mode", stage.FLUX_MODES)
def test_demo_init_electrical_keeps_issued_lineage_raw_values_and_both_flux_modes(mode, tmp_path):
    model, evidence = electrical_chain(mode=mode), Evidence()
    returned = execute(model, tmp_path, evidence)
    assert returned is model.state
    assert returned.result is model.field_objects["init_electrical"][0]
    assert (
        model.state.phase
        is model.state.init_phase
        is model.state.storage_phase
        is model.state.electrical_phase
    )
    assert (
        model.state.init_dynamics_completed
        and model.state.init_storage_completed
        and model.state.init_electrical_completed
    )
    assert model.dynamics_objects[0][0].consumed and model.field_objects["init_storage"][0].consumed
    with pytest.raises(AssertionError, match="Consumed"):
        _ = model.field_objects["init_storage"][0].trial
    captured = dict(evidence.values)
    for name in ("init_storage", "init_electrical"):
        _, phase, trial = model.field_objects[name]
        assert phase is model.state.phase
        assert captured[name + ".stores"][0][2] is trial.stores[0][2]
        assert captured[name + ".stores"][0][3] is trial.stores[0][3]
        assert captured[name + ".raw_returns"][1] is trial.raw_returns[1][1]
        assert model.calls.count(name + ".trial") == 1 and model.calls.count(name + ".phase") == 1
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "completed" and outcome["endpoint"] == "init_electrical"
    assert outcome["completed_stage_trials"][-2:] == ["init_storage", "init_electrical"]
    assert (
        outcome["init_time_steps_completed"] == 0
        and outcome["original_flux_defect_repaired"] is False
    )


@pytest.mark.parametrize("name", ["init_storage", "init_electrical"])
@pytest.mark.parametrize("field", ["p", "cells", "sim", "dyna", "callbacks", "cache", "phase"])
def test_demo_init_electrical_refuses_retargeted_same_object_chain(name, field, tmp_path):
    def mutate(actual, _model, phase, _trial):
        if actual == name:
            if field == "phase":
                return NS(**vars(phase))
            setattr(phase, field, object())

    model = electrical_chain(mutate=mutate)
    with pytest.raises(ValueError, match="exact phase"):
        execute(model, tmp_path)
    assert (
        getattr(model.state, name.removeprefix("init_") + "_trial") is model.field_objects[name][2]
    )
    assert not getattr(model.state, name + "_completed") and model.state.result is None
    assert model.calls[-1] == name + ".phase"


@pytest.mark.parametrize("name", ["init_storage", "init_electrical"])
@pytest.mark.parametrize(
    "mutation", ["parent", "completed", "rng", "rng_type", "rng_count", "stores", "partial_store"]
)
def test_demo_init_electrical_rejects_incomplete_or_changed_evidence(name, mutation, tmp_path):
    def mutate(actual, _model, _phase, trial):
        if actual != name:
            return
        if mutation == "parent":
            trial.parent_identity = "foreign"
        elif mutation == "completed":
            trial.source_completed = trial.completed = False
        elif mutation.startswith("rng"):
            value = (
                ("c" * 64, "b" * 64)
                if mutation == "rng"
                else ["a" * 64, "b" * 64]
                if mutation == "rng_type"
                else ("a" * 64,)
            )
            trial.stream_after = trial.rng_after = value
        elif mutation == "stores":
            trial.stores = ()
        else:
            trial.stores = ((*trial.stores[0][:-1], False),)

    model = electrical_chain(mutate=mutate)
    with pytest.raises(ValueError):
        execute(model, tmp_path)
    assert model.state.result is None and not model.state.init_electrical_completed
    assert model.calls[-1] == name + ".phase"


@pytest.mark.parametrize("name", ["init_storage", "init_electrical"])
@pytest.mark.parametrize("failure", ["request", "source", "trial", "phase", "record"])
def test_demo_init_electrical_failure_retains_consumption_and_original_cause(
    name, failure, tmp_path
):
    model = electrical_chain(fail=(name, failure))
    cause = KeyError("original")
    error = Falsey("field source failed")
    error.__cause__ = cause
    model.primary = error
    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path)
    assert caught.value is error and model.state.primary is error and error.__cause__ is cause
    parent = (
        model.dynamics_objects[0][0]
        if name == "init_storage"
        else model.field_objects["init_storage"][0]
    )
    assert parent.consumed is (failure != "request")
    assert model.state.init_dynamics_completed and not model.state.init_electrical_completed
    assert model.state.result is None


@pytest.mark.parametrize("name", ["init_storage", "init_electrical"])
@pytest.mark.parametrize(
    "field",
    ["record", "before", "after", "streams_before", "streams_after", "stores", "raw_returns"],
)
def test_demo_init_electrical_capture_failure_keeps_child_and_stops_next_stage(
    name, field, tmp_path
):
    if field.startswith("streams_"):
        field = ("stream_" if name == "init_storage" else "rng_") + field.removeprefix("streams_")
    model, evidence = electrical_chain(), Evidence(fail=name + "." + field)
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, evidence)
    assert model.state.owners[-1][1] is model.field_objects[name][0]
    assert model.state.last_trial is model.field_objects[name][2]
    assert not model.state.init_electrical_completed and model.state.result is None
    if name == "init_storage":
        assert "init_electrical" not in model.field_objects
        assert not model.field_objects[name][0].consumed


def test_demo_init_electrical_gate_precedes_all_dependency_reads_and_imports(monkeypatch):
    for key in (
        "INIT_SOURCE_PINS",
        "INIT_REVIEW_PINS",
        "PRELUDE_SOURCE_PINS",
        "PRELUDE_REVIEW_PINS",
        "COMPLETION_SOURCE_PINS",
        "COMPLETION_REVIEW_PINS",
    ):
        monkeypatch.setattr(stage, key, dict.fromkeys(getattr(stage, key), "a" * 64))

    def forbidden(*args, **kwargs):
        raise AssertionError("No dependency read/import while field producers remain unbound")

    monkeypatch.setattr(stage.snapshot, "digest", forbidden)
    monkeypatch.setattr(stage.importlib, "import_module", forbidden)
    with pytest.raises(stage.DemoRejected) as caught:
        stage._dependencies("init_electrical")
    assert caught.value.stage == "electrical_unbound"
    for endpoint in stage.ENDPOINTS:
        for key in stage.ELECTRICAL_MODULES:
            with pytest.raises(stage.DemoRejected, match="electrical producer unavailable"):
                stage.Modules(endpoint)[key]
    plan = stage.source_plan(endpoint="init_electrical")
    assert plan["stages"][-2:] == ("init_storage", "init_electrical")
    assert plan["optional_init_electrical"]["source_pins"] == dict.fromkeys(
        stage.ELECTRICAL_MODULES
    )
    assert plan["optional_init_electrical"]["checkpoint_or_time_loop_admission"] is False


@pytest.mark.parametrize(
    "module",
    [
        "betse_native_init_storage",
        "betse_native_init_storage_source",
        "betse_native_init_electrical",
        "betse_native_init_electrical_source",
    ],
)
def test_demo_init_electrical_runner_blocks_real_owners_and_methods(module):
    for name in ("prepare", "_run", "update_V", "clear_storage", "get_current", "HH_Decomp"):
        frame = NS(
            f_globals={"__name__": "cells.processes." + module},
            f_code=NS(co_name=name, co_filename="<metadata-only>"),
        )
        assert software.is_forbidden_frame(frame)


@pytest.mark.parametrize("name", ["init_storage", "init_electrical"])
@pytest.mark.parametrize("writer_failure", [False, True])
@pytest.mark.parametrize("failure_boundary", ["request", "source"])
def test_demo_init_electrical_failure_archive_keeps_partial_stores_and_last_return(
    name, writer_failure, failure_boundary, tmp_path
):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    model = electrical_chain(fail=(name, failure_boundary))
    error, cause = Falsey("original field failure"), KeyError("cause")
    error.__cause__ = cause
    original = bytes.fromhex("0000000000000080")
    raw = [-0.0, 0.5]
    partial = NS(
        before=("before",),
        after=None,
        stream_ids=("a" * 64, "b" * 64),
        stores=[(2007, "vm", original, raw, True, False)],
        raw_returns=[(sys._getframe(), raw)],
        last_raw=(sys._getframe(), raw),
        last_store=(2007, "vm", original, raw, True, False),
    )
    setattr(error, "init_storage_partial" if name == "init_storage" else "partial", partial)
    model.primary = error
    evidence = Recorder(tmp_path, sidecars=True, capture_writer=stage._evidence_writer())
    save = evidence.save
    secondary = OSError("first forensic observation failed")

    def write(label, value):
        if writer_failure and label == name + ".failure.before":
            raise secondary
        return save(label, value)

    evidence.save = write
    with pytest.raises(Falsey):
        execute(model, tmp_path, evidence)
    assert model.state.primary is error and error.__cause__ is cause
    assert model.state.electrical_failure_context is partial
    assert model.state.init_dynamics_completed and not model.state.init_electrical_completed
    rows = {row["label"]: row for row in evidence.rows}
    last = rows[name + ".failure.last_raw_return"]
    assert transport.read(tmp_path / last["path"], expected_sha256=last["sha256"])[0] == {
        "float64_bits": "0000000000000080"
    }
    stored = rows[name + ".failure.stores"]
    assert transport.read(tmp_path / stored["path"], expected_sha256=stored["sha256"])[0][2] == {
        "bytes_hex": original.hex()
    }
    if writer_failure:
        assert (name + ".failure.before", secondary) in model.state.secondary
    assert json.loads((tmp_path / "outcome.json").read_text())["status"] == "failed"


def test_demo_init_electrical_failed_store_projection_does_not_hide_last_raw_value(tmp_path):
    state = stage.Execution("original", endpoint="init_electrical")
    state.primary = Falsey("field failure")
    raw = bytes.fromhex("0000000000000080")
    state.primary.partial = NS(stores=[object()], last_raw=(sys._getframe(), raw))
    state.operations = [dict(name="init_electrical", status="failed")]
    evidence = Evidence()
    stage._finish(state, evidence, tmp_path)
    assert dict(evidence.values)["init_electrical.failure.last_raw_return"] is raw
    assert any(name == "init_electrical.failure.stores" for name, _ in state.secondary)
    assert state.result is None and state.init_electrical_completed is False


@pytest.mark.parametrize("native_attribute", ["none", "falsey", "unavailable"])
def test_demo_init_electrical_storage_failure_uses_actual_attachment_contract(
    native_attribute, tmp_path
):
    class Partial(NS):
        def __bool__(self):
            return False

    class SourceError(Falsey):
        @property
        def init_storage_partial(self):
            if native_attribute == "unavailable":
                raise secondary
            return native if native_attribute == "falsey" else None

    state = stage.Execution("original", endpoint="init_electrical")
    secondary, cause = OSError("attachment observation failed"), KeyError("source cause")
    native = Partial(last_raw=(sys._getframe(), b"native raw"))
    fallback = NS(last_raw=(sys._getframe(), b"fallback raw"))
    state.primary = state.delegate_error = SourceError("storage failed")
    state.primary.__cause__, state.primary.partial = cause, fallback
    state.operations = [dict(name="init_storage", status="failed")]
    evidence = Evidence()
    stage._finish(state, evidence, tmp_path)
    expected = native if native_attribute == "falsey" else fallback
    assert state.electrical_failure_context is expected
    assert dict(evidence.values)["init_storage.failure.last_raw_return"] is expected.last_raw[1]
    assert state.primary is state.delegate_error and state.primary.__cause__ is cause
    assert (("init_storage.failure.context", secondary) in state.secondary) is (
        native_attribute == "unavailable"
    )
    assert state.result is None and state.init_storage_completed is False


@pytest.mark.parametrize(
    "where", ["poisson.record", "core.cache", "profiles.after", "junctions.record"]
)
def test_demo_capture_failure_keeps_raw_child_and_trial_before_next_stage(where, tmp_path):
    model, evidence = chain(), Evidence(fail=where)
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, evidence)
    label = where.split(".")[0]
    assert model.state.last_trial is model.owners[-1].saved
    assert model.state.owners[-1] == (label, model.owners[-1])
    assert model.state.delegate_error is None and model.state.result is None
    assert model.calls[-1] == label + ".trial"


@pytest.mark.parametrize("field_name", ["p", "cells", "sim", "dyna", "callbacks"])
def test_demo_equal_next_stage_cannot_replace_any_retained_phase_link(field_name, tmp_path):
    def mutate(name, owner, phase):
        if name == "core":
            setattr(phase, field_name, object())

    model = chain(mutate=mutate)
    with pytest.raises(ValueError, match="actual phase"):
        execute(model, tmp_path)
    assert model.calls[-1] == "core.trial" and "profiles_request" not in model.calls
    assert model.state.last_trial is model.owners[-1].saved


@pytest.mark.parametrize("label", ["poisson", "core", "junctions"])
def test_demo_mode_is_not_silently_changed_by_later_stage(label, tmp_path):
    def mutate(name, owner, phase):
        if name == label:
            owner.saved.flux_operator = "disabled"

    model = chain(mutate=mutate)
    with pytest.raises(ValueError, match="mode changed"):
        execute(model, tmp_path)
    assert model.state.flux_operator == "original" and model.state.result is None


def test_demo_falsey_delegate_primary_survives_forensic_and_final_writer_failures(
    tmp_path, monkeypatch
):
    primary, forensic, writer = Falsey("source"), OSError("forensics"), OSError("writer")
    model, evidence = chain(fail="core", primary=primary), Evidence(forensic_error=forensic)

    def refuse(*args, **kwargs):
        raise writer

    # Restore the shared writer before pytest's own call-report callback.
    with monkeypatch.context() as patch:
        patch.setattr(stage.snapshot, "write_json", refuse)
        with pytest.raises(Falsey) as caught:
            execute(model, tmp_path, evidence)
    assert caught.value is primary and caught.value.__cause__.args == ("original cause",)
    assert model.state.secondary == [("failure_forensics", forensic), ("outcome", writer)]
    assert not model.state.evidence_completed and "profiles_request" not in model.calls


def test_demo_session_exit_failure_retains_completed_endpoint_but_does_not_publish_success(
    tmp_path,
):
    primary = OSError("shared writer release")

    @contextmanager
    def session():
        yield
        raise primary

    model = chain()
    with pytest.raises(OSError) as caught:
        execute(model, tmp_path, session=session())
    assert caught.value is primary
    assert model.state.methods_completed and model.state.result is model.owners[-1]
    assert json.loads((tmp_path / "outcome.json").read_text())["status"] == "failed"


def test_demo_session_cannot_suppress_original_falsey_failure(tmp_path):
    primary = Falsey("same source")

    @contextmanager
    def session():
        try:
            yield
        except Falsey:
            pass

    model = chain(fail="profiles", primary=primary)
    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path, session=session())
    assert caught.value is primary and "junctions_request" not in model.calls


def test_demo_last_raw_return_survives_failed_owner_registration(tmp_path):
    primary = OSError("owner append")

    class Broken(list):
        def append(self, value):
            if value[0] == "core":
                raise primary
            super().append(value)

    model = chain()
    model.state.owners = Broken()
    with pytest.raises(OSError) as caught:
        execute(model, tmp_path)
    assert caught.value is primary
    assert model.state.last_return is model.owners[-1]
    assert model.owners[-1].name == "core" and "profiles_request" not in model.calls
    assert model.state.trials[-1][0] == "poisson"


@pytest.mark.parametrize(
    "path",
    [
        "/mnt/workspaces/Cells/../escape",
        "/tmp/out",
        "/mnt/workspaces/Cells",
        "relative/out",
    ],
)
def test_demo_output_containment_refuses_before_mutation(path):
    with pytest.raises(stage.DemoRejected) as caught:
        stage._output(path)
    assert caught.value.stage == "output"


def test_demo_public_reentry_is_sticky_and_preserves_existing_falsey_primary(monkeypatch):
    state, primary = stage.Execution("original"), Falsey("original")
    state.primary = primary
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setattr(stage, "_ACTIVE", [state])
    for _ in range(2):
        with pytest.raises(stage.DemoRejected):
            stage.run_demo(None, None, plan_sha256=None, enabled=True)
    assert state.primary is primary and len(state.secondary) == 2
    with pytest.raises(Falsey) as caught:
        stage._stop(state)
    assert caught.value is primary


@pytest.mark.parametrize("mode", [None, True, "repair", "both"])
def test_demo_prepare_never_repairs_or_combines_modes(mode):
    with pytest.raises(stage.DemoRejected) as caught:
        stage.prepare(
            None,
            None,
            inputs=None,
            inputs_sha256=None,
            python=None,
            bootstrap=None,
            bootstrap_sha256=None,
            auxiliary_configuration=None,
            flux_operator=mode,
        )
    assert caught.value.stage == "mode"


def test_demo_log_lease_blocks_competing_writer_and_survives_session_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(stage, "_PROCESS_LEASES", [])
    lock = tmp_path / "log.lock"
    first, second = stage.ProcessLogLease(lock), stage.ProcessLogLease(lock)
    try:
        with first:
            with pytest.raises(BlockingIOError):
                second.__enter__()
        assert first.fd is not None and stage._PROCESS_LEASES == [first]
        first.check()
        with pytest.raises(BlockingIOError):
            second.__enter__()
    finally:
        if first.fd is not None:
            os.close(first.fd)  # Test-only teardown; production waits for process exit.


@pytest.mark.parametrize("change", ["symlink", "permissions", "retarget"])
def test_demo_log_lease_refuses_noncanonical_file_or_changed_inode(change, tmp_path, monkeypatch):
    monkeypatch.setattr(stage, "_PROCESS_LEASES", [])
    lock = tmp_path / "log.lock"
    lease = stage.ProcessLogLease(lock)
    if change == "symlink":
        target = tmp_path / "target"
        target.touch(mode=0o600)
        lock.symlink_to(target)
        with pytest.raises(stage.DemoRejected):
            lease.__enter__()
    elif change == "permissions":
        lock.touch(mode=0o644)
        with pytest.raises(stage.DemoRejected):
            lease.__enter__()
        assert lease.fd is None
    else:
        lease.__enter__()
        try:
            lock.unlink()
            lock.touch(mode=0o600)
            with pytest.raises(stage.DemoRejected):
                lease.check()
        finally:
            os.close(lease.fd)


@pytest.mark.parametrize("protected", ["frozen_source", "packet", "input_program"])
def test_demo_preflight_protects_all_input_roots_before_callback_or_lease(
    protected, tmp_path, monkeypatch
):
    # Real Key output_path is metadata only. Its packet reader is isolated here
    # so no raw YAML, runtime bootstrap or actual parameter owner is executed.
    from validation.betse import betse_native_parameter_world_ready_qualification as parameter

    image, packet, raw = (tmp_path / name for name in ("image", "packet", "raw"))
    for path in (image, packet, raw):
        path.mkdir()
    output = {"frozen_source": image, "packet": packet, "input_program": raw}[protected] / "out"

    def read_packet(*args):
        return {"program": {"root": _DEMO_TEST_RAW}}  # noqa: F821 - isolated declared globals

    reader = FunctionType(read_packet.__code__, vars(parameter))
    monkeypatch.setattr(parameter, "_DEMO_TEST_RAW", str(raw), raising=False)
    monkeypatch.setattr(parameter, "packet_inputs", reader)
    monkeypatch.setattr(stage, "ROOT", image)
    monkeypatch.setenv(stage.RELEASE, "1")
    monkeypatch.setattr(stage, "_dependencies", lambda: {"parameters": parameter})
    monkeypatch.setattr(
        stage,
        "_read_plan",
        lambda *a: {
            "parameter_packet": str(packet),
            "parameter_sha256": "a" * 64,
            "endpoint": "seed",
        },
    )
    activity = []

    def forbidden(*args, **kwargs):
        activity.append((args, kwargs))
        raise AssertionError("No lease, writer or delegate may be reached")

    monkeypatch.setattr(stage, "_resources", forbidden)
    monkeypatch.setattr(stage, "_writer_session", forbidden)
    with pytest.raises(ValueError):
        stage.run_demo("unused", output, plan_sha256="b" * 64, enabled=True)
    assert activity == [] and not output.exists()
    assert stage._ACTIVE == [] and stage._ATTEMPT is None


@pytest.mark.parametrize("where", ["lock", "check", "registration"])
@pytest.mark.parametrize("kind", [ValueError, Falsey])
def test_demo_lease_entry_primary_survives_close_failure(where, kind, tmp_path, monkeypatch):
    primary, cleanup = kind("entry"), OSError("close")
    cause = KeyError("original cause")
    primary.__cause__ = cause
    lease = stage.ProcessLogLease(tmp_path / "double.lock")

    def fail_primary(*args, **kwargs):
        raise primary

    def fail_close(fd):
        raise cleanup

    class Broken(list):
        def append(self, value):
            raise primary

    with monkeypatch.context() as patch:
        if where == "lock":
            patch.setattr(stage.fcntl, "flock", fail_primary)
        elif where == "check":
            patch.setattr(lease, "check", fail_primary)
        else:
            patch.setattr(stage, "_PROCESS_LEASES", Broken())
        patch.setattr(stage.os, "close", fail_close)
        with pytest.raises(kind) as caught:
            lease.__enter__()
        assert caught.value is primary and caught.value.__cause__ is cause
        assert lease.entry_error is primary and lease.cleanup_errors == (cleanup,)
        assert lease.fd is not None
    os.close(lease.fd)


def init_chain(*, mode="original", fail=None, mutate=None):
    """Private orchestration adapter; it cannot create a real native owner."""
    model = chain(mode=mode)
    model.state.endpoint = model.plan["endpoint"] = "init_setup"
    model.phase.cache = object()
    model.init_objects = []

    def request(parent, *, law_id):
        model.calls.append("init_setup_request")
        assert parent is model.owners[-1] and parent.name == "junctions"
        assert not parent.consumed and law_id == "init_setup"
        if fail == "request":
            raise model.primary
        return NS(parent=parent)

    def prepare(request, *, enabled):
        model.calls.append("init_setup")
        assert enabled is True
        request.parent.consumed = True
        if fail == "source":
            raise model.primary
        phase = NS(
            p=model.p,
            cells=model.phase.cells,
            callbacks=model.phase.callbacks,
            sim=NS(molecules=None),
            dyna=object(),
            cache=object(),
        )
        trial = NS(
            source_completed=True,
            identity="init_setup",
            parent_identity=request.parent.saved.identity,
            before=("before-init",),
            after=("after-init",),
            parameter_record=object(),
        )

        class Child:
            consumed = False

            @property
            def phase(self):
                assert not self.consumed, "Consumed INIT owner was reopened"
                model.calls.append("init_setup.phase")
                if fail == "phase":
                    raise model.primary
                return phase

            @property
            def trial(self):
                assert not self.consumed, "Consumed INIT owner was reopened"
                model.calls.append("init_setup.trial")
                if fail == "trial":
                    raise model.primary
                return trial

        child = Child()
        model.init_objects.append((child, phase, trial))
        if mutate is not None:
            replacement = mutate(model, phase, trial)
            if replacement is not None:
                phase = replacement
                model.init_objects[-1] = (child, phase, trial)
        return child

    model.modules["init_setup"] = NS(
        LAW_ID="init_setup",
        from_seed=request,
        prepare=prepare,
        trial_record=lambda trial: dict(identity=trial.identity, parent=trial.parent_identity),
    )
    return model


@pytest.mark.parametrize("mode", stage.FLUX_MODES)
def test_demo_init_setup_same_process_retains_tissue_and_creates_new_constructor_objects(
    mode, tmp_path
):
    model, evidence = init_chain(mode=mode), Evidence()
    result = execute(model, tmp_path, evidence)
    child, phase, trial = model.init_objects[0]
    assert result.result is child and result.phase is result.init_phase is phase
    assert result.seed_phase is model.phase and result.seed_trial is model.owners[-1].saved
    assert all(
        actual is expected
        for actual, expected in zip(
            result.seed_links,
            (
                model.p,
                model.phase.cells,
                model.phase.sim,
                model.phase.dyna,
                model.phase.callbacks,
                model.phase.cache,
            ),
            strict=True,
        )
    )
    assert result.parameters is phase.p is model.p
    assert phase.cells is model.phase.cells and phase.callbacks is model.phase.callbacks
    assert all(getattr(phase, k) is not getattr(model.phase, k) for k in ("sim", "dyna", "cache"))
    assert all(owner.consumed for owner in model.owners)
    assert model.calls[-4:] == [
        "init_setup_request",
        "init_setup",
        "init_setup.trial",
        "init_setup.phase",
    ]
    assert result.trials[-1] == ("init_setup", trial)
    assert evidence.values[-3:] == [
        ("init_setup.record", {"identity": "init_setup", "parent": "junctions"}),
        ("init_setup.before", trial.before),
        ("init_setup.after", trial.after),
    ]
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "completed" and outcome["endpoint"] == "init_setup"
    assert outcome["init_setup_completed"] is True and outcome["init_time_steps_completed"] == 0
    assert outcome["flux_operator"] == mode and outcome["scientific_or_physical_credit"] == 0


@pytest.mark.parametrize("field", ["p", "cells", "callbacks", "sim", "dyna", "cache"])
def test_demo_init_setup_refuses_retained_replacements_and_reused_new_objects(field, tmp_path):
    def mutate(model, phase, _trial):
        setattr(
            phase,
            field,
            getattr(model.phase, field) if field in ("sim", "dyna", "cache") else object(),
        )

    model = init_chain(mutate=mutate)
    with pytest.raises(ValueError, match="fresh INIT phase"):
        execute(model, tmp_path)
    child, phase, trial = model.init_objects[0]
    assert model.state.init_phase is phase and model.state.last_trial is trial
    assert model.state.last_return is child and model.state.seed_trial is model.owners[-1].saved
    assert not model.state.methods_completed and model.state.result is None
    assert model.state.phase is model.phase


@pytest.mark.parametrize(
    "field,value",
    [("source_completed", False), ("parent_identity", "wrong"), ("parameter_record", None)],
)
def test_demo_init_setup_refuses_incomplete_or_wrong_parent_trial(field, value, tmp_path):
    model = init_chain(mutate=lambda _m, _p, trial: setattr(trial, field, value))
    with pytest.raises(ValueError, match="fresh INIT phase"):
        execute(model, tmp_path)
    assert model.state.last_trial is model.init_objects[0][2]
    assert model.state.result is None


def test_demo_init_setup_cannot_relabel_existing_seed_phase(tmp_path):
    model = init_chain(mutate=lambda model, _phase, _trial: model.phase)
    with pytest.raises(ValueError, match="fresh INIT phase"):
        execute(model, tmp_path)
    assert model.state.init_phase is model.phase and model.state.result is None


@pytest.mark.parametrize("failure", ["request", "source", "trial", "phase"])
def test_demo_init_setup_failure_keeps_completed_seed_and_original_cause(failure, tmp_path):
    model = init_chain(fail=failure)
    with pytest.raises(ValueError) as caught:
        execute(model, tmp_path)
    assert caught.value is model.primary and caught.value.__cause__.args == ("original cause",)
    assert model.state.seed_trial is model.owners[-1].saved
    assert model.state.seed_phase is model.phase
    assert model.owners[-1].consumed is (failure != "request")
    assert model.state.result is None and not model.state.methods_completed
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "failed" and "junctions" in outcome["completed_stage_trials"]


@pytest.mark.parametrize("label", ["init_setup.record", "init_setup.before", "init_setup.after"])
def test_demo_init_setup_capture_failure_retains_actual_child_without_completion(label, tmp_path):
    model = init_chain()
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, Evidence(fail=label))
    child, phase, trial = model.init_objects[0]
    assert model.state.owners[-1] == ("init_setup", child)
    assert model.state.last_trial is trial and model.state.init_phase is phase
    assert model.state.result is None and not model.state.methods_completed
    assert model.calls[-1] == "init_setup.phase"


@pytest.mark.parametrize("endpoint", [None, True, "INIT", "sim", "init_setup"])
def test_demo_init_setup_endpoint_mismatch_refuses_before_first_delegate(endpoint, tmp_path):
    model = chain()
    model.state.endpoint = endpoint
    with pytest.raises(ValueError, match="Exact declared demonstration endpoint"):
        execute(model, tmp_path)
    assert model.calls == [] and not model.state.owners


def test_demo_init_setup_unadopted_producer_refuses_before_import_or_legacy_mutation(monkeypatch):
    base = stage.source_plan()
    monkeypatch.setattr(
        stage.snapshot, "digest", lambda *_a: pytest.fail("Unadopted route inspected producers")
    )
    monkeypatch.setattr(
        stage.importlib, "import_module", lambda *_a: pytest.fail("Unexpected import")
    )
    with pytest.raises(stage.DemoRejected) as caught:
        stage._dependencies("init_setup")
    assert caught.value.stage == "init_unbound"
    assert stage.source_plan() == base and stage._ATTEMPT is None and not stage._ACTIVE
    with pytest.raises(stage.DemoRejected, match="INIT producer unavailable"):
        stage.Modules("seed")["init_setup"]
    proposal = stage.source_plan(endpoint="init_setup")
    assert proposal["stages"] == (*stage.STAGES, "init_setup")
    assert proposal["selected_endpoint"] == "init_setup"
    assert proposal["optional_init_setup"]["checkpoint_or_time_loop_admission"] is False


@pytest.mark.parametrize("endpoint", stage.ENDPOINTS)
def test_demo_init_setup_plan_binds_selected_endpoint_and_full_stage_roster(
    endpoint, tmp_path, monkeypatch
):
    path = tmp_path / "plan.json"
    value = dict(
        kind=stage.KIND,
        source_plan=stage.source_plan(endpoint=endpoint),
        snapshot_sha256="a" * 64,
        parameter_packet="packet",
        parameter_sha256="b" * 64,
        callback_bootstrap="bootstrap",
        callback_bootstrap_sha256="c" * 64,
        auxiliary_configuration={},
        shared_writer_review="writer",
        flux_operator="original",
        endpoint=endpoint,
        policy=stage.POLICY,
        held=True,
    )
    path.write_text(json.dumps(value))
    calls = []
    monkeypatch.setattr(
        stage.snapshot, "verify", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    assert stage._read_plan(path, stage.snapshot.digest(path))["endpoint"] == endpoint
    assert len(calls) == 1
    value["endpoint"] = "init_setup" if endpoint == "seed" else "seed"
    path.write_text(json.dumps(value))
    with pytest.raises(stage.DemoRejected, match="single-mode plan changed"):
        stage._read_plan(path, stage.snapshot.digest(path))
    assert len(calls) == 1


@pytest.mark.parametrize("endpoint", [None, True, "sim", "INIT"])
def test_demo_init_setup_prepare_invalid_endpoint_never_loads_producers(endpoint, monkeypatch):
    monkeypatch.setattr(
        stage.importlib, "import_module", lambda *_a: pytest.fail("Unexpected import")
    )
    with pytest.raises(stage.DemoRejected, match="exactly seed or init_setup"):
        stage.prepare(
            "unused",
            "unused",
            inputs="unused",
            inputs_sha256="a" * 64,
            python="unused",
            bootstrap="unused",
            bootstrap_sha256="b" * 64,
            auxiliary_configuration={},
            flux_operator="original",
            endpoint=endpoint,
        )


def prelude_chain(*, mode="original", fail=None, mutate=None):
    """Private orchestration protocol only; no actual native owner is issued."""
    model = init_chain(mode=mode)
    model.state.endpoint = model.plan["endpoint"] = "init_prelude"
    model.prelude_objects = []

    def check(label):
        model.calls.append("init_prelude." + label)
        if fail == label:
            raise model.primary

    def request(parent, *, law_id):
        check("request")
        assert parent is model.init_objects[0][0]
        assert not parent.consumed and law_id == "init_prelude"
        return NS(parent=parent)

    def prepare(request, *, enabled):
        assert enabled is True and request.parent is model.init_objects[0][0]
        phase, parent_trial = model.init_objects[0][1:]
        request.parent.consumed = True
        check("source")
        raw = (None, ("retained-ion-return", [-0.0, 2.0]))
        trial = NS(
            source_completed=True,
            identity="init_prelude",
            parent_identity=parent_trial.identity,
            before=("before-prelude",),
            after=("after-prelude",),
            raw_returns=tuple((sys._getframe(), value) for value in raw),
        )

        class Child:
            consumed = False

            @property
            def trial(self):
                assert not self.consumed, "Consumed prelude owner was reopened"
                check("trial")
                return trial

            @property
            def phase(self):
                assert not self.consumed, "Consumed prelude owner was reopened"
                check("phase")
                return phase

        child = Child()
        if mutate is not None:
            replacement = mutate(model, phase, trial)
            if replacement is not None:
                phase = replacement
        model.prelude_objects.append((child, phase, trial))
        return child

    def record(trial):
        check("record")
        return dict(
            identity=trial.identity,
            parent=trial.parent_identity,
            returns=tuple((id(frame), id(raw)) for frame, raw in trial.raw_returns),
        )

    model.modules["init_prelude"] = NS(
        LAW_ID="init_prelude", from_init=request, prepare=prepare, trial_record=record
    )
    return model


@pytest.mark.parametrize("mode", stage.FLUX_MODES)
def test_demo_init_prelude_continues_same_init_owner_and_preserves_raw_returns(mode, tmp_path):
    model, evidence = prelude_chain(mode=mode), Evidence()
    result = execute(model, tmp_path, evidence)
    child, phase, trial = model.prelude_objects[0]
    parent, init_phase, init_trial = model.init_objects[0]
    assert result.result is child and result.phase is result.init_phase is phase is init_phase
    assert result.init_trial is init_trial and result.prelude_trial is result.last_trial is trial
    assert result.seed_phase is model.phase and result.seed_trial is model.owners[-1].saved
    assert parent.consumed
    with pytest.raises(AssertionError, match="Consumed INIT owner"):
        _ = parent.trial
    assert model.calls[-5:] == [
        "init_prelude.request",
        "init_prelude.source",
        "init_prelude.trial",
        "init_prelude.phase",
        "init_prelude.record",
    ]
    assert model.calls.count("init_setup.trial") == model.calls.count("init_setup.phase") == 1
    assert result.trials[-2:] == [("init_setup", init_trial), ("init_prelude", trial)]
    assert evidence.values[-1][0] == "init_prelude.raw_returns"
    projected = evidence.values[-1][1]
    assert all(value is raw for value, (_, raw) in zip(projected, trial.raw_returns, strict=True))
    assert all(type(frame).__name__ == "frame" for frame, _ in trial.raw_returns)
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "completed" and outcome["endpoint"] == "init_prelude"
    assert outcome["init_setup_completed"] is outcome["init_prelude_completed"] is True
    assert outcome["init_time_steps_completed"] == outcome["scientific_or_physical_credit"] == 0
    assert outcome["flux_operator"] == mode and outcome["original_flux_defect_repaired"] is False


@pytest.mark.parametrize("field", ["p", "cells", "sim", "dyna", "callbacks", "cache"])
def test_demo_init_prelude_refuses_retargeted_init_object_edges(field, tmp_path):
    model = prelude_chain(mutate=lambda _m, phase, _t: setattr(phase, field, object()))
    with pytest.raises(ValueError, match="exact phase, objects and parent"):
        execute(model, tmp_path)
    child, phase, trial = model.prelude_objects[0]
    assert model.state.owners[-1] == ("init_prelude", child)
    assert model.state.last_return is child and model.state.last_trial is trial
    assert model.state.prelude_phase is phase and model.state.init_setup_completed
    assert not model.state.init_prelude_completed and model.state.result is None
    assert model.calls[-1] == "init_prelude.phase"


def test_demo_init_prelude_refuses_equal_phase_replacement(tmp_path):
    model = prelude_chain(mutate=lambda _m, phase, _t: NS(**vars(phase)))
    with pytest.raises(ValueError, match="exact phase, objects and parent"):
        execute(model, tmp_path)
    assert model.state.prelude_phase is not model.state.init_phase
    assert model.state.result is None


@pytest.mark.parametrize(
    "field,value",
    [("source_completed", False), ("source_completed", 1), ("parent_identity", "seed")],
)
def test_demo_init_prelude_refuses_incomplete_or_wrong_parent_trial(field, value, tmp_path):
    model = prelude_chain(mutate=lambda _m, _p, trial: setattr(trial, field, value))
    with pytest.raises(ValueError, match="exact phase, objects and parent"):
        execute(model, tmp_path)
    assert model.state.last_trial is model.prelude_objects[0][2]
    assert model.state.init_trial is model.init_objects[0][2]
    assert model.state.result is None and not model.state.init_prelude_completed


@pytest.mark.parametrize("failure", ["request", "source", "trial", "phase", "record"])
@pytest.mark.parametrize("falsey", [False, True])
def test_demo_init_prelude_failure_keeps_original_cause_and_completed_init(
    failure, falsey, tmp_path
):
    class Error(ValueError):
        def __bool__(self):
            return not falsey

    model = prelude_chain(fail=failure)
    cause, error = KeyError("original source cause"), Error("prelude source failure")
    error.__cause__ = cause
    model.primary = error
    with pytest.raises(Error) as caught:
        execute(model, tmp_path)
    assert caught.value is error and error.__cause__ is cause
    assert model.state.primary is error and model.state.init_setup_completed
    assert model.state.init_trial is model.init_objects[0][2]
    assert model.state.seed_trial is model.owners[-1].saved
    assert model.init_objects[0][0].consumed is (failure != "request")
    assert model.state.result is None and not model.state.methods_completed
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "failed" and outcome["init_setup_completed"] is True
    assert outcome["init_prelude_completed"] is False and outcome["init_time_steps_completed"] == 0


@pytest.mark.parametrize("label", ["record", "before", "after", "raw_returns"])
def test_demo_init_prelude_capture_failure_retains_child_and_parent(label, tmp_path):
    model, evidence = prelude_chain(), Evidence(fail="init_prelude." + label)
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, evidence)
    child, phase, trial = model.prelude_objects[0]
    assert model.state.owners[-1] == ("init_prelude", child)
    assert model.state.prelude_phase is phase and model.state.last_trial is trial
    assert model.state.init_trial is model.init_objects[0][2]
    assert model.state.init_setup_completed and not model.state.init_prelude_completed
    assert model.state.result is None and model.calls[-1] == "init_prelude.record"


def test_demo_init_prelude_never_runs_after_init_capture_failure(tmp_path):
    model = prelude_chain()
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, Evidence(fail="init_setup.after"))
    assert not any(name.startswith("init_prelude") for name in model.calls)
    assert not model.prelude_objects and model.state.init_trial is model.init_objects[0][2]
    assert not model.state.init_setup_completed


def test_demo_init_prelude_unadopted_gate_precedes_import_and_source_reads(monkeypatch):
    monkeypatch.setattr(stage, "INIT_SOURCE_PINS", dict.fromkeys(stage.INIT_MODULES, "a" * 64))
    monkeypatch.setattr(stage, "INIT_REVIEW_PINS", dict.fromkeys(stage.INIT_MODULES, "b" * 64))
    monkeypatch.setattr(stage.snapshot, "digest", lambda *_: pytest.fail("Unexpected source read"))
    monkeypatch.setattr(
        stage.importlib, "import_module", lambda *_: pytest.fail("Unexpected import")
    )
    with pytest.raises(stage.DemoRejected) as caught:
        stage._dependencies("init_prelude")
    assert caught.value.stage == "prelude_unbound"
    assert stage._ATTEMPT is None and not stage._ACTIVE
    for endpoint in stage.ENDPOINTS:
        with pytest.raises(stage.DemoRejected, match="prelude producer unavailable"):
            stage.Modules(endpoint)["init_prelude"]
    plan = stage.source_plan(endpoint="init_prelude")
    assert plan["stages"] == (*stage.STAGES, "init_setup", "init_prelude")
    assert plan["optional_init_prelude"]["source_pins"] == {"init_prelude": None}
    assert plan["optional_init_prelude"]["checkpoint_or_time_loop_admission"] is False


@pytest.mark.parametrize("name", ["from_init", "prepare", "_execute"])
def test_demo_init_prelude_runner_blocks_actual_entry_metadata(name):
    def metadata():
        pass

    frame = NS(
        f_globals={"__name__": "cells.processes.betse_native_init_dynamics_prelude"},
        f_code=metadata.__code__.replace(co_name=name),
    )
    assert software.is_forbidden_frame(frame)


def dynamics_chain(*, mode="original", fail=None, mutate=None):
    """Synthetic public-protocol consumer only; no producer claim or RNG call."""
    model = prelude_chain(mode=mode)
    model.state.endpoint = model.plan["endpoint"] = "init_dynamics"
    model.dynamics_objects, model.file_inputs = [], ()
    original = model.modules["init_setup"].prepare

    def initial(request, *, enabled):
        child = original(request, enabled=enabled)
        # Install the synthetic handler before its first consumer observation.
        model.init_objects[0][1].dyna = NS(tissue_name_to_profile={})
        return child

    model.modules["init_setup"].prepare = initial

    def check(label):
        model.calls.append("init_dynamics." + label)
        if fail == label:
            raise model.primary

    def request(parent, *, law_id, file_inputs):
        check("request")
        assert parent is model.prelude_objects[0][0] and not parent.consumed
        assert law_id == "init_dynamics"
        model.file_inputs = file_inputs
        return NS(parent=parent, file_inputs=file_inputs)

    def prepare(request, *, enabled):
        assert enabled is True and request.parent is model.prelude_objects[0][0]
        request.parent.consumed = True
        check("source")
        phase, parent = model.prelude_objects[0][1:]
        stream_before, stream_after, draw = ("before-MT",), ("after-MT",), [-0.0, 0.5]
        trial = NS(
            source_completed=True,
            identity="init_dynamics",
            parent_identity=parent.identity,
            before=("before-dynamics",),
            after=("after-dynamics",),
            stream_before=stream_before,
            stream_after=stream_after,
            rng_calls=(
                NS(
                    index=0,
                    library="numpy",
                    operation="random",
                    before=stream_before,
                    after=stream_after,
                    raw_return=draw,
                    returned=True,
                    primary=None,
                    capture_errors=(),
                ),
            ),
            tissue_record=NS(
                completion_claim=object(),
                init_trial=model.init_objects[0][2],
                calls=(("init_profiles", {}), ("init_events", {})),
                source_completed=True,
                work_views_are_non_additive=True,
            ),
            raw_returns=((sys._getframe(), None), (sys._getframe(), draw)),
        )

        class Child:
            @property
            def trial(self):
                check("trial")
                return trial

            @property
            def phase(self):
                check("phase")
                return phase

        child = Child()
        if mutate is not None:
            replacement = mutate(model, phase, trial)
            if replacement is not None:
                phase = replacement
        model.dynamics_objects.append((child, phase, trial))
        return child

    def record(trial):
        check("record")
        return dict(parent=trial.parent_identity, source_completed=trial.source_completed)

    model.modules["init_dynamics"] = NS(
        LAW_ID="init_dynamics", from_prelude=request, prepare=prepare, trial_record=record
    )
    model.modules["init_tissue"] = object()
    model.module_loads = []

    class Modules(dict):
        def __getitem__(self, key):
            model.module_loads.append(key)
            if key == "init_tissue" and fail == "import":
                raise model.primary
            if key == "init_dynamics":
                assert "init_tissue" in model.module_loads
            return super().__getitem__(key)

    model.modules = Modules(model.modules)
    return model


@pytest.mark.parametrize("mode", stage.FLUX_MODES)
def test_demo_init_dynamics_preserves_whole_lineage_and_raw_rng_without_reopening_parent(
    mode, tmp_path
):
    model, evidence = dynamics_chain(mode=mode), Evidence()
    result = execute(model, tmp_path, evidence)
    child, phase, trial = model.dynamics_objects[0]
    parent, _, previous_trial = model.prelude_objects[0]
    assert result.result is child and result.dynamics_phase is phase is result.init_phase
    assert result.dynamics_trial is result.last_trial is trial
    assert (
        result.prelude_trial is previous_trial
        and result.init_trial is trial.tissue_record.init_trial
    )
    assert parent.consumed and model.init_objects[0][0].consumed
    with pytest.raises(AssertionError, match="Consumed prelude"):
        _ = parent.trial
    assert model.calls.count("init_prelude.trial") == 1
    assert model.calls.count("init_prelude.phase") == 1
    assert model.module_loads[-2:] == ["init_tissue", "init_dynamics"]
    assert model.calls[-5:] == [
        "init_dynamics." + n for n in ("request", "source", "trial", "phase", "record")
    ]
    captured = dict(evidence.values)
    assert captured["init_dynamics.stream_before"] is trial.stream_before
    assert captured["init_dynamics.stream_after"] is trial.stream_after
    assert captured["init_dynamics.rng_calls"][0]["raw_return"] is trial.rng_calls[0].raw_return
    assert captured["init_dynamics.raw_returns"][1] is trial.raw_returns[1][1]
    assert captured["init_dynamics.tissue_record"]["live_claim_or_frame_serialization"] is False
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "completed" and outcome["init_dynamics_completed"] is True
    assert outcome["flux_operator"] == mode and outcome["original_flux_defect_repaired"] is False
    assert outcome["init_time_steps_completed"] == outcome["scientific_or_physical_credit"] == 0
    assert outcome["completed_stage_trials"][-3:] == ["init_setup", "init_prelude", "init_dynamics"]


@pytest.mark.parametrize("field", ["p", "cells", "sim", "dyna", "callbacks", "cache", "phase"])
def test_demo_init_dynamics_rejects_replacement_after_retaining_child(field, tmp_path):
    def mutate(_model, phase, _trial):
        if field == "phase":
            return NS(**vars(phase))
        setattr(phase, field, object())

    model = dynamics_chain(mutate=mutate)
    with pytest.raises(ValueError, match="exact lineage"):
        execute(model, tmp_path)
    child, phase, trial = model.dynamics_objects[0]
    assert model.state.owners[-1] == ("init_dynamics", child)
    assert model.state.dynamics_phase is phase and model.state.last_trial is trial
    assert not model.state.init_dynamics_completed and model.state.result is None
    assert model.calls[-1] == "init_dynamics.phase"


@pytest.mark.parametrize(
    "mutation",
    [
        "incomplete",
        "parent",
        "tissue",
        "tissue_parent",
        "tissue_order",
        "additive",
        "rng_absent",
        "rng_index",
        "rng_return",
        "rng_primary",
        "rng_capture",
    ],
)
def test_demo_init_dynamics_refuses_incomplete_lineage_or_rng_evidence(mutation, tmp_path):
    def mutate(model, _phase, trial):
        if mutation == "incomplete":
            trial.source_completed = 1
        elif mutation == "parent":
            trial.parent_identity = model.state.init_trial.identity
        elif mutation == "tissue":
            trial.tissue_record = None
        elif mutation == "tissue_parent":
            trial.tissue_record.init_trial = NS(**vars(model.state.init_trial))
        elif mutation == "tissue_order":
            trial.tissue_record.calls = trial.tissue_record.calls[::-1]
        elif mutation == "additive":
            trial.tissue_record.work_views_are_non_additive = False
        elif mutation == "rng_absent":
            trial.rng_calls = ()
        else:
            field, value = {
                "rng_index": ("index", 1),
                "rng_return": ("returned", False),
                "rng_primary": ("primary", Falsey("source")),
                "rng_capture": ("capture_errors", (OSError("capture"),)),
            }[mutation]
            setattr(trial.rng_calls[0], field, value)

    model = dynamics_chain(mutate=mutate)
    with pytest.raises(ValueError, match="exact lineage"):
        execute(model, tmp_path)
    assert model.state.last_trial is model.dynamics_objects[0][2]
    assert model.state.init_prelude_completed and not model.state.init_dynamics_completed


@pytest.mark.parametrize("failure", ["request", "source", "trial", "phase", "record"])
@pytest.mark.parametrize("falsey", [False, True])
def test_demo_init_dynamics_failures_retain_exact_primary_parent_and_consumption(
    failure, falsey, tmp_path
):
    model = dynamics_chain(fail=failure)
    cause = KeyError("native source cause")
    model.primary = (Falsey if falsey else ValueError)("dynamics failure")
    model.primary.__cause__ = cause
    with pytest.raises(ValueError) as caught:
        execute(model, tmp_path)
    assert caught.value is model.state.primary is model.primary and caught.value.__cause__ is cause
    assert model.state.prelude_trial is model.prelude_objects[0][2]
    assert model.prelude_objects[0][0].consumed is (failure != "request")
    assert model.state.init_prelude_completed and not model.state.init_dynamics_completed
    assert model.state.result is None and not model.state.methods_completed


@pytest.mark.parametrize(
    "label",
    [
        "record",
        "before",
        "after",
        "stream_before",
        "stream_after",
        "rng_calls",
        "tissue_record",
        "raw_returns",
    ],
)
def test_demo_init_dynamics_capture_refusal_keeps_raw_trial_and_all_parent_history(label, tmp_path):
    model, evidence = dynamics_chain(), Evidence(fail="init_dynamics." + label)
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, evidence)
    child, phase, trial = model.dynamics_objects[0]
    assert model.state.owners[-1] == ("init_dynamics", child)
    assert model.state.last_trial is trial and model.state.dynamics_phase is phase
    assert model.state.prelude_trial is model.prelude_objects[0][2]
    assert model.state.init_trial is model.init_objects[0][2]
    assert model.state.result is None and not model.state.init_dynamics_completed


def test_demo_init_dynamics_does_not_retire_parent_after_incomplete_prelude_capture(tmp_path):
    model = dynamics_chain()
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, Evidence(fail="init_prelude.after"))
    assert not model.prelude_objects[0][0].consumed
    assert not model.dynamics_objects and not any(
        n.startswith("init_dynamics") for n in model.calls
    )


def test_demo_init_dynamics_participant_import_failure_preserves_unconsumed_prelude(tmp_path):
    model = dynamics_chain(fail="import")
    with pytest.raises(ValueError) as caught:
        execute(model, tmp_path)
    assert caught.value is model.primary and caught.value.__cause__.args == ("original cause",)
    assert model.state.prelude_trial is model.prelude_objects[0][2]
    assert not model.prelude_objects[0][0].consumed and not model.dynamics_objects
    assert model.module_loads[-1] == "init_tissue" and "init_dynamics" not in model.module_loads


def test_demo_init_dynamics_unadopted_gate_refuses_before_producer_reads_or_imports(monkeypatch):
    for source, review, modules in (
        ("INIT_SOURCE_PINS", "INIT_REVIEW_PINS", stage.INIT_MODULES),
        ("PRELUDE_SOURCE_PINS", "PRELUDE_REVIEW_PINS", stage.PRELUDE_MODULES),
    ):
        monkeypatch.setattr(stage, source, dict.fromkeys(modules, "a" * 64))
        monkeypatch.setattr(stage, review, dict.fromkeys(modules, "b" * 64))
    monkeypatch.setattr(stage.snapshot, "digest", lambda *_: pytest.fail("Unexpected source read"))
    monkeypatch.setattr(
        stage.importlib, "import_module", lambda *_: pytest.fail("Unexpected import")
    )
    with pytest.raises(stage.DemoRejected) as caught:
        stage._dependencies("init_dynamics")
    assert caught.value.stage == "dynamics_unbound" and stage._ATTEMPT is None and not stage._ACTIVE
    for endpoint in stage.ENDPOINTS:
        for name in stage.COMPLETION_MODULES:
            with pytest.raises(stage.DemoRejected, match="dynamics producer unavailable"):
                stage.Modules(endpoint)[name]
    plan = stage.source_plan(endpoint="init_dynamics")
    assert plan["stages"] == (*stage.STAGES, "init_setup", "init_prelude", "init_dynamics")
    assert all(pin is None for pin in plan["optional_init_dynamics"]["source_pins"].values())
    assert not plan["optional_init_dynamics"]["checkpoint_or_time_loop_admission"]


@pytest.mark.parametrize(
    "module,names",
    [
        (
            "betse_native_init_dynamics_completion",
            ("from_prelude", "prepare", "_execute", "_finish", "rng_call"),
        ),
        (
            "betse_native_init_tissue_dynamics",
            ("bind_completion", "dispatch", "finish", "_helper_call", "_make_mask"),
        ),
    ],
)
def test_demo_init_dynamics_runner_blocks_actual_source_and_rng_entry(module, names):
    def metadata():
        pass

    for name in names:
        frame = NS(
            f_globals={"__name__": "cells.processes." + module},
            f_code=metadata.__code__.replace(co_name=name),
        )
        assert software.is_forbidden_frame(frame)


def test_demo_init_dynamics_bitmap_declaration_is_original_deduplicated_and_passed_to_request(
    image_declarations, tmp_path
):
    b = image_declarations
    model = dynamics_chain()
    model.p = NS(grad_bm_fn=b.names[1], conf_dirname=str(b.root), molecules_enabled=False)
    model.ready.parameters = model.p
    model.phase.p = model.p
    original_parameters = model.modules["parameters"].acquire_world_ready

    def parameters(*args, **kwargs):
        ready, _ = original_parameters(*args, **kwargs)
        return ready, model.p

    model.modules["parameters"].acquire_world_ready = parameters
    model.state.input_root = b.root
    initial = model.modules["init_setup"].prepare

    def prepare(request, *, enabled):
        child = initial(request, enabled=enabled)
        model.init_objects[0][1].dyna.tissue_name_to_profile = {"image": b.profiles["0"]}
        return child

    model.modules["init_setup"].prepare = prepare
    dict.__getitem__(model.modules, "init_dynamics").files = b.module.files
    result = execute(model, tmp_path)
    assert result.init_dynamics_completed
    assert result.dynamics_file_inputs is model.file_inputs
    assert [v.filename for v in model.file_inputs] == [str(b.root / n) for n in b.names]
    assert [r["name"] for r in result.operations][-4:] == [
        "init_dynamics_file",
        "init_dynamics_file",
        "init_dynamics_request",
        "init_dynamics",
    ]
    for value in model.file_inputs:
        b.module.files._verify_file(value)
    b.state.parameters = NS(grad_bm_fn=b.names[0], conf_dirname=str(b.root))
    assert len(stage._profile_image_inputs(b.state, b.module, include_bitmap=True)) == 2


@pytest.mark.parametrize(
    "mutation", ["outside", "unknown", "bits", "bitmap_type", "directory_type"]
)
def test_demo_init_dynamics_bitmap_refusal_keeps_original_file_evidence(
    image_declarations, mutation
):
    b = image_declarations
    b.profiles.pop("1")
    b.state.parameters = NS(grad_bm_fn=b.names[1], conf_dirname=str(b.root))
    if mutation == "outside":
        b.state.parameters.grad_bm_fn = "../outside.png"
    elif mutation == "unknown":
        b.state.parameters.grad_bm_fn = "new.png"
    elif mutation == "bitmap_type":
        b.state.parameters.grad_bm_fn = b.root / b.names[1]
    elif mutation == "directory_type":
        b.state.parameters.conf_dirname = b.root
    else:
        path = b.root / b.names[1]
        path.chmod(0o644)
        path.write_bytes(b"changed input, never decoded")
        path.chmod(0o444)
    with pytest.raises(ValueError):
        stage._profile_image_inputs(b.state, b.module, include_bitmap=True)
    if mutation in ("outside", "unknown", "bits"):
        assert b.state.last_return.filename == str(b.root / b.names[0])
    else:
        assert b.state.last_return is None


@pytest.mark.parametrize("failure_mode", ["source", "first_capture"])
@pytest.mark.parametrize("writer_fails", [False, True])
def test_demo_init_dynamics_failure_values_are_durably_saved_independently(
    failure_mode, writer_fails, tmp_path
):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    model = dynamics_chain()
    primary, cause, secondary = (
        Falsey("original dynamics failure"),
        KeyError("cause"),
        OSError("first forensic writer"),
    )
    primary.__cause__ = cause
    raw, before, after = [-0.0, b"\x00\xff"], ("rng-before",), ("rng-after",)
    context = NS(
        before=("before-source",),
        stream_before=before,
        current_streams=after,
        rng_calls=[
            NS(
                index=0,
                library="numpy",
                operation="random",
                before=before,
                after=after,
                raw_return=raw,
                returned=True,
                primary=None,
                capture_errors=(),
            )
        ],
        raw_returns=[(sys._getframe(), raw)],
        last_raw=(sys._getframe(), raw),
        last_rng_return=raw,
    )
    if failure_mode == "source":

        def fail(request, *, enabled):
            assert enabled is True
            request.parent.consumed = True
            primary.init_dynamics_completion_partial = context
            raise primary

        dict.__getitem__(model.modules, "init_dynamics").prepare = fail

    class SavedEvidence(Recorder):
        def __init__(self):
            super().__init__(tmp_path, sidecars=True, capture_writer=stage._evidence_writer())
            self.attempts = []

        def save(self, label, value):
            self.attempts.append(label)
            if label == "init_dynamics.record" and failure_mode == "first_capture":
                raise primary
            if label == "init_dynamics.failure.before" and writer_fails:
                raise secondary
            return super().save(label, value)

    evidence = SavedEvidence()
    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path, evidence)
    assert caught.value is model.state.primary is primary and caught.value.__cause__ is cause
    assert model.state.init_prelude_completed and not model.state.init_dynamics_completed
    assert model.state.result is None and model.prelude_objects[0][0].consumed
    if failure_mode == "source":
        assert model.state.dynamics_trial is None
        assert model.state.dynamics_failure_context is context
    else:
        assert model.state.dynamics_trial is model.dynamics_objects[0][2]
    if writer_fails:
        assert ("init_dynamics.failure.before", secondary) in model.state.secondary
    saved = {}
    for row in evidence.rows:
        if row["label"].startswith("init_dynamics.failure.") and row["status"] == "saved":
            path = tmp_path / row["path"]
            saved[row["label"]] = transport.read(path, expected_sha256=row["sha256"])
            assert transport.files(path, expected_sha256=row["sha256"])
    assert saved["init_dynamics.failure.rng_calls"][0]["raw_return"][0] == {
        "float64_bits": "0000000000000080"
    }
    assert saved["init_dynamics.failure.raw_returns"]
    if failure_mode == "source":
        assert saved["init_dynamics.failure.current_streams"] == list(after)
        assert saved["init_dynamics.failure.last_rng_return"][1] == {"bytes_hex": "00ff"}
    assert saved["init_dynamics.failure.primary"]["live_claim_or_frame_serialization"] is False
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "failed" and outcome["scientific_or_physical_credit"] == 0
    attempts = {row["label"]: row["status"] for row in outcome["dynamics_failure_captures"]}
    assert len(attempts) == 11
    assert attempts["init_dynamics.failure.before"] == (
        "capture_failed" if writer_fails else "saved"
    )
    assert attempts["init_dynamics.failure.raw_returns"] == "saved"


def test_demo_init_dynamics_failure_projection_error_keeps_later_raw_return(tmp_path):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    state = stage.Execution("original", endpoint="init_dynamics")
    state.primary = Falsey("source")
    raw = [-0.0]
    state.primary.init_dynamics_completion_partial = NS(
        rng_calls=[object()], raw_returns=[(sys._getframe(), raw)], last_rng_return=raw
    )
    state.operations = [dict(name="init_dynamics", status="failed")]
    evidence = Recorder(tmp_path, sidecars=True, capture_writer=stage._evidence_writer())
    stage._finish(state, evidence, tmp_path)
    assert any(name == "init_dynamics.failure.rng_calls" for name, _ in state.secondary)
    row = next(r for r in evidence.rows if r["label"] == "init_dynamics.failure.last_rng_return")
    assert transport.read(tmp_path / row["path"], expected_sha256=row["sha256"]) == [
        {"float64_bits": "0000000000000080"}
    ]
    assert json.loads((tmp_path / "outcome.json").read_text())["status"] == "failed"


@dataclass
class StepSnapshot:
    """Serializable private protocol data; never an issued source snapshot/owner."""

    identity: str
    value: object


def first_step_chain(*, mode="original", fail=None, mutate=None, loop_returned=False):
    model = electrical_chain(mode=mode)
    model.state.endpoint = model.plan["endpoint"] = "init_first_step"
    model.step_objects = []

    def point(label):
        model.calls.append("init_first_step." + label)
        if fail == label:
            raise model.primary

    def request(parent, *, law_id):
        point("request")
        assert parent is model.field_objects["init_electrical"][0] and not parent.consumed
        assert model.state.electrical_trial is model.field_objects["init_electrical"][2]
        assert law_id == "init_first_step"
        return NS(parent=parent, identity="first-step-request")

    def prepare(request, *, enabled):
        assert enabled is True
        assert request.parent is model.field_objects["init_electrical"][0]
        request.parent.consumed = True
        point("source")
        _, phase, parent = model.field_objects["init_electrical"]
        raw = [-0.0, b"\x00\xff"]
        trial = NS(
            request_identity=request.identity,
            parent_identity=parent.identity,
            identity="9" * 64,
            before=StepSnapshot("1" * 64, ("before",)),
            after=StepSnapshot("2" * 64, ("after",)),
            calendar=StepSnapshot("3" * 64, (0.0, 0.4, 0.8)),
            sampled=StepSnapshot("4" * 64, (0.0, 0.8)),
            source_time_label=StepSnapshot("5" * 64, 0.0),
            configured_dt=StepSnapshot("6" * 64, 0.4),
            loop_index=0,
            iteration_complete=True,
            loop_returned=loop_returned,
            selected_stop=not loop_returned,
            work=({"code": prepare.__code__, "body_started": True, "returned": True},),
            stores=((1158, "fluxes_gj", b"old", raw, True, True),),
            raw_returns=((sys._getframe(), None), (sys._getframe(), raw)),
            stream_before=parent.rng_after,
            stream_after=("c" * 64, "d" * 64),
        )
        if mutate is not None:
            changed = mutate(model, phase, trial)
            if changed is not None:
                phase = changed

        class Child:
            @property
            def trial(self):
                point("trial")
                return trial

            @property
            def phase(self):
                point("phase")
                return phase

        child = Child()
        model.step_objects.append((child, phase, trial))
        return child

    def record(trial):
        point("record")
        return dict(
            request=trial.request_identity,
            parent=trial.parent_identity,
            before=trial.before.identity,
            after=trial.after.identity,
            calendar=trial.calendar.identity,
            sampled=trial.sampled.identity,
            t=trial.source_time_label.identity,
            dt=trial.configured_dt.identity,
            index=trial.loop_index,
            complete=trial.iteration_complete,
            loop_returned=trial.loop_returned,
            selected_stop=trial.selected_stop,
            work=stage._step_work_values(trial.work),
            rng_before=trial.stream_before,
            rng_after=trial.stream_after,
        )

    model.modules["init_first_step"] = NS(
        LAW_ID="init_first_step", from_electrical=request, prepare=prepare, trial_record=record
    )
    return model


@pytest.mark.parametrize("mode", stage.FLUX_MODES)
@pytest.mark.parametrize("loop_returned", [False, True])
def test_demo_init_first_step_retains_one_original_iteration_and_native_time_labels(
    mode, loop_returned, tmp_path
):
    model, evidence = first_step_chain(mode=mode, loop_returned=loop_returned), Evidence()
    result = execute(model, tmp_path, evidence)
    child, phase, trial = model.step_objects[0]
    assert result.result is child and result.first_step_phase is phase is result.init_phase
    assert (
        result.first_step_trial is trial
        and result.electrical_trial is model.field_objects["init_electrical"][2]
    )
    assert model.field_objects["init_electrical"][0].consumed
    assert model.calls.count("init_electrical.trial") == 1
    assert (
        model.calls.count("init_first_step.trial")
        == model.calls.count("init_first_step.phase")
        == 1
    )
    values = dict(evidence.values)
    for name in ("before", "after", "calendar", "sampled", "source_time_label", "configured_dt"):
        assert values["init_first_step." + name] is getattr(trial, name)
    assert values["init_first_step.source_time_label"].value == 0.0
    assert values["init_first_step.configured_dt"].value == 0.4
    assert values["init_first_step.raw_returns"][1] is trial.raw_returns[1][1]
    assert values["init_first_step.stores"][0][3] is trial.stores[0][3]
    assert values["init_first_step.stream_before"] == result.electrical_trial.rng_after
    assert values["init_first_step.stream_after"] != values["init_first_step.stream_before"]
    assert values["init_first_step.record"]["loop_returned"] is loop_returned
    assert values["init_first_step.record"]["selected_stop"] is not loop_returned
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["kind"].endswith("@5") and outcome["init_first_step_completed"] is True
    assert (
        type(outcome["init_time_steps_completed"]) is int
        and outcome["init_time_steps_completed"] == 1
    )
    assert outcome["scientific_or_physical_credit"] == 0
    assert outcome["complete_seed_runner_or_INIT_SIM_restart_claim"] is False
    assert [n for n in result.captures if n.startswith("init_first_step.")] == [
        "init_first_step." + name
        for name in (
            "record",
            "before",
            "after",
            "calendar",
            "sampled",
            "source_time_label",
            "configured_dt",
            "stream_before",
            "stream_after",
            "stores",
            "raw_returns",
        )
    ]


@pytest.mark.parametrize("edge", ["phase", "p", "cells", "sim", "dyna", "callbacks", "cache"])
def test_demo_init_first_step_same_owner_edges_cannot_be_replaced(edge, tmp_path):
    def mutate(model, phase, trial):
        if edge == "phase":
            return NS(**vars(phase))
        setattr(phase, edge, object())

    model = first_step_chain(mutate=mutate)
    with pytest.raises(ValueError, match="same retained chain"):
        execute(model, tmp_path)
    assert model.state.first_step_trial is model.step_objects[0][2]
    assert model.state.last_return is model.step_objects[0][0]
    assert not model.state.init_first_step_completed and model.state.init_time_steps_completed == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("iteration_complete", False),
        ("iteration_complete", 1),
        ("loop_index", 1),
        ("loop_index", False),
        ("loop_returned", True),
        ("loop_returned", 0),
        ("selected_stop", False),
        ("selected_stop", 1),
        ("request_identity", "foreign"),
        ("parent_identity", "foreign"),
        ("stream_before", ("c" * 64, "d" * 64)),
        ("stream_after", ("not-a-digest", "d" * 64)),
        ("stores", ()),
        ("calendar", NS(identity="not-a-digest")),
    ],
)
def test_demo_init_first_step_incomplete_or_relabelled_trial_never_counts(field, value, tmp_path):
    model = first_step_chain(mutate=lambda _m, _p, trial: setattr(trial, field, value))
    with pytest.raises(ValueError):
        execute(model, tmp_path)
    assert model.state.first_step_trial is model.step_objects[0][2]
    assert model.state.init_time_steps_completed == 0 and not model.state.init_first_step_completed
    assert json.loads((tmp_path / "outcome.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("failed", ["request", "source", "trial", "phase", "record"])
def test_demo_init_first_step_original_failure_keeps_parent_child_and_cause(failed, tmp_path):
    model = first_step_chain(fail=failed)
    with pytest.raises(ValueError) as caught:
        execute(model, tmp_path)
    assert caught.value is model.primary and caught.value.__cause__.args == ("original cause",)
    assert model.state.electrical_trial is model.field_objects["init_electrical"][2]
    assert model.field_objects["init_electrical"][0].consumed is (failed != "request")
    if failed in ("trial", "phase", "record"):
        assert model.state.last_return is model.step_objects[0][0]
        assert model.state.owners[-1] == ("init_first_step", model.step_objects[0][0])
    assert model.state.init_time_steps_completed == 0 and model.state.result is None


@pytest.mark.parametrize("label", ["record", "source_time_label", "raw_returns"])
def test_demo_init_first_step_capture_refusal_retains_trial_without_completion(label, tmp_path):
    model, evidence = first_step_chain(), Evidence(fail="init_first_step." + label)
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, evidence)
    assert model.state.first_step_trial is model.step_objects[0][2]
    assert model.state.first_step_record is not None
    assert model.state.init_time_steps_completed == 0 and not model.state.init_first_step_completed
    assert "init_first_step.failure.raw_returns" in dict(evidence.values)


def test_demo_init_first_step_never_consumes_parent_after_electrical_capture_failure(tmp_path):
    model = first_step_chain()
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, Evidence(fail="init_electrical.raw_returns"))
    assert not model.field_objects["init_electrical"][0].consumed
    assert not any(name.startswith("init_first_step.") for name in model.calls)
    assert model.state.init_time_steps_completed == 0


def test_demo_init_first_step_later_session_failure_keeps_raw_completion_but_zero_credit(tmp_path):
    model = first_step_chain()
    primary = Falsey("session closure after completed body")

    @contextmanager
    def session():
        yield
        raise primary

    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path, session=session())
    assert caught.value is primary and model.state.first_step_trial.iteration_complete is True
    assert model.state.first_step_trial.selected_stop is True
    assert not model.state.init_first_step_completed and model.state.init_time_steps_completed == 0
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "failed" and outcome["init_first_step_completed"] is False
    assert (
        type(outcome["init_time_steps_completed"]) is int
        and outcome["init_time_steps_completed"] == 0
    )


def test_demo_init_first_step_final_writer_failure_cannot_leave_state_completion_credit(
    tmp_path, monkeypatch
):
    model = first_step_chain()
    primary = OSError("final outcome write")
    original = stage.snapshot.write_json

    def fail(path, value):
        if path == tmp_path / "outcome.json":
            raise primary
        return original(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(stage.snapshot, "write_json", fail)
        with pytest.raises(OSError) as caught:
            execute(model, tmp_path)
    assert caught.value is primary and model.state.first_step_trial.iteration_complete is True
    assert not model.state.init_first_step_completed and model.state.init_time_steps_completed == 0
    assert not (tmp_path / "outcome.json").exists()


def test_demo_init_first_step_error_trial_is_retained_without_issuing_a_child(tmp_path):
    model = first_step_chain()
    module = model.modules["init_first_step"]
    original = module.prepare
    primary = Falsey("closure after sealed trial")

    def fail(request, *, enabled):
        original(request, enabled=enabled)
        primary.trial = model.step_objects[0][2]
        raise primary

    module.prepare = fail
    evidence = Evidence()
    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path, evidence)
    assert caught.value is primary and model.state.first_step_trial is primary.trial
    assert model.state.owners[-1][0] == "init_electrical" and model.state.result is None
    assert dict(evidence.values)["init_first_step.failure.calendar"] is primary.trial.calendar
    assert not model.state.init_first_step_completed and model.state.init_time_steps_completed == 0


@pytest.mark.parametrize("boundary", ["source", "first_capture"])
@pytest.mark.parametrize("secondary_failure", [False, True])
def test_demo_init_first_step_durable_failure_fields_survive_primary_and_writer_errors(
    boundary, secondary_failure, tmp_path
):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    model = first_step_chain()
    primary, cause, secondary = Falsey("step primary"), KeyError("step cause"), OSError("writer")
    primary.__cause__ = cause
    raw = [-0.0, b"\x00\xff"]
    context = NS(
        before=("before",),
        time_steps=(0.0, 0.4, 0.8),
        sampled={0.0, 0.8},
        source_time_label=0.0,
        stream_ids=("a" * 64, "b" * 64),
        iteration_complete=False,
        loop_returned=False,
        selected_stopped=False,
        stores=((1158, "fluxes_gj", None, raw, False, True),),
        raw_returns=[(sys._getframe(), raw)],
        last_raw=(sys._getframe(), raw),
        work=[dict(code=first_step_chain.__code__, body_started=True, returned=False)],
    )
    if boundary == "source":

        def fail(request, *, enabled):
            assert enabled is True
            request.parent.consumed = True
            primary.partial = context
            raise primary

        model.modules["init_first_step"].prepare = fail

    class SavedEvidence(Recorder):
        def __init__(self):
            super().__init__(tmp_path, sidecars=True, capture_writer=stage._evidence_writer())

        def save(self, label, value):
            if label == "init_first_step.record" and boundary == "first_capture":
                raise primary
            if label == "init_first_step.failure.before" and secondary_failure:
                raise secondary
            return super().save(label, value)

    evidence = SavedEvidence()
    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path, evidence)
    assert caught.value is model.state.primary is primary and caught.value.__cause__ is cause
    assert (
        model.state.init_electrical_completed and model.field_objects["init_electrical"][0].consumed
    )
    assert model.state.init_time_steps_completed == 0 and not model.state.init_first_step_completed
    saved = {}
    for row in evidence.rows:
        if row["label"].startswith("init_first_step.failure.") and row["status"] == "saved":
            path = tmp_path / row["path"]
            saved[row["label"]] = transport.read(path, expected_sha256=row["sha256"])
            assert transport.files(path, expected_sha256=row["sha256"])
    assert saved["init_first_step.failure.raw_returns"][-1][0] == {
        "float64_bits": "0000000000000080"
    }
    assert saved["init_first_step.failure.primary"]["live_claim_or_frame_serialization"] is False
    if boundary == "source":
        assert model.state.first_step_failure_context is context
        assert saved["init_first_step.failure.source_time_label"] == {
            "float64_bits": "0000000000000000"
        }
        assert saved["init_first_step.failure.last_raw_return"][1] == {"bytes_hex": "00ff"}
        assert "init_first_step.failure.configured_dt" not in saved
    else:
        assert saved["init_first_step.failure.source_time_label"]["value"] == {
            "float64_bits": "0000000000000000"
        }
        assert saved["init_first_step.failure.configured_dt"]["value"] == {
            "float64_bits": "9a9999999999d93f"
        }
    if secondary_failure:
        assert ("init_first_step.failure.before", secondary) in model.state.secondary
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["status"] == "failed" and outcome["scientific_or_physical_credit"] == 0
    assert outcome["first_step_failure_captures"][-1]["status"] == "saved"


def test_demo_init_first_step_bad_projection_preserves_later_raw_fields(tmp_path):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    state = stage.Execution("original", endpoint="init_first_step")
    state.primary = Falsey("partial source")
    state.primary.partial = NS(
        work=[object()], stores=[object()], raw_returns=[(None, b"retained")]
    )
    state.operations = [dict(name="init_first_step", status="failed")]
    evidence = Recorder(tmp_path, sidecars=True, capture_writer=stage._evidence_writer())
    stage._finish(state, evidence, tmp_path)
    assert {name for name, _ in state.secondary} >= {
        "init_first_step.failure.work",
        "init_first_step.failure.stores",
    }
    row = next(r for r in evidence.rows if r["label"] == "init_first_step.failure.raw_returns")
    assert transport.read(tmp_path / row["path"], expected_sha256=row["sha256"]) == [
        {"bytes_hex": b"retained".hex()}
    ]
    assert state.init_time_steps_completed == 0


def test_demo_init_first_step_source_gates_precede_all_reads_imports_and_callbacks(monkeypatch):
    for name in ("INIT", "PRELUDE", "COMPLETION", "ELECTRICAL"):
        for suffix in ("SOURCE_PINS", "REVIEW_PINS"):
            key = name + "_" + suffix
            monkeypatch.setattr(stage, key, dict.fromkeys(getattr(stage, key), "a" * 64))

    def forbidden(*args, **kwargs):
        pytest.fail("Unadopted step reached source/input/callback")

    monkeypatch.setattr(stage.snapshot, "digest", forbidden)
    monkeypatch.setattr(stage.importlib, "import_module", forbidden)
    with pytest.raises(stage.DemoRejected) as caught:
        stage._dependencies("init_first_step")
    assert caught.value.stage == "step_unbound"
    for endpoint in stage.ENDPOINTS:
        with pytest.raises(stage.DemoRejected, match="first-step producer unavailable"):
            stage.Modules(endpoint)["init_first_step"]
    plan = stage.source_plan(endpoint="init_first_step")
    assert plan["stages"][-3:] == ("init_storage", "init_electrical", "init_first_step")
    assert plan["optional_init_first_step"]["source_pins"] == {"init_first_step": None}
    assert plan["optional_init_first_step"]["review_pins"] == {"init_first_step": None}
    assert plan["optional_init_first_step"]["selected_stop_distinct_from_full_loop_return"] is True
    assert plan["optional_init_first_step"]["full_INIT_SIM_or_restart_admission"] is False


@pytest.mark.parametrize("prefix", ["INIT", "PRELUDE", "COMPLETION", "ELECTRICAL"])
def test_demo_init_first_step_each_ancestor_gate_remains_required(prefix, monkeypatch):
    for name in ("INIT", "PRELUDE", "COMPLETION", "ELECTRICAL", "STEP"):
        for suffix in ("SOURCE_PINS", "REVIEW_PINS"):
            key = name + "_" + suffix
            monkeypatch.setattr(stage, key, dict.fromkeys(getattr(stage, key), "a" * 64))
    monkeypatch.setattr(
        stage, prefix + "_REVIEW_PINS", dict.fromkeys(getattr(stage, prefix + "_REVIEW_PINS"))
    )
    monkeypatch.setattr(stage.snapshot, "digest", lambda *_: pytest.fail("Read before gate"))
    monkeypatch.setattr(
        stage.importlib, "import_module", lambda *_: pytest.fail("Import before gate")
    )
    with pytest.raises(stage.DemoRejected, match="unadopted"):
        stage._dependencies("init_first_step")


@pytest.mark.parametrize(
    "module", ["betse_native_init_first_step", "betse_native_init_first_step_source"]
)
def test_demo_init_first_step_runner_blocks_actual_entry_and_literal_bodies(module):
    names = (
        ("from_electrical", "prepare", "_run", "_authority", "_namespace", "_dispatch")
        if not module.endswith("_source")
        else (
            "_plot_loop",
            "_run_sim_core_loop",
            "after_update_V",
            "pumpNaKATP",
            "electroflux",
            "run",
        )
    )
    for name in names:
        assert software.is_forbidden_frame(
            NS(
                f_globals={"__name__": "cells.processes." + module},
                f_code=NS(co_name=name, co_filename="<metadata-only>"),
            )
        )
    assert "cells.processes.betse_native_init_first_step_source" in software.FORBIDDEN_MODULES


def molecule_chain(*, mode="original", endpoint="init_dynamics", mutate=None):
    """Private consumer protocol only; no molecular producer or native body executes."""
    model = (
        first_step_chain(mode=mode) if endpoint == "init_first_step" else dynamics_chain(mode=mode)
    )
    # Declare the original input before any public-protocol acquisition runs.
    model.p.molecules_enabled = True
    model.p._conf = {"general network": {"implement network": True}}
    model.p.network_config = model.p._conf["general network"]
    module = dict.__getitem__(model.modules, "init_dynamics")
    original_prepare, original_record = module.prepare, module.trial_record
    model.molecule_records, model.forensic_calls = [], []
    participant = NS()
    model.modules["init_molecules"] = participant

    def failed_completion(claim):
        model.forensic_calls.append(("completion", claim))
        assert claim is model.failed_completion_context.claim
        return model.failed_completion_context

    def failed_molecule(session):
        model.forensic_calls.append(("molecule", session))
        assert session is model.failed_molecular_context.session
        return model.failed_molecular_context

    # The consumer requires exact function globals on its retained module.
    # These private functions transport fixture state, never real issuer state.
    module.failed_context = FunctionType(
        failed_completion.__code__, vars(module), closure=failed_completion.__closure__
    )
    participant.failed_context = FunctionType(
        failed_molecule.__code__, vars(participant), closure=failed_molecule.__closure__
    )

    def request(parent, *, law_id, file_inputs):
        model.calls.append("molecular.request")
        assert parent is model.prelude_objects[0][0] and not parent.consumed
        assert law_id == "native_molecules"
        assert model.module_loads[-3:] == ["init_tissue", "init_molecules", "init_dynamics"]
        model.file_inputs = file_inputs
        return NS(parent=parent, file_inputs=file_inputs, native_molecules=True, identity="d" * 64)

    def forbidden_legacy(*args, **kwargs):
        pytest.fail("Enabled configuration must never fall back to the disabled request")

    def prepare(request, *, enabled):
        child = original_prepare(request, enabled=enabled)
        _, phase, trial = model.dynamics_objects[0]
        assert phase.sim.molecules is None
        frame, raw = sys._getframe(), [-0.0, b"\x00\xff"]
        core = NS(molecules={"X": object()})
        mom = NS(core=core)
        phase.sim.molecules = mom
        record = NS(
            identity="e" * 64,
            source_completed=True,
            original_claim=trial.tissue_record.completion_claim,
            original_molecules=mom,
            original_core=core,
            constructor_work=(("MasterOfMolecules", mom, frame), ("MasterOfNetworks", core, frame)),
            source_work=({"frame": frame, "code": frame.f_code, "returned": True},),
            raw_returns=((frame, raw),),
            dynamic_callbacks=(),
        )
        trial.request_identity, trial.molecule_record = request.identity, record
        model.molecule_records.append(record)
        if mutate is not None:
            mutate(model, phase, trial, record)
        return child

    def record(trial):
        return dict(
            original_record(trial),
            molecule_record=id(trial.molecule_record),
            tissue_record=id(trial.tissue_record),
        )

    module.MOLECULE_LAW_ID = "native_molecules"
    module.from_prelude_native_molecules, module.from_prelude = request, forbidden_legacy
    module.prepare, module.trial_record = prepare, record
    return model


@pytest.mark.parametrize("mode", stage.FLUX_MODES)
@pytest.mark.parametrize("endpoint", ["init_dynamics", "init_first_step"])
def test_demo_molecular_original_flag_routes_complete_same_chain_without_flux_repair(
    mode, endpoint, tmp_path
):
    model, evidence = molecule_chain(mode=mode, endpoint=endpoint), Evidence()
    result = execute(model, tmp_path, evidence)
    record = model.molecule_records[0]
    assert result.parameters is result.init_phase.p is model.p
    assert model.p.molecules_enabled is model.p.network_config["implement network"] is True
    assert result.dynamics_molecule_record is record
    assert record.original_molecules is result.init_phase.sim.molecules
    assert record.original_core is record.original_molecules.core
    assert record.original_claim is result.dynamics_trial.tissue_record.completion_claim
    assert model.module_loads.index("init_molecules") < model.module_loads.index("init_dynamics")
    assert (
        model.calls.count("molecular.request") == 1 and "init_dynamics.request" not in model.calls
    )
    values = dict(evidence.values)
    metadata = values["init_dynamics.molecule_record"]
    assert metadata["record_identity"] == values["init_dynamics.record"]["molecule_record"]
    assert (
        metadata["completion_claim_identity"]
        == values["init_dynamics.tissue_record"]["completion_claim_identity"]
    )
    assert metadata["work_views_are_non_additive"] is True
    assert metadata["live_claim_or_frame_serialization"] is False
    assert values["init_dynamics.molecule_raw_returns"][0] is record.raw_returns[0][1]
    assert result.init_molecule_network_completed and result.init_dynamics_completed
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert outcome["init_native_molecules"] is outcome["init_molecule_network_completed"] is True
    assert outcome["original_flux_defect_repaired"] is False and outcome["flux_operator"] == mode
    assert outcome["init_time_steps_completed"] == int(endpoint == "init_first_step")
    assert outcome["scientific_or_physical_credit"] == 0


def test_demo_molecular_disabled_input_keeps_legacy_factory_and_no_participant_import(tmp_path):
    model = dynamics_chain()
    result = execute(model, tmp_path)
    assert model.p.molecules_enabled is False and result.dynamics_native_molecules is False
    assert not result.init_molecule_network_completed and result.dynamics_molecule_record is None
    assert "init_molecules" not in model.module_loads
    assert "init_dynamics.request" in model.calls and "molecular.request" not in model.calls
    assert json.loads((tmp_path / "outcome.json").read_text())["init_native_molecules"] is False


@pytest.mark.parametrize("flag", [None, 1, "True", "missing"])
def test_demo_molecular_missing_or_nonboolean_flag_refuses_before_import_or_request(flag, tmp_path):
    model = dynamics_chain()
    if flag == "missing":
        del model.p.molecules_enabled
    else:
        model.p.molecules_enabled = flag
    with pytest.raises((ValueError, AttributeError)):
        execute(model, tmp_path)
    assert model.state.init_prelude_completed and not model.prelude_objects[0][0].consumed
    assert not model.dynamics_objects
    assert not {"init_tissue", "init_molecules", "init_dynamics"}.intersection(model.module_loads)
    assert model.state.dynamics_native_molecules is None


@pytest.mark.parametrize("boundary", ["participant_import", "request", "misrouted_request"])
def test_demo_molecular_early_failure_never_falls_back_or_consumes_parent(boundary, tmp_path):
    model = molecule_chain()
    primary, cause = Falsey("enabled request boundary"), KeyError("original cause")
    primary.__cause__ = cause
    module = dict.__getitem__(model.modules, "init_dynamics")
    original = module.from_prelude_native_molecules
    if boundary == "participant_import":
        parent_type = type(model.modules)

        class Modules(parent_type):
            def __getitem__(self, key):
                if key == "init_molecules":
                    raise primary
                return super().__getitem__(key)

        model.modules = Modules(model.modules)
    else:

        def request(*args, **kwargs):
            if boundary == "request":
                raise primary
            result = original(*args, **kwargs)
            result.native_molecules = False
            return result

        module.from_prelude_native_molecules = request
    with pytest.raises(ValueError) as caught:
        execute(model, tmp_path)
    if boundary != "misrouted_request":
        assert caught.value is primary and caught.value.__cause__ is cause
    assert model.state.init_prelude_completed and not model.prelude_objects[0][0].consumed
    assert model.state.prelude_trial is model.prelude_objects[0][2]
    assert not model.dynamics_objects and "init_dynamics.request" not in model.calls


@pytest.mark.parametrize(
    "mutation", ["flag", "claim", "molecules", "core", "incomplete", "request", "unfinished_work"]
)
def test_demo_molecular_record_drift_refuses_before_storage_and_preserves_raw_trial(
    mutation, tmp_path
):
    def mutate(model, phase, trial, record):
        if mutation == "flag":
            phase.p.molecules_enabled = False
        elif mutation == "claim":
            record.original_claim = object()
        elif mutation == "molecules":
            record.original_molecules = NS(core=record.original_core)
        elif mutation == "core":
            record.original_core = NS(**vars(record.original_core))
        elif mutation == "incomplete":
            record.source_completed = 1
        elif mutation == "request":
            trial.request_identity = "f" * 64
        else:
            record.source_work[0]["returned"] = False

    model = molecule_chain(endpoint="init_first_step", mutate=mutate)
    with pytest.raises(ValueError):
        execute(model, tmp_path)
    assert model.state.dynamics_molecule_record is model.molecule_records[0]
    assert model.state.dynamics_trial is model.dynamics_objects[0][2]
    assert model.prelude_objects[0][0].consumed
    assert (
        not model.state.init_molecule_network_completed and not model.state.init_dynamics_completed
    )
    assert not model.field_objects and model.state.result is None


@pytest.mark.parametrize("field", ["molecule_record", "molecule_raw_returns"])
def test_demo_molecular_capture_refusal_preserves_exact_returns_without_downstream_use(
    field, tmp_path
):
    model, evidence = (
        molecule_chain(endpoint="init_first_step"),
        Evidence(fail="init_dynamics." + field),
    )
    with pytest.raises(ValueError, match="Typed observation refused"):
        execute(model, tmp_path, evidence)
    assert model.state.dynamics_trial is model.dynamics_objects[0][2]
    assert model.state.dynamics_molecule_record is model.molecule_records[0]
    assert not model.state.init_molecule_network_completed and not model.field_objects
    saved = dict(evidence.values)
    assert (
        saved["init_dynamics.failure.molecule_raw_returns"][0]
        is model.molecule_records[0].raw_returns[0][1]
    )


@pytest.mark.parametrize("bad_projection", [False, True])
@pytest.mark.parametrize("attachment", ["ordinary_source_error", "completion_partial"])
def test_demo_molecular_original_failure_preserves_separate_partial_and_last_bits(
    bad_projection, attachment, tmp_path
):
    from validation.betse.native_single_cell_prefix_qualification import Evidence as Recorder

    model, primary, cause = (
        molecule_chain(),
        Falsey("molecular source failure"),
        KeyError("source cause"),
    )
    primary.__cause__ = cause
    frame, raw = sys._getframe(), [-0.0, b"\x00\xff"]
    session, claim = object(), object()
    original_context = NS(
        session=session,
        claim=claim,
        raw_returns=[(frame, raw)],
        last_raw=(frame, raw),
        work=[
            {
                "code": object() if bad_projection else frame.f_code,
                "frame": frame,
                "returned": False,
            }
        ],
    )
    completion = NS(
        before=("retained-completion",),
        raw_returns=[],
        claim=claim,
        molecule_session=session,
        molecule_record=None,
        molecule=dict.__getitem__(model.modules, "init_molecules"),
    )
    original_context.completion = completion
    model.failed_completion_context, model.failed_molecular_context = completion, original_context

    def fail(request, *, enabled):
        assert enabled and request.native_molecules is True
        request.parent.consumed = True
        completion.request = request
        if attachment == "ordinary_source_error":
            primary.init_dynamics_completion_partial = completion
        else:
            primary.partial = completion
        raise primary

    dict.__getitem__(model.modules, "init_dynamics").prepare = fail
    evidence = Recorder(tmp_path, sidecars=True, capture_writer=stage._evidence_writer())
    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path, evidence)
    assert caught.value is model.state.primary is primary and caught.value.__cause__ is cause
    assert model.state.dynamics_failure_context is completion
    assert model.state.dynamics_molecule_failure_context is original_context
    assert model.forensic_calls == [("completion", claim), ("molecule", session)]
    if attachment == "ordinary_source_error":
        assert not hasattr(primary, "partial")
    assert model.state.dynamics_trial is None and model.state.result is None
    saved = {
        row["label"]: transport.read(tmp_path / row["path"], expected_sha256=row["sha256"])
        for row in evidence.rows
        if row["status"] == "saved"
    }
    assert saved["init_dynamics.failure.molecule_raw_returns"][0] == [
        {"float64_bits": "0000000000000080"},
        {"bytes_hex": "00ff"},
    ]
    assert (
        saved["init_dynamics.failure.molecule_last_return"]
        == saved["init_dynamics.failure.molecule_raw_returns"][0]
    )
    assert (
        any(n == "init_dynamics.failure.molecule_work" for n, _ in model.state.secondary)
        is bad_projection
    )
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert (
        outcome["init_native_molecules"] is True
        and outcome["init_molecule_network_completed"] is False
    )
    assert outcome["status"] == "failed" and outcome["scientific_or_physical_credit"] == 0


@pytest.mark.parametrize("drift", ["request", "participant", "completion_link", "claim", "session"])
def test_demo_molecular_forensic_mismatch_never_mislabels_completion_returns(drift, tmp_path):
    model, primary = molecule_chain(), Falsey("original failed source")
    frame, claim, session = sys._getframe(), object(), object()
    completion = NS(
        before=("completion-only",),
        raw_returns=[(frame, b"completion")],
        claim=claim,
        molecule_session=session,
        molecule_record=None,
        molecule=dict.__getitem__(model.modules, "init_molecules"),
    )
    molecular = NS(
        completion=completion,
        claim=claim,
        session=session,
        raw_returns=[(frame, b"different-molecular-return")],
        last_raw=(frame, None),
    )
    model.failed_completion_context, model.failed_molecular_context = completion, molecular

    def fail(request, *, enabled):
        request.parent.consumed = True
        completion.request = request
        if drift == "request":
            completion.request = NS(**vars(request))
        elif drift == "participant":
            completion.molecule = NS(**vars(completion.molecule))
        elif drift == "completion_link":
            molecular.completion = NS(**vars(completion))
        elif drift == "claim":
            molecular.claim = object()
        else:
            molecular.session = object()
        primary.partial = completion
        raise primary

    dict.__getitem__(model.modules, "init_dynamics").prepare = fail
    evidence = Evidence()
    with pytest.raises(Falsey) as got:
        execute(model, tmp_path, evidence)
    assert got.value is primary and model.state.dynamics_failure_context is completion
    assert model.state.dynamics_molecule_failure_context is None
    values = dict(evidence.values)
    assert values["init_dynamics.failure.raw_returns"] == (b"completion",)
    assert "init_dynamics.failure.molecule_raw_returns" not in values
    assert any(n == "init_dynamics.failure.molecule_context" for n, _ in model.state.secondary)
    assert model.state.result is None and not model.state.init_molecule_network_completed


def test_demo_molecular_completion_seal_failure_retains_finished_record_without_failed_session_read(
    tmp_path,
):
    model, primary = molecule_chain(), Falsey("completion seal failed after molecular finish")
    module = dict.__getitem__(model.modules, "init_dynamics")
    original = module.prepare

    def fail(request, *, enabled):
        original(request, enabled=enabled)
        record = model.molecule_records[0]
        model.failed_completion_context = NS(
            request=request,
            claim=record.original_claim,
            molecule_session=object(),
            molecule_record=record,
            molecule=dict.__getitem__(model.modules, "init_molecules"),
            before=("completion-seal",),
            raw_returns=[],
        )
        primary.init_dynamics_completion_partial = model.failed_completion_context
        raise primary

    module.prepare = fail
    evidence = Evidence()
    with pytest.raises(Falsey) as got:
        execute(model, tmp_path, evidence)
    assert got.value is primary and model.state.dynamics_trial is None
    record = model.molecule_records[0]
    assert model.forensic_calls == [("completion", record.original_claim)]
    assert model.state.dynamics_molecule_record is record
    assert (
        dict(evidence.values)["init_dynamics.failure.molecule_raw_returns"][0]
        is record.raw_returns[0][1]
    )
    assert (
        dict(evidence.values)["init_dynamics.failure.molecule_record"]["source_completed"] is True
    )
    assert (
        not model.state.init_dynamics_completed and not model.state.init_molecule_network_completed
    )


def test_demo_molecular_completed_stage_survives_later_failure_without_endpoint_promotion(tmp_path):
    model, primary = molecule_chain(endpoint="init_first_step"), Falsey("later storage source")

    def fail(*args, **kwargs):
        raise primary

    model.modules["init_storage"].prepare = fail
    with pytest.raises(Falsey) as caught:
        execute(model, tmp_path)
    assert caught.value is primary
    outcome = json.loads((tmp_path / "outcome.json").read_text())
    assert (
        outcome["init_molecule_network_completed"] is True
        and outcome["init_dynamics_completed"] is True
    )
    assert outcome["status"] == "failed" and outcome["init_time_steps_completed"] == 0
    assert outcome["init_first_step_completed"] is False and model.state.result is None


def test_demo_molecular_unadopted_gate_and_actual_entry_blockade_stay_closed(monkeypatch):
    for name in ("INIT", "PRELUDE", "COMPLETION"):
        for suffix in ("SOURCE_PINS", "REVIEW_PINS"):
            key = name + "_" + suffix
            pins = dict.fromkeys(getattr(stage, key), "a" * 64)
            if name == "COMPLETION":
                pins["init_molecules"] = None
            monkeypatch.setattr(stage, key, pins)
    monkeypatch.setattr(
        stage.snapshot, "digest", lambda *_: pytest.fail("Read before new producer gate")
    )
    monkeypatch.setattr(
        stage.importlib, "import_module", lambda *_: pytest.fail("Import before gate")
    )
    with pytest.raises(stage.DemoRejected) as caught:
        stage._dependencies("init_dynamics")
    assert caught.value.stage == "dynamics_unbound"
    for module, names in (
        (
            "betse_native_init_molecule_network",
            ("<module>", "bind_storage", "finish", "observe_runtime"),
        ),
        ("betse_native_init_molecule_network_source", ("<module>", "_factory", "read_mol_config")),
        ("betse_native_init_dynamics_completion", ("from_prelude_native_molecules",)),
    ):
        for name in names:
            assert software.is_forbidden_frame(
                NS(
                    f_globals={"__name__": "cells.processes." + module},
                    f_code=NS(co_name=name, co_filename="<metadata-only>"),
                )
            )
