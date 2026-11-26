"""Tier-1 tests of cells.operator.scheduled_membrane_trafficking@1 (FR-2 version 1): T1, T2 and T3 of
docs/MEMBRANE_RETRIEVAL_DESIGN.md §8, in NumPy on bound worlds (no compile), each check beside a
planted error it catches.

* T1, identity and refusals. Each refusal of the definition fires with its reason: the
  requirements, the routes against the compartments' declaration, disjoint routes and one route
  per cell (D1), the carriers, the populations' enrichments and records, the floors and the
  schedule's exact area trajectory, the schedule's rules, the composition's admitted list and the
  declared kinds. The declaration and its schedule round-trip. Each refused case is its own plant.
* T2, idleness. Zero rates select the start state bitwise. Planted: a rate of one part in 10^12
  of the patch per half-step moves it.
* T3, area, capacitance and units, over a retrieval-recycling cycle with both directions at once:
  - A_k + A_b and C_k + C_b are conserved to rounding, and plasma units plus the record per
    population;
  - membrane state's three ledgers close exactly, the operator's own ledgers and @3's ledgers
    within their bounds (the host checks of the history);
  - each stage moves units by its closed form, N (A'/A)^e and R (A_b'/A_b)^e_r.
  Planted: a unit dropped from the record breaks the conserved total and the host checks refuse
  the history.

"""

from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.models import pump_composite
from cells.operators import OPERATORS, compartments
from cells.operators import membrane_trafficking as trafficking
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from validation.tissue import membrane_trafficking_fixtures as fx
from validation.tissue import site_occupancy_fixtures as sfx

