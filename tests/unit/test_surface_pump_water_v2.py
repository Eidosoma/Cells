"""resolved_pump_water@2: resolved_pump_water@1 plus KCC-type K+/anion symport routes.

Definitions: round trip, dispatch and declaration errors. Reductions: with no
route the model is resolved_pump_water@1 bitwise (a static branch); with every
route blocked it is too (compiled, and uncompiled). With routes: every ledger
closes, the cycles and heat are booked (heat nondecreasing), the route lowers
the swelling of a D cell, readouts carry the route in the K and anion
derivatives, the routes compose with @3's trapezoid junction-heat booking, host
and device checks agree and a falling symport heat fails the dissipation
check. Stationary: a state with routes is a fixed point of the split step.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.analysis import stationary as sa
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_pump_water_v2_spec import Control, control_values
from cells.models import surface_pump_water, surface_pump_water_v2
from cells.models.registry import get_model
from validation.tissue import pump_water_fixtures as fixtures

AQUAPORIN_PF = 5e-4


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def water(state="D", *, end=0.2, jit=True):
    raw = fixtures.heredity_cell(state, end_time=end)
    raw["experiment"]["observation_times"] = [0.0, round(end / 2, 3), end]
    raw["execution"]["jit"] = jit
    return fixtures.with_water(raw, pf_m_s=AQUAPORIN_PF)


def regulated(state="D", **kw):
    return fixtures.with_symport(water(state), flux_mmol_L_h=15.0, steepness=0.12, **kw)


def test_definition_round_trip_and_dispatch():
    spec = parse_spec(regulated())
    assert get_model(spec.model) is surface_pump_water_v2
    assert parse_spec(spec.to_dict()) == spec
    assert [r.membrane_id for r in spec.model.symport.routes] == ["membrane_0"]


def _route(raw):
    return raw["model"]["symport"]["routes"][0]


ERRORS = {
    "law": lambda r: r["model"]["symport"].update(law="kcc_reversible_tanh@1"),
    "role_valence": lambda r: r["model"]["symport"]["roles"].update(anion="K"),
    "role_species": lambda r: r["model"]["symport"]["roles"].update(anion="Cl"),
    "membrane": lambda r: _route(r).update(membrane_id="membrane_9"),
    "duplicate": lambda r: r["model"]["symport"]["routes"].append(dict(_route(r))),
    "capacity": lambda r: _route(r).update(capacity_fmol_s_mM2=-1.0),
    "steepness": lambda r: _route(r).update(steepness=0.0),
    "set_volume": lambda r: _route(r).update(set_volume_pL=0.0),
    "controls": lambda r: r["experiment"].update(symport_controls=[]),
    "availability": lambda r: r["experiment"]["symport_controls"][0].update(
        schedule=[dict(time=0.0, availability=1.5)]
    ),
}


@pytest.mark.parametrize("fault", ERRORS)
def test_definition_errors(fault):
    raw = regulated()
    ERRORS[fault](raw)
    with pytest.raises(ConfigError):
        parse_spec(raw)


def same(a, b, fields):
    return all(np.array_equal(np.asarray(getattr(a, k)), np.asarray(getattr(b, k))) for k in fields)


@pytest.mark.parametrize("jit", [True, False])
def test_no_route_and_blocked_routes_are_resolved_pump_water_1(jit):
    end = 0.2 if jit else 0.005
    reference = run(parse_spec(water(end=end, jit=jit))).history
    for raw in (
        fixtures.with_symport(water(end=end, jit=jit), membranes=[]),
        fixtures.with_symport(water(end=end, jit=jit), availability=0.0),
    ):
        history = run(parse_spec(raw)).history
        assert same(history, reference, surface_pump_water.STATE_TYPE._fields)
        assert not np.any(history.symport_cycles_fmol)
        assert not np.any(history.symport_dissipated_energy_pJ)


@pytest.fixture(scope="module")
def route_on():
    spec = parse_spec(regulated())
    return spec, run(spec)


def test_routes_book_their_ledgers_and_lower_the_swelling(route_on):
    spec, result = route_on
    d = result.diagnostics
    assert d["max_energy_balance_relative"] < 1e-6
    assert d["max_balance_error_fmol"] < 1e-12
    cycles = np.asarray(result.history.symport_cycles_fmol)[:, 0]
    heat = np.asarray(result.history.symport_dissipated_energy_pJ)[:, 0]
    assert cycles[-1] > 0 and np.all(np.diff(cycles) > 0)  # Net K/M efflux from D.
    assert np.all(np.diff(heat) >= 0) and heat[-1] > 0
    free = run(parse_spec(water())).observations.cell_volume_pL[-1, 0]
    assert result.observations.cell_volume_pL[-1, 0] < free


def test_readouts_carry_the_route_in_the_k_and_anion_derivatives(route_on):
    spec, result = route_on
    _, p = surface_pump_water_v2.initial_values(spec)
    row = surface_pump_water_v2.STATE_TYPE(*(np.asarray(v[-1]) for v in result.history))
    control = Control(*(v[0] for v in control_values(spec, [0.2])))
    on = surface_pump_water_v2.readouts(row, control, p, xp=np)
    off = surface_pump_water_v2.readouts(
        row, control._replace(symport=np.zeros_like(control.symport)), p, xp=np
    )
    cycles = on.symport.cycles_fmol_s[0]
    assert cycles > 0
    k, m = spec.model.species_ids.index("K"), spec.model.species_ids.index("M")
    for s in (k, m):
        delta = off.derivative.amount_increment[s, 0] - on.derivative.amount_increment[s, 0]
        assert delta == pytest.approx(cycles, rel=1e-9)
    assert on.derivative.symport_cycles_fmol[0] == cycles
    assert on.field.dissipation_pJ_s - off.field.dissipation_pJ_s == pytest.approx(
        on.symport.dissipation_pJ_s[0], rel=1e-9
    )


def test_routes_compose_with_the_junction_heat_booking():
    raw = fixtures.with_water(fixtures.gated_sheet(end_time=0.02), pf_m_s=AQUAPORIN_PF)
    raw["model"]["junction_heat_booking"] = "trapezoid_nonnegative@1"
    spec = parse_spec(fixtures.with_symport(raw, flux_mmol_L_h=15.0, steepness=0.12))
    result = run(spec)
    assert result.diagnostics["max_energy_balance_relative"] < 1e-6
    assert np.all(np.asarray(result.history.symport_cycles_fmol)[-1] != 0)


def test_device_checks_agree_and_a_falling_symport_heat_fails(route_on):
    spec, result = route_on
    _, p = surface_pump_water_v2.initial_values(spec)
    p = jax.tree.map(jnp.asarray, p)
    constants = surface_pump_water_v2.device_check_constants(spec)
    history = surface_pump_water_v2.STATE_TYPE(*(jnp.asarray(v) for v in result.history))
    host = surface_pump_water_v2.check_values(
        result.history, spec, steps=np.arange(len(result.times))
    )

    def device(rows, i):
        previous = type(rows)(*(v[i - 1] for v in rows))
        row = type(rows)(*(v[i] for v in rows))
        bits, values = surface_pump_water_v2.device_checks(previous, row, p, constants, i)
        names = surface_pump_water_v2.DEVICE_CHECKS
        return {n for n, b in zip(names, np.asarray(bits), strict=True) if b}, values

    worst = np.zeros(len(surface_pump_water_v2.DEVICE_DIAGNOSTICS))
    for i in range(1, len(result.times)):
        failed, values = device(history, i)
        assert failed == set(), i
        worst = np.maximum(worst, np.asarray(values))
    for key, value in zip(surface_pump_water_v2.DEVICE_DIAGNOSTICS, worst, strict=True):
        assert abs(value - host[key]) <= 1e-6 * max(abs(host[key]), 1e-30) + 1e-24, key
    i = 150
    heat = history.symport_dissipated_energy_pJ
    bad = history._replace(symport_dissipated_energy_pJ=heat.at[i, 0].set(heat[i - 1, 0] - 2e-12))
    assert device(bad, i)[0] == {"dissipation"}
    with pytest.raises(NumericalError, match="dissipation"):
        surface_pump_water_v2.check_values(
            surface_pump_water_v2.STATE_TYPE(*(np.asarray(v) for v in bad)),
            spec,
            steps=np.arange(len(result.times)),
        )


def test_stationary_state_with_routes_is_a_fixed_point_of_the_split_step():
    spec = parse_spec(fixtures.with_symport(water("H"), flux_mmol_L_h=15.0, steepness=1.0))
    pb = sa.problem(spec)
    solution = sa.newton(pb, pb.anchor)
    assert solution.converged, solution.message
    residual = pb.evaluate(solution.u, formulation="step_map", steps=4)[0]
    assert np.max(np.abs(residual)) < 1e-6
