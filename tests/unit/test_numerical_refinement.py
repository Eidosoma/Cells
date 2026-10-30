"""Explicit resolution changes numerical boundaries, not physiological clocks.

The microsecond histories below qualify execution plumbing and unchanged
accounting. They do not qualify recovery from the depleted half-second case.
"""

import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import batch, runner
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.grid import checked_grid
from cells.core.resources import trace_bytes
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble import ionic
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from validation.tissue import surface_cotransport_water_fixtures as fixtures


def definition(*, jit=False):
    raw = fixtures.definition()
    dt = fixtures.DT
    raw["execution"].update(jit=jit, refinement_times=[dt / 2, dt, 1.5 * dt])
    raw["experiment"].update(end_time=2 * dt, observation_times=[0.0, dt / 2, dt, 1.5 * dt, 2 * dt])
    raw["experiment"]["regeneration_controls"][0]["schedule"].append(
        dict(time=dt, availability=0.5)
    )
    return raw


def test_legacy_hash_and_empty_omission():
    raw = fixtures.definition()
    original = deepcopy(raw)
    legacy = parse_spec(raw)
    # Computed with the preceding frozen implementation, before this feature.
    assert legacy.fingerprint == "cadfc02750a325dfef820880d53a75766a2eab92eecedb2cb541c9871de2c045"
    raw["execution"]["refinement_times"] = []
    empty = parse_spec(raw)
    assert empty == legacy and empty.fingerprint == legacy.fingerprint
    assert "refinement_times" not in empty.to_dict()["execution"]
    assert original == {
        **raw,
        "execution": {k: v for k, v in raw["execution"].items() if k != "refinement_times"},
    }
    refined = parse_spec(definition())
    assert parse_spec(refined.to_dict()) == refined
    assert type(refined.execution.refinement_times) is tuple


@pytest.mark.parametrize(
    "points",
    [
        None,
        {},
        "times",
        (1e-8,),
        [True],
        [float("nan")],
        [float("inf")],
        [-1e-8],
        [0.0],
        [1.0],
        [fixtures.END_TIME],
        [2e-8, 1e-8],
        [1e-8, 1e-8],
    ],
)
def test_invalid_refinement_declarations(points):
    raw = fixtures.definition()
    raw["execution"]["refinement_times"] = points
    with pytest.raises(ConfigError, match="refinement"):
        parse_spec(raw)


def test_exact_grid_union_observations_and_unchanged_controls():
    raw = definition()
    dt = fixtures.DT
    adjacent = float(np.nextafter(dt, np.inf))
    raw["execution"]["refinement_times"].insert(2, adjacent)
    raw["experiment"]["observation_times"].insert(3, adjacent)
    before = deepcopy(raw)
    spec = parse_spec(raw)
    expected = np.array([0.0, dt / 2, dt, adjacent, 1.5 * dt, 2 * dt])
    np.testing.assert_array_equal(runner.timeline(spec), expected)
    grid = checked_grid(spec, window_steps=2)
    np.testing.assert_array_equal(np.asarray(grid), expected)
    windows = list(grid.windows(0, 2))
    np.testing.assert_array_equal(
        np.concatenate([windows[0], *[w[1:] for w in windows[1:]]]), expected
    )
    assert raw == before
    assert [c.time for c in spec.experiment.changes] == [0.0, dt]
    np.testing.assert_array_equal([event_index(spec, t) for t in expected], [0, 0, 1, 1, 1, 1])
    unrefined = deepcopy(raw)
    unrefined["execution"].pop("refinement_times")
    unrefined["experiment"]["observation_times"] = [0.0, dt, 2 * dt]
    for actual, old in zip(
        control_values(spec, expected), control_values(parse_spec(unrefined), expected), strict=True
    ):
        np.testing.assert_array_equal(actual, old)
    assert runner.integration_steps(spec, expected).min() == adjacent - dt


