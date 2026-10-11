"""Independent scalar graph traversal and finite-pool reaction oracle; no JAX."""

import math

from cells.assembly.graph import EDGES

AVOGADRO = 6.02214076e23


def bonds_within(mask, bonds):
    return sum(
        1 << i
        for i, (a, b) in enumerate(EDGES)
        if bonds & (1 << i) and mask & (1 << a) and mask & (1 << b)
    )


def connected(mask, bonds, root):
    reached = {root} if mask & (1 << root) else set()
    todo = list(reached)
    while todo:
        node = todo.pop()
        for i, (a, b) in enumerate(EDGES):
            if bonds & (1 << i) and node in (a, b):
                other = b if node == a else a
                if mask & (1 << other) and other not in reached:
                    reached.add(other)
                    todo.append(other)
    return sum(1 << n for n in reached)


def rates(mask, bonds, free, fragments, spec):
    result = [0.0] * 79
    on = spec.k_on_M_inv_s * (free / (AVOGADRO * spec.pool_volume_L))
    for i, (a, b) in enumerate(EDGES):
        has_a, has_b = bool(mask & (1 << a)), bool(mask & (1 << b))
        if has_a != has_b:
            result[i] = on
        elif has_a and not bonds & (1 << i):
            result[i] = spec.k_close_s_inv
        if bonds & (1 << i):
            result[i + 30] = spec.k_off_s_inv
    for size in range(2, 21):
        result[58 + size] = fragments[size] * spec.k_fragment_dissolve_s_inv
    return result


def transition(mask, bonds, free, fragments, event, root):
    fragments = list(fragments)
    removed = 0
    if event < 30:
        a, b = EDGES[event]
        has_a, has_b = bool(mask & (1 << a)), bool(mask & (1 << b))
        if has_a != has_b:
            mask |= (1 << a) | (1 << b)
            free -= 1
            kind = 0
        else:
            kind = 1
        bonds |= 1 << event
    elif event < 60:
        bonds &= ~(1 << (event - 30))
        kept = connected(mask, bonds, root)
        removed = (mask ^ kept).bit_count()
        if removed == 1:
            free += 1
        elif removed > 1:
            fragments[removed] += 1
        mask, bonds = kept, bonds_within(kept, bonds)
        kind = 2
    else:
        size = event - 58
        fragments[size] -= 1
        free += size
        kind = 3
    return mask, bonds, free, fragments, kind, removed


def trajectory(spec, uniforms, until=None):
    mask, bonds, free = spec.initial_mask, spec.initial_bonds, spec.initial_free_trimers
    fragments, clock, result = [0] * 21, 0.0, []
    until = spec.end_time_s if until is None else until
    for u, v in uniforms:
        if not 0 < u < 1 or not 0 < v < 1:
            raise ValueError("Open-interval random variates required")
        propensities = rates(mask, bonds, free, fragments, spec)
        total = sum(propensities)
        when = clock - math.log(u) / total if total else math.inf
        if when > until:
            return result
        cumulative = 0.0
        event = None
        for index, rate in enumerate(propensities):
            cumulative += rate
            if cumulative > v * total:
                event = index
                break
        if event is None:
            raise ValueError("Reference event selection failed")
        mask, bonds, free, fragments, kind, removed = transition(
            mask, bonds, free, fragments, event, spec.root_node
        )
        clock = when
        result.append((clock, mask, bonds, free, event, tuple(fragments), kind, removed))
    raise ValueError("Reference random stream exhausted")
