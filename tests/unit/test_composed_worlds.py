"""Composed worlds (G-7): ionic definitions whose channels assembly pools drive, from the composed
file to a run (cells.assembly_pool.schedule and resolve; the pool's own rows, and the direct walk of
its kernel that these use, are in test_assembly_pool.py).

Host side, on two held-bath cells, with planted errors that must fail each row (D187):
- a driven schedule is the declared one times the level, right-continuous (planted: the level
  alone, the base schedule alone, a left-continuous reading, switches rounded to the steps);
- a near miss is what the clock itself refuses, at the coarse, the fine and the end points; the
  driver refuses it naming the world, the pool and the switch, or declares it at its point and
  records the shift (planted: every switch rounded, and the shift left out);
- resolve writes the same bytes for the same file, in definitions that parse, hold the pools' paths
  in their own channels' schedules and nothing else new, and run as a batch by the planner's own
  bounds; its records say the file, the seeds and the switches (planted: the owners swapped, a
  schedule object shared by two controls, and records without the seeds);
- the refusals of a composed file, each by its name, and a pool's fault by its world and event cap.

Compiled, in one row (about 15 s of it, IMEX; the RK4 program of this world compiles for 40): a two-
cell world with a near and a far outside node (two free field offsets, so the floor solver, D147),
run by the command line with its inputs, conducts exactly where its pools' levels say, and is bit
for bit the run of a definition whose schedules were written by hand from the kernel's walk
(planted: the other pool's path, the levels of the step's start on the grid, and a path read one
event early or late).
"""

import copy
import hashlib
import json
import math
import os
from bisect import bisect_left
from types import SimpleNamespace

import numpy as np
import pytest

from cells.__main__ import main
from cells.assembly.spec import AssemblyError
from cells.assembly_pool import resolve, schedule
from cells.assembly_pool.io import load_checkpoint
from cells.assembly_pool.spec import parse_spec as parse_pool
from cells.definitions import pump_composite_spec
from cells.definitions.specs import ConfigError, load_spec, parse_spec, read_json
from cells.execution.batch import load_batch, parse_batch, plan_batch
from cells.execution.grid import EventGrid
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures
from tests.unit.test_assembly_pool import DRIVING, LEVELS, SEEDS, direct_path, walked
from validation.tissue import cell_replacement_fixtures as replacement
from validation.tissue import field_solver_choice
from validation.tissue import membrane_trafficking_fixtures as trafficking
from validation.tissue import surface_pump_v3_fixtures as tissue

OBSERVABLE = "root_component_has_cycle@1"
# configure_caches() sets these in os.environ; setting them through a MonkeyPatch restores them.
CACHES = (
    "TMPDIR",
    "XDG_CACHE_HOME",
    "CUDA_CACHE_PATH",
    "JAX_COMPILATION_CACHE_DIR",
    "XLA_PYTHON_CLIENT_PREALLOCATE",
    "PYTHONDONTWRITEBYTECODE",
)
BASE = {  # The declared schedules of the held-bath cells' channels.
    "kir_0": [(0.0, 0.8), (0.00023, 0.25), (0.00083, 1.0)],  # Both changes off the steps.
    "nav_0": [(0.0, 1.0)],
    "kir_1": [(0.0, 0.5), (0.0004, 0.75)],
    "nav_1": [(0.0, 1.0), (0.005, 0.5)],
}
DRIVEN = (["kir_0", "nav_0"], ["kir_1"])  # Each pool's channels; nav_1 is driven by none.


def controls(schedules):
    return [
        {
            "channel_id": channel,
            "schedule": [{"time": t, "availability": a} for t, a in changes],
        }
        for channel, changes in schedules.items()
    ]


def held_bath_cells(*, max_steps=400):
    """Two independent cells, each on its held bath, with two channel populations each."""
    states = tissue.HEREDITY_STATES
    raw = tissue.heredity_cells([states["H"][:4], states["D"][:4]], dt=1e-4, end_time=0.02)
    raw["experiment"]["channel_controls"] = controls(BASE)
    raw["execution"]["max_steps"] = max_steps
    return raw


def composed_file(ionic=None, *, seeds=SEEDS, channels=DRIVEN, levels=LEVELS, **pool):
    return {
        "schema_version": 1,
        "ionic": held_bath_cells() if ionic is None else ionic,
        "pools": [
            {
                "channels": list(given),
                "observable": OBSERVABLE,
                "levels": dict(levels),
                "pool": DRIVING | {"model": "finite_bond_assembly@1", "seed": seed} | pool,
            }
            for given, seed in zip(channels, seeds, strict=True)
        ],
    }


@pytest.fixture(scope="module")
def composed():
    return resolve.parse_composed(composed_file())


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    """A folder that the command line may write under, its cache variables restored after."""
    monkeypatch.setenv("CELLS_OUTPUT_ROOT", str(tmp_path))
    for name in CACHES:
        monkeypatch.setenv(name, os.environ.get(name, ""))
    return tmp_path


