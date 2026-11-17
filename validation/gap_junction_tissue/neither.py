"""The "neither" comparison (decision (b)): development work, not a judged comparison (D138).

A comparison with BITSEY's log at b2cb370 (D208), not with the preprint. Its two conditions are
written in docs/GAP_JUNCTION_CANCER_REPLICATION.md section 7 before the search:
1. In BITSEY's "no tricks" run every junction's dV is 0, so the miRNA's valence -1 drift vanishes
   and its junction transport is Fick's: a neutral miRNA is the same model there.
2. The world, criterion, bracket and tolerance are BITSEY's (cancer_GJ_sims/zombie.py at b2cb370):
   a line of 25 cells with a 6-cell tumor at one end; seeds miR200/Zeb mRNA/ZEB 0/100/100
   (tumor) and 100/0/0 (healthy, scaled coordinates); 500 time units uncoupled, then 20,000
   coupled; normalized when every cell ends with miR200 > Zeb mRNA + 2; the junction diffusion
   constant D searched in [0, 1e-13] m^2/s until x2 <= 1.001 x0, reporting x2; G_GJ = D x 4 pi
   (5 um)^2 / 100 nm. Agreement is called if Cells' x2 / 7.18e-15 lies in [0.95, 1.05].

The protocol has BITSEY's two stages (find_min_Kd_tumorFix): the uncoupled 500 s are run once,
from the seeds, in a world of one tumor cell and one healthy cell with no junctions (every tumor
cell, and every healthy cell, is the same while uncoupled); their end state seeds every coupled
run, as cc_discon does. The switch is autonomous, so each coupled run starts its clock at 0.

The model, on today's engine (nothing here adds physics):
* resolved_pump_composite@1 over resolved_pump_tissue@3, the species-only world of the
  secreted-species fixtures (ions at the bath's composition, zero permeability, so nothing but the
  switch's species moves);
* the EMT switch as local_species_reactions@1 reactions per cell (worlds.emt_switch_probe's
  structure) with GRN_miRNA.py's constants at b2cb370 as docs/EMT_REFERENCE.md states them, Snail
  72 folded into the rates, one scaled unit = 1 uM, BITSEY's time unit taken as 1 s;
* in the coupled stage, miR200 (u) alone on a cells.passive_routes@1 route
  (passive_neutral_permeation@1) on each junction, P A = G_GJ, junction gates pinned open; no
  routes at D = 0.
Seeds BITSEY sets to 0 start at the fixtures' trace, 1e-9 mM (1e-6 units): @3 needs positive
amounts.

The search runs one point per CPU of --cpus at a time, each in its own process pinned to one CPU:
first the bracket's ends and its bisection points 1e-13 / 2^k (k = 1..); then, whenever a point
finishes, its worker takes a new point inside the current bracket (search, place). Outcomes are
assumed monotone in D; a non-monotone set is reported, not repaired. After convergence, the final
bracket's two ends are rerun at half their step: reported, not used to move the threshold. Each
run is windowed (cells.core.windows, recording observations, device row checks; every engine
check still runs). Every point's result is appended to OUTDIR/points.jsonl (the half-step reruns
to OUTDIR/half_step.jsonl) and the search state written to OUTDIR/search.json as points finish.

Records for the viewer (--record): stage 1, then the coupled stage at each given D written by the
engine's windowed writer (cells.window_io.write_windowed_run, observed rows every RECORD_EVERY_S)
under OUTDIR/viewer/neither-d<D>/ with its run view (cells.run_view@1: the line of cells as touching
spheres) and run.json; a refused view is recorded and the run written without one.

Usage (from a snapshot root, PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu):
    python -B validation/gap_junction_tissue/neither.py OUTDIR --cpus 0,1,2,3,16,17,18,19
    python -B validation/gap_junction_tissue/neither.py OUTDIR --points 1e-14 --end 600  (a probe)
    python -B validation/gap_junction_tissue/neither.py OUTDIR --record 6e-15,7.2e-15,9e-15
"""

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
BITSEY_LOGGED = 7.18e-15  # results_miRNA/tumor_isolate_1D_V1M at b2cb370: the 1D no-tricks value.
AGREEMENT = (0.95, 1.05)
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


