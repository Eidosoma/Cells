"""Finite cellular ATP shared by resolved Na/K, PMCA and owned ER pumps."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core import er_spec
from cells.core import surface_calcium_spec as prior
from cells.core import surface_energy_spec as fuel
from cells.core.specs import (
    ChannelChange,
    ConfigError,
    KineticPumpSpec,
    MaintainedMetabolismSpec,
    _fields,
    _integer,
)
from cells.processes import er_calcium, plasma_calcium
from cells.processes import finite_calcium_pumps as calcium
from cells.processes import finite_energy as energy

MODEL_ID = "resolved_calcium_energy@1"
CATALOG_MODEL_ID = "resolved_calcium_energy@2"
CALCIUM_ACTIVATED_MODEL_ID = "resolved_calcium_energy@3"
MORRIS_LECAR_MODEL_ID = "resolved_calcium_energy@4"
HCN_EXTRA_MODEL_ID = "resolved_calcium_energy@5"


@dataclass(frozen=True)
class FiniteCalciumPump:
    law: str
    capacity_fmol_per_s: float
    km_ca_mM: float
    km_atp_mM: float
    metabolism: fuel.PoolMetabolism


@dataclass(frozen=True)
class SurfaceCalciumEnergyModel(prior.SurfaceCalciumCatalogModel):
    energy_pools: tuple[fuel.EnergyPool, ...]
    regeneration_ports: tuple[fuel.RegenerationPort, ...]


@dataclass(frozen=True)
class SurfaceCalciumEnergyCatalogModel(SurfaceCalciumEnergyModel):
    """39-law catalog; the first finite-calcium identity remains 35-law."""


@dataclass(frozen=True)
class SurfaceCalciumEnergyActivatedModel(SurfaceCalciumEnergyCatalogModel):
    """Calcium-sensitive potassium coupled to the existing shared fuel owner."""


@dataclass(frozen=True)
class SurfaceCalciumEnergyMorrisLecarModel(SurfaceCalciumEnergyActivatedModel):
    """Adds thirteen Morris–Lecar laws with explicit dynamic/instantaneous state."""


@dataclass(frozen=True)
class SurfaceCalciumEnergyHCNExtraModel(SurfaceCalciumEnergyMorrisLecarModel):
    """Adds HCNLeak and the fixed HCN2/4 cAMP-shift variants."""


def model_id(model):
    if isinstance(model, SurfaceCalciumEnergyHCNExtraModel):
        return HCN_EXTRA_MODEL_ID
    if isinstance(model, SurfaceCalciumEnergyMorrisLecarModel):
        return MORRIS_LECAR_MODEL_ID
    if isinstance(model, SurfaceCalciumEnergyActivatedModel):
        return CALCIUM_ACTIVATED_MODEL_ID
    return CATALOG_MODEL_ID if isinstance(model, SurfaceCalciumEnergyCatalogModel) else MODEL_ID


@dataclass(frozen=True)
class Execution(prior.Execution):
    regeneration_capacity: int = 0


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    er_reactions: object
    er_passive: object
    er_pump: object
    er_release: object
    plasma_pump: object
    plasma_exchange: object
    calcium_channel: object
    regeneration: object


@dataclass(frozen=True)
class Change(prior.Change):
    regeneration: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    regenerations: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = (super().changes, *self.regenerations)
        clocks = [[c.time for c in group] for group in groups]
        result = []
        for time in sorted({t for clock in clocks for t in clock}):
            held = [
                group[bisect_right(clock, time) - 1]
                for group, clock in zip(groups, clocks, strict=True)
            ]
            result.append(
                Change(
                    **(vars(held[0]) | dict(time=time)),
                    regeneration=tuple(c.availability for c in held[1:]),
                )
            )
        return tuple(result)


def initial_prior_spec(spec):
    """Initial maintained-law projection for layout/serialization, never stage fuel."""
    m = spec.model
    pools = {p.id: p for p in m.energy_pools}
    volumes = {c.id: c.volume_pL for c in m.cells}

    def maintained(pump, *, kind):
        if pump is None:
            return None
        pool = pools[pump.metabolism.pool_id]
        concentrations = tuple(a / volumes[pool.cell_id] for a in pool.initial_amount_fmol)
        if kind == "nak":
            return KineticPumpSpec(
                **(
                    vars(pump)
                    | dict(
                        metabolism=MaintainedMetabolismSpec(
                            "maintained_chemical_reservoirs@1",
                            *concentrations,
                            pool.delta_g0_J_per_mol,
                        )
                    )
                )
            )
        return er_spec.ERPump(
            plasma_calcium.PUMP_LAW if kind == "pmca" else er_calcium.PUMP_LAW,
            pump.capacity_fmol_per_s,
            pump.km_ca_mM,
            pump.km_atp_mM,
            prior.METABOLISM,
            *concentrations,
            float(calcium.legacy_standard_energy(pool.delta_g0_J_per_mol, m.temperature_K, xp=np)),
        )

    model = replace(
        fuel._project(
            m,
            prior.SurfaceCalciumHCNExtraModel
            if isinstance(m, SurfaceCalciumEnergyHCNExtraModel)
            else prior.SurfaceCalciumMorrisLecarModel
            if isinstance(m, SurfaceCalciumEnergyMorrisLecarModel)
            else prior.SurfaceCalciumActivatedCatalogModel
            if isinstance(m, SurfaceCalciumEnergyActivatedModel)
            else prior.SurfaceCalciumExtendedCatalogModel
            if isinstance(m, SurfaceCalciumEnergyCatalogModel)
            else prior.SurfaceCalciumCatalogModel,
        ),
        membranes=tuple(
            prior.ionic.Membrane(**(vars(p) | dict(pump=maintained(p.pump, kind="nak"))))
            for p in m.membranes
        ),
        plasma_routes=tuple(
            replace(p, pump=maintained(p.pump, kind="pmca")) for p in m.plasma_routes
        ),
        stores=tuple(
            replace(s, membrane=replace(s.membrane, pump=maintained(s.membrane.pump, kind="er")))
            for s in m.stores
        ),
    )
    return replace(
        spec,
        model=model,
        experiment=fuel._project(spec.experiment, prior.Experiment),
        execution=fuel._project(spec.execution, prior.Execution),
    )


def to_dict(spec):
    if (
        type(spec.model)
        not in (
            SurfaceCalciumEnergyModel,
            SurfaceCalciumEnergyCatalogModel,
            SurfaceCalciumEnergyActivatedModel,
            SurfaceCalciumEnergyMorrisLecarModel,
            SurfaceCalciumEnergyHCNExtraModel,
        )
        or type(spec.experiment) is not Experiment
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Finite owned calcium requires its own model/experiment/execution")
    raw = prior.to_dict(initial_prior_spec(spec))
    m = spec.model
    raw["model"].update(
        id=model_id(m),
        energy_pools=[
            asdict(p)
            | dict(
                initial_amount_fmol=dict(zip(energy.SPECIES, p.initial_amount_fmol, strict=True))
            )
            for p in m.energy_pools
        ],
        regeneration_ports=[asdict(p) for p in m.regeneration_ports],
    )
    for row, patch in zip(raw["model"]["ionic"]["membranes"], m.membranes, strict=True):
        if patch.pump is not None:
            row["pump"]["metabolism"] = asdict(patch.pump.metabolism)
    for row, route in zip(
        raw["model"]["plasma_transport"]["membranes"], m.plasma_routes, strict=True
    ):
        row["pump"] = None if route.pump is None else asdict(route.pump)
    for row, store in zip(raw["model"]["stores"], m.stores, strict=True):
        row["model"]["membrane"]["pump"] = (
            None if store.membrane.pump is None else asdict(store.membrane.pump)
        )
    raw["experiment"]["regeneration_controls"] = [
        dict(regeneration_id=p.id, schedule=[asdict(c) for c in group])
        for p, group in zip(m.regeneration_ports, spec.experiment.regenerations, strict=True)
    ]
    raw["execution"]["regeneration_capacity"] = spec.execution.regeneration_capacity
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    raw = deepcopy(data)
    m = _fields(
        raw["model"],
        {
            "id",
            "ionic",
            "stores",
            "plasma_transport",
            "calcium_channels",
            "ip3_release",
            "energy_pools",
            "regeneration_ports",
        },
        "finite owned calcium model",
    )
    hcn_extra = m["id"] == HCN_EXTRA_MODEL_ID
    morris_lecar = hcn_extra or m["id"] == MORRIS_LECAR_MODEL_ID
    calcium_activated = morris_lecar or m["id"] == CALCIUM_ACTIVATED_MODEL_ID
    extended = calcium_activated or m["id"] == CATALOG_MODEL_ID
    if (
        m["id"]
        not in (
            MODEL_ID,
            CATALOG_MODEL_ID,
            CALCIUM_ACTIVATED_MODEL_ID,
            MORRIS_LECAR_MODEL_ID,
            HCN_EXTRA_MODEL_ID,
        )
        or type(m["ionic"]) is not dict
    ):
        raise ConfigError(
            "Require resolved_calcium_energy@1/@2/@3/@4/@5 and explicit ionic definition"
        )
    x = _fields(raw["execution"], set(Execution.__dataclass_fields__), "finite calcium execution")
    e = _fields(
        raw["experiment"],
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "junction_controls",
            "channel_controls",
            "pump_controls",
            "store_controls",
            "plasma_controls",
            "calcium_channel_controls",
            "regeneration_controls",
        },
        "finite calcium experiment",
    )
    ion = m["ionic"]
    pools = fuel._pools(m.pop("energy_pools"), ion.get("cells"))
    ports = fuel._ports(m.pop("regeneration_ports"), pools)
    schedules = e.pop("regeneration_controls")
    capacity = _integer(x.pop("regeneration_capacity"), "regeneration capacity", minimum=len(ports))
    by_id = {p.id: p for p in pools}
    volumes = {c["id"]: fuel.positive(c["volume_pL"], "cell volume") for c in ion["cells"]}
    references = {}

    def convert(pump, owner, key, kind):
        if pump is None:
            return
        _fields(
            pump,
            set(fuel.FinitePump.__dataclass_fields__)
            if kind == "nak"
            else set(FiniteCalciumPump.__dataclass_fields__),
            "finite pump",
        )
        meta = _fields(pump["metabolism"], {"kind", "pool_id"}, "finite metabolism")
        name = fuel.identifier(meta["pool_id"])
        if meta["kind"] != fuel.METABOLISM_ID or name not in by_id or by_id[name].cell_id != owner:
            raise ConfigError("Every finite pump must reference its own cytosol cell's energy pool")
        pool = by_id[name]
        concentrations = dict(
            zip(
                ("atp_mM", "adp_mM", "pi_mM"),
                (a / volumes[owner] for a in pool.initial_amount_fmol),
                strict=True,
            )
        )
        references[key] = fuel.PoolMetabolism(fuel.METABOLISM_ID, name)
        if kind == "nak":
            pump["metabolism"] = dict(
                kind="maintained_chemical_reservoirs@1",
                **concentrations,
                delta_g0_J_per_mol=pool.delta_g0_J_per_mol,
            )
        else:
            if pump["law"] != (calcium.PMCA_LAW if kind == "pmca" else calcium.ER_LAW):
                raise ConfigError("Finite calcium pumps require their explicit finite-pool law")
            pump.update(
                law=plasma_calcium.PUMP_LAW if kind == "pmca" else er_calcium.PUMP_LAW,
                metabolism=prior.METABOLISM,
                **concentrations,
                delta_g0_J_per_mol=float(
                    calcium.legacy_standard_energy(
                        pool.delta_g0_J_per_mol, ion["temperature_K"], xp=np
                    )
                ),
            )

    if type(ion.get("membranes")) is not list:
        raise ConfigError("Finite calcium requires an explicit membrane list")
    owners = {p["id"]: p["inside"] for p in ion["membranes"]}
    for p in ion["membranes"]:
        convert(p["pump"], p["inside"], ("nak", p["id"]), "nak")
    for row in prior.ordered(m["stores"], "cell_id", list(volumes), {"model"}):
        convert(row["model"]["membrane"]["pump"], row["cell_id"], ("er", row["cell_id"]), "er")
    transport = _fields(
        m["plasma_transport"],
        {"calcium_species", "sodium_species", "membranes"},
        "plasma transport",
    )
    for row in prior.ordered(
        transport["membranes"], "membrane_id", list(owners), {"pump", "exchanger"}
    ):
        convert(row["pump"], owners[row["membrane_id"]], ("pmca", row["membrane_id"]), "pmca")
    m["id"] = (
        prior.HCN_EXTRA_MODEL_ID
        if hcn_extra
        else prior.MORRIS_LECAR_MODEL_ID
        if morris_lecar
        else prior.CALCIUM_ACTIVATED_MODEL_ID
        if calcium_activated
        else prior.EXTENDED_CATALOG_MODEL_ID
        if extended
        else prior.CATALOG_MODEL_ID
    )
    original = prior.parse(raw)
    b = original.model

    def finite(pump, key, kind):
        if pump is None:
            return None
        if kind == "nak":
            return fuel.FinitePump(**(vars(pump) | dict(metabolism=references[key])))
        return FiniteCalciumPump(
            calcium.PMCA_LAW if kind == "pmca" else calcium.ER_LAW,
            pump.capacity_fmol_per_s,
            pump.km_ca_mM,
            pump.km_atp_mM,
            references[key],
        )

    occupied = {
        p.id
        for p in (
            *b.cells,
            *b.extracellular,
            *b.membranes,
            *b.junctions,
            *b.faces,
            *b.channels,
            *b.calcium_channels,
            *(p.pump for p in b.membranes if p.pump is not None),
        )
    }
    occupied |= set(b.species_ids)
    names = [p.id for p in (*pools, *ports)]
    if len(names) != len(set(names)) or occupied & set(names):
        raise ConfigError("Energy pools/ports need unique IDs distinct from physical owners/routes")
    if set(energy.SPECIES) & {s.id for store in b.stores for s in store.species}:
        raise ConfigError("ATP/ADP/Pi belong exclusively to the neutral transformed energy pools")
    spec = replace(
        original,
        model=(
            SurfaceCalciumEnergyHCNExtraModel
            if hcn_extra
            else SurfaceCalciumEnergyMorrisLecarModel
            if morris_lecar
            else SurfaceCalciumEnergyActivatedModel
            if calcium_activated
            else SurfaceCalciumEnergyCatalogModel
            if extended
            else SurfaceCalciumEnergyModel
        )(
            **(
                vars(b)
                | dict(
                    membranes=tuple(
                        fuel.Membrane(**(vars(p) | dict(pump=finite(p.pump, ("nak", p.id), "nak"))))
                        for p in b.membranes
                    ),
                    plasma_routes=tuple(
                        replace(p, pump=finite(p.pump, ("pmca", p.membrane_id), "pmca"))
                        for p in b.plasma_routes
                    ),
                    stores=tuple(
                        replace(
                            s,
                            membrane=replace(
                                s.membrane, pump=finite(s.membrane.pump, ("er", c.id), "er")
                            ),
                        )
                        for c, s in zip(b.cells, b.stores, strict=True)
                    ),
                )
            ),
            energy_pools=pools,
            regeneration_ports=ports,
        ),
        experiment=Experiment(
            **vars(original.experiment),
            regenerations=fuel._controls(schedules, ports, original.experiment.end_time),
        ),
        execution=Execution(**vars(original.execution), regeneration_capacity=capacity),
    )
    from cells.models import surface_calcium_energy

    try:
        surface_calcium_energy.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid finite owned-calcium definition: " + str(error)) from error
    return spec
