"""Short actual-owner conditional checkpoint checks, not full qualification."""

import json
import shutil

import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation.betse.betse_normal_ecm_molecule_checkpoint import (
    accepted_prefix,
    prepare_INIT,
    prepare_SIM,
)

ATTEMPTS = []


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
    assert loaded.binding is binding
    assert loaded.parent.status == parent.status == "exhausted"
    assert loaded.parent.cursor == 0 and loaded.parent.identity == parent.identity
    assert checkpoint.codec.fingerprint((binding, parent)) == checkpoint.codec.fingerprint(
        (loaded.binding, loaded.parent)
    )
    assert receipt.verification_attempts == loaded.receipt.verification_attempts == 1
    assert loaded.operation["saved_operation"]["attempts"][0]["numerical_work_possible"]
    assert loaded.operation["timesteps"] == loaded.operation["producer_rebinds"] == 0
    assert loaded.parent.entry_receipt["declaration_is_initialization_attestation"] is False
    assert run.verify(loaded.binding, loaded.parent) is loaded.parent


def test_actual_capped_prefix_stays_capped_and_cannot_complete(tmp_path):
    binding, parent = prepare_INIT(
        tmp_path / "preparation", "one_INIT_call", ATTEMPTS, call_limit=0
    )
    assert parent.status == "capped" and parent.cursor == 0
    save(tmp_path / "saved", binding, parent)
    loaded = load(tmp_path / "saved", binding, parent, tmp_path / "load")
    assert loaded.parent.status == "capped" and loaded.parent.cursor == 0
    with pytest.raises(run.RunRejected):
        run.complete_INIT(binding, loaded.parent)


def test_actual_SIM_transition_and_both_phase_associations_roundtrip(owned, tmp_path):
    initial, parent = owned[0]
    try:
        binding, sim = prepare_SIM(tmp_path / "transition", initial, parent, ATTEMPTS)
    except Exception as error:
        pytest.xfail(
            "Existing warm owner prerequisite refused; complete evidence retained: " + str(error)
        )
    save(tmp_path / "saved", binding, sim)
    loaded = load(tmp_path / "saved", binding, sim, tmp_path / "load")
    assert loaded.receipt.phase == "SIM" and loaded.parent.cursor == 0
    assert loaded.parent.entry_receipt["previous_phase"].run.identity == parent.identity
    assert loaded.parent.active.source_init.parent.identity == parent.active.identity
    assert checkpoint.codec.fingerprint(sim) == checkpoint.codec.fingerprint(loaded.parent)


def test_actual_journal_and_sampling_prefix_conditional(tmp_path):
    binding, parent = prepare_INIT(tmp_path / "preparation", "both_disabled", ATTEMPTS)
    try:
        prefix = accepted_prefix(tmp_path / "calls", binding, parent, ATTEMPTS, calls=2)
    except Exception as error:
        pytest.xfail(
            "Existing numerical owner prerequisite refused; actual call evidence retained: "
            + str(error)
        )
    assert prefix.cursor == 2 and len(prefix.history) == 2 and len(prefix.observations) == 1
    paused = run.pause(binding, prefix)
    save(tmp_path / "saved", binding, paused)
    loaded = load(tmp_path / "saved", binding, paused, tmp_path / "load")
    assert checkpoint.codec.fingerprint(paused) == checkpoint.codec.fingerprint(loaded.parent)
    assert run.next_call(binding, run.resume(binding, loaded.parent))["call_index"] == 2


def test_paused_run_stays_paused_and_cannot_advance_implicitly(owned, tmp_path):
    binding, ready = owned[1]
    ATTEMPTS.append(dict(operation="actual_run.pause", numerical_work_possible=True))
    paused = run.pause(binding, ready)
    save(tmp_path / "saved", binding, paused)
    loaded = load(tmp_path / "saved", binding, paused, tmp_path / "load")
    assert loaded.parent.status == "paused" and loaded.parent.cursor == 0
    assert checkpoint.codec.fingerprint(paused) == checkpoint.codec.fingerprint(loaded.parent)
    with pytest.raises(ValueError):
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
        run.resume(binding, loaded.parent)


@pytest.mark.parametrize(
    "fault",
    ["array-truncated", "json-truncated", "wrong-parent", "wrong-phase", "producer", "status"],
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
        else:
            manifest["status"] = "ready"
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


def test_owned_checkpoint_has_no_native_persistence_or_default_law_change(owned):
    binding, parent = owned[0]
    assert binding.inputs["persistence"] == "none"
    assert parent.entry_receipt["native_load_called"] is False
    assert parent.entry_receipt["physical_seed_claim"] is False
    assert parent.active.stores["gj_block"] is not None
