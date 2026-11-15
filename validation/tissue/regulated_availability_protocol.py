"""The coupling operator's qualification protocol (milestone 4): its draft from disclosed runs.

docs/INVENTORY_COUPLING_DESIGN.md §10. The protocol (validation/tissue/
regulated_availability_protocol.json) is PROPOSED: drafted here from the development run named in
it, for the lead's review with the advisor. Only the lead registers it, and registration changes
its status alone. The path is D150's and MG0c's: the generator writes records
(validation/tissue/regulated_availability_dt_study), a separate judge reads them
(validation/tissue/regulated_availability_judge), controls show each judged rule can fail, then a
rehearsal, a dry run, the final check, the registration and one judged run.

What this draft decides from the development run, by rules fixed here (not by fitting):
* the judged observables of each arm: V, the amounts and U wherever they have a resolved pair; s,
  a_eff and F only where every pair of the ladder is resolved (the lead's rule: at 100 to 200
  floors they are fragile on another machine);
* each judged observable's minimum number of resolved pairs: the development count less one, at
  least one (a judged rule cannot pass with nothing resolved);
* the registered δ of each δ-control: the development δ, rounded up on a 1-2-5 grid;
* the regression pins at 1 ms (outside the judged list): twice the development error, at least
  100 floors, and at least 1e-13 for a dimensionless quantity.
It refuses to draft if a control is not caught on the development run.

With a rehearsal record (--rehearsal REHEARSAL_JSON: the rehearsal's facts on main, gathered from
its evidence), the redraft carries them and the judged run's resource budget (below) with its
memory cap of record. The criteria are drawn from the development run alone, so a redraft leaves
them unchanged. Every draft also records D147's facts for every world it runs (`d147`) and the
disclosures of what was fixed with development results in view.

The judged run's resource budget is three times the rehearsal's wall time plus ten minutes
(D150's rule); the launcher enforces it. Registration is the lead's, through `register` (MG0c's
form): the record's status replaces PROPOSED and the record follows it.

Usage: python -m validation.tissue.regulated_availability_protocol draft RESULTS_JSON
       [OUTPUT_JSON] [--rehearsal REHEARSAL_JSON]
       python -m validation.tissue.regulated_availability_protocol register PROTOCOL_JSON
       RECORD_JSON
"""

import json
import math
import sys
from pathlib import Path

from validation.tissue import regulated_availability_judge as judge

PROTOCOL = Path(__file__).with_name("regulated_availability_protocol.json")
STATUS = (
    "PROPOSED (drafted 14 November 2026 by the coupling operator's engine agent from the "
    "development run named in development_runs, for the lead's review with the advisor; not "
    "registered, and no judged run is made before the lead registers it)"
)
BAND = [1.7, 2.3]
FLOOR_FACTOR = 100.0
ROUNDING = {"s": 1e-13, "a_eff": 1e-13, "F": 1e-13, "U": "steps_eps_max"}
OBSERVABLES = ["V", "amounts", "a_eff", "s", "U", "F"]
CORE, FRAGILE = ("V", "amounts", "U"), ("s", "a_eff", "F")
ARMS = ("a4.baseline", "a4.coupled", "a4.fast", "a5.baseline", "a5.coupled")
CONTROL_ARMS = {
    "first_order_state": "a4.coupled",
    "lagged_factor": "a4.coupled",
    "delta_basal_a4": "a4.coupled",
    "delta_basal_a5": "a5.coupled",
}
ROW0_TOLERANCE_V = 1e-15  # A priori: both sides start from the reference's zero-current start.
FACTOR_ROUNDING = 64 * 2.0**-52  # A5's factor is the law at X: rounding only, a priori.
DIMENSIONLESS = ("a_eff", "F", "s")
GRID = [1, 2, 5]


def snap_up(value):
    """The smallest point of a 1-2-5 grid at or above value."""
    exponent = math.floor(math.log10(value))
    for e in (exponent, exponent + 1):
        for g in GRID:
            if g * 10.0**e >= value * (1 - 1e-12):
                return g * 10.0**e
    return value


def criterion(id_, metrics, comparison, threshold, basis, judged=True):
    return dict(
        id=id_,
        metrics=metrics,
        comparison=comparison,
        threshold=threshold,
        basis=basis,
        judged=judged,
    )


