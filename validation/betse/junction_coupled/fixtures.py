"""Authenticated native geometry with declared physical-gate experiment changes."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np

PARENT = "betse-junction-trajectory-20260920-03"
WORKSPACE = Path("/mnt/workspaces/Cells")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prior_definition(case, workspace=WORKSPACE):
    parent = workspace / PARENT
    done = read(parent / "completion.json")
    assert done["status"] == "held_open_free_voltage_junction_trajectories_pass"
    assert done["result_sha256"] == sha(parent / "result.json")
    result = read(parent / "result.json")
    relative = case + "/cells-0/definition.json"
    path = parent / "comparison" / relative
    assert result["comparison_files_sha256"][relative] == sha(path)
    return read(path)


def definition(case, protocol, *, dt=None, backend="cpu", end=None, workspace=WORKSPACE):
    raw = prior_definition(case, workspace)
    raw["model"]["id"] = protocol["model"]
    for i, edge in enumerate(raw["model"]["junctions"]):
        edge.pop("residual_fraction")
        edge["permeability_m_per_s"] = {
            k: v * protocol["junction_permeability_scale"]
            for k, v in edge["permeability_m_per_s"].items()
        }
        threshold, minimum, fraction = (
            protocol[k][i % len(protocol[k])]
            for k in ("thresholds_V", "minimums", "initial_fractions")
        )
        edge["gate"] = {
            "law": protocol["law"],
            "threshold_voltage_V": threshold,
            "minimum_open_fraction": minimum,
            "initial_gate": minimum + (1 - minimum) * fraction,
        }
    end = protocol["duration_s"] if end is None else end
    times = np.arange(0, end, protocol["observation_step_s"]).tolist()
    times.extend([end, min(end, protocol["off_grid_observation_s"])])
    raw["experiment"].update(end_time=end, observation_times=sorted(set(times)))
    for group in raw["experiment"]["junction_controls"]:
        opening = group["schedule"][0]["open_fraction"]
        group["schedule"] = [
            {"time": time, "open_fraction": opening * availability}
            for time, availability in protocol["availability"]
            if time <= end
        ]
    raw["execution"].update(
        dt=protocol["cells_steps_s"][0] if dt is None else dt,
        backend=backend,
        max_steps=100000,
        max_trace_bytes=protocol["resources"]["max_trace_bytes"],
        material_balance_atol_fmol=dict.fromkeys(
            raw["execution"]["material_balance_atol_fmol"], protocol["tolerances"]["material_fmol"]
        ),
    )
    return raw


def with_membrane_processes(raw):
    """Short composition witness; not part of the junction-only reference panel."""
    raw = copy.deepcopy(raw)
    cell = raw["model"]["cells"][0]
    cell["membrane"]["pump"] = {
        "id": "pump_0",
        "law": "nak_atp_mass_action_positive@1",
        "roles": {"sodium": "Na", "potassium": "K"},
        "stoichiometry": {"Na": -3, "K": 2},
        "capacity_fmol_per_s": 0.001,
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
    }
    cell["channel"] = {
        "id": "channel_0",
        "membrane_id": "membrane_0",
        "species_id": "K",
        "kinetic_law": "betse_kv1p5_mh@1",
        "max_permeability_m_per_s": 1e-11,
        "abundance": 0.5,
        "initial_gate": {"m": 0.2, "h": 0.7},
    }
    raw["execution"]["channel_capacity"] = 2
    raw["experiment"]["channel_controls"] = [
        {"channel_id": "channel_0", "schedule": [{"time": 0.0, "availability": 1.0}]}
    ]
    return raw
