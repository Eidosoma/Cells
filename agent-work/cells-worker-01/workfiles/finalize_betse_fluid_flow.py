"""Verify and freeze fluid-flow evidence and integration metadata only."""

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "agent-work/cells-worker-01/workfiles/BETSE_FLUID_FLOW_HANDOFF.md"
GEOMETRY_SHA = "18a082cd09acc817707ba775196666c446b439c5b254a04e36f0b49157b46dff"
MECHANICS_SHA = "88e61c22a979edbfaa564170a5e615b698092a6356cb1aaa017182e4aba56cb2"
ENVIRONMENT_SHA = "7cf5b793964f9b34dccd85b04982a3c2f2e92f3b043b8e04a30a647409afe42c"
DEPENDENCIES = {
    "src/cells/processes/betse_geometry.py": GEOMETRY_SHA,
    "src/cells/processes/betse_deformation.py": MECHANICS_SHA,
    "src/cells/processes/betse_environment_transport.py": ENVIRONMENT_SHA,
}


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and inputs["phase"] == "complete-component"
    assert report["tests"] == dict(tests=64, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"] and report["error"] is None
    assert [c["name"] for c in report["checks"]] == [
        "imports",
        "format",
        "lint",
        "native",
        "host",
        "jax",
    ]
    assert all(c["exit_code"] == 0 for c in report["checks"])
    for name, count in (("host", 60), ("jax", 4)):
        suites = list(ET.parse(component / (name + "-tests.xml")).getroot().iter("testsuite"))
        assert sum(int(s.get("tests", "0")) for s in suites) == count
        assert all(
            int(s.get(k, "0")) == 0 for s in suites for k in ("errors", "failures", "skipped")
        )
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {p: sha for p, sha in report["source_sha256"].items() if "betse_fluid_flow" in p}
    assert len(owned) == 7
    for relative, sha in {**owned, **DEPENDENCIES}.items():
        assert digest(ROOT / relative) == sha and report["source_sha256"][relative] == sha
    native = read(component / "native-source/source-manifest.json")
    assert native["status"] == "passed" and native["component_cases"] == 14
    assert native["refinement_cases"] == 6 and native["limitations"] == 11
    assert (
        len(native["records"]) == 31
        and sum(r["status"] == "passed" for r in native["records"]) == 23
    )
    assert (
        len(native["grn_records"]) == 4
        and sum(r["status"] == "passed" for r in native["grn_records"]) == 2
    )
    assert not any(
        native[k]
        for k in (
            "full_simulator",
            "jax_imported",
            "production_cells_imported",
            "geometry_generation_or_cut_executed",
        )
    )
    policy = read(component / "native-source/caller-policy.json")
    assert policy["source_fluid_flow"] is False and policy["source_td_deform"] is False
    assert policy["source_viscosity_Pa_s"] == 0.01 and policy["initialized"]["cell_inverse"] is None
    assert policy["missing_inverse"]["ecm_written_before_cell_failure"]
    assert native["reachability"]["fast_getFlow_calls"] == []
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
    assert len(evidence) == 39
    shutil.copyfile(ROOT / CONTRACT, output / "integration-contract.md")
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=digest(component / "result.json"),
        tests=report["tests"],
        host_tests=60,
        cpu_jax_tests=4,
        native_valid_cases=14,
        native_refinement_cases=6,
        observed_native_limit_cases=11,
        separate_grn_valid_cases=2,
        separate_grn_singular_cases=2,
        verified_component_artifact_count=len(report["output_sha256"]),
        owned_source_sha256=owned,
        readonly_dependency_sha256=DEPENDENCIES,
        source_version=native["version"],
        source_revision=native["revision"],
        source_files=native["files"],
        native_source_manifest_sha256=digest(component / "native-source/source-manifest.json"),
        native_runtime_versions=dict(numpy=native["numpy_version"], scipy=native["scipy_version"]),
        cpu_runtime_versions=inputs["versions"],
        resource_guards=guards,
        peak_process_tree_rss_bytes=max(
            g["sampled_peak_process_tree_rss_bytes"] for g in guards.values()
        ),
        minimum_available_host_memory_bytes=min(
            g["minimum_available_host_memory_bytes"] for g in guards.values()
        ),
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        evidence=evidence,
        cell_refinement=read(component / "evidence/betse-fluid-flow-cell-refinement.json"),
        ecm_refinement=read(component / "evidence/betse-fluid-flow-ecm-refinement.json"),
        dimensions_and_offset=read(
            component / "evidence/betse-fluid-flow-dimensions-and-offset.json"
        ),
        boundary_limits=read(
            component / "evidence/betse-fluid-flow-boundary-and-discarded-scalar.json"
        ),
        component_sequence=read(
            component / "evidence/betse-fluid-flow-jax-stateless-sequence.json"
        ),
        reachability=native["reachability"],
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
                phase=read(p / "inputs.json")["phase"],
            )
            for p in sorted(component.parent.glob("betse-fluid-flow-development-20261029-*"))
            if (p / "result.json").is_file()
        ],
        scope=(
            "Literal isolated cell flow in m/s and dimensionally defective ECM output in m3/s; "
            "explicit geometry/pressure ownership and dormant loader/caller behavior. "
            "No coupled tissue, physical Stokes/no-slip, water-volume, energy or checkpoint claim."
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
                artifacts=len(report["output_sha256"]),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.component, args.output)
