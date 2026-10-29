"""Verify existing scheduled water/repair evidence and export its bounded handoff."""

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("joint-water-profiles-handoff-")
    report, inputs = (read(component / n) for n in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=53, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert not report["workspace_sources_changed_during_checks"]
    nodes = []
    for path in component.glob("*-tests.xml"):
        for case in ET.parse(path).getroot().iter("testcase"):
            assert all(case.find(k) is None for k in ("failure", "error", "skipped"))
            nodes.append(case.attrib["classname"] + "::" + case.attrib["name"])
    assert len(nodes) == len(set(nodes)) == 53
    for name, expected in report["output_sha256"].items():
        assert sha(component / name) == expected, name
    for name, expected in report["source_sha256"].items():
        assert sha(ROOT / name) == expected, name
    protocol = read(ROOT / "validation/topology/joint_water_profile_interventions_protocol.json")
    for name, expected in protocol["readonly_source_sha256"].items():
        actual_root = component / "workspace" if name.startswith("src/") else ROOT
        assert sha(actual_root / name) == expected, name
    frozen = protocol["frozen_workspace"]
    for p, s in (("manifest", "manifest_sha256"), ("handoff_receipt", "handoff_receipt_sha256")):
        assert sha(Path(frozen[p])) == frozen[s]
    manifest_path = component / "workspace-manifest.json"
    assert sha(manifest_path) == report["workspace_manifest_sha256"]
    manifest = read(manifest_path)
    assert len(manifest["overlay_source_sha256"]) == 5
    assert not manifest["shared_files_written"] and not manifest["current_shared_engine_used"]
    assert set(manifest["only_test_dispatch_changed"]) == {
        "src/cells/core/specs.py",
        "src/cells/core/schedule.py",
        "src/cells/models/registry.py",
        "src/cells/ensemble/ionic.py",
        "src/cells/core/tissue_profile_composition_preparation.py",
    }
    for name, expected in manifest["source_sha256"].items():
        assert sha(component / "workspace" / name) == expected, name
        if name in manifest["overlay_source_sha256"]:
            assert sha(component / "sources" / name) == expected
        elif name not in manifest["only_test_dispatch_changed"]:
            assert expected == manifest["qualified_base_source_sha256"][name]
    assert inputs["affinity"] == [4]
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    assert inputs["environment"]["JAX_ENABLE_COMPILATION_CACHE"] == "false"
    guards = {}
    retained = report.get("retained_finalized_runs", [])
    if retained:
        assert sum(r["finalized_tests"] for r in retained) == 49
        for i, row in enumerate(retained):
            assert not row["rerun"] and sha(Path(row["receipt"])) == row["receipt_sha256"]
            for name, value in row["resources"].items():
                assert value["status"] == "completed" and value["returncode"] == 0
                assert value["sampled_peak_process_tree_rss_bytes"] <= 2**30
                assert value["minimum_available_host_memory_bytes"] >= 8 * 2**30
                guards["retained-" + str(i) + "-" + name] = value
    for row in report["checks"]:
        assert row["exit_code"] == 0 and row["wall_seconds"] < 480
        path = component / (row["name"] + "-guard/result.json")
        value = read(path)
        assert value["status"] == "completed" and value["returncode"] == 0
        assert value["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert value["minimum_available_host_memory_bytes"] >= 8 * 2**30
        guards[row["name"]] = value
    records = {}
    for path in sorted((component / "evidence").glob("*.json")):
        value = read(path)
        assert value["status"] == "passed", path
        records[path.stem.removeprefix("joint-water-profiles-")] = value
    assert len(records) == 53
    stages = [row for value in records.values() for row in value.get("stages", [])]
    assert len(stages) == 100 and all(row["error_over_budget"] <= 1 for row in stages)
    arrays = {}
    trajectories = {}
    for family, count in (("water", 44), ("repair", 49)):
        for case in ("SIM", "close-reopen"):
            label = family + "-" + case
            record = records["trajectory-" + label]
            assert (
                record["all_observations_compared"] and record["original_material_and_work_ledgers"]
            )
            assert record["reported_state_and_balances_from_actual_history"]
            assert record["resolved_background_transfer_refinement"]
            assert record["trajectory_layout"] == "compact; padding qualified separately at stages"
            assert not record["endpoint_only_claim"] and not record["convergence_order_claim"]
            assert all(r["error_over_budget"] <= 1 for r in record["refinements"])
            assert all(
                max(map(abs, r["independent_energy_residual_pJ"])) <= 1e-9
                for r in record["refinements"]
            )
            coarse, fine = [r["background_transfer_error_fmol"] for r in record["refinements"]]
            assert coarse > 1e-20 and fine <= 0.35 * coarse + 1e-22
            path = component / "evidence" / record["arrays_file"]
            with np.load(path, allow_pickle=False) as data:
                times = data["times_s"]
                np.testing.assert_array_equal(times, record["observation_times_s"])
                assert len(data["state_fields"]) == count
                assert (
                    data["reference_flat"].shape
                    == data["production_flat_1"].shape
                    == data["production_flat_2"].shape
                )
                assert data["reference_flat"].shape[0] == len(times)
                for prefix in ("1__", "2__"):
                    keys = [k for k in data.files if k.startswith(prefix)]
                    assert len(keys) == count
                    assert all(data[k].shape[0] == len(times) for k in keys)
                    assert all(np.isfinite(data[k]).all() for k in keys)
                raw = record["inputs"]
                assert set(raw["experiment"]["observation_times"]) <= set(times)
                for name, groups in raw["experiment"].items():
                    if name.endswith("_controls"):
                        for row in groups:
                            for entry in row["controls" if "controls" in row else "schedule"]:
                                assert entry["time"] in times, (label, name, entry["time"])
            arrays[label] = dict(
                path=str(path),
                sha256=sha(path),
                fields=count,
                observations=len(times),
                layout="compact",
            )
            trajectories[label] = record
    for row in stages:
        assert abs(row["energy_rate_residual_pJ_s"]) < 1e-10
        assert abs(row["independent"]["physical_energy_balance_pJ_s"]) < 1e-10
    output.mkdir(exist_ok=False)
    examples = {}
    for family, name in (("water", "stages-water-SIM"), ("repair", "stages-repair-SIM")):
        folder = output / "examples" / family
        folder.mkdir(parents=True)
        write(folder / "definition.json", records[name]["inputs"])
        write(
            folder / "trajectory-definition.json",
            records["trajectory-" + family + "-SIM"]["inputs"],
        )
        examples[family] = {p.name: sha(p) for p in folder.iterdir()}
    for source, name in (
        (
            ROOT / "validation/topology/joint_water_profile_interventions_protocol.json",
            "protocol.json",
        ),
        (Path(__file__), "finalize.py"),
    ):
        shutil.copyfile(source, output / name)
    result = dict(
        status="passed",
        models=protocol["supported_owners"],
        tests=report["tests"],
        unique_check_ids=nodes,
        retained_finalized_runs=retained,
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        verified_component_artifacts=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        executed_runtime_source_sha256=report["executed_runtime_source_sha256"],
        live_shared_source_sha256=report["live_shared_source_sha256"],
        live_shared_sources_changed_during_checks=report[
            "live_shared_sources_changed_during_checks"
        ],
        live_source_changes_during_checks=report["live_source_changes_during_checks"],
        independent_full_stage_comparisons=100,
        maximum_stage_error_over_budget=max(r["error_over_budget"] for r in stages),
        complete_state_fields=dict(water=44, repair=49),
        unchanged_parent_physical_fields=dict(water=43, repair=48),
        scheduled_scope=(
            "fresh INIT/SIM background membrane D; explicit clock; no phase transition bridge"
        ),
        trajectory_layout="compact; padding tested separately at initial/manufactured stages",
        all_channel_laws=56,
        full_observation_trajectories=trajectories,
        retained_arrays=arrays,
        resources=guards,
        examples=examples,
        original_v1_sources_edited=False,
        shared_sources_edited=False,
        scientific_tolerances_relaxed=False,
        endpoint_only_trajectory_claim=False,
        convergence_order_claim=False,
        compiled_or_gpu_qualified=False,
        stochastic_history_or_new_repair_energetics_qualified=False,
        automatic_followup=False,
    )
    result["handoff_artifact_sha256"] = {
        str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()
    }
    write(output / "result.json", result)
    print(
        json.dumps(
            dict(
                status="passed",
                receipt=str(output / "result.json"),
                sha256=sha(output / "result.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
