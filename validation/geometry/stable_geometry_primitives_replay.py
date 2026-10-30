"""Fresh independent primitive references; production and scientific imports denied."""

import argparse
import json
import os
import traceback
from pathlib import Path

from validation.geometry import stable_geometry_primitives_runtime as runtime

runtime.deny_production()

from validation.geometry import stable_geometry_primitives_checks as checks  # noqa: E402
from validation.geometry import stable_geometry_primitives_fixtures as fixtures  # noqa: E402
from validation.geometry import stable_geometry_primitives_reference as reference  # noqa: E402


def read(path):
    if Path(path).stat().st_size > 16 * 2**20:
        raise ValueError("Primitive metadata exceeds the declared bound")
    with Path(path).open() as handle:
        return json.load(handle)


def compare_case(case, source, output):
    positive = case in fixtures.CASES
    if positive:
        kind, points, manifest = fixtures.case(case)
        declared = read(source / (case + "-input.json"))
        assert declared["manifest"] == manifest
        assert declared["request"]["points_binary64_hex"] == fixtures.hex_points(points)
        assert declared["request"]["law"] == "cells_stable_binary64_geometry_primitives@1"
        assert not declared["request"]["native_equivalence"]
        actual = read(source / (case + "-actual.json"))
        reports = []
        for refinement in (1, 2):
            report = reference.evaluate(kind, manifest["input_points_hex"], refinement=refinement)
            runtime.write(output / (case + f"-reference-{refinement}.json"), report)
            reports.append(report)
        base = reference.evaluate(kind, manifest["base_points_hex"], refinement=2)
        runtime.write(output / (case + "-base-reference.json"), base)
        for refinement, report in enumerate(reports, 1):
            saved = read(source / (case + f"-reference-{refinement}.json"))
            assert report == saved
        assert base == read(source / (case + "-base-reference.json"))
        numerical = checks.compare(actual, *reports)
        transform = checks.transform_check(manifest, base, reports[1])
        summary = read(source / (case + ".json"))
        assert summary["comparisons"] == numerical and summary["transform"] == transform
        assert not actual["native_equivalence"] and not actual["whole_mesh_credit"]
        return dict(
            case=case,
            role="positive",
            method=actual["method"],
            comparisons=numerical,
            transform_kind=transform["kind"],
            whole_mesh_credit=False,
        )
    kind, points, declaration = fixtures.domain(case)
    actual = read(source / (case + "-actual.json"))
    assert actual["result"] is None and actual["failure"]["code"] == declaration["expected"]
    reports = []
    if declaration["independent_geometric_domain"]:
        for refinement in (1, 2):
            try:
                report = reference.evaluate(
                    kind, fixtures.hex_points(points), refinement=refinement
                )
            except reference.ReferenceRejected as error:
                report = dict(status="refused", code=error.code, trial=error.trial)
            runtime.write(output / (case + f"-reference-{refinement}.json"), report)
            reports.append(report)
        for refinement, report in enumerate(reports, 1):
            assert report == read(source / (case + f"-reference-{refinement}.json"))
        assert all(r.get("status") == "refused" or not r["output_representable"] for r in reports)
    else:
        runtime.write(
            output / (case + "-input-refusal.json"),
            dict(expected=declaration["expected"], independent_numerical_target_claim=False),
        )
    return dict(
        case=case,
        role="domain",
        code=actual["failure"]["code"],
        independently_geometric=declaration["independent_geometric_domain"],
        independent_numerical_target_claim=False,
        whole_mesh_credit=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    args = parser.parse_args()
    output = Path(os.environ["CELLS_COMPONENT_EVIDENCE"])
    failure, row = None, None
    try:
        row = compare_case(args.case, args.source_evidence / "stable-primitives", output)
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        captured = runtime.capture()
        assert not captured["production_modules_loaded"]
        runtime.write(
            output / "replay-result.json",
            dict(
                status="failed" if failure else "passed",
                failure=failure,
                case=args.case,
                row=row,
                production_imports_denied=True,
                runtime=captured,
                native_equivalence=False,
                whole_mesh_credit=False,
                topology_qualified=False,
            ),
        )


if __name__ == "__main__":
    main()
