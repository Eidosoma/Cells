"""Explicit BETSE phase labels alongside fixed-duration Cells call boundaries.

This preparation adapter does not change a solver's clock. Native event labels
span [0, N*dt] in N calls; each call still uses dt. A resumed window retains the
original N. Arrays are immutable host inputs suitable for later device staging,
not a qualified GPU scheduler or a tissue checkpoint.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from numbers import Integral, Real
from typing import NamedTuple

import numpy as np

KIND = "cells.betse_phase_calendar@1"
REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
MAX_PHASE_CALLS = 1_000_000


@dataclass(frozen=True, slots=True)
class NativePhaseCalendar:
    phase: str
    step_count: int
    dt_s: float
    sample_stride: float
    requested_duration_s: float | None
    provenance: str
    identity: str


class CalendarArrays(NamedTuple):
    call_index: object
    event_label_s: object
    elapsed_start_s: object
    elapsed_end_s: object
    duration_s: object
    sampled: object
    events_enabled: object


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _real(value, name, *, positive=False):
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not math.isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        raise ValueError(f"Require finite {'positive' if positive else 'nonnegative'} {name}")
    return float(value)


def _index(value, name, maximum):
    if (
        not isinstance(value, Integral)
        or isinstance(value, (bool, np.bool_))
        or not 0 <= value <= maximum
    ):
        raise ValueError(f"Require an integer {name} in [0, {maximum}]")
    return int(value)


def record(calendar):
    if type(calendar) is not NativePhaseCalendar:
        raise ValueError("Require a typed native phase calendar")
    values = asdict(calendar)
    values.pop("identity")
    payload = dict(kind=KIND, native_revision=REVISION, **values)
    return payload | dict(identity=_digest(payload))


def bind(*, phase, step_count, dt_s, sample_stride=1.0, provenance, requested_duration_s=None):
    """Declare the complete original phase, never the remaining restart length.

    A supplied duration uses the pinned configuration's binary64 division and
    integer truncation. A sub-unit sampling stride would stall the source loop
    and is refused, rather than reproduced as a nonterminating computation.
    Empty phases are representable calendar inputs, not simulated trajectories.
    """
    if type(phase) is not str or phase not in ("INIT", "SIM"):
        raise ValueError("Declare INIT or SIM explicitly")
    count = _index(step_count, "phase call count", MAX_PHASE_CALLS)
    dt = _real(dt_s, "call duration", positive=True)
    stride = _real(sample_stride, "sample stride", positive=True)
    if stride < 1:
        raise ValueError("Native sampling stride below one does not progress")
    if type(provenance) is not str or not provenance.strip():
        raise ValueError("Declare the source of the phase calendar")
    if not math.isfinite(count * dt):
        raise ValueError("Phase duration is not representable")
    duration = requested_duration_s
    if duration is not None:
        duration = _real(duration, "requested duration")
        ratio = duration / dt
        if not math.isfinite(ratio) or int(ratio) != count:
            raise ValueError("Phase count differs from native duration truncation")
    calendar = NativePhaseCalendar(phase, count, dt, stride, duration, provenance, "")
    return replace(calendar, identity=record(calendar)["identity"])


def from_duration(*, phase, requested_duration_s, dt_s, sample_stride=1.0, provenance):
    """Preserve int(total/dt), including near-integer binary64 effects."""
    duration = _real(requested_duration_s, "requested duration")
    dt = _real(dt_s, "call duration", positive=True)
    ratio = duration / dt
    if not math.isfinite(ratio) or ratio > MAX_PHASE_CALLS + 1:
        raise ValueError("Requested phase exceeds the bounded preparation domain")
    return bind(
        phase=phase,
        step_count=int(ratio),
        dt_s=dt,
        sample_stride=sample_stride,
        provenance=provenance,
        requested_duration_s=duration,
    )


def validate(calendar):
    if type(calendar) is not NativePhaseCalendar:
        raise ValueError("Require a typed native phase calendar")
    raw = asdict(calendar)
    identity = raw.pop("identity")
    expected = bind(**raw)
    if identity != expected.identity or record(calendar) != record(expected):
        raise ValueError("Native phase calendar association changed")
    return calendar


def restore(saved, *, expected_identity):
    """Restore against the caller's original calendar identity, without rebasing.

    This checks association, not authenticity or completed tissue work. A solver
    checkpoint must separately associate its state and accepted call cursor.
    """
    if type(saved) is not dict:
        raise ValueError("Require the complete serialized calendar")
    raw = dict(saved)
    for key in ("kind", "native_revision", "identity"):
        raw.pop(key, None)
    try:
        calendar = bind(**raw)
    except TypeError as error:
        raise ValueError("Incomplete or extended native calendar") from error
    if record(calendar) != saved or calendar.identity != expected_identity:
        raise ValueError("Saved calendar differs from the original phase")
    return calendar


def _frozen(values):
    values = np.ascontiguousarray(values)
    return np.frombuffer(values.tobytes(), dtype=values.dtype).reshape(values.shape)


@lru_cache(maxsize=4)
def _labels(count, dt_s):
    # A bounded immutable preparation cache avoids regenerating N labels during
    # every host proposal/replay. It stores no advancing cursor or solver state.
    return _frozen(np.linspace(0.0, count * dt_s, count, dtype=np.float64))


def event_label_s(calendar, call_index):
    """Return the original source label for one call, refusing the terminal cursor."""
    validate(calendar)
    index = _index(call_index, "event call index", calendar.step_count)
    if index == calendar.step_count:
        raise ValueError("Native phase calendar has no remaining event call")
    return float(_labels(calendar.step_count, calendar.dt_s)[index])


def window(calendar, *, start=0, stop=None):
    """Prepare a slice of the original calendar with immutable binary64 arrays.

    Source sampling labels describe observations after the full call. Their
    label is not the accepted elapsed endpoint. The explicit duration column
    must be used for updates; subtracting rounded endpoints can differ from dt.
    """
    validate(calendar)
    count = calendar.step_count
    start = _index(start, "window start", count)
    stop = count if stop is None else _index(stop, "window stop", count)
    if stop < start:
        raise ValueError("Window stop precedes its start")
    indices = np.arange(count, dtype=np.int64)
    labels = _labels(count, calendar.dt_s)
    starts = indices * calendar.dt_s
    ends = (indices + 1) * calendar.dt_s
    if (
        not all(np.isfinite(value).all() for value in (labels, starts, ends))
        or np.any(ends <= starts)
        or np.any(np.diff(labels) <= 0)
    ):
        raise ValueError("Calendar labels or elapsed boundaries collapsed")
    sampled = np.zeros(count, dtype=bool)
    index = 0
    while index < count - calendar.sample_stride:
        index = int(index + calendar.sample_stride)
        sampled[index] = True
    arrays = CalendarArrays(
        indices,
        labels,
        starts,
        ends,
        np.full(count, calendar.dt_s, dtype=np.float64),
        sampled,
        np.full(count, calendar.phase == "SIM", dtype=bool),
    )
    return CalendarArrays(*(_frozen(value[start:stop]) for value in arrays))
