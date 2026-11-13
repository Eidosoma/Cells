"""S3: the engine's one-cell Xenopus egg, with its furrow and restricted cleft (definition).

docs/CELL_DIVISION_S3_PLAN.md §1. The engine egg is R-full's own egg:
cleft_egg_reference.build(declared inputs, default values, the record's p_old_m_s and
a_over_l_m) from validation/division/j1_declared_inputs.json and j1_prediction_of_record.json,
written as a resolved_pump_composite@1 definition the way validation/tissue/injection_rm1.py
writes the uncleaved egg. Engine models:
* resolved_pump_composite@1 over resolved_pump_tissue@3: the cytosol (egg), the held Steinberg
  bath, the old membrane facing the bath, the new membrane facing the cleft (declared at its
  activation area A_on), the cleft node (declared at its onset volume w A_on / 2 and at bath
  composition, uncharged) and its access face to the bath (logmean_electrodiffusion@1 with
  A/L x D_s; the face length is 1 m, so area / length is A/L exactly);
* membrane_entity_state@1 (no channel populations: both membranes are passive);
* scheduled_membrane_insertion@1: the new membrane opens at the onset with A_on and grows at
  R-full's rate r = (A_J1 - A_on) / (t_J1 - onset), continuing to the horizon;
* restricted_cleft_lumen@1: the cleft's volume w A / 2, filled with bath fluid as it grows;
* electrode_current_injection@1: dLB74's pulse train throughout, carried by K and Cl in J1's
  registered fractions (rm_definition), the same field R-full's Pulses read.
Event times (onset, pulse edges) and observation times are k dt; at the steps of the study they
are R-full's times exactly (compare reports it). Observations: every pulse's front edge and
its sample 1 s later, through the horizon.

Actions (python -m validation.division.cleft_egg_engine ACTION --output FILE):
  compare      every field of the definition against R-full's build, with the declared
               differences
  check        the definition parsed at the step study's steps (0.5, 0.25 and 0.125 ms), with
               the runner's step checks (accepted or refused) and the explicit-rate bounds
The development study, R-full's reference terms and the judged run (plan §5, steps 4-6) wait for
the lead's approval; they follow injection_rm1.py's study, reference and judge.
"""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

STATUS = "Development definition of S3's cleft egg (restricted_cleft_lumen@1); not judged."
RECORD = ROOT / "validation/division/j1_prediction_of_record.json"
JUDGED_DT = 2.5e-4  # The lead's choice (plan §6).
STUDY_DTS = (5e-4, 2.5e-4, 1.25e-4)
FACE_LENGTH_M = 1.0  # Only area / length enters the face law: area_m2 is A/L itself.
BATH_PL = 1.0  # The held bath's nominal volume (only its composition enters).
SOLVER = "imex_ars222_face_electromigration@1"
FIELD_SOLVER = "capacitive_reduction_gauged_damped_newton@2"
LAWS = dict(
    state="membrane_entity_state@1",
    insertion="scheduled_membrane_insertion@1",
    lumen="restricted_cleft_lumen@1",
    injection="electrode_current_injection@1",
)


def rfull():
    """(R-full's egg with the record's P_old and A/L, the record, the declared inputs)."""
    from validation.division import cleft_egg_reference as ref

    d = ref.load_declared()
    record = json.loads(RECORD.read_text())
    egg = ref.build(
        d,
        ref.scalar_values(d),
        p_old=float(record["p_old_m_s"]),
        a_over_l=float(record["a_over_l_m"]),
    )
    return egg, record, d


def pulses(egg, end):
    """[(k, start, stop, current)] of every pulse starting before end (R-full's Pulses)."""
    p, rows, k = egg.pulses, [], 0
    while p.onset(k) < end:
        rows.append((k, p.onset(k), p.onset(k) + p.duration_s, p.sign(k) * p.amplitude_A))
        k += 1
    return rows


