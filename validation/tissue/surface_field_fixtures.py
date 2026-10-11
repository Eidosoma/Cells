"""Frozen synthetic charge-compatible fields, including actual native topology."""

import copy
import json

import numpy as np

from cells.numerics import surface_field as field
from cells.numerics import surface_transport as surface
from validation.tissue import surface_fixtures

CASES = (
    "open",
    "closed",
    "anchored",
    "all_clamped",
    "blocked",
    "equilibrium",
    "one_owner",
    "split",
    "padded",
    "divalent",
    "native_geometry",
)


def charge_from_patches(raw):
    """Manufactured fixed backgrounds permit the declared initial concentrations.

    These capacitor-compatible charges are inputs, not rounded ionic repairs or
    a claim that native BETSE's screened extracellular charge already fits them.
    """
    p, seed = raw["layout"], np.asarray(raw["seed_potential_V"])
    n = len(p["cell_active"])
    q = np.zeros(len(seed))
    for k, active in enumerate(p["membrane_active"]):
        if active:
            i, j = p["membrane_cell"][k], n + p["membrane_outside"][k]
            value = p["membrane_capacitance"][k] * (seed[i] - seed[j])
            q[i] += value
            q[j] -= value
    # Reservoir chemical inventories are held; explicit electrode charge supplies
    # any capacitor countercharge at their fixed-potential boundaries.
    q[n:] = np.where(p["reservoir"], 0.0, q[n:])
    raw["cell_charge_C"], raw["outside_charge_C"] = q[:n].tolist(), q[n:].tolist()
    return raw


def definition(name):
    if name == "native_geometry":
        row, trace, _, _ = surface_fixtures.native_capture()
        p, ids, _, _ = surface_fixtures.native_layout(row)
        k = int(np.flatnonzero((trace["method"] == 0) & ~trace["after"])[0])
        first = [np.flatnonzero(p.membrane_cell == i)[0] for i in range(len(p.cell_active))]
        outside = trace["Phi_b"][k]
        cell = (trace["vm"][k] + outside[p.membrane_outside])[first]
        raw = dict(
            layout={k: v.tolist() for k, v in p._asdict().items()},
            ci=trace["cc_at_mem"][k][ids][:, first].tolist(),
            co=trace["cc_env"][k][ids].tolist(),
            membrane_open=[1.0] * len(p.membrane_active),
            junction_open=[0.7] * len(p.junction_active),
            seed_potential_V=np.r_[cell, outside].tolist(),
            boundary_V=np.where(p.reservoir, outside, 0).tolist(),
            gauge_mask=[False] * len(p.outside_active),
            native_inputs="authenticated topology; manufactured compatible charge and controls",
            native_binding=json.loads(surface_fixtures.PROTOCOL_PATH.read_text())["native_binding"],
        )
        return charge_from_patches(raw)
    raw = surface_fixtures.definition()
    raw.pop("charge_C")
    raw.pop("outside_potential_V")
    p = raw["layout"]
    p.update(
        outside_active=[True] * 5,
        reservoir=[False] * 4 + [True],
        membrane_outside=[0, 1, 2, 3],
        face_active=[True] * 5,
        face_sender=[0, 2, 1, 4, 0],
        face_receiver=[1, 3, 4, 2, 3],
        face_factor=[
            [1e-19, 2e-19, 1e-19, 2e-19, 1e-19],
            [2e-19, 3e-19, 2e-19, 1e-19, 3e-19],
            [1.5e-19, 1e-19, 2e-19, 1e-19, 2e-19],
        ],
    )
    raw.update(
        co=[
            [145.0, 142.0, 147.0, 139.0, 150.0],
            [4.0, 4.5, 5.0, 4.2, 4.1],
            [120.0, 125.0, 124.0, 118.0, 122.0],
        ],
        seed_potential_V=[-0.035, -0.065, 0.0003, -0.0007, 0.001, -0.0015, 0.0],
        boundary_V=[0.0] * 5,
        gauge_mask=[False] * 5,
    )
    if name in ("closed", "one_owner"):
        p["reservoir"] = [False] * 5
        raw["gauge_mask"][4] = True
        if name == "one_owner":
            p["membrane_outside"] = [0, 0, 2, 2]
    elif name == "anchored":
        p["reservoir"][1] = True
        raw["boundary_V"][1] = -0.004
    elif name == "all_clamped":
        p["reservoir"] = [True] * 5
        raw["boundary_V"] = [0.002, -0.004, 0.003, -0.001, 0.0]
    elif name == "blocked":
        raw["membrane_open"], raw["junction_open"] = [0.0] * 4, [0.0]
    elif name == "equilibrium":
        raw["ci"], raw["co"] = [[20.0] * 2 for _ in range(3)], [[20.0] * 5 for _ in range(3)]
        raw["seed_potential_V"] = [0.0] * 7
    elif name == "split":
        for key in ("membrane_active", "membrane_cell", "membrane_outside"):
            p[key].append(p[key][0])
        for key in ("membrane_area", "membrane_capacitance"):
            p[key][0] /= 2
            p[key].append(p[key][0])
        for row in p["membrane_permeability"]:
            row.append(row[0])
        raw["membrane_open"].append(raw["membrane_open"][0])
    elif name == "padded":
        raw["seed_potential_V"].insert(2, 0.0)
        raw["seed_potential_V"].append(0.0)
        for key in ("ci", "co"):
            for row in raw[key]:
                row.append(1.0)
        for key in ("boundary_V", "membrane_open", "junction_open"):
            raw[key].append(0.0)
        raw["gauge_mask"].append(False)
        for key in list(p):
            if key.endswith("_active") or key == "reservoir":
                p[key].append(False)
            elif key.endswith(
                ("_cell", "_outside", "_sender", "_receiver", "_area", "_capacitance")
            ):
                p[key].append(0)
            elif key.endswith(("_permeability", "_factor")):
                for row in p[key]:
                    row.append(0.0)
    elif name == "divalent":
        p["valence"].append([2.0])
        p["membrane_permeability"].append([1e-10] * 4)
        p["junction_permeability"].append([1e-10])
        p["face_factor"].append([1e-19] * 5)
        raw["ci"].append([0.0001, 0.0002])
        raw["co"].append([1.8, 1.9, 1.7, 1.8, 2.0])
    elif name != "open":
        raise ValueError(name)
    return copy.deepcopy(charge_from_patches(raw))


def arrays(raw):
    def dtype(key):
        if key.endswith("_active") or key == "reservoir":
            return bool
        if key.endswith(("_sender", "_receiver")) or key in ("membrane_cell", "membrane_outside"):
            return np.int64
        return np.float64

    layout = surface.Layout(**{k: np.asarray(v, dtype=dtype(k)) for k, v in raw["layout"].items()})
    p = field.bind(layout, np.asarray(raw["gauge_mask"], dtype=bool))
    return (
        *(
            np.asarray(raw[k], dtype=float)
            for k in (
                "ci",
                "co",
                "cell_charge_C",
                "outside_charge_C",
                "membrane_open",
                "junction_open",
                "boundary_V",
            )
        ),
        p,
    )
