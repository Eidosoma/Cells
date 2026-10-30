"""Durable complete-boundary restart for changing-protein charged loops.

The conditioned ordinary origin stays separate from the evolved state. Loading
rechecks exact source/runtime pins and cumulative balances, not historical RK
stages or budget authorship. Per-loop proposals and budgets belong in run logs.
"""

import os
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from cells import physiology_protein_checkpoint as origin_io
from cells.core import physiology_permeability_schedule as schedules
from cells.core import physiology_protein_loop as loop
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

KIND = "cells.charged_protein_loop_restart@1"
FILES = frozenset(("origin/manifest.json", "components.json", "state.npz"))
SCHEDULED_KIND = "cells.charged_protein_loop_restart@2"


@dataclass(frozen=True, slots=True)
class ProteinLoopSnapshot:
    spec: object
    checkpoint: loop.ProteinLoopCheckpoint
    identity: str


def write_protein_loop_checkpoint(directory, spec, point):
    """Validate the actual endpoint and original cumulative budget before saving."""
    loop.validate(spec, point)
    sources, runtime = source_hashes(), runtime_identity(spec.execution.backend)
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    origin_io.write_held_protein_checkpoint(path / "origin", spec, point.origin)
    files = FILES
    if point.schedule is not None:
        _write_json(path / "schedule.json", schedules.record(point.schedule))
        files = FILES | {"schedule.json"}
    _write_json(
        path / "components.json",
        {
            name: dict(
                stream=streams.stream_record(component.stream),
                state=_component_record(
                    component, point.origin.binding.component, component.stream
                ),
            )
            for name, component in (
                ("initial", point.initial_component),
                ("current", point.component),
            )
        },
    )
    with (path / "state.npz").open("xb") as handle:
        np.savez(handle, **point.state._asdict())
        handle.flush()
        os.fsync(handle.fileno())
    if sources != source_hashes() or runtime != runtime_identity(spec.execution.backend):
        raise ConfigError("Source/runtime changed during charged-loop publication")
    payload = dict(
        kind=KIND if point.schedule is None else SCHEDULED_KIND,
        complete=True,
        checkpoint=loop.checkpoint_record(point),
        files={name: _sha(path / name) for name in sorted(files)},
    )
    _write_json(path / "manifest.json", payload | dict(identity=digest(payload)))
    _sync_directory(path)
    return path


def load_protein_loop_checkpoint(directory):
    """Recheck the sealed aggregate history; never reset anchors or random state."""
    path = Path(directory)
    manifest = read_json(path / "manifest.json")
    if type(manifest) is not dict or set(manifest) != {
        "kind",
        "complete",
        "checkpoint",
        "files",
        "identity",
    }:
        raise ConfigError("Incomplete charged-loop restart manifest")
    payload = {k: v for k, v in manifest.items() if k != "identity"}
    files = FILES | {"schedule.json"} if manifest["kind"] == SCHEDULED_KIND else FILES
    if (
        manifest["kind"] not in (KIND, SCHEDULED_KIND)
        or manifest["complete"] is not True
        or manifest["identity"] != digest(payload)
        or type(manifest["files"]) is not dict
        or set(manifest["files"]) != files
    ):
        raise ConfigError("Invalid charged-loop restart identity or file list")
    for name, expected in manifest["files"].items():
        if _sha(path / name) != expected:
            raise ConfigError("Charged-loop restart payload changed: " + name)
    origin = origin_io.load_held_protein_checkpoint(path / "origin")
    spec, initial = origin.spec, origin.checkpoint
    try:
        records = read_json(path / "components.json")
        if type(records) is not dict or set(records) != {"initial", "current"}:
            raise ValueError("Incomplete original/current component records")
        components = {}
        for name, record in records.items():
            if type(record) is not dict or set(record) != {"stream", "state"}:
                raise ValueError("Incomplete component/RNG record")
            stream = streams.restore_stream(record["stream"], initial.binding.component)
            components[name] = _restore_component(
                record["state"], initial.binding.component, stream
            )
        with np.load(path / "state.npz", allow_pickle=False) as archive:
            names = initial.state._fields
            if set(archive.files) != set(names) or len(archive.files) != len(names):
                raise ValueError("Incomplete/duplicate complete numeric state")
            state = type(initial.state)(*(archive[name] for name in names))
        record = manifest["checkpoint"]
        schedule = None
        if manifest["kind"] == SCHEDULED_KIND:
            schedule = schedules.restore(
                read_json(path / "schedule.json"),
                spec,
                initial.binding,
                components["initial"],
                record["origin_loop_index"],
            )
        base = loop.initialise(
            spec,
            initial.seed,
            initial.binding,
            initial.charge_reference,
            components["initial"],
            protein_species_id=initial.protein_species_id,
            valence=initial.valence,
            standard_concentration_mol_m3=record["standard_concentration_mol_m3"],
            loop_index=record["origin_loop_index"],
            schedule=schedule,
        )
        ledger = record["ledger"]
        if type(ledger) is not dict or set(ledger) != {
            "external_work_pJ",
            "dissipated_free_energy_pJ",
            "clamp_work_pJ",
            "electrode_charge_C",
        }:
            raise ValueError("Incomplete accumulated protein ledger")
        point = replace(
            base,
            state=loop.view._immutable_tree(state),
            component=components["current"],
            time=record["time"],
            step_index=record["step_index"],
            event_index=record["event_index"],
            loop_index=record["loop_index"],
            history_identity=record["history_identity"],
            ledger=loop.ProteinLoopLedger(
                **(ledger | dict(electrode_charge_C=tuple(ledger["electrode_charge_C"])))
            ),
            identity=record["identity"],
        )
        if loop.checkpoint_record(point) != record:
            raise ValueError("Charged-loop source/endpoint/component/ledger association changed")
        loop.validate(spec, point)
        return ProteinLoopSnapshot(spec, point, manifest["identity"])
    except (KeyError, TypeError, ValueError, NumericalError) as error:
        raise ConfigError("Invalid charged-loop restart: " + str(error)) from error
