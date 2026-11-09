"""Design pre-screen 7: written-disc stationary states for E07-v1 (development, not judged).

Question (heredity design E07-v1, docs/HEREDITY_FIRST_EXPERIMENT.md): with the
heredity slow parameter set and E07-v1's gap junctions, is a written D disc of
7, 19 or 37 cells a stationary state of the full pump-leak dynamics, is it
stable, and where along the junction coupling does it stop being so, for gates
held open and for voltage-gated junctions? Where do E07-v1's four coupling
arms (x0.3, x1, x3, x10) fall on that map, and is the uniform H state stable
at each arm (the spontaneous-D validity gate)?

Engine model analysed: resolved_pump_tissue@3, unmodified, through
stationary_continuation_analysis@1 (cells.analysis.stationary), slow mode,
the law's own derivative (model.rhs), dense Jacobians and spectra.

World: a hexagonal sheet of heredity cells (validation/tissue/
surface_pump_v3_fixtures.heredity_cells: BETSE default coefficients, Na leak
x0.2, Kir2.1 1e-8 m/s, NaV1.2 2.5e-7 m/s, 310 K, fixed volume; each cell faces
its own held bath, the F0 surrogate of the design), the cells carrying only P
as fixed charge (worlds.ionic_background), joined along the sheet's 342 edges
by E07-v1 junctions (worlds.e07_junction: W225's BETSE gap-junction area and
permeabilities, junction_voltage_relaxation@1 with threshold 15 mV and
minimum 0.1). Coupling: theta = open junction conductance at the H
composition / g_H, g_H the fast slope conductance of the slow H cell; the arm
multiplier s scales every junction permeability (s = 1 is E07-v1 x1).

Method per (disc radius, gating): Newton from the written guess (D slow
state inside the disc, H outside, gates at their steady state for those
voltages) at the weakest theta, then natural continuation over a geometric
theta grid that includes the arms, each step warm-started by secant
extrapolation. A state counts as the written disc while every disc cell is D
and no other cell is (V above the slow U voltage) and no voltage jumped by more
than 15 mV from the previous point. Between grid points the first loss of
stability is bisected on the sign of the leading growth rate (Hopf if the
crossing pair is complex), and the end of existence is bisected on Newton
convergence to a disc state (a fold, or a jump to another state).

Usage: python -m validation.stationary.heredity_prescreen --output DIR [--quick]
"""

import argparse
import json
import math
import resource
import sys
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells import __version__  # noqa: E402
from cells.analysis import stationary as sa  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from validation.stationary import reduced, targets, worlds  # noqa: E402

SHEET_RADIUS = 6  # 127 cells, 342 junctions
DISC_RADII = (1, 2, 3)  # 7, 19, 37 cells
ARMS = (0.3, 1.0, 3.0, 10.0)
THETA_RANGE = (0.005, 25.0)
GRID_POINTS = 24
JUMP_V = 0.025  # a cell switching state moves by 40 mV or more
BISECTIONS = 14
BOUNDARY_CHECK = dict(radius=7, disc=3, gated=True)  # 169 cells: does the edge matter?


def _log(line):
    print(f"[{time.strftime('%H:%M:%S')}] {line}", flush=True)


def units():
    """Arm couplings in theta units (derivation recorded in the result)."""
    from validation.tissue import surface_pump_v3_fixtures as fx

    th = reduced.theory()
    p = targets.heredity_parameters()
    j = worlds.e07_junction()
    h = fx.HEREDITY_STATES["H"]
    c_h = dict(zip(reduced.MOBILE, h[1:4], strict=True))
    g_h = th.slope_conductance_S(p, c_h, h[0], 0.0)
    perm = {s: j["permeability_m_per_s"][s] for s in reduced.MOBILE}
    g_open = th.junction_conductance_S(p, c_h, j["area_m2"], perm)
    mg0b = json.loads(targets.MG0B_THEORY.read_text())
    g_fast = mg0b["slope_conductance_S"]["H"]
    g_open_fast = th.junction_conductance_S(p, mg0b["composition_mM"], j["area_m2"], perm)
    from cells.processes import junction_gate

    gate = junction_gate.Parameters(j["threshold_voltage_V"], j["minimum_open_fraction"])
    d = fx.HEREDITY_STATES["D"]
    open_fraction = {
        f"{1e3 * v:.1f} mV": float(junction_gate.kinetics(np.asarray(v), gate, xp=np).target)
        for v in (0.0, 0.015, 0.03, 0.05, d[0] - h[0])
    }
    return dict(
        junction=j,
        formula="G = F^2/(RT) A sum_s z_s^2 P_s c_s (open constant-field junction, equal "
        "compositions c on both sides); theta = s G(c_H) / g_H",
        g_H_slow_S=g_h,
        g_H_slow="fast slope conductance dI/dV of the heredity cell at its slow H state "
        "(mg0b_theory.slope_conductance_S, NaV availability 1, no control)",
        G_open_x1_at_H_S=g_open,
        theta_per_unit_scale=g_open / g_h,
        g_H_fast_mg0b_S=g_fast,
        G_open_x1_at_mg0b_composition_S=g_open_fast,
        theta_fast_mg0b_per_unit_scale=g_open_fast / g_fast,
        arms={
            f"x{m:g}": dict(
                scale=m,
                theta_slow=m * g_open / g_h,
                theta_fast_mg0b=m * g_open_fast / g_fast,
                theta_slow_gated_at_H=m * g_open / g_h * open_fraction["0.0 mV"],
                theta_slow_gated_at_HD_boundary=m
                * g_open
                / g_h
                * open_fraction[f"{1e3 * (d[0] - h[0]):.1f} mV"],
            )
            for m in ARMS
        },
        gate_open_fraction_at_Vj=open_fraction,
    )


