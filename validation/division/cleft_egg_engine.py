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
are R-full's times to one ulp (compare reports it). Observations: every pulse's front edge and
its sample 1 s later, through the horizon.

Quantities (plan §4), the same rule in engine and R-full: Q1 V at the front edge of pulse 180
(J1), Q2 Rm of the pair (179, 180), Q3 Rm1 of the pair (0, 1, reported only), Q4 V at the front
edge of every pulse 0 to 210, Q5 the lumen's K and Na at J1 (mM, activity basis), which the
engine's observer reads filled to the area at that time, as R-full defines the lumen.

Actions (python -m validation.division.cleft_egg_engine ACTION --output FILE):
  compare      every field of the definition against R-full's build, with the declared
               differences
  check        the definition parsed at the step study's steps (0.5, 0.25 and 0.125 ms), with
               the runner's step checks (accepted or refused) and the explicit-rate bounds
  probe [--dt] the bounded ledger probe: through the onset plus 1e5 steps, every row's device
               checks and its electrode, reservoir-work, energy and fill residuals against their
               bounds; refused steps counted; no Q quantity
  admit        the study's admission at each of its steps (plan_vector_windows with the
               study's batch and policy); no step is taken
  study --dt   a development engine run in vector windows with device checks: Q1-Q5
  terms --studies F2dt Fdt Fdt/2
               each quantity's step term at the judged dt and its observed order
  reference    R-full's Q1-Q5 under the registered defaults and its reference term per quantity
  fill --terms F --reference F [--studies F ...]
               the protocol draft with its values and development observations (still PROPOSED)
  judge        the judged run: a registered protocol (status beginning "registered") and a clean
               execution snapshot only
study, reference and judge wait for the lead's approval (plan §5, steps 4-6); they follow
injection_rm1.py's. The protocol is validation/division/cleft_egg_protocol.json (PROPOSED).
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
        "anchor / C_old, carry R-full's C_old v0 to 2 ulp(background) / |charge|, 1.1e-9 "
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


# ------------------------------------------------------------------ the bounded ledger probe

PROBE_LEDGERS = ("electrode", "reservoir_work", "energy", "lumen_fill")
PROBE_STEPS_AFTER_ONSET = 100_000
PROBE_WINDOW = 89_000  # 20 windows of the 1.78e6 steps at 0.25 ms.


