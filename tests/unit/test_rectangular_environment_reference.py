"""Small independent arithmetic controls; no numerical library or solver entry."""

import ast
import copy
import json
import math
from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from validation.betse import rectangular_environment_reference as reference


def rational(value):
    return Fraction(int(value["numerator"]), int(value["denominator"]))


def square():
    # Hand-derived four-node graph and its zero-mean inverse. Every entry is
    # dyadic, so all products can be exactly zero in the diagnostic arithmetic.
    return dict(
        shape=(2, 2),
        indices=((0, 0), (0, 1), (1, 0), (1, 1)),
        bounds_m=(0.0, 2.0, 0.0, 2.0),
        operator=[
            -2.0,
            1.0,
            1.0,
            0.0,
            1.0,
            -2.0,
            0.0,
            1.0,
            1.0,
            0.0,
            -2.0,
            1.0,
            0.0,
            1.0,
            1.0,
            -2.0,
        ],
        inverse=[
            -5 / 16,
            1 / 16,
            1 / 16,
            3 / 16,
            1 / 16,
            -5 / 16,
            3 / 16,
            1 / 16,
            1 / 16,
            3 / 16,
            -5 / 16,
            1 / 16,
            3 / 16,
            1 / 16,
            1 / 16,
            -5 / 16,
        ],
    )


def exact_product(left, right, n):
    a, b = list(map(Fraction.from_float, left)), list(map(Fraction.from_float, right))
    return [
        sum((a[i * n + k] * b[k * n + j] for k in range(n)), Fraction(0))
        for i in range(n)
        for j in range(n)
    ]


def product_errors(left, right, n):
    values = exact_product(left, right, n)
    errors = [
        value - (Fraction(int(i == j)) - Fraction(1, n))
        for (i, j), value in zip(((i, j) for i in range(n) for j in range(n)), values, strict=True)
    ]
    return max(map(abs, errors)), max(sum(map(abs, errors[i * n : (i + 1) * n])) for i in range(n))


def assert_products(report, data):
    n = math.prod(data["shape"])
    for key, left, right in (
        ("AG_minus_P", data["operator"], data["inverse"]),
        ("GA_minus_P", data["inverse"], data["operator"]),
    ):
        maximum, norm = product_errors(left, right, n)
        assert rational(report["products"][key]["max_abs"]) == maximum
        assert rational(report["products"][key]["norm_inf"]) == norm
        assert report["products"][key]["entries_checked"] == n * n


def test_complete_square_exact_products_modes_and_no_acceptance():
    data = square()
    report = reference.diagnose(**data)
    assert report["support"]["entries_checked"] == 16
    assert report["support"]["observed_nonzeros"] == 12
    assert report["support"]["missing_nonzeros"] == 0
    assert report["support"]["unexpected_nonzeros"] == 0
    assert rational(report["support"]["coefficient_error"]["max_abs"]) == 0
    assert_products(report, data)
    for name in ("operator", "inverse"):
        for key in ("row_constant_mode", "column_constant_mode"):
            assert rational(report[name][key]["max_abs"]) == 0
        assert rational(report[name]["symmetry"]["max_abs"]) == 0
    assert report["arithmetic"]["inexact_flag"] is False
    assert report["arithmetic"]["decimal_inexact_trapped"] is True
    assert report["numerical_acceptance"] is False
    assert report["physical_admission"] is False
    assert report["native_source_correspondence"] is False
    assert report["new_residual_acceptance_tolerance"] is None
    assert report["solver_calls"] == report["inverse_constructions"] == 0
    json.dumps(report, allow_nan=False)


def test_anisotropic_coefficients_are_independent_of_stored_matrices():
    data = square()
    data["bounds_m"] = (0.0, 2.0, 0.0, 1.0)  # dx=1, dy=1/2: cx=1, cy=4.
    data["operator"] = [
        -5.0,
        1.0,
        4.0,
        0.0,
        1.0,
        -5.0,
        0.0,
        4.0,
        4.0,
        0.0,
        -5.0,
        1.0,
        0.0,
        4.0,
        1.0,
        -5.0,
    ]
    data["inverse"] = [
        v / 160
        for v in (
            -29,
            19,
            -11,
            21,
            19,
            -29,
            21,
            -11,
            -11,
            21,
            -29,
            19,
            21,
            -11,
            19,
            -29,
        )
    ]
    report = reference.diagnose(**data)
    assert rational(report["coefficients_per_m2"]["x"]["exact"]) == 1
    assert rational(report["coefficients_per_m2"]["y"]["exact"]) == 4
    assert rational(report["exact_cell_area_m2"]) == Fraction(1, 2)
    assert rational(report["support"]["coefficient_error"]["max_abs"]) == 0
    assert_products(report, data)
    assert rational(report["products"]["AG_minus_P"]["max_abs"]) > 0


