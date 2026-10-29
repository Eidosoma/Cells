"""Consolidate completed calcium/fuel checks without importing numerical models.

Every queued group must already have passed. Missing, repeated, skipped, stale
or incomplete evidence is refused before creating the handoff directory.
"""

import argparse
import ast
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARENT = Path("/mnt/workspaces/Cells")
TEST = "tests/unit/test_owned_calcium_profile_barriers.py"
RUNTIME = (
    "src/cells/core/owned_calcium_profile_barrier_preparation.py",
    "src/cells/core/owned_calcium_profile_barrier_binding.py",
    "src/cells/core/surface_calcium_profile_barrier_interventions_spec.py",
    "src/cells/core/surface_calcium_energy_profile_barrier_interventions_spec.py",
    "src/cells/models/surface_calcium_profile_barrier_interventions.py",
    "src/cells/models/surface_calcium_energy_profile_barrier_interventions.py",
)
REFERENCES = (
    "validation/transport/owned_calcium_profile_barrier_fixtures.py",
    "validation/transport/owned_calcium_profile_barrier_reference.py",
)
GROUP_COUNTS = (4, 2, 8, 9, 8, 9, 25, 25)
EXPECTED = {
    "test_complete_parent_identity_initialization_and_artifact": 2,
    "test_full_stage_all_stores_gates_actual_fuel_and_both_coefficients": 36,
    "test_disabled_matches_exact_full_parent_bitwise": 4,
    "test_exact_single_schedule_reductions_keep_full_owner": 4,
    "test_four_step_conservation_actual_pool_and_closed_history": 4,
    "test_portable_snapshots_full_controls_and_recipe": 4,
    "test_old_calcium_membrane_runtime_is_never_used": 2,
    "test_mismatched_full_owner_or_schedule_refused": 28,
    "test_closed_history_corruption_and_both_step_bounds_refuse": 4,
    "test_strong_background_sum_boundary_keeps_full_chemical_and_fuel_guards": 2,
}
PARENTS = {"calcium": "resolved_calcium@11", "energy": "resolved_calcium_energy@5"}
FIELDS = {"calcium": 35, "energy": 39}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def record(path):
    return {"path": str(path), "sha256": sha(path)}


def functions(path):
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.parse(path.read_text()).body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }


def held_times(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "time":
                yield item
            else:
                yield from held_times(item)
    elif isinstance(value, list):
        for item in value:
            yield from held_times(item)


def expected_clocks(definition):
    model, experiment = definition["model"], definition["experiment"]
    values = {0.0, experiment["end_time"], *held_times(experiment)}
    events = list(model["membrane_interventions"])
    if model["barrier_intervention"] is not None:
        events.append(model["barrier_intervention"])
    for event in events:
        values.update((event["on_s"], (event["on_s"] + event["off_s"]) / 2, event["off_s"]))
    return sorted(values)


def collect():
    phases, cases, stages, conservation, boundaries = [], [], [], [], []
    accepted, full_runtime = {}, None
    counter = Counter()
    maximum_rss, minimum_reserve = 0, None
    current_test = functions(ROOT / TEST)
    for number, count in enumerate(GROUP_COUNTS, 1):
        folder = PARENT / f"owned-calcium-profile-barriers-development-20261029-{number:02}"
        require(
            (folder / "result.json").is_file(),
            f"Incomplete qualification: missing {folder}/result.json",
        )
        result, manifest = read(folder / "result.json"), read(folder / "source-manifest.json")
        require(
            result["status"] == "passed" and not result["changed_frozen_inputs"],
            f"Failed or changed group {number}",
        )
        require(
            result["counts"] == {"tests": count, "errors": 0, "failures": 0, "skipped": 0},
            f"Wrong check counts in group {number}",
        )
        require(sha(folder / "inputs.json") == result["inputs_sha256"], f"Changed inputs {number}")
        require(
            sha(folder / "source-manifest.json") == result["source_manifest_sha256"],
            f"Changed manifest {number}",
        )
        for relative, expected in manifest["source_sha256"].items():
            require(
                sha(folder / "workspace" / relative) == expected,
                f"Changed frozen source {number}: {relative}",
            )
        runtime = {k: v for k, v in manifest["source_sha256"].items() if k.startswith("src/")}
        if full_runtime is None:
            full_runtime = runtime
        require(runtime == full_runtime, f"Executed runtime differs in group {number}")
        require(
            functions(folder / "workspace" / TEST) == current_test,
            f"Retained test functions differ {number}",
        )
        for relative in REFERENCES:
            require(
                sha(ROOT / relative) == manifest["source_sha256"][relative],
                f"Changed reference: {relative}",
            )
        resource_path = Path(result["resource_receipt"])
        resource = read(resource_path)
        require(
            resource["status"] == "completed" and resource["returncode"] == 0,
            f"Resource failure {number}",
        )
        require(resource["sampled_peak_process_tree_rss_bytes"] <= 2**30, f"RSS limit {number}")
        require(
            resource["minimum_available_host_memory_bytes"] >= 8 * 2**30, f"Host reserve {number}"
        )
        require(resource["elapsed_seconds"] < 480, f"Time limit {number}")
        maximum_rss = max(maximum_rss, resource["sampled_peak_process_tree_rss_bytes"])
        minimum_reserve = min(
            minimum_reserve or resource["minimum_available_host_memory_bytes"],
            resource["minimum_available_host_memory_bytes"],
        )
        phase_ids = []
        for case in ET.parse(folder / "tests.xml").getroot().iter("testcase"):
            require(
                not any(case.find(k) is not None for k in ("failure", "error", "skipped")),
                f"Unaccepted JUnit case {number}",
            )
            identity = case.attrib["classname"] + "::" + case.attrib["name"]
            require(identity not in accepted, f"Repeated check: {identity}")
            counter[case.attrib["name"].split("[")[0]] += 1
            phase_ids.append(identity)
            accepted[identity] = {"phase": number, "junit": record(folder / "tests.xml")}
            cases.append(deepcopy(case))
        require(len(phase_ids) == count, f"JUnit count differs {number}")
        phases.append(
            {
                "number": number,
                "checks": phase_ids,
                **{
                    key: record(path)
                    for key, path in {
                        "result": folder / "result.json",
                        "inputs": folder / "inputs.json",
                        "manifest": folder / "source-manifest.json",
                        "junit": folder / "tests.xml",
                        "resources": resource_path,
                        "private_dispatch": folder / "private-dispatch.patch",
                    }.items()
                },
            }
        )
        evidence = folder / "evidence/owned-calcium-profile-barriers"
        for path in sorted(evidence.glob("stages-*.json")):
            data = read(path)
            family = path.name.split("-")[1]
            rows = data["comparisons"]
            require(data["complete_fields"] == FIELDS[family], f"Incomplete state: {path}")
            require(
                [row["time_s"] for row in rows] == expected_clocks(data["definition"]),
                f"Missing stage clocks: {path}",
            )
            require(
                all(
                    math.isfinite(row["error_over_budget"]) and row["error_over_budget"] <= 1
                    for row in rows
                ),
                f"Stage error: {path}",
            )
            require(
                all(
                    abs(row["independent"]["physical_energy_balance_pJ_s"]) <= 1e-10
                    and abs(row["production_energy_residual_pJ_s"]) <= 1e-10
                    for row in rows
                ),
                f"Stage energy: {path}",
            )
            require(
                all(
                    row["independent"]["max_charge_residual_C"] <= 3e-25
                    and row["independent"]["max_component_current_residual_A"] <= 1e-23
                    for row in rows
                ),
                f"Stage charge/current: {path}",
            )
            stages.append(
                {
                    "family": family,
                    "report": record(path),
                    "arrays": record(path.with_suffix(".npz")),
                    "comparisons": len(rows),
                    "max_rhs_error_over_budget": max(row["error_over_budget"] for row in rows),
                    "max_independent_energy_residual_pJ_s": max(
                        abs(row["independent"]["physical_energy_balance_pJ_s"]) for row in rows
                    ),
                    "max_production_energy_residual_pJ_s": max(
                        abs(row["production_energy_residual_pJ_s"]) for row in rows
                    ),
                }
            )
        for path in sorted(evidence.glob("conservation-*.json")):
            data = read(path)
            require(
                len(data["independent_conservation"]) == 5 and len(data["clock_probes"]) == 2,
                f"Incomplete conservation/history: {path}",
            )
            require(
                all(
                    abs(value) <= (1e-9 if key == "energy_pJ" else 2e-11)
                    for row in data["independent_conservation"]
                    for key, value in row.items()
                ),
                f"Conservation failure: {path}",
            )
            conservation.append(
                {"report": record(path), "arrays": record(path.with_suffix(".npz"))}
            )
        for path in sorted(evidence.glob("background-boundary-*.json")):
            data = read(path)
            family = path.stem.removeprefix("background-boundary-")
            require(data["parent_model_id"] == PARENTS[family], f"Wrong guard owner: {path}")
            require(
                data["limit"] == 0.25 and data["below_product"] < 0.25 < data["above_product"],
                f"Missing guard boundary: {path}",
            )
            require(
                data["sum_bound_s"]
                == data["background_bound_s"] + data["full_chemical_or_bounded_fuel_bound_s"],
                f"Incomplete guard sum: {path}",
            )
            require(
                data["inherited_parent_guards_kept"] and data["ramp_guards_kept"],
                f"Missing inherited guards: {path}",
            )
            boundaries.append(record(path))
    require(counter == EXPECTED and len(accepted) == 90, "Incomplete distinct check categories")
    require(
        len(stages) == 36 and len(conservation) == 4 and len(boundaries) == 2,
        "Incomplete scientific reports",
    )
    owned = {name: full_runtime[name] for name in RUNTIME}
    for name, expected in owned.items():
        require(sha(ROOT / name) == expected, f"Current owned source changed: {name}")
    return cases, {
        "status": "passed_complete_calcium_fuel_combined_schedule_component",
        "utc": datetime.now(UTC).isoformat(),
        "model_ids": [
            "resolved_calcium_profile_barriers@1",
            "resolved_calcium_energy_profile_barriers@1",
        ],
        "parent_model_ids": list(PARENTS.values()),
        "preparation_kind": "cells.calcium_profile_barrier_preparation@1",
        "distinct_checks": 90,
        "test_categories": dict(counter),
        "phases": phases,
        "finalized_checks": accepted,
        "independent_full_stage_comparisons": sum(row["comparisons"] for row in stages),
        "state_fields": FIELDS,
        "physical_parent_fields": {k: v - 1 for k, v in FIELDS.items()},
        "distinct_channel_laws": 56,
        "channel_populations": 63,
        "stages": stages,
        "conservation_and_history": conservation,
        "summed_background_guard_boundaries": boundaries,
        "accepted_rk4_steps_per_case": 4,
        "conservation_samples": 20,
        "manufactured_history_clock_probes": 8,
        "max_rhs_error_over_budget": max(row["max_rhs_error_over_budget"] for row in stages),
        "max_independent_energy_residual_pJ_s": max(
            row["max_independent_energy_residual_pJ_s"] for row in stages
        ),
        "max_production_energy_residual_pJ_s": max(
            row["max_production_energy_residual_pJ_s"] for row in stages
        ),
        "owned_runtime_sha256": owned,
        "full_executed_runtime_sha256": full_runtime,
        "full_frozen_runtime_exact_across_phases": True,
        "all_frozen_inventory_files_verified": True,
        "retained_test_functions_AST_exact": True,
        "all_current_owned_runtime_exact": True,
        "resources": {
            "cpu": 6,
            "threads": 1,
            "max_guarded_rss_bytes": maximum_rss,
            "min_host_reserve_bytes": minimum_reserve,
            "max_unit_seconds": 480,
            "child_tree_limit_bytes": 2**30,
            "host_reserve_limit_bytes": 8 * 2**30,
        },
        "finalizer": record(Path(__file__).resolve()),
        "new_numerical_work_performed": False,
        "new_long_jobs_launched": False,
        "compiled_or_gpu_execution_qualification": False,
        "full10us_trajectory_qualification": False,
        "init_to_sim_handoff_qualification": False,
        "independent_biological_cases": 0,
        "native_solver_loop_parity": False,
        "shared_files_written": False,
        "root_public_integration_separate": True,
        "automatic_followup": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cases, result = collect()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    suite = ET.Element(
        "testsuite",
        name="complete_calcium_fuel_combined_schedule_component",
        tests="90",
        errors="0",
        failures="0",
        skipped="0",
    )
    suite.extend(cases)
    ET.ElementTree(suite).write(
        output / "component-tests.xml", encoding="utf-8", xml_declaration=True
    )
    result["component_junit"] = record(output / "component-tests.xml")
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "distinct_checks": 90,
                "result": str(output / "result.json"),
                "sha256": sha(output / "result.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
