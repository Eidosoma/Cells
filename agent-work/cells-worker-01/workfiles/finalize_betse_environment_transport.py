"""Freeze qualified environment transport evidence and contract metadata only."""

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "agent-work/cells-worker-01/workfiles/BETSE_ENVIRONMENT_TRANSPORT_HANDOFF.md"
GEOMETRY_SOURCE = "src/cells/processes/betse_geometry.py"
GEOMETRY_SHA = "18a082cd09acc817707ba775196666c446b439c5b254a04e36f0b49157b46dff"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and inputs["phase"] == "complete-component"
    assert report["tests"] == dict(tests=75, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"] and report["error"] is None
    assert [r["name"] for r in report["checks"]] == [
        "imports",
        "format",
        "lint",
        "native",
        "host",
        "jax",
    ]
    assert all(r["exit_code"] == 0 for r in report["checks"])
    for name, count in (("host", 71), ("jax", 4)):
        suites = list(ET.parse(component / (name + "-tests.xml")).getroot().iter("testsuite"))
        assert sum(int(s.get("tests", "0")) for s in suites) == count
        assert all(
            int(s.get(k, "0")) == 0 for s in suites for k in ("errors", "failures", "skipped")
        )
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {k: v for k, v in report["source_sha256"].items() if "betse_environment_transport" in k}
    assert len(owned) == 7
    for relative, sha in owned.items():
        assert digest(ROOT / relative) == sha
    assert (
        report["source_sha256"][GEOMETRY_SOURCE] == GEOMETRY_SHA == digest(ROOT / GEOMETRY_SOURCE)
    )
    native = read(component / "native-source/source-manifest.json")
    assert (
        native["status"] == "passed"
        and native["component_cases"] == 23
        and native["limitations"] == 19
        and native["refinement_cases"] == 3
    )
    assert (
        len(native["records"]) == 45
        and sum(r["status"] == "passed" for r in native["records"]) == 26
    )
    assert not any(
        native[k]
        for k in (
            "production_cells_imported",
            "jax_imported",
            "geometry_or_cut_executed",
            "full_tissue_or_membrane_physics",
            "full_simulator",
        )
    )
    assert not native["wound_fragment"]["cut_executed"]
    assert inputs["affinity"] == [7] and inputs["environment"]["JAX_PLATFORMS"] == "cpu"
    assert inputs["environment"]["JAX_ENABLE_COMPILATION_CACHE"] == "false"
    guards = {
        name: read(component / (name + "-guard/result.json")) for name in ("native", "host", "jax")
    }
    for guard in guards.values():
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 1024**3
    evidence = {}
    for path in sorted((component / "evidence").glob("*.json")):
        assert read(path)["status"] == "passed"
        evidence[path.name] = dict(path=str(path), sha256=digest(path))
    assert len(evidence) == 37
    shutil.copyfile(ROOT / CONTRACT, output / "integration-contract.md")
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=digest(component / "result.json"),
        tests=report["tests"],
        host_tests=71,
        cpu_jax_tests=4,
        native_valid_cases=23,
        observed_native_limit_cases=19,
        native_interior_refinement_cases=3,
        verified_component_artifact_count=len(report["output_sha256"]),
        owned_source_sha256=owned,
        shared_primitive_and_geometry_sha256={
            k: v
            for k, v in report["source_sha256"].items()
            if k
            in (
                GEOMETRY_SOURCE,
                "src/cells/processes/electrochemistry.py",
                "src/cells/numerics/extracellular_field.py",
            )
        },
        native_source_manifest_sha256=digest(component / "native-source/source-manifest.json"),
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        source_version=native["version"],
        source_revision=native["revision"],
        source_files=native["files"],
        native_runtime_versions=native["versions"],
        cpu_runtime_versions=inputs["versions"],
        resource_guards=guards,
        peak_process_tree_rss_bytes=max(
            g["sampled_peak_process_tree_rss_bytes"] for g in guards.values()
        ),
        minimum_available_host_memory_bytes=min(
            g["minimum_available_host_memory_bytes"] for g in guards.values()
        ),
        evidence=evidence,
        refinement=read(component / "evidence/betse-environment-transport-refinement.json"),
        native_defects=read(component / "evidence/betse-environment-transport-source-defects.json"),
        bath_overwrite=read(
            component / "evidence/betse-environment-transport-overlapping-baths.json"
        ),
        steady_baths=read(component / "evidence/betse-environment-transport-steady-baths.json"),
        conservative_open_bath=read(
            component / "evidence/betse-environment-transport-conservative-open-bath.json"
        ),
        component_restart=read(
            component / "evidence/betse-environment-transport-jax-restart-derivative.json"
        ),
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
                phase=read(p / "inputs.json")["phase"],
            )
            for p in sorted(
                component.parent.glob("betse-environment-transport-development-20261029-*")
            )
            if (p / "result.json").is_file()
        ],
        scope=(
            "Literal native collocated/barrier/bath arithmetic and a distinct conservative "
            "face law; source sign/checkerboard/mass/charge/clipping defects retained; "
            "no cut, field closure, whole-tissue, thermodynamic/ATP or shared checkpoint claim"
        ),
        automatic_followup=False,
    )
    result["handoff_payload_sha256"] = {
        str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                path=str(output / "result.json"),
                sha256=digest(output / "result.json"),
                artifacts=result["verified_component_artifact_count"],
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.component, args.output)
