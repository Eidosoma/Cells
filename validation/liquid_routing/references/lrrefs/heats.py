"""The holders' heats and the face's, by two quadratures whose integrands are evaluated in different ways.

- `by_tanh_sinh`: the double-exponential rule; the state from closed forms (the chain of LAWS section 4, or the
  two-node linear system of LAWS section 8 by its eigenvalues).
- `by_gauss`: graded Gauss-Legendre pieces; the state from the Taylor series of y' = G y, continued from one
  output to the next. It uses neither a closed form nor `expm`.
"""

from decimal import Decimal

from . import propagator as pr
from .arith import ONE, QUAD_DIGITS, TWO, ZERO, precision
from .flow import face_rate, holder_rates
from .laws import Chain
from .quadrature import GaussRule, TanhSinh, gauss_points

FACE = "face"

_cache = {}


def tanh_sinh(steps_per_unit, digits=QUAD_DIGITS, cutoff=62):
    key = ("ts", steps_per_unit, digits, cutoff)
    if key not in _cache:
        _cache[key] = TanhSinh(steps_per_unit, digits, cutoff)
    return _cache[key]


def gauss(n=40, digits=QUAD_DIGITS):
    key = ("gauss", n, digits)
    if key not in _cache:
        _cache[key] = GaussRule(n, digits)
    return _cache[key]


def grading_depth(world):
    """How many halvings reach below the shortest time scale near t = 0: the smallest declared level over the largest.

    A holder at a trace eps fed at level c has r singular near t = -eps V/(Q c): the pieces must reach below it.
    """
    levels = world.declared_concentrations()
    ratio = max(levels) / min(levels)
    depth = 6
    while TWO ** depth < ratio * 64:
        depth += 1
    return depth


# ---- states from closed forms -----------------------------------------------------------------------------

class ChainState:
    """The concentrations of a chain inlet -> first -> second -> collector, with an optional face between them."""

    def __init__(self, world, species):
        links = world.link_rates(ZERO)
        if len(links) != 3 or world.switch_times():
            raise ValueError("not a constant chain")
        (inlet, first, q1), (first2, second, q2), (second2, collector, q3) = links
        if not (inlet in world.inlets and first == first2 and second == second2 and q1 == q2 == q3):
            raise ValueError("not a chain")
        self.names = (inlet, first, second, collector)
        self.q = q1
        self.x = world.inlet_level(inlet, species, ZERO)
        self.v1, self.v2 = world.volumes[first], world.volumes[second]
        self.n1 = world.start[species].get(first, ZERO)
        self.n2 = world.start[species].get(second, ZERO)
        self.permeance = ZERO
        for a, b, table in world.faces:
            if {a, b} != {first, second}:
                raise ValueError("a face elsewhere")
            self.permeance += table.get(species, ZERO)
        self.chain = Chain(self.n1, self.n2, self.v1, self.v2, self.q, self.x)
        if self.permeance != 0:
            self._eigen()

    def _eigen(self):
        """c' = M c + s, M = [[-(Q+P)/V1, P/V1], [(Q+P)/V2, -(Q+P)/V2]], s = (Q x/V1, 0): both rates are real."""
        q, p = self.q, self.permeance
        self.m = [[-(q + p) / self.v1, p / self.v1], [(q + p) / self.v2, -(q + p) / self.v2]]
        trace = self.m[0][0] + self.m[1][1]
        determinant = self.m[0][0] * self.m[1][1] - self.m[0][1] * self.m[1][0]
        root = (trace * trace - 4 * determinant).sqrt()
        self.fast, self.slow = (trace - root) / 2, (trace + root) / 2
        if q == 0:
            # the slow rate is exactly 0: the two wells of LAWS section 1
            self.slow = ZERO
            self.fast = trace

    def levels(self, t):
        """{name: concentration} at t > 0."""
        inlet, first, second, collector = self.names
        if self.permeance == 0:
            n1, n2, collected = self.chain.state(t)
            c1, c2 = n1 / self.v1, n2 / self.v2
        else:
            # at Q = 0 the particular solution is the common level; otherwise it is x in both
            rest = self.x if self.q != 0 else (self.n1 + self.n2) / (self.v1 + self.v2)
            u = [self.n1 / self.v1 - rest, self.n2 / self.v2 - rest]
            out = [ZERO, ZERO]
            for rate, other in ((self.fast, self.slow), (self.slow, self.fast)):
                factor = (rate * t).exp() / (rate - other)
                for i in range(2):
                    for j in range(2):
                        entry = self.m[i][j] - (other if i == j else ZERO)
                        out[i] += factor * entry * u[j]
            c1, c2 = rest + out[0], rest + out[1]
            n1, n2 = c1 * self.v1, c2 * self.v2
            collected = self.n1 + self.n2 + self.q * self.x * t - n1 - n2
        levels = {inlet: self.x, first: c1, second: c2}
        if self.q != 0:
            levels[collector] = collected / (self.q * t)
        else:
            levels[collector] = ZERO
        return levels

    def amounts(self, t):
        levels = self.levels(t)
        _, first, second, collector = self.names
        return {first: levels[first] * self.v1, second: levels[second] * self.v2,
                collector: levels[collector] * self.q * t}


