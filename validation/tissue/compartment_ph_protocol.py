"""FR-4's and FR-5's qualification protocols: their machine criteria, units and registration path.

The protocols (validation/compartment_ph/protocols/fr4_acidification_v1.json and
fr5_transfer_v1.json) are PROPOSED, hand-drafted by the FR-4/FR-5 physics owner with prose
criteria (J1-J7 and J1-J11). This module writes, a priori and before any run of either world, what
the judge needs beside the prose (`judge`):
* `derivation`: the parts each metric reads and the arithmetic's parameters (the judge's docstring
  fixes the arithmetic itself);
* `criteria`: the machine criteria, each a metric path, a comparison and a threshold taken from
  the prose (MG0c's evaluator form; `judged: false` marks a reported item);
* `units` and `resources`: one part per unit, its cost at the vector path's measured rate on
  FR-4's world (0.95 ms per step plus about 48 s of compile per unit; the execution path, a dated
  pre-run correction), and the launch command as a template until the rehearsal measures each
  unit (D150's rule: 3 x its wall time plus 10 minutes).
`draft` writes that section into a PROPOSED protocol in place, sets `judged_parts` to the
generator's parts, and moves the hand-drafted registration plan to `registration_plan`, so that
`register` can add the lead's record under `registration` (MG0c's form). Rerunning it changes
nothing. Only the lead registers.

Usage:
  python -m validation.tissue.compartment_ph_protocol draft fr4|fr5|all
  python -m validation.tissue.compartment_ph_protocol register PROTOCOL_JSON RECORD_JSON
"""

import json
import math
import sys
from pathlib import Path

from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import dt_study
from validation.tissue import compartment_ph_qualification as generator
from validation.tissue import compartment_ph_reference_stage as stage

BAND = [1.8, 2.2]  # J2: the observed orders
PH_BUDGET = 1e-3  # J3/J4: pH units
PH_NODES = ["pH_L", "pH_c"]  # J4's buffered nodes, the lumen and the cytosol (the lead's ruling)
J4_NODES = ("at every buffered node, the lumen and the cytosol: the maximum over both nodes and "
            "every record (pre-run correction, the lead, 15 November 2026)")
START_TOLERANCE = 1e-11  # row 0 against the reference: rounding (the reference stage's)
START_X_OVER_BUDGET = 1e-9  # X_L's row 0 in budgets: the same products, so rounding
# The units' sizing (the lead's ruling of 17 November 2026): 1.5 ms per step plus 90 s of compile
# per engine unit (the rehearsal's compile took 74-134 s), 300 s as the estimate of a part without
# steps; each runtime limit is D150's rule on the larger of that estimate and the rehearsal's wall.
# (The earlier basis, 0.95 ms per step plus 48 s, was FR-4's world on a quiet core: fr45-transporter
# 427e4a05, CPU 1.)
SIZING_S_PER_STEP = 1.5e-3
COMPILE_ALLOWANCE_S = 90.0
NO_STEPS_ESTIMATE_S = 300.0
UNIT_CAP = "2G"
# The rehearsal (17 November 2026: run-e79b4232 from snapshot e79b4232, on CPUs 6, 7, 22 and 23,
# two pairs of sibling hyperthreads, all four busy): each unit's wall time (s) and memory peak, from
# its results and its journal (/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/
# rehearsal-20261117/run-e79b4232/reading.json).
REHEARSAL = {
    "fr4": dict(rung_2ms=(880.7, "1.3G"), rung_1ms=(1675.3, "1.3G"), rung_0p5ms=(3468.1, "1.3G"),
                rung_0p25ms=(5480.0, "1.3G"), control_k1=(2101.1, "1.3G"),
                control_k2=(1719.4, "1.3G"), control_k3=(3.6, "108.6M"),
                reference=(87.4, "58.2M")),
    "fr5": dict(start=(2687.2, "1.3G"), T_rung_1ms=(687.7, "1.3G"), T_rung_0p5ms=(1716.6, "1.3G"),
                T_rung_0p25ms=(3089.7, "1.4G"), T_rung_0p125ms=(6507.0, "1.3G"),
                T_control=(1653.9, "1.3G"), R_rung_1ms=(825.5, "1.3G"),
                R_rung_0p5ms=(1580.9, "1.3G"), R_rung_0p25ms=(3342.3, "1.3G"),
                R_rung_0p125ms=(5230.5, "1.3G"), R_control=(1464.7, "1.3G"),
                reference=(39.1, "57.9M")),
}
LANE = "/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45"
REHEARSAL_RUN = f"{LANE}/rehearsal-20261117/run-e79b4232"
PIPELINE = f"{LANE}/pipeline"
PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"
FILES = {"fr4": "fr4_acidification_v1.json", "fr5": "fr5_transfer_v1.json"}
WRITTEN = ("15 November 2026, by the FR-4/FR-5 physics owner, before any run of this world (no "
           "engine run exists: the core's seams are not wired into this lane), from this "
           "protocol's prose criteria, rules and controls")
ARITHMETIC = ("validation/tissue/compartment_ph_judge.py's docstring: max-norm differences on "
              "shared integer-second records; a difference resolved at N eps max|q| (N the finer "
              "rung's steps); orders on the three finest rungs; the Richardson error (4/3) "
              "D(dt, dt/2) at the nominal p = 2; crossings and mean rates by linear interpolation "
              "between records; ledgers over the engine's own tolerances; undefined values None")


def criterion(id_, metrics, comparison, threshold, basis, judged=True):
    return dict(id=id_, metrics=list(metrics), comparison=comparison, threshold=threshold,
                basis=basis, judged=judged)


# ------------------------------------------------------------------------ FR-4


def derivation_fr4():
    return dict(
        ladder_parts=list(generator.FR4_RUNGS), declared_part="rung_1ms", half_part="rung_0p5ms",
        control_parts=list(generator.FR4_CONTROLS),
        order_observables=["pH_L", "V_b", "K_L", "cycles"],
        reference_observables=["pH_L", "pH_c", "V_b", "K_L", "cycles"], ph_nodes=PH_NODES,
        cytosol_pH=7.2, **_shared(include_cargo=False))


def _shared(*, include_cargo):
    """The classes' band and edge, and the material allowance's species, nodes and floors."""
    species = [s for s, _ in defs.SPECIES] + (["X"] if include_cargo else [])
    floors = dict(Na=1e-10, K=1e-10, Cl=1e-10, H=1e-16,
                  **dict.fromkeys(defs.BACKGROUND_ROWS, defs.World().trace_floor_fmol))
    if include_cargo:
        floors["X"] = 1e-12
    return dict(band=BAND, energy_order_low=BAND[0], species=species,
                conserved_nodes=[defs.CELL, defs.LUMEN, defs.BATH], material_floors_fmol=floors,
                arithmetic=ARITHMETIC)


