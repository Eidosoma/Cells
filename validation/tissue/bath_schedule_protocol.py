"""fr10-dose-schedule-v1's drafter: its machine criteria, derivation, units, and registration path.

The protocol (validation/tissue/bath_schedule_protocol.json) is PROPOSED and hand-drafted, with
prose criteria J1-J12, budgets, controls K1-K6 and refusal classes R1-R13. This module writes what
the judge needs beside the prose (`judge`): the derivation's parts and parameters (the judge's
docstring fixes the arithmetic), the machine criteria in MG0c's evaluator form (a metric path, a
comparison and a threshold, `judged: false` for a reported item), the units, and the launch
template. `draft` writes that section and `judged_parts` into the PROPOSED protocol in place and
changes nothing else, so no hand-drafted leaf (its status above all) is pinned here; rerunning it
changes nothing. `register` is the lead's.

Usage:
  python -m validation.tissue.bath_schedule_protocol draft
  python -m validation.tissue.bath_schedule_protocol register PROTOCOL_JSON RECORD_JSON
"""

import json
import math
import sys
from pathlib import Path

from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import bath_schedule_qualification as generator

PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"
BAND = [1.8, 2.2]  # J2: the observed orders (the classes rule's band)
ENERGY_RELATIVE = 2e-3  # J5: the energy residual over the integrated flows (ARS's ledger)
CONTROLS_MARGIN = 10.0  # K1-K3: at least 10 x the arm's budget or bound
ROW0 = 1e-6  # J4: row 0 against the reference, in budgets (the same start: rounding)
FREE_ENERGY_RELATIVE = 1e-12  # J6: delta_G_b against R-records
BUDGET_FRACTION = 1e-3  # B1, B2: 1e-3 of the step
WRITTEN = ("17 November 2026, by the FR owner, after the protocol's worlds and refusal classes "
           "were fixed and before any run of the protocol (development runs of the generator's "
           "parts on quick horizons, to test the tools, had run)")
REFUSAL_CHECKS = {
    "R1_past_a_neutral_corner": "the step rule (region)",
    "R2_a_measured_failure": "the step rule (region)",
    "R3_a_dose_from_nothing": "the step rule (region)",
    "R4_past_the_down_corner": "the step rule (region)",
    "R5_past_the_K_corner": "the step rule (region)",
    "R6_an_unmeasured_ion_direction": "the step rule (region)",
    "R7_a_faster_face": "the step rule (face)",
    "R8_outside_the_measured_steps": "the step rule (solver and dt)",
    # R9_the_species_cap is retired (the lead's ruling, 23 November 2026; the protocol's
    # disclosures): FR-43 (D315) raised the cap from 16 to 1,024, so its 17-species world is
    # admitted.
    "R10_a_charged_unit": "the neutrality rule (integer charge)",
    "R11_an_anisosmotic_step": "the isosmotic rule",
    "R12_beyond_the_explicit_bound": "@3's explicit-rate bound",
    "R13_not_a_held_bath": "the held-bath rule",
}
LEDGERS = ["local", "outside", "total", "charge", "electrode", "global_charge", "energy",
           "reservoir_work", "electrode_work", "metabolic_work", "bath_dose",
           "bath_dose_free_energy", "bath_neutrality"]


def budget_b1():
    """1e-3 of the step's amount at a 1 pL node: V |delta c_b| over W1's largest step."""
    levels = bfx.CHAIN_LEVELS_mM
    step = max(abs(b - a) for a, b in zip(levels, levels[1:], strict=False))
    return BUDGET_FRACTION * 1.0 * step


def budget_b2():
    """1e-3 of the voltage step |E_K(after) - E_K(before)| = (RT/F) ln(K after / K before), at
    310 K with the SI constants."""
    charge, boltzmann = 1.602176634e-19, 1.380649e-23  # e and k_B (SI, exact): RT/F = k_B T/e
    rt_over_f = boltzmann * 310.0 / charge
    k0 = 5.0
    return BUDGET_FRACTION * rt_over_f * math.log((k0 + bfx.ION_STEP_mM) / k0)


