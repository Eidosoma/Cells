"""Tier-1 smoke test of cell_owned_compartments@1 and the contract's declarations (FR-1, D169).

docs/CLOSED_COMPARTMENT_DESIGN.md §1.4 to §1.6 and §4, in NumPy (no compile), on the silence world W
(validation/tissue/compartment_fixtures.loaded_compartment):
* the contract (§1.6, option (b), the lead's rulings): a DECLARATION_ONLY operator may define only
  contract.DECLARATION_MAY_DEFINE, fail closed: every other public attribute of Operator, data or
  method (parts, fields, step methods, schedule and definition-check hooks), is refused with its
  name, even restated at its default. Its SCOPED_READS may be unscoped reference reads only (D217):
  a current, fixed or scoped read is refused. The part-less operator with nothing at all (the
  contract test's `Nothing`) stays refused. A part-less owner whose every owned field is an accepted
  write is admitted, and one with an owned field nothing writes is refused. Every registered
  operator is admitted, as before;
* the declaration parses and round-trips, its refusals 1 to 7 fire with their reasons, and the
  summary carries the identity block. A label or reference changes no binding. Refusal 5 version
  1.2 admits an anchor where an admitted operator's routes charge the compartment (planted per
  compartment), at the definition, and FR-1's judged class still holds its prefixed message;
* the composite's structure check refuses the providers and closers of what the declaration reads
  as declared, in either order, and admits the operators of its list; the list fails closed. The
  areas and capacitances are reference reads, so membrane state passes the structure check, and the
  definition admits it only together with trafficking (FR-2's door; a stand-in until its module
  lands).
"""

import copy
import dataclasses
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import ClassVar

import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import ConfigError, parse_spec
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS
from cells.operators import compartments as comp
from cells.operators.contract import (
    DECLARATION_MAY_DEFINE,
    Operator,
    Read,
    check_declarations,
    declaration_errors,
    reads_of,
)
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from tests import kind_fixtures
from validation.fr7 import unit_turnover_fixtures as ufx
from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx

LAW = cfx.LAW
END = 0.004


def w(**kwargs):
    return cfx.loaded_compartment(end=END, **kwargs)


def declared(raw, compartments):
    out = copy.deepcopy(raw)
    out["model"]["operators"][-1]["compartments"] = compartments
    return out


def node(raw, name):
    return next(c for c in raw["model"]["extracellular"] if c["id"] == name)


def patch(raw, name):
    return next(p for p in raw["model"]["membranes"] if p["id"] == name)


def two_cells(*, contacts, faces=(), junctions=()):
    """Two cells on the bath; cell_0's compartment ecs_0, a finite node ecs_1 beside cell_1."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0), ("ecs_1", 1.0)),
        contacts=contacts,
        faces=faces,
        junctions=junctions,
        end=0.01,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6, ecs_1=5e-4),
    )
    return raw


# ------------------------------------------------------------------ the contract


class Minimal(Operator):
    LAW_ID = "minimal_declaration@1"
    DECLARATION_ONLY = True


def test_the_declaration_is_admitted_and_contributes_nothing():
    op = OPERATORS[LAW]
    assert type(op).DECLARATION_ONLY and declaration_errors(type(op)) == []
    assert check_declarations(type(op)) is type(op)
    assert check_declarations(Minimal) is Minimal
    for other in OPERATORS.values():  # Every registered operator, as before.
        assert check_declarations(type(other)) is type(other)


def test_the_operator_with_nothing_at_all_stays_refused():
    class Nothing(Operator):
        LAW_ID = "nothing@1"

    with pytest.raises(ValueError, match="contributes at least one part"):
        check_declarations(Nothing)


CONTRACT = sorted(n for n in dir(Operator) if not n.startswith("_"))
FORBIDDEN = [n for n in CONTRACT if n not in DECLARATION_MAY_DEFINE]


def test_the_check_covers_every_hook_the_lead_named():
    for name in ("inner_check_spec", "check_steps", "control_values", "schedule_times"):
        assert name in FORBIDDEN
    assert set(DECLARATION_MAY_DEFINE) <= set(CONTRACT)


@pytest.mark.parametrize("name", FORBIDDEN)
def test_a_declaration_that_defines_anything_else_of_the_contract_is_refused(name):
    """Fail closed: data or method, even at its default value, anything below Operator outside
    DECLARATION_MAY_DEFINE is refused, with its name."""
    value = (lambda self, *a, **k: None) if callable(getattr(Operator, name)) else ("x",)
    marked = type("Marked", (Minimal,), {name: value})
    with pytest.raises(ValueError, match=rf"a declaration contributes nothing.* {name}\b"):
        check_declarations(marked)
    same = type("Same", (Minimal,), {name: getattr(Operator, name)})
    if not callable(getattr(Operator, name)):  # Restating a default is still a definition.
        with pytest.raises(ValueError, match=rf" {name}\b"):
            check_declarations(same)


def test_a_declaration_may_define_what_a_declaration_needs():
    allowed = {
        "CONFLICTS_VIEW": ("volume",),
        "REQUIRES": (),
        "parse": lambda self, raw, base, inner: None,
        "to_dict": lambda self, declaration, base: {},
        "check_definition": lambda self, spec, declaration, schedule, model: None,
        "initial_values": lambda self, *a: ({}, {}),
        "summary": lambda self, *a: {},
    }
    declared = type("Declared", (Minimal,), allowed)
    assert check_declarations(declared) is declared


REFERENCE = Read("reference", "end")
# name: (SCOPED_READS, refusal or None). Each refused entry is its admitted twin's planted error.
DECLARATION_READS = {
    "a reference read": ({"membrane_area": REFERENCE}, None),
    "a reference read at two stages": (
        {"membrane_area": (REFERENCE, Read("reference", "observe"))},
        None,
    ),
    "a current read": ({"volume": Read("current", "end")}, "not an unscoped reference read"),
    "a fixed read": ({"volume": Read("fixed", "end")}, "not an unscoped reference read"),
    "a scoped reference read": (
        {"membrane_area": Read("reference", "end", scoped=True)},
        "not an unscoped reference read",
    ),
    "a reference read beside a current one": (
        {"volume": (REFERENCE, Read("current", "observe"))},
        "not an unscoped reference read",
    ),
    "a read that is no Read": ({"membrane_area": ("reference", "end")}, "not an unscoped"),
    "a reference read at a part's stage": (
        {"membrane_area": Read("reference", "split")},
        "at stage split, which none of its parts runs at",
    ),
}


@pytest.mark.parametrize("name", sorted(DECLARATION_READS))
def test_a_declarations_reads_are_unscoped_reference_reads(name):
    """The contract gap FR-2 found (its design statement §7.2; the lead's ruling (a) on its question
    10, 19 November 2026): a declaration may declare SCOPED_READS, each an unscoped reference read,
    the bound value as data (D217). It has no part to consume a view (current) and holds a field as
    physical only through CONFLICTS_VIEW (fixed), and it defines no read_slots (scoped): each is
    refused, naming the field. A reference read at a stage none of its parts runs at is refused by
    the door S check, as for any operator."""
    reads, refusal = DECLARATION_READS[name]
    declared = type("Reads", (Minimal,), {"SCOPED_READS": reads})
    if refusal is None:
        assert check_declarations(declared) is declared
    else:
        field = next(iter(reads))
        with pytest.raises(ValueError, match=rf"{field}.*{refusal}|{refusal}.*{field}"):
            check_declarations(declared)


def test_a_declarations_scoped_reads_are_a_mapping():
    unmapped = type("Unmapped", (Minimal,), {"SCOPED_READS": (REFERENCE,)})
    with pytest.raises(ValueError, match="declares SCOPED_READS that is not a mapping"):
        check_declarations(unmapped)


def test_the_compartments_read_their_areas_and_capacitances_as_references():
    """D217 (docs/MEMBRANE_RETRIEVAL_DESIGN.md §6): the declaration reads the declared bounding
    patch's area and capacitance as data, its identity, so they are no longer held as declared
    (CONFLICTS_VIEW) and a provider of them is no conflict; the volumes and masks stay fixed."""
    op = OPERATORS[LAW]
    for name in ("membrane_area", "membrane_capacitance"):
        assert name not in op.CONFLICTS_VIEW
        assert reads_of(op, name) == (REFERENCE,)
    for name in ("volume", "extracellular_volume", "active", "membrane_active", "face_active"):
        assert reads_of(op, name) == (Read("fixed", "event"),), name  # The default fixed read.


def test_a_part_less_owner_of_accepted_writes_only_is_admitted():
    class Owner(Operator):
        LAW_ID = "accepted_owner@1"
        STATE_AXES = {"held_fmol": ["cell_slot"]}
        LEDGERS = ("held",)
        LEDGER_DIAGNOSTICS = ("held_error_fmol",)
        ACCEPTS_WRITES = {"held_fmol": ("held",)}

    class Stranded(Owner):
        LAW_ID = "stranded_owner@1"
        STATE_AXES = {"held_fmol": ["cell_slot"], "stuck_fmol": ["cell_slot"]}

    assert check_declarations(Owner) is Owner
    with pytest.raises(ValueError, match="contributes at least one part"):
        check_declarations(Stranded)


# ------------------------------------------------------------------ the declaration


def test_the_declaration_parses_round_trips_and_names_its_compartments():
    spec = parse_spec(w())
    assert [d.law for d in spec.model.operators] == ["scheduled_species_exchange@1", LAW]
    declaration = spec.model.operators[-1]
    assert declaration.compartments == (
        comp.Compartment(
            "lys_0", "ecs_0", "contact_0", "cell_0", "lumen", False, "lysosome pool", None
        ),
    )
    assert parse_spec(cs.to_dict(spec)) == spec
    op = OPERATORS[LAW]
    summary = op.summary(spec, declaration, (), None)
    assert summary["compartments"] == [
        dict(
            id="lys_0",
            owner=dict(cell="cell_0", slot=0, carrier="cell_0"),
            role="lumen",
            role_declared=False,
            storage=dict(kind="outside_node", node="ecs_0", slot=1),
            membrane=dict(
                patch="contact_0",
                slot=1,
                inside=dict(kind="cell", id="cell_0", slot=0),
                outside=dict(kind="compartment", id="lys_0"),
                voltage="inside minus outside: V_b = phi_owner - phi_compartment",
            ),
            label="lysosome pool",
            reference=None,
        )
    ]
    model = get_model(spec.model)
    assert (
        model.STATE_TYPE._fields
        == get_model(parse_spec(w(declared=False)).model).STATE_TYPE._fields
    )


def test_two_compartments_in_one_cell_stay_distinct_in_the_identity_map():
    """ARCHITECTURE.md's modular core (D174): the host-side map keeps two compartments of one
    owner distinct, each with its own storage slot and its own oriented bounding membrane."""
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0), ("ecs_1", 0.5)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_0", "ecs_1")),
        faces=(),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6, ecs_1=1e-6),
    )
    raw = cfx.with_compartments(
        raw,
        [
            cfx.compartment(label="lysosome pool"),
            cfx.compartment(
                cid="gran_0",
                node="ecs_1",
                patch="contact_1",
                label="secretory granules",
                role="granule lumen",
            ),
        ],
    )
    spec = parse_spec(raw)
    entries = comp.identity_map(spec.model, spec.model.operators[-1])
    assert [e["id"] for e in entries] == ["lys_0", "gran_0"]
    assert [(e["role"], e["role_declared"]) for e in entries] == [
        ("lumen", False),
        ("granule lumen", True),
    ]
    assert [e["storage"]["node"] for e in entries] == ["ecs_0", "ecs_1"]
    assert {e["owner"]["cell"] for e in entries} == {"cell_0"}
    assert [e["storage"]["slot"] for e in entries] == [1, 2]
    assert [e["membrane"]["patch"] for e in entries] == ["contact_0", "contact_1"]
    assert [e["membrane"]["outside"]["id"] for e in entries] == ["lys_0", "gran_0"]
    assert all(e["membrane"]["inside"] == dict(kind="cell", id="cell_0", slot=0) for e in entries)
    assert OPERATORS[LAW].summary(spec, spec.model.operators[-1], (), None)["compartments"] == list(
        entries
    )


def test_a_label_or_a_reference_changes_no_binding():
    plain = cfx.bindings(w())
    for label, reference in (("secretory granules", None), (None, "GO:0005764")):
        other = cfx.bindings(declared(w(), [cfx.compartment(label=label, reference=reference)]))
        assert cfx.same_bindings(plain, other) == []
    for cid, role in (("lys_9", None), ("lys_0", "lysosome lumen")):  # Metadata too.
        other = cfx.bindings(declared(w(), [cfx.compartment(cid=cid, role=role)]))
        assert cfx.same_bindings(plain, other) == []


def test_a_declared_role_round_trips_and_the_default_is_recorded():
    spec = parse_spec(declared(w(), [cfx.compartment(role="lysosome lumen")]))
    assert parse_spec(cs.to_dict(spec)) == spec
    entry = comp.identity_map(spec.model, spec.model.operators[-1])[0]
    assert (entry["role"], entry["role_declared"]) == ("lysosome lumen", True)
    plain = parse_spec(w())
    assert "role" not in cs.to_dict(plain)["model"]["operators"][-1]["compartments"][0]
    summary = OPERATORS[LAW].summary(plain, plain.model.operators[-1], (), None)
    assert summary["compartments_role_default"] == "lumen"
    assert summary["compartments"][0]["role_declared"] is False


def closed_world(gauge):
    raw = w()
    node(raw, "bath")["reservoir"] = False
    raw["model"]["closure"]["gauge_reference"] = gauge
    return raw


def faced_world():
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"),),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5),),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6),
    )
    return cfx.with_compartments(raw, [cfx.compartment()])


def shared_node():
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_0")),
        faces=(),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, cell_1=1e-3, ecs_0=1e-6),
    )
    return cfx.with_compartments(raw, [cfx.compartment()])


def misowned():
    raw = two_cells(contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")))
    return cfx.with_compartments(raw, [cfx.compartment(owner="cell_1")])


def permeable():
    raw = w()
    patch(raw, "contact_0")["permeability_m_per_s"]["K"] = 1e-9
    return raw


def channelled():
    """A K leak channel population on the bounding patch (refusal 4's channel branch)."""
    raw = w()
    raw["model"]["channels"] = [
        dict(
            id="leak_0",
            membrane_id="contact_0",
            kinetic_law="kleak_always_open@1",
            max_permeability_m_per_s=1e-9,
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
    ]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id="leak_0", schedule=[dict(time=0.0, availability=1.0)])
    ]
    raw["execution"]["channel_capacity"] = 1
    return raw


