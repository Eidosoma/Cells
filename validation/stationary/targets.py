"""Development driver: stationary_continuation_analysis@1 against its targets.

Engine models analysed (unmodified, through cells.analysis.stationary):
resolved_pump_tissue@1 (default-world cell) and resolved_pump_tissue@3
(heredity cells, the MG0b cell and a small tissue). The analysis evaluates the
models' own derivative (model.rhs) and checked IMEX step (model.checked_step).

Parts (each writes PART.json into --output, which must not exist):
  default   slow stationary state of the pre-screen's default-world cell
            (prescreen-03.json), with stability and step-map consistency
  heredity  slow H, U, D states of the heredity cell (prescreen-06.json and the
            independent reduced model validation/morphogenesis/mg0b_theory.py)
  mg0b      fast states at u_M and continuation in the control u
            (protocols-draft/mg0b_reduced_predictions.json, dev-04 theory.json)
  tissue    a written D disc of 7 cells in a 61-cell hexagonal sheet
  default_run  the default-world cell run from its INIT end through the
            qualified windowed runner (resolved_pump_tissue@1, IMEX ARS(2,2,2)),
            to compare the trajectory's end and decay rate with the analysis

References are saved records and independent reduced models; nothing here
adds physics to the engine. Usage:
  python -m validation.stationary.targets PART [PART ...] --output DIR
"""

import argparse
import json
import resource
import sys
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells import __version__  # noqa: E402
from cells.analysis import continuation as cont  # noqa: E402
from cells.analysis import stationary as sa  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from validation.stationary import reduced, worlds  # noqa: E402

PRESCREEN = worlds.PRESCREEN


def _json(value):
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json(value.tolist())
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, complex):
        return [value.real, value.imag]
    return value


def _log(line):
    print(f"[{time.strftime('%H:%M:%S')}]   {line}", flush=True)


def _cell_state(record, cell="cell_0", membrane="membrane_0"):
    s = record["state"]
    c = s["cell_concentration_mM"][cell]
    return dict(
        vm_V=s["membrane_voltage_V"][membrane],
        **{k: c[k] for k in c},
        osmolarity_mM=s["cell_osmolarity_mM"][cell],
    )


# ---------------------------------------------------------------- default world


def _map_agreement(record, solutions):
    """max |u_rhs - u_step| (u units) against twice the step map's floor (E1.4)."""
    difference = float(np.max(np.abs(solutions["rhs"].u - solutions["step_map"].u)))
    floor = record["consistency"]["step_map_1"]["rounding_floor"]
    return dict(max_u_difference=difference, floor=floor, within=bool(difference <= 2 * floor))


def default_parameters():
    """The reduced model's default-world cell: no Kir2.1, no NaV1.2, Na leak x1."""
    from dataclasses import replace

    perm = {k: worlds.DEFAULT_WORLD["permeability_m_s"][k] for k in reduced.MOBILE}
    base = heredity_parameters(nav_availability=0.0)
    return replace(base, kir_m_s=0.0, nav_m_s=0.0, permeability_m_s=perm)


