"""The decimal propagator of a linear flow world, and an independent second one.

State vector of one species (LAWS section 4): one constant row per inlet (its level x_I, in mM), then the
nodes' amounts, then the collectors' (fmol). `y' = G y`, with G constant between switches.

- Method 1, `expm`: scaling and squaring as LAWS section 4 states it.
- Method 2, `uniformized`: Jensen's method, e^(Gt) v = e^(-qt) sum_k (qt)^k/k! (I + G/q)^k v. It uses no
  squaring and no negative number (I + G/q is non-negative for a compartment network), so its errors are
  unrelated to method 1's.
"""

from decimal import Decimal

from .arith import ONE, TWO, ZERO
from . import arith


# ---- matrices ------------------------------------------------------------------------------------------

def identity(n):
    return [[ONE if i == j else ZERO for j in range(n)] for i in range(n)]


def matmul(a, b):
    n, m, p = len(a), len(b), len(b[0])
    out = []
    for i in range(n):
        row_a = a[i]
        row = [ZERO] * p
        for k in range(m):
            value = row_a[k]
            if value == 0:
                continue
            row_b = b[k]
            for j in range(p):
                if row_b[j] != 0:
                    row[j] += value * row_b[j]
        out.append(row)
    return out


def matvec(a, v):
    return [sum((x * y for x, y in zip(row, v) if x != 0 and y != 0), ZERO) for row in a]


def scaled(a, factor):
    return [[x * factor for x in row] for row in a]


def add(a, b):
    return [[x + y for x, y in zip(ra, rb)] for ra, rb in zip(a, b)]


def largest(a):
    return max((abs(x) for row in a for x in row), default=ZERO)


def column_norm(a):
    """The 1-norm: the largest column sum of absolute values."""
    if not a:
        return ZERO
    return max(sum((abs(a[i][j]) for i in range(len(a))), ZERO) for j in range(len(a[0])))


def expm(g, t):
    """e^(gt) by scaling and squaring (LAWS section 4).

    t is halved until the 1-norm of g t is at most 2^-8; the Taylor series is summed until every entry's term is below
    10^-(working digits) of that entry's own sum (which is far below the 1e-58 of the sum that LAWS asks for, and keeps the
    relative accuracy of small entries); then squared back.
    """
    n = len(g)
    a = scaled(g, t)
    norm = column_norm(a)
    halvings = 0
    limit = TWO ** -8
    while norm > limit:
        norm /= 2
        halvings += 1
    if halvings:
        a = scaled(a, TWO ** -halvings)
    digits = arith.decimal.getcontext().prec
    tiny = Decimal(10) ** -(digits + 2)
    total = identity(n)
    term = identity(n)
    k = 0
    while True:
        k += 1
        term = scaled(matmul(term, a), ONE / k)
        total = add(total, term)
        # a path from one node to another has at most n - 1 links, so every entry that is not zero has appeared by k = n
        if k >= n and all(abs(x) <= tiny * abs(y) for rx, ry in zip(term, total) for x, y in zip(rx, ry)):
            break
        if k > 1000:
            raise ArithmeticError("the Taylor series did not end")
    for _ in range(halvings):
        total = matmul(total, total)
    return total


