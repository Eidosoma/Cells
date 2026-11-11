"""MG1 reference values, computed before registration by the independent reference only.

numpy/scipy (mg1_reference.py) and the analytic values (mg1_theory.py); no Cells
dynamics or analysis code runs here. The only shared input is the definition JSON,
built by the driver's honeycomb helpers (preparation geometry). The output is
embedded in the protocol as registered_predictions.reference_values (run it from a
clean commit and keep its output and revision with the evidence).

  PYTHONPATH=src:. taskset -c 5 python -m validation.morphogenesis.mg1_references \\
      --output EVIDENCE_DIR/mg1_reference_values_v1.json

Values:
  barriers   ordered 8 x 8 networks in the incompatible regime (unique minima):
             scipy relaxation of the registered perturbed definition, then the
             quasi-static contraction of three junction orientations
  moduli     relaxed shear and bulk curvatures by finite strain of scipy-relaxed
             4 x 4 lattices (a numeric check of the closed forms)
  recoil     the exact regular 12 x 12 case-I lattice: the opening rate of the
             Farhadifar cut, the linear small-cut response (opening per unit cut
             fraction at registered times, effective time) and the relaxed full cut
             (opening d1, change of the two cut cells' area and perimeter)
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from validation.morphogenesis import mg1_reference as ref
from validation.morphogenesis import mg1_theory as theory
from validation.morphogenesis import mg1_vertex as driver


def _tissue(model, control=None):
    return ref.from_definition(
        {"model": model, "experiment": {"parameter_controls": [control or {}]}}
    )


def barriers(quick=False):
    rows = []
    rs = (1.0,) if quick else (0.1, 1.0, 10.0)
    points = (3.7,) if quick else (3.5, 3.7)
    fractions = np.array((1.0, 0.5, 0.0) if quick else driver.FRACTIONS)
    for r in rs:
        for p0 in points:
            model = driver.staddon_model(4 if quick else 8, r, p0, sigma=0.02, seed=0)
            tissue = _tissue(model)
            x, force, _ = ref.relax(tissue, tissue.position, gtol=1e-12, polish=True)
            for k, junction in enumerate(driver.orientation_junctions(model)):
                energies, _, length0 = ref.contraction(tissue, x, junction, fractions, polish="end")
                rows.append(
                    {
                        "r": r,
                        "p0": p0,
                        "orientation": k,
                        "junction": junction,
                        "relaxed_max_force": force,
                        "barrier": float(energies[-1] - energies[0]),
                        "energies": energies.tolist(),
                        "initial_length": length0,
                    }
                )
    return rows


def moduli(quick=False):
    rows = []
    for r, p0 in ((1.0, 3.6),) if quick else ((0.04, 3.0), (0.1, 3.5), (1.0, 3.6)):
        model = driver.staddon_model(4, r, p0, sigma=0.02, seed=0)
        tissue = _tissue(model)
        x, _, _ = ref.relax(tissue, tissue.position, gtol=1e-12)
        area = float(np.linalg.det(tissue.box))
        shear = ref.relaxed_curvature(tissue, x, [[0.0, 1.0], [0.0, 0.0]]) / area
        bulk = ref.relaxed_curvature(tissue, x, np.eye(2)) / (4 * area)
        g, b = theory.moduli(r, p0)
        rows.append(
            {
                "r": r,
                "p0": p0,
                "G_reference": shear,
                "B_reference": bulk,
                "G_theory": g,
                "B_theory": b,
                "G_rel_difference": abs(shear - g) / g,
                "B_rel_difference": abs(bulk - b) / b,
            }
        )
    return rows


RECOIL_TIMES = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)


def recoil(quick=False):
    n = 4 if quick else 12
    model = driver.honeycomb(n)
    junction = driver.central_junction(model)
    before = _tissue(model)
    x = before.position
    cut = driver.cut_control(model, junction, 1.0, 0.0)[1]
    after = ref.with_control(before, cut)
    tail, head = before.junction_tail[junction], before.junction_head[junction]
    d = x[head] + before.junction_image[junction] @ before.box.T - x[tail]
    d0 = float(np.linalg.norm(d))
    jump = ref.velocity_jump(before, after, x)
    rate = float((jump[head] - jump[tail]) @ (d / d0))
    eps = 1e-4
    small = ref.with_control(before, driver.cut_control(model, junction, eps, 0.0)[1])
    opening, rate_small, tau = ref.linear_recoil(before, small, x, junction, RECOIL_TIMES)
    relaxed, force, _ = ref.relax(after, x, gtol=1e-12, polish=True)
    d1 = relaxed[head] + before.junction_image[junction] @ before.box.T - relaxed[tail]
    cells = [before.cell_ids.index(c) for c in cut["contractility"]]
    area0, perimeter0, _ = ref.geometry(after, x)
    area1, perimeter1, _ = ref.geometry(after, relaxed)
    return {
        "n": n,
        "junction": junction,
        "initial_length": d0,
        "opening_rate": rate,
        "opening_rate_theory": theory.recoil_opening_rate(
            driver.LAMBDA, driver.GAMMA, theory.ground_state(driver.LAMBDA, driver.GAMMA)[1]
        ),
        "small_cut_fraction": eps,
        "small_cut_times": list(RECOIL_TIMES),
        "small_cut_opening_per_fraction": (opening / eps).tolist(),
        "small_cut_rate_per_fraction": rate_small / eps,
        "small_cut_tau_effective": tau,
        "full_cut_relaxed_max_force": force,
        "full_cut_opening_d1": float(np.linalg.norm(d1) - d0),
        "full_cut_cell_area_change": float(np.sum(area1[cells] - area0[cells])),
        "full_cut_cell_perimeter_change": float(np.sum(perimeter1[cells] - perimeter0[cells])),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    t0 = time.perf_counter()
    values = {
        "kind": "cells.morphogenesis_mg1_reference_values@1",
        "independence": "numpy/scipy reference and closed forms; the definition JSON is shared",
        "quick": args.quick,
        "barriers": barriers(args.quick),
        "moduli": moduli(args.quick),
        "recoil": recoil(args.quick),
    }
    values["wall_seconds"] = time.perf_counter() - t0
    with args.output.open("x") as stream:
        json.dump(values, stream, indent=1)
    print(f"wrote {args.output} in {values['wall_seconds']:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
