"""Finite resolved tissue with one chemical cytosol/ER owner per cell."""

from bisect import bisect_right
from dataclasses import asdict, dataclass

from cells.core import er_spec
from cells.core import surface_kinetic_spec as ionic
from cells.core.bioelectric_spec import signed_number
from cells.core.ip3_calcium_spec import IP3Release
from cells.core.multispecies_spec import identifier
from cells.core.plasma_calcium_spec import Exchanger, PlasmaRoute, RouteChange
from cells.core.reaction_spec import bounded
from cells.core.spatial_calcium_spec import project, store_spec
from cells.core.specs import (
    ChannelChange,
    ChannelSpec,
    ConfigError,
    SimulationSpec,
    _fields,
    _integer,
)
from cells.processes import calcium_gates, ip3_release, plasma_calcium
from cells.processes.er_calcium import METABOLISM

MODEL_ID = "resolved_calcium@1"
CHANNEL_MODEL_ID = "resolved_calcium@2"
SODIUM_MODEL_ID = "resolved_calcium@3"
HCN_MODEL_ID = "resolved_calcium@4"
KV1_MODEL_ID = "resolved_calcium@5"
CAV_MODEL_ID = "resolved_calcium@6"
CATALOG_MODEL_ID = "resolved_calcium@7"
EXTENDED_CATALOG_MODEL_ID = "resolved_calcium@8"
CALCIUM_ACTIVATED_MODEL_ID = "resolved_calcium@9"
MORRIS_LECAR_MODEL_ID = "resolved_calcium@10"
HCN_EXTRA_MODEL_ID = "resolved_calcium@11"


@dataclass(frozen=True)
class SurfaceCalciumModel(ionic.SurfaceKineticModel):
    stores: tuple[er_spec.ERModel, ...]
    calcium_species: str
    sodium_species: str
    plasma_routes: tuple[PlasmaRoute, ...]
    calcium_channels: tuple[ChannelSpec, ...]
    ip3_release: tuple[IP3Release, ...]


@dataclass(frozen=True)
class SurfaceCalciumChannelModel(SurfaceCalciumModel):
    """Explicit composition of owned calcium stores and named potassium laws."""


@dataclass(frozen=True)
class SurfaceCalciumSodiumModel(SurfaceCalciumChannelModel):
    """Owned calcium stores with the explicit sodium/potassium channel catalog."""


@dataclass(frozen=True)
class SurfaceCalciumHCNModel(SurfaceCalciumSodiumModel):
    """Owned calcium stores with shared multi-ion channel populations."""

    channels: tuple[ionic.ChannelPopulation, ...]


@dataclass(frozen=True)
class SurfaceCalciumKv1Model(SurfaceCalciumHCNModel):
    """Owned calcium stores and the complete pinned Kv1 population catalog."""


@dataclass(frozen=True)
class SurfaceCalciumCavModel(SurfaceCalciumKv1Model):
    """Shared calcium-channel populations with one owned free cytosol/ER."""


@dataclass(frozen=True)
class SurfaceCalciumCatalogModel(SurfaceCalciumCavModel):
    """Expanded Na/K/leak populations sharing existing free cytosol/ER owners."""


@dataclass(frozen=True)
class SurfaceCalciumExtendedCatalogModel(SurfaceCalciumCatalogModel):
    """39 shared laws with one existing free chemical cytosol/ER owner."""


@dataclass(frozen=True)
class SurfaceCalciumActivatedCatalogModel(SurfaceCalciumExtendedCatalogModel):
    """Instantaneous potassium populations sense the existing free Ca owner."""


@dataclass(frozen=True)
class SurfaceCalciumMorrisLecarModel(SurfaceCalciumActivatedCatalogModel):
    """Adds thirteen Morris–Lecar laws with explicit dynamic/instantaneous state."""


@dataclass(frozen=True)
class SurfaceCalciumHCNExtraModel(SurfaceCalciumMorrisLecarModel):
    """Adds HCNLeak and the fixed HCN2/4 cAMP-shift variants."""


