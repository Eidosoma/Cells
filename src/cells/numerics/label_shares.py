"""Neutral arrival-time labels' shares over one applied move (FR-42, option A, D289).

docs/NEUTRAL_LABELS_DESIGN.md. Each labelled row at each node holds shares s [label], each in
[0, 1] and summing to 1. Label 0 is the species' base, which holds unlabelled material. The row's
amount n is the engine's own: no law reads a share, so a label never changes the dynamics or the
energy. Shares are not stored amounts, so a share may be exactly 0 while the row stays positive,
and a cohort starts at exactly zero.

**One application's report** (operators/contract.py: one interface for every mover): out, the
one-way amount the row lost at the node; into [label], the one-way amount it gained, by label (new
material at the label the step's window names, material that keeps its labels at theirs).

**The update** (advance). Over one application the shares follow the exact solution for a constant
per-molecule loss rate k and constant arrival rates a_l: n(t) = n0 e^(-k t) + A (1 - e^(-k t)) / k,
with A = sum_l a_l. Over the application (length h, u = k h, I = A h) this is

    n1 = n0 e^(-u) + I phi(u),   phi(u) = (1 - e^(-u)) / u   (phi(0) = 1).

u >= 0 is solved from the engine's own n0, n1 and I (survival_exponent: bisection with a fixed
iteration count, so no data-dependent loop is traced). Then each label's material is
x_l = n0 s_l e^(-u) + into_l phi(u), and the shares are x over its own sum, so they sum to 1 at
rounding.
- **Non-negative for any step.** Every term is non-negative, whatever the step and the loss law.
- **No arrivals:** the shares are kept exactly, bit for bit. Every molecule of a well-mixed
  population has one per-molecule loss rate, so losses never change the shares, whatever the loss
  law (FR-42's reference case, dN/dt = -N^2, is exact).
- **A zero share stays zero** exactly until its label receives arrivals: a new cohort starts at
  zero.
- **Exact** for a constant per-molecule loss rate and constant arrival rates within the
  application (first-order clearance with constant production, for example).
- **Otherwise second order.** With k(t) and a(t) varying within the application, the new
  material it attributes exceeds the exact amount by (a(0) k'(0) - a'(0) k(0)) h^3 / 12 + O(h^4),
  and the old material falls short by as much (old material's e^(-u) against e^(-integral of k)):
  third order per application, so second order over a run, as Strang splitting is. It vanishes
  when a and k vary in proportion. The totals are the engine's and carry no such error.
- **The closure** (closure_residual): n1 - (n0 + sum(into) - out) is the report's rounding where
  every mover of the row reported. out enters nothing else.

**A liquid exchange** (exchange; FR-44) is an event, not a rate. A well-mixed sample carries the
node's shares away, and a buffer brings unlabelled material, which joins the base. So each label's
material is the kept part times its share, plus the supply at the base: exact in the amounts it
is given, with no survival exponent. The continuous update above would not be exact here (it
spreads arrivals over an application).

**Checking against the run's own per-molecule loss rate** (FR-42's check 2): a cohort's survivors
are the arrivals of its window's steps, each carried forward by exp(-integral of k dt) to the
observation, with k = (one-way loss) / n per step from the run's records. Where k is constant
within each step (first-order clearance at a scheduled rate), that calculation and the update agree
at rounding; elsewhere they agree to the update's second order.
"""

import math

import jax
import jax.numpy as jnp

from cells.numerics.species_sums import entity_sum

# Bisection halvings of u's bracket [0, hi] (hi at most a few hundred in double precision): 2^-96
# of it is below double precision's resolution of u.
ITERATIONS = 96
SERIES_BELOW = 1e-8  # phi(u) = 1 - u/2 + u^2/6 below it (relative error below 1e-24).
SHARE_ULPS = 128  # The domain's rounding allowance on a row's sum of shares (up to 64 labels).
EPS = math.ulp(1.0)


def phi(u, *, xp=jnp):
    """(1 - e^(-u)) / u for u >= 0, with phi(0) = 1, accurate near 0."""
    small = u < SERIES_BELOW
    safe = xp.where(small, 1.0, u)
    return xp.where(small, 1.0 - u / 2 + u * u / 6, -xp.expm1(-safe) / safe)


def survival_exponent(n0, n1, arrived, *, xp=jnp, iterations=ITERATIONS):
    """u >= 0 with n1 = n0 e^(-u) + arrived phi(u), elementwise (module docstring).

    The right-hand side falls strictly from n0 + arrived at u = 0 towards 0, so where
    0 < n1 < n0 + arrived the root is unique, and the bracket [0, hi] holds it: hi makes
    n0 e^(-hi) < n1 / 2 and arrived phi(hi) < arrived / hi < n1 / 2. Elsewhere (no loss, or an
    empty row) u = 0."""
    lost = (n1 > 0) & (n1 < n0 + arrived)
    safe = xp.where(lost, n1, 1.0)
    hi = (
        xp.log(xp.maximum(2.0 * xp.where(lost, n0, 0.0) / safe, 1.0))
        + 2.0 * xp.where(lost, arrived, 0.0) / safe
        + 1.0
    )
    lo = xp.zeros_like(hi)

    def halve(_, bracket):
        a, b = bracket
        mid = 0.5 * (a + b)
        above = n0 * xp.exp(-mid) + arrived * phi(mid, xp=xp) > n1
        return xp.where(above, mid, a), xp.where(above, b, mid)

    if xp is jnp:
        lo, hi = jax.lax.fori_loop(0, iterations, halve, (lo, hi))
    else:
        for i in range(iterations):
            lo, hi = halve(i, (lo, hi))
    return xp.where(lost, 0.5 * (lo + hi), 0.0)