def probe(dt=JUDGED_DT, after=PROBE_STEPS_AFTER_ONSET, width=PROBE_WINDOW, chunk=4096):
    """The bounded ledger probe (the lead, 13 November).

    The definition through the onset plus `after` steps at dt, rolled out in windows by the
    runner's own checked step (runner._compiled_discrete_rollout, one compile per window
    shape). Every row gets the composite's device checks and its electrode, reservoir-work,
    energy and fill residuals against their bounds (the composite's balances, magnitudes and
    ledger_limits, as egg_scale_smoke.device_rows does). Refused steps are counted, not raised,
    and the probe stops after the first window that has one. No observation is taken and no
    Q quantity is computed.
    """
    import time

    import jax
    import jax.numpy as jnp
    import numpy as np

    from cells.core import runner
    from cells.core.schedule import control_values
    from cells.core.specs import parse_spec
    from cells.core.state import initialise
    from cells.models.registry import get_model

    started = time.perf_counter()
    egg, _, _ = rfull()
    onset_step = round(egg.onset_s / dt)
    spec = parse_spec(definition(dt, end=(onset_step + after) * dt))
    model = get_model(spec.model)
    times = runner.timeline(spec)
    total = len(times) - 1
    checkpoint = initialise(spec)
    state, layout = checkpoint.state, checkpoint.layout
    parameters = model.parameters(spec, layout)
    p = model.initial_values(spec)[1]
    constants = model.device_check_constants(spec)
    picked = [list(model.LEDGERS).index(k) for k in PROBE_LEDGERS]

    def one(previous, row, steps):
        failed, _ = model.device_checks(previous, row, p, constants, steps)
        values = list(model.device_balances(row, p).values())
        _, bounds = model.ledger_limits(
            row,
            p,
            constants.material_atol,
            constants.energy_rtol,
            steps=steps,
            magnitudes=model.magnitudes(row, p, xp=jnp),
            xp=jnp,
        )
        worst = []
        for k in picked:  # (ratio, |residual|, bound) at each ledger's worst entry.
            value = jnp.ravel(jnp.abs(values[k]))
            bound = jnp.ravel(jnp.broadcast_to(bounds[k], jnp.shape(values[k])))
            ratio = value / bound
            i = jnp.argmax(ratio)
            worst.append(jnp.stack([ratio[i], value[i], bound[i]]))
        return failed, jnp.stack(worst)

    check = jax.jit(jax.vmap(one))
    compiled, windows = {}, []
    refused, first_refused, failing, failed_checks = 0, None, 0, set()
    best = np.zeros((len(PROBE_LEDGERS), 3))
    best_time = np.zeros(len(PROBE_LEDGERS))
    for start in range(0, total, width):
        stop = min(total, start + width)
        window = times[start : stop + 1]
        steps = runner.integration_steps(spec, window)
        args = (state, steps, control_values(spec, window[:-1]), parameters, layout.active)
        if len(steps) not in compiled:
            compiled[len(steps)] = runner._compiled_discrete_rollout.lower(
                *args, model.checked_step
            ).compile()
        final, history, valid = compiled[len(steps)](*args)
        bad = np.flatnonzero(~np.asarray(valid))
        refused += len(bad)
        if len(bad) and first_refused is None:
            first_refused = float(window[bad[0]])
        history = jax.tree.map(np.asarray, history)
        previous = jax.tree.map(
            lambda s, h: np.concatenate((np.asarray(s)[None], h[:-1])), state, history
        )
        window_worst = np.zeros(len(PROBE_LEDGERS))
        for a in range(0, len(steps), chunk):
            b = min(len(steps), a + chunk)
            failed, worst = (
                np.asarray(x)
                for x in check(
                    jax.tree.map(lambda v, a=a, b=b: jnp.asarray(v[a:b]), previous),
                    jax.tree.map(lambda v, a=a, b=b: jnp.asarray(v[a:b]), history),
                    jnp.arange(start + a + 1, start + b + 1),
                )
            )
            rows = np.flatnonzero(failed.any(axis=1))
            failing += len(rows)
            for r in rows:
                failed_checks |= {
                    c for c, f in zip(model.DEVICE_CHECKS, failed[r], strict=True) if f
                }
            for j in range(len(PROBE_LEDGERS)):
                r = int(np.argmax(worst[:, j, 0]))
                window_worst[j] = max(window_worst[j], worst[r, j, 0])
                if worst[r, j, 0] > best[j, 0]:
                    best[j], best_time[j] = worst[r, j], float(window[a + r + 1])
        windows.append(
            dict(
                end_s=float(window[-1]),
                max_ratio=dict(zip(PROBE_LEDGERS, window_worst.tolist(), strict=True)),
            )
        )
        state = final
        if len(bad):
            break
    return dict(
        dt=dt,
        onset_s=float(times[onset_step]),
        end_s=float(times[-1]),
        steps=total,
        steps_after_onset=total - onset_step,
        refused_steps=refused,
        first_refused_time_s=first_refused,
        device_failing_rows=failing,
        device_failed_checks=sorted(failed_checks),
        residual_against_bound={
            name: dict(max_ratio=float(r), residual=float(v), bound=float(b), time_s=float(t))
            for name, (r, v, b), t in zip(PROBE_LEDGERS, best, best_time, strict=True)
        },
        windows=windows,
        wall_s=time.perf_counter() - started,
    )


# ------------------------------------------------------------------ quantities (plan §4)


def pulse_samples(times, values, egg):
    """({pulse k: value at its front edge}, {k: value 1 s later}) from (time, value) rows."""
    p, front, sample = egg.pulses, {}, {}
    for t, value in zip(times, values, strict=True):
        k = round((t - p.first_onset_s) / p.period_s)
        if abs(t - p.onset(k)) < 1e-6:
            front[k] = value
        elif abs(t - p.onset(k) - p.sample_s) < 1e-6:
            sample[k] = value
    return front, sample


