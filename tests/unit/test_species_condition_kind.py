"""cells.kind.species_condition@1 through the engine (G-5;
docs/IP3_RELEASE_AND_ASSEMBLY_AVAILABILITY_DESIGN.md, section 8).

The release world, plain @3 under IMEX, is cell_0 (0.5 pL) and its finite node_0 (0.05 pL), joined
by one patch that carries K and one charged Ca route (cells.route.passive_constant_field_permeation@1). The
route names two conditions at the cell, a ligand's (L, valence -3, an impermeant row) and calcium's
own (an activation and an inhibition), so the released calcium opens its own gate. On the host, no
compile:
- the gated flux is the closed form's, written without the law's kernels (planted: a wrong exponent,
  the forms exchanged, a missing factor, a wrong node, K in M, the row of another species);
- the released amount converges at second order (planted: a factor held at the step's start, first);
- L at -3 and at 0 is one run, bit for bit (planted: a reading scaled by |z|);
- the door refuses a factor outside [0, 1] and a NaN reading (planted: a factor above 1, one below
  0, a NaN read as 0), and the domain an infinite amount;
- a condition is a source of @3's channel slots too, two of them a left fold in the population's
  declared order (planted: the other order, which differs in the last bit);
- the feedback hooks feed the core's rule (section 5.5): its rate is the finite difference of the
  routed flux through the factor, at both ends, beside the ligand's pair, which closes no loop, and
  a channel slot's condition closes one as a route's does (planted: the held control, the ligand's
  pair, and for the division before the product, which is a NaN at a zero amount, a finite rate);
- beside operators, at the definition: admitted beside a compartment, the wash and labels, and water
  (read at its current volume), refused by name under RK4, beside replacement, trafficking, a closer
  and a retiring operator (planted hooks refused: bound_rate, moved_rows, rates); a loop is refused
  beside any operator that changes slots, whatever its kinds declare;
- a world that declares none keeps its definition, its structure and its program (D148).
Compiled, the store world (a composite of this file's own numbers: the same release from a
compartment, its ligand binding a buffer by cells.operator.local_species_reactions@1): ten steps in two windows, in
which the route's heat never falls and its factor is the closed form's, and a restart from a written
checkpoint that repeats the second window bit for bit (planted: a changed half-saturation is
refused).

Seconds: about 30 on a busy CPU, of which 16 are one compile (a window, which the resume reuses) and
the rest host steps and parses. The reason (D224): the kind's first runs in an IMEX step, in a
composite and from a checkpoint.
"""

import copy
import dataclasses
from functools import partial
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.windows import WindowPolicy, iter_windows
from cells.kinds import passive_routes
from cells.kinds import species_condition as species
from cells.laws.electrochemistry import F, R
from cells.laws.reactions import hill_product_factor as law
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump_v3 as tissue3
from cells.numerics import surface_imex as imex
from cells.operators import OPERATORS, membrane_state
from cells.records.io import load_snapshot, write_snapshot
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests.unit.test_neutral_arrival_labels import with_labels
from validation.tissue import compartment_fixtures as cf
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx
from validation.tissue import wash_schedule_fixtures as wfx

ROUTE = "cells.route.passive_constant_field_permeation@1"
AREA, PERMEABILITY = 1e-9, 3e-5  # m^2, m/s.
K_LIGAND, N_LIGAND = 1.5e-4, 2.0  # mM, 1.
K_ACT, N_ACT, K_INH, N_INH = 4e-3, 3.0, 2e-2, 2.0


def reading(row, form, half_saturation_mM, hill_coefficient):
    return dict(species=row, form=form, half_saturation_mM=half_saturation_mM,
                hill_coefficient=hill_coefficient)  # fmt: skip


def condition(name, reads, node="cell_0"):
    return dict(id=name, node=node, law=law.LAW_ID, reads=reads)


LIGAND = condition("ligand", [reading("L", "hill_activation", K_LIGAND, N_LIGAND)])
CALCIUM = condition(
    "calcium",
    [
        reading("Ca", "hill_activation", K_ACT, N_ACT),
        reading("Ca", "hill_inhibition", K_INH, N_INH),
    ],
)


