"""Accepted original-grid intervals with an explicitly held protein charge.

This is a separate checkpoint family. Its ordinary seed keeps all original
ionic/ER/fuel/electrical anchors; charged history is checked relative to that
seed with actual charged endpoint energies. Protein, permeability, component
clock and RNG remain held. Preparing this conditioned initial state does not
claim a physical protocol or work budget for the prior protein redistribution.
"""

import math
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType

import numpy as np

from cells.core import physiology_protein_charge_step as step
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_loop as seals
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint as validate_seed
from cells.core.schedule import control_values, event_index
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.models import physiology_protein_charge_rhs as charged

KIND = "cells.held_protein_charge_checkpoint@1"
ENERGY_RATE_ATOL_PJ_S = 1e-10


@dataclass(frozen=True, slots=True)
class HeldProteinCheckpoint:
    seed: Checkpoint
    binding: object
    charge_reference: object
    component: object
    protein_species_id: str
    valence: float
    source_definition_sha256: str
    state: object
    time: float
    step_index: int
    event_index: int
    identity: str

    @property
    def layout(self):
        return self.seed.layout


@dataclass(frozen=True, slots=True)
class HeldProteinStep:
    checkpoint: HeldProteinCheckpoint
    trial: object
    interval_accounting: object
    cumulative_accounting: object
    admission: object


class HeldProteinRejected(NumericalError):
    """An uncommitted attempt with original state and raw failed evidence."""

    def __init__(self, reason, *, source, stage, trial=None, accounting=None, diagnostics=None):
        super().__init__("Held protein-charge interval refused at " + stage + ": " + str(reason))
        self.source, self.stage = source, stage
        self.trial = None if trial is None else view._immutable_tree(trial)
        self.accounting = accounting
        self.diagnostics = MappingProxyType(dict(diagnostics or {}))


def _control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(np.asarray(value[0]) for value in table))


def checkpoint_record(point):
    """Seal complete context and current numeric association, not authorship."""
    if type(point) is not HeldProteinCheckpoint:
        raise ValueError("Require an exact held-protein checkpoint")
    payload = dict(
        kind=KIND,
        seed_identity=seals._checkpoint_identity(point.seed),
        binding_identity=point.binding.identity,
        charge_reference_identity=seals._component_identity(point.charge_reference),
        component_identity=seals._component_identity(point.component),
        protein_species_id=point.protein_species_id,
        valence=point.valence,
        source_definition_sha256=point.source_definition_sha256,
        state_identity=seals._arrays_identity(point.state),
        time=point.time,
        step_index=point.step_index,
        event_index=point.event_index,
    )
    return payload | dict(identity=seals._digest(payload))


def _seal(point):
    return replace(point, identity=checkpoint_record(point)["identity"])


def _clock(spec, point, grid):
    if (
        type(point.time) is not float
        or not math.isfinite(point.time)
        or type(point.step_index) is not int
        or not point.seed.step_index <= point.step_index < len(grid)
        or point.time != grid[point.step_index]
        or type(point.event_index) is not int
        or point.event_index != event_index(spec, point.time)
    ):
        raise ValueError("Charged checkpoint must retain an exact original grid/control boundary")


def _context(spec, point):
    if type(point) is not HeldProteinCheckpoint:
        raise ValueError("Require a separate held-protein checkpoint; ordinary snapshots differ")
    if point.source_definition_sha256 != seals._digest(spec.to_dict()):
        raise ValueError("Held-protein checkpoint belongs to another source definition")
    if point.identity != checkpoint_record(point)["identity"]:
        raise ValueError("Held-protein checkpoint association changed")
    grid = EventGrid(spec)
    validate_seed(spec, point.seed, times=grid)
    _clock(spec, point, grid)
    if point.seed.step_index + 1 >= len(grid):
        raise ValueError("A held trajectory requires a seed with a following original interval")
    # Admission is always against the unchanged ordinary seed, never against
    # evolved charged history or a layout with rebased charge/energy anchors.
    prepared = charged.evaluate(
        spec,
        point.seed,
        point.binding,
        point.charge_reference,
        point.component,
        protein_species_id=point.protein_species_id,
        valence=point.valence,
        step_s=grid[point.seed.step_index + 1] - point.seed.time,
    )
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    actual = view._state(point.state, point.seed.state)
    runtime = prepared.original.runtime_layout
    if not np.array_equal(
        runtime.membrane_permeability > 0, np.asarray(point.layout.membrane_permeability) > 0
    ):
        raise ValueError("Held intervals must preserve original passive route support")
    delta = prepared.rates.protein_charge_increment_C
    if not implementation.domain_valid(actual, runtime, runtime.active, xp=np):
        raise ValueError("Held checkpoint violates its complete material/history domain")
    rates = charged.array_readouts(
        actual, _control(spec, point.time), runtime, delta, implementation=implementation, xp=np
    )
    if not bool(rates.valid):
        raise ValueError("Held checkpoint fails its actual right-continuous charged field/rates")
    if point.step_index == point.seed.step_index and any(
        not np.array_equal(a, b) for a, b in zip(actual, point.seed.state, strict=True)
    ):
        raise ValueError("Conditioned initial state differs from its ordinary numeric seed")
    return grid, implementation, runtime, delta


