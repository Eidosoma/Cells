"""Pinned BETSE periodic/sweep factors with explicit, serializable parameters.

Array kernels do not choose a clock, advance state, draw randomness or apply an
intervention. They report finite arithmetic per sample; callers retain domain,
accuracy and physical admission. Matching source factors is not a driving law.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from numbers import Real
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

LAW_ID = "betse_time_modulation_source_v1_5_0@1"


class Values(NamedTuple):
    factor: object
    phase_rad: object
    finite: object


@dataclass(frozen=True, slots=True)
class Program:
    kind: str
    frequency_Hz: float
    phase_rad: float
    slope_Hz_s: float
    automatic_slope: bool
    requested_stop_Hz: float | None
    original_duration_s: float | None
    provenance: str
    identity: str


def _float(value):
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not math.isfinite(value)
    ):
        raise ValueError("Declare finite real modulation parameters")
    return float(value)


def _provenance(value):
    if type(value) is not str or not value.strip():
        raise ValueError("Declare the origin of the time modulator")


def _digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def record(program):
    if type(program) is not Program:
        raise ValueError("Require a typed time-modulation program")
    payload = asdict(program)
    payload.pop("identity")
    payload = dict(law=LAW_ID, **payload)
    return payload | dict(identity=_digest(payload))


def periodic_program(*, frequency_Hz, phase_rad, provenance):
    """Source periodic factor sin(pi*t*f + phase)^2, with signed finite f/phase."""
    _provenance(provenance)
    program = Program(
        "periodic",
        _float(frequency_Hz),
        _float(phase_rad),
        0.0,
        False,
        None,
        None,
        provenance,
        "",
    )
    return replace(program, identity=record(program)["identity"])


def sweep_program(
    *,
    start_Hz,
    slope_Hz_s=None,
    stop_Hz=None,
    original_duration_s=None,
    run_sim=True,
    provenance,
):
    """Bind source sweep coefficients once, using the original complete duration.

    The source phase is pi*(slope*t + start)*t; do not insert a conventional
    one-half chirp coefficient. Automatic slope follows source binary64
    subtraction then division, and is undefined in the source INIT branch.
    """
    _provenance(provenance)
    start = _float(start_Hz)
    if type(run_sim) is not bool:
        raise ValueError("Declare the native run_sim guard explicitly")
    automatic = slope_Hz_s is None
    if automatic:
        if not run_sim:
            raise ValueError("Native automatic sweep slope is unresolved outside SIM")
        stop, duration = _float(stop_Hz), _float(original_duration_s)
        if duration <= 0:
            raise ValueError("Automatic sweep slope needs a positive original duration")
        slope = (stop - start) / duration
        if not math.isfinite(slope):
            raise ValueError("Automatic sweep coefficient is not representable")
    else:
        if stop_Hz is not None or original_duration_s is not None:
            raise ValueError("Declare either an explicit slope or its original source inputs")
        slope, stop, duration = _float(slope_Hz_s), None, None
    program = Program("sweep", start, 0.0, slope, automatic, stop, duration, provenance, "")
    return replace(program, identity=record(program)["identity"])


def validate(program):
    if type(program) is not Program:
        raise ValueError("Require a typed time-modulation program")
    if program.kind == "periodic":
        expected = periodic_program(
            frequency_Hz=program.frequency_Hz,
            phase_rad=program.phase_rad,
            provenance=program.provenance,
        )
    elif program.kind == "sweep":
        if type(program.automatic_slope) is not bool:
            raise ValueError("Require an explicit slope policy")
        expected = sweep_program(
            start_Hz=program.frequency_Hz,
            slope_Hz_s=None if program.automatic_slope else program.slope_Hz_s,
            stop_Hz=program.requested_stop_Hz,
            original_duration_s=program.original_duration_s,
            provenance=program.provenance,
        )
    else:
        raise ValueError("Unknown time-modulation law")
    if program.identity != expected.identity or record(program) != record(expected):
        raise ValueError("Modulator differs from its complete original coefficients")
    return program


def restore(saved, *, expected_identity):
    if type(saved) is not dict or saved.get("law") != LAW_ID:
        raise ValueError("Require the complete saved modulation law")
    try:
        program = Program(**{k: v for k, v in saved.items() if k != "law"})
    except TypeError as error:
        raise ValueError("Incomplete or extended modulation program") from error
    validate(program)
    if program.identity != expected_identity or record(program) != saved:
        raise ValueError("Saved modulator differs from its original identity")
    return program


def _arrays(*values, xp):
    arrays = tuple(xp.asarray(value) for value in values)
    if any(value.dtype != xp.float64 for value in arrays):
        raise ValueError("Time and coefficient arrays require explicit float64 values")
    return xp.broadcast_arrays(*arrays)


def periodic(time_s, frequency_Hz, phase_rad, *, xp=jnp):
    """Broadcast source periodic arithmetic; no host extraction or implicit clock."""
    time, frequency, offset = _arrays(time_s, frequency_Hz, phase_rad, xp=xp)
    scaled_time = time * np.pi
    running_phase = scaled_time * (frequency / 1)
    phase = running_phase + offset
    value = xp.sin(phase) ** 2
    finite = (
        xp.isfinite(time)
        & xp.isfinite(frequency)
        & xp.isfinite(offset)
        & xp.isfinite(scaled_time)
        & xp.isfinite(running_phase)
        & xp.isfinite(phase)
        & xp.isfinite(value)
    )
    return Values(value, phase, finite)


def sweep(time_s, start_Hz, slope_Hz_s, *, xp=jnp):
    """Broadcast the literal source sweep phase; no integrated-frequency repair."""
    time, start, slope = _arrays(time_s, start_Hz, slope_Hz_s, xp=xp)
    ramp = slope * time
    running_frequency = ramp + start
    scaled_frequency = np.pi * running_frequency
    phase = scaled_frequency * time
    value = xp.sin(phase) ** 2
    finite = (
        xp.isfinite(time)
        & xp.isfinite(start)
        & xp.isfinite(slope)
        & xp.isfinite(ramp)
        & xp.isfinite(running_frequency)
        & xp.isfinite(scaled_frequency)
        & xp.isfinite(phase)
        & xp.isfinite(value)
    )
    return Values(value, phase, finite)


def evaluate(program, time_s, *, xp=jnp):
    """Use a fixed prepared program with an explicitly supplied time array."""
    validate(program)
    if program.kind == "periodic":
        return periodic(time_s, program.frequency_Hz, program.phase_rad, xp=xp)
    return sweep(time_s, program.frequency_Hz, program.slope_Hz_s, xp=xp)
