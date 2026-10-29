"""Full calcium/fuel bath epochs: guarded1ns INIT, unchanged8us SIM recipes.

The1/2ns carrier boundaries qualify public interfaces without shortening the
physical recipe or changing pulse widths. Full trajectories remain separate.
"""

from copy import deepcopy
from functools import lru_cache

import numpy as np

from cells.core import open_calcium_bath_phase_handoff as bridge
from cells.core import surface_open_calcium_bath_epoch_spec as calcium_schema
from cells.core import surface_open_calcium_energy_bath_epoch_spec as energy_schema
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import surface_open_calcium_bath_epoch as calcium
from cells.models import surface_open_calcium_energy_bath_epoch as energy
from cells.numerics.fixed_step import rk4_checked_step
from cells.tissue_phase import prepare_request
from tests.surface_open_calcium_bath_fixtures import OWNERS as SCHEDULED
from tests.surface_open_calcium_bath_fixtures import PREFIX_DT, definition

OWNERS = {
    "calcium": (calcium_schema, calcium, 36),
    "energy": (energy_schema, energy, 40),
}


@lru_cache
def source_checkpoint(family):
    raw = definition(family)
    raw["model"]["phase"] = "INIT"
    spec = parse_spec(raw)
    model = SCHEDULED[family][1]
    state, layout = model.initial_values(spec)
    table = control_values(spec, [0.0])
    held = type(table)(*(row[0] for row in table))

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
    point = Checkpoint(
        evolved,
        layout,
        PREFIX_DT,
        EventGrid(spec).exact_index(PREFIX_DT),
        event_index(spec, PREFIX_DT),
    )
    return spec, point


def target_simulation(family):
    raw = definition(family)
    for kind in ("membrane_controls", "channel_controls", "pump_controls"):
        for group in raw["experiment"][kind]:
            for row in group["schedule"]:
                row["availability"] *= 0.6
    return raw


@lru_cache
def _request(family):
    source, point = source_checkpoint(family)
    return dict(
        kind=bridge.REQUEST_KIND,
        policies=deepcopy(OWNERS[family][0].POLICIES),
        source=bridge.capture_source(source, point),
        simulation=target_simulation(family),
    )


def request(family):
    return deepcopy(_request(family))


@lru_cache
def prepared(family):
    return prepare_request(request(family))