def test_wrong_isotropic_coefficients_remain_visible_on_anisotropic_bounds():
    data = square()
    data["bounds_m"] = (0.0, 2.0, 0.0, 1.0)
    report = reference.diagnose(**data)
    assert rational(report["support"]["coefficient_error"]["max_abs"]) == 3
    assert rational(report["support"]["coefficient_error"]["norm_inf"]) == 6
    # The supplied wrong A/G still invert each other: the independent stencil
    # check must not be replaced by their self-consistency.
    assert rational(report["products"]["AG_minus_P"]["max_abs"]) == 0


def test_exact_binary64_bound_span_is_not_rounded_subtraction():
    data = square()
    data["bounds_m"] = (0.1, 0.7, -0.3, 0.8)
    report = reference.diagnose(**data)
    dx = (Fraction.from_float(0.7) - Fraction.from_float(0.1)) / 2
    dy = (Fraction.from_float(0.8) - Fraction.from_float(-0.3)) / 2
    assert dx != Fraction.from_float((0.7 - 0.1) / 2)
    assert rational(report["exact_spacing_m"]["x"]) == dx
    assert rational(report["exact_spacing_m"]["y"]) == dy
    for axis, spacing in (("x", dx), ("y", dy)):
        row = report["coefficients_per_m2"][axis]
        exact = 1 / spacing**2
        assert rational(row["exact"]) == exact
        assert rational(row["nearest_binary64_minus_exact"]) == (
            Fraction.from_float(float(exact)) - exact
        )


def test_complete_permutation_preserves_mapping_and_all_products():
    data = square()
    permutation = (2, 0, 1, 3)
    changed = copy.deepcopy(data)
    changed["indices"] = tuple(data["indices"][i] for i in permutation)
    for key in ("operator", "inverse"):
        changed[key] = [data[key][4 * i + j] for i in permutation for j in permutation]
    report = reference.diagnose(**changed)
    assert report["indices"] == [list(pair) for pair in changed["indices"]]
    assert rational(report["support"]["coefficient_error"]["max_abs"]) == 0
    assert_products(report, changed)
    unchanged_matrices = dict(changed, operator=data["operator"], inverse=data["inverse"])
    wrong = reference.diagnose(**unchanged_matrices)
    assert wrong["support"]["unexpected_nonzeros"] > 0


def test_off_stencil_entry_is_counted_and_used_in_both_full_products():
    data = square()
    data["operator"][3] = 0.5
    report = reference.diagnose(**data)
    assert report["support"]["unexpected_nonzeros"] == 1
    assert report["support"]["observed_nonzeros"] == 13
    assert report["support"]["unexpected_entries_dropped"] == 0
    assert report["support"]["unexpected_examples"] == [
        dict(row=0, column=3, binary64_hex=(0.5).hex())
    ]
    assert_products(report, data)
    assert rational(report["products"]["AG_minus_P"]["max_abs"]) == Fraction(5, 32)
    assert rational(report["operator"]["row_constant_mode"]["max_abs"]) == Fraction(1, 2)
    assert rational(report["operator"]["column_constant_mode"]["max_abs"]) == Fraction(1, 2)
    assert rational(report["operator"]["symmetry"]["max_abs"]) == Fraction(1, 2)


def test_missing_stencil_entry_is_not_filled_or_repaired():
    data = square()
    data["operator"][1] = 0.0
    report = reference.diagnose(**data)
    assert report["support"]["missing_nonzeros"] == 1
    assert report["support"]["observed_nonzeros"] == 11
    assert rational(report["support"]["coefficient_error"]["max_abs"]) == 1
    assert_products(report, data)
    assert data["operator"][1] == 0.0


