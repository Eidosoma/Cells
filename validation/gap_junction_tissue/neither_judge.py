"""GJ-N1, the "neither" threshold comparison: its rule, the reader of its references and its judge.

docs/GJ_NEITHER_REGISTRATION.md is the authority; this module is its arithmetic and
neither_rule.json (written by `rule`) every number. The engine's search (validation/
gap_junction_tissue/neither.py) for the smallest junction diffusion constant D of miR200 at which
healthy tissue normalizes a tumor, on BITSEY's 1x1x25 line and 1x25x25 field, is judged against a
code-blind reference: an independent integration of the registered equations (MODEL), read
through its interface alone (`interface_schema`). BITSEY's own outputs, its saved historical logs
and a pinned run at b2cb370 (validation/gap_junction_tissue/bitsey_run.py), are reported beside it
(bitsey_log.read). The reader exists at the registration's tag (D308).

**The verdict, per geometry** (D219: successful refinement and a predeclared convergence condition
are part of it, and no ratio alone judges):
- R, refinement: the search ends converged (hi <= (1 + 1e-3) lo) with every point run (none
  refused), outcomes monotone in D, D = 0 not normalized and D = 1e-13 normalized.
- C, convergence in the step: the final bracket's two ends, rerun at half their step, keep their
  outcomes. Then the threshold at dt/2 lies in the same bracket, and at second order the limit
  dt -> 0 lies within a third of the bracket's width of it.
- A, agreement: Cells' interval [lo - w/3, hi + w/3] (w = hi - lo) and the reference's bracket,
  verified at a ten-fold tighter tolerance, overlap.
- Verdicts: failed if R fails by a refused point or a wrong bracket end, or if R and C pass and A
  fails; inconclusive if the outcomes are not monotone or C fails (one retry, below); else
  passed. Overall, any failed geometry makes it failed, else any inconclusive inconclusive.

**Reported, never judged** (B): BITSEY's brackets at full precision, from the `Now doing Kd=` lines
of each log, their overlap with Cells' interval, the ratio of the thresholds, and the outcomes at
the points both evaluated. BITSEY integrates by explicit adaptive Euler (each step's change capped
at 0.1%), whose effect on a threshold has no a priori bound; the code-blind reference measures it,
and if A passes, agreement with BITSEY within that measured deviation follows.

Commands (PYTHONPATH=src:. JAX_ENABLE_X64=1):
- python -m validation.gap_junction_tissue.neither_judge rule --out FILE
- python -m validation.gap_junction_tissue.neither_judge spec --out FILE  (the references' input)
- python -m validation.gap_junction_tissue.neither_judge cells RUN_DIR --geometry line|field
- python -m validation.gap_junction_tissue.neither_judge judge --line RUN_DIR [--field RUN_DIR]
  [--interface DIR] [--bitsey-line LOG ...] [--bitsey-field LOG ...] --out FILE
"""

import argparse
import hashlib
import json
from pathlib import Path

from validation.gap_junction_tissue import bitsey_log, neither

