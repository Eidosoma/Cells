"""Read-only ordinary RHS view with explicit physiological passive permeability.

Only the passive membrane P array changes. The accepted state, all anchors,
active channel/pump parameters and component clocks stay owned by the caller.
Admission reuses original domain/balance/step checks and adds actual passive
and finite-fuel gross-turnover ceilings. This host view performs no integration.
"""

from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType

import jax
import numpy as np

from cells.core import physiology_tissue_binding as units
from cells.core import surface_calcium_energy_spec as fuel_spec
from cells.core import surface_calcium_spec as calcium_spec
from cells.core import surface_kinetic_spec as ionic_spec
from cells.core import surface_tissue_spec as passive_spec
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import SimulationSpec
from cells.models import surface_calcium_energy_hcn_extra as fuel
from cells.models import surface_calcium_hcn_extra as calcium
from cells.models import surface_hcn_extra as ionic
from cells.models import surface_tissue as passive
from cells.numerics import surface_transport
from cells.numerics.extracellular_field import scatter

KIND = "cells.physiology_permeability_view@1"
MAX_PASSIVE_FRACTION_PER_STEP = 0.05
MAX_FUEL_FRACTION_PER_STEP = 0.05
IMPLEMENTATIONS = {
    passive_spec.SurfaceTissueModel: passive,
    ionic_spec.SurfaceHCNExtraModel: ionic,
    calcium_spec.SurfaceCalciumHCNExtraModel: calcium,
    fuel_spec.SurfaceCalciumEnergyHCNExtraModel: fuel,
}


def _freeze(value):
    value = np.asarray(value)
    shape = value.shape
    value = np.ascontiguousarray(value)
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(shape)


def _immutable_tree(value):
    return jax.tree.map(_freeze, value)


@dataclass(frozen=True, slots=True)
class PermeabilityView:
    runtime_layout: object
    readouts: object
    derivative: object
    physical_permeability: units.PhysicalPermeability
    admission: object

    @property
    def field(self):
        return self.readouts.field if hasattr(self.readouts, "field") else self.readouts


def _exact_layout(actual, expected):
    if type(actual) is not type(expected):
        raise ValueError("Require the exact ordinary source layout type")
    for name, template in expected._asdict().items():
        value = np.asarray(getattr(actual, name))
        if (
            value.shape != template.shape
            or value.dtype != template.dtype
            or not np.array_equal(value, template)
        ):
            raise ValueError("Source layout owner/geometry/anchor/parameter mismatch: " + name)


def _state(actual, expected):
    if type(actual) is not type(expected):
        raise ValueError("Require the complete exact ordinary state type")
    values = []
    for name, template in expected._asdict().items():
        value = np.asarray(getattr(actual, name))
        if (
            value.shape != template.shape
            or value.dtype != template.dtype
            or not np.isfinite(value).all()
        ):
            raise ValueError("Invalid complete ordinary state shape/precision/domain: " + name)
        values.append(value)
    return type(actual)(*values)


def _control(spec, actual):
    table = control_values(spec, [0.0])
    if type(actual) is not type(table):
        raise ValueError("Require the exact ordinary actual-control type")
    values = []
    for name, rows in table._asdict().items():
        template, value = rows[0], np.asarray(getattr(actual, name))
        if (
            value.shape != template.shape
            or value.dtype != template.dtype
            or not np.isfinite(value).all()
            or np.any((value < 0) | (value > 1))
        ):
            raise ValueError("Invalid actual control shape/precision/availability: " + name)
        values.append(value)
    return type(actual)(*values)


def _admission_spec(spec, permeability):
    # This declaration is used ONLY by the original validators. Anchors, gates,
    # channels, pumps, controls and clocks remain the caller's declarations.
    membranes = tuple(
        replace(row, permeability_m_per_s=tuple(permeability[:, i]))
        for i, row in enumerate(spec.model.membranes)
    )
    return replace(spec, model=replace(spec.model, membranes=membranes))


def _passive_fraction(state, control, layout, field, implementation, step_s):
    inside, outside = implementation.physical_amounts(state, layout)
    ci = np.where(layout.active, inside / layout.volume, 1.0)
    co = np.where(layout.outside_active, outside / layout.extracellular_volume, 1.0)
    junction = control.junction
    if hasattr(state, "junction_gate"):
        junction = junction * state.junction_gate
    size = layout.active.size
    topology = surface_transport.Layout(
        *(getattr(layout, key) for key in surface_transport.Layout._fields)
    )
    rates = surface_transport.transport(
        ci,
        co,
        field.potential_V[:size],
        field.potential_V[size:],
        control.membrane,
        junction,
        topology,
        xp=np,
    )
    if not rates.valid:
        raise NumericalError("Mapped passive transport leaves the actual physical domain")
    gross = np.abs(rates.membrane_flux_fmol_s)
    cell = scatter(gross, inside, (layout.membrane_cell,), xp=np)
    exterior = scatter(gross, outside, (layout.membrane_outside,), xp=np)
    # Reservoirs own held chemical supply, so only finite exterior stocks enter
    # the depletion ceiling. All actual cell free-ion stocks remain explicit.
    exterior_active = layout.outside_active & ~layout.reservoir
    cell_fraction = np.where(layout.active, cell / np.where(layout.active, inside, 1.0), 0.0)
    outside_fraction = np.where(
        exterior_active, exterior / np.where(exterior_active, outside, 1.0), 0.0
    )
    return step_s * max(
        float(np.max(cell_fraction, initial=0)), float(np.max(outside_fraction, initial=0))
    )


