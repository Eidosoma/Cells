"""Finite kinetic cluster with a spatial outside; old family identities stay explicit.

All cells face the same declared local outside. Junction voltage therefore uses
the shared outside potential cancellation. Cross-region junctions are rejected,
not approximated by silently treating different outside potentials as equal.
"""

import copy
from dataclasses import asdict

from cells.core import junction_finite_spec as cluster
from cells.core import spatial_extracellular_spec as spatial
from cells.core.physical_ionic_graph_spec import _tuple
from cells.core.specs import (
    SPATIAL_JUNCTION_ID,
    ChannelChange,
    ConfigError,
    ExtracellularFaceSpec,
    FiniteCompartmentSpec,
    FiniteExtracellularExecutionSpec,
    JunctionFiniteExtracellularSpec,
    SimulationSpec,
    SpatialExperimentSpec,
    SpatialExtracellularExecutionSpec,
    SpatialExtracellularSpec,
    SpatialJunctionExecutionSpec,
    SpatialJunctionSpec,
    SpatialMembraneSpec,
    _fields,
)


def local_spec(spec):
    return SimulationSpec(
        JunctionFiniteExtracellularSpec(
            **{
                k: getattr(spec.model, k)
                for k in JunctionFiniteExtracellularSpec.__dataclass_fields__
            }
        ),
        spec.experiment,
        FiniteExtracellularExecutionSpec(
            **{
                k: getattr(spec.execution, k)
                for k in FiniteExtracellularExecutionSpec.__dataclass_fields__
            }
        ),
    )


def passive_spec(spec):
    """Geometry projection only; never a replacement for the coupled dynamics."""
    m, e, x = spec.model, spec.experiment, spec.execution
    return SimulationSpec(
        SpatialExtracellularSpec(
            m.species_ids,
            m.valence,
            m.temperature_K,
            m.cells,
            (m.extracellular, *m.surroundings),
            tuple(
                SpatialMembraneSpec(
                    p.id,
                    p.inside,
                    p.outside,
                    p.area_m2,
                    p.area_m2 * p.specific_capacitance_F_per_m2,
                    p.permeability_m_per_s,
                    p.initial_voltage_V,
                )
                for p in m.membranes
            ),
            m.faces,
            m.gauge_reference,
        ),
        SpatialExperimentSpec(
            e.end_time,
            e.observation_times,
            tuple((ChannelChange(0.0, 1.0),) for _ in m.membranes),
        ),
        SpatialExtracellularExecutionSpec(
            **{
                k: ("cpu" if k == "backend" else 0 if k == "edge_capacity" else getattr(x, k))
                for k in SpatialExtracellularExecutionSpec.__dataclass_fields__
            }
        ),
    )


def to_dict(spec):
    if type(spec.execution) is not SpatialJunctionExecutionSpec:
        raise ConfigError("Spatial cluster requires its own execution type")
    _tuple(spec.model.surroundings, FiniteCompartmentSpec, "surroundings")
    _tuple(spec.model.faces, ExtracellularFaceSpec, "faces")
    raw = cluster.to_dict(local_spec(spec))
    geometry = spatial.to_dict(passive_spec(spec))
    raw["model"].update(
        id=SPATIAL_JUNCTION_ID,
        surroundings=geometry["model"]["extracellular"][1:],
        faces=geometry["model"]["faces"],
        closure=geometry["model"]["closure"],
    )
    raw["execution"].update(
        face_capacity=spec.execution.face_capacity, field_solver=spec.execution.field_solver
    )
    return raw


def parse(data):
    _fields(
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
        "spatial cluster",
    )
    _fields(data["execution"], set(SpatialJunctionExecutionSpec.__dataclass_fields__), "execution")
    if type(data["model"]["surroundings"]) is not list:
        raise ConfigError("Spatial surroundings must be an explicit list")
    raw = copy.deepcopy(data)
    surroundings, faces, closure = (
        raw["model"].pop(k) for k in ("surroundings", "faces", "closure")
    )
    face_capacity, field_solver = (
        raw["execution"].pop(k) for k in ("face_capacity", "field_solver")
    )
    raw["model"]["id"] = "finite_extracellular@3"
    local = cluster.parse(raw)
    m, x = local.model, local.execution
    geometry = spatial.parse(
        {
            "schema_version": 1,
            "model": {
                "id": "spatial_extracellular@1",
                "species": raw["model"]["species"],
                "temperature_K": m.temperature_K,
                "cells": [
                    {k: v for k, v in c["cell"].items() if k != "initial_voltage_V"}
                    for c in raw["model"]["cells"]
                ],
                "extracellular": [raw["model"]["extracellular"], *surroundings],
                "membranes": [
                    {
                        "id": p.id,
                        "inside": p.inside,
                        "outside": p.outside,
                        "area_m2": p.area_m2,
                        "capacitance_F": p.area_m2 * p.specific_capacitance_F_per_m2,
                        "permeability_m_per_s": dict(
                            zip(m.species_ids, p.permeability_m_per_s, strict=True)
                        ),
                        "initial_voltage_V": p.initial_voltage_V,
                        "law": spatial.MEMBRANE_LAW,
                    }
                    for p in m.membranes
                ],
                "faces": faces,
                "closure": closure,
            },
            "experiment": {
                "end_time": local.experiment.end_time,
                "observation_times": list(local.experiment.observation_times),
                "membrane_controls": [
                    {"membrane_id": p.id, "schedule": [{"time": 0.0, "availability": 1.0}]}
                    for p in m.membranes
                ],
            },
            "execution": {
                **{k: v for k, v in asdict(x).items() if k != "channel_capacity"},
                "backend": "cpu",
                "edge_capacity": 0,
                "face_capacity": face_capacity,
                "field_solver": field_solver,
                "material_balance_atol_fmol": dict(
                    zip(m.species_ids, x.material_balance_atol_fmol, strict=True)
                ),
            },
        }
    )
    g = geometry.model
    identities = [
        p.id
        for p in (*m.cells, *m.membranes, *m.channels, *m.junctions, *g.extracellular, *g.faces)
    ]
    identities += [p.pump.id for p in m.membranes if p.pump is not None]
    if len(set(identities)) != len(identities):
        raise ConfigError("Spatial physical owners require globally unique IDs")
    return SimulationSpec(
        SpatialJunctionSpec(
            **{k: getattr(m, k) for k in JunctionFiniteExtracellularSpec.__dataclass_fields__},
            surroundings=g.extracellular[1:],
            faces=g.faces,
            gauge_reference=g.gauge_reference,
        ),
        local.experiment,
        SpatialJunctionExecutionSpec(
            **asdict(x),
            face_capacity=geometry.execution.face_capacity,
            field_solver=geometry.execution.field_solver,
        ),
    )