def part_default(args):
    """Slow stationary state of the default-world cell from the INIT-end composition."""
    record = json.loads((PRESCREEN / "prescreen-03.json").read_text())
    reference = next(
        r for r in record["kir_scan"] if r["p_kir_m_s"] == 0 and r["na_permeability_scale"] == 1.0
    )["steady_states"]
    if worlds.prescreen_world() != worlds.DEFAULT_WORLD:
        raise ValueError("worlds.DEFAULT_WORLD differs from the saved pre-screen world block")
    spec = parse_spec(worlds.default_world_cell())
    out = dict(world="default_world_cell (prescreen-03.json world block, INIT-end start)")
    pb = sa.problem(spec, mode="slow", formulation="rhs", steps=1)
    solutions = {}
    for formulation in ("rhs", "step_map"):
        t0 = time.perf_counter()
        options = dict(formulation=formulation, steps=1)
        result, solution = sa.solve_and_check(
            pb, pb.anchor, label="init_end", newton_options=options, stability_options=options
        )
        result["wall_seconds"] = time.perf_counter() - t0
        out[formulation] = result
        if solution.converged:
            out[formulation + "_cell"] = _cell_state(result)
            solutions[formulation] = solution
    if len(solutions) == 2:
        a, b = out["rhs_cell"], out["step_map_cell"]
        out["rhs_minus_step_map"] = {k: a[k] - b[k] for k in a}
        out["step_map_agreement"] = _map_agreement(out["step_map"], solutions)
    if "rhs" not in solutions:
        return out
    ref, cell = reference[0], out["rhs_cell"]
    out["prescreen"] = ref
    out["prescreen_comparison"] = dict(
        vm_mV=1e3 * cell["vm_V"] - ref["vm_mV"],
        Na_mM=cell["Na"] - ref["Na_mM"],
        K_mM=cell["K"] - ref["K_mM"],
        M_mM=cell["M"] - ref["M_mM"],
        osmolarity_mM=cell["osmolarity_mM"] - ref["osmolarity_in_mM"],
        engine_relaxation_times_s=sorted(out["rhs"]["stability"]["relaxation_times_s"]),
        prescreen_time_constants_s=ref["time_constants_s"],
    )
    p = default_parameters()
    states = reduced.theory().slow_states(p, 0.0)
    out["theory_states"] = [dict(vm_V=v, **c) for v, c in states]
    if len(states) == 1:
        out["theory_comparison"] = _compare_slow(pb, out["rhs"], solutions["rhs"], p, states[0])
    return out


# ---------------------------------------------------------------- heredity cell

MG0B = Path("/mnt/workspaces/Cells/morphogenesis-mg0-20261109-01")
MG0B_THEORY = MG0B / "dev-04-mg0b" / "theory.json"


def heredity_parameters(nav_availability=1.0, control_m_s=0.0):
    """The reduced model's heredity cell (mg0b_domain_wall.cell_parameters, NaV 1, no control)."""
    from dataclasses import replace

    from validation.morphogenesis import mg0b_domain_wall as wall

    return replace(
        wall.cell_parameters(), nav_availability=nav_availability, control_m_s=control_m_s
    )


def _adiabatic(pb, u, theta=None, cell="cell_0"):
    """Engine ion Jacobian with gates eliminated quasi-statically (Schur complement)."""
    _, jac, _, _, _ = pb.evaluate(u, theta)
    labels = pb.labels()
    ions = [labels.index(f"{s}@{cell}") for s in reduced.MOBILE]
    gates = [i for i, label in enumerate(labels) if label.startswith("gate")]
    return reduced.adiabatic_ions(jac, ions, gates), jac


EPS = float(np.finfo(float).eps)
BUDGET_FACTOR = 10.0  # Safety factor on summed error estimates (see the protocol draft).
REFERENCE_XTOL_V = 1e-15  # mg0b_theory brentq tolerance on voltage roots.