def test_constant_inverse_contamination_does_not_hide_behind_projector_products():
    data = square()
    data["inverse"] = [value + 0.25 for value in data["inverse"]]
    report = reference.diagnose(**data)
    for key in ("AG_minus_P", "GA_minus_P"):
        assert rational(report["products"][key]["max_abs"]) == 0
    for key in ("row_constant_mode", "column_constant_mode"):
        assert rational(report["inverse"][key]["max_abs"]) == 1


def test_left_and_right_constant_modes_are_measured_separately():
    data = square()
    data["inverse"][0:4] = [value + 0.25 for value in data["inverse"][0:4]]
    report = reference.diagnose(**data)
    assert rational(report["inverse"]["row_constant_mode"]["max_abs"]) == 1
    assert rational(report["inverse"]["column_constant_mode"]["max_abs"]) == Fraction(1, 4)
    assert_products(report, data)
    assert rational(report["products"]["AG_minus_P"]["max_abs"]) == Fraction(1, 2)
    assert rational(report["products"]["GA_minus_P"]["max_abs"]) == 0


def test_probe_residual_gauge_conservation_and_energy_have_hand_derived_values():
    data = square()
    b, x = [-4.0, -2.0, 2.0, 4.0], [2.0, 1.0, -1.0, -2.0]
    report = reference.diagnose(**data, probes=[dict(name="balanced", rhs=b, solution=x)])
    row = report["probes"][0]
    assert row["rhs_exactly_balanced"] is True
    assert rational(row["rhs_sum"]) == 0
    assert rational(row["rhs_abs_sum"]) == 12
    assert rational(row["residual"]["max_abs"]) == 0
    assert rational(row["inverse_action_minus_supplied_solution"]["max_abs"]) == 0
    assert rational(row["potential_mean"]) == 0
    assert rational(row["operator_image_sum"]) == 0
    assert rational(row["area_weighted_operator_image_sum"]) == 0
    assert rational(row["energy"]["stored_negative_x_A_x"]) == 20
    assert rational(row["energy"]["exact_stencil_edge_form"]) == 20
    assert rational(row["energy"]["stored_minus_exact_edge_form"]) == 0


def test_constant_supplied_potential_is_reported_without_projection():
    data = square()
    b, x = [-4.0, -2.0, 2.0, 4.0], [5.0, 4.0, 2.0, 1.0]
    before = copy.deepcopy(x)
    row = reference.diagnose(**data, probes=[dict(name="shifted", rhs=b, solution=x)])["probes"][0]
    assert rational(row["residual"]["max_abs"]) == 0
    assert rational(row["potential_mean"]) == 3
    assert rational(row["inverse_action_minus_supplied_solution"]["max_abs"]) == 3
    assert rational(row["energy"]["exact_stencil_edge_form"]) == 20
    assert x == before


def test_constant_incompatible_rhs_is_retained_and_not_centered():
    data = square()
    b = [1.0] * 4
    report = reference.diagnose(**data, probes=[dict(name="constant", rhs=b, solution=[0.0] * 4)])
    row = report["probes"][0]
    assert row["rhs_exactly_balanced"] is False
    assert rational(row["rhs_relative_imbalance"]) == 1
    assert rational(row["rhs_sum"]) == 4
    assert rational(row["residual"]["signed_value"]) == -1
    assert rational(row["residual_sum"]) == -4
    assert rational(row["area_weighted_residual_sum"]) == -4
    assert report["original_rhs_centered"] is False
    assert b == [1.0] * 4


def test_rhs_only_probe_reports_exact_compatibility_without_constructing_solution():
    report = reference.diagnose(
        **square(), probes=[dict(name="rhs_only", rhs=[1.0, -1.0, 0.0, 0.0], solution=None)]
    )
    row = report["probes"][0]
    assert row["rhs_exactly_balanced"] is True
    assert row["supplied_solution"] is False
    assert row["solution_diagnostics_available"] is False
    assert "residual" not in row
    assert report["inverse_constructions"] == 0