def advance(shares, n0, n1, into, present, *, xp=jnp):
    """The shares after one application (module docstring).

    shares [m, label, node] at its start; n0 and n1 [m, node] the rows' amounts at its start and
    end (the engine's); into [m, label, node] the one-way gains by label; present [m, label] the
    declared labels, or [m, label, node] per node (sites of several species). Where nothing
    arrived the start's shares are kept bit for bit."""
    declared = present if present.ndim == 3 else present[:, :, None]
    gained = xp.where(declared, into, 0.0)
    arrived = entity_sum(gained, axis=1, xp=xp)
    u = survival_exponent(n0, n1, arrived, xp=xp)
    x = (n0 * xp.exp(-u))[:, None, :] * shares + gained * phi(u, xp=xp)[:, None, :]
    x = xp.where(declared, x, 0.0)
    total = entity_sum(x, axis=1, xp=xp)
    moved = (arrived > 0) & (total > 0)
    out = x / xp.where(moved, total, 1.0)[:, None, :]
    return xp.where(moved[:, None, :], out, shares)


def _scatter_nodes(base, index, values, *, xp):
    """base [..., node] with values [..., entity] added at the nodes `index` [entity] names."""
    if xp is jnp:
        return base.at[..., index].add(values)
    out = xp.array(base, copy=True)
    xp.add.at(xp.moveaxis(out, -1, 0), xp.asarray(index), xp.moveaxis(values, -1, 0))
    return out


def carried(shares, transfers, *, xp=jnp):
    """(into [m, label, node], out [m, node]): each transfer (amount [m, entity], source [entity],
    destination [entity]) arriving at its destination apportioned by its source's shares, and
    leaving its source. The node axis is the shares' (cells, then outside nodes)."""
    m, width, nodes = shares.shape
    into, out = xp.zeros((m, width, nodes)), xp.zeros((m, nodes))
    for amount, source, destination in transfers:
        into = _scatter_nodes(into, destination, amount[:, None, :] * shares[:, :, source], xp=xp)
        out = _scatter_nodes(out, source, amount, xp=xp)
    return into, out


def advance_transfers(shares, n0, n1, transfers, present, held, *, xp=jnp, into=None):
    """The shares after a step of transport between nodes (FR-42's stage 2): each node advanced by
    advance(), its arrivals carrying their sources' shares, first at the step's start
    (predictor), then at the mean of start and predicted end (corrector): second order in the
    step, non-negative, and exact (at rounding) where no source's shares change. held [node]:
    nodes whose shares are kept (held baths). into [m, label, node]: new material arriving
    besides the transfers, by label (D296's sources and pools), or None."""
    fixed = 0.0 if into is None else into
    arriving, _ = carried(shares, transfers, xp=xp)
    predicted = advance(shares, n0, n1, arriving + fixed, present, xp=xp)
    arriving, _ = carried(0.5 * (shares + predicted), transfers, xp=xp)
    new = advance(shares, n0, n1, arriving + fixed, present, xp=xp)
    return xp.where(held[None, None, :], shares, new)


def exchange(shares, n0, removed, supplied, present, *, xp=jnp):
    """The shares after a liquid exchange at each node (FR-44): a well-mixed sample takes removed
    [m, node] of the row away, carrying the node's shares, and a buffer brings supplied [m, node]
    of unlabelled material, which joins the base (label 0).

    shares [m, label, node] are those just before the exchange, and n0 [m, node] the engine's
    amounts then. present [m, label] gives the declared labels. Each label's material after is
    (n0 - removed) s_k + supplied [k = 0], and the shares are that over its own sum, so they sum
    to 1 at rounding whatever the engine's new amount rounds to. The map is exact in the amounts
    it is given:
    - n' s_k' = (1 - f) n0 s_k for every other label;
    - a zero share stays exactly 0, and a base-only row stays exactly (1, 0, ...);
    - with removed = fl(1.0 * n0), a whole exchange, every other share is exactly 0;
    - where nothing is exchanged (removed = supplied = 0) the shares are kept bit for bit.
    The node axis is the caller's, so the same map serves any node axis."""
    declared = present if present.ndim == 3 else present[:, :, None]
    base = (xp.arange(shares.shape[1]) == 0)[None, :, None]
    kept = (n0 - removed)[:, None, :] * shares
    x = xp.where(declared, kept + xp.where(base, supplied[:, None, :], 0.0), 0.0)
    total = entity_sum(x, axis=1, xp=xp)
    moved = ((removed > 0) | (supplied > 0)) & (total > 0)
    out = x / xp.where(moved, total, 1.0)[:, None, :]
    return xp.where(moved[:, None, :], out, shares)


def closure_residual(n0, n1, into, out, *, xp=jnp):
    """|n1 - (n0 + sum(into) - out)| [m, node]: the report's closure, rounding where every mover of
    the row reported."""
    return xp.abs(n1 - (n0 + entity_sum(into, axis=1, xp=xp) - out))


def domain_valid(shares, present, *, xp=jnp):
    """Shares finite, each in [0, 1], 0 at every undeclared label (present [m, label] or
    [m, label, node]), and each row's summing to 1 within SHARE_ULPS ulps (zero shares
    allowed)."""
    declared = present if present.ndim == 3 else present[:, :, None]
    inside = (shares >= 0) & (shares <= 1)
    ok = xp.all(xp.isfinite(shares))
    ok &= xp.all(xp.where(declared, inside, shares == 0))
    return ok & xp.all(xp.abs(entity_sum(shares, axis=1, xp=xp) - 1.0) <= SHARE_ULPS * EPS)
