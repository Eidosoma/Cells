"""Verify public geometry workflow evidence and package the unapplied dispatch."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


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
    assert output.name.startswith("tissue-geometry-cli-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=33, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert [v["name"] for v in report["checks"]] == ["imports", "format", "lint", "host"]
    assert all(v["exit_code"] == 0 for v in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    contract = read(WORK / "tissue_geometry_cli_contract.json")
    prior = contract["geometry_handoff"]
    assert sha(Path(prior["path"])) == prior["sha256"]
    assert sha(component / "component-reference/receipt.json") == prior["sha256"]
    old = read(Path(prior["path"]))
    assert old["status"] == "passed" and old["tests"]["tests"] == 56
    for relative, expected in contract["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    for name, expected in contract["frozen_example"]["files_sha256"].items():
        assert sha(component / "component-reference" / name) == expected, name
    assert (
        sha(ROOT / contract["repository_example"]["path"])
        == contract["repository_example"]["sha256"]
    )
    assert inputs["affinity"] == [7]
    assert inputs["environment"]["JAX_DISABLE_JIT"] == "true"
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    guard = read(component / "host-guard/result.json")
    assert guard["status"] == "completed"
    assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
    assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    evidence = {}
    for path in sorted((component / "evidence").glob("*.json")):
        assert read(path)["status"] == "passed"
        evidence[path.name] = dict(path=str(path), sha256=sha(path))
    assert len(evidence) == 33
    portable = read(component / "evidence/tissue-geometry-cli-portable-workflow.json")
    assert portable["external_geometry_reads_blocked"]
    assert portable["original_input_and_output_removed"]
    assert len(portable["fresh_processes"]) == 4
    assert all(v["exit_code"] == 0 for v in portable["fresh_processes"])
    expected = read(component / "component-reference/provenance.json")
    actual = portable["exact_component_definition_and_initial_state"]
    assert actual["definition_sha256"] == expected["prepared_definition_sha256"]
    assert actual["initial_state_sha256"] == expected["initial_state_sha256"]
    assert actual["state_fields"] == expected["initial_state_fields"]
    replayed = Path(portable["fresh_processes"][2]["arguments"][-1])
    assert replayed.is_relative_to(component)
    for name in ("definition.json", "provenance.json"):
        assert sha(replayed / name) == contract["frozen_example"]["files_sha256"][name]
    dispatch = read(ROOT / contract["dispatch_metadata"])
    assert sha(ROOT / contract["dispatch_patch"]) == dispatch["patch_sha256"]
    assert sha(component / "dispatch-base" / dispatch["path"]) == dispatch["base_sha256"]
    output.mkdir(exist_ok=False)
    example = output / "example"
    example.mkdir()
    shutil.copyfile(ROOT / contract["repository_example"]["path"], example / "request.json")
    for name in ("definition.json", "provenance.json"):
        shutil.copyfile(replayed / name, example / name)
    assert identity(read(example / "definition.json")) == expected["prepared_definition_sha256"]
    for source, target in (
        (ROOT / contract["dispatch_patch"], output / "dispatch.patch"),
        (ROOT / contract["dispatch_metadata"], output / "dispatch.json"),
        (ROOT / "docs/TISSUE_GEOMETRY.md", output / "TISSUE_GEOMETRY.md"),
        (WORK / "TISSUE_GEOMETRY_CLI_HANDOFF.md", output / "HANDOFF.md"),
        (WORK / "tissue_geometry_cli_contract.json", output / "contract.json"),
        (Path(__file__), output / "finalize.py"),
    ):
        shutil.copyfile(source, target)
    result = dict(
        status="passed",
        module="cells.tissue_geometry",
        tests=report["tests"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=contract["readonly_source_sha256"],
        geometry_handoff=prior,
        geometry_component_suite_rerun=False,
        fresh_process_count=4,
        external_geometry_reads_blocked=True,
        exact_component_definition_and_initial_state=actual,
        repository_example=contract["repository_example"],
        example_files_sha256={p.name: sha(p) for p in example.iterdir()},
        unapplied_dispatch=dispatch,
        host_guard=guard,
        evidence=evidence,
        shared_dispatch_applied=False,
        gpu_executed=False,
        new_physics=False,
        long_jobs_launched=False,
        detached_jobs_polled=False,
        automatic_followup=False,
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
