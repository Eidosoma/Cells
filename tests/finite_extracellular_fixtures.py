"""Explicit production adapters for immutable NUM-009 v2 inputs and coordinates."""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from cells.core.specs import FINITE_EXTRACELLULAR_ID, parse_spec
from tests import finite_extracellular_numerical_data as data
from tests import finite_extracellular_numerical_data_v2 as v2

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "runs/num-009-2026-09-10/reference-02"
REFERENCE_SHA = "a628ee5eb7cbecb438728012ffe2a2ba6fb28b7a9ab20a7c4f429318f5b0c45b"


def load_cases():
    # The unchanged old-production guard runs in the preserved 0.13 context,
    # not against a deliberately new production family.
    if (
        data.sha(v2.PANEL) != v2.PANEL_SHA256
        or data.sha(REFERENCE / "verification.json") != REFERENCE_SHA
    ):
        raise ValueError("Frozen NUM-009 v2 protocol/evidence identity differs")
    plan = json.loads(v2.PANEL.read_text())
    source = ROOT / plan["definitions_source"]
    if data.sha(source) != plan["definitions_source_sha256"]:
        raise ValueError("Frozen SPEC-008 definitions changed")
    cases = data.resolve_cases(plan, json.loads(source.read_text()))
    receipt = json.loads((REFERENCE / "verification.json").read_text())
    if data.sha(REFERENCE / "cases.json") != receipt["files_sha256"]["cases.json"]:
        raise ValueError("Saved finite-world inputs changed")
    if [c.definition() for c in cases] != json.loads((REFERENCE / "cases.json").read_text()):
        raise ValueError("Resolved inputs differ from accepted reference")
    return plan, cases


def definition(
    case,
    *,
    dt=0.001,
    jit=True,
    capacity=4,
    membrane_capacity=5,
    channel_capacity=3,
    edge_capacity=4,
    extracellular_capacity=2,
    samples=None,
):
    w, controls, local = case.world, case.controls, []
    ids = w.species_ids

    def mapped(value):
        return dict(zip(ids, value, strict=True))

    def compartment(c):
        return asdict(c) | {"initial_amount_fmol": mapped(c.initial_amount_fmol)}

    for cell, m in zip(w.cells, w.membranes, strict=True):
        pump = None
        if m.pump is not None:
            p = m.pump
            nu = mapped(p.stoichiometry)
            pump = {
                "id": p.id,
                "law": "nak_atp_affinity_tanh@1",
                "roles": dict(zip(("sodium", "potassium"), p.roles, strict=True)),
                "stoichiometry": {s: nu[s] for s in p.roles},
                "capacity_fmol_per_s": p.capacity_fmol_per_s,
                "drive_J_per_mol": p.drive_J_per_mol,
            }
        ch = next((c for c in w.channels if c.membrane_id == m.id), None)
        local.append(
            {
                "cell": compartment(cell) | {"initial_voltage_V": m.initial_voltage_V},
                "membrane": {
                    "id": m.id,
                    "inside": m.inside,
                    "outside": m.outside,
                    "area_m2": m.area_m2,
                    "specific_capacitance_F_per_m2": m.specific_capacitance_F_per_m2,
                    "passive": {
                        "law": "constant_field@1",
                        "permeability_m_per_s": mapped(m.permeability_m_per_s),
                    },
                    "pump": pump,
                },
                "channel": None if ch is None else asdict(ch),
            }
        )
    return {
        "schema_version": 1,
        "model": {
            "id": FINITE_EXTRACELLULAR_ID,
            "species": [{"id": s, "valence": z} for s, z in zip(ids, w.valence, strict=True)],
            "temperature_K": w.temperature_K,
            "extracellular": compartment(w.extracellular),
            "cells": local,
            "junctions": [
                {
                    "id": p.id,
                    "from_cell": p.from_cell,
                    "to_cell": p.to_cell,
                    "area_m2": p.area_m2,
                    "permeability_m_per_s": mapped(p.permeability_m_per_s),
                    "residual_fraction": mapped(p.residual_fraction),
                    "gate": {
                        k: getattr(p, k)
                        for k in (
                            "law",
                            "sensitivity_per_V",
                            "half_voltage_V",
                            "tau_s",
                            "initial_gate",
                        )
                    },
                }
                for p in w.junctions
            ],
        },
        "experiment": {
            "end_time": case.horizon_s,
            "observation_times": [0.0, case.horizon_s] if samples is None else list(samples),
            "membrane_controls": [
                {
                    "membrane_id": m.id,
                    "leak": [
                        {"time": c.time_s, "multipliers": mapped(c.value.leak[i])} for c in controls
                    ],
                    "pump": [{"time": c.time_s, "multiplier": c.value.pump[i]} for c in controls],
                }
                for i, m in enumerate(w.membranes)
            ],
            "channel_controls": [
                {
                    "channel_id": ch.id,
                    "schedule": [
                        {"time": c.time_s, "availability": c.value.channel[i]} for c in controls
                    ],
                }
                for i, ch in enumerate(w.channels)
            ],
            "junction_controls": [
                {
                    "junction_id": edge.id,
                    "schedule": [
                        {"time": c.time_s, "open_fraction": c.value.junction[i]} for c in controls
                    ],
                }
                for i, edge in enumerate(w.junctions)
            ],
        },
        "execution": {
            "dt": dt,
            "jit": jit,
            "capacity": capacity,
            "membrane_capacity": membrane_capacity,
            "channel_capacity": channel_capacity,
            "edge_capacity": edge_capacity,
            "extracellular_capacity": extracellular_capacity,
            "backend": "cpu",
            "precision": "float64",
            "solver": "rk4",
            "max_steps": 10000,
            "max_trace_bytes": 2**28,
            "material_balance_atol_fmol": {s: 1e-12 if s == "Ca" else 1e-10 for s in ids},
        },
    }


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def canonical(case, values, prefix="", *, derivative=False):
    raw = case.definition() if hasattr(case, "definition") else case
    layout = data.layout(raw)
    n, k, e = layout.n, layout.k, layout.e

    def get(name):
        return np.asarray(values[prefix + name])

    leading = get("amount_increment").shape[:-2]

    def flat(a):
        return a.reshape((*leading, a.shape[-1] * a.shape[-2]))

    return np.concatenate(
        (
            flat(get("amount_increment")[..., :, :n].swapaxes(-1, -2)),
            flat(get("leak_transferred")[..., :, :n].swapaxes(-1, -2)),
            get("pump_cycles")[..., :n],
            get("dissipated_energy_pJ")[..., :n],
            flat(get("gate")[..., :, :k].swapaxes(-1, -2)),
            get("channel_transferred")[..., :k],
            get("junction_gate")[..., :e],
            flat(get("junction_transferred")[..., :, :e].swapaxes(-1, -2)),
            get("junction_dissipated_energy_pJ")[..., :e],
            get("extracellular_amount_increment")[..., :, 0],
        ),
        axis=-1,
    )
