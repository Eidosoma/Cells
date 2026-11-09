"""Vectorized worlds (core/vector_windows.py) against independent single-world runs.

A batch of heterogeneous resolved-pump worlds must reproduce each world's own
windowed run. With default XLA flags, the vmapped program is compiled
differently from the scalar one (algebraic rewrites and fused multiply-adds),
so states agree to a few ulp; test_vector_windows_bitwise.py shows that with
those passes disabled in both the batch is bitwise identical. Injected
failures stop both paths at the same step, and restart, the ensemble option and
pause/resume keep their guarantees.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.batch_windows import run_batch_windowed
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.core.state import initialise
from cells.core.vector_windows import (
    WorldCheckError,
    held_controls,
    iter_vector_windows,
    run_vector_windowed,
)
from cells.core.windows import WindowPolicy, run_windowed
from cells.models import surface_pump
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_fixtures, surface_pump_v2_fixtures

POLICY = WindowPolicy(5, "checkpoints")
CHANGE = 0.0005  # A world-specific pump schedule change used to inject faults.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def definition(fixtures=surface_pump_fixtures, arm="release", *, scale=1.0, change=None):
    raw = fixtures.definition(arm, solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    for membrane in raw["model"]["membranes"]:
        membrane["pump"]["capacity_fmol_per_s"] *= scale
    if change is not None:
        for control in raw["experiment"]["pump_controls"]:
            held = control["schedule"][-1]["availability"]
            control["schedule"] = [dict(time=0.0, availability=held), dict(time=CHANGE, **change)]
    return parse_spec(raw)


def cohort(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return BatchSpec(worlds, len(worlds), 10**6, 2**31)


def heterogeneous(fixtures=surface_pump_fixtures, arm="release", worlds=3):
    return cohort([definition(fixtures, arm, scale=1 + 0.1 * i) for i in range(worlds)])


def close(a, b, rtol=1e-12):
    """Per field: |a - b| <= rtol * max|b| (a few ulp of accumulated rounding)."""
    for name, x, y in zip(type(b)._fields, a, b, strict=True):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape, name
        assert np.max(np.abs(x - y), initial=0) <= rtol * np.max(np.abs(y), initial=0), name


@pytest.fixture(scope="module")
def references():
    """Each world's own windowed run with its observations, and the batch."""
    result = {}
    for name, fixtures, arm, worlds in (
        ("@1", surface_pump_fixtures, "release", 3),
        ("@2", surface_pump_v2_fixtures, "clamped", 2),
    ):
        spec = heterogeneous(fixtures, arm, worlds)
        scalar = {}
        for world in spec.worlds:
            seen = []
            final = run_windowed(world.simulation, POLICY, sink=lambda w, seen=seen: seen.append(w))
            scalar[world.world_id] = final, seen
        windows = []
        result[name] = spec, scalar, run_vector_windowed(spec, POLICY, sink=windows.append), windows
    return result


@pytest.mark.parametrize("name", ["@1", "@2"])
def test_batch_reproduces_independent_worlds_within_rounding(name, references):
    spec, scalar, batch, windows = references[name]
    assert batch.resources["mapping"] == "vmap_device_checks@1"
    for world in spec.worlds:
        own, seen = scalar[world.world_id]
        vector = batch.worlds[world.world_id]
        assert vector.final.step_index == own.final.step_index
        assert vector.final.time == own.final.time
        assert vector.final.event_index == own.final.event_index
        close(vector.final.state, own.final.state)
        assert vector.resources["windows"] == own.resources["windows"]
        assert vector.resources["validated_observations"] == own.resources["validated_observations"]
        observed = [
            w.observations[world.world_id] for w in windows if world.world_id in w.observations
        ]
        expected = [w.observations for w in seen if len(w.observations.times)]
        assert len(observed) == len(expected)
        for a, b in zip(observed, expected, strict=True):
            np.testing.assert_array_equal(a.times, b.times)
            assert np.max(np.abs(a.membrane_voltage_V - b.membrane_voltage_V)) <= 1e-13
        # Row-by-row agreement is tests/unit/test_surface_pump_device_checks.py;
        # here the merged maxima: the energy residual is a truncation quantity.
        assert vector.diagnostics.keys() == own.diagnostics.keys()
        for key in ("max_energy_balance_error_pJ", "max_energy_balance_relative"):
            value = own.diagnostics[key]
            assert abs(vector.diagnostics[key] - value) <= 1e-9 * value + 1e-15, key
        assert vector.diagnostics["max_global_charge_bound_ratio"] < 0.1