def _compare_slow(pb, record, solution, p, theory_state, cell="cell_0"):
    """Engine slow state vs a reduced-model state, with error budgets; Jacobians, eigenvalues.

    Budget per quantity: BUDGET_FACTOR x (engine correction + reference
    correction [+ the reference's root tolerance for V]) + 64 eps |value|, the
    corrections being one Newton step at each solution (its error estimate).
    """
    v_ref, c_ref = theory_state
    c3 = np.array([c_ref[s] for s in reduced.MOBILE])
    values = _cell_state(record)
    labels = pb.labels()
    ions = [labels.index(f"{s}@{cell}") for s in reduced.MOBILE]
    delta, _, _ = sa.correction_vector(pb, solution.u)
    v_engine = float(pb.evaluate(solution.u)[3][0])
    dv_engine = float(pb.evaluate(solution.u + delta)[3][0]) - v_engine
    dc_ref, dv_ref = reduced.correction(p, c3)
    diff = dict(vm_V=values["vm_V"] - v_ref)
    budget = dict(
        vm_V=BUDGET_FACTOR * (abs(dv_engine) + abs(dv_ref) + REFERENCE_XTOL_V)
        + 64 * EPS * abs(v_ref)
    )
    for k, s in enumerate(reduced.MOBILE):
        diff[s] = values[s] - c_ref[s]
        budget[s] = BUDGET_FACTOR * (abs(delta[ions[k]]) + abs(dc_ref[k])) + 64 * EPS * c_ref[s]
    j_engine, jac = _adiabatic(pb, solution.u)
    j_ref, j_err = reduced.slow_jacobian(p, c3)
    ref_values, ref_bounds = reduced.eigen_bounds(j_ref, j_err)
    eng_values, eng_bounds = reduced.eigen_bounds(j_engine, 64 * EPS * np.abs(j_engine))
    matched = [int(np.argmin(np.abs(eng_values - v))) for v in ref_values]
    eigen_diff = np.abs(eng_values[matched] - ref_values)
    eigen_budget = ref_bounds + eng_bounds[matched]
    return dict(
        engine=values,
        reference_vm_V=v_ref,
        reference_composition_mM=c_ref,
        engine_minus_reference=diff,
        budget=budget,
        within_budget={k: bool(abs(diff[k]) <= budget[k]) for k in diff},
        engine_error_estimate=dict(
            vm_V=dv_engine, **{s: delta[ions[k]] for k, s in enumerate(reduced.MOBILE)}
        ),
        reference_error_estimate=dict(
            vm_V=dv_ref, **dict(zip(reduced.MOBILE, dc_ref, strict=True))
        ),
        engine_reduced_jacobian_condition=float(
            np.linalg.cond(pb.reduction().operator(jac), np.inf)
        ),
        adiabatic_jacobian_engine=j_engine,
        adiabatic_jacobian_reference=j_ref,
        adiabatic_jacobian_reference_error=j_err,
        adiabatic_jacobian_within_error=bool(
            np.all(np.abs(j_engine - j_ref) <= j_err + 64 * EPS * np.abs(j_ref))
        ),
        adiabatic_eigenvalues_engine=[[v.real, v.imag] for v in eng_values[matched]],
        adiabatic_eigenvalues_reference=[[v.real, v.imag] for v in ref_values],
        adiabatic_eigenvalue_difference=eigen_diff,
        adiabatic_eigenvalue_budget=eigen_budget,
        adiabatic_eigenvalues_within_budget=bool(np.all(eigen_diff <= eigen_budget)),
    )


def part_heredity(args):
    """Slow H, U, D states of the heredity cell, from the pre-screen's states as guesses."""
    from validation.tissue import surface_pump_v3_fixtures as fx

    th = reduced.theory()
    record = json.loads((PRESCREEN / "prescreen-06.json").read_text())
    row = next(
        r
        for r in record["rows"]
        if r["bath_K_mM"] == 5.0
        and r["na_leak_scale"] == 0.2
        and r["p_kir_m_s"] == 1e-8
        and r["p_nav_m_s"] == 2.5e-7
    )
    p = heredity_parameters()
    theory_states = th.slow_states(p, 0.0)
    raw = worlds.ionic_background(fx.heredity_cells([fx.HEREDITY_STATES["H"][:4]]))
    pb = sa.problem(parse_spec(raw), mode="slow", formulation="rhs", steps=1)
    out = dict(
        world="heredity_cells([H]) with the reduced models' background (ionic charge only)",
        theory_states=[dict(vm_V=v, **c) for v, c in theory_states],
        prescreen_states=row["slow_steady_states"],
        states={},
    )
    for label, value in fx.HEREDITY_STATES.items():
        guess = parse_spec(
            worlds.ionic_background(fx.heredity_cells([value[:4]], gate_voltages=[value[0]]))
        )
        u0 = pb.coordinates(*pb.model.initial_values(guess))
        entry = {}
        for formulation in ("rhs", "step_map"):
            options = dict(formulation=formulation, steps=1)
            rec, solution = sa.solve_and_check(
                pb, u0, label=label, newton_options=options, stability_options=options
            )
            entry[formulation] = rec
            if not solution.converged:
                continue
            entry.setdefault("_solutions", {})[formulation] = solution
            cell = entry[formulation + "_cell"] = _cell_state(rec)
            if formulation == "rhs":
                nearest = min(theory_states, key=lambda s, v=cell["vm_V"]: abs(s[0] - v))
                entry["theory_comparison"] = _compare_slow(pb, rec, solution, p, nearest)
                pre = min(
                    row["slow_steady_states"],
                    key=lambda s, v=cell["vm_V"]: abs(s["vm_mV"] - 1e3 * v),
                )
                entry["prescreen_comparison"] = dict(
                    prescreen=pre,
                    vm_mV=1e3 * cell["vm_V"] - pre["vm_mV"],
                    Na_mM=cell["Na"] - pre["Na_mM"],
                    K_mM=cell["K"] - pre["K_mM"],
                    M_mM=cell["M"] - pre["M_mM"],
                    engine_relaxation_times_s=sorted(rec["stability"]["relaxation_times_s"]),
                    engine_classification=rec["stability"]["classification"],
                )
        solutions = entry.pop("_solutions", {})
        if len(solutions) == 2:
            a, b = entry["rhs_cell"], entry["step_map_cell"]
            entry["rhs_minus_step_map"] = {k: a[k] - b[k] for k in a}
            entry["step_map_agreement"] = _map_agreement(entry["step_map"], solutions)
        out["states"][label] = entry
    return out


