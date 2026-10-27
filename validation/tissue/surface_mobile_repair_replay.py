"""Run complete replay phases in fresh processes, one compiled shape per phase.

The pytest coordinator runs these workers and the ordinary CLI sequentially
under the existing process-tree guard. Full arrays bind every comparison.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from cells.core.runner import branch_checkpoint, run
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_mobile_repair as model
from validation.tissue import surface_mobile_repair_fixtures as fixtures


def exact(a, b):
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


def prepare(root, backend):
    v = run(parse_spec(fixtures.definition("release", backend=backend)))
    assert all(y.device.platform == backend for y in v.final.state)
    checkpoint = v.checkpoint_at(25e-6)
    write_snapshot(root / "checkpoint", v.spec, checkpoint)
    loaded = load_snapshot(root / "checkpoint")
    exact(loaded.checkpoint.state, checkpoint.state)
    exact(loaded.checkpoint.layout, checkpoint.layout)
    assert (
        loaded.checkpoint.time,
        loaded.checkpoint.step_index,
        loaded.checkpoint.event_index,
    ) == (checkpoint.time, checkpoint.step_index, checkpoint.event_index)
    write_snapshot(root / "expected", v.spec, v.final)
    np.savez_compressed(
        root / "expected_history.npz",
        accepted_times=v.times[checkpoint.step_index :],
        **{k: np.asarray(y[checkpoint.step_index :]) for k, y in v.history._asdict().items()},
    )
    np.savez_compressed(
        root / "full_history.npz",
        accepted_times=v.times,
        **{k: np.asarray(y) for k, y in v.history._asdict().items()},
    )
    return dict(status="prepared", disk=True, full_steps=v.final.step_index)


def resume_branch(root, backend):
    loaded = load_snapshot(root / "checkpoint")
    assert loaded.spec.execution.backend == backend
    checkpoint = loaded.checkpoint
    resumed = run(loaded.spec, checkpoint)
    assert all(y.device.platform == backend for y in resumed.final.state)
    with np.load(root / "expected_history.npz", allow_pickle=False) as expected:
        np.testing.assert_array_equal(resumed.times, expected["accepted_times"])
        for name, value in resumed.history._asdict().items():
            np.testing.assert_array_equal(value, expected[name])
    terminal = load_snapshot(root / "expected")
    exact(resumed.final.state, terminal.checkpoint.state)
    exact(
        tuple(y[0] for y in run(terminal.spec, terminal.checkpoint).history),
        terminal.checkpoint.state,
    )
    raw = loaded.spec.to_dict()
    for control in raw["experiment"]["mobile_channel_controls"]:
        # Retain future boundaries used by observations, even with channel conduction off.
        future = [
            dict(time=c["time"], availability=0.0) for c in control["schedule"] if c["time"] > 25e-6
        ]
        control["schedule"] = [c for c in control["schedule"] if c["time"] < 25e-6]
        control["schedule"].append(dict(time=25e-6, availability=0.0))
        control["schedule"].extend(future)
    spec = parse_spec(raw)
    changed = run(spec, branch_checkpoint(loaded.spec, checkpoint, spec))
    exact(tuple(y[0] for y in changed.history), checkpoint.state)
    # Blocking conduction preserves the protein inventory and leaves gates dynamic.
    assert np.any(
        changed.final.state.channel_gate_transferred != checkpoint.state.channel_gate_transferred
    )
    np.testing.assert_allclose(
        changed.history.channel_state_amount_increment.sum(axis=2),
        resumed.history.channel_state_amount_increment.sum(axis=2),
        atol=3e-13,
        rtol=0,
    )
    np.testing.assert_array_equal(changed.history.damage, resumed.history.damage)
    assert not np.array_equal(
        changed.final.state.mobile_channel_transferred,
        resumed.final.state.mobile_channel_transferred,
    )
    return dict(status="passed", branch=True, terminal=True, saved_complete_history=True)


def windows(root, backend):
    loaded = load_snapshot(root / "checkpoint")
    assert loaded.spec.execution.backend == backend
    # Seven equal windows cover all 84 accepted steps, including off-grid events.
    # One compiled length per process keeps the same memory guard as scalar runs.
    parts = list(iter_windows(loaded.spec, WindowPolicy(12, "full")))
    assert len(parts) == 7 and all(len(w.times) == 13 for w in parts)
    assert all(y.device.platform == backend for y in parts[-1].final.state)
    merged = tuple(
        np.concatenate([getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    times = np.concatenate([w.times[0 if i == 0 else 1 :] for i, w in enumerate(parts)])
    # Retain every actual field even when the first bitwise comparison fails.
    np.savez_compressed(
        root / "windows_history.npz",
        accepted_times=times,
        **dict(zip(model.STATE_TYPE._fields, merged, strict=True)),
    )
    with np.load(root / "full_history.npz", allow_pickle=False) as expected:
        np.testing.assert_array_equal(times, expected["accepted_times"])
        for name, value in zip(model.STATE_TYPE._fields, merged, strict=True):
            np.testing.assert_array_equal(value, expected[name])
    target = load_snapshot(root / "expected").checkpoint
    exact(parts[-1].final.state, target.state)
    exact(parts[-1].final.layout, target.layout)
    assert (parts[-1].final.time, parts[-1].final.step_index, parts[-1].final.event_index) == (
        target.time,
        target.step_index,
        target.event_index,
    )
    return dict(
        status="passed",
        windows=True,
        window_steps=12,
        window_count=7,
        history_file="windows_history.npz",
        history_sha256=hashlib.sha256((root / "windows_history.npz").read_bytes()).hexdigest(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--backend", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--phase", choices=("prepare", "resume_branch", "windows"), required=True)
    args = parser.parse_args()
    result = {"prepare": prepare, "resume_branch": resume_branch, "windows": windows}[args.phase](
        args.output, args.backend
    )
    with (args.output / (args.phase + ".json")).open("x") as stream:
        json.dump(
            result
            | dict(
                backend=args.backend,
                comparison="bitwise",
                state_fields=list(model.STATE_TYPE._fields),
            ),
            stream,
            indent=2,
        )
        stream.write("\n")
