"""One accepted INIT step and explicit new SIM bath inputs; no trajectory claim."""

from copy import deepcopy
from functools import lru_cache

import numpy as np

from cells.core import surface_active_bath_epoch_spec as active_epoch
from cells.core import surface_active_bath_events_spec as active_schema
from cells.core import surface_bath_phase_handoff as bridge
from cells.core import surface_passive_bath_epoch_spec as passive_epoch
from cells.core import surface_passive_bath_events_spec as passive_schema
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.state import Checkpoint
from cells.models import surface_active_bath_epoch as active
from cells.models import surface_passive_bath_epoch as passive
from cells.numerics.fixed_step import rk4_step
from validation.transport import surface_bath_events_fixtures as ordinary

FAMILIES = ("passive", "active")
CASES = ("changed", "empty", "negative", "retarget")
OWNERS = {
    "passive": (passive_schema, passive_epoch, passive, 14),
    "active": (active_schema, active_epoch, active, 21),
}


@lru_cache
def source_checkpoint(family):
    schema, _, model, _ = OWNERS[family]
    spec = schema.parse(ordinary.definition(family, "init"))
    zero, p = model.scheduled.initial_values(spec)
    table = control_values(schema.owner_spec(spec), [0.0])
    control = type(table)(*(v[0] for v in table))
    state = rk4_step(
        lambda y, *args: model.scheduled.rhs(y, *args, xp=np),
        zero,
        ordinary.DT,
        control,
        p,
        p.active,
    )
    point = Checkpoint(
        state,
        p,
        ordinary.DT,
        EventGrid(spec).exact_index(ordinary.DT),
        event_index(spec, ordinary.DT),
    )
    return spec, point


@lru_cache
def _request(family, case):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    _, schema, _, _ = OWNERS[family]
    source, point = source_checkpoint(family)
    target = ordinary.definition(family, case if case in ("empty", "negative") else "overlap")
    if case == "retarget":
        target["model"]["bath_site_ids"] = ["bath"]
    if case == "changed":
        for key, groups in target["experiment"].items():
            if key.endswith("_controls"):
                for group in groups:
                    for row in group["schedule"]:
                        row["availability"] *= 0.6
    return dict(
        kind=bridge.REQUEST_KIND,
        policies=deepcopy(schema.POLICIES),
        source=bridge.capture_source(source, point),
        simulation=target,
    )


def request(family, case="changed"):
    return deepcopy(_request(family, case))


@lru_cache
def prepared(family, case="changed"):
    return bridge.prepare(request(family, case))
