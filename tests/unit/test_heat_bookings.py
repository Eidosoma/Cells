"""Seam D: one heat booking per mover class, and the trapezoid written once (docs/
CORE_SEAMS_DESIGN.md §6.1-6.2; the lead's rulings of 18 November 2026: D's plan, the classes (b),
"stored" a level).

The booking probe (CORE_SEAMS_STEP0 §5.1, confirmed in §6.1) is the cheapest proof. A heredity
cell with a K+ and a Na+ leak starts 15 mV below E_K and relaxes through it. Under ARS(2,2,2) the
tableau books a negative K+ heat increment on the step that crosses, which the dissipation check
refuses, at dt G/C = 0.03. With `heat_bookings: {"channels": "trapezoid_nonnegative@1"}` the same
run is admitted with every channel heat element non-decreasing. The planted error, the tableau's
weights left in a class declared trapezoid, must again fail the dissipation check.

Beside it:
- the booked heat is the trapezoid of the start and end powers, and the state is the tableau's;
- a declared kind's heat field is booked by the same code;
- the key's parse, round trip and default (omitted, so no fingerprint or structure moves), and its
  refusals: junctions, the tableau listed, a class that admits nothing, RK4, and a caller that
  checks @3 without its structure; water@1, whose composition carries the structure, books it;
- the dissipation check reads declared energy roles, with today's suffix rule as the default.
"""

import copy
import dataclasses
import math

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.execution.schedule import control_values
from cells.laws.electrochemistry import F, R
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import surface_pump_v3_fixtures as fx

TRAPEZOID = spec3.TRAPEZOID_JUNCTION_HEAT
SOLVER = "imex_ars222_face_electromigration@1"
DISSIPATION_REFUSAL = "dissipation cannot be negative or decrease"

# The booking probe's world (STEP0 §5.1): P_Na puts the GHK rest 20 mV above E_K.
T = fx.HEREDITY_TEMPERATURE_K
_, NA_I, K_I, M_I, _ = fx.HEREDITY_STATES["H"]
NA_O, K_O = fx.HEREDITY_BATH_mM["Na"], fx.HEREDITY_BATH_mM["K"]
P_K = 1e-9  # m/s
RT_F = R * T / F
E_K = RT_F * math.log(K_O / K_I)
V_REST = E_K + 0.020
_X = math.exp(V_REST / RT_F)
P_NA = P_K * (_X * K_I - K_O) / (NA_O - _X * NA_I)
CROSSING, CONTROL = E_K - 0.015, E_K + 0.010  # The two arms' starting voltages (V).
RUNG = 0.03  # dt G/C at which the tableau's crossing step was refused (STEP0 §6.1, step 22).


def _ghk_current_A(v):
    total = 0.0
    for p, ci, co in ((P_K, K_I, K_O), (P_NA, NA_I, NA_O)):
        x = v / RT_F
        flux = p * fx.HEREDITY_AREA_M2 * x * (ci - co * math.exp(-x)) / (1 - math.exp(-x))
        total += F * flux
    return total


def _g_over_c():
    h = 1e-6
    slope = (_ghk_current_A(V_REST + h) - _ghk_current_A(V_REST - h)) / (2 * h)
    return slope / fx.HEREDITY_CAPACITANCE_F


