"""Passive cohort records of integer units: the identity map's rule, the exact update at an event
and the half-open label rule (FR-52; docs/PASSIVE_COHORT_DESIGN.md §2.3).

A cohort names one site, its identity class (the unit states that are forms of one unit) and a
window [start, end). Its record E [state, label] holds, for each state of the class, the expected
number of units whose identity began at t = 0 (`initial`), or at an event time before, inside or
after the window, conditional on the recorded events. Units of a state are exchangeable under the
population's law (a channel's propensity counts ordered tuples of distinct units), so an event
consumes a uniformly random subset of each state's units, independently across states, and by
linearity the update below is the exact conditional expectation. It is an expectation, never a
realization: it holds no variance and draws nothing.

**The identity map.** Over the class, r_a and p_b are a channel's reactants and products per state
(no class state is on both sides: the declaration refuses it), R and P their sums. min(R, P)
identities go on, through a table m_ab of whole numbers, the identities going from consumed state a
to produced state b, with at most r_a out of a and at most p_b into b. A channel's legal table is
unique, and resolves by rule, exactly when
- R = 0 or P = 0: the empty table (an assembly into the class makes new units, a disassembly out of
  it loses them);
- the consumed side holds one class state and R >= P: m_ab = p_b; or
- the produced side holds one class state and P >= R: m_ab = r_a.
Every other channel has two or more legal tables, so its table is declared. In a split one half
keeps the identity and the others are new (the user, D375).

**The update at an event** (n the counts before it, λ the label of its time):
1. s_a = E_a / n_a for each consumed state a, read before the loss (n_a >= r_a >= 1 there);
2. E_a <- E_a (n_a - r_a) / n_a, formed as fl(fl(E (n - r)) / n);
3. E_b <- E_b + m_ab s_a, one carry at a time in state order;
4. E_b,λ <- E_b,λ + p_b - Σ_a m_ab, the new units.
Nothing is subtracted, so every value stays finite and >= 0 and an emptied state holds an exact 0.
Each state's labels sum to its count. The binary64 record meets the exact one within
rounding_bound (§2.3: 8 (K + 1) u N).

One code for NumPy and jax.numpy (xp). It reads only its arguments.
"""

from cells.numerics.species_sums import entity_sum

LABELS = ("initial", "before", "inside", "after")
INITIAL, BEFORE, INSIDE, AFTER = range(len(LABELS))
UNIT_ROUNDOFF = 2.0**-53


def unique_table(r, p):
    """{(a, b): m} of a channel whose legal table is unique (empty where nothing goes on), else
    None. r, p: the channel's class reactants and products per state, whole numbers whose
    supports are disjoint (module docstring)."""
    consumed = [a for a, x in enumerate(r) if x]
    produced = [b for b, x in enumerate(p) if x]
    total_r = sum([r[a] for a in consumed])
    total_p = sum([p[b] for b in produced])
    if total_r == 0 or total_p == 0:
        return {}
    if len(consumed) == 1 and total_r >= total_p:
        return {(consumed[0], b): p[b] for b in produced}
    if len(produced) == 1 and total_p >= total_r:
        return {(a, produced[0]): r[a] for a in consumed}
    return None


def label_of(time, start, end, *, xp):
    """The label of an event at `time` against the half-open window [start, end): BEFORE where
    time < start, INSIDE where start <= time < end, AFTER where time >= end."""
    return xp.where(time < start, BEFORE, xp.where(time < end, INSIDE, AFTER))


def advance(units, counts, reactants, products, table, label, *, xp):
    """The record after one event (module docstring), for any leading axes:
    - units [..., S, L]: E before the event, S states and the L labels;
    - counts [..., S]: the counts before the event (int);
    - reactants, products [..., S]: the channel's class stoichiometry, 0 outside the class (int);
    - table [..., S, S]: m from consumed state a (axis -2) to produced state b (axis -1) (int);
    - label [...]: the label of the event's time (BEFORE, INSIDE or AFTER)."""
    n = counts.astype(units.dtype)
    taken = reactants > 0
    safe = xp.where(taken, n, 1.0)  # A consumed state holds n >= r >= 1; elsewhere unread.
    share = units / safe[..., None]
    lost = units * (n - reactants)[..., None] / safe[..., None]
    kept = xp.where(taken[..., None], lost, units)
    columns = []
    for b in range(units.shape[-2]):
        column = kept[..., b, :]
        for a in range(units.shape[-2]):
            column = column + table[..., a, b][..., None] * share[..., a, :]
        columns.append(column)
    carried = xp.stack(columns, axis=-2)
    arrived = products - entity_sum(table, axis=-2, xp=xp)  # p_b - Σ_a m_ab, the new units.
    hot = xp.arange(units.shape[-1]) == label[..., None]
    return carried + xp.where(hot[..., None, :], arrived[..., :, None], 0)


def rounding_bound(events, most):
    """8 (K + 1) u N (§2.3): how far a binary64 record's entry, and each state's labels summed in
    binary64, may lie from the exact values after K events, at a site holding at most N units of
    the class (its subunits over the class's smallest weight)."""
    return 8.0 * (events + 1) * UNIT_ROUNDOFF * most
