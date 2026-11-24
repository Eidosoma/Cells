"""A static-pattern sparse Cholesky for the field's node-space SPD systems (FR-17 stage 1;
docs/FIELD_SOLVER_INTERFACE_DESIGN.md §8, approved 23 November 2026, D317).

Phases, as §6 and §8.3 of the design state them:
- `bind` (host, NumPy and the standard library only, once per definition) takes the pattern of an
  SPD system: its size and its off-diagonal coordinates (topology fixes them; the diagonal is
  implied). It returns a `Symbolic` (host only): a minimum-degree order of our own (the lead's
  ruling, 23 November: no new dependency), the filled factor pattern, the elimination tree and its
  levels. From a Symbolic, `factor_plan` and `solve_plan` give the plans of the numeric passes, and
  `product_plan` gives a matrix-vector product's plan on a pattern. A plan is a NamedTuple of
  integer and boolean arrays whose shapes fix every static choice (the number of levels, their
  padded widths, the pairwise steps), so it can be bound as layout leaves: a checkpoint carries it
  and validate_checkpoint compares it, as any layout array.
- `factor` (xp NumPy or jax.numpy) computes the numeric factor on the bound pattern, level by level.
- `solve` is forward and back substitution, level by level.
- `product` is the matrix-vector product on a pattern.
No n x n array is formed anywhere.

Numerics:
- Left-looking Cholesky by levels: each entry is its assembled value minus the sum of its update
  terms L_ik L_jk (k the earlier columns that hold both rows); a pivot is the square root of its
  entry, and a below entry is multiplied by the reciprocal of its column's pivot (dpotf2's order).
- The solves apply each pivot as the dense path does on the same backend. On the device they
  multiply by its reciprocal, as XLA's dtrsm does: measured on this jaxlib (0.11.1, OpenBLAS), the
  dense cho_solve of a diagonal system is (b (1/l)) (1/l) bit for bit at every size tried, and
  differs from (b / l) / l on about 40% of entries. On the host (NumPy) they divide, as the dense
  host solve (surface_field.cholesky_solve, NumPy's dgesv on blocks) does: (b / l) / l, measured
  likewise (/mnt/workspaces/Cells/fr17-sparse-20261123/tools/). So a diagonal reduction's host
  results, which bind stores in the layout, are the dense ID's too, and its device results are.
  The host and the device therefore differ in the last bit of a solve, as the dense ID's do; the
  factor and every sum are the same on both.
- Every sum is a pairwise sum in a fixed tree (`pairwise_plan`, `fold`): one output's terms in
  ascending order of their column, added in adjacent pairs, step by step until one partial is left.
  It is a defined order on the host and the device alike. No scatter-add is used anywhere (XLA
  leaves the order of duplicate updates undefined); every scatter here writes distinct positions,
  apart from padding's writes to a sink slot that nothing reads. The terms are products: on the
  device they pass an optimization barrier first, so XLA cannot contract a product into the add
  that follows it (FMA), as numerics/species_sums does. A pairwise tree rather than a serial fold,
  because a hub row (a bath that holds every cell's patch) would make a serial fold as many
  dependent steps as the hub has entries.
- A diagonal system has one level and no terms: its factor is the square root of each diagonal entry
  and its solve two applications of the pivot, the dense path's operations. A zero right-hand side
  keeps its sign here; from 64 rows the dense device path's blocked dtrsm turns some -0.0 into
  +0.0 (measured), so the two can differ in the sign of a zero, never in a value.
- Not bitwise to a dense factorisation in general: the elimination and summation orders differ. The
  method is backward stable for SPD systems in any order.

Padding (plans are padded to uniform shapes across levels): a padded entry or node reads and writes
a sink slot appended to the value array (position F, or n for a node vector), which nothing real
reads; a padded pairwise step adds -0.0, the exact identity of IEEE addition; an output with no
terms takes +0.0, so subtracting it leaves its value exactly (signed zeros included).

A pivot that is not positive gives NaN (the square root of a negative) or an infinite reciprocal in
the factor, as the dense Cholesky's does. The callers' acceptance checks (finite factors, the
solves' residuals) refuse it; nothing here regularises.
"""

