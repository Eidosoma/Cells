"""Portable inputs for the native per-moving-ion dynamic-junction law."""

import copy
from dataclasses import dataclass, replace

import numpy as np

from cells.core import betse_spatial_spec as base
from cells.core.specs import ConfigError, _fields, _number
from cells.numerics import betse_junction as kernel
from cells.processes import junction_gate

MODEL_ID = kernel.MODEL_ID
SOLVER_ID = base.SOLVER_ID
Control = kernel.Control


@dataclass(frozen=True)
class BetseJunctionModel(base.BetseSpatialModel):
    junction: tuple
    junction_block: tuple
    moving_order: tuple[int, ...]
    junction_initial: tuple


@dataclass(frozen=True)
class Change(base.Change):
    junction: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(base.Experiment):
    changes: tuple[Change, ...] = ()


def definition_arrays(model):
    state, active = base.definition_arrays(model)
    layout = kernel.validate_layout(
        kernel.Layout(
            active,
            junction_gate.Parameters(*(np.asarray(v, dtype=float) for v in model.junction)),
            np.asarray(model.junction_block, dtype=float),
            np.asarray(model.moving_order, dtype=np.int64),
        )
    )
    return kernel.initial_state(state, layout, model.junction_initial), layout


def to_dict(spec):
    if type(spec.experiment) is not Experiment:
        raise ConfigError("Dynamic BETSE junctions require their own experiment")
    e, m = spec.experiment, spec.model
    raw = base.to_dict(
        replace(
            spec,
            experiment=base.Experiment(
                e.end_time,
                e.observation_times,
                tuple(base.Change(c.time, c.pump, c.channel) for c in e.changes),
            ),
        )
    )
    raw["model"].update(
        id=MODEL_ID,
        junction=dict(
            zip(junction_gate.Parameters._fields, map(base.portable, m.junction), strict=True)
        ),
        junction_block=base.portable(m.junction_block),
        moving_order=list(m.moving_order),
    )
    raw["model"]["initial"]["junction_open"] = base.portable(m.junction_initial)
    for target, change in zip(raw["experiment"].get("changes", []), e.changes, strict=True):
        target["junction"] = list(change.junction)
    return raw


def parse(data):
    raw = copy.deepcopy(data)
    m = _fields(
        raw["model"],
        {
            "id",
            "species",
            "tissue",
            "pump",
            "sodium_index",
            "potassium_index",
            "pump_available",
            "channel_permeability",
            "initial",
            "junction",
            "junction_block",
            "moving_order",
        },
        "BETSE dynamic junction model",
    )
    if m["id"] != MODEL_ID:
        raise ConfigError("Require the dynamic BETSE junction model")
    junction = _fields(m.pop("junction"), set(junction_gate.Parameters._fields), "junction")
    block, order = m.pop("junction_block"), m.pop("moving_order")
    initial = _fields(m["initial"], {*base.INITIAL_FIELDS, "junction_open"}, "initial state")
    opening = initial.pop("junction_open")
    m["id"] = base.MODEL_ID
    events = []
    e = raw["experiment"]
    if isinstance(e, dict) and "changes" in e:
        if type(e["changes"]) is not list:
            raise ConfigError("BETSE changes require a list")
        for change in e["changes"]:
            _fields(change, {"time", "pump", "channel", "junction"}, "BETSE intervention")
            values = change.pop("junction")
            if type(values) is not list:
                raise ConfigError("Junction controls require per-patch fractions")
            events.append(tuple(_number(v, "junction fraction") for v in values))
    parsed = base.parse(raw, horizon_s=512e-6)
    if parsed.experiment.end_time > 512e-6:
        raise ConfigError("This dynamic-junction runtime is bounded to 512 us")
    model = BetseJunctionModel(
        **{k: getattr(parsed.model, k) for k in base.BetseSpatialModel.__dataclass_fields__},
        junction=tuple(
            base.immutable(base.array(junction[k], k).tolist())
            for k in junction_gate.Parameters._fields
        ),
        junction_block=base.immutable(base.array(block, "junction_block").tolist()),
        moving_order=base.immutable(base.array(order, "moving_order", "int").tolist()),
        junction_initial=base.immutable(base.array(opening, "junction_open").tolist()),
    )
    try:
        _, layout = definition_arrays(model)
        for values in events:
            value = np.asarray(values)
            if (
                value.shape != layout.junction_block.shape
                or np.any((value < 0) | (value > 1))
                or not np.array_equal(value, value[layout.active.tissue.partner])
            ):
                raise ValueError("Junction controls must be reciprocal per-patch [0,1] fractions")
    except (ValueError, TypeError, IndexError, ArithmeticError) as error:
        raise ConfigError("Invalid BETSE junction definition: " + str(error)) from error
    experiment = Experiment(
        parsed.experiment.end_time,
        parsed.experiment.observation_times,
        tuple(
            Change(c.time, c.pump, c.channel, values)
            for c, values in zip(parsed.experiment.changes, events, strict=True)
        ),
    )
    return replace(parsed, model=model, experiment=experiment)