def skeleton():
    return dict(
        id="coupling_regulated_availability_v1",
        status=STATUS,
        operator="species_regulated_availability@1",
        models=[
            "resolved_pump_composite@1",
            "resolved_pump_tissue@3",
            "species_regulated_availability@1",
            "scheduled_species_turnover@1 (A5's regulator)",
        ],
        references="validation/coupling (R-fac, R-feedback, R-cell) through REFERENCES_USAGE.md",
        generator="validation/tissue/regulated_availability_dt_study.py",
        judge="validation/tissue/regulated_availability_judge.py",
        controls_module="validation/tissue/regulated_availability_controls.py",
        ladder_s=[1e-3, 5e-4, 2.5e-4, 1.25e-4],
        band=BAND,
        resolution=dict(floor_factor=FLOOR_FACTOR, rounding=ROUNDING),
        observables=OBSERVABLES,
        judged_parts=["a1", "a4", "a5", "controls"],
    )


def scope():
    return dict(
        worlds=(
            "A4 (R-feedback): two 2 pL cells on 4 pF patches facing held baths, joined by a "
            "contact of 2e-8 m/s with its gate held at 1; a state of Na in both, its complement "
            "on the contact (side both, basal 0.2); 2 s, started from the reference's own state "
            "at 50 ms (after the contact's voltage transient); the contact sits at the edge of "
            "@3's explicit-rate bound at 1 ms. A fast arm at k_on + k_off = 900/s. A5 (R-cell): "
            "one cell with a K-leak population read at once from a neutral regulator with D150's "
            "turnover and a production pulse; 1 s."
        ),
        not_covered=(
            "pumps and gated channels (the references model neither); horizons beyond 2 s (A4) "
            "and 1 s (A5); A10, the first consumer (its crossing level above the A.3 "
            "commitment limit is never reached: refuse it or mark it unreachable, the "
            "references agent's note, for A10's own protocol); A2's states against R-state "
            "(milestone 2's closed forms stand); restart, windows, batches and the bitwise "
            "items, which are tier tests"
        ),
        gpu=(
            "CPU-only in version 1 (proposed, the lead's recommendation): the floors, the band's "
            "resolution and A4's fragile observables were measured on CPU; an L4 variant is a "
            "later protocol with its own development runs"
        ),
        a1=(
            "the references agent's form: the absolute error in eps (fr.eps_error) against "
            "R-fac's exact path, not a relative-ulp criterion (too strict in deep Hill tails), "
            "within an a priori bound per point"
        ),
    )


