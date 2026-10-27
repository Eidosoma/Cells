"""Prepare complete replay evidence, then exit before the fresh CLI restarts.

This worker owns the compiled simulation graphs. The pytest coordinator runs
it and the ordinary CLI sequentially under the existing process-tree guard.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from cells.core.runner import branch_checkpoint, run
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_mobile_pump as model
from validation.tissue import surface_mobile_pump_fixtures as fixtures


def exact(a, b):
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(x, y)


def prepare(root, backend):
    v = run(parse_spec(fixtures.definition("release", backend=backend)))
    assert all(y.device.platform == backend for y in v.final.state)
    checkpoint = v.checkpoint_at(0.0002)
    write_snapshot(root / "checkpoint", v.spec, checkpoint)
    loaded = load_snapshot(root / "checkpoint")
    exact(loaded.checkpoint.state, checkpoint.state)
    resumed = run(loaded.spec, loaded.checkpoint)
    exact(resumed.history, tuple(y[checkpoint.step_index :] for y in v.history))
    exact(tuple(y[0] for y in run(v.spec, v.final).history), v.final.state)
    write_snapshot(root / "expected", v.spec, resumed.final)
    np.savez_compressed(
        root / "expected_history.npz",
        accepted_times=resumed.times,
        **{k: np.asarray(y) for k, y in resumed.history._asdict().items()},
    )
    raw = v.spec.to_dict()
    for control in raw["experiment"]["pump_controls"]:
        # Retain future boundaries used by observations, even with pumping off.
        future = [
            dict(time=c["time"], availability=0.0)
            for c in control["schedule"]
            if c["time"] > 0.0002
        ]
        control["schedule"] = [c for c in control["schedule"] if c["time"] < 0.0002]
        control["schedule"].append(dict(time=0.0002, availability=0.0))
        control["schedule"].extend(future)
    spec = parse_spec(raw)
    changed = run(spec, branch_checkpoint(v.spec, checkpoint, spec))
    exact(tuple(y[0] for y in changed.history), checkpoint.state)
    np.testing.assert_array_equal(changed.final.state.pump_cycles, checkpoint.state.pump_cycles)
    np.testing.assert_array_equal(
        changed.history.pump_surface_amount_increment,
        resumed.history.pump_surface_amount_increment,
    )
    parts = list(iter_windows(v.spec, WindowPolicy(11, "full")))
    merged = tuple(
        np.concatenate([getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    exact(merged, v.history)
    with (root / "prepared.json").open("x") as stream:
        json.dump(
            dict(
                status="prepared",
                backend=backend,
                comparison="bitwise",
                state_fields=list(model.STATE_TYPE._fields),
                disk=True,
                branch=True,
                terminal=True,
                windows=True,
                fresh_process=False,
            ),
            stream,
            indent=2,
        )
        stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--backend", choices=("cpu", "gpu"), required=True)
    args = parser.parse_args()
    prepare(args.output, args.backend)
