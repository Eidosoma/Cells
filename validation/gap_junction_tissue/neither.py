"""The "neither" comparison (decision (b)): the driver of its development runs and of GJ-N1's
judged searches (docs/GJ_NEITHER_REGISTRATION.md, judged by neither_judge.py).

A comparison with BITSEY's log at b2cb370 (D208), not with the preprint. Its two conditions are
written in docs/GAP_JUNCTION_CANCER_REPLICATION.md section 7 before the search; the judged
comparison (both geometries, the line and BITSEY's 25 x 25 field) is GJ-N1's, judged by
neither_judge.py (docs/GJ_NEITHER_REGISTRATION.md):
1. In BITSEY's "no tricks" run every junction's dV is 0, so the miRNA's valence -1 drift vanishes
   and its junction transport is Fick's: a neutral miRNA is the same model there.
2. The world, criterion, bracket and tolerance are BITSEY's (cancer_GJ_sims/zombie.py at b2cb370):
   a line of 25 cells with a 6-cell tumor at one end; seeds miR200/Zeb mRNA/ZEB 0/100/100
   (tumor) and 100/0/0 (healthy, scaled coordinates); 500 time units uncoupled, then 20,000
   coupled; normalized when every cell ends with miR200 > Zeb mRNA + 2; the junction diffusion
   constant D searched in [0, 1e-13] m^2/s until x2 <= 1.001 x0, reporting x2; G_GJ = D x 4 pi
   (5 um)^2 / 100 nm. In development (neither-01, -02) agreement was called if Cells' x2 / 7.18e-15
   lay in [0.95, 1.05]; GJ-N1 replaces that band with its verdict (R, C and A), and the search
   reports its threshold alone. The field adds BITSEY's row-spread condition.

The protocol has BITSEY's two stages (find_min_Kd_tumorFix): the uncoupled 500 s are run once,
from the seeds, in a world of one tumor cell and one healthy cell with no junctions (every tumor
cell, and every healthy cell, is the same while uncoupled); their end state seeds every coupled
run, as cc_discon does. The switch is autonomous, so each coupled run starts its clock at 0.

The model, on today's engine (nothing here adds physics):
* cells.model.resolved_pump_composite@1 over cells.model.resolved_pump_tissue@3, the species-only world of the
  secreted-species fixtures (ions at the bath's composition, zero permeability, so nothing but the
  switch's species moves);
* the EMT switch as cells.operator.local_species_reactions@1 reactions per cell (worlds.emt_switch_probe's
  structure) with GRN_miRNA.py's constants at b2cb370 as docs/EMT_REFERENCE.md states them, Snail
  72 folded into the rates, one scaled unit = 1 uM, BITSEY's time unit taken as 1 s;
* in the coupled stage, miR200 (u) alone on a cells.kind.passive_routes@1 route
  (cells.route.passive_neutral_permeation@1) on each junction, P A = G_GJ, junction gates pinned open; no
  routes at D = 0.
Seeds BITSEY sets to 0 start at the fixtures' trace, 1e-9 mM (1e-6 units): @3 needs positive
amounts.

The search runs one point per CPU of --cpus at a time, each in its own process pinned to one CPU:
first the bracket's ends and its bisection points 1e-13 / 2^k (k = 1..); then, whenever a point
finishes, its worker takes a new point inside the current bracket (search, place). Outcomes are
assumed monotone in D; a non-monotone set is reported, not repaired. After convergence, the final
bracket's two ends are rerun at half their step: reported, not used to move the threshold. Each
run is windowed (cells.execution.windows, recording observations, device row checks; every engine
check still runs). Every point's result is appended to OUTDIR/points.jsonl (the half-step reruns
to OUTDIR/half_step.jsonl) and the search state written to OUTDIR/search.json as points finish.

Records for the viewer (--record): stage 1, then the coupled stage at each given D written by the
engine's windowed writer (cells.records.window_io.write_windowed_run, observed rows every RECORD_EVERY_S)
under OUTDIR/viewer/neither-d<D>/ with its run view (cells.run_view@1: the line of cells as touching
spheres) and run.json; a refused view is recorded and the run written without one.

Usage (from a snapshot root, PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu):
    python -B validation/gap_junction_tissue/neither.py OUTDIR --cpus 0,1,2,3,16,17,18,19
    python -B validation/gap_junction_tissue/neither.py OUTDIR --points 1e-14 --end 600  (a probe)
    python -B validation/gap_junction_tissue/neither.py OUTDIR --record 6e-15,7.2e-15,9e-15
"""  # noqa: E501

import argparse
import json
import math
import multiprocessing
import os
import resource
import time
import traceback
from pathlib import Path

N_CELLS = 25
TUMOR = 6
R_CELL_M = 5e-6
V_CELL_PL = 4.0 / 3.0 * math.pi * R_CELL_M**3 * 1e15
A_CELL_M2 = 4.0 * math.pi * R_CELL_M**2
L_GJ_M = 100e-9
UNIT_mM = 1e-3  # One scaled unit is 1 uM.
TRACE_UNITS = 1e-6  # The fixtures' trace, 1e-9 mM: where BITSEY seeds 0.
SEEDS = {"tumor": {"u": 0.0, "m": 100.0, "z": 100.0}, "healthy": {"u": 100.0, "m": 0.0, "z": 0.0}}
UNCOUPLED_S = 500.0
COUPLED_S = 20000.0
BRACKET = (0.0, 1e-13)
RTOL = 1e-3
MARGIN_UNITS = 2.0
OBSERVE_EVERY_S = 1000.0
WINDOW_STEPS = 1024
STEP_BOUND_MARGIN = 0.04  # dt x @3's explicit rate, the driver's rule (worlds.STEP_BOUND_MARGIN).
# The largest step. Every D up to 0.04 / (0.125 s x 2.4e13 m^-2) = 1.33e-14 m^2/s runs at 1/8 s, so
# the points that decide a threshold in (1.6e-15, 1.3e-14) share one step; above, the bound halves
# it (1/16 s to 2.7e-14, 1/32 s to 5.3e-14, 1/64 s at the bracket's upper end).
BASE_DT_S = 0.125
# GRN_miRNA.py at b2cb370 (docs/EMT_REFERENCE.md), Snail 72 folded in: synthesis g H(s) with
# H(s; 72, 2, lambda) = (1 + lambda)/2 at s = 72.
U_SYNTHESIS = 6.0 * (1.0 + 0.4) / 2.0  # 4.2 units/s, times H(z; 100/9, 3, 0.1)
M_SYNTHESIS = (5.0 / 12.0) * (1.0 + 10.0) / 2.0  # 55/24 units/s, times H(z; 25/9, 2, 15)
U_HILL = (100.0 / 9.0, 3.0, 0.1)  # (K units, n, lambda) of ZEB on miR200
M_HILL = (25.0 / 9.0, 2.0, 15.0)  # (K units, n, lambda) of ZEB on Zeb mRNA
X0_UNITS = 40.0  # miR200's binding constant to Zeb mRNA
Z_TRANSLATION = 1.0 / 6.0  # per unit Zeb mRNA per s
L_SITES = (1.0, 0.5, 0.2, 0.02, 0.02, 0.02, 0.02)
DECAY = {"u": 0.05, "m": 0.5, "z": 0.1}
BINOMIAL6 = (1, 6, 15, 20, 15, 6, 1)
NAMES = ("u", "m", "z")