HERE = Path(__file__).resolve().parent
RULE_FILE = HERE / "neither_rule.json"
INTERFACE = HERE / "references" / "interface"
INTERFACE_FILE = "neither.json"
REFERENCE_FORMAT = "gap_junction_tissue.neither_references@1"
REGISTRATION = "docs/GJ_NEITHER_REGISTRATION.md"
PROPOSED_TAG = "gj-neither-registered-2026-11-23"
GEOMETRIES = ("line", "field")
CONSTANT_MATCH = 1e-12  # Relative: the interface's echo of a registered constant.
TIGHTER = 10.0  # The reference's bracket ends are checked again at a ten-fold tighter tolerance.
BITSEY_REVISION = "b2cb370aaecbc8299f259bc4251d5396c81f19a6"
HISTORICAL_LOGS = {
    "line": dict(
        file="cancer_GJ_sims/results_miRNA/tumor_isolate_1D_V1M",
        command="zombie.py zombie_tumor_isolate 1 1 25 0 (its first line)",
        revision="earlier than b2cb370: its search is titled 'lowest Kd that fixes a 1-spot', "
        "which no committed revision from 04225e4 (20 May 2026) on prints; its result line "
        "'Final NR=0' is 04225e4's format, not b2cb370's",
    ),
    "field": dict(
        file="cancer_GJ_sims/results_miRNA/tumor_isolate_2D_V1M",
        command="zombie.py zombie_tumor_isolate 1 25 25 0 (its first line)",
        revision="earlier than b2cb370: its result line 'Final NR=0: ...' is 04225e4's format "
        "(20 May 2026); b2cb370 prints '0. Final underexp=0.3: ...'. GRN_miRNA.py and sim.py "
        "differ between 04225e4 and b2cb370 in comments and one equivalent expression only; "
        "zombie.py's protocol code changed",
    ),
}
SAVED_LOGS = Path("/mnt/workspaces/Cells/gap-junction-20261117/downloads/bitsey-results-b2cb370")
PINNED_RUN = dict(
    runner="validation/gap_junction_tissue/bitsey_run.py",
    revision=BITSEY_REVISION,
    environment="/mnt/workspaces/Cells/venv-bitsey (numpy 2.3.5, scipy 1.16.3, matplotlib 3.10.7, "
    "Python 3.13)",
    line="zombie_tumor_isolate 1 1 25 0 0 1",
    field="zombie_tumor_isolate 1 25 25 0 0 1, stopped once the first search has printed its "
    "result",
    licence="none at b2cb370 or at the newest head (7e4fb45d, 22 November 2026); seven tracked "
    "files point to a LICENSE that does not exist; the user's D208 was ruled knowing this",
)


class ComparisonError(ValueError):
    """A comparison that cannot be made as registered: a refusal, never a pass or a fail."""


# --- The registered model ----------------------------------------------------------------------

MODEL = dict(
    species=dict(u="miR200 (total)", m="Zeb mRNA (total)", z="ZEB protein"),
    units="scaled units: one unit is 1 uM in the engine's world; time in s (BITSEY's unit)",
    equations=[
        "du/dt = g_u H(z; K_u, n_u, lambda_u) - k_u u + (junction terms, u only)",
        "dm/dt = g_m H(z; K_m, n_m, lambda_m) - k_m m",
        "dz/dt = g_z m sum_{i=0..6} C(6, i) l_i X^i / (1 + X)^6 - k_z z, X = u / x0",
        "H(z; K, n, lambda) = (1 + lambda (z/K)^n) / (1 + (z/K)^n)",
        "junction (a, b): its flux G (u_a - u_b) leaves a and enters b; G / V = D A_cell / "
        "(L_GJ V_cell) = 3 D / (r L_GJ)",
    ],
    constants=dict(
        g_u=neither.U_SYNTHESIS,
        K_u=neither.U_HILL[0],
        n_u=neither.U_HILL[1],
        lambda_u=neither.U_HILL[2],
        k_u=neither.DECAY["u"],
        g_m=neither.M_SYNTHESIS,
        K_m=neither.M_HILL[0],
        n_m=neither.M_HILL[1],
        lambda_m=neither.M_HILL[2],
        k_m=neither.DECAY["m"],
        g_z=neither.Z_TRANSLATION,
        x0=neither.X0_UNITS,
        l=list(neither.L_SITES),
        k_z=neither.DECAY["z"],
        radius_m=neither.R_CELL_M,
        junction_length_m=neither.L_GJ_M,
        g_over_v_per_d=3.0 / (neither.R_CELL_M * neither.L_GJ_M),
    ),
    constants_source="BITSEY's cancer_GJ_sims/GRN_miRNA.py at b2cb370 (numbers only, D208), "
    "scaled as it scales them, with Snail = 72 folded into g_u = 6 (1 + 0.4)/2 and g_m = "
    "(5/12)(1 + 10)/2; ITERATE = False, so the binding uses total miR200",
    seeds=dict(
        tumor=dict(u=neither.TRACE_UNITS, m=100.0, z=100.0),
        healthy=dict(u=100.0, m=neither.TRACE_UNITS, z=neither.TRACE_UNITS),
        note="BITSEY seeds 0 where these are 1e-6 (the engine needs positive amounts)",
    ),
    stages=dict(
        uncoupled_s=neither.UNCOUPLED_S,
        coupled_s=neither.COUPLED_S,
        rule="stage 1: one tumor cell and one healthy cell, no junctions, 500 s from the seeds, "
        "once; every tumor cell of stage 2 starts at stage 1's tumor end state, every healthy "
        "cell at its healthy one; stage 2 runs 20,000 s coupled, its clock from 0",
    ),
    criterion=dict(
        cell=f"u > m + {neither.MARGIN_UNITS:g} at the end of stage 2, in every cell",
        rows=f"for every row, max m - min m <= {neither.ROW_SPREAD_UNITS:g}; a row is the cells "
        "with one z (the last lattice index)",
        source="BITSEY's GRN_miRNA.py healthy_snapped_rows (line 519), on the whole field",
    ),
)
GEOMETRY = dict(
    line=dict(
        lattice="1 x 1 x 25: cells c0..c24 along z",
        tumor="z < 6 (c0..c5)",
        junctions="c_k - c_(k+1), k = 0..23",
        rows="each cell is its own row, so the spread condition is empty",
        neighbours=2,
        nodes=26,
    ),
    field=dict(
        lattice="1 x 25 x 25: cell c{y}_{z}, y and z in 0..24",
        tumor="y < 6 and z < 6 (a 6 x 6 block at the corner)",
        junctions="one per pair one lattice step apart (c{y}_{z} - c{y}_{z+1} and "
        "c{y}_{z} - c{y+1}_{z}), 1,200 in all; no diagonals",
        rows="row z holds c0_z .. c24_z",
        neighbours=4,
        nodes=626,
    ),
)