# ---------------------------------------------------------------- MG0b cell


def _mg0b_world(t, vm):
    from validation.morphogenesis import mg0b_domain_wall as wall

    c = t["composition_mM"]
    return wall.chain_definition(
        1,
        state=(vm, c["Na"], c["K"], c["M"]),
        end_time=1.0,
        observation_times=[0.0, 1.0],
        control=((0.0, t["u_maxwell"]),),
        junction_m_s=0.0,
    )


def part_mg0b(args):
    """Fast states at the Maxwell control and the fixed-composition window in u."""
    from validation.morphogenesis import mg0b_domain_wall as wall

    th = reduced.theory()
    t = json.loads(MG0B_THEORY.read_text())
    p, c, u_m = wall.cell_parameters(), t["composition_mM"], t["u_maxwell"]
    spec = parse_spec(_mg0b_world(t, t["fast_states_V"]["H"]))
    q = sa.parameter(spec, "channel_availability", ["ctrl_0"])
    pb = sa.problem(spec, mode="fast", parameter=q)
    out = dict(world="mg0b_domain_wall.chain_definition(1, ...) at u_M", theory=t, states={})
    out["theory_fast_states_recomputed_V"] = th.fast_states(p, c, u_m)
    for label, v in t["fast_states_V"].items():
        guess = parse_spec(_mg0b_world(t, v))
        rec, solution = sa.solve_and_check(
            pb, pb.coordinates(*pb.model.initial_values(guess)), label=label
        )
        if solution.converged:
            diff = rec["state"]["membrane_voltage_V"]["membrane_0"] - v
            slope = th.slope_conductance_S(p, c, v, u_m)
            reference_error = abs(float(th.current_A(p, c, v, u_m)) / slope) + REFERENCE_XTOL_V
            engine_error = sa.CHARGE_UNIT_V * rec["error_estimate"]
            budget = BUDGET_FACTOR * (engine_error + reference_error) + 64 * EPS * abs(v)
            rec.update(
                engine_minus_theory_V=diff,
                engine_error_V=engine_error,
                reference_error_V=reference_error,
                budget_V=budget,
                within_budget=bool(abs(diff) <= budget),
            )
        out["states"][label] = rec
    if not out["states"]["H"]["converged"]:
        return out
    started = time.perf_counter()
    diagram = cont.continue_branch(
        pb, pb.anchor, theta_start=u_m, direction=1, step=0.01, max_step=0.02, bounds=(0.0, 1.0)
    )
    diagram.pop("_states")
    diagram["wall_seconds"] = time.perf_counter() - started
    out["continuation"] = diagram
    points = sorted(
        (s for s in diagram["special_points"] if s["kind"] == "fold"),
        key=lambda s: s["parameter_value"],
    )
    folds = [s["parameter_value"] for s in points]
    window = t["bistable_control_range"]
    refined, misses = [], []
    for k, edge in enumerate(window):
        inside = edge + (0.002 if k == 0 else -0.002)
        roots = th.fast_states(p, c, inside)
        pair = (roots[1], roots[2]) if k == 0 else (roots[0], roots[1])
        brackets = ((edge - 0.004, edge + 0.004), (min(pair), max(pair)))
        u_edge, v_edge = reduced.fold(p, c, *brackets)
        u_half, _ = reduced.fold(p, c, *brackets, h=5e-7)
        refined.append(dict(u=u_edge, v=v_edge, error=abs(u_edge - u_half) + 1e-14))
        misses.append(reduced.grid_miss_bound(p, c, u_edge, v_edge))
    out.update(
        engine_window=folds,
        theory_window_grid=window,
        theory_window_refined=refined,
        theory_grid_miss_bound=misses,
    )
    if len(folds) == 2:
        engine_error = [s["parameter_error_estimate"] for s in points]
        out["engine_fold_error"] = engine_error
        out["engine_minus_refined"] = [f - r["u"] for f, r in zip(folds, refined, strict=True)]
        out["fold_budget"] = [
            BUDGET_FACTOR * (e + r["error"]) for e, r in zip(engine_error, refined, strict=True)
        ]
        out["folds_within_budget"] = [
            bool(abs(d) <= b)
            for d, b in zip(out["engine_minus_refined"], out["fold_budget"], strict=True)
        ]
        out["engine_minus_grid"] = [f - w for f, w in zip(folds, window, strict=True)]
        # The grid window lies inside the true one by at most the miss bound.
        out["grid_window_inside_engine_window"] = bool(
            0 <= window[0] - folds[0] <= misses[0] + out["fold_budget"][0]
            and 0 <= folds[1] - window[1] <= misses[1] + out["fold_budget"][1]
        )
    return out


