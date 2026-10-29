"""Verify existing full56 water/repair component evidence and export its handoff."""

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
    assert output.name.startswith("joint-water-hcn-handoff-")
    report, inputs = (read(component / n) for n in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=46, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert not report["workspace_sources_changed_during_checks"]
    nodes = []
    for path in component.glob("*-tests.xml"):
        for case in ET.parse(path).getroot().iter("testcase"):
            assert all(case.find(k) is None for k in ("failure", "error", "skipped"))
            nodes.append(case.attrib["classname"] + "::" + case.attrib["name"])
    assert len(nodes) == len(set(nodes)) == 46
    for name, expected in report["output_sha256"].items():
        assert sha(component / name) == expected, name
    for name, expected in report["source_sha256"].items():
        assert sha(ROOT / name) == expected, name
    protocol = read(ROOT / "validation/tissue/joint_water_hcn_protocol.json")
    for name, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / name) == expected, name
    frozen = protocol["frozen_workspace"]
    for p, s in (("manifest", "manifest_sha256"), ("handoff_receipt", "handoff_receipt_sha256")):
        assert sha(Path(frozen[p])) == frozen[s]
    manifest_path = component / "workspace-manifest.json"
    assert sha(manifest_path) == report["workspace_manifest_sha256"]
    manifest = read(manifest_path)
    assert len(manifest["overlay_source_sha256"]) == 4
    assert not manifest["shared_files_written"] and not manifest["current_shared_engine_used"]
    assert set(manifest["only_test_dispatch_changed"]) == {
        "src/cells/core/specs.py",
        "src/cells/core/schedule.py",
        "src/cells/models/registry.py",
        "src/cells/ensemble/ionic.py",
    }
    for name, expected in manifest["source_sha256"].items():
        assert sha(component / "workspace" / name) == expected, name
        if name in manifest["overlay_source_sha256"]:
            assert sha(ROOT / name) == expected
        elif name not in manifest["only_test_dispatch_changed"]:
            assert expected == manifest["qualified_base_source_sha256"][name]
    assert inputs["affinity"] == [7]
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    assert inputs["environment"]["JAX_ENABLE_COMPILATION_CACHE"] == "false"
    guards = {}
    retained = report.get("retained_finalized_runs", [])
    if retained:
        assert sum(r["finalized_tests"] for r in retained) == 45
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
        records[path.stem.removeprefix("joint-water-hcn-")] = value
    assert len(records) == 46
    stages = [row for value in records.values() for row in value.get("stages", [])]
    assert len(stages) == 48 and all(row["error_over_budget"] <= 1 for row in stages)
    arrays = {}
    trajectories = {}
    for family, count in (("water", 43), ("repair", 48)):
        record = records["trajectory-" + family]
        assert record["all_observations_compared"] and record["original_material_and_work_ledgers"]
        assert not record["endpoint_only_claim"] and not record["convergence_order_claim"]
        assert all(r["error_over_budget"] <= 1 for r in record["refinements"])
        assert all(
            max(map(abs, r["independent_energy_residual_pJ"])) <= 1e-9
            for r in record["refinements"]
        )
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
            for name, groups in raw["experiment"].items():
                if name.endswith("_controls"):
                    for row in groups:
                        for entry in row["controls" if "controls" in row else "schedule"]:
                            assert entry["time"] in times, (family, name, entry["time"])
        arrays[family] = dict(
            path=str(path), sha256=sha(path), fields=count, observations=len(times)
        )
        trajectories[family] = record
    static = read(WORK / "joint_water_hcn_static_boundary.json")
    assert static["status"] == "static_only"
    assert sum(r["function_count"] for r in static["production_function_comparison"]) == 49
    for row in static["production_function_comparison"]:
        assert sha(ROOT / row["original"]) == row["original_sha256"]
        assert sha(ROOT / row["new"]) == row["new_sha256"]
    output.mkdir(exist_ok=False)
    examples = {}
    for family, name in (("water", "water-stages-open"), ("repair", "repair-stages-preinjured")):
        folder = output / "examples" / family
        folder.mkdir(parents=True)
        write(folder / "definition.json", records[name]["inputs"])
        write(folder / "trajectory-definition.json", records["trajectory-" + family]["inputs"])
        examples[family] = {p.name: sha(p) for p in folder.iterdir()}
    for source, name in (
        (ROOT / "validation/tissue/joint_water_hcn_protocol.json", "protocol.json"),
        (WORK / "joint_water_hcn_static_boundary.json", "static-function-correspondence.json"),
        (WORK / "JOINT_WATER_HCN_BOUNDARY.md", "CONTRACT.md"),
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
        independent_full_stage_comparisons=48,
        maximum_stage_error_over_budget=max(r["error_over_budget"] for r in stages),
        complete_state_fields=dict(water=43, repair=48),
        all_channel_laws=56,
        full_observation_trajectories=trajectories,
        retained_arrays=arrays,
        inherited_function_correspondence=static,
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
