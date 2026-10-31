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
from enum import Enum
from importlib import metadata
from pathlib import Path
from types import ModuleType

import numpy as np

import cells
from cells.core.specs import digest
from cells.io import RUNTIME_PACKAGES, runtime_identity
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
    """Primary refusal plus available in-memory inputs if recovery I/O fails.

    Recovery errors never replace ``primary`` or its original exception chain.
    A rejected save may have a visible manifest: consult ``publication`` rather
    than treating this exception as proof that publication never happened.
    """

    def __init__(self, error, evidence, attempts, *, stage, context, publication):
        self.primary = error
        self.stage = stage
        self.evidence = Path(evidence)
        self.attempts = tuple(attempts)
        self.binding = context["binding"]
        self.parent = context["parent"]
        self.capture = context
        self.publication = publication
        self.recovery_errors = []
        self.primary_traceback = error.__traceback__
        self.primary_chain, seen, current = [], set(), error
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            self.primary_chain.append(current)
            current = current.__cause__ if current.__cause__ is not None else current.__context__
        self.primary_record = None
        try:
            self.primary_record = _exception_record(error)
        except BaseException as secondary:
            self.recovery_errors.append(dict(stage="recovery.primary_record", error=secondary))
        try:
            message = str(error)
        except BaseException as secondary:
            self.recovery_errors.append(dict(stage="recovery.primary_message", error=secondary))
            message = type(error).__name__
        super().__init__(message)


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
    runtime_files = {}
    for package in RUNTIME_PACKAGES:
        distribution = metadata.distribution(package)
        codec.require(distribution.files is not None, "Missing numerical runtime file inventory")
        for member in distribution.files:
            if str(member).endswith(".py") or ".so" in str(member) or str(member).endswith(".pyd"):
                path = Path(distribution.locate_file(member)).resolve()
                codec.require(path.is_file(), "Missing numerical runtime code file")
                runtime_files[str(path)] = _sha(path)
    for name in (
        "json",
        "json.decoder",
        "json.encoder",
        "zipfile",
        "ast",
        "struct",
        "io",
        "random",
        "tempfile",
        "hashlib",
        "traceback",
        "importlib.metadata",
        "enum",
        "_json",
        "_struct",
        "_hashlib",
        "binascii",
    ):
        module = importlib.import_module(name)
        if getattr(module, "__file__", None):
            path = Path(module.__file__).resolve()
            runtime_files[str(path)] = _sha(path)
    jax_configuration = {}
    for name, value in importlib.import_module("jax").config.values.items():
        if type(value) in (type(None), bool, int, float, str):
            jax_configuration[name] = value
        elif (
            isinstance(value, Enum)
            and type(value).__module__ == "jax._src.config"
            and type(value.value) in (bool, int, float, str)
        ):
            jax_configuration[name] = dict(
                enum_type=type(value).__module__ + "." + type(value).__qualname__,
                member=value.name,
                value=value.value,
            )
        else:
            raise ValueError("Unowned JAX runtime configuration object: " + name)
    codec.json_bytes(jax_configuration)
    return dict(
        kind="cells.molecule_checkpoint_producer@1",
        source_hashes=sources,
        runtime=runtime_identity("cpu"),
        executable=dict(path=str(executable), sha256=_sha(executable)),
        runtime_code_sha256=runtime_files,
        numpy_error_policy=np.geterr(),
        interpreter=dict(optimize=sys.flags.optimize, debug=__debug__, byteorder=sys.byteorder),
        jax_configuration=jax_configuration,
        numerical_environment={
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "XLA_FLAGS",
                "JAX_PLATFORMS",
                "JAX_ENABLE_X64",
                "JAX_DISABLE_JIT",
                "CUDA_VISIBLE_DEVICES",
            )
        },
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

    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
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


