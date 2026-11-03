"""Blocked orchestration controls; private protocol fakes never issue authority."""

import json
import os
from contextlib import contextmanager, nullcontext
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from tests.unit import test_betse_native_world_phase_construction as guards
from validation.betse import native_seed_demo as stage
from validation.betse import native_seed_demo_software as software

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


class Falsey(ValueError):
    def __bool__(self):
        return False


def chain(*, mode="original", fail=None, primary=None, mutate=None):
    """Stateful private protocol, with old-owner reads rejected after retirement."""
    p, calls, owners = object(), [], []
    phase = NS(p=p, cells=object(), sim=object(), dyna=object(), callbacks=object())
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
            assert kwargs == (dict(flux_operator=mode) if label == "poisson" else {})
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


def test_demo_plan_explicit_whole_endpoint_two_modes_and_closed_producers():
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


@pytest.mark.parametrize(
    "enabled,release", [(False, None), (True, None), (False, "1"), (True, "1")]
)
def test_demo_unbound_public_entry_refuses_before_inputs_or_imports(enabled, release, monkeypatch):
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