def definition(dt=JUDGED_DT, *, end=None):
    """The engine egg (R-full's) as a resolved_pump_composite@1 definition (raw)."""
    from cells.core import pump_composite_spec as cs
    from cells.processes.electrochemistry import CHARGE_PER_FMOL
    from validation.division import cleft_egg_reference as ref

    egg, _, d = rfull()
    end = float(d["time"]["horizon_s"]) if end is None else end

    def grid(t):  # Every scheduled time an exact multiple of dt.
        return round(t / dt) * dt

    ids, z = list(ref.SPECIES), dict(zip(ref.SPECIES, ref.Z, strict=True))
    volume_pL = egg.cytosol_volume_m3 * 1e15
    inside = {s: c * volume_pL for s, c in zip(ids, egg.cytosol_mM, strict=True)}
    _, _, v0 = ref.initial_state(egg)  # R-full's zero-current potential.
    background = egg.old_capacitance_F * v0 / CHARGE_PER_FMOL - math.fsum(
        z[s] * inside[s] for s in ids
    )
    bath_mM = dict(zip(ids, egg.bath_mM, strict=True))
    bath = {s: c * BATH_PL for s, c in bath_mM.items()}
    area_on = egg.activation_area_m2
    cleft_pL = 0.5e15 * egg.gap_width_m * area_on  # w A_on / 2.
    cleft = {s: c * cleft_pL for s, c in bath_mM.items()}  # At bath composition, uncharged.
    always = [dict(time=0.0, availability=1.0)]
    times = {0.0, end}
    for _, start, _, _ in pulses(egg, end):
        times |= {t for t in (start, start + egg.pulses.sample_s) if t <= end}
    raw = dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=egg.temperature_K,
            species=[dict(id=s, valence=z[s]) for s in ids],
            cells=[
                dict(
                    id="egg",
                    volume_pL=volume_pL,
                    initial_amount_fmol=inside,
                    fixed_charge_equivalent_fmol=background,
                    initial_charge_C=CHARGE_PER_FMOL
                    * math.fsum((background, *(z[s] * inside[s] for s in ids))),
                )
            ],
            extracellular=[
                dict(
                    id="steinberg",
                    volume_pL=BATH_PL,
                    initial_amount_fmol=bath,
                    fixed_charge_equivalent_fmol=-math.fsum(z[s] * bath[s] for s in ids),
                    initial_charge_C=0.0,
                    reservoir=True,
                    boundary_potential_V=0.0,
                ),
                dict(
                    id="cleft",
                    volume_pL=cleft_pL,
                    initial_amount_fmol=cleft,
                    fixed_charge_equivalent_fmol=-math.fsum(z[s] * cleft[s] for s in ids),
                    initial_charge_C=0.0,
                    reservoir=False,
                    boundary_potential_V=0.0,
                ),
            ],
            membranes=[
                dict(
                    id="old_membrane",
                    inside="egg",
                    outside="steinberg",
                    area_m2=egg.old_area_m2,
                    capacitance_F=egg.old_capacitance_F,
                    permeability_m_per_s={
                        s: egg.p_old * w for s, w in zip(ids, egg.old_relative, strict=True)
                    },
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                ),
                dict(
                    id="new_membrane",
                    inside="egg",
                    outside="cleft",
                    area_m2=area_on,
                    capacitance_F=egg.new_specific_capacitance_F_m2 * area_on,
                    permeability_m_per_s=dict(zip(ids, egg.new_permeability, strict=True)),
                    law="constant_field@1",
                    pump=None,
                    calcium_pump=None,
                ),
            ],
            junctions=[],
            faces=[
                dict(
                    id="access",
                    sender="cleft",
                    receiver="steinberg",
                    area_m2=egg.a_over_l_m * FACE_LENGTH_M,
                    length_m=FACE_LENGTH_M,
                    diffusivity_m2_per_s=dict(zip(ids, egg.access_D, strict=True)),
                    law="logmean_electrodiffusion@1",
                )
            ],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=[],
        ),
        experiment=dict(
            end_time=end,
            observation_times=sorted({grid(t) for t in times}),
            membrane_controls=[
                dict(membrane_id=m, schedule=json.loads(json.dumps(always)))
                for m in ("old_membrane", "new_membrane")
            ],
            junction_controls=[],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[],
        ),
        execution=dict(
            dt=dt,
            capacity=1,
            extracellular_capacity=2,
            membrane_capacity=2,
            edge_capacity=0,
            face_capacity=1,
            channel_capacity=0,
            backend="cpu",
            jit=True,
            precision="float64",
            solver=SOLVER,
            field_solver=FIELD_SOLVER,
            max_steps=int(math.ceil(end / dt)) + 8,
            max_trace_bytes=2**33,
            material_balance_atol_fmol={s: 1e-10 for s in ids},
        ),
    )
    out = cs.frozen_definition(raw)
    carriers = dict(d["rm_definition"]["injected_carrier_fractions"])
    assert (carriers["K"], carriers["Cl"]) == (egg.pulses.carrier_K, egg.pulses.carrier_Cl)
    assert egg.new_faces == "lumen" and not egg.extended  # The registered Model, no arm.
    (onset, rate), *rest = egg.schedule
    assert not rest and onset == egg.onset_s  # The default (uniform) schedule only (plan §6).
    out["model"]["operators"] = [
        dict(law=LAWS["state"], populations=[]),
        dict(
            law=LAWS["insertion"],
            patches=[
                dict(
                    membrane_id="new_membrane",
                    specific_capacitance_F_per_m2=egg.new_specific_capacitance_F_m2,
                    population_densities_per_m2={},
                )
            ],
        ),
        dict(
            law=LAWS["lumen"],
            lumens=[dict(node_id="cleft", source_id="steinberg", gap_width_m=egg.gap_width_m)],
        ),
        dict(law=LAWS["injection"], electrodes=[dict(cell_id="egg", carriers=carriers)]),
    ]
    out["experiment"]["insertion_controls"] = [
        dict(
            membrane_id="new_membrane",
            onset_time=grid(onset),
            schedule=[
                dict(time=0.0, rate_m2_per_s=0.0),
                dict(time=grid(onset), rate_m2_per_s=rate),
            ],
        )
    ]
    schedule = []
    for _, start, stop, current in pulses(egg, end):
        schedule.append(dict(time=grid(start), current_A=current))
        if stop < end:
            schedule.append(dict(time=grid(stop), current_A=0.0))
    out["experiment"]["injection_controls"] = [dict(cell_id="egg", schedule=schedule)]
    return out


