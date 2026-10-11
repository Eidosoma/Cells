"""Reference world identity, scientific-input binding and durable trace failures."""

from dataclasses import replace

import numpy as np
import pytest

from cells.assembly_cluster import engine
from cells.assembly_cluster.spec import parse_spec
from cells.ensemble import cli
from validation.ensemble import parallel_cluster as screen
from validation.ensemble.test_parallel_cluster import physical_spec


def campaign(tmp_path, intervals):
    original = physical_spec()
    tasks = {}
    for index, (first, count) in enumerate(intervals):
        name = f"task-{index:05d}"
        tasks[name] = {}
        path = tmp_path / "tasks" / name
        (path / "checkpoint").mkdir(parents=True)
        spec = screen.rebound(original, worlds=count, first=first)
        cli.write(path / "result.json", {"definition": spec.to_dict()})
        cli.write(path / "checkpoint/manifest.json", {"definition": spec.to_dict()})
        (path / "checkpoint/state.npz").write_bytes(b"placeholder; no state is loaded by indexing")
    cli.write(tmp_path / "result.json", {"result_records": tasks})
    return screen.with_run_budget(screen.rebound(original, worlds=65, first=0), 1200.0)


def test_qualified_worlds_are_sorted_by_identity_and_partial_tile_is_clipped(tmp_path):
    spec = campaign(tmp_path, [(32, 16), (64, 32), (0, 16), (48, 16), (16, 16), (96, 32)])
    slices = screen.qualified_slices(tmp_path, spec)
    assert [(s["world_id_start"], s["worlds"]) for s in slices] == [
        (0, 16),
        (16, 16),
        (32, 16),
        (48, 16),
        (64, 1),
    ]
    assert [s["slice_start"] for s in slices] == [0, 0, 0, 0, 0]
    subset = screen.rebound(spec, worlds=33, first=3)
    assert [
        (s["world_id_start"], s["worlds"], s["slice_start"])
        for s in screen.qualified_slices(tmp_path, subset)
    ] == [(3, 13, 3), (16, 16, 0), (32, 4, 0)]


@pytest.mark.parametrize(
    "intervals",
    [
        [(0, 32), (33, 32)],  # one missing world
        [(0, 33), (32, 33)],  # one duplicated world
        [(0, 64)],  # missing the final world
        [(1, 64)],  # missing the first world
    ],
)
def test_missing_or_duplicate_qualified_worlds_refused(tmp_path, intervals):
    spec = campaign(tmp_path, intervals)
    with pytest.raises(ValueError, match="world"):
        screen.qualified_slices(tmp_path, spec)


@pytest.mark.parametrize("change", ["seed", "clock", "window", "manifest"])
def test_reference_scientific_input_drift_refused(tmp_path, change):
    spec = campaign(tmp_path, [(0, 65)])
    path = tmp_path / "tasks/task-00000"
    raw = cli.read(path / "result.json")["definition"]
    if change == "seed":
        for binding in raw["pools"]:
            binding["pool"]["seed"] += 1
    elif change == "clock":
        raw["ionic"]["execution"]["dt"] /= 2
    else:
        raw["window_ticks"] += 1
    changed = parse_spec(raw).to_dict()
    if change != "manifest":
        screen.write_json(path / "result.json", {"definition": changed}, replace=True)
    screen.write_json(path / "checkpoint/manifest.json", {"definition": changed}, replace=True)
    with pytest.raises(ValueError, match="definition differs"):
        screen.qualified_slices(tmp_path, spec)


def test_wall_allowance_and_world_membership_are_only_permitted_reference_changes():
    original = physical_spec()
    larger = screen.with_run_budget(screen.rebound(original, worlds=65, first=0), 1200.0)
    screen.same_world_physics(original, larger)
    with pytest.raises(ValueError, match="physical definition"):
        screen.same_world_physics(original, replace(larger, window_ticks=7))


def test_scalar_reference_failure_preserves_all_completed_ticks(tmp_path, monkeypatch):
    spec = physical_spec()
    initial = engine.initial_state(spec)
    state = initial._replace(tick=np.ones_like(initial.tick))
    output = tmp_path / "gpu"
    output.mkdir()

    def failed_run(definition, *, backend, callback):
        assert definition.window_ticks == 1 and backend == "gpu"
        callback(1, state)
        raise RuntimeError("deliberate failed reference")

    monkeypatch.setattr(engine, "run", failed_run)
    with pytest.raises(RuntimeError, match="deliberate"):
        screen.fresh_scalar_trace(tmp_path, output, spec, "gpu")
    evidence = screen.load_arrays(output / "reference-failure-partial-trace.npz")
    np.testing.assert_array_equal(evidence["tick"], np.stack([initial.tick, state.tick]))
    assert cli.read(output / "reference-failure.json")["completed_ticks"] == 1
    assert not (output / "reference-trace.npz").exists()
