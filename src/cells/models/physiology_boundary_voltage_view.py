"""Complete ordinary readouts at explicit held reservoir clamp voltages.

Only boundary_V changes in the temporary layout. Original state, electrostatic
anchors, material/energy histories and all controls remain intact. Frozen-ion
capacitor changes are reported separately, never injected into accepted ledgers.
This API deliberately supplies no transition or accepted stepping operation.
"""

from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_boundary_voltage as voltage
from cells.models import physiology_permeability_view as ordinary
from cells.models import surface_open_calcium as open_calcium
from cells.models import surface_open_calcium_energy as open_fuel

KIND = "cells.physiology_boundary_voltage_view@1"
MAX_STAGE_ENERGY_RESIDUAL_PJ_S = 1e-10
IMPLEMENTATIONS = ordinary.IMPLEMENTATIONS | {
    voltage.SurfaceOpenCalciumModel: open_calcium,
    voltage.SurfaceOpenCalciumEnergyModel: open_fuel,
}


@dataclass(frozen=True, slots=True)
class BoundaryVoltageView:
    preparation: voltage.PreparedVoltage
    runtime_layout: object
    readouts: object
    derivative: object
    capacitor_change: object
    admission: object

    @property
    def field(self):
        return self.readouts.field if hasattr(self.readouts, "field") else self.readouts


def _readouts(implementation, state, control, layout):
    if implementation is ordinary.passive:
        field = implementation.field_values(state, control, layout, xp=np)
        return field, implementation.derivative_from_field(field, layout, xp=np), field.converged
    result = implementation.readouts(state, control, layout, xp=np)
    return result, result.derivative, result.valid


def _field(values):
    return values.field if hasattr(values, "field") else values


def _capacitor_change(before, after, original, runtime):
    """Endpoint algebra, conditional on frozen ions and linear capacitor response.

    The trapezoidal expression is the work of an *ideal linear capacitive ramp*
    at fixed free charges. It is not inferred from BETSE's sample/hold setter or
    a finite-time physiological ramp. No dissipated heat or accepted jump follows.
    """
    old, new = _field(before), _field(after)
    delta_vm = new.rates.membrane_voltage_V - old.rates.membrane_voltage_V
    delta_q = new.electrode_charge_C - old.electrode_charge_C
    delta_energy = 0.5e12 * np.sum(
        runtime.membrane_capacitance
        * delta_vm
        * (new.rates.membrane_voltage_V + old.rates.membrane_voltage_V)
    )
    ramp_work = 0.5e12 * np.sum((original.boundary_V + runtime.boundary_V) * delta_q)
    return MappingProxyType(
        dict(
            electrode_charge_change_C=ordinary._freeze(delta_q),
            membrane_voltage_change_V=ordinary._freeze(delta_vm),
            capacitor_energy_change_pJ=float(delta_energy),
            conditional_linear_capacitive_ramp_work_pJ=float(ramp_work),
            conditional_work_residual_pJ=float(delta_energy - ramp_work),
            scope="frozen-inventory endpoint algebra; no adopted transition, heat or ledger update",
        )
    )


