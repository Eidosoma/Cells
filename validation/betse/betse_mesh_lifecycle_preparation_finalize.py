"""Guarded streaming evidence verification; never aggregate full trace records."""

import argparse
import json
import math
import os
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from validation.betse import betse_initial_mesh_preparation_replay as transport
from validation.betse import betse_mesh_lifecycle_preparation_report as coverage

MAX_METADATA_BYTES = 16 * 2**20
MAX_RUNTIME_FILES = 20000
OVERLAY = Path("/mnt/workspaces/Cells/pillow-overlay-12.3.0-20261030-01")
PACKAGES = dict(numpy="2.5.3", scipy="1.18.1", jax="0.11.1", jaxlib="0.11.1", pillow="12.3.0")


def read_small(path):
    if path.stat().st_size > MAX_METADATA_BYTES:
        raise ValueError("Metadata exceeds the bounded JSON domain: " + str(path))
    with path.open() as handle:
        return json.load(handle)


def verify_runtime(value, seen, *, pytest):
    assert value["affinity"] == [6]
    assert not value["file_errors"] and not value["package_errors"]
    assert value["packages"] == (
        PACKAGES if pytest else {k: PACKAGES[k] for k in ("numpy", "scipy")}
    )
    if pytest:
        assert value["exitstatus"] == 0 and value["backend"] == "cpu"
        assert value["backend_error"] is None and value["package_inventory_complete"]
        assert all(v == "1" for v in value["threads"].values())
        for name, origin in value["module_origins"].items():
            assert Path(origin).is_relative_to(OVERLAY), name
        if "PIL.Image" in value["module_origins"]:
            assert value["module_origins"]["PIL.Image"] == str(OVERLAY / "PIL/Image.py")
    for name, expected in value["files"].items():
        if name in seen:
            assert seen[name] == expected, name
        else:
            assert len(seen) < MAX_RUNTIME_FILES
            assert transport.sha(name) == expected, name
            seen[name] = expected


