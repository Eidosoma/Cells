"""Versioned fixed-geometry 53-law owned-calcium tissue with prescribed injury."""

from cells.core.surface_repair_spec import MORRIS_LECAR_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_repair as base
from cells.models.surface_repair import (  # noqa: F401
    BATCH_CAPACITIES,
    EXTRA_AXES,
    OBSERVATION_FIELDS,
    OBSERVATION_SAMPLING,
    STATE_AXES,
    STATE_TYPE,
    Observations,
    accounting_state,
    balances,
    base_control,
    base_layout,
    base_state,
    batch_signature,
    check_definition,
    check_steps,
    check_values,
    control_domain_valid,
    cytosol_amount,
    domain_valid,
    ensemble_voltage,
    er,
    field_values,
    initial_values,
    injury_loss_bound,
    ip3_readouts,
    observe_history,
    parameters,
    readouts,
    rhs,
    store_layout,
    store_state,
    summarize,
    working_size,
)

LAYOUT_TYPE = base.MORRIS_LECAR_LAYOUT_TYPE
OBSERVER_ID = "resolved_owned_morris_lecar_prescribed_repair_accepted_grid@1"
STAGE_DOMAIN_ID = "resolved_free_cytosol_er_morris_lecar_damage_actual_controls@1"
