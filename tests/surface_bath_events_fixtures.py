"""Public bath probes retaining the complete 8-us schedule and physical owners.

The added 1/2-ns accepted boundaries permit short restart checks. Neither the
bath windows nor their ramp widths are compressed to make these probes faster.
"""

from functools import lru_cache

import numpy as np

from cells.core import surface_active_bath_events_spec as active_schema
from cells.core import surface_passive_bath_events_spec as passive_schema
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import surface_active_bath_events as active
from cells.models import surface_passive_bath_events as passive
from cells.numerics.fixed_step import rk4_checked_step
from validation.transport import surface_bath_events_fixtures as fixtures

PREFIX_DT = 1e-9
OWNERS = {
    "passive": (passive_schema, passive, 14),
    "active": (active_schema, active, 21),
}


def definition(family):
    raw = fixtures.definition(family)
    schedule = raw["experiment"]["membrane_controls"][0]["schedule"]
    value = schedule[0]["availability"]
    schedule.extend(dict(time=t, availability=value) for t in (PREFIX_DT, 2 * PREFIX_DT))
    schedule.sort(key=lambda row: row["time"])
    raw["experiment"]["observation_times"] = sorted(
        {*raw["experiment"]["observation_times"], PREFIX_DT, 2 * PREFIX_DT}
    )
    return raw


@lru_cache
def prefix(family):
    """A genuine guarded NumPy prefix; separate from runner/GPU qualification."""
    schema, model, _ = OWNERS[family]
    spec = parse_spec(definition(family))
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    held = type(controls)(*(v[0] for v in controls))
    evolved, valid = rk4_checked_step(
        lambda y, *args: model.rhs(y, *args, xp=np),
        lambda y, *args: model.domain_valid(y, *args, xp=np),
        state,
        PREFIX_DT,
        held,
        layout,
        layout.active,
    )
    assert valid
    model.check_values(evolved, spec)
    point = Checkpoint(evolved, layout, PREFIX_DT, 1, event_index(spec, PREFIX_DT))
    return schema, model, spec, point
