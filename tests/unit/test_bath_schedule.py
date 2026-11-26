"""Tier-1 smoke test of cells.operator.scheduled_bath_composition@1 (FR-10; docs/BATH_SCHEDULE_DESIGN.md, D169).

In NumPy (no compile), on the species-only dose leg (validation/tissue/bath_schedule_fixtures):
* the definition refusals with their messages: a net-charged formula unit (exact, in integers), a
  count that is not a positive int, an unknown species, a finite node as a target, an event at time
  0 or at the end, off the dt grid or out of order, an undeclared unit or an unscheduled bath, a
  step that leaves a species non-positive, and an anisosmotic step beside water@1 (an isosmotic one
  is admitted);
* the composite's structure check: insertion@1 (a second provider of the field), the closers
  insertion@2 and the partition (the field is padded beside them) and the lumens over either
  refused in either order; what version 1 composes with admitted, and D152 too, by door S (its
  outside reads at finite nodes, the schedule's change at its held baths:
  docs/SCOPED_COMPOSITION_DESIGN.md, D176);
* before a bath's first event its control is its declared content bit for bit, so the event map
  selects the start state;
* an event sets the held content to the target bit for bit and books the dose, its free-energy
  change (against the exact change written out independently, Decimal, 50 digits), the
  compensating charge (zero for a neutral step) and the reconciliation accumulator B;
* the view presents the held content at the bath and the declared array elsewhere, bit for bit;
* the reservoir-work ledger of a row whose supply is booked at each epoch's potential, as @3 books
  it, closes with the operator's term and fails without it (the negative control);
* the operator's own ledgers close after an event, and the step checks see the worst composition;
* a recipe's target does not depend on the order of its entries (each claim with its plant, the
  left-to-right running total; the independent Lean project's finding of 20 November 2026,
  lean/PROGRESS.md "Bath recipe order"), and every order of +24, -24 and +2^-49 mM books the exact
  dose (the user's regression).

These are the operator's own bookings checked against their definitions. The independent references
of record come from a separate agent (D169).
"""

import contextlib
import copy
import itertools
from decimal import Decimal, getcontext
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.laws.electrochemistry import R
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS
from cells.operators import bath_schedule as schedule
from cells.registry.models import get_model
from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import secreted_species_fixtures as fx

getcontext().prec = 50
R_SI = Decimal("6.02214076e23") * Decimal("1.380649e-23")  # N_A k_B, exact (SI 2019).
DT = 1e-3
EVENT = 10 * DT
DOSE = 5e-4  # mM of cargo: the bath from 1e-3 to 1.5e-3 mM.
UNITS = {**bfx.CARGO, **bfx.SALTS}


def definition(events=None, units=None, baths=("bath",)):
    raw = bfx.dosed_world(dt=DT, end=0.05)
    events = [(EVENT, ["bath"], {"cargo": DOSE})] if events is None else events
    return bfx.with_bath_schedule(raw, baths, UNITS if units is None else units, events)


@pytest.fixture(scope="module")
def bound():
    spec = parse_spec(definition())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == bfx.LAW)
    j = [c.id for c in spec.model.extracellular].index("bath")
    s = list(spec.model.species_ids).index(fx.SPECIES)
    return spec, model, op, state, p, j, s


def target_at(spec, time):
    return np.asarray(cs.control_values(spec, [time]).bath_target_amount_fmol[0])


def event(op, state, target, p):
    return op.event(state, SimpleNamespace(bath_target_amount_fmol=target), p, xp=np)


def free_energy(n, volume):
    n, volume = Decimal(float(n)), Decimal(float(volume))
    return Decimal("1e-3") * R_SI * Decimal("310") * n * ((n / volume).ln() - 1)


