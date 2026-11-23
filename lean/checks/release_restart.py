"""Compare unlabelled FR-38 state after disk restart for both polymerase return policies."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import jax
import numpy as np
from terminal_release import observed

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.records.io import load_snapshot, write_snapshot
from validation.gene_regulation import sheet_check, worlds


def restart_control(policy):
    """Restart an unlabelled chain with occupied stages and hold, before any replacement."""
    raw = observed(worlds.r1(0.75, machine=policy, initiation=float(sheet_check.A1["k_I_tx"])), 10)
    spec = parse_spec(raw)
    full = run(spec)
    checkpoint = full.checkpoint_at(4.0)
    state = checkpoint.state
    hold = float(np.sum(state.poly_hold_fmol))
    stages = np.asarray(state.poly_complexes_fmol)[0]
    assert hold > 0 and np.any(stages[1:] > 0)
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "checkpoint"
        write_snapshot(path, spec, checkpoint)
        loaded = load_snapshot(path)
        resumed = run(loaded.spec, loaded.checkpoint)
    start = checkpoint.step_index
    np.testing.assert_array_equal(resumed.times, full.times[start:])
    for name in full.history._fields:
        before = np.asarray(getattr(full.history, name))[start:]
        after = np.asarray(getattr(resumed.history, name))
        assert before.shape == after.shape and before.dtype == after.dtype, name
        assert before.tobytes() == after.tobytes(), name
    return dict(
        checkpoint_s=checkpoint.time,
        end_s=float(resumed.times[-1]),
        matching_state_fields=len(full.history._fields),
        matching_times=len(resumed.times),
        checkpoint_hold_fmol=hold,
        occupied_stages=int(np.count_nonzero(stages)),
    )


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    cases = {policy: restart_control(policy) for policy in ("returned", "held")}
    print(json.dumps(dict(passed=True, cases=cases), indent=2, allow_nan=False))