def criteria_fr4():
    d = "derived"
    out = [criterion("J1_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                     "the four rungs, K1, K2 and the reference admitted and run to their end; K3 "
                     "is refused by design, its catch J7_K3 (pre-run correction, the lead, 15 "
                     "November 2026)")]
    out += [criterion(f"J2_order_{x}", [f"{d}.orders.{x}.passes"], "ge", 1,
                      f"{x} on the three finest rungs (1, 0.5, 0.25 ms) by the classes rule: "
                      "resolved in [1.8, 2.2]; at rounding passes; mixed passes unless its lower "
                      "bound exceeds 2.2; reversed fails (rules.dt_study)")
            for x in ("pH_L", "V_b", "K_L", "cycles")]
    out += [
        criterion("J3_state_error_pH", [f"{d}.state_error.pH"], "le", PH_BUDGET,
                  "at 1 ms the Richardson-estimated error of the pH (4/3 D(1, 0.5 ms)) at every "
                  "buffered node, the lumen and the cytosol: the maximum over both (pre-run "
                  "correction, the lead, 15 November 2026)"),
        criterion("J3_state_error_V_b", [f"{d}.state_error.V_b_over_range"], "le", 1e-3,
                  "at 1 ms the Richardson-estimated error of V_b over its range at 1 ms"),
        criterion("J4_reference_pH", [f"{d}.reference.pH_max_abs"], "le", PH_BUDGET,
                  "|pH_engine - pH_reference| at every record at 1 ms (R-closure on the declared "
                  f"world), {J4_NODES}"),
        criterion("J4_start", [f"{d}.reference.start_pH", f"{d}.reference.start_V_b"], "le",
                  START_TOLERANCE, "row 0 is the reference's start at rounding (both from the "
                  "declared pH 7.2 state): the pH at every buffered node, the lumen and the "
                  "cytosol (the maximum over both; pre-run correction, the lead, 15 November "
                  "2026), and V_b"),
        criterion("J4_reported", [f"{d}.reference.{x}_max_abs"
                                  for x in ("pH_L", "pH_c", "V_b", "K_L", "cycles")]
                  + [f"{d}.reference.floor_pH_L", f"{d}.reference.floor_pH"], "ge", 0,
                  "reported beside J4: each node's pH, V_b, lumen K and the pump's cycles against "
                  "the reference; the reference's floor (rtol 1e-11 against 1e-12)", judged=False),
        criterion("J5_envelope_lag", [f"{d}.envelope.max_lag_ph"], "le", PH_BUDGET,
                  "the engine's running maximum of the closure's state-dependent lag estimate "
                  "over every stage of every buffered node (proton_buffer_max_lag_pH, gap 7), on "
                  "every rung: the margin, reported"),
        criterion("J5_envelope_count", [f"{d}.envelope.stages_beyond"], "le", 0,
                  "zero envelope refusals: the engine refuses the step at the first stage beyond "
                  "the budget (B4's stage check), so a completed rung has none, and a refusal "
                  "fails the part"),
        criterion("J6_material", [f"{d}.ledgers.material.max_over_allowance"], "le", 1,
                  "material per species within its allowance (the declared floor plus N eps max "
                  "over records of its total, computed by the judge) at every record of every "
                  "rung"),
        criterion("J6_charge", [f"{d}.ledgers.charge_over_tolerance"], "le", 1,
                  "charge within the capacitor tolerance on every rung"),
        criterion("J6_energy", [f"{d}.ledgers.energy_over_flows_at_declared"], "le", 2e-3,
                  "the energy residual over the integrated flows at every record at 1 ms"),
        criterion("J6_energy_falls", [f"{d}.ledgers.energy.passes"], "ge", 1,
                  "the energy residual falls at second order down the ladder: every successive "
                  "pair by the classes rule with no upper edge (resolved orders >= 1.8)"),
        criterion("J6_reported", [f"{d}.ledgers.energy.smallest_resolved_order"], "ge", 0,
                  "the smallest resolved order of the energy residual, reported", judged=False),
        criterion("J6_bands", [f"{d}.bands.cytosol_pH_max_deviation"], "le", 0.05,
                  "the cytosol's pH within 7.2 +- 0.05 at every stage of every rung"),
        criterion("J7_K1_control_stalls", [f"{d}.controls.k1.control_drop_ph"], "le", 0.1,
                  "K1: with P_K = 0 the lumen's pH falls by less than 0.1 in 900 s"),
        criterion("J7_K1_route_drops", [f"{d}.controls.k1.declared_drop_ph"], "ge", 1.0,
                  "K1: with the route it falls by more than 1 unit"),
        criterion("J7_K1_reference", [f"{d}.controls.k1.reference_control_drop_ph"], "ge", 0,
                  "K1's reference side, reported", judged=False),
        criterion("J7_K2_planted_sign", [f"{d}.controls.k2.pH_max_abs_vs_reference"], "ge",
                  2 * PH_BUDGET, "K2: a self-consistent reversed pump (moves, energetics and "
                  "ledger terms reversed), which every ledger closes, fails J4 by more than its "
                  "budget: max over the buffered nodes (the lumen and the cytosol) and the records "
                  "of |pH - pH_reference| >= 2 x 1e-3 (the lead's rulings)"),
        criterion("J7_K2_reported", [f"{d}.controls.k2.{x}_max_abs_vs_reference"
                                     for x in PH_NODES], "ge", 0,
                  "K2: each node's pH against the reference, reported", judged=False),
        criterion("J7_K3_envelope_flags", [f"{d}.controls.k3.engine_stages_beyond"], "ge", 1,
                  "K3: with the lumen's k_on at 1e-3 /mM/s on the closure's declaration, the "
                  "engine refuses the world at the definition through the envelope check (its "
                  "initial lag estimate about 1e4 pH), the refusal's reason the envelope's (the "
                  "same world admitted with B4's stage check removed): 1 when so"),
        criterion("J7_K3_kinetic_departs", [f"{d}.controls.k3.kinetic_departure_ph"], "ge",
                  PH_BUDGET, "K3: R-kinetic at that k_on departs from the closure beyond 1e-3 pH"),
    ]
    return out


# ------------------------------------------------------------------------ FR-5


def derivation_fr5():
    arms = {}
    for arm, dw in dt_study.FR5_ARMS.items():
        rungs = [n for n, (a, _) in generator.FR5_RUNGS.items() if a == arm]
        pore = dw.pore_cargo_m_s > 0
        arms[arm] = dict(
            ladder_parts=rungs, declared_part=f"{arm}_rung_0p5ms", half_part=f"{arm}_rung_0p25ms",
            control_part=f"{arm}_control", control=stage.CONTROLS[arm], ph50=dw.ph50,
            injury_window_s=list(dw.injury_window_s), conditioned_transfer="moved_X_transfer",
            pore_transfer="moved_X_pore" if pore else None,
            cargo_transfers=["moved_X_transfer"] + (["moved_X_pore"] if pore else []),
            passive_routes=["proton_leak_0", "proton_pore_0", "bounding_0_K", "cargo_transfer_0"]
            + (["cargo_pore_0"] if pore else []),
            exact_heat_routes=["cargo_transfer_0"] + (["cargo_pore_0"] if pore else []),
            judged_heat_routes=["proton_leak_0", "proton_pore_0", "bounding_0_K"])
    return dict(arms=arms, order_observables=["X_L", "pH_L", "V_b"], exact_observables=["d"],
                ph_nodes=PH_NODES,
                x_budget_fraction=dt_study.ARM_T.x_budget_fraction, cytosol_pH=7.2,
                proton_transfers=["moved_H_pump", "moved_H_leak", "moved_H_pore"],
                **_shared(include_cargo=True))


