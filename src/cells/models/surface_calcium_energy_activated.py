"""Instantaneous calcium-sensitive potassium with owned calcium and finite fuel."""

from cells.core.surface_calcium_energy_spec import (
    CALCIUM_ACTIVATED_MODEL_ID as MODEL_ID,  # noqa: F401
)
from cells.models import surface_calcium_energy as base
from cells.models.surface_calcium_energy import (  # noqa: F401
    BATCH_CAPACITIES,
    ENERGY_ATOL_PJ,
    EXTRA_AXES,
    OBSERVATION_FIELDS,
    OBSERVATION_SAMPLING,
    STATE_AXES,
    STATE_TYPE,
    balances,
    batch_signature,
    bounded_prior_spec,
    check_definition,
    check_steps,
    check_values,
    control_domain_valid,
    cytosol_amount,
    domain_valid,
    energy_amounts,
    ensemble_voltage,
    er,
    field_values,
    initial_values,
    ip3_readouts,
    observe_history,
    parameters,
    physical_amounts,
    pool_free_energy_change_pJ,
    prior_control,
    prior_layout,
    prior_state,
    pump_cycles,
    pump_routes,
    readouts,
    rhs,
    stage_layout,
    store_layout,
    store_state,
    summarize,
    working_size,
)

OBSERVER_ID = "resolved_calcium_energy_activated_accepted_grid@1"
STAGE_DOMAIN_ID = "owned_calcium_finite_atp_calcium_activated_actual_controls@1"
LAYOUT_TYPE = base.CALCIUM_ACTIVATED_LAYOUT_TYPE