def budget_k():
    """The cytosol K's budget: B2 carried through the owner's capacitor, C B2 / F (fmol). The cell's
    charge moves with its K alone (K is W2's only permeant species), so an error dV in V_m is an
    error C dV / F in its K: 1e-3 of the change to the new equilibrium, C |delta E_K| / F."""
    wall = next(m for m in bfx.ion_world()["model"]["membranes"] if m["id"] == "wall_cell_0")
    faraday = 6.02214076e23 * 1.602176634e-19  # N_A e (SI, exact)
    return wall["capacitance_F"] * budget_b2() / faraday * 1e15


def derivation():
    w1, w2 = list(generator.W1_RUNGS), list(generator.W2_RUNGS)
    run_parts = [*w1, "W1_control", *w2, "W2_control", "W3_rk4", "W4_idle", "W5_restart",
                 "W5_batch", "W6_water", "W7_staircase_ars", "W7_staircase_rk4", "refusals"]
    return dict(
        run_parts=run_parts,
        band=BAND,
        energy_order_low=BAND[0],
        W1=dict(ladder_parts=w1, declared_part=w1[0], half_part=w1[1], control_part="W1_control",
                observables=["amount_S_ecs_0", "amount_S_ecs_1"], budget_fmol=budget_b1()),
        W2=dict(ladder_parts=w2, declared_part=w2[0], half_part=w2[1], control_part="W2_control",
                observables=["V_wall_cell_0", "amount_K_cell_0"], v_observable="V_wall_cell_0",
                k_observable="amount_K_cell_0", budget_V=budget_b2(),
                k_budget_fmol=budget_k()),
        W3=dict(part="W3_rk4", event_s=20 * bfx.RK4_DT, ledgers=LEDGERS),
        record_ledgers=["bath_dose", "bath_dose_free_energy", "bath_neutrality"],
        charge_ledgers=["charge", "electrode", "global_charge"],
        records=dict(
            W1=dict(part=w1[0], event_s=list(bfx.CHAIN_EVENTS_S), species=["S"]),
            W2=dict(part=w2[0], event_s=[bfx.ION_EVENT_S], species=["Na", "K", "Cl"]),
            W3=dict(part="W3_rk4", event_s=[20 * bfx.RK4_DT], species=["S"])),
        restart_times_s=list(generator.RESTART_TIMES_S),
        batch_worlds=len(bfx.BATCH_LEVELS_mM),
        refusal_checks=REFUSAL_CHECKS,
        compensation_parts=[*w1, "W1_control", *w2, "W2_control", "W3_rk4", "W6_water",
                            "W7_staircase_ars", "W7_staircase_rk4"],
        W6_part="W6_water",
        W7_parts=["W7_staircase_ars", "W7_staircase_rk4"],
        record_unit_s=0.01,
    )


def criterion(id_, metrics, comparison, threshold, basis, judged=True):
    return dict(id=id_, metrics=list(metrics), comparison=comparison, threshold=threshold,
                basis=basis, judged=judged)


