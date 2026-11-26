"""The passive permeation law's insertion point, with §7.5's exact booking (cells.kind.passive_routes@1).

docs/INNER_MODEL_V4_DESIGN.md §7.4 (i), §7.5 version 1, §11. The closed pair is FR-1's face-free
world W as a plain @3 definition: cell_0 (1 pL) and its finite node ecs_0 (1 pL), joined only by
the contact patch, and the neutral species S impermeant everywhere else, so S passes only between
them. One passive route on the contact patch carries S at k = 1e15 P A (1/V_a + 1/V_b) = 100/s.
- The pair relaxes as the independent closed form says, material is conserved, and the exact
  booking's heat is the engine's own free-energy decrease to rounding; every ledger passes.
- A trace start (1e-12 mM) is admitted; the tableau's booking of the same run is not.
- The raw-sum check's factor 16 holds on every honest step, and a planted sign flip on a minor
  route fails it; a step that moves S uphill has a negative share and is refused.
- A route on a row another route also moves keeps the tableau's booking, bitwise.
- Binding refuses a charged species and a host that carries the species itself; dt L > 1 is
  refused by the step checks.
- FR-34's readouts: a route that asks reads out the step's own flux and its share of the patch's
  current, for each of the four laws, and a world that does not ask keeps today's world.
- FR-15 F2's junction hosting (D310): the charged law refuses a junction that crosses a floating
  capacitor component, in the row that refused every junction host before; its junction rows are
  test_passive_routes_junctions.py's, so this file keeps its tier-2 cost (D224).
- A route gated by a row it moves closes a loop (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §6.5):
  its rate in the material rule is the stage's own slope through the factor, at both ends, finite at
  a zero amount, and the step is refused above it (planted, each caught: the slope dropped, a source
  on another node, the held control in place of the routed one). No loop, no layout field and no
  program for a row the route does not move, a held bath or a source without the hooks; a sink
  without them is refused by name where a loop would close; a hook of the wrong form too. On the
  host, about 4 s on a busy CPU: parses, NumPy stages and eleven small traces (D224).
"""

import copy
import dataclasses
import re

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import passive_routes, proton_buffer, species_condition
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R, bernoulli
from cells.laws.reactions import hill_product_factor
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from validation.compartment_ph_engine import definitions as fr
from validation.passive import passive_reference as reference
from validation.tissue import secreted_species_fixtures as fx

RATE = 100.0  # 1/s, k of the closed pair.
AREA = fx.CONTACT_AREA_M2
P = RATE / (1e15 * AREA * 2.0)  # V_a = V_b = 1 pL.


def closed_pair(*, node_mM=5e-4, pool_mM=1e-3, end=0.02, dt=1e-3, routes=None, wall_s=0.0):
    """W (fx.face_free) as a plain @3 definition, with passive routes on the contact patch."""
    raw = fx.face_free(pool_mM=pool_mM, node_mM=node_mM, end=end, dt=dt)
    m = raw["model"]
    m["id"] = "cells.model.resolved_pump_tissue@3"
    m.pop("inner_model")
    m.pop("operators")
    if wall_s:
        m["membranes"][0]["permeability_m_per_s"][fx.SPECIES] = wall_s
    m[passive_routes.MODEL_KEY] = routes or [route("leak_S", P)]
    return raw


def route(rid, permeability, *, host=("patch", "contact_0"), species=fx.SPECIES):
    """A neutral route in FR-4's form (validation/compartment_ph_engine/definitions.py)."""
    return {
        "id": rid,
        host[0]: host[1],
        "law": passive_routes.LAW_ID,
        "species": species,
        "permeability_m_per_s": permeability,
    }


def test_the_closed_pair_relaxes_with_its_exact_heat():
    spec = parse_spec(closed_pair())
    model = get_model(spec.model)
    assert [k for k, _ in model.structure.kinds] == [passive_routes.KIND_ID]
    result = run(spec)  # Host checks every row: material, energy (with the exact heat), heat >= 0.
    state, p = model.initial_values(spec)
    assert bool(p.passive_exact[0])
    s = list(spec.model.species_ids).index(fx.SPECIES)
    final = result.final.state
    start = (p.amount_reference[s, 0], p.extracellular_amount_reference[s, 1])  # cell_0, ecs_0.
    end = (
        start[0] + final.amount_increment[s, 0],
        start[1] + final.extracellular_amount_increment[s, 1],
    )
    # abs=0 throughout: approx's default abs of 1e-12 would hide a relative error in small values.
    assert end[0] + end[1] == pytest.approx(start[0] + start[1], rel=1e-14, abs=0)  # Material.
    closed = reference.closed_pair(spec.experiment.end_time, *start, 1.0, 1.0, P * AREA)
    assert end[0] == pytest.approx(float(closed["n_a"]), rel=5e-4, abs=0)  # The independent form.
    rt = 1e-3 * R * spec.model.temperature_K
    g = [n * (np.log(n) - 1.0) for n in (*start, *end)]  # V = 1 pL.
    decrease = rt * ((g[0] + g[1]) - (g[2] + g[3]))
    heat = float(final.passive_dissipated_energy_pJ[0])
    assert heat > 0 and heat == pytest.approx(decrease, rel=1e-10, abs=0)  # Exact, to rounding.


def test_a_trace_start_is_admitted_and_the_tableau_is_not():
    raw = closed_pair(node_mM=1e-12)
    run(parse_spec(raw))  # The exact booking: every ledger passes.
    tableau = dataclasses.replace(passive_routes.PASSIVE_ROUTES, book=None)
    kinds = kind_registry.KindRegistry()
    kinds.register(tableau)
    with kind_registry.scope(kinds):
        with pytest.raises(NumericalError, match="accounting failed: energy"):
            run(parse_spec(raw))


def host_step(raw):
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    end, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    return state, end, p, valid