# ------------------------------------------------------------------ compare


def _row(engine, reference):
    a, b = (list(v) if isinstance(v, list | tuple) else [v] for v in (engine, reference))
    if any(isinstance(x, str) for x in (*a, *b)):
        return dict(engine=engine, rfull=reference, equal=a == b)
    worst = max(abs(x - y) / max(abs(y), 1e-300) for x, y in zip(a, b, strict=True))
    return dict(engine=engine, rfull=reference, max_relative_difference=worst)


def compare(raw):
    """Every field of the engine definition against R-full's egg ({name: row})."""
    from validation.division import cleft_egg_reference as ref

    egg, _, d = rfull()
    model, experiment, ids = raw["model"], raw["experiment"], list(ref.SPECIES)
    cell = model["cells"][0]
    bath, cleft = model["extracellular"]
    old, new = model["membranes"]
    face = model["faces"][0]
    ops = {op["law"]: op for op in model["operators"]}
    patch = ops[LAWS["insertion"]]["patches"][0]
    lumen_entry = ops[LAWS["lumen"]]["lumens"][0]
    electrode = ops[LAWS["injection"]]["electrodes"][0]
    (control,) = experiment["insertion_controls"]
    onset, rate = control["onset_time"], control["schedule"][-1]["rate_m2_per_s"]
    j1, horizon = float(d["time"]["j1_s"]), float(d["time"]["horizon_s"])
    _, _, v0 = ref.initial_state(egg)
    volume, cleft_volume = cell["volume_pL"], cleft["volume_pL"]
    # R-full's lumen at activation: bath Na and K, zero charge (simulate's activation).
    vc = egg.gap_width_m * egg.area(egg.onset_s) / 2.0
    lumen_on = [egg.bath_mM[0] * vc / ref.FMOL, egg.bath_mM[1] * vc / ref.FMOL]
    lumen_on.append(lumen_on[0] + lumen_on[1] - 0.0)
    end = experiment["end_time"]
    engine_pulses = [
        (c["time"], c["current_A"]) for c in experiment["injection_controls"][0]["schedule"]
    ]
    rfull_pulses, observed = [], {0.0, end}
    for _, start, stop, current in pulses(egg, end):
        rfull_pulses.append((start, current))
        if stop < end:
            rfull_pulses.append((stop, 0.0))
        observed |= {t for t in (start, start + egg.pulses.sample_s) if t <= end}  # Rm's samples.
    rows = dict(
        temperature_K=(model["temperature_K"], egg.temperature_K),
        cytosol_volume_m3=(volume * 1e-15, egg.cytosol_volume_m3),
        cytosol_mM_activity_basis=(
            [cell["initial_amount_fmol"][s] / volume for s in ids],
            list(egg.cytosol_mM),
        ),
        initial_potential_V=(cell["initial_charge_C"] / old["capacitance_F"], v0),
        bath_mM_activity_basis=(
            [bath["initial_amount_fmol"][s] / bath["volume_pL"] for s in ids],
            list(egg.bath_mM),
        ),
        bath_potential_V=(bath["boundary_potential_V"], 0.0),
        lumen_onset_mM_activity_basis=(
            [cleft["initial_amount_fmol"][s] / cleft_volume for s in ids],
            [x * ref.FMOL / vc for x in lumen_on],
        ),
        lumen_onset_charge_C=(cleft["initial_charge_C"], 0.0),
        old_area_m2_folded=(old["area_m2"], egg.old_area_m2),
        old_capacitance_F=(old["capacitance_F"], egg.old_capacitance_F),
        old_permeability_m_s_per_area=(
            [old["permeability_m_per_s"][s] for s in ids],
            [egg.p_old * w for w in egg.old_relative],
        ),
        old_relative=(
            [old["permeability_m_per_s"][s] / egg.p_old for s in ids],
            list(egg.old_relative),
        ),
        new_activation_area_m2=(new["area_m2"], egg.area(egg.onset_s)),
        new_capacitance_at_onset_F=(
            new["capacitance_F"],
            egg.new_specific_capacitance_F_m2 * egg.area(egg.onset_s),
        ),
        new_specific_capacitance_F_m2=(
            patch["specific_capacitance_F_per_m2"],
            egg.new_specific_capacitance_F_m2,
        ),
        new_permeability_m_s_per_area=(
            [new["permeability_m_per_s"][s] for s in ids],
            list(egg.new_permeability),
        ),
        access_m3_s=(
            [face["diffusivity_m2_per_s"][s] * face["area_m2"] / face["length_m"] for s in ids],
            [egg.a_over_l_m * D for D in egg.access_D],
        ),
        access_law=(face["law"], {"logmean": "logmean_electrodiffusion@1"}[egg.access_law]),
        gap_width_m=(lumen_entry["gap_width_m"], egg.gap_width_m),
        lumen_onset_volume_m3=(cleft_volume * 1e-15, vc),
        onset_s=(onset, egg.onset_s),
        insertion_rate_m2_s=(rate, egg.schedule[0][1]),
        area_at_j1_m2=(new["area_m2"] + rate * (j1 - onset), egg.area(j1)),
        area_at_horizon_m2=(new["area_m2"] + rate * (horizon - onset), egg.area(horizon)),
        pulse_times_s=([t for t, _ in engine_pulses], [t for t, _ in rfull_pulses]),
        pulse_currents_A=([c for _, c in engine_pulses], [c for _, c in rfull_pulses]),
        pulse_count=(sum(1 for _, c in engine_pulses if c != 0.0), len(pulses(egg, end))),
        carriers=(
            [electrode["carriers"]["K"], electrode["carriers"]["Cl"]],
            [egg.pulses.carrier_K, egg.pulses.carrier_Cl],
        ),
        observation_times_s=(experiment["observation_times"], sorted(observed)),
        cytosol_charge_anchor_C=(cell["initial_charge_C"], egg.old_capacitance_F * v0),
    )
    return {name: _row(*pair) for name, pair in rows.items()}


