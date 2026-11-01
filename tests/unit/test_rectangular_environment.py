"""Small algebra/conservation checks of the separate physical-grid convention."""

import json
import os
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_native_grid_metric_audit as metric
from cells.processes import rectangular_environment as field


def save(name, *, grid=None, **data):
    if folder := os.environ.get("CELLS_RECTANGULAR_EVIDENCE"):
        path = Path(folder) / name
        path.mkdir(parents=True, exist_ok=False)
        if grid is not None:
            data.update(
                grid_identity=grid.identity, shape=grid.shape, spacing_xy_m=grid.spacing_xy_m
            )
            for label in (
                "laplacian",
                "compatible_inverse",
                "coordinates_m",
                "vertices_x_m",
                "vertices_y_m",
            ):
                np.save(path / (label + ".npy"), getattr(grid, label), allow_pickle=False)
        arrays = {name: value for name, value in data.items() if type(value) is np.ndarray}
        for key, value in arrays.items():
            np.save(path / (key + ".npy"), value, allow_pickle=False)
            data[key] = dict(file=key + ".npy", shape=value.shape, dtype=value.dtype.str)
        (path / "report.json").write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def spec(shape=(2, 2), *, dx=1.0, dy=1.25):
    ny, nx = shape
    vx, vy = np.arange(nx + 1, dtype=np.float64) * dx, np.arange(ny + 1, dtype=np.float64) * dy
    points = np.array(
        [[(vx[j] + vx[j + 1]) / 2, (vy[i] + vy[i + 1]) / 2] for i, j in np.ndindex(shape)]
    )
    return field.GridSpec(
        tuple("cell:" + str(k) for k in range(ny * nx)),
        shape,
        (0.0, float(vx[-1]), 0.0, float(vy[-1])),
        points,
        vx,
        vy,
        {"kind": "declared small arithmetic fixture, no native or tissue authority"},
    )


def exact_four(cx, cy, rhs):
    # Independent explicit four-node constrained system; no production stencil
    # builder, inverse, rank detection or floating elimination is used.
    rows = [
        [-cx - cy, cx, cy, 0],
        [cx, -cx - cy, 0, cy],
        [cy, 0, -cx - cy, cx],
        [0, cy, cx, -cx - cy],
    ]
    augmented = [
        [Fraction(v) for v in row] + [Fraction(b)] for row, b in zip(rows, rhs, strict=True)
    ]
    augmented[-1] = [Fraction(1)] * 4 + [Fraction(0)]
    for j in range(4):
        pivot = next(i for i in range(j, 4) if augmented[i][j])
        augmented[j], augmented[pivot] = augmented[pivot], augmented[j]
        divisor = augmented[j][j]
        augmented[j] = [v / divisor for v in augmented[j]]
        for i in range(4):
            if i != j:
                coefficient = augmented[i][j]
                augmented[i] = [
                    v - coefficient * w for v, w in zip(augmented[i], augmented[j], strict=True)
                ]
    return tuple(row[-1] for row in augmented)


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (1.0, 1.25), (2.0, 1.0)])
def test_anisotropic_solutions_match_independent_exact_constrained_system(dx, dy):
    declared = spec(dx=dx, dy=dy)
    grid = field.bind(declared)
    rhs = np.array([1.0, -1.0, 2.0, -2.0])
    exact = exact_four(1 / Fraction(dx) ** 2, 1 / Fraction(dy) ** 2, (1, -1, 2, -2))
    result = field.solve(rhs, grid)
    expected = np.array([float(v) for v in exact])
    save(
        f"rational-{dx}-{dy}",
        grid=grid,
        rhs=rhs,
        potential=result.potential,
        residual=result.residual,
        exact=[str(v) for v in exact],
    )
    assert result.usable
    np.testing.assert_allclose(result.potential, expected, rtol=0, atol=2e-14)
    np.testing.assert_allclose(result.residual, 0.0, rtol=0, atol=4e-14)
    assert abs(result.potential.sum()) < 2e-14


