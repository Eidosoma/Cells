"""The kind contract's seam declarations and seam D's static switch (docs/CORE_SEAMS_DESIGN.md
§4.2, §6.1, §7.3; CORE_SEAMS §18's hand-offs to the @3 owner; seam F). On the host, each claim
with a planted error it must catch (D187):

- a kind's energy roles, admitted heat bookings, partition roles and ledgers are checked at
  registration (planted, each refused: an unknown role, a non-bool monotone, a heat-suffixed field
  declared work, a stray field, the tableau's unversioned ID, a repeated booking, a structural role
  without a fill, an intensive one with a fill, a non-finite fill, ledgers without their bounds);
  today's built-in kinds declare none and register as before;
- an undeclared state field takes today's suffix rule, a declaration overrides it (planted: a
  heat field declared non-monotone reads non-monotone; an unsuffixed field books no energy);
- a kind's missing partition roles are its state, layout and control fields with none, on a bound
  kind too (planted: one field left out is named);
- a kind's own ledgers are checked when read (planted: a ledger named for a ledger_terms role, a
  repeated name, a malformed result);
- InnerStructure.heat_bookings defaults to (), so today's structures are unchanged, and admits a
  sorted pair per mover class whose class admits it (planted, each refused: unsorted pairs, a
  repeated class, the tableau listed, channels, membranes, pumps or calcium pumps on the exact
  booking, junctions against junction_heat_booking, an undeclared kind, a kind that does not admit
  the booking, a malformed pair);
- a kind's field axes and its own axes' hosts are checked at registration (CORE_SEAMS §18, B1's
  lift; planted, each refused: an axis on a state field, a malformed axis tuple, a host of an
  unknown kind, a host on @3's own slot axis, an axis no field is on, a host index that is not a
  layout field, and one on another axis);
- a kind's internal axes (its laws' modes, rows, bands, edges: copied whole at a split, never
  hosted; the kinds owner's Q5) are checked at registration (planted, each refused: one also
  hosted, one no field is on, @3's slot axis, a repeated name);
- an entry's `without` removes those hooks from the kind bound to it, so a hook a later layout
  adds never reaches an earlier entry (the kinds owner's design statement 1 §6; planted: a name
  that is no hook, refused at binding);
- a kind's standard free energies are () by default and checked to the operators' form when read
  (planted, each refused: a bare species, a zero coefficient, a repeated species, a non-finite
  energy, a non-positive c0, a list).
"""

import math
from dataclasses import replace
from types import MappingProxyType

import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import parse_spec
from cells.models import inner_laws, surface_pump_v3
from cells.registry import kind_registry
from cells.registry.kind_registry import AxisHost, EnergyRole, Kind, KindFields, PartitionRole
from validation.tissue import pump_water_fixtures as water_fixtures

TRAPEZOID, EXACT = spec3.TRAPEZOID_JUNCTION_HEAT, "exact_free_energy_heat@1"
PLANTED_ID = "tests.booked_routes@1"


def planted(**declarations):
    """A planted kind with one state field of each energy suffix, one other, a layout field and a
    control, and the given seam declarations."""
    return Kind(
        kind_id=PLANTED_ID,
        model_key="booked_routes",
        state_axes=(
            ("booked_dissipated_energy_pJ", ("cell_slot",)),
            ("booked_work_pJ", ("cell_slot",)),
            ("booked_moved_fmol", ("cell_slot",)),
        ),
        layout_fields=("booked_host",),
        control_fields=("booked_availability",),
        **declarations,
    )


ROLES = MappingProxyType(
    {
        "booked_dissipated_energy_pJ": PartitionRole("history"),
        "booked_work_pJ": PartitionRole("history"),
        "booked_moved_fmol": PartitionRole("extensive"),
        "booked_host": PartitionRole("structural", 0),
        "booked_availability": PartitionRole("intensive"),
    }
)