def release(node, *, dt, steps, z=-3, conditions=(LIGAND, CALCIUM), permeability=PERMEABILITY):
    """The release world as a composite definition with no operators: cell_0 and `node`."""
    end = steps * dt
    raw = fx.world(
        cells=(("cell_0", 0.5),), nodes=((node, 0.05),), faces=(),
        contacts=(("contact_0", "cell_0", node),), dt=dt, end=end,
        observation_times=[0.0, end], concentrations_mM={"cell_0": 1e-3, node: 5e-4},
    )  # fmt: skip
    patch = next(p for p in raw["model"]["membranes"] if p["id"] == "contact_0")
    patch.update(area_m2=AREA, capacitance_F=1e-11)
    patch["permeability_m_per_s"]["K"] = 1e-7
    trace = partial(rfx.with_charged_trace, trace_mM=1e-9)
    raw = trace(raw, "Ca", 2, concentrations_mM={"cell_0": 2e-3, node: 0.2})
    raw = trace(raw, "L", z, concentrations_mM={"cell_0": 1e-4})
    route = dict(id="release_0", patch="contact_0", law=ROUTE, species="Ca",
                 permeability_m_per_s=permeability)  # fmt: skip
    if conditions:
        raw["model"]["species_conditions"] = copy.deepcopy(list(conditions))
        route["factors"] = [c["id"] for c in conditions]
    raw["model"]["passive_routes"] = [route]
    return raw


def floors(raw):
    """Every trace row's material floor at 1e-18 fmol, the ions' as they are."""
    ions = ("Na", "K", "Cl")
    raw["execution"]["material_balance_atol_fmol"] = {
        s["id"]: 1e-10 if s["id"] in ions else 1e-18 for s in raw["model"]["species"]
    }
    return raw


def tissue(*, dt=1e-4, steps=10, **changes):
    """The release world as a plain @3 definition."""
    raw = release("node_0", dt=dt, steps=steps, **changes)
    raw["model"]["id"] = "cells.model.resolved_pump_tissue@3"
    raw["model"].pop("inner_model")
    raw["model"].pop("operators")
    return floors(raw)


def host(raw):
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return spec, impl, state, p, control


def host_steps(raw, count):
    """(spec, implementation, layout, control, the states of `count` host steps and the start)."""
    spec, impl, state, p, control = host(raw)
    states = [state]
    for k in range(count):
        state, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert valid, k
        states.append(state)
    return spec, impl, p, control, states


def row_of(spec, name):
    return list(spec.model.species_ids).index(name)


def registry(**hooks):
    """The passive routes and the species condition with some of its hooks replaced, on one
    registry: what a planted error of this kind is."""
    out = kind_registry.KindRegistry()
    out.register(passive_routes.PASSIVE_ROUTES)
    out.register(dataclasses.replace(species.SPECIES_CONDITION, **hooks))
    return out


def bits(value):
    return np.asarray(value).tobytes()


def closed_form_factors(ligand_mM, calcium_mM):
    """The two conditions' factors, as plain powers."""
    f_ligand = ligand_mM**N_LIGAND / (K_LIGAND**N_LIGAND + ligand_mM**N_LIGAND)
    f_calcium = (
        calcium_mM**N_ACT / (K_ACT**N_ACT + calcium_mM**N_ACT)
        * K_INH**N_INH / (K_INH**N_INH + calcium_mM**N_INH)
    )  # fmt: skip
    return f_ligand, f_calcium


# ------------------------------------------------------------------ the flux and its order


def test_the_gated_flux_is_the_closed_form_s_and_each_plant_misses_it():
    spec, impl, p, control, states = host_steps(tissue(), 4)
    state, ca, ligand = states[-1], row_of(spec, "Ca"), row_of(spec, "L")
    n_cell = p.amount_reference + state.amount_increment
    n_node = p.extracellular_amount_reference + state.extracellular_amount_increment
    node = [o.id for o in spec.model.extracellular].index("node_0")
    c_in, c_out = n_cell[ca, 0] / 0.5, n_node[ca, node] / 0.05
    f_ligand, f_calcium = closed_form_factors(n_cell[ligand, 0] / 0.5, c_in)

    def flux(layout):
        values = impl.readouts(state, control, layout, xp=np)
        assert values.valid
        return float(values.derivative.passive_transferred[ca, 0]), values

    honest, values = flux(p)
    patch = [m.id for m in spec.model.membranes].index("contact_0")
    x = 2.0 * F * values.field.rates.membrane_voltage_V[patch] / (R * spec.model.temperature_K)
    assert abs(x) > 1e-3  # The voltage enters.
    inward, outward = x / np.expm1(x), -x / np.expm1(-x)
    expected = 1e15 * AREA * PERMEABILITY * f_ligand * f_calcium * (
        c_out * inward - c_in * outward)  # fmt: skip
    assert honest == pytest.approx(expected, rel=1e-12, abs=0)
    assert np.array_equal(
        species.factors(state, p, xp=np),
        np.asarray(impl.observe_history(
            np.zeros(1), impl.STATE_TYPE(*(np.asarray(v)[None] for v in state)), p, [0.0], spec
        ).species_condition_factor)[0],
    )  # fmt: skip
    k, n = p.species_condition_half_saturation_mM, p.species_condition_coefficient
    form, row = p.species_condition_form, p.species_condition_row
    first = np.zeros_like(form)
    first[0, 0] = 1  # The ligand's read.
    plants = {
        "a wrong exponent": dict(species_condition_coefficient=n + first),
        "the forms exchanged": dict(species_condition_form=np.where(form > 0, 3 - form, 0)),
        "a missing factor": dict(species_condition_form=np.where(first > 0, 0, form)),
        "a wrong node": dict(species_condition_node=p.species_condition_node + 1 + node),
        "K in M": dict(species_condition_half_saturation_mM=np.where(form > 0, 1e-3 * k, k)),
        "another species' row": dict(species_condition_row=row + first * (ca - ligand)),
    }
    for name, change in plants.items():
        assert abs(flux(p._replace(**change))[0] / expected - 1.0) > 1e-2, name


