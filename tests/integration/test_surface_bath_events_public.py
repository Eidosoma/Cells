"""Public bath identity, portable full-array checkpoints and guarded restart.

Short prefixes qualify interfaces and restart semantics. Independent stage
physics lives in the component suite; full bath trajectories remain separate.
"""

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from tests.surface_bath_events_fixtures import OWNERS, PREFIX_DT, definition, prefix
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


def arrays_and_observations(model, spec, point):
    state = model.STATE_TYPE(*(np.asarray(v) for v in point.state))
    layout = model.LAYOUT_TYPE(*(np.asarray(v) for v in point.layout))
    physical = model.physical_state(state, layout, xp=np)
    history = model.STATE_TYPE(*(v[None] for v in state))
    observed = model.observe_history(np.asarray([point.time]), history, layout, [point.time], spec)
    arrays = {
        group + "_" + key: np.asarray(value)
        for group, values in (
            ("state", state._asdict()),
            ("layout", layout._asdict()),
            ("physical", physical._asdict()),
            ("observed", vars(observed)),
        )
        for key, value in values.items()
    }
    return arrays


def export_restored_snapshot(snapshot, artifact_path, output):
    """Fresh interpreter entrypoint; all array values are returned for comparison."""
    saved = load_snapshot(snapshot)
    model = get_model(saved.spec.model)
    schema = OWNERS["active" if "active" in model.MODEL_ID else "passive"][0]
    artifact = json.loads(Path(artifact_path).read_text())
    assert schema.replay(artifact) == saved.spec
    assert type(saved.checkpoint.state) is model.STATE_TYPE
    assert type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    np.savez(output, **arrays_and_observations(model, saved.spec, saved.checkpoint))
    print(
        json.dumps(
            dict(
                definition=saved.spec.to_dict(),
                time=saved.checkpoint.time,
                state_fields=list(model.STATE_TYPE._fields),
                layout_fields=list(model.LAYOUT_TYPE._fields),
                initial_operation=model.initial_operation(saved.spec),
            )
        )
    )


def invoke(tmp_path, name, arguments):
    completed = subprocess.run(
        [sys.executable, "-B", *map(str, arguments)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    (tmp_path / (name + ".stdout.log")).write_text(completed.stdout)
    (tmp_path / (name + ".stderr.log")).write_text(completed.stderr)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize("family", OWNERS)
def test_bath_public_identity_controls_and_original_anchor_snapshot(tmp_path, family):
    schema, model, spec, point = prefix(family)
    assert get_model(spec.model) is model
    assert spec == parse_spec(spec.to_dict())
    assert len(point.state) == OWNERS[family][2]
    table = [0.0, PREFIX_DT, 2 * PREFIX_DT, *spec.experiment.observation_times]
    exact(control_values(spec, table), control_values(schema.owner_spec(spec), table))
    if family == "active":
        assert len({channel.kinetic_law for channel in spec.model.channels}) == 56
        assert len(spec.experiment.channels) == len(spec.model.channels)
        assert len(spec.experiment.pumps) == len(spec.model.membranes)
    initial = initialise(spec)
    exact(point.layout, initial.layout)
    assert np.any(point.state.face_transferred != 0)
    assert np.any(point.state.reservoir_chemical_work_pJ != 0)
    saved = load_snapshot(write_snapshot(tmp_path / "prefix", spec, point))
    assert saved.spec == spec
    exact(saved.checkpoint.state, point.state)
    exact(saved.checkpoint.layout, point.layout)
    bad = replace(point, state=point.state._replace(phase_clock_s=np.zeros(1)))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, bad)
    with pytest.raises(ConfigError):
        validate_checkpoint(schema.owner_spec(spec), point)
    changed = deepcopy(spec.to_dict())
    changed["model"]["bath_events"][0]["amplitude"] *= 1.01
    with pytest.raises(ConfigError, match="model"):
        branch_checkpoint(spec, point, parse_spec(changed))
    mixed = BatchSpec((WorldSpec(3, spec), WorldSpec(71, schema.owner_spec(spec))), 2, 512, 2**30)
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())
    evidence(
        "bath-public-prefix-" + family,
        dict(
            definition=spec.to_dict(),
            state_fields=list(point.state._fields),
            layout_fields=list(point.layout._fields),
            duration_s=PREFIX_DT,
            full_trajectory_credit=False,
        ),
        arrays_and_observations(model, spec, point),
    )


