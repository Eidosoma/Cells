"""Synthetic fixed-volume cotransport/finite-energy qualification fixtures."""

import json
import math
from copy import deepcopy
from pathlib import Path

from validation.tissue import surface_energy_fixtures as energy

DT, END_TIME, CHECKPOINT_TIME = energy.DT, energy.END_TIME, energy.CHECKPOINT_TIME
STEPS = energy.STEPS
ARMS = ("coupled", "sealed", "absent", "reverse", "stall", "release", "two_patches", "renamed")


def _charge_backgrounds(model):
    unit = 6.02214076e23 * 1.602176634e-19 * 1e-15
    for row in (*model["cells"], *model["extracellular"]):
        row["fixed_charge_equivalent_fmol"] = row["initial_charge_C"] / unit - math.fsum(
            s["valence"] * row["initial_amount_fmol"][s["id"]] for s in model["species"]
        )


def _rename(value, names):
    if isinstance(value, dict):
        return {names.get(k, k): _rename(v, names) for k, v in value.items()}
    if isinstance(value, list):
        return [_rename(v, names) for v in value]
    return names.get(value, value) if isinstance(value, str) else value


def definition(arm="coupled", *, backend="cpu", padded=False, dt=DT):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = json.loads(
        (
            Path(__file__).resolve().parents[2] / "configs/resolved_cotransport_tissue.json"
        ).read_text()
    )
    if arm == "two_patches":
        original = raw
        raw = energy.definition("two_patches", backend=backend, padded=padded, dt=dt)
        raw["model"].update(
            id="resolved_cotransport@1", cotransporters=original["model"]["cotransporters"]
        )
        raw["experiment"]["cotransport_controls"] = original["experiment"]["cotransport_controls"]
        raw["model"]["cotransporters"][1]["membrane_id"] = "membrane_1"
        extra = deepcopy(raw["model"]["cotransporters"][0])
        extra.update(id="kcc_repeated", capacity_fmol_per_s=5000.0)
        raw["model"]["cotransporters"].append(extra)
        raw["experiment"]["cotransport_controls"].append(
            dict(cotransport_id=extra["id"], schedule=[dict(time=0.0, availability=0.3)])
        )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    x.update(backend=backend, dt=dt)
    e["end_time"] = END_TIME
    if arm != "release":
        e["observation_times"] = [i * DT for i in (0, 10, 20, 30, 40)]
        for kind in ("membrane", "junction", "channel", "pump", "regeneration", "cotransport"):
            for row in e[kind + "_controls"]:
                level = 0.3 if row.get("cotransport_id") == "kcc_repeated" else 1.0
                row["schedule"] = [dict(time=0.0, availability=level)]
    if arm == "sealed":
        for row in e["cotransport_controls"]:
            row["schedule"][0]["availability"] = 0.0
    elif arm == "absent":
        m["cotransporters"], e["cotransport_controls"] = [], []
    elif arm in ("reverse", "stall"):
        inside, outside = m["cells"][0], m["extracellular"][0]
        vi, vo = inside["volume_pL"], outside["volume_pL"]
        for s in m["species"]:
            key = s["id"]
            ci, co = (
                inside["initial_amount_fmol"][key] / vi,
                outside["initial_amount_fmol"][key] / vo,
            )
            inside["initial_amount_fmol"][key] = (co if arm == "reverse" else ci) * vi
            outside["initial_amount_fmol"][key] = ci * vo
        _charge_backgrounds(m)
    pad = int(padded)
    x.update(
        capacity=len(m["cells"]) + pad,
        extracellular_capacity=len(m["extracellular"]) + pad,
        membrane_capacity=len(m["membranes"]) + pad,
        edge_capacity=len(m["junctions"]) + pad,
        face_capacity=len(m["faces"]) + pad,
        channel_capacity=len(m["channels"]) + pad,
        regeneration_capacity=len(m["regeneration_ports"]) + pad,
        cotransport_capacity=len(m["cotransporters"]) + pad,
    )
    if arm == "renamed":
        # Existing named channel laws bind canonical ion IDs. Keep that source
        # restriction intact while exercising arbitrary cotransport/pump roles.
        m["channels"], e["channel_controls"] = [], []
        x["channel_capacity"] = pad
        m["species"].reverse()
        raw = _rename(
            raw, dict(Na="sodium_ion", K="potassium_ion", Cl="chloride_ion", Ca="calcium_ion")
        )
    return raw


def normalized(raw):
    result = deepcopy(raw)
    result["execution"]["backend"] = "cpu"
    return result