def criteria_fr5():
    out = []
    for arm in ("T", "R"):
        d = f"derived.{arm}"
        out += [criterion(f"J1_{arm}_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                          f"arm {arm}: every rung, its control, the start and the reference "
                          "admitted and run to their ends")]
        out += [criterion(f"J2_{arm}_order_{x}", [f"{d}.orders.{x}.passes"], "ge", 1,
                          f"arm {arm}: {x} on the three finest rungs (0.5, 0.25, 0.125 ms) by "
                          "FR-4's classes rule")
                for x in ("X_L", "pH_L", "V_b")]
        out.append(criterion(f"J2_{arm}_d_exact", [f"{d}.orders.d.at_rounding_every_pair"], "ge",
                             1, f"arm {arm}: the damage d exact at rounding on every rung pair "
                             "(each difference under its floor)"))
        out += [
            criterion(f"J3_{arm}_X_L", [f"{d}.state_error.X_L_over_budget"], "le", 1,
                      "at the declared 0.5 ms the Richardson-estimated error of the lumen's X, in "
                      "X's budget B = 1e-3 X_L(0)"),
            criterion(f"J3_{arm}_pH", [f"{d}.state_error.pH"], "le", PH_BUDGET,
                      "at 0.5 ms the Richardson-estimated error of the pH at every buffered "
                      "node, the lumen and the cytosol: the maximum over both (pre-run "
                      "correction, the lead, 15 November 2026)"),
            criterion(f"J4_{arm}_X_L", [f"{d}.reference.X_L_over_budget"], "le", 1,
                      "|X_L,engine - X_L,reference| <= B at every record (the reference from "
                      "tr.Start)"),
            criterion(f"J4_{arm}_transfer", [f"{d}.reference.transfer_over_budget"], "le", 1,
                      "the conditioned route's cumulative transfer within B at every record"),
            criterion(f"J4_{arm}_pH", [f"{d}.reference.pH_max_abs"], "le", PH_BUDGET,
                      f"|pH_engine - pH_reference| <= 1e-3 at every record, {J4_NODES}"),
            criterion(f"J4_{arm}_start", [f"{d}.start.pH", f"{d}.start.V_b"], "le",
                      START_TOLERANCE, "every rung's and the control's row 0 is the reference's "
                      "start at rounding (one extract for both): the pH at every buffered node, "
                      "the lumen and the cytosol (the maximum over both; pre-run correction, the "
                      "lead, 15 November 2026), and V_b"),
            criterion(f"J4_{arm}_start_X_L", [f"{d}.start.X_L_over_budget"], "le",
                      START_X_OVER_BUDGET, "X_L's row 0 is the reference's (the same products)"),
            criterion(f"J4_{arm}_reported", [f"{d}.reference.floor_X_L_over_budget",
                                             f"{d}.reference.floor_pH_L",
                                             f"{d}.reference.floor_pH",
                                             f"{d}.reference.pH_L_max_abs",
                                             f"{d}.reference.pH_c_max_abs"], "ge", 0,
                      "the reference's floor and each node's pH against the reference, reported",
                      judged=False),
            criterion(f"J5_{arm}_envelope_lag", [f"{d}.envelope.max_lag_ph"], "le", PH_BUDGET,
                      "the engine's running maximum of the closure's lag estimate over every "
                      "stage of every buffered node (gap 7), through the damage window, on every "
                      "rung and the control: the margin, reported"),
            criterion(f"J5_{arm}_envelope_count", [f"{d}.envelope.stages_beyond"], "le", 0,
                      "zero envelope refusals (a stage beyond the budget refuses the step)"),
            criterion(f"J6_{arm}_protons", [f"{d}.protons.max_over_allowance"], "le", 1,
                      "H_eq at each node changes only by its routes' proton transfers (pump, leak, "
                      "proton pore), to H's material allowance, at every record (0.5 ms)"),
            # F4's two clauses, settled before registration (ENERGY_SETTLED): the level on the
            # coarsest rung (the ladder's first value, ladder_parts[0] = 1 ms) and on the
            # declared rung, and the fall down the ladder.
            criterion(f"J7_{arm}_energy", [f"{d}.energy.ladder.values.0",
                                           f"{d}.energy.over_flows_at_declared"], "le", 2e-3,
                      "the energy identity at every record within FR-4's ledger tolerance: the "
                      "residual over the integrated flows <= 2e-3 on the coarsest rung, 1 ms "
                      "(the dt study's F4, as written before any run and kept at 1 ms by the "
                      "lead's Q1 ruling), and on the declared 0.5 ms (pre-registration "
                      "correction, 17 November 2026)"),
            criterion(f"J7_{arm}_energy_falls", [f"{d}.energy.ladder.passes"], "ge", 1,
                      "the energy residual falls at second order down the ladder: every "
                      "successive pair by the classes rule with no upper edge (resolved orders "
                      ">= 1.8), F4's second clause, as FR-4's J6_energy_falls (pre-registration "
                      "correction, 17 November 2026)"),
            criterion(f"J7_{arm}_route_heat",
                      [f"{d}.energy.smallest_judged_route_heat_increment_pJ"], "ge", -1e-12,
                      "the routes §7.5 does not book exactly (the proton leak, the proton pore, "
                      "K+) never lose cumulative heat between records, at -1e-12 pJ (record "
                      "resolution); the exactly booked cargo routes are refused per step by the "
                      "engine"),
            criterion(f"J7_{arm}_reported",
                      [f"{d}.energy.route_heat_increments_pJ.{r}"
                       for r in derivation_fr5()["arms"][arm]["passive_routes"]]
                      + [f"{d}.energy.ladder.smallest_resolved_order"], "ge", -1e-12,
                      "each route's smallest heat increment, and the energy residual's smallest "
                      "resolved order down the ladder, reported", judged=False),
            criterion(f"J8_{arm}_cargo", [f"{d}.cargo.material_over_allowance",
                                          f"{d}.cargo.lumen_over_allowance",
                                          f"{d}.cargo.cytosol_over_allowance"], "le", 1,
                      "X conserved to its material allowance across lumen, cytosol and bath; "
                      "what leaves the lumen arrives in the cytosol on the same routes"),
            criterion(f"J9_{arm}_cytosol_band", [f"{d}.bands.cytosol_pH_max_deviation"], "le",
                      0.05, "the cytosol's pH within 7.2 +- 0.05 at every stage"),
            criterion(f"J9_{arm}_factors", [f"{d}.bands.d_min", f"{d}.bands.d_max",
                                            f"{d}.bands.f_min", f"{d}.bands.f_max"], "within",
                      [0.0, 1.0], "d and f within [0, 1] at every record"),
            criterion(f"J10_{arm}_control_X_L", [f"{d}.control.X_L_over_budget"], "ge", 10,
                      f"the control ({stage.CONTROLS[arm]}) differs from the arm in X_L by at "
                      "least 10 B"),
        ]
        if arm == "T":
            out.append(criterion("J10_T_control_transfer", [f"{d}.control.transfer_over_budget"],
                                 "ge", 10, "f = 1: the conditioned transfer differs by at least "
                                 "10 B"))
            out.append(criterion("J11_T_rate", [f"{d}.claims.engine.above_over_pre"], "le", 0.1,
                                 "while pH_L > pH50 the conditioned route's mean rate is at most "
                                 "1/10 of its pre-damage mean rate (over [0, 60] s), on its "
                                 "cumulative transfer"))
        else:
            out.append(criterion("J10_R_reported", [f"{d}.control.transfer_over_budget",
                                                    f"{d}.control.pH_L_max_abs"], "ge", 0,
                                 "d = 0: the transfer's and the pH's distance, reported",
                                 judged=False))
            out.append(criterion("J11_R_release", [f"{d}.claims.engine.released_in_window"], "ge",
                                 0.8, "at least 0.8 of X_L(0) released through the pore inside "
                                 "the window"))
        out += [
            criterion(f"J11_{arm}_returns", [f"{d}.claims.engine.returns_before_end"], "ge", 1,
                      "pH_L back below pH50 before 400 s"),
            criterion(f"J11_{arm}_crossing", [f"{d}.claims.down_crossing_difference_s"], "le", 5.0,
                      "that crossing within 5 s of the reference's (the same arithmetic)"),
            criterion(f"J11_{arm}_reported", [f"{d}.claims.up_crossing_difference_s"], "ge", 0,
                      "the up-crossing's difference, reported", judged=False),
        ]
    return out


# ------------------------------------------------------------------------ units and resources


def d150(estimate_s):
    """D150's runtime limit: 3 x the estimate plus 600 s, rounded up to the minute."""
    return 60 * math.ceil((3 * estimate_s + 600) / 60)


def unit_steps(which, part):
    """A part's steps: None for the references, 0 for K3 (refused at the definition)."""
    if part == "reference":
        return None
    if part == "control_k3":  # Refused at the definition (the lead's ruling): no step runs.
        return 0
    if which == "fr4":
        return round(900.0 / generator.FR4_RUNGS.get(part, generator.FR4_DECLARED_DT))
    if part == "start":
        return round(stage.START_TIME_S / generator.FR4_DECLARED_DT)
    return round(400.0 / generator.FR5_RUNGS.get(part, (None, dt_study.FR5_DECLARED_DT_S))[1])


def units(which):
    """Each part's steps, its cost at the sizing, its runtime limit (the larger of D150's rule on
    the sizing and on the rehearsal's wall time) and cap, and the rehearsal's measurements."""
    out = {}
    for part in generator.PARTS[which]:
        steps = unit_steps(which, part)
        estimate = (NO_STEPS_ESTIMATE_S if steps is None
                    else steps * SIZING_S_PER_STEP + COMPILE_ALLOWANCE_S)
        wall, peak = REHEARSAL[which][part]
        out[part] = dict(steps=steps, cpu_hours=round(estimate / 3600, 2) if steps else None,
                         runtime_max_s=max(d150(estimate), d150(wall)), cap=UNIT_CAP,
                         rehearsal=dict(wall_s=wall, memory_peak=peak))
        if part == "reference":
            out[part]["note"] = "the references: minutes"
        elif part == "control_k3":
            out[part]["note"] = "refused at the definition through the envelope: seconds"
    return out


