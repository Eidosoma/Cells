"""The routing door and its sink in the passive routes (docs/INNER_MODEL_V4_DESIGN.md §7.4 (n)).

Planted kinds from tests/kind_fixtures.py: `tests.kind.factor@1` exposes constant factors per source
ID (from its layout), and `tests.kind.sink@1` routes slots of its control `sink_gain` through named
sources. On the host:
- at a stage, a routed slot is its held value times its sources' factors, a left fold in
  declared order, and every kind's hooks receive it; `book` receives the held control;
- a factor outside [0, 1] refuses the definition, and the step at a stage;
- binding refuses an unknown source, a source two kinds expose, a slot routed twice, a field the
  sink does not own and a slot outside its field;
- without a sink the door is absent: no routes, and no factor is evaluated;
- the passive routes as the sink: a factored route's flux is the unfactored flux times the
  product of its factors, and the multiplier exists only where a route declares factors (a
  declaration without factors keeps today's entry and classes).
Through the runner (the closed pair of test_passive_routes_kind.py): a factored cargo route keeps
its exact booking, with heat equal to the free-energy decrease, at the rate the factor gives.
"""

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.kinds import passive_routes
from cells.laws.electrochemistry import R
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from tests.unit.test_passive_routes_kind import AREA, P, closed_pair, route
from validation.passive import passive_reference as reference
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import secreted_species_fixtures as fx

HELD = (0.9, 1.0)
FACTORS = {"f_a": 0.5, "f_b": 0.8, "f_c": 0.3}


def registry(*more):
    return kf.registry(kf.factor_source(), kf.SINK, *more)


def heredity(**kwargs):
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    return kf.declare_routing(raw, factors=FACTORS, held=HELD, **kwargs)


def host(spec):
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return impl, state, p, control


def observed_gain(spec):
    """The sink's readout column at t = 0: the control its hooks receive at the observed row."""
    impl, state, p, _ = host(spec)
    history = impl.STATE_TYPE(*(np.asarray(v)[None] for v in state))
    observations = impl.observe_history(np.zeros(1), history, p, [0.0], spec)
    return np.asarray(observations.sink_gain_column)[0]


def test_a_routed_slot_is_held_times_the_left_fold_of_its_factors():
    routes = ((0, ("f_a",)), (1, ("f_b", "f_c")))
    with kind_registry.scope(registry()):
        spec = parse_spec(heredity(routes=routes))
        impl = get_model(spec.model)
        assert impl.structure.routes == (
            (kf.SINK_ID, "sink_gain", 0, ((kf.FACTOR_ID, 0),)),
            (kf.SINK_ID, "sink_gain", 1, ((kf.FACTOR_ID, 1), (kf.FACTOR_ID, 2))),
        )
        gain = observed_gain(spec)
    assert gain[0] == HELD[0] * FACTORS["f_a"]
    assert gain[1] == (HELD[1] * FACTORS["f_b"]) * FACTORS["f_c"]  # The left fold.


def test_book_receives_the_held_control():
    with kind_registry.scope(registry()):
        spec = parse_spec(heredity(routes=((0, ("f_a",)),)))
        impl, state, p, control = host(spec)
        kf.SEEN.clear()
        _, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
    assert valid and kf.SEEN
    assert list(np.asarray(kf.SEEN[-1].sink_gain)) == list(HELD)  # Not the routed 0.45.


def test_a_factor_outside_the_unit_interval_refuses():
    with kind_registry.scope(registry()):
        with pytest.raises(ConfigError, match="domain invalid"):
            parse_spec(_bad_factor())
        spec = parse_spec(heredity(routes=((0, ("f_a",)),)))
        impl, state, p, control = host(spec)
        _, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert valid
        bad = p._replace(test_factors_values=np.asarray([0.5, 1.5, 0.3]))  # Unrouted f_b too.
        _, valid = impl.imex_step(state, spec.execution.dt, control, bad, xp=np)
        assert not valid
        nan = p._replace(test_factors_values=np.asarray([np.nan, 0.8, 0.3]))
        _, valid = impl.imex_step(state, spec.execution.dt, control, nan, xp=np)
        assert not valid


def _bad_factor():
    raw = heredity(routes=((0, ("f_a",)),))
    raw["model"][kf.FACTOR_KEY][0]["value"] = 1.5
    return raw


def test_binding_refusals():
    with kind_registry.scope(registry()):
        with pytest.raises(ConfigError, match="unknown factor sources"):
            parse_spec(heredity(routes=((0, ("f_missing",)),)))
        with pytest.raises(ConfigError, match="routed twice"):
            parse_spec(heredity(routes=((0, ("f_a",)), (0, ("f_b",)))))
        with pytest.raises(ConfigError, match="its own control fields only"):
            parse_spec(heredity(routes=((0, ("f_a",)),), field="membrane"))
        with pytest.raises(ConfigError, match="outside"):
            parse_spec(heredity(routes=((5, ("f_a",)),)))
    second = kf.factor_source("tests.kind.factor_b@1", "test_factors_b")
    with kind_registry.scope(registry(second)):
        raw = kf.declare_routing(heredity(), factors={"f_a": 0.2}, key="test_factors_b")
        with pytest.raises(ConfigError, match="is exposed by"):
            parse_spec(raw)


