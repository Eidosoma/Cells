"""53-law resolved channels with finite fuel and compliant volumes."""

from cells.core.surface_energy_water_spec import MORRIS_LECAR_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_energy_water as base
from cells.models.surface_energy_water import (  # noqa: F401
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
    effective_layout,
    energy_layout,
    energy_state,
    ensemble_voltage,
    field_values,
    initial_values,
    maximum_osmolyte_amount_fmol,
    observe_history,
    osmotic_amounts,
    parameters,
    physical_amounts,
    pool_dilution_pJ,
    pool_free_energy_change_pJ,
    readouts,
    rhs,
    summarize,
    volumes,
    water_layout,
    water_parameters,
    water_state,
    water_values,
    working_size,
)

OBSERVER_ID = "resolved_morris_lecar_finite_energy_water_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_ions_hybrid_gates_finite_atp_bounded_water_actual_controls@1"
LAYOUT_TYPE = base.MORRIS_LECAR_LAYOUT_TYPE
