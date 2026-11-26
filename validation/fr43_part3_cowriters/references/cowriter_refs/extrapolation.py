"""Method B: the same process by Gragg-Bulirsch-Stoer extrapolation in decimal arithmetic.

It shares no formula code with method A.  The rates are evaluated directly from the laws at each stage,
the steps land on every sample, and an event's time comes from the hazard as the independent variable
(dt/dH = 1/a_0): a step in time that would cross the threshold is discarded, and the state is carried
from its start to H = E_k.  Where a_0 is constant the event's time is the closed form.
"""

from __future__ import annotations

import math
from decimal import Context, Decimal, localcontext

PRECISION = 34
COLUMNS = 12  # of the extrapolation table: the sequence 2, 4, ..., 2 COLUMNS
TOLERANCE = Decimal("1e-23")  # of each component's weight, per step
ZERO = Decimal(0)


class ReactionsRates:
    """LAWS sections 1 and 2, in concentrations."""

    names = ("n_X", "n_S_c", "n_S_o", "n_Y", "n_W", "xi_1", "xi_2", "moved")

    def __init__(self, world):
        self.world = world
        rows = world.start
        self.initial = [rows["n_X"], rows["n_S_c"], rows["n_S_o"], rows["n_Y"], rows["n_W"], ZERO, ZERO, ZERO]
        total = sum(self.initial, ZERO)
        self.weights = [total] * len(self.initial)

    def read_total(self, y):
        """The propensity total while the site is free, from the row its channel reads."""
        site, w = self.world.site, self.world
        phi = y[1] / w.cell if site.read == "cell" else y[2] / w.node
        return 2 * site.assemble_rate * phi

    def rates(self, y, active):
        w = self.world
        x, s_c, s_o, other = y[0], y[1], y[2], y[3]
        make = w.make_rate * x
        spend = w.spend_rate * w.cell * (s_c / w.cell) * (other / w.cell)
        flow = w.site.conductance * (s_c / w.cell - s_o / w.node) if active else ZERO
        return [-make, make - spend - flow, flow, -spend, spend, make, spend, flow]

    def readouts(self, rows):
        return {name: [row[i] for row in rows] for i, name in enumerate(self.names)}


class GeneRates:
    """LAWS sections 1 and 3, in activities."""

    def __init__(self, world):
        self.world = world
        rows, m = world.start, world.stages
        self.initial = (
            [rows["n_N"], rows["n_Pi"], rows["n_M"], rows["n_R_c"], rows["n_R_o"], world.machines]
            + [ZERO] * m
            + [ZERO] * 5
        )
        chain = rows["n_N"] / world.residues
        self.weights = [rows["n_N"]] * 3 + [chain] * 2 + [world.machines] * (m + 1) + [chain] * 5
        mu = world.mu
        self.x_constant = (mu["residue"] + 2 * mu["Pi"] - mu["N"]).exp()
        self.y_constant = (mu["M"] - mu["residue"]).exp()
        self.unit_amount = world.cell * world.standard

    def read_total(self, y):
        site, w = self.world.site, self.world
        phi = y[3] / w.cell if site.read == "cell" else y[4] / w.node
        return 2 * site.assemble_rate * phi

    def rates(self, y, active):
        w, m = self.world, self.world.stages
        n, p, mono, r_c, r_o, free = y[:6]
        c_n = n / w.cell
        speed = w.stage_rate * c_n / (w.saturation + c_n)
        if w.transcription_factor:
            activity = p / self.unit_amount
            speed *= 1 - self.x_constant * activity * activity / (n / self.unit_amount)
        loss = w.degradation * r_c
        if w.degradation_factor:
            root = (-(r_c / self.unit_amount).ln() / w.residues).exp()
            loss *= 1 - self.y_constant * (mono / self.unit_amount) * root
        flow = w.site.conductance * (r_c / w.cell - r_o / w.node) if active else ZERO
        begun = w.initiation * w.template_conc * free
        flux = [speed * y[6 + j] for j in range(m)]
        all_exits = sum(flux, ZERO)
        chain = [begun] + flux
        stages = [chain[j] - chain[j + 1] for j in range(m)]
        return [
            -w.stage_residues * all_exits,
            2 * w.stage_residues * all_exits,
            w.residues * loss,
            flux[-1] - loss - flow,
            flow,
            flux[-1] - begun,
            *stages,
            begun,
            all_exits,
            flux[-1],
            loss,
            flow,
        ]

    def readouts(self, rows):
        m, r = self.world.stages, self.world.stage_residues
        columns = list(zip(*rows, strict=True))
        names = ("n_N", "n_Pi", "n_M", "n_R_c", "n_R_o", "free")
        series = {name: list(columns[i]) for i, name in enumerate(names)}
        complexes = columns[6 : 6 + m]
        for i, name in enumerate(("inits", "exits", "made", "lost", "moved")):
            series[name] = list(columns[6 + m + i])
        series["engaged"] = [sum(stage, ZERO) for stage in zip(*complexes, strict=True)]
        series["transit"] = [
            r * sum((j * amount for j, amount in enumerate(stage)), ZERO) for stage in zip(*complexes, strict=True)
        ]
        return series


