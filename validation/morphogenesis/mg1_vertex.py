"""MG1 driver: passive 2-D apical vertex mechanics (apical_vertex_mechanics@1).

Engine models: apical_vertex_mechanics@1 (dynamics), mechanical_equilibrium_analysis@1
(minima, moduli, barriers) and junction_tension_inference@1. References: the
analytic hexagonal-network values (mg1_theory.py), the independent numpy/scipy
reference (mg1_reference.py, no Cells code) and tyssue 1.1.0 run out of process
(mg1_tyssue.py). The protocol is validation/morphogenesis/protocols/mg1_vertex_mechanics_v1.json.

Parts (each writes DIR/<part>.json; a failed part is kept as evidence):
  theory      analytic predictions (registered values)
  ground      G: case-I/II ground state by engine relaxation; box stress and scan;
              box relaxation to a*
  rigidity    S: ordered-network shear and bulk moduli against Staddon 2023; the
              compatible regime; sheared-box engine relaxations; the zero of G
  barrier     B: quasi-static T1 contraction barriers of the ordered network
  recoil      R: Farhadifar cut: velocity jump, opening rate, small-cut linear
              response, full-cut relaxation against the reference minimizer
  inference   I: synthetic tension inference
  numerics    N: time-step orders, energy-balance allowance, restart, refusals,
              jax.grad against the closed form
  tyssue      T: static, relaxation, Euler and cut parity, pure-shear modulus

  PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu taskset -c 4,5 python -m \\
      validation.morphogenesis.mg1_vertex all --output RUN_DIR --protocol PROTOCOL
  ... judge --output RUN_DIR --protocol PROTOCOL   re-evaluates RUN_DIR/results.json

--quick runs a reduced development scale (never judged).
"""

import argparse
import copy
import json
import resource
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.morphogenesis import mg1_reference as ref
from validation.morphogenesis import mg1_theory as theory
from validation.morphogenesis.mg0a_gradient import _jsonable, evaluate

MODEL_ID = "apical_vertex_mechanics@1"
LAMBDA, GAMMA = 0.12, 0.04  # Farhadifar 2007 case I
CASE_II = (0.0, 0.1)
EULER_DT = 0.0625  # dt * rho = 0.79 for case I (rho 12.6); tyssue parity steps
STEP_FRACTION = 0.5  # driver runs use dt * rho0 <= 0.5 x the solver bound
WINDOW_STEPS = 4096
# Relaxation horizons (eta/(K A0)) from the slowest shear mode, about G k_min^2 a_v,
# for |F| below 1e-10 from the prepared perturbation.
HORIZON = {4: 400.0, 8: 800.0, 12: 1200.0, 16: 2000.0}


# --- definitions -------------------------------------------------------------------------


def honeycomb(n, *, line_tension=LAMBDA, contractility=GAMMA, area=None, sigma=0.0, seed=0):
    from cells.core import vertex_preparation as prep

    if area is None:
        area = theory.ground_state(line_tension, contractility)[0]
    return prep.periodic_honeycomb(
        n,
        n,
        cell_area=area,
        line_tension=line_tension,
        contractility=contractility,
        displacement=sigma,
        seed=seed,
    )


def stable_dt(model, solver="rk4"):
    """The largest power of two with dt * rho(initial) <= STEP_FRACTION x the bound."""
    from cells.core import vertex_preparation as prep
    from cells.core.specs import parse_spec
    from cells.models import apical_vertex as av
    from cells.processes import vertex_mechanics as vm

    spec = parse_spec(prep.definition(model, end_time=1.0, observation_times=[0.0], dt=1e-6))
    state, layout = av.initial_values(spec)
    rho = vm.hessian_rate(
        state.position, av.topology(layout), layout.box, av.mechanics(state), layout.friction, xp=np
    )
    bound = 2.0 if solver == "rk4" else 1.0
    return float(2.0 ** np.floor(np.log2(STEP_FRACTION * bound / rho)))


def definition(model, *, end, observe, dt=None, solver="rk4", controls=None):
    from cells.core import vertex_preparation as prep

    dt = stable_dt(model, solver) if dt is None else dt
    return prep.definition(
        model,
        end_time=end,
        observation_times=sorted(set([0.0, *observe, end])),
        dt=dt,
        solver=solver,
        parameter_controls=controls,
    )


def staddon_model(n, r, p0, *, sigma=0.02, seed=0):
    """An ordered network in Staddon's parameters (Lambda = -2 r p0, Gamma = r)."""
    area = theory.hexagon_state(r, p0)[0] if p0 < theory.P_STAR else 1.0
    return honeycomb(
        n, line_tension=-2.0 * r * p0, contractility=r, area=area, sigma=sigma, seed=seed
    )


def with_positions(model, x):
    model = copy.deepcopy(model)
    for v, p in zip(model["vertices"], np.asarray(x), strict=False):
        v["position"] = [float(p[0]), float(p[1])]
    return model


def sheared(model, gamma):
    """Simple shear x += gamma y of the positions and of the periodic box."""
    model = copy.deepcopy(model)
    (ax, ay), (bx, by) = model["periods"]
    model["periods"] = [[ax, ay], [bx + gamma * by, by]]
    for v in model["vertices"]:
        x, y = v["position"]
        v["position"] = [x + gamma * y, y]
    return model


def cut_control(model, junction, fraction, time):
    """Farhadifar's cut scaled by fraction: Lambda_ij and both cells' Gamma times (1 - f)."""
    j = model["junctions"][junction]
    a, b = j["vertices"]
    cells = []
    for c in model["cells"]:
        k = c["corners"]
        edges = {(k[n]["vertex"], k[(n + 1) % len(k)]["vertex"]) for n in range(len(k))}
        if (a, b) in edges or (b, a) in edges:
            cells.append(c)
    keep = 1.0 - fraction
    empty = {"line_tension": {}, "contractility": {}, "area_elasticity": {}, "preferred_area": {}}
    return [
        {"time": 0.0, **copy.deepcopy(empty)},
        {
            "time": time,
            "line_tension": {j["id"]: keep * j["line_tension"]},
            "contractility": {c["id"]: keep * c["contractility"] for c in cells},
            "area_elasticity": {},
            "preferred_area": {},
        },
    ]


