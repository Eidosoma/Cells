"""Operator scheduled_cell_replacement@1: scheduled carrier replacement with junction formation.

The operation, the junction formation law delayed_first_order_junction_formation@1
and their ledgers, moved here unchanged from resolved_pump_replacement@1
(models/cell_replacement.py, now a thin composition; docs/CELL_REPLACEMENT.md, D139).

Event map, per replaced slot i, at the start of the step leaving an event time t_e:
  * removal: the occupant's amounts are booked in replacement_removed_fmol (waste;
    the contents leave the system);
  * supply: the template's amounts, or for a donor copy (an inheritance route)
    the donor's amounts before any event at that time, are booked in
    replacement_supplied_fmol (the donor keeps its contents); the slot's amounts
    and channel gates become the template's or the donor's (by channel law);
    generation and occupant_template (1 + the route template's row, 0 for the
    slot's own route values) advance;
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
Untouched entries are selected, never offset by zero. A refused step returns the
state before the event, so an event is applied in full or not at all. The
junction abundance A of each junction at a slot follows the formation law and
multiplies the junction's availability; it is held at its step-midpoint value
inside @3's step (exact half-steps around it).

Contract (models/operators/contract.py):
* owned state: generation and occupant template per slot (int64), the formation
  law's lag and deficit per junction, the removal, supply, charge, free-energy and
  image-charge ledgers;
* entity writes: the replaced slots' amounts (booked as removal and supply, and
  their net charge), the held baths' plate charge and its work (booked in @3's
  electrode accumulators, with the image-charge magnitude); resets of the slots'
  channel gates and of the incident junction gates, which are intensive kinetic
  state without a ledger;
* view: each slot's occupant route values as @3's channel permeability and
  abundance, leak permeability and pump capacities; a factor on @3's junction
  availability, the junction abundance A (a product with any other factor);
* parts: an event map and a split process (the exact formation update over dt/2),
  kept split under an RK4 inner step;
* refusal: a schedule disagreement refuses the step; templates are checked
  against the declared slot volume, so no other operator may provide a volume;
  replaced slots need a held bath in their capacitor component.
"""

from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import cell_replacement_spec as replacement_spec
from cells.core import pump_composite_spec as composite_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core.specs import ConfigError, _fields, _integer
from cells.core.surface_pump_v2_spec import Control as IonicControl
from cells.core.surface_pump_v3_spec import LAW_CODES
from cells.models import surface_pump_v3 as ionic
from cells.models import surface_tissue as tissue
from cells.models.operators.contract import Operator
from cells.numerics.extracellular_field import scatter
from cells.processes import junction_formation as formation
from cells.processes import junction_gate
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R

LAW_ID = replacement_spec.OPERATION_LAW_ID
IONIC_FIELDS = ionic.STATE_TYPE._fields

# ------------------------------------------------------------------ the operation
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
    "cell_law_channel",  # [capacity, law] int64: the cell's population of that law; -1 none.
    "formation_initial_abundance",
    "formation_lag_s",
    "formation_time_constant_s",
    "arrival_gate_steady",  # shape (0,) law_open, (1,) law_steady: a static choice.
)


INTEGER_FIELDS = ("generation", "occupant_template")


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


def law_channels(spec):
    """[capacity, law] channel index of each cell's population of a law (-1: none).

    Donor copies read a donor's gates by law; the parser admits only donors with
    exactly one population of each gated law the slot has.
    """
    m, x = spec.model, spec.execution
    cells = {c.id: i for i, c in enumerate(m.cells)}
    owner = {p.id: cells[p.inside] for p in m.membranes}
    laws = list(LAW_CODES)
    table = -np.ones((x.capacity, len(laws)), dtype=np.int64)
    for k, c in enumerate(m.channels):
        i, law = owner[c.membrane_id], laws.index(c.kinetic_law)
        if table[i, law] < 0:
            table[i, law] = k
    return table


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
    copy = control.donor > 0  # Donor copies (inheritance route); else the template.
    donor = xp.maximum(control.donor - 1, 0)
    reference = p.amount_reference
    old = reference + state.amount_increment
    # Supply: the template's amounts, or the donor's before any event at this time.
    template = xp.where(copy[None, :], old[:, donor], p.template_amount_fmol[row].T)
    slot = due[None, :]
    increment = xp.where(slot, template - reference, state.amount_increment)
    dq = CHARGE_PER_FMOL * xp.sum(p.valence * (template - old), axis=0)
    cell = p.membrane_cell[p.channel_membranes]
    replaced = (due[cell] & p.channel_active)[None, :] & p.channel_gate_active
    source = xp.maximum(p.cell_law_channel[donor[cell], p.channel_laws], 0)
    gate = xp.where(
        copy[cell][None, :],
        state.channel_gate[:, source],
        p.template_channel_gate[row[cell], :, p.channel_laws].T,
    )
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
    supplied = (control.template >= 1) | (control.donor >= 1)
    ok = ~xp.any(stale) & xp.all(xp.where(due, supplied, True))
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
    valid &= xp.all((t >= 0) & (t <= rows)) & xp.all(xp.where(g == 0, t == 0, True))
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