def test_before_the_first_event_the_target_is_the_declared_content_and_nothing_is_due(bound):
    spec, _, op, state, p, j, _ = bound
    target = target_at(spec, EVENT - DT)
    declared = np.asarray(p.extracellular_amount_reference)[:, j]
    assert target[:, j].tobytes() == declared.tobytes()
    new, ok = event(op, state, target, p)
    assert ok
    for a, b in zip(new, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def test_an_event_sets_the_bath_and_books_its_records(bound):
    spec, _, op, state, p, j, s = bound
    target = target_at(spec, EVENT)
    supplied = np.array(state.reservoir_supplied, copy=True)
    supplied[s, j] = 2e-4  # The supply the bath has given so far (fmol).
    start = state._replace(reservoir_supplied=supplied)
    new, ok = event(op, start, target, p)
    assert ok
    held0 = np.asarray(p.extracellular_amount_reference)[:, j]
    volume = float(np.asarray(p.extracellular_volume)[j])
    assert new.bath_held_amount_fmol[:, j].tobytes() == target[:, j].tobytes()
    assert new.bath_dose_fmol[s, j] == pytest.approx(DOSE * volume, rel=1e-12)
    ions = np.arange(len(held0)) != s
    assert np.all(
        new.bath_dose_fmol[ions, j] == 0.0
    )  # The ions' targets are their declared content.
    exact = free_energy(target[s, j], volume) - free_energy(held0[s], volume)
    booked = Decimal(float(new.bath_dose_free_energy_pJ[j]))
    assert float(abs(booked - exact) / abs(exact)) < 1e-10
    assert new.bath_compensation_charge_C[j] == 0.0  # S is neutral: its own formula unit.
    shift = 1e-3 * R * 310.0 * np.log(held0[s] / target[s, j]) * 2e-4
    assert new.bath_reservoir_work_term_pJ[j] == pytest.approx(shift, rel=1e-12)
    others = np.arange(len(state.bath_dose_free_energy_pJ)) != j
    for name in ("bath_dose_free_energy_pJ", "bath_compensation_charge_C"):
        assert np.all(getattr(new, name)[others] == 0.0)


def test_a_salt_substitution_is_neutral_to_rounding():
    spec = parse_spec(definition(events=[(EVENT, ["bath"], {"NaCl": -10.0, "KCl": 10.0})]))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == bfx.LAW)
    j = [c.id for c in spec.model.extracellular].index("bath")
    ids = list(spec.model.species_ids)
    new, ok = event(op, state, target_at(spec, EVENT), p)
    assert ok
    volume = float(np.asarray(p.extracellular_volume)[j])
    dose = new.bath_dose_fmol[:, j]
    assert dose[ids.index("Na")] == pytest.approx(-10.0 * volume, rel=1e-12)
    assert dose[ids.index("K")] == pytest.approx(10.0 * volume, rel=1e-12)
    assert dose[ids.index("Cl")] == 0.0
    model.check_values(new, spec, steps=[11])  # Its own ledgers: neutrality to rounding.


def test_the_view_presents_the_held_content_and_the_declared_array_elsewhere(bound):
    spec, _, op, state, p, j, _ = bound
    new, _ = event(op, state, target_at(spec, EVENT), p)
    view = op.view(new, p, None, xp=np)["extracellular_amount_reference"]
    declared = np.asarray(p.extracellular_amount_reference)
    assert view[:, j].tobytes() == new.bath_held_amount_fmol[:, j].tobytes()
    others = np.arange(declared.shape[1]) != j
    assert view[:, others].tobytes() == declared[:, others].tobytes()
    before = op.view(state, p, None, xp=np)["extracellular_amount_reference"]
    assert before.tobytes() == declared.tobytes()  # No event yet: the declared array itself.


def test_the_reservoir_work_ledger_closes_with_the_term_and_fails_without_it(bound):
    """The supply of S before the event booked at mu0, after it at mu1, as @3 books it."""
    spec, model, op, state, p, j, s = bound
    rt = R * 310.0
    first, second = 2e-4, 3e-4  # Supply before and after the event (fmol).
    supplied = np.array(state.reservoir_supplied, copy=True)
    supplied[s, j] = first
    row, _ = event(op, state._replace(reservoir_supplied=supplied), target_at(spec, EVENT), p)
    volume = float(np.asarray(p.extracellular_volume)[j])
    mu0 = rt * np.log(float(np.asarray(p.extracellular_amount_reference)[s, j]) / volume)
    mu1 = rt * np.log(float(row.bath_held_amount_fmol[s, j]) / volume)
    supplied[s, j] = first + second
    work = np.array(row.reservoir_work_pJ, copy=True)
    work[j] = 1e-3 * (mu0 * first + mu1 * second)
    row = row._replace(reservoir_supplied=supplied, reservoir_work_pJ=work)
    with_term = model.inner_balances(row, p)["reservoir_work"][j]
    inner = model.inner.balances(model.inner.inner_state(row), model.inner.inner_layout(p))
    without = inner["reservoir_work"][j]
    expected = 1e-3 * (mu1 - mu0) * second
    assert abs(with_term) <= 1e-14 * abs(work[j])
    assert without == pytest.approx(expected, rel=1e-9)
    assert abs(without) > 1e3 * 3e-12  # The bound's floor: the term is what closes the ledger.


