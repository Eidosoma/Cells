"""resolved_pump_tissue@3: resolved_pump_tissue@2 with voltage-gated channel populations.

A channel population (definitions/surface_pump_v3_spec.py) is one more membrane process
at its patch: the constant-field flux of its law's ion with permeability
P * abundance * opening(gates) * availability, the shared-gate population
equations of resolved_tissue@5 and later (surface_kinetic.readouts). It moves
material from the cell to the patch's outside node, charging both capacitor
components, and has its own per-species transfer and dissipation ledgers. The
field law, factored solver, junction gate, both pumps and every @2 check are
those of models/surface_pump_v2.py; each rate below is @2's sequence of
operations with the channel terms appended, so with no channels this identity
reproduces resolved_pump_tissue@2. Accepted rows are checked on the host
(check_values) or, in vectorized worlds and projective bursts, on the device
(device_checks): the same tests with the same bounds.

Time integration. RK4 (reference runs) integrates the gate equations with every
other rate. The IMEX steps keep the split of @1 and @2: face electromigration
implicit, every other rate explicit at stage potentials, now including the
channel currents at stage gates. Gates are not advanced by the tableau: at each
stage they are the exponential update (numerics/exponential_gates.py) from the
step start to the stage time, from the start and stage membrane voltages. A
stage's voltage depends only on earlier stages' currents, so no iteration is
needed. Gates stay in [0, 1] at any step, and ARS(2,2,2) remains second order
(Euler first order); stiff NaV m gates relax to their quasi-steady values
instead of making the step unstable. The channel currents themselves stay
explicit, so their stiffness depends on how far the channels are open: an
IMEX step refuses itself (no repair) when dt times the membrane relaxation
rate at its actual openings (membrane_rate) exceeds the family's explicit
bound at any explicit stage. The step size the openings admit is therefore a
property of the run, not of the definition: window currents admit
millisecond steps, a fully open NaV1.2 population of 2.5e-7 m/s needs about
0.37 ms.

Extra membrane processes (opt-in hook for composing models; none by default).
readouts, explicit_rates and imex_step take an optional membrane_process,
called as membrane_process(ci, co, volume, voltage, xp=xp) with the patch's cell
and outside concentrations [species, membrane] (mM), its cell's volume
[membrane] (pL, the layout's) and its membrane voltage [membrane] (V). It
returns a MembraneProcess: outward flux [species, membrane] (fmol/s), heat
[membrane] (pJ/s) and a validity flag. The flux is added to the explicit
membrane terms at every explicit stage (and to readouts, so rhs and the field's
charge rates see it); its heat enters readouts' dissipation. imex_step then also
returns the step's applied transfer (the tableau's explicit weights, the exact
amount change) and its heat, booked as dt (q_start + q_end) / 2 from the start
state and the end state at its last-stage potentials, so a process whose heat
is nonnegative never books a negative increment. The composing model owns those
ledgers. The explicit-stage refusal (membrane_rate) does not include the
process: it must add no membrane conductance the family's bound does not cover
(an electroneutral process adds none). With no process the code is unchanged.
"""

import re
import sys
from dataclasses import make_dataclass, replace
from functools import cache, cached_property, partial
from types import MappingProxyType, SimpleNamespace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError
from cells.definitions.surface_pump_v3_spec import (
    GATED_CODES,
    LAW_CODES,
    MODEL_ID,
    NAV1P2_LAW_ID,
    TRAPEZOID_JUNCTION_HEAT,
    Control,
    projection,
)
from cells.execution.errors import NumericalError
from cells.laws.channels import sodium_channels, voltage_gates
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.laws.junctions import junction_gate
from cells.laws.junctions.selective import selective_flux
from cells.laws.pumps import calcium_atpase
from cells.laws.pumps import kinetic_pump as pump
from cells.laws.pumps import kinetic_pump_binding as pumps
from cells.models import inner_laws
from cells.models import surface_kinetic as kinetic
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models import surface_tissue as tissue
from cells.numerics import exponential_gates as gates
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from cells.numerics import surface_transport as surface
from cells.numerics.extracellular_field import scatter
from cells.numerics.fixed_step import rk4_checked_step
from cells.numerics.species_sums import entity_sum, species_sum
from cells.registry import kind_registry

OBSERVER_ID = kinetic.OBSERVER_ID
OBSERVATION_SAMPLING = kinetic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = kinetic.STAGE_DOMAIN_ID
BATCH_CAPACITIES = (*tissue.BATCH_CAPACITIES, "channel_capacity")
STATE_AXES = second.STATE_AXES | {
    "channel_transferred": ["species", "channel_slot"],
    "channel_dissipated_energy_pJ": ["species", "channel_slot"],
}
STATE_TYPE = NamedTuple("SurfacePumpChannelState", [(k, object) for k in STATE_AXES])
# junction_heat_trapezoid: one element with the trapezoid_nonnegative@1 junction-heat
# booking, none by default, so the step's branch is static (shape, not value). Every
# @3 layout carries it (empty by default); the state layout (STATE_TYPE) is unchanged,
# and @3 checkpoints from source before this field do not load (snapshots already
# refuse a source change).
CHANNEL_LAYOUT_FIELDS = (
    "channel_laws",
    "channel_relative_permeability",
    "channel_gate_active",
    "junction_heat_trapezoid",
)
LAYOUT_TYPE = NamedTuple(
    "SurfacePumpChannelLayout",
    [
        (k, object)
        for k in (
            *(k for k in second.LAYOUT_TYPE._fields if k != "channel_species"),
            *CHANNEL_LAYOUT_FIELDS,
        )
    ],
)
FLOOR_LAYOUT_TYPE = NamedTuple(  # Declared field solver surface_field.FLOOR_SOLVER_ID.
    "SurfacePumpChannelFloorLayout",
    [
        (k, object)
        for k in (
            *(k for k in second.FLOOR_LAYOUT_TYPE._fields if k != "channel_species"),
            *CHANNEL_LAYOUT_FIELDS,
        )
    ],
)
ENERGY_RTOL = first.ENERGY_RTOL
EXPLICIT_STEP_BOUND = first.EXPLICIT_STEP_BOUND
# The ledger protocol (docs/INNER_MODEL_V4_DESIGN.md §7.4 (p)): @1's lists, which the shared
# check paths read from the model object (ledger_lists: per structure).
LEDGERS = first.LEDGERS
LEDGER_DIAGNOSTICS = first.LEDGER_DIAGNOSTICS
ledger_limits = first.ledger_limits
GATE_INTEGRATOR_ID = gates.LAW_ID
VOLTAGE_DOMAIN_V = voltage_gates.VOLTAGE_DOMAIN_V
# RK4 reference steps keep the resolved channel family's qualified bounds
# (surface_kinetic.check_steps): 2.5 us with NaV1.2, 25 us with Kv1.5/Kir2.1. The laws'
# declarations hold them (models/inner_laws.py).
RK4_SODIUM_STEP = inner_laws.RK4_SODIUM_STEP_S
RK4_POTASSIUM_STEP = inner_laws.RK4_POTASSIUM_STEP_S
# Inactive population slots carry code 0 (domain_valid; the composite adapter's close), the
# code of this law. Where it is not declared, the host observer still reads its kinetics at an
# inactive slot, today's padding values, as a declared fill (docs/INNER_MODEL_V4_DESIGN.md
# §7.4 (b); temporary, until an explicit absent marker for padded entries).
PADDING_FILL_LAW = next(law for law, code in LAW_CODES.items() if code == 0)

parameters = first.parameters
batch_signature = first.batch_signature
physical_amounts = first.physical_amounts
global_charge_bound = first.global_charge_bound
node_charge = first.node_charge
rebind = first.rebind


class MembraneProcess(NamedTuple):
    """An extra explicit membrane process's rates (see the module docstring)."""

    flux: object  # [species, membrane] outward fmol/s
    heat: object  # [membrane] pJ/s
    valid: object


class Values(NamedTuple):
    field: object
    derivative: object
    channel_flux_fmol_s: object
    channel_targets: object
    channel_tau_s: object
    pump_affinity_J_mol: object
    calcium_pump_affinity_J_mol: object
    valid: object


def working_size(spec):
    x, s = spec.execution, len(spec.model.species_ids)
    return second.working_size(projection(spec)) + 2 * (2 + 2 * s) * x.channel_capacity


def initial_values(spec, *, structure=None):
    state, layout = _todays_initial_values(spec)
    if structure is None or not structure.kinds:
        return state, layout
    # Schema A (§7.4 (j), (k)): each declared kind adds its state and layout fields, by name, in
    # canonical order, into its structure's types.
    types = kind_types(structure)
    registry = kind_registry.active()
    declarations = dict(spec.model.kinds)
    fields, entries = state._asdict(), layout._asdict()
    for kind_id, entry in structure.kinds:  # Each bound to its entry's fields (§7.4 (n) 5).
        kind = kind_registry.bound(registry.lookup(kind_id), entry)
        own_state, own_layout = kind.initial(spec, declarations[kind_id], entries)
        kind_registry.refuse_foreign_writes(
            kind, "initial values", own_state, kind.state_fields, "state"
        )
        kind_registry.refuse_foreign_writes(
            kind, "initial values", own_layout, kind.layout_fields, "layout"
        )
        fields |= own_state
        entries |= own_layout
    floor = "field_current_floor" in entries
    return types.STATE_TYPE(**fields), (types.FLOOR_LAYOUT_TYPE if floor else types.LAYOUT_TYPE)(
        **entries
    )


def _todays_initial_values(spec):
    state, layout = second.initial_values(projection(spec))
    m, nc, s = spec.model, spec.execution.channel_capacity, len(spec.model.species_ids)
    v = layout._asdict()
    del v["channel_species"]
    v.update(
        channel_active=np.arange(nc) < len(m.channels),
        channel_membranes=np.zeros(nc, dtype=np.int64),
        channel_permeability=np.zeros(nc),
        channel_abundance=np.zeros(nc),
        channel_laws=np.zeros(nc, dtype=np.int64),
        channel_relative_permeability=np.zeros((s, nc)),
        channel_gate_active=np.zeros((2, nc), dtype=bool),
        junction_heat_trapezoid=np.zeros(int(m.junction_heat_booking == TRAPEZOID_JUNCTION_HEAT)),
    )
    gate, mids = np.zeros((2, nc)), [p.id for p in m.membranes]
    for i, c in enumerate(m.channels):
        v["channel_membranes"][i] = mids.index(c.membrane_id)
        v["channel_permeability"][i] = c.max_permeability_m_per_s
        v["channel_abundance"][i] = c.abundance
        v["channel_laws"][i] = LAW_CODES[c.kinetic_law]
        for ion in c.permeant_ions:
            row = m.species_ids.index(ion.species_id)
            v["channel_relative_permeability"][row, i] = ion.relative_permeability
        v["channel_gate_active"][: len(c.initial_gate), i] = True
        gate[: len(c.initial_gate), i] = c.initial_gate
    channel = dict(
        channel_gate=gate,
        channel_transferred=np.zeros((s, nc)),
        channel_dissipated_energy_pJ=np.zeros((s, nc)),
    )
    kind = FLOOR_LAYOUT_TYPE if "field_current_floor" in v else LAYOUT_TYPE
    return STATE_TYPE(**(state._asdict() | channel)), kind(**v)


def channel_kinetics(voltage, codes, *, xp=jnp, structure=None):
    """Targets and time constants [..., rows, channel] in s; gate-free leaks get 0 and 1.

    structure None: today's dispatch over the full catalogue. With a structure (§7.4 (c)), only
    the declared gated laws' kernels are traced, each selected where a slot carries its code, in
    code order (probe P2's form). A code-0 slot of a world that does not declare the code-0 law is
    padding: compiled programs give it 0 and 1, which nothing compiled reads, while the host, where
    the observer runs, gives it the code-0 law's values as today, a declared fill (§7.4 (b)).
    """
    if structure is None:
        gated = codes < GATED_CODES
        target, tau = sodium_channels.kinetics(voltage, xp.where(gated, codes, 0), xp=xp)
        rows = xp.expand_dims(gated, -2)
        return xp.where(rows, target, 0.0), xp.where(rows, tau, 1.0)
    rows = structure.gate_rows
    shape = (*voltage.shape[:-1], rows, voltage.shape[-1])
    target, tau = xp.zeros(shape, dtype=voltage.dtype), xp.ones(shape, dtype=voltage.dtype)
    laws = [law for law in structure.channel_laws if law.gated]
    fill = xp is np or structure.padding_fill  # The host's fill; compiled where slots close.
    if fill and PADDING_FILL_LAW not in structure.declared_channel_laws:
        laws.insert(0, inner_laws.CHANNEL_LAWS[PADDING_FILL_LAW])
    for law in laws:
        if len(law.gates) != rows:  # Not in R: every gated law has today's two gates.
            raise NotImplementedError("Channel laws with fewer gates than the structure's rows")
        law_target, law_tau = law.kinetics(voltage, xp=xp)
        mask = xp.expand_dims(codes == law.code, -2)
        target = xp.where(mask, law_target, target)
        tau = xp.where(mask, law_tau, tau)
    return target, tau


def channel_opening(gate, codes, *, xp=jnp, structure=None):
    """Open fractions [..., channel]: today's catalogue, or the declared gated laws (§7.4 (c))."""
    if structure is None:
        gated = codes < GATED_CODES
        return xp.where(gated, sodium_channels.opening(gate, xp.where(gated, codes, 0), xp=xp), 1.0)
    opening = xp.ones_like(gate[..., 0, :])
    for law in structure.channel_laws:
        if law.gated:
            opening = xp.where(codes == law.code, law.opening(gate, xp=xp), opening)
    return opening


def channel_voltage(membrane_voltage, p, *, xp=jnp):
    return xp.where(p.channel_active, membrane_voltage[p.channel_membranes], 0.0)


def channel_domain_valid(voltage, target, tau, p, *, xp=jnp):
    """Active populations stay on their laws' -120..60 mV domain with finite kinetics."""
    inside = (voltage >= VOLTAGE_DOMAIN_V[0]) & (voltage <= VOLTAGE_DOMAIN_V[1])
    kinetics = xp.isfinite(target) & (target >= 0) & (target <= 1) & xp.isfinite(tau) & (tau > 0)
    return xp.all(xp.where(p.channel_active, inside & xp.all(kinetics, axis=-2), True))


