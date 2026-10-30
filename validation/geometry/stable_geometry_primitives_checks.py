"""Production-denied full-precision comparisons and primitive certificate checks."""

import math
from decimal import Decimal, localcontext


def _ratio(row):
    return Decimal(row["numerator"]) / Decimal(row["denominator"])


def compare(actual, primary, refined):
    assert (
        set(actual["quantities_binary64_hex"])
        == set(primary["values_decimal"])
        == set(refined["values_decimal"])
    )
    assert primary["output_representable"] and refined["output_representable"]
    rows = {}
    maximum = resolution = 0.0
    with localcontext() as context:
        context.prec = max(primary["precision_digits"], refined["precision_digits"]) + 128
        for name, value_hex in actual["quantities_binary64_hex"].items():
            value = float.fromhex(value_hex)
            assert math.isfinite(value)
            a = Decimal.from_float(value)
            expected, second = (
                Decimal(primary["values_decimal"][name]),
                Decimal(refined["values_decimal"][name]),
            )
            ulp = Decimal.from_float(math.ulp(value))
            error, difference = abs(a - expected), abs(expected - second)
            floor = Decimal("1e-26") if name.endswith("_m2") else Decimal("1e-27")
            fixed_budget = floor + Decimal("6e-12") * abs(expected)
            assert error <= 32 * ulp, (name, str(error / ulp))
            assert error <= fixed_budget, (name, str(error / fixed_budget))
            assert difference <= Decimal("0.01") * ulp
            assert difference <= Decimal("0.1") * fixed_budget
            cert = actual["certificates"][name]
            if cert["kind"] == "outward_binary64_interval":
                lower = Decimal.from_float(float.fromhex(cert["lower_hex"]))
                upper = Decimal.from_float(float.fromhex(cert["upper_hex"]))
                assert lower <= expected <= upper
                assert max(abs(a - lower), abs(upper - a)) <= 32 * ulp
                assert cert["maximum_ulps"] == 32
            elif cert["kind"] == "correctly_rounded_binary_rational":
                truth = primary["exact_rational_targets"][name]
                assert int(truth["numerator"]) * int(cert["exact"]["denominator"]) == int(
                    cert["exact"]["numerator"]
                ) * int(truth["denominator"])
                assert (
                    value.hex()
                    == primary["values_rounded_hex"][name]
                    == refined["values_rounded_hex"][name]
                )
            else:
                assert cert["kind"] == "resolved_dyadic_sqrt_interval"
                assert _ratio(cert["lower"]) <= expected <= _ratio(cert["upper"])
                assert (
                    float(_ratio(cert["lower"])).hex()
                    == value.hex()
                    == float(_ratio(cert["upper"])).hex()
                )
                assert (
                    value.hex()
                    == primary["values_rounded_hex"][name]
                    == refined["values_rounded_hex"][name]
                )
            fraction = float(error / fixed_budget)
            refined_fraction = float(difference / fixed_budget)
            maximum, resolution = max(maximum, fraction), max(resolution, refined_fraction)
            rows[name] = dict(
                error_decimal=str(error),
                error_ulps=str(error / ulp),
                fixed_budget_decimal=str(fixed_budget),
                fixed_budget_fraction=fraction,
                reference_resolution_fraction=refined_fraction,
                certificate_verified=True,
            )
    return dict(
        maximum_error_fraction=maximum,
        maximum_reference_resolution_fraction=resolution,
        quantities=rows,
        full_precision_reference_compared=True,
        native_equivalence=False,
        topology_qualified=False,
    )


def transform_check(manifest, base, transformed):
    control = manifest["transform"]
    if not control["exact_binary64_input_transform"]:
        return dict(
            kind="rounded_inputs_compared_independently",
            exact_affine_invariance_claim=False,
            quantization=control["coordinate_quantization"],
        )
    rows = {}
    with localcontext() as context:
        context.prec = max(base["precision_digits"], transformed["precision_digits"]) + 128
        scale = Decimal(2) ** control["scale_exponent"]
        translation = [Decimal.from_float(float.fromhex(v)) for v in control["translation_hex"]]
        for name, raw in base["values_decimal"].items():
            value = Decimal(raw)
            if name.endswith("_x_m"):
                expected = value * scale + translation[0]
            elif name.endswith("_y_m"):
                expected = value * scale + translation[1]
            elif name.endswith("_m2"):
                expected = value * scale * scale
                if name == "signed_area_m2":
                    expected *= control["polygon_orientation_factor"]
            else:
                expected = value * abs(scale)
            actual = Decimal(transformed["values_decimal"][name])
            rounded = float.fromhex(transformed["values_rounded_hex"][name])
            ulp = Decimal.from_float(math.ulp(rounded))
            assert abs(actual - expected) <= Decimal("0.01") * ulp, name
            rows[name] = str(abs(actual - expected))
    return dict(
        kind="exact_binary64_affine_or_order_control",
        exact_affine_invariance_claim=True,
        reference_residuals_decimal=rows,
        bitwise_production_permutation_claim=False,
    )
