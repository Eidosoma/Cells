"""Compliant ionic volumes with all 53 named channel laws and explicit gate states."""

from cells.core.surface_water_kinetic_spec import MORRIS_LECAR_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_water_kinetic as base
from cells.models.surface_water_kinetic import (  # noqa: F401
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
    ensemble_voltage,
    field_values,
    initial_values,
    observe_history,
    parameters,
    physical_amounts,
    prior_layout,
    prior_state,
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

LAYOUT_TYPE = base.MORRIS_LECAR_LAYOUT_TYPE
OBSERVER_ID = "resolved_morris_lecar_compliant_water_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_ions_hybrid_gate_states_and_bounded_compliant_volumes@1"
