"""One accepted full INIT step and a new SIM program, retaining8us/caps."""

from copy import deepcopy
from functools import lru_cache

import numpy as np

from cells.core import open_calcium_bath_phase_handoff as bridge
from cells.core import surface_open_calcium_bath_epoch_spec as calcium_epoch
from cells.core import surface_open_calcium_bath_events_spec as calcium_schema
from cells.core import surface_open_calcium_energy_bath_epoch_spec as fuel_epoch
from cells.core import surface_open_calcium_energy_bath_events_spec as fuel_schema
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.state import Checkpoint
from cells.models import surface_open_calcium_bath_epoch as calcium
from cells.models import surface_open_calcium_energy_bath_epoch as fuel
from cells.numerics.fixed_step import rk4_step
from validation.tissue import open_calcium_bath_fixtures as ordinary

FAMILIES = ordinary.FAMILIES
CASES = ("changed", "empty", "negative", "retarget")
OWNERS = dict(
    calcium=(calcium_schema, calcium_epoch, calcium, 36), energy=(fuel_schema, fuel_epoch, fuel, 40)
)


@lru_cache
def source_checkpoint(family):
    schema, _, model, _ = OWNERS[family]
    spec = schema.parse(ordinary.definition(family, "init"))
    zero, layout = model.scheduled.initial_values(spec)
    table = control_values(schema.owner_spec(spec), [0.0])
    control = type(table)(*(row[0] for row in table))
    state = rk4_step(
        lambda y, *args: model.scheduled.rhs(y, *args, xp=np),
        zero,
        ordinary.DT,
        control,
        layout,
        layout.active,
    )
    return spec, Checkpoint(
        state,
        layout,
        ordinary.DT,
        EventGrid(spec).exact_index(ordinary.DT),
        event_index(spec, ordinary.DT),
    )


def _scale(row):
    if isinstance(row, dict):
        return {key: value if key == "time" else _scale(value) for key, value in row.items()}
    if isinstance(row, list):
        return [_scale(value) for value in row]
    return row * 0.6 if isinstance(row, (int, float)) and not isinstance(row, bool) else row


@lru_cache
def _request(family, case):
    if family not in FAMILIES or case not in CASES:
        raise ValueError((family, case))
    _, schema, _, _ = OWNERS[family]
    source, point = source_checkpoint(family)
    target = ordinary.definition(family, case if case in ("empty", "negative") else "overlap")
    if case == "retarget":
        target["model"]["bath_site_ids"] = target["model"]["bath_site_ids"][:1]
    if case == "changed":
        for name, groups in target["experiment"].items():
            if name.endswith("_controls"):
                for group in groups:
                    key = "controls" if "controls" in group else "schedule"
                    group[key] = [_scale(row) for row in group[key]]
    assert source.experiment.end_time == target["experiment"]["end_time"] == ordinary.END
    assert source.execution.max_trace_bytes == target["execution"]["max_trace_bytes"]
    assert source.execution.max_steps == target["execution"]["max_steps"]
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
