"""Gap-junction cancer replication driver: development work, not a judged comparison (D138).

The preprint (paper.CITATION) runs a bioelectric/GRN tissue model in BITSEY (Tables 1-3) and a
linear "intuitive model" analysed by hand (equations 1-2, appendix, Figures 3, 5 and 8). This
driver runs in Cells what the engine can run today and records, from the engine itself, why the
rest cannot run yet. It changes no engine source.

Parts:
* refusals: definition-time evidence (no integration).
  - A neutral species made in each cell by local_species_reactions@1 that also crosses a junction
    (the preprint's miRNA), against the same world without the junction route.
  - The EMT switch written as local_species_reactions@1 reactions in one cell (synthetic values):
    whether the declaration is admitted.
  - The junction, channel and pump laws @3 hosts.
  - The field solver's node bound against the preprint's lattices: a two-step shared-bath world
    at the bound must be admitted, and one node over it refused for the bound.
* gate: F3 and F4 measured. The engine's one junction law (its own kinetics, at steady state)
  fitted to Figure 1's Cx45 small-ion curve, and the same law against the miRNA curve.
* figure3: two equal linear cells (unloaded 5 and 10) joined by G_GJ = g G_eq, g = 0.5 ... 50.
* figure5: Figure 5b's lumped model (cell B 4/3 cell A) and Figure 5a's seven-cell network.
* figure8: straight chains of 1-5 and 10 cells, each loaded at its port by two held
  concentrations; the Norton conductance G_eq,n from the two steady states.
* control: figure3 at g = 1 with every junction permeability x1.01, judged against g = 1's
  reference: the comparison must catch it.

The linear cells are the preprint's linear cell through its Norton equivalent (worlds.py): the
model as the preprint writes it, a source and a decay in the cell plus a junction, is itself
refused today (gap F1, the first refusal above).

Criteria, fixed before any run (CRITERIA):
  E1 engine against the dense solve of the same network: relative error <= 1e-9 in every cell;
  E2 steady state: relative change over the last SETTLE_S seconds <= 1e-12 in every cell;
  E3 the probe flux from the engine's own membrane ledger against G_probe (c - held): relative
     error <= 1e-9;
  E4 Figure 8: the engine's G_eq,n against the physical chain's recursion: relative <= 1e-8;
  P1 the closed forms against the preprint's printed or read values, within the reading
     tolerances paper.REPORTED states (a check of the reading, not of the engine; the
     tolerances were set after the closed forms were evaluated);
  P2 Figure 8: the engine's G_eq,n against the recursion Figure 8 plots and against its read
     values (reported: the expected outcome is agreement at n <= 2 and disagreement from n = 3);
  K1 the planted control fails E1 (by more than 1e-6);
  A1 the engine's own run checks pass (material balance and every step check: a run that fails
     one raises, and that arm is recorded as failed while the others go on).

Engine models run: resolved_pump_tissue@3 with constant_field@1 membranes and junctions for one
neutral species, held reservoirs, junction_voltage_relaxation@1 pinned open, closed by
resolved_capacitor_components_current_continuity@1, integrated by
imex_ars222_face_electromigration@1 (worlds.py). Definition probes: local_species_reactions@1 in
resolved_pump_composite@1, and the law registry.

Records. Every arm's run is written by the engine's own writer, cells.io.write_run, under
OUTDIR/worlds/<arm id>/: trajectory.npz (every accepted step, the layout, the observations),
resolved_config.json, checkpoint_final, summary.json and manifest.json, and with them view.json,
the run view (cells.run_view@1) with the prescribed geometry of worlds.geometry, so that a viewer
package can be made from the records without re-running. A refused view is recorded and the run
is written without one.

Usage (from a snapshot root, PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu):
    python -B validation/gap_junction_tissue/run.py OUTDIR [part ...]
results.json is rewritten after every arm.
"""

import json
import math
import platform
import sys
import time
import traceback
from pathlib import Path
from typing import NamedTuple

import jax

jax.config.update("jax_enable_x64", True)

import numpy as np  # noqa: E402

