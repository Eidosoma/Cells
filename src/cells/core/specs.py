"""Strict, model-specific data definitions; no implicit unit conversion."""

from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cells.core.betse_spatial_spec import BetseSpatialModel
    from cells.core.betse_spatial_spec import Experiment as BetseExperiment
    from cells.core.er_spec import ERExperiment, ERModel
    from cells.core.reaction_spec import ReactionExperiment, ReactionNetworkSpec
    from cells.core.surface_tissue_spec import SurfaceExperiment, SurfaceTissueModel

MODEL_ID = "source_decay@1"
UNITS = {"amount": "fmol", "volume": "pL", "time": "s"}
EMT_MODEL_ID = "emt_mirna@1"
EMT_UNITS = {"concentration": "bitsey_scaled_coordinate", "time": "bitsey_time_unit"}
EMT_PARAMETER_SET = "bitsey-b2cb370-mirna-simple"
PAIR_MODEL_ID = "passive_pair@1"
REACTION_TRANSPORT_ID = "reaction_transport@1"
BIOELECTRIC_ID = "bioelectric_cell@1"
BIOELECTRIC_PAIR_ID = "bioelectric_pair@1"
SOURCE_PAIR_ID = "bitsey_emt_pair@1"
MULTISPECIES_ID = "multispecies_membrane@1"
VOLTAGE_GATED_ID = "voltage_gated_membrane@1"
PHYSICAL_IONIC_GRAPH_ID = "physical_ionic_graph@1"
FINITE_EXTRACELLULAR_ID = "finite_extracellular@1"
KINETIC_FINITE_EXTRACELLULAR_ID = "finite_extracellular@2"
JUNCTION_FINITE_EXTRACELLULAR_ID = "finite_extracellular@3"
SPATIAL_EXTRACELLULAR_ID = "spatial_extracellular@1"
SPATIAL_JUNCTION_ID = "spatial_extracellular@2"


