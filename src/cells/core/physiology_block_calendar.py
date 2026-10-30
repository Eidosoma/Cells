"""Atomic blocker calls using native event labels and ordinary physical steps.

The complete original phase owns the event label. Each call spans its declared
physical interval, subdivided only by the existing ordinary integration grid.
Global setters run once; internal disabled setter calls preserve those factors.
This controller holds the component and its RNG, and does not run the native
ionic solver, protein transitions, temperature/voltage events or observations.
"""

from dataclasses import dataclass, replace
from types import MappingProxyType

from cells.core import physiology_block_control_step as intervals
from cells.core import physiology_native_calendar as clocks
from cells.core.errors import NumericalError
from cells.models import physiology_block_control_view as blocks

KIND = "cells.physiology_block_calendar@1"
CLOCK = "native_phase_label_with_original_physical_subintervals@1"


@dataclass(frozen=True, slots=True)
class CalendarCheckpoint:
    point: intervals.BlockCheckpoint
    calendar: clocks.NativePhaseCalendar
    origin_call_index: int
    call_index: int
    identity: str


@dataclass(frozen=True, slots=True)
class CalendarResult:
    checkpoint: CalendarCheckpoint
    preparation: blocks.PreparedControl
    intervals: tuple
    admission: object


class CalendarRejected(NumericalError):
    def __init__(self, reason, *, source, stage, preparation=None, completed=(), failure=None):
        super().__init__("Native-calendar blocker call refused at " + stage + ": " + str(reason))
        self.source, self.stage = source, stage
        self.preparation, self.completed, self.failure = preparation, tuple(completed), failure


def record(checkpoint):
    if type(checkpoint) is not CalendarCheckpoint:
        raise ValueError("Require a complete native-calendar blocker checkpoint")
    payload = dict(
        kind=KIND,
        clock_policy=CLOCK,
        point_identity=checkpoint.point.identity,
        calendar_identity=checkpoint.calendar.identity,
        origin_call_index=checkpoint.origin_call_index,
        call_index=checkpoint.call_index,
        completed_calls=checkpoint.call_index - checkpoint.origin_call_index,
    )
    return payload | dict(identity=intervals.seals._digest(payload))


def _seal(checkpoint):
    return replace(checkpoint, identity=record(checkpoint)["identity"])


def validate(spec, checkpoint):
    if type(checkpoint) is not CalendarCheckpoint:
        raise ValueError("Require a typed native-calendar blocker checkpoint")
    calendar = clocks.validate(checkpoint.calendar)
    if calendar.step_count == 0:
        raise ValueError("Empty calendars have no physical blocker calls")
    if (
        type(checkpoint.origin_call_index) is not int
        or type(checkpoint.call_index) is not int
        or not 0 <= checkpoint.origin_call_index <= checkpoint.call_index <= calendar.step_count
    ):
        raise ValueError("Require explicit original and accepted integer call indices")
    if checkpoint.identity != record(checkpoint)["identity"]:
        raise ValueError("Native calendar and physical checkpoint association changed")
    point = checkpoint.point
    grid = intervals.validate(spec, point)
    if point.events_enabled is not False:
        raise ValueError("Only the outer native calendar may fire blocker events")
    if (
        point.component.controls.phase != calendar.phase
        or point.component.controls.dt_s != calendar.dt_s
    ):
        raise ValueError("Component declaration differs from native phase or call duration")
    if point.numeric.time != checkpoint.call_index * calendar.dt_s:
        raise ValueError("Accepted physical time differs from the original native call cursor")
    if grid.exact_index(checkpoint.origin_call_index * calendar.dt_s) != point.origin_step_index:
        raise ValueError("Physical interval origin differs from the native call origin")
    grid.exact_index(calendar.step_count * calendar.dt_s)
    # A saved endpoint does not depend on an unrequested next call being valid.
    # Each requested physical call must end on the original grid before any
    # event fires; an off-grid next boundary therefore refuses in advance().
    return grid


def initialise(
    spec, numeric, tissue_binding, component, binding, block_state, calendar, *, call_index=0
):
    point = intervals.initialise(
        spec, numeric, tissue_binding, component, binding, block_state, events_enabled=False
    )
    checkpoint = _seal(CalendarCheckpoint(point, calendar, call_index, call_index, ""))
    validate(spec, checkpoint)
    return checkpoint


def restore(saved, spec, point, calendar):
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require the complete native-calendar checkpoint record")
    checkpoint = CalendarCheckpoint(
        point,
        calendar,
        saved.get("origin_call_index"),
        saved.get("call_index"),
        saved.get("identity"),
    )
    validate(spec, checkpoint)
    if intervals.seals._json(record(checkpoint)) != intervals.seals._json(saved):
        raise ValueError("Native-calendar record differs from its actual saved inputs")
    return checkpoint


def advance(spec, checkpoint):
    """Publish one whole call only after every original physical interval passes."""
    stage, preparation, completed = "source_admission", None, []
    try:
        grid = validate(spec, checkpoint)
        calendar, point = checkpoint.calendar, checkpoint.point
        index = checkpoint.call_index
        label = clocks.event_label_s(calendar, index)  # Terminal cursors cannot fire.
        end = (index + 1) * calendar.dt_s
        if end <= point.numeric.time:
            raise ValueError("Native physical call boundaries collapsed")
        last = grid.exact_index(end)
        stage = "native_event_preparation"
        preparation = blocks.prepare(
            spec,
            point.tissue_binding,
            point.binding,
            point.block_state,
            intervals._control(spec, point.numeric.time),
            time_s=label,
            events_enabled=calendar.phase == "SIM",
        )
        staged = intervals._seal(replace(point, block_state=preparation.block_state))
        stage = "physical_subintervals"
        while staged.numeric.step_index < last:
            result = intervals.advance(spec, staged)
            completed.append(result)
            staged = result.checkpoint
        proposed = _seal(replace(checkpoint, point=staged, call_index=index + 1))
        stage = "accepted_checkpoint"
        validate(spec, proposed)
        admission = MappingProxyType(
            dict(
                clock_policy=CLOCK,
                calendar_identity=calendar.identity,
                call_index=index,
                phase=calendar.phase,
                events_enabled=calendar.phase == "SIM",
                event_label_s=label,
                elapsed_start_s=point.numeric.time,
                elapsed_end_s=end,
                declared_duration_s=calendar.dt_s,
                elapsed_interval_s=end - point.numeric.time,
                physical_subintervals=len(completed),
                component_advanced=False,
                rng_advanced=False,
                partial_commit=False,
            )
        )
        return CalendarResult(proposed, preparation, tuple(completed), admission)
    except Exception as error:
        raise CalendarRejected(
            error,
            source=checkpoint,
            stage=stage,
            preparation=preparation,
            completed=completed,
            failure=error,
        ) from error
