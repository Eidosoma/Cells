"""Owned calcium/ER chemistry composed with sodium and potassium channels.

The explicit layout carries the sodium catalog through the free-cytosol view,
checkpoints, independent worlds and assembly. Older calcium catalogs retain
their identities. Qualification scope and results are recorded in PROGRESS.md.
"""

from cells.core.surface_calcium_spec import SODIUM_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_calcium as base
from cells.models.surface_calcium import (  # noqa: F401
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
)

OBSERVER_ID = "resolved_owned_calcium_sodium_potassium_accepted_grid@1"
STAGE_DOMAIN_ID = "resolved_free_cytosol_er_ip3_named_sodium_potassium_actual_controls@1"
LAYOUT_TYPE = base.SODIUM_LAYOUT_TYPE


def working_size(spec):
    return base.working_size(spec) + spec.execution.channel_capacity
