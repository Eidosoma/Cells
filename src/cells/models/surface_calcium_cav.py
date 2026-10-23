"""Named pinned CaV populations composed with HCN/NaV and owned calcium/ER.

Each population keeps one gate pair and availability; its species routes use
the same free-cytosol owner as CaV, PMCA, NCX, binding and ER transport.
"""

from cells.core.surface_calcium_spec import CAV_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_calcium as base
from cells.models.surface_calcium import (  # noqa: F401
    BATCH_CAPACITIES,
    ENERGY_ATOL_PJ,
    OBSERVATION_FIELDS,
    OBSERVATION_SAMPLING,
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

OBSERVER_ID = "resolved_owned_calcium_shared_multi_ion_accepted_grid@1"
STAGE_DOMAIN_ID = "resolved_free_cytosol_er_ip3_shared_multi_ion_actual_controls@1"
LAYOUT_TYPE = base.CAV_LAYOUT_TYPE
STATE_AXES = base.HCN_STATE_AXES


def working_size(spec):
    return (
        base.working_size(spec)
        + (3 * len(spec.model.species_ids) + 1) * spec.execution.channel_capacity
    )
