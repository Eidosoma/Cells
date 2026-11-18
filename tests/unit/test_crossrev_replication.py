"""validation/tissue/composite_crossrev.py's replication set (D219).

The set holds quick worlds of the gap-junction replication
(docs/GAP_JUNCTION_CANCER_REPLICATION.md), each built by its driver's own generator
(validation/gap_junction_tissue/). They carry the replication's two neutral transport laws: @3's
neutral permeant species (the linear model's Norton form) and the passive routes' neutral law on a
junction host (the linear model as written and the neither condition's line, sheet and ladder
point). Like crossrev's other sets they are recorded as programs (jaxprs) and bindings, compared
bitwise at every core landing.
- The set builds: every world parses with its driver's model and laws over its first five steps,
  and the bindings record themselves again bit for bit.
- A planted parameter changes that world's record, and nothing else in the set's. Each plant is the
  driver's own: every junction permeability x1.01 for the linear model (its planted control, K1),
  and the junction diffusion constant D x1.01 for the neither worlds (the searched parameter; each
  keeps its step).
The programs are traced by the gates' crossrev runs, not here: this tier-1 file records bindings
only.
"""

import pytest

from validation.tissue import composite_crossrev as crossrev

PASSIVE = "passive_neutral_permeation@1"
REACTIONS = "local_species_reactions@1"
COMPOSITE = "resolved_pump_composite@1"
# (model, operators, passive routes as (host, species), cells, junctions, step in s)
EXPECTED = {
    "linear_norton": ("resolved_pump_tissue@3", set(), set(), 3, 2, 0.125),
    "linear_as_written": (COMPOSITE, {REACTIONS}, {("junction", "S"), ("patch", "S")}, 3, 2, 0.125),
    "neither_line": (COMPOSITE, {REACTIONS}, {("junction", "u")}, 25, 24, 0.125),
    "neither_sheet": (COMPOSITE, {REACTIONS}, {("junction", "u")}, 81, 144, 0.0625),
    "neither_ladder": (COMPOSITE, {REACTIONS}, {("junction", "u")}, 25, 24, 0.03125),
}


def plants():
    """One planted parameter per world, as replication_world's keyword arguments."""
    from validation.gap_junction_tissue import neither

    scale = dict(junction_scale=1.01)
    return {
        "linear_norton": scale,
        "linear_as_written": scale,
        "neither_line": dict(d=1.01 * neither.X2_M2_S),
        "neither_sheet": dict(d=1.01 * neither.X2_M2_S),
        "neither_ladder": dict(d=1.01 * crossrev.REPLICATION_LADDER_D_M2_S),
    }


@pytest.fixture(scope="module")
def honest(tmp_path_factory):
    directory = tmp_path_factory.mktemp("honest")
    crossrev.bindings(directory, "replication")
    return directory


def test_the_set_builds(honest, tmp_path):
    from cells.definitions.specs import parse_spec

    worlds = crossrev.replication_worlds()
    assert tuple(worlds) == crossrev.REPLICATION and set(worlds) == set(EXPECTED)
    for name, raw in worlds.items():
        model_id, operators, routes, n_cells, n_junctions, dt = EXPECTED[name]
        spec, m = parse_spec(raw), raw["model"]
        assert m["id"] == model_id, name
        assert {op["law"] for op in m.get("operators", [])} == operators, name
        hosts = {
            ("junction" if "junction" in r else "patch", r["species"])
            for r in m.get("passive_routes", [])
        }
        assert hosts == routes and {r["law"] for r in m.get("passive_routes", [])} <= {PASSIVE}
        assert (len(m["cells"]), len(m["junctions"])) == (n_cells, n_junctions), name
        assert {j["gate"]["law"] for j in m["junctions"]} == {"junction_voltage_relaxation@1"}
        assert all(j["gate"]["minimum_open_fraction"] == 1.0 for j in m["junctions"]), name
        neutral = {s["id"] for s in m["species"] if s["valence"] == 0}
        assert {s for _, s in routes} <= neutral, name
        if model_id == "resolved_pump_tissue@3":  # @3's own route for its neutral permeant species
            assert {s["id"] for s in m["species"]} == {"mR"} <= neutral
            assert {mb["law"] for mb in m["membranes"]} == {"constant_field@1"}
            assert {j["law"] for j in m["junctions"]} == {"constant_field@1"}
        assert spec.execution.dt == dt, name
        changes = {c.time for c in spec.experiment.changes}
        assert spec.experiment.end_time == 5 * spec.execution.dt and changes <= {0.0}, name
    assert sorted(p.name for p in honest.glob("*.npz")) == sorted(f"{n}.npz" for n in EXPECTED)
    again = tmp_path / "again"
    crossrev.bindings(again, "replication")
    assert crossrev.compare(honest, again)


@pytest.mark.parametrize("planted", sorted(EXPECTED))
def test_a_planted_parameter_changes_its_record(planted, honest, tmp_path, monkeypatch, capsys):
    worlds = crossrev.replication_worlds()
    worlds[planted] = crossrev.replication_world(planted, **plants()[planted])
    assert worlds[planted]["execution"]["dt"] == EXPECTED[planted][-1]  # The plant keeps the step.
    monkeypatch.setattr(crossrev, "replication_worlds", lambda: worlds)
    crossrev.bindings(tmp_path / "planted", "replication")
    capsys.readouterr()
    assert not crossrev.compare(honest, tmp_path / "planted")
    differs = [line for line in capsys.readouterr().out.splitlines() if "DIFFERS" in line]
    assert len(differs) == 1 and differs[0].startswith(f"{planted}.npz DIFFERS"), differs