def search_rule():
    return dict(
        bracket=list(neither.BRACKET),
        ends="D = 0 must not normalize and D = 1e-13 must; both are run",
        stop=f"hi <= (1 + {neither.RTOL:g}) lo, hi the smallest normalizing D and lo the largest "
        "below it that does not; reported x2 = hi",
        placement="one point per CPU; the first points are the bracket's ends and dyadic points "
        "1e-13/2^k, k from 1 on the line and from 4 on the field (the largest that runs at the "
        "base step, neither.first_points); then each finished worker takes a new point inside "
        "the current bracket (neither.place)",
        step="per point, dt = 1/8 s halved until dt x 2 x neighbours x G/V <= 0.04 "
        "(neither.step); stage 1 at the shape's finest coupled step (1/64 s on the line, 1/128 s "
        "on the field)",
        convergence="the final bracket's two ends rerun at half their step (C)",
        retry="if C fails, the whole search once more at half the step rule, with its own C at a "
        "quarter; if that C fails too, the geometry is inconclusive. A run the harness stops is "
        "rerun once from the same snapshot; an engine refusal is a result. neither.py's search "
        "has no step option yet: a retry needs a tagged amendment adding it before it runs "
        "(D308)",
    )


def rule():
    """The rule as data (written to neither_rule.json and tagged before any judged run)."""
    return dict(
        format="gap_junction_tissue.neither_rule@1",
        registration=REGISTRATION,
        proposed_tag=PROPOSED_TAG,
        engine_models=[
            "resolved_pump_composite@1 over resolved_pump_tissue@3 (the species-only world of the "
            "secreted-species fixtures: ions at the bath's composition with zero permeability)",
            "local_species_reactions@1: the switch, per cell",
            "cells.passive_routes@1 with passive_neutral_permeation@1: miR200 alone on each "
            "junction, P A = G (no routes at D = 0)",
            "junction_voltage_relaxation@1 pinned open; "
            "resolved_capacitor_components_current_continuity@1; "
            "imex_ars222_face_electromigration@1 with capacitive_reduction_gauged_damped_newton@2",
        ],
        model=MODEL,
        geometry=GEOMETRY,
        search=search_rule(),
        verdicts=dict(
            R="refinement: converged, no refused point, monotone, both ends as required",
            C="the final bracket's ends keep their outcomes at half their step",
            A="Cells' [lo - w/3, hi + w/3] overlaps the reference's bracket (verified at a "
            "ten-fold tighter tolerance)",
            geometry="failed if a point is refused, a bracket end is wrong, or A fails with R and "
            "C passed; inconclusive if the outcomes are not monotone or C fails after its retry; "
            "else passed",
            overall="any failed geometry makes it failed; else any inconclusive makes it "
            "inconclusive; else any not assessable makes it not assessable; else passed (D308)",
            no_ratio_alone="no ratio of thresholds judges (D219)",
        ),
        plants=plant_rows(),
        reported=dict(
            bitsey="the historical logs and the pinned run, each bracket at full precision, its "
            "overlap with Cells' interval, the ratio hi_Cells / hi_BITSEY and the outcomes at "
            "common points; never judged",
            logs={
                name: dict(log, sha256=_saved_sha256(log)) for name, log in HISTORICAL_LOGS.items()
            },  # fmt: skip
            pinned_run=PINNED_RUN,
            seen_values="the 1D log's bracket [7.171630859375e-15, 7.177734375e-15] and the 2D "
            "log's [1.8859863281250003e-15, 1.8875122070312503e-15], read before this rule",
        ),
        interface=interface_schema(),
        not_blind=not_blind(),
        compute_budget=compute_budget(),
    )


