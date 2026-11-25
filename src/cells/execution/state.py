"""Array state is separate from biological identity and host scheduling state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

import jax

from cells.definitions.specs import SimulationSpec

if TYPE_CHECKING:  # The record's module imports the models; this one stays light.
    from cells.execution.energy_check import EnergyCheckRecord


class ReactionTransportState(NamedTuple):
    amount: jax.Array  # [species, cell_capacity], fmol
    transferred: jax.Array  # [species, edge_capacity], signed net fmol
    converted: jax.Array  # [cell_capacity], signed net from-species -> to-species fmol


class ReactionTransportLayout(NamedTuple):
    volume: jax.Array
    active: jax.Array
    ids: jax.Array
    contact_ids: jax.Array
    senders: jax.Array
    receivers: jax.Array
    contact_active: jax.Array
    permeability: jax.Array  # [species, edge_capacity]
    forward_rate: jax.Array
    reverse_rate: jax.Array


@dataclass(frozen=True)
class Checkpoint:
    state: Any  # The model's state type (its STATE_TYPE).
    layout: Any  # The layout type that the definition binds.
    time: float
    step_index: int
    event_index: int
    # The step-doubled energy check's run-level record (execution/energy_check.py; FR-18's X2,
    # D224): None unless the definition selects execution.energy_check, so today's checkpoints,
    # their files and their digests are unchanged. Added by the @3 owner at the lead's word (a
    # recorded exception in this file).
    energy_check: EnergyCheckRecord | None = None


def cpu_device() -> jax.Device:
    from cells.execution.devices import execution_device

    return execution_device("cpu")


def initialise(spec: SimulationSpec) -> Checkpoint:
    from cells.execution.devices import execution_device
    from cells.registry.models import get_model

    device = execution_device(spec.execution.backend)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    return Checkpoint(
        jax.device_put(state, device),
        jax.device_put(layout, device),
        0.0,
        0,
        0 if spec.experiment.changes else -1,
    )