def test_retained_anisotropic_observation_uses_physical_spacing_without_repair():
    declared = spec()
    raw = metric.GridObservation(
        declared.shape,
        declared.bounds_m,
        1.0,
        tuple(map(tuple, declared.coordinates_m.tolist())),
        tuple(np.ndindex(declared.shape)),
        tuple(declared.vertices_x_m.tolist()),
        tuple(declared.vertices_y_m.tolist()),
        "synthetic source-shaped observation only",
    )
    audit = metric.audit(raw, boundaries=tuple((side, "flux") for side in metric.SIDES))
    before = audit.record_json
    assert not audit.record["uniform_metric_passed"]
    with pytest.raises(metric.UniformMetricRejected):
        metric.require_uniform_metric(audit)
    converted = field.spec_from_observation(audit, environment_ids=declared.environment_ids)
    grid = field.bind(converted)
    save(
        "retained-metric", grid=grid, audit_identity=audit.identity, native_scalar_delta=raw.delta_m
    )
    assert grid.spacing_xy_m == (1.0, 1.25)
    assert grid.laplacian[0, 2] == 1 / 1.25**2
    assert grid.laplacian[0, 2] != 1 / raw.delta_m**2
    assert grid.coordinates_m.tobytes() == declared.coordinates_m.tobytes()
    assert grid.vertices_y_m.tobytes() == declared.vertices_y_m.tobytes()
    assert audit.record_json == before and audit.observation is raw
    assert converted.provenance["native_source_equivalence"] is False


def test_flux_conservation_energy_and_both_nullspace_products():
    grid = field.bind(spec((3, 4), dx=2.0, dy=1.0))
    value = np.array([1, -2, 5, 3, -1, 4, 0, 2, 6, -3, -4, -2], dtype=np.float64)
    applied = field.apply(value, grid)
    energy = 0.0
    plane = value.reshape(grid.shape)
    energy += grid.cell_area_m2 / 4 * np.sum(np.diff(plane, axis=1) ** 2)
    energy += grid.cell_area_m2 * np.sum(np.diff(plane, axis=0) ** 2)
    p = np.eye(12) - np.ones((12, 12)) / 12
    save("conservation-energy", grid=grid, value=value, applied=applied, edge_energy=float(energy))
    assert grid.cell_area_m2 * applied.sum() == 0.0
    assert -grid.cell_area_m2 * np.dot(value, applied) == energy
    np.testing.assert_array_equal(field.apply(np.ones(12), grid), np.zeros(12))
    np.testing.assert_allclose(grid.laplacian @ grid.compatible_inverse, p, rtol=0, atol=2e-14)
    np.testing.assert_allclose(grid.compatible_inverse @ grid.laplacian, p, rtol=0, atol=2e-14)
    np.testing.assert_allclose(grid.compatible_inverse.sum(axis=0), 0, rtol=0, atol=2e-14)
    np.testing.assert_allclose(grid.compatible_inverse.sum(axis=1), 0, rtol=0, atol=2e-14)


def test_batch_refusal_preserves_original_rhs_and_does_not_hide_constant_forcing():
    grid = field.bind(spec())
    rhs = np.array(
        [[1.0, -1.0, 2.0, -2.0], [0.0] * 4, [1.0] * 4, [np.nan, 0, 0, 0], [np.inf, 0, 0, 0]]
    )
    before = rhs.tobytes()
    with np.errstate(invalid="ignore"):
        result = field.solve(rhs, grid)
    save(
        "batch-refusals",
        grid=grid,
        rhs=rhs,
        potential=result.potential,
        residual=result.residual,
        usable=result.usable,
    )
    np.testing.assert_array_equal(result.usable, [True, True, False, False, False])
    assert rhs.tobytes() == before
    # A projected source would hide this residual and falsely accept this row.
    np.testing.assert_allclose(result.residual[2], -np.ones(4), rtol=0, atol=2e-14)
    np.testing.assert_array_equal(result.potential[1], np.zeros(4))
    np.testing.assert_allclose(
        result.potential[0], field.solve(rhs[0], grid).potential, rtol=0, atol=2e-14
    )