def test_the_raw_sum_factor_holds_and_a_planted_sign_flip_fails():
    """Two routes on the patch, a major and a minor (1%). On honest steps, every exact row's raw
    sum is within 16 eps of its terms (the factor, confirmed here with its margin); flipping the
    minor route's recorded transfer misses the row's exact change by far more."""
    raw = closed_pair(routes=[route("major", P), route("minor", 0.01 * P)], node_mM=1e-12)
    start, end, p, valid = host_step(raw)
    assert valid
    residual, bound, rows = passive_routes.raw_sum_check(start, end, p)
    eps_terms = bound / passive_routes.RAW_SUM_FACTOR
    ratio = np.max(np.where(rows, residual / eps_terms, 0.0))
    assert ratio <= passive_routes.RAW_SUM_FACTOR, ratio  # The honest sums.
    heat, positive, within = passive_routes.exact_booking(start, end, p, xp=np)
    assert positive and within and np.all(heat > 0)
    moved = end.passive_transferred - start.passive_transferred
    flipped = moved.copy()
    flipped[:, 1] = -flipped[:, 1]  # The minor route's sign, planted.
    planted = end._replace(passive_transferred=start.passive_transferred + flipped)
    _, _, within = passive_routes.exact_booking(start, planted, p, xp=np)
    assert not within


SLOW = P / 1000  # dt k = 1e-4: the drained node stays drained over the test's steps.