def pumped():
    """A Na/K pump on the bounding patch (refusal 4's pump branch)."""
    raw = w()
    bounding = next(p for p in raw["model"]["membranes"] if p["id"] == "contact_0")
    bounding["pump"] = dict(
        id="pump_c",
        law="nak_atp_mass_action_positive@1",
        roles=dict(sodium="Na", potassium="K"),
        stoichiometry=dict(Na=-3, K=2),
        capacity_fmol_per_s=1e-3,
        km_na_mM=12.0,
        km_k_mM=0.2,
        km_atp_mM=0.5,
        metabolism=dict(
            kind="maintained_chemical_reservoirs@1",
            atp_mM=1.5,
            adp_mM=0.1,
            pi_mM=0.1,
            delta_g0_J_per_mol=-37000.0,
        ),
    )
    raw["experiment"]["pump_controls"] = [
        dict(pump_id="pump_c", schedule=[dict(time=0.0, availability=1.0)])
    ]
    return raw


def charged():
    raw = w()
    lumen = node(raw, "ecs_0")
    lumen["fixed_charge_equivalent_fmol"] += 1e-8
    valence = {s["id"]: s["valence"] for s in raw["model"]["species"]}
    net = lumen["fixed_charge_equivalent_fmol"] + sum(
        valence[s] * n for s, n in lumen["initial_amount_fmol"].items()
    )
    lumen["initial_charge_C"] = CHARGE_PER_FMOL * net
    return raw


REFUSALS = {
    "an undeclared node": (
        lambda: declared(w(), [cfx.compartment(node="nowhere")]),
        "is not a declared outside node",
    ),
    "a held bath": (
        lambda: declared(w(), [cfx.compartment(node="bath", patch="wall_cell_0")]),
        "is a held bath",
    ),
    "the gauge": (lambda: closed_world("ecs_0"), "is the gauge"),
    "a node named by a face": (faced_world, "is named by the face 'face_0'"),
    "an undeclared patch": (
        lambda: declared(w(), [cfx.compartment(patch="nope")]),
        "is not declared",
    ),
    "a patch that does not face the node": (
        lambda: declared(w(), [cfx.compartment(patch="wall_cell_0")]),
        "is bounded by exactly one patch",
    ),
    "a node faced by two patches": (shared_node, "is bounded by exactly one patch"),
    "an owner that is not a cell": (
        lambda: declared(w(), [cfx.compartment(owner="bath")]),
        "is not a cell",
    ),
    "a patch on another cell": (misowned, "not on its declared owner 'cell_1'"),
    "two compartments on one node": (
        lambda: declared(w(), [cfx.compartment(), cfx.compartment(cid="lys_1", label="again")]),
        "one compartment per node",
    ),
    "an ion route on the bounding patch": (
        permeable,
        "carries an ion route, a nonzero constant-field permeability, in a world that declares "
        "no kind",
    ),
    "a pump on the bounding patch": (
        pumped,
        "carries an ion route refusal 4 refuses there, pump_c",
    ),
    "an ID that is its node's": (
        lambda: declared(w(), [cfx.compartment(cid="ecs_0")]),
        "collides with an ID the world already declares",
    ),
    "an ID that is a cell's": (
        lambda: declared(w(), [cfx.compartment(cid="cell_0")]),
        "collides with an ID the world already declares",
    ),
    "an ID that is a species'": (
        lambda: declared(w(), [cfx.compartment(cid="S")]),
        "collides with an ID the world already declares",
    ),
    "an ID declared twice": (
        lambda: declared(w(), [cfx.compartment(), cfx.compartment(node="nowhere")]),
        "is declared twice",
    ),
    "an empty role": (lambda: declared(w(), [cfx.compartment(role="")]), "a short string"),
    "a role with spaces around it": (
        lambda: declared(w(), [cfx.compartment(role=" lumen")]),
        "a short string",
    ),
    "a role too long": (lambda: declared(w(), [cfx.compartment(role="x" * 41)]), "a short string"),
    "a role that is not a string": (
        lambda: declared(w(), [cfx.compartment(role=5)]),
        "a short string",
    ),
    "a channel population on the bounding patch": (
        channelled,
        "carries an ion route refusal 4 refuses there, leak_0",
    ),
    "a charge anchor": (charged, "nonzero charge anchor"),
    "no held bath in the owner's component": (lambda: closed_world("bath"), "with no held bath"),
    "an empty label": (
        lambda: declared(w(), [cfx.compartment(label=" ")]),
        "null or a non-empty string",
    ),
    "a numeric reference": (
        lambda: declared(w(), [cfx.compartment(reference=5)]),
        "null or a non-empty string",
    ),
}