def quantities(front, sample, lumen_at_j1, egg, d):
    """Q1-Q5 by the pulse protocol as rm_definition defines them, for engine and R-full alike.

    front, sample: V at each pulse's front edge and 1 s later; lumen_at_j1: {species: mM} of the
    lumen at J1 (the engine's observer reads it filled to the area at that time, as R-full).
    """
    rm, p = d["rm_definition"], egg.pulses

    def chord(k):
        return abs(sample[k] - front[k])

    def rm_pair(a, b):  # Rm(k) = (|dV_(k-1)| + |dV_k|) / (2 x 3e-8 A).
        return (chord(a) + chord(b)) / (2 * p.amplitude_A)

    last = max(front)
    return dict(
        Q1_em_at_j1_V=front[rm["j1_em_pulse"]],
        Q2_rm_at_j1_ohm=rm_pair(*rm["j1_pulse_pair"]),
        Q3_rm1_ohm=rm_pair(*rm["rm1_pulse_pair"]),
        Q4_em_trajectory_V=[front[k] for k in range(last + 1)],
        Q5_lumen_at_j1_mM={s: lumen_at_j1[s] for s in ("K", "Na")},
    )


QUANTITIES = ("Q1_em_at_j1_V", "Q2_rm_at_j1_ohm", "Q3_rm1_ohm", "Q4_em_trajectory_V")
JUDGED = (
    "Q1_em_at_j1_V",
    "Q2_rm_at_j1_ohm",
    "Q4_em_trajectory_V",
    "Q5_lumen_K_mM",
    "Q5_lumen_Na_mM",
)


def flat(q):
    """{name: float or [float]}: Q5 split into K and Na."""
    out = {k: q[k] for k in QUANTITIES}
    out |= {f"Q5_lumen_{s}_mM": q["Q5_lumen_at_j1_mM"][s] for s in ("K", "Na")}
    return out


def distance(a, b):
    """|a - b|, or its maximum over pulses for the trajectory."""
    if isinstance(a, list):
        return max(abs(x - y) for x, y in zip(a, b, strict=True))
    return abs(a - b)


# ------------------------------------------------------------------ the study (not run yet)

STUDY_WINDOW = 20_000


OBSERVED = ("times", "membrane_voltage_V", "lumen_concentration_mM")


def study_batch(spec, window_steps=STUDY_WINDOW):
    """The study's one-world vector-window batch and window policy, admission bounds included."""
    from cells.core.batch import BatchSpec, WorldSpec
    from cells.core.windows import WindowPolicy

    work = 2 * spec.execution.max_steps + 10**6
    batch = BatchSpec((WorldSpec(1, spec),), 1, work, 2**31)
    return batch, WindowPolicy(window_steps, "checkpoints")


def windowed_observations(spec, *, columns=OBSERVED, window_steps=STUDY_WINDOW):
    """One world run in vector windows with device checks on every row (core/vector_windows):
    the named observation columns at every requested time, stacked in time order, with the
    world's device diagnostics, the run's timings and the world's final checkpoint. run()
    cannot hold a 2100 s history."""
    import numpy as np

    from cells.core.vector_windows import run_vector_windowed

    found = []

    def sink(window):
        found.extend(window.observations.values())

    batch, policy = study_batch(spec, window_steps)
    result = run_vector_windowed(batch, policy, sink=sink)
    stacked = {k: np.concatenate([np.asarray(getattr(f, k)) for f in found]) for k in columns}
    world = result.worlds[1]
    return stacked, dict(world.diagnostics), dict(result.timings), world.final


def ledger_ratios(spec, state, steps, names=PROBE_LEDGERS):
    """Each named ledger's worst entry at one row, {name: (|residual|, bound, ratio)}, by the
    device checks' own functions: the composite's device balances, magnitudes and ledger
    limits, with steps the row's accepted-step count (the study's horizon: its final row)."""
    import jax.numpy as jnp
    import numpy as np

    from cells.models.registry import get_model

    model = get_model(spec.model)
    p = model.initial_values(spec)[1]
    constants = model.device_check_constants(spec)
    row = type(state)(*(jnp.asarray(v) for v in state))
    values = model.device_balances(row, p)
    _, bounds = model.ledger_limits(
        row,
        p,
        constants.material_atol,
        constants.energy_rtol,
        steps=steps,
        magnitudes=model.magnitudes(row, p, xp=jnp),
        xp=jnp,
    )
    out = {}
    for name in names:
        residual = np.abs(np.asarray(values[name]))
        bound = np.broadcast_to(np.asarray(bounds[list(model.LEDGERS).index(name)]), residual.shape)
        residual, bound = np.ravel(residual), np.ravel(bound)  # The bound shaped first, then both.
        i = int(np.argmax(residual / bound))
        out[name] = dict(
            residual=float(residual[i]), bound=float(bound[i]), ratio=float(residual[i] / bound[i])
        )
    return out