def probe_world(v0, *, bookings=None, rung=RUNG):
    """STEP0's booking world at one rung: the heredity cell, its pump and gated populations
    removed, its patch's own permeabilities zeroed, and the two leaks."""
    dt = rung / _g_over_c()
    steps = max(8, math.ceil(5 / rung))
    raw = fx.heredity_cells(
        [(v0, NA_I, K_I, M_I)],
        dt=dt,
        end_time=steps * dt,
        solver=SOLVER,
        observation_times=[k * dt for k in range(steps + 1)],
    )
    m = raw["model"]
    m["membranes"][0]["pump"] = None
    m["membranes"][0]["permeability_m_per_s"] = {
        s: 0.0 for s in m["membranes"][0]["permeability_m_per_s"]
    }
    m["channels"] = [
        fx.channel("kleak", 0, spec3.KLEAK_LAW_ID, "K", P_K, 1.0, []),
        fx.channel("naleak", 0, spec3.NALEAK_LAW_ID, "Na", P_NA, 1.0, []),
    ]
    e = raw["experiment"]
    e["pump_controls"] = []
    e["channel_controls"] = [
        dict(channel_id=c, schedule=[dict(time=0.0, availability=1.0)]) for c in ("kleak", "naleak")
    ]
    raw["execution"]["channel_capacity"] = 2
    raw["execution"]["max_steps"] = steps + 8
    if bookings is not None:
        m[spec3.HEAT_BOOKINGS_KEY] = dict(bookings)
    return raw


def _clear_compiled():
    """A fresh trace: compiled steps are cached by structure (surface_pump_v3._implementation)."""
    jax.clear_caches()
    surface_pump_v3._implementation.cache_clear()


def test_the_tableau_refuses_the_crossing_and_the_trapezoid_admits_it():
    with pytest.raises(NumericalError, match=DISSIPATION_REFUSAL):
        run(parse_spec(probe_world(CROSSING)))
    spec = parse_spec(probe_world(CROSSING, bookings={"channels": TRAPEZOID}))
    assert spec.model.heat_bookings == (("channels", TRAPEZOID),)
    result = run(spec)
    heat = np.asarray(result.history.channel_dissipated_energy_pJ)
    assert np.all(np.diff(heat, axis=0) >= 0) and np.all(heat >= 0)
    for bookings in (None, {"channels": TRAPEZOID}):  # The control is admitted either way.
        run(parse_spec(probe_world(CONTROL, bookings=bookings)))


def test_the_planted_tableau_weights_in_a_trapezoid_class_fail_the_dissipation_check(monkeypatch):
    _clear_compiled()
    monkeypatch.setattr(surface_pump_v3, "trapezoid_fields", lambda structure: ())
    try:
        spec = parse_spec(probe_world(CROSSING, bookings={"channels": TRAPEZOID}))
        with pytest.raises(NumericalError, match=DISSIPATION_REFUSAL):
            run(spec)
    finally:
        monkeypatch.undo()
        _clear_compiled()


def _steps(raw, count):
    """count checked steps of the world's model from its initial state: [(state, valid)]."""
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    c = control_values(spec, [0.0])
    control = type(c)(*(jnp.asarray(np.asarray(v)[0]) for v in c))
    state, p = jax.tree.map(jnp.asarray, (state, p))
    dt = jnp.asarray(spec.execution.dt)
    step = jax.jit(lambda s: model.checked_step(s, dt, control, p, p.active))
    rhs = jax.jit(lambda s: model.rhs(s, control, p, p.active))
    rows = [state]
    for _ in range(count):
        state, valid = step(state)
        assert bool(valid)
        rows.append(state)
    return spec, rows, rhs


def test_the_booked_heat_is_the_trapezoid_and_the_state_is_the_tableaus():
    count = 30  # Through the crossing at this rung (STEP0's step 22).
    spec, rows, rhs = _steps(probe_world(CROSSING, bookings={"channels": TRAPEZOID}), count)
    _, plain, _ = _steps(probe_world(CROSSING), count)
    dt = spec.execution.dt
    for start, end in zip(rows, rows[1:], strict=False):
        booked = np.asarray(end.channel_dissipated_energy_pJ - start.channel_dissipated_energy_pJ)
        q0 = np.asarray(rhs(start).channel_dissipated_energy_pJ)
        q1 = np.asarray(rhs(end).channel_dissipated_energy_pJ)
        np.testing.assert_allclose(booked, 0.5 * dt * (q0 + q1), rtol=1e-9, atol=1e-24)
        assert np.all(booked >= 0)
    for a, b in zip(rows, plain, strict=True):  # Only the heat fields' quadrature changes.
        for name in a._fields:
            if name != "channel_dissipated_energy_pJ":
                np.testing.assert_array_equal(
                    np.asarray(getattr(a, name)), np.asarray(getattr(b, name))
                )


