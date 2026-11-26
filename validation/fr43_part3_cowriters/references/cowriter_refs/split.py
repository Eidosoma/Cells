"""The sizing model: the declared split of LAWS section 5 at a step h, in decimal arithmetic.

One step of `cowriter-first` is B(h/2) A(h/2) A(h/2) B(h/2), one of `population-first` A(h/2) B(h/2)
B(h/2) A(h/2).  A is exact: the two pools relax as an exponential, and the hazard is linear in time
(where the site is free it conducts nothing, so the row it reads is fixed; where it is active, its
propensity is constant).  B is exact for W5's reactions (a Taylor series whose remainder is below 1e-20
per half-step) and, for W6's gene unit, one step of SSPRK(3,3), as LAWS section 5 says.  Nothing here
judges a run.
"""

from __future__ import annotations

from decimal import Context, Decimal, localcontext
from operator import mul

PRECISION = 28
ZERO = Decimal(0)
REMAINDER = Decimal("1e-20")  # of one half-step's reactions flow, over the moiety's total


def sequence(world, first, lie=False):
    """The four sub-flows of one step, in order: True for the co-writer's, False for the population's."""
    cowriter_first = first != "population"
    half = [cowriter_first, not cowriter_first]
    return half + half if lie else half + half[::-1]


class SiteFlow:
    """A over a half-step, for one copy: the two pools, the hazard and the events."""

    __slots__ = ("active", "assemble", "cell_share", "constant", "dissolve", "hazard", "moved", "node", "now",
                 "rate", "relax", "row", "start", "thresholds", "times", "tau")

    def __init__(self, world, thresholds, row, node, tau):
        site = world.site
        self.active, self.hazard, self.moved = False, ZERO, ZERO
        self.row, self.node, self.tau = row, node, tau
        self.cell_share = world.cell / (world.cell + world.node)
        self.rate = site.conductance * (1 / world.cell + 1 / world.node)
        self.relax = 1 - (-self.rate * tau).exp()
        self.constant = site.read is None
        if site.read == "node":
            raise ValueError("the sizing model is the honest one: the read is in the cell")
        self.assemble = 2 * site.assemble_rate if self.constant else 2 * site.assemble_rate / world.cell
        self.dissolve = site.dissolve_rate
        self.thresholds, self.times = thresholds, []

    def advance(self, start):
        """A(tau) from the time `start`."""
        left = self.tau
        whole = True
        while True:
            if self.active:
                total = self.dissolve
            elif self.constant:
                total = self.assemble
            else:
                total = self.assemble * self.row
            gain = total * left
            need = self.thresholds[len(self.times)] - self.hazard
            if gain < need:
                self.hazard += gain
                if self.active:
                    self._relax(self.relax if whole else 1 - (-self.rate * left).exp())
                return
            wait = need / total
            if self.active:
                self._relax(1 - (-self.rate * wait).exp())
            left -= wait
            whole = False
            self.times.append(start + (self.tau - left))
            self.active = not self.active
            self.hazard = ZERO

    def _relax(self, fraction):
        flow = (self.row - self.cell_share * (self.row + self.node)) * fraction
        self.row -= flow
        self.node += flow
        self.moved += flow


def _sample_steps(world, steps):
    length = world.end / steps
    indices = []
    for sample in world.samples:
        index = sample / length
        if index != index.to_integral_value():
            raise ValueError("a sample is not a whole number of steps")
        indices.append(int(index))
    return indices