# ---------------------------------------------------------------- tissue disc

SHEET_RADIUS = 4  # 61 cells
DISC_RADIUS = 1  # 7 cells
COUPLING_RANGE = (0.01, 4.0)  # junction permeability scale, in units of G = g_H


def _disc_states(cells, inside, outside):
    return [inside if worlds.ring(c) <= DISC_RADIUS else outside for c in cells]


def _disc_summary(pb, u, theta, cells, threshold):
    voltages = np.asarray(pb.evaluate(u, theta)[3])[: len(cells)]
    disc = np.array([worlds.ring(c) <= DISC_RADIUS for c in cells])
    labels = voltages > threshold
    return dict(
        d_cells_inside=int(np.sum(labels & disc)),
        d_cells_outside=int(np.sum(labels & ~disc)),
        disc_voltage_range_V=[float(voltages[disc].min()), float(voltages[disc].max())],
        outside_voltage_range_V=[float(voltages[~disc].min()), float(voltages[~disc].max())],
    )


def _disc_branch(pb, guess_u, cells, threshold, *, max_points=200, step=0.02, max_step=0.1):
    """Disc state at the weakest coupling, then continuation upward to its fold."""
    lo, hi = COUPLING_RANGE
    _log(f"{pb.mode} disc: solve at coupling {lo} ({pb.size} coordinates)")
    record, solution = sa.solve_and_check(pb, guess_u, label="disc", theta=lo)
    out = dict(start=record)
    _log(f"{pb.mode} disc: {record['message']} after {record['iterations']} iterations")
    if not solution.converged:
        return out
    record["disc"] = _disc_summary(pb, solution.u, solution.theta, cells, threshold)
    _log(f"{pb.mode} disc: {record['disc']} {record['stability']['classification']}")
    started = time.perf_counter()
    diagram = cont.continue_branch(
        pb,
        solution.u,
        theta_start=lo,
        direction=1,
        step=step,
        max_step=max_step,
        max_points=max_points,
        bounds=(0.0, hi),
        log=_log,
    )
    states = diagram.pop("_states")
    diagram["wall_seconds"] = time.perf_counter() - started
    diagram["disc"] = [
        _disc_summary(pb, u, point["parameter_value"], cells, threshold)
        for u, point in zip(states, diagram["points"], strict=True)
    ]
    out["continuation"] = diagram
    return out