def junction_rate(d):
    """@3's explicit rate for the coupled world (1/s): 2 x the largest sum of G_GJ / V over a
    cell's junction routes (an interior cell has two)."""
    return 2.0 * 2.0 * conductance(d) / (V_CELL_PL * 1e-15)


def step(d):
    dt = BASE_DT_S
    while dt * junction_rate(d) > STEP_BOUND_MARGIN:
        dt /= 2.0
    return dt


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
                law="passive_neutral_permeation@1",
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


def uncoupled_world(*, end=UNCOUPLED_S, dt=None):
    """Stage 1: one tumor cell and one healthy cell, no junctions, from BITSEY's seeds. Its dt is
    the finest coupled step (the bracket's upper end), so stage 1 is never the coarser stage."""
    dt = step(BRACKET[1]) if dt is None else dt
    observe = sorted(
        {0.0, *(k * 100.0 for k in range(int(end // 100.0) + 1) if k * 100.0 < end), end}
    )
    cells = (("tumor", "tumor"), ("healthy", "healthy"))
    return switch_world(cells, SEEDS, end=end, dt=dt, observe=observe)


def coupled_world(d, start, *, end=COUPLED_S, dt=None):
    """Stage 2: the line of 25 cells, the first TUMOR of them tumor, from stage 1's end state."""
    dt = step(d) if dt is None else dt
    cells = tuple((f"c{k}", "tumor" if k < TUMOR else "healthy") for k in range(N_CELLS))
    junctions = tuple((f"j{k}", f"c{k}", f"c{k + 1}") for k in range(N_CELLS - 1))
    observe = sorted(
        {0.0, *(k * OBSERVE_EVERY_S for k in range(int(end // OBSERVE_EVERY_S) + 1)), end}
    )
    observe = [t for t in observe if t <= end]
    return switch_world(cells, start, junctions=junctions, d=d, end=end, dt=dt, observe=observe)


def execute(raw, n_cells):
    """Run a world windowed with device row checks; the end state in units per cell, the observed
    rows of u and m, the steps, diagnostics and timings."""
    import numpy as np

    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, iter_windows

    spec = parse_spec(raw)
    ids = list(spec.model.species_ids)
    rows = {name: ids.index(name) for name in NAMES}
    last, diagnostics, observed = None, {}, dict(times=[], u=[], m=[])
    policy = WindowPolicy(WINDOW_STEPS, "observations", "device")
    for window in iter_windows(spec, policy):
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
    )


def uncoupled():
    """Stage 1, once: the tumor and healthy cells' state after UNCOUPLED_S."""
    started = time.perf_counter()
    out = dict(stage="uncoupled", end_s=UNCOUPLED_S, seeds_units=SEEDS)
    try:
        run = execute(uncoupled_world(), 2)
        start = {
            kind: {name: run["final_units"][name][k] for name in NAMES}
            for k, kind in enumerate(("tumor", "healthy"))
        }
        out.update(status="done", start_units=start, **run)
    except Exception as error:  # Recorded as evidence, never retried.
        out.update(status="failed", error=repr(error), traceback=traceback.format_exc())
    out.update(seconds=time.perf_counter() - started, max_rss_kib=_rss())
    return out


def evaluate(d, start, *, end=COUPLED_S, dt=None):
    """One point: the coupled stage at diffusion constant d (at step dt, default step(d)); the
    criterion at its end."""
    started = time.perf_counter()
    out = dict(
        d=d,
        end_s=end,
        g_gj_m3_s=conductance(d),
        pid=os.getpid(),
        cpus=sorted(os.sched_getaffinity(0)),
    )
    try:
        run = execute(coupled_world(d, start, end=end, dt=dt), N_CELLS)
        u, m = run["final_units"]["u"], run["final_units"]["m"]
        margins = [a - b - MARGIN_UNITS for a, b in zip(u, m, strict=True)]
        out.update(
            status="done",
            normalized=all(x > 0.0 for x in margins),
            epithelial_cells=sum(x > 0.0 for x in margins),
            min_margin_units=min(margins),
            **run,
        )
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


def record(out_dir, d, start, *, end=COUPLED_S, label="", log_rows=0):
    """The coupled stage at d written as a run record with its run view (module docstring)."""
    from cells import run_view
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy
    from cells.window_io import write_windowed_run

    arm_id = f"neither-d{d:.6g}"
    directory = Path(out_dir) / "viewer" / arm_id
    raw = coupled_world(d, start, end=end)
    raw["experiment"]["observation_times"] = record_times(step(d), end, log_rows)
    spec = parse_spec(raw)
    spacing = 2.0 * R_CELL_M * 1e6
    geometry = run_view.Geometry(
        unit="um",
        dimensions=2,
        sets={
            "cell": {
                "kind": "spheres",
                "centres": [[k * spacing, 0.0] for k in range(N_CELLS)],
                "radius": [R_CELL_M * 1e6] * N_CELLS,
            }
        },
        source="validation/gap_junction_tissue/neither.py: a line of 25 touching cells, the "
        "tumor the first 6 (BITSEY's 1x1x25 field)",
    )
    labels = dict(
        id=arm_id,
        experiment=EXPERIMENT,
        arm=arm_id,
        label=f"Neither condition, 1D: D = {d:.4g} m^2/s",
    )
    provenance = dict(
        operation="fresh",
        driver="validation/gap_junction_tissue/neither.py",
        experiment=EXPERIMENT,
        arm=arm_id,
        d_m2_s=d,
        **_snapshot_identity(),
    )
    policy = WindowPolicy(WINDOW_STEPS, "observations", "device")
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
    out = dict(arm=arm_id, d=d, directory=str(directory), dt_s=spec.execution.dt, status="done")
    try:
        write_windowed_run(directory, spec, policy, provenance=provenance, view=request)
        out["view"] = "written"
    except run_view.ViewRefused as error:
        write_windowed_run(directory, spec, policy, provenance=provenance)
        out.update(view="refused", refusal=str(error))
    out["seconds"] = time.perf_counter() - started
    out["final_units"] = final_units(directory, list(spec.model.species_ids))
    out["sidecar"] = criterion_sidecar(directory, list(spec.model.species_ids))
    out["species_sidecars"] = species_sidecars(directory, list(spec.model.species_ids))
    entry = dict(
        format="gap_junction_tissue.neither_run@1",
        status="development run of the engine, not judged (D138)",
        represents=REPRESENTS,
        models=["resolved_pump_composite@1", "resolved_pump_tissue@3"],
        laws=dict(
            switch="local_species_reactions@1 (GRN_miRNA.py's constants at b2cb370)",
            junction_route="passive_neutral_permeation@1 (cells.passive_routes@1), miR200 only",
            junction_gate="junction_voltage_relaxation@1 (pinned open)",
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


def final_units(directory, species_ids):
    """Each cell's u, m and z (units) from a written record's final checkpoint, read through the
    engine's loader (io.load_snapshot): a read, nothing continues from it."""
    import numpy as np

    from cells import io

    checkpoint = io.load_snapshot(Path(directory) / "checkpoint_final").checkpoint
    amount = np.asarray(checkpoint.layout.amount_reference) + np.asarray(
        checkpoint.state.amount_increment
    )
    volume = np.asarray(checkpoint.layout.volume)[:N_CELLS]
    return {
        name: (amount[species_ids.index(name), :N_CELLS] / volume / UNIT_mM).tolist()
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


def criterion_sidecar(directory, species_ids):
    """criterion.json beside a tissue arm's package (a viewer sidecar written by the driver, not an
    engine field): each cell's miR200 minus Zeb mRNA (uM) per observed row, from the record's own
    observed amounts (its chunks) and volumes, and its state under BITSEY's criterion. The cells
    are the view's cell set (the layout's order, the arrays' columns); without a view, the
    layout's ids."""
    directory = Path(directory)
    times, cells, values = observed_units(directory, species_ids)
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
    )
    (directory / "criterion.json").write_text(json.dumps(sidecar, allow_nan=False))
    return "criterion.json"


SPECIES_SIDECARS = {
    "u": ("concentration_mir200.json", "mir200", "miR200"),
    "m": ("concentration_zeb_mrna.json", "zeb_mrna", "Zeb mRNA"),
    "z": ("concentration_zeb_protein.json", "zeb_protein", "ZEB protein"),
}
SPECIES_SIDECARS_FILES = [filename for filename, _, _ in SPECIES_SIDECARS.values()]


def observed_units(directory, species_ids):
    """(times, cells, {species: rows of each cell's concentration in units}) from a written
    record's own observed amounts (its chunks) and the layout's volumes, read through the loader."""
    import numpy as np

    from cells import io

    directory = Path(directory)
    layout = io.load_snapshot(directory / "checkpoint_initial").checkpoint.layout  # A read.
    reference = np.asarray(layout.amount_reference)
    volume = np.asarray(layout.volume)[:N_CELLS]
    layout_ids = [str(i) for i in np.asarray(layout.ids)[:N_CELLS]]
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
            increment = chunk["observed_amount_increment"][:, :, :N_CELLS]
        for k, when in enumerate(when_rows):
            if times and when <= times[-1]:
                continue
            times.append(float(when))
            for name, (full, kept) in rows.items():
                amount = reference[full, :N_CELLS] + increment[k, kept]
                values[name].append((amount / volume / UNIT_mM).tolist())
    flat = [x for rows_ in values.values() for row in rows_ for x in row]
    if not all(math.isfinite(x) for x in [*flat, *times]):
        raise ValueError(f"{directory}: a value or time is not finite")
    return times, list(cells), values


def species_sidecars(directory, species_ids):
    """Each cell's miR200, Zeb mRNA and ZEB protein (uM) per observed row, beside a tissue arm's
    package (cells.experiment_quantity@1; viewer sidecars written by the driver)."""
    times, cells, values = observed_units(directory, species_ids)
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
    sweep = dict(
        id="neither-1d",
        label="The neither condition on BITSEY's 1D line",
        plain="Each cell's final miR200 minus Zeb mRNA in a line of 25 cells, the first 6 a "
        "tumor, against the junction diffusion constant D of miR200; above 2 a cell counts as "
        "epithelial (BITSEY's criterion).",
        parameter=dict(id="d", label="Junction diffusion constant D of miR200", unit="m^2/s"),
        readouts=[
            dict(
                id=f"cell_{k + 1:02d}",
                label=f"Cell {k + 1}{' (tumor)' if k < TUMOR else ''}: miR200 minus Zeb mRNA, in "
                "µM; the switch's scaled unit is 1 µM in this world",
                unit="uM",
            )
            for k in range(N_CELLS)
        ],
        arms=arms,
    )
    return dict(
        format="cells.experiment_summary@1",
        experiment=EXPERIMENT,
        note="Development runs of the engine, not judged (D138). One scaled unit of the switch is "
        "1 uM here. Species: u is miR200, m Zeb mRNA, z ZEB protein; each concentration is the "
        f"amount over the cell's volume in the layout ({V_CELL_PL:.6g} pL).",
        sweeps=[sweep] if len(arms) >= 2 else [],
    )


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
    d, start, end, out_dir, log_rows = args
    _start_engine()
    try:
        return record(out_dir, d, start, end=end, log_rows=log_rows)
    except Exception as error:  # A refused pick is reported, never swapped (section 7).
        return dict(
            arm=f"neither-d{d:.6g}",
            d=d,
            status="refused",
            error=repr(error),
            traceback=traceback.format_exc(),
        )


def record_all(out_dir, ds, end, cpus, log_rows=0):
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
            stage1 = pool.submit(_uncoupled_work, None).result()
            (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
            if stage1["status"] != "done":
                return 1
            futures = [
                pool.submit(_record_work, (d, stage1["start_units"], end, str(out_dir), log_rows))
                for d in ds
            ]
            results = [future.result() for future in futures]
    else:
        _start_engine()
        stage1 = uncoupled()
        (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
        if stage1["status"] != "done":
            return 1
        results = [
            _record_work((d, stage1["start_units"], end, str(out_dir), log_rows)) for d in ds
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


def _uncoupled_work(_):
    _start_engine()
    return uncoupled()


def _work(args):
    d, start, end, dt = args
    _start_engine()
    return evaluate(d, start, end=end, dt=dt)


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


def search(out_dir, cpus, end):
    """BITSEY's bisection, run in parallel: a worker that finishes takes a new point inside the
    current bracket at once (place), so the slow points near the bracket's upper end never hold
    the narrowing back. Stops submitting when converged (hi <= (1 + RTOL) lo) or when a stop
    condition holds; waits for the points still running (the upper end's result is required);
    then reruns the final bracket's two ends at half their step (reported, not used)."""
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    out_dir.mkdir(parents=True, exist_ok=True)
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    for cpu in cpus:
        queue.put(cpu)
    workers = len(cpus)
    first = [BRACKET[0], BRACKET[1], *(BRACKET[1] / 2.0**k for k in range(1, workers - 1))]
    state = dict(
        bracket=BRACKET,
        rtol=RTOL,
        bitsey_logged=BITSEY_LOGGED,
        agreement=AGREEMENT,
        started_utc=_utc(),
        events=[],
    )

    def save():
        (out_dir / "search.json").write_text(json.dumps(state, indent=1))

    with ProcessPoolExecutor(workers, mp_context=ctx, initializer=_pin, initargs=(queue,)) as pool:
        stage1 = pool.submit(_uncoupled_work, None).result()
        (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
        if stage1["status"] != "done":
            state.update(stopped="the uncoupled stage failed")
            save()
            return state
        start = stage1["start_units"]
        evaluated, running = {}, {}

        def submit(d):
            running[pool.submit(_work, (d, start, end, None))] = d
            state["events"].append(dict(utc=_utc(), submitted=d))

        for d in first[: max(2, workers)]:
            submit(d)
        save()
        submitting, halves = True, None

        def submit_halves(lo, hi):
            """The final bracket's ends at half their step, once no search point runs inside it."""
            state["half_step_bracket"] = [lo, hi]
            state["events"].append(dict(utc=_utc(), half_step_submitted=[lo, hi]))
            return {d: pool.submit(_work, (d, start, end, step(d) / 2.0)) for d in (lo, hi)}

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
            ratio = hi / BITSEY_LOGGED
            state.update(
                threshold=hi,
                ratio_to_bitsey_log=ratio,
                agreement_called=AGREEMENT[0] <= ratio <= AGREEMENT[1],
            )
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
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshot = Path("SNAPSHOT.json")
    plan = dict(
        module=__doc__,
        n_cells=N_CELLS,
        tumor=TUMOR,
        seeds_units=SEEDS,
        trace_units=TRACE_UNITS,
        uncoupled_s=UNCOUPLED_S,
        coupled_s=args.end,
        bracket=BRACKET,
        rtol=RTOL,
        margin_units=MARGIN_UNITS,
        bitsey_logged=BITSEY_LOGGED,
        agreement=AGREEMENT,
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
    if args.record:  # Records for the viewer: stage 1, then each D written with its view.
        cpus = [int(c) for c in args.cpus.split(",") if c]
        ds = [float(x) for x in args.record.split(",")]
        return record_all(out_dir, ds, args.end, cpus, log_rows=args.record_log)
    if args.points:  # A probe: stage 1, then the given points in this process; no search.
        _start_engine()
        stage1 = uncoupled()
        (out_dir / "uncoupled.json").write_text(json.dumps(stage1, indent=1))
        keys = ("status", "dt_s", "steps", "seconds", "start_units", "error")
        print(json.dumps({k: stage1.get(k) for k in keys}), flush=True)
        if stage1["status"] != "done":
            return 1
        for d in (float(x) for x in args.points.split(",")):
            result = evaluate(d, stage1["start_units"], end=args.end)
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
                "seconds",
                "max_rss_kib",
                "error",
            )
            print(json.dumps({k: result.get(k) for k in keys}), flush=True)
        return 0
    cpus = [int(c) for c in args.cpus.split(",") if c]
    state = search(out_dir, cpus, args.end)
    keys = ("lo", "hi", "threshold", "ratio_to_bitsey_log", "agreement_called", "stopped")
    print(json.dumps({k: state.get(k) for k in keys}), flush=True)
    return 0 if "threshold" in state else 1


if __name__ == "__main__":
    raise SystemExit(main())