def run_engine(defn, window_steps=WINDOW_STEPS):
    """Windowed engine run (bounded memory); observations concatenated across windows."""
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, run_windowed

    spec = parse_spec(defn)
    collected = []
    result = run_windowed(
        spec,
        WindowPolicy(window_steps=window_steps),
        sink=lambda w: collected.append(w.observations),
    )
    fields = list(vars(collected[0]))
    observations = SimpleNamespace(
        **{k: np.concatenate([np.asarray(getattr(o, k)) for o in collected]) for k in fields}
    )
    return SimpleNamespace(
        observations=observations,
        final=result.final,
        diagnostics=result.diagnostics,
        timings=result.timings,
        dt=spec.execution.dt,
    )


def _diagnostics(result):
    d = result.diagnostics
    return {
        "allowance_used": d["max_energy_balance_allowance_used"],
        "momentum_drift": d["max_momentum_drift"],
        "area_identity_error": d["max_area_identity_error"],
        "min_junction_length": 1.0 / d["max_inverse_min_junction_length"],
        "dt": result.dt,
    }


def central_junction(model):
    """The junction whose midpoint is nearest the box centre, on the regular lattice.

    Chosen on the regular honeycomb of the same size (same topology and slots), so
    the choice does not depend on perturbed or relaxed positions.
    """
    n = int(round(np.sqrt(len(model["cells"]))))
    tissue = ref.from_definition(
        {"model": honeycomb(n), "experiment": {"parameter_controls": [{}]}}
    )
    x = tissue.position
    d = ref.junction_vectors(tissue, x)
    middle = x[tissue.junction_tail] + 0.5 * d
    centre = 0.5 * (tissue.box[:, 0] + tissue.box[:, 1])
    return int(np.argmin(np.linalg.norm(middle - centre, axis=1)))


def _ref_tissue(defn, control=None):
    return ref.from_definition(defn, control)


# --- parts --------------------------------------------------------------------------------


def part_theory(args):
    return theory.predictions()


def part_ground(args):
    quick = args.quick
    a_star, p, side, e_star = theory.ground_state(LAMBDA, GAMMA)
    horizon = 200.0 if quick else 800.0
    cases = []
    runs = [(4, 0)] if quick else [(12, s) for s in range(5)] + [(8, 0), (16, 0)]
    for n, seed in runs:
        model = honeycomb(n, sigma=0.05, seed=seed)
        end = horizon if quick else HORIZON[n]
        result = run_engine(definition(model, end=end, observe=[]))
        obs = result.observations
        cells = n * n
        cases.append(
            {
                "n": n,
                "seed": seed,
                "energy_per_cell_rel_error": abs(obs.energy[-1] / cells - e_star) / e_star,
                "area_max_error": float(np.max(np.abs(obs.cell_area[-1][:cells] - a_star))),
                "perimeter_max_error": float(np.max(np.abs(obs.cell_perimeter[-1][:cells] - p))),
                "length_max_error": float(np.max(np.abs(obs.junction_length[-1] - side))),
                "stress_abs_max": float(np.max(np.abs(obs.box_stress[-1]))),
                "max_force": float(obs.max_force[-1]),
                **_diagnostics(result),
            }
        )
    scan = []
    for s in (0.95, 0.975, 1.025, 1.05):
        a = a_star * s * s
        model = honeycomb(4 if quick else 8, area=a, sigma=0.02, seed=0)
        cells = len(model["cells"])
        result = run_engine(definition(model, end=horizon, observe=[]))
        obs = result.observations
        expected_e = theory.energy_per_cell(a, LAMBDA, GAMMA)
        expected_s = theory.stress_half_trace(a, LAMBDA, GAMMA)
        stress = obs.box_stress[-1]
        scan.append(
            {
                "scale": s,
                "energy_per_cell": obs.energy[-1] / cells,
                "energy_per_cell_rel_error": abs(obs.energy[-1] / cells - expected_e) / expected_e,
                "stress_half_trace_abs_error": abs(0.5 * np.trace(stress) - expected_s),
                "shear_stress_abs": float(max(abs(stress[0, 1]), abs(stress[1, 0]))),
                "energy_above_ground": obs.energy[-1] / cells - e_star,
            }
        )
    a2, p2, _, e2 = theory.ground_state(*CASE_II)
    model = honeycomb(
        4 if quick else 12, line_tension=CASE_II[0], contractility=CASE_II[1], sigma=0.03
    )
    result = run_engine(definition(model, end=horizon if quick else HORIZON[12], observe=[]))
    cells = len(model["cells"])
    case_ii = {
        "energy_per_cell_rel_error": abs(result.observations.energy[-1] / cells - e2) / e2,
        "area_max_error": float(np.max(np.abs(result.observations.cell_area[-1][:cells] - a2))),
        **_diagnostics(result),
    }
    from cells.analysis import mechanical_equilibrium as me
    from cells.core import vertex_preparation as prep
    from cells.core.specs import parse_spec

    model = honeycomb(4 if quick else 8, area=a_star * 1.05**2, sigma=0.02, seed=1)
    spec = parse_spec(prep.definition(model, end_time=1.0, observation_times=[0.0], dt=1e-6))
    pb = me.problem(spec)
    eq = me.minimize(pb, box=True)
    box_relax = {
        "area_error": abs(np.linalg.det(eq.box) / len(model["cells"]) - a_star),
        "stress_abs_max": float(np.max(np.abs(eq.stress))),
        "box_iterations": eq.box_iterations,
    }
    return {
        "cases": cases,
        "case_I_metrics": {
            "energy_per_cell_rel_error_max": max(c["energy_per_cell_rel_error"] for c in cases),
            "shape_error_max": max(
                max(c["area_max_error"], c["perimeter_max_error"], c["length_max_error"])
                for c in cases
            ),
            "stress_abs_max": max(c["stress_abs_max"] for c in cases),
            "allowance_used_max": max(c["allowance_used"] for c in cases),
            "momentum_drift_max": max(c["momentum_drift"] for c in cases),
            "area_identity_error_max": max(c["area_identity_error"] for c in cases),
        },
        "scan": scan,
        "scan_metrics": {
            "energy_rel_error_max": max(s["energy_per_cell_rel_error"] for s in scan),
            "stress_abs_error_max": max(s["stress_half_trace_abs_error"] for s in scan),
            "shear_stress_abs_max": max(s["shear_stress_abs"] for s in scan),
            "ground_is_scan_minimum": min(s["energy_above_ground"] for s in scan),
        },
        "case_II": case_ii,
        "box_relaxation": box_relax,
    }