def formation_rates(state, p, *, xp=jnp):
    """d(lag)/dt and d(deficit)/dt of the formation law (for rhs; steps use advance)."""
    lag, deficit = state.junction_lag_remaining_s, state.junction_abundance_deficit
    waiting = lag > 0
    return (
        xp.where(waiting, -1.0, 0.0),
        xp.where(waiting, 0.0, -deficit / p.formation_time_constant_s),
    )


def _terms(result, state, *, xp):
    """@3's ledgers with the replacement terms, in @3's order and keys."""
    net = state.replacement_removed_fmol - state.replacement_supplied_fmol
    result["local"] = result["local"] + net
    result["total"] = result["total"] + xp.sum(net, axis=1)
    result["global_charge"] = result["global_charge"] + xp.sum(state.replacement_charge_C)
    result["energy"] = result["energy"] - xp.sum(state.replacement_free_energy_pJ)
    return result


def replaced_charge_magnitude(row, p, *, xp=np):
    """Per outside node: F sum |z| |amount increment| of the replaced cells facing it.

    After a whole-content swap a slot's amount increment (against the founder's
    declared reference) is a cell's worth of ions, about 50 fmol. Each step that
    updates it rounds by eps times its size, which moves the slot's charge by about
    1e-24 C. IMEX books the electrode from the rounded states and telescopes; RK4
    integrates the electrode from stage currents, so the plate charge and the
    electrode sum random-walk apart by that much per step (diagnosis,
    cell-replacement-g2-20261111-01/rk4-electrode: not a booking error, and not the
    plate-charge evaluation, which exact arithmetic reproduces to 1.5e-33 C). Zero
    for founders, so it vanishes without events.
    """
    replaced = row.generation > 0
    cell = CHARGE_PER_FMOL * xp.sum(xp.abs(p.valence * row.amount_increment), axis=0)
    per_patch = xp.where(p.membrane_active & replaced[p.membrane_cell], cell[p.membrane_cell], 0.0)
    return scatter(per_patch, xp.zeros_like(p.boundary_V), (p.membrane_outside,), xp=xp)


REPLACEMENT_READOUTS = ("junction_abundance",)


# ------------------------------------------------------------------ binding and checks


def template_tables(templates, species, rows):
    """The templates' amounts, gates and route values as [rows, ...] tables (padded)."""
    laws = list(LAW_CODES)
    species = list(species)
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
    for k, template in enumerate(templates):
        if template.amounts_fmol is not None:  # Route-only templates keep the padding.
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


