"""resolved_tissue@8: the shared gate catalogue's channel populations in a resolved tissue.

Its physics is surface_kinetic's. What its own identity changes is here: the layout, whose channels
hold each permeant ion's relative permeability, and the channel ledgers, one per species.
"""

from cells.definitions.surface_kinetic_spec import CATALOG_MODEL_ID as MODEL_ID  # noqa: F401
from cells.models import surface_kinetic as base
from cells.models.surface_kinetic import (  # noqa: F401
    BATCH_CAPACITIES,
    OBSERVATION_FIELDS,
    OBSERVATION_SAMPLING,
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
)

OBSERVER_ID = "resolved_expanded_shared_catalog_accepted_grid@1"
STAGE_DOMAIN_ID = "positive_resolved_inventory_expanded_catalog_actual_controls@1"
LAYOUT_TYPE = base.CATALOG_LAYOUT_TYPE
STATE_AXES = base.STATE_AXES | {
    "channel_transferred": ["species", "channel_slot"],
    "channel_dissipated_energy_pJ": ["species", "channel_slot"],
}


def working_size(spec):
    return (
        base.working_size(spec)
        + (3 * len(spec.model.species_ids) + 1) * spec.execution.channel_capacity
    )
