"""The unchanged 44-field calcium/fuel/configured-transport equations after removal."""

from cells.core.surface_calcium_energy_irreversible_transport_excision_spec import (
    MODEL_ID,
    base_spec,
)
from cells.models import surface_calcium_energy_irreversible_transport as base

STATE_AXES = base.STATE_AXES
# The layout type is a static law dispatcher in the existing shared kernel.
# Preserve it so every zero/one/two-state population keeps its declared law.
STATE_TYPE = base.STATE_TYPE
LAYOUT_TYPE = base.LAYOUT_TYPE
BATCH_CAPACITIES = base.BATCH_CAPACITIES
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
OBSERVER_ID = (
    "resolved_calcium_energy_irreversible_transport_excision_absolute_time_accepted_grid@1"
)
STAGE_DOMAIN_ID = base.STAGE_DOMAIN_ID
parameters = base.parameters
domain_valid = base.domain_valid
control_domain_valid = base.control_domain_valid
field_values = base.field_values
physical_amounts = base.physical_amounts
balances = base.balances
rhs = base.rhs


def initial_time(spec):
    return spec.model.epoch_start_time


def initial_values(spec):
    return base.initial_values(base_spec(spec))


def batch_signature(model):
    return base.batch_signature(model), model.epoch_start_time


def working_size(spec):
    return base.working_size(base_spec(spec))


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
        prior_history=(
            "Complete 44-field state, layout and source definition archived in model.excision"
        ),
        gate_policy="Preserve shared channel, junction and dedicated calcium-channel gate states",
        cut_energy_scope=(
            "Chemical/fuel/capacitor diagnostic; no gate or mechanical cutting-energy law"
        ),
    )
