"""Short actual-owner conditional checkpoint checks, not full qualification."""

import json
import os
import shutil
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation.betse import betse_normal_ecm_molecule_checkpoint as conditional
from validation.betse.betse_normal_ecm_molecule_checkpoint import (
    accepted_prefix,
    prepare_INIT,
    prepare_SIM,
    retained_SIM_prerequisite,
)

ATTEMPTS = []


@pytest.fixture(scope="module", autouse=True)
def retain_test_attempts(tmp_path_factory):
    yield
    root = Path(
        os.environ.get("CELLS_CHECKPOINT_TEST_EVIDENCE", str(tmp_path_factory.getbasetemp()))
    )
    with (root / "actual-execution-attempts.json").open("x") as stream:
        json.dump(
            dict(
                attempts=ATTEMPTS,
                policy=(
                    "Every explicit producer/verification/advance invocation is an attempt; "
                    "nested validation is included in its root invocation"
                ),
                upstream_qualification="pending",
                native_checkpoint_parity=False,
            ),
            stream,
            indent=2,
        )
        stream.write("\n")


@pytest.fixture(scope="module")
def owned(tmp_path_factory):
    root = tmp_path_factory.mktemp("actual-checkpoint-owners")
    zero = prepare_INIT(root / "zero", "zero_INIT_calls", ATTEMPTS)
    ready = prepare_INIT(root / "ready", "one_INIT_call", ATTEMPTS)
    return zero, ready


def save(root, binding, parent, **kwargs):
    return checkpoint.save_checkpoint(
        root,
        binding,
        parent,
        expected_phase=run.composition.kind(binding.composition),
        expected_parent_identity=parent.identity,
        **kwargs,
    )


def load(root, binding, parent, evidence, **kwargs):
    return checkpoint.load_checkpoint(
        root,
        binding=binding,
        expected_phase=run.composition.kind(binding.composition),
        expected_parent_identity=parent.identity,
        evidence_directory=evidence,
        **kwargs,
    )


