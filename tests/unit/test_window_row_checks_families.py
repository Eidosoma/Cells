"""Device row checks on resolved_pump_tissue@2, on @3 with a declared kind, and on @3 under the
step-doubled energy check.

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §9.6, conditions C1 and C2 beyond @1 and the composites:
@2's calcium pump, and @3 with a declared kind (tests/kind_fixtures.py's exchange), whose
device checks fold the kind's ledger terms. Windows of 5 steps, a partial last window
included: every array is host mode's, bitwise, and each device-decided window's diagnostics
agree with the host's check of the same rows.

@3 under FR-18's X2 (execution.energy_check, D224; docs/FR18_CRITERION_X_2026-11-18.md) runs on
FR-18's refused arm, Figure 5a at g = 100 and dt/16 (dt x rate 0.63), for 12 steps: a world
today's check refuses at its first row, with every step counted and |R| near 1e-2 pJ, far above
the floor. Its device windows continue from the host run's first window's checkpoint, written
and loaded, so the row is also the restart: two segments give one segment's arrays and energy
record, bit for bit, the record's IO included. The written checkpoint then binds its record: a
planted heat x (1 + 1e-6), FR-3's registered plant's form, is refused. (The X2 row's two runs
compile the doubled window program once, the device run reusing it, plus the device checks:
about 85 s on the shared light CPUs before that reuse; the binding test, about 2 s.)
"""

import dataclasses
import json
from contextlib import nullcontext

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import validate_checkpoint
from cells.execution.state import initialise
from cells.numerics import surface_imex as imex
from cells.records.io import load_snapshot, write_snapshot
from cells.registry import kind_registry
from tests.window_row_check_fixtures import assert_agreement, assert_same_windows, windows
from validation.tissue import surface_pump_v2_fixtures

WIDTH = 5


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def cases():
    from tests.unit.test_kind_schedules import scheduled, world

    raw = surface_pump_v2_fixtures.definition("clamped", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    return {
        "@2": (None, raw),
        "@3-kind": (scheduled(), world(None, end_time=0.012)),
        "@3-x2": (None, step_doubled_world()),
    }


def step_doubled_world(steps=12):
    from validation.gap_junction_tissue import worlds

    network = worlds.figure5_network(100.0)
    dt = worlds.BASE_DT_S / 16.0
    raw = worlds.linear_network(network.cells, network.edges, network.probes, dt=dt)
    raw["experiment"]["end_time"] = steps * dt
    raw["experiment"]["observation_times"] = [0.0, 7 * dt, steps * dt]
    raw["execution"]["energy_check"] = dict(
        check="step_doubled_energy@1", integration_error_cap=3e-2
    )
    return raw


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    out = {}
    for name, (registry, raw) in cases().items():
        with kind_registry.scope(registry) if registry is not None else nullcontext():
            spec = parse_spec(raw)
            host = windows(spec, WIDTH, "host")
            if spec.energy_check is None:
                out[name] = spec, host, windows(spec, WIDTH, "device")
                continue
            # The restart: the device windows continue from the first window's checkpoint.
            path = write_snapshot(tmp_path_factory.mktemp("x2") / "first", spec, host[0].final)
            loaded = load_snapshot(path).checkpoint
            out[name] = spec, host[1:], windows(spec, WIDTH, "device", loaded)
            out["x2-first"] = host[0].final, path
    return out


@pytest.mark.parametrize("name", ["@2", "@3-kind", "@3-x2"])
def test_device_mode_keeps_every_array_and_agrees_with_the_host(name, runs):
    spec, host, device = runs[name]
    steps = [len(w.times) - 1 for w in host]
    assert len(steps) > 1 and steps[-1] < WIDTH  # A partial last window.
    assert_same_windows(host, device)
    assert assert_agreement(spec, host, device) == len(device)


def test_a_step_doubled_checkpoint_binds_its_record_and_writes_it_only_with_the_check(
    runs, tmp_path
):
    """The X2 row's written checkpoint: its record loads bit for bit, and binds its state. A
    planted heat x (1 + 1e-6) is refused by the binding, the only energy guard on a loaded
    checkpoint (an edited row's jump would enter the next step's d and d'' alike and be held).
    A record without the check and the check without a record are refused, and without the
    check a checkpoint writes today's files."""
    spec = runs["@3-x2"][0]
    first, path = runs["x2-first"]
    loaded = load_snapshot(path).checkpoint
    assert loaded.energy_check.same(first.energy_check)
    assert loaded.energy_check.counted_q.size == first.step_index  # Every step counted.
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