def held(points, time):
    """The value of a right-continuous list of (time, value, ...) at a time, by a scan."""
    return [p[1] for p in points if p[0] <= time][-1]


def product(base, path):
    """The schedule of base x level, written from the definition's schedule and a path."""
    times = sorted({p[0] for p in (*base, *path)})
    return [(t, held(base, t) * held(path, t)) for t in times]


def hand_path(*switches, end=0.02, first=1.0):
    """A SwitchPath of (time, level) switches, each the next event."""
    times, levels = zip((0.0, first), *switches, strict=True)
    return schedule.SwitchPath(times, levels, tuple(range(len(times))), end, len(times) - 1)


# ------------------------------------------------------------------ the schedule


def test_a_driven_schedule_is_base_times_level_right_continuous():
    pool = parse_pool(DRIVING | {"seed": SEEDS[0]})
    points = direct_path(pool, 1)
    assert len(points) > 10
    times, levels, counts = zip(*points, strict=True)
    path = schedule.SwitchPath(times, levels, counts, pool.end_time_s, 1000)
    base = BASE["kir_0"]
    inside = [t for t, _ in base[1:]]  # The base changes between switches, under either level.
    assert all(times[1] < t < times[-1] for t in inside)
    assert {held(points, t) for t in inside} == {0.0, 1.0}
    half = schedule.SwitchPath(
        times, tuple(0.25 + v / 2 for v in levels), counts, pool.end_time_s, 1000
    )
    for given in (path, half):
        drive = schedule.ChannelDrive("kir_0", tuple(base), given)
        got = drive.schedule()
        expected = list(zip(given.times, given.levels, strict=True))
        assert list(got) == product(base, expected) and not drive.clashes()
        changes = sorted({*times, *(t for t, _ in base)})
        probes = [
            t
            for c in changes
            for t in (np.nextafter(c, 0.0), c, np.nextafter(c, 1.0))
            if 0 <= t <= pool.end_time_s
        ] + [(a + b) / 2 for a, b in zip(changes, changes[1:], strict=False)]
        right = [held(base, t) * held(expected, t) for t in probes]
        assert [held(got, t) for t in probes] == right
        # Planted: the level alone, the base alone, a left-continuous reading, rounded switches.
        before = [times[max(bisect_left(times, t) - 1, 0)] for t in probes]
        rounded = [(round(t / 1e-4) * 1e-4, v) for t, v in expected]
        for wrong in (
            [held(expected, t) for t in probes],
            [held(base, t) for t in probes],
            [held(base, t) * held(expected, b) for t, b in zip(probes, before, strict=True)],
            [held(base, t) * held(rounded, t) for t in probes],
        ):
            assert wrong != right
    with pytest.raises(ConfigError, match="starts at 0, increases within its end"):
        schedule.SwitchPath((0.0, 0.03), (1.0, 0.0), (0, 1), 0.02, 1)


def test_two_switches_at_one_point_leave_the_later_level():
    path = hand_path((0.0010, 0.0), (0.0012, 1.0), (0.005, 0.0))
    one = schedule.moved(path, {0.0010: 0.0011, 0.0012: 0.0011})
    assert list(zip(one.times, one.levels, one.counts, strict=True)) == [
        (0.0, 1.0, 0),
        (0.005, 0.0, 3),  # The two cancel: no change of level is left at their point.
    ]
    start = schedule.moved(path, {0.0010: 0.0})
    assert (start.times[0], start.levels[0], start.counts[0]) == (0.0, 0.0, 1)
    assert schedule.moved(path, {}) == path


# ------------------------------------------------------------------ near misses


def declared_at(time, fine=False):
    """The held-bath cells with one more change, of nav_1, at `time`."""
    raw = held_bath_cells()
    raw["experiment"]["channel_controls"] = controls(BASE | {"nav_1": [(0.0, 1.0), (time, 0.5)]})
    if fine:
        raw["execution"]["fine_windows"] = {
            "method": "fixed_fine_windows@1",
            "dt": 2.5e-5,
            "windows": [{"start_time": 0.001, "end_time": 0.002}],
        }
    return raw


DT = 1e-4
MISSES = [  # (a point of the clock, its step, the step it would split, times the offset, missed)
    (37 * DT, DT, 0.0, False),
    (37 * DT, DT, 1e-9, True),
    (37 * DT, DT, -1e-9, True),
    (37 * DT, DT, 0.999e-6, True),
    (37 * DT, DT, -0.999e-6, True),
    (37 * DT, DT, 1.01e-6, False),
    (37 * DT, DT, 0.5, False),
    (0.0, DT, 1e-9, True),
    (0.02, DT, -1e-9, True),
    (0.02, DT, -0.4, False),
]