def channel_rates(
    gate, ci, co, membrane_voltage, delta_mu, availability, p, *, xp=jnp, structure=None
):
    """Outward flux and heat [species, channel], kinetics and voltage of each population."""
    patch = p.channel_membranes
    voltage = channel_voltage(membrane_voltage, p, xp=xp)
    target, tau = channel_kinetics(voltage, p.channel_laws, xp=xp, structure=structure)
    flux = selective_flux(
        ci[:, p.membrane_cell[patch]],
        co[:, p.membrane_outside[patch]],
        voltage,
        p.valence,
        p.temperature,
        p.membrane_area[patch],
        p.channel_permeability * p.channel_relative_permeability,
        0.0,
        p.channel_abundance,
        channel_opening(gate, p.channel_laws, xp=xp, structure=structure) * availability,
        xp=xp,
    )
    flux = xp.where(p.channel_active, flux, 0.0)
    return flux, 1e-3 * flux * delta_mu[:, patch], target, tau, voltage


def channel_to_membrane(value, p, *, xp=jnp):
    """Sum [species, channel] values into their patches [species, membrane]."""
    return scatter(value, xp.zeros_like(p.membrane_permeability), (p.channel_membranes,), xp=xp)


def channel_heat(heat, p, *, xp=jnp):
    return scatter(
        species_sum(heat, xp=xp), xp.zeros_like(p.membrane_area), (p.channel_membranes,), xp=xp
    )


def nak_pump_rates(ci, co, delta_mu, control, p, *, xp=jnp, structure=None):
    """(Rates, domain arguments) of the Na/K pump law at its patches' inputs [species, membrane].

    Undeclared (§7.4 (c)): its kernel is not traced; its rates are exact zeros, which today's
    masked expressions turn into the same bits as a pump-free membrane's padding (whose drive and
    cycle energy are exactly +0.0), and its arguments are None (no domain to check).
    """
    if structure is not None and pump.LAW_ID not in structure.pump_laws:
        zero = xp.zeros_like(p.pump_capacity)
        return pump.Rates(zero, zero, zero), None
    args = (
        *pumps.role_inputs(ci, co, delta_mu, p.temperature, p, xp=xp),
        pumps.pump_parameters(p),
        control.pump,
    )
    return pump.kinetics(*args, xp=xp), args


def calcium_pump_rates(ci, co, voltage, control, p, *, xp=jnp, structure=None):
    """surface_pump_v2.calcium_rates where the calcium pump law is declared; else its exact zeros.

    (cycles, dissipation, metabolic power, affinity, domain arguments or None), with the zeros
    through calcium_rates' own expressions, so a pump-free membrane keeps today's bits.
    """
    if structure is not None and calcium_atpase.LAW_ID not in structure.pump_laws:
        zero = xp.zeros_like(p.calcium_pump_capacity)
        cycles = xp.where(p.calcium_pump_present, zero, 0.0)
        affinity = xp.where(p.calcium_pump_present, zero, 0.0)
        return cycles, -1e-3 * cycles * zero, -1e-3 * cycles * zero, affinity, None
    return second.calcium_rates(ci, co, voltage, control, p, xp=xp)


def junction_gate_rhs(gate, junction_voltage, p, *, xp=jnp, structure=None):
    """The junction law's gate derivative; exact zeros, with no kernel, where none is declared.

    Callers keep today's mask on active junctions, so the catalogue path's program is today's.
    """
    if structure is not None and not structure.junction_laws:
        return xp.zeros_like(gate)
    return junction_gate.rhs(gate, junction_voltage, kinetic.junction_parameters(p), xp=xp)


KindRates = kind_registry.KindRates  # The kind contract's (§8.5 of docs/CORE_SEAMS_DESIGN.md).


def _kinds(structure):
    """The declared kinds' declarations, in hook order, each bound to its structure entry's
    fields (§7.4 (n) 5); none for today's structures."""
    if structure is None or not structure.kinds:
        return ()
    registry, entries = kind_registry.active(), dict(structure.kinds)
    return tuple(
        kind_registry.bound(registry.lookup(kind_id), entries[kind_id])
        for kind_id in hook_order(structure)
    )


def _route(structure, kinds, read, control, p, *, xp):
    """§7.4 (n), the routing door, at one stage: (the control with each routed slot set to its
    held value x its sources' factors, a left fold in declared order; valid: every factor finite
    and in [0, 1]). The factors are the sources' at the stage's read state. Static: without
    routes the control is returned as it is, and no factor is evaluated."""
    if structure is None or not structure.routes:
        return control, True
    by_id = {kind_registry.qualified(kind.kind_id): kind for kind in kinds}
    sources = sorted({kind_id for *_, named in structure.routes for kind_id, _ in named})
    values, valid = {}, True
    for kind_id in sources:
        factors = by_id[kind_id].factors(read, p, xp=xp)
        valid = valid & xp.all(xp.isfinite(factors) & (factors >= 0) & (factors <= 1))
        values[kind_id] = factors
    fields = {}
    for _, name, slot, named in structure.routes:
        held = fields.get(name, getattr(control, name))
        value = held[slot]
        for kind_id, position in named:  # The left fold, in declared order.
            value = value * values[kind_id][position]
        if xp is np:
            held = np.array(held, dtype=np.float64, copy=True)
            held[slot] = value
        else:
            held = held.at[slot].set(value)
        fields[name] = held
    return control._replace(**fields), valid


def _routes(model):
    """§7.4 (n): the routing door's table for a parsed model block, resolved at binding: ((sink
    kind ID, control field, slot, ((source kind ID, position), ...)), ...) in canonical kind
    order; () without a sink. Refused: an unknown source ID, one that two kinds expose, a field
    that is not the sink's own control field, and a slot routed twice."""
    registry, declared = kind_registry.active(), getattr(model, "kinds", ())
    sources = {}
    for kind_id, declaration in declared:
        kind = registry.lookup(kind_id)
        if kind.factor_sources is None:
            continue
        for position, source in enumerate(kind.factor_sources(declaration)):
            if source in sources:
                raise ConfigError(
                    f"Factor source {source!r} is exposed by {sources[source][0]} and {kind_id}"
                )
            sources[source] = (kind_id, position)
    routes, taken = [], set()
    for kind_id, declaration in declared:
        kind = registry.lookup(kind_id)
        if kind.routed_controls is None:
            continue
        entry = kind.structure_entry(declaration) if kind.structure_entry else ()
        own = kind_registry.bound(kind, entry).control_fields
        for name, slot, named in kind.routed_controls(declaration):
            where = f"Kind {kind_id}'s routed control {name}[{slot}]"
            if name not in own:
                raise ConfigError(f"{where}: a sink routes its own control fields only")
            if (name, slot) in taken:
                raise ConfigError(f"{where} is routed twice")
            taken.add((name, slot))
            unknown = [source for source in named if source not in sources]
            if unknown:
                raise ConfigError(f"{where} names unknown factor sources {unknown}")
            routes.append((kind_id, name, slot, tuple(sources[source] for source in named)))
    return tuple(routes)


def _stage_read(state, p, kinds, *, xp):
    """The kinds' stage reads, composed in hook order: (the state whose amounts the rates read,
    valid). A failed read refuses the step (§7.4 (g) 1)."""
    valid = True
    for kind in kinds:
        if kind.stage_read is not None:
            state, ok = kind.stage_read(state, p, xp=xp)
            valid = valid & ok
    return state, valid


def _field_values(state, read, control, p, *, xp):
    """tissue.field_values with the stage read's concentrations and the stored rows' charges: a
    read changes the concentrations the rates see, never a node's charge (§7.4 (k); FR-4's H_eq
    and buffer totals carry the charge). Today's call, unchanged, when nothing is read."""
    if read is state:
        return tissue.field_values(state, control, p, xp=xp)
    ci, co = physical_amounts(read, p)
    q = tissue.charge_increment(state, p, xp=xp)
    n = p.active.size
    return field.solve(
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
        p.initial_cell_charge_C + q[:n],
        p.initial_outside_charge_C + q[n:],
        control.membrane,
        control.junction,
        p.boundary_V,
        tissue.field_layout(p),
        xp=xp,
    )


def _stage_checks(kinds, read, cell, outside, p, *, xp):
    """The kinds' stage checks at the stage's total node rates (§7.4 (k)); true without any."""
    valid = True
    for kind in kinds:
        if kind.stage_check is not None:
            valid = valid & kind.stage_check(read, cell, outside, p, xp=xp)
    return valid


def _kind_rates(kinds, state, potentials, control, p, *, xp):
    """Each kind's rates at the stage, in hook order. A kind's derivatives name only its own
    state fields (kinds bound to their entries; the keys are checked while tracing)."""
    rates = []
    for kind in kinds:
        if kind.rates:
            kr = kind.rates(state, potentials, control, p, xp=xp)
            kind_registry.refuse_foreign_writes(
                kind, "rates", kr.derivatives, kind.state_fields, "state"
            )
            rates.append(kr)
    return rates


def _with_kind_derivatives(base, rates, structure, state, *, xp):
    """base's derivative in the structure's state type, the kinds' fields by name."""
    types = kind_types(structure)
    derivatives = {}
    for kr in rates:
        derivatives |= kr.derivatives
    own = types.STATE_TYPE._fields[len(STATE_TYPE._fields) :]
    return types.STATE_TYPE(
        **base._asdict(),
        **{
            f: derivatives[f] if f in derivatives else xp.zeros_like(getattr(state, f)) for f in own
        },
    )


def _kind_bookings(kinds, applied, start, end, control, p, dt, *, xp):
    """Every kind's book hook on the same end state (before any kind books), each writing only its
    own state fields, so bookings commute and their order cannot matter (§7.4 (k)). Each receives
    the step's held control (§7.4 (l) 5: constant over the step), so a kind can book an exact
    per-step update at the step's values. Returns ({field: value}, valid): a booking may refuse
    the step (§7.5's negative exact share)."""
    booked, valid = {}, True
    for kind in kinds:
        if kind.book is None:
            continue
        values, ok = kind.book(applied, start, end, control, p, dt, xp=xp)
        foreign = set(values) - set(kind.state_fields)
        if foreign:
            raise ValueError(
                f"Kind {kind.kind_id}'s book writes {sorted(foreign)}; a booking writes only "
                "its own state fields"
            )
        booked |= values
        valid = valid & ok
    return booked, valid


def _stage_extrema(kinds, start, states, rates, p, *, xp):
    """Gap 7: each kind's stage_values at every explicit stage (its read state and the stage's
    total node rates, as stage_check sees them), reduced over the stages as its stage_extrema
    say, from the step start's value: {own state field: running extremum}."""
    out = {}
    for kind in kinds:
        if kind.stage_values is None:
            continue
        how = dict(kind.stage_extrema)
        per_stage = [
            kind.stage_values(
                _stage_read(state, p, kinds, xp=xp)[0],
                stage_rates.amount_increment,
                stage_rates.extracellular_amount_increment,
                p,
                xp=xp,
            )
            for state, stage_rates in zip(states, rates, strict=True)
        ]
        for name in per_stage[0]:
            if name not in kind.state_fields or how.get(name) not in ("max", "min"):
                raise ValueError(
                    f"Kind {kind.kind_id}'s stage value {name} is not one of its state fields "
                    "with a declared extremum (max or min)"
                )
            reduce = xp.maximum if how[name] == "max" else xp.minimum
            value = getattr(start, name)
            for values in per_stage:
                value = reduce(value, values[name])
            out[name] = value
    return out


def _availabilities(control, kinds):
    """Rule (d): today's control fields and the kinds' availability controls (those of kinds
    without a control_domain hook), each held to [0, 1]."""
    names = list(Control._fields)
    for kind in kinds:
        if kind.control_domain is None:
            names.extend(kind.control_fields)
    return [getattr(control, name) for name in names]