import heapq
from typing import NamedTuple

import numpy as np

# The level loop's static gate (by the plan's shape): up to this many levels the passes are unrolled
# as written; above, the same passes run as a lax.fori_loop over the levels on the device (the host
# always loops in Python). Both forms perform the same operations in the same order.
UNROLLED_LEVELS = 16


class Symbolic(NamedTuple):
    """The host's structure of one SPD pattern in its elimination order (not layout leaves).

    The factor's entries are stored column by column in elimination order: column k (the k-th
    eliminated node, order[k]) holds its diagonal, then its below rows ascending in rank."""

    size: int
    order: object  # [n] int64: the elimination order (order[k] is the k-th eliminated node).
    rank: object  # [n] int64: the inverse permutation.
    column_start: object  # [n + 1] int64: column k's entries are column_start[k]:column_start[k+1].
    row: object  # [F] int64: each entry's row, as a node.
    column: object  # [F] int64: each entry's column, as a node.
    parent: object  # [n] int64: the elimination tree by rank (-1 at a root).
    level: object  # [n] int64: each column's level by rank (leaves 0; a parent above its children).
    structure: tuple  # per rank: the ranks of the column's below rows, ascending.
    position: dict  # (row rank, column rank) -> the entry's position, row rank >= column rank.


class FactorPlan(NamedTuple):
    """The numeric factor's plan: per level, its columns' entries and their update terms."""

    entry: object  # [L, E] int64: the level's entries (factor positions; padding: the sink F).
    pivot: object  # [L, E] int64: each entry's column pivot, as a slot of `entry` (padding: 0).
    is_pivot: object  # [L, E] bool.
    terms: object  # [L, 2, T] int64: each update term's two factor positions (padding: 0).
    pairs: object  # [L, 2, S, N] int64: the terms' pairwise sums per entry (pairwise_plan).
    out: object  # [L, E] int64: each entry's sum among the last partials.
    column: object  # [F] int64: each factor entry's column, as a node (its shape is the factor's).


class SolvePlan(NamedTuple):
    """The solves' plan: per level, its columns as nodes, their pivots and their terms."""

    node: object  # [L, P] int64: the level's columns, as nodes (padding: the sink n).
    pivot: object  # [L, P] int64: their pivots' factor positions (padding: 0).
    forward: object  # [L, 2, Tf] int64: each forward term's factor position and node.
    forward_pairs: object  # [L, 2, Sf, Nf] int64.
    forward_out: object  # [L, P] int64.
    back: object  # [L, 2, Tb] int64: each back term's factor position and node.
    back_pairs: object  # [L, 2, Sb, Nb] int64.
    back_out: object  # [L, P] int64.


class ProductPlan(NamedTuple):
    """A matrix-vector product's plan on a symmetric pattern with its whole diagonal. Its entries
    are in row order, then column order; a value array on the pattern follows that order."""

    row: object  # [nnz] int64: each entry's row.
    column: object  # [nnz] int64: each entry's column.
    pairs: object  # [2, S, N] int64: the row sums' pairwise plan over the entries.
    out: object  # [n] int64: each row's sum among the last partials.
    diagonal: object  # [n] int64: each row's diagonal entry.


def _neighbours(size, rows, columns):
    rows, columns = np.asarray(rows, dtype=np.int64), np.asarray(columns, dtype=np.int64)
    if rows.shape != columns.shape or rows.ndim != 1:
        raise ValueError("A sparse pattern's coordinates must be two equal one-dimensional arrays")
    if rows.size and (min(rows.min(), columns.min()) < 0 or max(rows.max(), columns.max()) >= size):
        raise ValueError("A sparse pattern's coordinates must lie within its size")
    neighbours = [set() for _ in range(size)]
    for i, j in zip(rows.tolist(), columns.tolist(), strict=True):
        if i != j:
            neighbours[i].add(j)
            neighbours[j].add(i)
    return neighbours


