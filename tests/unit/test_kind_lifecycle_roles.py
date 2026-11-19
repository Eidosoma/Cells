"""The lifecycle by roles: the composite's refusal of kinds beside closers, lifted by role
(docs/CORE_SEAMS_DESIGN.md §4.2; the lead's rulings of 18 November 2026, CORE_SEAMS §18: Q1, Q2,
Q4, Q7 (a)); models/pump_composite_adapter.py's role table.

A kind beside an operator that closes, retires or provides activity masks is admitted only when the
lifecycle acts on every field it holds, checked in order:
1. every partition field declares a role: a kind that declares none keeps today's refusal, word for
   word (test_pump_composite_kinds.py holds the words for every slot changer);
2. every layout and control field declares its axes (Q1, the kind contract's declaration);
3. no field is per-entity, until the core gates every kind entity's rates by its host's activity
   (Q2): a planted per-patch kind with roles and axes stays refused.
A planted kind with roles and axes and no per-entity field is admitted beside every slot changer.
@3's role table is converted once (Q4): structural fields fill with 0, and the pumps' history is
left to the closers' records until composition's M5 Q2.
"""

import dataclasses
from types import MappingProxyType

import pytest

from cells.models import pump_composite
from cells.models import pump_composite_adapter as pump3
from cells.operators import OPERATORS
from cells.registry import kind_registry
from cells.registry.kind_registry import PartitionRole
from cells.registry.models import get_model
from tests import kind_fixtures as kf
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


def shared_carrier():
    """The carrier with every field on shared axes (no entity) and its axes declared: a planted
    kind the lifecycle need not act on."""
    carrier = kf.carrier()
    state = tuple((name, ("species",)) for name, _ in carrier.state_axes)
    flat = dataclasses.replace(carrier, state_axes=state)
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
    assert pump3.kind_lifecycle_errors(on_patches) == (
        "entities",
        ("carrier_transferred", "carrier_work_pJ", "carrier_rate_fmol_s"),
    )
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
def test_a_per_entity_kind_stays_refused_until_the_core_gates_its_rates(law):
    """Planted: roles and axes on a per-patch kind; its rates would keep running on a closed patch
    at the view (Q2), so Q7 (a) refuses it at the structure."""
    kind = axed(
        carrier_with_roles(),
        {"carrier_rate_fmol_s": ("species", "membrane_slot"), "carrier_availability": ()},
    )
    assert errors_beside(kind, law) == [
        f"{law} opens, closes or retires slots, and the kind {kf.CARRIER_ID} holds per-entity "
        "fields (carrier_transferred, carrier_work_pJ, carrier_rate_fmol_s), which keep running on "
        "a closed host until the core gates every kind entity's rates by its host's activity"
    ]


@pytest.mark.parametrize("law", SLOT_CHANGERS)
def test_a_kind_the_lifecycle_need_not_act_on_is_admitted_beside_a_closer(law):
    """The lift: every field has a role and declared axes, and none is per-entity."""
    assert errors_beside(shared_carrier(), law) == []


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
