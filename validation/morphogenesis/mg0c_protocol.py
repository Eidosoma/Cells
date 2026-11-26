"""MG0c's qualification protocol (D152 version 1): its draft from disclosed runs and registration.

docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §6.4, with §11 to §11.4. The protocol
(validation/morphogenesis/protocols/mg0c_turing_v1.json) is PROPOSED. It was drafted here from the
development runs named in it, and revised after the lead's review with the advisor (14 November
2026, review); its criteria, thresholds, registered deltas and development values come from those
runs. The rules carry over D150's reviewed and registered protocol
(validation/tissue/secreted_species_protocol.json and its module):
- S5's dt-study rule per element and record;
- the observed orders with their stop rules;
- judged controls by parameter at registered deltas;
- the attempt rule, with the judged entries' guard, judge-guards and combine.

Only the lead registers it, through register, which changes the status and adds the lead's
registration record alone.

The judged entries are the driver's (validation/morphogenesis/mg0c_turing.py: registered, their
first call; judge, judge-guards, combine; rules.judge_entries). Every judged criterion is
evaluated by validation/morphogenesis/mg0a_gradient.evaluate (metric paths, comparisons,
thresholds; a missing metric fails its criterion).

Usage:
  python -m validation.morphogenesis.mg0c_protocol draft OUTPUT_JSON RESULTS_JSON [...]
      [--guards GUARDS_OUT] [--basis RESULTS_JSON [...]]
      each RESULTS_JSON a complete run of the driver (development, or the rehearsal's on a
      registered dry-run copy), in order: a later run's part replaces an earlier run's, each
      part's run recorded; GUARDS_OUT a judge-guards output directory, for the guards' timing;
      --basis the development runs the thresholds and deltas were first derived from, named in
      development_runs.basis and refused unless they give the same criteria, thresholds,
      registered deltas and controls
  python -m validation.morphogenesis.mg0c_protocol register PROTOCOL_JSON RECORD_JSON
      the lead's registration: RECORD_JSON is the lead's record (its status begins 'registered')
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from validation.morphogenesis import mg0c_turing as mg
from validation.morphogenesis.mg0a_gradient import _lookup, evaluate

STATUS = (
    "PROPOSED (drafted 14 November 2026 by the D152 engine agent, revised the same day after the "
    "lead's review with the advisor (review), from {source} named in development_runs; not "
    "registered, and no judged run is made before the lead registers it)"
)
JUDGED_PARTS = (
    "d147",
    "theory",
    "linear",
    "floor",
    "q1",
    "q2",
    "q3",
    "q4",
    "q5",
    "q6",
    "q7",
    "sites",
)
DT_JUDGED = (mg.dt_key(mg.DTS[0]), mg.dt_key(mg.DTS[1]))  # Each with its half: the step term.
LINEARISED_MAP_DT = mg.dt_key(mg.DTS[0])  # Ruling 3: judged at 50 ms, with its control.
LINEARISED_MAP_TOLERANCE = 1e-6  # Ruling 3.
RATE_TOLERANCE = dict(q2=1e-3, q3=1e-2)  # Ruling 4, against the discrete-time rate.
DOMINANT_FROM_S = 500.0  # Q3: the predicted mode dominates from this record to the end.
CONTROL_FACTOR = 10.0  # D150's: a registered delta is 10 x the smallest caught in development.
SMALL_DELTA = 1e-2  # Ruling (c): a kept control's registered delta is at most this (1 %).
GUARD_TESTS = (  # Judged (judge-guards); reference-independent or against independent references.
    "tests/unit/test_species_reactions.py",
    "tests/unit/test_species_reactions_refusals.py",
    "tests/unit/test_species_reactions_halfstep.py",
    "tests/unit/test_species_reactions_against_references.py",
    "tests/unit/test_species_reactions_runs.py",
    "tests/unit/test_species_reactions_guards.py",
    "tests/unit/test_species_reactions_reference_runs.py",
    "tests/unit/test_species_reactions_composition.py",
    "tests/unit/test_mg0c_judged_refusal.py",
    "tests/unit/test_reaction_references.py",
)
REGRESSION_GUARDS = {  # Tier 3, not judged (rulings 7 and 10).
    "tests/unit/test_species_reactions_same_material.py": (
        "ruling 10: its exchange map is the engine agent's own, written from D150's documented "
        "law (one author on both sides, as D150's step map)"
    ),
    "tests/unit/test_species_reactions_accuracy.py": (
        "ruling 7: §11.1's pins, the scheme's accuracy against the exact node kinetics, with loose "
        "bounds; the mixed-node heat and work split is guarded, not qualified, until the first "
        "mixed-node protocol"
    ),
}
GUARDS_DEVELOPMENT = dict(  # The guard files' seconds before the split (evidence, not a run part).
    seconds={
        "test_species_reactions_guards.py": 315,
        "test_species_reactions_runs.py": 310,
        "test_species_reactions_reference_runs.py": 329,
        "test_species_reactions_composition.py": 802,
        "the six tier-1 files": 31,
    },
    peak_GB=3.28,
    evidence=(
        "/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/tests/: "
        "final-5de1c96-guards, final-5de1c96-runs and m3-3e7399a (the tier-3 files under load, "
        "before the review's split); tests/test_tiers.json (the tier-1 files)"
    ),
)
UNIT_B_MEMORY = (  # Why unit b keeps a 5 GiB cap until the rehearsal (the round-2 reruns).
    "q7 alone peaked at 1.8 GB and q6 alone at 0.87 GB (cgroup peaks, dev-7495288-q7 and -q6), "
    "so the old unit b's 3.5 GB (q6, q3, q5 and q7 in one process) was not q7's batch alone; "
    "unit b is that run's prefix, so its peak is at most 3.5 GB, but unmeasured"
)
UNITS = dict(  # Ruling 9: q7 alone, with a cap of at least 5 GiB; unit b too (UNIT_B_MEMORY).
    a=dict(parts=["d147", "theory", "timing", "linear", "floor", "q1", "q2", "sites"], cpu=5),
    b=dict(parts=["q6", "q3", "q5"], cpu=7, min_cap_GiB=5),
    q7=dict(parts=["q7"], cpu=7, min_cap_GiB=5),
    c=dict(parts=["q4"], cpu=5),
    guards=dict(entry="judge-guards", cpu=7, min_cap_GiB=5),  # Proposed (GUARDS_MEMORY).
)
LANES = (  # As the rehearsal ran them, each successor launched by hand when its lane is free.
    "CPU 5: unit a, then unit c; CPU 7: unit b, then q7, then judge-guards; then judge and "
    "combine, which run nothing"
)
SCOPE = (
    "MG0c's judged arms run cells.operator.local_species_reactions@1's driven mass action only, of "
    "orders 0, 1 "
    "and 3 (Schnakenberg's four reactions; guard 2's open world and the sites world, orders 0 and "
    "1), at outside nodes, with cells.model.resolved_pump_tissue@3's species transport on faces in "
    "cells.model.resolved_pump_composite@1, with five species per world (three quiescent ions and "
    "the "
    "network's two), within the 7 species the scope stays at: D150's cap of 16 since FR-9 / D165 "
    "is not exercised. One judged guard world departs from driven mass action, kept judged at "
    "the lead's answer (review.answers): guard 2's passive world runs "
    "cells.species_reaction.ideal_detailed_balance_mass_action@1 "
    "(A <-> B, linear) at outside nodes, judged against the engine order's exact map. Every other "
    "use of "
    "the passive law, Michaelis-Menten, Hill factors, cell routes, D150's writers and the "
    "mixed-node heat and work split enters only through test files; the heat and work split is "
    "guarded, not qualified, until the first mixed-node protocol. A qualified statement from this "
    "protocol carries this scope"
)
REVIEW = dict(
    by="the lead with the advisor, 14 November 2026, on the PROPOSED draft landed at e659ce4",
    rulings={
        "1": "accepted: a batch of seeds on L/l = 6, bitwise against its reverse and within 1e-12 "
        "of each scalar run (Q7_batch, Q7_batch_scalar)",
        "2": "accepted: the 600 s cap; it binds in Q5 only (cap_binds_in_q5)",
        "3": "the linearised-map tolerance 1e-6, judged at 50 ms with a judged control from the "
        "other side: the exact propagator must fail it there (Q1_linearised_map_control); the "
        "25 and 12.5 ms values reported (reported_not_judged). The 4.55 ratio (findings)",
        "4": "accepted: Q2 at 1e-3 and Q3 at 1e-2 against the discrete-time rate; Q5's fitted "
        "rates reported only",
        "5": "accepted, with the smallest top-two gap against the fit tolerance reported and near "
        "ties excluded up front (Q4_staircase; q4_near_ties)",
        "6": "accepted: Q6's controls at rtol 1e-12",
        "7": "§11.1's pins are regression guards with loose bounds, not judged "
        "(test_species_reactions_accuracy.py), and the scope line says the heat and work split "
        "is guarded, not qualified",
        "8": "the usage note's rule, 1e-14 x steps x the scale (disclosures)",
        "9": "q7 in its own unit, with a cap of at least 5 GiB (development_runs.units); q7 alone "
        "peaked at 1.8 GB, so unit b keeps a 5 GiB cap too until the rehearsal measures it "
        "(resources)",
        "10": "split by file: the same-material test is a regression guard outside the judged "
        "list; supply counted once, the rejected step, restart and batch stay judged guards",
    },
    blocking={
        "a": "the scope line (scope), with guard 2's passive world named (question 1, answered: it "
        "stays judged)",
        "b": "D150's pre-registration amendments carried over: judge-guards with its own verdict, "
        "uncapped per file; one combine verdict; the attempt rule's infrastructure endings; "
        "rules.timing; register with the lead's record, read by the guard; why the control "
        "criteria are evaluable only in a judged run (rules.controls_evaluable)",
        "c": "controls by parameter (rules.controls; controls.coverage, controls.removed)",
        "d": "§6.4's amplitude corrected to a defined, measured quantity, and the prototype's 0.68 "
        "identified as another measure, time and start (findings.amplitude; the design note's "
        "§6.4 and §11.4)",
    },
    d147="done and recorded: every MG0c world has 0 free field offsets with solver @2 (d147)",
    answers_by=(
        "the lead, 14 November 2026, landing the revision at main 58b6f14 (the combined landing "
        "f0e154a)"
    ),
    answers={
        "1": "keep guard 2's passive world judged, with the disclosure: both candidate rules pass "
        "on the development runs (the usage note's at 0.008 to 0.021, D150's at 0.96), so the "
        "choice was about fragility, not the outcome; the final check before registration can "
        "revisit it",
        "2": "yes, the split is intended: the true-kinetics heat and work comparisons against "
        "dr.integrate_node are regression guards of record; the judged guards keep the "
        "rounding-level agreement with nr.run_half_steps and the passive relaxation's total heat; "
        "the scope line's 'guarded, not qualified' is right",
    },
    confirmed=[
        "Q4_near_ties_as_registered",
        "every kept control must catch",
        "unit b at 5 GiB or more until the rehearsal measures it",
        "controls.at_grid_floor",
        "§6.4's Q7 row",
        "the refusal test on a PROPOSED copy",
    ],
    accepted_disclosures=[
        "the 1e-2 cutoff relative to mg0c/checks-r2.json",
        "the development runs predating FR-9",
    ],
    rehearsal_asked=(
        "record unit b's peak and Q6's re-integrated control catches, and run every control's "
        "passing path on the registered dry-run copy"
    ),
)
REHEARSAL_COMPARISON = (  # The rehearsal against development (evidence, not a run part).
    "mg0c/compare_rehearsal.py -> rehearsal-58b6f14/compare-a.json, -b, -q7 and -c in "
    "/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/: every part identical but "
    "Q6's controls_integrations, 38 against 32, the registered deltas' extra re-integrations; Q4's "
    "near-tie leaves are the judged run's own, equal to those derived at drafting"
)
DISCLOSURES = [
    "Guard 2's rule (ruling 8), 1e-14 x steps x the scale from REFERENCES_USAGE.md, was chosen "
    "with D150's steps x eps x the scale in view, at which the development's passive world sits at "
    "0.96 (8,000 steps at 12.5 ms); the long-double iteration shows that rounding is the engine's "
    "own, linear in steps",
    "The small-delta cutoff (a kept control's registered delta at most 1e-2) and Q4's fit "
    "tolerance (Q3's 1e-2) were fixed before the a, b and D_U thresholds were measured, but with "
    "the k and D_V thresholds, Q4's top-two gaps and every Q1 mode's slow-eigenvalue sensitivity "
    "to all five parameters in view (mg0c/checks-r2.json, written before the cutoff); those "
    "sensitivities estimate the thresholds to within about 5 x (controls.removed)",
    "The development runs came from snapshots before FR-9 (D165, the species cap raised to 16). "
    "This protocol is drafted from the rehearsal's runs on main 58b6f14 (FR-9 and the combined "
    f"landing included), which reproduce them at every non-timing leaf ({REHEARSAL_COMPARISON})",
]
GUARDS_MEMORY = (  # Proposed for the judged run from the rehearsal's peak (the lead decides).
    "judge-guards peaked at 3.18 GB in the rehearsal under a 4 GiB cap; 5 GiB is proposed for the "
    "judged run by ruling 9's reasoning"
)
QUESTIONS = []  # Questions 1 and 2 are answered (review.answers), as asked:
ASKED = [
    "1. The scope line: guard 2's passive world runs the passive law in judged criteria "
    "(G2_passive_*), against the lead's 'driven mass action only'. Ruling 8 rules on that very "
    "criterion (D150's 0.96 is the passive world's ratio), so this draft keeps it judged and "
    "names it in the scope line. Keep it so, or move it to the guards "
    "(test_species_reactions_composition.py already runs it, 10 s)?",
    "2. Ruling 7's consequence: with §11.1's pins in test_species_reactions_accuracy.py, the "
    "comparisons of heat and work against the true kinetics (dr.integrate_node: the share onset, "
    "the background guard, the crossing, the reversal onset) leave the judged list. The judged "
    "guards keep dissipation as rounding-level agreement with nr.run_half_steps (the same "
    "half-steps) and the passive relaxation's total heat against dr.passive_equilibrium's drop "
    "(1e-12). The coordinator's milestone-3 instruction kept the independent kinetic and "
    "dissipation comparisons as guards of record: is this split what the lead intends?",
]
CHECKS_R2 = (  # The round-2 host check behind the 4.55 answer (evidence, not a run part).
    "/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/mg0c/checks-r2.json: the "
    "linearised engine-order map alone (cr.strang_mode_map, K = k J) against the exact propagator "
    "at L/l = 6, n = 6 gives 1.27e-3, 2.79e-4 and 6.61e-5 at 50, 25 and 12.5 ms (ratios 4.549 and "
    "4.223), with dt D_V lambda_6 = 0.40 at 50 ms"
)
PROTOTYPE_B2 = (  # §6.4's 0.68 u0, identified in the prototype's record (evidence, not a run part).
    "the prototype's B2 (/mnt/workspaces/Cells/shared-inventory-reactions-20261114-01/probe2/: "
    "reaction_numerics_probe.py part_b2, probe2.json B2_nonlinear_pattern) recorded the range "
    "(max u - min u) / u* at 1500 s, from its own start (1e-3 relative noise on U and V, seed "
    "20261114): 0.678 to 0.679 at 50 to 12.5 ms on L/l = 11, its reference 0.679"
)


def _peak_gb(results_path):
    """The unit's cgroup memory peak, in GB: inside the run's directory (mg0c/dev.sh) or beside it
    as DIR.memory.peak (mg0c/rehearse_entry.sh, since a judged entry's directory is its own)."""
    folder = Path(results_path).parent
    for path in (folder / "memory.peak", folder.with_name(folder.name + ".memory.peak")):
        try:
            return round(int(path.read_text().split()[0]) / 1e9, 2)
        except (OSError, ValueError, IndexError):
            continue
    return None


def _rehearsal(runs):
    """Whether every run is a judged-form run (the rehearsal's, on a registered dry-run copy)."""
    return all(str(run.get("status", "")).startswith("Judged run of") for run in runs)


def linearised_map_summary(parts):
    """Ruling 3's figures per dt over Q1's eighteen modes: the worst floor (the engine against the
    linearised map) and the smallest discretisation error (the engine against the exact
    propagator), each with its mode."""
    out = {}
    for dt in mg.DTS:
        key = mg.dt_key(dt)
        rows = [
            (q1_entry[key]["against_linearised_map"], q1_entry[key]["against_exact"], f"L{L}_{n}")
            for L in (6, 11, 16)
            for n, q1_entry in parts["q1"][mg.key("L", L)].items()
            if n.startswith("n")
        ]
        floor = max(rows, key=lambda r: r[0])
        exact = min(rows, key=lambda r: r[1])
        out[key] = dict(
            worst_floor=floor[0],
            worst_floor_at=floor[2],
            smallest_against_exact=exact[1],
            smallest_against_exact_at=exact[2],
            floor_margin=LINEARISED_MAP_TOLERANCE / floor[0],
            control_margin=exact[1] / LINEARISED_MAP_TOLERANCE,
        )
    return out


def findings(parts):
    """The answers the review asked for, from the runs (and, for the 4.55, the round-2 check)."""
    entry = parts["q1"][mg.key("L", 6)]["n6"]
    ratios = entry["exact_ratios"]
    floor = entry[mg.dt_key(mg.DTS[0])]["against_linearised_map"]
    q3 = {L: parts["q3"][mg.key("L", L)]["saturated_amplitude_of_c_star"] for L in (6, 11, 16)}
    return dict(
        ratio_4_55=(
            f"Q1's {ratios[0]:.3g} (L/l = 6, n = 6, the 50 and 25 ms pair; then {ratios[1]:.3g}) "
            "is the scheme's higher-order term, not the floor: the map alone against the exact "
            f"propagator gives the same ratios ({CHECKS_R2}); the floor there is {floor:.2g} at "
            "50 ms, under 1e-3 of the engine's 50 ms error"
        ),
        amplitude=(
            "MG0c's measure: max over nodes of |u - mean(u)| at the last record (3000 s), in c* "
            "(u* = c*), in the reference's own integration of Q6's start on L/l = 11 "
            "(cr.integrate_chain, rtol 1e-13; amplitude_end_of_c_star): "
            f"{parts['q6']['amplitude_end_of_c_star']:.3g}. Q3's saturated_amplitude_of_c_star "
            "(max over nodes of |u - u*| at its end, the engine): "
            + ", ".join(f"{v:.3g} on L/l = {L}" for L, v in q3.items())
            + f". §6.4's '0.68 u0' is another measure, time and start: {PROTOTYPE_B2}. Reported, "
            "not judged"
        ),
    )


def merged(paths):
    """Every judged part from a complete development run, a later run's part replacing an earlier
    run's; each part's run recorded. Q4's near-tie verdict is derived with the driver's own
    q4_verdict where a run predates it."""
    parts, origin, runs = {}, {}, []
    for path in paths:
        data = json.loads(Path(path).read_text())
        if data.get("quick"):
            raise SystemExit(f"Refused: {path} is a quick run")
        if data.get("complete") is False:
            raise SystemExit(f"Refused: {path} is incomplete")
        for name, value in data["parts"].items():
            if not value.get("ok"):
                raise SystemExit(f"Refused: part {name} failed in {path}")
            parts[name], origin[name] = value, str(path)
        runs.append(
            dict(
                path=str(path),
                status=data.get("status"),
                source=data["source"],
                parts=sorted(data["parts"]),
                peak_GB=_peak_gb(path),
            )
        )
    missing = sorted(set(JUDGED_PARTS) - set(parts))
    if missing:
        raise SystemExit(f"Refused: the development runs lack parts {missing}")
    if "all_agree_outside_near_ties" not in parts["q4"]:
        parts["q4"] = dict(parts["q4"], **mg.q4_verdict(parts["q4"]["points"]))
        parts["q4"]["q4_verdict_derived"] = "by mg0c_turing.q4_verdict at drafting"
    results = dict(parts=parts)
    results["accounting_summary"] = mg.accounting_summary(results)
    return results, runs, origin


def snap_up(value):
    """The smallest point of the driver's 1-2-5 grid at or above value (the value past the grid)."""
    return next((d for d in mg.DELTAS if d >= value * (1 - 1e-12)), value)


def criterion(id_, metrics, comparison, threshold, basis):
    return dict(id=id_, metrics=metrics, comparison=comparison, threshold=threshold, basis=basis)


def _control_items(parts):
    """(item path, dt key, the rule's summary at dt, its scale, the Q1 entry or None) for every
    controlled rule."""
    for L in (6, 11, 16):
        for n in range(1, 7):
            entry = parts["q1"][mg.key("L", L)][f"n{n}"]
            rule = entry["dt_rule"]
            for dt in DT_JUDGED:
                yield f"q1.{mg.key('L', L)}.n{n}", dt, rule[dt], rule["scale"], entry
    rule = parts["q6"]["dt_rule"]
    for dt in DT_JUDGED:
        yield "q6", dt, rule[dt], rule["scale"], None


def controls_by_parameter(parts):
    """Ruling (c): per parameter, the kept controls (registered at 10 x the smallest caught delta,
    at most SMALL_DELTA) and the removed ones with their reasons; refused unless every parameter
    keeps at least one."""
    kept, removed, deltas, at_floor = {p: [] for p in mg.PARAMETERS}, [], {}, []
    for item, dt, rule, scale, entry in _control_items(parts):
        floor = mg.Q6_GRID[0] if item == "q6" else mg.DELTAS[0]  # Each item's lowest grid point.
        for p in mg.PARAMETERS:
            control = rule["controls"][p]
            if not control["rule_passes_unperturbed"]:
                raise SystemExit(f"Refused: {item} {dt}'s rule fails unperturbed")
            smallest = control["smallest_caught"]
            name = f"{item}.{dt}.{p}"
            if smallest is not None and CONTROL_FACTOR * smallest <= SMALL_DELTA * (1 + 1e-12):
                deltas[name] = snap_up(CONTROL_FACTOR * smallest)
                kept[p].append(name)
                if abs(smallest - floor) <= 1e-9 * floor:
                    at_floor.append(name)
                continue
            reason = dict(
                control=name,
                smallest_caught=smallest,
                why=(
                    "not caught on the grid"
                    if smallest is None
                    else f"caught only at {smallest:g}: 10 x is above the small-delta cutoff "
                    f"{SMALL_DELTA:g}"
                ),
            )
            if entry is not None:
                structure = entry["mode_structure"]
                sensitivity = structure["slow_log_sensitivity_times_record"][p]
                step = rule["max_step_term"] / scale
                predicted = 3 * step / max(sensitivity, 1e-300)  # The rule's tolerance over it.
                reason.update(
                    slow_log_sensitivity_times_record=sensitivity,
                    fast_over_slow_at_first_record=structure.get("fast_over_slow_at_first_record"),
                    predicted_threshold=predicted,
                )
                if smallest is not None and predicted / 5 <= smallest <= 5 * predicted:
                    fast = structure.get("fast_over_slow_at_first_record")
                    factor = max(predicted / smallest, smallest / predicted)
                    reason["why"] += (
                        f"; the mode's slow eigenvalue moves by |d lambda / d ln {p}| t = "
                        f"{sensitivity:.3g} over its record, so a delta shifts the coefficient by "
                        f"about {sensitivity:.3g} delta against the rule's tolerance of about 3 x "
                        f"its step term ({3 * step:.2g}): a threshold of about {predicted:.2g}, "
                        f"within {factor:.1f} x of the measured one"
                        + (
                            f"; the fast component has decayed to {fast:.2g} of the slow one "
                            "by the first record"
                            if fast is not None
                            else ""
                        )
                    )
            removed.append(reason)
    lacking = [p for p, names in kept.items() if not names]
    if lacking:
        raise SystemExit(f"Refused: no kept control for parameters {lacking}")
    criteria = [
        criterion(
            f"Control_{p}",
            [
                f"parts.{name.rsplit('.', 1)[0].replace('.dt', '.dt_rule.dt', 1)}"
                f".controls.{p}.caught_at_registered"
                for name in names
            ],
            "ge",
            1,
            f"{p} times (1 + delta) in the reference, at each kept control's registered delta "
            "(10 x its smallest caught delta, at most 1e-2), fails that rule somewhere: the rule "
            "can fail for an error in this parameter",
        )
        for p, names in kept.items()
    ]
    coverage = {
        p: dict(
            kept=len(names),
            smallest_registered_delta=min(deltas[n] for n in names),
            largest_registered_delta=max(deltas[n] for n in names),
        )
        for p, names in kept.items()
    }
    floor_note = (
        "each of these is caught at its grid's lowest point, so its threshold lies at or below "
        "it and its registered delta is at least 10 x the threshold (measured)"
    )
    if at_floor and all(n.startswith("q6.") and n.rsplit(".", 1)[1] in "ab" for n in at_floor):
        arrays = parts["q6"]["arrays"]
        tolerances = [float(np.min(arrays["tolerances"][dt])) for dt in DT_JUDGED]
        floor_note += (
            ". Why, inferred from the tolerances, not measured: on Q6, a and b set the uniform "
            "state (u* = (a + b) c*, v* = b c* / (a + b)^2), which k and the diffusivities do "
            "not, so a change of delta moves every element by order delta c* from the start, "
            "while at the early records, where the pattern is still small, the per-element "
            "tolerance falls toward the reference term (its smallest "
            f"{min(tolerances):.2g} mM over the records, against elements of order "
            f"{mg.C_STAR_MM:g} mM); the floor catch is consistent with that"
        )
    out = dict(kept=kept, removed=removed, coverage=coverage)
    out["at_grid_floor"] = dict(controls=at_floor, note=floor_note) if at_floor else {}
    return criteria, deltas, out


BOUNDS = ("energy_over_bound", "material_over_bound")


def criteria_for(parts):
    """The judged criteria (metric paths into the judged runs' merged results.json)."""
    out = [
        criterion(
            "D147_no_free_field_offsets",
            ["parts.d147.max_free_field_offsets"],
            "le",
            0,
            "D147: a definition with free field offsets declares field solver @3, and since D156 a "
            "composite follows its inner model (@3, in D147's family); every MG0c world has none "
            "(each chain node shares the cell's capacitor component with the held bath), so the "
            "declared @2 stands. The count is checked here because MG0c's worlds are declared "
            "with @2, not through the automatic choice",
        )
    ]
    for world in ("passive", "open"):
        base = f"parts.linear.{world}"
        out += [
            criterion(
                f"G2_{world}_engine_order_map",
                [f"{base}.{mg.dt_key(dt)}.map_over_usage_note_rule" for dt in mg.DTS],
                "le",
                1.0,
                "|engine - strang_mode_map iterated| <= 1e-14 x steps x the scale at every "
                "record (REFERENCES_USAGE.md's accumulation; ruling 8, disclosures): the "
                "composite's order P(dt/2) I(dt) P(dt/2) with @3's species transport, mode by mode",
            ),
            criterion(
                f"G2_{world}_dt_rule",
                [f"{base}.dt_rule.{dt}.max_ratio" for dt in DT_JUDGED],
                "le",
                1.0,
                "S5's dt-study rule against propagate_modes (exact), per element and record",
            ),
            criterion(
                f"G2_{world}_orders",
                [f"{base}.dt_rule.stop_rule_differences_decrease"],
                "ge",
                1,
                "every measurable step-term difference decreases (the orders are reported)",
            ),
            criterion(
                f"G2_{world}_accounting",
                [f"{base}.{mg.dt_key(dt)}.accounting.{k}" for dt in mg.DTS for k in BOUNDS],
                "le",
                1.0,
                "the energy and the network rows' material residuals inside their host bounds",
            ),
        ]
    modes = [f"n{n}" for n in range(1, 7)]
    maps = linearised_map_summary(parts)[LINEARISED_MAP_DT]
    for L in (6, 11, 16):
        base = f"parts.q1.{mg.key('L', L)}"
        out += [
            criterion(
                f"Q1_L{L}_linearised_map",
                [f"{base}.{n}.{LINEARISED_MAP_DT}.against_linearised_map" for n in modes],
                "le",
                LINEARISED_MAP_TOLERANCE,
                "ruling 3: the engine against the linearised engine-order map (strang_mode_map "
                "with K = k J) at 50 ms, relative to each record's largest coefficient, within "
                f"1e-6 ({maps['floor_margin']:.2g} x over the worst development floor, "
                f"{maps['worst_floor']:.2g} at {maps['worst_floor_at']})",
            ),
            criterion(
                f"Q1_L{L}_dt_rule",
                [f"{base}.{n}.dt_rule.{dt}.max_ratio" for n in modes for dt in DT_JUDGED],
                "le",
                1.0,
                "S5's dt-study rule against mode_propagator (exact for the linearised system)",
            ),
            criterion(
                f"Q1_L{L}_orders",
                [f"{base}.{n}.dt_rule.stop_rule_differences_decrease" for n in modes],
                "ge",
                1,
                "every measurable step-term difference decreases (the orders are reported)",
            ),
        ]
    out.append(
        criterion(
            "Q1_linearised_map_control",
            [
                f"parts.q1.{mg.key('L', L)}.{n}.{LINEARISED_MAP_DT}.against_exact"
                for L in (6, 11, 16)
                for n in modes
            ],
            "ge",
            LINEARISED_MAP_TOLERANCE,
            "ruling 3's control from the other side: the exact propagator, offered as the "
            "linearised map, fails Q1's linearised-map criterion at 50 ms for every mode (the "
            f"smallest development value {maps['smallest_against_exact']:.2g} at "
            f"{maps['smallest_against_exact_at']}, {maps['control_margin']:.2g} x above the "
            "tolerance)",
        )
    )
    p = parts
    out += [
        criterion(
            "Q2_never_above_start",
            ["parts.q2.max_deviation_never_above_start"],
            "ge",
            1,
            "no admissible unstable mode on L/l = 8: the deviation from uniform never exceeds its "
            "start",
        ),
        criterion(
            "Q2_slowest_mode",
            ["parts.q2.slowest_mode", "parts.q2.dominant_mode_at_end"],
            "within",
            [p["q2"]["slowest_mode"], p["q2"]["slowest_mode"]],
            "the slowest-decaying admissible mode (the references' discrete rates) dominates at "
            "the end",
        ),
        criterion(
            "Q2_rate",
            ["parts.q2.rate_relative_difference"],
            "le",
            RATE_TOLERANCE["q2"],
            "the slowest mode's fitted decay rate against the engine order's discrete-time rate",
        ),
    ]
    for L in (6, 11, 16):
        base = f"parts.q3.{mg.key('L', L)}"
        expected = p["theory"]["domains"][mg.key("L", L)]["fastest"]
        out += [
            criterion(
                f"Q3_L{L}_dominant",
                [f"{base}.expected_mode", f"{base}.dominant_at_end"],
                "within",
                [expected, expected],
                "the only admissible unstable mode (tu.fastest_admissible_mode, discrete at h) "
                "dominates at saturation",
            ),
            criterion(
                f"Q3_L{L}_dominant_from",
                [f"{base}.dominant_from_s"],
                "le",
                DOMINANT_FROM_S,
                "and from the linear phase on: it is the dominant mode at every record from 500 s",
            ),
            criterion(
                f"Q3_L{L}_rate",
                [f"{base}.rate_relative_difference"],
                "le",
                RATE_TOLERANCE["q3"],
                "its fitted growth rate in the linear phase against the engine order's "
                "discrete-time rate (sigma_n reported beside it)",
            ),
        ]
    q4 = p["q4"]
    if q4["near_ties_excluded"]:
        raise SystemExit("Refused: Q4 has near ties; register them before drafting a criterion")
    out += [
        criterion(
            "Q4_staircase",
            ["parts.q4.all_agree_outside_near_ties"],
            "ge",
            1,
            "at every L/l from 4 to 30 (step 0.5) outside the near ties excluded up front from the "
            "references alone (ruling 5: none), the fastest-growing single-mode start on the "
            "engine is the discrete argmax of sigma_n (none at 4 and 7.5 to 8.5), and the growing "
            "set is the admissible unstable set",
        ),
        criterion(
            "Q4_near_ties_as_registered",
            ["parts.q4.smallest_gap_over_allowance"],
            "ge",
            1.0,
            "the near ties, from the references' predicted rates alone, are as registered: none, "
            "so no length is excluded (in development the smallest top-two gap is "
            f"{q4['smallest_gap_over_allowance']:.3g} x its allowance, at L/l = "
            f"{q4['smallest_gap_L']:g})",
        ),
    ]
    for L in (6, 8, 11, 16):
        base = f"parts.q5.{mg.key('L', L)}"
        out += [
            criterion(
                f"Q5_L{L}_decays",
                [f"{base}.{n}.decays" for n in modes],
                "ge",
                1,
                "d = 8 < d_c: every single-mode start decays",
            ),
            criterion(
                f"Q5_L{L}_dt_rule",
                [f"{base}.{n}.dt_rule.{DT_JUDGED[0]}.max_ratio" for n in modes],
                "le",
                1.0,
                "at its predicted rate: S5's dt-study rule against mode_propagator at d = 8",
            ),
        ]
    out += [
        criterion(
            "Q6_dt_rule",
            [f"parts.q6.dt_rule.{dt}.max_ratio" for dt in DT_JUDGED],
            "le",
            1.0,
            "S5's dt-study rule against cr.integrate_chain (DOP853 at rtol 1e-13, its own term "
            "|rtol 1e-12 - rtol 1e-13|), per node, species and record, to saturation",
        ),
        criterion(
            "Q6_orders",
            ["parts.q6.dt_rule.stop_rule_differences_decrease"],
            "ge",
            1,
            "every measurable step-term difference decreases (the orders are reported)",
        ),
        criterion(
            "Q7_face_free",
            ["parts.q7.face_free.energy_over_rounding"],
            "le",
            1.0,
            "the face-free world (§3.4 guard 1, MG0c's network): the energy residual within 2.5 "
            "eps x steps x the energy magnitudes at every row",
        ),
        criterion(
            "Q7_restart",
            ["parts.q7.restart_bitwise"],
            "ge",
            1,
            "restart through a written snapshot read in a fresh process: bitwise",
        ),
        criterion(
            "Q7_batch",
            ["parts.q7.batch_bitwise_against_reverse"],
            "ge",
            1,
            "ruling 1: a vector batch of seeds on L/l = 6, bitwise against the reversed batch",
        ),
        criterion(
            "Q7_batch_scalar",
            ["parts.q7.batch_against_scalar_relative"],
            "le",
            1e-12,
            "ruling 1: each world within 1e-12 of its scalar run (§6.5)",
        ),
        criterion(
            "Q7_accounting",
            [
                "accounting_summary.max_energy_over_bound",
                "accounting_summary.max_material_over_bound",
            ],
            "le",
            1.0,
            "every run that records its accounting (every part's but Q4's, whose single-mode runs "
            "record only their rates): the energy residual and the network rows' material "
            "residuals (at the species' floors) inside their host bounds. Every run of every part, "
            "Q4's included, also passes every host check on every window, or it raises and its "
            "part fails",
        ),
        criterion(
            "S_dt_rule",
            [f"parts.sites.dt_rule.{dt}.max_ratio" for dt in DT_JUDGED],
            "le",
            1.0,
            "reactions at several sites with their own multipliers (one at zero) on the chain: "
            "S5's dt-study rule against cr.integrate_chain with the same [R, N] multipliers",
        ),
        criterion(
            "S_orders",
            ["parts.sites.dt_rule.stop_rule_differences_decrease"],
            "ge",
            1,
            "every measurable step-term difference decreases",
        ),
    ]
    return out


def development_values(protocol, results):
    """Each criterion's development values and its development verdict (not judged). A control's
    caught_at_registered exists only in a run with the registered deltas loaded (rules.
    controls_evaluable): there the development's smallest caught deltas stand beside them."""
    from validation.tissue import judge_harness  # The empty-metric guard (the review's finding 4).

    judge_harness.refuse(judge_harness.metrics(protocol["criteria"], results))
    verdict = evaluate(dict(criteria=protocol["criteria"]), results)
    out = {}
    for v, c in zip(verdict["criteria"], protocol["criteria"], strict=True):
        if c["id"].startswith("Control_"):
            out[v["id"]] = dict(
                evaluable="in a run with the registered deltas loaded only (caught_at_registered)",
                smallest_caught_in_development=[
                    _lookup(results, m.replace("caught_at_registered", "smallest_caught"))
                    for m in c["metrics"]
                ],
            )
            if all(x is not None for x in v["values"]):  # A run on a registered copy.
                out[v["id"]].update(passed=v["passed"], values=v["values"])
        else:
            out[v["id"]] = dict(passed=v["passed"], values=v["values"])
    return out


def unit_timing(results, runs, origin, guards=None):
    """Seconds per judged unit (the parts' own seconds in the runs drafted from) and the runtime
    limits at about 3 x them plus 10 min; the units' peaks. The guards' from a judge-guards verdict
    directory when given (its files' seconds; its peak beside it), else GUARDS_DEVELOPMENT."""
    seconds = {n: results["parts"][n]["seconds"] for n in results["parts"]}
    measured_in = "the rehearsal on main" if _rehearsal(runs) else "development"
    out = {}
    for unit, spec in UNITS.items():
        if "parts" not in spec:
            continue
        total = sum(seconds.get(n, 0.0) for n in spec["parts"])
        out[unit] = dict(
            development_seconds=round(total),
            runtime_max_seconds=int(3 * total + 600),
            measured_in=measured_in,
            source_runs=sorted({origin[n] for n in spec["parts"] if n in origin}),
        )
    peaks = {run["path"]: run["peak_GB"] for run in runs}
    if guards is None:
        total, source = sum(GUARDS_DEVELOPMENT["seconds"].values()), GUARDS_DEVELOPMENT["evidence"]
        peaks["guards"], guards_measured = GUARDS_DEVELOPMENT["peak_GB"], "development"
    else:
        verdict = json.loads((Path(guards) / "verdict.json").read_text())
        total = sum(f["seconds"] for f in verdict["files"])
        source = str(Path(guards) / "verdict.json")
        peaks["guards"] = _peak_gb(Path(guards) / "verdict.json")
        guards_measured = "the rehearsal on main" if _rehearsal(runs) else "a judge-guards run"
    out["guards"] = dict(
        development_seconds=round(total),
        runtime_max_seconds=int(3 * total + 600),
        measured_in=guards_measured,
        source=source,
    )
    return dict(units=out, development_peaks_GB=peaks)


def unit_b_memory(runs, origin):
    """Unit b's cap (ruling 9's reasoning, the lead's confirmation until measured) with its peak."""
    path = origin.get("q6")
    peak = next((r["peak_GB"] for r in runs if r["path"] == path), None)
    if peak is None or not _rehearsal(runs):
        return UNIT_B_MEMORY
    return (
        f"its peak in the rehearsal on main was {peak:g} GB, measured as the lead asked; the cap "
        "stays at 5 GiB, as confirmed until measured, since a cap kill would spend the single "
        "rerun (the lead may lower it at the final check)"
    )


def q4_near_ties(q4):
    """Ruling 5's report: the near ties excluded up front (from the references alone), the
    smallest top-two gap against its allowance, the sign margin, and the fits' accuracy for each
    length's smallest-|rate| candidate (what a sign rests on)."""
    marginal, every = [], []
    for point in q4["points"]:
        predicted, fitted = point["predicted_discrete_time_rates_per_s"], point["rates_per_s"]
        relative = {n: abs(fitted[n] - v) / abs(v) for n, v in predicted.items()}
        every += relative.values()
        n = min(predicted, key=lambda m: abs(predicted[m]))
        marginal.append((relative[n], point["L"], int(n)))
    worst = max(marginal)
    every.sort()
    out = dict(
        fit_tolerance=mg.Q4_FIT_TOLERANCE,
        excluded=q4["near_ties_excluded"],
        smallest_gap_over_allowance=q4["smallest_gap_over_allowance"],
        smallest_gap_L=q4.get("smallest_gap_L"),
        smallest_gap_per_s=q4.get("gap"),
        smallest_sign_margin=q4["smallest_sign_margin"],
        smallest_sign_margin_L=q4.get("smallest_sign_margin_L"),
        smallest_rate_fit_largest_relative_difference=worst[0],
        smallest_rate_fit_largest_at=dict(L=worst[1], mode=worst[2]),
        every_fit_median_relative_difference=every[len(every) // 2],
    )
    below = out["smallest_sign_margin"] < 1
    out["note"] = (
        (
            f"the sign margin is below 1 at L/l = {out['smallest_sign_margin_L']:g}: a "
            "near-marginal candidate's |rate| is under 1e-2 of the fastest one's there. "
            if below
            else "the sign margin is at least 1 at every length. "
        )
        + "A sign rests on each candidate's own fit, and each length's smallest-|rate| candidate "
        f"fits its predicted rate to at most {worst[0]:.2g} relative (L/l = {worst[1]:g}, n = "
        f"{worst[2]}), so no sign is in doubt and no length is excluded for it"
    )
    return out


def q5_cap_binds(parts):
    """Ruling 2: the Q5 modes whose 3 / |Re lambda| record the 600 s cap shortens, each with the
    record it would have (the driver's record_time without the cap, at d = 8)."""
    K, D = mg.schnakenberg_rates(mg.SUBCRITICAL)
    out = {}
    for L in (6, 8, 11, 16):
        for n in range(1, 7):
            if abs(parts["q5"][mg.key("L", L)][f"n{n}"]["record_s"] - 600.0) < 1e-9:
                uncapped = mg.record_time(K, D, mg.DOMAINS[L], n, cap=float("inf"))
                out[f"L{L}_n{n}"] = dict(record_s=600.0, uncapped_record_s=round(uncapped, 1))
    return out


def basis_record(paths, criteria, deltas, controls):
    """The development runs the thresholds and registered deltas were first derived from, named
    beside the runs drafted from: refused unless drafting from them gives the same criteria (ids,
    metric paths, comparisons, thresholds and bases), registered deltas and controls."""
    results, runs, origin = merged(paths)
    parts = results["parts"]
    own_controls, own_deltas, own = controls_by_parameter(parts)
    if (criteria_for(parts) + own_controls, own_deltas, own) != (criteria, deltas, controls):
        raise SystemExit("Refused: the basis runs give other criteria, deltas or controls")
    return dict(
        runs=runs,
        part_sources=origin,
        same_criteria_deltas_and_controls=True,
        note=(
            "the thresholds and the registered deltas were first derived from these development "
            "runs, from snapshots before FR-9 (D165); drafting from them gives the same criteria, "
            "thresholds, registered deltas and controls as drafting from the runs above (checked "
            "at drafting), whose values they reproduce at every non-timing leaf (disclosures)"
        ),
    )


def draft(output, paths, guards=None, basis=None):
    results, runs, origin = merged(paths)
    parts = results["parts"]
    criteria = criteria_for(parts)
    control_criteria, deltas, controls = controls_by_parameter(parts)
    criteria += control_criteria
    theory = parts["theory"]
    timing = unit_timing(results, runs, origin, guards)
    rehearsal = _rehearsal(runs)
    q4 = parts["q4"]
    q1 = parts["q1"]
    maps = linearised_map_summary(parts)
    judged_map, others = maps[LINEARISED_MAP_DT], [maps[mg.dt_key(dt)] for dt in mg.DTS[1:]]
    protocol = dict(
        schema="cells.morphogenesis_protocol@1",
        id="mg0c-turing-v1",
        title=(
            "MG0c: Turing patterning at the predicted wavelength, "
            "cells.operator.local_species_reactions@1's "
            "first acceptance on cells.model.resolved_pump_tissue@3's species transport"
        ),
        status=STATUS.format(
            source="the rehearsal's runs on main" if rehearsal else "the development runs"
        ),
        rung="MG0c",
        question=(
            "Does cells.operator.local_species_reactions@1, composed with @3's species transport "
            "on a closed "
            "chain, run the declared discrete system: the engine order's own map for linear "
            "networks and for Schnakenberg linearised, exact mode propagation and the nonlinear "
            "pattern to the scheme's step terms, only admissible modes growing, the predicted "
            "dominant mode and growth rate, the staircase of fastest modes against the domain's "
            "length, decay below the critical ratio, and closed accounting?"
        ),
        # Recorded text: the registered MG0c protocol (protocols/mg0c_turing_v1.json) holds these
        # lines word for word, so no move changes them (D188 move 2). Their paths and module names
        # are never resolved.
        engine_models=[
            "cells.model.resolved_pump_composite@1 (src/cells/models/pump_composite.py)",
            "cells.model.resolved_pump_tissue@3 (src/cells/core/surface_pump_v3_spec.py, "  # noqa: E501  source-moves: keep
            "src/cells/models/surface_pump_v3.py), IMEX ARS(2,2,2), CPU, float64",
            "cells.operator.local_species_reactions@1 (src/cells/models/operators/species_reactions.py): driven "  # noqa: E501  source-moves: keep
            "mass action; cells.species_reaction.ideal_detailed_balance_mass_action@1 in guard 2's "
            "passive world",
            "cells.core.inventory_species (D150) declares the network's species",  # noqa: E501  source-moves: keep
        ],
        scope=SCOPE,
        driver="validation/morphogenesis/mg0c_turing.py",
        judged_parts=list(JUDGED_PARTS),
        theory_sources=dict(
            turing="Turing 1952, Phil Trans R Soc B 237:37, doi:10.1098/rstb.1952.0012",
            schnakenberg="Schnakenberg 1979, J Theor Biol 81:389, doi:10.1016/0022-5193(79)90042-0",
            murray="Murray 2003, Mathematical Biology II, ch. 2 (the conditions, the band, d_c)",
            crank="Crank 1975, The Mathematics of Diffusion, ch. 14 (linear reaction-diffusion)",
        ),
        references=dict(
            independence=(
                "validation/reactions (network_reference, chain_reference, turing_reference), "
                "written from the design's Appendix A and textbooks by an agent that never read "
                "the operator's code; the driver uses them only through "
                "validation/reactions/REFERENCES_USAGE.md and feeds them the raw declaration"
            ),
            predictions=(
                "computed at run time, never typed: tu.turing_analysis, tu.domain_modes, "
                "tu.admissible_unstable_modes, tu.fastest_admissible_mode, tu.staircase (discrete "
                "at h); cr.chain_eigenvalues, cr.mode_coefficients, cr.mode_propagator, "
                "cr.propagate_modes, cr.strang_mode_map, cr.linear_rates, cr.integrate_chain"
            ),
            self_tests="tests/unit/test_reaction_references.py (tier 1)",
        ),
        world=dict(
            builder="validation/morphogenesis/mg0c_turing.py chain_world",
            chain=(
                "N finite outside nodes of 0.5 pL at h = l/2 = 5 um, faces of area V/h = 1e-10 m^2 "
                "and length h; zero-flux ends (no face to the bath); quiescent ions; one quiescent "
                "cell with a capacitive patch on every node and one on the held bath"
            ),
            parameters=dict(
                a=mg.A,
                b=mg.B,
                d=mg.D_RATIO,
                k_per_s=mg.RATE_K,
                c_star_mM=mg.C_STAR_MM,
                D_U_m2_per_s=mg.D_U,
                l_m=theory["length_scale_m"],
                labelled="synthetic and compressed (a textbook regime), not a biological claim",
            ),
            domains={f"L{L}": n for L, n in mg.DOMAINS.items()},
            dts_s=list(mg.DTS),
            explicit_rate_bound_per_s=theory["explicit_rate_bound_per_s"],
            trace_mM=mg.TRACE_MM,
            material_floor_fmol=mg.FLOOR_FMOL,
            single_mode_amplitude_of_c_star=mg.AMPLITUDE,
            noise_amplitude_of_c_star=mg.NOISE,
            seeds=mg.SEEDS,
            records=(
                "3 / |Re lambda| of each mode's slowest eigenvalue (the usage note's record), "
                "capped at 600 s (ruling 2), rounded to 50 ms, with records at 1/3 and 2/3 of it "
                "(Q5: at 0.4 to 0.9 of it)"
            ),
            cap_binds_in_q5=q5_cap_binds(parts),
            cap_binds_in_q1=[
                f"L{L}_n{n}"
                for L in (6, 11, 16)
                for n in range(1, 7)
                if abs(q1[mg.key("L", L)][f"n{n}"]["record_s"] - 600.0) < 1e-9
            ],
        ),
        predictions_at_drafting=dict(
            analysis=theory["analysis"],
            wavelength_m=theory["wavelength_m"],
            e_fold_s=theory["e_fold_s"],
            domains={
                k: dict(unstable=v["unstable"], fastest=v["fastest"])
                for k, v in theory["domains"].items()
            },
            staircase=theory["staircase"],
            subcritical_max_sigma=theory["subcritical"],
            note="for orientation only: the judged run recomputes every prediction",
        ),
        rules=dict(
            dt_study=(
                "S5's form, per element and record (D150's protocol): the step term |q(dt) - "
                "q(dt/2)| at the same records, the tolerance 3 x (the step term + the reference "
                "term), the reference term 64 eps x the scale for an exact reference (the scale "
                "the largest |reference| over the item's records), plus the reference's own "
                "difference |rtol 1e-12 - rtol 1e-13| for DOP853; judged at 50 and 25 ms"
            ),
            what_the_rule_shows=(
                "as D150's review found, the dt-study rule detects bias, not order: for a "
                "second-order error the ratio sits at 4/9 by structure, so the rule's power is its "
                "judged controls'; the orders are reported, and only their stop rules are judged"
            ),
            orders=(
                "per record, log2 of successive max-norm differences |q(dt) - q(dt/2)| / "
                "|q(dt/2) - q(dt/4)|, where both lie above 64 eps x the scale; the stop rule: "
                "every measurable difference decreases"
            ),
            linearised_map=(
                "ruling 3: Q1's engine against the linearised engine-order map within 1e-6 at 50 "
                f"ms (the development's worst {judged_map['worst_floor']:.2g}); its control, the "
                "exact propagator, must fail it there (the development's smallest "
                f"{judged_map['smallest_against_exact']:.2g}). At 25 and 12.5 ms the agreement is "
                "reported (linearised_map_by_dt), since the smallest discretisation error there ("
                + " and ".join(f"{m['smallest_against_exact']:.2g}" for m in others)
                + ") lies below 1e-6"
            ),
            controls=(
                "ruling (c), by parameter: each of k, a, b, D_U and D_V perturbed in the "
                "reference by (1 + delta) on Q1's items (the exact propagator with K = k J(a, b) "
                "and D, the whole 1-2-5 grid from 1e-14 to 0.5) and on Q6's (the reference "
                "re-integrated, bisected on the 1-2-5 grid from 1e-9 to 1e-1). A control is kept "
                "when 10 x its smallest caught delta is at most 1e-2 and is registered there; the "
                "others are removed with their reasons (controls.removed); every parameter keeps "
                "at least one, so each is caught by a judged criterion at a small delta with 10 x "
                "margin (Control_k to Control_D_V). Each criterion requires every kept control "
                "of its parameter to catch at its registered delta, stricter than the ruling's "
                "'at least one'"
            ),
            controls_evaluable=(
                "why the control criteria fail outside a judged run: they read "
                "caught_at_registered, which the driver writes only when the registered deltas "
                "are loaded, that is under --protocol (a judged run, or a registered dry-run "
                "copy). A development run has no registered deltas, so the metric is missing and "
                "evaluate fails a missing metric (development_values names them not evaluable). "
                "Their passing path had never run for these five criteria (milestone 3's dry run "
                "loaded the old k and D_V deltas on Q1's quick part alone), so the rehearsal on "
                "main ran them on a registered dry-run copy before registration"
                + (
                    ": every one passed there (development_values)"
                    if rehearsal
                    and all(
                        protocol_values.get("passed") is True
                        for protocol_values in development_values(
                            dict(criteria=control_criteria), results
                        ).values()
                    )
                    else ""
                )
            ),
            near_ties=(
                "ruling 5: Q4's fit tolerance is Q3's 1e-2, relative; the fastest two candidates "
                "at a length are a near tie when their gap is below 2 x 1e-2 x the larger |rate|, "
                "from the references alone before any run, and such a length is excluded; the "
                "sign margin (the smallest |rate| over 1e-2 x the largest) is reported beside it"
            ),
            judged_run=(
                "once, after registration, from a fresh clean execution snapshot of main "
                "(validation/source_snapshot.py, no dirty patch), through scripts/run_detached.sh. "
                "A failure is recorded and diagnosed, never retuned"
            ),
            attempts=(
                "an attempt that ends by infrastructure before its verdict is written is not a "
                "verdict: an out-of-memory kill, a unit stopped by the slice, a host crash, a "
                "harness timeout, a unit killed by its runtime limit (--runtime-max), a part run "
                "that ends incomplete (the judge refuses it: results.json's requested parts and "
                "complete), or a guard file whose process ends by a signal (judge-guards then "
                "writes infrastructure.json, not verdict.json). It is recorded with its logs and "
                "partial outputs and rerun once from the same snapshot; each attempt writes its "
                "own output directory, since every judged entry refuses an existing one. A second "
                "infrastructure ending goes to the lead, as does any other ending without a "
                "verdict. A run that has written its verdict is final (S5's rule). A part the "
                "engine refuses is a verdict: its criteria fail; a test failure or error inside a "
                "completed guards run is a verdict too"
            ),
            timing=(
                "each judged unit runs through scripts/run_detached.sh with --oom-first in its own "
                "unit, its --runtime-max about 3 x its seconds plus 10 min "
                + (
                    "(development_runs.timing: the rehearsal's on main; "
                    if rehearsal
                    else "(development_runs.timing: development's figures until the rehearsal "
                    "measures them; "
                )
                + "judge-guards from the guard files' seconds, uncapped per file; judge and "
                "combine, which run nothing, 600 s), q7 with a cap of at least 5 GiB (ruling 9) "
                f"and unit b likewise (resources); the lanes: {LANES}. "
                "The judged units run without "
                "--wait-headroom: the lead launches each only after checking that the slice has "
                "room for the unit's development peak plus a margin, so each runtime limit "
                "measures the entry alone and no wait can spend the single rerun"
            ),
            resolved_start=(
                "every run starts resolved: the uniform state with a mode of 1e-7 c* or seeded "
                "noise of 1e-3 c*, never a switch-on from the trace"
            ),
            judge_entries=dict(
                environment=(
                    "every entry from the snapshot's root with PYTHONPATH=src:. JAX_ENABLE_X64=1 "
                    "JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= and "
                    "/mnt/workspaces/Cells/venv-cpu/bin/python (CPU backend only, float64)"
                ),
                guard=(
                    "mg0c_turing.registered, every judged entry's first call: it refuses an "
                    "unregistered protocol (its status and a registration record matching it), "
                    "a source that is not a clean execution snapshot and an existing output "
                    "directory before anything is computed or written; "
                    "tests/unit/test_mg0c_judged_refusal.py tests it with every entry"
                ),
                parts=(
                    "per unit (development_runs.units): python -m "
                    "validation.morphogenesis.mg0c_turing PARTS --output RUN_DIR --protocol "
                    "THIS_FILE, each into its own new RUN_DIR, logs beside it (mg0c/dev.sh, which "
                    "creates its output directory first, is the development launcher only)"
                ),
                judge=(
                    "python -m validation.morphogenesis.mg0c_turing judge --output OUT --protocol "
                    "THIS_FILE --results RUN_DIR/results.json ...: the parts' verdict, refusing "
                    "runs of another protocol, from another snapshot or incomplete"
                ),
                guards=(
                    "python -m validation.morphogenesis.mg0c_turing judge-guards --output OUT "
                    "--protocol THIS_FILE: pytest on guards_of_record.tests from the snapshot, one "
                    "file at a time with no per-file cap; OUT/verdict.json with each file's "
                    "counts, exit code and duration"
                ),
                combined=(
                    "python -m validation.morphogenesis.mg0c_turing combine --output OUT "
                    "--protocol THIS_FILE --results PARTS_OUT GUARDS_OUT: the one qualification "
                    "verdict (every criterion, the guards' files, the scope line, the snapshot's "
                    "revision), refusing verdicts of another protocol or from another snapshot"
                ),
                register=(
                    "python -m validation.morphogenesis.mg0c_protocol register THIS_FILE "
                    "RECORD_JSON: the lead's registration; the status and the lead's record alone"
                ),
                launcher=(
                    "each entry in its own unit: scripts/run_detached.sh NAME CAP --cpus CPU "
                    "--oom-first --runtime-max LIMIT --env UNIT=NAME -- rehearse_entry.sh SNAPSHOT "
                    "SNAPSHOT/validation/morphogenesis/protocols/mg0c_turing_v1.json OUT ENTRY "
                    "[ARGS], with rehearse_entry.sh the rehearsal's launcher "
                    "(/mnt/workspaces/Cells/shared-inventory-reactions-v1-20261114-01/mg0c/, "
                    "copied unchanged into the judged run's inputs): it runs the entry from the "
                    "snapshot's root with judge_entries.environment, never creates OUT (the "
                    "entry does), and writes OUT.log, OUT.run.txt and the unit's memory record "
                    "beside OUT. The caps, lanes and runtime limits (development_runs.units and "
                    "timing) are enforced by the launcher alone (run_detached.sh's MemoryMax, "
                    "CPUAffinity and RuntimeMaxSec): no code reads them"
                ),
            ),
        ),
        criteria=criteria,
        registered_control_deltas=deltas,
        controls=controls,
        q4_near_ties=q4_near_ties(q4),
        guards_of_record=dict(
            tests=list(GUARD_TESTS),
            covers=[
                "the energy guards of record (§3.4): the face-free world at rounding on every "
                "booking path, and the per-law dG test against network_reference",
                "the independent kinetic and dissipation comparisons as implementation checks "
                "(test_species_reactions_reference_runs: whole runs against nr.run_half_steps at "
                "rounding), kept with their documented trace-scale limits (the reversal onset, "
                "§3.3; the stiff front's stall at about eps x its anchor, §4.4), because W = dG + "
                "H: a closed ledger cannot show heat and work separately",
                "the composed world (test_species_reactions_composition): supply counted once "
                "across writers, the rejected step restoring every field bitwise, restart and a "
                "vector batch; guard 2's linear chain; idle claim 3 (reported, as D150's ion "
                "test); the development composition with D150's writers and replacement@1",
                "reactions at several sites with their own multipliers against nr.run_half_steps",
                "the definition-time refusals, the batch signature, restart and vmap (§6.5)",
                "the judged entries' refusals and verdicts (test_mg0c_judged_refusal)",
            ],
            verdict_rule="pass when every file exits 0, from the judged snapshot (judge-guards)",
        ),
        regression_guards=REGRESSION_GUARDS,
        reported_not_judged=[
            "Q1's linearised-map agreement at 25 and 12.5 ms (ruling 3)",
            "the discrete sigma_n and k_n against the continuum (theory.domains; second order "
            "in h)",
            "the floor part: the linearised map's agreement against the start's amplitude",
            "every item's observed orders, and the rule's within fractions",
            "the timing part: cost per step and compile per chain size",
            "Q3's sigma_n beside the discrete-time rate, the saturated amplitude, the dominant "
            "mode at every record",
            "Q5's fitted rates beside the predicted ones (ruling 4)",
            "Q4's top-two gap and sign margin against the fit tolerance (ruling 5)",
            "the modes' structure (q1 mode_structure) and the removed controls' reasons",
        ],
        what_mg0c_does_not_show=[
            "any biological claim (the parameters are synthetic)",
            "the mixed-node heat and work split, Michaelis-Menten, Hill factors and cell routes, "
            "which only test files exercise (scope)",
            "local accuracy at a consumer's concentrations (concentration over time, integrated "
            "exposure, effective control and threshold time): the coupling milestone's protocol, "
            "not MG0c's (the coordinator, milestone 3)",
            "the selection between several unstable modes on wide domains (nonlinear)",
            "two-dimensional patterns (they need sparse field IDs, D150 §3)",
            "recovery after damage (E15's question)",
        ],
        review=REVIEW,
        findings=findings(parts),
        linearised_map_by_dt=maps,
        disclosures=DISCLOSURES,
        questions_for_the_lead=QUESTIONS,
        questions_answered=ASKED,
        pre_registration_amendments=[],
        outcome_rules=(
            "pass when the combined verdict passes: every judged criterion and every guard of "
            "record. A failure is recorded and kept; a revised protocol gets a new id and is "
            "reported as weaker evidence"
        ),
        resources=(
            "CPUs 5 and 7 (CPU backend only), each unit detached through scripts/run_detached.sh "
            "with --oom-first; memory caps 4 GiB for units a and c, at least 5 GiB for q7 (ruling "
            "9: a cap kill would spend the single rerun) and, by the same reasoning, for unit b "
            f"({unit_b_memory(runs, origin)}); judge-guards uncapped per file in time, its memory "
            f"cap proposed at 5 GiB ({GUARDS_MEMORY}); judge and combine 2 and 1 GiB; the units' "
            "peaks and seconds in development_runs.timing"
        ),
        development_runs=dict(
            runs=runs,
            part_sources=origin,
            basis=basis_record(basis, criteria, deltas, controls) if basis else None,
            units=UNITS,
            timing=timing,
            drafted_by=mg.source_identity(),
        ),
    )
    if not basis:
        del protocol["development_runs"]["basis"]
    protocol["development_values"] = development_values(protocol, results)
    Path(output).write_text(json.dumps(mg.plain(protocol), indent=1) + "\n")
    failed = [k for k, v in protocol["development_values"].items() if v.get("passed") is False]
    print(
        f"{len(criteria)} criteria, {len(deltas)} registered deltas, "
        f"{len(controls['removed'])} controls removed; failing in development: {failed}"
    )
    return protocol


def register(protocol_path, record_path):
    """The lead's registration through the generator's path: the PROPOSED protocol takes the
    record's status and, after it, the record itself (the lead's, never pre-filled here); every
    other leaf stays as drafted. Refused for a protocol already registered or recorded, or a record
    whose status does not begin 'registered'."""
    path = Path(protocol_path)
    protocol = json.loads(path.read_text())
    record = json.loads(Path(record_path).read_text())
    if not str(protocol.get("status")).startswith("PROPOSED") or "registration" in protocol:
        raise SystemExit("Refused: only a PROPOSED protocol without a registration record")
    if not (isinstance(record, dict) and str(record.get("status", "")).startswith("registered")):
        raise SystemExit("Refused: the registration record's status must begin 'registered'")
    out = {}
    for key, value in protocol.items():
        out[key] = record["status"] if key == "status" else value
        if key == "status":
            out["registration"] = dict(record)
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(path)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="action", required=True)
    drafting = commands.add_parser("draft")
    drafting.add_argument("output")
    drafting.add_argument("results", nargs="+")
    drafting.add_argument("--guards")
    drafting.add_argument("--basis", nargs="+")
    registering = commands.add_parser("register")
    registering.add_argument("protocol")
    registering.add_argument("record")
    args = parser.parse_args(argv)
    if args.action == "draft":
        draft(args.output, args.results, args.guards, args.basis)
    else:
        register(args.protocol, args.record)


if __name__ == "__main__":
    main(sys.argv[1:])
