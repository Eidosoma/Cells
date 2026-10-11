"""Synthetic resolved surfaces plus an authenticated, completed BETSE capture."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np

from cells.numerics import surface_transport as model

PROTOCOL_PATH = Path(__file__).with_name("surface_protocol.json")
CASES = (
    "gradient",
    "closed",
    "blocked",
    "equilibrium",
    "neutral",
    "reversed",
    "split",
    "padded",
    "isolated",
)


def definition(name="gradient"):
    p = dict(
        temperature=310.0,
        valence=[[1.0], [1.0], [-1.0]],
        cell_active=[True, True],
        outside_active=[True, True, True],
        reservoir=[False, False, True],
        membrane_active=[True] * 4,
        membrane_cell=[0, 0, 1, 1],
        membrane_outside=[0, 1, 1, 2],
        membrane_area=[4e-10, 6e-10, 3e-10, 7e-10],
        membrane_capacitance=[4e-12, 6e-12, 3e-12, 7e-12],
        membrane_permeability=[[1e-9] * 4, [2e-9] * 4, [8e-10] * 4],
        face_active=[True, True],
        face_sender=[0, 1],
        face_receiver=[1, 2],
        face_factor=[[1e-19, 2e-19], [2e-19, 3e-19], [1.5e-19, 1e-19]],
        junction_active=[True],
        junction_sender=[0],
        junction_receiver=[1],
        junction_area=[1e-11],
        junction_permeability=[[1e-9], [2e-9], [1e-9]],
    )
    raw = dict(
        layout=p,
        ci=[[12.0, 15.0], [140.0, 130.0], [10.0, 13.0]],
        co=[[145.0, 140.0, 150.0], [4.0, 5.0, 4.5], [120.0, 125.0, 122.0]],
        charge_C=[-4e-13, -6e-13],
        outside_potential_V=[0.001, -0.001, 0.003],
        membrane_open=[1.0, 0.5, 0.75, 1.0],
        junction_open=[0.6],
    )
    if name == "closed":
        p["reservoir"] = [False] * 3
    elif name == "blocked":
        raw["membrane_open"], raw["junction_open"] = [0.0] * 4, [0.0]
    elif name == "equilibrium":
        raw.update(
            ci=[[20.0] * 2 for _ in range(3)],
            co=[[20.0] * 3 for _ in range(3)],
            charge_C=[0.0] * 2,
            outside_potential_V=[0.0] * 3,
        )
    elif name == "neutral":
        p["valence"].append([0.0])
        p["membrane_permeability"].append([1e-9] * 4)
        p["junction_permeability"].append([1e-9])
        p["face_factor"].append([1e-19] * 2)
        raw["ci"].append([3.0, 4.0])
        raw["co"].append([2.0, 2.5, 3.0])
    elif name == "reversed":
        for prefix in ("face", "junction"):
            a, b = prefix + "_sender", prefix + "_receiver"
            p[a], p[b] = p[b], p[a]
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
        for key in ("ci", "co"):
            for row in raw[key]:
                row.append(1.0)
        for key in ("charge_C", "outside_potential_V", "membrane_open", "junction_open"):
            raw[key].append(0.0)
        for key in (
            "cell_active",
            "outside_active",
            "reservoir",
            "membrane_active",
            "face_active",
            "junction_active",
        ):
            p[key].append(False)
        for key in (
            "membrane_cell",
            "membrane_outside",
            "face_sender",
            "face_receiver",
            "junction_sender",
            "junction_receiver",
        ):
            p[key].append(0)
        for key in ("membrane_area", "membrane_capacitance", "junction_area"):
            p[key].append(0.0)
        for key in ("membrane_permeability", "face_factor", "junction_permeability"):
            for row in p[key]:
                row.append(0.0)
    elif name == "isolated":
        for prefix in ("face", "junction"):
            for key in list(p):
                if key.startswith(prefix + "_"):
                    p[key] = (
                        [[] for _ in range(3)]
                        if key in ("face_factor", "junction_permeability")
                        else []
                    )
        raw["junction_open"] = []
    elif name != "gradient":
        raise ValueError(name)
    return copy.deepcopy(raw)


def arrays(raw):
    def dtype(key):
        if key.endswith("_active") or key == "reservoir":
            return bool
        if key.endswith(("_sender", "_receiver")) or key in ("membrane_cell", "membrane_outside"):
            return np.int64
        return np.float64

    p = model.validate_layout(
        model.Layout(**{k: np.asarray(v, dtype=dtype(k)) for k, v in raw["layout"].items()})
    )
    return (
        *(
            np.asarray(raw[k], dtype=np.float64)
            for k in (
                "ci",
                "co",
                "charge_C",
                "outside_potential_V",
                "membrane_open",
                "junction_open",
            )
        ),
        p,
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_capture():
    """Read only the declared prior capture, checking its receipt and hash chain."""
    binding = json.loads(PROTOCOL_PATH.read_text())["native_binding"]
    root = Path(binding["root"])
    assert digest(root / "completion.json") == binding["completion_sha256"]
    done = json.loads((root / "completion.json").read_text())
    assert done["status"] == "completed"
    assert digest(root / "result.json") == done["result_sha256"]
    panel_path = "evidence/cpu/native/panel.json"
    assert digest(root / panel_path) == done["evidence_sha256"][panel_path]
    panel = json.loads((root / panel_path).read_text())
    selected = binding["row"]
    item = next(r for r in panel["rows"] if r["path"] == selected)
    directory = root / "evidence/cpu/native" / selected
    assert digest(directory / "result.json") == item["sha256"]
    row = json.loads((directory / "result.json").read_text())
    assert digest(directory / "preparation.json") == row["preparation_sha256"]
    assert digest(directory / "trace.npz") == row["trace_sha256"]
    with np.load(directory / "trace.npz", allow_pickle=False) as saved:
        trace = {k: saved[k] for k in saved}
    return row, trace, panel["protocol"], directory


def native_layout(row):
    g, a, p = row["geometry"], row["arrays"], row["parameters"]
    owner = np.asarray(g["mem_to_cells"], dtype=int)
    outside = np.asarray(g["map_mem2ecm"], dtype=int)
    partner = np.asarray(g["nn_i"], dtype=int)
    left = np.flatnonzero(partner > np.arange(len(partner)))
    right = partner[left]
    species = [row["species"][name] for name in ("Na", "K", "Cl")]
    grid = np.arange(np.asarray(g["X"]).size).reshape(np.asarray(g["X"]).shape)
    src = np.r_[grid[:, :-1].ravel(), grid[:-1, :].ravel()]
    dst = np.r_[grid[:, 1:].ravel(), grid[1:, :].ravel()]
    reservoir = np.zeros_like(grid, dtype=bool)
    reservoir[[0, -1], :], reservoir[:, [0, -1]] = True, True
    area = np.asarray(g["mem_sa"])
    permeability = np.asarray(a["D_gj"])[species] * 1e-8 / np.asarray(g["gj_len"])
    # Native grid topology, with declared synthetic finite-volume coefficients.
    # These faces do not reproduce BETSE's distinct centered derivative stencil.
    layout = model.validate_layout(
        model.Layout(
            np.asarray(p["T"]),
            np.asarray(a["zs"])[species, None],
            np.ones(len(g["cell_i"]), bool),
            np.ones(grid.size, bool),
            reservoir.ravel(),
            np.ones(len(owner), bool),
            owner,
            outside,
            area,
            p["cm"] * area,
            np.asarray(a["Dm_cells"])[species] / p["tm"],
            np.ones(len(src), bool),
            src,
            dst,
            np.full((3, len(src)), 1e-19),
            np.ones(len(left), bool),
            owner[left],
            owner[right],
            area[left],
            permeability[:, left],
        )
    )
    return layout, species, left, right
