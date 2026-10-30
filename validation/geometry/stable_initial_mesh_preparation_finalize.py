"""Bounded, production-denied audit of all declared bridge verdicts."""

import argparse
import json
import os
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from validation.geometry import stable_initial_mesh_preparation_runtime as runtime

runtime.deny_production(extra=("numpy", "scipy", "PIL"))


def read(path):
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Mesh controller metadata exceeds 16 MiB")
    with path.open() as handle:
        return json.load(handle)


def verify_runtime(value, files, plan, *, actual):
    assert value["affinity"] == [6]
    assert value["pytest_version"] == plan["pytest_version"]
    assert all(v == "1" for v in value["threads"].values())
    assert not value["file_errors"] and not value["mapped_file_errors"]
    if not actual:
        assert not value["denied_production_modules_loaded"]
    for name, expected in value["files"].items():
        if name in files:
            assert files[name] == expected, name
        else:
            assert len(files) < 20000
            assert runtime.inventory.sha(name) == expected, name
            files[name] = expected


def collect(out, plan, *, partial):
    checks, replays, verdicts, errors, files = [], [], [], [], {}
    available = set()
    unit_outcomes = read(out / "unit-outcomes.json")
    expected = plan["check_units"] + plan["replay_units"]
    assert set(unit_outcomes) <= {row["unit"] for row in expected}

    def error(unit, failure):
        errors.append(dict(unit=unit, type=type(failure).__name__, message=str(failure)))

    for unit in plan["check_units"]:
        label = unit["unit"]
        folder = out / "evidence" / label
        try:
            outcome = unit_outcomes[label]
            xml = out / "units" / label / "tests.xml"
            assert xml.stat().st_size <= 16 * 2**20
            cases = ET.parse(xml).getroot().findall(".//testcase")
            assert len(cases) == 1
            case = cases[0]
            observed = dict(classname=case.get("classname"), name=case.get("name"))
            assert observed == unit["pytest_id"]
            failed = any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
            captured = read(folder / "runtime.json")
            verify_runtime(captured, files, plan, actual=True)
            assert int(captured["exitstatus"]) == (1 if failed else 0)
            assert outcome["status"] == ("assertion_failed" if failed else "passed")
            checks.append(
                dict(
                    unit=label,
                    pytest_id=observed,
                    role=unit["role"],
                    case=unit["case"],
                    passed=not failed,
                )
            )
            if unit["role"] in ("mesh", "raw"):
                evidence = folder / "stable-initial-mesh"
                for suffix in ("-actual.json", "-actual.npz", "-outcome.json"):
                    assert (evidence / (unit["case"] + suffix)).is_file()
                available.add(unit["case"])
                summary = read(evidence / (unit["case"] + "-summary.json"))
                assert summary["case"] == unit["case"]
                assert not summary["exact_native_arithmetic_equivalence"]
                assert (
                    not summary["physical_geometry_admitted"] and not summary["topology_qualified"]
                )
                verdicts.append(
                    dict(
                        case=unit["case"],
                        status=summary["status"],
                        conditional_source=summary["source_comparison"],
                        primitive_comparisons=summary["primitive_comparisons"],
                        whole_mesh=summary["whole_mesh"],
                    )
                )
        except Exception as failure:
            error(label, failure)
    for unit in plan["replay_units"]:
        label = unit["unit"]
        folder = out / "evidence" / label
        try:
            outcome = unit_outcomes[label]
            result = read(folder / "replay-result.json")
            assert result["case"] == unit["case"] and result["lane"] == unit["lane"]
            assert result["production_imports_denied"]
            assert not result["exact_native_arithmetic_equivalence"]
            assert not result["physical_geometry_admitted"] and not result["topology_qualified"]
            verify_runtime(result["runtime"], files, plan, actual=False)
            source = out / "evidence" / unit["source_check"] / "stable-initial-mesh"
            assert (
                runtime.inventory.sha(source / (unit["case"] + "-actual.json"))
                == result["source_actual_sha256"]
            )
            assert (
                runtime.inventory.sha(source / (unit["case"] + "-actual.npz"))
                == result["source_arrays_sha256"]
            )
            passed = result["status"] == "passed"
            assert outcome["status"] == ("passed" if passed else "assertion_failed")
            if unit["lane"] == "conditional-source":
                row = result["row"]
                if row is not None:
                    assert row["conditional_source_equivalence"]
                    assert row["full_typed_caches_and_rng_exact_given_tape"]
            else:
                verdict = folder / (unit["case"] + "-geometry-verdict.json")
                row = read(verdict) if verdict.exists() else result["row"]
            replays.append(
                dict(
                    unit=label,
                    case=unit["case"],
                    lane=unit["lane"],
                    passed=passed,
                    failure=result["failure"],
                    row=row,
                )
            )
        except Exception as failure:
            error(label, failure)
    complete = len(checks) == 32 and len(replays) == 22
    if not partial:
        assert len(plan["check_units"]) == 32 and len(plan["replay_units"]) == 22
        assert {(row["pytest_id"]["classname"], row["pytest_id"]["name"]) for row in checks} == {
            (row["classname"], row["name"]) for row in plan["expected_pytest_ids"]
        }
        assert available == set(plan["mesh_cases"] + plan["raw_cases"])
    passed = complete and not errors and all(row["passed"] for row in checks + replays)
    return dict(
        status="passed" if passed else "partial" if partial else "candidate_checks_failed",
        all_declared_units_audited=complete,
        checks=checks,
        replay_cases=replays,
        mesh_verdicts=verdicts,
        metadata_errors=errors,
        passed_checks=sum(row["passed"] for row in checks),
        passed_conditional_source_records=sum(
            row["passed"] for row in replays if row["lane"] == "conditional-source"
        ),
        passed_independent_geometry_records=sum(
            row["passed"] for row in replays if row["lane"] == "geometry"
        ),
        runtime_files_verified=len(files),
        ordinary_failures_not_retried=True,
        physical_geometry_admitted=False,
        exact_native_arithmetic_equivalence=False,
        topology_qualified=False,
        original_19_of_22_limitation_open=True,
        original_failed_evidence_preserved=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    result, failure = None, None
    try:
        result = collect(args.output, read(args.plan), partial=args.partial)
    except BaseException as error:
        failure = dict(
            type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
        )
        raise
    finally:
        captured = runtime.capture()
        assert not captured["production_modules_loaded"]
        runtime.inventory.write(
            Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "finalization.json",
            dict(
                status="failed" if failure else "completed",
                failure=failure,
                result=result,
                runtime=captured,
                production_imports_denied=True,
                exact_native_arithmetic_equivalence=False,
                physical_geometry_admitted=False,
                topology_qualified=False,
            ),
        )


if __name__ == "__main__":
    main()