class Case:
    """One sheet, disc and gating: problem, guesses and disc labelling."""

    def __init__(self, sheet_radius, disc_radius, gated, mode="slow", heterogeneity=None, dt=1e-3):
        from validation.tissue import surface_pump_v3_fixtures as fx

        self.cells, self.edges = worlds.hexagon(sheet_radius)
        states = {k: v[:4] for k, v in fx.HEREDITY_STATES.items()}
        self.threshold = states["U"][0]
        self.disc = np.array([worlds.ring(c) <= disc_radius for c in self.cells])
        written = [states["D"] if d else states["H"] for d in self.disc]
        factors = {}
        if heterogeneity is not None:
            cell_factors, junction_factors = worlds.e07_heterogeneity(
                len(self.cells), len(self.edges), **heterogeneity
            )
            factors = dict(cell_factors=cell_factors, junction_factors=junction_factors)

        def spec(values):
            return parse_spec(
                worlds.ionic_background(
                    worlds.e07_sheet_definition(values, self.edges, gated=gated, dt=dt, **factors)
                )
            )

        if mode == "fast":
            # Frozen composition: the written world's amounts (D inside, H outside).
            base = spec(written)
            q = sa.parameter(base, "junction_permeability_scale", "all")
            self.pb = sa.problem(base, mode="fast", parameter=q)
            self.written = self.uniform = self.pb.anchor
        else:
            base = spec([states["H"]] * len(self.cells))
            q = sa.parameter(base, "junction_permeability_scale", "all")
            self.pb = sa.problem(base, mode="slow", parameter=q)
            self.written = self.pb.coordinates(*self.pb.model.initial_values(spec(written)))
            self.uniform = self.pb.anchor
        self.label = dict(
            sheet_cells=len(self.cells),
            junctions=len(self.edges),
            disc_cells=int(self.disc.sum()),
            gating="voltage-gated" if gated else "open",
            mode=mode,
            heterogeneity=heterogeneity,
        )

    def voltages(self, u, scale):
        return np.asarray(self.pb.evaluate(u, scale)[3])[: len(self.cells)]

    def is_disc(self, v):
        d = v > self.threshold
        return bool(np.all(d[self.disc]) and not np.any(d[~self.disc]))


class _Solved:
    def __init__(self, u, estimate):
        self.u, self.error_estimate, self.converged = u, estimate, True


NEWTON_STEPS = 12
NEWTON_BACKTRACKS = 4


def solve(case, guess, scale):
    """Newton on the conservation set that gives up fast (sweep and bisection use).

    Full steps with at most NEWTON_BACKTRACKS halvings, accepted while the step
    size decreases; converged at a full step <= stationary.NEWTON_TOLERANCE,
    after which one further correction is the error estimate. A fold or a jump
    to another state therefore costs a few Jacobians instead of the analysis
    Newton's full line search (which also falls back to pseudo-transient
    continuation, relaxing toward whatever state is stable).
    """
    pb = case.pb
    red = pb.reduction()
    origin = red.project(guess)
    u = origin
    r, jac, _, _, _ = pb.evaluate(u, scale)
    if not sa._finite(r):
        return None
    previous = np.inf
    for _ in range(NEWTON_STEPS):
        dz = -np.linalg.solve(red.operator(jac), red.vector(r))
        step = sa._norm(red.full(dz))
        if not np.isfinite(step) or step > 2 * previous:
            return None
        lam = 1.0
        for _ in range(NEWTON_BACKTRACKS + 1):
            trial = u + lam * red.full(dz)
            tr, tj, _, _, _ = pb.evaluate(trial, scale)
            if sa._finite(tr) and sa._finite(tj):
                break
            lam /= 2
        else:
            return None
        u, r, jac, previous = trial, tr, tj, step
        if lam == 1.0 and step <= sa.NEWTON_TOLERANCE:
            last = -np.linalg.solve(red.operator(jac), red.vector(r))
            return _Solved(u, sa._norm(red.full(last)))
    return None


def classify(case, u, scale):
    st = sa.stability(case.pb, u, theta=scale, count=6)
    return dict(
        classification=st["classification"],
        unstable_count=st["unstable_count"],
        marginal_count=st["marginal_count"],
        leading_eigenvalues_per_s=st["eigenvalues_per_s"][:4],
        leading_bound_per_s=st["eigenvalue_error_bounds_per_s"][0],
    )


