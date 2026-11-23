"""A static-pattern sparse Cholesky for the field's node-space SPD systems (FR-17 stage 1;
docs/FIELD_SOLVER_INTERFACE_DESIGN.md §8, approved 23 November 2026, D317).

Three phases, as §6 and §8.3 of the design state them:
- `bind` (host, NumPy only, once per definition) takes the structural pattern of an SPD system: a
  symmetric boolean matrix with a true diagonal, which topology fixes. It returns a `Symbolic`:
  - a minimum-degree ordering of our own (the lead's ruling, 23 November: no new dependency);
  - the filled lower-triangular pattern of the factor in that order;
  - the elimination tree and its level schedule (the columns of one level depend on none of each
    other);
  - the index maps that take a value array over the system's pattern straight into the factor's;
  - per level, the index arrays of the numeric pass.
  Every array has a static shape fixed by the pattern, so a `Symbolic` can be bound as layout
  leaves.
- `factor` (device or host, `xp` jax.numpy or NumPy) computes the numeric factor on that pattern,
  one pass per level: square roots of the level's pivots, the column scaling, and the outer-product
  updates as one scatter-add (segment sum). No n x n array is formed.
- `solve` is forward and back substitution, level by level, with gathers and scatter-adds.

Numerics: right-looking Cholesky in a fill-reducing order. It is backward stable for SPD systems in
any order, and not bitwise to a dense factorisation, whose elimination and summation orders differ.
A diagonal system has one level: its factor is the square roots of the diagonal and its solve is
two divisions per row, in the dense path's order of operations.

A pivot that is not positive gives NaN in the factor (sqrt of a negative) or an infinite scaling,
as the dense Cholesky's does. The callers' acceptance checks (finite factors, the solves'
residuals) refuse it; nothing here regularises.
"""

from typing import NamedTuple

import numpy as np


class Level(NamedTuple):
    """One level's numeric pass (all int64 arrays, positions into the factor's value array)."""

    pivots: object  # [k] the level's diagonal positions.
    below: object  # [m] the positions of the level's below-diagonal entries...
    below_pivot: object  # [m] ...and, for each, the index into `pivots` of its column.
    target: object  # [u] the positions each outer-product update subtracts from...
    left: object  # [u] ...the two scaled entries whose product it subtracts.
    right: object


class Symbolic(NamedTuple):
    """The bound structure of one SPD pattern (module docstring). The factor's entries are stored
    column by column in the permuted order: for each column j, its diagonal, then its below-diagonal
    rows ascending."""

    size: int
    order: object  # [n] int64: the elimination order (row i of the permuted system is order[i]).
    rank: object  # [n] int64: the inverse permutation.
    column_start: object  # [n + 1] int64: column j's entries are column_start[j]:column_start[j+1].
    row: object  # [nnz] int64: each entry's permuted row.
    column: object  # [nnz] int64: each entry's permuted column.
    parent: object  # [n] int64: the elimination tree (-1 at a root).
    levels: tuple  # (Level, ...) in elimination order.
    source: object  # [p] int64: for each nonzero of the lower pattern, its factor position...
    source_row: object  # [p] int64: ...and its original (unpermuted) row and column.
    source_column: object


def minimum_degree(pattern):
    """A minimum-degree elimination order of a symmetric pattern (bool [n, n]): repeatedly the
    node of least current degree in the elimination graph, ties by the least original degree and
    then the smallest index (so an arrowhead's hub, tied at the end with its last leaf, goes last:
    two levels); its neighbours then form a clique. Deterministic, NumPy and the standard library
    only."""
    pattern = np.asarray(pattern, dtype=bool)
    n = pattern.shape[0]
    adjacency = [set(np.flatnonzero(pattern[i]).tolist()) - {i} for i in range(n)]
    original = np.asarray([len(a) for a in adjacency], dtype=np.int64)
    alive = np.ones(n, dtype=bool)
    order = []
    for _ in range(n):
        candidates = np.flatnonzero(alive)
        degrees = np.fromiter((len(adjacency[i]) for i in candidates), dtype=np.int64)
        node = int(candidates[np.lexsort((candidates, original[candidates], degrees))[0]])
        neighbours = adjacency[node]
        for a in neighbours:
            adjacency[a].discard(node)
            adjacency[a] |= neighbours - {a}
        adjacency[node] = set()
        alive[node] = False
        order.append(node)
    return np.asarray(order, dtype=np.int64)