def drained(left=0.015):
    """FR-5's arm R regime after its burst (fr45-next d9323e1a): ecs_0 holds `left` of its
    reference, the rest having passed into cell_0 through a major route and a minor one (1%). Its
    stored amount is then a small difference of a large reference and increment, and each route's
    cumulative transfer is large; the planted history is consistent (the increments are the
    routes' transfers). Returns (spec, model, state, p, control, s, node)."""
    raw = closed_pair(
        routes=[route("major", SLOW), route("minor", 0.01 * SLOW)], node_mM=0.0654, pool_mM=1e-3
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    s = list(spec.model.species_ids).index(fx.SPECIES)
    node = int(p.passive_outside[0]) - p.active.size
    burst = (1.0 - left) * p.extracellular_amount_reference[s, node]  # fmol, ecs_0 -> cell_0.
    share = p.passive_permeability[s] / p.passive_permeability[s].sum()
    cell, outside = state.amount_increment.copy(), state.extracellular_amount_increment.copy()
    cell[s, 0] += burst
    outside[s, node] -= burst
    moved = state.passive_transferred.copy()
    moved[s] += burst * share
    state = state._replace(
        amount_increment=cell, extracellular_amount_increment=outside, passive_transferred=moved
    )
    return spec, model, state, p, control, s, node


def test_the_raw_sum_bound_carries_its_inputs_rounding_after_a_burst():
    """§7.5's raw-sum bound with its inputs' term, in FR-5's arm R regime (drained above). The
    node's amount is reference + increment and each route's step transfer a difference of
    cumulative fields, so an honest residual carries |mu-bar| times their rounding, far above the
    row's own terms at its small amount. Every honest step of 300 is admitted with every exact row
    within its bound; before the inputs' term (17a3863b) this run was refused at its first step."""
    spec, model, state, p, control, _, _ = drained()
    worst = 0.0
    for step in range(300):
        end, valid = model.imex_step(state, spec.execution.dt, control, p, xp=np)
        residual, bound, rows = passive_routes.raw_sum_check(state, end, p)
        worst = max(worst, float(np.max(np.where(rows, residual / bound, 0.0))))
        assert valid, step
        state = end
    assert worst <= 1.0, worst


def test_the_raw_sum_bound_keeps_its_teeth_after_a_burst():
    """In the drained state the bound is loosest, and it still refuses: the minor route's planted
    sign flip, and an unrecorded transfer between the pair of 1e-6 or 1e-8 of the step's recorded
    one (a mover the booking does not see). The smallest unrecorded transfer it refuses at a row is
    that row's bound over |mu-bar|: here about 2e-15 fmol, 6e-10 of the step's 3.3e-6 fmol; it grows
    with the stored increments and cumulative transfers (the inputs' rounding)."""
    spec, model, start, p, control, s, node = drained()
    end, valid = model.imex_step(start, spec.execution.dt, control, p, xp=np)
    assert valid
    moved = end.passive_transferred - start.passive_transferred
    flipped = moved.copy()
    flipped[:, 1] = -flipped[:, 1]
    planted = end._replace(passive_transferred=start.passive_transferred + flipped)
    assert not passive_routes.exact_booking(start, planted, p, xp=np)[2]
    step = abs(float(moved[s].sum()))
    for fraction in (1e-6, 1e-8):
        cell, outside = end.amount_increment.copy(), end.extracellular_amount_increment.copy()
        cell[s, 0] -= fraction * step
        outside[s, node] += fraction * step
        unrecorded = end._replace(amount_increment=cell, extracellular_amount_increment=outside)
        assert not passive_routes.exact_booking(start, unrecorded, p, xp=np)[2], fraction
    _, bound, rows = passive_routes.raw_sum_check(start, end, p)
    volume, _ = passive_routes._volumes(p, np)
    mu = passive_routes.passive.divided_potential_RT(
        passive_routes._amounts(start, p, np),
        passive_routes._amounts(end, p, np),
        volume[None, :],
        xp=np,
    )
    smallest = float(np.max(np.where(rows, bound / np.abs(mu), 0.0)[s]))  # The looser row's.
    assert smallest < 1e-14 and smallest < 1e-8 * step, (smallest, step)


def test_a_negative_share_refuses_the_step():
    """S moved uphill, from the dilute node into the richer cell, with the transfer recorded as
    the change: the raw sums hold, the share is negative, and the booking refuses."""
    raw = closed_pair()
    start, _, p, _ = host_step(raw)
    s = list(p.passive_permeability[:, 0] > 0).index(True)
    uphill = 1e-6  # fmol moved inward (node -> cell), against the gradient.
    cell = start.amount_increment.copy()
    node = start.extracellular_amount_increment.copy()
    cell[s, 0] += uphill
    node[s, p.passive_outside[0] - p.active.size] -= uphill
    moved = start.passive_transferred.copy()
    moved[s, 0] += uphill
    end = start._replace(
        amount_increment=cell, extracellular_amount_increment=node, passive_transferred=moved
    )
    heat, positive, within = passive_routes.exact_booking(start, end, p, xp=np)
    assert within and not positive and heat[0] < 0
    _, valid = passive_routes.book(None, start, end, None, p, 1e-3, xp=np)
    assert not valid  # "negative exact share: step-bound breach"


def test_a_route_on_a_row_another_route_moves_keeps_the_tableau_booking():
    # The wall patch also moves S at cell_0. A slow route (dt k = 1e-3): at dt k = 0.1 the
    # tableau's booking itself misses the energy ledger, which is why exact booking exists.
    raw = closed_pair(wall_s=1e-9, routes=[route("leak_S", P / 100)])
    spec = parse_spec(raw)
    _, p = get_model(spec.model).initial_values(spec)
    assert not bool(p.passive_exact[0])
    booked = run(spec).final.state
    tableau = dataclasses.replace(passive_routes.PASSIVE_ROUTES, book=None)
    kinds = kind_registry.KindRegistry()
    kinds.register(tableau)
    with kind_registry.scope(kinds):
        plain = run(parse_spec(raw)).final.state
    for name in booked._fields:
        a, b = np.asarray(getattr(booked, name)), np.asarray(getattr(plain, name))
        assert a.tobytes() == b.tobytes(), name


def test_a_route_sharing_a_row_with_a_tableau_booked_route_is_not_exact():
    """§7.5's scope is rows that exact-booked routes alone move: a route on the wall patch (to the
    held bath: tableau-booked) shares S's cell row with the contact route, so neither is exact
    (the advisor's case; without the fixpoint the contact route was marked exact and its raw sums
    would refuse every step)."""
    wall = route("wall_S", P / 100, host=("patch", "wall_cell_0"))
    spec = parse_spec(closed_pair(routes=[route("leak_S", P), wall]))
    _, p = get_model(spec.model).initial_values(spec)
    assert p.passive_exact.tolist() == [False, False]  # Sorted by ID: leak_S, wall_S.
    spec = parse_spec(closed_pair(routes=[route("leak_S", P), route("leak_T", P / 2)]))
    _, p = get_model(spec.model).initial_values(spec)
    assert p.passive_exact.tolist() == [True, True]  # Two exact routes on the same rows.


def test_binding_refuses_charged_species_a_carrying_host_and_a_fast_route():
    with pytest.raises(ConfigError, match="neutral species only"):
        parse_spec(closed_pair(routes=[route("leak_K", P, species="K")]))
    raw = closed_pair()
    raw["model"]["membranes"][1]["permeability_m_per_s"][fx.SPECIES] = 1e-9  # contact_0 itself.
    with pytest.raises(ConfigError, match="has its own permeability for S"):
        parse_spec(raw)
    spec = parse_spec(closed_pair(routes=[route("fast", 20 * P)]))  # dt L = 2.
    with pytest.raises(ConfigError, match="a declared kind's explicit-rate bound"):
        surface_pump_v3.check_steps(spec, np.asarray([spec.execution.dt]), None)
    spec = parse_spec(closed_pair())
    surface_pump_v3.check_steps(spec, np.asarray([spec.execution.dt]), None)  # dt L = 0.1.
    assert copy.deepcopy(spec.to_dict())["model"][passive_routes.MODEL_KEY][0]["id"] == "leak_S"


# ------------------------------------------------------------------ FR-15 P2: the charged law


def charged(rid, permeability, *, species="X", host=("patch", "contact_0")):
    """A route of cells.route.passive_constant_field_permeation@1 (FR-15 P2) in FR-4's form."""
    return dict(route(rid, permeability, host=host, species=species), law=CHARGED)


CHARGED = passive_routes.CHARGED_LAW_ID


def charged_pair(
    *, voltage_fmol=0.0, pool_mM=1e-9, node_mM=5e-10, end=0.02, dt=1e-3, species="X", valence=-1
):
    """The closed pair with a trace row `species` (default the anion X, z = -1) on the contact
    patch under the charged law, and S as before; the pair's anchors carry +-voltage_fmol of
    charge, so the contact patch holds a voltage that no ion moves (every ion is impermeant here)
    and the trace barely changes."""
    raw = closed_pair(end=end, dt=dt, routes=[charged(f"charged_{species}", P, species=species)])
    raw = add_inventory_species(
        raw,
        species,
        trace_mM=fx.TRACE_mM,
        diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM=dict(cell_0=pool_mM, ecs_0=node_mM),
    )
    m = raw["model"]
    next(s for s in m["species"] if s["id"] == species)["valence"] = valence
    for node in (*m["cells"], *m["extracellular"]):  # Each node stays neutral.
        node["fixed_charge_equivalent_fmol"] -= valence * node["initial_amount_fmol"][species]
    cell = next(c for c in m["cells"] if c["id"] == "cell_0")
    node = next(o for o in m["extracellular"] if o["id"] == "ecs_0")
    cell["fixed_charge_equivalent_fmol"] += voltage_fmol
    cell["initial_charge_C"] += voltage_fmol * CHARGE_PER_FMOL  # The explicit anchor agrees.
    node["fixed_charge_equivalent_fmol"] -= voltage_fmol
    node["initial_charge_C"] -= voltage_fmol * CHARGE_PER_FMOL
    return raw


def crossing_junction_pair():
    """FR-15 F2's junction pair (test_passive_routes_junctions.py) with cell_b's component floating,
    so its junction crosses a floating capacitor component (D310)."""
    from tests.unit import test_passive_routes_junctions as junctions

    return junctions.junction_pair(crossing=True)


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda raw: raw["model"][passive_routes.MODEL_KEY][0].update(species=fx.SPECIES),
         "carries a charged row, not the neutral S"),
        (lambda raw: raw.clear() or raw.update(crossing_junction_pair()),
         "on junction j_ab, which joins two capacitor components where one floats"),
        (lambda raw: raw["model"]["membranes"][1]["permeability_m_per_s"].update(X=1e-9),
         "has its own permeability for X"),
    ],
    ids=["neutral row", "crossing junction", "host's own permeability"],
)  # fmt: skip
def test_the_charged_law_refuses_a_neutral_row_a_junction_and_a_second_law(change, message):
    """FR-15 P2's admission (host side): a charged row only, on a patch or a junction; on a
    junction, only one that joins no floating capacitor component (version 1, D310: the row that
    refused every junction host became the crossing junction's, as the lead sanctioned); and one
    law per species and route."""
    raw = charged_pair()
    change(raw)
    with pytest.raises(ConfigError, match=re.escape(message)):
        parse_spec(raw)


