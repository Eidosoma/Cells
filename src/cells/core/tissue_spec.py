"""Cross-region kinetic tissue ownership, with an explicit new electrical law."""

import copy
from dataclasses import dataclass, fields, replace

from cells.core import junction_finite_spec, spatial_extracellular_spec, spatial_junction_spec
from cells.core.finite_extracellular_spec import parse_assembly
from cells.core.kinetic_finite_spec import parse_membrane
from cells.core.specs import (
    ConfigError,
    JunctionFiniteExtracellularSpec,
    SimulationSpec,
    SpatialExtracellularExecutionSpec,
    SpatialJunctionExecutionSpec,
    SpatialJunctionSpec,
    _fields,
)
from cells.numerics.tissue_field import LAW_ID, SOLVER_ID

MODEL_ID = "spatial_extracellular@3"


@dataclass(frozen=True)
class TissueModel(SpatialJunctionSpec):
    """One capacitor per cell, independently identified extracellular owners."""


def to_dict(spec):
    if type(spec.execution) is not SpatialJunctionExecutionSpec:
        raise ConfigError("Tissue requires explicit spatial junction execution")
    projected = SimulationSpec(
        SpatialJunctionSpec(**vars(spec.model)),
        spec.experiment,
        replace(spec.execution, field_solver=spatial_extracellular_spec.FIELD_SOLVER),
    )
    raw = spatial_junction_spec.to_dict(projected)
    raw["model"]["id"] = MODEL_ID
    raw["model"]["closure"]["law"] = LAW_ID
    raw["execution"]["field_solver"] = spec.execution.field_solver
    return raw


def parse(data):
    m = _fields(
        data["model"],
        {
            "id",
            "species",
            "temperature_K",
            "extracellular",
            "cells",
            "junctions",
            "surroundings",
            "faces",
            "closure",
        },
        "tissue model",
    )
    x = _fields(
        data["execution"], set(SpatialJunctionExecutionSpec.__dataclass_fields__), "execution"
    )
    closure = _fields(m["closure"], {"law", "gauge_reference"}, "tissue closure")
    if m["id"] != MODEL_ID or closure["law"] != LAW_ID or x["field_solver"] != SOLVER_ID:
        raise ConfigError("Tissue requires its named coupled closure and nonlinear solver")
    if type(m["cells"]) is not list or not m["cells"] or type(m["surroundings"]) is not list:
        raise ConfigError("Tissue requires explicit cells and surroundings")
    # Reuse strict spatial geometry/charge validation. This projection retains
    # every physical owner and coefficient; its passive dynamics are never run.
    cells, membranes = [], []
    for entry in m["cells"]:
        _fields(entry, {"cell", "membrane", "channel"}, "local cell")
        c, p = entry["cell"], entry["membrane"]
        try:
            cells.append({k: v for k, v in c.items() if k != "initial_voltage_V"})
            membranes.append(
                {
                    "id": p["id"],
                    "inside": p["inside"],
                    "outside": p["outside"],
                    "area_m2": p["area_m2"],
                    "capacitance_F": p["area_m2"] * p["specific_capacitance_F_per_m2"],
                    "permeability_m_per_s": p["passive"]["permeability_m_per_s"],
                    "initial_voltage_V": c["initial_voltage_V"],
                    "law": spatial_extracellular_spec.MEMBRANE_LAW,
                }
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise ConfigError("Incomplete tissue cell or membrane") from error
    geometry = spatial_extracellular_spec.parse(
        {
            "model": {
                "id": "spatial_extracellular@1",
                "species": m["species"],
                "temperature_K": m["temperature_K"],
                "cells": cells,
                "extracellular": [m["extracellular"], *m["surroundings"]],
                "membranes": membranes,
                "faces": m["faces"],
                "closure": {
                    "law": spatial_extracellular_spec.CLOSURE,
                    "gauge_reference": closure["gauge_reference"],
                },
            },
            "experiment": {
                "end_time": data["experiment"]["end_time"],
                "observation_times": data["experiment"]["observation_times"],
                "membrane_controls": [
                    {"membrane_id": p["id"], "schedule": [{"time": 0.0, "availability": 1.0}]}
                    for p in membranes
                ],
            },
            "execution": {f.name: x[f.name] for f in fields(SpatialExtracellularExecutionSpec)}
            | {
                "backend": "cpu",
                "edge_capacity": 0,
                "field_solver": spatial_extracellular_spec.FIELD_SOLVER,
            },
        }
    )
    raw = copy.deepcopy(data)
    for key in ("surroundings", "faces", "closure"):
        raw["model"].pop(key)
    for key in ("face_capacity", "field_solver"):
        raw["execution"].pop(key)
    raw["model"]["id"] = "finite_extracellular@3"
    from cells.models import junction_finite_extracellular as junction

    def check_local(model):
        junction.kinetic.check_definition(
            model,
            junction_check=junction.check_junction_definition,
            outside_compartments=geometry.model.extracellular,
        )

    local = parse_assembly(
        raw,
        JunctionFiniteExtracellularSpec,
        parse_membrane,
        check_local,
        bind_junction=junction_finite_spec.parse_junction,
        backends=("cpu", "gpu"),
        outside_compartments=geometry.model.extracellular[1:],
    )
    g = geometry.model
    identities = [
        p.id
        for p in (
            *local.model.cells,
            *local.model.membranes,
            *local.model.channels,
            *local.model.junctions,
            *g.extracellular,
            *g.faces,
        )
    ]
    identities += [p.pump.id for p in local.model.membranes if p.pump is not None]
    if len(set(identities)) != len(identities):
        raise ConfigError("Tissue physical owners require globally unique IDs")
    spec = SimulationSpec(
        TissueModel(
            **vars(local.model),
            surroundings=g.extracellular[1:],
            faces=g.faces,
            gauge_reference=g.gauge_reference,
        ),
        local.experiment,
        SpatialJunctionExecutionSpec(
            **vars(local.execution),
            face_capacity=geometry.execution.face_capacity,
            field_solver=SOLVER_ID,
        ),
    )
    from cells.models.tissue import check_definition

    check_definition(spec)
    return spec