def _graph_reference(result, p, c, t, edges, v0, pb):
    """The reduced graph model (reduced.graph_*) for the fast disc: state and fold coupling.

    Engine disc voltages at the weakest coupling are compared with the graph
    state under the same budget as the single-cell fast states: BUDGET_FACTOR
    x (engine correction in volts + graph correction) + 64 eps |V|.
    """
    lo, hi = COUPLING_RANGE
    lap = reduced.graph_laplacian(len(v0), edges)
    g_h, u_m = t["slope_conductance_S"]["H"], t["u_maxwell"]
    v, dv_ref = reduced.graph_state(p, c, u_m, lo * g_h, lap, v0)
    out = dict(model="C dV/dt = -I(V) - G L V on the sheet graph, frozen composition")
    if v is None:
        out["state"] = "no graph state at the weakest coupling"
        return out
    fold, width, v_fold = reduced.graph_fold(p, c, u_m, g_h, lap, v0, lo, hi)
    extrapolated = (
        None if fold is None else reduced.graph_fold_extrapolated(p, c, u_m, g_h, lap, v_fold, fold)
    )
    out.update(
        state_V=v,
        correction_V=dv_ref,
        leading_rate_per_s=reduced.graph_leading_rate(p, c, u_m, lo * g_h, lap, v, p.capacitance_F),
        fold_coupling=fold,
        fold_bracket=width,
        fold_extrapolated=extrapolated,
        fold_error=None if extrapolated is None else abs(extrapolated - fold) + width,
    )
    start = result["start"]
    if start.get("converged"):
        engine = np.array(list(start["state"]["membrane_voltage_V"].values()))
        dv_engine = sa.CHARGE_UNIT_V * start["error_estimate"]
        budget = BUDGET_FACTOR * (dv_engine + dv_ref) + 64 * EPS * np.abs(v)
        out.update(
            engine_minus_reference_V=engine - v,
            max_abs_difference_V=float(np.max(np.abs(engine - v))),
            budget_V=budget,
            within_budget=bool(np.all(np.abs(engine - v) <= budget)),
        )
    folds = [
        s for s in result.get("continuation", {}).get("special_points", []) if s["kind"] == "fold"
    ]
    if folds and out["fold_error"] is not None:
        first = folds[0]
        budget = BUDGET_FACTOR * (first["parameter_error_estimate"] + out["fold_error"])
        out.update(
            engine_first_fold=first["parameter_value"],
            engine_minus_reference_fold=first["parameter_value"] - fold,
            fold_budget=budget,
            fold_within_budget=bool(abs(first["parameter_value"] - fold) <= budget),
        )
    return out


