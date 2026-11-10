"""Heredity pilot W1: write and hold a disc in the full engine (development, not judged).

Question (E07-v1, docs/HEREDITY_FIRST_EXPERIMENT.md; D133): does the write cue,
Na leak x10 on a 19- or 37-cell disc, write a D disc in the full 825-node
heredity tissue; do the simplified-sheet retention predictions of pre-screens 7
and 8 (/mnt/workspaces/Cells/heredity-design-20261108-01) transfer; and what
does a batched run with observers cost? It is also the first E07 experiment
driver.

Engine models run: resolved_pump_tissue@3 (IMEX ARS(2,2,2) with exponential
stage gates, dt 1 ms, float64) through core/vector_windows.py, the
world_batching="vmap" mapping with the model's device row checks (the
ionic_worlds@1 task replicates one definition, so heterogeneous worlds use the
same runner directly), and through core/runner.py for the single-cell check;
stationary_continuation_analysis@1 (cells.analysis.stationary) for the start
state. Nothing here adds physics.

World: validation/tissue/surface_pump_v3_study.tissue_definition, the 825-node
heredity tissue (resolved_scale_world seed 0: 225 cells on a jittered hexagonal
lattice, 600 extracellular squares with a held outer ring, 1290 patches, 618
junctions, 1151 faces; NaV1.2 and Kir2.1 on every patch, Na leak x0.2).

Mapping onto E07-v1 (written to mapping.json by the map part):

* Discs: graph rings around cell 0 (the lattice origin) on the junction graph;
  rings 0-2 are the 19-cell disc, rings 0-3 the 37-cell disc (ring counts 1, 6,
  12, 18; all of these cells are interior, six junctions and six patches).
* Coupling: the junction area and permeabilities are those of E07-v1
  (validation/stationary/worlds.e07_junction reads them from the same world).
  The pre-screens define theta = s G_open(c_H) / g_H with the cell area of the
  BETSE default world (3.2613e-10 m^2). An interior cell here has 6 patches of
  5.3405e-11 m^2 (3.2043e-10 m^2), so g_H is 1.75% smaller; every junction
  permeability is multiplied by s * 3.2043e-10 / 3.2613e-10 so that theta is
  the pre-screens' at the same s for interior cells.
* Heterogeneity: validation/stationary/worlds.e07_heterogeneity (numpy
  default_rng(seed); per cell mean-one lognormal factors, CV 10%, drawn for
  NaV1.2, Kir2.1, Na leak and pump in that order, then one factor per junction,
  CV 20%). A cell's factors multiply every one of its patches' NaV1.2 and
  Kir2.1 permeabilities, Na leak permeability and pump capacity; a junction's
  factor multiplies all its permeabilities.
* Cue: one naleak_always_open@1 population on every patch of the 37 disc
  cells with 9x the patch's own Na leak permeability (so the patch's Na leak
  is x10 while it is available), availability 0 except on [cue on, cue off)
  for the arm's disc cells (experiment.channel_controls, which @3 turns into
  experiment.changes and controls). The 19-cell arms keep ring 3's populations
  at 0, so all worlds share shapes. membrane_controls cannot express the cue:
  a membrane availability scales the Na, K and M leaks together.

Parts (each writes into --output):
  map       disc and coupling mapping; per-cell single-cell state count
  cue       single heredity cell (held bath, run()): Na leak x10 for 0.02-2 s
  sheet     pre-screen 7's hexagonal held-bath sheet (127 cells) with the cue:
            19 and 37 discs, s 0.3 and 1.0, cue 0.5 and 2 s, 60 s after (vmap)
  start     per (seed, s): coupled uniform-H stationary state of the tissue's
            cell graph with held baths (stationary analysis, dense Newton)
  prepare   per (seed, s): the full tissue from that state, fine relaxation
            (vmap), stationarity from the law's derivative; batch snapshot
  run       16 worlds from the preparations: baseline, cue, retention (vmap)
  summarize per-world outcomes against predictions.json; cost
"""

import argparse
import json
import math
import resource
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.specs import parse_spec  # noqa: E402
from cells.core.surface_pump_v3_spec import NALEAK_LAW_ID  # noqa: E402
from cells.processes.electrochemistry import CHARGE_PER_FMOL  # noqa: E402
from validation.stationary import worlds  # noqa: E402
from validation.tissue import resolved_scale_world as scale_world  # noqa: E402
from validation.tissue import surface_pump_v3_fixtures as fixtures  # noqa: E402
from validation.tissue import surface_pump_v3_study as heredity  # noqa: E402

DT = 1e-3
SEEDS = (1, 2, 3, 4)
SCALES = (0.3, 1.0)
DISCS = {19: 2, 37: 3}  # disc cells -> largest ring
CELL_CV, JUNCTION_CV = 0.10, 0.20
CUE_FACTOR = 10.0
THRESHOLD_V = fixtures.HEREDITY_STATES["U"][0]  # pre-screens: D if Vm above the U state
H_STATE = fixtures.HEREDITY_STATES["H"]
MOBILE = ("Na", "K", "M")
ION_IDS = ("Na", "K", "M", "P")
ENV_mM = dict(zip((s for s, _ in scale_world.SPECIES), scale_world.ENV_mM, strict=True))
VALENCE = dict(scale_world.SPECIES)
# Run phases in steps of DT (all events on whole milliseconds, so no grid refinement).
BASELINE_STEPS = 30_000
RETENTION_STEPS = 180_000
WINDOW_STEPS = 200


def log(line):
    print(f"[{time.strftime('%H:%M:%S')}] {line}", flush=True)


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=_default) + "\n")
    tmp.replace(path)