def held_factor(full):
    """The planted kind: the factor held at the step's start, in a state field the step books."""

    def initial(spec, declaration, layout):
        _, own = full.initial(spec, declaration, layout)
        start = SimpleNamespace(
            amount_increment=np.zeros_like(layout["amount_reference"]),
            extracellular_amount_increment=np.zeros_like(
                layout["extracellular_amount_reference"]),
        )  # fmt: skip
        values = full.factors(start, SimpleNamespace(**layout, **own), xp=np)
        return dict(held_factor=values), own

    def book(applied, start, end, control, p, dt, *, xp):
        return dict(held_factor=full.factors(end, p, xp=xp)), True

    return registry(
        state_axes=(("held_factor", (species.AXIS,)),), initial=initial, book=book,
        factors=lambda read, p, *, xp: read.held_factor, factor_rows=None,
        factor_log_slopes=None, readouts=None, readout_columns=(), view=None,
    )  # fmt: skip


def test_the_released_amount_is_second_order_and_a_held_factor_is_first():
    """1 ms at 100, 50 and 25 us, the factor moving from 0.11 to about 0.18."""

    def halving():
        moved = []
        for dt, count in ((1e-4, 10), (5e-5, 20), (2.5e-5, 40)):
            spec, _, _, _, states = host_steps(tissue(dt=dt, steps=count), count)
            moved.append(float(states[-1].passive_transferred[row_of(spec, "Ca"), 0]))
        return (moved[0] - moved[1]) / (moved[1] - moved[2])

    assert halving() == pytest.approx(4.0, rel=0.05)
    with kind_registry.scope(held_factor(species.SPECIES_CONDITION)):
        assert halving() == pytest.approx(2.0, rel=0.05)  # Plant.


def test_a_reading_does_not_see_the_row_s_charge():
    """L at -3 and at 0, each node's fixed charge balancing it: one run, bit for bit."""

    def trajectory(z):
        _, _, p, _, states = host_steps(tissue(z=z), 10)
        factors = [species.factors(s, p, xp=np) for s in states]
        return [bits(v) for v in (*states[-1], *factors)]

    assert trajectory(-3) == trajectory(0)

    def scaled(read, p, *, xp):  # Plant: the concentration times |z|, at a charged row.
        z = xp.abs(xp.reshape(p.valence, (-1,))[p.species_condition_row])
        log_x = species.log_concentration(read, p, xp=xp) + xp.log(xp.maximum(z, 1.0))
        return law.factor(
            log_x, p.species_condition_half_saturation_mM, p.species_condition_coefficient,
            p.species_condition_form, xp=xp,
        )  # fmt: skip

    with kind_registry.scope(registry(factors=scaled)):
        assert trajectory(-3) != trajectory(0)


# ------------------------------------------------------------------ the door


def routed(impl, read, control, p):
    """(the routed multiplier, valid) of the door at a stage's read."""
    kinds = tissue3._kinds(impl.structure)
    control, valid = tissue3._route(impl.structure, kinds, read, control, p, xp=np)
    return control, bool(valid)


