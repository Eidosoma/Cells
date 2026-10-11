"""Source-bound setup and mapping; no simulator imports or implicit charge repair."""

import copy
import importlib
import math
import sys
from decimal import Decimal, localcontext
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
c = importlib.import_module("contact")
a = importlib.import_module("alignment")
PROTOCOL = HERE / "protocol.json"
GEOMETRY_FIELDS = (
    "cell_count",
    "membrane_count",
    "cell_centres_m",
    "cell_volumes_m3",
    "cell_areas_m2",
    "membrane_owners",
    "membrane_areas_m2",
)
BACKENDS = ("numpy", "jax_eager", "jax_jit")


def validate_protocol(p):
    # A new panel requires a new version, not an in-place adaptive amendment.
    c.require(p == c.read(PROTOCOL), "Protocol differs from source-bound panel")
    c.require(p["upstream_revision"] == c.REVISION, "Wrong native revision")
    c.require(p["temperature_K"] == 298.15 and p["dt_s"] == 25e-6, "Wrong regime")
    c.require(p["cell_count"] == 7 and p["membrane_face_count"] == 30, "Wrong geometry")
    c.require(
        [v["id"] for v in p["variants"]]
        == ["network_off", "empty_network", "blocked_channel", "active_channel"],
        "Wrong controls",
    )
    c.require(
        p["states"]
        == [
            {"id": "native_initial", "gate": None},
            {"id": "prescribed_mh_a", "gate": [0.2, 0.6]},
            {"id": "prescribed_mh_b", "gate": [0.4, 0.3]},
        ],
        "Wrong gate fixtures",
    )
    c.require(
        all(math.isfinite(v) and v > 0 for v in p["tolerances"].values()), "Invalid tolerance"
    )


def case_ids(p):
    return [f"{v['id']}/{s['id']}" for v in p["variants"] for s in p["states"]]


def configuration(template, base, p, variant, directory):
    conf = a.configuration(template, base, directory)
    conf["variable settings"]["temperature"] = p["temperature_K"]
    for block in ("init time settings", "sim time settings"):
        conf[block]["time step"] = p["dt_s"]
        conf[block]["total time"] = p["dt_s"]
        conf[block]["sampling rate"] = p["dt_s"]
    diffusivity = conf["tissue profile definition"]["tissue"]["default"]["diffusion constants"]
    for species in base["expected_species"]:
        diffusivity[f"Dm_{species}"] = 0.0
    conf["internal parameters"]["substances affect Vmem"] = p["substances_affect_charge"]
    # Replace the whole sample network. In particular no X, Nav, KLeak, ligand,
    # optimization or default transporter can survive a partial override.
    conf["general network"] = {
        "implement network": variant["network"],
        "biomolecules": None,
        "reactions": None,
        "transporters": None,
        "channels": [
            {
                "name": "Kv1p5_contact",
                "channel class": "K",
                "channel type": "Kv1p5",
                "max Dm": p["thickness_m"]
                * p["max_permeability_m_per_s"]
                * p["abundance"]
                * variant["permeability_fraction"],
                "apply to": "all",
                "init active": True,
            }
        ]
        if variant["channel"]
        else None,
        "modulators": None,
    }
    return conf


def uniform_faces(values, owners, n):
    c.require(len(values) == len(owners), "Face array shape differs")
    c.require(set(owners) == set(range(n)), "Invalid face ownership")
    result = []
    for cell in range(n):
        selected = [v for v, owner in zip(values, owners, strict=True) if owner == cell]
        c.require(all(math.isfinite(v) for v in selected), "Nonfinite face state")
        c.require(all(v == selected[0] for v in selected), "Nonuniform within-cell face state")
        result.append(selected[0])
    return result


def uniform_bath(values):
    c.require(bool(values) and all(math.isfinite(v) for v in values), "Invalid bath array")
    c.require(all(v == values[0] for v in values), "Nonuniform well-mixed bath")
    return values[0]


def cell_sums(values, g):
    c.require(len(values) == g["membrane_count"], "Wrong density shape")
    return [
        math.fsum(
            v * area
            for v, area, owner in zip(
                values, g["membrane_areas_m2"], g["membrane_owners"], strict=True
            )
            if owner == i
        )
        for i in range(g["cell_count"])
    ]


