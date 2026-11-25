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
  change at fixed free-node charges: potentials, image charge and heat);
* the split and the merge of membrane between patches, the charges following the patches
  (charge_following_transfer, R2 of docs/MEMBRANE_RETRIEVAL_DESIGN.md §2.2), with the carriers of
  its moved plate charges (check_carriers, carrier_scale, carrier_amounts): FR-2's retrieval and
  recycling and door F's one kernel (D217).
"""

import math
import sys
from collections.abc import Mapping
from functools import cache
from types import MappingProxyType
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import ConfigError
from cells.definitions.surface_pump_v2_spec import Control
from cells.laws.electrochemistry import CHARGE_PER_FMOL, R
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic
from cells.models import surface_tissue as tissue
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import scatter
from cells.registry import kind_registry

MODEL_ID = ionic.MODEL_ID
STATE_AXES = ionic.STATE_AXES
STATE_TYPE = ionic.STATE_TYPE
LAYOUT_TYPE = ionic.LAYOUT_TYPE
FLOOR_LAYOUT_TYPE = ionic.FLOOR_LAYOUT_TYPE
SPARSE_LAYOUT_TYPE = ionic.SPARSE_LAYOUT_TYPE
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
# Door S (docs/SCOPED_COMPOSITION_DESIGN.md §2): each view field's entity axis, its last axis,
# named by the definition's entity list (spec.model.<name>) its slots index.
VIEW_FIELD_ENTITIES = dict(
    volume="cells",
    extracellular_volume="extracellular",
    membrane_area="membranes",
    membrane_capacitance="membranes",
    initial_cell_charge_C="cells",
    channel_abundance="channels",
    channel_permeability="channels",
    membrane_permeability="membranes",
    pump_capacity="membranes",
    calcium_pump_capacity="membranes",
    active="cells",
    outside_active="extracellular",
    membrane_active="membranes",
    channel_active="channels",
    junction_active="junctions",
    face_active="faces",
    extracellular_amount_reference="extracellular",
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
# What closing each mask changes in close(): the mask, the masks below it in the entity hierarchy
# (a cell's patches, a node's patches and faces, a patch's populations, a cell's contacts) and the
# padded fields of all those slots. The composite's table of changes reads it
# (pump_composite.view_changes; docs/OPERATOR_COMPOSITION_DESIGN.md §17).
_POPULATION = ("channel_active", "channel_laws")
_PATCH = ("membrane_active", *_POPULATION)
CLOSURE_REACH = MappingProxyType(
    {
        "active": (
            "active",
            *_PATCH,
            "junction_active",
            "amount_reference",
            "initial_cell_charge_C",
            "junction_minimum",
        ),
        "outside_active": (
            "outside_active",
            *_PATCH,
            "face_active",
            "extracellular_amount_reference",
            "initial_outside_charge_C",
        ),
        "membrane_active": _PATCH,
        "channel_active": _POPULATION,
        "junction_active": ("junction_active", "junction_minimum"),
        "face_active": ("face_active",),
    }
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

# I2 (docs/INNER_MODEL_V4_DESIGN.md §7.4 (c)): the inner protocol taken from one implementation
# object per declared structure. These names are the object's, and so are the types (TYPE_NAMES,
# schema A) and any other name the object defines itself (channel_kinetics, junction_kinetics,
# field_values, structure, Control, ...); every other name is this module's own (the view and its
# merge, the field arrays, the energy terms), else @3's module's through the object.
FORWARDED = (
    "initial_values",
    "checked_step",
    "imex_step",
    "readouts",
    "domain_valid",
    "control_domain_valid",
    "balances",
    "device_balances",
    "check_steps",
    "bind_step_checks",
    "batch_signature",
    "working_size",
    "observe_history",
    "summarize",
    "device_check_constants",
    "device_failure_message",
)
inner_structure = ionic.structure  # The InnerStructure of a parsed @3 or composite model block.

# Schema A (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j)): the names an adapter takes per structure from
# its implementation object (structure_names). This module's own values are today's: the full
# catalogue declares no kind.
TYPE_NAMES = (
    "STATE_AXES",
    "STATE_TYPE",
    "LAYOUT_TYPE",
    "FLOOR_LAYOUT_TYPE",
    "CONTROL_TYPE",
    "STATE_FIELDS",
    "CONTROL_FIELDS",
    "OBSERVATION_FIELDS",
    "DISSIPATION_FIELDS",
    "HEAT_FIELDS",
    "WORK_FIELDS",
)
KINDS = ()  # The declared kinds' namespaced IDs, in canonical order.
KIND_FIELDS = MappingProxyType({})  # {state, layout or control field: the kind that declares it}
BOUND_KINDS = ()  # The declared kinds bound to their structure entries, in KINDS' order.

# ------------------------------------------------------------------ the lifecycle by roles
# docs/CORE_SEAMS_DESIGN.md §4.2, with the lead's rulings of 18 November 2026 (CORE_SEAMS §18): each
# per-entity field declares its partition role (kind_registry.PartitionRole: extensive, intensive,
# history or structural), and close, split, retire and open act on every field by its role, once.
# - Entity axes: @3's slot axes, which closure propagates along, and a kind's own axes, whose
#   entities name a host (Q1: the kind contract's host declaration). Neither @3's shared axes nor a
#   kind's laws' internal axes carry entities: one set, F's (kind_registry.SHARED_AXES and
#   entity_axes; a field's internal axes ride along at a split, copied whole, as shared ones do).
# - A kind beside a closer (an operator that closes, retires or provides activity masks) is
#   admitted only when the lifecycle acts on every field it holds (kind_lifecycle_errors):
#   1. every partition field declares a role (missing_partition_roles; §4.2, fail-closed);
#   2. every layout and control field declares its axes (Q1; the state fields' are state_axes);
#   3. every entity axis it has declares at least one presence field (kind_registry.presence_fields;
#      the lift of Q7 (a) after Q2, the lead's ruling of 19 November 2026). Where a closer is
#      declared, the core's presence gate makes an entity on a closed host absent to the kind's
#      rates, readouts and stage terms; a kind without presence would keep running there at the
#      view, so it stays refused (Q7 (a), checked at the structure);
#   4. every entity axis has a host the presence gate reads: one of @3's slot axes it closes
#      (GATED_SLOT_AXES), or an own axis with its axis_hosts declared. Otherwise the gate could
#      not close its entities, so it stays refused (fails closed).
SLOT_AXES = (
    "cell_slot",
    "extracellular_slot",
    "membrane_slot",
    "edge_slot",
    "channel_slot",
    "face_slot",
)
SHARED_AXES = kind_registry.SHARED_AXES  # F's set: one for the contract and the lifecycle.
# The slot axes whose entities the core's presence gate closes, @3's one list for the gate and
# this check (surface_pump_v3.PRESENCE_SLOT_AXES: cells, outside nodes, patches and junctions,
# and channel populations and faces); an own axis is gated through its declared axis_hosts.
GATED_SLOT_AXES = ionic.PRESENCE_SLOT_AXES
KIND_ROLE_STEPS = ("roles", "axes", "presence", "hosts")  # kind_lifecycle_errors' reasons.


def bound_kind(kind, declaration):
    """`kind` bound to its declaration's structure entry (kind_registry.bound), as the inner model
    binds it. A check reads the bound kind's hooks and fields, never the static kind's, which may
    differ per entry: a static read could admit what the bound kind refuses (fail-open)."""
    entry = kind.structure_entry(declaration) if kind.structure_entry else ()
    return kind_registry.bound(kind, entry)


def kind_field_axes(kind):
    """{field: axes or None} of a bound kind's partition fields (kind_registry.partition_fields'
    order): a state field's from state_axes, and a layout or control field's as the kind declares
    them (Q1's declaration, `field_axes` {field: (axis, ...)}), None where it declares none."""
    declared = getattr(kind, "field_axes", None) or {}
    axes = dict(kind.state_axes)
    return {
        name: tuple(axes[name]) if name in axes else declared.get(name)
        for name in kind_registry.partition_fields(kind)
    }


def kind_role_table(kind):
    """{field: (PartitionRole, axes)} of a bound kind whose every partition field declares its
    role and axes (kind_lifecycle_errors empty of the first two reasons)."""
    axes = kind_field_axes(kind)
    return {name: (kind.partition_roles[name], axes[name]) for name in axes}


def kind_lifecycle_errors(kind):
    """(reason, names) for the first of KIND_ROLE_STEPS a bound kind fails beside a closer, or ()
    when the lifecycle acts on all it holds (the module comment above): the fields without a role
    or axes; the entity axes (kind_registry.entity_axes) that declare no presence field; or the
    entity axes whose host the core's presence gate cannot read (hosts: neither one of
    GATED_SLOT_AXES nor an own axis with its axis_hosts declared, such as an own axis that declares
    none), where the gate could not close an entity (fails closed). A presence that names a field
    the kind does not hold is the contract's own refusal (kind_registry.presence_fields raises)."""
    missing = kind_registry.missing_partition_roles(kind)
    if missing:
        return ("roles", missing)
    axes = kind_field_axes(kind)
    undeclared = tuple(name for name, a in axes.items() if a is None)
    if undeclared:
        return ("axes", undeclared)
    entities = kind_registry.entity_axes(kind)
    declared = kind.presence if isinstance(kind.presence, Mapping) else {}
    lacking = tuple(axis for axis in entities if not declared.get(axis))
    if lacking:
        return ("presence", lacking)
    kind_registry.presence_fields(kind)  # Raises on a presence field it does not hold.
    hosts = kind.axis_hosts if isinstance(kind.axis_hosts, Mapping) else {}
    unhosted = tuple(axis for axis in entities if axis not in GATED_SLOT_AXES and axis not in hosts)
    if unhosted:
        return ("hosts", unhosted)
    return ()


def inner_role_table(roles, axes, *, excluded=()):
    """{field: (PartitionRole, axes)} of @3's fields from its role table (surface_pump_v3's
    FIELD_ROLES: {field: role name}), converted once here (Q4): every padded value of @3's is 0,
    so a structural field's fill is 0. `axes` gives each field's axes; `excluded` names fields the
    lifecycle leaves to their closers' own records (the pumps' history until composition's M5
    Q2)."""
    out = {}
    for name, role in roles.items():
        if name in excluded:
            continue
        fill = 0 if role == "structural" else None
        out[name] = (kind_registry.PartitionRole(role, fill), tuple(axes[name]))
    return out


# The single lifecycle implementation for kinds' state fields (B1's last slice; design statement 1,
# the lead's rulings of 19 November 2026). A closer that divides passes its maps, one per slot axis
# that has them: {axis: (parent rows, daughter rows [rows, 2], daughter 1's fraction, due rows)};
# a closer that retires passes its masks, {axis: bool [slots]}, by the entity hierarchy (the
# partition is their one source). A field is acted on along its entity axis, the last of its axes;
# shared axes ride along. Axes without maps (outside nodes, faces) are never divided or retired.
LIFECYCLE_AXES = ("cell_slot", "membrane_slot", "channel_slot", "edge_slot")


def _put_last(array, index, values, *, xp):
    """array with array[..., index] = values (distinct slots)."""
    if xp is np:
        out = np.array(array, copy=True)
        out[..., index] = values
        return out
    return array.at[..., index].set(values)


def lifecycle_axis(name, axes, internal=()):
    """A field's entity axis for the lifecycle, or None for a field on shared axes or its kind's
    internal axes (`internal`) only, as kind_registry.entity_axes counts them. Fails closed: a field
    with two entity axes, or whose entity axis is not its last, is refused."""
    entities = [axis for axis in axes if axis not in SHARED_AXES and axis not in internal]
    if not entities:
        return None
    if len(entities) > 1 or axes[-1] != entities[0]:
        raise ValueError(
            f"{name}: the lifecycle acts along one entity axis, its last ({tuple(axes)})"
        )
    return entities[0]


def lifecycle_split(values, table, maps, *, xp, internal=MappingProxyType({})):
    """({field: array} after a division's split, valid): each state field of `table` ({field:
    (PartitionRole, axes)}) on an axis with maps, by role: extensive by the anchor rule (daughter 1
    fl(a x), daughter 2 x - fl(a x), the parent 0, so the daughters sum to the parent exactly);
    intensive copied to the daughters; history left at the daughters' 0, which validity requires;
    structural kept as declared. Fields not in `values`, on shared or internal axes only
    (`internal`: {field: its kind's internal axes}) or on an unmapped axis are returned
    unchanged."""
    out, valid = dict(values), xp.asarray(True)
    for name, (role, axes) in table.items():
        axis = lifecycle_axis(name, axes, internal.get(name, ()))
        if name not in values or axis not in maps:
            continue
        parent, daughters, fraction, due = maps[axis]
        value = values[name]
        x = value[..., parent]
        k1, k2 = daughters[:, 0], daughters[:, 1]
        if role.role == "extensive":
            if fraction is None:  # Fails closed: no fraction to split by.
                raise ValueError(f"{name}: an extensive field on {axis} needs its map's fraction")
            first = fraction * x
            second = x - first
            value = _put_last(value, k1, xp.where(due, first, value[..., k1]), xp=xp)
            value = _put_last(value, k2, xp.where(due, second, value[..., k2]), xp=xp)
            value = _put_last(value, parent, xp.where(due, 0.0, value[..., parent]), xp=xp)
        elif role.role == "intensive":
            value = _put_last(value, k1, xp.where(due, x, value[..., k1]), xp=xp)
            value = _put_last(value, k2, xp.where(due, x, value[..., k2]), xp=xp)
        elif role.role == "history":
            fresh = (value[..., k1] == 0) & (value[..., k2] == 0)
            valid &= xp.all(xp.where(due, fresh, True))
        out[name] = value
    return out, valid


def lifecycle_retire(values, table, masks, records, *, xp, internal=MappingProxyType({})):
    """({field: array}, {record field: array}) after a retirement, by role: a history field's value
    on the retired slots moves into its record (`records`: {field: (record field, array)}), then 0;
    every other role takes its fill (a structural field's declared fill, else 0). A history field
    with no record is refused (fails closed: its history would be lost). `internal` as for
    lifecycle_split."""
    out, kept = dict(values), {}
    for name, (role, axes) in table.items():
        axis = lifecycle_axis(name, axes, internal.get(name, ()))
        if name not in values or axis not in masks:
            continue
        mask, value = masks[axis], values[name]
        if role.role == "history":
            if name not in records:
                raise ValueError(f"{name}: a history field retires only into its record")
            record, held = records[name]
            kept[record] = xp.where(mask, held + value, held)
            out[name] = xp.where(mask, 0.0, value)
        else:
            fill = role.fill if role.role == "structural" and role.fill is not None else 0
            out[name] = xp.where(mask, xp.asarray(fill, dtype=value.dtype), value)
    return out, kept


def structure_names(implementation):
    """{name: value} of TYPE_NAMES, KINDS and KIND_FIELDS for one implementation object (schema A).

    The object carries its structure's types: today's fields, then each declared kind's in
    canonical order (§7.4 (j)). The other names derive from them. A kind's state field is a heat
    (and dissipation) field when it ends in _dissipated_energy_pJ and a work field when it ends in
    _work_pJ, by @3's own rule (its dissipation_fields, and the energy flows its ledger bound reads
    by name). For a structure that declares no kind every value is this module's own object.
    """
    state_type, control_type = implementation.STATE_TYPE, implementation.Control
    added = state_type._fields[len(STATE_FIELDS) :]
    heat = tuple(k for k in added if k.endswith("_dissipated_energy_pJ"))
    work = tuple(k for k in added if k.endswith("_work_pJ"))
    kinds = tuple(kind_id for kind_id, _ in implementation.structure.kinds)
    owned, bound = {}, []
    entries = dict(implementation.structure.kinds)
    for kind_id in kinds:  # The registry the object's types were built from (its cache key).
        kind = kind_registry.bound(kind_registry.active().lookup(kind_id), entries[kind_id])
        bound.append(kind)
        owned |= dict.fromkeys(  # Its fields for the declaration (§7.4 (n) 5).
            (*kind.state_fields, *kind.layout_fields, *kind.control_fields), kind_id
        )
    return dict(
        STATE_AXES=implementation.STATE_AXES,
        STATE_TYPE=state_type,
        LAYOUT_TYPE=implementation.LAYOUT_TYPE,
        FLOOR_LAYOUT_TYPE=implementation.FLOOR_LAYOUT_TYPE,
        SPARSE_LAYOUT_TYPE=implementation.SPARSE_LAYOUT_TYPE,
        CONTROL_TYPE=control_type,
        STATE_FIELDS=state_type._fields,
        CONTROL_FIELDS=control_type._fields,
        OBSERVATION_FIELDS=implementation.OBSERVATION_FIELDS,
        DISSIPATION_FIELDS=(*DISSIPATION_FIELDS, *heat) if heat else DISSIPATION_FIELDS,
        HEAT_FIELDS=(*HEAT_FIELDS, *heat) if heat else HEAT_FIELDS,
        WORK_FIELDS=(*WORK_FIELDS, *work) if work else WORK_FIELDS,
        KINDS=kinds,
        KIND_FIELDS=MappingProxyType(owned) if owned else KIND_FIELDS,
        BOUND_KINDS=tuple(bound) if bound else BOUND_KINDS,
    )


class InnerAdapter:
    """This module with the inner protocol of one implementation object (I2): a composite's
    `inner`, and what an operator that declares USES_INNER receives as `inner=`.

    Schema A (docs/INNER_MODEL_V4_DESIGN.md §7.4 (j)): the object carries its structure's types.
    The adapter takes them and the names derived from them from the object (structure_names), and
    its functions that build @3's state, layout and control (inner_state, layout_kind,
    inner_layout, inner_control, view and control_view) build the structure's own. For a structure
    that declares no kind each of these is this module's: the same objects and the same results.
    """

    def __init__(self, implementation):
        self.implementation = implementation
        self.structure_key = implementation.structure_key
        for name in FORWARDED:
            setattr(self, name, getattr(implementation, name))
        self.magnitudes = implementation.channel_magnitudes
        for name, value in structure_names(implementation).items():
            setattr(self, name, value)

    def __getattr__(self, name):
        # Only reached for names not set above: the object's own names first (its per-structure
        # types and structure-bound functions, schema A), then this module's, then the object's
        # fallback, @3's module names.
        if name.startswith("__"):
            raise AttributeError(name)
        implementation = self.implementation
        if name in vars(implementation) or any(
            name in vars(k) for k in type(implementation).__mro__[:-1]
        ):
            return getattr(implementation, name)
        if hasattr(_MODULE, name):
            return getattr(_MODULE, name)
        return getattr(implementation, name)

    def __repr__(self):
        return f"<{MODEL_ID} adapter for {self.implementation!r}>"

    def inner_state(self, state):
        return self.STATE_TYPE(*(getattr(state, k) for k in self.STATE_FIELDS))

    def layout_kind(self, p):
        if hasattr(p, "field_capacitor_values"):  # The sparse field (SPARSE_SOLVER_ID).
            return self.SPARSE_LAYOUT_TYPE
        return self.FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else self.LAYOUT_TYPE

    def inner_layout(self, p):
        """The structure's declared layout (the bound values)."""
        kind = self.layout_kind(p)
        return kind(*(getattr(p, k) for k in kind._fields))

    def inner_control(self, control):
        return self.CONTROL_TYPE(*(getattr(control, k) for k in self.CONTROL_FIELDS))

    def view(self, p, state, providers, closers=(), *, xp=jnp, refresh=True):
        """The module's view (below) on the structure's declared layout."""
        return _view(self.inner_layout, p, state, providers, closers, xp=xp, refresh=refresh)

    def control_view(self, control, state, p, factors, *, xp=jnp, views=None, quantities=None):
        """The module's control_view (below) on the structure's control."""
        return _control_view(
            self.inner_control(control),
            state,
            p,
            factors,
            xp=xp,
            views=views,
            quantities=quantities,
        )


def for_structure(structure):
    """The adapter of one declared inner structure: one per implementation object, so equal
    structures share it, and a structure that declares kinds is also keyed on the active kind
    registry, as its object is (surface_pump_v3.implementation)."""
    if ionic.series_junctions(structure):  # FR-30, v1 (D262; the @3 owner's recorded exception).
        raise ConfigError(
            f"{ionic.SERIES_GATE_LAW_ID} runs in @3 alone in v1: a composite's operators, its "
            "closers and its lifecycle write junction_gate as one gate (D262)"
        )
    if ionic.forms_faces_declared(structure):  # The forms law, version 1 (the face builder's).
        raise ConfigError(
            f"{ionic.forms_law.LAW_ID} runs in @3 alone in version 1: a composite's operators, "
            "closers and field refresh know no forms face"
        )
    return _adapter(ionic.implementation(structure))


@cache
def _adapter(implementation):
    return InnerAdapter(implementation)


def inner_state(state):
    return STATE_TYPE(*(getattr(state, k) for k in STATE_FIELDS))


def layout_kind(p):
    if hasattr(p, "field_capacitor_values"):  # The sparse field (SPARSE_SOLVER_ID).
        return SPARSE_LAYOUT_TYPE
    return FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else LAYOUT_TYPE


def inner_layout(p):
    """@3's declared layout (the bound values)."""
    kind = layout_kind(p)
    return kind(*(getattr(p, k) for k in kind._fields))


def inner_control(control):
    return Control(*(getattr(control, k) for k in CONTROL_FIELDS))


def view(p, state, providers, closers=(), *, xp=jnp, refresh=True):
    """@3's layout at the composite state: the declared fields, merged with the providers'.

    providers: operators with VIEW_FIELDS, in declared order. Each provider's values are merged
    onto the accumulated view (door S, docs/SCOPED_COMPOSITION_DESIGN.md §4): on every slot, a
    replacing provider's values are the field itself, as before door S; a scoped change is taken
    only on its masked slots (merge). Overlaps are admitted only as the composite's structure and
    scope checks allow. Without providers this is the declared layout itself. closers: operators
    that close activity masks (CLOSES), each not statically idle; with none the call is exactly
    the one without closers. refresh=False leaves the derived field arrays bound (a door S
    reader's view, which reads none of them; docs/OPERATOR_COMPOSITION_DESIGN.md §11, C4).
    """
    return _view(inner_layout, p, state, providers, closers, xp=xp, refresh=refresh)


def _view(declared, p, state, providers, closers, *, xp, refresh=True):
    """view, with `declared` giving the declared layout of p: this module's inner_layout, or an
    adapter's for its structure (schema A)."""
    q = declared(p)
    provided = set()
    for operator in providers:
        values = operator.view(state, p, q, xp=xp)
        changes = {k: operator.view_change(k) for k in values}
        masks = operator.view_slots(p, xp=xp) if any(c.scoped for c in changes.values()) else {}
        q = q._replace(
            **{
                k: merge(
                    getattr(q, k),
                    v,
                    changes[k].contribution,
                    masks[k] if changes[k].scoped else None,
                    xp=xp,
                )
                for k, v in values.items()
            }
        )
        provided |= set(values)
    if closers:
        q = close(q, state, p, closers, xp=xp)
        provided |= set(MASK_FIELDS)
    if refresh and provided & set(FIELD_INPUTS):
        q = refresh_field(q, declared(p), xp=xp)
    return q


_MODULE = sys.modules[__name__]


def merge(current, value, contribution, mask=None, *, xp):
    """Door S's merge of one change onto the accumulated field (docs/SCOPED_COMPOSITION_DESIGN.md
    §4). Without a mask the change covers every slot (a replacement is the value itself); with
    one (a bool array over the field's last axis) it is taken on the masked slots only, and every
    other slot is selected from `current`, never offset by a computed zero."""
    if contribution == "replace":
        combined = value
    elif contribution == "add":
        combined = current + value
    elif contribution == "multiply":
        combined = current * value
    else:
        raise ValueError(f"Unknown view contribution {contribution!r}")
    return combined if mask is None else xp.where(mask, combined, current)


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


def control_view(control, state, p, factors, *, xp=jnp, views=None, quantities=None):
    """@3's control: each factored availability times its multipliers, in declared order.
    views: {factor operator: its reader-view function} for those that read at the control view
    (R2), each passed as view=; quantities: {factor operator: its quantities function} for the
    readers of an owner's quantities (R3), each passed as quantities=. None or absent, every call
    is as before."""
    return _control_view(
        inner_control(control), state, p, factors, xp=xp, views=views, quantities=quantities
    )


def _control_view(c, state, p, factors, *, xp, views=None, quantities=None):
    """control_view from @3's control c: this module's, or an adapter's for its structure."""
    for operator in factors:
        keywords = {"view": views[operator]} if views and operator in views else {}
        if quantities and operator in quantities:
            keywords["quantities"] = quantities[operator]
        values = operator.control_factors(state, p, xp=xp, **keywords)
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


def refuse_sparse_field_inputs():
    """The one refusal of a field-input provider under the sparse field (FR-17 stage 1)."""
    raise ConfigError(
        f"An operator that changes capacitances or activity masks is refused under "
        f"{field.SPARSE_SOLVER_ID} (FR-17 stage 1): its field refresh rebuilds the dense "
        "field arrays, which the sparse field does not bind"
    )


def check_field_inputs(p, nodes):
    """Refuse a field-input provider above the node cap or with floating capacitor components.

    nodes: the definition's padded field size (cell plus outside capacity). Under the sparse field
    (surface_field.SPARSE_SOLVER_ID) every field-input provider is refused: refresh_field rebuilds
    the dense field arrays, and the sparse layout has none (FR-17 stage 1).
    """
    if hasattr(p, "field_capacitor_values"):
        refuse_sparse_field_inputs()
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


# @3's chemical term per node and per species row (docs/SECRETED_SPECIES_TRANSPORT_DESIGN.md §2.4),
# for both node kinds. New beside chemical_free_energy_pJ, which stays as it is; no existing program
# calls these. The secreted-species operators (scheduled_species_turnover@1 and
# scheduled_species_exchange@1) book their work with them, one species row at a time, so a
# protein-scale change is never computed as a difference of ion-scale sums.


def species_chemical_free_energy_pJ(anchor, change, volume, temperature, *, xp):
    """@3's chemical term per element, pJ: the change of RT n (ln(n/V) - 1) from n = anchor to
    anchor + change at the declared volume V, written as balances writes it,
    1e-3 RT [change (ln(anchor/V) - 1) + (anchor + change) log1p(change/anchor)].

    With anchor the declared reference and change the stored increment it is balances' own term of
    one species at one node; with anchor the current amount and change a moved amount it is the
    exact free-energy change of that move, with no difference of bulk terms. Arrays broadcast: pass
    one species row (or rows) of cells with their volumes, or of outside nodes with theirs; mask
    padding with a positive anchor and a zero change (the term is then 0).

    Under the IMEX solvers the shared energy bound is set by the ions' flows and is blind to these
    bookings at µM–nM (bound/change 1.7 to 1,721 in a probed mixed world); the species-only world
    and a NumPy ΔG test per law are the guards of record.
    """
    return (
        1e-3
        * R
        * temperature
        * (change * (xp.log(anchor / volume) - 1) + (anchor + change) * xp.log1p(change / anchor))
    )


def species_chemical_magnitude_pJ(anchor, change, volume, temperature, *, xp):
    """The absolute terms of species_chemical_free_energy_pJ, pJ (the rounding allowance's
    magnitudes)."""
    return (
        1e-3
        * R
        * temperature
        * (
            xp.abs(change * (xp.log(anchor / volume) - 1))
            + xp.abs((anchor + change) * xp.log1p(change / anchor))
        )
    )


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
    declared = (field.capacitor_product(tissue.field_layout(bound), base, xp=xp) + cap)[n:]
    plates = field.capacitor_product(tissue.field_layout(view), phi, xp=xp)[n:]
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
    image = (field.capacitor_product(tissue.field_layout(q1), delta, xp=xp) + dk)[n:]
    first = 0.5e12 * s * v
    second = 0.5e12 * xp.sum(xp.where(q1.field_fixed, 0.0, delta * dk))
    total = xp.sum(first)
    positive = total > 0
    share = xp.where(positive, (total + second) / xp.where(positive, total, 1.0), 0.0)
    after = patch_voltages(phi + delta, q1, xp=xp)
    return q1, xp.where(bound.reservoir, image, 0.0), first * share, first, second, v, after


# The split and the merge of membrane between patches, the charges following the patches
# (docs/MEMBRANE_RETRIEVAL_DESIGN.md §2.2, R2; docs/CORE_SEAMS_DESIGN.md §4.6's merge; D217): one
# kernel for FR-2's retrieval and recycling, door F's fission and fusion and mitochondria's.


class ChargeTransfer(NamedTuple):
    """What one charge-following transfer of membrane does (charge_following_transfer)."""

    view: object  # q with the capacitances moved, its field arrays refreshed
    plate_C: object  # [T] each piece's inside plate charge, dc V_s (C); its outside one is -plate_C
    charge_C: object  # [cells, then outside nodes] each free node's charge change (C)
    supplied_C: object  # [outside] the charge each held node's reservoir supplies (C)
    electrode_C: object  # [outside] each held node's plate-charge change after the re-solve (C)
    heat_pJ: object  # the merge heat (pJ), >= 0
    before_V: object  # [membrane] the patch voltages before
    after_V: object  # [membrane] the patch voltages after


def charge_following_transfer(state, q, source, target, dc, bound, *, xp):
    """Move capacitance dc[t] >= 0 from patch source[t] to patch target[t], the charges following
    the patches (R2, docs/MEMBRANE_RETRIEVAL_DESIGN.md §2.2).

    Each piece leaves its source at the source's voltage V_s with both of its plate charges:
    +dc V_s on its inside face, from the source's cell to the target's (nothing moves within one
    cell), and -dc V_s on its outside face, from the source's outside node to the target's. So the
    rest of the network keeps its potentials as the piece leaves, and a piece is neutral. At a free
    node a plate charge changes the node's charge (what declared carriers carry); at a held node
    (a bath) the node's reservoir supplies it or takes it in (supplied_C). The potentials are then
    re-solved at the new capacitances and charges, the held nodes at their potentials, whose clamps
    change their plate charges (electrode_C). Where a held node loses a piece and supplies its
    carriers the two charges cancel.

    The heat is what attaching the pieces dissipates, the two-capacitor loss, with no bulk energy
    subtracted (**S**). With e_t the target's port (inside cell +1, outside node -1) on the free
    nodes, E = [e_t], D = diag(dc), jump_t = V_s - V_t and K0 the network with the pieces off their
    sources and not yet attached (so K' = K0 + E D E^T),
        H = 1/2 jump^T (D^-1 + E^T K0^-1 E)^-1 jump = 1/2 |L^-1 sqrt(D) jump|^2,
        L L^T = I + sqrt(D) E^T K0^-1 E sqrt(D),
    a sum of squares, so H >= 0 at rounding and exactly 0 where every piece meets its target's
    voltage; every eigenvalue of L L^T is at least 1, and a zero dc leaves its row the identity's.
    By Woodbury it equals 1/2 sum_t dc_t jump_t^2 - 1/2 delta . r, with r = E D jump and delta =
    K'^-1 r the free potentials' change, the form used until 19 November 2026: its difference of
    two solves carries about 1/2 dc |jump| eps |V| and fell below zero where a piece met its target
    at its own voltage to rounding (FR-2's probes). Into a free face-free node j that one patch b
    bounds, from a patch k of b's cell, only phi_j moves: V_b' = (C_b V_b + dc V_k)/(C_b + dc), and
    H = C_b dc (V_b - V_k)^2 / (2 (C_b + dc)), CORE_SEAMS §4.6's merge loss. The heat with the
    clamps' and reservoirs' work closes the capacitor energy: H = sum_h phi_h (electrode_h +
    supplied_h) - (U' - U), U = 1/2 sum C V^2 (the test's ledger).

    q: @3's layout at the current view, its field arrays refreshed; bound: the declared layout,
    refresh_field's reference; source, target: [T] active patch slots, distinct for each t; dc: [T]
    capacitances moved (F), each at most what its source holds (the caller refuses more, by a
    declared area floor). A pure function: it writes no state; the caller books the charges as
    carriers (carrier_amounts) and the heat.
    """
    n, o = q.active.size, q.outside_active.size
    charge = xp.concatenate((q.initial_cell_charge_C, q.initial_outside_charge_C))
    charge = charge + tissue.charge_increment(state, q, xp=xp)
    phi = node_potentials(state, q, xp=xp)
    v = patch_voltages(phi, q, xp=xp)
    plate = dc * v[source]  # Each piece's inside plate charge; its outside one is its negative.
    capacitance = q.membrane_capacitance + scatter(dc, q.membrane_capacitance, (target,), xp=xp)
    capacitance = capacitance - scatter(dc, q.membrane_capacitance, (source,), xp=xp)
    # The new view's field arrays start from the declared layout's, as _view's do: refresh_field
    # keeps its argument's arrays where no field input differs from the declared one, so a transfer
    # that returns every capacitance to its declared value then reads the declared field.
    derived = {k: getattr(bound, k) for k in DERIVED_FIELD_ARRAYS if hasattr(bound, k)}
    q1 = refresh_field(q._replace(membrane_capacitance=capacitance, **derived), bound, xp=xp)
    nodes = xp.zeros(n + o)
    moved = (  # Each node: the plate charges arriving less those leaving.
        scatter(plate, nodes, (q.membrane_cell[target],), xp=xp)
        - scatter(plate, nodes, (q.membrane_cell[source],), xp=xp)
        - scatter(plate, nodes, (n + q.membrane_outside[target],), xp=xp)
        + scatter(plate, nodes, (n + q.membrane_outside[source],), xp=xp)
    )
    held = xp.concatenate((xp.zeros(n, dtype=bool), q.reservoir))
    changed = xp.where(held, 0.0, moved)
    boundary = xp.concatenate((xp.zeros(n), q.boundary_V))
    after = field._capacitor_solve(charge + changed, boundary, tissue.field_layout(q1), xp=xp)
    jump = v[source] - v[target]  # Each piece's voltage less its target's.
    off = q.membrane_capacitance - scatter(dc, q.membrane_capacitance, (source,), xp=xp)
    q0 = refresh_field(q._replace(membrane_capacitance=off, **derived), bound, xp=xp)
    heat = merge_heat_pJ(q0, target, dc, jump, xp=xp)
    electrode = (
        field.capacitor_product(tissue.field_layout(q1), after, xp=xp)
        - field.capacitor_product(tissue.field_layout(q), phi, xp=xp)
    )[n:]
    return ChargeTransfer(
        view=q1,
        plate_C=plate,
        charge_C=changed,
        supplied_C=xp.where(q.reservoir, -moved[n:], 0.0),
        electrode_C=xp.where(q.reservoir, electrode, 0.0),
        heat_pJ=heat,
        before_V=v,
        after_V=patch_voltages(after, q1, xp=xp),
    )


def merge_heat_pJ(q0, target, dc, jump, *, xp):
    """The heat (pJ) of attaching pieces of capacitance dc[t] >= 0, each at its jump from its
    target's voltage, jump[t] = V_s - V_t, to the network q0: the pieces off their sources and not
    yet attached, its field arrays refreshed (charge_following_transfer's heat). A sum of squares,
    1/2 |L^-1 sqrt(dc) jump|^2 with L L^T = I + sqrt(D) E^T K0^-1 E sqrt(D), E the targets' ports
    and K0 the free block, solved with q0's own factor (held nodes fixed). Every eigenvalue of
    L L^T is at least 1, so the factor is well conditioned, and a piece of zero capacitance
    contributes exactly nothing. Outside the domain the heat is NaN, which the caller refuses: a
    negative dc (the former form gave a finite number there), or a singular q0 under JAX (in
    NumPy its refresh raises first, for the new view as before)."""
    n, o = q0.active.size, q0.outside_active.size
    p0 = tissue.field_layout(q0)
    nodes = xp.arange(n + o)[:, None]
    ports = (nodes == q0.membrane_cell[target][None, :]).astype(float) - (
        nodes == (n + q0.membrane_outside[target])[None, :]
    ).astype(float)
    rhs = xp.where(~p0.fixed[:, None], ports / p0.capacitor_scale, 0.0)
    solved = field.capacitor_factor_solve(rhs, p0, xp=xp)
    response = ports.T @ solved  # E^T K0^-1 E (1/F): the targets' ports seen through K0.
    root = xp.sqrt(dc)
    matrix = xp.eye(dc.size) + root[:, None] * response * root[None, :]
    lower = xp.linalg.cholesky(0.5 * (matrix + matrix.T))  # One symmetric matrix on either xp.
    scaled = xp.linalg.solve(lower, root * jump)
    return 0.5e12 * xp.sum(scaled**2)


def check_carriers(rows, transference, valence, what):
    """Refuse declared carriers of a moved plate charge (host, at the definition): distinct
    species rows, each charged (a neutral species carries no charge), with transference numbers
    t_s > 0 that sum to 1 within rounding."""
    rows, transference = tuple(rows), tuple(transference)
    if not rows or len(set(rows)) != len(rows) or len(rows) != len(transference):
        raise ConfigError(f"{what}: carriers are distinct species rows, one transference each")
    neutral = [r for r in rows if valence[r] == 0]
    if neutral:
        raise ConfigError(
            f"{what}: a carrier of charge has a nonzero valence; row {neutral[0]} is neutral"
        )
    if any(not (math.isfinite(t) and t > 0) for t in transference) or not math.isclose(
        math.fsum(transference), 1.0, rel_tol=0.0, abs_tol=4 * len(rows) * 2.0**-52
    ):
        raise ConfigError(f"{what}: transference numbers are positive and sum to 1")


def carrier_scale(rows, transference, valence, species):
    """[species] the amount (fmol) each row carries per coulomb of a moved plate charge: t_s / (z_s
    F) at a carrier, 0 elsewhere (host, at binding, after check_carriers): layout data, so a change
    of carriers or transference reuses the executable."""
    scale = np.zeros(species)
    for row, t in zip(rows, transference, strict=True):
        scale[row] = t / (valence[row] * CHARGE_PER_FMOL)
    return scale


def carrier_amounts(charge_C, scale, *, xp):
    """[species, nodes] the carriers' amounts (fmol) that carry charge_C [nodes] (C): carrier s
    takes t_s of each node's charge, delta_s = t_s charge / (z_s F), the partition's rule
    (operators/partition.py); every other row moves nothing. scale: carrier_scale's."""
    return xp.asarray(scale)[:, None] * charge_C[None, :]
