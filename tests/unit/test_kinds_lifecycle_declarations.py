"""The kinds owner's kinds' lifecycle declarations (item 3, B1's kind-side roles: CORE_SEAMS §4.2
and §18's B1 lift; seam E's kind hook; the lead's rulings of 18 and 19 November 2026).

Each claim with its plant (D187):
- every field of cells.kind.patch_damage@1 declares its partition role and its axes, its own axis (the
  damage entities) names its host and index, and F's declaration check holds; beside a closer the
  kind passes the lift's roles and axes and stops at its presence step, since it declares no
  presence for its entity axes, its patches' slots and its own source axis (fail-closed) (planted:
  one role removed, and one field's axes removed, each named at its own step);
- the same for cells.kind.transporter@1 in both layouts, bound to each world's entry (version 1's, the
  general form's, §10's composed world with a diagram and a finite-fuel pump, a net-flow law and a
  diagram pump): every field's role and axes, every declared axis count equal to the field's own
  dimensions in the world's layout, state and controls, the population axis's host on its patch;
  beside a closer the lift admits each layout, its one entity axis declaring presence and, for the
  population axis, its host (planted: a diagram table's axes removed, version 1's scalar's role
  removed, version 1 without its presence, and the population axis without its host, each
  refused at its own step);
- Q2's presence and the laws' internal axes (F's contract): version 1's fuel-role axis and the
  population axis's law-internal axes are internal, so each layout's one entity axis is gated by its
  presence masks (version 1's three slot masks; each population's cycle_present, anded into its
  host's activity), and with every entity absent its rates, readouts and stage and material terms
  are exactly zero, as @3's binding check holds every parse to (planted: the fuel-role axis taken
  out of the internal ones, which leaves its presence short of an entity axis; and readouts that
  ignore cycle_present, which that check refuses);
- the roles as declared: d, the rate constants and the schedules are levels of their patch
  (intensive, so a split copies them), the patch's presence and each entity's patch slot
  structural; a transporter's capacity extensive, its cycles, heat, work and supply history;
- seam E's kind hook: a diagram pump's cycle declares the standard free energy its constants imply
  (ATP's hydrolysis, at the diagram's standard state) as F's FreeEnergyEntry naming its law and
  its mode, equal to the registry's within the band Wegscheider's condition admitted it in, which
  the form gives the entry's check (CycleForm.free_energy_band: wegscheider's band plus one ulp of
  the implied value, per mode; none for a factored form; planted: one potential off); factored, net-flow and transport-only cycles, and version
  1's entries, declare none (planted: one rate constant 1e-9 off moves it outside the band).
- §5.2's admission's reading (F's EntityBinding, role_species, checked by kind_role_species): each
  population, in declared order and in both layouts, binds its law, exactly the roles its change
  rows name, a node at each end they name (N at its N end) and its named counts' values; version
  1's world and its general twin bind alike, and an N = b population's ends turn with it
  (planted: a role dropped, and a count's value dropped, each refused by name).
Not declared, by the lead's rulings: passive routes and pH conditions, whose entities sit on hosts
of two kinds where AxisHost names one, stay refused beside closers this pass (Q3 and Q6 (a)).
"""

import contextlib
import copy
import dataclasses
import math
from decimal import Decimal, localcontext
from types import MappingProxyType

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import patch_damage, transporter
from cells.laws.cycles import forms
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.kind_registry import EntityBinding, PartitionRole
from tests.unit import test_cycle_forms as tf
from tests.unit import test_cycle_kind as ck
from tests.unit import test_transporter_kind as tk


