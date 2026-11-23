"""Gap-junction cancer replication driver: development work, not a judged comparison (D138).

The preprint (paper.CITATION) runs a bioelectric/GRN tissue model in BITSEY (Tables 1-3) and a
linear "intuitive model" analysed by hand (equations 1-2, appendix, Figures 3, 5 and 8). This
driver runs in Cells what the engine can run today, and records from the engine itself what it
refuses or admits. It changes no engine source.

Parts (the default runs all but fixture):
* refusals: definition-time evidence (no integration).
  - A neutral species made in each cell by local_species_reactions@1 with an @3 constant-field
    junction route (refused), the same world without the route (admitted), and the same species
    carried instead by a cells.passive_routes@1 junction route (passive_neutral_permeation@1).
  - The EMT switch written as local_species_reactions@1 reactions in one cell, and in two cells
    with miR200 on a passive junction route (synthetic values): whether each is admitted.
  - The junction, channel and pump laws @3 hosts.
  - The field solver's node bound against the preprint's lattices: a two-step shared-bath world
    at the bound must be admitted, and one node over it refused for the bound.
* gate: F3 and F4 measured. The engine's one junction law (its own kinetics, at steady state)
  fitted to Figure 1's Cx45 small-ion curve, and the same law against the miRNA curve.
* figure3, figure5, figure8, control: the linear model's Norton-equivalent network on @3's own
  routes (worlds.linear_network): two equal cells against G_GJ; Figure 5b's lumped model and
  Figure 5a's seven-cell network; straight chains of 1-5 and 10 cells loaded at the port by two
  held concentrations (the Norton conductance from the two steady states); and the planted
  control, every junction permeability x1.01, judged against the unperturbed reference.
* aswritten: the same networks as the preprint writes them (worlds.as_written): a source and a
  decay in each cell (local_species_reactions@1) and a passive junction route
  (passive_neutral_permeation@1), each run at the step rule's dt, dt/2 and dt/4 (the dt study),
  with the planted control as written (aw-control-planted). Figure 5a at 10 G_eq runs through the
  windowed execution and record path (WINDOWED).
* fixture: two 60 s format fixtures (Norton and as written) for the viewer's tests; no verdict.

The judged comparison (docs/GJ_LINEAR_REGISTRATION.md) is judged by
validation/gap_junction_tissue/linear_judge.py from this driver's results.json, against
code-blind references; the criteria below are the development runs' (dev-01 to dev-06), kept as
their diagnostics against paper.py's own dense solve.
Development criteria, fixed before any development run (CRITERIA):
  E1 Norton network against the dense solve of the same network: relative error <= 1e-9;
  E2 steady state: relative change over the last SETTLE_S seconds <= 1e-12 in every cell;
  E3 the probe flux from the engine's own ledger against G_probe (c - held): relative <= 1e-9;
  E4 chains: the Norton network's G_eq,n against direct circuit analysis: relative <= 1e-8;
  W1 as written: E2 at both steps;
  W2 as written: relative error against the dense solve at the half step <= 1e-4;
  W3 as written: the observed order log2(e(dt)/e(dt/2)) within [1.6, 2.4] where e(dt) > 1e-9;
  P1 the closed forms against the preprint's printed or read values, within the reading
     tolerances paper.REPORTED states (a check of the reading, not of the engine; the
     tolerances were set after the closed forms were evaluated);
  K1 the planted control fails E1 (by more than 1e-6);
  A1 the engine's own run checks pass (material balance and every step check: a run that fails
     one raises, and that arm is recorded as failed while the others go on).
Figure 8's printed recursion is reported, not judged: taken literally and read as Figure 7's
resistance form, against direct analysis (paper.RECURSION_NOTE). The preprint gives no
conductance values for Figure 8.

Engine models run: resolved_pump_tissue@3 (Norton: constant_field@1 membranes and junctions for
one neutral species, held reservoirs) and resolved_pump_composite@1 over it (as written:
local_species_reactions@1, cells.passive_routes@1 with passive_neutral_permeation@1), both with
junction_voltage_relaxation@1 pinned open, resolved_capacitor_components_current_continuity@1 and
imex_ars222_face_electromigration@1.

Records. Every arm's run of record is written by the engine's own writer, cells.records.io.write_run,
under OUTDIR/worlds/<arm id>/ (trajectory.npz with every accepted step, resolved_config.json,
checkpoint_final, summary.json, manifest.json) with view.json, its run view (cells.run_view@1)
with worlds.geometry's prescribed layout, and run.json (revision, models, what the run represents
and, at the end, every arm's parameters and readouts). Selected arms are written again as viewer
packages (OUTDIR/viewer/<arm id>/) with a recording subset; viewer/index.json lists those under
2 MB per layer. A refused view is recorded and the run written without one.

Usage (from a snapshot root, PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu):
    python -B validation/gap_junction_tissue/run.py OUTDIR [part ...] [--no-dt-study] [--end S]
results.json is rewritten after every arm. --no-dt-study runs the as-written arms at the step
rule's dt only, for a rerun that writes their records (with views) and nothing more.
"""  # noqa: E501

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
from cells.definitions.specs import ConfigError, parse_spec  # noqa: E402
from cells.execution import blas_threads, runner  # noqa: E402
from cells.records import io, run_view  # noqa: E402
from validation.gap_junction_tissue import paper, worlds  # noqa: E402