@pytest.mark.parametrize("fine", [False, True])
def test_a_near_miss_is_what_the_clock_refuses(fine):
    spec = parse_spec(declared_at(0.5 * DT, fine))
    rows = list(MISSES)
    for ulps, missed in ((1, False), (3, False), (9, True)):
        rows.append((37 * DT, DT, ulps * math.ulp(37 * DT) / DT, missed))
    if fine:  # A fine point inside the window, between two coarse ones.
        rows += [(41 * 2.5e-5, 2.5e-5, 1e-9, True), (41 * 2.5e-5, 2.5e-5, 0.3, False)]
    else:
        rows += [(41 * 2.5e-5, DT, 1e-9, False)]
    for point, step, offset, missed in rows:
        time = point + offset * step
        assert (schedule.missed_point(spec, time) == point) is missed, (point, offset)
        assert missed or schedule.missed_point(spec, time) is None
        if missed:  # The clock itself, on a definition that declares the time.
            with pytest.raises(ConfigError, match="a near miss, D283"):
                EventGrid(parse_spec(declared_at(time, fine)))
            continue
        declared = parse_spec(declared_at(time, fine))
        changes = [c.time for c in declared.experiment.changes]
        assert schedule.step_count(spec, changes) == len(EventGrid(declared)) - 1


def test_a_near_miss_is_refused_by_name_or_declared_at_its_point(composed, monkeypatch):
    point = 37 * DT
    near, off = point + 1e-9 * DT, 60.25 * DT
    paths = [hand_path((0.5 * DT, 0.0)), hand_path((near, 0.25), (off, 0.75))]
    with pytest.raises(
        ConfigError,
        match=rf"World 5, pool 1: its switch at {near!r} s \(event 1\) misses the clock's point "
        rf"{point!r} by .* \(a near miss, D283\)",
    ):
        resolve.resolve_world(composed, 5, paths)
    world = resolve.resolve_world(composed, 5, paths, resolve.TO_GRID)
    assert world.declared[1].times == (0.0, point, off) and world.declared[0] == paths[0]
    (control,) = [
        c
        for c in json.loads(world.text)["experiment"]["channel_controls"]
        if c["channel_id"] == "kir_1"
    ]
    assert [(c["time"], c["availability"]) for c in control["schedule"]] == product(
        BASE["kir_1"], [(0.0, 1.0), (point, 0.25), (off, 0.75)]
    )
    # The steps: the base's two changes off the grid, and the two switches off it.
    assert world.steps == len(EventGrid(world.spec)) - 1 == 200 + 2 + 2
    rows = resolve.switches_of(world)
    assert [(r["pool"], r["time"], r.get("declared"), r.get("shift_s")) for r in rows] == [
        (0, 0.5 * DT, None, None),
        (1, near, point, point - near),
        (1, off, None, None),
    ]
    # Planted: every switch rounded to a point, where only the near one is declared at its own.
    rounded = [round(t / DT) * DT for t in world.declared[1].times]
    assert rounded != list(world.declared[1].times) and rounded[1] == point
    # A change of the same channel at the same instant, to the clock, is refused by name.
    change = BASE["kir_1"][1][0]
    beside = [paths[0], hand_path((np.nextafter(change, 1.0), 0.0))]
    with pytest.raises(ConfigError, match="World 5, pool 1: its switch at .* is the same instant"):
        resolve.resolve_world(composed, 5, beside)
    # A clock of more steps than the definition's limit, by its own count.
    tight = resolve.parse_composed(composed_file(held_bath_cells(max_steps=203)))
    with pytest.raises(
        ConfigError,
        match=r"World 5: its clock takes 204 steps \(200 without a change\), more .* 203",
    ):
        resolve.resolve_world(tight, 5, [hand_path((off, 0.0)), hand_path((off + DT, 0.0))])


# ------------------------------------------------------------------ the composed file's outputs


def shared(value, seen=None):
    """The objects that a JSON value holds more than once."""
    seen = set() if seen is None else seen
    if not isinstance(value, (dict, list)):
        return []
    if id(value) in seen:
        return [value]
    seen.add(id(value))
    items = value.values() if isinstance(value, dict) else value
    return [found for item in items for found in shared(item, seen)]


def expected_definition(data, world, *, owners=(0, 1), round_to=None, level_only=False):
    """A world's definition as the walk of its pools says. The options plant errors in it."""
    raw = copy.deepcopy(data["ionic"])
    for control in raw["experiment"]["channel_controls"]:
        for k, entry in enumerate(data["pools"]):
            if control["channel_id"] not in entry["channels"]:
                continue
            pool = parse_pool(data["pools"][owners[k]]["pool"])
            path = direct_path(pool, world, entry["levels"])
            if round_to is not None:
                path = [(round(t / round_to) * round_to, *rest) for t, *rest in path]
            base = [(0.0, 1.0)] if level_only else BASE[control["channel_id"]]
            control["schedule"] = [{"time": t, "availability": a} for t, a in product(base, path)]
    return raw


