"""Public active epoch interfaces retain full history and reject implicit changes."""

import json
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import surface_active_profile_epoch_spec as epoch
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_active_profile_epoch as model
from cells.models import surface_active_profile_interventions as active
from cells.models.registry import get_model
from cells.tissue_phase import prepare_request, read_preparation, replay
from tests.active_phase_fixtures import prepared, request, source_checkpoint
from tests.integration.test_cli import cli


def exact(left, right):
    assert type(left) is type(right)
    assert left._fields == right._fields
    for a, b in zip(left, right, strict=True):
        assert np.asarray(a).dtype == np.asarray(b).dtype
        np.testing.assert_array_equal(a, b)


def test_public_active_epoch_complete_identity_and_history(tmp_path):
    raw = prepared().definition
    spec = parse_spec(raw)
    assert get_model(spec.model) is model
    assert type(spec.model) is epoch.SurfaceActiveProfileEpochModel
    assert spec == epoch.parse(raw) == parse_spec(spec.to_dict())
    assert digest(spec.to_dict()) == digest(raw)
    source, before = source_checkpoint()
    point = initialise(spec)
    assert type(point.state) is model.STATE_TYPE and type(point.layout) is model.LAYOUT_TYPE
    exact(active.parent_state(point.state), active.parent_state(before.state))
    exact(active.parent_layout(point.layout), active.parent_layout(before.layout))
    assert np.any(point.state.pump_cycles != 0)
    assert np.any(point.state.channel_transferred != 0)
    assert np.any(point.state.metabolic_work_pJ != 0)
    assert len(point.state) == 20 and len(spec.model.channels) == 56
    np.testing.assert_array_equal(point.state.phase_clock_s, [0.0])
    assert point.time == point.step_index == 0
    write_snapshot(tmp_path / "epoch", spec, point)
    saved = load_snapshot(tmp_path / "epoch")
    exact(saved.checkpoint.state, point.state)
    exact(saved.checkpoint.layout, point.layout)
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 10000, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    with pytest.raises(ValueError, match="JIT"):
        parse_ensemble(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=2))
    compiled = deepcopy(raw)
    compiled["execution"]["jit"] = True
    assert parse_ensemble(
        dict(model="ionic_worlds@1", simulation=compiled, worlds=2, window_steps=2)
    ).simulation == parse_spec(compiled)
    with pytest.raises(ConfigError):
        validate_checkpoint(spec, before)
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(source, before, spec)
    with pytest.raises(ConfigError):
        excise(spec, point, [spec.model.cells[0].id])
    mixed = BatchSpec(
        (WorldSpec(3, spec), WorldSpec(79, epoch.scheduled_spec(spec))), 2, 10000, 2**32
    )
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())


def test_cli_active_snapshot_prepare_replay_and_ordinary_validation(tmp_path):
    source, before = source_checkpoint()
    snapshot = write_snapshot(tmp_path / "source", source, before)
    raw = request()
    simulation = tmp_path / "simulation.json"
    simulation.write_text(json.dumps(raw["simulation"]))
    output = tmp_path / "prepared"
    first = cli("tissue-phase", "from-snapshot", snapshot, simulation, "--output", output)
    assert first.returncode == 0, first.stderr
    summary = json.loads(first.stdout)
    assert summary["model_id"] == epoch.MODEL_ID
    assert summary["clocks"]["init_checkpoint_time_s"] == before.time
    assert len(summary["carried_parent_fields"]) == 19
    assert read_preparation(output) == prepared()
    again = tmp_path / "replayed"
    second = cli("tissue-phase", "replay", output / "provenance.json", "--output", again)
    assert second.returncode == 0, second.stderr
    assert read_preparation(again) == prepared()
    assert cli("tissue-phase", "validate", again).returncode == 0
    assert cli("validate", again / "definition.json").returncode == 0
    # The embedded recipe does not depend on the source file/directory after capture.
    simulation.unlink()
    portable = tmp_path / "portable.json"
    portable.write_text(json.dumps(raw))
    third = cli("tissue-phase", "prepare", portable, "--output", tmp_path / "portable")
    assert third.returncode == 0, third.stderr
    assert read_preparation(tmp_path / "portable") == prepared()
    refused = cli("tissue-phase", "prepare", portable, "--output", output)
    assert refused.returncode == 2 and "already exists" in refused.stderr


@pytest.mark.parametrize("target", ["policies", "source", "simulation", "clock"])
def test_public_active_preparation_refuses_corrupt_recipe(target):
    raw = request()
    if target == "policies":
        raw["policies"]["clock_policy"] = "reset-all-history"
    elif target == "source":
        raw["source"]["checkpoint"]["state"]["pump_cycles"]["values"][0] += 1
    elif target == "simulation":
        raw["simulation"]["model"]["phase"] = "INIT"
    else:
        raw["source"]["checkpoint"]["state"]["phase_clock_s"]["values"][0] = 0.0
        value = deepcopy(raw["source"])
        value.pop("identity")
        raw["source"]["identity"] = digest(value)
    with pytest.raises((ConfigError, NumericalError)):
        prepare_request(raw)


def test_active_replay_checks_the_complete_provenance():
    correct = prepared()
    assert replay(correct.provenance) == correct
    wrong = deepcopy(correct.provenance)
    wrong["preservation"]["carried_parent_fields"] = []
    value = deepcopy(wrong)
    value.pop("identity")
    wrong["identity"] = digest(value)
    with pytest.raises(ConfigError, match="preservation"):
        replay(wrong)


def test_public_eager_active_epoch_full_history_observations_and_restart(tmp_path):
    """Two SIM steps verify public execution; the independent component covers physics."""
    spec = parse_spec(prepared().definition)
    result = run(spec)
    write_run(tmp_path / "run", result)
    _, before = source_checkpoint()
    for key, values in active.parent_state(result.history)._asdict().items():
        np.testing.assert_array_equal(values[0], getattr(before.state, key))
    np.testing.assert_array_equal(
        result.observations.init_phase_clock_s,
        np.full_like(result.observations.init_phase_clock_s, before.state.phase_clock_s[0]),
    )
    np.testing.assert_allclose(
        result.observations.elapsed_time_s[:, 0],
        before.time + result.times,
        rtol=0,
        atol=1e-23,
    )
    middle = result.checkpoint_at(spec.execution.dt)
    folder = write_snapshot(tmp_path / "middle", spec, middle)
    restored = load_snapshot(folder)
    resumed = run(restored.spec, restored.checkpoint)
    exact(resumed.final.state, result.final.state)
    exact(resumed.final.layout, result.final.layout)
    damaged = replace(middle, state=middle.state._replace(phase_clock_s=np.zeros(1)))
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    (tmp_path / "comparison.json").write_text(
        json.dumps(
            dict(
                status="passed",
                state_fields=list(result.history._fields),
                real_sim_steps=result.final.step_index,
                init_time=before.time,
                complete_initial_parent_state_exact=True,
                complete_restart_exact=True,
                diagnostics=result.diagnostics,
                scope="Two eager CPU steps; no compiled qualification",
            ),
            indent=2,
        )
        + "\n"
    )
