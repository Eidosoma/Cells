"""Durable, replay-checked receipts for one post-ion split operator.

This saves an accepted held-protein source and a declared-drive receipt. Loading
replays the proposal from the saved source RNG without advancing any external
state, then checks exact full proposal identity. It does not produce a new
ordinary/held numeric checkpoint or claim subsequent-loop continuation.
"""

from dataclasses import dataclass
from pathlib import Path

from cells import physiology_protein_checkpoint as held_io
from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_protein_transition as transition
from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, digest, read_json
from cells.io import runtime_identity, source_hashes
from cells.physiology_checkpoint import (
    _component_record,
    _restore_component,
    _sha,
    _sync_directory,
    _write_json,
)

KIND = "cells.post_ion_protein_receipt@1"
FILES = frozenset(("source/manifest.json", "preparation.json", "receipt.json"))


@dataclass(frozen=True, slots=True)
class SavedProteinTransition:
    spec: object
    receipt: transition.ProteinTransitionReceipt
    identity: str


def _receipt_record(receipt):
    return dict(
        proposal_identity=receipt.proposal.identity,
        loop_index=receipt.proposal.loop_index,
        standard_concentration_mol_m3=receipt.proposal.standard_concentration_mol_m3,
        budget=transition._record(receipt.budget),
        balance_residual_pJ=receipt.balance_residual_pJ,
        balance_limit_pJ=receipt.balance_limit_pJ,
        receipt_identity=receipt.identity,
    )


def write_protein_transition(directory, spec, receipt):
    """Publish only a newly validated receipt, committing the manifest last."""
    if type(receipt) is not transition.ProteinTransitionReceipt:
        raise ValueError("Require an accepted post-ion receipt")
    checked = transition.accept(spec, receipt.proposal, receipt.budget)
    if transition._record(checked) != transition._record(receipt):
        raise ValueError("Post-ion receipt differs from its physical/budget admission")
    sources, runtime = source_hashes(), runtime_identity(spec.execution.backend)
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    point = receipt.proposal.source
    held_io.write_held_protein_checkpoint(path / "source", spec, point)
    preparation = receipt.proposal.preparation
    component = preparation.source_state
    _write_json(
        path / "preparation.json",
        dict(
            stream=streams.stream_record(component.stream),
            component=_component_record(component, point.binding.component, component.stream),
            preparation_identity=preparation.identity,
        ),
    )
    _write_json(path / "receipt.json", _receipt_record(receipt))
    if source_hashes() != sources or runtime_identity(spec.execution.backend) != runtime:
        raise ConfigError("Source/runtime changed during post-ion receipt publication")
    payload = dict(
        kind=KIND,
        complete=True,
        files={name: _sha(path / name) for name in sorted(FILES)},
        receipt_identity=receipt.identity,
    )
    _write_json(path / "manifest.json", payload | dict(identity=digest(payload)))
    _sync_directory(path)
    return path


def load_protein_transition(directory):
    """Reproduce the saved proposal/RNG and validate the declared energy budget."""
    path = Path(directory)
    manifest = read_json(path / "manifest.json")
    keys = {"kind", "complete", "files", "receipt_identity", "identity"}
    if type(manifest) is not dict or set(manifest) != keys:
        raise ConfigError("Incomplete post-ion receipt manifest")
    if (
        manifest["kind"] != KIND
        or manifest["complete"] is not True
        or manifest["identity"] != digest({k: v for k, v in manifest.items() if k != "identity"})
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != FILES
    ):
        raise ConfigError("Invalid post-ion receipt identity or payload list")
    for name, expected in manifest["files"].items():
        if _sha(path / name) != expected:
            raise ConfigError("Post-ion receipt payload changed: " + name)
    saved = held_io.load_held_protein_checkpoint(path / "source")
    spec, point = saved.spec, saved.checkpoint
    try:
        record = read_json(path / "preparation.json")
        if set(record) != {"stream", "component", "preparation_identity"}:
            raise ValueError("Incomplete pre-ion preparation source")
        stream = streams.restore_stream(record["stream"], point.binding.component)
        component = _restore_component(record["component"], point.binding.component, stream)
        preparation = phases.prepare(component, point.binding.component)
        if preparation.identity != record["preparation_identity"]:
            raise ValueError("Saved preparation does not match its complete source")
        record = read_json(path / "receipt.json")
        proposal = transition.propose(
            spec,
            point,
            preparation,
            loop_index=record["loop_index"],
            standard_concentration_mol_m3=record["standard_concentration_mol_m3"],
        )
        receipt = transition.accept(spec, proposal, transition.DrivingBudget(**record["budget"]))
        if _receipt_record(receipt) != record or receipt.identity != manifest["receipt_identity"]:
            raise ValueError("Receipt differs from exact source/packet/work replay")
        return SavedProteinTransition(spec, receipt, manifest["identity"])
    except (KeyError, TypeError, ValueError, NumericalError) as error:
        raise ConfigError("Invalid post-ion receipt: " + str(error)) from error
