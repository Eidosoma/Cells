"""The lifecycle by roles: the composite's refusal of kinds beside closers, lifted by role
(docs/CORE_SEAMS_DESIGN.md §4.2; the lead's rulings of 18 November 2026, CORE_SEAMS §18: Q1, Q2,
Q4, Q7 (a)); models/pump_composite_adapter.py's role table.

A kind beside an operator that closes, retires or provides activity masks is admitted only when the
lifecycle acts on every field it holds, checked in order:
1. every partition field declares a role: a kind that declares none keeps today's refusal, word for
   word (test_pump_composite_kinds.py holds the words for every slot changer);
2. every layout and control field declares its axes (Q1, the kind contract's declaration);
3. every entity axis it has declares at least one presence field (the lift of Q7 (a) after Q2's
   presence gate, the lead's ruling of 19 November 2026): a planted per-patch kind without
   presence stays refused, and the transporter declaring its three masks is admitted. Entity
   axes are F's (kind_registry.entity_axes): neither the shared axes, one set with F's, nor a
   kind's internal axes, so a kind whose only extra axis is internal needs no presence;
4. every entity axis has a host the presence gate reads: @3's slot axes it closes (one list with
   the gate's, surface_pump_v3.PRESENCE_SLOT_AXES, channel populations and faces included), or an
   own axis's declared axis_hosts: a planted own axis without them stays refused.
A planted kind with roles and axes and no per-entity field is admitted beside every slot changer.
Beside a dividing closer, a kind's own entity axes wait for B2's own-axis maps (refused).
@3's role table is converted once (Q4): structural fields fill with 0, and the pumps' history is
left to the closers' records until composition's M5 Q2.
"""

import dataclasses
from types import MappingProxyType

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite, surface_pump_v3
from cells.models import pump_composite_adapter as pump3
from cells.operators import OPERATORS, partition
from cells.registry import kind_registry
from cells.registry.kind_registry import Kind, PartitionRole
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from tests import partition_fixtures as pfx
from tests.unit.test_pump_composite_kinds import SLOT_CHANGERS, composite, world

RETIRES = "opens, closes or retires slots"


def roles_for(kind, role="intensive"):
    """Every partition field of `kind` with `role`."""
    return {name: PartitionRole(role) for name in kind_registry.partition_fields(kind)}


def axed(kind, axes, **changes):
    """`kind` with `axes` for its layout and control fields: the kind contract's `field_axes`
    (Q1's declaration, F's, which stood in here as a subclass until it landed)."""
    return dataclasses.replace(kind, **changes, field_axes=MappingProxyType(axes))


def carrier_with_roles():
    carrier = kf.carrier()
    return dataclasses.replace(carrier, partition_roles=roles_for(carrier))


def _shared_initial(spec, declaration, layout, *, bands=None):
    """The shared carrier's species-only state and layout ([bands, species] for its rate where it
    has a band axis internal to its law)."""
    species = len(spec.model.species_ids)
    state = dict(carrier_transferred=np.zeros(species), carrier_work_pJ=np.zeros(species))
    rate = np.zeros(species if bands is None else (bands, species))
    return state, dict(carrier_rate_fmol_s=rate)


def _shared_rates(state, potentials, control, p, *, xp):
    """The shared carrier moves nothing: no node change, derivative, heat or work."""
    return kind_registry.KindRates(
        cell=xp.zeros_like(state.amount_increment),
        outside=xp.zeros_like(state.extracellular_amount_increment),
        derivatives=dict(
            carrier_transferred=xp.zeros_like(state.carrier_transferred),
            carrier_work_pJ=xp.zeros_like(state.carrier_work_pJ),
        ),
        heat_pJ_s=xp.zeros(()),
        work_pJ_s=xp.zeros(()),
    )


def _shared_ledger_terms(state, p, *, xp):
    return dict(
        cell=xp.zeros_like(state.amount_increment),
        outside=xp.zeros_like(state.extracellular_amount_increment),
        work_pJ=state.carrier_work_pJ,
    )


def _shared_domain(state, p, *, xp):
    moved, work = state.carrier_transferred, state.carrier_work_pJ
    return xp.all(xp.isfinite(moved) & (moved >= 0)) & xp.all(xp.isfinite(work))


def shared_carrier():
    """The carrier with every field on shared axes (no entity) and its axes declared: a planted
    kind the lifecycle need not act on. Its state and layout are species-only to match those axes,
    so it moves nothing and carries no current (F's array-axes check, D228 item 6: the review found
    the carrier's species x patches arrays here)."""
    carrier = kf.carrier()
    state = tuple((name, ("species",)) for name, _ in carrier.state_axes)
    flat = dataclasses.replace(
        carrier,
        state_axes=state,
        initial=_shared_initial,
        rates=_shared_rates,
        ledger_terms=_shared_ledger_terms,
        domain=_shared_domain,
        readouts=lambda state, read, potentials, control, p, *, xp: (
            xp.zeros_like(p.membrane_area),
        ),
        moved_rows=lambda declaration: (),
    )
    kind = axed(flat, {"carrier_rate_fmol_s": ("species",), "carrier_availability": ()})
    return dataclasses.replace(kind, partition_roles=roles_for(kind))


def errors_beside(kind, law):
    with kind_registry.scope(kf.registry(kind)):
        inner = get_model(composite(kf.declare_carrier(world(), species="K")).model).inner
        assert inner.BOUND_KINDS and inner.BOUND_KINDS[0].kind_id == kf.CARRIER_ID
        return [
            e for e in pump_composite.structure_errors(inner, (OPERATORS[law],)) if RETIRES in e
        ]


def test_the_reasons_come_in_order():
    carrier = kf.carrier()
    assert pump3.kind_lifecycle_errors(carrier) == (
        "roles",
        kind_registry.partition_fields(carrier),
    )
    with_roles = carrier_with_roles()
    assert pump3.kind_lifecycle_errors(with_roles) == (
        "axes",
        ("carrier_rate_fmol_s", "carrier_availability"),
    )
    on_patches = axed(
        with_roles,
        {"carrier_rate_fmol_s": ("species", "membrane_slot"), "carrier_availability": ()},
    )
    assert pump3.kind_field_axes(on_patches)["carrier_work_pJ"] == ("membrane_slot",)
    assert pump3.kind_lifecycle_errors(on_patches) == ("presence", ("membrane_slot",))
    assert pump3.kind_lifecycle_errors(shared_carrier()) == ()
    assert set(pump3.kind_role_table(shared_carrier())) == set(
        kind_registry.partition_fields(shared_carrier())
    )


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_a_kind_without_roles_keeps_todays_refusal(law):
    assert errors_beside(kf.carrier(), law) == [
        f"{law} opens, closes or retires slots, and no closer resets a kind's per-slot fields, so "
        f"it does not run beside declared kinds ({kf.CARRIER_ID})"
    ]


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_a_kind_with_roles_is_refused_while_an_axis_is_undeclared(law):
    """Planted: roles alone do not lift the refusal; the layout and control fields' axes are
    unknown, so the lifecycle could not act on them."""
    assert errors_beside(carrier_with_roles(), law) == [
        f"{law} opens, closes or retires slots, and the kind {kf.CARRIER_ID} declares no axes for "
        "carrier_rate_fmol_s, carrier_availability, so the lifecycle cannot act on them by role"
    ]


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_a_per_entity_kind_without_presence_stays_refused(law):
    """Planted: roles and axes on a per-patch kind whose axis declares no presence field. The
    core's presence gate could not make its entities absent on a closed patch, so its rates would
    keep running there at the view: Q7 (a)'s refusal stands for it."""
    kind = axed(
        carrier_with_roles(),
        {"carrier_rate_fmol_s": ("species", "membrane_slot"), "carrier_availability": ()},
    )
    assert errors_beside(kind, law) == [
        f"{law} opens, closes or retires slots, and the kind {kf.CARRIER_ID} declares no presence "
        "field on its entity axes (membrane_slot), so the core's presence gate cannot make its "
        "entities there absent where their host is closed"
    ]


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_a_kind_the_lifecycle_need_not_act_on_is_admitted_beside_a_closer(law):
    """The lift: every field has a role and declared axes, and none is per-entity."""
    assert errors_beside(shared_carrier(), law) == []


