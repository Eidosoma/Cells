"""Reader, geometry-scope and retained-output controls; source solves blocked."""

import json
import struct

import numpy as np
import pytest

from validation.betse import environment_compatible_gauge_saved as module


def fixture():
    coordinates = np.array([[0.5, 0.625], [1.5, 0.625], [0.5, 1.875], [1.5, 1.875]])
    problem = dict(shape=(2, 2), indices=[(0, 0), (0, 1), (1, 0), (1, 1)])
    fields = {
        name: dict(type="numpy_scalar", dtype="<f8", bits=struct.pack("<d", value).hex())
        for name, value in dict(xmin=0, xmax=2, ymin=0, ymax=2.5, delta=1).items()
    }
    fields["xy_cents"] = dict(
        type="array", layout=dict(dtype="<f8", shape=[4, 2]), raw=coordinates.tobytes().hex()
    )
    return fields, problem, coordinates


def test_reader_preserves_retained_nonuniform_extent_without_repair():
    fields, problem, coordinates = fixture()
    before = json.dumps(fields)
    spec = module.grid_spec(fields, problem, "a" * 64)
    assert spec.bounds_m == (0, 2, 0, 2.5) and spec.delta_m == 1
    assert spec.coordinates_m.tobytes() == coordinates.tobytes()
    assert spec.provenance["live_native_owner"] is False and json.dumps(fields) == before


@pytest.mark.parametrize("change", ["dtype", "nonfinite", "coordinate_shape"])
def test_reader_refuses_changed_scalar_or_coordinate_schema(change):
    fields, problem, _ = fixture()
    if change == "dtype":
        fields["delta"]["dtype"] = "<f4"
    elif change == "nonfinite":
        fields["delta"]["bits"] = struct.pack("<d", np.nan).hex()
    else:
        fields["xy_cents"]["layout"]["shape"] = [4, 3]
    with pytest.raises(ValueError):
        module.grid_spec(fields, problem, "a" * 64)


def test_operator_metric_is_explicit_and_does_not_mutate_retained_grid():
    fields, problem, coords = fixture()
    spec = module.grid_spec(fields, problem, "a" * 64)
    other = module.operator_metric_grid(spec)
    assert other.bounds_m == (0, 2, 0, 2) and spec.bounds_m == (0, 2, 0, 2.5)
    assert other.delta_m == spec.delta_m and other.shape == spec.shape
    assert spec.coordinates_m.tobytes() == coords.tobytes()
    assert other.coordinates_m.tobytes() != coords.tobytes()
    assert other.provenance["geometry_repair_or_admission"] is False
    assert other.provenance["retained_physical_geometry"] is False


@pytest.mark.parametrize("shape", [(2, 2), (3, 4)])
def test_probe_roles_and_exact_compatibility(shape):
    probes = module.probes(shape, list(np.ndindex(shape)))
    assert list(probes) == [
        "zero",
        "corner_dipole",
        "opposing_edges",
        "centred_coordinate",
        "incompatible_constant",
    ]
    assert all(sum(v.tolist()) == 0 for k, v in probes.items() if k != "incompatible_constant")
    assert sum(probes["incompatible_constant"].tolist()) == np.prod(shape)
    assert np.count_nonzero(probes["corner_dipole"]) == 2


@pytest.mark.parametrize("operator_metric", [False, True])
def test_declared_scope_refusals_keep_complete_arrays_without_solver(
    tmp_path, monkeypatch, operator_metric
):
    fields, problem, _ = fixture()
    spec = module.grid_spec(fields, problem, "a" * 64)
    baseline = tmp_path / "retained" / "report.json"
    baseline.parent.mkdir()
    baseline.write_text("{}")
    pin = module.prior.pin(baseline)
    problem.update(
        operator=np.arange(16, dtype=float).tolist(),
        inverse=np.arange(16, dtype=float)[::-1].tolist(),
        inputs=[pin],
    )
    monkeypatch.setattr(module, "load_grid", lambda *a: (spec, problem))
    monkeypatch.setattr(module.saved, "blas_state", lambda np: {"software_only": True})
    monkeypatch.setattr(module.saved, "loaded_libraries", lambda: [])
    calls = []

    def refuse(candidate, **kwargs):
        calls.append(candidate.provenance["role"])
        assert kwargs["operator"].ravel().tolist() == problem["operator"]
        raise ValueError("synthetic geometry refusal")

    monkeypatch.setattr(module.gauge, "diagnose", refuse)
    output = tmp_path / "new"
    result = module.run(baseline, pin["sha256"], output, include_operator_metric=operator_metric)
    assert calls == ["retained_grid_data_only"] + (
        ["explicit_uniform_operator_metric_only"] if operator_metric else []
    )
    assert result["physical_admission"] is False and result["numerical_acceptance"] is False
    assert all(v["status"] == "refused" for v in result["scopes"].values())
    for key in ("retained_operator", "retained_inverse", "retained_coordinates", "rhs"):
        row = result["arrays"][key]
        assert module.prior.pin(row["path"])["sha256"] == row["sha256"]
        assert np.load(row["path"], allow_pickle=False).shape == tuple(row["shape"])
    assert module.prior.pin(baseline) == pin


def test_nonboolean_scope_refuses_before_any_reader(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "load_grid", lambda *a: pytest.fail("reader must not enter"))
    with pytest.raises(ValueError, match="explicitly"):
        module.run(tmp_path / "baseline", "a" * 64, tmp_path / "output", include_operator_metric=1)


