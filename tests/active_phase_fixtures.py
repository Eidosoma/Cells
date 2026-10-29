"""Short evolved active INIT evidence for public interface checks only."""

from copy import deepcopy
from functools import lru_cache

import numpy as np

from cells.core import active_membrane_profile_phase_handoff as handoff
from cells.core import surface_active_profile_epoch_spec as epoch
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import surface_active_profile_interventions as active
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_active_profile_interventions_dispatch import definition


@lru_cache
def source_checkpoint():
    raw = definition("INIT")
    raw["model"]["interventions"] = []
    raw["execution"].update(
        jit=False, intervention_capacity=0, intervention_target_capacity=0, max_steps=4
    )
    raw["experiment"].update(end_time=0.125e-6, observation_times=[0.0, 0.125e-6])
    for kind in ("membrane", "junction", "channel", "pump"):
        for row in raw["experiment"][kind + "_controls"]:
            row["schedule"] = row["schedule"][:1]
    spec = parse_spec(raw)
    state, layout = active.initial_values(spec)
    grid = EventGrid(spec)
    assert len(grid) - 1 == 2
    for i in range(len(grid) - 1):
        table = control_values(spec, [grid[i]])
        control = type(table)(*(value[0] for value in table))
        state = rk4_step(
            lambda y, *args: active.rhs(y, *args, xp=np),
            state,
            grid[i + 1] - grid[i],
            control,
            layout,
            layout.active,
        )
    checkpoint = Checkpoint(state, layout, grid[-1], len(grid) - 1, event_index(spec, grid[-1]))
    return spec, checkpoint


def request():
    source, point = source_checkpoint()
    target = definition("SIM")
    target["execution"].update(jit=False, dt=1e-9, max_steps=4)
    target["experiment"].update(end_time=2e-9, observation_times=[0.0, 1e-9, 2e-9])
    for kind in ("membrane", "junction", "channel", "pump"):
        for row in target["experiment"][kind + "_controls"]:
            row["schedule"] = [dict(time=0.0, availability=0.5)]
    event = next(row for row in target["model"]["interventions"] if row["kind"] == "Na_mem")
    event.update(
        profiles=["Selected"],
        spatial=None,
        source_function="None",
        on_s=0.5e-9,
        off_s=1.5e-9,
        change_s=8e-9,
    )
    target["model"]["interventions"] = [event]
    return dict(
        kind=handoff.REQUEST_KIND,
        policies=deepcopy(epoch.POLICIES),
        source=handoff.capture_source(source, point),
        simulation=target,
    )


@lru_cache
def prepared():
    return handoff.prepare(request())