def test_seam_declarations_are_checked_at_registration():
    good = planted(
        energy_roles={"booked_dissipated_energy_pJ": EnergyRole("heat", False)},
        heat_bookings=(EXACT,),
        partition_roles=ROLES,
        ledgers=lambda declaration: (("booked_moiety", "booked_moiety_residual"),),
        ledger_bounds=lambda row, p, tol, steps, *, xp: (tol,),
    )
    assert kind_registry.declaration_errors(good) == []
    assert kind_registry.KindRegistry().register(good) is good
    plants = {
        "unknown role": dict(energy_roles={"booked_moved_fmol": EnergyRole("light", True)}),
        "non-bool monotone": dict(energy_roles={"booked_moved_fmol": EnergyRole("stored", 1)}),
        "suffix contradicted": dict(energy_roles={"booked_work_pJ": EnergyRole("heat", True)}),
        "stray energy field": dict(energy_roles={"other_field": EnergyRole("stored", False)}),
        "tableau listed": dict(heat_bookings=(spec3.DEFAULT_JUNCTION_HEAT,)),
        "repeated booking": dict(heat_bookings=(EXACT, EXACT)),
        "structural without a fill": dict(
            partition_roles=dict(ROLES, booked_host=PartitionRole("structural"))
        ),
        "intensive with a fill": dict(
            partition_roles=dict(ROLES, booked_availability=PartitionRole("intensive", 1.0))
        ),
        "non-finite fill": dict(
            partition_roles=dict(ROLES, booked_host=PartitionRole("structural", math.nan))
        ),
        "stray partition field": dict(partition_roles=dict(ROLES, other=PartitionRole("history"))),
        "ledgers without bounds": dict(ledgers=lambda declaration: ()),
    }
    for name, declarations in plants.items():
        kind = planted(**declarations)
        assert kind_registry.declaration_errors(kind), name
        with pytest.raises(ValueError, match=PLANTED_ID):
            kind_registry.KindRegistry().register(kind)
    # Today's built-in kinds declare none, and register on BUILTIN as before.
    for kind in kind_registry.active().model_keys().values():
        assert kind_registry.declaration_errors(kind) == [], kind.kind_id
        assert kind.energy_roles == {} and kind.heat_bookings == () and kind.ledgers is None


def test_an_undeclared_field_takes_the_suffix_rule_and_a_declaration_overrides_it():
    kind = planted(energy_roles={"booked_dissipated_energy_pJ": EnergyRole("heat", False)})
    role = kind_registry.energy_role
    assert role(kind, "booked_dissipated_energy_pJ") == EnergyRole("heat", False)  # Declared.
    plain = planted()
    assert role(plain, "booked_dissipated_energy_pJ") == EnergyRole("heat", True)  # The rule.
    assert role(plain, "booked_work_pJ") == EnergyRole("work", False)
    assert role(plain, "booked_moved_fmol") is None
    stored = planted(energy_roles={"booked_moved_fmol": EnergyRole("stored", False)})
    assert role(stored, "booked_moved_fmol") == EnergyRole("stored", False)


def test_missing_partition_roles_name_each_field_left_undeclared():
    assert kind_registry.missing_partition_roles(planted(partition_roles=ROLES)) == ()
    fields = kind_registry.partition_fields(planted())
    assert kind_registry.missing_partition_roles(planted()) == fields
    partial = {k: v for k, v in ROLES.items() if k != "booked_host"}
    assert kind_registry.missing_partition_roles(planted(partition_roles=partial)) == (
        "booked_host",
    )
    # A kind whose fields follow its entry is read bound: the entry's fields alone.
    per_entry = replace(
        planted(partition_roles=partial),
        declared_fields=lambda entry: kind_registry.KindFields(
            (("booked_moved_fmol", ("cell_slot",)),), (), (), ()
        ),
    )
    assert kind_registry.declaration_errors(per_entry) == []
    assert kind_registry.missing_partition_roles(kind_registry.bound(per_entry, ())) == ()


def test_a_kind_s_own_ledgers_are_checked_when_read():
    def kind(result):
        return planted(ledgers=lambda declaration: result, ledger_bounds=lambda *a, **k: ())

    assert kind_registry.kind_ledgers(planted(), ()) == ()
    pairs = (("booked_moiety", "booked_moiety_residual"),)
    assert kind_registry.kind_ledgers(kind(pairs), ()) == pairs
    for result, match in (
        ((("produced", "produced_residual"),), "ledger_terms' roles"),
        ((("booked_moiety", "booked_moiety"),), "distinct names"),
        ((("booked_moiety",),), "returns"),
        ([("booked_moiety", "booked_moiety_residual")], "returns"),
    ):
        with pytest.raises(ValueError, match=match):
            kind_registry.kind_ledgers(kind(result), ())


BASE = dict(
    declared_channel_laws=(),
    junction_laws=(),
    pump_laws=(),
    fuel_kinds=(),
    junction_heat_booking=spec3.DEFAULT_JUNCTION_HEAT,
)


