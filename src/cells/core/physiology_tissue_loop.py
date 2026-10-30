"""Atomic Cells nominal loops over frozen component and held-P tissue steps.

Physiological dt is independent of tissue/event subdivision. Native order is
P finalization, ionic work, then protein noise. Left staging commutes only in
this restricted no-protein-charge/no-other-RNG composition; it is not full
native loop or failed-native-prefix parity. Only whole-loop cursors commit.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from types import MappingProxyType

import numpy as np

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as tissue
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.processes import betse_perturbations as perturb

KIND = "cells.physiology_tissue_loop@1"
MAX_LOOP_INDEX = 2**64 - 1


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _arrays_identity(values):
    return _digest(
        dict(
            type=type(values).__name__,
            fields={
                name: dict(
                    dtype=np.asarray(value).dtype.str,
                    shape=list(np.asarray(value).shape),
                    sha256=hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest(),
                )
                for name, value in values._asdict().items()
            },
        )
    )


def _checkpoint_identity(checkpoint):
    return _digest(
        dict(
            state=_arrays_identity(checkpoint.state),
            layout=_arrays_identity(checkpoint.layout),
            time_s=float(checkpoint.time),
            step_index=checkpoint.step_index,
            event_index=checkpoint.event_index,
        )
    )


def _component_identity(component):
    return _digest(
        dict(
            protein=_arrays_identity(component.protein),
            diffusion=_arrays_identity(component.diffusion),
            controls=asdict(perturb.validate_controls(component.controls)),
            stream=streams.stream_record(component.stream),
            time_s=float(component.time_s),
            loop_calls=component.loop_calls,
        )
    )


@dataclass(frozen=True, slots=True)
class TissueLoopCursor:
    loop_index: int
    physiological_dt_s: float
    numeric_time_s: float
    numeric_step_index: int
    numeric_event_index: int
    component_time_s: float
    component_loop_calls: int
    component_call_origin: int
    stream_next_tick: int
    source_definition_sha256: str
    binding_identity: str
    checkpoint_identity: str
    component_identity: str
    identity: str


@dataclass(frozen=True, slots=True)
class TissueLoopResult:
    checkpoint: object
    binding: object
    component: object
    cursor: TissueLoopCursor
    component_transition: object
    tissue_steps: tuple
    admission: object

    @property
    def next_loop_index(self):
        return self.cursor.loop_index


class TissueLoopRejected(NumericalError):
    """An uncommitted outer transaction, including its speculative RNG tape."""

    def __init__(
        self,
        reason,
        *,
        checkpoint,
        binding,
        component,
        cursor,
        transition,
        component_rejection,
        proposed_component,
        proposed_stream,
        packet,
        tissue_steps,
        failed_tissue_step,
        end_time_s,
        diagnostics,
        stage,
    ):
        super().__init__("Physiological tissue loop refused at " + stage + ": " + str(reason))
        self.source_checkpoint, self.source_component = checkpoint, component
        self.binding, self.cursor = binding, cursor
        self.component_transition, self.component_rejection = transition, component_rejection
        self.proposed_component, self.proposed_stream = proposed_component, proposed_stream
        self.packet, self.tissue_steps = packet, tuple(tissue_steps)
        self.failed_tissue_step, self.end_time_s = failed_tissue_step, end_time_s
        self.diagnostics, self.stage = MappingProxyType(dict(diagnostics)), stage


def _index(value):
    if type(value) is not int or not 0 <= value <= MAX_LOOP_INDEX:
        raise ValueError("Require an explicit uint64 nominal loop index")
    return value


def _pair(spec, checkpoint, binding, component):
    if type(checkpoint) is not Checkpoint:
        raise ValueError("Require the exact ordinary numeric Checkpoint")
    if type(spec.model) not in view.IMPLEMENTATIONS:
        raise ValueError("Require one of the four exact ordinary tissue families")
    units.restore_binding(units.binding_record(binding), spec)
    component_step.validate_state(component, binding.component)
    grid = EventGrid(spec)
    validate_checkpoint(spec, checkpoint, times=grid)
    return grid


def _cursor_payload(spec, checkpoint, binding, component, loop_index):
    return dict(
        kind=KIND,
        loop_index=loop_index,
        physiological_dt_s=float(component.controls.dt_s),
        numeric_time_s=float(checkpoint.time),
        numeric_step_index=checkpoint.step_index,
        numeric_event_index=checkpoint.event_index,
        component_time_s=float(component.time_s),
        component_loop_calls=component.loop_calls,
        component_call_origin=component.loop_calls - loop_index,
        stream_next_tick=component.stream.next_tick,
        source_definition_sha256=_digest(spec.to_dict()),
        binding_identity=binding.identity,
        checkpoint_identity=_checkpoint_identity(checkpoint),
        component_identity=_component_identity(component),
    )


def initialise(spec, checkpoint, binding, component, *, loop_index=0):
    """Explicitly declare a complete-boundary cursor; do not infer history.

    Component elapsed time and call count may have independent offsets. A
    terminal complete-boundary cursor can be stored/restored without a new call.
    Hashes seal association and detect changes; they do not authenticate authors.
    """
    loop_index = _index(loop_index)
    grid = _pair(spec, checkpoint, binding, component)
    start = loop_index * float(component.controls.dt_s)
    if not math.isfinite(start) or start != checkpoint.time:
        raise ValueError("Cursor requires the exact declared nominal left boundary")
    grid.exact_index(start)
    payload = _cursor_payload(spec, checkpoint, binding, component, loop_index)
    return TissueLoopCursor(
        **{key: value for key, value in payload.items() if key != "kind"},
        identity=_digest(payload),
    )


def cursor_record(cursor):
    """Fresh scalar JSON record of a sealed complete-boundary association."""
    if type(cursor) is not TissueLoopCursor:
        raise ValueError("Require an exact TissueLoopCursor")
    record = dict(kind=KIND, **asdict(cursor))
    payload = {key: value for key, value in record.items() if key != "identity"}
    if record["identity"] != _digest(payload):
        raise ValueError("Corrupt physiological loop cursor")
    return record


def restore_cursor(record, spec, checkpoint, binding, component):
    """Replay calendar and complete numeric/component/RNG association exactly."""
    if type(record) is not dict or record.get("kind") != KIND:
        raise ValueError("Require an explicit physiological loop cursor record")
    payload = {key: value for key, value in record.items() if key != "identity"}
    if record.get("identity") != _digest(payload):
        raise ValueError("Corrupt physiological loop cursor record")
    expected = initialise(spec, checkpoint, binding, component, loop_index=record.get("loop_index"))
    # Canonical JSON preserves scalar types (False != 0.0), fields and seals.
    if _json(cursor_record(expected)) != _json(record):
        raise ValueError("Cursor differs from the actual source/numeric/component association")
    return expected


def advance(spec, checkpoint, binding, component, cursor):
    """Stage one component call, all held-P tissue substeps, then one cursor.

    No mid-loop cursor, partial terminal call, resampling, retiming, automatic
    schedule staging or repair is provided. Original inputs remain untouched on
    success and failure. Public pair/cursor publication belongs to the caller.
    """
    transition = component_rejection = proposed = packet = failed = end = None
    proposed_stream = None
    completed = []
    stage = "cursor_admission"
    diagnostics = dict(kind=KIND, automatic_retry=False, partial_commit=False)
    try:
        restored = restore_cursor(cursor_record(cursor), spec, checkpoint, binding, component)
        index, dt = restored.loop_index, restored.physiological_dt_s
        if index == MAX_LOOP_INDEX:
            raise ValueError("Nominal loop index increment would overflow uint64")
        end = (index + 1) * dt
        grid = EventGrid(spec)
        if not math.isfinite(end) or end <= checkpoint.time or end > grid.end:
            raise ValueError("Require a full finite nominal interval inside the source horizon")
        end_index = grid.exact_index(end)
        diagnostics.update(
            source_loop_index=index,
            source_nominal_label_s=checkpoint.time,
            source_end_time_s=end,
            physiological_dt_s=dt,
            tissue_nominal_dt_s=spec.execution.dt,
            component_time_before_s=component.time_s,
            component_calls_before=component.loop_calls,
            stream_tick_before=component.stream.next_tick,
            component_call_origin=restored.component_call_origin,
            planned_tissue_intervals=end_index - checkpoint.step_index,
            clock_policy="Cells nominal labels; no native linspace-label equality claimed",
        )
        stage = "component_transition"
        try:
            transition = component_step.advance(component, binding.component)
        except component_step.PerturbationRejected as error:
            component_rejection = error
            proposed, proposed_stream, packet = error.trial, error.stream, error.packet
            raise
        proposed, packet = transition.state, transition.packet
        proposed_stream = proposed.stream
        stage = "tissue_substeps"
        local = checkpoint
        for _ in range(end_index - checkpoint.step_index):
            try:
                result = tissue.advance(spec, local, binding, proposed)
            except tissue.TissueStepRejected as error:
                failed = error
                raise
            completed.append(result)
            local = result.checkpoint
        if local.time != end or local.step_index != end_index:
            raise ValueError("Local tissue trials did not reach the exact nominal endpoint")
        stage = "completed_cursor"
        after = initialise(spec, local, binding, proposed, loop_index=index + 1)
        if after.component_call_origin != restored.component_call_origin:
            raise ValueError("A nominal loop must contain exactly one component call")
        diagnostics.update(
            component_time_after_s=proposed.time_s,
            component_calls_after=proposed.loop_calls,
            stream_tick_after=proposed.stream.next_tick,
            numeric_step_before=checkpoint.step_index,
            numeric_step_after=local.step_index,
            completed_tissue_intervals=len(completed),
            component_calls=1,
            current_P_held=True,
            component_protein_charge_coupled=False,
            other_rng_sites=False,
            native_full_loop_parity=False,
        )
        return TissueLoopResult(
            local,
            binding,
            proposed,
            after,
            transition,
            tuple(completed),
            MappingProxyType(diagnostics),
        )
    except Exception as error:
        raise TissueLoopRejected(
            error,
            checkpoint=checkpoint,
            binding=binding,
            component=component,
            cursor=cursor,
            transition=transition,
            component_rejection=component_rejection,
            proposed_component=proposed,
            proposed_stream=proposed_stream,
            packet=packet,
            tissue_steps=completed,
            failed_tissue_step=failed,
            end_time_s=end,
            diagnostics=diagnostics,
            stage=stage,
        ) from error
