"""Vectorized resolved_pump_tissue@3 worlds (core/vector_windows.py) against single worlds.

A batch of heterogeneous worlds with all five channel laws (the eight-population
fixture, channels switched on mid-run) reproduces each world's own windowed run
to rounding; test_vector_windows_v3_bitwise.py shows it is bitwise with XLA's
algebraic rewrites and fusion disabled. Faults injected into one world's
accepted rows (a channel-transfer booking, a channel gate leaving [0, 1]) or a
refused step stop the vectorized and the sequential (lax.map, host-checked)
paths at the same step with the same check, and the failing world refuses its
window: no world's state from that window is accepted. ionic_worlds@1 admits
@3 with world_batching "vmap" as an explicit option.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.batch_windows import run_batch_windowed
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values
from cells.core.specs import parse_spec
from cells.core.state import initialise
from cells.core.vector_windows import WorldCheckError, iter_vector_windows, run_vector_windowed
from cells.core.windows import WindowPolicy, run_windowed
from cells.models import surface_pump, surface_pump_v3
from cells.numerics import surface_imex as imex
from validation.tissue import surface_pump_v3_fixtures as fixtures

POLICY = WindowPolicy(5, "checkpoints")
CHANGE = 0.0005  # A world-specific channel schedule change used to inject faults.
FAULTY = 0.5  # The availability that marks the faulty world's steps after the change.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def definition(arm="release", *, scale=1.0, change=None):
    raw = fixtures.definition(arm, solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    for membrane in raw["model"]["membranes"]:
        membrane["pump"]["capacity_fmol_per_s"] *= scale
    for channel in raw["model"]["channels"]:
        channel["max_permeability_m_per_s"] *= scale
    if change is not None:
        control = raw["experiment"]["channel_controls"][0]
        held = control["schedule"][-1]["availability"]
        control["schedule"] = [
            dict(time=0.0, availability=held),
            dict(time=change, availability=FAULTY),
        ]
    return parse_spec(raw)


def cohort(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return BatchSpec(worlds, len(worlds), 10**6, 2**31)


def close(a, b, rtol=1e-12):
    """Per field: |a - b| <= rtol * max|b| (a few ulp of accumulated rounding)."""
    for name, x, y in zip(type(b)._fields, a, b, strict=True):
        x, y = np.asarray(x), np.asarray(y)
        assert x.shape == y.shape, name
        assert np.max(np.abs(x - y), initial=0) <= rtol * np.max(np.abs(y), initial=0), name


@pytest.fixture(scope="module")
def reference():
    """Three heterogeneous worlds: the batch and each world's own windowed run."""
    spec = cohort([definition(scale=1 + 0.1 * i) for i in range(3)])
    scalar = {}
    for world in spec.worlds:
        seen = []
        final = run_windowed(world.simulation, POLICY, sink=lambda w, seen=seen: seen.append(w))
        scalar[world.world_id] = final, seen
    windows = []
    return spec, scalar, run_vector_windowed(spec, POLICY, sink=windows.append), windows


def test_batch_reproduces_independent_worlds_within_rounding(reference):
    spec, scalar, batch, windows = reference
    assert batch.resources["mapping"] == "vmap_device_checks@1"
    assert batch.worlds[1].final.state.channel_transferred.shape[-1] == 9  # Padded slot.
    for world in spec.worlds:
        own, seen = scalar[world.world_id]
        vector = batch.worlds[world.world_id]
        assert vector.final.step_index == own.final.step_index
        assert vector.final.time == own.final.time
        assert vector.final.event_index == own.final.event_index
        assert np.any(np.asarray(own.final.state.channel_transferred) != 0)
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
            assert np.max(np.abs(a.channel_targets - b.channel_targets)) <= 1e-13
        # Row-by-row agreement is test_surface_pump_v3_device_checks.py; here the
        # merged maxima: the energy residual is a truncation quantity.
        assert vector.diagnostics.keys() == own.diagnostics.keys()
        for key in ("max_energy_balance_error_pJ", "max_energy_balance_relative"):
            value = own.diagnostics[key]
            assert abs(vector.diagnostics[key] - value) <= 1e-9 * value + 1e-15, key
        assert vector.diagnostics["max_global_charge_bound_ratio"] < 0.1