@pytest.mark.parametrize("name", sorted(REFUSALS))
def test_definition_refusals(name):
    build, message = REFUSALS[name]
    with pytest.raises(ConfigError, match=message):
        parse_spec(build())


def moves_at(spec, node):
    """{(kind, species, law, held terms)} of every kind move at `node` (refusal 4's reading: each
    kind bound to its declaration's structure entry, as the inner model binds it)."""
    out = set()
    for kind_id, declaration in spec.model.kinds:
        kind = adapter.bound_kind(kind_registry.active().lookup(kind_id), declaration)
        for entry in kind.moved_rows(declaration) if kind.moved_rows is not None else ():
            species, at, law = (*entry, None) if len(entry) == 2 else entry
            if at == node:
                out.add((kind_id, species, law, comp.held_terms(kind, law)[0]))
    return out


PROTON_PUMP = "cells.proton_atp_mass_action_positive@1"
NEUTRAL_PUMP = "cells.atp_driven_transporter_mass_action_positive@1"
LEAK, NEUTRAL_ROUTE = "proton_constant_field_leak@1", "passive_neutral_permeation@1"


def test_refusal_4_admits_fr4s_declared_world_move_by_move():
    """Refusal 4, version 1.3 (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4): FR-4's declared world, in
    the composite's form, is admitted as version 1.1 admitted it, now move by move. At the lumen the
    pump (cells.transporter@1) and the leak (cells.passive_routes@1) move the charged proton row,
    each under a law that declares a charge slope its kind holds (stage_term); the K+ permeability
    is @3's own route, admitted because the world declares kinds; B4's buffer is a stage read that
    moves nothing. A permeability in a world without kinds stays refused (REFUSALS), as do pumps
    and channels."""
    from validation.compartment_ph_engine import definitions as defs

    spec = parse_spec(defs.declared_world(defs.fr4_world()))
    bounding = next(p for p in spec.model.membranes if p.id == defs.BOUNDING)
    assert any(v > 0 for v in bounding.permeability_m_per_s)  # The K+ counterion.
    assert {k for k, _ in spec.model.kinds} == {
        "cells.passive_routes@1",
        "cells.rapid_proton_buffer@1",
        "cells.transporter@1",
    }
    assert moves_at(spec, defs.LUMEN) == {
        ("cells.passive_routes@1", "H", LEAK, ("stage_term",)),
        ("cells.transporter@1", "H", PROTON_PUMP, ("stage_term",)),
    }


def fr5_sources(definition):
    """FR-5's routing-door sources (the FR-4/FR-5 note's §16.2) added to a world: the bounding
    patch's damage and the lumen's pH condition."""
    from validation.compartment_ph_engine import definitions as defs

    definition["model"]["patch_damage"] = [dict(
        id="damage_0", patch=defs.BOUNDING, law="bounding_patch_damage@1", initial_damage=0.0,
        injury_rate_per_s=1.0, resealing_rate_per_s=0.05)]
    definition["model"]["ph_conditions"] = [dict(
        id="acid_0", node=defs.LUMEN, law="ph_conditioned_factor@1", ph50=5.5, slope=4.0)]
    return definition


SOURCE_KINDS = ("cells.patch_damage@1", "cells.ph_condition@1")


def test_refusal_4_admits_the_routing_doors_source_kinds_by_their_hooks():
    """Refusal 4 (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.2, version 1.2's ruling of 16 November
    2026, kept by version 1.3's §3.4.4): FR-5's source kinds, cells.patch_damage@1 and
    cells.ph_condition@1, are admitted beside a compartment with FR-4's kinds. Version 1.3 admits
    them as sources by their hooks, not their IDs: they declare no moved rows and none of a mover's
    hooks (test_the_built_in_kinds_hold_the_step_terms_their_laws_declare). Every declared kind is
    still refused under RK4 (the test below)."""
    from validation.compartment_ph_engine import definitions as defs

    spec = parse_spec(fr5_sources(defs.declared_world(defs.fr4_world())))
    assert {k for k, _ in spec.model.kinds} >= set(SOURCE_KINDS)
    assert moves_at(spec, defs.LUMEN) == {
        ("cells.passive_routes@1", "H", LEAK, ("stage_term",)),
        ("cells.transporter@1", "H", PROTON_PUMP, ("stage_term",)),
    }


def charged_start(charge_C=5.757025696278586e-14):
    """An FR-5 start extract with FR-4's steady state's charge split: the lumen +q, the cell -q
    (the engine's 1800 s checkpoint carries q = 5.757e-14 C), FR-4's declared amounts otherwise."""
    from validation.compartment_ph_engine import definitions as defs

    declared = defs.fr4_world()
    nodes = {n["id"]: dict(amounts_fmol=dict(n["initial_amount_fmol"]), charge_C=0.0)
             for n in declared["model"]["cells"] + declared["model"]["extracellular"]}
    nodes[defs.LUMEN]["charge_C"], nodes[defs.CELL]["charge_C"] = charge_C, -charge_C
    return defs.start_extract(producer="engine", nodes=nodes,
                              readouts=dict(pH_c=7.218, pH_L=5.0946, V_b_V=-7.33e-3),
                              time_s=1800.0, dt_s=1e-3, source=dict(kind="test"))


def test_refusal_5_version_1_1_admits_a_charged_start_where_charged_routes_are_admitted():
    """Refusal 5, version 1.1 (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.3; the lead's ruling of 16
    November 2026): a world whose admitted routes charge the lumen must be able to resume from
    its own checkpoint, so FR-5's declared world from FR-4's charged steady state (the lumen +q,
    the cell -q) is admitted with its nonzero anchor. A nonzero anchor stays refused without kinds
    (the silent version, REFUSALS' "a charge anchor") and under RK4 (fails closed)."""
    from validation.compartment_ph_engine import definitions as defs
    from validation.compartment_ph_engine.parameters import ARM_R

    spec = parse_spec(defs.declared_world(defs.fr5_world(ARM_R, start=charged_start())))
    lumen = next(o for o in spec.model.extracellular if o.id == defs.LUMEN)
    assert lumen.initial_charge_C == 5.757025696278586e-14
    assert {k for k, _ in spec.model.kinds} >= set(SOURCE_KINDS)
    # Refusal 5's own rule: version 1.1's branch admits it only with kinds declared and an IMEX
    # tableau (version 1.2's, a route into the compartment, is tested below).
    compartment = type("Node", (), dict(initial_charge_C=1e-17))()
    comp.refuse_charge_anchor("lumen_0", compartment, kinds=True, imex=True)
    for kinds, imex in ((False, True), (True, False), (False, False)):
        with pytest.raises(ConfigError, match="nonzero charge anchor"):
            comp.refuse_charge_anchor("lumen_0", compartment, kinds=kinds, imex=imex)
    neutral = type("Node", (), dict(initial_charge_C=0.0))()
    for kinds, imex in ((False, True), (True, False), (False, False)):
        comp.refuse_charge_anchor("lumen_0", neutral, kinds=kinds, imex=imex)
    # Under RK4, on @3's parsed base: the operator refuses it (refusal 4's RK4 rule first).
    import dataclasses

    base = parse_spec(defs.development_world(defs.fr5_world(ARM_R, start=charged_start())))
    block = defs.fr4_world()["model"]["operators"][0]
    assert comp.parse_declaration(block, base).compartments[0].node == defs.LUMEN
    rk4 = dataclasses.replace(
        base, execution=dataclasses.replace(base.execution, solver=comp.RK4_SOLVER)
    )
    with pytest.raises(ConfigError, match="version 1's refusal stands"):
        comp.parse_declaration(block, rk4)


STIFF_DT = 1e-4  # RK4's largest step (surface_tissue.check_steps).
STIFF_STEPS = 20


def stiff_fr4(solver=None, *, operator=True):
    """FR-4's world at STIFF_DT with its bounding patch's K+ permeability scaled 1e4: the lumen's
    row at about 2.5e5 1/s, so dt x rate = 25 (the core's review of refusal 4 version 1.1). The
    declared world (the composite with FR-1's operator), or the development world without it."""
    from validation.compartment_ph_engine import definitions as defs

    world = defs.declared_world if operator else defs.development_world
    raw = world(defs.fr4_world())
    end = STIFF_STEPS * STIFF_DT
    raw["execution"].update(dt=STIFF_DT, max_steps=2 * STIFF_STEPS)
    if solver is not None:
        raw["execution"]["solver"] = solver
    raw["experiment"].update(end_time=end, observation_times=[0.0, end])
    patch(raw, defs.BOUNDING)["permeability_m_per_s"]["K"] *= 1e4
    return raw