@pytest.mark.parametrize("species, valence", [("X", -1), ("H", 1)])
def test_a_charged_route_round_trips_its_species(species, valence):
    """to_dict keeps a charged route's species, the leak's default H included (the kinds owner's
    review: dropping it made the re-parse fail on species None). Host side."""
    spec = parse_spec(charged_pair(species=species, valence=valence))
    again = parse_spec(copy.deepcopy(spec.to_dict()))
    assert (
        dict(again.model.kinds)[passive_routes.KIND_ID]
        == dict(spec.model.kinds)[passive_routes.KIND_ID]
    )
    assert spec.to_dict()["model"][passive_routes.MODEL_KEY][0]["species"] == species


def test_the_charged_law_refuses_a_row_a_closure_holds():
    """FR-15 P2, fail-closed (the lead's rulings of 19 November 2026): the law reads amounts, so a
    row whose free/total split B4's closure owns (the FR-4 world's buffered proton row) is refused
    on it, by the species registry (check_amount_reading_routes, option (a)); the leak beside it
    reads free h through the closure as before."""
    raw = fr.declared_world(fr.fr4_world())
    routes = raw["model"][passive_routes.MODEL_KEY]
    routes.append(dict(id="charged_h", patch=fr.BOUNDING, law=CHARGED, species="H",
                       permeability_m_per_s=1e-9))  # fmt: skip
    with pytest.raises(
        ConfigError,
        match=r"species H at .* is held by .*cells.kind.rapid_proton_buffer@1.*reads amounts",
    ):
        parse_spec(raw)


@pytest.mark.parametrize("voltage_fmol", [0.0, -5.18e-5])
def test_a_charged_trace_row_relaxes_as_the_constant_field_closed_form(voltage_fmol):
    """FR-15 P2: a trace anion X (z = -1) on the contact patch under the charged law, with every
    check passing. Its charge moves the patch voltage by about 1 uV, so at the patch's held voltage
    V (0, and about -50 mV from the anchors) the flux is linear in the two amounts: dn_a/dt =
    k_b n_b - k_a n_a with k_a = A P B(-x)/V_a, k_b = A P B(x)/V_b (1e15 m^3 -> pL), x = z F V/RT,
    an exponential to its equilibrium n_a/n_b = k_b/k_a = e^-x, the independent closed form here.
    Material is conserved, the heat is >= 0, and the definition-only kind fields appear (the
    charged mask and the material term, which fails closed, +inf, where no potentials are given).
    Both rows take dt = 0.25 ms: at -50 mV the relaxation is 2.6 times faster, and one dt keeps
    the step's second-order error inside 5e-4 there and lets the second row reuse the first's
    compiled step (only the anchors differ, as data). One compile, about 11 s, for both rows."""
    spec = parse_spec(charged_pair(voltage_fmol=voltage_fmol, dt=2.5e-4))
    model = get_model(spec.model)
    bound = dict(model.structure.kinds)[passive_routes.KIND_ID]
    kind = kind_registry.bound(kind_registry.active().lookup(passive_routes.KIND_ID), bound)
    assert kind.material_term is not None and "passive_charged" in kind.layout_fields
    # Without potentials the material term fails closed: +inf at the charged route's two ends.
    start_state, layout = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    blind = np.asarray(kind.material_term(start_state, None, control, layout, xp=np))
    ends = [layout.passive_inside[0], layout.passive_outside[0]]
    assert np.isinf(blind[ends]).all() and not np.any(np.delete(blind, ends))
    result = run(spec)
    state, p = model.initial_values(spec)
    x_row = list(spec.model.species_ids).index("X")
    patch = [q.id for q in spec.model.membranes].index("contact_0")
    voltage = np.asarray(result.observations.membrane_voltage_V)[:, patch]
    assert np.ptp(voltage) < 1e-5  # The trace's own charge moves it by about 1 uV.
    v = float(voltage[0])
    if voltage_fmol:
        assert -0.06 < v < -0.04
    final = result.final.state
    start = (p.amount_reference[x_row, 0], p.extracellular_amount_reference[x_row, 1])
    end = (
        start[0] + final.amount_increment[x_row, 0],
        start[1] + final.extracellular_amount_increment[x_row, 1],
    )
    assert end[0] + end[1] == pytest.approx(start[0] + start[1], rel=1e-12, abs=0)
    x = -1 * F * v / (R * spec.model.temperature_K)
    rate = AREA * P * 1e15  # pL/s per pL of volume, before the Bernoulli factors (V = 1 pL).
    k_a, k_b = rate * float(bernoulli(-x, xp=np)), rate * float(bernoulli(x, xp=np))
    total, lam = start[0] + start[1], k_a + k_b
    expected = start[0] * np.exp(-lam * spec.experiment.end_time) + k_b * total / lam * (
        -np.expm1(-lam * spec.experiment.end_time)
    )
    assert end[0] == pytest.approx(expected, rel=5e-4, abs=0)
    assert float(final.passive_dissipated_energy_pJ[0]) > 0


# --------------------------------------------------------------- FR-34: the routes' readouts


def asking_worlds():
    """One world per law, each with a route asking for its readouts (FR-34): the closed pair's
    neutral route beside one that does not ask, the charged pair at its held -50 mV, the
    rectifier's pair, and FR-4's development world's proton leak."""
    from tests.unit import test_inward_rectifier_route as rectifier

    neutral = closed_pair(routes=[dict(route("leak_S", P), readout=True), route("quiet_S", P / 2)])
    charged = charged_pair(voltage_fmol=-5.18e-5, dt=2.5e-4)
    charged["model"][passive_routes.MODEL_KEY][0]["readout"] = True
    leak = fr.development_world(fr.fr4_world())
    for entry in leak["model"][passive_routes.MODEL_KEY]:
        entry["readout"] = True
    rectified = rectifier.closed_pair(rectifier.route(readout=True))
    return {"neutral": neutral, "charged": charged, "rectifier": rectified, "leak": leak}