def test_held_controls_equal_per_step_controls():
    spec = definition(change=dict(availability=0.25))
    grid = EventGrid(spec)
    times = np.array([grid[i] for i in range(len(grid))])
    table, index = held_controls(spec, times, 4)
    expected = control_values(spec, times[:-1])
    for a, b in zip(table, expected, strict=True):
        np.testing.assert_array_equal(np.asarray(a)[index], b)
    with pytest.raises(ValueError, match="more control segments"):
        held_controls(spec, times, 1)


def corrupted_step(kind):
    original = surface_pump.checked_step

    def step(state, dt, control, p, active):
        updated, ok = original(state, dt, control, p, active)
        bad = control.pump[0] == 0.5
        if kind == "refuse":
            return jax.tree.map(lambda a, b: jnp.where(bad, a, b), state, updated), ok & ~bad
        supplied = updated.reservoir_supplied + jnp.where(bad & p.reservoir, 1e-6, 0.0)
        return updated._replace(reservoir_supplied=supplied), ok

    return step


def host_first_failure(spec, step):
    """The first row that the host checks refuse on a trajectory of ``step``."""
    grid = EventGrid(spec)
    times = np.array([grid[i] for i in range(len(grid))])
    controls = control_values(spec, times[:-1])
    start = initialise(spec)
    layout = type(start.layout)(*(np.asarray(v) for v in start.layout))
    advance = jax.jit(step)
    rows, state = [start.state], start.state
    for i in range(len(times) - 1):
        control = type(controls)(*(v[i] for v in controls))
        state, ok = advance(state, times[i + 1] - times[i], control, layout, layout.active)
        if not bool(ok):
            return i + 1, "refused"
        rows.append(state)
        history = surface_pump.STATE_TYPE(
            *(np.stack([np.asarray(r[k]) for r in rows]) for k in range(len(state)))
        )
        try:
            surface_pump.check_values(history, spec)
        except NumericalError as error:
            return i + 1, str(error)
    return None, None


@pytest.mark.parametrize("kind", ["ledger", "refuse"])
def test_injected_failure_stops_both_paths_at_the_same_step(kind, monkeypatch):
    specs = [
        definition(surface_pump_fixtures, "clamped"),
        definition(surface_pump_fixtures, "clamped", change=dict(availability=0.5)),
        definition(surface_pump_fixtures, "clamped", scale=1.1),
    ]
    spec = cohort(specs)
    step = corrupted_step(kind)
    row, message = host_first_failure(specs[1], step)
    grid = EventGrid(specs[1])
    assert row == grid.exact_index(CHANGE) + 1
    monkeypatch.setattr(surface_pump, "checked_step", step)
    with pytest.raises(WorldCheckError) as caught:
        run_vector_windowed(spec, POLICY)
    error = caught.value
    assert error.world_id == 2 and error.step_index == row
    assert error.time_interval == (grid[row - 1], grid[row])
    with pytest.raises(NumericalError) as sequential:
        run_batch_windowed(spec, POLICY)
    if kind == "refuse":
        assert error.checks == ("step",)
        interval = f"[{grid[row - 1]}, {grid[row]}]"
        assert f"World 2: numerical failure on {interval}" in str(sequential.value)
        assert f"World 2: numerical failure on {interval}" in str(error)
    else:  # The first failed check in host order is the host's failure.
        assert surface_pump.device_failure_message(error.checks[0]) == message
        assert str(sequential.value).startswith(f"World 2: {message}")
        assert str(error).startswith(f"World 2: {message}")
        assert f"at accepted time {grid[row]}; vectorized batch refused" in str(error)


