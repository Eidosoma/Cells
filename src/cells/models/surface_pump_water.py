"""resolved_pump_water@1: resolved_pump_tissue@3 with osmotic water and compliant volumes.

The ionic model is resolved_pump_tissue@3 (models/surface_pump_v3.py),
unchanged and called, never copied. Water is the law
numerics/osmotic_water.LAW_ID on the membranes (core/surface_pump_water_spec.py):
the flow across a patch is Q = 1e15 A Lp a (psi_cell - psi_outside) pL/s with
psi = P - Pi, Pi = R T (sum of declared amounts + neutral impermeants) / V and
P = K (V / Vref - 1) + P0. Finite nodes change volume; a held bath keeps its
volume and composition, so its water potential is fixed and the water it
exchanges is booked as supply, with the work 1e-3 psi_b dS.

Concentrations. Every @3 function is evaluated on the @3 layout with the
current volumes (ionic_layout(p, state)): the field (its Newton solve and the
Kirchhoff offsets of floating components, through the currents), the
membrane, junction and face fluxes, the channel and both pump laws, the
implicit drift weights and @3's explicit-stage refusal all see amount / current
volume. Charges, capacitances and potentials do not depend on volume. Ledgers
use the declared layout plus explicit dilution and elastic terms.

Time integration (IMEX solvers). Strang splitting
Phi_dt = W_{dt/2} o I_dt o W_{dt/2}: I_dt is @3's own checked_step at the
volumes left by the first half (frozen over the ionic step); W_h advances the
volumes at frozen amounts by Heun's method (explicit trapezoid). The pieces act
on disjoint variables (I: amounts, gates and ionic ledgers at fixed volume; W:
volumes and water ledgers at fixed amounts), so a zero of the full right-hand
side is a fixed point of each piece and of Phi, and the free energy telescopes
exactly over the three pieces. Water is explicit: its relaxation is about
0.5-85 s for the sourced permeabilities (docs/PUMP_WATER_MODEL.md) against 1 ms
steps; each water step refuses itself if dt times the water relaxation rate at
its actual state exceeds MAX_WATER_RELAXATION_PER_STEP. Any refused piece
refuses the whole step (the previous state is returned). With every water
route closed the flows are exact zeros and @3's step sees exactly @3's inputs.
RK4 (reference runs) integrates the coupled, unsplit right-hand side.

Compilation. @3's step is wrapped in jax.lax.optimization_barrier (its inputs
and its outputs) so that XLA compiles it as one unit and does not fuse the
water arithmetic into it. This changes the schedule only, never the arithmetic.
It is what makes the water-off run bitwise equal to @3 under default XLA flags:
without it, fusion and FMA contraction differed in @3's dissipation accumulators
by about 1 ulp (bitwise again with XLA's algsimp and fusion passes disabled).

Implementation (D143, docs/PUMP_COMPOSITE.md). This identity is a thin
composition: resolved_pump_composite@1 with the single operator
ideal_osmosis_linear_compliance_water@1 (models/operators/osmotic_water.py, which
holds the water law, its Heun half-steps and its ledgers, moved there unchanged).
The composite's step is the splitting above, with @3's step behind the same
barrier. Before this module became thin, the composition was bitwise equal to
its own implementation on the model's test and qualification worlds (evidence:
/mnt/workspaces/Cells/composite-s1-20261111-01/). The law's names are
re-exported here; the definition format is unchanged.
"""

from dataclasses import replace

import jax.numpy as jnp

from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.surface_pump_v2_spec import Control as IonicControl
from cells.core.surface_pump_water_spec import MODEL_ID, projection
from cells.models import pump_composite
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic
from cells.models.operators import osmotic_water as operator
from cells.models.operators.osmotic_water import (  # noqa: F401  (the water law, re-exported)
    MAX_WATER_RELAXATION_PER_STEP,
    VOLUME_ATOL_PL,
    WATER_DIAGNOSTICS,
    WATER_LAYOUT_FIELDS,
    WATER_LEDGER_MESSAGE,
    WATER_LEDGERS,
    WATER_READOUTS,
    WATER_STATE_AXES,
    WATER_STEP_ID,
    WORK_ATOL_PJ,
    WaterRates,
    _advance,
    amounts,
    finite_nodes,
    volumes,
    water_bounds,
    water_control_valid,
    water_domain_valid,
    water_energy_rate,
    water_ledgers,
    water_magnitudes,
    water_parameters,
    water_rate,
    water_rates,
    water_step,
)
from cells.numerics import osmotic_water as water

OBSERVER_ID = "resolved_pump_water_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = ionic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_bounded_compliant_volumes@1"
BATCH_CAPACITIES = ionic.BATCH_CAPACITIES
SPLITTING_ID = "strang_water_ionic_water@1"
ENERGY_RTOL = ionic.ENERGY_RTOL
EXPLICIT_STEP_BOUND = ionic.EXPLICIT_STEP_BOUND
IONIC_FIELDS = ionic.STATE_TYPE._fields

parameters = ionic.parameters
physical_amounts = ionic.physical_amounts
rebind = first.rebind