def test_resolve_writes_the_pools_paths_and_says_where_they_came_from(outputs, capsys):
    data = composed_file(worlds=2)
    given = outputs / "composed.json"
    given.write_text(json.dumps(data, indent=3))
    argv = ["assembly-pool", "resolve", str(given), "--output"]
    assert main([*argv, str(outputs / "first"), "--batch", str(2**31)]) == 0
    assert json.loads(capsys.readouterr().out)["worlds"] == 2
    resolve.resolve(given, outputs / "second", max_working_bytes=2**31)
    first, second = outputs / "first", outputs / "second"
    files = ["composed.json", "inputs.json", "resolution.json", "batch.json"]
    files += [f"worlds/world-{w}.json" for w in range(2)]
    for name in files:  # The same file, the same bytes.
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    assert (first / "composed.json").read_bytes() == given.read_bytes()

    pools = [parse_pool(entry["pool"]) for entry in data["pools"]]
    paths = [[direct_path(pool, w) for w in range(2)] for pool in pools]
    inputs, resolution = read_json(first / "inputs.json"), read_json(first / "resolution.json")
    definitions = [read_json(first / f"worlds/world-{w}.json") for w in range(2)]
    for w, definition in enumerate(definitions):
        assert definition == expected_definition(data, w)  # Only the driven channels' schedules.
        for planted in (
            dict(owners=(1, 0)),  # The owners swapped (a pool given the other's walk).
            dict(round_to=DT),  # Switches rounded to the steps.
            dict(level_only=True),  # The base schedule left out.
        ):
            assert definition != expected_definition(data, w, **planted)
        assert definition["experiment"]["channel_controls"] != controls(BASE)  # Not the ionic side.
        assert shared(definition) == []
    # Planted: a schedule object two controls share, which is found, and which parse_composed's
    # own copy of a definition built in Python never keeps.
    aliased = held_bath_cells()
    one = aliased["experiment"]["channel_controls"]
    one[3]["schedule"] = one[1]["schedule"]
    assert shared(aliased) == [one[1]["schedule"]]
    kept = resolve.parse_composed(composed_file(aliased))
    assert shared(resolve.driven_definition(kept.raw, {"nav_0": ((0.0, 0.5),)})) == []
    assert one[3]["schedule"] == [{"time": 0.0, "availability": 1.0}]

    # inputs.json: the file, the pools, the seeds, the rule and every world's switches.
    assert inputs["composed_file_sha256"] == hashlib.sha256(given.read_bytes()).hexdigest()
    assert inputs["ionic_sha256"] == parse_spec(data["ionic"]).fingerprint
    seeds = [p.get("seed") for p in inputs["pools"]]
    assert seeds == [pool.seed for pool in pools]
    for row, pool, entry in zip(inputs["pools"], pools, data["pools"], strict=True):
        assert row["pool_sha256"] == pool.fingerprint
        assert {k: row[k] for k in ("channels", "observable", "levels")} == {
            k: entry[k] for k in ("channels", "observable", "levels")
        }
    specs = [load_spec(first / f"worlds/world-{w}.json") for w in range(2)]
    batch = load_batch(first / "batch.json")
    prints = [spec.fingerprint for spec in specs]
    assert inputs["definitions_sha256"] == [*prints, batch.fingerprint]
    for w, row in enumerate(inputs["worlds"]):
        switches = sorted(
            (time, k, level, event) for k in (0, 1) for time, level, event in paths[k][w][1:]
        )
        assert [(s["time"], s["pool"], s["level"], s["event"]) for s in row["switches"]] == switches
        assert (row["world"], row["definition_sha256"]) == (w, prints[w])

    # resolution.json: the same, and how the schedules were made, as the pools' own records say.
    for w, row in enumerate(resolution["worlds"]):
        assert row["switches"] == inputs["worlds"][w]["switches"]
        assert row["steps"] == len(EventGrid(specs[w])) - 1 and row["snapped"] == []
        for k, made in enumerate(row["pools"]):
            rows, final = walked(pools[k], w)
            assert made["events"] == len(rows) and made["initial_level"] == paths[k][w][0][1]
            ends = [p[0] for p in paths[k][w][1:]] + [pools[k].end_time_s]
            assert made["exposure_s"] == math.fsum(
                p[1] * (end - p[0]) for p, end in zip(paths[k][w], ends, strict=True)
            )
            _, saved, _ = load_checkpoint(first / f"pools/pool-{k:03}/checkpoint")
            for name, value in final._asdict().items():
                recorded = made["final"][name]
                value = np.asarray(value)
                if recorded is None:
                    assert not np.isfinite(value) and name == "pending_time_s"
                    continue
                again = np.asarray(recorded, dtype=value.dtype)
                assert (
                    again.tobytes()
                    == value.tobytes()
                    == saved[saved._fields.index(name)][w].tobytes()
                ), name

    # The batch holds the same definitions, admitted by its planner at its own bounds.
    assert [w.simulation for w in batch.worlds] == specs
    assert [w.world_id for w in batch.worlds] == [1, 2]
    assert plan_batch(batch).padded_step_bound == batch.max_padded_steps
    fewer = read_json(first / "batch.json")
    fewer["execution"]["max_padded_steps"] -= 1
    with pytest.raises(ConfigError, match="max_padded_steps"):
        plan_batch(parse_batch(fewer))

    # Planted: another seed, level, channel or ionic number changes the inputs; a record that
    # leaves the seed out does not say it.
    made = resolve.parse_composed(data)
    worlds = [
        resolve.resolve_world(made, w, [as_path(paths[k][w], pools[k]) for k in (0, 1)])
        for w in range(2)
    ]
    options = dict(file_sha256=inputs["composed_file_sha256"], near_misses=resolve.REFUSE)
    again = resolve.inputs_record(made, worlds, batch=batch.fingerprint, **options)
    assert json.loads(json.dumps(again)) == inputs
    for changed in (
        composed_file(seeds=(SEEDS[0], 7), worlds=2),
        composed_file(levels={"false": 0.0, "true": 0.5}, worlds=2),
        composed_file(channels=(["kir_0"], ["kir_1"]), worlds=2),
        composed_file(k_off_s_inv=401.0, worlds=2),
    ):
        other = resolve.parse_composed(changed)
        assert resolve.inputs_record(other, worlds, **options)["pools"] != inputs["pools"]
        assert other.fingerprint != made.fingerprint
    bare = {k: v for k, v in resolve.pool_record(made.drives[0]).items() if k != "seed"}
    assert [bare.get("seed")] != seeds[:1]


