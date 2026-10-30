"""One explicit ordinary grid interval with component permeability held fixed.

Host provenance/checkpoint admission is separate from an array-only RK4 trial
kernel. RK intermediate trials use stage domains, fields and gross turnover;
integrated conservation/energy/monotonic histories are checked at acceptance.
No random draw, component loop, clock synchronization or layout rebasing occurs.
"""

from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import physiology_tissue_binding as units
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.numerics import surface_transport
from cells.numerics.extracellular_field import ordered_scatter

KIND = "cells.physiology_tissue_step@1"


class StageStatus(NamedTuple):
    valid: object
    domain_valid: object
    field_valid: object
    rates_finite: object
    passive_fraction: object
    fuel_fraction: object
    energy_rate_residual_pJ_s: object
    reason: object  # 0 OK,1 domain,2 field,3 rates,4 gross,5 field solve,6 step.


class RK4Trial(NamedTuple):
    proposed_state: object
    stages: tuple  # y0, y2, y3, y4, endpoint; no clipping/repair.
    derivatives: tuple  # k1,k2,k3,k4,endpoint diagnostic derivative.
    status: tuple
    valid: object  # Stage validity ONLY; host acceptance remains separate.
    first_invalid_stage: object  # 5 means no invalid stage.


@dataclass(frozen=True, slots=True)
class TissueStepResult:
    checkpoint: Checkpoint
    binding: object
    component: object
    trial: RK4Trial
    admission: object


class TissueStepRejected(NumericalError):
    """Uncommitted attempt retaining the original input and raw numerical trial."""

    def __init__(
        self,
        reason,
        *,
        checkpoint,
        binding,
        component,
        trial,
        runtime_layout,
        held_control,
        end_time_s,
        diagnostics,
        stage,
    ):
        super().__init__("Physiological tissue step refused at " + stage + ": " + str(reason))
        self.source_checkpoint, self.binding, self.component = checkpoint, binding, component
        self.trial = None if trial is None else view._immutable_tree(trial)
        self.runtime_layout = runtime_layout
        self.held_control = held_control
        self.end_time_s = end_time_s
        self.diagnostics = MappingProxyType(dict(diagnostics))
        self.stage = stage


def _physical_amounts(state, p, implementation, *, xp):
    if implementation in (view.calcium, view.fuel):
        inside = implementation.cytosol_amount(state, p, xp=xp)
    else:
        inside = p.amount_reference + state.amount_increment
    return inside, p.extracellular_amount_reference + state.extracellular_amount_increment


def _gross_fractions(state, control, p, field, values, h, implementation, *, xp):
    inside, outside = _physical_amounts(state, p, implementation, xp=xp)
    ci = xp.where(p.active, inside / p.volume, 1.0)
    co = xp.where(p.outside_active, outside / p.extracellular_volume, 1.0)
    junction = control.junction
    if hasattr(state, "junction_gate"):
        junction = junction * state.junction_gate
    topology = surface_transport.Layout(
        *(getattr(p, key) for key in surface_transport.Layout._fields)
    )
    passive = surface_transport.transport(
        ci,
        co,
        field.potential_V[: p.active.size],
        field.potential_V[p.active.size :],
        control.membrane,
        junction,
        topology,
        xp=xp,
    )
    gross = xp.abs(passive.membrane_flux_fmol_s)
    cell = ordered_scatter(gross, xp.zeros_like(inside), (p.membrane_cell,), xp=xp)
    exterior = ordered_scatter(gross, xp.zeros_like(outside), (p.membrane_outside,), xp=xp)
    outside_active = p.outside_active & ~p.reservoir
    cell_fraction = xp.where(p.active, cell / xp.where(p.active, inside, 1.0), 0.0)
    exterior_fraction = xp.where(
        outside_active, exterior / xp.where(outside_active, outside, 1.0), 0.0
    )
    passive_fraction = h * xp.maximum(
        xp.max(cell_fraction, initial=0), xp.max(exterior_fraction, initial=0)
    )
    fuel_fraction = xp.asarray(0.0)
    if implementation is view.fuel:
        amount = p.energy_initial_amount_fmol + state.energy_amount_increment_fmol
        gross_fuel = (
            values.exchange.gross_hydrolysis_fmol_s + values.exchange.gross_synthesis_fmol_s
        )
        fuel_fraction = h * xp.max(
            xp.where(p.active, gross_fuel / xp.where(p.active, xp.min(amount, axis=0), 1.0), 0.0),
            initial=0,
        )
    return passive_fraction, fuel_fraction, passive.valid