def evaluate(spec, state, layout, control, binding, component, *, step_s):
    """Admit and evaluate one read-only actual-control ordinary RHS view.

    ``step_s`` is explicit, independent of the component loop dt/clock. It
    cannot exceed the source nominal step except for clock representation
    roundoff, and must pass inherited method/loss and current turnover checks.
    The returned runtime layout must not overwrite a numeric checkpoint.
    """
    if type(spec) is not SimulationSpec or type(spec.model) not in IMPLEMENTATIONS:
        raise ValueError("Permeability views require the four exact ordinary tissue families")
    if (
        not isinstance(step_s, Real)
        or isinstance(step_s, (bool, np.bool_))
        or not np.isfinite(step_s)
        or step_s <= 0
    ):
        raise ValueError("Declare a finite positive explicit tissue step")
    step_s = float(step_s)
    rounding = 8 * np.finfo(np.float64).eps * max(spec.experiment.end_time, spec.execution.dt)
    if step_s > spec.execution.dt + rounding:
        raise ValueError("Explicit tissue step exceeds the original source nominal timestep")
    units.validate_binding(binding)
    # Reconstruct from actual source declarations, rather than trusting cached
    # geometry/unit claims that could have been resealed with a new checksum.
    units.restore_binding(units.binding_record(binding), spec)
    implementation = IMPLEMENTATIONS[type(spec.model)]
    initial, expected = implementation.initial_values(spec)
    _exact_layout(layout, expected)
    actual = _state(state, initial)
    held = _control(spec, control)
    physical = units.component_permeability(component, binding)
    runtime = type(layout)(*(np.asarray(value) for value in layout))._replace(
        membrane_permeability=physical.current_m_s
    )
    admission_spec = _admission_spec(spec, physical.current_m_s)
    _, projected = implementation.initial_values(admission_spec)
    for key in expected._fields:
        if key != "membrane_permeability" and not np.array_equal(
            getattr(projected, key), getattr(expected, key)
        ):
            raise ValueError("Mapped permeability would require another layout parameter change")
    # Do not reinterpret P=0 as a temporary gate: the original structural
    # support rule still refuses nonzero past transfers on an absent route.
    if not implementation.domain_valid(actual, runtime, runtime.active, xp=np):
        raise NumericalError("Mapped permeability violates the original state/ledger domain")
    diagnostics = implementation.check_values(actual, admission_spec)
    table = type(held)(*(value[None] for value in held))
    implementation.check_steps(admission_spec, np.asarray([step_s]), table)
    if not implementation.control_domain_valid(actual, held, runtime, runtime.active, xp=np):
        raise NumericalError("Mapped permeability fails the actual-control field/domain")
    if implementation is passive:
        values = implementation.field_values(actual, held, runtime, xp=np)
        derivative = implementation.derivative_from_field(values, runtime, xp=np)
        field = values
    else:
        values = implementation.readouts(actual, held, runtime, xp=np)
        derivative, field = values.derivative, values.field
    if not field.converged or any(not np.isfinite(value).all() for value in derivative):
        raise NumericalError("Mapped permeability produced invalid full ordinary rates")
    passive_fraction = _passive_fraction(actual, held, runtime, field, implementation, step_s)
    pool_fraction = 0.0
    if implementation is fuel:
        amount = fuel.energy_amounts(actual, runtime)
        gross = values.exchange.gross_hydrolysis_fmol_s + values.exchange.gross_synthesis_fmol_s
        fraction = np.where(
            runtime.active, gross / np.where(runtime.active, np.min(amount, axis=0), 1.0), 0.0
        )
        pool_fraction = step_s * float(np.max(fraction, initial=0))
    if (
        not np.isfinite([passive_fraction, pool_fraction]).all()
        or passive_fraction > MAX_PASSIVE_FRACTION_PER_STEP
        or pool_fraction > MAX_FUEL_FRACTION_PER_STEP
    ):
        raise NumericalError("Explicit step exceeds actual passive/fuel gross-turnover ceiling")
    admission = MappingProxyType(
        dict(
            kind=KIND,
            source_definition_sha256=binding.source_definition_sha256,
            binding_identity=binding.identity,
            step_s=step_s,
            held_control=_immutable_tree(held),
            passive_fraction=passive_fraction,
            passive_limit=MAX_PASSIVE_FRACTION_PER_STEP,
            fuel_fraction=pool_fraction,
            fuel_limit=MAX_FUEL_FRACTION_PER_STEP,
            original_balance_checks=MappingProxyType(dict(diagnostics)),
            component_time_s=component.time_s,
            component_loop_calls=component.loop_calls,
            component_stream_tick=component.stream.next_tick,
            scope="explicit held-control view; no clock synchronization proof or automatic updates",
        )
    )
    return PermeabilityView(
        _immutable_tree(runtime),
        _immutable_tree(values),
        _immutable_tree(derivative),
        physical,
        admission,
    )