RIGIDITY_R = (0.04, 0.1, 1.0)
INCOMPATIBLE = (3.0, 3.2, 3.4, 3.5, 3.6, 3.65, 3.7, 3.71, 3.72)
COMPATIBLE = (3.73, 3.75, 3.8, 3.9)


def _staddon_problem(n, r, p0, *, sigma=0.02, seed=0):
    from cells.analysis import mechanical_equilibrium as me
    from cells.core import vertex_preparation as prep
    from cells.core.specs import parse_spec

    model = staddon_model(n, r, p0, sigma=sigma, seed=seed)
    spec = parse_spec(prep.definition(model, end_time=1.0, observation_times=[0.0], dt=0.001))
    return me.problem(spec), model


def part_rigidity(args):
    from cells.analysis import mechanical_equilibrium as me

    quick = args.quick
    n = 4 if quick else 8
    rows = []
    rs = (1.0,) if quick else RIGIDITY_R
    points = (3.5, 3.7) if quick else INCOMPATIBLE
    for r in rs:
        for p0 in points:
            g, b = theory.moduli(r, p0)
            row = {"r": r, "p0": p0, "G_theory": g, "B_theory": b}
            for size in (n, 2):
                pb, _ = _staddon_problem(size, r, p0)
                eq = me.minimize(pb)
                m = me.moduli(pb, eq.position)
                row[f"n{size}"] = {
                    "G": m.shear,
                    "B": m.bulk,
                    "G_rel_error": abs(m.shear - g) / g,
                    "B_rel_error": abs(m.bulk - b) / b,
                    "affine_ratio": m.shear / m.shear_affine,
                    "negative_modes": m.negative_modes,
                    "stress_abs_max": float(np.max(np.abs(m.stress))),
                }
            rows.append(row)
    compatible = []
    for r in rs:
        for p0 in (3.75,) if quick else COMPATIBLE:
            for seed in (0, 1):
                pb, _ = _staddon_problem(n, r, p0, seed=seed)
                eq = me.minimize(pb)
                m = me.moduli(pb, eq.position)
                cells = len(pb.spec.model.cells)
                compatible.append(
                    {
                        "r": r,
                        "p0": p0,
                        "seed": seed,
                        "excess_energy": eq.energy + cells * r * p0**2 / 2,
                        "G": m.shear,
                        "B_minus_one": m.bulk - 1.0,
                    }
                )
    dynamic = []
    gamma = 1e-3
    # Sheared-box engine relaxations on 4 x 4 lattices away from p* (critical slowing
    # down there makes gradient flow impractically slow; near p* the analysis judges).
    points = (
        ((1.0, 3.6),) if quick else ((0.04, 3.0), (0.1, 3.0), (0.1, 3.5), (1.0, 3.6), (1.0, 3.8))
    )
    for r, p0 in points:
        model = staddon_model(4, r, p0, sigma=0.02, seed=0)
        energies = []
        for g_ in (-gamma, 0.0, gamma):
            result = run_engine(definition(sheared(model, g_), end=1200.0, observe=[]))
            energies.append(float(result.observations.energy[-1]))
        area = float(np.linalg.det(np.array(model["periods"]).T))
        g_dyn = (energies[0] + energies[2] - 2 * energies[1]) / (area * gamma**2)
        g_theory = theory.moduli(r, p0)[0]
        cells = len(model["cells"])
        dynamic.append(
            {
                "r": r,
                "p0": p0,
                "G_dynamic": g_dyn,
                "G_theory": g_theory,
                "G_rel_error": abs(g_dyn - g_theory) / g_theory if g_theory > 0 else None,
                "excess_energy_sheared": max(e + cells * r * p0**2 / 2 for e in energies)
                if p0 > theory.P_STAR
                else None,
            }
        )
    zero = {}
    for r in rs:
        tail = [row for row in rows if row["r"] == r][-3:]
        p_values = np.array([row["p0"] for row in tail])
        g_values = np.array([row[f"n{n}"]["G"] for row in tail])
        slope, intercept = np.polyfit(p_values, g_values, 1)
        zero[f"r={r}"] = {
            "p0_zero": float(-intercept / slope),
            "error": float(-intercept / slope - theory.P_STAR),
        }
    return {
        "rows": rows,
        "metrics": {
            "G_rel_error_max": max(
                max(row[k]["G_rel_error"] for k in row if k.startswith("n")) for row in rows
            ),
            "B_rel_error_max": max(
                max(row[k]["B_rel_error"] for k in row if k.startswith("n")) for row in rows
            ),
            "affine_ratio_error_max": max(
                max(abs(row[k]["affine_ratio"] - 2 / 3) for k in row if k.startswith("n"))
                for row in rows
            ),
            "negative_modes_max": max(
                max(row[k]["negative_modes"] for k in row if k.startswith("n")) for row in rows
            ),
            "compatible_excess_abs_max": max(abs(c["excess_energy"]) for c in compatible),
            "compatible_G_abs_max": max(abs(c["G"]) for c in compatible),
            "compatible_B_minus_one_abs_max": max(abs(c["B_minus_one"]) for c in compatible),
            "dynamic_G_rel_error_max": max(
                d["G_rel_error"] for d in dynamic if d["G_rel_error"] is not None
            ),
            "dynamic_compatible_excess_abs_max": max(
                [
                    abs(d["excess_energy_sheared"])
                    for d in dynamic
                    if d["excess_energy_sheared"] is not None
                ]
                or [0.0]
            ),
            "zero_of_G_error_abs_max": max(abs(z["error"]) for z in zero.values()),
        },
        "compatible": compatible,
        "dynamic": dynamic,
        "zero_of_G": zero,
    }


