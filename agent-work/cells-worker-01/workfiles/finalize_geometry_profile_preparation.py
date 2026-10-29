"""Verify the joined frozen geometry/profile recipes and copy passed examples."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PUBLIC_RECEIPT = Path("/mnt/workspaces/Cells/tissue-geometry-cli-handoff-20261029-01/result.json")
PUBLIC_SHA = "d863b7b27d2aa55ab3fd5c1e2d8859ec14156000b0114396bb34e192abad0f62"


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
    assert output.name.startswith("geometry-profile-preparation-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=43, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert [v["name"] for v in report["checks"]] == ["imports", "format", "lint", "host"]
    assert all(v["exit_code"] == 0 for v in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    protocol = read(ROOT / "validation/geometry/geometry_profile_preparation_protocol.json")
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    for receipt in protocol["component_receipts"].values():
        assert sha(Path(receipt["path"])) == receipt["sha256"]
        assert read(Path(receipt["path"]))["status"] == "passed"
    assert sha(PUBLIC_RECEIPT) == PUBLIC_SHA
    public = read(PUBLIC_RECEIPT)
    assert (
        sha(ROOT / "src/cells/tissue_geometry.py")
        == public["source_sha256"]["src/cells/tissue_geometry.py"]
    )
    assert sha(ROOT / protocol["repository_example"]) == protocol["repository_example_sha256"]
    for name, artifact in protocol["geometry_artifacts"].items():
        for file in ("definition.json", "provenance.json"):
            assert (
                sha(component / "geometry-artifacts" / name / file)
                == artifact["files_sha256"][file]
            )
    assert inputs["affinity"] == [7]
    assert inputs["environment"]["JAX_DISABLE_JIT"] == "true"
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    guard = read(component / "host-guard/result.json")
    assert guard["status"] == "completed"
    assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
    assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    evidence, stages = {}, []
    for p in sorted((component / "evidence").glob("*.json")):
        value = read(p)
        assert value["status"] == "passed"
        evidence[p.name] = dict(path=str(p), sha256=sha(p))
        stages.extend(value.get("independent_comparisons", []))
    assert len(evidence) == 43 and len(stages) == 28
    assert max(v["error_over_budget"] for v in stages) <= 1
    portable = read(component / "evidence/geometry-profiles-portable-replay.json")
    assert portable["external_geometry_reads_blocked"]
    assert portable["typed_definition_tamper_refused"]
    image = read(component / "evidence/geometry-profiles-centroid-image-control.json")
    assert image["actual_centroid_targets"] != image["incorrect_seed_point_targets"]
    output.mkdir(exist_ok=False)
    examples = {}
    for name in ("overlap", "percent-alias", "image-centroids"):
        source = component / "evidence" / ("geometry-profiles-physical-" + name + ".json")
        value = read(source)
        p = dict(value["provenance"])
        seal = p.pop("identity")
        assert identity(p) == seal
        assert identity(value["prepared"]) == p["prepared_definition_sha256"]
        assert identity(value["request"]) == p["request_sha256"]
        assert (
            p["geometry_preparation_identity"]
            == value["request"]["geometry_preparation"]["provenance"]["identity"]
        )
        assert p["profile_preparation_identity"] == p["profile_preparation"]["identity"]
        folder = output / "examples" / name
        folder.mkdir(parents=True)
        for filename, key in (
            ("request.json", "request"),
            ("definition.json", "prepared"),
            ("provenance.json", "provenance"),
        ):
            (folder / filename).write_text(json.dumps(value[key], indent=2, allow_nan=False) + "\n")
        examples[name] = dict(
            path=str(folder),
            source_evidence_sha256=sha(source),
            files_sha256={p.name: sha(p) for p in folder.iterdir()},
        )
    for source, name in (
        (WORK / "GEOMETRY_PROFILE_PREPARATION_HANDOFF.md", "HANDOFF.md"),
        (ROOT / "validation/geometry/geometry_profile_preparation_protocol.json", "protocol.json"),
        (ROOT / "examples/geometry_tissue_profiles/README.md", "README.md"),
        (Path(__file__), "finalize.py"),
    ):
        shutil.copyfile(source, output / name)
    result = dict(
        status="passed",
        bridge_id=protocol["bridge_id"],
        tests=report["tests"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        component_receipts=protocol["component_receipts"],
        unchanged_public_cli=dict(receipt=str(PUBLIC_RECEIPT), sha256=PUBLIC_SHA),
        independent_physical_stages=28,
        maximum_rhs_error_over_budget=max(v["error_over_budget"] for v in stages),
        centroid_image_control=image,
        portable_replay=portable,
        host_guard=guard,
        evidence=evidence,
        examples=examples,
        shared_source_edits=False,
        existing_component_suites_rerun=False,
        gpu_executed=False,
        native_generation_executed=False,
        compiled_trajectory_qualified=False,
        physical_remap_qualified=False,
        full_native_simulator_qualified=False,
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
