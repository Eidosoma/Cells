"""Checkpoints and branches of one lineage (checkpoints.py; GARD_DESIGN §6.1, streams).

Each claim with a planted error it must catch (D187):
- a run stopped mid-growth and continued from its checkpoint is the uninterrupted run, bitwise:
  every event, time, row and fission (planted: a restore that recomputes the catalysis state
  beta n exactly, instead of restoring the kernel's incremental one; and one that resets the
  occupant's event counter, which reuses its draws);
- so is one stopped with its fission due and continued across the fission;
- a branch with the parent's branch word is the restart, and branches with other words are
  independent futures; each branch's entities keep their keys (planted: a branch whose exchange
  stream is not re-derived for its word, which repeats the parent's future);
- the files round-trip, and a changed lane file, a changed definition or a lineage with no
  future is refused.
"""

import json

import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import GARD_SINGLE_EVENT, checkpoints, gard, kernel, runner
from tests.assembly_lineage_fixtures import definition, world

THE_WORLD = world(count=6, size=12, seed=7, sigma=2.5)


def spec(**kw):
    return parse_spec(definition(THE_WORLD, GARD_SINGLE_EVENT, fissions=6, uniforms=True, **kw))


@pytest.fixture(scope="module")
def whole():
    return runner.run(spec())


def joined(first, second, whole):
    """Why first + second (stopped, then continued) is not `whole` (empty: it is)."""
    out = []
    for name in ("event_channel", "event_time"):
        if not np.array_equal(
            np.concatenate([first.trace[name], second.trace[name]]), whole.trace[name]
        ):
            out.append(name)
    for name, values in whole.fissions.items():
        if not np.array_equal(
            np.concatenate([first.fissions[name], second.fissions[name]]), values, equal_nan=True
        ):
            out.append(name)
    for name, values in whole.rows.items():  # The seam's end and start rows hold one state.
        seam = np.concatenate([first.rows[name][:-1], second.rows[name][1:]])
        if not np.array_equal(seam, values, equal_nan=True):
            out.append(name)
        if name not in ("row_kind",) and not np.array_equal(
            first.rows[name][-1], second.rows[name][0], equal_nan=True
        ):
            out.append(f"{name} at the seam")
    growths = np.concatenate([first.trace["events_per_growth"], second.trace["events_per_growth"]])
    growths[len(first.trace["events_per_growth"]) - 1] += growths[
        len(first.trace["events_per_growth"])
    ]
    growths = np.delete(growths, len(first.trace["events_per_growth"]))
    if not np.array_equal(growths, whole.trace["events_per_growth"]):
        out.append("events_per_growth")
    return out


def test_a_restart_mid_growth_is_the_uninterrupted_run(whole):
    rows = whole.rows
    born, split = int(rows["row_event"][2]), int(rows["row_event"][3])  # Fission 1 to 2.
    stop = (born + split) // 2
    first = runner.run(spec(), stop=stop)
    assert first.status == "stopped" and int(first.rows["row_event"][-1]) == stop
    state = first.checkpoint()
    assert int(state.lane["status"]) == kernel.RUNNING and int(state.lane["age"]) > 0
    second = runner.run(spec(), start=state)
    assert second.start["kind"] == "restart" and second.qualifier != whole.qualifier
    assert joined(first, second, whole) == []
    assert second.lives["life_birth_kind"][0] == "continued"
    assert second.lives["life_key"][0] == first.lives["life_key"][first.lives["life_slot"] == 0][-1]
    # Planted: the catalysis state recomputed exactly (beta n) instead of restored.
    lane = dict(state.lane)
    parsed = spec()
    data = gard.layout(parsed.model.world.data, parsed.execution.type_capacity)
    lane["factor_state"] = np.asarray(gard.state(lane["counts"].astype(np.float64), data, np))
    assert not np.array_equal(lane["factor_state"], state.lane["factor_state"])
    planted = checkpoints.make(spec(), first.qualifier, lane)
    assert joined(first, runner.run(spec(), start=planted), whole) != []
    # Planted: the event counter reset (the occupant's draws reused).
    lane = dict(state.lane, age=np.int64(0))
    planted = checkpoints.make(spec(), first.qualifier, lane)
    assert joined(first, runner.run(spec(), start=planted), whole) != []


def test_a_restart_across_a_due_fission_is_the_uninterrupted_run(whole):
    rows = whole.rows
    due = int(rows["row_event"][rows["row_kind"] == 1][2])  # The join that makes fission 3 due.
    first = runner.run(spec(), stop=due)
    state = first.checkpoint()
    assert int(state.lane["status"]) == kernel.FISSION_DUE
    assert len(first.fissions["fission_time"]) == 2  # The third is pending.
    second = runner.run(spec(), start=state)
    assert joined(first, second, whole) == []
    assert second.rows["row_kind"][:3].tolist() == [0, 1, 2]  # It splits first.


