"""Synthetic exact-grid algebra and saved-byte contracts; no source execution."""

import copy
import hashlib
import importlib.abc
import json
import math
import struct
import sys
from dataclasses import dataclass

import pytest

from validation.betse import native_single_cell_poisson_algebra as algebra


@pytest.fixture(autouse=True)
def no_science():
    attempted = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {
                "cells",
                "betse",
                "numpy",
                "scipy",
                "PIL",
                "jax",
                "jaxlib",
            }:
                attempted.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    finder = Block()
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        sys.meta_path.remove(finder)
    assert attempted == []


def flux():
    # Exact negative cycle-graph Laplacian and Moore-Penrose inverse, delta=2.
    b = [-2, 1, 1, 0, 1, -2, 0, 1, 1, 0, -2, 1, 0, 1, 1, -2]
    c16 = [-5, 1, 1, 3, 1, -5, 3, 1, 1, 3, -5, 1, 3, 1, 1, -5]
    return dict(
        shape=(2, 2),
        indices=[(0, 0), (0, 1), (1, 0), (1, 1)],
        delta=2.0,
        operator=[v / 4 for v in b],
        inverse=[v / 4 for v in c16],
        boundary="flux",
    )


def value():
    # Exact block-triangular9x9 inverse: eight prescribed rows and one interior.
    a, p = [0.0] * 81, [0.0] * 81
    for i in range(9):
        if i != 4:
            a[9 * i + i], p[9 * i + i] = 0.25, 4.0
    a[40], p[40] = -1.0, -1.0
    for neighbour in (1, 3, 5, 7):
        a[36 + neighbour], p[36 + neighbour] = 0.25, 1.0
    return dict(
        shape=(3, 3),
        indices=[(i // 3, i % 3) for i in range(9)],
        delta=2.0,
        operator=a,
        inverse=p,
        boundary="value",
    )


@pytest.mark.parametrize("fixture", [flux, value])
def test_exact_analytic_inverses_have_zero_product_and_stencil_residuals(fixture):
    report = algebra.diagnose(**fixture())
    assert report["products_available"]
    for key in (
        "dimensionless_stencil_error_inf",
        "dimensionless_stencil_error_max_abs",
        "operator_inverse_residual_inf",
        "inverse_operator_residual_inf",
        "normalized_operator_inverse_residual",
        "normalized_inverse_operator_residual",
    ):
        assert report[key] == 0.0, key
    assert report["off_stencil_nonzeros"] == report["missing_stencil_nonzeros"] == 0
    assert report["numerical_acceptance"] is False and report["new_acceptance_tolerance"] is None


def test_value_inverse_is_allowed_to_be_nonsymmetric():
    data = value()
    assert data["inverse"][4 * 9 + 1] != data["inverse"][1 * 9 + 4]
    assert algebra.diagnose(**data)["inverse_operator_residual_inf"] == 0.0


def test_flux_constant_nullspace_shift_is_detected_even_with_exact_products():
    data = flux()
    exact = algebra.diagnose(**data)
    assert exact["constant_mode"]["inverse_row_sum_inf"] == 0.0
    # Add J/8 to the dimensionless pseudoinverse, hence J/2 at delta=2.
    data["inverse"] = [v + 0.5 for v in data["inverse"]]
    shifted = algebra.diagnose(**data)
    assert (
        shifted["operator_inverse_residual_inf"] == shifted["inverse_operator_residual_inf"] == 0.0
    )
    assert (
        shifted["constant_mode"]["inverse_row_sum_inf"]
        == shifted["constant_mode"]["inverse_column_sum_inf"]
        == 2.0
    )
    assert shifted["constant_mode"]["inverse_row_sum_relative"] == 4 / 7
    assert shifted["numerical_acceptance"] is False


@pytest.mark.parametrize(
    "fixture,permutation", [(flux, [3, 0, 2, 1]), (value, [8, 4, 2, 5, 1, 3, 6, 0, 7])]
)
def test_row_mapping_permutation_changes_both_axes_without_changing_algebra(fixture, permutation):
    data = fixture()
    n = len(permutation)
    data["indices"] = [data["indices"][i] for i in permutation]
    for name in ("operator", "inverse"):
        previous = data[name]
        data[name] = [previous[i * n + j] for i in permutation for j in permutation]
    report = algebra.diagnose(**data)
    assert report["operator_inverse_residual_inf"] == report["inverse_operator_residual_inf"] == 0.0


def test_scaling_spacing_keeps_the_projector_and_dimensionless_stencil():
    data = flux()
    data["delta"] = 0.5
    data["operator"] = [v * 16 for v in data["operator"]]
    data["inverse"] = [v / 16 for v in data["inverse"]]
    report = algebra.diagnose(**data)
    assert (
        report["dimensionless_stencil_error_inf"] == report["operator_inverse_residual_inf"] == 0.0
    )


@pytest.mark.parametrize("changed", ["operator", "inverse", "missing"])
def test_changed_coefficients_or_inverse_are_reported_without_silent_repair(changed):
    data = flux()
    if changed == "missing":
        data["operator"][1] = 0.0
    else:
        data[changed][0] += 0.125
    before = copy.deepcopy(data)
    report = algebra.diagnose(**data)
    assert data == before
    assert report["operator_inverse_residual_inf"] > 0
    assert report["inverse_operator_residual_inf"] > 0
    if changed != "inverse":
        assert report["dimensionless_stencil_error_inf"] > 0
    assert report["numerical_acceptance"] is False


def test_unexpected_dense_entry_is_not_ignored_in_sparse_product():
    data = flux()
    data["operator"][3] = 1e-30
    report = algebra.diagnose(**data)
    assert report["off_stencil_nonzeros"] == 1
    assert report["products_available"] is False
    assert "operator_inverse_residual_inf" not in report
    assert report["off_stencil_examples"] == [dict(row=0, column=3, value=1e-30)]


@pytest.mark.parametrize("change", ["duplicate", "outside", "missing", "bool", "float"])
def test_invalid_map_cannot_be_treated_as_a_connected_grid(change):
    data = flux()
    if change == "missing":
        data["indices"].pop()
    else:
        data["indices"][0] = {
            "duplicate": (0, 1),
            "outside": (2, 0),
            "bool": (False, 0),
            "float": (0.0, 0),
        }[change]
    with pytest.raises(ValueError):
        algebra.diagnose(**data)


@pytest.mark.parametrize("shape", [(1, 4), (2, 1), (0, 4), (True, 4), (26, 25), (2,), (2.0, 2)])
def test_grid_bounds_remain_explicit(shape):
    data = flux()
    data["shape"] = shape
    with pytest.raises(ValueError):
        algebra.diagnose(**data)


@pytest.mark.parametrize(
    "name,value",
    [
        ("delta", 0.0),
        ("delta", -1.0),
        ("delta", 1e-300),
        ("delta", 1e300),
        ("delta", float("nan")),
        ("operator", float("inf")),
        ("inverse", float("nan")),
        ("inverse", True),
    ],
)
def test_nonfinite_unrepresentable_and_wrong_scalar_types_refuse(name, value):
    data = flux()
    if name == "delta":
        data[name] = value
    else:
        data[name][0] = value
    with pytest.raises(ValueError):
        algebra.diagnose(**data)


def test_full_default_grid_uses_bounded_sparse_products_but_does_not_claim_an_inverse():
    width, n = 25, 625
    a = [0.0] * (n * n)
    for row in range(n):
        i, j = divmod(row, width)
        if i in (0, width - 1) or j in (0, width - 1):
            a[row * n + row] = 0.25
        else:
            a[row * n + row] = -1.0
            for neighbour in (row - width, row + width, row - 1, row + 1):
                a[row * n + neighbour] = 0.25
    report = algebra.diagnose(
        shape=(width, width),
        indices=[divmod(i, width) for i in range(n)],
        delta=2.0,
        operator=a,
        inverse=[0.0] * (n * n),
        boundary="value",
    )
    assert report["expected_nonzeros"] == report["observed_nonzeros"] == 2741
    assert report["dimensionless_stencil_error_inf"] == 0.0
    assert report["operator_inverse_residual_inf"] == report["inverse_operator_residual_inf"] == 1.0
    assert report["numerical_acceptance"] is False


@dataclass
class Array:
    values: list
    shape: tuple
    dtype: str = "<f8"


def wire(value):
    """Independent small fixture encoder, never a source owner or solver."""
    columns = {}

    def visit(v):
        if type(v) is Array:
            name = "fixture_" + str(len(columns))
            fmt = v.dtype[0] + ("d" if v.dtype[1] == "f" else "q")
            raw = b"".join(struct.pack(fmt, x) for x in v.values)
            strides = [8 * math.prod(v.shape[i + 1 :]) for i in range(len(v.shape))]
            layout = dict(
                dtype=v.dtype,
                shape=list(v.shape),
                strides_bytes=strides,
                C_contiguous=True,
                F_contiguous=False,
            )
            columns[name] = dict(
                __ndarray__=True,
                dtype=v.dtype,
                shape=list(v.shape),
                strides=strides,
                raw_bytes_hex=raw.hex(),
            )
            return dict(
                type="array", layout=layout, column=name, sha256=hashlib.sha256(raw).hexdigest()
            )
        if type(v) is float:
            return dict(type="float", bits=struct.pack("<d", v).hex())
        if type(v) is dict:
            return dict(type="dict", values=[[visit(k), visit(x)] for k, x in v.items()])
        if type(v) in (list, tuple):
            return dict(type=type(v).__name__, values=[visit(x) for x in v])
        return dict(type=type(v).__name__, value=v)

    tree = visit(value)
    return dict(tree=tree, columns=columns)


def reference():
    data = flux()
    parent = dict(
        caller=dict(grid_len=4),
        grid=dict(
            cents_shape=(2, 2),
            map_ij2k_cents=Array([0, 0, 0, 1, 1, 0, 1, 1], (4, 2), "<i8"),
            delta=2.0,
        ),
        mesh={},
        parameters={},
        trees=[],
    )
    # All four points are prescribed in the all-value2x2 operator.
    v_a = [0.25 if i == j else 0.0 for i in range(4) for j in range(4)]
    v_p = [4.0 if i == j else 0.0 for i in range(4) for j in range(4)]
    results, helpers = [], []
    for name, a, p in [
        (algebra.compare.POISSON_STAGES[0], v_a, v_p),
        (algebra.compare.POISSON_STAGES[1], data["operator"], data["inverse"]),
    ]:
        aa, pp = Array(a, (4, 4)), Array(p, (4, 4))
        results.append((name, (aa, pp)))
        helpers += [(name, "zeros", Array([v * 4 for v in a], (4, 4))), (name, "pinv", pp)]
    return dict(
        status="source_completed",
        source_error=None,
        capture_error=None,
        stop_after="lapENV_P_inv",
        environment=dict(cache=wire(parent)),
        poisson=dict(cache=dict(outputs=wire(dict(results=results, helpers=helpers)))),
    )


def test_saved_wire_values_are_diagnosed_without_issuing_source_owners():
    report = algebra.analyse(reference())
    assert [r["boundary"] for r in report["operators"]] == ["value", "flux"]
    assert all(r["operator_inverse_residual_inf"] == 0.0 for r in report["operators"])
    assert report["native_source_executions"] == 0 and report["new_acceptance_tolerance"] is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("status", "failed"),
        ("source_error", {}),
        ("capture_error", {}),
        ("stop_after", "make_maskM"),
    ],
)
def test_failed_or_incomplete_reference_markers_refuse(key, value):
    raw = reference()
    raw[key] = value
    with pytest.raises(ValueError):
        algebra.analyse(raw)


