"""The declarations manifest (D185; FR-12; seam F): every registered law, kind and operator, and
every active model, written from the registries and the static model table in the versioned
format cells.declarations@2 (docs/library/DECLARATIONS_FORMAT.md).

Each claim with a planted error it must catch (D187):
- every registered piece has its entry and every entry is registered (planted: a law, a kind and
  an operator registered after a manifest was written, which the coverage check must name; and
  the reverse, entries whose pieces are no longer registered);
- the format round-trips through the command line, the same registries give the same bytes, and
  the reader refuses a malformed manifest (planted: each of nine breaks, @1's kind among them);
- the older families are listed by model ID only, flagged legacy, read without importing them
  (planted: a dispatch form the reader does not know, which must refuse rather than drop a
  family);
- @2's IDs join a real definition byte for byte: every ID it names is a declared spelling of the
  manifest (a piece's, a host's, a model's or a model row's), except the solvers and the closure
  law, which no registry declares; each piece names its file and declaration line, each read its
  mode, each field its unit as the run view resolves it (planted: a definition naming a law in its
  namespaced spelling, and a line read from a module with two declarations of one ID).
"""

import ast
import copy
import json
from pathlib import Path

import pytest

import cells
from cells.__main__ import main
from cells.core import kind_registry
from cells.core import pump_composite_spec as composite_spec
from cells.models.operators import contract
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


def planted_scopes():
    """The built-in registries plus one planted piece of each section, as three nested scopes."""
    kinds = kind_registry.KindRegistry()
    for kind in (*kind_registry.active().model_keys().values(), PLANTED_KIND):
        kinds.register(kind)
    return (
        law_registry.scope(law_registry.BUILTIN.extended(PLANTED_LAW)),
        kind_registry.scope(kinds),
        operator_registry.scope(operator_registry.BUILTIN.extended(PlantedOperator)),
    )


PLANTED_PIECES = ("law", "kind", "operator")
PLANTED = {
    ("law", "tests.planted_route@1"),
    ("kind", "tests.planted_kind@1"),
    ("operator", "tests.planted_operator@1"),
}


def test_every_registered_piece_has_its_entry_and_every_entry_is_registered():
    doc = declarations.manifest()
    assert declarations.format_errors(doc) == [] and declarations.coverage_errors(doc) == []
    counts = {piece: sum(e["piece"] == piece for e in doc["pieces"]) for piece in PLANTED_PIECES}
    assert counts == {
        "law": len(law_registry.active()._laws),
        "kind": len(kind_registry.active().model_keys()),
        "operator": len(operator_registry.active().operators())
        + len(operator_registry.active().family_operators()),
    }
    laws_scope, kinds_scope, operators_scope = planted_scopes()
    with laws_scope, kinds_scope, operators_scope:
        missing = declarations.coverage_errors(doc)  # The earlier manifest misses each one.
        assert missing == [f"registered {p} {i} has no entry" for p, i in sorted(PLANTED)]
        planted = declarations.manifest()
        assert declarations.coverage_errors(planted) == []
        entry = next(e for e in planted["pieces"] if e["id"] == "tests.planted_route@1")
        assert entry["module"] == __name__ and entry["family"] == declarations.INNER
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
    kind = next(e for e in doc["pieces"] if e["piece"] == "kind")
    operator = next(e for e in doc["pieces"] if e["reads"] and e["piece"] == "operator")
    breaks = {
        "its kind is": dict(doc, kind="cells.declarations@1"),  # The format before @2.
        "a piece has exactly the keys": dict(
            doc, pieces=[{k: v for k, v in entry.items() if k != "status"}]
        ),
        "listed once": dict(doc, pieces=[entry, entry]),
        "flagged legacy": dict(doc, legacy=[dict(doc["legacy"][0], legacy=False)]),
        "copied from a record": dict(doc, pieces=[dict(entry, status="judged")]),
        "not extracted, so null": dict(doc, pieces=[dict(kind, ledgers=["material"])]),
        "each read has exactly the keys": dict(
            doc, pieces=[dict(operator, reads=[{"name": operator["reads"][0]["name"]}])]
        ),
        "a model has exactly the keys": dict(
            doc, models=[{k: v for k, v in doc["models"][0].items() if k != "next_code"}]
        ),
        "its doc is its page's path": dict(doc, pieces=[dict(entry, doc="docs/elsewhere.md")]),
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


# A real definition in the repository: the frozen water composition of the KCC predictions.
DEFINITION = (
    Path(__file__).resolve().parents[2] / "validation/tissue/pump_water_kcc_predictions.json"
)
# Its IDs that no registry declares: the field solve's closure law and the two solvers.
UNDECLARED = {"/model/closure/law", "/execution/solver", "/execution/field_solver"}


def _ids(value, path=""):
    """(path, ID) of every string in a definition that is an ID (name@major)."""
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in _ids(item, f"{path}/{key}")]
    if isinstance(value, list):
        return [found for item in value for found in _ids(item, f"{path}[*]")]
    if isinstance(value, str) and law_registry._is_id(value):
        return [(path, value)]
    return []


