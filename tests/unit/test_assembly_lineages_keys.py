"""The relationship keys of one lineage (D202; keys.py): carrier keys, lives, the run qualifier and
the reserved label stream.

Each claim with a planted error it must catch (D187):
- single-lineage keys are the lineage counter's (the founder 0:0, daughters 0:1 and 0:2, then
  0:3 and 0:4 from the followed one), and the lives table holds the founder and both daughters of
  every fission, each with its parent and its end (planted: a dropped unfollowed daughter, a life
  with no end reason);
- an unfollowed daughter's life ends not_followed and an empty daughter's extinct, followed or
  not (planted: an empty unfollowed daughter recorded as not_followed);
- the last row is always the run's end state, and each life that ran has one growth (planted: a
  growth count off by one event);
- the qualifier separates runs that differ only by seed, is the same for a replica, and is never
  in a stream (planted: a qualifier folded into the definition's streams changes the events);
- the label domain is numbered and undrawable.
"""

import hashlib
import json

import numpy as np
import pytest

from cells.core.specs import parse_spec
from cells.models.assembly_lineages import keys, runner, streams
from tests.assembly_lineage_fixtures import definition, world


def census(lives, table):
    """Why a lives table is not the lineage's (empty: it is)."""
    out = []
    founders = int(np.sum(lives["life_birth_kind"] == "founder"))
    if len(lives["life_key"]) != founders + 2 * len(table["fission_time"]):
        out.append("lives are the founder and both daughters of every fission")
    if len(set(lives["life_key"].tolist())) != len(lives["life_key"]):
        out.append("keys are unique")
    known = set(lives["life_key"].tolist())
    for k, parent in zip(lives["life_key"], lives["life_parent"], strict=True):
        if parent != -1 and parent not in known:
            out.append(f"{keys.spelled(k)}'s parent is a life")
    reasons = set(keys.END_REASONS)
    if not all(r in reasons for r in lives["life_end_reason"].tolist()):
        out.append("every life ends with a reason")
    return out


@pytest.fixture(scope="module")
def lineage():
    return runner.run(parse_spec(definition(world(), fissions=6)))


def test_single_lineage_keys_are_the_counters_and_lives_hold_every_daughter(lineage):
    lives, table = lineage.lives, lineage.fissions
    assert census(lives, table) == []
    assert lives["life_key"].tolist() == list(range(13))
    assert np.array_equal(table["fission_daughters"], np.arange(1, 13).reshape(6, 2))
    assert [keys.spelled(k) for k in lives["life_key"][:3]] == ["0:0", "0:1", "0:2"]
    assert keys.carrier_id(keys.key(1, 2)) == "carrier:a4294967298"  # The key in decimal.
    assert keys.spelled(keys.key(1, 2)) == "1:2" and keys.words(2**32 + 5) == (1, 5)
    followed = lives["life_slot"] == 0
    assert lives["life_end_reason"][~followed].tolist() == ["not_followed"] * 6
    assert lives["life_end_reason"][followed].tolist() == ["divided"] * 6 + ["censored"]
    assert lives["life_censored_by"][-2] == "horizon"
    assert lives["life_parent"][1:].tolist() == [0, 0, 1, 1, 3, 3, 5, 5, 7, 7, 9, 9]
    assert np.all(lives["life_sublineage"][followed] == 0)
    assert np.all(lives["life_sublineage"][~followed] == -1)
    planted = {k: v[:-1] for k, v in lives.items()}  # A dropped unfollowed daughter.
    assert census(planted, table)
    planted = dict(lives, life_end_reason=lives["life_end_reason"].copy())
    planted["life_end_reason"][3] = ""  # A life with no end reason.
    assert census(planted, table)


def reason_errors(lives):
    """Daughters whose end reason does not follow from their birth (empty: none)."""
    sizes, reasons = lives["life_size_at_birth"], lives["life_end_reason"]
    division = lives["life_birth_kind"] == "division"
    unfollowed = division & (lives["life_slot"] == -1)
    out = np.flatnonzero(division & (sizes == 0) & (reasons != "extinct")).tolist()
    out += np.flatnonzero(unfollowed & (sizes > 0) & (reasons != "not_followed")).tolist()
    return sorted(out)


def test_an_unfollowed_daughter_is_not_an_extinct_one():
    """A split that can leave a daughter empty (binomial, p = 0.25, at size 4): an empty daughter
    ends extinct at its birth, followed or not; a nonempty unfollowed one ends not_followed."""
    the_world = world(
        count=3, size=4, founder_size=2, partition={"rule": "binomial", "probability": 0.25}
    )
    empty_unfollowed, empty_followed = None, False
    for seed in range(1, 40):
        run = runner.run(parse_spec(definition(the_world, fissions=8, seed=seed)))
        lives = run.lives
        assert census(lives, run.fissions) == [] and reason_errors(lives) == []
        sizes, division = lives["life_size_at_birth"], lives["life_birth_kind"] == "division"
        unfollowed = division & (lives["life_slot"] == -1)
        if np.any(unfollowed & (sizes == 0)) and empty_unfollowed is None:
            empty_unfollowed = lives
        if np.any(division & (lives["life_slot"] == 0) & (sizes == 0)):
            empty_followed = True
            assert run.status == "extinct"
    assert empty_unfollowed is not None and empty_followed  # Both cases occurred.
    planted = dict(empty_unfollowed, life_end_reason=empty_unfollowed["life_end_reason"].copy())
    sizes = planted["life_size_at_birth"]
    hit = np.flatnonzero((planted["life_slot"] == -1) & (sizes == 0))[0]
    planted["life_end_reason"][hit] = "not_followed"  # An empty daughter called unfollowed.
    assert reason_errors(planted) == [hit]