def resources(which):
    name = FILES[which]
    entry = (f"{PYTHON} -B -m validation.tissue.compartment_ph_qualification judged "
             f"SNAPSHOT/validation/compartment_ph/protocols/{name} OUT/PART PART")
    out = dict(
        status="filled from the rehearsal (run-e79b4232, 17 November 2026): one unit per CPU, its "
               "runtime limit RUNTIME_MAX_S = judge.units[PART].runtime_max_s and its cap CAP = "
               "judge.units[PART].cap; the CPUs are the lead's at the launch",
        environment="from the snapshot's root, PYTHONPATH=SNAPSHOT/src:SNAPSHOT, "
                    "JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu, CUDA_VISIBLE_DEVICES= (empty), "
                    "PYTHONDONTWRITEBYTECODE=1, CPU backend only, float64",
        unit=(f"scripts/run_detached.sh {which}-PART CAP --cpus CPU --oom-first --runtime-max "
              "RUNTIME_MAX_S --dir SNAPSHOT --env PYTHONPATH=SNAPSHOT/src:SNAPSHOT --env "
              "JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu --env CUDA_VISIBLE_DEVICES= --env "
              f"PYTHONDONTWRITEBYTECODE=1 -- {entry}"),
        judge=(f"{PYTHON} -B -m validation.tissue.compartment_ph_judge judged "
               f"SNAPSHOT/validation/compartment_ph/protocols/{name} OUT/verdict "
               "OUT/*/results.json (in its own unit: 1G, 600 s; it runs nothing)"),
        runtime_max_rule="the larger of D150's rule on the sizing, 3 x (steps x 1.5 ms + 90 s of "
                         "compile) + 600 s (300 s as the estimate of a part without steps), and "
                         "D150's rule on the rehearsal's wall time, 3 x wall + 600 s, each rounded "
                         "up to the minute (the lead's ruling, 17 November 2026)",
        caps="2G per unit: the rehearsal's peaks were 1.3-1.4G for every engine part, 0.11G for "
             "K3 and 0.06G for the references; the judge 1G",
        cost_note="the rehearsal (run-e79b4232: snapshot e79b4232 on CPUs 6, 7, 22 and 23, two "
                  "pairs of sibling hyperthreads, all four busy, so not a quiet-core rate) "
                  "measured 1.43-2.21 ms per step of execution and 74-134 s of compile per engine "
                  "unit; the units' cpu_hours use the lead's sizing, 1.5 ms per step plus 90 s. "
                  "The earlier basis, 0.95 ms per step plus about 48 s, was FR-4's world on a "
                  "quiet core (fr45-transporter 427e4a05, CPU 1; pre-run correction, the lead, 15 "
                  "November 2026)",
        no_wait_headroom="judged units run without --wait-headroom: the wait would run inside "
                         "the unit and count against its runtime limit; the lead checks the "
                         "slice's room before each launch",
        attempts=f"{HARNESS_RULE} (harness_limits)",
        enforced_by="the launcher alone (run_detached.sh's MemoryMax, CPUAffinity and "
                    "RuntimeMaxSec, with the values above): neither the generator nor the judge "
                    "reads these fields",
    )
    if which == "fr5":
        out["order"] = ("the start unit first; when it has written OUT/start/start.json, every "
                        "other unit with --start OUT/start/start.json appended (the references "
                        "take minutes); the judge last")
    return out


def judge_section(which):
    derivation, criteria = ((derivation_fr4(), criteria_fr4()) if which == "fr4" else
                            (derivation_fr5(), criteria_fr5()))
    return dict(
        written=WRITTEN,
        generator="validation/tissue/compartment_ph_qualification.py (records only)",
        judge="validation/tissue/compartment_ph_judge.py (reads records, never runs)",
        references="validation/tissue/compartment_ph_reference_stage.py (the references through "
                   "their usage note's API)",
        derivation=derivation, criteria=criteria, units=units(which),
        resources=resources(which),
        engine_readouts=generator.ENGINE_READOUTS,
    )