def test_without_a_sink_the_door_is_absent():
    with kind_registry.scope(registry()):
        spec = parse_spec(heredity())  # The source alone.
        impl, state, p, control = host(spec)
        assert impl.structure.routes == ()
        kf.CALLS.clear()
        impl.readouts(state, control, p, xp=np)
        _, valid = impl.imex_step(state, spec.execution.dt, control, p, xp=np)
        assert valid and kf.CALLS["factors"] == 0


# ------------------------------------------------------------------ the passive routes as the sink


def with_routes():
    """The planted kinds and the built-in passive routes, on one test-local registry."""
    return registry(passive_routes.PASSIVE_ROUTES)


def pair(factors=None, *, end=0.02):
    """The closed pair, its route optionally factored, with the planted source's factors."""
    leak = route("leak_S", P)
    if factors is not None:
        leak["factors"] = list(factors)
    return kf.declare_routing(closed_pair(routes=[leak], end=end), factors=FACTORS)


def test_a_factored_routes_flux_is_the_unfactored_flux_times_the_product():
    rates = {}
    for factors in (None, ("f_a", "f_b")):
        with kind_registry.scope(with_routes()):
            spec = parse_spec(pair(factors))
            impl, state, p, control = host(spec)
            rates[factors] = impl.readouts(state, control, p, xp=np).derivative
    plain, factored = rates[None], rates[("f_a", "f_b")]
    rows = np.flatnonzero(np.asarray(plain.passive_transferred)[:, 0])  # The carried row only.
    assert len(rows) == 1
    s = int(rows[0])
    ratio = float(factored.passive_transferred[s, 0]) / float(plain.passive_transferred[s, 0])
    assert ratio == pytest.approx(FACTORS["f_a"] * FACTORS["f_b"], rel=1e-14)
    heat_ratio = float(factored.passive_dissipated_energy_pJ[0]) / float(
        plain.passive_dissipated_energy_pJ[0]
    )
    assert heat_ratio == pytest.approx(FACTORS["f_a"] * FACTORS["f_b"], rel=1e-14)


def test_the_multiplier_exists_only_where_a_route_declares_factors():
    with kind_registry.scope(with_routes()):
        plain = get_model(parse_spec(pair()).model)
        factored = get_model(parse_spec(pair(("f_a",))).model)
    entries = dict(plain.structure.kinds)
    assert entries[passive_routes.KIND_ID] == (passive_routes.LAW_ID,)  # Today's entry.
    assert "passive_multiplier" not in plain.Control._fields and plain.structure.routes == ()
    assert "passive_multiplier" in factored.Control._fields
    assert factored.structure.routes == (
        (passive_routes.KIND_ID, "passive_multiplier", 0, ((kf.FACTOR_ID, 0),)),
    )
    assert plain.Control is not factored.Control and "passive_multiplier" in (
        factored.Control.__name__
    )  # A deterministic variant name.
    assert plain.STATE_TYPE._fields == factored.STATE_TYPE._fields  # Only the control differs.


def test_a_factored_cargo_route_keeps_its_exact_booking():
    with kind_registry.scope(with_routes()):
        spec = parse_spec(pair(("f_c",)))
        model = get_model(spec.model)
        result = run(spec)  # Host checks every row: material, energy with the exact heat.
        state, p = model.initial_values(spec)
    assert bool(p.passive_exact[0])  # The factor leaves the exact scope as it was.
    s = list(spec.model.species_ids).index(fx.SPECIES)
    final = result.final.state
    start = (p.amount_reference[s, 0], p.extracellular_amount_reference[s, 1])
    end = (
        start[0] + final.amount_increment[s, 0],
        start[1] + final.extracellular_amount_increment[s, 1],
    )
    effective = FACTORS["f_c"] * P * AREA  # The route at its factor's rate.
    closed = reference.closed_pair(spec.experiment.end_time, *start, 1.0, 1.0, effective)
    assert end[0] == pytest.approx(float(closed["n_a"]), rel=5e-4)
    rt = 1e-3 * R * spec.model.temperature_K
    g = [n * (np.log(n) - 1.0) for n in (*start, *end)]  # V = 1 pL.
    decrease = rt * ((g[0] + g[1]) - (g[2] + g[3]))
    heat = float(final.passive_dissipated_energy_pJ[0])
    assert heat > 0 and heat == pytest.approx(decrease, rel=1e-10)  # Exact, to rounding.
