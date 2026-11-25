"""Method A: the exact coupled process by Taylor series in decimal arithmetic.

Between events the rows, the books and the hazard are expanded about the current time, by recurrences on
their Taylor coefficients.  The step comes from the last two coefficients.  Samples are read from the
expansion, and an event is the root of the hazard's polynomial (safeguarded Newton).  The books are
integrated from their own rates, so the identities of READOUTS section 4 are tests of the solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Context, Decimal, localcontext
from operator import mul

from .declared import ACTIVE, CHANNELS, COUNTS_AFTER, FREE, machine_start

PRECISION = 50
ORDER = 40
TOLERANCE = Decimal("1e-40")  # of each component's weight, per step
DOMAIN_POINTS = 16  # points of each step at which the affinities are read, beside its ends


@dataclass
class Solution:
    """One copy's exact process: its events, and its rows and books at the samples."""

    times: list = field(default_factory=list)
    channels: list = field(default_factory=list)
    counts_after: list = field(default_factory=list)
    series: dict = field(default_factory=dict)
    steps: int = 0
    affinities: dict | None = None  # the gene world: the largest x and y met


def horner(coefficients, x):
    total = coefficients[-1]
    for coefficient in coefficients[-2::-1]:
        total = total * x + coefficient
    return total


def product(left, right, k):
    """The k-th coefficient of a product of two series."""
    return sum(map(mul, left[: k + 1], right[k::-1]))


class ReactionsSeries:
    """LAWS section 2 with the transfer and the hazard."""

    names = ("n_S_c", "n_S_o", "n_X", "n_Y", "n_W", "xi_1", "xi_2", "moved")

    def __init__(self, world):
        self.world = world

    def start(self):
        rows = self.world.start
        return [rows[name] for name in self.names[:5]] + [Decimal(0)] * 3

    def weights(self):
        rows = self.world.start
        sulfur = rows["n_X"] + rows["n_S_c"] + rows["n_S_o"] + rows["n_W"]
        other = rows["n_Y"] + rows["n_W"]
        return [sulfur, sulfur, sulfur, other, sulfur, sulfur, sulfur, sulfur]

    def series(self, state, active, order):
        w, site = self.world, self.world.site
        cell, node = w.cell, w.node
        conductance = site.conductance if active else Decimal(0)
        g_cell, g_node = conductance / cell, conductance / node
        spend = w.spend_rate / cell
        s, o, x, y = [state[0]], [state[1]], [state[2]], [state[3]]
        q, e1, e2, mv = [state[4]], [state[5]], [state[6]], [state[7]]
        hazard = [Decimal(0)]
        for k in range(order):
            made = w.make_rate * x[k]
            spent = spend * product(s, y, k)
            flow = g_cell * s[k] - g_node * o[k] if active else Decimal(0)
            if active:
                rate = site.dissolve_rate if k == 0 else Decimal(0)
            elif site.read is None:
                rate = 2 * site.assemble_rate if k == 0 else Decimal(0)
            elif site.read == "cell":
                rate = 2 * site.assemble_rate * s[k] / cell
            else:
                rate = 2 * site.assemble_rate * o[k] / node
            n = k + 1
            s.append((made - spent - flow) / n)
            o.append(flow / n)
            x.append(-made / n)
            y.append(-spent / n)
            q.append(spent / n)
            e1.append(made / n)
            e2.append(spent / n)
            mv.append(flow / n)
            hazard.append(rate / n)
        return [s, o, x, y, q, e1, e2, mv], hazard


