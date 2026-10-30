"""Accepted ordinary intervals with explicitly owned junction/NaK blockers.

Setters run once at each original interval's left physical-time label. Their
result is held through RK stages and the right endpoint; the next event call
belongs to the next interval. This is not a native physiological loop clock.
Conductance/capacity controls change rates only: charge, geometry, voltage
boundaries and original chemical/electrical anchors are never reassigned.
"""

import math
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_loop as seals
from cells.core import physiology_tissue_step as tissue
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.state import Checkpoint
from cells.models import physiology_block_control_view as blocks
from cells.models import physiology_permeability_view as view

KIND = "cells.physiology_block_interval@1"
CLOCK = "original_grid_left_label_held_through_right_endpoint@1"
ENERGY_RATE_ATOL_PJ_S = 1e-10


@dataclass(frozen=True, slots=True)
class BlockCheckpoint:
    numeric: Checkpoint
    tissue_binding: object
    component: object
    binding: blocks.Binding
    block_state: blocks.BlockState
    events_enabled: bool
    origin_step_index: int
    identity: str


@dataclass(frozen=True, slots=True)
class BlockStepResult:
    checkpoint: BlockCheckpoint
    preparation: blocks.PreparedControl
    trial: tissue.RK4Trial
    admission: object


class BlockStepRejected(NumericalError):
    def __init__(
        self, reason, *, source, stage, preparation=None, trial=None, control_failure=None
    ):
        super().__init__("Blocked tissue interval refused at " + stage + ": " + str(reason))
        self.source, self.stage = source, stage
        self.preparation = preparation
        self.trial = None if trial is None else view._immutable_tree(trial)
        self.control_failure = control_failure


def _control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(np.asarray(value[0]) for value in table))


def record(point):
    if type(point) is not BlockCheckpoint:
        raise ValueError("Require the complete block-control checkpoint")
    payload = dict(
        kind=KIND,
        clock_policy=CLOCK,
        source_definition_sha256=point.binding.source_definition_sha256,
        numeric_identity=seals._checkpoint_identity(point.numeric),
        tissue_binding_identity=point.tissue_binding.identity,
        component_identity=seals._component_identity(point.component),
        block_binding_identity=point.binding.identity,
        block_state_identity=seals._arrays_identity(point.block_state),
        events_enabled=point.events_enabled,
        origin_step_index=point.origin_step_index,
        completed_event_calls=point.numeric.step_index - point.origin_step_index,
    )
    return payload | dict(identity=seals._digest(payload))


def _seal(point):
    return replace(point, identity=record(point)["identity"])


def validate(spec, point):
    if type(point) is not BlockCheckpoint or type(point.numeric) is not Checkpoint:
        raise ValueError("Require the complete typed block/numeric checkpoint")
    if point.identity != record(point)["identity"]:
        raise ValueError("Block checkpoint association changed")
    if type(point.events_enabled) is not bool or (
        type(point.origin_step_index) is not int
        or not 0 <= point.origin_step_index <= point.numeric.step_index
    ):
        raise ValueError("Require an explicit enable flag and original interval origin")
    if type(spec.model) not in view.IMPLEMENTATIONS:
        raise ValueError("Require one of the four exact ordinary tissue families")
    grid = EventGrid(spec)
    validate_checkpoint(spec, point.numeric, times=grid)
    units.restore_binding(units.binding_record(point.tissue_binding), spec)
    component_step.validate_state(point.component, point.tissue_binding.component)
    blocks.restore(blocks.record(point.binding), spec, point.tissue_binding)
    # Validate the carried buffer without firing the next event. A terminal or
    # pre-event checkpoint must remain restorable even if its next call refuses.
    carried = blocks.prepare(
        spec,
        point.tissue_binding,
        point.binding,
        point.block_state,
        _control(spec, point.numeric.time),
        time_s=point.numeric.time,
        events_enabled=False,
    )
    permeability = units.component_permeability(point.component, point.tissue_binding)
    if not np.array_equal(
        permeability.current_m_s > 0, np.asarray(point.numeric.layout.membrane_permeability) > 0
    ):
        raise ValueError("Blocked intervals must retain original passive route support")
    # Check an endpoint, not a hypothetical next timestep. Original method and
    # turnover limits apply to the actual interval only when advance is called.
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    runtime = point.numeric.layout._replace(membrane_permeability=permeability.current_m_s)
    changed = view._admission_spec(spec, permeability.current_m_s)
    _, projected = implementation.initial_values(changed)
    for name in runtime._fields:
        if not np.array_equal(getattr(runtime, name), getattr(projected, name)):
            raise ValueError("Mapped permeability changes another physical layout field")
    implementation.check_values(point.numeric.state, changed)
    if not implementation.control_domain_valid(
        point.numeric.state, carried.effective_control, runtime, runtime.active, xp=np
    ):
        raise ValueError("Checkpoint fails its actual carried-control field/domain")
    return grid


