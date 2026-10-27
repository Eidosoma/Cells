"""Bounded 50-us injury qualification; numerical controls, not measured recovery."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.runner import run, timeline
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_repair as model
from tests.unit.test_surface_calcium import BACKEND, EVIDENCE, evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_repair_fixtures as fixtures
from validation.tissue import surface_repair_reference as reference

PREFIX = "resolved-repair-full"
STEPS = (0.625e-6, 0.3125e-6, 0.15625e-6)
REFERENCE = dict(rtol=1e-12, atol=1e-16, charge_atol=5e-32)


def normalized(raw):
    value = deepcopy(raw)
    value["execution"]["backend"] = "cpu"
    return value


def arrays(value):
    return {
        "accepted_times": value.times,
        **value.history._asdict(),
        **{"observed_" + k: v for k, v in vars(value.observations).items()},
    }


def capture(arm, value, *, status="captured", **details):
    evidence(
        PREFIX + "-" + arm,
        dict(status=status, inputs=value.spec.to_dict(), diagnostics=value.diagnostics, **details),
        arrays(value),
    )


def independent(raw, arm):
    name = PREFIX + "-reference-" + arm
    if BACKEND == "gpu" and EVIDENCE:
        directory = Path(EVIDENCE) / "cpu"
        receipt = json.loads((directory / (name + ".json")).read_text())
        assert receipt["status"] == "passed"
        assert receipt["inputs"] == normalized(raw) and receipt["settings"] == REFERENCE
        with np.load(directory / (name + ".npz"), allow_pickle=False) as saved:
            values = saved["state"].copy()
        assert values.shape[0] == len(raw["experiment"]["observation_times"])
        evidence(name, receipt | dict(reused_cpu_reference=True), dict(state=values))
        return values
    result = reference.integrate(raw, **REFERENCE)
    evidence(
        name,
        dict(
            status="passed",
            inputs=normalized(raw),
            settings=REFERENCE,
            method=result["method"],
            evaluations=result["evaluations"],
        ),
        dict(state=result["state"]),
    )
    return result["state"]


def compare_backend(actual, saved):
    assert set(actual) == set(saved)
    count = 0
    for name, value in actual.items():
        value = np.asarray(value)
        assert value.shape == saved[name].shape and value.dtype == saved[name].dtype
        if value.dtype.kind in "bui" or name in (
            "accepted_times",
            "observed_times",
            "observed_injury_control",
            "observed_resealing_control",
        ):
            np.testing.assert_array_equal(value, saved[name], err_msg=name)
        else:
            atol = (
                3e-25
                if name.endswith("_C")
                else (3e-23 if name.endswith("_A") else (3e-11 if name.endswith("_V") else 3e-13))
            )
            np.testing.assert_allclose(value, saved[name], rtol=3e-10, atol=atol, err_msg=name)
        count += value.size
    return count


def test_declared_grids_and_existing_gpu_examples():
    grids = []
    for arm in fixtures.ARMS:
        raw = fixtures.definition(arm, backend=BACKEND)
        for dt in STEPS:
            raw["execution"]["dt"] = dt
            spec = parse_spec(raw)
            times = timeline(spec)
            assert 5.3e-6 in times and 15.3e-6 in times
            assert len(model.STATE_TYPE._fields) == 39
            grids.append(dict(arm=arm, dt_s=dt, steps=len(times) - 1))
    root = Path(__file__).resolve().parents[2]
    assert json.loads(
        (root / "configs/resolved_repair_tissue.json").read_text()
    ) == fixtures.definition(backend="gpu")
    assert json.loads(
        (root / "configs/assembly_resolved_repair_tissue.json").read_text()
    ) == fixtures.assembly_definition(backend="gpu")
    evidence(PREFIX + "-grids", dict(status="passed", grids=grids, state_fields=39))


@pytest.fixture(scope="module")
def histories(tmp_path_factory):
    root = tmp_path_factory.mktemp("injury-histories")
    values = {}
    for arm in fixtures.ARMS:
        value = run(parse_spec(fixtures.definition(arm, backend=BACKEND)))
        write_run(root / arm, value)
        capture(arm, value)
        assert all(v.device.platform == BACKEND for v in value.final.state)
        values[arm] = value
    return values


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_complete_trajectories_independent_reference_and_damage(histories, arm):
    value = histories[arm]
    raw = value.spec.to_dict()
    expected = independent(raw, arm)
    c = reference.bind(raw)
    actual = reference.flatten(c, vars(value.observations))
    evidence(
        PREFIX + "-errors-" + arm,
        dict(inputs=raw),
        dict(actual=actual, reference=expected, signed_error=actual - expected),
    )
    ratio = assert_states(c, actual, expected)
    hazard = 20000.0 if arm in ("held", "resealing") else 0.0
    closure = 0.0 if arm == "held" else 4000.0
    targets = []
    for time in value.observations.times:
        duration = min(max(float(time) - 5.3e-6, 0.0), 10e-6)
        damaged = reference.analytic_damage(0.0, hazard, closure, duration)
        targets.append(
            reference.analytic_damage(damaged, 0.0, closure, max(float(time) - 15.3e-6, 0.0))
        )
    np.testing.assert_allclose(value.observations.damage[:, 0], targets, rtol=0, atol=2e-9)
    assert not np.any(value.history.damage[:, 1:])
    if arm in ("uninjured", "sham"):
        assert all(not np.any(getattr(value.history, name)) for name in model.EXTRA_AXES)
    elif arm == "held":
        assert not np.any(value.history.damage_closed)
    else:
        assert value.final.state.damage_closed[0] > 0
    model.check_values(value.history, value.spec)
    capture(arm, value, status="passed", max_error_over_budget=ratio, analytic_damage=targets)


@pytest.mark.parametrize("arm", ("held", "resealing"))
def test_reference_accuracy(arm):
    raw = parse_spec(fixtures.definition(arm, backend=BACKEND)).to_dict()
    if BACKEND == "gpu":
        assert EVIDENCE
        saved = json.loads(
            (Path(EVIDENCE) / "cpu" / (PREFIX + "-reference-accuracy-" + arm + ".json")).read_text()
        )
        assert saved["status"] == "passed" and saved["inputs"] == normalized(raw)
        assert saved["settings"] == REFERENCE
        assert saved["tighter_settings"] == {k: v / 4 for k, v in REFERENCE.items()}
        evidence(PREFIX + "-reference-accuracy-" + arm, saved | dict(reused_cpu_reference=True))
        return
    c = reference.bind(raw)
    ordinary = independent(raw, arm)
    tighter = reference.integrate(raw, **{k: v / 4 for k, v in REFERENCE.items()})["state"]
    evidence(
        PREFIX + "-reference-accuracy-arrays-" + arm,
        dict(inputs=raw),
        dict(reference=ordinary, tighter=tighter, signed_error=ordinary - tighter),
    )
    diff = reference.unpack(c, ordinary - tighter)
    for name, value in diff.items():
        assert np.max(np.abs(value), initial=0) <= (3e-28 if name.endswith("_C") else 3e-14), name
    evidence(
        PREFIX + "-reference-accuracy-" + arm,
        dict(
            status="passed",
            inputs=normalized(raw),
            settings=REFERENCE,
            tighter_settings={k: v / 4 for k, v in REFERENCE.items()},
            noncharge_floor=3e-14,
            charge_floor_C=3e-28,
        ),
    )


@pytest.mark.parametrize("arm", ("held", "resealing"))
def test_coupled_timestep_refinement(arm):
    raw = parse_spec(fixtures.definition(arm, backend=BACKEND)).to_dict()
    expected, c = independent(raw, arm), reference.bind(raw)
    errors, charge_errors, ratios = [], [], []
    for i, dt in enumerate(STEPS):
        raw["execution"]["dt"] = dt
        value = run(parse_spec(raw))
        actual = reference.flatten(c, vars(value.observations))
        capture(f"refinement-{arm}-{i}", value)
        evidence(
            PREFIX + f"-refinement-errors-{arm}-{i}",
            dict(inputs=raw),
            dict(actual=actual, reference=expected, signed_error=actual - expected),
        )
        ratios.append(assert_states(c, actual, expected))
        diff = reference.unpack(c, actual - expected)
        errors.append(
            max(
                float(np.max(np.abs(v), initial=0)) for k, v in diff.items() if not k.endswith("_C")
            )
        )
        charge_errors.append(
            max(float(np.max(np.abs(v), initial=0)) for k, v in diff.items() if k.endswith("_C"))
        )
    assert errors[-1] <= max(errors[0] * 0.2, 3e-13)
    assert charge_errors[-1] <= max(charge_errors[0] * 0.2, 3e-27)
    evidence(
        PREFIX + "-refinement-" + arm,
        dict(
            status="passed",
            steps_s=STEPS,
            max_error_over_budget=ratios,
            noncharge_max_errors=errors,
            charge_max_errors_C=charge_errors,
            noncharge_floor=3e-13,
            charge_floor_C=3e-27,
            final_to_initial_limit=0.2,
        ),
    )


def test_complete_identical_repeat_fresh_process_and_windows(histories, tmp_path):
    value = histories["resealing"]
    repeated = run(value.spec)
    capture("identical-repeat", repeated)
    exact(repeated.history, value.history)
    exact(histories["uninjured"].history, histories["sham"].history)
    checkpoint = value.checkpoint_at(15.3e-6)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    saved = load_snapshot(tmp_path / "checkpoint")
    exact(saved.checkpoint.state, checkpoint.state)
    resumed = run(saved.spec, saved.checkpoint)
    capture("resumed", resumed)
    exact(resumed.history, tuple(v[checkpoint.step_index :] for v in value.history))
    parts = list(iter_windows(saved.spec, WindowPolicy(7, "full"), saved.checkpoint))
    merged = tuple(
        np.concatenate([getattr(p.history, k)[0 if i == 0 else 1 :] for i, p in enumerate(parts)])
        for k in model.STATE_TYPE._fields
    )
    evidence(
        PREFIX + "-windows",
        dict(inputs=value.spec.to_dict()),
        dict(zip(model.STATE_TYPE._fields, merged, strict=True)),
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
            str(tmp_path / "fresh"),
        ],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    (tmp_path / "fresh.stdout.log").write_text(process.stdout)
    (tmp_path / "fresh.stderr.log").write_text(process.stderr)
    process.check_returncode()
    assert not process.stderr
    exact(load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint.state, resumed.final.state)
    with np.load(tmp_path / "fresh/trajectory.npz", allow_pickle=False) as archive:
        exact(tuple(archive[k] for k in model.STATE_TYPE._fields), resumed.history)
    terminal = run(value.spec, value.final)
    exact(tuple(v[0] for v in terminal.history), value.final.state)
    evidence(
        PREFIX + "-restart",
        dict(
            status="passed",
            comparison="bitwise complete histories",
            identical_repeat=True,
            sham_reduction=True,
            fresh_process=True,
            changed_windows=True,
            terminal=True,
            event_boundary_s=15.3e-6,
        ),
    )


def test_independent_worlds_reordering_and_saved_windows(histories, tmp_path):
    expected = {7: histories["resealing"], 29: histories["held"]}
    batch = BatchSpec(tuple(WorldSpec(i, v.spec) for i, v in expected.items()), 2, 256, 2**30)
    actual = run_batch(batch)
    for identity, value in actual.worlds.items():
        capture(f"world-{identity}", value)
        exact(value.history, expected[identity].history)
    reversed_worlds = run_batch(BatchSpec(tuple(reversed(batch.worlds)), 2, 256, 2**30))
    for identity, value in reversed_worlds.worlds.items():
        capture(f"reordered-world-{identity}", value)
        exact(value.history, actual.worlds[identity].history)
    checkpoints = actual.checkpoint_at({7: 15.3e-6, 29: 50e-6})
    write_batch_snapshot(tmp_path / "batch", batch, checkpoints)
    loaded = load_batch_snapshot(tmp_path / "batch")
    parts = list(iter_batch_windows(loaded.spec, WindowPolicy(7, "full"), loaded.checkpoints))
    for identity in expected:
        rows = [p.worlds[identity] for p in parts if identity in p.worlds]
        merged = tuple(
            np.concatenate(
                [getattr(p.history, k)[0 if i == 0 else 1 :] for i, p in enumerate(rows)]
            )
            for k in model.STATE_TYPE._fields
        )
        evidence(
            PREFIX + f"-world-restarted-{identity}",
            dict(world_id=identity),
            dict(zip(model.STATE_TYPE._fields, merged, strict=True)),
        )
        exact(
            merged,
            tuple(v[checkpoints[identity].step_index :] for v in actual.worlds[identity].history),
        )
    evidence(
        PREFIX + "-worlds",
        dict(
            status="passed",
            comparison="bitwise complete histories",
            world_ids=list(expected),
            reordered=True,
            independent_restart_times=[15.3e-6, 50e-6],
        ),
    )


def test_cpu_gpu_complete_histories_and_observations(histories):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and complete saved CPU histories")
    assert EVIDENCE
    count = 0
    for arm, value in histories.items():
        path = Path(EVIDENCE) / "cpu" / (PREFIX + "-" + arm)
        receipt = json.loads(path.with_suffix(".json").read_text())
        assert receipt["status"] == "passed" and receipt["inputs"] == normalized(
            value.spec.to_dict()
        )
        with np.load(path.with_suffix(".npz"), allow_pickle=False) as saved:
            count += compare_backend(arrays(value), saved)
    evidence(
        PREFIX + "-cpu-gpu",
        dict(
            status="passed",
            physical_scalars=count,
            rtol=3e-10,
            amount_energy_gate_atol=3e-13,
            charge_atol_C=3e-25,
            current_atol_A=3e-23,
            voltage_atol_V=3e-11,
            exact_times_and_external_controls=True,
        ),
    )