import cells  # noqa: E402,F401
from cells import io, run_view  # noqa: E402
from cells.core import blas_threads, runner  # noqa: E402
from cells.core.specs import ConfigError, parse_spec  # noqa: E402
from validation.gap_junction_tissue import paper, worlds  # noqa: E402

CRITERIA = {
    "E1_engine_vs_dense_rtol": 1e-9,
    "E2_steady_rtol": 1e-12,
    "E3_ledger_flux_rtol": 1e-9,
    "E4_norton_vs_physical_rtol": 1e-8,
    "K1_planted_min_rel_error": 1e-6,
}
FIGURE3_G = (0.5, 1.0, 2.0, 5.0, 10.0, 50.0)
FIGURE5_G = (1.0, 10.0, 50.0)  # Figure 5b runs to 100; 50 keeps the run short.
FIGURE8_N = (1, 2, 3, 4, 5, 10)
FIGURE8_LOADS = (0.5, 2.0)  # Held concentrations at the port (mM); the unloaded value is 1.
PLANTED_SCALE = 1.01
FIXTURE_END_S = 60.0
TIME_MATCH_RTOL = 1e-12
EXPERIMENT = "gap-junction-cancer-linear-network"
RECORDS = None  # OUTDIR/worlds, set by main(); None writes no records (tools that only check).
PARTS = ("fixture", "refusals", "gate", "figure3", "figure5", "figure8", "control")


class Recorder:
    """results.json, rewritten after every arm so that a late failure loses nothing."""

    def __init__(self, path, record):
        self.path, self.data = path, dict(record=record, parts={})

    def part(self, name):
        self.data["parts"][name] = dict(status="running", result={})
        self.save()
        return self.data["parts"][name]["result"]

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=1, default=str))


def reference(network):
    """The dense solve of the same network (paper.linear_steady_state), in SI units."""
    conductance = [size * worlds.G_EQ1_M3_S for _, _, size in network.cells]
    unloaded = [u for _, u, _ in network.cells]
    edges = [(i, j, g * worlds.G_EQ1_M3_S) for _, i, j, g in network.edges]
    probes = [(i, g * worlds.G_EQ1_M3_S, held) for _, i, held, g in network.probes]
    return paper.linear_steady_state(conductance, unloaded, edges, probes)


def _row(times, t):
    k = int(np.argmin(np.abs(times - t)))
    if abs(times[k] - t) > TIME_MATCH_RTOL * max(1.0, abs(t)):
        raise ValueError(f"No accepted time at {t}: nearest {times[k]!r}")
    return k


REPRESENTS = (
    "The Norton-equivalent network of the preprint's linear ('intuitive') model: linear cells "
    "exchanging one neutral species through gap junctions, each cell's generation and decay "
    "carried by a membrane to a reservoir held at its unloaded value (its equations 1-2, appendix, "
    "Figures 3, 5 and 8). The engine refuses the model as written (a source and a decay in the "
    "cell plus a junction route; gap F1). This is not the preprint's tissue simulation (Tables "
    "1-3), which the engine cannot run yet."
)
# The viewer packages (the visualizer's request, 17 November): a recording subset of the fields
# it names, for these arms in this order, kept where every layer's records stay under 1 MB.
VIEWER_FIELDS = (
    "amount_increment",
    "junction_transferred",
    "junction_gate",
    "membrane_voltage_V",
    "junction_voltage_V",
)
VIEWER_ARMS = (
    "fixture-figure3-g1",
    "figure3-g0.5",
    "figure3-g1",
    "figure3-g5",
    "figure5-lumped-g1",
    "figure5-network-g1",
    "figure8-chain1-held0.5",
    "figure8-chain2-held0.5",
    "figure8-chain3-held0.5",
    "figure8-chain5-held0.5",
    "figure8-chain10-held0.5",
)
VIEWER_LAYER_BYTES = 2**20


def source_identity():
    """The execution snapshot this run comes from (SNAPSHOT.json at the working directory, as
    tools/run.sh runs it), or the checkout's revision when run from a checkout."""
    path = Path("SNAPSHOT.json")
    if path.is_file():
        snapshot = json.loads(path.read_text())
        return dict(
            revision=snapshot["git_revision"],
            snapshot=Path.cwd().name,
            clean=not snapshot["selected_status_porcelain_v1_z"],
        )
    return dict(revision=None, snapshot=None, clean=None)