def test_the_default_is_omitted_and_the_key_round_trips():
    plain = parse_spec(probe_world(CROSSING))
    assert plain.model.heat_bookings == ()
    assert spec3.HEAT_BOOKINGS_KEY not in spec3.to_dict(plain)["model"]
    assert surface_pump_v3.structure(plain.model).heat_bookings == ()
    booked = parse_spec(probe_world(CROSSING, bookings={"pumps": TRAPEZOID, "channels": TRAPEZOID}))
    assert booked.model.heat_bookings == (("channels", TRAPEZOID), ("pumps", TRAPEZOID))
    written = spec3.to_dict(booked)
    assert written["model"][spec3.HEAT_BOOKINGS_KEY] == {"channels": TRAPEZOID, "pumps": TRAPEZOID}
    assert parse_spec(written).model == booked.model
    assert surface_pump_v3.structure(booked.model).heat_bookings == booked.model.heat_bookings
    assert surface_pump_v3.trapezoid_fields(surface_pump_v3.structure(booked.model)) == (
        "channel_dissipated_energy_pJ",
        "pump_dissipated_energy_pJ",
    )


@pytest.mark.parametrize(
    "bookings,message",
    [
        ({"junctions": TRAPEZOID}, "junction_heat_booking, not heat_bookings"),
        ({"channels": "explicit_tableau"}, "the tableau .* is the default"),
        (
            {"channels": "exact_free_energy_heat@1"},
            "admit trapezoid_nonnegative@1 beyond the tableau",
        ),
        ({"faces": TRAPEZOID}, "neither one of @3's own mover classes"),
        ({"channels": 1}, "maps mover classes to booking IDs"),
    ],
)
def test_heat_bookings_refusals(bookings, message):
    with pytest.raises(ConfigError, match=message):
        parse_spec(probe_world(CROSSING, bookings=bookings))


def test_rk4_refuses_a_booking():
    raw = probe_world(CROSSING, bookings={"channels": TRAPEZOID})
    raw["execution"]["solver"] = "rk4"
    with pytest.raises(ConfigError, match="requires an IMEX solver"):
        parse_spec(raw)


def test_a_caller_without_the_structure_refuses_a_booking_rather_than_ignore_it():
    spec = parse_spec(probe_world(CROSSING, bookings={"channels": TRAPEZOID}))
    surface_pump_v3.check_definition(spec, structure=surface_pump_v3.structure(spec.model))
    with pytest.raises(ConfigError, match="runs @3 without one"):
        surface_pump_v3.check_definition(spec)


def test_the_water_family_books_through_its_compositions_structure():
    """Water@1 runs @3 through a composition whose inner carries the structure, picks included,
    so the family books what the definition picks: the probe's crossing, refused by the tableau,
    is admitted under the trapezoid there too."""
    with pytest.raises(NumericalError, match=DISSIPATION_REFUSAL):
        run(parse_spec(wfx.with_water(probe_world(CROSSING))))
    spec = parse_spec(wfx.with_water(probe_world(CROSSING, bookings={"channels": TRAPEZOID})))
    assert spec.model.heat_bookings == (("channels", TRAPEZOID),)
    assert (
        get_model(spec.model).composition.inner.structure.heat_bookings == spec.model.heat_bookings
    )
    heat = np.asarray(run(spec).history.channel_dissipated_energy_pJ)
    assert np.all(np.diff(heat, axis=0) >= 0)


# ------------------------------------------------------------------ a kind's routes, by its ID


def _booked_conversion():
    """tests.conversion@1 with its heat declared heat and monotone, admitting the trapezoid."""
    base = kf.conversion()
    return dataclasses.replace(
        base,
        energy_roles={"conversion_heat_pJ": kind_registry.EnergyRole("heat", True)},
        heat_bookings=(TRAPEZOID,),
    )