def _default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def resources():
    out = dict(host_peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
    try:
        stats = jax.devices()[0].memory_stats() or {}
        out.update({k: stats.get(k) for k in ("peak_bytes_in_use", "bytes_in_use", "bytes_limit")})
    except Exception:  # CPU devices may not report.
        pass
    return out


# ------------------------------------------------------------------ geometry


class Tissue:
    """The full tissue's cells, patches, junctions and the disc rings."""

    def __init__(self):
        g = scale_world.geometry(0)
        self.g = g
        self.cells = int(g["cells"])
        self.pairs = [(int(a), int(b)) for a, b in g["pairs"]]
        self.owner = np.asarray(g["owner"], dtype=np.int64)
        self.square = np.asarray(g["square"], dtype=np.int64)
        self.patch_area = float(g["patch_area"])
        self.patches = np.bincount(self.owner, minlength=self.cells)
        self.area = self.patches * self.patch_area
        self.volume_pL = float(g["cell_volume_pL"])
        neighbours = [[] for _ in range(self.cells)]
        for a, b in self.pairs:
            neighbours[a].append(b)
            neighbours[b].append(a)
        self.degree = np.array([len(n) for n in neighbours])
        ring = np.full(self.cells, -1)
        ring[0], queue = 0, [0]
        for i in queue:
            for j in neighbours[i]:
                if ring[j] < 0:
                    ring[j] = ring[i] + 1
                    queue.append(j)
        self.ring = ring
        counts = np.bincount(ring)
        if list(counts[:4]) != [1, 6, 12, 18] or np.any(self.degree[ring <= 3] != 6):
            raise ValueError("Disc rings are not hexagonal around cell 0")
        # Patch-to-cell averaging (equal patch areas): cell Vm = mean of its patches.
        self.average = np.zeros((len(self.owner), self.cells))
        self.average[np.arange(len(self.owner)), self.owner] = 1.0 / self.patches[self.owner]

    def disc(self, cells):
        return np.flatnonzero(self.ring <= DISCS[cells])

    def cue_patches(self):
        """Patches of the 37-cell disc: every world carries their cue populations."""
        return np.flatnonzero(self.ring[self.owner] <= DISCS[37])


INTERIOR_PATCHES = 6


def interior_area(tissue):
    return INTERIOR_PATCHES * tissue.patch_area


def junction_multiplier(tissue, s):
    """Full-tissue junction permeability factor for E07-v1 arm s (same theta)."""
    return s * interior_area(tissue) / fixtures.HEREDITY_AREA_M2


def heterogeneity(tissue, seed):
    return worlds.e07_heterogeneity(
        tissue.cells, len(tissue.pairs), seed=seed, cell_cv=CELL_CV, junction_cv=JUNCTION_CV
    )


def theory_cell(tissue, factors=None):
    """mg0b_theory parameters of an interior full-tissue cell (optionally heterogeneous)."""
    from validation.stationary import targets

    p = targets.heredity_parameters()
    area = interior_area(tissue)
    p = replace(
        p,
        area_m2=area,
        capacitance_F=scale_world.CAPACITANCE_F_m2 * area,
        volume_m3=tissue.volume_pL * 1e-15,
        pump_capacity_mol_s=scale_world.ALPHA_NAK_mol_m2_s * area,
    )
    if factors is not None:
        perm = dict(p.permeability_m_s)
        perm["Na"] *= factors["na_leak"]
        p = replace(
            p,
            permeability_m_s=perm,
            nav_m_s=p.nav_m_s * factors["nav"],
            kir_m_s=p.kir_m_s * factors["kir"],
            pump_capacity_mol_s=p.pump_capacity_mol_s * factors["pump"],
        )
    return p


def coupling(tissue, composition=None, voltage=None):
    """theta per unit s: pre-screen cell vs interior full-tissue cell at a composition."""
    from validation.stationary import reduced, targets

    th = reduced.theory()
    c = dict(zip(MOBILE, H_STATE[1:4], strict=True)) if composition is None else composition
    v = H_STATE[0] if voltage is None else voltage
    j = worlds.e07_junction()
    perm = {s: j["permeability_m_per_s"][s] for s in MOBILE}
    g_open = th.junction_conductance_S(targets.heredity_parameters(), c, j["area_m2"], perm)
    g_pre = th.slope_conductance_S(targets.heredity_parameters(), c, v, 0.0)
    g_full = th.slope_conductance_S(theory_cell(tissue), c, v, 0.0)
    factor = junction_multiplier(tissue, 1.0)
    return dict(
        junction_area_m2=j["area_m2"],
        junction_permeability_m_per_s=j["permeability_m_per_s"],
        G_open_x1_S=g_open,
        g_H_prescreen_cell_S=g_pre,
        g_H_interior_tissue_cell_S=g_full,
        theta_per_unit_s_prescreen=g_open / g_pre,
        junction_permeability_factor_per_unit_s=factor,
        theta_per_unit_s_tissue_interior=factor * g_open / g_full,
        theta_per_unit_s_tissue_edge_cells={
            f"{k} patches": factor * g_open / (g_full * k / INTERIOR_PATCHES) for k in (4, 5)
        },
    )


def part_map(args):
    tissue = Tissue()
    g = tissue.g
    out = dict(
        kind="cells.heredity_pilot_w1_mapping@1",
        world="validation/tissue/surface_pump_v3_study.tissue_definition (resolved_scale_world "
        "seed 0)",
        cells=tissue.cells,
        extracellular_squares=int(g["squares"]),
        patches=len(tissue.owner),
        junctions=len(tissue.pairs),
        faces=len(g["face_sender"]),
        ring_counts=np.bincount(tissue.ring).tolist(),
        degree_counts=np.bincount(tissue.degree).tolist(),
        patch_counts=np.bincount(tissue.patches).tolist(),
        edge_cell_rings=[int(tissue.ring[tissue.degree < 6].min()), int(tissue.ring.max())],
        discs={
            str(n): dict(
                cells=tissue.disc(n).tolist(),
                largest_ring=DISCS[n],
                patches=int(tissue.patches[tissue.disc(n)].sum()),
                extracellular_squares=sorted(
                    set(tissue.square[np.isin(tissue.owner, tissue.disc(n))].tolist())
                ),
            )
            for n in DISCS
        },
        cell_volume_pL=dict(tissue=tissue.volume_pL, prescreen=fixtures.HEREDITY_VOLUME_PL),
        cell_area_m2=dict(
            tissue_interior=interior_area(tissue),
            prescreen=fixtures.HEREDITY_AREA_M2,
            ratio=interior_area(tissue) / fixtures.HEREDITY_AREA_M2,
        ),
        extracellular_square_volume_pL=float(g["square_volume_pL"]),
        coupling_at_nominal_H=coupling(tissue),
        arms={f"s{s:g}": dict(s=s, junction_factor=junction_multiplier(tissue, s)) for s in SCALES},
        heterogeneity=dict(
            function="validation/stationary/worlds.e07_heterogeneity",
            cell_cv=CELL_CV,
            junction_cv=JUNCTION_CV,
            seeds=SEEDS,
            draws="numpy default_rng(seed): lognormal(-sigma^2/2, sigma), sigma^2 = log(1+cv^2); "
            "per cell nav, kir, na_leak, pump (225 each, in that order), then 618 junctions",
        ),
        cue=dict(
            law=NALEAK_LAW_ID,
            factor=CUE_FACTOR,
            populations="one per patch of the 37-cell disc, max permeability 9 x the patch's Na "
            "leak (heterogeneity included), availability 1 only during the cue on the arm's disc",
        ),
        classification=dict(
            threshold_V=THRESHOLD_V,
            rule="a cell is D when the mean of its patches' membrane voltages is above the "
            "single-cell U state (pre-screens: V above the slow U voltage)",
        ),
        mismatches=[
            "extracellular space: finite 0.54 pL squares (shared by neighbouring patches, held "
            "outer ring) instead of one held bath per cell; extracellular potentials and "
            "concentrations are free",
            "cell volume 0.741 pL vs 0.7505 pL; interior area 3.204e-10 vs 3.261e-10 m^2 "
            "(compensated in the junction factor)",
            "lattice jitter 3% of the spacing; 225 cells in a roughly circular cluster (rings up "
            "to 9) instead of the 127-cell hexagon; edge cells have 4-6 patches",
            "tissue junction gates start at the uniform-H steady state of the start analysis",
        ],
    )
    out["single_cell_states"] = cell_states(tissue, args.seeds)
    write_json(Path(args.output) / "mapping.json", out)
    log("mapping written")


def cell_states(tissue, seeds=SEEDS):
    """Stationary states of each disc cell alone at its drawn factors (reduced theory)."""
    from validation.stationary import reduced

    th = reduced.theory()
    result = {}
    for seed in seeds:
        factors, _ = heterogeneity(tissue, seed)
        rows = []
        for i in tissue.disc(37):
            states = th.slow_states(theory_cell(tissue, factors[i]), 0.0)
            rows.append(
                dict(
                    cell=int(i),
                    factors=factors[i],
                    states_mV=[1e3 * v for v, _ in states],
                    has_D=any(v > THRESHOLD_V for v, _ in states),
                )
            )
        result[str(seed)] = dict(
            disc_cells_without_D=[r["cell"] for r in rows if not r["has_D"]], cells=rows
        )
        log(
            f"seed {seed}: disc cells without a D state {result[str(seed)]['disc_cells_without_D']}"
        )
    return result


# ---------------------------------------------------------- cue checks (simplified)


def part_cue(args):
    """Single heredity cell: how long must Na leak x10 last to switch H -> D?"""
    from cells.core.runner import run

    out = dict(dt_s=DT, threshold_V=THRESHOLD_V, cue_start_s=0.1, after_s=5.0, cases=[])
    for duration_ms in (20, 50, 100, 120, 150, 200, 500, 2000):
        start, stop = 100, 100 + duration_ms
        total = stop + 5000
        times = [k * DT for k in range(0, total, 10)] + [total * DT]
        raw = heredity.write_definition(
            DT, end_time=total * DT, times=times, cue=(start * DT, stop * DT)
        )
        tick = time.perf_counter()
        value = run(parse_spec(raw))
        vm = np.asarray(value.observations.membrane_voltage_V[:, 0])
        t = np.asarray(times)
        above = t[vm > THRESHOLD_V]
        out["cases"].append(
            dict(
                cue_s=duration_ms * DT,
                vm_at_cue_end_V=float(vm[t == stop * DT][0]) if np.any(t == stop * DT) else None,
                final_vm_V=float(vm[-1]),
                final_state="D" if vm[-1] > THRESHOLD_V else "H",
                first_above_U_s=float(above[0]) if len(above) else None,
                wall_s=time.perf_counter() - tick,
                diagnostics=value.diagnostics,
            )
        )
        log(f"single cell cue {duration_ms} ms: {out['cases'][-1]['final_state']}")
        write_json(Path(args.output) / "cue_single_cell.json", out)
    switched = [c["cue_s"] for c in out["cases"] if c["final_state"] == "D"]
    held = [c["cue_s"] for c in out["cases"] if c["final_state"] == "H"]
    out["minimum_switching_cue_bracket_s"] = [max(held, default=None), min(switched, default=None)]
    write_json(Path(args.output) / "cue_single_cell.json", out)


SHEET_RADIUS = 6
SHEET_CUES_MS = (500, 2000)
SHEET_AFTER_STEPS = 20_000
SHEET_LEAD_STEPS = 500


def sheet_definition(disc_cells, s, cue_ms, backend, after=SHEET_AFTER_STEPS):
    """Pre-screen 7's sheet (127 cells, own held baths, E07 gated junctions) with the cue."""
    cells, edges = worlds.hexagon(SHEET_RADIUS)
    h = H_STATE[:4]
    on, off = SHEET_LEAD_STEPS, SHEET_LEAD_STEPS + cue_ms
    end = off + after
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition([h] * len(cells), edges, scale=s, gated=True, dt=DT)
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    disc = [i for i, c in enumerate(cells) if worlds.ring(c) <= DISCS[disc_cells]]
    # Every world carries the 37-cell disc's cue populations (equal shapes for vmap).
    for i in (i for i, c in enumerate(cells) if worlds.ring(c) <= DISCS[37]):
        schedule = [dict(time=0.0, availability=0.0)]
        if i in disc:
            schedule += [
                dict(time=on * DT, availability=1.0),
                dict(time=off * DT, availability=0.0),
            ]
        m["channels"].append(
            fixtures.channel(
                f"cue_{i}",
                i,
                NALEAK_LAW_ID,
                "Na",
                (CUE_FACTOR - 1) * m["membranes"][i]["permeability_m_per_s"]["Na"],
                1.0,
                [],
            )
        )
        e["channel_controls"].append(dict(channel_id=f"cue_{i}", schedule=schedule))
    x["channel_capacity"] = len(m["channels"])
    observed = observation_steps_sheet(on, off, end)
    e["end_time"] = end * DT
    e["observation_times"] = [k * DT for k in observed]
    x.update(backend=backend, max_steps=end + 8)
    return raw, np.array(disc), dict(on=on, off=off, end=end)


def observation_steps_sheet(on, off, end):
    steps = set(range(0, on, 100)) | set(range(on, off + 3000, 20))
    steps |= set(range(off + 3000, off + 15000, 100)) | set(range(off + 15000, end, 500))
    return sorted(k for k in steps | {end} if k <= end)


def part_sheet(args):
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.vector_windows import run_vector_windowed
    from cells.core.windows import WindowPolicy

    output = Path(args.output) / "sheet"
    output.mkdir(parents=True, exist_ok=True)
    cases, worlds_, discs = [], [], {}
    for disc_cells in DISCS:
        for s in SCALES:
            for cue_ms in SHEET_CUES_MS:
                raw, disc, phases = sheet_definition(
                    disc_cells, s, cue_ms, args.backend, int(round(args.sheet_after_seconds / DT))
                )
                wid = len(cases) + 1
                cases.append(
                    dict(world=wid, disc_cells=disc_cells, s=s, cue_s=cue_ms * DT, **phases)
                )
                worlds_.append(WorldSpec(wid, parse_spec(raw)))
                discs[wid] = disc
    spec = BatchSpec(tuple(worlds_), len(worlds_), 2**53 - 1, 2**53 - 1)
    records = {c["world"]: [] for c in cases}
    n = len(worlds.hexagon(SHEET_RADIUS)[0])

    def sink(window):
        for wid, found in window.observations.items():
            vm = np.asarray(found.membrane_voltage_V)[:, :n]
            amount = np.asarray(found.amount)
            for row, t in enumerate(found.times):
                d = vm[row] > THRESHOLD_V
                inside = np.zeros(n, dtype=bool)
                inside[discs[wid]] = True
                conc = amount[row][:, discs[wid]] / fixtures.HEREDITY_VOLUME_PL
                records[wid].append(
                    dict(
                        t=float(t),
                        d_inside=int(d[inside].sum()),
                        d_outside=int(d[~inside].sum()),
                        disc_vm_V=[float(vm[row][inside].min()), float(vm[row][inside].max())],
                        outside_vm_V=[float(vm[row][~inside].min()), float(vm[row][~inside].max())],
                        disc_mean_mM=dict(zip(ION_IDS, conc.mean(axis=1).tolist(), strict=True)),
                        cue_availability=float(
                            np.asarray(found.channel_availability)[row][2 * n :].max()
                        ),
                    )
                )

    tick = time.perf_counter()
    report = dict(kind="cells.heredity_pilot_w1_sheet@1", cases=cases, threshold_V=THRESHOLD_V)
    try:
        result = run_vector_windowed(spec, WindowPolicy(WINDOW_STEPS, "checkpoints"), sink=sink)
        report.update(timings=result.timings, resources=dict(result.resources))
        report["diagnostics"] = {str(k): w.diagnostics for k, w in result.worlds.items()}
    except Exception as error:  # Preserved as evidence.
        report["failure"] = dict(error=repr(error), traceback=traceback.format_exc())
    report["wall_seconds"] = time.perf_counter() - tick
    for case in cases:
        case["outcome"] = sheet_outcome(records[case["world"]], case)
        log(f"sheet {case['disc_cells']} s {case['s']} cue {case['cue_s']}: {case['outcome']}")
    write_json(output / "sheet.json", report)
    write_json(output / "sheet_records.json", {str(k): v for k, v in records.items()})


def sheet_outcome(rows, case):
    """Write and retention summary of one sheet record list (times in s from cue off)."""
    off = case["off"] * DT
    disc = case["disc_cells"]
    during = [r for r in rows if case["on"] * DT <= r["t"] <= off]
    all_d = next((r["t"] - case["on"] * DT for r in during if r["d_inside"] == disc), None)
    at_off = next((r for r in rows if r["t"] >= off), None)
    after = [r for r in rows if r["t"] > off]
    first = next((r["t"] - off for r in after if r["d_inside"] < disc), None)
    gone = next((r["t"] - off for r in after if r["d_inside"] == 0), None)
    return dict(
        all_disc_D_under_cue_after_s=all_d,
        written_at_cue_off=bool(at_off and at_off["d_inside"] == disc and at_off["d_outside"] == 0),
        disc_mean_at_cue_off_mM=at_off and at_off["disc_mean_mM"],
        first_D_lost_after_cue_off_s=first,
        all_D_lost_after_cue_off_s=gone,
        d_inside_at_end=rows[-1]["d_inside"] if rows else None,
        max_d_outside=max((r["d_outside"] for r in rows), default=None),
    )


# --------------------------------------------------- 70-minute sheet retention

LONG_SCALES = (0.3, 0.6, 1.0)
LONG_CUE_S = (0.5, 2.5)  # Na leak x10 on [0.5, 2.5) s: the cue chosen above (2 s).
LONG_END_S = 4200.0  # D133's 70 min D-residence cap.
OSMOTIC_FLAG, OSMOTIC_CENSOR = 0.10, 0.15  # E07: flag above 10%, censor above 15%.
# Written before the 70-minute runs, from pre-screens 7-9 and the 20 s sheet check
# (checks/sheet: cue-written discs, H composition, all held at s 0.3 and 1.0 for 20 s).
LONG_PREDICTIONS = dict(
    kind="cells.heredity_pilot_w1_long_sheet_predictions@1",
    status="written before the 70-minute sheet runs; development analysis, not judged",
    sources=[
        "prescreen-07-stationary/summary.md: stationary D-composition discs stable for s < 0.661 "
        "(19) and s < 0.922 (37); at s 1 started from D they are lost in 0.5-1 s and 30-60 s",
        "prescreen-09-turnover/mechanism: cells written from the H composition load slowly "
        "(K 136 -> 153, M 7 -> 29 mM over 1500 s); loading takes about 40-50 min",
        "heredity-pilot-w1 checks/sheet: cue-written discs keep the H composition (K 136, M 7) "
        "and all held 20 s, also at s 1.0; the frozen-composition disc at H composition exists "
        "at s 1.0 although the D-composition one does not (pre-screen 7)",
        "design.json R1: written D cells reach about +8-9% osmolarity at 1 h, +15% at 2 h",
    ],
    arms={
        "s0.3": "both discs written and held for 70 min (inside the stationary window)",
        "s0.6": "37-cell disc held for 70 min; 19-cell disc held (s 0.6 is 9% below its "
        "stationary edge 0.661), the least certain of the held arms",
        "s1.0": "both written and held at first (frozen-composition disc at H composition); "
        "lost once composition loading removes that disc, before full loading: the 19-cell "
        "disc first, the 37-cell disc later, both within 70 min, most likely between 5 and "
        "45 min after the cue; the loss is collective within seconds once it starts",
    },
    osmotic="held discs approach the 10% flag near 60-70 min (relative to the cell's own "
    "osmolarity at t = 0); none reaches the 15% censor within 70 min",
    spontaneous_D_outside_disc="none in any arm",
)


def long_sheet_definition(disc_cells, s, dt, end_s, backend):
    """Pre-screen 7's sheet with the cue, on a dt grid, to end_s (every event i * dt)."""
    cells, edges = worlds.hexagon(SHEET_RADIUS)
    on, off = int(round(LONG_CUE_S[0] / dt)), int(round(LONG_CUE_S[1] / dt))
    end = int(round(end_s / dt))
    raw = worlds.ionic_background(
        worlds.e07_sheet_definition([H_STATE[:4]] * len(cells), edges, scale=s, gated=True, dt=dt)
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    disc = [i for i, c in enumerate(cells) if worlds.ring(c) <= DISCS[disc_cells]]
    for i in (i for i, c in enumerate(cells) if worlds.ring(c) <= DISCS[37]):
        schedule = [dict(time=0.0, availability=0.0)]
        if i in disc:
            schedule += [
                dict(time=on * dt, availability=1.0),
                dict(time=off * dt, availability=0.0),
            ]
        m["channels"].append(
            fixtures.channel(
                f"cue_{i}",
                i,
                NALEAK_LAW_ID,
                "Na",
                (CUE_FACTOR - 1) * m["membranes"][i]["permeability_m_per_s"]["Na"],
                1.0,
                [],
            )
        )
        e["channel_controls"].append(dict(channel_id=f"cue_{i}", schedule=schedule))
    x["channel_capacity"] = len(m["channels"])
    per_s = int(round(1.0 / dt))
    steps = {0, *range(0, on, max(1, int(round(0.1 / dt))))}
    steps |= set(range(on, off + 3 * per_s, max(1, int(round(0.02 / dt)))))
    steps |= set(range(off + 3 * per_s, off + 15 * per_s, max(1, int(round(0.1 / dt)))))
    steps |= set(range(off + 15 * per_s, min(end, 600 * per_s), per_s))
    steps |= set(range(600 * per_s, end, 5 * per_s))
    observed = sorted(t for t in steps | {end} if t <= end)
    e["end_time"] = end * dt
    e["observation_times"] = [t * dt for t in observed]
    x.update(backend=backend, max_steps=end + 8)
    return raw, np.array(disc), dict(on_s=on * dt, off_s=off * dt, end_s=end * dt, dt_s=dt)


class SheetRecorder:
    """Per-cell Vm, composition and osmolarity of each sheet world, written as it runs."""

    def __init__(self, output, discs, cells, *, snapshots=(), batch=None):
        self.output, self.discs, self.cells = Path(output), discs, cells
        self.output.mkdir(parents=True, exist_ok=True)
        self.snapshots, self.batch = sorted(snapshots), batch
        self.data = {w: dict(t=[], vm=[], conc=[]) for w in discs}
        self.initial = {}
        self.streams = {w: open(self.output / f"world-{w}.jsonl", "a", buffering=1) for w in discs}
        self.windows = open(self.output / "windows.jsonl", "a", buffering=1)
        self.last = time.perf_counter()

    def __call__(self, window):
        tick = time.perf_counter()
        n = self.cells
        for wid, found in window.observations.items():
            inside = np.zeros(n, dtype=bool)
            inside[self.discs[wid]] = True
            vm = np.asarray(found.membrane_voltage_V)[:, :n]
            conc = np.asarray(found.amount)[:, :, :n] / fixtures.HEREDITY_VOLUME_PL
            osm = conc.sum(axis=1)
            if wid not in self.initial:
                self.initial[wid] = osm[0]
            excess = osm / self.initial[wid] - 1.0
            for row, t in enumerate(np.asarray(found.times)):
                d = vm[row] > THRESHOLD_V
                ex = excess[row][inside]
                self.streams[wid].write(
                    json.dumps(
                        dict(
                            t=float(t),
                            d_inside=int(d[inside].sum()),
                            d_outside=int(d[~inside].sum()),
                            disc_vm_V=[float(vm[row][inside].min()), float(vm[row][inside].max())],
                            outside_vm_V=[
                                float(vm[row][~inside].min()),
                                float(vm[row][~inside].max()),
                            ],
                            disc_mean_mM=dict(
                                zip(
                                    ION_IDS, conc[row][:, inside].mean(axis=1).tolist(), strict=True
                                )
                            ),
                            disc_osmotic_excess=[float(ex.min()), float(ex.max())],
                            max_osmotic_excess=float(excess[row].max()),
                            flagged=bool(excess[row].max() > OSMOTIC_FLAG),
                            censored=bool(excess[row].max() > OSMOTIC_CENSOR),
                            cue_availability=float(
                                np.asarray(found.channel_availability)[row][2 * n :].max()
                            ),
                        )
                    )
                    + "\n"
                )
                self.data[wid]["t"].append(float(t))
                self.data[wid]["vm"].append(vm[row])
                self.data[wid]["conc"].append(conc[row][:3])
        self.windows.write(
            json.dumps(
                dict(
                    index=window.index,
                    timings=window.timings,
                    diagnostics={str(w): d for w, d in window.diagnostics.items()},
                    end_times={str(w): c.time for w, c in window.checkpoints.items()},
                    sink_seconds=time.perf_counter() - tick,
                )
            )
            + "\n"
        )
        if time.perf_counter() - self.last > 600:
            self.save()
        ends = {c.time for c in window.checkpoints.values()}
        if self.snapshots and len(ends) == 1:
            end = ends.pop()
            due = [t for t in self.snapshots if end >= t - 1e-9]
            if due:
                from cells.batch_io import write_batch_snapshot

                self.save()
                write_batch_snapshot(
                    self.output.parent / "snapshots" / f"t{end:09.3f}",
                    self.batch,
                    dict(window.checkpoints),
                )
                self.snapshots = [t for t in self.snapshots if t not in due]

    def save(self):
        for wid, d in self.data.items():
            if d["t"]:
                np.savez(
                    self.output / f"world-{wid}-cells.npz",
                    times_s=np.array(d["t"]),
                    vm_V=np.array(d["vm"]),
                    concentration_mM=np.array(d["conc"]),
                    species=np.array(ION_IDS[:3]),
                    initial_osmolarity_mM=self.initial.get(wid, np.array([])),
                )
        self.last = time.perf_counter()

    def close(self):
        self.save()
        for stream in (*self.streams.values(), self.windows):
            stream.close()


def part_longsheet(args):
    """Cue-written 19- and 37-cell discs on the homogeneous held-bath sheet, 70 min."""
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.windows import WindowPolicy

    output = Path(args.output) / (f"longsheet-{args.label}" if args.label else "longsheet")
    output.mkdir(parents=True, exist_ok=True)
    if not (output / "predictions.json").exists():
        write_json(output / "predictions.json", LONG_PREDICTIONS)
    cases, members, discs = [], [], {}
    for disc_cells in args.discs:
        for s in args.scales:
            raw, disc, phases = long_sheet_definition(
                disc_cells, s, args.dt, args.long_end_seconds, args.backend
            )
            wid = len(cases) + 1
            cases.append(dict(world=wid, disc_cells=disc_cells, s=s, **phases))
            members.append(WorldSpec(wid, parse_spec(raw)))
            discs[wid] = disc
    spec = BatchSpec(tuple(members), len(members), 2**53 - 1, 2**53 - 1)
    report = dict(
        kind="cells.heredity_pilot_w1_long_sheet@1",
        world="validation/stationary/worlds.e07_sheet_definition: 127-cell hexagon, own held "
        "baths, E07 gated junctions at s, homogeneous heredity cells (ionic background), "
        "cue populations on the 37-cell disc's cells",
        engine_model="resolved_pump_tissue@3 through core/vector_windows.py (device checks)",
        cases=cases,
        threshold_V=THRESHOLD_V,
        osmotic=dict(
            excess="cell osmolarity (Na + K + M + P) over its own value at t = 0, minus 1",
            flag=OSMOTIC_FLAG,
            censor=OSMOTIC_CENSOR,
        ),
        window_steps=WINDOW_STEPS,
    )
    write_json(output / "longsheet.json", report)
    n = len(worlds.hexagon(SHEET_RADIUS)[0])
    marks = [t for t in np.arange(600.0, args.long_end_seconds, 600.0)]
    recorder = SheetRecorder(output / "records", discs, n, snapshots=marks, batch=spec)
    tick = time.perf_counter()
    result, failure = run_batch(spec, WindowPolicy(WINDOW_STEPS, "checkpoints"), recorder)
    report["wall_seconds"] = time.perf_counter() - tick
    report["resources"] = resources()
    if failure is not None:
        report["failure"] = failure
        write_json(output / f"failure-{int(time.time())}.json", failure)
    else:
        report.update(timings=result.timings, batch_resources=dict(result.resources))
        report["diagnostics"] = {str(k): w.diagnostics for k, w in result.worlds.items()}
    write_json(output / "longsheet.json", report)
    summarize_longsheet(output)
    return 1 if failure is not None else 0


def summarize_longsheet(output):
    output = Path(output)
    report = json.loads((output / "longsheet.json").read_text())
    rows = {}
    for case in report["cases"]:
        path = output / "records" / f"world-{case['world']}.jsonl"
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        off, disc = case["off_s"], case["disc_cells"]
        after = [r for r in records if r["t"] >= off - 1e-9]
        written = bool(after and after[0]["d_inside"] == disc and after[0]["d_outside"] == 0)
        cells = output / "records" / f"world-{case['world']}-cells.npz"
        per_cell = None
        if cells.exists():
            with np.load(cells) as data:
                t, vm = data["times_s"], data["vm_V"]
            inside = np.zeros(vm.shape[1], dtype=bool)
            inside[
                [
                    i
                    for i, c in enumerate(worlds.hexagon(SHEET_RADIUS)[0])
                    if worlds.ring(c) <= DISCS[disc]
                ]
            ] = True
            later = t >= off - 1e-9
            lost = {}
            for i in np.flatnonzero(inside):
                h = later & (vm[:, i] <= THRESHOLD_V)
                lost[int(i)] = None if not h.any() else float(t[np.flatnonzero(h)[0]] - off)
            per_cell = lost
        rows[str(case["world"])] = dict(
            case,
            written=written,
            first_D_lost_bracket_s=_bracket(after, off, lambda r, n=disc: r["d_inside"] < n),
            all_D_lost_bracket_s=_bracket(after, off, lambda r: r["d_inside"] == 0),
            d_inside_at_end=records[-1]["d_inside"] if records else None,
            max_d_outside=max((r["d_outside"] for r in records), default=None),
            first_flag_s=next((r["t"] for r in records if r["flagged"]), None),
            first_censor_s=next((r["t"] for r in records if r["censored"]), None),
            max_osmotic_excess=max((r["max_osmotic_excess"] for r in records), default=None),
            last_time_s=records[-1]["t"] if records else None,
            disc_mean_at_end_mM=records[-1]["disc_mean_mM"] if records else None,
            cell_first_H_after_cue_off_s=per_cell,
        )
    kind = "cells.heredity_pilot_w1_long_sheet_results@1"
    write_json(output / "results.json", dict(kind=kind, failure=report.get("failure"), worlds=rows))


# ------------------------------------------------------------- start state


def held_bath_definition(tissue, seed, s):
    """The tissue's cell graph with held baths: cells of the tissue's volume and areas."""
    cell_factors, junction_factors = heterogeneity(tissue, seed)
    states = [H_STATE[:4]] * tissue.cells
    raw = worlds.e07_sheet_definition(
        states,
        tissue.pairs,
        scale=junction_multiplier(tissue, s),
        gated=True,
        dt=DT,
        cell_factors=cell_factors,
        junction_factors=junction_factors,
    )
    m = raw["model"]
    composition = dict(zip(MOBILE, H_STATE[1:4], strict=True)) | dict(
        P=fixtures.HEREDITY_FIXED_ANION_mM
    )
    for i, cell in enumerate(m["cells"]):
        membrane, area = m["membranes"][i], float(tissue.area[i])
        membrane["area_m2"] = area
        membrane["capacitance_F"] = scale_world.CAPACITANCE_F_m2 * area
        cell["volume_pL"] = tissue.volume_pL
        amounts = {k: composition[k] * tissue.volume_pL for k in ION_IDS}
        # The guess's charge is C V_H (M absorbs the difference, ~0.01 mM): with the
        # tissue's areas the H composition alone would put edge cells near -120 mV.
        excess = ionic_charge(amounts) - membrane["capacitance_F"] * H_STATE[0]
        amounts["M"] += excess / CHARGE_PER_FMOL
        cell["initial_amount_fmol"] = amounts
        membrane["pump"]["capacity_fmol_per_s"] = (
            scale_world.ALPHA_NAK_mol_m2_s * area * 1e15 * cell_factors[i]["pump"]
        )
    return worlds.ionic_background(raw)


def part_start(args):
    """Coupled uniform-H start per (seed, s): Newton on the held-bath cell graph."""
    import jax.numpy as jnp

    from cells.analysis import stationary as sa

    tissue = Tissue()
    output = Path(args.output) / "start"
    output.mkdir(parents=True, exist_ok=True)
    for seed in args.seeds:
        for s in args.scales:
            label = f"seed{seed}-s{s:g}"
            if (output / f"{label}.npz").exists():
                continue
            tick = time.perf_counter()
            record = dict(seed=seed, s=s, analysis=sa.ANALYSIS_ID, mode="slow", formulation="rhs")
            try:
                spec = parse_spec(held_bath_definition(tissue, seed, s))
                pb = sa.problem(spec, mode="slow")
                record["coordinates"] = int(len(pb.anchor))
                solution = sa.newton(pb, pb.anchor)
                record.update(
                    converged=solution.converged,
                    message=solution.message,
                    iterations=solution.iterations,
                    residual_inf_per_s=solution.residual_inf,
                    error_estimate=solution.error_estimate,
                )
                if not solution.converged:
                    raise RuntimeError("Newton did not converge: " + solution.message)
                state, p, _ = pb.embed(jnp.asarray(solution.u))
                amounts = np.asarray(p.amount_reference + state.amount_increment)
                voltage = np.asarray(pb.evaluate(solution.u)[3])[: tissue.cells]
                gate = np.asarray(state.channel_gate)
                ids = list(spec.model.species_ids)
                fmol = np.stack([amounts[ids.index(k), : tissue.cells] for k in ION_IDS], axis=1)
                stab = sa.stability(pb, solution.u, count=8)
                record.update(
                    all_H=bool(np.all(voltage < THRESHOLD_V)),
                    vm_range_V=[float(voltage.min()), float(voltage.max())],
                    stability=dict(
                        classification=stab["classification"],
                        leading_eigenvalues_per_s=stab["eigenvalues_per_s"][:4],
                        relaxation_times_s=stab["relaxation_times_s"][:4],
                    ),
                    consistency=sa.consistency(pb, solution.u),
                    wall_seconds=time.perf_counter() - tick,
                )
                np.savez(
                    output / f"{label}.npz",
                    amounts_fmol=fmol,
                    species=np.array(ION_IDS),
                    vm_V=voltage,
                    kir_gate=gate[:, 0 : 2 * tissue.cells : 2].T,
                    nav_gate=gate[:, 1 : 2 * tissue.cells : 2].T,
                    junction_gate=np.asarray(state.junction_gate)[: len(tissue.pairs)],
                )
                log(f"start {label}: {record['vm_range_V']} {stab['classification']}")
            except Exception as error:  # Kept as evidence.
                record["failure"] = dict(error=repr(error), traceback=traceback.format_exc())
                log(f"start {label} failed: {error!r}")
            write_json(output / f"{label}.json", record)


def load_start(directory, seed, s):
    with np.load(Path(directory) / "start" / f"seed{seed}-s{s:g}.npz") as data:
        return {k: data[k] for k in data.files}


# ------------------------------------------------------------- full tissue


def tissue_world(
    tissue, seed, s, start, *, end_step, observed, backend, cue=None, max_trace_bytes=2**34
):
    """The full tissue at arm (seed, s) from a start state; cue = (disc cells, on, off)."""
    raw = heredity.tissue_definition(
        dt=DT, end_time=end_step * DT, backend=backend, observation_times=[k * DT for k in observed]
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    cell_factors, junction_factors = heterogeneity(tissue, seed)
    channels = {c["id"]: c for c in m["channels"]}
    for k, membrane in enumerate(m["membranes"]):
        i, f = int(tissue.owner[k]), cell_factors[int(tissue.owner[k])]
        kir, nav = channels[f"kir_{k}"], channels[f"nav_{k}"]
        kir["max_permeability_m_per_s"] *= f["kir"]
        nav["max_permeability_m_per_s"] *= f["nav"]
        kir["initial_gate"] = [float(v) for v in start["kir_gate"][i]]
        nav["initial_gate"] = [float(v) for v in start["nav_gate"][i]]
        membrane["permeability_m_per_s"]["Na"] *= f["na_leak"]
        membrane["pump"]["capacity_fmol_per_s"] *= f["pump"]
    disc = set() if cue is None else set(tissue.disc(cue[0]).tolist())
    for k in tissue.cue_patches():
        membrane = m["membranes"][k]
        m["channels"].append(
            dict(
                id=f"cue_{k}",
                membrane_id=membrane["id"],
                kinetic_law=NALEAK_LAW_ID,
                max_permeability_m_per_s=(CUE_FACTOR - 1) * membrane["permeability_m_per_s"]["Na"],
                abundance=1.0,
                initial_gate=[],
                permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
            )
        )
        schedule = [dict(time=0.0, availability=0.0)]
        if int(tissue.owner[k]) in disc:
            schedule += [
                dict(time=cue[1] * DT, availability=1.0),
                dict(time=cue[2] * DT, availability=0.0),
            ]
        e["channel_controls"].append(dict(channel_id=f"cue_{k}", schedule=schedule))
    x["channel_capacity"] = len(m["channels"])
    x["max_trace_bytes"] = max_trace_bytes
    factor = junction_multiplier(tissue, s)
    for k, junction in enumerate(m["junctions"]):
        junction["permeability_m_per_s"] = {
            name: value * factor * junction_factors[k]
            for name, value in junction["permeability_m_per_s"].items()
        }
        junction["gate"]["initial_gate"] = float(start["junction_gate"][k])
    # Cells at the start composition; their charge is the ions' (fixed charge 0) and
    # sits as C Vm on the patch capacitors, so each patch's square gets -C_patch Vm,
    # carried as K (the ion a cell charging from neutral would have moved out). The
    # squares' charge anchors are those counter-charges exactly: the capacitor
    # component's net charge is then zero to rounding of the charges themselves
    # (the bath composition's own float residue, ~1e-24 C a square, stays within
    # the anchor check but would otherwise add up across the component).
    ions = [str(v) for v in start["species"]]
    counter = np.zeros(len(m["extracellular"]))
    charge = np.zeros(tissue.cells)
    for i, cell in enumerate(m["cells"]):
        cell["initial_amount_fmol"] = {
            k: float(start["amounts_fmol"][i, ions.index(k)]) for k in cell["initial_amount_fmol"]
        }
        cell["fixed_charge_equivalent_fmol"] = 0.0
        cell["initial_charge_C"] = charge[i] = ionic_charge(cell["initial_amount_fmol"])
    capacitance = np.array([p["capacitance_F"] for p in m["membranes"]])
    total = np.bincount(tissue.owner, weights=capacitance, minlength=tissue.cells)
    for k in range(len(m["membranes"])):
        i = tissue.owner[k]
        counter[tissue.square[k]] -= charge[i] * (capacitance[k] / total[i])
    for j, square in enumerate(m["extracellular"]):
        if counter[j] != 0.0:
            square["initial_amount_fmol"]["K"] += counter[j] / CHARGE_PER_FMOL
            square["initial_charge_C"] = float(counter[j])
    return raw


def ionic_charge(amounts, fixed=0.0):
    return CHARGE_PER_FMOL * math.fsum((fixed, *(VALENCE[k] * v for k, v in amounts.items())))


def arm_label(seed, s, disc=None):
    return f"seed{seed}-s{s:g}" + ("" if disc is None else f"-disc{disc}")


class Observer:
    """Window sink: compact per-observation records, per-window diagnostics, cost."""

    def __init__(self, tissue, meta, output, *, snapshots=(), batch=None):
        self.tissue, self.meta, self.output = tissue, meta, Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        # Complete cohort snapshots (resume points) at these model times (s).
        self.snapshots, self.batch = sorted(snapshots), batch
        self.cell_vm = {w: [] for w in meta}
        self.times = {w: [] for w in meta}
        self.streams = {w: open(self.output / f"world-{w}.jsonl", "a", buffering=1) for w in meta}
        self.windows = open(self.output / "windows.jsonl", "a", buffering=1)
        self.disc_squares = {
            n: np.array(sorted(set(tissue.square[np.isin(tissue.owner, tissue.disc(n))])))
            for n in DISCS
        }
        self.started = time.perf_counter()
        self.last_write = self.started

    def __call__(self, window):
        tick = time.perf_counter()
        t = self.tissue
        for wid, found in window.observations.items():
            meta = self.meta[wid]
            disc = np.zeros(t.cells, dtype=bool)
            disc[t.disc(meta.get("disc", 37))] = True
            vm = np.asarray(found.membrane_voltage_V)[:, : len(t.owner)] @ t.average
            amount = np.asarray(found.amount)[:, :, : t.cells]
            outside = np.asarray(found.extracellular_amount)
            ids = meta["species"]
            availability = np.asarray(found.channel_availability)[:, meta["cue_slots"]]
            on = availability[:, meta["cue_on_mask"]] if meta["cue_on_mask"].any() else None
            for row, time_s in enumerate(np.asarray(found.times)):
                d = vm[row] > THRESHOLD_V
                conc = amount[row][:, disc] / t.volume_pL
                squares = self.disc_squares[meta.get("disc", 37)]
                ecm = outside[row][:, squares] / t.g["square_volume_pL"]
                record = dict(
                    t=float(time_s),
                    d_inside=int(d[disc].sum()),
                    d_outside=int(d[~disc].sum()),
                    d_outside_cells=np.flatnonzero(d & ~disc).tolist()[:20],
                    disc_vm_V=[float(vm[row][disc].min()), float(vm[row][disc].max())],
                    outside_vm_V=[float(vm[row][~disc].min()), float(vm[row][~disc].max())],
                    disc_mean_mM={k: float(conc[ids.index(k)].mean()) for k in ION_IDS},
                    disc_squares_mean_mM={k: float(ecm[ids.index(k)].mean()) for k in ION_IDS},
                    cue_on_availability=None
                    if on is None
                    else [float(on[row].min()), float(on[row].max())],
                    cue_off_availability_max=float(
                        availability[row][~meta["cue_on_mask"]].max(initial=0.0)
                    ),
                    extracellular_potential_V=[
                        float(np.asarray(found.extracellular_potential_V)[row].min()),
                        float(np.asarray(found.extracellular_potential_V)[row].max()),
                    ],
                )
                self.streams[wid].write(json.dumps(record) + "\n")
                self.times[wid].append(float(time_s))
                self.cell_vm[wid].append(vm[row])
        self.windows.write(
            json.dumps(
                dict(
                    index=window.index,
                    timings=window.timings,
                    observed={str(w): len(o.times) for w, o in window.observations.items()},
                    diagnostics={str(w): d for w, d in window.diagnostics.items()},
                    end_times={str(w): c.time for w, c in window.checkpoints.items()},
                    sink_seconds=time.perf_counter() - tick,
                    wall_seconds=time.perf_counter() - self.started,
                )
            )
            + "\n"
        )
        if time.perf_counter() - self.last_write > 300:
            self.save()
        ends = {c.time for c in window.checkpoints.values()}
        if self.snapshots and len(ends) == 1:
            end = ends.pop()
            if any(abs(end - t) < 0.5 * DT for t in self.snapshots):
                from cells.batch_io import write_batch_snapshot

                self.save()
                write_batch_snapshot(
                    self.output.parent / "snapshots" / f"t{end:09.3f}",
                    self.batch,
                    dict(window.checkpoints),
                )
                self.snapshots = [t for t in self.snapshots if abs(end - t) >= 0.5 * DT]

    def save(self):
        for wid in self.meta:
            if self.times[wid]:
                np.savez(
                    self.output / f"world-{wid}-cell-vm.npz",
                    times_s=np.array(self.times[wid]),
                    cell_vm_V=np.array(self.cell_vm[wid]),
                )
        self.last_write = time.perf_counter()

    def close(self):
        self.save()
        for stream in (*self.streams.values(), self.windows):
            stream.close()


def world_meta(spec, tissue, disc=None):
    ids = [c.id for c in spec.model.channels]
    slots = np.array([ids.index(f"cue_{k}") for k in tissue.cue_patches()])
    on = np.zeros(len(slots), dtype=bool)
    if disc is not None:
        on = np.isin(tissue.owner[tissue.cue_patches()], tissue.disc(disc))
    return dict(
        species=list(spec.model.species_ids), cue_slots=slots, cue_on_mask=on, disc=disc or 37
    )


def run_batch(spec, policy, observer, checkpoints=None):
    """run_vector_windowed with the failure preserved; returns (result, failure)."""
    from cells.core.vector_windows import WorldCheckError, run_vector_windowed

    try:
        return run_vector_windowed(spec, policy, checkpoints, sink=observer), None
    except WorldCheckError as error:
        return None, dict(
            error=repr(error),
            world_id=error.world_id,
            step_index=error.step_index,
            time_interval=error.time_interval,
            checks=error.checks,
            traceback=traceback.format_exc(),
        )
    except Exception as error:
        return None, dict(error=repr(error), traceback=traceback.format_exc())
    finally:
        observer.close()


def prepare_steps(args):
    return int(round(args.prepare_seconds / DT))


def prepare_worlds(args, tissue, *, end_step, observed, cue_for=None):
    """(BatchSpec, meta) of the (seed, s) worlds from their start states."""
    from cells.core.batch import BatchSpec, WorldSpec

    members, meta = [], {}
    for seed in args.seeds:
        for s in args.scales:
            start = load_start(args.start or args.output, seed, s)
            for disc in [None] if cue_for is None else args.discs:
                cue = None if disc is None else cue_for(disc)
                raw = tissue_world(
                    tissue, seed, s, start, end_step=end_step, observed=observed,
                    backend=args.backend, cue=cue,
                )  # fmt: skip
                spec = parse_spec(raw)
                wid = len(members) + 1
                members.append(WorldSpec(wid, spec))
                meta[wid] = dict(seed=seed, s=s, **world_meta(spec, tissue, disc))
    return BatchSpec(tuple(members), len(members), 2**53 - 1, 2**53 - 1), meta


def stationarity(spec, checkpoint, tissue):
    """The law's derivative at a checkpoint: rates per cell, drift over the run's length."""
    from cells.core.surface_pump_v3_spec import control_values
    from cells.models import surface_pump_v3 as model

    state = model.STATE_TYPE(*(np.asarray(v) for v in checkpoint.state))
    p = type(checkpoint.layout)(*(np.asarray(v) for v in checkpoint.layout))
    controls = control_values(spec, [checkpoint.time])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    values = model.readouts(state, control, p, xp=np)
    rate = values.derivative
    n = tissue.cells
    ids = list(spec.model.species_ids)
    amounts, _ = model.physical_amounts(state, p)
    dc = np.asarray(rate.amount_increment)[:, :n] / tissue.volume_pL  # mM/s
    dq = CHARGE_PER_FMOL * np.sum(
        np.asarray(p.valence).reshape(-1, 1) * np.asarray(rate.amount_increment)[:, :n], axis=0
    )
    capacitance = np.bincount(
        tissue.owner, weights=np.asarray(p.membrane_capacitance)[: len(tissue.owner)], minlength=n
    )
    vm = np.asarray(values.field.rates.membrane_voltage_V)[: len(tissue.owner)] @ tissue.average
    horizon = (BASELINE_STEPS + RETENTION_STEPS) * DT
    conc = np.asarray(amounts)[:, :n] / tissue.volume_pL
    relative = np.abs(dc) / conc
    gate_rate = np.asarray(rate.channel_gate)
    return dict(
        time_s=checkpoint.time,
        valid=bool(values.valid),
        vm_range_V=[float(vm.min()), float(vm.max())],
        all_H=bool(np.all(vm < THRESHOLD_V)),
        max_abs_dvm_dt_V_per_s=float(np.max(np.abs(dq / capacitance))),
        max_abs_dc_dt_mM_per_s={k: float(np.max(np.abs(dc[ids.index(k)]))) for k in MOBILE},
        max_relative_dc_dt_per_s={k: float(np.max(relative[ids.index(k)])) for k in MOBILE},
        max_abs_channel_gate_rate_per_s=float(np.max(np.abs(gate_rate))),
        max_abs_junction_gate_rate_per_s=float(np.max(np.abs(np.asarray(rate.junction_gate)))),
        projected_over_run=dict(
            horizon_s=horizon,
            vm_drift_mV=1e3 * horizon * float(np.max(np.abs(dq / capacitance))),
            relative_composition_drift=horizon
            * float(np.max(relative[[ids.index(k) for k in MOBILE]])),
        ),
    )


# Stationarity accepted (fixed before the preparation ran): over the 210 s of
# baseline and retention, each cell's Vm would drift by at most 1 mV and each
# mobile ion's concentration by at most 0.5%, from the derivative at the end.
STATIONARY_VM_DRIFT_MV = 1.0
STATIONARY_RELATIVE_DRIFT = 0.005


def part_prepare(args):
    from cells.batch_io import write_batch_snapshot
    from cells.core.windows import WindowPolicy

    tissue = Tissue()
    output = Path(args.output) / "prepare"
    output.mkdir(parents=True, exist_ok=True)
    end = prepare_steps(args)
    observed = sorted({*range(0, end, 1000), *range(0, min(end, 2000), 20), end})
    tick = time.perf_counter()
    spec, meta = prepare_worlds(args, tissue, end_step=end, observed=observed)
    report = dict(
        kind="cells.heredity_pilot_w1_prepare@1",
        steps=end,
        worlds={str(w): dict(seed=m["seed"], s=m["s"]) for w, m in meta.items()},
        definition_seconds=time.perf_counter() - tick,
        criterion=dict(vm_drift_mV=STATIONARY_VM_DRIFT_MV, relative=STATIONARY_RELATIVE_DRIFT),
    )
    write_json(output / "prepare.json", report)
    observer = Observer(tissue, meta, output / "records")
    tick = time.perf_counter()
    result, failure = run_batch(spec, WindowPolicy(WINDOW_STEPS, "checkpoints"), observer)
    report["run_wall_seconds"] = time.perf_counter() - tick
    report["resources"] = resources()
    if failure is not None:
        report["failure"] = failure
        write_json(output / "prepare.json", report)
        write_json(output / "failure.json", failure)
        return 1
    report.update(timings=result.timings, batch_resources=dict(result.resources))
    checkpoints = result.checkpoints
    report["stationarity"] = {}
    for world in spec.worlds:
        value = stationarity(world.simulation, checkpoints[world.world_id], tissue)
        value["accepted"] = bool(
            value["all_H"]
            and value["projected_over_run"]["vm_drift_mV"] <= STATIONARY_VM_DRIFT_MV
            and value["projected_over_run"]["relative_composition_drift"]
            <= STATIONARY_RELATIVE_DRIFT
        )
        report["stationarity"][str(world.world_id)] = value
        arm = meta[world.world_id]
        log(f"prepare {arm_label(arm['seed'], arm['s'])}: {value['projected_over_run']}")
    write_json(output / "prepare.json", report)
    tick = time.perf_counter()
    write_batch_snapshot(output / "snapshot", spec, checkpoints)
    report["snapshot_seconds"] = time.perf_counter() - tick
    write_json(output / "prepare.json", report)
    return 0


def run_steps(args, prepared):
    on = prepared + int(round(args.baseline_seconds / DT))
    off = on + int(round(args.cue_seconds / DT))
    end = off + int(round(args.retention_seconds / DT))
    return on, off, end


# Pre-registered expectations from pre-screens 7 and 8 (simplified held-bath sheets,
# discs started from their stationary D state), recorded before the full run and
# written unchanged to the output directory. Nothing is judged against them here.
PREDICTIONS = dict(
    kind="cells.heredity_pilot_w1_predictions@1",
    status="pre-registered before the 16-world run; development pilot, not judged",
    sources=[
        "/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-07-stationary/summary.md",
        "/mnt/workspaces/Cells/heredity-design-20261108-01/prescreen-08-conversion/summary.md",
    ],
    arms={
        "s1-disc19": "written disc lost within about 1 s after the cue ends (pre-screen 7 "
        "transient from the written D state: first D lost by 0.5 s, none left by 1 s; no "
        "stationary or frozen-composition disc at theta 1.657)",
        "s1-disc37": "written disc lost within 30-60 s after the cue ends (pre-screen 7: settles "
        "on the frozen-composition disc within 0.5 s, all D at 30 s, none left by 60 s); "
        "10% CV heterogeneity lowers the 37-cell edge to theta 1.434 (still absent at 1.657)",
        "s0.3-disc19": "held for the 180 s retention (stable stationary disc up to s 0.661)",
        "s0.3-disc37": "held for the 180 s retention (stable stationary disc up to s 0.922; "
        "10% CV lowers that by about 6%)",
    },
    spontaneous_D_outside_disc="none (uniform H stable at both arms and both gatings)",
    caveats=[
        "the pre-screens start discs at their stationary D composition; the cue writes from "
        "the H composition, so the released disc carries H-like ion contents",
        "the full tissue adds finite extracellular squares, extracellular potentials and "
        "per-cell areas; theta is matched for interior cells only",
    ],
)


def observation_steps_run(start, on, off, end):
    steps = {0, *range(start, on, 1000)}
    steps |= set(range(on - 500, off, 20)) | set(range(off, min(off + 3000, end), 20))
    steps |= set(range(off + 3000, min(off + 15000, end), 100))
    steps |= set(range(off + 15000, end, 500))
    return sorted(k for k in steps | {end} if 0 <= k <= end)


def part_run(args):
    from cells.batch_io import load_batch_snapshot
    from cells.core.windows import WindowPolicy

    tissue = Tissue()
    output = Path(args.output) / ("run" if args.label is None else f"run-{args.label}")
    output.mkdir(parents=True, exist_ok=True)
    base = Path(args.prepared or args.output) / "prepare"
    prepared = load_batch_snapshot(base / "snapshot")
    arms = json.loads((base / "prepare.json").read_text())["worlds"]
    steps = {prepared.checkpoints[w.world_id].step_index for w in prepared.spec.worlds}
    if len(steps) != 1:
        raise ValueError("Preparations end at different steps")
    first = steps.pop()
    on, off, end = run_steps(args, first)
    observed = observation_steps_run(first, on, off, end)
    tick = time.perf_counter()
    spec, meta = prepare_worlds(
        args, tissue, end_step=end, observed=observed, cue_for=lambda disc: (disc, on, off)
    )
    # Each (seed, s) preparation starts both disc arms (same layout: the cue
    # populations exist in both, at availability 0 until the cue).
    by_arm = {
        (arms[str(w.world_id)]["seed"], arms[str(w.world_id)]["s"]): prepared.checkpoints[
            w.world_id
        ]
        for w in prepared.spec.worlds
    }
    checkpoints = {wid: by_arm[(m["seed"], m["s"])] for wid, m in meta.items()}
    records, report_path = output / "records", output / "run.json"
    if args.resume:  # Continue from a complete cohort snapshot of this run.
        snapshot = load_batch_snapshot(args.resume)
        if snapshot.spec.fingerprint != spec.fingerprint:
            raise ValueError("The resume snapshot holds other definitions")
        checkpoints = dict(snapshot.checkpoints)
        label = f"from-t{next(iter(checkpoints.values())).time:09.3f}"
        records, report_path = output / f"records-{label}", output / f"run-{label}.json"
    if not (output / "predictions.json").exists():
        write_json(output / "predictions.json", PREDICTIONS)
    report = dict(
        kind="cells.heredity_pilot_w1_run@1",
        resumed_from=args.resume,
        phases_s=dict(
            preparation_end=first * DT,
            cue_on=on * DT,
            cue_off=off * DT,
            end=end * DT,
            baseline=(on - first) * DT,
            cue=(off - on) * DT,
            retention=(end - off) * DT,
        ),
        observations_per_world=len([k for k in observed if k >= first]),
        worlds={
            str(w): dict(seed=m["seed"], s=m["s"], disc_cells=m["disc"]) for w, m in meta.items()
        },
        definition_seconds=time.perf_counter() - tick,
        window_steps=WINDOW_STEPS,
    )
    write_json(report_path, report)
    definitions = output / "definitions"
    definitions.mkdir(exist_ok=True)
    for world in spec.worlds:
        path = definitions / f"world-{world.world_id}.json"
        if not path.exists():
            path.write_text(json.dumps(world.simulation.to_dict()) + "\n")
    marks = [on, off, off + 30_000, off + 90_000]
    observer = Observer(
        tissue,
        meta,
        records,
        snapshots=[k * DT for k in marks if first < k < end],
        batch=spec,
    )
    tick = time.perf_counter()
    result, failure = run_batch(
        spec, WindowPolicy(WINDOW_STEPS, "checkpoints"), observer, checkpoints
    )
    report["run_wall_seconds"] = time.perf_counter() - tick
    report["resources"] = resources()
    if failure is not None:
        report["failure"] = failure
        write_json(report_path, report)
        write_json(output / f"failure-{int(time.time())}.json", failure)
        return 1
    report.update(timings=result.timings, batch_resources=dict(result.resources))
    report["diagnostics"] = {str(k): w.diagnostics for k, w in result.worlds.items()}
    world_steps = sum(w.resources["executed_steps"] for w in result.worlds.values())
    report["cost"] = dict(
        world_steps=world_steps,
        wall_ms_per_world_step=1e3 * report["run_wall_seconds"] / world_steps,
        compile_seconds=result.timings.get("compile_seconds"),
        execute_seconds=result.timings.get("execute_seconds"),
        host_analysis_seconds=result.timings.get("analysis_seconds"),
        sink_seconds=result.timings.get("sink_seconds"),
    )
    write_json(report_path, report)
    final = {w: c for w, c in result.checkpoints.items()}
    report["final_stationarity"] = {
        str(w.world_id): stationarity(w.simulation, final[w.world_id], tissue) for w in spec.worlds
    }
    write_json(report_path, report)
    return 0


def _records(directory, world):
    """A world's observation rows from the run and any resumed segments, by time."""
    rows = {}
    for path in sorted(Path(directory).glob(f"records*/world-{world}.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["t"]] = row
    return [rows[t] for t in sorted(rows)]


def _bracket(rows, start, test):
    """(last time not meeting test, first time meeting it) after start, in s from start."""
    previous = None
    for r in rows:
        if r["t"] < start - 1e-9:
            continue
        if test(r):
            return [None if previous is None else previous - start, r["t"] - start]
        previous = r["t"]
    return None


def world_outcome(rows, disc, phases):
    on, off = phases["cue_on"], phases["cue_off"]
    baseline = [r for r in rows if r["t"] < on - 1e-9]
    cue = [r for r in rows if on - 1e-9 <= r["t"] < off - 1e-9]
    after = [r for r in rows if r["t"] >= off - 1e-9]
    at_off = after[0] if after else None
    written = bool(at_off and at_off["d_inside"] == disc and at_off["d_outside"] == 0)
    marks = (0, 0.5, 1, 2, 5, 10, 20, 30, 45, 60, 90, 120, 150, 180)
    timeline = {}
    for m in marks:
        row = next((r for r in after if r["t"] >= off + m - 1e-9), None)
        if row is not None:
            timeline[f"{m:g}"] = dict(d_inside=row["d_inside"], d_outside=row["d_outside"])
    return dict(
        observations=len(rows),
        baseline_max_d=max((r["d_inside"] + r["d_outside"] for r in baseline), default=None),
        baseline_vm_V=[
            min((r["outside_vm_V"][0] for r in baseline), default=None),
            max((max(r["outside_vm_V"][1], r["disc_vm_V"][1]) for r in baseline), default=None),
        ],
        all_disc_D_under_cue_bracket_s=_bracket(cue, on, lambda r: r["d_inside"] == disc),
        d_inside_at_cue_off=at_off and at_off["d_inside"],
        d_outside_at_cue_off=at_off and at_off["d_outside"],
        disc_mean_at_cue_off_mM=at_off and at_off["disc_mean_mM"],
        disc_squares_at_cue_off_mM=at_off and at_off["disc_squares_mean_mM"],
        written=written,
        first_D_lost_bracket_s=_bracket(after, off, lambda r: r["d_inside"] < disc),
        all_D_lost_bracket_s=_bracket(after, off, lambda r: r["d_inside"] == 0),
        max_d_outside_after_cue=max((r["d_outside"] for r in after), default=None),
        outside_D_cells_seen=sorted({c for r in rows for c in r.get("d_outside_cells", [])}),
        d_inside_at_end=rows[-1]["d_inside"] if rows else None,
        last_time_s=rows[-1]["t"] if rows else None,
        timeline_after_cue_off=timeline,
    )


def part_summarize(args):
    output = Path(args.output) / ("run" if args.label is None else f"run-{args.label}")
    run = json.loads((output / "run.json").read_text())
    phases = run["phases_s"]
    worlds_, arms = {}, {}
    for wid, w in run["worlds"].items():
        value = world_outcome(_records(output, wid), w["disc_cells"], phases)
        worlds_[wid] = dict(w, **value)
        arms.setdefault(f"s{w['s']:g}-disc{w['disc_cells']}", []).append(wid)
    summary = dict(
        kind="cells.heredity_pilot_w1_results@1",
        phases_s=phases,
        predictions=json.loads((output / "predictions.json").read_text()),
        worlds=worlds_,
        arms={
            arm: dict(
                worlds=ids,
                written=sum(worlds_[i]["written"] for i in ids),
                first_D_lost_bracket_s=[worlds_[i]["first_D_lost_bracket_s"] for i in ids],
                all_D_lost_bracket_s=[worlds_[i]["all_D_lost_bracket_s"] for i in ids],
                d_inside_at_end=[worlds_[i]["d_inside_at_end"] for i in ids],
                max_d_outside_after_cue=[worlds_[i]["max_d_outside_after_cue"] for i in ids],
            )
            for arm, ids in sorted(arms.items())
        },
        cost=run.get("cost"),
        failure=run.get("failure"),
    )
    write_json(output / "results.json", summary)
    lines = [
        "| world | seed | s | disc | written | D at cue off (in/out) | first D lost (s after "
        "cue off) | all lost | D at end | max D outside after cue |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for wid, w in sorted(worlds_.items(), key=lambda kv: int(kv[0])):
        lines.append(
            f"| {wid} | {w['seed']} | {w['s']:g} | {w['disc_cells']} | {w['written']} | "
            f"{w['d_inside_at_cue_off']}/{w['d_outside_at_cue_off']} | "
            f"{w['first_D_lost_bracket_s']} | {w['all_D_lost_bracket_s']} | "
            f"{w['d_inside_at_end']} | {w['max_d_outside_after_cue']} |"
        )
    (output / "results.md").write_text("\n".join(lines) + "\n")
    log("results written")


def part_heat(args):
    """Diagnostic: per-step route-heat increments from the run's cue-on snapshot.

    The vectorized run refuses a world whose dissipation ledger decreases by more
    than surface_pump_checks.DISSIPATION_ATOL_PJ in a step. This replays the
    engine's own checked step (models/surface_pump_v3.checked_step, unmodified,
    no runner checks) from the cue-on cohort snapshot through the cue and after
    it, and records each step's negative increments of every dissipation field
    (how many routes, the most negative value, the worst junction's cells), the
    model's own device checks on every replayed row (models/surface_pump_v3.
    device_checks: which checks fail and where), and at each 0.1 s the disc's D
    counts. Evidence only: an unchecked replay is not a run of the experiment.
    """
    import jax.numpy as jnp

    from cells.batch_io import load_batch_snapshot
    from cells.core.surface_pump_v3_spec import control_values
    from cells.models import surface_pump_v3 as model
    from cells.models.surface_pump_checks import DISSIPATION_ATOL_PJ

    tissue = Tissue()
    output = Path(args.output) / ("run" if args.label is None else f"run-{args.label}")
    run = json.loads((output / "run.json").read_text())
    on, off = run["phases_s"]["cue_on"], run["phases_s"]["cue_off"]
    snapshot = load_batch_snapshot(output / "snapshots" / f"t{on:09.3f}")
    steps = int(round((off - on) / DT)) + int(round(args.heat_after_seconds / DT))
    report = dict(
        kind="cells.heredity_pilot_w1_heat@1",
        snapshot=str(output / "snapshots" / f"t{on:09.3f}"),
        tolerance_pJ=DISSIPATION_ATOL_PJ,
        steps=steps,
        worlds={},
    )
    fields = model.DISSIPATION_FIELDS
    names = ["heat.json", *(f"heat-{k:02d}.json" for k in range(2, 100))]
    name = next(n for n in names if not (output / n).exists())  # Never overwrite a replay.

    def advance(state, control, p, constants, index):
        def body(carry, _):
            y, n = carry
            new, ok = model.checked_step(y, DT, control, p, p.active)
            failed, _ = model.device_checks(y, new, p, constants, n + 1)
            change = [getattr(new, k) - getattr(y, k) for k in fields]
            low = jnp.stack([jnp.min(c) for c in change])
            count = jnp.stack([jnp.sum(c < -DISSIPATION_ATOL_PJ) for c in change])
            j = new.junction_dissipated_energy_pJ - y.junction_dissipated_energy_pJ
            return (new, n + 1), (ok, low, count, jnp.argmin(j), failed)

        return jax.lax.scan(body, (state, index), None, length=chunk)

    chunk = 100
    compiled = jax.jit(advance)
    for world in snapshot.spec.worlds:
        spec, checkpoint = world.simulation, snapshot.checkpoints[world.world_id]
        p = type(checkpoint.layout)(*(jnp.asarray(v) for v in checkpoint.layout))
        state = model.STATE_TYPE(*(jnp.asarray(v) for v in checkpoint.state))
        constants = jax.tree.map(jnp.asarray, model.device_check_constants(spec))
        host = type(checkpoint.layout)(*(np.asarray(v) for v in checkpoint.layout))
        disc = np.zeros(tissue.cells, dtype=bool)
        disc[tissue.disc(run["worlds"][str(world.world_id)]["disc_cells"])] = True
        events, refused, checks, counts = [], None, {}, []
        first, cue_end = int(round(checkpoint.time / DT)), int(round(off / DT))
        for n in range(-(-steps // chunk)):
            k0 = first + n * chunk
            t = k0 * DT  # Chunk start on the grid (integer steps: no accumulated rounding).
            if k0 < cue_end < k0 + chunk:
                raise ValueError("Diagnostic chunks must not straddle the cue end")
            controls = control_values(spec, [t])
            control = type(controls)(*(jnp.asarray(v[0]) for v in controls))
            (state, _), outputs = compiled(state, control, p, constants, jnp.asarray(k0))
            ok, low, count, worst, failed = (np.asarray(v) for v in outputs)
            for c, check in enumerate(model.DEVICE_CHECKS):
                rows = np.flatnonzero(failed[:, c])
                if len(rows):
                    entry = checks.setdefault(check, dict(rows=0, first_s=None))
                    entry["rows"] += int(len(rows))
                    entry["first_s"] = entry["first_s"] or (k0 + int(rows[0]) + 1) * DT
            row = model.STATE_TYPE(*(np.asarray(v) for v in state))
            end = control_values(spec, [(k0 + chunk) * DT])
            values = model.readouts(row, type(end)(*(np.asarray(v[0]) for v in end)), host, xp=np)
            vm = np.asarray(values.field.rates.membrane_voltage_V)[: len(tissue.owner)]
            d = vm @ tissue.average > THRESHOLD_V
            counts.append([(k0 + chunk) * DT, int(d[disc].sum()), int(d[~disc].sum())])
            if not ok.all():
                refused = (k0 + int(np.argmin(ok)) + 1) * DT
                break
            for k in np.flatnonzero(count.sum(axis=1)):
                j = int(worst[k])
                events.append(
                    dict(
                        step_end_s=(k0 + int(k) + 1) * DT,
                        counts={f: int(c) for f, c in zip(fields, count[k], strict=True) if c},
                        min_increment_pJ={
                            f: float(v) for f, v in zip(fields, low[k], strict=True) if v < 0
                        },
                        worst_junction=j,
                        worst_junction_cells=list(tissue.pairs[j]),
                        worst_junction_rings=[int(tissue.ring[c]) for c in tissue.pairs[j]],
                    )
                )
        report["worlds"][str(world.world_id)] = dict(
            seed=run["worlds"][str(world.world_id)]["seed"],
            s=run["worlds"][str(world.world_id)]["s"],
            disc_cells=run["worlds"][str(world.world_id)]["disc_cells"],
            steps_with_decrease=len(events),
            refused_at_s=refused,
            failed_device_checks=checks,
            d_counts_t_inside_outside=counts,
            events=events[:200],
            event_times_s=[e["step_end_s"] for e in events],
        )
        log(f"heat world {world.world_id}: {len(events)} steps with a decrease")
        write_json(output / name, report)


def part_gapa(args):
    """Measurements for the junction-heat refusal (no engine change; evidence only).

    On the refused step of a run (its cue-on snapshot, first step): per junction
    the booked heat increment, the explicit stage powers q1 (start) and q2 (at
    gamma dt) of ARS(2,2,2), whose weights are (delta, 1 - delta) with delta < 0,
    and the alternatives:
      (a) face-like: dt 1e-3 sum_s J_app^2 dmu_1 / J_1 (J_app the step's booked
          flux, dmu_1 / J_1 the start stage's resistance), nonnegative;
      (b) nonnegative stage weights: dt q1, dt q2, and dt (q1 + q_end) / 2 with
          q_end the end state's power (trapezoid);
      (c) the derived bound increment >= delta dt q1 per route.
    The energy ledger's defect under (a) and (b) is the sum of (alternative -
    booked) over junctions for this step, set against the row's energy residual
    and bound (surface_pump.ledger_limits). Then, on the seeded-fault fixture of
    tests/unit/test_surface_pump_v3_device_checks.py and test_surface_pump_device_
    checks.py, the allowance (c) would give each seeded route at the seeded row.
    """
    from cells.batch_io import load_batch_snapshot
    from cells.core.surface_pump_v3_spec import control_values
    from cells.models import surface_pump as first
    from cells.models import surface_pump_v3 as model
    from cells.models.surface_pump_checks import DISSIPATION_ATOL_PJ
    from cells.numerics import surface_imex as imex

    tableau = imex.TABLEAUX[imex.ARS222_ID].explicit
    delta, weights = float(tableau[2, 0]), np.asarray(tableau[2, :2], dtype=float)
    output = Path(args.output) / ("run" if args.label is None else f"run-{args.label}")
    run = json.loads((output / "run.json").read_text())
    on = run["phases_s"]["cue_on"]
    snapshot = load_batch_snapshot(output / "snapshots" / f"t{on:09.3f}")
    tissue = Tissue()
    report = dict(
        kind="cells.heredity_pilot_w1_gap_a@1",
        snapshot=str(output / "snapshots" / f"t{on:09.3f}"),
        tableau_weights=weights.tolist(),
        delta=delta,
        dissipation_atol_pJ=DISSIPATION_ATOL_PJ,
        energy_rtol=first.ENERGY_RTOL[imex.ARS222_ID],
        worlds={},
    )
    for world in snapshot.spec.worlds:
        spec, checkpoint = world.simulation, snapshot.checkpoints[world.world_id]
        state = model.STATE_TYPE(*(np.asarray(v) for v in checkpoint.state))
        p = type(checkpoint.layout)(*(np.asarray(v) for v in checkpoint.layout))
        controls = control_values(spec, [checkpoint.time])
        control = type(controls)(*(np.asarray(v[0]) for v in controls))
        new, ok, stages = _instrumented_step_at(model, state, control, p, DT)
        start = model.readouts(state, control, p, xp=np)
        end = model.readouts(new, control, p, xp=np)
        q1, q2 = (np.asarray(s.junction_dissipated_energy_pJ) for s in stages[:2])
        q_end = np.asarray(end.derivative.junction_dissipated_energy_pJ)
        booked = new.junction_dissipated_energy_pJ - state.junction_dissipated_energy_pJ
        flux = np.asarray(start.field.rates.junction_flux_fmol_s)
        mu = np.asarray(start.field.rates.junction_delta_mu_J_mol)
        applied = (new.junction_transferred - state.junction_transferred) / DT
        resistance = np.where(flux != 0, mu / np.where(flux != 0, flux, 1.0), 0.0)
        alternatives = {
            "a_face_like": DT * 1e-3 * np.sum(applied * applied * resistance, axis=0),
            "b_start_stage": DT * q1,
            "b_gamma_stage": DT * q2,
            "b_trapezoid_end": DT * 0.5 * (q1 + q_end),
        }
        bound_c = delta * DT * q1
        active = np.asarray(p.junction_active)
        negative = np.flatnonzero(active & (booked < -DISSIPATION_ATOL_PJ))
        steps = checkpoint.step_index + 1
        _, bounds = first.ledger_limits(
            new,
            p,
            np.asarray(spec.execution.material_balance_atol_fmol),
            first.ENERGY_RTOL[spec.execution.solver],
            steps=steps,
            magnitudes=model.channel_magnitudes(new, p, xp=np),
            xp=np,
        )
        energy = float(model.balances(new, p)["energy"])
        energy_bound = float(bounds[first.LEDGERS.index("energy")])
        value = dict(
            step=[checkpoint.time, checkpoint.time + DT],
            step_valid=ok,
            tableau_reproduces_booking_max_abs_pJ=float(
                np.max(np.abs(booked - DT * (weights[0] * q1 + weights[1] * q2)))
            ),
            negative_junctions=[
                dict(
                    junction=int(j),
                    cells=list(tissue.pairs[j]),
                    rings=[int(tissue.ring[c]) for c in tissue.pairs[j]],
                    booked_pJ=float(booked[j]),
                    q1_pJ_s=float(q1[j]),
                    q2_pJ_s=float(q2[j]),
                    q_end_pJ_s=float(q_end[j]),
                    bound_c_pJ=float(bound_c[j]),
                    margin_over_bound_c_pJ=float(booked[j] - bound_c[j]),
                    vj_start_mV=1e3 * float(np.asarray(start.field.rates.junction_voltage_V)[j]),
                    vj_end_mV=1e3 * float(np.asarray(end.field.rates.junction_voltage_V)[j]),
                    **{f"{k}_pJ": float(v[j]) for k, v in alternatives.items()},
                )
                for j in negative
            ],
            bound_c_all_junctions=dict(
                min_margin_pJ=float(np.min((booked - bound_c)[active])),
                violations=int(np.sum((booked - bound_c)[active] < 0)),
            ),
            booked_step_heat_pJ=float(np.sum(booked[active])),
            energy_residual_pJ=energy,
            energy_bound_pJ=energy_bound,
            defect_per_step_pJ={
                k: float(np.sum((v - booked)[active])) for k, v in alternatives.items()
            },
            alternatives_min_pJ={k: float(np.min(v[active])) for k, v in alternatives.items()},
        )
        report["worlds"][str(world.world_id)] = value
        log(
            f"gap A world {world.world_id}: {len(negative)} negative, {value['defect_per_step_pJ']}"
        )
        write_json(output / "gap_a.json", report)
    report["seeded_faults"] = seeded_fault_allowances(delta)
    write_json(output / "gap_a.json", report)


def seeded_fault_allowances(delta):
    """The (c) allowance on the routes the dissipation-fault tests seed, at their row.

    tests/unit/test_surface_pump_v3_device_checks.py seeds a 2e-12 pJ decrease of
    face 0's heat and of the Kv1.5 population's heat at ROW = 5 of the clamped
    eight-population IMEX run (end 1.2 ms); test_surface_pump_device_checks.py
    seeds the face decrease. Here the allowance |delta| dt q1 of each seeded route
    is evaluated at the seeded step's start row, for (c) applied to the routes
    whose heat the tableau books (membrane, junction, channel, pump) - faces book
    J^2 RT / W >= 0 and keep the strict test either way.
    """
    from cells.core.runner import run
    from cells.core.surface_pump_v3_spec import control_values
    from cells.models import surface_pump_v3 as model
    from cells.numerics import surface_imex as imex
    from validation.tissue import surface_pump_v3_fixtures as fixtures

    raw = fixtures.definition("clamped", solver=imex.ARS222_ID, backend="cpu")
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0012]
    spec = parse_spec(raw)
    value = run(spec)
    history = model.STATE_TYPE(*(np.asarray(v) for v in value.history))
    _, p = model.initial_values(spec)
    p = type(p)(*(np.asarray(v) for v in p))
    row, seeded = 5, 2e-12
    times = np.asarray(value.times)
    dt = float(times[row] - times[row - 1])
    controls = control_values(spec, [float(times[row - 1])])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    previous = model.STATE_TYPE(*(v[row - 1] for v in history))
    _, _, stages = _instrumented_step_at(model, previous, control, p, dt)
    q1 = stages[0]
    kv = 0  # channel_0, the fixture's first Kv1.5 population (the test's kv)
    allowance = dict(
        channel_kv15=abs(delta)
        * dt
        * float(np.max(np.asarray(q1.channel_dissipated_energy_pJ)[:, kv])),
        face_0_if_tableau_booked=abs(delta)
        * dt
        * float(
            np.asarray(
                model.readouts(previous, control, p, xp=np).derivative.face_dissipated_energy_pJ
            )[0]
        ),
        junctions_max=abs(delta)
        * dt
        * float(np.max(np.asarray(q1.junction_dissipated_energy_pJ), initial=0.0)),
    )
    return dict(
        fixture="validation/tissue/surface_pump_v3_fixtures.definition('clamped'), ARS(2,2,2), "
        "end 1.2 ms (the tests' runs['clamped'])",
        row=row,
        dt_s=dt,
        seeded_decrease_pJ=seeded,
        allowance_pJ=allowance,
        still_trips={k: seeded > v for k, v in allowance.items()},
    )


def _instrumented_step_at(model, state, control, p, dt):
    """One declared IMEX step on the host, with each explicit stage's rates recorded.

    models/surface_pump_v3.imex_step is run unchanged (xp=numpy); its module-level
    explicit_rates is wrapped for the call only, to copy the stage rates out.
    """
    stages, original = [], model.explicit_rates

    def recording(*args, **kwargs):
        rates, ok = original(*args, **kwargs)
        stages.append(rates)
        return rates, ok

    model.explicit_rates = recording
    try:
        new, ok = model.imex_step(state, dt, control, p, xp=np)
    finally:
        model.explicit_rates = original
    return new, bool(ok), stages


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("parts", nargs="+", choices=sorted(PARTS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--start", help="directory holding start/ (default output)")
    parser.add_argument("--prepared", help="directory holding prepare/ (default output)")
    parser.add_argument("--backend", default="gpu")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    parser.add_argument("--scales", type=float, nargs="+", default=list(SCALES))
    parser.add_argument("--discs", type=int, nargs="+", default=list(DISCS))
    parser.add_argument("--prepare-seconds", type=float, default=20.0)
    parser.add_argument("--baseline-seconds", type=float, default=BASELINE_STEPS * DT)
    parser.add_argument("--cue-seconds", type=float, default=2.0)
    parser.add_argument("--retention-seconds", type=float, default=RETENTION_STEPS * DT)
    parser.add_argument("--resume", help="a run snapshot directory to continue from")
    parser.add_argument("--label", help="run subdirectory suffix (pilots)")
    parser.add_argument("--sheet-after-seconds", type=float, default=SHEET_AFTER_STEPS * DT)
    parser.add_argument("--heat-after-seconds", type=float, default=3.0)
    parser.add_argument("--dt", type=float, default=DT, help="longsheet step (s)")
    parser.add_argument("--long-end-seconds", type=float, default=LONG_END_S)
    args = parser.parse_args(argv)
    Path(args.output).mkdir(parents=True, exist_ok=True)
    status = 0
    for name in args.parts:
        started = time.perf_counter()
        log(f"part {name}")
        try:
            status |= PARTS[name](args) or 0
        except Exception as error:  # Preserved as evidence; later parts still run.
            status = 1
            write_json(
                Path(args.output) / f"{name}.failure.json",
                dict(error=repr(error), traceback=traceback.format_exc()),
            )
            log(f"part {name} failed: {error!r}")
        log(f"part {name} done in {time.perf_counter() - started:.1f} s")
    return status


PARTS = dict(
    map=part_map,
    cue=part_cue,
    sheet=part_sheet,
    start=part_start,
    prepare=part_prepare,
    run=part_run,
    summarize=part_summarize,
    heat=part_heat,
    gapa=part_gapa,
    longsheet=part_longsheet,
)

if __name__ == "__main__":
    sys.exit(main())