# ------------------------------------------------------------------ the lift of Q7 (a) (item 3)
# After Q2's presence gate (the lead's rulings of 19 November 2026): a kind beside a closer is
# admitted once every entity axis it has declares at least one presence field (F's contract:
# Kind.presence, read through kind_registry.presence_fields), since the core's gate then makes an
# entity on a closed host absent. The plant is the real transporter.

THREE_MASKS = ("transporter_present", "transporter_neutral", "transporter_proton")


def test_one_set_of_shared_axes():
    """The adapter's shared axes are F's (kind_registry.SHARED_AXES), so the lifecycle and the
    contract's entity_axes count entities alike."""
    assert pump3.SHARED_AXES is kind_registry.SHARED_AXES
    assert pump3.SHARED_AXES == ("species", "gate")


def test_a_kind_whose_only_extra_axis_is_internal_needs_no_presence():
    """A shared-axis carrier with a layout field on an axis internal to its law (F's internal_axes)
    has no entity axis, so it needs no presence and is admitted beside every slot changer. Planted:
    the same axis not declared internal is an entity axis without presence, refused."""
    kind = axed(
        shared_carrier(),
        {"carrier_rate_fmol_s": ("carrier_band", "species"), "carrier_availability": ()},
        internal_axes=("carrier_band",),
        initial=lambda spec, declaration, layout: _shared_initial(
            spec, declaration, layout, bands=1
        ),
    )
    assert kind_registry.entity_axes(kind) == () and pump3.kind_lifecycle_errors(kind) == ()
    for law in SLOT_CHANGERS:
        assert errors_beside(kind, law) == [], law
    planted = dataclasses.replace(kind, internal_axes=())
    assert pump3.kind_lifecycle_errors(planted) == ("presence", ("carrier_band",))


def planted_transporter(presence=MappingProxyType({"membrane_slot": THREE_MASKS})):
    """The built-in transporter (cells.kind.transporter@1) with the seams' declarations the lift reads:
    a role for every field, the layout and control fields' axes, its fuel rows' axis internal to
    its law, and `presence` (by default its three masks)."""
    from cells.kinds import transporter

    layout = (*transporter.LAYOUT_FIELDS, *transporter.CONTROL_FIELDS)
    roles = {name: PartitionRole("history") for name, _ in transporter.STATE_AXES}
    roles |= {name: PartitionRole("intensive") for name in layout}
    roles |= {
        name: PartitionRole("structural", False) for name in (*THREE_MASKS, "transporter_held")
    }
    roles |= {
        k: PartitionRole("structural", 0) for k in ("transporter_role", "transporter_fuel_rows")
    }
    roles["transporter_capacity_fmol_s"] = PartitionRole("extensive")
    axes = dict.fromkeys(layout, ("membrane_slot",))
    axes |= dict(transporter_fuel_rows=("transporter_fuel", "membrane_slot"), transporter_c0_mM=())
    return dataclasses.replace(
        transporter.TRANSPORTER,
        partition_roles=MappingProxyType(roles),
        field_axes=MappingProxyType(axes),
        internal_axes=("transporter_fuel",),
        presence=MappingProxyType(dict(presence)),
    )


def transporter_beside(kind, law):
    """(the slot-changer refusals, the lifecycle refusals) of `law` beside the transporter world
    (tests/unit/test_transporter_kind.held_world) with `kind` registered."""
    from tests.unit.test_transporter_kind import held_world, scoped

    with scoped(kind):
        inner = get_model(composite(held_world()).model).inner
        assert [k.kind_id for k in inner.BOUND_KINDS] == [kind.kind_id]
        ops = (OPERATORS[law],)
        found = [e for e in pump_composite.structure_errors(inner, ops) if RETIRES in e]
        return found, pump_composite.lifecycle_errors(inner, ops)


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_the_transporter_declaring_its_three_masks_is_admitted_beside_a_closer(law):
    """Admitted beside each closer (the partition, insertion@2), where the core's presence gate
    acts (@3's padding_fill: a declared CLOSES). Beside insertion@1 alone, which provides the masks
    without closing them, no closer is declared and the gate is off, so its entities would keep
    running on an onset patch before its onset: refused, fail-closed."""
    kind = planted_transporter()
    assert kind_registry.declaration_errors(kind) == []
    assert kind_registry.entity_axes(kind) == ("membrane_slot",)  # Its fuel rows' axis: internal.
    assert pump3.kind_lifecycle_errors(kind) == ()
    found, lifecycle = transporter_beside(kind, law)
    assert lifecycle == []
    if OPERATORS[law].CLOSES:
        assert found == []
    else:
        from cells.kinds import transporter

        assert found == [
            f"{law} opens, closes or retires slots, but no closer is declared, so the core's "
            f"presence gate is off and the kind {transporter.KIND_ID}'s entities on membrane_slot "
            "would keep running where the view closes their host"
        ]


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_the_transporter_without_presence_stays_refused(law):
    """Planted: the same transporter declaring no presence; Q7 (a)'s refusal stands for it."""
    from cells.kinds import transporter

    found, _ = transporter_beside(planted_transporter(presence={}), law)
    assert found == [
        f"{law} opens, closes or retires slots, and the kind {transporter.KIND_ID} declares no "
        "presence field on its entity axes (membrane_slot), so the core's presence gate cannot "
        "make its entities there absent where their host is closed"
    ]


def own_axis_kind(host):
    """A planted kind on one entity axis of its own, `planted_site`, hosted on `host`'s slots
    (F's axis_hosts), with its presence declared: the lift admits it beside a closer."""
    fields = ("planted_site_host", "planted_site_present", "planted_site_k")
    roles = dict(
        planted_site_host=PartitionRole("structural", 0),
        planted_site_present=PartitionRole("structural", False),
        planted_site_k=PartitionRole("intensive"),
    )
    return Kind(
        kind_id="tests.kind.planted_sites@1",
        model_key="test_planted_sites",
        layout_fields=fields,
        partition_roles=MappingProxyType(roles),
        field_axes=MappingProxyType(dict.fromkeys(fields, ("planted_site",))),
        axis_hosts=MappingProxyType(
            {"planted_site": kind_registry.AxisHost(host, "planted_site_host")}
        ),
        presence=MappingProxyType({"planted_site": ("planted_site_present",)}),
    )


def test_own_entity_axes_wait_for_own_axis_maps_beside_a_dividing_closer():
    """B1's division splits and retires @3's slot axes only (B2 adds own-axis maps), so a kind's
    own entity axis hosted on cells, patches or contacts is refused beside a retiring operator,
    fail-closed: its entities would neither divide nor retire. A closer that does not divide
    admits it (presence gates it), as does an own axis hosted on outside nodes, which never
    divide."""
    from types import SimpleNamespace

    retiring = (OPERATORS[partition.LAW_ID],)
    closing = (OPERATORS["cells.operator.scheduled_membrane_insertion@2"],)
    patches = own_axis_kind("patch")
    assert kind_registry.declaration_errors(patches) == []
    assert pump3.kind_lifecycle_errors(patches) == ()
    assert pump_composite.own_axes(patches) == ("planted_site",)
    inner = SimpleNamespace(BOUND_KINDS=(patches,))
    assert pump_composite.lifecycle_errors(inner, retiring) == [
        "The kind tests.kind.planted_sites@1's own entity axes ['planted_site'] are refused beside a "
        "dividing closer until own-axis maps exist (B2): a division would neither split nor "
        "retire their entities (fails closed)"
    ]
    assert pump_composite.lifecycle_errors(inner, closing) == []
    nodes = SimpleNamespace(BOUND_KINDS=(own_axis_kind("outside_node"),))
    assert pump_composite.lifecycle_errors(nodes, retiring) == []


