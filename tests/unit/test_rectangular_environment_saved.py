"""Retained-grid reader and orchestration controls; real solves are blocked."""

import json
import struct
from types import SimpleNamespace

import numpy as np
import pytest

from validation.betse import rectangular_environment_saved as adapter


def fields():
    x = np.array([[0.0, 1.0, 2.0]] * 3)
    y = np.array([[0.0] * 3, [1.25] * 3, [2.5] * 3])
    points = np.array([[0.5, 0.625], [1.5, 0.625], [0.5, 1.875], [1.5, 1.875]])
    result = {
        name: dict(type="numpy_scalar", dtype="<f8", bits=struct.pack("<d", value).hex())
        for name, value in dict(xmin=0.0, xmax=2.0, ymin=0.0, ymax=2.5, delta=1.0).items()
    }
    for name, array in (("verts_X", x), ("verts_Y", y), ("xy_cents", points)):
        result[name] = dict(
            type="array",
            layout=dict(dtype="<f8", shape=list(array.shape)),
            raw=array.tobytes().hex(),
        )
    return result, dict(shape=(2, 2), indices=list(np.ndindex((2, 2)))), points


def test_complete_tensor_grid_is_retained_without_scalar_spacing_substitution():
    data, problem, points = fields()
    before = json.dumps(data)
    observed, arrays = adapter.observation(data, problem, "input-pin")
    assert observed.bounds_m == (0.0, 2.0, 0.0, 2.5) and observed.delta_m == 1.0
    assert observed.vertices_y_m == (0.0, 1.25, 2.5)
    assert arrays["retained_coordinates"].tobytes() == points.tobytes()
    assert arrays["retained_vertices_y"].shape == (3, 3)
    assert json.dumps(data) == before


@pytest.mark.parametrize(
    "change",
    [
        "x_unsampled_row",
        "y_unsampled_column",
        "coordinate_dtype",
        "scalar_nonfinite",
        "mapping",
        "vertex_shape",
    ],
)
def test_reader_refuses_bad_full_grid_or_metadata(change):
    data, problem, _ = fields()
    if change in ("x_unsampled_row", "y_unsampled_column"):
        key = "verts_X" if change == "x_unsampled_row" else "verts_Y"
        values = (
            np.frombuffer(bytes.fromhex(data[key]["raw"]), dtype=np.float64).copy().reshape(3, 3)
        )
        values[1, 1] += 0.1
        data[key]["raw"] = values.tobytes().hex()
    elif change == "coordinate_dtype":
        data["xy_cents"]["layout"]["dtype"] = "<f4"
    elif change == "scalar_nonfinite":
        data["delta"]["bits"] = struct.pack("<d", np.nan).hex()
    elif change == "mapping":
        problem["indices"][0], problem["indices"][1] = problem["indices"][1], problem["indices"][0]
    else:
        data["verts_X"]["layout"]["shape"] = [2, 3]
    with pytest.raises(ValueError):
        adapter.observation(data, problem, "input-pin")


