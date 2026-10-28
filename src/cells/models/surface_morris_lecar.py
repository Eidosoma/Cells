"""53 shared laws in resolved tissue, with explicit zero/one/two-state gates."""

from cells.core.surface_kinetic_spec import MORRIS_LECAR_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_kinetic as base
from cells.models.surface_cav import (  # noqa: F401
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

OBSERVER_ID = "resolved_morris_lecar_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_resolved_morris_lecar_actual_controls@1"
LAYOUT_TYPE = base.MORRIS_LECAR_LAYOUT_TYPE
