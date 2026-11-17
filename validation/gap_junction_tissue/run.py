"""Gap-junction cancer replication driver: development work, not a judged comparison (D138).

The preprint (paper.CITATION) runs a bioelectric/GRN tissue model in BITSEY (Tables 1-3) and a
linear "intuitive model" analysed by hand (equations 1-2, appendix, Figures 3, 5 and 8). This
driver runs in Cells what the engine can run today and records, from the engine itself, why the
rest cannot run yet. It changes no engine source.

Parts:
* refusals: definition-time evidence for the gaps (no integration). A neutral species that is
  made in each cell by local_species_reactions@1 and also crosses a junction (the preprint's
  miRNA) against the same world without the junction route; the junction, channel and pump laws
  @3 hosts; the field solver's node bound against the preprint's lattices (a shared-bath world
  one node over the bound must be refused).
* gate: F3 and F4 measured. The engine's one junction law (its own kinetics, at steady state)
  fitted to Figure 1's Cx45 small-ion curve, and the same law against the miRNA curve.
* figure3: two equal linear cells (unloaded 5 and 10) joined by G_GJ = g G_eq, g = 0.5 ... 50.
* figure5: Figure 5b's lumped model (cell B 4/3 cell A) and Figure 5a's seven-cell network.
* figure8: straight chains of 1-5 and 10 cells, each loaded at its port by two held
  concentrations; the Norton conductance G_eq,n from the two steady states.
* control: figure3 at g = 1 with every junction permeability x1.01, judged against g = 1's
  reference: the comparison must catch it.

Criteria, fixed before any run (CRITERIA):
  E1 engine against the dense solve of the same network: relative error <= 1e-9 in every cell;
  E2 steady state: relative change over the last SETTLE_S seconds <= 1e-12 in every cell;
  E3 the probe flux from the engine's own membrane ledger against G_probe (c - held): relative
     error <= 1e-9;
  E4 Figure 8: the engine's G_eq,n against the physical chain's recursion: relative <= 1e-8;
  P1 the closed forms against the preprint's printed or read values, within the reading
     tolerances paper.REPORTED states (a check of the reading, not of the engine);
  P2 Figure 8: the engine's G_eq,n against the recursion Figure 8 plots and against its read
     values (reported: the expected outcome is agreement at n <= 2 and disagreement from n = 3);
  K1 the planted control fails E1 (by more than 1e-6);
  A1 the engine's own run checks pass (material balance and every step check: a run that fails
     one raises, and is recorded as failed).

Engine models run: resolved_pump_tissue@3 with constant_field@1 membranes and junctions for one
neutral species, held reservoirs, junction_voltage_relaxation@1 pinned open, closed by
resolved_capacitor_components_current_continuity@1, integrated by
imex_ars222_face_electromigration@1 (worlds.py). Definition probes: local_species_reactions@1 in
resolved_pump_composite@1, and the law registry.

Usage (from a snapshot root, PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu):
    python -B validation/gap_junction_tissue/run.py OUTDIR [part ...]
"""

import json
import math
import platform
import sys
import time
import traceback
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import numpy as np  # noqa: E402

import cells  # noqa: E402,F401
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
FIGURE5_G = (1.0, 10.0, 100.0)
FIGURE8_N = (1, 2, 3, 4, 5, 10)
FIGURE8_LOADS = (0.5, 2.0)  # Held concentrations at the port (mM); the unloaded value is 1.
PLANTED_SCALE = 1.01
PARTS = ("refusals", "gate", "figure3", "figure5", "figure8", "control")


def reference(cells_, edges, probes):
    """The dense solve of the same network (paper.linear_steady_state), in SI units."""
    conductance = [size * worlds.G_EQ1_M3_S for _, _, size in cells_]
    unloaded = [u for _, u, _ in cells_]
    dense_edges = [(i, j, g * worlds.G_EQ1_M3_S) for _, i, j, g in edges]
    dense_probes = [(i, g * worlds.G_EQ1_M3_S, held) for _, i, held, g in probes]
    return paper.linear_steady_state(conductance, unloaded, dense_edges, dense_probes)


