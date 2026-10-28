"""53-law resolved channels with finite shared cellular fuel."""

from cells.core.surface_energy_spec import MORRIS_LECAR_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_energy as base
from cells.models.surface_energy import (  # noqa: F401
    BATCH_CAPACITIES,
    EXTRA_AXES,
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
    energy_amounts,
    ensemble_voltage,
    field_values,
    initial_values,
    observe_history,
    parameters,
    physical_amounts,
    pool_free_energy_change_pJ,
    pool_parameters,
    prior_control,
    prior_layout,
    prior_state,
    pump_routes,
    readouts,
    regeneration_parameters,
    regeneration_routes,
    rhs,
    stage_layout,
    summarize,
    working_size,
)

OBSERVER_ID = "resolved_morris_lecar_finite_energy_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_ions_hybrid_gates_finite_cellular_atp_actual_controls@1"
LAYOUT_TYPE = base.MORRIS_LECAR_LAYOUT_TYPE