def readouts(state, control, p, *, xp=jnp, membrane_process=None, structure=None):
    """surface_pump_v2.readouts with the channel populations' currents and gate rates.

    membrane_process: the opt-in extra membrane process (module docstring). structure: the
    declared structure (§7.4), or None for today's dispatch over the full catalogue.
    """
    from cells.execution.schedule import SurfaceControl

    kinds = _kinds(structure)
    read, read_valid = _stage_read(state, p, kinds, xp=xp) if kinds else (state, True)
    if kinds and structure.routes:  # §7.4 (n): the routing door, after the read (static).
        control, routed = _route(structure, kinds, read, control, p, xp=xp)
        read_valid = read_valid & routed
    v = _field_values(  # §7.4 (k): the rates read `read`; the field solve the stored charges.
        state,
        read,
        SurfaceControl(control.membrane, control.junction * state.junction_gate),
        p,
        xp=xp,
    )
    r, n = v.rates, p.active.size
    ci, co = physical_amounts(read, p)
    ci, co = (
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
    )
    channel, channel_d, target, tau, cv = channel_rates(
        state.channel_gate,
        ci,
        co,
        r.membrane_voltage_V,
        r.membrane_delta_mu_J_mol,
        control.channel,
        p,
        xp=xp,
        structure=structure,
    )
    gate_rate = xp.where(p.channel_gate_active, (target - state.channel_gate) / tau, 0.0)
    pr, args = nak_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_delta_mu_J_mol,
        control,
        p,
        xp=xp,
        structure=structure,
    )
    cycles = xp.where(p.pump_present, pr.cycles_fmol_s, 0.0)
    pump_d = -1e-3 * cycles * pr.cycle_free_energy_J_mol
    metabolic = -1e-3 * cycles * pr.chemical_drive_J_mol
    ca_cycles, ca_d, ca_metabolic, ca_affinity, ca_args = calcium_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_voltage_V,
        control,
        p,
        xp=xp,
        structure=structure,
    )
    jgate_rate = xp.where(
        p.junction_active,
        junction_gate_rhs(state.junction_gate, r.junction_voltage_V, p, xp=xp, structure=structure),
        0.0,
    )
    # Inward-positive pump stoichiometries, outward-positive channel flux.
    extra = (
        -p.stoichiometry * cycles
        - p.calcium_stoichiometry * ca_cycles
        + channel_to_membrane(channel, p, xp=xp)
    )
    process = None
    if membrane_process is not None:  # Opt-in (static); none by default.
        process = membrane_process(
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            p.volume[p.membrane_cell],
            r.membrane_voltage_V,
            xp=xp,
        )
        extra = extra + process.flux
    cell = r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp)
    out_extra = scatter(extra, r.outside_rate_fmol_s, (p.membrane_outside,), xp=xp)
    outside = r.outside_rate_fmol_s + xp.where(p.reservoir, 0.0, out_extra)
    supplied = r.reservoir_supply_fmol_s - xp.where(p.reservoir, out_extra, 0.0)
    kind_rates = _kind_rates(kinds, read, v.potential_V, control, p, xp=xp)
    for kr in kind_rates:  # §7.4 (k), rates: into the shared inventory (rule (c)).
        cell = cell + kr.cell
        outside = outside + xp.where(p.reservoir, 0.0, kr.outside)
        supplied = supplied - xp.where(p.reservoir, kr.outside, 0.0)
    total_flux = r.membrane_flux_fmol_s + extra
    for kr in kind_rates:  # Gap 9: a kind's patch flux joins the patches' total and current.
        if kr.membrane_flux is not None:
            total_flux = total_flux + kr.membrane_flux
    total_membrane_d = (
        r.membrane_dissipation_pJ_s + pump_d + ca_d + channel_heat(channel_d, p, xp=xp)
    )
    if process is not None:
        total_membrane_d = total_membrane_d + process.heat
    total_rates = r._replace(
        cell_rate_fmol_s=cell,
        outside_rate_fmol_s=outside,
        reservoir_supply_fmol_s=supplied,
        membrane_flux_fmol_s=total_flux,
        membrane_current_A=CHARGE_PER_FMOL * species_sum(p.valence * total_flux, xp=xp),
        membrane_dissipation_pJ_s=total_membrane_d,
    )
    qdot = CHARGE_PER_FMOL * species_sum(p.valence * xp.concatenate((cell, outside), axis=1), xp=xp)
    dphi = field._capacitor_solve(qdot, xp.zeros_like(qdot), tissue.field_layout(p), xp=xp)
    dvm = xp.where(p.membrane_active, dphi[p.membrane_cell] - dphi[n + p.membrane_outside], 0.0)
    electrode = xp.where(p.reservoir, (p.field_capacitor_matrix @ dphi)[n:], 0.0)
    chemical = (
        1e-3
        * R
        * p.temperature
        * (
            entity_sum(species_sum(xp.log(ci) * cell, xp=xp), axis=None, xp=xp)
            + entity_sum(species_sum(xp.log(co) * outside, xp=xp), axis=None, xp=xp)
        )
    )
    capacitor = 1e12 * entity_sum(
        p.membrane_capacitance * r.membrane_voltage_V * dvm, axis=None, xp=xp
    )
    mu = R * p.temperature * xp.log(co) + p.valence * F * v.potential_V[n:]
    reservoir_work = 1e-3 * species_sum(mu * supplied, xp=xp)
    electrode_work = 1e12 * p.boundary_V * electrode
    dissipation = (
        entity_sum(total_membrane_d, axis=None, xp=xp)
        + entity_sum(r.junction_dissipation_pJ_s, axis=None, xp=xp)
        + entity_sum(r.face_dissipation_pJ_s, axis=None, xp=xp)
    )
    for kr in kind_rates:  # The kinds' heat and work, by role (rule (a)).
        dissipation = dissipation + entity_sum(kr.heat_pJ_s, axis=None, xp=xp)
    energy = (
        chemical
        + capacitor
        + dissipation
        - entity_sum(reservoir_work + electrode_work, axis=None, xp=xp)
        - entity_sum(metabolic, axis=None, xp=xp)
        - entity_sum(ca_metabolic, axis=None, xp=xp)
    )
    for kr in kind_rates:
        energy = energy - entity_sum(kr.work_pJ_s, axis=None, xp=xp)
    for kr in kind_rates:  # §7.4 (m), gap 2: a kind's stored free energy, by role (static).
        if kr.stored_pJ_s is not None:
            energy = energy + entity_sum(kr.stored_pJ_s, axis=None, xp=xp)
    result = STATE_TYPE(
        cell,
        outside,
        r.membrane_flux_fmol_s,
        r.junction_flux_fmol_s,
        r.face_flux_fmol_s,
        supplied,
        r.membrane_dissipation_pJ_s,
        r.junction_dissipation_pJ_s,
        r.face_dissipation_pJ_s,
        electrode,
        reservoir_work,
        electrode_work,
        gate_rate,
        channel,
        channel_d,
        jgate_rate,
        cycles,
        pump_d,
        metabolic,
        ca_cycles,
        ca_d,
        ca_metabolic,
    )
    if kinds:
        result = _with_kind_derivatives(result, kind_rates, structure, state, xp=xp)
    valid = v.converged
    if args is not None:  # The Na/K pump's domain, where its law is declared.
        valid = valid & xp.all(pump.domain_valid(*args, xp=xp))
    if ca_args is not None:
        valid &= xp.all(calcium_atpase.domain_valid(*ca_args, xp=xp))
    valid &= channel_domain_valid(cv, target, tau, p, xp=xp)
    if process is not None:
        valid &= process.valid
    if kinds:  # A failed stage read, a kind's domain or a stage check refuses the row.
        valid &= read_valid & _stage_checks(kinds, read, cell, outside, p, xp=xp)
        for kr in kind_rates:
            valid &= kr.valid
    for value in _availabilities(control, kinds) if kinds else control:
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
    for kind in kinds:
        if kind.control_domain is not None:
            valid &= kind.control_domain(control, p, xp=xp)
    if structure is None or structure.junction_laws:
        valid &= xp.all(
            junction_gate.domain_valid(
                state.junction_gate,
                r.junction_voltage_V,
                kinetic.junction_parameters(p),
                control.junction,
                xp=xp,
            )
        )
    for value in result:
        valid &= xp.all(xp.isfinite(value))
    for value in (qdot, dphi, chemical, capacitor, dissipation, energy):
        valid &= xp.all(xp.isfinite(value))
    valid &= domain_valid(state, p, p.active, xp=xp, structure=structure)
    total_rates = total_rates._replace(valid=valid)
    v = v._replace(
        rates=total_rates,
        electrode_current_A=electrode,
        reservoir_supply_charge_A=CHARGE_PER_FMOL * species_sum(p.valence * supplied, xp=xp),
        membrane_voltage_rate_V_s=dvm,
        chemical_energy_rate_pJ_s=chemical,
        capacitor_energy_rate_pJ_s=capacitor,
        reservoir_power_pJ_s=entity_sum(reservoir_work, axis=None, xp=xp),
        electrode_power_pJ_s=entity_sum(electrode_work, axis=None, xp=xp),
        dissipation_pJ_s=dissipation,
        energy_balance_pJ_s=energy,
        converged=valid,
    )
    return Values(
        v,
        result,
        channel,
        target,
        tau,
        xp.where(p.pump_present, pr.cycle_free_energy_J_mol, 0.0),
        ca_affinity,
        valid,
    )


def field_values(state, control, p, *, xp=jnp, structure=None):
    return readouts(state, control, p, xp=xp, structure=structure).field


def rhs(state, control, p, active, *, xp=jnp, structure=None):
    values = readouts(state, control, p, xp=xp, structure=structure)
    derivative = values.derivative  # The structure's own state type (schema A).
    return type(derivative)(*(xp.where(values.valid, v, xp.nan) for v in derivative))


def domain_valid(state, p, active, *, xp=jnp, structure=None):
    valid = tissue.domain_valid(kinetic.passive_state(state), p, active, xp=xp)
    laws = p.channel_laws
    if structure is None:  # Today's check against the whole registry.
        valid &= xp.all((laws >= 0) & (laws < len(LAW_CODES)))
    else:  # An active slot runs a declared law; no literal comes from the registry.
        declared = xp.zeros(laws.shape, dtype=bool)
        for law in structure.channel_laws:
            declared = declared | (laws == law.code)
        valid &= xp.all(xp.where(p.channel_active, declared, True))
    valid &= xp.all(xp.where(p.channel_active, True, laws == 0))
    masks = (
        p.channel_gate_active,
        p.channel_active,
        p.channel_active,
        p.junction_active,
        p.pump_present,
        p.pump_present,
        p.pump_present,
        p.calcium_pump_present,
        p.calcium_pump_present,
        p.calcium_pump_present,
    )
    todays = STATE_TYPE._fields[len(tissue.STATE_TYPE._fields) :]
    for name, mask in zip(todays, masks, strict=True):  # Today's fields; kinds' below.
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    valid &= xp.all((state.channel_gate >= 0) & (state.channel_gate <= 1))
    valid &= xp.all((state.junction_gate >= p.junction_minimum) & (state.junction_gate <= 1))
    # Absent species routes never carry hidden transfers or heat.
    route = p.channel_relative_permeability * p.channel_permeability * p.channel_abundance
    valid &= xp.all(xp.where(route > 0, True, state.channel_transferred == 0))
    valid &= xp.all(xp.where(route > 0, True, state.channel_dissipated_energy_pJ == 0))
    valid &= xp.all(xp.where(p.pump_capacity > 0, True, state.pump_cycles == 0))
    valid &= xp.all(xp.where(p.calcium_pump_capacity > 0, True, state.calcium_pump_cycles == 0))
    if structure is not None and structure.kinds:  # Each declared kind's own domain (§7.4 (k)).
        kinds = _kinds(structure)
        _, read_valid = _stage_read(state, p, kinds, xp=xp)  # The reads hold at this state too.
        valid &= read_valid
        for kind in kinds:
            if kind.domain is not None:
                valid &= kind.domain(state, p, xp=xp)
    return valid


def hook_order(structure):
    """The kinds' hook-evaluation order (§7.4 (k)): named apart from the field order
    (structure.kinds, canonical), and equal to it in version 1."""
    return tuple(kind_id for kind_id, _ in structure.kinds)


def control_domain_valid(state, control, p, active, *, xp=jnp, structure=None):
    valid = domain_valid(state, p, active, xp=xp, structure=structure)
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return readouts(state, control, p, xp=np, structure=structure).valid
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid,
        lambda: readouts(state, control, p, structure=structure).valid,
        lambda: jnp.asarray(False),
    )


domain_valid.with_control = control_domain_valid


def explicit_rates(state, potential, control, p, *, xp=jnp, membrane_process=None, structure=None):
    """surface_pump_v2.explicit_rates with the channel currents at the same potentials.

    The gate rate is zero here: IMEX steps set gates by the exponential update.
    With a membrane_process (opt-in) its flux joins the explicit membrane terms
    and the call returns (rates, valid, MembraneProcess); otherwise (rates, valid).
    """
    s, n = tissue.field_layout(p).surface, p.active.size
    kinds = _kinds(structure)
    read, read_valid = _stage_read(state, p, kinds, xp=xp) if kinds else (state, True)
    if kinds and structure.routes:  # §7.4 (n): the routing door, after the read (static).
        control, routed = _route(structure, kinds, read, control, p, xp=xp)
        read_valid = read_valid & routed
    ci, co = physical_amounts(read, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    r = surface.transport(
        ci,
        co,
        potential[:n],
        potential[n:],
        control.membrane,
        control.junction * state.junction_gate,
        s,
        xp=xp,
    )
    weight, log = imex.face_weights(co, s, xp=xp)
    diffusion = weight * log
    channel, channel_d, target, tau, cv = channel_rates(
        state.channel_gate,
        ci,
        co,
        r.membrane_voltage_V,
        r.membrane_delta_mu_J_mol,
        control.channel,
        p,
        xp=xp,
        structure=structure,
    )
    rate, args = nak_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_delta_mu_J_mol,
        control,
        p,
        xp=xp,
        structure=structure,
    )
    cycles = xp.where(p.pump_present, rate.cycles_fmol_s, 0.0)
    ca_cycles, ca_d, ca_metabolic, _, ca_args = calcium_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_voltage_V,
        control,
        p,
        xp=xp,
        structure=structure,
    )
    extra = (
        -p.stoichiometry * cycles
        - p.calcium_stoichiometry * ca_cycles
        + channel_to_membrane(channel, p, xp=xp)
    )
    process = None
    if membrane_process is not None:  # Opt-in (static); none by default.
        process = membrane_process(
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            p.volume[p.membrane_cell],
            r.membrane_voltage_V,
            xp=xp,
        )
        extra = extra + process.flux
    zero = xp.zeros_like(co)
    inflow = (
        scatter(r.membrane_flux_fmol_s + extra, zero, (p.membrane_outside,), xp=xp)
        - scatter(diffusion, zero, (p.face_sender,), xp=xp)
        + scatter(diffusion, zero, (p.face_receiver,), xp=xp)
    )
    gate = junction_gate_rhs(
        state.junction_gate, r.junction_voltage_V, p, xp=xp, structure=structure
    )
    outside_zero = xp.zeros_like(p.boundary_V)
    cell_rate = r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp)
    kind_rates = _kind_rates(kinds, read, potential, control, p, xp=xp)
    for kr in kind_rates:  # §7.4 (k), rates: into the shared inventory (rule (c)).
        cell_rate = cell_rate + kr.cell
        inflow = inflow + kr.outside
    rates = STATE_TYPE(
        cell_rate,
        xp.where(p.reservoir, 0.0, inflow),
        r.membrane_flux_fmol_s,
        r.junction_flux_fmol_s,
        diffusion,
        xp.where(p.reservoir, -inflow, 0.0),
        r.membrane_dissipation_pJ_s,
        r.junction_dissipation_pJ_s,
        xp.zeros_like(state.face_dissipated_energy_pJ),
        outside_zero,
        outside_zero,
        outside_zero,
        xp.zeros_like(state.channel_gate),
        channel,
        channel_d,
        xp.where(p.junction_active, gate, 0.0),
        cycles,
        -1e-3 * cycles * rate.cycle_free_energy_J_mol,
        -1e-3 * cycles * rate.chemical_drive_J_mol,
        ca_cycles,
        ca_d,
        ca_metabolic,
    )
    if kinds:
        rates = _with_kind_derivatives(rates, kind_rates, structure, state, xp=xp)
    valid = r.valid
    if kinds:  # A failed stage read, a kind's domain or a stage check refuses the step.
        outside_rate = xp.where(p.reservoir, 0.0, inflow)
        valid = valid & read_valid & _stage_checks(kinds, read, cell_rate, outside_rate, p, xp=xp)
        for kr in kind_rates:
            valid = valid & kr.valid
    if args is not None:  # The Na/K pump's domain, where its law is declared.
        valid = valid & xp.all(pump.domain_valid(*args, xp=xp))
    if ca_args is not None:
        valid &= xp.all(calcium_atpase.domain_valid(*ca_args, xp=xp))
    valid &= channel_domain_valid(cv, target, tau, p, xp=xp)
    if structure is None or structure.junction_laws:
        valid &= xp.all(
            junction_gate.domain_valid(
                state.junction_gate,
                r.junction_voltage_V,
                kinetic.junction_parameters(p),
                control.junction,
                xp=xp,
            )
        )
    for value in (*control, *rates):
        valid &= xp.all(xp.isfinite(value))
    for value in _availabilities(control, kinds) if kinds else control:
        valid &= xp.all((value >= 0) & (value <= 1))
    for kind in kinds:
        if kind.control_domain is not None:
            valid &= kind.control_domain(control, p, xp=xp)
    if process is not None:
        valid &= process.valid & xp.all(xp.isfinite(process.flux))
        valid &= xp.all(xp.isfinite(process.heat))
        return rates, valid, process
    return rates, valid


