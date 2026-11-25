"""The kind contract's seam declarations and seam D's static switch (docs/CORE_SEAMS_DESIGN.md
§4.2, §6.1, §7.3; CORE_SEAMS §18's hand-offs to the @3 owner; seam F). On the host, each claim
with a planted error it must catch (D187):

- a kind's energy roles, admitted heat bookings, partition roles and ledgers are checked at
  registration (planted, each refused: an unknown role, a non-bool monotone, a heat-suffixed field
  declared work, a stray field, the tableau's unversioned ID, a repeated booking, a structural role
  without a fill, an intensive one with a fill, a non-finite fill, ledgers without their bounds,
  FR-42's label transfers without label refusals and a label refusal that is not a callable, and a
  factor's feedback hooks alone, not callable, or without its factors); today's built-in kinds
  declare none, but the transporter, which admits the trapezoid booking (K2), and register as
  before;
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
- a kind's presence fields (Q2's presence gate, CORE_SEAMS §18 at 931b6606, widened to a tuple
  on 19 November) are checked at registration: for each entity axis a non-empty tuple of distinct
  bool layout fields, each on exactly that axis, structural with fill False (planted, each
  refused: a field that is not a layout field, a fill of 0, an intensive role, no role, a field on
  another axis too, presence on a shared axis and on an internal one, an entity axis left
  uncovered, an axis no field is on, an empty tuple, a repeated field, a name for a tuple, a
  non-name); a bound kind's presence_fields covers its own entity axes with its own layout fields
  (planted: an entry with an entity axis uncovered, an entry without one of the masks), and the
  shared axes are B1's; two entries with disjoint fields, and one field_axes and presence covering
  both, each bind to their own axis's masks only;
- an entry's `without` removes those hooks from the kind bound to it, so a hook a later layout
  adds never reaches an earlier entry (the kinds owner's design statement 1 §6; planted: a name
  that is no hook, refused at binding);
- a kind's standard free energies are () by default and checked when read: a tuple of
  FreeEnergyEntry, each naming the law and mode that produced it, a law the kind hosts with a
  general form and a mode it has, or neither, and giving dG° in exactly one form, dG°/RT or, as a
  law citing kJ/mol does, dG° in kJ/mol with its temperature basis (D234's option (b)) (planted,
  each refused, naming the entry: a list, a mapping, a bare 3-tuple, refused since every kind
  declares entries, a four-item tuple, a bare species, a zero coefficient, a repeated species, an
  empty stoichiometry, a non-finite energy, a zero, a negative and a missing c0, a law without
  its mode, a mode without its law, a law another kind hosts, an unregistered law, a version-1
  law, a mode the form lacks, both forms, neither, a kJ/mol value without its basis, an unknown
  basis, a non-finite and a bool kJ/mol value, a basis beside dG°/RT, an offset beside dG°/RT,
  a NaN and a bool offset, and a hook that is not a callable, refused at registration); an entry
  with a temperature-free offset in RT units beside its kJ/mol value (a pH 7 value's) reads;
- a kind's role_species is None by default, not refused by its reader, and where set gives one
  EntityBinding per entity: a cycle law the kind hosts, exactly that law's roles bound to species
  IDs (a version-1 law's moves and a general form's "role@end" rows read as their roles), a node
  at every end its rows name (both MOVES_ENDS for a moves-only law) and a finite value for every
  parameter-named count; entities of one law may differ (planted, each refused, naming the
  entity: a list, a plain tuple, a law another kind hosts, an unregistered law, a missing and an
  extra role, a non-string species, an empty role, a form's missing end, a moves-only law's
  missing inside and its missing outside (MOVES_ENDS: its counts land there with the opposite
  sign), a non-string node, a missing count, a string, a bool and an infinite value, and a hook
  that is not a callable, refused at registration);
- a kind's arrays match the axes it declares where the host binds them (D228 item 6): each field
  with one dimension per declared axis, the host's axes at the host's lengths (axis_sizes), its own
  and internal axes at one length, and only a dispatch mask empty along them (planted, each
  refused: dispatch masks that are a list, repeated, not a field, or a scalar; a host field off
  its axes and two disagreeing on one; a field of the wrong rank, a host axis at another length,
  an own axis at two lengths, an empty field that is no mask, a mask at a wrong nonzero length,
  and an internal axis at two lengths).
"""

