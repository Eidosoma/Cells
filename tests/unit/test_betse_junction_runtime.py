"""Configured dynamic junctions against authenticated component trajectories."""

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows
from cells.core.betse_junction_spec import Control, definition_arrays
from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import (
    _compiled_discrete_rollout,
    branch_checkpoint,
    run,
    timeline,
    validate_checkpoint,
)
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, load_spec, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import betse_junction as model
from cells.models.registry import get_model
from cells.numerics import betse_junction as kernel
from cells.window_io import write_windowed_run
from tests.unit import test_betse_spatial_runtime as previous
from tests.unit.test_windows import assert_windows
from validation.betse.spatial_active import intervention_refinement as legacy
from validation.betse.spatial_active import junction_runtime as runtime
from validation.betse.spatial_active import junctions, refinement

PROTOCOL = runtime.protocol()
CASES = [(case, i) for case in PROTOCOL["cases"] for i in PROTOCOL["step_indices"]]
common, short = previous.common, previous.short
BACKEND, EVIDENCE = common.BACKEND, common.EVIDENCE


@pytest.fixture(scope="module")
def prior():
    return runtime.baseline()


def test_runtime_baseline(prior):
    common.evidence("junction-runtime-baseline", prior)


def reference_arrays(result):
    """Match the qualified observable layout without changing values or ordering."""
    data = previous.saved_arrays(result)
    # fixtures.comparison flattens these two potentials in C order. The two
    # electric-field components retain their grid axes in the frozen reference.
    grid = result.final.layout.tissue_boundary_values.shape
    samples = len(result.observations.times)
    for key in ("observed__Phi_b", "observed__v_env"):
        assert data[key].shape == (samples, *grid), key
        data[key] = data[key].reshape((samples, int(np.prod(grid))), order="C")
    return data


def arrays(result):
    data = reference_arrays(result)
    data["junction__open"] = data.pop("active__junction_open")
    return data


def compare(actual, expected, area):
    assert set(actual) == set(expected)
    ordinary = {k: v for k, v in actual.items() if k != "junction__open"}
    count = short.compare_cpu_gpu_arrays(ordinary, {k: expected[k] for k in ordinary}, area)
    a, b = actual["junction__open"], expected["junction__open"]
    assert a.shape == b.shape and a.dtype == b.dtype
    assert np.isfinite(a).all() and np.isfinite(b).all()
    np.testing.assert_allclose(
        a, b, atol=PROTOCOL["tolerances"]["gate_atol"], rtol=PROTOCOL["tolerances"]["gate_rtol"]
    )
    return count + a.size


def replay_batch():
    specs = [
        parse_spec(runtime.definition(c, i, backend=BACKEND, steps=n))
        for c, i, n in (("coupled", 0, 64), ("block_release", 1, 96), ("reversed", 0, 37))
    ]
    return BatchSpec(
        tuple(WorldSpec(i + 10, s) for i, s in enumerate(specs)),
        4,
        4096,
        PROTOCOL["resources"]["batch_max_working_bytes"],
    )


def test_host_definitions_and_resources():
    total = 0
    old = json.loads(
        (Path(PROTOCOL["prior_binding"]["root"]) / "component-protocol.json").read_text()
    )
    for case, index in CASES:
        raw = runtime.definition(case, index, backend=BACKEND)
        spec = parse_spec(raw)
        assert parse_spec(spec.to_dict()) == spec
        assert get_model(spec.model) is model
        state, p = definition_arrays(spec.model)
        flat, layout = model.initial_values(spec)
        common.bits(model.unflatten(flat), state)
        common.bits(model.parameters(spec, layout), p)
        assert len(flat) == 14
        grid = timeline(spec)
        expected = junctions.controls(
            next(c for c in old["cases"] if c["id"] == case),
            spec.execution.dt,
            len(grid) - 1,
            spec.execution.membrane_capacity,
        )
        common.bits(control_values(spec, grid[:-1]), expected)
        assert model.check_values(flat, spec)["max_material_error_over_budget"] == 0
        total += trace_bytes(spec, len(grid) - 1)
    assert total < PROTOCOL["resources"]["max_retained_array_estimate_bytes"]
    batch = replay_batch()
    full, windows = plan_batch(batch), plan_batch_windows(batch, WindowPolicy(23))
    assert (
        max(full.estimated_working_bytes, windows.estimated_working_bytes) < batch.max_working_bytes
    )
    exported = load_spec(runtime.ROOT / "configs/betse_spatial_junction.json")
    assert exported.to_dict() == parse_spec(runtime.definition(backend="gpu")).to_dict()
    common.evidence(
        "junction-runtime-resources",
        dict(
            status="passed",
            histories=len(CASES),
            retained_array_estimate_bytes=total,
            full_batch_bytes=full.estimated_working_bytes,
            window_batch_bytes=windows.estimated_working_bytes,
            batch_budget_bytes=batch.max_working_bytes,
        ),
    )


