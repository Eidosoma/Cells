"""From one set of inputs and its draws to the reference files of SPEC section 7.

The heavy work is a list of independent tasks (one copy's exact solution by both methods, one copy's split
run at one step), so the number of worker processes changes nothing in the files.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Context, Decimal, localcontext
from math import inf, nextafter

from . import declared, draws, extrapolation, pooled, split, taylor
from .declared import exact, grid

PRECISION = 60
ZERO = Decimal(0)
TWO_METHODS = 10  # the published accuracy holds this many times the two methods' difference
GENE_CHUNK = 8  # copies and orders that one task of the gene world's split carries together


def context():
    return localcontext(Context(prec=PRECISION))


def make_world(name, block, plant=None):
    with context():
        base = declared.world(name, block)
        return declared.planted(base, plant) if plant else base


def make_thresholds(u1):
    return draws.thresholds(u1, Context(prec=PRECISION))


# ---------------------------------------------------------------------------------------------- tasks


def exact_task(task):
    """One copy's exact process by both methods, honest or planted."""
    name, block, u1, plant = task
    world, thresholds = make_world(name, block, plant), make_thresholds(u1)
    solution = taylor.solve(world, thresholds, watch=world.kind == "gene" and plant is None)
    if world.site.read is None:
        solution.times = taylor.decimal_times(world, thresholds)  # the closed form (LAWS section 4)
    times, series = extrapolation.solve(world, thresholds)
    return solution, times, series


def integrated_times_task(task):
    """W5-exact's events by method A's own hazard, to be compared with the decimal sums."""
    name, block, u1 = task
    return taylor.solve(make_world(name, block), make_thresholds(u1)).times


def split_task(task):
    """The split model at one step: a list of (times, series), one per (first, copy's draws)."""
    name, block, members, steps, lie = task
    world = make_world(name, block)
    pairs = [(first, make_thresholds(u1)) for first, u1 in members]
    if world.kind == "gene":
        return split.gene_runs(world, steps, pairs)
    return [split.reactions_run(world, thresholds, steps, first, lie) for first, thresholds in pairs]


def relaxation_residual(name, block):
    """SPEC 9.2: the transfer alone, by method A, against its exponential: the largest relative difference."""
    with context():
        world = make_world(name, block)
        if world.kind == "reactions":
            world = replace(world, make_rate=ZERO, spend_rate=ZERO)
            cell, node = "n_S_c", "n_S_o"
        else:
            world = replace(world, initiation=ZERO, degradation=ZERO)
            cell, node = "n_R_c", "n_R_o"
        solution = taylor.solve(world, [Decimal("1e30")], active=True)
        rate = world.site.conductance * (1 / world.cell + 1 / world.node)
        start_c, start_o = world.start[cell], world.start[node]
        rest = (start_c + start_o) * world.cell / (world.cell + world.node)
        worst = ZERO
        for i, t in enumerate(world.samples):
            moved = (start_c - rest) * (1 - (-rate * t).exp())
            for value, closed in (
                (solution.series[cell][i], start_c - moved),
                (solution.series[node][i], start_o + moved),
                (solution.series["moved"][i], moved),
            ):
                if closed != 0:
                    worst = max(worst, abs(value - closed) / abs(closed))
                elif value != 0:
                    raise ArithmeticError("the closed form is zero and the solution is not")
        return worst


# ------------------------------------------------------------------------------------------ rounding


def upward(value):
    """The least double not below a non-negative decimal."""
    out = float(value)
    while Decimal(out) < value:
        out = nextafter(out, inf)
    return out


# ------------------------------------------------------------------------------------------- one copy


@dataclass
class Copy:
    """One copy's exact process, as published: its values, their accuracy and the two methods' difference."""

    index: int
    seed: int
    times: list  # decimals
    channels: list
    counts_after: list
    series: dict  # decimals
    time_accuracy: Decimal
    accuracy: dict  # decimals, by readout
    time_difference: Decimal  # the two methods', and
    differences: dict  # by readout
    affinities: dict | None
    judged: int = 0  # K


def make_copy(index, seed, world, result):
    solution, other_times, other_series = result
    with context():
        if len(other_times) != len(solution.times):
            raise ArithmeticError("the two methods count different events")
        apart = max((abs(a - b) for a, b in zip(solution.times, other_times, strict=True)), default=ZERO)
        accuracy, differences = {}, {}
        for name, values in solution.series.items():
            difference = max(abs(a - b) for a, b in zip(values, other_series[name], strict=True))
            differences[name] = difference
            accuracy[name] = pooled.UNIT * max(abs(v) for v in values) + TWO_METHODS * difference
        return Copy(
            index=index,
            seed=seed,
            times=solution.times,
            channels=solution.channels,
            counts_after=solution.counts_after,
            series=solution.series,
            time_accuracy=pooled.UNIT * world.end + TWO_METHODS * apart,
            accuracy=accuracy,
            time_difference=apart,
            differences=differences,
            affinities=solution.affinities,
        )