def test_the_last_row_is_the_end_and_each_life_that_ran_has_one_growth(lineage):
    rows, trace = lineage.rows, lineage.trace
    assert rows["row_kind"][-1] == 3 and rows["row_kind"][-2] == 2  # Ended at its last fission.
    for name in ("assembly_count", "row_time", "row_event", "occupant"):
        assert np.array_equal(rows[name][-1], rows[name][-2])  # The end is the last daughter.
    occupants = lineage.lives["life_key"][lineage.lives["life_slot"] == 0]
    assert trace["growth_carrier"].tolist() == occupants.tolist()
    assert trace["events_per_growth"][-1] == 0  # The last daughter never ran.
    assert trace["events_per_growth"].sum() == len(trace["event_channel"]) == rows["row_event"][-1]
    ages = rows["row_event"][rows["row_kind"] == 1] - np.concatenate(
        ([0], rows["row_event"][rows["row_kind"] == 2][:-1])
    )
    assert np.array_equal(trace["events_per_growth"][:-1], ages)
    planted = trace["events_per_growth"].copy()
    planted[0] += 1
    assert not np.array_equal(planted[:-1], ages)


def test_the_qualifier_is_in_ids_only():
    base = definition(world(), fissions=2, seed=3)
    other = definition(world(), fissions=2, seed=4)
    a, again, b = (runner.run(parse_spec(d)) for d in (base, base, other))
    assert a.qualifier == again.qualifier != b.qualifier
    fingerprint = parse_spec(base).fingerprint
    body = json.dumps({"definition": fingerprint, "start": "fresh"}, sort_keys=True)
    assert a.qualifier == hashlib.sha256(body.encode()).hexdigest()  # cells.relations@1's form.
    stopped = runner.run(parse_spec(base), stop=5)  # A stopped run is not the whole run.
    assert stopped.qualifier not in {a.qualifier, again.qualifier}
    assert stopped.qualifier == keys.qualifier(
        fingerprint, "fresh", {"events": 5, "fissions": int(stopped.rows["generation"][-1, 0])}
    )
    assert a.lives["life_key"].tolist() == b.lives["life_key"].tolist()  # Keys: no seed in them.
    assert a.qualifier not in str(streams.identity(3, 0, 0, 0))
    # Planted: a qualifier folded into a stream word (here the lineage word) moves every event.
    folded = definition(world(), fissions=2, seed=3, lineage=int(a.qualifier[:8], 16))
    assert runner.run(parse_spec(folded)).trace["event_channel"].tolist() != (
        a.trace["event_channel"].tolist()
    )


def test_the_label_domain_is_numbered_and_never_drawn():
    assert dict(streams.DOMAINS) == {
        "initial_composition": 0,
        "exchange": 1,
        "partition": 2,
        "continuation": 3,
        "label": 4,
    }
    assert streams.RESERVED == ("label",)
    base = streams.base_key_data(1, 0, 0, 0)
    with pytest.raises(ValueError, match="reserved"):
        streams.stream_key_data(base, np.int64(0), "label")
    assert streams.identity(1, 0, 0, 0)["reserved_domains"] == ["label"]


def test_descent_rows_are_the_writers_lives_and_events(lineage):
    """records.descent and relation_events: cells.relations@1's Life and Event rows, with every
    parent a life ending at its daughters' birth event, and every end event an event row at the
    life's end time; through the writer itself when it is installed. Planted: a parent that is no
    life's, and an end event at another time."""
    from cells.models.assembly_lineages import records

    arrays = {**lineage.lives, **lineage.fissions}
    lives = records.descent(arrays)
    events = {e["id"]: e for e in records.relation_events(arrays)}
    by_id = {r["id"]: r for r in lives}
    assert (
        lives[0] | {"id": "carrier:a0", "parent": "", "birth_event": "", "root": "carrier:a0"}
        == (lives[0])
    )
    assert lives[1]["parent"] == "carrier:a0" and lives[1]["birth_event"] == "event:fission/0"
    assert lives[2]["end_reason"] == "not_followed" and lives[2]["slot"] == ""
    assert lives[2]["end_event"] == lives[2]["birth_event"] and lives[-2]["end_event"] == ""

    def errors(rows, table):
        out = []
        for r in rows:
            if r["parent"] and (
                r["parent"] not in by_id or by_id[r["parent"]]["end_event"] != r["birth_event"]
            ):
                out.append(r["id"])
            if r["end_event"] and table[r["end_event"]]["time"] != r["end_time"]:
                out.append(r["id"])
        return out

    assert errors(lives, events) == []
    assert all(
        abs(sum(r["share"] for r in lives if r["parent"] == p) - 1.0) < 1e-12
        for p in {r["parent"] for r in lives if r["parent"]}
    )
    planted = [dict(r) for r in lives]
    planted[4]["parent"] = "carrier:a99"
    assert errors(planted, events) == ["carrier:a4"]
    moved = dict(events, **{"event:fission/1": dict(events["event:fission/1"], time=-1.0)})
    assert errors(lives, moved) != []


def test_the_writer_takes_the_rows_unchanged(lineage, tmp_path):
    """When cells.relations@1's writer is installed, it writes the family's rows as they are."""
    from cells.models.assembly_lineages import records

    relations = pytest.importorskip("cells.records.relations")
    arrays = {**lineage.lives, **lineage.fissions}
    relations.write(
        tmp_path,
        world=lineage.qualifier,
        lives=[relations.Life(**r) for r in records.descent(arrays)],
        events=[relations.Event(**e) for e in records.relation_events(arrays)],
        nodes=[relations.Node(**n) for n in records.relation_nodes(arrays)],
    )
