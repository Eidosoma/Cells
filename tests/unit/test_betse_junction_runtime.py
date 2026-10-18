"""Configured dynamic junctions against authenticated component trajectories."""

import copy
import json
import os
import subprocess
import sys
import zipfile
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
from validation.betse.spatial_active import junction_reference as independent
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
        for c, i, n in (("coupled", 0, 512), ("block_release", 1, 640), ("reversed", 0, 384))
    ]
    return BatchSpec(
        tuple(WorldSpec(i + 10, s) for i, s in enumerate(specs)),
        4,
        4096,
        PROTOCOL["resources"]["batch_max_working_bytes"],
    )


def long_definition(case, index):
    count = round(PROTOCOL["duration_s"] / PROTOCOL["native_steps_s"][index])
    return runtime.definition(case, index, backend=BACKEND, steps=count)


def test_host_definitions_and_resources():
    retained, transient, native_bytes = 0, 0, 0
    old = json.loads(
        (Path(PROTOCOL["prior_binding"]["root"]) / "component-protocol.json").read_text()
    )
    for case, index in CASES:
        raw = long_definition(case, index)
        spec = parse_spec(raw)
        assert parse_spec(spec.to_dict()) == spec
        assert get_model(spec.model) is model
        state, p = definition_arrays(spec.model)
        flat, layout = model.initial_values(spec)
        common.bits(model.unflatten(flat), state)
        common.bits(model.parameters(spec, layout), p)
        assert len(flat) == 14
        assert spec.experiment.end_time == PROTOCOL["duration_s"] == 512e-6
        grid = timeline(spec)
        expected = junctions.controls(
            next(c for c in old["cases"] if c["id"] == case),
            spec.execution.dt,
            len(grid) - 1,
            spec.execution.membrane_capacity,
        )
        common.bits(control_values(spec, grid[:-1]), expected)
        assert model.check_values(flat, spec)["max_material_error_over_budget"] == 0
        # Histories are retained, but compiler/field working arrays are reused
        # between the sequential scalar runs. Count both separately.
        initial_history = model.STATE_TYPE(*(np.asarray(v)[None] for v in flat))
        observed = model.observe_history(
            np.array([0.0]), initial_history, layout, np.array([0.0]), spec
        )
        per_sample = sum(v.nbytes for v in flat) + sum(v.nbytes for v in vars(observed).values())
        retained += 2 * (per_sample * len(grid) + sum(v.nbytes for v in layout))
        transient = max(transient, trace_bytes(spec, len(grid) - 1))
        assert trace_bytes(spec, len(grid) - 1) <= spec.execution.max_trace_bytes
        with zipfile.ZipFile(runtime.capture_folder(case, index) / "trace.npz") as archived:
            # Two times the old duration, with two copies for target reconstruction.
            native_bytes = max(native_bytes, 4 * sum(v.file_size for v in archived.infolist()))
    total = retained + transient + native_bytes
    assert total < PROTOCOL["resources"]["max_retained_array_estimate_bytes"]
    batch = replay_batch()
    full, windows = plan_batch(batch), plan_batch_windows(batch, WindowPolicy(137))
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
            retained_histories_with_host_device_copies_bytes=retained,
            largest_scalar_working_bytes=transient,
            largest_native_target_working_bytes=native_bytes,
            estimate_scope="Retained histories plus scalar working and one native target",
            full_batch_bytes=full.estimated_working_bytes,
            window_batch_bytes=windows.estimated_working_bytes,
            batch_budget_bytes=batch.max_working_bytes,
        ),
    )


def test_host_native_protocol_and_static_horizon():
    old = json.loads(
        (Path(PROTOCOL["prior_binding"]["root"]) / "component-protocol.json").read_text()
    )
    native = runtime.native_protocol()
    metadata = {"kind", "duration_s", "resources", "scope", "automatic_followup"}
    for name in set(native) - metadata:
        assert native[name] == old[name], name
    assert native["duration_s"] == 2 * old["duration_s"] == 512e-6
    assert native["tolerances"] == PROTOCOL["tolerances"]
    assert PROTOCOL["default_duration_s"] == 64e-6
    static = previous.runtime.definition(backend=BACKEND)
    static["experiment"]["end_time"] = 257e-6
    with pytest.raises(ConfigError, match="horizon up to 256 us"):
        parse_spec(static)
    with pytest.raises(ValueError, match="registered horizon"):
        runtime.definition(steps=513)