class GeneSeries:
    """LAWS section 3 with the transfer and the hazard."""

    def __init__(self, world):
        self.world = world
        complexes = tuple(f"C_{j + 1}" for j in range(world.stages))
        self.state_names = (
            ("free",) + complexes
            + ("n_N", "n_Pi", "n_M", "n_R_c", "n_R_o", "inits", "exits", "made", "lost", "moved")
        )
        rows = world.start
        moles = world.cell * world.standard  # the amount of a row at unit activity
        mu = world.mu
        # e^x = k_x n_Pi^2 / n_N, and n_R e^y = k_y n_M n_R^(1 - 1/L)
        self.k_x = (mu["residue"] + 2 * mu["Pi"] - mu["N"]).exp() / moles
        self.power = 1 - Decimal(1) / world.residues
        self.k_y = (mu["M"] - mu["residue"]).exp() / moles * (moles.ln() / world.residues).exp()
        self.initiation = world.initiation * world.template_conc
        self.largest = {"x": None, "y": None}
        self.unit = {
            "machines": world.machines,
            "monomer": rows["n_N"],
            "chain": rows["n_N"] / world.residues,
        }

    def start(self):
        rows = self.world.start
        return (
            machine_start(self.world)
            + [rows["n_N"], rows["n_Pi"], rows["n_M"], rows["n_R_c"], rows["n_R_o"]]
            + [Decimal(0)] * 5
        )

    def weights(self):
        m, unit = self.world.stages, self.unit
        return (
            [unit["machines"]] * (m + 1)
            + [unit["monomer"]] * 3
            + [unit["chain"]] * 2
            + [unit["chain"]] * 5
        )

    def series(self, state, active, order):
        w, site, m = self.world, self.world.site, self.world.stages
        zero = Decimal(0)
        conductance = site.conductance if active else zero
        g_cell, g_node = conductance / w.cell, conductance / w.node
        saturation = w.saturation * w.cell
        f = [state[0]]
        c = [[state[1 + j]] for j in range(m)]
        n, p, mo, r, o, b_init, b_exit, b_made, b_lost, b_moved = ([v] for v in state[m + 1 :])
        share, square, reverse, forward, phi = [], [], [], [], []
        power, held = [], []
        hazard = [zero]
        for k in range(order):
            if k == 0:
                share.append(n[0] / (saturation + n[0]))
                square.append(p[0] * p[0])
                reverse.append(self.k_x * square[0] / n[0])
                forward.append(1 - reverse[0] if w.transcription_factor else Decimal(1))
                power.append((self.power * r[0].ln()).exp())
            else:
                tail = n[1 : k + 1]
                share.append((n[k] - sum(map(mul, tail, share[k - 1 :: -1]))) / (saturation + n[0]))
                square.append(product(p, p, k))
                reverse.append((self.k_x * square[k] - sum(map(mul, tail, reverse[k - 1 :: -1]))) / n[0])
                forward.append(-reverse[k] if w.transcription_factor else zero)
                total = zero
                for i in range(1, k + 1):
                    total += (self.power * i - (k - i)) * r[i] * power[k - i]
                power.append(total / (k * r[0]))
            phi.append(product(share, forward, k))
            exits = [w.stage_rate * product(phi, c[j], k) for j in range(m)]
            total_exits = sum(exits, zero)
            begun = self.initiation * f[k]
            if w.degradation_factor:
                held.append(product(mo, power, k))
                lost = w.degradation * (r[k] - self.k_y * held[k])
            else:
                lost = w.degradation * r[k]
            flow = g_cell * r[k] - g_node * o[k] if active else zero
            if active:
                rate = site.dissolve_rate if k == 0 else zero
            elif site.read == "cell":
                rate = 2 * site.assemble_rate * r[k] / w.cell
            elif site.read == "node":
                rate = 2 * site.assemble_rate * o[k] / w.node
            else:
                rate = 2 * site.assemble_rate if k == 0 else zero
            d = k + 1
            f.append((exits[m - 1] - begun) / d)
            c[0].append((begun - exits[0]) / d)
            for j in range(1, m):
                c[j].append((exits[j - 1] - exits[j]) / d)
            n.append(-w.stage_residues * total_exits / d)
            p.append(2 * w.stage_residues * total_exits / d)
            mo.append(w.residues * lost / d)
            r.append((exits[m - 1] - lost - flow) / d)
            o.append(flow / d)
            b_init.append(begun / d)
            b_exit.append(total_exits / d)
            b_made.append(exits[m - 1] / d)
            b_lost.append(lost / d)
            b_moved.append(flow / d)
            hazard.append(rate / d)
        return [f, *c, n, p, mo, r, o, b_init, b_exit, b_made, b_lost, b_moved], hazard

    def watch(self, coefficients, length):
        """The largest x and y of LAWS section 3 on one step, read from its expansion."""
        m = self.world.stages
        n, p, mo, r = coefficients[m + 1 : m + 5]
        for i in range(DOMAIN_POINTS + 2):
            at = length * i / (DOMAIN_POINTS + 1)
            x, y = affinities(self.world, horner(n, at), horner(p, at), horner(mo, at), horner(r, at))
            for name, value in (("x", x), ("y", y)):
                if self.largest[name] is None or value > self.largest[name]:
                    self.largest[name] = value


def affinities(world, n, p, m, r):
    """x and y of LAWS section 3, from the rows in the cell."""
    moles, mu = world.cell * world.standard, world.mu
    x = mu["residue"] + 2 * (mu["Pi"] + (p / moles).ln()) - (mu["N"] + (n / moles).ln())
    y = mu["M"] + (m / moles).ln() - mu["residue"] - (r / moles).ln() / world.residues
    return x, y