def test_unsupported_public_models_refuse_refinement(config_data):
    original = parse_spec(config_data)
    config_data["execution"]["refinement_times"] = [0.01]
    with pytest.raises(ConfigError):
        parse_spec(config_data)
    fabricated = replace(
        original, execution=SimpleNamespace(**vars(original.execution), refinement_times=(0.01,))
    )
    for operation in (
        lambda: fabricated.to_dict(),
        lambda: runner.timeline(fabricated),
        lambda: checked_grid(fabricated),
    ):
        with pytest.raises(ConfigError, match="refinement_times currently require"):
            operation()


def test_native_discrete_clock_refuses_refinement():
    raw = json.loads(
        (Path(__file__).resolve().parents[2] / "configs/betse_spatial_junction.json").read_text()
    )
    original = parse_spec(raw)
    assert callable(get_model(original.model).integration_steps)
    points = (original.execution.dt / 2,)
    raw["execution"]["refinement_times"] = list(points)
    with pytest.raises(ConfigError):
        parse_spec(raw)
    fabricated = replace(
        original,
        execution=SimpleNamespace(**vars(original.execution), refinement_times=points),
    )
    with pytest.raises(ConfigError, match="refinement_times currently require"):
        runner.timeline(fabricated)
    with pytest.raises(ConfigError, match="refinement_times currently require"):
        fabricated.to_dict()


def test_refined_bounds_before_timeline_allocation(monkeypatch):
    spec = parse_spec(definition())

    def no_allocation(*args, **kwargs):
        raise AssertionError("Timeline allocated before its resource admission")

    monkeypatch.setattr(runner.np, "fromiter", no_allocation)
    tight_steps = replace(spec, execution=replace(spec.execution, max_steps=3))
    with pytest.raises(ConfigError, match="max_steps"):
        runner.timeline(tight_steps)
    tight_storage = replace(
        spec, execution=replace(spec.execution, max_trace_bytes=trace_bytes(spec, 3))
    )
    with pytest.raises(ConfigError, match="max_trace_bytes"):
        runner.timeline(tight_storage)


def test_batch_and_ensemble_bounds_include_refinement(monkeypatch):
    spec = parse_spec(definition(jit=True))
    worlds = (WorldSpec(1, spec), WorldSpec(2, spec))
    # Legacy conservative bound: (2 nominal steps + 2 control points) * 2.
    too_small = BatchSpec(worlds, 2, 8, 2**30)

    def no_timeline(*args, **kwargs):
        raise AssertionError("Batch allocated a timeline before work admission")

    monkeypatch.setattr(batch, "timeline", no_timeline)
    for operation in (batch.plan_batch, batch.checkpoint_batch_limits):
        with pytest.raises(ConfigError, match="max_padded_steps"):
            operation(too_small)
    adequate = replace(too_small, max_padded_steps=14)
    assert batch.checkpoint_batch_limits(adequate)[1] == 14
    old_storage = 2 * sum(
        trace_bytes(w.simulation, 4) + trace_bytes(w.simulation, 0, 0) for w in worlds
    )
    with pytest.raises(ConfigError, match="max_working_bytes"):
        batch.plan_batch(replace(adequate, max_working_bytes=old_storage))
    ensemble = ionic.parse_spec(dict(model="ionic_worlds@1", simulation=spec.to_dict(), worlds=2))
    assert ensemble.batch().max_padded_steps == 16


