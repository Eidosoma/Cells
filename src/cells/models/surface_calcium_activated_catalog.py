"""Instantaneous calcium-sensitive potassium with owned calcium/ER chemistry."""

from cells.core.surface_calcium_spec import CALCIUM_ACTIVATED_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_calcium as base
from cells.models.surface_calcium_cav import (  # noqa: F401
    BATCH_CAPACITIES,
    ENERGY_ATOL_PJ,
    OBSERVATION_FIELDS,
    OBSERVATION_SAMPLING,
    STATE_AXES,
    STATE_TYPE,
    balances,
    batch_signature,
    check_definition,
    check_steps,
    check_values,
    chemical_loss_bound,
    control_domain_valid,
    cytosol_amount,
    domain_valid,
    ensemble_voltage,
    er,
    field,
    field_values,
    initial_values,
    ionic_layout,
    ionic_state,
    ip3_readouts,
    loss_bound,
    observe_history,
    parameters,
    physical_amounts,
    readouts,
    rhs,
    store_layout,
    store_state,
    summarize,
    working_size,
)

OBSERVER_ID = "resolved_owned_calcium_activated_accepted_grid@1"
STAGE_DOMAIN_ID = "resolved_free_cytosol_er_calcium_activated_actual_controls@1"
LAYOUT_TYPE = base.CALCIUM_ACTIVATED_LAYOUT_TYPE
