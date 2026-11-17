"""Registered probe inputs: the states at which the engine evaluates its kernel.

The kernel probe lists member-count states. At each listed state p, and for each step r in the
world's order, the engine reports two numbers:
- a_plus[p, r]: the rate of the forward channel, p -> p + nu_r (zero where impossible);
- a_minus[p, r]: the rate of the reverse channel, p -> p - nu_r (zero where impossible).

The list is built so that detailed balance can be decided without any convention:
- **squares.** For each base state n and each pair of steps (r, q), the four corners n,
  n + nu_r, n + nu_q and n + nu_r + nu_q are listed. Kolmogorov's criterion on the square needs
  only the eight rates around it.
- **parallel pairs.** Steps with the same net change (r1 and r4 in ``ol1_wa``) form two-cycles,
  n -> n + nu by one and back by the other.
- **boundary states** are listed explicitly: the empty assembly, every one-member state, and
  the states where a catalysed step's common state is empty. This is where conventions act, so
  they are pinned in the registered inputs rather than relayed (G2's lesson: its disagreement
  surfaced on four mass-1 states).

Base states are drawn from a registered seed through NumPy's ``Generator``: each finite place's
count uniform on 0..``max_count``, rejecting a membrane total below 2.
"""

from __future__ import annotations

import itertools

import numpy as np

from .world import World

KERNEL_PROBE_SEED = 2026111701
KERNEL_PROBE_BASES = 24
KERNEL_PROBE_MAX_COUNT = 9


def add(n, d, sign=1):
    return tuple(a + sign * b for a, b in zip(n, d))


def valid(n) -> bool:
    return all(v >= 0 for v in n)


def step_pairs(world: World) -> list[tuple[int, int]]:
    return list(itertools.combinations(range(len(world.steps)), 2))


def parallel_pairs(world: World) -> list[tuple[int, int]]:
    nus = [world.nu(st) for st in world.steps]
    return [(r, q) for r, q in step_pairs(world) if nus[r] == nus[q]]


def antiparallel_pairs(world: World) -> list[tuple[int, int]]:
    """Steps declared in opposite directions (nu_q = -nu_r), such as a join and a declared leave."""
    nus = [world.nu(st) for st in world.steps]
    return [(r, q) for r, q in step_pairs(world) if nus[r] == tuple(-v for v in nus[q])]


def base_states(world: World, seed: int = KERNEL_PROBE_SEED, n_base: int = KERNEL_PROBE_BASES,
                max_count: int = KERNEL_PROBE_MAX_COUNT) -> list[tuple[int, ...]]:
    rng = np.random.default_rng(seed)
    out = []
    while len(out) < n_base:
        n = tuple(int(v) for v in rng.integers(0, max_count + 1, size=world.dim))
        if sum(v for v, m in zip(n, world.membrane_mask()) if m) >= 2:
            out.append(n)
    return out


def boundary_states(world: World) -> list[tuple[int, ...]]:
    """The empty state, and one and two molecules of each finite place alone.

    The dilute places are empty in all of them, so a pool step never fires at an empty
    membrane and no convention beyond the declared menu is exercised."""
    G = world.dim
    out = [tuple([0] * G)]
    for i in range(G):
        for k in (1, 2):
            e = [0] * G
            e[i] = k
            out.append(tuple(e))
    return out


def kernel_probe_states(world: World, seed: int = KERNEL_PROBE_SEED, n_base: int = KERNEL_PROBE_BASES,
                        max_count: int = KERNEL_PROBE_MAX_COUNT) -> np.ndarray:
    """The registered probe states: every square's corners, and the boundary states, sorted."""
    nus = [world.nu(st) for st in world.steps]
    states = set(boundary_states(world))
    for n in base_states(world, seed, n_base, max_count):
        states.add(n)
        for r in range(len(nus)):
            for sign in (1, -1):
                p = add(n, nus[r], sign)
                if valid(p):
                    states.add(p)
        for r, q in step_pairs(world):
            corners = [add(n, nus[r]), add(n, nus[q]), add(add(n, nus[r]), nus[q])]
            if all(valid(c) for c in corners):
                states.update(corners)
    return np.array(sorted(states), dtype=np.int64)


def squares(world: World, states) -> list[tuple[tuple, int, int]]:
    """Every (n, r, q) whose four corners are listed (r < q, nu_r != nu_q)."""
    listed = {tuple(int(v) for v in s) for s in states}
    nus = [world.nu(st) for st in world.steps]
    out = []
    for n in sorted(listed):
        for r, q in step_pairs(world):
            if nus[r] == nus[q]:
                continue
            corners = [add(n, nus[r]), add(n, nus[q]), add(add(n, nus[r]), nus[q])]
            if all(c in listed for c in corners):
                out.append((n, r, q))
    return out


def two_cycles(world: World, states) -> list[tuple[tuple, int, int]]:
    """Every (n, r, q) for parallel steps r, q with n and n + nu_r listed."""
    listed = {tuple(int(v) for v in s) for s in states}
    nus = [world.nu(st) for st in world.steps]
    out = []
    for n in sorted(listed):
        for r, q in parallel_pairs(world):
            if add(n, nus[r]) in listed:
                out.append((n, r, q))
    return out


def antiparallel_cycles(world: World, states) -> list[tuple[tuple, int, int]]:
    """Every (n, r, q) for opposite steps r, q (nu_q = -nu_r) with n and n + nu_r listed: the
    two-cycle n -> n + nu_r by r's forward channel and back by q's forward channel."""
    listed = {tuple(int(v) for v in s) for s in states}
    nus = [world.nu(st) for st in world.steps]
    out = []
    for n in sorted(listed):
        for r, q in antiparallel_pairs(world):
            if add(n, nus[r]) in listed:
                out.append((n, r, q))
    return out


def closed_world_states(world: World, initial) -> np.ndarray:
    """Every state reachable from ``initial`` by the world's steps (both directions), sorted.

    The registered closed worlds are connected by construction; this is a breadth-first search
    over the step graph, independent of any rates.
    """
    nus = [world.nu(st) for st in world.steps]
    alphas = [world.alpha(st) for st in world.steps]
    start = world.state_from(initial) if isinstance(initial, dict) else tuple(initial)
    seen = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for n in frontier:
            for nu, al in zip(nus, alphas):
                if all(v >= a for v, a in zip(n, al)):
                    p = add(n, nu)
                    if valid(p) and p not in seen:
                        seen.add(p)
                        nxt.append(p)
                back = add(n, nu, -1)
                if valid(back) and all(v >= a for v, a in zip(back, al)) and back not in seen:
                    seen.add(back)
                    nxt.append(back)
        frontier = nxt
    return np.array(sorted(seen), dtype=np.int64)