CRITERIA = {
    "E1_engine_vs_dense_rtol": 1e-9,
    "E2_steady_rtol": 1e-12,
    "E3_ledger_flux_rtol": 1e-9,
    "E4_norton_vs_direct_rtol": 1e-8,
    "W2_as_written_half_step_rtol": 1e-4,
    "W3_as_written_order": (1.6, 2.4),
    "W3_as_written_order_floor": 1e-9,
    "K1_planted_min_rel_error": 1e-6,
}
FIGURE3_G = (0.5, 1.0, 2.0, 5.0, 10.0, 50.0)
FIGURE5_G = (1.0, 10.0, 50.0)  # Figure 5b runs to 100; 50 keeps the run short.
# The as-written part stops at 10 G_eq: at 50 its step (the energy check's dt x rate <= 0.04)
# makes each run about 10^5 steps, twice over for the dt study.
AS_WRITTEN_FIGURE3_G = (0.5, 1.0, 2.0, 5.0, 10.0)
AS_WRITTEN_FIGURE5_G = (1.0, 10.0)
FIGURE8_N = (1, 2, 3, 4, 5, 10)
FIGURE8_LOADS = (0.5, 2.0)  # Held concentrations at the port; the unloaded value is 1.
PLANTED_SCALE = 1.01
FIXTURE_END_S = 60.0
TIME_MATCH_RTOL = 1e-12
EXPERIMENT = "gap-junction-cancer-linear-network"
RECORDS = None  # OUTDIR/worlds, set by main(); None writes no records (tools that only check).
PARTS = ("fixture", "refusals", "gate", "figure3", "figure5", "figure8", "control", "aswritten")
DEFAULT_PARTS = tuple(p for p in PARTS if p != "fixture")
NORTON, AS_WRITTEN = "norton", "as_written"
REPRESENTS = {
    NORTON: (
        "The Norton-equivalent network of the preprint's linear ('intuitive') model (its equations "
        "1-2, appendix, Figures 3, 5 and 8): each cell's generation and decay carried by a "
        "membrane to a reservoir held at its unloaded value, cells joined by junctions, on @3's "
        "own constant-field routes for one neutral species. Exact at the fixed point; the check on "
        "the as-written arms. Not the preprint's tissue simulations (Tables 1-3)."
    ),
    AS_WRITTEN: (
        "The preprint's linear ('intuitive') model as it writes it (its equations 1-2, appendix, "
        "Figures 3, 5 and 8): a source and a decay in each cell (local_species_reactions@1) and a "
        "passive junction route for the neutral species (cells.passive_routes@1, "
        "passive_neutral_permeation@1, not numerically qualified). Not the preprint's tissue "
        "simulations (Tables 1-3)."
    ),
}
MODELS = {
    NORTON: ["resolved_pump_tissue@3"],
    AS_WRITTEN: ["resolved_pump_composite@1", "resolved_pump_tissue@3"],
}
LAWS = {
    NORTON: dict(membrane_and_junction_route="constant_field@1"),
    AS_WRITTEN: dict(
        cell_generation_and_decay="local_species_reactions@1 (mass_action source and decay)",
        junction_and_probe_route="passive_neutral_permeation@1 (cells.passive_routes@1)",
    ),
}
# The viewer packages (the visualizer's request, 17 November): a recording subset of the fields
# it names, for these arms in this order, kept where every layer's records stay under 2 MB.
VIEWER_FIELDS = {
    NORTON: (
        "amount_increment",
        "junction_transferred",
        "junction_gate",
        "membrane_voltage_V",
        "junction_voltage_V",
    ),
    AS_WRITTEN: (
        "amount_increment",
        "passive_transferred",
        "junction_gate",
        "membrane_voltage_V",
        "junction_voltage_V",
    ),
}
# Every arm of the summary's sweeps is packaged, so that each chart point opens its run (the
# lead, 17 November), with Figure 5a's network as written; the index keeps those within the limit.
VIEWER_ARMS = (
    *(f"figure3-g{g:g}" for g in FIGURE3_G),
    *(f"figure5-lumped-g{g:g}" for g in FIGURE5_G),
    *(f"figure5-network-g{g:g}" for g in FIGURE5_G),
    *(f"figure8-chain{n}-held{FIGURE8_LOADS[0]:g}" for n in FIGURE8_N),
    *(f"aw-figure3-g{g:g}" for g in AS_WRITTEN_FIGURE3_G),
    *(f"aw-figure5-lumped-g{g:g}" for g in AS_WRITTEN_FIGURE5_G),
    *(f"aw-figure5-network-g{g:g}" for g in AS_WRITTEN_FIGURE5_G),
    *(f"aw-figure8-chain{n}-held{FIGURE8_LOADS[0]:g}" for n in FIGURE8_N),
    "fixture-figure3-g1",
    "fixture-aw-figure3-g1",
)
VIEWER_LAYER_BYTES = 2**21  # 2 MB: Figure 5a's 1.06 MB layer is fine (the lead, 17 November).
VIEWER_MAX = 64
# The sweeps' summary for the viewer's charts (cells.experiment_summary@1, the visualizer's
# schema/RUN_VIEW.md, "A sweep's chart"): numbers only, copied as stated. A run lists the Norton
# sweeps, and the as-written ones once its as-written records carry run views (they do once
# local_species_reactions@1 declares its run view; the lead, 17 November).
SUMMARY_FORMAT = "cells.experiment_summary@1"
SUMMARY_KINDS = (NORTON,)
# The as-written dt study: each arm again at these fractions of its step, the registered triple dt,
# dt/2 and dt/4 (docs/GJ_LINEAR_REGISTRATION.md; dev-04 ran dt and dt/2). `--no-dt-study` leaves
# it out, for a rerun that only writes the as-written records.
DT_STUDY = True
DT_STUDY_FRACTIONS = (0.5, 0.25)
# Every arm's horizon: worlds.END_S, the registered 600 s. `--end S` shortens it for a smoke run of
# the code paths, whose arms are not steady and carry no verdict.
HORIZON_S = worlds.END_S
# Arms whose full trace exceeds the runner's 2 GB budget run through the windowed execution
# (cells.execution.windows) and its record writer (cells.records.window_io), at every step of
# their dt study: Figure 5a at 10 G_eq as written (2.6 GB at its step, 1/128 s; dev-04 refused it).
WINDOWED = frozenset({"aw-figure5-network-g10"})
WINDOW_STEPS = 1024
EQUATION_2 = dict(
    label="Equation 2",
    source=(
        "the preprint's equation 2, the steady state of two linear cells; its second line as "
        "corrected in docs/GAP_JUNCTION_CANCER_REPLICATION.md, section 1, item 6"
    ),
)


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