def test_host_schedule_boundaries_and_static_controls():
    raw = runtime.definition("block_release", 1)
    spec = parse_spec(raw)
    times = timeline(spec)
    controls = control_values(spec, times)
    np.testing.assert_array_equal(controls.junction[:, 0], [1] * 32 + [0] * 48 + [1] * 49)
    assert [event_index(spec, times[i]) for i in (31, 32, 79, 80)] == [0, 1, 1, 2]
    raw["experiment"].pop("changes")
    static = parse_spec(raw)
    assert all(np.all(v == 1) for v in control_values(static, times))
    assert all(v.shape == (0, 30) for v in control_values(static, np.array([])))
    assert parse_spec(static.to_dict()) == static
    with pytest.raises(ConfigError, match="controls"):
        model.check_steps(spec, np.array([spec.execution.dt]), np.zeros(1))
    bad = jax.tree.map(np.copy, control_values(spec, times[:1]))
    _, p = definition_arrays(spec.model)
    patch = np.flatnonzero(p.active.tissue.partner != np.arange(30))[0]
    bad.junction[0, patch] = 0.5
    with pytest.raises(ConfigError, match="reciprocal"):
        model.check_steps(spec, np.array([spec.execution.dt]), bad)


@pytest.mark.parametrize(
    "fault",
    (
        "missing_open",
        "gate_above_one",
        "gate_nan",
        "asymmetric_open",
        "threshold_shape",
        "threshold_negative",
        "minimum_above_one",
        "block_above_one",
        "nonbinary_mask",
        "missing_ion",
        "duplicate_ion",
        "fractional_ion",
        "immobile_ion",
        "long_horizon",
        "missing_control",
        "asymmetric_control",
        "short_control",
        "boolean_control",
        "negative_control",
        "nonfinite_control",
        "off_grid",
        "extra_field",
    ),
)
def test_host_bad_definition(fault):
    raw = runtime.definition()
    m, e = raw["model"], raw["experiment"]
    patch = next(i for i, j in enumerate(m["tissue"]["partner"]) if i != j)
    if fault == "missing_open":
        del m["initial"]["junction_open"]
    elif fault in ("gate_above_one", "gate_nan", "asymmetric_open"):
        m["initial"]["junction_open"][patch] = {
            "gate_above_one": 1.1,
            "gate_nan": float("nan"),
            "asymmetric_open": 0.8,
        }[fault]
    elif fault == "threshold_shape":
        m["junction"]["threshold_voltage_V"].pop()
    elif fault == "threshold_negative":
        m["junction"]["threshold_voltage_V"][0] = -1
    elif fault == "minimum_above_one":
        m["junction"]["minimum_open_fraction"][0] = 2
    elif fault == "block_above_one":
        m["junction_block"][0] = 2
    elif fault == "nonbinary_mask":
        m["tissue"]["junction_open"] = [0.5] * 30
    elif fault == "missing_ion":
        m["moving_order"].pop()
    elif fault == "duplicate_ion":
        m["moving_order"][1] = m["moving_order"][0]
    elif fault == "fractional_ion":
        m["moving_order"][0] = 0.5
    elif fault == "immobile_ion":
        m["moving_order"][0] = 3
    elif fault == "long_horizon":
        e["end_time"] = 128e-6
    elif fault == "missing_control":
        del e["changes"][1]["junction"]
    elif fault == "asymmetric_control":
        e["changes"][1]["junction"][patch] = 0.5
    elif fault == "short_control":
        e["changes"][1]["junction"].pop()
    elif fault in ("boolean_control", "negative_control", "nonfinite_control"):
        e["changes"][1]["junction"][0] = {
            "boolean_control": True,
            "negative_control": -0.1,
            "nonfinite_control": float("nan"),
        }[fault]
    elif fault == "off_grid":
        e["changes"][1]["time"] += 0.4e-6
    else:
        m["junction"]["clock"] = "physical_time"
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize("fault", ("gate", "shape", "dtype", "asymmetric", "material", "clock"))
def test_host_corrupt_state(fault):
    spec = parse_spec(runtime.definition())
    state, _ = model.initial_values(spec)
    if fault == "gate":
        state = state._replace(junction_open=np.full(30, 1.1))
    elif fault == "shape":
        state = state._replace(junction_open=np.zeros(29))
    elif fault == "dtype":
        state = state._replace(junction_open=state.junction_open.astype(np.float32))
    elif fault == "asymmetric":
        _, p = definition_arrays(spec.model)
        state.junction_open[np.flatnonzero(p.active.tissue.partner != np.arange(30))[0]] = 0.5
    elif fault == "material":
        state.junction_outward_fmol[0, 0] += 1e-6
    else:
        state.elapsed_s[0] += 1e-6
    with pytest.raises((ConfigError, NumericalError)):
        model.check_values(state, spec)