def layer_bytes(directory):
    """Bytes of the saved arrays of each layer of a written run, from its own view.json."""
    view = json.loads((directory / "view.json").read_text())
    with np.load(directory / "trajectory.npz") as arrays:
        sizes = {name: arrays[name].nbytes for name in arrays.files}
    out = {}
    for record in view["records"]:
        out[record["layer"]] = out.get(record["layer"], 0) + sizes.get(record["id"], 0)
    return out


def write_record(result, arm_id, label):
    """The engine's own run record with its run view (module docstring), and for VIEWER_ARMS a
    viewer package of the same run with the recording subset. A view's refusal is recorded and
    the run written without one."""
    if RECORDS is None:
        return None
    labels = dict(id=arm_id, experiment=EXPERIMENT, arm=arm_id, label=label)
    provenance = dict(
        operation="fresh",
        driver="validation/gap_junction_tissue/run.py",
        experiment=EXPERIMENT,
        arm=arm_id,
        citation=paper.CITATION,
        **source_identity(),
    )
    source = (
        "validation/gap_junction_tissue/worlds.py: touching spheres after the preprint's "
        "drawings (Figures 3a, 5a, 7)"
    )
    geometry = worlds.geometry(result.network, source)
    out = {}
    targets = [("record", RECORDS / arm_id, None)]
    if arm_id in VIEWER_ARMS:
        recording = run_view.Recording(fields=VIEWER_FIELDS)
        targets.append(("viewer", RECORDS.parent / "viewer" / arm_id, recording))
    for kind, directory, recording in targets:
        request = run_view.Request(labels, geometry=geometry, recording=recording)
        try:
            io.write_run(directory, result.run, provenance=provenance, view=request)
            out[kind] = dict(directory=str(directory), view="written")
            if kind == "viewer":
                sizes = layer_bytes(directory)
                out[kind].update(
                    layer_bytes=sizes,
                    within_limit=all(v < VIEWER_LAYER_BYTES for v in sizes.values()),
                )
        except run_view.ViewRefused as error:
            io.write_run(directory, result.run, provenance=provenance)
            out[kind] = dict(directory=str(directory), view="refused", refusal=str(error))
        write_run_json(directory, arm_id, result.run.spec, provenance, experiment=None)
    return out


def write_run_json(directory, arm_id, spec, provenance, experiment):
    """run.json beside the engine's files: the revision, the models, the definition's hash, what
    the run represents, and (once the experiment ends) every arm's parameters and readouts."""
    entry = dict(
        format="gap_junction_tissue.run@1",
        status="development run of the engine, not judged (D138)",
        represents=REPRESENTS,
        citation=dict(text=paper.CITATION, doi=paper.DOI_URL),
        revision=provenance.get("revision"),
        snapshot=provenance.get("snapshot"),
        snapshot_clean=provenance.get("clean"),
        models=["resolved_pump_tissue@3"],
        laws=dict(
            membrane_and_junction_route="constant_field@1",
            junction_gate="junction_voltage_relaxation@1 (pinned open)",
            closure="resolved_capacitor_components_current_continuity@1",
            solver=worlds.SOLVER,
        ),
        definition_sha256=spec.fingerprint,
        arm=arm_id,
        experiment=experiment,
    )
    (Path(directory) / "run.json").write_text(json.dumps(entry, indent=1, default=str))


