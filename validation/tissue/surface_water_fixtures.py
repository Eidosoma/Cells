"""Small finite-volume water/ion cases; synthetic parameters, fixed interfaces."""

import json
from copy import deepcopy
from pathlib import Path

from validation.tissue import surface_dynamics_fixtures

ARMS = ("coupled", "sealed", "water_only", "shrink", "release")
STEPS = (1e-4, 5e-5, 2.5e-5)


def definition(arm="coupled", *, backend="cpu", padded=True, dt=STEPS[0]):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/resolved_water_tissue.json").read_text()
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    x.update(backend=backend, dt=dt)
    pad = int(padded)
    x.update(
        capacity=1 + pad,
        extracellular_capacity=1 + pad,
        membrane_capacity=1 + pad,
        edge_capacity=pad,
        face_capacity=pad,
    )
    if arm != "release":
        e["observation_times"] = [i * STEPS[0] for i in (0, 4, 8, 12, 16, 20)]
        for family in ("membrane", "water"):
            e[family + "_controls"][0]["schedule"] = [dict(time=0.0, availability=1.0)]
    if arm == "sealed":
        m["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = 0.0
    if arm == "water_only":
        e["membrane_controls"][0]["schedule"][0]["availability"] = 0.0
    if arm == "shrink":
        m["water_compartments"][0]["impermeant_amount_fmol"] = 10.0
    return raw


def multicell(*, backend="cpu", padded=True):
    raw = surface_dynamics_fixtures.definition("closed", backend=backend, padded=padded)
    m, e = raw["model"], raw["experiment"]
    m["id"] = "resolved_water@1"
    m["water_compartments"] = [
        dict(
            compartment_id=p["id"],
            reference_volume_pL=0.9 * p["volume_pL"],
            minimum_volume_pL=0.5 * p["volume_pL"],
            maximum_volume_pL=1.5 * p["volume_pL"],
            impermeant_amount_fmol=7.0 + i,
            bulk_modulus_Pa=200000.0 + i,
            pressure_offset_Pa=-500.0 + i,
        )
        for i, p in enumerate(m["cells"] + m["extracellular"])
    ]
    m["water_membranes"] = [
        dict(membrane_id=p["id"], hydraulic_permeability_m_per_Pa_s=(i + 1) * 1e-13)
        for i, p in enumerate(m["membranes"])
    ]
    e["water_controls"] = [
        dict(membrane_id=p["id"], schedule=[dict(time=0.0, availability=0.2 * (i + 1))])
        for i, p in enumerate(m["membranes"])
    ]
    return raw


def normalized(raw):
    result = deepcopy(raw)
    result["execution"]["backend"] = "cpu"
    return result