def test_the_door_refuses_a_factor_outside_the_unit_interval_and_a_nan_reading():
    def with_calcium(state, p, amount):
        increment = np.array(state.amount_increment)
        increment[ca, 0] = amount - p.amount_reference[ca, 0]
        return state._replace(amount_increment=increment)

    def scaled(scale):  # The plants: the factor scaled once anything has moved.
        def factors(read, p, *, xp):
            moved = xp.any(read.amount_increment != 0)
            return xp.where(moved, scale, 1.0) * species.factors(read, p, xp=xp)

        return registry(factors=factors)

    spec, impl, state, p, control = host(tissue())
    ca, dt = row_of(spec, "Ca"), spec.execution.dt
    gate, valid = routed(impl, state, control, p)
    assert valid and gate.passive_multiplier[0] == np.prod(species.factors(state, p, xp=np))
    assert impl.imex_step(state, dt, control, p, xp=np)[1]
    for scale in (5.0, -1.0):  # Planted: above 1 and below 0, at the step's second stage.
        with kind_registry.scope(scaled(scale)):
            _, planted, start, layout, gates = host(tissue())
            assert routed(planted, start, gates, layout)[1]
            assert not planted.imex_step(start, dt, gates, layout, xp=np)[1]
    with kind_registry.scope(
        registry(factors=lambda r, q, *, xp: 5.0 * species.factors(r, q, xp=xp))
    ):
        with pytest.raises(ConfigError, match="domain invalid"):  # And at the definition.
            parse_spec(tissue())
    nan_as_zero = registry(factors=lambda r, q, *, xp: xp.nan_to_num(species.factors(r, q, xp=xp)))
    with np.errstate(all="ignore"):
        for bad in (np.nan, -1e-6):
            assert not routed(impl, with_calcium(state, p, bad), control, p)[1]
        # An infinite amount has a finite limit, 0 here: the domain refuses it, not the door.
        infinite = with_calcium(state, p, np.inf)
        assert routed(impl, infinite, control, p)[1]
        assert not impl.domain_valid(infinite, p, p.active, xp=np)
        with kind_registry.scope(nan_as_zero):  # Planted: a NaN read as 0, which the door admits.
            _, planted, start, layout, gates = host(tissue())
            assert routed(planted, with_calcium(start, layout, np.nan), gates, layout)[1]


def channel_world(factors=("gate_a", "gate_b"), *, name="gate_a"):
    """One heredity cell whose first channel population names two conditions at its cell."""
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    cell = raw["model"]["cells"][0]["id"]
    raw["model"]["species_conditions"] = [
        condition(name, [reading("K", "hill_activation", 130.0, 1.7)], cell),
        condition("gate_b", [reading("Na", "hill_inhibition", 9.0, 2.3)], cell),
    ]
    raw["model"]["channels"][0]["factors"] = list(factors)
    return raw


def test_a_channel_slot_takes_its_held_value_times_its_conditions_in_declared_order():
    spec, impl, state, p, control = host(channel_world())
    order = ((species.KIND_ID, 0), (species.KIND_ID, 1))
    assert impl.structure.routes == ((tissue3.OWN_SINK, "channel", 0, order),)
    f_a, f_b = species.factors(state, p, xp=np)
    _, backward, *_ = host(channel_world(("gate_b", "gate_a")))
    differs = 0
    for held in np.linspace(0.05, 0.95, 64):  # Availabilities: held x f_a x f_b, a left fold.
        channel = np.array(control.channel)
        channel[0] = held
        gates = control._replace(channel=channel)
        forward, valid = routed(impl, state, gates, p)
        assert valid and forward.channel[0] == (held * f_a) * f_b
        assert np.array_equal(forward.channel[1:], channel[1:])  # The one routed slot.
        other = routed(backward, state, gates, p)[0].channel[0]
        assert other == (held * f_b) * f_a
        differs += other != forward.channel[0]
    assert differs > 0  # The order matters, in the last bit: the plant "the other order" fails.
    assert 0.1 < f_a < 0.9 and 0.1 < f_b < 0.9 and f_a != f_b
    # A condition named as a channel population is refused: the model's IDs are unique.
    channel_id = channel_world()["model"]["channels"][0]["id"]
    with pytest.raises(ConfigError, match=f"condition '{channel_id}': its ID must be a name, uniq"):
        parse_spec(channel_world((channel_id, "gate_b"), name=channel_id))
    with pytest.raises(ConfigError, match="unknown factor sources"):
        parse_spec(channel_world(("gate_a", "gate_c")))


