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

Event map, per replaced slot i:
  * removal: the occupant's amounts are booked in replacement_removed_fmol (waste;
    the contents leave the system);
  * supply: the template's amounts are booked in replacement_supplied_fmol; the
    slot's amounts and channel gates become the template's; generation and
    occupant_template (1 + template row) advance;
  * incident junctions: lag and deficit restart from the declared arrival state,
    the gate is the junction law's value at Vj = 0 (law_open) or its steady state at
    the post-event Vj (law_steady, one extra field solve);
  * charge and energy: the held nodes' plate-charge change, from the same
    surface_tissue.capacitor_change that @3's electrode ledger uses, is booked as
    electrode transfer with its work; z F (supplied - removed) is booked in
    replacement_charge_C; the change of the chemical and capacitor free energy
    (balances' own expressions) minus that electrode work is booked in
    replacement_free_energy_pJ (an electric part shared equally by simultaneous
    events; the sum is exact) with its absolute terms in
    replacement_energy_magnitude_pJ for the rounding bound.
Untouched entries are selected, never offset by zero, so a world without events
reproduces @3 bitwise.

Checks. Host and device use @3's own row checks (surface_pump.checked_rows,
surface_pump_checks.row_checks, surface_pump.ledger_limits) with @3's balances
plus the replacement terms: local and total material (+ removed - supplied),
global charge (+ replacement charge), energy (- booked free energy); the material,
global-charge and energy rounding magnitudes add the replacement terms; the
domain adds the replacement fields. Stage 1 scope: worlds whose replaced slots
are in capacitor components with a held bath (an event changes a floating
component's net charge, which the field law holds constant; a gauge node alone
does not hold it).
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.cell_replacement_spec import (
    MODEL_ID,
    OPERATION_LAW_ID,
    Control,
    control_values,
    lineage,
    projection,
)
from cells.core.errors import NumericalError
from cells.core.specs import ChannelChange, ConfigError
from cells.core.surface_pump_v2_spec import Control as IonicControl
from cells.core.surface_pump_v3_spec import LAW_CODES
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic
from cells.models import surface_tissue as tissue
from cells.processes import junction_formation as formation
from cells.processes import junction_gate
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R

OBSERVER_ID = "resolved_pump_replacement_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = ionic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_replacement_ledgers@1"
BATCH_CAPACITIES = ionic.BATCH_CAPACITIES
SPLITTING_ID = "event_formation_ionic_formation@1"
REPLACEMENT_STATE_AXES = {
    "generation": ["cell_slot"],  # int64: events applied to the slot.
    "occupant_template": ["cell_slot"],  # int64: 1 + template row of the occupant; 0 founder.
    "junction_lag_remaining_s": ["edge_slot"],
    "junction_abundance_deficit": ["edge_slot"],  # 1 - A; 0 for a formed junction.
    "replacement_removed_fmol": ["species", "cell_slot"],
    "replacement_supplied_fmol": ["species", "cell_slot"],
    "replacement_charge_C": ["cell_slot"],
    "replacement_free_energy_pJ": ["cell_slot"],
    "replacement_energy_magnitude_pJ": ["cell_slot"],
    "replacement_image_charge_C": ["extracellular_slot"],  # Sum of |image charge| booked.
}
STATE_AXES = ionic.STATE_AXES | REPLACEMENT_STATE_AXES
STATE_TYPE = NamedTuple("SurfacePumpReplacementState", [(k, object) for k in STATE_AXES])
REPLACEMENT_LAYOUT_FIELDS = (
    "template_amount_fmol",  # [rows, species]
    "template_channel_gate",  # [rows, 2, law]
    "template_channel_permeability",  # [rows, law]
    "template_channel_permeability_set",
    "template_channel_abundance",  # [rows, law]
    "template_channel_abundance_set",
    "template_membrane_permeability",  # [rows, species]
    "template_membrane_permeability_set",
    "template_pump_density",  # [rows] fmol/(s m^2)
    "template_pump_density_set",
    "template_calcium_pump_density",
    "template_calcium_pump_density_set",
    "slot_event_count",  # [capacity] int64
    "formation_initial_abundance",
    "formation_lag_s",
    "formation_time_constant_s",
    "arrival_gate_steady",  # shape (0,) law_open, (1,) law_steady: a static choice.
)
LAYOUT_TYPE = NamedTuple(
    "SurfacePumpReplacementLayout",
    [(k, object) for k in (*ionic.LAYOUT_TYPE._fields, *REPLACEMENT_LAYOUT_FIELDS)],
)
FLOOR_LAYOUT_TYPE = NamedTuple(
    "SurfacePumpReplacementFloorLayout",
    [(k, object) for k in (*ionic.FLOOR_LAYOUT_TYPE._fields, *REPLACEMENT_LAYOUT_FIELDS)],
)
ENERGY_RTOL = ionic.ENERGY_RTOL
EXPLICIT_STEP_BOUND = ionic.EXPLICIT_STEP_BOUND
IONIC_FIELDS = ionic.STATE_TYPE._fields
DISSIPATION_FIELDS = ionic.DISSIPATION_FIELDS
INTEGER_FIELDS = ("generation", "occupant_template")

