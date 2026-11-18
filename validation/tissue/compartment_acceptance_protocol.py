"""fr1-closed-compartment-v1's drafter: its machine criteria, derivation, units, and registration
path.

The protocol (validation/tissue/compartment_acceptance_protocol.json) is PROPOSED and hand-drafted,
with prose criteria C1 to C13, budgets, controls and questions for the lead. This module writes what
the judge needs beside the prose (`judge`): the derivation's parts and parameters (the judge's
docstring fixes the arithmetic), the machine criteria in MG0c's evaluator form (a metric path, a
comparison and a threshold, `judged: false` for a reported item), the units and the launch
template. `draft` writes that section and `judged_parts` into the PROPOSED protocol in place and
changes nothing else, so no hand-drafted leaf (its status above all) is pinned here; rerunning it
changes nothing. `register` is the lead's.

Usage:
  python -m validation.tissue.compartment_acceptance_protocol draft
  python -m validation.tissue.compartment_acceptance_protocol register PROTOCOL_JSON RECORD_JSON
"""

import json
import sys
from pathlib import Path

from validation.tissue import compartment_acceptance_fixtures as af
from validation.tissue import compartment_acceptance_qualification as generator

PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"
BAND = [1.8, 2.2]  # Orders: the classes rule's band.
SPLIT_FRACTION = 1e-3  # B_split: of the world's initial S (and P) content.
ENERGY_RELATIVE = 2e-3  # The IMEX energy residual over the integrated flows.
SPLITTING_TOLERANCE = 1e-3  # C4: (x/x_eq - 1) over the design's form, within this of 1.
BATCH_RELATIVE = 1e-12  # C12: each batched world against its scalar run.
CONTROLS_MARGIN = 10.0
WRITTEN = ("17 November 2026, by the FR owner, after the protocol's worlds were fixed and before "
           "any run of the protocol (development runs of the generator's parts on quick horizons, "
           "to test the tools, had run)")
OBSERVABLES = ["amount_S_cell_0", "amount_S_ecs_0"]
C1_CHECKS = {
    "R1_a_face": "refusal 1 (the node: a face)",
    "R1_a_held_bath": "refusal 1 (the node: a held bath)",
    "R2_two_patches": "refusal 2 (the patch)",
    "R3_one_compartment_per_node": "refusal 3 (one compartment per node)",
    "R4_an_ion_route": "refusal 4 (an ion route)",
    "R5_a_charge_anchor": "refusal 5 (the charge anchor)",
    "R6_no_held_bath": "refusal 6 (a held-bath topology)",
    "R7_replacement_on_an_owner": "refusal 7 (replacement's owners)",
}
MATERIAL_LEDGERS = ["local", "outside", "total", "charge", "electrode", "global_charge"]


def derivation():
    ladder = list(af.LADDER_S)
    exact = ["C3_flux", "C3_first_order", "C5_saturable", *generator.C11_PARTS]
    engine = [*exact[:3], *generator.C4_RUNGS, *generator.C6_RUNGS, *generator.C7_RUNGS,
              *generator.C8_RUNGS, "C10_rk4", *generator.C11_PARTS, "K1_one_way",
              "K2_no_clearance"]
    return dict(
        run_parts=[*engine, "C1_refusals", "C2_identity", "C9_silence", "C12_restart",
                   "C12_batch", "C13_controls", "K3_planted"],
        band=BAND,
        observables=OBSERVABLES,
        split_fraction=SPLIT_FRACTION,
        C3=dict(parts=["C3_flux", "C3_first_order"], route="load", node=af.NODE),
        C5=dict(part="C5_saturable"),
        C4=dict(ladder_parts=list(generator.C4_RUNGS), dt_s=ladder, observables=OBSERVABLES,
                a=af.C4_A, b=af.C4_B),
        C6=dict(ladder_parts=list(generator.C6_RUNGS), observables=OBSERVABLES,
                cleared=f"cleared_{af.NODE}_fmol"),
        C7=dict(ladder_parts=list(generator.C7_RUNGS),
                observables=[*OBSERVABLES, f"amount_P_{af.NODE}"]),
        C8=dict(ladder_parts=list(generator.C8_RUNGS),
                observables=[*OBSERVABLES, f"amount_S_{af.UPTAKE_NODE}"]),
        C10=dict(closure_parts=[*exact, *generator.C4_RUNGS, *generator.C6_RUNGS,
                                *generator.C8_RUNGS],
                 clearance=list(generator.C6_RUNGS), rk4_part="C10_rk4",
                 c6_part=list(generator.C6_RUNGS)[0],
                 imex_parts=["C3_flux", "C3_first_order", "C5_saturable",
                             list(generator.C4_RUNGS)[0],
                             list(generator.C6_RUNGS)[0], list(generator.C7_RUNGS)[0],
                             list(generator.C8_RUNGS)[0]]),
        C11=dict(parts=list(generator.C11_PARTS)),
        ledger_parts=engine,
        material_ledgers=MATERIAL_LEDGERS,
        C12=dict(restarts=2 * len(generator.RESTART_TIMES_S), worlds=len(generator.C12_WORLDS)),
        C1=dict(checks=C1_CHECKS),
        C2=dict(pairs=4),
        record_unit_s=0.01,
    )