def experiment_summary(data):
    """Each arm's parameters and readouts under the preprint's names (mol/m^3 = mM, mol/s)."""
    parts, arms = data["parts"], []

    def add(arm_id, figure, parameters, result, extra=None):
        readouts = None
        if result.get("status") == "done":
            readouts = {
                "[mR] steady, per cell (mol/m^3)": result["concentration_mM"],
                "reference (dense solve of the same network)": result["reference_mM"],
                "relative error": result["engine_rel_error"],
                **(extra or {}),
            }
        arms.append(
            dict(id=arm_id, figure=figure, parameters=parameters, status=result.get("status"),
                 readouts=readouts, record=result.get("record"))
        )  # fmt: skip

    for name in ("fixture", "figure3"):
        for result in parts.get(name, {}).get("result", {}).get("arms", []):
            g, tag = result.get("g"), ("fixture-" if name == "fixture" else "")
            add(f"{tag}figure3-g{g:g}", "3b",
                {"G_GJ / G_eq": g, "mR_UL0, mR_UL1 (mol/m^3)": [5.0, 10.0]}, result,
                {"equation 2": result.get("eq2")})  # fmt: skip
    figure5 = parts.get("figure5", {}).get("result", {})
    for result in figure5.get("lumped", []):
        add(f"figure5-lumped-g{result['g']:g}", "5b",
            {"G_GJ / G_eq,A": result["g"], "G_eq,B / G_eq,A": 4.0 / 3.0,
             "mR_UL,A, mR_UL,B (mol/m^3)": [10.0, 5.0]}, result,
            {"equation 2": result.get("eq2")})  # fmt: skip
    for result in figure5.get("network", []):
        add(f"figure5-network-g{result['g']:g}", "5a",
            {"G_GJ / G_eq": result["g"], "cells": "A with two backups at 10, B with three at 5"},
            result)  # fmt: skip
    for chain in parts.get("figure8", {}).get("result", {}).get("chains", []):
        for held, result in zip(FIGURE8_LOADS, chain["loads"], strict=False):
            add(f"figure8-chain{chain['n']}-held{held:g}", "8",
                {"cells n": chain["n"], "G_GJ / G_eq,1": 1.0, "mR_UL0 (mol/m^3)": 1.0,
                 "probe held [mR] (mol/m^3)": held, "G_probe / G_eq,1": 1.0}, result,
                {"port [mR] (mol/m^3)": result.get("port_mM"),
                 "i_exit (mol/s)": result.get("exit_flux_mol_s"),
                 "G_eq,n / G_eq,1 (from both loads)": chain.get("g_eq_ratio")})  # fmt: skip
    control = parts.get("control", {}).get("result", {})
    if control:
        planted = {"relative error against the unperturbed solve": control.get("planted_rel_error")}
        parameters = {"G_GJ / G_eq": 1.0, "junction permeability scale": PLANTED_SCALE}
        add("control-planted", "3b (planted control)", parameters, control, planted)
    return dict(id=EXPERIMENT, represents=REPRESENTS, arms=arms)


def finish_records(data):
    """Rewrite every record's run.json with the whole experiment's summary; write the viewer
    index (viewer/index.json) of the packages within the size limit, in VIEWER_ARMS order."""
    if RECORDS is None:
        return
    summary = experiment_summary(data)
    viewer = []
    for arm in summary["arms"]:
        for kind, record in (arm.get("record") or {}).items():
            directory = Path(record["directory"])
            if not (directory / "run.json").is_file():
                continue
            entry = json.loads((directory / "run.json").read_text())
            entry["experiment"] = summary
            (directory / "run.json").write_text(json.dumps(entry, indent=1, default=str))
            if kind == "viewer":
                viewer.append(dict(arm=arm["id"], **record))
    order = {arm_id: k for k, arm_id in enumerate(VIEWER_ARMS)}
    viewer.sort(key=lambda v: order.get(v["arm"], len(order)))
    selected = [v["arm"] for v in viewer if v.get("within_limit")][:10]
    index = dict(experiment=EXPERIMENT, represents=REPRESENTS, layer_limit_bytes=VIEWER_LAYER_BYTES,
                 packages=viewer, selected=selected)  # fmt: skip
    path = RECORDS.parent / "viewer" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=1, default=str))


class Outcome(NamedTuple):
    run: object
    network: object


