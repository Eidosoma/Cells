"""A pool's switch path, and the channel schedule it drives: pure functions over recorded arrays.

A pool is one event-driven walk that reads nothing outside itself. An observable of its assembly
(assembly_pool/observables.py) gives a value after each committed event, and a composed file gives
each value a level in [0, 1]. So a pool's level in one world is a path: piecewise constant and
right-continuous, with a switch at each event that changes the level. The level of a switch is the
one after its event, and it holds until the next switch. Most events are no switch.

A driven channel's availability is base(t) x level(t), where base is the schedule the ionic
definition declares for it. Both factors are right-continuous, so the product is a schedule too,
with a change at every base change and every switch. It is ordinary data: the clock takes a change
at any time and splits the step that holds it (execution/grid.py), so no switch time is rounded to
a step.

**Near misses (D283).** The clock refuses a change that misses a point of its grid by more than
rounding but by at most a millionth of the step. missed_point finds one by asking the clock itself,
so a driver can refuse it by name before any run. `moved` declares such a switch at the point it
misses, where a driver's caller asks for that; the caller records the shift.

Nothing here runs a pool or reads a file.
"""

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import NamedTuple

import numpy as np

from cells.definitions.specs import ConfigError
from cells.execution.grid import EventGrid, near_miss, same_instant

ANY_STEPS = 2**53  # A clock read here has no step limit of its own; step_count's caller compares.


class Trace(NamedTuple):
    """The recorded rows of a pool run ("events"), in order, each [row, world]. A row commits an
    event where its event is not negative, and its state is the state after that event."""

    time_s: np.ndarray
    occupied: np.ndarray
    bonds: np.ndarray
    free: np.ndarray
    event: np.ndarray


def joined(chunks):
    """One Trace of a run's recorded chunks, each the kernel's five arrays in its order."""
    columns = zip(*([np.asarray(a) for a in chunk] for chunk in chunks), strict=True)
    return Trace(*(np.concatenate(column) for column in columns))


def initial_fields(pool):
    """{state field: value} of a pool's assembly and free material at time 0."""
    return dict(
        occupied=pool.initial_mask, bonds=pool.initial_bonds, free=pool.initial_free_trimers
    )


# ------------------------------------------------------------------ the path


@dataclass(frozen=True)
class SwitchPath:
    """A pool's level in one world, from time 0 to `end`: levels[k] holds from times[k] on, after
    counts[k] committed events. times[0] is 0; every later point is a switch."""

    times: tuple[float, ...]
    levels: tuple[float, ...]
    counts: tuple[int, ...]
    end: float
    events: int  # All the committed events, the ones that switch nothing among them.

    def __post_init__(self):
        if (
            not len(self.times) == len(self.levels) == len(self.counts) >= 1
            or self.times[0] != 0.0
            or any(b <= a for a, b in zip(self.times, self.times[1:], strict=False))
            or self.times[-1] > self.end
            or not all(0.0 <= v <= 1.0 for v in self.levels)
        ):
            raise ConfigError("A switch path starts at 0, increases within its end, in [0, 1]")

    @property
    def switches(self):
        """((time, level, event count), ...) of its switches."""
        return tuple(zip(self.times[1:], self.levels[1:], self.counts[1:], strict=True))

    def at(self, time):
        """The level at a time (right-continuous)."""
        return self.levels[bisect_right(self.times, time) - 1]

    def exposure(self):
        """The integral of the level over [0, end] (s): the fsum of level x duration."""
        ends = (*self.times[1:], self.end)
        return math.fsum(
            level * (b - a) for level, a, b in zip(self.levels, self.times, ends, strict=True)
        )


def switch_path(law, levels, initial, trace, world, end):
    """The SwitchPath of one world of a pool's run.

    law: the observable; levels: {each of its values: its level}; initial: initial_fields' state at
    time 0; trace: the run's Trace; world: its index; end: the run's horizon (s)."""
    rows = np.flatnonzero(trace.event[:, world] >= 0)
    states = []
    for name in law.reads:
        after = getattr(trace, name)[rows, world]
        states.append(np.concatenate((np.asarray([initial[name]], dtype=after.dtype), after)))
    values = np.asarray([levels[value] for value in law.values], dtype=np.float64)
    level = values[law.evaluate(*states, xp=np)]
    times = np.concatenate(([0.0], trace.time_s[rows, world]))
    kept = np.flatnonzero(np.concatenate(([True], level[1:] != level[:-1])))
    return SwitchPath(
        tuple(times[kept].tolist()),
        tuple(level[kept].tolist()),
        tuple(kept.tolist()),  # Row k is the state after k events.
        float(end),
        len(rows),
    )


def moved(path, points):
    """The path with each switch at a time of `points` declared at its point instead. Where two
    then share a time the later one's level stands, and a point with no change of level goes."""
    kept = []
    for time, level, count in zip(path.times, path.levels, path.counts, strict=True):
        time = points.get(time, time)
        while kept and kept[-1][0] >= time:
            kept.pop()
        if not kept or kept[-1][1] != level:
            kept.append((time, level, count))
    times, levels, counts = zip(*kept, strict=True)
    return replace(path, times=times, levels=levels, counts=counts)


# ------------------------------------------------------------------ the driven schedule


@dataclass(frozen=True)
class ChannelDrive:
    """One channel population's driven schedule: the (time, availability) schedule its definition
    declares, times a pool's level."""

    channel: str
    base: tuple[tuple[float, float], ...]
    path: SwitchPath

    def declared(self, time):
        """The declared availability at a time (right-continuous)."""
        return self.base[bisect_right([t for t, _ in self.base], time) - 1][1]

    def schedule(self):
        """((time, availability), ...): base x level at every base change and every switch."""
        times = sorted({*(t for t, _ in self.base), *self.path.times})
        return tuple((t, self.declared(t) * self.path.at(t)) for t in times)

    def clashes(self):
        """((switch time, base change), ...) that are one instant to the clock but not one number:
        two changes of one channel there, which the clock's own copy could not hold apart."""
        return tuple(
            (s, t)
            for s in self.path.times[1:]
            for t, _ in self.base
            if s != t and same_instant(s, t)
        )


# ------------------------------------------------------------------ the clock


def clock(spec, times=()):
    """The clock of a definition with changes at these times alone. Its step, horizon and fine
    windows are the definition's own."""
    experiment = SimpleNamespace(
        end_time=spec.experiment.end_time, changes=[SimpleNamespace(time=t) for t in times]
    )
    execution = replace(spec.execution, max_steps=ANY_STEPS)
    return EventGrid(replace(spec, experiment=experiment, execution=execution))


def step_count(spec, times=()):
    """The steps of the definition's clock with changes at these times alone, none a near miss."""
    return len(clock(spec, times)) - 1


def missed_point(spec, time):
    """The point of the definition's clock that a change at `time` misses (a near miss, which the
    clock refuses), or None where the clock takes it."""
    try:
        clock(spec, (time,))
    except ConfigError:
        points = clock(spec)
        i = bisect_left(points, time)
        step = points[i] - points[i - 1]
        for point in (points[i - 1], points[i]):
            if near_miss(time, point, step):
                return point
        raise
    return None


def repeated_seeds(seeds):
    """((i, j), ...) of the pools, by position, that share a seed: their walks in one world would be
    one walk."""
    first, out = {}, []
    for j, seed in enumerate(seeds):
        if seed in first:
            out.append((first[seed], j))
        first.setdefault(seed, j)
    return tuple(out)
