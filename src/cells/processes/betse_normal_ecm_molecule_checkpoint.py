"""Cells-owned durable checkpoints for the existing ordinary molecule run.

Save/load do not change persistence='none', execute a timestep, rebind/setup a
producer, or implement native BETSE pickle parity. The complete existing run
record is restored under a caller-supplied binding, phase and parent identity.
Ownership verification is numerical work and is recorded before it is attempted.
"""

import hashlib
import importlib
import os
import random
import re
import sys
import tempfile
import traceback
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import numpy as np

import cells
from cells.core.specs import digest
from cells.io import runtime_identity
from cells.physiology_checkpoint import _sha, _sync_directory, _write_json
from cells.processes import betse_normal_ecm_molecule_checkpoint_codec as codec
from cells.processes import betse_normal_ecm_molecule_checkpoint_records as records
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run

KIND = "cells.ordinary_ecm_molecule_headless_checkpoint@1"
FILES = frozenset(("state.json", "arrays.npz", "operation.json", "request.json"))
RNG_POLICY = "owned_setup_manifests_only_no_live_or_unowned_draws@1"


@dataclass(frozen=True)
class Receipt:
    directory: Path
    identity: str
    binding_identity: str
    parent_identity: str
    phase: str
    cursor: int
    status: str
    verification_attempts: int


@dataclass(frozen=True)
class Loaded:
    binding: run.Binding
    parent: run.RunState
    failure: object
    receipt: Receipt
    operation: object


class CheckpointRejected(ValueError):
    def __init__(self, error, evidence, attempts):
        super().__init__(str(error))
        self.evidence = Path(evidence)
        self.attempts = tuple(attempts)


def producer_identity():
    """Pin the actual scientific import closure, codec/helpers and CPU runtime.

    Unrelated tissue changes need not rebase a molecule checkpoint. Only the
    closed, already-imported Cells dependency modules select source paths.
    """
    pending, scientific = [run], {}
    while pending:
        module = pending.pop()
        if module.__name__ in scientific:
            continue
        scientific[module.__name__] = module
        for value in vars(module).values():
            name = (
                value.__name__
                if isinstance(value, ModuleType)
                else getattr(value, "__module__", "")
            )
            if name.startswith("cells.") and name in sys.modules and name not in scientific:
                pending.append(sys.modules[name])
    for name in (
        codec.__name__,
        records.__name__,
        __name__,
        "cells.io",
        "cells.physiology_checkpoint",
        "cells.core.specs",
    ):
        scientific[name] = importlib.import_module(name)
    root = Path(cells.__file__).resolve().parent
    sources = {}
    for module in scientific.values():
        path = Path(module.__file__).resolve()
        codec.require(path.is_relative_to(root) and path.suffix == ".py", "Unowned producer module")
        sources[str(path.relative_to(root))] = _sha(path)
    executable = Path(sys.executable).resolve()
    return dict(
        kind="cells.molecule_checkpoint_producer@1",
        source_hashes=sources,
        runtime=runtime_identity("cpu"),
        executable=dict(path=str(executable), sha256=_sha(executable)),
        rng_policy=RNG_POLICY,
    )


def _expect(binding, phase, parent_identity):
    codec.require(type(binding) is run.Binding, "Actual externally supplied run binding required")
    codec.require(
        type(phase) is str and phase in {"INIT", "SIM"},
        "Explicit INIT/SIM checkpoint phase required",
    )
    codec.require(
        type(parent_identity) is str and re.fullmatch("[0-9a-f]{64}", parent_identity),
        "Explicit externally expected parent identity required",
    )
    actual = run.composition.kind(binding.composition)
    codec.require(actual == phase, "Wrong checkpoint phase for supplied binding")


