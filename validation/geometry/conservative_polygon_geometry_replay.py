"""Prepared fresh reference worker; production/scientific imports are denied."""

import argparse
import json
import os
import traceback
from pathlib import Path

from validation.geometry import stable_geometry_primitives_runtime as runtime

runtime.deny_production()

from validation.geometry import conservative_polygon_geometry_reference as reference  # noqa: E402


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Polygon reference record exceeds 16 MiB")
    with path.open() as handle:
        return json.load(handle)


def write(name, value):
    runtime.write(Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / (name + ".json"), value)


def geometry_case(case, source):
    source = source / "conservative-polygon"
    request = read(source / (case + "-request.json"))
    raw = request["record"]["declaration"]
    actual = read(source / (case + "-actual.json"))
    assert reference._hash(request["record"]) == request["identity"]
    assert reference._hash(actual["geometry"]) == actual["identity"]
    assert actual["geometry"]["request_identity"] == request["identity"]
    reports = []
    for refinement in (1, 2):
        target = reference.evaluate(raw, refinement=refinement)
        write(case + f"-reference-{refinement}", target)
        assert target == read(source / (case + f"-reference-{refinement}.json"))
        reports.append(target)
    comparison = reference.compare(raw, actual["geometry"], *reports)
    assert comparison == read(source / (case + "-comparison.json"))
    return dict(case=case, role="geometry", comparison=comparison)


def domain_case(case, source):
    source = source / "conservative-polygon"
    raw = read(source / (case + "-input.json"))
    actual = read(source / (case + "-refusal.json"))
    assert actual["reason"] and actual["type"]
    if case in ("area-underflow", "volume-overflow"):
        for refinement in (1, 2):
            target = reference.evaluate(raw, refinement=refinement)
            write(case + f"-reference-{refinement}", target)
            assert not target["required_outputs_representable"]
            assert target == read(source / (case + f"-reference-{refinement}.json"))
        return dict(case=case, role="domain", independent_unrepresentable_required_measure=True)
    try:
        reference.evaluate(raw)
    except reference.ReferenceRejected as error:
        refusal = dict(type=type(error).__name__, reason=str(error))
        write(case + "-independent-refusal", refusal)
        assert refusal == read(source / (case + "-independent-refusal.json"))
        return dict(case=case, role="domain", independent_refusal=refusal)
    raise AssertionError("Unsupported polygon input was independently admitted")


def physical_case(case, source):
    source = source / "conservative-polygon-tissue"
    geometry = read(source / (case + "-geometry-actual.json"))
    raw = geometry["request"]["declaration"]
    request = read(source / (case + "-physical-input.json"))
    actual = read(source / (case + "-physical-actual.json"))
    assert reference._hash(geometry["geometry"]) == geometry["identity"]
    assert reference._hash(geometry["request"]) == geometry["geometry"]["request_identity"]
    assert (
        reference._hash(dict(definition=actual["definition"], provenance=actual["provenance"]))
        == actual["identity"]
    )
    assert request["geometry_identity"] == geometry["identity"]
    assert actual["provenance"]["geometry_identity"] == geometry["identity"]
    assert actual["provenance"]["geometry"] == geometry["geometry"]
    assert actual["provenance"]["request"] == request
    reports = []
    for refinement in (1, 2):
        target = reference.evaluate(raw, refinement=refinement)
        write(case + f"-geometry-reference-{refinement}", target)
        assert target == read(source / (case + f"-geometry-reference-{refinement}.json"))
        reports.append(target)
    geometry_comparison = reference.compare(raw, geometry["geometry"], *reports)
    comparison = reference.compare_physical(
        geometry["geometry"], request, actual["definition"], *reports
    )
    combined = dict(geometry=geometry_comparison, physical=comparison)
    assert combined == read(source / (case + "-comparison.json"))
    write(case + "-comparison", combined)
    return dict(case=case, role="physical", comparison=combined)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--role", choices=("geometry", "domain", "physical"), required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    args = parser.parse_args()
    failure, row = None, None
    try:
        function = {"geometry": geometry_case, "domain": domain_case, "physical": physical_case}[
            args.role
        ]
        row = function(args.case, args.source_evidence)
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, reason=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        captured = runtime.capture()
        assert not captured["production_modules_loaded"]
        write(
            "replay-result",
            dict(
                status="failed" if failure else "passed",
                case=args.case,
                role=args.role,
                row=row,
                failure=failure,
                runtime=captured,
                production_imports_denied=True,
                source_generation_authenticated=False,
                native_equivalence=False,
                field_or_solver_executed=False,
                automatic_retry=False,
            ),
        )


if __name__ == "__main__":
    main()