def admit(dts=STUDY_DTS, window_steps=STUDY_WINDOW):
    """The study's admission on the egg at each step: plan_vector_windows with the study's own
    batch and policy (the cohort limits, the window plan, and the whole clock's checks through
    core/grid's checked_grid). No step is taken and nothing is observed."""
    from cells.core.errors import NumericalError
    from cells.core.specs import ConfigError, parse_spec
    from cells.core.vector_windows import plan_vector_windows

    cases = []
    for dt in dts:
        spec = parse_spec(definition(dt))
        batch, policy = study_batch(spec, window_steps)
        case = dict(
            dt=dt,
            steps=int(round(spec.experiment.end_time / dt)),
            window_steps=window_steps,
            max_padded_steps=batch.max_padded_steps,
            max_working_bytes=batch.max_working_bytes,
        )
        try:
            plan = plan_vector_windows(batch, policy)
        except (ConfigError, NumericalError) as error:  # Kept: a refusal is the result.
            cases.append(dict(case, verdict="refused", refusal=str(error)))
            continue
        cases.append(
            dict(
                case,
                verdict="admitted",
                width=plan.width,
                control_rows=plan.control_rows,
                observation_rows=plan.observation_rows,
                estimated_working_bytes=plan.estimated_working_bytes,
                padded_step_bound=plan.padded_step_bound,
            )
        )
    return dict(cases=cases)


def study(dt, *, window_steps=STUDY_WINDOW, keep=None):
    """One development run of the study (plan §3-§4): the engine's Q1-Q5 at dt, from the old
    membrane's voltage and the observer's lumen at every observation time
    (windowed_observations), with the device checks' diagnostics and, at the horizon (the
    final row), the electrode, reservoir-work, energy and fill residuals against their
    bounds. keep: a folder for the run's observation rows, diagnostics and final checkpoint,
    written before any post-processing (cells.io.write_snapshot), so a later failure loses no
    run."""
    import time

    from cells.core.specs import parse_spec
    from validation.division import cleft_egg_reference as ref

    started = time.perf_counter()
    egg, _, d = rfull()
    raw = definition(dt)
    spec = parse_spec(raw)
    cleft = [c["id"] for c in raw["model"]["extracellular"]].index("cleft")
    old = [m["id"] for m in raw["model"]["membranes"]].index("old_membrane")
    stacked, diagnostics, timings, final = windowed_observations(spec, window_steps=window_steps)
    if keep is not None:  # The run's rows and final checkpoint, before any post-processing.
        import numpy as np

        from cells.io import write_snapshot

        keep = Path(keep)
        keep.mkdir(parents=True, exist_ok=True)
        np.savez(keep / "observations.npz", **stacked)
        (keep / "run.json").write_text(
            json.dumps(dict(dt=dt, diagnostics=diagnostics, timings=timings), default=float)
        )
        write_snapshot(keep / "final", spec, final)
    times = stacked["times"].tolist()
    voltages = stacked["membrane_voltage_V"][:, old].tolist()
    lumen = stacked["lumen_concentration_mM"][:, :, cleft].tolist()
    front, sample = pulse_samples(times, voltages, egg)
    j1 = float(d["time"]["j1_s"])
    row = min(range(len(times)), key=lambda i: abs(times[i] - j1))
    assert abs(times[row] - j1) < 1e-6
    at_j1 = dict(zip(ref.SPECIES, lumen[row], strict=True))
    return dict(
        dt=dt,
        quantities=quantities(front, sample, at_j1, egg, d),
        front_V=[front[k] for k in sorted(front)],
        sample_V=[sample[k] for k in sorted(sample)],
        lumen_at_j1_mM=at_j1,
        device_diagnostics=diagnostics,
        horizon=dict(
            time_s=float(final.time),
            steps=int(final.step_index),
            ledgers=ledger_ratios(spec, final.state, int(final.step_index)),
        ),
        timings=timings,
        wall_s=time.perf_counter() - started,
    )


STOP_CONDITION = (
    "stop and report (non-convergence under the plan's stop rule) if any judged quantity's step "
    "term fails to decrease from the (0.5, 0.25 ms) pair to the (0.25, 0.125 ms) pair; a step "
    "term that is 0 at both pairs does not stop (the lead, 13 November)"
)


