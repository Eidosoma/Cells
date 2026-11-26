"""cells.operator.local_species_reactions@1 in the run view (docs/RUN_VIEW_DESIGN.md §3; cells/records/run_view.py): the
operator's view declarations, which the gap-junction replication's viewer example needs (D207).

Each claim with a planted error it must catch (D187):
- a small composite world with the operator (validation/tissue/species_reactions_fixtures'
  enzyme network: passive, mass-action and Michaelis-Menten routes at a cell and an outside node)
  writes a view whose layer, route set and records are its declarations: the reactions layer,
  simulated; the reaction_route set, one route per (reaction, site) in declared order, each at its
  cell or outside node, with its law as a word and the roles its signs name; every field of the
  operator on that layer, the route readouts on that set with their units (fmol/s, and 1 for A/RT),
  kinds and signs, and nothing of the operator left unstated;
- each declaration the view needs, removed in turn, is refused again with its reason, and nothing
  is written (planted: no layers, no readout axes, no route set, no unit for A/RT);
- the declarations manifest (cells.declarations@2) reads the same units and signs.
"""  # noqa: E501

import json

import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import OPERATORS
from cells.operators import species_reactions as sr
from cells.records import run_view
from cells.records.io import write_run
from cells.registry import declarations
from tests.run_view_fixtures import load, plant
from validation.tissue import species_reactions_fixtures as rfx

LAW = sr.LAW_ID
READOUTS = {"reaction_rate_fmol_per_s": ("fmol/s", "rate"), "reaction_affinity_RT": ("1", "level")}


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    """The enzyme network, 4 ms, written with a view (no engine source, as the run-view tests)."""
    spec = parse_spec(rfx.enzyme_network(None, end=0.004, observation_times=[0.0, 0.002, 0.004]))
    result = run(spec)
    root = tmp_path_factory.mktemp("reactions-view")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(run_view, "_engine_source", lambda root=None: None)
        write_run(root / "run", result, view=run_view.Request({"label": "reactions"}))
    return spec, result, load(root / "run")


def test_a_reactions_world_writes_a_view_of_its_declarations(written):
    spec, _, view = written
    op = OPERATORS[LAW]
    assert [layer for layer in view["layers"] if layer["owner"] == LAW] == [
        dict(op.VIEW_LAYERS[0], owner=LAW)
    ]
    (routes,) = (s for s in view["sets"] if s["id"] == "reaction_route")
    declaration = next(d for d in spec.model.operators if d.law == LAW)
    laws = {r.id: r.law for r in declaration.reactions}
    assert routes["owner"] == LAW and routes["holds"] == "reaction route"
    assert routes["ids"] == [f"{r.reaction}:{r.node}" for r in declaration.routes]
    assert routes["at"] == [
        {"cell" if r.kind == "cell" else "outside": r.node} for r in declaration.routes
    ]
    assert routes["kinds"] == [sr.LAW_WORDS[laws[r.reaction]] for r in declaration.routes]
    assert {"passive", "mass_action", "michaelis_menten"} <= set(routes["kinds"])
    assert {a for at in routes["at"] for a in at} == {"cell", "outside"}  # Both kinds of site.
    assert set(routes["roles"]) == {"reactants", "products"}
    records = {r["id"]: r for r in view["records"] if r["owner"] == LAW}
    fields = {*op.STATE_AXES, *op.READOUT_COLUMNS}
    assert {r["field"] for r in records.values()} == fields
    assert all(r["layer"] == "reactions" for r in records.values())
    for name, (unit, kind) in READOUTS.items():
        record = records[f"observed_{name}"]
        assert record["axes"] == ["time", "reaction_route"] and record["set"] == "reaction_route"
        assert record["unit"] == unit and record["kind"] == kind
    assert records["observed_reaction_rate_fmol_per_s"]["sign"] == dict(
        op.ORIENTATION["reaction_rate_fmol_per_s"]
    )
    assert records["observed_reaction_affinity_RT"]["difference"] == dict(
        op.ORIENTATION["reaction_affinity_RT"]
    )
    assert records["reaction_extent_fmol"]["sign"]["from"] == "reactants"
    assert all(r["kind"] for r in records.values())  # Every one stated.
    assert not [u for u in view["unstated"] if LAW in json.dumps(u)]


@pytest.mark.parametrize(
    "planted, reason",
    [
        (dict(VIEW_LAYERS=None), f"{LAW} declares no VIEW_LAYERS"),
        (
            dict(OBSERVATION_AXES={}),
            f"{LAW} declares no axes for its readout column reaction_rate_fmol_per_s",
        ),
        (dict(view_sets=None), f"{LAW} declares no set for its axis reaction_route"),
        (dict(UNITS={}), f"{LAW} declares no unit for its field reaction_affinity_RT"),
    ],
)
def test_a_missing_declaration_is_refused_again(written, monkeypatch, tmp_path, planted, reason):
    _, result, _ = written
    if planted.get("view_sets", True) is None:
        monkeypatch.delattr(type(OPERATORS[LAW]), "view_sets")  # The contract's default: none.
    else:
        plant(monkeypatch, LAW, **planted)
    monkeypatch.setattr(run_view, "_engine_source", lambda root=None: None)
    with pytest.raises(run_view.ViewRefused, match=reason):
        write_run(tmp_path / "out", result, view=run_view.Request())
    assert not (tmp_path / "out").exists()


def test_the_declarations_manifest_reads_the_same_units_and_signs():
    (entry,) = (e for e in declarations.manifest()["pieces"] if e["declared_id"] == LAW)
    op = OPERATORS[LAW]
    assert {name: entry["units"][name] for name in READOUTS} == {
        name: unit for name, (unit, _) in READOUTS.items()
    }
    assert entry["signs"] == json.loads(json.dumps(op.ORIENTATION))
    assert entry["fields"]["record_kinds"] == dict(op.RECORD_KINDS)
