"""Operator cells.operator.scheduled_bath_composition@1: a held bath's composition changed on the dt grid (FR-10).

docs/BATH_SCHEDULE_DESIGN.md (accepted by the lead with the advisor, D169). At declared times on the
dt grid, an event map sets each scheduled held bath's composition to its declared one plus a sum of
neutral formula units, c = c0 + sum_f a_f nu_f. Each unit's counts nu_f are integers, and its charge
sum_s z_s nu_sf is checked to be exactly 0 in integer arithmetic (D152's integer moiety form), so
every step is electroneutral by construction and a net-charged step is refused. The offsets a_f of
an event are absolute against the declared composition, so successive events never accumulate
rounding. The bath's held content is this operator's state. @3 reads it through the view of
extracellular_amount_reference at that bath (an adapter view field), so @3's transport, its IMEX
face weights and reservoir potential mu_b, RK4's derivative and the run-time membrane rate all see
the scheduled composition (models/surface_pump_v3.imex_step,
models/surface_tissue.derivative_from_field).

The frame (design §2.1). @3 pins a held bath's increment at zero (surface_tissue.domain_valid, the
mask outside_active & ~reservoir), and a held bath's exchange with the tissue is supply
(numerics/surface_transport.transport), so a held bath's content lies outside @3's tissue: its free
energy is in no ledger, and @3 books every supply at the view's mu_b. So:
* records, with no heat or work role (the reservoir's content is outside the energy ledger, and its
  free energy scales with the bath's nominal volume, which as work would loosen the IMEX bound):
  - bath_dose_fmol, the dose: the controller's supply to the reservoir, kept apart from @3's
    reservoir_supplied (the reservoir's supply to the tissue);
  - bath_dose_free_energy_pJ, its exact free-energy change at the declared volume
    (adapter.species_chemical_free_energy_pJ; the older law's chemical work of a dose, models/
    surface_bath_events.signal_values). A neutral step has no electrical part, so this is the
    composition change's whole external work;
  - bath_compensation_charge_C, the older rule's compensating electrode charge, -F sum_s z_s dn_s
    (surface_bath_events.Adapter.balances: "Its held electrode supplies the opposite charge"). A
    neutral step makes it zero to rounding, which this operator's own ledger checks. The bath's
    charge anchor is not changed, so neither the field (a held bath is a fixed node) nor @3's
    electrode ledger moves;
* the reconciliation term K of @3's reservoir-work ledger, this operator's own ledger term, never a
  write into @3's reservoir_work_pJ. @3's ledger is W - 1e-3 sum_s mu0_s S_s at the declared mu0,
  while @3 books each epoch's supply at that epoch's mu: K = B + 1e-3 sum_s (mu_now - mu0) S_s, with
  B updated at each event by 1e-3 sum_s (mu_old - mu_new) S_s(t_e). The electrical parts z F phi_b
  cancel in the differences, so only RT ln(c / c0) enters;
* the energy ledger needs no term: at an event nothing in the tissue moves.

Step checks (R5): @3's bounds on the definition with each scheduled bath at its per-species maximum
over the schedule (inner_check_spec): the explicit-rate bound's slope term grows with max(c).

Refusals. At the definition: a target that is not a held bath; a formula unit with a count that is
not a positive int, an unknown species, or a nonzero integer charge; an event at or before 0, at or
beyond the end, off the dt grid, out of time order for a bath, naming an unscheduled bath or an
undeclared unit, or leaving a species of a bath non-positive; more than 1,024 species (the shared
cap, FR-43 / D315); an anisosmotic step beside water@1, whose bath water potential is bound at the
definition (the design's door W); and (milestone 2, the design's §8) a step outside the measured
region: a step is admitted only if a measured passing point of its key (neutral species by class,
ions by species ID) and direction dominates its ratio and level, under ARS(2,2,2) at dt <= 1 ms or
RK4 at dt <= 0.1 ms, beside faces at kappa/V <= 10/s. The composite's own
structure check refuses cells.operator.local_species_reactions@1 (it reads the field as declared, a nominal
conflict: the design's door S), cells.operator.scheduled_membrane_insertion@1 (a second provider of the field),
the closers (the field is padded beside them) and so the lumens. The stationary analysis does not
admit the composite (its own ID check). At run time: a target that is not finite and positive.

Idle: a step with no event due selects the start state, and before a bath's first event its control
is its declared reference amounts themselves, so with no event the view is the declared array bit
for bit.

A dose from nothing is D150's unresolved switch-on at the face beside the bath, a known limit
(D169): the host energy ledger refuses it in species-only worlds and a mixed one runs it unseen
(FR-10's probe 1), so milestone 2 refuses it at the definition, with every other step outside the
measured region (MEASURED_POINTS: §7's staircase probe and milestone 2's probes I and D). Dose
through stairs inside the region.
"""

