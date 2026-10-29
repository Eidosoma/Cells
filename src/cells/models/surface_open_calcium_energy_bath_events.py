"""Live finite-fuel full56 calcium with explicit scheduled ideal baths."""

from cells.core import surface_open_calcium_energy_bath_events_spec as schema
from cells.models import open_calcium_bath_runtime as runtime
from cells.models import surface_open_calcium_energy as base

MODEL_ID = schema.MODEL_ID
OBSERVER_ID = "scheduled_open_calcium_finite_fuel_complete_bath_readouts@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "actual_finite_fuel_owned_calcium_bath_hard_ionic_domain@1"
BATCH_CAPACITIES = base.BATCH_CAPACITIES
_adapter = runtime.Adapter(base, schema, "SurfaceOpenCalciumEnergyBath", finite_fuel=True)
STATE_AXES = _adapter.STATE_AXES
STATE_TYPE = _adapter.STATE_TYPE
LAYOUT_TYPE = _adapter.LAYOUT_TYPE
OBSERVATION_FIELDS = _adapter.OBSERVATION_FIELDS
Observations = _adapter.Observations
parameters = base.parameters
signal_values = runtime.signal_values
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
initial_pool_turnover_bound = _adapter.initial_pool_turnover_bound
balances = _adapter.balances
check_values = _adapter.check_values
check_checkpoint = _adapter.check_checkpoint
observe_history = _adapter.observe_history
ensemble_voltage = _adapter.ensemble_voltage
batch_signature = _adapter.batch_signature
working_size = _adapter.working_size
summarize = _adapter.summarize


def domain_valid(state, p, active, *, xp=runtime.jnp):
    return _adapter.domain_valid(state, p, active, xp=xp)


domain_valid.with_control = control_domain_valid