def minimum_degree(size, rows, columns):
    """A minimum-degree elimination order of a symmetric pattern (its off-diagonal coordinates,
    either or both triangles): repeatedly the node of least current degree in the elimination graph,
    ties by the least original degree and then the smallest index (so an arrowhead's hub, tied at
    the end with its last leaf, goes last: two levels); its neighbours then form a clique. A heap of
    (degree, original degree, index), entries made stale by a degree change skipped. Deterministic,
    NumPy and the standard library only."""
    adjacency = _neighbours(size, rows, columns)
    original = [len(a) for a in adjacency]
    heap = [(original[i], original[i], i) for i in range(size)]
    heapq.heapify(heap)
    alive = [True] * size
    order = []
    while heap:
        degree, _, node = heapq.heappop(heap)
        if not alive[node] or degree != len(adjacency[node]):
            continue
        alive[node] = False
        order.append(node)
        neighbours = adjacency[node]
        for a in neighbours:
            adjacency[a].discard(node)
            adjacency[a] |= neighbours - {a}
            heapq.heappush(heap, (len(adjacency[a]), original[a], a))
        adjacency[node] = set()
    return np.asarray(order, dtype=np.int64)


def bind(size, rows, columns, order=None):
    """The Symbolic of an SPD pattern of `size` nodes whose off-diagonal entries are at (rows,
    columns) (either or both triangles; the diagonal is implied), in `order` (default
    minimum_degree)."""
    if type(size) is not int or size < 1:
        raise ValueError("A sparse pattern needs a positive integer size")
    neighbours = _neighbours(size, rows, columns)
    if order is None:
        order = minimum_degree(size, rows, columns)
    order = np.asarray(order, dtype=np.int64)
    if order.shape != (size,) or sorted(order.tolist()) != list(range(size)):
        raise ValueError("The elimination order must be a permutation")
    rank = np.empty(size, dtype=np.int64)
    rank[order] = np.arange(size)
    # Symbolic factorisation: column k's rows are its own later neighbours and those of every child
    # column above k (the elimination tree's union rule).
    below = [set() for _ in range(size)]
    for i in range(size):
        r = int(rank[i])
        below[r].update(int(rank[a]) for a in neighbours[i] if rank[a] > r)
    parent = np.full(size, -1, dtype=np.int64)
    for k in range(size):
        if below[k]:
            p = min(below[k])
            parent[k] = p
            below[p] |= below[k] - {p}
    structure = tuple(tuple(sorted(b)) for b in below)
    column_start = np.zeros(size + 1, dtype=np.int64)
    column_start[1:] = np.cumsum([1 + len(b) for b in structure])
    entry_row, entry_column, position = [], [], {}
    for k, rows_k in enumerate(structure):
        for r in (k, *rows_k):
            position[(r, k)] = len(entry_row)
            entry_row.append(int(order[r]))
            entry_column.append(int(order[k]))
    level = np.zeros(size, dtype=np.int64)
    for k in range(size):
        if parent[k] >= 0:
            level[parent[k]] = max(level[parent[k]], level[k] + 1)
    return Symbolic(
        size=size,
        order=order,
        rank=rank,
        column_start=column_start,
        row=np.asarray(entry_row, dtype=np.int64),
        column=np.asarray(entry_column, dtype=np.int64),
        parent=parent,
        level=level,
        structure=structure,
        position=position,
    )


def positions(symbolic, rows, columns):
    """The factor positions of the entries (rows[q], columns[q]) (nodes, either orientation), each
    in the bound pattern (a KeyError otherwise)."""
    s = symbolic
    out = np.empty(len(rows), dtype=np.int64)
    pairs = zip(np.asarray(rows).tolist(), np.asarray(columns).tolist(), strict=True)
    for q, (i, j) in enumerate(pairs):
        a, b = int(s.rank[i]), int(s.rank[j])
        out[q] = s.position[(max(a, b), min(a, b))]
    return out


def _row_structures(symbolic):
    """Per rank r, the column ranks m < r whose column holds row r, ascending."""
    rows = [[] for _ in range(symbolic.size)]
    for m, rows_m in enumerate(symbolic.structure):
        for r in rows_m:
            rows[r].append(m)
    return rows


def _levels(symbolic):
    """The column ranks of each level, ascending."""
    count = int(symbolic.level.max(initial=-1)) + 1
    return [np.flatnonzero(symbolic.level == value).tolist() for value in range(count)]


