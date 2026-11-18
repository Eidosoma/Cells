"""The family's relationship tables (records.relation_tables, cells.relations@1), written with every
bundle.

Each claim with a planted error it must catch (D187):
- every bundle carries its tables, which the writer's own reader accepts: single lineage, a run
  stopped and one continued from its checkpoint, every descendant, an extinct lineage;
- the material edges account for the material: in single-lineage mode the reservoir's supply
  and the leaves, weighed by the bundle's own records, are each type's joins and leaves, and the
  unfollowed daughters' discards are discarded_total's steps; in every-descendant mode the lives'
  numbers sum to the trace's joins and leaves (planted: a supply edge pointing at the next type's
  column, and a life's edges dropped);
- each fission is paid by the unmodelled agent, the payer of fission_work_kT.
"""

import copy
import json

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages import records, runner
from tests.assembly_lineage_fixtures import definition, world

rel = pytest.importorskip("cells.records.relations")
THE_WORLD = world(count=6, size=12, seed=17)


def edge_totals(directory, tables):
    """{(relation, from, to, species): the material it carried}, from each edge's number or its
    record's change over the run (event edges: over their event's two rows)."""
    with np.load(directory / records.ARRAYS, allow_pickle=False) as saved:
        arrays = {k: saved[k] for k in saved.files}
    events = {e.id: e for e in tables["events"]}
    out = {}
    for edge in tables["edges"]:
        if edge.relation not in ("supplies", "removes_to"):
            continue
        if edge.weight_record:
            values = arrays[edge.weight_record]
            index = tuple(int(p) for p in edge.weight_index.split(","))
            series = values[(slice(None), *index)]
            if edge.event:
                row = int(np.searchsorted(arrays["row_time"], events[edge.event].time, "left"))
                moved = series[row + 1] - series[row]
            else:
                moved = series[-1] - series[0]
        else:
            moved = edge.weight
        key = (edge.relation, edge.from_, edge.to, edge.species)
        out[key] = out.get(key, 0) + float(moved)
    return out


def written(tmp_path, run, name):
    directory = tmp_path / name
    records.write_run(directory, run)
    rel.read(directory)  # The writer's own reader accepts it.
    manifest = json.loads((directory / "manifest.json").read_text())
    assert {"relations.npz", "relations.json"} <= set(manifest["files_sha256"])
    return directory, records.relation_tables(directory, run)


def test_single_lineage_tables_account_for_every_molecule(tmp_path):
    spec = parse_spec(definition(THE_WORLD, fissions=5))
    run = runner.run(spec)
    directory, tables = written(tmp_path, run, "single")
    types = list(spec.model.world.types.ids)
    totals = edge_totals(directory, tables)
    joined = run.rows["joined_total"][-1, :, 0] - run.rows["joined_total"][0, :, 0]
    left = run.rows["left_total"][-1, :, 0] - run.rows["left_total"][0, :, 0]
    for i, name in enumerate(types):
        assert totals.get(("supplies", records.RESERVOIR, records.SLOT, name), 0) == joined[i]
        assert totals.get(("removes_to", records.SLOT, records.RESERVOIR, name), 0) == left[i]
    assert not np.any(discard_gap(directory, tables, run))  # Per type.
    paid = {e.id: e.source for e in tables["events"]}
    assert set(paid.values()) == {records.AGENT}
    agent = next(s for s in tables["sources"] if s.id == records.AGENT)
    assert agent.payer_of == "fission_work_kT"
    # Planted: a supply edge pointing at the next type's column.
    edges = list(tables["edges"])
    k = next(n for n, e in enumerate(edges) if e.relation == "supplies")
    i = int(edges[k].weight_index.split(",")[0])
    edges[k] = rel.Edge(**{**edges[k].__dict__, "weight_index": f"{(i + 1) % len(types)},0"})
    shifted = edge_totals(directory, dict(tables, edges=edges))
    assert shifted != totals