def _coefficients():
    """Neville's weights: T(j, k) = T(j, k-1) + w(j, k) (T(j, k-1) - T(j-1, k-1))."""
    table = []
    for j in range(COLUMNS):
        n_j = 2 * (j + 1)
        row = [ZERO]
        for k in range(1, j + 1):
            n_i = 2 * (j - k + 1)
            row.append(Decimal(n_i * n_i) / Decimal(n_j * n_j - n_i * n_i))
        table.append(row)
    return table


def _attempt(field, y, h, weights, table):
    """One extrapolated step of the autonomous system y' = field(y): the end and the error over the weights."""
    slope = field(y)
    size = len(y)
    previous = []
    for j in range(COLUMNS):
        n = 2 * (j + 1)
        part = h / n
        twice = 2 * part
        older = y
        newer = [a + part * b for a, b in zip(y, slope, strict=True)]
        for _ in range(n - 1):
            rate = field(newer)
            older, newer = newer, [a + twice * b for a, b in zip(older, rate, strict=True)]
        rate = field(newer)
        value = [(a + b + part * c) / 2 for a, b, c in zip(older, newer, rate, strict=True)]
        row = [value]
        for k in range(1, j + 1):
            weight = table[j][k]
            left, below = row[k - 1], previous[k - 1]
            row.append([left[i] + weight * (left[i] - below[i]) for i in range(size)])
        previous = row
    last, second = previous[-1], previous[-2]
    error = max(abs(a - b) / w for a, b, w in zip(last, second, weights, strict=True))
    return last, error


def _rescale(h, error):
    """The next trial step, from the error of the last one."""
    if error == 0:
        return 2 * h
    ratio = TOLERANCE / error
    tens = ratio.adjusted() + math.log10(float(ratio.scaleb(-ratio.adjusted())))
    factor = 0.85 * 10.0 ** (tens / (2 * COLUMNS - 1))
    return h * Decimal(f"{min(2.5, max(0.1, factor)):.3g}")


def _carry(field, y, span, trial, weights, table):
    """Carry y over `span` of the independent variable: the end, and the last trial step."""
    done = ZERO
    while done < span:
        h = min(trial, span - done)
        end, error = _attempt(field, y, h, weights, table)
        if error <= TOLERANCE:
            y, done = end, done + h
            if h == trial or _rescale(h, error) > trial:
                trial = _rescale(h, error)
        else:
            trial = _rescale(h, error)
    return y, trial


def solve(world, thresholds):
    """The events' times and the rows and books at the samples of one copy, to the world's end."""
    with localcontext(Context(prec=PRECISION)):
        parts = ReactionsRates(world) if world.kind == "reactions" else GeneRates(world)
        site, table = world.site, _coefficients()
        y, t, active, hazard = list(parts.initial), ZERO, False, ZERO
        rows, times = [list(y)], []
        trial = Decimal("0.05")
        for sample in world.samples[1:]:
            while t < sample:
                need = thresholds[len(times)] - hazard
                constant = active or site.read is None
                if constant:
                    total = site.dissolve_rate if active else 2 * site.assemble_rate
                    wait = need / total
                    span = min(wait, sample - t)
                    y, trial = _carry(lambda v, a=active: parts.rates(v, a), y, span, trial, parts.weights, table)
                    fires = wait <= sample - t
                    t = t + span if fires or span < sample - t else sample
                    hazard = ZERO if fires else hazard + total * span
                else:
                    fires, y, t, hazard, trial = _free_step(parts, y, t, hazard, sample, need, trial, table)
                if fires:
                    times.append(t)
                    active = not active
            rows.append(list(y))
        return times, parts.readouts(rows)


def _free_step(parts, y, t, hazard, sample, need, trial, table):
    """One step of the free site: in time, or, where the threshold lies within it, in the hazard."""

    def in_time(v):
        return [*parts.rates(v[:-1], False), parts.read_total(v)]

    def in_hazard(v):
        total = parts.read_total(v)
        return [*(rate / total for rate in parts.rates(v[:-1], False)), 1 / total]

    h = min(trial, sample - t)
    weights = [*parts.weights, Decimal(1)]
    end, error = _attempt(in_time, [*y, ZERO], h, weights, table)
    if error > TOLERANCE:
        return False, y, t, hazard, _rescale(h, error)
    grown = _rescale(h, error)
    if h == trial or grown > trial:
        trial = grown
    if end[-1] < need:
        return False, end[:-1], sample if h == sample - t else t + h, hazard + end[-1], trial
    # The last component is now the time since the step's start, in the hazard's own variable.
    crossing, _ = _carry(in_hazard, [*y, ZERO], need, need, weights, table)
    return True, crossing[:-1], t + crossing[-1], ZERO, trial
