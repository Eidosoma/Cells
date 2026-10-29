"""Host-side, right-continuous experiment controls; never physical fluxes."""

from bisect import bisect_right
from typing import NamedTuple

import numpy as np

from cells.core.betse_junction_spec import BetseJunctionModel
from cells.core.betse_junction_spec import Control as BetseJunctionControl
from cells.core.betse_spatial_spec import BetseSpatialModel
from cells.core.betse_spatial_spec import Control as BetseSpatialControl
from cells.core.er_spec import ERChange
from cells.core.gated_calcium_spec import GatedCalciumChange
from cells.core.gated_calcium_spec import base_spec as plasma_spec
from cells.core.plasma_calcium_spec import PlasmaChange
from cells.core.reaction_spec import ReactionChange
from cells.core.spatial_calcium_spec import CalciumChange, ionic_spec, store_spec
from cells.core.specs import (
    ContactChange,
    GraphContactChange,
    MembraneChange,
    PairChange,
    PhysicalIonicGraphChange,
    RoutePairChange,
    SpatialChange,
    VoltageGatedChange,
)
from cells.core.surface_calcium_energy_mitochondria_spec import (
    SurfaceCalciumEnergyMitochondriaModel,
)
from cells.core.surface_calcium_energy_spec import (
    Control as SurfaceCalciumEnergyControl,
)
from cells.core.surface_calcium_energy_spec import (
    SurfaceCalciumEnergyModel,
)
from cells.core.surface_calcium_energy_spec import (
    initial_prior_spec as calcium_energy_prior,
)
from cells.core.surface_calcium_energy_transport_spec import (
    SurfaceCalciumEnergyTransportModel,
)
from cells.core.surface_calcium_energy_water_hcn_extra_spec import (
    Control as JointHCNWaterControl,
)
from cells.core.surface_calcium_energy_water_hcn_extra_spec import (
    SurfaceCalciumEnergyWaterHCNExtraModel,
)
from cells.core.surface_calcium_energy_water_hcn_extra_spec import (
    energy_spec as joint_hcn_water_prior,
)
from cells.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
    Control as JointHCNRepairControl,
)
from cells.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
    SurfaceCalciumEnergyWaterRepairHCNExtraModel,
)
from cells.core.surface_calcium_energy_water_repair_hcn_extra_spec import (
    base_spec as joint_hcn_repair_prior,
)
from cells.core.surface_calcium_energy_water_repair_spec import Control as JointRepairControl
from cells.core.surface_calcium_energy_water_repair_spec import SurfaceCalciumEnergyWaterRepairModel
from cells.core.surface_calcium_energy_water_repair_spec import base_spec as joint_repair_prior
from cells.core.surface_calcium_energy_water_spec import Control as SurfaceCalciumEnergyWaterControl
from cells.core.surface_calcium_energy_water_spec import SurfaceCalciumEnergyWaterModel
from cells.core.surface_calcium_energy_water_spec import energy_spec as calcium_energy_water_prior
from cells.core.surface_calcium_spec import Change as SurfaceCalciumChange
from cells.core.surface_calcium_spec import ionic_spec as surface_ionic_spec
from cells.core.surface_calcium_water_spec import Control as SurfaceCalciumWaterControl
from cells.core.surface_calcium_water_spec import SurfaceCalciumWaterModel
from cells.core.surface_calcium_water_spec import prior_spec as calcium_water_prior
from cells.core.surface_cotransport_spec import Control as SurfaceCotransportControl
from cells.core.surface_cotransport_spec import SurfaceCotransportModel
from cells.core.surface_cotransport_spec import energy_spec as cotransport_energy_spec
from cells.core.surface_cotransport_water_spec import Control as CotransportWaterControl
from cells.core.surface_cotransport_water_spec import SurfaceCotransportWaterModel
from cells.core.surface_cotransport_water_spec import water_spec as cotransport_water_spec
from cells.core.surface_energy_spec import Control as SurfaceEnergyControl
from cells.core.surface_energy_spec import SurfaceEnergyModel, initial_ionic_spec
from cells.core.surface_energy_water_spec import Control as SurfaceEnergyWaterControl
from cells.core.surface_energy_water_spec import SurfaceEnergyWaterModel, energy_spec
from cells.core.surface_kinetic_spec import Change as SurfaceKineticChange
from cells.core.surface_mobile_channel_spec import Control as SurfaceMobileChannelControl
from cells.core.surface_mobile_channel_spec import SurfaceMobileChannelModel
from cells.core.surface_mobile_channel_spec import prior_spec as mobile_channel_prior
from cells.core.surface_mobile_pump_repair_spec import SurfaceMobilePumpRepairModel
from cells.core.surface_mobile_pump_repair_spec import prior_spec as mobile_pump_repair_prior
from cells.core.surface_mobile_pump_spec import Control as SurfaceMobilePumpControl
from cells.core.surface_mobile_pump_spec import SurfaceMobilePumpModel
from cells.core.surface_mobile_pump_spec import prior_spec as mobile_pump_prior
from cells.core.surface_mobile_repair_spec import SurfaceMobileRepairModel
from cells.core.surface_mobile_repair_spec import prior_spec as mobile_repair_prior
from cells.core.surface_repair_spec import SurfaceRepairModel
from cells.core.surface_repair_spec import base_spec as repair_base_spec
from cells.core.surface_tissue_spec import SurfaceChange
from cells.core.surface_water_kinetic_spec import Control as SurfaceWaterKineticControl
from cells.core.surface_water_kinetic_spec import SurfaceWaterKineticModel
from cells.core.surface_water_kinetic_spec import prior_spec as water_kinetic_prior
from cells.core.surface_water_spec import Control as SurfaceWaterControl
from cells.core.surface_water_spec import SurfaceWaterModel
from cells.core.surface_water_spec import prior_spec as water_prior