def not_blind():
    return dict(
        line=(
            "Not blind (D219): the registrant's development search neither-02 (from 1f4c740a, 17 "
            "November) converged at x2 = 7.177734375e-15 m^2/s, bracket [7.176208496e-15, "
            "7.177734375e-15], 37 points, the half-step check passed; neither-01, picks-01/-02, "
            "dense-01 and ladder-01 ran the line at many D values. These conditions were written "
            "after; the judged run repeats the search fresh from the tag."
        ),
        field=(
            "A true pre-registration (D219): no 25 x 25 world has run past 16 s. Seen before this "
            "rule: BITSEY's whole 2D bisection in its saved log (bracket 1.886e-15 to 1.888e-15); "
            "sheet-01, a different world (9 x 9, a central 3 x 3 tumor, 2,000 s), whose threshold "
            "lay between 9.0e-16 and 1.8e-15; field-parse-01, a parse with no integration; and "
            "the cost probe field-cost-01: D = 1e-13 for 1.5 s and D = 0 for 16 s, where every "
            "tumor cell was still mesenchymal and every healthy cell epithelial (589 of 625), "
            "which cannot show a threshold; the smokes probes/smoke-registered-01 (a field point, "
            "D = 1e-13 for 0.25 s; a field search and a line search at 0.25 s and 2 s, each "
            "stopped at its upper end); and the pinned BITSEY field run's first five outcomes (D "
            "= 0 not normalized; 1e-13, 5e-14, 2.5e-14 and 1.25e-14 normalized), as in the "
            "historical log"
        ),
    )


def compute_budget():
    return dict(
        measured="field-cost-01 on today's engine (main db54d0f5), one CPU: the field takes "
        "0.16-0.19 s a step (with or without routes; 32- and 16-step windows, 1.3 GB), the line "
        "3.4 ms a step; the first window's compile 72-77 s",
        line="as neither-02: about 37 points, 8 CPU-hours; the upper end's 1.28 million steps "
        "(72 minutes) are the critical path; on four light CPUs about 2-3 hours",
        field="a base-step point (1/8 s, 160,000 steps) takes 7-8.5 hours; the upper end (1/128 "
        "s, 2.56 million steps) 4.7-5.6 days; the search with its convergence check about "
        "350-410 CPU-hours. It does not fit the light CPUs; the field runs when the lead "
        "assigns the compute, or after an amendment tagged before it runs",
        memory="the line 1.2 GB a worker, the field 1.3 GB a worker",
    )