import math
import re
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import parse_spec
from cells.models import inner_laws, pump_composite_adapter, surface_pump_v3
from cells.registry import kind_registry
from cells.registry import laws as law_registry
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
    # A factor's feedback hooks (G-5): both or neither, beside the factors they belong to.
    factors = dict(factor_sources=lambda d: (), factors=lambda read, p, *, xp: ())
    rows = dict(factor_rows=lambda declaration: ())
    slopes = dict(factor_log_slopes=lambda read, p, *, xp: ())
    assert kind_registry.declaration_errors(planted(**factors, **rows, **slopes)) == []
    plants = {
        "factor rows alone": dict(**factors, **rows),
        "factor slopes alone": dict(**factors, **slopes),
        "feedback hooks without factors": dict(**rows, **slopes),
        "factor rows not a callable": dict(**factors, **slopes, factor_rows=()),
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
        # FR-42's hook (D303 item 6): transfers only beside the refusals that bound them.
        "label transfers without refusals": dict(label_transfers=lambda *a, **k: ()),
        "label refusals not a callable": dict(label_refusals=[]),
    }
    for name, declarations in plants.items():
        kind = planted(**declarations)
        assert kind_registry.declaration_errors(kind), name
        with pytest.raises(ValueError, match=PLANTED_ID):
            kind_registry.KindRegistry().register(kind)
    # Today's built-in kinds declare none, but the transporter, which admits the trapezoid booking
    # (K2), and register on BUILTIN as before.
    bookings = {"cells.transporter@1": ("trapezoid_nonnegative@1",)}  # K2, D234's Option 2.
    for kind in kind_registry.active().model_keys().values():
        assert kind_registry.declaration_errors(kind) == [], kind.kind_id
        assert kind.heat_bookings == bookings.get(kind.kind_id, ()), kind.kind_id
        assert kind.energy_roles == {} and kind.ledgers is None, kind.kind_id


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
    # Each of @3's own classes but faces admits the trapezoid, whose power is never negative (the
    # lead); faces admit the exact booking alone (D280).
    own = tuple(
        sorted(
            (mover, TRAPEZOID)
            for mover, admitted in inner_laws.OWN_HEAT_BOOKINGS.items()
            if TRAPEZOID in admitted
        )
    )
    assert inner_laws.OWN_HEAT_BOOKINGS[inner_laws.FACES] == (EXACT,)
    faces = ((inner_laws.FACES, EXACT),)
    assert inner_laws.InnerStructure(**BASE, heat_bookings=faces).heat_bookings == faces
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
            "faces admit": ((inner_laws.FACES, TRAPEZOID),),
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
    def kernel(*args, **kwargs):
        raise AssertionError("a planted law's kernel is never called")

    entry = kind_registry.FreeEnergyEntry
    hydrolysis = (("ATP", -1), ("ADP", 1), ("Pi", 1))
    formed = law_registry.CycleLaw(
        "tests.booked_formed_cycle@1", cycle=RolesForm(), host=PLANTED_ID
    )
    version_1 = law_registry.CycleLaw(
        "tests.booked_cycle@1", (("substrate", -1),), (), kernel, kernel, host=PLANTED_ID
    )
    elsewhere = law_registry.CycleLaw(
        "tests.elsewhere_cycle@1", cycle=RolesForm(), host="cells.transporter@1"
    )
    plain = entry(hydrolysis, -12.3, 1000.0)  # Names no law: an operator's reaction, say.
    coupled = entry(hydrolysis, -12.3, 1000.0, "tests.booked_formed_cycle@1", "coupled")
    assert (plain.law_id, plain.mode, plain.dG_kJ_mol, plain.dG_basis) == (None,) * 4
    # A law citing kJ/mol gives dG° so, with its basis, and no temperature (D234's option (b)).
    cited = entry(
        hydrolysis,
        c0=1000.0,
        dG_kJ_mol=-30.5,
        dG_basis=kind_registry.TEMPERATURE_INDEPENDENT,
        law_id="tests.booked_formed_cycle@1",
        mode="coupled",
    )
    assert cited.dG_RT is None and kind_registry.DG_BASES == ("temperature_independent",)
    assert plain.dG_RT_offset == cited.dG_RT_offset == 0  # Temperature-free part: none by default.
    # A value cited at pH 7: its temperature-free part, here nu_H ln 10^7, beside the kJ part.
    at_ph7 = cited._replace(dG_RT_offset=math.log(1e7))
    assert kind_registry.kind_standard_free_energies(planted(), ()) == ()
    kind = planted(standard_free_energies=lambda declaration: (plain, coupled, cited, at_ph7))
    assert kind_registry.declaration_errors(kind) == []
    with law_registry.scope(law_registry.BUILTIN.extended(formed, version_1, elsewhere)):
        assert kind_registry.kind_standard_free_energies(kind, ()) == (
            plain,
            coupled,
            cited,
            at_ph7,
        )
        plants = (  # Each refused when read, naming the entry.
            ([plain], "returns a tuple of FreeEnergyEntry"),
            (((hydrolysis, -12.3, 1000.0),), "returns a tuple of FreeEnergyEntry"),  # Bare.
            ((dict(plain._asdict()),), "returns a tuple of FreeEnergyEntry"),
            (((hydrolysis, -12.3, 1000.0, "x"),), "returns a tuple of FreeEnergyEntry"),
            ((plain._replace(stoichiometry=(("ATP",),)),), "entry 0: its stoichiometry"),
            ((plain._replace(stoichiometry=(("ATP", 0), ("ADP", 1))),), "its stoichiometry"),
            ((plain._replace(stoichiometry=(("ATP", -1), ("ATP", 1))),), "its stoichiometry"),
            ((plain._replace(stoichiometry=()),), "its stoichiometry"),
            ((plain._replace(dG_RT=math.inf),), "its dG°/RT is finite"),
            ((plain._replace(c0=0.0),), "its c0 is finite and positive"),
            ((plain._replace(c0=-1.0),), "its c0 is finite and positive"),
            ((plain, coupled._replace(mode=None)), "entry 1: it names its law and its mode"),
            ((plain._replace(mode="coupled"),), "it names its law and its mode together"),
            ((coupled._replace(law_id="tests.elsewhere_cycle@1"),), "is not a cycle law it hosts"),
            ((coupled._replace(law_id="tests.unregistered@1"),), "is not a cycle law it hosts"),
            ((coupled._replace(law_id="tests.booked_cycle@1"),), "is a version-1 law"),
            ((coupled._replace(mode="uncoupled"),), "form has no mode 'uncoupled'"),
            # Exactly one form: both, neither, and each form's own refusals.
            ((cited._replace(dG_RT=-12.3),), "entry 0: it gives its dG° in exactly one form"),
            ((plain._replace(dG_RT=None),), "it gives its dG° in exactly one form"),
            ((cited._replace(dG_basis=None),), "its dG_kJ_mol gives its basis, one of"),
            ((cited._replace(dG_basis="vant_hoff"),), "not 'vant_hoff'"),
            ((cited._replace(dG_kJ_mol=math.nan),), "its dG° in kJ/mol is finite"),
            ((cited._replace(dG_kJ_mol=True),), "its dG° in kJ/mol is finite"),
            (
                (plain._replace(dG_basis=kind_registry.TEMPERATURE_INDEPENDENT),),
                "qualifies a dG_kJ",
            ),
            ((cited._replace(c0=None),), "its c0 is finite and positive"),
            # The temperature-free offset: beside dG_kJ_mol alone, finite, not a bool.
            ((plain._replace(dG_RT_offset=1.0),), "its dG_RT_offset belongs beside a dG_kJ_mol"),
            ((cited._replace(dG_RT_offset=math.nan),), "its dG_RT_offset is finite"),
            ((cited._replace(dG_RT_offset=True),), "its dG_RT_offset is finite"),
        )
        for declared, words in plants:
            planted_kind = planted(standard_free_energies=lambda d, declared=declared: declared)
            with pytest.raises(ValueError, match=re.escape(words)):
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


