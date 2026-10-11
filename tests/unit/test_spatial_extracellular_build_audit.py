"""Independent saved-production checks, including deliberately rehashed corruption."""

import json
import shutil
import zipfile
from dataclasses import replace

import numpy as np
import pytest

from cells.core.runner import run
from cells.io import _sha256 as sha
from cells.io import write_run
from cells.models import spatial_extracellular as model
from scripts import spatial_extracellular_production_audit as audit
from tests.spatial_extracellular_fixtures import load_cases, spec_for

PLAN, CASES = load_cases()


def short(case):
    return replace(case, horizon_s=0.00075, controls=(case.controls[0],))


@pytest.fixture(scope="module")
def original(tmp_path_factory):
    case = short(next(c for c in CASES if c.id == "ternary_loop"))
    spec = spec_for(case, samples=[0, 0.00001, 0.00021, 0.000375, 0.00075])
    path = tmp_path_factory.mktemp("spatial-artifacts") / "original"
    write_run(path, run(spec), checkpoint_times=(0.000375,))
    return path, case


@pytest.fixture
def saved(tmp_path, original):
    path, case = original
    shutil.copytree(path, tmp_path / "run")
    return tmp_path / "run", case


def rehash(path):
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files_sha256"]["trajectory.npz"] = sha(path / "trajectory.npz")
    (path / "manifest.json").write_text(json.dumps(manifest))


def test_all_readouts_and_full_cubic_are_independent(original, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Production dynamics/observer used as audit oracle")

    path, case = original
    arrays, result = audit.audit_run(path, case, PLAN)
    assert result["independent_readout_fields"] == 26
    assert result["dense_domain"]["pass"] and result["snapshots"] == 2
    # The normal checkpoint loader runs its production-domain preflight. It is
    # not the independent scientific oracle, which must work with both poisoned.
    monkeypatch.setattr(model, "rhs", forbidden)
    monkeypatch.setattr(model, "observe_history", forbidden)
    spec = audit.load_spec(path / "resolved_config.json")
    independent = audit.inspect_arrays(case, spec, arrays, PLAN)
    assert independent["independent_readout_fields"] == 26


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_all_fourteen_short_prefixes(tmp_path, case):
    case = short(case)
    spec = spec_for(case, samples=[0, 0.00001, 0.00021, 0.000375, 0.00075])
    path = tmp_path / "run"
    write_run(path, run(spec), checkpoint_times=(0.000375,))
    _, report = audit.audit_run(path, case, PLAN, expected_spec=spec)
    assert report["native"]["errors"]["pass"]
    assert report["observed"]["accounting"]["pass"]


@pytest.mark.parametrize("field", sorted(audit.ARRAY_FIELDS))
def test_rehashed_real_state_readout_or_geometry_is_rejected(saved, field):
    path, case = saved
    with np.load(path / "trajectory.npz", allow_pickle=False) as source:
        arrays = dict(source)
    a = arrays[field]
    if field in audit.LAYOUT_FIELDS:
        a.flat[0] = not a.flat[0] if a.dtype == bool else a.flat[0] + 1
    else:
        a.reshape(len(a), -1)[1, 0] += 1
    np.savez(path / "trajectory.npz", **arrays)
    rehash(path)
    with pytest.raises((ValueError, AssertionError)):
        audit.audit_run(path, case, PLAN)


@pytest.mark.parametrize(
    "change", ["nan", "dtype", "shape", "missing", "extra", "padding", "duplicate"]
)
def test_rehashed_malformed_numeric_payload_is_rejected(saved, change):
    path, case = saved
    with np.load(path / "trajectory.npz", allow_pickle=False) as source:
        arrays = dict(source)
    name = "face_transferred"
    if change == "nan":
        arrays[name][1, 0, 0] = np.nan
    elif change == "dtype":
        arrays[name] = arrays[name].astype("float32")
    elif change == "shape":
        arrays[name] = arrays[name][:-1]
    elif change == "missing":
        arrays.pop(name)
    elif change == "extra":
        arrays["invented"] = np.zeros(1)
    elif change == "padding":
        arrays[name][1, 0, -1] = 1
    np.savez(path / "trajectory.npz", **arrays)
    if change == "duplicate":
        with zipfile.ZipFile(path / "trajectory.npz", "a") as archive:
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr(name + ".npy", archive.read(name + ".npy"))
    rehash(path)
    with pytest.raises((ValueError, AssertionError)):
        audit.audit_run(path, case, PLAN)


@pytest.mark.parametrize(
    "change", ["extra", "symlink", "hardlink", "escape", "source", "snapshot_list", "numerics"]
)
def test_rehashed_evidence_provenance_is_rejected(saved, tmp_path, change):
    path, case = saved
    manifest = json.loads((path / "manifest.json").read_text())
    if change == "extra":
        (path / "extra.json").write_text("{}")
    elif change in ("symlink", "hardlink"):
        original = path / "trajectory.npz"
        moved = tmp_path / "external.npz"
        original.rename(moved)
        if change == "symlink":
            original.symlink_to(moved)
        else:
            original.hardlink_to(moved)
    elif change == "escape":
        manifest["files_sha256"]["../external.npz"] = manifest["files_sha256"].pop("trajectory.npz")
    elif change == "source":
        manifest["source_hashes"]["models/spatial_extracellular.py"] = "0" * 64
    elif change == "snapshot_list":
        manifest["snapshots"].append(manifest["snapshots"][0])
    elif change == "numerics":
        manifest["numerics"]["stage_domain"] = "unchecked"
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, AssertionError)):
        audit.audit_run(path, case, PLAN)