def test_a_condition_at_an_outside_node_reads_it_under_padded_capacities():
    """The node's index is past the cells' capacity, not their count (planted: past their count)."""
    lumen = condition("lumen", [reading("Ca", "hill_activation", 0.1, 2.0)], "node_0")
    raw = tissue(conditions=(lumen,))
    _, _, state, p, _ = host(raw)
    compact = species.factors(state, p, xp=np)
    assert compact[0] == pytest.approx(0.2**2 / (0.1**2 + 0.2**2), rel=1e-12)
    raw["execution"].update(capacity=3, extracellular_capacity=5)
    _, _, state, p, _ = host(raw)
    assert bits(species.factors(state, p, xp=np)) == bits(compact)
    with np.errstate(all="ignore"):  # Plant.
        wrong = p._replace(species_condition_node=p.species_condition_node - 2)
        assert bits(species.factors(state, wrong, xp=np)) != bits(compact)


# ------------------------------------------------------------------ the feedback hooks


def loop_rates(impl, read, potentials, control, p):
    """[node] the core's rate of the loops at a stage's read (surface_pump_v3)."""
    return tissue3.loop_material_rates(
        read, read, potentials, control, p, xp=np, structure=impl.structure,
        kinds=tissue3._kinds(impl.structure),
    )  # fmt: skip


def test_the_hooks_feed_the_core_s_feedback_rule():
    """The rule's own rows are the passive routes' (test_passive_routes_kind.py); here it reads this
    kind's two conditions."""
    spec, impl, state, p, control = host(tissue())
    ca, pair = row_of(spec, "Ca"), (species.KIND_ID, 1)  # The pairs: the ligand's, calcium's.
    # Names at binding: the route moves Ca, so calcium's pair closes a loop and the ligand's none.
    assert impl.structure.loops == (((0, 0), pair),)
    node = p.active.size + [o.id for o in spec.model.extracellular].index("node_0")
    layout = [getattr(p, name).tolist() for name in tissue3.LOOP_LAYOUT_FIELDS]
    assert layout == [[ca], [0], [ca], [0], [node]]
    potentials = impl.readouts(state, control, p, xp=np).field.potential_V

    def at(amount):
        """(the core's rate, the held control's, the ligand pair's (planted), the routed flux, the
        factors) with calcium at `amount` fmol in the cell."""
        reference = np.array(p.amount_reference)
        reference[ca, 0] = amount
        q = p._replace(amount_reference=reference)
        gate, valid = routed(impl, state, control, q)
        assert valid
        loops = (((0, 0), (species.KIND_ID, 0)),)
        ligand = SimpleNamespace(structure=dataclasses.replace(impl.structure, loops=loops))
        flux = passive_routes.routed_flux(state, potentials, gate, q, xp=np)
        return (
            loop_rates(impl, state, potentials, gate, q),
            loop_rates(impl, state, potentials, control, q),
            loop_rates(ligand, state, potentials, gate, q),
            float(flux[passive_routes.MULTIPLIER][ca, 0]),
            species.factors(state, q, xp=np),
        )

    n, h = float(p.amount_reference[ca, 0]), 1e-5
    rate, held, planted, flux, factors = at(n)
    up, down = (at(n * np.exp(s * h))[4][1] for s in (1, -1))
    through_factor = flux / factors[1] * (up - down) / (n * (np.exp(h) - np.exp(-h)))
    assert rate[0] > 1.0 and rate[0] == pytest.approx(abs(through_factor), rel=1e-7, abs=0)
    assert rate[node] == rate[0] and np.count_nonzero(rate) == 2  # Both ends of the row.
    # Planted: the held control, and the ligand's pair (which the route does not move).
    assert held[0] > 2 * rate[0] and planted[0] != pytest.approx(rate[0], rel=1e-2)
    # A trace: the routed rate is small, the held control's refuses any step (planted).
    trace = at(1e-9)
    assert trace[0][0] < 1e-3 and trace[1][0] > 1e6
    # Exactly zero: the product first is finite (the division first would be 0/0).
    with np.errstate(all="ignore"):  # ln 0, the source's, and the planted rates' overflow.
        rate, _, _, flux, factors = at(0.0)
    assert factors[1] == 0.0 and flux == 0.0 and not np.any(rate)
    # A channel slot is a sink as a route is: its population moves K at its cell and the held bath.
    spec, impl, state, p, control = host(channel_world())
    k = row_of(spec, "K")
    assert impl.structure.loops == (((0, 0), (species.KIND_ID, 0)),)
    assert p.loop_flux_end_a.tolist() == [0] and p.loop_flux_row.tolist() == [k]
    values = impl.readouts(state, control, p, xp=np)
    gate, _ = routed(impl, state, control, p)
    found = loop_rates(impl, state, values.field.potential_V, gate, p)
    slope = species.factor_log_slopes(state, p, xp=np)[0]
    moved = abs(float(values.derivative.channel_transferred[k, 0]))
    assert found[0] == pytest.approx(moved * slope / p.amount_reference[k, 0], rel=1e-12, abs=0)
    assert found[0] > 0 and found[1] == found[0]  # The bath's row, which material_rate drops.
    assert p.reservoir.tolist() == [True]


