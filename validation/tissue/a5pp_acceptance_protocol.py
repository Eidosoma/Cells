"""fr6-a5pp-v1's drafter: its machine criteria, derivation, units, and registration path.

The protocol (validation/tissue/a5pp_acceptance_protocol.json) is PROPOSED and hand-drafted, with
its prose criteria, budgets, controls and the lead's rulings. This module writes what the judge
needs beside the prose (`judge`): the derivation's parts and parameters (the judge's docstring
fixes the arithmetic), the machine criteria in MG0c's evaluator form (`judged: false` for a
reported item), the units and the launch template. `draft` writes that section and
`judged_parts` into the PROPOSED protocol in place and changes nothing else; rerunning it changes
nothing. `register` is the lead's.

Usage:
  python -m validation.tissue.a5pp_acceptance_protocol draft
  python -m validation.tissue.a5pp_acceptance_protocol register PROTOCOL_JSON RECORD_JSON
"""

import json
import sys
from pathlib import Path

from validation.tissue import a5pp_acceptance_fixtures as af
from validation.tissue import a5pp_acceptance_qualification as generator

PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"
BAND = [1.7, 2.3]  # A5's band (the coupling protocol's).
RESOLUTION = {"floor_factor": 100.0, "rounding": {"s": 1e-13, "a_eff": 1e-13}}  # Its rule.
OBSERVABLES = ["V", "amounts", "s", "a_eff"]
JUDGED_OBSERVABLES = ["V", "amounts"]
STATE_BUDGET = {"V": 1e-6, "amounts": 3e-8}  # At 1 ms; reported only (the lead's ruling 1).
CONTROLS_MARGIN = 10.0
START_RELATIVE = 1e-15
WRITTEN = ("18 November 2026, by the FR owner, after the protocol's world was fixed and the lead "
           "ruled on its six questions, and before any engine output compared with the references")
ENGINE_IDS = [
    "cells.model.resolved_pump_composite@1", "cells.model.resolved_pump_tissue@3", "cells.operator.species_regulated_availability@1",
    "exact_two_state_half_steps@1", "cells.regulation.hill_regulated_two_state@1", "cells.operator.scheduled_species_turnover@1",
    "exact_production_clearance_half_steps@1", "cells.channel.kleak_always_open@1",
    "cells.route.constant_field@1", "cells.field_closure.resolved_capacitor_components_current_continuity@1",
    "cells.solver.capacitive_reduction_gauged_damped_newton@2", "cells.solver.imex_ars222_face_electromigration@1"]
ALL = ["V", "amounts"]


def rung_keys():
    return [generator.dt_key(dt) for dt in af.LADDER_S]


def control_checks():
    """{control part: {rung key: [judged observables]}} (the lead's rulings 1 and 6)."""
    keys = rung_keys()
    every = {key: list(ALL) for key in keys}
    out = {name: dict(every) for name in (
        "K_prior_swapped", "K_prior_shared_a", "K_prior_shared_b", "K_prior_shared_mean",
        "K_prior_ignored", "K_state_bypassed", "K_k_on", "K_k_off")}
    fine, finest = keys[2], keys[3]
    out["K_basal_reference"] = {key: (["amounts", "V"] if key in (fine, finest) else ["amounts"])
                                for key in keys}
    out["K_basal_rule"] = {fine: ["amounts"], finest: ["amounts", "V"]}
    return out


def derivation():
    return dict(
        run_parts=list(generator.PARTS),
        rung_parts=list(generator.RUNGS),
        rung_keys=rung_keys(),
        ladder_dt_s=list(af.LADDER_S),
        engine_ids=ENGINE_IDS,
        band=BAND,
        resolution=RESOLUTION,
        observables=OBSERVABLES,
        judged_observables=JUDGED_OBSERVABLES,
        controls=control_checks(),
        state_budget=STATE_BUDGET,
        record_unit_s=af.RECORD_UNIT_S,
    )


def criterion(id_, metrics, comparison, threshold, basis, judged=True):
    return dict(id=id_, metrics=list(metrics), comparison=comparison, threshold=threshold,
                basis=basis, judged=judged)


