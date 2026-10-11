"""Classical RK4 over a PyTree; the caller fixes inputs within each segment."""

import jax
import jax.numpy as jnp


def rk4_step(rhs, state, dt, *args):
    def increment(derivative, factor):
        return jax.tree.map(lambda y, dy: y + factor * dt * dy, state, derivative)

    k1 = rhs(state, *args)
    k2 = rhs(increment(k1, 0.5), *args)
    k3 = rhs(increment(k2, 0.5), *args)
    k4 = rhs(increment(k3, 1.0), *args)
    return jax.tree.map(
        lambda y, a, b, c, d: y + (dt / 6.0) * (a + 2.0 * b + 2.0 * c + d),
        state,
        k1,
        k2,
        k3,
        k4,
    )


def rk4_checked_step(rhs, valid, state, dt, control, parameters, active):
    """RK4 with refusal at every trial and endpoint, without modifying biology.

    A false status means NO step was accepted. Guard invalid states before RHS
    evaluation (in particular logs); never repair concentrations or return a
    clipped trajectory. Status is numerical metadata, not checkpoint state.
    A model may supply valid.with_control(state, control, parameters, active)
    for an algebraic constraint whose domain depends on the held controls.
    Existing state-only guards keep their original call path.
    """

    def valid_trial(trial):
        contextual = getattr(valid, "with_control", None)
        return (
            valid(trial, parameters, active)
            if contextual is None
            else contextual(trial, control, parameters, active)
        )

    def evaluate(trial):
        ok = valid_trial(trial)
        slope = jax.lax.cond(
            ok,
            lambda y: rhs(y, control, parameters, active),
            lambda y: jax.tree.map(jnp.zeros_like, y),
            trial,
        )
        finite = jnp.all(jnp.stack([jnp.all(jnp.isfinite(v)) for v in slope]))
        return slope, ok & finite

    def increment(derivative, factor):
        return jax.tree.map(lambda y, dy: y + factor * dt * dy, state, derivative)

    k1, a = evaluate(state)
    k2, b = evaluate(increment(k1, 0.5))
    k3, c = evaluate(increment(k2, 0.5))
    k4, d = evaluate(increment(k3, 1.0))
    updated = jax.tree.map(
        lambda y, a, b, c, d: y + (dt / 6.0) * (a + 2.0 * b + 2.0 * c + d),
        state,
        k1,
        k2,
        k3,
        k4,
    )
    ok = a & b & c & d & valid_trial(updated)
    return jax.tree.map(lambda old, new: jnp.where(ok, new, old), state, updated), ok