@pytest.mark.parametrize("source_failure", [False, True])
def test_separate_operator_return_or_failure_is_durable(tmp_path, monkeypatch, source_failure):
    fields, problem, _ = fixture()
    spec = module.grid_spec(fields, problem, "a" * 64)
    baseline = tmp_path / "baseline" / "report.json"
    baseline.parent.mkdir()
    baseline.write_text("{}")
    pin = module.prior.pin(baseline)
    problem.update(
        operator=np.eye(4).ravel().tolist(), inverse=np.eye(4).ravel().tolist(), inputs=[pin]
    )
    monkeypatch.setattr(module, "load_grid", lambda *a: (spec, problem))
    monkeypatch.setattr(module.saved, "blas_state", lambda np: {"software_only": True})
    monkeypatch.setattr(module.saved, "loaded_libraries", lambda: [])
    monkeypatch.setattr(module.saved, "forcing_report", lambda *a: {"software_only": True})
    primary, cause = RuntimeError("synthetic operator failure"), ValueError("synthetic cause")

    def source(candidate, **kwargs):
        if candidate.provenance["role"] == "retained_grid_data_only":
            raise ValueError("retained geometry refused")
        if source_failure:
            raise primary from cause
        return dict(
            compatible_inverse=np.eye(4),
            solutions=(*[np.zeros(4) for _ in range(4)], None),
            numerical_acceptance=False,
            rhs_reports=[{"software_only": True}] * 5,
        )

    monkeypatch.setattr(module.gauge, "diagnose", source)
    output = tmp_path / "new"
    if source_failure:
        with pytest.raises(RuntimeError) as caught:
            module.run(baseline, pin["sha256"], output, include_operator_metric=True)
        assert caught.value is primary and primary.__cause__ is cause
        result = module.prior.read(output / "failure.json")
        assert "synthetic cause" in json.dumps(result["error"])
        assert result["scopes"]["operator_metric_only"]["status"] == "started"
        assert not (output / "report.json").exists()
    else:
        result = module.run(baseline, pin["sha256"], output, include_operator_metric=True)
        row = result["scopes"]["operator_metric_only"]
        assert row["status"] == "diagnosed" and row["solutions"][-1] is None
        assert np.array_equal(np.load(row["inverse"]["path"], allow_pickle=False), np.eye(4))
        assert len(row["solutions"]) == 5 and row["checks"]["numerical_acceptance"] is False
    assert result["scopes"]["retained_grid"]["status"] == "refused"
    assert module.prior.pin(baseline) == pin


@pytest.mark.parametrize("failed_array", ["retained_coordinates", "solution_1"])
def test_later_archive_failure_keeps_earlier_successful_array_descriptors(
    tmp_path, monkeypatch, failed_array
):
    fields, problem, _ = fixture()
    spec = module.grid_spec(fields, problem, "a" * 64)
    baseline = tmp_path / "baseline" / "report.json"
    baseline.parent.mkdir()
    baseline.write_text("{}")
    pin = module.prior.pin(baseline)
    problem.update(
        operator=np.eye(4).ravel().tolist(), inverse=np.eye(4).ravel().tolist(), inputs=[pin]
    )
    monkeypatch.setattr(module, "load_grid", lambda *a: (spec, problem))
    monkeypatch.setattr(module.saved, "blas_state", lambda np: {"software_only": True})
    monkeypatch.setattr(module.saved, "loaded_libraries", lambda: [])
    monkeypatch.setattr(module.saved, "forcing_report", lambda *a: {"software_only": True})
    monkeypatch.setattr(
        module.gauge,
        "diagnose",
        lambda *a, **k: dict(
            compatible_inverse=np.eye(4), solutions=tuple(np.zeros(4) for _ in range(5))
        ),
    )
    writer = module.saved.array_evidence
    primary, cause = OSError("later array write"), RuntimeError("original IO cause")

    def write(np, output, name, value):
        if name == failed_array:
            raise primary from cause
        return writer(np, output, name, value)

    monkeypatch.setattr(module.saved, "array_evidence", write)
    output = tmp_path / "new"
    with pytest.raises(OSError) as caught:
        module.run(baseline, pin["sha256"], output)
    assert caught.value is primary and primary.__cause__ is cause
    result = module.prior.read(output / "failure.json")
    assert {"retained_inverse", "retained_operator"} <= set(result["arrays"])
    for name in ("retained_operator", "retained_inverse"):
        row = result["arrays"][name]
        assert module.prior.pin(row["path"])["sha256"] == row["sha256"]
    if failed_array == "solution_1":
        row = result["scopes"]["retained_grid"]
        assert len(row["solutions"]) == 1
        for item in (row["inverse"], row["solutions"][0]):
            assert module.prior.pin(item["path"])["sha256"] == item["sha256"]
    assert not (output / "report.json").exists()


def test_failed_report_write_does_not_replace_primary_or_cause(tmp_path, monkeypatch):
    primary, cause, capture = RuntimeError("primary"), ValueError("cause"), OSError("disk")
    writer = module.prior.write

    def load(*args):
        raise primary from cause

    def write(path, value):
        if path == tmp_path / "new/failure.json":
            raise capture
        return writer(path, value)

    monkeypatch.setattr(module, "load_grid", load)
    monkeypatch.setattr(module.prior, "write", write)
    with pytest.raises(RuntimeError) as caught:
        module.run(tmp_path / "baseline/report.json", "a" * 64, tmp_path / "new")
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.diagnostic_persistence_error is capture
