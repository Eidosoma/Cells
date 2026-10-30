"""Prepared primitive-only qualification; no automatic scientific execution."""

import json
import os
import struct
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from cells.processes import stable_geometry_primitives as geometry
from validation.geometry import stable_geometry_primitives_checks as checks
from validation.geometry import stable_geometry_primitives_fixtures as fixtures
from validation.geometry import stable_geometry_primitives_reference as reference


def safe(value):
    if type(value) is float:
        return dict(binary64_hex=value.hex())
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(v) for v in value]
    if isinstance(value, Decimal):
        return dict(type="Decimal", text=str(value))
    return value


def save(label, value):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(folder) / "stable-primitives"
        root.mkdir(parents=True, exist_ok=True)
        with (root / (label + ".json")).open("x") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())


def retained_reference(label, kind, points_hex, refinement):
    try:
        result = reference.evaluate(kind, points_hex, refinement=refinement)
    except reference.ReferenceRejected as error:
        save(
            label + f"-reference-{refinement}",
            dict(status="refused", code=error.code, trial=error.trial),
        )
        raise
    save(label + f"-reference-{refinement}", result)
    return result


def retained_prepare(label, request):
    save(label + "-input", dict(request=geometry.request_record(request)))
    try:
        return geometry.prepare(request)
    except geometry.GeometryRejected as error:
        save(
            label + "-failure",
            dict(code=error.code, stage=error.stage, detail=error.detail, trial=error.trial),
        )
        raise


