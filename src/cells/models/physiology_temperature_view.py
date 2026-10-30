"""Original-history-preserving held temperature readouts and explicit limits."""

import math
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_temperature as temperature
from cells.models import physiology_permeability_view as ordinary
from cells.models import surface_open_calcium as open_calcium
from cells.models import surface_open_calcium_energy as open_fuel
from cells.processes.electrochemistry import R

KIND = "cells.physiology_temperature_view@1"
MAX_STAGE_ENERGY_RESIDUAL_PJ_S = 1e-10
IMPLEMENTATIONS = ordinary.IMPLEMENTATIONS | {
    temperature.SurfaceOpenCalciumModel: open_calcium,
    temperature.SurfaceOpenCalciumEnergyModel: open_fuel,
}


@dataclass(frozen=True, slots=True)
class TemperatureView:
    preparation: temperature.PreparedTemperature
    runtime_layout: object
    readouts: object
    derivative: object
    thermodynamic_assumptions: object
    admission: object

    @property
    def field(self):
        return self.readouts.field if hasattr(self.readouts, "field") else self.readouts


def _functional_shift(spec, state, layout, target):
    if type(spec.model) is not temperature.SurfaceTissueModel:
        return 0.0  # The active model domain admits only exact original T.
    inside, outside = ordinary.passive.physical_amounts(state, layout)
    terms = []
    for amounts, volume, active in (
        (inside, layout.volume, layout.active),
        (outside, layout.extracellular_volume, layout.outside_active & ~layout.reservoir),
    ):
        for column in np.flatnonzero(active):
            terms.extend(
                float(amount) * (math.log(float(amount) / float(volume[column])) - 1)
                for amount in amounts[:, column]
            )
    return 1e-3 * R * float(target - spec.model.temperature_K) * math.fsum(terms)


def evaluate(
    spec, state, layout, control, binding, temperature_state, *, time_s, events_enabled, step_s
):
    """Complete instantaneous rates; a temperature change is never an accepted step."""
    temperature._spec(spec)
    if (
        not isinstance(step_s, Real)
        or isinstance(step_s, (bool, np.bool_))
        or not np.isfinite(step_s)
        or step_s <= 0
    ):
        raise ValueError("Declare a finite positive explicit held-temperature rate-view step")
    rounding = 8 * np.finfo(np.float64).eps * max(spec.experiment.end_time, spec.execution.dt)
    if step_s > spec.execution.dt + rounding:
        raise ValueError("Explicit rate-view step exceeds the source nominal timestep")
    preparation = temperature.prepare(
        spec, binding, temperature_state, time_s=time_s, events_enabled=events_enabled
    )
    implementation = IMPLEMENTATIONS[type(spec.model)]
    initial, expected = implementation.initial_values(spec)
    ordinary._exact_layout(layout, expected)
    actual = ordinary._state(state, initial)
    held = ordinary._control(spec, control)
    checks = implementation.check_values(actual, spec)
    implementation.check_steps(
        spec, np.asarray([step_s]), type(held)(*(value[None] for value in held))
    )
    runtime = type(layout)(*(np.asarray(value) for value in layout))._replace(
        temperature=preparation.state.temperature_K
    )
    if not implementation.domain_valid(actual, runtime, runtime.active, xp=np):
        raise temperature.TemperatureRejected(
            "Held T violates the original material/gate/ledger domain",
            dict(preparation=preparation),
        )
    if implementation is ordinary.passive:
        values = implementation.field_values(actual, held, runtime, xp=np)
        derivative = implementation.derivative_from_field(values, runtime, xp=np)
        field, valid = values, values.converged
    else:
        values = implementation.readouts(actual, held, runtime, xp=np)
        derivative, field, valid = values.derivative, values.field, values.valid
    trial = dict(
        preparation=preparation,
        runtime_layout=ordinary._immutable_tree(runtime),
        readouts=ordinary._immutable_tree(values),
        derivative=ordinary._immutable_tree(derivative),
    )
    if (
        not valid
        or not field.converged
        or any(not np.isfinite(value).all() for value in derivative)
        or abs(float(field.energy_balance_pJ_s)) > MAX_STAGE_ENERGY_RESIDUAL_PJ_S
    ):
        raise temperature.TemperatureRejected(
            "Held-temperature field or complete ordinary rates invalid", trial
        )
    passive_fraction = ordinary._passive_fraction(
        actual, held, runtime, field, implementation, float(step_s)
    )
    fuel_fraction = 0.0
    if implementation in (ordinary.fuel, open_fuel):
        amount = ordinary.fuel.energy_amounts(actual, runtime)
        exchange = values.parent.exchange if implementation is open_fuel else values.exchange
        gross = exchange.gross_hydrolysis_fmol_s + exchange.gross_synthesis_fmol_s
        fraction = np.where(
            runtime.active, gross / np.where(runtime.active, np.min(amount, axis=0), 1.0), 0.0
        )
        fuel_fraction = float(step_s) * float(np.max(fraction, initial=0))
    if (
        not np.isfinite([passive_fraction, fuel_fraction]).all()
        or passive_fraction > ordinary.MAX_PASSIVE_FRACTION_PER_STEP
        or fuel_fraction > ordinary.MAX_FUEL_FRACTION_PER_STEP
    ):
        raise temperature.TemperatureRejected(
            "Held T exceeds the unchanged passive/fuel turnover ceilings", trial
        )
    shift = _functional_shift(spec, actual, layout, preparation.state.temperature_K)
    if not math.isfinite(shift):
        raise temperature.TemperatureRejected(
            "Unrepresentable isothermal mixing-functional parameter shift", trial
        )
    assumptions = MappingProxyType(
        dict(
            uniform_prescribed_temperature_K=float(preparation.state.temperature_K),
            original_temperature_K=spec.model.temperature_K,
            finite_owner_mixing_functional_shift_pJ=shift,
            functional="ideal isothermal mixing Gibbs functional; reservoir references excluded",
            caloric_internal_energy_defined=False,
            heat_capacity_defined=False,
            accepted_heat_pJ=None,
            accepted_thermal_transition=False,
            thermal_scope="held readouts; no ionic, gate, history, control or clock update",
        )
    )
    admission = MappingProxyType(
        dict(
            kind=KIND,
            source_definition_sha256=spec.fingerprint,
            binding_identity=binding.identity,
            inventory=temperature.inventory(spec),
            original_balance_checks=MappingProxyType(dict(checks)),
            held_control=ordinary._immutable_tree(held),
            step_s=float(step_s),
            passive_fraction=passive_fraction,
            passive_limit=ordinary.MAX_PASSIVE_FRACTION_PER_STEP,
            fuel_fraction=fuel_fraction,
            fuel_limit=ordinary.MAX_FUEL_FRACTION_PER_STEP,
            stage_energy_limit_pJ_s=MAX_STAGE_ENERGY_RESIDUAL_PJ_S,
            accepted_thermal_stepping=False,
        )
    )
    return TemperatureView(
        preparation,
        trial["runtime_layout"],
        trial["readouts"],
        trial["derivative"],
        assumptions,
        admission,
    )