def _pairwise_steps(segments):
    """The pairwise steps of one set of segments (lists of indices into the partials before the
    first step): a list of steps, each a list of (left, right) pairs whose None stands for the
    identity slot; and each segment's final partial (None when empty)."""
    current = [list(segment) for segment in segments]
    steps = []
    while any(len(c) > 1 for c in current):
        step, following = [], []
        for c in current:
            new = []
            for a in range(0, len(c), 2):
                step.append((c[a], c[a + 1] if a + 1 < len(c) else None))
                new.append(len(step) - 1)
            following.append(new)
        steps.append(step)
        current = following
    return steps, [c[0] if c else None for c in current]


def _padded_folds(groups, term_count):
    """pairs [G, 2, S, N] and out [G, M] for G groups of segments (each group: a list of segments, a
    segment a list of term indices into an array of term_count terms), padded to common shapes. The
    identity slot follows each step's input (index term_count before the first step, N after); the
    empty slot is the one after it. A group with fewer steps passes its partials through."""
    built = [_pairwise_steps(segments) for segments in groups]
    depth = max((len(steps) for steps, _ in built), default=0)
    padded = []
    for steps, finals in built:
        steps = [list(step) for step in steps]
        live = len(steps[-1]) if steps else None  # Partials alive after the last real step.
        while len(steps) < depth:
            if live is None:  # No step yet: the terms pass through, one partial each.
                live = max((f + 1 for f in finals if f is not None), default=0)
            steps.append([(k, None) for k in range(live)])
        padded.append((steps, finals))
    width = max((len(step) for steps, _ in padded for step in steps), default=0)
    count = len(groups)
    outputs = max((len(finals) for _, finals in padded), default=0)
    pairs = np.zeros((count, 2, depth, width), dtype=np.int64)
    out = np.zeros((count, outputs), dtype=np.int64)
    for g, (steps, finals) in enumerate(padded):
        for s, step in enumerate(steps):
            identity = term_count if s == 0 else width
            pairs[g, :, s, :] = identity
            for k, (a, b) in enumerate(step):
                pairs[g, 0, s, k] = a
                pairs[g, 1, s, k] = identity if b is None else b
        empty = (term_count if depth == 0 else width) + 1
        out[g, :] = empty
        for m, f in enumerate(finals):
            out[g, m] = empty if f is None else f
    return pairs, out


def pairwise_plan(segments, term_count):
    """pairs [2, S, N] and out [M] for fold: segment m's terms (indices into an array of term_count
    terms, in summation order) summed in adjacent pairs, step by step."""
    pairs, out = _padded_folds([segments], term_count)
    return pairs[0], out[0]


def _barrier(values, xp):
    """jax.lax.optimization_barrier on the device; the identity on the host."""
    if xp is np:
        return values
    import jax

    return jax.lax.optimization_barrier(values)


def _tail(partial, xp):
    """The identity (-0.0) and empty (+0.0) slots appended after a partial array's first axis."""
    shape = (1, *partial.shape[1:])
    return xp.concatenate(
        (partial, xp.full(shape, -0.0, dtype=partial.dtype), xp.zeros(shape, dtype=partial.dtype))
    )


def fold(terms, pairs, out, *, xp):
    """Segmented pairwise sums along the first axis (pairwise_plan's plan): one sum per output, +0.0
    for an output with no terms. Trailing axes are independent."""
    partial = terms
    for s in range(pairs.shape[-2]):
        padded = _tail(partial, xp)
        partial = padded[pairs[0, s]] + padded[pairs[1, s]]
    return _tail(partial, xp)[out]


def _broadcast(values, like):
    """values [k] shaped to multiply an array [k, ...] along its first axis."""
    return values.reshape(values.shape + (1,) * (like.ndim - 1))


def _set(values, index, updates, *, xp):
    if xp is np:
        out = np.array(values, copy=True)
        out[index] = updates
        return out
    return values.at[index].set(updates)


def _arrays(plan, xp):
    """The plan's arrays as xp arrays (the device's level loop indexes them by a traced level)."""
    return plan if xp is np else type(plan)(*(xp.asarray(a) for a in plan))