# Below the pentagon threshold 3.8119350: incompatible 3.5, 3.7; compatible start 3.75-3.81.
BARRIER_P0 = (3.5, 3.7, 3.75, 3.8, 3.81, 3.815, 3.82, 3.83, 3.85)
FRACTIONS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05, 0.02, 0.0)


def orientation_junctions(model):
    """One junction per edge direction (30, 90, 150 degrees), on the regular lattice."""
    n = int(round(np.sqrt(len(model["cells"]))))
    tissue = ref.from_definition(
        {"model": honeycomb(n), "experiment": {"parameter_controls": [{}]}}
    )
    d = ref.junction_vectors(tissue, tissue.position)
    angle = np.degrees(np.mod(np.arctan2(d[:, 1], d[:, 0]), np.pi))
    centre = central_junction(model)
    chosen = []
    for target in (30.0, 90.0, 150.0):
        candidates = np.flatnonzero(np.abs(angle - target) < 15)
        middle = tissue.position[tissue.junction_tail] + 0.5 * d
        c = middle[centre]
        chosen.append(int(candidates[np.argmin(np.linalg.norm(middle[candidates] - c, axis=1))]))
    return chosen


def part_barrier(args):
    from cells.analysis import mechanical_equilibrium as me

    quick = args.quick
    n = 4 if quick else 8
    rs = (1.0,) if quick else (0.1, 1.0, 10.0)
    points = (3.7, 3.85) if quick else BARRIER_P0
    fractions = np.array((1.0, 0.5, 0.0) if quick else FRACTIONS)
    rows = []
    for r in rs:
        for p0 in points:
            seeds = (0,) if (p0 < theory.P_STAR or quick) else (0, 1)
            for seed in seeds:
                pb, model = _staddon_problem(n, r, p0, seed=seed)
                eq = me.minimize(pb)
                for k, junction in enumerate(orientation_junctions(model)):
                    path = me.contraction(pb, eq.position, junction, fractions)
                    row = {
                        "r": r,
                        "p0": p0,
                        "seed": seed,
                        "orientation": k,
                        "junction": junction,
                        "barrier": path.barrier,
                        "barrier_bi_units": 2 * path.barrier,
                        "energies": path.energies,
                        "max_force": float(np.max(path.max_forces)),
                    }
                    if p0 < theory.P_STAR and seed == 0:
                        tissue = ref.from_definition(
                            {"model": model, "experiment": {"parameter_controls": [{}]}}
                        )
                        x = eq.position[: len(tissue.position)]
                        energies, _, _ = ref.contraction(
                            tissue, x, junction, fractions, polish="end"
                        )
                        row["reference_barrier"] = float(energies[-1] - energies[0])
                        row["reference_energy_max_difference"] = float(
                            np.max(np.abs(np.asarray(path.energies) - energies))
                        )
                    rows.append(row)
    below = [row["barrier"] for row in rows if row["p0"] < theory.minimal_perimeter(5)]
    vanishing = {}
    for r in rs:
        zero_points = sorted(
            {
                row["p0"]
                for row in rows
                if row["r"] == r
                and all(
                    abs(other["barrier"]) <= 1e-10
                    for other in rows
                    if other["r"] == r and other["p0"] == row["p0"]
                )
            }
        )
        vanishing[f"r={r}"] = zero_points[0] if zero_points else None
    references = [row for row in rows if "reference_barrier" in row]
    result = {
        "rows": rows,
        "vanishing_point": vanishing,
        "metrics": {
            "barrier_below_pentagon_min": min(below) if below else None,
            "vanishing_points": [v for v in vanishing.values()],
            "engine_reference_barrier_rel_difference_max": max(
                abs(row["barrier"] - row["reference_barrier"])
                / max(abs(row["reference_barrier"]), 1e-12)
                for row in references
            )
            if references
            else None,
            "path_max_force": max(row["max_force"] for row in rows),
        },
    }
    registered = getattr(args, "registered", None)
    if registered is not None and not quick:
        differences = []
        for value in registered["barriers"]:
            match = [
                row
                for row in rows
                if row["r"] == value["r"]
                and row["p0"] == value["p0"]
                and row["junction"] == value["junction"]
                and row["seed"] == 0
            ]
            differences.append(
                abs(match[0]["barrier"] - value["barrier"]) / abs(value["barrier"])
                if match
                else float("inf")
            )
        result["metrics"]["registered_barrier_rel_difference_max"] = max(differences)
    return result


