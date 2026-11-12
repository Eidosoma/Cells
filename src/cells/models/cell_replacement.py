"""resolved_pump_replacement@1: scheduled cell replacement on resolved_pump_tissue@3.

The ionic model is resolved_pump_tissue@3 (models/surface_pump_v3.py), unchanged
and called, never copied (the precedent of models/surface_pump_water.py). The
operation scheduled_cell_replacement@1 removes a carrier's contents from its slot
and supplies a newcomer from a declared template; the junctions at the slot follow
delayed_first_order_junction_formation@1 (processes/junction_formation.py).
Definition: core/cell_replacement_spec.py. Design, sources and the probe of @3's
checks: /mnt/workspaces/Cells/cell-replacement-g2-20261111-01/design-note-G2.md.

Step. checked_step is
  1. the event map, at the start of the step leaving an event time t_e: slots whose
     scheduled count (control.generation) is one ahead of the state's are replaced;
     any other disagreement refuses the step;
  2. the exact formation update over dt/2;
  3. @3's own checked_step at the occupant view of the layout (each slot's current
     template route values gathered into @3's fields) with junction availability
     times the junction abundance A, behind jax.lax.optimization_barrier so @3's
     step compiles as one unit;
  4. the exact formation update over dt/2.
A is held at its step-midpoint value inside @3's step (A is an exogenous input of
time, so this is second order with ARS(2,2,2)). A refused step returns the state
before the event, so an event is applied in full or not at all. The accepted row
at t_e is the departing carrier's last state; t_e + dt is the newcomer's first.
The event map's bookings are described in models/operators/cell_replacement.py.

Checks. Host and device use @3's own row checks (surface_pump.checked_rows,
surface_pump_checks.row_checks, surface_pump.ledger_limits) with @3's balances
plus the replacement terms: local and total material (+ removed - supplied),
global charge (+ replacement charge), energy (- booked free energy); the material,
global-charge and energy rounding magnitudes add the replacement terms; the
domain adds the replacement fields. Stage 1 scope: worlds whose replaced slots
are in capacitor components with a held bath (an event changes a floating
component's net charge, which the field law holds constant; a gauge node alone
does not hold it).

Implementation (D143, docs/PUMP_COMPOSITE.md). This identity is a thin
composition: resolved_pump_composite@1 with the single operator
scheduled_cell_replacement@1 (models/operators/cell_replacement.py, which holds
the event map, the formation law's half-steps and the ledgers, moved there
unchanged). Before this module became thin, the composition was bitwise equal to
its own implementation on the model's test and qualification worlds (evidence:
/mnt/workspaces/Cells/composite-s1-20261111-01/). The operation's names are
re-exported here; the definition format is unchanged.
"""

from dataclasses import replace

import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.cell_replacement_spec import (  # noqa: F401
    MODEL_ID,
    OPERATION_LAW_ID,
    Control,
    control_values,
    lineage,
    projection,
)
from cells.core.specs import ChannelChange
from cells.models import pump_composite
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic
from cells.models.operators import cell_replacement as operator
from cells.models.operators.cell_replacement import (  # noqa: F401  (the operation, re-exported)
    INTEGER_FIELDS,
    IONIC_FIELDS,
    REPLACEMENT_LAYOUT_FIELDS,
    REPLACEMENT_READOUTS,
    REPLACEMENT_STATE_AXES,
    SPLITTING_ID,
    _chemical,
    _electric,
    _terms,
    abundance,
    apply_events,
    event_map,
    formation_parameters,
    formation_rates,
    held_cells,
    ionic_control,
    ionic_layout,
    ionic_state,
    law_channels,
    replaced_charge_magnitude,
    replacement_domain_valid,
)

OBSERVER_ID = "resolved_pump_replacement_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = ionic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_replacement_ledgers@1"
BATCH_CAPACITIES = ionic.BATCH_CAPACITIES
ENERGY_RTOL = ionic.ENERGY_RTOL
EXPLICIT_STEP_BOUND = ionic.EXPLICIT_STEP_BOUND
DISSIPATION_FIELDS = ionic.DISSIPATION_FIELDS

parameters = ionic.parameters
physical_amounts = ionic.physical_amounts
rebind = first.rebind

# The composition this identity runs (one cached implementation).
_model = pump_composite.implementation(ionic.MODEL_ID, (OPERATION_LAW_ID,))
STATE_AXES = _model.STATE_AXES
STATE_TYPE = _model.STATE_TYPE
LAYOUT_TYPE = _model.LAYOUT_TYPE
FLOOR_LAYOUT_TYPE = _model.FLOOR_LAYOUT_TYPE
Values = _model.VALUES_TYPE