def draft(results, results_path):
    if results.get("status") != "Development run" or not results.get("complete"):
        raise SystemExit("Refused: the draft needs a complete development run")
    missing = sorted({"a1", "a4", "a5", "controls"} - set(results["parts"]))
    if missing:
        raise SystemExit(f"Refused: the development run lacks parts {missing}")
    protocol = skeleton()
    parts = results["parts"]

    # The judged observables and their minimum resolved pairs, from the development run.
    candidates = dict(protocol, judged_observables={a: [] for a in ARMS}, control_arms={})
    derived = judge.derive(results, candidates)
    judged, minimum = {}, {}
    for key in ARMS:
        world, arm = key.split(".")
        metrics = derived[world][arm]
        chosen = []
        for x in OBSERVABLES:
            pairs = metrics[x]["pairs"]
            resolved = metrics[x]["resolved"]
            if (x in CORE and resolved >= 1) or (x in FRAGILE and resolved == len(pairs)):
                chosen.append(x)
                minimum[f"{key}.{x}"] = max(1, resolved - 1)
        judged[key] = chosen
    protocol["judged_observables"] = judged
    protocol["minimum_resolved_pairs"] = minimum
    protocol["control_arms"] = CONTROL_ARMS

    # The controls must be caught on the development run, by the judge.
    check = dict(protocol)
    controls = judge.derive(results, check)["controls"]
    uncaught = sorted(k for k, v in controls.items() if not v["caught"])
    if uncaught:
        raise SystemExit(f"Refused: the development run does not catch the controls {uncaught}")
    protocol["registered_control_deltas"] = {
        k: snap_up(parts["controls"][k]["delta"]) for k in ("delta_basal_a4", "delta_basal_a5")
    }

    criteria = []
    for which in ("host", "device", "products"):
        criteria += [
            criterion(
                f"A1_{which}_within_bound",
                [f"parts.a1.{which}.max_ratio"],
                "le",
                1.0,
                f"A1, {which}: every grid point's absolute error in eps against R-fac's exact "
                "path is within its a priori bound (4 + 2 f (1 - f) n (|ln x| + |ln K| + 1); "
                "4 for state laws; the sum plus 1 for a product)",
            ),
            criterion(
                f"A1_{which}_exact_points",
                [f"parts.a1.{which}.exact_points_exact"],
                "ge",
                1,
                f"A1, {which}: at x = 0 the factor is exactly 0 (activation) or 1 (inhibition)",
            ),
        ]
    for key in ARMS:
        world, arm = key.split(".")
        for x in judged[key]:
            base = f"derived.{world}.{arm}.{x}"
            criteria += [
                criterion(
                    f"{world.upper()}_{arm}_{x}_order",
                    [f"{base}.in_band"],
                    "ge",
                    1,
                    f"every resolved pair's observed order of {x} lies in {BAND} (resolved: the "
                    f"finer error at least {FLOOR_FACTOR:g} floors and its rounding scale)",
                ),
                criterion(
                    f"{world.upper()}_{arm}_{x}_resolved",
                    [f"{base}.resolved"],
                    "ge",
                    minimum[f"{key}.{x}"],
                    "the judged rule is not vacuous: at least this many resolved pairs (the "
                    "development count less one)",
                ),
            ]
        for x in OBSERVABLES:
            if x not in judged[key]:
                criteria.append(
                    criterion(
                        f"{world.upper()}_{arm}_{x}_reported",
                        [
                            f"derived.{world}.{arm}.{x}.errors",
                            f"derived.{world}.{arm}.{x}.resolved",
                        ],
                        "ge",
                        0,
                        "reported, not judged (the errors over the ladder, then the resolved "
                        "pairs): no resolved pair, or (for s, a_eff and F) not every pair "
                        "resolved in development",
                        judged=False,
                    )
                )
        criteria.append(
            criterion(
                f"{world.upper()}_{arm}_start",
                [f"derived.{world}.{arm}.row0_max"],
                "le",
                ROW0_TOLERANCE_V,
                "row 0 is the reference's start (a priori: both start from it)",
            )
        )
    for arm in ("baseline", "coupled", "fast"):
        criteria.append(
            criterion(
                f"A4_{arm}_gate_held",
                [f"derived.a4.{arm}.gates_held"],
                "ge",
                1,
                "the contact's gate stays at exactly 1 in every run (the reference's gate is "
                "fixed open)",
            )
        )
    criteria.append(
        criterion(
            "A5_coupled_factor_at_rounding",
            ["derived.a5.coupled.a_eff.max_error", "derived.a5.coupled.F.max_error"],
            "le",
            FACTOR_ROUNDING,
            "A5's factor is the law at X, which D150's turnover gives exactly on the grid: the "
            "error is rounding at every dt (64 eps, a priori)",
        )
    )
    for name, arm in CONTROL_ARMS.items():
        what = {
            "first_order_state": "the regulatory state integrated at first order (explicit "
            "Euler half-steps)",
            "lagged_factor": "the factor one step stale",
            "delta_basal_a4": "A4's basal level times (1 + δ) at the registered δ",
            "delta_basal_a5": "A5's basal level times (1 + δ) at the registered δ",
        }[name]
        criteria.append(
            criterion(
                f"control_{name}_caught",
                [f"derived.controls.{name}.caught"],
                "ge",
                1,
                f"control: {what}, on {arm}, puts a resolved pair of a judged observable out "
                "of the band (the rule can fail)",
            )
        )
    protocol["criteria"] = criteria

    pins = {}
    for key in ("a4.coupled", "a5.coupled"):
        world, arm = key.split(".")
        floor = parts[world][arm]["floor"]
        for x in OBSERVABLES:
            e = derived[world][arm][x]["at_first_dt"]
            if e == 0.0:
                continue  # Not an observable of this world (A5 has no state).
            pin = max(
                2.0 * e,
                FLOOR_FACTOR * floor.get(x, 0.0),
                1e-13 if x in DIMENSIONLESS or x == "U" else 0.0,
            )
            if pin > 0:
                pins[f"{key}.{x}"] = pin
    protocol["regression_pins_1ms"] = dict(
        judged=False,
        pins=pins,
        basis=(
            "a regression guard, not a qualification (the lead's ruling): twice the "
            "development error at 1 ms, at least 100 floors and 1e-13 for dimensionless "
            "quantities; tests/unit/test_species_regulated_availability_regression.py"
        ),
    )
    protocol["scope"] = scope()
    protocol["attempt_rule"] = (
        "D150's: one judged run from a clean execution snapshot of main into a new directory. An "
        "infrastructure ending (a timeout at the launcher's runtime limit, a runtime kill, an OOM "
        "kill, a signal, or an incomplete results.json) is rerun once from the same snapshot into "
        "a new directory; a failed criterion is a verdict, not a retry"
    )
    protocol["disclosures"] = DISCLOSURES
    protocol["d147"] = d147_worlds()
    protocol["steps_before_judgement"] = [
        "the lead's review of this draft with the advisor",
        "a rehearsal: the judged entry from a snapshot, refused while PROPOSED (the guard)",
        "a dry run: the judged entries with a registered dry-run copy, from the snapshot to be "
        "judged, every part, compared bitwise with the development run",
        "the final check of the registered values against the dry run",
        "registration by the lead (the status alone changes)",
        "one judged run and its verdict",
    ]
    protocol["development_runs"] = [
        dict(path=str(results_path), source=results["source"], status=results["status"])
    ]
    protocol["development_summary"] = {
        key: {
            x: dict(
                orders=[
                    p["order"] for p in derived[key.split(".")[0]][key.split(".")[1]][x]["pairs"]
                ],
                resolved=derived[key.split(".")[0]][key.split(".")[1]][x]["resolved"],
            )
            for x in OBSERVABLES
        }
        for key in ARMS
    }
    protocol["development_controls"] = controls
    protocol["questions"] = [
        "Answered by the lead (14 November 2026): the band [1.7, 2.3] stands, set a priori "
        "around the scheme's order; the minimum resolved pairs and U's rounding-scale rule "
        "stand, and A4's uncoupled U stays reported; version 1 is CPU-only, an L4 variant later",
    ]
    return protocol