def setup(tmp_path, monkeypatch):
    data, problem, _ = fields()
    observed, arrays = adapter.observation(data, problem, "test-only")
    baseline = tmp_path / "input" / "report.json"
    baseline.parent.mkdir()
    baseline.write_text(json.dumps(dict(inputs=[])))
    pin = adapter.prior.pin(baseline)
    library = baseline.parent / "synthetic-blas.so"
    library.write_bytes(b"synthetic library metadata only")
    library_pin = adapter.prior.pin(library)
    problem.update(
        operator=np.eye(4).ravel().tolist(), inverse=(np.eye(4) * 7).ravel().tolist(), inputs=[pin]
    )
    monkeypatch.setattr(adapter, "load_grid", lambda *a: (observed, arrays, problem))
    monkeypatch.setattr(adapter.saved, "primitive_bindings", lambda *a: ())
    monkeypatch.setattr(adapter.saved, "blas_state", lambda *a: {"library": library_pin})
    monkeypatch.setattr(adapter.saved, "loaded_libraries", lambda: [])
    calls = []
    grid = SimpleNamespace(
        identity="synthetic-grid",
        shape=(2, 2),
        bounds_m=observed.bounds_m,
        spacing_xy_m=(1.0, 1.25),
        cell_area_m2=1.25,
        coordinates_m=arrays["retained_coordinates"],
        vertices_x_m=np.array(observed.vertices_x_m),
        vertices_y_m=np.array(observed.vertices_y_m),
        laplacian=np.eye(4) * 2,
        compatible_inverse=np.eye(4) / 2,
    )

    def bind(spec):
        calls.append("bind")
        assert spec.bounds_m == observed.bounds_m
        assert spec.coordinates_m.tobytes() == arrays["retained_coordinates"].tobytes()
        return grid

    def solve(rhs, owner):
        assert owner is grid
        calls.append("solve")
        return adapter.field.SolveResult(
            np.arange(20, dtype=np.float64).reshape(5, 4),
            rhs.copy(),
            np.array([True, True, True, True, False]),
            np.ones(5, dtype=bool),
        )

    def diagnose(**kw):
        calls.append("reference")
        assert kw["bounds_m"] == observed.bounds_m
        assert len(kw["probes"]) == 5 and kw["probes"][-1]["name"] == "incompatible_constant"
        return dict(stub=True, numerical_acceptance=False)

    monkeypatch.setattr(adapter.field, "bind", bind)
    monkeypatch.setattr(adapter.field, "solve", solve)
    monkeypatch.setattr(adapter.reference, "diagnose", diagnose)
    return pin, problem, grid, calls


def pins(pin):
    return [adapter.prior.pin(adapter.Path(pin["path"]).parent / "synthetic-blas.so")]


def test_full_adapter_keeps_native_and_new_arrays_separate(tmp_path, monkeypatch):
    pin, problem, grid, calls = setup(tmp_path, monkeypatch)
    result = adapter.run(pin["path"], pin["sha256"], tmp_path / "output", numpy_pins=pins(pin))
    assert calls == ["bind", "solve", "reference"]
    assert result["status"] == "completed_numerical_diagnostic_only"
    assert result["native_inverse_replaced"] is False
    assert result["usable"] == [True, True, True, True, False]
    assert result["refused_rows_still_evaluated"] is True
    assert result["input_mean_subtracted"] is False and result["physical_tissue_admission"] is False
    for name, expected in (
        ("retained_native_operator", problem["operator"]),
        ("retained_native_inverse", problem["inverse"]),
        ("physical_operator", grid.laplacian.ravel()),
        ("physical_inverse", grid.compatible_inverse.ravel()),
    ):
        item = result["arrays"][name]
        assert adapter.prior.pin(item["path"])["sha256"] == item["sha256"]
        assert np.load(item["path"], allow_pickle=False).ravel().tolist() == list(expected)