def terms(studies, judged=JUDGED_DT):
    """The engine step term of each quantity at the judged pair (judged dt against judged / 2)
    and its observed order, log2(|Q(2 dt) - Q(dt)| / |Q(dt) - Q(dt / 2)|); for the trajectory,
    the maxima over pulses. studies: the study outputs at 2 dt, dt and dt / 2. The orders are
    reported for inspection; the registered stop condition (STOP_CONDITION) is evaluated."""
    import math

    by = {round(s["dt"], 12): flat(s["quantities"]) for s in studies}
    coarse, mid, fine = (by[round(x, 12)] for x in (2 * judged, judged, judged / 2))
    out = {}
    for name in mid:
        first, second = distance(coarse[name], mid[name]), distance(mid[name], fine[name])
        order = math.log2(first / second) if first > 0 and second > 0 else None
        out[name] = dict(
            step_term=second,
            coarse_difference=first,
            observed_order=order,
            step_term_decreases=second < first or first == second == 0,
            judged=name in JUDGED,
            # The engine's value at each step (the trajectory's 211 values stay in the studies).
            values=None
            if isinstance(mid[name], list)
            else {repr(k): v[name] for k, v in by.items()},
        )
    stop = sorted(k for k, v in out.items() if v["judged"] and not v["step_term_decreases"])
    return dict(
        judged_dt=judged,
        dts=sorted(by),
        terms=out,
        stop_condition=STOP_CONDITION,
        stop=bool(stop),
        non_converging=stop,
    )


def protocol_values(term_values, reference_values):
    """The protocol's values per quantity from terms and reference: the R-full reference, both
    terms, the observed order, the tolerance 3 x (engine step term + reference term) and, as a
    reported shared sensitivity outside the tolerance, the activation-area variant's |dQ|. The
    reference terms are formed here from the reference's rows (reference_terms_from_rows), so
    the rule is this module's whatever version wrote the file."""
    base, ref_terms, shared = reference_terms_from_rows(reference_values["rows"])
    out = {}
    for name, t in term_values["terms"].items():
        step, ref_term = t["step_term"], ref_terms[name]
        out[name] = dict(
            judged=t["judged"],
            reference=base[name],
            engine_step_term=step,
            engine_coarse_difference=t["coarse_difference"],
            observed_order=t["observed_order"],
            reference_term=ref_term,
            tolerance=3 * (step + ref_term),
            shared_sensitivity=shared[name],
            engine_values_by_dt_s=t.get("values"),
        )
    return out


def development_observations(term_values, reference_values, studies=()):
    """Engine minus R-full at each step of the study (the trajectory: its maximum over pulses),
    and the fine-pair order against R-full, log2(|E(dt) - R| / |E(dt / 2) - R|) at the judged
    pair: information for the protocol's reader, not a verdict."""
    import math

    base, _, _ = reference_terms_from_rows(reference_values["rows"])
    judged = term_values["judged_dt"]
    by = {round(s["dt"], 12): flat(s["quantities"]) for s in studies}
    out = {}
    for name, t in term_values["terms"].items():
        values = t.get("values")
        if values is not None:
            engine = {float(k): v for k, v in values.items()}
        else:
            engine = {dt: q[name] for dt, q in by.items()}
        if not engine:
            continue
        signed = not isinstance(base[name], list)
        difference = {
            repr(dt): (v - base[name]) if signed else distance(v, base[name])
            for dt, v in sorted(engine.items(), reverse=True)
        }
        mid, fine = (engine.get(round(x, 12)) for x in (judged, judged / 2))
        order = None
        if mid is not None and fine is not None:
            a, b = distance(mid, base[name]), distance(fine, base[name])
            order = math.log2(a / b) if a > 0 and b > 0 else None
        out[name] = dict(engine_minus_reference=difference, fine_pair_order_against_reference=order)
    return out


# ------------------------------------------------------------------ R-full's reference (not run)

# The reference term bounds R-full's own numerical error: its integrator variants only (the
# lead's ruling of 13 November). The activation area is R-full's and the engine's alike, so its
# variant measures a sensitivity both share: reported per quantity, outside the tolerance.
REFERENCE_VARIANTS = ("radau_rtol_1e-8", "bdf_rtol_1e-10", "lsoda_rtol_1e-10")
SHARED_SENSITIVITIES = ("activation_1e-10_m2",)
DEFAULT_VARIANT = "radau_rtol_1e-10"