def _conversion_world(bookings=None):
    from tests.unit.test_kind_stored_rate import world

    raw = copy.deepcopy(world())
    if bookings is not None:
        raw["model"][spec3.HEAT_BOOKINGS_KEY] = dict(bookings)
    return raw


def test_a_kinds_declared_heat_is_booked_by_the_same_trapezoid():
    _clear_compiled()
    try:
        with kind_registry.scope(kf.registry(_booked_conversion())):
            spec, rows, rhs = _steps(_conversion_world({kf.CONVERSION_ID: TRAPEZOID}), 3)
            structure = surface_pump_v3.structure(spec.model)
            assert structure.heat_bookings == ((kf.CONVERSION_ID, TRAPEZOID),)
            assert surface_pump_v3.trapezoid_fields(structure) == ("conversion_heat_pJ",)
            assert "conversion_heat_pJ" in surface_pump_v3.dissipation_fields(structure)
            dt = spec.execution.dt
            for start, end in zip(rows, rows[1:], strict=False):
                booked = np.asarray(end.conversion_heat_pJ - start.conversion_heat_pJ)
                q0 = np.asarray(rhs(start).conversion_heat_pJ)
                q1 = np.asarray(rhs(end).conversion_heat_pJ)
                np.testing.assert_allclose(booked, 0.5 * dt * (q0 + q1), rtol=1e-9, atol=1e-24)
        with kind_registry.scope(kf.registry(kf.conversion())):  # It admits nothing by default.
            with pytest.raises(ConfigError, match="admits no heat booking"):
                parse_spec(_conversion_world({kf.CONVERSION_ID: TRAPEZOID}))
    finally:
        _clear_compiled()


# ------------------------------------------------------------------ declared monotonicity


def test_the_dissipation_check_reads_declared_roles_with_the_suffix_rule_by_default():
    from cells.kinds import passive_routes
    from tests.unit.test_passive_routes_kind import closed_pair

    spec = parse_spec(closed_pair())
    structure = surface_pump_v3.structure(spec.model)
    fields = surface_pump_v3.dissipation_fields(structure)
    suffixed = tuple(
        k
        for k in surface_pump_v3.kind_types(structure).STATE_AXES
        if k.endswith("_dissipated_energy_pJ")
    )
    assert fields == suffixed and "passive_dissipated_energy_pJ" in fields  # Today's rule.
    declared = dataclasses.replace(
        passive_routes.PASSIVE_ROUTES,
        energy_roles={"passive_dissipated_energy_pJ": kind_registry.EnergyRole("heat", False)},
    )
    registry = kind_registry.KindRegistry()  # The world declares the passive routes alone.
    registry.register(declared)
    with kind_registry.scope(registry):
        structure = surface_pump_v3.structure(spec.model)
        fields = surface_pump_v3.dissipation_fields(structure)
    assert "passive_dissipated_energy_pJ" not in fields  # Declared heat, not monotone.
    assert fields == tuple(k for k in suffixed if k != "passive_dissipated_energy_pJ")


def test_the_run_views_monotone_claim_reads_declared_roles(monkeypatch):
    from cells.kinds import passive_routes
    from cells.records import run_view
    from tests.unit.test_passive_routes_kind import closed_pair

    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)

    def plan():
        spec = parse_spec(closed_pair())
        _, layout = get_model(spec.model).initial_values(spec)
        return run_view.prepare(spec, run_view.Request(), layout=layout)

    default = plan()
    assert default._monotone("passive_dissipated_energy_pJ")  # Today's suffix rule.
    assert default._monotone("channel_dissipated_energy_pJ")  # @3's own fields keep it.
    declared = dataclasses.replace(
        passive_routes.PASSIVE_ROUTES,
        energy_roles={"passive_dissipated_energy_pJ": kind_registry.EnergyRole("heat", False)},
    )
    registry = kind_registry.KindRegistry()
    registry.register(declared)
    with kind_registry.scope(registry):
        assert not plan()._monotone("passive_dissipated_energy_pJ")  # Declared non-monotone.