def conductance(d):
    """G_GJ (m^3/s) of BITSEY's junction at diffusion constant d: d x cell area / its length."""
    return d * A_CELL_M2 / L_GJ_M


def junction_rate(d, neighbours=2):
    """@3's explicit rate for the coupled world (1/s): 2 x the largest sum of G_GJ / V over a
    cell's junction routes (an interior cell has two on the line, four on the sheet)."""
    return 2.0 * neighbours * conductance(d) / (V_CELL_PL * 1e-15)


def step(d, neighbours=2):
    dt = BASE_DT_S
    while dt * junction_rate(d, neighbours) > STEP_BOUND_MARGIN:
        dt /= 2.0
    return dt


# The sheet: an extension beyond the replication (note section 7.6), the same switch, seeds and
# protocol on a square sheet with 4-neighbour junctions and a square tumor patch in the middle.
SHEET_N = 9
SHEET_TUMOR = 3
# The field: BITSEY's 1x25x25 field, the "neither" comparison's 2D geometry (docs/
# GJ_NEITHER_REGISTRATION.md). cancer_GJ_sims/zombie.py at b2cb370: coord_set_dimensions(1, 25,
# 25), setup_GJ_3D(allow_diag=False), one junction per pair of cells one lattice step apart, and
# set_corner_tumor(6), which puts the 6x6 tumor at y < 6 and z < 6. A cell's lattice place is
# (y, z), its index y * FIELD_N + z (coord_xyz2idx with x = 0).
FIELD_N = 25
FIELD_TUMOR = 6
# GRN_miRNA.py's healthy_snapped_rows, line 519: besides every cell's miR200 > Zeb mRNA + 2, every
# row's Zeb mRNA spread (largest minus smallest) is at most this. A row is the set of cells with
# one z, so its spread is taken over y (the min and max over the first two lattice axes, per
# last-axis index). On the line each row is one cell, so the condition is empty there.
ROW_SPREAD_UNITS = 2.0
SHAPES = ("line", "sheet", "field")


def tissue(shape):
    """(cells ((id, kind)), junctions ((id, a, b)), centres in um, neighbours) of a shape: 'line',
    BITSEY's 1x1x25 field (the replication), 'field', BITSEY's 1x25x25 field (the replication's 2D
    geometry), or 'sheet', SHEET_N x SHEET_N cells with a SHEET_TUMOR x SHEET_TUMOR tumor in the
    middle (an extension beyond it)."""
    spacing = 2.0 * R_CELL_M * 1e6
    if shape == "line":
        cells = tuple((f"c{k}", "tumor" if k < TUMOR else "healthy") for k in range(N_CELLS))
        junctions = tuple((f"j{k}", f"c{k}", f"c{k + 1}") for k in range(N_CELLS - 1))
        return cells, junctions, [[k * spacing, 0.0] for k in range(N_CELLS)], 2
    if shape == "field":
        n, t = FIELD_N, FIELD_TUMOR
        cells = tuple(
            (f"c{y}_{z}", "tumor" if y < t and z < t else "healthy")
            for y in range(n)
            for z in range(n)
        )
        junctions = []
        for y in range(n):  # BITSEY's allocation order: per cell, its z step, then its y step.
            for z in range(n):
                if z + 1 < n:
                    junctions.append((f"jz{y}_{z}", f"c{y}_{z}", f"c{y}_{z + 1}"))
                if y + 1 < n:
                    junctions.append((f"jy{y}_{z}", f"c{y}_{z}", f"c{y + 1}_{z}"))
        centres = [[z * spacing, y * spacing] for y in range(n) for z in range(n)]
        return cells, tuple(junctions), centres, 4
    if shape == "sheet":
        n, lo = SHEET_N, (SHEET_N - SHEET_TUMOR) // 2
        inside = range(lo, lo + SHEET_TUMOR)
        cells = tuple(
            (f"c{r}_{c}", "tumor" if r in inside and c in inside else "healthy")
            for r in range(n)
            for c in range(n)
        )
        junctions = []
        for r in range(n):
            for c in range(n):
                if c + 1 < n:
                    junctions.append((f"jh{r}_{c}", f"c{r}_{c}", f"c{r}_{c + 1}"))
                if r + 1 < n:
                    junctions.append((f"jv{r}_{c}", f"c{r}_{c}", f"c{r + 1}_{c}"))
        centres = [[c * spacing, r * spacing] for r in range(n) for c in range(n)]
        return cells, tuple(junctions), centres, 4
    raise ValueError(f"Unknown shape {shape!r}")


def row_spreads(m, shape):
    """Each row's Zeb mRNA spread (units), largest minus smallest over its cells, for the shapes
    BITSEY's criterion covers: on the line every row is one cell (spread 0); on the field a row is
    the cells of one z. None for the sheet, which has no BITSEY counterpart."""
    if shape == "line":
        return [0.0] * len(m)
    if shape == "field":
        n = FIELD_N
        rows = [[m[y * n + z] for y in range(n)] for z in range(n)]
        return [max(row) - min(row) for row in rows]
    return None


def criterion(u, m, shape="line"):
    """BITSEY's healthy_snapped_rows on the end state: every cell's miR200 exceeds its Zeb mRNA by
    more than MARGIN_UNITS, and every row's Zeb mRNA spread is at most ROW_SPREAD_UNITS."""
    margins = [a - b - MARGIN_UNITS for a, b in zip(u, m, strict=True)]
    spreads = row_spreads(m, shape)
    spread_ok = spreads is None or all(s <= ROW_SPREAD_UNITS for s in spreads)
    return dict(
        normalized=all(x > 0.0 for x in margins) and spread_ok,
        epithelial_cells=sum(x > 0.0 for x in margins),
        min_margin_units=min(margins),
        max_row_spread_units=None if spreads is None else max(spreads),
        rows_over_spread=None if spreads is None else sum(s > ROW_SPREAD_UNITS for s in spreads),
    )


