"""Accepted ideal capacitor-only ramps with separate, complete owner histories.

The original ordinary checkpoint is immutable and retains its fixed-clamp law.
Supplemental displacement charge and work belong to this new named intervention.
No ionic, chemical, gate, thermal, random or physical-clock advance occurs.
"""

import hashlib
import math
from dataclasses import dataclass, fields, replace
from types import MappingProxyType

import numpy as np

from cells.core import physiology_boundary_voltage as boundary
from cells.core.errors import NumericalError
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import digest
from cells.core.state import Checkpoint
from cells.models import physiology_boundary_voltage_transition_algebra as algebra
from cells.models import physiology_boundary_voltage_view as held

KIND = "cells.physiology_boundary_voltage_transition@1"
DECLARATION = "cells.physiology_boundary_voltage_ramp_declaration@1"
LAW = algebra.LAW
MAX_CAPACITY = 64


@dataclass(frozen=True, slots=True)
class Ramp:
    law: str
    target_boundary_voltage_V: object
    provenance: str
    identity: str


@dataclass(frozen=True, slots=True)
class Segment:
    declaration: Ramp
    change: algebra.CapacitiveChange


@dataclass(frozen=True, slots=True)
class TransitionCheckpoint:
    numeric: Checkpoint
    binding: boundary.Binding
    control: object
    origin_boundary_state: boundary.BoundaryState
    boundary_state: boundary.BoundaryState
    segments: tuple
    cumulative_electrode_charge_C: object
    cumulative_external_work_pJ: object
    cumulative_capacitor_energy_pJ: float
    capacity: int
    provenance: str
    identity: str


@dataclass(frozen=True, slots=True)
class TransitionResult:
    checkpoint: TransitionCheckpoint
    before: held.BoundaryVoltageView
    after: held.BoundaryVoltageView
    segment: Segment
    admission: object


class TransitionRejected(NumericalError):
    def __init__(self, reason, *, source, declaration, stage, trial=None, failure=None):
        super().__init__("Ideal capacitive ramp refused at " + stage + ": " + str(reason))
        self.source, self.declaration, self.stage = source, declaration, stage
        self.trial = MappingProxyType(dict(trial or {}))
        self.failure = failure


def array_record(value):
    array = np.asarray(value)
    return dict(
        dtype=array.dtype.str,
        shape=list(array.shape),
        sha256=hashlib.sha256(array.tobytes()).hexdigest(),
    )


def _arrays(values):
    return {name: array_record(value) for name, value in values._asdict().items()}


def declaration_record(ramp):
    if type(ramp) is not Ramp:
        raise ValueError("Require a complete typed ideal-ramp declaration")
    payload = dict(
        kind=DECLARATION,
        law=ramp.law,
        target_boundary_voltage_V=np.asarray(ramp.target_boundary_voltage_V).tolist(),
        provenance=ramp.provenance,
    )
    return payload | dict(identity=digest(payload))


def declare(*, target_boundary_voltage_V, provenance, law=LAW):
    if law != LAW:
        raise ValueError("Only the explicitly named ideal fixed-inventory linear ramp is supported")
    if type(target_boundary_voltage_V) is not dict or set(target_boundary_voltage_V) != set(
        boundary.SIDES
    ):
        raise ValueError("Declare all four target side potentials by their native names")
    values = list(target_boundary_voltage_V[side] for side in boundary.SIDES)
    if any(
        isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.floating))
        for value in values
    ):
        raise ValueError("Require real target potentials, not inferred controls or boolean flags")
    values = np.asarray(values, dtype=np.float64)
    if not np.isfinite(values).all() or type(provenance) is not str or not provenance.strip():
        raise ValueError("Require finite potentials and explicit physical path provenance")
    ramp = Ramp(law, boundary._freeze(values), provenance, "")
    return replace(ramp, identity=declaration_record(ramp)["identity"])