def bind(pattern, order=None):
    """The `Symbolic` of an SPD pattern (bool [n, n], symmetric, true diagonal), in `order`
    (default: minimum_degree)."""
    pattern = np.asarray(pattern, dtype=bool)
    n = pattern.shape[0]
    if pattern.shape != (n, n) or not np.array_equal(pattern, pattern.T):
        raise ValueError("A sparse Cholesky pattern must be a symmetric square matrix")
    if not pattern.diagonal().all():
        raise ValueError("A sparse Cholesky pattern must hold its whole diagonal")
    order = minimum_degree(pattern) if order is None else np.asarray(order, dtype=np.int64)
    if sorted(order.tolist()) != list(range(n)):
        raise ValueError("The elimination order must be a permutation")
    rank = np.empty(n, dtype=np.int64)
    rank[order] = np.arange(n)
    permuted = pattern[np.ix_(order, order)]
    # Symbolic factorisation: column j's rows are its own below-diagonal rows and those of every
    # child's column above j (the elimination tree's union rule).
    rows = [set((np.flatnonzero(permuted[j + 1:, j]) + j + 1).tolist()) for j in range(n)]
    parent = np.full(n, -1, dtype=np.int64)
    for j in range(n):
        if rows[j]:
            p = min(rows[j])
            parent[j] = p
            rows[p] |= rows[j] - {p}
    rows = [np.asarray(sorted(r), dtype=np.int64) for r in rows]
    column_start = np.zeros(n + 1, dtype=np.int64)
    column_start[1:] = np.cumsum([1 + r.size for r in rows])
    entry_row = np.concatenate([np.r_[j, r] for j, r in enumerate(rows)]).astype(np.int64)
    entry_column = np.repeat(np.arange(n, dtype=np.int64), np.diff(column_start))
    position = {(int(i), int(j)): k for k, (i, j) in enumerate(zip(entry_row, entry_column))}
    # Levels: a column's level is one above its highest child's (leaves at 0).
    level = np.zeros(n, dtype=np.int64)
    for j in range(n):
        if parent[j] >= 0:
            level[parent[j]] = max(level[parent[j]], level[j] + 1)
    levels = []
    for value in range(int(level.max(initial=-1)) + 1):
        columns = np.flatnonzero(level == value)
        pivots = column_start[columns]
        below, below_pivot, target, left, right = [], [], [], [], []
        for slot, j in enumerate(columns):
            r = rows[j]
            first = int(column_start[j]) + 1
            below += range(first, first + r.size)
            below_pivot += [slot] * r.size
            for a in range(r.size):  # Each pair (i >= k) of the column's rows: L_ik -= L_ij L_kj.
                for b in range(a + 1):
                    target.append(position[(int(r[a]), int(r[b]))])
                    left.append(first + a)
                    right.append(first + b)
        levels.append(
            Level(*(np.asarray(x, dtype=np.int64) for x in
                    (pivots, below, below_pivot, target, left, right)))
        )
    lower = np.argwhere(np.tril(pattern))  # Original (row, column) with row >= column.
    source = np.asarray(
        [position[tuple(sorted((int(rank[i]), int(rank[j])), reverse=True))] for i, j in lower],
        dtype=np.int64,
    )
    return Symbolic(
        size=n,
        order=order,
        rank=rank,
        column_start=column_start,
        row=entry_row,
        column=entry_column,
        parent=parent,
        levels=tuple(levels),
        source=source,
        source_row=lower[:, 0].astype(np.int64),
        source_column=lower[:, 1].astype(np.int64),
    )


def _scatter_add(values, positions, updates, *, xp):
    if xp is np:
        out = np.array(values, copy=True)
        np.add.at(out, positions, updates)
        return out
    return values.at[positions].add(updates)


def _set(values, positions, updates, *, xp):
    if xp is np:
        out = np.array(values, copy=True)
        out[positions] = updates
        return out
    return values.at[positions].set(updates)


def assemble(matrix, symbolic, *, xp):
    """The factor's value array holding the lower triangle of `matrix` ([n, n], the system in its
    original order, structurally within the bound pattern) at its pattern's positions, zero at the
    fill."""
    s = symbolic
    entries = matrix[s.source_row, s.source_column]
    return _set(xp.zeros(s.row.shape[0], dtype=entries.dtype), s.source, entries, xp=xp)


def factor(values, symbolic, *, xp):
    """The numeric factor (module docstring) of an assembled value array: the factor's entries in
    the symbolic's storage, column by column."""
    for lv in symbolic.levels:
        pivot = xp.sqrt(values[lv.pivots])
        values = _set(values, lv.pivots, pivot, xp=xp)
        if lv.below.size:
            values = _set(values, lv.below, values[lv.below] / pivot[lv.below_pivot], xp=xp)
        if lv.target.size:
            values = _scatter_add(values, lv.target, -(values[lv.left] * values[lv.right]), xp=xp)
    return values


def solve(factor_values, rhs, symbolic, *, xp):
    """x with A x = rhs for the factored A (rhs [n] in the original order)."""
    s = symbolic
    y = rhs[s.order]
    for lv in s.levels:  # Forward: L y = b, column by column within each level.
        columns = s.column[lv.pivots]
        y = _set(y, columns, y[columns] / factor_values[lv.pivots], xp=xp)
        if lv.below.size:
            rows = s.row[lv.below]
            y = _scatter_add(y, rows, -(factor_values[lv.below] * y[columns[lv.below_pivot]]),
                             xp=xp)
    for lv in reversed(s.levels):  # Back: L^T x = y, each column from its rows already solved.
        columns = s.column[lv.pivots]
        if lv.below.size:
            rows = s.row[lv.below]
            products = factor_values[lv.below] * y[rows]
            sums = _scatter_add(xp.zeros(columns.shape[0], dtype=y.dtype), lv.below_pivot,
                                products, xp=xp)
            y = _set(y, columns, (y[columns] - sums) / factor_values[lv.pivots], xp=xp)
        else:
            y = _set(y, columns, y[columns] / factor_values[lv.pivots], xp=xp)
    return y[s.rank]