def test_micrometre_units_and_translation_preserve_metric_solution():
    base = spec(dx=2.0, dy=1.0)
    small = spec(dx=2e-6, dy=1e-6)
    shifted = replace(
        base,
        bounds_m=(8.0, 12.0, -4.0, -2.0),
        coordinates_m=base.coordinates_m + np.array([8.0, -4.0]),
        vertices_x_m=base.vertices_x_m + 8.0,
        vertices_y_m=base.vertices_y_m - 4.0,
    )
    a, b = field.bind(base), field.bind(small)
    translated = field.bind(shifted)
    rhs = np.array([1.0, -1.0, 0.0, 0.0])
    large_result, small_result = field.solve(rhs, a), field.solve(rhs, b)
    save("units", grid=b, rhs=rhs, potential=small_result.potential)
    np.testing.assert_allclose(
        small_result.potential, large_result.potential * 1e-12, rtol=3e-14, atol=0
    )
    np.testing.assert_array_equal(translated.laplacian, a.laplacian)
    np.testing.assert_array_equal(field.solve(rhs, translated).potential, large_result.potential)


@pytest.mark.parametrize("case", ["cross_axis", "unresolved", "duplicate", "permuted"])
def test_translated_axes_do_not_widen_coordinate_or_owner_gates(case, monkeypatch):
    incoming = spec(dy=1.0)
    shift = float(2**50 if case == "unresolved" else 2**40)
    incoming = replace(
        incoming,
        bounds_m=(shift, shift + 2.0, 0.0, 2.0),
        coordinates_m=incoming.coordinates_m + np.array([shift, 0.0]),
        vertices_x_m=incoming.vertices_x_m + shift,
    )
    if case == "cross_axis":
        incoming.coordinates_m[:, 1] += 0.01
    elif case == "unresolved":
        incoming.coordinates_m[:, 1] = 10.0
    elif case == "duplicate":
        incoming.coordinates_m[1] = incoming.coordinates_m[0]
    else:
        incoming.coordinates_m[[0, 1]] = incoming.coordinates_m[[1, 0]]
    monkeypatch.setattr(np.linalg, "inv", lambda *a: pytest.fail("No inverse for invalid centres"))
    with pytest.raises(ValueError) as caught:
        field.bind(incoming)
    save("translated-" + case, coordinates=incoming.coordinates_m, error=str(caught.value))


def test_bound_arrays_cannot_be_rearmed_and_input_mutation_does_not_change_binding():
    incoming = spec()
    grid = field.bind(incoming)
    before = grid.coordinates_m.tobytes()
    incoming.coordinates_m[0, 0] += 0.2
    for name in (
        "coordinates_m",
        "vertices_x_m",
        "vertices_y_m",
        "laplacian",
        "compatible_inverse",
    ):
        with pytest.raises(ValueError):
            getattr(grid, name).setflags(write=True)
    assert grid.coordinates_m.tobytes() == before
    save("immutability", grid=grid)


@pytest.mark.parametrize(
    "change",
    [
        "shape",
        "ids",
        "coordinate_order",
        "vertices",
        "irregular",
        "nonfinite",
        "dtype",
        "bounds",
        "provenance",
        "underflow",
    ],
)
def test_invalid_metric_refuses_before_inverse(change, monkeypatch):
    incoming = spec()
    if change == "shape":
        incoming = replace(incoming, shape=(1, 4))
    elif change == "ids":
        incoming = replace(incoming, environment_ids=("same",) * 4)
    elif change == "coordinate_order":
        incoming.coordinates_m[[0, 1]] = incoming.coordinates_m[[1, 0]]
    elif change == "vertices":
        incoming.vertices_y_m[0] -= 0.01
    elif change == "irregular":
        incoming.vertices_y_m[1] += 0.1
    elif change == "nonfinite":
        incoming.coordinates_m[0, 0] = np.nan
    elif change == "dtype":
        incoming = replace(incoming, coordinates_m=incoming.coordinates_m.astype(np.float32))
    elif change == "bounds":
        incoming = replace(incoming, bounds_m=(0.0, -2.0, 0.0, 2.5))
    elif change == "provenance":
        incoming = replace(incoming, provenance={})
    else:
        incoming = spec(dx=1e-200, dy=1e-200)
    monkeypatch.setattr(
        np.linalg, "inv", lambda *a, **k: pytest.fail("No inverse after invalid metric")
    )
    with pytest.raises(ValueError) as caught:
        field.bind(incoming)
    save("invalid-" + change, error=str(caught.value))


