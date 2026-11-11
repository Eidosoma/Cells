# SPDX-License-Identifier: GPL-3.0-or-later
# This one file is licensed GPL-3.0-or-later because it imports tyssue (GPL-3.0)
# at run time; the rest of the Cells repository stays MIT. Do not import this
# file, or tyssue, from src/ or from any MIT file. Run it only as a separate
# process with the tyssue environment's interpreter:
#
#   /mnt/workspaces/Cells/venv-tyssue/bin/python -I run_tyssue.py REQUEST.json OUT_DIR
#
"""Run tyssue 1.1.0, unmodified, on an apical_vertex_mechanics@1 definition.

MG1's out-of-process reference (docs/MORPHOGENESIS_PLAN.md; recipe and stage-0
findings in /mnt/workspaces/Cells/morphogenesis-mg1-20261111-01/stage0-tyssue-smoke).
The request JSON holds a definition (the Cells JSON, read here as plain data) and
a list of operations; each writes OUT_DIR/<name>.npz. Supported:

  static  energy (total and per term) and gradient at the definition's positions,
          optionally under a parameter control (the definition's override format)
  relax   scipy L-BFGS over tyssue's own energy and gradient at the fixed box
  euler   forward Euler written here over tyssue's gradient, a fixed number of
          updates, with optional parameter switches at given step numbers
  euler_shipped  tyssue's own EulerSolver.solve, reported as shipped

Two properties of tyssue 1.1.0 found in stage 0 shape this runner. Its
PlanarGeometry.update_all normalizes edge vectors before it updates lengths, so
gradients are exact only after two updates at the same positions; every gradient
here follows two updates. Its periodic QSSolver also relaxes a square box size,
so relaxations use scipy directly at the definition's fixed rectangular box.
Periodic boundaries are axis-aligned in tyssue, so only rectangular periods are
accepted. tyssue re-wraps vertices into the box; positions are written as tyssue
holds them and must be compared modulo the box.
"""

import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import tyssue
from scipy import optimize
from tyssue import PlanarGeometry, Sheet
from tyssue.dynamics import effectors, model_factory
from tyssue.solvers.viscous import EulerSolver

EFFECTORS = (effectors.FaceAreaElasticity, effectors.LineTension, effectors.FaceContractility)


def corner_junctions(model):
    """Junction index of each cell corner's outgoing edge (matched by periodic image)."""
    declared = {}
    for i, j in enumerate(model["junctions"]):
        a, b = j["vertices"]
        declared[(a, b, *j["image"])] = i
        declared[(b, a, -j["image"][0], -j["image"][1])] = i
    rows = []
    for c in model["cells"]:
        k = c["corners"]
        for n, corner in enumerate(k):
            following = k[(n + 1) % len(k)]
            d = [
                following["image"][0] - corner["image"][0],
                following["image"][1] - corner["image"][1],
            ]
            rows.append(declared[(corner["vertex"], following["vertex"], *d)])
    return rows


def overrides(model, control):
    lam = {j["id"]: j["line_tension"] for j in model["junctions"]}
    cells = {
        kind: {c["id"]: c[kind] for c in model["cells"]}
        for kind in ("contractility", "area_elasticity", "preferred_area")
    }
    for key, value in (control or {}).get("line_tension", {}).items():
        lam[key] = value
    for kind in cells:
        for key, value in (control or {}).get(kind, {}).items():
            cells[kind][key] = value
    return lam, cells


def build_sheet(definition, control=None):
    model = definition["model"]
    (ax, ay), (bx, by) = model["periods"]
    if ay != 0.0 or bx != 0.0:
        raise ValueError("tyssue periodic boundaries are axis-aligned: rectangular periods only")
    slot = {v["id"]: i for i, v in enumerate(model["vertices"])}
    vert = pd.DataFrame([v["position"] for v in model["vertices"]], columns=["x", "y"])
    rows, face = [], []
    for f, c in enumerate(model["cells"]):
        k = c["corners"]
        for n, corner in enumerate(k):
            rows.append((slot[corner["vertex"]], slot[k[(n + 1) % len(k)]["vertex"]], f))
        face.append((0.0, 0.0))
    sheet = Sheet(
        "cells-mg1",
        {
            "vert": vert,
            "edge": pd.DataFrame(rows, columns=["srce", "trgt", "face"]),
            "face": pd.DataFrame(face, columns=["x", "y"]),
        },
        coords=["x", "y"],
    )
    sheet.update_specs(
        {
            "face": {
                "area_elasticity": 1.0,
                "prefered_area": 1.0,
                "contractility": 0.0,
                "is_alive": 1,
            },
            "edge": {"line_tension": 0.0, "is_active": 1},
            "vert": {"viscosity": 1.0, "is_active": 1},
        },
        reset=True,
    )
    sheet.settings["boundaries"] = {"x": [0.0, float(ax)], "y": [0.0, float(by)]}
    sheet.vert_df["viscosity"] = [v["friction"] for v in model["vertices"]]
    apply_control(sheet, definition, control)
    return sheet


