"""The resolved_pump_tissue@3 entity adapter of the composite (docs/CELL_DIVISION_DESIGN.md §3.3).

The composite (models/pump_composite.py) runs @3's own step at a view of its
layout. This adapter is the only place that knows @3's names:

* the inner protocol: state, layout and control types, the checked step (and the
  IMEX step with @3's opt-in membrane-process hook), readouts, domain, balances,
  magnitudes, bounds, checks and observations, all @3's own functions, called and
  never copied; @3's code is not changed;
* the view: entity quantities provided by operators, mapped onto @3's layout
  names (VIEW_FIELDS: volumes, membrane areas and capacitances, charge anchors,
  channel abundance and route values, activity masks) and control names
  (CONTROL_FIELDS: availabilities, multiplied by declared factors);
* the field arrays derived from capacitances and masks (field_capacitor_matrix,
  _scale, _solve_matrix, _factor, field_fixed, field_active). They are bound on
  the host once. When an operator provides a capacitance or a mask (FIELD_INPUTS),
  refresh_field recomputes them on the device and selects them only where an input
  differs from the bound one in that step, so an unchanged step uses the bound
  arrays bitwise. The recomputation covers held-bath topologies (every capacitor
  component holds a reservoir, so the floating basis is empty); a definition with
  floating components and a field-input provider is refused (topology epochs are
  later work, §3.8). No S1 operator provides a field input.
"""

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.specs import ConfigError
from cells.core.surface_pump_v2_spec import Control
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic

MODEL_ID = ionic.MODEL_ID
STATE_AXES = ionic.STATE_AXES
STATE_TYPE = ionic.STATE_TYPE
LAYOUT_TYPE = ionic.LAYOUT_TYPE
FLOOR_LAYOUT_TYPE = ionic.FLOOR_LAYOUT_TYPE
CONTROL_TYPE = Control
STATE_FIELDS = ionic.STATE_TYPE._fields
CONTROL_FIELDS = Control._fields
# Layout names an operator may provide from state (entity quantities).
VIEW_FIELDS = (
    "volume",
    "extracellular_volume",
    "membrane_area",
    "membrane_capacitance",
    "initial_cell_charge_C",
    "channel_abundance",
    "channel_permeability",
    "membrane_permeability",
    "pump_capacity",
    "calcium_pump_capacity",
    "active",
    "outside_active",
    "membrane_active",
    "channel_active",
    "junction_active",
)
# Inputs of the derived field arrays: providing one makes the view refresh them.
FIELD_INPUTS = ("membrane_capacitance", "active", "outside_active", "membrane_active")
DERIVED_FIELD_ARRAYS = (
    "field_capacitor_matrix",
    "field_capacitor_scale",
    "field_capacitor_solve_matrix",
    "field_capacitor_factor",
    "field_fixed",
    "field_active",
)
LEDGERS = first.LEDGERS
LEDGER_DIAGNOSTICS = first.LEDGER_DIAGNOSTICS
DISSIPATION_FIELDS = ionic.DISSIPATION_FIELDS
OBSERVATION_FIELDS = ionic.OBSERVATION_FIELDS
BATCH_CAPACITIES = ionic.BATCH_CAPACITIES
ENERGY_RTOL = ionic.ENERGY_RTOL
EXPLICIT_STEP_BOUND = ionic.EXPLICIT_STEP_BOUND
OBSERVER_ID = ionic.OBSERVER_ID
OBSERVATION_SAMPLING = ionic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = ionic.STAGE_DOMAIN_ID
MembraneProcess = ionic.MembraneProcess

initial_values = ionic.initial_values
parameters = ionic.parameters
physical_amounts = ionic.physical_amounts
checked_step = ionic.checked_step
imex_step = ionic.imex_step
readouts = ionic.readouts
domain_valid = ionic.domain_valid
control_domain_valid = ionic.control_domain_valid
balances = ionic.balances
device_balances = ionic.device_balances
magnitudes = ionic.channel_magnitudes
ledger_limits = first.ledger_limits
checked_rows = first.checked_rows
check_steps = ionic.check_steps
batch_signature = ionic.batch_signature
working_size = ionic.working_size
observe_history = ionic.observe_history
summarize = ionic.summarize
device_check_constants = ionic.device_check_constants
device_failure_message = ionic.device_failure_message
rebind = first.rebind


def inner_state(state):
    return STATE_TYPE(*(getattr(state, k) for k in STATE_FIELDS))


def layout_kind(p):
    return FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else LAYOUT_TYPE


