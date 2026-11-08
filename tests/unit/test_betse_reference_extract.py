"""BETSE-free checks of the BETSE reference extraction format (synthetic data only)."""

import enum
import json
from pathlib import Path

import numpy as np
import pytest

from validation.betse import betse_reference_extract as ex
from validation.betse import betse_reference_run as runner


def betse_sampled_indices(n_steps, resample, dt):
    """Transcription of the sampling loop in BETSE 1.5.0 sim.py ``_plot_loop``."""
    t_resample, i, indices = resample / dt, 0, []
    while i < n_steps - t_resample:
        i += t_resample
        i = int(i)
        indices.append(i)
    return indices


def write_extract(directory, step_index, n_steps=10, dt=0.5, offset=0.0, units="V"):
    """A tiny complete extraction whose history is a function of the step index."""
    directory.mkdir()
    steps = np.asarray(step_index)
    grid = np.linspace(0, n_steps * dt, n_steps)
    vm = np.outer(steps + 1.0, np.arange(3.0)) + offset
    files = {
        "geometry.npz": ex.write_npz(
            directory / "geometry.npz",
            {
                "cell_centres": (np.arange(4.0).reshape(2, 2), {"units": "m"}),
                "mem_to_cells": (np.array([0, 0, 1]), {"units": "index"}),
            },
        ),
        "sim_history.npz": ex.write_npz(
            directory / "sim_history.npz",
            {"time": (grid[steps], {"units": "s"}), "vm_time": (vm, {"units": units})},
        ),
        "sim_final.npz": ex.write_npz(
            directory / "sim_final.npz", {"vm": (vm[-1] * 0 + offset, {"units": "V"})}
        ),
    }
    schedule = ex.sample_schedule(n_steps, dt, grid[steps])
    manifest = {
        "kind": ex.KIND,
        "status": "complete",
        "files": files,
        "time": {"sim": {"step_index": schedule["step_index"].tolist()}},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    return manifest


def rewrite_manifest(directory, change):
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))


def test_sampling_loop_and_schedule_follow_betse_clock():
    # Default world: INIT 500 x 10 ms sampled every 1 s; SIM 350 x 0.1 ms every 1 ms.
    assert betse_sampled_indices(500, 1.0, 1e-2) == [100, 200, 300, 400]
    sim = betse_sampled_indices(350, 1e-3, 1e-4)
    assert sim[:2] == [10, 20] and sim[-1] == 340 and len(sim) == 34
    # Dense sampling (interval == dt) never records step 0 and ends on the last step.
    assert betse_sampled_indices(10, 1e-4, 1e-4) == list(range(1, 10))

    n_steps, dt = 500, 1e-2
    labels = np.linspace(0, n_steps * dt, n_steps)[[100, 200, 300, 400]]
    schedule = ex.sample_schedule(n_steps, dt, labels)
    assert schedule["step_index"].tolist() == [100, 200, 300, 400]
    np.testing.assert_allclose(schedule["elapsed_after_update_s"], [1.01, 2.01, 3.01, 4.01])
    assert schedule["label_spacing_s"] == pytest.approx(5.0 / 499)
    assert labels[0] == pytest.approx(1.002004008016032)  # label != elapsed update time

    missing = ex.sample_schedule(n_steps, dt, [labels[0], 1.01])
    assert missing["step_index"].tolist() == [100, -1]
    assert np.isnan(missing["elapsed_after_update_s"][1])
    assert ex.json_floats(missing["elapsed_after_update_s"])[1] is None


def test_flatten_ragged_round_trip_keeps_dtype_and_trailing_shape():
    polygons = [np.ones((3, 2)), np.zeros((0, 2)), np.arange(8.0).reshape(4, 2)]
    flat, offsets = ex.flatten_ragged(np.array(polygons, dtype=object))
    assert flat.shape == (7, 2) and offsets.tolist() == [0, 3, 3, 7]
    for i, polygon in enumerate(polygons):
        np.testing.assert_array_equal(flat[offsets[i] : offsets[i + 1]], polygon)

    neighbours, offsets = ex.flatten_ragged([[1, 2], [], [0]])
    assert neighbours.dtype == np.int64 and neighbours.tolist() == [1, 2, 0]
    assert offsets.tolist() == [0, 2, 2, 3]


def test_manifest_matches_written_arrays(tmp_path):
    manifest = write_extract(tmp_path / "x", [3, 6, 9])
    assert ex.verify_extract(tmp_path / "x") == []
    entry = manifest["files"]["sim_history.npz"]["arrays"]["vm_time"]
    assert entry["shape"] == [3, 3] and entry["dtype"] == "<f8" and entry["units"] == "V"
    with np.load(tmp_path / "x/sim_history.npz", allow_pickle=False) as npz:
        assert ex.array_sha256(npz["vm_time"]) == entry["sha256"]