def as_path(points, pool):
    times, levels, counts = zip(*points, strict=True)
    return schedule.SwitchPath(times, levels, counts, pool.end_time_s, counts[-1])


# ------------------------------------------------------------------ the refusals


def put(path, value):
    """A change of a composed file: the value at a path of keys."""

    def change(data):
        target = data
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return change


def pool(k, **values):
    def change(data):
        data["pools"][k]["pool"] |= values

    return change


def drop(*path):
    def change(data):
        target = data
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return change


REFUSALS = [
    (put(["extra"], 1), r"composed definition: missing=\[\], unknown=\['extra'\]"),
    (drop("pools"), r"composed definition: missing=\['pools'\]"),
    (put(["schema_version"], 2), "Only schema_version 1"),
    (put(["schema_version"], True), "Only schema_version 1"),
    (put(["ionic"], []), "The ionic definition's model is one of .*, not None"),
    (put(["ionic", "model", "id"], "resolved_pump_tissue@2"), "not 'resolved_pump_tissue@2'"),
    (put(["ionic", "experiment", "extra"], 1), "unknown"),
    (put(["pools"], []), "pools is a non-empty list"),
    (put(["pools"], {}), "pools is a non-empty list"),
    (put(["pools", 1, "stream"], 1), r"pool 1: missing=\[\], unknown=\['stream'\]"),
    (drop("pools", 0, "levels"), r"pool 0: missing=\['levels'\]"),
    (put(["pools", 0, "channels"], []), "Pool 0: channels is a non-empty list of distinct"),
    (put(["pools", 0, "channels"], ["kir_0", "kir_0"]), "Pool 0: channels is a non-empty list"),
    (put(["pools", 0, "channels"], "kir_0"), "Pool 0: channels is a non-empty list"),
    (put(["pools", 1, "channels"], ["kv_9"]), "Pool 1: 'kv_9' is no channel of the ionic"),
    (put(["pools", 1, "channels"], ["nav_0"]), "Channel 'nav_0' is set by pools 0 and 1"),
    (put(["pools", 0, "observable"], "root_component_has_cycle"), "Pool 0: Unknown assembly obs"),
    (put(["pools", 1, "observable"], "kv1p5_mh@1"), "Pool 1: Unknown .* observable 'kv1p5_mh@1'"),
    (put(["ionic", "experiment", "end_time"], math.inf), "end time must be finite"),
    (drop("pools", 0, "levels", "true"), r"pool 0: levels: missing=\['true'\]"),
    (put(["pools", 0, "levels", "maybe"], 0.5), r"pool 0: levels: .*unknown=\['maybe'\]"),
    (put(["pools", 0, "levels", "true"], 1.5), r"pool 0: the level of 'true' must lie in \[0, 1\]"),
    (put(["pools", 0, "levels", "true"], -0.1), "pool 0: the level of 'true' must be finite"),
    (put(["pools", 0, "levels", "true"], math.nan), "pool 0: the level of 'true' must be finite"),
    (put(["pools", 0, "levels", "true"], True), "pool 0: the level of 'true' must be a finite"),
    (pool(1, stream_id=1), "Pool 1: Unknown finite-bond assembly definition fields"),
    (pool(1, k_off_s_inv=-1.0), "Pool 1: k_off_s_inv must be finite and nonnegative"),
    (pool(1, recording="summary"), "Pool 1 declares recording 'summary': .* declares \"events\""),
    (pool(1, end_time_s=0.01), "Pool 1's horizon, end_time_s = 0.01, is not .* end_time = 0.02"),
    (pool(1, end_time_s=0.04), "Pool 1's horizon, end_time_s = 0.04, is not"),
    (pool(1, worlds=3), "Pool 1 declares 3 worlds from ID 0, and pool 0 4 from ID 0"),
    (pool(1, world_id_start=4), "Pool 1 declares 4 worlds from ID 4, and pool 0 4 from ID 0"),
    (pool(1, seed=SEEDS[0]), f"Pools 0 and 1 have one seed, {SEEDS[0]}"),
    (
        put(["ionic", "experiment", "channel_controls", 3, "schedule", 1, "time"], 5e-3 + 1e-13),
        "a near miss, D283",
    ),
]