@pytest.mark.parametrize("fault", [None, "trace", "missing_pair", "observer", "protocol", "mode"])
def test_host_native_capture_authentication(tmp_path, fault):
    """Reuse one real archived pair; reject changed evidence and observer effects."""
    root = Path(PROTOCOL["prior_binding"]["root"])
    rule = json.loads((root / "component-protocol.json").read_text())
    rule["cases"], rule["native_steps_s"] = rule["cases"][:1], rule["native_steps_s"][:1]
    rows = []
    for mode in ("observed", "bare"):
        key = f"{rule['cases'][0]['id']}/step-0/{mode}"
        old = root / "evidence/cpu/long-junction-native" / key
        folder = tmp_path / key
        folder.mkdir(parents=True)
        row = json.loads((old / "result.json").read_text())
        (folder / "preparation.json").write_bytes((old / "preparation.json").read_bytes())
        if mode == "observed":
            if fault == "trace":
                (folder / "trace.npz").write_bytes(b"corrupt")
            else:
                # Read-only link: the frozen archive is never modified by a fault.
                (folder / "trace.npz").symlink_to(old / "trace.npz")
        if fault == "observer" and mode == "bare":
            row["final"] = {}
        if fault == "mode" and mode == "observed":
            row["mode"] = "bare"
        (folder / "result.json").write_text(json.dumps(row))
        rows.append(dict(path=key, sha256=refinement.digest(folder / "result.json")))
    panel = dict(protocol=rule, rows=rows[:-1] if fault == "missing_pair" else rows)
    if fault == "protocol":
        panel["protocol"] = rule | {"duration_s": 512e-6}
    (tmp_path / "panel.json").write_text(json.dumps(panel))
    (tmp_path / "completion.json").write_text(
        json.dumps(
            dict(
                status="native_spatial_contact_recorded",
                panel_sha256=refinement.digest(tmp_path / "panel.json"),
            )
        )
    )
    if fault is None:
        assert len(runtime.authenticate_capture(tmp_path, rule)) == 2
    else:
        with pytest.raises(AssertionError):
            runtime.authenticate_capture(tmp_path, rule)


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
        e["end_time"] = 513e-6
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
    return {(c, i): run(parse_spec(long_definition(c, i))) for c, i in CASES}