def run_network(network, *, junction_scale=1.0, end=worlds.END_S, arm_id=None, label=""):
    """Run one linear network to steady state; return the engine's readouts and the reference."""
    cells_, probes = network.cells, network.probes
    raw = worlds.linear_network(
        cells_, network.edges, probes, junction_scale=junction_scale, end=end
    )
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = runner.run(spec)
    seconds = time.perf_counter() - started
    times = np.asarray(result.times)
    end, before = spec.experiment.end_time, spec.experiment.end_time - worlds.SETTLE_S
    rows = {t: _row(times, t) for t in (before, end)}
    layout, history = result.final.layout, result.history
    volume = np.asarray(layout.volume)[: len(cells_)]
    reference_amount = np.asarray(layout.amount_reference)[0, : len(cells_)]

    def concentration(t):
        increment = np.asarray(history.amount_increment[rows[t]])[0, : len(cells_)]
        return (reference_amount + increment) / volume  # fmol / pL = mM

    c_end, c_before = concentration(end), concentration(before)
    c_ref, flux_ref = reference(network)
    out = dict(
        dt_s=spec.execution.dt,
        steps=int(round(end / spec.execution.dt)),
        accepted_rows=int(times.size),
        seconds=seconds,
        concentration_mM=c_end.tolist(),
        reference_mM=c_ref.tolist(),
        engine_rel_error=float(np.max(np.abs(c_end - c_ref) / np.abs(c_ref))),
        steady_rel_change=float(np.max(np.abs(c_end - c_before) / np.abs(c_end))),
        diagnostics={k: float(v) for k, v in result.diagnostics.items() if _number(v)},
    )
    if probes:
        # The probe membrane is the last membrane; its ledger counts cell -> held reservoir.
        slot = len(cells_) + len(probes) - 1
        moved = [np.asarray(history.membrane_transferred[rows[t]])[0, slot] for t in (before, end)]
        ledger = (moved[1] - moved[0]) / worlds.SETTLE_S * 1e-15  # mol/s out of the port cell
        _, i, held, g = probes[-1]
        formula = g * worlds.G_EQ1_M3_S * (c_end[i] - held)  # m^3/s * mol/m^3
        out.update(
            port_mM=float(c_end[i]),
            exit_flux_mol_s=float(ledger),
            exit_flux_formula_mol_s=float(formula),
            exit_flux_reference_mol_s=float(flux_ref[-1]),
            ledger_rel_error=float(abs(ledger - formula) / abs(formula)),
        )
    if arm_id is not None:
        out["record"] = write_record(Outcome(result, network), arm_id, label)
    return out


def arm(network, *, arm_id=None, label="", **kwargs):
    """run_network with its checks, or the failure (recorded as evidence, never retried)."""
    try:
        out = run_network(network, arm_id=arm_id, label=label, **kwargs)
    except Exception as error:
        return dict(status="failed", error=repr(error), traceback=traceback.format_exc())
    out["status"] = "done"
    out["E1"] = out["engine_rel_error"] <= CRITERIA["E1_engine_vs_dense_rtol"]
    out["E2"] = out["steady_rel_change"] <= CRITERIA["E2_steady_rtol"]
    if "ledger_rel_error" in out:
        out["E3"] = out["ledger_rel_error"] <= CRITERIA["E3_ledger_flux_rtol"]
    return out


def _number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _parse(raw):
    try:
        parse_spec(raw)
        return dict(accepted=True)
    except ConfigError as error:
        return dict(accepted=False, refusal=str(error))