LAW = trafficking.LAW_ID
H = fx.DT / 2


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def bind(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def operator(model):
    return next(op for op in model.operators if op.LAW_ID == LAW)


def control(retrieval, recycling):
    return SimpleNamespace(
        trafficking_retrieval_rate_m2_s=np.asarray(retrieval, dtype=float),
        trafficking_recycling_rate_m2_s=np.asarray(recycling, dtype=float),
    )


def route_block(raw):
    return next(op for op in raw["model"]["operators"] if op["law"] == LAW)


# ------------------------------------------------------------------ the admission


def test_the_compartments_admit_trafficking_and_read_the_areas_as_references():
    """The compartments admission (D217): membrane state and this operator on its admitted list,
    the areas and capacitances read as references, never as declared; and no development shim."""
    assert {compartments.STATE_LAW, trafficking.LAW_ID} <= set(compartments.ADMITTED)
    assert compartments.TRAFFICKING_LAW == trafficking.LAW_ID
    for name in ("membrane_area", "membrane_capacitance"):
        assert name not in compartments.CellOwnedCompartments.CONFLICTS_VIEW, name
        assert compartments.CellOwnedCompartments.SCOPED_READS[name].mode == "reference", name
    root = Path(__file__).resolve().parents[2]
    assert not (root / "tests" / "membrane_trafficking_development_shim.py").exists()
    assert {"cells.operator.membrane_entity_state@1", LAW} <= set(compartments.ADMITTED)
    assert not {"membrane_area", "membrane_capacitance"} & set(
        compartments.CellOwnedCompartments.CONFLICTS_VIEW
    )


# ------------------------------------------------------------------ T1: identity and refusals


def two_cells():
    raw = fx.pooled_cells(2)
    return raw, [fx.route(raw, 0), fx.route(raw, 1)]


def one_route(**changes):
    """The one-cell world with its route changed by `changes` (route() keywords), and a schedule
    moving 10% of the plasma area."""
    raw = fx.pooled_cells(1)
    entry = fx.route(raw, 0, **changes)
    return fx.with_trafficking(
        raw, [entry], [fx.schedule(entry["id"], [(0.0, fx.rate(raw, 0, 0.1))])]
    )


def edited(edit, **changes):
    raw = one_route(**changes)
    edit(raw)
    return raw


def scheduled(retrieval, recycling=((0.0, 0.0),), **changes):
    """The one-cell world with the route's schedules given as [(time, area fraction per run)]."""
    raw = fx.pooled_cells(1)
    entry = fx.route(raw, 0, **changes)

    def rates(points):
        return [(t, fx.rate(raw, 0, f)) for t, f in points]

    return fx.with_trafficking(
        raw, [entry], [fx.schedule(entry["id"], rates(retrieval), rates(recycling))]
    )


def without(law):
    def edit(raw):
        raw["model"]["operators"] = [op for op in raw["model"]["operators"] if op["law"] != law]

    return edit


def second_route(**changes):
    def edit(raw):
        block = route_block(raw)
        block["routes"].append(dict(block["routes"][0], id="second", **changes))
        controls = raw["experiment"]["trafficking_controls"]
        controls.append(dict(controls[0], route_id="second"))

    return edit


def with_operator(block, key=None, controls=None):
    def edit(raw):
        raw["model"]["operators"].append(block)
        if key is not None:
            raw["experiment"][key] = controls

    return edit


def schedule_edit(change):
    def edit(raw):
        change(raw["experiment"]["trafficking_controls"][0])

    return edit


INJECTION = dict(
    law="cells.operator.electrode_current_injection@1",
    electrodes=[dict(cell_id="cell_0", carriers={"K": 0.4912, "M": 0.5088})],
)
INJECTION_CONTROLS = [dict(cell_id="cell_0", schedule=[dict(time=0.0, current_A=0.0)])]
BATH = dict(
    law="cells.operator.scheduled_bath_composition@1", baths=["bath_0"], formula_units={"KM": {"K": 1, "M": 1}}
)


def sites_beside():
    """cells.operator.site_occupancy@1 beside the route: its ligand declared and one population on the furrow,
    which faces the finite cleft (a population facing a held bath is site occupancy's own
    refusal)."""
    raw = fx.pooled_cells(1, cleft=True)
    entry = fx.route(raw, 0)
    raw = fx.with_trafficking(
        raw, [entry], [fx.schedule(entry["id"], [(0.0, fx.rate(raw, 0, 0.1))])]
    )
    raw = add_inventory_species(
        raw, sfx.LIGAND, trace_mM=sfx.TRACE_mM, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    return sfx.with_site_occupancy(raw, [sfx.population(patch="furrow_0")])


def refusal_cases():
    yield (
        "membrane state is required",
        edited(without("cells.operator.membrane_entity_state@1")),
        (f"{LAW} requires cells.operator.membrane_entity_state@1 before it"),
    )
    yield (
        "the compartments are required",
        edited(without("cells.operator.cell_owned_compartments@1")),
        (f"{LAW} requires cells.operator.cell_owned_compartments@1 before it"),
    )
    yield (
        "an undeclared compartment",
        one_route(compartment_id="endosome_9"),
        ("compartment 'endosome_9' is not declared by cells.operator.cell_owned_compartments@1"),
    )
    yield (
        "an undeclared plasma patch",
        edited(lambda raw: route_block(raw)["routes"][0].update(plasma_patch="nowhere")),
        "plasma patch 'nowhere' is not declared",
    )
    raw, routes = two_cells()
    routes[0] = fx.route(raw, 0, plasma="membrane_1")
    yield (
        "a plasma patch of another cell",
        fx.with_trafficking(raw, routes[:1], [fx.schedule(routes[0]["id"], [(0.0, 0.0)])]),
        "lies on 'cell_1', not on its compartment's owner 'cell_0'",
    )
    yield (
        "a bounding patch as the plasma patch",
        one_route(plasma="pool_membrane_0"),
        ("plasma patch 'pool_membrane_0' is a compartment's bounding patch"),
    )
    yield (
        "two routes on one plasma patch",
        edited(second_route(compartment="endosome_1")),
        ("two routes share a plasma patch"),
    )
    raw, routes = two_cells()
    routes[1]["compartment"] = "endosome_0"
    yield (
        "two routes into one compartment",
        fx.with_trafficking(raw, routes, [fx.schedule(r["id"], [(0.0, 0.0)]) for r in routes]),
        "two routes share a compartment",
    )
    raw = fx.pooled_cells(2, cleft=True)  # cell_1's pool moved onto cell_0: two pools of cell_0.
    fx.patch(raw, "pool_membrane_1")["inside"] = "cell_0"
    block = next(op for op in raw["model"]["operators"] if op["law"] == fx.COMPARTMENTS)
    block["compartments"][1]["owner"] = "cell_0"
    routes = [fx.route(raw, 0), fx.route(raw, 1, plasma="furrow_0")]
    yield (
        "two routes of one cell",
        fx.with_trafficking(raw, routes, [fx.schedule(r["id"], [(0.0, 0.0)]) for r in routes]),
        "two routes fill receiving pools of one cell, 'cell_0'",
    )
    yield (
        "transference numbers that do not sum to 1",
        one_route(carriers={"K": 0.6, "Na": 0.5}),
        "transference numbers are positive and sum to 1",
    )
    yield (
        "a zero transference number",
        one_route(carriers={"K": 1.0, "Na": 0.0}),
        ("transference numbers are positive and sum to 1"),
    )
    yield "an undeclared carrier", one_route(carriers={"X": 1.0}), "undeclared carrier 'X'"
    yield (
        "an enrichment missing a population",
        one_route(retrieval={"kir_0": 1.0}),
        ("retrieval enrichment names exactly the populations on its plasma patch"),
    )
    yield (
        "a negative enrichment",
        one_route(recycling={"kir_0": -1.0, "nav_0": 1.0}),
        ("recycling enrichment of kir_0 must be finite and nonnegative"),
    )
    yield (
        "a negative record",
        one_route(internalised={"kir_0": -1.0, "nav_0": 0.0}),
        ("internalised units of kir_0 must be finite and nonnegative"),
    )
    yield (
        "a plasma floor at the declared area",
        one_route(plasma_floor=1.0),
        ("plasma area floor .* is not below the declared area"),
    )
    yield (
        "a pool floor above the declared area",
        one_route(pool_floor=1.5),
        ("pool area floor .* is not below the declared area"),
    )
    yield (
        "retrieval below the plasma floor",
        scheduled([(0.0, 0.6)]),
        ("takes its plasma patch below its area floor"),
    )
    yield (
        "recycling below the pool floor",
        scheduled([(0.0, 0.0)], [(0.0, 0.03)]),
        ("takes its pool below its area floor"),
    )
    yield (
        "the palindrome's excursion below the plasma floor",
        scheduled([(0.0, 0.0), (0.002, 0.6)], [(0.0, 0.0), (0.002, 0.6)], plasma_floor=0.999),
        "takes its plasma patch below its area floor",
    )
    yield (
        "a negative rate",
        edited(schedule_edit(lambda s: s["retrieval"][0].update(rate_m2_per_s=-1e-12))),
        "negative retrieval rate",
    )
    yield (
        "a change off the dt grid",
        edited(
            schedule_edit(lambda s: s["recycling"].append(dict(time=0.0015, rate_m2_per_s=0.0)))
        ),
        "on the clock's grid",
    )
    yield (
        "a schedule not starting at 0",
        edited(schedule_edit(lambda s: s["recycling"][0].update(time=0.001))),
        "recycling schedule starts at time 0",
    )
    yield (
        "a change at the end time",
        edited(
            schedule_edit(lambda s: s["retrieval"].append(dict(time=fx.END, rate_m2_per_s=0.0)))
        ),
        "at or beyond the end time",
    )
    yield (
        "a route without a schedule",
        edited(lambda raw: raw["experiment"]["trafficking_controls"].clear()),
        "every route, and only those, has a schedule",
    )
    yield (
        "an undeclared route's schedule",
        edited(schedule_edit(lambda s: s.update(route_id="elsewhere"))),
        "undeclared route 'elsewhere'",
    )
    yield (
        "injection beside it",
        edited(with_operator(INJECTION, "injection_controls", INJECTION_CONTROLS)),
        "cells.operator.electrode_current_injection@1 is refused: it is not qualified beside membrane trafficking",
    )
    yield (  # The compartments' admitted list, which runs first, refuses it before this one does.
        "site occupancy beside it",
        sites_beside(),
        f"{fx.COMPARTMENTS} composes only with .*; cells.operator.site_occupancy@1 is not on its admitted list",
    )
    yield (
        "the bath schedule beside it",
        edited(with_operator(BATH, "bath_composition_events", [])),
        f"{LAW} reads extracellular_amount_reference as declared, but "
        "cells.operator.scheduled_bath_composition@1 provides it",
    )


CASES = list(refusal_cases())


@pytest.mark.parametrize("name, raw, message", CASES, ids=[c[0] for c in CASES])
def test_each_refusal_fires_with_its_reason(name, raw, message):
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)


def test_the_admitted_world_parses_and_round_trips():
    raw = one_route(
        retrieval={"kir_0": 0.5, "nav_0": 2.0}, internalised={"kir_0": 3.0, "nav_0": 0.0}
    )
    spec = parse_spec(raw)
    again = parse_spec(cs.to_dict(spec))
    assert again.model.operators == spec.model.operators
    assert again.experiment.operators == spec.experiment.operators
    # The run view's records and the summary's identity block name the route's entities.
    op = OPERATORS[LAW]
    ((_, declaration, schedule),) = [e for e in cs.entries(spec) if e[0].LAW_ID == LAW]
    events = op.view_events(spec, declaration, schedule)
    assert [(e["time"], e["kind"], e["at"]) for e in events] == [
        (0.0, "recycling rate", {"membrane": "membrane_0"}),
        (0.0, "retrieval rate", {"membrane": "membrane_0"}),
    ]
    assert op.view_sets(spec, declaration)["trafficking_route"]["ids"] == ("uptake_0",)
    # Refusal 5 version 1.2's hook: the compartments the routes charge, by their own IDs.
    assert op.charged_compartments(spec, declaration) == ("endosome_0",)
    route = op.summary(spec, declaration, schedule, None)["trafficking_routes"]["uptake_0"]
    assert (route["pool_node"], route["pool_patch"], route["owner"]) == (
        "pool_0",
        "pool_membrane_0",
        "cell_0",
    )


def test_insertion_and_declared_kinds_are_refused_beside_it():
    """Insertion@1 is a second writer of capacitances (the composite and the compartments refuse
    its masks first); a declared kind is refused by FIXED_INNER_FIELDS, the operator's own
    declaration, beside any kind."""
    insertion = dict(
        law="cells.operator.scheduled_membrane_insertion@1",
        patches=[
            dict(
                membrane_id="membrane_0",
                specific_capacitance_F_per_m2=0.05,
                population_densities_per_m2={},
            )
        ],
    )
    controls = [
        dict(
            membrane_id="membrane_0", onset_time=None, schedule=[dict(time=0.0, rate_m2_per_s=0.0)]
        )
    ]
    with pytest.raises(ConfigError, match="cells.operator.scheduled_membrane_insertion@1"):
        parse_spec(edited(with_operator(insertion, "insertion_controls", controls)))
    assert trafficking.REFUSED["cells.operator.scheduled_membrane_insertion@1"] == trafficking.INSERTION_REASON
    # The declared inner structure, from the world with membrane state alone (the compartments
    # admit membrane state only with trafficking, and trafficking is refused beside the kind).
    plain = fx.pooled_cells(1)
    plain["model"]["operators"] = plain["model"]["operators"][:1]
    with kind_registry.scope(kf.registry(kf.carrier())):
        declared = get_model(parse_spec(kf.declare_carrier(plain)).model).inner
        laws = ("cells.operator.membrane_entity_state@1", "cells.operator.cell_owned_compartments@1", LAW)
        errors = pump_composite.structure_errors(declared, tuple(OPERATORS[k] for k in laws))
    assert errors == [
        f"{LAW} builds the inner model's state, layout or control with today's fixed fields, so "
        f"it does not run beside declared kinds ({kf.CARRIER_ID})"
    ]


def test_the_step_checks_read_the_schedules_extremes():
    """R5: @3's bounds run on the definition with the plasma patch at its largest area and its
    smallest capacitance over the schedule, and its populations at their largest units N0 + R0.
    Planted: retrieval of 95% of the patch, whose smallest capacitance raises @3's explicit rate
    past its bound at a step the zero-rate world admits."""
    raw = scheduled([(0.0, 0.3)], internalised={"kir_0": 50.0, "nav_0": 0.0}, plasma_floor=0.6)
    spec = parse_spec(raw)
    ((_, declaration, schedule),) = [e for e in cs.entries(spec) if e[0].LAW_ID == LAW]
    check = trafficking.check_spec_for(spec, spec, declaration, schedule)
    declared = {p.id: p for p in spec.model.membranes}
    checked = {p.id: p for p in check.model.membranes}
    plasma, pool = declared["membrane_0"], declared["pool_membrane_0"]
    assert checked["membrane_0"].area_m2 == plasma.area_m2  # Retrieval only: the start's.
    assert checked["membrane_0"].capacitance_F == pytest.approx(0.7 * plasma.capacitance_F)
    assert checked["pool_membrane_0"].capacitance_F == pytest.approx(pool.capacitance_F)
    kir = {c.id: c for c in check.model.channels}["kir_0"]
    units = 1.0 * plasma.area_m2 * fx.DENSITY + 50.0  # a0 A0 rho + R0 at the largest area.
    assert kir.abundance == pytest.approx(units / (plasma.area_m2 * fx.DENSITY), rel=1e-12)
    # The declared world at half its explicit-rate bound is admitted; 95% retrieved, its cell's
    # patch capacitance falls about tenfold in the check spec, and the same step is refused.
    zero = parse_spec(scheduled([(0.0, 0.0)], plasma_floor=0.04))
    deep = parse_spec(scheduled([(0.0, 0.95)], plasma_floor=0.04))
    rate = get_model(zero.model).inner.bind_step_checks(zero).explicit_rate
    steps = np.array([0.5 / rate])
    get_model(zero.model).bind_step_checks(zero)(steps)
    with pytest.raises(ConfigError, match="explicit-rate stability bound"):
        get_model(deep.model).bind_step_checks(deep)(steps)


def test_run_time_refusals_return_an_invalid_step(monkeypatch):
    """At run time a step is refused, never repaired: a negative merge heat from the kernel (the
    strict rule, kept as a guard now that the kernel's heat is a sum of squares), a piece as large
    as its source's whole area, a negative rate (the schedule's parser refuses one, so it is
    planted at the step; its piece never reaches the kernel, whose heat form gives NaN for a
    negative piece), and a carrier amount driven non-positive at a free node. Each is planted
    against the same step admitted."""
    _, model, state, p = bind(one_route())
    op = operator(model)
    area = float(p.membrane_area[int(p.trafficking_route_plasma[0])])
    _, ok = op.half_step(state, H, control([0.02 * area / H], [0.0]), p, xp=np)
    assert ok
    real = trafficking.adapter.charge_following_transfer

    def negative(*args, **kwargs):  # Planted: the kernel's heat rounds below zero.
        return real(*args, **kwargs)._replace(heat_pJ=-1e-30)

    monkeypatch.setattr(trafficking.adapter, "charge_following_transfer", negative)
    _, ok = op.half_step(state, H, control([0.02 * area / H], [0.0]), p, xp=np)
    assert not ok
    monkeypatch.setattr(trafficking.adapter, "charge_following_transfer", real)
    _, ok = op.half_step(state, H, control([area / (H / 2)], [0.0]), p, xp=np)  # The whole patch.
    assert not ok
    seen = []

    def spy(*args, **kwargs):  # The pieces the kernel is given.
        seen.append(np.asarray(args[4]))
        return real(*args, **kwargs)

    monkeypatch.setattr(trafficking.adapter, "charge_following_transfer", spy)
    _, ok = op.half_step(state, H, control([-0.02 * area / H], [0.0]), p, xp=np)
    assert not ok and seen and all(np.all(pieces >= 0) for pieces in seen)
    monkeypatch.setattr(trafficking.adapter, "charge_following_transfer", real)
    raw = fx.pooled_cells(1, cleft=True, cleft_pL=1e-5)  # A cleft of 5e-5 fmol of K.
    entry = fx.route(raw, 0, plasma="furrow_0")
    _, model, state, p = bind(
        fx.with_trafficking(raw, [entry], [fx.schedule(entry["id"], [(0.0, 0.0)])])
    )
    furrow = float(p.membrane_area[int(p.trafficking_route_plasma[0])])
    _, ok = operator(model).half_step(state, H, control([0.02 * furrow / H], [0.0]), p, xp=np)
    assert ok
    _, ok = operator(model).half_step(state, H, control([0.5 * furrow / H], [0.0]), p, xp=np)
    assert not ok  # Half the furrow carries about 3.4e-4 fmol of K out: more than it holds.


# ------------------------------------------------------------------ T2: idleness


def test_zero_rates_select_the_start_state_bitwise():
    _, model, state, p = bind(one_route())
    idle, ok = operator(model).half_step(state, H, control([0.0], [0.0]), p, xp=np)
    assert ok
    for a, b in zip(idle, state, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()
    # Planted: a rate of 1e-12 of the patch per half-step moves the state, so the check is live.
    area = float(p.membrane_area[int(p.trafficking_route_plasma[0])])
    moved, ok = operator(model).half_step(state, H, control([1e-12 * area / H], [0.0]), p, xp=np)
    assert (
        ok
        and np.asarray(moved.membrane_area_increment_m2).tobytes()
        != np.asarray(state.membrane_area_increment_m2).tobytes()
    )


# ------------------------------------------------------------------ T3: area, capacitance, units


def cycle_world():
    """One cell, its populations at distinct enrichments both ways, and a record of R0 units."""
    return one_route(
        retrieval={"kir_0": 1.0, "nav_0": 0.5},
        recycling={"kir_0": 2.0, "nav_0": 1.0},
        internalised={"kir_0": 20.0, "nav_0": 0.0},
    )


def cycle_rates(p):
    """Per half-step: 2% of the plasma area retrieved, then 3% of the pool recycled, then both."""
    plasma = float(p.membrane_area[int(p.trafficking_route_plasma[0])])
    pool = float(p.membrane_area[int(p.trafficking_route_pool[0])])
    retrieve, recycle = 0.02 * plasma / H, 0.03 * pool / H
    return [(retrieve, 0.0)] * 3 + [(0.0, recycle)] * 3 + [(retrieve, recycle)] * 2


def run_cycle(model, state, p, *, plant=None):
    op = operator(model)
    rows = [state]
    for retrieve, recycle in cycle_rates(p):
        state, ok = op.half_step(state, H, control([retrieve], [recycle]), p, xp=np)
        assert ok
        if plant is not None:
            state = plant(state)
        rows.append(state)
    return rows


def totals(state, p):
    """(A_k + A_b, C_k + C_b, plasma units + record per population) of the one route."""
    from cells.operators import membrane_state

    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    area = membrane_state.area(state, p, xp=np)
    capacitance = membrane_state.capacitance(state, p, xp=np)
    units = membrane_state.units(state, p, xp=np) + np.sum(
        state.trafficking_internalised_units, axis=0
    )
    return area[k] + area[b], capacitance[k] + capacitance[b], units


def history(rows):
    return type(rows[0])(*(np.stack(fields) for fields in zip(*rows, strict=True)))


def test_area_capacitance_and_units_are_conserved_and_every_ledger_closes():
    spec, model, state, p = bind(cycle_world())
    area0, capacitance0, units0 = totals(state, p)
    rows = run_cycle(model, state, p)
    for row in rows:
        area, capacitance, units = totals(row, p)
        assert area == pytest.approx(area0, rel=4e-16)
        assert capacitance == pytest.approx(capacitance0, rel=4e-16)
        np.testing.assert_allclose(units, units0, rtol=1e-14)
        ledgers = model.balances(row, p)
        for name in (
            "membrane_area_entity",
            "membrane_capacitance_entity",
            "population_abundance_entity",
        ):
            assert not np.any(ledgers[name]), name
    last = rows[-1]
    assert np.all(last.trafficking_retrieved_m2 > 0) and np.all(last.trafficking_recycled_m2 > 0)
    assert np.all(np.diff([float(r.trafficking_dissipated_energy_pJ[0]) for r in rows]) >= 0)
    diagnostics = model.check_values(history(rows), spec, steps=list(range(len(rows))))
    assert diagnostics["max_trafficking_unit_balance_error"] < 1e-11
    assert diagnostics["max_energy_balance_relative"] < 1e-9


def test_each_stage_moves_units_by_its_closed_form():
    """One retrieval stage: N' = N (A_k'/A_k)^e per population; one recycling stage:
    R' = R (A_b'/A_b)^e_r, the returned units joining the plasma population."""
    from cells.operators import membrane_state

    _, model, state, p = bind(cycle_world())
    k, b = int(p.trafficking_route_plasma[0]), int(p.trafficking_route_pool[0])
    area = membrane_state.area(state, p, xp=np)
    units = membrane_state.units(state, p, xp=np)
    rate = 0.04 * area[k] / H
    after, ok = trafficking.stage(state, H, np.asarray([rate]), p, True, xp=np)
    assert ok
    ratio = (area[k] - rate * H) / area[k]
    expected = units * ratio ** np.array([1.0, 0.5])
    np.testing.assert_allclose(membrane_state.units(after, p, xp=np), expected, rtol=1e-14)
    np.testing.assert_allclose(
        after.trafficking_internalised_units[0],
        np.array([20.0, 0.0]) + units - expected,
        rtol=1e-14,
    )
    pool = membrane_state.area(after, p, xp=np)[b]
    record = np.asarray(after.trafficking_internalised_units[0])
    rate = 0.1 * pool / H
    back, ok = trafficking.stage(after, H, np.asarray([rate]), p, False, xp=np)
    assert ok
    shrink = (pool - rate * H) / pool
    np.testing.assert_allclose(
        back.trafficking_internalised_units[0], record * shrink ** np.array([2.0, 1.0]), rtol=1e-14
    )
    returned = record - np.asarray(back.trafficking_internalised_units[0])
    np.testing.assert_allclose(
        membrane_state.units(back, p, xp=np),
        membrane_state.units(after, p, xp=np) + returned,
        rtol=1e-14,
    )


def test_a_unit_dropped_from_the_record_is_caught():
    spec, model, state, p = bind(cycle_world())
    _, _, units0 = totals(state, p)

    def drop(row):  # Planted: the record loses one Kir unit at every half-step.
        record = np.array(row.trafficking_internalised_units)
        record[0, 0] -= 1.0
        return row._replace(trafficking_internalised_units=record)

    rows = run_cycle(model, state, p, plant=drop)
    _, _, units = totals(rows[-1], p)
    assert units0[0] - units[0] == pytest.approx(len(rows) - 1, rel=1e-12)
    with pytest.raises(NumericalError, match="Membrane trafficking accounting failed"):
        model.check_values(history(rows), spec, steps=list(range(len(rows))))