STRUCTURAL_FALSE = PartitionRole("structural", False)
MASKS = ("booked_present", "booked_open")  # A population mask and a law's, as the transporter's.


def present_kind(**changes):
    """A kind with an entity axis of its own (routes on patches), a law-internal mode axis, and two
    presence masks for its routes."""
    kind = replace(
        planted(),
        state_axes=(("booked_dissipated_energy_pJ", ("booked_route", "booked_mode")),),
        layout_fields=("booked_host", *MASKS),
        field_axes={
            "booked_host": ("booked_route",),
            **dict.fromkeys(MASKS, ("booked_route",)),
            "booked_availability": (),
        },
        axis_hosts={"booked_route": AxisHost("patch", "booked_host")},
        internal_axes=("booked_mode",),
        presence={"booked_route": MASKS},
        partition_roles=dict.fromkeys(MASKS, STRUCTURAL_FALSE),
    )
    return replace(kind, **changes)


def test_presence_fields_are_bool_structural_fields_on_each_entity_axis():
    kind = present_kind()
    assert kind_registry.declaration_errors(kind) == []
    assert kind_registry.KindRegistry().register(kind) is kind
    assert kind_registry.entity_axes(kind) == ("booked_route",)  # The mode axis is internal.
    assert kind_registry.presence_fields(kind) == {"booked_route": MASKS}
    assert kind_registry.presence_fields(planted()) == {}  # None declared: refused by closers.
    one = present_kind(presence={"booked_route": ("booked_present",)})
    assert kind_registry.declaration_errors(one) == []  # One mask is a tuple of one.
    plants = {
        "booked_availability: not one of its layout fields": dict(
            presence={"booked_route": (*MASKS, "booked_availability")}
        ),
        "booked_open: its fill is 0, not False": dict(
            partition_roles={
                "booked_present": STRUCTURAL_FALSE,
                "booked_open": PartitionRole("structural", 0),
            }
        ),
        "fill=None), not structural with fill False": dict(
            partition_roles={
                "booked_present": PartitionRole("intensive"),
                "booked_open": STRUCTURAL_FALSE,
            }
        ),
        "booked_open: None, not structural with fill False": dict(
            partition_roles={"booked_present": STRUCTURAL_FALSE}
        ),
        "on ('booked_route', 'booked_mode'), not exactly ('booked_route',)": dict(
            field_axes={
                "booked_host": ("booked_route",),
                "booked_present": ("booked_route",),
                "booked_open": ("booked_route", "booked_mode"),
            }
        ),
        "presence of axis booked_mode: a shared or internal axis": dict(
            presence={"booked_route": MASKS, "booked_mode": ("booked_host",)}
        ),
        "presence of axis species: a shared or internal axis": dict(
            presence={"booked_route": MASKS, "species": ("booked_host",)}
        ),
        "lacks its entity axes ['membrane_slot']": dict(
            state_axes=(
                ("booked_dissipated_energy_pJ", ("booked_route", "booked_mode")),
                ("booked_work_pJ", ("membrane_slot",)),  # @3's slot axis: an entity axis.
            )
        ),
        "names axes no field of its own is on: ['booked_band']": dict(
            presence={"booked_route": MASKS, "booked_band": ("booked_host",)}
        ),
        "an empty tuple": dict(presence={"booked_route": ()}),
        "names fields more than once: ['booked_present']": dict(
            presence={"booked_route": ("booked_present", "booked_open", "booked_present")}
        ),
        "maps its entity axes to tuples of layout fields": dict(
            presence={"booked_route": "booked_present"}  # A name, not a tuple of names.
        ),
        "to tuples of layout fields": dict(presence={"booked_route": ("booked_present", 1)}),
    }
    for words, changes in plants.items():
        planted_kind = present_kind(**changes)
        errors = kind_registry.declaration_errors(planted_kind)
        assert any(words in e for e in errors), (words, errors)
        with pytest.raises(ValueError, match=PLANTED_ID):
            kind_registry.KindRegistry().register(planted_kind)
    # A kind whose fields follow its entry: each bound kind's presence covers its own entity axes
    # with its own layout fields.
    fields = present_kind()
    entries = {
        "routes": KindFields(fields.state_axes, fields.layout_fields, (), ()),
        "patches": KindFields(
            (("booked_work_pJ", ("membrane_slot",)),), fields.layout_fields, (), ()
        ),
        "bare": KindFields(fields.state_axes, ("booked_host", "booked_present"), (), ()),
    }
    per_entry = replace(fields, declared_fields=entries.get)
    assert kind_registry.presence_fields(kind_registry.bound(per_entry, "routes")) == {
        "booked_route": MASKS
    }
    with pytest.raises(ValueError, match=r"lacks its entity axes \['membrane_slot'\]"):
        kind_registry.presence_fields(kind_registry.bound(per_entry, "patches"))
    with pytest.raises(ValueError, match=r"names fields \['booked_open'\] that are not its"):
        kind_registry.presence_fields(kind_registry.bound(per_entry, "bare"))
    # B1's adapter's shared axes are the contract's.
    assert kind_registry.SHARED_AXES == pump_composite_adapter.SHARED_AXES