import math
from bisect import bisect_right
from dataclasses import dataclass, replace

import jax.numpy as jnp
import numpy as np

from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump as first
from cells.numerics import osmotic_water as water_law
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.species_sums import entity_sum, species_sum
from cells.operators import species_common as common
from cells.operators.contract import Change, Operator

LAW_ID = "cells.operator.scheduled_bath_composition@1"
EVENTS_KEY = "bath_composition_events"
WATER_LAWS = (water_law.LAW_ID,)  # Their bath water potential is bound at the definition.
ISOSMOTIC_RTOL = 1e-12  # |sum_s dc_s| against sum_s c0_s beside water@1.
DOSE_FLOOR_FMOL = 1e-12  # Floors of the own ledgers (plus the per-step rounding).
ENERGY_FLOOR_PJ = 3e-12
CHARGE_FLOOR_C = 3e-25
# Milestone 2 (the design's §8): a step is admitted only inside the measured region.
ARS_LAW = "cells.solver.imex_ars222_face_electromigration@1"
MEASURED_DT = {ARS_LAW: 1e-3, "rk4": 1e-4}  # Solver: its largest measured step (s).
MEASURED_FACE_RATE = 10.0  # 1/s: the fastest face (kappa / V of its other node) measured.
NEUTRAL = "neutral"  # The key of every species of valence 0.
# {(key, direction): ((ratio, level mM), ...)}: each point passed under both solvers, ARS at 1 ms
# and RK4 at 0.1 ms (the design's §7). Neutral species are keyed by class, ions by species ID.
MEASURED_POINTS = {
    # The staircase probe (run-2a7e594/staircase): stairs of 100 and single steps of 10.
    (NEUTRAL, "up"): ((100.0, 1e-3), (10.0, 1e-2), (3.0, 3e-3), (1.5, 1.5e-3)),
    # Milestone 2's probe D (m2-probes/run-3d16980): steps down from 1e-2 and 1e-3 mM.
    (NEUTRAL, "down"): ((10.0, 1e-3), (100.0, 1e-3), (10.0, 1e-2), (100.0, 1e-2)),
    # Milestone 2's probe I: KCl for NaCl from K 5 mM; K rises, Na falls.
    ("K", "up"): ((1.5, 7.5), (3.0, 15.0), (10.0, 50.0)),
    ("Na", "down"): ((145.0 / 142.5, 145.0), (145.0 / 135.0, 145.0), (1.45, 145.0)),
}
REGION_RTOL = 1e-9  # A step on a measured corner, to representation.

STATE_AXES = {
    "bath_held_amount_fmol": ["species", "extracellular_slot"],  # Held content; 0 off the baths.
    "bath_dose_fmol": ["species", "extracellular_slot"],  # Cumulative dose (a record).
    "bath_dose_free_energy_pJ": ["extracellular_slot"],  # Its free-energy change (a record).
    "bath_compensation_charge_C": ["extracellular_slot"],  # -F sum z dose (a record, ~0).
    "bath_reservoir_work_term_pJ": ["extracellular_slot"],  # B of K.
    "bath_energy_magnitude_pJ": ["extracellular_slot"],  # Magnitudes of the bookings.
}
LAYOUT_FIELDS = ("bath_scheduled",)  # [outside] bool: the scheduled held baths.
CONTROL_FIELDS = ("bath_target_amount_fmol",)  # [species, outside]: the held content in force.
LEDGERS = ("bath_dose", "bath_dose_free_energy", "bath_neutrality")
LEDGER_DIAGNOSTICS = (
    "bath_dose_balance_error_fmol",
    "bath_dose_free_energy_error_pJ",
    "bath_neutrality_error_C",
)
LEDGER_MESSAGE = "Bath schedule accounting failed: "