def test_patch_damage_declares_every_fields_role_and_axes_and_its_entities_host():
    kind = patch_damage.PATCH_DAMAGE
    assert kind_registry.declaration_errors(kind) == []
    assert kind_registry.missing_partition_roles(kind) == ()
    # Past the roles and the axes, the lift's presence step: no presence for either entity axis.
    assert kind_registry.entity_axes(kind) == ("membrane_slot", patch_damage.SOURCE_AXIS)
    assert adapter.kind_lifecycle_errors(kind) == ("presence", ("membrane_slot", patch_damage.SOURCE_AXIS))
    table = adapter.kind_role_table(kind)
    patch, source = ("membrane_slot",), (patch_damage.SOURCE_AXIS,)
    for name in ("patch_damage", "patch_damage_injury_rate_per_s", "patch_damage_injury"):
        assert table[name] == (PartitionRole("intensive"), patch), name
    assert table["patch_damage_present"] == (PartitionRole("structural", False), patch)
    assert table["patch_damage_source_slot"] == (PartitionRole("structural", 0), source)
    host = kind.axis_hosts[patch_damage.SOURCE_AXIS]
    assert host.kind == "patch" and kind.field_axes[host.index] == source
    # Planted: one role removed, then one field's axes removed, each named at its own step.
    roles = {k: v for k, v in kind.partition_roles.items() if k != "patch_damage_injury"}
    no_role = dataclasses.replace(kind, partition_roles=MappingProxyType(roles))
    assert adapter.kind_lifecycle_errors(no_role) == ("roles", ("patch_damage_injury",))
    axes = {k: v for k, v in kind.field_axes.items() if k != "patch_damage_resealing"}
    no_axes = dataclasses.replace(kind, field_axes=MappingProxyType(axes))
    assert adapter.kind_lifecycle_errors(no_axes) == ("axes", ("patch_damage_resealing",))


# ------------------------------------------------------------------ the transporter's two layouts

PUMP = law_registry.CycleLaw(
    "seamtest.cycle.diagram_pump@1",
    (),
    (),
    None,
    None,
    cycle=tf.pump_form(),
    host=transporter.KIND_ID,
    provenance="calibrated",
    source="a test-only diagram pump (tests/unit/test_cycle_forms.py), never shipped",
)


def pump_world():
    """Heredity cell D with H and the registry's potentials that the diagram pump's constants were
    built on (tests/unit/test_cycle_forms.py's PUMP_MU, at 1000 mM), held fuel, one population."""
    population = dict(
        id="diagram_pump_0", host="membrane_0", law=PUMP.law_id, orientation={"N": "a"},
        capacity_fmol_s=0.01, roles={"H": "H", "ATP": "ATP", "ADP": "ADP", "Pi": "Pi"},
        parameters={}, held_rows=[["ATP", "N"], ["ADP", "N"], ["Pi", "N"]],
    )  # fmt: skip
    raw = tk.held_world(population, potentials=False)
    m = raw["model"]
    m["standard_concentration_mM"] = 1000.0
    for entry in m["species"]:
        if entry["id"] in ("ATP", "ADP", "Pi"):
            entry["standard_mu_RT"] = tf.PUMP_MU[(entry["id"], "N")]
    return ck.add_species(raw, "H", 1, 0.0, {"cell_0": 1e-4, "bath_0": 1e-4})


def worlds():
    """{name: raw definition} for each layout and form the transporter's declarations cover."""
    v1 = tk.held_world()
    general = copy.deepcopy(v1)
    general["model"]["transporters"] = [ck.general(v1["model"]["transporters"][0])]
    return {
        "version_1": v1,
        "general": general,
        "composed": ck.exchange_world(ck.exchanger(), ck.FINITE_POP),
        "net_flow": ck.exchange_world(ck.exchanger(law=ck.HONEST.law_id)),
        "diagram_pump": pump_world(),
    }


@contextlib.contextmanager
def scoped():
    """The transporter in a test kind registry; its test laws and the diagram pump in a law one."""
    with tk.scoped(), law_registry.scope(law_registry.BUILTIN.extended(*ck.TEST_LAWS, PUMP)):
        yield