def criteria():
    d, segs = "derived", ("before", "at", "after")
    out = [criterion("J1_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                     "every run part admitted and run to its end with every host check on every "
                     "row (the runner)")]
    for world, observables in (("W1", derivation()["W1"]["observables"]),
                               ("W2", derivation()["W2"]["observables"])):
        out += [criterion(f"J2_order_{world}_{x}", [f"{d}.orders.{world}_{x}.passes"], "ge", 1,
                          f"{world}'s {x} on the three finest rungs by FR-4's classes rule")
                for x in observables]
    out += [
        criterion("J3_state_error", [f"{d}.state_error.max"], "le", 1,
                  "at the declared 1 ms, the Richardson-estimated error of every judged "
                  "observable within its budget (B1; B2 for V_m; C B2 / F for the cytosol K)"),
        criterion("J4_reference", [f"{d}.reference.max"], "le", 1,
                  "W1 against R-faces and W2 against R-ion within their budgets at every record "
                  "at the declared 1 ms"),
        criterion("J4_row0", [f"{d}.reference.row0_max"], "le", ROW0,
                  "row 0 against the reference at rounding, in budgets"),
        criterion("J4_reported", [f"{d}.reference.W1_amount_S_ecs_0_floor",
                                  f"{d}.reference.W2_V_wall_cell_0_floor"], "ge", 0,
                  "each reference's floor, in budgets", judged=False),
        criterion("J5_W3_energy", [f"{d}.W3.energy.{s}" for s in segs], "le", 1,
                  "W3 under RK4: the energy ledger within its absolute bound before, at and "
                  "after the event"),
        criterion("J5_W3_reservoir_work", [f"{d}.W3.reservoir_work.{s}" for s in segs], "le", 1,
                  "W3: the reservoir-work ledger, with the operator's term, within its bound "
                  "before, at and after the event"),
        criterion("J5_energy", [f"{d}.energy.W1.over_flows_at_declared",
                                f"{d}.energy.W2.over_flows_at_declared"], "le", ENERGY_RELATIVE,
                  "W1 and W2 under ARS: the energy residual over the integrated flows <= 2e-3 at "
                  "the declared 1 ms, which is the coarsest rung, at every record"),
        criterion("J5_energy_falls", [f"{d}.energy.W1.ladder.passes",
                                      f"{d}.energy.W2.ladder.passes"], "ge", 1,
                  "the energy residual falls at second order down the ladder (the classes, no "
                  "upper edge)"),
        criterion("J6_records", [f"{d}.ledger_max.records"], "le", 1,
                  "the operator's own ledgers (the dose against the held content, the "
                  "free-energy record against its endpoints, neutrality) within their bounds at "
                  "every record of every run part"),
        criterion("J5_K_reference", [f"{d}.K_reference.max_over_bound"], "le", 1,
                  "W3: the operator's reconciliation term K equal to R-records' K from W3's "
                  "supply series within the reservoir-work ledger's bound at every record"),
        criterion("J6_compensation", [f"{d}.compensation.max"], "le", 1,
                  "the compensation-charge record at rounding of zero at every record of every "
                  "engine part: within (n + 2) eps F times the dose's charge magnitude so far"),
        criterion("J6_records_reference", [f"{d}.records.dose_over_rounding_max"], "le", 1,
                  "each event's dose equal to R-records' at rounding (N eps |dose|)"),
        criterion("J6_free_energy_reference", [f"{d}.records.free_energy_relative_max"], "le",
                  FREE_ENERGY_RELATIVE, "each event's delta_G_b within 1e-12 relative of "
                  "R-records"),
        criterion("J6_charge", [f"{d}.ledger_max.charge"], "le", 1,
                  "the charge, electrode and global-charge ledgers within their bounds at every "
                  "record of every run part"),
        criterion("J7_idle", [f"{d}.idle"], "ge", 1,
                  "W4: the operator with no event bitwise the composition without it"),
        criterion("J8_restart", [f"{d}.restart"], "ge", 1,
                  "W5: every restart bitwise the straight run from its restart time"),
        criterion("J8_batch", [f"{d}.batch"], "ge", 1,
                  "W5: every batched world bitwise its batch of one"),
        criterion("J9_refusals", [f"{d}.refusals.all"], "ge", 1,
                  "every refusal class's representative refused by its own check, and its "
                  "neighbour admitted and run; R12's declared composition alone admitted"),
        criterion("J9_reported", [f"{d}.refusals.{c}" for c in REFUSAL_CHECKS], "ge", 1,
                  "each refusal class, reported", judged=False),
        criterion("J10_staircase", [f"{d}.staircase"], "ge", 1,
                  "W7: the six-stair dose from the trace run under both solvers"),
        criterion("J11_water", [f"{d}.water"], "ge", 1, "W6: the isosmotic step run"),
        criterion("J11_water_ledgers", [f"{d}.ledger_max.water"], "le", 1,
                  "W6: every ledger, water's included, within its bound at every record"),
        criterion("J12_K1", [f"{d}.controls.K1_over_budget"], "ge", CONTROLS_MARGIN,
                  "W1 without its events against R-faces: at least 10 x B1"),
        criterion("J12_K2", [f"{d}.controls.K2_over_budget"], "ge", CONTROLS_MARGIN,
                  "W2 without its event against R-ion: at least 10 x B2"),
        criterion("J12_K3_before", [f"{d}.controls.K3_before"], "le", 1,
                  "W3's reservoir-work ledger without the operator's term within its bound "
                  "before the event"),
        criterion("J12_K3_after", [f"{d}.controls.K3_after_min"], "ge", CONTROLS_MARGIN,
                  "and at least 10 x its bound at every record after it"),
        criterion("J12_K4", [f"{d}.controls.K4_planted_differs"], "ge", 1,
                  "W4's pair with one ulp planted is not bitwise equal"),
        criterion("J12_K5", [f"{d}.controls.K5_moved_event_differs"], "ge", 1,
                  "W5's restart with the event moved one step is not bitwise the straight run"),
    ]
    return out


