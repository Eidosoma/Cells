"""The resolved_pump_tissue@3 entity adapter of the composite (docs/CELL_DIVISION_DESIGN.md §3.3).

The composite (models/pump_composite.py) runs @3's own step at a view of its
layout. This adapter is the only place that knows @3's names:

* the inner protocol: state, layout and control types, the checked step (and the
  IMEX step with @3's opt-in membrane-process hook), readouts, domain, balances,
  magnitudes, bounds, checks and observations, all @3's own functions, called and
  never copied; @3's code is not changed;
* the view: entity quantities provided by operators, mapped onto @3's layout
  names (VIEW_FIELDS: volumes, membrane areas and capacitances, charge anchors,
  channel abundance and route values, activity masks and the reference amounts
  of outside nodes that are switched off) and control names (CONTROL_FIELDS:
  availabilities, multiplied by declared factors);
* the field arrays derived from capacitances and masks (field_capacitor_matrix,
  _scale, _solve_matrix, _factor, field_fixed, field_active). They are bound on
  the host once. When an operator provides a capacitance or a mask (FIELD_INPUTS),
  refresh_field recomputes them on the device and selects them only where an input
  differs from the bound one in that step, so an unchanged step uses the bound
  arrays bitwise. The recomputation runs every step (a select by value), so a
  field-input provider is refused above FIELD_INPUT_NODE_CAP field nodes (option (a)
  of v2 design §3). It covers held-bath topologies (every capacitor component holds
  a reservoir, so the floating basis is empty); a definition with floating
  components and a field-input provider is refused (topology epochs are later work,
  §3.8). membrane_entity_state@1 and scheduled_membrane_insertion@1 (S2) are the
  first field-input providers;
* @3's free energy and its capacitor field at a view: chemical_free_energy_pJ and
  capacitor_free_energy_pJ (balances' own terms), view_capacitor_terms (the energy
  rule: @3's term on the declared layout brought to the physical capacitor energy at
  the view, with the clamps' plate charges) and fixed_charge_change (one capacitance
  change at fixed free-node charges: potentials, image charge and heat).
"""

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.specs import ConfigError
from cells.core.surface_pump_v2_spec import Control
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic
from cells.models import surface_tissue as tissue
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.processes.electrochemistry import R

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
    "face_active",
    "extracellular_amount_reference",
)
# Inputs of the derived field arrays: providing one makes the view refresh them.
FIELD_INPUTS = ("membrane_capacitance", "active", "outside_active", "membrane_active")
# Activity masks an operator may close (docs/CELL_DIVISION_S5_DESIGN.md §2): close() combines
# them by conjunction, propagates closure down the entity hierarchy and pads closed slots.
MASK_FIELDS = (
    "active",
    "outside_active",
    "membrane_active",
    "face_active",
    "junction_active",
    "channel_active",
)
# Layout fields close() pads for closed slots (no operator provides them beside a closer).
PADDED_FIELDS = (
    "amount_reference",
    "extracellular_amount_reference",
    "initial_cell_charge_C",
    "initial_outside_charge_C",
    "channel_laws",
    "junction_minimum",
)
# Option (a) of v2 design §3 (R3): the refresh refactorises every step once a field input is
# provided, so a field-input provider is refused above this many field nodes (cells plus
# outside nodes, padded). Measured on one CPU core (composite-v2-20261112-01/s2-r3-cost): +7.5%
# per step at 2 nodes, noise at 14, +20% at 254 and +48% at 825.
FIELD_INPUT_NODE_CAP = 64
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
# @3's energy roles by name (v2 design §1.1): heat (dissipation, nonnegative increments) and
# work (supplied energy). The composite's energy-role table starts from these.
HEAT_FIELDS = (
    "membrane_dissipated_energy_pJ",
    "junction_dissipated_energy_pJ",
    "face_dissipated_energy_pJ",
    "channel_dissipated_energy_pJ",
    "pump_dissipated_energy_pJ",
    "calcium_pump_dissipated_energy_pJ",
)
WORK_FIELDS = (
    "reservoir_work_pJ",
    "electrode_work_pJ",
    "metabolic_work_pJ",
    "calcium_metabolic_work_pJ",
)
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
bind_step_checks = ionic.bind_step_checks
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


