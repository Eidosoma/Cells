"""Array state is separate from biological identity and host scheduling state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

import jax
import numpy as np

from cells.core.specs import SimulationSpec


class CellState(NamedTuple):
    amount: jax.Array
    supplied: jax.Array
    degraded: jax.Array


class EMTState(NamedTuple):
    mir200_total: jax.Array
    zeb_mrna_total: jax.Array
    zeb_protein: jax.Array


class ExchangeState(NamedTuple):
    amount: jax.Array  # [cell_capacity], fmol
    transferred: jax.Array  # [edge_capacity], signed net fmol from sender to receiver


class ReactionTransportState(NamedTuple):
    amount: jax.Array  # [species, cell_capacity], fmol
    transferred: jax.Array  # [species, edge_capacity], signed net fmol
    converted: jax.Array  # [cell_capacity], signed net from-species -> to-species fmol


class BioelectricState(NamedTuple):
    amount: jax.Array  # [species, cell_capacity], fmol
    leak_transferred: jax.Array  # [species, membrane_capacity], signed inward fmol
    pump_cycles: jax.Array  # [membrane_capacity], signed forward fmol cycles


class MultispeciesState(NamedTuple):
    amount: jax.Array  # [species, cell_capacity]; sole mobile charge inventory.
    leak_transferred: jax.Array  # [species, membrane_capacity], signed inward fmol.
    pump_cycles: jax.Array  # [membrane_capacity], signed forward fmol cycles.
    dissipated_energy_pJ: jax.Array  # [membrane_capacity], diagnostic integral.


class MultispeciesLayout(NamedTuple):
    volume: jax.Array
    active: jax.Array
    ids: jax.Array  # Local positive label codes; labels live in the resolved spec.
    species_codes: jax.Array
    valence: jax.Array  # [species, 1], integer chemical property, not a selector.
    stoichiometry: jax.Array  # [species, 1], ID-resolved inward pump coefficients.
    amount_reference: jax.Array
    voltage_reference: jax.Array
    fixed_charge_equivalent: jax.Array
    membrane_ids: jax.Array
    membrane_active: jax.Array
    owners: jax.Array
    membrane_baths: jax.Array
    area: jax.Array
    specific_capacitance: jax.Array
    capacitance: jax.Array
    permeability: jax.Array
    pump_capacity: jax.Array
    pump_drive: jax.Array
    bath_ids: jax.Array
    bath_concentration: jax.Array
    bath_background_charge: jax.Array
    temperature: jax.Array


class VoltageGatedState(NamedTuple):
    amount: jax.Array
    leak_transferred: jax.Array
    pump_cycles: jax.Array
    dissipated_energy_pJ: jax.Array
    gate: jax.Array  # [gate (m,h), channel_capacity]
    channel_transferred: jax.Array  # [channel_capacity], signed inward fmol.


VoltageGatedLayout = NamedTuple(
    "VoltageGatedLayout",
    [
        (name, jax.Array)
        for name in MultispeciesLayout._fields
        + (
            "channel_ids",
            "channel_active",
            "channel_membranes",
            "channel_species",
            "channel_laws",
            "channel_permeability",
            "channel_abundance",
        )
    ],
)


PhysicalIonicGraphState = NamedTuple(
    "PhysicalIonicGraphState",
    [(name, Any) for name in VoltageGatedState._fields]
    + [
        ("junction_gate", Any),
        ("junction_transferred", Any),
        ("junction_dissipated_energy_pJ", Any),
    ],
)

PhysicalIonicGraphLayout = NamedTuple(
    "PhysicalIonicGraphLayout",
    [(name, Any) for name in VoltageGatedLayout._fields]
    + [
        ("cell_membranes", Any),
        ("junction_ids", Any),
        ("junction_active", Any),
        ("senders", Any),
        ("receivers", Any),
        ("junction_area", Any),
        ("junction_permeability", Any),
        ("junction_residual", Any),
        ("junction_sensitivity", Any),
        ("junction_half_voltage", Any),
        ("junction_tau", Any),
    ],
)


FiniteExtracellularState = NamedTuple(
    "FiniteExtracellularState",
    [("amount_increment", Any)]
    + [(name, Any) for name in PhysicalIonicGraphState._fields[1:]]
    + [("extracellular_amount_increment", Any)],
)

# No maintained-bath alias: a membrane gathers from an owned finite inventory.
FiniteExtracellularLayout = NamedTuple(
    "FiniteExtracellularLayout",
    [
        (name, Any)
        for name in PhysicalIonicGraphLayout._fields
        if name
        not in ("membrane_baths", "bath_ids", "bath_concentration", "bath_background_charge")
    ]
    + [
        ("outside_owners", Any),
        ("extracellular_ids", Any),
        ("extracellular_active", Any),
        ("extracellular_volume", Any),
        ("extracellular_amount_reference", Any),
        ("extracellular_fixed_charge_equivalent", Any),
        ("initial_countercharge_C", Any),
    ],
)


KineticFiniteExtracellularLayout = NamedTuple(
    "KineticFiniteExtracellularLayout",
    [(name, Any) for name in FiniteExtracellularLayout._fields]
    + [
        (name, Any)
        for name in (
            "pump_present",
            "pump_sodium_species",
            "pump_potassium_species",
            "pump_atp_mM",
            "pump_adp_mM",
            "pump_pi_mM",
            "pump_km_na_mM",
            "pump_km_k_mM",
            "pump_km_atp_mM",
            "pump_delta_g0_J_mol",
        )
    ],
)


JunctionFiniteExtracellularLayout = NamedTuple(
    "JunctionFiniteExtracellularLayout",
    [
        (name, Any)
        for name in KineticFiniteExtracellularLayout._fields
        if name
        not in (
            "junction_residual",
            "junction_sensitivity",
            "junction_half_voltage",
            "junction_tau",
        )
    ]
    + [("junction_threshold_voltage", Any), ("junction_minimum", Any)],
)


class BioelectricLayout(NamedTuple):
    volume: jax.Array
    active: jax.Array
    ids: jax.Array
    amount_reference: jax.Array
    voltage_reference: jax.Array
    fixed_charge: jax.Array
    membrane_ids: jax.Array
    membrane_active: jax.Array
    owners: jax.Array
    membrane_baths: jax.Array
    area: jax.Array
    specific_capacitance: jax.Array
    capacitance: jax.Array
    permeability: jax.Array
    pump_capacity: jax.Array
    bath_ids: jax.Array
    bath_concentration: jax.Array
    bath_potential: jax.Array
    temperature: jax.Array
    atp_free_energy: jax.Array


class BioelectricPairState(NamedTuple):
    amount: jax.Array  # [species, cell_capacity], fmol; sole ionic charge owner.
    leak_transferred: jax.Array  # [species, membrane_capacity], signed inward fmol.
    pump_cycles: jax.Array  # [membrane_capacity], signed forward fmol cycles.
    transferred: jax.Array  # [species, edge_capacity], signed from -> to fmol.
    gate: jax.Array  # [edge_capacity], explicit evolving fraction.
    dissipated_energy_pJ: jax.Array  # [leak, pump, junction], diagnostic integrals only.


class SourcePairState(NamedTuple):
    ions: jax.Array  # [ion, cell], source numerical mol/m3.
    regulation: jax.Array  # [regulatory coordinate, cell], nominal coordinates.
    leak_history: jax.Array  # [ion, membrane], inward concentration-equivalent.
    pump_history: jax.Array  # [membrane], signed cycles, concentration-equivalent.
    ion_transferred: jax.Array  # [ion, edge], oriented concentration-equivalent.
    local_regulation: jax.Array  # [regulatory coordinate, cell], nominal history.
    mirna_transferred: jax.Array  # [edge], oriented nominal regulatory history.


class SourcePairLayout(NamedTuple):
    active: jax.Array
    ids: jax.Array
    ion_reference: jax.Array
    regulatory_reference: jax.Array
    context: jax.Array  # Fixed P, Snail and inert ST, with distinct coordinate roles.
    volume: jax.Array
    membrane_ids: jax.Array
    membrane_active: jax.Array
    owners: jax.Array
    membrane_baths: jax.Array
    area: jax.Array
    membrane_diffusion: jax.Array
    bath_ids: jax.Array
    bath_ions: jax.Array
    contact_ids: jax.Array
    contact_active: jax.Array
    senders: jax.Array
    receivers: jax.Array
    ion_diffusion: jax.Array
    mirna_diffusion: jax.Array
    gate_enabled: jax.Array
    gate_parameters: jax.Array


# Flat, named arrays remain portable in NPZ/checkpoints. Reuse the exact membrane
# layout contract, adding independent edge capacity and a cell -> membrane map.
BioelectricPairLayout = NamedTuple(
    "BioelectricPairLayout",
    [
        (name, jax.Array)
        for name in BioelectricLayout._fields
        + (
            "cell_membranes",
            "contact_ids",
            "contact_active",
            "senders",
            "receivers",
            "contact_area",
            "contact_permeability",
            "residual",
            "gate_sensitivity",
            "gate_half_voltage",
            "gate_tau",
        )
    ],
)


class CellLayout(NamedTuple):
    volume: jax.Array
    active: jax.Array
    ids: jax.Array


class RegulatoryLayout(NamedTuple):
    active: jax.Array
    ids: jax.Array


class ExchangeLayout(NamedTuple):
    volume: jax.Array
    active: jax.Array
    ids: jax.Array
    contact_ids: jax.Array
    senders: jax.Array
    receivers: jax.Array
    contact_active: jax.Array
    permeability: jax.Array


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


class SpatialExtracellularState(NamedTuple):
    amount_increment: jax.Array  # [species, cell], fmol from immutable anchors.
    extracellular_amount_increment: jax.Array  # [species, outside], fmol.
    membrane_transferred: jax.Array  # [species, membrane], outward fmol.
    face_transferred: jax.Array  # [species, face], sender -> receiver fmol.
    membrane_dissipated_energy_pJ: jax.Array  # [membrane], diagnostic only.
    face_dissipated_energy_pJ: jax.Array  # [face], diagnostic only.


SpatialExtracellularLayout = NamedTuple(
    "SpatialExtracellularLayout",
    [
        (name, jax.Array)
        for name in (
            "active",
            "ids",
            "volume",
            "amount_reference",
            "fixed_charge_equivalent",
            "species_codes",
            "valence",
            "temperature",
            "voltage_reference",
            "initial_inside_charge_C",
            "initial_outside_charge_C",
            "extracellular_active",
            "extracellular_ids",
            "extracellular_volume",
            "extracellular_amount_reference",
            "extracellular_fixed_charge_equivalent",
            "membrane_active",
            "membrane_ids",
            "owners",
            "outside_owners",
            "cell_membranes",
            "area",
            "capacitance",
            "permeability",
            "face_active",
            "face_ids",
            "senders",
            "receivers",
            "face_area",
            "face_length",
            "face_diffusivity",
            "face_factor",
            "gauge_mask",
        )
    ],
)


SpatialJunctionState = NamedTuple(
    "SpatialJunctionState",
    [(name, Any) for name in FiniteExtracellularState._fields]
    + [("face_transferred", Any), ("face_dissipated_energy_pJ", Any)],
)

SpatialJunctionLayout = NamedTuple(
    "SpatialJunctionLayout",
    [(name, Any) for name in JunctionFiniteExtracellularLayout._fields]
    + [
        (name, Any)
        for name in (
            "face_active",
            "face_ids",
            "face_senders",
            "face_receivers",
            "face_factor",
            "gauge_mask",
            "initial_inside_charge_C",
            "initial_outside_charge_C",
        )
    ],
)


@dataclass(frozen=True)
class Checkpoint:
    state: (
        CellState
        | EMTState
        | ExchangeState
        | ReactionTransportState
        | BioelectricState
        | BioelectricPairState
        | SourcePairState
        | MultispeciesState
        | VoltageGatedState
        | PhysicalIonicGraphState
        | FiniteExtracellularState
        | SpatialExtracellularState
    )
    layout: (
        CellLayout
        | RegulatoryLayout
        | ExchangeLayout
        | ReactionTransportLayout
        | BioelectricLayout
        | BioelectricPairLayout
        | SourcePairLayout
        | MultispeciesLayout
        | VoltageGatedLayout
        | PhysicalIonicGraphLayout
        | FiniteExtracellularLayout
        | SpatialExtracellularLayout
    )
    time: float
    step_index: int
    event_index: int


def cpu_device() -> jax.Device:
    from cells.core.devices import execution_device

    return execution_device("cpu")


def initialise(spec: SimulationSpec) -> Checkpoint:
    from cells.core.devices import execution_device
    from cells.models.registry import get_model

    device = execution_device(spec.execution.backend)
    state, layout = get_model(spec.model).initial_values(spec)
    return Checkpoint(
        jax.device_put(state, device),
        jax.device_put(layout, device),
        0.0,
        0,
        0 if spec.experiment.changes else -1,
    )


def identity_arrays(spec: SimulationSpec) -> tuple[np.ndarray, np.ndarray]:
    size = spec.execution.capacity
    active = np.zeros(size, dtype=bool)
    active[0] = True
    ids = np.full(size, -1, dtype=np.int64)
    ids[0] = spec.model.cell_id
    return active, ids
