"""Production schema/state adapters; the preserved reference is not a production loader."""

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from cells.core.specs import PHYSICAL_IONIC_GRAPH_ID, parse_spec
from tests import multispecies_fixtures as ionic
from tests import physical_ionic_graph_numerical_data as data

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "runs/num-008-2026-09-10/reference-01"
REFERENCE_SHA = "bd9ee2599899dd3b34fa2072b308c2dd435485bb538a7775f24396baf664c8a7"


def load_cases():
    """Resolve immutable physical inputs, not NUM-008's old-production guard.

    That guard is still exercised unchanged by the preserved-source auditor.
    Here saved protocol/case identities are pinned for current production tests.
    """
    plan_path = ROOT / "configs/reference/physical_ionic_graph_trajectories_v1.json"
    if (
        data.sha(plan_path) != data.PANEL_SHA256
        or data.sha(REFERENCE / "verification.json") != REFERENCE_SHA
    ):
        raise ValueError("Frozen NUM-008 protocol/evidence identity differs")
    plan = json.loads(plan_path.read_text())
    panel_path = ROOT / plan["physical_panel"]
    if data.sha(panel_path) != plan["physical_panel_sha256"]:
        raise ValueError("Frozen physical graph panel identity differs")
    cases = data.resolve_cases(plan, json.loads(panel_path.read_text()))
    receipt = json.loads((REFERENCE / "verification.json").read_text())
    if data.sha(REFERENCE / "cases.json") != receipt["files_sha256"]["cases.json"]:
        raise ValueError("Saved case identity differs")
    if [c.definition() for c in cases] != json.loads((REFERENCE / "cases.json").read_text()):
        raise ValueError("Resolved inputs differ from accepted reference cases")
    return plan, cases


def definition(
    case,
    *,
    dt=0.002,
    jit=True,
    capacity=4,
    membrane_capacity=5,
    channel_capacity=3,
    edge_capacity=4,
    samples=None,
):
    graph, controls = case.graph, case.controls
    local, membranes = [], []
    for index, cell in enumerate(graph.cells):
        rows = tuple(
            SimpleNamespace(time_s=c.time_s, leak=c.value.leak[index], pump=c.value.pump[index])
            for c in controls
        )
        base = ionic.definition(
            SimpleNamespace(parameters=cell, horizon_s=case.horizon_s, controls=rows),
            dt=dt,
            jit=jit,
            capacity=capacity,
            membrane_capacity=membrane_capacity,
            samples=samples,
        )
        binding = next((c for c in graph.channels if c.assembly.cell_id == cell.cell_id), None)
        local.append(
            {k: base["model"][k] for k in ("cell", "membrane")}
            | {"channel": None if binding is None else asdict(binding.channel)}
        )
        membranes.append(base["experiment"]["membrane_controls"])
    ids = graph.species_ids
    edges = [
        {
            "id": c.id,
            "from_cell": c.from_cell,
            "to_cell": c.to_cell,
            "area_m2": c.area_m2,
            **{
                key: dict(zip(ids, getattr(c, key), strict=True))
                for key in ("permeability_m_per_s", "residual_fraction")
            },
            "gate": {
                key: getattr(c, key)
                for key in ("law", "sensitivity_per_V", "half_voltage_V", "tau_s", "initial_gate")
            },
        }
        for c in graph.junctions
    ]
    return base | {
        "model": {
            "id": PHYSICAL_IONIC_GRAPH_ID,
            "species": base["model"]["species"],
            "bath": base["model"]["bath"],
            "cells": local,
            "junctions": edges,
        },
        "experiment": {
            "end_time": case.horizon_s,
            "observation_times": [0.0, case.horizon_s] if samples is None else list(samples),
            "membrane_controls": membranes,
            "channel_controls": [
                {
                    "channel_id": c.channel.id,
                    "schedule": [
                        {"time": p.time_s, "availability": p.value.channel[i]} for p in controls
                    ],
                }
                for i, c in enumerate(graph.channels)
            ],
            "junction_controls": [
                {
                    "junction_id": c.id,
                    "schedule": [
                        {"time": p.time_s, "open_fraction": p.value.junction[i]} for p in controls
                    ],
                }
                for i, c in enumerate(graph.junctions)
            ],
        },
        "execution": base["execution"]
        | {"channel_capacity": channel_capacity, "edge_capacity": edge_capacity},
    }


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def canonical(case, values, prefix="", *, derivative=False):
    """Padded species-major production -> frozen cell/edge-major increment coordinates."""
    raw = case.definition() if hasattr(case, "definition") else case
    layout = data.layout(raw)
    n, k, e = layout.n, layout.k, layout.e

    def get(name):
        return np.asarray(values[prefix + name])

    leading = get("amount").shape[:-2]

    def flat(a):
        return a.reshape((*leading, a.shape[-1] * a.shape[-2]))

    amount = get("amount")[..., :, :n].swapaxes(-1, -2)
    if not derivative:
        amount = amount - np.asarray([c["initial_amount_fmol"] for c in raw["graph"]["cells"]])
    return np.concatenate(
        (
            flat(amount),
            flat(get("leak_transferred")[..., :, :n].swapaxes(-1, -2)),
            get("pump_cycles")[..., :n],
            get("dissipated_energy_pJ")[..., :n],
            flat(get("gate")[..., :, :k].swapaxes(-1, -2)),
            get("channel_transferred")[..., :k],
            get("junction_gate")[..., :e],
            flat(get("junction_transferred")[..., :, :e].swapaxes(-1, -2)),
            get("junction_dissipated_energy_pJ")[..., :e],
        ),
        axis=-1,
    )
