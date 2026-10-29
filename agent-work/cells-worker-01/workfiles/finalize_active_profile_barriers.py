"""Index completed combined-owner evidence without new numerical work."""

import argparse
import ast
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARENT = Path("/mnt/workspaces/Cells")
TEST = "tests/unit/test_active_profile_barrier_interventions.py"
RUNTIME = (
    "src/cells/core/active_profile_barrier_preparation.py",
    "src/cells/core/surface_active_profile_barrier_interventions_spec.py",
    "src/cells/core/surface_active_profile_barrier_binding.py",
    "src/cells/models/surface_active_profile_barrier_interventions.py",
)
EXPECTED = dict(
    test_complete_preparation_and_parent_initialization=1,
    test_both_stage_coefficients_full_rhs_field_and_energy=18,
    test_disabled_schedules_match_complete_parent_bitwise=2,
    test_four_step_conservation_and_closed_reopened_actual_history=2,
    test_portable_typed_snapshot_fresh_process_and_full_controls=2,
    test_combined_preparation_refuses_mismatched_static_owners=5,
    test_invalid_combined_schedule_refused=16,
    test_both_ramp_bounds_and_actual_history_domain_refuse=1,
    test_explicit_backend_input_admission_without_accelerator_execution=2,
    test_closed_route_view_cannot_hide_invalid_actual_history=2,
)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def record(path):
    return dict(path=str(path), sha256=sha(path))