def test_heat_bookings_default_to_none_listed_and_admit_each_class_s_own():
    today = inner_laws.InnerStructure(**BASE)
    assert today.heat_bookings == () and today == inner_laws.InnerStructure(
        **BASE, heat_bookings=()
    )
    world = parse_spec(water_fixtures.heredity_cell("D", end_time=0.01))
    assert surface_pump_v3.structure(world.model).heat_bookings == ()  # Today's worlds.
    channels = ((inner_laws.CHANNELS, TRAPEZOID),)
    assert inner_laws.InnerStructure(**BASE, heat_bookings=channels).heat_bookings == channels
    trapezoid = dict(BASE, junction_heat_booking=TRAPEZOID)
    both = ((inner_laws.CHANNELS, TRAPEZOID), (inner_laws.JUNCTIONS, TRAPEZOID))
    assert inner_laws.InnerStructure(**trapezoid, heat_bookings=both).heat_bookings == both
    # Each of @3's own classes admits the trapezoid, whose power is never negative (the lead).
    own = tuple(sorted((mover, TRAPEZOID) for mover in inner_laws.OWN_HEAT_BOOKINGS))
    assert {mover for mover, _ in own} == {
        "calcium_pumps",
        "channels",
        "junctions",
        "membranes",
        "pumps",
    }
    assert inner_laws.InnerStructure(**trapezoid, heat_bookings=own).heat_bookings == own
    registry = kind_registry.KindRegistry()
    registry.register(planted(heat_bookings=(EXACT,)))
    kinds = ((PLANTED_ID, ()),)
    with kind_registry.scope(registry):
        booked = ((inner_laws.CHANNELS, TRAPEZOID), (PLANTED_ID, EXACT))  # Sorted by class.
        assert inner_laws.InnerStructure(**BASE, kinds=kinds, heat_bookings=booked)
        plants = {  # Each with the words of its own refusal.
            "sorted, one pair": booked[::-1],
            "one pair per mover class": (
                (inner_laws.CHANNELS, TRAPEZOID),
                (inner_laws.CHANNELS, TRAPEZOID),
            ),
            "never listed": ((inner_laws.CHANNELS, spec3.DEFAULT_JUNCTION_HEAT),),
            "channels admit": ((inner_laws.CHANNELS, EXACT),),
            "membranes admit": ((inner_laws.MEMBRANES, EXACT),),
            "pumps admit": ((inner_laws.PUMPS, EXACT),),
            "calcium_pumps admit": ((inner_laws.CALCIUM_PUMPS, EXACT),),
            "junctions book": ((inner_laws.JUNCTIONS, TRAPEZOID),),
            "nor a declared kind": (("tests.undeclared@1", EXACT),),
            "admits no heat booking": ((PLANTED_ID, TRAPEZOID),),
            "pairs of names": ((inner_laws.CHANNELS,),),
        }
        for words, bookings in plants.items():
            with pytest.raises(ValueError, match="Heat bookings"):
                inner_laws.InnerStructure(**BASE, kinds=kinds, heat_bookings=bookings)
            errors = inner_laws.heat_booking_errors(bookings, (PLANTED_ID,))
            assert any(words in error for error in errors), (words, errors)


def test_field_axes_and_own_axes_hosts_are_checked_at_registration():
    # A kind on its own axis "booked_route", each route hosted on a patch through booked_host.
    on_routes = replace(
        planted(),
        state_axes=(("booked_dissipated_energy_pJ", ("booked_route",)),),
    )
    good = replace(
        on_routes,
        field_axes={"booked_host": ("booked_route",), "booked_availability": ()},  # () a scalar.
        axis_hosts={"booked_route": AxisHost("patch", "booked_host")},
    )
    assert kind_registry.declaration_errors(good) == []
    assert kind_registry.KindRegistry().register(good) is good
    assert kind_registry.AXIS_HOST_KINDS["patch"] == "membrane_slot"
    plants = {
        "not its layout or control fields": dict(field_axes={"booked_work_pJ": ("cell_slot",)}),
        "tuples of distinct axis names": dict(field_axes={"booked_host": ("a", "a")}),
        "its host kind is one of": dict(
            axis_hosts={"booked_route": AxisHost("planet", "booked_host")}
        ),
        "@3's own slot axis": dict(axis_hosts={"cell_slot": AxisHost("cell", "booked_host")}),
        "no field of the kind's is on it": dict(
            axis_hosts={"other_axis": AxisHost("cell", "booked_host")}
        ),
        "is not one of its layout fields": dict(
            axis_hosts={"booked_route": AxisHost("patch", "booked_availability")}
        ),
        "is on": dict(field_axes={**good.field_axes, "booked_host": ("cell_slot",)}),
        "AxisHost(kind, index)": dict(axis_hosts={"booked_route": ("patch", "booked_host")}),
    }
    for words, changes in plants.items():
        kind = replace(good, **changes)
        errors = kind_registry.declaration_errors(kind)
        assert any(words in e for e in errors), (words, errors)
        with pytest.raises(ValueError, match=PLANTED_ID):
            kind_registry.KindRegistry().register(kind)