def reactions_run(world, thresholds, steps, first, lie=False):
    """W5's and W5-exact's split at h = T/steps, one copy: the events' times and the rows at the samples."""
    with localcontext(Context(prec=PRECISION)):
        length = world.end / steps
        tau = length / 2
        rows = world.start
        site = SiteFlow(world, thresholds, rows["n_S_c"], rows["n_S_o"], tau)
        spend = world.spend_rate / world.cell
        total = sum(rows.values(), ZERO)
        bound = (world.make_rate + 2 * spend * total) * tau
        terms = 1
        while bound ** (terms + 1) > REMAINDER:
            terms += 1
        # c[m] = tau/(m+1); make[m] is the share of X turned over at order m + 1 of the flow's expansion
        c = [tau / (m + 1) for m in range(terms)]
        make, share = [], Decimal(1)
        for m in range(terms):
            share = share * world.make_rate * c[m] * (-1 if m else 1)
            make.append(share)
        scaled = [spend * value for value in c]
        made_whole = 1 - (-world.make_rate * tau).exp()
        x, y, w, xi_1, xi_2 = rows["n_X"], rows["n_Y"], rows["n_W"], ZERO, ZERO
        order = sequence(world, first, lie)
        stops = set(_sample_steps(world, steps))
        names = ("n_S_c", "n_S_o", "n_X", "n_Y", "n_W", "xi_1", "xi_2", "moved")
        taken = [(site.row, site.node, x, y, w, xi_1, xi_2, site.moved)]
        for step in range(steps):
            base = length * step
            halves = 0
            for cowriter in order:
                if not cowriter:
                    site.advance(base + tau * halves)
                    halves += 1
                    continue
                s_series, y_series = [site.row], [y]
                for m in range(terms):
                    spent = scaled[m] * sum(map(mul, s_series, y_series[::-1]))
                    s_series.append(x * make[m] - spent)
                    y_series.append(-spent)
                spent = y - sum(y_series, ZERO)
                made = x * made_whole
                site.row += made - spent
                x -= made
                y -= spent
                w += spent
                xi_1 += made
                xi_2 += spent
            if step + 1 in stops:
                taken.append((site.row, site.node, x, y, w, xi_1, xi_2, site.moved))
        return site.times, {name: [row[i] for row in taken] for i, name in enumerate(names)}


class GeneChain:
    """The gene unit's own half-steps by SSPRK(3,3): they read neither R nor the population."""

    def __init__(self, world, tau):
        self.tau = tau
        m = world.stages
        moles = world.cell * world.standard
        mu = world.mu
        self.k_x = (mu["residue"] + 2 * mu["Pi"] - mu["N"]).exp() / moles
        self.saturation = world.saturation * world.cell
        self.rate = world.stage_rate
        self.begin = world.initiation * world.template_conc
        self.per_stage = world.stage_residues
        self.free, self.chain = world.machines, [ZERO] * m
        self.n, self.p = world.start["n_N"], world.start["n_Pi"]
        self.inits = self.exits = self.made = ZERO

    def _rates(self, free, chain, n, p):
        speed = self.rate * (n - self.k_x * p * p) / (self.saturation + n)
        flux = [speed * amount for amount in chain]
        return self.begin * free, flux, sum(flux, ZERO)

    def half_step(self):
        """One half-step: the finished chains' rates at its three stages, and the chains it finished."""
        tau, r = self.tau, self.per_stage
        stages = []
        free, chain, n, p = self.free, self.chain, self.n, self.p
        first = self._rates(free, chain, n, p)
        stages.append(first)
        second = self._rates(*self._moved(tau, first[0], first[1], first[2]))
        stages.append(second)
        quarter = tau / 4
        mixed = [a + b for a, b in zip(first[1], second[1], strict=True)]
        third = self._rates(*self._moved(quarter, first[0] + second[0], mixed, first[2] + second[2]))
        stages.append(third)
        sixth = tau / 6
        begun = sixth * (first[0] + second[0] + 4 * third[0])
        flux = [sixth * (a + b + 4 * c) for a, b, c in zip(first[1], second[1], third[1], strict=True)]
        exits = sum(flux, ZERO)
        self.free += flux[-1] - begun
        links = [begun] + flux
        self.chain = [amount + links[j] - links[j + 1] for j, amount in enumerate(chain)]
        self.n -= r * exits
        self.p += 2 * r * exits
        self.inits += begun
        self.exits += exits
        self.made += flux[-1]
        return first[1][-1], second[1][-1], third[1][-1], flux[-1]

    def _moved(self, weight, begun, flux, exits):
        links = [begun] + flux
        return (
            self.free + weight * (flux[-1] - begun),
            [amount + weight * (links[j] - links[j + 1]) for j, amount in enumerate(self.chain)],
            self.n - weight * self.per_stage * exits,
            self.p + weight * 2 * self.per_stage * exits,
        )


