"""Instantaneous calcium-sensitive potassium alongside 39 shared tissue laws."""

from cells.definitions.surface_kinetic_spec import (
    CALCIUM_ACTIVATED_MODEL_ID as MODEL_ID,  # noqa: F401
)
from cells.legacy.models.surface_cav import (  # noqa: F401
    BATCH_CAPACITIES,
    OBSERVATION_FIELDS,
    OBSERVATION_SAMPLING,
    STATE_AXES,
    STATE_TYPE,
    balances,
    batch_signature,
    check_definition,
    check_steps,
    check_values,
    control_domain_valid,
    domain_valid,
    ensemble_voltage,
    field_values,
    initial_values,
    observe_history,
    parameters,
    physical_amounts,
    readouts,
    rhs,
    summarize,
    working_size,
)
from cells.models import surface_kinetic as base

OBSERVER_ID = "resolved_calcium_activated_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_resolved_calcium_activated_actual_controls@1"
LAYOUT_TYPE = base.CALCIUM_ACTIVATED_LAYOUT_TYPE
