"""D283's one same-instant predicate, in a module with no engine imports, so the clock
(cells.execution.grid) and every operator's grid check share it without an import cycle.

Two times are one instant to within the rounding of two products of declared steps (each product
and each step's binary value round by half an ulp; ROUNDING_ULPS holds them with margin). On steps
of dt, a time within that tolerance of k * dt *is* that point (on_grid)."""

import math

ROUNDING_ULPS = 4

# The refusals' words for a time that on_grid does not admit (every operator's grid check).
ON_THE_GRID = f"on the clock's grid (within {ROUNDING_ULPS} ulps of k * dt)"


def same_instant(a, b):
    """Whether a and b differ by at most ROUNDING_ULPS ulps of the larger."""
    return abs(a - b) <= ROUNDING_ULPS * math.ulp(max(abs(a), abs(b)))


def on_grid(time, dt):
    """D283's one predicate for steps of dt: the point k * dt that `time` is, exactly or within the
    same-instant tolerance, or None. Every check that asks whether a time is on the step grid asks
    this. The clock snaps such a time, as an event, onto the point, and the runner's applied copy
    (cells.execution.grid.applied_definition) declares it there, so every event map reads it."""
    point = round(time / dt) * dt
    return point if point == time or same_instant(point, time) else None
