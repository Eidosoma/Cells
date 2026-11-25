"""Resolved patches with explicit intrinsic gates and maintained ATPase pools."""

import copy
from bisect import bisect_right
from dataclasses import asdict, dataclass, replace

from cells.definitions import surface_tissue_spec as base
from cells.definitions.kinetic_pump_spec import parse_pump, pump_to_dict
from cells.definitions.rate_junction_spec import parse_junction
from cells.definitions.spec_values import fraction, identifier
from cells.definitions.specs import (
    ChannelChange,
    ChannelSpec,
    ConfigError,
    KineticPumpSpec,
    SpatialExtracellularExecutionSpec,
    _fields,
    _integer,
    _number,
)
from cells.laws.channels import shared_channel_catalog, voltage_gates

MODEL_ID = "resolved_tissue@2"
CATALOG_MODEL_ID = "resolved_tissue@8"


@dataclass(frozen=True)
class Membrane(base.Membrane):
    pump: KineticPumpSpec | None


@dataclass(frozen=True)
class Junction(base.Junction):
    law: str
    threshold_voltage_V: float
    minimum_open_fraction: float
    initial_gate: float


@dataclass(frozen=True)
class SeriesGate:
    """One gate of a junction_series_gates@1 junction (FR-30): its kind, its parameters in that
    kind's Parameters order (laws/junctions/junction_series_gates.py), and its initial
    conductance factor c in [r, 1]."""

    kind: str
    parameters: tuple[float, ...]
    initial: float


@dataclass(frozen=True)
class SeriesJunction(Junction):
    """A junction whose gate is junction_series_gates@1 (FR-30; parsed by @3 alone, D262). Its
    Junction fields hold the conductance the gates give: minimum_open_fraction the product of
    the gates' residuals, initial_gate the product of their initial factors, the law the series
    law's ID; threshold_voltage_V is 0.0 and read by nothing, since each gate carries its own
    parameters. development is True: the law is development only, and a registered or judged
    result whose definition carries it is not admissible."""

    gates: tuple[SeriesGate, ...]
    development: bool

    def gate_block(self):
        """The definition's gate block, as parsed (to_dict's form)."""
        return {
            "law": self.law,
            "development": self.development,
            "gates": [
                {"kind": g.kind}
                | dict(zip(series_parameter_names(g.kind), g.parameters, strict=True))
                | {"initial": g.initial}
                for g in self.gates
            ],
        }


def series_parameter_names(kind):
    """A series gate kind's parameter names, its Parameters' fields in the law's own order."""
    from cells.laws.junctions import junction_series_gates as series
    from cells.laws.junctions import junction_voltage_relaxation as relaxation

    names = {
        "threshold_relaxation": relaxation.Parameters._fields,
        "boltzmann_eyring": series.BoltzmannEyring._fields,
    }
    if kind not in names:
        raise ConfigError(f"A series junction gate's kind is one of {series.KINDS}, not {kind!r}")
    return names[kind]


@dataclass(frozen=True)
class SurfaceKineticModel(base.SurfaceTissueModel):
    channels: tuple[ChannelSpec, ...]


@dataclass(frozen=True)
class PermeantIon:
    species_id: str
    relative_permeability: float


@dataclass(frozen=True)
class ChannelPopulation:
    id: str
    membrane_id: str
    kinetic_law: str
    max_permeability_m_per_s: float
    abundance: float
    initial_gate: tuple[float, ...]
    permeant_ions: tuple[PermeantIon, ...]


@dataclass(frozen=True)
class SurfaceCatalogModel(SurfaceKineticModel):
    """The shared gate catalogue's populations, each of one or more permeant ions, with transfer
    and dissipation ledgers per species."""

    channels: tuple[ChannelPopulation, ...]


def model_id(model):
    return CATALOG_MODEL_ID if isinstance(model, SurfaceCatalogModel) else MODEL_ID


@dataclass(frozen=True)
class Execution(SpatialExtracellularExecutionSpec):
    channel_capacity: int = 0