ASKED = {  # The questions as asked (15 November 2026), now ruled:
    "fr4": [
        "1. K2: 'J4 must fail by more than its budget' is read as |pH - pH_reference| >= 2e-3 (the "
        "excess over the budget at least the budget). Confirm, or give the reading",
        "2. J6's 'falls at second order down the ladder' has no band: the smallest resolved order "
        "of the energy residual over flows is judged >= 1.8 (the band's lower edge; falling "
        "faster is no defect). Confirm",
        "3. Cost: with the ladder and the controls inside the judged run, the upper bound is 6.75 "
        "CPU-h for the rungs plus 2.7 for K1-K3 (the runbook's 0.9 was one rung); as parallel "
        "units the 0.25 ms rung bounds the wall time at about 3.6 h, for the development dt "
        "study, the rehearsal and the judged run each",
        "4. K3's engine part reruns the 1 ms world only for the envelope at the lowered k_on (the "
        "trajectory is rung_1ms's, since k_on enters only the check): keep it as its own 0.9 "
        "CPU-h unit, as 'at run time' says?",
        "5. J6's material check uses the engine's own per-species tolerance, the declared floor "
        "plus its rounding allowance, which the seam must report: the cytosol holds about 105 "
        "fmol of H_eq (one ulp is 1.4e-14 fmol), so the declared H floor of 1e-16 fmol cannot "
        "hold alone",
        "6. The resolution rule is this draft's choice: a rung difference counts only at or above "
        "N eps max|q| (N the finer rung's steps, a worst-case accumulation), and an observable "
        "whose finest differences fall under it has no order, so J2 fails for it. Lumen K at "
        "the 0.25 ms rung needs a difference of about 7e-9 fmol (3.6e6 steps x eps x 9.2 "
        "fmol). Keep the rule, or judge such an observable as converged at rounding?",
    ],
    "fr5": [
        "1. dt_study_criteria_written_first still says 'state error at 1 ms as J3' and 'the "
        "declared 1 ms stands', from before the step moved to 0.5 ms (the ruling, and J3's own "
        "text). The dt study's criteria (validation/compartment_ph/dt_study.FR5_CRITERIA) follow "
        "J3 at 0.5 ms. Correct the block's text?",
        "2. outcome_rules says 'PASS when J1-J10 hold', but J11 exists and is judged here. "
        "Include it?",
        "3. J2 lists the damage d, whose step is exact (cells.damage.bounding_patch_damage@1 on piecewise-"
        "constant schedules whose breakpoints lie on every rung's grid), so its rung differences "
        "are rounding: its order is None and J2 fails for d by construction. Proposed: d's item "
        "becomes 'exact at rounding on every rung' (max |d(dt) - d(dt/2)| <= N eps), or d "
        "leaves J2",
        "4. The controls run at the declared 0.5 ms only, while J1 reads 'both arms and their "
        "controls ... at every rung': controls on every rung would add about 5.2 CPU-h per arm",
        "5. J6's 'to the material floor': as FR-4's question 5 (the engine's own H tolerance)",
        "6. J7's 'each passive route's heat >= 0' is judged on the increments of each route's "
        "cumulative heat between records, at >= -1e-12 pJ (the booking probe's allowance)",
        "7. Cost: the start 1.8 CPU-h, then per arm 6.0 for the ladder and 0.8 for the control: "
        "15.4 CPU-h upper bound; as parallel units about 2 h for the start, then 3.2 h for the "
        "0.125 ms rungs",
        "8. The resolution rule, as FR-4's question 6: a difference counts at N eps max|q| or "
        "above, else the observable has no order and J2 fails for it (the 0.125 ms rungs take "
        "3.2e6 steps)",
    ],
}
RULED = "pre-run correction, 15 November 2026, the lead's ruling on"
RULINGS = {
    "fr4": [
        "Q1 (K2): confirmed. K2 is caught when the maximum over records of |pH_engine - "
        "pH_reference| >= 2e-3",
        "Q2 (the energy residual's order): confirmed. The smallest resolved order of the energy "
        "residual is >= 1.8 and faster is no defect; Q6's classes apply to it, with no upper edge",
        "Q3 (cost): not a discrepancy. The runbook's 0.9 CPU-h was one 1 ms rung, and that figure "
        "is the charged-patch test's upper bound from another world; the first development rung "
        "measures the real cost before anything is budgeted, and the lead sets the rehearsal's "
        "horizon from it",
        "Q4 (K3's unit): confirmed. K3's engine part stays its own unit at 1 ms, because the "
        "run-time flag is what it tests; it needs gap 7's per-stage count or maximum, scheduled "
        "by the core before FR-4's registration",
        "Q5 (the H floor): the 1e-16 fmol H floor sits below one ulp of the cytosol's H_eq, so the "
        "check changes: the material allowance is the declared floor plus N eps max over records "
        "of the species' total (N the run's steps), computed by the judge from the records, never "
        "read from the engine, and reported per species",
        "Q6 (resolution): one ruling with FR-5's Q3 and Q8. The floor F = N eps max|q| (N the "
        "finer rung's steps) is kept; on the two judged differences, each with its own floor: "
        "resolved (both >= F) lies in [1.8, 2.2]; at rounding (both < F) passes; mixed (the "
        "coarser >= F, the finer < F) passes unless the implied lower bound log2(coarser "
        "difference / finer floor) exceeds 2.2; reversed (the coarser < F, the finer >= F) "
        "fails. The judge reports each observable's class with its differences and floors; J3 "
        "and J4 still judge every observable against its budget",
    ],
    "fr5": [
        "Q1 (the dt-study block): 'state error at 1 ms as J3' becomes 'state error at the "
        "declared 0.5 ms, as J3', and 'the declared 1 ms stands' becomes 'the declared 0.5 ms "
        "stands'; the energy-residual line stays at 1 ms (<= 2e-3 at the coarsest rung, falling "
        "at second order), since moving it to 0.5 ms would loosen it about fourfold",
        "Q2 (the outcome rule): J11 is included: PASS needs J1-J11 for both arms",
        "Q3 (d in J2): d stays in J2, written as 'exact at rounding on every rung pair (each "
        "difference under its floor)', fixed before the run; under Q8's classes it passes at "
        "rounding",
        "Q4 (the controls' rungs): the controls run at the declared 0.5 ms only; J1 reads 'both "
        "arms at every rung, and their controls at the declared step', as FR-4's controls are at "
        "1 ms",
        "Q5 (the H floor): as FR-4's Q5, for J6's and J8's route ledgers and X's conservation",
        "Q6 (route heat): increments between records can hide a negative step. The routes §7.5 "
        "books exactly (the cargo routes: X is neutral and moved only by them) are refused per "
        "step by the engine when a raw share is negative, and a refusal is a verdict; the rest "
        "(the proton leak, the proton pore, K+) are judged on their increments at >= -1e-12 pJ, "
        "disclosed as record resolution, with each route's smallest increment reported",
        "Q7 (cost): as FR-4's Q3",
        "Q8 (resolution): as FR-4's Q6",
    ],
}
# The prose the rulings correct (leaf paths of the protocol, set by `draft`).
PROSE = {
    "fr4": {
        ("criteria", "J2_orders"): "observed orders of lumen pH, V_b, lumen K and pump cycles on "
        "the three finest rungs, by the classes rule (rules.dt_study)",
        ("criteria", "J6_ledgers"): "the ledgers rule (material within its allowance), and the "
        "bands rule",
        ("criteria", "J4_reference"): "the reference rule at 1 ms: |pH_engine - pH_reference| <= "
        "1e-3 at every record at every buffered node, the lumen and the cytosol (the maximum over "
        "both nodes and every record; pre-run correction, the lead, 15 November 2026), with V_b, "
        "lumen K and pump cycles reported against the reference beside it",
        ("rules", "dt_study"): "S5's form, as D150's and MG0c's: per record, the step term "
        "|q(dt) - q(dt/2)|, and the observed orders log2 of successive max-norm differences on "
        "the three finest rungs; the rule detects bias, not order. Each difference has its floor "
        "F = N eps max|q| (N the finer rung's steps). On the two judged differences: resolved "
        "(both >= F) lies in [1.8, 2.2]; at rounding (both < F) passes; mixed (the coarser >= F, "
        "the finer < F) passes unless the implied lower bound log2(coarser difference / finer "
        "floor) exceeds 2.2; reversed (the coarser < F, the finer >= F) fails; each observable's "
        "class is reported with its differences and floors (pre-run correction, the lead, 15 "
        "November 2026)",
        ("rules", "envelope"): "the closure's estimated first-order lag behind the kinetic system, "
        "(rho/lambda)(beta/ln 10 - h)/(h ln 10), within 1e-3 pH at every stage of every buffered "
        "node (rapid_proton_buffer.lag_estimate_ph). The engine refuses the step at the first "
        "stage beyond it (B4's stage check), so a completed part has none and a refusal fails "
        "the part; it reports the running maximum of the estimate over every stage "
        "(proton_buffer_max_lag_pH, gap 7) as the margin (pre-run correction, the lead, 15 "
        "November 2026). Revised before registration: the FR-4 references' run 02 showed the "
        "earlier fixed ratio lambda >= 1e3 rho does not imply the budget (it passes from k_on "
        "0.83 /mM/s, the budget only from about 1.28e4)",
        ("criteria", "J1_admission"): "the four rungs, K1, K2 and the reference admitted and run "
        "without refusal; K3 is refused by design, its catch J7 (pre-run correction, the lead, "
        "15 November 2026)",
        ("criteria", "J5_envelope"): "the envelope rule: zero envelope refusals, and the engine's "
        "reported running maximum of the lag estimate within 1e-3 pH at every buffered node",
        ("controls", "K2_planted_sign"): "a self-consistent reversed pump (the lead's ruling "
        "(b), 15 November 2026), defined physically: the declared world with its pump's two "
        "sides exchanged in the law. The same population on the bounding patch (capacity k, n = "
        "2, K_H, K_ATP, the held fuel at the cytosol, availability 1) hydrolyses one ATP at the "
        "cytosol per forward cycle and moves n H+ from the lumen to the cytosol. Its cycle free "
        "energy is dG_cyc = d_rG'_ATP + n [RT ln(h_c/h_L) + F V_b], with V_b = phi_c - phi_L and "
        "h_c, h_L the free protons; its rate is J = k a S (1 - exp(dG_cyc/RT)), S = [1 + "
        "(K_H/h_L)^n]^-1 [1 + K_ATP/c_ATP]^-1, saturating on the lumen's free proton, the side it "
        "takes protons from. Per cycle: the lumen's H_eq -n and the cytosol's +n, a charge n e "
        "from the lumen to the cytosol; heat -J dG_cyc >= 0; the maintenance's work -J "
        "d_rG'_ATP. Every ledger closes, so only J4 can catch it: it must fail by more than its "
        "budget, and the independent reference computes its trajectory and records that its "
        "effect exceeds the budget (D176's G3). The pump's moves flipped alone (+n per forward "
        "cycle) are refused by the engine's material ledger: a unit guard in the tests, not a "
        "judged control",
        ("controls", "K3_closure_outside"): "the lumen buffer's k_on lowered to 1e-3 mM-1 s-1 (1 "
        "M-1 s-1): the engine refuses the world at the definition through the envelope check "
        "(its initial lag estimate about 1e4 pH; the reason the envelope's, since the same world "
        "is admitted with B4's stage check removed), and in the kinetic reference the closure "
        "departs beyond 1e-3 pH units",
        ("world", "builder"): "validation/compartment_ph_engine/definitions.py "
        "fr4_world(parameters.World())",
        ("rules", "state_error"): "at the declared 1 ms, the Richardson-estimated error of the pH "
        "at every buffered node, the lumen and the cytosol (the maximum over both), <= 1e-3 pH "
        "units and of V_b <= 1e-3 of its range (pre-run correction, the lead, 15 November 2026)",
        ("rules", "timing"): "each unit through scripts/run_detached.sh; one rung per unit; on "
        "the vector path (the execution path) FR-4's world costs 0.95 ms per step after about "
        "48 s of compile per unit (measured on fr45-transporter 427e4a05, CPU 1), replacing the "
        "charged-patch test's upper bound of 0.9 CPU-hours per 1 ms rung: the 900 s world at 1 ms "
        "about 15 minutes, the ladder's 6.75e6 steps about 1.8 CPU-hours, K1 and K2 about 15 "
        "minutes each and K3 seconds; the rehearsal runs the full horizon (pre-run correction, "
        "the lead, 15 November 2026). The rehearsal (run-e79b4232) measured 1.43-2.21 ms per step "
        "on sibling hyperthreads, and each unit's runtime limit and cap are judge.units' "
        "(judge.resources.runtime_max_rule; pre-registration correction, 17 November 2026)",
        ("rules", "ledgers"): "material per species within its allowance at every record: the "
        "declared floor plus N eps max over records of the species' total over the cell, the "
        "lumen and the bath (N the run's steps), computed by the judge from the records and "
        "reported per species (pre-run correction, the lead, 15 November 2026); charge within "
        "the capacitor tolerance; energy residual over flows <= 2e-3 at 1 ms (today's booking), "
        "falling at second order down the ladder (the classes, with no upper edge)",
    },
    "fr5": {
        ("criteria", "J1_admission"): "both arms at every rung, and their controls at the "
        "declared step, admitted and run without refusal",
        ("criteria", "J2_orders"): "the dt study's orders on the three finest rungs, for the "
        "lumen's X, the lumen's pH and V_b, by FR-4's classes rule; the damage d exact at rounding "
        "on every rung pair (each difference under its floor)",
        ("criteria", "J6_protons"): "H_eq conserved except across routes: the change of H_eq at "
        "each node equals the sum of its routes' proton transfers (pump, leak, proton pore) to "
        "H's material allowance (FR-4's rules.ledgers), at every record",
        ("criteria", "J7_energy"): "the energy identity at every record: stored change + heat = "
        "the maintenance's supplied work, within FR-4's ledger tolerance (the residual over the "
        "integrated flows <= 2e-3) on the coarsest rung, 1 ms, and on the declared 0.5 ms, "
        "falling at second order down the ladder: the dt study's F4 (pre-registration "
        "correction, 17 November 2026); each passive route's "
        "heat >= 0: the routes §7.5 books exactly (the cargo routes) are refused per step by the "
        "engine, and the rest (the proton leak, the proton pore, K+) are judged on their "
        "increments between records at >= -1e-12 pJ (record resolution), each route's smallest "
        "increment reported",
        ("criteria", "J8_cargo"): "X conserved across lumen, cytosol and bath to its material "
        "allowance; whatever leaves the lumen arrives in the cytosol on the same route",
        ("criteria", "J3_state_error"): "at the declared 0.5 ms, the Richardson-estimated error of "
        "the lumen's X <= the X budget and of the pH at every buffered node, the lumen and the "
        "cytosol (the maximum over both), <= 1e-3 (pre-run correction, the lead, 15 November "
        "2026)",
        ("budgets", "pH"): "|pH_engine - pH_reference| <= 1e-3 at every record at every buffered "
        "node, the lumen and the cytosol, the maximum over both nodes (FR-4's J4; pre-run "
        "correction, the lead, 15 November 2026)",
        ("dt_study_criteria_written_first", "checks"): [
            "admission of every rung", "orders as J2",
            "state error at the declared 0.5 ms, as J3",
            "energy residual <= 2e-3 at 1 ms, falling at second order",
            "the envelope as J5 on every rung"],
        ("dt_study_criteria_written_first", "verdict"): "the declared 0.5 ms stands if every "
        "check holds; otherwise the arm declares the finest rung that passes, reported, not "
        "repaired",
        ("outcome_rules",): "PASS when J1-J11 hold for both arms; otherwise the failing criteria "
        "are reported with their values, without repair or retuning after the judged run",
    },
}