class ConfigError(ValueError):
    """A definition cannot be executed without changing its declared meaning."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def read_json(path: str | Path) -> dict:
    def reject_constant(value: str) -> None:
        raise ConfigError(f"Non-finite JSON number: {value}")

    try:
        return json.loads(
            Path(path).read_text(),
            object_pairs_hook=_unique_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON: {exc}") from exc


def _fields(value: Any, expected: set[str], name: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be an object")
    missing, unknown = expected - value.keys(), value.keys() - expected
    if missing or unknown:
        raise ConfigError(f"{name}: missing={sorted(missing)}, unknown={sorted(unknown)}")
    return value


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{name} must be a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ConfigError(f"{name} exceeds float64 range") from exc
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ConfigError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return result


def _integer(value: Any, name: str, *, minimum: int = 1, maximum: int = 2**31 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


@dataclass(frozen=True)
class ModelSpec:
    initial_amount: float
    volume: float
    decay_rate: float
    cell_id: int


@dataclass(frozen=True)
class EMTModelSpec:
    initial_mir200_total: float
    initial_zeb_mrna_total: float
    initial_zeb_protein: float
    snail: float
    cell_id: int


@dataclass(frozen=True)
class PassivePairSpec:
    initial_amounts: tuple[float, float]
    volumes: tuple[float, float]
    cell_ids: tuple[int, int]
    contact_id: int
    from_cell_id: int
    to_cell_id: int
    permeability: float


@dataclass(frozen=True)
class SpeciesContactSpec:
    contact_id: int
    from_cell_id: int
    to_cell_id: int
    permeability: tuple[float, ...]  # In the declared species order; pL/s.


@dataclass(frozen=True)
class ReactionTransportSpec:
    species: tuple[str, str]
    cell_ids: tuple[int, ...]
    initial_amounts: tuple[tuple[float, ...], ...]  # [species, cell]
    volumes: tuple[float, ...]
    from_species: str
    to_species: str
    forward_rate: tuple[float, ...]  # Per-cell 1/s.
    reverse_rate: tuple[float, ...]
    contacts: tuple[SpeciesContactSpec, ...]


@dataclass(frozen=True)
class MembraneSpec:
    membrane_id: int
    owner_cell_id: int
    bath_id: int
    area_m2: float
    specific_capacitance_F_per_m2: float
    permeability_m_per_s: tuple[float, ...]
    pump_capacity_fmol_per_s: float


@dataclass(frozen=True)
class BathSpec:
    bath_id: int
    concentration_mM: tuple[float, ...]
    potential_V: float
    temperature_K: float
    atp_free_energy_J_per_mol: float


@dataclass(frozen=True)
class BioelectricSpec:
    cell_id: int
    initial_amount: tuple[float, ...]
    volume_pL: float
    initial_voltage_V: float
    membrane: MembraneSpec
    bath: BathSpec


@dataclass(frozen=True)
class MultispeciesSpec:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    cell_id: str
    bath_id: str
    membrane_id: str
    volume_pL: float
    area_m2: float
    specific_capacitance_F_per_m2: float
    temperature_K: float
    initial_amount_fmol: tuple[float, ...]
    bath_mM: tuple[float, ...]
    permeability_m_per_s: tuple[float, ...]
    fixed_charge_equivalent_fmol: float
    initial_voltage_V: float
    bath_background_charge_mM: float
    pump_id: str | None
    pump_roles: tuple[str, str] | None
    stoichiometry: tuple[int, ...]
    capacity_fmol_per_s: float
    drive_J_per_mol: float


@dataclass(frozen=True)
class ChannelSpec:
    id: str
    membrane_id: str
    species_id: str
    kinetic_law: str
    max_permeability_m_per_s: float
    abundance: float
    initial_gate: tuple[float, float]  # Explicit activation m and inactivation h.


@dataclass(frozen=True)
class VoltageGatedSpec(MultispeciesSpec):
    channel: ChannelSpec


@dataclass(frozen=True)
class IonicJunctionSpec:
    id: str
    from_cell: str
    to_cell: str
    area_m2: float
    permeability_m_per_s: tuple[float, ...]
    residual_fraction: tuple[float, ...]
    law: str
    sensitivity_per_V: float
    half_voltage_V: float
    tau_s: float
    initial_gate: float


@dataclass(frozen=True)
class RateJunctionSpec:
    id: str
    from_cell: str
    to_cell: str
    area_m2: float
    permeability_m_per_s: tuple[float, ...]
    law: str
    threshold_voltage_V: float
    minimum_open_fraction: float
    initial_gate: float  # Intrinsic conductance, including the minimum opening.


@dataclass(frozen=True)
class PhysicalIonicGraphSpec:
    cells: tuple[MultispeciesSpec, ...]
    channels: tuple[ChannelSpec, ...]
    junctions: tuple[IonicJunctionSpec, ...]

    @property
    def species_ids(self):
        return self.cells[0].species_ids


@dataclass(frozen=True)
class FiniteCompartmentSpec:
    id: str
    volume_pL: float
    initial_amount_fmol: tuple[float, ...]
    fixed_charge_equivalent_fmol: float


@dataclass(frozen=True)
class FiniteMembraneSpec:
    id: str
    inside: str
    outside: str
    area_m2: float
    specific_capacitance_F_per_m2: float
    permeability_m_per_s: tuple[float, ...]
    initial_voltage_V: float
    pump_id: str | None
    pump_roles: tuple[str, str] | None
    stoichiometry: tuple[int, ...]
    capacity_fmol_per_s: float
    drive_J_per_mol: float


@dataclass(frozen=True)
class FiniteExtracellularSpec:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    extracellular: FiniteCompartmentSpec
    cells: tuple[FiniteCompartmentSpec, ...]
    membranes: tuple[FiniteMembraneSpec, ...]
    channels: tuple[ChannelSpec, ...]
    junctions: tuple[IonicJunctionSpec, ...]


@dataclass(frozen=True)
class MaintainedMetabolismSpec:
    kind: str
    atp_mM: float
    adp_mM: float
    pi_mM: float
    delta_g0_J_per_mol: float


@dataclass(frozen=True)
class KineticPumpSpec:
    id: str
    law: str
    roles: tuple[str, str]
    stoichiometry: tuple[int, ...]
    capacity_fmol_per_s: float
    km_na_mM: float
    km_k_mM: float
    km_atp_mM: float
    metabolism: MaintainedMetabolismSpec


@dataclass(frozen=True)
class KineticFiniteMembraneSpec:
    id: str
    inside: str
    outside: str
    area_m2: float
    specific_capacitance_F_per_m2: float
    permeability_m_per_s: tuple[float, ...]
    initial_voltage_V: float
    pump: KineticPumpSpec | None


@dataclass(frozen=True)
class KineticFiniteExtracellularSpec:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    extracellular: FiniteCompartmentSpec
    cells: tuple[FiniteCompartmentSpec, ...]
    membranes: tuple[KineticFiniteMembraneSpec, ...]
    channels: tuple[ChannelSpec, ...]
    junctions: tuple[IonicJunctionSpec, ...]


@dataclass(frozen=True)
class JunctionFiniteExtracellularSpec:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    extracellular: FiniteCompartmentSpec
    cells: tuple[FiniteCompartmentSpec, ...]
    membranes: tuple[KineticFiniteMembraneSpec, ...]
    channels: tuple[ChannelSpec, ...]
    junctions: tuple[RateJunctionSpec, ...]


@dataclass(frozen=True)
class SpatialMembraneSpec:
    id: str
    inside: str
    outside: str
    area_m2: float
    capacitance_F: float
    permeability_m_per_s: tuple[float, ...]
    initial_voltage_V: float


@dataclass(frozen=True)
class ExtracellularFaceSpec:
    id: str
    sender: str
    receiver: str
    area_m2: float
    length_m: float
    diffusivity_m2_per_s: tuple[float, ...]


@dataclass(frozen=True)
class SpatialExtracellularSpec:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple[FiniteCompartmentSpec, ...]
    extracellular: tuple[FiniteCompartmentSpec, ...]
    membranes: tuple[SpatialMembraneSpec, ...]
    faces: tuple[ExtracellularFaceSpec, ...]
    gauge_reference: str


@dataclass(frozen=True)
class SpatialJunctionSpec(JunctionFiniteExtracellularSpec):
    """One local cell cluster coupled to a connected finite extracellular mesh."""

    surroundings: tuple[FiniteCompartmentSpec, ...]
    faces: tuple[ExtracellularFaceSpec, ...]
    gauge_reference: str


@dataclass(frozen=True)
class SelectiveContactSpec:
    contact_id: int
    from_cell_id: int
    to_cell_id: int
    area_m2: float
    permeability_m_per_s: tuple[float, ...]
    residual: tuple[float, ...]
    sensitivity_per_V: float
    half_voltage_V: float
    tau_s: float
    initial_gate: float


@dataclass(frozen=True)
class BioelectricPairSpec:
    cells: tuple[BioelectricSpec, BioelectricSpec]
    contact: SelectiveContactSpec


@dataclass(frozen=True)
class SourceMembraneSpec:
    membrane_id: int
    owner_cell_id: int
    bath_id: int
    diffusion: tuple[float, ...]


@dataclass(frozen=True)
class SourceContactSpec:
    contact_id: int
    from_cell_id: int
    to_cell_id: int
    ion_diffusion: tuple[float, ...]
    mirna_diffusion: float
    gate_profile: str | None
    swap_hemichannels: bool


@dataclass(frozen=True)
class SourcePairSpec:
    cell_ids: tuple[int, int]
    initial_ions: tuple[tuple[float, ...], ...]
    initial_regulation: tuple[tuple[float, ...], ...]
    context: tuple[tuple[float, ...], ...]  # P, Snail, inert ST; not dynamic state.
    membranes: tuple[SourceMembraneSpec, ...]
    bath_id: int
    bath_ions: tuple[float, ...]
    contact: SourceContactSpec


@dataclass(frozen=True)
class InputChange:
    time: float
    rate: float


@dataclass(frozen=True)
class ContactChange:
    time: float
    open_fraction: float


@dataclass(frozen=True)
class GraphContactChange:
    time: float
    open_fractions: tuple[float, ...]  # Normalized to model contact order.


@dataclass(frozen=True)
class LeakChange:
    time: float
    multipliers: tuple[float, ...]  # Na, K, Cl, on the explicitly identified membrane.


@dataclass(frozen=True)
class PumpChange:
    time: float
    multiplier: float


@dataclass(frozen=True)
class MembraneChange:
    time: float
    leak: tuple[float, ...]
    pump: float


@dataclass(frozen=True)
class ChannelChange:
    time: float
    availability: float


@dataclass(frozen=True)
class SpatialChange:
    time: float
    availability: tuple[float, ...]  # Identified membrane order; may be empty.


@dataclass(frozen=True)
class SpatialExperimentSpec:
    end_time: float
    observation_times: tuple[float, ...]
    membranes: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = self.membranes
        times = [[p.time for p in group] for group in groups]
        return tuple(
            SpatialChange(
                time,
                tuple(
                    group[bisect_right(clock, time) - 1].availability
                    for group, clock in zip(groups, times, strict=True)
                ),
            )
            for time in sorted({0.0, *(t for clock in times for t in clock)})
        )


@dataclass(frozen=True)
class VoltageGatedChange(MembraneChange):
    availability: float


@dataclass(frozen=True)
class VoltageGatedExperimentSpec:
    end_time: float
    observation_times: tuple[float, ...]
    leak: tuple[LeakChange, ...]
    pump: tuple[PumpChange, ...]
    channel: tuple[ChannelChange, ...]

    @property
    def changes(self):
        groups = (self.leak, self.pump, self.channel)
        times = [[p.time for p in g] for g in groups]
        result = []
        for time in sorted({t for group in times for t in group}):
            held = [g[bisect_right(t, time) - 1] for g, t in zip(groups, times, strict=True)]
            result.append(
                VoltageGatedChange(
                    time, held[0].multipliers, held[1].multiplier, held[2].availability
                )
            )
        return tuple(result)


@dataclass(frozen=True)
class MembraneSchedule:
    leak: tuple[LeakChange, ...]
    pump: tuple[PumpChange, ...]


@dataclass(frozen=True)
class PhysicalIonicGraphChange:
    time: float
    leak: tuple[tuple[float, ...], ...]  # [membrane, species]
    pump: tuple[float, ...]
    channel: tuple[float, ...]
    junction: tuple[float, ...]


@dataclass(frozen=True)
class PhysicalIonicGraphExperimentSpec:
    end_time: float
    observation_times: tuple[float, ...]
    membranes: tuple[MembraneSchedule, ...]
    channels: tuple[tuple[ChannelChange, ...], ...]
    junctions: tuple[tuple[ContactChange, ...], ...]

    @property
    def changes(self):
        groups = [g for m in self.membranes for g in (m.leak, m.pump)]
        n, k = len(groups), len(self.channels)
        groups += [*self.channels, *self.junctions]
        times = [[p.time for p in g] for g in groups]
        result = []
        for time in sorted({t for group in times for t in group}):
            held = [g[bisect_right(t, time) - 1] for g, t in zip(groups, times, strict=True)]
            result.append(
                PhysicalIonicGraphChange(
                    time,
                    tuple(p.multipliers for p in held[:n:2]),
                    tuple(p.multiplier for p in held[1:n:2]),
                    tuple(p.availability for p in held[n : n + k]),
                    tuple(p.open_fraction for p in held[n + k :]),
                )
            )
        return tuple(result)


@dataclass(frozen=True)
class PairChange:
    time: float
    leak: tuple[tuple[float, ...], ...]  # [membrane, species], resolved host order.
    pump: tuple[float, ...]
    contact: float


@dataclass(frozen=True)
class PairExperimentSpec:
    end_time: float
    observation_times: tuple[float, ...]
    membranes: tuple[MembraneSchedule, ...]
    contact: tuple[ContactChange, ...]

    @property
    def changes(self):
        groups = [g for m in self.membranes for g in (m.leak, m.pump)] + [self.contact]
        times = [[p.time for p in group] for group in groups]
        result = []
        for time in sorted({t for group in times for t in group}):
            held = [g[bisect_right(t, time) - 1] for g, t in zip(groups, times, strict=True)]
            result.append(
                PairChange(
                    time,
                    tuple(p.multipliers for p in held[:-1:2]),
                    tuple(p.multiplier for p in held[1:-1:2]),
                    held[-1].open_fraction,
                )
            )
        return tuple(result)


@dataclass(frozen=True)
class RoutePairChange:
    time: float
    leak: tuple[tuple[float, ...], ...]
    pump: tuple[float, ...]
    contact: tuple[float, ...]  # Independent route multipliers, resolved host order.


@dataclass(frozen=True)
class RoutePairExperimentSpec:
    end_time: float
    observation_times: tuple[float, ...]
    membranes: tuple[MembraneSchedule, ...]
    contacts: tuple[tuple[ContactChange, ...], ...]

    @property
    def changes(self):
        membrane_groups = [g for m in self.membranes for g in (m.leak, m.pump)]
        groups = membrane_groups + list(self.contacts)
        times = [[p.time for p in g] for g in groups]
        result = []
        for time in sorted({t for group in times for t in group}):
            held = [g[bisect_right(t, time) - 1] for g, t in zip(groups, times, strict=True)]
            n = len(membrane_groups)
            result.append(
                RoutePairChange(
                    time,
                    tuple(p.multipliers for p in held[:n:2]),
                    tuple(p.multiplier for p in held[1:n:2]),
                    tuple(p.open_fraction for p in held[n:]),
                )
            )
        return tuple(result)


@dataclass(frozen=True)
class ExperimentSpec:
    end_time: float
    source: tuple[InputChange, ...]
    observation_times: tuple[float, ...]
    contact: tuple[ContactChange, ...] | tuple[GraphContactChange, ...] = ()
    leak: tuple[LeakChange, ...] = ()
    pump: tuple[PumpChange, ...] = ()

    @property
    def changes(self):
        if self.leak or self.pump:
            if self.source or self.contact or not self.leak or not self.pump:
                raise ConfigError("Membrane controls require both independent groups only")
            leak_times, pump_times = [p.time for p in self.leak], [p.time for p in self.pump]
            return tuple(
                MembraneChange(
                    time,
                    self.leak[bisect_right(leak_times, time) - 1].multipliers,
                    self.pump[bisect_right(pump_times, time) - 1].multiplier,
                )
                for time in sorted(set(leak_times + pump_times))
            )
        # Older models each declare one family; neither can accept membrane controls.
        return self.contact or self.source


@dataclass(frozen=True)
class ExecutionSpec:
    dt: float
    capacity: int
    jit: bool
    max_steps: int
    max_trace_bytes: int
    backend: str = "cpu"
    precision: str = "float64"
    solver: str = "rk4"
    edge_capacity: int = 0
    membrane_capacity: int = 0


@dataclass(frozen=True)
class MultispeciesExecutionSpec(ExecutionSpec):
    material_balance_atol_fmol: tuple[float, ...] = ()  # Declared species order.


@dataclass(frozen=True)
class VoltageGatedExecutionSpec(MultispeciesExecutionSpec):
    channel_capacity: int = 0


@dataclass(frozen=True)
class PhysicalIonicGraphExecutionSpec(VoltageGatedExecutionSpec):
    """Distinct graph execution identity; all four capacity axes are explicit."""


@dataclass(frozen=True)
class FiniteExtracellularExecutionSpec(PhysicalIonicGraphExecutionSpec):
    extracellular_capacity: int = 0


@dataclass(frozen=True)
class SpatialExtracellularExecutionSpec(MultispeciesExecutionSpec):
    extracellular_capacity: int = 0
    face_capacity: int = 0
    field_solver: str = "gauged_dense_kirchhoff@1"


@dataclass(frozen=True)
class SpatialJunctionExecutionSpec(FiniteExtracellularExecutionSpec):
    face_capacity: int = 0
    field_solver: str = "gauged_dense_kirchhoff@1"


@dataclass(frozen=True)
class SimulationSpec:
    model: (
        ModelSpec
        | EMTModelSpec
        | PassivePairSpec
        | ReactionTransportSpec
        | BioelectricSpec
        | BioelectricPairSpec
        | SourcePairSpec
        | MultispeciesSpec
        | VoltageGatedSpec
        | PhysicalIonicGraphSpec
        | FiniteExtracellularSpec
        | KineticFiniteExtracellularSpec
        | JunctionFiniteExtracellularSpec
        | SpatialExtracellularSpec
        | SpatialJunctionSpec
        | ReactionNetworkSpec
        | ERModel
        | SurfaceTissueModel
        | BetseSpatialModel
    )
    experiment: (
        ExperimentSpec
        | PairExperimentSpec
        | RoutePairExperimentSpec
        | VoltageGatedExperimentSpec
        | PhysicalIonicGraphExperimentSpec
        | SpatialExperimentSpec
        | ReactionExperiment
        | ERExperiment
        | SurfaceExperiment
        | BetseExperiment
    )
    execution: ExecutionSpec

    def to_dict(self) -> dict:
        m, e, x = self.model, self.experiment, self.execution
        from cells.core.betse_spatial_spec import BetseSpatialModel, to_dict

        if isinstance(m, BetseSpatialModel):
            return to_dict(self)
        from cells.core.surface_calcium_spec import SurfaceCalciumModel, to_dict

        if isinstance(m, SurfaceCalciumModel):
            return to_dict(self)
        from cells.core.surface_kinetic_spec import SurfaceKineticModel, to_dict

        if isinstance(m, SurfaceKineticModel):
            return to_dict(self)
        from cells.core.surface_tissue_spec import SurfaceTissueModel, to_dict

        if isinstance(m, SurfaceTissueModel):
            return to_dict(self)
        from cells.core.tissue_calcium_spec import TissueCalciumModel, to_dict

        if isinstance(m, TissueCalciumModel):
            return to_dict(self)
        from cells.core.tissue_spec import TissueModel, to_dict

        if isinstance(m, TissueModel):
            return to_dict(self)
        from cells.core.ip3_calcium_spec import IP3CalciumModel, to_dict

        if isinstance(m, IP3CalciumModel):
            return to_dict(self)
        from cells.core.gated_calcium_spec import GatedCalciumModel, to_dict

        if isinstance(m, GatedCalciumModel):
            return to_dict(self)
        from cells.core.plasma_calcium_spec import PlasmaModel, to_dict

        if isinstance(m, PlasmaModel):
            return to_dict(self)
        from cells.core.spatial_calcium_spec import CalciumModel, to_dict

        if isinstance(m, CalciumModel):
            return to_dict(self)
        from cells.core.er_spec import ERModel, to_dict

        if isinstance(m, ERModel):
            return to_dict(self)
        from cells.core.reaction_spec import ReactionNetworkSpec, to_dict

        if isinstance(m, ReactionNetworkSpec):
            return to_dict(self)
        if isinstance(m, SpatialJunctionSpec):
            from cells.core.spatial_junction_spec import to_dict

            return to_dict(self)
        if isinstance(m, JunctionFiniteExtracellularSpec):
            from cells.core.junction_finite_spec import to_dict

            return to_dict(self)
        if isinstance(m, KineticFiniteExtracellularSpec):
            from cells.core.kinetic_finite_spec import to_dict

            return to_dict(self)
        if isinstance(m, SpatialExtracellularSpec):
            from cells.core.spatial_extracellular_spec import to_dict

            return to_dict(self)
        if isinstance(m, FiniteExtracellularSpec):
            from cells.core.finite_extracellular_spec import to_dict

            return to_dict(self)
        if isinstance(m, PhysicalIonicGraphSpec):
            from cells.core.physical_ionic_graph_spec import to_dict

            return to_dict(self)
        if isinstance(m, VoltageGatedSpec):
            from cells.core.voltage_gated_spec import to_dict

            return to_dict(self)
        if isinstance(m, MultispeciesSpec):
            from cells.core.multispecies_spec import to_dict

            return to_dict(self)
        if isinstance(x, MultispeciesExecutionSpec):
            raise ConfigError("Multispecies execution settings require their own model identity")
        if isinstance(m, SourcePairSpec):
            from cells.core.source_pair_spec import to_dict

            return to_dict(self)
        if isinstance(m, BioelectricPairSpec):
            from cells.core.bioelectric_pair_spec import to_dict

            return to_dict(self)
        if not isinstance(e, ExperimentSpec):
            raise ConfigError("Experiment type does not match the declared model")
        if isinstance(m, BioelectricSpec):
            from cells.core.bioelectric_spec import to_dict

            return to_dict(self)
        if e.leak or e.pump or x.membrane_capacity != 0:
            raise ConfigError("This model does not support membrane controls or capacity")
        contact_type = GraphContactChange if isinstance(m, ReactionTransportSpec) else ContactChange
        if any(type(p) is not InputChange for p in e.source) or any(
            type(p) is not contact_type for p in e.contact
        ):
            raise ConfigError("Control entries do not match the declared model's control family")
        if isinstance(m, ModelSpec):
            model = {
                "id": MODEL_ID,
                "units": dict(UNITS),
                "population": {"count": 1, "cell_id": m.cell_id},
                "initial_state": {"amount": m.initial_amount, "volume": m.volume},
                "parameters": {"decay_rate": m.decay_rate},
            }
            source = {
                "kind": "prescribed_external_amount_rate",
                "schedule": [{"time": p.time, "rate": p.rate} for p in e.source],
            }
        elif isinstance(m, EMTModelSpec):
            model = {
                "id": EMT_MODEL_ID,
                "units": dict(EMT_UNITS),
                "population": {"count": 1, "cell_id": m.cell_id},
                "initial_state": {
                    "mir200_total": m.initial_mir200_total,
                    "zeb_mrna_total": m.initial_zeb_mrna_total,
                    "zeb_protein": m.initial_zeb_protein,
                },
                "parameters": {"snail": m.snail, "parameter_set": EMT_PARAMETER_SET},
            }
            # Do not silently discard a source supplied through the Python API.
            source = {"kind": "none"}
            if e.source:
                source["schedule"] = [{"time": p.time, "rate": p.rate} for p in e.source]
        elif isinstance(m, PassivePairSpec):
            model = {
                "id": PAIR_MODEL_ID,
                "units": dict(UNITS),
                "population": {"count": 2, "cell_ids": list(m.cell_ids)},
                "initial_state": {"amount": list(m.initial_amounts), "volume": list(m.volumes)},
                "parameters": {
                    "contact": {
                        "contact_id": m.contact_id,
                        "from_cell_id": m.from_cell_id,
                        "to_cell_id": m.to_cell_id,
                        "permeability": m.permeability,
                    },
                },
            }
            source = {"kind": "none"}
            if e.source:
                source["schedule"] = [{"time": p.time, "rate": p.rate} for p in e.source]
        elif isinstance(m, ReactionTransportSpec):
            model = {
                "id": REACTION_TRANSPORT_ID,
                "units": dict(UNITS),
                "species": list(m.species),
                "population": {"count": len(m.cell_ids), "cell_ids": list(m.cell_ids)},
                "initial_state": {
                    "amount": [list(row) for row in m.initial_amounts],
                    "volume": list(m.volumes),
                },
                "parameters": {
                    "reaction": {
                        "from_species": m.from_species,
                        "to_species": m.to_species,
                        "forward_rate": list(m.forward_rate),
                        "reverse_rate": list(m.reverse_rate),
                    },
                    "contacts": [
                        {
                            "contact_id": c.contact_id,
                            "from_cell_id": c.from_cell_id,
                            "to_cell_id": c.to_cell_id,
                            "permeability": list(c.permeability),
                        }
                        for c in m.contacts
                    ],
                },
            }
            source = {"kind": "none"}
            if e.source:
                source["schedule"] = [{"time": p.time, "rate": p.rate} for p in e.source]
        else:
            raise ConfigError(f"Unknown model specification type: {type(m).__name__}")
        if not isinstance(m, (PassivePairSpec, ReactionTransportSpec)) and (
            e.contact or x.edge_capacity != 0
        ):
            raise ConfigError("This model does not support contact controls or edge capacity")
        result = {
            "schema_version": 1,
            "model": model,
            "experiment": {
                "end_time": e.end_time,
                "source": source,
                "observation_times": list(e.observation_times),
            },
            "execution": {
                "backend": x.backend,
                "precision": x.precision,
                "solver": x.solver,
                "dt": x.dt,
                "capacity": x.capacity,
                "jit": x.jit,
                "max_steps": x.max_steps,
                "max_trace_bytes": x.max_trace_bytes,
            },
        }
        if isinstance(m, PassivePairSpec):
            result["experiment"]["contact"] = {
                "kind": "prescribed_open_fraction",
                "schedule": [{"time": p.time, "open_fraction": p.open_fraction} for p in e.contact],
            }
            result["execution"]["edge_capacity"] = x.edge_capacity
        elif isinstance(m, ReactionTransportSpec):
            result["experiment"]["contact"] = {
                "kind": "prescribed_contact_open_fractions",
                "contact_ids": [c.contact_id for c in m.contacts],
                "schedule": [
                    {"time": p.time, "open_fractions": list(p.open_fractions)} for p in e.contact
                ],
            }
            result["execution"]["edge_capacity"] = x.edge_capacity
        return result

    @property
    def fingerprint(self) -> str:
        # Python callers may supply 20 where JSON parsing resolves 20.0. Hash
        # the validated numerical meaning, not that incidental representation.
        return digest(parse_spec(self.to_dict()).to_dict())


def parse_spec(data: dict) -> SimulationSpec:
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    if isinstance(data["model"], dict) and data["model"].get("id") == "betse_spatial_nak_kv1p5@1":
        from cells.core.betse_spatial_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_calcium@1":
        from cells.core.surface_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_tissue@2":
        from cells.core.surface_kinetic_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "resolved_tissue@1":
        from cells.core.surface_tissue_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@5":
        from cells.core.tissue_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_extracellular@3":
        from cells.core.tissue_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@4":
        from cells.core.ip3_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@3":
        from cells.core.gated_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@2":
        from cells.core.plasma_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "spatial_calcium@1":
        from cells.core.spatial_calcium_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "er_calcium@1":
        from cells.core.er_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == "compartment_reactions@1":
        from cells.core.reaction_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == SPATIAL_JUNCTION_ID:
        from cells.core.spatial_junction_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == JUNCTION_FINITE_EXTRACELLULAR_ID
    ):
        from cells.core.junction_finite_spec import parse

        return parse(data)
    if (
        isinstance(data["model"], dict)
        and data["model"].get("id") == KINETIC_FINITE_EXTRACELLULAR_ID
    ):
        from cells.core.kinetic_finite_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == SPATIAL_EXTRACELLULAR_ID:
        from cells.core.spatial_extracellular_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == FINITE_EXTRACELLULAR_ID:
        from cells.core.finite_extracellular_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == PHYSICAL_IONIC_GRAPH_ID:
        from cells.core.physical_ionic_graph_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == VOLTAGE_GATED_ID:
        from cells.core.voltage_gated_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == MULTISPECIES_ID:
        from cells.core.multispecies_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == SOURCE_PAIR_ID:
        from cells.core.source_pair_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == BIOELECTRIC_PAIR_ID:
        from cells.core.bioelectric_pair_spec import parse

        return parse(data)
    if isinstance(data["model"], dict) and data["model"].get("id") == BIOELECTRIC_ID:
        from cells.core.bioelectric_spec import parse

        return parse(data)
    model_fields = {"id", "units", "population", "initial_state", "parameters"}
    if isinstance(data["model"], dict) and data["model"].get("id") == REACTION_TRANSPORT_ID:
        model_fields.add("species")
    model = _fields(data["model"], model_fields, "model")
    if model["id"] not in (MODEL_ID, EMT_MODEL_ID, PAIR_MODEL_ID, REACTION_TRANSPORT_ID):
        raise ConfigError(
            f"Unknown model: {model['id']!r}; "
            f"available: {MODEL_ID}, {EMT_MODEL_ID}, {PAIR_MODEL_ID}, "
            f"{REACTION_TRANSPORT_ID}, {BIOELECTRIC_ID}, {BIOELECTRIC_PAIR_ID}, {SOURCE_PAIR_ID}, "
            f"{MULTISPECIES_ID}, {VOLTAGE_GATED_ID}"
        )
    units = EMT_UNITS if model["id"] == EMT_MODEL_ID else UNITS
    if model["units"] != units:
        raise ConfigError(f"This model requires exactly {units}; no implicit unit conversion")
    is_pair = model["id"] == PAIR_MODEL_ID
    is_graph = model["id"] == REACTION_TRANSPORT_ID
    if not (is_pair or is_graph):
        population = _fields(model["population"], {"count", "cell_id"}, "population")
        if type(population["count"]) is not int or population["count"] != 1:
            raise ConfigError("This model supports exactly one active cell; capacity may be larger")
        cell_id = _integer(population["cell_id"], "cell ID")
    if model["id"] == MODEL_ID:
        initial = _fields(model["initial_state"], {"amount", "volume"}, "initial_state")
        parameters = _fields(model["parameters"], {"decay_rate"}, "parameters")
        m = ModelSpec(
            initial_amount=_number(initial["amount"], "initial amount"),
            volume=_number(initial["volume"], "volume", positive=True),
            decay_rate=_number(parameters["decay_rate"], "decay rate"),
            cell_id=cell_id,
        )
    elif model["id"] == EMT_MODEL_ID:
        initial = _fields(
            model["initial_state"],
            {"mir200_total", "zeb_mrna_total", "zeb_protein"},
            "initial_state",
        )
        parameters = _fields(model["parameters"], {"snail", "parameter_set"}, "parameters")
        if parameters["parameter_set"] != EMT_PARAMETER_SET:
            raise ConfigError(f"EMT requires parameter_set={EMT_PARAMETER_SET!r}")
        m = EMTModelSpec(
            initial_mir200_total=_number(initial["mir200_total"], "initial miR200 total"),
            initial_zeb_mrna_total=_number(initial["zeb_mrna_total"], "initial Zeb mRNA total"),
            initial_zeb_protein=_number(initial["zeb_protein"], "initial ZEB protein"),
            snail=_number(parameters["snail"], "fixed Snail input"),
            cell_id=cell_id,
        )
    elif is_pair:
        m = _parse_pair(model)
    else:
        m = _parse_reaction_transport(model)
    experiment_fields = {"end_time", "source", "observation_times"}
    if is_pair or is_graph:
        experiment_fields.add("contact")
    experiment = _fields(data["experiment"], experiment_fields, "experiment")
    end_time = _number(experiment["end_time"], "end time", positive=True)
    changes = []
    if isinstance(m, ModelSpec):
        source = _fields(experiment["source"], {"kind", "schedule"}, "source")
        if source["kind"] != "prescribed_external_amount_rate":
            raise ConfigError(
                "Unsupported source kind; external supply must be explicitly declared"
            )
        if not isinstance(source["schedule"], list) or not source["schedule"]:
            raise ConfigError("source schedule must be a nonempty list")
        for item in source["schedule"]:
            _fields(item, {"time", "rate"}, "source change")
            change = InputChange(
                _number(item["time"], "source time"), _number(item["rate"], "rate")
            )
            if change.time > end_time or (changes and change.time <= changes[-1].time):
                raise ConfigError("source times must be strictly increasing and within the horizon")
            changes.append(change)
        if changes[0].time != 0:
            raise ConfigError("source schedule must explicitly start at time 0")
    else:
        source = _fields(experiment["source"], {"kind"}, "source")
        if source["kind"] != "none":
            raise ConfigError("This model requires source.kind='none'")
    contact_changes = []
    if is_pair:
        control = _fields(experiment["contact"], {"kind", "schedule"}, "contact control")
        if control["kind"] != "prescribed_open_fraction":
            raise ConfigError("Contact control must declare kind='prescribed_open_fraction'")
        if not isinstance(control["schedule"], list) or not control["schedule"]:
            raise ConfigError("Contact schedule must be a nonempty list")
        for item in control["schedule"]:
            _fields(item, {"time", "open_fraction"}, "contact change")
            change = ContactChange(
                _number(item["time"], "contact time"),
                _number(item["open_fraction"], "contact open fraction"),
            )
            if change.open_fraction > 1:
                raise ConfigError("Contact open fraction must be in [0, 1]")
            if change.time > end_time or (
                contact_changes and change.time <= contact_changes[-1].time
            ):
                raise ConfigError(
                    "Contact times must be strictly increasing and within the horizon"
                )
            contact_changes.append(change)
        if contact_changes[0].time != 0:
            raise ConfigError("Contact schedule must explicitly start at time 0")
    elif is_graph:
        contact_changes = _parse_graph_control(experiment["contact"], m, end_time)
    observations = experiment["observation_times"]
    if not isinstance(observations, list) or not observations:
        raise ConfigError("observation_times must be a nonempty list")
    times = tuple(_number(t, "observation time") for t in observations)
    if any(t > end_time for t in times) or any(
        b <= a for a, b in zip(times, times[1:], strict=False)
    ):
        raise ConfigError("observation times must be strictly increasing and within the horizon")
    execution_fields = {
        "backend",
        "precision",
        "solver",
        "dt",
        "capacity",
        "jit",
        "max_steps",
        "max_trace_bytes",
    }
    if is_pair or is_graph:
        execution_fields.add("edge_capacity")
    execution = _fields(data["execution"], execution_fields, "execution")
    for name, required in {"backend": "cpu", "precision": "float64", "solver": "rk4"}.items():
        if execution[name] != required:
            raise ConfigError(
                f"This version requires {name}={required!r}; requested {execution[name]!r}"
            )
    if type(execution["jit"]) is not bool:
        raise ConfigError("jit must be a boolean")
    x = ExecutionSpec(
        dt=_number(execution["dt"], "dt", positive=True),
        capacity=_integer(execution["capacity"], "capacity"),
        jit=execution["jit"],
        max_steps=_integer(execution["max_steps"], "max_steps"),
        max_trace_bytes=_integer(
            execution["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1
        ),
        edge_capacity=(
            _integer(execution["edge_capacity"], "edge capacity", minimum=0 if is_graph else 1)
            if is_pair or is_graph
            else 0
        ),
    )
    if is_pair and x.capacity < 2:
        raise ConfigError("Passive pair requires capacity >= 2")
    if is_graph and (x.capacity < len(m.cell_ids) or x.edge_capacity < len(m.contacts)):
        raise ConfigError("Cell/edge capacities must fit all declared cells and contacts")
    return SimulationSpec(
        m, ExperimentSpec(end_time, tuple(changes), times, tuple(contact_changes)), x
    )


def _parse_pair(model: dict) -> PassivePairSpec:
    population = _fields(model["population"], {"count", "cell_ids"}, "population")
    if type(population["count"]) is not int or population["count"] != 2:
        raise ConfigError("Passive pair supports exactly two active cells")

    def two_values(value, name, convert):
        if not isinstance(value, list) or len(value) != 2:
            raise ConfigError(f"{name} must list exactly two values, in cell slot order")
        return tuple(convert(v, name) for v in value)

    ids = two_values(population["cell_ids"], "cell IDs", _integer)
    if len(set(ids)) != 2:
        raise ConfigError("Cell IDs must be distinct")
    initial = _fields(model["initial_state"], {"amount", "volume"}, "initial_state")
    amounts = two_values(initial["amount"], "initial amounts", _number)
    volumes = two_values(initial["volume"], "volumes", lambda v, n: _number(v, n, positive=True))
    if not math.isfinite(sum(amounts)) or not math.isfinite(sum(volumes)):
        raise ConfigError("Combined pair amount and volume must fit finite float64")
    parameters = _fields(model["parameters"], {"contact"}, "parameters")
    contact = _fields(
        parameters["contact"],
        {"contact_id", "from_cell_id", "to_cell_id", "permeability"},
        "contact",
    )
    contact_id = _integer(contact["contact_id"], "contact ID")
    sender = _integer(contact["from_cell_id"], "contact from-cell ID")
    receiver = _integer(contact["to_cell_id"], "contact to-cell ID")
    if sender == receiver or set((sender, receiver)) != set(ids):
        raise ConfigError("Contact must connect the two declared, distinct cell IDs")
    return PassivePairSpec(
        amounts,
        volumes,
        ids,
        contact_id,
        sender,
        receiver,
        _number(contact["permeability"], "contact permeability"),
    )


def _vector(value, size, name, convert=_number):
    if not isinstance(value, list) or len(value) != size:
        raise ConfigError(f"{name} must be a list of length {size}")
    return tuple(convert(v, name) for v in value)


def _parse_reaction_transport(model):
    species = model["species"]
    if (
        not isinstance(species, list)
        or len(species) != 2
        or any(not isinstance(s, str) or not s.isascii() or not s.isidentifier() for s in species)
        or len(set(species)) != 2
    ):
        raise ConfigError("Reversible conversion requires two distinct ASCII species identifiers")
    population = _fields(model["population"], {"count", "cell_ids"}, "population")
    count = _integer(population["count"], "cell count")
    ids = _vector(population["cell_ids"], count, "cell IDs", _integer)
    if len(set(ids)) != count:
        raise ConfigError("Cell IDs must be distinct")
    initial = _fields(model["initial_state"], {"amount", "volume"}, "initial_state")
    amounts = _vector(initial["amount"], 2, "species amounts", lambda v, n: _vector(v, count, n))
    volumes = _vector(
        initial["volume"], count, "volumes", lambda v, n: _number(v, n, positive=True)
    )
    if not math.isfinite(sum(sum(row) for row in amounts)) or not math.isfinite(sum(volumes)):
        raise ConfigError("Total graph amount and volume must fit finite float64")
    parameters = _fields(model["parameters"], {"reaction", "contacts"}, "parameters")
    reaction = _fields(
        parameters["reaction"],
        {"from_species", "to_species", "forward_rate", "reverse_rate"},
        "reaction",
    )
    first, second = reaction["from_species"], reaction["to_species"]
    if first not in species or second not in species or first == second:
        raise ConfigError("Reaction must connect the two distinct declared species")
    forward = _vector(reaction["forward_rate"], count, "forward rates")
    reverse = _vector(reaction["reverse_rate"], count, "reverse rates")
    if not isinstance(parameters["contacts"], list):
        raise ConfigError("contacts must be a list; use [] for a contact-free world")
    contacts, seen = [], set()
    id_set = set(ids)
    for entry in parameters["contacts"]:
        c = _fields(entry, {"contact_id", "from_cell_id", "to_cell_id", "permeability"}, "contact")
        identity = _integer(c["contact_id"], "contact ID")
        sender = _integer(c["from_cell_id"], "contact from-cell ID")
        receiver = _integer(c["to_cell_id"], "contact to-cell ID")
        if identity in seen:
            raise ConfigError("Contact IDs must be distinct")
        if sender == receiver or sender not in id_set or receiver not in id_set:
            raise ConfigError("Contact endpoints must be distinct declared cell IDs")
        seen.add(identity)
        contacts.append(
            SpeciesContactSpec(
                identity, sender, receiver, _vector(c["permeability"], 2, "species permeabilities")
            )
        )
    return ReactionTransportSpec(
        tuple(species), ids, amounts, volumes, first, second, forward, reverse, tuple(contacts)
    )


def _parse_graph_control(value, model, end_time):
    control = _fields(value, {"kind", "contact_ids", "schedule"}, "graph contact control")
    if control["kind"] != "prescribed_contact_open_fractions":
        raise ConfigError("Graph control requires kind='prescribed_contact_open_fractions'")
    ids = _vector(control["contact_ids"], len(model.contacts), "control contact IDs", _integer)
    expected = tuple(c.contact_id for c in model.contacts)
    if len(set(ids)) != len(ids) or set(ids) != set(expected):
        raise ConfigError("Control contact IDs must identify every physical contact exactly once")
    slots = {identity: slot for slot, identity in enumerate(ids)}
    order = [slots[identity] for identity in expected]
    if not isinstance(control["schedule"], list) or not control["schedule"]:
        raise ConfigError("Graph contact schedule must be a nonempty list")
    changes = []
    for item in control["schedule"]:
        _fields(item, {"time", "open_fractions"}, "graph contact change")
        time = _number(item["time"], "contact time")
        fractions = _vector(item["open_fractions"], len(ids), "contact open fractions")
        if any(v > 1 for v in fractions):
            raise ConfigError("Contact open fractions must be in [0, 1]")
        if time > end_time or (changes and time <= changes[-1].time):
            raise ConfigError("Contact times must be strictly increasing and within the horizon")
        changes.append(GraphContactChange(time, tuple(fractions[index] for index in order)))
    if changes[0].time != 0:
        raise ConfigError("Graph contact schedule must explicitly start at time 0")
    return changes


def load_spec(path: str | Path) -> SimulationSpec:
    return parse_spec(read_json(path))