def joins(doc, definition):
    """{(path, ID): what it joins} for every ID of `definition`, by its declared spelling, byte
    for byte; None where it joins nothing."""
    spellings = {}
    for e in doc["pieces"]:
        spellings.setdefault(e["declared_id"], f"{e['piece']} {e['id']}")
        if e["declared_host"]:
            spellings.setdefault(e["declared_host"], f"host {e['host']}")
    for m in doc["models"]:
        spellings.setdefault(m["declared_id"], f"model {m['id']}")
        for row in m["rows"]:
            spellings.setdefault(row["declared_id"], f"{row['role']} {row['id']} of {m['id']}")
    return {(path, i): spellings.get(i) for path, i in sorted(set(_ids(definition)))}


def test_version_2_joins_a_real_definition_and_states_lines_reads_and_units(tmp_path, monkeypatch):
    doc = declarations.manifest()
    definition = json.loads(DEFINITION.read_text())["definition"]
    found = joins(doc, definition)
    assert {path for (path, _), joined in found.items() if joined is None} == UNDECLARED
    assert found[("/model/id", "resolved_pump_water@1")] == "model cells.resolved_pump_water@1"
    law = found[("/model/water/law", "ideal_osmosis_linear_compliance_water@1")]
    assert law == "operator cells.ideal_osmosis_linear_compliance_water@1"
    # The host, as definitions write it: the composite's inner model, which frozen_definition gives
    # this definition, is the declared host of the inner model's laws.
    inner = composite_spec.frozen_definition(definition)["model"]["inner_model"]
    pieces = {e["id"]: e for e in doc["pieces"]}
    kv1p5 = pieces["cells.kv1p5_mh@1"]
    assert kv1p5["declared_host"] == inner and kv1p5["host"] == "cells." + inner
    # Its file and its declaration's first line, and its kernels' lines.
    path = Path(cells.__file__).resolve().parents[1].parent / kv1p5["module_path"]
    assert kv1p5["module_path"] == "src/" + kv1p5["module"].replace(".", "/") + ".py"
    lines = path.read_text().splitlines()
    snippet = "\n".join(lines[kv1p5["line"] - 1 : kv1p5["line"] + 2])
    assert "ChannelLaw(" in snippet and "KV1P5_LAW_ID" in snippet
    for record in kv1p5["kernels"].values():
        name = record["function"].rsplit(".", 1)[1]
        kernel_file = Path(cells.__file__).resolve().parents[1].parent / record["module_path"]
        assert f"def {name}(" in kernel_file.read_text().splitlines()[record["line"] - 1]
    water = pieces["cells.ideal_osmosis_linear_compliance_water@1"]
    assert water["reads"] == [
        dict(name="membrane_area", mode="fixed", stage="split", scoped=False)
    ]  # The declared value, read as the physical one (CONFLICTS_VIEW).
    assert water["units"]["membrane_area"] == "m2" and water["units"]["water_flow_pL_s"] == "pL/s"
    assert water["units"]["water"] is None  # Not stated: no declaration and no suffix.
    assert {(p["interface"], p["key"]) for p in doc["not_extracted"]} >= {
        ("cells.kind@1", "ledgers"),
        ("cells.operator@1", "test"),
    }
    assert all(e["doc"] is None for e in doc["pieces"])  # Until the pages are complete.
    # Planted: a definition naming a law in its namespaced spelling joins nothing byte for byte.
    renamed = copy.deepcopy(definition)
    for channel in renamed["model"]["channels"]:
        channel["kinetic_law"] = "cells." + channel["kinetic_law"]
    assert joins(doc, renamed)[("/model/channels[*]/kinetic_law", "cells.kir2p1_mh2@1")] is None
    # Planted: a module with two declarations of one ID, whose line the read refuses to guess.
    source = (
        "from cells.registry.laws import RouteLaw\n"
        "A = RouteLaw('tests.twice@1', ('membrane',), 'a', host='cells.passive_routes@1')\n"
        "B = RouteLaw('tests.twice@1', ('membrane',), 'b', host='cells.passive_routes@1')\n"
    )
    planted = (ast.parse(source), {"RouteLaw": law_registry.RouteLaw})
    monkeypatch.setattr(declarations, "_syntax", lambda module: planted)
    with pytest.raises(ValueError, match="2 declarations of tests.twice@1 found"):
        declarations.declaration_line(
            "cells.planted", law_registry.RouteLaw, "tests.twice@1", "law_id"
        )
