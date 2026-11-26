"""fr3-site-occupancy-v1's drafter: its machine criteria, derivation, units, and registration path.

The protocol (validation/tissue/site_occupancy_acceptance_protocol.json) is PROPOSED and
hand-drafted, with its prose criteria Q1 to Q6, budgets, controls and the lead's rulings. This
module writes what the judge needs beside the prose (`judge`): the derivation's parts and
parameters (the judge's docstring fixes the arithmetic), the machine criteria in MG0c's evaluator
form (a metric path, a comparison and a threshold, `judged: false` for a reported item), the units
and the launch template. `draft` writes that section and `judged_parts` into the PROPOSED protocol
in place and changes nothing else, so no hand-drafted leaf (its status above all) is pinned here;
rerunning it changes nothing. `register` is the lead's.

Usage:
  python -m validation.tissue.site_occupancy_acceptance_protocol draft
  python -m validation.tissue.site_occupancy_acceptance_protocol register PROTOCOL_JSON RECORD_JSON
"""

import json
import sys
from pathlib import Path

from validation.tissue import site_occupancy_acceptance_fixtures as af
from validation.tissue import site_occupancy_acceptance_qualification as generator

PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"
F_STATE = 2e-5  # B_state = F_STATE x S_world (the lead's ruling 1).
F_ENERGY = 1e-3  # B_energy = F_ENERGY x the largest reference |heat| or |work| (ruling 1).
CLOSURE_ROUNDING = 2.5  # The guard of record: 2.5 eps x steps x the energy magnitude (§3.4).
BAND = [2.8, 3.2]  # The orders: §8.3's third order, +/- 0.2.
BAND_REPORTED = [1.8, 2.2]  # The heat's and work's orders, reported (the share: second, §4.5).
M_Q4 = 1e-3  # The lead's ruling 5.
BACKGROUND_FACTOR = 0.1  # 'Far below': at least 10 x below B_state (the lead's ruling 2).
BATCH_RELATIVE = 1e-12
CONTROLS_MARGIN = 10.0
WRITTEN = ("18 November 2026, by the FR owner, after the protocol's worlds were fixed, its "
           "budgets declared and the lead's rulings recorded, and before any engine output of a "
           "protocol world")
ORDER_OBSERVABLES = ["amount_cell_0", "amount_ecs_0", "B_r0"]
ENGINE_IDS = [
    "cells.model.resolved_pump_composite@1",
    "cells.model.resolved_pump_tissue@3",
    "cells.operator.site_occupancy@1",
    "cells.site_binding.langmuir_site_binding@1",
    "cells.site_internalisation.site_conserving_internalisation@1",
    "ssprk33_unidirectional_stage_condition_site_bookings@1",
    "cells.route.constant_field@1",
    "cells.field_closure.resolved_capacitor_components_current_continuity@1",
    "cells.solver.capacitive_reduction_gauged_damped_newton@2",
    "cells.solver.imex_ars222_face_electromigration@1",
]
LEDGERS = ["local", "outside", "total", "charge", "electrode", "global_charge", "reservoir_work",
           "electrode_work", "metabolic_work", "site_bound_entity", "site_moiety_entity"]
CONTROLS = {
    "K_rates": {"k_on": "state", "k_off": "state", "k_int": "state"},
    "K_alpha": {"alpha_ignored": "state"},
    "K_binding_multiplier": {"ignored": "state", "squared": "state"},
    "K_internalisation_multiplier": {"ignored": "state"},
    "K_cell_volume": {"q5_inward": "state", "q1_eps_1e-1": "work_pJ"},
}


def items():
    worlds = list(generator.WORLD_PARTS)
    by = {f"Q{k}": [w for w in worlds if w.startswith(f"q{k}_")] for k in range(1, 6)}
    by["Q1"] += list(generator.LADDER_PARTS)
    by["Q4"].append("q1_eps_1e-1_alpha_half")  # Q1's world at alpha = 1/2 (§8.3's Q4).
    return by


def trace_independent():
    """The worlds whose energy does not depend on the trace: binding only, every facing node
    declared above the trace (the lead's ruling 1: their honest energy error reported)."""
    out = []
    for wid in af.world_ids():
        w = af.registered(wid)
        trace = w["trace_mM"]
        if all(p["internalisation"] is None and
               w["nodes"][p["owner"]["faces_node"]]["L_mM"] > trace for p in w["populations"]):
            out.append(wid)
    return out


