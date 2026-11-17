"""Resolved sodium/potassium populations with complete ordinary execution."""

from cells.core.surface_kinetic_spec import SODIUM_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_kinetic as base
from cells.models.surface_kinetic import (  # noqa: F401
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
)

OBSERVER_ID = "resolved_sodium_potassium_accepted_grid_readouts@1"
STAGE_DOMAIN_ID = "positive_resolved_inventory_named_na_k_gates_atp_actual_controls@1"
LAYOUT_TYPE = base.SODIUM_LAYOUT_TYPE


def working_size(spec):
    return base.working_size(spec) + spec.execution.channel_capacity
