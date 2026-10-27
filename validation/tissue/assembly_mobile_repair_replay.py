"""Fresh-process complete assembly/mobile-channel restart with one graph per worker."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np

from cells.assembly.io import digest, write_json
from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine
from cells.assembly_cluster.spec import parse_spec


def execute(root, backend, phase, baseline):
    receipt = json.loads(baseline.with_suffix(".json").read_text())
    raw = receipt["inputs"]
    raw["ionic"]["execution"]["backend"] = backend
    spec = parse_spec(raw)
    if phase == "prepare":
        state = engine.initial_state(spec)
        until = 40 * spec.ionic.execution.dt
    else:
        loaded, state, _ = load_checkpoint(root / "checkpoint", backend=backend)
        assert loaded == spec
        spec = replace(loaded, window_ticks=3)
        until = spec.ionic.experiment.end_time
    wanted = {round(t / spec.ionic.execution.dt) for t in spec.ionic.experiment.observation_times}
    start = int(state.tick[0])
    rows = [flatten(state)]

    def capture(_, current):
        if int(current.tick[0]) in wanted:
            rows.append({k: v.copy() for k, v in flatten(current).items()})

    final, report = engine.run(spec, backend=backend, state=state, until=until, callback=capture)
    actual = {k: np.stack([v[k] for v in rows]) for k in rows[0]}
    archive = root / (phase + "_history.npz")
    np.savez_compressed(archive, **actual)
    with np.load(baseline, allow_pickle=False) as expected:
        mask = (expected["tick"][:, 0] >= start) & (expected["tick"][:, 0] <= final.tick[0])
        assert set(actual) == set(expected.files)
        for name, values in actual.items():
            np.testing.assert_array_equal(values, expected[name][mask], err_msg=name)
    if phase == "prepare":
        assert np.any(final.pool.pending_valid)
        write_checkpoint(root / "checkpoint", spec, final, backend=backend)
        _, saved, _ = load_checkpoint(root / "checkpoint", backend=backend)
        for a, b in zip(jax.tree.leaves(final), jax.tree.leaves(saved), strict=True):
            np.testing.assert_array_equal(a, b)
    else:
        write_checkpoint(root / "final", spec, final, backend=backend)
        restored, saved, _ = load_checkpoint(root / "final", backend=backend)
        terminal, _ = engine.run(restored, backend=backend, state=saved)
        for name, values in flatten(terminal).items():
            np.testing.assert_array_equal(values, actual[name][-1], err_msg=name)
    return dict(
        status="passed",
        phase=phase,
        backend=backend,
        ionic_fields=47,
        window_ticks=spec.window_ticks,
        history_sha256=digest(archive),
        baseline_sha256=digest(baseline),
        report=report,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--backend", choices=("cpu", "gpu"), required=True)
    parser.add_argument("--phase", choices=("prepare", "resume"), required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.output, args.backend, args.phase, args.baseline)
    write_json(args.output / (args.phase + ".json"), result)