@pytest.fixture(scope="module")
def trajectories(prior):
    assert prior["status"] == "passed"
    return {(c, i): run(parse_spec(runtime.definition(c, i, backend=BACKEND))) for c, i in CASES}


@pytest.mark.parametrize("case,index", CASES)
def test_runtime_qualified_histories(case, index, trajectories):
    result = trajectories[(case, index)]
    actual = {k: v[1:] for k, v in arrays(result).items()}
    path = (
        Path(PROTOCOL["prior_binding"]["root"])
        / f"evidence/{BACKEND}/junction-native-{case}-{index}.npz"
    )
    with np.load(path, allow_pickle=False) as saved:
        expected = {k: saved[k] for k in actual}
        count = compare(actual, expected, result.final.layout.tissue_membrane_area)
        exact = all(np.array_equal(actual[k], expected[k]) for k in actual)
    common.evidence(
        f"junction-runtime-qualified-{case}-{index}",
        dict(
            status="passed",
            compared_scalars=count,
            all_saved_arrays_bitwise=exact,
            target=str(path),
            state_arrays=14,
            diagnostics=result.diagnostics,
            native_evolving_values_used_as_inputs=False,
        ),
        arrays(result),
    )


def test_runtime_mixed_controls():
    raw = runtime.definition(backend=BACKEND, steps=6)
    raw["experiment"]["changes"] = [
        dict(time=i * 2e-6, **{k: [v] * 30 for k, v in zip(Control._fields, values, strict=True)})
        for i, values in enumerate(((1, 1, 1), (0, 0.5, 0), (0.5, 0, 1)))
    ]
    spec = parse_spec(raw)
    result = run(spec)
    assert all(v.device.platform == BACKEND for v in result.final.state)
    state, p = definition_arrays(spec.model)
    states = [model.flatten(state)]
    for i in range(6):
        values = ((1, 1, 1), (0, 0.5, 0), (0.5, 0, 1))[i // 2]
        state, _, valid = kernel.step(
            state, p, 1e-6, Control(*(np.full(30, v) for v in values)), xp=np
        )
        assert valid
        states.append(model.flatten(state))
    expected = model.STATE_TYPE(*(np.stack(v) for v in zip(*states, strict=True)))
    short.compare_cpu_gpu_arrays(
        previous.state_arrays(model.active_state(result.history)),
        previous.state_arrays(model.active_state(expected)),
        p.active.tissue.membrane_area,
    )
    np.testing.assert_allclose(
        result.history.junction_open,
        expected.junction_open,
        atol=PROTOCOL["tolerances"]["gate_atol"],
        rtol=PROTOCOL["tolerances"]["gate_rtol"],
    )
    raw["execution"]["jit"] = False
    compare(arrays(run(parse_spec(raw))), arrays(result), p.active.tissue.membrane_area)
    common.evidence(
        "junction-runtime-mixed-controls",
        dict(
            status="passed",
            steps=6,
            routes=list(Control._fields),
            eager=True,
            scope="Configured mapping versus unchanged component; no new mixed native claim",
        ),
    )


def test_runtime_disk_windows_and_clock(trajectories, tmp_path):
    full = trajectories[("block_release", 1)]
    cuts = [1, 31, 32, 33, 79, 80, 81, 128]
    for cut in cuts:
        checkpoint = full.checkpoint_at(float(full.times[cut]))
        path = tmp_path / f"cut-{cut}"
        write_snapshot(path, full.spec, checkpoint)
        saved = load_snapshot(path)
        suffix = run(saved.spec, saved.checkpoint)
        common.bits(suffix.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
        if cut == 32:
            assert_windows(
                list(iter_windows(saved.spec, WindowPolicy(37), saved.checkpoint)), suffix
            )
            with pytest.raises(ConfigError, match="event position"):
                validate_checkpoint(full.spec, replace(checkpoint, event_index=0))
    assert_windows(list(iter_windows(full.spec, WindowPolicy(13))), full)
    write_run(tmp_path / "run", full)
    write_windowed_run(tmp_path / "windows", full.spec, WindowPolicy(23, "full"))
    for folder in ("run", "windows"):
        common.bits(
            load_snapshot(tmp_path / folder / "checkpoint_final").checkpoint.state, full.final.state
        )
    sparse = full.spec.to_dict()
    sparse["experiment"]["observation_times"] = [0, sparse["experiment"]["end_time"]]
    sparse_spec = parse_spec(sparse)
    assert_windows(list(iter_windows(sparse_spec, WindowPolicy(13))), run(sparse_spec))
    common.evidence(
        "junction-runtime-disk-windows",
        dict(
            status="passed",
            state_arrays=14,
            comparison="bitwise",
            cuts=cuts,
            windows=[13, 37, 23],
            empty_observation_windows=True,
            stale_event_rejected=True,
        ),
    )


@pytest.mark.parametrize("fault", ("missing_open", "gate", "order"))
def test_runtime_corrupt_disk(trajectories, tmp_path, fault):
    full = trajectories[("block_release", 1)]
    path = tmp_path / fault
    write_snapshot(path, full.spec, full.checkpoint_at(float(full.times[32])))
    with np.load(path / "state.npz", allow_pickle=False) as saved:
        values = {k: saved[k].copy() for k in saved.files}
    if fault == "missing_open":
        del values["junction_open"]
    elif fault == "gate":
        values["junction_open"][:] = 1.1
    else:
        values["moving_order"] = values["moving_order"][::-1]
    np.savez(path / "state.npz", **values)
    manifest = json.loads((path / "manifest.json").read_text())
    manifest.pop("manifest_sha256")
    manifest["state_sha256"] = refinement.digest(path / "state.npz")
    manifest["manifest_sha256"] = digest(manifest)
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ConfigError, NumericalError)):
        load_snapshot(path)


