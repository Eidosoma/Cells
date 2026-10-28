"""Synthetic active-water cases; no fitted metabolic or mechanical parameters."""

import json
import math
from copy import deepcopy
from pathlib import Path

from validation.tissue import surface_water_fixtures as passive

ARMS = ("coupled", "sealed", "passive", "inhibited", "reverse", "release")
STEPS = (1.25e-6, 6.25e-7, 3.125e-7)
END = 40 * STEPS[0]
CHECKPOINT_TIME = 20 * STEPS[0]


def definition(arm="coupled", *, backend="cpu", padded=True, dt=STEPS[0]):
    if arm not in ARMS:
        raise ValueError("Unknown active-water arm")
    path = Path(__file__).resolve().parents[2] / "configs/resolved_water_kinetic_tissue.json"
    raw = json.loads(path.read_text())
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    x.update(
        backend=backend,
        dt=dt,
        capacity=1 + int(padded),
        extracellular_capacity=1 + int(padded),
        membrane_capacity=1 + int(padded),
        edge_capacity=int(padded),
        face_capacity=int(padded),
        channel_capacity=3 + int(padded),
    )
    if arm != "release":
        e["observation_times"] = [i * STEPS[0] for i in (0, 10, 20, 30, 40)]
        for key in ("membrane_controls", "water_controls", "channel_controls", "pump_controls"):
            for group in e[key]:
                group["schedule"] = [dict(time=0.0, availability=1.0)]
    if arm == "sealed":
        m["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = 0.0
    if arm == "passive":
        m["membranes"][0]["pump"] = None
        m["channels"] = []
        e["channel_controls"] = e["pump_controls"] = []
        x["channel_capacity"] = int(padded)
    if arm == "inhibited":
        e["pump_controls"][0]["schedule"][0]["availability"] = 0.0
    if arm == "reverse":
        m["membranes"][0]["pump"]["metabolism"].update(atp_mM=0.0001, adp_mM=10.0, pi_mM=10.0)
    return raw


def multicell(*, backend="cpu", padded=True):
    raw = passive.multicell(backend=backend, padded=padded)
    sample = definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_water@2"
    m["temperature_K"] = 298.15
    m["species"].append(dict(id="Ca", valence=2))
    charge_per_fmol = 6.02214076e23 * 1.602176634e-19 * 1e-15
    for family, concentration in (("cells", 0.0001), ("extracellular", 0.02)):
        for owner in m[family]:
            owner["initial_amount_fmol"]["Ca"] = concentration * owner["volume_pL"]
            owner["fixed_charge_equivalent_fmol"] = owner[
                "initial_charge_C"
            ] / charge_per_fmol - math.fsum(
                s["valence"] * owner["initial_amount_fmol"][s["id"]] for s in m["species"]
            )
    for kind, key in (
        ("membranes", "permeability_m_per_s"),
        ("junctions", "permeability_m_per_s"),
        ("faces", "diffusivity_m2_per_s"),
    ):
        for route in m[kind]:
            route[key]["Ca"] = 0.0
    m["channels"], e["channel_controls"], e["pump_controls"] = [], [], []
    for i, patch in enumerate(m["membranes"]):
        patch["pump"] = deepcopy(sample["model"]["membranes"][0]["pump"])
        patch["pump"]["id"] = f"pump_{i}"
        e["pump_controls"].append(
            dict(pump_id=f"pump_{i}", schedule=[dict(time=0.0, availability=0.8)])
        )
        for template in sample["model"]["channels"]:
            channel = deepcopy(template)
            channel.update(id=f"{template['id']}_{i}", membrane_id=patch["id"])
            m["channels"].append(channel)
            e["channel_controls"].append(
                dict(channel_id=channel["id"], schedule=[dict(time=0.0, availability=0.8)])
            )
    for junction in m["junctions"]:
        junction["gate"] = dict(
            law="betse_rate_junction_relaxation@1",
            threshold_voltage_V=0.015,
            minimum_open_fraction=0.1,
            initial_gate=0.6,
        )
    for edge in m["water_membranes"]:
        edge["hydraulic_permeability_m_per_Pa_s"] = 1e-10
    for key in ("membrane_controls", "junction_controls", "water_controls"):
        for group in e[key]:
            group["schedule"] = [dict(time=0.0, availability=1.0)]
    e.update(end_time=END, observation_times=[i * STEPS[0] for i in (0, 10, 20, 30, 40)])
    x.update(dt=STEPS[0], channel_capacity=len(m["channels"]) + int(padded))
    x["material_balance_atol_fmol"]["Ca"] = 2e-11
    return raw


def normalized(raw):
    raw = deepcopy(raw)
    raw["execution"]["backend"] = "cpu"
    return raw