def composite(spec):
    """This definition as its composition: the replacement block as the operator."""
    m, e = spec.model, spec.experiment
    model = composite_spec.CompositeModel(
        **{k: getattr(m, k) for k in ionic_spec.SurfacePumpChannelModel.__dataclass_fields__},
        inner_model=m.replacement.inner_model,
        operators=(m.replacement,),
    )
    experiment = composite_spec.Experiment(
        **{k: getattr(e, k) for k in ionic_spec.Experiment.__dataclass_fields__},
        operators=(composite_spec.OperatorSchedule(OPERATION_LAW_ID, e.replacement_events),),
    )
    return replace(spec, model=model, experiment=experiment)


def composition_identity(spec):
    return composite_spec.identity(composite(spec).model)


def field_owners(spec):
    """The composition's field-to-owner map (run manifests, beside the identity)."""
    return _model.field_owners(composite(spec))


def batch_signature(model):
    r, f = model.replacement, model.replacement.junction_formation
    return (
        *ionic.batch_signature(model),
        r.law,
        r.inner_model,
        f.law,
        f.gate_at_arrival,
        r.template_capacity,
    )


def working_size(spec):
    x, s = spec.execution, len(spec.model.species_ids)
    return ionic.working_size(projection(spec)) + 2 * (
        (2 * s + 5) * x.capacity + 2 * x.edge_capacity
    )


def initial_values(spec):
    return _model.initial_values(composite(spec))


def compact(spec):
    m = spec.model
    return replace(
        spec,
        execution=replace(
            spec.execution,
            capacity=len(m.cells),
            extracellular_capacity=len(m.extracellular),
            membrane_capacity=len(m.membranes),
            edge_capacity=len(m.junctions),
            face_capacity=len(m.faces),
            channel_capacity=len(m.channels),
        ),
    )


def check_definition(spec):
    """Stage-1 scope, then each template in the domain at its first slot."""
    _model.check_definition(composite(spec))


def check_steps(spec, steps, controls):
    """@3's step checks on the worst-case inner definition, every occupant included."""
    _model.check_steps(composite(spec), steps, controls)


def bind_step_checks(spec):
    """check_steps bound to one definition (core/grid.clock_checks): the composite's."""
    return _model.bind_step_checks(composite(spec))


def worst_case(spec):
    return operator.worst_case(spec, spec.model.replacement, spec.experiment.replacement_events)


checked_step = _model.checked_step
readouts = _model.readouts
field_values = _model.field_values
rhs = _model.rhs
domain_valid = _model.domain_valid
control_domain_valid = _model.control_domain_valid

# Checks: the composite's (@3's own row checks with the replacement terms).
balances = _model.balances
device_balances = _model.device_balances
magnitudes = _model.magnitudes


def check_values(state, spec, steps=None):
    """@3's host row checks (surface_pump.checked_rows) with the replacement terms."""
    return _model.check_values(state, composite(spec), steps=steps)


DEVICE_CHECKS = _model.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = _model.DEVICE_DIAGNOSTICS
device_failure_message = _model.device_failure_message
device_check_constants = _model.device_check_constants
device_checks = _model.device_checks

OBSERVATION_FIELDS = _model.OBSERVATION_FIELDS
Observations = _model.Observations


def _held_junctions(base, junction):
    """The inner definition with each junction availability held at one value."""
    e = base.experiment
    held = tuple((ChannelChange(0.0, float(v)),) for v in junction[: len(e.junctions)])
    return replace(base, experiment=replace(e, junctions=held))


def observe_history(times, history, layout, requested, spec):
    """@3's observations of each row at its occupant view; junction availability x A."""
    return _model.observe_history(times, history, layout, requested, composite(spec))


def ensemble_voltage(state, layout, spec, time):
    return _model.ensemble_voltage(state, layout, composite(spec), time)


def summarize(history, diagnostics, spec):
    r = spec.model.replacement
    generation = None
    if hasattr(history, "generation") and len(np.asarray(history.generation)):
        generation = np.asarray(history.generation)[-1]
    return ionic.summarize(history, diagnostics, projection(spec)) | {
        "model": MODEL_ID,
        "inner_model": r.inner_model,
        "state_fields": list(STATE_TYPE._fields),
        "replacement_law": OPERATION_LAW_ID,
        "junction_formation": dict(
            law=r.junction_formation.law,
            initial_abundance=r.junction_formation.initial_abundance,
            lag_s=r.junction_formation.lag_s,
            time_constant_s=r.junction_formation.time_constant_s,
            gate_at_arrival=r.junction_formation.gate_at_arrival,
        ),
        "splitting": SPLITTING_ID,
        "replacement_events_declared": len(spec.experiment.replacement_events),
        "lineage": lineage(spec, generation),
        "composition": composition_identity(spec),
    }