@dataclass(frozen=True)
class FormulaUnit:
    name: str
    counts: tuple  # ((species id, positive int count), ...) as declared.


@dataclass(frozen=True)
class BathScheduleDeclaration:
    law: str
    baths: tuple  # Held bath IDs, in declared order.
    formula_units: tuple  # FormulaUnit, in declared order.


@dataclass(frozen=True)
class BathEvent:
    time: float
    baths: tuple
    offsets: tuple  # ((unit name, mM), ...) as declared; units not named are 0.


@dataclass(frozen=True)
class BathProgram:
    events: tuple  # BathEvent, as declared.
    held: (
        tuple  # Per scheduled bath: ((time, amounts), ...) from time 0, the declared content first.
    )


# ------------------------------------------------------------------ definition


def _finite(value, what):
    if type(value) not in (int, float) or not np.isfinite(value):
        raise ConfigError(f"{LAW_ID}: {what} is a finite number")
    return float(value)


def parse_declaration(raw, base):
    _fields(raw, {"law", "baths", "formula_units"}, "bath schedule")
    if raw["law"] != LAW_ID:
        raise ConfigError("A bath schedule requires law " + LAW_ID)
    m = base.model
    outside = {c.id: c for c in m.extracellular}
    if type(raw["baths"]) is not list or not raw["baths"]:
        raise ConfigError(f"{LAW_ID} declares the held baths it schedules in a non-empty list")
    baths = []
    for name in raw["baths"]:
        bath = identifier(name)
        if bath not in outside:
            raise ConfigError(f"{LAW_ID} schedules an undeclared outside node {bath!r}")
        if not outside[bath].reservoir:
            raise ConfigError(
                f"{LAW_ID} schedules held baths only; {bath!r} is a finite node, which cannot be "
                "clamped"
            )
        baths.append(bath)
    if len(set(baths)) != len(baths):
        raise ConfigError(f"{LAW_ID} lists a bath twice")
    valence = dict(zip(m.species_ids, m.valence, strict=True))
    if not isinstance(raw["formula_units"], dict) or not raw["formula_units"]:
        raise ConfigError(f"{LAW_ID} declares its formula units as a non-empty object")
    units = []
    for name, counts in raw["formula_units"].items():
        unit = identifier(name)
        if not isinstance(counts, dict) or not counts:
            raise ConfigError(f"{LAW_ID}: formula unit {unit} declares its species counts")
        rows, charge = [], 0
        for species, count in counts.items():
            if species not in valence:
                raise ConfigError(
                    f"{LAW_ID}: formula unit {unit} names a species the model does not declare: "
                    f"{species!r}"
                )
            if type(count) is not int or count < 1:
                raise ConfigError(
                    f"{LAW_ID}: formula unit {unit}'s counts are positive integers (as D152's "
                    "moieties)"
                )
            rows.append((species, count))
            charge += valence[species] * count  # Integer arithmetic: exact.
        if charge != 0:
            raise ConfigError(
                f"{LAW_ID}: formula unit {unit} carries a net charge of {charge} (integer valences "
                "times counts); a net-charged step is refused in version 1, so every step is "
                "electroneutral by construction"
            )
        units.append(FormulaUnit(unit, tuple(rows)))
    return BathScheduleDeclaration(LAW_ID, tuple(baths), tuple(units))


def declaration_to_dict(declaration):
    if type(declaration) is not BathScheduleDeclaration or any(
        type(u) is not FormulaUnit for u in declaration.formula_units
    ):
        raise ConfigError("Require explicit immutable bath schedule declaration types")
    return dict(
        law=declaration.law,
        baths=list(declaration.baths),
        formula_units={u.name: dict(u.counts) for u in declaration.formula_units},
    )