def test_a_bound_entry_s_presence_reads_its_own_fields_only():
    """Two entries with disjoint fields and one field_axes and presence covering both, as the
    transporter's two layouts declare them: each bound entry's presence is its own axis's masks
    (bound keeps field_axes whole, so entity_axes reads only the entry's own fields)."""
    routes = present_kind()
    bands = KindFields(
        (("booked_work_pJ", ("booked_band",)),), ("booked_band_host", "booked_band_present"), (), ()
    )
    entries = {
        "routes": KindFields(routes.state_axes, routes.layout_fields, (), ()),
        "bands": bands,
    }
    kind = replace(
        routes,
        declared_fields=entries.get,
        field_axes={
            **routes.field_axes,
            "booked_band_host": ("booked_band",),
            "booked_band_present": ("booked_band",),
        },
        axis_hosts={
            **routes.axis_hosts,
            "booked_band": AxisHost("junction", "booked_band_host"),
        },
        presence={"booked_route": MASKS, "booked_band": ("booked_band_present",)},
        partition_roles={**routes.partition_roles, "booked_band_present": STRUCTURAL_FALSE},
    )
    assert kind_registry.declaration_errors(kind) == []
    assert kind_registry.KindRegistry().register(kind) is kind
    on_routes, on_bands = (kind_registry.bound(kind, entry) for entry in ("routes", "bands"))
    assert kind_registry.entity_axes(on_routes) == ("booked_route",)
    assert kind_registry.entity_axes(on_bands) == ("booked_band",)
    assert kind_registry.presence_fields(on_routes) == {"booked_route": MASKS}
    assert kind_registry.presence_fields(on_bands) == {"booked_band": ("booked_band_present",)}