def source_identity():
    """The execution snapshot this run comes from (SNAPSHOT.json at the working directory, as
    tools/run.sh runs it), or nothing when run from a checkout."""
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


def write_record(result, arm_id, label, kind):
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
        kind=kind,
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
        species = worlds.SPECIES if kind == NORTON else worlds.AS_WRITTEN_SPECIES
        # The linear species alone: the ions are a static background (package size).
        recording = run_view.Recording(fields=VIEWER_FIELDS[kind], elements={"species": [species]})
        targets.append(("viewer", RECORDS.parent / "viewer" / arm_id, recording))
    for target, directory, recording in targets:
        request = run_view.Request(labels, geometry=geometry, recording=recording)
        try:
            io.write_run(directory, result.run, provenance=provenance, view=request)
            out[target] = dict(directory=str(directory), view="written")
            if target == "viewer":
                sizes = layer_bytes(directory)
                out[target].update(
                    layer_bytes=sizes,
                    within_limit=all(v < VIEWER_LAYER_BYTES for v in sizes.values()),
                    sidecar=concentration_sidecar(directory, kind),
                )
        except run_view.ViewRefused as error:
            io.write_run(directory, result.run, provenance=provenance)
            out[target] = dict(directory=str(directory), view="refused", refusal=str(error))
        write_run_json(directory, arm_id, kind, result.run.spec, provenance, experiment=None)
    return out


def write_windowed_record(spec, network, arm_id, label, kind):
    """A WINDOWED arm's run record, written by the engine's windowed writer
    (cells.records.window_io.write_windowed_run: windows.jsonl and its chunks, with the run view
    and run.json), from a second, identical windowed run. No viewer package: the windowed record
    has its own layout."""
    if RECORDS is None:
        return None
    from cells.execution.windows import WindowPolicy
    from cells.records.window_io import write_windowed_run

    labels = dict(id=arm_id, experiment=EXPERIMENT, arm=arm_id, label=label)
    provenance = dict(
        operation="fresh",
        driver="validation/gap_junction_tissue/run.py",
        experiment=EXPERIMENT,
        arm=arm_id,
        kind=kind,
        citation=paper.CITATION,
        **source_identity(),
    )
    source = (
        "validation/gap_junction_tissue/worlds.py: touching spheres after the preprint's "
        "drawings (Figures 3a, 5a, 7)"
    )
    request = run_view.Request(labels, geometry=worlds.geometry(network, source))
    directory = RECORDS / arm_id
    policy = WindowPolicy(WINDOW_STEPS, "observations", "device")
    try:
        write_windowed_run(directory, spec, policy, provenance=provenance, view=request)
        out = dict(directory=str(directory), view="written", execution="windowed")
    except run_view.ViewRefused as error:
        write_windowed_run(directory, spec, policy, provenance=provenance)
        out = dict(directory=str(directory), view="refused", refusal=str(error))
    write_run_json(directory, arm_id, kind, spec, provenance, experiment=None)
    return dict(record=out)


QUANTITY_FORMAT = "cells.experiment_quantity@1"


def concentration_sidecar(directory, kind):
    """concentration.json beside a viewer package (a viewer sidecar written by the driver, not an
    engine field): each cell's concentration of the linear model's species per observed row, from
    the package's own saved amounts and volumes (fmol / pL = mM), in the unit of the summary's
    readouts for the form (the Norton form mM; as written uM, one of the preprint's units being
    1 uM there). The cells are the view's cell set, in the layout's order, which is the
    arrays' column order."""
    directory = Path(directory)
    view = json.loads((directory / "view.json").read_text())
    cell_ids = next(s for s in view["sets"] if s["id"] == "cell")["ids"]
    species = worlds.SPECIES if kind == NORTON else worlds.AS_WRITTEN_SPECIES
    unit, scale = ("mM", 1.0) if kind == NORTON else ("uM", worlds.AS_WRITTEN_SCALE_mM)
    species_set = next(s for s in view["sets"] if s["id"] == "species")
    full = species_set["ids"].index(species)
    recorded = species_set.get("recorded")  # The recording's species, when it keeps a subset.
    kept = full if recorded is None else recorded.index(full)
    with np.load(directory / "trajectory.npz") as arrays:
        if len(arrays["cell_ids"]) < len(cell_ids) or arrays["volume"].shape[0] < len(cell_ids):
            raise ValueError(f"{directory}: the arrays hold fewer cells than the view")
        n = len(cell_ids)
        times = np.asarray(arrays["observation_times"], dtype=float)
        reference = arrays["amount_reference"]  # The layout's: every species.
        ref_row = full if reference.shape[0] == len(species_set["ids"]) else kept
        amount = reference[ref_row, :n] + arrays["observed_amount_increment"][:, kept, :n]
        values = amount / arrays["volume"][:n] / scale
    if not (np.all(np.isfinite(values)) and np.all(np.isfinite(times))):
        raise ValueError(f"{directory}: a concentration or time is not finite")
    label = (
        "[mR], the preprint's linear species, in each cell, in mM; the preprint's scaled unit "
        "is 1 mM in this world"
        if kind == NORTON
        else "[mR] as written (the species S), in each cell, in µM; the preprint's scaled unit "
        "is 1 µM in this world"
    )
    sidecar = dict(
        format=QUANTITY_FORMAT,
        quantity=dict(
            id="concentration",
            label=f"{label} (amount / volume from the run's own arrays)",
            unit=unit,
        ),
        times_s=times.tolist(),
        cells=list(cell_ids),
        values=values.tolist(),
    )
    (directory / "concentration.json").write_text(json.dumps(sidecar, allow_nan=False))
    return "concentration.json"


