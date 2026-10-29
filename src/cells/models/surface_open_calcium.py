"""Static open-exterior full56 owned calcium; all original physical histories."""

from cells.core import surface_open_calcium_spec as schema
from cells.models import open_calcium_runtime as runtime
from cells.models import surface_calcium_hcn_extra as base

MODEL_ID = schema.MODEL_ID
OBSERVER_ID = "open_owned_calcium_complete_reservoir_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "actual_owned_calcium_static_reservoirs_hard_ionic_moiety_domain@1"
BATCH_CAPACITIES = base.BATCH_CAPACITIES
STATE_AXES = base.STATE_AXES
_adapter = runtime.Adapter(base, schema, "SurfaceOpenCalcium", finite_fuel=False)
STATE_TYPE = _adapter.STATE_TYPE
LAYOUT_TYPE = _adapter.LAYOUT_TYPE
OBSERVATION_FIELDS = _adapter.OBSERVATION_FIELDS
Observations = _adapter.Observations
parameters = base.parameters
parent_state = _adapter.parent_state
parent_layout = _adapter.parent_layout
initial_values = _adapter.initial_values
physical_amounts = _adapter.physical_amounts
readouts = _adapter.readouts
field_values = _adapter.field_values
rhs = _adapter.rhs
control_domain_valid = _adapter.control_domain_valid
check_definition = _adapter.check_definition
loss_bound = _adapter.loss_bound
check_steps = _adapter.check_steps
balances = _adapter.balances
check_values = _adapter.check_values
batch_signature = _adapter.batch_signature
working_size = _adapter.working_size
observe_history = _adapter.observe_history
ensemble_voltage = _adapter.ensemble_voltage
summarize = _adapter.summarize


def domain_valid(state, p, active, *, xp=runtime.jnp):
    return _adapter.domain_valid(state, p, active, xp=xp)


domain_valid.with_control = control_domain_valid
