"""Explicit production adapter for the separately preserved NUM-011 coordinates."""

import hashlib
import json
from pathlib import Path

import numpy as np

from cells.core.specs import parse_spec

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "runs/num-011-kinetic-pump-2026-09-16/candidate-01"


def evidence():
    def read(name):
        return json.loads((CAPTURE / name).read_text())

    assert hashlib.sha256((CAPTURE / "completion.json").read_bytes()).hexdigest() == (
        "57df709995d155139e20f026dbdd40bd37b417e9cbc8c182586ae8ecf681cbcb"
    )
    receipt = read("completion.json")
    for name in ("registration.json", "reference.json"):
        assert (
            hashlib.sha256((CAPTURE / name).read_bytes()).hexdigest()
            == receipt["files_sha256"][name]
        )
    return read("registration.json")["protocol"], read("reference.json")["results"]


def definition(case, *, dt=0.0001, end=None, padded=True, samples=None, jit=True):
    ids = case["species"]
    n = len(case["volume_pL"])
    end = case["end_time_s"] if end is None else end

    def mapped(values):
        return dict(zip(ids, values, strict=True))

    local = []
    for i in range(n):
        local.append(
            {
                "cell": {
                    "id": f"cell_{i}",
                    "volume_pL": case["volume_pL"][i],
                    "initial_amount_fmol": mapped(
                        [v * case["volume_pL"][i] for v in case["initial_inside_mM"][i]]
                    ),
                    "initial_voltage_V": case["initial_voltage_V"][i],
                    "fixed_charge_equivalent_fmol": case["fixed_inside_charge_fmol"][i],
                },
                "membrane": {
                    "id": f"membrane_{i}",
                    "inside": f"cell_{i}",
                    "outside": "outside",
                    "area_m2": case["area_m2"][i],
                    "specific_capacitance_F_per_m2": case["specific_capacitance_F_m2"][i],
                    "passive": {
                        "law": "constant_field@1",
                        "permeability_m_per_s": mapped(case["permeability_m_s"][i]),
                    },
                    "pump": {
                        "id": f"pump_{i}",
                        "law": "nak_atp_mass_action_positive@1",
                        "roles": {
                            "sodium": ids[case["sodium_index"]],
                            "potassium": ids[case["potassium_index"]],
                        },
                        "stoichiometry": {
                            ids[i]: v for i, v in enumerate(case["pump_stoichiometry"]) if v
                        },
                        "capacity_fmol_per_s": case["area_m2"][i]
                        * case["alpha_mol_m2_s"][i]
                        * 1e15,
                        **{k: case[k][i] for k in ("km_na_mM", "km_k_mM", "km_atp_mM")},
                        "metabolism": {
                            "kind": "maintained_chemical_reservoirs@1",
                            **{k: case[k][i] for k in ("atp_mM", "adp_mM", "pi_mM")},
                            "delta_g0_J_per_mol": case["delta_g0_J_mol"][i],
                        },
                    },
                },
                "channel": None,
            }
        )
    return {
        "schema_version": 1,
        "model": {
            "id": "finite_extracellular@2",
            "species": [{"id": s, "valence": z} for s, z in zip(ids, case["valence"], strict=True)],
            "temperature_K": case["temperature_K"],
            "extracellular": {
                "id": "outside",
                "volume_pL": case["outside_volume_pL"],
                "initial_amount_fmol": mapped(
                    [v * case["outside_volume_pL"] for v in case["initial_outside_mM"]]
                ),
                "fixed_charge_equivalent_fmol": case["fixed_outside_charge_fmol"],
            },
            "cells": local,
            "junctions": [],
        },
        "experiment": {
            "end_time": end,
            "observation_times": [0.0, end] if samples is None else list(samples),
            "membrane_controls": [
                {
                    "membrane_id": f"membrane_{i}",
                    "leak": [
                        {"time": r["time_s"], "multipliers": dict.fromkeys(ids, r["leak"])}
                        for r in case["controls"]
                        if r["time_s"] <= end
                    ],
                    "pump": [
                        {"time": r["time_s"], "multiplier": r["pump"]}
                        for r in case["controls"]
                        if r["time_s"] <= end
                    ],
                }
                for i in range(n)
            ],
            "channel_controls": [],
            "junction_controls": [],
        },
        "execution": {
            "dt": dt,
            "jit": jit,
            "capacity": 3 if padded else n,
            "membrane_capacity": 4 if padded else n,
            "channel_capacity": 2 if padded else 0,
            "edge_capacity": 2 if padded else 0,
            "extracellular_capacity": 2 if padded else 1,
            "backend": "cpu",
            "precision": "float64",
            "solver": "rk4",
            "max_steps": 10000,
            "max_trace_bytes": 2**28,
            "material_balance_atol_fmol": dict.fromkeys(ids, 2e-11),
        },
    }


def spec_for(case, **kwargs):
    return parse_spec(definition(case, **kwargs))


def canonical(values, n):
    """Convert every physical/history coordinate; omit only structurally zero gates/edges."""

    def get(name):
        return np.asarray(values[name])

    def flat(a):
        return a.swapaxes(-1, -2).reshape((*a.shape[:-2], -1))

    return np.concatenate(
        (
            flat(get("amount_increment")[..., :, :n]),
            get("extracellular_amount_increment")[..., :, 0],
            flat(get("leak_transferred")[..., :, :n]),
            get("pump_cycles")[..., :n],
            get("dissipated_energy_pJ")[..., :n],
        ),
        axis=-1,
    )