def _point(case, u, scale, theta_unit, stab=True):
    v = case.voltages(u, scale)
    out = dict(
        scale=scale,
        theta=scale * theta_unit,
        disc_voltage_range_V=[float(v[case.disc].min()), float(v[case.disc].max())],
        outside_voltage_range_V=[float(v[~case.disc].min()), float(v[~case.disc].max())],
        is_disc=case.is_disc(v),
    )
    if stab:
        out.update(classify(case, u, scale))
    return out, v


def sweep(case, theta_unit, arm_scales, classify_from=0.0):
    """Natural continuation of the written disc with bisection of its first changes.

    Spectra are computed at grid points with theta >= classify_from only (and at
    the start); below it the points are marked unclassified, which saves the
    dense eigen-decompositions of large sheets in the weak-coupling range.
    """
    lo, hi = (t / theta_unit for t in THETA_RANGE)
    grid = np.unique(np.r_[np.geomspace(lo, hi, GRID_POINTS), arm_scales])
    first = solve(case, case.written, grid[0])
    result = dict(case=case.label, points=[], stability_boundary=None, existence_boundary=None)
    if first is None:
        result["start"] = "no converged disc state at the weakest coupling"
        return result
    point, v = _point(case, first.u, grid[0], theta_unit)
    if not point["is_disc"]:
        result["start"] = "the weakest-coupling state is not the written disc"
        result["points"].append(point)
        return result
    history = [(np.log(grid[0]), first.u, v, point)]
    result["points"].append(point)
    _log(f"  {case.label} theta {point['theta']:.4g}: {point['classification']}")
    for scale in grid[1:]:
        (x1, u1, v1, p1), x = history[-1], np.log(scale)
        guess = u1
        if len(history) > 1:
            x0, u0 = history[-2][0], history[-2][1]
            guess = u1 + (u1 - u0) * (x - x1) / (x1 - x0)
        solution = solve(case, guess, scale) or solve(case, u1, scale)
        accepted = False
        if solution is not None:
            point, v = _point(case, solution.u, scale, theta_unit, stab=False)
            accepted = point["is_disc"] and np.max(np.abs(v - v1)) <= JUMP_V
        if not accepted:
            result["existence_boundary"] = _existence(case, history[-1], scale, theta_unit)
            _log(f"  {case.label} disc ends near theta {result['existence_boundary']['theta']:.5g}")
            _end_stability(case, result, history[-1], theta_unit)
            break
        if scale * theta_unit >= classify_from:
            point.update(classify(case, solution.u, scale))
        else:
            point["classification"] = "unclassified"
        _log(f"  {case.label} theta {point['theta']:.4g}: {point['classification']}")
        classified = point["classification"] != "unclassified"
        if (
            result["stability_boundary"] is None
            and classified
            and point["classification"] != "stable"
        ):
            if p1["classification"] == "stable":
                result["stability_boundary"] = _stability(
                    case, history[-1], (x, solution.u), theta_unit
                )
                _log(
                    f"  {case.label} stability lost at {result['stability_boundary']['theta']:.5g}"
                )
            elif p1["classification"] == "unclassified":
                result["stability_boundary"] = dict(
                    theta=None,
                    note=f"already {point['classification']} at the first classified point "
                    f"(theta {point['theta']:.4g}); not located below it",
                )
        history.append((x, solution.u, v, point))
        result["points"].append(point)
    return result


def _existence(case, last, scale_out, theta_unit):
    """Bisection in log scale on: Newton from the last disc state reaches a disc state."""
    x_in, u_in, v_in, _ = last
    x_out = np.log(scale_out)
    for _ in range(BISECTIONS):
        x = 0.5 * (x_in + x_out)
        solution = solve(case, u_in, np.exp(x))
        ok = False
        if solution is not None:
            v = case.voltages(solution.u, np.exp(x))
            ok = case.is_disc(v) and np.max(np.abs(v - v_in)) <= JUMP_V
        if ok:
            x_in, u_in, v_in = x, solution.u, v
        else:
            x_out = x
    point, _ = _point(case, u_in, np.exp(x_in), theta_unit)
    return dict(
        theta=point["theta"],
        theta_bracket=[float(np.exp(x_in) * theta_unit), float(np.exp(x_out) * theta_unit)],
        last_disc_state=point,
        kind="end of the written-disc branch (fold, or Newton reaches another state)",
        _end=(x_in, u_in),
    )


def _end_stability(case, result, last_grid, theta_unit):
    """If the branch's end state is unstable but the last grid state was stable, bisect.

    The grid can step from a stable state straight past the loss of stability
    to a point where Newton fails; the existence bisection then walks the
    branch to its end, so stability is lost in between.
    """
    end = result["existence_boundary"]
    x_end, u_end = end.pop("_end")
    if (
        result["stability_boundary"] is None
        and last_grid[3].get("classification") == "stable"
        and end["last_disc_state"]["classification"] != "stable"
    ):
        result["stability_boundary"] = _stability(case, last_grid, (x_end, u_end), theta_unit)
        _log(f"  {case.label} stability lost at {result['stability_boundary']['theta']:.5g}")


