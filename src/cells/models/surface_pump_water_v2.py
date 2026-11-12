"""resolved_pump_water@2: resolved_pump_water@1 plus KCC-type K+/anion symport routes.

Each route (core/surface_pump_water_v2_spec.py) is the law
processes/k_anion_symport.LAW_ID on its membrane patch: outward cycles
J = k a f(V) (K_i A_i - K_o A_o), one potassium and one anion per cycle, so it
carries no current, with heat 1e-3 J A >= 0 and the cell's current volume in
f(V). It is passed to resolved_pump_tissue@3's opt-in membrane-process hook
(models/surface_pump_v3.py), so it is one more explicit membrane term at every
@3 stage, in readouts and in rhs; @3 returns the tableau-applied transfer and
the trapezoid heat of each step, which this model books in its own ledgers
(symport_cycles_fmol, symport_dissipated_energy_pJ). Everything else, water
included, is resolved_pump_water@1 (models/surface_pump_water.py): the same
Strang splitting, with @3's step behind the same optimization barrier.

With no route declared the identity is resolved_pump_water@1: the step is that
model's step (a static branch on the route layout's shape). Fixed points stay
exact: the symport moves amounts inside @3's step, and water acts only on
volumes at frozen amounts, so a zero of the full right-hand side is a fixed
point of each split piece.

Ledgers: the material ledgers include the symport transfers (K and anion);
the energy ledger adds the symport heat; dissipation includes it.

Implementation (D143, docs/PUMP_COMPOSITE.md). This identity is a thin
composition: resolved_pump_composite@1 with the operators
ideal_osmosis_linear_compliance_water@1 and k_anion_symport_mass_action@1
(models/operators/, which hold the water and route laws, moved there unchanged).
Before this module became thin, the composition was bitwise equal to its own
implementation on the model's test and qualification worlds (evidence:
/mnt/workspaces/Cells/composite-s1-20261111-01/). The laws' names are re-exported
here; the definition format is unchanged.
"""

from dataclasses import replace

import jax.numpy as jnp

from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.surface_pump_water_spec import Control as WaterControl
from cells.core.surface_pump_water_v2_spec import MODEL_ID, Control, projection  # noqa: F401
from cells.models import pump_composite
from cells.models import surface_pump_v3 as ionic
from cells.models import surface_pump_water as w1
from cells.models.operators import k_anion_symport as operator
from cells.models.operators.k_anion_symport import (  # noqa: F401  (the route law, re-exported)
    SYMPORT_LAYOUT_FIELDS,
    SYMPORT_READOUTS,
    SYMPORT_STATE_AXES,
    membrane_process,
    symport_parameters,
    symport_rates,
    transfer,
)
from cells.models.operators.osmotic_water import LAW_ID as WATER_LAW_ID

OBSERVER_ID = "resolved_pump_regulated_water_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = w1.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_bounded_volumes_symport@1"
BATCH_CAPACITIES = w1.BATCH_CAPACITIES
WATER_FIELDS = w1.STATE_TYPE._fields
ENERGY_RTOL = w1.ENERGY_RTOL
parameters = w1.parameters
physical_amounts = w1.physical_amounts
rebind = w1.rebind

# The composition this identity runs (one cached implementation).
_model = pump_composite.implementation(ionic.MODEL_ID, (WATER_LAW_ID, operator.LAW_ID))
STATE_AXES = _model.STATE_AXES
STATE_TYPE = _model.STATE_TYPE
LAYOUT_TYPE = _model.LAYOUT_TYPE
FLOOR_LAYOUT_TYPE = _model.FLOOR_LAYOUT_TYPE
Values = _model.VALUES_TYPE


def composite(spec):
    """This definition as its composition: water, then the routes."""
    m, e = spec.model, spec.experiment
    model = composite_spec.CompositeModel(
        **{k: getattr(m, k) for k in ionic_spec.SurfacePumpChannelModel.__dataclass_fields__},
        inner_model=ionic.MODEL_ID,
        operators=(m.water, m.symport),
    )
    experiment = composite_spec.Experiment(
        **{k: getattr(e, k) for k in ionic_spec.Experiment.__dataclass_fields__},
        operators=(
            composite_spec.OperatorSchedule(WATER_LAW_ID, e.water),
            composite_spec.OperatorSchedule(operator.LAW_ID, e.symport),
        ),
    )
    return replace(spec, model=model, experiment=experiment)