def model_id(model):
    if isinstance(model, SurfaceCalciumHCNExtraModel):
        return HCN_EXTRA_MODEL_ID
    if isinstance(model, SurfaceCalciumMorrisLecarModel):
        return MORRIS_LECAR_MODEL_ID
    if isinstance(model, SurfaceCalciumActivatedCatalogModel):
        return CALCIUM_ACTIVATED_MODEL_ID
    if isinstance(model, SurfaceCalciumExtendedCatalogModel):
        return EXTENDED_CATALOG_MODEL_ID
    if isinstance(model, SurfaceCalciumCatalogModel):
        return CATALOG_MODEL_ID
    if isinstance(model, SurfaceCalciumCavModel):
        return CAV_MODEL_ID
    if isinstance(model, SurfaceCalciumKv1Model):
        return KV1_MODEL_ID
    if isinstance(model, SurfaceCalciumHCNModel):
        return HCN_MODEL_ID
    if isinstance(model, SurfaceCalciumSodiumModel):
        return SODIUM_MODEL_ID
    return CHANNEL_MODEL_ID if isinstance(model, SurfaceCalciumChannelModel) else MODEL_ID


@dataclass(frozen=True)
class Execution(ionic.Execution):
    chemical_capacity: int = 2
    reaction_capacity: int = 0


@dataclass(frozen=True)
class Change(ionic.Change):
    stores: tuple[er_spec.ERChange, ...]
    plasma_pump: tuple[float, ...]
    plasma_exchange: tuple[float, ...]
    calcium_channel: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(ionic.Experiment):
    stores: tuple[er_spec.ERExperiment, ...]
    plasma: tuple[tuple[RouteChange, ...], ...]
    calcium_channel: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        n, m = len(self.stores), len(self.plasma)
        groups = [
            super().changes,
            *(s.changes for s in self.stores),
            *self.plasma,
            *self.calcium_channel,
        ]
        clocks = [[p.time for p in g] for g in groups]
        result = []
        for time in sorted({t for clock in clocks for t in clock}):
            held = [
                g[bisect_right(clock, time) - 1] for g, clock in zip(groups, clocks, strict=True)
            ]
            result.append(
                Change(
                    **(vars(held[0]) | {"time": time}),
                    stores=tuple(held[1 : 1 + n]),
                    plasma_pump=tuple(c.pump for c in held[1 + n : 1 + n + m]),
                    plasma_exchange=tuple(c.exchanger for c in held[1 + n : 1 + n + m]),
                    calcium_channel=tuple(c.availability for c in held[1 + n + m :]),
                )
            )
        return tuple(result)


def ionic_spec(spec):
    return SimulationSpec(
        project(
            spec.model,
            ionic.SurfaceHCNExtraModel
            if isinstance(spec.model, SurfaceCalciumHCNExtraModel)
            else ionic.SurfaceMorrisLecarModel
            if isinstance(spec.model, SurfaceCalciumMorrisLecarModel)
            else ionic.SurfaceCalciumActivatedModel
            if isinstance(spec.model, SurfaceCalciumActivatedCatalogModel)
            else ionic.SurfaceExtendedCatalogModel
            if isinstance(spec.model, SurfaceCalciumExtendedCatalogModel)
            else ionic.SurfaceCatalogModel
            if isinstance(spec.model, SurfaceCalciumCatalogModel)
            else ionic.SurfaceCavModel
            if isinstance(spec.model, SurfaceCalciumCavModel)
            else ionic.SurfaceKv1Model
            if isinstance(spec.model, SurfaceCalciumKv1Model)
            else ionic.SurfaceHCNModel
            if isinstance(spec.model, SurfaceCalciumHCNModel)
            else ionic.SurfaceSodiumModel
            if isinstance(spec.model, SurfaceCalciumSodiumModel)
            else ionic.SurfaceChannelModel
            if isinstance(spec.model, SurfaceCalciumChannelModel)
            else ionic.SurfaceKineticModel,
        ),
        project(spec.experiment, ionic.Experiment),
        project(spec.execution, ionic.Execution),
    )