def _stability(case, last, nxt, theta_unit):
    """Bisection in log scale on the sign of the leading growth rate."""
    x_in, u_in = last[0], last[1]
    x_out, u_out = nxt
    for _ in range(BISECTIONS):
        x = 0.5 * (x_in + x_out)
        solution = solve(case, u_in, np.exp(x))
        if solution is None:
            break
        st = classify(case, solution.u, np.exp(x))
        if st["classification"] == "stable":
            x_in, u_in = x, solution.u
        else:
            x_out, u_out = x, solution.u
    inside = classify(case, u_in, np.exp(x_in))
    outside = classify(case, u_out, np.exp(x_out))
    lead = outside["leading_eigenvalues_per_s"][0]
    hopf = abs(lead[1]) > 1e-9 * max(math.hypot(*lead), 1.0)
    return dict(
        theta=float(np.exp(0.5 * (x_in + x_out)) * theta_unit),
        theta_bracket=[float(np.exp(x_in) * theta_unit), float(np.exp(x_out) * theta_unit)],
        kind="Hopf (complex pair)" if hopf else "real eigenvalue(s)",
        frequency_hz=abs(lead[1]) / (2 * math.pi) if hopf else None,
        stable_side=inside,
        unstable_side=outside,
    )


def uniform_h(theta_unit, arm_scales, gated, sheet_radius=SHEET_RADIUS):
    """Uniform H at each arm: Newton from the all-H sheet, then its spectrum.

    The declared H cells carry only P as fixed charge, so the all-H sheet is
    within the pre-screen's root residual of stationary; Newton removes it
    (identical cells: the solution is the single cell's H at any coupling).
    """
    case = Case(sheet_radius, 0, gated)
    out = []
    for scale in arm_scales:
        start = np.asarray(case.pb.evaluate(case.uniform, scale)[0])
        solution = solve(case, case.uniform, scale)
        if solution is None:
            out.append(dict(scale=scale, theta=scale * theta_unit, error="no uniform H state"))
            continue
        point, v = _point(case, solution.u, scale, theta_unit)
        point.update(
            residual_inf_at_declared_state_per_s=float(np.max(np.abs(start))),
            error_estimate=solution.error_estimate,
            voltage_spread_V=float(np.max(v) - np.min(v)),
        )
        out.append(point)
        _log(f"  uniform H {case.label['gating']} {point['theta']:.4g}: {point['classification']}")
    return out


def uniform(output):
    u = units()
    unit, arm_scales = u["theta_per_unit_scale"], np.asarray(ARMS, dtype=float)
    out = {
        ("voltage-gated" if gated else "open"): uniform_h(unit, arm_scales, gated)
        for gated in (True, False)
    }
    with open(output / "uniform_h.json", "x") as stream:
        json.dump(targets._json(dict(units=u, uniform_h=out)), stream, indent=1)
    return out


def outcome(sweep_result, theta):
    """stable / unstable / absent at theta for one case."""
    if sweep_result.get("start"):
        return "absent"
    exist = sweep_result["existence_boundary"]
    if exist is not None and theta > exist["theta"]:
        return "absent"
    for p in sweep_result["points"]:
        if abs(p["theta"] - theta) <= 1e-9 * theta:
            return p["classification"]
    return "not evaluated"


def summary_table(result):
    arms = result["units"]["arms"]
    lines = [
        "| disc | gating | stable up to theta | first change | "
        + " | ".join(f"x{m:g} (theta {arms[f'x{m:g}']['theta_slow']:.3g})" for m in ARMS)
        + " |",
        "|---|---|---|---|" + "---|" * len(ARMS),
    ]
    for case in result["cases"]:
        sb, eb = case["stability_boundary"], case["existence_boundary"]
        if sb is not None and sb.get("theta") is None:
            sb = None  # lost below the classified range: noted in the case record
        first = sb or eb
        kind = "none in range" if first is None else (sb and sb["kind"]) or "branch ends"
        crit = (
            "start"
            if case.get("start")
            else (f"{first['theta']:.4g}" if first else f">{THETA_RANGE[1]}")
        )
        if eb is not None and sb is not None:
            crit += f" (branch ends {eb['theta']:.4g})"
        cells = [outcome(case, arms[f"x{m:g}"]["theta_slow"]) for m in ARMS]
        lines.append(
            f"| {case['case']['disc_cells']} | {case['case']['gating']} | {crit} | {kind} | "
            + " | ".join(cells)
            + " |"
        )
    return "\n".join(lines)


EDGE_CASES = (  # (disc radius, gated, theta to start from, theta bound) after result.json
    (1, True, 0.60, 0.90),
    (3, True, 1.40, 2.00),
)