# The harness-limit rule (the lead's ruling of 17 November 2026, before registration: text only).
HARNESS_RULE = (
    "a part ended by its runtime limit or its memory cap (as by any other infrastructure ending: a "
    "signal, an incomplete results.json) is a harness failure, not a verdict: the judged run is "
    "void and is relaunched once, whole, from the same snapshot under the same protocol, into a "
    "new output directory; the void attempt is kept and reported beside the relaunch's verdict. A "
    "second harness failure goes to the lead. A refusal by the engine is a verdict, never a "
    "harness failure"
)

# The text brought level with the runs before registration (the lead's ruling, 17 November 2026:
# text only, no criterion changed), set by `draft` as PROSE's leaves are.
SCOPE_LINE = ("The verdict covers cells.operator.cell_owned_compartments@1 as built at the judged snapshot "
              "(refusal 4 version 1.2, refusal 5 version 1.1)")
LEVEL_NOTE = ("its text brought level with the runs before registration on 17 November 2026, no "
              "criterion changed")
LAUNCH = ("each judged unit through scripts/run_detached.sh as judge.resources has it: one unit "
          "per CPU, its cap and runtime limit from judge.units, --oom-first, no --wait-headroom; "
          "the judge in its own unit")
OPTION_A = ("The judged run follows once, from a fresh clean snapshot of main taken after the "
            "registration commit, past seam F (the lead's ruling of 17 November 2026: option (a))")
MODELS_COMMON = [
    "cells.model.resolved_pump_composite@1, the declared world: the composite with cells.model.resolved_pump_tissue@3 as "
    "its inner model and FR-1's compartment operator "
    "(validation/compartment_ph_engine/definitions.declared_world)",
    "cells.model.resolved_pump_tissue@3, the inner model, with its stage-read, transporter, held-row and "
    "face-free-term insertion points",
]
FR4_KINDS = [
    "cells.kind.rapid_proton_buffer@1, the kind of the stage read cells.kind.rapid_proton_buffer@1 (a declared "
    "reduced representation, D175)",
    "cells.kind.transporter@1, the kind of the pump on the bounding patch: the law "
    "cells.cycle.proton_atp_mass_action_positive@1 on the fuel kind cells.fuel_kind.maintained_held_rows@1 (the held "
    "ATP, ADP and Pi rows at the cytosol)",
    "cells.kind.passive_routes@1, the kind of the proton leak on the bounding patch: the law "
    "cells.route.proton_constant_field_leak@1",
    "cells.route.constant_field@1, the bounding patch's own law: the K+ counterion route",
]
LEVEL = {
    "fr4": {
        ("status",): "PROPOSED (drafted 15 November 2026 by the FR-4/FR-5 physics owner on branch "
        f"fr45-physics; {LEVEL_NOTE}). Its dt study and its rehearsal have run on the integrated "
        "candidate (development_runs); registration is the lead's",
        ("registration_plan", "no_judged_run_yet"): "No judged run yet. The engine path is wired "
        "and has run for development: the dt study (dev-3c10b833-dt) and the rehearsal on a "
        "registered dry-run copy (run-e79b4232: 21 of 21 judged criteria, every part's records "
        "bitwise the dt study's)",
        ("registration_plan", "launch"): LAUNCH,
        ("registration_plan", "path"): "The lead registers it on main, after its dt study and "
        f"its rehearsal (the D150/MG0c path, both done). {OPTION_A}; the judge's compare of every "
        "judged part against the rehearsal's (run-e79b4232) is its full-horizon check across F, "
        "expecting every part identical",
        ("development_runs",): dict(
            runs=[dict(path="/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/"
                            f"charged_patch/run-0{k}", status=status)
                  for k, status in ((2, "development (charged-patch test), not this world"),
                                    (3, "development (charged-patch test), not this world"),
                                    (4, "development (state against booking), not this world"))],
            fr4_world_runs=[
                dict(path=f"{PIPELINE}/dev-3c10b833-dt", status="development: the dt study, from "
                     "snapshot 3c10b833 on the vector path and the declared world; not judged",
                     reading="J1-J7 pass in its development reading (reading/verdict.json)"),
                dict(path=f"{REHEARSAL_RUN}/fr4", status="the rehearsal, on a registered dry-run "
                     "copy from snapshot e79b4232; not a verdict",
                     reading="21 of 21 judged criteria pass (verdict/verdict.json); every part's "
                     "records bitwise the dt study's, run times apart (compare/)")]),
        ("engine_models",): [*MODELS_COMMON, *FR4_KINDS,
                             "cells.operator.cell_owned_compartments@1, FR-1's operator: the compartment's "
                             "identity (refusal 4 version 1.2, refusal 5 version 1.1)"],
        ("scope",): "Maintained fuel only (no depletion or recovery: that is the finite-fuel "
        "case's acceptance, D176 item 2). The K+ counterion only, at 5e-10 m/s (Cl- at lysosomal "
        "values and every ionic pore wait for the implicit patch). A lumped population of N = 1000 "
        "identical compartments as one node, declared; the single-compartment form is reported, "
        "not judged, in version 1 (a later version may judge it once species-scaled energy floors "
        "exist). Fixed volume (no water). The cytosol's pH within its fuel band (7.2 ± 0.05). "
        "Explicit ARS(2,2,2) at the world's declared dt; no implicit patch in this rung. "
        f"{SCOPE_LINE}",
        ("references", "self_tests"): "tests/unit/test_fr45_proton_laws.py, "
        "test_fr45_damage_and_worlds.py, test_fr45_patch_implicit.py (tier 1)",
    },
    "fr5": {
        ("status",): "PROPOSED (drafted 15 November 2026 by the FR-4/FR-5 physics owner on branch "
        f"fr45-physics; {LEVEL_NOTE}). Its world agreement, its dt study and its rehearsal have "
        "run on the integrated candidate (development_runs); registration is the lead's. The arm "
        "values and restated claims are confirmed by the references' readout (branch 931fb38a; "
        "compartment-transfer-arms-01-readout.* beside /mnt/workspaces/Cells/"
        "independent-references-20261115-01/compartment-transfer-arms-01/), which reran the "
        "record's own worlds and reproduced it exactly",
        ("registration_plan", "no_judged_run_yet"): "No judged run yet. The engine path is wired "
        "and has run for development: the world agreement (worlds-d82e1935), the dt study "
        "(dt5-a6639e79) and the rehearsal on a registered dry-run copy (run-e79b4232: 51 of 51 "
        "judged criteria, every part's records bitwise the dt study's apart from the start "
        "extract's identity)",
        ("registration_plan", "path"): "The lead registers it on main, after its dt study and "
        f"its rehearsal (the D150/MG0c path, both done). {OPTION_A}, FR-5's start part first from "
        "the same snapshot; the judge's compare of every judged part against the rehearsal's "
        "(run-e79b4232) is its full-horizon check across F, expecting only the start extract's "
        "identity to differ",
        ("registration_plan", "launch"): f"{LAUNCH}; FR-5's start part first",
        ("development_runs",): dict(
            runs=[
                dict(path=f"{PIPELINE}/worlds-d82e1935", status="development: the world "
                     "agreement over 400 s, both arms, from snapshot d82e1935; not judged",
                     reading="the declared world bitwise the development world on both arms, "
                     "800000 steps each (check.json)"),
                dict(path=f"{PIPELINE}/dt5-a6639e79", status="development: the dt study, from "
                     "snapshot a6639e79 on the vector path and the declared world; not judged",
                     reading="J1-J11 pass on both arms in its development reading "
                     "(reading/verdict.json), and again under the energy line settled on 17 "
                     "November 2026 (rehearsal-20261117/dt5-a6639e79-reread/)"),
                dict(path=f"{REHEARSAL_RUN}/fr5", status="the rehearsal, on a registered dry-run "
                     "copy from snapshot e79b4232; not a verdict",
                     reading="51 of 51 judged criteria pass (verdict/verdict.json); every part's "
                     "records bitwise the dt study's, run times apart, except the start "
                     "extract's identity (compare/)")],
            note="the charged-patch test's runs (fr45/charged_patch/) are development evidence "
                 "for the explicit limit only"),
        ("engine_models",): [
            *MODELS_COMMON,
            "FR-4's kinds and laws, unchanged: " + "; ".join(FR4_KINDS),
            "cells.kind.passive_routes@1 also carries FR-5's routes: cells.route.passive_neutral_permeation@1 (the "
            "conditioned transfer and the cargo pore) and cells.route.proton_constant_field_leak@1 (the "
            "proton pore)",
            "cells.kind.patch_damage@1, the kind of the damage control state: the law "
            "cells.damage.bounding_patch_damage@1, exact per step",
            "cells.kind.ph_condition@1, the kind of the condition: the law cells.transfer_factor.ph_conditioned_factor@1",
            "the routing door, which multiplies the routes' openings by their factors",
            "cells.operator.cell_owned_compartments@1, FR-1's operator: refusal 4 version 1.2 (its FACTOR_KINDS "
            "admit the two source kinds) and refusal 5 version 1.1 (it admits the charged 1800 s "
            "start)"],
        ("scope",): "FR-4's scope (maintained fuel, the K+ counterion, a lumped population of 1000 "
        "as declared, fixed volume, explicit ARS(2,2,2)), plus FR-5's damage, a proton pore and a "
        "neutral cargo pore. Ionic pores are refused in version 1 (they wait for the implicit "
        f"patch). The single-compartment form is reported, not judged. {SCOPE_LINE}",
    },
}
for _which, _leaves in LEVEL.items():
    PROSE[_which].update(_leaves)
    PROSE[_which][("harness_limits",)] = HARNESS_RULE[0].upper() + HARNESS_RULE[1:]