def criterion(id_, metrics, comparison, threshold, basis, judged=True):
    return dict(id=id_, metrics=list(metrics), comparison=comparison, threshold=threshold,
                basis=basis, judged=judged)


def criteria():
    d = "derived"
    out = [
        criterion("C0_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                  "every run part admitted and run to its end with every host check on every "
                  "row (the runner)"),
        criterion("C1_refusals", [f"{d}.C1.all"], "ge", 1,
                  "each of §1.4's refusals refused by its own check, its neighbour admitted and "
                  "run"),
        criterion("C1_reported", [f"{d}.C1.{c}" for c in C1_CHECKS], "ge", 1,
                  "each refusal class, reported", judged=False),
        criterion("C2_identity", [f"{d}.C2"], "ge", 1,
                  "S5: the four traced pairs identical in program text, constants and bindings"),
        criterion("C3_loading", [f"{d}.C3.max"], "le", 1,
                  "both loading laws at rounding of R-closed at every record, and each route's "
                  "moved amount at rounding of the compartment's gain"),
    ]
    for item in ("C4", "C6", "C7", "C8"):
        observables = derivation()[item]["observables"]
        out += [criterion(f"{item}_order_{x}", [f"{d}.orders.{item}_{x}.passes"], "ge", 1,
                          f"{item}'s {x} on the three finest rungs by FR-4's classes rule")
                for x in observables]
    out += [
        criterion("C4_C8_state_error", [f"{d}.state_error.max"], "le", 1,
                  "at the declared 1 ms, each observable's Richardson error within B_split"),
        criterion("C4_C8_reference", [f"{d}.reference.max"], "le", 1,
                  "C4 against R-closed, and C6, C7 and C8 against R-linear, within B_split at "
                  "every record at the declared 1 ms"),
        criterion("C6_cleared", [f"{d}.C6_cleared"], "le", 1,
                  "C6's cleared amount within B_split of R-linear's at every record"),
        criterion("C4_step_map", [f"{d}.C4_map.map_max", f"{d}.C4_map.x_star_max"], "le", 1,
                  "at every rung, the engine at rounding of R-step-map's iterated map, and its "
                  "last x at rounding of x*"),
        criterion("C4_splitting_term", [f"{d}.C4_map.splitting_worst"], "le",
                  SPLITTING_TOLERANCE,
                  "at every rung, (x/x_eq - 1) within 1e-3 of -a(a + 2b) dt^2 / 96"),
        criterion("C5_saturable", [f"{d}.C5.reference"], "le", 1,
                  "the saturable release within rounding and its Newton tolerance of R-closed at "
                  "every record"),
        criterion("C9_S1", [f"{d}.C9.s1"], "ge", 1,
                  "S1: the compartment's ion rows bitwise at every row of every program"),
        criterion("C9_S2_S3", [f"{d}.C9.s2", f"{d}.C9.s3"], "le", 1,
                  "S2 and S3 within @3's charge tolerance at every row of every program"),
        criterion("C9_live", [f"{d}.C9.live"], "ge", 1,
                  "the owner live in every program: its ion rows moving, |phi| >= 0.05 V"),
        criterion("C10_closure", [f"{d}.C10.closure_max"], "le", 1,
                  "each exact world's route work (and C6's clearance work) equal to its nodes' "
                  "free-energy change on its own trajectory at rounding"),
        criterion("C10_C6_reference", [f"{d}.C10.C6_reference"], "le", 1,
                  "C6 (sum dn != 0): its summed route and clearance work against R-energy's "
                  "change of both nodes' G within RT B_split sum_i max_t |ln c_i| at every "
                  "record"),
        criterion("C10_rk4", [f"{d}.C10.rk4_energy"], "le", 1,
                  "the RK4 face-free world within the absolute energy bound at every row"),
        criterion("C10_imex", [f"{d}.C10.imex_over_flows"], "le", ENERGY_RELATIVE,
                  "the IMEX worlds' energy residual over the integrated flows <= 2e-3 at every "
                  "record"),
        criterion("C11_from_trace", [f"{d}.C11.max"], "le", 1,
                  "every row of the eight from-trace runs within its energy bound"),
        criterion("C11_trajectory", [f"{d}.C11_trajectory.max"], "le", 1,
                  "each from-trace run's amounts at rounding of R-energy's trajectory at every "
                  "row"),
        criterion("C11_ledgers", [f"{d}.ledgers"], "le", 1,
                  "every material and charge ledger within its bound at every record of every "
                  "run part"),
        criterion("C12_restart", [f"{d}.C12_restart"], "ge", 1,
                  "every restart, in process and through a snapshot, bitwise the straight run"),
        criterion("C12_batch_scalar", [f"{d}.C12_batch_relative"], "le", BATCH_RELATIVE,
                  "each batched world within 1e-12 relative of its scalar run"),
        criterion("C12_batch_reversed", [f"{d}.C12_batch_reversed"], "ge", 1,
                  "each batched world bitwise its place in the reversed batch"),
        criterion("C12_batch_scalar_bitwise", [f"{d}.C12_batch_scalar_bitwise"], "ge", 1,
                  "each batched world bitwise its scalar run (reported; the lead's ruling 4)",
                  judged=False),
        criterion("C13_move", [f"{d}.C13.move.exact"], "ge", 1,
                  "the misbooked move: every row before it within every bound, the planted row "
                  "refused by the outside ledger with the cytosol's local ledger passing"),
        criterion("C13_move_margin", [f"{d}.C13.move.margin"], "ge", CONTROLS_MARGIN,
                  "the misbooked move's outside ratio at the planted row, at least 10"),
        criterion("C13_work", [f"{d}.C13.work.exact"], "ge", 1,
                  "the misbooked work: every row before it within every bound, the planted row "
                  "refused by the energy ledger with every material and charge ledger passing"),
        criterion("C13_work_margin", [f"{d}.C13.work.margin"], "ge", CONTROLS_MARGIN,
                  "the misbooked work's energy ratio at the planted row, at least 10"),
        criterion("K3_route", [f"{d}.K3.route.exact"], "ge", 1,
                  "the planted K route breaks S1 and S2 at every row after its first, and at "
                  "no row before"),
        criterion("K3_route_margin", [f"{d}.K3.route.margin"], "ge", CONTROLS_MARGIN,
                  "its smallest S2 ratio over the planted rows, at least 10"),
        criterion("K3_anchor", [f"{d}.K3.anchor.exact"], "ge", 1,
                  "the planted anchor breaks S2 at every row"),
        criterion("K3_anchor_margin", [f"{d}.K3.anchor.margin"], "ge", CONTROLS_MARGIN,
                  "its smallest S2 ratio, at least 10"),
        criterion("K1", [f"{d}.controls.K1_over_budget"], "ge", CONTROLS_MARGIN,
                  "C4 without its import against R-closed: at least 10 x B_split"),
        criterion("K2", [f"{d}.controls.K2_over_budget"], "ge", CONTROLS_MARGIN,
                  "C6 without its clearance against R-linear: at least 10 x B_split"),
        criterion("K4", [f"{d}.controls.K4_moved_change_differs"], "ge", 1,
                  "C12's restart with its change moved one step is not bitwise the straight "
                  "run"),
    ]
    return out


