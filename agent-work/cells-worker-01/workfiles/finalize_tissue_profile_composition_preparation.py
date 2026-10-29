"""Verify full-parent static preparation and publish exact validated payloads."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = "agent-work/cells-worker-01/workfiles/"
PRIOR = Path("/mnt/workspaces/Cells/regulated-v2-excision-handoff-20261029-01/result.json")
PRIOR_SHA = "25a157373cfa051a2104567589fde6966004fbc500df8fc98e9d1b1e3f7699ea"


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
    assert output.name.startswith("tissue-profile-composition-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=35, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert [r["name"] for r in report["checks"]] == ["imports", "format", "lint", "host"]
    assert all(r["exit_code"] == 0 for r in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    protocol = read(ROOT / "validation/topology/tissue_profile_composition_protocol.json")
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    direct = protocol["direct_bridge_receipt"]
    assert sha(Path(direct["path"])) == direct["sha256"]
    assert read(Path(direct["path"]))["status"] == "passed"
    assert inputs["affinity"] == [7]
    assert inputs["environment"]["JAX_DISABLE_JIT"] == "true"
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    guard = read(component / "host-guard/result.json")
    assert guard["status"] == "completed"
    assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
    assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    evidence = {}
    for p in sorted((component / "evidence").glob("*.json")):
        assert read(p)["status"] == "passed"
        evidence[p.name] = dict(path=str(p), sha256=sha(p))
    assert len(evidence) == 35

    # These older scalar reference dependencies were already frozen before
    # this run. Bind them to that passed receipt and archive the same bytes,
    # rather than silently supplying current, unauthenticated dependencies.
    assert sha(PRIOR) == PRIOR_SHA
    prior = read(PRIOR)
    prior_component = Path(prior["component_receipt"])
    assert sha(prior_component) == prior["component_receipt_sha256"]
    prior_report = read(prior_component)
    manifest = prior_component.parent / "frozen-sources.json"
    assert sha(manifest) == prior_report["output_sha256"]["frozen-sources.json"]
    frozen = read(manifest)["after_sha256"]
    inherited = {k: v for k, v in frozen.items() if k.startswith("tests/reference_")}
    assert len(inherited) == 37
    for relative, expected in inherited.items():
        assert sha(ROOT / relative) == expected, relative
        assert sha(prior_component.parent / "snapshot" / relative) == expected, relative

    output.mkdir(exist_ok=False)
    examples = {}
    for name in ("mitochondria", "fuel_water", "regulation_v2"):
        source = component / "evidence" / ("tissue-profile-composition-family-" + name + ".json")
        value = read(source)
        assert identity(value["prepared"]) == value["provenance"]["prepared_definition_sha256"]
        provenance = dict(value["provenance"])
        seal = provenance.pop("identity")
        assert identity(provenance) == seal
        folder = output / "examples" / name
        folder.mkdir(parents=True)
        for filename, key in (("definition.json", "prepared"), ("provenance.json", "provenance")):
            (folder / filename).write_text(json.dumps(value[key], indent=2, allow_nan=False) + "\n")
        examples[name] = dict(
            path=str(folder),
            source_evidence_sha256=sha(source),
            definition_sha256=sha(folder / "definition.json"),
            provenance_sha256=sha(folder / "provenance.json"),
        )
    for relative in inherited:
        target = output / "inherited-reference-sources" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    shutil.copyfile(ROOT / (WORK + "TISSUE_PROFILE_COMPOSITION_HANDOFF.md"), output / "HANDOFF.md")
    shutil.copyfile(
        ROOT / "validation/topology/tissue_profile_composition_protocol.json",
        output / "protocol.json",
    )
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        bridge_id=protocol["bridge_id"],
        supported_schema_map=protocol["supported_schema_map"],
        independently_checked_families=protocol["families"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        tests=report["tests"],
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        direct_bridge_receipt=direct,
        inherited_reference_provenance=dict(
            receipt=str(PRIOR),
            receipt_sha256=PRIOR_SHA,
            source_manifest_sha256=sha(manifest),
            source_sha256=inherited,
            policy="Exact preexisting frozen scalar dependencies, supplemented without rerunning",
        ),
        host_guard=guard,
        evidence=evidence,
        examples=examples,
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