def uniformized(g, t, v):
    """e^(gt) v by uniformization, for t >= 0 and a generator with non-negative off-diagonal entries."""
    n = len(g)
    if t == 0:
        return list(v)
    q = max((-g[i][i] for i in range(n)), default=ZERO)
    if q <= 0:
        # no outflow anywhere: the nodes are constant and only inlet columns act; a Taylor series ends there
        q = ONE
    jump = [[(ONE if i == j else ZERO) + g[i][j] / q for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(n):
            if jump[i][j] < 0:
                raise ValueError("uniformization needs non-negative jumps")
    qt = q * t
    digits = arith.decimal.getcontext().prec
    weight = (-qt).exp()
    vector = list(v)
    total = [weight * x for x in vector]
    k = 0
    tiny = Decimal(10) ** -(digits + 4)
    while True:
        k += 1
        weight = weight * qt / k
        vector = matvec(jump, vector)
        piece = [weight * x for x in vector]
        total = [s + p for s, p in zip(total, piece)]
        if k > qt and all(abs(p) <= tiny * abs(s) for p, s in zip(piece, total)):
            return total


# ---- generators -----------------------------------------------------------------------------------------

class Layout:
    """The order of the state vector: inlets, nodes, collectors."""

    def __init__(self, world):
        self.inlets = sorted(world.inlets)
        self.nodes = list(world.nodes)
        self.collectors = list(world.collectors)
        self.names = self.inlets + self.nodes + self.collectors
        self.index = {name: i for i, name in enumerate(self.names)}
        self.size = len(self.names)


def generator(world, species, time, layout=None, with_flow=True, with_faces=True, rate_factor=ONE):
    """G in force from `time`. Columns: an inlet's is its supply (pL/s); a node's sums to zero."""
    layout = layout or Layout(world)
    g = [[ZERO] * layout.size for _ in range(layout.size)]
    if with_flow:
        for source, target, rate in world.link_rates(time):
            if rate == 0:
                continue
            q = rate * rate_factor
            i, j = layout.index[target], layout.index[source]
            if source in world.inlets:
                g[i][j] += q
            else:
                per_volume = q / world.volumes[source]
                g[i][j] += per_volume
                g[j][j] -= per_volume
    if with_faces:
        for a, b, table in world.faces:
            permeance = table.get(species, ZERO)
            if permeance == 0:
                continue
            i, j = layout.index[a], layout.index[b]
            out_a = permeance / world.volumes[a]
            out_b = permeance / world.volumes[b]
            g[i][i] -= out_a
            g[j][i] += out_a
            g[j][j] -= out_b
            g[i][j] += out_b
    return g


def start_vector(world, species, layout, amounts=None):
    """The node amounts at t = 0 (inlet rows are set per segment); `species` may be "volume"."""
    y = [ZERO] * layout.size
    if amounts is None:
        amounts = world.volumes if species == "volume" else world.start[species]
    for node in layout.nodes:
        y[layout.index[node]] = amounts.get(node, ZERO)
    return y


def with_inlets(world, species, time, y, layout, inlet_on=True):
    """`y` with the inlet rows of the segment that starts at `time`."""
    y = list(y)
    for inlet in layout.inlets:
        if not inlet_on:
            level = ZERO
        elif species == "volume":
            level = ONE
        else:
            level = world.inlet_level(inlet, species, time)
        y[layout.index[inlet]] = level
    return y


def segments(world, start, stop):
    """[(a, b)] of the constant pieces from `start` to `stop`."""
    edges = [start] + [t for t in world.switch_times() if start < t < stop] + [stop]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b > a]


def solve(world, species, time, amounts=None, inlet_on=True, method="expm", rate_factor=ONE,
          with_faces=True, with_flow=True):
    """The state of `species` at `time`, piece by piece.

    `amounts` replaces the declared start (a label's own start, LAWS section 7); `inlet_on=False` makes the
    inlets carry none of it (an inlet's liquid belongs to the base label).
    """
    layout = Layout(world)
    y = start_vector(world, species, layout, amounts)
    for a, b in segments(world, ZERO, time):
        y = with_inlets(world, species, a, y, layout, inlet_on)
        g = generator(world, species, a, layout, with_flow=with_flow,
                      with_faces=with_faces and species != "volume", rate_factor=rate_factor)
        if method == "expm":
            y = matvec(expm(g, b - a), y)
        elif method == "uniformized":
            y = uniformized(g, b - a, y)
        else:
            raise ValueError(method)
    return y


def supplied(world, species, time):
    """x delivered by the inlets from t = 0: the sum of Q x dt over the links that leave an inlet."""
    total = ZERO
    for a, b in segments(world, ZERO, time):
        for source, _, rate in world.link_rates(a):
            if source in world.inlets:
                level = ONE if species == "volume" else world.inlet_level(source, species, a)
                total += rate * level * (b - a)
    return total


def collector_volume(world, time):
    """V_K: the integral of the rates of the links that enter the collector."""
    total = ZERO
    for a, b in segments(world, ZERO, time):
        for _, target, rate in world.link_rates(a):
            if target in world.collectors:
                total += rate * (b - a)
    return total