def test_inner_roles_are_converted_once():
    """@3's string table (surface_pump_v3.FIELD_ROLES' form) into PartitionRole: a structural
    field fills with 0, every other role carries none, and excluded fields are left out."""
    table = {
        "channel_gate": "intensive",
        "membrane_area": "extensive",
        "pump_cycles": "history",
        "channel_laws": "structural",
    }
    axes = {
        "channel_gate": ("gate", "channel_slot"),
        "membrane_area": ("membrane_slot",),
        "pump_cycles": ("membrane_slot",),
        "channel_laws": ("channel_slot",),
    }
    roles = pump3.inner_role_table(table, axes, excluded=("pump_cycles",))
    assert roles == {
        "channel_gate": (PartitionRole("intensive"), ("gate", "channel_slot")),
        "membrane_area": (PartitionRole("extensive"), ("membrane_slot",)),
        "channel_laws": (PartitionRole("structural", 0), ("channel_slot",)),
    }
    for role, _ in roles.values():  # Each is a role F's contract admits.
        assert role.role in kind_registry.PARTITION_ROLES
        assert (role.fill is not None) == (role.role == "structural")


def test_the_held_row_check_reads_the_kind_bound_to_its_entry(monkeypatch):
    """The composite's held-row check (gap 8) reads the kind bound to its declaration's structure
    entry, the hooks the step runs. Planted: a bound kind that holds F at its cell while its static
    form holds nothing (a per-entry hook). A static read would admit the in-step writer of F
    (fail-open); the bound read refuses it."""
    from cells.definitions import pump_composite_spec as cs
    from cells.definitions.specs import parse_spec
    from tests.unit.test_pump_composite_writers import HELD, Writer, declared, holding_world

    with kind_registry.scope(kf.registry()):
        spec = parse_spec(cs.frozen_definition(holding_world()))
        pairs = [(Writer(), declared((HELD, "cell")))]
        assert kind_registry.active().lookup(kf.KIND_ID).held_rows is None  # Static: holds none.
        assert pump_composite.held_row_errors(pairs, spec) == []
        real = kind_registry.bound

        def per_entry(kind, entry):
            out = real(kind, entry)
            if out.kind_id != kf.KIND_ID:
                return out
            return dataclasses.replace(out, held_rows=lambda d: ((HELD, d[1]),))

        monkeypatch.setattr(kind_registry, "bound", per_entry)
        errors = pump_composite.held_row_errors(pairs, spec)
        assert len(errors) == 1 and errors[0].startswith(f"Kind {kf.KIND_ID} holds F at cell_0")


# ------------------------------------------------------------------ @3's roles and the partition
# B1's last slice, its equality checks (the lead's rulings of 19 November 2026 on design statement
# 1, CORE_SEAMS §18): tests only. partition.event_map's hand-written handling of @3's fields
# stays, and these show that @3's role table (surface_pump_v3.FIELD_ROLES, converted once)
# reproduces it. Each check has a flipped-role plant.

RETIRED_AXES = ("membrane_slot", "edge_slot", "channel_slot")  # What a retired cell takes down.
DIVIDED_AXES = ("cell_slot", "membrane_slot", "edge_slot")  # Where check_structure checks anchors.
# The pumps' history, left to the closers' own records until composition's M5 Q2.
PUMP_HISTORY = (
    "pump_cycles",
    "pump_dissipated_energy_pJ",
    "metabolic_work_pJ",
    "calcium_pump_cycles",
    "calcium_pump_dissipated_energy_pJ",
    "calcium_metabolic_work_pJ",
)
PUMP_CAPACITIES = ("pump_capacity", "calcium_pump_capacity")  # Refused on a dividing cell.
# check_structure's anchors, by the layout field each check holds: per cell the volume, the species'
# amounts and the charge anchor (its fixed-charge check has no layout field of its own: it enters
# the charge anchor); per patch the area and capacitance; per contact the area.
CHECKED_ANCHORS = {
    "volume",
    "amount_reference",
    "initial_cell_charge_C",
    "membrane_area",
    "membrane_capacitance",
    "junction_area",
}
# What closure (pump_composite_adapter.close) leaves unpadded although its role pads it at
# retirement, by kind. A new field in none of these and not padded fails the test and forces a
# decision (the lead's ruling 6).
UNPADDED = {
    "geometry, kept for the capacitor solve": {
        "volume",
        "extracellular_volume",
        "membrane_area",
        "membrane_capacitance",
        "junction_area",
    },
    "parameters read only on active slots (the masks)": {
        "membrane_permeability",
        "channel_abundance",
        "channel_permeability",
        "channel_relative_permeability",
        "junction_permeability",
        "junction_threshold_voltage",
    },
    "hosts and ends, the topology kept": {
        "channel_membranes",
        "membrane_cell",
        "membrane_outside",
        "junction_sender",
        "junction_receiver",
    },
    "the pumps, gated by their host's activity": {
        "pump_present",
        "calcium_pump_present",
        "pump_capacity",
        "calcium_pump_capacity",
    },
}
SIZES = dict(  # Distinct capacities, so each layout array's shape names its axes.
    capacity=5,
    extracellular_capacity=6,
    membrane_capacity=7,
    edge_capacity=8,
    face_capacity=9,
    channel_capacity=10,
)
AXIS_OF_SIZE = {
    5: "cell_slot",
    6: "extracellular_slot",
    7: "membrane_slot",
    8: "edge_slot",
    9: "face_slot",
    10: "channel_slot",
}


@pytest.fixture(scope="module")
def inner_roles():
    """@3's role table converted once ({field: (PartitionRole, axes)}): the state fields' axes from
    the adapter's STATE_AXES, each layout field's read from a parsed world's layout, whose
    capacities are all distinct (padding included), so an array's shape names its axes."""
    from cells.definitions.specs import parse_spec
    from cells.models import surface_pump_v3
    from validation.tissue import secreted_species_fixtures as fx

    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"),),
        faces=(),
        end=0.004,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6),
    )
    raw["execution"].update(SIZES)
    spec = parse_spec(raw)
    _, p = get_model(spec.model).initial_values(spec)
    layout = pump3.inner_layout(p)
    species = len(spec.model.species_ids)
    assert species not in AXIS_OF_SIZE
    axes = {name: tuple(axis) for name, axis in pump3.STATE_AXES.items()}
    for name in surface_pump_v3.FIELD_ROLES:
        if name not in axes:
            shape = getattr(layout, name).shape
            axes[name] = tuple(
                "species" if size == species else AXIS_OF_SIZE[size] for size in shape
            )
    return pump3.inner_role_table(surface_pump_v3.FIELD_ROLES, axes)


def retired_history(table):
    """The history state fields on the retired axes, less the pumps': what a retirement records."""
    return {
        name
        for name, (role, axes) in table.items()
        if name in pump3.STATE_AXES and role.role == "history" and set(axes) & set(RETIRED_AXES)
    } - set(PUMP_HISTORY)


def resets(table):
    """The intensive state fields: what a division copies to the daughters."""
    state = pump3.STATE_AXES
    return {k for k, (role, _) in table.items() if k in state and role.role == "intensive"}


def anchors(table):
    """The extensive layout fields on the divided axes, less the pumps' capacities."""
    return {
        name
        for name, (role, axes) in table.items()
        if name not in pump3.STATE_AXES
        and role.role == "extensive"
        and set(axes) & set(DIVIDED_AXES)
    } - set(PUMP_CAPACITIES)


def padded(table):
    """The layout fields whose role pads them at retirement, less what closure leaves unpadded."""
    left = set().union(*UNPADDED.values())
    return {
        name
        for name, (role, _) in table.items()
        if name not in pump3.STATE_AXES and role.role in ("extensive", "intensive", "structural")
    } - left


def flipped(table, name, role):
    out = dict(table)
    out[name] = (PartitionRole(role, 0 if role == "structural" else None), table[name][1])
    return out


def test_roles_reproduce_the_partitions_retirement_record(inner_roles):
    from cells.operators import partition

    assert retired_history(inner_roles) == set(partition.RECORD)
    # Planted: a retired history field taken for an intensive one leaves the record.
    assert retired_history(flipped(inner_roles, "junction_transferred", "intensive")) != set(
        partition.RECORD
    )