@pytest.mark.parametrize("law", ("neutral", "charged", "rectifier", "leak"))
def test_an_asking_route_reads_out_the_steps_own_flux_and_its_share_of_the_current(law):
    """FR-34 (D251, D252): at the observed row each asking route's passive_flux_fmol_s is the rates
    hook's own flux, exactly (inward, as passive_transferred moves), and passive_current_A its
    share of the patch's membrane current (outward, A); a route that does not ask reads 0.
    clamped_flux at the row's own patch voltage gives the same values, and FR-34's control holds:
    half the availability, exactly half the current. Without the key the world keeps today's
    structure entry, its fields and its observation columns, and has no readouts hook. On the
    charged pair, the only mover, the route's current is the patch's own. Planted: with the
    flux's inward sign it is not. Each row parses one world and observes its start, without
    stepping: about 2 s each, the leak's FR-4 world the longest."""
    raw = asking_worlds()[law]
    spec = parse_spec(copy.deepcopy(raw))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    history = model.STATE_TYPE(*(np.asarray(v)[None] for v in state))
    observed = model.observe_history(np.zeros(1), history, p, [0.0], spec)
    structure = surface_pump_v3.structure(spec.model)
    values = surface_pump_v3.readouts(state, control, p, xp=np, structure=structure)
    potentials = np.asarray(values.field.potential_V)
    read = state
    if any(kind == proton_buffer.KIND_ID for kind, _ in structure.kinds):  # FR-4's stage read.
        read = proton_buffer.stage_read(state, p, xp=np)[0]
    rates = passive_routes.rates(read, potentials, control, p, xp=np)
    flux = np.asarray(rates.derivatives["passive_transferred"])
    asks = np.asarray(p.passive_readout)
    readout_flux = np.asarray(observed.passive_flux_fmol_s[0])
    readout_current = np.asarray(observed.passive_current_A[0])
    assert np.array_equal(readout_flux, np.where(asks[None, :], flux, 0.0))
    assert np.any(readout_flux != 0) and (law != "neutral" or not asks[1])
    volts = potentials[p.passive_inside] - potentials[p.passive_outside]
    clamped, current = passive_routes.clamped_flux(read, control, p, volts)
    assert np.array_equal(np.where(asks[None, :], clamped, 0.0), readout_flux)
    assert np.array_equal(np.where(asks, current, 0.0), readout_current)
    halved = control._replace(membrane=0.5 * control.membrane)
    assert np.array_equal(passive_routes.clamped_flux(read, halved, p, volts)[1], 0.5 * current)
    if law == "charged":  # Its one mover: the route's current is the patch's own.
        outward = np.asarray(observed.membrane_flux_fmol_s[0])[:, int(p.passive_membrane[0])]
        own = CHARGE_PER_FMOL * float(np.sum(np.asarray(p.valence)[:, 0] * outward))
        assert readout_current[0] == own != 0
        assert -readout_current[0] != own  # Planted: the flux's inward sign.
    bare = copy.deepcopy(raw)
    for entry in bare["model"][passive_routes.MODEL_KEY]:
        entry.pop(passive_routes.READOUT_KEY, None)
    bare_structure = surface_pump_v3.structure(parse_spec(bare).model)
    entry = dict(bare_structure.kinds)[passive_routes.KIND_ID]
    assert entry == tuple(sorted({r["law"] for r in raw["model"][passive_routes.MODEL_KEY]}))
    bound = kind_registry.bound(passive_routes.PASSIVE_ROUTES, entry)
    assert bound.readouts is None and bound.readout_columns == ()
    columns = surface_pump_v3.kind_types(bare_structure).OBSERVATION_FIELDS
    assert not set(passive_routes.READOUT_COLUMNS) & set(columns)


def test_the_readout_key_round_trips_states_its_records_and_refuses_a_non_boolean():
    """FR-34: the key is written back only where a route asks, the run view states each column's
    unit, kind and sign, and a value other than true or false is refused on both route forms.
    Parses only, about 2 s."""
    from cells.execution.state import initialise
    from cells.records import run_view
    from tests.unit import test_inward_rectifier_route as rectifier

    raw = asking_worlds()["neutral"]
    spec = parse_spec(copy.deepcopy(raw))
    declaration = dict(spec.model.kinds)[passive_routes.KIND_ID]
    assert passive_routes.to_dict(declaration) == raw["model"][passive_routes.MODEL_KEY]
    plan = run_view.prepare(spec, run_view.Request(), layout=initialise(spec).layout)
    view = plan.view(run_view.single_file_bases([0.0], [0.0]), "write_run")
    records = {r["field"]: r for r in view["records"]}
    flux, current = records["passive_flux_fmol_s"], records["passive_current_A"]
    assert (flux["unit"], flux["kind"]) == ("fmol/s", "rate")
    assert (current["unit"], current["kind"]) == ("A", "rate")
    assert (flux["sign"]["from"], flux["sign"]["to"]) == ("outside", "inside")
    assert (current["sign"]["from"], current["sign"]["to"]) == ("inside", "outside")
    run_view.validate(view)
    for bad in ("yes", 1):
        planted = copy.deepcopy(raw)
        planted["model"][passive_routes.MODEL_KEY][0][passive_routes.READOUT_KEY] = bad
        with pytest.raises(ConfigError, match="readout is true or false"):
            parse_spec(planted)
        rectified = rectifier.closed_pair(rectifier.route(readout=bad))
        with pytest.raises(ConfigError, match="readout is true or false"):
            parse_spec(rectified)


# ------------------------------------------------------------------ FR-50's one-way records
# fr50-one-way-records-v1 (D327): host rows, each judged by the tagged judge's own checks
# (validation/fr50/judge.py) against the builder's closed forms (validation/fr50/closed_forms.py),
# on the registered cases (validation/fr50/references/spec/cases.json). The compiled rows are
# tests/unit/test_one_way_records.py and test_one_way_records_transporter.py.


def _fr50():
    import json

    from validation.fr50 import closed_forms, engine, judge, plants

    cases = json.loads(judge.SPEC.read_text())["cases"]
    return cases, closed_forms, engine, judge, plants


