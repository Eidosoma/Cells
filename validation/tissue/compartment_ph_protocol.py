"""FR-4's and FR-5's qualification protocols: their machine criteria, units and registration path.

The protocols (validation/compartment_ph/protocols/fr4_acidification_v1.json and
fr5_transfer_v1.json) are PROPOSED, hand-drafted by the FR-4/FR-5 physics owner with prose
criteria (J1-J7 and J1-J11). This module writes, a priori and before any run of either world, what
the judge needs beside the prose (`judge`):
* `derivation`: the parts each metric reads and the arithmetic's parameters (the judge's docstring
  fixes the arithmetic itself);
* `criteria`: the machine criteria, each a metric path, a comparison and a threshold taken from
  the prose (MG0c's evaluator form; `judged: false` marks a reported item);
* `units` and `resources`: one part per unit, the upper-bound costs (3.6 ms per step, the
  charged-patch test's runner path), and the launch command as a template until the rehearsal
  measures each unit (D150's rule: 3 x its wall time plus 10 minutes).
`draft` writes that section into a PROPOSED protocol in place, sets `judged_parts` to the
generator's parts, and moves the hand-drafted registration plan to `registration_plan`, so that
`register` can add the lead's record under `registration` (MG0c's form). Rerunning it changes
nothing. Only the lead registers.

Usage:
  python -m validation.tissue.compartment_ph_protocol draft fr4|fr5|all
  python -m validation.tissue.compartment_ph_protocol register PROTOCOL_JSON RECORD_JSON
"""

import json
import sys
from pathlib import Path

from validation.compartment_ph import dt_study
from validation.tissue import compartment_ph_qualification as generator
from validation.tissue import compartment_ph_reference_stage as stage

BAND = [1.8, 2.2]  # J2: the observed orders
PH_BUDGET = 1e-3  # J3/J4: pH units
START_TOLERANCE = 1e-11  # row 0 against the reference: rounding (the reference stage's)
START_X_OVER_BUDGET = 1e-9  # X_L's row 0 in budgets: the same products, so rounding
COST_S_PER_STEP = 3.6e-3  # the upper bound of the runbook (the charged-patch test's runner path)
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
        reference_observables=["pH_L", "V_b", "K_L", "cycles"], cytosol_pH=7.2,
        arithmetic=ARITHMETIC)


