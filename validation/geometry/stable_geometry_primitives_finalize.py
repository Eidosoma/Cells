"""Guarded primitive metadata audit; actual and reference records stay separate."""

import argparse
import json
import math
import os
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from validation.geometry import stable_geometry_primitives_runtime as runtime

runtime.deny_production()


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Primitive metadata exceeds declared byte bound")
    with path.open() as handle:
        return json.load(handle)


def verify_runtime(value, files, *, pytest, expected_version):
    assert value["affinity"] == [6] and value["pytest_version"] == expected_version
    assert not value["file_errors"] and not value["mapped_file_errors"]
    assert not value["scientific_modules_loaded"]
    assert value["float_info"] == dict(radix=2, mant_dig=53, max_exp=1024, min_exp=-1021)
    assert all(v == "1" for v in value["threads"].values())
    if pytest:
        assert value["exitstatus"] == 0
    else:
        assert not value["production_modules_loaded"]
    for name, expected in value["files"].items():
        if name in files:
            assert files[name] == expected
        else:
            assert len(files) < 20000
            assert runtime.sha(name) == expected, name
            files[name] = expected


def collect(out, plan, partial):
    checks, replays, positives, domains, errors, files = [], [], [], [], [], {}

    def error(path, failure):
        errors.append(dict(path=str(path), type=type(failure).__name__, message=str(failure)))
        if not partial:
            raise failure

    for unit in plan["check_units"]:
        xml = out / "units" / unit["unit"] / "tests.xml"
        source = out / "evidence" / unit["unit"]
        try:
            assert xml.stat().st_size <= 16 * 2**20
            cases = ET.parse(xml).getroot().findall(".//testcase")
            assert len(cases) == 1
            case = cases[0]
            assert dict(classname=case.get("classname"), name=case.get("name")) == unit["pytest_id"]
            assert all(case.find(tag) is None for tag in ("failure", "error", "skipped"))
            verify_runtime(
                read(source / "runtime.json"),
                files,
                pytest=True,
                expected_version=plan["pytest_version"],
            )
            checks.append(unit["pytest_id"])
            if unit["role"] == "positive":
                summary = read(source / "stable-primitives" / (unit["case"] + ".json"))
                assert summary["status"] == "primitive_candidate_passed"
                assert not summary["native_equivalence"] and not summary["whole_mesh_credit"]
                assert not summary["topology_qualified"]
                assert summary["comparisons"]["full_precision_reference_compared"]
                positives.append(
                    dict(
                        case=unit["case"],
                        method=summary["method"],
                        transform_kind=summary["transform"]["kind"],
                    )
                )
            elif unit["role"] == "domain":
                actual = read(source / "stable-primitives" / (unit["case"] + "-actual.json"))
                assert actual["failure"] is not None and actual["result"] is None
                domains.append(dict(case=unit["case"], code=actual["failure"]["code"]))
        except Exception as failure:
            error(xml, failure)
    for unit in plan["replay_units"]:
        path = out / "evidence" / unit["unit"] / "replay-result.json"
        try:
            result = read(path)
            assert result["status"] == "passed" and result["failure"] is None
            assert result["production_imports_denied"] and result["case"] == unit["case"]
            assert not result["native_equivalence"] and not result["whole_mesh_credit"]
            assert not result["topology_qualified"]
            verify_runtime(
                result["runtime"], files, pytest=False, expected_version=plan["pytest_version"]
            )
            row = result["row"]
            assert row["role"] == unit["role"] and row["case"] == unit["case"]
            if row["role"] == "positive":
                assert math.isfinite(row["comparisons"]["maximum_error_fraction"])
                assert row["comparisons"]["maximum_error_fraction"] <= 1
                assert row["comparisons"]["maximum_reference_resolution_fraction"] <= 0.1
            replays.append(row)
            del result
        except Exception as failure:
            error(path, failure)
    if not partial:
        assert len(checks) == len({(r["classname"], r["name"]) for r in checks}) == 84
        assert {(r["classname"], r["name"]) for r in checks} == {
            (r["classname"], r["name"]) for r in plan["expected_pytest_ids"]
        }
        assert len(replays) == 75 and len(positives) == 54 and len(domains) == 21
        for role, expected in (
            ("positive", plan["positive_cases"]),
            ("domain", plan["domain_cases"]),
        ):
            names = [r["case"] for r in replays if r["role"] == role]
            assert len(names) == len(set(names)) and set(names) == set(expected)
    methods = {}
    transformations = {}
    for row in positives:
        methods[row["method"]] = methods.get(row["method"], 0) + 1
        transformations[row["transform_kind"]] = transformations.get(row["transform_kind"], 0) + 1
    return dict(
        status="partial" if partial else "passed",
        checks=checks,
        replay_cases=replays,
        observed_positive_cases=positives,
        observed_domain_cases=domains,
        observed_methods=methods,
        observed_transform_kinds=transformations,
        runtime_files_verified=len(files),
        errors=errors,
        maximum_error_fraction=max(
            (
                r["comparisons"]["maximum_error_fraction"]
                for r in replays
                if r["role"] == "positive"
            ),
            default=None,
        ),
        only_observed_methods_receive_scope_credit=True,
        original_failed_campaign_reclassified=False,
        original_19_of_22_limitation_open=True,
        native_equivalence=False,
        whole_mesh_credit=False,
        topology_qualified=False,
        physical_geometry_admitted=False,
        acceleration_qualified=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    result, failure = None, None
    try:
        result = collect(args.output, read(args.plan), args.partial)
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        captured = runtime.capture()
        assert not captured["production_modules_loaded"]
        runtime.write(
            Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "finalization.json",
            dict(
                status="failed" if failure else result["status"],
                failure=failure,
                result=result,
                runtime=captured,
                production_imports_denied=True,
                native_equivalence=False,
                whole_mesh_credit=False,
            ),
        )


if __name__ == "__main__":
    main()
