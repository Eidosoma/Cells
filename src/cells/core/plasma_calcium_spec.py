"""Explicit plasma calcium routes on the owned spatial calcium family."""

from bisect import bisect_right
from dataclasses import asdict, dataclass, fields

from cells.core import spatial_calcium_spec as base
from cells.core.bioelectric_spec import signed_number
from cells.core.er_spec import ERPump
from cells.core.multispecies_spec import identifier
from cells.core.reaction_spec import bounded
from cells.core.specs import ConfigError, SimulationSpec, _fields
from cells.processes.er_calcium import METABOLISM
from cells.processes.plasma_calcium import EXCHANGER_LAW, PUMP_LAW

MODEL_ID = "spatial_calcium@2"


@dataclass(frozen=True)
class Exchanger:
    law: str
    capacity_fmol_per_s: float
    km_na_mM: float
    km_ca_mM: float


@dataclass(frozen=True)
class PlasmaRoute:
    membrane_id: str
    pump: ERPump | None
    exchanger: Exchanger | None


@dataclass(frozen=True)
class PlasmaModel(base.CalciumModel):
    calcium_species: str
    sodium_species: str
    plasma_routes: tuple[PlasmaRoute, ...]


@dataclass(frozen=True)
class RouteChange:
    time: float
    pump: float
    exchanger: float


@dataclass(frozen=True)
class PlasmaChange(base.CalciumChange):
    plasma_pump: tuple[float, ...]
    plasma_exchange: tuple[float, ...]


@dataclass(frozen=True)
class PlasmaExperiment(base.CalciumExperiment):
    plasma: tuple[tuple[RouteChange, ...], ...]

    @property
    def changes(self):
        groups = [super().changes, *self.plasma]
        times = [[p.time for p in group] for group in groups]
        result = []
        for time in sorted({t for ts in times for t in ts}):
            held = [g[bisect_right(ts, time) - 1] for g, ts in zip(groups, times, strict=True)]
            result.append(
                PlasmaChange(
                    **(vars(held[0]) | {"time": time}),
                    plasma_pump=tuple(p.pump for p in held[1:]),
                    plasma_exchange=tuple(p.exchanger for p in held[1:]),
                )
            )
        return tuple(result)


def base_spec(spec):
    return SimulationSpec(
        base.project(spec.model, base.CalciumModel),
        base.project(spec.experiment, base.CalciumExperiment),
        spec.execution,
    )


def to_dict(spec):
    raw = base.to_dict(base_spec(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["plasma_transport"] = {
        "calcium_species": spec.model.calcium_species,
        "sodium_species": spec.model.sodium_species,
        "membranes": [asdict(p) for p in spec.model.plasma_routes],
    }
    raw["experiment"]["plasma_controls"] = [
        {"membrane_id": route.membrane_id, "schedule": [asdict(p) for p in changes]}
        for route, changes in zip(spec.model.plasma_routes, spec.experiment.plasma, strict=True)
    ]
    return raw


def parse(data, *, ionic_family=None):
    _fields(data["model"], {"id", "ionic", "stores", "plasma_transport"}, "plasma calcium model")
    if data["model"]["id"] != MODEL_ID:
        raise ConfigError("Require the explicit plasma calcium model identity")
    _fields(
        data["experiment"],
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "channel_controls",
            "junction_controls",
            "store_controls",
            "plasma_controls",
        },
        "plasma calcium experiment",
    )
    original = base.parse(
        data
        | {
            "model": {k: v for k, v in data["model"].items() if k != "plasma_transport"}
            | {"id": base.MODEL_ID},
            "experiment": {k: v for k, v in data["experiment"].items() if k != "plasma_controls"},
        },
        **({} if ionic_family is None else {"ionic_family": ionic_family}),
    )
    transport = _fields(
        data["model"]["plasma_transport"],
        {"calcium_species", "sodium_species", "membranes"},
        "plasma transport",
    )
    ca, na = (identifier(transport[k]) for k in ("calcium_species", "sodium_species"))
    ids, z = original.model.species_ids, original.model.valence
    if (
        ca == na
        or ca not in ids
        or na not in ids
        or z[ids.index(ca)] != 2
        or z[ids.index(na)] != 1
        or any(s.membrane.calcium_species != ca for s in original.model.stores)
    ):
        raise ConfigError("Plasma roles require shared ER Ca(+2) and distinct Na(+1)")
    membranes = [m.id for m in original.model.membranes]

    def owned(rows, required):
        if not isinstance(rows, list) or len(rows) != len(membranes):
            raise ConfigError("Require one plasma route/control per membrane")
        result = {}
        for row in rows:
            _fields(row, {"membrane_id", *required}, "plasma owner")
            name = row["membrane_id"]
            if not isinstance(name, str) or name not in membranes or name in result:
                raise ConfigError("Plasma owners must be distinct declared membranes")
            result[name] = row
        return [result[name] for name in membranes]

    routes = []
    for row in owned(transport["membranes"], ("pump", "exchanger")):
        p = row["pump"]
        if p is not None:
            _fields(p, {f.name for f in fields(ERPump)}, "plasma pump")
            if p["law"] != PUMP_LAW or p["metabolism"] != METABOLISM:
                raise ConfigError("Plasma pump requires its named BETSE law and mM quotient")
            drive = signed_number(p["delta_g0_J_per_mol"], "plasma hydrolysis potential")
            if abs(drive) > 100000:
                raise ConfigError("Plasma hydrolysis potential exceeds the bounded domain")
            p = ERPump(
                PUMP_LAW,
                bounded(p["capacity_fmol_per_s"], "pump capacity", 0, 1e3),
                *(bounded(p[k], k, 1e-9, 1e3) for k in ("km_ca_mM", "km_atp_mM")),
                METABOLISM,
                *(bounded(p[k], k, 1e-9, 1e3) for k in ("atp_mM", "adp_mM", "pi_mM")),
                drive,
            )
        x = row["exchanger"]
        if x is not None:
            _fields(x, {f.name for f in fields(Exchanger)}, "plasma exchanger")
            if x["law"] != EXCHANGER_LAW:
                raise ConfigError("Require the named synthetic 3-Na/1-Ca exchanger law")
            x = Exchanger(
                EXCHANGER_LAW,
                bounded(x["capacity_fmol_per_s"], "exchanger capacity", 0, 1e3),
                *(bounded(x[k], k, 1e-9, 1e3) for k in ("km_na_mM", "km_ca_mM")),
            )
        routes.append(PlasmaRoute(row["membrane_id"], p, x))
    controls = []
    for row in owned(data["experiment"]["plasma_controls"], ("schedule",)):
        schedule = row["schedule"]
        if not isinstance(schedule, list) or not schedule:
            raise ConfigError("Plasma schedules must start at zero")
        changes = []
        for p in schedule:
            _fields(p, {"time", "pump", "exchanger"}, "plasma control")
            time = bounded(p["time"], "plasma control time", 0, original.experiment.end_time)
            if (not changes and time != 0) or (changes and time <= changes[-1].time):
                raise ConfigError("Plasma control times must increase strictly from zero")
            changes.append(
                RouteChange(time, *(bounded(p[k], k, 0, 1) for k in ("pump", "exchanger")))
            )
        controls.append(tuple(changes))
    spec = SimulationSpec(
        PlasmaModel(
            **vars(original.model),
            calcium_species=ca,
            sodium_species=na,
            plasma_routes=tuple(routes),
        ),
        PlasmaExperiment(**vars(original.experiment), plasma=tuple(controls)),
        original.execution,
    )
    from cells.models.plasma_calcium import check_definition

    check_definition(spec)
    return spec