@pytest.mark.parametrize("change,reason", REFUSALS, ids=[str(i) for i in range(len(REFUSALS))])
def test_a_composed_file_is_refused_by_name(change, reason):
    data = composed_file()
    change(data)
    with pytest.raises(ConfigError, match=reason):
        resolve.parse_composed(data)


def test_a_refused_file_leaves_no_output_and_a_faulted_pool_is_named(outputs, capsys):
    given = outputs / "composed.json"
    given.write_text(json.dumps(composed_file())[:-1] + ', "pools": []}')
    out = outputs / "refused"
    assert main(["assembly-pool", "resolve", str(given), "--output", str(out)]) == 2
    assert "Duplicate JSON field: pools" in capsys.readouterr().err and not out.exists()
    given.write_text(json.dumps(composed_file(max_events_per_world=12)))
    with pytest.raises(
        AssemblyError,
        match=r"Pool 0, world 1: it reached its event cap, max_events_per_world = 12, at 0\.\d+ s",
    ):
        resolve.resolve(given, out)
    assert "event cap" in read_json(out / "failure.json")["error"]
    assert (out / "pools/pool-000/failure.json").exists() and not (out / "worlds").exists()


def test_an_operator_that_ends_or_empties_a_driven_cell_is_refused():
    sheet = replacement.heredity_sheet(1, 0, end_time=0.01)
    replaced = replacement.with_replacement(
        sheet,
        [replacement.template_from_cell(sheet, "cell_1", "h")],
        [(0.005, "cell_0", "h", "n1")],
    )
    pooled = trafficking.pooled_cells(2)
    route = trafficking.route(pooled, 0)
    plan = trafficking.schedule(route["id"], [(0.0, trafficking.rate(pooled, 0, 0.1))])
    cases = [
        (
            pump_composite_spec.frozen_definition(replaced),
            "kir_0",
            "scheduled_cell_replacement@1 replaces cell cell_0",
            "kir_1",
        ),
        (
            partition_fixtures.divided(),
            "kir_0",
            "isopotential_partition@1 begins or ends cell cell_0",
            None,
        ),
        (
            partition_fixtures.divided(),
            "kir_0_d1",
            "isopotential_partition@1 begins or ends cell d1",
            None,
        ),
        (
            trafficking.with_trafficking(pooled, [route], [plan]),
            "kir_0",
            "scheduled_membrane_trafficking@1 moves channels out of cell cell_0",
            "kir_1",
        ),
    ]
    for raw, channel, reason, beside in cases:
        options = dict(seeds=(1,), end_time_s=raw["experiment"]["end_time"])
        with pytest.raises(ConfigError, match=reason + ".*would outlive the cell"):
            resolve.parse_composed(composed_file(raw, channels=([channel],), **options))
        if beside is not None:  # Another cell of the same world.
            assert resolve.parse_composed(composed_file(raw, channels=([beside],), **options))
    # Planted: an operator that replaces or retires cells and names none reaches every cell.
    spec = parse_spec(partition_fixtures.divided())
    blind = SimpleNamespace(
        LAW_ID="tests.blind@1",
        RETIRES=True,
        EVENT_REPLACES={"amount_increment": ()},
        living_intervals=lambda *_: {},
    )
    entries = ((blind, None, (SimpleNamespace(time=0.001),)),)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(resolve.composite, "entries", lambda _: entries)
        assert {row[2] for row in resolve.lifecycles(spec, {"cell_0": 0})} == {"cell_0"}
        blind.RETIRES, blind.EVENT_REPLACES = False, {}
        assert resolve.lifecycles(spec, {"cell_0": 0}) == ()


# ------------------------------------------------------------------ a composed run