def criteria_fr4():
    d = "derived"
    out = [criterion("J1_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                     "every rung, control and the reference admitted and run to its end")]
    out += [criterion(f"J2_order_{x}", [f"{d}.orders.{x}.order_finest"], "within", BAND,
                      f"the observed order of {x} on the three finest rungs (1, 0.5, 0.25 ms) "
                      "lies in [1.8, 2.2]; an unresolved difference gives None, which fails")
            for x in ("pH_L", "V_b", "K_L", "cycles")]
    out += [
        criterion("J3_state_error_pH_L", [f"{d}.state_error.pH_L"], "le", PH_BUDGET,
                  "at 1 ms the Richardson-estimated error of the lumen's pH (4/3 D(1, 0.5 ms))"),
        criterion("J3_state_error_V_b", [f"{d}.state_error.V_b_over_range"], "le", 1e-3,
                  "at 1 ms the Richardson-estimated error of V_b over its range at 1 ms"),
        criterion("J4_reference_pH_L", [f"{d}.reference.pH_L_max_abs"], "le", PH_BUDGET,
                  "|pH_engine - pH_reference| at every record at 1 ms (R-closure on the declared "
                  "world)"),
        criterion("J4_start", [f"{d}.reference.start_pH_L", f"{d}.reference.start_V_b"], "le",
                  START_TOLERANCE, "row 0 is the reference's start at rounding (both from the "
                  "declared pH 7.2 state)"),
        criterion("J4_reported", [f"{d}.reference.{x}_max_abs" for x in ("V_b", "K_L", "cycles")]
                  + [f"{d}.reference.floor_pH_L"], "ge", 0,
                  "reported beside J4: V_b, lumen K and the pump's cycles against the reference; "
                  "the reference's floor (rtol 1e-11 against 1e-12)", judged=False),
        criterion("J5_envelope_lag", [f"{d}.envelope.max_lag_ph"], "le", PH_BUDGET,
                  "the closure's state-dependent lag estimate at every stage of every buffered "
                  "node, on every rung"),
        criterion("J5_envelope_count", [f"{d}.envelope.stages_beyond"], "le", 0,
                  "no stage beyond the budget (counted and reported; any failure fails)"),
        criterion("J6_material", [f"{d}.ledgers.material_over_tolerance"], "le", 1,
                  "material per species within its declared floor, by the engine's own check, at "
                  "every record of every rung"),
        criterion("J6_charge", [f"{d}.ledgers.charge_over_tolerance"], "le", 1,
                  "charge within the capacitor tolerance on every rung"),
        criterion("J6_energy", [f"{d}.ledgers.energy_over_flows_at_declared"], "le", 2e-3,
                  "the energy residual over the integrated flows at every record at 1 ms"),
        criterion("J6_energy_falls", [f"{d}.ledgers.energy.smallest_order"], "ge", BAND[0],
                  "the energy residual falls at second order down the ladder: its smallest "
                  "resolved order at least the band's lower edge (the protocol gives no band; put "
                  "to the lead)"),
        criterion("J6_bands", [f"{d}.bands.cytosol_pH_max_deviation"], "le", 0.05,
                  "the cytosol's pH within 7.2 +- 0.05 at every stage of every rung"),
        criterion("J7_K1_control_stalls", [f"{d}.controls.k1.control_drop_ph"], "le", 0.1,
                  "K1: with P_K = 0 the lumen's pH falls by less than 0.1 in 900 s"),
        criterion("J7_K1_route_drops", [f"{d}.controls.k1.declared_drop_ph"], "ge", 1.0,
                  "K1: with the route it falls by more than 1 unit"),
        criterion("J7_K1_reference", [f"{d}.controls.k1.reference_control_drop_ph"], "ge", 0,
                  "K1's reference side, reported", judged=False),
        criterion("J7_K2_planted_sign", [f"{d}.controls.k2.pH_L_max_abs_vs_reference"], "ge",
                  2 * PH_BUDGET, "K2: the pump's moves flipped fail J4 by more than its budget "
                  "(read as |pH - pH_reference| >= 2 x 1e-3; put to the lead)"),
        criterion("J7_K3_envelope_flags", [f"{d}.controls.k3.engine_stages_beyond"], "ge", 1,
                  "K3: with the lumen's k_on at 1e-3 /mM/s on the closure's declaration, the "
                  "engine's envelope check flags stages at run time"),
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
            + (["cargo_pore_0"] if pore else []))
    return dict(arms=arms, order_observables=["X_L", "pH_L", "V_b", "d"],
                x_budget_fraction=dt_study.ARM_T.x_budget_fraction, cytosol_pH=7.2,
                proton_transfers=["moved_H_pump", "moved_H_leak", "moved_H_pore"],
                arithmetic=ARITHMETIC)


def criteria_fr5():
    out = []
    for arm in ("T", "R"):
        d = f"derived.{arm}"
        out += [criterion(f"J1_{arm}_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                          f"arm {arm}: every rung, its control, the start and the reference "
                          "admitted and run to their ends")]
        out += [criterion(f"J2_{arm}_order_{x}", [f"{d}.orders.{x}.order_finest"], "within",
                          BAND, f"arm {arm}: the observed order of {x} on the three finest rungs "
                          "(0.5, 0.25, 0.125 ms) in [1.8, 2.2]")
                for x in ("X_L", "pH_L", "V_b", "d")]
        out += [
            criterion(f"J3_{arm}_X_L", [f"{d}.state_error.X_L_over_budget"], "le", 1,
                      "at the declared 0.5 ms the Richardson-estimated error of the lumen's X, in "
                      "X's budget B = 1e-3 X_L(0)"),
            criterion(f"J3_{arm}_pH_L", [f"{d}.state_error.pH_L"], "le", PH_BUDGET,
                      "at 0.5 ms the Richardson-estimated error of the lumen's pH"),
            criterion(f"J4_{arm}_X_L", [f"{d}.reference.X_L_over_budget"], "le", 1,
                      "|X_L,engine - X_L,reference| <= B at every record (the reference from "
                      "tr.Start)"),
            criterion(f"J4_{arm}_transfer", [f"{d}.reference.transfer_over_budget"], "le", 1,
                      "the conditioned route's cumulative transfer within B at every record"),
            criterion(f"J4_{arm}_pH_L", [f"{d}.reference.pH_L_max_abs"], "le", PH_BUDGET,
                      "|pH_L,engine - pH_L,reference| <= 1e-3 at every record"),
            criterion(f"J4_{arm}_start", [f"{d}.start.pH_L", f"{d}.start.V_b"], "le",
                      START_TOLERANCE, "every rung's and the control's row 0 is the reference's "
                      "start at rounding (one extract for both)"),
            criterion(f"J4_{arm}_start_X_L", [f"{d}.start.X_L_over_budget"], "le",
                      START_X_OVER_BUDGET, "X_L's row 0 is the reference's (the same products)"),
            criterion(f"J4_{arm}_reported", [f"{d}.reference.floor_X_L_over_budget",
                                             f"{d}.reference.floor_pH_L"], "ge", 0,
                      "the reference's floor, reported", judged=False),
            criterion(f"J5_{arm}_envelope_lag", [f"{d}.envelope.max_lag_ph"], "le", PH_BUDGET,
                      "the closure's envelope at every stage of every buffered node, through the "
                      "damage window, on every rung and the control"),
            criterion(f"J5_{arm}_envelope_count", [f"{d}.envelope.stages_beyond"], "le", 0,
                      "no stage beyond the budget"),
            criterion(f"J6_{arm}_protons", [f"{d}.protons.max_over_tolerance"], "le", 1,
                      "H_eq at each node changes only by its routes' proton transfers (pump, leak, "
                      "proton pore), to the engine's H tolerance, at every record (0.5 ms)"),
            criterion(f"J7_{arm}_energy", [f"{d}.energy.over_flows_at_declared"], "le", 2e-3,
                      "the energy identity at every record within FR-4's ledger tolerance"),
            criterion(f"J7_{arm}_route_heat", [f"{d}.energy.smallest_route_heat_increment_pJ"],
                      "ge", -1e-12, "each passive route's cumulative heat never falls between "
                      "records (the booking probe's -1e-12 pJ rounding allowance)"),
            criterion(f"J7_{arm}_energy_ladder", [f"{d}.energy.ladder.smallest_order"], "ge", 0,
                      "the energy residual down the ladder, reported", judged=False),
            criterion(f"J8_{arm}_cargo", [f"{d}.cargo.material_over_tolerance",
                                          f"{d}.cargo.lumen_over_tolerance",
                                          f"{d}.cargo.cytosol_over_tolerance"], "le", 1,
                      "X conserved to its tolerance; what leaves the lumen arrives in the cytosol "
                      "on the same routes"),
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


def units(which):
    out = {}
    for part in generator.PARTS[which]:
        if part == "reference":
            out[part] = dict(steps=None, cpu_hours_upper=None, note="the references: minutes")
            continue
        if which == "fr4":
            dt = generator.FR4_RUNGS.get(part, generator.FR4_DECLARED_DT)
            steps = round(900.0 / dt)
        elif part == "start":
            steps = round(stage.START_TIME_S / generator.FR4_DECLARED_DT)
        else:
            dt = generator.FR5_RUNGS.get(part, (None, dt_study.FR5_DECLARED_DT_S))[1]
            steps = round(400.0 / dt)
        out[part] = dict(steps=steps, cpu_hours_upper=round(steps * COST_S_PER_STEP / 3600, 2))
    return out


def resources(which):
    name = FILES[which]
    entry = (f"{PYTHON} -B -m validation.tissue.compartment_ph_qualification judged "
             f"SNAPSHOT/validation/compartment_ph/protocols/{name} OUT/PART PART")
    out = dict(
        status="a template until the rehearsal measures each unit: CPU, RUNTIME_MAX_S and the "
               "caps are placeholders, filled by the lead at the final check",
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
        runtime_max_rule="3 x the rehearsal's wall time of the unit plus 600 s, rounded up to the "
                         "minute (D150's rule)",
        caps="2G per unit (the runbook) until the rehearsal measures the peaks",
        no_wait_headroom="judged units run without --wait-headroom: the wait would run inside "
                         "the unit and count against its runtime limit; the lead checks the "
                         "slice's room before each launch",
        attempts="an infrastructure ending (a runtime or memory kill, a signal, an incomplete "
                 "results.json) is rerun once from the same snapshot into a new OUT/PART; a "
                 "refusal by the engine is a verdict",
        enforced_by="the launcher alone (run_detached.sh's MemoryMax, CPUAffinity and "
                    "RuntimeMaxSec): no code reads these fields",
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


QUESTIONS = {
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
        "3. J2 lists the damage d, whose step is exact (bounding_patch_damage@1 on piecewise-"
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
DISCLOSURE = (
    "The machine criteria (judge.criteria), the judge's arithmetic (judge.derivation and "
    "validation/tissue/compartment_ph_judge.py's docstring) and the units were written on 15 "
    "November 2026 from this protocol's prose criteria, rules and controls, before any run of this "
    "world (no engine run exists). The registration plan moved from 'registration' to "
    "'registration_plan' so that the registration path adds the lead's record under "
    "'registration' (MG0c's form), and judged_parts names the generator's parts")


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
                     "validation/compartment_ph/definitions.py's worlds")
    out["judge"] = judge_section(which)
    if DISCLOSURE not in out["disclosures"]:
        out["disclosures"] = [*out["disclosures"], DISCLOSURE]
    out["questions_for_the_lead"] = QUESTIONS[which]
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