def part_tissue(args):
    """A written D disc of 7 cells in a 61-cell sheet: existence, stability, fold coupling."""
    from validation.morphogenesis import mg0b_domain_wall as wall
    from validation.tissue import surface_pump_v3_fixtures as fx

    th = reduced.theory()
    cells, edges = worlds.hexagon(SHEET_RADIUS)
    disc = int(sum(worlds.ring(c) <= DISC_RADIUS for c in cells))
    out = dict(cells=len(cells), junctions=len(edges), disc_cells=disc)
    # Fast mode, MG0b set: NaV 0.4, control at u_M, composition c in every cell.
    t = json.loads(MG0B_THEORY.read_text())
    p, c = wall.cell_parameters(), t["composition_mM"]
    unit = wall.junction_permeability_for(1.0, t["slope_conductance_S"]["H"], c, p)
    fast = {k: (v, c["Na"], c["K"], c["M"]) for k, v in t["fast_states_V"].items()}
    kw = dict(nav_availability=wall.NAV_AVAILABILITY, control=t["u_maxwell"])
    background = [fast["H"]] * len(cells)
    written = _disc_states(cells, fast["D"], fast["H"])

    def sheet(states, **extra):
        return parse_spec(
            worlds.sheet_definition(
                states, edges, unit, gate_voltages=[s[0] for s in states], **kw, **extra
            )
        )

    base = sheet(background)
    q = sa.parameter(base, "junction_permeability_scale", "all")
    pb = sa.problem(base, mode="fast", parameter=q)
    u0 = pb.coordinates(*pb.model.initial_values(sheet(written)))
    out["fast_mg0b"] = dict(
        coupling_unit_m_s=unit,
        coupling_unit="G = g_H of the MG0b cell (mg0b junction_permeability_for, ratio 1)",
        **_disc_branch(pb, u0, cells, t["fast_states_V"]["U"]),
    )
    out["fast_mg0b"]["reference"] = _graph_reference(
        out["fast_mg0b"], p, c, t, edges, [s[0] for s in written], pb
    )
    # Slow mode, heredity set: NaV 1, no control; disc cells at the slow D state.
    states = {k: v[:4] for k, v in fx.HEREDITY_STATES.items()}
    ph = heredity_parameters()
    c_h = dict(zip(reduced.MOBILE, states["H"][1:4], strict=True))
    g_h = th.slope_conductance_S(ph, c_h, states["H"][0], 0.0)
    unit = wall.junction_permeability_for(1.0, g_h, c_h, ph)
    kw = {}
    written = _disc_states(cells, states["D"], states["H"])

    def slow_sheet(values):
        return parse_spec(
            worlds.ionic_background(
                worlds.sheet_definition(values, edges, unit, gate_voltages=[s[0] for s in values])
            )
        )

    base = slow_sheet([states["H"]] * len(cells))
    q = sa.parameter(base, "junction_permeability_scale", "all")
    pb = sa.problem(base, mode="slow", parameter=q)
    u0 = pb.coordinates(*pb.model.initial_values(slow_sheet(written)))
    out["slow_heredity"] = dict(
        coupling_unit_m_s=unit,
        coupling_unit="G = fast slope conductance of the slow H cell",
        **_disc_branch(pb, u0, cells, states["U"][0], max_points=300, step=0.5, max_step=5.0),
    )
    return out


# ---------------------------------------------------------------- confirming run

RUN_DT = 0.01  # s; 26 steps per membrane time constant (0.26 s)
RUN_HORIZON = 200000.0  # s, 12 slowest relaxation times
RUN_CHUNK_STEPS = 100000  # 1000 s per recorded point
RUNNER_PROBE_S = 100.0


def part_default_run(args):
    """The default-world cell from its INIT end for 2e5 s, against the analysis.

    First the qualified windowed runner is tried on a 100 s run; its host ledger
    checks refuse resolved pump runs of this length (the known @1/@2/@3 check
    issue under repair), so the refusal is recorded and the long trajectory is
    a diagnostic: the model's own checked IMEX step (every step's validity
    enforced, a refusal is NaN) iterated by the analysis step map, without the
    host ledger checks (no ledgers are carried). The trajectory's end and late
    decay rate are compared with the stationary state and slowest eigenvalue
    of the analysis.
    """
    from cells.core.errors import NumericalError
    from cells.core.windows import WindowPolicy, run_windowed

    out = dict(dt_s=RUN_DT, horizon_s=RUN_HORIZON, chunk_steps=RUN_CHUNK_STEPS)
    probe = parse_spec(
        worlds.default_world_cell(
            dt=RUN_DT, end_time=RUNNER_PROBE_S, observation_times=[0.0, RUNNER_PROBE_S]
        )
    )
    try:
        run_windowed(probe, WindowPolicy(10000, "observations"))
        out["runner_probe"] = "passed"
    except NumericalError as error:
        out["runner_probe"] = "refused: " + str(error)
    spec = parse_spec(worlds.default_world_cell(dt=RUN_DT, end_time=1.0))
    pb = sa.problem(spec, mode="slow", formulation="step_map", steps=RUN_CHUNK_STEPS)
    advance = jax.jit(lambda u: pb.step_residual(u, pb.theta0(), RUN_CHUNK_STEPS))
    period = RUN_CHUNK_STEPS * RUN_DT
    u, times, trajectory = np.asarray(pb.anchor), [0.0], [np.asarray(pb.anchor)]
    started = time.perf_counter()
    while times[-1] < RUN_HORIZON - 0.5 * period:
        rate = np.asarray(advance(u))
        if not np.all(np.isfinite(rate)):
            out["refused_at_s"] = times[-1]
            break
        u = u + period * rate
        times.append(times[-1] + period)
        trajectory.append(u)
        if len(times) % 20 == 1:
            _log(f"default_run: t = {times[-1]:.0f} s, {time.perf_counter() - started:.0f} s wall")
    out["step_wall_seconds"] = time.perf_counter() - started
    out["ledgers"] = "not carried: the step map restarts the ledgers each chunk (diagnostic)"
    rhs = sa.problem(spec, mode="slow")
    solution = sa.newton(rhs, rhs.anchor)
    stab = sa.stability(rhs, solution.u)
    rate = stab["eigenvalues_per_s"][0][0]
    labels = pb.labels()
    ions = [labels.index(f"{s}@cell_0") for s in reduced.MOBILE]
    trajectory = np.asarray(trajectory)
    distance = np.max(np.abs(trajectory[:, ions] - solution.u[ions]), axis=1)
    times = np.asarray(times)
    late = (times >= 50000.0) & (distance > 0)
    slope = float(np.polyfit(times[late], np.log(distance[late]), 1)[0])
    out.update(
        times_s=times,
        concentration_mM=trajectory[:, ions]
        + np.asarray([pb.p.amount_reference[k, 0] / pb.p.volume[0] for k in range(3)]),
        stationary_state=sa.describe(rhs, solution.u),
        stationary_slowest_rate_per_s=rate,
        distance_mM=distance,
        final_distance_mM=float(distance[-1]),
        predicted_final_distance_mM=float(
            distance[times >= 50000.0][0] * np.exp(rate * (times[-1] - 50000.0))
        ),
        late_log_slope_per_s=slope,
        late_slope_vs_slowest_rate_relative=slope / rate - 1,
    )
    return out


