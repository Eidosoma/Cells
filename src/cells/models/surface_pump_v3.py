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
from contextlib import contextmanager
from dataclasses import make_dataclass, replace
from functools import cache, cached_property, partial
from types import MappingProxyType, SimpleNamespace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError
from cells.definitions.surface_pump_v3_spec import (
    EXACT_FREE_ENERGY_HEAT,
    GATED_CODES,
    LAW_CODES,
    MODEL_ID,
    NAV1P2_LAW_ID,
    SERIES_GATE_LAW_ID,
    TRAPEZOID_JUNCTION_HEAT,
    Control,
    channel_factors,
    channel_laws,
    law_codes,
    projection,
)
from cells.execution.errors import NumericalError
from cells.laws.channels import sodium_channels, voltage_gates
from cells.laws.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R
from cells.laws.junctions import junction_gate
from cells.laws.junctions import junction_series_gates as series_gates
from cells.laws.junctions.selective import selective_flux
from cells.laws.pumps import calcium_atpase
from cells.laws.pumps import kinetic_pump as pump
from cells.laws.pumps import kinetic_pump_binding as pumps
from cells.laws.reactions import rapid_binding as binding_law
from cells.laws.routes import logmean_electrodiffusion_forms as forms_law
from cells.laws.routes import passive_permeation as exact_kernel
from cells.laws.routes import patch_electrodiffusion as constant_field_route
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
from cells.registry import laws as law_registry

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
# N2 (D235) adds no layout field: its static switch is its tableau's operator time, a vector
# (implicit_conductances), so every other world's layout is today's.
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
SPARSE_LAYOUT_TYPE = NamedTuple(  # Declared field solver surface_field.SPARSE_SOLVER_ID.
    "SurfacePumpChannelSparseLayout",
    [
        (k, object)
        for k in (
            *(k for k in second.SPARSE_LAYOUT_TYPE._fields if k != "channel_species"),
            *CHANNEL_LAYOUT_FIELDS,
        )
    ],
)
# The forms faces (logmean_electrodiffusion_forms@1; MITOCHONDRIA_DESIGN's face note, its build
# plan's item 1): their own entity set, with their own state and layout fields, present only in a
# structure that declares forms faces (InnerStructure.forms_faces, _kind_types), so no other
# world's types, layouts or programs carry anything of them (D148 case 2). A mover is a row moving
# as itself or a binder's form (laws/routes/logmean_electrodiffusion_forms.Movers).
FORMS_STATE_AXES = {
    "forms_face_transferred": ["face_mover", "forms_face_slot"],  # Per mover, sender -> receiver.
    "forms_face_dissipated_energy_pJ": ["forms_face_slot"],
}
FORMS_LAYOUT_FIELDS = (
    "forms_face_active",  # [forms face]
    "forms_face_sender",  # [forms face] outside node
    "forms_face_receiver",  # [forms face] outside node
    "forms_face_factor",  # [mover, forms face] D A / L (m^3/s)
    "forms_face_valence",  # [mover, 1]
    "forms_face_stoichiometry",  # [mover, species]
    "forms_face_row",  # [mover] the species row a row mover reads (-1 for a binder form)
    "forms_face_binder",  # [mover] a binder form's binder in the general closure (-1 for a row)
    "forms_face_form",  # [mover] a binder form's index among its binder's forms (-1 for a row)
    "forms_face_form_movers",  # [form mover] the binder forms' movers; its size is static
    "forms_face_incidence",  # [floating component, forms face] (field.bind's face_incidence's form)
)
FORMS_STRUCTURE_REFUSAL = (
    f"{forms_law.LAW_ID} runs in @3 through its structure's implementation (registry.get_model), "
    "which holds the forms faces' own entity set; a path without that structure would drop them, "
    "so it refuses them (version 1)"
)
FORMS_PROJECTIVE_REFUSAL = (
    f"{forms_law.LAW_ID} runs on the fine engine in version 1: execution.projective's settling "
    "test reads no forms face"
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
    """Stored values per accepted step plus a margin (surface_pump.working_size): @2's, the
    channel populations', the declared kinds' (kind_row_values) and a series world's junction
    gates (FR-30), each with the margin 2."""
    x, s = spec.execution, len(spec.model.species_ids)
    series = (
        series_gates.GATE_COUNT * x.edge_capacity if declares_series_junctions(spec.model) else 0
    )
    forms = 0
    if getattr(spec.model, "forms_faces", ()):  # Each mover's transfer and each face's heat.
        faces = len(spec.model.forms_faces)
        forms = faces * (forms_law.mover_count(spec.model, forms_of_binders(spec.model)) + 1)
    return (
        second.working_size(projection(spec))
        + 2 * (2 + 2 * s) * x.channel_capacity
        + 2 * kind_row_values(spec)
        + 2 * series
        + 2 * forms
    )


def kind_row_values(spec):
    """The values the declared kinds add to every saved row (the runner stacks each state field
    at every accepted step), read from the row's own structure rather than a formula kept per
    kind: each kind state field (its bound state_axes, which the structure's state type holds)
    sized by its axes, @3's shared axes from the execution's capacities and the species, a kind's
    own axes from its view sets' IDs (view_sets, the run view's one list of its entities). So
    every kind's saved arrays count; an axis with no size is refused, never left uncounted, and
    check_definition refuses a count below the bound state's (the @3 owner's review; the lead's
    ruling: an overcount is the safe direction, for memory), so the estimate never undercounts a
    definition it admits. 0 without kinds, so a kind-free world's estimate is today's (the third
    review's finding 3)."""
    kinds = getattr(spec.model, "kinds", ())
    if not kinds:
        return 0
    x = spec.execution
    shared = {
        "species": len(spec.model.species_ids),
        "node": x.capacity + x.extracellular_capacity,  # Cells, then outside nodes.
        "cell_slot": x.capacity,
        "extracellular_slot": x.extracellular_capacity,
        "membrane_slot": x.membrane_capacity,
        "edge_slot": x.edge_capacity,
        "face_slot": x.face_capacity,
        "channel_slot": x.channel_capacity,
    }
    registry, declarations, total = kind_registry.active(), dict(kinds), 0
    for kind_id, entry in structure(spec.model).kinds:
        kind = kind_registry.bound(registry.lookup(kind_id), entry)
        own = {} if kind.view_sets is None else kind.view_sets(spec, declarations[kind_id])
        sizes = shared | {axis: len(entities["ids"]) for axis, entities in own.items()}
        for name, axes in kind.state_axes:
            unsized = [axis for axis in axes if axis not in sizes]
            if unsized:
                raise ConfigError(
                    f"Kind {kind_id}'s state field {name} has axes {unsized} that the trace "
                    "estimate cannot size: a kind's own axis is sized by its view set"
                )
            values = 1
            for axis in axes:
                values *= sizes[axis]
            total += values
    return total


def initial_values(spec, *, structure=None):
    series = series_junctions(structure)
    if structure is None and declares_series_junctions(spec.model):
        raise ConfigError(SERIES_STRUCTURE_REFUSAL)  # Fail closed: no one-gate path runs it.
    declared_forms = getattr(spec.model, "forms_faces", ())
    if bool(declared_forms) != forms_faces_declared(structure):
        raise ConfigError(FORMS_STRUCTURE_REFUSAL)  # Fail closed: a path without them drops them.
    with forms_return_paths(spec.model):  # Left before anything else runs.
        state, layout = _todays_initial_values(spec)
    if (structure is None or not structure.kinds) and not series and not declared_forms:
        return state, layout
    # Schema A (§7.4 (j), (k)): each declared kind adds its state and layout fields, by name, in
    # canonical order, into its structure's types.
    types = kind_types(structure)
    registry = kind_registry.active()
    declarations = dict(spec.model.kinds)
    fields, entries = state._asdict(), layout._asdict()
    if series:  # FR-30 (D262): the gates' factors and parameters, [series_gate, ..., edge_slot].
        fields[SERIES_GATES], entries[SERIES_PARAMETERS] = series_initial_values(spec)
    sizes = kind_registry.axis_sizes(STATE_AXES, fields)  # @3's axes, for the kinds' arrays.
    for kind_id, entry in structure.kinds:  # Each bound to its entry's fields (§7.4 (n) 5).
        kind = kind_registry.bound(registry.lookup(kind_id), entry)
        own_state, own_layout = kind.initial(spec, declarations[kind_id], entries)
        kind_registry.refuse_foreign_writes(
            kind, "initial values", own_state, kind.state_fields, "state"
        )
        kind_registry.refuse_foreign_writes(
            kind, "initial values", own_layout, kind.layout_fields, "layout"
        )
        kind_registry.refuse_misshapen(kind, "initial values", own_state, own_layout, sizes)
        fields |= own_state
        entries |= own_layout
    if declared_forms:  # The forms faces' own entity set, after the kinds (their closure's arrays).
        own_state, own_layout = forms_initial_values(spec, entries)
        fields |= own_state
        entries |= own_layout
    kind = (
        types.FLOOR_LAYOUT_TYPE
        if "field_current_floor" in entries
        else types.SPARSE_LAYOUT_TYPE
        if "field_capacitor_values" in entries
        else types.LAYOUT_TYPE
    )
    return types.STATE_TYPE(**fields), kind(**entries)


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
    if (imex.operator_times(v["imex_operator_time"])[1] is not None) != (
        spec.execution.solver in imex.IMPLICIT_CONDUCTANCE_IDS
    ):  # N2's switch is its tableau's vector operator time; only N2's IDs declare one.
        raise ConfigError(
            f"{spec.execution.solver}: the layout's operator time does not match its solver "
            "(a vector operator time is N2's alone, one entry per frozen block)"
        )
    gate, mids = np.zeros((2, nc)), [p.id for p in m.membranes]
    codes = law_codes()  # The registry's codes (today's five keep theirs, 0-4).
    for i, c in enumerate(m.channels):
        v["channel_membranes"][i] = mids.index(c.membrane_id)
        v["channel_permeability"][i] = c.max_permeability_m_per_s
        v["channel_abundance"][i] = c.abundance
        v["channel_laws"][i] = codes[c.kinetic_law]
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
    kind = (
        FLOOR_LAYOUT_TYPE
        if "field_current_floor" in v
        else SPARSE_LAYOUT_TYPE
        if "field_capacitor_values" in v
        else LAYOUT_TYPE
    )
    return STATE_TYPE(**(state._asdict() | channel)), kind(**v)


@contextmanager
def forms_return_paths(model):
    """field.bind's return paths for the model's forms faces, around one base binding: bind (their
    one reader) counts each forms face as a charged path between its two outside nodes, so a
    floating component whose only path to a clamp is a forms face binds. Nothing is set for a model
    without forms faces, and the context is left with the block."""
    faces = getattr(model, "forms_faces", ())
    if not faces:
        yield
        return
    oids = [o.id for o in model.extracellular]
    with field.return_paths([(oids.index(f.sender), oids.index(f.receiver)) for f in faces]):
        yield


def forms_of_binders(model):
    """{binder row: its forms, base first ((form ID, ((ligand, n), ...), mu°/RT), ...)} from the
    species registry (species_registry.forms_of), for each binder some forms face moves as its
    forms; {} without one. The law module takes them as data (laws/ import the registry only
    through cells.modules)."""
    rows = forms_law.form_binders(model)
    if not rows:
        return {}
    from cells.registry import species_registry  # Host side; the registry imports this module.

    spec = SimpleNamespace(model=model)
    return {row: species_registry.forms_of(spec, row) for row in rows}


def forms_faces_declared(structure):
    """Whether the structure declares forms faces (InnerStructure.forms_faces; static)."""
    return structure is not None and bool(structure.forms_faces)


def _has_forms(p):
    """Static: the layout of a world that declares forms faces (its type holds their fields)."""
    return "forms_face_active" in type(p)._fields


def forms_initial_values(spec, layout):
    """(state fields, layout fields) of the forms faces (FORMS_STATE_AXES, FORMS_LAYOUT_FIELDS),
    from the definition and the layout's fields (a mapping: its outside nodes and floating basis,
    and the general closure's arrays where a binder moves as its forms). One slot per declared
    forms face; the movers are the law's table (forms_law.movers)."""
    m = spec.model
    oids = [o.id for o in m.extracellular]
    network = None
    if "binding_rows" in layout:  # The general closure's arrays (its kind's initial values).
        network = (
            np.asarray(layout["binding_rows"]),
            np.asarray(layout["binding_counts"]),
            np.asarray(layout["binding_present"]),
            np.asarray(layout["binding_held"]).shape[0],
        )
    table = forms_law.movers(m, network, forms_of_binders(m))
    charge = np.asarray(table.stoichiometry) @ np.asarray(m.valence, dtype=float)
    if not np.array_equal(charge, np.asarray(table.valence, dtype=float)):  # Exact: integers.
        bad = table.names[int(np.flatnonzero(charge != np.asarray(table.valence))[0])]
        raise ConfigError(
            f"Forms face mover {bad} changes its rows' charge by other than its valence: a bound "
            "form carries its ligands, and the field books the rows' charge"
        )
    faces = len(m.forms_faces)
    sender = np.asarray([oids.index(f.sender) for f in m.forms_faces], dtype=np.int64)
    receiver = np.asarray([oids.index(f.receiver) for f in m.forms_faces], dtype=np.int64)
    n = np.asarray(layout["active"]).size
    basis = np.asarray(layout["field_floating_basis"])
    own = dict(
        forms_face_active=np.ones(faces, dtype=bool),
        forms_face_sender=sender,
        forms_face_receiver=receiver,
        forms_face_factor=forms_law.face_factors(m, table),
        forms_face_valence=np.asarray(table.valence, dtype=float)[:, None],
        forms_face_stoichiometry=np.asarray(table.stoichiometry, dtype=float),
        forms_face_row=np.asarray(table.row, dtype=np.int64),
        forms_face_binder=np.asarray(table.binder, dtype=np.int64),
        forms_face_form=np.asarray(table.form, dtype=np.int64),
        forms_face_form_movers=np.flatnonzero(np.asarray(table.binder) >= 0).astype(np.int64),
        forms_face_incidence=(basis[n + sender] - basis[n + receiver]).T,
    )
    state = dict(
        forms_face_transferred=np.zeros((len(table.names), faces)),
        forms_face_dissipated_energy_pJ=np.zeros(faces),
    )
    return state, own


def forms_faces_of(p):
    """The layout's forms faces as numerics/surface_transport.FormsFaces."""
    return surface.FormsFaces(
        p.forms_face_active,
        p.forms_face_sender,
        p.forms_face_receiver,
        p.forms_face_factor,
        p.forms_face_valence,
        p.forms_face_stoichiometry,
    )


def forms_ends(co, p, *, xp=jnp):
    """(left, right) [mover, forms face]: each mover's concentration (mM) at each forms face's
    sender and receiver, from the outside nodes' concentrations co [species, outside node] (the
    stage read's, or the predictor's at the predicted totals): a row mover reads its row (a ligand
    row's free amount at a closure node, its stored amount elsewhere); a binder's form is the
    closure's c_f = c_base beta_f prod x_L^n_L (rapid_binding.forms_from_free, the binding
    owner's export) at the read's free ligands and free base form. Static: without a binder form
    (the size of forms_face_form_movers) only the rows are read."""
    c = co[xp.maximum(p.forms_face_row, 0)]
    if p.forms_face_form_movers.shape[0]:
        nl, rows = p.binding_held.shape[0], p.binding_rows
        forms = binding_law.forms_from_free(
            xp.log(co[rows[:nl]]), co[rows[nl:]], p.binding_log_beta, p.binding_counts,
            p.binding_present, xp=xp,
        )  # fmt: skip
        gathered = forms[xp.maximum(p.forms_face_binder, 0), xp.maximum(p.forms_face_form, 0)]
        c = xp.where((p.forms_face_binder >= 0)[:, None], gathered, c)
    return c[:, p.forms_face_sender], c[:, p.forms_face_receiver]


def forms_field(co, p, *, xp=jnp):
    """field.solve's forms argument at outside concentrations co (the stage read's)."""
    left, right = forms_ends(co, p, xp=xp)
    return field.FormsField(forms_faces_of(p), left, right, p.forms_face_incidence)


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


def channel_current_A(flux, p, *, xp=np):
    """FR-34: each channel population's electric current [..., channel] (A, outward-positive:
    positive charge from its patch's cell to that patch's outside node, e sum_s z_s J_s, the
    convention of membrane_current_A and of the kinds' passive_current_A) from its outward flux
    [..., species, channel] (fmol/s): the recorded channel_flux_fmol_s at observed rows, one row or
    a stack of them, or clamped_channel_flux's. Host side by default; it records nothing."""
    charge = xp.moveaxis(p.valence * flux, -2, 0)  # [species, ..., channel], the fold's axis first.
    return CHARGE_PER_FMOL * species_sum(charge, xp=xp)


def clamped_channel_flux(state, control, p, voltages_V, *, xp=np, structure=None):
    """FR-34, current at a declared voltage: each channel population's outward flux
    [species, channel] (fmol/s, the sign of channel_flux_fmol_s) and its current [channel] (A,
    outward-positive, channel_current_A) at the patch voltages phi_in - phi_out given [membrane]
    (V; a scalar applies to every patch), at a state and its controls.

    It is readouts' own path to the channel kernel: the kinds' stage read and the routing door where
    the structure declares them, the read's concentrations, the state's gates and the routed
    availabilities; then channel_rates itself, with the field's membrane voltage replaced by the one
    given. The gates are the state's, not their values at the declared voltage, so this is the
    population's instantaneous current there. Pure: nothing calls it and it records nothing, so no
    program or record changes (crossrev).

    The controls are the ones @3 receives: in a composite, the composite's control view
    (control_view(control, state, p), with the operators' factors and writes, as held_schedules
    holds them for its observations), never the composite's stored controls, which leave an
    operator's factor out (D265, finding 1)."""
    kinds = _kinds(structure)
    read = _stage_read(state, p, kinds, xp=xp)[0] if kinds else state
    if kinds and structure.routes:  # §7.4 (n): the routing door, after the read (static).
        control = _route(structure, kinds, read, control, p, xp=xp)[0]
    ci, co = physical_amounts(read, p)
    ci, co = (
        xp.where(p.active, ci / p.volume, 1.0),
        xp.where(p.outside_active, co / p.extracellular_volume, 1.0),
    )
    voltage = xp.broadcast_to(xp.asarray(voltages_V, dtype=float), p.membrane_area.shape)
    flux = channel_rates(
        state.channel_gate,
        ci,
        co,
        voltage,
        xp.zeros_like(p.membrane_permeability),  # No heat is asked for.
        control.channel,
        p,
        xp=xp,
        structure=structure,
    )[0]
    return flux, channel_current_A(flux, p, xp=xp)


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


def series_kinetics(voltage, p, structure, *, xp=jnp):
    """FR-30: each junction_series_gates@1 gate's Rates at the junction voltages [edge], in GATES
    order (the law's own kinetics, with the layout's parameters); a padded edge's relaxation is 1,
    so no update divides by its zero rates (its gates are held)."""
    kinds = structure.junction_series_kinds
    rates = series_gates.kinetics(voltage, series_parameters(p, kinds), kinds=kinds, xp=xp)
    return tuple(
        r._replace(relaxation_per_s=xp.where(p.junction_active, r.relaxation_per_s, 1.0))
        for r in rates
    )


def series_junction_rates(state, junction_voltage, p, structure, *, xp=jnp):
    """FR-30 (S2): (junction_gate's rate [edge], each gate's [series_gate, edge]), 0 on padded
    edges: each gate's own rhs, and the conductance's the product's (the chain rule). The step
    never integrates junction_gate: it sets it to the gates' product at every stage."""
    kinds = structure.junction_series_kinds
    gates = getattr(state, SERIES_GATES)
    each = series_gates.rhs(
        tuple(gates[k] for k in range(len(kinds))),
        junction_voltage,
        series_parameters(p, kinds),
        kinds=kinds,
        xp=xp,
    )
    total = xp.zeros_like(state.junction_gate)
    for k, rate in enumerate(each):
        others = xp.ones_like(state.junction_gate)
        for j in range(len(kinds)):
            others = others if j == k else others * gates[j]
        total = total + others * rate
    each = xp.stack([xp.where(p.junction_active, rate, 0.0) for rate in each])
    return xp.where(p.junction_active, total, 0.0), each


def series_conductance(gates, p, *, xp=jnp):
    """FR-30 (S2): each junction's conductance factor [edge], its gates' product; 0 padded."""
    product = series_gates.conductance(tuple(gates[k] for k in range(gates.shape[0])), xp=xp)
    return xp.where(p.junction_active, product, 0.0)


def series_stage(stage, start, p, *, xp=jnp):
    """FR-30 (S2), a tableau stage: its junction_gate set to its gates' product, as the tableau
    moved them from the step's start (`start`, for the order test's planted stale product)."""
    del start
    return with_series_conductance(stage, p, xp=xp)


def with_series_conductance(state, p, *, xp=jnp):
    """state with junction_gate set to its gates' product (S2: computed, never integrated)."""
    return state._replace(junction_gate=series_conductance(getattr(state, SERIES_GATES), p, xp=xp))


def series_junction_domain(state, junction_voltage, availability, p, structure, *, xp=jnp):
    """FR-30: every active junction on its law's domain, gate by gate (the law's domain_valid)."""
    kinds = structure.junction_series_kinds
    gates = getattr(state, SERIES_GATES)
    ok = series_gates.domain_valid(
        tuple(gates[k] for k in range(len(kinds))),
        junction_voltage,
        series_parameters(p, kinds),
        availability,
        kinds=kinds,
        xp=xp,
    )
    return xp.all(xp.where(p.junction_active, ok, True))


def series_rate_bound(spec):
    """FR-30: a bound (1/s) on a series world's junction gates' relaxation rates over the
    voltage domain, for the tableau's junction-gate step bound (N2 lifts it): each gate's α + β is
    convex in its exponent, so its largest value lies at |V| = 0 or the domain's edge. A gate
    whose residual is 1 is pinned open and sets none."""
    rates = [0.0]
    edges = (0.0, series_gates.MAX_ABS_VOLTAGE_V)
    for junction in spec.model.junctions:
        for gate in junction.gates:
            values = series_gate_parameters_of(gate)
            if series_gates.residual_of(gate.kind, values) >= 1.0:
                continue
            for v in edges:
                rate = series_gates.gate_kinetics(gate.kind, np.asarray(v), values, xp=np)
                rates.append(float(rate.relaxation_per_s))
    return max(rates)


def series_gate_parameters_of(gate):
    """A parsed SeriesGate's parameters as its kind's type (host values)."""
    return series_parameter_type(gate.kind)(*gate.parameters)


def host_gated_pumps(p, structure, *, xp=jnp):
    """B1 (docs/CORE_SEAMS_DESIGN.md §4.2, §4.5 Q1): the layout @3's pump laws see, each pump idle
    where its host is closed.

    Where the structure declares a closer (padding_fill) beside a pump law, each Na/K and Ca²⁺
    pump's presence is and-ed with its patch's activity through the host table: the view's, so a
    pump on a patch a closer has closed reads as a padded slot's (neutral inputs inside its domain;
    exact zeros for its cycles, heat, work and affinity) at every stage, on the host and the
    device. Its state (cycles and booked energy, history) is untouched. Static: in every other
    structure the layout is returned as it is, so closer-free and pump-free worlds keep their
    programs; no world of G1's or crossrev's declares both (18 November 2026)."""
    if structure is None or not (structure.padding_fill and structure.pump_laws):
        return p
    patches = host_table(p, xp=xp).active[: p.membrane_active.size]
    return p._replace(
        pump_present=p.pump_present & patches,
        calcium_pump_present=p.calcium_pump_present & patches,
    )


# Q2, the presence gate (docs/CORE_SEAMS_DESIGN.md §18 at 931b6606), in the form of B1's pump gate:
# where a closer is declared, each kind's entity is absent where its host is closed. @3's slot axes
# that are hosts themselves, by the host kind they index (kind_registry.AXIS_HOST_KINDS reversed).
SLOT_AXIS_HOSTS = MappingProxyType(
    {axis: host for host, axis in kind_registry.AXIS_HOST_KINDS.items()}
)


def _host_activity(host_kind, p, *, xp):
    """[host] one host kind's activity: cells' and outside nodes' masks, and patches' and
    junctions' through the host table (patches first, then junctions)."""
    if host_kind == "cell":
        return p.active
    if host_kind == "outside_node":
        return p.outside_active
    hosts, m = host_table(p, xp=xp).active, p.membrane_active.size
    return hosts[:m] if host_kind == "patch" else hosts[m:]


def _channel_activity(p, *, xp):
    """[channel slot] each population's activity: its own slot's and its patch's, as a
    composite's close() closes a population on a closed patch."""
    return p.channel_active & _host_activity("patch", p, xp=xp)[p.channel_membranes]


def _face_activity(p, *, xp):
    """[face slot] each face's activity: its own slot's and both its outside nodes', as close()
    closes a face at a closed node."""
    nodes = _host_activity("outside_node", p, xp=xp)
    return p.face_active & nodes[p.face_sender] & nodes[p.face_receiver]


# Q2's hosts for @3's slot axes that index no host kind (the lead's ruling of 19 November 2026,
# the operators owner's finding: a planted kind's channel_slot presence met the gate as a
# KeyError): channel populations and faces, each active where its slot and its hosts are.
SLOT_ACTIVITY = MappingProxyType({"channel_slot": _channel_activity, "face_slot": _face_activity})
# Every @3 slot axis whose entities the presence gate closes: one list for the gate and for the
# composite's lifecycle check of the axes it can host.
PRESENCE_SLOT_AXES = (*SLOT_AXIS_HOSTS, *SLOT_ACTIVITY)


def entity_activity(kind, axis, p, *, xp=jnp):
    """[entity] each of a kind's entities' host activity on one of its entity axes: an @3 slot
    axis that indexes a host kind is its own host (SLOT_AXIS_HOSTS); a channel population or a face
    is active where its slot and its hosts are (SLOT_ACTIVITY); an own axis names its host kind and
    the layout field of each entity's host index (kind.axis_hosts, AxisHost(kind, index))."""
    if axis in SLOT_AXIS_HOSTS:
        return _host_activity(SLOT_AXIS_HOSTS[axis], p, xp=xp)
    if axis in SLOT_ACTIVITY:
        return SLOT_ACTIVITY[axis](p, xp=xp)
    host = kind.axis_hosts[axis]
    return _host_activity(host.kind, p, xp=xp)[getattr(p, host.index)]


def presence_gated(p, structure, *, xp=jnp):
    """Q2 (CORE_SEAMS §18 at 931b6606): the layout the declared kinds' rates, readouts, stage
    checks and stage terms see, each entity absent where its host is closed.

    Where the structure declares a closer (padding_fill) beside declared kinds, each presence field
    a bound kind declares (kind_registry.presence_fields, F's contract: one or more bool
    masks per entity axis, the lead's ruling (2)) is and-ed with its entities' host activity through
    axis_hosts and the host table, on the host and the device. Kinds already give exact zeros where
    an entity is absent, which the binding check holds them to (_check_presence), so kind code is
    unchanged. The kinds' state, stage reads, bookings and ledger terms see the layout as it is, so
    a closed entity's history keeps counting. Static: in every other structure the layout is
    returned as it is, so closer-free worlds keep their programs."""
    if structure is None or not (structure.padding_fill and structure.kinds):
        return p
    gated = {}
    for kind in _kinds(structure):
        for axis, names in kind_registry.presence_fields(kind).items():
            activity = entity_activity(kind, axis, p, xp=xp)
            for name in names:
                mask = getattr(p, name)
                if mask.shape[-1]:  # Static: an empty mask (an undeclared law's) stays empty.
                    gated[name] = mask & activity
    return p._replace(**gated) if gated else p


KindRates = kind_registry.KindRates  # The kind contract's (§8.5 of docs/CORE_SEAMS_DESIGN.md).
LabelView = kind_registry.LabelView  # The kind contract's too: FR-42's end of a step.
OWN_SINK = kind_registry.qualified(MODEL_ID)  # @3 as the sink of its channel field (B1's door).
# FR-34's record of the effective availability: recorded only where the door routes into @3's
# channels (routes_into_channels), the one place it differs from channel_availability.
EFFECTIVE_AVAILABILITY = "channel_effective_availability"


def routes_into_channels(structure):
    """Whether the structure routes factors into @3's own channel slots (B1's door; static)."""
    return structure is not None and any(sink == OWN_SINK for sink, *_ in structure.routes)


# FR-30 (D262): junction_series_gates@1's state and layout fields, present only where the
# structure's junctions take that law (series_junctions); junction_gate then holds the
# junction's conductance, the product of its gates' factors (S2).
SERIES_GATES = "junction_series_gates"  # [series_gate, edge_slot]: each gate's factor c in [r, 1].
SERIES_GATES_AXES = ("series_gate", "edge_slot")
SERIES_PARAMETERS = "junction_series_parameters"  # [series_gate, series_parameter, edge_slot].
SERIES_PARAMETER_SLOTS = max(
    len(junction_gate.Parameters._fields), len(series_gates.BoltzmannEyring._fields)
)


def series_junctions(structure):
    """Whether the structure's junctions take junction_series_gates@1 (static)."""
    return structure is not None and bool(structure.junction_series_kinds)


def declares_series_junctions(model):
    """Whether a parsed model's junctions take junction_series_gates@1 (from the definition)."""
    return any(j.law == SERIES_GATE_LAW_ID for j in model.junctions)


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
    routes the control is returned as it is, and no factor is evaluated. The routed slots are the
    kinds' own control fields' and @3's own channel slots (B1's door)."""
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
    order, then @3's own channel slots; () without a sink. Refused: an unknown source ID, one that
    two kinds expose, a field that is not the sink's own control field, and a slot routed twice.

    @3 is the sink of its own `channel` field (B1's door, docs/CORE_SEAMS_DESIGN.md §4.3): each
    population whose entry declares factors routes its slot, its position among the channels,
    through its sources, so "a sink routes its own control fields only" holds (sink ID: @3's
    namespaced model ID)."""
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
    for slot, channel_id, named in channel_factors(model):  # B1: @3, the sink of its channels.
        unknown = [source for source in named if source not in sources]
        if unknown:
            raise ConfigError(
                f"Channel population {channel_id}'s factors name unknown factor sources {unknown}"
                + ("" if declared else " (only a declared kind exposes factors)")
            )
        routes.append((OWN_SINK, "channel", slot, tuple(sources[source] for source in named)))
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
    and buffer totals carry the charge). Today's call, unchanged, when nothing is read and no
    forms face is declared; the forms faces' movers join the offsets' current balance (static)."""
    forms = _has_forms(p)
    if read is state and not forms:
        return tissue.field_values(state, control, p, xp=xp)
    ci, co = physical_amounts(read, p)
    q = tissue.charge_increment(state, p, xp=xp)
    n = p.active.size
    # Today's operation order (crossrev compares the program text): the cells' concentrations,
    # then the outside nodes'.
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    return field.solve(
        ci,
        co,
        p.initial_cell_charge_C + q[:n],
        p.initial_outside_charge_C + q[n:],
        control.membrane,
        control.junction,
        p.boundary_V,
        tissue.field_layout(p),
        xp=xp,
        **({"forms": forms_field(co, p, xp=xp)} if forms else {}),
    )


def forms_rates(read, potential, p, *, xp):
    """The forms faces' point law at a state's read and its node potentials: (their rates
    (surface_transport.FormsRates), each outside node's inflow [species, outside node])."""
    n = p.active.size
    _, co = physical_amounts(read, p)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    faces = forms_faces_of(p)
    left, right = forms_ends(co, p, xp=xp)
    outside = potential[n:]
    rates = surface.forms_face_transport(
        left, right, outside[faces.sender] - outside[faces.receiver], p.temperature, faces, xp=xp
    )
    _, inflow = surface.forms_row_rates(rates.flux_fmol_s, faces, p.outside_active.size, xp=xp)
    return rates, inflow


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


def _with_kind_derivatives(base, rates, structure, state, *, xp, extra=None):
    """base's derivative in the structure's state type, the kinds' fields by name, and extra's
    ({field: rate}: FR-30's series gates)."""
    types = kind_types(structure)
    derivatives = dict(extra or {})
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
    pumped = host_gated_pumps(p, structure, xp=xp)  # B1: idle on a closed host (static).
    pr, args = nak_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_delta_mu_J_mol,
        control,
        pumped,
        xp=xp,
        structure=structure,
    )
    cycles = xp.where(pumped.pump_present, pr.cycles_fmol_s, 0.0)
    pump_d = -1e-3 * cycles * pr.cycle_free_energy_J_mol
    metabolic = -1e-3 * cycles * pr.chemical_drive_J_mol
    ca_cycles, ca_d, ca_metabolic, ca_affinity, ca_args = calcium_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_voltage_V,
        control,
        pumped,
        xp=xp,
        structure=structure,
    )
    series_rate = None  # FR-30 (S2): each series gate's own rate, where the law is declared.
    if series_junctions(structure):
        jgate_rate, series_rate = series_junction_rates(
            state, r.junction_voltage_V, p, structure, xp=xp
        )
    else:
        jgate_rate = xp.where(
            p.junction_active,
            junction_gate_rhs(
                state.junction_gate, r.junction_voltage_V, p, xp=xp, structure=structure
            ),
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
    forms = None
    if forms_faces_declared(structure):  # The forms faces' rates, at the read (static).
        forms, forms_inflow = forms_rates(read, v.potential_V, p, xp=xp)
        outside = outside + xp.where(p.reservoir, 0.0, forms_inflow)
        supplied = supplied - xp.where(p.reservoir, forms_inflow, 0.0)
    gated = presence_gated(p, structure, xp=xp)  # Q2: entities on closed hosts absent (static).
    kind_rates = _kind_rates(kinds, read, v.potential_V, control, gated, xp=xp)
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
    electrode = xp.where(
        p.reservoir, field.capacitor_product(tissue.field_layout(p), dphi, xp=xp)[n:], 0.0
    )
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
    if forms is not None:
        dissipation = dissipation + entity_sum(forms.dissipation_pJ_s, axis=None, xp=xp)
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
    if kinds or series_rate is not None or forms is not None:
        extra = {} if series_rate is None else {SERIES_GATES: series_rate}
        if forms is not None:
            extra["forms_face_transferred"] = forms.flux_fmol_s
            extra["forms_face_dissipated_energy_pJ"] = forms.dissipation_pJ_s
        result = _with_kind_derivatives(result, kind_rates, structure, state, xp=xp, extra=extra)
    valid = v.converged
    if forms is not None:
        valid &= forms.valid
    if args is not None:  # The Na/K pump's domain, where its law is declared.
        valid = valid & xp.all(pump.domain_valid(*args, xp=xp))
    if ca_args is not None:
        valid &= xp.all(calcium_atpase.domain_valid(*ca_args, xp=xp))
    valid &= channel_domain_valid(cv, target, tau, p, xp=xp)
    if process is not None:
        valid &= process.valid
    if kinds:  # A failed stage read, a kind's domain or a stage check refuses the row.
        valid &= read_valid & _stage_checks(kinds, read, cell, outside, gated, xp=xp)
        for kr in kind_rates:
            valid &= kr.valid
    for value in _availabilities(control, kinds) if kinds else control:
        valid &= xp.all(xp.isfinite(value) & (value >= 0) & (value <= 1))
    for kind in kinds:
        if kind.control_domain is not None:
            valid &= kind.control_domain(control, p, xp=xp)
    if series_junctions(structure):  # FR-30: each gate on its law's domain.
        valid &= series_junction_domain(state, r.junction_voltage_V, control.junction, p, structure,
                                        xp=xp)  # fmt: skip
    elif structure is None or structure.junction_laws:
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
        xp.where(pumped.pump_present, pr.cycle_free_energy_J_mol, 0.0),
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
    if structure is None:  # Today's five (codes 0-4), the only laws the full catalogue runs: a code
        # the registry adds from 5 is refused here, so it never meets that path's dispatch.
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
    if series_junctions(structure):  # FR-30 (D262): each gate's domain, and their product.
        valid &= series_domain_valid(state, p, structure, xp=xp)
    # Absent species routes never carry hidden transfers or heat.
    route = p.channel_relative_permeability * p.channel_permeability * p.channel_abundance
    valid &= xp.all(xp.where(route > 0, True, state.channel_transferred == 0))
    valid &= xp.all(xp.where(route > 0, True, state.channel_dissipated_energy_pJ == 0))
    valid &= xp.all(xp.where(p.pump_capacity > 0, True, state.pump_cycles == 0))
    valid &= xp.all(xp.where(p.calcium_pump_capacity > 0, True, state.calcium_pump_cycles == 0))
    if forms_faces_declared(structure):  # The forms faces: finite, and nothing on an absent mover.
        moved, heat = state.forms_face_transferred, state.forms_face_dissipated_energy_pJ
        valid &= xp.all(xp.isfinite(moved)) & xp.all(xp.isfinite(heat))
        valid &= xp.all(xp.where(p.forms_face_factor > 0, True, moved == 0))
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


def explicit_rates(
    state,
    potential,
    control,
    p,
    *,
    xp=jnp,
    membrane_process=None,
    structure=None,
    conductances=None,
):
    """surface_pump_v2.explicit_rates with the channel currents at the same potentials.

    The channel gates' rate is zero here: IMEX steps set them by the exponential update, and
    under N2 the junction gates' too ((a)).
    With a membrane_process (opt-in) its flux joins the explicit membrane terms
    and the call returns (rates, valid, MembraneProcess); otherwise (rates, valid).
    Under N2 (conductances, the step's frozen ConductanceWeights) the rates are the remainder:
    the routes' linear parts W dv leave them (explicit_remainder), after the kinds' stage checks,
    which read the whole node rates.
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
    pumped = host_gated_pumps(p, structure, xp=xp)  # B1: idle on a closed host (static).
    rate, args = nak_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_delta_mu_J_mol,
        control,
        pumped,
        xp=xp,
        structure=structure,
    )
    cycles = xp.where(pumped.pump_present, rate.cycles_fmol_s, 0.0)
    ca_cycles, ca_d, ca_metabolic, _, ca_args = calcium_pump_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        r.membrane_voltage_V,
        control,
        pumped,
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
    forms_diffusion = None
    if forms_faces_declared(structure):  # The forms faces' diffusion, explicit as the faces'.
        faces = forms_faces_of(p)
        forms_weight, forms_log = imex.forms_face_weights(*forms_ends(co, p, xp=xp), faces, xp=xp)
        forms_diffusion = forms_weight * forms_log
        _, forms_inflow = surface.forms_row_rates(forms_diffusion, faces, co.shape[1], xp=xp)
        inflow = inflow + forms_inflow
    series_rate = None  # FR-30 (S2): each series gate's own rate, where the law is declared.
    if conductances is not None:  # N2 ((a), static): imex_step sets the junction gates by their
        # exponential update.
        gate = xp.zeros_like(state.junction_gate)
        if series_junctions(structure):
            series_rate = xp.zeros_like(getattr(state, SERIES_GATES))
    elif series_junctions(structure):
        gate, series_rate = series_junction_rates(state, r.junction_voltage_V, p, structure, xp=xp)
    else:
        gate = junction_gate_rhs(
            state.junction_gate, r.junction_voltage_V, p, xp=xp, structure=structure
        )
    outside_zero = xp.zeros_like(p.boundary_V)
    cell_rate = r.cell_rate_fmol_s - scatter(extra, r.cell_rate_fmol_s, (p.membrane_cell,), xp=xp)
    gated = presence_gated(p, structure, xp=xp)  # Q2: entities on closed hosts absent (static).
    kind_rates = _kind_rates(kinds, read, potential, control, gated, xp=xp)
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
    if kinds or series_rate is not None or forms_diffusion is not None:
        extra = {} if series_rate is None else {SERIES_GATES: series_rate}
        if forms_diffusion is not None:  # Their heat is the step's (imex_step).
            extra["forms_face_transferred"] = forms_diffusion
        rates = _with_kind_derivatives(rates, kind_rates, structure, state, xp=xp, extra=extra)
    if conductances is not None:  # N2 (static): the remainder, J - W dv, at these potentials.
        rates = explicit_remainder(rates, conductances, potential, r, p, xp=xp)
    valid = r.valid
    if kinds:  # A failed stage read, a kind's domain or a stage check refuses the step.
        outside_rate = xp.where(p.reservoir, 0.0, inflow)
        valid = (
            valid & read_valid & _stage_checks(kinds, read, cell_rate, outside_rate, gated, xp=xp)
        )
        for kr in kind_rates:
            valid = valid & kr.valid
    if args is not None:  # The Na/K pump's domain, where its law is declared.
        valid = valid & xp.all(pump.domain_valid(*args, xp=xp))
    if ca_args is not None:
        valid &= xp.all(calcium_atpase.domain_valid(*ca_args, xp=xp))
    valid &= channel_domain_valid(cv, target, tau, p, xp=xp)
    if series_junctions(structure):  # FR-30: each gate on its law's domain.
        valid &= series_junction_domain(state, r.junction_voltage_V, control.junction, p, structure,
                                        xp=xp)  # fmt: skip
    elif structure is None or structure.junction_laws:
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


def implicit_rates(weight, potential, state, p, *, xp=jnp, conductances=None, forms_weight=None):
    """Face electromigration rates with frozen face weights; zero elsewhere.

    Under N2 (conductances, the step's frozen ConductanceWeights) the membranes', channels' and
    junctions' linear parts at the same potentials join them (linear_route_fluxes), with their
    amounts on both sides; their heat is set at the stage (implicit_route_heat). With forms faces
    (forms_weight, their movers' frozen weights; static) their electromigration joins the faces'."""
    s, n = tissue.field_layout(p).surface, p.active.size
    flux = imex.drift_flux(weight, potential[n:], s, xp=xp)
    zero = xp.zeros_like(state.extracellular_amount_increment)
    inflow = scatter(flux, zero, (p.face_receiver,), xp=xp) - scatter(
        flux, zero, (p.face_sender,), xp=xp
    )
    rates = type(state)(*(xp.zeros_like(v) for v in state))  # The state's own type (schema A).
    if forms_weight is not None:
        faces = forms_faces_of(p)
        forms_flux = imex.forms_drift_flux(forms_weight, potential[n:], p.temperature, faces, xp=xp)
        _, forms_inflow = surface.forms_row_rates(forms_flux, faces, zero.shape[1], xp=xp)
        inflow = inflow + forms_inflow
        rates = rates._replace(forms_face_transferred=forms_flux)
    if conductances is None:
        return rates._replace(
            extracellular_amount_increment=xp.where(p.reservoir, 0.0, inflow),
            face_transferred=flux,
            reservoir_supplied=xp.where(p.reservoir, -inflow, 0.0),
        )
    membrane, channel, junction = linear_route_fluxes(conductances, potential, p, xp=xp)
    cells, outside = route_amount_rates(membrane, channel, junction, p, xp=xp)
    inflow = inflow + outside
    return rates._replace(
        amount_increment=xp.where(p.active, cells, 0.0),
        extracellular_amount_increment=xp.where(p.reservoir, 0.0, inflow),
        membrane_transferred=membrane,
        junction_transferred=junction,
        face_transferred=flux,
        reservoir_supplied=xp.where(p.reservoir, -inflow, 0.0),
        channel_transferred=channel,
    )


# --- N2 (FR-8 rung 1, D235): membranes' and junctions' slope conductances in the operator ------
#
# Each constant-field route (a membrane's passive permeabilities, a channel population, a
# junction) is split as J(dv) = W dv + [J(dv) - W dv], W = dJ/d(dv) frozen for the step at the
# tableau's operator time (the face weights' time). The first part is implicit: its charge
# current is G dv, G = CHARGE_PER_FMOL sum_s z_s W_s >= 0 (S), a Laplacian block beside the faces'
# in (C + a dt L) phi = q, so one factorization still serves the step and the matrix stays SPD.
# The species move in flux form with the same W, so material and charge stay exact. The second
# part, the remainder, stays among the explicit rates; its derivative in dv vanishes at the
# operator time. Each part's heat, J x its electrochemical difference, is booked with its own
# weights of the tableau (the remainder at the explicit stages, the linear part at the implicit
# ones), so the heat accumulators integrate as the state does. The pieces are FR45's frozen-
# weight constant-field split (laws/routes/patch_electrodiffusion.py), in this file's sender ->
# receiver sign (cell -> outside for patches).
#
# (a): each junction gate is advanced by its exponential update at the stages, as the channel
# gates are (stage_junction_gates), not by the tableau, so the junction-gate step bound
# (GATE_STEP_BOUND) does not apply. The risk it opens, frozen W: W holds the junction gates'
# operator-time prediction for the whole step, while a gate may now move far within one step.
# The split stays exact (each stage's remainder is J - W dv at that stage's gate), so material,
# charge and the heat booking stay exact; what a gate that moves far can cost is accuracy and,
# at a large step, a transfer's sign. The per-element dissipation check and X2 refuse a
# wrong-signed transfer or a misbooking (as the channel gates' wrong-signed nav_0 transfer at
# 200 ms on H2 was refused, RUNG1 §10.13); nothing bounds the junction current's accuracy there.
#
# What stays explicit, and its checks. The stage rule (membrane_rate, explicit_only) counts the
# declared kinds' terms; the definition-time bound (implicit_conductance_rate_bound) counts face
# diffusion and every species' material relaxation; the calcium and kind bounds stay. A known
# gap, guarded by X2: the pumps' electrogenic currents stay explicit and no rule
# counts their slope, as today's never did. Their charge relaxation through dI/dV is
# 1.2e-4 per s on H2 and 4.8e-4 per s on W0 at the declared states (20 November 2026, a central
# difference of the pump law), against 1/(10 x 200 ms) = 0.5 per s.


class ConductanceWeights(NamedTuple):
    """N2's frozen slopes dJ/d(dv) (fmol/s per V, sender -> receiver flux)."""

    membrane: object  # [species, membrane]: the patches' own constant-field permeabilities
    channel: object  # [species, channel]: each population at its patch's voltage
    junction: object  # [species, junction]


def implicit_conductances(p):
    """Whether the layout's solver is an N2 ID: static, from its tableau's operator time, a vector
    (faces, then routes) under N2 alone (surface_imex.operator_times)."""
    return imex.operator_times(p.imex_operator_time)[1] is not None


def route_slope(c_from, c_to, dv, valence, temperature, area, permeability, available, *, xp):
    """dJ/d(dv) of selective_flux's constant-field flux (sender -> receiver, fmol/s per V):
    J = A P a/MOL (c_from B(-x) - c_to B(x)), x = z F dv/RT, so dJ/d(dv) = A P a/MOL (zF/RT)
    (-c_from B'(-x) - c_to B'(x)); B' < 0, so z dJ/d(dv) >= 0."""
    k = valence * F / (R * temperature)
    x = k * dv
    prefactor = area * permeability * available / MOL_PER_FMOL
    slope = constant_field_route.bernoulli_slope
    return prefactor * k * (-c_from * slope(-x, xp=xp) - c_to * slope(x, xp=xp))


def conductance_weights(state, read, potential, control, p, *, xp=jnp, structure=None):
    """N2's ConductanceWeights at a state (its read's concentrations, the given node potentials,
    its gates) under the step's controls, as transport and channel_rates form the fluxes."""
    n = p.active.size
    ci, co = physical_amounts(read, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    dv = xp.where(
        p.membrane_active, potential[p.membrane_cell] - potential[n + p.membrane_outside], 0.0
    )
    left, right = ci[:, p.membrane_cell], co[:, p.membrane_outside]
    membrane = route_slope(
        xp.where(p.membrane_active, left, 1.0),
        xp.where(p.membrane_active, right, 1.0),
        dv,
        p.valence,
        p.temperature,
        p.membrane_area,
        p.membrane_permeability,
        control.membrane,
        xp=xp,
    )
    patch = p.channel_membranes
    opening = channel_opening(state.channel_gate, p.channel_laws, xp=xp, structure=structure)
    channel = route_slope(
        left[:, patch],
        right[:, patch],
        channel_voltage(dv, p, xp=xp),
        p.valence,
        p.temperature,
        p.membrane_area[patch],
        p.channel_permeability * p.channel_relative_permeability,
        p.channel_abundance * opening * control.channel,
        xp=xp,
    )
    sender, receiver = ci[:, p.junction_sender], ci[:, p.junction_receiver]
    junction = route_slope(
        xp.where(p.junction_active, sender, 1.0),
        xp.where(p.junction_active, receiver, 1.0),
        xp.where(
            p.junction_active,
            potential[p.junction_sender] - potential[p.junction_receiver],
            0.0,
        ),
        p.valence,
        p.temperature,
        p.junction_area,
        p.junction_permeability,
        control.junction * state.junction_gate,
        xp=xp,
    )
    return ConductanceWeights(
        xp.where(p.membrane_active, membrane, 0.0),
        xp.where(p.channel_active, channel, 0.0),
        xp.where(p.junction_active, junction, 0.0),
    )


def conductance_laplacian(weights, p, *, xp=jnp):
    """N2's node-space Laplacian (S): each patch's G (its own and its channels') between its cell
    and outside node, each junction's between its two cells."""
    n, o = p.active.size, p.outside_active.size
    g_patch = CHARGE_PER_FMOL * species_sum(p.valence * weights.membrane, xp=xp)
    g_patch = g_patch + channel_to_membrane_sum(
        CHARGE_PER_FMOL * species_sum(p.valence * weights.channel, xp=xp), p, xp=xp
    )
    g_junction = CHARGE_PER_FMOL * species_sum(p.valence * weights.junction, xp=xp)
    zero = xp.zeros((n + o, n + o), dtype=g_patch.dtype)

    def block(g, a, b):
        return (
            scatter(g, zero, (a, a), xp=xp)
            + scatter(g, zero, (b, b), xp=xp)
            - scatter(g, zero, (a, b), xp=xp)
            - scatter(g, zero, (b, a), xp=xp)
        )

    return block(g_patch, p.membrane_cell, n + p.membrane_outside) + block(
        g_junction, p.junction_sender, p.junction_receiver
    )


def channel_to_membrane_sum(value, p, *, xp=jnp):
    """Sum a per-channel value [channel] into its patch [membrane]."""
    return scatter(value, xp.zeros_like(p.membrane_area), (p.channel_membranes,), xp=xp)


def linear_route_fluxes(weights, potential, p, *, xp=jnp):
    """(membrane [species, membrane], channel [species, channel], junction [species, junction]):
    N2's implicit parts W dv at the given node potentials (sender -> receiver)."""
    n = p.active.size
    dv = xp.where(
        p.membrane_active, potential[p.membrane_cell] - potential[n + p.membrane_outside], 0.0
    )
    dj = xp.where(
        p.junction_active, potential[p.junction_sender] - potential[p.junction_receiver], 0.0
    )
    return (
        weights.membrane * dv,
        weights.channel * channel_voltage(dv, p, xp=xp),
        (weights.junction * dj),
    )


def route_amount_rates(membrane, channel, junction, p, *, xp=jnp):
    """(cells [species, cell], outside [species, outside]): the amount rates of route fluxes
    (sender -> receiver; a channel's on its patch)."""
    patches = membrane + channel_to_membrane(channel, p, xp=xp)
    zero_cells = xp.zeros((patches.shape[0], p.active.size), dtype=patches.dtype)
    zero_outside = xp.zeros((patches.shape[0], p.outside_active.size), dtype=patches.dtype)
    cells = (
        scatter(junction, zero_cells, (p.junction_receiver,), xp=xp)
        - scatter(junction, zero_cells, (p.junction_sender,), xp=xp)
        - scatter(patches, zero_cells, (p.membrane_cell,), xp=xp)
    )
    return cells, scatter(patches, zero_outside, (p.membrane_outside,), xp=xp)


def route_delta_mu(read, potential, p, *, xp=jnp):
    """(membrane, junction) electrochemical differences (J/mol, sender minus receiver) at a
    state's read concentrations and the given node potentials, as transport forms them."""
    n = p.active.size
    ci, co = physical_amounts(read, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    rt, z = R * p.temperature, p.valence
    out = []
    for active, left, right, dv in (
        (
            p.membrane_active,
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            potential[p.membrane_cell] - potential[n + p.membrane_outside],
        ),
        (
            p.junction_active,
            ci[:, p.junction_sender],
            ci[:, p.junction_receiver],
            potential[p.junction_sender] - potential[p.junction_receiver],
        ),
    ):
        left, right = xp.where(active, left, 1.0), xp.where(active, right, 1.0)
        dv = xp.where(active, dv, 0.0)
        out.append(xp.where(active, rt * (xp.log(left) - xp.log(right)) + z * F * dv, 0.0))
    return tuple(out)


def route_heat_rates(membrane, channel, junction, mu_membrane, mu_junction, p, *, xp=jnp):
    """The heat rates (pJ/s) of route fluxes against their electrochemical differences:
    (membrane [membrane], channel [species, channel], junction [junction]), in the accumulators'
    shapes (transport's dissipation and channel_rates' heat)."""
    return (
        1e-3 * species_sum(membrane * mu_membrane, xp=xp),
        1e-3 * channel * mu_membrane[:, p.channel_membranes],
        1e-3 * species_sum(junction * mu_junction, xp=xp),
    )


def explicit_remainder(rates, weights, potential, r, p, *, xp=jnp):
    """N2's explicit rates: today's at a stage less the linear parts W dv at the stage's
    potentials, in the amounts, the transfers and the heat (r: the stage's transport values)."""
    membrane, channel, junction = linear_route_fluxes(weights, potential, p, xp=xp)
    cells, outside = route_amount_rates(membrane, channel, junction, p, xp=xp)
    heat_m, heat_c, heat_j = route_heat_rates(
        membrane, channel, junction, r.membrane_delta_mu_J_mol, r.junction_delta_mu_J_mol, p, xp=xp
    )
    return rates._replace(
        amount_increment=rates.amount_increment - xp.where(p.active, cells, 0.0),
        extracellular_amount_increment=rates.extracellular_amount_increment
        - xp.where(p.reservoir, 0.0, outside),
        reservoir_supplied=rates.reservoir_supplied - xp.where(p.reservoir, -outside, 0.0),
        membrane_transferred=rates.membrane_transferred - membrane,
        junction_transferred=rates.junction_transferred - junction,
        channel_transferred=rates.channel_transferred - channel,
        membrane_dissipated_energy_pJ=rates.membrane_dissipated_energy_pJ - heat_m,
        junction_dissipated_energy_pJ=rates.junction_dissipated_energy_pJ - heat_j,
        channel_dissipated_energy_pJ=rates.channel_dissipated_energy_pJ - heat_c,
    )


def implicit_route_heat(drift, stage, weights, potential, p, *, xp=jnp, kinds=()):
    """N2: the implicit rates at a stage with their routes' heat, the linear parts against the
    stage's electrochemical differences (its read concentrations, its potentials), and the stage's
    validity of that read."""
    read, ok = _stage_read(stage, p, kinds, xp=xp) if kinds else (stage, True)
    mu_membrane, mu_junction = route_delta_mu(read, potential, p, xp=xp)
    heat_m, heat_c, heat_j = route_heat_rates(
        drift.membrane_transferred,
        drift.channel_transferred,
        drift.junction_transferred,
        mu_membrane,
        mu_junction,
        p,
        xp=xp,
    )
    drift = drift._replace(
        membrane_dissipated_energy_pJ=heat_m,
        junction_dissipated_energy_pJ=heat_j,
        channel_dissipated_energy_pJ=heat_c,
    )
    return drift, ok


def operator_time_conductances(start, control, p, dt, *, xp=jnp, kinds=(), structure=None):
    """(N2's ConductanceWeights frozen for the step, the prediction's validity), from the step's
    start (`start`: readouts at the state) at the routes' operator time (the tableau's second
    entry), as the face weights at theirs:
    - the amounts advanced over that operator time x dt by the start derivative, the face weights'
      prediction, here for cells too;
    - the channel gates by their exponential update over that time at the start kinetics, and the
      junction gates likewise at the start's junction voltages (their law's relaxation), so a fast
      gate is never carried past its target;
    - the node potentials the field gives the predicted amounts' charges.
    The prediction must keep every concentration positive, its field finite and converged, and
    every slope finite."""
    state, derivative, potential = start.state, start.values.derivative, start.potential
    theta = imex.operator_times(p.imex_operator_time)[1] * dt
    gate = gates.advance(
        state.channel_gate,
        start.values.channel_targets,
        start.values.channel_tau_s,
        start.values.channel_targets,
        start.values.channel_tau_s,
        theta,
        xp=xp,
    )
    junction_voltage = xp.where(
        p.junction_active, potential[p.junction_sender] - potential[p.junction_receiver], 0.0
    )
    if series_junctions(structure):  # FR-30: each gate's own exponential update, then the product.
        series = predicted_series_gates(state, junction_voltage, theta, p, structure, xp=xp)
        ahead = with_series_conductance(state._replace(**{SERIES_GATES: series}), p, xp=xp)
        ahead = ahead._replace(
            amount_increment=state.amount_increment + theta * derivative.amount_increment,
            extracellular_amount_increment=state.extracellular_amount_increment
            + theta * derivative.extracellular_amount_increment,
            channel_gate=xp.where(p.channel_gate_active, gate, state.channel_gate),
        )
    else:  # Today's program, unchanged.
        rates = junction_gate.kinetics(junction_voltage, kinetic.junction_parameters(p), xp=xp)
        junction = state.junction_gate + (rates.target - state.junction_gate) * -xp.expm1(
            -rates.relaxation_per_s * theta
        )
        ahead = state._replace(
            amount_increment=state.amount_increment + theta * derivative.amount_increment,
            extracellular_amount_increment=state.extracellular_amount_increment
            + theta * derivative.extracellular_amount_increment,
            channel_gate=xp.where(p.channel_gate_active, gate, state.channel_gate),
            junction_gate=xp.where(p.junction_active, junction, state.junction_gate),
        )
    read, valid = _stage_read(ahead, p, kinds, xp=xp) if kinds else (ahead, True)
    ci, co = physical_amounts(read, p)
    valid = valid & xp.all(xp.where(p.active, xp.isfinite(ci) & (ci > 0), True))
    valid = valid & xp.all(xp.where(p.outside_active, xp.isfinite(co) & (co > 0), True))
    from cells.execution.schedule import SurfaceControl

    values = _field_values(
        ahead,
        read,
        SurfaceControl(control.membrane, control.junction * ahead.junction_gate),
        p,
        xp=xp,
    )
    ahead_potential = values.potential_V
    valid = valid & xp.all(xp.isfinite(ahead_potential)) & values.converged
    weights = conductance_weights(
        ahead, read, ahead_potential, control, p, xp=xp, structure=structure
    )
    for value in weights:
        valid = valid & xp.all(xp.isfinite(value))
    return weights, valid


class StepStart(NamedTuple):
    """The step's start, as operator_time_conductances reads it."""

    state: object
    values: object  # readouts at the state (Values)
    potential: object  # the start's node potentials


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


def junction_voltage_kinetics(potential, p, *, xp=jnp):
    """(the junction voltages, the junction law's kinetics at them) at the node potentials."""
    voltage = xp.where(
        p.junction_active, potential[p.junction_sender] - potential[p.junction_receiver], 0.0
    )
    return voltage, junction_gate.kinetics(voltage, kinetic.junction_parameters(p), xp=xp)


def stage_junctions(stage, state, start, potential, availability, fraction, dt, p, *, xp=jnp,
                    structure=None):  # fmt: skip
    """N2's (a) at a stage: (the stage with its junction gates by their exponential update, its
    validity): one gate's (stage_junction_gates), or each series gate's and their product
    (stage_series_gates, FR-30)."""
    if series_junctions(structure):
        return stage_series_gates(
            stage, state, start, potential, availability, fraction, dt, p, structure, xp=xp
        )
    junction, ok = stage_junction_gates(
        state.junction_gate, start, potential, availability, fraction, dt, p, xp=xp,
        structure=structure,
    )  # fmt: skip
    return stage._replace(junction_gate=junction), ok


def predicted_series_gates(state, junction_voltage, theta, p, structure, *, xp=jnp):
    """FR-30: each series gate after theta by its exponential update at the start's kinetics
    (N2's operator-time prediction, as for one gate) [series_gate, edge]; padded edges held."""
    gates = getattr(state, SERIES_GATES)
    out = []
    for k, rates in enumerate(series_kinetics(junction_voltage, p, structure, xp=xp)):
        moved = gates[k] + (rates.target - gates[k]) * -xp.expm1(-rates.relaxation_per_s * theta)
        out.append(xp.where(p.junction_active, moved, gates[k]))
    return xp.stack(out)


def stage_series_gates(stage, state, start, potential, availability, fraction, dt, p, structure, *,
                       xp=jnp):  # fmt: skip
    """N2's (a) for junction_series_gates@1 (FR-30): each gate's exponential update from the
    step start to the stage at fraction * dt, as stage_junction_gates' for one gate, from each
    gate's Rates at the start's (`start`) and the stage's junction voltages; then junction_gate
    their product (S2); with the law's domain at the stage. (stage, valid)."""
    voltage = xp.where(
        p.junction_active, potential[p.junction_sender] - potential[p.junction_receiver], 0.0
    )
    gates = getattr(state, SERIES_GATES)
    out = []
    for k, (begin, end) in enumerate(zip(start, series_kinetics(voltage, p, structure, xp=xp),
                                         strict=True)):  # fmt: skip
        advanced = gates_advance(gates[k], begin, end, fraction * dt, xp=xp)
        out.append(xp.where(p.junction_active, advanced, gates[k]))
    stage = with_series_conductance(stage._replace(**{SERIES_GATES: xp.stack(out)}), p, xp=xp)
    return stage, series_junction_domain(stage, voltage, availability, p, structure, xp=xp)


def gates_advance(gate, begin, end, interval, *, xp=jnp):
    """exponential_gates.advance from two junction Rates (targets and time constants)."""
    return gates.advance(gate, begin.target, 1.0 / begin.relaxation_per_s, end.target,
                         1.0 / end.relaxation_per_s, interval, xp=xp)  # fmt: skip


def stage_junction_gates(
    gate, start, potential, availability, fraction, dt, p, *, xp=jnp, structure=None
):
    """N2's (a): each junction gate's exponential update from the step start to a stage at
    fraction * dt, as stage_gates' for the channels (exponential_gates.advance: the mean of the
    start's and the stage's relaxation rates, the target linear between them), from the law's
    kinetics at the start's (`start`, junction_gate.Rates) and the stage's junction voltages; with
    the law's domain at the stage. A gate stays between its start and its targets, in
    [minimum, 1], at any step, so no junction-gate step bound applies. Without a declared
    junction law the gates hold, as junction_gate_rhs's zeros hold them today."""
    if structure is not None and not structure.junction_laws:
        return gate, True
    voltage, stage = junction_voltage_kinetics(potential, p, xp=xp)
    advanced = gates.advance(
        gate,
        start.target,
        1.0 / start.relaxation_per_s,
        stage.target,
        1.0 / stage.relaxation_per_s,
        fraction * dt,
        xp=xp,
    )
    advanced = xp.where(p.junction_active, advanced, gate)
    parameters = kinetic.junction_parameters(p)
    ok = xp.all(junction_gate.domain_valid(advanced, voltage, parameters, availability, xp=xp))
    return advanced, ok


# --- FR-42 (D289): labelled rows' one-way amounts over an inner step ---------------------------
#
# Labels are shares of a physical row; they follow material only through one-way amounts. With
# `labels` (the labelled species' rows, static), imex_step and checked_step also return transfers:
# per direction and entity kind, (amount [m, entity] fmol over the step, each >= 0, source and
# destination node [entity] on the combined axis, cells then outside nodes). The state and validity
# are the unlabelled call's bit for bit; without labels nothing is traced. Each entity's amounts are
# the trapezoid of its one-way fluxes at the step's start and end states (the Euler IMEX, whose
# weights are all >= 0, combines its one explicit stage directly), plus the gap to the booked move
# (O(dt^3)) on the side its sign gives: forward - backward is the booked net at rounding, both stay
# >= 0 and second order. ARS(2,2,2)'s explicit weights (delta, 1 - delta, 0), delta < 0, would make
# a stage-weighted one-way amount negative where a flux falls by more than 59% within a step.
# Declared kinds report theirs through their own hook (D303 item 6, kind_registry.Kind's
# label_transfers, the same rule on their own one-way fluxes and booked nets), appended after the
# core's; their refusals are their label_refusals (kind_registry.label_refusal_errors).

FR42_REFUSAL = "FR-42 (labelled rows inside @3's step)"


def label_errors(p, rows, *, structure=None, solver=None, model=None):
    """FR-42's refusals at the definition (host side, the layout's values): the reasons the
    labelled rows `rows` cannot be carried, or []. Declared kinds give their own reasons
    (label_refusals, read from their declarations in `model`, the parsed inner model); without
    the model they stay refused."""
    errors = []
    if solver == "rk4" or getattr(p, "imex_explicit", np.zeros((1,))).shape[0] == 0:
        errors.append(f"{FR42_REFUSAL}: RK4 refuses labels in version 1")
    if structure is not None and structure.kinds:
        if model is None:
            errors.append(
                f"{FR42_REFUSAL}: declared kinds give their refusals from their declarations, "
                "which need the parsed model"
            )
        else:
            species = tuple(model.species_ids[int(r)] for r in rows)
            errors += [
                f"{FR42_REFUSAL}: {reason}"
                for reason in kind_registry.label_refusal_errors(model.kinds, species)
            ]
    rows = list(rows)
    s = tissue.field_layout(p).surface
    valence = np.asarray(p.valence).reshape(len(p.valence), -1)[:, 0]
    faces = np.asarray(s.face_active, dtype=bool)
    for r in rows:
        if valence[r] != 0 and faces.any():
            errors.append(f"{FR42_REFUSAL}: charged row {r} on a logmean face has no one-way form")
        # A channel carries row r where its relative permeability [species, channel] is nonzero,
        # on an active population with a permeability (FR-42's fix: species row, not channel).
        relative = getattr(p, "channel_relative_permeability", None)
        if relative is not None and np.asarray(relative).shape[-1]:
            carried = np.asarray(relative)[r] != 0
            carried &= np.asarray(p.channel_active, dtype=bool) & (
                np.asarray(p.channel_permeability) > 0
            )
            if np.any(carried):
                errors.append(f"{FR42_REFUSAL}: row {r} crosses a channel population")
        # A pump moves row r where its stoichiometry [species, membrane] is nonzero at a patch with
        # a capacity.
        pumps = (
            ("stoichiometry", "pump_capacity"),
            ("calcium_stoichiometry", "calcium_pump_capacity"),
        )
        for stoichiometry, capacity in pumps:
            if hasattr(p, stoichiometry):
                moved = np.asarray(getattr(p, stoichiometry))[r] != 0
                if hasattr(p, capacity):
                    moved &= np.asarray(getattr(p, capacity)) > 0
                if np.any(moved):
                    errors.append(f"{FR42_REFUSAL}: row {r} is moved by a pump")
                    break
        # A forms face moves row r where a mover it carries (a positive factor on an active face)
        # changes the row: as itself, as a binder's form, or as a ligand a form carries. FR-42's
        # face term assumes one face factor per row, so version 1 refuses it (the build plan's
        # item 1; the face builder's line, landing after FR-42's hook).
        if _has_forms(p):
            changes = np.asarray(p.forms_face_stoichiometry)[:, r] != 0  # [mover]
            carried = (np.asarray(p.forms_face_factor) > 0) & np.asarray(
                p.forms_face_active, dtype=bool
            )[None, :]
            if np.any(changes[:, None] & carried):
                errors.append(
                    f"{FR42_REFUSAL}: row {r} is moved by a forms face ({forms_law.LAW_ID}), "
                    "whose one-way term is not built (version 1)"
                )
    return errors


def one_way_fluxes(view, p, rows, *, xp=jnp):
    """FR-42: the labelled rows' one-way fluxes (fmol/s) at one end of a step (a LabelView: its
    read's amounts, its potentials and its control), as (forward, backward) per entity kind
    [m, entity], in the transport law's own directions: faces sender to receiver, membranes cell
    to outside, junctions sender to receiver. Faces carry
    uncharged rows (W ln(a/b) = c (a - b), c = face_factor / MOL_PER_FMOL, so c a and c b);
    membranes and junctions the constant-field law's two terms, opening x B(-x) c_from and
    B(x) c_to (laws/junctions/selective)."""
    from cells.laws.electrochemistry import bernoulli

    idx = xp.asarray(rows)
    s = tissue.field_layout(p).surface
    n = p.active.size
    ci, co = physical_amounts(view.read, p)
    ci = xp.where(p.active, ci / p.volume, 1.0)
    co = xp.where(p.outside_active, co / p.extracellular_volume, 1.0)
    z = p.valence[idx]
    rt = R * p.temperature
    cell, outside = view.potentials[:n], view.potentials[n:]

    def route(c_from, c_to, dv, area, permeability, opening, active):
        x = z * F * xp.where(active, dv, 0.0) / rt
        prefactor = area * permeability[idx] * opening / MOL_PER_FMOL
        c_from, c_to = xp.where(active, c_from, 1.0), xp.where(active, c_to, 1.0)
        forward = xp.where(active, prefactor * c_from * bernoulli(-x, xp=xp), 0.0)
        backward = xp.where(active, prefactor * c_to * bernoulli(x, xp=xp), 0.0)
        return forward, backward

    membrane = route(
        ci[idx][:, s.membrane_cell],
        co[idx][:, s.membrane_outside],
        cell[s.membrane_cell] - outside[s.membrane_outside],
        s.membrane_area,
        s.membrane_permeability,
        view.control.membrane,
        s.membrane_active,
    )
    junction = route(
        ci[idx][:, s.junction_sender],
        ci[idx][:, s.junction_receiver],
        cell[s.junction_sender] - cell[s.junction_receiver],
        s.junction_area,
        s.junction_permeability,
        view.control.junction * view.state.junction_gate,
        s.junction_active,
    )
    c = xp.where(s.face_active, s.face_factor[idx] / MOL_PER_FMOL, 0.0)
    face = (
        c * xp.where(s.face_active, co[idx][:, s.face_sender], 0.0),
        c * xp.where(s.face_active, co[idx][:, s.face_receiver], 0.0),
    )
    return dict(face=face, membrane=membrane, junction=junction)


def step_transfers(start, end, p, dt, rows, *, xp=jnp, direct=None):
    """FR-42: the step's transfers (module comment above) between its two ends (LabelViews): the
    trapezoid of the start and end one-way fluxes (or `direct`, the Euler IMEX's combined stage
    terms, the end then carrying only its state), plus the gap to the booked net (the end state's
    accumulators less the start's) on the side its sign gives."""
    idx = xp.asarray(rows)
    s = tissue.field_layout(p).surface
    n = p.active.size
    if direct is None:
        a = one_way_fluxes(start, p, rows, xp=xp)
        b = one_way_fluxes(end, p, rows, xp=xp)
        sums = {k: tuple(0.5 * dt * (a[k][i] + b[k][i]) for i in (0, 1)) for k in a}
    else:
        sums = direct
    nodes = dict(
        face=(n + s.face_sender, n + s.face_receiver),
        membrane=(s.membrane_cell, n + s.membrane_outside),
        junction=(s.junction_sender, s.junction_receiver),
    )
    booked = dict(face="face_transferred", membrane="membrane_transferred",
                  junction="junction_transferred")  # fmt: skip
    transfers = []
    for kind in ("face", "membrane", "junction"):
        forward, backward = sums[kind]
        net = (getattr(end.state, booked[kind]) - getattr(start.state, booked[kind]))[idx]
        gap = net - (forward - backward)
        source, destination = nodes[kind]
        transfers.append((forward + xp.maximum(gap, 0.0), source, destination))
        transfers.append((backward + xp.maximum(-gap, 0.0), destination, source))
    return tuple(transfers)


def crosses_floating(structure):
    """Fix (A) (D273): whether a junction joins two capacitor components where one floats (the
    structure's crossing_junctions; static)."""
    return structure is not None and bool(structure.crossing_junctions)


def crossing_view(state, control, p, *, xp=jnp, kinds=(), structure=None):
    """(LabelView, valid): crossing_potential's solve with the read and the routed control it
    solves at, so FR-42's end of a step reads what the stage rates read."""
    from cells.execution.schedule import SurfaceControl

    read = _stage_read(state, p, kinds, xp=xp)[0] if kinds else state
    if kinds and structure.routes:  # §7.4 (n): the routing door, as readouts opens it.
        control = _route(structure, kinds, read, control, p, xp=xp)[0]
    values = _field_values(
        state,
        read,
        SurfaceControl(control.membrane, control.junction * state.junction_gate),
        p,
        xp=xp,
    )
    potential = values.potential_V
    valid = xp.all(xp.isfinite(potential)) & values.converged
    return LabelView(state, read, potential, control), valid


def crossing_potential(state, control, p, *, xp=jnp, kinds=(), structure=None):
    """Fix (A) (D273): a stage state's quasi-static potentials and their validity, solved as
    readouts solves the step start's: the field at the state's charges, with the stage read and the
    routing door, and each floating component's offset by current balance at the state's own
    junction openings. Where a junction joins capacitor components and one floats, the stage solve's
    offsets follow from current balance with a lagged junction current, and its junction converges
    at first order; the explicit rates (and N2's stage junction gates) read these instead."""
    view, valid = crossing_view(state, control, p, xp=xp, kinds=kinds, structure=structure)
    return view.potentials, valid


def imex_step(state, dt, control, p, *, xp=jnp, membrane_process=None, structure=None, labels=None):
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
    if labels is not None and forms_faces_declared(structure):  # Version 1 (label_errors' line).
        raise ConfigError(
            f"{FR42_REFUSAL}: {forms_law.LAW_ID}'s faces have no one-way term (version 1)"
        )
    if labels is not None:  # FR-42 (static, D303 item 6): a kind's moves need its refusals.
        for kind in kinds:
            if kind.rates is not None and kind.label_refusals is None:
                raise ConfigError(
                    f"{FR42_REFUSAL}: kind {kind.kind_id} has a rates hook and no label_refusals, "
                    "so it is refused beside labels (fail-closed)"
                )
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
    drift = first_values.derivative.extracellular_amount_increment  # The stored totals' rate.
    operator_time = imex.operator_times(p.imex_operator_time)[0]  # The faces' (today's scalar).
    if structure is not None and structure.free_amount_reads:
        # P1 (CORE_SEAMS §17; §19 as amended, static): the predictor reads the quantity it
        # differentiates. The stored totals are predicted, and the stage read at them gives the
        # free amounts, its closure's after equilibration; a failed read refuses the step. Every
        # stage read here takes this form (_check_stage_rows), and the read leaves rows it does
        # not hold as stored. Elsewhere, today's form: the start read's amount plus the stored
        # derivative.
        stored = state.extracellular_amount_increment + operator_time * dt * drift
        ahead, ahead_ok = _stage_read(
            state._replace(extracellular_amount_increment=stored), p, kinds, xp=xp
        )
        valid &= ahead_ok
        predicted = p.extracellular_amount_reference + ahead.extracellular_amount_increment
    else:
        amount = p.extracellular_amount_reference + read.extracellular_amount_increment
        predicted = amount + operator_time * dt * drift
    predicted = xp.where(p.outside_active, predicted / p.extracellular_volume, 1.0)
    valid &= xp.all(xp.isfinite(predicted) & (predicted > 0))
    weight, _ = imex.face_weights(xp.where(predicted > 0, predicted, 1.0), s, xp=xp)
    # The coefficient before the Laplacian, in today's order, so a world without N2 keeps
    # today's program text (crossrev compares it).
    coefficient = implicit_matrix[-1, -1] * dt
    laplacian = imex.operator_laplacian(weight, s, f, xp=xp)  # On the sparse field, its pattern's.
    forms_weight = None
    if forms_faces_declared(structure):  # The forms faces' movers, frozen as the faces' (static).
        faces = forms_faces_of(p)
        ends = forms_ends(xp.where(predicted > 0, predicted, 1.0), p, xp=xp)
        forms_weight, _ = imex.forms_face_weights(*ends, faces, xp=xp)
        laplacian = laplacian + imex.forms_face_laplacian(
            forms_weight, p.temperature, laplacian.shape[0], p.active.size, faces, xp=xp
        )
    n2 = implicit_conductances(p)  # N2 (D235, static): the routes' slopes join the operator.
    if n2 and forms_weight is not None:  # Version 1 (the parse refuses it first).
        raise ConfigError(forms_law.LAW_ID + " is refused under N2 in version 1")
    crossing = crosses_floating(structure)  # Fix (A) (D273, static): () for every other world.
    if n2:
        conductances, ok = operator_time_conductances(
            StepStart(state, first_values, start),
            control,
            p,
            dt,
            xp=xp,
            kinds=kinds,
            structure=structure,
        )
        valid &= ok
        laplacian = laplacian + conductance_laplacian(conductances, p, xp=xp)
        hook["conductances"] = conductances
    operator, ok = imex.factor_operator(coefficient, laplacian, p.boundary_V, f, xp=xp)
    valid &= ok
    rates, ok, *process = explicit_rates(state, start, control, p, xp=xp, **hook)
    processes += process
    explicit, implicit, valid = [rates], [None], valid & ok
    explicit_states = [state]  # Each explicit stage's state (gap 7's per-stage values).
    # Channel currents are explicit: refuse the step where their actual
    # conductance at an explicit stage exceeds the family's stability bound. Under N2 the
    # patches' and channels' slopes are implicit, so the rule counts the kinds' terms alone.
    valid &= dt * membrane_rate(
        state, control, p, xp=xp, structure=structure, potentials=start, explicit_only=n2
    ) <= (EXPLICIT_STEP_BOUND)
    material = material_rate(state, control, p, xp=xp, structure=structure, potentials=start)
    if material is not None:  # D4: a kind's material slope joins the same per-stage bound.
        valid &= dt * material <= EXPLICIT_STEP_BOUND
    # The start kinetics are the law's own (readouts at the start potentials).
    start_kinetics = (first_values.channel_targets, first_values.channel_tau_s)
    # (a)'s start: the junction law's kinetics at the start's junction voltages.
    if n2 and series_junctions(structure):  # FR-30: each gate's Rates at the start.
        voltage = xp.where(
            p.junction_active, start[p.junction_sender] - start[p.junction_receiver], 0.0
        )
        start_junction = series_kinetics(voltage, p, structure, xp=xp)
    else:  # Today's.
        start_junction = junction_voltage_kinetics(start, p, xp=xp)[1] if n2 else None
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
        scale = xp.maximum(  # Today's order of evaluation (crossrev compares the program text).
            xp.abs(charge), xp.abs(imex.operator_product(operator, potential, xp=xp))
        )
        valid &= xp.all(xp.isfinite(potential))
        valid &= xp.all(xp.abs(residual) <= field.CHARGE_ATOL_C + field.CHARGE_RTOL * scale)
        if n2:  # The routes' linear parts join the faces', their heat at the stage's state.
            drift = implicit_rates(weight, potential, state, p, xp=xp, conductances=conductances)
            stage = first._combine(known, dt, [(implicit_matrix[i, i], drift)])
            drift, ok = implicit_route_heat(
                drift, stage, conductances, potential, p, xp=xp, kinds=kinds
            )
            valid &= ok
        elif forms_weight is not None:  # The forms faces' electromigration beside the faces'.
            drift = implicit_rates(weight, potential, state, p, xp=xp, forms_weight=forms_weight)
        else:
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
        if n2:  # (a): the junction gates by their exponential update, as the channel gates.
            fraction = entity_sum(explicit_matrix[i], axis=None, xp=xp)
            moved, ok = stage_junctions(
                stage,
                state,
                start_junction,
                potential,
                control.junction,
                fraction,
                dt,
                p,
                xp=xp,
                structure=structure,
            )
            if crossing:  # Fix (A): the gates again, at the moved stage's quasi-static potentials.
                quasi, solved = crossing_potential(
                    moved, control, p, xp=xp, kinds=kinds, structure=structure
                )
                moved, ok = stage_junctions(
                    stage,
                    state,
                    start_junction,
                    quasi,
                    control.junction,
                    fraction,
                    dt,
                    p,
                    xp=xp,
                    structure=structure,
                )
                valid &= solved
            stage = moved
            valid &= ok
        elif series_junctions(structure):  # FR-30 (S2): the tableau moved the gates; the product.
            stage = series_stage(stage, state, p, xp=xp)
        if i < stages - 1:
            if crossing:  # Fix (A): the rates at the stage state's quasi-static potentials.
                at, solved = crossing_potential(
                    stage, control, p, xp=xp, kinds=kinds, structure=structure
                )
                valid &= solved
            else:
                at = potential
            rates, ok, *process = explicit_rates(stage, at, control, p, xp=xp, **hook)
            processes += process
            explicit.append(rates)
            explicit_states.append(stage)
            valid &= ok & (
                dt
                * membrane_rate(
                    stage,
                    control,
                    p,
                    xp=xp,
                    structure=structure,
                    potentials=potential,
                    explicit_only=n2,
                )
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
    if forms_weight is not None:  # Each mover's dissipation, J^2 RT / W >= 0, as the faces'.
        forms_flux = applied("forms_face_transferred")
        forms_heat = (
            1e-3
            * R
            * p.temperature
            * species_sum(
                xp.where(
                    forms_weight > 0,
                    forms_flux * forms_flux / xp.where(forms_weight > 0, forms_weight, 1.0),
                    0.0,
                ),
                xp=xp,
            )
        )
        stage = stage._replace(
            forms_face_dissipated_energy_pJ=state.forms_face_dissipated_energy_pJ + dt * forms_heat
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
    if exact_faces(structure):  # exact_free_energy_heat@1 (D280, a static choice).
        # Each face books its rows' exact free-energy release from the nodes' start and end
        # amounts, in place of the face heat above: no clamp, and no other form where a share
        # falls below its floor or a row's shares miss its exact change (the step is refused).
        release, booked = exact_face_heat(state, stage, p, xp=xp)
        valid &= booked
        stage = stage._replace(face_dissipated_energy_pJ=state.face_dissipated_energy_pJ + release)
    if p.junction_heat_trapezoid.shape[0]:  # trapezoid_nonnegative@1 (a static choice).
        # The tableau's explicit weights (delta, 1 - delta), delta < 0, book a negative
        # junction heat increment where a junction's power falls by more than 59% in a
        # step (its voltage crossing zero). This booking instead averages the start
        # and end states' junction powers, both >= 0 (sum_s J_s dmu_s with J_s and dmu_s
        # of one sign); the end state's at its last-stage potentials, which satisfy
        # C phi = its charges. Only this ledger changes: the state is the default's.
        end_power = junction_heat_rate(stage, potential, control, p, xp=xp)
        # Under N2 stage 0's explicit rates hold the remainder alone: the start's whole power.
        start_power = (
            junction_heat_rate(state, start, control, p, xp=xp)
            if n2
            else explicit[0].junction_dissipated_energy_pJ
        )
        stage = stage._replace(
            junction_dissipated_energy_pJ=state.junction_dissipated_energy_pJ
            + 0.5 * dt * (start_power + end_power)
        )
    booked = trapezoid_fields(structure)  # Seam D (§6.2): static; () by default.
    if booked:
        # The trapezoid, written once: each booked class's heat rates at the end state, at the
        # last-stage potentials, with the stage read and the routing door (explicit_rates, as at
        # every explicit stage), averaged with stage 0's. Only those heat fields change; the
        # state is the tableau's. Junctions keep their own switch above.
        whole = {k: v for k, v in hook.items() if k != "conductances"}  # N2: whole heat rates.
        at = potential
        if crossing:  # Fix (A): as every explicit stage's rates.
            at, solved = crossing_potential(
                stage, control, p, xp=xp, kinds=kinds, structure=structure
            )
            valid &= solved
        end_rates, end_ok, *_ = explicit_rates(stage, at, control, p, xp=xp, **whole)
        valid &= end_ok
        start_rates = explicit[0]
        if n2:  # Stage 0's explicit rates hold the remainder alone: the start's whole rates.
            start_rates, start_ok, *_ = explicit_rates(state, start, control, p, xp=xp, **whole)
            valid &= start_ok
        stage = stage._replace(
            **{
                k: getattr(state, k) + 0.5 * dt * (getattr(start_rates, k) + getattr(end_rates, k))
                for k in booked
            }
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
    extra = ()
    if labels is not None:  # FR-42 (static): the labelled rows' transfers; nothing else changes.
        routed = control
        if kinds and structure.routes:  # The routing door at the start, as readouts opens it.
            routed = _route(structure, kinds, read, control, p, xp=xp)[0]
        begin = LabelView(state, read, start, routed)
        if stages == 2 and not n2:  # The Euler IMEX: its one explicit stage, weights >= 0.
            terms = one_way_fluxes(begin, p, labels, xp=xp)
            weight = dt * explicit_matrix[last, 0]
            direct = {k: (weight * f, weight * b) for k, (f, b) in terms.items()}
            end, weighted = LabelView(stage), dict(weight=weight)
            transfers = step_transfers(begin, end, p, dt, labels, xp=xp, direct=direct)
        else:
            end, _ = crossing_view(stage, control, p, xp=xp, kinds=kinds, structure=structure)
            transfers, weighted = step_transfers(begin, end, p, dt, labels, xp=xp), {}
        gated = presence_gated(p, structure, xp=xp)  # The layout the kinds' rates see (Q2).
        for kind in kinds:  # D303 item 6: each reporting kind's transfers, after the core's.
            if kind.label_transfers is not None:
                transfers += tuple(
                    kind.label_transfers(begin, end, gated, dt, labels, xp=xp, **weighted)
                )
        extra = (transfers,)
    if membrane_process is None:
        kept = jax.tree.map(lambda old, new: xp.where(valid, new, old), state, stage)
        return (kept, valid, *extra)
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
    return (new, valid, (transfer, heat), *extra)


def junction_heat_rate(state, potential, control, p, *, xp=jnp):
    """Each junction's dissipation (pJ/s) at the given node potentials.

    The junction part of numerics/surface_transport.transport: constant-field
    flux (laws/junctions/selective.selective_flux) at the gated opening times the
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


def checked_step(state, dt, control, p, active, *, structure=None, labels=None):
    """RK4 for an empty tableau (reference runs); otherwise the declared IMEX step. With `labels`
    (FR-42) the IMEX step also returns its transfers; RK4 refuses them in version 1."""
    if p.imex_explicit.shape[0] == 0:
        if labels is not None:
            raise ConfigError(f"{FR42_REFUSAL}: RK4 refuses labels in version 1")
        if structure is None:
            return rk4_checked_step(rhs, domain_valid, state, dt, control, p, active)
        bound = _bound_checks(structure)
        return rk4_checked_step(bound.rhs, bound.domain_valid, state, dt, control, p, active)
    if labels is not None:
        return imex_step(state, dt, control, p, structure=structure, labels=labels)
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
    if structure is None and getattr(m, "heat_bookings", ()):
        # Seam D: the picks live in the structure, so a caller that ran @3 without one would book
        # the tableau silently; it refuses them instead. The water and replacement families run
        # @3 through compositions whose inner carries the structure, so they book the picks.
        raise ConfigError(
            "Heat bookings are @3's structure's (heat_bookings); this family runs @3 without "
            "one, so it refuses them"
        )
    if exact_faces(structure):  # D280: the faces' exact booking's scope (version 1).
        if getattr(m, "forms_faces", ()):
            raise ConfigError(
                f"{EXACT_FREE_ENERGY_HEAT} books today's faces' neutral rows; a world with "
                f"{forms_law.LAW_ID} faces books the tableau (version 1)"
            )
        _check_exact_faces(m)
    if getattr(m, "forms_faces", ()):  # The forms law's carriage (a one-ended binder, v1).
        problems = forms_law.carriage(m)[1]
        if problems:
            raise ConfigError(problems[0])
    kinds = _kinds(structure)
    for kind in kinds:  # §7.4 (k): a kind's definition checks, ahead of @3's.
        if kind.check_definition is not None:
            kind.check_definition(spec)
    _check_stage_rows(spec, kinds)
    _check_held_rows(spec, kinds)
    state, p = initial_values(compact, structure=structure)
    if series_junctions(structure) and np.any(getattr(p, "passive_on_junction", False)):
        raise ConfigError(  # FR-30, v1 (D262): the kinds' junction routes are not wired.
            f"A kind's passive route on a {SERIES_GATE_LAW_ID} junction takes its own route "
            "factor through the gates (its residuals per gate), never the ionic conductance; that "
            "route factor is not built (v1, D262)"
        )
    controls = control_values(compact, [c.time for c in compact.experiment.changes])
    control_type = kind_types(structure).Control if structure is not None else Control
    if kinds:
        _check_device_hooks(
            kinds,
            state,
            p,
            control_type(*(v[0] for v in controls)),
            ledgers=structure.kind_ledgers,
            tol=np.asarray(compact.execution.material_balance_atol_fmol),
        )
        _check_routes(spec, structure, kinds, state, p, control_type(*(v[0] for v in controls)))
        # The trace estimate counts every kind value a row holds (the third review's finding 3):
        # an undercount is refused, and an overcount is the safe direction (the lead's ruling).
        estimated = kind_row_values(compact)
        held = sum(
            int(np.size(getattr(state, name))) for kind in kinds for name, _ in kind.state_axes
        )
        if estimated < held:
            raise ConfigError(
                f"The trace estimate counts {estimated} kind state values per row, while the "
                f"bound state holds {held}: it would undercount the trace, so the definition is "
                "refused (a kind's own axis is sized by its view set)"
            )
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
    if kinds:  # The moved-rows guard, after the initial domain holds (its rates are defined).
        each = [control_type(*(v[i] for v in controls)) for i in range(len(controls.membrane))]
        _check_moved_rows(compact, structure, kinds, state, p, each)
        _check_presence(structure, kinds, state, p, each)  # Q2's contract (no program change).
        # Beside a closer, a kind with entities and no presence is the composite's refusal
        # (pump_composite_adapter.kind_lifecycle_errors): a composite's parse checks the inner
        # projection, whose structure declares no closer, so a check here would never fire.


# The moved-rows guard's perturbed state: each stored amount raised by up to this fraction of its
# reference, by a fixed pattern over (species, node), so a rate that moves a row only away from the
# initial concentrations is seen too.
GUARD_PERTURBATION = 0.1


def _perturbed(state, p):
    """The guard's second state: the initial amounts raised by a fixed pattern (all positive)."""

    def pattern(reference):
        s, n = np.indices(np.shape(reference))
        return GUARD_PERTURBATION * (1 + (7 * s + 3 * n) % 10) / 10 * np.asarray(reference)

    return state._replace(
        amount_increment=np.asarray(state.amount_increment) + pattern(p.amount_reference),
        extracellular_amount_increment=np.asarray(state.extracellular_amount_increment)
        + pattern(p.extracellular_amount_reference),
    )


def _check_moved_rows(spec, structure, kinds, state, p, controls):
    """The operators owner's ruling (CORE_SEAMS §18, amended at f609dd7f; the lead's ruling 3 (a)):
    a kind's rates move only the rows its `moved_rows` declares, since refusal 4 admits a kind by
    them (a source kind, which declares none, moves nothing). Checked on the host at binding, with
    no program change: each kind's rates at the stage read of the initial state and of a perturbed
    state (_perturbed), at every change record's control after the routing door and at the initial
    state's node potentials; a nonzero cell or outside change at a (species, node) its moved_rows
    does not name refuses the definition, naming the kind and the row. Not exhaustive: a rate that
    moves a row only at states neither reaches would pass; a run-time check is the later option."""
    movers = [kind for kind in kinds if kind.rates is not None]
    if not movers:
        return
    declarations, nodes = dict(spec.model.kinds), node_ids(spec)
    species = list(spec.model.species_ids)
    allowed = {}
    for kind in movers:
        mask = np.zeros((len(species), len(nodes)), dtype=bool)
        declaration = declarations[kind_registry.qualified(kind.kind_id)]
        declared = kind.moved_rows(declaration) if kind.moved_rows is not None else ()
        for entry in declared:
            mask[species.index(entry[0]), nodes.index(entry[1])] = True
        allowed[kind.kind_id] = mask
    with np.errstate(all="ignore"):
        potentials = readouts(state, controls[0], p, xp=np, structure=structure).field.potential_V
        for x in (state, _perturbed(state, p)):
            read, _ = _stage_read(x, p, kinds, xp=np)
            for control in controls:
                routed, _ = _route(structure, kinds, read, control, p, xp=np)
                for kind, rates in zip(
                    movers, _kind_rates(movers, read, potentials, routed, p, xp=np), strict=True
                ):
                    moved = np.concatenate(
                        (np.asarray(rates.cell), np.asarray(rates.outside)), axis=1
                    )
                    stray = np.argwhere((moved != 0) & ~allowed[kind.kind_id])
                    if len(stray):
                        row, node = stray[0]
                        raise ConfigError(
                            f"Kind {kind.kind_id}'s rates move {species[row]} at "
                            f"{nodes[node]}, which its moved_rows does not declare (refusal 4 "
                            "admits a kind by its moved_rows)"
                        )


def _check_presence(structure, kinds, state, p, controls):
    """Q2's contract (CORE_SEAMS §18 at 931b6606): a kind that declares presence fields gives
    exactly zero rates, readouts and stage terms with every entity absent, since the presence gate
    (presence_gated) closes an entity by making it absent. Checked on the host at binding, with no
    program change: each such kind with every presence field false, at the initial state's stage
    read and node potentials and at every change record's control after the routing door; any
    nonzero value (a move, a derivative, a heat, work, stored or patch flux rate, a readout
    column, a stage or material term) refuses the definition, naming the kind and what does not
    vanish."""
    declared = [(kind, kind_registry.presence_fields(kind)) for kind in kinds]
    declared = [(kind, fields) for kind, fields in declared if fields]
    if not declared:
        return
    with np.errstate(all="ignore"):
        potentials = readouts(state, controls[0], p, xp=np, structure=structure).field.potential_V
        for kind, fields in declared:
            names = [name for group in fields.values() for name in group]
            loose = [n for n in names if np.asarray(getattr(p, n)).dtype != np.bool_]
            if loose:  # F's declaration says fill False; the gate ands, so it binds bool masks.
                raise ConfigError(
                    f"Kind {kind.kind_id}'s presence fields {', '.join(loose)} bind "
                    f"{', '.join(str(np.asarray(getattr(p, n)).dtype) for n in loose)} arrays, "
                    "not bool masks (Q2's presence gate ands them)"
                )
            absent = p._replace(
                **{name: np.zeros(np.shape(getattr(p, name)), dtype=bool) for name in names}
            )
            read, _ = _stage_read(state, absent, kinds, xp=np)
            found = set()
            for control in controls:
                routed, _ = _route(structure, kinds, read, control, absent, xp=np)
                values = {}
                if kind.rates is not None:
                    kr = kind.rates(read, potentials, routed, absent, xp=np)
                    values.update(
                        {
                            "rates' cell moves": kr.cell,
                            "rates' outside moves": kr.outside,
                            "rates' heat": kr.heat_pJ_s,
                            "rates' work": kr.work_pJ_s,
                            "rates' patch flux": kr.membrane_flux,
                            "rates' stored rate": kr.stored_pJ_s,
                        }
                    )
                    values.update({f"derivative of {k}": v for k, v in kr.derivatives.items()})
                if kind.readouts is not None:
                    columns = kind.readouts(state, read, potentials, routed, absent, xp=np)
                    values.update({f"readout column {i}": c for i, c in enumerate(columns)})
                for hook in ("stage_term", "material_term"):
                    term = getattr(kind, hook)
                    if term is not None:
                        values[hook] = term(read, potentials, routed, absent, xp=np)
                found |= {
                    what
                    for what, value in values.items()
                    if value is not None and np.any(np.asarray(value) != 0)
                }
            if found:
                raise ConfigError(
                    f"Kind {kind.kind_id} declares presence fields "
                    f"({', '.join(names)}), but with every entity absent its "
                    + ", ".join(sorted(found))
                    + " do not vanish (the presence gate closes an entity by its absence)"
                )


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
    reads on a shared row are refused at binding (until a dependency order exists). A row is
    (species, node ID), or (species, node ID, the read's law ID): the third item is P1's selector
    (CORE_SEAMS §17; the binding owner's ruling (a), 19 November 2026). Rows are shared by their
    (species, node), whatever law each names.

    P1's predictor takes a stage read whole, so two more refusals hold until a world needs them:
    a read whose rows name a law that declares free_amounts on some rows and not on others, and a
    free-amount read beside another kind's read of today's form."""
    if not kinds:
        return
    declarations, claimed, laws = dict(spec.model.kinds), {}, law_registry.active()
    forms = {True: [], False: []}  # P1's form, or today's: the kinds whose reads hold rows.
    for kind in kinds:
        if kind.stage_read is None:
            continue
        if kind.stage_rows is None:
            raise ConfigError(f"Kind {kind.kind_id} has a stage read but declares no stage rows")
        marks = set()
        for row in kind.stage_rows(declarations[kind.kind_id]):
            row = tuple(row)
            if len(row) not in (2, 3):
                raise ConfigError(
                    f"Kind {kind.kind_id}'s stage row {row} is not (species, node ID) or "
                    "(species, node ID, the read's law ID)"
                )
            other = claimed.setdefault(row[:2], kind.kind_id)
            if other != kind.kind_id:
                raise ConfigError(
                    f"Kinds {other} and {kind.kind_id} both read row {row[:2]} at each stage; "
                    "stage reads on a shared row do not commute and are refused"
                )
            marks.add(reads_free_amounts(row, laws))
        if len(marks) > 1:
            raise ConfigError(
                f"Kind {kind.kind_id}'s stage rows name a law that declares free_amounts on some "
                "rows and not on others; P1's predictor takes a stage read whole, so it is refused"
            )
        for mark in marks:
            forms[mark].append(kind.kind_id)
    if forms[True] and forms[False]:
        raise ConfigError(
            f"P1's predictor reads {forms[True][0]}'s stage read at the predicted totals, while "
            f"{forms[False][0]}'s read keeps today's form; the two together are refused until a "
            "world needs them"
        )


def moved_nodes(model):
    """{(species, node ID): (mover, ...)} of every in-step mover of the inner model, from
    moved_rows: each route's two end nodes (a channel's or a pump's, its patch's), and a kind's
    named nodes. A mover is named "<mover kind> <entity>" (a kind's: its kind ID)."""
    ends = {m.id: (m.inside, m.outside) for m in model.membranes}
    ends |= {j.id: (j.sender, j.receiver) for j in model.junctions}
    ends |= {f.id: (f.sender, f.receiver) for f in model.faces}
    ends |= {f.id: (f.sender, f.receiver) for f in getattr(model, "forms_faces", ())}
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


def _check_device_hooks(kinds, state, p, control, *, ledgers=(), tol=None):
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
        own = [ledger for ledger, _ in dict(ledgers).get(kind_registry.qualified(kind.kind_id), ())]
        if own and kind.ledger_terms is None:
            refuse(kind, "ledger_terms", f"is missing, so it values none of its ledgers {own}")
        if kind.ledger_terms is not None:
            terms = traced(kind, "ledger_terms", partial(kind.ledger_terms, xp=jnp), state, p)
            unknown = set(terms) - set(LEDGER_TERM_KEYS) - set(own)
            if unknown:
                refuse(kind, "ledger_terms", f"returns unknown terms {sorted(unknown)}")
            for key, shape in shapes.items():
                if key in terms and tuple(terms[key].shape) != shape:
                    refuse(kind, "ledger_terms", f"returns {key} of shape {terms[key].shape}")
            missing = [ledger for ledger in own if ledger not in terms]
            if missing:  # E (§7.3): each declared ledger is valued under its own name.
                refuse(kind, "ledger_terms", f"values none of its declared ledgers {missing}")
        if own:  # Its bounds: one per ledger, each broadcasting against its value.
            bound = partial(kind.ledger_bounds, xp=jnp)
            bounds = traced(kind, "ledger_bounds", bound, state, p, tol, 0)
            if not (isinstance(bounds, tuple) and len(bounds) == len(own)):
                refuse(kind, "ledger_bounds", f"must return one bound per ledger ({len(own)})")
            for ledger, limit in zip(own, bounds, strict=True):
                shape = tuple(terms[ledger].shape)
                if np.broadcast_shapes(shape, tuple(limit.shape)) != shape:
                    refuse(kind, "ledger_bounds", f"bounds {ledger} with shape {limit.shape}")


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


def membrane_rate(
    state, control, p, *, xp=jnp, structure=None, potentials=None, explicit_only=False
):
    """Gershgorin rate (1/s) of membrane charge relaxation at a stage's actual openings.

    @1's membrane term, max_i sum_m G_m / C_i, with each population's open
    constant-field slope conductance F^2/RT sum z^2 P r a o v A max(c) added to
    its patch (o its opening, v its availability). max(c) bounds the
    constant-field slope, so this bounds the explicit channel stiffness.
    Quasi-steady gating slopes are not included; the step studies measure them.
    A channel population that the routing door factors (B1, docs/CORE_SEAMS_DESIGN.md §4.3) enters
    at its held availability: its factors are at most 1, so the held value bounds the routed one
    (conservative), and the door's order here stays the kinds' (after this term).
    explicit_only (N2, D235): the patches' and channels' terms are left out, since their slopes
    sit in the operator; the declared kinds' terms remain, and without kinds the rate is 0.
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
    if explicit_only:  # N2 (static): the patches' and channels' slopes are implicit.
        membrane = xp.zeros_like(membrane)
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
    gated = presence_gated(p, structure, xp=xp)  # Q2 (static).
    for kind in kinds:
        if kind.stage_term is not None:
            nodes = nodes + kind.stage_term(read, potentials, control, gated, xp=xp)
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
    gated = presence_gated(p, structure, xp=xp)  # Q2 (static).
    for kind in sloped:
        nodes = nodes + kind.material_term(read, potentials, control, gated, xp=xp)
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
    if _has_forms(p):  # A forms face's ends are faced too: its electromigration is implicit.
        forms = xp.where(p.forms_face_active, 1.0, 0.0)
        named = named + scatter(forms, zero, (p.forms_face_sender,), xp=xp)
        named = named + scatter(forms, zero, (p.forms_face_receiver,), xp=xp)
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
    index: int  # Its row of the host table of this spec's layout (it depends on the capacities).
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
    """{host ID: Host} of every declared patch and junction, on the host side.

    A row belongs to one spec's layout: a junction's is membrane_capacity + its position, so it
    follows the execution's capacities. A kind resolves its hosts' rows in `initial(spec, ...)`,
    whose spec is the one its layout is built for, and never keeps a row in its declaration:
    `parse` sees the definition's capacities, while check_definition binds a compact copy."""
    m, offset = spec.model, spec.execution.membrane_capacity
    out = {p.id: Host(p.id, "patch", i, p.inside, p.outside) for i, p in enumerate(m.membranes)}
    for i, j in enumerate(m.junctions):
        out[j.id] = Host(j.id, "junction", offset + i, j.sender, j.receiver)
    return out


def host_index(spec, host_id):
    """The host-table row of a declared patch or junction in this spec's layout (declared_hosts:
    resolve it in a kind's `initial`); ConfigError for any other ID."""
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


def implicit_conductance_rate_bound(spec):
    """N2's definition-time explicit-rate bound (1/s, D235): surface_pump.explicit_rate_bound's
    terms for what stays explicit when the patches' and junctions' slopes sit in the operator.
    - The face-diffusion term stays as it is.
    - The membrane and junction charge terms, and the face-free node's (B7), leave: those charge
      modes are implicit.
    - Every species' material relaxation through patches and junctions stays explicit, since the
      remainder J - W dv carries the concentrations: neutral_material_rate's form, taken over
      every species, each patch's side weighted by its constant-field factor (B(-x) on the cell's,
      B(x) on the outside's, x = z F V/RT at the declared patch voltage). Junctions join cells
      near one potential and take the neutral factor 1. For a charged species this term is
      smaller than its charge term by about F^2 c V/(RT C) (about 10^4 in a cell)."""
    from cells.laws.electrochemistry import bernoulli

    _, p = kinetic.initial_values(spec)
    volume = np.where(p.outside_active & ~p.reservoir, p.extracellular_volume * 1e-15, np.inf)
    zero = np.zeros((len(p.valence), p.outside_active.size))
    rows = scatter(p.face_factor, zero, (p.face_sender,), xp=np)
    rows += scatter(p.face_factor, zero, (p.face_receiver,), xp=np)
    face = 2 * np.max(rows / volume, initial=0.0)
    species = np.asarray(p.valence).reshape(-1).size
    cell_volume = np.where(p.active, p.volume * 1e-15, np.inf)
    x = (
        np.asarray(p.valence).reshape(-1, 1)
        * F
        * np.where(p.membrane_active, p.initial_membrane_voltage_V, 0.0)
        / (R * p.temperature)
    )
    pm = p.membrane_permeability * np.where(p.membrane_active, p.membrane_area, 0.0)
    pj = p.junction_permeability * np.where(p.junction_active, p.junction_area, 0.0)
    cells = scatter(pm * bernoulli(-x, xp=np), np.zeros((species, p.active.size)),
                    (p.membrane_cell,), xp=np)  # fmt: skip
    cells += scatter(pj, np.zeros((species, p.active.size)), (p.junction_sender,), xp=np)
    cells += scatter(pj, np.zeros((species, p.active.size)), (p.junction_receiver,), xp=np)
    outside = scatter(pm * bernoulli(x, xp=np), np.zeros((species, p.outside_active.size)),
                      (p.membrane_outside,), xp=np)  # fmt: skip
    material = 2 * float(
        np.max(np.concatenate((cells / cell_volume, outside / volume), axis=1), initial=0.0)
    )
    return max(face, material)


def forms_rate_bound(spec):
    """The forms faces' explicit diffusion bound (1/s), the face term of
    surface_pump.explicit_rate_bound with the forms faces: 2 max over rows and finite outside nodes
    of the D A / (L V) of every face that moves the row there, today's and the forms faces'. A
    binder's forms move at its row's diffusivity (one class), so each form's term is its row's (the
    face note's §4: the face's explicit bound joins the per-stage bound per form)."""
    m = spec.model
    oids = [o.id for o in m.extracellular]
    volume = np.asarray([np.inf if o.reservoir else o.volume_pL * 1e-15 for o in m.extracellular])
    plain = np.zeros((len(m.species_ids), len(oids)))
    for face in m.faces:
        factor = np.asarray(face.diffusivity_m2_per_s) * face.area_m2 / face.length_m
        plain[:, oids.index(face.sender)] += factor
        plain[:, oids.index(face.receiver)] += factor
    rows = np.zeros_like(plain)  # Each row's forms faces, as itself or as its forms (one class).
    for face in m.forms_faces:
        factor = np.asarray(face.diffusivity_m2_per_s) * face.area_m2 / face.length_m
        rows[:, oids.index(face.sender)] += factor
        rows[:, oids.index(face.receiver)] += factor
    return 2 * float(np.max((rows + plain) / volume, initial=0.0))


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
        if self.spec.execution.solver in imex.IMPLICIT_CONDUCTANCE_IDS:  # N2: what stays explicit.
            return implicit_conductance_rate_bound(self.base)
        if getattr(self.spec.model, "forms_faces", ()):  # The forms faces' per-mover term too.
            with forms_return_paths(self.spec.model):  # The projection's binding sees them.
                base = first.explicit_rate_bound(self.base)
            return max(base, forms_rate_bound(self.spec))
        return first.explicit_rate_bound(self.base)

    @cached_property
    def calcium_rate(self):
        with forms_return_paths(self.spec.model):  # Nothing set without forms faces.
            return second.calcium_rate_bound(self.base)

    @cached_property
    def gated_laws(self):
        return {c.kinetic_law for c in self.spec.model.channels if c.initial_gate}

    @cached_property
    def rk4_bound(self):
        """(the smallest declared rk4_step_s over the world's gated laws, a law that has it), or
        None without gated laws: each law's declaration holds its reference RK4 step bound."""
        laws = channel_laws()
        unbounded = sorted(law for law in self.gated_laws if laws[law].rk4_step_s is None)
        if unbounded:  # Fail closed: a gated law without its bound runs on no RK4 grid.
            return (0.0, unbounded[0])
        bounds = sorted((laws[law].rk4_step_s, law) for law in self.gated_laws)
        return bounds[0] if bounds else None

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

    @cached_property
    def junction_rate(self):
        """The junction gates' relaxation-rate bound: the one-gate law's (first's), or each series
        gate's largest over the voltage domain (FR-30)."""
        if declares_series_junctions(self.spec.model):
            return series_rate_bound(self.spec)
        return first.junction_gate_rate_bound(self.spec)

    def __call__(self, steps):
        spec, step = self.spec, np.max(steps, initial=0)
        if declares_series_junctions(spec.model):  # FR-30, v1 (D262).
            if spec.execution.solver == "rk4":
                raise ConfigError(SERIES_RK4_REFUSAL)
            if getattr(spec, "projective", None) is not None:
                raise ConfigError(SERIES_PROJECTIVE_REFUSAL)
        if getattr(spec.model, "forms_faces", ()):  # The forms law, version 1.
            if getattr(spec, "projective", None) is not None:
                raise ConfigError(FORMS_PROJECTIVE_REFUSAL)
            if spec.execution.solver not in (imex.EULER_ID, imex.ARS222_ID):
                raise ConfigError(forms_law.LAW_ID + " runs on the plain IMEX tableaux (v1)")
        if spec.execution.solver == "rk4":
            tissue.check_steps(spec, steps, None)
            laws, bound = self.gated_laws, self.rk4_bound
            if NAV1P2_LAW_ID in laws and step > RK4_SODIUM_STEP + 1e-16:
                raise ConfigError("Resolved NaV1.2 channels require RK4 steps <= 2.5 us")
            if bound is not None and step > bound[0] + 1e-16:  # Each gated law's own bound.
                if bound[0] == RK4_POTASSIUM_STEP:
                    raise ConfigError("Resolved gated channels require RK4 steps <= 25 us")
                raise ConfigError(
                    f"Resolved gated channels ({bound[1]}) require RK4 steps <= "
                    f"{bound[0] * 1e6:g} us"
                )
        else:
            if (
                spec.execution.solver in imex.IMPLICIT_CONDUCTANCE_IDS
                and getattr(spec, "energy_check", None) is None
            ):  # N2's guard (RUNG1 §2, D235): no coarse step runs without X2.
                raise ConfigError(
                    f"{spec.execution.solver} runs only with execution.energy_check "
                    "step_doubled_energy@1 selected"
                )
            self.require_accepted_observations()
            if step * self.explicit_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the explicit-rate stability bound")
            if step * self.calcium_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the explicit calcium pump rate bound")
            if step * self.kind_rate > EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds a declared kind's explicit-rate bound")
        if (
            spec.execution.solver not in imex.IMPLICIT_CONDUCTANCE_IDS
            and step * self.junction_rate > first.GATE_STEP_BOUND
        ):  # N2's (a) advances the junction gates by their exponential update: no gate bound.
            raise ConfigError("Resolved junction step exceeds conservative kinetic bound")


def balances(state, p, *, structure=None):
    total = state.membrane_transferred + channel_to_membrane(state.channel_transferred, p, xp=np)
    result = second.balances(state._replace(membrane_transferred=total), p)
    result["energy"] += entity_sum(
        species_sum(state.channel_dissipated_energy_pJ, xp=np), axis=None, xp=np
    )
    if forms_faces_declared(structure):
        _fold_forms_ledgers(result, state, p, xp=np)
    if structure is not None and structure.kinds:
        _fold_kind_ledgers(
            result, state, p, _kinds(structure), xp=np, ledgers=structure.kind_ledgers
        )
    return result


def forms_row_transfers(state, p, *, xp):
    """[species, forms face] each forms face's cumulative row transfer, sender -> receiver: its
    movers' cumulative transfers through their stoichiometry, folded over the movers in order."""
    moved = p.forms_face_stoichiometry[:, :, None] * state.forms_face_transferred[:, None, :]
    return species_sum(moved, xp=xp)


def _fold_forms_ledgers(result, state, p, *, xp):
    """The forms faces' terms in today's ledgers, as the faces' (surface_tissue.balances): their
    rows' cumulative transfers close each outside node's material ledger (out of the sender, into
    the receiver; a held bath's through its supply, which the step books), and their heat joins the
    energy ledger's dissipation."""
    rows = forms_row_transfers(state, p, xp=xp)
    zero = xp.zeros_like(state.extracellular_amount_increment)
    into = scatter(rows, zero, (p.forms_face_receiver,), xp=xp) - scatter(
        rows, zero, (p.forms_face_sender,), xp=xp
    )
    result["outside"] = result["outside"] - into
    result["energy"] = result["energy"] + entity_sum(
        state.forms_face_dissipated_energy_pJ, axis=None, xp=xp
    )


def _fold_kind_ledgers(result, state, p, kinds, *, xp, ledgers=()):
    """Rule (a): each kind's ledger terms fold into today's ledgers by role. Its cumulative
    inward-positive node transfers close the material ledgers (they are in the amounts, rule
    (c)); its heat and work accumulators join the energy ledger as dissipation and work; its
    stored term (free energy it holds beyond the stored rows' own terms, since the start: FR-4's
    buffer term, finite fuel's standard term) joins the stored energy. Its net production per
    species (`produced`, a reaction's record: finite fuel's ATP -> ADP + Pi) joins the global
    material ledger, which otherwise holds every kind to transfers (§7.4 (m)).

    E (§7.3): `ledgers`, the structure's kind_ledgers, then appends each kind's own ledgers after
    today's ten, in that order, each valued by the kind's ledger_terms under its own name (a
    moiety's Σ w x net production, say). () adds none, so today's balances are unchanged."""
    terms_of = {}
    for kind in kinds:
        if kind.ledger_terms is None:
            continue
        terms = terms_of[kind_registry.qualified(kind.kind_id)] = kind.ledger_terms(state, p, xp=xp)
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
    for kind_id, pairs in ledgers:
        terms = terms_of[kind_registry.qualified(kind_id)]
        for ledger, _ in pairs:
            result[ledger] = terms[ledger]


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
    if forms_faces_declared(structure):  # The forms faces' row transfers, at both their ends.
        moved = species_sum(
            xp.abs(p.forms_face_stoichiometry)[:, :, None]
            * xp.abs(row.forms_face_transferred)[:, None, :],
            xp=xp,
        )
        zero = xp.zeros_like(row.extracellular_amount_increment)
        index = ledger_lists(structure).LEDGERS.index("outside")
        magnitudes = list(magnitudes)
        magnitudes[index] = (
            magnitudes[index]
            + scatter(moved, zero, (p.forms_face_sender,), xp=xp)
            + scatter(moved, zero, (p.forms_face_receiver,), xp=xp)
        )
        magnitudes = tuple(magnitudes)
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
# Seam D (docs/CORE_SEAMS_DESIGN.md §6.1-6.2): the heat fields of @3's own mover classes, which a
# booking other than the tableau books. Junctions keep their own switch (junction_heat_booking,
# the layout's junction_heat_trapezoid), so they are not listed here.
OWN_HEAT_FIELDS = MappingProxyType(
    {
        inner_laws.CHANNELS: ("channel_dissipated_energy_pJ",),
        inner_laws.MEMBRANES: ("membrane_dissipated_energy_pJ",),
        inner_laws.PUMPS: ("pump_dissipated_energy_pJ",),
        inner_laws.CALCIUM_PUMPS: ("calcium_pump_dissipated_energy_pJ",),
    }
)


def trapezoid_fields(structure):
    """The heat fields the step books by trapezoid_nonnegative@1 (seam D, §6.2), in the
    structure's class order: each picked own class's (OWN_HEAT_FIELDS), and each picked kind's
    state fields whose energy role is heat (kind_registry.energy_role). () by default, so the
    step's branch is static and today's programs are unchanged. A kind that admits another
    booking books it itself."""
    if structure is None or not structure.heat_bookings:
        return ()
    kinds = {kind_registry.qualified(kind.kind_id): kind for kind in _kinds(structure)}
    out = []
    for mover, booking in structure.heat_bookings:
        if booking != TRAPEZOID_JUNCTION_HEAT or mover == inner_laws.JUNCTIONS:
            continue
        if mover in OWN_HEAT_FIELDS:
            out += OWN_HEAT_FIELDS[mover]
            continue
        kind = kinds[mover]
        out += [
            name
            for name in kind.state_fields
            if (role := kind_registry.energy_role(kind, name)) is not None and role.role == "heat"
        ]
    return tuple(out)


# exact_free_energy_heat@1 on @3's faces (D280; docs/CORE_SEAMS_DESIGN.md §6.5): the passive
# routes' booking of INNER_MODEL_V4_DESIGN §7.5, version 1, for faces. Its sign rule's and raw-sum
# bound's factor is the passive routes' (kinds/passive_routes.RAW_SUM_FACTOR).
EXACT_FACE_RAW_SUM_FACTOR = 16.0


def exact_faces(structure):
    """Whether the structure picks exact_free_energy_heat@1 for @3's faces: a static switch,
    False for every definition that does not list it, so today's programs are unchanged."""
    return structure is not None and (
        (inner_laws.FACES, EXACT_FREE_ENERGY_HEAT) in structure.heat_bookings
    )


def _check_exact_faces(model):
    """The faces' exact booking's scope (version 1, as the passive routes'): every row a face
    carries (a species with a positive diffusivity on it, at each of its end nodes) is neutral,
    lies at two finite nodes (a held bath's row is never one) and is moved in the step by faces
    alone (moved_nodes). Operators' in-step writers are the composite's admission
    (pump_composite.exact_face_row_errors)."""
    valence = dict(zip(model.species_ids, model.valence, strict=True))
    held = {o.id for o in model.extracellular if o.reservoir}
    movers = moved_nodes(model)
    for face in model.faces:
        for species, diffusivity in zip(model.species_ids, face.diffusivity_m2_per_s, strict=True):
            if not diffusivity:
                continue
            if valence[species]:
                raise ConfigError(
                    f"Face {face.id} carries the charged row {species}; "
                    f"{EXACT_FREE_ENERGY_HEAT} books neutral rows only (version 1)"
                )
            bath = next((n for n in (face.sender, face.receiver) if n in held), None)
            if bath is not None:
                raise ConfigError(
                    f"Face {face.id} carries {species} to the held bath {bath}; "
                    f"{EXACT_FREE_ENERGY_HEAT} books faces between finite nodes (version 1)"
                )
            for node in (face.sender, face.receiver):
                others = [w for w in movers.get((species, node), ()) if not w.startswith("face ")]
                if others:
                    raise ConfigError(
                        f"Face {face.id} carries {species} at {node}, which {others[0]} also "
                        f"moves in the step; {EXACT_FREE_ENERGY_HEAT} books rows that faces "
                        "alone move (version 1)"
                    )


def exact_face_heat(start, end, p, *, xp=jnp):
    """exact_free_energy_heat@1 over one step: (each face's heat [face] in pJ, booked), from the
    step's start and end states.

    Each face's share of a row it carries is the amount it moved, sender to receiver, times the
    difference of the row's divided-difference potentials at its two ends, each from that node's
    start and end amounts in the ledger's own form (passive_permeation.divided_potential_RT):
    Q = 1e-3 RT moved (mu-bar_sender - mu-bar_receiver). Where faces alone move a row (the
    definition's check, which also keeps held baths out), a node's shares sum to its exact
    free-energy change, so the energy ledger closes to rounding for those rows.

    booked is False, and the step refused, where a share lies below its floor,
    -RAW_SUM_FACTOR eps (|mu-bar_s| + |mu-bar_r| + 2) |moved| RT (the passive routes' sign rule,
    INNER_MODEL_V4_DESIGN §7.5 as amended 17 November 2026), or where a finite node's shares miss
    its exact change by more than RAW_SUM_FACTOR eps times its terms and its inputs' rounding (the
    raw-sum bound). No clamp and no other form: a falling face heat is also the dissipation
    check's."""
    s = tissue.field_layout(p).surface
    eps = np.finfo(float).eps
    volume = xp.where(p.outside_active, p.extracellular_volume, 1.0)[None, :]
    reference = xp.where(p.outside_active, p.extracellular_amount_reference, 1.0)
    i0, i1 = start.extracellular_amount_increment, end.extracellular_amount_increment
    n0, n1 = reference + i0, reference + i1
    mu = exact_kernel.divided_potential_RT(n0, n1, volume, xp=xp)  # [species, outside node]
    carried = s.face_active[None, :] & (s.face_factor > 0)  # [species, face]
    moved = xp.where(carried, end.face_transferred - start.face_transferred, 0.0)
    mu_s, mu_r = mu[:, s.face_sender], mu[:, s.face_receiver]
    shares = 1e-3 * R * p.temperature * moved * (mu_s - mu_r)
    terms = (xp.abs(mu_s) + xp.abs(mu_r) + 2.0) * xp.abs(moved)  # RT fmol.
    floor = -(EXACT_FACE_RAW_SUM_FACTOR * eps * 1e-3 * R) * p.temperature * terms
    positive = xp.all(xp.where(carried, shares >= floor, True))
    zero = xp.zeros_like(n0)

    def at_ends(values):  # [species, face] -> [species, outside node], at both ends of each face.
        return scatter(values, zero, (s.face_sender,), xp=xp) + scatter(
            values, zero, (s.face_receiver,), xp=xp
        )

    # Raw sums at each node a face carries a row to (finite nodes, by the definition's check; a held
    # bath's change would be its supply): the shares' potential times the faces' net change,
    # against the row's exact change of G.
    rows = (at_ends(xp.where(carried, 1.0, 0.0)) > 0) & ~p.reservoir[None, :]
    safe0, safe1 = xp.where(n0 > 0, n0, 1.0), xp.where(n1 > 0, n1, 1.0)
    g0 = xp.where(n0 > 0, n0 * (xp.log(safe0 / volume) - 1.0), 0.0)
    g1 = xp.where(n1 > 0, n1 * (xp.log(safe1 / volume) - 1.0), 0.0)
    net = scatter(moved, zero, (s.face_receiver,), xp=xp) - scatter(
        moved, zero, (s.face_sender,), xp=xp
    )
    residual = xp.abs(mu * net - (g1 - g0))
    own = (
        xp.abs(g0)
        + xp.abs(g1)
        + scatter(xp.abs(mu_s * moved), zero, (s.face_sender,), xp=xp)
        + scatter(xp.abs(mu_r * moved), zero, (s.face_receiver,), xp=xp)
    )
    cumulative = xp.where(
        carried, xp.abs(start.face_transferred) + xp.abs(end.face_transferred), 0.0
    )
    inputs = xp.abs(mu) * (xp.abs(n0) + xp.abs(n1) + xp.abs(i0) + xp.abs(i1) + at_ends(cumulative))
    within = xp.all(
        xp.where(rows, residual <= EXACT_FACE_RAW_SUM_FACTOR * eps * (own + inputs), True)
    )
    heat = species_sum(xp.where(carried, shares, 0.0), xp=xp)  # A7: the species fold.
    return heat, positive & within


def check_values(state, spec, steps=None, *, structure=None):
    """The family's host checks (surface_pump.checked_rows) with the channel ledgers."""
    _, p = initial_values(spec, structure=structure)
    kinds = structure is not None and bool(structure.kinds or structure.forms_faces)
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
    """The heat fields the dissipation check holds non-negative and non-decreasing per element,
    on the host and the device, in the structure's state order: @3's own *_dissipated_energy_pJ
    fields, and each declared kind's fields whose energy role is heat and monotone (seam D,
    §6.1: a declaration, else today's suffix rule, kind_registry.energy_role). A heat declared
    non-monotone stays among the energy flows but leaves this check; a stored field is a level,
    in neither."""
    if structure is None or not (structure.kinds or structure.forms_faces):
        return DISSIPATION_FIELDS
    own = set(STATE_AXES) | set(FORMS_STATE_AXES)  # The forms faces' heat is @3's own.
    roles = {}
    for kind in _kinds(structure):
        for name in kind.state_fields:
            roles[name] = kind_registry.energy_role(kind, name)
    out = []
    for k in kind_types(structure).STATE_AXES:
        if k in own:
            if k.endswith("_dissipated_energy_pJ"):
                out.append(k)
        elif (role := roles.get(k)) is not None and role.role == "heat" and role.monotone:
            out.append(k)
    return tuple(out)


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
    DEVICE_DIAGNOSTICS built from them. A structure whose kinds declare no ledger of their own
    has today's: @1's own objects, so its programs are unchanged. Each declared kind's own ledgers
    (E, CORE_SEAMS §7.3; InnerStructure.kind_ledgers) follow @1's ten, in the structure's order:
    their names and diagnostics, their bounds through ledger_limits (the kind's ledger_bounds) and
    their values through balances (the kind's ledger_terms under the same names), which the shared
    check paths take with no edit. None is the module's."""
    names = LEDGER_NAMES + ("DEVICE_CHECKS", "DEVICE_DIAGNOSTICS")
    if structure is None or not structure.kind_ledgers:
        return SimpleNamespace(**{name: getattr(first, name) for name in names})
    own = [pair for _, pairs in structure.kind_ledgers for pair in pairs]
    ledgers = (*first.LEDGERS, *(ledger for ledger, _ in own))
    diagnostics = (*first.LEDGER_DIAGNOSTICS, *(diagnostic for _, diagnostic in own))
    after = first.DEVICE_DIAGNOSTICS[len(first.LEDGER_DIAGNOSTICS) :]  # The two ratios.
    return SimpleNamespace(
        LEDGERS=ledgers,
        LEDGER_DIAGNOSTICS=diagnostics,
        ledger_limits=partial(_kind_ledger_limits, structure=structure),
        ENERGY_RTOL=first.ENERGY_RTOL,
        DEVICE_CHECKS=("domain", *ledgers, "dissipation"),
        DEVICE_DIAGNOSTICS=(*("max_" + k for k in diagnostics), *after),
    )


def _kind_ledger_limits(
    row, p, tol, rtol, *, steps, magnitudes, xp=np, flow_fields=None, structure
):
    """surface_pump.ledger_limits, then each declared kind's own ledgers' bounds, its
    ledger_bounds(row, p, tol, steps, *, xp), in the structure's order (E, §7.3): functions of the
    row and the layout at check time, one per ledger."""
    flows, bounds = first.ledger_limits(
        row, p, tol, rtol, steps=steps, magnitudes=magnitudes, xp=xp, flow_fields=flow_fields
    )
    kinds = {kind_registry.qualified(kind.kind_id): kind for kind in _kinds(structure)}
    extra = []
    for kind_id, pairs in structure.kind_ledgers:
        own = tuple(
            kinds[kind_registry.qualified(kind_id)].ledger_bounds(row, p, tol, steps, xp=xp)
        )
        if len(own) != len(pairs):
            raise ValueError(
                f"Kind {kind_id}'s ledger_bounds gives {len(own)} bounds for {len(pairs)} ledgers"
            )
        # A kind's bound that is not finite would admit any residual (|r| > NaN or +inf is
        # false): it becomes -inf, which no residual passes, on the host and the device (the
        # fourth review's finding 2). An operator's and @1's own bounds are not mapped: the gap
        # that leaves on the device is stated at surface_pump_checks.row_checks' comparison.
        extra.extend(xp.where(xp.isfinite(bound), bound, -xp.inf) for bound in own)
    return flows, (*bounds, *extra)


def device_balances(state, p, *, structure=None):
    """balances() with jax.numpy: the same channel terms, then @2's, in the same order."""
    total = state.membrane_transferred + channel_to_membrane(state.channel_transferred, p, xp=jnp)
    result = second.device_balances(state._replace(membrane_transferred=total), p)
    result["energy"] += entity_sum(
        species_sum(state.channel_dissipated_energy_pJ, xp=jnp), axis=None, xp=jnp
    )
    if forms_faces_declared(structure):
        _fold_forms_ledgers(result, state, p, xp=jnp)
    if structure is not None and structure.kinds:
        _fold_kind_ledgers(
            result, state, p, _kinds(structure), xp=jnp, ledgers=structure.kind_ledgers
        )
    return result


def device_checks(previous, row, p, constants, steps, *, structure=None, margins=False):
    """check_values' tests for one accepted row on the device: (failed, diagnostics).

    steps is the row's accepted-step count, the host check's value for that row.
    margins=True also returns each ledger's ratio to its bound (row_checks).
    """
    from cells.models.surface_pump_checks import row_checks

    kinds = structure is not None and bool(structure.kinds or structure.forms_faces)
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

# ------------------------------------------------------------------ field roles (B1, seam B)
# docs/CORE_SEAMS_DESIGN.md §4.2: each per-entity field declares its partition role, and the
# lifecycle (close, split, retire and open) is implemented once for every role:
# - extensive: divided by the host's fraction with the anchor rule, so the daughters sum to the
#   parent exactly; padded at retirement (its amount went to the daughters);
# - intensive: copied at a split; padded at retirement;
# - history: each daughter starts from 0; at retirement it moves into the closer's record, which
#   adjust_inner adds back;
# - structural: as declared at a split (law, host, ends); padded with its fill at retirement.
# Every padded value of @3's is 0 (the adapter's PADDED_FIELDS; a closed contact's gate), so no
# fill is declared. @3's own fields take these roles in place of the partition's hand-written
# lists: every state field, and the per-entity layout fields that the lifecycle splits, copies or
# pads today. These are host-side declarations: no program reads them.
ROLES = ("extensive", "intensive", "history", "structural")
FIELD_ROLES = MappingProxyType(
    {
        # State.
        "amount_increment": "extensive",  # The partition's carriers move its charge mismatch.
        "extracellular_amount_increment": "extensive",
        "membrane_transferred": "history",
        "junction_transferred": "history",
        "face_transferred": "history",
        "reservoir_supplied": "history",
        "membrane_dissipated_energy_pJ": "history",
        "junction_dissipated_energy_pJ": "history",
        "face_dissipated_energy_pJ": "history",
        "electrode_charge_transferred_C": "history",
        "reservoir_work_pJ": "history",
        "electrode_work_pJ": "history",
        # A closed slot keeps the code-0 law's gate update (docs/INNER_MODEL_V4_DESIGN.md §7.4
        # (b), (o)): its fill is that padding's, until an explicit absent marker.
        "channel_gate": "intensive",
        "channel_transferred": "history",
        "channel_dissipated_energy_pJ": "history",
        "junction_gate": "intensive",  # A closed contact holds 0.
        "pump_cycles": "history",
        "pump_dissipated_energy_pJ": "history",
        "metabolic_work_pJ": "history",
        "calcium_pump_cycles": "history",
        "calcium_pump_dissipated_energy_pJ": "history",
        "calcium_metabolic_work_pJ": "history",
        # Layout: the anchors the partition splits (volume, amounts, charge, area, capacitance,
        # contact area) and the pumps' per-patch capacities (composition's level (a)).
        "volume": "extensive",
        "amount_reference": "extensive",
        "initial_cell_charge_C": "extensive",
        "extracellular_volume": "extensive",
        "extracellular_amount_reference": "extensive",
        "initial_outside_charge_C": "extensive",
        "membrane_area": "extensive",
        "membrane_capacitance": "extensive",
        "pump_capacity": "extensive",
        "calcium_pump_capacity": "extensive",
        "junction_area": "extensive",
        # Layout copied at a split. A population takes its patch's fraction through the patch's
        # area: its abundance and permeability are copied.
        "membrane_permeability": "intensive",
        "channel_abundance": "intensive",
        "channel_permeability": "intensive",
        "channel_relative_permeability": "intensive",
        "junction_permeability": "intensive",
        "junction_threshold_voltage": "intensive",
        "junction_minimum": "intensive",  # A closed contact's minimum open fraction is 0.
        # Layout as declared: laws, hosts and ends.
        "channel_laws": "structural",  # Padded with code 0, the padding code.
        "channel_membranes": "structural",
        "membrane_cell": "structural",
        "membrane_outside": "structural",
        "junction_sender": "structural",
        "junction_receiver": "structural",
        "pump_present": "structural",
        "calcium_pump_present": "structural",
    }
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
_MEMBRANE_FLUX = _flow(
    "inside",
    "outside",
    "a positive amount leaves the patch's cell for its outside node; a declared kind's conversion "
    "at P (cells.transporter@1, chemistry at P) appears as its forms crossing in opposite "
    "directions, the electron's charge written in them, so the patch's current is the charge the "
    "field sees",
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
    "membrane_flux_fmol_s": (
        "fmol/s",
        "rate",
        "membrane",
        ("species", "membrane_slot"),
        _MEMBRANE_FLUX,
    ),
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
    if not kinds and not series_junctions(structure):
        names = (*_VIEW_MAPS, "VIEW_LAYERS", "VIEW_AXIS_SETS", *_RECORD_ROLES)
        return {name: globals()[name] for name in names}
    types = kind_types(structure)
    present = {*types.STATE_TYPE._fields, *types.OBSERVATION_FIELDS}
    merged = {name: dict(globals()[name]) for name in _VIEW_MAPS}
    if series_junctions(structure):  # FR-30: the gates' factors; junction_gate, their product.
        for name, value in zip(("UNITS", "RECORD_KINDS", "RECORD_LAYERS"),
                               ("1", "level", "channels"), strict=True):  # fmt: skip
            merged[name][SERIES_GATES] = value
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
    notes = dict(RECORD_NOTES)
    if routes_into_channels(structure):  # B1's door into @3, with FR-34's effective record.
        notes["channel_availability"] = ROUTED_CHANNEL_NOTE
        notes[EFFECTIVE_AVAILABILITY] = EFFECTIVE_AVAILABILITY_NOTE
        declared = ("1", "level", "channels", ("channel_slot",))
        for name, value in zip(("UNITS", "RECORD_KINDS", "RECORD_LAYERS", "OBSERVATION_AXES"),
                               declared, strict=True):  # fmt: skip
            merged[name][EFFECTIVE_AVAILABILITY] = value
    out = {name: MappingProxyType(value) for name, value in merged.items()}
    return out | dict(
        VIEW_LAYERS=tuple(layers),
        VIEW_AXIS_SETS=MappingProxyType(axis_sets),
        RECORD_DIAGNOSTICS=tuple(diagnostics),
        RECORD_REFERENCES=MappingProxyType(references),
        RECORD_NOTES=MappingProxyType(notes),
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


# B1's door (docs/CORE_SEAMS_DESIGN.md §4.3): what channel_availability records where a population
# declares factors, and FR-34's record of the value its flux runs at.
ROUTED_CHANNEL_NOTE = (
    "the held availability, before the routing door: the control @3 receives, which in a "
    "composite is its control view (the operators' factors and writes, as held_schedules holds "
    "them), never the composite's stored controls. An operator's write to the availability "
    "enters here, through the held value; a population that declares factors runs, at every "
    "stage, at this times its sources' factors (a left fold in declared order), which enter "
    "through the door; their product, the value its flux follows, is "
    "channel_effective_availability"
)
EFFECTIVE_AVAILABILITY_NOTE = (
    "the effective availability, the value each population's flux runs at: the held "
    "availability (channel_availability: the control @3 receives, which carries an operator's "
    "writes and, in a composite, its control view's factors; never the composite's stored "
    "controls) times its sources' factors at the row's read state, a left fold in declared "
    "order (B1's door); recorded only where a population declares factors, since elsewhere it "
    "is channel_availability"
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
                    for column in kind.readouts(
                        state,
                        read,
                        v.potential_V,
                        routed,
                        presence_gated(p, structure, xp=np),
                        xp=np,
                    )
                ),
                # FR-34: the routed availability, where the door routes into @3's channels.
                *((routed.channel,) if routes_into_channels(structure) else ()),
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
        "junction_law": SERIES_GATE_LAW_ID
        if declares_series_junctions(spec.model)
        else junction_gate.RELAXATION_LAW_ID,
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
        heat_bookings=getattr(model, "heat_bookings", ()),  # Seam D (§6.1): () by default.
        free_amount_reads=_free_amount_reads(model),  # P1 (§17): () by default.
        kind_ledgers=_kind_ledgers(model),  # E (§7.3): () by default.
        junction_series_kinds=_series_kinds(model),  # FR-30 (D262): () by default.
        crossing_junctions=crossing_junctions(model),  # Fix (A) (D273): () by default.
        forms_faces=tuple(sorted(f.id for f in getattr(model, "forms_faces", ()))),  # () default.
    )


def crossing_junctions(model):
    """Fix (A) (D273): the IDs, sorted, of a parsed model's junctions that join two capacitor
    components where at least one floats, from its topology as numerics/surface_field.bind reads
    it: a membrane joins its cell and its outside node into one component; a component holding a
    reservoir is held, the one holding the closure's gauge has a fixed offset, and every other
    floats. Host side and static; () for a world whose junctions all join held components."""
    cells = getattr(model, "cells", ())
    outside = getattr(model, "extracellular", ())
    parent = {node.id: node.id for node in (*cells, *outside)}

    def root(node):
        # Path halving: the same components and representatives as following the links, in
        # near-constant time. Without it, a bath shared by every membrane makes the links one
        # chain, and structure() (called by the windowed path's control and readout passes)
        # cost O(n^2) per call: 0.14 s on GJ-N1's 625-cell field (D317 (d)).
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for membrane in getattr(model, "membranes", ()):
        if membrane.inside in parent and membrane.outside in parent:
            parent[root(membrane.outside)] = root(membrane.inside)
    held = {root(node.id) for node in outside if getattr(node, "reservoir", False)}
    gauge = getattr(model, "gauge_reference", None)
    fixed = held | ({root(gauge)} if gauge in parent else set())
    return tuple(
        sorted(
            j.id
            for j in getattr(model, "junctions", ())
            if j.sender in parent
            and j.receiver in parent
            and root(j.sender) != root(j.receiver)
            and (root(j.sender) not in fixed or root(j.receiver) not in fixed)
        )
    )


SERIES_RK4_REFUSAL = (
    f"{SERIES_GATE_LAW_ID} runs on the IMEX tableaux in v1 (D262): RK4 would integrate "
    "junction_gate apart from its gates, while the IMEX step sets it to their product at every "
    "stage"
)
SERIES_PROJECTIVE_REFUSAL = (
    f"{SERIES_GATE_LAW_ID} runs on the fine engine in v1 (D262): execution.projective's settling "
    "test reads one junction gate's kinetics"
)
SERIES_STRUCTURE_REFUSAL = (
    f"{SERIES_GATE_LAW_ID} runs in @3 alone in v1, through its structure's implementation "
    "(registry.get_model), which holds the gates; a path without that structure, a composite's or "
    "a water family's, would run them as one gate, so it refuses them (FR-30, D262)"
)


def series_initial_values(spec):
    """FR-30: (each gate's initial factor [series_gate, edge_slot], each gate's parameters
    [series_gate, SERIES_PARAMETER_SLOTS, edge_slot], zero-padded) of a series world's junctions;
    padded edge slots hold 0, as a closed contact's junction_gate does."""
    edges, gates = spec.execution.edge_capacity, series_gates.GATE_COUNT
    factors = np.zeros((gates, edges))
    parameters = np.zeros((gates, SERIES_PARAMETER_SLOTS, edges))
    for i, j in enumerate(spec.model.junctions):
        for k, g in enumerate(j.gates):
            factors[k, i] = g.initial
            parameters[k, : len(g.parameters), i] = g.parameters
    return factors, parameters


def series_parameters(p, kinds):
    """Each gate's parameters as its kind's NamedTuple of [edge_slot] arrays, from the layout."""
    out = []
    for k, kind in enumerate(kinds):
        names = series_parameter_type(kind)._fields
        values = [p.junction_series_parameters[k, n] for n in range(len(names))]
        out.append(series_parameter_type(kind)(*values))
    return tuple(out)


def series_parameter_type(kind):
    """A series gate kind's parameter type (the law's own)."""
    return {
        "threshold_relaxation": junction_gate.Parameters,
        "boltzmann_eyring": series_gates.BoltzmannEyring,
    }[kind]


# junction_gate equals its gates' product to this many ulps of 1 (it is computed from them).
SERIES_PRODUCT_ULPS = 8.0


def series_domain_valid(state, p, structure, *, xp=jnp):
    """FR-30: every active junction's gates in [their residual, 1], padding at 0, and
    junction_gate their product (S2: it is computed from them, never integrated)."""
    gates = getattr(state, SERIES_GATES)
    kinds = structure.junction_series_kinds
    parameters = series_parameters(p, kinds)
    valid = True
    for k, (kind, values) in enumerate(zip(kinds, parameters, strict=True)):
        inside = (gates[k] >= series_gates.residual_of(kind, values)) & (gates[k] <= 1)
        valid = valid & xp.all(xp.where(p.junction_active, inside, gates[k] == 0))
    product = series_gates.conductance(tuple(gates[k] for k in range(len(kinds))), xp=xp)
    product = xp.where(p.junction_active, product, 0.0)
    eps = SERIES_PRODUCT_ULPS * float(np.finfo(np.float64).eps)
    return valid & xp.all(xp.abs(state.junction_gate - product) <= eps)


def _series_kinds(model):
    """FR-30: the gate kinds of the junctions' junction_series_gates@1 (the parse holds every
    junction to one law and every series junction to one kind per gate), or ()."""
    series = [j for j in model.junctions if j.law == SERIES_GATE_LAW_ID]
    return tuple(g.kind for g in series[0].gates) if series else ()


def _kind_ledgers(model):
    """E's list (InnerStructure.kind_ledgers; CORE_SEAMS §7.3): each declared kind's own ledgers,
    ((kind ID, ((ledger, diagnostic), ...)), ...) in canonical (kind ID) order, read once from
    its declaration through the kind contract's kind_ledgers. Names only: values and bounds are
    the kind's ledger_terms and ledger_bounds at check time. A malformed hook result, or a name
    one of @1's ten ledgers or their diagnostics holds, refuses the definition, naming the kind."""
    registry, taken, out = kind_registry.active(), {*first.LEDGERS, *first.LEDGER_DIAGNOSTICS}, []
    for kind_id, declaration in sorted(getattr(model, "kinds", ()), key=lambda entry: entry[0]):
        try:
            pairs = kind_registry.kind_ledgers(registry.lookup(kind_id), declaration)
        except ValueError as error:
            raise ConfigError(f"Kind {kind_id}'s ledgers are refused: {error}") from error
        clash = sorted({name for pair in pairs for name in pair} & taken)
        if clash:
            raise ConfigError(
                f"Kind {kind_id}'s ledgers {clash} take names of @1's ledgers or diagnostics"
            )
        if pairs:
            out.append((kind_id, tuple(pairs)))
    return tuple(out)


def reads_free_amounts(row, laws):
    """Whether a stage row's third item names a law of `laws` (a law registry) that declares
    free_amounts (P1's selector, the binding owner's ruling (a) of 19 November 2026). A row with
    no third item, or one naming a law the registry does not hold (version 1's read,
    rapid_proton_buffer@1) or a law without free_amounts, keeps today's predictor."""
    return (
        len(row) == 3
        and row[2] in laws
        and getattr(laws.lookup(row[2]), "free_amounts", None) is not None
    )


def _free_amount_reads(model):
    """P1's switch (InnerStructure.free_amount_reads): the declared kinds, sorted, whose stage
    rows all name a law that declares free_amounts. _check_stage_rows refuses a read whose rows
    mix the two forms, and a free-amount read beside a read of today's form."""
    kinds, laws = kind_registry.active(), law_registry.active()
    out = []
    for kind_id, declaration in getattr(model, "kinds", ()):
        kind = kinds.lookup(kind_id)
        if kind.stage_read is None or kind.stage_rows is None:
            continue
        rows = tuple(tuple(row) for row in kind.stage_rows(declaration))
        if rows and all(reads_free_amounts(row, laws) for row in rows):
            out.append(kind_id)
    return tuple(sorted(out))


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
    forms_moved = {}
    if getattr(model, "forms_faces", ()):  # Each forms face's rows, its forms' ligands included.
        forms_moved = forms_law.moved_rows_of(model, forms_of_binders(model))

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
        add(  # The forms faces (their own entity set): each row they carry or a form carries.
            s,
            "face",
            inner_laws.FORMS_FACE_ROUTE_LAW_ID,
            [f.id for f in getattr(model, "forms_faces", ()) if s in forms_moved.get(f.id, ())],
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
    SPARSE_LAYOUT_TYPE: object
    Control: object
    OBSERVATION_FIELDS: tuple
    Observations: object


TODAYS_TYPES = KindTypes(
    STATE_AXES,
    STATE_TYPE,
    LAYOUT_TYPE,
    FLOOR_LAYOUT_TYPE,
    SPARSE_LAYOUT_TYPE,
    Control,
    OBSERVATION_FIELDS,
    Observations,
)


@cache
def _kind_types(fields, registry, series=False, forms=False):
    """fields: ((kind ID, the bound kind's KindFields), ...) in canonical order. Classes are cached
    by field set (§7.4 (j); (n) 5): structures whose kinds carry the same fields share them, and a
    kind bound to fields other than its static ones (a declaration-dependent variant) names its
    extra fields in the classes' deterministic names. series (FR-30, D262): the structure's
    junctions take junction_series_gates@1, whose gates are a state field (SERIES_GATES, after the
    kinds' state fields) and whose parameters a layout field (SERIES_PARAMETERS). forms: the
    structure declares forms faces, whose state fields (FORMS_STATE_AXES) follow those and whose
    layout fields (FORMS_LAYOUT_FIELDS) follow the others."""
    if not fields and not series and not forms:
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
    suffix += "_" + SERIES_GATES if series else ""
    suffix += "_forms_faces" if forms else ""
    axes = dict(STATE_AXES)
    for kind_id, own in fields:
        for name, name_axes in own.state_axes:  # Not `field`: the field-solver module's name.
            if name in axes:
                raise ValueError(f"Kind {kind_id}'s state field {name} is already declared")
            axes[name] = list(name_axes)
    series_state = (SERIES_GATES,) if series else ()
    if series:
        axes[SERIES_GATES] = list(SERIES_GATES_AXES)
    forms_state = tuple(FORMS_STATE_AXES) if forms else ()
    for name in forms_state:
        axes[name] = list(FORMS_STATE_AXES[name])
    state = NamedTuple("SurfacePumpChannelState" + suffix, [(k, object) for k in axes])
    layout_extra = [name for _, own in fields for name in own.layout_fields]
    layout_extra += [SERIES_PARAMETERS] if series else []
    layout_extra += list(FORMS_LAYOUT_FIELDS) if forms else []
    layout = NamedTuple(
        "SurfacePumpChannelLayout" + suffix,
        [(k, object) for k in (*LAYOUT_TYPE._fields, *layout_extra)],
    )
    floor = NamedTuple(
        "SurfacePumpChannelFloorLayout" + suffix,
        [(k, object) for k in (*FLOOR_LAYOUT_TYPE._fields, *layout_extra)],
    )
    sparse = NamedTuple(
        "SurfacePumpChannelSparseLayout" + suffix,
        [(k, object) for k in (*SPARSE_LAYOUT_TYPE._fields, *layout_extra)],
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
        *series_state,
        *forms_state,
        *OBSERVATION_FIELDS[today_state:],
        *(column for _, own in fields for column in own.readout_columns),
    )
    observations = make_dataclass(
        "SurfacePumpChannelObservations" + suffix, [(k, np.ndarray) for k in columns], frozen=True
    )
    return KindTypes(axes, state, layout, floor, sparse, control, columns, observations)


def kind_types(structure):
    """The structure's types: today's own objects when it declares no kind (§7.4 (j), schema A),
    else classes cached by its kinds' fields, each kind bound to its structure entry ((n) 5), in
    canonical order. Where the door routes into @3's channels, the observations gain FR-34's
    effective availability last (_routed_kind_types); state, layout and controls are the same."""
    registry = kind_registry.active()
    fields = []
    for kind_id, entry in structure.kinds:
        kind = kind_registry.bound(registry.lookup(kind_id), entry)
        own = kind_registry.KindFields(
            kind.state_axes, kind.layout_fields, kind.control_fields, kind.readout_columns
        )
        fields.append((kind_id, own))
    series = series_junctions(structure)
    forms = forms_faces_declared(structure)
    if routes_into_channels(structure):
        return _routed_kind_types(tuple(fields), registry, series, forms)
    return _kind_types(tuple(fields), registry, series, forms)


@cache
def _routed_kind_types(fields, registry, series=False, forms=False):
    """_kind_types' classes with one more observation column, EFFECTIVE_AVAILABILITY, last."""
    types = _kind_types(fields, registry, series, forms)
    columns = (*types.OBSERVATION_FIELDS, EFFECTIVE_AVAILABILITY)
    observations = make_dataclass(
        types.Observations.__name__ + "_" + EFFECTIVE_AVAILABILITY,
        [(k, np.ndarray) for k in columns],
        frozen=True,
    )
    return types._replace(OBSERVATION_FIELDS=columns, Observations=observations)


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
        """The declared junction law's kinetics at junction voltages (junction_gate.Rates); a
        series law's gates have one Rates each, so it refuses there (FR-30, D262)."""
        if series_junctions(self.structure):
            raise ConfigError(
                f"{SERIES_GATE_LAW_ID} has one Rates per gate: its gates' kinetics are the "
                "law's own (junction_series_gates.kinetics), not one junction Rates"
            )
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
    "clamped_channel_flux",
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
    """The batch signature with the declared structure: different law sets never share a batch.
    Nor do kinds whose own axes hold different numbers of entities (kind_axis_sizes): a structure
    entry is value-free, so one transporter population on the population axis and two of one law
    share theirs, as one passive route and two do, while their arrays differ in shape (the fourth
    review's finding 4). Where no kind has an own axis, the signature is today's."""
    sizes = kind_axis_sizes(model)
    forms = getattr(model, "forms_faces", ())
    shapes = ()
    if forms:  # The forms faces' static shapes: no mixed batch.
        count = forms_law.mover_count(model, forms_of_binders(model))
        shapes = ((("forms_faces", len(forms)), ("face_mover", count)),)
    return (
        *batch_signature(model),
        structure(model),
        *((sizes,) if sizes else ()),
        *shapes,
    )


def kind_axis_sizes(model):
    """((kind ID, ((own axis, size), ...)), ...) in the structure's order: each declared kind's own
    axes, sized as kind_row_values sizes them, by their view sets' IDs; () where no kind has one. A
    view set is read from its kind's declaration, so the hook gets a spec holding the model alone:
    a batch compares models. A hook that reads more is refused, naming its kind (fail closed; the
    @3 owner's review)."""
    kinds = getattr(model, "kinds", ())
    if not kinds:
        return ()
    spec, declarations = SimpleNamespace(model=model), dict(kinds)
    registry, out = kind_registry.active(), []
    for kind_id, entry in structure(model).kinds:
        kind = kind_registry.bound(registry.lookup(kind_id), entry)
        try:
            own = {} if kind.view_sets is None else kind.view_sets(spec, declarations[kind_id])
        except AttributeError as error:
            raise ConfigError(
                f"Kind {kind_id}'s view_sets read more than its declaration and the model during "
                f"batch planning ({error})"
            ) from error
        if own:
            out.append((kind_id, tuple((axis, len(own[axis]["ids"])) for axis in sorted(own))))
    return tuple(out)


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
