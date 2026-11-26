"""N2 (FR-8 rung 1, D235): the membranes' and junctions' slope conductances in @3's IMEX operator,
with each junction gate advanced by its exponential update ((a)).

Host-only rows, no world compiled (about 2 s): the frozen slope against a central difference of the
constant-field flux; the operator block's symmetry, zero row sums and non-negative conductances;
the N2 ID admitted by @3's parse (wherever the ionic step is @3's), with its static switch, its
tableau's vector operator time; X2's guard at the step checks; (a)'s lifted junction-gate bound and
its stage update against the law's exact constant-voltage solution; and the definition-time bound,
which drops the charge terms N2 makes implicit (H2's 292 ms term) and keeps every species' material
relaxation. The stepped rows (ledgers, heat against RK4, second order) are N2's rows in
test_surface_pump_v3_imex.py.
"""

import copy

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.laws.junctions import junction_gate
from cells.laws.junctions.selective import selective_flux
from cells.models import surface_kinetic as kinetic
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as v3
from cells.numerics import surface_imex as imex
from validation.long_duration import worlds
from validation.tissue import surface_pump_v2_fixtures as fixtures_v2
from validation.tissue import surface_pump_v3_fixtures as fixtures

N2 = imex.IMPLICIT_CONDUCTANCES_ID
X2 = {"check": "cells.execution.step_doubled_energy@1", "integration_error_cap": 2e-3}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.mark.parametrize("dv", [-0.12, -0.03, -1e-6, 0.0, 2e-6, 0.04, 0.09])
def test_route_slope_is_the_flux_derivative(dv):
    """dJ/d(dv) of selective_flux's constant-field flux, sender -> receiver, for z = -1, 0, 1, 2."""
    z = np.array([[-1.0], [0.0], [1.0], [2.0]])
    c_from, c_to = np.array([[12.0, 0.4]] * 4), np.array([[110.0, 3.0]] * 4)
    args = (z, 310.0, 2e-9, 3e-9)
    h = 1e-7

    def flux(v):
        return selective_flux(c_from, c_to, np.full(2, v), *args, 0.0, 1.0, 0.7, xp=np)

    expected = (flux(dv + h) - flux(dv - h)) / (2 * h)
    slope = v3.route_slope(c_from, c_to, np.full(2, dv), *args, 0.7, xp=np)
    np.testing.assert_allclose(slope, expected, rtol=1e-6, atol=1e-30)
    assert np.all(z * slope >= 0)  # So each route's charge conductance is non-negative.


def at3_world(solver):
    raw = fixtures.definition("closed", solver=imex.ARS222_ID)
    raw["execution"]["solver"] = solver
    return raw


def test_the_operator_block_is_symmetric_with_zero_row_sums():
    spec = parse_spec(at3_world(imex.ARS222_ID))
    state, p = v3.initial_values(spec)
    rng = np.random.default_rng(7)
    weights = v3.ConductanceWeights(
        rng.random(p.membrane_permeability.shape) * np.sign(p.valence),
        rng.random(p.channel_relative_permeability.shape) * np.sign(p.valence),
        rng.random(p.junction_permeability.shape) * np.sign(p.valence),
    )
    block = v3.conductance_laplacian(weights, p, xp=np)
    np.testing.assert_allclose(block, block.T, rtol=0, atol=0)
    np.testing.assert_allclose(block.sum(axis=1), 0.0, atol=1e-30)
    assert np.all(np.diag(block) >= 0)


def test_the_n2_id_is_admitted_by_at3_alone_with_its_static_switch():
    spec = parse_spec(at3_world(N2))
    assert spec.execution.solver == N2
    _, layout = v3.initial_values(spec)
    assert layout.imex_operator_time.shape == (2,)  # The switch: N2's tableau's vector.
    assert v3.implicit_conductances(layout)
    _, today = v3.initial_values(parse_spec(at3_world(imex.ARS222_ID)))
    assert np.shape(today.imex_operator_time) == () and not v3.implicit_conductances(today)
    assert type(today) is type(layout)  # No field of N2's in any layout.
    with pytest.raises(ValueError, match="one entry per frozen block"):
        imex.operator_times(np.zeros(3))  # Any other shape refuses, never broadcasts.
    raw = fixtures_v2.definition("closed", solver=imex.ARS222_ID)
    raw["execution"]["solver"] = N2
    with pytest.raises(ConfigError):  # @1 and @2 refuse it.
        parse_spec(raw)


def test_n2_runs_only_with_x2_selected():
    raw = at3_world(N2)
    checks = v3.bind_step_checks(parse_spec(raw))
    with pytest.raises(ConfigError, match="runs only with execution.energy_check"):
        checks(np.array([raw["execution"]["dt"]]))
    selected = copy.deepcopy(raw)
    selected["execution"]["energy_check"] = dict(X2)
    v3.bind_step_checks(parse_spec(selected))(np.array([raw["execution"]["dt"]]))  # Admitted.


