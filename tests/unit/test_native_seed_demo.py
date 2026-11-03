"""Blocked orchestration controls; private protocol fakes never issue authority."""

import json
import os
import sys
from contextlib import contextmanager, nullcontext
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
    p, calls, owners = object(), [], []
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
            sim=object(),
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
