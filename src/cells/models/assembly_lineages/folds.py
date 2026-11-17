"""Serial left folds over a leading axis, the same arithmetic in NumPy and JAX (D182, D165).

A sum over molecule types, or over the kernel's channels, is a serial left fold in declared order:
total = v[0], then total = total + v[k] for k = 1, 2, ... It is never a tree reduce, so bitwise
equal terms give bitwise equal totals on the host and on any device. On the device the input
passes through jax.lax.optimization_barrier first, so that XLA cannot contract the callers'
products into the adds (FMA), which D182 measured to make host and device differ.

- prefix(values, xp): every partial total along axis 0 (NumPy's cumsum is this fold: an
  accumulate is sequential, unlike a sum). The kernel draws its channel from these.
- total(values, xp): the last partial total, carried alone on the device.

`unroll` (device only) sets how many fold steps one loop trip holds. It changes the compiled
loop, never the order of the additions, so every value is the same for every unroll.
"""

import numpy as np

UNROLL = 8


def prefix(values, xp, unroll=UNROLL):
    if xp is np:
        return np.cumsum(values, axis=0)
    import jax
    import jax.numpy as jnp

    values = jax.lax.optimization_barrier(values)

    def step(running, value):
        running = running + value
        return running, running

    _, rest = jax.lax.scan(step, values[0], values[1:], unroll=unroll)
    return jnp.concatenate((values[:1], rest))


def total(values, xp, unroll=UNROLL):
    if xp is np:
        return np.cumsum(values, axis=0)[-1]
    import jax

    values = jax.lax.optimization_barrier(values)
    result, _ = jax.lax.scan(
        lambda running, v: (running + v, None), values[0], values[1:], unroll=unroll
    )
    return result
