"""Synthetic exact-grid algebra and saved-byte contracts; no source execution."""

import copy
import hashlib
import importlib.abc
import json
import math
import struct
import sys
from dataclasses import dataclass
from fractions import Fraction

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


def rational(record):
    return Fraction(record["numerator"]) / record["denominator"]


def dense_product(a, b):
    return [
        [sum(x * y for x, y in zip(row, col, strict=True)) for col in zip(*b, strict=True)]
        for row in a
    ]


def infinity_norm(a):
    return max(sum(map(abs, row)) for row in a)


@pytest.mark.parametrize("regime", ["dyadic", "recurring_means", "extreme_binary64"])
def test_exact_decomposition_and_all_products_agree_with_dense_fraction_oracle(regime):
    if regime == "recurring_means":
        n = 6
        data = dict(
            shape=(2, 3), indices=[divmod(i, 3) for i in range(n)], delta=2.0, boundary="flux"
        )
        a = [0.0] * (n * n)
        for i, (row, col) in enumerate(data["indices"]):
            neighbours = [
                j for j, (r, c) in enumerate(data["indices"]) if abs(r - row) + abs(c - col) == 1
            ]
            a[i * n + i] = -len(neighbours) / 4
            for j in neighbours:
                a[i * n + j] = 0.25
        data.update(
            operator=a, inverse=[((i * 7 + j * 3) % 11 - 5) / 8 for i in range(n) for j in range(n)]
        )
    else:
        data, n = flux(), 4
        data["inverse"] = [v + 0.5 for v in data["inverse"]]
        if regime == "extreme_binary64":
            data["operator"][0] = sys.float_info.max
            data["inverse"][0] = float.fromhex("0x0.0000000000001p-1022")
            data["inverse"][1] = sys.float_info.max
    before = copy.deepcopy(data)
    a, g = [
        [[Fraction.from_float(v) for v in values[i * n : (i + 1) * n]] for i in range(n)]
        for values in (data["operator"], data["inverse"])
    ]
    j = [[Fraction(1, n)] * n for _ in range(n)]
    p = [[Fraction(int(i == k)) - j[i][k] for k in range(n)] for i in range(n)]
    pieces = {
        "JGJ": dense_product(dense_product(j, g), j),
        "JGP": dense_product(dense_product(j, g), p),
        "PGJ": dense_product(dense_product(p, g), j),
        "PGP": dense_product(dense_product(p, g), p),
    }
    report = algebra.diagnose_constant_mode(**data)
    assert data == before
    assert rational(report["decomposition_reconstruction_max_abs"]) == 0
    assert report["exact_arithmetic_inexact_flag"] is False
    for name, values in pieces.items():
        assert rational(report["components"][name]["norm_inf"]) == infinity_norm(values)
        assert rational(report["components"][name]["norm_one"]) == infinity_norm(
            list(zip(*values, strict=True))
        )
    products = {
        "AG_minus_P": dense_product(a, g),
        "GA_minus_P": dense_product(g, a),
        "A_PGP_minus_P": dense_product(a, pieces["PGP"]),
        "PGP_A_minus_P": dense_product(pieces["PGP"], a),
    }
    for name, product in products.items():
        errors = [
            [x - y for x, y in zip(row, target, strict=True)]
            for row, target in zip(product, p, strict=True)
        ]
        assert rational(report["products"][name]["residual_inf"]) == infinity_norm(errors)
        assert rational(report["products"][name]["residual_max_abs"]) == max(
            abs(x) for row in errors for x in row
        )
    assert report["production_repair"] is report["numerical_acceptance"] is False
    if regime == "recurring_means":
        assert any(
            v["display_inexact"]
            for component in report["components"].values()
            for v in component.values()
        )
    if regime == "extreme_binary64":
        assert report["precision_digits"] > 1000


