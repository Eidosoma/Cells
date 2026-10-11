"""Host-side, right-continuous experiment controls; never physical fluxes."""

from bisect import bisect_right
from typing import NamedTuple

import numpy as np

from cells.core.betse_spatial_spec import BetseSpatialModel
from cells.core.betse_spatial_spec import Control as BetseSpatialControl
from cells.core.er_spec import ERChange
from cells.core.gated_calcium_spec import GatedCalciumChange
from cells.core.gated_calcium_spec import base_spec as plasma_spec
from cells.core.plasma_calcium_spec import PlasmaChange, base_spec
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
from cells.core.surface_calcium_spec import Change as SurfaceCalciumChange
from cells.core.surface_calcium_spec import ionic_spec as surface_ionic_spec
from cells.core.surface_kinetic_spec import Change as SurfaceKineticChange
from cells.core.surface_tissue_spec import SurfaceChange


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
    changes = spec.experiment.changes
    if isinstance(spec.model, BetseSpatialModel):
        if not changes:
            return BetseSpatialControl(
                *(np.ones((len(times), spec.execution.membrane_capacity)) for _ in range(2))
            )
        indices = np.searchsorted([p.time for p in changes], times, side="right") - 1
        return BetseSpatialControl(
            *(
                np.asarray([getattr(p, k) for p in changes], dtype=np.float64)[indices]
                for k in ("pump", "channel")
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
