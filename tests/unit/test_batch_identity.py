"""Cohort metadata sharing preserves standalone checkpoints and change refusal."""

import copy
import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells import batch_io
from cells.core.batch import parse_batch
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.io import load_snapshot, write_snapshot
from tests.batch_fixtures import definition


def cohort():
    # Exercise the same supported ionic model on CPU and GPU. Parse the complete
    # definitions before allocating states, including each requested backend.
    path = Path(__file__).resolve().parents[2] / "configs/assembly_regulated_cell.json"
    first = json.loads(path.read_text())["ionic"]
    first["execution"]["backend"] = os.environ.get("CELLS_COUPLED_TEST_BACKEND", "cpu")
    second = copy.deepcopy(first)
    second["model"]["cells"][0]["channel"]["initial_gate"]["m"] = 0.35
    spec = parse_batch(definition([parse_spec(first), parse_spec(second)]).to_dict())
    return spec, {w.world_id: initialise(w.simulation) for w in spec.worlds}


def test_shared_identity_preserves_complete_standalone_children(tmp_path, monkeypatch):
    spec, checkpoints = cohort()
    assert not np.array_equal(checkpoints[10].state.gate, checkpoints[11].state.gate)
    calls = {"source": 0, "runtime": 0}
    for name, field in (("source_hashes", "source"), ("runtime_identity", "runtime")):
        original = getattr(batch_io, name)

        def measured(*args, original=original, field=field):
            calls[field] += 1
            return original(*args)

        monkeypatch.setattr(batch_io, name, measured)
    batch_io.write_batch_snapshot(tmp_path / "batch", spec, checkpoints)
    assert calls == {"source": 2, "runtime": 2}
    parent = json.loads((tmp_path / "batch/manifest.json").read_text())
    for world in spec.worlds:
        child = tmp_path / f"batch/world-{world.world_id}"
        standalone = tmp_path / f"scalar-{world.world_id}"
        write_snapshot(standalone, world.simulation, checkpoints[world.world_id])
        observed = json.loads((child / "manifest.json").read_text())
        expected = json.loads((standalone / "manifest.json").read_text())
        for field in ("runtime", "source_hashes"):
            assert observed[field] == expected[field] == parent[field]
        # Archive byte digests can include ZIP metadata; compare all semantic
        # manifest fields and every complete state/layout array independently.
        for field in ("manifest_sha256", "state_sha256"):
            observed.pop(field)
            expected.pop(field)
        assert observed == expected
        restored = load_snapshot(child)
        for actual, wanted in zip(
            (*restored.checkpoint.state, *restored.checkpoint.layout),
            (*checkpoints[world.world_id].state, *checkpoints[world.world_id].layout),
            strict=True,
        ):
            np.testing.assert_array_equal(actual, wanted)


@pytest.mark.parametrize("field", ["source_hashes", "runtime_identity"])
def test_changed_identity_prevents_cohort_publication(tmp_path, monkeypatch, field):
    spec, checkpoints = cohort()
    original = getattr(batch_io, field)
    calls = 0

    def changing(*args):
        nonlocal calls
        calls += 1
        value = copy.deepcopy(original(*args))
        if calls > 1:
            value["changed_during_test"] = "changed"
        return value

    monkeypatch.setattr(batch_io, field, changing)
    with pytest.raises(ConfigError, match="changed during publication"):
        batch_io.write_batch_snapshot(tmp_path / "incomplete", spec, checkpoints)
    assert not (tmp_path / "incomplete/manifest.json").exists()


def test_each_publication_reads_fresh_sources(tmp_path, monkeypatch):
    spec, checkpoints = cohort()
    original = batch_io.source_hashes
    calls = 0

    def versioned():
        nonlocal calls
        calls += 1
        return original() | {"fixture_version": str((calls - 1) // 2)}

    monkeypatch.setattr(batch_io, "source_hashes", versioned)
    for name in ("first", "second"):
        batch_io.write_batch_snapshot(tmp_path / name, spec, checkpoints)
    assert calls == 4
    versions = [
        json.loads((tmp_path / name / "manifest.json").read_text())["source_hashes"][
            "fixture_version"
        ]
        for name in ("first", "second")
    ]
    assert versions == ["0", "1"]


def test_shared_identity_keeps_child_corruption_refusal(tmp_path):
    spec, checkpoints = cohort()
    batch_io.write_batch_snapshot(tmp_path / "batch", spec, checkpoints)
    with (tmp_path / f"batch/world-{spec.worlds[0].world_id}/state.npz").open("ab") as handle:
        handle.write(b"corrupted saved checkpoint")
    with pytest.raises(ConfigError, match="state checksum"):
        batch_io.load_batch_snapshot(tmp_path / "batch")