parameters = ionic.parameters
physical_amounts = ionic.physical_amounts
rebind = first.rebind


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


def ionic_state(state):
    return ionic.STATE_TYPE(*(getattr(state, k) for k in IONIC_FIELDS))


def abundance(state):
    return formation.abundance(state.junction_abundance_deficit)


def ionic_control(control, state):
    """@3's control with junction availability times the junction abundance."""
    return IonicControl(
        control.membrane,
        control.junction * abundance(state),
        control.channel,
        control.pump,
        control.calcium_pump,
    )


def formation_parameters(p):
    return formation.Parameters(
        p.formation_initial_abundance, p.formation_lag_s, p.formation_time_constant_s
    )


def ionic_layout(p, state=None, *, xp=jnp):
    """The @3 layout: declared values, or each slot's occupant route values."""
    kind = ionic.FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else ionic.LAYOUT_TYPE
    q = kind(*(getattr(p, k) for k in kind._fields))
    if state is None:
        return q
    occupant = state.occupant_template
    row, has = xp.maximum(occupant - 1, 0), occupant > 0
    cell = p.membrane_cell[p.channel_membranes]
    c_row, c_has = row[cell], has[cell] & p.channel_active
    law = p.channel_laws
    m_row, m_has = row[p.membrane_cell], has[p.membrane_cell] & p.membrane_active

    def channel(values, mask, base):
        return xp.where(mask[c_row, law] & c_has, values[c_row, law], base)

    def pump(values, mask, base):
        return xp.where(mask[m_row] & m_has, values[m_row] * p.membrane_area, base)

    leak = p.template_membrane_permeability_set[m_row].T & m_has
    return q._replace(
        channel_permeability=channel(
            p.template_channel_permeability,
            p.template_channel_permeability_set,
            p.channel_permeability,
        ),
        channel_abundance=channel(
            p.template_channel_abundance, p.template_channel_abundance_set, p.channel_abundance
        ),
        membrane_permeability=xp.where(
            leak, p.template_membrane_permeability[m_row].T, p.membrane_permeability
        ),
        pump_capacity=pump(p.template_pump_density, p.template_pump_density_set, p.pump_capacity),
        calcium_pump_capacity=pump(
            p.template_calcium_pump_density,
            p.template_calcium_pump_density_set,
            p.calcium_pump_capacity,
        ),
    )


# ------------------------------------------------------------------ definition


def _template_tables(spec, rows):
    m, r = spec.model, spec.model.replacement
    species, laws = list(m.species_ids), list(LAW_CODES)
    s, nl = len(species), len(laws)
    t = dict(
        template_amount_fmol=np.ones((rows, s)),
        template_channel_gate=np.zeros((rows, 2, nl)),
        template_channel_permeability=np.zeros((rows, nl)),
        template_channel_permeability_set=np.zeros((rows, nl), dtype=bool),
        template_channel_abundance=np.zeros((rows, nl)),
        template_channel_abundance_set=np.zeros((rows, nl), dtype=bool),
        template_membrane_permeability=np.zeros((rows, s)),
        template_membrane_permeability_set=np.zeros((rows, s), dtype=bool),
        template_pump_density=np.zeros(rows),
        template_pump_density_set=np.zeros(rows, dtype=bool),
        template_calcium_pump_density=np.zeros(rows),
        template_calcium_pump_density_set=np.zeros(rows, dtype=bool),
    )
    for k, template in enumerate(r.templates):
        t["template_amount_fmol"][k] = template.amounts_fmol
        for law, gates in template.channel_gates:
            t["template_channel_gate"][k, : len(gates), laws.index(law)] = gates
        for name, values, index in (
            ("template_channel_permeability", template.channel_permeability_m_per_s, laws),
            ("template_channel_abundance", template.channel_abundance, laws),
            ("template_membrane_permeability", template.membrane_permeability_m_per_s, species),
        ):
            for key, value in values:
                t[name][k, index.index(key)] = value
                t[name + "_set"][k, index.index(key)] = True
        for name, value in (
            ("template_pump_density", template.pump_capacity_fmol_per_s_m2),
            ("template_calcium_pump_density", template.calcium_pump_capacity_fmol_per_s_m2),
        ):
            if value is not None:
                t[name][k], t[name + "_set"][k] = value, True
    return t


