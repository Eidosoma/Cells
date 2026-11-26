"""FR-22, rung P: checkpoints of population worlds in cells.model.assembly_lineages@2 (checkpoints.py; the
lead's ruling of 20 November 2026: the population runner, D215's option a, cuts before or after a
stop, never at one).

Each claim with a planted error it must catch (D187):
- K1: a world stopped at an exact event count, its checkpoint written and read back, and resumed,
  is the uninterrupted world after the cut, bitwise: its trace and event uniforms, every row (the
  counts, the bookings and the ledger, referenced to the world's own initial F), the final lane,
  the lyses, transfers and fission rows, with the world's numbering. The stopped run's end row is
  the resumed run's start row, and the two runs' lives, joined at the cut, are the uninterrupted
  run's; both bundles write and read back with cells.relations@2. The cuts sit mid-run, one event
  before and after a lysis, after a division, and one event before and after a transfer, with a
  slot freed before the cut and taken by a daughter after it (planted: the draw at the cut counted
  twice, which moves the trace; the device's heat sum restored from the bundle's heat column,
  which holds the host's lysis heat too, so the resumed run's ledger does not close and the run is
  refused. "The rates recomputed at the restore", the planned plant, cannot fail: refresh gives
  the event step's rates bitwise);
- K2: the refusals: a cut at a lysing event (its time would need cells.relations' same-time
  order), a changed world, a new branch word, a single-lineage start or stop (rung S), a stop
  outside its range, and a checkpoint whose file, source or state changed.

World-compiling cost: one population program (two worlds of one structure, K = 6) and about 20
runs, 70.01 s for the whole file on the timed lane. Reason: the claim is the runs' own bitwise
continuation.
"""

import dataclasses
import json

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    checkpoints,
    lumen,
    population,
    records,
    runner,
)
from cells.records import relations as rel
from tests.unit.test_assembly_lineages_v2_population import FOUNDER, pop_spec, with_diagnostic


def lysis_world():
    tense = dict(FOUNDER, **{"L@membrane": 6, "I@lumen": 6})
    probe = pop_spec([FOUNDER, tense], 6, mu_bilayer=3.0)
    sigma = lumen.host_tension(probe.model.world, population.founder_vectors(probe.model.world)[1])
    return with_diagnostic(
        pop_spec([FOUNDER, tense], 6, sigma_max=sigma * 1.001, horizon=5.0, mu_bilayer=3.0)
    )


def staged_world():
    """Two founders; a division at 1 s, a transfer keeping 2 at 2 s, and a division at 2.5 s whose
    daughters take the slots the transfer freed."""
    schedules = [
        {"index": 2, "kind": "shear", "k": 2, "times_s": [1.0, 2.5]},
        {"index": 4, "kind": "transfer", "times_s": [2.0], "K_keep": 2, "fresh_pool": [20, 4, 0]},
    ]
    founders = [dict(FOUNDER, **{"L@membrane": 12}), dict(FOUNDER, **{"L@membrane": 10})]
    return with_diagnostic(pop_spec(founders, 6, schedules=schedules, horizon=3.0))


@pytest.fixture(scope="module")
def worlds():
    out = {}
    for name, spec in (("lysis", lysis_world()), ("staged", staged_world())):
        a = runner.run(spec).check()
        out[name] = (spec, a)
    return out


def cut(a, where):
    """The event count of a named cut in the uninterrupted run `a`."""
    times, n = a.trace["event_time"], len(a.trace["event_time"])
    if where == "mid":
        return n // 2
    if where in ("before_lysis", "after_lysis"):
        e = a.population["lyses"][0]["event"]
        return e - 1 if where == "before_lysis" else e + 1
    if where == "after_division":
        return int(np.searchsorted(times, a.population["fissions"]["fission_time"][0])) + 1
    t = a.population["transfers"][0]["time_s"]
    j = int(np.searchsorted(times, t))  # the last event before the transfer
    return j if where == "before_transfer" else j + 1