def unit_change(declaration, offsets, species_ids):
    """[species] the concentration change sum_f a_f nu_f (mM) of one event's offsets.

    Each species' terms a_f nu_f are summed by math.fsum, correctly rounded, so the change does not
    depend on the order of the recipe's entries. A left-to-right running total lost a small term
    between a large one and its negative: with +A, +d and -A it gave A + d = A, then 0, and the
    dose was erased (the independent Lean project's finding, lean/PROGRESS.md "Bath recipe order",
    20 November 2026). With two terms or fewer per species the two sums are equal bit for bit, as
    in every registered world (45 worlds, 87 sums, 20 November 2026)."""
    counts = {u.name: dict(u.counts) for u in declaration.formula_units}
    terms = {}
    for unit, amount in offsets:
        for species, count in counts[unit].items():
            terms.setdefault(species, []).append(count * amount)
    change = np.zeros(len(species_ids))
    for species, values in terms.items():
        change[species_ids.index(species)] = math.fsum(values)
    return change


def parse_events(raw, base, declaration):
    """The events (module docstring) and each scheduled bath's held content over time (host)."""
    events_raw = raw[EVENTS_KEY]
    if type(events_raw) is not list:
        raise ConfigError(f"{EVENTS_KEY} requires an explicit list")
    dt, end = base.execution.dt, base.experiment.end_time
    m = base.model
    species_ids = list(m.species_ids)
    known = {u.name for u in declaration.formula_units}
    events = []
    for entry in events_raw:
        _fields(entry, {"time", "baths", "formula_units_mM"}, f"{EVENTS_KEY} entry")
        time = _finite(entry["time"], "an event time")
        if not 0.0 < time < end:
            raise ConfigError(
                f"{LAW_ID}: an event lies after time 0 and before the end time (the declared "
                "composition is the initial one)"
            )
        if on_grid(time, dt) is None:
            raise ConfigError(f"{LAW_ID}: an event time must be {ON_THE_GRID}")
        if type(entry["baths"]) is not list or not entry["baths"]:
            raise ConfigError(f"{LAW_ID}: an event names the baths it sets")
        baths = tuple(identifier(b) for b in entry["baths"])
        for bath in baths:
            if bath not in declaration.baths:
                raise ConfigError(f"{LAW_ID}: an event names an unscheduled bath {bath!r}")
        if len(set(baths)) != len(baths):
            raise ConfigError(f"{LAW_ID}: an event names a bath twice")
        offsets_raw = entry["formula_units_mM"]
        if not isinstance(offsets_raw, dict):
            raise ConfigError(f"{LAW_ID}: an event's formula_units_mM is an object")
        offsets = []
        for unit, amount in offsets_raw.items():
            if unit not in known:
                raise ConfigError(f"{LAW_ID}: an event names an undeclared formula unit {unit!r}")
            offsets.append((unit, _finite(amount, f"the offset of {unit}")))
        events.append(BathEvent(time, baths, tuple(offsets)))
    outside = {c.id: c for c in m.extracellular}
    held = []
    for bath in declaration.baths:
        node = outside[bath]
        declared = tuple(node.initial_amount_fmol)
        series = [(0.0, declared)]
        for event in events:
            if bath not in event.baths:
                continue
            if event.time <= series[-1][0]:
                raise ConfigError(f"{LAW_ID}: the events of bath {bath} increase strictly in time")
            change = unit_change(declaration, event.offsets, species_ids)
            amounts = tuple(
                float(n + node.volume_pL * c) for n, c in zip(declared, change, strict=True)
            )
            if not all(np.isfinite(a) and a > 0 for a in amounts):
                raise ConfigError(
                    f"{LAW_ID}: the event at {event.time} s leaves a species of bath {bath} "
                    "non-positive (every species stays positive, at least at its trace)"
                )
            series.append((event.time, amounts))
        held.append(tuple(series))
    return BathProgram(tuple(events), tuple(held))


def events_to_dict(schedule):
    if type(schedule) is not BathProgram or any(type(e) is not BathEvent for e in schedule.events):
        raise ConfigError("Require explicit immutable bath schedule types")
    return {
        EVENTS_KEY: [
            dict(time=e.time, baths=list(e.baths), formula_units_mM=dict(e.offsets))
            for e in schedule.events
        ]
    }


def held_at(schedule, time):
    """Each scheduled bath's held content in force at `time` (hashable)."""
    out = []
    for series in schedule.held:
        k = bisect_right([t for t, _ in series], time)
        out.append(series[max(k, 1) - 1][1])
    return tuple(out)