def composition_identity(spec):
    return composite_spec.identity(composite(spec).model)


def field_owners(spec):
    """The composition's field-to-owner map (run manifests, beside the identity)."""
    return _model.field_owners(composite(spec))


def batch_signature(model):
    routes = tuple(r.membrane_id for r in model.symport.routes)
    return (*w1.batch_signature(model), model.symport.law, routes)


def working_size(spec):
    return w1.working_size(projection(spec)) + 4 * spec.execution.membrane_capacity


def water_state(state):
    return w1.STATE_TYPE(*(getattr(state, k) for k in WATER_FIELDS))


def water_layout(p):
    kind = w1.FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else w1.LAYOUT_TYPE
    return kind(*(getattr(p, k) for k in kind._fields))


def water_control(control):
    return WaterControl(*control[: len(WaterControl._fields)])


def initial_values(spec):
    return _model.initial_values(composite(spec))


def imex_step(state, dt, control, p, *, xp=jnp):
    """resolved_pump_water@1's split step with the routes in @3's step (static skip)."""
    return _model.split_step(state, dt, control, p, xp=xp)


checked_step = _model.checked_step
readouts = _model.readouts
field_values = _model.field_values
rhs = _model.rhs
domain_valid = _model.domain_valid
control_domain_valid = _model.control_domain_valid


def check_definition(spec):
    _model.check_definition(composite(spec))


def check_steps(spec, steps, controls):
    """resolved_pump_water@1's step checks on this definition's full event grid, and the
    route bound (the routes are electroneutral, so they add no membrane conductance)."""
    _model.check_steps(composite(spec), steps, controls)


# Row checks: the composite's (@3's own check functions with the water and route terms).
DISSIPATION_FIELDS = _model.DISSIPATION_FIELDS
LEDGER_DIAGNOSTICS = w1.LEDGER_DIAGNOSTICS
LEDGERS = w1.LEDGERS
WATER_DIAGNOSTICS = w1.WATER_DIAGNOSTICS


def adjusted(row, p, *, xp):
    """The row with the symport transfers added to @3's membrane transfers."""
    return water_state(row)._replace(
        membrane_transferred=row.membrane_transferred + transfer(row.symport_cycles_fmol, p, xp=xp)
    )


ionic_balances = _model.inner_balances
balances = _model.balances
device_balances = _model.device_balances
ionic_magnitudes = _model.inner_magnitudes
magnitudes = _model.magnitudes
ledger_limits = _model.ledger_limits


def check_values(state, spec, steps=None):
    """resolved_pump_water@1's host checks with the symport ledgers (same order)."""
    return _model.check_values(state, composite(spec), steps=steps)


DEVICE_CHECKS = _model.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = _model.DEVICE_DIAGNOSTICS
device_check_constants = _model.device_check_constants
device_failure_message = _model.device_failure_message
device_checks = _model.device_checks

OBSERVATION_FIELDS = _model.OBSERVATION_FIELDS
Observations = _model.Observations


def observe_history(times, history, layout, requested, spec):
    """resolved_pump_water@1's observations (its fields at the routes' amounts), then the routes."""
    return _model.observe_history(times, history, layout, requested, composite(spec))


def ensemble_voltage(state, layout, spec, time):
    return _model.ensemble_voltage(state, layout, composite(spec), time)


def summarize(history, diagnostics, spec):
    y = spec.model.symport
    return w1.summarize(history, diagnostics, projection(spec)) | {
        "model": MODEL_ID,
        "state_fields": list(STATE_TYPE._fields),
        "symport_law": y.law,
        "symport_volume_factor": y.volume_factor,
        "symport_roles": dict(potassium=y.potassium, anion=y.anion),
        "symport_routes": [r.membrane_id for r in y.routes],
        "composition": composition_identity(spec),
    }