def by_tanh_sinh(world, outputs, fine_first=160, fine_rest=24, state=ChainState, digits=QUAD_DIGITS, cutoff=62):
    """({holder or "face": [heat at each output]}, {same: largest |fine - half grid|}).

    The half grid's error is the square root of the fine grid's or so: the spread is a diagnosis of convergence, not an
    accuracy. The accuracy is the agreement with `by_gauss`.
    """
    with precision(digits):
        states = {x: state(world, x) for x in world.species}
        rates = world.link_rates(ZERO)
        holders = world.flow_nodes + world.collectors
        totals = {name: ZERO for name in holders + [FACE]}
        coarse_totals = dict(totals)
        values = {name: [] for name in totals}
        spread = {name: ZERO for name in totals}
        left = ZERO
        for right in outputs:
            rule = tanh_sinh(fine_first if left == 0 else fine_rest, digits, cutoff)
            for s, weight, on_half_grid in rule.points(ZERO, right - left):
                t = left + s
                point = {name: ZERO for name in totals}
                for x in world.species:
                    levels = states[x].levels(t)
                    for name, rate in holder_rates(world, rates, levels).items():
                        point[name] += rate
                    point[FACE] += face_rate(world, x, levels)
                for name, rate in point.items():
                    totals[name] += weight * rate
                    if on_half_grid:
                        coarse_totals[name] += 2 * weight * rate
            for name in totals:
                values[name].append(totals[name])
                spread[name] = max(spread[name], abs(totals[name] - coarse_totals[name]))
            left = right
    return values, spread


# ---- states from Taylor series -------------------------------------------------------------------------------

class TaylorTrajectory:
    """One species on [t0, t0 + length] as the Taylor series of y' = G y about t0 (entire)."""

    def __init__(self, g, y, length):
        self.coefficients = [list(y)]
        digits = pr.arith.decimal.getcontext().prec
        tiny = Decimal(10) ** -(digits + 2)
        power = ONE
        k = 0
        scale = max((abs(v) for v in y), default=ONE)
        while True:
            k += 1
            power *= length
            term = [v / k for v in pr.matvec(g, self.coefficients[-1])]
            self.coefficients.append(term)
            # an entry is done when its term is far below its own sum; the smallest entries decide
            if max(abs(v) for v in term) * power <= tiny * tiny * scale or k > 2000:
                break
        self.coefficients.reverse()

    def at(self, s):
        out = list(self.coefficients[0])
        for row in self.coefficients[1:]:
            out = [a * s + b for a, b in zip(out, row)]
        return out


def doubling_pieces(a, b):
    """[a, b] cut so that no piece more than doubles the distance from t = 0, where the integrands may be singular, and
    each piece halved (after an inlet's switch the nearest singularity is not at t = 0 but nearer the piece).
    """
    edges = [a]
    while edges[-1] * 2 < b:
        edges.append(edges[-1] * 2)
    edges.append(b)
    pieces = []
    for left, right in zip(edges, edges[1:]):
        middle = (left + right) / 2
        pieces += [(left, middle), (middle, right)]
    return pieces


def by_gauss(world, outputs, depth=None, order=40, digits=QUAD_DIGITS):
    """The same dictionary as `by_tanh_sinh`'s first, by graded Gauss pieces and Taylor states, any network.

    From t = 0 the pieces are graded toward it; later ones at most double.
    """
    if depth is None:
        depth = grading_depth(world)
    with precision(digits):
        layout = pr.Layout(world)
        holders = world.flow_nodes + world.collectors
        totals = {name: ZERO for name in holders + [FACE]}
        values = {name: [] for name in totals}
        ends = {x: pr.start_vector(world, x, layout) for x in world.species}
        volume_end = ZERO
        rule = gauss(order, digits)
        left = ZERO
        for right in outputs:
            for a, b in pr.segments(world, left, right):
                rates = world.link_rates(a)
                inflow = sum((q for _, target, q in rates if target in world.collectors), ZERO)
                trajectories = {}
                for x in world.species:
                    y = pr.with_inlets(world, x, a, ends[x], layout)
                    g = pr.generator(world, x, a, layout)
                    trajectories[x] = TaylorTrajectory(g, y, b - a)
                if a == 0:
                    points = gauss_points(rule, ZERO, b - a, depth)
                else:
                    points = [(s - a, w) for lo, hi in doubling_pieces(a, b) for s, w in rule.points(lo, hi)]
                for s, weight in points:
                    for x in world.species:
                        y = trajectories[x].at(s)
                        levels = {}
                        for name in layout.names:
                            value = y[layout.index[name]]
                            if name in world.inlets:
                                levels[name] = value
                            elif name in world.collectors:
                                volume = volume_end + inflow * s
                                levels[name] = value / volume if volume != 0 else ZERO
                            else:
                                levels[name] = value / world.volumes[name]
                        for name, rate in holder_rates(world, rates, levels).items():
                            totals[name] += weight * rate
                        totals[FACE] += weight * face_rate(world, x, levels)
                for x in world.species:
                    ends[x] = trajectories[x].at(b - a)
                volume_end += inflow * (b - a)
            for name in totals:
                values[name].append(totals[name])
            left = right
    return values


def chain_taylor_end(world, species, time, pieces=8):
    """The state at `time` by Taylor continuation alone (a third propagator, used in the checks)."""
    layout = pr.Layout(world)
    y = pr.start_vector(world, species, layout)
    for a, b in pr.segments(world, ZERO, time):
        y = pr.with_inlets(world, species, a, y, layout)
        g = pr.generator(world, species, a, layout, with_faces=species != "volume")
        piece = (b - a) / pieces
        for _ in range(pieces):
            y = TaylorTrajectory(g, y, piece).at(piece)
    return {name: y[layout.index[name]] for name in layout.nodes + layout.collectors}


__all__ = ["TWO"]