DECLARED_DIFFERENCES = dict(
    numerics=(
        "R-full integrates one ODE (Radau, rtol 1e-10); the engine takes IMEX ARS(2,2,2) steps "
        "with insertion, the lumen fill and injection as exact half-steps around them. The fill "
        "added after a step's last insertion half-step waits for the next step's first half "
        "(a splitting error, part of the step term)."
    ),
    onset=(
        "Both open the furrow uncharged with the lumen at bath composition. At a step far longer "
        "than the access time constant the engine's IMEX step leaves the charging heat "
        "1/2 C_on Vm^2 (about 3e-4 pJ) unbooked (S3 prerequisite (a))."
    ),
    lumen_chloride=(
        "R-full sets the lumen's Cl at activation from zero charge (Na + K); the engine declares "
        "the bath's Cl activity. They are one float: the bath's Na + K - Cl is 0.0 in float64 "
        "(its exact sum is -1.7e-15 mM, which R-full's supply_charge carries)."
    ),
    lumen_energy=(
        "R-full books only the insertion heat; the engine also books the fill's supply work, the "
        "fluid's volume work and the mixing heat (restricted_cleft_lumen@1), which change no state."
    ),
    units=(
        "The engine holds volumes in pL and amounts in fmol (m^3 x 1e15); relative conversion "
        "differences of order 1e-16."
    ),
    event_times=(
        "Event and observation times are k dt (round(t / dt) dt); at some steps a pulse edge "
        "differs from R-full's time by one ulp (about 2e-16 relative)."
    ),
    charge_anchor=(
        "The cytosol's charge anchor is F (background + sum z n), an exact sum of the rounded "
        "inventories (egg_scale_smoke's consistent anchor: @3's definition check allows 1e-20 C "
        "between anchor and inventory). The background, about -4.7e7 fmol, is stored to its "
        "ulp while the cell's charge is about -3.3 fmol, so the anchor, and the initial potential "
        "anchor / C_old, carry R-full's C_old v0 to 2 ulp(background) / |charge|, about 5e-9 "
        "relative (here 3.9e-11, 4e-13 V)."
    ),
)
ANCHORED_ROWS = ("initial_potential_V", "cytosol_charge_anchor_C")