VALENCE = {"Na": 1, "K": 1, "Cl": -1}
INSIDE = {"Na": 12.0, "K": 140.0, "Cl": 10.0}  # mM
OUTSIDE = {"Na": 145.0, "K": 5.0, "Cl": 150.0}
NEAR_FAR_DT, NEAR_FAR_END = 2.5e-5, 0.001
AVAILABLE = 0.8  # Every channel's declared availability.


def near_far():
    """Two cells, one on a near and one on a far finite outside node, the nodes joined in a line to
    a held bath by faces and the cells by one gated junction; each cell with Kv1.5 and an
    always-open K leak. Synthetic numbers. The two outside components float: two free field
    offsets."""
    capacitance = 1e-12
    charge = -0.06 * capacitance

    def owner(name, volume, concentrations, held_charge, **more):
        amounts = {s: c * volume for s, c in concentrations.items()}
        background = math.fsum(VALENCE[s] * a for s, a in amounts.items())
        return dict(
            id=name,
            volume_pL=volume,
            initial_amount_fmol=amounts,
            fixed_charge_equivalent_fmol=held_charge / CHARGE_PER_FMOL - background,
            initial_charge_C=held_charge,
            **more,
        )

    def always(kind, name, availability=1.0):
        return {
            f"{kind}_id": name,
            "schedule": [{"time": 0.0, "availability": availability}],
        }

    membranes = [
        dict(
            id=f"membrane_{k}",
            inside=f"cell_{k}",
            outside=outside,
            area_m2=1e-10,
            capacitance_F=capacitance,
            permeability_m_per_s=dict(Na=2e-10, K=4e-10, Cl=1e-10),
            law="constant_field@1",
            pump=None,
            calcium_pump=None,
        )
        for k, outside in enumerate(("near", "far"))
    ]
    channels = [
        dict(
            id=f"{name}_{k}",
            membrane_id=f"membrane_{k}",
            kinetic_law=law,
            max_permeability_m_per_s=permeability,
            abundance=1.0,
            initial_gate=list(gate),
            permeant_ions=[dict(species_id="K", relative_permeability=1.0)],
        )
        for k in (0, 1)
        for name, law, permeability, gate in (
            ("kv", "kv1p5_mh@1", 3e-8, (0.2, 0.7)),
            ("leak", "kleak_always_open@1", 1e-8, ()),
        )
    ]
    finite = dict(reservoir=False, boundary_potential_V=0.0)
    return dict(
        schema_version=1,
        model=dict(
            id="resolved_pump_tissue@3",
            temperature_K=298.15,
            species=[dict(id=s, valence=z) for s, z in VALENCE.items()],
            cells=[owner("cell_0", 1.0, INSIDE, charge), owner("cell_1", 1.5, INSIDE, charge)],
            extracellular=[
                owner("near", 2.0, OUTSIDE, -charge, **finite),
                owner("far", 3.0, OUTSIDE, -charge, **finite),
                owner("bath", 1.0, OUTSIDE, 0.0, reservoir=True, boundary_potential_V=0.0),
            ],
            membranes=membranes,
            junctions=[
                dict(
                    id="junction_0",
                    sender="cell_0",
                    receiver="cell_1",
                    area_m2=1e-12,
                    permeability_m_per_s=dict.fromkeys(VALENCE, 1e-9),
                    law="constant_field@1",
                    gate=dict(
                        law="junction_voltage_relaxation@1",
                        threshold_voltage_V=0.015,
                        minimum_open_fraction=0.1,
                        initial_gate=0.6,
                    ),
                )
            ],
            faces=[
                dict(
                    id=f"{a}_{b}",
                    sender=a,
                    receiver=b,
                    area_m2=1e-10,
                    length_m=1e-5,
                    diffusivity_m2_per_s=dict(Na=1e-11, K=2e-11, Cl=2e-11),
                    law="logmean_electrodiffusion@1",
                )
                for a, b in (("near", "far"), ("far", "bath"))
            ],
            closure=dict(
                law="resolved_capacitor_components_current_continuity@1", gauge_reference=None
            ),
            channels=channels,
        ),
        experiment=dict(
            end_time=NEAR_FAR_END,
            observation_times=[0.0, NEAR_FAR_END],
            membrane_controls=[always("membrane", p["id"]) for p in membranes],
            junction_controls=[always("junction", "junction_0")],
            pump_controls=[],
            calcium_pump_controls=[],
            channel_controls=[always("channel", c["id"], AVAILABLE) for c in channels],
        ),
        execution=dict(
            dt=NEAR_FAR_DT,
            capacity=2,
            extracellular_capacity=3,
            membrane_capacity=2,
            edge_capacity=1,
            face_capacity=2,
            channel_capacity=len(channels),
            backend="cpu",
            jit=True,
            precision="float64",
            solver="imex_ars222_face_electromigration@1",
            field_solver="capacitive_reduction_gauged_damped_newton@2",
            max_steps=400,
            max_trace_bytes=2**30,
            material_balance_atol_fmol=dict.fromkeys(VALENCE, 1e-10),
        ),
    )