@pytest.mark.parametrize("stage", ["bind", "solve", "reference", "physical_inverse", "potential"])
def test_failure_retains_earlier_arrays_and_original_return_objects(tmp_path, monkeypatch, stage):
    pin, _, grid, calls = setup(tmp_path, monkeypatch)
    primary, cause = RuntimeError("synthetic " + stage), ValueError("original cause")

    def fail(*args, **kw):
        raise primary from cause

    if stage == "bind":
        monkeypatch.setattr(adapter.field, "bind", fail)
    elif stage == "solve":
        monkeypatch.setattr(adapter.field, "solve", fail)
    elif stage == "reference":
        monkeypatch.setattr(adapter.reference, "diagnose", fail)
    else:
        original = adapter.saved.array_evidence

        def writer(np, out, name, value):
            if name == stage:
                raise primary from cause
            return original(np, out, name, value)

        monkeypatch.setattr(adapter.saved, "array_evidence", writer)
    output = tmp_path / "output"
    with pytest.raises(RuntimeError) as caught:
        adapter.run(pin["path"], pin["sha256"], output, numpy_pins=pins(pin))
    assert caught.value is primary and primary.__cause__ is cause
    report = adapter.prior.read(output / "failure.json")
    assert report["status"] == "failed" and "original cause" in json.dumps(report["error"])
    assert "retained_native_inverse" in report["arrays"]
    if stage != "bind":
        assert primary.rectangular_raw_returns["grid"] is grid
    if stage in ("reference", "potential"):
        assert primary.rectangular_raw_returns["solve"].potential.shape == (5, 4)
        retained = report["failed_return_capture"]
        for name in ("potential", "residual", "rhs_compatible", "finite_result"):
            item = retained["arrays"]["solve_" + name]
            expected = getattr(primary.rectangular_raw_returns["solve"], name)
            assert np.load(item["path"], allow_pickle=False).tobytes() == expected.tobytes()
        assert not retained["errors"]
    if stage == "physical_inverse":
        item = report["failed_return_capture"]["arrays"]["grid_compatible_inverse"]
        assert (
            np.load(item["path"], allow_pickle=False).tobytes() == grid.compatible_inverse.tobytes()
        )
    assert not (output / "report.json").exists()
    for item in report["arrays"].values():
        assert adapter.prior.pin(item["path"])["sha256"] == item["sha256"]


def test_failure_writer_does_not_replace_original_exception(tmp_path, monkeypatch):
    pin, _, _, _ = setup(tmp_path, monkeypatch)
    primary, cause, persistence = RuntimeError("source"), ValueError("cause"), OSError("disk")

    def fail(*a, **k):
        raise primary from cause

    original = adapter.prior.write

    def write(path, data):
        if path.name == "failure.json":
            raise persistence
        return original(path, data)

    monkeypatch.setattr(adapter.field, "bind", fail)
    monkeypatch.setattr(adapter.prior, "write", write)
    with pytest.raises(RuntimeError) as caught:
        adapter.run(pin["path"], pin["sha256"], tmp_path / "output", numpy_pins=pins(pin))
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.rectangular_persistence_error is persistence


def test_output_overlap_refuses_before_source_or_directory_creation(tmp_path, monkeypatch):
    pin, _, _, calls = setup(tmp_path, monkeypatch)
    output = tmp_path / "input" / "forbidden"
    with pytest.raises(ValueError, match="overlap"):
        adapter.run(pin["path"], pin["sha256"], output, numpy_pins=[])
    assert not output.exists() and not calls


def test_changed_input_pin_refuses_before_source_or_output(tmp_path, monkeypatch):
    pin, _, _, calls = setup(tmp_path, monkeypatch)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="baseline"):
        adapter.run(pin["path"], "0" * 64, output, numpy_pins=[])
    assert not output.exists() and not calls


def test_missing_declared_blas_refuses_before_binding(tmp_path, monkeypatch):
    pin, _, _, calls = setup(tmp_path, monkeypatch)
    output = tmp_path / "output"
    with pytest.raises(ValueError, match="BLAS"):
        adapter.run(pin["path"], pin["sha256"], output, numpy_pins=[])
    assert not calls
    assert adapter.prior.read(output / "failure.json")["stage"] == "load_grid"


def test_one_failed_fallback_buffer_does_not_lose_remaining_returns(tmp_path, monkeypatch):
    pin, _, _, _ = setup(tmp_path, monkeypatch)
    primary, capture = RuntimeError("archive potential"), OSError("fallback potential")
    original = adapter.saved.array_evidence

    def writer(np, out, name, value):
        if name == "potential":
            raise primary
        if name == "failed_solve_potential":
            raise capture
        return original(np, out, name, value)

    monkeypatch.setattr(adapter.saved, "array_evidence", writer)
    output = tmp_path / "output"
    with pytest.raises(RuntimeError) as caught:
        adapter.run(pin["path"], pin["sha256"], output, numpy_pins=pins(pin))
    assert caught.value is primary
    retained = adapter.prior.read(output / "failure.json")["failed_return_capture"]
    assert [row["field"] for row in retained["errors"]] == ["solve_potential"]
    assert "fallback potential" in json.dumps(retained["errors"])
    for name in ("residual", "rhs_compatible", "finite_result"):
        item = retained["arrays"]["solve_" + name]
        expected = getattr(primary.rectangular_raw_returns["solve"], name)
        assert np.load(item["path"], allow_pickle=False).tobytes() == expected.tobytes()


