"""cells.model.assembly_lineages@2's laws on seam F's template and registry, and U2 in both families.

Structural only for version 2 (no rate of its laws is computed). Each claim with a planted error it
must catch (D187):
- OL1's four laws, and OL2's three (the bilayer geometry, phase exchange and permeation), are
  declarations of the family's interfaces, hosted by @2, cited with their works, registered from
  the homes the static model table lists, each by one direct call with a literal ID that the
  declarations manifest reads (planted: a manifest without them);
- parse_spec and get_model dispatch @2 to its own spec and model, and @1 to @1's (planted: an
  unknown major is refused);
- U2 (D199) holds structurally in @2: a declaration that is driven, or names a source, or claims a
  factor that sees a direction, or a dilute catalysing phase, or another host, is refused at
  registration (planted: each);
- D215's guard in @1: a second unsourced driven rate-factor law is refused at registration, and
  D192's single-event GARD law, labelled comparison only, is the one exception (planted: the label
  broken three ways); the @1 tests' planted variant, which keeps the label, is admitted;
- D192's exception is pinned on @1: its single-event form still runs, admitted as driven, with its
  unsourced cycle work reported and never closed.
"""

import dataclasses

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import GARD_SINGLE_EVENT, factors, gard
from cells.models.assembly_lineages import runner as v1_runner
from cells.models.assembly_lineages.spec import LineageModel
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    FREE_ENERGY_INTERFACE,
    GATE_FACTOR,
    GEOMETRY_INTERFACE,
    HAZARD_INTERFACE,
    IDEAL_MIXING,
    MASS_ACTION,
    MEMBRANE_PERMEATION,
    MODEL_ID,
    OPERATOR_INTERFACE,
    OSMOTIC_LUMEN,
    PHASE_EXCHANGE,
    POPULATION_INTERFACE,
    PORE_NUCLEATION,
    PRESCRIBED_SHELL,
    RATE_EQUATIONS,
    RATE_FACTOR_INTERFACE,
    REACTION_INTERFACE,
    REPRESENTATION_INTERFACE,
    REGULAR_MIXING,
    SHARED_POOL,
    SHEAR_FISSION,
    SHELL_PERMEATION,
    SIZE_THRESHOLD_DIVISION,
    TENSION_HOLD,
    TRANSITION_STATE,
    division,
    exchange,
    gate_factor,
    geometry,
    ideal_mixing,
    interfaces,
    lumen,
    mass_action,
    permeation,
    population,
    pore_nucleation,
    prescribed_shell,
    rate_equations,
    regular_mixing,
    replacement,
    shell_permeation,
    size_division,
    tension_hold,
    transfer,
    transition_state,
    withdrawal,
)
from cells.models.assembly_lineages_v2 import model as v2_model
from cells.models.assembly_lineages_v2.spec import AssemblyModel
from cells.registry import declarations
from cells.registry import laws as law_registry
from cells.registry.model_table import MODELS
from cells.registry.models import get_model
from tests import assembly_lineage_fixtures as v1_fixtures
from tests.assembly_lineage_v2_fixtures import definition, world