@pytest.fixture(scope="module")
def captured(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    rule = runtime.native_protocol()
    if BACKEND == "gpu":
        assert EVIDENCE
        root = Path(EVIDENCE) / "cpu"
    else:
        root = Path(EVIDENCE) / "cpu" if EVIDENCE else tmp_path_factory.mktemp("junction-native")
        root.mkdir(parents=True, exist_ok=True)
        settings = root / "junction-runtime-native-protocol.json"
        settings.write_text(json.dumps(rule, indent=2) + "\n")
        with (
            (root / "junction-runtime-native.stdout.log").open("x") as out,
            (root / "junction-runtime-native.stderr.log").open("x") as err,
        ):
            subprocess.run(
                [
                    "/mnt/workspaces/Cells/venv-betse/bin/python",
                    "-B",
                    str(runtime.PROTOCOL_PATH.with_name("junction_native.py")),
                    "--output",
                    str(root / "junction-runtime-native"),
                    "--protocol",
                    str(settings),
                ],
                check=True,
                timeout=PROTOCOL["resources"]["native_timeout_seconds"],
                stdout=out,
                stderr=err,
                env=dict(
                    os.environ,
                    MPLBACKEND="Agg",
                    MPLCONFIGDIR=str(root / "matplotlib-junction-runtime"),
                ),
            )
    path = root / "junction-runtime-native"
    rows = runtime.authenticate_capture(path, rule)
    common.evidence(
        "junction-runtime-native-capture",
        dict(
            status="passed",
            root=str(path),
            pairs=len(CASES),
            rows=len(rows),
            completion_sha256=refinement.digest(path / "completion.json"),
            observer_neutrality="bitwise",
            trace_loading="one case at a time",
            duration_s=rule["duration_s"],
        ),
    )
    return path, rows


@pytest.mark.parametrize("case,index", CASES)
def test_runtime_qualified_histories(case, index, trajectories, captured):
    result = trajectories[(case, index)]
    actual = {k: v[1:] for k, v in arrays(result).items()}
    path = (
        Path(PROTOCOL["prior_binding"]["root"])
        / f"evidence/{BACKEND}/long-junction-native-{case}-{index}.npz"
    )
    with np.load(path, allow_pickle=False) as saved:
        expected = {k: saved[k] for k in actual}
        prefix = {k: v[: len(expected[k])] for k, v in actual.items()}
        count = compare(prefix, expected, result.final.layout.tissue_membrane_area)
        exact = all(np.array_equal(prefix[k], expected[k]) for k in actual)
    native_root, rows = captured
    key = f"{case}/step-{index}/observed"
    row = rows[key]
    with np.load(native_root / key / "trace.npz", allow_pickle=False) as saved:
        trace = dict(saved)
    native = runtime.compare_native(actual, row, trace)
    native_prefix_scalars = 0
    old_folder = runtime.capture_folder(case, index)
    old_row = json.loads((old_folder / "result.json").read_text())
    with np.load(old_folder / "trace.npz", allow_pickle=False) as saved:
        assert set(trace) == set(saved)
        for name in saved:
            if name == "raw_label_s":
                continue  # Native linspace labels depend on duration; completed-step clocks do not.
            expected = saved[name]
            common.bits(
                trace[name] if name.startswith("initial_") else trace[name][: len(expected)],
                expected,
            )
            native_prefix_scalars += expected.size
    before = old_row["fixture"]["junction_inputs"]["steps"]
    assert row["fixture"]["junction_inputs"]["steps"][: len(before)] == before
    if BACKEND == "cpu":
        updates = independent.native_check(row, trace, runtime.native_protocol())
    else:
        report = json.loads(
            (native_root.parent / f"junction-runtime-qualified-{case}-{index}.json").read_text()
        )
        assert report["status"] == "passed" and report["native_trace_sha256"] == row["trace_sha256"]
        updates = report["native_updates"]
    common.evidence(
        f"junction-runtime-qualified-{case}-{index}",
        dict(
            status="passed",
            compared_scalars=count,
            all_saved_arrays_bitwise=exact,
            target=str(path),
            state_arrays=14,
            duration_s=result.spec.experiment.end_time,
            component_prefix_duration_s=old_row["steps"] * old_row["dt_s"],
            native_comparison=native,
            native_trace_sha256=row["trace_sha256"],
            native_updates=updates,
            native_update_check="fresh CPU oracle" if BACKEND == "cpu" else "same saved CPU target",
            native_prefix_scalars=native_prefix_scalars,
            native_prefix_comparison="bitwise except duration-dependent raw sample labels",
            diagnostics=result.diagnostics,
            native_evolving_values_used_as_inputs=False,
        ),
        arrays(result),
    )


def test_runtime_256_prefixes(trajectories):
    root = Path(PROTOCOL["runtime_prefix_binding"]["root"])
    count, differences = 0, {}
    for (case, index), result in trajectories.items():
        end = round(256e-6 / result.spec.execution.dt) + 1
        actual = {k: v[:end] for k, v in arrays(result).items()}
        with np.load(
            root / f"evidence/{BACKEND}/junction-runtime-qualified-{case}-{index}.npz",
            allow_pickle=False,
        ) as saved:
            count += compare(actual, saved, result.final.layout.tissue_membrane_area)
            differences[f"{case}-{index}"] = {
                k: float(np.max(abs(actual[k] - saved[k])))
                for k in actual
                if not np.array_equal(actual[k], saved[k])
            }
    common.evidence(
        "junction-runtime-256-prefixes",
        dict(
            status="passed",
            histories=len(CASES),
            duration_s=256e-6,
            compared_scalars=count,
            nonbitwise_fields=differences,
            all_arrays_bitwise=not any(differences.values()),
            comparison="Unchanged physical tolerances; exact differences recorded separately",
        ),
    )


def test_runtime_original_prefixes(trajectories):
    root = Path(PROTOCOL["prefix_binding"]["root"])
    count, differences = 0, {}
    for case, index in ((c, i) for c in PROTOCOL["cases"] for i in (0, 1)):
        result = trajectories[(case, index)]
        end = round(PROTOCOL["default_duration_s"] / result.spec.execution.dt) + 1
        actual = {k: v[:end] for k, v in arrays(result).items()}
        path = root / f"evidence/{BACKEND}/junction-runtime-qualified-{case}-{index}.npz"
        with np.load(path, allow_pickle=False) as saved:
            count += compare(actual, saved, result.final.layout.tissue_membrane_area)
            differences[f"{case}-{index}"] = {
                k: float(np.max(abs(actual[k] - saved[k])))
                for k in actual
                if not np.array_equal(actual[k], saved[k])
            }
    common.evidence(
        "junction-runtime-original-prefixes",
        dict(
            status="passed",
            histories=12,
            duration_s=64e-6,
            compared_scalars=count,
            comparison="Unchanged physical tolerances; exact differences recorded separately",
            nonbitwise_fields=differences,
            all_arrays_bitwise=not any(differences.values()),
        ),
    )


def test_runtime_native_targets_reject_corruption(trajectories, captured):
    result = trajectories[("block_release", 1)]
    actual = {k: np.asarray(v[1:]) for k, v in arrays(result).items()}
    native_root, rows = captured
    key = "block_release/step-1/observed"
    folder, row = native_root / key, rows[key]
    faults = {
        "state__cell_concentration": 1e-5,
        "state__membrane_inward_fmol": 1e-5,
        "state__elapsed_s": 1e-6,
        "junction__open": 1e-3,
        "observed__vm": 1e-5,
    }
    with np.load(folder / "trace.npz", allow_pickle=False) as trace:
        for name, change in faults.items():
            corrupted = dict(actual)
            corrupted[name] = actual[name].copy()
            corrupted[name].flat[-1] += change
            with pytest.raises(AssertionError):
                runtime.compare_native(corrupted, row, trace)
    common.evidence(
        "junction-runtime-native-negative-controls",
        dict(
            status="passed",
            rejected=list(faults),
            tolerances_unchanged=True,
        ),
    )


@pytest.mark.parametrize("duration", [64e-6, 256e-6])
def test_runtime_horizon_branch(trajectories, tmp_path, duration):
    full = trajectories[("block_release", 1)]
    raw = runtime.definition(
        "block_release", 1, backend=BACKEND, steps=round(duration / full.spec.execution.dt)
    )
    # Reserve the full continuation's storage before creating the checkpoint:
    # branches intentionally cannot change execution settings, including budgets.
    raw["execution"]["max_trace_bytes"] = full.spec.execution.max_trace_bytes
    short_spec = parse_spec(raw)
    original = run(short_spec)
    cut = len(original.times) - 1
    common.bits(original.history, model.STATE_TYPE(*(v[: cut + 1] for v in full.history)))
    write_snapshot(tmp_path / "short-final", original.spec, original.final)
    saved = load_snapshot(tmp_path / "short-final")
    checkpoint = branch_checkpoint(saved.spec, saved.checkpoint, full.spec)
    resumed = run(full.spec, checkpoint)
    common.bits(resumed.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
    common.evidence(
        f"junction-runtime-horizon-branch-{round(duration * 1e6)}",
        dict(
            status="passed",
            from_duration_s=duration,
            to_duration_s=PROTOCOL["duration_s"],
            state_arrays=14,
            comparison="bitwise",
            disk=True,
            reserved_trace_bytes=full.spec.execution.max_trace_bytes,
        ),
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
    cuts = [1, 31, 32, 33, 79, 80, 81, 128, 256, 511, 512, 513, 767, 1023, 1024]
    for cut in cuts:
        checkpoint = full.checkpoint_at(float(full.times[cut]))
        path = tmp_path / f"cut-{cut}"
        write_snapshot(path, full.spec, checkpoint)
        saved = load_snapshot(path)
        suffix = run(saved.spec, saved.checkpoint)
        common.bits(suffix.history, model.STATE_TYPE(*(v[cut:] for v in full.history)))
        if cut == 32:
            assert_windows(
                list(iter_windows(saved.spec, WindowPolicy(173), saved.checkpoint)), suffix
            )
            with pytest.raises(ConfigError, match="event position"):
                validate_checkpoint(full.spec, replace(checkpoint, event_index=0))
    assert_windows(list(iter_windows(full.spec, WindowPolicy(137))), full)
    write_run(tmp_path / "run", full)
    write_windowed_run(tmp_path / "windows", full.spec, WindowPolicy(127, "full"))
    for folder in ("run", "windows"):
        common.bits(
            load_snapshot(tmp_path / folder / "checkpoint_final").checkpoint.state, full.final.state
        )
    sparse = full.spec.to_dict()
    sparse["experiment"]["observation_times"] = [0, sparse["experiment"]["end_time"]]
    sparse_spec = parse_spec(sparse)
    assert_windows(list(iter_windows(sparse_spec, WindowPolicy(137))), run(sparse_spec))
    common.evidence(
        "junction-runtime-disk-windows",
        dict(
            status="passed",
            state_arrays=14,
            comparison="bitwise",
            cuts=cuts,
            windows=[137, 173, 127],
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
    rounds = list(iter_batch_windows(batch, WindowPolicy(137)))
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
            durations_s=[world.simulation.experiment.end_time for world in batch.worlds],
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
