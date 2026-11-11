"""MG1 tyssue comparison driver: runs tyssue out of process and reads its outputs.

tyssue (GPL-3.0) is never imported here. This driver writes a request JSON, runs
validation/morphogenesis/tyssue_reference/run_tyssue.py with the tyssue
environment's interpreter as a separate process, and compares the saved NPZ
outputs with the independent numpy reference (mg1_reference.py) and, in later
stages, with the engine.

Stage-0 gate (`stage0`): tyssue's pure-Python periodic geometry must accept the
periodic honeycomb tables of apical_vertex_mechanics@1, and its static energy and
gradient (after two geometry updates) must match the independent reference on a
perturbed lattice, before any dynamics comparison.

  PYTHONPATH=src:. JAX_ENABLE_X64=1 taskset -c 5 python -m validation.morphogenesis.mg1_tyssue \
      stage0 --output RUN_DIR
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

import numpy as np

from validation.morphogenesis import mg1_reference as ref
from validation.morphogenesis import mg1_theory as theory

RUNNER = Path(__file__).resolve().parent / "tyssue_reference" / "run_tyssue.py"
DEFAULT_PYTHON = "/mnt/workspaces/Cells/venv-tyssue/bin/python"


def run_tyssue(definition, operations, out_dir, *, python=None):
    """Run the GPL runner in its own environment; returns {name: dict of arrays}."""
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    request = out_dir.with_suffix(".request.json")
    request.write_text(json.dumps({"definition": definition, "operations": operations}))
    python = python or os.environ.get("CELLS_TYSSUE_PYTHON", DEFAULT_PYTHON)
    done = subprocess.run(
        [python, "-I", str(RUNNER), str(request), str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    (out_dir.with_suffix(".log")).write_text(done.stdout + "\n--- stderr ---\n" + done.stderr)
    if done.returncode:
        raise RuntimeError(f"tyssue runner failed ({done.returncode}); see {out_dir}.log")
    results = {}
    for op in operations:
        with np.load(out_dir / f"{op['name']}.npz") as data:
            results[op["name"]] = {k: data[k] for k in data.files}
    results["environment"] = json.loads((out_dir / "environment.json").read_text())
    return results


def modulo_box(delta, box):
    """Differences of positions reduced to the nearest periodic image (rectangular box)."""
    period = np.diag(box)
    return delta - period * np.round(delta / period)


def honeycomb(nx, ny, *, displacement, seed, line_tension=0.12, contractility=0.04):
    from cells.core import vertex_preparation as prep

    a = theory.ground_state(line_tension, contractility)[0]
    model = prep.periodic_honeycomb(
        nx,
        ny,
        cell_area=a,
        line_tension=line_tension,
        contractility=contractility,
        displacement=displacement,
        seed=seed,
    )
    return prep.definition(model, end_time=1.0, observation_times=[0.0], dt=0.01)


def farhadifar_cut(definition, junction):
    """Overrides that cut one junction: its line tension and both cells' contractility."""
    model = definition["model"]
    j = model["junctions"][junction]
    a, b = j["vertices"]
    cells = [
        c["id"]
        for c in model["cells"]
        if any(
            k["vertex"] == a
            and c["corners"][(n + 1) % len(c["corners"])]["vertex"] == b
            or k["vertex"] == b
            and c["corners"][(n + 1) % len(c["corners"])]["vertex"] == a
            for n, k in enumerate(c["corners"])
        )
    ]
    return {
        "time": 0.0,
        "line_tension": {j["id"]: 0.0},
        "contractility": {c: 0.0 for c in cells},
        "area_elasticity": {},
        "preferred_area": {},
    }


def stage0(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {"gate": "mg1-stage0-tyssue-periodic", "cases": {}}
    for name, nx, ny, sigma in (("hex12_perturbed", 12, 12, 0.05), ("hex4_perturbed", 4, 4, 0.05)):
        definition = honeycomb(nx, ny, displacement=sigma, seed=0)
        cut = farhadifar_cut(definition, junction=0)
        tissue = ref.from_definition(definition)
        cut_tissue = ref.with_control(tissue, cut)
        x0 = tissue.position
        steps, dt = 20, 0.02
        operations = [
            {"kind": "static", "name": "static"},
            {"kind": "static", "name": "static_cut", "control": cut},
            {"kind": "euler", "name": "euler", "dt": dt, "steps": steps},
        ]
        results = run_tyssue(definition, operations, output / name)
        case = {"cells": tissue.cells, "vertices": len(x0)}
        for key, t in (("static", tissue), ("static_cut", cut_tissue)):
            e_ref, g_ref = ref.energy(t, x0), ref.gradient(t, x0)
            r = results[key]
            case[key] = {
                "energy_reference": e_ref,
                "energy_tyssue": float(r["energy"]),
                "energy_relative_difference": abs(float(r["energy"]) - e_ref) / abs(e_ref),
                "gradient_max_abs_difference": float(np.max(np.abs(r["gradient"] - g_ref))),
                "gradient_scale": float(np.max(np.abs(g_ref))),
                "rewrap_position_difference": float(
                    np.max(np.abs(modulo_box(r["position"] - x0, tissue.box)))
                ),
            }
        x = x0.copy()
        for _ in range(steps):
            x = x - dt * ref.gradient(tissue, x) / tissue.friction[:, None]
        tyssue_final = results["euler"]["position"][-1]
        case["euler_parity"] = {
            "steps": steps,
            "dt": dt,
            "max_position_difference_mod_box": float(
                np.max(np.abs(modulo_box(tyssue_final - x, tissue.box)))
            ),
        }
        case["reference_self_check"] = ref.self_check(tissue, x0)
        report["cases"][name] = case
    report["environment"] = results["environment"]
    worst = max(
        max(c[k]["energy_relative_difference"] for k in ("static", "static_cut"))
        for c in report["cases"].values()
    )
    worst_gradient = max(
        max(c[k]["gradient_max_abs_difference"] for k in ("static", "static_cut"))
        for c in report["cases"].values()
    )
    worst_euler = max(
        c["euler_parity"]["max_position_difference_mod_box"] for c in report["cases"].values()
    )
    report["verdict"] = {
        "energy_relative_max": worst,
        "gradient_abs_max": worst_gradient,
        "euler_position_max": worst_euler,
        "pass": bool(worst <= 1e-12 and worst_gradient <= 1e-10 and worst_euler <= 1e-10),
        "criteria": "energy <= 1e-12 relative; gradient <= 1e-10 absolute; 20 Euler steps <= 1e-10",
    }
    (output / "stage0.json").write_text(json.dumps(report, indent=1))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    s0 = sub.add_parser("stage0")
    s0.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "stage0":
        report = stage0(args.output)
        print(json.dumps(report["verdict"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