def anchor_granularity(raw):
    """2 ulp(background) / |background + sum z n|: the cytosol anchor's relative precision."""
    import numpy as np

    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    cell = raw["model"]["cells"][0]
    charge = cell["initial_charge_C"] / CHARGE_PER_FMOL
    return float(2 * np.spacing(abs(cell["fixed_charge_equivalent_fmol"])) / abs(charge))


def compare_report(raw, *, tolerance=1e-12):
    """compare's rows: matched within tolerance, or within a declared bound with its reason."""
    rows = compare(raw)
    bound = dict.fromkeys(ANCHORED_ROWS, anchor_granularity(raw))
    worst = {
        k: r["max_relative_difference"] for k, r in rows.items() if "max_relative_difference" in r
    }
    declared = {
        k: dict(bound=bound[k], reason="charge_anchor")
        for k in bound
        if tolerance < worst[k] <= bound[k]
    }
    mismatched = sorted(
        [k for k, v in worst.items() if not v <= max(tolerance, bound.get(k, 0.0))]
        + [k for k, r in rows.items() if r.get("equal") is False]
    )
    return dict(
        tolerance_relative=tolerance,
        fields=len(rows),
        matched=len(rows) - len(mismatched) - len(declared),
        declared=declared,
        mismatched=mismatched,
        worst_relative_difference=max(worst.values()),
        differences=rows,
        declared_differences=DECLARED_DIFFERENCES,
    )


# ------------------------------------------------------------------ step checks


def check(dts=STUDY_DTS):
    """The definition at each step: parsed, its explicit-rate bounds, and the runner's step
    checks (core/grid's chunks call the same bound checks), accepted or refused."""
    import numpy as np

    from cells.core import pump_composite_spec as cs
    from cells.core import surface_pump_v3_spec as ionic_spec
    from cells.core.specs import ConfigError, parse_spec
    from cells.models import surface_pump as first
    from cells.models.operators import membrane_insertion as insertion
    from cells.models.registry import get_model

    cases = []
    for dt in dts:
        case = dict(dt=dt)
        try:
            spec = parse_spec(definition(dt))
        except ConfigError as error:  # Kept: a refusal is the result.
            cases.append(dict(case, verdict="refused at definition", refusal=str(error)))
            continue
        model = get_model(spec.model)
        check_spec = spec
        for op, declaration, schedule in cs.entries(spec):
            check_spec = op.inner_check_spec(check_spec, spec, declaration, schedule)
        largest = first.explicit_rate_bound(ionic_spec.projection(cs.projection(check_spec)))
        schedule = next(s for op, _, s in cs.entries(spec) if op.LAW_ID == LAWS["insertion"])
        before = first.explicit_rate_bound(insertion.pre_onset_spec(spec, schedule))
        case.update(
            explicit_rate_largest_area_per_s=float(largest),
            dt_x_rate_largest_area=float(dt * largest),
            explicit_rate_before_onset_per_s=float(before),
            dt_x_rate_before_onset=float(dt * before),
            explicit_step_bound=first.EXPLICIT_STEP_BOUND,
            steps=int(round(spec.experiment.end_time / dt)),
        )
        try:
            model.bind_step_checks(spec)(np.array([dt]))
            case["verdict"] = "accepted"
        except ConfigError as error:  # Kept: a refusal is the result.
            case.update(verdict="refused at step check", refusal=str(error))
        cases.append(case)
    return dict(cases=cases)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("compare", "check"):
        sub.add_parser(name).add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.action == "compare":
        import jax

        from cells.core.specs import parse_spec

        jax.config.update("jax_enable_x64", True)
        raw = definition()
        parse_spec(raw)  # The composite's definition checks (raises on a refusal).
        result = dict(status=STATUS, **compare_report(raw), definition=raw)
    else:
        import jax

        jax.config.update("jax_enable_x64", True)
        result = dict(status=STATUS, **check())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1, default=float) + "\n")
    print(args.action, "written", args.output)


if __name__ == "__main__":
    main()
