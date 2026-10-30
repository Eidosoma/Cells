"""Complete controlled charged-loop restart with mandatory blocker context.

The frozen loop codec runs in the same private control scope as admission.
Distinct inner semantic kinds prevent accidental bare restoration that would
drop the original calendar/blocker memory. Manifests publish last; raw failed
states/intervals/packets can be journaled through the existing numeric archive.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells import physiology_protein_batch_loop_io as raw_io
from cells import physiology_protein_checkpoint as origin_io
from cells.core import physiology_protein_batch_loop as journal
from cells.core import physiology_protein_block_calendar as calls
from cells.core import physiology_protein_block_calendar_scope as scoped
from cells.core.specs import ConfigError, digest, read_json
from cells.io import runtime_identity, source_hashes
from cells.physiology_checkpoint import _sha, _sync_directory, _write_json

KIND = "cells.complete_charged_protein_block_calendar_restart@1"
FILES = frozenset(("charged/manifest.json", "block-context.json", "block-state.npz"))


@dataclass(frozen=True, slots=True)
class ProteinBlockSnapshot:
    spec: object
    checkpoint: calls.ProteinBlockCheckpoint
    identity: str


def write_checkpoint(directory, spec, checkpoint):
    context = calls.validate(spec, checkpoint)
    sources, runtime = source_hashes(), runtime_identity("cpu")
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    context.codec.write_protein_loop_checkpoint(path / "charged", spec, checkpoint.point)
    _write_json(
        path / "block-context.json",
        dict(
            calendar=scoped.clocks.record(checkpoint.calendar),
            binding=scoped.blocks.record(checkpoint.binding),
            origin_call_index=checkpoint.origin_call_index,
            call_index=checkpoint.call_index,
            control_policy=scoped.POLICY,
            frozen_sources=scoped.PINS,
        ),
    )
    arrays = {
        prefix + "/" + name: value
        for prefix, state in (
            ("initial", checkpoint.initial_block_state),
            ("current", checkpoint.block_state),
        )
        for name, value in state._asdict().items()
    }
    with (path / "block-state.npz").open("xb") as handle:
        import os

        np.savez(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    if source_hashes() != sources or runtime_identity("cpu") != runtime:
        raise ConfigError("Source/runtime changed during controlled charged checkpoint publication")
    payload = dict(
        kind=KIND,
        complete=True,
        checkpoint=calls.record(checkpoint),
        source_hashes=sources,
        runtime=runtime,
        files={name: _sha(path / name) for name in sorted(FILES)},
    )
    _write_json(path / "manifest.json", payload | dict(identity=digest(payload)))
    _sync_directory(path)
    _sync_directory(path.parent)
    return path


def load_checkpoint(directory):
    path = Path(directory)
    manifest = read_json(path / "manifest.json")
    if type(manifest) is not dict or set(manifest) != {
        "kind",
        "complete",
        "checkpoint",
        "source_hashes",
        "runtime",
        "files",
        "identity",
    }:
        raise ConfigError("Incomplete controlled charged checkpoint manifest")
    payload = {key: value for key, value in manifest.items() if key != "identity"}
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or manifest["identity"] != digest(payload)
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
        or manifest["source_hashes"] != source_hashes()
        or manifest["runtime"] != runtime_identity("cpu")
    ):
        raise ConfigError("Controlled charged source/runtime/manifest association changed")
    for name, expected in manifest["files"].items():
        if _sha(path / name) != expected:
            raise ConfigError("Controlled charged checkpoint file changed: " + name)
    metadata = read_json(path / "block-context.json")
    if type(metadata) is not dict or set(metadata) != {
        "calendar",
        "binding",
        "origin_call_index",
        "call_index",
        "control_policy",
        "frozen_sources",
    }:
        raise ConfigError("Incomplete source blocker/calendar metadata")
    if metadata["control_policy"] != scoped.POLICY or metadata["frozen_sources"] != scoped.PINS:
        raise ConfigError("Scoped source/control contract changed")
    original = origin_io.load_held_protein_checkpoint(path / "charged/origin")
    spec, origin = original.spec, original.checkpoint
    calendar = scoped.clocks.restore(
        metadata["calendar"], expected_identity=metadata["calendar"]["identity"]
    )
    binding = scoped.blocks.restore(metadata["binding"], spec, origin.binding)
    with np.load(path / "block-state.npz", allow_pickle=False) as archive:
        names = {
            prefix + "/" + name
            for prefix in ("initial", "current")
            for name in scoped.blocks.BlockState._fields
        }
        if set(archive.files) != names or len(archive.files) != len(names):
            raise ConfigError("Incomplete/duplicate carried blocker arrays")
        states = {}
        for prefix in ("initial", "current"):
            state = scoped.blocks.BlockState(
                *(archive[prefix + "/" + name] for name in scoped.blocks.BlockState._fields)
            )
            states[prefix] = scoped.provider._frozen_tree(scoped.blocks._state(state, binding))
    context = scoped.ControlScope(
        spec, origin.binding, binding, states["initial"], calendar, metadata["origin_call_index"]
    )
    charged = context.codec.load_protein_loop_checkpoint(path / "charged")
    checkpoint = calls.ProteinBlockCheckpoint(
        charged.checkpoint,
        binding,
        states["initial"],
        states["current"],
        calendar,
        metadata["origin_call_index"],
        metadata["call_index"],
        manifest["checkpoint"]["identity"],
    )
    calls.validate(spec, checkpoint)
    if calls.record(checkpoint) != manifest["checkpoint"]:
        raise ConfigError("Controlled charged state/ledger/block/calendar association differs")
    return ProteinBlockSnapshot(spec, checkpoint, manifest["identity"])


def write_attempt(directory, *, source, proposal=None, receipt=None, failure=None):
    """Full actual numerical evidence, including nonfinite refused trials."""
    return raw_io.write_raw_evidence(
        directory,
        journal.raw(
            dict(
                source=source,
                proposal=proposal,
                speculative_receipt=receipt,
                failure=failure,
            )
        ),
    )


def advance_checkpoint(source, destination, budget):
    """Explicit caller declaration; publish only after whole-call admission."""
    target = Path(destination)
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    loaded = load_checkpoint(source)
    proposal = calls.propose(loaded.spec, loaded.checkpoint)
    receipt = calls.accept(loaded.spec, loaded.checkpoint, proposal, budget)
    write_checkpoint(target, loaded.spec, receipt.checkpoint)
    return receipt


def replay(spec, source, receipts):
    """Explicit deterministic whole-call replay; restore itself never samples."""
    point = source
    for expected in receipts:
        proposed = calls.propose(spec, point)
        actual = calls.accept(spec, point, proposed, expected.charged_receipt.budget)
        if (
            calls.proposal_record(proposed) != calls.proposal_record(expected.proposal)
            or actual.identity != expected.identity
            or calls.record(actual.checkpoint) != calls.record(expected.checkpoint)
        ):
            raise ValueError("Explicit blocker/ionic/protein/ledger replay differs")
        point = actual.checkpoint
    return point