def _loop(count, body, carry, *, xp, reverse=False):
    """body(level, carry) for each level in order (or reversed): unrolled up to UNROLLED_LEVELS, a
    lax.fori_loop on the device above (the same operations in the same order)."""
    if xp is np or count <= UNROLLED_LEVELS:
        for k in reversed(range(count)) if reverse else range(count):
            carry = body(k, carry)
        return carry
    import jax

    if reverse:
        return jax.lax.fori_loop(0, count, lambda i, c: body(count - 1 - i, c), carry)
    return jax.lax.fori_loop(0, count, body, carry)


def factor_plan(symbolic):
    """The FactorPlan of a Symbolic (host)."""
    s, rows_of = symbolic, _row_structures(symbolic)
    levels, groups, entries, pivots, flags, all_terms = _levels(s), [], [], [], [], []
    for columns in levels:
        entry, pivot, is_pivot, terms, segments = [], [], [], [], []
        for k in columns:
            own = len(entry)
            for r in (k, *s.structure[k]):
                entry.append(s.position[(r, k)])
                pivot.append(own)
                is_pivot.append(r == k)
                common = rows_of[k] if r == k else sorted(set(rows_of[r]) & set(rows_of[k]))
                segment = []
                for m in common:
                    segment.append(len(terms))
                    terms.append((s.position[(r, m)], s.position[(k, m)]))
                segments.append(segment)
        entries.append(entry)
        pivots.append(pivot)
        flags.append(is_pivot)
        all_terms.append(terms)
        groups.append(segments)
    width = max(len(e) for e in entries)
    term_count = max(len(t) for t in all_terms)
    pairs, out = _padded_folds(groups, term_count)
    sink = int(s.column_start[-1])
    shape = (len(levels), width)
    plan_entry, plan_pivot = np.full(shape, sink, dtype=np.int64), np.zeros(shape, dtype=np.int64)
    plan_is_pivot = np.zeros(shape, dtype=bool)
    plan_terms = np.zeros((len(levels), 2, term_count), dtype=np.int64)
    for v in range(len(levels)):
        count = len(entries[v])
        plan_entry[v, :count] = entries[v]
        plan_pivot[v, :count] = pivots[v]
        plan_is_pivot[v, :count] = flags[v]
        if all_terms[v]:
            plan_terms[v, :, : len(all_terms[v])] = np.asarray(all_terms[v], dtype=np.int64).T
    return FactorPlan(plan_entry, plan_pivot, plan_is_pivot, plan_terms, pairs, out[:, :width],
                      s.column.copy())  # fmt: skip


def solve_plan(symbolic):
    """The SolvePlan of a Symbolic (host)."""
    s, rows_of = symbolic, _row_structures(symbolic)
    levels = _levels(s)
    width = max(len(c) for c in levels)
    node = np.full((len(levels), width), s.size, dtype=np.int64)
    pivot = np.zeros((len(levels), width), dtype=np.int64)
    forward_groups, forward_terms, back_groups, back_terms = [], [], [], []
    for v, columns in enumerate(levels):
        node[v, : len(columns)] = s.order[columns]
        pivot[v, : len(columns)] = s.column_start[columns]
        terms, segments = [], []
        for k in columns:  # Forward: row k's earlier columns.
            segments.append(list(range(len(terms), len(terms) + len(rows_of[k]))))
            terms += [(s.position[(k, m)], int(s.order[m])) for m in rows_of[k]]
        forward_groups.append(segments)
        forward_terms.append(terms)
        terms, segments = [], []
        for k in columns:  # Back: column k's later rows.
            segments.append(list(range(len(terms), len(terms) + len(s.structure[k]))))
            terms += [(s.position[(r, k)], int(s.order[r])) for r in s.structure[k]]
        back_groups.append(segments)
        back_terms.append(terms)

    def arrays(groups, terms):
        count = max(len(t) for t in terms)
        pairs, out = _padded_folds(groups, count)
        packed = np.zeros((len(levels), 2, count), dtype=np.int64)
        for v, t in enumerate(terms):
            if t:
                packed[v, :, : len(t)] = np.asarray(t, dtype=np.int64).T
        return packed, pairs, out[:, :width]

    return SolvePlan(node, pivot, *arrays(forward_groups, forward_terms),
                     *arrays(back_groups, back_terms))  # fmt: skip