def derivation():
    world_of = {w: w for w in generator.WORLD_PARTS}
    world_of.update({n: af.LADDER_WORLD for n in generator.LADDER_PARTS})
    q4_worlds = {regime: {"0.5": f"q4_alpha_1_2_{regime}", "0.25": f"q4_alpha_1_4_{regime}"}
                 for regime in generator.Q4_REGIMES}
    pair = ["q5_background_threshold", "q5_background_lowered"]
    return dict(
        run_parts=list(generator.PARTS),
        engine_parts=[*generator.WORLD_PARTS, *generator.LADDER_PARTS],
        control_parts=list(generator.CONTROL_PARTS),
        engine_ids=ENGINE_IDS,
        world_of=world_of,
        items=items(),
        F_state=F_STATE,
        F_energy=F_ENERGY,
        closure_rounding=CLOSURE_ROUNDING,
        band=BAND,
        band_reported=BAND_REPORTED,
        order_observables=ORDER_OBSERVABLES,
        order_reported=["heat_pJ", "work_pJ"],
        ladder_world=af.LADDER_WORLD,
        ladder_parts=list(generator.LADDER_PARTS),
        ladder_dt_s=list(af.LADDER_S),
        qss_worlds=["q1_eps_1e-1", "q1_eps_1e-2", "q1_eps_1e-3"],
        Q2=["q2_large", "q2_closed", "q2_two_populations"],
        Q2_quadratic="q2_closed",
        Q4=dict(margin=M_Q4, regimes=list(generator.Q4_REGIMES), worlds=q4_worlds),
        ledgers=LEDGERS,
        controls=CONTROLS,
        background=dict(pair=pair, factor=BACKGROUND_FACTOR,
                        S_world_fmol=af.world_sites_fmol(af.registered(pair[0]))),
        plants={k: list(v) for k, v in generator.PLANT_PARTS.items()},
        material_plants=["move", "bound"],
        energy_plants=["work", "heat_sign", "site_free_energy"],
        Q6=dict(restarts=2 * len(generator.RESTART_TIMES_S),
                batch_worlds=len(generator.BATCH_VARIANTS),
                signature={"internalisation_differs": True, "facing_differs": True,
                           "same_structure": False},
                refusal_checks=dict(generator.EXPECTED_CHECKS)),
        trace_independent=trace_independent(),
        record_unit_s=af.RECORD_UNIT_S,
    )


def criterion(id_, metrics, comparison, threshold, basis, judged=True):
    return dict(id=id_, metrics=list(metrics), comparison=comparison, threshold=threshold,
                basis=basis, judged=judged)