def bound_worlds():
    """{name: (spec, the bound kind, its declaration, its layout, state and controls)}."""
    out = {}
    with scoped():
        for name, raw in worlds().items():
            spec = parse_spec(raw)
            structure = surface_pump_v3.structure(spec.model)
            entry = dict(structure.kinds)[transporter.KIND_ID]
            state, p = surface_pump_v3.initial_values(spec, structure=structure)
            controls = control_values(spec, [0.0])
            bound = kind_registry.bound(transporter.TRANSPORTER, entry)
            declaration = dict(spec.model.kinds)[transporter.KIND_ID]
            out[name] = (spec, bound, declaration, p, state, controls)
    return out


def test_the_transporters_two_layouts_declare_every_fields_role_and_axes():
    kind = transporter.TRANSPORTER
    assert kind_registry.declaration_errors(kind) == []
    host = kind.axis_hosts[transporter.POPULATION_AXIS]
    assert host == kind_registry.AxisHost("patch", transporter.MARK)
    assert kind.field_axes[host.index] == (transporter.POPULATION_AXIS,)
    for name, (_, bound, _, p, state, controls) in bound_worlds().items():
        assert kind_registry.missing_partition_roles(bound) == (), name
        axes = adapter.kind_field_axes(bound)
        for field in bound.layout_fields:  # Each declared axis count is the field's own.
            assert np.ndim(getattr(p, field)) == len(axes[field]), (name, field)
        for field in bound.state_fields:
            assert np.ndim(getattr(state, field)) == len(axes[field]), (name, field)
        for field in bound.control_fields:  # control_values: [times, ...].
            assert np.ndim(getattr(controls, field)) - 1 == len(axes[field]), (name, field)
        fields = kind_registry.partition_fields(bound)
        per_entity = tuple(f for f in fields if any(a not in adapter.SHARED_AXES for a in axes[f]))
        scalars = {"transporter_c0_mM"} if name == "version_1" else set()
        assert set(fields) - set(per_entity) == scalars, name
        # The lift admits it beside a closer: its one entity axis declares presence, and the
        # population axis also its host (version 1's slots are a gated slot axis of @3's).
        assert adapter.kind_lifecycle_errors(bound) == (), name
        table = adapter.kind_role_table(bound)
        if name == "version_1":
            assert table["transporter_capacity_fmol_s"][0] == PartitionRole("extensive")
            assert table["transporter_km_atp_mM"][0] == PartitionRole("structural", 1.0)
            assert table["transporter_cycles"][0] == PartitionRole("history")
        else:
            assert table["cycle_capacity_fmol_s"][0] == PartitionRole("extensive")
            assert table[transporter.MARK] == (
                PartitionRole("structural", 0),
                (transporter.POPULATION_AXIS,),
            )
            for field in ("cycle_count", "cycle_dissipated_energy_pJ", "cycle_supplied_fmol"):
                assert table[field][0] == PartitionRole("history"), field
    # Q2's presence and the internal axes: one entity axis per layout, gated by its masks.
    built = bound_worlds()
    for name, (_, bound, _, p, _, _) in built.items():
        presence = kind_registry.presence_fields(bound)
        if name == "version_1":
            assert kind_registry.entity_axes(bound) == ("membrane_slot",)
            assert presence == {"membrane_slot": transporter.PRESENCE["membrane_slot"]}
        else:
            assert kind_registry.entity_axes(bound) == (transporter.POPULATION_AXIS,)
            assert presence == {transporter.POPULATION_AXIS: ("cycle_present",)}, name
            assert p.cycle_present.dtype == np.bool_ and bool(np.all(p.cycle_present)), name
    short = tuple(a for a in kind.internal_axes if a != "transporter_fuel_role")
    with pytest.raises(ValueError, match=r"lacks its entity axes \['transporter_fuel_role'\]"):
        kind_registry.presence_fields(dataclasses.replace(built["version_1"][1], internal_axes=short))
    # Planted: a diagram table's axes removed, and version 1's scalar's role removed.
    axes = {k: v for k, v in kind.field_axes.items() if k != "cycle_dg_term_slots"}
    composed = dataclasses.replace(built["composed"][1], field_axes=MappingProxyType(axes))
    assert adapter.kind_lifecycle_errors(composed) == ("axes", ("cycle_dg_term_slots",))
    roles = {k: v for k, v in kind.partition_roles.items() if k != "transporter_c0_mM"}
    v1 = dataclasses.replace(built["version_1"][1], partition_roles=MappingProxyType(roles))
    assert adapter.kind_lifecycle_errors(v1) == ("roles", ("transporter_c0_mM",))
    # Planted: version 1 without its presence, and the population axis without its host.
    no_presence = dataclasses.replace(built["version_1"][1], presence=MappingProxyType({}))
    assert adapter.kind_lifecycle_errors(no_presence) == ("presence", ("membrane_slot",))
    unhosted = dataclasses.replace(built["general"][1], axis_hosts=MappingProxyType({}))
    assert adapter.kind_lifecycle_errors(unhosted) == ("hosts", (transporter.POPULATION_AXIS,))