def test_restart_from_a_window_checkpoint_is_bitwise(tmp_path, references):
    spec, _, uninterrupted, _ = references["@1"]
    windows = iter_vector_windows(spec, POLICY)
    checkpoints = dict(next(windows).checkpoints)  # Resume with the same window shape.
    windows.close()
    write_batch_snapshot(tmp_path / "cohort", spec, checkpoints)
    saved = load_batch_snapshot(tmp_path / "cohort")
    resumed = run_vector_windowed(saved.spec, POLICY, checkpoints=saved.checkpoints)
    for identity, world in resumed.worlds.items():
        assert world.final.step_index == uninterrupted.worlds[identity].final.step_index
        for a, b in zip(world.final.state, uninterrupted.worlds[identity].final.state, strict=True):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))


def ionic_definition(**extra):
    simulation = definition(surface_pump_fixtures, "release").to_dict()
    return dict(model="ionic_worlds@1", simulation=simulation, worlds=3, window_steps=5) | extra


def test_ionic_option_is_explicit_and_keeps_default_fingerprints():
    from cells.ensemble import ionic

    default = ionic.parse_spec(ionic_definition())
    assert "world_batching" not in default.to_dict()
    assert (
        default.fingerprint
        == ionic.parse_spec(ionic_definition(world_batching="lax_map")).fingerprint
    )
    vector = ionic.parse_spec(ionic_definition(world_batching="vmap"))
    assert vector.to_dict()["world_batching"] == "vmap"
    assert ionic.parse_spec(vector.to_dict()) == vector
    assert vector.fingerprint != default.fingerprint
    with pytest.raises(ValueError, match="world_batching"):
        ionic.parse_spec(ionic_definition(world_batching="pmap"))
    tissue = surface_pump_fixtures.reduction("release")  # resolved_tissue@2: no device checks
    with pytest.raises(ValueError, match="device checks"):
        ionic.parse_spec(
            dict(model="ionic_worlds@1", simulation=tissue, worlds=2, world_batching="vmap")
        )


def test_ionic_vmap_pause_and_resume_is_bitwise(tmp_path):
    from cells.ensemble import ionic

    spec = ionic.parse_spec(ionic_definition(world_batching="vmap"))
    complete, report = ionic.run(spec, backend="cpu")
    steps = len(EventGrid(spec.simulation)) - 1
    assert report["world_batching"] == "vmap" and report["integrated_world_steps"] == 3 * steps
    reference, _ = ionic.run(ionic.parse_spec(ionic_definition()), backend="cpu")
    for identity, checkpoint in complete.items():
        close(checkpoint.state, reference[identity].state)

    class Pause(Exception):
        pass

    saved = {}

    def pause(chunk, current, _):
        saved.update(current)
        if chunk == 1:
            raise Pause

    with pytest.raises(Pause):
        ionic.run(spec, backend="cpu", callback=pause)
    kind = jax.devices("cpu")[0].device_kind
    execution = dict(backend="cpu", device_index=0, device_kind=kind)
    ionic.write_checkpoint(tmp_path / "paused", spec, saved, execution=execution)
    loaded, state, _ = ionic.load_checkpoint(tmp_path / "paused", backend="cpu")
    assert loaded == spec
    resumed, _ = ionic.run(loaded, backend="cpu", state=state)
    for identity, checkpoint in resumed.items():
        assert checkpoint.step_index == complete[identity].step_index
        for a, b in zip(checkpoint.state, complete[identity].state, strict=True):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