HOMES = {
    MASS_ACTION: (mass_action, interfaces.ReactionLaw, REACTION_INTERFACE, "10.1021/j100540a008"),
    TRANSITION_STATE: (
        transition_state, interfaces.RateFactorLaw, RATE_FACTOR_INTERFACE, "10.1063/1.1749604"
    ),
    IDEAL_MIXING: (ideal_mixing, interfaces.FreeEnergyTerm, FREE_ENERGY_INTERFACE, None),
    REGULAR_MIXING: (
        regular_mixing, interfaces.FreeEnergyTerm, FREE_ENERGY_INTERFACE, "10.1021/ja01376a009"
    ),
    # OL2's three (milestone 1, geometry worlds).
    BILAYER_GEOMETRY: (geometry, interfaces.GeometryLaw, GEOMETRY_INTERFACE, None),
    PHASE_EXCHANGE: (exchange, interfaces.ReactionLaw, REACTION_INTERFACE, None),
    MEMBRANE_PERMEATION: (permeation, interfaces.ReactionLaw, REACTION_INTERFACE, None),
    # OL2 milestone 2.
    OSMOTIC_LUMEN: (lumen, interfaces.FreeEnergyTerm, FREE_ENERGY_INTERFACE, None),
    # OL2 milestone 3.
    SHARED_POOL: (population, interfaces.PopulationStructure, POPULATION_INTERFACE, None),
    # FR-21's shell (D244, D246).
    PRESCRIBED_SHELL: (prescribed_shell, interfaces.GeometryLaw, GEOMETRY_INTERFACE, None),
    SHELL_PERMEATION: (shell_permeation, interfaces.ReactionLaw, REACTION_INTERFACE, None),
    GATE_FACTOR: (gate_factor, interfaces.RateFactorLaw, RATE_FACTOR_INTERFACE, None),
    # FR-31's Phase A (D287).
    PORE_NUCLEATION: (pore_nucleation, interfaces.AssemblyHazard, HAZARD_INTERFACE,
                      "10.1088/1367-2630/13/9/095010"),
    # OL6 (D304): the deterministic representation, a level of detail.
    RATE_EQUATIONS: (rate_equations, interfaces.AssemblyRepresentation, REPRESENTATION_INTERFACE,
                     "10.1063/1.1678692"),
}  # fmt: skip
OPERATORS = {  # OL3 milestone 1, then OL2 milestone 3
    SHEAR_FISSION: (division, interfaces.AssemblyOperator, OPERATOR_INTERFACE),
    "cells.operator.serial_transfer@1": (transfer, interfaces.AssemblyOperator, OPERATOR_INTERFACE),
    "cells.operator.pool_replacement@1": (replacement, interfaces.AssemblyOperator, OPERATOR_INTERFACE),
    "cells.operator.pool_withdrawal@1": (withdrawal, interfaces.AssemblyOperator, OPERATOR_INTERFACE),
    TENSION_HOLD: (tension_hold, interfaces.AssemblyOperator, OPERATOR_INTERFACE),  # FR-31
    # OL6 S7 (D304): the size-threshold division.
    SIZE_THRESHOLD_DIVISION: (size_division, interfaces.AssemblyOperator, OPERATOR_INTERFACE),
}


def test_the_four_laws_are_template_declarations_of_the_family_s_interfaces():
    registry = law_registry.active()
    row = MODELS[MODEL_ID]
    assert row.type == "family" and row.module == "cells.models.assembly_lineages_v2.spec"
    assert row.runner == v2_model.RUNNER
    assert set(row.law_homes) == {home.__name__ for home, *_ in HOMES.values()}
    assert set(row.interfaces) == {interface for *_, interface, _ in HOMES.values()} | {
        interface for *_, interface in OPERATORS.values()
    }
    assert set(row.operator_homes) == {home.__name__ for home, *_ in OPERATORS.values()}
    for operator_id, (home, kind, interface) in OPERATORS.items():
        operator = home.OPERATOR
        assert isinstance(operator, kind) and operator.errors() == []
        assert operator.operator_id == operator_id and operator.interface == interface
        assert interface in law_registry.FAMILY_INTERFACES and operator.host == MODEL_ID
    for law_id, (home, kind, interface, doi) in HOMES.items():
        law = registry.lookup(law_id)
        assert isinstance(law, kind) and law.errors() == [] and law.interface == interface
        assert interface in law_registry.FAMILY_INTERFACES and law.host == MODEL_ID
        assert law.provenance == "cited" and law.test and registry.module(law_id) == home.__name__
        works = [w.doi for w in law.source.works]
        assert works == ([] if doi is None else [doi])
    assert {law.law_id for law in registry.laws(REACTION_INTERFACE, MODEL_ID)} == {
        MASS_ACTION,
        PHASE_EXCHANGE,
        MEMBRANE_PERMEATION,
        SHELL_PERMEATION,
    }
    # @1's rate factors are unchanged by @2's registrations.
    assert set(factors.registered()) == {law.law_id for law in gard.LAWS}