def gate_reference(voltage, before, dt):
    """Independent SI logistic targets and native rational gate update, 80 digits."""
    with localcontext() as context:
        context.prec = 80
        d = lambda value: Decimal(str(value))  # noqa: E731
        v, step = d(voltage), d(dt)
        target = [
            1 / (1 + (-(v + d(0.006)) / d(0.0064)).exp()),
            1 / (1 + ((v + d(0.0253)) / d(0.0035)).exp()),
        ]
        tau = [d(0.008330) - d(0.1163) * v, d(1.620) - d(15.5) * v]
        after = [
            (t * d(q) + step * inf) / (t + step)
            for t, q, inf in zip(tau, before, target, strict=True)
        ]
        return tuple(list(map(float, group)) for group in (target, tau, after))


def definition(base, p, variant, g, row):
    """Use measured mobile inventories and actual immobile-ion charge, not neutrality."""
    before = row["before"]
    ids, z = base["mobile_species"], base["expected_valence"]
    n = g["cell_count"]
    voltage = uniform_faces(before["voltage_V"], g["membrane_owners"], n)
    outside = [uniform_bath(v) for v in before["outside_mM"]]
    gates = (
        None
        if not variant["channel"]
        else [
            uniform_faces(row["channel_before"][key], g["membrane_owners"], n) for key in ("m", "h")
        ]
    )
    entries, controls, channel_controls = [], [], []
    for i in range(n):
        local_geometry = {
            "cell_volume_m3": g["cell_volumes_m3"][i],
            "cell_area_m2": g["cell_areas_m2"][i],
            "effective_bath_volume_m3": g["effective_bath_volume_m3"],
            "specific_capacitance_F_per_m2": g["specific_capacitance_F_per_m2"],
        }
        piece = a.cells_definition(base, local_geometry)
        entry = copy.deepcopy(piece["model"]["cells"][0])
        vi = g["cell_volumes_m3"][i] / 1e-15
        entry["cell"].update(
            {
                "id": f"cell_{i}",
                "initial_voltage_V": voltage[i],
                "initial_amount_fmol": {
                    name: before["inside_mM"][k][i] * vi for k, name in enumerate(ids)
                },
                "fixed_charge_equivalent_fmol": math.fsum(
                    z[k] * before["inside_mM"][k][i] * vi for k in range(3, 6)
                ),
            }
        )
        entry["membrane"].update({"id": f"membrane_{i}", "inside": f"cell_{i}", "pump": None})
        entry["membrane"]["passive"]["permeability_m_per_s"] = dict.fromkeys(ids, 0.0)
        if gates is not None:
            entry["channel"] = {
                "id": f"channel_{i}",
                "membrane_id": f"membrane_{i}",
                "species_id": "K",
                "kinetic_law": "betse_kv1p5_mh@1",
                "max_permeability_m_per_s": p["max_permeability_m_per_s"]
                * variant["permeability_fraction"],
                "abundance": p["abundance"],
                "initial_gate": {"m": gates[0][i], "h": gates[1][i]},
            }
            channel_controls.append(
                {"channel_id": f"channel_{i}", "schedule": [{"time": 0, "availability": 1}]}
            )
        entries.append(entry)
        controls.append(
            {
                "membrane_id": f"membrane_{i}",
                "leak": [{"time": 0, "multipliers": dict.fromkeys(ids, 0)}],
                "pump": [{"time": 0, "multiplier": 0}],
            }
        )
    result = piece
    result["model"].update({"temperature_K": p["temperature_K"], "cells": entries})
    vo = g["effective_bath_volume_m3"] / 1e-15
    result["model"]["extracellular"].update(
        {
            "initial_amount_fmol": {name: outside[k] * vo for k, name in enumerate(ids)},
            "fixed_charge_equivalent_fmol": math.fsum(z[k] * outside[k] * vo for k in range(3, 6)),
        }
    )
    result["experiment"].update(
        {
            "end_time": p["dt_s"],
            "observation_times": [0, p["dt_s"]],
            "membrane_controls": controls,
            "channel_controls": channel_controls,
        }
    )
    # Independent padded capacities exercise owner maps without changing production.
    result["execution"].update(
        {
            "dt": p["dt_s"],
            "capacity": 8,
            "membrane_capacity": 9,
            "channel_capacity": 10,
            "extracellular_capacity": 2,
        }
    )
    return result