def plant_rows():
    return [
        dict(id="P-A1", what="a reference bracket 1% above Cells' interval",
             expected="A fails"),
        dict(id="P-A2", what="a reference bracket inside Cells' widened interval but outside "
             "its bracket", expected="A passes: the margin is the stated w/3"),
        dict(id="P-R1", what="a refused point in Cells' search", expected="the geometry fails"),
        dict(id="P-R2", what="non-monotone outcomes", expected="the geometry is inconclusive"),
        dict(id="P-C1", what="a half-step rerun that flips an outcome",
             expected="the geometry is inconclusive"),
        dict(id="P-I1", what="a reference bracket wider than 1.001",
             expected="refused before comparison"),
        dict(id="P-I2", what="a reference whose bracket ends flip at the tighter tolerance",
             expected="refused before comparison"),
        dict(id="P-I3", what="a reference echoing a different constant (Snail's g_u 4.0)",
             expected="refused before comparison"),
    ]  # fmt: skip


# --- What the references read, and the interface they write ------------------------------------

SPEC_FILE = HERE / "references" / "spec" / "neither.json"


def spec():
    """What the code-blind references read (references/spec/neither.json): the model, the
    geometries, the criterion, the search and the interface, with no run's or log's value."""
    search = search_rule()
    return dict(
        format="gap_junction_tissue.neither_spec@1",
        registration=REGISTRATION,
        model=MODEL,
        geometry=GEOMETRY,
        search=dict(
            bracket=search["bracket"],
            ends=search["ends"],
            stop=search["stop"],
            placement="free: any sequence of points that narrows the bracket to the stopping "
            "rule, every point integrated from stage 1's end state over the full 20,000 s",
            tighter="the final bracket's two ends again at a ten-fold tighter integration "
            "tolerance; both must keep their outcomes",
        ),
        interface=interface_schema(),
    )


# --- The references' interface ----------------------------------------------------------------


def interface_schema():
    return dict(
        file=f"validation/gap_junction_tissue/references/interface/{INTERFACE_FILE}",
        format=REFERENCE_FORMAT,
        keys=dict(
            format=REFERENCE_FORMAT,
            registration="the tag the references read",
            model="{constants: {every key of model.constants, each value as read}, seeds: "
            "{tumor: {u, m, z}, healthy: {u, m, z}} as read from model.seeds}",
            stage1="{tumor: {u, m, z}, healthy: {u, m, z}} after 500 s uncoupled",
            geometries="{line, field}: {bracket: [lo, hi], points: [{d, normalized, "
            "epithelial_cells, min_margin, max_row_spread}], tighter: {factor, lo_normalized, "
            "hi_normalized}, method}; a geometry the references did not compute is absent and is "
            "then not assessable",
        ),
        conditions=[
            f"hi <= (1 + {neither.RTOL:g}) lo",
            "lo not normalized and hi normalized, in points and again at the tighter tolerance",
            "points monotone in d, with 0 not normalized and 1e-13 normalized",
        ],
    )


def read_interface(directory=INTERFACE):
    """The references' interface, checked: format, the echoed model, and per geometry present its
    bracket, points and tighter check. A mismatch is refused (ComparisonError)."""
    path = Path(directory) / INTERFACE_FILE
    if not path.is_file():
        raise ComparisonError(f"No interface at {path}")
    data = json.loads(path.read_text())
    if data.get("format") != REFERENCE_FORMAT:
        raise ComparisonError(f"Interface format {data.get('format')!r}, not {REFERENCE_FORMAT}")
    echoed = (data.get("model") or {}).get("constants") or {}
    for key, value in MODEL["constants"].items():
        other = echoed.get(key)
        values = value if isinstance(value, list) else [value]
        others = other if isinstance(other, list) else [other]
        if len(values) != len(others) or not all(
            isinstance(b, (int, float)) and abs(b - a) <= CONSTANT_MATCH * max(1.0, abs(a))
            for a, b in zip(values, others, strict=True)
        ):
            raise ComparisonError(f"The echoed constant {key} is {other!r}, registered {value!r}")
    seeds = (data.get("model") or {}).get("seeds") or {}
    for kind in ("tumor", "healthy"):
        for species in ("u", "m", "z"):
            value = MODEL["seeds"][kind][species]
            other = (seeds.get(kind) or {}).get(species)
            if not isinstance(other, (int, float)) or abs(other - value) > CONSTANT_MATCH * max(
                1.0, abs(value)
            ):
                raise ComparisonError(f"The echoed seed {kind} {species} is {other!r}")
    for name, entry in (data.get("geometries") or {}).items():
        if name not in GEOMETRIES:
            raise ComparisonError(f"Unknown geometry {name!r}")
        lo, hi = entry.get("bracket") or (None, None)
        if not (isinstance(lo, float) and isinstance(hi, float) and 0 < lo < hi):
            raise ComparisonError(f"{name}: no bracket")
        if hi > (1.0 + neither.RTOL) * lo * (1.0 + 1e-12):
            raise ComparisonError(f"{name}: bracket {lo:.6g}-{hi:.6g} wider than 1 + 1e-3")
        points = sorted((p["d"], bool(p["normalized"])) for p in entry.get("points") or [])
        outcomes = [ok for _, ok in points]
        if outcomes != sorted(outcomes):
            raise ComparisonError(f"{name}: the reference's outcomes are not monotone in d")
        by_d = dict(points)
        if by_d.get(0.0) is not False or by_d.get(neither.BRACKET[1]) is not True:
            raise ComparisonError(f"{name}: the reference's bracket ends are not as required")
        if by_d.get(lo) is not False or by_d.get(hi) is not True:
            raise ComparisonError(f"{name}: the bracket's ends are not among its points as stated")
        tighter = entry.get("tighter") or {}
        if not (
            tighter.get("factor", 0) >= TIGHTER
            and tighter.get("lo_normalized") is False
            and tighter.get("hi_normalized") is True
        ):
            raise ComparisonError(f"{name}: the bracket ends change at the tighter tolerance")
    return data


