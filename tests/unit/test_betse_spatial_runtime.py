"""Configured discrete BETSE execution against qualified saved trajectories."""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.betse_spatial_spec import SOLVER_ID, definition_arrays
from cells.core.errors import NumericalError
from cells.core.runner import (
    _compiled_discrete_rollout,
    branch_checkpoint,
    run,
    timeline,
    validate_checkpoint,
)
from cells.core.specs import ConfigError, load_spec, parse_spec
from cells.core.state import Checkpoint
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import betse_spatial as model
from cells.models.registry import get_model
from cells.numerics import betse_active as active
from cells.numerics import betse_spatial as passive
from cells.window_io import write_windowed_run
from tests.unit import test_betse_spatial_active as short
from tests.unit.test_windows import assert_windows
from validation.betse.spatial_active import fixtures, runtime

PROTOCOL = runtime.protocol()
CASES = [(case, index) for case in PROTOCOL["cases"] for index in PROTOCOL["step_indices"]]
common = short.short
BACKEND, EVIDENCE = common.BACKEND, common.EVIDENCE


@pytest.fixture(scope="module")
def prior():
    return runtime.baseline()


def test_runtime_baseline(prior):
    common.evidence("runtime-baseline", prior)


@pytest.fixture(scope="module")
def trajectories(prior):
    return {
        (case, index): run(parse_spec(runtime.definition(case, index, backend=BACKEND)))
        for case, index in CASES
    }


def state_arrays(history):
    return {
        ("state__" if name in passive.State._fields else "active__") + name: value[..., 0]
        if name in ("step_count", "elapsed_s")
        else value
        for name, value in history._asdict().items()
    }


def saved_arrays(result):
    names = dict(
        zip(
            passive.Field._fields,
            ("vm", "vm_ave", "rho_cells", "Phi_b", "v_env", "E_env_x", "E_env_y"),
            strict=True,
        )
    )
    return state_arrays(result.history) | {
        "observed__" + name: getattr(result.observations, key) for key, name in names.items()
    }


def test_registry_roundtrip_and_export():
    spec = load_spec(runtime.ROOT / "configs/betse_spatial_active.json")
    assert get_model(spec.model) is model and spec.execution.solver == SOLVER_ID
    assert parse_spec(spec.to_dict()) == spec
    assert spec.model.species_ids == ("Na", "K", "Cl", "Ca", "P", "M")
    assert spec.to_dict() == parse_spec(runtime.definition(backend="gpu")).to_dict()


