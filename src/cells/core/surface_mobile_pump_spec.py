"""Neutral mobile Na/K ATPase populations with explicit maintained metabolism."""

import copy
from bisect import bisect_right
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_redistribution_spec as prior
from cells.core.bioelectric_spec import positive
from cells.core.kinetic_finite_spec import parse_pump
from cells.core.multispecies_spec import aligned, identifier
from cells.core.specs import (
    ChannelChange,
    ConfigError,
    KineticPumpSpec,
    MaintainedMetabolismSpec,
    _fields,
    _integer,
    _number,
)
from cells.core.surface_tissue_spec import SurfaceChange, SurfaceExperiment
from cells.core.voltage_gated_spec import fraction

MODEL_ID = "resolved_redistribution@2"


@dataclass(frozen=True)
class PumpPopulation:
    id: str
    law: str
    roles: tuple[str, str]
    stoichiometry: tuple[int, ...]
    turnover_per_s: float
    km_na_mM: float
    km_k_mM: float
    km_atp_mM: float
    metabolism: MaintainedMetabolismSpec
    reference_density_fmol_per_um2: float
    initial_amount_fmol: tuple[float, ...]
    diffusivity_um2_per_s: float


@dataclass(frozen=True)
class SurfaceMobilePumpModel(prior.SurfaceRedistributionModel):
    mobile_pumps: tuple[PumpPopulation, ...]


@dataclass(frozen=True)
class Execution(prior.Execution):
    pump_population_capacity: int = 0


@dataclass(frozen=True)
class Change(SurfaceChange):
    pump: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class Experiment(SurfaceExperiment):
    pumps: tuple[tuple[tuple[ChannelChange, ...], ...], ...]

    @property
    def changes(self):
        groups = self.membranes + self.junctions + tuple(g for pop in self.pumps for g in pop)
        clocks = [[p.time for p in g] for g in groups]
        nm, nj = len(self.membranes), len(self.junctions)
        result = []
        for time in sorted({0.0, *(t for clock in clocks for t in clock)}):
            held = tuple(
                g[bisect_right(clock, time) - 1].availability
                for g, clock in zip(groups, clocks, strict=True)
            )
            pump = held[nm + nj :]
            result.append(
                Change(
                    time,
                    held[:nm],
                    held[nm : nm + nj],
                    tuple(pump[k * nm : (k + 1) * nm] for k in range(len(self.pumps))),
                )
            )
        return tuple(result)


class Control(NamedTuple):
    membrane: object
    junction: object
    pump: object  # [..., pump_population_slot, membrane_slot]


def prior_spec(spec):
    def project(value, cls):
        return cls(**{k: getattr(value, k) for k in cls.__dataclass_fields__})

    return replace(
        spec,
        model=project(spec.model, prior.SurfaceRedistributionModel),
        execution=project(spec.execution, prior.Execution),
        experiment=project(spec.experiment, SurfaceExperiment),
    )


def to_dict(spec):
    if type(spec.experiment) is not Experiment or type(spec.execution) is not Execution:
        raise ConfigError("Mobile pumps require their own experiment and execution")
    raw = prior.to_dict(prior_spec(spec))
    m = spec.model
    raw["model"]["id"] = MODEL_ID
    raw["model"]["mobile_pumps"] = [
        asdict(p)
        | dict(
            roles=dict(zip(("sodium", "potassium"), p.roles, strict=True)),
            stoichiometry={s: p.stoichiometry[m.species_ids.index(s)] for s in p.roles},
            initial_amount_fmol=dict(
                zip((v.id for v in m.membranes), p.initial_amount_fmol, strict=True)
            ),
        )
        for p in m.mobile_pumps
    ]
    raw["experiment"]["pump_controls"] = [
        dict(pump_id=p.id, membrane_id=mem.id, schedule=[asdict(c) for c in group])
        for p, groups in zip(m.mobile_pumps, spec.experiment.pumps, strict=True)
        for mem, group in zip(m.membranes, groups, strict=True)
    ]
    raw["execution"]["pump_population_capacity"] = spec.execution.pump_population_capacity
    return raw