def test_n2_lifts_the_junction_gate_bound_and_keeps_the_calcium_bound():
    """(a): N2 advances the junction gates by their exponential update, so the junction-gate step
    bound (0.125 / 24.1 per s, 5.18 ms on the fixture's junction) does not apply; the calcium
    pump's explicit bound still does (0.44 at 20 ms, 1.1 at 50 ms)."""
    raw = at3_world(N2)
    raw["execution"].update(dt=0.02, max_steps=18, energy_check=dict(X2))
    raw["experiment"].update(end_time=0.2, observation_times=[0.0, 0.2])
    checks = v3.bind_step_checks(parse_spec(raw))
    assert 0.02 * checks.junction_rate > first.GATE_STEP_BOUND  # Today's bound would refuse it.
    checks(np.array([0.02]))  # Admitted.
    with pytest.raises(ConfigError, match="calcium pump rate bound"):
        checks(np.array([0.05]))


def test_the_junction_gate_update_is_exact_at_constant_voltage():
    """(a)'s stage update at a held junction voltage is the law's exact solution (advance_clamped),
    here at 40 times today's bound, and it leaves inactive slots as they are."""
    spec = parse_spec(at3_world(N2))
    state, p = v3.initial_values(spec)
    potential = np.zeros(p.active.size + p.outside_active.size)
    potential[p.junction_sender[0]] = -0.031  # -31 mV across junction_0, past its threshold.
    voltage, start = v3.junction_voltage_kinetics(potential, p, xp=np)
    dt = 40 * first.GATE_STEP_BOUND / float(start.relaxation_per_s[0])
    gate, availability = np.asarray(state.junction_gate), np.ones(p.junction_active.shape)
    advanced, ok = v3.stage_junction_gates(gate, start, potential, availability, 1.0, dt, p, xp=np)
    exact = junction_gate.advance_clamped(gate, voltage, kinetic.junction_parameters(p), dt, xp=np)
    active = np.asarray(p.junction_active)
    np.testing.assert_allclose(advanced[active], exact[active], rtol=1e-14, atol=0)
    np.testing.assert_array_equal(advanced[~active], gate[~active])
    assert bool(ok) and not np.allclose(advanced[active], gate[active])


def stepped(solver, dt, steps):
    """(the states after each step, each step's validity) of one patch with all five channel
    laws, gates off steady state, through @3's checked step (no runner: no step checks)."""
    from cells.definitions.surface_pump_v3_spec import control_values
    from cells.registry.models import get_model

    raw = fixtures.single_patch(dt=dt, end_time=dt * steps, solver=imex.ARS222_ID)
    raw["execution"]["solver"] = solver
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    params = model.parameters(spec, layout)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(np.asarray(v[0]) for v in controls))
    step = jax.jit(lambda s: model.checked_step(s, dt, control, params, layout.active))
    states, valid = [], []
    for _ in range(steps):
        state, ok = step(state)
        states.append(state)
        valid.append(bool(ok))
    return states, valid, layout


def test_n2_steps_a_channel_patch_with_exact_material_and_ars_accuracy():
    """About 30 s (one tiny world compiled under both schemes): N2 at 10 us tracks ARS(2,2,2) to
    its own step error, moves every amount in flux form, and at 20 ms, where ARS's stage rule
    refuses the first step (the patch's rate is 65 per s), admits every step."""
    fine = {s: stepped(s, 1e-5, 40) for s in (imex.ARS222_ID, N2)}
    assert all(fine[N2][1]) and all(fine[imex.ARS222_ID][1])
    a, b = fine[imex.ARS222_ID][0][-1], fine[N2][0][-1]
    np.testing.assert_allclose(b.amount_increment, a.amount_increment, rtol=0, atol=1e-9)
    np.testing.assert_allclose(b.channel_gate, a.channel_gate, rtol=0, atol=1e-6)
    layout = fine[N2][2]
    moved = -(b.membrane_transferred + v3.channel_to_membrane(b.channel_transferred, layout, xp=np))
    pumped = layout.stoichiometry * b.pump_cycles
    np.testing.assert_allclose(b.amount_increment[:, 0], (moved + pumped)[:, 0], rtol=0,
                               atol=1e-15)  # fmt: skip
    coarse = {s: stepped(s, 2e-2, 4)[1] for s in (imex.ARS222_ID, N2)}
    assert coarse[imex.ARS222_ID][0] is False  # The stage rule: dt x membrane rate > 1.
    assert all(coarse[N2])


def test_the_definition_bound_drops_the_implicit_charge_terms():
    """H2's 3.42 per s (292 ms) is its patches' membrane charge term (FR-8's M1, 'M'); under N2 it
    leaves, and every species' material relaxation, about 2.3e-4 per s there, sets the bound."""
    raw = worlds.h2(1e-3)
    today = v3.bind_step_checks(parse_spec(raw)).explicit_rate
    raw["execution"]["solver"] = N2
    n2 = v3.bind_step_checks(parse_spec(raw)).explicit_rate
    assert today == pytest.approx(3.4232333520717, rel=1e-9)
    assert 1e-4 < n2 < 1e-3