def write_run_json(directory, arm_id, kind, spec, provenance, experiment):
    """run.json beside the engine's files: the revision, the models, the definition's hash, what
    the run represents, and (once the experiment ends) every arm's parameters and readouts."""
    entry = dict(
        format="gap_junction_tissue.run@1",
        status="development run of the engine, not judged (D138)",
        kind=kind,
        represents=REPRESENTS[kind],
        citation=dict(text=paper.CITATION, doi=paper.DOI_URL),
        revision=provenance.get("revision"),
        snapshot=provenance.get("snapshot"),
        snapshot_clean=provenance.get("clean"),
        models=MODELS[kind],
        laws=dict(
            **LAWS[kind],
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
    """Each arm's parameters and readouts under the preprint's names (mol/m^3 for [mR], mol/s)."""
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
            dict(
                id=arm_id,
                figure=figure,
                kind=result.get("kind", NORTON),
                parameters=parameters,
                status=result.get("status"),
                readouts=readouts,
                record=result.get("record"),
            )
        )

    for name in ("fixture", "figure3", "figure5", "aswritten"):
        result_of = parts.get(name, {}).get("result", {})
        for result in result_of.get("figure3", []):
            add(
                result["arm_id"],
                "3b",
                {"G_GJ / G_eq": result.get("g"), "mR_UL0, mR_UL1 (mol/m^3)": [5, 10]},
                result,
                {"equation 2": result.get("eq2"), "half step": result.get("half_step")},
            )
        for result in result_of.get("figure5_lumped", []):
            add(
                result["arm_id"],
                "5b",
                {
                    "G_GJ / G_eq,A": result["g"],
                    "G_eq,B / G_eq,A": 4.0 / 3.0,
                    "mR_UL,A, mR_UL,B (mol/m^3)": [10, 5],
                },
                result,
                {"equation 2": result.get("eq2"), "half step": result.get("half_step")},
            )
        for result in result_of.get("figure5_network", []):
            add(
                result["arm_id"],
                "5a",
                {
                    "G_GJ / G_eq": result["g"],
                    "cells": "A with two backups at 10, B with three at 5",
                },
                result,
                {"half step": result.get("half_step")},
            )
    for name in ("figure8", "aswritten"):
        for chain in parts.get(name, {}).get("result", {}).get("chains", []):
            for held, result in zip(FIGURE8_LOADS, chain["loads"], strict=False):
                add(
                    result["arm_id"],
                    "8",
                    {
                        "cells n": chain["n"],
                        "G_GJ / G_eq,1": 1.0,
                        "mR_UL0 (mol/m^3)": 1.0,
                        "probe held [mR] (mol/m^3)": held,
                        "G_probe / G_eq,1": 1.0,
                    },
                    result,
                    {
                        "port [mR] (mol/m^3)": result.get("port_mM"),
                        "i_exit (mol/s)": result.get("exit_flux_mol_s"),
                        "G_eq,n / G_eq,1 (from both loads)": chain.get("g_eq_ratio"),
                        "G_eq,n / G_eq,1, direct analysis": chain.get("direct_ratio"),
                    },
                )
    control = parts.get("control", {}).get("result", {})
    if control:
        planted = {"relative error against the unperturbed solve": control.get("planted_rel_error")}
        parameters = {"G_GJ / G_eq": 1.0, "junction permeability scale": PLANTED_SCALE}
        add("control-planted", "3b (planted control)", parameters, control, planted)
    return dict(id=EXPERIMENT, represents=REPRESENTS, arms=arms)


def finish_records(data):
    """Rewrite every record's run.json with the whole experiment's summary; write the viewer
    index (viewer/index.json): the packages within the size limit, in VIEWER_ARMS order, at most
    VIEWER_MAX, fixtures only when nothing else was written."""
    if RECORDS is None:
        return
    summary = experiment_summary(data)
    viewer = []
    for arm in summary["arms"]:
        for target, record in (arm.get("record") or {}).items():
            directory = Path(record["directory"])
            if not (directory / "run.json").is_file():
                continue
            entry = json.loads((directory / "run.json").read_text())
            entry["experiment"] = summary
            (directory / "run.json").write_text(json.dumps(entry, indent=1, default=str))
            if target == "viewer":
                viewer.append(dict(arm=arm["id"], **record))
    order = {arm_id: k for k, arm_id in enumerate(VIEWER_ARMS)}
    viewer.sort(key=lambda v: order.get(v["arm"], len(order)))
    real = [v for v in viewer if not v["arm"].startswith("fixture-")]
    candidates = real or viewer
    selected = [v["arm"] for v in candidates if v.get("within_limit")][:VIEWER_MAX]
    index = dict(
        experiment=EXPERIMENT,
        represents=REPRESENTS,
        layer_limit_bytes=VIEWER_LAYER_BYTES,
        packages=viewer,
        selected=selected,
    )
    path = RECORDS.parent / "viewer" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=1, default=str))
    summary = sweep_summary(data, kinds=summary_kinds(data))
    (path.parent / "summary.json").write_text(json.dumps(summary, indent=1, allow_nan=False))


def summary_kinds(data):
    """SUMMARY_KINDS, and the as-written form when one of the run's as-written records carries
    its run view."""
    for part in data["parts"].values():
        for value in part.get("result", {}).values():
            results = value if isinstance(value, list) else []
            for result in results:
                loads = result.get("loads", [result]) if isinstance(result, dict) else []
                for r in loads:
                    if r.get("kind") != AS_WRITTEN:
                        continue
                    records = (r.get("record") or {}).values()
                    if any(record.get("view") == "written" for record in records):
                        return (*SUMMARY_KINDS, AS_WRITTEN)
    return SUMMARY_KINDS