DISCLOSURES = [
    "The band [1.7, 2.3] was set around the scheme's order 2 (the lead's ruling) with the "
    "development orders, 1.97 to 2.08 on resolved pairs, in view",
    "The judged observables (V, the amounts and U wherever resolved; s, a_eff and F only where "
    "every pair is resolved) and each rule's minimum resolved pairs (the development count less "
    "one) are rules applied to the development run, so they were fixed with its results in view",
    "The registered deltas (2e-5 and 5e-6) are the development deltas rounded up on a 1-2-5 "
    "grid; the development deltas were set from that run's own finest errors (a plateau at 10 "
    "times the finest error in V)",
    "The rounding-scale rule (N eps max|U| for U; 1e-13 for s, a_eff and F) was written after "
    "the development record showed A4's uncoupled U pair at 2.33, with errors of 8.6e-13 and "
    "1.7e-13 s at accumulated rounding; the rule excludes that pair, and U is reported only in "
    "that arm",
    "A1's bound (4 + 2 f (1 - f) n (|ln x| + |ln K| + 1) eps) and the 100-floor factor were "
    "written before A1 and the dt study first ran",
    "The development run of record comes from the snapshot of 476c6e01 and the rehearsal from "
    "main at 0448f9fc; the rehearsal's records equal the development run's bit for bit, the "
    "δ-controls apart (run at the registered δ by design)",
]


def d147_worlds():
    """D147's facts for every world the protocol runs (the lead's final check, as MG0c's
    hand-back): validation/tissue/field_solver_choice.free_field_offsets, the declared field
    solver and solver_for's automatic choice, at the ladder's first dt (the layout does not
    depend on dt). Each cell's capacitor component holds its own held bath, so 0 free offsets
    are expected; any free offset refuses the draft (D147: such a world declares @3)."""
    from validation.coupling import cells_reference as rc
    from validation.tissue import field_solver_choice as fsc
    from validation.tissue import regulated_availability_controls as controls_module
    from validation.tissue import regulated_availability_dt_study as generator
    from validation.tissue import regulated_availability_references as rr

    def initial_of(world):
        reference = rc.simulate(world, 0.01, record=(0.01,))
        return {
            c: (reference.initial[c]["V"], reference.initial[c]["background_fmol"])
            for c in world.cells
        }

    def raw_of(world, spec_, initial, control=None):
        times = [0.0, *generator.grid_records(spec_["end"], spec_["every"], generator.DTS[0])]
        raw = rr.engine_definition(
            world, dt=generator.DTS[0], end=spec_["end"], times=times, initial=initial
        )
        return raw if control is None else controls_module.as_control(raw, control)

    a4, a5 = generator.a4_world(), rr.cell_world
    a4_initial, a5_initial = initial_of(a4()), initial_of(a5())
    A4, A5 = generator.A4, generator.A5
    worlds = [
        ("a4.baseline", raw_of(a4(enabled=0), A4, initial_of(a4(enabled=0))), None),
        ("a4.coupled", raw_of(a4(), A4, a4_initial), None),
        ("a4.fast", raw_of(a4(**A4["fast"]), A4, initial_of(a4(**A4["fast"]))), None),
        ("a5.baseline", raw_of(a5(**A5["baseline"]), A5, initial_of(a5(**A5["baseline"]))), None),
        ("a5.coupled", raw_of(a5(), A5, a5_initial), None),
        (
            "controls.first_order_state",
            raw_of(a4(), A4, a4_initial, "first_order_state"),
            "first_order_state",
        ),
        ("controls.lagged_factor", raw_of(a4(), A4, a4_initial, "lagged_factor"), "lagged_factor"),
        ("controls.delta_basal_a4", raw_of(a4(basal=A4["basal"] * 1.00002), A4, a4_initial), None),
        ("controls.delta_basal_a5", raw_of(a5(basal=A5["basal"] * 1.000005), A5, a5_initial), None),
    ]
    records = []
    for label, raw, control in worlds:
        if control is None:
            free, auto = fsc.free_field_offsets(raw), fsc.solver_for(raw)
        else:
            with controls_module.registered(control):
                free, auto = fsc.free_field_offsets(raw), fsc.solver_for(raw)
        records.append(
            dict(
                world=label,
                model=raw["model"]["id"],
                inner_model=raw["model"].get("inner_model"),
                free_field_offsets=free,
                declared_field_solver=raw["execution"]["field_solver"],
                solver_for_auto=auto,
            )
        )
    worst = max(r["free_field_offsets"] for r in records)
    if worst > 0:
        raise SystemExit("Refused: a protocol world has free field offsets (D147): tell the lead")
    return dict(
        worlds=records,
        max_free_field_offsets=worst,
        declared_field_solvers=sorted({r["declared_field_solver"] for r in records}),
        automatic_choice_agrees=all(
            r["solver_for_auto"] == r["declared_field_solver"] for r in records
        ),
    )


