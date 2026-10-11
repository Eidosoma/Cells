"""Evolving cross-region tissue: independent dynamics, controls and complete replay."""

import json
import os
import subprocess
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import spatial_junction as previous
from cells.models import tissue as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from validation.tissue import dynamics_fixtures as fixtures
from validation.tissue import dynamics_reference as reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
ARMS = ("baseline", "blocked", "release", "same_region")
STATE_ATOL, STATE_RTOL = 2e-11, 3e-9
VOLTAGE_ATOL = 2e-8


def evidence(name, value):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.0])))
    return spec, state, layout, control


def exact(left, right):
    for a, b in zip(left, right, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_registered_roundtrip_and_ensemble(backend):
    raw = fixtures.definition(backend=backend)
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    assert (
        parse_ensemble({"model": "ionic_worlds@1", "simulation": raw, "worlds": 2}).simulation
        == spec
    )


@pytest.mark.parametrize("arm", ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_full_stage_rates_and_ownership(arm, padded):
    raw = fixtures.definition(arm=arm, padded=padded)
    _, state, layout, control = initial(raw)
    rates = model.rhs(state, control, layout, layout.active, xp=np)
    c = reference.bind(raw)
    expected = reference.rhs(c, reference.control_at(raw, 0.0), reference.initial(c))
    np.testing.assert_allclose(
        reference.flatten(c, rates._asdict()), expected, rtol=2e-12, atol=2e-12
    )
    charge = model.spatial.component_charge(rates, layout, xp=np, derivative=True)
    np.testing.assert_allclose(charge, 0, rtol=0, atol=2e-23)
    np.testing.assert_allclose(
        np.sum(rates.amount_increment, axis=-1)
        + np.sum(rates.extracellular_amount_increment, axis=-1),
        0,
        rtol=0,
        atol=2e-15,
    )


def test_actual_field_control_changes_voltage_without_resetting_intrinsic_gate():
    _, state, layout, control = initial()
    blocked = control._replace(junction=np.zeros_like(control.junction))
    a = model.field_values(state, control.junction, layout, xp=np)
    b = model.field_values(state, blocked.junction, layout, xp=np)
    assert np.max(np.abs(a.junction_voltage_V - b.junction_voltage_V)) > 1e-4
    assert np.all(b.junction_flux_fmol_per_s == 0)
    rates = model.rhs(state, blocked, layout, layout.active, xp=np)
    assert np.any(rates.junction_gate != 0)
    np.testing.assert_array_equal(state.junction_gate, [0.6, 0.0])


@pytest.mark.parametrize(
    "fault", ["owner", "charge", "closure", "solver", "identity", "old_family", "off_grid"]
)
def test_unsupported_or_inconsistent_meanings_are_rejected(fault):
    raw = fixtures.definition()
    if fault == "owner":
        raw["model"]["cells"][1]["membrane"]["outside"] = "missing"
    elif fault == "charge":
        raw["model"]["surroundings"][0]["fixed_charge_equivalent_fmol"] += 0.01
    elif fault == "closure":
        raw["model"]["closure"]["law"] = "capacitive_components_current_continuity@1"
    elif fault == "solver":
        raw["execution"]["field_solver"] = "gauged_dense_kirchhoff@1"
    elif fault == "identity":
        raw["model"]["faces"][0]["id"] = "pump_0"
    elif fault == "old_family":
        raw["model"]["id"] = "spatial_extracellular@2"
        raw["model"]["closure"]["law"] = "capacitive_components_current_continuity@1"
        raw["execution"]["field_solver"] = "gauged_dense_kirchhoff@1"
    else:
        raw["experiment"]["observation_times"] = [0.0, 0.000073, 0.002]
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


@pytest.mark.parametrize(
    "field",
    ["extracellular_amount_increment", "junction_transferred", "face_transferred", "pump_cycles"],
)
def test_corrupt_owned_ledgers_are_rejected(field):
    spec, state, _, _ = initial()
    wrong = getattr(state, field).copy()
    wrong.flat[0] = 0.01
    with pytest.raises(NumericalError):
        model.check_values(state._replace(**{field: wrong}), spec)


def test_failed_field_never_yields_acceptable_rates(monkeypatch):
    _, state, layout, control = initial()
    solve = model.field.solve
    monkeypatch.setattr(
        model.field, "solve", lambda *a, **k: solve(*a, **k)._replace(converged=False)
    )
    assert not model.control_domain_valid(state, control, layout, layout.active, xp=np)
    assert any(
        not np.isfinite(v).all() for v in model.rhs(state, control, layout, layout.active, xp=np)
    )


def test_held_control_guard_rejects_invalid_rk4_stage_and_preserves_state():
    def valid(state, parameters, active):
        return jnp.asarray(True)

    def contextual(state, control, parameters, active):
        return jnp.all(state < control)

    valid.with_control = contextual

    def rhs(y, control, parameters, active):
        return jnp.ones_like(y)

    initial = jnp.asarray([0.0], dtype=jnp.float64)
    compute = jax.jit(lambda limit: rk4_checked_step(rhs, valid, initial, 1.0, limit, None, None))
    kept, passed = compute(0.75)
    assert not passed and kept == initial
    updated, passed = compute(2.0)
    assert passed and updated == 1.0


def test_held_control_guard_also_checks_the_combined_endpoint():
    def valid(state, parameters, active):
        return jnp.asarray(True)

    def contextual(state, control, parameters, active):
        # For y'=1-y, dt=1: RK4 trial states are 0, .5, .25, .75;
        # the combined endpoint is .625. Only that endpoint is inadmissible.
        return jnp.all((state <= control[0]) | (state >= control[1]))

    def rhs(state, control, parameters, active):
        return 1 - state

    valid.with_control = contextual
    start = jnp.asarray([0.0], dtype=jnp.float64)
    kept, passed = jax.jit(
        lambda: rk4_checked_step(rhs, valid, start, 1.0, jnp.asarray([0.6, 0.65]), None, None)
    )()
    assert not passed
    np.testing.assert_array_equal(kept, start)


@pytest.fixture(scope="module")
def trajectories(tmp_path_factory):
    root = tmp_path_factory.mktemp("tissue-trajectories")
    result = {}
    for arm in ARMS:
        spec = parse_spec(fixtures.definition(backend=BACKEND, arm=arm))
        value = run(spec)
        assert all(v.device.platform == BACKEND for v in value.final.state)
        write_run(root / arm, value, checkpoint_times=(0.001,))
        if EVIDENCE:
            target = Path(EVIDENCE) / BACKEND
            target.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(
                target / ("trajectory-" + arm + ".npz"),
                **{k: np.asarray(v) for k, v in value.history._asdict().items()},
                voltage_V=value.observations.voltage_V,
            )
        result[arm] = value
    return result


@pytest.mark.parametrize("arm", ARMS)
def test_independent_evolving_trajectories_and_accounting(arm, trajectories):
    value = trajectories[arm]
    raw = value.spec.to_dict()
    expected = reference.integrate(raw)
    actual = reference.flatten(reference.bind(raw), vars(value.observations))
    wanted = np.asarray(expected["state"])
    ratio = np.abs(actual - wanted) / (STATE_ATOL + STATE_RTOL * np.abs(wanted))
    assert np.max(ratio) <= 1
    increments = reference.unpack(reference.bind(raw), wanted)["amount_increment"]
    vm = reference.spatial.voltage(reference.bind(raw), increments)
    np.testing.assert_allclose(value.observations.voltage_V[:, :2], vm, rtol=0, atol=VOLTAGE_ATOL)
    assert value.diagnostics["max_energy_balance_error_pJ"] <= 2e-8
    assert value.diagnostics["max_component_charge_C"] <= 1e-20
    if arm == "blocked":
        assert not np.any(value.history.junction_transferred)
        assert np.any(value.history.junction_gate[-1] != value.history.junction_gate[0])
    if arm == "release":
        obs = value.observations
        assert not np.any(obs.junction_transferred[obs.times <= 0.001])
        assert np.any(obs.junction_current_A[obs.times == 0.001])
        assert np.any(obs.junction_transferred[-1])
    evidence(
        "trajectory-" + arm,
        {
            "status": "passed",
            "inputs": raw,
            "max_state_error_over_budget": float(np.max(ratio)),
            "physical_scalars": actual.size,
            "reference": expected,
            "diagnostics": value.diagnostics,
        },
    )


def test_timestep_refinement(trajectories):
    raw = trajectories["baseline"].spec.to_dict()
    c = reference.bind(raw)
    wanted = np.asarray(reference.integrate(raw)["state"])
    errors = []
    for dt in (0.0001, 0.00005, 0.000025):
        raw["execution"]["dt"] = dt
        value = trajectories["baseline"] if dt == 0.0001 else run(parse_spec(raw))
        actual = reference.flatten(c, vars(value.observations))
        errors.append(float(np.max(np.abs(actual - wanted))))
        np.testing.assert_allclose(actual, wanted, rtol=STATE_RTOL, atol=STATE_ATOL)
    assert errors[-1] <= max(errors[0] * 0.2, 3e-13)
    evidence(
        "trajectory-refinement",
        {
            "status": "passed",
            "dt_s": [0.0001, 0.00005, 0.000025],
            "max_absolute_state_errors": errors,
            "roundoff_floor": 3e-13,
        },
    )


def test_complete_disk_restart_branch_and_changed_windows(trajectories, tmp_path):
    value = trajectories["baseline"]
    cp = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, cp)
    saved = load_snapshot(tmp_path / "checkpoint")
    exact(saved.checkpoint.state, cp.state)
    resumed = run(saved.spec, saved.checkpoint)
    exact(resumed.history, tuple(v[cp.step_index :] for v in value.history))
    # Terminal reload must also work, including empty observer slope histories.
    terminal = run(value.spec, value.final)
    exact(tuple(v[0] for v in terminal.history), value.final.state)
    raw = value.spec.to_dict()
    raw["experiment"]["junction_controls"][0]["schedule"].append(
        {"time": cp.time, "open_fraction": 0.0}
    )
    changed = parse_spec(raw)
    branch = run(changed, branch_checkpoint(value.spec, cp, changed))
    exact(tuple(v[0] for v in branch.history), cp.state)
    np.testing.assert_array_equal(
        branch.history.junction_transferred[-1], cp.state.junction_transferred
    )
    assert np.any(branch.history.junction_gate[-1] != cp.state.junction_gate)
    parts = list(iter_windows(value.spec, WindowPolicy(7, "full"), saved.checkpoint))
    merged = tuple(
        np.concatenate([getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    exact(merged, resumed.history)
    process = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "cells",
            "resume",
            str(tmp_path / "checkpoint"),
            "--output",
            str(tmp_path / "fresh-process"),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    (tmp_path / "fresh.stdout.log").write_text(process.stdout)
    (tmp_path / "fresh.stderr.log").write_text(process.stderr)
    process.check_returncode()
    fresh = load_snapshot(tmp_path / "fresh-process/checkpoint_final")
    exact(fresh.checkpoint.state, resumed.final.state)
    evidence(
        "trajectory-restart",
        {
            "status": "passed",
            "complete_disk_state": True,
            "fresh_process": True,
            "changed_windows": True,
            "future_branch": True,
            "terminal_restart": True,
            "same_backend_comparison": "bitwise",
        },
    )


def test_world_batches_partition_and_independent_resume(trajectories, tmp_path):
    expected = [trajectories[a] for a in ("baseline", "release")]
    # Two worlds, each bounded by 20 nominal steps plus up to two control events.
    batch = BatchSpec(
        tuple(WorldSpec(i + 10, v.spec) for i, v in enumerate(expected)), 2, 44, 2**28
    )
    result = run_batch(batch)
    for identity, value in result.worlds.items():
        exact(value.history, expected[identity - 10].history)
    starts = result.checkpoint_at({10: 0.001, 11: 0.002})
    write_batch_snapshot(tmp_path / "batch", batch, starts)
    saved = load_batch_snapshot(tmp_path / "batch")
    parts = list(iter_batch_windows(saved.spec, WindowPolicy(7, "full"), saved.checkpoints))
    for identity in (10, 11):
        relevant = [part.worlds[identity] for part in parts if identity in part.worlds]
        merged = tuple(
            np.concatenate(
                [getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(relevant)]
            )
            for k in model.STATE_TYPE._fields
        )
        exact(
            merged, tuple(v[starts[identity].step_index :] for v in result.worlds[identity].history)
        )
        partition = BatchSpec((batch.worlds[identity - 10],), 1, 40, 2**28)
        exact(run_batch(partition).worlds[identity].history, result.worlds[identity].history)
    evidence(
        "trajectory-partition",
        {
            "status": "passed",
            "world_ids": [10, 11],
            "independent_restart_times": [0.001, 0.002],
            "partition_and_scalar": "bitwise",
        },
    )


def test_same_region_preserves_previous_dynamics(trajectories):
    value = trajectories["same_region"]
    raw = value.spec.to_dict()
    raw["model"]["id"] = "spatial_extracellular@2"
    raw["model"]["closure"]["law"] = "capacitive_components_current_continuity@1"
    raw["execution"]["field_solver"] = "gauged_dense_kirchhoff@1"
    prior = run(parse_spec(raw))
    assert get_model(prior.spec.model) is previous
    for actual, expected in zip(value.history, prior.history, strict=True):
        np.testing.assert_allclose(actual, expected, rtol=3e-10, atol=3e-13)
    evidence("trajectory-legacy", {"status": "passed", "scope": "Same-region @2 reduction"})


def test_cpu_gpu_complete_saved_trajectories(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    count = 0
    for arm, value in trajectories.items():
        with np.load(
            Path(EVIDENCE) / "cpu" / ("trajectory-" + arm + ".npz"), allow_pickle=False
        ) as saved:
            for k, actual in value.history._asdict().items():
                np.testing.assert_allclose(actual, saved[k], rtol=3e-10, atol=3e-13)
                count += actual.size
            np.testing.assert_allclose(
                value.observations.voltage_V, saved["voltage_V"], rtol=0, atol=3e-11
            )
    evidence(
        "trajectory-cpu-gpu",
        {
            "status": "passed",
            "complete_state_scalars": count,
            "state_rtol": 3e-10,
            "state_atol": 3e-13,
            "voltage_atol_V": 3e-11,
        },
    )