def test_the_manifest_lists_each_law_at_its_one_direct_call():
    law_registry.active()
    doc = declarations.manifest()
    assert declarations.format_errors(doc) == [] and declarations.coverage_errors(doc) == []
    pieces = {p["id"]: p for p in doc["pieces"]}
    for law_id, (home, *_) in HOMES.items():
        entry = pieces[law_id]
        assert entry["host"] == MODEL_ID and entry["line"] > 0
        assert entry["module_path"] == "src/" + home.__name__.replace(".", "/") + ".py"
    model = next(m for m in doc["models"] if m["id"] == MODEL_ID)
    assert {r["id"] for r in model["rows"]} == set(HOMES) | set(OPERATORS)
    # Planted: a manifest without them is caught by the coverage check.
    planted = dict(doc, pieces=[p for p in doc["pieces"] if p["id"] not in HOMES])
    assert len(declarations.coverage_errors(planted)) == len(HOMES)


def test_parse_spec_and_get_model_dispatch_each_major_to_its_own():
    spec = parse_spec(definition(world()))
    assert isinstance(spec.model, AssemblyModel) and get_model(spec.model) is v2_model
    old = parse_spec(v1_fixtures.definition(v1_fixtures.world(), fissions=1))
    assert isinstance(old.model, LineageModel)
    planted = definition(world())
    planted["model"]["id"] = "cells.assembly_lineages@3"
    with pytest.raises(ConfigError):
        parse_spec(planted)


def _refused(law, match):
    with pytest.raises(ValueError, match=match):
        law_registry.BUILTIN.extended(law)


def test_u2_holds_structurally_in_version_2():
    law_registry.active()
    reaction = mass_action.LAW
    _refused(
        dataclasses.replace(reaction, law_id="tests.reaction.driven_reaction@1", energy_role="driven"),
        "U2",
    )
    _refused(
        dataclasses.replace(reaction, law_id="tests.reaction.sourced_reaction@1", energy_source="fuel"),
        "U2",
    )
    _refused(
        dataclasses.replace(reaction, law_id="tests.reaction.v1_host@1", host="cells.model.assembly_lineages@1"),
        "is hosted by cells.model.assembly_lineages@2",
    )
    factor = transition_state.LAW
    _refused(
        dataclasses.replace(factor, law_id="tests.rate_factor.each_direction@1", evaluated_on="each_direction"),
        "common state m only",
    )
    _refused(
        dataclasses.replace(factor, law_id="tests.rate_factor.dilute@1", catalysing_phases=("lumen",)),
        "condensed phase only",
    )
    _refused(
        dataclasses.replace(regular_mixing.TERM, law_id="tests.free_energy.term@1", part="other"),
        "its part is one of",
    )
    # Control: a passive declaration under its own namespace is admitted.
    admitted = dataclasses.replace(reaction, law_id="tests.reaction.passive_reaction@1")
    assert law_registry.BUILTIN.extended(admitted).lookup("tests.reaction.passive_reaction@1") is admitted


def test_d215_s_guard_on_1_admits_only_d192_s_labelled_exception():
    law_registry.active()
    assert gard.SINGLE_EVENT.errors() == [] and gard.SINGLE_EVENT.energy_role == "driven"
    assert law_registry.BUILTIN.lookup(GARD_SINGLE_EVENT) is gard.SINGLE_EVENT
    single = gard.SINGLE_EVENT
    for change in ({"law_set": "other"}, {"comparison_only": False}, {"form": "pair-consistent"}):
        planted = dataclasses.replace(single, law_id="tests.rate_factor.second_driven@1", **change)
        _refused(planted, "U2, D199; D215")
    # @1's own kernel test plants a variant that keeps the label: still admitted.
    kept = dataclasses.replace(single, law_id="tests.rate_factor.row_update@1", update=lambda *a: None)
    assert kept.errors() == []
    # A passive law needs no label.
    passive = dataclasses.replace(gard.PAIR_CONSISTENT, law_id="tests.rate_factor.renamed_factor@1")
    assert passive.errors() == []


def test_d192_s_single_event_law_still_runs_on_1_as_the_labelled_exception():
    the_world = v1_fixtures.world(seed=4)
    run = v1_runner.run(
        parse_spec(v1_fixtures.definition(the_world, GARD_SINGLE_EVENT, fissions=2))
    )
    assert run.status == "complete" and run.verdict["admitted_as"] == "driven"
    assert run.closure["checked"] is False and run.closure["refused"] is None
    assert run.closure["max_abs_residual_kT"] > 1e-6  # Its unsourced cycle work, reported.
    law = factors.resolve(GARD_SINGLE_EVENT)
    assert law.comparison_only and law.law_set == "gard" and law.form == "single-event"