def registry_sum(stoichiometry):
    """The registry's sum of nu mu°/RT at 1000 mM for the pump world's species (PUMP_MU), exact."""
    with localcontext() as ctx:
        ctx.prec = forms.DIGITS
        return sum(n * Decimal(tf.PUMP_MU[(species, "N")]) for species, n in stoichiometry)


def test_a_diagram_pumps_cycle_declares_the_free_energy_its_constants_imply():
    built = bound_worlds()
    kind = transporter.TRANSPORTER
    _, _, declaration, _, _, _ = built["diagram_pump"]
    with scoped():
        declared = kind_registry.kind_standard_free_energies(kind, declaration)  # Its form, checked.
    (entry,) = declared
    stoichiometry, value, c0 = entry.stoichiometry, entry.dG_RT, entry.c0
    assert stoichiometry == (("ATP", -1), ("ADP", 1), ("Pi", 1)) and c0 == 1000.0  # H only moves.
    assert isinstance(entry, kind_registry.FreeEnergyEntry)  # F's entry, no longer a 3-tuple:
    assert (entry.law_id, entry.mode) == (PUMP.law_id, "pump")  # the law and mode it came from.
    valence = dict(tf.PUMP_ROLES)
    potential = {role: tf.PUMP_MU[(role, "N")] for role in ("ATP", "ADP", "Pi")}
    w = forms.wegscheider(PUMP.cycle, 0, valence, potential, 1000.0)
    assert w.admitted
    # The registry's at the same standard state (c0 = the registry's here): within the band that
    # admitted the law, and the value's own rounding (half an ulp).
    allowed = float(w.band) + math.ulp(value)
    assert abs(Decimal(value) - registry_sum(stoichiometry)) <= Decimal(allowed)
    # The form's band for this entry (CycleForm.free_energy_band; the binding owner's check, under
    # ruling (d)): wegscheider's own band, plus one ulp of the implied value (the lead's ruling);
    # a factored form gives none. Planted: one potential off moves it.
    terms = tuple((n, tf.PUMP_MU[(s, "N")]) for s, n in stoichiometry)
    band = PUMP.cycle.free_energy_band(entry.mode, terms, 1000.0)
    assert band == w.band + Decimal(math.ulp(value))
    off = ((terms[0][0], terms[0][1] + 1.0), *terms[1:])
    assert PUMP.cycle.free_energy_band(entry.mode, off, 1000.0) != band
    assert transporter.PROTON.cycle.free_energy_band("cycle", terms, 1000.0) is None
    slip = tf.slip_form()  # Each mode reads its own cycle: the slip exchanger's three.
    valence = dict(tf.SLIP_ROLES)
    for m, (mode, _) in enumerate(slip.modes):
        own = forms.wegscheider(slip, m, valence, {}, 1000.0).band
        implied = forms.implied_free_energy(slip, m)[1]
        assert slip.free_energy_band(mode, (), 1000.0) == own + Decimal(math.ulp(implied)), mode
    for name in ("version_1", "general", "composed", "net_flow"):  # No constants of their own.
        _, bound, other, _, _, _ = built[name]
        with scoped():
            assert kind_registry.kind_standard_free_energies(bound, other) == (), name
    assert built["version_1"][1].standard_free_energies is None  # Version 1's hooks, exactly.
    # Planted: the fuel edge's forward constant 1e-9 larger moves the implied value outside.
    edges = tuple(
        e._replace(forward=e.forward._replace(k0_per_s=e.forward.k0_per_s * (1 + 1e-9)))
        if e.id == "fuel" else e
        for e in PUMP.cycle.diagram.edges
    )  # fmt: skip
    planted = PUMP.cycle._replace(diagram=PUMP.cycle.diagram._replace(edges=edges))
    _, shifted, _ = forms.implied_free_energy(planted, 0)
    assert abs(Decimal(shifted) - registry_sum(stoichiometry)) > Decimal(allowed)