def evaluate(
    spec,
    state,
    layout,
    control,
    binding,
    boundary_state,
    *,
    time_s,
    events_enabled,
    step_s,
):
    """Check original history, then evaluate complete rates with clamps held fixed.

    step_s retains inherited numerical and gross-turnover bounds for this rate
    view; it does not establish an accepted transition to the changed voltage.
    A caller cannot publish the temporary layout as an ordinary checkpoint.
    """
    voltage._spec(spec)
    if (
        not isinstance(step_s, Real)
        or isinstance(step_s, (bool, np.bool_))
        or not np.isfinite(step_s)
        or step_s <= 0
    ):
        raise ValueError("Declare a finite positive explicit tissue rate-view step")
    step_s = float(step_s)
    rounding = 8 * np.finfo(np.float64).eps * max(spec.experiment.end_time, spec.execution.dt)
    if step_s > spec.execution.dt + rounding:
        raise ValueError("Explicit rate-view step exceeds the source nominal timestep")
    prepared = voltage.prepare(
        spec, binding, boundary_state, time_s=time_s, events_enabled=events_enabled
    )
    implementation = IMPLEMENTATIONS[type(spec.model)]
    initial, expected = implementation.initial_values(spec)
    ordinary._exact_layout(layout, expected)
    actual = ordinary._state(state, initial)
    held = ordinary._control(spec, control)
    # Check the accepted history against its actual original clamp/anchor law.
    # Reinitializing under the new voltage would silently replace that law.
    checks = implementation.check_values(actual, spec)
    table = type(held)(*(value[None] for value in held))
    implementation.check_steps(spec, np.asarray([step_s]), table)
    runtime = type(layout)(*(np.asarray(value) for value in layout))._replace(
        boundary_V=prepared.boundary_V
    )
    if not implementation.domain_valid(actual, runtime, runtime.active, xp=np):
        raise voltage.BoundaryVoltageRejected(
            "Held-voltage state leaves the original material/ledger domain",
            dict(preparation=prepared),
        )
    before, _, before_ok = _readouts(implementation, actual, held, layout)
    values, derivative, ok = _readouts(implementation, actual, held, runtime)
    field = _field(values)
    trial = dict(
        preparation=prepared,
        runtime_layout=ordinary._immutable_tree(runtime),
        readouts=ordinary._immutable_tree(values),
        derivative=ordinary._immutable_tree(derivative),
    )
    if (
        not before_ok
        or not ok
        or not field.converged
        or any(not np.isfinite(value).all() for value in derivative)
        or abs(float(field.energy_balance_pJ_s)) > MAX_STAGE_ENERGY_RESIDUAL_PJ_S
    ):
        raise voltage.BoundaryVoltageRejected(
            "Held-voltage field or full ordinary rates invalid", trial
        )
    passive_fraction = ordinary._passive_fraction(
        actual, held, runtime, field, implementation, step_s
    )
    fuel_fraction = 0.0
    if implementation in (ordinary.fuel, open_fuel):
        amount = ordinary.fuel.energy_amounts(actual, runtime)
        exchange = values.parent.exchange if implementation is open_fuel else values.exchange
        gross = exchange.gross_hydrolysis_fmol_s + exchange.gross_synthesis_fmol_s
        fraction = np.where(
            runtime.active, gross / np.where(runtime.active, np.min(amount, axis=0), 1.0), 0.0
        )
        fuel_fraction = step_s * float(np.max(fraction, initial=0))
    if (
        not np.isfinite([passive_fraction, fuel_fraction]).all()
        or passive_fraction > ordinary.MAX_PASSIVE_FRACTION_PER_STEP
        or fuel_fraction > ordinary.MAX_FUEL_FRACTION_PER_STEP
    ):
        raise voltage.BoundaryVoltageRejected(
            "Held voltage exceeds the unchanged passive/fuel gross-turnover ceiling", trial
        )
    change = _capacitor_change(before, values, layout, runtime)
    if not np.isfinite(
        [change["capacitor_energy_change_pJ"], change["conditional_linear_capacitive_ramp_work_pJ"]]
    ).all():
        raise voltage.BoundaryVoltageRejected(
            "Unrepresentable frozen-inventory capacitor change", trial
        )
    admission = MappingProxyType(
        dict(
            kind=KIND,
            source_definition_sha256=spec.fingerprint,
            binding_identity=binding.identity,
            held_control=ordinary._immutable_tree(held),
            step_s=step_s,
            passive_fraction=passive_fraction,
            passive_limit=ordinary.MAX_PASSIVE_FRACTION_PER_STEP,
            fuel_fraction=fuel_fraction,
            fuel_limit=ordinary.MAX_FUEL_FRACTION_PER_STEP,
            original_balance_checks=MappingProxyType(dict(checks)),
            stage_energy_limit_pJ_s=MAX_STAGE_ENERGY_RESIDUAL_PJ_S,
            accepted_stepping=False,
            scope="complete held-clamp rates; no physical voltage transition accepted",
        )
    )
    return BoundaryVoltageView(
        prepared,
        trial["runtime_layout"],
        trial["readouts"],
        trial["derivative"],
        change,
        admission,
    )