def criteria():
    d, der = "derived", derivation()
    out = [
        criterion("C0_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                  "every run part admitted and run to its end with every host check on every "
                  "accepted row (the runner)"),
        criterion("C0_ids", [f"{d}.ids.all"], "ge", 1,
                  "every engine run's printed IDs among the declared engine models"),
    ]
    for item in ("Q1", "Q2", "Q3", "Q4", "Q5"):
        out += [
            criterion(f"{item}_state", [f"{d}.{item}.state"], "le", 1,
                      f"{item}'s worlds: every amount within B_state (+ 10 x the reference's "
                      "floor) of R-ode at every record"),
            criterion(f"{item}_energy", [f"{d}.{item}.energy"], "le", 1,
                      f"{item}'s worlds: the heat and the work within B_energy of R-ode's "
                      "integrals at every record"),
        ]
    out += [criterion(f"Q1_order_{x}", [f"{d}.orders.{x}.passes"], "ge", 1,
                      f"q1_fast's {x} on the registered ladder: both pairs of errors against "
                      "R-ode by FR-4's classes rule in [2.8, 3.2]") for x in ORDER_OBSERVABLES]
    out += [
        criterion("Q1_order_energy_reported", [f"{d}.orders.heat_pJ.passes",
                                               f"{d}.orders.work_pJ.passes"], "ge", 1,
                  "the heat's and the work's orders on q1_fast in [1.8, 2.2] (the share, "
                  "§4.5): reported", judged=False),
        criterion("Q1_eps_reported", [f"{d}.Q1_eps_reported.orders"], "within", [0.9, 1.1],
                  "the order in eps of R-ode against R-qss, a property of the references "
                  "(the lead's ruling 8): reported", judged=False),
        criterion("Q2_equilibrium", [f"{d}.Q2_equilibrium"], "le", 1,
                  "Q2's worlds: the last record's B of each population and the free ligand at "
                  "the facing node within B_state of R-eq"),
        criterion("Q2_quadratic", [f"{d}.Q2_quadratic"], "le", 1,
                  "q2_closed's last B within B_state of the depletion quadratic's r-"),
        criterion("Q2_heat_to_equilibrium", [f"{d}.Q2_heat_to_equilibrium"], "le", 1,
                  "Q2's worlds: the total heat at the last record within 1e-3 of G(start) - "
                  "G(eq)"),
        criterion("Q3_riccati", [f"{d}.riccati"], "le", 1,
                  "wherever the references give the Riccati form, B and the free ligand within "
                  "B_state of it at every record"),
        criterion("Q4_ratio", [f"{d}.Q4_accessibility.ratio_max"], "le", 1,
                  "|B(alpha, t)/B(1, t) - alpha| <= M_Q4 at every record t > 0, both regimes, "
                  "alpha = 1/2 and 1/4"),
        criterion("Q4_K", [f"{d}.Q4_accessibility.K_min"], "ge", CONTROLS_MARGIN,
                  "the kinetic factor (K) departs by at least 10 M_Q4 in both regimes"),
        criterion("Q4_A", [f"{d}.Q4_accessibility.A_high_min"], "ge", CONTROLS_MARGIN,
                  "the affinity factor (A) departs by at least 10 M_Q4 at 100 K_d"),
        criterion("Q4_A_low_reported", [f"{d}.Q4_accessibility.A.low_0p5",
                                        f"{d}.Q4_accessibility.A.low_0p25"], "ge",
                  CONTROLS_MARGIN, "(A) at 0.01 K_d: zero power (the lead's ruling 5), reported",
                  judged=False),
        criterion("Q5_closure", [f"{d}.closure_max"], "le", 1,
                  "the guard of record: |energy residual| <= 2.5 eps x steps x the energy "
                  "magnitude at every record of every engine run"),
        criterion("Q5_heat", [f"{d}.heat_max"], "le", 1,
                  "every heat field non-negative and non-decreasing to the closure's rounding at "
                  "every record of every engine run"),
        criterion("Q5_ledgers", [f"{d}.ledgers"], "le", 1,
                  "every material, charge and own ledger within the engine's bound at every "
                  "record of every engine run"),
        criterion("Q5_system_total", [f"{d}.system_total"], "le", 1,
                  "the ligand's system total within its floor + N eps max |total| at every "
                  "record of every engine run"),
        criterion("Q5_background", [f"{d}.background.ratio"], "le", BACKGROUND_FACTOR,
                  "the background guard: every amount's change from t = 0 in the two background "
                  "worlds against each other at least 10 x below B_state (the lead's ruling 2)"),
    ]
    for plant in ("move", "bound", "work", "heat_sign", "site_free_energy"):
        out += [
            criterion(f"Q5_plant_{plant}", [f"{d}.plants.{plant}.exact"], "ge", 1,
                      f"the {plant} plant: every prefix row within every check, the planted "
                      "row flagged by the plant's checks with its passing ledgers within their "
                      "bounds"),
            criterion(f"Q5_plant_{plant}_margin", [f"{d}.plants.{plant}.margin"], "ge",
                      CONTROLS_MARGIN, f"the {plant} plant's margin at its row, at least 10"),
        ]
    out += [
        criterion("Q5_plants_material_engine", [f"{d}.plants_material_engine"], "ge", 1,
                  "the material plants refused by the engine on resuming, naming their ledger"),
        criterion("Q5_plants_energy_engine_reported",
                  [f"{d}.plants.{p}.engine_refused" for p in der["energy_plants"]], "ge", 1,
                  "the engine's own verdict on each energy plant (under ARS, 2e-8 pJ + 2e-3 x "
                  "the flows does not refuse a 1e-6 misbooking: FR-18): reported",
                  judged=False),
        criterion("Q5_energy_margins_reported",
                  [f"{d}.worlds.{w}.heat" for w in der["trace_independent"]], "le", 1,
                  "the honest heat errors over B_energy in the worlds whose energy does not "
                  "depend on the trace (the lead's ruling 1): reported", judged=False),
    ]
    for name, runs in CONTROLS.items():
        out.append(criterion(name, [f"{d}.controls.{name}.min"], "ge", CONTROLS_MARGIN,
                             f"{name} ({', '.join(runs)}): each departs from its arm's "
                             "reference by at least 10 x the arm's budget"))
    out += [
        criterion("Q6_restart", [f"{d}.Q6.restart"], "ge", 1,
                  "every restart, in process and through a snapshot, bitwise the straight run"),
        criterion("K4", [f"{d}.Q6.K4_moved_switch_differs"], "ge", 1,
                  "the restart with its switch moved one step is not bitwise the straight run"),
        criterion("Q6_batch_scalar", [f"{d}.Q6.batch_relative"], "le", BATCH_RELATIVE,
                  "each batched world within 1e-12 relative of its scalar run"),
        criterion("Q6_batch_reversed", [f"{d}.Q6.batch_reversed"], "ge", 1,
                  "each batched world bitwise its place in the reversed batch"),
        criterion("Q6_batch_scalar_bitwise", [f"{d}.Q6.batch_scalar_bitwise"], "ge", 1,
                  "each batched world bitwise its scalar run: reported", judged=False),
        criterion("Q6_idle", [f"{d}.Q6.idle"], "ge", 1,
                  "§4.8's claim 2: every multiplier zero, and no populations, bitwise the world "
                  "without the operator on every inner field and row; the zero world's own "
                  "fields frozen; no populations statically idle"),
        criterion("Q6_twins", [f"{d}.Q6.twins"], "ge", 1,
                  "the value twins identical in program text and closed-over constants"),
        criterion("Q6_signature", [f"{d}.Q6.signature"], "ge", 1,
                  "worlds of different structure refused by the batch signature with its "
                  "reason; one structure admitted"),
        criterion("Q6_refusals", [f"{d}.Q6.refusals_all"], "ge", 1,
                  "each refusal class's representative refused by its own check, its neighbour "
                  "admitted and run; the stage condition refused at run time"),
        criterion("Q6_refusals_reported",
                  [f"{d}.Q6.refusals.{c}" for c in generator.EXPECTED_CHECKS], "ge", 1,
                  "each refusal class, reported", judged=False),
    ]
    return out