DISCLOSURE = (
    "The machine criteria (judge.criteria), the judge's arithmetic (judge.derivation and "
    "validation/tissue/compartment_ph_judge.py's docstring) and the units were written on 15 "
    "November 2026 from this protocol's prose criteria, rules and controls, before any run of this "
    "world (no engine run exists). The registration plan moved from 'registration' to "
    "'registration_plan' so that the registration path adds the lead's record under "
    "'registration' (MG0c's form), and judged_parts names the generator's parts")


CHARGE_CHECK = (
    "pre-run correction, 15 November 2026, the lead's ruling on the charge check: it reads the "
    "engine's charge residual and its capacitor tolerance from the records (ledgers."
    "charge_residual_C and charge_tolerance_C); Q5's record-computed allowance (the judge's, from "
    "the amounts) covers material only, since computing charge from the records would need the "
    "node charges and capacitances in them"
)
J4_NODES_FR4 = (
    "pre-run correction, 15 November 2026, the lead's ruling on J4's node: J4, and so K2's catch, "
    "judges the pH of every buffered node, the lumen and the cytosol: the maximum over both nodes "
    "and every record of |pH_engine - pH_reference| within 1e-3 (K2: at least 2e-3). The protocol "
    "had not named the node. The independent references found that either reading catches K2(b) "
    "(R-closure: the lumen's difference reaches 2e-3 at the first record, 1 s, and the cytosol's "
    "at 35 s; 3.276 and 0.0192 pH at 900 s)"
)
J4_NODES_FR5 = (
    "pre-run correction, 15 November 2026, the lead's ruling on the pH budget's node, as FR-4's "
    "J4: the pH budget judges every buffered node, the lumen and the cytosol: the maximum over "
    "both nodes and every record of |pH_engine - pH_reference| within 1e-3, against the "
    "reference started at tr.Start (J4); it had named the lumen alone"
)
J3_START_NODES = (
    "pre-run correction, 15 November 2026, the lead's ruling on J3's and J4_start's nodes: as "
    "J4's, the Richardson-estimated state error of the pH (J3) and the start check (J4_start, row "
    "0 against the reference at rounding) judge the pH of every buffered node, the lumen and the "
    "cytosol, the maximum over both; V_b stays as written. Stricter, and free: the records hold "
    "both nodes"
)
MODULE_PATHS = (
    "pre-run correction, 16 November 2026, the lead's ruling on the module paths (paths only): the "
    "lane's engine-facing modules moved from validation/compartment_ph/ to "
    "validation/compartment_ph_engine/ (parameters, definitions and dt_study; with them on "
    "fr45-transporter engine_records, planted, compare_reference, path_agreement and "
    "refusal_paths), so validation/compartment_ph/ holds the independent references' code-blind "
    "modules alone (their isolation tests: nothing there imports cells, jax or validation.tissue), "
    "with this protocol beside them. The driver and the world's builder name the new paths; "
    "earlier text naming the old ones (the execution path's correction, the questions as asked) "
    "reads with the new folder. Nothing else changes"
)
DECLARED_WORLD_FR4 = (
    "pre-run correction, 16 November 2026, the lead's ruling on the judged world: every engine "
    "part runs the declared world, fr4_world with FR-1's compartment operator, which is what the "
    "world's builder describes (validation/compartment_ph_engine/definitions.declared_world: the "
    "composite cells.model.resolved_pump_composite@1, @3 inner, cells.operator.cell_owned_compartments@1 with refusal 4's "
    "version 1.1), in place of the development world without the operator, which development runs "
    "keep. Measured before any judged run (fr45-compartment-op e73e4afd, CPU 1, the vector path; "
    "/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/pipeline/dev-e73e4afd-declared/): the "
    "declared world's records are bitwise equal to the development world's at 20 s and at all 901 "
    "records over 900 s (every series, amount row, stage extremum and ledger), since the operator "
    "adds identity and refusals only"
)
DECLARED_WORLD_FR5 = (
    "pre-run correction, 16 November 2026, the lead's ruling on the judged world, as FR-4's: every "
    "engine part runs the declared world with FR-1's compartment operator (the composite, "
    "definitions.declared_world), in place of the development world without it; FR-4's world "
    "showed the two bitwise equal over 900 s (fr45-compartment-op e73e4afd, "
    "dev-e73e4afd-declared/), and FR-5's world is checked the same way once its kinds are wired"
)
EXECUTION_PATH = (
    # Recorded text: the registered FR-4 and FR-5 protocols hold this ruling word for word, so no
    # move changes it (D188 move 2). Its module name is never resolved as a module.
    "pre-run correction, 15 November 2026, the lead's ruling on the execution path: every engine "
    "part runs its world as the one world of a vector window (cells.core.vector_windows; the "  # noqa: E501  source-moves: keep
    "generator's judged runs, validation/compartment_ph/engine_records.run with path 'vector'), "
    "which checks every accepted row on the device with the host checks' own functions and bounds "
    "(the domain with the kinds' domains and B4's read; the ten ledgers with the kinds' terms "
    "against the same ledger limits and magnitudes; dissipation at the same 1e-12 pJ tolerance) "
    "in place of the windowed runner's checks on the host. The in-step checks (B4's read and "
    "envelope, the pump's domain and pH band, B7 per stage and node, the bookings' validity) are "
    "the same compiled step on both paths, and the observed rows' readouts and continuity checks "
    "stay on the host; the host path stays for development. Measured before any judged run "
    "(fr45-transporter 427e4a05, CPU 1, FR-4's rung_1ms over 20 s on both paths from one clean "
    "snapshot): every record bitwise equal to the host path's except two leak accumulators (the "
    "leak's cumulative proton transfer and heat, relative 5e-14 and 1e-13); the check "
    "diagnostics differ at rounding only; a refusal differs in its text (the device path's "
    "WorldCheckError names the failed checks and the first failing row), not in its verdict; the "
    "run phase 7.46 times faster (0.95 against 7.13 ms per step), the compile cost named as such "
    "(48 s against 23 s per unit), so every judged unit runs about 7.5 times faster"
)
COST_FR4 = (
    "pre-run correction, 15 November 2026, the lead's ruling on the cost and the rehearsal: on the "
    "vector path a pass costs about the ladder's 6.75e6 steps at 0.95 ms per step (about 1.8 "
    "CPU-hours), K1 and K2 about 15 minutes each and K3 seconds, with about 48 s of compile per "
    "unit; that measured per-step cost replaces the charged-patch test's 0.9 CPU-hour upper "
    "bound in the timing rule (Q3's ruling: the first development rung measured it, 0.27 ms per "
    "step and 7.08 ms of host checks per row over 900 s on the host path), and at that cost the "
    "rehearsal runs the full horizon, not a shortened one"
)
COST_FR5 = (
    "pre-run correction, 15 November 2026, the lead's ruling on the cost and the rehearsal, as "
    "FR-4's: on the vector path FR-5's units scale with FR-4's measured 0.95 ms per step (about "
    "48 s of compile per unit; FR-5's world, with more routes and rows, at its own rate, measured "
    "by its rehearsal), in place of the charged-patch test's upper bound, and the rehearsal runs "
    "the full horizon, not a shortened one"
)
ENERGY_SETTLED = (
    "pre-registration correction, 17 November 2026, the energy criterion, settled by the FR owner "
    "at the lead's order of 16 November (the dt study's F4 and the protocol's J7 to agree before "
    "registration), its direction approved by the lead on 17 November: J7 now judges F4 as it was "
    "written before any run (dt_study.FR5_CRITERIA and dt_study_criteria_written_first) and as "
    "the lead's Q1 ruling kept it at 1 ms. J7_*_energy judges the energy residual over the "
    "integrated flows <= 2e-3 on the coarsest rung, 1 ms (the ladder's first value), as well as "
    "on the declared 0.5 ms, which it alone had read; J7_*_energy_falls judges its fall at second "
    "order down the ladder (every successive pair by the classes rule, with no upper edge), as "
    "FR-4's J6_energy_falls does, where it had been reported only. Why: the declared rung alone is "
    "about four times looser than F4, since the residual falls at second order, which is what Q1 "
    "ruled out; the choice adds and tightens, and loosens nothing. It was made after FR-5's "
    "development dt study (dt5-a6639e79, 16 November 2026), whose values were known when the line "
    "was settled: the residual over flows 1.32e-10 (T) and 8.21e-11 (R) at 1 ms, 3.30e-11 and "
    "2.09e-11 at 0.5 ms, the ladder passing on both arms (T mixed, then at rounding; R at rounding "
    "on every pair). That study's records, read again by the judge under these criteria, pass "
    "both arms (/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/rehearsal-20261117/"
    "dt5-a6639e79-reread/)"
)
TEXT_LEVELLED = (
    "pre-registration correction, 17 November 2026, the lead's ruling on the stale text (text "
    "only: no criterion, derivation or threshold changed, checked byte for byte when redrafted): "
    "the status prose, the registration plan ('not yet wired', its path and its launch), the "
    "development runs (now listed), engine_models (the landed IDs), the scope line (the verdict "
    "covers cells.operator.cell_owned_compartments@1 as built at the judged snapshot: refusal 4 version 1.2, "
    "refusal 5 version 1.1), and judge.units and judge.resources (the cost basis is the lead's "
    "sizing of 1.5 ms per step plus 90 s, with the rehearsal's measured walls and peaks beside "
    "each unit, and each runtime limit D150's rule on the larger of the sizing and the "
    "rehearsal's wall) were brought level with the runs"
)
HARNESS_LIMITS = (
    "pre-registration correction, 17 November 2026, the lead's ruling on harness limits (text "
    "only: no criterion, derivation or threshold changed, checked byte for byte when redrafted): "
    f"{HARNESS_RULE}. It is the protocol's leaf harness_limits, and judge.resources.attempts "
    "follows it, in place of rerunning the failed part alone; it is fixed before any judged run, "
    "so a first timeout needs no ruling after the fact"
)
TEXT_LEVELLED_FR4 = (f"{TEXT_LEVELLED}; and the timing rule's measured rate and the "
                     "references' tier-1 note")