def test_refusal_4_admits_routes_beside_a_compartment_only_with_an_imex_tableau():
    """Refusal 4, version 1.1, admits kinds and @3's permeability on a bounding patch only with an
    IMEX tableau (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.1; the core's review): an RK4 step runs
    neither the per-stage rule nor B7's and the kinds' definition-time terms. The review's probe:
    FR-4's declared world with the stiff K+ permeability is admitted under IMEX, whose step checks
    then refuse it as before, and refused under RK4, where it used to pass its step checks. @3
    now refuses declared kinds under RK4 first (surface_pump_v3._check_kinds_solver), so the
    operator's own rule is checked on @3's parsed base, which reaches it under either solver."""
    import dataclasses

    import numpy as np

    from validation.compartment_ph_engine import definitions as defs

    spec = parse_spec(stiff_fr4())  # FR-4's own IMEX solver.
    assert spec.execution.solver != comp.RK4_SOLVER
    with pytest.raises(ConfigError, match="IMEX step exceeds the explicit-rate stability bound"):
        get_model(spec.model).bind_step_checks(spec)(np.full(STIFF_STEPS, STIFF_DT))
    refusal = re.escape("cells.transporter@1) require an IMEX solver")
    with pytest.raises(ConfigError, match=refusal):
        parse_spec(stiff_fr4(comp.RK4_SOLVER))  # @3's refusal, ahead of the operator's.
    # The operator's own rule, on @3's parsed base under each solver.
    base = parse_spec(stiff_fr4(operator=False))
    block = defs.fr4_world()["model"]["operators"][0]
    assert comp.parse_declaration(block, base).compartments[0].node == defs.LUMEN
    rk4 = dataclasses.replace(
        base, execution=dataclasses.replace(base.execution, solver=comp.RK4_SOLVER)
    )
    with pytest.raises(ConfigError, match="version 1's refusal stands"):
        comp.parse_declaration(block, rk4)
    # The routing door's source kinds alone open nothing under RK4 (fails closed).
    sources_only = stiff_fr4(operator=False)
    for key in ("transporters", "passive_routes", "stage_reads"):
        sources_only["model"].pop(key)
    base = parse_spec(fr5_sources(sources_only))
    assert {k for k, _ in base.model.kinds} == set(SOURCE_KINDS)
    assert comp.parse_declaration(block, base).compartments[0].node == defs.LUMEN
    rk4 = dataclasses.replace(
        base, execution=dataclasses.replace(base.execution, solver=comp.RK4_SOLVER)
    )
    with pytest.raises(ConfigError, match="version 1's refusal stands"):
        comp.parse_declaration(block, rk4)


def test_the_built_in_kinds_hold_the_step_terms_their_laws_declare():
    """Version 1.3's premise (§3.4.4; §3.4.1's wording after the core's review, finding 4): each
    built-in law a kind moves rows under declares, in the law registry, the step terms its kind
    holds. The declarations are seam F's (CORE_SEAMS §18 as amended): the pump's proton law and
    the leak (laws/transport/proton_leak) declare a charge slope (stage_term, the per-stage
    rule's), the passive neutral law (laws/routes/passive_permeation) a material bound
    (material_bound, through the kind's bound_rate: dt L <= 1). The transporter's neutral law
    declares none, version 1.1's open item, so a move of it at a compartment's node is refused
    (the test below). The buffer is a stage read and the routing door's two kinds are sources,
    by their hooks. Refusal 4 reads exactly the template's step terms (registry/laws.STEP_TERMS),
    each mapped to a hook. If a declaration or a hook goes, or the template gains a term refusal
    4 does not map, its admission loses its premise and this fails."""
    laws = law_registry.active()
    kinds = kind_registry.active()
    assert tuple(comp.TERM_HOOKS) == law_registry.STEP_TERMS
    pump, routes = kinds.lookup("cells.transporter@1"), kinds.lookup("cells.passive_routes@1")
    held = {
        law.law_id: comp.held_terms(kind, law.law_id)[0]
        for kind, interface in ((pump, law_registry.CYCLE_LAW), (routes, law_registry.ROUTE_LAW))
        for law in laws.laws(interface, kind.kind_id)
    }
    assert held == {
        PROTON_PUMP: ("stage_term",),
        NEUTRAL_PUMP: (),
        LEAK: ("stage_term",),
        "proton_constant_field_leak@2": ("stage_term",),  # MT-1b's leak reading the closure: @1's.
        NEUTRAL_ROUTE: ("material_bound",),
        "inward_rectifier_linear_driving_force@1": ("stage_term",),  # The rectifier (RECTIFIER).
        "passive_constant_field_permeation@1": ("stage_term", "material_term"),  # FR-15 P2.
        # Declares no step term: refused at a compartment's node (fail-closed).
        "cells.na_anion_symport_factored@1": (),
        "cells.na2_anion_symport_diagram@1": (),  # Version 2: likewise, no step term.
        "cells.sodium_calcium_exchange_symmetric_barrier@1": (),  # Likewise: refused there.
        "cells.atp_driven_transporter_mass_action_positive@2": (),  # Likewise: none yet.
        "cells.na_k_2anion_symport_reversible_tanh@1": (),  # Likewise, and no charge to slope.
        "cells.electroneutral_symport_reversible_tanh@1": (),  # Likewise.
        # The mitochondrion's inner-membrane laws: likewise.
        **dict.fromkeys(
            (
                "cells.nadh_ubiquinone_proton_cycle@1",
                "cells.ubiquinol_cytochrome_c_proton_cycle@1",
                "cells.cytochrome_c_oxygen_proton_cycle@1",
                "cells.proton_coupled_atp_synthesis_cycle@1",
                "cells.electrogenic_nucleotide_exchange@1",
                "cells.phosphate_proton_symport@1",
                "cells.potassium_proton_exchange@1",
                "cells.held_reductant_supply@1",  # The matrix's NADH supply: likewise.
                "cells.adenylate_kinase@1",  # The intermembrane space's kinase: likewise.
            ),
            (),
        ),
    }
    assert comp.held_terms(pump, NEUTRAL_PUMP)[1] == "declares no step term"
    from validation.compartment_ph_engine import definitions as defs

    spec = parse_spec(fr5_sources(defs.declared_world(defs.fr4_world())))
    declared = dict(spec.model.kinds)
    for kind_id in ("cells.rapid_proton_buffer@1", *SOURCE_KINDS):
        kind = kinds.lookup(kind_id)
        assert kind.moved_rows is None, kind_id
        # Admitted by its hooks alone, read on the kind bound to its declared entry.
        comp.refuse_kind_moves(spec.model, defs.LUMEN, kind_id, declared[kind_id])
    assert kinds.lookup("cells.rapid_proton_buffer@1").stage_read is not None
    assert all(kinds.lookup(k).stage_read is None for k in SOURCE_KINDS)


@dataclass(frozen=True)
class PlantedLaw(law_registry.Law):
    """A planted law under its own tests. interface (never registered on BUILTIN): the step-term
    fields the cycle and route law types declare (registry/laws.STEP_TERMS;
    docs/CORE_SEAMS_DESIGN.md §8.1), each a kernel's name or None, as refusal 4 version 1.3 reads
    them."""

    stage_term: str | None = None
    material_term: str | None = None
    charge_bound: str | None = None
    material_bound: str | None = None

    interface: ClassVar[str] = "tests.planted_law@1"


PLANTED_LAW = "tests.planted_move@1"


def no_slope(read, potentials, control, p, *, xp):
    """A planted per-stage term (cells, then outside nodes): zero."""
    return xp.zeros(p.active.size + p.outside_active.size)


def no_bound(spec, declaration):
    """A planted definition-time bound (1/s): zero."""
    return 0.0


def carrier_under(law, **hooks):
    """kind_fixtures' carrier (tests.carrier@1: a declared species carried across one membrane
    patch) with its moved rows naming `law`, or naming none when `law` is None, and `hooks`."""
    carrier = kind_fixtures.carrier()
    if law is None:
        return dataclasses.replace(carrier, **hooks)
    rows = carrier.moved_rows
    named = lambda declaration: tuple((*row, law) for row in rows(declaration))  # noqa: E731
    return dataclasses.replace(carrier, moved_rows=named, **hooks)


def carried(kind, *laws, species="K", membrane=cfx.PATCH):
    """W with `kind` carrying `species` across `membrane` (the bounding patch by default), parsed
    with the planted `laws` registered and `kind` in the kind registry."""
    raw = kind_fixtures.declare_carrier(w(), species=species, membrane=membrane)
    with law_registry.scope(law_registry.BUILTIN.extended(*laws)):
        with kind_registry.scope(kind_fixtures.registry(kind)):
            return parse_spec(raw)