def test_two_by_three_rectangle_energy_and_nonuniform_axis_coefficients():
    # C-order 2x3 graph, dx=2 and dy=1/2. Explicit rows avoid sharing a
    # stencil builder with the reference under test.
    a = [
        -4.25,
        0.25,
        0.0,
        4.0,
        0.0,
        0.0,
        0.25,
        -4.5,
        0.25,
        0.0,
        4.0,
        0.0,
        0.0,
        0.25,
        -4.25,
        0.0,
        0.0,
        4.0,
        4.0,
        0.0,
        0.0,
        -4.25,
        0.25,
        0.0,
        0.0,
        4.0,
        0.0,
        0.25,
        -4.5,
        0.25,
        0.0,
        0.0,
        4.0,
        0.0,
        0.25,
        -4.25,
    ]
    x = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    b = [12.25, 12.0, 11.75, -11.75, -12.0, -12.25]
    report = reference.diagnose(
        shape=(2, 3),
        indices=((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)),
        bounds_m=(0.0, 6.0, 0.0, 1.0),
        operator=a,
        inverse=[0.0] * 36,
        probes=[dict(name="linear", rhs=b, solution=x)],
    )
    assert rational(report["support"]["coefficient_error"]["max_abs"]) == 0
    assert rational(report["exact_cell_area_m2"]) == 1
    row = report["probes"][0]
    assert rational(row["residual"]["max_abs"]) == 0
    assert rational(row["potential_mean"]) == Fraction(5, 2)
    assert rational(row["energy"]["stored_negative_x_A_x"]) == 109
    assert rational(row["energy"]["exact_stencil_edge_form"]) == 109
    assert rational(report["products"]["AG_minus_P"]["max_abs"]) == Fraction(5, 6)


def test_dense_work_refusal_keeps_complete_support_and_constant_modes(monkeypatch):
    data = square()
    data["operator"] = [1.0] * 16
    monkeypatch.setattr(reference, "MAX_ARITHMETIC_TERMS", 1)
    report = reference.diagnose(
        **data, probes=[dict(name="held", rhs=[1.0] * 4, solution=[0.0] * 4)]
    )
    assert report["support"]["entries_checked"] == 16
    assert report["support"]["observed_nonzeros"] == 16
    assert report["support"]["unexpected_nonzeros"] == 4
    assert report["work"]["omitted_operator_entries"] == 0
    assert report["work"]["scalar_product_terms"] == 160
    assert report["work"]["products_and_solution_actions_available"] is False
    assert report["work"]["refusal"]
    assert report["products"] is None
    assert rational(report["operator"]["row_constant_mode"]["max_abs"]) == 4
    assert report["probes"][0]["solution_diagnostics_available"] is False
    assert rational(report["probes"][0]["rhs_sum"]) == 4


def test_exact_decimal_products_span_extreme_binary64_values_without_float_overflow():
    data = square()
    huge, tiny = float.fromhex("0x1.fffffffffffffp+1023"), float.fromhex("0x0.0000000000001p-1022")
    data["operator"][0] = huge
    data["operator"][1] = tiny
    data["inverse"][0] = huge
    report = reference.diagnose(**data)
    assert_products(report, data)
    assert report["arithmetic"]["precision_digits"] <= reference.MAX_PRECISION
    assert report["arithmetic"]["inexact_flag"] is False
    json.dumps(report, allow_nan=False)


def test_decimal_context_is_local_and_precision_failure_is_explicit(monkeypatch):
    with localcontext() as context:
        context.prec = 7
        context.traps[Inexact] = False
        context.clear_flags()
        report = reference.diagnose(**square())
        assert context.prec == 7
        assert context.traps[Inexact] is False
        assert not context.flags[Inexact]
        assert report["arithmetic"]["inexact_flag"] is False
    monkeypatch.setattr(reference, "MAX_PRECISION", 1)
    with pytest.raises(ValueError, match="precision bound"):
        reference.diagnose(**square())


def test_underflowing_ideal_spacing_is_exact_not_silently_replaced():
    data = square()
    tiny = float.fromhex("0x0.0000000000001p-1022")
    data["bounds_m"] = (0.0, tiny, 0.0, 2.0)
    report = reference.diagnose(**data)
    assert rational(report["exact_spacing_m"]["x"]) == Fraction.from_float(tiny) / 2
    assert report["coefficients_per_m2"]["x"]["nearest_binary64_finite"] is False
    assert report["coefficients_per_m2"]["x"]["nearest_binary64_hex"] is None
    assert report["physical_admission"] is False
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("shape", [(1, 4), (2, 1), (True, 4), (2.0, 2), (26, 25), (2,), None])
def test_shape_refusals_before_matrix_work(shape):
    with pytest.raises(ValueError, match="rectangle"):
        reference.diagnose(**dict(square(), shape=shape))