def reference_terms_from_rows(rows):
    """(R-full's default Q, the reference term per quantity over REFERENCE_VARIANTS, {quantity:
    {shared variant: |dQ|}}) from the reference action's rows."""
    base = flat(rows[DEFAULT_VARIANT]["quantities"])
    terms = {
        name: max(
            distance(flat(rows[v]["quantities"])[name], base[name]) for v in REFERENCE_VARIANTS
        )
        for name in base
    }
    shared = {
        name: {
            v: distance(flat(rows[v]["quantities"])[name], base[name]) for v in SHARED_SENSITIVITIES
        }
        for name in base
    }
    return base, terms, shared


def rfull_quantities(egg, d, **kwargs):
    """R-full's Q1-Q5 to the horizon (simulate, Radau rtol 1e-10 unless kwargs say otherwise)."""
    from validation.division import cleft_egg_reference as ref

    j1, horizon = float(d["time"]["j1_s"]), float(d["time"]["horizon_s"])
    run = ref.simulate(egg, horizon, record=(j1,), **kwargs)
    at_j1 = dict(zip(ref.SPECIES, run.at[j1]["lumen_mM"], strict=True))
    q = quantities(dict(run.onset_V), dict(run.sample_V), at_j1, egg, d)
    return q, dict(steps=run.steps, wall_s=run.wall_s)


def reference():
    """R-full's quantities under the registered defaults (Radau rtol 1e-10, the record's
    calibration) and its reference term per quantity: the largest |dQ| over Radau rtol 1e-8 and
    BDF and LSODA at rtol 1e-10 (REFERENCE_VARIANTS). The activation area 1e-10 m2, which J1's
    reference_numerics included, is run too and reported as a shared sensitivity (the variants
    as the record's part_record forms them). Q1, Q2 and Q3 are checked against the record."""
    from dataclasses import replace

    from validation.division import cleft_egg_reference as ref

    egg, record, d = rfull()
    values = ref.scalar_values(d)
    small = replace(egg, activation_area_m2=1e-10)
    small = replace(
        small,
        schedule=ref.uniform_schedule(
            egg.onset_s, values["new_membrane_area_at_j1_m2"], 1e-10, float(d["time"]["j1_s"])
        ),
    )
    default, info = rfull_quantities(egg, d)
    rows = {DEFAULT_VARIANT: dict(quantities=default, **info)}
    for label, e, kwargs in (
        ("radau_rtol_1e-8", egg, dict(rtol=1e-8)),
        ("bdf_rtol_1e-10", egg, dict(method="BDF")),
        ("lsoda_rtol_1e-10", egg, dict(method="LSODA")),
        ("activation_1e-10_m2", small, {}),
    ):
        q, info = rfull_quantities(e, d, **kwargs)
        rows[label] = dict(quantities=q, **info)
    base, reference_terms, shared = reference_terms_from_rows(rows)
    return dict(
        reference=base,
        reference_terms=reference_terms,
        shared_sensitivities=shared,
        rows=rows,
        record_check=dict(
            em_V=(base["Q1_em_at_j1_V"], record["prediction_of_record_V"]),
            rm_at_j1_ohm=(base["Q2_rm_at_j1_ohm"], record["rm_at_j1_ohm"]),
            rm1_ohm=(base["Q3_rm1_ohm"], record["rm1_ohm"]),
        ),
    )


# ------------------------------------------------------------------ the judged run (not run)

PROTOCOL = ROOT / "validation/division/cleft_egg_protocol.json"


def judged_run_refusal(protocol, root=ROOT):
    """Why a judged run may not start (None: it may): an unregistered protocol, or a source
    that is not a clean execution snapshot (validation/source_snapshot.py), as injection_rm1's
    judge refuses them."""
    import hashlib

    status = protocol.get("status")
    if not (isinstance(status, str) and status.startswith("registered")):
        return "the S3 protocol is not registered (its status does not begin 'registered')"
    manifest = Path(root) / "SNAPSHOT.json"
    if not manifest.exists():
        return "a judged run comes from a clean execution snapshot of main, not a checkout"
    snapshot = json.loads(manifest.read_text())
    clean = snapshot.get("patch_sha256") == hashlib.sha256(b"").hexdigest()
    if snapshot.get("status") != "complete" or not clean:
        return "the execution snapshot is incomplete or carries uncommitted changes"
    return None