# name: (species carried, the law's declared terms, the kind's hooks, refusal or None). Each
# refusal is its admitted twin's planted error, which version 1.3 must catch (D187).
PLANTED_MOVES = {
    "a charged row held by its charge slope": ("K", dict(stage_term="slope"), {}, None),
    "a charged row whose law declares no term": ("K", {}, {}, "declares no step term"),
    "a charged row held only by material terms": (
        "K",
        dict(material_term="slope", material_bound="bound"),
        dict(material_term=no_slope, bound_rate=no_bound),
        "a charge slope",
    ),
    "a charged row held only by its charge bound": (
        "K",
        dict(charge_bound="bound"),
        dict(stage_term=None, bound_rate=no_bound),
        "a charge slope",
    ),
    "a charged row whose kind lacks the slope its law declares": (
        "K",
        dict(stage_term="slope"),
        dict(stage_term=None),
        "of which its kind holds none",
    ),
    "a neutral row held by its material slope": (
        "S",
        dict(material_term="slope"),
        dict(material_term=no_slope),
        None,
    ),
    "a neutral row held by its material bound": (
        "S",
        dict(material_bound="bound"),
        dict(bound_rate=no_bound),
        None,
    ),
    "a neutral row whose law declares no term": (
        "S",
        {},
        dict(material_term=no_slope, bound_rate=no_bound),
        "declares no step term",
    ),
    "a neutral row held only by a charge slope": (
        "S",
        dict(stage_term="slope"),
        {},
        "a material slope",
    ),
    "a neutral row held only by a charge bound": (
        "S",
        dict(charge_bound="bound"),
        dict(bound_rate=no_bound),
        "a material slope",
    ),
    "a neutral row whose kind lacks the bound its law declares": (
        "S",
        dict(material_bound="bound"),
        {},
        "of which its kind holds none",
    ),
}


@pytest.mark.parametrize("name", sorted(PLANTED_MOVES))
def test_a_move_at_the_compartments_node_needs_a_term_its_law_declares(name):
    """Refusal 4, version 1.3 (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.4; docs/CORE_SEAMS_DESIGN.md
    §4.4): a planted kind moves a row across the bounding patch, so at the compartment's node,
    under a planted law. A charged row is admitted only by a charge slope (stage_term), a neutral
    row by a material slope (material_term) or a definition-time material bound (material_bound),
    each declared by the law and held by the kind's hook that supplies it (bound_rate for the
    bounds); a charge bound alone holds neither (§18 as amended splits the bound). Otherwise the
    move is refused, naming the law."""
    species, terms, hooks, refusal = PLANTED_MOVES[name]
    hooks = dict(dict(stage_term=no_slope), **hooks)  # The carrier has no slope of its own.
    kind = carrier_under(PLANTED_LAW, **hooks)
    law = PlantedLaw(PLANTED_LAW, host=kind_fixtures.CARRIER_ID, **terms)
    if refusal is None:
        spec = carried(kind, law, species=species)
        held = comp.held_terms(kind, PLANTED_LAW)[0]
        assert moves_at_planted(spec, kind, cfx.NODE) == {(species, PLANTED_LAW, held)}
    else:
        under = rf"moves the (charged|neutral) row {species} at its node under {PLANTED_LAW}, "
        with pytest.raises(ConfigError, match=under + rf"which .*{refusal}"):
            carried(kind, law, species=species)


def moves_at_planted(spec, kind, node):
    """{(species, law, held terms)} of the planted kind's moves at `node`, the kind bound to its
    declaration's entry as refusal 4 reads it."""
    declaration = dict(spec.model.kinds)[kind_fixtures.CARRIER_ID]
    kind = adapter.bound_kind(kind, declaration)
    return {
        (species, law, comp.held_terms(kind, law)[0])
        for species, at, law in kind.moved_rows(declaration)
        if at == node
    }


def test_refusal_4_judges_the_moves_at_the_compartments_node_and_names_no_kind():
    """Version 1.3 has no list of kinds: a kind none of whose moves is at a compartment's node is
    not refusal 4's, whatever its ID. kind_fixtures' carrier, whose rows name no law, is admitted
    carrying K across the owner's wall (cell to bath), where version 1.2 refused it as a kind it did
    not know; across the bounding patch the same kind is refused, its move at the node naming no
    law (fails closed)."""
    kind = carrier_under(None)
    spec = carried(kind, membrane=cfx.WALL)
    assert {k for k, _ in spec.model.kinds} == {kind_fixtures.CARRIER_ID}
    with pytest.raises(ConfigError, match=r"row K at its node under no law, which names no law"):
        carried(kind)


def test_a_moves_law_is_read_by_its_id_from_the_kind_that_hosts_it():
    """Version 1.3 reads a move's law in the law registry by its ID: an unregistered law ID has no
    terms, and neither has a registered law that another kind hosts, since only its host's hooks
    hold its terms (both fail closed). The admitted twin is the first planted case above."""
    kind = carrier_under(PLANTED_LAW, stage_term=no_slope)
    with pytest.raises(ConfigError, match=rf"under {PLANTED_LAW}, which is not a registered law"):
        carried(kind)
    foreign = PlantedLaw(PLANTED_LAW, host=kind_fixtures.KIND_ID, stage_term="slope")
    with pytest.raises(ConfigError, match=rf"is hosted by {kind_fixtures.KIND_ID}"):
        carried(kind, foreign)


def test_a_kind_that_reuses_a_laws_id_is_held_by_its_own_hooks():
    """CORE_SEAMS_STEP0 §3.2's note: a planted variant that reuses a law's ID, as FR-4's K2 does
    (validation/compartment_ph_engine/planted.py: the transporter with its rates and stage term
    replaced), is admitted on the law's declaration only where it keeps the hook the law names.
    K2's reversed pump keeps its stage_term, so FR-4's declared world is admitted with it; the same
    kind with its stage_term removed is refused at the lumen."""
    from validation.compartment_ph_engine import definitions as defs
    from validation.compartment_ph_engine import planted

    raw = defs.declared_world(defs.fr4_world())
    reversed_pump = planted.reversed_pump()
    with kind_registry.scope(planted.registry(reversed_pump)):
        parse_spec(raw)
    unsloped = dataclasses.replace(reversed_pump, stage_term=None)
    with kind_registry.scope(planted.registry(unsloped)):
        with pytest.raises(ConfigError, match=rf"under {PROTON_PUMP}, which declares stage_term, "
                           "of which its kind holds none"):
            parse_spec(raw)


def test_refusal_4_reads_the_kind_bound_to_its_entry(monkeypatch):
    """The bound-kind sweep (CORE_SEAMS §18; the operators brief's item 2, 19 November 2026):
    refusal 4 reads each kind bound to its declaration's structure entry
    (pump_composite_adapter.bound_kind), whose hooks the step runs, never the static kind's, which
    may differ per entry: a static read could admit what the bound kind refuses (fail-open).
    Planted: in FR-4's declared world the transporter's bound kind loses its stage_term while its
    static kind keeps it. The static read would still admit the proton move at the lumen; the bound
    read refuses it, naming the law."""
    from validation.compartment_ph_engine import definitions as defs

    spec = parse_spec(defs.declared_world(defs.fr4_world()))
    pump = "cells.transporter@1"
    declaration = dict(spec.model.kinds)[pump]
    comp.refuse_kind_moves(spec.model, defs.LUMEN, pump, declaration)  # Admitted, unplanted.
    real = kind_registry.bound

    def stripped(kind, entry):
        out = real(kind, entry)
        if kind_registry.qualified(out.kind_id) != pump:
            return out
        return dataclasses.replace(out, stage_term=None)

    monkeypatch.setattr(kind_registry, "bound", stripped)
    assert kind_registry.active().lookup(pump).stage_term is not None  # The static kind keeps it.
    with pytest.raises(
        ConfigError,
        match=rf"under {PROTON_PUMP}, which declares stage_term, of which its kind holds none",
    ):
        comp.refuse_kind_moves(spec.model, defs.LUMEN, pump, declaration)
    assert moves_at(spec, defs.LUMEN) == {
        ("cells.passive_routes@1", "H", LEAK, ("stage_term",)),
        (pump, "H", PROTON_PUMP, ()),
    }


def test_a_hook_its_entry_does_not_have_holds_no_move():
    """F's per-entry hooks (KindFields.without, 487710c6): a kind's declared_fields may leave a hook
    out of an entry, which binding sets to None, so the entry's programs never run it. Refusal 4
    reads the bound kind, so a move whose law declares that hook's term is refused for such an
    entry, though the static kind has the hook. Planted: the carrier of the first planted case
    (admitted there), its entry without its stage_term."""
    carrier = carrier_under(PLANTED_LAW, stage_term=no_slope)
    entry = kind_registry.KindFields(
        carrier.state_axes,
        carrier.layout_fields,
        carrier.control_fields,
        carrier.readout_columns,
        without=("stage_term",),
    )
    kind = dataclasses.replace(carrier, declared_fields=lambda structure: entry)
    assert kind.stage_term is not None  # The static kind holds the slope.
    law = PlantedLaw(PLANTED_LAW, host=kind_fixtures.CARRIER_ID, stage_term="slope")
    with pytest.raises(
        ConfigError, match=rf"under {PLANTED_LAW}, which declares stage_term, of which its kind "
        "holds none"
    ):
        carried(kind, law)


def planted_kind(kind_id, **hooks):
    return kind_registry.Kind(kind_id=kind_id, model_key=kind_id.rsplit(".", 1)[1], **hooks)


def hook(*args, **kwargs):
    return None


NON_MOVERS = {
    "a stage read": (dict(stage_read=hook, stage_rows=hook, ledger_terms=hook), None),
    "a stage read with rates": (dict(stage_read=hook, stage_rows=hook, rates=hook), "has rates"),
    "a stage read with a charge slope": (
        dict(stage_read=hook, stage_rows=hook, stage_term=hook),
        "has stage_term",
    ),
    "a stage read without its rows": (
        dict(stage_read=hook),
        "declares no stage_rows for its stage read",
    ),
    "a source": (dict(rates=hook, book=hook, domain=hook, factors=hook), None),
    "a source with ledger terms": (dict(rates=hook, ledger_terms=hook), "has ledger_terms"),
    "a source with held rows": (dict(rates=hook, held_rows=hook), "has held_rows"),
    "a source with a material slope": (dict(rates=hook, material_term=hook), "has material_term"),
}