def initial_values(spec):
    state, p = ionic.initial_values(projection(spec))
    m, x, r = spec.model, spec.execution, spec.model.replacement
    n, ne, s = x.capacity, x.edge_capacity, len(m.species_ids)
    f = r.junction_formation
    counts = np.zeros(n, dtype=np.int64)
    order = {c.id: i for i, c in enumerate(m.cells)}
    for v in spec.experiment.replacement_events:
        counts[order[v.slot]] += 1
    values = _template_tables(spec, r.template_capacity) | dict(
        slot_event_count=counts,
        formation_initial_abundance=np.asarray(f.initial_abundance),
        formation_lag_s=np.asarray(f.lag_s),
        formation_time_constant_s=np.asarray(f.time_constant_s),
        arrival_gate_steady=np.zeros(1 if f.gate_at_arrival == "law_steady" else 0),
    )
    extra = (
        np.zeros(n, dtype=np.int64),
        np.zeros(n, dtype=np.int64),
        np.zeros(ne),
        np.zeros(ne),
        np.zeros((s, n)),
        np.zeros((s, n)),
        np.zeros(n),
        np.zeros(n),
        np.zeros(n),
        np.zeros(x.extracellular_capacity),
    )
    kind = FLOOR_LAYOUT_TYPE if type(p) is ionic.FLOOR_LAYOUT_TYPE else LAYOUT_TYPE
    return STATE_TYPE(*state, *extra), kind(*p, *(values[k] for k in REPLACEMENT_LAYOUT_FIELDS))


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


def held_cells(p):
    """Cells whose capacitor component contains a held bath (a reservoir node).

    A gauge node is not enough: it fixes the potential reference of a floating
    component whose net charge the field law holds constant, and an event changes
    the replaced cell's charge (the inner step then refuses).
    """
    matrix = np.asarray(p.field_capacitor_matrix)
    active = np.asarray(p.field_active)
    fixed = np.concatenate((np.zeros(p.active.size, dtype=bool), np.asarray(p.reservoir)))
    nodes = matrix.shape[0]
    label = -np.ones(nodes, dtype=np.int64)
    held = []
    for start in range(nodes):
        if label[start] >= 0 or not active[start]:
            continue
        stack, members = [start], []
        label[start] = start
        while stack:
            i = stack.pop()
            members.append(i)
            for j in np.flatnonzero((matrix[i] != 0) & active):
                if label[j] < 0:
                    label[j] = start
                    stack.append(j)
        held.append((members, bool(np.any(fixed[members]))))
    result = np.zeros(p.active.size, dtype=bool)
    for members, has_fixed in held:
        for i in members:
            if i < p.active.size:
                result[i] = has_fixed
    return result


def check_definition(spec):
    """Stage-1 scope, then each template in the domain at its first slot.

    The inner definition was checked by its own parser. A replaced slot needs a
    held node in its capacitor component. For each template, its first event is
    applied to the initial state (the event map on the host) and the occupant
    state must lie in @3's domain with a valid field.
    """
    small = compact(spec)
    state, p = initial_values(small)
    order = {c.id: i for i, c in enumerate(small.model.cells)}
    held = held_cells(p)
    for v in small.experiment.replacement_events:
        if not held[order[v.slot]]:
            raise ConfigError(
                f"Replacement slot {v.slot} has no held node in its capacitor component "
                "(stage 1 supports held-bath components only)"
            )
    rows = {t.id: k + 1 for k, t in enumerate(small.model.replacement.templates)}
    controls = control_values(small, [0.0])
    base = Control(*(np.asarray(v[0]) for v in controls))
    checked = set()
    with np.errstate(all="ignore"):
        for v in small.experiment.replacement_events:
            if v.template in checked:
                continue
            checked.add(v.template)
            i = order[v.slot]
            generation, template = np.zeros_like(base.generation), np.zeros_like(base.template)
            generation[i], template[i] = 1, rows[v.template]
            control = base._replace(generation=generation, template=template)
            after, ok = apply_events(state, control, p, xp=np)
            if not ok or not control_domain_valid(after, control, p, p.active, xp=np):
                raise ConfigError(f"Template {v.template} is outside the domain at slot {v.slot}")


