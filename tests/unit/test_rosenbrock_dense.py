"""cells.solver.rosenbrock_rodas4_dense@1 (OL6 S1; docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §6.1).

Five checks, each on a closed form, so a wrong coefficient fails one: the solution's order (4), the
dense output's order (3), a linear invariant kept to rounding, L-stability on a stiff linear system,
and the adaptive controller's accuracy. Small programs only: about 10 s, compiling included (D224:
the method's own proof, a new file because the module is new).
"""

import math

import jax
import jax.numpy as jnp
import numpy as np

from cells.numerics import rosenbrock_dense as rd

jax.config.update("jax_enable_x64", True)


def logistic(y):
    return y * (1.0 - y)


def logistic_exact(t, y0=0.1):
    return 1.0 / (1.0 + (1.0 / y0 - 1.0) * math.exp(-t))


def fixed_steps(rhs, y0, horizon, count, theta=None):
    jac = jax.jacfwd(rhs)
    one = jax.jit(lambda y, h: rd.step(rhs, jac, y, h))
    y, h, mids = jnp.asarray(y0), horizon / count, []
    for _ in range(count):
        result = one(y, h)
        if theta is not None:
            mids.append(np.asarray(rd.dense(y, result, theta)))
        y = result.y
    return np.asarray(y), mids


def test_the_solution_is_of_order_four_and_the_dense_output_of_order_three():
    errors, dense_errors = [], []
    for count in (10, 20, 40):
        y, mids = fixed_steps(logistic, np.array([0.1]), 4.0, count, theta=0.5)
        errors.append(abs(y[0] - logistic_exact(4.0)))
        h = 4.0 / count
        dense_errors.append(max(abs(m[0] - logistic_exact((k + 0.5) * h)) for k, m in enumerate(mids)))
    orders = [math.log2(errors[i] / errors[i + 1]) for i in range(2)]
    dense_orders = [math.log2(dense_errors[i] / dense_errors[i + 1]) for i in range(2)]
    assert min(orders) > 3.7, orders
    assert min(dense_orders) > 2.7, dense_orders


def test_a_linear_invariant_is_kept_to_rounding():
    # A + B <-> C and C <-> 2D: the moiety a = n_A + n_C + n_D/2 is kept by every step's stages.
    def rhs(n):
        j1 = 2.0 * n[0] * n[1] - 0.7 * n[2]
        j2 = 1.3 * n[2] - 0.4 * n[3] ** 2
        return jnp.stack((-j1, -j1, j1 - j2, 2.0 * j2))

    y0 = np.array([1.0, 0.6, 0.1, 0.2])
    y, _ = fixed_steps(rhs, y0, 3.0, 17)
    moiety = np.array([1.0, 0.0, 1.0, 0.5])
    assert abs(moiety @ y - moiety @ y0) <= 4 * np.finfo(float).eps * (moiety @ y0) * 17


def test_a_stiff_linear_system_is_damped_and_accurate_at_large_steps():
    # y1' = -1e4 (y1 - y2), y2' = -y2: the fast mode decays in 1e-4; steps of 0.05 (h λ = -500).
    def rhs(y):
        return jnp.stack((-1e4 * (y[0] - y[1]), -y[1]))

    y, _ = fixed_steps(rhs, np.array([1.0, 1.0]), 2.0, 40)
    slow = math.exp(-2.0)
    fast_limit = slow * 1e4 / (1e4 - 1.0)  # y1 follows y2 on the slow manifold
    assert abs(y[1] - slow) < 1e-7
    assert abs(y[0] - fast_limit) < 1e-6


def test_the_controller_meets_its_tolerance():
    jac = jax.jacfwd(logistic)
    one = jax.jit(lambda y, h: rd.step(logistic, jac, y, h))
    norm = jax.jit(rd.error_norm)
    rtol, atol, weight = 1e-8, 1e-12, jnp.ones(1)
    t, y = 0.0, jnp.asarray([0.1])
    h = rd.initial_step(logistic, y, rtol, atol, weight, 6.0)
    accepted = rejected = 0
    last_rejected = False
    while t < 6.0:
        h = min(h, 6.0 - t)
        result = one(y, h)
        e = float(norm(result.error, y, result.y, rtol, atol, weight))
        if e <= 1.0 and bool(result.finite):
            t, y = t + h, result.y
            accepted += 1
            last_rejected = False
        else:
            rejected += 1
            last_rejected = True
        h = rd.next_step(h, e, last_rejected)
    assert abs(float(y[0]) - logistic_exact(6.0)) < 1e-7
    assert accepted < 200


def test_a_carried_quantity_is_of_order_four_and_leaves_the_steps_unchanged():
    # Z' = y² along the logistic y, carried by the stages (OL6 S3, the hazard clock's H):
    # ∫_0^t y² = ln(e^t + a) − ln(1 + a) − y(t) + y0, a = 1/y0 − 1 (y² = y − y').
    def rate(y):
        return y[0] ** 2

    jac, grad = jax.jacfwd(logistic), jax.grad(rate)
    one = jax.jit(lambda y, h: rd.step(logistic, jac, y, h))
    carry = jax.jit(lambda y, h, stages: rd.quadrature(rate, grad, y, h, stages))
    a, horizon, errors, dense_errors = 9.0, 4.0, [], []
    for count in (10, 20, 40):
        y, z, h, worst = jnp.asarray([0.1]), 0.0, horizon / count, 0.0
        for k in range(count):
            result = one(y, h)
            carried = carry(y, h, result.stages)
            t = (k + 0.5) * h
            mid = float(rd.dense_carried(z, carried, 0.5))
            exact_mid = math.log(math.exp(t) + a) - math.log(1 + a) - logistic_exact(t) + 0.1
            worst = max(worst, abs(mid - exact_mid))
            y, z = result.y, z + float(carried.increment)
        exact = math.log(math.exp(horizon) + a) - math.log(1 + a) - logistic_exact(horizon) + 0.1
        errors.append(abs(z - exact))
        dense_errors.append(worst)
    orders = [math.log2(errors[i] / errors[i + 1]) for i in range(2)]
    dense_orders = [math.log2(dense_errors[i] / dense_errors[i + 1]) for i in range(2)]
    assert min(orders) > 3.7, orders
    assert min(dense_orders) > 2.7, dense_orders
    # The step that carries a quantity is its twin's, bit for bit (the quantity reads y, never back).
    plain = jax.jit(lambda y, h: rd.step(logistic, jac, y, h).y)
    assert np.array_equal(np.asarray(plain(jnp.asarray([0.1]), 0.4)),
                          np.asarray(one(jnp.asarray([0.1]), 0.4).y))  # fmt: skip
