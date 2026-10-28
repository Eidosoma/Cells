"""Sequential water replay workers with complete arrays saved before comparisons.

The ordinary qualification coordinator launches these phases and CLI restarts
under its existing process-tree guard. This module does not launch any jobs.
"""

import argparse
import hashlib
import json
import traceback
from pathlib import Path

import numpy as np

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.specs import parse_spec
from cells.core.surface_water_kinetic_spec import prior_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_water_kinetic as model
from validation.tissue import surface_water_kinetic_fixtures as fixtures

CHECKPOINT_TIME = fixtures.CHECKPOINT_TIME
WORLD_ARMS = {101: "coupled", 707: "sealed"}


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(left, right):
    for a, b in zip(left, right, strict=True):
        a, b = np.asarray(a), np.asarray(b)
        np.testing.assert_array_equal(a, b)
        assert a.dtype == b.dtype
        assert a.tobytes() == b.tobytes()


def save_history(path, times, history):
    with path.open("xb") as stream:
        np.savez_compressed(
            stream,
            accepted_times=np.asarray(times),
            **{name: np.asarray(value) for name, value in history._asdict().items()},
        )


def save_checkpoint_arrays(path, checkpoint):
    with path.open("xb") as stream:
        np.savez_compressed(
            stream,
            **{"state_" + k: np.asarray(v) for k, v in checkpoint.state._asdict().items()},
            **{"layout_" + k: np.asarray(v) for k, v in checkpoint.layout._asdict().items()},
            time=np.asarray(checkpoint.time),
            step_index=np.asarray(checkpoint.step_index),
            event_index=np.asarray(checkpoint.event_index),
        )


def exact_checkpoint(actual, expected):
    exact(actual.state, expected.state)
    exact(actual.layout, expected.layout)
    assert (actual.time, actual.step_index, actual.event_index) == (
        expected.time,
        expected.step_index,
        expected.event_index,
    )


def merge_windows(rows):
    history = model.STATE_TYPE(
        *(
            np.concatenate(
                [getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(rows)]
            )
            for k in model.STATE_TYPE._fields
        )
    )
    times = np.concatenate([w.times[0 if i == 0 else 1 :] for i, w in enumerate(rows)])
    return times, history, rows[-1].final


def prepare(root, backend):
    raw = fixtures.definition("release", backend=backend, padded=True)
    write_json(root / "release_inputs.json", raw)
    value = run(parse_spec(raw))
    save_history(root / "full_history.npz", value.times, value.history)
    save_checkpoint_arrays(root / "full_final.npz", value.final)
    checkpoint = value.checkpoint_at(CHECKPOINT_TIME)
    save_checkpoint_arrays(root / "original_checkpoint.npz", checkpoint)
    write_snapshot(root / "checkpoint", value.spec, checkpoint)
    write_snapshot(root / "expected", value.spec, value.final)
    save_history(
        root / "expected_history.npz",
        value.times[checkpoint.step_index :],
        model.STATE_TYPE(*(v[checkpoint.step_index :] for v in value.history)),
    )
    loaded = load_snapshot(root / "checkpoint")
    save_checkpoint_arrays(root / "loaded_checkpoint.npz", loaded.checkpoint)
    assert len(model.STATE_TYPE._fields) == 23
    assert all(v.device.platform == backend for v in value.final.state)
    exact_checkpoint(loaded.checkpoint, checkpoint)
    assert loaded.spec == value.spec
    return dict(status="prepared", disk=True, full_steps=value.final.step_index)