@pytest.mark.parametrize("backend", ("cpu", "gpu"))
@pytest.mark.parametrize("family", OWNERS)
def test_bath_world_admission_preserves_model_and_full_controls(family, backend):
    raw = definition(family)
    raw["execution"]["backend"] = backend
    with pytest.raises(ValueError, match="JIT"):
        parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2))
    raw["execution"]["jit"] = True
    spec = parse_spec(raw)
    worlds = parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2))
    assert worlds.simulation == spec
    assert get_model(spec.model) is OWNERS[family][1]
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(71, spec)), 2, 512, 2**30)
    assert parse_batch(batch.to_dict()) == batch


@pytest.mark.parametrize("family", OWNERS)
def test_bath_fresh_cli_validation_and_complete_portable_snapshot(tmp_path, family):
    schema, model, spec, point = prefix(family)
    config, artifact = tmp_path / "definition.json", tmp_path / "controller.json"
    config.write_text(json.dumps(spec.to_dict()))
    artifact.write_text(json.dumps(schema.artifact(spec)))
    validated = invoke(tmp_path, "validate", ["-m", "cells", "validate", config])
    assert validated == dict(status="valid", steps=len(timeline(spec)) - 1, sha256=spec.fingerprint)
    snapshot = write_snapshot(tmp_path / "snapshot", spec, point)
    before = {path.name: path.read_bytes() for path in snapshot.iterdir()}
    config.unlink()
    restored = tmp_path / "restored.npz"
    result = invoke(
        tmp_path,
        "restore",
        [
            "-c",
            "from tests.integration.test_surface_bath_events_public import "
            "export_restored_snapshot; import sys; export_restored_snapshot(*sys.argv[1:])",
            snapshot,
            artifact,
            restored,
        ],
    )
    assert result["definition"] == spec.to_dict()
    assert result["time"] == PREFIX_DT
    assert result["state_fields"] == list(model.STATE_TYPE._fields)
    assert result["layout_fields"] == list(model.LAYOUT_TYPE._fields)
    assert result["initial_operation"] == model.initial_operation(spec)
    assert {path.name: path.read_bytes() for path in snapshot.iterdir()} == before
    expected = arrays_and_observations(model, spec, point)
    with np.load(restored, allow_pickle=False) as actual:
        assert set(actual.files) == set(expected)
        for key, value in expected.items():
            assert actual[key].dtype == value.dtype
            np.testing.assert_array_equal(actual[key], value, err_msg=key)
    evidence(
        "bath-public-fresh-snapshot-" + family,
        dict(
            definition=spec.to_dict(),
            complete_state_layout_physical_observations_exact=True,
            initial_controller_operation=result["initial_operation"],
            full_trajectory_credit=False,
        ),
        expected,
    )


@pytest.mark.parametrize("family", OWNERS)
def test_bath_actual_guarded_windows_restart_preserves_controller_history(tmp_path, family):
    spec = parse_spec(definition(family))
    model = OWNERS[family][1]
    assert spec.execution.jit is False
    iterator = iter_windows(spec, WindowPolicy(1, "full"))
    first, expected = next(iterator), next(iterator)
    iterator.close()
    assert first.final.time == PREFIX_DT
    assert expected.final.time == 2 * PREFIX_DT
    saved = load_snapshot(write_snapshot(tmp_path / "middle", spec, first.final))
    iterator = iter_windows(spec, WindowPolicy(1, "full"), saved.checkpoint)
    actual = next(iterator)
    iterator.close()
    exact(actual.final.state, expected.final.state)
    exact(actual.final.layout, expected.final.layout)
    exact(actual.history, expected.history)
    baseline_times = np.concatenate((first.observations.times, expected.observations.times))
    selected = baseline_times >= PREFIX_DT
    for name in vars(expected.observations):
        baseline = np.concatenate(
            (getattr(first.observations, name), getattr(expected.observations, name)), axis=0
        )
        np.testing.assert_array_equal(
            getattr(actual.observations, name), baseline[selected], err_msg=name
        )
    for result in (first, expected, actual):
        assert result.timings["compile_or_cache_seconds"] == 0
        assert np.any(result.final.state.reservoir_chemical_work_pJ != 0)
    evidence(
        "bath-public-guarded-window-restart-" + family,
        dict(
            definition=spec.to_dict(),
            duration_s=2 * PREFIX_DT,
            complete_restart_exact=True,
            full_trajectory_credit=False,
            compiled_or_GPU_execution=False,
        ),
        arrays_and_observations(model, spec, actual.final),
    )