def view(p, state, providers, closers=(), *, xp=jnp):
    """@3's layout at the composite state: declared fields, replaced by the providers'.

    providers: operators with VIEW_FIELDS, in declared order (one provider per
    field, checked when the composite is built). Without providers this is the
    declared layout itself. closers: operators that close activity masks (CLOSES), each
    not statically idle; with none the call is exactly the one without closers.
    """
    q = inner_layout(p)
    provided = set()
    for operator in providers:
        values = operator.view(state, p, q, xp=xp)
        q = q._replace(**values)
        provided |= set(values)
    if closers:
        q = close(q, state, p, closers, xp=xp)
        provided |= set(MASK_FIELDS)
    if provided & set(FIELD_INPUTS):
        q = refresh_field(q, inner_layout(p), xp=xp)
    return q


def close(q, state, p, closers, *, xp):
    """q with every closer's masks applied (docs/CELL_DIVISION_S5_DESIGN.md §2).

    * Conjunction: each mask is the running one AND every closer's, in declared order (exact,
      and independent of order).
    * Propagation down the entity hierarchy: a patch of a closed cell or node is closed, a
      population on a closed patch is closed, a contact with a closed endpoint is closed and a
      face at a closed node is closed.
    * Padding: a closed slot reads as @3's padded slot, the only kind @3's domain and field
      solve admit: its reference amounts and its charge anchor are 0 (so its physical amount
      and its charge are exactly 0 with zero increments), a closed population carries law
      code 0 and a closed contact's minimum open fraction is 0. A closed contact's gate is
      state and holds 0 (@3's domain): close_state pads it at the bind, and a closer that
      opens or closes a contact writes its gate at that event.
    """
    masks = {k: getattr(q, k) for k in MASK_FIELDS}
    for operator in closers:
        for name, value in operator.closures(state, p, q, xp=xp).items():
            masks[name] = masks[name] & value
    cell, node = masks["active"], masks["outside_active"]
    membrane = masks["membrane_active"] & cell[q.membrane_cell] & node[q.membrane_outside]
    channel = masks["channel_active"] & membrane[q.channel_membranes]
    junction = masks["junction_active"] & cell[q.junction_sender] & cell[q.junction_receiver]
    face = masks["face_active"] & node[q.face_sender] & node[q.face_receiver]
    return q._replace(
        active=cell,
        outside_active=node,
        membrane_active=membrane,
        channel_active=channel,
        junction_active=junction,
        face_active=face,
        amount_reference=xp.where(cell, q.amount_reference, 0.0),
        extracellular_amount_reference=xp.where(node, q.extracellular_amount_reference, 0.0),
        initial_cell_charge_C=xp.where(cell, q.initial_cell_charge_C, 0.0),
        initial_outside_charge_C=xp.where(node, q.initial_outside_charge_C, 0.0),
        channel_laws=xp.where(channel, q.channel_laws, 0),
        junction_minimum=xp.where(junction, q.junction_minimum, 0.0),
    )


def close_state(state, q, *, xp):
    """state with a closed contact's gate at 0, @3's padded value (q: a view with closers).

    The composite applies it to the initial state; afterwards the closers keep it (close)."""
    return state._replace(junction_gate=xp.where(q.junction_active, state.junction_gate, 0.0))


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


def check_field_inputs(p, nodes):
    """Refuse a field-input provider above the node cap or with floating capacitor components.

    nodes: the definition's padded field size (cell plus outside capacity).
    """
    if nodes > FIELD_INPUT_NODE_CAP:
        raise ConfigError(
            f"An operator that changes capacitances or activity masks refactorises the field "
            f"every step, so it is limited to {FIELD_INPUT_NODE_CAP} field nodes (cell plus "
            f"outside capacity; this definition has {nodes}). Larger worlds need option (b), "
            "refactorising only at declared insertion epochs, or (c), a rank-k update of the "
            "factor (docs/PUMP_COMPOSITE_V2_DESIGN.md §3)"
        )
    basis = np.asarray(p.field_floating_basis)
    if basis.size and basis.shape[1]:
        raise ConfigError(
            "An operator that changes capacitances or activity masks requires every "
            "capacitor component to hold a reservoir (no floating components)"
        )


def barrier(values, *, xp=jnp):
    """jax.lax.optimization_barrier on the device; the identity on the host."""
    return jax.lax.optimization_barrier(values) if xp is jnp else values