# ------------------------------------------------------------------------------------------ one world


class WorldSet:
    """Everything the reference file of one world holds, from the task results."""

    def __init__(self, inputs, name, table):
        self.inputs, self.name, self.table = inputs, name, table
        self.block = inputs["worlds"][name]
        self.world = make_world(name, self.block)
        self.families = [f for f in inputs["families"] if f["world"] == name]
        self.judged = inputs["judged"][name]
        self.plants = [p for p in inputs["plants"] if p["world"] == name]
        self.u1 = [copy["u1"] for copy in table]
        self.rungs = [grid(h) for h in self.families[0]["rungs_s"]]
        if any([grid(h) for h in f["rungs_s"]] != self.rungs for f in self.families):
            raise ValueError("the families of a world share their rungs")
        retry = self.families[0]["retry_rung_s"]
        self.retry = None if retry is None else grid(retry)
        self.all_rungs = self.rungs + ([] if self.retry is None else [self.retry])
        self.exact_results, self.split_results, self.lie_results = {}, {}, {}
        self.integrated = {}

    # -- tasks

    def series_plants(self):
        return [p for p in self.plants if p["kind"] == "reference" and p["id"] in declared.SERIES_PLANTS]

    def lie_plant(self):
        found = [p for p in self.plants if p["kind"] == "engine"]
        return found[0] if found else None

    def firsts(self):
        return [f["first"] for f in self.families]

    def steps(self, rung):
        with context():
            count = self.world.end / rung
            if count != count.to_integral_value():
                raise ValueError("the horizon is not a whole number of steps")
            return int(count)

    def tasks(self):
        """(key, function, argument), roughly the longest first."""
        out = []
        for rung_index in reversed(range(len(self.all_rungs))):
            steps = self.steps(self.all_rungs[rung_index])
            members = [(first, c) for first in self.firsts() for c in range(len(self.u1))]
            size = GENE_CHUNK if self.world.kind == "gene" else 1
            for start in range(0, len(members), size):
                part = members[start : start + size]
                argument = (self.name, self.block, [(f, self.u1[c]) for f, c in part], steps, False)
                out.append((("split", self.name, rung_index, tuple(part)), split_task, argument))
        if self.lie_plant():
            first = self.families_of(self.lie_plant())[0]["first"]
            for rung_index in range(len(self.rungs) - 3, len(self.rungs)):
                for c in range(len(self.u1)):
                    argument = (self.name, self.block, [(first, self.u1[c])], self.steps(self.rungs[rung_index]), True)
                    out.append((("lie", self.name, rung_index, c), split_task, argument))
        for plant in [None] + self.series_plants():
            for c in range(len(self.u1)):
                key = ("exact", self.name, plant["id"] if plant else None, c)
                out.append((key, exact_task, (self.name, self.block, self.u1[c], plant)))
        if self.world.site.read is None:
            for c in range(len(self.u1)):
                out.append((("integrated", self.name, c), integrated_times_task, (self.name, self.block, self.u1[c])))
        return out

    def take(self, key, value):
        kind = key[0]
        if kind == "split":
            for (first, c), run in zip(key[3], value, strict=True):
                self.split_results[first, key[2], c] = run
        elif kind == "lie":
            self.lie_results[key[2], key[3]] = value[0]
        elif kind == "exact":
            self.exact_results[key[2], key[3]] = value
        else:
            self.integrated[key[2]] = value

    # -- the exact process

    def families_of(self, plant):
        if plant["families"] == "both":
            return self.families
        return [f for f in self.families if f["id"] in plant["families"]]

    def cut(self):
        """T - g h_1: the judged events end there (SPEC section 3)."""
        return self.world.end - self.inputs["guard_steps"] * self.rungs[0]

    def copies_of(self, plant_id):
        out = []
        for c, entry in enumerate(self.table):
            copy = make_copy(c, entry["seed"], self.world, self.exact_results[plant_id, c])
            copy.judged = sum(1 for t in copy.times if t <= self.cut())
            out.append(copy)
        return out

    def finish(self):
        with context():
            self.copies = self.copies_of(None)
            self.planted = {p["id"]: self.copies_of(p["id"]) for p in self.series_plants()}
            self.scales = self.make_scales()
            self.sizing = self.make_sizing()
            self.margins = self.make_margins()

    def make_scales(self):
        """READOUTS section 2, over the copies and samples."""
        scales = {"t_events": self.world.end}
        row = "S" if self.world.kind == "reactions" else "R"
        books = ("xi_1", "xi_2") if row == "S" else ("made", "lost")

        def largest(function):
            return max(function(copy.series, i) for copy in self.copies for i in range(len(self.world.samples)))

        for name in self.copies[0].series:
            if name == f"n_{row}_c":
                terms = (*books, "moved")
            elif name == f"n_{row}_o":
                terms = ("moved",)
            else:
                scales[name] = largest(lambda s, i, n=name: abs(s[n][i]))
                continue
            scales[name] = largest(
                lambda s, i, n=name, t=terms: abs(s[n][i]) + abs(s[n][0]) + sum((abs(s[b][i]) for b in t), ZERO)
            )
        return scales

    # -- the sizing (SPEC section 5)

    def kind_of(self, readout):
        return "event" if readout == "t_events" else "row"

    def run_series(self, readout, first, rung_index):
        runs = [self.split_results[first, rung_index, c] for c in range(len(self.copies))]
        if readout == "t_events":
            return [run[0][: copy.judged] for run, copy in zip(runs, self.copies, strict=True)]
        return [run[1][readout][1:] for run in runs]

    def reference_series(self, readout, copies=None):
        copies = copies or self.copies
        if readout == "t_events":
            return [copy.times[: honest.judged] for copy, honest in zip(copies, self.copies, strict=True)]
        return [copy.series[readout][1:] for copy in copies]

    def reference_accuracy(self, readout):
        if readout == "t_events":
            return max(Decimal(upward(copy.time_accuracy)) for copy in self.copies)
        return max(Decimal(upward(copy.accuracy[readout])) for copy in self.copies)

    def bound(self, readout, rung):
        return pooled.rounding(self.kind_of(readout), self.world.end / rung, self.scales[readout])

    def family_statistics(self, family, entry, offset):
        """CRITERIA 3.3 for one readout, over the registered rungs (0) or the retry's (1)."""
        readout = entry["readout"]
        count = len(self.rungs)
        indices = range(offset, offset + count)
        return pooled.statistics(
            [self.all_rungs[i] for i in indices],
            self.kind_of(readout),
            self.world.end,
            self.scales[readout],
            entry["p"],
            [self.run_series(readout, family["first"], i) for i in indices],
            self.reference_series(readout),
            self.reference_accuracy(readout),
        )

    def make_sizing(self):
        sizing = {}
        for family in self.families:
            sizing[family["id"]] = {
                entry["readout"]: {
                    "first": self.family_statistics(family, entry, 0),
                    "retry": self.family_statistics(family, entry, 1),
                }
                for entry in self.judged["S"]
            }
        sizing["mutant"] = {}
        plant = self.lie_plant()
        if plant:
            family = self.families_of(plant)[0]
            chosen = range(len(self.rungs) - 3, len(self.rungs))
            errors = []
            for i in chosen:
                runs = [
                    self.lie_results[i, c][0][: copy.judged] for c, copy in enumerate(self.copies)
                ]
                errors.append(pooled.rms(runs, self.reference_series("t_events")))
            sizing["mutant"][family["id"]] = {
                "E": errors,
                "q": pooled.slope([self.rungs[i] for i in chosen], errors),
            }
        first, second = self.firsts()
        sizing["pair"] = {}
        for readout in self.judged["orders_differ"]:
            apart = pooled.rms(self.run_series(readout, first, 0), self.run_series(readout, second, 0))
            sizing["pair"][readout] = self._against(apart, readout)
        sizing["rungs"] = {}
        for readout in self.judged.get("rungs_differ", ()):
            for family in self.families:
                apart = pooled.rms(
                    self.run_series(readout, family["first"], 0), self.run_series(readout, family["first"], 1)
                )
                sizing["rungs"].setdefault(family["id"], {})[readout] = self._against(apart, readout)
        return sizing

    def _against(self, apart, readout):
        threshold = pooled.RESOLUTION * self.bound(readout, self.rungs[0])
        return {"rms": apart, "threshold": threshold, "ratio": apart / threshold}

    # -- the plants (CRITERIA section 6)

    def make_margins(self):
        margins = []
        for plant in self.plants:
            for family in self.families_of(plant) if plant["kind"] != "record" else [None]:
                for wanted in plant["must_fail"]:
                    margins.append(self.margin(plant, family, *wanted))
        return margins

    def margin(self, plant, family, check_class, check):
        entry = {
            "plant": plant["id"],
            "family": family["id"] if family else None,
            "check": check,
            "no_margin": bool(plant.get("no_margin", False)),
        }
        if plant["kind"] == "record":
            distance, tolerance = self._record_plant(plant, check_class, check)
        elif check_class == "R":
            distance, tolerance = self._exact_times_plant(plant)
        else:
            tolerance = self.sizing[family["id"]][check]["first"]["tau"]
            if plant["kind"] == "engine":
                distance = max(self.sizing["mutant"][family["id"]]["E"])
            elif plant["id"] in declared.SERIES_PLANTS:
                distance = self._planted_distance(plant["id"], check)
            else:
                distance = self.shift(family)
        entry.update(distance=distance, expected_tolerance=tolerance)
        if entry["no_margin"]:
            entry["margin"] = None
            entry["reason"] = "class E: the trace is equal or it is not, and its distance is a count of entries"
        else:
            entry["margin"] = distance / tolerance
        return entry

    def shift(self, family):
        """P4: ten times the family's expected tolerance of the event times."""
        return 10 * self.sizing[family["id"]]["t_events"]["first"]["tau"]

    def _planted_distance(self, plant_id, check):
        copies = self.planted[plant_id]
        if check != "t_events":
            return pooled.rms(self.reference_series(check, copies), self.reference_series(check))
        honest, other = [], []
        for copy, planted in zip(self.copies, copies, strict=True):
            count = min(copy.judged, len(planted.times))
            honest.append(copy.times[:count])
            other.append(planted.times[:count])
        return pooled.rms(other, honest)

    def _exact_times_plant(self, plant):
        """P5: the judged event the farthest from its exact time, at the rung with the least bound."""
        distance = max(
            abs(a - b)
            for copy, other in zip(self.copies, self.planted[plant["id"]], strict=True)
            for a, b in zip(copy.times[: copy.judged], other.times, strict=False)
        )
        return distance, self.bound("t_events", self.rungs[0]) + self.reference_accuracy("t_events")

    def _record_plant(self, plant, check_class, check):
        """P6, P7, P13, P14, P15 on the references' rows of copy 0 (no record exists yet), and P8."""
        copy = self.copies[0]
        series, samples = copy.series, self.world.samples
        if check_class == "E":
            middle = copy.judged // 2
            kept = [
                (channel, tuple(counts))
                for i, (channel, counts) in enumerate(zip(copy.channels, copy.counts_after, strict=True))
                if i != middle
            ]
            wanted = [(copy.channels[k], tuple(copy.counts_after[k])) for k in range(copy.judged)]
            differs = sum(1 for k, entry in enumerate(wanted) if k >= len(kept) or kept[k] != entry)
            return Decimal(differs), ZERO
        kind, name = check.split(" ", 1)
        edited = self._edited(plant, series)
        if kind == "start":
            value = series[name][0]
            return abs(edited[name][0] - value), 4 * pooled.UNIT * abs(value)
        best = None
        for i, sample in enumerate(samples):
            if sample == 0:
                continue
            honest_sum, terms = self.identity(name, series, i)
            planted_sum, _ = self.identity(name, edited, i)
            tolerance = 16 * (sample / self.rungs[0] + 1) * pooled.UNIT * terms
            candidate = (abs(planted_sum - honest_sum), tolerance)
            if best is None or candidate[0] / candidate[1] > best[0] / best[1]:
                best = candidate
        return best

    def _edited(self, plant, series):
        """The record plant's change, as READOUTS names the edited leaves."""
        edits = {
            "xi_2 x (1 + 1e-3)": ("scale", ("xi_2",), exact(1e-3)),
            "lost x (1 + 1e-3)": ("scale", ("lost",), exact(1e-3)),
            "n_S_o at its t = 0 value at every sample": ("hold", ("n_S_o",), None),
            "n_R_o at its t = 0 value at every sample": ("hold", ("n_R_o",), None),
            "n_Pi at its t = 0 value at every sample (a product not released)": ("hold", ("n_Pi",), None),
            "n_N, n_M, n_Pi and free at t = 0 each x 1.01 (a start amount wrong)": (
                "start", ("n_N", "n_M", "n_Pi", "free"), exact(1.01)),
            "n_N and n_M at their t = 0 values at every sample (the monomer neither made nor consumed)": (
                "hold", ("n_N", "n_M"), None),
        }
        action, names, number = edits[plant["change"]]
        edited = dict(series)
        for name in names:
            values = series[name]
            if action == "scale":
                edited[name] = [v * (1 + number) for v in values]
            elif action == "hold":
                edited[name] = [values[0]] * len(values)
            else:
                edited[name] = [values[0] * number, *values[1:]]
        return edited

    def identity(self, name, series, i):
        """The sum of one identity's terms at sample i, and the sum of their absolute values."""
        total = size = ZERO
        for readout, coefficient, when in self.inputs["identities"][self.name][name]:
            term = exact(coefficient) * series[readout][i if when == "t" else 0]
            total += term
            size += abs(term)
        return total, size