def packet(tmp_path, monkeypatch):
    monkeypatch.setattr(algebra.prior, "BASE", tmp_path)
    root = tmp_path / "reference"
    root.mkdir()
    algebra.payload.write(root / "native.json", reference())
    comparison = dict(
        kind="cells.single_cell_saved_poisson_exact_comparison@1",
        exact_match=True,
        mismatches=[],
        stop_after="lapENV_P_inv",
        cache_pairs_compared=22,
        streams_compared=8,
        poisson_boundaries_compared=4,
        poisson_stages_compared=2,
        poisson_output_cache_pairs_compared=4,
        poisson_environment_checks=4,
    )
    algebra.prior.write(root / "comparison.json", comparison)
    worker = dict(
        status="exact_source_match",
        accepted_source_comparisons=1,
        native_executions=1,
        attempted_model_imports=[],
        physical_geometry_admitted=False,
        stop_after="lapENV_P_inv",
        native=algebra.prior.pin(root / "native.json"),
        comparison=algebra.prior.pin(root / "comparison.json"),
        native_files=algebra.payload.files(root / "native.json"),
    )
    algebra.prior.write(root / "worker-result.json", worker)
    return root, worker, comparison


def test_complete_saved_report_binds_inputs_and_never_overwrites_them(tmp_path, monkeypatch):
    root, _, _ = packet(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    output = tmp_path / "reports/algebra.json"
    report = algebra.saved_report(root, output)
    assert json.loads(output.read_text()) == report
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
    assert len(report["inputs"]) == 3
    with pytest.raises(ValueError):
        algebra.saved_report(root, output)
    with pytest.raises(ValueError):
        algebra.saved_report(root, root / "new-report.json")


@pytest.mark.parametrize("alias", ["parent_traversal", "symlink"])
def test_aliased_input_root_cannot_bypass_preservation(tmp_path, monkeypatch, alias):
    root, _, _ = packet(tmp_path, monkeypatch)
    if alias == "parent_traversal":
        aliased = root / ".." / root.name
    else:
        aliased = tmp_path / "linked"
        aliased.symlink_to(root, target_is_directory=True)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises(ValueError):
        algebra.saved_report(aliased, root / "new-report.json")
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}