def test_the_operators_own_ledgers_close_after_events(bound):
    spec, model, op, state, p, j, _ = bound
    row, _ = event(op, state, target_at(spec, EVENT), p)
    ledgers = op.own_ledgers(row, p, xp=np)
    bounds = op.own_bounds(op.own_magnitudes(row, p, xp=np), 11)
    for (name, value), bound_value in zip(ledgers.items(), bounds, strict=True):
        assert np.all(np.abs(value) <= bound_value), name
    model.check_values(row, spec, steps=[11])


def test_the_step_checks_see_the_worst_composition(bound):
    spec, _, op, _, _, _, s = bound
    ((_, declaration, schedule),) = [e for e in cs.entries(spec) if e[0].LAW_ID == bfx.LAW]
    worst = op.inner_check_spec(spec, spec, declaration, schedule)
    bath = next(c for c in worst.model.extracellular if c.id == "bath")
    declared = next(c for c in spec.model.extracellular if c.id == "bath")
    assert bath.initial_amount_fmol[s] == pytest.approx(declared.initial_amount_fmol[s] * 1.5)
    others = [k for k in range(len(declared.initial_amount_fmol)) if k != s]
    assert all(bath.initial_amount_fmol[k] == declared.initial_amount_fmol[k] for k in others)


def water_definition(offsets):
    from validation.tissue import pump_water_fixtures as wfx

    raw = cs.frozen_definition(
        wfx.with_water(wfx.heredity_cell("D", end_time=0.1), pf_m_s=5e-4, bath_pressure_Pa=12.5)
    )
    units = {"NaM": {"Na": 1, "M": 1}, "KM": {"K": 1, "M": 1}}
    return bfx.with_bath_schedule(raw, ["bath_0"], units, [(0.05, ["bath_0"], offsets)])


def test_beside_water_only_an_isosmotic_step_is_admitted():
    parse_spec(water_definition({"NaM": -10.0, "KM": 10.0}))
    with pytest.raises(ConfigError, match="anisosmotic"):
        parse_spec(water_definition({"NaM": 10.0}))


def _units(**changes):
    return {**UNITS, **changes}


REFUSALS = [
    (dict(units=_units(bad={"K": 1}), events=[(EVENT, ["bath"], {"bad": 1.0})]), "net charge of 1"),
    (dict(units=_units(bad={"S": 2, "K": 1, "Cl": 2})), "net charge of -1"),
    (dict(units=_units(bad={"S": 1.5})), "positive integers"),
    (dict(units=_units(bad={"S": True})), "positive integers"),
    (dict(units=_units(bad={"S": 0})), "positive integers"),
    (dict(units=_units(bad={"X": 1})), "does not declare"),
    (dict(baths=("ecs_0",), events=[]), "finite node"),
    (dict(events=[(0.0, ["bath"], {"cargo": DOSE})]), "after time 0"),
    (dict(events=[(0.05, ["bath"], {"cargo": DOSE})]), "before the end time"),
    (dict(events=[(EVENT + DT / 3, ["bath"], {"cargo": DOSE})]), "on the clock's grid"),
    (dict(events=[(EVENT, ["bath"], {"nope": 1.0})]), "undeclared formula unit"),
    (dict(events=[(EVENT, ["ecs_0"], {"cargo": DOSE})]), "unscheduled bath"),
    (dict(events=[(EVENT, ["bath"], {"cargo": -2e-3})]), "non-positive"),
    (
        dict(events=[(2 * EVENT, ["bath"], {"cargo": DOSE}), (EVENT, ["bath"], {"cargo": 0.0})]),
        "increase strictly",
    ),
]


@pytest.mark.parametrize("change, message", REFUSALS)
def test_definition_refusals(change, message):
    with pytest.raises(ConfigError, match=message):
        parse_spec(definition(**change))