CORRECTIONS = {  # Dated pre-run corrections beyond the questions' rulings.
    "fr4": [
        CHARGE_CHECK,
        J4_NODES_FR4,
        EXECUTION_PATH,
        COST_FR4,
        J3_START_NODES,
        MODULE_PATHS,
        DECLARED_WORLD_FR4,
        "pre-run correction, 15 November 2026, the lead's rulings on refusal semantics and K2: "
        "B4's envelope check refuses the step at the first stage beyond the budget, so J5 judges "
        "zero envelope refusals in a completed part and the engine's reported running maximum of "
        "the lag estimate (proton_buffer_max_lag_pH, gap 7) within 1e-3 pH at every buffered "
        "node; K3 is caught when the engine refuses its world at the definition through the "
        "envelope (its reason the envelope's: the same world is admitted with B4's stage check "
        "removed), and leaves J1; K2 is a self-consistent reversed pump (moves, energetics and "
        "ledger terms reversed), which every ledger closes, so only J4 against the independent "
        "reference can catch it (max over records |pH - pH_ref| >= 2e-3, as ruled), the "
        "reference recording that its effect exceeds the budget (D176's G3); the moves flipped "
        "alone stay a unit guard in the tests. Verdicts are unchanged in kind: a refusal is a "
        "verdict",
        TEXT_LEVELLED_FR4,
        HARNESS_LIMITS,
    ],
    "fr5": [
        CHARGE_CHECK,
        J4_NODES_FR5,
        EXECUTION_PATH,
        COST_FR5,
        J3_START_NODES,
        MODULE_PATHS,
        DECLARED_WORLD_FR5,
        "pre-run correction, 15 November 2026, the lead's ruling on refusal semantics: B4's "
        "envelope check refuses the step at the first stage beyond the budget, so J5 judges zero "
        "envelope refusals in a completed part and the engine's reported running maximum of the "
        "lag estimate (gap 7) within 1e-3 pH at every buffered node",
        ENERGY_SETTLED,
        TEXT_LEVELLED,
        HARNESS_LIMITS,
    ],
}


def draft(which, path=None):
    """Write the judge section into the PROPOSED protocol in place (idempotent)."""
    path = Path(path or generator.PROTOCOLS[which])
    protocol = json.loads(path.read_text())
    if not str(protocol.get("status")).startswith("PROPOSED"):
        raise SystemExit("Refused: only a PROPOSED protocol is drafted")
    out = {}
    for key, value in protocol.items():
        if key == "registration":
            if value.get("status") != "not registered":
                raise SystemExit("Refused: the protocol carries a registration record")
            out["registration_plan"] = value
            continue
        if key == "judged_parts" and "judged_groups" not in protocol and which == "fr4":
            out["judged_groups"] = value
        out[key] = value
    out["judged_parts"] = list(generator.PARTS[which])
    out["driver"] = ("validation/tissue/compartment_ph_qualification.py (the generator) and "
                     "validation/tissue/compartment_ph_judge.py (the judge), on "
                     "validation/compartment_ph_engine/definitions.py's worlds")
    out["judge"] = judge_section(which)
    if DISCLOSURE not in out["disclosures"]:
        out["disclosures"] = [*out["disclosures"], DISCLOSURE]
    for correction in CORRECTIONS[which]:
        if correction not in out["disclosures"]:
            out["disclosures"] = [*out["disclosures"], correction]
    for path_, text in PROSE[which].items():
        leaf = out
        for key in path_[:-1]:
            leaf = leaf[key]
        leaf[path_[-1]] = text
    answered = list(out.get("questions_answered", []))
    for asked_, ruling in zip(ASKED[which], RULINGS[which], strict=True):
        entry = f"{asked_} RULED ({RULED} this question): {ruling}"
        if entry not in answered:
            answered.append(entry)
        disclosure = f"{RULED} {which.upper()}'s {ruling}"
        if disclosure not in out["disclosures"]:
            out["disclosures"] = [*out["disclosures"], disclosure]
    out["questions_answered"] = answered
    out["questions_for_the_lead"] = []
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out


def register(protocol_path, record_path):
    """The lead's registration (MG0c's form): the PROPOSED protocol takes the record's status and,
    after it, the record itself (the lead's, never pre-filled here); every other leaf stays as
    drafted. Refused for a protocol already registered or recorded, or a record whose status does
    not begin 'registered'."""
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
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out


def main(argv):
    if len(argv) == 2 and argv[0] == "draft" and argv[1] in ("fr4", "fr5", "all"):
        for which in ("fr4", "fr5") if argv[1] == "all" else (argv[1],):
            protocol = draft(which)
            judged = [c["id"] for c in protocol["judge"]["criteria"] if c["judged"]]
            print(generator.PROTOCOLS[which], len(judged), "judged criteria")
        return 0
    if len(argv) == 3 and argv[0] == "register":
        register(argv[1], argv[2])
        print(argv[1])
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