@pytest.mark.parametrize("component", ["constant", "right_constant", "left_constant", "both_cross"])
def test_uniform_and_cross_contamination_are_distinguished_without_changing_source(component):
    data = flux()
    r, c = [0.5, -0.5, 0.0, 0.0], [0.0, 0.0, 0.25, -0.25]
    for i in range(4):
        for j in range(4):
            if component == "constant":
                data["inverse"][4 * i + j] += 0.5
            if component in ("right_constant", "both_cross"):
                data["inverse"][4 * i + j] += r[i]
            if component in ("left_constant", "both_cross"):
                data["inverse"][4 * i + j] += c[j]
    report = algebra.diagnose_constant_mode(**data)
    assert (rational(report["components"]["JGJ"]["norm_inf"]) > 0) == (component == "constant")
    assert (rational(report["components"]["PGJ"]["norm_inf"]) > 0) == (
        component in ("right_constant", "both_cross")
    )
    assert (rational(report["components"]["JGP"]["norm_inf"]) > 0) == (
        component in ("left_constant", "both_cross")
    )
    for name in ("A_PGP_minus_P", "PGP_A_minus_P"):
        assert rational(report["products"][name]["residual_inf"]) == 0
    assert (rational(report["products"]["AG_minus_P"]["residual_inf"]) > 0) == (
        component in ("right_constant", "both_cross")
    )
    assert (rational(report["products"]["GA_minus_P"]["residual_inf"]) > 0) == (
        component in ("left_constant", "both_cross")
    )
    assert report["projected_arrays_exported"] is False


def test_decimal_products_preserve_small_terms_lost_by_binary64_product_rounding():
    data = flux()
    data["operator"] = [v * 1e12 for v in data["operator"]]
    data["inverse"] = [v / 1e12 + 0.25 for v in data["inverse"]]
    rounded = algebra.diagnose(**data)
    exact = algebra.diagnose_constant_mode(**data)
    exact_residual = rational(exact["products"]["AG_minus_P"]["residual_inf"])
    assert exact_residual != Fraction.from_float(rounded["operator_inverse_residual_inf"])
    # Stored G already lost information when its small entries were added to0.25.
    # Exact diagnostic multiplication must not silently repair those source bits.
    assert exact_residual > 0
    assert rational(exact["products"]["A_PGP_minus_P"]["residual_inf"]) > 0


@pytest.mark.parametrize("change", ["off_stencil", "nonfinite", "wrong_boundary", "incomplete"])
def test_constant_diagnostic_refuses_unrepresentable_or_unbounded_inputs(change):
    data = flux()
    if change == "off_stencil":
        data["operator"][3] = 1e-300
    elif change == "nonfinite":
        data["inverse"][0] = float("nan")
    elif change == "wrong_boundary":
        data["boundary"] = "value"
    else:
        data["inverse"].pop()
    with pytest.raises(ValueError):
        algebra.diagnose_constant_mode(**data)


def test_full_default_grid_constant_matrix_is_not_promoted_to_an_inverse():
    width, n = 25, 625
    a = [0.0] * (n * n)
    for i in range(n):
        row, col = divmod(i, width)
        neighbours = [j for j in (i - width, i + width) if 0 <= j < n]
        neighbours += ([i - 1] if col else []) + ([i + 1] if col < width - 1 else [])
        a[i * n + i] = -len(neighbours) / 4
        for j in neighbours:
            a[i * n + j] = 0.25
    report = algebra.diagnose_constant_mode(
        shape=(width, width),
        indices=[divmod(i, width) for i in range(n)],
        delta=2.0,
        operator=a,
        inverse=[0.125] * (n * n),
        boundary="flux",
    )
    assert report["full_product_entries_per_product"] == n * n
    assert rational(report["components"]["JGJ"]["norm_inf"]) == Fraction(n, 8)
    assert rational(report["components"]["PGP"]["norm_inf"]) == 0
    for product in report["products"].values():
        assert rational(product["residual_inf"]) == Fraction(2 * (n - 1), n)
    assert report["numerical_acceptance"] is False


def test_saved_constant_mode_report_preserves_inputs_and_separates_default_mode(
    tmp_path, monkeypatch
):
    root, _, _ = packet(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    output = tmp_path / "reports/constant.json"
    report = algebra.saved_report(root, output, constant_mode=True)
    assert report["kind"] == algebra.CONSTANT_KIND
    assert [r["boundary"] for r in report["operators"]] == ["flux"]
    assert report["native_source_executions"] == report["independent_biological_cases"] == 0
    assert before == {p.name: p.read_bytes() for p in root.iterdir()}
    with pytest.raises(ValueError):
        algebra.saved_report(root, output, constant_mode=True)
    with pytest.raises(ValueError):
        algebra.saved_report(root, root / "new.json", constant_mode=True)
    with pytest.raises(ValueError):
        algebra.saved_report(root, tmp_path / "unwritten.json", constant_mode="yes")