def part_refusals(out, save):
    from cells.models.inner_laws import HOST
    from cells.registry import laws as law_registry

    out["with_junction_route"] = _parse(worlds.junction_route_reaction(1e-9))
    out["without_junction_route"] = _parse(worlds.junction_route_reaction(0.0))
    out["emt_switch_reactions"] = _parse(worlds.emt_switch_probe())
    save()
    registry = law_registry.active()
    out["hosted_laws"] = {
        "junction": sorted(law.law_id for law in registry.laws(law_registry.JUNCTION_LAW, HOST)),
        "channel": sorted(law.law_id for law in registry.laws(law_registry.CHANNEL_LAW, HOST)),
        "cycle": sorted(law.law_id for law in registry.laws(law_registry.CYCLE_LAW, HOST)),
    }
    bound = worlds.FIELD_NODE_BOUND
    shapes = {"1D_1x1x25": (1, 1, 25), "2D_1x25x25": (1, 25, 25), "3D_25x25x25": (25, 25, 25)}
    out["field_node_bound"] = bound
    out["preprint_lattices"] = {
        k: dict(nodes=worlds.lattice_nodes(s), within=worlds.lattice_nodes(s) <= bound)
        for k, s in shapes.items()
    }
    out["shared_bath_at_bound"] = dict(cells=bound - 1, **_parse(worlds.shared_bath(bound - 1)))
    out["shared_bath_over_bound"] = dict(cells=bound, **_parse(worlds.shared_bath(bound)))
    route = out["with_junction_route"]
    over = out["shared_bath_over_bound"]
    out["verdict"] = dict(
        junction_route_reaction_refused=not route["accepted"]
        and "route through junction j_0" in route.get("refusal", "")
        and out["without_junction_route"]["accepted"],
        emt_switch_expressible=out["emt_switch_reactions"]["accepted"],
        only_relaxation_junction_law=out["hosted_laws"]["junction"]
        == ["junction_voltage_relaxation@1"],
        three_d_lattice_over_bound=not out["preprint_lattices"]["3D_25x25x25"]["within"]
        and out["shared_bath_at_bound"]["accepted"]
        and not over["accepted"]
        and "dense node bound" in over.get("refusal", ""),
    )
    save()


def part_gate(out, save):
    """F3/F4 measured: the engine's one junction law (its own kinetics, steady target) fitted to
    Figure 1's Cx45 small-ion curve normalized at dV = 0, over the figure's -100..100 mV; then the
    same law, with the same single minimum, against the miRNA curve (floor 0)."""
    from cells.processes import junction_gate

    dv = np.linspace(-0.1, 0.1, 201)
    peak = paper.chen_izu(0.0, paper.CX45_SMALL_ION_GMIN)
    ions = paper.chen_izu(dv, paper.CX45_SMALL_ION_GMIN) / peak
    mirna = paper.chen_izu(dv, 0.0) / peak
    thresholds = np.linspace(0.0, junction_gate.MAX_ABS_VOLTAGE_V, 121)
    minima = np.linspace(0.0, 0.2, 101)
    t, m = np.meshgrid(thresholds, minima, indexing="ij")
    params = junction_gate.Parameters(t[..., None], m[..., None])
    target = junction_gate.kinetics(dv, params, xp=np).target  # [threshold, minimum, dV]
    error = np.max(np.abs(target - ions), axis=-1)
    k = np.unravel_index(np.argmin(error), error.shape)
    best = target[k]
    out.update(
        law=junction_gate.LAW_ID,
        cx45_small_ion_at_0=float(peak),
        cx45_mirna_at_0=float(paper.chen_izu(0.0, 0.0)),
        cx45_floor_small_ion=float(ions[0]),
        best_threshold_V=float(thresholds[k[0]]),
        best_minimum=float(minima[k[1]]),
        max_abs_error_small_ions=float(error[k]),
        max_abs_error_mirna_same_law=float(np.max(np.abs(best - mirna))),
        engine_at_40mV=float(np.interp(0.04, dv, best)),
        cx45_small_ion_at_40mV=float(np.interp(0.04, dv, ions)),
        cx45_mirna_at_40mV=float(np.interp(0.04, dv, mirna)),
    )
    save()


def part_fixture(out, save):
    """A tiny run of the real runs' shape for the viewer's tests (FIXTURE_END_S, not steady)."""
    result = arm(
        worlds.figure3(1.0),
        end=FIXTURE_END_S,
        arm_id="fixture-figure3-g1",
        label="Format fixture: Figure 3 at G_GJ = G_eq, 60 s (not at steady state; no verdict)",
    )
    result.update(g=1.0, eq2=list(paper.eq2(5.0, 10.0, 1.0, 1.0)), purpose="format fixture")
    out["arms"] = [result]
    save()


