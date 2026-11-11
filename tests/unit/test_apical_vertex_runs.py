"""apical_vertex_mechanics@1 runs: relaxation, refusals, ablation, restart, vmap.

Relaxation reaches the case-I ground state with both solvers; invalid steps are
refused; a scheduled Farhadifar cut books its control work and the exact
velocity jump; restart is bitwise; vmapped steps equal single worlds.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.models import apical_vertex as av
from tests.apical_vertex_fixtures import (
    A_STAR,
    E_STAR,
    GAMMA,
    LAMBDA,
    P_CASE,
    farhadifar_cut,
    honeycomb,
    jax_forces,
)
from validation.morphogenesis import mg1_reference as ref
from validation.morphogenesis import mg1_theory as theory

jax.config.update("jax_enable_x64", True)


@pytest.mark.parametrize("solver", ["rk4", "euler"])
def test_relaxation_reaches_case_one_ground_state(solver):
    dt = 0.125 if solver == "rk4" else 0.0625
    definition = honeycomb(
        displacement=0.05,
        seed=1,
        end_time=240.0,
        observation_times=[0.0, 240.0],
        dt=dt,
        solver=solver,
    )
    result = run(parse_spec(definition))
    obs = result.observations
    assert abs(obs.energy[-1] / 16 - E_STAR) <= 1e-10
    np.testing.assert_allclose(obs.cell_area[-1][:16], A_STAR, atol=1e-8)
    assert obs.max_force[-1] < 1e-9
    d = result.diagnostics
    assert d["max_energy_balance_allowance_used"] < 1.0
    assert d["max_momentum_drift"] < 1e-11 and d["max_area_identity_error"] < 1e-12
    assert np.all(np.diff(obs.energy) <= 0)


def test_step_bound_and_edge_collapse_are_refused():
    with pytest.raises(ConfigError, match="bound"):
        run(parse_spec(honeycomb(dt=0.5, end_time=1.0, observation_times=[0.0, 1.0])))
    definition = honeycomb(end_time=20.0, observation_times=[0.0, 20.0], dt=0.015625)
    definition["model"]["length_floor"] = 0.3
    definition["model"]["junctions"][0]["line_tension"] = 3.0
    with pytest.raises(NumericalError, match="domain|refused|invalid"):
        run(parse_spec(definition))


def test_ablation_books_control_work_and_the_velocity_jump():
    definition = honeycomb(end_time=1.0, observation_times=[0.0, 0.5, 0.5625, 1.0], dt=0.0625)
    controls, cells = farhadifar_cut(definition)
    definition["experiment"]["parameter_controls"] = controls
    spec = parse_spec(definition)
    result = run(spec)
    obs = result.observations
    tissue = ref.from_definition(definition)
    before, after = tissue, ref.with_control(tissue, controls[1])
    x = tissue.position
    expected_work = ref.energy(after, x) - ref.energy(before, x)
    assert abs(obs.control_work[1]) == 0
    assert abs(obs.control_work[2] - expected_work) <= 1e-12 * abs(expected_work)
    # The jump of velocity across the event, at the event row, is exact.
    jump = ref.velocity_jump(before, after, x)
    state, layout = av.initial_values(spec)
    cut_state = state._replace(
        line_tension=np.asarray(result.history.line_tension[-1]),
        contractility=np.asarray(result.history.contractility[-1]),
    )
    np.testing.assert_allclose(
        jax_forces(cut_state, layout)[:32] - jax_forces(state, layout)[:32], jump, atol=1e-13
    )
    # 120-degree junctions: the cut junction opens at 2 (Lambda + Gamma L) / eta.
    j = tissue.junction_ids.index(definition["model"]["junctions"][0]["id"])
    t, h = tissue.junction_tail[j], tissue.junction_head[j]
    d = x[h] + tissue.junction_image[j] @ tissue.box.T - x[t]
    rate = (jump[h] - jump[t]) @ (d / np.linalg.norm(d))
    assert abs(rate - theory.recoil_opening_rate(LAMBDA, GAMMA, P_CASE)) <= 1e-10
    assert result.diagnostics["max_energy_balance_allowance_used"] < 1.0


def test_checkpoint_restart_is_bitwise():
    definition = honeycomb(
        displacement=0.05, seed=4, end_time=4.0, observation_times=[0.0, 2.0, 4.0], dt=0.125
    )
    spec = parse_spec(definition)
    whole = run(spec)
    resumed = run(spec, whole.checkpoint_at(2.0))
    for a, b in zip(whole.final.state, resumed.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))


def test_vmapped_steps_equal_single_worlds():
    worlds = [honeycomb(displacement=0.05, seed=s) for s in (5, 6)]
    specs = [parse_spec(w) for w in worlds]
    states, params = [], []
    for spec in specs:
        state, layout = av.initial_values(spec)
        states.append(jax.tree.map(jnp.asarray, state))
        params.append(jax.tree.map(jnp.asarray, av.parameters(spec, layout)))
    control = av.Control(*(s for s in states[0][2:6]))

    def step(s, p):
        return av.checked_step(s, 0.0625, control, p, None)

    single = jax.jit(step)
    singles = [single(s, p) for s, p in zip(states, params, strict=True)]
    stacked_states = jax.tree.map(lambda *v: jnp.stack(v), *states)
    stacked_params = jax.tree.map(lambda *v: jnp.stack(v), *params)
    batched, ok = jax.jit(jax.vmap(step))(stacked_states, stacked_params)
    assert bool(jnp.all(ok))
    for i, (state, single_ok) in enumerate(singles):
        assert bool(single_ok)
        for a, b in zip(state, batched, strict=True):
            np.testing.assert_allclose(np.asarray(a), np.asarray(b[i]), rtol=0, atol=1e-15)