def restore_declaration(saved):
    if type(saved) is not dict or set(saved) != {
        "kind",
        "law",
        "target_boundary_voltage_V",
        "provenance",
        "identity",
    }:
        raise ValueError("Incomplete ideal-ramp declaration")
    if saved["kind"] != DECLARATION:
        raise ValueError("Wrong intervention declaration kind")
    try:
        expected = declare(
            target_boundary_voltage_V=dict(
                zip(boundary.SIDES, saved["target_boundary_voltage_V"], strict=True)
            ),
            provenance=saved["provenance"],
            law=saved["law"],
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Malformed ideal-ramp declaration") from error
    if declaration_record(expected) != saved:
        raise ValueError("Ideal-ramp declaration differs from its complete identity")
    return expected


def _declaration(ramp):
    if type(ramp) is not Ramp:
        raise ValueError("Require a typed ideal ramp")
    restore_declaration(declaration_record(ramp))
    if ramp.identity != declaration_record(ramp)["identity"]:
        raise ValueError("Stale ideal-ramp declaration")


def change_record(change):
    return {
        row.name: array_record(getattr(change, row.name))
        if isinstance(getattr(change, row.name), np.ndarray)
        else getattr(change, row.name)
        for row in fields(algebra.CapacitiveChange)
    }


def record(point):
    if type(point) is not TransitionCheckpoint:
        raise ValueError("Require the complete typed ideal voltage-transition checkpoint")
    payload = dict(
        kind=KIND,
        law=LAW,
        numeric=dict(
            state=_arrays(point.numeric.state),
            layout=_arrays(point.numeric.layout),
            time=point.numeric.time,
            step_index=point.numeric.step_index,
            event_index=point.numeric.event_index,
        ),
        binding_identity=point.binding.identity,
        control=_arrays(point.control),
        origin_boundary_state=_arrays(point.origin_boundary_state),
        boundary_state=_arrays(point.boundary_state),
        segments=[
            dict(declaration=declaration_record(row.declaration), change=change_record(row.change))
            for row in point.segments
        ],
        cumulative_electrode_charge_C=array_record(point.cumulative_electrode_charge_C),
        cumulative_external_work_pJ=array_record(point.cumulative_external_work_pJ),
        cumulative_capacitor_energy_pJ=point.cumulative_capacitor_energy_pJ,
        capacity=point.capacity,
        provenance=point.provenance,
    )
    return payload | dict(identity=digest(payload))


def _seal(point):
    return replace(point, identity=record(point)["identity"])


def _host_numeric(numeric):
    if type(numeric) is not Checkpoint:
        raise ValueError("Require the complete original numerical checkpoint")
    # Snapshot IO restores device arrays. This intervention evaluates NumPy
    # fields and capacitor algebra, so keep every numeric leaf on the host as
    # initialization does. Copy exact bytes; retain all original anchors/clocks.
    return replace(
        numeric,
        state=held.ordinary._immutable_tree(numeric.state),
        layout=held.ordinary._immutable_tree(numeric.layout),
    )


def _view(spec, point, memory):
    return held.evaluate(
        spec,
        point.numeric.state,
        point.numeric.layout,
        point.control,
        point.binding,
        memory,
        time_s=point.numeric.time,
        events_enabled=False,
        step_s=spec.execution.dt / 16,
    )


def _same(actual, expected, name):
    if array_record(actual) != array_record(expected):
        raise ValueError("Ideal transition has stale/replaced " + name)


def _base(spec, point):
    if type(point) is not TransitionCheckpoint or type(point.numeric) is not Checkpoint:
        raise ValueError("Require the complete original numerical checkpoint")
    if point.identity != record(point)["identity"]:
        raise ValueError("Ideal transition checkpoint association changed")
    if (
        type(point.capacity) is not int
        or not 0 <= len(point.segments) <= point.capacity <= MAX_CAPACITY
    ):
        raise ValueError("Invalid declared ideal-ramp history capacity")
    if (
        type(point.segments) is not tuple
        or type(point.provenance) is not str
        or not point.provenance.strip()
    ):
        raise ValueError("Declare complete immutable segment history and provenance")
    validate_checkpoint(spec, point.numeric)
    boundary.restore(boundary.record(point.binding), spec)
    ordinary = control_values(spec, [point.numeric.time])
    expected = type(ordinary)(*(value[0] for value in ordinary))
    if type(point.control) is not type(expected):
        raise ValueError("Original scheduled control type changed")
    for key in expected._fields:
        _same(getattr(point.control, key), getattr(expected, key), "scheduled control " + key)
    _same(
        point.origin_boundary_state.boundary_voltage_V,
        boundary.initial_state(spec, point.binding).boundary_voltage_V,
        "origin side memory",
    )


def validate(spec, point):
    """Reconstruct every accepted segment from its declaration and original state."""
    _base(spec, point)
    before = _view(spec, point, point.origin_boundary_state)
    origin = before
    for segment in point.segments:
        if type(segment) is not Segment or type(segment.change) is not algebra.CapacitiveChange:
            raise ValueError("Require complete typed ideal ramp segments")
        _declaration(segment.declaration)
        memory = boundary.BoundaryState(segment.declaration.target_boundary_voltage_V)
        after = _view(spec, point, memory)
        expected = algebra.derive(point.numeric.layout, before, after)
        if not expected.valid or digest(change_record(expected)) != digest(
            change_record(segment.change)
        ):
            raise ValueError(
                "Saved segment differs from its original incremental capacitor/work law"
            )
        before = after
    _same(
        point.boundary_state.boundary_voltage_V,
        before.preparation.boundary_state.boundary_voltage_V,
        "current side memory",
    )
    charge, work, energy = algebra.cumulative(
        point.segments, point.numeric.layout.outside_active.size
    )
    _same(point.cumulative_electrode_charge_C, charge, "cumulative displacement charge")
    _same(point.cumulative_external_work_pJ, work, "cumulative external work")
    if (
        type(point.cumulative_capacitor_energy_pJ) is not float
        or point.cumulative_capacitor_energy_pJ != energy
    ):
        raise ValueError("Cumulative capacitor change differs from compensated segment history")
    endpoint = algebra.derive(point.numeric.layout, origin, before)
    charge_budget = 3e-25 + 2e-12 * abs(endpoint.electrode_charge_change_C)
    charge_error = float(
        np.max(abs(charge - endpoint.electrode_charge_change_C) / charge_budget, initial=0)
    )
    work_residual = math.fsum((energy, *(-float(value) for value in work)))
    energy_residual = math.fsum((energy, -endpoint.capacitor_energy_change_pJ))
    budget = algebra.WORK_ATOL_PJ + algebra.WORK_RTOL * math.fsum(
        (abs(energy), *(abs(float(value)) for value in work))
    )
    if (
        not endpoint.valid
        or charge_error > 1
        or max(abs(work_residual), abs(energy_residual)) > budget
    ):
        raise ValueError(
            "Cumulative transition histories violate the original-owner endpoint identities"
        )
    return before


def initialise(spec, numeric, binding, *, capacity=64, provenance):
    validate_checkpoint(spec, numeric)
    boundary.restore(boundary.record(binding), spec)
    frozen = _host_numeric(numeric)
    table = control_values(spec, [numeric.time])
    control = held.ordinary._immutable_tree(type(table)(*(value[0] for value in table)))
    memory = boundary.initial_state(spec, binding)
    zero = boundary._freeze(np.zeros(spec.execution.extracellular_capacity))
    point = _seal(
        TransitionCheckpoint(
            frozen, binding, control, memory, memory, (), zero, zero, 0.0, capacity, provenance, ""
        )
    )
    validate(spec, point)
    return point


def restore(
    saved,
    spec,
    numeric,
    binding,
    control,
    origin_boundary_state,
    boundary_state,
    segments,
    cumulative_electrode_charge_C,
    cumulative_external_work_pJ,
):
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require the complete saved ideal-transition association")
    point = TransitionCheckpoint(
        _host_numeric(numeric),
        binding,
        control,
        origin_boundary_state,
        boundary_state,
        tuple(segments),
        cumulative_electrode_charge_C,
        cumulative_external_work_pJ,
        saved.get("cumulative_capacitor_energy_pJ"),
        saved.get("capacity"),
        saved.get("provenance"),
        saved.get("identity"),
    )
    validate(spec, point)
    if record(point) != saved:
        raise ValueError("Saved ideal-transition record differs from its complete original fields")
    return point


def advance(spec, point, declaration):
    stage, trial = "parent_admission", {}
    try:
        before = validate(spec, point)
        stage = "declaration"
        _declaration(declaration)
        if len(point.segments) >= point.capacity:
            raise ValueError("Declared ramp history capacity is exhausted")
        stage = "held_endpoint"
        memory = boundary.BoundaryState(declaration.target_boundary_voltage_V)
        after = _view(spec, point, memory)
        trial.update(before=before, after=after)
        stage = "incremental_capacitor_work"
        change = algebra.derive(point.numeric.layout, before, after)
        trial["change"] = change
        if not change.valid:
            raise ValueError(
                "Declared ideal ramp fails incremental charge, endpoint or work identity"
            )
        segment = Segment(declaration, change)
        segments = (*point.segments, segment)
        charge, work, energy = algebra.cumulative(
            segments, point.numeric.layout.outside_active.size
        )
        proposed = _seal(
            replace(
                point,
                boundary_state=after.preparation.boundary_state,
                segments=segments,
                cumulative_electrode_charge_C=charge,
                cumulative_external_work_pJ=work,
                cumulative_capacitor_energy_pJ=energy,
            )
        )
        stage = "accepted_association"
        trial["checkpoint"] = proposed
        validate(spec, proposed)
        admission = MappingProxyType(
            dict(
                law=LAW,
                path_coordinate="dimensionless linear ramp; no physical duration",
                source_definition_sha256=spec.fingerprint,
                parent_identity=point.identity,
                accepted_segments=len(segments),
                ionic_time_s=point.numeric.time,
                numeric_step_index=point.numeric.step_index,
                controls_unchanged=True,
                ionic_gates_inventories_clocks_unchanged=True,
                native_transition_claim=False,
                ionic_evolution=False,
                heat_added=False,
                partial_acceptance=False,
            )
        )
        return TransitionResult(proposed, before, after, segment, admission)
    except Exception as error:
        if isinstance(error, boundary.BoundaryVoltageRejected):
            trial["held_refusal"] = error.trial
        raise TransitionRejected(
            error, source=point, declaration=declaration, stage=stage, trial=trial, failure=error
        ) from error
