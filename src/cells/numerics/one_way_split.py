"""The step rule for one-way amounts, shared by FR-42's labels and FR-50's one-way records.

docs: the FR-49/50/51 design note §2.3 (/mnt/workspaces/Cells/fr49-51-design-20261123/DESIGN.md),
ruled by D327; the registered protocol fr50-one-way-records-v1 §1 (validation/fr50/REGISTRATION.md).

A route's flux is J = J+ - J-, each direction linear in one end's concentration at a fixed voltage.
Over one step:
- **the uncorrected amounts** F_t and B_t are the trapezoid of each direction's fluxes at the step's
  two ends, 0.5 dt (J(start) + J(end)), or under the Euler IMEX `weight` times the start's, its one
  explicit stage's weight dt a[last, 0] >= 0 (`step_one_way_amounts`). ARS(2,2,2)'s explicit
  weights (delta, 1 - delta, 0), delta < 0, would make a stage-weighted amount negative where a flux
  falls by more than 59% within a step, so the stages are not used;
- **the gap** to the booked net, the net record's change over the step: g = net - (F_t - B_t),
  measured before any correction (D327);
- **the closed amounts** F_t + max(g, 0) and B_t + max(-g, 0) (`close_one_way`). Their difference
  is the booked net at rounding, and both stay >= 0;
- **the relative gap** r = |g| / max(F_t + B_t, |g|), 0 where all three are 0, in [0, 1]
  (`one_way_gap_relative`). r = 1 flags a booked net with no one-way flow.

The labels' three copies of this rule (surface_pump_v3.step_transfers and the passive-route and
transporter kinds' label_transfers) call `step_one_way_amounts` and `close_one_way` with their
operations in the order they had, so the labelled worlds' programs are unchanged (the design note's
§2.6). Kinds import them through cells.modules.
"""

from typing import NamedTuple


class OneWaySplit(NamedTuple):
    """One step's one-way amounts, each in the shape of its fluxes."""

    forward: object  # F_t + max(g, 0): closed to the net.
    backward: object  # B_t + max(-g, 0).
    gap: object  # g = net - (F_t - B_t), before the correction.
    forward_uncorrected: object  # F_t.
    backward_uncorrected: object  # B_t.


def trapezoid(start, end, dt):
    """One direction's amount over a step: the trapezoid of its fluxes at the step's two ends."""
    return 0.5 * dt * (start + end)


def step_one_way_amounts(start, end, dt, *, weight=None):
    """(F_t, B_t): the uncorrected amounts of a step whose ends' fluxes are `start` and `end`, each
    (forward, backward); under the Euler IMEX, `weight` times the start's, and `end` is unread."""
    if weight is None:
        return trapezoid(start[0], end[0], dt), trapezoid(start[1], end[1], dt)
    return weight * start[0], weight * start[1]


def close_one_way(forward, backward, net, *, xp):
    """The amounts closed to the booked net, on the side the gap's sign gives."""
    gap = net - (forward - backward)
    return OneWaySplit(
        forward + xp.maximum(gap, 0.0), backward + xp.maximum(-gap, 0.0), gap, forward, backward
    )


def one_way_gap_relative(split, *, xp):
    """r = |g| / max(F_t + B_t, |g|), and 0 where F_t, B_t and g are all 0: in [0, 1]."""
    size = xp.abs(split.gap)
    scale = xp.maximum(split.forward_uncorrected + split.backward_uncorrected, size)
    return xp.where(scale > 0, size / xp.where(scale > 0, scale, 1.0), 0.0)