def _account(spec, point, before, after, before_control, after_control):
    # Imported lazily to keep the array trial layer independent of host balance
    # accounting. This gate is required; no fallback to ordinary energy checks.
    from cells.core import physiology_protein_interval_accounting as accounting

    return accounting.evaluate(
        spec,
        before,
        after,
        point.layout,
        point.binding,
        point.charge_reference,
        point.component,
        protein_species_id=point.protein_species_id,
        valence=point.valence,
        before_control=before_control,
        after_control=after_control,
    )


def validate(spec, point):
    """Recheck source, complete association, charged domains and seed balances."""
    context = _context(spec, point)
    accounting = _account(
        spec,
        point,
        point.seed.state,
        point.state,
        _control(spec, point.seed.time),
        _control(spec, point.time),
    )
    return context, accounting


def initialise(spec, seed, binding, charge_reference, component, *, protein_species_id, valence):
    """Declare a held, conditioned charge state at an accepted ordinary seed.

    No random draw, component loop or elapsed numeric time is introduced.
    The prior redistribution's energy cost is outside this trajectory; its
    actual charged initial energy is retained by the unchanged seed/context.
    """
    if type(seed) is not Checkpoint:
        raise ValueError("Require the original accepted ordinary seed")
    validate_seed(spec, seed)
    units.restore_binding(units.binding_record(binding), spec)
    frozen_seed = Checkpoint(
        view._immutable_tree(seed.state),
        view._immutable_tree(seed.layout),
        float(seed.time),
        seed.step_index,
        seed.event_index,
    )
    point = _seal(
        HeldProteinCheckpoint(
            frozen_seed,
            binding,
            charge_reference,
            component,
            protein_species_id,
            valence,
            seals._digest(spec.to_dict()),
            frozen_seed.state,
            float(seed.time),
            seed.step_index,
            seed.event_index,
            "",
        )
    )
    validate(spec, point)
    return point


def advance(spec, point, *, end_time_s=None):
    """Accept precisely one original grid interval or retain an uncommitted failure."""
    stage, trial, accounting = "source_admission", None, None
    diagnostics = dict(kind=KIND, automatic_retry=False, component_advanced=False)
    try:
        (grid, implementation, runtime, delta), _ = validate(spec, point)
        if point.step_index + 1 >= len(grid):
            raise ValueError("Terminal held checkpoint has no next interval")
        end = float(grid[point.step_index + 1])
        if end_time_s is not None and (
            not isinstance(end_time_s, Real)
            or isinstance(end_time_s, (bool, np.bool_))
            or not math.isfinite(end_time_s)
            or end_time_s != end
        ):
            raise ValueError("End must be exactly the next original grid/control boundary")
        h = end - point.time
        held, right = _control(spec, point.time), _control(spec, end)
        diagnostics.update(source_identity=point.identity, end_time_s=end, step_s=h)
        stage = "step_admission"
        changed = view._admission_spec(spec, runtime.membrane_permeability)
        table = type(held)(*(value[None] for value in held))
        implementation.check_steps(changed, np.asarray([h]), table)
        stage = "charged_rk4_trial"
        trial = step.array_rk4_step(
            point.state, held, runtime, delta, h, implementation=implementation, xp=np
        )
        if not bool(trial.valid):
            raise ValueError(
                "Charged RK4 domain/field/rate/gross guard failed at stage "
                + str(int(trial.first_invalid_stage))
            )
        if any(
            not np.isfinite(status.energy_rate_residual_pJ_s)
            or abs(float(status.energy_rate_residual_pJ_s)) > ENERGY_RATE_ATOL_PJ_S
            for status in trial.status
        ):
            raise ValueError("Charged RK4 stage exceeds the unchanged energy-rate budget")
        stage = "interval_accounting"
        accounting = _account(spec, point, point.state, trial.proposed_state, held, held)
        stage = "right_continuous_endpoint"
        right_rates = charged.array_readouts(
            trial.proposed_state, right, runtime, delta, implementation=implementation, xp=np
        )
        if not bool(right_rates.valid):
            raise ValueError("Endpoint fails the right-continuous charged field/rate domain")
        frozen_trial = view._immutable_tree(trial)
        proposed = _seal(
            replace(
                point,
                state=frozen_trial.proposed_state,
                time=end,
                step_index=point.step_index + 1,
                event_index=event_index(spec, end),
            )
        )
        stage = "cumulative_accounting"
        cumulative = _account(
            spec,
            proposed,
            point.seed.state,
            proposed.state,
            _control(spec, point.seed.time),
            right,
        )
        diagnostics.update(
            numeric_layout_preserved=True,
            protein_held=True,
            permeability_held=True,
            preparation_work_accounted=False,
            protein_transition_performed=False,
            parent_identity=point.identity,
            result_identity=proposed.identity,
        )
        return HeldProteinStep(
            proposed, frozen_trial, accounting, cumulative, MappingProxyType(diagnostics)
        )
    except Exception as error:
        raise HeldProteinRejected(
            error,
            source=point,
            stage=stage,
            trial=trial,
            accounting=getattr(error, "accounting", accounting),
            diagnostics=diagnostics,
        ) from error