def test_owned_zero_INIT_roundtrip_without_setup_rebind_or_replay(owned, tmp_path, monkeypatch):
    binding, parent = owned[0]

    def forbidden(*args, **kwargs):
        raise AssertionError("Checkpoint cannot regenerate, bind or replay a source state")

    for module, name in (
        (run, "advance"),
        (run, "bind"),
        (run.composition.lifecycle, "transition"),
        (run.composition.lifecycle.init, "initialize"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    receipt = save(tmp_path / "saved", binding, parent)
    loaded = load(
        tmp_path / "saved",
        binding,
        parent,
        tmp_path / "load",
        expected_checkpoint_identity=receipt.identity,
    )
    assert checkpoint.codec.fingerprint(loaded.binding) == checkpoint.codec.fingerprint(binding)
    assert loaded.parent.status == parent.status == "exhausted"
    assert loaded.parent.cursor == 0 and loaded.parent.identity == parent.identity
    assert checkpoint.codec.fingerprint((binding, parent)) == checkpoint.codec.fingerprint(
        (loaded.binding, loaded.parent)
    )
    assert receipt.verification_attempts == loaded.receipt.verification_attempts == 1
    assert loaded.operation["saved_operation"]["attempts"][0]["numerical_work_possible"]
    assert loaded.operation["timesteps"] == loaded.operation["producer_rebinds"] == 0
    assert loaded.parent.entry_receipt["declaration_is_initialization_attestation"] is False
    ATTEMPTS.append(dict(operation="postload_existing_run.verify", numerical_work_possible=True))
    assert run.verify(loaded.binding, loaded.parent) is loaded.parent


def test_actual_capped_prefix_stays_capped_and_cannot_complete(tmp_path):
    binding, parent = prepare_INIT(
        tmp_path / "preparation", "one_INIT_call", ATTEMPTS, call_limit=0
    )
    assert parent.status == "capped" and parent.cursor == 0
    save(tmp_path / "saved", binding, parent)
    loaded = load(tmp_path / "saved", binding, parent, tmp_path / "load")
    assert loaded.parent.status == "capped" and loaded.parent.cursor == 0
    ATTEMPTS.append(
        dict(operation="capped_existing_run.complete_INIT", numerical_work_possible=True)
    )
    with pytest.raises(run.RunRejected):
        run.complete_INIT(binding, loaded.parent)


@pytest.mark.skipif(
    os.environ.get("CELLS_ECM_MOLECULE_RUN_LIFECYCLE_RELEASED") != "1",
    reason="Held positive SIM handoff; Root must coordinate the existing run-lifecycle release",
)
def test_actual_SIM_transition_and_both_phase_associations_roundtrip(owned, tmp_path):
    initial, parent = owned[0]
    try:
        binding, sim = prepare_SIM(tmp_path / "transition", initial, parent, ATTEMPTS)
    except run.RunRejected as error:
        if retained_SIM_prerequisite(error):
            pytest.xfail("Known retained warm-owner prerequisite: " + str(error))
        raise
    save(tmp_path / "saved", binding, sim)
    loaded = load(tmp_path / "saved", binding, sim, tmp_path / "load")
    assert loaded.receipt.phase == "SIM" and loaded.parent.cursor == 0
    assert loaded.parent.entry_receipt["previous_phase"].run.identity == parent.identity
    assert loaded.parent.active.source_init.parent.identity == parent.active.identity
    assert checkpoint.codec.fingerprint(sim) == checkpoint.codec.fingerprint(loaded.parent)


def test_actual_journal_and_sampling_prefix_conditional(tmp_path):
    binding, parent = prepare_INIT(tmp_path / "preparation", "both_disabled", ATTEMPTS)
    prefix = accepted_prefix(tmp_path / "calls", binding, parent, ATTEMPTS, calls=2)
    assert prefix.cursor == 2 and len(prefix.history) == 2 and len(prefix.observations) == 1
    ATTEMPTS.append(dict(operation="actual_journal_run.pause", numerical_work_possible=True))
    paused = run.pause(binding, prefix)
    save(tmp_path / "saved", binding, paused)
    loaded = load(tmp_path / "saved", binding, paused, tmp_path / "load")
    assert checkpoint.codec.fingerprint(paused) == checkpoint.codec.fingerprint(loaded.parent)
    ATTEMPTS.append(dict(operation="loaded_existing_run.resume", numerical_work_possible=True))
    resumed = run.resume(binding, loaded.parent)
    ATTEMPTS.append(dict(operation="loaded_existing_run.next_call", numerical_work_possible=True))
    assert run.next_call(binding, resumed)["call_index"] == 2


def test_paused_run_stays_paused_and_cannot_advance_implicitly(owned, tmp_path):
    binding, ready = owned[1]
    ATTEMPTS.append(dict(operation="actual_run.pause", numerical_work_possible=True))
    paused = run.pause(binding, ready)
    save(tmp_path / "saved", binding, paused)
    loaded = load(tmp_path / "saved", binding, paused, tmp_path / "load")
    assert loaded.parent.status == "paused" and loaded.parent.cursor == 0
    assert checkpoint.codec.fingerprint(paused) == checkpoint.codec.fingerprint(loaded.parent)
    with pytest.raises(ValueError):
        ATTEMPTS.append(
            dict(operation="paused_existing_run.next_call", numerical_work_possible=True)
        )
        run.next_call(binding, loaded.parent)


def test_failed_prefix_retains_actual_input_cause_and_failed_status(owned, tmp_path):
    binding, ready = owned[1]

    def stop(stage, value):
        raise RuntimeError("Actual declared pre-call checkpoint conditional refusal")

    ATTEMPTS.append(
        dict(
            operation="actual_run.advance_before_call_failure",
            numerical_work_possible=True,
            component_timestep_executions=0,
        )
    )
    with pytest.raises(run.RunRejected) as caught:
        run.advance(binding, ready, observer=stop)
    error = caught.value
    failed = error.partial["accepted"]
    assert failed.status == "failed" and failed.cursor == 0
    with pytest.raises(checkpoint.CheckpointRejected, match="failed-run evidence"):
        save(tmp_path / "without-failure", binding, failed)
    save(tmp_path / "saved", binding, failed, failure=error)
    loaded = load(tmp_path / "saved", binding, failed, tmp_path / "load")
    assert loaded.parent.status == "failed"
    assert loaded.failure["partial"]["caller_parent"].identity == ready.identity
    assert loaded.failure["exception_chain"][-1]["message"] == str(error.__cause__)
    with pytest.raises(ValueError):
        ATTEMPTS.append(dict(operation="failed_existing_run.resume", numerical_work_possible=True))
        run.resume(binding, loaded.parent)


@pytest.mark.parametrize(
    "fault",
    [
        "array-truncated",
        "json-truncated",
        "wrong-parent",
        "wrong-phase",
        "producer",
        "status",
        "boolean-cursor",
    ],
)
def test_refused_load_preserves_checkpoint_and_has_no_numeric_validation(owned, tmp_path, fault):
    binding, parent = owned[0]
    save(tmp_path / "saved", binding, parent)
    copy = tmp_path / "copy"
    shutil.copytree(tmp_path / "saved", copy)
    phase, identity = "INIT", parent.identity
    if fault == "array-truncated":
        p = copy / "arrays.npz"
        p.write_bytes(p.read_bytes()[:-1])
    elif fault == "json-truncated":
        p = copy / "state.json"
        p.write_bytes(p.read_bytes()[:-1])
    elif fault == "wrong-parent":
        identity = "0" * 64
    elif fault == "wrong-phase":
        phase = "SIM"
    else:
        p = copy / "manifest.json"
        manifest = json.loads(p.read_text())
        if fault == "producer":
            manifest["producer"]["source_hashes"][
                next(iter(manifest["producer"]["source_hashes"]))
            ] = "0" * 64
        elif fault == "status":
            manifest["status"] = "ready"
        else:
            manifest["cursor"] = False
        manifest["identity"] = checkpoint.digest(
            {k: v for k, v in manifest.items() if k != "identity"}
        )
        p.write_text(json.dumps(manifest))
    before = {p.name: checkpoint._sha(p) for p in copy.iterdir()}
    with pytest.raises(checkpoint.CheckpointRejected) as caught:
        checkpoint.load_checkpoint(
            copy,
            binding=binding,
            expected_phase=phase,
            expected_parent_identity=identity,
            evidence_directory=tmp_path / "load",
        )
    assert caught.value.attempts == ()
    assert before == {p.name: checkpoint._sha(p) for p in copy.iterdir()}
    assert json.loads((tmp_path / "load/failure.json").read_text())["no_checkpoint_admission"]


def test_atomic_commit_refusal_and_failed_input_output_retention(owned, tmp_path, monkeypatch):
    binding, parent = owned[0]

    def interrupted(*args, **kwargs):
        raise OSError("Injected pre-commit failure")

    monkeypatch.setattr(checkpoint, "_publish", interrupted)
    with pytest.raises(checkpoint.CheckpointRejected):
        save(tmp_path / "partial", binding, parent)
    assert not (tmp_path / "partial/manifest.json").exists()
    assert {"state.json", "arrays.npz", "operation.json", "failure.json"} <= {
        p.name for p in (tmp_path / "partial").iterdir()
    }
    with pytest.raises(checkpoint.CheckpointRejected, match="Incomplete"):
        load(tmp_path / "partial", binding, parent, tmp_path / "load")


def test_partial_array_write_retains_complete_input_and_failed_output(owned, tmp_path, monkeypatch):
    binding, parent = owned[0]
    captured = {}

    def interrupted(encoder, directory, tree):
        captured.update(encoder.arrays)
        checkpoint._write_json(directory / "state.json", tree)
        (directory / "arrays.npz").write_bytes(b"truncated injected output")
        raise OSError("Injected array-write failure")

    monkeypatch.setattr(checkpoint.codec.Encoder, "write", interrupted)
    with pytest.raises(checkpoint.CheckpointRejected, match="array-write") as caught:
        save(tmp_path / "partial", binding, parent)
    assert caught.value.attempts == ()
    assert (tmp_path / "partial/arrays.npz").read_bytes() == b"truncated injected output"
    assert not (tmp_path / "partial/manifest.json").exists()
    with np.load(tmp_path / "partial/input-arrays.npz", allow_pickle=False) as arrays:
        assert set(arrays.files) == set(captured)
        for key, expected in captured.items():
            assert arrays[key].dtype == expected.dtype
            assert arrays[key].shape == expected.shape
            assert arrays[key].tobytes(order="A") == expected.tobytes(order="A")
    assert json.loads((tmp_path / "partial/failure.json").read_text())["no_checkpoint_admission"]


def test_wrong_save_parent_preserves_complete_unadmitted_input(owned, tmp_path):
    binding, parent = owned[0]
    with pytest.raises(checkpoint.CheckpointRejected) as caught:
        checkpoint.save_checkpoint(
            tmp_path / "refused",
            binding,
            parent,
            expected_phase="INIT",
            expected_parent_identity="0" * 64,
        )
    assert caught.value.attempts == ()
    assert (tmp_path / "refused/state.json").exists()
    assert (tmp_path / "refused/arrays.npz").exists()
    assert not (tmp_path / "refused/manifest.json").exists()


def test_existing_destination_and_receipt_are_never_parent_admission(owned, tmp_path):
    binding, parent = owned[0]
    receipt = save(tmp_path / "saved", binding, parent)
    before = {p.name: checkpoint._sha(p) for p in (tmp_path / "saved").iterdir()}
    with pytest.raises(FileExistsError):
        save(tmp_path / "saved", binding, parent)
    assert before == {p.name: checkpoint._sha(p) for p in (tmp_path / "saved").iterdir()}
    with pytest.raises(checkpoint.CheckpointRejected):
        checkpoint.save_checkpoint(
            tmp_path / "receipt",
            binding,
            receipt,
            expected_phase="INIT",
            expected_parent_identity=parent.identity,
        )


def test_actual_foreign_run_binding_is_refused_before_numeric_validation(owned, tmp_path):
    binding, parent = owned[0]
    save(tmp_path / "saved", binding, parent)
    ATTEMPTS.append(dict(operation="actual_foreign_run.bind", numerical_work_possible=True))
    raw = run.ions.data(binding.inputs)
    raw["run_id"] += "-foreign"
    foreign = run.bind(raw, binding.composition)
    with pytest.raises(checkpoint.CheckpointRejected, match="binding mismatch") as caught:
        load(tmp_path / "saved", foreign, parent, tmp_path / "load")
    assert caught.value.attempts == ()


def test_changed_effective_jax_precision_refused_before_numeric_validation(owned, tmp_path):
    binding, parent = owned[0]
    save(tmp_path / "saved", binding, parent)
    jax = checkpoint.importlib.import_module("jax")
    prior = jax.config.jax_enable_x64
    try:
        jax.config.update("jax_enable_x64", not prior)
        with pytest.raises(checkpoint.CheckpointRejected, match="runtime mismatch") as caught:
            load(tmp_path / "saved", binding, parent, tmp_path / "load")
    finally:
        jax.config.update("jax_enable_x64", prior)
    assert caught.value.attempts == ()


def test_self_digested_synthetic_receipt_is_not_parent_admission(owned, tmp_path):
    binding, parent = owned[0]
    receipt = run.ions.data(parent.entry_receipt)
    receipt["declaration_is_initialization_attestation"] = True
    changed = replace(parent, entry_receipt=run.ions.freeze(receipt), identity="")
    changed = replace(changed, identity=run.ions.digest(run._record(changed)))
    with pytest.raises(checkpoint.CheckpointRejected, match="entry") as caught:
        save(tmp_path / "refused", binding, changed)
    assert len(caught.value.attempts) == 1 and caught.value.attempts[0]["status"] == "refused"
    assert not (tmp_path / "refused/manifest.json").exists()
    assert (tmp_path / "refused/state.json").exists()


def test_manifest_is_linked_only_after_all_payload_fsyncs(owned, tmp_path, monkeypatch):
    binding, parent = owned[0]
    sync, link = checkpoint.os.fsync, checkpoint.os.link
    synced = set()

    def durable(fd):
        synced.add(Path(os.readlink(f"/proc/self/fd/{fd}")).name)
        return sync(fd)

    def publish(source, target, **kwargs):
        assert checkpoint.FILES <= synced
        assert not Path(target).exists()
        return link(source, target, **kwargs)

    monkeypatch.setattr(checkpoint.os, "fsync", durable)
    monkeypatch.setattr(checkpoint.os, "link", publish)
    save(tmp_path / "saved", binding, parent)
    assert (tmp_path / "saved/manifest.json").is_file()


def test_nonregular_payload_is_refused_without_waiting_for_a_writer(tmp_path):
    path = tmp_path / "fifo"
    os.mkfifo(path)
    with pytest.raises(ValueError, match="regular"):
        checkpoint._read(path, 100)


def test_owned_checkpoint_has_no_native_persistence_or_default_law_change(owned):
    binding, parent = owned[0]
    assert binding.inputs["persistence"] == "none"
    assert parent.entry_receipt["native_load_called"] is False
    assert parent.entry_receipt["physical_seed_claim"] is False
    assert parent.active.stores["gj_block"] is not None


@pytest.fixture
def software_checkpoint(tmp_path, monkeypatch):
    """Unowned plain records only; every real scientific entry is forbidden.

    The metadata gate below is a fault-injection seam, never owner admission.
    Tests using it must fail before a receipt. Its operation record deliberately
    differs from the required real ownership record, and its producer is marked
    synthetic, so any visible test manifest cannot become a real run parent.
    """
    forbidden, gates = [], []

    def block(label):
        def denied(*args, **kwargs):
            forbidden.append(label)
            raise AssertionError("Scientific entry forbidden in software control: " + label)

        return denied

    for name in (
        "bind",
        "begin",
        "verify",
        "advance",
        "transition",
        "complete_INIT",
        "entry_receipt",
        "pause",
        "resume",
        "next_call",
    ):
        monkeypatch.setattr(run, name, block("run." + name))
    for module, names in (
        (run.composition.phase, ("bind", "initialize", "verify", "advance")),
        (run.composition.lifecycle, ("bind", "transition", "verify")),
        (run.composition.lifecycle.setup, ("numpy_restore",)),
        (run.composition.lifecycle.setup.init_setup, ("python_restore",)),
        (np.random, ("get_state", "set_state", "RandomState")),
        (checkpoint.random, ("getstate", "setstate")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, block(module.__name__ + "." + name))
    monkeypatch.setattr(checkpoint, "_rng_identity", block("checkpoint.RNG"))

    def plain(cls, **values):
        names = [field.name for field in fields(cls)] if is_dataclass(cls) else cls._fields
        return cls(**{name: values.get(name) for name in names})

    calendar = plain(run.calendars.NativePhaseCalendar, phase="INIT", step_count=0)
    phase = run.composition.phase
    component = plain(phase.Binding, calendar=calendar, identity="b" * 64)
    binding = run.Binding(component, dict(synthetic_control_only=True), "b" * 64)
    active = plain(
        phase.State,
        clock=plain(phase.Clock, call_index=0),
        stores=dict(values=np.array([3.0, -0.0])),
        identity="a" * 64,
    )
    parent = run.RunState(
        binding.identity,
        active,
        dict(synthetic_control_only=True),
        active,
        (),
        (),
        "ready",
        "c" * 64,
    )

    def metadata_gate(binding, parent, attempts):
        gates.append("synthetic_metadata_gate")
        attempts.append(
            dict(
                operation="synthetic_metadata_gate",
                numerical_work_possible=False,
                status="returned",
                producer_rebinds=0,
                timesteps=0,
            )
        )

    monkeypatch.setattr(checkpoint, "_verify", metadata_gate)
    monkeypatch.setattr(checkpoint, "producer_identity", lambda: dict(synthetic_only=True))
    temporary = []

    def mkstemp(*, prefix, suffix, dir):
        path = Path(dir) / (prefix + "synthetic-" + str(len(temporary)) + suffix)
        temporary.append(path)
        return os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600), str(path)

    monkeypatch.setattr(checkpoint.tempfile, "mkstemp", mkstemp)
    value = SimpleNamespace(binding=binding, parent=parent, gates=gates, temporary=temporary)
    yield value
    (tmp_path / "software-control.json").write_text(
        json.dumps(
            dict(
                synthetic_only=True,
                mock_ownership_gate_invocations=len(gates),
                forbidden_entry_attempts=forbidden,
                actual_owner_verifier_invocations=0,
                actual_setup_RNG_timestep_invocations=0,
                independent_scientific_credit=0,
            ),
            indent=2,
        )
        + "\n"
    )
    assert forbidden == []


@pytest.mark.parametrize(
    "fault",
    [
        "prefix",
        "arrays",
        "array_sync",
        "failure_json",
        "failure_sync",
        "directory_sync",
        "parent_sync",
        "all",
    ],
)
def test_software_checkpoint_secondary_recovery_failure_keeps_primary(
    software_checkpoint, tmp_path, monkeypatch, fault
):
    specimen = software_checkpoint
    destination = tmp_path / "refused"
    primary, cause, secondary = (
        OSError("Primary payload failure"),
        ValueError("Original cause"),
        OSError("Secondary recovery failure"),
    )

    def interrupted(encoder, directory, tree):
        (directory / "state.json").write_bytes(b"preserved partial JSON")
        (directory / "arrays.npz").write_bytes(b"preserved partial NPZ")
        raise primary from cause

    monkeypatch.setattr(checkpoint.codec.Encoder, "write", interrupted)
    write, savez, sync, fsync = (
        checkpoint._write_json,
        np.savez,
        checkpoint._sync_directory,
        os.fsync,
    )

    def metadata(path, value):
        if (
            fault == "prefix"
            and path.name == "input-prefix.json"
            or fault == "failure_json"
            and path.name == "failure.json"
            or fault == "all"
            and path.name != "request.json"
        ):
            raise secondary
        return write(path, value)

    def arrays(stream, **values):
        if fault in ("arrays", "all"):
            raise secondary
        return savez(stream, **values)

    def durable(fd):
        name = Path(os.readlink(f"/proc/self/fd/{fd}")).name
        if (fault == "array_sync" and name == "input-arrays.npz") or (
            fault == "failure_sync" and name == "failure.json"
        ):
            raise secondary
        return fsync(fd)

    def directory(path):
        if (
            fault == "all"
            or (fault == "directory_sync" and path == destination)
            or (fault == "parent_sync" and path == destination.parent)
        ):
            raise secondary
        return sync(path)

    monkeypatch.setattr(checkpoint, "_write_json", metadata)
    monkeypatch.setattr(np, "savez", arrays)
    monkeypatch.setattr(checkpoint.os, "fsync", durable)
    monkeypatch.setattr(checkpoint, "_sync_directory", directory)
    with pytest.raises(checkpoint.CheckpointRejected) as caught:
        save(destination, specimen.binding, specimen.parent)
    rejection = caught.value
    assert rejection.primary is rejection.__cause__ is primary
    assert primary.__cause__ is cause and rejection.stage == "save.payload"
    assert rejection.primary_chain == [primary, cause]
    assert rejection.primary_traceback is not None
    assert rejection.binding is specimen.binding and rejection.parent is specimen.parent
    assert rejection.capture["graph"]["parent"] is specimen.parent
    buffers = rejection.capture["arrays"]
    assert len(buffers) == 1
    assert (
        next(iter(buffers.values())).tobytes() == specimen.parent.active.stores["values"].tobytes()
    )
    assert rejection.attempts == () and rejection.recovery_errors
    assert all(row["error"] is secondary for row in rejection.recovery_errors)
    assert (destination / "state.json").read_bytes() == b"preserved partial JSON"
    assert (destination / "arrays.npz").read_bytes() == b"preserved partial NPZ"
    assert not (destination / "manifest.json").exists()
    if fault not in ("failure_json", "failure_sync", "all"):
        recorded = json.loads((destination / "failure.json").read_text())
        assert recorded["stage"] == "save.payload"
        assert [row["type"] for row in recorded["exception_chain"]] == ["OSError", "ValueError"]
    if fault in ("failure_json", "failure_sync"):
        recorded = json.loads((destination / "recovery-errors.json").read_text())
        assert recorded["primary"]["message"] == str(primary)
        assert recorded["primary"]["parent_identity"] == specimen.parent.identity
        assert recorded["errors"][0]["stage"] == "recovery.failure_json"


def test_software_checkpoint_partial_encoding_and_prefix_failure_keep_original_graph(
    software_checkpoint, tmp_path, monkeypatch
):
    specimen = software_checkpoint
    unknown = object()
    specimen.parent.active.stores["unowned"] = unknown
    secondary = OSError("Prefix cannot be recorded")
    write = checkpoint._write_json

    def metadata(path, value):
        if path.name == "input-prefix.json":
            raise secondary
        return write(path, value)

    monkeypatch.setattr(checkpoint, "_write_json", metadata)
    with pytest.raises(checkpoint.CheckpointRejected, match="Missing ownership") as caught:
        save(tmp_path / "refused", specimen.binding, specimen.parent)
    rejection = caught.value
    assert rejection.stage == "save.capture" and rejection.capture["tree"] is None
    assert rejection.parent is specimen.parent
    assert rejection.parent.active.stores["unowned"] is unknown
    assert None in rejection.capture["nodes"] and len(rejection.capture["arrays"]) == 1
    assert rejection.recovery_errors[0]["stage"] == "recovery.input_prefix"
    assert rejection.recovery_errors[0]["error"] is secondary
    assert (tmp_path / "refused/input-arrays.npz").is_file()


@pytest.mark.parametrize(
    "fault",
    ["manifest_sync", "link_return", "directory_sync", "parent_sync", "unlink", "cleanup_sync"],
)
def test_software_checkpoint_publication_fault_reports_visible_marker_uncertainty(
    software_checkpoint, tmp_path, monkeypatch, fault
):
    specimen = software_checkpoint
    destination = tmp_path / "refused"
    primary, secondary = (
        OSError("Primary publication failure"),
        OSError("Failure metadata unavailable"),
    )
    link, sync, fsync, unlink, write = (
        os.link,
        checkpoint._sync_directory,
        os.fsync,
        Path.unlink,
        checkpoint._write_json,
    )
    parent_syncs = []

    def linked(source, target, **kwargs):
        result = link(source, target, **kwargs)
        if fault == "link_return":
            raise primary
        return result

    def durable(fd):
        if fault == "manifest_sync" and ".molecule-checkpoint-" in os.readlink(
            f"/proc/self/fd/{fd}"
        ):
            raise primary
        return fsync(fd)

    def directory(path):
        marker = (destination / "manifest.json").exists()
        if marker and path == destination.parent:
            parent_syncs.append(path)
        if marker and fault == "directory_sync" and path == destination:
            raise primary
        if (
            marker
            and path == destination.parent
            and (fault == "parent_sync" or fault == "cleanup_sync" and len(parent_syncs) == 2)
        ):
            raise primary
        return sync(path)

    def remove(path, **kwargs):
        if fault == "unlink" and path in specimen.temporary:
            raise primary
        return unlink(path, **kwargs)

    def metadata(path, value):
        if path.name == "failure.json":
            raise secondary
        return write(path, value)

    monkeypatch.setattr(checkpoint.os, "link", linked)
    monkeypatch.setattr(checkpoint.os, "fsync", durable)
    monkeypatch.setattr(checkpoint, "_sync_directory", directory)
    monkeypatch.setattr(Path, "unlink", remove)
    monkeypatch.setattr(checkpoint, "_write_json", metadata)
    with pytest.raises(checkpoint.CheckpointRejected) as caught:
        save(destination, specimen.binding, specimen.parent)
    rejection = caught.value
    assert rejection.primary is rejection.__cause__ is primary
    assert rejection.binding is specimen.binding and rejection.parent is specimen.parent
    assert (
        len(rejection.attempts) == 1 and rejection.attempts[0]["numerical_work_possible"] is False
    )
    assert any(
        row["stage"] == "recovery.failure_json" and row["error"] is secondary
        for row in rejection.recovery_errors
    )
    marker = fault != "manifest_sync"
    assert (destination / "manifest.json").exists() is marker
    assert rejection.publication["manifest_visibility"] == ("visible" if marker else "absent")
    assert rejection.publication["durability"] == ("uncertain" if marker else "not_published")
    assert rejection.publication["success_receipt_returned"] is False
    record = json.loads((destination / "recovery-errors.json").read_text())["primary"]
    assert record["no_checkpoint_admission"] is (None if marker else True)
    if fault != "cleanup_sync":
        assert specimen.temporary[0].exists()


@pytest.mark.parametrize("fault", ["manifest_parse", "payload_read"])
def test_software_checkpoint_load_keeps_raw_inputs_when_recovery_also_fails(
    software_checkpoint, tmp_path, monkeypatch, fault
):
    specimen = software_checkpoint
    source, evidence = tmp_path / "source", tmp_path / "load"
    source.mkdir()
    for name in checkpoint.FILES:
        (source / name).write_bytes(b"unadmitted synthetic bytes")
    manifest = dict(
        kind=checkpoint.KIND,
        complete=True,
        producer=dict(synthetic_only=True),
        binding_identity=specimen.binding.identity,
        binding_seal=checkpoint.codec.fingerprint(specimen.binding),
        parent_identity=specimen.parent.identity,
        phase="INIT",
        cursor=0,
        status="ready",
        graph_seal="d" * 64,
        files={name: checkpoint._sha(source / name) for name in checkpoint.FILES},
    )
    manifest["identity"] = checkpoint.digest(manifest)
    (source / "manifest.json").write_text(json.dumps(manifest))
    before = {path.name: checkpoint._sha(path) for path in source.iterdir()}
    primary, secondary = OSError("Primary load failure"), OSError("Secondary load evidence failure")
    read, parse, raw = checkpoint._read, checkpoint.codec.parse_json, checkpoint._raw_file

    def read_input(path, maximum):
        if fault == "payload_read" and path.name == "state.json":
            raise primary
        return read(path, maximum)

    def parse_input(data, limits):
        if fault == "manifest_parse":
            raise primary
        return parse(data, limits)

    def capture(path, data):
        if path.name == "input-manifest.json":
            raise secondary
        return raw(path, data)

    monkeypatch.setattr(checkpoint, "_read", read_input)
    monkeypatch.setattr(checkpoint.codec, "parse_json", parse_input)
    monkeypatch.setattr(checkpoint, "_raw_file", capture)
    with pytest.raises(checkpoint.CheckpointRejected) as caught:
        load(source, specimen.binding, specimen.parent, evidence)
    rejection = caught.value
    assert rejection.primary is rejection.__cause__ is primary
    assert rejection.binding is specimen.binding and rejection.parent is None
    assert rejection.capture["expected_parent_identity"] == specimen.parent.identity
    assert rejection.capture["raw"]["manifest.json"] == (source / "manifest.json").read_bytes()
    assert len(rejection.capture["raw"]) == (1 if fault == "manifest_parse" else 4)
    assert any(
        row["stage"] == "recovery.raw.manifest.json" and row["error"] is secondary
        for row in rejection.recovery_errors
    )
    assert before == {path.name: checkpoint._sha(path) for path in source.iterdir()}
    assert rejection.attempts == ()


def _synthetic_transition_refusal(
    message=conditional.SIM_PREREQUISITE, stage="actual_retained_molecule54_transition"
):
    return run.RunRejected(message, dict(stage=stage, automatic_retry=False))


@pytest.mark.parametrize("operation", ["save", "load"])
def test_software_checkpoint_visibility_probe_failure_preserves_unknown_and_parent(
    software_checkpoint, tmp_path, monkeypatch, operation
):
    specimen = software_checkpoint
    source = tmp_path / "source"
    source.mkdir()
    marker = source / "manifest.json"
    marker.write_bytes(b"preserved synthetic visible marker")
    evidence = source if operation == "save" else tmp_path / "load"
    if operation == "load":
        evidence.mkdir()
    primary, secondary = OSError("Primary refusal"), OSError("Marker observation unavailable")
    observe = os.lstat

    def interrupted(path, **kwargs):
        if Path(path) == marker:
            raise secondary
        return observe(path, **kwargs)

    monkeypatch.setattr(checkpoint.os, "lstat", interrupted)
    context = dict(
        operation=operation,
        source=str(source),
        binding=specimen.binding,
        parent=specimen.parent,
        expected_phase="INIT",
        expected_parent_identity=specimen.parent.identity,
        input_written=True,
        tree=None,
        graph=dict(parent=specimen.parent),
        raw={"manifest.json": marker.read_bytes()},
    )
    publication = dict(complete=False)
    rejection = checkpoint._refusal(
        primary, evidence, [], "synthetic.refusal", context, publication
    )
    assert rejection.primary is primary and rejection.parent is specimen.parent
    assert rejection.capture["graph"]["parent"] is specimen.parent
    assert rejection.publication["manifest_visibility"] == "unknown"
    assert rejection.recovery_errors[0] == dict(stage="recovery.observe_manifest", error=secondary)
    record = json.loads((evidence / "failure.json").read_text())
    assert record["no_checkpoint_admission"] is (None if operation == "save" else True)
    assert record["parent_identity"] == specimen.parent.identity
    assert record["available_capture"]["parent_available_in_memory"] is True
    assert marker.read_bytes() == b"preserved synthetic visible marker"


def test_software_checkpoint_marker_absence_does_not_erase_recorded_link_history(
    software_checkpoint, tmp_path
):
    specimen = software_checkpoint
    directory = tmp_path / "refused"
    directory.mkdir()
    temporary = tmp_path / "synthetic-manifest"
    temporary.write_bytes(b"preserved synthetic publication")
    os.link(temporary, directory / "manifest.json")
    (directory / "manifest.json").rename(directory / "moved-manifest.json")
    context = dict(
        operation="save",
        source=str(directory),
        binding=specimen.binding,
        parent=specimen.parent,
        expected_phase="INIT",
        expected_parent_identity=specimen.parent.identity,
        input_written=True,
        tree=None,
    )
    publication = dict(complete=False, link_attempted=True, link_returned=True)
    rejection = checkpoint._refusal(
        OSError("Post-link refusal"), directory, [], "publish.sync_directory", context, publication
    )
    assert rejection.publication["manifest_visibility"] == "absent"
    assert rejection.publication["durability"] == "uncertain"
    record = json.loads((directory / "failure.json").read_text())
    assert record["no_checkpoint_admission"] is None
    assert (directory / "moved-manifest.json").read_bytes() == temporary.read_bytes()


@pytest.mark.parametrize(
    "fault",
    [
        "known",
        "wrong_stage",
        "wrong_message",
        "unretained",
        "io",
        "type",
        "assertion",
        "retention_io",
    ],
)
def test_software_checkpoint_only_exact_retained_SIM_refusal_can_xfail(
    software_checkpoint, tmp_path, monkeypatch, fault
):
    error = (
        OSError("Unexpected evidence I/O")
        if fault == "io"
        else TypeError("Unexpected type failure")
        if fault == "type"
        else AssertionError("Unexpected assertion")
        if fault == "assertion"
        else _synthetic_transition_refusal(stage="other")
        if fault == "wrong_stage"
        else _synthetic_transition_refusal(message="other")
        if fault == "wrong_message"
        else _synthetic_transition_refusal()
    )
    secondary = OSError("Retained archive I/O failure")

    def prepare(directory, *args):
        if fault == "unretained":
            raise error
        directory.mkdir()
        retain = conditional._retainer(directory, [])

        def refuse():
            raise error

        return retain("actual-INIT-to-SIM", refuse)

    if fault == "retention_io":

        def interrupted(*args, **kwargs):
            raise secondary

        monkeypatch.setattr(conditional.archives, "write_archive", interrupted)
    monkeypatch.setitem(globals(), "prepare_SIM", prepare)
    specimen = software_checkpoint
    owned = ((specimen.binding, specimen.parent), (specimen.binding, specimen.parent))
    if fault == "known":
        with pytest.raises(pytest.xfail.Exception):
            test_actual_SIM_transition_and_both_phase_associations_roundtrip(owned, tmp_path)
        assert retained_SIM_prerequisite(error) is True
    else:
        expected = secondary if fault == "retention_io" else error
        with pytest.raises(type(expected)) as caught:
            test_actual_SIM_transition_and_both_phase_associations_roundtrip(owned, tmp_path)
        assert caught.value is expected
        if fault == "retention_io":
            assert secondary.__cause__ is error
            assert error.checkpoint_retention["payload"]["available"]["partial"] is error.partial


def test_software_checkpoint_corrupt_retained_SIM_evidence_is_not_an_xfail(
    software_checkpoint, tmp_path
):
    directory = tmp_path / "transition"
    directory.mkdir()
    error = _synthetic_transition_refusal()

    def refuse():
        raise error

    with pytest.raises(run.RunRejected):
        conditional._retainer(directory, [])("actual-INIT-to-SIM", refuse)
    archive = directory / "actual-INIT-to-SIM"
    with (archive / "data.json").open("ab") as stream:
        stream.write(b"preserved deliberate corruption")
    with pytest.raises(ValueError, match="Changed retained SIM prerequisite payload"):
        retained_SIM_prerequisite(error)


@pytest.mark.parametrize("kind", [OSError, TypeError, AssertionError, run.RunRejected])
def test_software_checkpoint_journal_failures_are_never_broadly_xfailed(
    software_checkpoint, tmp_path, monkeypatch, kind
):
    error = (
        _synthetic_transition_refusal()
        if kind is run.RunRejected
        else kind("Unexpected journal failure")
    )
    specimen = software_checkpoint
    monkeypatch.setitem(
        globals(), "prepare_INIT", lambda *args: (specimen.binding, specimen.parent)
    )

    def refuse(*args, **kwargs):
        raise error

    monkeypatch.setitem(globals(), "accepted_prefix", refuse)
    with pytest.raises(kind) as caught:
        test_actual_journal_and_sampling_prefix_conditional(tmp_path)
    assert caught.value is error