def parse(data):
    raw = copy.deepcopy(data)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if (
        m.get("id") != MODEL_ID
        or "mobile_pumps" not in m
        or "pump_controls" not in e
        or "pump_population_capacity" not in x
    ):
        raise ConfigError("Require resolved_redistribution@2, mobile pumps, controls and capacity")
    pumps, controls = m.pop("mobile_pumps"), e.pop("pump_controls")
    if type(pumps) is not list or not pumps:
        raise ConfigError("Require an explicit nonempty mobile pump list")
    capacity = _integer(
        x.pop("pump_population_capacity"), "pump population capacity", minimum=len(pumps)
    )
    m["id"] = prior.MODEL_ID
    original = prior.parse(raw, allow_empty_populations=True)
    b = original.model
    patches = tuple(p.id for p in b.membranes)
    parsed = parse_populations(pumps, b)
    names = [
        p.id
        for family in (
            b.cells,
            b.extracellular,
            b.membranes,
            b.junctions,
            b.faces,
            b.mobile_populations,
            b.surface_edges,
            parsed,
        )
        for p in family
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Mobile pump, population and physical IDs must be unique")
    schedules = parse_controls(controls, parsed, patches, original.experiment.end_time)
    spec = replace(
        original,
        model=SurfaceMobilePumpModel(**vars(b), mobile_pumps=tuple(parsed)),
        experiment=Experiment(
            **vars(original.experiment),
            pumps=tuple(tuple(schedules[p.id, patch] for patch in patches) for p in parsed),
        ),
        execution=Execution(**vars(original.execution), pump_population_capacity=capacity),
    )
    from cells.models.surface_mobile_pump import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid mobile pump definition: " + str(error)) from error
    return spec


def parse_populations(pumps, b):
    """Validate neutral ATPase declarations independently of the ionic family."""
    if type(pumps) is not list or not pumps:
        raise ConfigError("Require an explicit nonempty mobile pump list")
    patches = tuple(p.id for p in b.membranes)
    parsed = []
    for p in pumps:
        _fields(p, set(PumpPopulation.__dataclass_fields__), "mobile pump")
        # Reuse the existing chemistry validator with a zero placeholder capacity.
        # No static capacity is stored: actual capacity is turnover * owned amount.
        q = {k: p[k] for k in KineticPumpSpec.__dataclass_fields__ if k != "capacity_fmol_per_s"}
        kinetic = parse_pump(q | dict(capacity_fmol_per_s=0.0), b.species_ids, b.valence)
        amount = aligned(p["initial_amount_fmol"], patches, "pump amount", _number)
        for cell in b.cells:
            present = [
                a > 0
                for patch, a in zip(b.membranes, amount, strict=True)
                if patch.inside == cell.id
            ]
            if not present or (any(present) and not all(present)):
                raise ConfigError(
                    "A pump population must fill every patch positively or be absent on that cell"
                )
        parsed.append(
            PumpPopulation(
                **{
                    k: getattr(kinetic, k)
                    for k in KineticPumpSpec.__dataclass_fields__
                    if k != "capacity_fmol_per_s"
                },
                turnover_per_s=_number(p["turnover_per_s"], "pump turnover"),
                reference_density_fmol_per_um2=positive(
                    p["reference_density_fmol_per_um2"], "pump reference density"
                ),
                initial_amount_fmol=amount,
                diffusivity_um2_per_s=_number(p["diffusivity_um2_per_s"], "pump diffusivity"),
            )
        )
    return tuple(parsed)


def parse_controls(controls, parsed, patches, end_time):
    if type(controls) is not list:
        raise ConfigError("Require an explicit pump control list")
    schedules = {}
    for group in controls:
        _fields(group, {"pump_id", "membrane_id", "schedule"}, "mobile pump control")
        pair = identifier(group["pump_id"]), identifier(group["membrane_id"])
        if pair in schedules or type(group["schedule"]) is not list or not group["schedule"]:
            raise ConfigError("Every pump/patch pair needs one nonempty control schedule")
        for c in group["schedule"]:
            _fields(c, {"time", "availability"}, "pump control change")
        values = tuple(
            ChannelChange(_number(c["time"], "time"), fraction(c["availability"], "availability"))
            for c in group["schedule"]
        )
        if (
            values[0].time != 0
            or any(v.time > end_time for v in values)
            or any(v.time >= w.time for v, w in zip(values, values[1:], strict=False))
        ):
            raise ConfigError("Pump controls must start at zero and increase within the horizon")
        schedules[pair] = values
    if set(schedules) != {(p.id, patch) for p in parsed for patch in patches}:
        raise ConfigError("Controls must exactly match every mobile pump/patch pair")
    return schedules
