"""Joint-state mobile Kv1.5 on finite calcium/ER tissue with prescribed injury."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace

from cells.core import surface_mobile_channel_spec as mobile
from cells.core import surface_repair_spec as prior
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ConfigError, _integer
from cells.core.surface_redistribution_spec import SurfaceEdge, parse_edges
from cells.processes.mobile_channel_gates import STATE_IDS

MODEL_ID = "resolved_repair@2"


@dataclass(frozen=True)
class SurfaceMobileRepairModel(prior.SurfaceRepairModel):
    mobile_channels: tuple[mobile.ChannelPopulation, ...]
    surface_edges: tuple[SurfaceEdge, ...]


@dataclass(frozen=True)
class Execution(prior.base.Execution):
    channel_population_capacity: int = 0
    surface_edge_capacity: int = 0


@dataclass(frozen=True)
class Change(prior.Change):
    mobile_channel: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    mobile_channels: tuple[tuple[tuple[mobile.ChannelChange, ...], ...], ...]

    @property
    def changes(self):
        original = super().changes
        clocks = [c.time for c in original]
        groups = tuple(g for pop in self.mobile_channels for g in pop)
        times = sorted({*clocks, *(c.time for g in groups for c in g)})
        n = len(self.membranes)
        result = []
        for t in times:
            held = original[bisect_right(clocks, t) - 1]
            levels = tuple(g[bisect_right([c.time for c in g], t) - 1].availability for g in groups)
            result.append(
                Change(
                    **(vars(held) | dict(time=t)),
                    mobile_channel=tuple(
                        levels[k * n : (k + 1) * n] for k in range(len(self.mobile_channels))
                    ),
                )
            )
        return tuple(result)


def prior_spec(spec):
    return replace(
        spec,
        model=project(spec.model, prior.SurfaceRepairModel),
        experiment=project(spec.experiment, prior.Experiment),
        execution=project(spec.execution, prior.base.Execution),
    )


def accounting_spec(spec):
    """Historical ion-flow support; this widened permeability never drives the RHS."""
    base = prior_spec(spec)
    ids = base.model.species_ids
    return replace(
        base,
        model=replace(
            base.model,
            membranes=tuple(
                replace(
                    p,
                    permeability_m_per_s=tuple(
                        value
                        + sum(
                            c.permeability_at_reference_density_m_per_s
                            for c in spec.model.mobile_channels
                            if c.species_id == ion
                            and sum(v[j] for v in c.initial_state_amount_fmol) > 0
                        )
                        for ion, value in zip(ids, p.permeability_m_per_s, strict=True)
                    ),
                )
                for j, p in enumerate(base.model.membranes)
            ),
        ),
    )


def to_dict(spec):
    raw = prior.to_dict(prior_spec(spec))
    m = spec.model
    patches = [p.id for p in m.membranes]
    raw["model"].update(
        id=MODEL_ID,
        surface_edges=[asdict(e) for e in m.surface_edges],
        mobile_channels=[
            asdict(p)
            | dict(
                initial_state_amount_fmol={
                    s: dict(zip(patches, values, strict=True))
                    for s, values in zip(STATE_IDS, p.initial_state_amount_fmol, strict=True)
                }
            )
            for p in m.mobile_channels
        ],
    )
    raw["experiment"]["mobile_channel_controls"] = [
        dict(channel_id=p.id, membrane_id=mem.id, schedule=[asdict(c) for c in group])
        for p, groups in zip(m.mobile_channels, spec.experiment.mobile_channels, strict=True)
        for mem, group in zip(m.membranes, groups, strict=True)
    ]
    for key in ("channel_population_capacity", "surface_edge_capacity"):
        raw["execution"][key] = getattr(spec.execution, key)
    return raw


def parse(data):
    raw = deepcopy(data)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if (
        m.get("id") != MODEL_ID
        or not {"mobile_channels", "surface_edges"} <= m.keys()
        or "mobile_channel_controls" not in e
        or not {"channel_population_capacity", "surface_edge_capacity"} <= x.keys()
    ):
        raise ConfigError("Mobile repair requires channels, surface edges, controls and capacities")
    channels, edges = m.pop("mobile_channels"), m.pop("surface_edges")
    controls = e.pop("mobile_channel_controls")
    capacity, edge_capacity = x.pop("channel_population_capacity"), x.pop("surface_edge_capacity")
    m["id"] = prior.MODEL_ID
    original = prior.parse(raw)
    b = original.model
    parsed = mobile.parse_populations(channels, b)
    connections = parse_edges(edges, b.membranes)
    capacity = _integer(capacity, "channel population capacity", minimum=len(parsed))
    edge_capacity = _integer(edge_capacity, "surface edge capacity", minimum=len(connections))
    patches = tuple(p.id for p in b.membranes)
    schedules = mobile.parse_controls(controls, parsed, patches, original.experiment.end_time)
    names = [
        p.id
        for family in (
            b.cells,
            b.extracellular,
            b.membranes,
            b.junctions,
            b.faces,
            b.channels,
            b.calcium_channels,
            parsed,
            connections,
        )
        for p in family
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Mobile channel, edge and existing physical IDs must be unique")
    spec = replace(
        original,
        model=SurfaceMobileRepairModel(
            **vars(b), mobile_channels=parsed, surface_edges=connections
        ),
        execution=Execution(
            **vars(original.execution),
            channel_population_capacity=capacity,
            surface_edge_capacity=edge_capacity,
        ),
        experiment=Experiment(
            **vars(original.experiment),
            mobile_channels=tuple(
                tuple(schedules[p.id, patch] for patch in patches) for p in parsed
            ),
        ),
    )
    from cells.models.surface_mobile_repair import check_definition

    check_definition(spec)
    return spec