def test_an_absent_population_reads_zero_and_ungated_readouts_are_refused_at_binding():
    """@3's binding check (Q2's contract) holds every parse of a presence-declaring kind to exact
    zeros with every entity absent: the transporter's general layout passes it in every world
    above (bound_worlds parses each); planted, readouts that ignore cycle_present are refused."""

    def ungated(state, read, potentials, control, p, *, xp):
        return transporter.readouts(
            state, read, potentials, control, p._replace(cycle_present=xp.ones_like(p.cycle_present)), xp=xp
        )

    planted = dataclasses.replace(transporter.TRANSPORTER, readouts=ungated)
    raw = worlds()["general"]
    with tk.scoped(planted), law_registry.scope(law_registry.BUILTIN.extended(*ck.TEST_LAWS, PUMP)):
        with pytest.raises(ConfigError, match="readout column"):
            parse_spec(copy.deepcopy(raw))


def test_each_population_binds_its_laws_roles_ends_and_counts_for_the_admission():
    kind = transporter.TRANSPORTER
    built = bound_worlds()
    with scoped():
        read = {
            name: kind_registry.kind_role_species(kind, declaration)
            for name, (_, _, declaration, _, _, _) in built.items()
        }
    fuel = {"ATP": "ATP", "ADP": "ADP", "Pi": "Pi"}
    ends = {"N": "cell_0", "P": "bath_0"}
    pump = EntityBinding(transporter.NEUTRAL_LAW, {"role": "Y", **fuel}, ends, {"stoichiometry": 1})
    assert read["version_1"] == (pump,) and read["general"] == (pump,)  # The one-to-one map.
    exchanger, fuel_pump = read["composed"]
    assert exchanger == EntityBinding("seamtest.cycle.slip_exchanger@1", {"X": "X", "Y": "W"}, ends, {})
    assert fuel_pump == pump
    # An N = b population's ends turn with it: N at the outside node.
    turned = ck.general(tk.population(id="t_b"), n_end="b")
    turned["held_rows"] = [["ATP", "N"], ["ADP", "N"], ["Pi", "N"]]
    with scoped():
        spec = parse_spec(tk.held_world(ck.general(tk.population(id="t_a")), turned))
        a, b = kind_registry.kind_role_species(kind, dict(spec.model.kinds)[transporter.KIND_ID])
    assert a.ends == ends and b.ends == {"N": "bath_0", "P": "cell_0"} and a.roles == b.roles
    # Planted: a role dropped, then a count's value dropped, each refused by name.
    declaration = built["version_1"][2]

    def dropping(field, name):
        def read_less(d):
            return tuple(
                e._replace(**{field: {k: v for k, v in getattr(e, field).items() if k != name}})
                for e in transporter.role_species(d)
            )

        return dataclasses.replace(kind, role_species=read_less)

    with scoped():
        with pytest.raises(ValueError, match=r"lacks \['ATP'\]"):
            kind_registry.kind_role_species(dropping("roles", "ATP"), declaration)
        with pytest.raises(ValueError, match=r"no value for the counts \['stoichiometry'\]"):
            kind_registry.kind_role_species(dropping("parameters", "stoichiometry"), declaration)