def verdicts(engine, protocol):
    """Each quantity's |engine - reference| against its registered tolerance."""
    out = {}
    for name, entry in protocol["values"].items():
        difference = distance(engine[name], entry["reference"])
        out[name] = dict(
            engine=engine[name] if not isinstance(engine[name], list) else None,
            difference=difference,
            tolerance=entry["tolerance"],
            judged=entry["judged"],
            verdict="pass" if difference <= entry["tolerance"] else "fail",
        )
    judged = [v["verdict"] for v in out.values() if v["judged"]]
    return out, "pass" if judged and all(v == "pass" for v in judged) else "fail"


def judge(protocol_path=PROTOCOL):
    """The judged run of a registered protocol, once, at its judged dt, with its verdict."""
    protocol = json.loads(Path(protocol_path).read_text())
    refusal = judged_run_refusal(protocol)
    if refusal:
        raise SystemExit("Refused: " + refusal)
    result = study(protocol["judged_dt_s"])
    items, verdict = verdicts(flat(result["quantities"]), protocol)
    snapshot = json.loads((ROOT / "SNAPSHOT.json").read_text())
    return dict(
        protocol=str(protocol_path),
        protocol_status=protocol["status"],
        source_revision=snapshot["git_revision"],
        items=items,
        verdict=verdict,
        run=result,
    )


ACTIONS = ("compare", "check", "probe", "admit", "study", "terms", "reference", "fill", "judge")


def fill(term_path, reference_path, study_paths=(), protocol_path=PROTOCOL):
    """The protocol draft with its values (protocol_values), its development observations
    (development_observations, the trajectory's from the study files) and evidence filled in,
    still PROPOSED: the lead registers it."""
    protocol = json.loads(Path(protocol_path).read_text())
    if not protocol["status"].startswith("PROPOSED"):
        raise SystemExit("Refused: fill writes a PROPOSED draft only")
    term_values = json.loads(Path(term_path).read_text())
    reference_values = json.loads(Path(reference_path).read_text())
    studies = [json.loads(Path(f).read_text()) for f in study_paths]
    if term_values["stop"]:
        raise SystemExit(
            "Refused: the study met the stop condition: " + str(term_values["non_converging"])
        )
    protocol["values"] = protocol_values(term_values, reference_values)
    observations = protocol.setdefault("development_observations", {})
    observations["by_quantity"] = development_observations(term_values, reference_values, studies)
    observations["stop_condition_met"] = term_values["stop"]
    protocol["evidence"] = dict(
        protocol["evidence"], terms=str(term_path), reference=str(reference_path)
    )
    if study_paths:
        protocol["evidence"]["study"] = [str(f) for f in study_paths]
    return protocol


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ACTIONS:
        one = sub.add_parser(name)
        one.add_argument("--output", type=Path, required=True)
        if name in ("probe", "study"):
            one.add_argument("--dt", type=float, default=JUDGED_DT)
        if name == "terms":
            one.add_argument("--studies", type=Path, nargs=3, required=True)
        if name == "fill":
            one.add_argument("--terms", type=Path, required=True)
            one.add_argument("--reference", type=Path, required=True)
            one.add_argument("--studies", type=Path, nargs="*", default=())
    args = parser.parse_args(argv)
    if args.action not in ("terms", "fill"):
        import jax

        jax.config.update("jax_enable_x64", True)
    if args.action == "compare":
        from cells.core.specs import parse_spec

        raw = definition()
        parse_spec(raw)  # The composite's definition checks (raises on a refusal).
        result = dict(status=STATUS, **compare_report(raw), definition=raw)
    elif args.action == "check":
        result = dict(status=STATUS, **check())
    elif args.action == "probe":
        result = dict(status=STATUS + " Bounded ledger probe; no Q quantity.", **probe(args.dt))
    elif args.action == "admit":
        result = dict(status=STATUS + " The study's admission; no step taken.", **admit())
    elif args.action == "study":
        keep = args.output.with_name(args.output.stem + "-run")
        result = dict(status=STATUS + " Development dt study.", **study(args.dt, keep=keep))
    elif args.action == "terms":
        studies = [json.loads(Path(f).read_text()) for f in args.studies]
        result = dict(status=STATUS + " Step terms of the dt study.", **terms(studies))
    elif args.action == "reference":
        result = dict(status=STATUS + " R-full's reference terms.", **reference())
    elif args.action == "fill":
        result = fill(args.terms, args.reference, args.studies)
    else:
        result = judge()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1, default=float) + "\n")
    print(args.action, "written", args.output)


if __name__ == "__main__":
    main()