def check_steps(spec, steps, controls):
    """@3's step checks on the worst-case inner definition, every occupant included.

    Each replaced slot takes the largest leak permeabilities and pump capacities over
    its founder and its templates (@3's explicit-rate and calcium bounds read
    them); channel stiffness is refused in-step by @3 at the actual openings.
    """
    ionic.check_steps(worst_case(spec), steps, controls)


def worst_case(spec):
    base = projection(spec)
    m = base.model
    species = list(m.species_ids)
    names = {t.id: t for t in spec.model.replacement.templates}
    by_slot = {}
    for v in spec.experiment.replacement_events:
        by_slot.setdefault(v.slot, set()).add(v.template)
    membranes = []
    for p in m.membranes:
        templates = [names[t] for t in by_slot.get(p.inside, ())]
        leak = list(p.permeability_m_per_s)
        pump, calcium = p.pump, p.calcium_pump
        for t in templates:
            for s, value in t.membrane_permeability_m_per_s:
                leak[species.index(s)] = max(leak[species.index(s)], value)
            if t.pump_capacity_fmol_per_s_m2 is not None:
                cap = t.pump_capacity_fmol_per_s_m2 * p.area_m2
                pump = replace(pump, capacity_fmol_per_s=max(pump.capacity_fmol_per_s, cap))
            if t.calcium_pump_capacity_fmol_per_s_m2 is not None:
                cap = t.calcium_pump_capacity_fmol_per_s_m2 * p.area_m2
                calcium = replace(
                    calcium, capacity_fmol_per_s=max(calcium.capacity_fmol_per_s, cap)
                )
        membranes.append(
            replace(p, permeability_m_per_s=tuple(leak), pump=pump, calcium_pump=calcium)
        )
    return replace(base, model=replace(m, membranes=tuple(membranes)))


# ------------------------------------------------------------------ the operation


def _chemical(delta, p, *, xp):
    """Per-cell chemical free-energy change from the reference (balances' own term), pJ."""
    a = xp.where(p.active, p.amount_reference, 1.0)
    term = delta * (xp.log(a / p.volume) - 1) + (a + delta) * xp.log1p(delta / a)
    return 1e-3 * R * p.temperature * xp.sum(xp.where(p.active, term, 0.0), axis=0)


def _electric(dv, p, *, xp):
    return 0.5e12 * xp.sum(p.membrane_capacitance * dv * (2 * p.initial_membrane_voltage_V + dv))