def test_one_way_records_exist_only_where_a_route_asks():
    """D148: without the key the structure entry, the bound kind's fields and its two record hooks
    are today's; with it, OneWay, the records' fields, the mask and the hooks, and the key round
    trips through to_dict."""
    cases, _, engine, _, _ = _fr50()
    case = cases["K1_neutral_zero_net"]
    plain = parse_spec(engine.route_world(case, dt=0.1, end=0.1, one_way=False))
    asked = parse_spec(engine.route_world(case, dt=0.1, end=0.1))
    entries = [
        passive_routes.structure_entry(dict(s.model.kinds)[passive_routes.KIND_ID])
        for s in (plain, asked)
    ]
    assert entries[0] == (passive_routes.LAW_ID,) and isinstance(entries[1], passive_routes.OneWay)
    today = kind_registry.bound(passive_routes.PASSIVE_ROUTES, entries[0])
    recorded = kind_registry.bound(passive_routes.PASSIVE_ROUTES, entries[1])
    assert today.state_axes == passive_routes.STATE_AXES and today.one_way_records == ()
    assert today.one_way_fluxes is None and today.one_way_nets is None
    assert "passive_one_way" not in today.layout_fields
    assert recorded.one_way_records == (passive_routes.ONE_WAY_RECORD,)
    assert recorded.state_axes == passive_routes.STATE_AXES + passive_routes.ONE_WAY_STATE_AXES
    assert recorded.one_way_fluxes is passive_routes.record_fluxes
    declared = dict(asked.model.kinds)[passive_routes.KIND_ID]
    assert passive_routes.to_dict(declared)[0][passive_routes.ONE_WAY_KEY] is True
    assert passive_routes.ONE_WAY_KEY not in passive_routes.to_dict(
        dict(plain.model.kinds)[passive_routes.KIND_ID]
    )[0]
    bad = engine.route_world(case, dt=0.1, end=0.1)
    bad["model"][passive_routes.MODEL_KEY][0][passive_routes.ONE_WAY_KEY] = 1
    with pytest.raises(ConfigError, match="one_way is true or false"):
        parse_spec(bad)


def test_k3_the_charged_routes_one_way_fluxes_meet_ussing_and_the_swap_plant_fails():
    """K3 at the four registered voltages (check_k3: each direction and inward/outward within
    1e-12); plant K3, B(x) and B(-x) exchanged, fails at every nonzero voltage and only there."""
    cases, closed_forms, engine, judge, _ = _fr50()
    reference = closed_forms.k3("K3_charged_kernel", cases["K3_charged_kernel"])
    request = judge.request_for(reference)
    honest = judge.check_k3(reference, engine.engine(request))
    assert honest["passed"], honest
    planted = engine.engine(dict(request, plant="K3_bernoulli_exchanged"))
    per = judge.check_k3(reference, planted)["per_voltage"]
    assert [v["passed"] for v in per] == [v["zero"] for v in per] == [False, False, True, False]


def _host_rows(engine, world, steps, dt):
    """The K1 route's rows (n, F, B, net, gap) over `steps` NumPy steps of @3 at dt."""
    spec = parse_spec(world)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    s = list(spec.model.species_ids).index(fx.SPECIES)
    rows = {q: [] for q in ("n", "F", "B", "net", "gap")}
    for n in range(steps + 1):
        if n:
            state, valid = impl.imex_step(state, dt, control, p, xp=np)
            assert bool(valid)
        values = (
            n,
            state.passive_inward_fmol[0],
            state.passive_outward_fmol[0],
            state.passive_transferred[s, 0],
            state.passive_one_way_gap_relative[0],
        )
        for q, value in zip(rows, values, strict=True):
            rows[q].append(value)
    return {q: np.asarray(v, dtype=np.int64 if q == "n" else np.float64) for q, v in rows.items()}


@pytest.mark.parametrize(
    "plant,failed",
    [(None, []), ("K1a_backward_halved", ["K1-2"]), ("K1b_both_halved", ["K1-1"])],
)
def test_k1_plants_fail_only_their_criterion(plant, failed):
    """K1 on ten host steps at 0.1 s, by the judge's checks: honest, it passes K1-1, K1-2 and
    K1-3. Plant (a), the backward kernel halved: the rule restores the records from the booked net
    (K1-1 and closure pass) and the gap shows it, r = 1/3 (K1-2 fails). Plant (b), both halved:
    no gap, and the records are half (K1-1 fails)."""
    cases, closed_forms, engine, judge, plants = _fr50()
    case = cases["K1_neutral_zero_net"]
    reference = closed_forms.k1("K1_neutral_zero_net", case, times=("0", "0.5", "1.0"))
    with plants.planted(plant):
        rows = _host_rows(engine, engine.route_world(case, dt=0.1, end=1.0), 10, 0.1)
    results = {
        "K1-1": judge.check_absolute(reference, rows, "0.1"),
        "K1-2": judge.check_gap(rows),
        "K1-3": judge.check_closure(rows),
    }
    assert sorted(k for k, r in results.items() if not r["passed"]) == failed
    if plant == "K1a_backward_halved":
        assert abs(float(results["K1-2"]["worst"]) - 1 / 3) <= 1e-12


def test_k5_every_one_way_refusal_names_its_cause_and_its_control_is_admitted():
    """K5's four rows (the engine adapter's worlds; the judge's erratum 1 for RK4's control): a
    rectifier route, a net-flow population, RK4 and a slot-changing operator, each refused with
    its reason, naming one_way, where the same world without the cause is admitted."""
    _, _, engine, judge, _ = _fr50()
    results = judge.check_refusals("K5", engine.engine(dict(kind="K5", plant=None)))
    assert all(row["passed"] for row in results.values()), results


def test_an_unresolved_step_marks_the_record_and_refuses_nothing(monkeypatch):
    """FR-50's passive records (the lead's ruling, 24 November 2026): where a step's end-of-step
    solve fails (planted: the third step's reports no convergence), the step is not refused and
    every other field is the unrecorded twin's, bit for bit. The record keeps its value for that
    step, and its gap becomes ONE_WAY_UNRESOLVED (2, above r's [0, 1]) and stays there. So the
    tagged judge fails closed on it: its gap and absolute checks fail."""
    cases, closed_forms, engine, judge, _ = _fr50()
    case = cases["K1_neutral_zero_net"]
    honest, calls = surface_pump_v3.crossing_view, []

    def third_fails(*args, **kwargs):
        view, valid = honest(*args, **kwargs)
        calls.append(None)
        return view, (False if len(calls) == 3 else valid)

    monkeypatch.setattr(surface_pump_v3, "crossing_view", third_fails)
    states = []
    for one_way in (True, False):
        spec = parse_spec(engine.route_world(case, dt=0.1, end=1.0, one_way=one_way))
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        run_states = [state]
        for _ in range(10):
            state, valid = impl.imex_step(state, 0.1, control, p, xp=np)
            assert bool(valid)
            run_states.append(state)
        states.append(run_states)
    recorded, twin = states
    for a, b in zip(recorded, twin, strict=True):
        for name in type(b)._fields:
            assert np.asarray(getattr(a, name)).tobytes() == np.asarray(getattr(b, name)).tobytes()
    s = list(spec.model.species_ids).index(fx.SPECIES)
    rows = {
        "n": np.arange(11),
        "F": np.asarray([x.passive_inward_fmol[0] for x in recorded]),
        "B": np.asarray([x.passive_outward_fmol[0] for x in recorded]),
        "net": np.asarray([x.passive_transferred[s, 0] for x in recorded]),
        "gap": np.asarray([x.passive_one_way_gap_relative[0] for x in recorded]),
    }
    assert rows["F"][3] == rows["F"][2] and rows["F"][4] > rows["F"][3]
    assert np.all(rows["gap"][:3] == 0.0) and np.all(rows["gap"][3:] == 2.0)
    assert surface_pump_v3.ONE_WAY_UNRESOLVED == 2.0
    reference = closed_forms.k1("K1_neutral_zero_net", case, times=("0", "0.5", "1.0"))
    assert not judge.check_gap(rows)["passed"]
    assert not judge.check_absolute(reference, rows, "0.1")["passed"]