def steps(spec, declaration, schedule):
    """Every step of every scheduled bath: (bath, time, species, valence, c, c') in mM."""
    m = spec.model
    volumes = {c.id: c.volume_pL for c in m.extracellular}
    out = []
    for bath, series in zip(declaration.baths, schedule.held, strict=True):
        for (_, before), (time, after) in zip(series[:-1], series[1:], strict=True):
            for s, (a, b) in enumerate(zip(before, after, strict=True)):
                if a != b:
                    v = volumes[bath]
                    out.append((bath, time, m.species_ids[s], m.valence[s], a / v, b / v))
    return out


def face_rates(spec, bath, s):
    """[1/s] kappa / V of the other node, for species row s, over every face touching `bath`."""
    m = spec.model
    nodes = {c.id: c for c in m.extracellular}
    rates = []
    for f in m.faces:
        if bath not in (f.sender, f.receiver):
            continue
        other = nodes[f.receiver if f.sender == bath else f.sender]
        if other.reservoir:
            continue
        kappa = 1e15 * f.diffusivity_m2_per_s[s] * f.area_m2 / f.length_m  # pL/s
        rates.append(kappa / other.volume_pL)
    return rates


def admitted(key, direction, ratio, level):
    """Whether a measured point of (key, direction) dominates (ratio, level)."""
    bound = 1.0 + REGION_RTOL
    return any(
        ratio <= r * bound and level <= c * bound
        for r, c in MEASURED_POINTS.get((key, direction), ())
    )


def refuse_unmeasured_steps(spec, declaration, schedule):
    """Milestone 2's rule (the design's §8): every step inside the measured region, or refused."""
    found = steps(spec, declaration, schedule)
    if not found:
        return
    x = spec.execution
    if x.solver not in MEASURED_DT or x.dt > MEASURED_DT[x.solver] * (1.0 + REGION_RTOL):
        raise ConfigError(
            f"{LAW_ID}: dose steps are measured only under ARS(2,2,2) at dt <= 1 ms and RK4 at "
            f"dt <= 0.1 ms; this definition runs {x.solver} at {x.dt} s (the design's §8)"
        )
    ids = list(spec.model.species_ids)
    for bath, time, species, valence, c, c_new in found:
        key = NEUTRAL if valence == 0 else species
        direction = "up" if c_new > c else "down"
        ratio, level = max(c, c_new) / min(c, c_new), max(c, c_new)
        fast = [r for r in face_rates(spec, bath, ids.index(species)) if r > MEASURED_FACE_RATE]
        if fast:
            raise ConfigError(
                f"{LAW_ID}: the step of {species} at bath {bath} at {time} s crosses a face at "
                f"{max(fast):g}/s beside it; steps are measured only beside faces at "
                f"kappa/V <= {MEASURED_FACE_RATE:g}/s (the design's §8)"
            )
        if not admitted(key, direction, ratio, level):
            points = MEASURED_POINTS.get((key, direction), ())
            raise ConfigError(
                f"{LAW_ID}: the {direction} step of {species} at bath {bath} at {time} s, from "
                f"{c:g} to {c_new:g} mM (ratio {ratio:g}, level {level:g} mM), lies outside the "
                f"measured region for ({key}, {direction}): "
                + (
                    "admitted steps have a ratio and a level both within one of "
                    + ", ".join(f"(ratio {r:g}, level {lv:g} mM)" for r, lv in points)
                    if points
                    else "no step of that kind is measured"
                )
                + ". Dose through stairs inside the region (the design's §7 and §8)"
            )


def check_definition(spec, declaration, schedule, model):
    """The species cap (as every species operator); beside water@1, every step is isosmotic (its
    bath water potential is bound at the definition, models/operators/osmotic_water.bind, so an
    anisosmotic step would leave water reading the declared bath: the design's door W); then every
    step inside the measured region (milestone 2, the design's §8)."""
    common.check_species_cap(spec, LAW_ID)
    if any(op.LAW_ID in WATER_LAWS for op in model.operators):
        check_isosmotic(declaration, schedule)
    refuse_unmeasured_steps(spec, declaration, schedule)