@dataclass(frozen=True)
class Change(base.SurfaceChange):
    channel: tuple[float, ...]
    pump: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(base.SurfaceExperiment):
    channels: tuple[tuple[ChannelChange, ...], ...]
    pumps: tuple[tuple[ChannelChange, ...], ...]  # All membrane slots; absent pumps stay zero.

    @property
    def changes(self):
        groups = (self.membranes, self.junctions, self.channels, self.pumps)
        times = sorted({0.0, *(c.time for family in groups for g in family for c in g)})
        return tuple(
            Change(
                time,
                *(
                    tuple(
                        g[bisect_right([p.time for p in g], time) - 1].availability for g in family
                    )
                    for family in groups
                ),
            )
            for time in times
        )


def passive_spec(spec):
    """Geometry/ledger projection only; intrinsic gates are not passive controls."""

    def project(value, cls):
        return cls(**{k: getattr(value, k) for k in cls.__dataclass_fields__})

    m, e = spec.model, spec.experiment
    model = replace(
        project(m, base.SurfaceTissueModel),
        membranes=tuple(project(p, base.Membrane) for p in m.membranes),
        junctions=tuple(project(p, base.Junction) for p in m.junctions),
    )
    return replace(
        spec,
        model=model,
        experiment=project(e, base.SurfaceExperiment),
        execution=project(spec.execution, SpatialExtracellularExecutionSpec),
    )


def to_dict(spec):
    if type(spec.experiment) is not Experiment or type(spec.execution) is not Execution:
        raise ConfigError("Resolved kinetics requires its own experiment and execution")
    raw = base.to_dict(passive_spec(spec))
    m, e = spec.model, spec.experiment
    raw["model"]["id"] = model_id(m)
    for target, p in zip(raw["model"]["membranes"], m.membranes, strict=True):
        target["pump"] = pump_to_dict(p, m.species_ids)
    for target, p in zip(raw["model"]["junctions"], m.junctions, strict=True):
        target["gate"] = {
            k: getattr(p, k)
            for k in ("law", "threshold_voltage_V", "minimum_open_fraction", "initial_gate")
        }
    raw["model"]["channels"] = [
        asdict(p)
        | {"initial_gate": list(p.initial_gate)}
        | (
            {"permeant_ions": [asdict(ion) for ion in p.permeant_ions]}
            if isinstance(p, ChannelPopulation)
            else {}
        )
        for p in m.channels
    ]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id=p.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.channels, e.channels, strict=True)
    ]
    raw["experiment"]["pump_controls"] = [
        dict(pump_id=p.pump.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.membranes, e.pumps, strict=True)
        if p.pump is not None
    ]
    raw["execution"]["channel_capacity"] = spec.execution.channel_capacity
    return raw