def sweep_summary(data, kinds=SUMMARY_KINDS, note=None):
    """The run's sweeps (cells.experiment_summary@1): per figure and form, the parameter, each
    readout and, where the preprint states one, its reference (equation 2), for every arm that
    ran; a sweep with fewer than two such arms is left out. Values are in the units named: the
    Norton form's concentrations in mM; the as-written form's in uM (one of the preprint's units
    is 1 uM there)."""
    parts = data["parts"]

    def result(name):
        return parts.get(name, {}).get("result", {})

    def done(results):
        return [r for r in results if r.get("status") == "done"]

    sweeps = []
    for kind in kinds:
        prefix, unit = ("", "mM") if kind == NORTON else ("aw-", "uM")
        mapping = (
            "in mM; the preprint's scaled unit is 1 mM in this world"
            if kind == NORTON
            else "in µM; the preprint's scaled unit is 1 µM in this world"
        )
        form = "Norton form" if kind == NORTON else "as written"
        own = {
            key: result("aswritten" if kind == AS_WRITTEN else name)
            for key, name in (
                ("figure3", "figure3"),
                ("figure5", "figure5"),
                ("figure8", "figure8"),
            )
        }
        candidates = [
            dict(
                id=f"{prefix}figure3",
                label=f"Figure 3b: two equal linear cells ({form})",
                plain="The steady [mR] of two equal linear cells, unloaded at 5 and 10, as their "
                "junction conductance grows.",
                parameter=dict(id="g", label="Junction conductance G_GJ", unit="G_eq"),
                readouts=[
                    dict(id="c_A", label=f"[mR] in cell A, unloaded at 5, {mapping}", unit=unit),
                    dict(id="c_B", label=f"[mR] in cell B, unloaded at 10, {mapping}", unit=unit),
                ],
                reference=EQUATION_2,
                arms=[
                    dict(
                        arm=r["arm_id"],
                        parameter=r["g"],
                        readouts=dict(c_A=r["concentration_mM"][0], c_B=r["concentration_mM"][1]),
                        reference=dict(c_A=r["eq2"][0], c_B=r["eq2"][1]),
                    )
                    for r in done(own["figure3"].get("figure3", []))
                ],
            ),
            dict(
                id=f"{prefix}figure5b",
                label=f"Figure 5b: cell B 4/3 of cell A ({form})",
                plain="The steady [mR] of a linear cell A, unloaded at 10, and a cell B 4/3 its "
                "size, unloaded at 5, as their junction conductance grows.",
                parameter=dict(id="g", label="Junction conductance G_GJ", unit="G_eq,A"),
                readouts=[
                    dict(id="c_A", label=f"[mR] in cell A, {mapping}", unit=unit),
                    dict(id="c_B", label=f"[mR] in cell B, {mapping}", unit=unit),
                ],
                reference=dict(
                    label="Equation 2, with G_eq,B = 4/3 G_eq,A",
                    source="the preprint's equation 2 and Figure 5's caption",
                ),
                arms=[
                    dict(
                        arm=r["arm_id"],
                        parameter=r["g"],
                        readouts=dict(c_A=r["concentration_mM"][0], c_B=r["concentration_mM"][1]),
                        reference=dict(c_A=r["eq2"][0], c_B=r["eq2"][1]),
                    )
                    for r in done(own["figure5"].get("figure5_lumped", []))
                ],
            ),
            dict(
                id=f"{prefix}figure5a",
                label=f"Figure 5a: the drawn network ({form})",
                plain="The steady [mR] of cells A and B as drawn in Figure 5a, A with two backup "
                "cells at 10 and B with three at 5, as every junction's conductance grows.",
                parameter=dict(id="g", label="Junction conductance G_GJ", unit="G_eq"),
                readouts=[
                    dict(id="c_A", label=f"[mR] in cell A, {mapping}", unit=unit),
                    dict(id="c_B", label=f"[mR] in cell B, {mapping}", unit=unit),
                ],
                arms=[
                    dict(
                        arm=r["arm_id"],
                        parameter=r["g"],
                        readouts=dict(c_A=r["concentration_mM"][0], c_B=r["concentration_mM"][1]),
                    )
                    for r in done(own["figure5"].get("figure5_network", []))
                ],
            ),
            dict(
                id=f"{prefix}figure8",
                label=f"Figure 8: straight chains of linear cells ({form})",
                plain="The Norton conductance of a straight chain of n linear cells at "
                "G_GJ = G_eq,1, from its runs with the port held at 0.5 and at 2.",
                parameter=dict(id="n", label="Cells in the chain", unit="cells"),
                readouts=[
                    dict(id="g_eq", label="Norton conductance G_eq,n of the chain", unit="G_eq,1")
                ],
                arms=[
                    dict(
                        arm=c["loads"][0]["arm_id"],
                        parameter=c["n"],
                        readouts=dict(g_eq=c["g_eq_ratio"]),
                    )
                    for c in own["figure8"].get("chains", [])
                    if isinstance(c.get("g_eq_ratio"), float) and math.isfinite(c["g_eq_ratio"])
                ],
            ),
        ]
        sweeps += [sweep for sweep in candidates if len(sweep["arms"]) >= 2]
    summary = dict(format=SUMMARY_FORMAT, experiment=EXPERIMENT, sweeps=sweeps)
    if note:
        summary["note"] = note
    return summary


class Outcome(NamedTuple):
    run: object
    network: object