def resume_branch(root, backend):
    loaded = load_snapshot(root / "checkpoint")
    checkpoint = loaded.checkpoint
    resumed = run(loaded.spec, checkpoint)
    save_history(root / "resumed_history.npz", resumed.times, resumed.history)
    save_checkpoint_arrays(root / "resumed_final.npz", resumed.final)
    terminal = load_snapshot(root / "expected")
    unchanged = run(terminal.spec, terminal.checkpoint)
    save_history(root / "terminal_history.npz", unchanged.times, unchanged.history)
    save_checkpoint_arrays(root / "terminal_final.npz", unchanged.final)
    assert loaded.spec.execution.backend == backend
    assert all(v.device.platform == backend for v in resumed.final.state)
    with np.load(root / "expected_history.npz", allow_pickle=False) as expected:
        assert set(expected.files) == {"accepted_times", *model.STATE_TYPE._fields}
        exact((resumed.times,), (expected["accepted_times"],))
        exact(resumed.history, (expected[k] for k in model.STATE_TYPE._fields))
    exact_checkpoint(resumed.final, terminal.checkpoint)
    exact(tuple(v[0] for v in unchanged.history), terminal.checkpoint.state)
    exact_checkpoint(unchanged.final, terminal.checkpoint)
    raw = loaded.spec.to_dict()
    for control in raw["experiment"]["water_controls"]:
        future = [
            dict(time=c["time"], availability=0.0)
            for c in control["schedule"]
            if c["time"] > checkpoint.time
        ]
        control["schedule"] = [c for c in control["schedule"] if c["time"] < checkpoint.time]
        control["schedule"] += [dict(time=checkpoint.time, availability=0.0), *future]
    write_json(root / "branch_inputs.json", raw)
    spec = parse_spec(raw)
    changed = run(spec, branch_checkpoint(loaded.spec, checkpoint, spec))
    save_history(root / "branch_history.npz", changed.times, changed.history)
    save_checkpoint_arrays(root / "branch_final.npz", changed.final)
    exact(tuple(v[0] for v in changed.history), checkpoint.state)
    exact(changed.final.layout, checkpoint.layout)
    assert prior_spec(spec) == prior_spec(loaded.spec)
    exact((changed.times,), (resumed.times,))
    for name in model.EXTRA_AXES:
        expected = np.broadcast_to(
            getattr(checkpoint.state, name), getattr(changed.history, name).shape
        )
        exact((getattr(changed.history, name),), (expected,))
    assert np.any(resumed.final.state.water_transferred_pL != checkpoint.state.water_transferred_pL)
    assert np.any(changed.final.state.membrane_transferred != checkpoint.state.membrane_transferred)
    assert not np.array_equal(
        changed.final.state.volume_increment_pL, resumed.final.state.volume_increment_pL
    )
    return dict(status="passed", branch=True, terminal=True, saved_complete_history=True)


def windows(root, backend):
    loaded = load_snapshot(root / "checkpoint")
    total = len(timeline(loaded.spec)) - 1
    width = next(d for d in range(11, 0, -1) if total % d == 0)
    parts = list(iter_windows(loaded.spec, WindowPolicy(width, "full")))
    times, history, final = merge_windows(parts)
    save_history(root / "windows_history.npz", times, history)
    save_checkpoint_arrays(root / "windows_final.npz", final)
    remaining = total - loaded.checkpoint.step_index
    resume_width = next(d for d in range(7, 0, -1) if remaining % d == 0 and d != width)
    resumed = list(iter_windows(loaded.spec, WindowPolicy(resume_width, "full"), loaded.checkpoint))
    resumed_times, resumed_history, resumed_final = merge_windows(resumed)
    save_history(root / "resumed_windows_history.npz", resumed_times, resumed_history)
    save_checkpoint_arrays(root / "resumed_windows_final.npz", resumed_final)
    assert width != resume_width
    assert len(parts) == total // width and all(len(w.times) == width + 1 for w in parts)
    assert all(v.device.platform == backend for v in final.state)
    with np.load(root / "full_history.npz", allow_pickle=False) as expected:
        exact((times,), (expected["accepted_times"],))
        exact(history, (expected[k] for k in model.STATE_TYPE._fields))
    with np.load(root / "expected_history.npz", allow_pickle=False) as expected:
        exact((resumed_times,), (expected["accepted_times"],))
        exact(resumed_history, (expected[k] for k in model.STATE_TYPE._fields))
    target = load_snapshot(root / "expected").checkpoint
    exact_checkpoint(final, target)
    exact_checkpoint(resumed_final, target)
    return dict(
        status="passed",
        windows=True,
        window_steps=width,
        window_count=len(parts),
        resumed_window_steps=resume_width,
        resumed_window_count=len(resumed),
        complete_layout_and_clock=True,
    )