def test_roles_reproduce_the_partitions_kinetic_resets(inner_roles):
    from cells.operators import partition

    resets_declared = OPERATORS[partition.LAW_ID].STATE_RESETS
    assert resets(inner_roles) == set(resets_declared) == {"channel_gate", "junction_gate"}
    assert resets(flipped(inner_roles, "junction_gate", "history")) != set(resets_declared)


def test_roles_reproduce_the_anchors_the_partition_checks(inner_roles):
    assert anchors(inner_roles) == CHECKED_ANCHORS
    assert anchors(flipped(inner_roles, "membrane_capacitance", "intensive")) != CHECKED_ANCHORS


def test_roles_reproduce_closures_padded_fields_but_for_what_the_masks_hold(inner_roles):
    """PADDED_FIELDS is the padded roles' layout fields less what closure leaves unpadded (UNPADDED,
    written here by kind). Every field of UNPADDED has a padding role, the kinds are disjoint, and
    none of them is padded."""
    assert padded(inner_roles) == set(pump3.PADDED_FIELDS)
    groups = list(UNPADDED.values())
    assert sum(len(g) for g in groups) == len(set().union(*groups))  # Disjoint.
    for name in set().union(*groups):
        assert inner_roles[name][0].role in ("extensive", "intensive", "structural"), name
        assert name not in pump3.PADDED_FIELDS, name
    assert padded(flipped(inner_roles, "channel_laws", "history")) != set(pump3.PADDED_FIELDS)


# ------------------------------------------------------------------ the lifecycle by roles (step A)
# The single lifecycle implementation for kinds' state fields
# (pump_composite_adapter.lifecycle_split and lifecycle_retire): the split by the
# partition's maps, retirement by its masks. Nothing calls it in a program yet (B wires it
# to the partition's event, beside a kind with entity fields, which Q7 (a) still refuses),
# so it is tested on planted states over a parsed division world.


@pytest.fixture(scope="module")
def division():
    """FR-1's division world with a neighbour (tests/partition_fixtures.divided), bound: its spec,
    model, initial state and layout, and its one division due."""
    import numpy as np

    from tests import partition_fixtures as pfx
    from tests.unit.test_partition import bind

    spec, model, state, p = bind(pfx.divided(neighbour=True))
    return spec, model, state, p, np.ones(1, dtype=bool)


def test_the_retirement_masks_are_what_the_partitions_event_retires(division):
    """partition.retirement_masks, the one source the lifecycle reads, equals what event_map moves
    into the partition's record for @3's history: with history 1 on every active slot, the record
    holds 1 exactly where the mask is set."""
    import numpy as np

    from cells.operators import partition
    from tests.unit.test_partition import divide

    spec, model, state, p, due = division
    axes = dict(pump3.STATE_AXES)
    ones = {
        k: np.where(np.ones_like(np.asarray(getattr(state, k))) > 0, 1.0, 0.0)
        for k in partition.RECORD
    }
    after, ok = divide(model, state._replace(**ones), p)
    assert bool(ok)
    masks = partition.retirement_masks(due, p, xp=np)
    for field, record in partition.RECORD.items():
        mask = masks[axes[field][-1]]
        kept = np.asarray(getattr(after, record)) != 0
        assert (kept == np.broadcast_to(mask, kept.shape)).all(), field
    assert masks["membrane_slot"].any() and not masks["membrane_slot"].all()


PLANTED_ROLES = {
    "planted_amount_fmol": (PartitionRole("extensive"), ("species", "membrane_slot")),
    "planted_cell_amount_fmol": (PartitionRole("extensive"), ("cell_slot",)),
    "planted_saturation": (PartitionRole("intensive"), ("membrane_slot",)),
    "planted_cycles": (PartitionRole("history"), ("membrane_slot",)),
    "planted_law": (PartitionRole("structural", 7), ("membrane_slot",)),
    "planted_node_amount_fmol": (PartitionRole("extensive"), ("extracellular_slot",)),
}


def planted_values(p, *, value=0.3):
    """Planted kind state: every slot of each planted field at `value`, but the history's daughters
    (pending slots) at 0."""
    import numpy as np

    from cells.operators import partition

    sizes = dict(
        membrane_slot=p.membrane_active.size,
        cell_slot=p.active.size,
        extracellular_slot=p.outside_active.size,
    )
    out = {}
    for name, (_, axes) in PLANTED_ROLES.items():
        shape = tuple(2 if a == "species" else sizes[a] for a in axes)
        out[name] = np.full(shape, value)
    maps = partition.division_maps(np.ones(1, dtype=bool), p)
    out["planted_cycles"][..., maps["membrane_slot"][1].ravel()] = 0.0
    return out


def test_the_split_follows_each_role_through_the_partitions_maps(division):
    import numpy as np

    from cells.operators import partition

    spec, model, state, p, due = division
    values = planted_values(p)
    maps = partition.division_maps(due, p)
    out, valid = pump3.lifecycle_split(values, PLANTED_ROLES, maps, xp=np)
    assert bool(valid)
    for axis, name in (
        ("membrane_slot", "planted_amount_fmol"),
        ("cell_slot", "planted_cell_amount_fmol"),
    ):
        parent, kids, fraction, _ = maps[axis]
        x = values[name][..., parent]
        one, two = out[name][..., kids[:, 0]], out[name][..., kids[:, 1]]
        assert (one == fraction * x).all() and (two == x - fraction * x).all()
        assert (one + two == x).all() and (out[name][..., parent] == 0).all()  # Exactly.
    parent, kids, _, _ = maps["membrane_slot"]
    assert (out["planted_saturation"][kids] == values["planted_saturation"][parent][:, None]).all()
    for name in ("planted_cycles", "planted_law", "planted_node_amount_fmol"):
        assert (out[name] == values[name]).all(), name  # Untouched: history, structure, no map.
    # An extensive field on edge slots, whose map binds no fraction, is refused.
    contact = {"planted_contact_fmol": (PartitionRole("extensive"), ("edge_slot",))}
    edges = {"planted_contact_fmol": np.ones(p.junction_active.size)}
    with pytest.raises(ValueError, match="needs its map's fraction"):
        pump3.lifecycle_split(edges, contact, maps, xp=np)
    # Planted: a pending daughter that already holds history makes the split invalid.
    stale = dict(values, planted_cycles=np.full_like(values["planted_cycles"], 0.3))
    assert not bool(pump3.lifecycle_split(stale, PLANTED_ROLES, maps, xp=np)[1])


def test_retirement_records_history_and_pads_the_rest(division):
    import numpy as np

    from cells.operators import partition

    spec, model, state, p, due = division
    values = planted_values(p, value=1.0)
    masks = partition.retirement_masks(due, p, xp=np)
    records = {
        "planted_cycles": ("planted_cycles_retired", np.zeros_like(values["planted_cycles"]))
    }
    out, kept = pump3.lifecycle_retire(values, PLANTED_ROLES, masks, records, xp=np)
    gone = masks["membrane_slot"]
    assert (kept["planted_cycles_retired"] == np.where(gone, 1.0, 0.0)).all()
    assert (
        out["planted_cycles"] + kept["planted_cycles_retired"] == values["planted_cycles"]
    ).all()
    assert (out["planted_amount_fmol"][..., gone] == 0).all() and (
        out["planted_saturation"][gone] == 0
    ).all()
    assert (out["planted_law"][gone] == 7).all() and (out["planted_law"][~gone] == 1.0).all()
    assert (out["planted_cell_amount_fmol"][masks["cell_slot"]] == 0).all()
    assert (out["planted_node_amount_fmol"] == 1.0).all()  # Outside nodes are never retired.
    # Planted: a history field with no record would lose its history, so it is refused.
    with pytest.raises(ValueError, match="retires only into its record"):
        pump3.lifecycle_retire(values, PLANTED_ROLES, masks, {}, xp=np)


def test_the_lifecycle_acts_along_one_entity_axis_its_last():
    assert pump3.lifecycle_axis("gates", ("gate", "channel_slot")) == "channel_slot"
    assert pump3.lifecycle_axis("shared", ("species",)) is None
    for axes in (("membrane_slot", "species"), ("membrane_slot", "channel_slot")):
        with pytest.raises(ValueError, match="one entity axis, its last"):
            pump3.lifecycle_axis("planted", axes)