# --- Cells' search -----------------------------------------------------------------------------


def cells(run_dir):
    """R and C of one engine search (neither.py's search.json, points.jsonl, half_step.jsonl)."""
    run_dir = Path(run_dir)
    state = json.loads((run_dir / "search.json").read_text())
    points = [json.loads(x) for x in (run_dir / "points.jsonl").read_text().splitlines() if x]
    halves_path = run_dir / "half_step.jsonl"
    halves = [json.loads(x) for x in halves_path.read_text().splitlines() if x] if (
        halves_path.is_file()) else []  # fmt: skip
    refused = sorted(p["d"] for p in points if p["status"] != "done")
    done = sorted((p["d"], p["normalized"]) for p in points if p["status"] == "done")
    outcomes = [ok for _, ok in done]
    by_d = dict(done)
    normalizing = [d for d, ok in done if ok]
    hi = min(normalizing) if normalizing else None
    lo = max((d for d, ok in done if not ok and (hi is None or d < hi)), default=None)
    converged = lo is not None and hi is not None and hi <= (1.0 + neither.RTOL) * lo
    ends = by_d.get(neither.BRACKET[0]) is False and by_d.get(neither.BRACKET[1]) is True
    monotone = outcomes == sorted(outcomes)
    half = {h["d"]: h for h in halves}
    c_ok = (
        converged
        and lo in half
        and hi in half
        and half[lo].get("status") == "done"
        and half[hi].get("status") == "done"
        and half[lo]["normalized"] is False
        and half[hi]["normalized"] is True
    )
    return dict(
        run_dir=str(run_dir),
        shape=state.get("shape", "line"),
        points=len(points),
        refused=refused,
        monotone=monotone,
        ends_as_required=ends,
        converged=converged,
        lo=lo,
        hi=hi,
        stopped=state.get("stopped"),
        R=bool(converged and not refused and monotone and ends),
        C=bool(c_ok),
        half_step={
            str(d): dict(normalized=h.get("normalized"), status=h.get("status"), dt_s=h.get("dt_s"))
            for d, h in half.items()
        },  # fmt: skip
        outcomes={f"{d:.17g}": ok for d, ok in done},
    )


def interval(result):
    """Cells' interval for the converged threshold: [lo - w/3, hi + w/3] (module docstring)."""
    w = result["hi"] - result["lo"]
    return result["lo"] - w / 3.0, result["hi"] + w / 3.0


