"""Source-discrete native temperature/calendar replay with fixed material.

Only temperature, explicit HH/ML clock probes and the source call cursor advance.
Fast initializer caches retain their original inputs. No current, ion, voltage,
thermal energy, accepted tissue state or external callback is advanced here.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core import physiology_native_calendar as clocks
from cells.core.errors import NumericalError
from cells.processes import betse_fast_solver as fast
from cells.processes import betse_global_controls as setters

LAW_ID = "betse_temperature_calendar_source_v1_5_0@1"
INPUT_KIND = "cells.betse_temperature_calendar_inputs@1"
CHECKPOINT_KIND = "cells.betse_temperature_calendar_checkpoint@1"
REVISION = clocks.REVISION
MAX_CALLS = 64
NONCE = 1e-25
PROFILES = {
    "literal_native": dict(R_J_mol_K=8.314, F_C_mol=96485.0, q_C=1.602e-19, kb_J_K=1.3806e-23),
    "matched_SI": dict(
        R_J_mol_K=6.02214076e23 * 1.380649e-23,
        F_C_mol=6.02214076e23 * 1.602176634e-19,
        q_C=1.602176634e-19,
        kb_J_K=1.380649e-23,
    ),
}
GATE_ARRAYS = (
    "initial_hh_m",
    "initial_hh_h",
    "initial_ml_m",
    "hh_m_inf",
    "hh_h_inf",
    "hh_m_tau_native",
    "hh_h_tau_native",
    "ml_m_inf",
    "ml_tau_native",
)
ORDER = (
    "phase_entry_cache",
    "SIM_global_temperature",
    "selected_tissue_clock_probes",
    "makeAllChanges_marker",
    "coefficient_readouts",
    "source_cursor_commit",
)


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "_asdict"):
        return {key: plain(item) for key, item in value._asdict().items()}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def _json(value):
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _frozen(value):
    value = np.asarray(value, dtype=np.float64)
    return np.frombuffer(value.tobytes(), dtype=np.float64).reshape(value.shape)


def buffer_record(value):
    """Exact binary64 transport, including raw nonfinite refusal evidence."""
    value = np.asarray(value, dtype=np.float64)
    return dict(dtype="<f8", shape=list(value.shape), hex=value.astype("<f8").tobytes().hex())


def _buffer(saved, shape):
    if (
        type(saved) is not dict
        or set(saved) != {"dtype", "shape", "hex"}
        or saved["dtype"] != "<f8"
        or type(saved["shape"]) is not list
        or any(type(value) is not int for value in saved["shape"])
        or saved["shape"] != list(shape)
        or type(saved["hex"]) is not str
        or len(saved["hex"]) != 16 * math.prod(shape)
    ):
        raise ValueError("Require the complete exact original binary64 buffer")
    try:
        return _frozen(np.frombuffer(bytes.fromhex(saved["hex"]), dtype="<f8").reshape(shape))
    except ValueError as error:
        raise ValueError("Malformed exact binary64 buffer") from error


class ClockState(NamedTuple):
    temperature_K: object
    hh_m: object
    hh_h: object
    ml_m: object


class ProbeValues(NamedTuple):
    membrane_electroflux_alpha: object
    configured_junction_electroflux_alpha: object
    live_nernst_planck_alpha: object
    configured_conductivity_S_m2: object
    configured_normal_sigma_S_m: object
    membrane_voltage_after_nonce_V: object
    junction_voltage_after_nonce_V: object
    valence_after_nonce: object


class GateArithmetic(NamedTuple):
    duration_native_units: object
    hh_m_numerator: object
    hh_h_numerator: object
    hh_m_denominator: object
    hh_h_denominator: object
    ml_numerator: object
    ml_denominator: object


@dataclass(frozen=True, slots=True)
class Binding:
    definition_json: str
    calendar: clocks.NativePhaseCalendar
    program: setters.Program
    kernel: setters.Kernel
    cache: fast.FastModel
    gate_parameters: object
    membrane_voltage_V: object
    junction_voltage_V: object
    identity: str

    @property
    def definition(self):
        return json.loads(self.definition_json)


@dataclass(frozen=True, slots=True)
class Checkpoint:
    binding_identity: str
    cache_identity: str
    call_index: int
    values: ClockState
    parent_identity: str | None
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    parent_identity: str
    call_index: int
    event_label_s: float
    elapsed_start_s: float
    elapsed_end_s: float
    duration_s: float
    sampled: bool
    events_enabled: bool
    raw_setter: setters.Values
    values: ClockState
    probes: ProbeValues
    gate_arithmetic: GateArithmetic | None
    cache_identity: str
    source_order: tuple
    diagnostics: object


@dataclass(frozen=True, slots=True)
class Receipt:
    checkpoint: Checkpoint
    trial: Trial


class TemperatureCalendarRejected(NumericalError):
    def __init__(self, reason, *, stage, source, trial=None):
        super().__init__("Native temperature calendar refused at " + stage + ": " + str(reason))
        self.stage, self.source, self.trial = stage, source, trial


def _array(value, shape, name, *, positive=False, probability=False):
    a = np.asarray(value)
    if a.dtype.kind not in "iuf" or a.shape != shape:
        raise ValueError("Require the complete explicit numeric owner axis: " + name)
    a = np.asarray(a, dtype=np.float64)
    if not np.isfinite(a).all() or positive and np.any(a <= 0):
        raise ValueError("Require finite positive probe parameters where declared: " + name)
    if probability and np.any((a < 0) | (a > 1)):
        raise ValueError("Clock-probe probabilities must lie in [0,1]: " + name)
    return _frozen(a)


def _scalar(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError("Require an explicit real scalar: " + name)
    return _array(value, (), name, positive=True)


def binding_record(binding):
    return dict(
        law=LAW_ID,
        revision=REVISION,
        definition=binding.definition,
        calendar=clocks.record(binding.calendar),
        program=setters.record(binding.program),
        cache_identity=binding.cache.identity,
        cache=fast.model_record(binding.cache),
        gate_parameters={
            key: buffer_record(value) for key, value in binding.gate_parameters.items()
        },
        membrane_voltage_V=buffer_record(binding.membrane_voltage_V),
        junction_voltage_V=buffer_record(binding.junction_voltage_V),
        source_order=list(ORDER),
    )


def bind(raw, calendar, program):
    """Bind fixed source material and clock probes, without shared API changes."""
    if type(raw) is not dict or set(raw) != {
        "kind",
        "provenance",
        "constant_profile",
        "entry_mode",
        "material",
        "clock_probes",
        "membrane_voltage_V",
        "junction_voltage_V",
    }:
        raise ValueError("Require the separate complete temperature-calendar definition")
    if (
        raw["kind"] != INPUT_KIND
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
        or type(raw["constant_profile"]) is not str
        or raw["constant_profile"] not in PROFILES
        or type(raw["entry_mode"]) is not str
        or raw["entry_mode"] not in ("fresh_configured_copy", "explicit_carried_runtime")
    ):
        raise ValueError("Declare the exact source law, constants, entry lifecycle and provenance")
    clocks.validate(calendar)
    if calendar.step_count > MAX_CALLS:
        raise ValueError("Temperature replay is bounded to the declared source microcase")
    clocks.window(calendar)  # Complete original labels/boundaries, before any source call.
    setters.validate(program)
    if any(event.kind != "temperature" for event in program.events):
        raise ValueError("This source component owns temperature events only")
    cache = fast.bind(raw["material"], calendar)
    material = cache.definition
    p = material["parameters"]
    if p["is_ecm"] is not False:
        raise ValueError("The fixed-material cache replay requires explicit no-ECM source axes")
    if any(p[key] != value for key, value in PROFILES[raw["constant_profile"]].items()):
        raise ValueError("Declared constant profile differs from its exact original values")
    if (
        raw["entry_mode"] == "fresh_configured_copy"
        and p["temperature_K"] != p["configured_temperature_K"]
    ):
        raise ValueError("Fresh source initialization copies configured p.T exactly")
    owners = material["geometry"]["membrane_ids"]
    if program.membrane_ids != owners:
        raise ValueError("Temperature program differs from the original ordered membrane owners")
    gates = raw["clock_probes"]
    if (
        type(gates) is not dict
        or set(gates) != {*GATE_ARRAYS, "owner_ids", "time_unit", "Phi"}
        or tuple(gates["owner_ids"]) != owners
    ):
        raise ValueError("Require complete ordered explicit HH/ML clock-probe owners")
    m = len(owners)
    if len(material["geometry"]["cell_ids"]) > 16 or m > 128:
        raise ValueError("Source temperature replay owner axes exceed the declared microcase")
    parameters = {
        key: _array(gates[key], (m,), key, positive="tau" in key, probability="tau" not in key)
        for key in GATE_ARRAYS
    }
    parameters.update({key: _scalar(gates[key], key) for key in ("time_unit", "Phi")})
    definition_json = _json(raw)
    binding = Binding(
        definition_json,
        calendar,
        program,
        setters.compile_program(program),
        cache,
        MappingProxyType(parameters),
        _array(raw["membrane_voltage_V"], (m,), "membrane voltage probe"),
        _array(raw["junction_voltage_V"], (m,), "junction voltage probe"),
        "",
    )
    return replace(binding, identity=_digest(binding_record(binding)))


def validate_binding(binding):
    if type(binding) is not Binding:
        raise ValueError("Require the complete original temperature replay binding")
    expected = bind(binding.definition, binding.calendar, binding.program)
    if (
        binding.identity != expected.identity
        or _digest(binding_record(binding)) != expected.identity
        or type(binding.kernel) is not setters.Kernel
        or binding.cache.identity != expected.cache.identity
        or any(
            not np.array_equal(a, b) for a, b in zip(binding.kernel, expected.kernel, strict=True)
        )
    ):
        raise ValueError("Temperature binding/cache/program differs from original source inputs")
    return binding


def checkpoint_record(point):
    if type(point) is not Checkpoint:
        raise ValueError("Require a typed complete temperature replay checkpoint")
    payload = dict(
        kind=CHECKPOINT_KIND,
        binding_identity=point.binding_identity,
        cache_identity=point.cache_identity,
        call_index=point.call_index,
        parent_identity=point.parent_identity,
        values={key: buffer_record(value) for key, value in point.values._asdict().items()},
    )
    return payload | dict(identity=_digest(payload))


def _seal(point):
    return replace(point, identity=checkpoint_record(point)["identity"])


def _initial(binding):
    gates = binding.gate_parameters
    values = ClockState(
        _frozen(binding.cache.definition["parameters"]["temperature_K"]),
        gates["initial_hh_m"],
        gates["initial_hh_h"],
        gates["initial_ml_m"],
    )
    return _seal(Checkpoint(binding.identity, binding.cache.identity, 0, values, None, ""))


def initialise(binding):
    validate_binding(binding)
    return _initial(binding)


def _probes(binding, temperature):
    material = binding.cache.definition
    p, ions = material["parameters"], material["ions"]
    z = ions["valence"][:, None]
    used_z = np.broadcast_to(z, (len(ions["ids"]), binding.membrane_voltage_V.size)) + NONCE
    membrane = binding.membrane_voltage_V + NONCE
    junction = binding.junction_voltage_V + NONCE
    means = np.asarray([binding.cache.coefficients.ion_mean_mol_m3[name] for name in ions["ids"]])
    configured = p["configured_temperature_K"]
    return ProbeValues(
        *(
            _frozen(value)
            for value in (
                (used_z * membrane * p["F_C_mol"]) / (p["R_J_mol_K"] * temperature),
                (used_z * junction * p["F_C_mol"]) / (p["R_J_mol_K"] * configured),
                np.broadcast_to(
                    (ions["free_diffusion_m2_s"][:, None] * z * p["q_C"])
                    / (p["kb_J_K"] * temperature),
                    used_z.shape,
                ),
                (ions["membrane_diffusion_m2_s"] * p["q_C"] * z**2 * p["F_C_mol"] * means)
                / (p["membrane_thickness_m"] * p["kb_J_K"] * configured),
                binding.cache.coefficients.sigma_cell_S_m,
                membrane,
                junction,
                used_z,
            )
        )
    )


def _gate_update(binding, old):
    g = binding.gate_parameters
    dt = binding.calendar.dt_s * g["time_unit"]
    numerator_m = g["hh_m_tau_native"] * old.hh_m + dt * g["hh_m_inf"]
    numerator_h = g["hh_h_tau_native"] * old.hh_h + dt * g["hh_h_inf"]
    denominator_m = g["hh_m_tau_native"] + dt
    denominator_h = g["hh_h_tau_native"] + dt
    ml_numerator = old.ml_m + (dt * g["Phi"] * g["ml_m_inf"] / g["ml_tau_native"])
    ml_denominator = 1 + (dt * g["Phi"] / g["ml_tau_native"])
    arithmetic = GateArithmetic(
        *(
            _frozen(value)
            for value in (
                dt,
                numerator_m,
                numerator_h,
                denominator_m,
                denominator_h,
                ml_numerator,
                ml_denominator,
            )
        )
    )
    return (
        *(
            _frozen(value)
            for value in (
                numerator_m / denominator_m,
                numerator_h / denominator_h,
                ml_numerator / ml_denominator,
            )
        ),
        arithmetic,
    )


def _raw_call(binding, point):
    calendar = binding.calendar
    i = point.call_index
    label = clocks.event_label_s(calendar, i)
    enabled = calendar.phase == "SIM"
    old = point.values
    source_state = setters.State(
        old.temperature_K,
        np.ones(len(binding.program.membrane_ids)),
        np.asarray(1.0),
        np.zeros(4),
    )
    with np.errstate(all="ignore"):
        setter = setters.apply(
            source_state,
            binding.kernel,
            np.asarray(label),
            np.asarray(binding.cache.definition["parameters"]["configured_temperature_K"]),
            np.asarray(enabled),
            xp=np,
        )
        m, h, ml, arithmetic = (
            _gate_update(binding, old) if enabled else (old.hh_m, old.hh_h, old.ml_m, None)
        )
        values = ClockState(_frozen(setter.state.temperature_K), m, h, ml)
        probes = _probes(binding, values.temperature_K)
    probabilities = all(np.all((value >= 0) & (value <= 1)) for value in values[1:])
    finite_gates = all(np.isfinite(value).all() for value in values[1:])
    if arithmetic is not None:
        finite_gates &= all(np.isfinite(value).all() for value in arithmetic)
    diagnostics = MappingProxyType(
        dict(
            source_setter_finite=bool(setter.finite),
            temperature_positive=bool(
                np.isfinite(values.temperature_K) & (values.temperature_K > 0)
            ),
            complete_probe_finite=all(np.isfinite(value).all() for value in probes),
            gate_arithmetic_finite=bool(finite_gates),
            gate_probability_domain=bool(probabilities),
            original_cache_valid=bool(binding.cache.coefficients.valid),
        )
    )
    return Trial(
        point.identity,
        i,
        label,
        i * calendar.dt_s,
        (i + 1) * calendar.dt_s,
        calendar.dt_s,
        bool(clocks.window(calendar, start=i, stop=i + 1).sampled[0]),
        enabled,
        setter,
        values,
        probes,
        arithmetic,
        binding.cache.identity,
        ORDER[1:4] + (ORDER[4],) if enabled else (ORDER[4],),
        diagnostics,
    )


def _candidate(binding, point, trial):
    return _seal(
        Checkpoint(
            binding.identity,
            binding.cache.identity,
            point.call_index + 1,
            trial.values,
            point.identity,
            "",
        )
    )


def validate(binding, point):
    """Rebuild the original source prefix, not merely the saved content hash."""
    validate_binding(binding)
    if (
        type(point) is not Checkpoint
        or type(point.call_index) is not int
        or not 0 <= point.call_index <= binding.calendar.step_count
        or point.binding_identity != binding.identity
        or point.cache_identity != binding.cache.identity
        or type(point.values) is not ClockState
    ):
        raise ValueError("Temperature checkpoint differs from original binding/cache/cursor")
    count = len(binding.program.membrane_ids)
    for i, value in enumerate(point.values):
        if (
            type(value) is not np.ndarray
            or value.dtype != np.float64
            or value.shape != (() if i == 0 else (count,))
            or not np.isfinite(value).all()
            or (np.any(value <= 0) if i == 0 else np.any((value < 0) | (value > 1)))
        ):
            raise ValueError("Temperature checkpoint has an invalid complete numeric frame")
    if point.identity != checkpoint_record(point)["identity"]:
        raise ValueError("Temperature checkpoint content association changed")
    expected = _initial(binding)
    for _ in range(point.call_index):
        trial = _raw_call(binding, expected)
        if not all(trial.diagnostics.values()):
            raise ValueError("Saved source prefix crosses an unaccepted temperature call")
        expected = _candidate(binding, expected, trial)
    if checkpoint_record(point) != checkpoint_record(expected):
        raise ValueError("Temperature checkpoint differs from the original causal source prefix")
    return point


def restore(binding, saved):
    if (
        type(saved) is not dict
        or set(saved)
        != {
            "kind",
            "binding_identity",
            "cache_identity",
            "call_index",
            "values",
            "parent_identity",
            "identity",
        }
        or saved["kind"] != CHECKPOINT_KIND
    ):
        raise ValueError("Require the complete saved source temperature checkpoint")
    validate_binding(binding)
    m = len(binding.program.membrane_ids)
    if type(saved["values"]) is not dict or set(saved["values"]) != set(ClockState._fields):
        raise ValueError("Saved temperature clock-probe frame is incomplete or extended")
    values = ClockState(
        *(
            _buffer(saved["values"][name], () if name == "temperature_K" else (m,))
            for name in ClockState._fields
        )
    )
    point = Checkpoint(
        saved["binding_identity"],
        saved["cache_identity"],
        saved["call_index"],
        values,
        saved["parent_identity"],
        saved["identity"],
    )
    validate(binding, point)
    if checkpoint_record(point) != saved:
        raise ValueError("Saved source temperature checkpoint record changed")
    return point


def advance(binding, point):
    stage, trial = "source_validation", None
    try:
        validate(binding, point)
        if point.call_index == binding.calendar.step_count:
            raise ValueError("Original source temperature calendar is exhausted")
        stage = "native_temperature_clock_probe_call"
        trial = _raw_call(binding, point)
        if not all(trial.diagnostics.values()):
            raise ValueError("Source temperature/probe proposal violates declared finite domains")
        candidate = _candidate(binding, point, trial)
        return Receipt(candidate, trial)
    except Exception as error:
        raise TemperatureCalendarRejected(error, stage=stage, source=point, trial=trial) from error


def trial_record(trial):
    """Raw records are representational; they never publish a failed call."""
    raw = trial.raw_setter
    return dict(
        parent_identity=trial.parent_identity,
        call_index=trial.call_index,
        event_label_s=trial.event_label_s,
        elapsed_start_s=trial.elapsed_start_s,
        elapsed_end_s=trial.elapsed_end_s,
        duration_s=trial.duration_s,
        sampled=trial.sampled,
        events_enabled=trial.events_enabled,
        cache_identity=trial.cache_identity,
        source_order=list(trial.source_order),
        values={key: buffer_record(value) for key, value in trial.values._asdict().items()},
        probes={key: buffer_record(value) for key, value in trial.probes._asdict().items()},
        gate_arithmetic=None
        if trial.gate_arithmetic is None
        else {key: buffer_record(value) for key, value in trial.gate_arithmetic._asdict().items()},
        raw_pulse=buffer_record(raw.pulse),
        raw_pulse_finite=np.asarray(raw.pulse_finite).tolist(),
        raw_exponential_saturated=np.asarray(raw.exponential_saturated).tolist(),
        diagnostics=dict(trial.diagnostics),
    )