def differences(a, b1, b2, k):
    """Where the resumed run b2 differs from the uninterrupted run a after the cut at k."""
    bad = []
    t_k = float(b1.final["time"])
    rows = a.rows["row_event"]
    after = (rows > k) | ((rows == k) & (a.rows["row_time"] > t_k))
    for name, column in a.rows.items():
        if np.asarray(column)[after].tobytes() != np.asarray(b2.rows[name])[1:].tobytes():
            bad.append(f"rows.{name}")
        if name != "row_kind" and (
            np.asarray(b1.rows[name])[-1].tobytes() != np.asarray(b2.rows[name])[0].tobytes()
        ):
            bad.append(f"the cut's row: {name}")
    for group in ("trace", "diagnostics"):
        for name, column in getattr(a, group).items():
            if np.asarray(column)[k:].tobytes() != np.asarray(getattr(b2, group)[name]).tobytes():
                bad.append(f"{group}.{name}")
    bad += [f"final.{n}" for n in a.final if not np.array_equal(a.final[n], b2.final[n])]
    pa, pb = a.population, b2.population
    text = lambda x: json.dumps(x, default=str)  # noqa: E731
    if text([r for r in pa["lyses"] if r["time_s"] > t_k]) != text(pb["lyses"]):
        bad.append("lyses")
    if text(pa["transfers"][pb["numbering"]["transfers"] :]) != text(pb["transfers"]):
        bad.append("transfers")
    if pa["fissions"] is not None:
        start = pb["numbering"]["attempts"]
        for name, column in pa["fissions"].items():
            mine = np.asarray(column)[start:]
            theirs = np.zeros(0) if pb["fissions"] is None else pb["fissions"][name]
            if len(mine) and mine.tobytes() != np.asarray(theirs).tobytes():
                bad.append(f"fissions.{name}")
    joined = {life["key"]: dict(life) for life in b1.population["lives"]}
    for life in pb["lives"]:
        ends = {f: life[f] for f in ("end_time", "end_reason", "end_event")}
        joined[life["key"]] = (
            joined[life["key"]] | ends if life["birth_kind"] == "continued" else dict(life)
        )
    lives = {life["key"]: life for life in pa["lives"]}
    if text(sorted(lives.items())) != text(sorted(joined.items())):
        bad.append("lives")
    return bad


CUTS = [("lysis", "mid"), ("lysis", "before_lysis"), ("lysis", "after_lysis"),
        ("staged", "after_division"), ("staged", "before_transfer"),
        ("staged", "after_transfer")]  # fmt: skip


@pytest.mark.parametrize("world, where", CUTS)
def test_a_resumed_world_is_the_uninterrupted_world_after_the_cut(worlds, world, where, tmp_path):
    spec, a = worlds[world]
    k = cut(a, where)
    b1 = runner.run(spec, stop=k).check()
    assert b1.status == "stopped" and int(b1.final["events"]) == k
    checkpoints.write(tmp_path / "checkpoint", b1.checkpoint())
    saved = checkpoints.read(tmp_path / "checkpoint")
    b2 = runner.run(spec, start=saved).check()
    assert b2.start["checkpoint"] == saved.digest and b2.start["events"] == k
    assert differences(a, b1, b2, k) == []
    for name, run in (("b1", b1), ("b2", b2)):  # both bundles write, relations@2 included
        records.write_run(tmp_path / name, run)
        descriptor, _ = rel.read(tmp_path / name)
        assert descriptor["format"] == rel.FORMAT_V2
    continued = [life for life in b2.population["lives"] if life["birth_kind"] == "continued"]
    assert continued and all(life["birth_time"] == float(b1.final["time"]) for life in continued)
    if where == "after_transfer":  # a slot freed before the cut is taken by a daughter after it
        freed = set(a.population["transfers"][0]["removed"])
        born = {life["slot"] for life in b2.population["lives"] if life["birth_kind"] == "division"}
        assert {f"slot:{s}" for s in freed} & born


