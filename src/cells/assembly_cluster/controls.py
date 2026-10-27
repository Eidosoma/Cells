"""Immutable external controls on the union of ionic and assembly event clocks."""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.schedule import control_values


class ScheduledControl(NamedTuple):
    times: object  # Change times followed by an infinite end sentinel.
    values: object  # Existing model control PyTree, with a leading change axis.


class ChannelOwners(NamedTuple):
    fixed: object  # Cell index for each immobile channel slot.
    mobile: object  # Cell index for each membrane patch, shared by mobile populations.


def modulate(control, opening, owners):
    """Assembly scales conduction only; gates, protein motion and injury keep their laws."""
    if isinstance(owners, ChannelOwners):
        return control._replace(
            channel=control.channel * opening[owners.fixed],
            mobile_channel=control.mobile_channel * opening[owners.mobile][None, :],
        )
    return control._replace(channel=control.channel * opening[owners])


def prepare(spec):
    """Retain the original scalar control path for constant-input definitions."""
    times = np.array([change.time for change in spec.experiment.changes])
    values = control_values(spec, times)
    if len(times) == 1:
        return type(values)(*(v[0] for v in values))
    return ScheduledControl(np.r_[times, np.inf], values)


def at(schedule, time):
    """Right-continuous control; a change at an endpoint drives the next segment."""
    index = jnp.searchsorted(schedule.times, time, side="right") - 1
    return jax.tree.map(lambda v: v[index], schedule.values), schedule.times[index + 1]


def extra_boundaries(spec, through=None):
    """Count exact off-grid splits once, including simultaneous control changes."""
    end = spec.experiment.end_time if through is None else through
    dt = spec.execution.dt
    return sum(
        0 < change.time <= end and change.time != round(change.time / dt) * dt
        for change in spec.experiment.changes
    )


def storage_bytes(spec):
    count = len(spec.experiment.changes)
    if count == 1:
        return 0
    first = control_values(spec, [0.0])
    return 8 * (count + 1) + count * sum(v.nbytes for v in first)