@pytest.mark.parametrize("name", sorted(NON_MOVERS))
def test_a_kind_without_moved_rows_is_a_stage_read_or_a_source(name):
    """Version 1.3 places a kind that declares no moved rows by its hooks, never its ID: a stage
    read declares its rows and has no rates, moves or slope (B4's buffer); a source has none of a
    mover's hooks (FR-5's damage and pH condition, version 1.2's ruling). Anything else fails
    closed, naming what it has. The planted kinds are checked directly (@3 itself refuses a stage
    read without its rows, ahead of the operator)."""
    hooks, refusal = NON_MOVERS[name]
    planted = planted_kind("tests.non_mover@1", **hooks)
    registry = kind_registry.KindRegistry()
    registry.register(planted)
    with kind_registry.scope(registry):
        if refusal is None:
            comp.refuse_kind_moves(None, cfx.NODE, planted.kind_id, ())
        else:
            with pytest.raises(ConfigError, match=rf"declares no moved rows.*it .*{refusal}"):
                comp.refuse_kind_moves(None, cfx.NODE, planted.kind_id, ())


def neutral_pump(raw, patch, *, alone):
    """FR-5's world with a population of the transporter's neutral law carrying its cargo X on
    `patch`, on the pump's held fuel: alone on the patch (in place of the proton pump) or beside
    it."""
    raw = copy.deepcopy(raw)
    pumps = raw["model"]["transporters"]
    entry = copy.deepcopy(pumps[0])
    entry.update(id="cargo_pump_0", patch=patch, law=NEUTRAL_PUMP, role="X", stoichiometry=1)
    entry["fuel"].update(ph_ref=None, ph_band=None)  # The neutral law names no proton row.
    pumps[:] = [entry] if alone else [*pumps, entry]
    return raw


def test_the_transporters_neutral_law_has_no_term_at_a_compartments_node():
    """Version 1.1's open item (§3.4.1), closed by version 1.3 (§3.4.4): the transporter's
    neutral law declares no step term, so nothing bounds its material stiffness at a small node.
    Version 1.2 admitted it on the bounding patch as one of a known kind's laws; version 1.3
    refuses it there, naming the law, until it declares D4's material term. On the owner's plasma
    patch (cell to bath) the same population is not refusal 4's, and FR-5's world is admitted
    with it. CORE_SEAMS_STEP0 §3 found no saved or registered world with this law beside a
    compartment."""
    from validation.compartment_ph_engine import definitions as defs
    from validation.compartment_ph_engine.parameters import ARM_T

    raw = defs.declared_world(defs.fr5_world(ARM_T))
    with pytest.raises(ConfigError, match=rf"the neutral row X at its node under {NEUTRAL_PUMP}, "
                       "which declares no step term"):
        parse_spec(neutral_pump(raw, defs.BOUNDING, alone=True))
    spec = parse_spec(neutral_pump(raw, defs.PLASMA, alone=False))
    pumps = dict(spec.model.kinds)["cells.transporter@1"]
    assert [(t.patch, t.law) for t in pumps] == [
        (defs.BOUNDING, PROTON_PUMP),
        (defs.PLASMA, NEUTRAL_PUMP),
    ]


def test_refusal_4s_premise_the_stage_rule_holds_a_permeability_at_the_compartments_node(
    monkeypatch,
):
    """Refusal 4's premise (§3.4.1; the core's review, finding 3): with kinds declared, @3's
    per-stage rule (surface_pump_v3.membrane_rate) counts @3's own constant-field permeability at
    the compartment's free node, so an IMEX step at dt G_b / C_b > 1 is refused there. FR-4's world
    with its K+ permeability scaled k, at its own 1 ms: at k = 60 the lumen's row from the K+ route
    alone is about 1.5 / dt while the owner's whole row stays under 1 / dt (the cells-only rate
    would have passed the step), and the step is refused by the stage bound; at k = 20 (about 0.5)
    it is accepted. The declared world (with the operator) is admitted at both."""
    import numpy as np

    from cells.definitions.surface_pump_v3_spec import control_values
    from cells.laws.electrochemistry import F, R
    from cells.models import surface_pump_v3
    from validation.compartment_ph_engine import definitions as defs

    def scaled(k, world):
        raw = world(defs.fr4_world())
        patch(raw, defs.BOUNDING)["permeability_m_per_s"]["K"] *= k
        return raw

    for k, accepted in ((20, True), (60, False)):
        parse_spec(scaled(k, defs.declared_world))  # Refusal 4 admits it (kinds, IMEX).
        spec = parse_spec(scaled(k, defs.development_world))  # The same @3 world and kinds.
        impl = get_model(spec.model)
        state, p = impl.initial_values(spec)
        control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
        dt = spec.execution.dt
        b = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
        cell, node = int(p.membrane_cell[b]), int(p.membrane_outside[b])
        assert bool(surface_pump_v3.free_outside_nodes(p, xp=np)[node])  # The lumen is free.
        row = spec.model.species_ids.index("K")
        c_in = p.amount_reference[row, cell] / p.volume[cell]
        c_out = p.extracellular_amount_reference[row, node] / p.extracellular_volume[node]
        slope = F * F / (R * spec.model.temperature_K)  # @3's constant-field slope factor.
        g_k = slope * p.membrane_permeability[row, b] * max(c_in, c_out) * p.membrane_area[b]
        node_rate = g_k / p.membrane_capacitance[b]  # The K+ route alone, at the lumen (1/s).
        assert (dt * node_rate > 1.0) == (not accepted), (k, dt * node_rate)
        rate = float(impl.membrane_rate(state, control, p, xp=np))
        cells_only = float(surface_pump_v3.membrane_rate(state, control, p, xp=np))
        assert rate >= node_rate and dt * cells_only < 1.0, (k, rate, cells_only)
        _, valid = impl.imex_step(state, dt, control, p, xp=np)
        assert bool(valid) == accepted, (k, dt * rate)
        if not accepted:  # The stage bound is what refuses it.
            monkeypatch.setattr(surface_pump_v3, "EXPLICIT_STEP_BOUND", np.inf)
            assert bool(impl.imex_step(state, dt, control, p, xp=np)[1])
            monkeypatch.undo()


def replaced(events):
    raw = two_cells(
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_1", "ecs_1")),
        faces=(("face_1", "ecs_1", "bath", 1e-10, 1e-5),),
        junctions=(("junction_0", "cell_0", "cell_1"),),
    )
    template = fx.template(raw, "cell_1", "T", s_mM=1e-3)
    raw = fx.with_replacement(raw, [template], events)
    return cfx.with_compartments(raw, [cfx.compartment()])


def test_replacement_composes_away_from_owners_and_never_on_or_from_one():
    parse_spec(replaced([(0.005, "cell_1", "T", "c1_new")]))
    with pytest.raises(ConfigError, match="schedules an event on 'cell_0'"):
        parse_spec(replaced([(0.005, "cell_0", "T", "c0_new")]))
    with pytest.raises(ConfigError, match="names 'cell_0', which owns a compartment, as a donor"):
        parse_spec(replaced([(0.005, "cell_1", None, "c1_new", "cell_0")]))


# Admitted laws whose modules have not landed: none. FR-2's law was admitted before its module
# (the lead's ruling of 19 November 2026), and its entry went with that landing; a law listed here
# fails the test below once it registers.
PENDING_ADMITTED = frozenset()
ADMITTED_AT_IMPORT = comp.ADMITTED  # The module's list, before any fixture patches it.


def test_the_admitted_list_fails_closed(monkeypatch):
    class Newcomer(Operator):
        LAW_ID = "a_future_operator@1"
        EVENT = True

    monkeypatch.setitem(OPERATORS, Newcomer.LAW_ID, Newcomer())
    spec = parse_spec(w())
    model = SimpleNamespace(operators=(*spec.model.operators, SimpleNamespace(law=Newcomer.LAW_ID)))
    experiment = SimpleNamespace(operators=(*spec.experiment.operators, SimpleNamespace(data=())))
    fake = SimpleNamespace(model=model, experiment=experiment)
    with pytest.raises(ConfigError, match="a_future_operator@1 is not on its admitted list"):
        comp.check_definition(fake, spec.model.operators[-1])
    assert comp.TRAFFICKING_LAW in OPERATORS  # FR-2's law, registered with its module.
    assert set(comp.ADMITTED) - set(OPERATORS) == PENDING_ADMITTED, "a pending law registered"


# ------------------------------------------------------------------ the membrane-state wall's door

STAND_IN = "trafficking_stand_in@1"


@dataclass(frozen=True)
class StandInRoutes:
    law: str
    compartments: tuple  # The compartment IDs its routes enter.


class TraffickingStandIn(Operator):
    """A stand-in for FR-2's scheduled_membrane_trafficking@1 until its module lands (FR-2's own
    tests are its builder's): an idle event part, membrane state and the compartments before it,
    and routes that name the compartments they enter. It has a law ID of its own, which the
    `trafficking` fixture puts in the compartments' place for trafficking, so no composition cached
    for FR-2's law is ever built from it."""

    LAW_ID = STAND_IN
    EVENT = True
    REQUIRES = (comp.STATE_LAW, LAW)

    def parse(self, raw, base, inner_model):
        return StandInRoutes(raw["law"], tuple(raw["compartments"]))

    def to_dict(self, declaration, base):
        return dict(law=declaration.law, compartments=list(declaration.compartments))

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return {}, {}

    def event(self, state, control, p, *, xp):
        return state, xp.asarray(True)

    def charged_compartments(self, spec, declaration):
        return declaration.compartments  # Its routes charge the pools they enter (R2).


