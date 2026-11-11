"""apical_vertex_mechanics@1: definition of a periodic 2-D apical vertex tissue.

The model is a periodic tiling of polygonal cells: vertices with positions and
friction, junctions (edges between two vertices, with the integer periodic image
of the head relative to the tail and a line tension), and cells given as
counterclockwise corner lists (vertex plus integer image), with area elasticity,
preferred area and contractility. Topology is fixed: no T1, T2, division or
extrusion. Units are reduced (lengths sqrt(A0), energies K A0^2, time
eta / (K A0)); physical units are a later version.

The experiment holds parameter_controls: right-continuous overrides of junction
line tensions and cell parameters, starting at time zero. Each control lists the
complete set of overrides in effect from its time (unlisted entries take the
model's values); this is how an ablation is scheduled (D136).

The execution declares the solver (rk4 or euler) and four capacities: cells
(capacity), vertices, junctions and half-edges (one per cell corner).
"""

import copy
from dataclasses import asdict, dataclass, fields

import numpy as np

from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, ExecutionSpec, SimulationSpec, _fields, _integer, _number

MODEL_ID = "apical_vertex_mechanics@1"
UNITS = "reduced"
SOLVERS = ("rk4", "euler")
MAX_IMAGE = 2**20
PARAMETER_KINDS = ("line_tension", "contractility", "area_elasticity", "preferred_area")


@dataclass(frozen=True)
class Vertex:
    id: str
    position: tuple[float, float]
    friction: float


@dataclass(frozen=True)
class Corner:
    vertex: str
    image: tuple[int, int]


@dataclass(frozen=True)
class Junction:
    id: str
    vertices: tuple[str, str]
    image: tuple[int, int]
    line_tension: float


@dataclass(frozen=True)
class Cell:
    id: str
    corners: tuple[Corner, ...]
    area_elasticity: float
    preferred_area: float
    contractility: float


@dataclass(frozen=True)
class ApicalVertexModel:
    units: str
    periods: tuple[tuple[float, float], tuple[float, float]]
    length_floor: float
    vertices: tuple[Vertex, ...]
    junctions: tuple[Junction, ...]
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class ParameterChange:
    time: float
    line_tension: tuple[tuple[str, float], ...] = ()
    contractility: tuple[tuple[str, float], ...] = ()
    area_elasticity: tuple[tuple[str, float], ...] = ()
    preferred_area: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class Experiment:
    end_time: float
    observation_times: tuple[float, ...]
    changes: tuple[ParameterChange, ...]


@dataclass(frozen=True)
class Execution(ExecutionSpec):
    vertex_capacity: int = 0
    junction_capacity: int = 0
    half_edge_capacity: int = 0


EXECUTION_FIELDS = {f.name for f in fields(Execution)} - {"edge_capacity", "membrane_capacity"}


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if type(m) is not ApicalVertexModel or type(e) is not Experiment or type(x) is not Execution:
        raise ConfigError("apical_vertex_mechanics@1 requires its own model/experiment/execution")
    execution = asdict(x)
    del execution["edge_capacity"], execution["membrane_capacity"]
    return {
        "schema_version": 1,
        "model": {
            "id": MODEL_ID,
            "units": m.units,
            "periods": [list(p) for p in m.periods],
            "length_floor": m.length_floor,
            "vertices": [
                {"id": v.id, "position": list(v.position), "friction": v.friction}
                for v in m.vertices
            ],
            "junctions": [
                {
                    "id": j.id,
                    "vertices": list(j.vertices),
                    "image": list(j.image),
                    "line_tension": j.line_tension,
                }
                for j in m.junctions
            ],
            "cells": [
                {
                    "id": c.id,
                    "corners": [{"vertex": k.vertex, "image": list(k.image)} for k in c.corners],
                    "area_elasticity": c.area_elasticity,
                    "preferred_area": c.preferred_area,
                    "contractility": c.contractility,
                }
                for c in m.cells
            ],
        },
        "experiment": {
            "end_time": e.end_time,
            "observation_times": list(e.observation_times),
            "parameter_controls": [
                {"time": p.time, **{k: dict(getattr(p, k)) for k in PARAMETER_KINDS}}
                for p in e.changes
            ],
        },
        "execution": execution,
    }


def signed(value, name):
    return signed_number(value, name)


def image(value, name):
    if type(value) is not list or len(value) != 2:
        raise ConfigError(f"{name} must be a pair of integers")
    for n in value:
        if type(n) is not int or abs(n) > MAX_IMAGE:
            raise ConfigError(f"{name} entries must be integers with |n| <= {MAX_IMAGE}")
    return tuple(value)


def pair(value, name):
    if type(value) is not list or len(value) != 2:
        raise ConfigError(f"{name} must be a pair of numbers")
    return tuple(signed(v, name) for v in value)


def named(rows, name):
    if type(rows) is not list or not rows:
        raise ConfigError(f"{name} must be a nonempty list")
    ids = [identifier(r.get("id") if isinstance(r, dict) else None) for r in rows]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"Duplicate {name} ID")
    return rows


