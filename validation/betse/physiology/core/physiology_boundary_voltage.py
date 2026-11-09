"""Explicit native side setters bound to actual electrical reservoir owners.

A named side is a declaration, never a geometric inference. An owner at two
corners must receive the same voltage from both sides. Numerical gauges are
not electrodes. This module samples setters without accepting a physical step.
"""

import math
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import SimulationSpec, digest
from cells.core.surface_calcium_energy_spec import SurfaceCalciumEnergyHCNExtraModel
from cells.core.surface_calcium_spec import SurfaceCalciumHCNExtraModel
from cells.core.surface_kinetic_spec import SurfaceHCNExtraModel
from cells.core.surface_open_calcium_energy_spec import SurfaceOpenCalciumEnergyModel
from cells.core.surface_open_calcium_spec import SurfaceOpenCalciumModel
from cells.core.surface_tissue_spec import SurfaceTissueModel
from cells.processes import betse_global_controls as source

KIND = "cells.physiology_boundary_voltage_binding@1"
SIDES = source.SIDES
MODEL_TYPES = (
    SurfaceTissueModel,
    SurfaceHCNExtraModel,
    SurfaceCalciumHCNExtraModel,
    SurfaceCalciumEnergyHCNExtraModel,
    SurfaceOpenCalciumModel,
    SurfaceOpenCalciumEnergyModel,
)


def _freeze(value):
    value = np.asarray(value)
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


@dataclass(frozen=True, slots=True)
class Binding:
    source_definition_sha256: str
    program: source.Program
    boundary_reservoir_ids: tuple  # Ordered (side, ordered reservoir IDs) rows.
    provenance: str
    identity: str


class BoundaryState(NamedTuple):
    boundary_voltage_V: object  # top, bottom, left, right; native setter memory.


@dataclass(frozen=True, slots=True)
class PreparedVoltage:
    boundary_state: BoundaryState
    boundary_V: object  # Full ordinary outside axis, including neutral padding.
    source_values: source.Values
    binding_identity: str
    event_time_s: float
    events_enabled: bool


class BoundaryVoltageRejected(NumericalError):
    """Refusal with immutable source proposals; the caller still owns the parent."""

    def __init__(self, reason, trial):
        super().__init__(reason)
        self.trial = MappingProxyType(dict(trial))


def _spec(spec):
    if type(spec) is not SimulationSpec or type(spec.model) not in MODEL_TYPES:
        raise ValueError(
            "Boundary voltages require exact ordinary passive/ionic/calcium/fuel models"
        )
    return spec


def record(binding):
    if type(binding) is not Binding:
        raise ValueError("Require the complete typed boundary-voltage binding")
    payload = dict(
        kind=KIND,
        source_definition_sha256=binding.source_definition_sha256,
        program=source.record(binding.program),
        boundary_reservoir_ids=[
            [side, list(owners)] for side, owners in binding.boundary_reservoir_ids
        ],
        provenance=binding.provenance,
    )
    return payload | dict(identity=digest(payload))


def bind(spec, program, *, boundary_reservoir_ids, provenance):
    """Bind all four named sides; empty sides are explicit and cannot be driven.

    Multiple sides may name a corner reservoir, but prepare() refuses conflicting
    writes. Unmapped reservoirs retain the original declared clamp potential.
    Finite outside owners and a closed world's gauge cannot become electrodes.
    """
    _spec(spec)
    source.validate(program)
    if program.membrane_ids != tuple(row.id for row in spec.model.membranes):
        raise ValueError("Native setter axes must match the complete source membrane order")
    if any(row.kind != "voltage" for row in program.events):
        raise ValueError("Boundary-voltage bindings accept only the source voltage setter")
    if type(provenance) is not str or not provenance.strip():
        raise ValueError("Declare the source of the actual side-to-reservoir association")
    if type(boundary_reservoir_ids) is not dict or set(boundary_reservoir_ids) != set(SIDES):
        raise ValueError("Explicitly declare actual owners for all four native boundaries")
    outside = {row.id: row for row in spec.model.extracellular}
    rows = []
    for side in SIDES:
        owners = boundary_reservoir_ids[side]
        if (
            not isinstance(owners, (tuple, list))
            or any(type(name) is not str or name not in outside for name in owners)
            or len(set(owners)) != len(owners)
        ):
            raise ValueError("Each side requires unique actual outside owner IDs")
        if any(not outside[name].reservoir for name in owners):
            raise ValueError("Boundary owners must be physical reservoirs; gauges are not clamps")
        rows.append((side, tuple(owners)))
    mapping = dict(rows)
    for event in program.events:
        if not mapping[event.positive_boundary] or not mapping[event.negative_boundary]:
            raise ValueError("Both source voltage boundaries require explicit reservoir owners")
    result = Binding(spec.fingerprint, program, tuple(rows), provenance, "")
    return replace(result, identity=record(result)["identity"])