# -------------------------------------------------------- a factor's feedback (calcium note, §6.5)

SOURCE = species_condition.SPECIES_CONDITION
SINK = passive_routes.PASSIVE_ROUTES


def gated_pair(reads=("X", "cell_0"), form="hill_activation", host="contact_0"):
    """The charged pair at its held -50 mV, its route (on `host`) gated by a condition that reads
    one species at one node. X is a trace, so its amounts bind and not its charge, and 20 times less
    in the cell than at the node: the contact route moves it into the cell."""
    raw = charged_pair(voltage_fmol=-5.18e-5, pool_mM=1e-8, node_mM=2e-7, dt=1e-4)
    species, node = reads
    read = dict(species=species, form=form, half_saturation_mM=1e-8, hill_coefficient=5.0)
    law = hill_product_factor.LAW_ID
    raw["model"]["species_conditions"] = [dict(id="gate", node=node, law=law, reads=[read])]
    raw["model"][passive_routes.MODEL_KEY][0].update(factors=["gate"], patch=host)
    return raw


def both(source=SOURCE, sink=SINK):
    """The two kinds on one registry: a planted error replaces one's hooks."""
    kinds = kind_registry.KindRegistry()
    kinds.register(sink)
    kinds.register(source)
    return kind_registry.scope(kinds)


def without(kind):
    """A kind without its side's feedback hooks."""
    hooks = ("factor_rows", "factor_log_slopes") if kind is SOURCE else ("routed_rows",
                                                                         "routed_flux")  # fmt: skip
    return dataclasses.replace(kind, **dict.fromkeys(hooks))


def gated_start(raw):
    """(spec, implementation, state, control, layout, potentials, X's row) at the start."""
    spec = parse_spec(raw)
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    potentials = impl.readouts(state, control, p, xp=np).field.potential_V
    return spec, impl, state, control, p, potentials, list(spec.model.species_ids).index("X")


def stage_parts(impl, state, control, p, potentials):
    """([node] the passive kind's material term, [node] the loops') at a stage, and the loops' with
    the held control in place of the routed one."""
    kinds = surface_pump_v3._kinds(impl.structure)
    routed, _ = surface_pump_v3._route(impl.structure, kinds, state, control, p, xp=np)
    (passive,) = [k for k in kinds if k.kind_id == passive_routes.KIND_ID]

    def loops(gates):
        return surface_pump_v3.loop_material_rates(
            state, state, potentials, gates, p, xp=np, structure=impl.structure, kinds=kinds
        )

    term = passive.material_term(state, potentials, routed, p, xp=np)
    return np.asarray(term), loops(routed), loops(control)


@pytest.mark.parametrize("form", ("hill_activation", "hill_inhibition"))
def test_a_loop_s_rate_is_the_stage_s_own_slope_through_the_factor(form):
    """d(dn/dt)/dn of X at the cell, by a central difference of the stage's own derivative, is the
    direct slope (the closed form's) and the part through the factor; that part is the engine's
    rate, at both ends. Under an inhibition the two add, so the whole rule is the block's own
    eigenvalue; under an activation the rule is no less. Then the step itself."""
    spec, impl, state, control, p, potentials, x = gated_start(gated_pair(form=form))
    n, node = p.active.size, 1
    assert impl.structure.loops == (((0, 0), (species_condition.KIND_ID, 0)),)
    h = 1e-5

    def derivative(cell, outside):
        inner, outer = np.array(p.amount_reference), np.array(p.extracellular_amount_reference)
        inner[x, 0] *= 1 + cell
        outer[x, node] *= 1 + outside
        moved = p._replace(amount_reference=inner, extracellular_amount_reference=outer)
        rates, _ = impl.explicit_rates(state, potentials, control, moved, xp=np)
        return np.array(
            [rates.amount_increment[x, 0], rates.extracellular_amount_increment[x, node]]
        )

    amounts = p.amount_reference[x, 0], p.extracellular_amount_reference[x, node]
    by_cell = (derivative(h, 0) - derivative(-h, 0)) / (2 * h * amounts[0])
    by_node = (derivative(0, h) - derivative(0, -h)) / (2 * h * amounts[1])
    factor = species_condition.factors(state, p, xp=np)[0]
    v = potentials[0] - potentials[n + node]
    assert -0.06 < v < -0.04
    drive = -1 * F * v / (R * spec.model.temperature_K)
    direct = AREA * P * 1e15 * factor * float(bernoulli(-drive, xp=np))  # V = 1 pL.
    through = np.abs(by_cell + np.array([direct, -direct]))
    term, loops, held = stage_parts(impl, state, control, p, potentials)
    assert loops[[0, n + node]] == pytest.approx(through, rel=1e-6, abs=0)
    assert not np.any(np.delete(loops, [0, n + node])) and loops[0] > 2 * direct
    rate = float(impl.material_rate(state, control, p, xp=np, potentials=potentials))
    assert rate == pytest.approx((term + loops).max(), rel=1e-14, abs=0)
    fastest = abs(by_cell[0] + by_node[1])  # The other eigenvalue is 0: X is conserved.
    assert rate >= fastest * (1 - 1e-8)
    if form == "hill_inhibition":
        assert rate == pytest.approx(fastest, rel=1e-6, abs=0)
    assert held[0] > 1.5 * loops[0]  # Planted: the held control, whose flux holds no factor.
    charge = float(impl.membrane_rate(state, control, p, xp=np, potentials=potentials))
    assert charge < 0.5 * rate
    for scale, admitted in ((0.9, True), (1.1, False)):
        assert bool(impl.imex_step(state, scale / rate, control, p, xp=np)[1]) is admitted
    blind = loops_without_potentials(impl, state, control, p)
    assert np.isinf(blind[[0, n + node]]).all() and not np.any(np.delete(blind, [0, n + node]))
    with both(source=without(SOURCE)):  # Planted: the slope dropped, the same step admitted.
        _, planted, start, gates, layout, *_ = gated_start(gated_pair(form=form))
        assert planted.structure.loops == ()
        assert bool(planted.imex_step(start, 1.1 / rate, gates, layout, xp=np)[1])
    far = dataclasses.replace(SOURCE, factor_rows=lambda declaration: ((("X", "ecs_0"),),))
    with both(source=far):  # Planted: a source on another node.
        _, planted, start, gates, layout, at, _ = gated_start(gated_pair(form=form))
        _, wrong, _ = stage_parts(planted, start, gates, layout, at)
        assert wrong[0] < 0.2 * loops[0]