@pytest.mark.parametrize(
    "fault",
    (
        "solver",
        "precision",
        "backend",
        "boolean_number",
        "fractional_owner",
        "asymmetric_partner",
        "capacity",
        "off_grid",
        "long_horizon",
        "large_step",
        "zero_substrate",
        "zero_concentration",
        "gate",
        "nonfinite",
        "missing_state",
        "species",
        "off_grid_end",
        "extra_control",
    ),
)
def test_rejected_config(fault):
    raw = runtime.definition(steps=8)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if fault in ("solver", "precision", "backend"):
        x[fault] = {"solver": "rk4", "precision": "float32", "backend": "tpu"}[fault]
    elif fault == "boolean_number":
        m["tissue"]["height"] = True
    elif fault == "fractional_owner":
        m["tissue"]["cell_owner"][0] = 0.5
    elif fault == "asymmetric_partner":
        m["tissue"]["partner"][0] = 1
    elif fault == "capacity":
        x["capacity"] += 1
    elif fault == "off_grid":
        e["observation_times"][1] = x["dt"] * 0.4
    elif fault == "long_horizon":
        e["end_time"] = 512e-6
    elif fault == "large_step":
        x["dt"] = 2e-6
    elif fault == "zero_substrate":
        m["pump"]["atp_mM"][0] = 0
    elif fault == "zero_concentration":
        m["initial"]["outside_concentration"][0][0] = 0
    elif fault == "gate":
        m["initial"]["m_gate"][0] = 1.1
    elif fault == "nonfinite":
        m["pump_available"][0] = float("nan")
    elif fault == "missing_state":
        del m["initial"]["membrane_concentration"]
    elif fault == "species":
        m["species"][0], m["species"][1] = m["species"][1], m["species"][0]
    elif fault == "off_grid_end":
        e["end_time"] -= x["dt"] * 0.4
    else:
        e["pump_controls"] = []
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_host_adapter_and_fixed_clock():
    spec = parse_spec(runtime.definition())
    expected, p = definition_arrays(spec.model)
    root = Path(PROTOCOL["prior_binding"]["root"])
    folder = root / "evidence/cpu/long-active-native/coupled/step-2/observed"
    row = json.loads((folder / "result.json").read_text())
    with np.load(folder / "trace.npz", allow_pickle=False) as trace:
        source_state, source_layout = fixtures.prepare(
            row, trace, json.loads((root / "component-protocol.json").read_text())
        )
    common.bits(expected, source_state)
    common.bits(p, source_layout)
    state, layout = model.initial_values(spec)
    common.bits(model.unflatten(state), expected)
    common.bits(model.parameters(spec, layout), p)
    grid = timeline(spec)
    steps = model.integration_steps(spec, grid)
    assert np.all(steps == spec.execution.dt)
    assert np.any(np.diff(grid) != spec.execution.dt)
    assert len(state) == 13 and state.elapsed_s.shape == state.step_count.shape == (1,)
    assert model.check_values(state, spec)["max_material_residual_fmol"] == 0
    changed = state._replace(
        step_count=np.array([1], dtype=np.int64), elapsed_s=np.array([spec.execution.dt])
    )
    with pytest.raises(ConfigError, match="clock differs"):
        validate_checkpoint(spec, Checkpoint(changed, layout, 0.0, 0, -1))


@pytest.mark.parametrize(
    "field",
    (
        "reservoir_reset_fmol",
        "stencil_exchange_fmol",
        "membrane_inward_fmol",
        "channel_inward_fmol",
        "junction_outward_fmol",
    ),
)
def test_host_missing_material_is_rejected(field):
    spec = parse_spec(runtime.definition(steps=8))
    state, _ = model.initial_values(spec)
    getattr(state, field).flat[0] += 1e-6
    with pytest.raises(NumericalError, match="material balance"):
        model.check_values(state, spec)


def test_compiled_short_runtime_smoke():
    raw = runtime.definition("coupled", 0, backend=BACKEND, steps=8)
    result = run(parse_spec(raw))
    assert all(v.device.platform == BACKEND for v in result.final.state)
    p = model.parameters(result.spec, result.final.layout)
    initial, _ = model.initial_values(result.spec)
    target = model.unflatten(initial)
    for _ in range(8):
        target, _, ok = active.step(target, jax.tree.map(np.asarray, p), 1e-6, xp=np)
        assert ok
    actual = state_arrays(model.STATE_TYPE(*(np.asarray(v) for v in result.final.state)))
    expected = state_arrays(model.flatten(target))
    short.compare_cpu_gpu_arrays(actual, expected, np.asarray(p.tissue.membrane_area))


@pytest.mark.parametrize("case,index", CASES)
def test_runtime_matches_qualified_histories(case, index, trajectories):
    value = trajectories[(case, index)]
    actual = {name: v[1:] for name, v in state_arrays(value.history).items()}
    path = Path(PROTOCOL["prior_binding"]["root"]) / (
        f"evidence/{BACKEND}/long-active-native-trajectory-{case}-{index}.npz"
    )
    with np.load(path, allow_pickle=False) as saved:
        expected = {name: saved[name] for name in actual}
        count = short.compare_cpu_gpu_arrays(
            actual, expected, value.final.layout.tissue_membrane_area
        )
        bitwise = all(np.array_equal(actual[k], expected[k]) for k in actual)
    common.evidence(
        f"runtime-qualified-state-{case}-{index}",
        dict(
            status="passed",
            compared_scalars=count,
            all_state_arrays_bitwise=bitwise,
            state_arrays=13,
            target=str(path),
            diagnostics=value.diagnostics,
            scope="Full configured history versus same-backend qualified saved Cells state",
        ),
        saved_arrays(value),
    )


