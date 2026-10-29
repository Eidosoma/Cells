"""Public open-calcium probes with the full 8-us control recipe retained.

The unchanged 1/2-ns control boundaries permit short interface/restart checks.
They do not qualify the later controls, biological timescales, or GPU execution.
"""

from functools import lru_cache

import numpy as np

from cells.core import surface_open_calcium_energy_spec as energy_schema
from cells.core import surface_open_calcium_spec as calcium_schema
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import surface_open_calcium as calcium
from cells.models import surface_open_calcium_energy as energy
from cells.numerics.fixed_step import rk4_checked_step
from validation.tissue import open_calcium_fixtures as fixtures

PREFIX_DT = 1e-9
OWNERS = {
    "calcium": (calcium_schema, calcium, 34),
    "energy": (energy_schema, energy, 38),
}


def definition(family):
    raw = fixtures.definition(family, "mixed", depleted=family == "energy")
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
    """A guarded NumPy step from the actual open world, with all ledgers."""
    schema, model, _ = OWNERS[family]
    spec = parse_spec(definition(family))
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    held = type(controls)(*(v[0] for v in controls))

    def valid_stage(value, parameters, active):
        return model.domain_valid(value, parameters, active, xp=np)

    valid_stage.with_control = lambda value, control, parameters, active: (
        model.control_domain_valid(value, control, parameters, active, xp=np)
    )
    evolved, valid = rk4_checked_step(
        lambda y, *args: model.rhs(y, *args, xp=np),
        valid_stage,
        state,
        PREFIX_DT,
        held,
        layout,
        layout.active,
    )
    assert valid
    # The shared guarded step selects its accepted result with JAX. Host
    # accounting consumes NumPy arrays, as it does in the ordinary runner.
    evolved = model.STATE_TYPE(*(np.asarray(value) for value in evolved))
    model.check_values(evolved, spec)
    point = Checkpoint(evolved, layout, PREFIX_DT, 1, event_index(spec, PREFIX_DT))
    return schema, model, spec, point