def implicit_rates(weight, potential, state, p, *, xp=jnp):
    """Face electromigration rates with frozen face weights; zero elsewhere."""
    s, n = tissue.field_layout(p).surface, p.active.size
    flux = imex.drift_flux(weight, potential[n:], s, xp=xp)
    zero = xp.zeros_like(state.extracellular_amount_increment)
    inflow = scatter(flux, zero, (p.face_receiver,), xp=xp) - scatter(
        flux, zero, (p.face_sender,), xp=xp
    )
    rates = type(state)(*(xp.zeros_like(v) for v in state))  # The state's own type (schema A).
    return rates._replace(
        extracellular_amount_increment=xp.where(p.reservoir, 0.0, inflow),
        face_transferred=flux,
        reservoir_supplied=xp.where(p.reservoir, -inflow, 0.0),
    )


def potential_kinetics(potential, p, *, xp=jnp, structure=None):
    """Channel targets, time constants and voltage-domain status at node potentials."""
    n = p.active.size
    membrane = potential[p.membrane_cell] - potential[n + p.membrane_outside]
    voltage = channel_voltage(xp.where(p.membrane_active, membrane, 0.0), p, xp=xp)
    target, tau = channel_kinetics(voltage, p.channel_laws, xp=xp, structure=structure)
    return target, tau, channel_domain_valid(voltage, target, tau, p, xp=xp)


def stage_gates(gate, start, stage, fraction, dt, p, *, xp=jnp):
    """Exponential gate update from the step start to a stage at fraction * dt.

    start is (targets, time constants) at the step start; stage is (targets,
    time constants, voltage domain status) from potential_kinetics. Gate rows
    without a relaxation law (leaks, padding) keep their zero state.
    """
    advanced = gates.advance(gate, start[0], start[1], stage[0], stage[1], fraction * dt, xp=xp)
    return xp.where(p.channel_gate_active, advanced, gate), stage[2]


def imex_step(state, dt, control, p, *, xp=jnp, membrane_process=None, structure=None):
    """surface_pump_v2.imex_step with channel currents and exponential stage gates.

    With a membrane_process (opt-in, module docstring) the call returns
    (state, valid, (transfer, heat)): the process's applied transfer
    [species, membrane] (fmol) and its trapezoid heat [membrane] (pJ) over the
    step, for the composing model's own ledgers. Otherwise (state, valid).
    """
    hook = {} if membrane_process is None else dict(membrane_process=membrane_process)
    hook["structure"] = structure
    processes = []
    kinds = _kinds(structure)
    f = tissue.field_layout(p)
    s, explicit_matrix, implicit_matrix = f.surface, p.imex_explicit, p.imex_implicit
    stages = explicit_matrix.shape[0]
    first_values = readouts(state, control, p, xp=xp, structure=structure)
    start = first_values.field.potential_V
    valid = first_values.valid
    if kinds:  # The face weights' amounts are the read's (§7.4 (k)).
        read, read_valid = _stage_read(state, p, kinds, xp=xp)
        valid &= read_valid
    else:
        read = state
    amount = p.extracellular_amount_reference + read.extracellular_amount_increment
    predicted = (
        amount + p.imex_operator_time * dt * first_values.derivative.extracellular_amount_increment
    )
    predicted = xp.where(p.outside_active, predicted / p.extracellular_volume, 1.0)
    valid &= xp.all(xp.isfinite(predicted) & (predicted > 0))
    weight, _ = imex.face_weights(xp.where(predicted > 0, predicted, 1.0), s, xp=xp)
    operator, ok = imex.factor_operator(
        implicit_matrix[-1, -1] * dt, imex.face_laplacian(weight, s, xp=xp), p.boundary_V, f, xp=xp
    )
    valid &= ok
    rates, ok, *process = explicit_rates(state, start, control, p, xp=xp, **hook)
    processes += process
    explicit, implicit, valid = [rates], [None], valid & ok
    explicit_states = [state]  # Each explicit stage's state (gap 7's per-stage values).
    # Channel currents are explicit: refuse the step where their actual
    # conductance at an explicit stage exceeds the family's stability bound.
    valid &= dt * membrane_rate(
        state, control, p, xp=xp, structure=structure, potentials=start
    ) <= (EXPLICIT_STEP_BOUND)
    material = material_rate(state, control, p, xp=xp, structure=structure, potentials=start)
    if material is not None:  # D4: a kind's material slope joins the same per-stage bound.
        valid &= dt * material <= EXPLICIT_STEP_BOUND
    # The start kinetics are the law's own (readouts at the start potentials).
    start_kinetics = (first_values.channel_targets, first_values.channel_tau_s)
    potential, stage = start, state
    for i in range(1, stages):
        known = first._combine(
            state,
            dt,
            [(explicit_matrix[i, j], explicit[j]) for j in range(i)]
            + [(implicit_matrix[i, j], implicit[j]) for j in range(1, i)],
        )
        charge = node_charge(known, p, xp=xp)
        potential, residual = imex.solve_operator(charge, operator, xp=xp)
        scale = xp.maximum(xp.abs(charge), xp.abs(operator.matrix @ potential))
        valid &= xp.all(xp.isfinite(potential))
        valid &= xp.all(xp.abs(residual) <= field.CHARGE_ATOL_C + field.CHARGE_RTOL * scale)
        drift = implicit_rates(weight, potential, state, p, xp=xp)
        implicit.append(drift)
        stage = first._combine(known, dt, [(implicit_matrix[i, i], drift)])
        gate, ok = stage_gates(
            state.channel_gate,
            start_kinetics,
            potential_kinetics(potential, p, xp=xp, structure=structure),
            entity_sum(explicit_matrix[i], axis=None, xp=xp),
            dt,
            p,
            xp=xp,
        )
        stage, valid = stage._replace(channel_gate=gate), valid & ok
        if i < stages - 1:
            rates, ok, *process = explicit_rates(stage, potential, control, p, xp=xp, **hook)
            processes += process
            explicit.append(rates)
            explicit_states.append(stage)
            valid &= ok & (
                dt
                * membrane_rate(stage, control, p, xp=xp, structure=structure, potentials=potential)
                <= EXPLICIT_STEP_BOUND
            )
            material = material_rate(
                stage, control, p, xp=xp, structure=structure, potentials=potential
            )
            if material is not None:
                valid &= dt * material <= EXPLICIT_STEP_BOUND
    last = stages - 1

    def applied(name):
        return sum(
            explicit_matrix[last, j] * getattr(explicit[j], name) for j in range(stages - 1)
        ) + sum(implicit_matrix[last, j] * getattr(implicit[j], name) for j in range(1, stages))

    # Dissipation of the applied average face flux, J^2 RT / W >= 0.
    flux = applied("face_transferred")
    heat = (
        1e-3
        * R
        * p.temperature
        * species_sum(
            xp.where(weight > 0, flux * flux / xp.where(weight > 0, weight, 1.0), 0.0), xp=xp
        )
    )
    electrode = first.electrode_increment(state, stage, p, xp=xp)
    co = xp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * xp.log(co) + p.valence * F * p.boundary_V
    stage = stage._replace(
        face_dissipated_energy_pJ=state.face_dissipated_energy_pJ + dt * heat,
        electrode_charge_transferred_C=state.electrode_charge_transferred_C + electrode,
        reservoir_work_pJ=state.reservoir_work_pJ
        + 1e-3 * species_sum(mu * (dt * applied("reservoir_supplied")), xp=xp),
        electrode_work_pJ=state.electrode_work_pJ + 1e12 * p.boundary_V * electrode,
    )
    if p.junction_heat_trapezoid.shape[0]:  # trapezoid_nonnegative@1 (a static choice).
        # The tableau's explicit weights (delta, 1 - delta), delta < 0, book a negative
        # junction heat increment where a junction's power falls by more than 59% in a
        # step (its voltage crossing zero). This booking instead averages the start
        # and end states' junction powers, both >= 0 (sum_s J_s dmu_s with J_s and dmu_s
        # of one sign); the end state's at its last-stage potentials, which satisfy
        # C phi = its charges. Only this ledger changes: the state is the default's.
        end_power = junction_heat_rate(stage, potential, control, p, xp=xp)
        stage = stage._replace(
            junction_dissipated_energy_pJ=state.junction_dissipated_energy_pJ
            + 0.5 * dt * (explicit[0].junction_dissipated_energy_pJ + end_power)
        )
    if kinds:  # Gap 7: the kinds' per-stage values, their running extrema over the stages.
        extrema = _stage_extrema(kinds, state, explicit_states, explicit, p, xp=xp)
        stage = stage._replace(**extrema)
    if kinds:  # §7.4 (k), book: a kind's bookings from the step's applied rates.
        booked, ok = _kind_bookings(kinds, applied, state, stage, control, p, dt, xp=xp)
        stage, valid = stage._replace(**booked), valid & ok
    valid &= domain_valid(stage, p, p.active, xp=xp, structure=structure)
    for value in stage:
        valid &= xp.all(xp.isfinite(value))
    if membrane_process is None:
        return jax.tree.map(lambda old, new: xp.where(valid, new, old), state, stage), valid
    # The process's applied transfer (the tableau's explicit weights: the exact
    # amount change it made) and its heat, the trapezoid of its start power and
    # its power at the end state and last-stage potentials.
    transfer = dt * sum(explicit_matrix[last, j] * processes[j].flux for j in range(stages - 1))
    n = p.active.size
    ci, co = physical_amounts(stage, p)
    end = membrane_process(
        xp.where(p.active, ci / p.volume, 1.0)[:, p.membrane_cell],
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0)[:, p.membrane_outside],
        p.volume[p.membrane_cell],
        xp.where(
            p.membrane_active, potential[p.membrane_cell] - potential[n + p.membrane_outside], 0.0
        ),
        xp=xp,
    )
    heat = 0.5 * dt * (processes[0].heat + end.heat)
    valid &= end.valid & xp.all(xp.isfinite(heat)) & xp.all(xp.isfinite(transfer))
    new = jax.tree.map(lambda old, new: xp.where(valid, new, old), state, stage)
    return new, valid, (transfer, heat)