def functions(path):
    return {
        f.name: ast.dump(f, include_attributes=False)
        for f in ast.parse(path.read_text()).body
        if isinstance(f, (ast.FunctionDef, ast.ClassDef))
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    phases = []
    accepted = {}
    cases = []
    counter = Counter()
    stages = []
    conservation = []
    full_runtime = None
    maximum_rss = 0
    minimum_reserve = None
    current_test = functions(ROOT / TEST)
    for number in (1, 2, 3):
        folder = PARENT / f"active-profile-barriers-development-20261029-{number:02}"
        result = read(folder / "result.json")
        manifest = read(folder / "source-manifest.json")
        assert result["status"] == "passed" and result["changed_frozen_inputs"] == []
        assert result["counts"]["tests"] == {1: 2, 2: 19, 3: 30}[number]
        assert all(result["counts"][k] == 0 for k in ("failures", "errors", "skipped"))
        for relative, expected in manifest["source_sha256"].items():
            assert sha(folder / "workspace" / relative) == expected, relative
        runtime = {k: v for k, v in manifest["source_sha256"].items() if k.startswith("src/")}
        if full_runtime is None:
            full_runtime = runtime
        assert runtime == full_runtime
        for name, value in functions(folder / "workspace" / TEST).items():
            assert current_test[name] == value, name
        resource = read(Path(result["resource_receipt"]))
        assert resource["status"] == "completed" and resource["returncode"] == 0
        assert resource["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert resource["minimum_available_host_memory_bytes"] >= 8 * 2**30
        assert resource["elapsed_seconds"] < 480
        maximum_rss = max(maximum_rss, resource["sampled_peak_process_tree_rss_bytes"])
        minimum_reserve = min(
            minimum_reserve or resource["minimum_available_host_memory_bytes"],
            resource["minimum_available_host_memory_bytes"],
        )
        phase_ids = []
        for case in ET.parse(folder / "tests.xml").getroot().iter("testcase"):
            assert not any(case.find(k) is not None for k in ("failure", "error", "skipped"))
            identity = case.attrib["classname"] + "::" + case.attrib["name"]
            assert identity not in accepted
            counter[case.attrib["name"].split("[")[0]] += 1
            phase_ids.append(identity)
            accepted[identity] = dict(phase=number, junit=record(folder / "tests.xml"))
            cases.append(deepcopy(case))
        phases.append(
            dict(
                number=number,
                result=record(folder / "result.json"),
                inputs=record(folder / "inputs.json"),
                manifest=record(folder / "source-manifest.json"),
                junit=record(folder / "tests.xml"),
                resources=record(Path(result["resource_receipt"])),
                checks=phase_ids,
                private_dispatch=record(folder / "private-dispatch.patch"),
            )
        )
        evidence = folder / "evidence/active-profile-barriers"
        for path in sorted(evidence.glob("stages-*.json")):
            rows = read(path)["comparisons"]
            assert len(rows) == 8
            assert all(row["error_over_budget"] <= 1 for row in rows)
            assert all(
                abs(row["independent"]["physical_energy_balance_pJ_s"]) <= 1e-10 for row in rows
            )
            assert all(abs(row["production_energy_residual_pJ_s"]) <= 1e-10 for row in rows)
            assert all(
                row["independent"]["max_charge_residual_C"] <= 3e-25
                and row["independent"]["max_component_current_residual_A"] <= 1e-23
                for row in rows
            )
            stages.append(
                dict(
                    report=record(path),
                    arrays=record(path.with_suffix(".npz")),
                    comparisons=len(rows),
                    max_rhs_error_over_budget=max(row["error_over_budget"] for row in rows),
                    max_independent_energy_residual_pJ_s=max(
                        abs(row["independent"]["physical_energy_balance_pJ_s"]) for row in rows
                    ),
                    max_production_energy_residual_pJ_s=max(
                        abs(row["production_energy_residual_pJ_s"]) for row in rows
                    ),
                )
            )
        for path in sorted(evidence.glob("conservation-history-*.json")):
            data = read(path)
            assert len(data["independent_conservation"]) == 5 and len(data["clock_probes"]) == 2
            for row in data["independent_conservation"]:
                assert all(abs(v) <= (1e-9 if k == "energy_pJ" else 2e-11) for k, v in row.items())
            conservation.append(dict(report=record(path), arrays=record(path.with_suffix(".npz"))))
    assert (
        counter == EXPECTED and len(accepted) == 51 and len(stages) == 18 and len(conservation) == 2
    )
    owned = {name: full_runtime[name] for name in RUNTIME}
    for name, expected in owned.items():
        assert sha(ROOT / name) == expected
    suite = ET.Element(
        "testsuite",
        name="combined_full56_membrane_barrier_component",
        tests="51",
        errors="0",
        failures="0",
        skipped="0",
    )
    for case in cases:
        suite.append(case)
    ET.ElementTree(suite).write(
        output / "component-tests.xml", encoding="utf-8", xml_declaration=True
    )
    result = dict(
        status="passed_complete_ionic_combined_schedule_component",
        utc=datetime.now(UTC).isoformat(),
        model_id="resolved_active_profile_barriers@1",
        parent_model_id="resolved_tissue@12",
        preparation_kind="cells.active_profile_barrier_preparation@1",
        distinct_checks=51,
        test_categories=dict(counter),
        phases=phases,
        finalized_checks=accepted,
        component_junit=record(output / "component-tests.xml"),
        independent_full_stage_comparisons=144,
        state_fields=20,
        physical_parent_fields=19,
        distinct_channel_laws=56,
        channel_populations=63,
        stages=stages,
        conservation_and_history=conservation,
        accepted_rk4_steps_per_case=4,
        manufactured_history_clock_probes=4,
        max_rhs_error_over_budget=max(row["max_rhs_error_over_budget"] for row in stages),
        max_independent_energy_residual_pJ_s=max(
            row["max_independent_energy_residual_pJ_s"] for row in stages
        ),
        max_production_energy_residual_pJ_s=max(
            row["max_production_energy_residual_pJ_s"] for row in stages
        ),
        owned_runtime_sha256=owned,
        full_executed_runtime_sha256=full_runtime,
        full_frozen_runtime_exact_across_phases=True,
        all_frozen_inventory_files_verified=True,
        retained_test_functions_AST_exact=True,
        all_current_owned_runtime_exact=True,
        resources=dict(
            cpu=6,
            threads=1,
            max_guarded_rss_bytes=maximum_rss,
            min_host_reserve_bytes=minimum_reserve,
            max_unit_seconds=480,
            child_tree_limit_bytes=2**30,
            host_reserve_limit_bytes=8 * 2**30,
        ),
        failed_evidence=[],
        finalizer=record(Path(__file__).resolve()),
        new_long_jobs_launched=False,
        compiled_or_gpu_execution_qualification=False,
        full10us_trajectory_qualification=False,
        init_to_sim_handoff_qualification=False,
        independent_biological_cases=0,
        native_solver_loop_parity=False,
        shared_files_written=False,
        root_public_integration_separate=True,
        automatic_followup=False,
    )
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                distinct_checks=51,
                result=str(output / "result.json"),
                sha256=sha(output / "result.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