def test_worker_change_during_diagnostics_cannot_bind_unread_success(tmp_path, monkeypatch):
    root, worker, _ = packet(tmp_path, monkeypatch)
    original = algebra.analyse

    def change_worker(raw):
        report = original(raw)
        worker["status"] = "failed"
        (root / "worker-result.json").write_text(json.dumps(worker))
        return report

    monkeypatch.setattr(algebra, "analyse", change_worker)
    output = tmp_path / "reports/algebra.json"
    with pytest.raises(ValueError, match="Changed external input"):
        algebra.saved_report(root, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "change", ["native", "comparison", "sidecars", "failed", "error", "bool_count", "partial_count"]
)
def test_failed_unbound_or_partial_saved_comparison_refuses(tmp_path, monkeypatch, change):
    root, worker, comparison = packet(tmp_path, monkeypatch)
    if change in ("native", "comparison"):
        with (root / (change + ".json")).open("a") as stream:
            stream.write(" ")
    elif change == "partial_count":
        comparison["cache_pairs_compared"] = 14
        (root / "comparison.json").write_text(json.dumps(comparison))
        worker["comparison"] = algebra.prior.pin(root / "comparison.json")
    else:
        key, value = {
            "sidecars": ("native_files", []),
            "failed": ("status", "failed"),
            "error": ("runtime_capture_error", {}),
            "bool_count": ("accepted_source_comparisons", True),
        }[change]
        worker[key] = value
    (root / "worker-result.json").write_text(json.dumps(worker))
    output = tmp_path / "reports/algebra.json"
    with pytest.raises(ValueError):
        algebra.saved_report(root, output)
    assert not output.exists()
