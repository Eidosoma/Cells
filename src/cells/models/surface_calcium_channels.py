"""Owned calcium chemistry composed with mixed potassium channel populations.

The explicit layout preserves per-population laws through ordinary checkpoints,
independent GPU worlds and assembly coupling. Physics reuse the same owned
cytosol/ER implementation; resolved_calcium@1 retains its original layout.
"""

from cells.core.surface_calcium_spec import CHANNEL_MODEL_ID as MODEL_ID  # noqa: F401
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

OBSERVER_ID = "resolved_owned_calcium_mixed_potassium_accepted_grid@1"
STAGE_DOMAIN_ID = "resolved_free_cytosol_er_ip3_named_potassium_actual_controls@1"
LAYOUT_TYPE = base.CHANNEL_LAYOUT_TYPE


def working_size(spec):
    return base.working_size(spec) + spec.execution.channel_capacity
