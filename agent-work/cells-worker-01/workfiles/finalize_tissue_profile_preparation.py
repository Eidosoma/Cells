"""Verify the B13 bridge receipt and publish exact validated example payloads."""

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
    assert output.name.startswith("tissue-profile-preparation-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert report["tests"] == dict(tests=49, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    assert [r["name"] for r in report["checks"]] == ["imports", "format", "lint", "native", "host"]
    assert all(r["exit_code"] == 0 for r in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    protocol = read(ROOT / "validation/topology/tissue_profile_preparation_protocol.json")
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    native_source = protocol["native_units"]
    for relative, expected in native_source["source_sha256"].items():
        assert sha(Path(native_source["checkout"]) / relative) == expected
        assert sha(Path(native_source["installed_package"]).parent / relative) == expected
    prior = protocol["native_component_receipt"]
    assert sha(Path(prior["path"])) == prior["sha256"]
    assert read(Path(prior["path"]))["status"] == "passed"
    capture = read(component / "native-source/result.json")
    assert capture["status"] == "passed" and len(capture["cases"]) == 7
    assert not capture["cells_imported"] and not capture["jax_imported"]
    assert not capture["before_imports"] and not capture["after_capture_imports"]
    assert capture["electroflux_ast_sha256"] == native_source["electroflux_ast_sha256"]
    assert inputs["affinity"] == [7]
    assert inputs["environment"]["JAX_DISABLE_JIT"] == "true"
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    guards = {name: read(component / (name + "-guard/result.json")) for name in ("native", "host")}
    for guard in guards.values():
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    evidence = {}
    for p in sorted((component / "evidence").glob("*.json")):
        assert read(p)["status"] == "passed"
        evidence[p.name] = dict(path=str(p), sha256=sha(p))
    assert len(evidence) == 49
    output.mkdir(exist_ok=False)
    examples = {}
    for name in ("active-overlap", "active-color", "passive-percent-alias"):
        source = component / "evidence" / ("tissue-profile-preparation-" + name + ".json")
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
    shutil.copyfile(ROOT / (WORK + "TISSUE_PROFILE_PREPARATION_HANDOFF.md"), output / "HANDOFF.md")
    shutil.copyfile(
        ROOT / "validation/topology/tissue_profile_preparation_protocol.json",
        output / "protocol.json",
    )
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        bridge_id=protocol["bridge_id"],
        supported_models=protocol["supported_models"],
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        tests=report["tests"],
        native_unit_cases=7,
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        readonly_source_sha256=protocol["readonly_source_sha256"],
        native_component_receipt=prior,
        native_unit_provenance=capture,
        resource_guards=guards,
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
                tests=49,
                native_unit_cases=7,
            )
        )
    )


if __name__ == "__main__":
    main()
