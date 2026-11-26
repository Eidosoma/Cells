"""FR-18's X2, the step-doubled energy check, through the scalar windows (execution.energy_check,
D224; docs/FR18_CRITERION_X_2026-11-18.md, its implementation section).

The world is FR-18's refused arm, Figure 5a at g = 100 and dt/16 (dt x rate 0.63), for 12 steps.
Today's check refuses it at its first row. Every step is counted, and |R| is near 1e-2 pJ, far
above the floor. Windows are 5 steps, a partial last window included.
- Host and device parity, and the restart: the device windows continue from the host run's first
  window's checkpoint, written and loaded. They give the host run's later windows bit for bit:
  every array, the energy record and X2's diagnostics (tests/window_row_check_fixtures.py).
- A record at any row: a checkpoint taken mid-window (RunResult.checkpoint_at) carries the record
  that a run split there carries, so a restart from it continues the record bit for bit. The
  windowed writer's snapshots carry their records too.
- The record binds its state. A planted heat x (1 + 1e-6), FR-3's registered plant's form, is
  refused. So are a record without the check and the check without a record. Without the check, a
  checkpoint writes today's files.

About 40 s: one compile of the doubled window program, which every later run here reuses, and the
device checks' compile. It is a new file (D224 allows one for a new feature) because its row would
take test_window_row_checks_families.py past the 90 s measuring cap.
"""

import dataclasses
import json
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import validate_checkpoint
from cells.execution.state import initialise
from cells.execution.windows import WindowPolicy
from cells.records.io import load_snapshot, write_snapshot
from cells.records.window_io import write_windowed_run
from tests.window_row_check_fixtures import assert_agreement, assert_same_windows, windows

WIDTH = 5
STEPS = 12


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def step_doubled_world(steps=STEPS):
    from validation.gap_junction_tissue import worlds

    network = worlds.figure5_network(100.0)
    dt = worlds.BASE_DT_S / 16.0
    raw = worlds.linear_network(network.cells, network.edges, network.probes, dt=dt)
    raw["experiment"]["end_time"] = steps * dt
    raw["experiment"]["observation_times"] = [0.0, 7 * dt, steps * dt]
    raw["execution"]["energy_check"] = dict(
        check="cells.execution.step_doubled_energy@1", integration_error_cap=3e-2
    )
    return raw


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    spec = parse_spec(step_doubled_world())
    host = windows(spec, WIDTH, "host")
    first = write_snapshot(tmp_path_factory.mktemp("x2") / "first", spec, host[0].final)
    device = windows(spec, WIDTH, "device", load_snapshot(first).checkpoint)
    return SimpleNamespace(spec=spec, host=host, device=device, first=first)


def same_state(a, b):
    return all(
        np.asarray(x).tobytes() == np.asarray(y).tobytes()
        for x, y in zip(a.state, b.state, strict=True)
    )


def test_device_windows_restarted_from_a_snapshot_are_the_host_run_bit_for_bit(runs):
    host, device = runs.host[1:], runs.device
    assert [len(w.times) - 1 for w in runs.host] == [5, 5, 2]
    assert_same_windows(host, device)
    assert assert_agreement(runs.spec, host, device) == len(device)
    record = runs.host[-1].final.energy_check
    assert record.counted_q.size == STEPS  # Every step counted.
    assert 4.0 < float(np.median(record.counted_q)) < 4.6


def test_a_checkpoint_mid_window_carries_the_record_a_split_run_carries(runs, tmp_path):
    spec, window = runs.spec, runs.host[0]
    assert window.checkpoint_at(window.final.time).energy_check.same(window.final.energy_check)
    mid = window.checkpoint_at(float(window.times[3]))
    assert mid.step_index == 3 and mid.energy_check.counted_q.size == 3
    rest = windows(spec, WIDTH, "host", mid)
    assert rest[-1].final.energy_check.same(runs.host[-1].final.energy_check)
    assert same_state(rest[-1].final, runs.host[-1].final)
    write_windowed_run(
        tmp_path / "run", spec, WindowPolicy(WIDTH, "checkpoints"), checkpoint_times=[mid.time]
    )
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["resources"]["energy_check"]["counted_steps"] == STEPS
    snapshot = load_snapshot(tmp_path / "run" / "snapshots" / "step-0000000003").checkpoint
    assert snapshot.energy_check.same(mid.energy_check)


def test_a_step_doubled_checkpoint_binds_its_record_and_writes_it_only_with_the_check(
    runs, tmp_path
):
    """The written checkpoint's record loads bit for bit, and binds its state. A planted heat x
    (1 + 1e-6) is refused by the binding, the only energy guard on a loaded checkpoint (an edited
    row's jump would enter the next step's d and d'' alike and be held)."""
    spec = runs.spec
    loaded = load_snapshot(runs.first).checkpoint
    assert loaded.energy_check.same(runs.host[0].final.energy_check)
    heat = np.asarray(loaded.state.junction_dissipated_energy_pJ) * (1 + 1e-6)
    planted = dataclasses.replace(
        loaded, state=loaded.state._replace(junction_dissipated_energy_pJ=heat)
    )
    with pytest.raises(ConfigError, match="does not hold its state's residual"):
        validate_checkpoint(spec, planted, energy_check=True)
    data = spec.to_dict()
    del data["execution"]["energy_check"]
    off = parse_spec(data)
    with pytest.raises(ConfigError, match="needs a definition that selects it"):
        validate_checkpoint(off, loaded)
    with pytest.raises(ConfigError, match="carries its energy record"):
        validate_checkpoint(spec, dataclasses.replace(loaded, energy_check=None), energy_check=True)
    written = write_snapshot(tmp_path / "off", off, initialise(off))
    assert sorted(p.name for p in written.iterdir()) == ["manifest.json", "state.npz"]
    assert "energy_check" not in json.loads((written / "manifest.json").read_text())