def to_dict(spec):
    if type(spec.experiment) is not Experiment or type(spec.execution) is not Execution:
        raise ConfigError("Resolved calcium requires its explicit experiment/execution")
    raw = ionic.to_dict(ionic_spec(spec))
    m, e = spec.model, spec.experiment
    raw["model"] = dict(
        id=model_id(m),
        ionic=raw["model"],
        stores=[],
        plasma_transport=dict(
            calcium_species=m.calcium_species,
            sodium_species=m.sodium_species,
            membranes=[asdict(p) for p in m.plasma_routes],
        ),
        calcium_channels=[
            asdict(c) | {"initial_gate": dict(zip(("m", "h"), c.initial_gate, strict=True))}
            for c in m.calcium_channels
        ],
        ip3_release=[asdict(p) for p in m.ip3_release],
    )
    raw["experiment"]["store_controls"] = []
    for i, cell in enumerate(m.cells):
        store = er_spec.to_dict(store_spec(spec, i))
        raw["model"]["stores"].append(dict(cell_id=cell.id, model=store["model"]))
        raw["experiment"]["store_controls"].append(
            dict(cell_id=cell.id, controls=store["experiment"]["controls"])
        )
    raw["experiment"]["plasma_controls"] = [
        dict(membrane_id=p.membrane_id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.plasma_routes, e.plasma, strict=True)
    ]
    raw["experiment"]["calcium_channel_controls"] = [
        dict(channel_id=p.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.calcium_channels, e.calcium_channel, strict=True)
    ]
    raw["execution"].update(
        chemical_capacity=spec.execution.chemical_capacity,
        reaction_capacity=spec.execution.reaction_capacity,
    )
    return raw


def ordered(rows, owner_key, names, required):
    if type(rows) is not list or len(rows) != len(names):
        raise ConfigError("Require exactly one declared entry per " + owner_key)
    result = {}
    for row in rows:
        _fields(row, {owner_key, *required}, "owned resolved calcium entry")
        name = identifier(row[owner_key])
        if name not in names or name in result:
            raise ConfigError("Calcium owners must be distinct and declared")
        result[name] = row
    return [result[name] for name in names]


@dataclass(frozen=True)
class _OwnedDeclarations:
    """Decoded ownership only; neither an admitted nor executable simulation."""

    model: object
    experiment: object
    execution: object


def _require_finite_exterior(ion):
    if any(c.reservoir for c in ion.model.extracellular):
        raise ConfigError(
            "Resolved calcium requires finite outside inventories for conserved-pool loss bounds"
        )


