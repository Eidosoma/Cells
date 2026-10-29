"""Verify static native geometry preparation and copy validated payloads only."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = "agent-work/cells-worker-01/workfiles/"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("geometry-tissue-preparation-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=56, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert [r["name"] for r in report["checks"]] == ["imports", "format", "lint", "host"]
    assert all(r["exit_code"] == 0 for r in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    protocol = read(ROOT / "validation/geometry/geometry_tissue_preparation_protocol.json")
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    prior = protocol["geometry_receipt"]
    assert sha(Path(prior["path"])) == prior["sha256"]
    old = read(Path(prior["path"]))
    assert old["status"] == "passed"
    for relative, expected in old["owned_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    assert inputs["affinity"] == [7]
    assert inputs["environment"]["JAX_DISABLE_JIT"] == "true"
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    guard = read(component / "host-guard/result.json")
    assert guard["status"] == "completed"
    assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
    assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    for name, expected in protocol["native_input_sha256"].items():
        assert sha(component / "native-inputs" / name) == expected, name
    evidence, comparisons = {}, []
    for p in sorted((component / "evidence").glob("*.json")):
        value = read(p)
        assert value["status"] == "passed"
        evidence[p.name] = dict(path=str(p), sha256=sha(p))
        comparisons.extend(value.get("independent_comparisons", []))
        if "independent_comparisons" in value:
            generation = value["request"]["geometry_source"]["generation"]
            capture = generation["native_capture_record"]
            name = generation["input"]["name"] + ".json"
            assert capture == read(component / "native-inputs" / name)
            assert generation["native_capture_file_sha256"] == protocol["native_input_sha256"][name]
            assert generation["native_capture_identity"] == identity(capture)
    assert len(evidence) == 56 and len(comparisons) == 20
    assert max(v["error_over_budget"] for v in comparisons) <= 1
    output.mkdir(exist_ok=False)
    examples = {}
    cases = {
        "irregular-native-radial": ("irregular-centroid-aux", "native_radial"),
        "irregular-polygon": ("irregular-centroid-aux", "polygon"),
        "scaled-polygon": ("translated-scaled-circumcenter", "polygon"),
    }
    for name, (case, policy) in cases.items():
        source = component / "evidence" / ("geometry-tissue-" + case + "-" + policy + ".json")
        value = read(source)
        assert identity(value["prepared"]) == value["provenance"]["prepared_definition_sha256"]
        assert identity(value["request"]) == value["provenance"]["request_sha256"]
        provenance = dict(value["provenance"])
        seal = provenance.pop("identity")
        assert identity(provenance) == seal
        folder = output / "examples" / name
        folder.mkdir(parents=True)
        for filename, key in (
            ("definition.json", "prepared"),
            ("provenance.json", "provenance"),
            ("request.json", "request"),
        ):
            (folder / filename).write_text(json.dumps(value[key], indent=2, allow_nan=False) + "\n")
        examples[name] = dict(
            path=str(folder),
            source_evidence_sha256=sha(source),
            files_sha256={p.name: sha(p) for p in sorted(folder.iterdir())},
        )
    shutil.copyfile(ROOT / (WORK + "GEOMETRY_TISSUE_PREPARATION_HANDOFF.md"), output / "HANDOFF.md")
    shutil.copyfile(
        ROOT / "validation/geometry/geometry_tissue_preparation_protocol.json",
        output / "protocol.json",
    )
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        bridge_id=protocol["bridge_id"],
        target_model=protocol["target_model"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        tests=report["tests"],
        independently_checked_native_cases=protocol["native_cases"],
        cell_volume_policies=protocol["cell_volume_policies"],
        refused_native_cases=protocol["refused_native_cases"],
        independent_stage_count=20,
        maximum_rhs_error_over_budget=max(v["error_over_budget"] for v in comparisons),
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        qualified_geometry_receipt=prior,
        native_input_sha256=protocol["native_input_sha256"],
        host_guard=guard,
        evidence=evidence,
        examples=examples,
        geometry_generation_executed=False,
        physical_remap_qualified=False,
        shared_source_edits=False,
        gpu_executed=False,
        compiled_trajectory_qualified=False,
        full_native_simulator_qualified=False,
        automatic_followup=False,
        detached_jobs_polled=False,
    )
    result["handoff_artifact_sha256"] = {
        str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
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