# ------------------------------------------------------------------ composition and D148


def composite(raw):
    return floors(cs.frozen_definition(raw))


def test_the_kind_s_place_beside_operators_is_admitted_or_refused_by_name():
    plain = tissue()
    stored = cf.with_compartments(
        floors(release("node_0", dt=1e-4, steps=10)),
        [cf.compartment(node="node_0", patch="contact_0")],
    )
    tracer = condition("tracer", [reading(fx.SPECIES, "hill_activation", 1e-3, 2.0)], "well")
    washed = wfx.with_wash(
        wfx.well(sites=False), ("well",), ((1.0, "well", 0.5, {wfx.TRACER: wfx.TRACE_mM}),)
    )
    washed["model"]["species_conditions"] = [tracer]
    for world in (
        stored,
        with_labels(composite(plain), [("K", ["base"], {})]),
        with_labels(composite(plain), [("Ca", ["base"], {})]),  # The row its route moves.
        washed,
    ):
        assert species.KIND_ID in dict(parse_spec(world).model.kinds)
    # Planted, each a hook that makes it more than a source: a compartment refuses one with a bound
    # rate, the wash one that moves its neutral row, and labels one with rates.
    moves = dict(moved_rows=lambda d: ((fx.SPECIES, "well"), (fx.SPECIES, "specimen")))

    def still(state, potentials, control, p, *, xp):  # Rates that move nothing.
        return kind_registry.KindRates(
            xp.zeros_like(state.amount_increment),
            xp.zeros_like(state.extracellular_amount_increment),
            {}, xp.zeros(()), xp.zeros(()),
        )  # fmt: skip

    for hooks, world, match in (
        (dict(bound_rate=lambda s, d: 0.0), stored, f"{species.KIND_ID}.*it has bound_rate"),
        (moves, washed, f"S may cross node well's surface by {species.KIND_ID}"),
        (
            dict(rates=still),
            with_labels(composite(plain), [("K", ["base"], {})]),
            f"{species.KIND_ID} has a rates hook and no label_refusals",
        ),
    ):
        with kind_registry.scope(registry(**hooks)):
            with pytest.raises(ConfigError, match=match):
                parse_spec(world)
    # Refused by name: RK4, an operator that builds today's fixed inner fields, a closer.
    fourth = copy.deepcopy(plain)
    fourth["execution"]["solver"] = "rk4"
    with pytest.raises(ConfigError, match=f"{species.KIND_ID}.* require an IMEX solver"):
        parse_spec(fourth)
    replaced = fx.face_free(end=0.004)
    replaced = fx.with_replacement(
        replaced, [fx.template(replaced, "cell_0", "t0")], [(0.002, "cell_0", "t0", "n1")]
    )
    assert parse_spec(replaced)
    replaced["model"]["species_conditions"] = [dict(tracer, node="cell_0")]
    with pytest.raises(ConfigError, match=f"not run beside declared kinds .{species.KIND_ID}"):
        parse_spec(replaced)
    # A closer, a retiring operator, and the three that build the inner fields in today's layout:
    # the structure check on the store's inner model refuses each, naming the kind.
    inner = get_model(parse_spec(stored).model).inner
    for changer, match in (
        ("cells.operator.isopotential_partition@1", "opens, closes or retires slots"),
        ("cells.operator.scheduled_membrane_insertion@2", "opens, closes or retires slots"),
        ("cells.operator.scheduled_cell_replacement@2", "today's fixed fields"),
        ("cells.operator.scheduled_membrane_trafficking@1", "today's fixed fields"),
    ):
        errors = pump_composite.structure_errors(inner, (OPERATORS[changer],))
        assert any(match in e and species.KIND_ID in e for e in errors), (changer, errors)
    reason, fields = adapter.kind_lifecycle_errors(species.SPECIES_CONDITION)
    assert reason == "roles" and set(fields) == set(
        species.LAYOUT_FIELDS
    )  # Why: no partition role.


