"""Explicit resolved surfaces, held reservoirs and scheduled passive transport."""

from bisect import bisect_right
from dataclasses import asdict, dataclass

from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import aligned, identifier
from cells.core.specs import (
    ChannelChange,
    ConfigError,
    ExtracellularFaceSpec,
    FiniteCompartmentSpec,
    SimulationSpec,
    SpatialExtracellularExecutionSpec,
    _fields,
    _integer,
    _number,
)
from cells.core.voltage_gated_spec import fraction
from cells.numerics.surface_field import LAW_ID, MAX_NODES, SOLVER_ID

MODEL_ID = "resolved_tissue@1"


@dataclass(frozen=True)
class Compartment(FiniteCompartmentSpec):
    initial_charge_C: float


@dataclass(frozen=True)
class Outside(Compartment):
    reservoir: bool
    boundary_potential_V: float


@dataclass(frozen=True)
class Membrane:
    id: str
    inside: str
    outside: str
    area_m2: float
    capacitance_F: float
    permeability_m_per_s: tuple[float, ...]


@dataclass(frozen=True)
class Junction:
    id: str
    sender: str
    receiver: str
    area_m2: float
    permeability_m_per_s: tuple[float, ...]


@dataclass(frozen=True)
class SurfaceTissueModel:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple[Compartment, ...]
    extracellular: tuple[Outside, ...]
    membranes: tuple[Membrane, ...]
    junctions: tuple[Junction, ...]
    faces: tuple[ExtracellularFaceSpec, ...]
    gauge_reference: str | None


@dataclass(frozen=True)
class SurfaceChange:
    time: float
    membrane: tuple[float, ...]
    junction: tuple[float, ...]


@dataclass(frozen=True)
class SurfaceExperiment:
    end_time: float
    observation_times: tuple[float, ...]
    membranes: tuple[tuple[ChannelChange, ...], ...]
    junctions: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = self.membranes + self.junctions
        clocks = [[p.time for p in g] for g in groups]
        result = []
        for time in sorted({0.0, *(t for clock in clocks for t in clock)}):
            held = tuple(
                g[bisect_right(clock, time) - 1].availability
                for g, clock in zip(groups, clocks, strict=True)
            )
            result.append(
                SurfaceChange(time, held[: len(self.membranes)], held[len(self.membranes) :])
            )
        return tuple(result)


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if type(e) is not SurfaceExperiment or type(x) is not SpatialExtracellularExecutionSpec:
        raise ConfigError("Resolved tissue requires its own experiment and spatial execution")

    def mapped(v):
        if type(v) is not tuple or len(v) != len(m.species_ids):
            raise ConfigError("Resolved species vectors require complete immutable tuples")
        return dict(zip(m.species_ids, v, strict=True))

    raw = {"id": MODEL_ID, "temperature_K": m.temperature_K}
    raw["species"] = [
        {"id": s, "valence": z} for s, z in zip(m.species_ids, m.valence, strict=True)
    ]
    for key in ("cells", "extracellular", "membranes", "junctions", "faces"):
        rows = []
        for p in getattr(m, key):
            row = asdict(p)
            for name in ("initial_amount_fmol", "permeability_m_per_s", "diffusivity_m2_per_s"):
                if name in row:
                    row[name] = mapped(row[name])
            if key in ("membranes", "junctions", "faces"):
                row["law"] = "logmean_electrodiffusion@1" if key == "faces" else "constant_field@1"
            rows.append(row)
        raw[key] = rows
    raw["closure"] = {"law": LAW_ID, "gauge_reference": m.gauge_reference}
    experiment = {"end_time": e.end_time, "observation_times": list(e.observation_times)}
    for family in ("membrane", "junction"):
        experiment[family + "_controls"] = [
            {family + "_id": p.id, "schedule": [asdict(c) for c in group]}
            for p, group in zip(getattr(m, family + "s"), getattr(e, family + "s"), strict=True)
        ]
    return {
        "schema_version": 1,
        "model": raw,
        "experiment": experiment,
        "execution": asdict(x)
        | {"material_balance_atol_fmol": mapped(x.material_balance_atol_fmol)},
    }