PARTS = dict(
    default=part_default,
    heredity=part_heredity,
    mg0b=part_mg0b,
    tissue=part_tissue,
    default_run=part_default_run,
)


SNAPSHOT_SCOPE = (
    "src/cells",
    "validation/stationary",
    "validation/morphogenesis",
    "validation/tissue",
    "validation/source_snapshot.py",
)


def snapshot(destination):
    """Freeze the engine and these drivers (validation/source_snapshot.py) for a run."""
    import os
    import subprocess

    from validation import source_snapshot

    root = Path(__file__).resolve().parents[2]
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        + ["--", *SNAPSHOT_SCOPE],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    names = sorted({os.fsdecode(n) for n in listed.split(b"\0") if n})
    names = [n for n in names if (root / n).is_file() and "__pycache__" not in n]
    return source_snapshot.freeze(root, destination, {n: n for n in names})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("parts", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.parts == ["snapshot"]:
        result = snapshot(args.output)
        print(json.dumps({k: result[k] for k in ("git_revision", "status")}))
        return 0
    names = list(PARTS) if args.parts == ["all"] else args.parts
    if any(n not in PARTS for n in names):
        parser.error(f"parts: {sorted(PARTS)} or all")
    args.output.mkdir(parents=True, exist_ok=False)
    status = 0
    for name in names:
        started = time.perf_counter()
        print(f"[{time.strftime('%H:%M:%S')}] part {name}", flush=True)
        try:
            value = PARTS[name](args)
            value = dict(
                part=name,
                analysis=sa.ANALYSIS_ID,
                cells_version=__version__,
                wall_seconds=time.perf_counter() - started,
                max_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                **value,
            )
            with open(args.output / f"{name}.json", "x") as stream:
                json.dump(_json(value), stream, indent=1)
            print(f"[{time.strftime('%H:%M:%S')}] part {name} done", flush=True)
        except Exception as error:  # Failures are kept as evidence.
            status = 1
            with open(args.output / f"{name}.failure.json", "x") as stream:
                json.dump(
                    dict(part=name, error=repr(error), traceback=traceback.format_exc()),
                    stream,
                    indent=1,
                )
            print(f"part {name} failed: {error!r}", flush=True)
    return status


if __name__ == "__main__":
    sys.exit(main())