def remade(checkpoint, lane=None, host_arrays=None):
    """The checkpoint with changed state and a fresh digest (a plant, not a tampered file)."""
    from cells.definitions.specs import digest

    lane = {**checkpoint.lane, **(lane or {})}
    host = {"arrays": {**checkpoint.host["arrays"], **(host_arrays or {})},
            "doc": checkpoint.host["doc"]}  # fmt: skip
    clock = checkpoints.clock_of(lane)
    state = checkpoints.state_digest(lane, host)
    return dataclasses.replace(checkpoint, lane=lane, host=host, clock=clock, digest=digest(
        {"definition": checkpoint.fingerprint, "clock": clock, "state": state}))  # fmt: skip


def test_the_planted_restores_are_caught(worlds):
    spec, a = worlds["lysis"]
    k = cut(a, "after_lysis")
    b1 = runner.run(spec, stop=k).check()
    c = b1.checkpoint()
    assert differences(a, b1, runner.run(spec, start=c).check(), k) == []
    # Planted: the draw at the cut counted twice (as if a crossing draw were spent there).
    twice = remade(c, lane={"counter": np.asarray(c.lane["counter"] + 1)})
    moved = differences(a, b1, runner.run(spec, start=twice).check(), k)
    assert "trace.event_time" in moved
    # Planted: the device's heat sum restored from the bundle's heat column, which also holds the
    # host's lysis heat (the lane's own sum is the device's alone).
    column = b1.rows["event_heat_kT"][-1]
    assert column != c.lane["heat"]
    rebuilt = remade(c, lane={"heat": np.asarray(np.float64(column))})
    with pytest.raises(runner.LedgerRefused, match="does not close"):
        runner.run(spec, start=rebuilt).check()


def test_the_checkpoint_refusals(worlds, tmp_path):
    spec, a = worlds["lysis"]
    e = a.population["lyses"][0]["event"]
    with pytest.raises(ConfigError, match="lysed a vesicle"):  # its time needs same-time order
        runner.run(spec, stop=e).check().checkpoint()
    k = cut(a, "mid")
    c = runner.run(spec, stop=k).check().checkpoint()
    with pytest.raises(ConfigError, match="taken of a run stopped"):
        a.checkpoint()  # a run that ended at its horizon
    d = spec.to_dict()
    d["execution"]["stream"]["branch"] = 1
    with pytest.raises(ConfigError, match="not .*execution.stream.branch"):
        runner.run(parse_spec(d), start=c)
    d = spec.to_dict()
    d["model"]["world"]["founder"]["L@pool"] += 1
    with pytest.raises(ConfigError, match="not .*model.world.founder"):
        runner.run(parse_spec(d), start=c)
    d = spec.to_dict()
    d["experiment"]["time_horizon_s"] = float(c.clock["time"]) / 2
    with pytest.raises(ConfigError, match="ends after the checkpoint's time"):
        runner.run(parse_spec(d), start=c)
    for stop in (0, spec.experiment.event_limit, 2.0):
        with pytest.raises(ConfigError, match="A stop is an event count"):
            runner.run(spec, stop=stop)
    single = dataclasses.replace(
        spec, execution=dataclasses.replace(spec.execution, mode="single_lineage")
    )
    with pytest.raises(ConfigError, match="rung S"):
        runner.run(single, stop=3)
    # The files: a changed lane file, a changed source, a state that no longer matches its digest.
    path = checkpoints.write(tmp_path / "c", c)
    with np.load(path / "lane.npz") as saved:
        lane = {name: saved[name] for name in saved.files}
    lane["time"] = np.asarray(lane["time"] + 1.0)
    np.savez(path / "lane.npz", **lane)
    with pytest.raises(ConfigError, match="lane file's checksum differs"):
        checkpoints.read(path)
    record = json.loads((path / "checkpoint.json").read_text())
    from cells.records.io import _sha256

    record["lane_sha256"] = _sha256(path / "lane.npz")
    (path / "checkpoint.json").write_text(json.dumps(record))
    with pytest.raises(ConfigError, match="does not match the checkpoint's digest"):
        checkpoints.read(path)
    record["source_hashes"] = {**record["source_hashes"], "planted.py": "0" * 64}
    (path / "checkpoint.json").write_text(json.dumps(record))
    with pytest.raises(ConfigError, match="engine source differs"):
        checkpoints.read(path)