def part_recoil(args):
    from cells.analysis import mechanical_equilibrium as me
    from cells.core.specs import parse_spec
    from cells.models import apical_vertex as av
    from cells.processes import vertex_mechanics as vm

    quick = args.quick
    n = 4 if quick else 12
    a_star, p_case, _, _ = theory.ground_state(LAMBDA, GAMMA)
    prep_model = honeycomb(n, sigma=0.05, seed=0)
    prepared = run_engine(definition(prep_model, end=200.0 if quick else 1200.0, observe=[]))
    x_eq = np.asarray(prepared.final.state.position)
    base = with_positions(prep_model, x_eq)
    junction = central_junction(base)
    t_cut = 1.0
    taus = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0)
    out = {"junction": junction, "prepared_max_force": float(prepared.observations.max_force[-1])}
    # Full Farhadifar cut.
    horizon = 200.0 if quick else 2000.0
    dt = stable_dt(base)
    defn = definition(
        base,
        end=t_cut + horizon,
        observe=[t_cut, t_cut + dt, *(t_cut + t for t in taus)],
        dt=dt,
        controls=cut_control(base, junction, 1.0, t_cut),
    )
    result = run_engine(defn)
    obs = result.observations
    spec = parse_spec(defn)
    state, layout = av.initial_values(spec)
    topo = av.topology(layout)
    row = list(obs.times).index(t_cut)
    x_cut = obs.position[row]
    before = ref.from_definition(defn)
    after = ref.with_control(before, defn["experiment"]["parameter_controls"][1])
    v = len(before.position)
    import jax.numpy as jnp

    def forces(tissue_ref):
        mech = vm.Mechanics(
            *(
                jnp.asarray(np.pad(getattr(tissue_ref, k), (0, cap - len(getattr(tissue_ref, k)))))
                for k, cap in (
                    ("line_tension", spec.execution.junction_capacity),
                    ("contractility", spec.execution.capacity),
                    ("area_elasticity", spec.execution.capacity),
                    ("preferred_area", spec.execution.capacity),
                )
            )
        )
        return np.asarray(vm.forces(jnp.asarray(x_cut), topo, jnp.asarray(layout.box), mech))[:v]

    jump_engine = forces(after) - forces(before)
    jump_reference = ref.velocity_jump(before, after, x_cut[:v]) * before.friction[:, None]
    t, h = before.junction_tail[junction], before.junction_head[junction]
    d = x_cut[h] + before.junction_image[junction] @ before.box.T - x_cut[t]
    unit = d / np.linalg.norm(d)
    rate = float((forces(after)[h] - forces(after)[t]) @ unit / before.friction[0])
    out["full_cut"] = {
        "velocity_jump_rel_error": float(
            np.max(np.abs(jump_engine - jump_reference)) / np.max(np.abs(jump_reference))
        ),
        "opening_rate": rate,
        "opening_rate_theory": theory.recoil_opening_rate(LAMBDA, GAMMA, p_case),
        "opening_rate_abs_error": abs(rate - theory.recoil_opening_rate(LAMBDA, GAMMA, p_case)),
        "control_work_rel_error": abs(
            obs.total_control_work[row + 1]
            - (ref.energy(after, x_cut[:v]) - ref.energy(before, x_cut[:v]))
        )
        / abs(ref.energy(after, x_cut[:v]) - ref.energy(before, x_cut[:v])),
        **_diagnostics(result),
    }
    x_final = np.asarray(result.final.state.position)[:v]
    x_ref, f_ref, _ = ref.relax(after, x_cut[:v], gtol=1e-12)
    shift = np.mean(x_final - x_ref, axis=0)
    d0 = float(np.linalg.norm(d))
    d1 = float(obs.junction_length[-1][junction] - d0)
    out["full_cut"].update(
        {
            "final_position_difference": float(np.max(np.abs(x_final - shift - x_ref))),
            "final_energy_rel_difference": abs(
                ref.energy(after, x_final) - ref.energy(after, x_ref)
            )
            / abs(ref.energy(after, x_ref)),
            "reference_max_force": f_ref,
            "opening_d1": d1,
            "opening_over_length": d1 / d0,
            "opening_curve": [
                float(obs.junction_length[i][junction] - d0) for i in range(row, len(obs.times))
            ],
            "opening_times": [float(obs.times[i] - t_cut) for i in range(row, len(obs.times))],
        }
    )
    # Small cuts against the linear response of the reference.
    small = []
    for eps in (1e-4, 1e-3, 1e-2):
        defn = definition(
            base,
            end=t_cut + (100.0 if quick else 400.0),
            observe=[t_cut, *(t_cut + t for t in taus)],
            controls=cut_control(base, junction, eps, t_cut),
        )
        result = run_engine(defn)
        obs = result.observations
        row = list(obs.times).index(t_cut)
        x_cut = obs.position[row][:v]
        before = ref.from_definition(defn)
        after = ref.with_control(before, defn["experiment"]["parameter_controls"][1])
        linear, rate0, tau = ref.linear_recoil(before, after, x_cut, junction, taus)
        d0 = obs.junction_length[row][junction]
        engine = np.array(
            [obs.junction_length[list(obs.times).index(t_cut + t)][junction] - d0 for t in taus]
        )
        final = float(obs.junction_length[-1][junction] - d0)
        tau_engine = final / rate0
        small.append(
            {
                "eps": eps,
                "deviation": float(np.max(np.abs(engine - linear)) / np.max(np.abs(linear))),
                "tau_effective_linear": tau,
                "tau_effective_engine": tau_engine,
                "tau_rel_difference": abs(tau_engine - tau) / tau,
            }
        )
    dev = [s["deviation"] for s in small]
    out["small_cuts"] = small
    out["metrics"] = {
        "velocity_jump_rel_error": out["full_cut"]["velocity_jump_rel_error"],
        "opening_rate_abs_error": out["full_cut"]["opening_rate_abs_error"],
        "control_work_rel_error": out["full_cut"]["control_work_rel_error"],
        "final_position_difference": out["full_cut"]["final_position_difference"],
        "final_energy_rel_difference": out["full_cut"]["final_energy_rel_difference"],
        "small_cut_deviation_smallest_eps": dev[0],
        "small_cut_deviation_slope": float(np.log10(dev[2] / dev[0]) / 2.0),
        "small_cut_tau_rel_difference": small[0]["tau_rel_difference"],
        "allowance_used": out["full_cut"]["allowance_used"],
    }
    registered = getattr(args, "registered", None)
    if registered is not None:  # Committed reference values (mg1_references.py).
        values = registered["recoil"]
        out["metrics"].update(
            {
                "registered_opening_rate_abs_difference": abs(rate - values["opening_rate"]),
                "registered_d1_rel_difference": abs(
                    out["full_cut"]["opening_d1"] - values["full_cut_opening_d1"]
                )
                / abs(values["full_cut_opening_d1"]),
                "registered_tau_rel_difference": abs(
                    small[0]["tau_effective_engine"] - values["small_cut_tau_effective"]
                )
                / values["small_cut_tau_effective"],
            }
        )
    del me
    return out


