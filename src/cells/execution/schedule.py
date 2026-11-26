"""Host-side, right-continuous experiment controls; never physical fluxes."""

from bisect import bisect_right
from typing import NamedTuple

import numpy as np

from cells.definitions.specs import ConfigError, GraphContactChange
from cells.definitions.surface_kinetic_spec import Change as SurfaceKineticChange
from cells.definitions.surface_tissue_spec import SurfaceChange


class SurfaceControl(NamedTuple):
    membrane: object  # [..., membrane_capacity], passive route availability.
    junction: object  # [..., edge_capacity], passive route availability.


class SurfaceKineticControl(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object


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
    indices = np.searchsorted([p.time for p in changes], times, side="right") - 1

    def held(name, capacity):
        values = np.asarray([getattr(p, name) for p in changes], dtype=np.float64)
        padded = np.zeros((len(times), capacity))
        padded[:, : values.shape[-1]] = values[indices]
        return padded

    x, first = spec.execution, changes[0] if changes else None
    if isinstance(first, SurfaceKineticChange):
        return SurfaceKineticControl(
            held("membrane", x.membrane_capacity),
            held("junction", x.edge_capacity),
            held("channel", x.channel_capacity),
            held("pump", x.membrane_capacity),
        )
    if isinstance(first, SurfaceChange):
        return SurfaceControl(
            held("membrane", x.membrane_capacity), held("junction", x.edge_capacity)
        )
    if isinstance(first, GraphContactChange):
        return held("open_fractions", x.edge_capacity)
    raise ConfigError(f"No control schedule for {type(first).__name__}")
