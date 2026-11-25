"""An indexed event-split clock without horizon-length arrays.

The clock (EventGrid) is the coarse lattice i * dt from 0 to its last point before the end, the end
itself, and the events: schedule changes (doses, writes and operators' schedules among them). An
event equal to a lattice point is that point; any other splits the step it falls in, at its own
time.

Fine windows (execution.fine_windows, definitions/fine_window_spec.py; C, D235;
docs/LONG_DURATION_MODE_DESIGN.md §4.2) refine the lattice inside each declared window. Between
each pair of neighbouring coarse points i * dt and (i + 1) * dt in a window the clock adds the
m - 1 fine points (m * i + r) * h, r = 1, ..., m - 1, where h is the fine dt and m = dt / h a whole
number. Every coarse point stays a boundary, bit for bit, so a window adds boundaries and moves
none: an event or an observation on the coarse grid keeps its exact time inside a window. A
window's ends are coarse points exactly, so the steps beside it are whole coarse steps, and the
fine steps are h to within the rounding of the products: no window makes a tiny step. The clock
keeps one entry per window and per event.

One rule for every clock, with fine windows or without (D283): an event within the clock's
same-instant tolerance (same_instant, ROUNDING_ULPS) of a point of the clock, fine, coarse or the
end, *is* that point. It snaps there and adds no step: a decimal 1.25e-06 declared beside
10 * 1.25e-7 = 1.2499999999999999e-06 changes the controls at that point, where before it split
off a step of one ulp. An event past that tolerance but within NEAR_MISS of a point's step is
refused as an author's near miss (near_miss below), and every other event splits the step it falls
in, at its own time. The clock records each snap, declared and applied (snapped); the runner runs
an applied copy of the definition (applied_definition), and the declared definition keeps its
fingerprint.
"""

import math
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from cells.definitions.specs import ConfigError, _integer
from cells.execution.resources import trace_bytes
from cells.execution.schedule import control_values
from cells.numerics.clock_instants import (  # noqa: F401 (D283's one predicate)
    ROUNDING_ULPS,
    on_grid,
    same_instant,
)
from cells.registry.models import get_model

# The near-miss band (D283): an event more than ROUNDING_ULPS from a point of the clock but within
# NEAR_MISS of the step it would split off is refused. Such a sub-step, a millionth of its step or
# less, is never an intended event: it is a computed time that missed the grid (0.1 * 3 against
# 3 * 0.1 is within the tolerance and snaps; 1800.3000001 at dt 0.1 is in the band). Both of D283's
# scans, every saved run definition and the judged worlds' builders, found no event in the band.
NEAR_MISS = 1e-6


def near_miss(time, point, step):
    """Whether `time` misses `point` by more than the same-instant tolerance but by at most
    NEAR_MISS of `step`, the step it would split (the band, refused)."""
    return not same_instant(point, time) and abs(time - point) <= NEAR_MISS * step


# The keys under which an experiment declares event times: every schedule's "time", a bridge's
# "start_time" (bridge_closure@1) and an insertion's "onset_time" (membrane_insertion@1 and @2).
# An explicit set, never a *_time pattern: experiment.end_time is no event. A key missed here
# fails closed: the applied copy keeps its event off the point, and applied_definition refuses it.
EVENT_TIME_KEYS = frozenset({"time", "start_time", "onset_time"})