# ------------------------------------------------------------------ the record and the door (B)
# Q6 (b): the composite owns a record per kind history field (and a moved accumulator per
# extensive one), written through the partition's event (lifecycle=), added back before the
# checks; ruling 4 (b): field plus record unchanged across a retiring event. Q7 (a) refuses a
# per-patch kind beside the partition, so these patch pump_composite._kinds_lifecycle only (the
# accepted bypass, as the silence tests bypass refusals 4 and 5).


def per_patch_carrier(transferred="history"):
    """The carrier with its two state fields per patch (its transfers, history unless given, and
    its work, history), its rate per patch as its arrays hold it (F's array-axes check, D228 item
    6), and its availability on shared axes."""
    kind = axed(
        kf.carrier(),
        {"carrier_rate_fmol_s": ("species", "membrane_slot"), "carrier_availability": ()},
    )
    roles = roles_for(kind, "intensive") | {
        "carrier_transferred": PartitionRole(transferred),
        "carrier_work_pJ": PartitionRole("history"),
        # Its rate is per patch, set at its declared patch alone: structural (as declared), so
        # each daughter patch keeps the 0 the carrier's initial values give every other patch.
        # Intensive or extensive would claim the parent's rate there, which step C refuses. The
        # fill pads only a state field's retired slot, so nothing reads it for this layout field.
        "carrier_rate_fmol_s": PartitionRole("structural", 0.0),
    }
    return dataclasses.replace(kind, partition_roles=roles)


@pytest.fixture(params=["history"])
def lifecycle_world(monkeypatch, request):
    """The division world with the carrier on its parent's first patch, parsed with the bypass:
    (spec, model, a planted pre-event state with history on that patch, layout, patch slot)."""
    import numpy as np

    from cells.definitions.specs import parse_spec
    from tests import partition_fixtures as pfx

    monkeypatch.setattr(
        pump_composite, "_kinds_lifecycle", lambda inner, kinds: dict.fromkeys(kinds, ())
    )
    raw = pfx.divided()
    division = next(o for o in raw["model"]["operators"] if o["law"] == "cells.operator.isopotential_partition@1")
    parent = division["divisions"][0]["parent"]
    patch = next(m["id"] for m in raw["model"]["membranes"] if m["inside"] == parent)
    with kind_registry.scope(kf.registry(per_patch_carrier(request.param))):
        spec = parse_spec(kf.declare_carrier(raw, species="K", membrane=patch))
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        k = [m.id for m in spec.model.membranes].index(patch)
        transferred = np.array(state.carrier_transferred, copy=True)
        transferred[:, k] = 0.2
        work = np.array(state.carrier_work_pJ, copy=True)
        work[k] = 1e-6
        yield (
            spec,
            model,
            state._replace(carrier_transferred=transferred, carrier_work_pJ=work),
            p,
            k,
        )


def retire(model, state, p):
    from types import SimpleNamespace

    import numpy as np

    from cells.operators import partition

    op = next(o for o in model.operators if o.LAW_ID == partition.LAW_ID)
    control = SimpleNamespace(partition_due=np.ones(1))
    view = lambda s: model.view(p, s, xp=np)  # noqa: E731
    return op.event(state, control, p, xp=np, view=view, lifecycle=model._lifecycle)


def test_the_composite_owns_a_record_per_kind_history_field(lifecycle_world):
    """The records are composite state, named without the energy suffix (ruling 3)."""
    spec, model, state, p, k = lifecycle_world
    assert model.KIND_RECORDS == {
        "carrier_transferred": "carrier_transferred_retired",
        "carrier_work_pJ": "carrier_retired_work_energy_pJ",
    }
    assert model.KIND_MOVED == {}
    assert model.FIELD_MAP["state"]["carrier_transferred_retired"]["owner"] == "composite"
    records = set(model.KIND_RECORDS.values())
    assert not records & set(model.ENERGY_FLOW_FIELDS)  # In no energy sum by role,
    assert not any(r.endswith(("_dissipated_energy_pJ", "_work_pJ")) for r in records)  # nor name.


def test_a_retirement_moves_the_kinds_history_into_the_record_and_back_for_the_checks(
    lifecycle_world,
):
    import numpy as np

    spec, model, state, p, k = lifecycle_world
    after, ok = retire(model, state, p)
    assert bool(ok)
    assert (np.asarray(after.carrier_transferred)[:, k] == 0).all()
    assert (np.asarray(after.carrier_transferred_retired)[:, k] == 0.2).all()
    assert float(np.asarray(after.carrier_retired_work_energy_pJ)[k]) == 1e-6
    assert bool(model._history_kept(state, after, xp=np))
    adjusted = model._adjusted(after, p, xp=np)
    assert (np.asarray(adjusted.carrier_transferred) == np.asarray(state.carrier_transferred)).all()
    # The ledgers read the adjusted row as if nothing moved: each equals the pre-event one.
    before_l, after_l = model.balances(state, p), model.balances(after, p)
    for name in ("local", "energy"):
        np.testing.assert_allclose(after_l[name], before_l[name], rtol=1e-9, atol=1e-15)


def test_a_retirement_that_loses_history_is_refused(lifecycle_world, monkeypatch):
    """Planted (ruling 4): the lifecycle's retirement drops the record. The field-plus-record check
    refuses it whatever the field (a cycle count no ledger reads included), and the material ledger
    that reads the transfers sees them gone."""
    import numpy as np

    spec, model, state, p, k = lifecycle_world
    real = pump3.lifecycle_retire

    def losing(values, table, masks, records, *, xp, **kwargs):
        out, kept = real(values, table, masks, records, xp=xp, **kwargs)
        return out, {r: held for r, held in records.values()}  # The history zeroed, not kept.

    monkeypatch.setattr(pump3, "lifecycle_retire", losing)
    after, ok = retire(model, state, p)
    assert not bool(model._history_kept(state, after, xp=np))
    before_l, after_l = model.balances(state, p), model.balances(after, p)
    assert np.max(np.abs(np.asarray(after_l["local"]) - np.asarray(before_l["local"]))) > 0.1


def test_a_retiring_operator_without_the_lifecycle_door_is_refused(lifecycle_world, monkeypatch):
    """Ruling 1, fail closed: beside the kinds' lifecycle fields, a retiring operator whose event
    map takes no lifecycle= is refused at the structure. Planted: the partition with
    TAKES_LIFECYCLE false."""
    from cells.operators import partition

    spec, model, state, p, k = lifecycle_world
    op = next(o for o in model.operators if o.LAW_ID == partition.LAW_ID)
    assert pump_composite.lifecycle_errors(model.inner, model.operators) == []
    monkeypatch.setattr(type(op), "TAKES_LIFECYCLE", False)
    (error,) = pump_composite.lifecycle_errors(model.inner, model.operators)
    assert error.startswith(f"{partition.LAW_ID} retires slots beside the kinds' fields")


def test_a_per_cell_extensive_kind_field_is_refused_beside_a_dividing_closer(lifecycle_world):
    """Ruling 7 (c): a per-cell extensive kind field waits for a charge rule. Planted: the table
    with one such field."""
    spec, model, state, p, k = lifecycle_world
    table = dict(
        model.kind_lifecycle, planted_cell_fmol=(PartitionRole("extensive"), ("cell_slot",))
    )
    import unittest.mock

    with unittest.mock.patch.object(
        pump_composite, "kind_lifecycle_table", lambda inner, ops: table
    ):
        errors = pump_composite.lifecycle_errors(model.inner, model.operators)
    assert errors == [
        "The kinds' per-cell extensive fields ['planted_cell_fmol'] are refused beside a dividing "
        "closer until a charge rule exists: a division splits them by the volume fraction alone"
    ]


