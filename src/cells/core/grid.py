"""An indexed event-split clock without horizon-length arrays."""

import math
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from cells.core.resources import trace_bytes
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, _integer
from cells.models.registry import get_model


def refinement_times(spec):
    """Validate immutable optional numerical boundaries independently of events."""
    points = getattr(spec.execution, "refinement_times", ())
    if type(points) is not tuple or len(points) > spec.execution.max_steps:
        raise ConfigError("refinement_times must be an immutable sequence within max_steps")
    previous = 0.0
    for time in points:
        if (
            type(time) not in (int, float)
            or not math.isfinite(time)
            or not previous < time < spec.experiment.end_time
        ):
            raise ConfigError("refinement_times must strictly increase inside the horizon")
        previous = time
    return points


def require_refinement_model(spec):
    """Public execution must not silently refine discrete/native clock models."""
    if refinement_times(spec) and getattr(get_model(spec.model), "MODEL_ID", None) != (
        "resolved_cotransport_water@1"
    ):
        raise ConfigError("refinement_times currently require resolved_cotransport_water@1")


@dataclass(frozen=True, init=False)
class EventGrid(Sequence):
    """Exact union of float i*dt, events, numerical refinement, zero and end.

    Only off-nominal boundaries and their global indices are stored. Binary searches
    compare actual products rather than rounding a time/dt quotient.
    Internal model projections may use this clock during inherited validation;
    public execution additionally calls require_refinement_model().
    """

    dt: float
    end: float
    last_nominal: int
    extras: tuple[float, ...]
    extra_indices: tuple[int, ...]

    def __init__(self, spec):
        end, dt = spec.experiment.end_time, spec.execution.dt
        count = end / dt
        if not math.isfinite(count) or count > spec.execution.max_steps:
            raise ConfigError("Nominal integration grid exceeds max_steps")
        last = max(0, math.ceil(count) - 1)
        while last > 0 and last * dt >= end:
            last -= 1
        extras, indices = [], []
        points = sorted({*(c.time for c in spec.experiment.changes), *refinement_times(spec)})
        for t in points:
            if t == 0 or t == end:
                continue
            lo, hi = 0, last + 1
            while lo < hi:
                mid = (lo + hi) // 2
                if mid * dt < t:
                    lo = mid + 1
                else:
                    hi = mid
            if lo <= last and lo * dt == t:
                continue
            indices.append(lo + len(extras))
            extras.append(t)
        if last + 1 + len(extras) > spec.execution.max_steps:
            raise ConfigError("Event-split integration grid exceeds max_steps")
        for key, value in (
            ("dt", dt),
            ("end", end),
            ("last_nominal", last),
            ("extras", tuple(extras)),
            ("extra_indices", tuple(indices)),
        ):
            object.__setattr__(self, key, value)

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
        return self.end if nominal == self.last_nominal + 1 else nominal * self.dt

    def exact_index(self, time):
        index = bisect_left(self, time)
        if index == len(self) or self[index] != time:
            raise ConfigError("Checkpoints require an exact accepted integration boundary")
        return index

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
    require_refinement_model(spec)
    grid = EventGrid(spec)
    base = trace_bytes(spec, 0, 0)
    per_step = trace_bytes(spec, 1, 0) - base
    if base > spec.execution.max_trace_bytes:
        raise ConfigError("Checkpoint storage estimate exceeds max_trace_bytes")
    width = min(window_steps, max(1, (spec.execution.max_trace_bytes - base) // per_step))
    model = get_model(spec.model)
    for times in grid.windows(0, width):
        model.check_steps(spec, np.diff(times), control_values(spec, times[:-1]))
    return grid
