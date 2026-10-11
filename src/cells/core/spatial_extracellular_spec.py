"""Strict passive spatial definitions; explicit owners, closure and solver identity."""

from dataclasses import asdict

from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import aligned, identifier
from cells.core.physical_ionic_graph_spec import _tuple
from cells.core.specs import (
    SPATIAL_EXTRACELLULAR_ID,
    ChannelChange,
    ConfigError,
    ExtracellularFaceSpec,
    FiniteCompartmentSpec,
    SimulationSpec,
    SpatialExperimentSpec,
    SpatialExtracellularExecutionSpec,
    SpatialExtracellularSpec,
    SpatialMembraneSpec,
    _fields,
    _integer,
    _number,
)
from cells.core.voltage_gated_spec import fraction

CLOSURE = "capacitive_components_current_continuity@1"
FACE_LAW = "logmean_electrodiffusion@1"
MEMBRANE_LAW = "constant_field@1"
FIELD_SOLVER = "gauged_dense_kirchhoff@1"


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if type(e) is not SpatialExperimentSpec or type(x) is not SpatialExtracellularExecutionSpec:
        raise ConfigError("Spatial model requires its own execution and experiment types")
    ids = m.species_ids
    _tuple(ids, str, "species IDs")
    if not ids or len(set(ids)) != len(ids):
        raise ConfigError("Require nonempty distinct species IDs")

    def mapped(value):
        if type(value) is not tuple or len(value) != len(ids):
            raise ConfigError("Species vectors must be complete immutable tuples")
        return dict(zip(ids, value, strict=True))

    _tuple(m.cells, FiniteCompartmentSpec, "cells")
    _tuple(m.extracellular, FiniteCompartmentSpec, "extracellular")
    _tuple(m.membranes, SpatialMembraneSpec, "membranes", size=len(m.cells))
    _tuple(m.faces, ExtracellularFaceSpec, "faces")
    if type(e.observation_times) is not tuple:
        raise ConfigError("Observation times must be an immutable tuple")
    _tuple(e.membranes, tuple, "membrane schedules", size=len(m.membranes))
    for group in e.membranes:
        _tuple(group, ChannelChange, "membrane availability changes")
    if tuple(p.inside for p in m.membranes) != tuple(c.id for c in m.cells):
        raise ConfigError("Membranes must be in cell owner order")
    z = mapped(m.valence)
    return {
        "schema_version": 1,
        "model": {
            "id": SPATIAL_EXTRACELLULAR_ID,
            "species": [{"id": s, "valence": z[s]} for s in ids],
            "temperature_K": m.temperature_K,
            **{
                name: [
                    asdict(c) | {"initial_amount_fmol": mapped(c.initial_amount_fmol)}
                    for c in getattr(m, name)
                ]
                for name in ("cells", "extracellular")
            },
            "membranes": [
                asdict(p)
                | {"law": MEMBRANE_LAW, "permeability_m_per_s": mapped(p.permeability_m_per_s)}
                for p in m.membranes
            ],
            "faces": [
                asdict(p)
                | {"law": FACE_LAW, "diffusivity_m2_per_s": mapped(p.diffusivity_m2_per_s)}
                for p in m.faces
            ],
            "closure": {"law": CLOSURE, "gauge_reference": m.gauge_reference},
        },
        "experiment": {
            "end_time": e.end_time,
            "observation_times": list(e.observation_times),
            "membrane_controls": [
                {"membrane_id": p.id, "schedule": [asdict(c) for c in group]}
                for p, group in zip(m.membranes, e.membranes, strict=True)
            ],
        },
        "execution": asdict(x)
        | {"material_balance_atol_fmol": mapped(x.material_balance_atol_fmol)},
    }