def test_an_operator_that_changes_slots_is_refused_beside_a_loop(monkeypatch):
    """Every registered operator that opens, closes or retires slots, beside the store world whose
    release closes a loop and beside the same world without one. Today its kinds refuse such an
    operator too, for their roles; with those refusals planted away, as a kind that declares its
    roles passes them, the loop's refusal is the one that is left beside a closer."""

    def inner(*factors):
        raw = store()
        raw["model"]["passive_routes"][0]["factors"] = list(factors)
        return get_model(parse_spec(raw).model).inner

    loop, none = inner("ligand", "calcium"), inner("ligand")
    assert loop.structure.loops and none.structure.loops == ()
    masks, units = set(loop.MASK_FIELDS), OPERATORS[membrane_state.LAW_ID]
    changers = {
        name: op
        for name, op in OPERATORS.items()
        if op.CLOSES or op.RETIRES or masks & set(op.VIEW_FIELDS)
    }
    assert set(changers) == {
        law for law in pump_composite.SLOT_WRITERS if not OPERATORS[law].FIXED_INNER_FIELDS
    }  # The other slot writers build the inner fields in today's layout: refused beside any kind.
    refusal = "opens, closes or retires slots, and a routed slot closes a loop on its own gate"

    def errors(world, op):
        return pump_composite.structure_errors(world, (units, op))

    for op in changers.values():
        assert any(refusal in e for e in errors(loop, op))
    passed = lambda inner, kinds: dict.fromkeys(kinds, ())  # noqa: E731
    monkeypatch.setattr(pump_composite, "_kinds_lifecycle", passed)
    for name, op in changers.items():
        left = errors(none, op)
        (own,) = [e for e in errors(loop, op) if e not in left]
        assert own.startswith(f"{name} {refusal}")
        assert not left or not op.CLOSES  # Beside a closer it is the only wall.


def test_beside_water_a_reading_takes_the_current_volume():
    raw = water_fixtures.heredity_cell("H", solver=imex.ARS222_ID, end_time=0.01)
    cell = raw["model"]["cells"][0]["id"]
    raw = cs.frozen_definition(water_fixtures.with_water(raw))
    raw["model"]["species_conditions"] = [
        condition("gate", [reading("K", "hill_activation", 140.0, 2.0)], cell)
    ]
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    shrunk = state._replace(volume_increment_pL=-0.05 * p.volume)
    view, inner = model.view(p, shrunk, xp=np), model.inner.inner_state(shrunk)
    amount = float((p.amount_reference + shrunk.amount_increment)[row_of(spec, "K"), 0])
    volume = 0.95 * float(p.volume[0])
    assert float(view.volume[0]) == pytest.approx(volume, rel=1e-14)

    def hill(c):
        return c**2 / (140.0**2 + c**2)

    (f,) = species.factors(inner, view, xp=np)
    assert f == pytest.approx(hill(amount / volume), rel=1e-12)
    assert f != pytest.approx(hill(amount / float(p.volume[0])), rel=1e-3)  # Plant: the declared.


def step_program(raw, kinds):
    """A world under one kind registry: its definition, fingerprint, structure, type fields, traced
    step and one host step's bits."""
    with kind_registry.scope(kinds):
        spec, impl, state, p, control = host(raw)
        dt = spec.execution.dt
        traced = jax.make_jaxpr(lambda s, c, q: impl.imex_step(s, dt, c, q))(state, control, p)
        end, valid = impl.imex_step(state, dt, control, p, xp=np)
        assert valid
    return dict(
        definition=spec.to_dict(), fingerprint=spec.fingerprint, structure=impl.structure,
        fields=[*(type(v)._fields for v in (state, p, control)), impl.OBSERVATION_FIELDS],
        program=str(traced), step=[bits(v) for v in (*end, *p)],
    )  # fmt: skip


def test_a_world_that_declares_none_is_bit_for_bit_the_one_without_the_kind():
    """D148: the kind registered and undeclared, and not registered at all, give one definition, one
    structure, one program and one step (a world with a declared kind, the passive route, and one
    without any). Planted: the declared conditions, which the same comparison must see."""
    builtin = kind_registry.active()
    without = kind_registry.KindRegistry()
    for kind in builtin.model_keys().values():
        if kind.kind_id != species.KIND_ID:
            without.register(kind)
    raw = tissue(conditions=())
    today = step_program(raw, without)
    assert step_program(raw, builtin) == today
    assert not any(f.startswith("species_condition") for f in sum(today["fields"], ()))
    spec, impl, *values = host(tissue())  # Planted.
    fields = [*(type(v)._fields for v in values), impl.OBSERVATION_FIELDS]
    for planted, name in ((fields, "fields"), (impl.structure, "structure")):
        assert planted != today[name], name
    assert spec.to_dict() != today["definition"]
    spec = parse_spec(water_fixtures.heredity_cell("D", end_time=0.004))
    impl = get_model(spec.model)
    with kind_registry.scope(without):
        assert get_model(spec.model) is impl and impl.structure.kinds == ()