# The composition this identity runs (one cached implementation).
_model = pump_composite.implementation(ionic.MODEL_ID, (operator.LAW_ID,))
STATE_AXES = _model.STATE_AXES
STATE_TYPE = _model.STATE_TYPE
LAYOUT_TYPE = _model.LAYOUT_TYPE
FLOOR_LAYOUT_TYPE = _model.FLOOR_LAYOUT_TYPE
Values = _model.VALUES_TYPE


def composite(spec):
    """This definition as its composition: the same fields, the water block as the operator."""
    m, e = spec.model, spec.experiment
    model = composite_spec.CompositeModel(
        **{k: getattr(m, k) for k in ionic_spec.SurfacePumpChannelModel.__dataclass_fields__},
        inner_model=ionic.MODEL_ID,
        operators=(m.water,),
    )
    experiment = composite_spec.Experiment(
        **{k: getattr(e, k) for k in ionic_spec.Experiment.__dataclass_fields__},
        operators=(composite_spec.OperatorSchedule(operator.LAW_ID, e.water),),
    )
    return replace(spec, model=model, experiment=experiment)


def composition_identity(spec):
    return composite_spec.identity(composite(spec).model)


def field_owners(spec):
    """The composition's field-to-owner map (run manifests, beside the identity)."""
    return _model.field_owners(composite(spec))


def batch_signature(model):
    w = model.water
    return (
        *ionic.batch_signature(model),
        w.law,
        tuple(p.compartment_id for p in w.compartments),
        tuple(p.compartment_id for p in w.baths),
    )


def working_size(spec):
    x = spec.execution
    return ionic.working_size(projection(spec)) + 2 * (
        x.capacity + 3 * x.extracellular_capacity + 2 * x.membrane_capacity
    )


def ionic_state(state):
    return ionic.STATE_TYPE(*(getattr(state, k) for k in IONIC_FIELDS))


def ionic_control(control):
    return IonicControl(*control[: len(IonicControl._fields)])


def ionic_layout(p, state=None):
    """The @3 layout: declared volumes, or the current ones of `state`."""
    kind = ionic.FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else ionic.LAYOUT_TYPE
    q = kind(*(getattr(p, k) for k in kind._fields))
    if state is None:
        return q
    return q._replace(
        volume=p.volume + state.volume_increment_pL,
        extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
    )


def initial_values(spec):
    return _model.initial_values(composite(spec))


def imex_step(state, dt, control, p, *, xp=jnp):
    """Strang splitting around @3's own checked step; (new or unchanged state, valid)."""
    return _model.split_step(state, dt, control, p, xp=xp)


checked_step = _model.checked_step
readouts = _model.readouts
field_values = _model.field_values
rhs = _model.rhs
domain_valid = _model.domain_valid
control_domain_valid = _model.control_domain_valid


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
    _model.check_definition(composite(spec))


def minimum_volume_spec(spec):
    """The @3 definition with every compliant node at its declared minimum volume."""
    return operator.minimum_volume_spec(spec, spec.model.water)


def check_steps(spec, steps, controls):
    """@3's step checks on this definition's full event grid, plus the water bounds."""
    _model.check_steps(composite(spec), steps, controls)


# Row checks: the composite's, which are @3's own check functions with the water
# terms and ledgers (models/pump_composite.py).
LEDGER_DIAGNOSTICS = (*first.LEDGER_DIAGNOSTICS, *WATER_DIAGNOSTICS)
LEDGERS = (*first.LEDGERS, *WATER_LEDGERS)
DISSIPATION_FIELDS = _model.DISSIPATION_FIELDS
ionic_balances = _model.inner_balances
balances = _model.balances
device_balances = _model.device_balances
ionic_magnitudes = _model.inner_magnitudes
magnitudes = _model.magnitudes
ledger_limits = _model.ledger_limits


def check_values(state, spec, steps=None):
    """Host checks of every accepted row (one row or a [time, ...] history)."""
    return _model.check_values(state, composite(spec), steps=steps)


DEVICE_CHECKS = _model.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = _model.DEVICE_DIAGNOSTICS
device_check_constants = _model.device_check_constants
device_failure_message = _model.device_failure_message
device_checks = _model.device_checks

OBSERVATION_FIELDS = _model.OBSERVATION_FIELDS
Observations = _model.Observations


def observe_history(times, history, layout, requested, spec):
    """@3's observations of each row at its current volumes, then the water readouts."""
    return _model.observe_history(times, history, layout, requested, composite(spec))


def ensemble_voltage(state, layout, spec, time):
    return _model.ensemble_voltage(state, layout, composite(spec), time)


def summarize(history, diagnostics, spec):
    base = projection(spec)
    solver = spec.execution.solver
    return ionic.summarize(history, diagnostics, base) | {
        "model": MODEL_ID,
        "ionic_model": ionic.MODEL_ID,
        "state_fields": list(STATE_TYPE._fields),
        "water_law": water.LAW_ID,
        "time_integrator": solver,
        "splitting": "coupled rhs (rk4)" if solver == "rk4" else SPLITTING_ID,
        "water_step": None if solver == "rk4" else WATER_STEP_ID,
        "volume_owner_ids": [c.compartment_id for c in spec.model.water.compartments],
        "water_bath_ids": [c.compartment_id for c in spec.model.water.baths],
        "water_routes": "membranes only; no junction or extracellular-face water",
        "geometry_scope": "fixed areas, capacitances and topology; compliant volumes",
        "composition": composition_identity(spec),
    }
