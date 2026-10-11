import hashlib
import json
from dataclasses import replace

import numpy as np
import pytest

from cells.core.runner import branch_checkpoint, run, validate_checkpoint
from cells.core.specs import ConfigError, InputChange, digest
from cells.io import load_snapshot, write_run, write_snapshot


@pytest.mark.parametrize("time", [0.0, 2.03, 5.07, 6.0, 12.0])
def test_snapshot_restart_is_exact(spec, tmp_path, time):
    uninterrupted = run(spec)
    saved = uninterrupted.checkpoint_at(time)
    path = write_snapshot(tmp_path / "snapshot", spec, saved)
    restored = load_snapshot(path)
    assert restored.spec == spec
    assert restored.checkpoint.time == time
    resumed = run(restored.spec, restored.checkpoint)
    for a, b in zip(uninterrupted.final.state, resumed.final.state, strict=True):
        np.testing.assert_array_equal(a, b)
    assert resumed.final.step_index == uninterrupted.final.step_index
    assert resumed.supplied[-1, 0] == uninterrupted.supplied[-1, 0]
    assert resumed.times[0] == time


def test_branch_changes_only_the_future(spec):
    parent = run(spec)
    saved = parent.checkpoint_at(6.0)
    original_amount = np.asarray(saved.state.amount).copy()
    changed = replace(
        spec,
        experiment=replace(spec.experiment, source=spec.experiment.source + (InputChange(6, 0.5),)),
    )
    altered = run(changed, branch_checkpoint(spec, saved, changed))
    unchanged = run(spec, saved)
    assert altered.amount[-1, 0] > unchanged.amount[-1, 0]
    np.testing.assert_array_equal(saved.state.amount, original_amount)
    np.testing.assert_array_equal(parent.final.state.amount, unchanged.final.state.amount)
    np.testing.assert_array_equal(unchanged.amount[0], altered.amount[0])
    assert altered.supplied[-1, 0] > unchanged.supplied[-1, 0]


@pytest.mark.parametrize("mode", ["model", "solver", "history", "lost_boundary", "short_horizon"])
def test_branch_refuses_incompatible_changes(spec, mode):
    saved = run(spec).checkpoint_at(5.07)
    changed = spec
    if mode == "model":
        changed = replace(spec, model=replace(spec.model, decay_rate=0.5))
    elif mode == "solver":
        changed = replace(spec, execution=replace(spec.execution, dt=0.1))
    elif mode == "history":
        changed = replace(spec, experiment=replace(spec.experiment, source=(InputChange(0, 1),)))
    elif mode == "lost_boundary":
        changed = replace(
            spec, experiment=replace(spec.experiment, source=spec.experiment.source[:2])
        )
    else:
        changed = replace(
            spec,
            experiment=replace(
                spec.experiment,
                end_time=4,
                source=spec.experiment.source[:2],
                observation_times=(0, 4),
            ),
        )
    with pytest.raises(ConfigError):
        branch_checkpoint(spec, saved, changed)


def test_off_grid_checkpoint_refused(spec):
    with pytest.raises(ConfigError, match="exact accepted"):
        run(spec).checkpoint_at(0.0125)


def test_checkpoint_clock_and_layout_are_validated(spec):
    saved = run(spec).checkpoint_at(6.0)
    for invalid in (
        replace(saved, time=6.01),
        replace(saved, step_index=True),
        replace(saved, event_index=0),
        replace(saved, layout=saved.layout._replace(ids=np.array([99], dtype=np.int64))),
        replace(saved, state=saved.state._replace(amount=np.array([1.0], dtype=np.float32))),
    ):
        with pytest.raises(ConfigError):
            validate_checkpoint(spec, invalid)


def _rewrite_manifest(path, transform):
    manifest = json.loads((path / "manifest.json").read_text())
    transform(manifest)
    manifest.pop("manifest_sha256", None)
    manifest["manifest_sha256"] = digest(manifest)
    (path / "manifest.json").write_text(json.dumps(manifest))


@pytest.mark.parametrize("mode", ["schema", "source", "runtime", "clock", "random"])
def test_incompatible_snapshot_is_refused(spec, tmp_path, mode):
    path = write_snapshot(tmp_path / "snapshot", spec, run(spec).final)

    def change(manifest):
        if mode == "schema":
            manifest["schema_version"] = 99
        elif mode == "source":
            manifest["source_hashes"]["models/source_decay.py"] = "wrong"
        elif mode == "runtime":
            manifest["runtime"]["python"] = "0.0.0"
        elif mode == "clock":
            manifest["clock"]["event_index"] = -1
        else:
            manifest["random_state"] = 42

    _rewrite_manifest(path, change)
    with pytest.raises(ConfigError):
        load_snapshot(path)


@pytest.mark.parametrize("mode", ["state", "manifest"])
def test_corruption_is_detected(spec, tmp_path, mode):
    path = write_snapshot(tmp_path / "snapshot", spec, run(spec).final)
    if mode == "state":
        with (path / "state.npz").open("ab") as handle:
            handle.write(b"corrupted")
    else:
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["clock"]["time"] = 0
        (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ConfigError, match="checksum"):
        load_snapshot(path)


def test_object_arrays_are_never_unpickled(spec, tmp_path):
    path = write_snapshot(tmp_path / "snapshot", spec, run(spec).final)
    with np.load(path / "state.npz", allow_pickle=False) as archive:
        arrays = {name: archive[name] for name in archive.files}
    arrays["amount"] = np.array([{"not": "numeric"}], dtype=object)
    np.savez(path / "state.npz", **arrays)
    _rewrite_manifest(
        path,
        lambda m: m.update(
            {"state_sha256": hashlib.sha256((path / "state.npz").read_bytes()).hexdigest()}
        ),
    )
    with pytest.raises(ConfigError, match="numeric checkpoint"):
        load_snapshot(path)


def test_outputs_and_snapshots_never_overwrite(spec, tmp_path):
    result = run(spec)
    snapshot = tmp_path / "snapshot"
    write_snapshot(snapshot, spec, result.final)
    before = (snapshot / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        write_snapshot(snapshot, spec, result.final)
    assert (snapshot / "manifest.json").read_bytes() == before
    output = tmp_path / "run"
    summary = write_run(output, result, checkpoint_times=(6.0,))
    with pytest.raises(FileExistsError):
        write_run(output, result)
    assert summary["status"] == "complete"
    manifest = json.loads((output / "manifest.json").read_text())
    for name, checksum in manifest["files_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == checksum
    with np.load(output / "trajectory.npz", allow_pickle=False) as data:
        np.testing.assert_array_equal(data["amount"], result.amount)
    assert manifest["runtime"]["packages"]["jax"]
    assert manifest["source_hashes"]["models/source_decay.py"]
