"""Ordinary conservative passive dynamics after an archived excision event."""

from typing import NamedTuple

from cells.core.surface_excision_spec import MODEL_ID, base_spec
from cells.models import surface_tissue as base

STATE_AXES = base.STATE_AXES
STATE_TYPE = NamedTuple("SurfaceExcisionState", [(k, object) for k in STATE_AXES])
LAYOUT_TYPE = NamedTuple("SurfaceExcisionLayout", [(k, object) for k in base.LAYOUT_TYPE._fields])
OBSERVER_ID = "resolved_excision_absolute_time_accepted_grid@1"
STAGE_DOMAIN_ID = base.STAGE_DOMAIN_ID
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
BATCH_CAPACITIES = base.BATCH_CAPACITIES
parameters = base.parameters
domain_valid = base.domain_valid
control_domain_valid = base.control_domain_valid
field_values = base.field_values
physical_amounts = base.physical_amounts
balances = base.balances


def initial_time(spec):
    return spec.model.epoch_start_time


def initial_values(spec):
    state, layout = base.initial_values(base_spec(spec))
    return STATE_TYPE(*state), LAYOUT_TYPE(*layout)


def batch_signature(model):
    return base.batch_signature(model), model.epoch_start_time


def working_size(spec):
    return base.working_size(base_spec(spec))


def rhs(state, control, p, active, **kwargs):
    return STATE_TYPE(*base.rhs(state, control, p, active, **kwargs))


def check_steps(spec, steps, controls):
    return base.check_steps(base_spec(spec), steps, controls)


def check_values(state, spec):
    return base.check_values(state, base_spec(spec))


def observe_history(times, history, layout, requested, spec):
    return base.observe_history(times, history, layout, requested, base_spec(spec))


def ensemble_voltage(state, layout, spec, time):
    return base.ensemble_voltage(state, layout, base_spec(spec), time)


def summarize(history, diagnostics, spec):
    return base.summarize(history, diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        epoch_start_time_s=initial_time(spec),
        prior_history="Complete source state and prior definition are archived in model.excision",
        cut_energy_scope="Explicit field/chemical jump; no predicted cutting work or healing",
    )