def event_map(state, due, control, p, *, xp=jnp):
    """Replace the carriers of the due slots (module docstring); the new state."""
    n = p.active.size
    row = xp.maximum(control.template - 1, 0)
    reference = p.amount_reference
    old = reference + state.amount_increment
    template = p.template_amount_fmol[row].T
    slot = due[None, :]
    increment = xp.where(slot, template - reference, state.amount_increment)
    dq = CHARGE_PER_FMOL * xp.sum(p.valence * (template - old), axis=0)
    cell = p.membrane_cell[p.channel_membranes]
    replaced = (due[cell] & p.channel_active)[None, :] & p.channel_gate_active
    gate = p.template_channel_gate[row[cell], :, p.channel_laws].T
    edge = p.junction_active & (due[p.junction_sender] | due[p.junction_receiver])
    lag0, deficit0 = formation.arrival(formation_parameters(p), xp=xp)
    params = junction_gate.Parameters(p.junction_threshold_voltage, p.junction_minimum)
    opened = junction_gate.kinetics(xp.zeros_like(p.junction_threshold_voltage), params, xp=xp)
    new = state._replace(
        amount_increment=increment,
        channel_gate=xp.where(replaced, gate, state.channel_gate),
        junction_gate=xp.where(edge, opened.target, state.junction_gate),
        junction_lag_remaining_s=xp.where(edge, lag0, state.junction_lag_remaining_s),
        junction_abundance_deficit=xp.where(edge, deficit0, state.junction_abundance_deficit),
        generation=xp.where(due, state.generation + 1, state.generation),
        occupant_template=xp.where(due, control.template, state.occupant_template),
        replacement_removed_fmol=xp.where(
            slot, state.replacement_removed_fmol + old, state.replacement_removed_fmol
        ),
        replacement_supplied_fmol=xp.where(
            slot, state.replacement_supplied_fmol + template, state.replacement_supplied_fmol
        ),
        replacement_charge_C=xp.where(
            due, state.replacement_charge_C + dq, state.replacement_charge_C
        ),
    )
    if p.arrival_gate_steady.shape[0]:
        v = ionic.field_values(
            ionic_state(new), ionic_control(control, new), ionic_layout(p, new, xp=xp), xp=xp
        )
        steady = junction_gate.kinetics(v.rates.junction_voltage_V, params, xp=xp).target
        new = new._replace(junction_gate=xp.where(edge, steady, new.junction_gate))
    # Electrode image charge on held nodes and the free-energy booking.
    q = ionic_layout(p)
    _, start, dv0 = tissue.capacitor_change(ionic_state(state), q, xp=xp)
    _, end, dv1 = tissue.capacitor_change(ionic_state(new), q, xp=xp)
    electrode = xp.where(p.reservoir, end[n:] - start[n:], 0.0)
    work = 1e12 * p.boundary_V * electrode
    g0 = _chemical(state.amount_increment, p, xp=xp)
    g1 = _chemical(increment, p, xp=xp)
    e0, e1 = _electric(dv0, p, xp=xp), _electric(dv1, p, xp=xp)
    count = xp.maximum(xp.sum(due), 1)
    shared = (e1 - e0 - xp.sum(work)) / count
    magnitude = xp.abs(g0) + xp.abs(g1) + (xp.abs(e0) + xp.abs(e1) + xp.sum(xp.abs(work))) / count
    return new._replace(
        electrode_charge_transferred_C=state.electrode_charge_transferred_C + electrode,
        replacement_image_charge_C=state.replacement_image_charge_C + xp.abs(electrode),
        electrode_work_pJ=state.electrode_work_pJ + work,
        replacement_free_energy_pJ=xp.where(
            due,
            state.replacement_free_energy_pJ + (g1 - g0) + shared,
            state.replacement_free_energy_pJ,
        ),
        replacement_energy_magnitude_pJ=xp.where(
            due,
            state.replacement_energy_magnitude_pJ + magnitude,
            state.replacement_energy_magnitude_pJ,
        ),
    )


def apply_events(state, control, p, *, xp=jnp):
    """(state after the due replacements, schedule consistency) at a step start."""
    due = p.active & (control.generation == state.generation + 1)
    stale = p.active & ~due & (control.generation != state.generation)
    ok = ~xp.any(stale) & xp.all(xp.where(due, control.template >= 1, True))
    if xp is np:
        return (event_map(state, due, control, p, xp=np) if np.any(due) else state), ok
    return (
        jax.lax.cond(
            jnp.any(due),
            lambda s: event_map(s, due, control, p),
            lambda s: s,
            state,
        ),
        ok,
    )


def replacement_domain_valid(state, p, *, xp=jnp):
    """Replacement fields: counts within the schedule, formation domain, signed ledgers."""
    g, t = state.generation, state.occupant_template
    rows = p.template_amount_fmol.shape[0]
    valid = xp.all((g >= 0) & (g <= p.slot_event_count))
    valid &= xp.all((t >= 0) & (t <= rows)) & xp.all((g == 0) == (t == 0))
    valid &= xp.all(xp.where(p.active, True, (g == 0) & (t == 0)))
    valid &= formation.domain_valid(
        state.junction_lag_remaining_s, state.junction_abundance_deficit, xp=xp
    )
    for name in ("junction_lag_remaining_s", "junction_abundance_deficit"):
        valid &= xp.all(xp.where(p.junction_active, True, getattr(state, name) == 0))
    fresh = g == 0
    for name in ("replacement_removed_fmol", "replacement_supplied_fmol"):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
        valid &= xp.all(xp.where(fresh[None, :], value == 0, True))
    for name in (
        "replacement_charge_C",
        "replacement_free_energy_pJ",
        "replacement_energy_magnitude_pJ",
    ):
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(fresh, value == 0, True))
    valid &= xp.all(state.replacement_energy_magnitude_pJ >= 0)
    image = state.replacement_image_charge_C
    valid &= xp.all(xp.isfinite(image)) & xp.all(image >= 0)
    valid &= xp.all(xp.where(p.reservoir, True, image == 0))
    valid &= xp.where(xp.any(g > 0), True, xp.all(image == 0))
    return valid


