"""Pinned global temperature/block/voltage setters, independent of tissue physics.

These setters prescribe controls. They do not advance ions, select a phase clock,
draw random targets or account for heat, electrode work or a biological protocol.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from numbers import Real
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

LAW_ID = "betse_global_controls_source_v1_5_0@1"
KINDS = ("temperature", "junction_block", "pump_block", "voltage")
SIDES = ("top", "bottom", "left", "right")


@dataclass(frozen=True, slots=True)
class Event:
    kind: str
    on_s: float
    off_s: float
    change_s: float
    amplitude: float = 0.0  # Temperature multiplier or signed peak volts.
    target_ids: tuple = ()
    positive_boundary: str | None = None
    negative_boundary: str | None = None


@dataclass(frozen=True, slots=True)
class Program:
    membrane_ids: tuple
    events: tuple
    provenance: str
    identity: str


class Kernel(NamedTuple):
    on_s: object
    off_s: object
    change_s: object
    enabled: object
    temperature_multiplier: object
    junction_mask: object
    peak_voltage_V: object
    positive_index: object
    negative_index: object


class State(NamedTuple):
    temperature_K: object
    junction_available: object  # Native membrane-indexed gj_block, not physical edges.
    pump_available: object
    boundary_voltage_V: object  # [...,top/bottom/left/right].


class Values(NamedTuple):
    state: State
    pulse: object
    pulse_finite: object
    exponential_saturated: object
    finite: object
    physical_domain: object


def _real(value):
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not math.isfinite(value)
    ):
        raise ValueError("Require explicit finite real pulse parameters")
    return float(value)


def record(program):
    if type(program) is not Program:
        raise ValueError("Require a typed global-control program")
    raw = asdict(program)
    raw.pop("identity")
    raw = json.loads(json.dumps(dict(law=LAW_ID, **raw), allow_nan=False))
    identity = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return raw | dict(identity=identity)


def bind(*, membrane_ids, events, provenance):
    if (
        not isinstance(membrane_ids, (tuple, list))
        or any(type(x) is not str or not x for x in membrane_ids)
        or len(set(membrane_ids)) != len(membrane_ids)
        or not isinstance(events, (tuple, list))
        or len(events) > 4
        or type(provenance) is not str
        or not provenance.strip()
    ):
        raise ValueError("Require ordered unique membrane owners, bounded events and provenance")
    rows, seen = [], set()
    for row in events:
        if type(row) is not Event or row.kind not in KINDS or row.kind in seen:
            raise ValueError("Require at most one typed event per source setter")
        seen.add(row.kind)
        on, off, width, amplitude = map(_real, (row.on_s, row.off_s, row.change_s, row.amplitude))
        if off < on or width <= 0 or not math.isfinite((1 / width) * 10):
            raise ValueError(
                "Require ordered finite pulse times and a positive representable width"
            )
        if (
            type(row.target_ids) is not tuple
            or len(set(row.target_ids)) != len(row.target_ids)
            or any(x not in membrane_ids for x in row.target_ids)
            or (row.kind != "junction_block" and row.target_ids)
            or (row.kind in ("junction_block", "pump_block") and amplitude != 0)
        ):
            raise ValueError("Require explicit unique junction targets and relevant coefficients")
        if row.kind == "voltage":
            if row.positive_boundary not in SIDES or row.negative_boundary not in SIDES:
                raise ValueError("Require explicit top/bottom/left/right voltage boundaries")
        elif row.positive_boundary is not None or row.negative_boundary is not None:
            raise ValueError("Only voltage events have boundary names")
        rows.append(replace(row, on_s=on, off_s=off, change_s=width, amplitude=amplitude))
    rows.sort(key=lambda row: KINDS.index(row.kind))
    program = Program(tuple(membrane_ids), tuple(rows), provenance, "")
    return replace(program, identity=record(program)["identity"])


def validate(program):
    if type(program) is not Program:
        raise ValueError("Require a typed global-control program")
    expected = bind(
        membrane_ids=program.membrane_ids, events=program.events, provenance=program.provenance
    )
    if expected != program:
        raise ValueError("Global-control program differs from its complete original identity")
    return program


def restore(saved, *, expected_identity):
    if (
        type(saved) is not dict
        or set(saved) != {"law", "membrane_ids", "events", "provenance", "identity"}
        or saved["law"] != LAW_ID
    ):
        raise ValueError("Require the complete saved global-control record")
    try:
        rows = tuple(
            Event(**(row | dict(target_ids=tuple(row["target_ids"])))) for row in saved["events"]
        )
        answer = bind(
            membrane_ids=saved["membrane_ids"], events=rows, provenance=saved["provenance"]
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Incomplete or extended global event") from error
    if answer.identity != expected_identity or record(answer) != saved:
        raise ValueError("Saved global controls differ from original owners/parameters")
    return answer


def compile_program(program):
    """Host preparation; explicit targets only, no shuffled-prefix or RNG inference."""
    validate(program)
    by_kind = {row.kind: row for row in program.events}
    rows = [by_kind.get(kind, Event(kind, 0.0, 1.0, 1.0)) for kind in KINDS]

    def frozen(value, dtype):
        array = np.asarray(value, dtype=dtype)
        return np.frombuffer(array.tobytes(), dtype=dtype).reshape(array.shape)

    return Kernel(
        *(
            frozen([getattr(row, key) for row in rows], np.float64)
            for key in ("on_s", "off_s", "change_s")
        ),
        frozen([kind in by_kind for kind in KINDS], bool),
        frozen(rows[0].amplitude, np.float64),
        frozen([name in rows[1].target_ids for name in program.membrane_ids], bool),
        frozen(rows[3].amplitude, np.float64),
        frozen(SIDES.index(rows[3].positive_boundary) if "voltage" in by_kind else 0, np.int64),
        frozen(SIDES.index(rows[3].negative_boundary) if "voltage" in by_kind else 1, np.int64),
    )


def apply(state, kernel, time_s, original_temperature_K, events_enabled, *, xp=jnp):
    """Float64 single-world kernel suitable for jit/vmap; no host value extraction.

    Logistic exponent overflow is retained as a saturation diagnostic; finite
    sigmoid limits are allowed. Nonfinite gain/arguments or setter results fail.
    Disabled events do not invalidate unchanged state because of unused inputs.
    """
    if type(state) is not State or type(kernel) is not Kernel:
        raise ValueError("Require complete typed control state and prepared kernel")
    state = State(*(xp.asarray(v) for v in state))
    kernel = Kernel(*(xp.asarray(v) for v in kernel))
    time, base, enabled = (
        xp.asarray(time_s),
        xp.asarray(original_temperature_K),
        xp.asarray(events_enabled),
    )
    floats = (
        *state,
        kernel.on_s,
        kernel.off_s,
        kernel.change_s,
        kernel.temperature_multiplier,
        kernel.peak_voltage_V,
        time,
        base,
    )
    if any(v.dtype != xp.float64 for v in floats):
        raise ValueError("Control values and coefficients require float64 arrays")
    if (
        state.temperature_K.shape != ()
        or state.pump_available.shape != ()
        or state.junction_available.ndim != 1
        or state.boundary_voltage_V.shape != (4,)
        or any(
            v.shape != (4,) for v in (kernel.on_s, kernel.off_s, kernel.change_s, kernel.enabled)
        )
        or kernel.junction_mask.shape != state.junction_available.shape
        or kernel.junction_mask.dtype != xp.bool_
        or kernel.enabled.dtype != xp.bool_
        or enabled.dtype != xp.bool_
        or enabled.shape != ()
        or time.shape != ()
        or base.shape != ()
        or any(
            v.shape != ()
            for v in (
                kernel.temperature_multiplier,
                kernel.peak_voltage_V,
                kernel.positive_index,
                kernel.negative_index,
            )
        )
        or kernel.positive_index.dtype != xp.int64
        or kernel.negative_index.dtype != xp.int64
    ):
        raise ValueError(
            "Require complete single-world axes and explicit masks/indices; batch with vmap"
        )
    active = kernel.enabled & enabled
    gain = (1 / kernel.change_s) * 10
    first_arg, last_arg = -gain * (time - kernel.on_s), -gain * (time - kernel.off_s)
    first_exp, last_exp = xp.exp(first_arg), xp.exp(last_arg)
    pulse = 1 / (1 + first_exp) - 1 / (1 + last_exp)
    pulse_finite = ~active | (
        xp.isfinite(time)
        & xp.isfinite(kernel.on_s)
        & xp.isfinite(kernel.off_s)
        & xp.isfinite(kernel.change_s)
        & (kernel.change_s > 0)
        & (kernel.off_s >= kernel.on_s)
        & xp.isfinite(gain)
        & xp.isfinite(first_arg)
        & xp.isfinite(last_arg)
        & xp.isfinite(pulse)
    )
    temperature = xp.where(
        active[0], kernel.temperature_multiplier * pulse[0] * base + base, state.temperature_K
    )
    junctions = xp.where(active[1] & kernel.junction_mask, 1.0 - pulse[1], state.junction_available)
    pump = xp.where(active[2], 1.0 - pulse[2], state.pump_available)
    side = xp.arange(4)
    positive = xp.where(
        active[3] & (side == kernel.positive_index),
        kernel.peak_voltage_V * pulse[3],
        state.boundary_voltage_V,
    )
    # Preserve the actual ordered writes: negative wins if both name one side.
    voltage = xp.where(
        active[3] & (side == kernel.negative_index), -kernel.peak_voltage_V * pulse[3], positive
    )
    output = State(temperature, junctions, pump, voltage)
    finite = xp.all(pulse_finite)
    for value in output:
        finite &= xp.all(xp.isfinite(value))
    finite &= ~active[0] | (xp.isfinite(base) & xp.isfinite(kernel.temperature_multiplier))
    finite &= ~active[3] | (
        xp.isfinite(kernel.peak_voltage_V)
        & (kernel.positive_index >= 0)
        & (kernel.positive_index < 4)
        & (kernel.negative_index >= 0)
        & (kernel.negative_index < 4)
    )
    physical = (
        finite
        & (temperature > 0)
        & (~active[0] | (base > 0))
        & (pump >= 0)
        & (pump <= 1)
        & xp.all((junctions >= 0) & (junctions <= 1))
    )
    return Values(
        output,
        xp.where(active, pulse, 0.0),
        pulse_finite,
        active & (xp.isinf(first_exp) | xp.isinf(last_exp)),
        finite,
        physical,
    )