class RolesForm:
    """A planted general form, as seam A's CycleForm gives its change rows: "role@end", the ends
    its host's N and P."""

    def errors(self):
        return []

    def changes(self):
        return (
            {"role": "cofactor@N", "per_cycle": -1, "mode": "coupled"},
            {"role": "cofactor@P", "per_cycle": 1, "mode": "coupled"},
            {"role": "substrate@N", "per_cycle": "-n_coupled", "mode": "coupled"},
        )


def test_role_species_binds_each_entity_s_law_and_is_checked_when_read():
    def kernel(*args, **kwargs):
        raise AssertionError("a planted law's kernel is never called")

    version_1 = law_registry.CycleLaw(  # Moves-only: substrate and product at the inside.
        "tests.booked_cycle@1",
        (("substrate", -1), ("product", "n_coupled")),
        (),
        kernel,
        kernel,
        host=PLANTED_ID,
    )
    formed = law_registry.CycleLaw(
        "tests.booked_formed_cycle@1", cycle=RolesForm(), host=PLANTED_ID
    )
    elsewhere = law_registry.CycleLaw(  # A cycle law another kind hosts.
        "tests.elsewhere_cycle@1",
        (("substrate", -1),),
        (),
        kernel,
        kernel,
        host="cells.transporter@1",
    )
    inside = kind_registry.MOVES_END
    bind = kind_registry.EntityBinding
    # One per entity, in the declaration's order: two entities of one law bind different species,
    # nodes and counts, as two transporter populations of one law do; extra ends and values pass.
    entities = (
        bind(
            "tests.booked_cycle@1",
            roles={"substrate": "glucose", "product": "lactate"},
            ends={inside: "cell_a", "outside": "bath"},
            parameters={"n_coupled": 2},
        ),
        bind(
            "tests.booked_formed_cycle@1",
            roles={"cofactor": "ATP", "substrate": "glucose"},
            ends={"N": "cell_a", "P": "bath"},
            parameters={"n_coupled": 3},
        ),
        bind(
            "tests.booked_cycle@1",
            roles={"substrate": "fructose", "product": "lactate"},
            ends={inside: "cell_b", "outside": "bath", "P": "bath"},
            parameters={"n_coupled": 1, "spare": 0.5},
        ),
    )
    kind = planted(role_species=lambda declaration: entities)
    assert kind_registry.declaration_errors(kind) == []
    assert kind_registry.KindRegistry().register(kind) is kind
    with law_registry.scope(law_registry.BUILTIN.extended(version_1, formed, elsewhere)):
        assert kind_registry.law_roles(version_1) == {"substrate", "product"}
        assert kind_registry.law_roles(formed) == {"cofactor", "substrate"}  # "@end" read off.
        # A moves-only law's rows cross its patch: inward-positive at the inside, the opposite
        # sign at the outside, so both ends are its.
        assert kind_registry.law_ends(version_1) == set(kind_registry.MOVES_ENDS)
        assert kind_registry.MOVES_ENDS == (inside, "outside")
        assert kind_registry.law_ends(formed) == {"N", "P"}
        assert kind_registry.law_count_names(version_1) == {"n_coupled"}
        assert kind_registry.law_count_names(formed) == {"n_coupled"}  # Its "-" read off.
        assert kind_registry.kind_role_species(kind, ()) is entities
        assert kind_registry.kind_role_species(planted(role_species=lambda d: ()), ()) == ()
        assert planted().role_species is None
        assert kind_registry.kind_role_species(planted(), ()) is None  # Not refused here.
        first, second, third = entities
        plants = (  # Each refused when read, naming the entity.
            (list(entities), "returns a tuple of EntityBinding"),
            ((tuple(first), second, third), "returns a tuple of EntityBinding"),
            ((first._replace(law_id="tests.elsewhere_cycle@1"), second, third), "its law is not"),
            ((first._replace(law_id="tests.unregistered@1"), second, third), "its law is not"),
            ((first._replace(roles={"substrate": "glucose"}), second, third), "lacks ['product']"),
            (
                (first._replace(roles={**first.roles, "cofactor": "ATP"}), second, third),
                "binds ['cofactor']",
            ),
            ((first._replace(roles={**first.roles, "product": 1}), second, third), "its roles map"),
            ((first._replace(roles={**first.roles, "": "Na"}), second, third), "its roles map"),
            (
                (first, second._replace(ends={"N": "cell_a"}), third),
                "entity 1 ('tests.booked_formed_cycle@1'): it places no node at the ends ['P']",
            ),
            (
                (first._replace(ends={"outside": "bath"}), second, third),
                "entity 0 ('tests.booked_cycle@1'): it places no node at the ends ['inside']",
            ),
            (  # A moves-only law's outside, where its counts land with the opposite sign.
                (first._replace(ends={inside: "cell_a"}), second, third),
                "entity 0 ('tests.booked_cycle@1'): it places no node at the ends ['outside']",
            ),
            ((first._replace(ends={inside: 7}), second, third), "its ends map names to a name"),
            (
                (first, second, third._replace(parameters={"spare": 0.5})),
                "entity 2 ('tests.booked_cycle@1'): it gives no value for the counts ['n_coupled']",
            ),
            ((first._replace(parameters={"n_coupled": "2"}), second, third), "its parameters map"),
            ((first._replace(parameters={"n_coupled": True}), second, third), "its parameters map"),
            (
                (first._replace(parameters={"n_coupled": math.inf}), second, third),
                "its parameters map",
            ),
        )
        for declared, words in plants:
            planted_kind = planted(role_species=lambda declaration, declared=declared: declared)
            with pytest.raises(ValueError, match=re.escape(words)):
                kind_registry.kind_role_species(planted_kind, ())
    with pytest.raises(ValueError, match=PLANTED_ID):
        kind_registry.KindRegistry().register(planted(role_species=entities))


