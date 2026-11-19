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


@dataclasses.dataclass(frozen=True, eq=False)  # Hashed by identity, as Kind is.
class AxedKind(kind_registry.Kind):
    """A planted kind with Q1's axes declaration, `field_axes` {layout or control field: axes},
    standing in for the kind contract's until it lands (F's)."""

    field_axes: object = MappingProxyType({})


def roles_for(kind, role="intensive"):
    """Every partition field of `kind` with `role`."""
    return {name: PartitionRole(role) for name in kind_registry.partition_fields(kind)}


def axed(kind, axes, **changes):
    """`kind` as an AxedKind with `axes` for its layout and control fields."""
    values = {f.name: getattr(kind, f.name) for f in dataclasses.fields(kind_registry.Kind)}
    return AxedKind(**{**values, **changes}, field_axes=MappingProxyType(axes))


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
