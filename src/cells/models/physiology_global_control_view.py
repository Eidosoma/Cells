"""One full held-rate evaluation after simultaneous ordered native setters."""

from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_global_control_view as controls
from cells.core.runner import validate_checkpoint
from cells.core.state import Checkpoint
from cells.models import physiology_active_temperature_view as active
from cells.models import physiology_permeability_view as ordinary
from cells.models import physiology_temperature_view as thermal

KIND = "cells.physiology_global_control_view@1"
IMPLEMENTATIONS = thermal.IMPLEMENTATIONS


@dataclass(frozen=True, slots=True)
class GlobalControlView:
    preparation: controls.Preparation
    runtime_layout: object
    readouts: object
    derivative: object
    original_clock: tuple
    admission: object
    assumptions: object

    @property
    def field(self):
        return self.readouts.field if hasattr(self.readouts, "field") else self.readouts


def evaluate(
    spec, checkpoint, base_control, binding, memory, *, event_time_s, events_enabled, step_s
):
    """Validate an original checkpoint, sample setters, then solve once at hold.

    Accepted physical time/step/event indices remain unchanged. event_time_s
    labels native setter sampling and is never inferred from the physical clock.
    """
    controls._spec(spec)
    if type(checkpoint) is not Checkpoint:
        raise ValueError("Combined held views require the complete original physical checkpoint")
    if (
        not isinstance(step_s, Real)
        or isinstance(step_s, (bool, np.bool_))
        or not np.isfinite(step_s)
        or step_s <= 0
    ):
        raise ValueError("Declare a finite positive held-rate admissibility step")
    rounding = 8 * np.finfo(np.float64).eps * max(spec.experiment.end_time, spec.execution.dt)
    if step_s > spec.execution.dt + rounding:
        raise ValueError("Combined held-rate step exceeds the original nominal step")
    implementation = IMPLEMENTATIONS[type(spec.model)]
    initial, expected = implementation.initial_values(spec)
    ordinary._exact_layout(checkpoint.layout, expected)
    state = ordinary._state(checkpoint.state, initial)
    # Normalize the complete tree once: restored device-backed layouts must not
    # dispatch later NumPy ER gathers into JAX or replace any exact anchor bit.
    layout = type(checkpoint.layout)(*(np.asarray(value) for value in checkpoint.layout))
    parent = Checkpoint(
        state, layout, checkpoint.time, checkpoint.step_index, checkpoint.event_index
    )
    validate_checkpoint(spec, parent)
    original_checks = implementation.check_values(state, spec)
    prepared = controls.prepare(
        spec,
        binding,
        memory,
        base_control,
        event_time_s=event_time_s,
        events_enabled=events_enabled,
    )
    held = prepared.effective_control
    table = type(held)(*(value[None] for value in held))
    trial = dict(
        preparation=prepared, original_clock=(parent.time, parent.step_index, parent.event_index)
    )
    try:
        implementation.check_steps(spec, np.asarray([step_s]), table)
        target = prepared.source_values.state.temperature_K
        if type(spec.model) is controls.temperature.SurfaceTissueModel:
            runtime = layout._replace(temperature=target)
            projection = spec
            if float(target) != spec.model.temperature_K:
                from dataclasses import replace

                projection = replace(spec, model=replace(spec.model, temperature_K=float(target)))
        else:
            runtime, projection, _ = active._runtime(spec, layout, implementation, target)
        implementation.check_steps(projection, np.asarray([step_s]), table)
        runtime = runtime._replace(boundary_V=prepared.boundary_V)
        trial["runtime_layout"] = ordinary._immutable_tree(runtime)
        if not implementation.domain_valid(state, runtime, runtime.active, xp=np):
            raise ValueError(
                "Combined held coefficients leave the original material/gate/affinity domain"
            )
        if implementation is ordinary.passive:
            values = implementation.field_values(state, held, runtime, xp=np)
            derivative = implementation.derivative_from_field(values, runtime, xp=np)
            field, valid = values, values.converged
        else:
            values = implementation.readouts(state, held, runtime, xp=np)
            derivative, field, valid = values.derivative, values.field, values.valid
        trial.update(
            readouts=ordinary._immutable_tree(values),
            derivative=ordinary._immutable_tree(derivative),
        )
        if (
            not valid
            or not field.converged
            or any(not np.isfinite(value).all() for value in derivative)
            or abs(float(field.energy_balance_pJ_s)) > 1e-10
            or any(
                np.min(getattr(derivative, name), initial=0) < -1e-12
                for name in derivative._fields
                if name.endswith("_dissipated_energy_pJ")
            )
        ):
            raise ValueError("Combined held rates violate convergence/energy/dissipation guards")
        passive_fraction = ordinary._passive_fraction(
            state, held, runtime, field, implementation, float(step_s)
        )
        fuel_fraction = 0.0
        if hasattr(runtime, "energy_initial_amount_fmol"):
            amounts = ordinary.fuel.energy_amounts(state, runtime)
            parent_values = values.parent if hasattr(values, "parent") else values
            gross = (
                parent_values.exchange.gross_hydrolysis_fmol_s
                + parent_values.exchange.gross_synthesis_fmol_s
            )
            fraction = np.where(
                runtime.active, gross / np.where(runtime.active, np.min(amounts, axis=0), 1.0), 0.0
            )
            fuel_fraction = float(step_s) * float(np.max(fraction, initial=0))
        trial.update(passive_fraction=passive_fraction, fuel_fraction=fuel_fraction)
        if (
            not np.isfinite([passive_fraction, fuel_fraction]).all()
            or passive_fraction > 0.05
            or fuel_fraction > 0.05
        ):
            raise ValueError("Combined held rates exceed unchanged gross-turnover ceilings")
    except controls.GlobalControlRejected:
        raise
    except (ValueError, ArithmeticError, controls.NumericalError) as error:
        raise controls.GlobalControlRejected(str(error), trial) from error
    admission = MappingProxyType(
        dict(
            kind=KIND,
            policy=controls.POLICY,
            source_definition_sha256=spec.fingerprint,
            binding_identity=binding.identity,
            step_s=float(step_s),
            original_balance_checks=MappingProxyType(dict(original_checks)),
            passive_fraction=passive_fraction,
            fuel_fraction=fuel_fraction,
            passive_limit=0.05,
            fuel_limit=0.05,
            stage_energy_limit_pJ_s=1e-10,
            accepted_stepping=False,
            ordinary_checkpoint_admission=False,
            original_physical_time_s=parent.time,
            original_step_index=parent.step_index,
            original_event_index=parent.event_index,
            native_event_time_s=prepared.event_time_s,
        )
    )
    assumptions = MappingProxyType(
        dict(
            policy=controls.POLICY,
            source_order=tuple(controls.ORDER),
            uniform_held_temperature_K=float(target),
            fixed_J_ER_standards=True,
            finite_calcium_standard_projection="shared_pool_deltaG0_minus_RT_log1000",
            native_split_semantics="separate_evidence",
            thermal_jump=False,
            accepted_voltage_transition=False,
            accepted_heat_pJ=None,
            heat_law=False,
            clock_relation=(
                "explicit setter label distinct from unchanged accepted physical checkpoint clock"
            ),
        )
    )
    return GlobalControlView(
        prepared,
        trial["runtime_layout"],
        trial["readouts"],
        trial["derivative"],
        trial["original_clock"],
        admission,
        assumptions,
    )