def worlds(root, backend):
    worlds = tuple(
        WorldSpec(identity, parse_spec(fixtures.definition(arm, backend=backend, padded=True)))
        for identity, arm in WORLD_ARMS.items()
    )
    batch = BatchSpec(worlds, 2, 128, 2**29)
    write_json(root / "worlds_inputs.json", batch.to_dict())
    scalar = {}
    for world in worlds:
        value = run(world.simulation)
        save_history(root / f"scalar-{world.world_id}.npz", value.times, value.history)
        save_checkpoint_arrays(root / f"scalar-final-{world.world_id}.npz", value.final)
        scalar[world.world_id] = value
    forward = run_batch(batch)
    for identity, value in forward.worlds.items():
        save_history(root / f"batch-{identity}.npz", value.times, value.history)
        save_checkpoint_arrays(root / f"batch-final-{identity}.npz", value.final)
    reversed_values = run_batch(BatchSpec(tuple(reversed(worlds)), 2, 128, 2**29))
    for identity, value in reversed_values.worlds.items():
        save_history(root / f"reordered-{identity}.npz", value.times, value.history)
        save_checkpoint_arrays(root / f"reordered-final-{identity}.npz", value.final)
    partitions = {}
    for world in worlds:
        value = run_batch(BatchSpec((world,), 1, 64, 2**29)).worlds[world.world_id]
        save_history(root / f"partition-{world.world_id}.npz", value.times, value.history)
        save_checkpoint_arrays(root / f"partition-final-{world.world_id}.npz", value.final)
        partitions[world.world_id] = value
    checkpoint_times = {101: CHECKPOINT_TIME, 707: worlds[1].simulation.experiment.end_time}
    checkpoints = forward.checkpoint_at(checkpoint_times)
    write_batch_snapshot(root / "worlds_checkpoint", batch, checkpoints)
    loaded = load_batch_snapshot(root / "worlds_checkpoint")
    for identity in WORLD_ARMS:
        save_checkpoint_arrays(root / f"worlds-original-{identity}.npz", checkpoints[identity])
        save_checkpoint_arrays(root / f"worlds-loaded-{identity}.npz", loaded.checkpoints[identity])
    rounds = list(iter_batch_windows(loaded.spec, WindowPolicy(5, "full"), loaded.checkpoints))
    resumed = {}
    for identity in WORLD_ARMS:
        rows = [r.worlds[identity] for r in rounds if identity in r.worlds]
        times, history, final = merge_windows(rows)
        save_history(root / f"worlds-resumed-{identity}.npz", times, history)
        save_checkpoint_arrays(root / f"worlds-resumed-final-{identity}.npz", final)
        resumed[identity] = (times, history, final)
    for identity, value in forward.worlds.items():
        for expected in (scalar[identity], reversed_values.worlds[identity], partitions[identity]):
            exact((value.times,), (expected.times,))
            exact(value.history, expected.history)
            exact_checkpoint(value.final, expected.final)
        exact_checkpoint(loaded.checkpoints[identity], checkpoints[identity])
        times, history, final = resumed[identity]
        start = checkpoints[identity].step_index
        exact((times,), (value.times[start:],))
        exact(history, (v[start:] for v in value.history))
        exact_checkpoint(final, value.final)
        assert all(v.device.platform == backend for v in value.final.state)
    assert loaded.spec == batch
    assert checkpoints[101].time != checkpoints[707].time
    assert np.any(forward.worlds[101].final.state.volume_increment_pL)
    assert not np.any(forward.worlds[707].history.volume_increment_pL)
    return dict(
        status="passed",
        world_ids=list(WORLD_ARMS),
        arms=WORLD_ARMS,
        scalar=True,
        partitions=True,
        reordered=True,
        disk=True,
        independent_restart_times=checkpoint_times,
        terminal_world_retained=True,
        changed_windows=True,
        complete_layout_and_clock=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--backend", choices=("cpu", "gpu"), required=True)
    parser.add_argument(
        "--phase", choices=("prepare", "resume_branch", "windows", "worlds"), required=True
    )
    args = parser.parse_args()
    try:
        result = dict(prepare=prepare, resume_branch=resume_branch, windows=windows, worlds=worlds)[
            args.phase
        ](args.output, args.backend)
        write_json(
            args.output / (args.phase + ".json"),
            result
            | dict(
                backend=args.backend,
                comparison="bitwise",
                state_fields=list(model.STATE_TYPE._fields),
                history_sha256={p.name: digest(p) for p in args.output.glob("*.npz")},
            ),
        )
    except BaseException:
        write_json(
            args.output / (args.phase + ".failure.json"),
            dict(
                status="failed",
                phase=args.phase,
                backend=args.backend,
                traceback=traceback.format_exc(),
                retained_arrays={p.name: digest(p) for p in args.output.glob("*.npz")},
            ),
        )
        raise