def part_figure3(out, save):
    rep = paper.REPORTED["figure3b"]
    out["arms"] = []
    for g in FIGURE3_G:
        result = arm(
            worlds.figure3(g, rep["unloaded"]),
            arm_id=f"figure3-g{g:g}",
            label=f"Figure 3: two equal linear cells (unloaded 5 and 10 mM), G_GJ = {g:g} G_eq",
        )
        result.update(g=g, eq2=list(paper.eq2(*rep["unloaded"], g, g)))
        out["arms"].append(result)
        save()
    a1, b1 = paper.eq2(*rep["unloaded"], 1.0, 1.0)
    limit = 0.5 * sum(rep["unloaded"])
    out["reading"] = dict(
        at_g1_closed_form=[a1, b1],
        at_g1_read=list(rep["at_g1"]),
        P1_at_g1=bool(
            max(abs(a1 - rep["at_g1"][0]), abs(b1 - rep["at_g1"][1])) <= rep["tolerance"]
        ),
        limit_closed_form=limit,
        P1_limit=bool(abs(limit - rep["limit"]) <= rep["tolerance"]),
    )
    save()


def part_figure5(out, save):
    rep = paper.REPORTED["figure5"]
    ua, ub = rep["unloaded"]["A"], rep["unloaded"]["B"]
    out["lumped"], out["network"] = [], []
    for g in FIGURE5_G:
        result = arm(
            worlds.figure5_lumped(g, rep["size_ratio"], (ua, ub)),
            arm_id=f"figure5-lumped-g{g:g}",
            label=f"Figure 5b: cell B 4/3 of cell A (unloaded 10 and 5 mM), G_GJ = {g:g} G_eq",
        )
        result.update(g=g, eq2=list(paper.eq2(ua, ub, g, g / rep["size_ratio"])))
        out["lumped"].append(result)
        save()
        result = arm(
            worlds.figure5_network(g, (ua, ub)),
            arm_id=f"figure5-network-g{g:g}",
            label=f"Figure 5a: A with two backup cells, B with three, G_GJ = {g:g} G_eq",
        )
        result.update(g=g)
        out["network"].append(result)
        save()
    limit = (ua + rep["size_ratio"] * ub) / (1.0 + rep["size_ratio"])
    out["reading"] = dict(
        limit_closed_form=limit,
        caption_final=rep["final"],
        P1_final=bool(abs(limit - rep["final"]) <= rep["tolerance"]),
        text_ratio_1p5_limit=(ua + 1.5 * ub) / 2.5,
    )
    save()


def part_figure8(out, save):
    rep = paper.REPORTED["figure8"]
    physical = paper.chain_physical(1.0, 1.0, max(FIGURE8_N))
    plotted = paper.chain_paper(1.0, 1.0, max(FIGURE8_N))
    out.update(
        physical_limit_ratio=paper.chain_limit(1.0, 1.0), recursion_note=paper.RECURSION_NOTE
    )
    out["chains"] = []
    for n in FIGURE8_N:
        entry = dict(n=n, physical_ratio=physical[n - 1], plotted_ratio=plotted[n - 1], loads=[])
        out["chains"].append(entry)
        for held in FIGURE8_LOADS:
            entry["loads"].append(
                arm(
                    worlds.chain(n, held),
                    arm_id=f"figure8-chain{n}-held{held:g}",
                    label=f"Figure 8: a straight chain of {n} linear cells, its port loaded by "
                    f"a reservoir held at {held:g} mM",
                )
            )
            save()
        if any(load["status"] != "done" for load in entry["loads"]):
            continue
        points = [(load["exit_flux_mol_s"], load["port_mM"]) for load in entry["loads"]]
        g_m3_s, unloaded = paper.norton_from_two_loads(points)
        ratio = g_m3_s / worlds.G_EQ1_M3_S
        entry.update(
            g_eq_ratio=ratio,
            unloaded_mM=unloaded,
            E4=bool(
                abs(ratio - physical[n - 1]) / physical[n - 1]
                <= CRITERIA["E4_norton_vs_physical_rtol"]
            ),
            vs_plotted_rel=float(abs(ratio - plotted[n - 1]) / plotted[n - 1]),
        )
        if n <= len(rep["at_minus_half"]):
            # In Figure 8's units: G_eq,1 = 0.1 m^3/s, [mR]_UL0 = 1 mol/m^3, Iexit = -0.5 mol/s.
            g_fig = ratio * rep["g_eq1"]
            entry.update(
                engine_at_minus_half=rep["unloaded"] + 0.5 / g_fig,
                plotted_at_minus_half=rep["unloaded"] + 0.5 / (plotted[n - 1] * rep["g_eq1"]),
                read_at_minus_half=rep["at_minus_half"][n - 1],
                engine_intercept=g_fig * rep["unloaded"],
                read_intercept=rep["intercepts"][n - 1],
            )
            entry["P2_engine_matches_read"] = bool(
                abs(entry["engine_at_minus_half"] - entry["read_at_minus_half"]) <= rep["tolerance"]
            )
            entry["P1_plotted_matches_read"] = bool(
                abs(entry["plotted_at_minus_half"] - entry["read_at_minus_half"])
                <= rep["tolerance"]
            )
        save()


