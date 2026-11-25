"""Host-side, right-continuous experiment controls; never physical fluxes."""

from bisect import bisect_right
from typing import NamedTuple

import numpy as np

from cells.definitions.specs import (
    ContactChange,
    GraphContactChange,
    MembraneChange,
    PairChange,
    PhysicalIonicGraphChange,
    RoutePairChange,
    SpatialChange,
    VoltageGatedChange,
)
from cells.definitions.surface_kinetic_spec import Change as SurfaceKineticChange
from cells.definitions.surface_tissue_spec import SurfaceChange


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
    """The schedule position at `time`: the last change at or before it, a change within the
    clock's same-instant tolerance after it counting as at it (D283's one predicate)."""
    from cells.execution.grid import same_instant

    times = [change.time for change in spec.experiment.changes]
    k = bisect_right(times, time)
    while k < len(times) and same_instant(times[k], time):
        k += 1
    return k - 1


def control_values(spec, times):
    from cells.definitions import apical_vertex_spec as apical_vertex

    if isinstance(spec.model, apical_vertex.ApicalVertexModel):
        return apical_vertex.control_values(spec, times)
    from cells.definitions import cell_replacement_spec as replacement
    from cells.definitions import surface_pump_v2_spec as pump_v2
    from cells.definitions import surface_pump_v3_spec as pump_v3
    from cells.definitions import surface_pump_water_spec as pump_water
    from cells.definitions import surface_pump_water_v2_spec as pump_water_v2

    if isinstance(spec.model, pump_water_v2.SurfacePumpRegulatedWaterModel):
        return pump_water_v2.control_values(spec, times)
    if isinstance(spec.model, pump_water.SurfacePumpWaterModel):
        return pump_water.control_values(spec, times)
    if isinstance(spec.model, replacement.CellReplacementModel):
        return replacement.control_values(spec, times)
    from cells.definitions import pump_composite_spec as composite

    if isinstance(spec.model, composite.CompositeModel):
        return composite.control_values(spec, times)
    if isinstance(spec.model, pump_v3.SurfacePumpChannelModel):
        return pump_v3.control_values(spec, times)
    if isinstance(spec.model, pump_v2.SurfacePumpModel):
        return pump_v2.control_values(spec, times)
    changes = spec.experiment.changes
    if not changes:
        return np.zeros(len(times), dtype=np.float64)
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