def _windowed_rows(spec, times):
    """The amount increments at `times` (each an observation time) from the windowed execution
    (cells.execution.windows, observations kept, device row checks; every engine check runs),
    with the final layout, the diagnostics' largest values and the accepted step count."""
    from cells.execution.windows import WindowPolicy, iter_windows

    wanted, found, diagnostics, last = set(times), {}, {}, None
    for window in iter_windows(spec, WindowPolicy(WINDOW_STEPS, "observations", "device")):
        last = window.final
        for k, v in window.diagnostics.items():
            if _number(v):
                diagnostics[k] = max(diagnostics.get(k, -math.inf), float(v))
        obs = window.observations
        if obs is None or not hasattr(obs, "amount_increment"):
            continue
        for row, when in enumerate(np.asarray(obs.times, dtype=float)):
            for t in wanted:
                if abs(when - t) <= TIME_MATCH_RTOL * max(1.0, abs(t)):
                    found[t] = np.asarray(obs.amount_increment)[row]
    missing = sorted(wanted - set(found))
    if missing:
        raise ValueError(f"No observed row at {missing}")
    return found, last.layout, diagnostics, int(last.step_index)


def run_network(
    network,
    *,
    kind=NORTON,
    junction_scale=1.0,
    end=None,
    dt=None,
    arm_id=None,
    label="",
    windowed_arm=None,
):
    """Run one network to steady state; return the engine's readouts and the dense reference.

    kind NORTON builds worlds.linear_network, AS_WRITTEN worlds.as_written (amounts in uM,
    reported in the preprint's units). The probe's exit flux is read from the engine's own
    ledger: the probe membrane's (NORTON, cell to held) or the probe route's (AS_WRITTEN,
    inward). windowed_arm (an arm of WINDOWED) runs the windowed execution instead of the full
    trace, reading the concentrations from its observed rows; its record, when one is written,
    comes from the windowed writer (write_windowed_record)."""
    cells_, probes = network.cells, network.probes
    end = HORIZON_S if end is None else end
    if kind == NORTON:
        raw = worlds.linear_network(
            cells_, network.edges, probes, junction_scale=junction_scale, end=end, dt=dt
        )
        scale = 1.0
    else:
        raw = worlds.as_written(network, junction_scale=junction_scale, end=end, dt=dt)
        scale = worlds.AS_WRITTEN_SCALE_mM
    spec = parse_spec(raw)
    row_species = list(spec.model.species_ids).index(
        worlds.SPECIES if kind == NORTON else worlds.AS_WRITTEN_SPECIES
    )
    windowed = windowed_arm is not None
    started = time.perf_counter()
    end, before = spec.experiment.end_time, spec.experiment.end_time - worlds.SETTLE_S
    if windowed:
        if probes:
            raise ValueError("The windowed path reads concentrations only; this arm has a probe")
        increments, layout, diagnostics, accepted = _windowed_rows(spec, (before, end))
    else:
        result = runner.run(spec)
        times = np.asarray(result.times)
        rows = {t: _row(times, t) for t in (before, end)}
        layout, history, accepted = result.final.layout, result.history, int(times.size)
        increments = {t: np.asarray(history.amount_increment[rows[t]]) for t in (before, end)}
        diagnostics = result.diagnostics
    seconds = time.perf_counter() - started
    volume = np.asarray(layout.volume)[: len(cells_)]
    reference_amount = np.asarray(layout.amount_reference)[row_species, : len(cells_)]

    def concentration(t):
        increment = increments[t][row_species, : len(cells_)]
        return (reference_amount + increment) / volume / scale  # the preprint's units

    c_end, c_before = concentration(end), concentration(before)
    c_ref, flux_ref = reference(network)
    out = dict(
        kind=kind,
        dt_s=spec.execution.dt,
        steps=int(round(end / spec.execution.dt)),
        accepted_rows=accepted,
        seconds=seconds,
        execution="windowed" if windowed else "full trace",
        concentration_mM=c_end.tolist(),
        reference_mM=c_ref.tolist(),
        engine_rel_error=float(np.max(np.abs(c_end - c_ref) / np.abs(c_ref))),
        steady_rel_change=float(np.max(np.abs(c_end - c_before) / np.abs(c_end))),
        diagnostics={k: float(v) for k, v in diagnostics.items() if _number(v)},
        definition_sha256=spec.fingerprint,
    )
    if probes:
        _, i, held, g = probes[-1]
        if kind == NORTON:
            slot = len(cells_) + len(probes) - 1  # the last membrane; cell -> held reservoir
            moved = [
                np.asarray(history.membrane_transferred[rows[t]])[row_species, slot]
                for t in (before, end)
            ]
            out_of_cell = moved[1] - moved[0]
        else:
            slot = len(network.edges) + len(probes) - 1  # the last route; inward positive
            moved = [
                np.asarray(history.passive_transferred[rows[t]])[row_species, slot]
                for t in (before, end)
            ]
            out_of_cell = -(moved[1] - moved[0])
        ledger = out_of_cell / worlds.SETTLE_S * 1e-15 / scale  # mol/s in the preprint's units
        formula = g * worlds.G_EQ1_M3_S * (c_end[i] - held)  # m^3/s * mol/m^3
        out.update(
            port_mM=float(c_end[i]),
            exit_flux_mol_s=float(ledger),
            exit_flux_formula_mol_s=float(formula),
            exit_flux_reference_mol_s=float(flux_ref[-1]),
            ledger_rel_error=float(abs(ledger - formula) / abs(formula)),
        )
    if arm_id is not None:
        if windowed:
            out["record"] = write_windowed_record(spec, network, arm_id, label, kind)
        else:
            out["record"] = write_record(Outcome(result, network), arm_id, label, kind)
    return out