def test_stopped_continued_extinct_and_every_descendant_runs_write_their_tables(tmp_path):
    spec = parse_spec(definition(THE_WORLD, fissions=4))
    whole = runner.run(spec)
    stopped = runner.run(spec, stop=int(whole.rows["row_event"][-1]) // 2)
    written(tmp_path, stopped, "stopped")
    written(tmp_path, runner.run(spec, start=stopped.checkpoint()), "continued")
    bare = world(count=4, size=12, matrix=False, transfer_constant=0.6, founder_size=3, seed=2)
    extinct = runner.run(parse_spec(definition(bare, None, fissions=40, seed=2)))
    assert extinct.status == "extinct"
    _, tables = written(tmp_path, extinct, "extinct")
    assert any(e.kind == "extinction" for e in tables["events"])
    data = copy.deepcopy(definition(THE_WORLD, fissions=4))
    data["execution"] |= {"mode": "every_descendant", "lanes": 3}
    data["experiment"]["life_budget"] = 500
    population = runner.run_population(parse_spec(data))
    directory, tables = written(tmp_path, population, "population")
    totals = edge_totals(directory, tables)
    channels = population.trace["event_channel"]
    assert sum(v for (r, *_), v in totals.items() if r == "supplies") == np.sum(channels > 0)
    assert sum(v for (r, *_), v in totals.items() if r == "removes_to") == np.sum(channels < 0)
    # Planted: one life's edges dropped.
    dropped = next(e.to for e in tables["edges"] if e.relation == "supplies")
    edges = [e for e in tables["edges"] if dropped not in (e.from_, e.to)]
    assert len(edges) < len(tables["edges"])
    fewer = edge_totals(directory, dict(tables, edges=edges))
    assert sum(v for (r, *_), v in fewer.items() if r == "supplies") != np.sum(channels > 0)


def discard_gap(directory, tables, run):
    """Per type, the discard edges' material less discarded_total's change over the run (all
    zero: they agree)."""
    totals = edge_totals(directory, tables)
    types = list(run.spec.model.world.types.ids)
    edges = np.zeros(len(types))
    for (relation, source, _, species), value in totals.items():
        if relation == "removes_to" and source != records.SLOT:
            edges[types.index(species)] += value
    booked = run.rows["discarded_total"][-1, :, 0] - run.rows["discarded_total"][0, :, 0]
    return edges - booked


def test_discards_are_exact_where_two_events_share_a_time(tmp_path):
    """Two cases put another row at a fission's time: a run continued from a pending-fission
    checkpoint (its start row), and a daughter born at the fission size (its own fission at its
    parent's time). The discard edges carry each unfollowed daughter's own counts, so they are
    discarded_total's change in both (planted: the edges weighed through the record's event rows,
    which read the wrong rows there)."""
    spec = parse_spec(definition(THE_WORLD, fissions=5))
    whole = runner.run(spec)
    due = int(whole.rows["row_event"][whole.rows["row_kind"] == 1][2])
    stopped = runner.run(spec, stop=due)
    continued = runner.run(spec, start=stopped.checkpoint())
    small = world(
        count=3,
        size=4,
        founder_size=2,
        daughter="uniform",
        empty="other",
        partition={"rule": "binomial", "probability": 0.25},
    )
    binomial = runner.run(parse_spec(definition(small, fissions=10, seed=3, limit=400)))
    at_size = binomial.rows["assembly_count"][binomial.rows["row_kind"] == 2, :, 0].sum(1) == 4
    assert at_size.any()  # A daughter was born at the fission size.
    for name, run in (("continued", continued), ("binomial", binomial)):
        directory, tables = written(tmp_path, run, name)
        assert not np.any(discard_gap(directory, tables, run)), name
        # Planted: the same edges weighed through discarded_total at the record's event rows.
        events = {e.id: e for e in tables["events"]}
        times = run.rows["row_time"]
        steps = run.rows["discarded_total"][:, :, 0]
        planted = []
        for edge in tables["edges"]:
            if edge.event and edge.relation == "removes_to":
                row = int(np.searchsorted(times, events[edge.event].time, "left"))
                i = list(run.spec.model.world.types.ids).index(edge.species)
                planted.append(float(steps[row + 1, i] - steps[row, i]))
        assert sum(planted) != float(steps[-1].sum() - steps[0].sum()), name