def test_an_extensive_kind_field_on_edge_slots_is_refused_at_the_definition(lifecycle_world):
    """CORE_SEAMS §18 (02:25 UTC, 19 November 2026): the partition binds no contact fraction, so an
    extensive kind field on edge slots is refused at the structure, not first when the event is
    traced (lifecycle_split's own refusal stays, behind it). Planted: the table with one such
    field; an intensive one there is admitted."""
    import unittest.mock

    spec, model, state, p, k = lifecycle_world

    def errors_with(role):
        planted = (PartitionRole(role), ("edge_slot",))
        table = dict(model.kind_lifecycle, planted_contact_fmol=planted)
        with unittest.mock.patch.object(
            pump_composite, "kind_lifecycle_table", lambda inner, ops: table
        ):
            return pump_composite.lifecycle_errors(model.inner, model.operators)

    assert errors_with("extensive") == [
        "The kinds' extensive fields on edge slots ['planted_contact_fmol'] are refused beside a "
        "dividing closer: the partition binds no contact fraction to split them by"
    ]
    assert errors_with("intensive") == []


def test_no_composition_admitted_today_gains_a_lifecycle_field():
    """Q7 (a) refuses a kind with entity fields beside a closer, so every registered composition
    keeps its types: the table is empty beside the partition with a shared-axis kind, and without
    a retiring operator."""
    with kind_registry.scope(kf.registry(shared_carrier())):
        inner = get_model(composite(kf.declare_carrier(world(), species="K")).model).inner
        partition_op = OPERATORS["cells.operator.isopotential_partition@1"]
        assert pump_composite.kind_lifecycle_table(inner, (partition_op,)) == {}
    assert pump_composite.kind_lifecycle_table(pump3, (partition_op,)) == {}


@pytest.mark.parametrize("lifecycle_world", ["extensive"], indirect=True)
def test_an_extensive_kind_field_is_split_and_its_move_booked(lifecycle_world):
    """Ruling 5: the carrier's transfers declared extensive. The daughters' patches take the
    anchor rule's shares and the parent's goes to 0; the composite's moved accumulator books the
    split, so the adjusted row is the pre-event one and the ledgers equal the pre-event ones."""
    import numpy as np

    from cells.operators import partition

    spec, model, state, p, k = lifecycle_world
    assert model.KIND_MOVED == {"carrier_transferred": "carrier_transferred_moved"}
    after, ok = retire(model, state, p)
    assert bool(ok)
    parent, kids, fraction, _ = partition.division_maps(np.ones(1, dtype=bool), p)["membrane_slot"]
    row = int(np.flatnonzero(np.asarray(parent) == k)[0])
    x = np.asarray(state.carrier_transferred)[:, k]
    one = np.asarray(after.carrier_transferred)[:, kids[row, 0]]
    two = np.asarray(after.carrier_transferred)[:, kids[row, 1]]
    assert (one + two == x).all() and (np.asarray(after.carrier_transferred)[:, k] == 0).all()
    adjusted = model._adjusted(after, p, xp=np)
    assert (np.asarray(adjusted.carrier_transferred) == np.asarray(state.carrier_transferred)).all()
    before_l, after_l = model.balances(state, p), model.balances(after, p)
    np.testing.assert_allclose(after_l["local"], before_l["local"], rtol=1e-9, atol=1e-15)


# ------------------------------------------------------------------ the declared fields by role (C)
# Step C (the lead's ruling 2 of 19 November 2026): a kind's layout and control fields on the
# divided slot axes are checked by role at the definition, in the partition's check_definition
# (partition.check_kind_roles), since a kind's layout values exist only at binding. The planted
# kind declares its values slot by slot on the asymmetric division world (f 0.75, the patch's
# fraction 0.6, so a population's split shows that it takes its patch's fraction), beside the
# partition under the accepted bypass. One plant per role, each refused with its field named.

PLANTED_ID = "tests.kind.planted_population@1"
PLANTED_KEY = "test_planted_population"
PLANTED_FIELDS = {  # field: (layout or control, entity axis, role)
    "planted_capacity_fmol_s": ("layout", "membrane_slot", PartitionRole("extensive")),
    "planted_km_mM": ("layout", "membrane_slot", PartitionRole("intensive")),
    "planted_law": ("layout", "membrane_slot", PartitionRole("structural", 0)),
    "planted_units": ("layout", "channel_slot", PartitionRole("extensive")),
    "planted_availability": ("control", "membrane_slot", PartitionRole("intensive")),
}
SLOT_LISTS = dict(  # Each slot axis: its capacity in the execution block, its entity list.
    cell_slot=("capacity", "cells"),
    membrane_slot=("membrane_capacity", "membranes"),
    channel_slot=("channel_capacity", "channels"),
    edge_slot=("edge_capacity", "junctions"),
)


def _freeze(value):
    return tuple(_freeze(v) for v in value) if isinstance(value, (list, tuple)) else float(value)


def _thaw(value):
    return [_thaw(v) for v in value] if isinstance(value, tuple) else value


def _planted_slots(spec, axis):
    """(capacity, slot ids) of one of @3's slot axes; a kind's own axis has none in the world (its
    field takes its length from `bound_on`)."""
    if axis not in SLOT_LISTS:
        return None, []
    capacity, entities = SLOT_LISTS[axis]
    return getattr(spec.execution, capacity), [e.id for e in getattr(spec.model, entities)]


def planted_population(fields=PLANTED_FIELDS, *, bound_on=None, presence=None):
    """The planted per-slot kind: `fields` {field: (layout or control, entity axis, role)}, with
    their roles and axes declared, every value given slot by slot in its model block ({field: {slot:
    value}}, a control's value a schedule [[time, value], ...]). `bound_on` {field: axis or a
    length} binds a field along another axis than it declares, or with that many entries (a planted
    shape; 0, no entities; an own axis's length). `presence`: F's declaration, {entity axis:
    (field, ...)}. A structural field with fill False is a bool mask. No state, rates or moves."""
    bound_on = bound_on or {}
    layout = tuple(k for k, (what, _, _) in fields.items() if what == "layout")
    control = tuple(k for k, (what, _, _) in fields.items() if what == "control")

    def initial(spec, declaration, entries):
        values, out = dict(declaration), {}
        for name in layout:
            _, ids = _planted_slots(spec, fields[name][1])  # The declared axis's slots ...
            bound = bound_on.get(name, fields[name][1])  # ... bound along this axis, or length.
            size = bound if isinstance(bound, int) else _planted_slots(spec, bound)[0]
            role = fields[name][2]
            mask = role.role == "structural" and role.fill is False
            dtype = bool if mask else np.int64 if role.role == "structural" else float
            out[name] = np.zeros(size, dtype=dtype)
            for slot, value in values.get(name, ()) if size else ():
                out[name][ids.index(slot)] = value
        return {}, out

    def control_values(spec, declaration, times):
        values, out = dict(declaration), {}
        for name in control:
            _, ids = _planted_slots(spec, fields[name][1])  # As initial's layout: `bound_on`.
            bound = bound_on.get(name, fields[name][1])
            size = bound if isinstance(bound, int) else _planted_slots(spec, bound)[0]
            out[name] = np.zeros((len(times), size))
            for slot, schedule in values.get(name, ()) if size else ():
                for start, value in schedule:  # Piecewise constant, each point from its time on.
                    out[name][np.asarray(times) >= start, ids.index(slot)] = value
        return out

    return Kind(
        kind_id=PLANTED_ID,
        model_key=PLANTED_KEY,
        layout_fields=layout,
        control_fields=control,
        parse=lambda entries, base: tuple(
            (name, tuple((slot, _freeze(v)) for slot, v in sorted(values.items())))
            for name, values in sorted(entries.items())
        ),
        to_dict=lambda declaration: {
            name: {slot: _thaw(v) for slot, v in values} for name, values in declaration
        },
        structure_entry=lambda declaration: (),
        initial=initial,
        control_values=control_values,
        partition_roles=MappingProxyType({k: role for k, (_, _, role) in fields.items()}),
        field_axes=MappingProxyType({k: (axis,) for k, (_, axis, _) in fields.items()}),
        presence=MappingProxyType({a: tuple(names) for a, names in (presence or {}).items()}),
        # A field bound with no entries is empty by static dispatch, as the transporter's mask of
        # a law its declaration leaves out (F's dispatch_masks, D228 item 6).
        dispatch_masks=tuple(name for name, bound in bound_on.items() if bound == 0),
    )