def product_plan(size, rows, columns):
    """The ProductPlan of the symmetric pattern of `size` nodes with off-diagonal entries at (rows,
    columns) (either or both triangles) and its whole diagonal."""
    neighbours = _neighbours(size, rows, columns)
    entry_row, entry_column, segments, diagonal = [], [], [], np.zeros(size, dtype=np.int64)
    for i in range(size):
        start = len(entry_row)
        for j in sorted(neighbours[i] | {i}):
            if j == i:
                diagonal[i] = len(entry_row)
            entry_row.append(i)
            entry_column.append(j)
        segments.append(list(range(start, len(entry_row))))
    pairs, out = pairwise_plan(segments, len(entry_row))
    return ProductPlan(
        np.asarray(entry_row, dtype=np.int64),
        np.asarray(entry_column, dtype=np.int64),
        pairs,
        out,
        diagonal,
    )


def product(values, x, plan, *, xp):
    """A x for the matrix A whose entries on the plan's pattern are `values` (x [n] or [n, ...]; its
    trailing axes are independent): each row's products summed in the plan's pairwise order."""
    terms = _barrier(_broadcast(values, x) * x[plan.column], xp)
    return fold(terms, plan.pairs, plan.out, xp=xp)


def factor(values, plan, *, xp):
    """The numeric factor (module docstring) of an assembled value array [F] (the system's entries
    at their factor positions, zero at the fill): the factor's entries at the same positions."""
    plan = _arrays(plan, xp)
    v = xp.concatenate((values, xp.zeros(1, dtype=values.dtype)))  # The sink.
    with_terms = plan.terms.shape[-1] > 0

    def level(k, v):
        entry, pivot, is_pivot = plan.entry[k], plan.pivot[k], plan.is_pivot[k]
        acc = v[entry]
        if with_terms:
            terms = _barrier(v[plan.terms[k, 0]] * v[plan.terms[k, 1]], xp)
            acc = acc - fold(terms, plan.pairs[k], plan.out[k], xp=xp)
        root = xp.sqrt(xp.where(is_pivot, acc, 1.0))
        return _set(v, entry, xp.where(is_pivot, root, acc * (1.0 / root[pivot])), xp=xp)

    return _loop(plan.entry.shape[0], level, v, xp=xp)[:-1]


def solve(factor_values, rhs, plan, *, xp):
    """x with A x = rhs for the factored A (rhs [n] or [n, ...], in node order; its trailing axes
    are independent)."""
    f, plan = factor_values, _arrays(plan, xp)
    y = xp.concatenate((rhs, xp.zeros((1, *rhs.shape[1:]), dtype=rhs.dtype)))  # The sink.

    def substitute(k, y, terms, pairs, out):
        node, pivot = plan.node[k], _broadcast(f[plan.pivot[k]], y)
        known = y[node]
        if terms.shape[-1] > 0:
            products = _barrier(_broadcast(f[terms[k, 0]], y) * y[terms[k, 1]], xp)
            known = known - fold(products, pairs[k], out[k], xp=xp)
        if xp is np:  # The dense host solve's division (module docstring).
            return _set(y, node, known / pivot, xp=xp)
        return _set(y, node, known * (1.0 / pivot), xp=xp)  # The device dtrsm's reciprocal.

    count = plan.node.shape[0]
    y = _loop(count, lambda k, y: substitute(k, y, plan.forward, plan.forward_pairs,
                                             plan.forward_out), y, xp=xp)  # fmt: skip
    y = _loop(count, lambda k, y: substitute(k, y, plan.back, plan.back_pairs, plan.back_out), y,
              xp=xp, reverse=True)  # fmt: skip
    return y[:-1]


def finite(factor_values, *, xp):
    """Whether every factor entry is finite (the sink excluded: factor returns none)."""
    return xp.all(xp.isfinite(factor_values))