def test_branches_are_independent_futures_that_keep_their_keys(whole, tmp_path):
    landmark = runner.run(
        parse_spec(definition(THE_WORLD, GARD_SINGLE_EVENT, fissions=2, uniforms=True))
    )
    state = landmark.checkpoint()  # A post-fission landmark: its horizon.
    assert int(state.lane["status"]) == kernel.COMPLETE
    restart = runner.run(spec(), start=state)
    assert restart.start["kind"] == "restart"
    assert np.array_equal(
        restart.trace["event_channel"],
        whole.trace["event_channel"][whole.trace["events_per_growth"][:2].sum() :],
    )
    futures = [runner.run(spec(branch=b), start=state) for b in (1, 2, 3)]
    channels = [f.trace["event_channel"][:12].tolist() for f in futures]
    assert len({tuple(c) for c in channels + [restart.trace["event_channel"][:12].tolist()]}) == 4
    for f in futures:
        assert f.start["kind"] == "branch" and f.start["branch_word"] in (1, 2, 3)
        assert f.start["differs"] == ["execution.stream.branch", "experiment.fissions"]
        assert f.lives["life_key"].tolist() == restart.lives["life_key"].tolist()
        assert f.qualifier not in {restart.qualifier, whole.qualifier}
    # Planted: a branch that keeps the parent's exchange stream repeats the parent's future
    # until its first fission (its partition stream does take the branch word).
    original = checkpoints.admit

    def stale(the_spec, checkpoint):
        start, lane = original(the_spec, checkpoint)
        return start, dict(lane, exchange_stream=checkpoint.lane["exchange_stream"])

    try:
        checkpoints.admit = stale
        planted = runner.run(spec(branch=1), start=state)
    finally:
        checkpoints.admit = original
    n = int(restart.trace["events_per_growth"][0])
    assert (
        planted.trace["event_channel"][:n].tolist() == restart.trace["event_channel"][:n].tolist()
    )
    assert planted.trace["event_channel"][:12].tolist() != channels[0]


def test_the_files_round_trip_and_refuse_what_may_not_change(whole, tmp_path):
    state = runner.run(spec(), stop=20).checkpoint()
    path = checkpoints.write(tmp_path / "cp", state)
    again = checkpoints.read(path)
    assert again.digest == state.digest and again.clock == state.clock
    assert all(np.array_equal(again.lane[k], state.lane[k]) for k in state.lane)
    assert runner.run(spec(), start=again).trace["event_channel"].tolist() == (
        runner.run(spec(), start=state).trace["event_channel"].tolist()
    )
    lane = dict(np.load(path / "lane.npz"))
    lane["counts"] = lane["counts"].copy()
    lane["counts"][0] += 1
    np.savez(path / "lane.npz", **lane)
    with pytest.raises(ConfigError, match="checksum"):
        checkpoints.read(path)
    path = checkpoints.write(tmp_path / "cp2", state)
    record = json.loads((path / "checkpoint.json").read_text())
    record["source_hashes"] = dict(record["source_hashes"], changed="source")
    (path / "checkpoint.json").write_text(json.dumps(record))
    with pytest.raises(ConfigError, match="source differs"):
        checkpoints.read(path)
    other = definition(THE_WORLD, GARD_SINGLE_EVENT, fissions=6, uniforms=True)
    other["model"]["world"]["supply"] = 0.2
    with pytest.raises(ConfigError, match="keeps the world"):
        runner.run(parse_spec(other), start=state)
    with pytest.raises(ConfigError, match="keeps the world"):
        runner.run(spec(seed=2), start=state)
    ended = runner.run(spec()).checkpoint()  # Its horizon reached: extend it, or nothing runs.
    with pytest.raises(ConfigError, match="extends experiment.fissions"):
        runner.run(spec(), start=ended)


def test_a_landmark_at_every_horizon_continues_the_whole_run():
    """The binomial world of size 4 (p = 0.25), where a daughter can be born at the fission size:
    a landmark at every horizon k, continued to the full horizon, is the whole run. Such a
    daughter at the horizon is censored, and splits at once when the horizon is extended, as it
    would have in the longer run (planted: restored as running, it grows past the size)."""
    the_world = world(
        count=3,
        size=4,
        founder_size=2,
        daughter="uniform",
        empty="other",
        partition={"rule": "binomial", "probability": 0.25},
    )
    at_size = None
    for seed in (3, 5, 8, 11):
        full = parse_spec(definition(the_world, fissions=10, seed=seed, uniforms=True, limit=400))
        whole = runner.run(full)
        for k in range(1, len(whole.fissions["fission_time"])):
            part = parse_spec(
                definition(the_world, fissions=k, seed=seed, uniforms=True, limit=400)
            )
            first = runner.run(part)
            state = first.checkpoint()
            if int(state.lane["size"]) >= 4:
                at_size = (full, first, state, whole)
                assert int(checkpoints.admit(full, state)[1]["status"]) == kernel.FISSION_DUE
            assert joined(first, runner.run(full, start=state), whole) == [], (seed, k)
    assert at_size is not None  # The case occurred.
    full, first, state, whole = at_size
    original = checkpoints.admit

    def running(the_spec, checkpoint):  # Planted: restored as running.
        start, lane = original(the_spec, checkpoint)
        return start, dict(lane, status=np.int32(kernel.RUNNING))

    try:
        checkpoints.admit = running
        planted = runner.run(full, start=state)
    finally:
        checkpoints.admit = original
    assert joined(first, planted, whole) != []