CAPACITY, KM, UNITS = 0.3, 0.2, 6.0  # The parent's planted values.


def planted_world(**changes):
    """(raw, its division block): the asymmetric division world with the planted kind's values
    following every role: the capacity and each population's units split by the patch's fraction
    (the anchor rule), the Michaelis constant and the availability (a control, held 1 from t = 0)
    equal, and the law as declared, different at each daughter. changes: {field: {slot: value}}."""
    raw = pfx.divided(f=0.75, area_fraction=0.6, carriers={"Na": 0.5, "K": 0.5})
    block = next(o for o in raw["model"]["operators"] if o["law"] == partition.LAW_ID)
    (division,) = block["divisions"]
    (patch,) = division["patches"]
    a, (one, two) = patch["fraction"], patch["daughters"]
    slots = (patch["parent"], one, two)
    values = dict(
        planted_capacity_fmol_s=dict(
            zip(slots, (CAPACITY, *partition.split(CAPACITY, a)), strict=True)
        ),
        planted_km_mM=dict.fromkeys(slots, KM),
        planted_law=dict(zip(slots, (2, 3, 4), strict=True)),
        planted_availability={slot: [[0.0, 1.0]] for slot in slots},
        planted_units={},
    )
    for population in division["populations"]:
        rows = (population["parent"], *population["daughters"])
        values["planted_units"].update(zip(rows, (UNITS, *partition.split(UNITS, a)), strict=True))
    for name, update in changes.items():
        values[name] = {**values.get(name, {}), **update}
    raw["model"][PLANTED_KEY] = values
    return raw, division


@pytest.fixture
def planted(monkeypatch):
    """parse(raw, fields=PLANTED_FIELDS, bound_on=None) -> spec, under the accepted bypass (Q7 (a)
    refuses a per-entity kind beside a closer at the structure) and a registry with the planted
    kind; and the registry's scope, for binding the parsed spec."""
    monkeypatch.setattr(
        pump_composite, "_kinds_lifecycle", lambda inner, kinds: dict.fromkeys(kinds, ())
    )

    def parse(raw, fields=PLANTED_FIELDS, bound_on=None):
        with kind_registry.scope(kf.registry(planted_population(fields, bound_on=bound_on))):
            return parse_spec(raw)

    return parse


def roles_of(**changes):
    """PLANTED_FIELDS with the named fields' roles changed ({field: PartitionRole})."""
    return {
        k: (what, axis, changes.get(k, role)) for k, (what, axis, role) in PLANTED_FIELDS.items()
    }


def test_declared_fields_that_follow_their_roles_are_admitted(planted):
    """The admitted world, not vacuously: the check compares the four non-structural fields, which
    the bound layout and controls hold at the daughters as planted (the anchor rule's shares by the
    patch's fraction 0.6, not by f 0.75), and the structural law differs at each daughter."""
    raw, division = planted_world()
    spec = planted(raw)
    with kind_registry.scope(kf.registry(planted_population())):
        model = get_model(spec.model)
        checked = partition.kind_role_fields(model)
        _, p = model.initial_values(spec)
    fields = {(name, role.role, axis, what) for _, name, role, axis, what in checked}
    assert fields == {
        (name, role.role, axis, what) for name, (what, axis, role) in PLANTED_FIELDS.items()
    }
    ids = [m.id for m in spec.model.membranes]
    (patch,) = division["patches"]
    held = [p.planted_capacity_fmol_s[ids.index(s)] for s in (patch["parent"], *patch["daughters"])]
    assert held[1:] == list(partition.split(CAPACITY, 0.6)) and held[1] + held[2] == CAPACITY
    assert held[1] != 0.75 * CAPACITY
    assert sorted(p.planted_law[: len(ids)]) == [2, 3, 4]


def test_an_extensive_field_off_the_anchor_rule_by_one_ulp_is_refused(planted):
    raw, division = planted_world()
    (patch,) = division["patches"]
    one = raw["model"][PLANTED_KEY]["planted_capacity_fmol_s"][patch["daughters"][0]]
    raw["model"][PLANTED_KEY]["planted_capacity_fmol_s"][patch["daughters"][0]] = np.nextafter(
        one, np.inf
    )
    with pytest.raises(ConfigError, match="planted_capacity_fmol_s is extensive, so its values at"):
        planted(raw)


def test_a_population_takes_its_patchs_fraction(planted):
    """Planted: a population's units split by the volume fraction f 0.75, not by its patch's 0.6."""
    raw, division = planted_world()
    population = division["populations"][0]
    shares = dict(zip(population["daughters"], partition.split(UNITS, 0.75), strict=True))
    raw["model"][PLANTED_KEY]["planted_units"].update(shares)
    with pytest.raises(ConfigError, match="planted_units is extensive"):
        planted(raw)


def test_an_intensive_field_that_differs_at_a_daughter_is_refused(planted):
    raw, division = planted_world()
    (patch,) = division["patches"]
    raw["model"][PLANTED_KEY]["planted_km_mM"][patch["daughters"][1]] = 0.25
    with pytest.raises(ConfigError, match="planted_km_mM is intensive, so its values at"):
        planted(raw)


def test_a_structural_field_is_as_declared_until_it_is_declared_intensive(planted):
    """Structural: as declared (law, host, orientation), as the run-time split keeps it, so the
    admitted world's laws differ at each daughter. Planted: the same definition with the law
    declared intensive is refused."""
    raw, _ = planted_world()
    planted(raw)  # Admitted: 2 at the parent, 3 and 4 at the daughters.
    with pytest.raises(ConfigError, match="planted_law is intensive"):
        planted(raw, roles_of(planted_law=PartitionRole("intensive")))


def test_a_layout_field_declared_history_is_refused(planted):
    """Planted: a layout field declared history; it accumulates nothing for a record to keep."""
    raw, _ = planted_world()
    with pytest.raises(ConfigError, match="planted_km_mM on membrane_slot, declared history"):
        planted(raw, roles_of(planted_km_mM=PartitionRole("history")))


def test_a_control_is_checked_at_every_change_record(planted):
    """Planted: a daughter's availability, equal at t = 0, drops at a later change record. A kind's
    controls are evaluated at the inner model's change records and held between them, so the test
    adds one at t = 1 ms, a neutral point of a patch's own schedule (the same availability)."""
    raw, division = planted_world()
    (patch,) = division["patches"]
    later = pfx.DT
    control = next(
        c for c in raw["experiment"]["membrane_controls"] if c["membrane_id"] == "membrane_0"
    )
    control["schedule"].append(
        dict(time=later, availability=control["schedule"][-1]["availability"])
    )
    planted(raw)  # Admitted: the record changes nothing.
    raw["model"][PLANTED_KEY]["planted_availability"][patch["daughters"][0]] = [
        [0.0, 1.0],
        [later, 0.5],
    ]
    with pytest.raises(ConfigError, match=f"planted_availability is intensive.*at t = {later!r}"):
        planted(raw)


def test_extensive_fields_per_cell_or_per_contact_are_refused(planted):
    """Planted: an extensive layout field per cell (ruling 7 (c): until a charge rule exists) and
    one per contact (the partition binds no contact fraction), each refused before any binding."""
    raw, division = planted_world()
    for axis, words in (
        ("cell_slot", "a per-cell extensive kind field is refused"),
        ("edge_slot", "binds no contact fraction"),
    ):
        fields = dict(PLANTED_FIELDS, planted_extent=("layout", axis, PartitionRole("extensive")))
        refused = f"planted_extent on {axis}, declared extensive.*{words}"
        with pytest.raises(ConfigError, match=refused):
            planted(raw, fields)


