"""Complete ordinary rates with a separately owned, held protein charge.

Only transient field arguments acquire the charge increment. Persisted ionic
anchors, ER/fuel owners and all historical energy baselines stay unchanged.
This module supplies rates, not a coupled checkpoint or trajectory acceptance.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.core import physiology_tissue_step as tissue
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.models import physiology_permeability_view as permeability
from cells.models import physiology_protein_charge_view as charge

KIND = "cells.physiology_protein_charge_rhs@1"


class ProteinChargeRates(NamedTuple):
    readouts: object
    derivative: object
    source_charge_C: object
    protein_charge_increment_C: object
    actual_charge_C: object
    charge_grouping_roundoff_C: object
    valid: object

    @property
    def field(self):
        return self.readouts.field if hasattr(self.readouts, "field") else self.readouts


@dataclass(frozen=True, slots=True)
class ProteinChargeRHS:
    original: permeability.PermeabilityView
    charge_response: charge.ProteinChargeView
    rates: ProteinChargeRates
    admission: object

    @property
    def field(self):
        return self.rates.field

    @property
    def derivative(self):
        return self.rates.derivative


class ProteinChargeRHSRejected(NumericalError):
    """Unpublished rate evaluation with available source and charged trials."""

    def __init__(self, reason, *, stage, original, response, trial, diagnostics, field_rejection):
        super().__init__("Protein-charge rates refused at " + stage + ": " + str(reason))
        self.stage, self.original, self.charge_response = stage, original, response
        self.trial = None if trial is None else permeability._immutable_tree(trial)
        self.diagnostics = MappingProxyType(dict(diagnostics))
        self.field_rejection = field_rejection


def _charge_arguments(layout, delta):
    """Ephemeral charge inputs for frozen kernels; never a checkpoint layout.

    Those kernels name their plasma charge arguments initial_*_charge_C. This
    call changes their argument values only, not the owned historical anchors.
    ER charge, initial membrane voltages and every material owner are retained.
    """
    n = layout.active.size
    return layout._replace(
        initial_cell_charge_C=layout.initial_cell_charge_C + delta[:n],
        initial_outside_charge_C=layout.initial_outside_charge_C + delta[n:],
    )


def array_readouts(state, control, layout, protein_charge_increment_C, *, implementation, xp=jnp):
    """Pure array RHS with static implementation and pre-admitted held protein.

    The array port does not validate spec/binding provenance or supply a new
    trajectory energy baseline. Its valid flag checks the actual rate domain.
    A protein transition itself requires separately declared work accounting.
    """
    if implementation not in permeability.IMPLEMENTATIONS.values():
        raise ValueError("Require an exact ordinary implementation")
    delta = xp.asarray(protein_charge_increment_C)
    expected = (layout.active.size + layout.outside_active.size,)
    if delta.shape != expected or delta.dtype != layout.initial_cell_charge_C.dtype:
        raise ValueError("Protein charge requires the exact padded float64 owner axis")
    arguments = _charge_arguments(layout, delta)
    ionic = permeability.passive.charge_increment(state, layout, xp=xp)
    anchors = xp.concatenate((layout.initial_cell_charge_C, layout.initial_outside_charge_C))
    source = anchors + ionic
    actual = (
        xp.concatenate((arguments.initial_cell_charge_C, arguments.initial_outside_charge_C))
        + ionic
    )
    if implementation is permeability.passive:
        values = implementation.field_values(state, control, arguments, xp=xp)
        derivative = implementation.derivative_from_field(values, arguments, xp=xp)
        valid = values.converged
    else:
        values = implementation.readouts(state, control, arguments, xp=xp)
        derivative, valid = values.derivative, values.valid & values.field.converged
    active = xp.concatenate((layout.active, layout.outside_active))
    valid = (
        valid
        & implementation.domain_valid(state, arguments, arguments.active, xp=xp)
        & xp.all(xp.isfinite(delta))
        & xp.all(xp.isfinite(actual))
        & xp.all(xp.where(active, True, delta == 0))
        & xp.all(xp.stack([xp.all(xp.isfinite(value)) for value in derivative]))
    )
    return ProteinChargeRates(
        values, derivative, source, delta, actual, actual - (source + delta), valid
    )


def evaluate(spec, checkpoint, binding, reference, current, *, protein_species_id, valence, step_s):
    """Admit full same-state rates at actual controls, with held protein charge.

    The original checkpoint is validated against its original anchors. Its
    history is not reinterpreted as an accepted charged-protein trajectory.
    Protein and current permeability remain fixed throughout this rate call.
    """
    stage, original, response, trial = "admission", None, None, None
    diagnostics, field_rejection = {}, None
    try:
        stage = "charge_admission"
        response = charge.evaluate(
            spec,
            checkpoint,
            binding,
            reference,
            current,
            protein_species_id=protein_species_id,
            valence=valence,
        )
        if not response.projection_change.strict_conservation_valid:
            raise ValueError("Closed held-protein rates require strict material conservation")
        table = control_values(spec, [checkpoint.time])
        held = type(table)(*(np.asarray(value[0]) for value in table))
        stage = "original_rates"
        original = permeability.evaluate(
            spec, checkpoint.state, checkpoint.layout, held, binding, current, step_s=step_s
        )
        implementation = permeability.IMPLEMENTATIONS[type(spec.model)]
        state = type(checkpoint.state)(*(np.asarray(value) for value in checkpoint.state))
        stage = "charged_rates"
        trial = array_readouts(
            state,
            held,
            original.runtime_layout,
            response.applied_delta_charge_C,
            implementation=implementation,
            xp=np,
        )
        if not trial.valid:
            raise NumericalError("Actual charged rates fail original field/rate domain")
        stage = "gross_turnover"
        passive, fuel, valid = tissue._gross_fractions(
            state,
            held,
            original.runtime_layout,
            trial.field,
            trial.readouts,
            step_s,
            implementation,
            xp=np,
        )
        diagnostics.update(
            passive_fraction=float(passive),
            fuel_fraction=float(fuel),
            energy_rate_residual_pJ_s=float(trial.field.energy_balance_pJ_s),
        )
        if (
            not valid
            or not np.isfinite([passive, fuel]).all()
            or passive > permeability.MAX_PASSIVE_FRACTION_PER_STEP
            or fuel > permeability.MAX_FUEL_FRACTION_PER_STEP
        ):
            raise NumericalError("Actual charged rates exceed passive/fuel turnover ceilings")
        admission = MappingProxyType(
            dict(
                kind=KIND,
                source_definition_sha256=binding.source_definition_sha256,
                binding_identity=binding.identity,
                numeric_time_s=checkpoint.time,
                step_s=float(step_s),
                protein_species_id=protein_species_id,
                protein_valence=valence,
                original_anchors_preserved=True,
                original_energy_baselines_preserved=True,
                protein_held_fixed=True,
                protein_charge_rate_C_s=0.0,
                original_checkpoint_validated=True,
                coupled_rhs=True,
                coupled_trajectory=False,
                protein_transfer_work_accounted=False,
                **diagnostics,
                scope="complete ordinary rates with a separately owned held protein charge",
            )
        )
        return ProteinChargeRHS(original, response, permeability._immutable_tree(trial), admission)
    except Exception as error:
        if isinstance(error, charge.ProteinChargeViewRejected):
            field_rejection = error
        raise ProteinChargeRHSRejected(
            error,
            stage=stage,
            original=original,
            response=response,
            trial=trial,
            diagnostics=diagnostics,
            field_rejection=field_rejection,
        ) from error