def domain_valid(state, p, active, *, xp=jnp):
    valid = ionic.domain_valid(ionic_state(state), ionic_layout(p), active, xp=xp)
    return valid & replacement_domain_valid(state, p, xp=xp)


def checked_step(state, dt, control, p, active):
    """Event map, formation dt/2, @3's checked step, formation dt/2; refusal keeps the start."""
    moved, ok = apply_events(state, control, p)
    h = 0.5 * dt
    parameters_ = formation_parameters(p)
    lag, deficit = formation.advance(
        moved.junction_lag_remaining_s, moved.junction_abundance_deficit, h, parameters_
    )
    middle = moved._replace(junction_lag_remaining_s=lag, junction_abundance_deficit=deficit)
    inputs = jax.lax.optimization_barrier(
        (ionic_state(middle), ionic_control(control, middle), ionic_layout(p, middle))
    )
    stepped, ionic_ok = ionic.checked_step(inputs[0], dt, inputs[1], inputs[2], p.active)
    stepped, ionic_ok = jax.lax.optimization_barrier((stepped, ionic_ok))
    lag, deficit = formation.advance(lag, deficit, h, parameters_)
    final = middle._replace(
        **stepped._asdict(), junction_lag_remaining_s=lag, junction_abundance_deficit=deficit
    )
    valid = ok & ionic_ok & replacement_domain_valid(final, p)
    return jax.tree.map(lambda old, new: jnp.where(valid, new, old), state, final), valid


# ------------------------------------------------------------------ readouts


class Values(NamedTuple):
    field: object
    derivative: object
    ionic: object
    valid: object


def formation_rates(state, p, *, xp=jnp):
    """d(lag)/dt and d(deficit)/dt of the formation law (for rhs; steps use advance)."""
    lag, deficit = state.junction_lag_remaining_s, state.junction_abundance_deficit
    waiting = lag > 0
    return (
        xp.where(waiting, -1.0, 0.0),
        xp.where(waiting, 0.0, -deficit / p.formation_time_constant_s),
    )


def readouts(state, control, p, *, xp=jnp):
    """@3's readouts at the occupant view and junction abundance (rhs, observations)."""
    v = ionic.readouts(
        ionic_state(state), ionic_control(control, state), ionic_layout(p, state, xp=xp), xp=xp
    )
    lag_rate, deficit_rate = formation_rates(state, p, xp=xp)
    zeros = {k: xp.zeros_like(getattr(state, k)) for k in REPLACEMENT_STATE_AXES}
    zeros |= dict(junction_lag_remaining_s=lag_rate, junction_abundance_deficit=deficit_rate)
    derivative = STATE_TYPE(*v.derivative, *(zeros[k] for k in REPLACEMENT_STATE_AXES))
    valid = v.valid & replacement_domain_valid(state, p, xp=xp)
    return Values(v.field._replace(converged=valid), derivative, v, valid)


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return np.asarray(readouts(state, control, p, xp=np).valid)
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


# ------------------------------------------------------------------ checks


def _terms(result, state, *, xp):
    """@3's ledgers with the replacement terms, in @3's order and keys."""
    net = state.replacement_removed_fmol - state.replacement_supplied_fmol
    result["local"] = result["local"] + net
    result["total"] = result["total"] + xp.sum(net, axis=1)
    result["global_charge"] = result["global_charge"] + xp.sum(state.replacement_charge_C)
    result["energy"] = result["energy"] - xp.sum(state.replacement_free_energy_pJ)
    return result


def balances(state, p):
    return _terms(ionic.balances(ionic_state(state), ionic_layout(p)), state, xp=np)


