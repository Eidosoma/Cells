"""The passive permeation law's insertion point, with §7.5's exact booking (cells.passive_routes@1).

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
"""

import copy
import dataclasses

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import passive_routes
from cells.laws.electrochemistry import R
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.passive import passive_reference as reference
from validation.tissue import secreted_species_fixtures as fx

RATE = 100.0  # 1/s, k of the closed pair.
AREA = fx.CONTACT_AREA_M2
P = RATE / (1e15 * AREA * 2.0)  # V_a = V_b = 1 pL.


def closed_pair(*, node_mM=5e-4, pool_mM=1e-3, end=0.02, dt=1e-3, routes=None, wall_s=0.0):
    """W (fx.face_free) as a plain @3 definition, with passive routes on the contact patch."""
    raw = fx.face_free(pool_mM=pool_mM, node_mM=node_mM, end=end, dt=dt)
    m = raw["model"]
    m["id"] = "resolved_pump_tissue@3"
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
    assert end[0] + end[1] == pytest.approx(start[0] + start[1], rel=1e-14)  # Material.
    closed = reference.closed_pair(spec.experiment.end_time, *start, 1.0, 1.0, P * AREA)
    assert end[0] == pytest.approx(float(closed["n_a"]), rel=5e-4)  # The independent form.
    rt = 1e-3 * R * spec.model.temperature_K
    g = [n * (np.log(n) - 1.0) for n in (*start, *end)]  # V = 1 pL.
    decrease = rt * ((g[0] + g[1]) - (g[2] + g[3]))
    heat = float(final.passive_dissipated_energy_pJ[0])
    assert heat > 0 and heat == pytest.approx(decrease, rel=1e-10)  # Exact, to rounding.


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
