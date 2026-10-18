"""Ordinary execution and complete checkpoints for dynamic spatial junctions."""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import numpy as np

from cells.core.betse_junction_spec import MODEL_ID, SOLVER_ID, Control, definition_arrays
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.models import betse_spatial as base
from cells.numerics import betse_junction as kernel
from cells.numerics import betse_spatial as passive
from cells.processes import junction_gate

OBSERVER_ID = "betse_spatial_dynamic_junction_accepted_fields@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "native_order_positive_inventory_reciprocal_junction_retained_on_failure@1"
BATCH_CAPACITIES = base.BATCH_CAPACITIES
STATE_AXES = base.STATE_AXES | {"junction_open": ["membrane_slot"]}
STATE_TYPE = NamedTuple(
    "BetseJunctionState", [(k, object) for k in (*base.STATE_TYPE._fields, "junction_open")]
)
LAYOUT_TYPE = NamedTuple(
    "BetseJunctionLayout",
    [
        (k, object)
        for k in (
            *base.LAYOUT_TYPE._fields,
            "junction_threshold",
            "junction_minimum",
            "junction_block",
            "moving_order",
        )
    ],
)
Observations = make_dataclass(
    "BetseJunctionObservations",
    [(k, np.ndarray) for k in ("times", *STATE_TYPE._fields, *passive.Field._fields)],
    frozen=True,
)

check_checkpoint = base.check_checkpoint
integration_steps = base.integration_steps


def active_state(state):
    return base.STATE_TYPE(*(getattr(state, k) for k in base.STATE_TYPE._fields))


def flatten(state):
    return STATE_TYPE(**base.flatten(state.active)._asdict(), junction_open=state.junction_open)


def unflatten(state):
    return kernel.State(base.unflatten(active_state(state)), state.junction_open)


def initial_values(spec):
    state, p = definition_arrays(spec.model)
    _, layout = base.initial_values(spec)
    return flatten(state), LAYOUT_TYPE(*layout, *p.junction, p.junction_block, p.moving_order)


def parameters(spec, layout):
    return kernel.Layout(
        base.parameters(spec, layout),
        junction_gate.Parameters(layout.junction_threshold, layout.junction_minimum),
        layout.junction_block,
        layout.moving_order,
    )


def checked_step(state, dt, control, parameters, active_mask):
    result, _, valid = kernel.step(unflatten(state), parameters, dt, control)
    return flatten(result), valid


def batch_signature(model):
    return *base.batch_signature(model), len(model.moving_order)


def working_size(spec):
    state, p = definition_arrays(spec.model)
    return 4 * (
        sum(v.size for v in jax.tree.leaves((state, p))) + p.active.tissue.boundary_values.size**2
    )


def check_steps(spec, steps, controls):
    base._check_fixed_steps(spec, steps)
    if not isinstance(controls, Control):
        raise ConfigError("BETSE controls must name pump, channel and junction availability")
    for values in controls:
        if (
            values.shape != (len(steps), spec.execution.membrane_capacity)
            or not np.isfinite(values).all()
            or np.any((values < 0) | (values > 1))
        ):
            raise ConfigError("Invalid BETSE per-patch intervention fractions")
    partner = np.asarray(spec.model.tissue[passive.Layout._fields.index("partner")])
    if not np.array_equal(controls.junction, controls.junction[:, partner]):
        raise ConfigError("Junction controls must be reciprocal")


def check_values(state, spec):
    diagnostics = base.check_values(active_state(state), spec)
    gate = np.asarray(state.junction_open)
    expected = np.asarray(state.m_gate)
    if gate.shape != expected.shape or gate.dtype != expected.dtype:
        raise ConfigError("BETSE state shape/precision differs: junction_open")
    if not np.isfinite(gate).all() or np.any((gate < 0) | (gate > 1)):
        raise NumericalError("BETSE junction gate is outside [0,1]")
    partner = np.asarray(spec.model.tissue[passive.Layout._fields.index("partner")])
    if not np.array_equal(gate, gate[..., partner]):
        raise NumericalError("BETSE junction gates are not reciprocal")
    return diagnostics


def observe_history(times, history, layout, requested, spec):
    observed = base.observe_history(times, active_state(history), layout, requested, spec)
    indices = np.searchsorted(times, observed.times)
    return Observations(**vars(observed), junction_open=np.asarray(history.junction_open)[indices])


def summarize(history, diagnostics, spec):
    return base.summarize(active_state(history), diagnostics, spec) | dict(
        model=MODEL_ID,
        solver=SOLVER_ID,
        state_fields=list(STATE_TYPE._fields),
        intervention_scope="held pump/channel/junction fractions on completed step boundaries",
        junction_clock="one outer dt per moving ion, in explicit moving_order",
        junction_blocking="multiply stored opening after each implicit update",
        qualification_scope="synthetic native dynamic junction compatibility through 512 us",
    )