def system(world):
    return ReactionsSeries(world) if world.kind == "reactions" else GeneSeries(world)


def _step_length(coefficients, hazard, weights, order):
    """The length at which the last two terms of every expansion fall to the tolerance."""
    shortest = None
    for series, weight in [*zip(coefficients, weights, strict=True), (hazard, Decimal(1))]:
        for j in (order - 1, order):
            size = abs(series[j])
            if size == 0:
                continue
            ratio = TOLERANCE * weight / size
            length = math.exp((ratio.adjusted() * math.log(10.0) + math.log(float(ratio.scaleb(-ratio.adjusted())))) / j)
            if shortest is None or length < shortest:
                shortest = length
    return None if shortest is None else Decimal(f"{0.9 * shortest:.3g}")


def _crossing(hazard, need, length, reached):
    """The root of hazard(x) = need on (0, length], the hazard increasing there."""
    slope = [j * c for j, c in enumerate(hazard)][1:]
    low, high = Decimal(0), length
    x = length * need / reached
    small = Decimal(10) ** (6 - PRECISION)
    for _ in range(400):
        value = horner(hazard, x) - need
        if value == 0:
            return x
        if value > 0:
            high = x
        else:
            low = x
        step = value / horner(slope, x)
        following = x - step
        if not low <= following <= high:
            following = (low + high) / 2
        if abs(following - x) <= small * length:
            return following
        x = following
    raise ArithmeticError("the hazard's crossing did not converge")


def solve(world, thresholds, watch=False, active=False, order=ORDER):
    """The exact process of one copy to the world's end: its events, its rows and its books.

    `active` starts the site active (the closed-form relaxation's check alone; a run starts free).
    """
    with localcontext(Context(prec=PRECISION)):
        parts = system(world)
        weights = parts.weights()
        state, hazard_now, t = parts.start(), Decimal(0), Decimal(0)
        out = Solution()
        rows = [list(state)]
        next_sample, samples, end = 1, world.samples, world.end
        while t < end:
            coefficients, hazard = parts.series(state, active, order)
            length = _step_length(coefficients, hazard, weights, order)
            length = end - t if length is None else min(length, end - t)
            need = thresholds[len(out.times)] - hazard_now
            reached = horner(hazard, length)
            fires = reached >= need
            if fires:
                length = _crossing(hazard, need, length, reached)
            while next_sample < len(samples) and samples[next_sample] <= t + length:
                at = samples[next_sample] - t
                rows.append([horner(c, at) for c in coefficients])
                next_sample += 1
            if watch:
                parts.watch(coefficients, length)
            state = [horner(c, length) for c in coefficients]
            t += length
            out.steps += 1
            if fires:
                channel = CHANNELS[ACTIVE if active else FREE]
                out.times.append(t)
                out.channels.append(channel)
                out.counts_after.append(list(COUNTS_AFTER[channel]))
                active, hazard_now = not active, Decimal(0)
            else:
                hazard_now += reached
        if len(rows) != len(samples):
            raise ArithmeticError("a sample was missed")
        out.series = readouts(world, rows)
        if watch:
            out.affinities = dict(parts.largest)
        return out


def readouts(world, rows):
    """READOUTS section 1's rows and books at the samples, from the states there."""
    parts = system(world)
    if world.kind == "reactions":
        return {name: [row[i] for row in rows] for i, name in enumerate(parts.names)}
    m, r = world.stages, world.stage_residues
    series = {name: [row[i] for row in rows] for i, name in enumerate(parts.state_names)}
    complexes = [series.pop(f"C_{j + 1}") for j in range(m)]
    series["engaged"] = [sum(stage, Decimal(0)) for stage in zip(*complexes, strict=True)]
    series["transit"] = [
        r * sum((j * amount for j, amount in enumerate(stage)), Decimal(0)) for stage in zip(*complexes, strict=True)
    ]
    return series


def decimal_times(world, thresholds):
    """W5-exact's event times as LAWS section 4's sums of E_i / a_0,i, up to the world's end."""
    with localcontext(Context(prec=PRECISION + 10)):
        totals = (2 * world.site.assemble_rate, world.site.dissolve_rate)
        times, t = [], Decimal(0)
        for k, threshold in enumerate(thresholds):
            t += threshold / totals[k % 2]
            if t > world.end:
                return times
            times.append(t)
        raise ArithmeticError("the draws ran out before the world's end")
