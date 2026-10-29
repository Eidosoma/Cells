"""Short evolved checkpoints for barrier phase contracts, not recovery histories."""

import importlib
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache

import numpy as np

from cells.core import joint_water_barrier_phase_handoff as handoff
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import initialise
from cells.numerics.fixed_step import rk4_step
from cells.tissue_phase import prepare_request
from tests.joint_water_barrier_dispatch_fixtures import DT, OWNERS, definition
from validation.topology.owned_calcium_profile_interventions_fixtures import _scaled


def components(family):
    if family not in OWNERS:
        raise ValueError(family)
    name = "surface_calcium_energy_water" + ("_repair" if family == "repair" else "")
    name += "_barrier_epoch"
    return (
        importlib.import_module("cells.core." + name + "_spec"),
        importlib.import_module("cells.models." + name),
    )


@lru_cache
def source_checkpoint(family):
    _, model, _ = OWNERS[family]
    spec = parse_spec(definition(family, "INIT"))
    point = initialise(spec)
    state = model.STATE_TYPE(*(np.asarray(v) for v in point.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in point.layout))
    table = control_values(spec, [0.0])
    control = type(table)(*(v[0] for v in table))
    evolved = rk4_step(
        lambda y, *args: model.rhs(y, *args, xp=np), state, DT, control, layout, layout.active
    )
    saved = replace(
        point,
        state=evolved,
        layout=layout,
        time=DT,
        step_index=EventGrid(spec).exact_index(DT),
        event_index=event_index(spec, DT),
    )
    validate_checkpoint(spec, saved)
    return spec, saved


@lru_cache
def _request(family, case):
    schema, _ = components(family)
    spec, point = source_checkpoint(family)
    target = definition(family)
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
        source=handoff.capture_source(spec, point),
        simulation=target,
    )


def request(family, case="changed"):
    return deepcopy(_request(family, case))


@lru_cache
def prepared(family, case="changed"):
    return prepare_request(request(family, case))