def collect(out, plan, *, partial):
    checks, replays, cases, errors, seen = [], [], [], [], {}

    def failure(path, error):
        errors.append(dict(path=str(path), type=type(error).__name__, message=str(error)))
        if not partial:
            raise error

    for unit in plan["check_units"]:
        xml = out / "units" / unit["unit"] / "tests.xml"
        evidence = out / "evidence" / unit["unit"]
        try:
            if xml.stat().st_size > MAX_METADATA_BYTES:
                raise ValueError("JUnit metadata exceeds the bounded domain")
            rows = ET.parse(xml).getroot().findall(".//testcase")
            assert len(rows) == 1
            row = rows[0]
            assert (row.get("classname"), row.get("name")) == (
                unit["pytest_id"]["classname"],
                unit["pytest_id"]["name"],
            )
            assert all(row.find(tag) is None for tag in ("failure", "error", "skipped"))
            runtime = read_small(evidence / "runtime.json")
            verify_runtime(runtime, seen, pytest=True)
            del runtime
            checks.append(unit["pytest_id"])
        except Exception as error:
            failure(xml, error)
        actual_paths = sorted((evidence / "mesh-lifecycle").glob("*-actual.json"))
        if not partial:
            assert {p.stem.removesuffix("-actual") for p in actual_paths} == set(
                unit["actual_cases"]
            )
        for path in actual_paths:
            try:
                cases.append(coverage.inspect_record(path))
            except Exception as error:
                failure(path, error)

    for unit in plan["replay_units"]:
        path = out / "evidence" / unit["unit"] / "replay-result.json"
        try:
            value = read_small(path)
            assert value["status"] == "passed" and value["failure"] is None
            assert value["mode"] == unit["mode"] and value["case"] == unit["case"]
            assert value["production_imports_denied"] and not value["loaded_production_modules"]
            assert not value["topology_qualified"] and not value["physical_geometry_admitted"]
            verify_runtime(value["runtime"], seen, pytest=False)
            row = value["row"]
            assert row["case"] == unit["case"] and row["role"] == unit["role"]
            if unit["mode"] == "native":
                assert row["full_native_typed_trace_exact"]
            elif unit["role"] in ("mesh", "helper"):
                assert (
                    math.isfinite(row["maximum_error_fraction"])
                    and row["maximum_error_fraction"] <= 1
                )
                assert (
                    math.isfinite(row["maximum_reference_resolution_fraction"])
                    and row["maximum_reference_resolution_fraction"] <= 0.1
                )
            elif unit["role"] == "raw_helper":
                assert not row["independent_numerical_target_claim"]
            else:
                assert row["outcome"] == "refusal_domain_verified"
            replays.append(dict(unit=unit["unit"], mode=unit["mode"], **row))
            del value
        except Exception as error:
            failure(path, error)
    if not partial:
        assert len(checks) == len({(r["classname"], r["name"]) for r in checks}) == 39
        assert {(r["classname"], r["name"]) for r in checks} == {
            (r["classname"], r["name"]) for r in plan["expected_pytest_ids"]
        }
        assert len(replays) == 54
        for mode in ("native", "reference"):
            for role in ("mesh", "helper", "raw_helper"):
                selected = [r["case"] for r in replays if r["mode"] == mode and r["role"] == role]
                assert len(selected) == len(set(selected)) and set(selected) == set(
                    plan["case_roster"][role]
                )
        assert {r["case"] for r in replays if r["role"] == "reference_domain"} == set(
            plan["reference_domain_cases"]
        )
        assert len(cases) == 28
        for role in ("mesh", "helper", "raw_helper", "ancillary"):
            selected = [r["case"] for r in cases if r["role"] == role]
            assert len(selected) == len(set(selected)) and set(selected) == set(
                plan["case_roster"][role]
            )
    whole = [r for r in cases if r["role"] == "mesh"]
    keys = whole[0]["counts"] if whole else ()
    branches = whole[0]["observed_branches"] if whole else ()
    return dict(
        status="partial" if partial else "passed",
        checks=checks,
        replay_cases=replays,
        observed_cases=cases,
        errors=errors,
        whole_pipeline_observed_counts={key: sum(r["counts"][key] for r in whole) for key in keys},
        whole_pipeline_observed_branch_cases={
            key: sum(r["observed_branches"][key] for r in whole) for key in branches
        },
        runtime_files_verified=len(seen),
        maximum_error_fraction=max(
            (r["maximum_error_fraction"] for r in replays if "maximum_error_fraction" in r),
            default=None,
        ),
        maximum_reference_resolution_fraction=max(
            (
                r["maximum_reference_resolution_fraction"]
                for r in replays
                if "maximum_reference_resolution_fraction" in r
            ),
            default=None,
        ),
        whole_pipeline_cases=len(whole),
        manufactured_helpers_are_whole_pipeline=False,
        only_observed_branches_receive_scope_credit=True,
        declared_cases_do_not_guarantee_coverage=True,
        metadata_file_limit_bytes=MAX_METADATA_BYTES,
        upstream_initial_qualification="19/22 accuracy qualification open",
        new_initial_or_clipping_qualification_credit=False,
        topology_qualified=False,
        physical_geometry_admitted=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    failure, result = None, None
    try:
        assert not transport.runtime()["loaded_production_modules"]
        result = collect(args.output, read_small(args.plan), partial=args.partial)
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        runtime = transport.runtime()
        transport.write(
            Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "finalization",
            dict(
                status="failed" if failure else result["status"],
                failure=failure,
                result=result,
                production_imports_denied=True,
                loaded_production_modules=runtime.pop("loaded_production_modules"),
                runtime=runtime,
                topology_qualified=False,
                physical_geometry_admitted=False,
            ),
        )


if __name__ == "__main__":
    main()