def switch_world(cells, start, *, junctions=(), d=0.0, end, dt, observe):
    """The switch in each of `cells` ((cell id, kind)), started at start[kind][species] (units),
    with miR200 on a passive route on each junction at diffusion constant d."""
    from validation.tissue import species_reactions_fixtures as rfx

    profile = {
        name: {cell_id: max(start[kind][name], TRACE_UNITS) * UNIT_mM for cell_id, kind in cells}
        for name in NAMES
    }
    raw = rfx.species_world(
        extra=NAMES,
        faces=False,
        cells=tuple((cell_id, V_CELL_PL) for cell_id, _ in cells),
        nodes=(),
        contacts=(),
        junctions=junctions,
        dt=dt,
        end=end,
        observation_times=observe,
        profile=profile,
    )
    m = raw["model"]
    for junction in m["junctions"]:
        junction["gate"].update(
            threshold_voltage_V=0.0, minimum_open_fraction=1.0, initial_gate=1.0
        )
    if d > 0.0:
        m["passive_routes"] = [
            dict(
                id=f"{j['id']}_mir200",
                junction=j["id"],
                law="cells.route.passive_neutral_permeation@1",
                species="u",
                permeability_m_per_s=conductance(d) / j["area_m2"],
            )
            for j in m["junctions"]
        ]
    sites = {"cells": "all"}
    k_u, n_u, lam_u = U_HILL
    k_m, n_m, lam_m = M_HILL
    reactions = [
        rfx.mass_action(
            "u_inhibited",
            sites,
            {},
            {"u": 1},
            U_SYNTHESIS * UNIT_mM,
            [rfx.hill("hill_inhibition", "z", k_u * UNIT_mM, n_u)],
        ),
        rfx.mass_action(
            "u_activated",
            sites,
            {},
            {"u": 1},
            U_SYNTHESIS * lam_u * UNIT_mM,
            [rfx.hill("hill_activation", "z", k_u * UNIT_mM, n_u)],
        ),
        rfx.mass_action(
            "m_inhibited",
            sites,
            {},
            {"m": 1},
            M_SYNTHESIS * UNIT_mM,
            [rfx.hill("hill_inhibition", "z", k_m * UNIT_mM, n_m)],
        ),
        rfx.mass_action(
            "m_activated",
            sites,
            {},
            {"m": 1},
            M_SYNTHESIS * lam_m * UNIT_mM,
            [rfx.hill("hill_activation", "z", k_m * UNIT_mM, n_m)],
        ),
    ]
    for i in range(7):
        factors = [rfx.hill("hill_activation", "u", X0_UNITS * UNIT_mM, 1.0)] * i
        factors += [rfx.hill("hill_inhibition", "u", X0_UNITS * UNIT_mM, 1.0)] * (6 - i)
        rate = Z_TRANSLATION * BINOMIAL6[i] * L_SITES[i]
        reactions.append(
            rfx.mass_action(f"z_site{i}", sites, {"m": 1}, {"m": 1, "z": 1}, rate, factors)
        )
    for name, k in DECAY.items():
        reactions.append(rfx.mass_action(f"{name}_decay", sites, {name: 1}, {}, k))
    controls = [(r["id"], None, [(0.0, 1.0)]) for r in reactions]
    return rfx.with_reactions(raw, [rfx.species(n) for n in NAMES], reactions, controls)


def declared_field_solver(raw, shape):
    """raw with the field solver its shape runs under GJ-N1's amendment 1 (docs/
    GJ_NEITHER_REGISTRATION.md, tag gj-n1-amendment-1-2026-11-23): the field's worlds, its stage 1
    among them, declare FR-17's sparse field solver, qualified against version 2 (docs/
    FIELD_SOLVER_INTERFACE_DESIGN.md §8.5); the line and the sheet keep the version 2 their
    definitions declare, as they ran."""
    if shape == "field":
        from cells.numerics.surface_field import SPARSE_SOLVER_ID

        raw["execution"]["field_solver"] = SPARSE_SOLVER_ID
    return raw