def _exception_record(error):
    chain, seen, current = [], set(), error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(
            dict(type=type(current).__name__, module=type(current).__module__, message=str(current))
        )
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return dict(
        type=type(error).__name__,
        module=type(error).__module__,
        message=str(error),
        traceback="".join(traceback.format_exception(error)),
        exception_chain=chain,
    )


def _recover(rejection, stage, operation):
    """One independent evidence attempt; its failure cannot mask the refusal."""
    try:
        return operation()
    except BaseException as error:
        rejection.recovery_errors.append(dict(stage=stage, error=error))
        return None


def _refusal_record(rejection):
    primary = rejection.primary_record or _exception_record(rejection.primary)
    capture = rejection.capture
    return dict(
        status="refused",
        **primary,
        stage=rejection.stage,
        attempts=rejection.attempts,
        success_receipt_returned=False,
        no_checkpoint_admission=(
            True
            if capture["operation"] == "load"
            or (
                rejection.publication["manifest_visibility"] == "absent"
                and not rejection.publication.get("link_attempted", False)
            )
            else None
        ),
        publication=rejection.publication,
        binding_identity=(
            rejection.binding.identity if type(rejection.binding) is run.Binding else None
        ),
        parent_identity=(
            rejection.parent.identity if type(rejection.parent) is run.RunState else None
        ),
        expected_phase=capture["expected_phase"],
        expected_parent_identity=capture["expected_parent_identity"],
        available_capture=dict(
            tree_complete=capture.get("tree") is not None,
            nodes=len(capture.get("nodes", ())),
            arrays=list(capture.get("arrays", {})),
            raw_files=list(capture.get("raw", {})),
            caller_binding_retained_in_memory=True,
            parent_available_in_memory=rejection.parent is not None,
        ),
    )


def _failure(directory, rejection):
    _write_json(directory / "failure.json", _refusal_record(rejection))