def test_runtime_worlds(tmp_path):
    batch = replay_batch()
    full = run_batch(batch)
    reverse = run_batch(replace(batch, worlds=tuple(reversed(batch.worlds))))
    for world in batch.worlds:
        target = full.worlds[world.world_id].history
        common.bits(target, run(world.simulation).history)
        common.bits(target, reverse.worlds[world.world_id].history)
        common.bits(
            target, run_batch(replace(batch, worlds=(world,))).worlds[world.world_id].history
        )
    rounds = list(iter_batch_windows(batch, WindowPolicy(23)))
    for world in batch.worlds:
        assert_windows(
            [r.worlds[world.world_id] for r in rounds if world.world_id in r.worlds],
            full.worlds[world.world_id],
        )
    checkpoints = {i: r.checkpoint_at(float(r.times[17])) for i, r in full.worlds.items()}
    checkpoints[12] = full.worlds[12].final
    write_batch_snapshot(tmp_path / "worlds", batch, checkpoints)
    saved = load_batch_snapshot(tmp_path / "worlds")
    resumed = run_batch(saved.spec, saved.checkpoints)
    for identity, result in resumed.worlds.items():
        cut = checkpoints[identity].step_index
        common.bits(
            result.history, model.STATE_TYPE(*(v[cut:] for v in full.worlds[identity].history))
        )
    common.evidence(
        "junction-runtime-worlds",
        dict(
            status="passed",
            worlds=3,
            comparison="bitwise",
            independent_clocks=True,
            reordered=True,
            partitioned=True,
            disk=True,
            finished_world=True,
        ),
    )