def corrupted_step(kind):
    """@3's checked step, wrong in a world's rows once its channel 0 is at FAULTY."""
    original = surface_pump_v3.checked_step

    def step(state, dt, control, p, active):
        updated, ok = original(state, dt, control, p, active)
        bad = control.channel[0] == FAULTY
        if kind == "refuse":
            return jax.tree.map(lambda a, b: jnp.where(bad, a, b), state, updated), ok & ~bad
        if kind == "channel_ledger":  # K booked through channel 0 that no inventory holds.
            moved = updated.channel_transferred.at[1, 0].add(jnp.where(bad, 1e-6, 0.0))
            return updated._replace(channel_transferred=moved), ok
        # A Kv1.5 activation gate above 1.
        gate = updated.channel_gate.at[0, 0].set(
            jnp.where(bad, 1.0 + 1e-9, updated.channel_gate[0, 0])
        )
        return updated._replace(channel_gate=gate), ok

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
        history = surface_pump_v3.STATE_TYPE(
            *(np.stack([np.asarray(r[k]) for r in rows]) for k in range(len(state)))
        )
        try:
            surface_pump_v3.check_values(history, spec, steps=np.arange(len(rows)))
        except NumericalError as error:
            return i + 1, str(error)
    return None, None


# kind: (first failed check, host message, schedule change). A step from an
# invalid gate state refuses itself, which the sequential path reports before
# its host checks, so that fault's first row closes a window there. Changes lie
# on the float grid i * dt (0.0009 does not: it would add a 1e-19 s step).
FAILURES = {
    "channel_ledger": ("local", surface_pump.LEDGER_MESSAGE + "local", CHANGE),
    "gate": ("domain", surface_pump.DOMAIN_MESSAGE, 9 * 1e-4),
    "refuse": ("step", "refused", CHANGE),
}


@pytest.mark.parametrize("kind", FAILURES)
def test_a_failing_world_refuses_its_window_on_both_paths(kind, monkeypatch):
    check, message, change = FAILURES[kind]
    specs = [
        definition("clamped"),
        definition("clamped", change=change),
        definition("clamped", scale=1.1),
    ]
    spec = cohort(specs)
    step = corrupted_step(kind)
    grid = EventGrid(specs[1])
    row = grid.exact_index(change) + 1
    assert len(grid) == 13 and (kind != "gate" or row % POLICY.window_steps == 0)
    assert host_first_failure(specs[1], step) == (row, message)
    assert host_first_failure(specs[0], step) == (None, None)
    monkeypatch.setattr(surface_pump_v3, "checked_step", step)
    accepted = []
    with pytest.raises(WorldCheckError) as caught:
        for window in iter_vector_windows(spec, POLICY):
            accepted.append(window)
    error = caught.value
    assert error.world_id == 2 and error.step_index == row
    assert error.time_interval == (grid[row - 1], grid[row])
    assert error.checks[0] == check
    # Nothing from the failing window is accepted, for any world of the batch.
    start = (row - 1) // POLICY.window_steps * POLICY.window_steps
    assert accepted and all(c.step_index <= start for w in accepted for c in w.checkpoints.values())
    assert {c.step_index for c in accepted[-1].checkpoints.values()} == {start}
    with pytest.raises(NumericalError) as sequential:
        run_batch_windowed(spec, POLICY)
    if kind == "refuse":
        interval = f"[{grid[row - 1]}, {grid[row]}]"
        assert f"World 2: numerical failure on {interval}" in str(sequential.value)
        assert f"World 2: numerical failure on {interval}" in str(error)
    else:  # The first failed check in host order is the host's failure.
        assert surface_pump_v3.device_failure_message(check) == message
        assert str(sequential.value).startswith(f"World 2: {message}")
        assert str(error).startswith(f"World 2: {message}")
        assert f"at accepted time {grid[row]}; vectorized batch refused" in str(error)


def ionic_definition(**extra):
    simulation = definition().to_dict()
    return dict(model="ionic_worlds@1", simulation=simulation, worlds=2, window_steps=5) | extra


def test_ionic_admits_resolved_pump_tissue_v3_with_an_explicit_vmap_option(reference):
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
    complete, report = ionic.run(vector, backend="cpu")
    assert report["world_batching"] == "vmap"
    assert report["physical_model"] == "resolved_pump_tissue@3"
    steps = len(EventGrid(vector.simulation)) - 1
    assert report["integrated_world_steps"] == 2 * steps
    # Replicas of the reference's first world: its own windowed run, to rounding.
    own, _ = reference[1][1]
    for checkpoint in complete.values():
        assert checkpoint.step_index == own.final.step_index
        close(checkpoint.state, own.final.state)