def units():
    out = {}
    for part in generator.PARTS:
        dt = generator.W1_RUNGS.get(part) or generator.W2_RUNGS.get(part)
        horizon = (bfx.CHAIN_END_S if part.startswith("W1") else
                   bfx.ION_END_S if part.startswith("W2") else None)
        out[part] = dict(steps=None if dt is None else round(horizon / dt),
                         note="sized at the rehearsal")
    return out


def resources():
    entry = (f"{PYTHON} -B -m validation.tissue.bath_schedule_qualification judged "
             "SNAPSHOT/validation/tissue/bath_schedule_protocol.json OUT/PART PART")
    return dict(
        status="a template until the rehearsal measures each unit",
        environment="from the snapshot's root, PYTHONPATH=SNAPSHOT/src:SNAPSHOT, "
                    "JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu, CUDA_VISIBLE_DEVICES= (empty), "
                    "PYTHONDONTWRITEBYTECODE=1, CPU backend only, float64",
        unit=("scripts/run_detached.sh fr10-PART CAP --cpus CPU --oom-first --runtime-max "
              "RUNTIME_MAX_S --dir SNAPSHOT --env PYTHONPATH=SNAPSHOT/src:SNAPSHOT --env "
              "JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu --env CUDA_VISIBLE_DEVICES= --env "
              f"PYTHONDONTWRITEBYTECODE=1 -- {entry}"),
        references_unit="the references part adds --w3 OUT/W3_rk4/results.json and runs after "
                        "W3_rk4's unit has ended (R-records' K reads W3's own supply)",
        judge=(f"{PYTHON} -B -m validation.tissue.bath_schedule_judge judged "
               "SNAPSHOT/validation/tissue/bath_schedule_protocol.json OUT/verdict "
               "OUT/*/results.json (in its own unit: 1G, 600 s; it runs nothing)"),
        runtime_max_rule="D150's rule on the larger of a sizing rate and the rehearsal's wall "
                         "(3 x estimate + 600 s, rounded up to the minute)",
        attempts="harness_limits",
    )


def judge_section():
    return dict(
        written=WRITTEN,
        generator="validation/tissue/bath_schedule_qualification.py (records only)",
        judge="validation/tissue/bath_schedule_judge.py (reads records, never runs; FR-4's and "
              "FR-5's arithmetic imported read-only from validation/tissue/"
              "compartment_ph_judge.py)",
        references="the FR references agent's R-faces, R-ion and R-records "
                   "(validation/fr10/references, branch fr10-references at 23b8ff58: its "
                   "registered design README.md and designs/), used through its usage note's API "
                   "only (REFERENCES_USAGE.md), from Appendix A and the registered inputs "
                   "validation/bath_schedule/reference_inputs.json",
        derivation=derivation(),
        criteria=criteria(),
        units=units(),
        resources=resources(),
    )


def draft(path=None):
    """Write the judge section and judged_parts into the PROPOSED protocol in place; nothing else
    changes, and rerunning it changes nothing. Refused for a protocol that is not PROPOSED or that
    carries a registration record."""
    path = Path(path or generator.PROTOCOL)
    protocol = json.loads(path.read_text())
    if not str(protocol.get("status")).startswith("PROPOSED") or "registration" in protocol:
        raise SystemExit("Refused: only a PROPOSED protocol without a registration record is "
                         "drafted")
    out = dict(protocol)
    out["judged_parts"] = list(generator.PARTS)
    out["judge"] = judge_section()
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out


def register(protocol_path, record_path):
    """The lead's registration (MG0c's form): the PROPOSED protocol takes the record's status and,
    after it, the record itself; every other leaf stays as drafted."""
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
    if argv == ["draft"]:
        protocol = draft()
        print(generator.PROTOCOL, sum(c["judged"] for c in protocol["judge"]["criteria"]),
              "judged criteria")
        return 0
    if len(argv) == 3 and argv[0] == "register":
        register(argv[1], argv[2])
        print(argv[1])
        return 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