def _scope(binding, parent):
    actual = run.composition.phase_state(parent.active)
    phase_binding = (
        binding.composition
        if run.composition.kind(binding.composition) == "INIT"
        else parent.active.phase_binding
    )
    flags = phase_binding.inputs_raw["flags"]
    for name in (
        "fluid_flow",
        "td_deform",
        "sim_eosmosis",
        "physical_initialization",
        "cut_requested",
        "Ca_dyn",
    ):
        codec.require(flags.get(name) is False, "Unsupported checkpoint scope: " + name)
    codec.require(
        flags["solver"] == "FULL" and flags["is_ecm"] is True, "Ordinary FULL/ECM checkpoint only"
    )
    setup = phase_binding.inputs_raw["setup"]
    codec.require(
        setup["channel_noise_level"] == 0
        and setup["dynamic_noise"] == dict(enabled=False, level=0.0),
        "Live/unowned RNG continuation is unsupported",
    )
    receipt = phase_binding.setup_receipt
    codec.require(
        "numpy_rng_after" in receipt and "python_rng_after" in receipt["event_finalization"],
        "Missing actual owned setup RNG manifests",
    )
    # Validate the actual manifests with the existing private-stream parsers;
    # never install them as process-global RNG or invent replacement streams.
    run.composition.lifecycle.setup.numpy_restore(run.ions.data(receipt["numpy_rng_after"]))
    run.composition.lifecycle.setup.init_setup.python_restore(
        run.ions.data(receipt["event_finalization"]["python_rng_after"])
    )
    codec.require(actual.cursor == parent.cursor, "Phase/run cursor ownership differs")
    codec.require(
        parent.entry_receipt["native_load_called"] is False
        and parent.entry_receipt["physical_seed_claim"] is False,
        "Native/physical/post-cut continuation is unsupported",
    )


def _rng_identity():
    state = np.random.get_state()
    return digest(
        dict(
            numpy=[state[0], state[1].tolist(), state[2], state[3], state[4]],
            python=random.getstate(),
        )
    )


def _verify(binding, parent, attempts):
    event = dict(
        operation="existing_run_ownership_contract_and_scope",
        numerical_work_possible=True,
        status="attempted",
        producer_rebinds=0,
        timesteps=0,
    )
    attempts.append(event)
    before = _rng_identity()
    try:
        run.verify(binding, parent)
        _scope(binding, parent)
        codec.require(
            _rng_identity() == before, "Ownership validation consumed an unowned process RNG"
        )
    except BaseException as error:
        event.update(
            status="refused",
            type=type(error).__name__,
            message=str(error),
            global_rng_unchanged=_rng_identity() == before,
        )
        raise
    event.update(status="returned", global_rng_unchanged=True)


def failure_record(error, parent):
    """Retain the actual owned failed prefix/cause, not an invented completion."""
    codec.require(
        type(error) is run.RunRejected and isinstance(error.partial, Mapping),
        "Actual RunRejected evidence required for a failed run",
    )
    partial = error.partial
    accepted = partial.get("accepted")
    codec.require(
        type(accepted) is run.RunState
        and accepted.identity == parent.identity
        and accepted.status == parent.status == "failed"
        and partial.get("automatic_retry") is False
        and partial.get("native_pickle_called") is False,
        "Failure evidence is foreign to this exact failed run",
    )
    chain, seen, current = [], set(), error
    while current is not None:
        codec.require(id(current) not in seen, "Cyclic exception chain")
        seen.add(id(current))
        chain.append(
            dict(
                type=type(current).__module__ + "." + type(current).__qualname__,
                message=str(current),
            )
        )
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return dict(
        partial=partial, exception_chain=chain, traceback="".join(traceback.format_exception(error))
    )


def _check_failure(parent, failure):
    if parent.status == "failed":
        codec.require(
            type(failure) is dict
            and set(failure) == {"partial", "exception_chain", "traceback"}
            and failure["exception_chain"]
            and failure["traceback"],
            "Complete failed-run evidence required",
        )
        partial = failure["partial"]
        codec.require(
            partial["accepted"].identity == parent.identity
            and partial["automatic_retry"] is False
            and partial["native_pickle_called"] is False,
            "Wrong failed-prefix association",
        )
    else:
        codec.require(failure is None, "A nonfailed run cannot adopt failure evidence")


def _read(path, maximum):
    """Hash/consume the same bounded regular inode, refusing links."""
    import stat

    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        info = os.fstat(stream.fileno())
        codec.require(
            stat.S_ISREG(info.st_mode) and info.st_size <= maximum,
            "Bounded regular checkpoint file required",
        )
        data = stream.read(maximum + 1)
    codec.require(
        len(data) == info.st_size <= maximum, "Checkpoint truncated or changed during reading"
    )
    return data


def _failure(directory, error, attempts):
    target = directory / "failure.json"
    if not target.exists():
        _write_json(
            target,
            dict(
                status="refused",
                type=type(error).__name__,
                message=str(error),
                attempts=attempts,
                no_checkpoint_admission=True,
                preserved_inputs=True,
                traceback="".join(traceback.format_exception(error)),
            ),
        )
        _sync_directory(directory)
        _sync_directory(directory.parent)