def test_a_dose_beside_reactions_is_admitted_by_door_s():
    """D152 reads the field as declared at finite nodes, the schedule changes it at its held baths:
    the slots are disjoint, so door S admits the pair (it was a nominal refusal before door S;
    docs/SCOPED_COMPOSITION_DESIGN.md §5, D176)."""
    from validation.tissue import species_reactions_fixtures as rfx

    raw = rfx.with_reactions(
        copy.deepcopy(definition()),
        [rfx.species(fx.SPECIES)],
        [rfx.mass_action("decay", {"outside": ["ecs_0"]}, {fx.SPECIES: 1}, {}, 0.1)],
        rfx.always(["decay"]),
    )
    parse_spec(raw)


STATE = "cells.operator.membrane_entity_state@1"
STRUCTURE_REFUSED = {
    "insertion@1, a second provider": (
        (STATE, "cells.operator.scheduled_membrane_insertion@1"),
        "two providers of the view field extracellular_amount_reference",
    ),
    "insertion@2, a closer": (
        (STATE, "cells.operator.scheduled_membrane_insertion@2"),
        "extracellular_amount_reference has closers or a provider, never both",
    ),
    "the partition, a closer": (
        (STATE, "cells.operator.isopotential_partition@1"),
        "extracellular_amount_reference has closers or a provider, never both",
    ),
    "lumen@1, over insertion@1": (
        (
            STATE,
            "cells.operator.scheduled_membrane_insertion@1",
            "cells.operator.restricted_cleft_lumen@1",
        ),
        "two providers of the view field extracellular_amount_reference",
    ),
    "lumen@2, over insertion@2": (
        (
            STATE,
            "cells.operator.scheduled_membrane_insertion@2",
            "cells.operator.restricted_cleft_lumen@2",
        ),
        "extracellular_amount_reference has closers or a provider, never both",
    ),
}
STRUCTURE_ADMITTED = (
    ("cells.operator.electrode_current_injection@1",),
    (STATE,),
    ("cells.operator.scheduled_cell_replacement@1",),
    ("cells.operator.scheduled_species_turnover@1",),
    ("cells.operator.scheduled_species_exchange@1",),
    ("cells.operator.scheduled_species_turnover@1", "cells.operator.scheduled_species_exchange@1"),
    (
        "cells.operator.ideal_osmosis_linear_compliance_water@1",
    ),  # Isosmotic steps only, at the definition.
    ("cells.operator.local_species_reactions@1",),  # Door S: disjoint slots (D176).
)