def part_inference(args):
    import jax

    from cells.analysis import junction_tension_inference as jti
    from cells.analysis import mechanical_equilibrium as me
    from cells.core.specs import parse_spec

    quick = args.quick
    rows = []
    for n in (4,) if quick else (8, 12):
        for seed in (0,) if quick else range(5):
            model = honeycomb(n, sigma=0.0)
            rng = np.random.Generator(np.random.PCG64(seed))
            for j in model["junctions"]:
                j["line_tension"] = LAMBDA * (1 + 0.2 * rng.standard_normal())
            model = with_positions(
                model,
                np.array([v["position"] for v in model["vertices"]])
                + 0.01 * rng.standard_normal((len(model["vertices"]), 2)),
            )
            defn = definition(model, end=400.0 if quick else {8: 1000.0, 12: 1600.0}[n], observe=[])
            result = run_engine(defn)
            spec = parse_spec(defn)
            pb = me.problem(spec, position=np.asarray(result.final.state.position))
            x = pb.position
            mech = jax.tree.map(np.asarray, pb.mechanics)
            tension, pressure = jti.true_tensions(x, pb.host_topology, pb.box, mech)
            b = jti.balance(x, pb.host_topology, pb.box)
            known = jti.known_pressure(b, pressure)
            joint = jti.joint(b, mean_tension=np.mean(tension), mean_pressure=np.mean(pressure))
            noise = []
            direction = rng.standard_normal(x.shape)  # One draw, scaled: linearity test.
            for sigma in (1e-7, 1e-6, 1e-5):
                noisy = x + sigma * direction
                k = jti.known_pressure(jti.balance(noisy, pb.host_topology, pb.box), pressure)
                noise.append(float(np.sqrt(np.mean((k.tension - tension) ** 2)) / np.mean(tension)))
            bayes = []
            for sigma in (1e-3, 1e-2):
                for _ in range(2 if quick else 20):
                    noisy = x + sigma * rng.standard_normal(x.shape)
                    by = jti.bayesian(jti.balance(noisy, pb.host_topology, pb.box))
                    bayes.append(
                        {
                            "sigma": sigma,
                            "rms": float(
                                np.sqrt(
                                    np.mean(
                                        (
                                            by.tension / np.mean(by.tension)
                                            - tension / np.mean(tension)
                                        )
                                        ** 2
                                    )
                                )
                            ),
                            "correlation": float(np.corrcoef(by.tension, tension)[0, 1]),
                            "hyperparameter": by.hyperparameter,
                            "at_grid_edge": bool(
                                by.hyperparameter
                                in (by.hyperparameter_grid[0], by.hyperparameter_grid[-1])
                            ),
                        }
                    )
            rows.append(
                {
                    "n": n,
                    "seed": seed,
                    "max_force": float(result.observations.max_force[-1]),
                    "relative_spread": float(np.std(tension) / np.mean(tension)),
                    "known_pressure_rel_error": float(
                        np.max(np.abs(known.tension - tension)) / np.mean(tension)
                    ),
                    "joint_null_dimension": joint.null_dimension,
                    "joint_rel_error": float(
                        np.max(np.abs(joint.tension - tension)) / np.mean(tension)
                    ),
                    "joint_condition": joint.condition_beyond_gauges,
                    "noise_rms": noise,
                    "noise_slope": float(
                        np.polyfit(np.log10([1e-7, 1e-6, 1e-5]), np.log10(noise), 1)[0]
                    ),
                    "bayesian": bayes,
                }
            )
    return {
        "rows": rows,
        "metrics": {
            "max_force_max": max(r["max_force"] for r in rows),
            "known_pressure_rel_error_max": max(r["known_pressure_rel_error"] for r in rows),
            "joint_null_dimensions": [r["joint_null_dimension"] for r in rows],
            "joint_rel_error_max": max(r["joint_rel_error"] for r in rows),
            "noise_slopes": [r["noise_slope"] for r in rows],
        },
    }


def _engine_positions(model, dt, solver, end, controls=None):
    result = run_engine(
        definition(model, end=end, observe=[], dt=dt, solver=solver, controls=controls)
    )
    return np.asarray(result.final.state.position), result