@pytest.mark.parametrize("axis", ["cell_slot", "edge_slot"])
def test_an_intensive_field_per_cell_or_per_contact_follows_its_map(planted, axis):
    """The cell and contact maps' rows and their divisions, on the neighbour world (the parent's
    contact mapped to both daughters): an intensive field per cell or per contact is admitted equal
    at the daughters and refused, naming the division and the slots, when one differs."""
    raw = pfx.divided(neighbour=True)
    block = next(o for o in raw["model"]["operators"] if o["law"] == partition.LAW_ID)
    (division,) = block["divisions"]
    if axis == "cell_slot":
        parent, kids = division["parent"], division["daughters"]
    else:
        (contact,) = division["contacts"]
        parent, kids = contact["parent"], contact["daughters"]
    fields = {"planted_entity_km_mM": ("layout", axis, PartitionRole("intensive"))}
    raw["model"][PLANTED_KEY] = {"planted_entity_km_mM": dict.fromkeys((parent, *kids), KM)}
    planted(raw, fields)
    raw["model"][PLANTED_KEY]["planted_entity_km_mM"][kids[1]] = 0.25
    refused = (
        f"Division {division['id']}: .* planted_entity_km_mM is intensive, so its values at "
        f"{kids[0]} and {kids[1]} must be its value at {parent}"
    )
    with pytest.raises(ConfigError, match=refused):
        planted(raw, fields)


def test_a_field_bound_along_another_axis_than_it_declares_is_refused(planted):
    """Planted: the Michaelis constant declared per patch but bound per population (6 slots, not
    the patches' 3); read along the patches' maps it would be compared at the wrong slots. F's
    array-axes check refuses it where @3 binds the kind's initial values (D228 item 6), before
    step C's own refusal (partition.check_kind_roles). F's check binds state and layout only, so
    the availability, a control, bound per population reaches step C's refusal (planted)."""
    raw, _ = planted_world()
    with pytest.raises(
        ValueError, match=r"planted_km_mM's axis membrane_slot has length 6, not the host's 3"
    ):
        planted(raw, bound_on={"planted_km_mM": "channel_slot"})
    with pytest.raises(ConfigError, match=r"planted_availability binds shape \(\d+, 6\), whose"):
        planted(raw, bound_on={"planted_availability": "channel_slot"})


def test_nothing_is_bound_without_a_field_to_compare(planted, monkeypatch):
    """A kind on shared axes only (admitted beside closers today) gives no field, and a structural
    field alone is compared with nothing, so neither binds the definition again."""
    with kind_registry.scope(kf.registry(shared_carrier())):
        inner = get_model(composite(kf.declare_carrier(world(), species="K")).model).inner
        assert partition.kind_role_fields(type("Model", (), {"inner": inner})) == ()
    raw, _ = planted_world()
    for name in list(raw["model"][PLANTED_KEY]):
        if name != "planted_law":
            del raw["model"][PLANTED_KEY][name]
    law = {"planted_law": PLANTED_FIELDS["planted_law"]}
    spec = planted(raw, law)
    with kind_registry.scope(kf.registry(planted_population(law))):
        model = get_model(spec.model)
        assert [f[1] for f in partition.kind_role_fields(model)] == ["planted_law"]
        monkeypatch.setattr(type(model), "initial_values", lambda *a, **k: pytest.fail("bound"))
        op, declaration, schedule = next(
            e for e in composite_spec.entries(spec) if e[0].LAW_ID == partition.LAW_ID
        )
        partition.check_kind_roles(spec, declaration, model)


# ------------------------------------------------------------------ step C with the lift (item 3)
# The lead's rulings of 19 November 2026: presence is equal at the daughters (ruling 1 (c)), and a
# law's mask that a declaration leaves out, bound [0], holds no entities.

PRESENT = ("layout", "membrane_slot", PartitionRole("structural", False))  # A bool mask.
ON_PATCHES = {k: v for k, v in PLANTED_FIELDS.items() if v[1] == "membrane_slot"}


def test_presence_is_equal_at_the_daughters():
    """The planted kind on patches only, its presence declared there, is admitted beside the
    partition with no bypass (the lift), present at the parent patch and at both daughters: a
    population divides with its host. Planted: a parent-present population whose daughter patch is
    declared absent is refused."""
    raw, division = planted_world()
    (patch,) = division["patches"]
    raw["model"][PLANTED_KEY].pop("planted_units")
    slots = (patch["parent"], *patch["daughters"])
    raw["model"][PLANTED_KEY]["planted_present"] = dict.fromkeys(slots, True)
    fields = dict(ON_PATCHES, planted_present=PRESENT)
    kind = planted_population(fields, presence={"membrane_slot": ("planted_present",)})
    with kind_registry.scope(kf.registry(kind)):
        assert kind_registry.declaration_errors(kind) == []
        spec = parse_spec(raw)  # Admitted, no bypass.
        model = get_model(spec.model)
        # The core's presence gate acts here: the bound structure declares the closer.
        assert model.inner.implementation.structure.padding_fill
        checked = {f[1] for f in partition.kind_role_fields(model)}
        assert "planted_present" in checked
        raw["model"][PLANTED_KEY]["planted_present"][patch["daughters"][1]] = False
        with pytest.raises(ConfigError, match="planted_present is a presence field, so its values"):
            parse_spec(raw)


def test_an_entity_axis_the_presence_gate_cannot_host_is_refused():
    """The core's presence gate closes the entities of @3's slot axes, channel populations and
    faces included (surface_pump_v3.PRESENCE_SLOT_AXES, one list with the lifecycle's), and of an
    own axis through its declared host. So the planted kind with presence on patches and channel
    populations is admitted beside the partition with no bypass, and the gate closes its
    populations (it met their channel_slot as a KeyError before the @3 owner's batch). Planted: an
    own axis with presence and no axis_hosts could not be closed, so it is refused beside a closer,
    fail-closed."""
    assert pump3.GATED_SLOT_AXES is surface_pump_v3.PRESENCE_SLOT_AXES
    raw, division = planted_world()
    rows = [x for p in division["populations"] for x in (p["parent"], *p["daughters"])]
    (patch,) = division["patches"]
    raw["model"][PLANTED_KEY]["planted_present"] = dict.fromkeys(
        (patch["parent"], *patch["daughters"]), True
    )
    raw["model"][PLANTED_KEY]["planted_population_present"] = dict.fromkeys(rows, True)
    fields = dict(
        PLANTED_FIELDS,
        planted_present=PRESENT,
        planted_population_present=("layout", "channel_slot", PartitionRole("structural", False)),
    )
    presence = {
        "membrane_slot": ("planted_present",),
        "channel_slot": ("planted_population_present",),
    }
    kind = planted_population(fields, presence=presence)
    assert kind_registry.declaration_errors(kind) == []
    assert pump3.kind_lifecycle_errors(kind) == ()
    with kind_registry.scope(kf.registry(kind)):
        spec = parse_spec(raw)  # Admitted, no bypass.
        model = get_model(spec.model)
        _, p = model.initial_values(spec)
        layout = model.inner.inner_layout(p)
        gated = surface_pump_v3.presence_gated(layout, model.inner.implementation.structure, xp=np)
        hosts = surface_pump_v3.entity_activity(kind, "channel_slot", layout, xp=np)
        np.testing.assert_array_equal(
            gated.planted_population_present, layout.planted_population_present & hosts
        )
    own = ("layout", "planted_site", PartitionRole("structural", False))
    unhosted = planted_population(
        dict(fields, planted_site_present=own),
        bound_on={"planted_site_present": 2},
        presence=dict(presence, planted_site=("planted_site_present",)),
    )
    assert kind_registry.declaration_errors(unhosted) == []
    assert pump3.kind_lifecycle_errors(unhosted) == ("hosts", ("planted_site",))
    with kind_registry.scope(kf.registry(unhosted)):
        with pytest.raises(ConfigError, match=r"entity axes \(planted_site\) have no host"):
            parse_spec(raw)


def test_a_mask_bound_with_no_entities_is_not_compared(planted):
    """A field bound [0], as the transporter binds the mask of a law its declaration leaves out,
    holds no entities, so step C compares nothing there; any other length stays refused
    (test_a_field_bound_along_another_axis_than_it_declares_is_refused)."""
    raw, _ = planted_world()
    planted(raw, bound_on={"planted_km_mM": 0})  # Admitted: no entities to compare.