def edges(output, theta_unit=None):
    """Pseudo-arclength continuation across the end of the natural sweep's branch.

    The sweep's existence bisection gives a lower bound: Newton from the last
    disc state stops converging near a fold. Here the branch is followed with
    cells.analysis.continuation from just below that end, which locates folds,
    Hopf points and losses of stability (with re-walked brackets) directly.
    """
    from cells.analysis import continuation as cont

    # Dense spectra of ~1200 coordinates cost ~10 s each: shorter refinement.
    cont.REFINE_ITERATIONS, cont.REWALK_PIECES = 24, 8

    theta_unit = units()["theta_per_unit_scale"] if theta_unit is None else theta_unit
    out = []
    for disc, gated, start, bound in EDGE_CASES:
        case = Case(SHEET_RADIUS, disc, gated)
        _log(f"edge {case.label}")
        u = case.written
        for scale in np.geomspace(THETA_RANGE[0], start, 12) / theta_unit:
            solution = solve(case, u, scale)
            if solution is None:
                break
            u = solution.u
        if solution is None:
            out.append(dict(case=case.label, error="no disc state at the start coupling"))
            continue
        diagram = cont.continue_branch(
            case.pb,
            u,
            theta_start=start / theta_unit,
            step=0.05,
            max_step=1.0,
            max_points=30,
            bounds=(0.0, bound / theta_unit),
            log=_log,
        )
        diagram.pop("_states")
        for record in (*diagram["points"], *diagram["special_points"]):
            record["theta"] = record["parameter_value"] * theta_unit
        out.append(dict(case=case.label, start_theta=start, diagram=diagram))
    with open(output / "edges.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    return out


def ends(output, results):
    """Locate the loss of stability of every slow case of a saved result.json.

    The branch is rebuilt by Newton along the saved grid up to its last stable
    point (no spectra there), the existence bisection is repeated from it, and
    if the end state is unstable the stability boundary is bisected between
    the last stable point and the end. The saved sweep is not changed.
    """
    saved = json.loads(Path(results).read_text())
    theta_unit = saved["units"]["theta_per_unit_scale"]
    out = dict(source=str(results), units=saved["units"], cases=[])
    for item in saved["cases"]:
        label = item["case"]
        disc = {7: 1, 19: 2, 37: 3}[label["disc_cells"]]
        case = Case(label["sheet_radius"], disc, label["gating"] == "voltage-gated")
        _log(f"ends {case.label} sheet {label['sheet_radius']}")
        scales = [p["scale"] for p in item["points"] if p.get("classification") == "stable"]
        u, history = case.written, []
        for scale in scales:
            guess = u
            if len(history) > 1:
                (x0, u0), (x1, u1) = history[-2], history[-1]
                guess = u1 + (u1 - u0) * (np.log(scale) - x1) / (x1 - x0)
            solution = solve(case, guess, scale) or solve(case, u, scale)
            if solution is None:
                break
            u = solution.u
            history.append((np.log(scale), u))
        value = dict(case=label, rebuilt_points=len(history), saved_stable_points=len(scales))
        if not history:
            value["error"] = "branch not rebuilt"
            out["cases"].append(value)
            continue
        point, v = _point(case, u, np.exp(history[-1][0]), theta_unit)
        value["last_stable"] = point
        last = (history[-1][0], u, v, point)
        boundary = item["existence_boundary"]
        if boundary is not None:
            scale_out = boundary["theta_bracket"][1] / theta_unit
            value["existence_boundary"] = _existence(case, last, scale_out, theta_unit)
            value["stability_boundary"] = None
            _end_stability(case, value, last, theta_unit)
        out["cases"].append(value)
    with open(output / "ends.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    return out


EXTRA_DISCS = (4, 5)  # 61 and 91 cells
EXTRA_SHEET = 8  # 217 cells, about W225's size
HETEROGENEITY = dict(cell_cv=0.15, junction_cv=0.20)
HETEROGENEITY_SEEDS = (1, 2, 3)
CLASSIFY_FROM = 0.4  # below the smallest arm (0.497); every smaller disc was stable there


TRANSIENTS = (  # (disc radius, start, horizon s): written discs at x1, gated
    (3, "written", 600.0),
    (3, "fast_stationary", 3600.0),
    (2, "written", 600.0),
)
TRANSIENT_DT = 5e-3  # admitted: junction gate bound 5.2 ms at threshold 15 mV
TRANSIENT_TIMES = (0, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 1800, 2400, 3000, 3600)


def _fast_start(case_slow, disc):
    """Slow-mode coordinates of the frozen-composition disc at x1.

    The fast state at the written composition has the written amounts plus a
    node charge offset dQ and its own gates. Here dQ is carried by K (the
    largest pool: a 1 mV shift is about 2e-4 mM, 1e-6 of the K content) so the
    state is a real model state; its gates are the fast solution's.
    """
    fast = Case(SHEET_RADIUS, disc, True, mode="fast", dt=TRANSIENT_DT)
    u = fast.written
    for scale in np.geomspace(THETA_RANGE[0] / units()["theta_per_unit_scale"], 1.0, 16):
        solution = solve(fast, u, scale)
        if solution is None:
            return None, "no frozen-composition disc on the way to x1"
        u = solution.u
    parts_fast, parts_slow = fast.pb._split(u), case_slow.pb._split(np.asarray(case_slow.written))
    slow = {k: np.array(v, copy=True) for k, v in parts_slow.items()}
    charge = fast.pb.blocks[0]
    k_row = case_slow.pb.spec.model.species_ids.index("K")
    amount = next(b for b in case_slow.pb.blocks if b.field == "amount_increment")
    cells = np.asarray(case_slow.pb.p.active).size
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    for j, node in enumerate(charge.flat):
        dq = parts_fast["node_charge"][j] * charge.unit[j]
        where = np.flatnonzero(amount.flat == k_row * cells + node)
        slow["amount_increment"][where] += dq / CHARGE_PER_FMOL / amount.unit[where]
    for name in ("channel_gate", "junction_gate"):
        if name in parts_fast:
            slow[name] = np.asarray(parts_fast[name])
    return np.concatenate([slow[b.field] for b in case_slow.pb.blocks]), None


def transient(output):
    """Diagnostic: written discs at x1 run forward by the engine's own checked step.

    The question is the time scale of loss where no stationary disc exists.
    The IMEX step (model.checked_step, every step's validity enforced, a
    refusal ends the run) is iterated through the analysis step map between
    log-spaced record times; the host ledger checks are not run (the family's
    known check issue refuses runs this long), so no ledgers are carried.
    Starts: the written (uncoupled) state, and for the 37-cell disc also the
    frozen-composition disc that exists at x1 (_fast_start). Reported at each
    record: D cells inside and outside the disc and the voltage ranges.
    """
    out = dict(dt_s=TRANSIENT_DT, record_times_s=TRANSIENT_TIMES, scale=1.0, cases=[])
    for disc, start, horizon in TRANSIENTS:
        case = Case(SHEET_RADIUS, disc, True, dt=TRANSIENT_DT)
        label = dict(case.label, start=start)
        if not case.pb.step_map_admitted:
            out["cases"].append(dict(case=label, error="dt not admitted by check_steps"))
            continue
        u = np.asarray(case.written)
        if start == "fast_stationary":
            u, error = _fast_start(case, disc)
            if u is None:
                out["cases"].append(dict(case=label, error=error))
                continue
        advance = jax.jit(lambda x, k, c=case: c.pb.step_residual(x, 1.0, k))
        t, rows = 0.0, []
        _log(f"transient {label} at x1 for {horizon:g} s")
        started = time.perf_counter()
        for target in (s for s in TRANSIENT_TIMES if s <= horizon):
            if target > t:
                k = int(round((target - t) / TRANSIENT_DT))
                rate = np.asarray(advance(u, k))
                if not np.all(np.isfinite(rate)):
                    rows.append(dict(time_s=target, refused="a step was refused (NaN)"))
                    break
                u, t = u + k * TRANSIENT_DT * rate, target
            v = case.voltages(u, 1.0)
            d = v > case.threshold
            rows.append(
                dict(
                    time_s=t,
                    d_inside=int(np.sum(d[case.disc])),
                    d_outside=int(np.sum(d[~case.disc])),
                    disc_voltage_range_V=[float(v[case.disc].min()), float(v[case.disc].max())],
                    outside_voltage_range_V=[
                        float(v[~case.disc].min()),
                        float(v[~case.disc].max()),
                    ],
                )
            )
            _log(
                f"  t {t:7.1f} s: D inside {rows[-1]['d_inside']}, outside {rows[-1]['d_outside']}"
            )
        out["cases"].append(
            dict(
                case=label,
                horizon_s=horizon,
                wall_seconds=time.perf_counter() - started,
                trajectory=rows,
            )
        )
    with open(output / "transient.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    return out


def extra(output):
    """Larger discs (61, 91 cells, 217-cell sheet) and heterogeneous 37-cell discs, gated."""
    u = units()
    unit, arm_scales = u["theta_per_unit_scale"], np.asarray(ARMS, dtype=float)
    global BISECTIONS
    BISECTIONS = 10  # 2^-10 of a grid interval (factor 1.45): 0.04 percent in theta
    out = dict(units=u, heterogeneity=HETEROGENEITY, bisections=BISECTIONS, cases=[], failures=[])
    runs = [(SHEET_RADIUS, 3, dict(seed=k, **HETEROGENEITY)) for k in HETEROGENEITY_SEEDS]
    runs += [(EXTRA_SHEET, d, None) for d in EXTRA_DISCS]
    for sheet, disc, hetero in runs:
        try:
            case = Case(sheet, disc, True, heterogeneity=hetero)
            _log(f"extra case sheet {sheet} {case.label}")
            value = sweep(case, unit, arm_scales, classify_from=CLASSIFY_FROM)
            value["case"]["sheet_radius"] = sheet
            out["cases"].append(value)
        except Exception as error:  # Kept as evidence.
            out["failures"].append(
                dict(
                    case=[sheet, disc, hetero], error=repr(error), traceback=traceback.format_exc()
                )
            )
    with open(output / "extra.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(output / "extra_table.md", "x") as stream:
        stream.write(summary_table(targets._json(out)) + "\n")
    return out


def _key(label):
    het = label.get("heterogeneity")
    return (
        label["sheet_cells"],
        label["disc_cells"],
        label["gating"],
        label.get("mode", "slow"),
        None if not het else het.get("seed"),
    )


def _row(case, ends_case, arms):
    """One map row: stability loss, branch end and the arms' outcomes."""
    label = case["case"]
    sb = (ends_case or {}).get("stability_boundary") or case.get("stability_boundary")
    if sb is not None and sb.get("theta") is None:
        sb = None
    eb = case.get("existence_boundary")
    theta_end = None if eb is None else eb["theta"]
    theta_stab = theta_end if sb is None else sb["theta"]
    row = dict(
        sheet_cells=label["sheet_cells"],
        disc_cells=label["disc_cells"],
        gating=label["gating"],
        mode=label.get("mode", "slow"),
        heterogeneity=label.get("heterogeneity"),
        start=case.get("start"),
        theta_stability_loss=None if sb is None else sb["theta"],
        loss_kind=None if sb is None else sb["kind"],
        loss_frequency_hz=None if sb is None else sb.get("frequency_hz"),
        loss_unstable_side_leading_per_s=None
        if sb is None
        else sb["unstable_side"]["leading_eigenvalues_per_s"][:3],
        theta_end=theta_end,
        stable_up_to=theta_stab,
    )
    outcomes = {}
    for name, arm in arms.items():
        theta = arm["theta_slow"]
        if case.get("start"):
            outcomes[name] = "absent"
        elif theta_end is not None and theta > theta_end:
            outcomes[name] = "absent"
        elif theta_stab is not None and theta >= theta_stab:
            outcomes[name] = "unstable"
        else:
            outcomes[name] = outcome(case, theta)
    row["arms"] = outcomes
    return row


def _transient_row(case):
    """Record times bracketing the loss of D cells in one transient."""
    label, rows = case["case"], case.get("trajectory", [])
    records = [r for r in rows if "d_inside" in r]
    disc = label["disc_cells"]
    first = next((r["time_s"] for r in records if r["d_inside"] < disc), None)
    gone = next((r["time_s"] for r in records if r["d_inside"] == 0), None)
    held = [
        r["time_s"]
        for r in records
        if r["d_inside"] == disc and r["d_outside"] == 0 and (first is None or r["time_s"] < first)
    ]
    return dict(
        disc_cells=disc,
        start=label.get("start"),
        horizon_s=case.get("horizon_s"),
        error=case.get("error"),
        refused=next((r["refused"] for r in rows if "refused" in r), None),
        last_all_d_s=held[-1] if held else None,
        first_loss_by_s=first,
        all_lost_by_s=gone,
        d_inside_end=records[-1]["d_inside"] if records else None,
        d_outside_end=records[-1]["d_outside"] if records else None,
        last_time_s=records[-1]["time_s"] if records else None,
    )


def summarize(directory):
    """Combine the main sweep, its ends, the extras, fast sweeps, uniform H and transients."""
    directory = Path(directory)

    def load(name):
        path = directory / name
        return json.loads(path.read_text()) if path.exists() else None

    main = load("result.json")
    ends_saved = load("followup/ends.json") or dict(cases=[])
    fast_saved = load("followup/fast.json") or dict(cases=[])
    extra_saved = load("extra/extra.json") or dict(cases=[])
    uniform_saved = load("uniform/uniform_h.json")
    transient_saved = load("transient/transient.json") or dict(cases=[])
    arms = main["units"]["arms"]
    ends_by = {_key(c["case"]): c for c in ends_saved["cases"]}
    rows = [_row(c, ends_by.get(_key(c["case"])), arms) for c in main["cases"]]
    rows += [_row(c, None, arms) for c in extra_saved["cases"]]
    fast_rows = [_row(c, None, arms) for c in fast_saved["cases"]]
    uniform = {
        gating: {f"x{p['scale']:g}": p.get("classification", p.get("error")) for p in points}
        for gating, points in (uniform_saved or {}).get("uniform_h", {}).items()
    }
    out = dict(
        kind="cells.heredity_design_prescreen@7_summary",
        units=main["units"],
        slow=rows,
        fast=fast_rows,
        uniform_h=uniform,
        transient=[_transient_row(c) for c in transient_saved["cases"]],
        sources=dict(
            main="result.json",
            ends="followup/ends.json",
            fast="followup/fast.json",
            extra="extra/extra.json",
            uniform="uniform/uniform_h.json",
            transient="transient/transient.json",
        ),
    )
    with open(directory / "final.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    lines = [
        "| mode | disc | sheet | gating | heterogeneity | stable up to theta | loss | ends | "
        + " | ".join(f"x{m:g} ({arms[f'x{m:g}']['theta_slow']:.3g})" for m in ARMS)
        + " |",
        "|---|---|---|---|---|---|---|---|" + "---|" * len(ARMS),
    ]
    for r in rows + fast_rows:
        het = r["heterogeneity"]
        het = "none" if not het else f"seed {het['seed']}"

        def fmt(v):
            return "-" if v is None else f"{v:.4g}"

        loss = "-" if r["loss_kind"] is None else r["loss_kind"].split(" ")[0]
        loss = "no start" if r["start"] else loss
        lines.append(
            f"| {r['mode']} | {r['disc_cells']} | {r['sheet_cells']} | {r['gating']} | {het} | "
            f"{fmt(r['stable_up_to'])} | {loss} | {fmt(r['theta_end'])} | "
            + " | ".join(r["arms"][f"x{m:g}"] for m in ARMS)
            + " |"
        )
    if out["transient"]:
        lines += [
            "",
            "| transient at x1 | disc | start | horizon s | all D at s | first D lost by s | "
            "all lost by s | D inside at end | D outside at end | note |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in out["transient"]:
            cells = [r["disc_cells"], r["start"], r["horizon_s"], r["last_all_d_s"]]
            cells += [r["first_loss_by_s"], r["all_lost_by_s"], r["d_inside_end"]]
            cells += [r["d_outside_end"], r["error"] or r["refused"]]
            text = " | ".join("-" if c is None else f"{c}" for c in cells)
            lines.append(f"| gated | {text} |")
    with open(directory / "final_table.md", "x") as stream:
        stream.write("\n".join(lines) + "\n")
    return out


def fast(output):
    """The same sweeps at frozen composition (written amounts): the seconds-scale question.

    A disc absent from the slow map can still be held for a while if a
    frozen-composition disc state exists and is stable: the written state then
    decays only as the ions drift (hours). Absent here means it collapses on
    the electrical and gate time scale.
    """
    u = units()
    unit, arm_scales = u["theta_per_unit_scale"], np.asarray(ARMS, dtype=float)
    out = dict(units=u, cases=[])
    for disc in DISC_RADII:
        for gated in (True, False):
            case = Case(SHEET_RADIUS, disc, gated, mode="fast")
            _log(f"fast case {case.label}")
            out["cases"].append(sweep(case, unit, arm_scales))
    with open(output / "fast.json", "x") as stream:
        json.dump(targets._json(out), stream, indent=1)
    with open(output / "fast_table.md", "x") as stream:
        stream.write(summary_table(targets._json(out)) + "\n")
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quick", action="store_true", help="disc 7 only, both gatings")
    parser.add_argument("--edges", action="store_true", help="only the branch-end check")
    parser.add_argument("--fast", action="store_true", help="only the frozen-composition sweeps")
    parser.add_argument("--ends", type=Path, help="stability ends of a saved result.json")
    parser.add_argument("--uniform", action="store_true", help="only the uniform-H stability")
    parser.add_argument("--extra", action="store_true", help="larger and heterogeneous discs")
    parser.add_argument("--summarize", action="store_true", help="final.json from all parts")
    parser.add_argument("--transient", action="store_true", help="written discs at x1, forward")
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)  # result.json is never overwritten
    if args.edges:
        edges(args.output)
        _log("edges done")
        return 0
    if args.ends:
        ends(args.output, args.ends)
        _log("ends done")
        return 0
    if args.uniform:
        uniform(args.output)
        _log("uniform done")
        return 0
    if args.extra:
        extra(args.output)
        _log("extra done")
        return 0
    if args.summarize:
        summarize(args.output)
        return 0
    if args.transient:
        transient(args.output)
        _log("transient done")
        return 0
    if args.fast:
        fast(args.output)
        _log("fast done")
        return 0
    started = time.perf_counter()
    result = dict(
        kind="cells.heredity_design_prescreen@7",
        scope="Design input only (development analysis, not judged): written-disc stationary "
        "states, stability and critical couplings for E07-v1 on held-bath sheets.",
        analysis=sa.ANALYSIS_ID,
        engine_model="resolved_pump_tissue@3",
        cells_version=__version__,
        sheet_radius=SHEET_RADIUS,
        theta_range=THETA_RANGE,
        cases=[],
        uniform_h={},
        failures=[],
    )
    status = 0
    try:
        result["units"] = units()
        unit = result["units"]["theta_per_unit_scale"]
        arm_scales = np.asarray(ARMS, dtype=float)
        for gated in (True, False):
            name = "voltage-gated" if gated else "open"
            _log(f"uniform H, {name}")
            result["uniform_h"][name] = uniform_h(unit, arm_scales, gated)
        cases = [
            (SHEET_RADIUS, r, g)
            for r in ((1,) if args.quick else DISC_RADII)
            for g in (True, False)
        ]
        if not args.quick:
            b = BOUNDARY_CHECK
            cases.append((b["radius"], b["disc"], b["gated"]))
        for sheet, disc, gated in cases:
            _log(f"case sheet {sheet} disc radius {disc} gated {gated}")
            try:
                value = sweep(Case(sheet, disc, gated), unit, arm_scales)
                value["case"]["sheet_radius"] = sheet
                result["cases"].append(value)
            except Exception as error:  # Kept as evidence.
                status = 1
                result["failures"].append(
                    dict(
                        case=[sheet, disc, gated],
                        error=repr(error),
                        traceback=traceback.format_exc(),
                    )
                )
    except Exception as error:
        status = 1
        result["failures"].append(dict(error=repr(error), traceback=traceback.format_exc()))
    result["wall_seconds"] = time.perf_counter() - started
    result["max_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    with open(args.output / "result.json", "x") as stream:
        json.dump(targets._json(result), stream, indent=1)
    if result["cases"]:
        with open(args.output / "table.md", "x") as stream:
            stream.write(summary_table(targets._json(result)) + "\n")
    _log("done" if status == 0 else "done with failures")
    return status


if __name__ == "__main__":
    sys.exit(main())