@pytest.mark.parametrize("failure", ["retained_coordinates", "reference.json"])
def test_loaded_inputs_and_reference_have_independent_durable_fallback(
    tmp_path, monkeypatch, failure
):
    pin, _, _, _ = setup(tmp_path, monkeypatch)
    original_write, original_array = adapter.prior.write, adapter.saved.array_evidence
    primary = RuntimeError("synthetic archive failure")

    def write(path, value):
        if path.name == failure:
            raise primary
        return original_write(path, value)

    def array(np, output, name, value):
        if name == failure:
            raise primary
        return original_array(np, output, name, value)

    monkeypatch.setattr(adapter.prior, "write", write)
    monkeypatch.setattr(adapter.saved, "array_evidence", array)
    output = tmp_path / "output"
    with pytest.raises(RuntimeError) as caught:
        adapter.run(pin["path"], pin["sha256"], output, numpy_pins=pins(pin))
    assert caught.value is primary
    retained = adapter.prior.read(output / "failure.json")["failed_return_capture"]
    assert not retained["errors"]
    assert len(retained["arrays"]) >= 5
    for item in retained["arrays"].values():
        assert adapter.prior.pin(item["path"])["sha256"] == item["sha256"]
    if failure == "reference.json":
        assert adapter.prior.read(retained["reference"]["path"])["stub"] is True


@pytest.mark.parametrize("location", ["baseline", "sidecar", "runtime"])
def test_preparation_overlap_refuses_before_any_snapshot(tmp_path, monkeypatch, location):
    pin, _, _, _ = setup(tmp_path, monkeypatch)
    sidecar = tmp_path / "sidecars" / "array.bin"
    sidecar.parent.mkdir()
    sidecar.write_bytes(b"retained")
    baseline = adapter.Path(pin["path"])
    baseline.write_text(json.dumps(dict(inputs=[adapter.prior.pin(sidecar)])))
    pin = adapter.prior.pin(baseline)
    runtime = tmp_path / "runtime" / "library.so"
    runtime.parent.mkdir()
    runtime.write_bytes(b"runtime")
    declaration = tmp_path / "analysis.json"
    declaration.write_text(
        json.dumps(
            dict(
                baseline=pin,
                numpy_pins=[adapter.prior.pin(runtime)],
                scope="retained_physical_rectangle_diagnostic",
            )
        )
    )
    parent = dict(baseline=baseline.parent, sidecar=sidecar.parent, runtime=runtime.parent)[
        location
    ]
    output = parent / "forbidden"

    def forbidden(*a, **k):
        pytest.fail("Snapshot preparation must not be reached")

    monkeypatch.setattr(adapter.runner.snapshot, "freeze", forbidden)
    with pytest.raises(ValueError, match="overlap"):
        adapter.runner.prepare(output, False, suite="saved", analysis_inputs=declaration)
    assert not output.exists()


def test_input_hash_is_of_decoded_bytes_and_replacement_refuses(tmp_path, monkeypatch):
    path = tmp_path / "declaration.json"
    path.write_bytes(b'{"version":1}')
    pin, value = adapter.runner.bound_json(path)
    assert value == {"version": 1} and pin == adapter.prior.pin(path)
    original = adapter.runner.json.loads

    def replace_after_decode(raw):
        value = original(raw)
        path.write_bytes(b'{"version":2}')
        return value

    monkeypatch.setattr(adapter.runner.json, "loads", replace_after_decode)
    with pytest.raises(ValueError, match="changed while decoding"):
        adapter.runner.bound_json(path)