def loops_without_potentials(impl, state, control, p):
    return surface_pump_v3.loop_material_rates(
        state, state, None, control, p, xp=np, structure=impl.structure,
        kinds=surface_pump_v3._kinds(impl.structure),
    )  # fmt: skip


def test_a_loop_s_rate_is_finite_at_a_zero_amount_and_small_at_a_trace():
    """J and n are both 0 at a zero amount: the product first, 0 over the smallest normal float, is
    0 (the division first is 0 times infinity, a NaN, at this coefficient). At a millionth of K the
    held control's rate would refuse any step (planted), the routed one's is small."""
    _, impl, state, control, p, potentials, x = gated_start(gated_pair())

    def at(amount):
        reference = np.array(p.amount_reference)
        reference[x, 0] = amount
        with np.errstate(all="ignore"):  # ln 0, the source's, and the planted rate's overflow.
            return stage_parts(
                impl, state, control, p._replace(amount_reference=reference), potentials
            )

    _, loops, _ = at(0.0)
    assert np.isfinite(loops).all() and not np.any(loops)
    _, loops, held = at(1e-14)
    assert 0 < loops[0] < 1e-6 and held[0] > 1e6


EMPTY = {  # What the gate reads, the route's host, and the source: no loop in any.
    "a row the route does not move": ((fx.SPECIES, "cell_0"), "contact_0", SOURCE),
    "a node that is no end of it": (("X", "bath"), "contact_0", SOURCE),
    "a held bath": (("X", "bath"), "wall_cell_0", SOURCE),
    "a source without the hooks": (("X", "cell_0"), "contact_0", without(SOURCE)),
}


@pytest.mark.parametrize("name", sorted(EMPTY))
def test_no_loop_no_layout_field_and_no_program(name):
    """Each world has the structure, the layout's fields and the rule's program that the same world
    has where neither side has the hooks (D148); a sink without them is admitted there."""
    reads, host, source = EMPTY[name]

    def traced(**kinds):
        with both(**kinds):
            _, impl, state, control, p, potentials, _ = gated_start(gated_pair(reads, host=host))
            assert impl.structure.loops == ()
            rule = jax.make_jaxpr(lambda s, c, q, v: impl.material_rate(s, c, q, potentials=v))
            return impl.structure, type(p)._fields, str(rule(state, control, p, potentials))

    given = traced(source=source)
    assert given == traced(source=without(SOURCE), sink=without(SINK))
    assert not any(field.startswith("loop_") for field in given[1])
    if source is SOURCE:
        assert given == traced(sink=without(SINK))


def flux_of(change):
    """The sink with its routed_flux's result changed."""

    def routed_flux(read, potentials, control, p, *, xp):
        return change(SINK.routed_flux(read, potentials, control, p, xp=xp))

    return dataclasses.replace(SINK, routed_flux=routed_flux)


def slopes_of(change):
    """The source with its factor_log_slopes' result changed."""
    return dataclasses.replace(
        SOURCE, factor_log_slopes=lambda read, p, *, xp: change(
            SOURCE.factor_log_slopes(read, p, xp=xp)
        ),
    )  # fmt: skip


NAME = passive_routes.MULTIPLIER
REFUSED = {
    "a sink without the hooks": (
        dict(sink=without(SINK)),
        f"{passive_routes.KIND_ID} routes {NAME}[0], which 'gate' drives from X at cell_0, but "
        "declares no routed_flux: the loop has no bound",
    ),
    "slopes of another shape": (
        dict(source=slopes_of(lambda v: v[:, None])), "factor_log_slopes must be float64 (1,), not",
    ),
    "slopes in float32": (
        dict(source=slopes_of(lambda v: v.astype(np.float32))),
        "factor_log_slopes must be float64 (1,), not float32 (1,)",
    ),
    "fluxes that are no mapping": (
        dict(sink=flux_of(lambda v: v[NAME])), f"routed_flux of {NAME} must be float64 (",
    ),
    "fluxes of another field": (
        dict(sink=flux_of(lambda v: {"other": v[NAME]})), f"routed_flux of {NAME} must be float64",
    ),
    "fluxes of another shape": (
        dict(sink=flux_of(lambda v: {NAME: v[NAME][0]})), f"routed_flux of {NAME} must be float64",
    ),
    "a moved row of no declared node": (
        dict(sink=dataclasses.replace(SINK, routed_rows=lambda d: ((("X", "cell_0", "q"),),))),
        "routed_rows names 'q', which the model does not declare",
    ),
    "a read row of no declared species": (
        dict(source=dataclasses.replace(SOURCE, factor_rows=lambda d: ((("Q", "cell_0"),),))),
        "factor_rows names 'Q', which the model does not declare",
    ),
    "a malformed moved row": (
        dict(sink=dataclasses.replace(SINK, routed_rows=lambda d: ((("X", "cell_0"),),))),
        f"feedback hooks are refused: Kind {passive_routes.KIND_ID}'s routed_rows, {NAME}[0]",
    ),
}  # fmt: skip


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_a_hook_of_the_wrong_form_and_a_sink_without_its_hooks_are_refused_by_name(name):
    kinds, message = REFUSED[name]
    with both(**kinds), pytest.raises(ConfigError, match=re.escape(message)):
        parse_spec(gated_pair())