@pytest.mark.parametrize("name", sorted(STRUCTURE_REFUSED))
def test_the_composites_structure_check_refuses_the_other_writers_of_the_field(name):
    """Design §3.1: insertion@1 provides the field, the closers pad it, the lumens need one of them,
    and D152 reads it as declared. Each refusal is the composite's own rule, in either order."""
    laws, message = STRUCTURE_REFUSED[name]
    for order in ((*laws, bfx.LAW), (bfx.LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert any(message in e for e in errors), (order, errors)


@pytest.mark.parametrize("laws", STRUCTURE_ADMITTED, ids="+".join)
def test_the_composites_structure_check_admits_what_version_1_composes_with(laws):
    for order in ((*laws, bfx.LAW), (bfx.LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert errors == [], (order, errors)


# ------------------------------------------------------------ the recipe's order

ORDER_DT = 2.0**-10
ORDER_UNITS = {"single": {fx.SPECIES: 1}, "pair": {fx.SPECIES: 2}, "triple": {fx.SPECIES: 3}}
# (bath S mM, intended change d mM, opposing terms A mM): the three units give +d, +A and -A, every
# input and product a float64, so the 1 pL bath's target is S + d fmol in every order. The ordinary
# +-24 mM terms on a trace are the six cases below, with the event's records.
ORDER_CASES = {
    "opposing_extremes": (2.0**-10, 2.0**-11, 24.0 * 2.0**39),  # An ordinary dose.
}


def running_sum(declaration, offsets, species_ids):  # Planted: the left-to-right running total.
    counts = {u.name: dict(u.counts) for u in declaration.formula_units}
    change = np.zeros(len(species_ids))
    for unit, amount in offsets:
        for species, count in counts[unit].items():
            change[species_ids.index(species)] += count * amount
    return change


@contextlib.contextmanager
def summed_by(function):
    """The operator's unit_change replaced for the block (a plant)."""
    saved = schedule.unit_change
    schedule.unit_change = function
    try:
        yield
    finally:
        schedule.unit_change = saved


def order_failures(case):
    """The recipe's six orders whose parsed target is not S + d, with the operator as it stands."""
    anchor, d, a = ORDER_CASES[case]
    offsets = {"single": d, "pair": a / 2, "triple": -a / 3}
    raw = fx.world(nodes=(), contacts=(), faces=(), dt=ORDER_DT, end=4 * ORDER_DT, trace_mM=anchor)
    out = []
    for names in itertools.permutations(offsets):
        recipe = {name: offsets[name] for name in names}
        events = [(ORDER_DT, ["bath"], recipe)]
        spec = parse_spec(bfx.with_bath_schedule(raw, ["bath"], ORDER_UNITS, events))
        row = list(spec.model.species_ids).index(fx.SPECIES)
        j = [c.id for c in spec.model.extracellular].index("bath")
        node = spec.model.extracellular[j]
        expected = node.initial_amount_fmol[row] + node.volume_pL * d
        target = target_at(spec, ORDER_DT)[row, j]
        if not (node.volume_pL == 1.0 and target == expected == anchor + d):
            out.append(f"{' '.join(names)}: {target!r} fmol against {anchor + d!r}")
    return out


@pytest.mark.parametrize("case", sorted(ORDER_CASES))
def test_a_recipes_target_does_not_depend_on_the_order_of_its_entries(case):
    assert order_failures(case) == []
    with summed_by(running_sum):
        assert order_failures(case) != []


# The user's regression (20 November 2026): +24 mM, -24 mM and +2^-49 mM of S, in every order, to a
# 1 pL bath at 2^-49 mM give the parsed target 2^-48 fmol, which the event holds, and the dose
# 2^-49 fmol = 1.7763568394002505e-15 fmol, each exactly. Before, "+24, +2^-49, -24" booked 0
# and "+24, -24, +2^-49" booked 2^-49 (lean/checks/bath_schedule.py, recipe_orders(2**-49, 2**-49,
# 1): the units pair, triple and single give +24, -24 and +2^-49 mM).
TRACE = 2.0**-49
TRACE_RECIPE = {"pair": 12.0, "triple": -8.0, "single": TRACE}
TRACE_ORDERS = tuple(itertools.permutations(TRACE_RECIPE))
SIGNED = {"pair": "+24", "triple": "-24", "single": "+2^-49"}


def trace_order(names):
    """(target, held, dose) fmol of S at the bath after the event, and its validity, for one
    order of the recipe (parse, bind and the event in NumPy; no compile)."""
    raw = fx.world(nodes=(), contacts=(), faces=(), dt=ORDER_DT, end=4 * ORDER_DT, trace_mM=TRACE)
    events = [(ORDER_DT, ["bath"], {name: TRACE_RECIPE[name] for name in names})]
    spec = parse_spec(bfx.with_bath_schedule(raw, ["bath"], ORDER_UNITS, events))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    op = next(o for o in model.operators if o.LAW_ID == bfx.LAW)
    row = list(spec.model.species_ids).index(fx.SPECIES)
    j = [c.id for c in spec.model.extracellular].index("bath")
    target = target_at(spec, ORDER_DT)
    new, ok = event(op, state, target, p)
    held, dose = new.bath_held_amount_fmol[row, j], new.bath_dose_fmol[row, j]
    return float(target[row, j]), float(held), float(dose), bool(ok)


@pytest.mark.parametrize("names", TRACE_ORDERS, ids=lambda n: ",".join(SIGNED[k] for k in n))
def test_every_order_of_plus_and_minus_24_mM_and_a_trace_books_the_exact_dose(names):
    target, held, dose, ok = trace_order(names)
    assert ok and target == held == 2.0**-48
    assert dose == TRACE == 1.7763568394002505e-15


def test_the_running_sum_books_zero_unless_the_trace_comes_last():
    """The plant of the six cases above: the left-to-right running total erases the trace wherever
    it is added before the two 24 mM terms have cancelled (four of the six orders)."""
    with summed_by(running_sum):
        wrong = {names for names in TRACE_ORDERS if trace_order(names)[2] != TRACE}
    assert wrong == {names for names in TRACE_ORDERS if names[-1] != "single"}