def test_runtime_disk_and_windows(trajectories, tmp_path):
    full = trajectories[("coupled", 2)]
    cut = 257
    snapshot = tmp_path / "ordinary-snapshot"
    write_snapshot(snapshot, full.spec, full.checkpoint_at(float(full.times[cut])))
    saved = load_snapshot(snapshot)
    resumed = run(saved.spec, saved.checkpoint)
    common.bits(resumed.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
    assert_windows(list(iter_windows(full.spec, WindowPolicy(389))), full)
    assert_windows(list(iter_windows(saved.spec, WindowPolicy(173), saved.checkpoint)), resumed)
    terminal = run(full.spec, full.final)
    assert len(terminal.times) == 1
    common.bits(terminal.final.state, full.final.state)
    write_run(tmp_path / "ordinary-run", full, checkpoint_times=(float(full.times[cut]),))
    common.bits(
        load_snapshot(tmp_path / "ordinary-run/checkpoint_final").checkpoint.state, full.final.state
    )
    write_windowed_run(tmp_path / "windowed-run", full.spec, WindowPolicy(257, "full"))
    common.bits(
        load_snapshot(tmp_path / "windowed-run/checkpoint_final").checkpoint.state, full.final.state
    )
    common.evidence(
        "runtime-disk-windows",
        dict(
            status="passed",
            state_arrays=13,
            comparison="bitwise",
            window_steps=[389, 173, 257],
            disk=True,
            terminal=True,
        ),
    )


def test_runtime_worlds(tmp_path):
    specs = [
        parse_spec(runtime.definition(case, index, backend=BACKEND, steps=count))
        for case, index, count in (("coupled", 0, 64), ("pump", 1, 37), ("channel", 2, 128))
    ]
    batch = BatchSpec(tuple(WorldSpec(i + 10, s) for i, s in enumerate(specs)), 4, 4096, 1024**3)
    full = run_batch(batch)
    for world in batch.worlds:
        common.bits(full.worlds[world.world_id].history, run(world.simulation).history)
    reordered = run_batch(replace(batch, worlds=tuple(reversed(batch.worlds))))
    for world in batch.worlds:
        common.bits(reordered.worlds[world.world_id].history, full.worlds[world.world_id].history)
        alone = run_batch(replace(batch, worlds=(world,)))
        common.bits(alone.worlds[world.world_id].history, full.worlds[world.world_id].history)
    rounds = list(iter_batch_windows(batch, WindowPolicy(23)))
    for world in batch.worlds:
        parts = [r.worlds[world.world_id] for r in rounds if world.world_id in r.worlds]
        assert_windows(parts, full.worlds[world.world_id])
    checkpoints = {
        i: result.checkpoint_at(float(result.times[min(17, len(result.times) - 1)]))
        for i, result in full.worlds.items()
    }
    checkpoints[11] = full.worlds[11].final  # A finished world must remain unchanged.
    write_batch_snapshot(tmp_path / "batch", batch, checkpoints)
    saved = load_batch_snapshot(tmp_path / "batch")
    resumed = run_batch(saved.spec, saved.checkpoints)
    for identity, result in resumed.worlds.items():
        start = checkpoints[identity].step_index
        common.bits(
            result.history, model.STATE_TYPE(*(v[start:] for v in full.worlds[identity].history))
        )
    common.evidence(
        "runtime-worlds",
        dict(
            status="passed",
            worlds=3,
            clocks="independent",
            comparison="bitwise",
            reordered=True,
            partitions=True,
            disk=True,
            finished_world=True,
        ),
    )


def test_runtime_horizon_branch(trajectories):
    full = trajectories[("coupled", 0)]
    short_raw = full.spec.to_dict()
    short_raw["experiment"] = dict(end_time=64e-6, observation_times=[0, 64e-6])
    short_spec = parse_spec(short_raw)
    prefix = run(short_spec)
    checkpoint = branch_checkpoint(short_spec, prefix.final, full.spec)
    suffix = run(full.spec, checkpoint)
    common.bits(prefix.history, model.STATE_TYPE(*(v[:65] for v in full.history)))
    common.bits(suffix.history, model.STATE_TYPE(*(v[64:] for v in full.history)))
    changed = full.spec.to_dict()
    changed["model"]["pump_available"][0] = 0
    with pytest.raises(ConfigError, match="may not change model"):
        branch_checkpoint(short_spec, prefix.final, parse_spec(changed))
    common.evidence(
        "runtime-horizon-branch",
        dict(
            status="passed",
            comparison="bitwise",
            original_duration_s=64e-6,
            extended_duration_s=256e-6,
            changed_model_rejected=True,
        ),
    )


def test_runtime_domain_controls():
    raw = runtime.definition(backend=BACKEND, steps=4)
    raw["model"]["pump"]["capacity_fmol_s"] = [1e12] * raw["execution"]["membrane_capacity"]
    spec = parse_spec(raw)
    with pytest.raises(NumericalError, match="domain failure"):
        run(spec)
    state, layout = model.initial_values(spec)
    device = jax.devices(BACKEND)[0]
    args = jax.device_put(
        (
            state,
            np.full(4, spec.execution.dt),
            np.zeros(4),
            model.parameters(spec, layout),
            layout.active,
        ),
        device,
    )
    final, history, valid = _compiled_discrete_rollout(*args, model.checked_step)
    assert not np.asarray(valid).any()
    common.bits(final, state)
    common.bits(history, model.STATE_TYPE(*(np.stack([v] * 4) for v in state)))
    common.evidence(
        "runtime-domain-controls",
        dict(
            status="passed",
            failure_latched=True,
            complete_state_retained=True,
            high_capacity_negative_trial_rejected=True,
        ),
    )


def test_runtime_eager_matches_compiled():
    raw = runtime.definition(backend=BACKEND, steps=3)
    compiled = run(parse_spec(raw))
    raw["execution"]["jit"] = False
    eager = run(parse_spec(raw))
    short.compare_cpu_gpu_arrays(
        saved_arrays(eager), saved_arrays(compiled), compiled.final.layout.tissue_membrane_area
    )


def test_runtime_cli(tmp_path):
    raw = runtime.definition(backend=BACKEND, steps=4)
    path, output = tmp_path / "definition.json", tmp_path / "cli-run"
    path.write_text(json.dumps(raw))
    for arguments in (["validate", str(path)], ["run", str(path), "--output", str(output)]):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "cells", *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert not result.stderr, result.stderr
        json.loads(result.stdout)
    saved = load_snapshot(output / "checkpoint_final")
    assert saved.checkpoint.step_index == 4
    assert len(saved.checkpoint.state) == 13 and saved.spec.execution.solver == SOLVER_ID
    common.evidence(
        "runtime-cli",
        dict(
            status="passed",
            validate=True,
            run=True,
            complete_checkpoint_restored=True,
            solver=SOLVER_ID,
        ),
    )


def test_runtime_cpu_gpu(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved configured CPU histories")
    assert EVIDENCE
    count = 0
    for (case, index), result in trajectories.items():
        path = Path(EVIDENCE) / "cpu" / f"runtime-qualified-state-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += short.compare_cpu_gpu_arrays(
                saved_arrays(result), saved, result.final.layout.tissue_membrane_area
            )
    common.evidence("runtime-cpu-gpu", dict(status="passed", compared_scalars=count))