@pytest.fixture
def trafficking(monkeypatch):
    """The stand-in registered, admitted, and in the compartments' place for trafficking."""
    assert check_declarations(TraffickingStandIn) is TraffickingStandIn
    monkeypatch.setitem(OPERATORS, STAND_IN, TraffickingStandIn())
    monkeypatch.setattr(comp, "TRAFFICKING_LAW", STAND_IN)
    monkeypatch.setattr(comp, "ADMITTED", (*comp.ADMITTED, STAND_IN))
    return STAND_IN


def stateful(*, routes=None, compartments=None):
    """A face-free compartment world without exchange (whose own fixed read of the areas refuses
    membrane state first): membrane state, the compartments declaration (W's compartment, or
    `compartments`) and, given `routes`, the stand-in with routes into those compartment IDs."""
    raw = fx.face_free(end=END)
    raw["model"]["operators"].append(dict(law=comp.STATE_LAW, populations=[]))
    raw = cfx.with_compartments(raw, compartments or [cfx.compartment()])
    if routes is not None:
        raw["model"]["operators"].append(dict(law=STAND_IN, compartments=list(routes)))
    return raw


def test_membrane_state_beside_a_compartment_only_with_trafficking(trafficking):
    """The membrane-state wall's door (docs/CLOSED_COMPARTMENT_DESIGN.md §4; FR-2's question 11,
    the lead's ruling of 19 November 2026): the areas and capacitances are reference reads, so the
    structure check admits membrane state beside a compartment (STRUCTURE_ADMITTED), and the
    definition admits it only together with trafficking, the one writer of them on the admitted
    list. Planted: the same world without trafficking is refused, with the reason. FR-2's law ID is
    on the list, beside membrane state's."""
    spec = parse_spec(stateful(routes=["lys_0"]))
    assert [d.law for d in spec.model.operators] == [comp.STATE_LAW, LAW, trafficking]
    refusal = rf"admits {comp.STATE_LAW} only together with {STAND_IN}"
    with pytest.raises(ConfigError, match=refusal):
        parse_spec(stateful())
    assert {comp.STATE_LAW, "scheduled_membrane_trafficking@1"} <= set(ADMITTED_AT_IMPORT)


# ------------------------------------------------------------------ FR-49: the labels beside it

LABELS_REFUSAL = rf"{comp.LABELS_LAW} beside a compartment is qualified without {comp.STATE_LAW}"


def labelled(raw, species=fx.SPECIES):
    """raw with neutral_arrival_labels@1 on `species` (two labels, no arrivals), declared last."""
    out = copy.deepcopy(raw)
    out["model"]["operators"].append(
        dict(law=comp.LABELS_LAW, species=[dict(id=species, labels=["base", "x"], initial=[])])
    )
    out["experiment"]["label_arrivals"] = []
    return out


LABELS_BESIDE = {
    "a loaded compartment, S labelled": (lambda: labelled(w()), None),
    "with turnover inside": (
        lambda: labelled(cfx.loaded_compartment(end=END, turnover=True)),
        None,
    ),
    "beside membrane state with no writer": (lambda: labelled(stateful()), LABELS_REFUSAL),
    # The wall passes here (the producer writes units); the explicit check refuses first.
    "beside membrane state and the unit producer": (
        lambda: labelled(producing(), species=ufx.TEMPLATE),
        LABELS_REFUSAL,
    ),
}


@pytest.mark.parametrize("name", sorted(LABELS_BESIDE))
def test_labels_beside_a_compartment(name):
    """FR-49's labels entry (validation/fr49/REGISTRATION.md, Part H; ruling 4): the list names
    neutral_arrival_labels@1, and a compartment world that also declares membrane state is refused
    by name, before the membrane-state wall's own rule. Host only: a parse, no compile."""
    build, words = LABELS_BESIDE[name]
    if words is None:
        spec = parse_spec(build())
        assert comp.LABELS_LAW in [d.law for d in spec.model.operators]
        return
    with pytest.raises(ConfigError, match=words):
        parse_spec(build())


def test_labels_beside_membrane_state_the_explicit_check_names_the_reason(monkeypatch):
    """The plant (Part H): without the explicit check, the same world is refused by the
    membrane-state wall's rule instead, so the labels' reason comes from the check alone."""
    monkeypatch.setattr(comp, "refuse_labels_beside_membrane_state", lambda entries: None)
    with pytest.raises(ConfigError, match=rf"admits {comp.STATE_LAW} only together with"):
        parse_spec(labelled(stateful()))


# ------------------------------------------------------------------ FR-7's releasing compartment

PRODUCER, EXCHANGE = "population_unit_turnover@1", "scheduled_species_exchange@1"
KAPPA = 0.5  # 1/s: the release's rate constant out of the compartment, synthetic.


def producing(*, release=True):
    """FR-7's U2 world in miniature (validation/fr7/unit_turnover_fixtures): the unit producer on
    kir_0 with species_regulated_availability@2 routing the template onto its assembly rate, a
    compartment of the cell holding template, and with `release` an exchange import releasing it
    into the cell at KAPPA."""
    raw = ufx.with_producer(
        ufx.cell(end=END), [ufx.route("kir_units", "kir_0")], {"kir_units": [(0.0, 0.02, 0.01)]}
    )
    raw = ufx.with_compartment(ufx.with_template_route(raw), amounts_fmol={ufx.TEMPLATE: 1e-5})
    if release:
        raw = ufx.with_release(raw, [(0.0, ufx.release_velocity(KAPPA))])
    return raw


def entry(law, writes=()):
    """An entry of the composite's (operator, declaration, schedule) list for the wall's rule."""
    return SimpleNamespace(LAW_ID=law, ENTITY_WRITES=dict.fromkeys(writes, ())), None, ()


def test_the_unit_producer_and_coupling_v2_compose_beside_a_compartment():
    """The lead's rulings of 20 November 2026 (FR-7's U2 world with a releasing compartment,
    D217): the producer and the coupling's version 2 are on the admitted list, and the wall's door
    admits membrane state beside a compartment when its only writers are trafficking or the
    producer, which writes units only. Planted: membrane state with no admitted writer, and a
    third writer of its fields beside the producer, each refused with its reason."""
    for release in (False, True):
        spec = parse_spec(producing(release=release))
        laws = [d.law for d in spec.model.operators]
        assert laws[:4] == [comp.STATE_LAW, "species_regulated_availability@2", PRODUCER, LAW]
        assert (EXCHANGE in laws) is release
    assert {PRODUCER, "species_regulated_availability@2"} <= set(ADMITTED_AT_IMPORT)
    units = "population_abundance_increment"
    comp.refuse_unwritten_state([entry(comp.STATE_LAW), entry(PRODUCER, [units])])
    with pytest.raises(ConfigError, match=rf"only together with {comp.TRAFFICKING_LAW} or"):
        comp.refuse_unwritten_state([entry(comp.STATE_LAW), entry(LAW)])
    for field in comp.STATE_FIELDS:
        writers = [entry(comp.STATE_LAW), entry(PRODUCER, [field]), entry("a_writer@1", [field])]
        with pytest.raises(ConfigError, match=rf"a_writer@1 writes its {field} \(fails closed\)"):
            comp.refuse_unwritten_state(writers)
        comp.refuse_unwritten_state(writers[:2])


def test_exchange_reads_the_current_area_beside_membrane_state():
    """D191's current-area read (the lead's ruling of 20 November 2026): beside membrane state,
    which provides the areas, exchange is a door S view reader and its import takes the view's
    area at the half-step; at a zero increment that is the declared area, so the half-step is
    bitwise the declared-area one, and a doubled area doubles the rate constant. With no provider
    (W) it receives no view (C1). Planted: a second patch joining a route's cell and node is
    refused where a provider is composed, and admitted without one."""
    spec = parse_spec(producing())
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    exchange = next(op for op in model.operators if op.LAW_ID == EXCHANGE)
    assert exchange in model.view_readers
    assert not get_model(parse_spec(w()).model).view_readers
    control = SimpleNamespace(
        exchange_rate=np.array([ufx.release_velocity(KAPPA)]), exchange_saturation_mM=np.zeros(1)
    )
    h = 0.5e-3
    viewed, ok = model._half_step(exchange, state, h, control, p, xp=np)
    declared, ok_declared = exchange.half_step(state, h, control, p, xp=np)
    assert ok and ok_declared
    for name, a, b in zip(type(state)._fields, viewed, declared, strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), name
    species = list(spec.model.species_ids).index(ufx.TEMPLATE)
    node = [o.id for o in spec.model.extracellular].index(ufx.NODE)
    held = float(np.asarray(p.extracellular_amount_reference)[species, node])
    slot = [m.id for m in spec.model.membranes].index(ufx.BOUNDING)
    increment = np.zeros_like(np.asarray(state.membrane_area_increment_m2))
    increment[slot] = np.asarray(p.membrane_area)[slot]  # The bounding patch at twice its area.
    doubled, ok = model._half_step(
        exchange, state._replace(membrane_area_increment_m2=increment), h, control, p, xp=np
    )
    moved = -float(np.asarray(doubled.exchange_moved_fmol)[0])
    assert ok and abs(moved - held * -np.expm1(-2 * KAPPA * h)) <= 1e-14 * moved
    twin = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0),),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_0", "ecs_0")),
        faces=(("face_0", "ecs_0", "bath", 1e-10, 1e-5),),
        concentrations_mM=dict(cell_0=1e-3, ecs_0=5e-4),
    )
    twin = fx.with_exchange(
        twin, [("take", "contact_0", "import", "first_order")], [("take", "cell_0", [(0.0, 1e-4)])]
    )
    parse_spec(twin)  # The declared area: no lookup by the pair.
    twin["model"]["operators"].insert(0, dict(law=comp.STATE_LAW, populations=[]))
    with pytest.raises(ConfigError, match=r"'contact_0' is one of 2 declared patches joining"):
        parse_spec(twin)