def uncoupled_world(*, end=UNCOUPLED_S, dt=None, neighbours=2, shape=None):
    """Stage 1: one tumor cell and one healthy cell, no junctions, from BITSEY's seeds. Its dt is
    the finest coupled step (the bracket's upper end, with the shape's neighbours: 1/64 s on the
    line, 1/128 s on the field), so stage 1 is never the coarser stage. shape: the search it seeds,
    for its field solver (declared_field_solver)."""
    dt = step(BRACKET[1], neighbours) if dt is None else dt
    observe = sorted(
        {0.0, *(k * 100.0 for k in range(int(end // 100.0) + 1) if k * 100.0 < end), end}
    )
    cells = (("tumor", "tumor"), ("healthy", "healthy"))
    raw = switch_world(cells, SEEDS, end=end, dt=dt, observe=observe)
    return declared_field_solver(raw, shape)


def coupled_world(d, start, *, end=COUPLED_S, dt=None, shape="line"):
    """Stage 2: the line of 25 cells, the first TUMOR of them tumor (or the sheet: tissue), from
    stage 1's end state."""
    cells, junctions, _, neighbours = tissue(shape)
    dt = step(d, neighbours) if dt is None else dt
    observe = sorted(
        {0.0, *(k * OBSERVE_EVERY_S for k in range(int(end // OBSERVE_EVERY_S) + 1)), end}
    )
    observe = [t for t in observe if t <= end]
    raw = switch_world(cells, start, junctions=junctions, d=d, end=end, dt=dt, observe=observe)
    return declared_field_solver(raw, shape)


def execute(raw, n_cells, window_steps=WINDOW_STEPS):
    """Run a world windowed with device row checks; the end state in units per cell, the observed
    rows of u and m, the steps, diagnostics and timings (the parse, and each window's wall time,
    which includes the first window's compile)."""
    import numpy as np

    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows

    started = time.perf_counter()
    spec = parse_spec(raw)
    parsed = time.perf_counter()
    ids = list(spec.model.species_ids)
    rows = {name: ids.index(name) for name in NAMES}
    last, diagnostics, observed = None, {}, dict(times=[], u=[], m=[])
    policy = WindowPolicy(window_steps, "observations", "device")
    timing = dict(parse_s=parsed - started, window_steps=window_steps, windows_s=[])
    clock = parsed
    for window in iter_windows(spec, policy):
        now = time.perf_counter()
        timing["windows_s"].append(now - clock)
        clock = now
        last = window.final
        for k, v in window.diagnostics.items():
            diagnostics[k] = max(diagnostics.get(k, 0.0), float(v))
        obs = window.observations
        if obs is not None and hasattr(obs, "amount_increment"):
            reference = np.asarray(window.final.layout.amount_reference)
            volume = np.asarray(window.final.layout.volume)[:n_cells]
            for row, when in enumerate(np.asarray(obs.times)):
                if observed["times"] and when <= observed["times"][-1]:
                    continue
                amount = reference + np.asarray(obs.amount_increment)[row]
                observed["times"].append(float(when))
                for name in ("u", "m"):
                    units = amount[rows[name], :n_cells] / volume / UNIT_mM
                    observed[name].append(units.tolist())
    amount = np.asarray(last.layout.amount_reference) + np.asarray(last.state.amount_increment)
    volume = np.asarray(last.layout.volume)[:n_cells]
    final = {name: (amount[rows[name], :n_cells] / volume / UNIT_mM).tolist() for name in NAMES}
    return dict(
        definition_sha256=spec.fingerprint,
        dt_s=spec.execution.dt,
        final_time_s=float(last.time),
        steps=int(last.step_index),
        final_units=final,
        observed=observed,
        diagnostics=diagnostics,
        timing=timing,
    )


# Stage 1's step follows the finest coupled step of the shape's search (uncoupled_world). The sheet
# keeps the line's, as its records ran it (sheet-01).
STAGE1_NEIGHBOURS = dict(line=2, sheet=2, field=4)


def uncoupled(shape="line"):
    """Stage 1, once: the tumor and healthy cells' state after UNCOUPLED_S, at the shape's finest
    coupled step (uncoupled_world)."""
    started = time.perf_counter()
    out = dict(stage="uncoupled", end_s=UNCOUPLED_S, seeds_units=SEEDS, shape=shape)
    try:
        run = execute(uncoupled_world(neighbours=STAGE1_NEIGHBOURS[shape], shape=shape), 2)
        start = {
            kind: {name: run["final_units"][name][k] for name in NAMES}
            for k, kind in enumerate(("tumor", "healthy"))
        }
        out.update(status="done", start_units=start, **run)
    except Exception as error:  # Recorded as evidence, never retried.
        out.update(status="failed", error=repr(error), traceback=traceback.format_exc())
    out.update(seconds=time.perf_counter() - started, max_rss_kib=_rss())
    return out


def evaluate(d, start, *, end=COUPLED_S, dt=None, shape="line"):
    """One point: the coupled stage at diffusion constant d (at step dt, default the shape's
    step(d)); BITSEY's criterion at its end (criterion)."""
    started = time.perf_counter()
    out = dict(
        d=d,
        end_s=end,
        shape=shape,
        g_gj_m3_s=conductance(d),
        pid=os.getpid(),
        cpus=sorted(os.sched_getaffinity(0)),
    )
    try:
        cells = tissue(shape)[0]
        raw = coupled_world(d, start, end=end, dt=dt, shape=shape)
        run = execute(raw, len(cells), WINDOW_STEPS_OF[shape])
        u, m = run["final_units"]["u"], run["final_units"]["m"]
        out.update(status="done", **criterion(u, m, shape), **run)
    except Exception as error:  # Recorded as evidence, never retried.
        out.update(status="failed", error=repr(error), traceback=traceback.format_exc())
    out.update(seconds=time.perf_counter() - started, max_rss_kib=_rss())
    return out


RECORD_EVERY_S = 100.0
RECORD_FIELDS = (
    "amount_increment",
    "passive_transferred",
    "junction_gate",
    "membrane_voltage_V",
    "junction_voltage_V",
)
EXPERIMENT = "gap-junction-cancer-neither-1d"
REPRESENTS = (
    "BITSEY's 1D no-tricks condition (a comparison with BITSEY's log saved at b2cb370, written by "
    "an earlier revision of its code): the EMT switch in a line of 25 cells, the first 6 tumor, "
    "coupled by miR200 alone on passive junction routes at junction diffusion constant D, after "
    "an uncoupled 500 s computed once. Development run of the engine, not judged (D138)."
)


def record_times(dt, end, log_rows=0):
    """The record's observed times: 0, every RECORD_EVERY_S and the end; with log_rows, as many
    log-spaced times from the first step to the end, each on the step grid (a multiple of dt), so
    that no record splits a step and the integration grid, and so the run, is unchanged."""
    times = {0.0, *(k * RECORD_EVERY_S for k in range(int(end // RECORD_EVERY_S) + 1)), end}
    if log_rows:
        steps = round(end / dt)
        for k in range(log_rows):
            fraction = k / (log_rows - 1) if log_rows > 1 else 1.0
            n = max(1, min(steps, round(math.exp(fraction * math.log(steps)))))
            times.add(n * dt)
    return sorted(t for t in times if t <= end)


SHEET_EXPERIMENT = "gap-junction-cancer-neither-sheet-extension"
SHEET_REPRESENTS = (
    "An extension beyond the replication: the neither condition's switch, seeds and protocol "
    f"on a {SHEET_N}x{SHEET_N} sheet with 4-neighbour junctions and a {SHEET_TUMOR}x{SHEET_TUMOR} "
    "tumor patch in the middle, at D values chosen around the 1D search's threshold (x2). The "
    "sheet's own threshold may differ. Development run of the engine, not judged (D138)."
)
FIELD_EXPERIMENT = "gap-junction-cancer-neither-2d"
FIELD_REPRESENTS = (
    "BITSEY's 2D no-tricks condition on its 1x25x25 field (docs/GJ_NEITHER_REGISTRATION.md): the "
    "EMT switch in 25x25 cells with one junction per pair one lattice step apart, the 6x6 corner "
    "block "
    "tumor, coupled by miR200 alone on passive junction routes at junction diffusion constant D, "
    "after an uncoupled 500 s computed once; normalized under BITSEY's healthy_snapped_rows (every "
    "cell E and every row's Zeb mRNA spread at most 2)."
)
ARM_PREFIX = dict(line="neither-d", sheet=f"sheet{SHEET_N}-d", field="field-d")
# The note's own words for the sheet (section 7.6), carried by its summary.
SHEET_NOTE = (
    "The sheet is an extension beyond the replication, not part of it. Its coupled horizon is "
    "2,000 s, a tenth of the line's, so each outcome is the state at 2,000 s "
    "(docs/GAP_JUNCTION_CANCER_REPLICATION.md, section 7.6)."
)
# The 1D search's threshold (section 7.5), against which every arm's place is stated as data.
X2_M2_S = 7.177734375e-15
# Stage 1's end state (units), as neither-02 computed it (gap-junction-20261117/runs/neither-02/
# uncoupled.json, from 1f4c740a). neither-01, picks-01 and -02, dense-01, sheet-01 and ladder-01
# each computed it again: the same definition and the same numbers. Pinned for worlds built
# without running stage 1 (crossrev's replication set); a run computes its own (uncoupled).
STAGE1_END_UNITS = {
    "tumor": {"u": 8.817966182826796, "m": 68.62439028595331, "z": 62.721311560141714},
    "healthy": {"u": 83.99620026465712, "m": 5.951805842605415, "z": 0.41005485698284977},
}
X2_SOURCE = dict(
    line="the 1D search's threshold x2 (docs/GAP_JUNCTION_CANCER_REPLICATION.md, section 7.5)",
    sheet="the line's threshold x2 (section 7.5); the sheet's own lies between x2/8 and x2/4 at "
    "2,000 s (section 7.6)",
    field="the line's threshold x2 (section 7.5), for scale only: the field's own threshold is "
    "its registered search's (docs/GJ_NEITHER_REGISTRATION.md)",
)
SPECIES_MAP = {"u": "miR200", "m": "Zeb mRNA", "z": "ZEB protein"}
X2_FRACTIONS = {
    0.0: "0",
    1 / 16: "x2/16",
    1 / 8: "x2/8",
    1 / 4: "x2/4",
    1 / 2: "x2/2",
    1.0: "x2",
    2.0: "2 x2",
}


def threshold_place(d, shape="line"):
    """An arm's place against x2, as data: its ratio, a label where it is a registered fraction,
    and its side (below, at or above)."""
    ratio = d / X2_M2_S
    label = next((v for k, v in X2_FRACTIONS.items() if abs(ratio - k) <= 1e-12), f"{ratio:.4g} x2")
    side = "at" if abs(ratio - 1.0) <= 1e-12 else ("below" if ratio < 1.0 else "above")
    return dict(
        D=d, x2=X2_M2_S, ratio_to_x2=ratio, relative_to_x2=label, side=side, source=X2_SOURCE[shape]
    )


TUMOR_CELLS_OF = {shape: [c for c, kind in tissue(shape)[0] if kind == "tumor"] for shape in SHAPES}
# A window's working storage scales with the world: the sheet's 81 cells and 144 junctions fit
# 256 steps a window. Windows cut the execution, not the step grid.
# The field's 625 cells and 1,200 junctions: FIELD_WINDOW_STEPS, sized by the cost probe
# (docs/GJ_NEITHER_REGISTRATION.md, the compute budget): 64 steps exceed the runner's 2 GB trace
# budget (the window planner refuses them); 32 ran at 0.16 s a step, 16 at 0.19 s.
FIELD_WINDOW_STEPS = 32
WINDOW_STEPS_OF = dict(line=WINDOW_STEPS, sheet=256, field=FIELD_WINDOW_STEPS)
EXPERIMENT_OF = dict(line=EXPERIMENT, sheet=SHEET_EXPERIMENT, field=FIELD_EXPERIMENT)
REPRESENTS_OF = dict(line=REPRESENTS, sheet=SHEET_REPRESENTS, field=FIELD_REPRESENTS)
LABEL_OF = dict(
    line="Neither condition, 1D",
    sheet=f"Neither condition on a {SHEET_N}x{SHEET_N} sheet (extension)",
    field=f"Neither condition on BITSEY's {FIELD_N}x{FIELD_N} field",
)
GEOMETRY_SOURCE = dict(
    line="validation/gap_junction_tissue/neither.py: a line of 25 touching cells, the tumor the "
    "first 6 (BITSEY's 1x1x25 field)",
    sheet=f"validation/gap_junction_tissue/neither.py: a {SHEET_N}x{SHEET_N} sheet of touching "
    f"cells, the tumor the middle {SHEET_TUMOR}x{SHEET_TUMOR} (an extension beyond the "
    "replication)",
    field=f"validation/gap_junction_tissue/neither.py: BITSEY's 1x{FIELD_N}x{FIELD_N} field of "
    f"touching cells, the tumor the {FIELD_TUMOR}x{FIELD_TUMOR} block at the corner (y, z < "
    f"{FIELD_TUMOR}); z along the first axis",
)


def record(out_dir, d, start, *, end=COUPLED_S, label="", log_rows=0, shape="line"):
    """The coupled stage at d written as a run record with its run view (module docstring)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy
    from cells.records import run_view
    from cells.records.window_io import write_windowed_run

    arm_id = f"{ARM_PREFIX[shape]}{d:.6g}"
    directory = Path(out_dir) / "viewer" / arm_id
    cells, _, centres, neighbours = tissue(shape)
    raw = coupled_world(d, start, end=end, shape=shape)
    raw["experiment"]["observation_times"] = record_times(step(d, neighbours), end, log_rows)
    spec = parse_spec(raw)
    geometry = run_view.Geometry(
        unit="um",
        dimensions=2,
        sets={
            "cell": {
                "kind": "spheres",
                "centres": centres,
                "radius": [R_CELL_M * 1e6] * len(cells),
            }
        },
        source=GEOMETRY_SOURCE[shape],
    )
    labels = dict(
        id=arm_id,
        experiment=EXPERIMENT_OF[shape],
        arm=arm_id,
        label=f"{LABEL_OF[shape]}: D = {d:.4g} m^2/s",
    )
    provenance = dict(
        operation="fresh",
        driver="validation/gap_junction_tissue/neither.py",
        experiment=EXPERIMENT_OF[shape],
        arm=arm_id,
        d_m2_s=d,
        **_snapshot_identity(),
    )
    policy = WindowPolicy(WINDOW_STEPS_OF[shape], "observations", "device")
    request = run_view.Request(
        labels,
        geometry=geometry,
        recording=run_view.Recording(
            # D = 0 declares no routes, so it records no route transfers.
            fields=tuple(f for f in RECORD_FIELDS if d > 0.0 or f != "passive_transferred"),
            elements={"species": list(NAMES)},
        ),
    )
    started = time.perf_counter()
    out = dict(
        arm=arm_id,
        d=d,
        directory=str(directory),
        dt_s=spec.execution.dt,
        status="done",
        shape=shape,
        cells=[c for c, _ in cells],
        tumor=[c for c, kind in cells if kind == "tumor"],
    )
    n_cells = len(cells)
    try:
        write_windowed_run(directory, spec, policy, provenance=provenance, view=request)
        out["view"] = "written"
    except run_view.ViewRefused as error:
        write_windowed_run(directory, spec, policy, provenance=provenance)
        out.update(view="refused", refusal=str(error))
    out["seconds"] = time.perf_counter() - started
    ids = list(spec.model.species_ids)
    out["final_units"] = final_units(directory, ids, n_cells)
    out["place"] = threshold_place(d, shape)
    out["sidecar"] = criterion_sidecar(directory, ids, n_cells, out["tumor"], out["place"])
    out["species_sidecars"] = species_sidecars(directory, ids, n_cells)
    entry = dict(
        format="gap_junction_tissue.neither_run@1",
        status="development run of the engine, not judged (D138)",
        represents=REPRESENTS_OF[shape],
        models=["cells.model.resolved_pump_composite@1", "cells.model.resolved_pump_tissue@3"],
        laws=dict(
            switch="cells.operator.local_species_reactions@1 (GRN_miRNA.py's constants at b2cb370)",
            junction_route="cells.route.passive_neutral_permeation@1 (cells.kind.passive_routes@1), miR200 only",
            junction_gate="cells.junction.junction_voltage_relaxation@1 (pinned open)",
        ),
        definition_sha256=spec.fingerprint,
        arm=arm_id,
        d_m2_s=d,
        g_gj_m3_s=conductance(d),
        start_units=start,
        species=dict(u="miR200", m="Zeb mRNA", z="ZEB protein"),
        concentration=(
            "amount / the cell's volume in the layout (4/3 pi (5 um)^3 = "
            f"{V_CELL_PL:.6g} pL); fmol / pL = mM, and one scaled unit of the switch is 1 uM"
        ),
        sidecars=[*SPECIES_SIDECARS_FILES, "criterion.json"],
        **_snapshot_identity(),
    )
    (directory / "run.json").write_text(json.dumps(entry, indent=1))
    return out


def final_units(directory, species_ids, n_cells=N_CELLS):
    """Each cell's u, m and z (units) from a written record's final checkpoint, read through the
    engine's loader (io.load_snapshot): a read, nothing continues from it."""
    import numpy as np

    from cells.records import io

    checkpoint = io.load_snapshot(Path(directory) / "checkpoint_final").checkpoint
    amount = np.asarray(checkpoint.layout.amount_reference) + np.asarray(
        checkpoint.state.amount_increment
    )
    volume = np.asarray(checkpoint.layout.volume)[:n_cells]
    return {
        name: (amount[species_ids.index(name), :n_cells] / volume / UNIT_mM).tolist()
        for name in NAMES
    }


CRITERION_FORMAT = "cells.experiment_criterion@1"
CRITERION_WORDS = (
    "A cell is epithelial (E) when its miR200 exceeds its Zeb mRNA by more than 2 scaled units "
    "(2 uM here, one unit being 1 uM), mesenchymal (M) when its Zeb mRNA exceeds its miR200 by "
    "more than 2, and neither (X) in between: BITSEY's state_char; the tissue is normalized when "
    "every cell is E (healthy_snapped_rows)."
)
CRITERION_SOURCE = (
    "BITSEY's log tumor_isolate_1D_V1M at b2cb370, written by an earlier revision of its code "
    "(cancer_GJ_sims/GRN_miRNA.py: state_char, lines 443-448; healthy_snapped_rows, line 519); "
    "docs/GAP_JUNCTION_CANCER_REPLICATION.md, section 7"
)


def cell_state(value):
    """BITSEY's state_char on miR200 minus Zeb mRNA (units): E above 2, M below -2, X between."""
    if value > MARGIN_UNITS:
        return "E"
    if value < -MARGIN_UNITS:
        return "M"
    return "X"


def criterion_sidecar(directory, species_ids, n_cells=N_CELLS, tumor_cells=None, arm_place=None):
    """criterion.json beside a tissue arm's package (a viewer sidecar written by the driver, not an
    engine field): each cell's miR200 minus Zeb mRNA (uM) per observed row, from the record's own
    observed amounts (its chunks) and volumes, and its state under BITSEY's criterion. The cells
    are the view's cell set (the layout's order, the arrays' columns); without a view, the
    layout's ids."""
    directory = Path(directory)
    times, cells, values = observed_units(directory, species_ids, n_cells)
    values = [
        [u - m for u, m in zip(row_u, row_m, strict=True)]
        for row_u, row_m in zip(values["u"], values["m"], strict=True)
    ]
    sidecar = dict(
        format=CRITERION_FORMAT,
        quantity=dict(id="mir200_minus_zeb_mrna", label="miR200 minus Zeb mRNA", unit="uM"),
        criterion=dict(
            threshold=MARGIN_UNITS,
            above="epithelial",
            lower=dict(threshold=-MARGIN_UNITS, below="mesenchymal"),
            between="neither (X)",
            words=CRITERION_WORDS,
            source=CRITERION_SOURCE,
        ),
        times_s=times,
        cells=list(cells),
        values=values,
        states=[[cell_state(x) for x in row] for row in values],
        # The tumor's cells, as seeded (the view's cell ids): stated, not inferred.
        tumor_cells=list(tumor_cells if tumor_cells is not None else TUMOR_CELLS_OF["line"]),
        species=SPECIES_MAP,
        place=arm_place,
    )
    (directory / "criterion.json").write_text(json.dumps(sidecar, allow_nan=False))
    return "criterion.json"


SPECIES_SIDECARS = {
    "u": ("concentration_mir200.json", "mir200", "miR200"),
    "m": ("concentration_zeb_mrna.json", "zeb_mrna", "Zeb mRNA"),
    "z": ("concentration_zeb_protein.json", "zeb_protein", "ZEB protein"),
}
SPECIES_SIDECARS_FILES = [filename for filename, _, _ in SPECIES_SIDECARS.values()]


def observed_units(directory, species_ids, n_cells=N_CELLS):
    """(times, cells, {species: rows of each cell's concentration in units}) from a written
    record's own observed amounts (its chunks) and the layout's volumes, read through the loader."""
    import numpy as np

    from cells.records import io

    directory = Path(directory)
    layout = io.load_snapshot(directory / "checkpoint_initial").checkpoint.layout  # A read.
    reference = np.asarray(layout.amount_reference)
    volume = np.asarray(layout.volume)[:n_cells]
    layout_ids = [str(i) for i in np.asarray(layout.ids)[:n_cells]]
    view = directory / "view.json"
    sets = {s["id"]: s for s in json.loads(view.read_text())["sets"]} if view.is_file() else {}
    cells = sets["cell"]["ids"] if "cell" in sets else layout_ids
    recorded = sets.get("species", {}).get("recorded")  # The kept species, when a subset.
    rows = {}
    for name in NAMES:
        full = species_ids.index(name)
        rows[name] = (full, full if recorded is None else recorded.index(full))
    times, values = [], {name: [] for name in NAMES}
    for line in (directory / "windows.jsonl").read_text().splitlines():
        entry = json.loads(line)
        if entry.get("kind") != "window" or not entry.get("path"):
            continue
        with np.load(directory / entry["path"]) as chunk:
            if "observation_times" not in chunk.files:
                continue
            when_rows = np.asarray(chunk["observation_times"], dtype=float)
            increment = chunk["observed_amount_increment"][:, :, :n_cells]
        for k, when in enumerate(when_rows):
            if times and when <= times[-1]:
                continue
            times.append(float(when))
            for name, (full, kept) in rows.items():
                amount = reference[full, :n_cells] + increment[k, kept]
                values[name].append((amount / volume / UNIT_mM).tolist())
    flat = [x for rows_ in values.values() for row in rows_ for x in row]
    if not all(math.isfinite(x) for x in [*flat, *times]):
        raise ValueError(f"{directory}: a value or time is not finite")
    return times, list(cells), values


def species_sidecars(directory, species_ids, n_cells=N_CELLS):
    """Each cell's miR200, Zeb mRNA and ZEB protein (uM) per observed row, beside a tissue arm's
    package (cells.experiment_quantity@1; viewer sidecars written by the driver)."""
    times, cells, values = observed_units(directory, species_ids, n_cells)
    written = []
    for name, (filename, quantity_id, label) in SPECIES_SIDECARS.items():
        sidecar = dict(
            format=QUANTITY_FORMAT,
            quantity=dict(
                id=quantity_id,
                label=f"{label} in each cell, in µM; the switch's scaled unit is 1 µM in this "
                "world (amount / volume from the record's own arrays)",
                unit="uM",
            ),
            times_s=times,
            cells=cells,
            values=values[name],
        )
        (Path(directory) / filename).write_text(json.dumps(sidecar, allow_nan=False))
        written.append(filename)
    return written


QUANTITY_FORMAT = "cells.experiment_quantity@1"


def records_summary(results):
    """The records' sweep for the viewer's chart (cells.experiment_summary@1): D along it, each
    cell's final miR200 minus Zeb mRNA as a readout. Numbers only, copied as computed."""
    arms = [
        dict(
            arm=r["arm"],
            parameter=r["d"],
            place=r.get("place") or threshold_place(r["d"], r.get("shape", "line")),
            readouts={
                f"cell_{k + 1:02d}": u - m
                for k, (u, m) in enumerate(
                    zip(r["final_units"]["u"], r["final_units"]["m"], strict=True)
                )
            },
        )
        for r in results
        if r.get("final_units")
    ]
    first = next((r for r in results if r.get("final_units")), {})
    shape = first.get("shape", "line")
    cell_ids = first.get("cells") or [f"c{k}" for k in range(N_CELLS)]
    tumor = set(first.get("tumor") or [f"c{k}" for k in range(TUMOR)])
    if shape == "line":
        sweep_id, sweep_label = "neither-1d", "The neither condition on BITSEY's 1D line"
        plain = (
            "Each cell's final miR200 minus Zeb mRNA in a line of 25 cells, the first 6 a tumor, "
            "against the junction diffusion constant D of miR200; above 2 a cell counts as "
            "epithelial (BITSEY's criterion)."
        )
    else:
        sweep_id = f"neither-sheet-{SHEET_N}x{SHEET_N}"
        sweep_label = (
            f"The neither condition on a {SHEET_N}x{SHEET_N} sheet (an extension beyond the "
            "replication)"
        )
        plain = (
            f"Each cell's final miR200 minus Zeb mRNA on a {SHEET_N}x{SHEET_N} sheet, a "
            f"{SHEET_TUMOR}x{SHEET_TUMOR} tumor in the middle, against the junction diffusion "
            "constant D of miR200; above 2 a cell counts as epithelial (BITSEY's criterion). Its "
            "D values sit around the 1D threshold; the sheet's own threshold may differ."
        )
    sweep = dict(
        id=sweep_id,
        label=sweep_label,
        plain=plain,
        parameter=dict(id="d", label="Junction diffusion constant D of miR200", unit="m^2/s"),
        readouts=[
            dict(
                id=f"cell_{k + 1:02d}",
                label=f"Cell {cell_id}{' (tumor)' if cell_id in tumor else ''}: miR200 minus Zeb "
                "mRNA, in µM; the switch's scaled unit is 1 µM in this world",
                unit="uM",
            )
            for k, cell_id in enumerate(cell_ids)
        ],
        arms=arms,
    )
    sweep["tumor_cells"] = sorted(tumor, key=cell_ids.index)
    sweep["species"] = SPECIES_MAP
    note = (
        "Development runs of the engine, not judged (D138). One scaled unit of the switch is 1 uM "
        "here. Species: u is miR200, m Zeb mRNA, z ZEB protein; each concentration is the amount "
        f"over the cell's volume in the layout ({V_CELL_PL:.6g} pL)."
    )
    if shape == "sheet":
        note = f"{SHEET_NOTE} {note}"
    return dict(
        format="cells.experiment_summary@1",
        experiment=EXPERIMENT_OF[shape],
        note=note,
        sweeps=[sweep] if len(arms) >= 2 else [],
    )


def rewrite_packaging(run_dir):
    """criterion.json (now stating the tumor's cells) and viewer/summary.json of a finished
    tissue run, rewritten from its records' own data by this driver; the runs are unchanged."""
    results = json.loads((run_dir / "records.json").read_text())
    written = {}
    for r in results:
        if r.get("status") != "done":
            continue
        shape = "sheet" if r["arm"].startswith(ARM_PREFIX["sheet"]) else "line"
        cells, *_ = tissue(shape)
        r.setdefault("shape", shape)
        r.setdefault("cells", [c for c, _ in cells])
        r.setdefault("tumor", TUMOR_CELLS_OF[shape])
        directory = run_dir / "viewer" / r["arm"]
        ids = json.loads((directory / "summary.json").read_text())["species_ids"]
        r.setdefault("place", threshold_place(r["d"], shape))
        written[r["arm"]] = criterion_sidecar(directory, ids, len(cells), r["tumor"], r["place"])
    summary = records_summary([r for r in results if r.get("status") == "done"])
    summary["note"] += (
        " criterion.json and this summary were rewritten after the run by neither.py --sidecars, "
        "from the records' own data."
    )
    (run_dir / "viewer" / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False))
    return written


def _snapshot_identity():
    path = Path("SNAPSHOT.json")
    if not path.is_file():
        return dict(revision=None, snapshot=None, clean=None)
    snapshot = json.loads(path.read_text())
    return dict(
        revision=snapshot["git_revision"],
        snapshot=Path.cwd().name,
        clean=not snapshot["selected_status_porcelain_v1_z"],
    )


def _record_work(args):
    d, start, end, out_dir, log_rows, shape = args
    _start_engine()
    try:
        return record(out_dir, d, start, end=end, log_rows=log_rows, shape=shape)
    except Exception as error:  # A refused pick is reported, never swapped (section 7).
        return dict(
            arm=f"{ARM_PREFIX[shape]}{d:.6g}",
            d=d,
            status="refused",
            error=repr(error),
            traceback=traceback.format_exc(),
        )


def record_all(out_dir, ds, end, cpus, log_rows=0, shape="line"):
    """Stage 1, then each D's record, one process per CPU of `cpus` (in this process when none);
    records.json and viewer/summary.json once every pick has ended."""
    from concurrent.futures import ProcessPoolExecutor

    out_dir.mkdir(parents=True, exist_ok=True)
    if cpus:
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        for cpu in cpus:
            queue.put(cpu)
        with ProcessPoolExecutor(
            len(cpus), mp_context=ctx, initializer=_pin, initargs=(queue,)
        ) as pool:
            stage1 = pool.submit(_uncoupled_work, shape).result()
            (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
            if stage1["status"] != "done":
                return 1
            futures = [
                pool.submit(
                    _record_work, (d, stage1["start_units"], end, str(out_dir), log_rows, shape)
                )
                for d in ds
            ]
            results = [future.result() for future in futures]
    else:
        _start_engine()
        stage1 = uncoupled(shape)
        (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
        if stage1["status"] != "done":
            return 1
        results = [
            _record_work((d, stage1["start_units"], end, str(out_dir), log_rows, shape)) for d in ds
        ]
    (out_dir / "records.json").write_text(json.dumps(results, indent=1))
    (out_dir / "viewer").mkdir(parents=True, exist_ok=True)
    summary = records_summary([r for r in results if r.get("status") == "done"])
    (out_dir / "viewer" / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False))
    for r in results:
        print(json.dumps({k: r.get(k) for k in ("arm", "status", "view", "seconds", "error")}))
    return 0 if all(r.get("status") == "done" for r in results) else 1


def _rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _start_engine():
    import jax

    jax.config.update("jax_enable_x64", True)
    import cells  # noqa: F401  (pins the BLAS at import, D190)


def _pin(queue):
    os.sched_setaffinity(0, {queue.get()})


def _uncoupled_work(shape):
    _start_engine()
    return uncoupled(shape or "line")


def _work(args):
    d, start, end, dt, shape = args
    _start_engine()
    return evaluate(d, start, end=end, dt=dt, shape=shape)


def first_points(workers, shape="line"):
    """The search's first points: the bracket's two ends, then dyadic points BRACKET[1] / 2^k, one
    per further worker. On the line, k = 1, 2, ... (neither-01 and -02). On the field, k starts at
    the smallest k whose point runs at the base step, so that no first point but the upper end
    runs at a reduced step (docs/GJ_NEITHER_REGISTRATION.md, the search)."""
    k0 = 1
    if shape == "field":
        neighbours = tissue(shape)[3]
        while step(BRACKET[1] / 2.0**k0, neighbours) < BASE_DT_S:
            k0 += 1
    ladder = [BRACKET[1] / 2.0**k for k in range(k0, k0 + max(0, workers - 2))]
    return [BRACKET[0], BRACKET[1], *ladder][: max(2, workers)]


def place(lo, hi, running, free):
    """New points for `free` workers: equally spaced inside (lo, hi) when no running point lies
    there, otherwise each the midpoint of the widest gap among lo, the running points and hi."""
    inside = sorted(x for x in running if lo < x < hi)
    if not inside:
        return [lo + (hi - lo) * j / (free + 1) for j in range(1, free + 1)]
    edges, new = [lo, *inside, hi], []
    for _ in range(free):
        a, b = max(zip(edges[:-1], edges[1:], strict=True), key=lambda gap: gap[1] - gap[0])
        new.append(0.5 * (a + b))
        edges = sorted([*edges, new[-1]])
    return new


def bracket(evaluated):
    """lo, hi (the largest persisting D below the smallest normalizing one), monotone, failed."""
    done = sorted((d, r["normalized"]) for d, r in evaluated.items() if r["status"] == "done")
    failed = sorted(d for d, r in evaluated.items() if r["status"] != "done")
    outcomes = [ok for _, ok in done]
    normalizing = [d for d, ok in done if ok]
    hi = min(normalizing) if normalizing else None
    lo = max((d for d, ok in done if not ok and (hi is None or d < hi)), default=None)
    return lo, hi, outcomes == sorted(outcomes), failed


def search(out_dir, cpus, end, shape="line"):
    """BITSEY's bisection, run in parallel: a worker that finishes takes a new point inside the
    current bracket at once (place), so the slow points near the bracket's upper end never hold
    the narrowing back. Stops submitting when converged (hi <= (1 + RTOL) lo) or when a stop
    condition holds; waits for the points still running (the upper end's result is required);
    then reruns the final bracket's two ends at half their step (the convergence condition of
    docs/GJ_NEITHER_REGISTRATION.md; development runs reported it only)."""
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    for cpu in cpus:
        queue.put(cpu)
    workers = len(cpus)
    neighbours = tissue(shape)[3]
    first = first_points(workers, shape)
    state = dict(
        shape=shape,
        first_points=first,
        bracket=BRACKET,
        rtol=RTOL,
        started_utc=_utc(),
        events=[],
    )

    def save():
        (out_dir / "search.json").write_text(json.dumps(state, indent=1))

    with ProcessPoolExecutor(workers, mp_context=ctx, initializer=_pin, initargs=(queue,)) as pool:
        stage1 = pool.submit(_uncoupled_work, shape).result()
        (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
        if stage1["status"] != "done":
            state.update(stopped="the uncoupled stage failed")
            save()
            return state
        start = stage1["start_units"]
        evaluated, running = {}, {}

        def submit(d):
            running[pool.submit(_work, (d, start, end, None, shape))] = d
            state["events"].append(dict(utc=_utc(), submitted=d))

        for d in first:
            submit(d)
        save()
        submitting, halves = True, None

        def submit_halves(lo, hi):
            """The final bracket's ends at half their step, once no search point runs inside it."""
            state["half_step_bracket"] = [lo, hi]
            state["events"].append(dict(utc=_utc(), half_step_submitted=[lo, hi]))
            return {
                d: pool.submit(_work, (d, start, end, step(d, neighbours) / 2.0, shape))
                for d in (lo, hi)
            }

        while running:
            finished, _ = wait(running, return_when=FIRST_COMPLETED)
            with (out_dir / "points.jsonl").open("a") as stream:
                for future in finished:
                    d = running.pop(future)
                    result = future.result()
                    evaluated[d] = result
                    stream.write(json.dumps(result) + "\n")
                    state["events"].append(
                        dict(
                            utc=_utc(),
                            finished=d,
                            normalized=result.get("normalized"),
                            status=result["status"],
                        )
                    )
            lo, hi, monotone, failed = bracket(evaluated)
            state.update(lo=lo, hi=hi, monotone=monotone, failed=failed, evaluated=len(evaluated))
            upper = evaluated.get(BRACKET[1])
            lower = evaluated.get(BRACKET[0])
            if failed:
                state["stopped"] = "a point failed"
            elif not monotone:
                state["stopped"] = "the outcomes are not monotone in D"
            elif upper is not None and not upper["normalized"]:
                state["stopped"] = "the bracket's upper end does not normalize"
            elif lower is not None and lower["normalized"]:
                state["stopped"] = "the bracket's lower end normalizes"
            converged = lo is not None and hi is not None and hi <= (1.0 + RTOL) * lo
            if converged or "stopped" in state:
                submitting = False
            if submitting and lo is not None and hi is not None:
                free = workers - len(running)
                for d in place(lo, hi, list(running.values()), free):
                    submit(d)
            inside = any(lo < x < hi for x in running.values()) if converged else True
            if converged and halves is None and "stopped" not in state and not inside:
                halves = submit_halves(lo, hi)  # The slow points above the bracket still run.
            save()
        lo, hi, monotone, failed = bracket(evaluated)
        converged = lo is not None and hi is not None and hi <= (1.0 + RTOL) * lo
        if converged and "stopped" not in state:
            # The threshold alone: its comparisons are GJ-N1's judge's (neither_judge.py).
            state.update(threshold=hi)
            save()
            if halves is None:
                halves = submit_halves(lo, hi)
        if halves is not None:
            check = {}
            for d, future in halves.items():
                result = future.result()
                with (out_dir / "half_step.jsonl").open("a") as stream:
                    stream.write(json.dumps(result) + "\n")
                check[str(d)] = dict(
                    dt_s=result.get("dt_s"),
                    status=result["status"],
                    normalized=result.get("normalized"),
                    min_margin_units=result.get("min_margin_units"),
                    same_as_step=result.get("normalized") == evaluated[d]["normalized"],
                )
            state["half_step_check"] = check
    state["finished_utc"] = _utc()
    save()
    return state


def _utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--cpus", default="")
    parser.add_argument("--points", default="")
    parser.add_argument("--end", type=float, default=COUPLED_S)
    parser.add_argument("--record", default="")
    parser.add_argument("--record-log", type=int, default=0)
    parser.add_argument("--shape", default="line", choices=SHAPES)
    parser.add_argument("--sidecars", default="")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot = Path("SNAPSHOT.json")
    plan = dict(
        module=__doc__,
        shape=args.shape,
        n_cells=N_CELLS,
        tumor=TUMOR,
        field=dict(n=FIELD_N, tumor=FIELD_TUMOR, row_spread_units=ROW_SPREAD_UNITS),
        seeds_units=SEEDS,
        trace_units=TRACE_UNITS,
        uncoupled_s=UNCOUPLED_S,
        coupled_s=args.end,
        bracket=BRACKET,
        rtol=RTOL,
        margin_units=MARGIN_UNITS,
        step_bound_margin=STEP_BOUND_MARGIN,
        window_steps=WINDOW_STEPS,
        constants=dict(
            u_synthesis=U_SYNTHESIS,
            m_synthesis=M_SYNTHESIS,
            u_hill=U_HILL,
            m_hill=M_HILL,
            x0=X0_UNITS,
            z_translation=Z_TRANSLATION,
            l=L_SITES,
            decay=DECAY,
            unit_mM=UNIT_mM,
        ),
        snapshot=json.loads(snapshot.read_text()).get("git_revision")
        if snapshot.is_file()
        else None,
        points=args.points or None,
        cpus=args.cpus or None,
    )
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=1))
    if args.sidecars:  # Packaging for a finished run's tissue arms; no run is changed.
        print(json.dumps(rewrite_packaging(Path(args.sidecars)), indent=1))
        return 0
    if args.record:  # Records for the viewer: stage 1, then each D written with its view.
        cpus = [int(c) for c in args.cpus.split(",") if c]
        ds = [float(x) for x in args.record.split(",")]
        return record_all(out_dir, ds, args.end, cpus, log_rows=args.record_log, shape=args.shape)
    if args.points:  # A probe: stage 1, then the given points in this process; no search.
        _start_engine()
        stage1 = uncoupled(args.shape)
        (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
        keys = ("status", "dt_s", "steps", "seconds", "start_units", "error")
        print(json.dumps({k: stage1.get(k) for k in keys}), flush=True)
        if stage1["status"] != "done":
            return 1
        for d in (float(x) for x in args.points.split(",")):
            result = evaluate(d, stage1["start_units"], end=args.end, shape=args.shape)
            with (out_dir / "probe.jsonl").open("a") as stream:
                stream.write(json.dumps(result) + "\n")
            keys = (
                "d",
                "status",
                "dt_s",
                "steps",
                "normalized",
                "epithelial_cells",
                "min_margin_units",
                "max_row_spread_units",
                "seconds",
                "max_rss_kib",
                "error",
            )
            print(json.dumps({k: result.get(k) for k in keys}), flush=True)
        return 0
    cpus = [int(c) for c in args.cpus.split(",") if c]
    state = search(out_dir, cpus, args.end, args.shape)
    keys = ("lo", "hi", "threshold", "stopped")
    print(json.dumps({k: state.get(k) for k in keys}), flush=True)
    return 0 if "threshold" in state else 1


if __name__ == "__main__":
    raise SystemExit(main())
