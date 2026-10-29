"""Scheduled, explicitly accounted ideal baths for passive resolved tissue."""

from cells.core import surface_passive_bath_events_spec as schema
from cells.models import surface_bath_events as controller
from cells.models import surface_tissue as base

MODEL_ID = schema.MODEL_ID
OBSERVER_ID = "resolved_passive_bath_controller_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_passive_bath_controller_original_anchors@1"
BATCH_CAPACITIES = base.BATCH_CAPACITIES
_adapter = controller.Adapter(base, schema, "SurfacePassiveBath", active=False)
STATE_AXES = _adapter.STATE_AXES
STATE_TYPE = _adapter.STATE_TYPE
LAYOUT_TYPE = _adapter.LAYOUT_TYPE
OBSERVATION_FIELDS = _adapter.OBSERVATION_FIELDS
Observations = _adapter.Observations
parameters = base.parameters
signal_values = controller.signal_values
parent_state = _adapter.parent_state
parent_layout = _adapter.parent_layout
stage_layout = _adapter.stage_layout
initial_values = _adapter.initial_values
initial_operation = _adapter.initial_operation
physical_state = _adapter.physical_state
physical_amounts = _adapter.physical_amounts
readouts = _adapter.readouts
field_values = _adapter.field_values
rhs = _adapter.rhs
control_domain_valid = _adapter.control_domain_valid
check_definition = _adapter.check_definition
check_steps = _adapter.check_steps
balances = _adapter.balances
check_values = _adapter.check_values
check_checkpoint = _adapter.check_checkpoint
observe_history = _adapter.observe_history
ensemble_voltage = _adapter.ensemble_voltage
batch_signature = _adapter.batch_signature
working_size = _adapter.working_size
summarize = _adapter.summarize


def domain_valid(state, p, active, *, xp=controller.jnp):
    return _adapter.domain_valid(state, p, active, xp=xp)


domain_valid.with_control = control_domain_valid