def arrays(manifest, name):
    return manifest["files"][name]["arrays"]


@pytest.mark.parametrize(
    "change, expected",
    [
        (lambda m: arrays(m, "geometry.npz")["cell_centres"].update(shape=[4]), "shape"),
        (lambda m: arrays(m, "geometry.npz")["mem_to_cells"].update(dtype="<i4"), "dtype"),
        (lambda m: arrays(m, "sim_final.npz")["vm"].update(sha256="0" * 64), "array sha"),
        (lambda m: arrays(m, "sim_final.npz")["vm"].pop("units"), "no units"),
        (lambda m: arrays(m, "sim_final.npz").pop("vm"), "only in the file"),
        (lambda m: m["files"]["sim_final.npz"].update(sha256="0" * 64), "file sha256"),
        (lambda m: m.update(status="failed"), "status"),
        (lambda m: m["files"].update({"../x.npz": {}}), "missing"),
    ],
)
def test_verify_reports_manifest_corruption(tmp_path, change, expected):
    write_extract(tmp_path / "x", [3, 6, 9])
    rewrite_manifest(tmp_path / "x", change)
    problems = ex.verify_extract(tmp_path / "x")
    assert any(expected in problem for problem in problems), problems


def test_verify_reports_changed_file_bytes(tmp_path):
    write_extract(tmp_path / "x", [3, 6, 9])
    replacement = tmp_path / "other.npz"
    np.savez(replacement, vm=np.ones(3))  # same name and shape, different values
    (tmp_path / "x/sim_final.npz").write_bytes(replacement.read_bytes())
    problems = ex.verify_extract(tmp_path / "x")
    assert any("file sha256" in p for p in problems)
    assert any("array sha256" in p for p in problems)


def test_write_npz_refuses_object_arrays_and_existing_files(tmp_path):
    with pytest.raises(TypeError):
        ex.write_npz(tmp_path / "a.npz", {"bad": (np.array([[1], [1, 2]], dtype=object), {})})
    ex.write_npz(tmp_path / "b.npz", {"ok": (np.zeros(2), {"units": "1"})})
    with pytest.raises(FileExistsError):
        ex.write_npz(tmp_path / "b.npz", {"ok": (np.zeros(2), {"units": "1"})})


def test_compare_pairs_samples_by_step_index(tmp_path):
    write_extract(tmp_path / "dense", list(range(1, 10)))
    write_extract(tmp_path / "sparse", [3, 6, 9])
    result = ex.compare_extracts(tmp_path / "dense", tmp_path / "sparse")
    sim = result["phases"]["sim"]
    assert result["geometry_identical"] and sim["common_step_indices"] == [3, 6, 9]
    assert sim["history_identical_at_common_steps"] and sim["final_identical"]

    write_extract(tmp_path / "shifted", [3, 6, 9], offset=1e-3)
    shifted = ex.compare_extracts(tmp_path / "dense", tmp_path / "shifted")["phases"]["sim"]
    assert not shifted["history_identical_at_common_steps"] and not shifted["final_identical"]
    assert shifted["history"]["vm_time"]["max_abs_diff"] == pytest.approx(1e-3)


def test_to_plain_accepts_simple_values_only():
    class Kind(enum.Enum):
        FULL = 1

    value = {"a": np.float64(1.5), "b": [np.int64(2), True], 3: Kind.FULL, "c": float("nan")}
    assert ex.to_plain(value) == {"a": 1.5, "b": [2, True], "3": "Kind.FULL", "c": "nan"}
    assert ex.to_plain(np.arange(3)) == [0, 1, 2]
    with pytest.raises(ex.NotPlain):
        ex.to_plain(object())
    with pytest.raises(ex.NotPlain):
        ex.to_plain(np.zeros(1000))


def test_runner_paths_come_from_arguments_and_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CELLS_OUTPUT_ROOT", str(tmp_path))
    assert runner.resolve_out("case/run") == tmp_path / "case/run"
    assert runner.resolve_out("/abs/run") == Path("/abs/run")
    monkeypatch.delenv("CELLS_OUTPUT_ROOT")
    assert runner.output_root() == Path(runner.DEFAULT_OUTPUT_ROOT)
    assert runner.parse_cpus("1,2") == [1, 2] and runner.parse_cpus("0-2,5") == [0, 1, 2, 5]
