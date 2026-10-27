"""Neutral mobile ATPases on the complete mobile-channel/calcium/injury model."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace

from cells.core import surface_mobile_pump_spec as pumps
from cells.core import surface_mobile_repair_spec as prior
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ConfigError, _integer

MODEL_ID = "resolved_repair@3"


@dataclass(frozen=True)
class SurfaceMobilePumpRepairModel(prior.SurfaceMobileRepairModel):
    mobile_pumps: tuple[pumps.PumpPopulation, ...]


@dataclass(frozen=True)
class Execution(prior.Execution):
    pump_population_capacity: int = 0


@dataclass(frozen=True)
class Change(prior.Change):
    mobile_pump: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    mobile_pumps: tuple[tuple[tuple[pumps.ChannelChange, ...], ...], ...]

    @property
    def changes(self):
        original = super().changes
        clocks = [c.time for c in original]
        groups = tuple(g for pop in self.mobile_pumps for g in pop)
        n = len(self.membranes)
        result = []
        for t in sorted({*clocks, *(c.time for g in groups for c in g)}):
            held = original[bisect_right(clocks, t) - 1]
            levels = tuple(g[bisect_right([c.time for c in g], t) - 1].availability for g in groups)
            result.append(
                Change(
                    **(vars(held) | dict(time=t)),
                    mobile_pump=tuple(
                        levels[k * n : (k + 1) * n] for k in range(len(self.mobile_pumps))
                    ),
                )
            )
        return tuple(result)


def prior_spec(spec):
    return replace(
        spec,
        model=project(spec.model, prior.SurfaceMobileRepairModel),
        experiment=project(spec.experiment, prior.Experiment),
        execution=project(spec.execution, prior.Execution),
    )


def to_dict(spec):
    raw = prior.to_dict(prior_spec(spec))
    m = spec.model
    patches = [p.id for p in m.membranes]
    raw["model"].update(
        id=MODEL_ID,
        mobile_pumps=[
            asdict(p)
            | dict(
                roles=dict(zip(("sodium", "potassium"), p.roles, strict=True)),
                stoichiometry={s: p.stoichiometry[m.species_ids.index(s)] for s in p.roles},
                initial_amount_fmol=dict(zip(patches, p.initial_amount_fmol, strict=True)),
            )
            for p in m.mobile_pumps
        ],
    )
    raw["experiment"]["mobile_pump_controls"] = [
        dict(pump_id=p.id, membrane_id=patch, schedule=[asdict(c) for c in group])
        for p, groups in zip(m.mobile_pumps, spec.experiment.mobile_pumps, strict=True)
        for patch, group in zip(patches, groups, strict=True)
    ]
    raw["execution"]["pump_population_capacity"] = spec.execution.pump_population_capacity
    return raw


def parse(data):
    raw = deepcopy(data)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if (
        m.get("id") != MODEL_ID
        or "mobile_pumps" not in m
        or "mobile_pump_controls" not in e
        or "pump_population_capacity" not in x
    ):
        raise ConfigError("Mobile pump repair requires populations, controls and capacity")
    declarations = m.pop("mobile_pumps")
    controls = e.pop("mobile_pump_controls")
    capacity = x.pop("pump_population_capacity")
    m["id"] = prior.MODEL_ID
    original = prior.parse(raw)
    b = original.model
    parsed = pumps.parse_populations(declarations, b)
    capacity = _integer(capacity, "pump population capacity", minimum=len(parsed))
    patches = tuple(p.id for p in b.membranes)
    schedules = pumps.parse_controls(controls, parsed, patches, original.experiment.end_time)
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
            b.surface_edges,
            b.mobile_channels,
            parsed,
        )
        for p in family
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Mobile pumps and physical population IDs must be unique")
    spec = replace(
        original,
        model=SurfaceMobilePumpRepairModel(**vars(b), mobile_pumps=parsed),
        experiment=Experiment(
            **vars(original.experiment),
            mobile_pumps=tuple(tuple(schedules[p.id, patch] for patch in patches) for p in parsed),
        ),
        execution=Execution(**vars(original.execution), pump_population_capacity=capacity),
    )
    from cells.models.surface_mobile_pump_repair import check_definition

    check_definition(spec)
    return spec
