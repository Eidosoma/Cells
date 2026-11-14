"""MG0c's qualification protocol (D152 version 1, milestone 3): its draft from disclosed runs.

docs/SHARED_INVENTORY_REACTIONS_DESIGN.md §6.4, with §11 and §11.2. The protocol
(validation/morphogenesis/protocols/mg0c_turing_v1.json) is PROPOSED: drafted here from the
development runs named in it, for the lead's review with the advisor. Only the lead registers it,
and registration changes its status alone. The rules follow D150's reviewed protocol
(validation/tissue/secreted_species_protocol.json): S5's dt-study rule per element and record, the
observed orders with their stop rules, judged controls at registered deltas, the attempt rule.

The judged runs are the driver's --protocol runs (validation/morphogenesis/mg0c_turing.py:
registered, their first call, refuses an unregistered protocol, a source that is not a clean
execution snapshot and an existing output directory), one per part group; the verdict is the
driver's judge entry over their merged results.json (one snapshot, every part once), each
criterion evaluated by validation/morphogenesis/mg0a_gradient.evaluate (metric paths, comparisons,
thresholds; a missing metric fails its criterion).

Usage: python -m validation.morphogenesis.mg0c_protocol OUTPUT_JSON RESULTS_JSON [RESULTS_JSON ...]
  (each RESULTS_JSON a development run of the driver; together they hold every judged part once)
"""

import json
import sys
from pathlib import Path

from validation.morphogenesis import mg0c_turing as mg
from validation.morphogenesis.mg0a_gradient import _lookup, evaluate