def units():
    out = {}
    for part in generator.PARTS:
        dt = (generator.C4_RUNGS.get(part) or generator.C6_RUNGS.get(part)
              or generator.C7_RUNGS.get(part) or generator.C8_RUNGS.get(part))
        out[part] = dict(dt_s=dt, note="sized at the rehearsal")
    return out


def resources():
    entry = (f"{PYTHON} -B -m validation.tissue.compartment_acceptance_qualification judged "
             "SNAPSHOT/validation/tissue/compartment_acceptance_protocol.json OUT/PART PART")
    return dict(
        status="a template until the rehearsal measures each unit",
        environment="from the snapshot's root, PYTHONPATH=SNAPSHOT/src:SNAPSHOT, "
                    "JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu, CUDA_VISIBLE_DEVICES= (empty), "
                    "PYTHONDONTWRITEBYTECODE=1, CPU backend only, float64",
        unit=("scripts/run_detached.sh fr1-PART CAP --cpus CPU --oom-first --runtime-max "
              "RUNTIME_MAX_S --dir SNAPSHOT --env PYTHONPATH=SNAPSHOT/src:SNAPSHOT --env "
              "JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu --env CUDA_VISIBLE_DEVICES= --env "
              f"PYTHONDONTWRITEBYTECODE=1 -- {entry}"),
        judge=(f"{PYTHON} -B -m validation.tissue.compartment_acceptance_judge judged "
               "SNAPSHOT/validation/tissue/compartment_acceptance_protocol.json OUT/verdict "
               "OUT/*/results.json (in its own unit: 1G, 600 s; it runs nothing)"),
        runtime_max_rule="D150's rule on the larger of a sizing rate and the rehearsal's wall "
                         "(3 x estimate + 600 s, rounded up to the minute)",
        attempts="harness_limits",
    )


def judge_section():
    return dict(
        written=WRITTEN,
        generator="validation/tissue/compartment_acceptance_qualification.py (records only)",
        judge="validation/tissue/compartment_acceptance_judge.py (reads records, never runs; "
              "FR-4's and FR-5's arithmetic imported read-only from validation/tissue/"
              "compartment_ph_judge.py)",
        references="the FR references agent's R-closed, R-step-map, R-linear, R-capacitor and "
                   "R-energy, from Appendix A and validation/closed_compartment/"
                   "reference_inputs.json",
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
