"""Explicit production adapters; frozen NUM-010 guards remain unchanged."""

import json
from pathlib import Path

import numpy as np

from cells.core.spatial_extracellular_spec import CLOSURE, FACE_LAW, FIELD_SOLVER, MEMBRANE_LAW
from cells.core.specs import SPATIAL_EXTRACELLULAR_ID, parse_spec
from tests import spatial_extracellular_numerical_data as data

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "runs/num-010-2026-09-11/reference-01"
REFERENCE_SHA = "abf25d88ebd64bf2c922f189bdf0669ae100c46eef3101d0d8eda98f15a66046"


def load_cases():
    if (
        data.file_sha(data.PANEL) != data.PANEL_SHA256
        or data.file_sha(REFERENCE / "verification.json") != REFERENCE_SHA
        or any(data.file_sha(ROOT / p) != value for p, value in data.INHERITED_SHA256.items())
    ):
        raise ValueError("Frozen spatial protocol or accepted reference identity differs")
    plan = json.loads(data.PANEL.read_text())
    receipt = json.loads((REFERENCE / "verification.json").read_text())
    cases = tuple(data.resolve(c) for c in plan["cases"])
    for case in cases:
        path = f"cases/{case.id}/definition.json"
        if (
            data.file_sha(REFERENCE / path) != receipt["files_sha256"][path]
            or json.loads((REFERENCE / path).read_text()) != case.definition()
        ):
            raise ValueError("Saved spatial inputs differ from the frozen panel")
    return plan, cases


def definition(case, *, dt=0.000125, jit=True, padded=True, capacities=None, samples=None):
    world = case.raw["world"]
    ids = tuple(world["species_ids"])

    def mapped(value):
        return dict(zip(ids, value, strict=True))

    def compartments(kind):
        return [
            {k: v for k, v in c.items() if k != "kind"}
            | {"initial_amount_fmol": mapped(c["initial_amount_fmol"])}
            for c in world["compartments"]
            if c["kind"] == kind
        ]

    cells, outside = compartments("intracellular"), compartments("extracellular")
    sizes = dict(
        capacity=len(cells),
        membrane_capacity=len(world["membranes"]),
        extracellular_capacity=len(outside),
        face_capacity=len(world["faces"]),
    )
    if padded:
        sizes = {k: v + (2 if k == "membrane_capacity" else 1) for k, v in sizes.items()}
    if capacities is not None:
        sizes.update(capacities)
    return {
        "schema_version": 1,
        "model": {
            "id": SPATIAL_EXTRACELLULAR_ID,
            "species": [
                {"id": s, "valence": z} for s, z in zip(ids, world["valence"], strict=True)
            ],
            "temperature_K": world["temperature_K"],
            "cells": cells,
            "extracellular": outside,
            "membranes": [
                p | {"law": MEMBRANE_LAW, "permeability_m_per_s": mapped(p["permeability_m_per_s"])}
                for p in world["membranes"]
            ],
            "faces": [
                {k: v for k, v in p.items() if k not in ("left", "right")}
                | {
                    "sender": p["left"],
                    "receiver": p["right"],
                    "law": FACE_LAW,
                    "diffusivity_m2_per_s": mapped(p["diffusivity_m2_per_s"]),
                }
                for p in world["faces"]
            ],
            "closure": {"law": CLOSURE, "gauge_reference": outside[-1]["id"]},
        },
        "experiment": {
            "end_time": case.horizon_s,
            "observation_times": data.observations(case).tolist()
            if samples is None
            else list(samples),
            "membrane_controls": [
                {
                    "membrane_id": p["id"],
                    "schedule": [
                        {"time": c.time_s, "availability": c.availability[i]} for c in case.controls
                    ],
                }
                for i, p in enumerate(world["membranes"])
            ],
        },
        "execution": {
            "dt": dt,
            "jit": jit,
            **sizes,
            "edge_capacity": 0,
            "field_solver": FIELD_SOLVER,
            "backend": "cpu",
            "precision": "float64",
            "solver": "rk4",
            "max_steps": 10000,
            "max_trace_bytes": 2**30,
            "material_balance_atol_fmol": {s: 1e-10 for s in ids},
        },
    }


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def load_reference(case, name="refined"):
    if data.file_sha(REFERENCE / "verification.json") != REFERENCE_SHA:
        raise ValueError("Accepted spatial reference identity differs")
    receipt = json.loads((REFERENCE / "verification.json").read_text())
    relative = f"cases/{case.id}/{name}.npz"
    if data.file_sha(REFERENCE / relative) != receipt["files_sha256"][relative]:
        raise ValueError("Saved spatial trajectory differs from its authenticated reference")
    with np.load(REFERENCE / relative, allow_pickle=False) as source:
        return dict(source)


def canonical(case, values):
    """All six production leaves, in frozen mixed-owner/reference coordinate order."""
    parts = {}
    source = np.asarray(values["amount_increment"])
    head = source.shape[:-2]
    parts["amount"] = np.zeros((*head, *case.layout.shapes["amount"]))
    for kind, key in (
        ("intracellular", "amount_increment"),
        ("extracellular", "extracellular_amount_increment"),
    ):
        owners = [i for i, c in enumerate(case.raw["world"]["compartments"]) if c["kind"] == kind]
        parts["amount"][..., owners, :] = np.asarray(values[key])[
            ..., : len(case.g.z), : len(owners)
        ].swapaxes(-1, -2)
    for key, name in (
        ("membrane_transfer", "membrane_transferred"),
        ("face_transfer", "face_transferred"),
        ("membrane_dissipation", "membrane_dissipated_energy_pJ"),
        ("face_dissipation", "face_dissipated_energy_pJ"),
    ):
        array = np.asarray(values[name])[..., : case.layout.shapes[key][0]]
        parts[key] = array.swapaxes(-1, -2) if len(case.layout.shapes[key]) == 2 else array
    return np.concatenate(
        [
            parts[key].reshape(*head, int(np.prod(shape)))
            for key, shape in case.layout.shapes.items()
        ],
        axis=-1,
    )


def potentials(case, observations):
    head = observations["extracellular_potential_V"].shape[:-1]
    result = np.zeros((*head, len(case.g.ids)))
    for kind, key in (
        ("intracellular", "cell_potential_V"),
        ("extracellular", "extracellular_potential_V"),
    ):
        owners = [i for i, c in enumerate(case.raw["world"]["compartments"]) if c["kind"] == kind]
        result[..., owners] = observations[key][..., : len(owners)]
    return result - result[..., -1:]
