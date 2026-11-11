"""Prepare apical_vertex_mechanics@1 definitions: periodic honeycomb tissues.

Preparation geometry only (no physics). A pointy-top honeycomb of nx x ny cells
(ny even) tiles a rectangular periodic box. Vertices lie on an integer grid in units
(sqrt(3) s / 2, s / 2) with s the hexagon side, so deduplication and periodic
images are exact. An optional seeded Gaussian displacement breaks the symmetry
(numpy PCG64; the seed and amplitude are part of the request).
"""

import numpy as np

from cells.core.apical_vertex_spec import MODEL_ID, UNITS
from cells.core.specs import ConfigError

# Corner offsets of a pointy-top hexagon on the grid, counterclockwise from 30 degrees.
_OFFSETS = ((1, 1), (0, 2), (-1, 1), (-1, -1), (0, -2), (1, -1))


def hexagon_side(cell_area):
    return float(np.sqrt(2.0 * cell_area / (3.0 * np.sqrt(3.0))))


def periodic_honeycomb(
    nx,
    ny,
    *,
    cell_area,
    line_tension,
    contractility,
    area_elasticity=1.0,
    preferred_area=1.0,
    friction=1.0,
    length_floor=1e-3,
    displacement=0.0,
    seed=0,
):
    """The model block of a periodic honeycomb definition (JSON-ready)."""
    if type(nx) is not int or type(ny) is not int or nx < 2 or ny < 2 or ny % 2:
        raise ConfigError("A periodic honeycomb needs integer nx >= 2 and even ny >= 2")
    side = hexagon_side(cell_area)
    unit = np.array([np.sqrt(3.0) * side / 2.0, side / 2.0])
    period = np.array([2 * nx, 3 * ny])
    keys, cells, junctions, seen = {}, [], [], {}
    for j in range(ny):
        for i in range(nx):
            centre = np.array([2 * i + (j % 2), 3 * j])
            corners = []
            for offset in _OFFSETS:
                grid = centre + offset
                wrapped, image = np.mod(grid, period), np.floor_divide(grid, period)
                key = (int(wrapped[0]), int(wrapped[1]))
                keys.setdefault(key, len(keys))
                corners.append((keys[key], (int(image[0]), int(image[1]))))
            cells.append(corners)
    for corners in cells:
        for k, (a, na) in enumerate(corners):
            b, nb = corners[(k + 1) % 6]
            d = (nb[0] - na[0], nb[1] - na[1])
            canonical = (a, b, *d) if a < b else (b, a, -d[0], -d[1])
            if canonical not in seen:
                seen[canonical] = len(junctions)
                junctions.append((a, b, d))
    position = np.array([np.array(k) * unit for k in sorted(keys, key=keys.get)])
    if displacement:
        rng = np.random.Generator(np.random.PCG64(seed))
        position = position + displacement * rng.standard_normal(position.shape)
    return {
        "id": MODEL_ID,
        "units": UNITS,
        "periods": [[float(period[0] * unit[0]), 0.0], [0.0, float(period[1] * unit[1])]],
        "length_floor": length_floor,
        "vertices": [
            {"id": f"v{n}", "position": [float(p[0]), float(p[1])], "friction": friction}
            for n, p in enumerate(position)
        ],
        "junctions": [
            {
                "id": f"j{n}",
                "vertices": [f"v{a}", f"v{b}"],
                "image": list(d),
                "line_tension": line_tension,
            }
            for n, (a, b, d) in enumerate(junctions)
        ],
        "cells": [
            {
                "id": f"c{n}",
                "corners": [{"vertex": f"v{v}", "image": list(m)} for v, m in corners],
                "area_elasticity": area_elasticity,
                "preferred_area": preferred_area,
                "contractility": contractility,
            }
            for n, corners in enumerate(cells)
        ],
    }


def definition(
    model,
    *,
    end_time,
    observation_times,
    dt,
    solver="rk4",
    parameter_controls=None,
    jit=True,
    backend="cpu",
    max_steps=10**7,
    max_trace_bytes=2**34,
    padding=0,
):
    """A complete definition around a model block; padding adds spare capacity."""
    corners = sum(len(c["corners"]) for c in model["cells"])
    controls = parameter_controls or [
        {
            "time": 0.0,
            "line_tension": {},
            "contractility": {},
            "area_elasticity": {},
            "preferred_area": {},
        }
    ]
    return {
        "schema_version": 1,
        "model": model,
        "experiment": {
            "end_time": float(end_time),
            "observation_times": [float(t) for t in observation_times],
            "parameter_controls": controls,
        },
        "execution": {
            "dt": float(dt),
            "capacity": len(model["cells"]) + padding,
            "vertex_capacity": len(model["vertices"]) + 2 * padding,
            "junction_capacity": len(model["junctions"]) + 3 * padding,
            "half_edge_capacity": corners + 6 * padding,
            "jit": jit,
            "max_steps": max_steps,
            "max_trace_bytes": max_trace_bytes,
            "backend": backend,
            "precision": "float64",
            "solver": solver,
        },
    }