def test_a_kind_s_arrays_match_the_axes_it_declares_where_the_host_binds_them():
    """F's array-axes check (D228 item 6): where @3 binds a kind's initial state and layout, each
    field's array has its declared axes, @3's at @3's lengths, the kind's own at one length, and
    only a dispatch mask may be empty along them."""
    kind = present_kind(
        layout_fields=("booked_host", *MASKS, "booked_rate", "booked_scale"),
        field_axes={
            "booked_host": ("booked_route",),
            **dict.fromkeys(MASKS, ("booked_route",)),
            "booked_rate": ("species", "booked_route"),
            "booked_scale": (),
            "booked_availability": (),
        },
        dispatch_masks=("booked_open",),
    )
    assert kind_registry.declaration_errors(kind) == [] and planted().dispatch_masks == ()
    for masks, words in (  # Planted, each refused at registration.
        (["booked_open"], "a tuple of distinct field names"),
        (("booked_open", "booked_open"), "a tuple of distinct field names"),
        (("booked_elsewhere",), "dispatch mask booked_elsewhere: one of its state or layout"),
        (("booked_availability",), "dispatch mask booked_availability: one of its state or"),
        (("booked_scale",), "dispatch mask booked_scale: one of its state or layout fields"),
    ):
        with pytest.raises(ValueError, match=re.escape(words)):
            kind_registry.KindRegistry().register(replace(kind, dispatch_masks=masks))
    host = {"amounts": ("species", "cell_slot"), "heat": ("membrane_slot",)}
    sizes = kind_registry.axis_sizes(host, {"amounts": np.zeros((3, 2)), "heat": np.zeros(4)})
    assert sizes == {"species": 3, "cell_slot": 2, "membrane_slot": 4}
    with pytest.raises(ValueError, match=re.escape("amounts has shape (3,), not its axes")):
        kind_registry.axis_sizes(host, {"amounts": np.zeros(3)})
    with pytest.raises(ValueError, match="axis species has lengths 3 and 4"):
        kind_registry.axis_sizes(
            {"a": ("species",), "b": ("species",)}, {"a": np.zeros(3), "b": np.zeros(4)}
        )
    routes, modes = 5, 2
    state = {"booked_dissipated_energy_pJ": np.zeros((routes, modes))}
    layout = {
        "booked_host": np.zeros(routes, dtype=int),
        **{mask: np.zeros(routes, dtype=bool) for mask in MASKS},
        "booked_rate": np.zeros((3, routes)),
    }
    kind_registry.refuse_misshapen(kind, "initial values", state, layout, sizes)
    empty = {**layout, "booked_open": np.zeros(0, dtype=bool)}  # A dispatch mask may be empty.
    kind_registry.refuse_misshapen(kind, "initial values", state, empty, sizes)
    for changes, words in (  # Planted, each refused, naming the field.
        (dict(booked_rate=np.zeros(3)), "booked_rate binds shape (3,), not its declared axes"),
        (dict(booked_rate=np.zeros((2, routes))), "axis species has length 2, not the host's 3"),
        (dict(booked_present=np.zeros(4, dtype=bool)), "booked_present's axis booked_route has"),
        (dict(booked_present=np.zeros(0, dtype=bool)), "booked_present's axis booked_route has"),
        (dict(booked_open=np.zeros(3, dtype=bool)), "booked_open's axis booked_route has length 3"),
    ):
        with pytest.raises(ValueError, match=re.escape(words)):
            kind_registry.refuse_misshapen(
                kind, "initial values", state, {**layout, **changes}, sizes
            )
    with pytest.raises(
        ValueError, match=re.escape("booked_mode has length 3")
    ):  # An internal axis.
        kind_registry.refuse_misshapen(
            replace(kind, state_axes=(*kind.state_axes, ("booked_work_pJ", ("booked_mode",)))),
            "initial values",
            {**state, "booked_work_pJ": np.zeros(3)},
            layout,
            sizes,
        )