# ------------------------------------------------------------------ refusal 5, version 1.2

# Version 1.1's message, as FR-1's judged refusal record (run-05a8d193, C1_refusals) holds it.
V1_1_ANCHOR = (
    "cell_owned_compartments@1: compartment 'ecs_0' declares a nonzero charge anchor (1e-17 C); "
    "version 1.1 admits one only where charged routes are admitted on its bounding patch (a world "
    "that declares kinds and steps with an IMEX tableau); elsewhere the content is "
    "electroneutral, so V_b = 0"
)


def two_pools(routes, anchored):
    """Two compartments of one owner (lys_0 on ecs_0, gran_0 on ecs_1), with membrane state, the
    stand-in's routes into the compartment IDs `routes`, and FR-1's planted anchor (1e-17 C) on the
    node `anchored` (its fixed charge matched, the anchor rule)."""
    raw = fx.world(
        cells=(("cell_0", 1.0),),
        nodes=(("ecs_0", 1.0), ("ecs_1", 0.5)),
        contacts=(("contact_0", "cell_0", "ecs_0"), ("contact_1", "cell_0", "ecs_1")),
        faces=(),
        end=END,
        concentrations_mM=dict(cell_0=1e-3, ecs_0=1e-6, ecs_1=1e-6),
    )
    raw["model"]["operators"].append(dict(law=comp.STATE_LAW, populations=[]))
    raw = cfx.with_compartments(
        raw,
        [cfx.compartment(), cfx.compartment(cid="gran_0", node="ecs_1", patch="contact_1")],
    )
    raw["model"]["operators"].append(dict(law=STAND_IN, compartments=list(routes)))
    cfx._anchor(node(raw, anchored), cfx.PLANTED_ANCHOR_C)
    return raw


def test_refusal_5_version_1_2_admits_an_anchor_where_a_route_charges_its_compartment(
    trafficking,
):
    """Refusal 5, version 1.2 (docs/CLOSED_COMPARTMENT_DESIGN.md §3.4.5; D217, FR-2's design
    statement §7.3): retrieval gives the pool the charge of its membrane (R2), so a checkpoint of a
    trafficking world imported as a new definition carries a nonzero anchor on the pool. It is
    admitted where an admitted operator declares a route into that compartment (the contract's
    charged_compartments), in a world without kinds. Planted, per compartment: the same anchor on
    the other compartment, which no route enters, is refused, naming the operator; and a route into
    an ID the declaration does not declare is refused."""
    spec = parse_spec(two_pools(["lys_0"], "ecs_0"))
    lumen = next(o for o in spec.model.extracellular if o.id == "ecs_0")
    assert lumen.initial_charge_C == cfx.PLANTED_ANCHOR_C and not spec.model.kinds
    with pytest.raises(
        ConfigError,
        match=rf"compartment 'ecs_1' declares a nonzero charge anchor \(1e-17 C\), and no route of "
        rf"{STAND_IN} moves charge into it; version 1.2 admits one only where",
    ):
        parse_spec(two_pools(["lys_0"], "ecs_1"))
    with pytest.raises(ConfigError, match=r"routes charge 'nowhere', which is not a compartment"):
        parse_spec(two_pools(["lys_0", "nowhere"], "ecs_0"))
    # The rule itself: a route into it admits it whatever the solver; version 1.1's branch stays.
    node_1e17 = type("Node", (), dict(initial_charge_C=1e-17))()
    for kinds, imex in ((False, False), (False, True), (True, False)):
        comp.refuse_charge_anchor("ecs_0", node_1e17, kinds, imex, (STAND_IN,), (STAND_IN,))
        with pytest.raises(ConfigError, match="version 1.2 admits one only where"):
            comp.refuse_charge_anchor("ecs_0", node_1e17, kinds, imex, (), (STAND_IN,))
    comp.refuse_charge_anchor("ecs_0", node_1e17, True, True, (), (STAND_IN,))
    with pytest.raises(ConfigError) as caught:
        comp.refuse_charge_anchor("ecs_0", node_1e17, False, True, (), ())
    assert str(caught.value) == V1_1_ANCHOR  # No route charges a compartment: 1.1's words.


def test_fr1s_judged_refusal_class_holds_refusal_5_from_the_definition_check():
    """The lead's ruling of 19 November 2026 on version 1.2's move: refusal 5 reads the
    composition, so it is checked at the definition, whose refusals the composite prefixes. A
    re-run of FR-1's R5 world (its protocol's own refusal_pairs, through its own capture, admit)
    now reports that prefix before version 1.1's message, kept byte for byte, and FR-1's
    classify() still puts it in its judged class, so a later re-judge keeps it; the admitted
    neighbour is admitted."""
    from validation.tissue import compartment_acceptance_qualification as fr1

    refused, admitted = fr1.refusal_pairs()["R5_a_charge_anchor"]
    spec, message = fr1.admit(refused)
    assert spec is None and message == "Invalid composite definition: " + V1_1_ANCHOR
    assert fr1.classify(message) == "refusal 5 (the charge anchor)"
    spec, message = fr1.admit(admitted)
    assert spec is not None and message is None


def test_the_scope_names_refusal_5_version_1_2_and_no_operator_charges_by_default():
    """The summary's scope string names the code's versions (the lead's ruling (a)): every
    compartment world's summary says version 1.2. The contract's hook charges nothing by default."""
    spec = parse_spec(w())
    scope = OPERATORS[LAW].summary(spec, spec.model.operators[-1], (), None)["compartments_scope"]
    assert scope.startswith("refusal 4 version 1.3, refusal 5 version 1.2: ")
    assert Operator().charged_compartments(spec, None) == ()


# ------------------------------------------------------------------ the structure check

STATE, WATER = "membrane_entity_state@1", "ideal_osmosis_linear_compliance_water@1"
STRUCTURE_REFUSED = {
    "water": ((WATER,), WATER),
    "insertion@1": ((STATE, "scheduled_membrane_insertion@1"), "scheduled_membrane_insertion@1"),
    "insertion@2": ((STATE, "scheduled_membrane_insertion@2"), "scheduled_membrane_insertion@2"),
    "the partition": ((STATE, "isopotential_partition@1"), "isopotential_partition@1"),
    "lumen@1": (
        (STATE, "scheduled_membrane_insertion@1", "restricted_cleft_lumen@1"),
        "restricted_cleft_lumen@1",
    ),
    "lumen@2": (
        (STATE, "scheduled_membrane_insertion@2", "restricted_cleft_lumen@2"),
        "restricted_cleft_lumen@2",
    ),
    "replacement@2, over water": ((WATER, "scheduled_cell_replacement@2"), WATER),
    "the symport, over water": ((WATER, "k_anion_symport_mass_action@1"), WATER),
}
STRUCTURE_ADMITTED = (
    ("scheduled_species_exchange@1",),
    ("scheduled_species_turnover@1",),
    ("scheduled_species_turnover@1", "scheduled_species_exchange@1"),
    ("local_species_reactions@1",),
    ("species_regulated_availability@1",),
    ("electrode_current_injection@1",),
    ("scheduled_cell_replacement@1",),
    ("scheduled_bath_composition@1",),
    (STATE,),  # Its areas and capacitances are reference reads; the definition wants trafficking.
    # FR-7's U2 world with a releasing compartment (the lead's rulings of 20 November 2026): the
    # coupling's version 2, the unit producer, and exchange reading the areas current (D191).
    ("species_regulated_availability@2",),
    (STATE, "population_unit_turnover@1"),
    (STATE, "scheduled_species_exchange@1"),
    (STATE, "population_unit_turnover@1", "scheduled_species_exchange@1"),
)


@pytest.mark.parametrize("name", sorted(STRUCTURE_REFUSED))
def test_the_structure_check_refuses_providers_and_closers_of_what_it_reads(name):
    laws, culprit = STRUCTURE_REFUSED[name]
    for order in ((*laws, LAW), (LAW, *laws)):
        errors = pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order))
        assert any(e.startswith(LAW + " reads") and f"but {culprit} " in e for e in errors), (
            order,
            errors,
        )


@pytest.mark.parametrize("laws", STRUCTURE_ADMITTED, ids="+".join)
def test_the_structure_check_admits_the_operators_it_composes_with(laws):
    for order in ((*laws, LAW), (LAW, *laws)):
        assert pump_composite.structure_errors(adapter, tuple(OPERATORS[k] for k in order)) == []
