"""Synthetic two-cell / three-region composition; no biological calibration claim."""

import copy
import math

IDS = ("Na", "K", "Cl")
F = 6.02214076e23 * 1.602176634e-19


def definition(*, end=0.02, dt=0.0001, backend="cpu", arm="baseline", padded=True):
    if arm not in (
        "baseline",
        "pump_release",
        "channel_release",
        "junction_release",
        "blocked",
        "finite_limit",
    ):
        raise ValueError("Unknown spatial qualification arm")

    def mapped(values):
        return dict(zip(IDS, values, strict=True))

    local, charges = [], []
    for i, (volume, voltage, concentrations) in enumerate(
        (
            (0.5, -0.060, (12, 140, 8)),
            (0.7, -0.040, (15, 130, 10)),
        )
    ):
        area = 3e-10 * (1 + 0.2 * i)
        amounts = [v * volume for v in concentrations]
        equivalent = area * 0.01 * voltage / (F * 1e-15)
        charges.append(area * 0.01 * voltage)
        local.append(
            {
                "cell": {
                    "id": f"cell_{i}",
                    "volume_pL": volume,
                    "initial_amount_fmol": mapped(amounts),
                    "fixed_charge_equivalent_fmol": equivalent
                    - math.fsum((amounts[0], amounts[1], -amounts[2])),
                    "initial_voltage_V": voltage,
                },
                "membrane": {
                    "id": f"membrane_{i}",
                    "inside": f"cell_{i}",
                    "outside": "local",
                    "area_m2": area,
                    "specific_capacitance_F_per_m2": 0.01,
                    "passive": {
                        "law": "constant_field@1",
                        "permeability_m_per_s": mapped((1e-11, 2e-10, 8e-11)),
                    },
                    "pump": {
                        "id": f"pump_{i}",
                        "law": "nak_atp_mass_action_positive@1",
                        "roles": {"sodium": "Na", "potassium": "K"},
                        "stoichiometry": {"Na": -3, "K": 2},
                        "capacity_fmol_per_s": 0.05 * (i + 1),
                        "km_na_mM": 12.0,
                        "km_k_mM": 0.2,
                        "km_atp_mM": 0.5,
                        "metabolism": {
                            "kind": "maintained_chemical_reservoirs@1",
                            "atp_mM": 1.5,
                            "adp_mM": 0.1,
                            "pi_mM": 0.1,
                            "delta_g0_J_per_mol": -37000.0,
                        },
                    },
                },
                "channel": {
                    "id": f"channel_{i}",
                    "membrane_id": f"membrane_{i}",
                    "species_id": "K",
                    "kinetic_law": "betse_kv1p5_mh@1",
                    "max_permeability_m_per_s": 3e-10,
                    "abundance": 0.5 + i * 0.1,
                    "initial_gate": {"m": 0.2, "h": 0.7},
                },
            }
        )
    outside = []
    for name, volume, concentration in (
        ("local", 2.0, (140, 4, 110)),
        ("near", 1.0, (120, 8, 105)),
        ("far", 3.0, (150, 3, 115)),
    ):
        amounts = [v * volume for v in concentration]
        equivalent = -math.fsum(charges) / (F * 1e-15) if name == "local" else 0.0
        outside.append(
            {
                "id": name,
                "volume_pL": volume,
                "initial_amount_fmol": mapped(amounts),
                "fixed_charge_equivalent_fmol": equivalent
                - math.fsum((amounts[0], amounts[1], -amounts[2])),
            }
        )

    def schedule(kind, key):
        values = [{"time": 0.0, key: 1.0}]
        if arm == kind + "_release":
            values += [
                {"time": t, key: value} for t, value in ((0.005, 0.0), (0.01, 1.0)) if t <= end
            ]
        if arm == "blocked":
            values[0][key] = 0.0
        return values

    times = sorted(
        {0.0, end, *(v for v in (0.000073, 0.0025, 0.005, 0.0075, 0.01, 0.015) if v < end)}
    )
    raw = {
        "schema_version": 1,
        "model": {
            "id": "spatial_extracellular@2",
            "species": [{"id": s, "valence": z} for s, z in zip(IDS, (1, 1, -1), strict=True)],
            "temperature_K": 298.15,
            "cells": local,
            "extracellular": outside[0],
            "surroundings": outside[1:],
            "junctions": [
                {
                    "id": "junction",
                    "from_cell": "cell_0",
                    "to_cell": "cell_1",
                    "area_m2": 1e-10,
                    "permeability_m_per_s": mapped((3e-10, 5e-10, 4e-10)),
                    "gate": {
                        "law": "betse_rate_junction_relaxation@1",
                        "threshold_voltage_V": 0.015,
                        "minimum_open_fraction": 0.1,
                        "initial_gate": 0.6,
                    },
                }
            ],
            "faces": [
                {
                    "id": f"face_{i}",
                    "sender": a,
                    "receiver": b,
                    "area_m2": 1e-11,
                    "length_m": 2e-5,
                    "diffusivity_m2_per_s": mapped((1.2e-9, 1.7e-9, 2e-9)),
                    "law": "logmean_electrodiffusion@1",
                }
                for i, (a, b) in enumerate((("local", "near"), ("near", "far"), ("far", "local")))
            ],
            "closure": {
                "law": "capacitive_components_current_continuity@1",
                "gauge_reference": "local",
            },
        },
        "experiment": {
            "end_time": end,
            "observation_times": times,
            "membrane_controls": [
                {
                    "membrane_id": f"membrane_{i}",
                    "leak": [
                        {
                            "time": 0.0,
                            "multipliers": dict.fromkeys(IDS, 0.0 if arm == "blocked" else 1.0),
                        }
                    ],
                    "pump": schedule("pump", "multiplier"),
                }
                for i in range(2)
            ],
            "channel_controls": [
                {"channel_id": f"channel_{i}", "schedule": schedule("channel", "availability")}
                for i in range(2)
            ],
            "junction_controls": [
                {"junction_id": "junction", "schedule": schedule("junction", "open_fraction")}
            ],
        },
        "execution": {
            "dt": dt,
            "jit": True,
            "capacity": 3 if padded else 2,
            "membrane_capacity": 4 if padded else 2,
            "channel_capacity": 3 if padded else 2,
            "edge_capacity": 2 if padded else 1,
            "extracellular_capacity": 5 if padded else 3,
            "face_capacity": 4 if padded else 3,
            "field_solver": "gauged_dense_kirchhoff@1",
            "backend": backend,
            "precision": "float64",
            "solver": "rk4",
            "max_steps": 10000,
            "max_trace_bytes": 256 * 1024**2,
            "material_balance_atol_fmol": dict.fromkeys(IDS, 2e-11),
        },
    }
    if arm == "finite_limit":
        raw["model"].update(surroundings=[], faces=[])
    return raw


def local_definition(raw):
    raw = copy.deepcopy(raw)
    for key in ("surroundings", "faces", "closure"):
        raw["model"].pop(key)
    for key in ("face_capacity", "field_solver"):
        raw["execution"].pop(key)
    raw["model"]["id"] = "finite_extracellular@3"
    return raw
