"""Host-only event oracle using graph traversal and scalar Gillespie arithmetic.

No JAX or device event-enumeration code is imported. Tests supply common random
variates separately, so event physics and clock arithmetic can be compared.
"""

import math

import numpy as np

from cells.assembly.graph import EDGES, FULL, component
from cells.assembly.spec import AssemblyError


def events(mask, root, on_rate, off_rate):
    rates = np.zeros(60, dtype=np.float64)
    targets = np.full(60, mask, dtype=np.uint32)
    if mask == FULL:
        return rates, targets
    for index, (a, b) in enumerate(EDGES):
        has_a, has_b = bool(mask & (1 << a)), bool(mask & (1 << b))
        if has_a != has_b:
            rates[index] = on_rate
            targets[index] = mask | (1 << (b if has_a else a))
        if has_a and has_b:
            retained = component(mask, root, (a, b))
            if retained != mask:
                rates[index + 30] = off_rate
                targets[index + 30] = retained
    return rates, targets


def propose(mask, time_s, root, on_rate, off_rate, uniforms):
    if not all(0 < u < 1 for u in uniforms):
        raise AssemblyError("Gillespie variates must be strictly between zero and one")
    rates, targets = events(mask, root, on_rate, off_rate)
    # Same declared ordering, independently evaluated with scalar arithmetic.
    cumulative = []
    total = 0.0
    for rate in rates:
        total += float(rate)
        cumulative.append(total)
    if total == 0:
        return math.inf, mask, -1
    when = time_s - math.log(uniforms[0]) / total
    threshold = uniforms[1] * total
    index = next(i for i, value in enumerate(cumulative) if value > threshold)
    return when, int(targets[index]), index


def trajectory(spec, uniforms, until=None):
    """Unbatched oracle with a supplied stream; records only committed events."""
    horizon = spec.end_time_s if until is None else until
    mask, time_s = spec.initial_mask, 0.0
    result = []
    for pair in uniforms:
        when, target, event = propose(
            mask,
            time_s,
            spec.root_node,
            spec.k_on_M_inv_s * spec.free_trimer_M,
            spec.k_off_s_inv,
            pair,
        )
        if when > horizon:
            return result
        result.append((when, target, event))
        mask, time_s = target, when
        if mask == FULL:
            return result
    raise AssemblyError("Reference random stream exhausted before the horizon")