def parse(data):
    raw = copy.deepcopy(data)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    _fields(
        m,
        {
            "id",
            "species",
            "temperature_K",
            "cells",
            "extracellular",
            "membranes",
            "junctions",
            "faces",
            "closure",
            "channels",
        },
        "resolved kinetic model",
    )
    _fields(
        e,
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "junction_controls",
            "channel_controls",
            "pump_controls",
        },
        "resolved kinetic experiment",
    )
    _fields(x, set(Execution.__dataclass_fields__), "resolved kinetic execution")
    for key in ("species", "membranes", "junctions"):
        if type(m[key]) is not list:
            raise ConfigError(key + " requires an explicit list")
    if type(e["junction_controls"]) is not list:
        raise ConfigError("Require explicit junction controls")
    for group in e["junction_controls"]:
        _fields(group, {"junction_id", "schedule"}, "junction control")
        if type(group["schedule"]) is not list:
            raise ConfigError("Require explicit junction control changes")
        for c in group["schedule"]:
            _fields(c, {"time", "availability"}, "junction control change")
            fraction(c["availability"], "junction availability")
    channels = m.pop("channels", None)
    catalog = m["id"] == CATALOG_MODEL_ID
    if m["id"] not in (MODEL_ID, CATALOG_MODEL_ID) or type(channels) is not list:
        raise ConfigError(f"Require {MODEL_ID} or {CATALOG_MODEL_ID} with an explicit channel list")
    for p in m["membranes"]:
        _fields(p, set(base.Membrane.__dataclass_fields__) | {"law", "pump"}, "membrane")
    gates = []
    ids = tuple(_fields(p, {"id", "valence"}, "species")["id"] for p in m["species"])
    for p in m["junctions"]:
        _fields(p, set(base.Junction.__dataclass_fields__) | {"law", "gate"}, "junction")
        gates.append(
            parse_junction(
                dict(
                    id=p["id"],
                    from_cell=p["sender"],
                    to_cell=p["receiver"],
                    area_m2=p["area_m2"],
                    permeability_m_per_s=p["permeability_m_per_s"],
                    gate=p.pop("gate"),
                ),
                ids,
            )
        )
    pumps = [p.pop("pump") for p in m["membranes"]]
    controls = {kind: e.pop(kind + "_controls", None) for kind in ("channel", "pump")}
    capacity = x.pop("channel_capacity", None)
    m["id"] = base.MODEL_ID
    # Validate the initial field with the actual intrinsic junction openings.
    original = copy.deepcopy(e["junction_controls"])
    gate_by_id = {g.id: g.initial_gate for g in gates}
    scaled = []
    for group in e["junction_controls"]:
        if group["junction_id"] not in gate_by_id:
            raise ConfigError("Unknown junction control")
        initial = gate_by_id[group["junction_id"]]
        scaled.append(
            {
                **group,
                "schedule": [
                    {**c, "availability": c["availability"] * initial} for c in group["schedule"]
                ],
            }
        )
    # New control objects: a schedule shared with another control stays unscaled there.
    e["junction_controls"] = scaled
    passive = base.parse(raw)
    m0 = passive.model
    if m0.temperature_K != voltage_gates.TEMPERATURE_K:
        raise ConfigError("Resolved channels require 298.15 K; no temperature scaling")
    membranes = tuple(
        Membrane(**asdict(p), pump=parse_pump(q, ids, m0.valence))
        for p, q in zip(m0.membranes, pumps, strict=True)
    )
    junctions = tuple(
        Junction(
            **asdict(p),
            **{
                k: getattr(g, k)
                for k in ("law", "threshold_voltage_V", "minimum_open_fraction", "initial_gate")
            },
        )
        for p, g in zip(m0.junctions, gates, strict=True)
    )
    parsed = []
    for p in channels:
        if catalog:
            _fields(p, set(ChannelPopulation.__dataclass_fields__), "shared-gate channel")
            law = p["kinetic_law"]
            if (
                type(law) is not str
                or law not in shared_channel_catalog.LAW_CODES
                or type(p["permeant_ions"]) is not list
            ):
                raise ConfigError("Shared-gate channel requires a named law and permeant ions")
            ions = []
            for ion in p["permeant_ions"]:
                _fields(ion, set(PermeantIon.__dataclass_fields__), "permeant ion")
                species = identifier(ion["species_id"])
                weight = _number(ion["relative_permeability"], "relative permeability")
                if species not in ids or m0.valence[
                    ids.index(species)
                ] != shared_channel_catalog.SPECIES_VALENCE.get(species):
                    raise ConfigError("Shared-gate ion requires its law's species and valence")
                ions.append(PermeantIon(species, weight))
            if (
                tuple((ion.species_id, ion.relative_permeability) for ion in ions)
                != shared_channel_catalog.LAW_PERMEABILITIES[law]
            ):
                raise ConfigError(
                    "Shared-gate ions must exactly match the named law's "
                    "ordered permeability ratios"
                )
            if (
                p["membrane_id"] not in {v.id for v in membranes}
                or type(p["initial_gate"]) is not list
                or len(p["initial_gate"]) != 2
            ):
                raise ConfigError(
                    "Channel requires its patch and exactly the named law's declared gate state"
                )
            parsed.append(
                ChannelPopulation(
                    identifier(p["id"]),
                    identifier(p["membrane_id"]),
                    law,
                    _number(p["max_permeability_m_per_s"], "channel permeability"),
                    _number(p["abundance"], "channel abundance"),
                    tuple(fraction(v, "initial channel gate") for v in p["initial_gate"]),
                    tuple(ions),
                )
            )
            continue
        _fields(p, set(ChannelSpec.__dataclass_fields__), "channel")
        if (
            p["kinetic_law"] != voltage_gates.LAW_ID
            or p["membrane_id"] not in {v.id for v in membranes}
            or p["species_id"] not in ids
            or m0.valence[ids.index(p["species_id"])] != 1
            or type(p["initial_gate"]) is not list
            or len(p["initial_gate"]) != 2
        ):
            raise ConfigError(
                "Channel requires a named patch, its law's +1 species and explicit m/h gates"
            )
        parsed.append(
            ChannelSpec(
                *(identifier(p[k]) for k in ("id", "membrane_id", "species_id")),
                p["kinetic_law"],
                _number(p["max_permeability_m_per_s"], "channel permeability"),
                _number(p["abundance"], "channel abundance"),
                tuple(fraction(v, "initial channel gate") for v in p["initial_gate"]),
            )
        )
    names = [
        p.id
        for p in (
            *m0.cells,
            *m0.extracellular,
            *membranes,
            *junctions,
            *m0.faces,
            *parsed,
            *(p.pump for p in membranes if p.pump is not None),
        )
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Owner, route, channel and pump IDs must be globally unique")

    def schedules(groups, kind, names):
        if type(groups) is not list:
            raise ConfigError("Require explicit " + kind + " controls")
        result = {}
        for group in groups:
            _fields(group, {kind + "_id", "schedule"}, "control")
            name, changes = identifier(group[kind + "_id"]), group["schedule"]
            if name in result or type(changes) is not list or not changes:
                raise ConfigError("Each route needs one nonempty control schedule")
            for c in changes:
                _fields(c, {"time", "availability"}, "control change")
            values = tuple(
                ChannelChange(
                    _number(c["time"], "time"), fraction(c["availability"], "availability")
                )
                for c in changes
            )
            if (
                values[0].time != 0
                or any(c.time > passive.experiment.end_time for c in values)
                or any(b.time <= a.time for a, b in zip(values, values[1:], strict=False))
            ):
                raise ConfigError("Controls must start at zero and increase within the horizon")
            result[name] = values
        if set(result) != set(names):
            raise ConfigError("Control IDs must exactly match their routes")
        return result

    cs = schedules(controls["channel"], "channel", [p.id for p in parsed])
    ps = schedules(controls["pump"], "pump", [p.pump.id for p in membranes if p.pump is not None])
    js = schedules(original, "junction", [p.id for p in junctions])
    model = (SurfaceCatalogModel if catalog else SurfaceKineticModel)(
        **{
            k: getattr(m0, k)
            for k in base.SurfaceTissueModel.__dataclass_fields__
            if k not in ("membranes", "junctions")
        },
        membranes=membranes,
        junctions=junctions,
        channels=tuple(parsed),
    )
    experiment = Experiment(
        passive.experiment.end_time,
        passive.experiment.observation_times,
        passive.experiment.membranes,
        tuple(js[p.id] for p in junctions),
        tuple(cs[p.id] for p in parsed),
        tuple((ChannelChange(0.0, 0.0),) if p.pump is None else ps[p.pump.id] for p in membranes),
    )
    spec = replace(
        passive,
        model=model,
        experiment=experiment,
        execution=Execution(
            **asdict(passive.execution),
            channel_capacity=_integer(capacity, "channel_capacity", minimum=len(parsed)),
        ),
    )
    from cells.models.surface_kinetic import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved kinetic definition: " + str(error)) from error
    return spec