STATUS = (
    "PROPOSED (drafted 14 November 2026 by the D152 engine agent from the development runs named "
    "in development_runs, for the lead's review with the advisor; not registered, and no judged "
    "run is made before the lead registers it)"
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
LINEARISED_MAP_TOLERANCE = 1e-6  # Proposed a priori (question 3 for the lead).
RATE_TOLERANCE = dict(q2=1e-3, q3=1e-2, q5=1e-2)  # Fit-limited, proposed a priori (question 4).
DOMINANT_FROM_S = 500.0  # Q3: the predicted mode dominates from this record to the end.
CONTROL_FACTOR = 10.0  # D150's: 10 x the larger of the smallest deltas caught in development.


def merged(paths):
    """Every part from exactly one development run, with the runs named."""
    parts, runs = {}, []
    for path in paths:
        data = json.loads(Path(path).read_text())
        if data.get("quick"):
            raise SystemExit(f"Refused: {path} is a quick run")
        for name, value in data["parts"].items():
            if name in parts:
                raise SystemExit(f"Refused: part {name} is in more than one run")
            if not value.get("ok"):
                raise SystemExit(f"Refused: part {name} failed in {path}")
            parts[name] = value
        runs.append(dict(path=str(path), source=data["source"], parts=sorted(data["parts"])))
    missing = sorted(set(JUDGED_PARTS) - set(parts))
    if missing:
        raise SystemExit(f"Refused: the development runs lack parts {missing}")
    results = dict(parts=parts)
    results["accounting_summary"] = mg.accounting_summary(results)
    return results, runs


def snap_up(value):
    """The smallest point of the driver's 1-2-5 grid at or above value (the value past the grid)."""
    return next((d for d in mg.DELTAS if d >= value * (1 - 1e-12)), value)


def criterion(id_, metrics, comparison, threshold, basis):
    return dict(id=id_, metrics=metrics, comparison=comparison, threshold=threshold, basis=basis)


def criteria_and_controls(results):
    """The judged criteria (metric paths into the judged run's results.json) and the registered
    control deltas, from the development results' structure and controls."""
    p = results["parts"]
    out, deltas = [], {}
    if p["d147"]["max_free_field_offsets"] > 0:
        raise SystemExit(
            "Refused: an MG0c world has free field offsets (D147): tell the lead first"
        )
    out.append(
        criterion(
            "D147_no_free_field_offsets",
            ["parts.d147.max_free_field_offsets"],
            "le",
            0,
            "D147: a definition with free field offsets declares field solver @3; every MG0c world "
            "has none (each chain node shares the cell's capacitor component with the held bath), "
            "so the declared @2 stands. Composite IDs skip D147's automatic choice, so the count "
            "is checked here",
        )
    )
    for world in ("passive", "open"):
        base = f"parts.linear.{world}"
        out += [
            criterion(
                f"G2_{world}_engine_order_map",
                [f"{base}.{mg.dt_key(dt)}.map_over_usage_note_rule" for dt in mg.DTS],
                "le",
                1.0,
                "|engine - strang_mode_map iterated| <= 1e-14 x steps x the scale at every "
                "record (REFERENCES_USAGE.md's accumulation, a priori; D150's steps x eps x the "
                "scale reported, question 8): the composite's order P(dt/2) I(dt) P(dt/2) with "
                "@3's species transport, mode by mode",
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
    for L in (6, 11, 16):
        base = f"parts.q1.{mg.key('L', L)}"
        modes = [f"n{n}" for n in range(1, 7)]
        out += [
            criterion(
                f"Q1_L{L}_linearised_map",
                [
                    f"{base}.{n}.{mg.dt_key(dt)}.against_linearised_map"
                    for n in modes
                    for dt in mg.DTS
                ],
                "le",
                LINEARISED_MAP_TOLERANCE,
                "the engine against the linearised engine-order map (strang_mode_map with "
                "K = k J), relative to each record's largest coefficient: the implementation at "
                "the floor of the 1e-7 start (floor part)",
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
        paths = []
        for n in modes:
            for dt in DT_JUDGED:
                rule = p["q1"][mg.key("L", L)][n]["dt_rule"][dt]["controls"]
                deltas[f"q1.{mg.key('L', L)}.{n}.{dt}"] = rule
                paths += [
                    f"{base}.{n}.dt_rule.{dt}.controls.{k}.caught_at_registered" for k in rule
                ]
        out.append(
            criterion(
                f"Q1_L{L}_controls",
                paths,
                "ge",
                1,
                "the exact propagator with k, and separately D_V, times (1 + delta) at the "
                "registered delta fails the dt-study rule somewhere (the rule can fail)",
            )
        )
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
    out.append(
        criterion(
            "Q4_staircase",
            ["parts.q4.all_agree"],
            "ge",
            1,
            "at every L/l from 4 to 30 (step 0.5), the fastest-growing single-mode start on the "
            "engine is the discrete argmax of sigma_n (none at 4 and 7.5 to 8.5), and the growing "
            "set is the admissible unstable set",
        )
    )
    for L in (6, 8, 11, 16):
        base = f"parts.q5.{mg.key('L', L)}"
        modes = [f"n{n}" for n in range(1, 7)]
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
    base = "parts.q6"
    paths = []
    for dt in DT_JUDGED:
        rule = p["q6"]["dt_rule"][dt]["controls"]
        deltas[f"q6.{dt}"] = rule
        paths += [f"{base}.dt_rule.{dt}.controls.{k}.caught_at_registered" for k in rule]
    out += [
        criterion(
            "Q6_dt_rule",
            [f"{base}.dt_rule.{dt}.max_ratio" for dt in DT_JUDGED],
            "le",
            1.0,
            "S5's dt-study rule against cr.integrate_chain (DOP853 at rtol 1e-13, its own term "
            "|rtol 1e-12 - rtol 1e-13|), per node, species and record, to saturation",
        ),
        criterion(
            "Q6_orders",
            [f"{base}.dt_rule.stop_rule_differences_decrease"],
            "ge",
            1,
            "every measurable step-term difference decreases (the orders are reported)",
        ),
        criterion(
            "Q6_controls",
            paths,
            "ge",
            1,
            "the reference re-integrated with k, and separately D_V, times (1 + delta) at the "
            "registered delta fails the rule somewhere",
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
            "a vector batch over seeds on one domain: bitwise against the reversed batch",
        ),
        criterion(
            "Q7_batch_scalar",
            ["parts.q7.batch_against_scalar_relative"],
            "le",
            1e-12,
            "each world within 1e-12 of its scalar run (§6.5)",
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
    registered = {}
    for item, rule in deltas.items():
        if not all(v["rule_passes_unperturbed"] for v in rule.values()):
            raise SystemExit(
                f"Refused: {item}'s rule fails unperturbed, so its controls mean nothing"
            )
        caught = [v["smallest_caught"] for v in rule.values()]
        if None in caught:
            raise SystemExit(f"Refused: a control of {item} is not caught in development")
        delta = snap_up(CONTROL_FACTOR * max(caught))
        registered.update({f"{item}.{kind}": delta for kind in rule})
    return out, registered


BOUNDS = ("energy_over_bound", "material_over_bound")


def development_values(protocol, results):
    """Each criterion's development values and its development verdict (not judged). A control's
    caught_at_registered exists only in a judged run: there the development's smallest caught
    deltas stand beside the registered ones instead."""
    verdict = evaluate(dict(criteria=protocol["criteria"]), results)
    out = {}
    for v, c in zip(verdict["criteria"], protocol["criteria"], strict=True):
        if c["id"].endswith("_controls"):
            out[v["id"]] = dict(
                evaluable="in the judged run only (caught_at_registered)",
                smallest_caught_in_development=[
                    _lookup(results, m.replace("caught_at_registered", "smallest_caught"))
                    for m in c["metrics"]
                ],
            )
        else:
            out[v["id"]] = dict(passed=v["passed"], values=v["values"])
    return out


def draft(output, paths):
    results, runs = merged(paths)
    criteria, deltas = criteria_and_controls(results)
    theory = results["parts"]["theory"]
    protocol = dict(
        schema="cells.morphogenesis_protocol@1",
        id="mg0c-turing-v1",
        title=(
            "MG0c: Turing patterning at the predicted wavelength, local_species_reactions@1's "
            "first acceptance on resolved_pump_tissue@3's species transport"
        ),
        status=STATUS,
        rung="MG0c",
        question=(
            "Does local_species_reactions@1, composed with @3's species transport on a closed "
            "chain, run the declared discrete system: the engine order's own map for linear "
            "networks and for Schnakenberg linearised, exact mode propagation and the nonlinear "
            "pattern to the scheme's step terms, only admissible modes growing, the predicted "
            "dominant mode and growth rate, the staircase of fastest modes against the domain's "
            "length, decay below the critical ratio, and closed accounting?"
        ),
        engine_models=[
            "resolved_pump_composite@1 (src/cells/models/pump_composite.py)",
            "resolved_pump_tissue@3 (src/cells/core/surface_pump_v3_spec.py, "
            "src/cells/models/surface_pump_v3.py), IMEX ARS(2,2,2), CPU, float64",
            "local_species_reactions@1 (src/cells/models/operators/species_reactions.py): driven "
            "mass action; ideal_detailed_balance_mass_action@1 in guard 2's passive world",
            "cells.core.inventory_species (D150) declares the network's species",
        ],
        driver="validation/morphogenesis/mg0c_turing.py",
        command=(
            "From a fresh clean execution snapshot of main, through scripts/run_detached.sh: "
            "PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= python -m "
            "validation.morphogenesis.mg0c_turing PARTS --output RUN_DIR --protocol THIS_FILE, "
            "one unit per part group (development_runs.units), each into its own new RUN_DIR; then "
            "python -m validation.morphogenesis.mg0c_turing judge --output JUDGE_DIR --protocol "
            "THIS_FILE --results RUN_DIR/results.json ..., the verdict over the merged runs (one "
            "snapshot, every part once); then the guards of record (guards_of_record.tests) with "
            "pytest from the same snapshot"
        ),
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
            q1_records=(
                "3 / |Re lambda| of each mode's slowest eigenvalue (the usage note's record), "
                "capped at 600 s, rounded to 50 ms, with records at 1/3 and 2/3 of it"
            ),
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
                "second-order error the pass fraction is structural, so the rule's power is its "
                "judged controls'; the orders are reported, and only their stop rules are judged"
            ),
            orders=(
                "per record, log2 of successive max-norm differences |q(dt) - q(dt/2)| / "
                "|q(dt/2) - q(dt/4)|, where both lie above 64 eps x the scale; the stop rule: "
                "every measurable difference decreases"
            ),
            controls=(
                "judged (D150's form): the judged run's output against the reference with k, and "
                "separately D_V, times (1 + delta) at the registered delta, 10 x the larger of the "
                "smallest deltas that caught k and D_V in development on a 1-2-5 grid from 1e-14 "
                "to 0.5 (Q6: 1e-9 to 1e-2 by decades), snapped up to the grid; each must fail the "
                "rule somewhere"
            ),
            judged_run=(
                "once, after registration, from a fresh clean execution snapshot of main "
                "(validation/source_snapshot.py, no dirty patch), through scripts/run_detached.sh. "
                "A failure is recorded and diagnosed, never retuned"
            ),
            attempts=(
                "an attempt killed by infrastructure before its verdict is written is not a "
                "verdict: it is recorded with its logs and rerun once from the same snapshot into "
                "a new directory (the driver refuses an existing one); a second goes to the lead. "
                "A part the engine refuses is a verdict: its criteria fail"
            ),
            resolved_start=(
                "every run starts resolved: the uniform state with a mode of 1e-7 c* or seeded "
                "noise of 1e-3 c*, never a switch-on from the trace"
            ),
        ),
        criteria=criteria,
        registered_control_deltas=deltas,
        guards_of_record=dict(
            tests=[
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
            ],
            covers=[
                "the energy guards of record (§3.4): the face-free world at rounding on every "
                "booking path, and the per-law dG test against network_reference",
                "the independent kinetic and dissipation comparisons (test_species_reactions_"
                "reference_runs: whole runs against nr.run_half_steps, H and W against "
                "dr.integrate_node), kept with their documented trace-scale limits (the reversal "
                "onset, §3.3; the background guard; the stiff front's stall at about eps x its "
                "anchor, §4.4), because W = dG + H: a closed ledger cannot show heat and work "
                "separately (the coordinator's milestone-3 addition)",
                "the composed world (test_species_reactions_composition): transport and reactions "
                "see the same material under the declared splitting (the face-free export and "
                "reactions against E R I R E at rounding, second order to the coupled solution); "
                "supply counted once across writers (each species' inventory against its writers' "
                "sources at every row); restart and a vector batch preserve its results; a "
                "rejected step restores every field bitwise, the other writers' accumulators "
                "included",
                "the definition-time refusals, the batch signature, restart and vmap (§6.5)",
                "guard 2's linear chain against the engine order's map, idle claim 3 (reported), "
                "the development composition with D150's writers and replacement@1",
                "reactions at several sites with their own multipliers against nr.run_half_steps",
                "the judged-run refusal",
            ],
            verdict_rule="pass when every test in these files passes, from the judged snapshot",
        ),
        reported_not_judged=[
            "the discrete sigma_n and k_n against the continuum (theory.domains; second order "
            "in h)",
            "the floor part: the linearised map's agreement against the start's amplitude",
            "every item's observed orders, and the rule's within fractions",
            "the timing part: cost per step and compile per chain size",
            "Q3's sigma_n beside the discrete-time rate, the saturated amplitude, the dominant "
            "mode at every record",
            "Q5's fitted rates beside the predicted ones",
            "§11.1's accuracy pins (proposals for the lead; the face-free guards' accuracy)",
        ],
        what_mg0c_does_not_show=[
            "any biological claim (the parameters are synthetic)",
            "local accuracy at a consumer's concentrations (concentration over time, integrated "
            "exposure, effective control and threshold time): the coupling milestone's protocol, "
            "not MG0c's (the coordinator, milestone 3)",
            "the selection between several unstable modes on wide domains (nonlinear)",
            "two-dimensional patterns (they need sparse field IDs, D150 §3)",
            "recovery after damage (E15's question)",
        ],
        questions_for_the_lead=QUESTIONS,
        outcome_rules=(
            "pass when every judged criterion passes and the guards of record pass. A failure is "
            "recorded and kept; a revised protocol gets a new id and is reported as weaker evidence"
        ),
        resources=RESOURCES,
        development_runs=dict(runs=runs, units=UNITS, drafted_by=mg.source_identity()),
    )
    protocol["development_values"] = development_values(protocol, results)
    Path(output).write_text(json.dumps(protocol, indent=1) + "\n")
    failed = [k for k, v in protocol["development_values"].items() if v.get("passed") is False]
    print(
        f"{len(criteria)} criteria, {len(deltas)} registered deltas; "
        f"failing in development: {failed}"
    )
    return protocol


QUESTIONS = [
    "1. Q7's 'a vmap batch of the domains' cannot run: a route's node is part of the operator's "
    "batch signature (ruling Q11 (c)), so domains of different N are refused in one batch. "
    "Proposed: a vector batch over seeds on one domain (L/l = 6), bitwise against its reverse and "
    "within 1e-12 of each scalar run",
    "2. Q1's records: 3 / |Re lambda| of each mode's slowest eigenvalue, capped at 600 s (the "
    "near-marginal modes' 3 / |Re lambda| would run to 590 s and beyond)",
    "3. Q1's linearised-map tolerance, 1e-6 relative a priori: above the floor measured at the "
    "1e-7 start (the floor part) and below the smallest discretisation error at 12.5 ms",
    "4. The fit-limited rate tolerances (Q2 1e-3, Q3 1e-2, relative to the engine order's "
    "discrete-time rate, not the continuous sigma_n, which differs by O(dt^2)); Q5's fitted "
    "rates reported only",
    "5. Q4's candidate modes: every mode whose discrete k^2 lies in [0.1, 0.7] l^-2 (real "
    "eigenvalues; the band is (0.2, 0.5)), at least two per domain, 100 s each, fitted from 50 s",
    "6. Q6's controls are integrated at rtol 1e-12 on a decade grid (each costs an integration)",
    "7. §11.1's accuracy pins: adopted as guards, or kept as proposals",
    "8. Guard 2's rounding rule: REFERENCES_USAGE.md's 1e-14 x steps x the scale, or D150's "
    "steps x eps x the scale (development: up to 0.92 of the latter at 800 steps, both sides' "
    "rounding counted; see development_values)",
]
RESOURCES = (
    "CPUs 5 and 7 (CPU backend only), each unit capped at 4 GiB, detached through "
    "scripts/run_detached.sh; development wall times in development_runs"
)
UNITS = dict(
    a="CPU 5: theory, timing, linear, floor, q1, q2, sites",
    b="CPU 7: q6, q3, q5, q7",
    c="CPU 5, after a: q4",
    note="development's split; the judged run keeps it, each unit into its own new directory",
)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    draft(sys.argv[1], sys.argv[2:])