def parse_model(raw):
    _fields(
        raw, {"id", "units", "periods", "length_floor", "vertices", "junctions", "cells"}, "model"
    )
    if raw["id"] != MODEL_ID or raw["units"] != UNITS:
        raise ConfigError("Require apical_vertex_mechanics@1 in reduced units")
    if type(raw["periods"]) is not list or len(raw["periods"]) != 2:
        raise ConfigError("periods must list two periodic vectors")
    periods = tuple(pair(p, "periodic vector") for p in raw["periods"])
    if not np.linalg.det(np.array(periods).T) > 0:
        raise ConfigError("Periodic vectors must be right-handed with positive area")
    floor = positive(raw["length_floor"], "length_floor")
    vertices = []
    for v in named(raw["vertices"], "vertex"):
        _fields(v, {"id", "position", "friction"}, "vertex")
        vertices.append(
            Vertex(
                v["id"], pair(v["position"], "vertex position"), positive(v["friction"], "friction")
            )
        )
    known = {v.id for v in vertices}
    junctions = []
    for j in named(raw["junctions"], "junction"):
        _fields(j, {"id", "vertices", "image", "line_tension"}, "junction")
        ends = j["vertices"]
        if type(ends) is not list or len(ends) != 2 or not set(ends) <= known or ends[0] == ends[1]:
            raise ConfigError("A junction joins two distinct declared vertices")
        junctions.append(
            Junction(
                j["id"],
                tuple(ends),
                image(j["image"], "junction image"),
                signed(j["line_tension"], "line_tension"),
            )
        )
    cells = []
    for c in named(raw["cells"], "cell"):
        _fields(c, {"id", "corners", "area_elasticity", "preferred_area", "contractility"}, "cell")
        if type(c["corners"]) is not list or len(c["corners"]) < 3:
            raise ConfigError("A cell needs at least three corners")
        corners = []
        for k in c["corners"]:
            _fields(k, {"vertex", "image"}, "cell corner")
            if k["vertex"] not in known:
                raise ConfigError("Cell corners must name declared vertices")
            corners.append(Corner(k["vertex"], image(k["image"], "corner image")))
        cells.append(
            Cell(
                c["id"],
                tuple(corners),
                positive(c["area_elasticity"], "area_elasticity"),
                positive(c["preferred_area"], "preferred_area"),
                _number(c["contractility"], "contractility"),
            )
        )
    names = [v.id for v in vertices] + [j.id for j in junctions] + [c.id for c in cells]
    if len(set(names)) != len(names):
        raise ConfigError("Vertex, junction and cell IDs must be globally unique")
    model = ApicalVertexModel(
        UNITS, periods, floor, tuple(vertices), tuple(junctions), tuple(cells)
    )
    topology_index(model)
    return model


def topology_index(model):
    """Match every cell edge to its junction; return (junction, direction) per corner.

    A cell edge from corner (a, n_a) to (b, n_b) is the junction (a, b) with image
    n_b - n_a, or the junction (b, a) with image n_a - n_b. Every junction must be
    used by exactly two cell edges in opposite directions, every vertex must have at
    least three corners, and V - J + C = 0 (a torus).
    """
    slot = {v.id: i for i, v in enumerate(model.vertices)}
    declared, unordered = {}, set()
    for index, j in enumerate(model.junctions):
        a, b = slot[j.vertices[0]], slot[j.vertices[1]]
        canonical = (a, b, *j.image) if a < b else (b, a, -j.image[0], -j.image[1])
        if canonical in unordered:
            raise ConfigError("Two junctions join the same vertices through the same image")
        unordered.add(canonical)
        declared[(a, b, *j.image)] = index
    uses = [[] for _ in model.junctions]
    corners_at = np.zeros(len(model.vertices), dtype=int)
    matched = []
    for c in model.cells:
        row = []
        n = len(c.corners)
        for k, corner in enumerate(c.corners):
            following = c.corners[(k + 1) % n]
            a, b = slot[corner.vertex], slot[following.vertex]
            d = (following.image[0] - corner.image[0], following.image[1] - corner.image[1])
            if a == b:
                raise ConfigError("Consecutive cell corners must be distinct vertices")
            if (a, b, *d) in declared:
                index, direction = declared[(a, b, *d)], 1
            elif (b, a, -d[0], -d[1]) in declared:
                index, direction = declared[(b, a, -d[0], -d[1])], -1
            else:
                raise ConfigError(f"Cell {c.id} edge has no junction with matching periodic image")
            uses[index].append(direction)
            row.append((index, direction))
            corners_at[a] += 1
        matched.append(tuple(row))
    if any(sorted(u) != [-1, 1] for u in uses):
        raise ConfigError("Every junction must border cells once in each direction")
    if np.any(corners_at < 3):
        raise ConfigError("Every vertex needs at least three cell corners")
    if len(model.vertices) - len(model.junctions) + len(model.cells) != 0:
        raise ConfigError("A periodic tiling must satisfy V - J + C = 0")
    return tuple(matched)


