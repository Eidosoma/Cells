"""A real user-facing one-cell definition, not a reference import at execution."""

from dataclasses import replace
from pathlib import Path

import numpy as np

from cells.core.runner import run
from cells.core.specs import load_spec
from cells.io import load_snapshot, write_run

ROOT = Path(__file__).resolve().parents[2]


def test_example_uses_shared_run_writer_and_complete_checkpoint(tmp_path):
    spec = load_spec(ROOT / "configs/spatial_extracellular_cell.json")
    assert len(spec.model.cells) == 1 and len(spec.model.extracellular) == 2
    assert spec.execution.capacity == 1 and spec.execution.face_capacity == 1
    spec = replace(
        spec,
        experiment=replace(
            spec.experiment, end_time=0.001, observation_times=(0.0, 0.00013, 0.001)
        ),
    )
    result = run(spec)
    write_run(tmp_path / "run", result, checkpoint_times=(0.0005,))
    saved = load_snapshot(tmp_path / "run/checkpoint_final")
    for a, b in zip(result.final.state, saved.checkpoint.state, strict=True):
        np.testing.assert_array_equal(a, b)
    with np.load(tmp_path / "run/trajectory.npz", allow_pickle=False) as arrays:
        assert "observed_membrane_current_A" in arrays
        assert "observed_extracellular_potential_V" in arrays
        assert "observed_face_current_A" in arrays
        assert arrays["extracellular_ids"].tolist() == [1, 2]
        assert arrays["face_ids"].tolist() == [1]