def _invalid_stage(state, reason, *, xp):
    derivative = jax.tree.map(lambda value: xp.full_like(value, xp.nan), state)
    false, nan = xp.asarray(False), xp.asarray(xp.nan)
    return derivative, StageStatus(false, false, false, false, nan, nan, nan, xp.asarray(reason))


def _stage(state, control, layout, h, implementation, *, xp):
    step_ok = xp.isfinite(h) & (h > 0)
    domain = implementation.domain_valid(state, layout, layout.active, xp=xp) & step_ok

    def evaluate():
        if implementation is view.passive:
            values = field = implementation.field_values(state, control, layout, xp=xp)
            derivative = implementation.derivative_from_field(field, layout, xp=xp)
            field_ok = field.converged
        else:
            values = implementation.readouts(state, control, layout, xp=xp)
            derivative, field = values.derivative, values.field
            field_ok = values.valid & field.converged
        passive, fuel, passive_ok = _gross_fractions(
            state, control, layout, field, values, h, implementation, xp=xp
        )
        finite = xp.all(xp.stack([xp.all(xp.isfinite(value)) for value in derivative]))
        fractions_ok = (
            xp.isfinite(passive)
            & xp.isfinite(fuel)
            & (passive <= view.MAX_PASSIVE_FRACTION_PER_STEP)
            & (fuel <= view.MAX_FUEL_FRACTION_PER_STEP)
        )
        field_ok = field_ok & passive_ok
        valid = domain & field_ok & finite & fractions_ok
        reason = xp.where(~field_ok, 2, xp.where(~finite, 3, xp.where(~fractions_ok, 4, 0)))
        return derivative, StageStatus(
            valid, domain, field_ok, finite, passive, fuel, field.energy_balance_pJ_s, reason
        )

    if xp is np:
        if not bool(domain):
            return _invalid_stage(state, 1 if bool(step_ok) else 6, xp=np)
        try:
            return evaluate()
        except np.linalg.LinAlgError:
            derivative, status = _invalid_stage(state, 5, xp=np)
            return derivative, status._replace(domain_valid=np.asarray(True))
    return jax.lax.cond(
        domain, lambda: evaluate(), lambda: _invalid_stage(state, xp.where(step_ok, 1, 6), xp=xp)
    )


def array_rk4_step(state, control, runtime_layout, step_s, *, implementation, xp=jnp):
    """Pure array trial over a pre-admitted fixed-P/layout/held-control context.

    ``implementation`` is static and must be one of the four original modules.
    No spec, binding, RNG, host checkpoint or integrated-energy check enters
    this kernel. A valid trial is NOT itself an accepted public checkpoint.
    """
    if implementation not in view.IMPLEMENTATIONS.values():
        raise ValueError("Require an exact supported ordinary implementation")
    h = xp.asarray(step_s)
    if h.ndim != 0:
        raise ValueError("RK4 trial step requires a scalar interval")

    def shifted(derivative, factor):
        return jax.tree.map(lambda value, rate: value + factor * h * rate, state, derivative)

    k1, a = _stage(state, control, runtime_layout, h, implementation, xp=xp)
    y2 = shifted(k1, 0.5)
    k2, b = _stage(y2, control, runtime_layout, h, implementation, xp=xp)
    y3 = shifted(k2, 0.5)
    k3, c = _stage(y3, control, runtime_layout, h, implementation, xp=xp)
    y4 = shifted(k3, 1.0)
    k4, d = _stage(y4, control, runtime_layout, h, implementation, xp=xp)
    proposed = jax.tree.map(
        lambda value, a, b, c, d: value + (h / 6.0) * (a + 2.0 * b + 2.0 * c + d),
        state,
        k1,
        k2,
        k3,
        k4,
    )
    endpoint_rate, e = _stage(proposed, control, runtime_layout, h, implementation, xp=xp)
    statuses = (a, b, c, d, e)
    valid = xp.stack([status.valid for status in statuses])
    first_invalid = xp.min(xp.where(valid, 5, xp.arange(5)))
    return RK4Trial(
        proposed,
        (state, y2, y3, y4, proposed),
        (k1, k2, k3, k4, endpoint_rate),
        statuses,
        xp.all(valid),
        first_invalid,
    )