def parse_overrides(raw, kind, ids, convert):
    if not isinstance(raw, dict) or not set(raw) <= ids:
        raise ConfigError(f"{kind} overrides must name declared entries")
    return tuple((key, convert(raw[key], kind)) for key in sorted(raw))


def parse_experiment(raw, model):
    _fields(raw, {"end_time", "observation_times", "parameter_controls"}, "experiment")
    end = positive(raw["end_time"], "end_time")
    times = raw["observation_times"]
    if type(times) is not list or not times:
        raise ConfigError("Require observation times")
    times = tuple(_number(t, "observation time") for t in times)
    if any(t > end for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observation times must strictly increase within the horizon")
    controls = raw["parameter_controls"]
    if type(controls) is not list or not controls:
        raise ConfigError("Require parameter_controls, starting at time zero")
    junction_ids = {j.id for j in model.junctions}
    cell_ids = {c.id for c in model.cells}
    converters = {
        "line_tension": (junction_ids, signed),
        "contractility": (cell_ids, _number),
        "area_elasticity": (cell_ids, positive),
        "preferred_area": (cell_ids, positive),
    }
    changes = []
    for p in controls:
        _fields(p, {"time", *PARAMETER_KINDS}, "parameter control")
        time = _number(p["time"], "control time")
        if time > end or (changes and time <= changes[-1].time):
            raise ConfigError("Parameter control times must strictly increase within the horizon")
        changes.append(
            ParameterChange(
                time,
                **{
                    kind: parse_overrides(p[kind], kind, *converters[kind])
                    for kind in PARAMETER_KINDS
                },
            )
        )
    if changes[0].time != 0:
        raise ConfigError("Parameter controls must start at time zero")
    return Experiment(end, times, tuple(changes))


def parse_execution(raw, model):
    _fields(raw, EXECUTION_FIELDS, "execution")
    if (
        raw["backend"] not in ("cpu", "gpu")
        or raw["precision"] != "float64"
        or raw["solver"] not in SOLVERS
        or type(raw["jit"]) is not bool
    ):
        raise ConfigError("Vertex execution requires CPU/GPU float64, rk4 or euler, boolean jit")
    corners = sum(len(c.corners) for c in model.cells)
    return Execution(
        dt=positive(raw["dt"], "dt"),
        capacity=_integer(raw["capacity"], "cell capacity", minimum=len(model.cells)),
        jit=raw["jit"],
        max_steps=_integer(raw["max_steps"], "max_steps", maximum=10**8),
        max_trace_bytes=_integer(raw["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1),
        backend=raw["backend"],
        precision="float64",
        solver=raw["solver"],
        vertex_capacity=_integer(
            raw["vertex_capacity"], "vertex capacity", minimum=len(model.vertices)
        ),
        junction_capacity=_integer(
            raw["junction_capacity"], "junction capacity", minimum=len(model.junctions)
        ),
        half_edge_capacity=_integer(
            raw["half_edge_capacity"], "half-edge capacity", minimum=corners
        ),
    )


def parse(data):
    raw = copy.deepcopy(data)
    _fields(raw, {"schema_version", "model", "experiment", "execution"}, "definition")
    model = parse_model(raw["model"])
    spec = SimulationSpec(
        model, parse_experiment(raw["experiment"], model), parse_execution(raw["execution"], model)
    )
    from cells.models.apical_vertex import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        if isinstance(error, ConfigError):
            raise
        raise ConfigError("Invalid apical vertex definition: " + str(error)) from error
    return spec


def held_parameters(spec, change):
    """Arrays (padded to capacity) of the parameters in effect under one control."""
    m, x = spec.model, spec.execution
    values = {
        "line_tension": np.zeros(x.junction_capacity),
        "contractility": np.zeros(x.capacity),
        "area_elasticity": np.zeros(x.capacity),
        "preferred_area": np.zeros(x.capacity),
    }
    values["line_tension"][: len(m.junctions)] = [j.line_tension for j in m.junctions]
    for kind in PARAMETER_KINDS[1:]:
        values[kind][: len(m.cells)] = [getattr(c, kind) for c in m.cells]
    slots = {
        "line_tension": {j.id: i for i, j in enumerate(m.junctions)},
        **{kind: {c.id: i for i, c in enumerate(m.cells)} for kind in PARAMETER_KINDS[1:]},
    }
    for kind in PARAMETER_KINDS:
        for key, value in getattr(change, kind):
            values[kind][slots[kind][key]] = value
    return values


def control_values(spec, times):
    """Right-continuous parameters at each time (one row per time)."""
    from cells.models.apical_vertex import Control

    changes = spec.experiment.changes
    held = [held_parameters(spec, c) for c in changes]
    indices = np.searchsorted([c.time for c in changes], np.asarray(times), side="right") - 1
    return Control(*(np.stack([h[kind] for h in held])[indices] for kind in PARAMETER_KINDS))