# @3's free energy (v2 design §1.1): the inner model's per-entity free-energy terms, owned here
# with the rest of @3's names. Operators that change @3's state outside its step (replacement
# events, injection half-steps) book their exact change with these; @3's balances hold the
# same terms. The chemical term of each cell is against its reference at the declared volume,
# in pJ; the capacitor term is over every membrane, in pJ.


def chemical_free_energy_pJ(delta, p, *, xp):
    """Per-cell chemical free-energy change from the reference (balances' own term), pJ."""
    a = xp.where(p.active, p.amount_reference, 1.0)
    term = delta * (xp.log(a / p.volume) - 1) + (a + delta) * xp.log1p(delta / a)
    return 1e-3 * R * p.temperature * xp.sum(xp.where(p.active, term, 0.0), axis=0)


def capacitor_free_energy_pJ(dv, p, *, xp):
    """Capacitor energy against the initial membrane voltages, pJ."""
    return 0.5e12 * xp.sum(p.membrane_capacitance * dv * (2 * p.initial_membrane_voltage_V + dv))


# @3's capacitor field at a view (v2 design §3, the energy rule; division design §5.1). @3's
# balances run on the declared layout, so their capacitor term is 1/2 sum C0 dv_b (2 V0 + dv_b)
# = 1/2 sum C0 (Vb^2 - V0^2), with Vb = V0 + dv_b the patch voltages that the declared
# capacitances and masks give the current charges. Once an operator provides capacitances or
# masks, the physical capacitor energy is 1/2 sum C V^2 - 1/2 sum C0 V0^2, with C and V at the
# view and the reference fixed at the declared initial state. view_capacitor_terms gives the
# difference, and the matching difference of the held nodes' plate charges for @3's electrode
# ledger. fixed_charge_change applies one capacitance change at fixed free-node charges.


def node_potentials(state, q, *, xp):
    """Node potentials (V) of @3's capacitor field at layout q: the charge anchors plus the
    state's increments on the free nodes, the held nodes at their bath potentials."""
    n = q.active.size
    charge = xp.concatenate((q.initial_cell_charge_C, q.initial_outside_charge_C))
    charge = charge + tissue.charge_increment(state, q, xp=xp)
    boundary = xp.concatenate((xp.zeros(n), q.boundary_V))
    return field._capacitor_solve(charge, boundary, tissue.field_layout(q), xp=xp)


def patch_voltages(phi, q, *, xp):
    n = q.active.size
    return xp.where(q.membrane_active, phi[q.membrane_cell] - phi[n + q.membrane_outside], 0.0)


def field_inputs_changed(view, bound, *, xp):
    """Whether a field input of the view differs from the declared one (as refresh_field tests)."""
    changed = xp.asarray(False)
    for name in FIELD_INPUTS:
        changed |= xp.any(getattr(view, name) != getattr(bound, name))
    return changed


def view_capacitor_terms(state, view, bound, *, xp):
    """@3's capacitor and electrode terms at the view, against its own on the declared layout.

    view: @3's layout at the composite state with its field arrays refreshed; bound: the
    declared layout. Returns (energy pJ, electrode C [outside], energy magnitude pJ,
    electrode magnitude C [outside]):
    * energy, 1/2 sum [(C - C0) V^2 + C0 (V - Vb)(V + Vb)], which brings @3's term
      1/2 sum C0 (Vb^2 - V0^2) to 1/2 sum C V^2 - 1/2 sum C0 V0^2. C and V are the view's
      capacitances and patch voltages at the current charges (0 on inactive patches); C0 and
      Vb = V0 + dv_b are @3's own, from the declared layout. No bulk energies are subtracted;
    * electrode, at each held node the view's plate charge less the declared layout's, both at
      the current charges: the clamps supplied the view's plate charges, so @3's electrode
      ledger subtracts it;
    * the magnitudes of their terms, for the rounding allowance.
    All four are exact zeros, selected, when no field input differs from the declared one.
    """
    n = bound.active.size
    _, cap, dv = tissue.capacitor_change(state, bound, xp=xp)
    vb = bound.initial_membrane_voltage_V + dv
    phi = node_potentials(state, view, xp=xp)
    v = patch_voltages(phi, view, xp=xp)
    c = xp.where(view.membrane_active, view.membrane_capacitance, 0.0)
    c0 = xp.where(bound.membrane_active, bound.membrane_capacitance, 0.0)
    energy = 0.5e12 * xp.sum((c - c0) * v**2 + c0 * (v - vb) * (v + vb))
    initial = xp.concatenate((bound.initial_cell_charge_C, bound.initial_outside_charge_C))
    boundary = xp.concatenate((xp.zeros(n), bound.boundary_V))
    base = field._capacitor_solve(initial, boundary, tissue.field_layout(bound), xp=xp)
    declared = (bound.field_capacitor_matrix @ base + cap)[n:]
    plates = (view.field_capacitor_matrix @ phi)[n:]
    changed = field_inputs_changed(view, bound, xp=xp)
    held = changed & bound.reservoir
    return (
        xp.where(changed, energy, 0.0),
        xp.where(held, plates - declared, 0.0),
        xp.where(changed, 0.5e12 * xp.sum(c * v**2 + c0 * vb**2), 0.0),
        xp.where(held, xp.abs(plates) + xp.abs(declared), 0.0),
    )