@pytest.mark.parametrize("case", fixtures.CASES)
def test_stable_full_precision_original_scale_translation_order_controls(case):
    kind, points, manifest = fixtures.case(case)
    request = geometry.make_request(kind, points)
    save(case + "-input", dict(request=geometry.request_record(request), manifest=manifest))
    failure, actual = None, None
    try:
        result = geometry.prepare(request)
        actual = geometry.result_record(result)
    except geometry.GeometryRejected as error:
        failure = error
        actual = dict(status="refused", code=error.code, stage=error.stage, trial=error.trial)
    save(case + "-actual", actual)
    primary = retained_reference(case, kind, manifest["input_points_hex"], 1)
    refined = retained_reference(case, kind, manifest["input_points_hex"], 2)
    base = reference.evaluate(kind, manifest["base_points_hex"], refinement=2)
    save(case + "-base-reference", base)
    assert failure is None, "Unexpected refusal retained before expectations"
    numerical = checks.compare(actual, primary, refined)
    transformation = checks.transform_check(manifest, base, refined)
    if case == "retained-centroid":
        assert result.method == "exact_binary_rational"
    if case in ("retained-centroid", "retained-thin"):
        native = [
            v[0]
            for v in struct.iter_unpack(
                "<d", bytes.fromhex(manifest["source"]["saved_native_output"]["bits_C"])
            )
        ]
        names = (
            ("centroid_x_m", "centroid_y_m")
            if kind == "polygon"
            else ("circumcenter_x_m", "circumcenter_y_m", "circumradius_m", "inradius_m")
        )
        with localcontext() as context:
            context.prec = primary["precision_digits"] + 128
            old = [
                abs(Decimal.from_float(v) - Decimal(primary["values_decimal"][name]))
                / (
                    Decimal("1e-27")
                    + Decimal("6e-12") * abs(Decimal(primary["values_decimal"][name]))
                )
                for name, v in zip(names, native, strict=True)
            ]
        save(
            case + "-retained-native-failure",
            dict(
                native_error_fractions=[str(v) for v in old],
                original_bits_unchanged=manifest["source"]["saved_native_output"],
                original_failed_campaign_reclassified=False,
            ),
        )
        assert max(old) > 1
        assert any(
            result.values[name].hex() != v.hex() for name, v in zip(names, native, strict=True)
        )
    geometry.validate(request, result)
    save(
        case,
        dict(
            status="primitive_candidate_passed",
            method=result.method,
            comparisons=numerical,
            transform=transformation,
            native_equivalence=False,
            whole_mesh_credit=False,
            topology_qualified=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.DOMAIN_CASES)
def test_explicit_degeneracy_shape_range_and_scalar_refusals(case):
    kind, points, declaration = fixtures.domain(case)
    save(case + "-input", dict(primitive=kind, points=safe(points), declaration=declaration))
    error, result = None, None
    try:
        request = geometry.make_request(kind, points)
        result = geometry.result_record(geometry.prepare(request))
    except geometry.GeometryRejected as failure:
        error = failure
    save(
        case + "-actual",
        dict(
            result=result,
            failure=None
            if error is None
            else dict(code=error.code, stage=error.stage, detail=error.detail, trial=error.trial),
        ),
    )
    independent = []
    if declaration["independent_geometric_domain"]:
        for refinement in (1, 2):
            try:
                report = reference.evaluate(
                    kind, fixtures.hex_points(points), refinement=refinement
                )
            except reference.ReferenceRejected as failure:
                report = dict(status="refused", code=failure.code, trial=failure.trial)
            save(case + f"-reference-{refinement}", report)
            independent.append(report)
    assert error is not None, "Unexpected completion retained before refusal assertion"
    assert error.code == declaration["expected"]
    if independent:
        assert all(
            r.get("status") == "refused" or not r["output_representable"] for r in independent
        )


@pytest.mark.parametrize(
    "target",
    (
        "request_identity",
        "mutable_points",
        "private_integer_points",
        "result_values",
        "certificates",
        "provenance",
        "method",
        "mutable_quantities",
    ),
)
def test_resealed_primitive_identity_ownership_and_method_tampering(target):
    request = geometry.make_request("polygon", [[1, 1], [3, 1], [3, 3], [1, 3]])
    result = retained_prepare("tamper-" + target, request)
    save(
        "tamper-" + target + "-original",
        dict(request=geometry.request_record(request), result=geometry.result_record(result)),
    )
    if target == "request_identity":
        request = replace(request, identity="changed")
    elif target == "mutable_points":
        request = replace(request, points=[list(p) for p in request.points])
    elif target == "private_integer_points":
        request = replace(request, points=tuple(tuple(int(v) for v in p) for p in request.points))
    elif target == "result_values":
        result = replace(
            result,
            quantities=(
                (result.quantities[0][0], result.quantities[0][1] + 1.0),
                *result.quantities[1:],
            ),
        )
    elif target == "certificates":
        result = replace(result, certificates_json="{}")
    elif target == "provenance":
        result = replace(result, provenance_json='{"native_equivalence":true}')
    elif target == "method":
        result = replace(result, method="literal_betse")
    else:
        result = replace(result, quantities=list(result.quantities))
    if target in ("result_values", "certificates", "provenance", "method"):
        result = replace(result, identity=geometry._digest(geometry.result_record(result)))
    with pytest.raises(geometry.GeometryRejected):
        geometry.validate(request, result)


def test_caller_aliases_and_primitive_output_scope():
    points = [[1.0, 1.0], [3.0, 1.0], [3.0, 3.0], [1.0, 3.0]]
    request = geometry.make_request("polygon", points)
    points[0][0] = 77.0
    result = retained_prepare("ownership", request)
    save(
        "ownership",
        dict(request=geometry.request_record(request), result=geometry.result_record(result)),
    )
    assert request.points[0][0] == 1.0
    with pytest.raises(FrozenInstanceError):
        result.method = "changed"
    copy = result.values
    copy["centroid_x_m"] = 99.0
    assert result.values["centroid_x_m"] != 99.0
    exported = geometry.result_record(result)
    assert not exported["native_equivalence"] and not exported["whole_mesh_credit"]
    assert not exported["topology_qualified"] and not exported["physical_geometry_admitted"]