def bind(spec, declaration, events):
    """The replacement state (zero) and layout fields of a definition."""
    m, x = spec.model, spec.execution
    n, ne, s = x.capacity, x.edge_capacity, len(m.species_ids)
    f = declaration.junction_formation
    counts = np.zeros(n, dtype=np.int64)
    order = {c.id: i for i, c in enumerate(m.cells)}
    for v in events:
        counts[order[v.slot]] += 1
    values = template_tables(declaration.templates, m.species_ids, declaration.template_capacity)
    values |= dict(
        slot_event_count=counts,
        cell_law_channel=law_channels(spec),
        formation_initial_abundance=np.asarray(f.initial_abundance),
        formation_lag_s=np.asarray(f.lag_s),
        formation_time_constant_s=np.asarray(f.time_constant_s),
        arrival_gate_steady=np.zeros(1 if f.gate_at_arrival == "law_steady" else 0),
    )
    zeros = (
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
    return (
        dict(zip(REPLACEMENT_STATE_AXES, zeros, strict=True)),
        {k: values[k] for k in REPLACEMENT_LAYOUT_FIELDS},
    )


def check_definition(spec, declaration, events, model):
    """Stage-1 scope, then each template in the domain at its first slot.

    The inner definition was checked by its own parser. A replaced slot needs a
    held node in its capacitor component. For each template, its first event is
    applied to the initial state (the event map on the host) and the occupant
    state must lie in the composition's domain with a valid field.
    """
    from cells.models.pump_composite import compact

    small = compact(spec)
    state, p = model.initial_values(small)
    order = {c.id: i for i, c in enumerate(small.model.cells)}
    held = held_cells(p)
    for v in events:
        if not held[order[v.slot]]:
            raise ConfigError(
                f"Replacement slot {v.slot} has no held node in its capacitor component "
                "(stage 1 supports held-bath components only)"
            )
    rows = {t.id: k + 1 for k, t in enumerate(declaration.templates)}
    controls = composite_spec.control_values(small, [0.0])
    base = model.CONTROL_TYPE(*(np.asarray(v[0]) for v in controls))
    checked = set()
    with np.errstate(all="ignore"):
        for v in events:
            key = (v.template, v.donor is not None)
            if key in checked:
                continue
            checked.add(key)
            i = order[v.slot]
            generation, template, donor = (np.zeros_like(base.generation) for _ in range(3))
            generation[i] = 1
            template[i] = 0 if v.template is None else rows[v.template]
            donor[i] = 0 if v.donor is None else order[v.donor] + 1
            control = base._replace(generation=generation, template=template, donor=donor)
            after, ok = apply_events(state, control, p, xp=np)
            if not ok or not model.control_domain_valid(after, control, p, p.active, xp=np):
                raise ConfigError(
                    f"Newcomer {v.carrier_id} ({v.newcomer}) is outside the domain at {v.slot}"
                )


def worst_case(spec, declaration, events):
    """The inner definition with each replaced slot's largest leak and pump routes.

    Each replaced slot takes the largest leak permeabilities and pump capacities over
    its founder and its templates (@3's explicit-rate and calcium bounds read them);
    channel stiffness is refused in-step by @3 at the actual openings.
    """
    base = composite_spec.projection(spec)
    m = base.model
    species = list(m.species_ids)
    names = {t.id: t for t in declaration.templates}
    by_slot = {}
    for v in events:
        if v.template is not None:  # Donor copies without one keep the slot's routes.
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


def frozen_spec(spec, declaration, events):
    """The resolved_pump_replacement@1 definition (the spec-level helpers' format)."""
    m, e = spec.model, spec.experiment
    model = replacement_spec.CellReplacementModel(
        **{k: getattr(m, k) for k in ionic_spec.SurfacePumpChannelModel.__dataclass_fields__},
        replacement=declaration,
    )
    experiment = replacement_spec.Experiment(
        **{k: getattr(e, k) for k in ionic_spec.Experiment.__dataclass_fields__},
        replacement_events=events,
    )
    return replace(spec, model=model, experiment=experiment)


# ------------------------------------------------------------------ the operator


class ScheduledReplacement(Operator):
    LAW_ID = LAW_ID
    STEP_ID = formation.LAW_ID
    EVENT = True
    SPLIT = True
    RK4 = "split"
    STATE_AXES = REPLACEMENT_STATE_AXES
    STATE_DTYPES = {k: np.int64 for k in INTEGER_FIELDS}
    LAYOUT_FIELDS = REPLACEMENT_LAYOUT_FIELDS
    CONTROL_FIELDS = ("generation", "template", "donor")
    EXPERIMENT_KEYS = ("replacement_events",)
    VIEW_FIELDS = (
        "channel_permeability",
        "channel_abundance",
        "membrane_permeability",
        "pump_capacity",
        "calcium_pump_capacity",
    )
    CONTROL_FACTORS = ("junction",)
    CONFLICTS_VIEW = ("volume", "extracellular_volume")
    ENTITY_WRITES = {
        "amount_increment": (
            "replacement_removed_fmol",
            "replacement_supplied_fmol",
            "replacement_charge_C",
        ),
        "electrode_charge_transferred_C": ("replacement_image_charge_C",),
        "electrode_work_pJ": ("replacement_free_energy_pJ", "replacement_energy_magnitude_pJ"),
    }
    STATE_RESETS = ("channel_gate", "junction_gate")
    READOUT_COLUMNS = REPLACEMENT_READOUTS

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        _fields(raw, {"law", "junction_formation", "templates", "template_capacity"}, "replacement")
        if raw["law"] != LAW_ID:
            raise ConfigError("Replacement requires law " + LAW_ID)
        if type(raw["templates"]) is not list:
            raise ConfigError("Replacement templates require an explicit list")
        templates = tuple(replacement_spec.parse_template(t, base) for t in raw["templates"])
        if len({t.id for t in templates}) != len(templates):
            raise ConfigError("Template IDs must be unique")
        capacity = _integer(
            raw["template_capacity"], "template_capacity", minimum=max(1, len(templates))
        )
        return replacement_spec.Replacement(
            LAW_ID,
            inner_model,
            replacement_spec.parse_formation(raw["junction_formation"]),
            templates,
            capacity,
        )

    def to_dict(self, declaration, base):
        r = declaration
        if (
            type(r) is not replacement_spec.Replacement
            or type(r.junction_formation) is not replacement_spec.JunctionFormation
            or any(type(t) is not replacement_spec.Template for t in r.templates)
        ):
            raise ConfigError("Require explicit immutable replacement declaration types")
        f = r.junction_formation
        return dict(
            law=r.law,
            junction_formation=dict(
                law=f.law,
                initial_abundance=f.initial_abundance,
                lag_s=f.lag_s,
                time_constant_s=f.time_constant_s,
                gate_at_arrival=f.gate_at_arrival,
            ),
            templates=[
                replacement_spec.template_to_dict(t, base.model.species_ids) for t in r.templates
            ],
            template_capacity=r.template_capacity,
        )

    def parse_schedule(self, raw, base, declaration):
        return replacement_spec.parse_events(raw["replacement_events"], base, declaration.templates)

    def schedule_to_dict(self, schedule, base, declaration):
        if any(type(v) is not replacement_spec.ReplacementEvent for v in schedule):
            raise ConfigError("Require explicit immutable replacement event types")
        return dict(
            replacement_events=[
                dict(
                    time=v.time,
                    slot=v.slot,
                    newcomer=v.newcomer,
                    template=v.template,
                    donor=v.donor,
                    carrier_id=v.carrier_id,
                )
                for v in schedule
            ]
        )

    def schedule_times(self, schedule):
        return tuple(v.time for v in schedule)

    def value_at(self, schedule, time):
        return tuple(v for v in schedule if v.time == time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        controls = replacement_spec.control_values(frozen_spec(spec, declaration, schedule), times)
        return controls.generation, controls.template, controls.donor

    def check_definition(self, spec, declaration, schedule, model):
        check_definition(spec, declaration, schedule, model)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        """@3's step checks on the worst-case inner definition, every occupant included."""
        return worst_case(spec, declaration, schedule)

    def batch_signature(self, declaration):
        f = declaration.junction_formation
        return (declaration.law, f.law, f.gate_at_arrival, declaration.template_capacity)

    def working_size(self, spec):
        x, s = spec.execution, len(spec.model.species_ids)
        return 2 * ((2 * s + 5) * x.capacity + 2 * x.edge_capacity)

    def summary(self, spec, declaration, schedule, history):
        f = declaration.junction_formation
        generation = None
        if hasattr(history, "generation") and len(np.asarray(history.generation)):
            generation = np.asarray(history.generation)[-1]
        return {
            "replacement_law": LAW_ID,
            "junction_formation": dict(
                law=f.law,
                initial_abundance=f.initial_abundance,
                lag_s=f.lag_s,
                time_constant_s=f.time_constant_s,
                gate_at_arrival=f.gate_at_arrival,
            ),
            "replacement_events_declared": len(schedule),
            "lineage": replacement_spec.lineage(
                frozen_spec(spec, declaration, schedule), generation
            ),
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration, schedule)

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        occupant = ionic_layout(p, state, xp=xp)
        return {k: getattr(occupant, k) for k in self.VIEW_FIELDS}

    def control_factors(self, state, p, *, xp):
        return dict(junction=abundance(state))

    def event(self, state, control, p, *, xp):
        return apply_events(state, control, p, xp=xp)

    def half_step(self, state, h, control, p, *, xp):
        lag, deficit = formation.advance(
            state.junction_lag_remaining_s,
            state.junction_abundance_deficit,
            h,
            formation_parameters(p),
            xp=xp,
        )
        return state._replace(
            junction_lag_remaining_s=lag, junction_abundance_deficit=deficit
        ), None

    def rates(self, state, control, p, view, *, xp):
        lag, deficit = formation_rates(state, p, xp=xp)
        rates = {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}
        rates.update(junction_lag_remaining_s=lag, junction_abundance_deficit=deficit)
        return rates, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & replacement_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = replacement_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        return _terms(result, row, xp=xp), {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """Removed + supplied amounts in the material ledgers, their charge in the global
        charge, and as running allowances (None for @3, whose bounds are fixed) the
        booked image charge plus the replaced cells' charge magnitude at their held
        nodes, and the booked energy terms. Every term is zero for founders, so without
        events every bound is @3's exactly (bound + 0)."""
        moved = row.replacement_removed_fmol + row.replacement_supplied_fmol
        magnitudes[0] = magnitudes[0] + moved
        magnitudes[2] = magnitudes[2] + xp.sum(moved, axis=1)
        charge = CHARGE_PER_FMOL * xp.sum(xp.abs(p.valence) * moved)
        magnitudes[5] = charge if magnitudes[5] is None else magnitudes[5] + charge
        held = xp.where(p.reservoir, replaced_charge_magnitude(row, p, xp=xp), 0.0)
        image = row.replacement_image_charge_C + held
        magnitudes[4] = image if magnitudes[4] is None else magnitudes[4] + image
        energy = xp.sum(row.replacement_energy_magnitude_pJ)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        columns["junction_abundance"] = np.asarray(abundance(state))
        return columns
