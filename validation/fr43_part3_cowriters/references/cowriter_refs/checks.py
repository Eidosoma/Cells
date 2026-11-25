"""SPEC section 9's checks on one world, in the references' own arithmetic.

A check passes where its residual is at most its bound.  Each copy carries its own, and copy 0 carries the
world's beside them (their names begin with `world:`).
"""

from __future__ import annotations

from decimal import Decimal

from . import pooled, taylor
from .build import ZERO, context, make_thresholds, relaxation_residual
from .declared import copy_fmol, exact

ROW_ACCURACY = Decimal("1e-11")
EVENT_ACCURACY = {"S": Decimal("1e-11"), "R": Decimal("1e-15")}
RELAXATION = Decimal("1e-30")
GUARD_CLEARANCE = Decimal("1e-9")
ORDER_WINDOW = Decimal("0.4")
MUTANT_WINDOW = Decimal("0.25")
LEAST_MARGIN = 10 * (1 - Decimal("1e-9"))
LEAST_RATIO = Decimal(10)
DOMAIN = Decimal(-1)


def entry(name, residual, bound):
    return {"name": name, "residual": float(residual), "bound": float(bound), "passes": bool(residual <= bound)}


def event_class(world_set):
    return "R" if "t_events" in world_set.judged["R"] else "S"


def published(values):
    """The doubles a list of decimals is published as, read back exactly."""
    return [Decimal(float(value)) for value in values]


def copy_checks(world_set, c, draws_differ):
    """The checks of one copy."""
    copy, world, inputs, name = world_set.copies[c], world_set.world, world_set.inputs, world_set.name
    out = []
    with context():
        out.append(entry("draws: entries that differ from the declared table", draws_differ, 0))
        times = published(copy.times)
        limit = EVENT_ACCURACY[event_class(world_set)] * world.end
        out.append(entry("accuracy of the events' times against SPEC 4", copy.time_accuracy, limit))
        out.append(
            entry(
                "two methods: events' times, s",
                max((abs(a - b) for a, b in zip(times, copy.times, strict=True)), default=ZERO) + copy.time_difference,
                copy.time_accuracy,
            )
        )
        if event_class(world_set) == "R":
            closed = taylor.decimal_times(world, make_thresholds(world_set.u1[c]))
            integrated = world_set.integrated[c]
            if len(closed) != len(integrated) or len(closed) != len(times):
                raise ArithmeticError("the closed form and the integration count different events")
            out.append(
                entry(
                    "closed form: integrated event times against the decimal sums, s",
                    max(abs(a - b) for a, b in zip(integrated, closed, strict=True)),
                    limit,
                )
            )
            out.append(
                entry(
                    "closed form: published event times against the decimal sums, s",
                    max(abs(a - b) for a, b in zip(times, closed, strict=True)),
                    limit,
                )
            )
        values = {readout: published(series) for readout, series in copy.series.items()}
        for readout in sorted(copy.series):
            rounded = max(abs(a - b) for a, b in zip(values[readout], copy.series[readout], strict=True))
            scale = world_set.scales[readout]
            out.append(entry(f"accuracy of {readout} against SPEC 4", copy.accuracy[readout], ROW_ACCURACY * scale))
            out.append(
                entry(f"two methods: {readout}, fmol", rounded + copy.differences[readout], copy.accuracy[readout])
            )
        for identity in inputs["judged"][name]["identities"]:
            worst = max(abs(world_set.identity(identity, values, i)[0]) for i in range(len(world.samples)))
            terms = inputs["identities"][name][identity]
            least = min(abs(exact(k)) * world_set.scales[readout] for readout, k, _ in terms)
            out.append(entry(f"identity {identity}: published values, fmol", worst, ROW_ACCURACY * least))
        out.append(entry("start: the worst row or book over its bound", start_residual(world_set, values), 1))
        cut, clear = world_set.cut(), GUARD_CLEARANCE * world.end
        nearest = min(abs(t - cut) for t in copy.times)
        out.append(entry("guard: 1e-9 T over the least distance of an event from T - g h_1", clear / nearest, 1))
        counts = inputs["minimum_events"][name]
        out.append(entry("minimum events per copy over K", Decimal(counts["per_copy"]) / copy.judged, 1))
        out.append(entry("events to T against the pairs of draws", len(copy.times), inputs["draws"]["pairs_per_copy"] - 1))
        if copy.affinities is not None:
            for affinity in ("x", "y"):
                out.append(entry(f"domain: the largest {affinity} over the run", copy.affinities[affinity], DOMAIN))
        if "running" in inputs["judged"][name]:
            out.append(entry("running check: the worst bound over its book", running_residual(world_set, values), 1))
    return out