def arm(network, *, arm_id=None, label="", **kwargs):
    """run_network with its checks, or the failure (recorded as evidence, never retried)."""
    try:
        out = run_network(network, arm_id=arm_id, label=label, **kwargs)
    except Exception as error:
        return dict(
            status="failed",
            error=repr(error),
            traceback=traceback.format_exc(),
            arm_id=arm_id,
            kind=kwargs.get("kind", NORTON),
        )
    out.update(status="done", arm_id=arm_id)
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
    out["passive_junction_route"] = _parse(worlds.junction_route_passive())
    out["emt_switch_reactions"] = _parse(worlds.emt_switch_probe())
    out["emt_switch_two_cells_passive_route"] = _parse(worlds.emt_switch_two_cells_passive())
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
        constant_field_junction_route_refused=not route["accepted"]
        and "route through junction j_0" in route.get("refusal", "")
        and out["without_junction_route"]["accepted"],
        passive_junction_route_admitted=out["passive_junction_route"]["accepted"],
        emt_switch_admitted=out["emt_switch_reactions"]["accepted"],
        emt_switch_with_passive_route_admitted=out["emt_switch_two_cells_passive_route"][
            "accepted"
        ],
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
    from cells.laws.junctions import junction_gate

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


def _arm_id(kind, base):
    return base if kind == NORTON else f"aw-{base}"


def _figure3(out, save, kind, *, gs=FIGURE3_G, end=None, prefix=""):
    rep = paper.REPORTED["figure3b"]
    out.setdefault("figure3", [])
    for g in gs:
        arm_id = prefix + _arm_id(kind, f"figure3-g{g:g}")
        label = f"Figure 3: two equal linear cells (unloaded 5 and 10), G_GJ = {g:g} G_eq ({kind})"
        result = arm(
            worlds.figure3(g, rep["unloaded"]), kind=kind, end=end, arm_id=arm_id, label=label
        )
        result.update(g=g, eq2=list(paper.eq2(*rep["unloaded"], g, g)))
        out["figure3"].append(result)
        save()


def part_fixture(out, save):
    """Two 60 s runs of the real runs' shape for the viewer's tests (not steady; no verdict)."""
    for kind in (NORTON, AS_WRITTEN):
        _figure3(out, save, kind, gs=(1.0,), end=FIXTURE_END_S, prefix="fixture-")
    for result in out["figure3"]:
        result["purpose"] = "format fixture"
    save()


def part_figure3(out, save):
    rep = paper.REPORTED["figure3b"]
    _figure3(out, save, NORTON)
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


def _figure5(out, save, kind, gs=FIGURE5_G):
    rep = paper.REPORTED["figure5"]
    ua, ub = rep["unloaded"]["A"], rep["unloaded"]["B"]
    out.setdefault("figure5_lumped", [])
    out.setdefault("figure5_network", [])
    for g in gs:
        result = arm(
            worlds.figure5_lumped(g, rep["size_ratio"], (ua, ub)),
            kind=kind,
            arm_id=_arm_id(kind, f"figure5-lumped-g{g:g}"),
            label=f"Figure 5b: cell B 4/3 of cell A, G_GJ = {g:g} G_eq ({kind})",
        )
        result.update(g=g, eq2=list(paper.eq2(ua, ub, g, g / rep["size_ratio"])))
        out["figure5_lumped"].append(result)
        save()
        arm_id = _arm_id(kind, f"figure5-network-g{g:g}")
        result = arm(
            worlds.figure5_network(g, (ua, ub)),
            kind=kind,
            arm_id=arm_id,
            label=f"Figure 5a: A with two backups, B with three, G_GJ = {g:g} G_eq ({kind})",
            windowed_arm=arm_id if arm_id in WINDOWED else None,
        )
        result.update(g=g, windowed_arm=arm_id if arm_id in WINDOWED else None)
        out["figure5_network"].append(result)
        save()


def part_figure5(out, save):
    rep = paper.REPORTED["figure5"]
    ua, ub = rep["unloaded"]["A"], rep["unloaded"]["B"]
    _figure5(out, save, NORTON)
    limit = (ua + rep["size_ratio"] * ub) / (1.0 + rep["size_ratio"])
    out["reading"] = dict(
        limit_closed_form=limit,
        caption_final=rep["final"],
        P1_final=bool(abs(limit - rep["final"]) <= rep["tolerance"]),
        text_ratio_1p5_limit=(ua + 1.5 * ub) / 2.5,
    )
    save()


