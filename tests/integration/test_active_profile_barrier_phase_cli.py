"""Public combined ionic phase preparation, exact snapshots and real SIM restart."""

import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import active_profile_barrier_phase_handoff as bridge
from cells.core import surface_active_profile_barrier_epoch_spec as schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_active_profile_barrier_epoch as model
from cells.models.registry import get_model
from cells.tissue_phase import _source_adapter, read_preparation
from tests.active_profile_barrier_phase_fixtures import DT, prepared, request, source_checkpoint
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


def invoke(directory, name, *args):
    result = subprocess.run(
        [sys.executable, "-B", "-m", "cells", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    (directory / (name + ".stdout.log")).write_text(result.stdout)
    (directory / (name + ".stderr.log")).write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_combined_epoch_public_routing_snapshot_and_explicit_owner_boundary(tmp_path):
    spec = parse_spec(prepared().definition)
    assert get_model(spec.model) is model
    assert spec == parse_spec(spec.to_dict())
    source, before = source_checkpoint()
    assert _source_adapter(source) == (bridge, schema.POLICIES)
    point = initialise(spec)
    assert type(point.state) is model.STATE_TYPE and type(point.layout) is model.LAYOUT_TYPE
    assert len(point.state) == 20 and len(spec.model.channels) == 63
    laws = np.asarray(point.layout.channel_laws)[np.asarray(point.layout.channel_active)]
    assert set(laws.tolist()) == set(range(56))
    table = control_values(spec, [0.0, DT])
    exact(table, control_values(schema.scheduled_spec(spec), [0.0, DT]))
    assert np.any(table.membrane != control_values(source, [0.0, DT]).membrane)
    loaded = load_snapshot(write_snapshot(tmp_path / "epoch", spec, point))
    assert loaded.spec == spec
    exact(loaded.checkpoint.state, point.state)
    exact(loaded.checkpoint.layout, point.layout)
    for target, wrong in ((spec, before), (source, point)):
        with pytest.raises(ConfigError):
            validate_checkpoint(target, wrong)
    with pytest.raises(ConfigError):
        branch_checkpoint(source, before, spec)
    with pytest.raises(ConfigError):
        _source_adapter(spec)
    ordinary = schema.scheduled_spec(spec)
    mixed = BatchSpec((WorldSpec(3, spec), WorldSpec(79, ordinary)), 2, 100, 2**30)
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())
    evidence(
        "combined-epoch-public-snapshot",
        dict(definition=spec.to_dict(), full_trajectory_credit=False),
    )


@pytest.mark.parametrize("backend", ("cpu", "gpu"))
def test_combined_epoch_ensemble_admission_keeps_exact_model(backend):
    raw = deepcopy(prepared().definition)
    raw["execution"]["backend"] = backend
    with pytest.raises(ValueError, match="JIT"):
        parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2))
    raw["execution"]["jit"] = True
    spec = parse_spec(raw)
    assert parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(79, spec)), 2, 100, 2**30)
    assert parse_batch(batch.to_dict()) == batch
    assert get_model(spec.model) is model


def test_combined_epoch_fresh_cli_preparation_and_portable_replay(tmp_path):
    source, point = source_checkpoint()
    snapshot = write_snapshot(tmp_path / "INIT", source, point)
    before = {p.name: p.read_bytes() for p in snapshot.iterdir()}
    simulation = tmp_path / "SIM.json"
    simulation.write_text(json.dumps(request()["simulation"]))
    output = tmp_path / "prepared"
    summary = invoke(
        tmp_path,
        "prepare",
        "tissue-phase",
        "from-snapshot",
        snapshot,
        simulation,
        "--output",
        output,
    )
    assert summary["model_id"] == schema.MODEL_ID
    assert len(summary["carried_parent_fields"]) == 19
    assert read_preparation(output) == prepared()
    assert {p.name: p.read_bytes() for p in snapshot.iterdir()} == before
    invoke(tmp_path, "validate", "tissue-phase", "validate", output)
    snapshot.rename(tmp_path / "archived-INIT")
    simulation.unlink()
    invoke(
        tmp_path,
        "replay",
        "tissue-phase",
        "replay",
        output / "provenance.json",
        "--output",
        tmp_path / "replayed",
    )
    assert read_preparation(tmp_path / "replayed") == prepared()
    evidence(
        "combined-epoch-public-cli",
        dict(summary=summary, portable_replay=True, full_trajectory_credit=False),
    )


def test_combined_epoch_fresh_sim_and_intermediate_restart_keep_all_history(tmp_path):
    spec = parse_spec(prepared().definition)
    assert spec.execution.jit is False
    config = tmp_path / "epoch.json"
    config.write_text(json.dumps(spec.to_dict()))
    original, resumed = tmp_path / "original", tmp_path / "resumed"
    invoke(tmp_path, "run", "run", config, "--output", original, "--checkpoint-at", DT)
    manifest = json.loads((original / "manifest.json").read_text())
    middle = original / manifest["snapshots"][0]
    saved = load_snapshot(middle)
    assert saved.checkpoint.time == DT
    damaged = replace(
        saved.checkpoint, state=saved.checkpoint.state._replace(phase_clock_s=np.zeros(1))
    )
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, damaged)
    invoke(tmp_path, "resume", "resume", middle, "--output", resumed)
    expected, actual = (load_snapshot(p / "checkpoint_final") for p in (original, resumed))
    assert actual.spec == expected.spec == spec
    assert actual.checkpoint.time == expected.checkpoint.time == 2 * DT
    assert type(actual.checkpoint.state) is model.STATE_TYPE
    exact(actual.checkpoint.state, expected.checkpoint.state)
    exact(actual.checkpoint.layout, expected.checkpoint.layout)
    _, before = source_checkpoint()
    with (
        np.load(original / "trajectory.npz", allow_pickle=False) as first,
        np.load(resumed / "trajectory.npz", allow_pickle=False) as second,
    ):
        assert len(first["accepted_times"]) == 3
        np.testing.assert_array_equal(second["accepted_times"], first["accepted_times"][1:])
        for name in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(second[name], first[name][1:])
            if name != "phase_clock_s":
                np.testing.assert_array_equal(first[name][0], getattr(before.state, name))
        selected = first["observation_times"] >= DT
        observed = [k for k in first.files if k.startswith("observed_")]
        for name in ["observation_times", *observed]:
            np.testing.assert_array_equal(second[name], first[name][selected])
        np.testing.assert_array_equal(first["observed_init_phase_clock_s"], DT)
        np.testing.assert_allclose(
            first["observed_elapsed_time_s"][:, 0],
            DT + first["observation_times"],
            atol=1e-23,
            rtol=0,
        )
        arrays = {"original_" + k: first[k] for k in first.files}
        arrays.update({"resumed_" + k: second[k] for k in second.files})
    for directory in (original, resumed):
        metadata = json.loads((directory / "manifest.json").read_text())
        assert metadata["numerics"]["jit"] is False
        assert metadata["timings"]["compile_or_cache_seconds"] == 0
    evidence(
        "combined-epoch-sim-restart",
        dict(
            state_fields=list(model.STATE_TYPE._fields),
            observation_fields=observed,
            duration_s=2 * DT,
            complete_restart_exact=True,
            full_trajectory_credit=False,
            compiled_or_GPU_execution=False,
        ),
        arrays,
    )