class ReverseShare:
    """e^y of LAWS section 3 as k n_M R^(-1/L): the power from a nearby one, by its binomial series."""

    LIMITS = ((Decimal("1e-5"), 4), (Decimal("1e-3"), 8), (Decimal("1e-2"), 12))

    def __init__(self, world):
        moles = world.cell * world.standard
        mu = world.mu
        exponent = Decimal(-1) / world.residues
        self.scale = (mu["M"] - mu["residue"]).exp() / moles * (-exponent * moles.ln()).exp()
        self.exponent = exponent
        self.binomials, term = [Decimal(1)], Decimal(1)
        for i in range(12):
            term = term * (exponent - i) / (i + 1)
            self.binomials.append(term)
        self.near = self.inverse = self.root = None

    def __call__(self, r, m):
        if self.near is not None:
            offset = r * self.inverse - 1
            size = abs(offset)
            for limit, terms in self.LIMITS:
                if size < limit:
                    table = self.binomials
                    total = table[terms]
                    for i in range(terms - 1, -1, -1):
                        total = total * offset + table[i]
                    return self.scale * m * self.root * total
        self.near, self.inverse = r, 1 / r
        self.root = (self.exponent * r.ln()).exp()
        return self.scale * m * self.root


class Member:
    """One copy at one declared order beside the gene unit: R, M, the books of the degradation, the site."""

    def __init__(self, world, thresholds, tau):
        rows = world.start
        self.site = SiteFlow(world, thresholds, rows["n_R_c"], rows["n_R_o"], tau)
        self.m, self.lost = rows["n_M"], ZERO
        self.share = ReverseShare(world)
        self.rate, self.residues, self.tau = world.degradation, world.residues, tau

    def _loss(self, r, m):
        return self.rate * r * (1 - self.share(r, m))

    def half_step(self, at_first, at_second, at_third, made):
        """B(tau), given the chain's finishing rates at the stages and the chains it finished."""
        tau, length = self.tau, self.residues
        r, m = self.site.row, self.m
        quarter = tau / 4
        one = self._loss(r, m)
        two = self._loss(r + tau * (at_first - one), m + tau * length * one)
        pair = one + two
        three = self._loss(r + quarter * (at_first + at_second - pair), m + quarter * length * pair)
        lost = tau * (pair + 4 * three) / 6
        self.site.row = r + made - lost
        self.m = m + length * lost
        self.lost += lost


def gene_runs(world, steps, members):
    """W6's split at h = T/steps for `members`, a list of (first, thresholds): each one's times and rows."""
    with localcontext(Context(prec=PRECISION)):
        length = world.end / steps
        tau = length / 2
        chain = GeneChain(world, tau)
        runs = [Member(world, thresholds, tau) for _, thresholds in members]
        orders = [sequence(world, first) for first, _ in members]
        stops = set(_sample_steps(world, steps))
        taken = [[_gene_row(chain, run)] for run in runs]
        for step in range(steps):
            base = length * step
            halves = (chain.half_step(), chain.half_step())
            for run, order in zip(runs, orders, strict=True):
                done_a = done_b = 0
                for cowriter in order:
                    if cowriter:
                        run.half_step(*halves[done_b])
                        done_b += 1
                    else:
                        run.site.advance(base + tau * done_a)
                        done_a += 1
            if step + 1 in stops:
                for run, rows in zip(runs, taken, strict=True):
                    rows.append(_gene_row(chain, run))
        return [
            (run.site.times, {name: [row[name] for row in rows] for name in rows[0]})
            for run, rows in zip(runs, taken, strict=True)
        ]


def _gene_row(chain, run):
    r = chain.per_stage
    return {
        "n_R_c": run.site.row,
        "n_R_o": run.site.node,
        "n_N": chain.n,
        "n_M": run.m,
        "n_Pi": chain.p,
        "free": chain.free,
        "engaged": sum(chain.chain, ZERO),
        "transit": r * sum((j * amount for j, amount in enumerate(chain.chain)), ZERO),
        "inits": chain.inits,
        "exits": chain.exits,
        "made": chain.made,
        "lost": run.lost,
        "moved": run.site.moved,
    }
