"""Explicit pool ownership, independent random streams and a common physical clock."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cells.assembly.spec import AssemblyError
from cells.assembly_cell.spec import tick_at
from cells.assembly_cluster import MODEL_ID
from cells.assembly_pool.spec import parse_spec as parse_pool
from cells.core.gated_calcium_spec import GatedCalciumModel
from cells.core.ip3_calcium_spec import IP3CalciumModel
from cells.core.plasma_calcium_spec import PlasmaModel
from cells.core.schedule import control_values
from cells.core.spatial_calcium_spec import CalciumModel
from cells.core.specs import SpatialJunctionSpec
from cells.core.specs import parse_spec as parse_ionic
from cells.core.surface_calcium_spec import (
    SurfaceCalciumCavModel,
    SurfaceCalciumChannelModel,
    SurfaceCalciumHCNModel,
    SurfaceCalciumKv1Model,
    SurfaceCalciumModel,
    SurfaceCalciumSodiumModel,
)
from cells.core.tissue_calcium_spec import TissueCalciumModel
from cells.models.registry import get_model


@dataclass(frozen=True)
class PoolBinding:
    cell_id: str
    stream_id: int
    pool: object
    inactive_availability: float
    active_availability: float

    def to_dict(self):
        return {
            "cell_id": self.cell_id,
            "stream_id": self.stream_id,
            "pool": self.pool.to_dict(),
            "coupling": {
                "law": "root_component_has_cycle@1",
                "inactive_availability": self.inactive_availability,
                "active_availability": self.active_availability,
            },
        }


@dataclass(frozen=True)
class ClusterSpec:
    pools: tuple[PoolBinding, ...]
    ionic: object
    window_ticks: int

    @property
    def pool(self):
        """Common population/resource policy, checked equal across all owners."""
        return self.pools[0].pool

    @property
    def ticks(self):
        return round(self.pool.end_time_s / self.ionic.execution.dt)

    @property
    def working_bytes(self):
        return sum(p.pool.working_bytes for p in self.pools) + (
            self.pool.worlds * 64 * get_model(self.ionic.model).working_size(self.ionic)
        )

    @property
    def output_bound(self):
        return (
            sum(p.pool.output_bound for p in self.pools)
            + self.pool.worlds * (32 * get_model(self.ionic.model).working_size(self.ionic) + 4096)
            + len(self.ionic.experiment.observation_times)
            * len(self.pools)
            * (65536 + 1024 * self.pool.worlds)
        )

    def to_dict(self):
        return {
            "model": MODEL_ID,
            "pools": [p.to_dict() for p in self.pools],
            "ionic": self.ionic.to_dict(),
            "window_ticks": self.window_ticks,
        }

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()


def parse_spec(data):
    if not isinstance(data, dict) or set(data) != {"model", "pools", "ionic", "window_ticks"}:
        raise AssemblyError("Require complete assembly-cluster definition")
    if data["model"] != MODEL_ID:
        raise AssemblyError("Unsupported assembly-cluster identity")
    ion = parse_ionic(data["ionic"])
    if type(ion.model) not in (
        SpatialJunctionSpec,
        CalciumModel,
        PlasmaModel,
        GatedCalciumModel,
        IP3CalciumModel,
        TissueCalciumModel,
        SurfaceCalciumModel,
        SurfaceCalciumChannelModel,
        SurfaceCalciumSodiumModel,
        SurfaceCalciumHCNModel,
        SurfaceCalciumKv1Model,
        SurfaceCalciumCavModel,
    ):
        raise AssemblyError("Assembly cluster requires a qualified spatial ionic or calcium family")
    if len(ion.experiment.changes) != 1 or ion.experiment.changes[0].time != 0:
        raise AssemblyError("Initial assembly cluster requires constant external controls")
    cell_ids = [c.id for c in ion.model.cells]
    if isinstance(ion.model, SurfaceCalciumModel):
        owners = {p.id: p.inside for p in ion.model.membranes}
        if {owners[c.membrane_id] for c in ion.model.channels} != set(cell_ids):
            raise AssemblyError("Resolved assembly requires channel ownership in every cell")
    elif len(ion.model.channels) != len(cell_ids):
        raise AssemblyError("Require one channel and one assembly pool per cell")
    entries = data["pools"]
    if type(entries) is not list or len(entries) != len(cell_ids):
        raise AssemblyError("Require one explicitly owned pool per cell")
    pools, streams, base_seeds = {}, set(), set()
    for row in entries:
        if not isinstance(row, dict) or set(row) != {"cell_id", "stream_id", "pool", "coupling"}:
            raise AssemblyError("Invalid assembly pool binding")
        owner, stream = row["cell_id"], row["stream_id"]
        if not isinstance(owner, str) or owner not in cell_ids or owner in pools:
            raise AssemblyError("Pool owners must match distinct ionic cell IDs")
        if type(stream) is not int or not 0 <= stream < 2**32 or stream in streams:
            raise AssemblyError("Cell stream IDs must be distinct uint32 values")
        pool = parse_pool(row["pool"])
        coupling = row["coupling"]
        if (
            not isinstance(coupling, dict)
            or set(coupling) != {"law", "inactive_availability", "active_availability"}
            or coupling["law"] != "root_component_has_cycle@1"
        ):
            raise AssemblyError("Require explicit cycle-dependent channel availability")
        levels = [coupling[k] for k in ("inactive_availability", "active_availability")]
        if any(
            type(v) not in (int, float) or not np.isfinite(v) or not 0 <= v <= 1 for v in levels
        ):
            raise AssemblyError("Channel availability must be finite in [0,1]")
        pools[owner] = PoolBinding(owner, stream, pool, *map(float, levels))
        streams.add(stream)
        base_seeds.add((pool.seed - stream) % 2**32)
    if len(base_seeds) != 1:
        raise AssemblyError("Cell seeds must equal common ensemble seed plus stream ID modulo 2^32")
    ordered = tuple(pools[owner] for owner in cell_ids)
    common = ordered[0].pool
    for binding in ordered:
        p = binding.pool
        if any(
            getattr(p, k) != getattr(common, k)
            for k in (
                "worlds",
                "world_id_start",
                "end_time_s",
                "recording",
                "max_wall_seconds",
                "max_output_bytes",
            )
        ):
            raise AssemblyError("Cell pools require common world IDs, clocks and resource policy")
    if common.end_time_s != ion.experiment.end_time or common.recording != "summary":
        raise AssemblyError("Components require the same horizon and summary assembly recording")
    if (
        not 1 <= common.worlds <= 4096
        or not 0 < ion.execution.dt <= 1e-4
        or not ion.execution.jit
        or ion.execution.solver != "rk4"
    ):
        raise AssemblyError("Require <=4096 worlds, compiled RK4, and ionic dt <= 0.0001 s")
    window = data["window_ticks"]
    if type(window) is not int or not 1 <= window <= 256:
        raise AssemblyError("window_ticks must be an integer in [1,256]")
    spec = ClusterSpec(ordered, ion, window)
    tick_at(spec, common.end_time_s)
    for time in ion.experiment.observation_times:
        tick_at(spec, time)
    if (
        spec.ticks > ion.execution.max_steps
        or spec.ticks > 1000000
        or spec.working_bytes > 2 * 1024**3
        or spec.output_bound > common.max_output_bytes
    ):
        raise AssemblyError("Cluster tick, working-memory or output budget exceeded")
    get_model(ion.model).check_steps(ion, [ion.execution.dt], control_values(ion, [0.0]))
    return spec


def channel_owners(spec):
    cells = [p.cell_id for p in spec.pools]
    membranes = {p.id: p.inside for p in spec.ionic.model.membranes}
    result = np.zeros(spec.ionic.execution.channel_capacity, np.int32)
    for i, channel in enumerate(spec.ionic.model.channels):
        result[i] = cells.index(membranes[channel.membrane_id])
    return result


def load_spec(path):
    return parse_spec(json.loads(Path(path).read_text()))
