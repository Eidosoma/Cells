"""Index completed immutable barrier evidence without another numerical run."""

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARENT = Path("/mnt/workspaces/Cells")
RUNTIME = (
    "src/cells/core/surface_barrier_interventions_binding.py",
    "src/cells/core/surface_active_barrier_interventions_spec.py",
    "src/cells/core/surface_calcium_barrier_interventions_spec.py",
    "src/cells/core/surface_calcium_energy_barrier_interventions_spec.py",
    "src/cells/models/surface_active_barrier_interventions.py",
    "src/cells/models/surface_calcium_barrier_interventions.py",
    "src/cells/models/surface_calcium_energy_barrier_interventions.py",
)
EXPECTED = dict(
    test_exact_parent_initialization_serialization_and_catalog=3,
    test_complete_stage_field_rhs_energy_and_coefficients=18,
    test_disabled_opening_has_bitwise_exact_full_parent_rhs=9,
    test_duplicate_occurrences_preserve_single_opening=3,
    test_closed_face_keeps_actual_history_and_observations=3,
    test_invalid_full_owner_recipe_and_event_refused=20,
    test_full_step_and_actual_history_admission=3,
    test_short_rk4_uses_stage_clock_with_every_parent_field=3,
)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def reference(path):
    return dict(path=str(path), sha256=sha(path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    phases, runtime, accepted, tests = [], None, {}, []
    counters, stages, closed, smoke = Counter(), [], [], []
    for number in (2, 3, 4, 5):
        folder = PARENT / f"owned-barrier-development-20261029-{number:02}"
        result, manifest = read(folder / "result.json"), read(folder / "source-manifest.json")
        assert result["status"] == ("failed" if number == 3 else "passed")
        assert result["changed_frozen_inputs"] == []
        for name, expected in manifest["source_sha256"].items():
            assert sha(folder / "workspace" / name) == expected, name
        current = {name: manifest["owned_source_sha256"][name] for name in RUNTIME}
        if runtime is None:
            runtime = current
        assert current == runtime
        resource_path = Path(result["resource_receipt"])
        resource = read(resource_path)
        assert resource["limits"]["max_process_tree_rss_bytes"] == 2**30
        assert resource["limits"]["min_available_host_memory_bytes"] == 8 * 2**30
        assert resource["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert resource["minimum_available_host_memory_bytes"] >= 8 * 2**30
        assert resource["elapsed_seconds"] < 480
        passed, failed = [], []
        for case in ET.parse(folder / "tests.xml").getroot().iter("testcase"):
            identity = case.attrib["classname"] + "::" + case.attrib["name"]
            if any(case.find(key) is not None for key in ("failure", "error", "skipped")):
                failed.append(identity)
                continue
            assert identity not in accepted
            accepted[identity] = dict(phase=number, junit=reference(folder / "tests.xml"))
            passed.append(identity)
            counters[case.attrib["name"].split("[")[0]] += 1
            tests.append(deepcopy(case))
        phases.append(
            dict(
                phase=number,
                receipt=reference(folder / "result.json"),
                inputs=reference(folder / "inputs.json"),
                manifest=reference(folder / "source-manifest.json"),
                junit=reference(folder / "tests.xml"),
                resource=reference(resource_path),
                status=result["status"],
                accepted_checks=passed,
                preserved_failures=failed,
            )
        )
        evidence = folder / "evidence/complete-scheduled-barriers"
        for path in sorted(evidence.glob("stages-*.json")):
            record = read(path)
            rows = record["comparisons"]
            assert len(rows) == 5
            assert all(row["error_over_budget"] <= 1 for row in rows)
            assert all(abs(row["energy_residual_pJ_s"]) <= 1e-10 for row in rows)
            assert all(
                abs(row["independent"]["physical_energy_balance_pJ_s"]) <= 1e-10 for row in rows
            )
            assert all(row["independent"]["max_charge_residual_C"] <= 3e-25 for row in rows)
            assert all(
                row["independent"]["max_component_current_residual_A"] <= 1e-23 for row in rows
            )
            stages.append(
                dict(
                    report=reference(path),
                    arrays=reference(path.with_suffix(".npz")),
                    comparisons=len(rows),
                    max_rhs_error_over_budget=max(row["error_over_budget"] for row in rows),
                    max_independent_energy_residual_pJ_s=max(
                        abs(row["independent"]["physical_energy_balance_pJ_s"]) for row in rows
                    ),
                    max_production_energy_residual_pJ_s=max(
                        abs(row["energy_residual_pJ_s"]) for row in rows
                    ),
                )
            )
        for path in sorted(evidence.glob("closed-history-*.json")):
            assert read(path)["all_history_exact"] is True
            closed.append(dict(report=reference(path), arrays=reference(path.with_suffix(".npz"))))
        for path in sorted(evidence.glob("short-rk4-*.json")):
            smoke.append(dict(report=reference(path), arrays=reference(path.with_suffix(".npz"))))
    assert counters == EXPECTED, counters
    assert len(accepted) == 62 and len(stages) == 18 and len(closed) == len(smoke) == 3
    for name, expected in runtime.items():
        assert sha(ROOT / name) == expected, "Live owned runtime changed: " + name
    suite = ET.Element(
        "testsuite",
        name="retained_complete_scheduled_barrier_component",
        tests=str(len(tests)),
        errors="0",
        failures="0",
        skipped="0",
    )
    for case in tests:
        suite.append(case)
    ET.ElementTree(suite).write(
        output / "component-tests.xml", encoding="utf-8", xml_declaration=True
    )
    files = {}
    for phase in phases:
        for key in ("receipt", "inputs", "manifest", "junit", "resource"):
            files[phase[key]["path"]] = phase[key]["sha256"]
    for collection in (stages, closed, smoke):
        for item in collection:
            for key in ("report", "arrays"):
                files[item[key]["path"]] = item[key]["sha256"]
    summary = dict(
        status="passed_complete_parent_barrier_stages_and_contracts",
        utc=datetime.now(UTC).isoformat(),
        distinct_checks=62,
        test_categories=dict(counters),
        component_junit=reference(output / "component-tests.xml"),
        finalized_checks=accepted,
        phases=phases,
        full_independent_stage_comparisons=90,
        stages=stages,
        full_state_fields=dict(ionic=20, calcium=35, energy=39),
        physical_parent_state_fields=dict(ionic=19, calcium=34, energy=38),
        distinct_channel_laws=56,
        channel_populations=63,
        closed_face_history_comparisons=closed,
        four_step_smoke_per_owner=smoke,
        max_rhs_error_over_budget=max(row["max_rhs_error_over_budget"] for row in stages),
        max_independent_energy_residual_pJ_s=max(
            row["max_independent_energy_residual_pJ_s"] for row in stages
        ),
        max_production_energy_residual_pJ_s=max(
            row["max_production_energy_residual_pJ_s"] for row in stages
        ),
        executed_owned_runtime_sha256=runtime,
        full_frozen_inventory_files_verified=True,
        executed_owned_runtime_exact_across_phases_and_current=True,
        preserved_initial_failures=[
            reference(PARENT / f"owned-barrier-development-20261029-{n:02}" / "result.json")
            for n in (1, 3)
        ],
        test_input_corrections=[
            "Model identity assertion uses serialized identity; typed model has no id field.",
            "Manufactured noninitial calcium K transfer includes its chemical cytosol ownership.",
            "Reseal fixture closes Na TJ coefficients; other ions preserve return paths.",
        ],
        retained_input_scope=(
            "Passed partial/asymmetric stages retain their original captured inputs. "
            "The corrected reseal input and corrected noninitial calcium states were qualified "
            "only after those fixture corrections. No product equation or numerical budget changed."
        ),
        public_integration_tests_rerun=False,
        previous_qualification_tests_rerun=False,
        long_transient_qualification=False,
        two_dt_refinement_qualification=False,
        compiled_or_gpu_execution_qualification=False,
        native_solver_loop_parity=False,
        independent_biological_cases=0,
        limits=dict(
            cpu=3,
            threads=1,
            max_child_tree_rss_bytes=2**30,
            min_host_reserve_bytes=8 * 2**30,
            max_unit_wall_seconds=420,
        ),
        evidence_sha256=files,
        finalizer=reference(Path(__file__).resolve()),
        shared_files_written=False,
        automatic_followup=False,
    )
    (output / "result.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status=summary["status"],
                distinct_checks=62,
                result=str(output / "result.json"),
                sha256=sha(output / "result.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