def _raw_file(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _refusal(error, directory, attempts, stage, context, publication, *, encoder=None):
    """Best-effort recovery, retaining actual objects independently of storage."""
    if encoder is not None:
        context.update(nodes=encoder.nodes, arrays=encoder.arrays)
    rejection = CheckpointRejected(
        error, directory, attempts, stage=stage, context=context, publication=publication
    )
    publication["success_receipt_returned"] = False

    def observe_manifest():
        try:
            os.lstat(Path(context["source"]) / "manifest.json")
        except FileNotFoundError:
            publication["manifest_visibility"] = "absent"
        else:
            publication["manifest_visibility"] = "visible"

    publication["manifest_visibility"] = "unknown"
    _recover(rejection, "recovery.observe_manifest", observe_manifest)
    if context["operation"] == "save":
        publication["durability"] = (
            "not_published"
            if publication["manifest_visibility"] == "absent"
            and not publication.get("link_attempted", False)
            else "uncertain"
        )
        if encoder is not None and encoder.nodes and not context.get("input_written", False):
            _recover(
                rejection,
                "recovery.input_prefix",
                lambda: _write_json(
                    directory / "input-prefix.json",
                    dict(
                        complete=False,
                        nodes=encoder.nodes,
                        root=context.get("tree", {}).get("root") if context.get("tree") else None,
                        error="Unadmitted available input; no reconstruction permitted",
                    ),
                ),
            )

            def arrays():
                with (directory / "input-arrays.npz").open("xb") as stream:
                    np.savez(stream, allow_pickle=False, **encoder.arrays)
                    stream.flush()
                    os.fsync(stream.fileno())

            _recover(rejection, "recovery.input_arrays", arrays)
    else:
        for name, data in context["raw"].items():
            _recover(
                rejection,
                "recovery.raw." + name,
                lambda name=name, data=data: _raw_file(directory / ("input-" + name), data),
            )
    _recover(rejection, "recovery.failure_json", lambda: _failure(directory, rejection))
    _recover(rejection, "recovery.sync_directory", lambda: _sync_directory(directory))
    _recover(rejection, "recovery.sync_parent", lambda: _sync_directory(directory.parent))
    if rejection.recovery_errors:
        # Later recovery failures cannot be appended to an already written
        # failure.json without overwriting evidence. Keep a separate record;
        # the exception's list remains authoritative if this write/sync fails.
        _recover(
            rejection,
            "recovery.secondary_json",
            lambda: _write_json(
                directory / "recovery-errors.json",
                dict(
                    primary=_refusal_record(rejection),
                    errors=[
                        dict(stage=row["stage"], **_exception_record(row["error"]))
                        for row in rejection.recovery_errors
                    ],
                ),
            ),
        )
        _recover(rejection, "recovery.secondary_sync", lambda: _sync_directory(directory))
    return rejection


def _publish(directory, payload, *, publication):
    """Publish atomically; retain temporary bytes on failure without rollback.

    A later I/O error can follow a successful link. The caller retains each
    completed step and reports publication uncertainty instead of hiding it.
    """
    publication["stage"] = "publish.create_temporary"
    fd, name = tempfile.mkstemp(
        prefix=".molecule-checkpoint-", suffix=".json", dir=directory.parent
    )
    temporary = Path(name)
    publication["temporary_path"] = str(temporary)
    with os.fdopen(fd, "wb") as stream:
        publication["stage"] = "publish.write_manifest"
        stream.write(codec.json_bytes(payload) + b"\n")
        stream.flush()
        publication["stage"] = "publish.sync_manifest"
        os.fsync(stream.fileno())
    publication["stage"] = "publish.link_manifest"
    publication["link_attempted"] = True
    os.link(temporary, directory / "manifest.json", follow_symlinks=False)
    publication["link_returned"] = True
    publication["stage"] = "publish.sync_directory"
    _sync_directory(directory)
    publication["directory_synced"] = True
    publication["stage"] = "publish.sync_parent"
    _sync_directory(directory.parent)
    publication["parent_synced"] = True
    publication["stage"] = "publish.unlink_temporary"
    temporary.unlink()
    publication["stage"] = "publish.sync_cleanup"
    _sync_directory(directory.parent)
    publication.update(complete=True, manifest_visibility="visible", durability="confirmed")


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

    Failed runs require their actual RunRejected object. Existing destinations
    are untouched. A refused call returns no receipt; after publication starts,
    its exception reports possible manifest visibility/durability uncertainty.
    The source run's persistence/native laws and defaults are not modified.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    attempts, encoder = [], None
    context = dict(
        operation="save",
        source=str(directory),
        binding=binding,
        parent=parent,
        expected_phase=expected_phase,
        expected_parent_identity=expected_parent_identity,
        failure_input=failure,
        input_written=False,
        tree=None,
    )
    publication = dict(
        complete=False,
        link_attempted=False,
        link_returned=False,
        directory_synced=False,
        parent_synced=False,
    )
    stage = "save.request"
    try:
        _write_json(
            directory / "request.json",
            dict(
                operation="save",
                expected_phase=expected_phase,
                expected_parent_identity=expected_parent_identity,
            ),
        )
        stage = "save.encoder"
        encoder = codec.Encoder(limits)
        stage = "save.failure_record"
        retained_failure = failure_record(failure, parent) if failure is not None else None
        graph = dict(binding=binding, parent=parent, failure=retained_failure)
        context["graph"] = graph
        stage = "save.capture"
        tree = encoder.capture(graph)
        context["tree"] = tree
        stage = "save.seal"
        seal = encoder.seal(tree)
        stage = "save.payload"
        encoder.write(directory, tree)
        context["input_written"] = True
        stage = "save.binding_and_parent"
        _expect(binding, expected_phase, expected_parent_identity)
        codec.require(
            type(parent) is run.RunState and parent.identity == expected_parent_identity,
            "Wrong expected checkpoint parent",
        )
        _check_failure(parent, retained_failure)
        stage = "save.producer"
        producer = producer_identity()
        stage = "save.ownership"
        _verify(binding, parent, attempts)
        stage = "save.unchanged"
        codec.require(
            codec.fingerprint(graph, limits) == seal, "Save validation changed owned input state"
        )
        codec.require(
            producer_identity() == producer, "Producer/dependency changed during checkpoint save"
        )
        stage = "save.operation"
        _write_json(
            directory / "operation.json", dict(attempts=attempts, producer_rebinds=0, timesteps=0)
        )
        stage = "save.manifest"
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
        context["manifest"] = manifest
        stage = "save.publish"
        _publish(directory, manifest, publication=publication)
        stage = "save.receipt"
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
        if stage == "save.publish":
            stage = publication.get("stage", stage)
        rejection = _refusal(
            error, directory, attempts, stage, context, publication, encoder=encoder
        )
        raise rejection from error


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
    context = dict(
        operation="load",
        source=str(directory),
        binding=binding,
        parent=None,
        raw={},
        expected_phase=expected_phase,
        expected_parent_identity=expected_parent_identity,
        tree=None,
    )
    publication = dict(complete=False, durability="not_assessed_by_refused_load")
    stage = "load.request"
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
        stage = "load.binding_and_directory"
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
        stage = "load.read.manifest.json"
        manifest_data = _read(directory / "manifest.json", limits.json_bytes)
        context["raw"]["manifest.json"] = manifest_data
        stage = "load.manifest"
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
            type(manifest["cursor"]) is int
            and manifest["cursor"] >= 0
            and type(manifest["status"]) is str
            and manifest["status"] in run.STATUS,
            "Checkpoint cursor/status categories changed",
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
        stage = "load.producer"
        producer = producer_identity()
        codec.require(
            manifest["producer"] == producer, "Checkpoint producer/dependency/runtime mismatch"
        )
        codec.require(
            type(manifest["files"]) is dict and set(manifest["files"]) == FILES,
            "Checkpoint payload list differs",
        )
        raw = {}
        for name in sorted(FILES):
            stage = "load.read." + name
            raw[name] = _read(
                directory / name,
                limits.archive_bytes if name == "arrays.npz" else limits.json_bytes,
            )
            context["raw"][name] = raw[name]
        stage = "load.payload_hashes"
        for name, data in raw.items():
            codec.require(
                hashlib.sha256(data).hexdigest() == manifest["files"][name],
                "Checkpoint payload hash changed: " + name,
            )
        stage = "load.operation"
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
        expected_operation = dict(
            attempts=[
                dict(
                    operation="existing_run_ownership_contract_and_scope",
                    numerical_work_possible=True,
                    status="returned",
                    producer_rebinds=0,
                    timesteps=0,
                    global_rng_unchanged=True,
                )
            ],
            producer_rebinds=0,
            timesteps=0,
        )
        codec.require(
            codec.json_bytes(saved_operation) == codec.json_bytes(expected_operation),
            "Missing successful save ownership-validation evidence",
        )
        stage = "load.decode"
        context["tree"] = codec.parse_json(raw["state.json"], limits)
        graph = codec.decode(context["tree"], raw["arrays.npz"], limits)
        context["graph"] = graph
        if type(graph) is dict:
            context["parent"] = graph.get("parent")
        stage = "load.graph"
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
        restored_binding = graph["binding"]
        stage = "load.ownership"
        _verify(restored_binding, parent, attempts)
        stage = "load.unchanged"
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
        stage = "load.operation_evidence"
        _write_json(evidence / "operation.json", operation)
        stage = "load.sync_directory"
        _sync_directory(evidence)
        stage = "load.sync_parent"
        _sync_directory(evidence.parent)
        stage = "load.receipt"
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
        # Return the reconstructed binding graph after its complete external
        # match, retaining aliases shared with the restored state. No producer
        # bind/reinitialization routine is used to construct these plain records.
        return Loaded(restored_binding, parent, graph["failure"], receipt, operation)
    except BaseException as error:
        rejection = _refusal(error, evidence, attempts, stage, context, publication)
        raise rejection from error