def device_balances(state, p):
    return _terms(ionic.device_balances(ionic_state(state), ionic_layout(p)), state, xp=jnp)


def magnitudes(row, p, *, xp=np):
    """@3's ledger magnitudes plus the replacement terms (first.LEDGERS order).

    Material: removed + supplied amounts. Electrode, global charge and energy (None
    for @3, whose bounds are fixed) take the booked image charge, the replacement
    charge and the energy magnitudes, so without events the bounds are @3's exactly
    (bound + 0). The electrode term is the family's running-ledger allowance: after
    an image charge is booked, each step's electrode increment is added to a sum of
    that size, rounding eps times it per step.
    """
    result = list(ionic.channel_magnitudes(ionic_state(row), ionic_layout(p), xp=xp))
    moved = row.replacement_removed_fmol + row.replacement_supplied_fmol
    result[0] = result[0] + moved
    result[2] = result[2] + xp.sum(moved, axis=1)
    result[5] = CHARGE_PER_FMOL * xp.sum(xp.abs(p.valence) * moved)
    result[4] = row.replacement_image_charge_C
    result[6] = xp.sum(row.replacement_energy_magnitude_pJ)
    return tuple(result)


def check_values(state, spec, steps=None):
    """@3's host row checks (surface_pump.checked_rows) with the replacement terms."""
    _, p = initial_values(spec)
    return first.checked_rows(
        state,
        spec,
        p,
        domain=domain_valid,
        balances=balances,
        magnitudes=magnitudes,
        dissipation=DISSIPATION_FIELDS,
        steps=steps,
    )


DEVICE_CHECKS = ionic.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = ionic.DEVICE_DIAGNOSTICS
device_failure_message = ionic.device_failure_message
device_check_constants = ionic.device_check_constants


def device_checks(previous, row, p, constants, steps):
    """check_values' tests for one accepted row on the device: (failed, diagnostics)."""
    from cells.models.surface_pump_checks import row_checks

    return row_checks(
        previous,
        row,
        p,
        constants,
        steps,
        domain_valid=domain_valid,
        balances=device_balances,
        limits=first.ledger_limits,
        magnitudes=magnitudes,
        dissipation=DISSIPATION_FIELDS,
    )


# ------------------------------------------------------------------ observations

REPLACEMENT_READOUTS = ("junction_abundance",)
OBSERVATION_FIELDS = (*ionic.OBSERVATION_FIELDS, *REPLACEMENT_STATE_AXES, *REPLACEMENT_READOUTS)
Observations = make_dataclass(
    "SurfacePumpReplacementObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)


def _held_junctions(base, junction):
    """The inner definition with each junction availability held at one value."""
    e = base.experiment
    held = tuple((ChannelChange(0.0, float(v)),) for v in junction[: len(e.junctions)])
    return replace(base, experiment=replace(e, junctions=held))


def observe_history(times, history, layout, requested, spec):
    """@3's observations of each row at its occupant view; junction availability x A.

    @3's observer reads its controls from its definition, so each row is observed
    on the inner definition with every junction availability held at its
    scheduled value times that row's abundance (the effective availability, which
    the junction control field then reports), plus the replacement fields.
    """
    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved pump replacement observations require accepted times")
    controls, base, records = control_values(spec, requested), projection(spec), []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        control = Control(*(v[j] for v in controls))
        a = np.asarray(abundance(state))
        one = ionic.STATE_TYPE(*(getattr(state, k)[None] for k in IONIC_FIELDS))
        observed = ionic.observe_history(
            np.array([t]),
            one,
            ionic_layout(p, state, xp=np),
            np.array([t]),
            _held_junctions(base, np.asarray(control.junction) * a),
        )
        row = {k: v[0] for k, v in vars(observed).items()}
        row.update({k: getattr(state, k) for k in REPLACEMENT_STATE_AXES})
        row["junction_abundance"] = a
        records.append(row)
    if records:
        return Observations(*(np.stack([r[k] for r in records]) for k in OBSERVATION_FIELDS))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    controls = control_values(spec, [time])
    control = Control(*(v[0] for v in controls))
    p = type(layout)(*(np.asarray(v) for v in layout))
    v = field_values(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not v.converged:
        raise NumericalError("Resolved pump replacement ensemble endpoint invalid")
    return v.rates.membrane_voltage_V[p.membrane_active]


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
    }
