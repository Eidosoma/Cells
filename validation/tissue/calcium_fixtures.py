"""Synthetic owned calcium/IP3 tissue; charge backgrounds are explicit inputs."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
F = 96485.33212
ARMS = ("baseline", "blocked", "release", "same_region")


def definition(*, end=0.002, dt=0.0000125, backend="cpu", arm="baseline", padded=True):
    if arm not in ARMS:
        raise ValueError("Unknown tissue calcium arm")
    raw = json.loads((ROOT / "configs/ip3_calcium_cluster.json").read_text())
    raw["model"]["id"] = "spatial_calcium@5"
    m = raw["model"]["ionic"]
    m["id"] = "spatial_extracellular@3"
    m["closure"]["law"] = "capacitive_regions_ghk_return_current@1"
    if arm != "same_region":
        m["cells"][1]["membrane"]["outside"] = "near"
    for outside in (m["extracellular"], *m["surroundings"]):
        q = math.fsum(
            c["membrane"]["area_m2"]
            * c["membrane"]["specific_capacitance_F_per_m2"]
            * c["cell"]["initial_voltage_V"]
            for c in m["cells"]
            if c["membrane"]["outside"] == outside["id"]
        )
        outside["fixed_charge_equivalent_fmol"] = -q / (F * 1e-15) - math.fsum(
            s["valence"] * outside["initial_amount_fmol"][s["id"]] for s in m["species"]
        )
    for face in m["faces"]:
        face["area_m2"] *= 1e-4
    e = raw["experiment"]
    e["end_time"] = end
    e["observation_times"] = sorted({0.0, end, *(t for t in (0.0005, 0.001, 0.0015) if t < end)})
    for key, rows in e.items():
        if key.endswith("_controls"):
            for row in rows:
                for k, v in row.items():
                    if isinstance(v, list):
                        row[k] = [v[0]]
    schedule = e["junction_controls"][0]["schedule"]
    if arm in ("blocked", "release"):
        schedule[0]["open_fraction"] = 0.0
    if arm == "release":
        schedule.append({"time": 0.001, "open_fraction": 1.0})
    x = raw["execution"]
    x.update(backend=backend, dt=dt, field_solver="gauged_damped_newton@1")
    if not padded:
        x.update(
            capacity=2,
            membrane_capacity=2,
            channel_capacity=2,
            edge_capacity=1,
            extracellular_capacity=3,
            face_capacity=len(m["faces"]),
            chemical_capacity=2,
        )
    return raw


def assembly_definition(*, end=0.002, dt=0.0000125, backend="cpu", worlds=2):
    raw = json.loads((ROOT / "configs/assembly_regulated_ip3_calcium_cluster.json").read_text())
    raw["ionic"] = definition(end=end, dt=dt, backend=backend, padded=False)
    for row in raw["pools"]:
        row["pool"].update(end_time_s=end, worlds=worlds)
    raw["window_ticks"] = 20
    return raw