def criteria():
    d = "derived"
    out = [
        criterion("C0_admission", [f"{d}.admission.all_admitted"], "ge", 1,
                  "every run part admitted and run to its end with every host check on every "
                  "accepted row (the runner)"),
        criterion("C0_ids", [f"{d}.ids"], "ge", 1,
                  "every rung's printed IDs among the declared engine models"),
        criterion("A5pp_start", [f"{d}.start"], "le", START_RELATIVE,
                  "row 0 is the references' start (V, the amounts, s), within 1e-15 relative"),
    ]
    for x in JUDGED_OBSERVABLES:
        out += [
            criterion(f"A5pp_{x}_order", [f"{d}.orders.{x}_in_band"], "ge", 1,
                      f"every resolved pair's observed order of {x} lies in [1.7, 2.3] "
                      "(resolved: the finer error at least 100 floors and its rounding scale)"),
            criterion(f"A5pp_{x}_resolved", [f"{d}.orders.{x}_resolved"], "ge",
                      "DEVELOPMENT_COUNT_LESS_ONE",
                      "the judged rule is not vacuous: at least this many resolved pairs (the "
                      "development count less one, the lead's ruling 5)"),
        ]
    for name in control_checks():
        if name == "K_basal_rule":
            continue
        out.append(criterion(name, [f"{d}.controls.{name}.min"], "ge", CONTROLS_MARGIN,
                             f"{name}: its departure from the references at least 10 x the honest "
                             "engine's own error at the same rung, where the lead's rulings 1 "
                             "and 6 judge it"))
    out += [
        criterion("K_basal_rule_detected", [f"{d}.basal_rule_detection.caught"], "ge", 1,
                  "K_basal_rule at the registered delta: some resolved pair of V or the amounts "
                  "outside the band (the coupling protocol's detection; the lead's ruling 6)"),
        criterion("K_basal_rule", [f"{d}.controls.K_basal_rule.min"], "ge", CONTROLS_MARGIN,
                  "K_basal_rule: at least 10 x the honest error in the amounts at 0.25 and 0.125 "
                  "ms and in V at 0.125 ms (rule (b) where it has power: the lead's ruling 6)"),
        criterion("A5pp_state_reported", [f"{d}.state_budget_reported.V",
                                          f"{d}.state_budget_reported.amounts"], "le", 1,
                  "V and the amounts against the dt^2 state budget derived from the references' "
                  "stand-in: reported (the lead's ruling 1)", judged=False),
        criterion("A5pp_s_reported", [f"{d}.orders.s.resolved"], "ge", 0,
                  "s's errors and orders: reported", judged=False),
        criterion("A5pp_a_eff_reported", [f"{d}.orders.a_eff.resolved"], "ge", 0,
                  "a_eff's errors and orders: reported", judged=False),
    ]
    return out


def units():
    return {part: dict(dt_s=generator.RUNGS.get(part), note="sized at the rehearsal")
            for part in generator.PARTS}


def resources():
    entry = (f"{PYTHON} -B -m validation.tissue.a5pp_acceptance_qualification judged "
             "SNAPSHOT/validation/tissue/a5pp_acceptance_protocol.json OUT/PART PART")
    return dict(
        status="a template until the rehearsal measures each unit",
        environment="from the snapshot's root, PYTHONPATH=SNAPSHOT/src:SNAPSHOT, "
                    "JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu, CUDA_VISIBLE_DEVICES= (empty), "
                    "OPENBLAS_NUM_THREADS=1, PYTHONDONTWRITEBYTECODE=1, CPU backend only, "
                    "float64",
        unit=("scripts/run_detached.sh fr6-PART CAP --cpus CPU --oom-first --runtime-max "
              "RUNTIME_MAX_S --dir SNAPSHOT --env PYTHONPATH=SNAPSHOT/src:SNAPSHOT --env "
              "JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu --env CUDA_VISIBLE_DEVICES= --env "
              f"OPENBLAS_NUM_THREADS=1 --env PYTHONDONTWRITEBYTECODE=1 -- {entry}"),
        judge=(f"{PYTHON} -B -m validation.tissue.a5pp_acceptance_judge judged "
               "SNAPSHOT/validation/tissue/a5pp_acceptance_protocol.json OUT/verdict "
               "OUT/*/results.json (in its own unit: 1G, 600 s; it runs nothing)"),
        runtime_max_rule="D150's rule on the larger of a sizing rate and the rehearsal's wall "
                         "(3 x estimate + 600 s, rounded up to the minute)",
        attempts="harness_limits",
    )


def judge_section(protocol=None):
    """The judge section; the resolved-count thresholds come from the protocol's
    `development_counts` once the development run fixes them (the lead's ruling 5)."""
    counts = (protocol or {}).get("development_counts") or {}
    rows = criteria()
    for c in rows:
        if c["threshold"] == "DEVELOPMENT_COUNT_LESS_ONE":
            x = c["id"].split("_")[1]
            fixed = isinstance(counts.get(x), int)
            c["threshold"] = max(1, counts[x] - 1) if fixed else 1  # Provisional: at least one.
            if not fixed:
                c["basis"] += "; provisional at 1 until the development run fixes the count"
    return dict(
        written=WRITTEN,
        generator="validation/tissue/a5pp_acceptance_qualification.py (records only)",
        judge="validation/tissue/a5pp_acceptance_judge.py (reads records, never runs; the "
              "coupling protocol's resolved-pair arithmetic imported read-only from "
              "validation/tissue/regulated_availability_judge.py, FR-4's and FR-5's merge from "
              "validation/tissue/compartment_ph_judge.py)",
        references="the FR references agent's a5pp.reference and a5pp.floor through "
                   "validation/fr6/references/REFERENCES_USAGE.md, on "
                   "validation/fr6/references/reference_inputs.json",
        derivation=derivation(),
        criteria=rows,
        units=units(),
        resources=resources(),
    )


def draft(path=None):
    path = Path(path or generator.PROTOCOL)
    protocol = json.loads(path.read_text())
    if not str(protocol.get("status")).startswith("PROPOSED") or "registration" in protocol:
        raise SystemExit("Refused: only a PROPOSED protocol without a registration record is "
                         "drafted")
    out = dict(protocol)
    out["judged_parts"] = list(generator.PARTS)
    out["judge"] = judge_section(protocol)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    return out


def register(protocol_path, record_path):
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