def part_control(out, save):
    result = arm(
        worlds.figure3(1.0),
        junction_scale=PLANTED_SCALE,
        arm_id="control-planted",
        label="Planted control: Figure 3 at G_GJ = G_eq with every junction permeability x1.01",
    )
    out.update(result, junction_scale=PLANTED_SCALE)
    if result["status"] == "done":
        # Judged against the unperturbed g = 1 network's dense solve.
        unperturbed = reference(worlds.figure3(1.0))[0]
        concentration = np.asarray(result["concentration_mM"])
        error = float(np.max(np.abs(concentration - unperturbed) / np.abs(unperturbed)))
        out.update(
            unperturbed_reference_mM=unperturbed.tolist(),
            planted_rel_error=error,
            K1=bool(
                error > CRITERIA["K1_planted_min_rel_error"]
                and error > CRITERIA["E1_engine_vs_dense_rtol"]
            ),
        )
    save()


FUNCTIONS = dict(
    fixture=part_fixture,
    refusals=part_refusals,
    gate=part_gate,
    figure3=part_figure3,
    figure5=part_figure5,
    figure8=part_figure8,
    control=part_control,
)


def main(argv):
    out_dir = Path(argv[1])
    parts = argv[2:] or list(PARTS)
    unknown = set(parts) - set(PARTS)
    if unknown:
        raise SystemExit(f"Unknown parts: {sorted(unknown)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    global RECORDS
    RECORDS = out_dir / "worlds"
    plan = dict(
        criteria=CRITERIA,
        parts=parts,
        figure3_g=FIGURE3_G,
        figure5_g=FIGURE5_G,
        figure8_n=FIGURE8_N,
        figure8_loads_mM=FIGURE8_LOADS,
        planted_scale=PLANTED_SCALE,
        world=dict(
            species=worlds.SPECIES,
            radius_m=worlds.R_CELL_M,
            k_dec_per_s=worlds.K_DEC_PER_S,
            g_eq1_m3_s=worlds.G_EQ1_M3_S,
            end_s=worlds.END_S,
            settle_s=worlds.SETTLE_S,
            observe_every_s=worlds.OBSERVE_EVERY_S,
            base_dt_s=worlds.BASE_DT_S,
            step_bound_margin=worlds.STEP_BOUND_MARGIN,
            solver=worlds.SOLVER,
        ),
        citation=paper.CITATION,
    )
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=1, default=str))
    recorder = Recorder(
        out_dir / "results.json",
        dict(
            python=sys.version,
            platform=platform.platform(),
            jax=jax.__version__,
            blas=blas_threads.libraries(),
            started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ),
    )
    for part in parts:
        started = time.perf_counter()
        out = recorder.part(part)
        entry = recorder.data["parts"][part]
        try:
            FUNCTIONS[part](out, recorder.save)
            entry["status"] = "done"
        except Exception as error:  # Recorded as failed evidence, never retried silently.
            entry.update(status="failed", error=repr(error), traceback=traceback.format_exc())
        entry["seconds"] = time.perf_counter() - started
        recorder.save()
        print(part, entry["status"], f"{entry['seconds']:.1f} s", flush=True)
    recorder.data["record"]["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        finish_records(recorder.data)
    except Exception as error:  # The results stand; the summary's failure is recorded.
        recorder.data["record"]["finish_records_error"] = repr(error)
    recorder.save()
    failed = [p for p, r in recorder.data["parts"].items() if r["status"] != "done"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