def _chains(out, save, kind):
    direct = paper.chain_physical(1.0, 1.0, max(FIGURE8_N))
    resistance_form = paper.chain_paper(1.0, 1.0, max(FIGURE8_N))
    literal = paper.chain_literal(1.0, 1.0, max(FIGURE8_N))
    out.update(direct_limit_ratio=paper.chain_limit(1.0, 1.0), recursion_note=paper.RECURSION_NOTE)
    out["chains"] = []
    for n in FIGURE8_N:
        entry = dict(
            n=n,
            direct_ratio=direct[n - 1],
            printed_resistance_form=resistance_form[n - 1],
            printed_literal_in_units_of_g=literal[n - 1],
            loads=[],
        )
        out["chains"].append(entry)
        for held in FIGURE8_LOADS:
            entry["loads"].append(
                arm(
                    worlds.chain(n, held),
                    kind=kind,
                    arm_id=_arm_id(kind, f"figure8-chain{n}-held{held:g}"),
                    label=f"Figure 8: a straight chain of {n} linear cells, its port loaded by a "
                    f"reservoir held at {held:g} ({kind})",
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
            vs_direct_rel=float(abs(ratio - direct[n - 1]) / direct[n - 1]),
        )
        entry["E4"] = bool(entry["vs_direct_rel"] <= CRITERIA["E4_norton_vs_direct_rtol"])
        save()


def part_figure8(out, save):
    _chains(out, save, NORTON)


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


def _dt_study(network, result, *, junction_scale=1.0):
    """The dt study's further runs: the same as-written world at DT_STUDY_FRACTIONS of the arm's
    step (dt/2 and dt/4, the registered triple with the arm's own run), each with every readout
    the judge reads (validation/gap_junction_tissue/linear_judge.py); none when the run leaves
    the dt study out or the arm failed."""
    if result.get("status") != "done" or not DT_STUDY:
        return None
    steps = []
    for fraction in DT_STUDY_FRACTIONS:
        run = arm(
            network,
            kind=AS_WRITTEN,
            dt=result["dt_s"] * fraction,
            junction_scale=junction_scale,
            windowed_arm=result.get("windowed_arm"),
        )
        entry = dict(fraction=fraction, dt_s=run.get("dt_s"), status=run["status"])
        for key in (
            "error",
            "steps",
            "seconds",
            "execution",
            "concentration_mM",
            "steady_rel_change",
            "engine_rel_error",
            "port_mM",
            "exit_flux_mol_s",
            "exit_flux_formula_mol_s",
            "ledger_rel_error",
            "definition_sha256",
            "diagnostics",
        ):
            if key in run:
                entry[key] = run[key]
        steps.append(entry)
    return steps


def _study(result, network, **kwargs):
    """The arm's dt study, stored as `dt_study` (each step) and `half_step` (its dt/2 entry, which
    the viewer's summary reads)."""
    steps = _dt_study(network, result, **kwargs)
    result["dt_study"] = steps
    result["half_step"] = steps[0] if steps else None


def part_aswritten(out, save):
    """The linear model as written, each arm at the step rule's dt (its run of record) and at
    dt/2 and dt/4 (the dt study, the registered triple); the planted control as written
    (aw-control-planted, every junction route x PLANTED_SCALE), with its own triple."""
    _figure3(out, save, AS_WRITTEN, gs=AS_WRITTEN_FIGURE3_G)
    for result in out["figure3"]:
        _study(result, worlds.figure3(result["g"]))
        save()
    planted = arm(
        worlds.figure3(1.0),
        kind=AS_WRITTEN,
        junction_scale=PLANTED_SCALE,
        arm_id="aw-control-planted",
        label="Planted control as written: Figure 3 at G_GJ = G_eq with every junction route x1.01",
    )
    planted.update(g=1.0, junction_scale=PLANTED_SCALE)
    _study(planted, worlds.figure3(1.0), junction_scale=PLANTED_SCALE)
    out["control_planted"] = planted
    save()
    _figure5(out, save, AS_WRITTEN, gs=AS_WRITTEN_FIGURE5_G)
    rep = paper.REPORTED["figure5"]
    for result in out["figure5_lumped"]:
        network = worlds.figure5_lumped(
            result["g"], rep["size_ratio"], (rep["unloaded"]["A"], rep["unloaded"]["B"])
        )
        _study(result, network)
        save()
    for result in out["figure5_network"]:
        network = worlds.figure5_network(result["g"], (rep["unloaded"]["A"], rep["unloaded"]["B"]))
        _study(result, network)
        save()
    _chains(out, save, AS_WRITTEN)
    for entry in out["chains"]:
        for held, load in zip(FIGURE8_LOADS, entry["loads"], strict=True):
            _study(load, worlds.chain(entry["n"], held))
        entry["dt_study_g_eq_ratio"] = []
        for k, fraction in enumerate(DT_STUDY_FRACTIONS if DT_STUDY else ()):
            steps = [(load.get("dt_study") or [None] * (k + 1))[k] for load in entry["loads"]]
            if all(x and x.get("status") == "done" and "exit_flux_mol_s" in x for x in steps):
                points = [(x["exit_flux_mol_s"], x["port_mM"]) for x in steps]
                g_m3_s, unloaded = paper.norton_from_two_loads(points)
                entry["dt_study_g_eq_ratio"].append(
                    dict(
                        fraction=fraction, g_eq_ratio=g_m3_s / worlds.G_EQ1_M3_S, unloaded=unloaded
                    )
                )
            else:
                entry["dt_study_g_eq_ratio"].append(dict(fraction=fraction, status="failed"))
        save()


FUNCTIONS = dict(
    fixture=part_fixture,
    refusals=part_refusals,
    gate=part_gate,
    figure3=part_figure3,
    figure5=part_figure5,
    figure8=part_figure8,
    control=part_control,
    aswritten=part_aswritten,
)


def write_sidecars(run_dir):
    """concentration.json for every viewer package of a finished run (each with its view)."""
    written = {}
    for directory in sorted((Path(run_dir) / "viewer").iterdir()):
        if directory.is_dir() and (directory / "view.json").is_file():
            kind = AS_WRITTEN if "aw-" in directory.name else NORTON
            written[directory.name] = concentration_sidecar(directory, kind)
    return written


def main(argv):
    global DT_STUDY
    if argv[1:2] == ["--sidecars"]:  # Sidecars for a finished run's packages (run made before).
        print(json.dumps(write_sidecars(argv[2]), indent=1))
        return 0
    if "--no-dt-study" in argv:
        argv = [a for a in argv if a != "--no-dt-study"]
        DT_STUDY = False
    global HORIZON_S
    if "--end" in argv:  # A smoke run's short horizon: its arms are not steady (no verdict).
        k = argv.index("--end")
        HORIZON_S = float(argv[k + 1])
        argv = argv[:k] + argv[k + 2 :]
    out_dir = Path(argv[1])
    parts = argv[2:] or list(DEFAULT_PARTS)
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
        as_written_figure3_g=AS_WRITTEN_FIGURE3_G,
        as_written_figure5_g=AS_WRITTEN_FIGURE5_G,
        figure8_n=FIGURE8_N,
        figure8_loads=FIGURE8_LOADS,
        planted_scale=PLANTED_SCALE,
        as_written_dt_study=DT_STUDY,
        world=dict(
            species=worlds.SPECIES,
            as_written_species=worlds.AS_WRITTEN_SPECIES,
            as_written_scale_mM=worlds.AS_WRITTEN_SCALE_mM,
            radius_m=worlds.R_CELL_M,
            k_dec_per_s=worlds.K_DEC_PER_S,
            g_eq1_m3_s=worlds.G_EQ1_M3_S,
            end_s=HORIZON_S,
            registered_end_s=worlds.END_S,
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
            **source_identity(),
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