def advance(spec, checkpoint, binding, component, *, end_time_s=None):
    """Attempt precisely the next original EventGrid interval, without commit.

    Result retains the identical original layout, binding and component. Route
    zero/nonzero support must stay unchanged so ordinary checkpoint validation
    remains meaningful. Source schedules alone choose the held control.
    """
    trial, runtime, held, end = None, None, None, end_time_s
    stage, diagnostics = "source", dict(kind=KIND, automatic_retry=False)
    try:
        if type(checkpoint) is not Checkpoint:
            raise ValueError("Require the exact ordinary numeric Checkpoint")
        if type(spec.model) not in view.IMPLEMENTATIONS:
            raise ValueError("Require one of the four exact ordinary families")
        grid = EventGrid(spec)
        validate_checkpoint(spec, checkpoint, times=grid)
        if checkpoint.step_index + 1 >= len(grid):
            raise ValueError("Terminal checkpoint has no next accepted tissue interval")
        end = grid[checkpoint.step_index + 1]
        if end_time_s is not None and (
            not isinstance(end_time_s, Real)
            or isinstance(end_time_s, (bool, np.bool_))
            or not np.isfinite(end_time_s)
            or end_time_s != end
        ):
            raise ValueError(
                "Requested end must be exactly the next original grid/control boundary"
            )
        h = end - checkpoint.time
        table = control_values(spec, [checkpoint.time, end])
        held = type(table)(*(value[0] for value in table))
        at_end = type(table)(*(value[1] for value in table))
        diagnostics.update(
            source_time_s=checkpoint.time,
            end_time_s=end,
            step_s=h,
            source_step_index=checkpoint.step_index,
            source_event_index=checkpoint.event_index,
        )
        stage = "route_support"
        mapped = units.component_permeability(component, binding)
        if not np.array_equal(
            mapped.current_m_s > 0, np.asarray(checkpoint.layout.membrane_permeability) > 0
        ):
            raise ValueError("Tissue stepping cannot change original passive zero/nonzero support")
        stage = "input_admission"
        prepared = view.evaluate(
            spec, checkpoint.state, checkpoint.layout, held, binding, component, step_s=h
        )
        runtime = prepared.runtime_layout
        implementation = view.IMPLEMENTATIONS[type(spec.model)]
        actual = implementation.STATE_TYPE(*(np.asarray(value) for value in checkpoint.state))
        stage = "rk4_trial"
        trial = array_rk4_step(actual, held, runtime, h, implementation=implementation, xp=np)
        if not bool(trial.valid):
            raise ValueError(
                "RK4 stage domain/field/rate/gross guard failed at stage "
                + str(int(trial.first_invalid_stage))
            )
        stage = "endpoint_conservation_and_histories"
        history = implementation.STATE_TYPE(
            *(
                np.stack((before, after))
                for before, after in zip(actual, trial.proposed_state, strict=True)
            )
        )
        changed = view._admission_spec(spec, runtime.membrane_permeability)
        ordinary_checks = implementation.check_values(history, spec)
        runtime_checks = implementation.check_values(history, changed)
        stage = "right_continuous_endpoint"
        # Restored checkpoints may hold JAX arrays. This host guard uses NumPy
        # indexing throughout; the accepted checkpoint retains the source layout.
        original_host_layout = type(checkpoint.layout)(
            *(np.asarray(value) for value in checkpoint.layout)
        )
        for parameters in (original_host_layout, runtime):
            if not implementation.control_domain_valid(
                trial.proposed_state, at_end, parameters, parameters.active, xp=np
            ):
                raise ValueError("Endpoint fails the original right-continuous control domain")
        frozen_trial = view._immutable_tree(trial)
        result = Checkpoint(
            frozen_trial.proposed_state,
            checkpoint.layout,
            end,
            checkpoint.step_index + 1,
            event_index(spec, end),
        )
        stage = "ordinary_checkpoint_acceptance"
        validate_checkpoint(spec, result, times=grid)
        diagnostics.update(
            held_control=view._immutable_tree(held),
            endpoint_control=view._immutable_tree(at_end),
            input_admission=prepared.admission,
            ordinary_balance_checks=MappingProxyType(dict(ordinary_checks)),
            runtime_balance_checks=MappingProxyType(dict(runtime_checks)),
            structural_support_preserved=True,
            component_advanced=False,
            numeric_layout_preserved=True,
        )
        return TissueStepResult(
            result, binding, component, frozen_trial, MappingProxyType(diagnostics)
        )
    except Exception as error:
        raise TissueStepRejected(
            error,
            checkpoint=checkpoint,
            binding=binding,
            component=component,
            trial=trial,
            runtime_layout=runtime,
            held_control=None if held is None else view._immutable_tree(held),
            end_time_s=end,
            diagnostics=diagnostics,
            stage=stage,
        ) from error
