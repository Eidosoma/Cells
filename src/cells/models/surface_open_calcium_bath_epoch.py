"""Full calcium INIT-to-SIM bath epoch with continuous original histories."""

from cells.core import surface_open_calcium_bath_epoch_spec as schema
from cells.models import open_calcium_bath_epoch as epoch
from cells.models import surface_open_calcium_bath_events as scheduled

MODEL_ID = schema.MODEL_ID
OBSERVER_ID = "resolved_init_sim_open_calcium_bath_epoch_readouts@1"
OBSERVATION_SAMPLING = scheduled.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = scheduled.STAGE_DOMAIN_ID
BATCH_CAPACITIES = scheduled.BATCH_CAPACITIES
STATE_AXES = scheduled.STATE_AXES
_adapter = epoch.Adapter(scheduled, schema, "SurfaceOpenCalciumBathEpoch")
STATE_TYPE = _adapter.STATE_TYPE
LAYOUT_TYPE = _adapter.LAYOUT_TYPE
OBSERVATION_FIELDS = _adapter.OBSERVATION_FIELDS
Observations = _adapter.Observations
parameters = scheduled.parameters
domain_valid = scheduled.domain_valid
control_domain_valid = scheduled.control_domain_valid
parent_state = scheduled.parent_state
parent_layout = scheduled.parent_layout
stage_layout = scheduled.stage_layout
physical_state = scheduled.physical_state
physical_amounts = scheduled.physical_amounts
signal_values = scheduled.signal_values
readouts = scheduled.readouts
field_values = scheduled.field_values
balances = scheduled.balances
batch_signature = scheduled.batch_signature
handoff_record = _adapter.handoff_record
initial_values = _adapter.initial_values
initial_operation = _adapter.initial_operation
rhs = _adapter.rhs
check_definition = _adapter.check_definition
carried_pool_turnover_bound = _adapter.carried_pool_turnover_bound
check_carried_pool_turnover = _adapter.check_carried_pool_turnover
check_steps = _adapter.check_steps
check_values = _adapter.check_values
check_checkpoint = _adapter.check_checkpoint
working_size = _adapter.working_size
observe_history = _adapter.observe_history
ensemble_voltage = _adapter.ensemble_voltage
summarize = _adapter.summarize