def _publish(directory, payload):
    """Atomic, nonreplacing commit marker after all payload bytes are durable."""
    fd, name = tempfile.mkstemp(
        prefix=".molecule-checkpoint-", suffix=".json", dir=directory.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(codec.json_bytes(payload) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, directory / "manifest.json", follow_symlinks=False)
        _sync_directory(directory)
        _sync_directory(directory.parent)
    finally:
        temporary.unlink(missing_ok=True)
        _sync_directory(directory.parent)


def save_checkpoint(
    directory,
    binding,
    parent,
    *,
    expected_phase,
    expected_parent_identity,
    failure=None,
    limits=codec.DEFAULT_LIMITS,
):
    """Save a complete, externally identified owned run; retain refused writes.

    Failed runs require their actual RunRejected object. A partial/refused
    directory never becomes a checkpoint. Existing destinations are untouched.
    The source run's persistence/native laws and defaults are not modified.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    attempts, encoder = [], None
    try:
        _write_json(
            directory / "request.json",
            dict(
                operation="save",
                expected_phase=expected_phase,
                expected_parent_identity=expected_parent_identity,
            ),
        )
        encoder = codec.Encoder(limits)
        retained_failure = failure_record(failure, parent) if failure is not None else None
        graph = dict(binding=binding, parent=parent, failure=retained_failure)
        tree = encoder.capture(graph)
        seal = encoder.seal(tree)
        encoder.write(directory, tree)
        _expect(binding, expected_phase, expected_parent_identity)
        codec.require(
            type(parent) is run.RunState and parent.identity == expected_parent_identity,
            "Wrong expected checkpoint parent",
        )
        _check_failure(parent, retained_failure)
        producer = producer_identity()
        _verify(binding, parent, attempts)
        codec.require(
            codec.fingerprint(graph, limits) == seal, "Save validation changed owned input state"
        )
        codec.require(
            producer_identity() == producer, "Producer/dependency changed during checkpoint save"
        )
        _write_json(
            directory / "operation.json", dict(attempts=attempts, producer_rebinds=0, timesteps=0)
        )
        payload = dict(
            kind=KIND,
            complete=True,
            producer=producer,
            binding_identity=binding.identity,
            binding_seal=codec.fingerprint(binding, limits),
            parent_identity=parent.identity,
            phase=expected_phase,
            cursor=parent.cursor,
            status=parent.status,
            graph_seal=seal,
            files={name: _sha(directory / name) for name in sorted(FILES)},
        )
        manifest = payload | dict(identity=digest(payload))
        _publish(directory, manifest)
        return Receipt(
            directory,
            manifest["identity"],
            binding.identity,
            parent.identity,
            expected_phase,
            parent.cursor,
            parent.status,
            len(attempts),
        )
    except BaseException as error:
        if not (directory / "state.json").exists() and encoder is not None and encoder.nodes:
            _write_json(
                directory / "input-prefix.json",
                dict(
                    complete=False,
                    nodes=encoder.nodes,
                    error="Unadmitted partial encoding; no reconstruction permitted",
                ),
            )
            with (directory / "input-arrays.npz").open("xb") as stream:
                np.savez(stream, allow_pickle=False, **encoder.arrays)
                stream.flush()
                os.fsync(stream.fileno())
        _failure(directory, error, attempts)
        raise CheckpointRejected(error, directory, attempts) from error


def load_checkpoint(
    directory,
    *,
    binding,
    expected_phase,
    expected_parent_identity,
    evidence_directory,
    expected_checkpoint_identity=None,
    limits=codec.DEFAULT_LIMITS,
):
    """Load without rebinding, setup, draw replay, transition or timestep work.

    The existing ownership verifier still performs numerical validation. Its
    attempted call is durably logged in a separate, exclusive evidence directory;
    neither successful nor refused loads write into the saved checkpoint.
    """
    directory, evidence = Path(directory), Path(evidence_directory)
    codec.require(
        not evidence.resolve().is_relative_to(directory.resolve())
        and not directory.resolve().is_relative_to(evidence.resolve()),
        "Load evidence must be separate from checkpoint",
    )
    evidence.mkdir(parents=True, exist_ok=False)
    attempts = []
    try:
        _write_json(
            evidence / "request.json",
            dict(
                operation="load",
                source=str(directory),
                expected_phase=expected_phase,
                expected_parent_identity=expected_parent_identity,
                expected_checkpoint_identity=expected_checkpoint_identity,
            ),
        )
        limits.check()
        _expect(binding, expected_phase, expected_parent_identity)
        codec.require(
            directory.is_dir() and not directory.is_symlink(),
            "Regular checkpoint directory required",
        )
        codec.require(
            {p.name for p in directory.iterdir()} == FILES | {"manifest.json"},
            "Incomplete, refused or extended checkpoint directory",
        )
        manifest_data = _read(directory / "manifest.json", limits.json_bytes)
        manifest = codec.parse_json(manifest_data, limits)
        fields = {
            "kind",
            "complete",
            "producer",
            "binding_identity",
            "binding_seal",
            "parent_identity",
            "phase",
            "cursor",
            "status",
            "graph_seal",
            "files",
            "identity",
        }
        codec.require(
            type(manifest) is dict and set(manifest) == fields, "Incomplete checkpoint manifest"
        )
        payload = {k: v for k, v in manifest.items() if k != "identity"}
        codec.require(
            manifest["kind"] == KIND
            and manifest["complete"] is True
            and manifest["identity"] == digest(payload),
            "Checkpoint manifest identity changed",
        )
        codec.require(
            expected_checkpoint_identity is None
            or manifest["identity"] == expected_checkpoint_identity,
            "Wrong expected checkpoint identity",
        )
        codec.require(
            manifest["phase"] == expected_phase
            and manifest["parent_identity"] == expected_parent_identity,
            "Wrong checkpoint phase or parent",
        )
        codec.require(
            manifest["binding_identity"] == binding.identity
            and manifest["binding_seal"] == codec.fingerprint(binding, limits),
            "Complete supplied binding mismatch",
        )
        producer = producer_identity()
        codec.require(
            manifest["producer"] == producer, "Checkpoint producer/dependency/runtime mismatch"
        )
        codec.require(
            type(manifest["files"]) is dict and set(manifest["files"]) == FILES,
            "Checkpoint payload list differs",
        )
        raw = {
            name: _read(
                directory / name,
                limits.archive_bytes if name == "arrays.npz" else limits.json_bytes,
            )
            for name in sorted(FILES)
        }
        for name, data in raw.items():
            codec.require(
                hashlib.sha256(data).hexdigest() == manifest["files"][name],
                "Checkpoint payload hash changed: " + name,
            )
        saved_operation = codec.parse_json(raw["operation.json"], limits)
        saved_request = codec.parse_json(raw["request.json"], limits)
        codec.require(
            saved_request
            == dict(
                operation="save",
                expected_phase=expected_phase,
                expected_parent_identity=expected_parent_identity,
            ),
            "Saved request/parent association changed",
        )
        codec.require(
            type(saved_operation) is dict
            and set(saved_operation) == {"attempts", "producer_rebinds", "timesteps"}
            and saved_operation["producer_rebinds"] == saved_operation["timesteps"] == 0
            and type(saved_operation["attempts"]) is list
            and len(saved_operation["attempts"]) == 1
            and saved_operation["attempts"][0]["status"] == "returned"
            and saved_operation["attempts"][0]["numerical_work_possible"] is True,
            "Missing successful save ownership-validation evidence",
        )
        graph = codec.decode(codec.parse_json(raw["state.json"], limits), raw["arrays.npz"], limits)
        codec.require(
            type(graph) is dict and set(graph) == {"binding", "parent", "failure"},
            "Complete run graph required",
        )
        codec.require(
            codec.fingerprint(graph, limits) == manifest["graph_seal"],
            "Checkpoint graph category/buffer seal changed",
        )
        codec.require(
            codec.fingerprint(graph["binding"], limits) == manifest["binding_seal"],
            "Saved binding graph mismatch",
        )
        parent = graph["parent"]
        codec.require(
            type(parent) is run.RunState and parent.identity == expected_parent_identity,
            "Saved object is not the expected actual run parent",
        )
        codec.require(
            (parent.cursor, parent.status) == (manifest["cursor"], manifest["status"]),
            "Saved status/cursor mismatch",
        )
        _check_failure(parent, graph["failure"])
        _verify(binding, parent, attempts)
        codec.require(
            codec.fingerprint(graph, limits) == manifest["graph_seal"],
            "Load validation changed saved runtime state",
        )
        codec.require(producer_identity() == producer, "Producer changed during load validation")
        operation = dict(
            status="loaded",
            attempts=attempts,
            producer_rebinds=0,
            timesteps=0,
            saved_operation=saved_operation,
            checkpoint_identity=manifest["identity"],
            parent_identity=parent.identity,
        )
        _write_json(evidence / "operation.json", operation)
        _sync_directory(evidence)
        _sync_directory(evidence.parent)
        receipt = Receipt(
            directory,
            manifest["identity"],
            binding.identity,
            parent.identity,
            expected_phase,
            parent.cursor,
            parent.status,
            len(attempts),
        )
        return Loaded(binding, parent, graph["failure"], receipt, operation)
    except BaseException as error:
        _failure(evidence, error, attempts)
        raise CheckpointRejected(error, evidence, attempts) from error