def apply_control(sheet, definition, control):
    model = definition["model"]
    lam, cells = overrides(model, control)
    junction = corner_junctions(model)
    sheet.edge_df["line_tension"] = [lam[model["junctions"][j]["id"]] for j in junction]
    ids = [c["id"] for c in model["cells"]]
    sheet.face_df["contractility"] = [cells["contractility"][i] for i in ids]
    sheet.face_df["area_elasticity"] = [cells["area_elasticity"][i] for i in ids]
    sheet.face_df["prefered_area"] = [cells["preferred_area"][i] for i in ids]
    update(sheet)


def update(sheet):
    PlanarGeometry.update_all(sheet)
    PlanarGeometry.update_all(sheet)  # Second pass: unit vectors from current lengths.


def positions(sheet):
    return sheet.vert_df[["x", "y"]].to_numpy(copy=True)


def set_positions(sheet, x):
    sheet.vert_df[["x", "y"]] = x
    update(sheet)


def evaluate(sheet, model):
    terms = [float(np.sum(e.energy(sheet))) for e in EFFECTORS]
    grad = model.compute_gradient(sheet).loc[sheet.vert_df.index].to_numpy()
    return float(model.compute_energy(sheet)), terms, grad


def run_static(definition, op, model):
    sheet = build_sheet(definition, op.get("control"))
    energy, terms, grad = evaluate(sheet, model)
    return {
        "energy": energy,
        "terms": np.array(terms),
        "gradient": grad,
        "position": positions(sheet),
    }


def run_relax(definition, op, model):
    sheet = build_sheet(definition, op.get("control"))
    shape = positions(sheet).shape

    def fun(flat):
        set_positions(sheet, flat.reshape(shape))
        energy, _, grad = evaluate(sheet, model)
        return energy, grad.ravel()

    result = optimize.minimize(
        fun,
        positions(sheet).ravel(),
        jac=True,
        method="L-BFGS-B",
        options={
            "maxiter": op.get("maxiter", 100000),
            "maxcor": 50,
            "gtol": op.get("gtol", 1e-12),
            "ftol": 1e-18,
        },
    )
    set_positions(sheet, result.x.reshape(shape))
    energy, terms, grad = evaluate(sheet, model)
    return {
        "energy": energy,
        "terms": np.array(terms),
        "gradient": grad,
        "position": positions(sheet),
        "iterations": np.array(result.nit),
        "max_gradient": np.array(np.max(np.abs(grad))),
    }


def run_euler(definition, op, model):
    """x_{n+1} = x_n - dt grad E(x_n) / eta, gradient after two geometry updates."""
    sheet = build_sheet(definition, op.get("control"))
    switches = {int(s["step"]): s["control"] for s in op.get("schedule", [])}
    dt, steps, every = float(op["dt"]), int(op["steps"]), int(op.get("record_every", 1))
    eta = sheet.vert_df["viscosity"].to_numpy()[:, None]
    record, energies = [positions(sheet)], []
    for n in range(steps):
        if n in switches:
            apply_control(sheet, definition, switches[n])
        energy, _, grad = evaluate(sheet, model)
        energies.append(energy)
        set_positions(sheet, positions(sheet) - dt * grad / eta)
        if (n + 1) % every == 0:
            record.append(positions(sheet))
    return {"position": np.array(record), "energy_before_step": np.array(energies)}


def run_euler_shipped(definition, op, model):
    """tyssue's EulerSolver as shipped (one geometry update per step)."""
    sheet = build_sheet(definition, op.get("control"))
    solver = EulerSolver(sheet, PlanarGeometry, model)
    start = positions(sheet)
    dt, updates = float(op["dt"]), int(op["updates"])
    # solve() takes one update per element of arange(prev_t, tf + dt, dt).
    tf = (updates - 1) * dt
    taken = len(np.arange(0.0, tf + dt, dt))
    solver.solve(tf=tf, dt=dt)
    return {"start": start, "position": positions(sheet), "updates_taken": np.array(taken)}


OPERATIONS = {
    "static": run_static,
    "relax": run_relax,
    "euler": run_euler,
    "euler_shipped": run_euler_shipped,
}


def main(argv):
    request, out = json.loads(Path(argv[1]).read_text()), Path(argv[2])
    out.mkdir(parents=True, exist_ok=False)
    definition = request["definition"]
    model = model_factory(list(EFFECTORS))
    names = []
    for op in request["operations"]:
        result = OPERATIONS[op["kind"]](definition, op, model)
        np.savez(out / f"{op['name']}.npz", **result)
        names.append(op["name"])
    environment = {
        "tyssue": getattr(tyssue, "__version__", "1.1.0 (no __version__ attribute)"),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "python": platform.python_version(),
        "executable": sys.executable,
        "operations": names,
        "geometry_updates_per_gradient": 2,
    }
    (out / "environment.json").write_text(json.dumps(environment, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
