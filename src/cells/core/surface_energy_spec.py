"""Strict finite cellular energy owners on fixed resolved active ionic tissue."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_kinetic_spec as prior
from cells.core.bioelectric_spec import positive, signed_number
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
from cells.core.voltage_gated_spec import fraction
from cells.processes import finite_energy as energy

MODEL_ID = "resolved_energy@1"
MORRIS_LECAR_MODEL_ID = "resolved_energy@2"
METABOLISM_ID = "finite_energy_pool@1"


@dataclass(frozen=True)
class EnergyPool:
    id: str
    cell_id: str
    law: str
    initial_amount_fmol: tuple[float, float, float]
    delta_g0_J_per_mol: float


@dataclass(frozen=True)
class RegenerationPort:
    id: str
    pool_id: str
    law: str
    capacity_fmol_per_s: float
    supplied_energy_J_per_mol: float


@dataclass(frozen=True)
class PoolMetabolism:
    kind: str
    pool_id: str


@dataclass(frozen=True)
class FinitePump(KineticPumpSpec):
    metabolism: PoolMetabolism


@dataclass(frozen=True)
class Membrane(prior.Membrane):
    pump: FinitePump | None


@dataclass(frozen=True)
class SurfaceEnergyModel(prior.SurfaceCavModel):
    energy_pools: tuple[EnergyPool, ...]
    regeneration_ports: tuple[RegenerationPort, ...]


@dataclass(frozen=True)
class SurfaceEnergyMorrisLecarModel(SurfaceEnergyModel):
    """Finite fuel with the 53-law catalog and explicit zero/one/two gate states."""


def model_id(model):
    return MORRIS_LECAR_MODEL_ID if isinstance(model, SurfaceEnergyMorrisLecarModel) else MODEL_ID


@dataclass(frozen=True)
class Execution(prior.Execution):
    regeneration_capacity: int = 0


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    regeneration: object


@dataclass(frozen=True)
class Change(prior.Change):
    regeneration: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    regenerations: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        families = (self.membranes, self.junctions, self.channels, self.pumps, self.regenerations)
        times = sorted({0.0, *(c.time for family in families for group in family for c in group)})
        return tuple(
            Change(
                time,
                *(
                    tuple(
                        group[bisect_right([c.time for c in group], time) - 1].availability
                        for group in family
                    )
                    for family in families
                ),
            )
            for time in times
        )


def _project(value, cls):
    return cls(**{key: getattr(value, key) for key in cls.__dataclass_fields__})


def initial_ionic_spec(spec):
    """Initial parser/layout projection only; finite pools evolve in the new model."""
    m = spec.model
    kind = (
        prior.SurfaceMorrisLecarModel
        if isinstance(m, SurfaceEnergyMorrisLecarModel)
        else prior.SurfaceCavModel
    )
    pools = {pool.id: pool for pool in m.energy_pools}
    volumes = {cell.id: cell.volume_pL for cell in m.cells}
    membranes = []
    for membrane in m.membranes:
        pump = membrane.pump
        if pump is not None:
            pool = pools[pump.metabolism.pool_id]
            metabolism = MaintainedMetabolismSpec(
                "maintained_chemical_reservoirs@1",
                *(value / volumes[pool.cell_id] for value in pool.initial_amount_fmol),
                pool.delta_g0_J_per_mol,
            )
            pump = KineticPumpSpec(**(vars(pump) | dict(metabolism=metabolism)))
        membranes.append(prior.Membrane(**(vars(membrane) | dict(pump=pump))))
    return replace(
        spec,
        model=replace(_project(m, kind), membranes=tuple(membranes)),
        experiment=_project(spec.experiment, prior.Experiment),
        execution=_project(spec.execution, prior.Execution),
    )


def to_dict(spec):
    if (
        type(spec.model) not in (SurfaceEnergyModel, SurfaceEnergyMorrisLecarModel)
        or type(spec.experiment) is not Experiment
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Resolved energy requires its own model/experiment/execution types")
    raw = prior.to_dict(initial_ionic_spec(spec))
    m, e = spec.model, spec.experiment
    raw["model"].update(
        id=model_id(m),
        energy_pools=[
            asdict(pool)
            | dict(
                initial_amount_fmol=dict(
                    zip(
                        energy.SPECIES,
                        pool.initial_amount_fmol,
                        strict=True,
                    )
                )
            )
            for pool in m.energy_pools
        ],
        regeneration_ports=[asdict(port) for port in m.regeneration_ports],
    )
    for row, membrane in zip(raw["model"]["membranes"], m.membranes, strict=True):
        if membrane.pump is not None:
            row["pump"]["metabolism"] = asdict(membrane.pump.metabolism)
    raw["experiment"]["regeneration_controls"] = [
        dict(regeneration_id=port.id, schedule=[asdict(c) for c in group])
        for port, group in zip(m.regeneration_ports, e.regenerations, strict=True)
    ]
    raw["execution"]["regeneration_capacity"] = spec.execution.regeneration_capacity
    return raw


def _pools(rows, cells):
    if type(rows) is not list or type(cells) is not list:
        raise ConfigError("Require explicit energy pool and cell lists")
    owners = []
    for cell in cells:
        _fields(cell, set(prior.base.Compartment.__dataclass_fields__), "cell")
        owners.append(identifier(cell["id"]))
    pools, identifiers = {}, set()
    for row in rows:
        _fields(row, set(EnergyPool.__dataclass_fields__), "energy pool")
        name, owner = identifier(row["id"]), identifier(row["cell_id"])
        if (
            row["law"] != energy.LAW_ID
            or owner not in owners
            or owner in pools
            or name in identifiers
        ):
            raise ConfigError("Energy pools require their named law and one unique owner per cell")
        pools[owner] = EnergyPool(
            name,
            owner,
            energy.LAW_ID,
            aligned(row["initial_amount_fmol"], energy.SPECIES, "energy amount", positive),
            signed_number(row["delta_g0_J_per_mol"], "pool standard energy"),
        )
        identifiers.add(name)
    if set(pools) != set(owners):
        raise ConfigError("Every cell requires exactly one finite energy pool")
    return tuple(pools[owner] for owner in owners)


def _ports(rows, pools):
    if type(rows) is not list:
        raise ConfigError("Regeneration ports require an explicit ordered list")
    names, result = set(), []
    for row in rows:
        _fields(row, set(RegenerationPort.__dataclass_fields__), "regeneration port")
        name, pool = identifier(row["id"]), identifier(row["pool_id"])
        if (
            name in names
            or pool not in {p.id for p in pools}
            or row["law"] != energy.REGENERATION_LAW_ID
        ):
            raise ConfigError("Regeneration requires unique IDs, a declared pool and its named law")
        names.add(name)
        result.append(
            RegenerationPort(
                name,
                pool,
                energy.REGENERATION_LAW_ID,
                _number(row["capacity_fmol_per_s"], "regeneration capacity"),
                _number(row["supplied_energy_J_per_mol"], "supplied energy"),
            )
        )
    return tuple(result)


def _controls(rows, ports, end):
    if type(rows) is not list:
        raise ConfigError("Regeneration controls require an explicit list")
    result = {}
    for row in rows:
        _fields(row, {"regeneration_id", "schedule"}, "regeneration control")
        name, group = identifier(row["regeneration_id"]), row["schedule"]
        if name in result or type(group) is not list or not group:
            raise ConfigError("Each regeneration port needs one nonempty schedule")
        for change in group:
            _fields(change, {"time", "availability"}, "regeneration control change")
        changes = tuple(
            ChannelChange(
                _number(c["time"], "regeneration time"),
                fraction(c["availability"], "regeneration availability"),
            )
            for c in group
        )
        if (
            changes[0].time != 0
            or any(c.time > end for c in changes)
            or any(b.time <= a.time for a, b in zip(changes, changes[1:], strict=False))
        ):
            raise ConfigError(
                "Regeneration controls must start at zero and increase within horizon"
            )
        result[name] = changes
    if set(result) != {port.id for port in ports}:
        raise ConfigError("Regeneration control IDs must exactly match ports")
    return tuple(result[port.id] for port in ports)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    raw = deepcopy(data)
    m = _fields(
        raw["model"],
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
            "energy_pools",
            "regeneration_ports",
        },
        "finite energy model",
    )
    e = _fields(
        raw["experiment"],
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "junction_controls",
            "channel_controls",
            "pump_controls",
            "regeneration_controls",
        },
        "finite energy experiment",
    )
    x = _fields(raw["execution"], set(Execution.__dataclass_fields__), "finite energy execution")
    if m["id"] not in (MODEL_ID, MORRIS_LECAR_MODEL_ID) or type(m["membranes"]) is not list:
        raise ConfigError("Require resolved_energy@1/@2 and an explicit membrane list")
    added = m["id"] == MORRIS_LECAR_MODEL_ID
    pools = _pools(m.pop("energy_pools"), m["cells"])
    ports = _ports(m.pop("regeneration_ports"), pools)
    schedules = e.pop("regeneration_controls")
    capacity = _integer(x.pop("regeneration_capacity"), "regeneration capacity", minimum=len(ports))
    by_id = {pool.id: pool for pool in pools}
    volumes = {cell["id"]: positive(cell["volume_pL"], "cell volume") for cell in m["cells"]}
    references = {}
    for membrane in m["membranes"]:
        _fields(membrane, set(prior.Membrane.__dataclass_fields__) | {"law"}, "membrane")
        if membrane["pump"] is None:
            continue
        pump = _fields(membrane["pump"], set(FinitePump.__dataclass_fields__), "finite pump")
        meta = _fields(
            pump["metabolism"], set(PoolMetabolism.__dataclass_fields__), "finite metabolism"
        )
        name = identifier(meta["pool_id"])
        if (
            meta["kind"] != METABOLISM_ID
            or name not in by_id
            or by_id[name].cell_id != membrane["inside"]
        ):
            raise ConfigError("A finite pump must reference its own inside cell's energy pool")
        pool = by_id[name]
        references[membrane["id"]] = PoolMetabolism(METABOLISM_ID, name)
        pump["metabolism"] = dict(
            kind="maintained_chemical_reservoirs@1",
            **dict(
                zip(
                    ("atp_mM", "adp_mM", "pi_mM"),
                    (a / volumes[pool.cell_id] for a in pool.initial_amount_fmol),
                    strict=True,
                )
            ),
            delta_g0_J_per_mol=pool.delta_g0_J_per_mol,
        )
    m["id"] = prior.MORRIS_LECAR_MODEL_ID if added else prior.CAV_MODEL_ID
    original = prior.parse(raw)
    if any(owner.reservoir for owner in original.model.extracellular):
        raise ConfigError("Resolved energy requires finite closed outside owners")
    b = original.model
    membranes = tuple(
        Membrane(
            **(
                vars(patch)
                | dict(
                    pump=(
                        None
                        if patch.pump is None
                        else FinitePump(
                            **(vars(patch.pump) | dict(metabolism=references[patch.id]))
                        )
                    )
                )
            )
        )
        for patch in b.membranes
    )
    names = [
        item.id
        for family in (
            b.cells,
            b.extracellular,
            b.membranes,
            b.junctions,
            b.faces,
            b.channels,
            tuple(p.pump for p in b.membranes if p.pump is not None),
            pools,
            ports,
        )
        for item in family
    ]
    if len(names) != len(set(names)):
        raise ConfigError(
            "Energy pools, ports and physical owner/route IDs must be globally unique"
        )
    spec = replace(
        original,
        model=(SurfaceEnergyMorrisLecarModel if added else SurfaceEnergyModel)(
            **(vars(b) | dict(membranes=membranes)), energy_pools=pools, regeneration_ports=ports
        ),
        experiment=Experiment(
            **vars(original.experiment),
            regenerations=_controls(
                schedules,
                ports,
                original.experiment.end_time,
            ),
        ),
        execution=Execution(**vars(original.execution), regeneration_capacity=capacity),
    )
    from cells.models import surface_energy

    try:
        surface_energy.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid resolved finite-energy definition: " + str(error)) from error
    return spec