def run_network(cells_, edges, probes, *, junction_scale=1.0):
    """Run one linear network to steady state; return the engine's readouts and the reference."""
    raw = worlds.linear_network(cells_, edges, probes, junction_scale=junction_scale)
    spec = parse_spec(raw)
    started = time.perf_counter()
    result = runner.run(spec)
    seconds = time.perf_counter() - started
    times = np.asarray(result.times)
    end, before = spec.experiment.end_time, spec.experiment.end_time - worlds.SETTLE_S
    rows = {t: int(np.flatnonzero(times == t)[0]) for t in (before, end)}
    layout, history = result.final.layout, result.history
    volume = np.asarray(layout.volume)[: len(cells_)]
    reference_amount = np.asarray(layout.amount_reference)[0, : len(cells_)]

    def concentration(t):
        increment = np.asarray(history.amount_increment[rows[t]])[0, : len(cells_)]
        return (reference_amount + increment) / volume  # fmol / pL = mM

    c_end, c_before = concentration(end), concentration(before)
    c_ref, flux_ref = reference(cells_, edges, probes)
    out = dict(
        dt_s=spec.execution.dt,
        steps=int(round(end / spec.execution.dt)),
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
    return out


def _number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _checks(arm, criteria):
    arm["E1"] = arm["engine_rel_error"] <= criteria["E1_engine_vs_dense_rtol"]
    arm["E2"] = arm["steady_rel_change"] <= criteria["E2_steady_rtol"]
    if "ledger_rel_error" in arm:
        arm["E3"] = arm["ledger_rel_error"] <= criteria["E3_ledger_flux_rtol"]
    return arm


def part_refusals():
    from cells.models.inner_laws import HOST
    from cells.registry import laws as law_registry

    out = {}
    for name, permeability in (("with_junction_route", 1e-9), ("without_junction_route", 0.0)):
        try:
            parse_spec(worlds.junction_route_reaction(permeability))
            out[name] = dict(accepted=True)
        except ConfigError as error:
            out[name] = dict(accepted=False, refusal=str(error))
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
    for name, n in (("at_bound", bound - 1), ("over_bound", bound)):
        try:
            parse_spec(worlds.shared_bath(n))
            out[f"shared_bath_{name}"] = dict(cells=n, accepted=True)
        except ConfigError as error:
            out[f"shared_bath_{name}"] = dict(cells=n, accepted=False, refusal=str(error))
    out["verdict"] = dict(
        junction_route_reaction_refused=not out["with_junction_route"]["accepted"]
        and out["without_junction_route"]["accepted"],
        only_relaxation_junction_law=out["hosted_laws"]["junction"]
        == ["junction_voltage_relaxation@1"],
        three_d_lattice_over_bound=not out["preprint_lattices"]["3D_25x25x25"]["within"]
        and out["shared_bath_at_bound"]["accepted"]
        and not out["shared_bath_over_bound"]["accepted"],
    )
    return out


def part_gate():
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
    return dict(
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


def part_figure3():
    rep = paper.REPORTED["figure3b"]
    arms = []
    for g in FIGURE3_G:
        arm = run_network(*worlds.figure3(g, rep["unloaded"]))
        a, b = paper.eq2(*rep["unloaded"], g, g)
        arm.update(
            g=g,
            eq2=[a, b],
            eq2_vs_dense=float(
                max(abs(a - arm["reference_mM"][0]), abs(b - arm["reference_mM"][1]))
            ),
        )
        arms.append(_checks(arm, CRITERIA))
    a1, b1 = paper.eq2(*rep["unloaded"], 1.0, 1.0)
    limit = 0.5 * sum(rep["unloaded"])
    reading = dict(
        at_g1_closed_form=[a1, b1],
        at_g1_read=list(rep["at_g1"]),
        P1_at_g1=bool(
            max(abs(a1 - rep["at_g1"][0]), abs(b1 - rep["at_g1"][1])) <= rep["tolerance"]
        ),
        limit_closed_form=limit,
        P1_limit=bool(abs(limit - rep["limit"]) <= rep["tolerance"]),
    )
    return dict(arms=arms, reading=reading)


def part_figure5():
    rep = paper.REPORTED["figure5"]
    ua, ub = rep["unloaded"]["A"], rep["unloaded"]["B"]
    lumped, network = [], []
    for g in FIGURE5_G:
        arm = run_network(*worlds.figure5_lumped(g, rep["size_ratio"], (ua, ub)))
        arm.update(g=g, eq2=list(paper.eq2(ua, ub, g, g / rep["size_ratio"])))
        lumped.append(_checks(arm, CRITERIA))
        arm = run_network(*worlds.figure5_network(g, (ua, ub)))
        arm.update(g=g)
        network.append(_checks(arm, CRITERIA))
    limit = (ua + rep["size_ratio"] * ub) / (1.0 + rep["size_ratio"])
    reading = dict(
        limit_closed_form=limit,
        caption_final=rep["final"],
        P1_final=bool(abs(limit - rep["final"]) <= rep["tolerance"]),
        text_ratio_1p5_limit=(ua + 1.5 * ub) / 2.5,
    )
    return dict(lumped=lumped, network=network, reading=reading)


def part_figure8():
    rep = paper.REPORTED["figure8"]
    physical = paper.chain_physical(1.0, 1.0, max(FIGURE8_N))
    plotted = paper.chain_paper(1.0, 1.0, max(FIGURE8_N))
    chains = []
    for n in FIGURE8_N:
        loads = [run_network(*worlds.chain(n, held)) for held in FIGURE8_LOADS]
        points = [(arm["exit_flux_mol_s"], arm["port_mM"]) for arm in loads]
        g_m3_s, unloaded = paper.norton_from_two_loads(points)
        ratio = g_m3_s / worlds.G_EQ1_M3_S
        entry = dict(
            n=n,
            loads=[_checks(arm, CRITERIA) for arm in loads],
            g_eq_ratio=ratio,
            unloaded_mM=unloaded,
            physical_ratio=physical[n - 1],
            plotted_ratio=plotted[n - 1],
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
        chains.append(entry)
    return dict(
        chains=chains,
        physical_limit_ratio=paper.chain_limit(1.0, 1.0),
        recursion_note=paper.RECURSION_NOTE,
    )


def part_control():
    arm = run_network(*worlds.figure3(1.0), junction_scale=PLANTED_SCALE)
    arm["junction_scale"] = PLANTED_SCALE
    # Judged against the unperturbed g = 1 network's dense solve.
    unperturbed = reference(*worlds.figure3(1.0))[0]
    error = float(
        np.max(np.abs(np.asarray(arm["concentration_mM"]) - unperturbed) / np.abs(unperturbed))
    )
    arm.update(unperturbed_reference_mM=unperturbed.tolist(), planted_rel_error=error)
    arm["K1"] = bool(
        error > CRITERIA["K1_planted_min_rel_error"] and error > CRITERIA["E1_engine_vs_dense_rtol"]
    )
    return arm


FUNCTIONS = dict(
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
            solver=worlds.SOLVER,
        ),
        citation=paper.CITATION,
    )
    (out_dir / "plan.json").write_text(json.dumps(plan, indent=1, default=str))
    record = dict(
        python=sys.version,
        platform=platform.platform(),
        jax=jax.__version__,
        blas=blas_threads.libraries(),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    results = dict(record=record, parts={})
    for part in parts:
        started = time.perf_counter()
        try:
            results["parts"][part] = dict(status="done", result=FUNCTIONS[part]())
        except Exception as error:  # Recorded as failed evidence, never retried silently.
            results["parts"][part] = dict(
                status="failed", error=repr(error), traceback=traceback.format_exc()
            )
        results["parts"][part]["seconds"] = time.perf_counter() - started
        (out_dir / "results.json").write_text(json.dumps(results, indent=1, default=str))
        print(
            part,
            results["parts"][part]["status"],
            f"{results['parts'][part]['seconds']:.1f} s",
            flush=True,
        )
    results["record"]["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, default=str))
    failed = [p for p, r in results["parts"].items() if r["status"] != "done"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