@pytest.mark.parametrize(
    "indices",
    [
        ((0, 0), (0, 1), (1, 0)),
        ((0, 0), (0, 1), (1, 0), (1, 0)),
        ((0, 0), (0, 1), (1, 0), (2, 1)),
        ((0, 0), (0, 1), (1, 0), (1, True)),
        ((0, 0), (0, 1), (1, 0), (1, 1.0)),
    ],
)
def test_complete_mapping_refusals(indices):
    with pytest.raises(ValueError, match="mapping|grid index"):
        reference.diagnose(**dict(square(), indices=indices))


@pytest.mark.parametrize(
    "bounds",
    [
        (0.0, 0.0, 0.0, 2.0),
        (2.0, 0.0, 0.0, 2.0),
        (0.0, 2.0, 2.0, 0.0),
        (0.0, math.inf, 0.0, 2.0),
        (0.0, 2.0, math.nan, 2.0),
        (0, 2.0, 0.0, 2.0),
        (0.0, 2.0, 0.0),
    ],
)
def test_bounds_refusals(bounds):
    with pytest.raises(ValueError, match="bound|binary64"):
        reference.diagnose(**dict(square(), bounds_m=bounds))


@pytest.mark.parametrize("key", ["operator", "inverse"])
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 1, True])
def test_nonfinite_or_non_binary64_matrix_entry_refused(key, bad):
    data = square()
    data[key][-1] = bad
    with pytest.raises(ValueError, match="finite binary64"):
        reference.diagnose(**data)


@pytest.mark.parametrize("key", ["operator", "inverse"])
def test_truncated_full_matrix_refused(key):
    data = square()
    data[key].pop()
    with pytest.raises(ValueError, match="complete flattened"):
        reference.diagnose(**data)


@pytest.mark.parametrize(
    "probe",
    [
        dict(name="", rhs=[0.0] * 4, solution=None),
        dict(name="bad", rhs=[0.0] * 3, solution=None),
        dict(name="bad", rhs=[0.0] * 4, solution=[0.0] * 3),
        dict(name="bad", rhs=[0.0, 0.0, 0.0, math.nan], solution=None),
        dict(name="bad", rhs=[0.0] * 4, solution=[0.0, 0.0, math.inf, 0.0]),
        dict(name="bad", rhs=[0.0] * 4),
        dict(name="bad", rhs=[0.0] * 4, solution=None, accepted=True),
    ],
)
def test_probe_schema_and_finiteness_refusals(probe):
    with pytest.raises(ValueError):
        reference.diagnose(**square(), probes=[probe])


def test_probe_names_and_count_are_bounded():
    probe = dict(name="same", rhs=[0.0] * 4, solution=None)
    with pytest.raises(ValueError, match="unique"):
        reference.diagnose(**square(), probes=[probe, probe])
    with pytest.raises(ValueError, match="at most32"):
        reference.diagnose(**square(), probes=[probe] * 33)


def test_all_inputs_including_signed_zero_and_probe_objects_remain_unchanged():
    data = square()
    data["operator"][3] = -0.0
    data["probes"] = [dict(name="zero", rhs=[-0.0] * 4, solution=[0.0] * 4)]
    before = copy.deepcopy(data)
    reference.diagnose(**data)
    assert data == before
    assert data["operator"][3].hex() == "-0x0.0p+0"
    assert all(value.hex() == "-0x0.0p+0" for value in data["probes"][0]["rhs"])


def test_reference_import_surface_is_only_stdlib_and_contains_no_solver_call():
    tree = ast.parse(Path(reference.__file__).read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module)
    assert imports == {"math", "decimal", "fractions"}
    forbidden = {"inv", "pinv", "svd", "solve", "lstsq", "diagnose_constant_mode"}
    assert not any(
        isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id in forbidden)
            or (isinstance(node.func, ast.Attribute) and node.func.attr in forbidden)
        )
        for node in ast.walk(tree)
    )


def test_decimal_display_is_explicitly_separate_from_exact_fraction():
    value = reference._ratio(Fraction(1, 3))
    assert rational(value) == Fraction(1, 3)
    assert value["display_inexact"] is True
    assert len(value["decimal80"].removeprefix("0.")) == 80
    exact = reference._ratio(Decimal("0.125"))
    assert rational(exact) == Fraction(1, 8)
    assert exact["display_inexact"] is False