def test_runtime_branch(trajectories):
    original = trajectories[("block_release", 1)]
    checkpoint = original.checkpoint_at(float(original.times[32]))
    raw = original.spec.to_dict()
    raw["experiment"]["changes"][1]["junction"] = [0.5] * 30
    changed = parse_spec(raw)
    branch = branch_checkpoint(original.spec, checkpoint, changed)
    suffix, full = run(changed, branch), run(changed)
    common.bits(original.history.junction_open[:33], full.history.junction_open[:33])
    common.bits(suffix.history, model.STATE_TYPE(*(v[32:] for v in full.history)))
    corrupt = copy.deepcopy(raw)
    corrupt["experiment"]["changes"][0]["junction"] = [0] * 30
    with pytest.raises(ConfigError, match="rewrite"):
        branch_checkpoint(original.spec, checkpoint, parse_spec(corrupt))
    corrupt = copy.deepcopy(raw)
    corrupt["model"]["moving_order"].reverse()
    with pytest.raises(ConfigError, match="may not change model"):
        branch_checkpoint(original.spec, checkpoint, parse_spec(corrupt))
    common.evidence(
        "junction-runtime-branch",
        dict(
            status="passed",
            comparison="bitwise",
            changed_future_junction_control=True,
            past_rewrite_rejected=True,
            changed_moving_order_rejected=True,
        ),
    )


def test_runtime_domain():
    raw = runtime.definition(backend=BACKEND, steps=4)
    raw["model"]["pump"]["capacity_fmol_s"] = [1e12] * 30
    spec = parse_spec(raw)
    with pytest.raises(NumericalError, match="domain failure"):
        run(spec)
    state, layout = model.initial_values(spec)
    args = jax.device_put(
        (
            state,
            np.full(4, 1e-6),
            Control(*(np.ones((4, 30)) for _ in range(3))),
            model.parameters(spec, layout),
            layout.active,
        ),
        jax.devices(BACKEND)[0],
    )
    final, history, valid = _compiled_discrete_rollout(*args, model.checked_step)
    assert not np.asarray(valid).any()
    common.bits(final, state)
    common.bits(history, model.STATE_TYPE(*(np.stack([v] * 4) for v in state)))
    common.evidence(
        "junction-runtime-domain",
        dict(
            status="passed",
            failure_latched=True,
            complete_state_retained=True,
            state_arrays=14,
        ),
    )


def test_runtime_legacy_schedules():
    root = Path(junctions.protocol()["prior_binding"]["root"])
    count = 0
    for case in ("coupled_block", "regional", "staggered"):
        result = run(parse_spec(legacy.definition(case, 1, backend=BACKEND)))
        actual = {k: v[1:] for k, v in reference_arrays(result).items()}
        with np.load(
            root / f"evidence/{BACKEND}/long-intervention-native-{case}-1.npz", allow_pickle=False
        ) as saved:
            count += short.compare_cpu_gpu_arrays(
                actual, {k: saved[k] for k in actual}, result.final.layout.tissue_membrane_area
            )
    common.evidence(
        "junction-runtime-legacy-schedules",
        dict(
            status="passed",
            compared_scalars=count,
            cases=["coupled_block", "regional", "staggered"],
            duration_s=256e-6,
            target=str(root),
            scope="Unchanged existing model, not longer dynamic junctions",
        ),
    )


def test_runtime_cli(tmp_path):
    raw = runtime.definition(backend=BACKEND, steps=4)
    path, output = tmp_path / "definition.json", tmp_path / "cli-run"
    path.write_text(json.dumps(raw))
    for args in (["validate", str(path)], ["run", str(path), "--output", str(output)]):
        response = subprocess.run(
            [sys.executable, "-B", "-m", "cells", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert not response.stderr, response.stderr
        json.loads(response.stdout)
    saved = load_snapshot(output / "checkpoint_final")
    assert saved.checkpoint.step_index == 4 and len(saved.checkpoint.state) == 14
    common.evidence(
        "junction-runtime-cli", dict(status="passed", validate=True, run=True, state_arrays=14)
    )


def test_runtime_cpu_gpu(trajectories):
    if BACKEND == "cpu":
        pytest.skip("Requires the following L4 phase and saved configured CPU histories")
    assert EVIDENCE
    count = 0
    for (case, index), result in trajectories.items():
        path = Path(EVIDENCE) / f"cpu/junction-runtime-qualified-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += compare(arrays(result), saved, result.final.layout.tissue_membrane_area)
    common.evidence("junction-runtime-cpu-gpu", dict(status="passed", compared_scalars=count))