# ------------------------------------------------------------------ the store world, compiled


def store(*, dt=5e-5, steps=10):
    """The release world's route from a compartment, a composite: L binds a buffer in the cell."""
    raw = release("store_0", dt=dt, steps=steps, permeability=1e-6)
    trace = partial(rfx.with_charged_trace, trace_mM=1e-9)
    raw = trace(raw, "L_buffer", 0, concentrations_mM=dict(cell_0=1e-3))
    raw = trace(raw, "L_bound", -3, concentrations_mM=dict(cell_0=2e-4))
    raw = rfx.with_reactions(
        raw,
        [
            rfx.species("L", moieties={"L": 1}),
            rfx.species("L_buffer", moieties={"site": 1}),
            rfx.species("L_bound", moieties={"L": 1, "site": 1}, mu=-9.210340371976184),
        ],
        [
            rfx.passive(
                "binding", {"cells": ["cell_0"]}, {"L": 1, "L_buffer": 1}, {"L_bound": 1}, 2e4
            )
        ],
        [("binding", None, [(0.0, 1.0)])],
    )
    raw = cf.with_compartments(raw, [cf.compartment(node="store_0", patch="contact_0")])
    raw["experiment"]["observation_times"] = fx.grid_times(steps * dt, dt, dt)
    return floors(raw)


def test_the_store_world_runs_in_a_composite_and_restarts_bit_for_bit(tmp_path):
    spec, policy = parse_spec(store()), WindowPolicy(window_steps=5)
    windows = list(iter_windows(spec, policy))  # Two windows, every host check on every row.
    ca, ligand = row_of(spec, "Ca"), row_of(spec, "L")

    def history(name):  # The windows share their boundary row.
        first, second = (np.asarray(getattr(w.history, name)) for w in windows)
        return np.concatenate([first, second[1:]])

    def observed(name):
        return np.concatenate([np.asarray(getattr(w.observations, name)) for w in windows])

    heat = history("passive_dissipated_energy_pJ")[:, 0]
    moved = history("passive_transferred")[:, ca, 0]
    assert len(heat) == len(moved) == 11
    assert np.all(np.diff(heat) > 0) and np.all(np.diff(moved) > 0)  # Into the cell, dissipating.
    amount = observed("amount")[:, :, 0] / 0.5  # mM in the cell.
    expected = np.stack(closed_form_factors(amount[:, ligand], amount[:, ca]), axis=1)
    factors = observed("species_condition_factor")
    np.testing.assert_allclose(factors, expected, rtol=1e-12, atol=0)
    assert abs(factors[-1, 0] / factors[0, 0] - 1.0) > 1e-2  # The binding moves the ligand's.
    # A restart from a written checkpoint repeats the second window, bit for bit: no state.
    write_snapshot(tmp_path / "checkpoint", spec, windows[0].final)
    loaded = load_snapshot(tmp_path / "checkpoint")
    (resumed,) = iter_windows(loaded.spec, policy, loaded.checkpoint)
    for name in type(resumed.history)._fields:
        a, b = getattr(resumed.history, name), getattr(windows[1].history, name)
        assert bits(a) == bits(b), name
    column = resumed.observations.species_condition_factor
    assert bits(column[1:]) == bits(windows[1].observations.species_condition_factor)
    # The release closes a loop on its own gate, at both ends of its row, in the composite's layout.
    layout = loaded.checkpoint.layout
    loops = [getattr(layout, name).tolist() for name in tissue3.LOOP_LAYOUT_FIELDS]
    node = layout.active.size + [o.id for o in spec.model.extracellular].index("store_0")
    assert loops == [[ca], [0], [ca], [0], [node]]
    # Planted: the layout is saved and compared, so a changed K and a loop's other node are refused.
    for name, change in (
        ("species_condition_half_saturation_mM", lambda v: 2.0 * v),
        ("loop_pair_node", lambda v: v + node),
    ):
        planted = dataclasses.replace(
            loaded.checkpoint, layout=layout._replace(**{name: change(getattr(layout, name))})
        )
        with pytest.raises(ConfigError, match=f"Checkpoint layout {name} does not match"):
            list(iter_windows(loaded.spec, policy, planted))
