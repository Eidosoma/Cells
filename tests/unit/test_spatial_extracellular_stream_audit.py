"""Saved bounded windows, independent clocks and rehashed chunk/checkpoint failures."""

import json
import shutil
from dataclasses import replace

import numpy as np
import pytest

from cells.batch_io import load_batch_snapshot
from cells.batch_window_io import write_windowed_batch
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.windows import WindowPolicy
from cells.io import _sha256 as sha
from cells.window_io import write_windowed_run
from scripts import spatial_extracellular_acceptance_plan as plan
from scripts.audit_spatial_extracellular_build import audit_stream, collect_stream
from tests.spatial_extracellular_fixtures import load_cases, spec_for

PROTOCOL, CASES = load_cases()


@pytest.fixture(scope="module")
def original(tmp_path_factory):
    available = {c.id: c for c in CASES}
    names = plan.GROUPS["membrane"]
    cases = [
        replace(available[name], horizon_s=t, controls=(available[name].controls[0],))
        for name, t in zip(names, (0.00075, 0.00125, 0.001, 0.0005, 0.0015), strict=True)
    ]
    sizes = dict(zip(plan.CAPACITY_KEYS, plan.CAPACITIES["membrane"], strict=True))
    specs = [
        spec_for(c, capacities=sizes, samples=[0, 0.00001, 0.00021, c.horizon_s]) for c in cases
    ]
    batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 5, 1000, 2**29)
    root = tmp_path_factory.mktemp("spatial-streams")
    write_windowed_run(
        root / "scalar", specs[0], WindowPolicy(2, "full"), checkpoint_times=(0.00025,)
    )
    write_windowed_batch(
        root / "cohort", batch, WindowPolicy(2, "full"), checkpoint_every_windows=2
    )
    saved = load_batch_snapshot(root / "cohort/snapshots/round-0000000002")
    write_windowed_batch(root / "resumed", batch, WindowPolicy(3, "full"), saved.checkpoints)
    return root, cases, specs, batch


def test_short_scalar_and_different_horizon_cohorts(original):
    root, cases, specs, batch = original
    values, scalar = audit_stream(root / "scalar", cases[0], PROTOCOL, expected_spec=specs[0])
    assert scalar["structure"]["snapshots"] == 3 and values[0]["accepted_times"][-1] == 0.00075
    for name in ("cohort", "resumed"):
        values, report = audit_stream(
            root / name, cases, PROTOCOL, group="membrane", expected_spec=batch
        )
        assert report["structure"]["worlds"] == 5
        assert len({v["accepted_times"][-1] for v in values.values()}) == 5


@pytest.fixture
def saved(tmp_path, original):
    root, cases, specs, batch = original
    shutil.copytree(root / "cohort", tmp_path / "cohort")
    return tmp_path / "cohort", cases, batch


@pytest.mark.parametrize(
    "field",
    [
        "amount_increment",
        "extracellular_amount_increment",
        "face_transferred",
        "membrane_transferred",
        "membrane_dissipated_energy_pJ",
        "face_dissipated_energy_pJ",
        "observed_face_current_A",
        "observed_current_normalized",
        "observed_face_delta_mu_J_per_mol",
        "observed_membrane_flux_fmol_per_s",
    ],
)
def test_rehashed_real_chunk_corruption_fails(saved, field):
    path, cases, batch = saved
    records = [json.loads(line) for line in (path / "windows.jsonl").read_text().splitlines()]
    # World 2 has two real cells and two real bulk faces, not merely padding.
    record = next(
        r for r in records if r["kind"] == "world_window" and r["world_id"] == 2 and r["index"] == 0
    )
    target = path / record["path"]
    with np.load(target, allow_pickle=False) as archive:
        values = dict(archive)
    values[field].reshape(len(values[field]), -1)[1, 0] += 1
    np.savez(target, **values)
    record["sha256"] = sha(target)
    (path / "windows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files_sha256"]["windows.jsonl"] = sha(path / "windows.jsonl")
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, AssertionError)):
        audit_stream(path, cases, PROTOCOL, group="membrane", expected_spec=batch)


@pytest.mark.parametrize(
    "change",
    ["extra", "duplicate_chunk", "missing_world", "clock", "observer", "source", "checkpoint"],
)
def test_stream_structure_and_complete_snapshot_identity(saved, change):
    path, cases, batch = saved
    manifest = json.loads((path / "manifest.json").read_text())
    records = [json.loads(line) for line in (path / "windows.jsonl").read_text().splitlines()]
    if change == "extra":
        (path / "extra.json").write_text("{}")
    elif change == "duplicate_chunk":
        records.insert(1, records[0])
    elif change == "missing_world":
        records = [r for r in records if r.get("world_id") != 2]
    elif change == "clock":
        records[0]["end_step"] += 1
    elif change == "observer":
        manifest["observer"]["id"] = "invented"
    elif change == "source":
        manifest["source_hashes"] = {}
    else:
        target = path / "checkpoint_final/world-2/state.npz"
        with np.load(target, allow_pickle=False) as archive:
            values = dict(archive)
        values["face_transferred"][0, 0] += 1
        np.savez(target, **values)
        # Even a caller recomputing the stream hash cannot evade checkpoint identity.
        manifest["files_sha256"]["checkpoint_final/world-2/state.npz"] = sha(target)
    (path / "windows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    manifest["files_sha256"]["windows.jsonl"] = sha(path / "windows.jsonl")
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, AssertionError)):
        audit_stream(path, cases, PROTOCOL, group="membrane", expected_spec=batch)


def test_prospective_full_plan_has_resume_boundaries():
    from cells.core.grid import EventGrid

    for group in plan.GROUPS:
        batch = plan.cohort(group, CASES)
        steps = [len(EventGrid(w.simulation)) - 1 for w in batch.worlds]
        assert max(steps) > 4 * plan.window_width(group)
    assert sorted(n for names in plan.eager_schedule(CASES).values() for n in names) == sorted(
        c.id for c in CASES
    )


def test_linked_stream_tree_cannot_be_collected(saved, tmp_path):
    path, _, _ = saved
    moved = tmp_path / "outside"
    (path / "worlds").rename(moved)
    (path / "worlds").symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match="Linked"):
        collect_stream(path, cohort=True)
