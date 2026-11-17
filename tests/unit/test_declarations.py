"""The declarations manifest (D185; FR-12; seam F): every registered law, kind and operator,
written from the registries in the versioned format cells.declarations@1.

Each claim with a planted error it must catch (D187):
- every registered piece has its entry and every entry is registered, a family's own operators
  among them (planted: a law, a kind, a composite operator and a family operator registered after
  a manifest was written, which the coverage check must name and the counts must include; and the
  reverse, entries whose pieces are no longer registered);
- the format round-trips through the command line, the same registries give the same bytes, and
  the reader refuses a malformed manifest (planted: each of five breaks);
- the older families are listed by model ID only, flagged legacy, read without importing them
  (planted: a dispatch form the reader does not know, which must refuse rather than drop a
  family).
"""

import json

import pytest

from cells.__main__ import main
from cells.core import kind_registry
from cells.models.operators import OPERATORS, contract
from cells.registry import declarations
from cells.registry import laws as law_registry
from cells.registry import operators as operator_registry

PLANTED_LAW = law_registry.RouteLaw(
    "tests.planted_route@1", ("membrane",), "a planted route", host="cells.passive_routes@1"
)
PLANTED_KIND = kind_registry.Kind(kind_id="tests.planted_kind@1", model_key="planted_block")


class PlantedOperator(contract.Operator):
    LAW_ID = "tests.planted_operator@1"
    EVENT = True


class PlantedLineageOperator(operator_registry.FamilyOperator):
    """A family's own operator (not the composite's), under an interface a family declares."""

    interface = "cells.lineage_operator@1"


PLANTED_FAMILY_OPERATOR = PlantedLineageOperator(
    "tests.planted_lineage_operator@1", host="cells.assembly_lineages@1"
)


def planted_scopes():
    """The built-in registries plus one planted piece of each section, as three nested scopes."""
    kinds = kind_registry.KindRegistry()
    for kind in (*kind_registry.active().model_keys().values(), PLANTED_KIND):
        kinds.register(kind)
    return (
        law_registry.scope(law_registry.BUILTIN.extended(PLANTED_LAW)),
        kind_registry.scope(kinds),
        operator_registry.scope(
            operator_registry.BUILTIN.extended(PlantedOperator, PLANTED_FAMILY_OPERATOR)
        ),
    )


PLANTED_PIECES = ("law", "kind", "operator")
PLANTED = {
    ("law", "tests.planted_route@1"),
    ("kind", "tests.planted_kind@1"),
    ("operator", "tests.planted_operator@1"),
    ("operator", "tests.planted_lineage_operator@1"),
}


def counts(doc):
    """{piece: its entries' count} of a manifest, and of the active registries: an operator count
    is the composite's operators and the families' together."""
    listed = {piece: sum(e["piece"] == piece for e in doc["pieces"]) for piece in PLANTED_PIECES}
    operators = operator_registry.active()
    registered = {
        "law": len(law_registry.active()._laws),
        "kind": len(kind_registry.active().model_keys()),
        "operator": len(operators.operators()) + len(operators.family_operators()),
    }
    return listed, registered


def test_every_registered_piece_has_its_entry_and_every_entry_is_registered():
    doc = declarations.manifest()
    assert declarations.format_errors(doc) == [] and declarations.coverage_errors(doc) == []
    listed, registered = counts(doc)
    assert listed == registered
    laws_scope, kinds_scope, operators_scope = planted_scopes()
    with laws_scope, kinds_scope, operators_scope:
        missing = declarations.coverage_errors(doc)  # The earlier manifest misses each one.
        assert missing == [f"registered {p} {i} has no entry" for p, i in sorted(PLANTED)]
        planted = declarations.manifest()
        assert declarations.coverage_errors(planted) == []
        listed, registered = counts(planted)
        assert listed == registered and registered["operator"] == len(OPERATORS) + 1
        entry = next(e for e in planted["pieces"] if e["id"] == "tests.planted_route@1")
        assert entry["module"] == __name__ and entry["family"] == declarations.INNER
        family = next(
            e for e in planted["pieces"] if e["id"] == PLANTED_FAMILY_OPERATOR.operator_id
        )
        assert family["interface"] == "cells.lineage_operator@1"
        assert family["host"] == family["family"] == "cells.assembly_lineages@1"
    stale = declarations.coverage_errors(planted)  # Unregistered again: entries without pieces.
    assert stale == [f"listed {p} {i} is not registered" for p, i in sorted(PLANTED)]


def test_the_format_round_trips_and_the_reader_refuses_a_malformed_manifest(tmp_path, capsys):
    out = tmp_path / "declarations.json"
    assert main(["declarations", "--out", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == declarations.FORMAT
    written = out.read_bytes()
    doc = declarations.read(out)
    assert declarations.dumps(doc).encode() == written  # Read back, written again: the same bytes.
    assert declarations.dumps(declarations.manifest()).encode() == written  # No time stamp.
    with pytest.raises(FileExistsError):
        declarations.write(out)
    entry = doc["pieces"][0]
    breaks = {
        "its kind is": dict(doc, kind="cells.declarations@2"),
        "a piece has exactly the keys": dict(
            doc, pieces=[{k: v for k, v in entry.items() if k != "status"}]
        ),
        "listed once": dict(doc, pieces=[entry, entry]),
        "flagged legacy": dict(doc, legacy=[dict(doc["legacy"][0], legacy=False)]),
        "copied from a record": dict(doc, pieces=[dict(entry, status="judged")]),
    }
    for reason, broken in breaks.items():
        path = tmp_path / f"broken-{len(reason)}.json"
        path.write_text(declarations.dumps(broken))
        with pytest.raises(ValueError, match=reason):
            declarations.read(path)


def test_older_families_are_listed_by_model_id_only(tmp_path):
    legacy = declarations.manifest()["legacy"]
    assert legacy and all(
        entry == dict(id=entry["id"], legacy=True, piece="model") for entry in legacy
    )
    ids = {entry["id"] for entry in legacy}
    assert "resolved_tissue@12" in ids and "finite_extracellular@1" in ids  # A literal, a name.
    assert not ids & {declarations.INNER.split(".", 1)[1], "resolved_pump_composite@1"}
    planted = tmp_path / "registration.py"
    planted.write_text(
        "def parse(data):\n"
        "    if data['model'].get('id') == 'kept@1':\n        return 1\n"
        "    if data['model'].get('id') == f'{data}@1':\n        return 2\n"
    )
    with pytest.raises(ValueError, match="An unread model-ID form"):
        declarations.legacy_entries(planted)
    planted.write_text(
        "from cells.legacy.core.old_spec import OLD_ID\n"
        "def parse(data):\n    if data['model'].get('id') == OLD_ID:\n        return 1\n"
    )
    with pytest.raises(ValueError, match="An unread model-ID form"):
        declarations.legacy_entries(planted)  # A legacy module's name is never imported.