def inner_layout(p):
    """@3's declared layout (the bound values)."""
    kind = layout_kind(p)
    return kind(*(getattr(p, k) for k in kind._fields))


def inner_control(control):
    return Control(*(getattr(control, k) for k in CONTROL_FIELDS))


def view(p, state, providers, *, xp=jnp):
    """@3's layout at the composite state: declared fields, replaced by the providers'.

    providers: operators with VIEW_FIELDS, in declared order (one provider per
    field, checked when the composite is built). Without providers this is the
    declared layout itself.
    """
    q = inner_layout(p)
    provided = set()
    for operator in providers:
        values = operator.view(state, p, q, xp=xp)
        q = q._replace(**values)
        provided |= set(values)
    if provided & set(FIELD_INPUTS):
        q = refresh_field(q, inner_layout(p), xp=xp)
    return q


def control_view(control, state, p, factors, *, xp=jnp):
    """@3's control: each factored availability times its multipliers, in declared order."""
    c = inner_control(control)
    for operator in factors:
        values = operator.control_factors(state, p, xp=xp)
        c = c._replace(**{k: getattr(c, k) * v for k, v in values.items()})
    return c


def field_arrays(q, *, xp=jnp):
    """The capacitor reduction of a held-bath topology from q's capacitances and masks.

    surface_field.bind's construction without its host graph search: the
    capacitor matrix sums C_k e_k e_k^T over active patches; fixed nodes are the
    inactive ones and the reservoirs (every capacitor component holds one, so no
    representative is added); the solve matrix is the scaled free block plus the
    fixed identity, and its lower Cholesky factor. Also returns whether the
    factor is finite (a component that lost its reservoir is singular).
    """
    n, o = q.active.size, q.outside_active.size
    size = n + o
    i, j = q.membrane_cell, n + q.membrane_outside
    c = xp.where(q.membrane_active, q.membrane_capacitance, 0.0)
    if xp is np:
        matrix = np.zeros((size, size))
        for a, b, value in zip(i, j, c, strict=True):
            matrix[a, a] += value
            matrix[b, b] += value
            matrix[a, b] -= value
            matrix[b, a] -= value
    else:
        matrix = (
            jnp.zeros((size, size))
            .at[i, i]
            .add(c)
            .at[j, j]
            .add(c)
            .at[i, j]
            .add(-c)
            .at[j, i]
            .add(-c)
        )
    active = xp.concatenate((q.active, q.outside_active))
    fixed = ~active | xp.concatenate((xp.zeros(n, dtype=bool), q.reservoir))
    scale = xp.max(xp.abs(matrix))
    free = ~fixed
    solve = xp.where(free[:, None] & free[None, :], matrix / scale, 0.0)
    solve = solve + xp.diag(fixed.astype(solve.dtype))
    factor = np.linalg.cholesky(solve) if xp is np else jnp.linalg.cholesky(solve)
    arrays = dict(
        field_capacitor_matrix=matrix,
        field_capacitor_scale=scale,
        field_capacitor_solve_matrix=solve,
        field_fixed=fixed,
        field_active=active,
    )
    if hasattr(q, "field_capacitor_factor"):
        arrays["field_capacitor_factor"] = factor
    return arrays, xp.all(xp.isfinite(factor))


def refresh_field(q, bound, *, xp=jnp):
    """q with its derived field arrays recomputed where a field input changed.

    The bound arrays are selected unless an input differs from the bound value,
    so an unchanged step is bitwise the bound layout. A singular refreshed
    reduction gives NaN arrays, which the inner step refuses.
    """
    changed = xp.asarray(False)
    for name in FIELD_INPUTS:
        changed |= xp.any(getattr(q, name) != getattr(bound, name))
    arrays, finite = field_arrays(q, xp=xp)
    values = {}
    for name, value in arrays.items():
        refreshed = xp.where(finite, value, xp.nan) if value.dtype.kind == "f" else value
        values[name] = xp.where(changed, refreshed, getattr(q, name))
    return q._replace(**values)


def check_field_inputs(p):
    """Refuse a field-input provider on a layout with floating capacitor components."""
    basis = np.asarray(p.field_floating_basis)
    if basis.size and basis.shape[1]:
        raise ConfigError(
            "An operator that changes capacitances or activity masks requires every "
            "capacitor component to hold a reservoir (no floating components)"
        )


def barrier(values, *, xp=jnp):
    """jax.lax.optimization_barrier on the device; the identity on the host."""
    return jax.lax.optimization_barrier(values) if xp is jnp else values
