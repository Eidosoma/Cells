"""The family's laws on seam F's template and registry (CORE_SEAMS_DESIGN §8.1, §8.3, §15).

A new piece joins with no edit to other pieces: the exchange law and GARD's two rate-factor laws
are declarations on the law template under the family's own interfaces (in its own namespace),
registered from their own homes through the public call, and the family finds its rate-factor laws
in the active registry by interface and host, never in a module tuple.

Planted errors it must catch:
- a rate-factor law declared under another host (the family's template refuses it at
  registration);
- a law of another interface under the family's host (not a rate factor: not resolved);
- a manifest written before the family's homes are loaded (the coverage check names its laws).
"""

import dataclasses

import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import (
    EXCHANGE_INTERFACE,
    EXCHANGE_LAW,
    GARD_PAIR_CONSISTENT,
    GARD_SINGLE_EVENT,
    MODEL_ID,
    RATE_FACTOR_INTERFACE,
    exchange,
    factors,
    gard,
    runner,
)
from cells.registry import declarations
from cells.registry import laws as law_registry
from tests.assembly_lineage_fixtures import definition, world

LAWS = {EXCHANGE_LAW: EXCHANGE_INTERFACE} | dict.fromkeys(
    (GARD_SINGLE_EVENT, GARD_PAIR_CONSISTENT), RATE_FACTOR_INTERFACE
)


def test_the_family_laws_are_template_declarations_in_its_own_namespace():
    factors.load_homes()
    for law_id, interface in LAWS.items():
        law = law_registry.BUILTIN.lookup(law_id)
        assert isinstance(law, law_registry.Law) and law.errors() == []
        assert law.interface == interface and interface.split(".", 1)[0] == "assembly_lineages"
        assert law.host == MODEL_ID and law.provenance == "cited" and law.test
    assert law_registry.BUILTIN.lookup(EXCHANGE_LAW) is exchange.LAW
    assert factors.registered() == {law.law_id: law for law in gard.LAWS}
    assert law_registry.BUILTIN.module(GARD_SINGLE_EVENT) == gard.__name__
    assert law_registry.BUILTIN.module(EXCHANGE_LAW) == exchange.__name__


def test_the_manifest_lists_the_family_laws_once_their_homes_are_loaded():
    factors.load_homes()
    doc = declarations.manifest()
    assert declarations.format_errors(doc) == [] and declarations.coverage_errors(doc) == []
    entries = {e["id"]: e for e in doc["pieces"] if e["host"] == MODEL_ID}
    assert set(entries) == set(LAWS)
    for law_id, entry in entries.items():
        assert entry["piece"] == "law" and entry["interface"] == LAWS[law_id]
        assert entry["family"] == MODEL_ID and entry["models"] == [MODEL_ID]
        assert entry["provenance"]["tag"] == "cited" and entry["provenance"]["citation"]
    # Planted: a manifest that missed the family (written as if its homes were never loaded).
    missed = dict(doc, pieces=[e for e in doc["pieces"] if e["host"] != MODEL_ID])
    assert declarations.coverage_errors(missed) == [
        f"registered law {law_id} has no entry" for law_id in sorted(LAWS)
    ]


def test_a_new_rate_factor_law_joins_by_registration_alone():
    """A law in its own namespace, registered in a scope, runs with no edit to the family; a law
    under another host is refused at registration, and a law of another interface is not the
    family's rate factor."""
    factors.load_homes()
    renamed = dataclasses.replace(gard.PAIR_CONSISTENT, law_id="tests.renamed_factor@1")
    elsewhere = dataclasses.replace(
        gard.PAIR_CONSISTENT, law_id="tests.elsewhere_factor@1", host="cells.transporter@1"
    )
    with pytest.raises(ValueError, match="a rate-factor law is hosted by"):
        law_registry.BUILTIN.extended(elsewhere)
    other = law_registry.RouteLaw("tests.not_a_factor@1", ("assembly",), "planted", host=MODEL_ID)
    the_world = world(seed=4)
    with law_registry.scope(law_registry.BUILTIN.extended(renamed, other)):
        assert factors.resolve("tests.renamed_factor@1") is renamed
        new = runner.run(parse_spec(definition(the_world, "tests.renamed_factor@1", fissions=2)))
        with pytest.raises(ConfigError, match="Unknown rate-factor law"):
            parse_spec(definition(the_world, "tests.not_a_factor@1", fissions=2))
    with pytest.raises(ConfigError, match="Unknown rate-factor law"):
        factors.resolve("tests.renamed_factor@1")  # Out of the scope: not registered.
    old = runner.run(parse_spec(definition(the_world, GARD_PAIR_CONSISTENT, fissions=2)))
    assert new.trace["event_channel"].tolist() == old.trace["event_channel"].tolist()