def restore(saved, spec):
    if type(saved) is not dict or saved.get("kind") != KIND:
        raise ValueError("Require the complete saved boundary-voltage binding")
    try:
        program = source.restore(saved["program"], expected_identity=saved["program"]["identity"])
        rows = saved["boundary_reservoir_ids"]
        if not isinstance(rows, list) or any(
            not isinstance(row, list) or len(row) != 2 for row in rows
        ):
            raise ValueError("Malformed saved side ownership")
        mapping = {side: owners for side, owners in rows}
        if len(mapping) != len(rows):
            raise ValueError("Duplicate saved boundary name")
        expected = bind(
            spec, program, boundary_reservoir_ids=mapping, provenance=saved["provenance"]
        )
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed saved boundary-voltage binding") from error
    if record(expected) != saved:
        raise ValueError("Boundary binding differs from its complete original source/owners")
    return expected


def _binding(spec, binding):
    if type(binding) is not Binding or binding.identity != record(binding)["identity"]:
        raise ValueError("Stale boundary-voltage binding")
    restore(record(binding), spec)


def initial_state(spec, binding):
    """Read native side memory from declared clamps, without resetting any state."""
    _binding(spec, binding)
    outside = {row.id: row.boundary_potential_V for row in spec.model.extracellular}
    values = []
    for _, owners in binding.boundary_reservoir_ids:
        voltages = [outside[name] for name in owners]
        if voltages and any(value != voltages[0] for value in voltages):
            raise ValueError("One native side cannot represent inconsistent initial owner voltages")
        values.append(voltages[0] if voltages else 0.0)
    return BoundaryState(_freeze(np.asarray(values, dtype=np.float64)))


def prepare(spec, binding, boundary_state, *, time_s, events_enabled):
    """Sample ordered source writes, then reconcile named physical corner owners.

    Source negative-after-positive writes on the *same side* remain intact. A
    reservoir shared by different sides has no implicit last-side priority.
    No clock, charge, energy ledger, random stream or accepted state is updated.
    """
    _binding(spec, binding)
    if (
        not isinstance(time_s, Real)
        or isinstance(time_s, (bool, np.bool_))
        or not math.isfinite(time_s)
        or type(events_enabled) is not bool
    ):
        raise ValueError("Declare a finite source event label and an explicit enable flag")
    if type(boundary_state) is not BoundaryState:
        raise ValueError("Require the complete typed native boundary state")
    current = np.asarray(boundary_state.boundary_voltage_V)
    if current.dtype != np.float64 or current.shape != (4,) or not np.isfinite(current).all():
        raise ValueError("Native boundary memory requires four finite float64 voltages")
    original = source.State(
        np.asarray(spec.model.temperature_K),
        np.ones(len(binding.program.membrane_ids)),
        np.asarray(1.0),
        current,
    )
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        values = source.apply(
            original,
            source.compile_program(binding.program),
            np.asarray(time_s, dtype=np.float64),
            np.asarray(spec.model.temperature_K),
            events_enabled,
            xp=np,
        )
    frozen_values = source.Values(
        source.State(*(_freeze(value) for value in values.state)),
        *(_freeze(value) for value in values[1:]),
    )
    trial = dict(source_values=frozen_values)
    if not values.physical_domain:
        raise BoundaryVoltageRejected(
            "Source voltage setter produced a nonphysical proposal", trial
        )
    proposed = np.zeros(spec.execution.extracellular_capacity, dtype=np.float64)
    outside = {row.id: i for i, row in enumerate(spec.model.extracellular)}
    proposed[: len(outside)] = [row.boundary_potential_V for row in spec.model.extracellular]
    writes = {}
    conflicts = []
    for index, (side, owners) in enumerate(binding.boundary_reservoir_ids):
        for name in owners:
            voltage = values.state.boundary_voltage_V[index]
            if name in writes and voltage != writes[name][1]:
                conflicts.append((name, writes[name][0], side))
            writes[name] = (side, voltage)
    for name, (_, voltage) in writes.items():
        proposed[outside[name]] = voltage
    trial.update(boundary_V=_freeze(proposed), conflicting_owners=tuple(conflicts))
    if conflicts:
        raise BoundaryVoltageRejected(
            "Different native sides prescribe conflicting corner voltages", trial
        )
    return PreparedVoltage(
        BoundaryState(frozen_values.state.boundary_voltage_V),
        _freeze(proposed),
        frozen_values,
        binding.identity,
        float(time_s),
        events_enabled,
    )