def _snap_times(value, snap, pairs):
    """`value` with every number under an EVENT_TIME_KEYS key replaced by snap(it) where snap gives
    a point (recording (declared, applied)); lists and dicts walked, everything else kept."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in EVENT_TIME_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                applied = snap(float(v))
                if applied is not None and applied != v:
                    pairs.append((float(v), applied))
                    v = applied
            else:
                v = _snap_times(v, snap, pairs)
            out[k] = v
        return out
    if isinstance(value, list):
        return [_snap_times(v, snap, pairs) for v in value]
    return value


def applied_definition(spec):
    """(the applied copy of a parsed definition, its snaps): every event time of its experiment that
    its clock snaps (EventGrid(spec).snapped) replaced by the point, re-parsed. The runner runs
    this copy, so every control lookup, observation and operator sees the instant the clock steps
    at; the declared definition keeps its fingerprint, record and manifest. Without a snap, `spec`
    itself.

    The operators' own schedules are among these events (D283 stage 2): each operator reports its
    times (schedule_times) into the experiment's changes, and its grid check admits a time within
    the same-instant tolerance of k * dt (numerics.clock_instants.on_grid), which the clock snaps
    onto k * dt, so the copy declares it there."""
    from cells.definitions.specs import parse_spec

    grid = EventGrid(spec)
    snapped = dict(grid.snapped)
    rows = [t for t in spec.experiment.observation_times if grid.instant(t) != t]
    if not snapped and not rows:
        return spec, ()
    raw = spec.to_dict()
    pairs = [(t, grid.instant(t)) for t in rows]
    raw["experiment"] = _snap_times(raw["experiment"], snapped.get, pairs)
    if rows:  # A row declared at a snapped instant is that point's row.
        raw["experiment"]["observation_times"] = [
            grid.instant(t) for t in raw["experiment"]["observation_times"]
        ]
    applied = parse_spec(raw)
    if EventGrid(applied).snapped:
        raise ConfigError("The applied definition still holds an event to snap (D283)")
    return applied, tuple(sorted(set(pairs)))


GRID_ID = "zero_anchored_event_split"  # The run manifests' name for this clock.


def manifest_numerics(spec):
    """The clock's entries in a run manifest's numerics (records/io.py and records/window_io.py):
    its name, and with declared fine windows their method (numerics.fine_windows), so a manifest
    without the block keeps its bytes."""
    entries = {"grid": GRID_ID}
    windows = getattr(spec, "fine_windows", None)
    if windows is not None:
        entries["fine_windows"] = windows.method
    return entries


def require_scalar_path(spec, admitted):
    """Refuse declared fine windows off the scalar runner and its windows. admitted: the caller is
    that path (runner.timeline and windows._plan_windows_metadata pass the flag with which they
    admit the step-doubled energy check). The batch and vector paths size their work from
    end / dt, so version 1 refuses them, fail-closed."""
    if getattr(spec, "fine_windows", None) is not None and not admitted:
        raise ConfigError(
            "execution.fine_windows runs only through cells.execution.runner.run and the scalar "
            "windows (refused on this path)"
        )


@dataclass(frozen=True)
class FineSpan:
    """One declared fine window on the clock: the coarse steps that start at the coarse points
    first <= i < stop, each divided into `subdivision` fine steps of `fine_dt` (module docstring).
    `position` is the coarse point first's place among the lattice points; `shift` counts the fine
    points this window and every earlier one add."""

    first: int
    stop: int
    subdivision: int
    fine_dt: float
    position: int
    shift: int

    @property
    def size(self):
        """Its lattice points: the coarse point first and every point before the coarse point
        stop."""
        return self.subdivision * (self.stop - self.first)


def _coarse_point(time, dt, last, what):
    """The coarse index i <= last with i * dt == time exactly, or ConfigError naming the nearest."""
    lo, hi = 0, last + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if mid * dt < time:
            lo = mid + 1
        else:
            hi = mid
    if lo <= last and lo * dt == time:
        return lo
    near = [repr(i * dt) for i in (lo - 1, lo) if 0 <= i <= last]
    raise ConfigError(
        f"execution.fine_windows: {what} {time!r} is not a point of the coarse grid, i x "
        f"execution.dt exactly (the nearest: {' and '.join(near)})"
    )


def fine_spans(spec, dt, end, last):
    """The definition's fine windows as FineSpans on its coarse lattice (last: the last coarse
    index before the end), or ConfigError; () without the block."""
    block = getattr(spec, "fine_windows", None)
    if block is None:
        return ()
    h = block.dt
    m = round(dt / h)
    if m < 2 or not same_instant(m * h, dt):
        raise ConfigError(
            "execution.fine_windows dt must divide execution.dt into a whole number of fine "
            f"steps, at least 2 (execution.dt / dt = {dt / h!r})"
        )
    spans, shift, previous = [], 0, 0
    for window in block.windows:
        first = _coarse_point(window.start_time, dt, last, "a window's start")
        if window.end_time == end and (last + 1) * dt == end:
            stop = last + 1  # The run's end, itself a coarse point.
        else:
            stop = _coarse_point(window.end_time, dt, last, "a window's end")
        if not previous <= first < stop:
            raise ConfigError("execution.fine_windows windows must increase and not overlap")
        position = first + shift
        shift += (m - 1) * (stop - first)
        spans.append(FineSpan(first, stop, m, h, position, shift))
        previous = stop
    return tuple(spans)


@dataclass(frozen=True, init=False)
class EventGrid(Sequence):
    """Exact union of float i*dt, declared fine windows, events, zero and end.

    The nominal points are the lattice (module docstring): the coarse products i*dt and, inside a
    declared fine window, the fine products between them. Only the windows (spans, one FineSpan
    each), off-nominal boundaries (extras) and their global indices are stored. Binary searches
    compare actual products rather than rounding a time/dt quotient. Without fine windows a
    nominal point n is n*dt and last_nominal the last coarse index, as before; with them
    last_nominal is the last lattice point's place.
    """

    dt: float
    end: float
    last_nominal: int
    extras: tuple[float, ...]
    extra_indices: tuple[int, ...]
    spans: tuple[FineSpan, ...] = ()
    span_positions: tuple[int, ...] = ()
    snapped: tuple[tuple[float, float], ...] = ()  # D283: each snapped event (declared, applied).

    def __init__(self, spec):
        end, dt = spec.experiment.end_time, spec.execution.dt
        count = end / dt
        if not math.isfinite(count) or count > spec.execution.max_steps:
            raise ConfigError("Nominal integration grid exceeds max_steps")
        last = max(0, math.ceil(count) - 1)
        while last > 0 and last * dt >= end:
            last -= 1
        spans = fine_spans(spec, dt, end, last)
        nominal = last + 1 + (spans[-1].shift if spans else 0)  # Lattice points before the end.
        if spans and nominal > spec.execution.max_steps:
            raise ConfigError("Fine-windowed integration grid exceeds max_steps")
        for key, value in (
            ("dt", dt),
            ("end", end),
            ("last_nominal", nominal - 1),
            ("spans", spans),
            ("span_positions", tuple(s.position for s in spans)),
        ):
            object.__setattr__(self, key, value)
        extras, indices, snapped = [], [], []
        for t in sorted({c.time for c in spec.experiment.changes}):
            if t == 0 or t == end:
                continue
            lo, hi = 0, nominal
            while lo < hi:
                mid = (lo + hi) // 2
                if self._nominal(mid) < t:
                    lo = mid + 1
                else:
                    hi = mid
            if lo < nominal and self._nominal(lo) == t:
                continue
            point = self._near_point(t, lo)  # D283: its point, or None.
            if point is not None:
                snapped.append((t, point))
                continue
            indices.append(lo + len(extras))
            extras.append(t)
        if nominal + len(extras) > spec.execution.max_steps:
            raise ConfigError("Event-split integration grid exceeds max_steps")
        object.__setattr__(self, "extras", tuple(extras))
        object.__setattr__(self, "extra_indices", tuple(indices))
        object.__setattr__(self, "snapped", tuple(snapped))

    def __len__(self):
        return self.last_nominal + 2 + len(self.extras)

    def __getitem__(self, index):
        if type(index) is not int:
            raise TypeError("EventGrid supports scalar integer indexing, not array slices")
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        extra = bisect_left(self.extra_indices, index)
        if extra < len(self.extras) and self.extra_indices[extra] == index:
            return self.extras[extra]
        nominal = index - extra
        if nominal == self.last_nominal + 1:
            return self.end
        return self._windowed(nominal)[0] if self.spans else nominal * self.dt

    def _nominal(self, n):
        """Nominal point n, 0 <= n <= last_nominal."""
        return self._windowed(n)[0] if self.spans else n * self.dt

    def _windowed(self, n):
        """(nominal point n, whether it is a fine point) on a clock with fine windows."""
        k = bisect_right(self.span_positions, n) - 1
        if k >= 0:
            span = self.spans[k]
            offset = n - span.position
            if offset < span.size:
                q, r = divmod(offset, span.subdivision)
                i = span.first + q
                if r:
                    return (span.subdivision * i + r) * span.fine_dt, True
                return i * self.dt, False
            n -= span.shift  # A coarse point after window k: its coarse index.
        return n * self.dt, False

    def _point(self, n):
        """(point n of the lattice, or the end at last_nominal + 1; its kind)."""
        if n == self.last_nominal + 1:
            return self.end, "end"
        point, fine = self._windowed(n)
        return point, "fine" if fine else "coarse"

    def _near_point(self, t, lo):
        """D283: the point of the clock (fine, coarse or the end; the points either side of t,
        lo - 1 and lo) that the event t is within the same-instant tolerance, or None; an event in
        the near-miss band of the step it would split is refused, naming the point."""
        near = [self._point(n) for n in (lo - 1, lo) if 0 <= n <= self.last_nominal + 1]
        for point, _ in near:
            if same_instant(point, t):
                return point
        if len(near) == 2:
            step = near[1][0] - near[0][0]
            for point, kind in near:
                if near_miss(t, point, step):
                    raise ConfigError(
                        f"The clock: an event at {t!r} misses the {kind} point {point!r} by "
                        f"{abs(t - point)!r} s, at most {NEAR_MISS} of its step (a near miss, "
                        f"D283); declare it at {point!r} or clearly off it"
                    )
        return None

    def fine_window_record(self):
        """The declared fine windows as this clock runs them (a windowed run's resources): each
        window's start and end, its fine dt and subdivision, and the steps inside it, events
        included; and the clock's fine and coarse step totals."""
        rows = []
        for span in self.spans:
            start, stop = span.first * self.dt, span.stop * self.dt
            rows.append(
                dict(
                    start_time=start,
                    end_time=stop,
                    dt=span.fine_dt,
                    subdivision=span.subdivision,
                    steps=self.exact_index(stop) - self.exact_index(start),
                )
            )
        fine = sum(row["steps"] for row in rows)
        return dict(windows=rows, fine_steps=fine, coarse_steps=len(self) - 1 - fine)

    def exact_index(self, time):
        """The index of the point `time` is: equal, or within the same-instant tolerance (D283's
        one predicate, so a checkpoint or row declared at a snapped event's time finds its
        point)."""
        index = bisect_left(self, time)
        if index < len(self) and self[index] == time:
            return index
        for i in (index - 1, index):
            if 0 <= i < len(self) and same_instant(self[i], time):
                return i
        raise ConfigError("Checkpoints require an exact accepted integration boundary")

    def instant(self, time):
        """The point of the clock that `time` is (D283), or `time` itself where it is none."""
        try:
            return self[self.exact_index(time)]
        except ConfigError:
            return time

    def windows(self, start_step, window_steps):
        """Adjacent windows share one endpoint; a terminal continuation yields one row."""
        _integer(window_steps, "window_steps")
        _integer(start_step, "start_step", minimum=0, maximum=len(self) - 1)
        start = start_step
        while True:
            stop = min(start + window_steps, len(self) - 1)
            yield np.fromiter((self[i] for i in range(start, stop + 1)), dtype=np.float64)
            if stop == len(self) - 1:
                break
            start = stop


def checked_grid(spec, *, window_steps=1024):
    """Validate clock/method without requiring a full recording buffer.

    Used for portable checkpoint validation, not a promise about execution RSS.
    Execution policies make their own (larger) working-array reservation.
    """
    grid = EventGrid(spec)
    base = trace_bytes(spec, 0, 0)
    per_step = trace_bytes(spec, 1, 0) - base
    if base > spec.execution.max_trace_bytes:
        raise ConfigError("Checkpoint storage estimate exceeds max_trace_bytes")
    width = min(window_steps, max(1, (spec.execution.max_trace_bytes - base) // per_step))
    check = clock_checks(spec)
    for times in grid.windows(0, width):
        check(np.diff(times), times)
    return grid


def clock_checks(spec):
    """The model's step checks for the chunks of one definition's clock.

    Returns check(steps, times): times are a chunk's accepted boundaries and steps
    its integration steps. A model whose step checks read only the steps and the
    definition provides bind_step_checks(spec), the checks bound to the
    definition: what they read from it (for example rate bounds that build the
    layout) is then evaluated once for the whole clock, not once per chunk, and
    no chunk builds a control table (models/surface_pump.py). Any other model's
    check_steps gets each chunk's steps and control table.
    """
    model = get_model(spec.model)
    bind = getattr(model, "bind_step_checks", None)
    if bind is None:
        return lambda steps, times: model.check_steps(spec, steps, control_values(spec, times[:-1]))
    bound = bind(spec)
    return lambda steps, times: bound(steps)