def charge_energy_change(state, dv0, dv1, view, *, xp):
    """The capacitor energy change (pJ) at the view of a change of charges only.

    dv0 and dv1 are tissue.capacitor_change's patch voltages at the view before and after;
    with V the view's patch voltages before, the change is 1/2 sum C dv (2 V + dv),
    dv = dv1 - dv0, which subtracts no bulk energies (an injection half-step at the view).
    """
    v = patch_voltages(node_potentials(state, view, xp=xp), view, xp=xp)
    c = xp.where(view.membrane_active, view.membrane_capacitance, 0.0)
    dv = dv1 - dv0
    return 0.5e12 * xp.sum(c * dv * (2 * v + dv))


def fixed_charge_change(state, q, dc, bound, *, xp):
    """One capacitance change C -> C + dc at fixed free-node charges (division design §5.1).

    q: @3's layout at the current view, its field arrays refreshed; dc [membrane] >= 0. With
    dKphi = sum_k dc_k V_k e_k, the free potentials move by delta_f = -(K'_ff)^-1 (dKphi)_f and
    the held nodes' plate charges by dq_b = (K' delta + dKphi)_b. The capacitor free energy
    G = max over phi_f of [q_f phi_f - 1/2 phi K phi] falls by
        H = 1/2 sum_k dc_k V_k^2 + 1/2 delta_f (dKphi)_f >= 0,
    whose second term, -1/2 (dKphi)_f (K'_ff)^-1 (dKphi)_f, is of second order: no bulk
    energies are subtracted. A one-patch cell gives V' = V C / C' and H = q^2 dc / (2 C C').

    Returns (q' with its field arrays refreshed, dq_b [outside] (zero off the held nodes), H per
    patch in pJ (the total shared in proportion to the first-order terms), the first-order
    terms 1/2 dc V^2 in pJ, the second-order term in pJ, the patch voltages before and after).
    """
    n, o = q.active.size, q.outside_active.size
    phi = node_potentials(state, q, xp=xp)
    v = patch_voltages(phi, q, xp=xp)
    q1 = refresh_field(q._replace(membrane_capacitance=q.membrane_capacitance + dc), bound, xp=xp)
    s = xp.where(q.membrane_active, dc * v, 0.0)
    dk = xp.concatenate(
        (
            scatter(s, xp.zeros(n), (q.membrane_cell,), xp=xp),
            -scatter(s, xp.zeros(o), (q.membrane_outside,), xp=xp),
        )
    )
    delta = field._capacitor_solve(-dk, xp.zeros_like(dk), tissue.field_layout(q1), xp=xp)
    image = (q1.field_capacitor_matrix @ delta + dk)[n:]
    first = 0.5e12 * s * v
    second = 0.5e12 * xp.sum(xp.where(q1.field_fixed, 0.0, delta * dk))
    total = xp.sum(first)
    positive = total > 0
    share = xp.where(positive, (total + second) / xp.where(positive, total, 1.0), 0.0)
    after = patch_voltages(phi + delta, q1, xp=xp)
    return q1, xp.where(bound.reservoir, image, 0.0), first * share, first, second, v, after
