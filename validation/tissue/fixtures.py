"""Synthetic field witnesses; concentrations are mM, geometry is SI, no fit."""

import copy

import numpy as np


def definition(name="gradient"):
    three = name in ("triangle", "triangle_padded", "divalent")
    n = 3 if three else 2
    data = {
        "ci": [[12.0, 15.0, 13.0][:n], [140.0, 130.0, 135.0][:n], [8.0, 10.0, 9.0][:n]],
        "co": [[140.0, 120.0, 150.0][:n], [4.0, 8.0, 3.0][:n], [110.0, 105.0, 115.0][:n]],
        "membrane_voltage": [-0.06, -0.04, -0.05][:n],
        "gate": [0.6, 0.7, 0.8] if three else [0.6],
        "availability": [1.0] * (3 if three else 1),
        "layout": {
            "temperature": 298.15,
            "valence": [[1], [1], [-1]],
            "cell_active": [True] * n,
            "cell_outside": list(range(n)),
            "extracellular_active": [True] * n,
            "gauge_mask": [True] + [False] * (n - 1),
            "face_active": [True] * (3 if three else 1),
            "face_senders": [0, 1, 2] if three else [0],
            "face_receivers": [1, 2, 0] if three else [1],
            "face_factor": [[v] * (3 if three else 1) for v in (6e-20, 8.5e-20, 1e-19)],
            "junction_active": [True] * (3 if three else 1),
            "junction_senders": [0, 1, 2] if three else [0],
            "junction_receivers": [1, 2, 0] if three else [1],
            "junction_area": [1e-10] * (3 if three else 1),
            "junction_permeability": [[v] * (3 if three else 1) for v in (3e-10, 5e-10, 4e-10)],
        },
    }
    p = data["layout"]
    if name in ("equal", "zero_drive", "reverse"):
        for key in ("ci", "co"):
            data[key] = [[row[0]] * n for row in data[key]]
        if name == "zero_drive":
            data["membrane_voltage"] = [-0.05] * n
        if name == "reverse":
            data["membrane_voltage"].reverse()
    elif name == "blocked":
        data["availability"] = [0.0]
    elif name == "same_region":
        p["cell_outside"] = [0, 0]
    elif name in ("narrow_return", "wide_return"):
        scale = 0.001 if name == "narrow_return" else 1000.0
        p["face_factor"] = [[v * scale for v in row] for row in p["face_factor"]]
    elif name == "divalent":
        p["valence"].append([2])
        p["face_factor"].append([4e-20] * 3)
        p["junction_permeability"].append([2e-10] * 3)
        data["ci"].append([0.0001, 0.0002, 0.00015])
        data["co"].append([1.8, 2.0, 1.9])
    elif name not in ("gradient", "triangle", "triangle_padded"):
        raise ValueError("Unknown tissue field witness: " + name)
    if name == "triangle_padded":
        for key in ("ci", "co"):
            data[key] = [row + [1.0] for row in data[key]]
        data["membrane_voltage"].append(0.0)
        data["gate"].append(0.0)
        data["availability"].append(0.0)
        for key in (
            "cell_active",
            "extracellular_active",
            "gauge_mask",
            "face_active",
            "junction_active",
        ):
            p[key].append(False)
        for key in (
            "cell_outside",
            "face_senders",
            "face_receivers",
            "junction_senders",
            "junction_receivers",
        ):
            p[key].append(0)
        p["junction_area"].append(1.0)
        for key in ("face_factor", "junction_permeability"):
            p[key] = [row + [0.0] for row in p[key]]
    return copy.deepcopy(data)


CASES = (
    "gradient",
    "equal",
    "zero_drive",
    "reverse",
    "blocked",
    "same_region",
    "narrow_return",
    "wide_return",
    "triangle",
    "triangle_padded",
    "divalent",
)


def arrays(data):
    from cells.numerics.tissue_field import Layout, validate_layout

    layout = validate_layout(Layout(**{k: np.asarray(v) for k, v in data["layout"].items()}))
    return (
        *(
            np.asarray(data[k], dtype=np.float64)
            for k in ("ci", "co", "membrane_voltage", "gate", "availability")
        ),
        layout,
    )