def part_numerics(args):
    import jax
    import jax.numpy as jnp

    from cells.core.errors import NumericalError
    from cells.core.specs import ConfigError, parse_spec
    from cells.models import apical_vertex as av
    from cells.processes import vertex_mechanics as vm

    quick = args.quick
    model = honeycomb(4, sigma=0.05, seed=2)
    end = 4.0
    v = len(model["vertices"])
    reference, _ = _engine_positions(model, 2.0**-9, "rk4", end)
    orders = {}
    for solver, steps in (
        ("rk4", (2.0**-3, 2.0**-4, 2.0**-5, 2.0**-6)),
        ("euler", (2.0**-4, 2.0**-5, 2.0**-6, 2.0**-7)),
    ):
        errors, used = [], []
        for dt in steps[:2] if quick else steps:
            x, result = _engine_positions(model, dt, solver, end)
            errors.append(float(np.max(np.abs(x[:v] - reference[:v]))))
            used.append(result.diagnostics["max_energy_balance_allowance_used"])
        orders[solver] = {
            "dt": list(steps),
            "errors": errors,
            "orders": [float(np.log2(a / b)) for a, b in zip(errors, errors[1:], strict=False)],
            "allowance_used_max": max(used),
        }
    # Recoil transient: a cut at t = 0.5 of an equilibrium honeycomb.
    base = honeycomb(4)
    controls = cut_control(base, 0, 1.0, 0.5)
    recoil_ref, _ = _engine_positions(base, 2.0**-9, "rk4", 2.5, controls)
    recoil = []
    for dt in (2.0**-3, 2.0**-4) if quick else (2.0**-3, 2.0**-4, 2.0**-5, 2.0**-6):
        x, result = _engine_positions(base, dt, "rk4", 2.5, controls)
        recoil.append(float(np.max(np.abs(x[:v] - recoil_ref[:v]))))
    # Refusals.
    refusals = {}
    try:
        run_engine(definition(honeycomb(4), end=1.0, observe=[], dt=0.5))
        refusals["oversize_step"] = False
    except ConfigError:
        refusals["oversize_step"] = True
    collapse = honeycomb(4)
    collapse["length_floor"] = 0.3
    collapse["junctions"][0]["line_tension"] = 3.0
    try:
        run_engine(definition(collapse, end=20.0, observe=[], dt=2.0**-6))
        refusals["edge_collapse"] = False
    except NumericalError:
        refusals["edge_collapse"] = True
    # jax.grad against the closed form on a perturbed 12 x 12 lattice.
    big = honeycomb(4 if quick else 12, sigma=0.05, seed=9)
    spec = parse_spec(definition(big, end=1.0, observe=[]))
    state, layout = av.initial_values(spec)
    f = np.asarray(
        jax.jit(vm.forces)(
            jnp.asarray(state.position),
            av.topology(layout),
            jnp.asarray(layout.box),
            av.mechanics(state),
        )
    )
    tissue = ref.from_definition(spec.to_dict())
    closed = ref.forces(tissue, tissue.position)
    return {
        "orders": orders,
        "recoil_errors": recoil,
        "recoil_orders": [float(np.log2(a / b)) for a, b in zip(recoil, recoil[1:], strict=False)],
        "refusals": refusals,
        "metrics": {
            "rk4_orders": orders["rk4"]["orders"],
            "euler_orders": orders["euler"]["orders"],
            "allowance_used_max": max(o["allowance_used_max"] for o in orders.values()),
            "refusals_all": all(refusals.values()),
            "grad_vs_closed_form_rel": float(
                np.max(np.abs(f[: len(closed)] - closed)) / np.max(np.abs(closed))
            ),
        },
    }