NEAR_FAR_CHANNELS = (["kv_0", "leak_0"], ["leak_1"])  # kv_1 is driven by none.
FAST = dict(  # The driving pools five times faster, over the composed run's horizon: one world.
    worlds=1,
    world_id_start=1,
    end_time_s=NEAR_FAR_END,
    k_on_M_inv_s=1.5e10,
    k_close_s_inv=20000.0,
    k_off_s_inv=2000.0,
)


def near_far_file(ionic):
    data = composed_file(ionic, channels=NEAR_FAR_CHANNELS, **FAST)
    data["pools"][1]["levels"] = {"false": 0.0, "true": 0.5}
    return data


def conducts(times, transferred, level_at):
    """Whether a channel moved K on exactly the steps whose level is above 0: not at all where it
    is 0, bit for bit, and some where it is not. A step's level is the one at its start."""
    still = transferred[1:] == transferred[:-1]
    return np.array_equal(~still, [level_at(t) > 0 for t in times[:-1]])


def test_a_composed_world_conducts_exactly_on_its_pools_paths(outputs):
    raw = near_far()
    assert field_solver_choice.free_field_offsets(raw) == 2
    sparse = copy.deepcopy(raw)
    sparse["execution"]["field_solver"] = "sparse_capacitive_reduction_gauged_damped_newton@1"
    for wrong in (raw, sparse):  # D147: two free offsets, and no floor.
        with pytest.raises(ConfigError, match=r"has 2 free field offsets and declares .* \(D147\)"):
            resolve.parse_composed(near_far_file(wrong))
    declared = field_solver_choice.declare(raw)
    data = near_far_file(declared)
    given = outputs / "composed.json"
    given.write_text(json.dumps(data))
    summary = resolve.resolve(given, outputs / "resolved")
    assert summary["worlds"] == 1 and not (outputs / "resolved/batch.json").exists()
    definition = outputs / "resolved/worlds/world-1.json"
    recorded = outputs / "resolved/inputs.json"
    argv = ["run", str(definition), "--output", str(outputs / "run")]
    assert main([*argv, "--inputs", str(recorded)]) == 0

    pools = [parse_pool(entry["pool"]) for entry in data["pools"]]
    paths = [
        direct_path(p, 0, entry["levels"]) for p, entry in zip(pools, data["pools"], strict=True)
    ]
    assert all(len(path) > 10 for path in paths)
    switches = {p[0] for path in paths for p in path[1:]}
    manifest = read_json(outputs / "run/manifest.json")
    assert manifest["provenance"] == {"operation": "run", "inputs": read_json(recorded)}
    assert manifest["definition_sha256"] in manifest["provenance"]["inputs"]["definitions_sha256"]
    with np.load(outputs / "run/trajectory.npz") as saved:
        trajectory = {k: saved[k] for k in saved.files}
    times = trajectory["accepted_times"]
    nominal = round(NEAR_FAR_END / NEAR_FAR_DT)
    assert len(times) - 1 == nominal + len(switches) and switches <= set(times.tolist())

    # The same world, its schedules written by hand from the kernel's walk: the same bits.
    by_hand = copy.deepcopy(declared)
    for control in by_hand["experiment"]["channel_controls"]:
        for channels, path in zip(NEAR_FAR_CHANNELS, paths, strict=True):
            if control["channel_id"] in channels:
                control["schedule"] = [
                    {"time": t, "availability": a} for t, a in product([(0.0, AVAILABLE)], path)
                ]
    result = run(parse_spec(by_hand))
    assert np.array_equal(result.times, times)
    for name, value in result.history._asdict().items():
        assert np.array_equal(np.asarray(value), trajectory[name]), name

    # It conducts where its pools' levels say, and nowhere else.
    rows = [c["id"] for c in declared["model"]["channels"]]
    moved = {c: trajectory["channel_transferred"][:, 1, k] for k, c in enumerate(rows)}
    assert conducts(times, moved["kv_1"], lambda t: 1.0)
    for k, channels in enumerate(NEAR_FAR_CHANNELS):
        path, other = paths[k], paths[1 - k]
        events = [p[0] for p in path] + [NEAR_FAR_END]
        early = [(events[max(i - 1, 0)], p[1]) for i, p in enumerate(path)]
        late = [(0.0, path[0][1])] + [
            (events[i + 1], p[1]) for i, p in enumerate(path) if i and events[i + 1] < NEAR_FAR_END
        ]
        on_grid = [(math.ceil(p[0] / NEAR_FAR_DT) * NEAR_FAR_DT, p[1]) for p in path]
        for channel in channels:
            assert conducts(times, moved[channel], lambda t, p=path: held(p, t))
            for wrong in (other, early, late, on_grid, [(0.0, AVAILABLE)]):
                assert not conducts(times, moved[channel], lambda t, p=wrong: held(p, t))