def parse(data):
    root = _fields(
        data["model"],
        {
            "id",
            "species",
            "temperature_K",
            "cells",
            "extracellular",
            "membranes",
            "faces",
            "closure",
        },
        "model",
    )
    if type(root["species"]) is not list or not root["species"]:
        raise ConfigError("Require a nonempty ordered species list")
    species = [_fields(s, {"id", "valence"}, "species") for s in root["species"]]
    ids, z = tuple(identifier(s["id"]) for s in species), tuple(s["valence"] for s in species)
    if len(set(ids)) != len(ids) or any(
        type(v) is not int or v not in (-3, -2, -1, 1, 2, 3) for v in z
    ):
        raise ConfigError("Require unique species and nonzero integer valences in [-3,3]")
    temperature = positive(root["temperature_K"], "temperature")
    for name in ("cells", "extracellular", "membranes", "faces"):
        if type(root[name]) is not list:
            raise ConfigError(f"{name} must be an explicit list")

    def compartment(c):
        _fields(c, set(FiniteCompartmentSpec.__dataclass_fields__), "compartment")
        return FiniteCompartmentSpec(
            identifier(c["id"]),
            positive(c["volume_pL"], "volume"),
            aligned(c["initial_amount_fmol"], ids, "initial amounts", positive),
            signed_number(c["fixed_charge_equivalent_fmol"], "fixed charge"),
        )

    cells = tuple(compartment(c) for c in root["cells"])
    outside = tuple(compartment(c) for c in root["extracellular"])
    cids, oids = tuple(c.id for c in cells), tuple(c.id for c in outside)
    if not outside or len(set(cids + oids)) != len(cids + oids):
        raise ConfigError("Require at least one outside and distinct compartment IDs")
    membranes = []
    for p in root["membranes"]:
        _fields(p, set(SpatialMembraneSpec.__dataclass_fields__) | {"law"}, "membrane")
        if p["law"] != MEMBRANE_LAW:
            raise ConfigError("Unsupported passive membrane law")
        membranes.append(
            SpatialMembraneSpec(
                *(identifier(p[k]) for k in ("id", "inside", "outside")),
                positive(p["area_m2"], "membrane area"),
                positive(p["capacitance_F"], "membrane capacitance"),
                aligned(p["permeability_m_per_s"], ids, "membrane permeability"),
                signed_number(p["initial_voltage_V"], "initial voltage"),
            )
        )
    if (
        len(membranes) != len(cells)
        or {p.inside for p in membranes} != set(cids)
        or any(p.outside not in oids for p in membranes)
    ):
        raise ConfigError("Each cell requires exactly one membrane facing an identified outside")
    membranes = tuple(sorted(membranes, key=lambda p: cids.index(p.inside)))
    faces, pairs = [], set()
    neighbors = {i: set() for i in oids}
    for p in root["faces"]:
        _fields(p, set(ExtracellularFaceSpec.__dataclass_fields__) | {"law"}, "face")
        if p["law"] != FACE_LAW:
            raise ConfigError("Unsupported outside transport law")
        face = ExtracellularFaceSpec(
            *(identifier(p[k]) for k in ("id", "sender", "receiver")),
            positive(p["area_m2"], "face area"),
            positive(p["length_m"], "face length"),
            aligned(p["diffusivity_m2_per_s"], ids, "face diffusivity"),
        )
        pair = frozenset((face.sender, face.receiver))
        if (
            len(pair) != 2
            or not pair <= set(oids)
            or pair in pairs
            or not any(face.diffusivity_m2_per_s)
        ):
            raise ConfigError(
                "Face requires distinct outside owners, unique edge and positive conduction"
            )
        pairs.add(pair)
        neighbors[face.sender].add(face.receiver)
        neighbors[face.receiver].add(face.sender)
        faces.append(face)
    visited, frontier = set(), [oids[0]]
    while frontier:
        owner = frontier.pop()
        if owner not in visited:
            visited.add(owner)
            frontier.extend(neighbors[owner] - visited)
    if visited != set(oids):
        raise ConfigError("The conductive outside graph must be connected")
    owners = (*cids, *oids, *(p.id for p in membranes), *(p.id for p in faces))
    if len(set(owners)) != len(owners):
        raise ConfigError("All physical IDs must be globally distinct")
    closure = _fields(root["closure"], {"law", "gauge_reference"}, "closure")
    if closure["law"] != CLOSURE or closure["gauge_reference"] not in oids:
        raise ConfigError("Require the supported closure and one identified outside gauge")

    e = _fields(
        data["experiment"], {"end_time", "observation_times", "membrane_controls"}, "experiment"
    )
    end = positive(e["end_time"], "end time")
    if type(e["observation_times"]) is not list or not e["observation_times"]:
        raise ConfigError("Observation times must be a nonempty list")
    times = tuple(_number(t, "observation time") for t in e["observation_times"])
    if any(t > end for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observation times must strictly increase within the horizon")
    if type(e["membrane_controls"]) is not list:
        raise ConfigError("Require explicit membrane controls, empty for a pure bulk world")
    controls = {}
    for group in e["membrane_controls"]:
        _fields(group, {"membrane_id", "schedule"}, "membrane control")
        mid = identifier(group["membrane_id"])
        if mid in controls or type(group["schedule"]) is not list or not group["schedule"]:
            raise ConfigError("Each membrane needs one nonempty identified schedule")
        changes = []
        for p in group["schedule"]:
            _fields(p, {"time", "availability"}, "membrane control change")
            changes.append(
                ChannelChange(
                    _number(p["time"], "control time"), fraction(p["availability"], "availability")
                )
            )
        if (
            changes[0].time != 0
            or any(c.time > end for c in changes)
            or any(b.time <= a.time for a, b in zip(changes, changes[1:], strict=False))
        ):
            raise ConfigError(
                "Controls must begin at zero and strictly increase within the horizon"
            )
        controls[mid] = tuple(changes)
    if set(controls) != {p.id for p in membranes}:
        raise ConfigError("Control IDs must exactly match membrane owners")

    x = _fields(
        data["execution"], set(SpatialExtracellularExecutionSpec.__dataclass_fields__), "execution"
    )
    for key, required in (
        ("backend", "cpu"),
        ("precision", "float64"),
        ("solver", "rk4"),
        ("field_solver", FIELD_SOLVER),
    ):
        if x[key] != required:
            raise ConfigError(f"This version requires {key}={required!r}")
    if type(x["jit"]) is not bool:
        raise ConfigError("jit must be a boolean")
    execution = SpatialExtracellularExecutionSpec(
        dt=positive(x["dt"], "dt"),
        jit=x["jit"],
        max_steps=_integer(x["max_steps"], "max_steps"),
        max_trace_bytes=_integer(x["max_trace_bytes"], "max_trace_bytes", maximum=2**53 - 1),
        material_balance_atol_fmol=aligned(
            x["material_balance_atol_fmol"], ids, "material tolerance", positive
        ),
        edge_capacity=_integer(x["edge_capacity"], "edge_capacity", minimum=0, maximum=0),
        **{
            key: _integer(x[key], key, minimum=n)
            for key, n in (
                ("capacity", len(cells)),
                ("membrane_capacity", len(membranes)),
                ("extracellular_capacity", len(outside)),
                ("face_capacity", len(faces)),
            )
        },
    )
    if (execution.capacity == 0) != (execution.membrane_capacity == 0):
        raise ConfigError(
            "Zero cell and membrane capacity must be paired; padded slots are not owners"
        )
    if any(t > 1e-10 for t in execution.material_balance_atol_fmol):
        raise ConfigError("Material tolerance cannot weaken the inherited 1e-10 fmol limit")
    model = SpatialExtracellularSpec(
        ids, z, temperature, cells, outside, membranes, tuple(faces), closure["gauge_reference"]
    )
    from cells.models.spatial_extracellular import check_definition

    try:
        check_definition(model)
    except ConfigError:
        raise
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Derived spatial arithmetic exceeds finite float64") from error
    return SimulationSpec(
        model,
        SpatialExperimentSpec(end, times, tuple(controls[p.id] for p in membranes)),
        execution,
    )