def with_rehearsal(protocol, rehearsal):
    """The rehearsal's facts, and the judged run's resource budget from them."""
    if not rehearsal.get("passed"):
        raise SystemExit("Refused: the rehearsal record does not pass; nothing is redrafted")
    wall = rehearsal["judged_run_wall_s"]
    protocol["rehearsal"] = rehearsal
    protocol["resources"] = dict(
        cpus=1,
        memory_cap=rehearsal["memory_cap"],
        observed_memory_peak_bytes=rehearsal["memory_peak_bytes"],
        observed_wall_s=wall,
        runtime_max_s=60 * math.ceil((3 * wall + 600) / 60),
        basis=(
            "three times the rehearsal's wall time on one CPU plus 10 minutes, rounded up to the "
            "minute (D150's rule; shared CPUs ran 1.65 to 4.6 times slow on 14 November)"
        ),
        enforced_by=(
            "the launcher: scripts/run_detached.sh with the memory cap, --oom-first and "
            "--runtime-max; neither the generator nor the judge reads these fields"
        ),
        launch=(
            "scripts/run_detached.sh UNIT 4G --cpus CPU --oom-first --runtime-max "
            "RUNTIME_MAX_S -- python -m validation.tissue.regulated_availability_dt_study judged "
            "validation/tissue/regulated_availability_protocol.json NEW_DIR (from the clean "
            "snapshot of main to be judged); then python -m "
            "validation.tissue.regulated_availability_judge judged PROTOCOL NEW_DIR/results.json "
            "VERDICT_DIR"
        ),
    )
    protocol["steps_before_judgement"] = [
        step
        + (
            " (done: protocol['rehearsal'])"
            if step.startswith(("a rehearsal", "a dry run"))
            else ""
        )
        for step in protocol["steps_before_judgement"]
    ]
    return protocol


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
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(path)
    return out


def main(argv):
    if not argv or argv[0] not in ("draft", "register"):
        raise SystemExit(__doc__)
    action, argv = argv[0], argv[1:]
    if action == "register":
        if len(argv) != 2:
            raise SystemExit("Usage: register PROTOCOL_JSON RECORD_JSON")
        return register(*argv)
    rehearsal = None
    if "--rehearsal" in argv:
        i = argv.index("--rehearsal")
        rehearsal = json.loads(Path(argv[i + 1]).read_text())
        argv = argv[:i] + argv[i + 2 :]
    results_path = Path(argv[0])
    out = Path(argv[1]) if len(argv) > 1 else PROTOCOL
    results = json.loads(results_path.read_text())
    protocol = draft(results, results_path)
    if rehearsal is not None:
        protocol = with_rehearsal(protocol, rehearsal)
    out.write_text(json.dumps(protocol, indent=1) + "\n")
    judged = [c["id"] for c in protocol["criteria"] if c["judged"]]
    print(out, len(judged), "judged criteria")


if __name__ == "__main__":
    main(sys.argv[1:])
