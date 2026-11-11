"""apical_vertex_mechanics@1 checked steps: vmap over worlds and the step bound.

Vmapped steps over two worlds equal the single-world steps; an RK4 step whose
dt * rho exceeds 2 at its start state is refused without changing the state, and
a step well inside the bound is accepted.
"""

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.specs import parse_spec
from cells.models import apical_vertex as av
from cells.processes import vertex_mechanics as vm
from tests.apical_vertex_fixtures import honeycomb

jax.config.update("jax_enable_x64", True)


def test_vmapped_steps_and_the_step_bound():
    worlds = [honeycomb(displacement=0.05, seed=s) for s in (5, 6)]
    specs = [parse_spec(w) for w in worlds]
    states, params = [], []
    for spec in specs:
        state, layout = av.initial_values(spec)
        states.append(jax.tree.map(jnp.asarray, state))
        params.append(jax.tree.map(jnp.asarray, av.parameters(spec, layout)))
    control = av.Control(*(s for s in states[0][2:6]))

    def step(s, p, dt):
        return av.checked_step(s, dt, control, p, None)

    single = jax.jit(step)
    singles = [single(s, p, 0.0625) for s, p in zip(states, params, strict=True)]
    stacked_states = jax.tree.map(lambda *v: jnp.stack(v), *states)
    stacked_params = jax.tree.map(lambda *v: jnp.stack(v), *params)
    batched, ok = jax.jit(jax.vmap(step, in_axes=(0, 0, None)))(
        stacked_states, stacked_params, 0.0625
    )
    assert bool(jnp.all(ok))
    for i, (state, single_ok) in enumerate(singles):
        assert bool(single_ok)
        for a, b in zip(state, batched, strict=True):
            np.testing.assert_allclose(np.asarray(a), np.asarray(b[i]), rtol=0, atol=1e-15)
    # RK4 refuses a step whose dt * rho exceeds 2 at the start state; just below
    # (at every evaluated state) it is accepted.
    s, p = states[0], params[0]
    rho = float(vm.hessian_rate(s.position, p.topology, p.box, av.mechanics(s), p.friction))
    refused, refused_ok = single(s, p, 2.0 / rho * 1.05)
    assert not bool(refused_ok)
    for a, b in zip(refused, s, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    assert bool(single(s, p, 0.5 / rho)[1])


def test_energy_rise_alone_refuses_a_step(monkeypatch):
    spec = parse_spec(honeycomb(displacement=0.005, seed=8, solver="euler"))
    state, layout = av.initial_values(spec)
    state = jax.tree.map(jnp.asarray, state)
    p = jax.tree.map(jnp.asarray, av.parameters(spec, layout))
    x, mech = state.position, av.mechanics(state)
    force = vm.forces(x, p.topology, p.box, mech)
    hessian = jax.hessian(vm.energy)(x, p.topology, p.box, mech)
    n = x.size
    curvature = float(force.ravel() @ (hessian.reshape(n, n) @ force.ravel()))
    dt = 3.0 * float(jnp.sum(force * force)) / curvature  # Euler overshoots: energy rises.
    trial = x + dt * force
    assert float(vm.energy(trial, p.topology, p.box, mech)) > float(
        vm.energy(x, p.topology, p.box, mech)
    )
    assert bool(vm.domain_valid(trial, p.topology, p.box, p.length_floor))
    monkeypatch.setattr(av, "_rate", lambda s, q: jnp.array(0.0))  # Disable the step bound.
    control = av.Control(*state[2:6])
    refused, ok = jax.jit(lambda s: av.checked_step(s, dt, control, p, None))(state)
    assert not bool(ok)
    for a, b in zip(refused, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