def start_residual(world_set, values):
    """READOUTS section 4's start on the published values: the worst |value - declared| / (4 u |declared|)."""
    inputs, name = world_set.inputs, world_set.name
    worst = ZERO
    machines = inputs["worlds"][name].get("gene", {}).get("machines_copies")
    for readout, declared_value in inputs["start"][name].items():
        if declared_value == "machines_copies * copy_fmol":
            expected = machines * copy_fmol()
        else:
            expected = exact(declared_value)
        apart = abs(values[readout][0] - expected)
        if expected == 0:
            if apart != 0:
                return Decimal("Infinity")
            continue
        worst = max(worst, apart / (4 * pooled.UNIT * abs(expected)))
    if set(values) != set(inputs["start"][name]):
        raise ValueError("the start does not name the world's rows and books")
    if name in inputs["machines_start"]:
        declared_start = inputs["machines_start"][name]
        complexes = declared_start["stage_complexes_fmol"]
        if len(complexes) != world_set.world.stages or any(complexes):
            raise ValueError("the stage complexes do not start empty")
        if declared_start["free_fmol"] != "machines_copies * copy_fmol":
            raise ValueError("the machines do not start free")
    return worst


def running_residual(world_set, values):
    """CRITERIA 3.2's running check on the references' own extents, at every rung: the worst ratio."""
    multiple = exact(world_set.inputs["judged"][world_set.name]["running"]["multiple"])
    carried = {"xi_1": "X", "xi_2": "Y", "moved": "S node"}
    last = len(world_set.world.samples) - 1
    worst = ZERO
    for rung in world_set.rungs:
        steps = world_set.world.end / rung
        for readout, identity in carried.items():
            _, size = world_set.identity(identity, values, last)
            bound = 16 * (steps + 1) * pooled.UNIT * size
            worst = max(worst, multiple * bound / abs(values[readout][last]))
    return worst


def world_checks(world_set):
    """The checks of the world, carried by copy 0."""
    inputs, name = world_set.inputs, world_set.name
    out = []
    with context():
        out.append(
            entry(
                "world: closed-form relaxation of the transfer, relative",
                relaxation_residual(name, world_set.block),
                RELAXATION,
            )
        )
        total = sum(copy.judged for copy in world_set.copies)
        out.append(
            entry("world: minimum events in all over their number", Decimal(inputs["minimum_events"][name]["total"]) / total, 1)
        )
        for plant_id, copies in world_set.planted.items():
            worst = max(
                [copy.time_accuracy / (EVENT_ACCURACY[event_class(world_set)] * world_set.world.end) for copy in copies]
                + [
                    copy.accuracy[readout] / (ROW_ACCURACY * world_set.scales[readout])
                    for copy in copies
                    for readout in copy.accuracy
                ]
            )
            out.append(entry(f"world: planted {plant_id}: the worst accuracy over SPEC 4's bound", worst, 1))
        named = set(world_set.judged["at_rounding"])
        for family in world_set.families:
            for item in world_set.judged["S"]:
                readout, p = item["readout"], item["p"]
                got = world_set.sizing[family["id"]][readout]["first"]
                label = f"world: sizing {family['id']} {readout}"
                if readout in named:
                    out.append(entry(f"{label}: used differences, named at rounding", got["used"], pooled.NEEDED - 1))
                else:
                    out.append(entry(f"{label}: used differences, negated", -got["used"], -pooled.NEEDED))
                    if got["q"] is not None:
                        out.append(entry(f"{label}: |q - p|", abs(got["q"] - p), ORDER_WINDOW))
                out.append(entry(f"{label}: E over tau", got["E"] / got["tau"], 1))
        for family_id, mutant in world_set.sizing["mutant"].items():
            out.append(entry(f"world: P3 {family_id}: |q - (p - 1)|", abs(mutant["q"] - 1), MUTANT_WINDOW))
        for readout, pair in world_set.sizing["pair"].items():
            out.append(entry(f"world: pair {readout}: 10 over the ratio", LEAST_RATIO / pair["ratio"], 1))
        for family_id, rows in world_set.sizing["rungs"].items():
            for readout, pair in rows.items():
                out.append(entry(f"world: rungs {family_id} {readout}: 10 over the ratio", LEAST_RATIO / pair["ratio"], 1))
        for margin in world_set.margins:
            label = f"world: plant {margin['plant']} {margin['family'] or 'record'} {margin['check']}"
            if margin["no_margin"]:
                out.append(entry(f"{label}: entries that differ, negated", -margin["distance"], -1))
            else:
                out.append(entry(f"{label}: 10 (1 - 1e-9) over the margin", LEAST_MARGIN / margin["margin"], 1))
    return out
