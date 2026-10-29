"""Complete scheduled calcium/fuel bath interface probes, with original clocks.

Unchanged carrier controls add 1/2-ns accepted boundaries. The full 8-us bath
schedule and native ramp widths are retained; these probes qualify interfaces.
"""

from functools import lru_cache

import numpy as np

from cells.core import surface_open_calcium_bath_events_spec as calcium_schema
from cells.core import surface_open_calcium_energy_bath_events_spec as energy_schema
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import surface_open_calcium_bath_events as calcium
from cells.models import surface_open_calcium_energy_bath_events as energy
from cells.numerics.fixed_step import rk4_checked_step
from validation.tissue import open_calcium_bath_fixtures as fixtures

PREFIX_DT = 1e-9
OWNERS = {
    "calcium": (calcium_schema, calcium, 36),
    "energy": (energy_schema, energy, 40),
}


def definition(family):
    raw = fixtures.definition(family, "overlap", depleted=family == "energy")
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
    schema, model, _ = OWNERS[family]
    spec = parse_spec(definition(family))
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    held = type(controls)(*(value[0] for value in controls))

    def valid_stage(value, parameters, active):
        return model.domain_valid(value, parameters, active, xp=np)

    valid_stage.with_control = lambda value, control, parameters, active: (
        model.control_domain_valid(value, control, parameters, active, xp=np)
    )
    evolved, valid = rk4_checked_step(
        lambda value, *args: model.rhs(value, *args, xp=np),
        valid_stage,
        state,
        PREFIX_DT,
        held,
        layout,
        layout.active,
    )
    assert valid
    evolved = model.STATE_TYPE(*(np.asarray(value) for value in evolved))
    model.check_values(evolved, spec)
    point = Checkpoint(evolved, layout, PREFIX_DT, 1, event_index(spec, PREFIX_DT))
    return schema, model, spec, point