def check_isosmotic(declaration, schedule):
    for bath, series in zip(declaration.baths, schedule.held, strict=True):
        declared = np.asarray(series[0][1])
        for time, amounts in series[1:]:
            change = abs(
                float(
                    entity_sum(species_sum(np.asarray(amounts) - declared, xp=np), axis=None, xp=np)
                )
            )
            if change > ISOSMOTIC_RTOL * float(
                entity_sum(species_sum(declared, xp=np), axis=None, xp=np)
            ):
                raise ConfigError(
                    f"{LAW_ID}: the step of bath {bath} at {time} s is anisosmotic; beside water@1 "
                    "only isosmotic steps are admitted, since water reads the declared bath "
                    "(door W)"
                )


def bind(spec, declaration, inner_layout):
    m, x = spec.model, spec.execution
    o = x.extracellular_capacity
    outside = [c.id for c in m.extracellular]
    scheduled = np.zeros(o, dtype=bool)
    for bath in declaration.baths:
        scheduled[outside.index(bath)] = True
    reference = np.asarray(inner_layout.extracellular_amount_reference)
    s = reference.shape[0]
    state = {
        "bath_held_amount_fmol": np.where(scheduled[None, :], reference, 0.0),
        "bath_dose_fmol": np.zeros((s, o)),
        "bath_dose_free_energy_pJ": np.zeros(o),
        "bath_compensation_charge_C": np.zeros(o),
        "bath_reservoir_work_term_pJ": np.zeros(o),
        "bath_energy_magnitude_pJ": np.zeros(o),
    }
    return state, dict(bath_scheduled=scheduled)


# ------------------------------------------------------------------ the law


def _masked(mask, value, fill, *, xp):
    return xp.where(mask, value, fill)


def apply_events(state, control, p, *, xp=jnp):
    """(state after the events due at the step start, the targets' validity)."""
    scheduled = p.bath_scheduled
    held = state.bath_held_amount_fmol
    target = control.bath_target_amount_fmol
    due = scheduled & xp.any(held != target, axis=0)  # [outside]
    on = due[None, :]
    anchor = _masked(on, held, 1.0, xp=xp)
    goal = _masked(on, target, 1.0, xp=xp)
    change = _masked(on, target - held, 0.0, xp=xp)
    volume = p.extracellular_volume[None, :]
    t = p.temperature
    energy = adapter.species_chemical_free_energy_pJ(anchor, change, volume, t, xp=xp)
    magnitude = adapter.species_chemical_magnitude_pJ(anchor, change, volume, t, xp=xp)
    # B: 1e-3 sum_s (mu_old - mu_new) S_s, with mu_old - mu_new = RT ln(n_old / n_new).
    shift = 1e-3 * R * t * xp.log(anchor / goal) * state.reservoir_supplied
    charge = CHARGE_PER_FMOL * species_sum(p.valence * change, xp=xp)
    new = state._replace(
        bath_held_amount_fmol=xp.where(on, target, held),
        bath_dose_fmol=state.bath_dose_fmol + change,
        bath_dose_free_energy_pJ=state.bath_dose_free_energy_pJ
        + species_sum(_masked(on, energy, 0.0, xp=xp), xp=xp),
        bath_compensation_charge_C=state.bath_compensation_charge_C - xp.where(due, charge, 0.0),
        bath_reservoir_work_term_pJ=state.bath_reservoir_work_term_pJ
        + species_sum(_masked(on, shift, 0.0, xp=xp), xp=xp),
        bath_energy_magnitude_pJ=state.bath_energy_magnitude_pJ
        + species_sum(_masked(on, magnitude + xp.abs(shift), 0.0, xp=xp), xp=xp),
    )
    valid = xp.all(xp.where(scheduled[None, :], xp.isfinite(target) & (target > 0), True))
    flowing = xp.any(due)  # Nothing due: the start state, bitwise.
    selected = type(state)(*(xp.where(flowing, a, b) for a, b in zip(new, state, strict=True)))
    return selected, valid


def held_view(state, p, *, xp):
    """@3's extracellular_amount_reference: the held content at the scheduled baths, the declared
    array elsewhere (selected, never offset)."""
    return xp.where(
        p.bath_scheduled[None, :], state.bath_held_amount_fmol, p.extracellular_amount_reference
    )


