"""Verify and freeze the new @2 host receipt without rerunning scientific jobs."""

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    component, output = args.component.resolve(), args.output.resolve()
    assert component.parent == output.parent == Path("/mnt/workspaces/Cells")
    assert output.name.startswith("integrated-network-regulation-v2-handoff-")
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and report["error"] is None
    assert inputs["phase"] == "common-stage-consumer-regulation-v2-host"
    assert not report["sources_changed_during_checks"]
    assert report["tests"]["tests"] >= 39
    assert all(report["tests"][key] == 0 for key in ("errors", "failures", "skipped"))
    assert [c["name"] for c in report["checks"]] == ["imports", "format", "lint", "oracle", "host"]
    assert all(c["exit_code"] == 0 for c in report["checks"])
    for relative, expected in report["output_sha256"].items():
        assert sha(component / relative) == expected, relative
    for relative, expected in report["source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    protocol = read(ROOT / "validation/regulation/integrated_network_regulation_v2_protocol.json")
    for relative, expected in protocol["readonly_source_sha256"].items():
        assert sha(ROOT / relative) == expected == report["source_sha256"][relative]
    native = protocol["frozen_native_handoff"]
    assert sha(Path(native["path"])) == native["sha256"]
    assert read(Path(native["path"]))["status"] == "passed"
    guards = {name: read(component / (name + "-guard/result.json")) for name in ("oracle", "host")}
    for guard in guards.values():
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 2**30
    assert inputs["affinity"] == [7] and not inputs["compiled_execution"]
    assert inputs["environment"]["JAX_PLATFORMS"] == "cpu"
    assert inputs["environment"]["CUDA_VISIBLE_DEVICES"] == ""
    oracle = read(component / "evidence/independent-v2.json")
    assert oracle["production_imported"] is False and oracle["jax_imported"] is False
    assert not oracle["execution"]["pytest_imported"]
    assert all(not v for v in oracle["independence_guards"].values())
    dispatch = read(ROOT / (WORK + "integrated_network_regulation_v2_dispatch.json"))
    assert dispatch["status"] == "prepared-not-applied"
    assert sha(ROOT / dispatch["patch_path"]) == dispatch["patch_sha256"]
    evidence = {}
    for path in sorted((component / "evidence").glob("*.json")):
        assert read(path)["status"] == "passed"
        evidence[path.name] = dict(path=str(path), sha256=sha(path))
    output.mkdir(exist_ok=False)
    for relative in (
        WORK + "INTEGRATED_NETWORK_REGULATION_V2_HANDOFF.md",
        WORK + "integrated_network_regulation_v2_dispatch.patch",
        WORK + "integrated_network_regulation_v2_dispatch.json",
        "validation/regulation/integrated_network_regulation_v2_protocol.json",
    ):
        shutil.copyfile(ROOT / relative, output / Path(relative).name)
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        model_id=protocol["model_id"],
        parent=protocol["parent"],
        state_fields=38,
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=sha(component / "result.json"),
        tests=report["tests"],
        compiled_execution_qualified=False,
        public_dispatch_qualified=False,
        verified_component_artifact_count=len(report["output_sha256"]),
        source_sha256=report["source_sha256"],
        frozen_native_source=native,
        resources=guards,
        runtime_versions=inputs["versions"] | oracle["versions"],
        unapplied_dispatch=dispatch,
        shared_dispatch_now={
            path: dict(
                current_sha256=sha(ROOT / path),
                matches_prepared_before=sha(ROOT / path) == row["before_sha256"],
            )
            for path, row in dispatch["shared_files"].items()
        },
        evidence=evidence,
        coupled_refinement=read(component / "evidence/regulation-v2-coupled-refinement.json"),
        automatic_followup=False,
        active_v1_job_polled=False,
    )
    result["handoff_artifact_sha256"] = {
        p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(output=str(output), status="passed", tests=report["tests"])))


if __name__ == "__main__":
    main()