def units():
    return {part: dict(dt_s=generator.LADDER_PARTS.get(part), note="sized at the rehearsal")
            for part in generator.PARTS}


def resources():
    entry = (f"{PYTHON} -B -m validation.tissue.site_occupancy_acceptance_qualification judged "
             "SNAPSHOT/validation/tissue/site_occupancy_acceptance_protocol.json OUT/PART PART")
    return dict(
        status="a template until the rehearsal measures each unit",
        environment="from the snapshot's root, PYTHONPATH=SNAPSHOT/src:SNAPSHOT, "
                    "JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu, CUDA_VISIBLE_DEVICES= (empty), "
                    "OPENBLAS_NUM_THREADS=1, PYTHONDONTWRITEBYTECODE=1, CPU backend only, "
                    "float64",
        unit=("scripts/run_detached.sh fr3-PART CAP --cpus CPU --oom-first --runtime-max "
              "RUNTIME_MAX_S --dir SNAPSHOT --env PYTHONPATH=SNAPSHOT/src:SNAPSHOT --env "
              "JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu --env CUDA_VISIBLE_DEVICES= --env "
              f"OPENBLAS_NUM_THREADS=1 --env PYTHONDONTWRITEBYTECODE=1 -- {entry}"),
        judge=(f"{PYTHON} -B -m validation.tissue.site_occupancy_acceptance_judge judged "
               "SNAPSHOT/validation/tissue/site_occupancy_acceptance_protocol.json OUT/verdict "
               "OUT/*/results.json (in its own unit: 1G, 600 s; it runs nothing)"),
        runtime_max_rule="D150's rule on the larger of a sizing rate and the rehearsal's wall "
                         "(3 x estimate + 600 s, rounded up to the minute)",
        attempts="harness_limits",
    )


def judge_section():
    return dict(
        written=WRITTEN,
        generator="validation/tissue/site_occupancy_acceptance_qualification.py (records only)",
        plants="validation/tissue/site_occupancy_acceptance_plants.py (checkpoint edits, each in "
               "its own process)",
        judge="validation/tissue/site_occupancy_acceptance_judge.py (reads records, never runs; "
              "FR-4's and FR-5's arithmetic imported read-only from validation/tissue/"
              "compartment_ph_judge.py)",
        references="the FR references agent's R-ode, R-closed, R-eq and R-qss through "
                   "validation/fr3/references/REFERENCES_USAGE.md (api.reference, "
                   "api.accessibility), on validation/fr3/references/reference_inputs.json",
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
