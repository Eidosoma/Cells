"""Seam D: one heat booking per mover class (docs/CORE_SEAMS_DESIGN.md §6.1-6.2; the lead's rulings
of 18 and 19 November 2026: D's plan, the classes (b), "stored" a level, the water and replacement
families booking what is picked). Host-side claims; the booking probe's runs are in
test_heat_bookings_probe.py, the booked heat's form in test_heat_bookings_formula.py:
- the key's parse, round trip and default (omitted, so no fingerprint or structure moves), and its
  refusals: junctions, the tableau listed, a class that admits nothing, RK4, and a caller that
  checks @3 without its structure;
- the faces' exact booking (cells.heat.exact_free_energy_heat@1, D280) refuses a face that carries a charged
  row, touches a held bath, or carries a row another mover moves in the step (version 1's scope);
- the dissipation check and the run view read declared energy roles, with today's suffix rule as
  the default.
"""

import dataclasses
import math

import jax
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.laws.electrochemistry import F, R
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry.models import get_model
from validation.tissue import secreted_species_fixtures as sfx
from validation.tissue import surface_pump_v3_fixtures as fx

TRAPEZOID = spec3.TRAPEZOID_JUNCTION_HEAT
EXACT = spec3.EXACT_FREE_ENERGY_HEAT
SOLVER = "cells.solver.imex_ars222_face_electromigration@1"
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


CROSSED_STEPS = 30  # Past the crossing step at RUNG (STEP0 §6.1: step 22).


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


def probe_world(v0, *, bookings=None, rung=RUNG, steps=None):
    """STEP0's booking world at one rung: the heredity cell, its pump and gated populations
    removed, its patch's own permeabilities zeroed, and the two leaks. steps: STEP0's five
    relaxation times by default; CROSSED_STEPS runs just past the crossing."""
    dt = rung / _g_over_c()
    steps = max(8, math.ceil(5 / rung)) if steps is None else steps
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


FACE_RATE = 1.0  # 1/s: each node's exchange rate through the face, D A / (L V) at V = 1 pL.


def face_world(low_mM=sfx.TRACE_mM, bookings=None, *, steps=5):
    """The faces' booking world (D280): two 1 pL outside nodes joined by one face that diffuses
    the neutral inventory row S at FACE_RATE, S at 1 mM in n1 and at low_mM elsewhere (its trace
    by default), as cells.model.resolved_pump_tissue@3 itself: the fixture's composite has no operators."""
    area, length = 1e-10, 1e-5
    rest = {} if low_mM == sfx.TRACE_mM else dict(n2=low_mM, cell_0=low_mM, bath=low_mM)
    raw = sfx.world(
        nodes=(("n1", 1.0), ("n2", 1.0)),
        contacts=(("contact_1", "cell_0", "n1"), ("contact_2", "cell_0", "n2")),
        faces=(("face_12", "n1", "n2", area, length),),
        dt=1e-3,
        end=1e-3 * steps,
        observation_times=[0.0, 1e-3 * steps],
        diffusivity=FACE_RATE * length * 1e-15 / area,
        concentrations_mM={"n1": 1.0, **rest},
    )
    m = raw["model"]
    assert m.pop("operators") == []
    m["id"] = m.pop("inner_model")
    if bookings is not None:
        m[spec3.HEAT_BOOKINGS_KEY] = dict(bookings)
    return raw


def _clear_compiled():
    """A fresh trace: compiled steps are cached by structure (surface_pump_v3._implementation)."""
    jax.clear_caches()
    surface_pump_v3._implementation.cache_clear()


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
            {"channels": "cells.heat.exact_free_energy_heat@1"},
            "admit cells.heat.trapezoid_nonnegative@1 beyond the tableau",
        ),
        ({"walls": TRAPEZOID}, "neither one of @3's own mover classes"),
        ({"channels": 1}, "maps mover classes to booking IDs"),
        (
            {"faces": TRAPEZOID},
            "faces admit cells.heat.exact_free_energy_heat@1 beyond the tableau",
        ),
    ],
)
def test_heat_bookings_refusals(bookings, message):
    with pytest.raises(ConfigError, match=message):
        parse_spec(probe_world(CROSSING, bookings=bookings))


def _charged_face_row(raw):
    raw["model"]["faces"][0]["diffusivity_m2_per_s"]["Na"] = 1e-10


def _membrane_also_moves(raw):
    patch = next(p for p in raw["model"]["membranes"] if p["id"] == "contact_2")
    patch["permeability_m_per_s"][sfx.SPECIES] = 1e-9


def _face_to_the_bath(raw):
    face = dict(raw["model"]["faces"][0], id="face_2b", sender="n2", receiver="bath")
    raw["model"]["faces"].append(face)
    raw["execution"]["face_capacity"] = 2


@pytest.mark.parametrize(
    "edit,message",
    [
        (
            _charged_face_row,
            "carries the charged row Na; cells.heat.exact_free_energy_heat@1 books neutral",
        ),
        (_membrane_also_moves, "which membrane contact_2 also moves in the step"),
        (_face_to_the_bath, "carries S to the held bath bath; .* between finite nodes"),
    ],
)
def test_the_faces_exact_booking_refuses_rows_outside_its_scope(edit, message):
    raw = face_world(bookings={"faces": EXACT})
    edit(raw)
    with pytest.raises(ConfigError, match=message):
        parse_spec(raw)
    raw["model"].pop(spec3.HEAT_BOOKINGS_KEY)  # The same world books the tableau without it.
    parse_spec(raw)


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
