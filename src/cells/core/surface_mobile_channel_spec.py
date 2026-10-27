"""Mobile Kv1.5 joint gate-state populations on the existing pump/leak tissue."""

import copy
from bisect import bisect_right
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_mobile_pump_spec as prior
from cells.core.bioelectric_spec import positive
from cells.core.multispecies_spec import aligned, identifier
from cells.core.specs import ChannelChange, ConfigError, _fields, _integer, _number
from cells.core.voltage_gated_spec import fraction
from cells.processes import mobile_channel_gates as gates

MODEL_ID = "resolved_redistribution@3"


@dataclass(frozen=True)
class ChannelPopulation:
    id: str
    kinetic_law: str
    species_id: str
    reference_density_fmol_per_um2: float
    permeability_at_reference_density_m_per_s: float
    initial_state_amount_fmol: tuple[tuple[float, ...], ...]
    diffusivity_um2_per_s: float
    gate_mode: str


@dataclass(frozen=True)
class SurfaceMobileChannelModel(prior.SurfaceMobilePumpModel):
    mobile_channels: tuple[ChannelPopulation, ...]


@dataclass(frozen=True)
class Execution(prior.Execution):
    channel_population_capacity: int = 0


@dataclass(frozen=True)
class Change(prior.Change):
    channel: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    channels: tuple[tuple[tuple[ChannelChange, ...], ...], ...]

    @property
    def changes(self):
        original = prior.Experiment(
            **{k: getattr(self, k) for k in prior.Experiment.__dataclass_fields__}
        ).changes
        clocks = [c.time for c in original]
        groups = tuple(g for pop in self.channels for g in pop)
        times = sorted({*clocks, *(c.time for g in groups for c in g)})
        result = []
        for t in times:
            base = original[bisect_right(clocks, t) - 1]
            values = tuple(g[bisect_right([c.time for c in g], t) - 1].availability for g in groups)
            n = len(self.membranes)
            result.append(
                Change(
                    t,
                    base.membrane,
                    base.junction,
                    base.pump,
                    tuple(values[k * n : (k + 1) * n] for k in range(len(self.channels))),
                )
            )
        return tuple(result)


class Control(NamedTuple):
    membrane: object
    junction: object
    pump: object
    channel: object


def prior_spec(spec):
    def project(v, cls):
        return cls(**{k: getattr(v, k) for k in cls.__dataclass_fields__})

    return replace(
        spec,
        model=project(spec.model, prior.SurfaceMobilePumpModel),
        execution=project(spec.execution, prior.Execution),
        experiment=project(spec.experiment, prior.Experiment),
    )


def to_dict(spec):
    if type(spec.experiment) is not Experiment or type(spec.execution) is not Execution:
        raise ConfigError("Mobile channels require their own experiment and execution")
    raw = prior.to_dict(prior_spec(spec))
    m = spec.model
    patches = [p.id for p in m.membranes]
    raw["model"]["id"] = MODEL_ID
    raw["model"]["mobile_channels"] = [
        asdict(p)
        | dict(
            initial_state_amount_fmol={
                state: dict(zip(patches, values, strict=True))
                for state, values in zip(gates.STATE_IDS, p.initial_state_amount_fmol, strict=True)
            }
        )
        for p in m.mobile_channels
    ]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id=p.id, membrane_id=mem.id, schedule=[asdict(c) for c in group])
        for p, groups in zip(m.mobile_channels, spec.experiment.channels, strict=True)
        for mem, group in zip(m.membranes, groups, strict=True)
    ]
    raw["execution"]["channel_population_capacity"] = spec.execution.channel_population_capacity
    return raw