def test_observation_adapter_refuses_mixed_boundary_or_inconsistent_map():
    incoming = spec()
    raw = metric.GridObservation(
        incoming.shape,
        incoming.bounds_m,
        1.0,
        tuple(map(tuple, incoming.coordinates_m.tolist())),
        tuple(np.ndindex(incoming.shape)),
        tuple(incoming.vertices_x_m.tolist()),
        tuple(incoming.vertices_y_m.tolist()),
    )
    for label, sample, boundaries in (
        ("boundary", raw, (("N", "value"), ("S", "flux"), ("E", "flux"), ("W", "flux"))),
        (
            "mapping",
            replace(raw, map_ij2k=((0, 1), (0, 0), (1, 0), (1, 1))),
            tuple((s, "flux") for s in metric.SIDES),
        ),
    ):
        audit = metric.audit(sample, boundaries=boundaries)
        with pytest.raises(ValueError) as caught:
            field.spec_from_observation(audit, environment_ids=incoming.environment_ids)
        save("adapter-" + label, error=str(caught.value), audit_identity=audit.identity)


def test_nonfinite_inverse_failure_does_not_issue_binding(monkeypatch):
    def broken(*args):
        return np.full((4, 4), np.nan)

    monkeypatch.setattr(np.linalg, "inv", broken)
    with pytest.raises(ValueError, match="finite compatible inverse"):
        field.bind(spec())


def test_field_axis_and_precision_refusals():
    grid = field.bind(spec())
    for data in (np.zeros(3), np.zeros(4, dtype=np.float32), np.array(1.0)):
        with pytest.raises(ValueError):
            field.solve(data, grid)


@pytest.mark.parametrize(
    "change", ["valid", "foreign_project", "missing_required", "external_hash", "affinity"]
)
def test_runner_producer_origins_and_runtime_hashes_are_required(tmp_path, change):
    import sys

    from validation.betse import rectangular_environment_validation as runner

    frozen = tmp_path / "source"
    source, loaded = {"files": {}}, {}
    for i, name in enumerate(runner.FILES):
        path = frozen / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic runtime binding:" + name)
        digest = runner.snapshot.digest(path)
        source["files"][name] = {"sha256": digest}
        loaded["cells.synthetic_" + str(i)] = {"path": str(path), "sha256": digest}
    external = tmp_path / "external.py"
    external.write_text("synthetic external dependency")
    loaded["external"] = {"path": str(external), "sha256": runner.snapshot.digest(external)}
    executable = Path(sys.executable).resolve()
    data = dict(
        loaded_files=loaded,
        measured_cpu_affinity=[2],
        executable=dict(path=str(executable), sha256=runner.snapshot.digest(executable)),
    )
    if change == "foreign_project":
        other = tmp_path / "old-snapshot.py"
        other.write_bytes(Path(loaded["cells.synthetic_0"]["path"]).read_bytes())
        loaded["cells.synthetic_0"]["path"] = str(other)
    elif change == "missing_required":
        del loaded["cells.synthetic_0"]
    elif change == "external_hash":
        external.write_text("changed after recorded runtime inventory")
    elif change == "affinity":
        data["measured_cpu_affinity"] = [3]
    if change == "valid":
        assert len(runner.verify_runtime(frozen, source, data, [2])) == len(runner.FILES)
    else:
        with pytest.raises(ValueError) as caught:
            runner.verify_runtime(frozen, source, data, [2])
        save("runtime-" + change, error=str(caught.value))