def evidence_root():
    path = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if not path:
        raise RuntimeError("Numerical qualification requires persistent evidence")
    folder = Path(path) / "refinement"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def capture(monkeypatch, label):
    """Retain all proposed fields even if the unchanged acceptance checks fail."""
    original = runner._analyse_segment
    folder = evidence_root()
    count = 0

    def analyse(spec, parent, times, arrays, final_state, layout, requested):
        nonlocal count
        name = f"{label}-{count:02d}"
        count += 1
        with (folder / (name + ".npz")).open("xb") as stream:
            np.savez_compressed(
                stream,
                times=times,
                **dict(zip(parent.state._fields, arrays, strict=True)),
                **{"layout__" + k: np.asarray(v) for k, v in layout._asdict().items()},
            )
        row = dict(
            inputs=spec.to_dict(),
            parent_time=parent.time,
            parent_step=parent.step_index,
            parent_event=parent.event_index,
            status="proposed",
        )
        path = folder / (name + ".json")
        path.write_text(json.dumps(row, indent=2) + "\n")
        try:
            result = original(spec, parent, times, arrays, final_state, layout, requested)
        except Exception as error:
            row.update(status="rejected", error_type=type(error).__name__, error=str(error))
            path.write_text(json.dumps(row, indent=2) + "\n")
            raise
        row.update(status="accepted", diagnostics=result[3])
        path.write_text(json.dumps(row, indent=2) + "\n")
        return result

    monkeypatch.setattr(runner, "_analyse_segment", analyse)


def assert_same_state(left, right):
    for a, b in zip(left, right, strict=True):
        np.testing.assert_array_equal(a, b)


def test_numerical_eager_windows_snapshot_and_batch(tmp_path, monkeypatch):
    capture(monkeypatch, "eager")
    spec = parse_spec(definition())
    result = runner.run(spec)
    assert len(result.history) == 31
    assert result.final.step_index == 4 and result.final.event_index == 1
    point = result.checkpoint_at(fixtures.DT / 2)
    assert point.step_index == 1 and point.event_index == 0
    path = tmp_path / "refined-snapshot"
    write_snapshot(path, spec, point)
    saved = load_snapshot(path)
    assert saved.spec == spec
    resumed = runner.run(saved.spec, saved.checkpoint)
    for actual, target in zip(resumed.history, result.history, strict=True):
        np.testing.assert_array_equal(actual, target[1:])
    terminal = runner.run(spec, result.final)
    assert len(terminal.times) == 1
    assert_same_state(terminal.final.state, result.final.state)
    parts = list(iter_windows(spec, WindowPolicy(2, "full")))
    for field, target in zip(result.history._fields, result.history, strict=True):
        np.testing.assert_array_equal(
            np.concatenate(
                [getattr(p.history, field)[0 if i == 0 else 1 :] for i, p in enumerate(parts)]
            ),
            target,
        )
    changed = replace(spec, execution=replace(spec.execution, refinement_times=(fixtures.DT / 4,)))
    with pytest.raises(ConfigError, match="execution settings"):
        runner.branch_checkpoint(spec, point, changed)
    raw = definition()
    raw["execution"]["refinement_times"] = [fixtures.DT / 4]
    raw["experiment"]["observation_times"] = [0.0, fixtures.DT / 4, fixtures.DT, 2 * fixtures.DT]
    second = parse_spec(raw)
    other = runner.run(second)
    cohort = BatchSpec((WorldSpec(5, spec), WorldSpec(9, second)), 2, 32, 2**30)
    together = batch.run_batch(cohort)
    for key, single in ((5, result), (9, other)):
        assert_same_state(together.worlds[key].history, single.history)
        assert_same_state(together.worlds[key].final.state, single.final.state)


def test_numerical_compiled_same_declared_grid(monkeypatch):
    import jax

    assert not jax.config.jax_disable_jit, "This check must actually compile"
    capture(monkeypatch, "compiled")
    result = runner.run(parse_spec(definition(jit=True)))
    folder = evidence_root()
    with np.load(folder / "eager-00.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(result.times, saved["times"])
        for name, values in zip(result.history._fields, result.history, strict=True):
            # JIT expression fusion can round differently; use the existing
            # component budget, with a charge-specific absolute tolerance.
            absolute = 3e-23 if name.endswith("_C") else 3e-12
            np.testing.assert_allclose(values, saved[name], rtol=3e-10, atol=absolute)
    assert result.final.step_index == 4 and result.final.event_index == 1