def geometry_verdict(result, reference):
    """R, C and A for one geometry (module docstring)."""
    out = dict(R=result["R"], C=result["C"], lo=result["lo"], hi=result["hi"])
    if result["refused"] or not result["ends_as_required"]:
        return dict(out, status="failed", reason="a refused point or a wrong bracket end")
    if not result["monotone"]:
        return dict(out, status="inconclusive", reason="the outcomes are not monotone in D")
    if not result["converged"]:
        return dict(out, status="inconclusive", reason="the search did not converge")
    if not result["C"]:
        return dict(out, status="inconclusive", reason="an end changed its outcome at half step")
    if reference is None:
        return dict(out, status="not assessable", reason="the references did not compute it")
    a, b = interval(result)
    lo_r, hi_r = reference["bracket"]
    overlap = max(a, lo_r) <= min(b, hi_r)
    out.update(interval=[a, b], reference_bracket=[lo_r, hi_r], A=overlap,
               ratio_to_reference=result["hi"] / hi_r)  # fmt: skip
    return dict(out, status="passed" if overlap else "failed")


def bitsey_rows(result, logs):
    """B, reported: each BITSEY log's first search against Cells' interval (module docstring)."""
    rows = []
    a, b = interval(result) if result.get("lo") is not None else (None, None)
    for path in logs:
        data = bitsey_log.read(path)
        search = data["searches"][0]
        bracket = search["bracket"]
        common = [p for p in search["points"] if f"{p['d']:.17g}" in result["outcomes"]]
        rows.append(dict(
            log=str(path),
            sha256=data["sha256"],
            field=data["field"],
            strategy=search["strategy"],
            bracket=[bracket["lo"], bracket["hi"]],
            printed_bracket=search["printed_bracket"],
            overlaps_cells_interval=None if a is None else (
                max(a, bracket["lo"]) <= min(b, bracket["hi"])),
            ratio_cells_to_bitsey=None if result.get("hi") is None else (
                result["hi"] / bracket["hi"]),
            common_points=len(common),
            common_outcomes_agree=sum(
                p["fixed"] == result["outcomes"][f"{p['d']:.17g}"] for p in common),
        ))  # fmt: skip
    return rows


def judge(results, interface, bitsey=None):
    """The comparison's verdict: per geometry R, C and A, and B reported (module docstring)."""
    bitsey = bitsey or {}
    refs = (interface or {}).get("geometries") or {}
    verdicts = {}
    for name, result in results.items():
        verdicts[name] = geometry_verdict(result, refs.get(name))
        if result.get("lo") is not None:
            verdicts[name]["reported_bitsey"] = bitsey_rows(result, bitsey.get(name, []))
    statuses = [v["status"] for v in verdicts.values()]
    overall = (
        "failed" if "failed" in statuses
        else "inconclusive" if "inconclusive" in statuses
        else "not assessable" if "not assessable" in statuses
        else "passed"
    )  # fmt: skip
    return dict(format="gap_junction_tissue.neither_verdict@1", verdict=overall,
                geometries=verdicts)  # fmt: skip


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _saved_sha256(log):
    """The saved copy's sha256 (SAVED_LOGS, read at b2cb370), or None where it is not present."""
    saved = SAVED_LOGS / Path(log["file"]).name
    return _sha256(saved) if saved.is_file() else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rule").add_argument("--out", required=True)
    sub.add_parser("spec").add_argument("--out", required=True)
    c = sub.add_parser("cells")
    c.add_argument("run_dir")
    j = sub.add_parser("judge")
    j.add_argument("--line")
    j.add_argument("--field")
    j.add_argument("--interface", default=str(INTERFACE))
    j.add_argument("--bitsey-line", nargs="*", default=[])
    j.add_argument("--bitsey-field", nargs="*", default=[])
    j.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "rule":
        out = rule()
    elif args.command == "spec":
        out = spec()
    elif args.command == "cells":
        print(json.dumps(cells(args.run_dir), indent=1))
        return 0
    else:
        results = {k: cells(v) for k, v in (("line", args.line), ("field", args.field)) if v}
        interface = read_interface(args.interface)
        bitsey = dict(line=args.bitsey_line, field=args.bitsey_field)
        out = judge(results, interface, bitsey)
    Path(args.out).write_text(json.dumps(out, indent=1, allow_nan=False) + "\n")
    print(out.get("verdict", out["format"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
