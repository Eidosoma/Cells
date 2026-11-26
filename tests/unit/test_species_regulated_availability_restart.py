"""cells.operator.species_regulated_availability@1, A8: restart, windows and snapshots preserve every result.

docs/INVENTORY_COUPLING_DESIGN.md §4.4 A8 and §1.9. The moving world
(regulated_availability_fixtures.dynamic_world: R cleared in cell_0 and dosed there from 12 ms, a
state of Na in cell_0 and cell_3 with a crossing level, c_r switched off over [15, 20) ms, a write
to (s, cell_3) at 10 ms placed before the dose's step), 30 steps at 1 ms, observed at every step.
One window program (7-step windows, which do not divide 30) serves every run:
* resumed from a checkpoint before, at and after the write, at the crossing's step, between the
  write and the dose, at the dose, at both switch changes and late in the run, every state field
  of every later row (the operator's int64 fields included) and every observation column at every
  later row are bitwise the uninterrupted run's; window boundaries fall at other steps in each;
* resumed through a snapshot written and read back (load_snapshot), the same, with the int64
  fields still int64;
* the step counter ends at the real step count and the crossing step is the same in every run, so
  the last window's padded steps advance nothing.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.records.io import load_snapshot, write_snapshot
from validation.tissue import regulated_availability_fixtures as rf

POLICY = WindowPolicy(7, "full")
STEPS = 30
INTEGER_FIELDS = ("regulatory_crossing_step", "regulatory_writes_applied", "coupling_step_count")
RESUME_TIMES = (0.009, 0.010, 0.011, 0.012, 0.015, 0.016, 0.020, 0.023)


def collect(spec, checkpoint=None):
    """(windows, {step: state row}, {time: {column: value}}) of a windowed run."""
    windows = list(iter_windows(spec, POLICY, checkpoint))
    rows, observed = {}, {}
    for window in windows:
        for i, _ in enumerate(np.asarray(window.times)):
            step = window.start_step + i
            rows[step] = type(window.history)(*(np.asarray(v)[i] for v in window.history))
        obs = vars(window.observations)
        for j, t in enumerate(np.asarray(obs["times"])):
            observed[float(t)] = {k: np.asarray(v)[j] for k, v in obs.items()}
    return windows, rows, observed


@pytest.fixture(scope="module")
def reference():
    spec = parse_spec(rf.dynamic_world())
    return (spec, *collect(spec))


def checkpoint_at(windows, time):
    """The checkpoint at the accepted time nearest `time` (the grid's own value, exactly)."""
    for window in windows:
        times = np.asarray(window.times)
        near = np.flatnonzero(np.abs(times - time) < 1e-9)
        if len(near):
            return window.checkpoint_at(float(times[near[0]]))
    raise KeyError(time)


def assert_bitwise_from(start, rows, observed, reference_rows, reference_observed):
    for step, row in rows.items():
        expected = reference_rows[step]
        for name, a, b in zip(type(row)._fields, row, expected, strict=True):
            assert a.dtype == b.dtype and a.tobytes() == b.tobytes(), (start, step, name)
    for t, columns in observed.items():
        for name, value in columns.items():
            expected = reference_observed[t][name]
            assert np.array_equal(value, expected, equal_nan=True), (start, t, name)


def test_the_uninterrupted_run_counts_its_real_steps(reference):
    _, windows, rows, _ = reference
    assert [len(np.asarray(w.times)) for w in windows][-1] < 8  # A short last window.
    final = windows[-1].final.state
    assert int(np.asarray(final.coupling_step_count)[0]) == STEPS
    assert list(np.asarray(final.regulatory_writes_applied)) == [0, 1]
    crossing = np.asarray(final.regulatory_crossing_step)
    assert crossing[1] == 11  # The write at 10 ms lifts (s, cell_3); the next step start records.
    for name in INTEGER_FIELDS:
        assert np.asarray(getattr(final, name)).dtype == np.int64


@pytest.mark.parametrize("time", RESUME_TIMES)
def test_a_restart_is_bitwise(reference, time):
    spec, windows, reference_rows, reference_observed = reference
    checkpoint = checkpoint_at(windows, time)
    resumed, rows, observed = collect(spec, checkpoint)
    assert min(rows) == checkpoint.step_index and max(rows) == STEPS
    assert_bitwise_from(time, rows, observed, reference_rows, reference_observed)
    final = resumed[-1].final.state
    assert int(np.asarray(final.coupling_step_count)[0]) == STEPS


def test_a_snapshot_round_trip_is_bitwise(reference, tmp_path):
    spec, windows, reference_rows, reference_observed = reference
    checkpoint = checkpoint_at(windows, 0.011)  # Between the write and the dose.
    write_snapshot(tmp_path / "snapshot", spec, checkpoint)
    loaded = load_snapshot(tmp_path / "snapshot")
    for name in INTEGER_FIELDS:
        assert np.asarray(getattr(loaded.checkpoint.state, name)).dtype == np.int64, name
    _, rows, observed = collect(loaded.spec, loaded.checkpoint)
    assert_bitwise_from("snapshot", rows, observed, reference_rows, reference_observed)
