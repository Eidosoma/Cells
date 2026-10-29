"""Short complete ionic/calcium/fuel INIT probes; no full transient qualification."""

from copy import deepcopy
from functools import lru_cache

import numpy as np

from cells.core import owned_barrier_phase_handoff as handoff
from cells.core import surface_active_barrier_epoch_spec as ionic_schema
from cells.core import surface_calcium_barrier_epoch_spec as calcium_schema
from cells.core import surface_calcium_energy_barrier_epoch_spec as energy_schema
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import surface_active_barrier_epoch as ionic
from cells.models import surface_calcium_barrier_epoch as calcium
from cells.models import surface_calcium_energy_barrier_epoch as energy
from cells.numerics.fixed_step import rk4_step
from cells.tissue_phase import prepare_request
from tests.owned_barrier_dispatch_fixtures import DT, definition
from validation.topology.owned_calcium_profile_interventions_fixtures import _scaled

OWNERS = {
    "ionic": (ionic_schema, ionic, 20),
    "calcium": (calcium_schema, calcium, 35),
    "energy": (energy_schema, energy, 39),
}


@lru_cache
def source_checkpoint(family):
    _, model, _ = OWNERS[family]
    scheduled = model.scheduled
    raw = definition(family, "INIT")
    raw["execution"]["jit"] = False
    spec = parse_spec(raw)
    state, layout = scheduled.initial_values(spec)
    table = control_values(spec, [0.0])
    control = type(table)(*(value[0] for value in table))
    evolved = rk4_step(
        lambda y, *args: scheduled.rhs(y, *args, xp=np),
        state,
        DT,
        control,
        layout,
        layout.active,
    )
    checkpoint = Checkpoint(
        evolved, layout, DT, EventGrid(spec).exact_index(DT), event_index(spec, DT)
    )
    return spec, checkpoint


@lru_cache
def _request(family, case):
    schema, _, _ = OWNERS[family]
    source, point = source_checkpoint(family)
    target = definition(family, "SIM")
    target["execution"]["jit"] = False
    if case == "empty":
        target["model"]["intervention"] = None
    elif case == "changed":
        for name, rows in target["experiment"].items():
            if name.endswith("_controls"):
                for row in rows:
                    key = "controls" if "controls" in row else "schedule"
                    row[key] = [_scaled(value, 0.5) for value in row[key]]
    else:
        raise ValueError(case)
    return dict(
        kind=handoff.REQUEST_KIND,
        policies=deepcopy(schema.POLICIES),
        source=handoff.capture_source(source, point),
        simulation=target,
    )


def request(family, case="changed"):
    return deepcopy(_request(family, case))


@lru_cache
def prepared(family, case="changed"):
    return prepare_request(request(family, case))