def _decode_components(data, *, exterior_check=None):
    """Decode all actual component/ownership inputs, without tissue admission.

    The closed public parser supplies its existing exterior check at the same
    point as before. A separate open family must perform its own complete
    physical/domain/step admission; these declarations carry no such promise.
    """
    m = _fields(
        data["model"],
        {"id", "ionic", "stores", "plasma_transport", "calcium_channels", "ip3_release"},
        "resolved calcium model",
    )
    e = _fields(
        data["experiment"],
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
        },
        "resolved calcium experiment",
    )
    x = _fields(
        data["execution"], set(Execution.__dataclass_fields__), "resolved calcium execution"
    )
    hcn_extra = m["id"] == HCN_EXTRA_MODEL_ID
    morris_lecar = hcn_extra or m["id"] == MORRIS_LECAR_MODEL_ID
    calcium_activated = morris_lecar or m["id"] == CALCIUM_ACTIVATED_MODEL_ID
    extended = calcium_activated or m["id"] == EXTENDED_CATALOG_MODEL_ID
    expanded = extended or m["id"] == CATALOG_MODEL_ID
    cav = expanded or m["id"] == CAV_MODEL_ID
    kv1 = cav or m["id"] == KV1_MODEL_ID
    hcn = kv1 or m["id"] == HCN_MODEL_ID
    sodium = hcn or m["id"] == SODIUM_MODEL_ID
    mixed = sodium or m["id"] == CHANNEL_MODEL_ID
    ionic_id = (
        ionic.HCN_EXTRA_MODEL_ID
        if hcn_extra
        else ionic.MORRIS_LECAR_MODEL_ID
        if morris_lecar
        else ionic.CALCIUM_ACTIVATED_MODEL_ID
        if calcium_activated
        else ionic.EXTENDED_CATALOG_MODEL_ID
        if extended
        else ionic.CATALOG_MODEL_ID
        if expanded
        else ionic.CAV_MODEL_ID
        if cav
        else ionic.KV1_MODEL_ID
        if kv1
        else ionic.HCN_MODEL_ID
        if hcn
        else ionic.SODIUM_MODEL_ID
        if sodium
        else ionic.CHANNEL_MODEL_ID
        if mixed
        else ionic.MODEL_ID
    )
    if (
        m["id"]
        not in (
            MODEL_ID,
            CHANNEL_MODEL_ID,
            SODIUM_MODEL_ID,
            HCN_MODEL_ID,
            KV1_MODEL_ID,
            CAV_MODEL_ID,
            CATALOG_MODEL_ID,
            EXTENDED_CATALOG_MODEL_ID,
            CALCIUM_ACTIVATED_MODEL_ID,
            MORRIS_LECAR_MODEL_ID,
            HCN_EXTRA_MODEL_ID,
        )
        or not isinstance(m["ionic"], dict)
        or m["ionic"].get("id") != ionic_id
    ):
        raise ConfigError("Resolved calcium requires matching ionic ownership: " + ionic_id)
    ion = ionic.parse(
        dict(
            schema_version=1,
            model=m["ionic"],
            experiment={
                k: v
                for k, v in e.items()
                if k not in ("store_controls", "plasma_controls", "calcium_channel_controls")
            },
            execution={k: x[k] for k in ionic.Execution.__dataclass_fields__},
        )
    )
    if exterior_check is not None:
        exterior_check(ion)
    cells, membranes = [c.id for c in ion.model.cells], [p.id for p in ion.model.membranes]
    if not 1 <= len(cells) <= 16:
        raise ConfigError("Resolved calcium supports 1–16 owned stores per world")
    capacity = _integer(x["chemical_capacity"], "chemical capacity", maximum=64)
    reactions = _integer(x["reaction_capacity"], "reaction capacity", minimum=0, maximum=1024)
    stores, experiments = [], []
    for cell, row, control in zip(
        ion.model.cells,
        ordered(m["stores"], "cell_id", cells, {"model"}),
        ordered(e["store_controls"], "cell_id", cells, {"controls"}),
        strict=True,
    ):
        store = er_spec.parse(
            dict(
                model=row["model"],
                experiment=dict(
                    end_time=e["end_time"],
                    observation_times=e["observation_times"],
                    controls=control["controls"],
                ),
                execution={
                    k: x[k]
                    for k in (
                        "backend",
                        "precision",
                        "solver",
                        "dt",
                        "jit",
                        "max_steps",
                        "max_trace_bytes",
                    )
                }
                | dict(capacity=capacity, reaction_capacity=reactions),
            )
        )
        sm = store.model
        names = [s.id for s in sm.species]
        if (
            sm.temperature_K != ion.model.temperature_K
            or sm.standard_concentration_mM != 1
            or not set(ion.model.species_ids) <= set(sm.moieties) & set(names)
        ):
            raise ConfigError(
                "Stores require matching ionic species/moieties, temperature "
                "and 1 mM standard state"
            )
        cy = next(c for c in sm.compartments if c.id == sm.membrane.cytosol)
        if cy.volume_pL != cell.volume_pL:
            raise ConfigError("Ionic and chemical cytosol must share one physical volume")
        for j, name in enumerate(ion.model.species_ids):
            s = sm.species[names.index(name)]
            if (
                s.moieties != tuple(int(k == name) for k in sm.moieties)
                or s.valence != ion.model.valence[j]
                or s.standard_mu_RT != 0
                or cy.initial_amount_fmol[names.index(name)] != cell.initial_amount_fmol[j]
            ):
                raise ConfigError(
                    "Free ionic and chemical species must share identity and initial amounts"
                )
        if stores and (sm.species, sm.moieties) != (stores[0].species, stores[0].moieties):
            raise ConfigError("Owned stores require the same chemical species/moiety table")
        stores.append(sm)
        experiments.append(store.experiment)
    transport = _fields(
        m["plasma_transport"],
        {"calcium_species", "sodium_species", "membranes"},
        "plasma transport",
    )
    ca, na = (identifier(transport[k]) for k in ("calcium_species", "sodium_species"))
    ids, z = ion.model.species_ids, ion.model.valence
    if (
        ca == na
        or ca not in ids
        or na not in ids
        or z[ids.index(ca)] != 2
        or z[ids.index(na)] != 1
        or any(s.membrane.calcium_species != ca for s in stores)
    ):
        raise ConfigError("Plasma roles require shared ER Ca(+2) and distinct Na(+1)")
    routes = []
    for row in ordered(transport["membranes"], "membrane_id", membranes, {"pump", "exchanger"}):
        p, ex = row["pump"], row["exchanger"]
        if p is not None:
            _fields(p, set(er_spec.ERPump.__dataclass_fields__), "plasma pump")
            if p["law"] != plasma_calcium.PUMP_LAW or p["metabolism"] != METABOLISM:
                raise ConfigError("PMCA requires its named law and maintained numeric-mM quotient")
            dg = signed_number(p["delta_g0_J_per_mol"], "PMCA hydrolysis")
            if abs(dg) > 100000:
                raise ConfigError("PMCA hydrolysis potential exceeds the bounded domain")
            p = er_spec.ERPump(
                plasma_calcium.PUMP_LAW,
                bounded(p["capacity_fmol_per_s"], "PMCA capacity", 0, 1e3),
                *(bounded(p[k], k, 1e-9, 1e3) for k in ("km_ca_mM", "km_atp_mM")),
                METABOLISM,
                *(bounded(p[k], k, 1e-9, 1e3) for k in ("atp_mM", "adp_mM", "pi_mM")),
                dg,
            )
        if ex is not None:
            _fields(ex, set(Exchanger.__dataclass_fields__), "exchanger")
            if ex["law"] != plasma_calcium.EXCHANGER_LAW:
                raise ConfigError("Require the named synthetic 3-Na/1-Ca exchanger")
            ex = Exchanger(
                plasma_calcium.EXCHANGER_LAW,
                bounded(ex["capacity_fmol_per_s"], "NCX capacity", 0, 1e3),
                *(bounded(ex[k], k, 1e-9, 1e3) for k in ("km_na_mM", "km_ca_mM")),
            )
        routes.append(PlasmaRoute(row["membrane_id"], p, ex))

    def schedule(values, kind):
        if type(values) is not list or not values:
            raise ConfigError("Calcium schedules must start at zero")
        result = []
        names = ("pump", "exchanger") if kind is RouteChange else ("availability",)
        for value in values:
            _fields(value, {"time", *names}, "calcium control")
            t = bounded(value["time"], "control time", 0, ion.experiment.end_time)
            if (not result and t != 0) or (result and t <= result[-1].time):
                raise ConfigError("Calcium control times must increase from zero")
            result.append(kind(t, *(bounded(value[k], k, 0, 1) for k in names)))
        return tuple(result)

    plasma = tuple(
        schedule(row["schedule"], RouteChange)
        for row in ordered(e["plasma_controls"], "membrane_id", membranes, {"schedule"})
    )
    occupied = {
        p.id
        for p in (
            *ion.model.cells,
            *ion.model.extracellular,
            *ion.model.membranes,
            *ion.model.junctions,
            *ion.model.faces,
            *ion.model.channels,
            *(p.pump for p in ion.model.membranes if p.pump is not None),
        )
    } | set(ids)
    channels = []
    for row in ordered(
        m["calcium_channels"],
        "membrane_id",
        membranes,
        set(ChannelSpec.__dataclass_fields__) - {"membrane_id"},
    ):
        name = identifier(row["id"])
        g = _fields(row["initial_gate"], {"m", "h"}, "Cav1.2 initial gates")
        if (
            name in occupied
            or row["species_id"] != ca
            or row["kinetic_law"] != calcium_gates.LAW_ID
        ):
            raise ConfigError("Cav1.2 needs a unique ID, declared Ca and its named law")
        occupied.add(name)
        channels.append(
            ChannelSpec(
                name,
                row["membrane_id"],
                ca,
                calcium_gates.LAW_ID,
                bounded(row["max_permeability_m_per_s"], "Cav permeability", 0, 1e-3),
                bounded(row["abundance"], "Cav abundance", 0, 1e6),
                tuple(bounded(g[k], k, 0, 1) for k in ("m", "h")),
            )
        )
    calcium_control = tuple(
        schedule(row["schedule"], ChannelChange)
        for row in ordered(
            e["calcium_channel_controls"], "channel_id", [c.id for c in channels], {"schedule"}
        )
    )
    bindings = []
    for i, row in enumerate(
        ordered(
            m["ip3_release"], "cell_id", cells, set(IP3Release.__dataclass_fields__) - {"cell_id"}
        )
    ):
        sm = stores[i]
        names = [s.id for s in sm.species]
        if (
            row["law"] != ip3_release.LAW_ID
            or row["species_id"] != "IP3"
            or "IP3" not in names
            or "IP3" not in sm.moieties
            or sm.membrane.release is None
        ):
            raise ConfigError(
                "IP3 release requires a finite free IP3 species/moiety and explicit ER release"
            )
        if sm.species[names.index("IP3")].moieties != tuple(int(k == "IP3") for k in sm.moieties):
            raise ConfigError("IP3 release must read free ligand, not a bound complex")
        bindings.append(
            IP3Release(
                cells[i],
                "IP3",
                ip3_release.LAW_ID,
                bounded(row["activation_mM"], "IP3 activation", 1e-12, 1e6),
                _integer(row["activation_n"], "IP3 power", maximum=8),
            )
        )
    return _OwnedDeclarations(
        (
            SurfaceCalciumHCNExtraModel
            if hcn_extra
            else SurfaceCalciumMorrisLecarModel
            if morris_lecar
            else SurfaceCalciumActivatedCatalogModel
            if calcium_activated
            else SurfaceCalciumExtendedCatalogModel
            if extended
            else SurfaceCalciumCatalogModel
            if expanded
            else SurfaceCalciumCavModel
            if cav
            else SurfaceCalciumKv1Model
            if kv1
            else SurfaceCalciumHCNModel
            if hcn
            else SurfaceCalciumSodiumModel
            if sodium
            else SurfaceCalciumChannelModel
            if mixed
            else SurfaceCalciumModel
        )(
            **vars(ion.model),
            stores=tuple(stores),
            calcium_species=ca,
            sodium_species=na,
            plasma_routes=tuple(routes),
            calcium_channels=tuple(channels),
            ip3_release=tuple(bindings),
        ),
        Experiment(
            **vars(ion.experiment),
            stores=tuple(experiments),
            plasma=plasma,
            calcium_channel=calcium_control,
        ),
        Execution(**vars(ion.execution), chemical_capacity=capacity, reaction_capacity=reactions),
    )


def parse(data):
    declared = _decode_components(data, exterior_check=_require_finite_exterior)
    spec = SimulationSpec(declared.model, declared.experiment, declared.execution)
    from cells.models.surface_calcium import check_definition

    check_definition(spec)
    return spec