def parse(data):
    m = _fields(
        data["model"],
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
        },
        "resolved tissue model",
    )
    if m["id"] != MODEL_ID or type(m["species"]) is not list or not m["species"]:
        raise ConfigError("Require resolved_tissue@1 and an ordered species list")
    species = [_fields(p, {"id", "valence"}, "species") for p in m["species"]]
    ids = tuple(identifier(p["id"]) for p in species)
    z = tuple(p["valence"] for p in species)
    if len(set(ids)) != len(ids) or any(type(v) is not int or abs(v) > 8 for v in z):
        raise ConfigError("Species require unique IDs and integer valences in [-8,8]")
    for key in ("cells", "extracellular", "membranes", "junctions", "faces"):
        if type(m[key]) is not list:
            raise ConfigError(key + " must be an explicit list")

    def compartment(p, cls):
        _fields(p, set(cls.__dataclass_fields__), "compartment")
        values = dict(
            id=identifier(p["id"]),
            volume_pL=positive(p["volume_pL"], "volume"),
            initial_amount_fmol=aligned(p["initial_amount_fmol"], ids, "amount", positive),
            fixed_charge_equivalent_fmol=signed_number(
                p["fixed_charge_equivalent_fmol"], "fixed charge"
            ),
            initial_charge_C=signed_number(p["initial_charge_C"], "charge anchor"),
        )
        if cls is Outside:
            if type(p["reservoir"]) is not bool:
                raise ConfigError("Reservoir ownership must be explicitly boolean")
            values.update(
                reservoir=p["reservoir"],
                boundary_potential_V=signed_number(
                    p["boundary_potential_V"], "held boundary potential"
                ),
            )
        return cls(**values)

    cells = tuple(compartment(p, Compartment) for p in m["cells"])
    outside = tuple(compartment(p, Outside) for p in m["extracellular"])
    if not cells or not outside or len(cells) + len(outside) > MAX_NODES:
        raise ConfigError("Resolved tissue requires cells/outside within the dense node bound")
    cids, oids = {p.id for p in cells}, {p.id for p in outside}
    routes = {}
    for key, cls in (
        ("membranes", Membrane),
        ("junctions", Junction),
        ("faces", ExtracellularFaceSpec),
    ):
        rows = []
        for p in m[key]:
            _fields(p, set(cls.__dataclass_fields__) | {"law"}, key)
            law = "logmean_electrodiffusion@1" if key == "faces" else "constant_field@1"
            if p["law"] != law:
                raise ConfigError("Unsupported resolved transport law")
            a, b = ("inside", "outside") if key == "membranes" else ("sender", "receiver")
            allowed_a, allowed_b = (
                (cids, oids)
                if key == "membranes"
                else ((oids, oids) if key == "faces" else (cids, cids))
            )
            if p[a] not in allowed_a or p[b] not in allowed_b:
                raise ConfigError("Transport requires identified physical owners")
            values = {k: identifier(p[k]) for k in ("id", a, b)}
            values["area_m2"] = positive(p["area_m2"], "route area")
            if key == "faces":
                values["length_m"] = positive(p["length_m"], "face length")
                values["diffusivity_m2_per_s"] = aligned(
                    p["diffusivity_m2_per_s"], ids, "diffusivity"
                )
            else:
                values["permeability_m_per_s"] = aligned(
                    p["permeability_m_per_s"], ids, "permeability"
                )
                if key == "membranes":
                    values["capacitance_F"] = positive(p["capacitance_F"], "capacitance")
            rows.append(cls(**values))
        routes[key] = tuple(rows)
    names = [
        p.id
        for p in (*cells, *outside, *routes["membranes"], *routes["junctions"], *routes["faces"])
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Physical owner and route IDs must be globally unique")
    closure = _fields(m["closure"], {"law", "gauge_reference"}, "closure")
    gauge = closure["gauge_reference"]
    if closure["law"] != LAW_ID or (
        gauge is not None and (type(gauge) is not str or gauge not in oids)
    ):
        raise ConfigError("Require the resolved charge/current closure and declared gauge")
    if (any(p.reservoir for p in outside) and gauge is not None) or (
        not any(p.reservoir for p in outside) and gauge is None
    ):
        raise ConfigError("Use held reservoirs or exactly one outside gauge")
    if any(p.boundary_potential_V != 0 and not (p.reservoir or p.id == gauge) for p in outside):
        raise ConfigError("Only reservoirs or the gauge may impose boundary potentials")
    model = SurfaceTissueModel(
        ids,
        z,
        positive(m["temperature_K"], "temperature"),
        cells,
        outside,
        routes["membranes"],
        routes["junctions"],
        routes["faces"],
        gauge,
    )
    e = _fields(
        data["experiment"],
        {"end_time", "observation_times", "membrane_controls", "junction_controls"},
        "experiment",
    )
    end = positive(e["end_time"], "end time")
    if type(e["observation_times"]) is not list or not e["observation_times"]:
        raise ConfigError("Require a nonempty observation list")
    times = tuple(_number(t, "observation time") for t in e["observation_times"])
    if any(t > end for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observations must increase within the horizon")
    schedules = {}
    for family in ("membrane", "junction"):
        groups = e[family + "_controls"]
        if type(groups) is not list:
            raise ConfigError("Require explicit identified control lists")
        parsed = {}
        for group in groups:
            _fields(group, {family + "_id", "schedule"}, "control")
            name, changes = identifier(group[family + "_id"]), group["schedule"]
            if name in parsed or type(changes) is not list or not changes:
                raise ConfigError("Each route needs one nonempty control schedule")
            for c in changes:
                _fields(c, {"time", "availability"}, "control change")
            values = tuple(
                ChannelChange(
                    _number(c["time"], "control time"), fraction(c["availability"], "availability")
                )
                for c in changes
            )
            if (
                values[0].time != 0
                or any(v.time > end for v in values)
                or any(b.time <= a.time for a, b in zip(values, values[1:], strict=False))
            ):
                raise ConfigError("Controls must start at zero and increase within the horizon")
            parsed[name] = values
        if set(parsed) != {p.id for p in routes[family + "s"]}:
            raise ConfigError("Control IDs must exactly match transport routes")
        schedules[family + "s"] = tuple(parsed[p.id] for p in routes[family + "s"])
    x = _fields(
        data["execution"], set(SpatialExtracellularExecutionSpec.__dataclass_fields__), "execution"
    )
    if (
        x["backend"] not in ("cpu", "gpu")
        or x["precision"] != "float64"
        or x["solver"] != "rk4"
        or x["field_solver"] != SOLVER_ID
        or type(x["jit"]) is not bool
    ):
        raise ConfigError(
            "Resolved tissue requires float64 CPU/GPU RK4 and its declared field solver"
        )
    sizes = {
        "capacity": len(cells),
        "extracellular_capacity": len(outside),
        "membrane_capacity": len(routes["membranes"]),
        "edge_capacity": len(routes["junctions"]),
        "face_capacity": len(routes["faces"]),
    }
    capacities = {k: _integer(x[k], k, minimum=v) for k, v in sizes.items()}
    if capacities["capacity"] + capacities["extracellular_capacity"] > MAX_NODES:
        raise ConfigError("Padded capacities exceed the bounded dense solver")
    tolerance = aligned(x["material_balance_atol_fmol"], ids, "material tolerance", positive)
    if any(v > 1e-10 for v in tolerance):
        raise ConfigError("Material tolerance cannot exceed 1e-10 fmol")
    execution = SpatialExtracellularExecutionSpec(
        dt=positive(x["dt"], "dt"),
        jit=x["jit"],
        backend=x["backend"],
        max_steps=_integer(x["max_steps"], "max_steps"),
        max_trace_bytes=_integer(x["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1),
        material_balance_atol_fmol=tolerance,
        field_solver=SOLVER_ID,
        **capacities,
    )
    spec = SimulationSpec(model, SurfaceExperiment(end, times, **schedules), execution)
    from cells.models.surface_tissue import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved tissue definition: " + str(error)) from error
    return spec