def test_an_entry_s_without_removes_those_hooks_from_its_bound_kind():
    def rates(*args, **kwargs):
        raise AssertionError("a planted hook is never called here")

    fields = planted()
    entries = {
        "general": KindFields(fields.state_axes, fields.layout_fields, fields.control_fields, ()),
        "version 1": KindFields(
            fields.state_axes, fields.layout_fields, fields.control_fields, (), ("material_term",)
        ),
    }
    kind = replace(fields, material_term=rates, view_sets=rates, declared_fields=entries.get)
    assert kind_registry.bound(kind, "general").material_term is rates
    one = kind_registry.bound(kind, "version 1")
    assert one.material_term is None and one.view_sets is rates and one.declared_fields is None
    assert set(kind_registry.HOOKS) >= {"material_term", "view_sets", "rates", "book"}
    assert "declared_fields" not in kind_registry.HOOKS and "view" not in kind_registry.HOOKS
    # Planted: a name that is no hook.
    stray = replace(
        kind,
        declared_fields=lambda entry: KindFields((), (), (), (), ("state_axes",)),
        kind_id="tests.stray_without@1",
    )
    with pytest.raises(ValueError, match="names its hooks only"):
        kind_registry.bound(stray, "any")


def test_standard_free_energies_are_none_by_default_and_checked_when_read():
    assert kind_registry.kind_standard_free_energies(planted(), ()) == ()
    hydrolysis = ((("ATP", -1), ("ADP", 1), ("Pi", 1)), -12.3, 1000.0)
    kind = planted(standard_free_energies=lambda declaration: (hydrolysis,))
    assert kind_registry.declaration_errors(kind) == []
    assert kind_registry.kind_standard_free_energies(kind, ()) == (hydrolysis,)
    for declared in (  # Each a tuple of entries, one entry broken.
        ((("ATP",), -12.3, 1000.0),),
        (((("ATP", 0), ("ADP", 1)), -12.3, 1000.0),),
        (((("ATP", -1), ("ATP", 1)), -12.3, 1000.0),),
        (((("ATP", -1), ("ADP", 1)), math.inf, 1000.0),),
        (((("ATP", -1), ("ADP", 1)), -12.3, 0.0),),
        [hydrolysis],
    ):
        planted_kind = planted(standard_free_energies=lambda d, declared=declared: declared)
        with pytest.raises(ValueError, match="standard_free_energies returns"):
            kind_registry.kind_standard_free_energies(planted_kind, ())
    with pytest.raises(ValueError, match=PLANTED_ID):
        kind_registry.KindRegistry().register(planted(standard_free_energies="not a hook"))


def test_internal_axes_are_unhosted_and_used_by_a_field():
    # Routes hosted on patches, each with per-mode cycles on the law-internal axis booked_mode.
    kind = replace(
        planted(),
        state_axes=(("booked_dissipated_energy_pJ", ("booked_route", "booked_mode")),),
        field_axes={"booked_host": ("booked_route",), "booked_availability": ()},
        axis_hosts={"booked_route": AxisHost("patch", "booked_host")},
        internal_axes=("booked_mode",),
    )
    assert kind_registry.declaration_errors(kind) == []
    assert kind_registry.KindRegistry().register(kind) is kind
    assert planted().internal_axes == ()  # None today.
    plants = {
        "it is hosted": dict(internal_axes=("booked_mode", "booked_route")),
        "no field of the kind's is on it": dict(internal_axes=("booked_band",)),
        "@3's own slot axis": dict(internal_axes=("membrane_slot",)),
        "a tuple of distinct axis names": dict(internal_axes=("booked_mode", "booked_mode")),
    }
    for words, changes in plants.items():
        planted_kind = replace(kind, **changes)
        errors = kind_registry.declaration_errors(planted_kind)
        assert any(words in e for e in errors), (words, errors)
        with pytest.raises(ValueError, match=PLANTED_ID):
            kind_registry.KindRegistry().register(planted_kind)