class PairControl(NamedTuple):
    membrane: object  # [..., 4, membrane_capacity], three leak controls and pump.
    contact: object  # [..., (optional route axis), edge_capacity], never intrinsic gating.


class SurfaceControl(NamedTuple):
    membrane: object  # [..., membrane_capacity], passive route availability.
    junction: object  # [..., edge_capacity], passive route availability.


class SurfaceKineticControl(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object


SurfaceCalciumControl = NamedTuple(
    "SurfaceCalciumControl",
    [
        (k, object)
        for k in (
            *SurfaceKineticControl._fields,
            "er_reactions",
            "er_passive",
            "er_pump",
            "er_release",
            "plasma_pump",
            "plasma_exchange",
            "calcium_channel",
        )
    ],
)

SurfaceRepairControl = NamedTuple(
    "SurfaceRepairControl",
    [(k, object) for k in (*SurfaceCalciumControl._fields, "injury", "resealing")],
)

SurfaceMobileRepairControl = NamedTuple(
    "SurfaceMobileRepairControl",
    [(k, object) for k in (*SurfaceRepairControl._fields, "mobile_channel")],
)

SurfaceMobilePumpRepairControl = NamedTuple(
    "SurfaceMobilePumpRepairControl",
    [(k, object) for k in (*SurfaceMobileRepairControl._fields, "mobile_pump")],
)


class ERControl(NamedTuple):
    reactions: object
    passive: object
    pump: object
    release: object


class CalciumControl(NamedTuple):
    membrane: object
    channel: object
    junction: object
    er_reactions: object
    er_passive: object
    er_pump: object
    er_release: object


PlasmaControl = NamedTuple(
    "PlasmaControl",
    [(k, object) for k in (*CalciumControl._fields, "plasma_pump", "plasma_exchange")],
)
GatedCalciumControl = NamedTuple(
    "GatedCalciumControl", [(k, object) for k in (*PlasmaControl._fields, "calcium_channel")]
)


class VoltageGatedControl(NamedTuple):
    membrane: object  # [..., species+1, membrane_capacity], baseline leak and pump.
    channel: object  # [..., channel_capacity], availability only, not intrinsic gating.


class PhysicalIonicGraphControl(NamedTuple):
    membrane: object  # [..., species+1, membrane_capacity]
    channel: object  # [..., channel_capacity]
    junction: object  # [..., edge_capacity], independent of intrinsic junction gates.


def event_index(spec, time):
    return bisect_right([change.time for change in spec.experiment.changes], time) - 1


def control_values(spec, times):
    from cells.core import surface_active_profile_barrier_interventions_spec as active_combined

    if isinstance(spec.model, active_combined.SurfaceActiveProfileBarrierInterventionModel):
        return control_values(active_combined.owner_spec(spec), times)
    from cells.core import surface_calcium_energy_water_barrier_epoch_spec as water_barrier_epoch
    from cells.core import (
        surface_calcium_energy_water_repair_barrier_epoch_spec as repair_barrier_epoch,
    )

    if isinstance(
        spec.model, repair_barrier_epoch.SurfaceCalciumEnergyWaterRepairBarrierEpochModel
    ):
        return control_values(repair_barrier_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, water_barrier_epoch.SurfaceCalciumEnergyWaterBarrierEpochModel):
        return control_values(water_barrier_epoch.scheduled_spec(spec), times)
    from cells.core import surface_calcium_energy_water_barrier_interventions_spec as water_barrier
    from cells.core import (
        surface_calcium_energy_water_repair_barrier_interventions_spec as repair_barrier,
    )

    if isinstance(
        spec.model, repair_barrier.SurfaceCalciumEnergyWaterRepairBarrierInterventionModel
    ):
        return control_values(repair_barrier.owner_spec(spec), times)
    if isinstance(spec.model, water_barrier.SurfaceCalciumEnergyWaterBarrierInterventionModel):
        return control_values(water_barrier.owner_spec(spec), times)
    from cells.core import surface_active_barrier_interventions_spec as active_barrier
    from cells.core import surface_calcium_barrier_interventions_spec as calcium_barrier
    from cells.core import surface_calcium_energy_barrier_interventions_spec as energy_barrier

    if isinstance(spec.model, active_barrier.SurfaceActiveBarrierInterventionModel):
        return control_values(active_barrier.owner_spec(spec), times)
    if isinstance(spec.model, calcium_barrier.SurfaceCalciumBarrierInterventionModel):
        return control_values(calcium_barrier.owner_spec(spec), times)
    if isinstance(spec.model, energy_barrier.SurfaceCalciumEnergyBarrierInterventionModel):
        return control_values(energy_barrier.owner_spec(spec), times)
    from cells.core import surface_calcium_energy_water_profile_epoch_spec as joint_water_epoch
    from cells.core import (
        surface_calcium_energy_water_repair_profile_epoch_spec as joint_repair_epoch,
    )

    if isinstance(spec.model, joint_repair_epoch.SurfaceCalciumEnergyWaterRepairProfileEpochModel):
        return control_values(joint_repair_epoch.scheduled_spec(spec), times)
    if isinstance(spec.model, joint_water_epoch.SurfaceCalciumEnergyWaterProfileEpochModel):
        return control_values(joint_water_epoch.scheduled_spec(spec), times)
    from cells.core import (
        surface_calcium_energy_water_profile_interventions_spec as joint_water_profile,
    )
    from cells.core import (
        surface_calcium_energy_water_repair_profile_interventions_spec as joint_repair_profile,
    )

    if isinstance(
        spec.model, joint_repair_profile.SurfaceCalciumEnergyWaterRepairProfileInterventionModel
    ):
        return control_values(joint_repair_profile.owner_spec(spec), times)
    if isinstance(
        spec.model, joint_water_profile.SurfaceCalciumEnergyWaterProfileInterventionModel
    ):
        return control_values(joint_water_profile.owner_spec(spec), times)
    changes = spec.experiment.changes
    if isinstance(spec.model, SurfaceCalciumEnergyWaterRepairHCNExtraModel):
        original = control_values(joint_hcn_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        extra = []
        for key in ("injury", "resealing"):
            values = np.asarray([getattr(p, key) for p in changes], dtype=float)[indices]
            padded = np.zeros((len(times), spec.execution.membrane_capacity))
            padded[:, : len(spec.model.membranes)] = values
            extra.append(padded)
        return JointHCNRepairControl(*original, *extra)
    if isinstance(spec.model, SurfaceCalciumEnergyWaterHCNExtraModel):
        original = control_values(joint_hcn_water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return JointHCNWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCalciumEnergyWaterRepairModel):
        original = control_values(joint_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        extra = []
        for key in ("injury", "resealing"):
            values = np.asarray([getattr(p, key) for p in changes], dtype=float)[indices]
            padded = np.zeros((len(times), spec.execution.membrane_capacity))
            padded[:, : len(spec.model.membranes)] = values
            extra.append(padded)
        return JointRepairControl(*original, *extra)
    if isinstance(spec.model, SurfaceCalciumEnergyWaterModel):
        original = control_values(calcium_energy_water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceCalciumEnergyWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCalciumWaterModel):
        original = control_values(calcium_water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceCalciumWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCalciumEnergyMitochondriaModel):
        from cells.core.surface_calcium_energy_mitochondria_spec import Control, base_spec

        original = control_values(base_spec(spec), times)
        indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
        values = np.asarray([c.mitochondria for c in changes])[indices]
        padded = np.zeros((len(times), spec.execution.capacity))
        padded[:, : len(spec.model.mitochondria)] = values
        return Control(*original, padded)
    if isinstance(spec.model, SurfaceCalciumEnergyTransportModel):
        from cells.core.surface_calcium_energy_transport_spec import Control, base_spec

        original = control_values(base_spec(spec), times)
        changes = spec.experiment.changes
        indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
        values = np.asarray([c.network_transport for c in changes])[indices]
        padded = np.zeros((len(times), spec.execution.network_transport_capacity))
        padded[:, : len(spec.model.network_transporters)] = values
        return Control(*original, padded)
    from cells.core.surface_calcium_energy_regulated_spec import (
        SurfaceCalciumEnergyRegulatedModel,
    )
    from cells.core.surface_calcium_energy_regulated_spec import (
        control_values as regulated_controls,
    )
    from cells.core.surface_calcium_energy_regulated_v2_spec import (
        SurfaceCalciumEnergyRegulatedV2Model,
    )
    from cells.core.surface_calcium_energy_regulated_v2_spec import (
        control_values as regulated_v2_controls,
    )

    if isinstance(spec.model, SurfaceCalciumEnergyRegulatedModel):
        return regulated_controls(spec, times)
    if isinstance(spec.model, SurfaceCalciumEnergyRegulatedV2Model):
        return regulated_v2_controls(spec, times)
    if isinstance(spec.model, SurfaceCalciumEnergyModel):
        original = control_values(calcium_energy_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.regeneration for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.regeneration_capacity))
        padded[:, : len(spec.model.regeneration_ports)] = values
        return SurfaceCalciumEnergyControl(*original, padded)
    if isinstance(spec.model, SurfaceCotransportWaterModel):
        original = control_values(cotransport_water_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.cotransport for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.cotransport_capacity))
        padded[:, : len(spec.model.cotransporters)] = values
        return CotransportWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceCotransportModel):
        original = control_values(cotransport_energy_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.cotransport for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.cotransport_capacity))
        padded[:, : len(spec.model.cotransporters)] = values
        return SurfaceCotransportControl(*original, padded)
    if isinstance(spec.model, SurfaceEnergyWaterModel):
        original = control_values(energy_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceEnergyWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceEnergyModel):
        original = control_values(initial_ionic_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.regeneration for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.regeneration_capacity))
        padded[:, : len(spec.model.regeneration_ports)] = values
        return SurfaceEnergyControl(*original, padded)
    if isinstance(spec.model, SurfaceWaterKineticModel):
        original = control_values(water_kinetic_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceWaterKineticControl(*original, padded)
    if isinstance(spec.model, SurfaceWaterModel):
        original = control_values(water_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.water for p in changes], dtype=float)[indices]
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : len(spec.model.membranes)] = values
        return SurfaceWaterControl(*original, padded)
    if isinstance(spec.model, SurfaceMobileChannelModel):
        original = control_values(mobile_channel_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.channel for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (
                len(times),
                spec.execution.channel_population_capacity,
                spec.execution.membrane_capacity,
            )
        )
        padded[:, : len(spec.model.mobile_channels), : len(spec.model.membranes)] = values
        return SurfaceMobileChannelControl(*original, padded)
    if isinstance(spec.model, SurfaceMobilePumpModel):
        original = control_values(mobile_pump_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.pump for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (len(times), spec.execution.pump_population_capacity, spec.execution.membrane_capacity)
        )
        padded[:, : len(spec.model.mobile_pumps), : len(spec.model.membranes)] = values
        return SurfaceMobilePumpControl(*original, padded)
    if isinstance(spec.model, SurfaceMobilePumpRepairModel):
        original = control_values(mobile_pump_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.mobile_pump for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (len(times), spec.execution.pump_population_capacity, spec.execution.membrane_capacity)
        )
        padded[:, : len(spec.model.mobile_pumps), : len(spec.model.membranes)] = values
        return SurfaceMobilePumpRepairControl(*original, padded)
    if isinstance(spec.model, SurfaceMobileRepairModel):
        original = control_values(mobile_repair_prior(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.mobile_channel for p in changes], dtype=float)[indices]
        padded = np.zeros(
            (
                len(times),
                spec.execution.channel_population_capacity,
                spec.execution.membrane_capacity,
            )
        )
        padded[:, : len(spec.model.mobile_channels), : len(spec.model.membranes)] = values
        return SurfaceMobileRepairControl(*original, padded)
    if isinstance(spec.model, SurfaceRepairModel):
        original = control_values(repair_base_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        routes = []
        for name in ("injury", "resealing"):
            values = np.asarray([getattr(p, name) for p in changes], dtype=float)[indices]
            array = np.zeros((len(times), spec.execution.membrane_capacity))
            array[:, : values.shape[-1]] = values
            routes.append(array)
        return SurfaceRepairControl(*original, *routes)
    if isinstance(spec.model, BetseSpatialModel):
        control_type = (
            BetseJunctionControl
            if isinstance(spec.model, BetseJunctionModel)
            else BetseSpatialControl
        )
        if not changes:
            return control_type(
                *(
                    np.ones((len(times), spec.execution.membrane_capacity))
                    for _ in control_type._fields
                )
            )
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        return control_type(
            *(
                np.asarray([getattr(p, k) for p in changes], dtype=np.float64)[indices]
                for k in control_type._fields
            )
        )
    if not changes:
        return np.zeros(len(times), dtype=np.float64)
    if isinstance(changes[0], SurfaceCalciumChange):
        original = control_values(surface_ionic_spec(spec), times)
        stores = [control_values(store_spec(spec, i), times) for i in range(len(spec.model.stores))]
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        routes = []
        for name in ("plasma_pump", "plasma_exchange", "calcium_channel"):
            values = np.asarray([getattr(p, name) for p in changes], dtype=float)[indices]
            array = np.zeros((len(times), spec.execution.membrane_capacity))
            array[:, : values.shape[-1]] = values
            routes.append(array)
        return SurfaceCalciumControl(
            *original, *(np.stack([v[j] for v in stores], axis=1) for j in range(4)), *routes
        )
    if isinstance(changes[0], SurfaceKineticChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        result = []
        for name, capacity in (
            ("membrane", spec.execution.membrane_capacity),
            ("junction", spec.execution.edge_capacity),
            ("channel", spec.execution.channel_capacity),
            ("pump", spec.execution.membrane_capacity),
        ):
            values = np.asarray([getattr(p, name) for p in changes], dtype=np.float64)
            padded = np.zeros((len(times), capacity))
            padded[:, : values.shape[-1]] = values[indices]
            result.append(padded)
        return SurfaceKineticControl(*result)
    if isinstance(changes[0], SurfaceChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        result = []
        for name, capacity in (
            ("membrane", spec.execution.membrane_capacity),
            ("junction", spec.execution.edge_capacity),
        ):
            values = np.asarray([getattr(p, name) for p in changes], dtype=np.float64)
            padded = np.zeros((len(times), capacity))
            padded[:, : values.shape[-1]] = values[indices]
            result.append(padded)
        return SurfaceControl(*result)
    if isinstance(changes[0], GatedCalciumChange):
        original = control_values(plasma_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.calcium_channel for p in changes], dtype=np.float64)[indices]
        array = np.zeros((len(times), spec.execution.membrane_capacity))
        array[:, : values.shape[-1]] = values
        return GatedCalciumControl(*original, array)
    if isinstance(changes[0], PlasmaChange):
        original = control_values(base_spec(spec), times)
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        routes = []
        for name in ("plasma_pump", "plasma_exchange"):
            values = np.asarray([getattr(p, name) for p in changes], dtype=np.float64)[indices]
            array = np.zeros((len(times), spec.execution.membrane_capacity))
            array[:, : values.shape[-1]] = values
            routes.append(array)
        return PlasmaControl(*original, *routes)
    if isinstance(changes[0], CalciumChange):
        ionic = control_values(ionic_spec(spec), times)
        stores = [control_values(store_spec(spec, i), times) for i in range(len(spec.model.stores))]
        return CalciumControl(*ionic, *(np.stack([v[j] for v in stores], axis=1) for j in range(4)))
    if isinstance(changes[0], ERChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        reactions = np.zeros((len(times), spec.execution.reaction_capacity))
        values = np.asarray([p.reactions for p in changes], dtype=np.float64)
        reactions[:, : values.shape[-1]] = values[indices]
        return ERControl(
            reactions,
            *(
                np.asarray([getattr(p, name) for p in changes], dtype=np.float64)[indices]
                for name in ("passive", "pump", "release")
            ),
        )
    if isinstance(changes[0], ReactionChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.multipliers for p in changes], dtype=np.float64)
        result = np.zeros((len(times), spec.execution.reaction_capacity))
        result[:, : values.shape[-1]] = values[indices]
        return result
    if isinstance(changes[0], SpatialChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.asarray([p.availability for p in changes], dtype=np.float64)
        result = np.zeros((len(times), spec.execution.membrane_capacity))
        result[..., : values.shape[-1]] = values[indices]
        return result
    if isinstance(changes[0], PhysicalIonicGraphChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.array(
            [[(*leak, pump) for leak, pump in zip(p.leak, p.pump, strict=True)] for p in changes],
            dtype=np.float64,
        ).transpose(0, 2, 1)
        membrane = np.zeros((len(times), values.shape[1], spec.execution.membrane_capacity))
        membrane[..., : values.shape[-1]] = values[indices]
        routes = []
        for name, capacity in (
            ("channel", spec.execution.channel_capacity),
            ("junction", spec.execution.edge_capacity),
        ):
            group = np.asarray([getattr(p, name) for p in changes], dtype=np.float64)
            result = np.zeros((len(times), capacity))
            result[..., : group.shape[-1]] = group[indices]
            routes.append(result)
        return PhysicalIonicGraphControl(membrane, *routes)
    if isinstance(changes[0], VoltageGatedChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.array([(*p.leak, p.pump) for p in changes], dtype=np.float64)
        membrane = np.zeros((len(times), values.shape[1], spec.execution.membrane_capacity))
        membrane[:, :, 0] = values[indices]
        channel = np.zeros((len(times), spec.execution.channel_capacity))
        channel[:, 0] = np.array([p.availability for p in changes])[indices]
        return VoltageGatedControl(membrane, channel)
    if isinstance(changes[0], (PairChange, RoutePairChange)):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.array(
            [[(*leak, pump) for leak, pump in zip(p.leak, p.pump, strict=True)] for p in changes],
            dtype=np.float64,
        ).transpose(0, 2, 1)
        membrane = np.zeros((len(times), 4, spec.execution.membrane_capacity))
        membrane[:, :, : values.shape[-1]] = values[indices]
        routes = (len(changes[0].contact),) if isinstance(changes[0], RoutePairChange) else ()
        contact = np.zeros((len(times), *routes, spec.execution.edge_capacity))
        contact[..., 0] = np.array([p.contact for p in changes])[indices]
        return PairControl(membrane, contact)
    if isinstance(changes[0], MembraneChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.array([(*p.leak, p.pump) for p in changes], dtype=np.float64)
        result = np.zeros(
            (len(times), values.shape[1], spec.execution.membrane_capacity), dtype=np.float64
        )
        result[:, :, 0] = values[indices]
        return result
    if isinstance(changes[0], GraphContactChange):
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        values = np.array([p.open_fractions for p in changes], dtype=np.float64)
        result = np.zeros((len(times), spec.execution.edge_capacity), dtype=np.float64)
        result[:, : values.shape[1]] = values[indices]
        return result
    values = np.array(
        [
            change.open_fraction if isinstance(change, ContactChange) else change.rate
            for change in changes
        ],
        dtype=np.float64,
    )
    indices = np.searchsorted([change.time for change in changes], times, side="right") - 1
    return values[indices]