def parse(data):
    raw = copy.deepcopy(data)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if (
        m.get("id") != MODEL_ID
        or "mobile_channels" not in m
        or "channel_controls" not in e
        or "channel_population_capacity" not in x
    ):
        raise ConfigError("Require mobile channels, controls and capacity")
    pops, controls = m.pop("mobile_channels"), e.pop("channel_controls")
    if type(pops) is not list or not pops:
        raise ConfigError("Require an explicit nonempty mobile channel list")
    capacity = _integer(
        x.pop("channel_population_capacity"), "channel population capacity", minimum=len(pops)
    )
    m["id"] = prior.MODEL_ID
    original = prior.parse(raw)
    b = original.model
    patches = tuple(p.id for p in b.membranes)
    parsed = parse_populations(pops, b)
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
            b.mobile_pumps,
            parsed,
        )
        for p in family
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Mobile channel and physical IDs must be unique")
    schedules = parse_controls(controls, parsed, patches, original.experiment.end_time)
    spec = replace(
        original,
        model=SurfaceMobileChannelModel(**vars(b), mobile_channels=tuple(parsed)),
        experiment=Experiment(
            **vars(original.experiment),
            channels=tuple(tuple(schedules[p.id, patch] for patch in patches) for p in parsed),
        ),
        execution=Execution(**vars(original.execution), channel_population_capacity=capacity),
    )
    from cells.models.surface_mobile_channel import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid mobile channel definition: " + str(error)) from error
    return spec


def parse_populations(pops, b):
    """Shared neutral joint-state declarations, independent of the tissue composition."""
    if type(pops) is not list or not pops:
        raise ConfigError("Require an explicit nonempty mobile channel list")
    patches = tuple(p.id for p in b.membranes)
    parsed = []
    for p in pops:
        _fields(p, set(ChannelPopulation.__dataclass_fields__), "mobile channel")
        if p["kinetic_law"] != gates.LAW_ID or p["gate_mode"] not in ("dynamic", "frozen"):
            raise ConfigError("Require the Kv1.5 law and dynamic/frozen gate mode")
        if (
            p["species_id"] not in b.species_ids
            or b.valence[b.species_ids.index(p["species_id"])] != 1
        ):
            raise ConfigError("Kv1.5 requires a named monovalent potassium role")
        # Explicit role identity is K; other channel families need a separate law.
        if p["species_id"] != "K":
            raise ConfigError("Kv1.5 mobile channels currently require species K")
        _fields(p["initial_state_amount_fmol"], set(gates.STATE_IDS), "joint gate-state amounts")
        amounts = tuple(
            aligned(p["initial_state_amount_fmol"][s], patches, "channel state amount", _number)
            for s in gates.STATE_IDS
        )
        for cell in b.cells:
            present = [
                a > 0
                for values in amounts
                for patch, a in zip(b.membranes, values, strict=True)
                if patch.inside == cell.id
            ]
            if not present or (any(present) and not all(present)):
                raise ConfigError(
                    "All four channel states must be positive on every cell patch, "
                    "or the population wholly absent on that cell"
                )
        parsed.append(
            ChannelPopulation(
                identifier(p["id"]),
                p["kinetic_law"],
                p["species_id"],
                positive(p["reference_density_fmol_per_um2"], "channel reference density"),
                _number(p["permeability_at_reference_density_m_per_s"], "channel permeability"),
                amounts,
                _number(p["diffusivity_um2_per_s"], "channel diffusivity"),
                p["gate_mode"],
            )
        )
    return tuple(parsed)


def parse_controls(controls, parsed, patches, end_time):
    """Return a complete channel/patch schedule mapping without changing clocks."""
    if type(controls) is not list:
        raise ConfigError("Require an explicit channel control list")
    schedules = {}
    for group in controls:
        _fields(group, {"channel_id", "membrane_id", "schedule"}, "channel control")
        pair = identifier(group["channel_id"]), identifier(group["membrane_id"])
        if pair in schedules or type(group["schedule"]) is not list or not group["schedule"]:
            raise ConfigError("Every channel/patch pair needs one nonempty schedule")
        for c in group["schedule"]:
            _fields(c, {"time", "availability"}, "channel change")
        values = tuple(
            ChannelChange(_number(c["time"], "time"), fraction(c["availability"], "availability"))
            for c in group["schedule"]
        )
        if (
            values[0].time != 0
            or any(v.time > end_time for v in values)
            or any(v.time >= w.time for v, w in zip(values, values[1:], strict=False))
        ):
            raise ConfigError(
                "Channel schedules must start at zero and increase within the horizon"
            )
        schedules[pair] = values
    if set(schedules) != {(p.id, patch) for p in parsed for patch in patches}:
        raise ConfigError("Controls must exactly match every channel/patch pair")
    return schedules