def part_tyssue(args):
    from cells.analysis import mechanical_equilibrium as me
    from cells.core.specs import parse_spec
    from validation.morphogenesis import mg1_tyssue as ty

    quick = args.quick
    n = 4 if quick else 12
    model = honeycomb(n, sigma=0.05, seed=0)
    defn = definition(model, end=1.0, observe=[])
    tissue = ref.from_definition(defn)
    x0 = tissue.position
    junction = central_junction(model)
    cut = cut_control(model, junction, 1.0, 0.0)[1]
    steps = 40
    eps = 1e-3
    stretched = []
    for e in (-eps, 0.0, eps):
        m = copy.deepcopy(model)
        (ax, _), (_, by) = m["periods"]
        m["periods"] = [[ax * (1 + e), 0.0], [0.0, by / (1 + e)]]
        for vtx in m["vertices"]:
            vtx["position"] = [vtx["position"][0] * (1 + e), vtx["position"][1] / (1 + e)]
        stretched.append(m)
    ops = [
        {"kind": "static", "name": "static"},
        {"kind": "relax", "name": "relax", "gtol": 1e-12},
        {"kind": "euler", "name": "euler", "dt": EULER_DT, "steps": steps},
        {
            "kind": "euler",
            "name": "euler_cut",
            "dt": EULER_DT,
            "steps": steps,
            "schedule": [{"step": steps // 2, "control": cut}],
        },
    ]
    results = ty.run_tyssue(defn, ops, args.output / "tyssue_main")
    stretch = [
        ty.run_tyssue(
            definition(m, end=1.0, observe=[]),
            [{"kind": "relax", "name": "relax", "gtol": 1e-12}],
            args.output / f"tyssue_stretch_{k}",
        )["relax"]
        for k, m in enumerate(stretched)
    ]
    out = {"environment": results["environment"]}
    out["static"] = {
        "energy_rel_difference": abs(float(results["static"]["energy"]) - ref.energy(tissue, x0))
        / ref.energy(tissue, x0),
        "gradient_abs_difference": float(
            np.max(np.abs(results["static"]["gradient"] - ref.gradient(tissue, x0)))
        ),
    }
    pb = me.problem(parse_spec(defn))
    eq = me.minimize(pb)
    v = len(x0)
    relaxed = results["relax"]
    delta = ty.modulo_box(relaxed["position"] - eq.position[:v], tissue.box)
    out["relax"] = {
        "energy_rel_difference": abs(float(relaxed["energy"]) - eq.energy) / abs(eq.energy),
        "position_difference": float(np.max(np.abs(delta - np.mean(delta, axis=0)))),
    }
    x_euler, _ = _engine_positions(model, EULER_DT, "euler", steps * EULER_DT)
    x_cut, _ = _engine_positions(
        model,
        EULER_DT,
        "euler",
        steps * EULER_DT,
        cut_control(model, junction, 1.0, (steps // 2) * EULER_DT),
    )
    out["euler"] = {
        "position_difference": float(
            np.max(
                np.abs(ty.modulo_box(results["euler"]["position"][-1] - x_euler[:v], tissue.box))
            )
        ),
        "cut_position_difference": float(
            np.max(
                np.abs(ty.modulo_box(results["euler_cut"]["position"][-1] - x_cut[:v], tissue.box))
            )
        ),
    }
    area = float(np.linalg.det(tissue.box))
    g_pure = (
        float(stretch[0]["energy"]) + float(stretch[2]["energy"]) - 2 * float(stretch[1]["energy"])
    ) / (4 * area * eps**2)
    g_cells = me.moduli(pb, eq.position).shear
    out["pure_shear"] = {
        "G_tyssue_pure_shear": g_pure,
        "G_cells_simple_shear": g_cells,
        "rel_difference": abs(g_pure - g_cells) / g_cells,
    }
    out["metrics"] = {
        "static_energy_rel": out["static"]["energy_rel_difference"],
        "static_gradient_abs": out["static"]["gradient_abs_difference"],
        "relax_energy_rel": out["relax"]["energy_rel_difference"],
        "relax_position": out["relax"]["position_difference"],
        "euler_position": out["euler"]["position_difference"],
        "euler_cut_position": out["euler"]["cut_position_difference"],
        "pure_shear_rel": out["pure_shear"]["rel_difference"],
    }
    return out


PARTS = dict(
    theory=part_theory,
    ground=part_ground,
    rigidity=part_rigidity,
    barrier=part_barrier,
    recoil=part_recoil,
    inference=part_inference,
    numerics=part_numerics,
    tyssue=part_tyssue,
)


def registered_predictions_check(protocol, parts):
    """Recomputed theory values against the protocol's registered ones (relative)."""
    registered = protocol.get("registered_predictions", {}).get("theory")
    if registered is None or "theory" not in parts:
        return None
    worst = 0.0

    def walk(a, b):
        nonlocal worst
        if isinstance(a, dict):
            for k in a:
                walk(a[k], b[k])
        elif isinstance(a, (int, float)) and not isinstance(a, bool):
            worst = max(worst, abs(a - b) / max(abs(a), 1e-300))

    walk(registered, parts["theory"])
    return {"max_relative_difference": worst}


def judge(protocol, parts, failures):
    verdict = evaluate(protocol, parts)
    verdict["failed_parts"] = sorted(failures)
    verdict["passed"] = bool(verdict["passed"] and not failures)
    verdict["registered_predictions_check"] = registered_predictions_check(protocol, parts)
    return verdict


def run_parts(args, parts):
    results, failures = {}, {}
    for part in parts:
        t0 = time.perf_counter()
        try:
            results[part] = PARTS[part](args)
            results[part]["part_wall_seconds"] = time.perf_counter() - t0
            (args.output / f"{part}.json").write_text(
                json.dumps(_jsonable(results[part]), indent=1)
            )
        except Exception as error:  # Preserve the failure as evidence.
            failures[part] = dict(error=repr(error), traceback=traceback.format_exc())
        status = "ok" if part in results else "FAILED"
        print(f"{part}: {status} in {time.perf_counter() - t0:.1f} s", flush=True)
    return results, failures


def build_report(results, failures, protocol=None):
    report = dict(
        kind="cells.morphogenesis_mg1_results@1",
        engine_models=[
            MODEL_ID,
            "mechanical_equilibrium_analysis@1",
            "junction_tension_inference@1",
        ],
        parts=json.loads(json.dumps(_jsonable(results))),
        failures=failures,
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    if protocol is not None:
        report["protocol_id"] = protocol["id"]
        report["verdict"] = judge(protocol, report["parts"], failures)
    return report


def rejudge(results_path, protocol, destination):
    saved = json.loads(Path(results_path).read_text())
    judgement = dict(
        kind="cells.morphogenesis_mg1_judgement@1",
        results=str(results_path),
        protocol_id=protocol["id"],
        verdict=judge(protocol, saved["parts"], saved.get("failures", {})),
    )
    if "verdict" in saved:
        judgement["matches_saved_verdict"] = (
            json.loads(json.dumps(_jsonable(judgement["verdict"]))) == saved["verdict"]
        )
    with Path(destination).open("x") as stream:
        json.dump(judgement, stream, indent=1)
    return judgement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="+", choices=[*PARTS, "all", "judge"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    protocol = None if args.protocol is None else json.loads(args.protocol.read_text())
    if "judge" in args.parts:
        if args.parts != ["judge"] or protocol is None:
            parser.error("judge takes no other parts and needs --protocol")
        judgement = rejudge(args.output / "results.json", protocol, args.output / "judgement.json")
        print(f"passed: {judgement['verdict']['passed']}", flush=True)
        return 0 if judgement["verdict"]["passed"] else 1
    if protocol is not None and args.quick:
        parser.error("--quick is a development scale and is never judged")
    import jax

    jax.config.update("jax_enable_x64", True)
    args.output.mkdir(parents=True, exist_ok=True)
    args.registered = None
    if protocol is not None:  # Reference values committed in the protocol (mg1_references.py).
        args.registered = protocol.get("registered_predictions", {}).get("reference_values")
    results, failures = run_parts(args, list(PARTS) if "all" in args.parts else args.parts)
    report = build_report(results, failures, protocol)
    with (args.output / "results.json").open("x") as stream:
        json.dump(report, stream, indent=1)
    if failures:
        (args.output / "failure.json").write_text(json.dumps(failures, indent=1))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
