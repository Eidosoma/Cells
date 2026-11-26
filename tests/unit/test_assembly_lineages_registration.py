"""The family's laws and operators on seam F's templates and registry (CORE_SEAMS_DESIGN §8.1,
§8.3, §8.4, §15).

A new piece joins with no edit to other pieces: the exchange law and GARD's two rate-factor laws
are declarations on the law template, and the fission and continuation operators on the template
of a family's own operators, under the interfaces the family declares in its row of the static
model table (cells.exchange_law@1, cells.rate_factor_law@1, cells.lineage_operator@1), registered
from the homes that row lists through the public call. The family finds its rate-factor laws in
the active registry by interface and host, never in a module tuple, and a fresh process's
manifest lists every piece.

Planted errors it must catch:
- a rate-factor law declared under another host (the family's template refuses it at
  registration);
- a law of another interface under the family's host (not a rate factor: not resolved);
- a manifest written before the family's homes are loaded (the coverage check names its pieces).
"""

import dataclasses
import json
import subprocess
import sys
from pathlib import Path

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import (
    CONTINUATION,
    EXCHANGE_INTERFACE,
    EXCHANGE_LAW,
    FISSION,
    GARD_PAIR_CONSISTENT,
    GARD_PAIR_CONSISTENT_V2,
    GARD_SINGLE_EVENT,
    MODEL_ID,
    OPERATOR_INTERFACE,
    RATE_FACTOR_INTERFACE,
    continuation,
    exchange,
    factors,
    fission,
    gard,
    runner,
)
from cells.registry import declarations
from cells.registry import laws as law_registry
from cells.registry import operators as operator_registry
from tests.assembly_lineage_fixtures import definition, world

LAWS = {EXCHANGE_LAW: EXCHANGE_INTERFACE} | dict.fromkeys(
    (GARD_SINGLE_EVENT, GARD_PAIR_CONSISTENT, GARD_PAIR_CONSISTENT_V2), RATE_FACTOR_INTERFACE
)
OPERATORS = {FISSION: fission, CONTINUATION: continuation}
ROOT = Path(__file__).resolve().parents[2]


def test_the_family_pieces_are_template_declarations_of_its_interfaces():
    law_registry.active()
    for law_id, interface in LAWS.items():
        law = law_registry.BUILTIN.lookup(law_id)
        assert isinstance(law, law_registry.Law) and law.errors() == []
        assert law.interface == interface and interface in law_registry.FAMILY_INTERFACES
        assert law.host == MODEL_ID and law.provenance == "cited" and law.test
    held = {d.operator_id: d for d in operator_registry.active().family_operators()}
    for operator_id, home in OPERATORS.items():
        declaration = held[operator_id]
        assert declaration is home.OPERATOR and declaration.errors() == []
        assert declaration.interface == OPERATOR_INTERFACE and declaration.host == MODEL_ID
        assert home.DECLARATION == declaration.record() and declaration.test
    assert operator_id not in operator_registry.OPERATORS  # Not one of the composite's.
    assert law_registry.BUILTIN.lookup(EXCHANGE_LAW) is exchange.LAW
    assert factors.registered() == {law.law_id: law for law in gard.LAWS}
    assert law_registry.BUILTIN.module(GARD_SINGLE_EVENT) == gard.__name__
    assert law_registry.BUILTIN.module(EXCHANGE_LAW) == exchange.__name__


def test_the_manifest_lists_the_family_laws_once_their_homes_are_loaded():
    law_registry.active()
    doc = declarations.manifest()
    assert declarations.format_errors(doc) == [] and declarations.coverage_errors(doc) == []
    entries = {e["id"]: e for e in doc["pieces"] if e["host"] == MODEL_ID}
    assert set(entries) == set(LAWS) | set(OPERATORS)
    for piece_id, entry in entries.items():
        assert entry["piece"] == ("law" if piece_id in LAWS else "operator")
        assert entry["interface"] == LAWS.get(piece_id, OPERATOR_INTERFACE)
        assert entry["family"] == MODEL_ID and entry["models"] == [MODEL_ID]
        assert entry["provenance"]["tag"] == "cited" and entry["provenance"]["citation"]
    # Planted: a manifest that missed the family (written as if its homes were never loaded).
    missed = dict(doc, pieces=[e for e in doc["pieces"] if e["host"] != MODEL_ID])
    assert declarations.coverage_errors(missed) == sorted(
        [f"registered law {law_id} has no entry" for law_id in LAWS]
        + [f"registered operator {op} has no entry" for op in OPERATORS]
    )


def test_a_fresh_process_manifest_lists_the_family(tmp_path):
    out = tmp_path / "declarations.json"
    subprocess.run(
        [sys.executable, "-B", "-m", "cells", "declarations", "--out", str(out)],
        check=True,
        capture_output=True,
        timeout=300,
        cwd=ROOT,
    )
    pieces = {p["id"]: p for p in json.loads(out.read_text())["pieces"]}
    assert set(LAWS) | set(OPERATORS) <= set(pieces)
    for piece_id in LAWS | OPERATORS:
        assert pieces[piece_id]["host"] == MODEL_ID and pieces[piece_id]["line"] > 0
    missing = {k: v for k, v in pieces.items() if k != FISSION}  # Planted: a piece missing.
    assert not set(LAWS) | set(OPERATORS) <= set(missing)


def test_a_new_rate_factor_law_joins_by_registration_alone():
    """A law in its own namespace, registered in a scope, runs with no edit to the family; a law
    under another host is refused at registration, and a law of another interface is not the
    family's rate factor."""
    law_registry.active()
    renamed = dataclasses.replace(gard.PAIR_CONSISTENT, law_id="tests.rate_factor.renamed_factor@1")
    elsewhere = dataclasses.replace(
        gard.PAIR_CONSISTENT,
        law_id="tests.rate_factor.elsewhere_factor@1",
        host="cells.kind.transporter@1",
    )
    with pytest.raises(ValueError, match="a rate-factor law is hosted by"):
        law_registry.BUILTIN.extended(elsewhere)
    other = law_registry.RouteLaw(
        "tests.route.not_a_factor@1", ("assembly",), "planted", host=MODEL_ID
    )
    the_world = world(seed=4)
    with law_registry.scope(law_registry.BUILTIN.extended(renamed, other)):
        assert factors.resolve("tests.rate_factor.renamed_factor@1") is renamed
        new = runner.run(
            parse_spec(definition(the_world, "tests.rate_factor.renamed_factor@1", fissions=2))
        )
        with pytest.raises(ConfigError, match="Unknown rate-factor law"):
            parse_spec(definition(the_world, "tests.route.not_a_factor@1", fissions=2))
    with pytest.raises(ConfigError, match="Unknown rate-factor law"):
        factors.resolve("tests.rate_factor.renamed_factor@1")  # Out of the scope: not registered.
    old = runner.run(parse_spec(definition(the_world, GARD_PAIR_CONSISTENT, fissions=2)))
    assert new.trace["event_channel"].tolist() == old.trace["event_channel"].tolist()