def junction_heat_rate(state, potential, control, p, *, xp=jnp):
    """Each junction's dissipation (pJ/s) at the given node potentials.

    The junction part of numerics/surface_transport.transport: constant-field
    flux (coupling/selective.selective_flux) at the gated opening times the
    species' electrochemical potential difference, summed over species.
    """
    s = tissue.field_layout(p).surface
    ci, _ = physical_amounts(state, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    active = s.junction_active
    left = xp.where(active, ci[:, s.junction_sender], 1.0)
    right = xp.where(active, ci[:, s.junction_receiver], 1.0)
    dv = xp.where(active, potential[s.junction_sender] - potential[s.junction_receiver], 0.0)
    mu = R * s.temperature * (xp.log(left) - xp.log(right)) + s.valence * F * dv
    flux = selective_flux(
        left,
        right,
        dv,
        s.valence,
        s.temperature,
        s.junction_area,
        s.junction_permeability,
        0.0,
        1.0,
        control.junction * state.junction_gate,
        xp=xp,
    )
    flux, mu = xp.where(active, flux, 0.0), xp.where(active, mu, 0.0)
    return 1e-3 * species_sum(flux * mu, xp=xp)


def checked_step(state, dt, control, p, active, *, structure=None):
    """RK4 for an empty tableau (reference runs); otherwise the declared IMEX step."""
    if p.imex_explicit.shape[0] == 0:
        if structure is None:
            return rk4_checked_step(rhs, domain_valid, state, dt, control, p, active)
        bound = _bound_checks(structure)
        return rk4_checked_step(bound.rhs, bound.domain_valid, state, dt, control, p, active)
    return imex_step(state, dt, control, p, structure=structure)


def check_definition(spec, *, structure=None):
    from cells.definitions.surface_pump_v3_spec import control_values

    m = spec.model
    compact = replace(
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
    _check_kinds_solver(spec)  # Ahead of the kinds' own checks: under RK4 they are moot.
    kinds = _kinds(structure)
    for kind in kinds:  # §7.4 (k): a kind's definition checks, ahead of @3's.
        if kind.check_definition is not None:
            kind.check_definition(spec)
    _check_stage_rows(spec, kinds)
    _check_held_rows(spec, kinds)
    state, p = initial_values(compact, structure=structure)
    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    control_type = kind_types(structure).Control if structure is not None else Control
    if kinds:
        _check_device_hooks(kinds, state, p, control_type(*(v[0] for v in controls)))
        _check_routes(spec, structure, kinds, state, p, control_type(*(v[0] for v in controls)))
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            if not control_domain_valid(
                state,
                control_type(*(v[i] for v in controls)),
                p,
                p.active,
                xp=np,
                structure=structure,
            ):
                raise ConfigError("Initial resolved channel/junction/pump domain invalid")


def _check_kinds_solver(spec):
    """Declared kinds need an IMEX solver; under RK4 they are refused, fail-closed (the core's
    review of refusal 4 version 1.1, finding 6; the lead's ruling, 16 November 2026). Every kind
    guard that bounds or books a step belongs to the IMEX step: StepChecks holds B7's term and the
    kinds' bound_rate (kind_rate) for the IMEX solvers only, and the per-stage rule (membrane_rate
    with each kind's stage_term) and the end-of-step bookings (book, §7.5's exact booking) run in
    imex_step only. An RK4 step keeps only its 0.1 ms cap. A design for kinds under RK4 can lift
    this refusal."""
    declared = [kind_id for kind_id, _ in getattr(spec.model, "kinds", ())]
    if declared and spec.execution.solver == "rk4":
        raise ConfigError(
            f"Declared kinds ({', '.join(declared)}) require an IMEX solver: under RK4 none of "
            "the kinds' step guards run (the definition-time bound terms, the per-stage rule, the "
            "end-of-step bookings), so @3 refuses them (fails closed)"
        )


def _check_stage_rows(spec, kinds):
    """§7.4 (k): stage reads compose in hook order, so two that share a row would compose by ID,
    not physically. A kind's stage read declares the rows it reads or rewrites, and two kinds'
    reads on a shared row are refused at binding (until a dependency order exists)."""
    if not kinds:
        return
    declarations, claimed = dict(spec.model.kinds), {}
    for kind in kinds:
        if kind.stage_read is None:
            continue
        if kind.stage_rows is None:
            raise ConfigError(f"Kind {kind.kind_id} has a stage read but declares no stage rows")
        for row in kind.stage_rows(declarations[kind.kind_id]):
            other = claimed.setdefault(tuple(row), kind.kind_id)
            if other != kind.kind_id:
                raise ConfigError(
                    f"Kinds {other} and {kind.kind_id} both read row {tuple(row)} at each stage; "
                    "stage reads on a shared row do not commute and are refused"
                )


def moved_nodes(model):
    """{(species, node ID): (mover, ...)} of every in-step mover of the inner model, from
    moved_rows: each route's two end nodes (a channel's or a pump's, its patch's), and a kind's
    named nodes. A mover is named "<mover kind> <entity>" (a kind's: its kind ID)."""
    ends = {m.id: (m.inside, m.outside) for m in model.membranes}
    ends |= {j.id: (j.sender, j.receiver) for j in model.junctions}
    ends |= {f.id: (f.sender, f.receiver) for f in model.faces}
    ends |= {c.id: ends[c.membrane_id] for c in model.channels}
    out = {}
    for species, movers in moved_rows(model).items():
        for mover, _, entities in movers:
            for entity in entities:
                nodes = ends.get(entity, (entity,)) if mover in INNER_MOVERS else (entity,)
                name = f"{mover} {entity}" if mover in INNER_MOVERS else mover
                for node in nodes:
                    out.setdefault((species, node), []).append(name)
    return {key: tuple(value) for key, value in out.items()}


INNER_MOVERS = ("membrane", "junction", "face", "channel", "pump")


def _check_held_rows(spec, kinds):
    """Gap 8, one writer: a row a kind holds (read at every stage, never moved, such as held fuel)
    is moved by nothing in the inner step, neither a route nor another kind. Operators' writers
    are the composite's admission (species_registry.moved_in_step)."""
    held = [kind for kind in kinds if kind.held_rows is not None]
    if not held:
        return
    declarations, movers = dict(spec.model.kinds), moved_nodes(spec.model)
    for kind in held:
        for species, node in kind.held_rows(declarations[kind.kind_id]):
            writers = movers.get((species, node), ())
            if writers:
                raise ConfigError(
                    f"Kind {kind.kind_id} holds {species} at {node}, which {writers[0]} moves in "
                    "the step; a held row is moved by nothing in the step (one writer)"
                )


LEDGER_TERM_KEYS = ("cell", "outside", "produced", "heat_pJ", "work_pJ", "stored_pJ")


def _check_device_hooks(kinds, state, p, control):
    """§7.4 (k): the check-path hooks (stage_read, which domain_valid evaluates, domain,
    control_domain, ledger_terms) trace under jax.numpy with no value branch, so the device's row
    checks include the kinds as the host's do. Each is traced once here, on the definition's
    initial state, and its result's form is checked."""

    def refuse(kind, hook, reason):
        raise ConfigError(f"Kind {kind.kind_id}'s {hook} hook {reason}")

    def traced(kind, hook, function, *args):
        try:
            return jax.eval_shape(function, *args)
        except jax.errors.JAXTypeError as error:
            refuse(kind, hook, f"does not trace on the device (a value branch?): {error}")

    def boolean(kind, hook, value):
        if value.shape != () or value.dtype != np.bool_:
            refuse(kind, hook, f"must return one boolean, not {value.shape} {value.dtype}")

    shapes = dict(
        cell=np.shape(state.amount_increment),
        outside=np.shape(state.extracellular_amount_increment),
        produced=np.shape(state.amount_increment)[:1],
    )
    tree = jax.tree.structure(state)
    for kind in kinds:
        if kind.stage_read is not None:  # On the check path too: domain_valid evaluates reads.
            read, ok = traced(kind, "stage_read", partial(kind.stage_read, xp=jnp), state, p)
            if jax.tree.structure(read) != tree:
                refuse(kind, "stage_read", "must return a state of the structure's state type")
            boolean(kind, "stage_read", ok)
        if kind.stage_check is not None:  # On the step path; traced here for an early refusal.
            rates = (state.amount_increment, state.extracellular_amount_increment)
            check = traced(kind, "stage_check", partial(kind.stage_check, xp=jnp), state, *rates, p)
            boolean(kind, "stage_check", check)
        if kind.domain is not None:
            domain = traced(kind, "domain", partial(kind.domain, xp=jnp), state, p)
            boolean(kind, "domain", domain)
        if kind.control_domain is not None:
            hook = partial(kind.control_domain, xp=jnp)
            boolean(kind, "control_domain", traced(kind, "control_domain", hook, control, p))
        if kind.ledger_terms is not None:
            terms = traced(kind, "ledger_terms", partial(kind.ledger_terms, xp=jnp), state, p)
            unknown = set(terms) - set(LEDGER_TERM_KEYS)
            if unknown:
                refuse(kind, "ledger_terms", f"returns unknown terms {sorted(unknown)}")
            for key, shape in shapes.items():
                if key in terms and tuple(terms[key].shape) != shape:
                    refuse(kind, "ledger_terms", f"returns {key} of shape {terms[key].shape}")


def _check_routes(spec, structure, kinds, state, p, control):
    """§7.4 (n): every source's factors are [len(sources)] numbers on the device (traced once on the
    initial state), and every routed slot lies inside its control field."""
    declarations = dict(spec.model.kinds)
    for kind in kinds:
        if kind.factor_sources is None:
            continue
        kind_id = kind_registry.qualified(kind.kind_id)
        count = len(kind.factor_sources(declarations[kind_id]))
        try:
            factors = jax.eval_shape(partial(kind.factors, xp=jnp), state, p)
        except jax.errors.JAXTypeError as error:
            raise ConfigError(f"Kind {kind_id}'s factors hook does not trace: {error}") from error
        if factors.shape != (count,) or not jnp.issubdtype(factors.dtype, jnp.floating):
            raise ConfigError(
                f"Kind {kind_id}'s factors must be {count} floats, not {factors.shape} "
                f"{factors.dtype}"
            )
    for kind_id, name, slot, _ in structure.routes:
        size = np.shape(getattr(control, name))[-1]
        if not 0 <= slot < size:
            raise ConfigError(
                f"Kind {kind_id}'s routed control {name}[{slot}] is outside [0, {size})"
            )


def membrane_rate(state, control, p, *, xp=jnp, structure=None, potentials=None):
    """Gershgorin rate (1/s) of membrane charge relaxation at a stage's actual openings.

    @1's membrane term, max_i sum_m G_m / C_i, with each population's open
    constant-field slope conductance F^2/RT sum z^2 P r a o v A max(c) added to
    its patch (o its opening, v its availability). max(c) bounds the
    constant-field slope, so this bounds the explicit channel stiffness.
    Quasi-steady gating slopes are not included; the step studies measure them.
    """
    ci, co = physical_amounts(state, p)
    ci = xp.where(p.active, ci / p.volume, 0.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 0.0)
    slope, n, patch = F * F / (R * p.temperature), p.active.size, p.channel_membranes
    largest = xp.maximum(ci[:, p.membrane_cell], co[:, p.membrane_outside])
    passive = (
        species_sum(p.valence**2 * p.membrane_permeability * largest, xp=xp) * control.membrane
    )
    open_fraction = xp.where(
        p.channel_active,
        p.channel_abundance
        * channel_opening(state.channel_gate, p.channel_laws, xp=xp, structure=structure),
        0.0,
    )
    channel = species_sum(
        p.valence**2 * p.channel_permeability * p.channel_relative_permeability * largest[:, patch],
        xp=xp,
    ) * (open_fraction * control.channel)
    membrane = xp.where(p.membrane_active, passive * p.membrane_area, 0.0)
    membrane += scatter(channel * p.membrane_area[patch], membrane, (patch,), xp=xp)
    total = slope * scatter(membrane, xp.zeros(n), (p.membrane_cell,), xp=xp)
    capacitance = scatter(p.membrane_capacitance, xp.zeros(n), (p.membrane_cell,), xp=xp)
    kinds = _kinds(structure)
    if not kinds:  # Today's rate: the cells' rows.
        return xp.max(xp.where(p.active, total / xp.where(p.active, capacitance, 1.0), 0.0))
    # Gap 5 with kinds: each kind's conductance at the stage, per node (cells, then outside
    # nodes), at the read amounts and the stage's potentials; and the free outside nodes' rows
    # too (a face-free compartment's small capacitance), with @3's own patch terms there.
    read, _ = _stage_read(state, p, kinds, xp=xp)
    control, _ = _route(structure, kinds, read, control, p, xp=xp)  # §7.4 (n); its validity is
    nodes = xp.zeros(n + p.outside_active.size)  # the stage's (explicit_rates, readouts).
    for kind in kinds:
        if kind.stage_term is not None:
            nodes = nodes + kind.stage_term(read, potentials, control, p, xp=xp)
    total = total + nodes[:n]
    cells = xp.max(xp.where(p.active, total / xp.where(p.active, capacitance, 1.0), 0.0))
    o = p.outside_active.size
    node_total = slope * scatter(membrane, xp.zeros(o), (p.membrane_outside,), xp=xp) + nodes[n:]
    patches = xp.where(p.membrane_active, p.membrane_capacitance, 0.0)
    node_capacitance = scatter(patches, xp.zeros(o), (p.membrane_outside,), xp=xp)
    free = free_outside_nodes(p, xp=xp) & (node_capacitance > 0)
    outside = xp.max(xp.where(free, node_total / xp.where(free, node_capacitance, 1.0), 0.0))
    return xp.maximum(cells, outside)


def material_rate(state, control, p, *, xp=jnp, structure=None, potentials=None):
    """D4: the declared kinds' material relaxation rate (1/s) at a stage, or None without a kind
    that declares material_term (so no program changes). Each such kind's term is per node (cells,
    then outside nodes) at the stage's read amounts and node potentials, after the routing door;
    the terms add per node, and the rate is their largest over cells and outside nodes that are not
    held baths (a held row does not relax). The step holds dt x rate <= EXPLICIT_STEP_BOUND at
    every explicit stage, as membrane_rate's charge rule (the FR-4/FR-5 note's §17, D4)."""
    kinds = _kinds(structure)
    sloped = [kind for kind in kinds if kind.material_term is not None]
    if not sloped:
        return None
    read, _ = _stage_read(state, p, kinds, xp=xp)
    control, _ = _route(structure, kinds, read, control, p, xp=xp)  # Validity: the stage's.
    n = p.active.size
    nodes = xp.zeros(n + p.outside_active.size)
    for kind in sloped:
        nodes = nodes + kind.material_term(read, potentials, control, p, xp=xp)
    cells = xp.max(xp.where(p.active, nodes[:n], 0.0), initial=0.0)
    moving = p.outside_active & ~p.reservoir
    return xp.maximum(cells, xp.max(xp.where(moving, nodes[n:], 0.0), initial=0.0))


def free_outside_nodes(p, *, xp=jnp):
    """[outside] the free outside nodes: active, not a held bath, not the gauge, not a fixed node
    and named by no active face (B7's face-free nodes, surface_pump.face_free_node_rate), whose
    charge their patches relax explicitly."""
    o, n = p.outside_active.size, p.active.size
    zero = xp.zeros(o)
    faced = xp.where(p.face_active, 1.0, 0.0)
    named = scatter(faced, zero, (p.face_sender,), xp=xp) + scatter(
        faced, zero, (p.face_receiver,), xp=xp
    )
    fixed = p.field_fixed[n:] if hasattr(p, "field_fixed") else xp.zeros(o, dtype=bool)
    return p.outside_active & ~p.reservoir & (named == 0) & ~p.field_gauge_mask & ~fixed


def patch_node_conductance(slope, p, *, xp=jnp):
    """[cells, then outside nodes] a per-patch conductance [membrane] (S) at both of each active
    patch's ends: the form a kind's stage_term returns (gap 5)."""
    n, o = p.active.size, p.outside_active.size
    slope = xp.where(p.membrane_active, slope, 0.0)
    zero = xp.zeros(n + o)
    inside = scatter(slope, zero, (p.membrane_cell,), xp=xp)
    return inside + scatter(slope, zero, (n + p.membrane_outside,), xp=xp)


# ------------------------------------------------------------------ the host table (seam A's)
# docs/CORE_SEAMS_DESIGN.md §2 and §3. A host is an entity with two ends, each resolved at binding
# to a node index (cells, then outside nodes). The core gives one table per structure: each host's
# kind, its end-a node, its end-b node and its activity. Kinds read their ends through it, never
# through a host's own fields, so a population sits on any host by its index.
# - Layout data, not structure: the table is read from the layout, so a world of the same shapes
#   with another topology reuses the executable (P5).
# - No field of its own: it is read from the hosts' own layout fields (membrane_cell,
#   membrane_outside, membrane_active; junction_sender, junction_receiver, junction_active). So a
#   world that does not read it keeps its programs and bindings (A4). Under a composite it reads
#   the adapter's view, so a patch or junction that a closer closes reads inactive there.
# - The index space: the membrane slots (patches) first, then the edge slots (junctions), padded
#   slots included and inactive. A patch's end a is its cell and its end b its outside node; a
#   junction's end a is its sender and its end b its receiver.
# - The voltage rule: phi(a) - phi(b) for a patch and for a junction, @3's membrane and junction
#   voltages (numerics/surface_transport.transport). A route between two pools joins later as a
#   host kind of its own, whose rule is zero, with no change to the kinds that read the table.
HOST_KINDS = ("patch", "junction")  # In table order.


class HostTable(NamedTuple):
    """The host table of a layout (or of a composite's view), each field [host]."""

    kind: object  # int64, an index of HOST_KINDS
    end_a: object  # int64, a node index (cells, then outside nodes)
    end_b: object  # int64, a node index
    active: object  # bool: an inactive host (padding, or closed at the view) moves nothing


class Host(NamedTuple):
    """One declared host, resolved on the host side: its ID, kind, index and end nodes' IDs."""

    id: str
    kind: str  # One of HOST_KINDS.
    index: int  # Its row of the host table.
    end_a: str  # A patch's cell, a junction's sender.
    end_b: str  # A patch's outside node, a junction's receiver.


def host_table(p, *, xp=jnp):
    """The host table of a layout p (or a composite's view of it): HostTable, each field [host]."""
    n, m, e = p.active.size, p.membrane_active.size, p.junction_active.size
    return HostTable(
        kind=xp.concatenate(
            (xp.zeros(m, dtype=np.int64), xp.full(e, HOST_KINDS.index("junction"), dtype=np.int64))
        ),
        end_a=xp.concatenate((p.membrane_cell, p.junction_sender)),
        end_b=xp.concatenate((n + p.membrane_outside, p.junction_receiver)),
        active=xp.concatenate((p.membrane_active, p.junction_active)),
    )


def host_ends(values, hosts, p, *, xp=jnp):
    """(at end a, at end b), each [..., len(hosts)]: a node quantity values [..., node] (cells,
    then outside nodes, such as node_concentrations) read at the two ends of each listed host.
    hosts: host indices, layout data (a population's host, say)."""
    table = host_table(p, xp=xp)
    return values[..., table.end_a[hosts]], values[..., table.end_b[hosts]]


def host_voltage(potentials, p, *, xp=jnp):
    """[host] each host's voltage by its kind's rule (V), from node potentials [cells, then outside
    nodes]: phi(end a) - phi(end b) for a patch and for a junction; 0 at an inactive host."""
    table = host_table(p, xp=xp)
    return xp.where(table.active, potentials[table.end_a] - potentials[table.end_b], 0.0)


def host_scatter(at_a, at_b, hosts, p, *, xp=jnp):
    """(cell [..., cell], outside [..., outside node]): per-entity node changes summed into the
    nodes at its host's ends, at_a at end a and at_b at end b (each [..., len(hosts)]), in a kind's
    rates form (KindRates.cell, KindRates.outside). An entity on an inactive host adds nothing.
    A transfer f from end a to end b is at_a = -f, at_b = +f."""
    table = host_table(p, xp=xp)
    n, o = p.active.size, p.outside_active.size
    active = table.active[hosts]
    zero = xp.zeros((*at_a.shape[:-1], n + o), dtype=at_a.dtype)
    nodes = scatter(xp.where(active, at_a, 0.0), zero, (table.end_a[hosts],), xp=xp)
    nodes = nodes + scatter(xp.where(active, at_b, 0.0), zero, (table.end_b[hosts],), xp=xp)
    return nodes[..., :n], nodes[..., n:]


def host_node_conductance(slope, hosts, p, *, xp=jnp):
    """[cells, then outside nodes] a per-entity conductance (S) at both ends of its host, for a
    kind's stage_term (gap 5): patch_node_conductance for entities on any host. An entity on an
    inactive host adds nothing."""
    table = host_table(p, xp=xp)
    n, o = p.active.size, p.outside_active.size
    slope = xp.where(table.active[hosts], slope, 0.0)
    zero = xp.zeros(n + o)
    return scatter(slope, zero, (table.end_a[hosts],), xp=xp) + scatter(
        slope, zero, (table.end_b[hosts],), xp=xp
    )


def node_concentrations(state, p, *, xp=jnp):
    """[species, node] every node's concentrations (mM) at `state` (a stage's read state, say),
    cells then outside nodes, as the rates read them; padded nodes read 1."""
    ci, co = physical_amounts(state, p)
    return xp.concatenate(
        (
            xp.where(p.active, ci / p.volume, 1.0),
            xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
        ),
        axis=1,
    )


def node_ids(spec):
    """The node index space's IDs, cells then outside nodes, each padded slot None."""
    m, x = spec.model, spec.execution
    cells = [c.id for c in m.cells] + [None] * (x.capacity - len(m.cells))
    outside = [o.id for o in m.extracellular]
    return cells + outside + [None] * (x.extracellular_capacity - len(outside))


def host_ids(spec):
    """The host table's IDs in host order: the membrane slots' patches, then the edge slots'
    junctions, each padded slot None."""
    m, x = spec.model, spec.execution
    patches = [p.id for p in m.membranes] + [None] * (x.membrane_capacity - len(m.membranes))
    junctions = [j.id for j in m.junctions] + [None] * (x.edge_capacity - len(m.junctions))
    return patches + junctions


def declared_hosts(spec):
    """{host ID: Host} of every declared patch and junction, on the host side (a kind's parse and
    initial values resolve a declared host with it)."""
    m, offset = spec.model, spec.execution.membrane_capacity
    out = {p.id: Host(p.id, "patch", i, p.inside, p.outside) for i, p in enumerate(m.membranes)}
    for i, j in enumerate(m.junctions):
        out[j.id] = Host(j.id, "junction", offset + i, j.sender, j.receiver)
    return out


def host_index(spec, host_id):
    """The host-table row of a declared patch or junction; ConfigError for any other ID."""
    host = declared_hosts(spec).get(host_id)
    if host is None:
        raise ConfigError(f"{host_id!r} is not a declared host (a membrane patch or a junction)")
    return host.index


def check_steps(spec, steps, controls):
    """@2's step checks on this definition's own event grid (channel events included).

    Observations must lie on accepted boundaries of the full grid; the junction,
    explicit-rate and calcium bounds depend only on the channel-free part. RK4
    also keeps the channel family's qualified step bounds. IMEX channel
    stiffness depends on the openings, so each IMEX step refuses itself when
    dt * membrane_rate exceeds the explicit bound at a stage. The checks of one
    chunk of steps (StepChecks); they read no controls.
    """
    bind_step_checks(spec)(steps)


def bind_step_checks(spec):
    """check_steps bound to one definition, for every chunk of its clock (StepChecks)."""
    return StepChecks(spec)


class StepChecks(first.StepChecks):
    """check_steps for one definition, called with the steps of each chunk of its clock.

    As surface_pump.StepChecks: what the checks read from the definition alone
    (accepted observations, the explicit-rate and calcium bounds of the
    channel-free projection, each building its layout, the junction bound and the
    gated RK4 laws) is evaluated at its first use and kept for the later chunks.
    A call makes check_steps' refusals in check_steps' order.
    """

    @cached_property
    def base(self):
        """The channel-free (@2) projection that the explicit and calcium bounds read."""
        return projection(self.spec)

    @cached_property
    def explicit_rate(self):
        return first.explicit_rate_bound(self.base)

    @cached_property
    def calcium_rate(self):
        return second.calcium_rate_bound(self.base)

    @cached_property
    def gated_laws(self):
        return {c.kinetic_law for c in self.spec.model.channels if c.initial_gate}

    @cached_property
    def kind_rate(self):
        """Gap 5: the declared kinds' definition-time bound terms (1/s; the passive law's
        dt L <= 1, say), each its own rule: the largest."""
        registry, rates = kind_registry.active(), [0.0]
        for kind_id, declaration in getattr(self.spec.model, "kinds", ()):
            kind = registry.lookup(kind_id)
            if kind.bound_rate is not None:
                rates.append(float(kind.bound_rate(self.spec, declaration)))
        return max(rates)

    def __call__(self, steps):
        spec, step = self.spec, np.max(steps, initial=0)
        if spec.execution.solver == "rk4":
            tissue.check_steps(spec, steps, None)
            laws = self.gated_laws
            if NAV1P2_LAW_ID in laws and step > RK4_SODIUM_STEP + 1e-16:
                raise ConfigError("Resolved NaV1.2 channels require RK4 steps <= 2.5 us")
            if laws and step > RK4_POTASSIUM_STEP + 1e-16:
                raise ConfigError("Resolved gated channels require RK4 steps <= 25 us")
        else:
            self.require_accepted_observations()
            if step * self.explicit_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the explicit-rate stability bound")
            if step * self.calcium_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")
            if step * self.kind_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds a declared kind's explicit-rate bound")
        if step * self.junction_rate > first.GATE_STEP_BOUND:
            raise ConfigError("Resolved junction step exceeds conservative kinetic bound")


def balances(state, p, *, structure=None):
    total = state.membrane_transferred + channel_to_membrane(state.channel_transferred, p, xp=np)
    result = second.balances(state._replace(membrane_transferred=total), p)
    result["energy"] += entity_sum(
        species_sum(state.channel_dissipated_energy_pJ, xp=np), axis=None, xp=np
    )
    if structure is not None and structure.kinds:
        _fold_kind_ledgers(result, state, p, _kinds(structure), xp=np)
    return result


def _fold_kind_ledgers(result, state, p, kinds, *, xp):
    """Rule (a): each kind's ledger terms fold into today's ledgers by role. Its cumulative
    inward-positive node transfers close the material ledgers (they are in the amounts, rule
    (c)); its heat and work accumulators join the energy ledger as dissipation and work; its
    stored term (free energy it holds beyond the stored rows' own terms, since the start: FR-4's
    buffer term, finite fuel's standard term) joins the stored energy. Its net production per
    species (`produced`, a reaction's record: finite fuel's ATP -> ADP + Pi) joins the global
    material ledger, which otherwise holds every kind to transfers (§7.4 (m))."""
    for kind in kinds:
        if kind.ledger_terms is None:
            continue
        terms = kind.ledger_terms(state, p, xp=xp)
        if "cell" in terms:
            result["local"] = result["local"] - terms["cell"]
        if "outside" in terms:
            result["outside"] = result["outside"] - terms["outside"]
        if "produced" in terms:
            result["total"] = result["total"] - terms["produced"]
        if "heat_pJ" in terms:
            result["energy"] = result["energy"] + entity_sum(terms["heat_pJ"], axis=None, xp=xp)
        if "work_pJ" in terms:
            result["energy"] = result["energy"] - entity_sum(terms["work_pJ"], axis=None, xp=xp)
        if "stored_pJ" in terms:
            result["energy"] = result["energy"] + entity_sum(terms["stored_pJ"], axis=None, xp=xp)


def channel_magnitudes(row, p, *, xp=np, structure=None):
    """surface_pump.ledger_magnitudes with both pumps' and the channels' accumulators."""
    membrane = (
        xp.abs(row.membrane_transferred)
        + channel_to_membrane(xp.abs(row.channel_transferred), p, xp=xp)
        + xp.abs(p.stoichiometry * row.pump_cycles)
        + xp.abs(p.calcium_stoichiometry * row.calcium_pump_cycles)
    )
    metabolic = xp.concatenate(
        (
            xp.abs(row.metabolic_work_pJ) + 1e-3 * xp.abs(p.pump_drive * row.pump_cycles),
            xp.abs(row.calcium_metabolic_work_pJ)
            + 1e-3 * xp.abs(p.calcium_pump_drive * row.calcium_pump_cycles),
        )
    )
    magnitudes = first.ledger_magnitudes(row, p, membrane, metabolic, xp=xp)
    if structure is None or not structure.kinds:
        return magnitudes
    magnitudes = list(magnitudes)  # Rule (a): the kinds' terms join their ledgers' magnitudes.
    for kind in _kinds(structure):
        if kind.ledger_terms is None:
            continue
        terms = kind.ledger_terms(row, p, xp=xp)
        names = ledger_lists(structure).LEDGERS
        for key, ledger in (("cell", "local"), ("outside", "outside"), ("produced", "total")):
            index = names.index(ledger)
            if key in terms and magnitudes[index] is not None:
                magnitudes[index] = magnitudes[index] + xp.abs(terms[key])
        # The energy ledger's bound scales with the flows, which take every *_dissipated_energy_pJ
        # and *_work_pJ field by name, the kinds' accumulators included.
    return tuple(magnitudes)


DISSIPATION_FIELDS = tuple(k for k in STATE_AXES if k.endswith("_dissipated_energy_pJ"))


def check_values(state, spec, steps=None, *, structure=None):
    """The family's host checks (surface_pump.checked_rows) with the channel ledgers."""
    _, p = initial_values(spec, structure=structure)
    kinds = structure is not None and bool(structure.kinds)
    return first.checked_rows(
        state,
        spec,
        p,
        domain=domain_valid if structure is None else _bound_checks(structure).domain_valid,
        balances=partial(balances, structure=structure) if kinds else balances,
        magnitudes=partial(channel_magnitudes, structure=structure)
        if kinds
        else channel_magnitudes,
        dissipation=dissipation_fields(structure),
        steps=steps,
        ledgers=ledger_lists(structure),
    )


def dissipation_fields(structure):
    """Every *_dissipated_energy_pJ state field of the structure's state type, kinds' included
    (checked nonnegative and non-decreasing per element, on the host and the device)."""
    if structure is None or not structure.kinds:
        return DISSIPATION_FIELDS
    axes = kind_types(structure).STATE_AXES
    return tuple(k for k in axes if k.endswith("_dissipated_energy_pJ"))


# Device checks (cells.execution.vector_windows, execution/projective.py): check_values'
# tests per accepted row, compiled. They are the host tests with the same
# functions and bounds: domain_valid (channel laws and padding, gates in [0, 1],
# no gate state on gate-free leaks or padding, no transfer or heat on an absent
# route), every ledger of balances() with the channel transfers in the membrane
# total and their heat in the energy ledger, bounds from surface_pump.ledger_limits
# with channel_magnitudes, and every dissipation field, channels' included.
DEVICE_CHECKS = first.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = first.DEVICE_DIAGNOSTICS
device_failure_message = first.device_failure_message
device_check_constants = first.device_check_constants
LEDGER_NAMES = ("LEDGERS", "LEDGER_DIAGNOSTICS", "ledger_limits", "ENERGY_RTOL")


@cache
def ledger_lists(structure):
    """The ledger protocol of a structure (docs/INNER_MODEL_V4_DESIGN.md §7.4 (p)): LEDGERS,
    LEDGER_DIAGNOSTICS, ledger_limits and ENERGY_RTOL, which the shared check paths read
    (surface_pump.checked_rows, surface_pump_checks.row_checks), with DEVICE_CHECKS and
    DEVICE_DIAGNOSTICS built from them. Every structure has today's: @1's own objects. A kind
    that declares a ledger of its own will append to them here (the hook, ledgers(declaration),
    follows its first consumer; §7.4 (p)). None is the module's."""
    names = LEDGER_NAMES + ("DEVICE_CHECKS", "DEVICE_DIAGNOSTICS")
    return SimpleNamespace(**{name: getattr(first, name) for name in names})


def device_balances(state, p, *, structure=None):
    """balances() with jax.numpy: the same channel terms, then @2's, in the same order."""
    total = state.membrane_transferred + channel_to_membrane(state.channel_transferred, p, xp=jnp)
    result = second.device_balances(state._replace(membrane_transferred=total), p)
    result["energy"] += entity_sum(
        species_sum(state.channel_dissipated_energy_pJ, xp=jnp), axis=None, xp=jnp
    )
    if structure is not None and structure.kinds:
        _fold_kind_ledgers(result, state, p, _kinds(structure), xp=jnp)
    return result


def device_checks(previous, row, p, constants, steps, *, structure=None, margins=False):
    """check_values' tests for one accepted row on the device: (failed, diagnostics).

    steps is the row's accepted-step count, the host check's value for that row.
    margins=True also returns each ledger's ratio to its bound (row_checks).
    """
    from cells.models.surface_pump_checks import row_checks

    kinds = structure is not None and bool(structure.kinds)
    return row_checks(
        previous,
        row,
        p,
        constants,
        steps,
        domain_valid=domain_valid if structure is None else _bound_checks(structure).domain_valid,
        balances=partial(device_balances, structure=structure) if kinds else device_balances,
        limits=ledger_lists(structure).ledger_limits,
        magnitudes=partial(channel_magnitudes, structure=structure)
        if kinds
        else channel_magnitudes,
        dissipation=dissipation_fields(structure),
        ledgers=ledger_lists(structure),
        margins=margins,
    )


OBSERVATION_FIELDS = second.OBSERVATION_FIELDS
Observations = make_dataclass(
    "SurfacePumpChannelObservations", [(k, np.ndarray) for k in OBSERVATION_FIELDS], frozen=True
)

# ------------------------------------------------------------------ the run view's declarations
# docs/RUN_VIEW_DESIGN.md §3 (D154), in the operator contract's forms: host-side metadata read
# only by the run-view writer (cells/records/run_view.py), so none changes a program, a binding or a
# checkpoint. They replace the writer's interim table for resolved_pump_tissue@3. Each state
# field and observation column has its unit, record kind and layer; each readout its axes (the
# state's are STATE_AXES). Orientations name the roles of the record's entity set: a flow's
# {from, to} (which way a positive value moves) or a difference's {plus, minus} (plus less
# minus). The core's owner confirmed them from the code (core-next, 16 November 2026):
# numerics/surface_transport.transport takes a membrane's voltage as its cell's potential less
# its outside node's and a junction's as its sender's less its receiver's, and its positive route
# flux runs sender -> receiver, a membrane's cell -> outside node; surface_tissue.balances books
# membrane_transferred out of the cell into the node, junction and face transfers out of the
# sender into the receiver, and reservoir supply into the held node; surface_pump_v2.balances
# subtracts stoichiometry x cycles (inward-positive per cycle) from the membrane total.
_CONFIRMED = "the core's owner, from the code (core-next, 16 November 2026)"


def _flow(origin, target, says):
    return MappingProxyType({"from": origin, "to": target, "says": says, "confirmed": _CONFIRMED})


def _difference(plus, minus, says):
    return MappingProxyType({"plus": plus, "minus": minus, "says": says, "confirmed": _CONFIRMED})


_OUTWARD = _flow(
    "inside", "outside", "a positive amount leaves the patch's cell for its outside node"
)
_CHANNEL_OUTWARD = _flow(
    "inside",
    "outside",
    "a positive amount leaves the cell of the population's patch for that patch's outside node; "
    "the material balance adds it into the patch's total",
)
_SENDER_TO_RECEIVER = _flow(
    "sender", "receiver", "a positive amount leaves the sender for the receiver"
)
_PUMP_INWARD = _flow(
    "outside",
    "inside",
    "pump cycles are inward-positive: a positive cycle moves each moved row's per-cycle count "
    "(the law's moves, by role, signed) from the patch's outside node into its cell",
)
_SUPPLY = _flow(
    "exterior", "node", "a positive amount is supplied into the held outside node from beyond"
)
_MEMBRANE_VOLTAGE = _difference(
    "inside",
    "outside",
    "the potential of the patch's cell less that of its outside node: positive when the cell is "
    "at the higher potential",
)
_JUNCTION_VOLTAGE = _difference(
    "sender",
    "receiver",
    "the potential of the junction's sender cell less that of its receiver: positive when the "
    "sender is at the higher potential",
)
VIEW_LAYERS = (
    MappingProxyType(
        {"id": "membrane", "label": "Membrane voltage and ions", "representation": "simulated"}
    ),
    MappingProxyType(
        {
            "id": "channels",
            "label": "Channel populations and junction gates",
            "representation": "modelled",
        }
    ),
    MappingProxyType({"id": "pumps", "label": "Pump populations", "representation": "modelled"}),
)
# field: (unit, record kind, layer, readout axes or None for a state field, orientation or None)
_VIEW_TABLE = {
    # State.
    "amount_increment": ("fmol", "amount", "membrane", None, None),
    "extracellular_amount_increment": ("fmol", "amount", "membrane", None, None),
    "membrane_transferred": ("fmol", "cumulative", "membrane", None, _OUTWARD),
    "junction_transferred": ("fmol", "cumulative", "membrane", None, _SENDER_TO_RECEIVER),
    "face_transferred": ("fmol", "cumulative", "membrane", None, _SENDER_TO_RECEIVER),
    "reservoir_supplied": ("fmol", "cumulative", "membrane", None, _SUPPLY),
    "membrane_dissipated_energy_pJ": ("pJ", "cumulative", "membrane", None, None),
    "junction_dissipated_energy_pJ": ("pJ", "cumulative", "membrane", None, None),
    "face_dissipated_energy_pJ": ("pJ", "cumulative", "membrane", None, None),
    "electrode_charge_transferred_C": ("C", "cumulative", "membrane", None, None),
    "reservoir_work_pJ": ("pJ", "cumulative", "membrane", None, None),
    "electrode_work_pJ": ("pJ", "cumulative", "membrane", None, None),
    "channel_gate": ("1", "level", "channels", None, None),
    "channel_transferred": ("fmol", "cumulative", "channels", None, _CHANNEL_OUTWARD),
    "channel_dissipated_energy_pJ": ("pJ", "cumulative", "channels", None, None),
    "junction_gate": ("1", "level", "channels", None, None),
    "pump_cycles": ("fmol", "cumulative", "pumps", None, _PUMP_INWARD),
    "pump_dissipated_energy_pJ": ("pJ", "cumulative", "pumps", None, None),
    "metabolic_work_pJ": ("pJ", "cumulative", "pumps", None, None),
    "calcium_pump_cycles": ("fmol", "cumulative", "pumps", None, _PUMP_INWARD),
    "calcium_pump_dissipated_energy_pJ": ("pJ", "cumulative", "pumps", None, None),
    "calcium_metabolic_work_pJ": ("pJ", "cumulative", "pumps", None, None),
    # Readouts.
    "amount": ("fmol", "amount", "membrane", ("species", "cell_slot"), None),
    "extracellular_amount": ("fmol", "amount", "membrane", ("species", "extracellular_slot"), None),
    "cell_potential_V": ("V", "level", "membrane", ("cell_slot",), None),
    "extracellular_potential_V": ("V", "level", "membrane", ("extracellular_slot",), None),
    "membrane_voltage_V": ("V", "level", "membrane", ("membrane_slot",), _MEMBRANE_VOLTAGE),
    "junction_voltage_V": ("V", "level", "membrane", ("edge_slot",), _JUNCTION_VOLTAGE),
    "membrane_flux_fmol_s": ("fmol/s", "rate", "membrane", ("species", "membrane_slot"), _OUTWARD),
    "junction_flux_fmol_s": (
        "fmol/s",
        "rate",
        "membrane",
        ("species", "edge_slot"),
        _SENDER_TO_RECEIVER,
    ),
    "face_flux_fmol_s": (
        "fmol/s",
        "rate",
        "membrane",
        ("species", "face_slot"),
        _SENDER_TO_RECEIVER,
    ),
    "reservoir_supply_fmol_s": (
        "fmol/s",
        "rate",
        "membrane",
        ("species", "extracellular_slot"),
        _SUPPLY,
    ),
    "electrode_charge_C": ("C", "amount", "membrane", ("extracellular_slot",), None),
    "electrode_current_A": ("A", "rate", "membrane", ("extracellular_slot",), None),
    "reservoir_power_pJ_s": ("pJ/s", "rate", "membrane", ("world",), None),
    "electrode_power_pJ_s": ("pJ/s", "rate", "membrane", ("world",), None),
    "charge_residual_C": ("C", "level", "membrane", ("field_node",), None),
    "component_current_residual_A": ("A", "rate", "membrane", ("floating_component",), None),
    "energy_balance_pJ_s": ("pJ/s", "rate", "membrane", ("world",), None),
    "membrane_availability": ("1", "level", "membrane", ("membrane_slot",), None),
    "junction_availability": ("1", "level", "channels", ("edge_slot",), None),
    "channel_flux_fmol_s": (
        "fmol/s",
        "rate",
        "channels",
        ("species", "channel_slot"),
        _CHANNEL_OUTWARD,
    ),
    "channel_targets": ("1", "level", "channels", ("gate", "channel_slot"), None),
    "channel_tau_s": ("s", "level", "channels", ("gate", "channel_slot"), None),
    "pump_cycle_rate_fmol_s": ("fmol/s", "rate", "pumps", ("membrane_slot",), _PUMP_INWARD),
    "pump_affinity_J_mol": ("J/mol", "level", "pumps", ("membrane_slot",), None),
    "metabolic_power_pJ_s": ("pJ/s", "rate", "pumps", ("membrane_slot",), None),
    "channel_availability": ("1", "level", "channels", ("channel_slot",), None),
    "pump_availability": ("1", "level", "pumps", ("membrane_slot",), None),
    "calcium_pump_cycle_rate_fmol_s": ("fmol/s", "rate", "pumps", ("membrane_slot",), _PUMP_INWARD),
    "calcium_pump_affinity_J_mol": ("J/mol", "level", "pumps", ("membrane_slot",), None),
    "calcium_metabolic_power_pJ_s": ("pJ/s", "rate", "pumps", ("membrane_slot",), None),
    "calcium_pump_availability": ("1", "level", "pumps", ("membrane_slot",), None),
}
UNITS = MappingProxyType({k: v[0] for k, v in _VIEW_TABLE.items()})
RECORD_KINDS = MappingProxyType({k: v[1] for k, v in _VIEW_TABLE.items()})
RECORD_LAYERS = MappingProxyType({k: v[2] for k, v in _VIEW_TABLE.items()})
OBSERVATION_AXES = MappingProxyType({k: v[3] for k, v in _VIEW_TABLE.items() if v[3] is not None})
ORIENTATION = MappingProxyType({k: v[4] for k, v in _VIEW_TABLE.items() if v[4] is not None})
VIEW_AXIS_SETS = MappingProxyType({})  # A kind's axis that maps to an existing view set.
# Records that are residuals of the step's own balances, each with its own tolerance, apart from
# the physical records (the run view's loop closure measure, FR-11): the field solve's charge
# residual (CHARGE_ATOL_C + CHARGE_RTOL x scale) and the floating components' current residual
# (the Newton target or the attainable floor), both held by the step, and the stage energy-rate
# balance, zero to rounding (§7.4 (m)).
RECORD_DIAGNOSTICS = ("charge_residual_C", "component_current_residual_A", "energy_balance_pJ_s")
# {increment field: its reference layout field}: a stored amount is reference + increment.
RECORD_REFERENCES = MappingProxyType(
    {
        "amount_increment": "amount_reference",
        "extracellular_amount_increment": "extracellular_amount_reference",
    }
)
_VIEW_MAPS = ("UNITS", "OBSERVATION_AXES", "RECORD_KINDS", "ORIENTATION", "RECORD_LAYERS")
_RECORD_ROLES = ("RECORD_DIAGNOSTICS", "RECORD_REFERENCES")


def view_declarations(structure):
    """The run view's declarations for a structure (D154): @3's own, then each declared kind's
    KindView entries for the fields its structure's types hold, its layers and its axis sets, its
    residual records (RECORD_DIAGNOSTICS) and its increments' references (RECORD_REFERENCES,
    where the reference is a field of the structure's layout). A structure without kinds gets the
    module's own objects."""
    kinds = _kinds(structure)
    if not kinds:
        names = (*_VIEW_MAPS, "VIEW_LAYERS", "VIEW_AXIS_SETS", *_RECORD_ROLES)
        return {name: globals()[name] for name in names}
    types = kind_types(structure)
    present = {*types.STATE_TYPE._fields, *types.OBSERVATION_FIELDS}
    merged = {name: dict(globals()[name]) for name in _VIEW_MAPS}
    layers, axis_sets = list(VIEW_LAYERS), {}
    diagnostics, references = list(RECORD_DIAGNOSTICS), dict(RECORD_REFERENCES)
    for kind in kinds:
        view = kind.view
        if view is None:
            continue
        parts = (
            view.units,
            view.observation_axes,
            view.record_kinds,
            view.orientation,
            view.record_layers,
        )
        for name, part in zip(_VIEW_MAPS, parts, strict=True):
            merged[name] |= {k: v for k, v in part.items() if k in present}
        known = {layer["id"] for layer in layers}
        layers += [MappingProxyType(dict(x)) for x in view.view_layers if x["id"] not in known]
        axis_sets |= dict(view.axis_sets)
        diagnostics += [k for k in view.record_diagnostics if k in present and k not in diagnostics]
        references |= {
            k: v
            for k, v in view.record_references.items()
            if k in present and v in types.LAYOUT_TYPE._fields
        }
    out = {name: MappingProxyType(value) for name, value in merged.items()}
    return out | dict(
        VIEW_LAYERS=tuple(layers),
        VIEW_AXIS_SETS=MappingProxyType(axis_sets),
        RECORD_DIAGNOSTICS=tuple(diagnostics),
        RECORD_REFERENCES=MappingProxyType(references),
    )


# Notes a record carries, in the model's own words (its summary's membrane_transfer_ledger).
RECORD_NOTES = MappingProxyType(
    {
        "membrane_transferred": "the passive membrane routes only. A patch's total in the "
        "material balance is the balance's own sum: this record plus channel_transferred of its "
        "populations, less each pump's per-cycle rows times its cycles (pump_cycles); the pump is "
        "a separate term, never in this record",
    }
)


def observe_history(times, history, layout, requested, spec, *, structure=None):
    from cells.definitions.surface_pump_v3_spec import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved kinetic observations require accepted times")
    controls, records = control_values(spec, requested), []
    types = kind_types(structure) if structure is not None else TODAYS_TYPES
    kinds = _kinds(structure)
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state, control = (
            types.STATE_TYPE(*(v[i] for v in history)),
            types.Control(*(v[j] for v in controls)),
        )
        w = readouts(state, control, p, xp=np, structure=structure)
        if not w.valid:
            raise NumericalError("Resolved kinetic observation domain invalid")
        v, n, r = w.field, p.active.size, w.field.rates
        read = _stage_read(state, p, kinds, xp=np)[0] if kinds else state  # Kinds' readouts.
        routed = _route(structure, kinds, read, control, p, xp=np)[0] if kinds else control
        records.append(
            (
                np.asarray(t),
                *state,
                *physical_amounts(state, p),
                v.potential_V[:n],
                v.potential_V[n:],
                r.membrane_voltage_V,
                r.junction_voltage_V,
                r.membrane_flux_fmol_s,
                r.junction_flux_fmol_s,
                r.face_flux_fmol_s,
                r.reservoir_supply_fmol_s,
                v.electrode_charge_C,
                v.electrode_current_A,
                np.atleast_1d(v.reservoir_power_pJ_s),
                np.atleast_1d(v.electrode_power_pJ_s),
                v.charge_residual_C,
                v.component_current_residual_A,
                np.atleast_1d(v.energy_balance_pJ_s),
                control.membrane,
                control.junction,
                w.channel_flux_fmol_s,
                w.channel_targets,
                w.channel_tau_s,
                w.derivative.pump_cycles,
                w.pump_affinity_J_mol,
                w.derivative.metabolic_work_pJ,
                control.channel,
                control.pump,
                w.derivative.calcium_pump_cycles,
                w.calcium_pump_affinity_J_mol,
                w.derivative.calcium_metabolic_work_pJ,
                control.calcium_pump,
                *(  # Rule (b): the kinds' readout columns follow today's.
                    column
                    for kind in kinds
                    if kind.readouts is not None
                    for column in kind.readouts(state, read, v.potential_V, routed, p, xp=np)
                ),
            )
        )
    if records:
        return types.Observations(*(np.stack(v) for v in zip(*records, strict=True)))
    sample = observe_history(
        times[:1],
        types.STATE_TYPE(*(v[:1] for v in history)),
        p,
        times[:1],
        spec,
        structure=structure,
    )
    return types.Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time, *, structure=None):
    from cells.definitions.surface_pump_v3_spec import control_values

    controls = control_values(spec, [time])
    types = kind_types(structure) if structure is not None else TODAYS_TYPES
    control = types.Control(*(v[0] for v in controls))
    p = type(layout)(*(np.asarray(v) for v in layout))
    v = field_values(
        types.STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np, structure=structure
    )
    if not v.converged:
        raise NumericalError("Resolved kinetic ensemble endpoint invalid")
    return v.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    return tissue.summarize(history, diagnostics, spec) | {
        "model": MODEL_ID,
        "field_solver": spec.execution.field_solver,
        "time_integrator": spec.execution.solver,
        "gate_integrator": "rk4" if spec.execution.solver == "rk4" else GATE_INTEGRATOR_ID,
        "state_fields": list(STATE_TYPE._fields),
        "junction_law": junction_gate.RELAXATION_LAW_ID,
        "pump_law": pump.LAW_ID,
        "calcium_pump_law": calcium_atpase.LAW_ID,
        "channel_laws": {c.id: c.kinetic_law for c in spec.model.channels},
        "membrane_transfer_ledger": "baseline passive only; channel and pump ledgers separate",
        "junction_heat_booking": spec.model.junction_heat_booking,
    }


# ------------------------------------------------------------------ declared structure (D172)
# docs/INNER_MODEL_V4_DESIGN.md §7.4: what a definition declares is structure (Python values,
# never a parameter value); every value is a layout array. registry.get_model returns one
# implementation object per structure, cached, so equal structures share the object, its
# functions and their compiled executables. Its structure-dependent functions are this module's,
# bound once to the structure (keyword `structure`), so a program traces only the declared laws'
# kernels. The module's own names keep structure=None, today's dispatch over the full catalogue,
# for callers that have not moved to the object yet (the composite's adapter until it does).


def structure(model):
    """The InnerStructure of a parsed @3 (or composite) model block, on the host."""
    codes = inner_laws.channel_codes()
    declared = sorted({c.kinetic_law for c in model.channels}, key=codes.__getitem__)
    pump_laws = {m.pump.law for m in model.membranes if m.pump is not None}
    pump_laws |= {m.calcium_pump.law for m in model.membranes if m.calcium_pump is not None}
    fuels = {
        p.metabolism.kind
        for m in model.membranes
        for p in (m.pump, m.calcium_pump)
        if p is not None
    }
    return inner_laws.InnerStructure(
        declared_channel_laws=tuple(declared),
        junction_laws=tuple(sorted({j.law for j in model.junctions})),
        pump_laws=tuple(law for law in inner_laws.PUMP_LAWS if law in pump_laws),
        fuel_kinds=tuple(sorted(fuels)),
        junction_heat_booking=model.junction_heat_booking,
        padding_fill=_closes_slots(model),
        kinds=_kind_entries(model),
        routes=_routes(model),
    )


def _kind_entries(model):
    """((kind ID, structure entry), ...) of the declared kinds, from the active registry."""
    registry = kind_registry.active()
    entries = []
    for kind_id, declaration in getattr(model, "kinds", ()):
        kind = registry.lookup(kind_id)
        entries.append((kind_id, kind.structure_entry(declaration) if kind.structure_entry else ()))
    return tuple(entries)


def _closes_slots(model):
    """Whether a composite's operators close activity masks mid-run (contract CLOSES)."""
    declared = getattr(model, "operators", ())
    if not declared:
        return False
    from cells.operators import OPERATORS

    return any(OPERATORS[d.law].CLOSES for d in declared)


def moved_rows(model):
    """Every in-step mover of the inner model, by species (§7.4 (f), answer 6), on the host.

    {species: ((mover kind, law ID, entity IDs), ...)} for the species something moves inside
    @3's step: membrane and junction routes with nonzero permeability, faces with nonzero
    diffusivity, each declared channel law's permeant ions on its populations, and the pumps'
    transported ions on their patches. Today's pumps hold their fuel as parameters, so they move
    no fuel row; a species absent from the mapping is moved by nothing in the step.
    """
    movers = {s: [] for s in model.species_ids}

    def add(species, kind, law, entities):
        if entities:
            movers[species].append((kind, law, tuple(entities)))

    for row, s in enumerate(model.species_ids):
        route = inner_laws.MEMBRANE_ROUTE_LAW_ID
        add(s, "membrane", route, [m.id for m in model.membranes if m.permeability_m_per_s[row]])
        add(s, "junction", route, [j.id for j in model.junctions if j.permeability_m_per_s[row]])
        add(
            s,
            "face",
            inner_laws.FACE_ROUTE_LAW_ID,
            [f.id for f in model.faces if f.diffusivity_m2_per_s[row]],
        )
    for law in structure(model).declared_channel_laws:
        for s in model.species_ids:
            add(
                s,
                "channel",
                law,
                [
                    c.id
                    for c in model.channels
                    if c.kinetic_law == law
                    and any(i.species_id == s and i.relative_permeability for i in c.permeant_ions)
                ],
            )
    for s in model.species_ids:
        add(s, "pump", pump.LAW_ID, [m.id for m in model.membranes if m.pump and s in m.pump.roles])
        add(
            s,
            "pump",
            calcium_atpase.LAW_ID,
            [m.id for m in model.membranes if m.calcium_pump and m.calcium_pump.role == s],
        )
    # §7.4 (k): each declared kind's moved rows, (species, node ID) pairs, or (species, node ID,
    # law ID) triples, grouped as (kind ID, law ID, (node IDs, ...)); the registry places each
    # node from the model's node lists (the operators stream's moved_in_step).
    registry = kind_registry.active()
    for kind_id, declaration in getattr(model, "kinds", ()):
        kind = registry.lookup(kind_id)
        if kind.moved_rows is None:
            continue
        grouped = {}
        for entry in kind.moved_rows(declaration):
            species, node, law = (*entry, kind_id) if len(entry) == 2 else entry
            grouped.setdefault((species, law), []).append(node)
        for (species, law), nodes in grouped.items():
            add(species, kind_id, law, nodes)
    return MappingProxyType({s: tuple(v) for s, v in movers.items() if v})


class KindTypes(NamedTuple):
    """The types of one set of declared kinds (§7.4 (j), schema A)."""

    STATE_AXES: object
    STATE_TYPE: object
    LAYOUT_TYPE: object
    FLOOR_LAYOUT_TYPE: object
    Control: object
    OBSERVATION_FIELDS: tuple
    Observations: object


TODAYS_TYPES = KindTypes(
    STATE_AXES,
    STATE_TYPE,
    LAYOUT_TYPE,
    FLOOR_LAYOUT_TYPE,
    Control,
    OBSERVATION_FIELDS,
    Observations,
)


@cache
def _kind_types(fields, registry):
    """fields: ((kind ID, the bound kind's KindFields), ...) in canonical order. Classes are cached
    by field set (§7.4 (j); (n) 5): structures whose kinds carry the same fields share them, and a
    kind bound to fields other than its static ones (a declaration-dependent variant) names its
    extra fields in the classes' deterministic names."""
    if not fields:
        return TODAYS_TYPES

    def label(kind_id, own):
        static = registry.lookup(kind_id)
        known = {*static.state_fields, *static.layout_fields, *static.control_fields}
        known |= set(static.readout_columns)
        names = (
            *(name for name, _ in own.state_axes),
            *own.layout_fields,
            *own.control_fields,
            *own.readout_columns,
        )
        extra = "".join("_" + name for name in names if name not in known)
        return "_" + re.sub(r"\W", "_", kind_id) + extra

    suffix = "".join(label(kind_id, own) for kind_id, own in fields)  # Deterministic.
    axes = dict(STATE_AXES)
    for kind_id, own in fields:
        for name, name_axes in own.state_axes:  # Not `field`: the field-solver module's name.
            if name in axes:
                raise ValueError(f"Kind {kind_id}'s state field {name} is already declared")
            axes[name] = list(name_axes)
    state = NamedTuple("SurfacePumpChannelState" + suffix, [(k, object) for k in axes])
    layout_extra = [name for _, own in fields for name in own.layout_fields]
    layout = NamedTuple(
        "SurfacePumpChannelLayout" + suffix,
        [(k, object) for k in (*LAYOUT_TYPE._fields, *layout_extra)],
    )
    floor = NamedTuple(
        "SurfacePumpChannelFloorLayout" + suffix,
        [(k, object) for k in (*FLOOR_LAYOUT_TYPE._fields, *layout_extra)],
    )
    control = NamedTuple(
        "SurfacePumpChannelControl" + suffix,
        [
            (k, object)
            for k in (*Control._fields, *(f for _, own in fields for f in own.control_fields))
        ],
    )
    # Rule (b): a kind's state fields are observation columns right after today's state fields
    # (the windowed runner rebuilds states from observations by name); its readouts follow
    # today's readouts.
    today_state = len(STATE_TYPE._fields) + 1
    columns = (
        *OBSERVATION_FIELDS[:today_state],
        *(name for _, own in fields for name, _ in own.state_axes),
        *OBSERVATION_FIELDS[today_state:],
        *(column for _, own in fields for column in own.readout_columns),
    )
    observations = make_dataclass(
        "SurfacePumpChannelObservations" + suffix, [(k, np.ndarray) for k in columns], frozen=True
    )
    return KindTypes(axes, state, layout, floor, control, columns, observations)


def kind_types(structure):
    """The structure's types: today's own objects when it declares no kind (§7.4 (j), schema A),
    else classes cached by its kinds' fields, each kind bound to its structure entry ((n) 5), in
    canonical order."""
    registry = kind_registry.active()
    fields = []
    for kind_id, entry in structure.kinds:
        kind = kind_registry.bound(registry.lookup(kind_id), entry)
        own = kind_registry.KindFields(
            kind.state_axes, kind.layout_fields, kind.control_fields, kind.readout_columns
        )
        fields.append((kind_id, own))
    return _kind_types(tuple(fields), registry)


class InnerImplementation:
    """resolved_pump_tissue@3 for one declared structure (§7.4 (c)); see implementation().

    It has every public name of this module, with the same signature: structure-free names
    (types, constants, parameters, physical_amounts, projection, rebind, ...) are the module's
    own objects, and the step, readout, domain, check and observation functions are taken from
    it by every consumer. New names: structure, structure_key, declared_channel_laws,
    law_columns, gate_rows, junction_kinetics.
    """

    def __init__(self, structure):
        self.structure = structure
        self.structure_key = (MODEL_ID, structure)
        self.law_columns = MappingProxyType(
            {law: column for column, law in enumerate(structure.declared_channel_laws)}
        )
        # Bound once, so jit's static arguments and compile_window's key see stable objects.
        for name in STRUCTURED_FUNCTIONS:
            setattr(self, name, partial(getattr(_MODULE, name), structure=structure))
        self.domain_valid.with_control = self.control_domain_valid
        self.batch_signature = structured_batch_signature
        for name, value in kind_types(structure)._asdict().items():  # Schema A (§7.4 (j)).
            setattr(self, name, value)
        for name, value in vars(ledger_lists(structure)).items():  # The ledger protocol, (p).
            setattr(self, name, value)
        if structure.kinds:  # The run view's declarations, the kinds' folded in (D154).
            for name, value in view_declarations(structure).items():
                setattr(self, name, value)

    def view_sets(self, spec):
        """{axis: view set} of the declared kinds' own axes (their view_sets hooks), for the run
        view (D154): {"id", "ids", "roles", per-entity facts}; none without kinds."""
        out, declarations = {}, dict(getattr(spec.model, "kinds", ()))
        for kind in _kinds(self.structure):
            if kind.view_sets is not None:
                out |= kind.view_sets(spec, declarations[kind_registry.qualified(kind.kind_id)])
        return out

    def __getattr__(self, name):
        # Only reached for names the object does not define: this module's own.
        if name.startswith("__"):
            raise AttributeError(name)
        try:
            return getattr(_MODULE, name)
        except AttributeError:
            raise AttributeError(
                f"resolved_pump_tissue@3 implementation has no attribute {name!r}"
            ) from None

    def __dir__(self):
        return sorted(set(dir(_MODULE)) | set(vars(self)) | set(dir(type(self))))

    def __repr__(self):
        return f"<{MODEL_ID} implementation for {self.structure!r}>"

    @property
    def declared_channel_laws(self):
        return self.structure.declared_channel_laws

    @property
    def gate_rows(self):
        return self.structure.gate_rows

    def junction_kinetics(self, voltage, p, *, xp=jnp):
        """The declared junction law's kinetics at junction voltages (junction_gate.Rates)."""
        return junction_gate.kinetics(voltage, kinetic.junction_parameters(p), xp=xp)


# The module's functions that read the declared structure; the object binds each to its own.
STRUCTURED_FUNCTIONS = (
    "initial_values",
    "balances",
    "device_balances",
    "channel_magnitudes",
    "channel_kinetics",
    "channel_opening",
    "channel_rates",
    "readouts",
    "field_values",
    "rhs",
    "domain_valid",
    "control_domain_valid",
    "explicit_rates",
    "potential_kinetics",
    "imex_step",
    "checked_step",
    "membrane_rate",
    "material_rate",
    "check_definition",
    "check_values",
    "device_checks",
    "observe_history",
    "ensemble_voltage",
)


@cache
def _bound_checks(structure):
    """rhs and domain_valid bound to a structure, for the RK4 step and the row checks."""
    domain = partial(domain_valid, structure=structure)
    domain.with_control = partial(control_domain_valid, structure=structure)
    return SimpleNamespace(rhs=partial(rhs, structure=structure), domain_valid=domain)


def structured_batch_signature(model):
    """The batch signature with the declared structure: different law sets never share a batch."""
    return (*batch_signature(model), structure(model))


def implementation(structure):
    """The one InnerImplementation of a structure (cached: equal structures share it). A
    structure that declares kinds is also keyed on the active kind registry, whose kinds its
    types are built from; one that declares none shares its object across registries, so a
    registered but undeclared kind changes nothing, the compile key included."""
    return _implementation(structure, kind_registry.active() if structure.kinds else None)


@cache
def _implementation(structure, registry):
    return InnerImplementation(structure)


def model_for(model):
    """registry.get_model's answer for a parsed @3 model block."""
    return implementation(structure(model))


_MODULE = sys.modules[__name__]