def reconciliation(row, p, *, xp):
    """([outside] K, [outside] its magnitude): K = B + 1e-3 sum_s RT ln(n_now / n0) S_s."""
    on = p.bath_scheduled[None, :]
    now = _masked(on, row.bath_held_amount_fmol, 1.0, xp=xp)
    declared = _masked(on, p.extracellular_amount_reference, 1.0, xp=xp)
    term = 1e-3 * R * p.temperature * xp.log(now / declared) * row.reservoir_supplied
    term = _masked(on, term, 0.0, xp=xp)
    k = row.bath_reservoir_work_term_pJ + species_sum(term, xp=xp)
    return k, xp.abs(row.bath_reservoir_work_term_pJ) + species_sum(xp.abs(term), xp=xp)


def own_valid(state, p, *, xp):
    scheduled = p.bath_scheduled
    on = scheduled[None, :]
    held = state.bath_held_amount_fmol
    valid = xp.all(xp.where(on, xp.isfinite(held) & (held > 0), held == 0))
    valid &= xp.all(xp.isfinite(state.bath_dose_fmol))
    valid &= xp.all(xp.where(on, True, state.bath_dose_fmol == 0))
    for name in (
        "bath_dose_free_energy_pJ",
        "bath_compensation_charge_C",
        "bath_reservoir_work_term_pJ",
        "bath_energy_magnitude_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(scheduled, True, value == 0))
    return valid & xp.all(state.bath_energy_magnitude_pJ >= 0)


def worst_case(check_spec, declaration, schedule):
    """The definition with each scheduled bath at its per-species maximum over the schedule."""
    m = check_spec.model
    maxima = {
        bath: tuple(float(v) for v in np.max(np.asarray([a for _, a in series]), axis=0))
        for bath, series in zip(declaration.baths, schedule.held, strict=True)
    }
    outside = tuple(
        replace(c, initial_amount_fmol=maxima[c.id]) if c.id in maxima else c
        for c in m.extracellular
    )
    return replace(check_spec, model=replace(m, extracellular=outside))


class ScheduledBathComposition(Operator):
    LAW_ID = LAW_ID
    EVENT = True
    STATE_AXES = STATE_AXES
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = CONTROL_FIELDS
    EXPERIMENT_KEYS = (EVENTS_KEY,)
    VIEW_FIELDS = ("extracellular_amount_reference",)
    # Door S (docs/SCOPED_COMPOSITION_DESIGN.md §5): it replaces the anchors at its held baths only.
    VIEW_CHANGES = {"extracellular_amount_reference": Change("replace", "event", scoped=True)}
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_events(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return events_to_dict(schedule)

    def schedule_times(self, schedule):
        return tuple(sorted({e.time for e in schedule.events}))

    def value_at(self, schedule, time):
        return held_at(schedule, time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        outside = [c.id for c in spec.model.extracellular]
        slots = [outside.index(b) for b in declaration.baths]
        x = spec.execution
        values = np.zeros((len(records), len(spec.model.species_ids), x.extracellular_capacity))
        for i, record in enumerate(records):
            for slot, amounts in zip(slots, record, strict=True):
                values[i, :, slot] = amounts
        return (values[indices],)

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration, schedule, model)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        return worst_case(check_spec, declaration, schedule)

    def batch_signature(self, declaration):
        """The scheduled baths and the formula units; event times and offsets are controls."""
        return (
            LAW_ID,
            declaration.baths,
            tuple((u.name, u.counts) for u in declaration.formula_units),
        )

    def working_size(self, spec):
        x = spec.execution
        return 8 * (3 * len(spec.model.species_ids) + 5) * x.extracellular_capacity

    def summary(self, spec, declaration, schedule, history):
        outside = [c.id for c in spec.model.extracellular]
        records = {}
        for bath in declaration.baths:
            j = outside.index(bath)
            records[bath] = dict(
                dose_fmol=dict(
                    zip(
                        spec.model.species_ids,
                        np.asarray(history.bath_dose_fmol)[-1][:, j].tolist(),
                        strict=True,
                    )
                ),
                dose_free_energy_pJ=float(np.asarray(history.bath_dose_free_energy_pJ)[-1][j]),
                compensation_charge_C=float(np.asarray(history.bath_compensation_charge_C)[-1][j]),
            )
        return {
            "bath_schedule_law": LAW_ID,
            "bath_schedule_baths": list(declaration.baths),
            "bath_schedule_formula_units": {
                u.name: dict(u.counts) for u in declaration.formula_units
            },
            "bath_schedule_events": events_to_dict(schedule)[EVENTS_KEY],
            "bath_schedule_records": records,
            "bath_schedule_frame": (
                "@3 pins a held bath's increment at zero, so its content is outside the tissue's "
                "ledgers: the dose, its free-energy change at the declared volume and the "
                "compensating charge are this operator's records, and its reconciliation term "
                "closes @3's reservoir-work ledger"
            ),
            "bath_schedule_known_limit": (
                "a dose from nothing is D150's unresolved switch-on at the face beside the bath "
                "(D169): refused by the host energy ledger in species-only worlds, unseen in mixed "
                "ones"
            ),
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, inner_layout)

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        return dict(extracellular_amount_reference=held_view(state, p, xp=xp))

    def changed_slots(self, spec, declaration):
        outside = [c.id for c in spec.model.extracellular]
        baths = tuple(outside.index(b) for b in declaration.baths)
        return {"extracellular_amount_reference": baths}

    def view_slots(self, p, *, xp):
        return {"extracellular_amount_reference": p.bath_scheduled}

    def event(self, state, control, p, *, xp):
        return apply_events(state, control, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        target = control.bath_target_amount_fmol
        on = p.bath_scheduled[None, :]
        return xp.all(xp.where(on, xp.isfinite(target) & (target > 0), True))

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """K in @3's reservoir-work ledger (this operator's own term), and its own ledgers."""
        k, _ = reconciliation(row, p, xp=xp)
        result["reservoir_work"] = result["reservoir_work"] - k
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """K's magnitude in the reservoir-work bound (zero until a bath's first event)."""
        _, magnitude = reconciliation(row, p, xp=xp)
        magnitudes[7] = magnitude if magnitudes[7] is None else magnitudes[7] + magnitude
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        """The dose against the held content, the free-energy record against its endpoint
        difference (the terms telescope exactly), and the compensating charge against zero."""
        on = p.bath_scheduled[None, :]
        declared = _masked(on, p.extracellular_amount_reference, 0.0, xp=xp)
        held = row.bath_held_amount_fmol
        anchor = _masked(on, p.extracellular_amount_reference, 1.0, xp=xp)
        change = _masked(on, held - declared, 0.0, xp=xp)
        volume = p.extracellular_volume[None, :]
        energy = adapter.species_chemical_free_energy_pJ(
            anchor, change, volume, p.temperature, xp=xp
        )
        return dict(
            bath_dose=held - declared - row.bath_dose_fmol,
            bath_dose_free_energy=row.bath_dose_free_energy_pJ
            - species_sum(_masked(on, energy, 0.0, xp=xp), xp=xp),
            bath_neutrality=row.bath_compensation_charge_C,
        )

    def own_magnitudes(self, row, p, *, xp):
        on = p.bath_scheduled[None, :]
        declared = _masked(on, p.extracellular_amount_reference, 0.0, xp=xp)
        held = row.bath_held_amount_fmol
        anchor = _masked(on, p.extracellular_amount_reference, 1.0, xp=xp)
        change = _masked(on, held - declared, 0.0, xp=xp)
        volume = p.extracellular_volume[None, :]
        energy = adapter.species_chemical_magnitude_pJ(anchor, change, volume, p.temperature, xp=xp)
        amounts = xp.abs(held) + xp.abs(declared)
        return (
            amounts + xp.abs(row.bath_dose_fmol),
            xp.abs(row.bath_dose_free_energy_pJ)
            + species_sum(_masked(on, energy, 0.0, xp=xp), xp=xp)
            + row.bath_energy_magnitude_pJ,
            CHARGE_PER_FMOL * species_sum(xp.abs(p.valence) * amounts, xp=xp),
        )

    def own_bounds(self, magnitudes, steps):
        rounding = first.LEDGER_STEP_ROUNDING * np.finfo(float).eps * steps
        return (
            DOSE_FLOOR_FMOL + rounding * magnitudes[0],
            ENERGY_FLOOR_PJ + rounding * magnitudes[1],
            CHARGE_FLOOR_C + rounding * magnitudes[2],
        )