def initialise(spec, numeric, tissue_binding, component, binding, block_state, *, events_enabled):
    """Declare a complete pre-event boundary; no implicit setter call occurs."""
    if type(numeric) is not Checkpoint:
        raise ValueError("Require an accepted ordinary numeric checkpoint")
    validate_checkpoint(spec, numeric, times=EventGrid(spec))
    frozen = Checkpoint(
        view._immutable_tree(numeric.state),
        view._immutable_tree(numeric.layout),
        float(numeric.time),
        numeric.step_index,
        numeric.event_index,
    )
    point = _seal(
        BlockCheckpoint(
            frozen,
            tissue_binding,
            component,
            binding,
            view._immutable_tree(blocks._state(block_state, binding)),
            events_enabled,
            numeric.step_index,
            "",
        )
    )
    validate(spec, point)
    return point


def restore(saved, spec, numeric, tissue_binding, component, binding, block_state):
    """Restore a sealed association; this does not authenticate past authorship."""
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require a complete block interval record")
    point = initialise(
        spec,
        numeric,
        tissue_binding,
        component,
        binding,
        block_state,
        events_enabled=saved.get("events_enabled"),
    )
    point = replace(
        point, origin_step_index=saved.get("origin_step_index"), identity=saved.get("identity")
    )
    if seals._json(record(point)) != seals._json(saved):
        raise ValueError("Block interval record differs from its actual saved inputs")
    validate(spec, point)
    return point


def advance(spec, point, *, end_time_s=None):
    """Accept one original interval atomically; leave failed buffers uncommitted."""
    stage, preparation, trial, control_failure = "source_admission", None, None, None
    try:
        grid = validate(spec, point)
        numeric = point.numeric
        if numeric.step_index + 1 >= len(grid):
            raise ValueError("Terminal block checkpoint has no following interval")
        end = float(grid[numeric.step_index + 1])
        if end_time_s is not None and (
            not isinstance(end_time_s, Real)
            or isinstance(end_time_s, (bool, np.bool_))
            or not math.isfinite(end_time_s)
            or end_time_s != end
        ):
            raise ValueError("End must be exactly the next original grid boundary")
        h = end - numeric.time
        stage = "left_event_preparation"
        prepared = blocks.evaluate(
            spec,
            numeric.state,
            numeric.layout,
            _control(spec, numeric.time),
            point.tissue_binding,
            point.component,
            point.binding,
            point.block_state,
            time_s=numeric.time,
            events_enabled=point.events_enabled,
            step_s=h,
        )
        preparation, runtime = prepared.preparation, prepared.physical.runtime_layout
        implementation = view.IMPLEMENTATIONS[type(spec.model)]
        stage = "held_control_rk4"
        trial = tissue.array_rk4_step(
            numeric.state,
            preparation.effective_control,
            runtime,
            h,
            implementation=implementation,
            xp=np,
        )
        if not bool(trial.valid):
            raise ValueError(
                "RK stage/domain/field/turnover failure at " + str(int(trial.first_invalid_stage))
            )
        if any(
            not np.isfinite(s.energy_rate_residual_pJ_s)
            or abs(float(s.energy_rate_residual_pJ_s)) > ENERGY_RATE_ATOL_PJ_S
            for s in trial.status
        ):
            raise ValueError("RK stage exceeds the unchanged field-energy rate budget")
        stage = "complete_balances_and_histories"
        history = implementation.STATE_TYPE(
            *(np.stack((a, b)) for a, b in zip(numeric.state, trial.proposed_state, strict=True))
        )
        ordinary = implementation.check_values(history, spec)
        changed = view._admission_spec(spec, runtime.membrane_permeability)
        effective = implementation.check_values(history, changed)
        stage = "right_continuous_endpoint"
        right = blocks.prepare(
            spec,
            point.tissue_binding,
            point.binding,
            preparation.block_state,
            _control(spec, end),
            time_s=end,
            events_enabled=False,
        )
        for p in (numeric.layout, runtime):
            if not implementation.control_domain_valid(
                trial.proposed_state, right.effective_control, p, p.active, xp=np
            ):
                raise ValueError(
                    "Endpoint fails the actual carried right-continuous control domain"
                )
        frozen = view._immutable_tree(trial)
        endpoint = Checkpoint(
            frozen.proposed_state,
            numeric.layout,
            end,
            numeric.step_index + 1,
            event_index(spec, end),
        )
        proposed = _seal(replace(point, numeric=endpoint, block_state=preparation.block_state))
        stage = "accepted_checkpoint"
        validate(spec, proposed)
        admission = MappingProxyType(
            dict(
                clock_policy=CLOCK,
                event_time_s=float(numeric.time),
                step_s=h,
                ordinary_balance_checks=MappingProxyType(dict(ordinary)),
                runtime_balance_checks=MappingProxyType(dict(effective)),
                endpoint_control=right.effective_control,
                original_anchors_preserved=True,
                component_advanced=False,
                partial_commit=False,
            )
        )
        return BlockStepResult(proposed, preparation, frozen, admission)
    except Exception as error:
        if isinstance(error, blocks.BlockControlRejected):
            control_failure = error
        raise BlockStepRejected(
            error,
            source=point,
            stage=stage,
            preparation=preparation,
            trial=trial,
            control_failure=control_failure,
        ) from error
