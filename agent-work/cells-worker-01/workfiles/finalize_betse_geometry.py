"""Freeze qualified geometry evidence and frozen dependency metadata only."""

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "agent-work/cells-worker-01/workfiles/BETSE_GEOMETRY_HANDOFF.md"
DEPENDENCIES = {
    "src/cells/processes/betse_tissue_cut.py": (
        "2ca66f3f0e3c95b210586c85826668ff681579e908ba896e7c11201c868bc0b1"
    ),
    "src/cells/processes/betse_deformation.py": (
        "88e61c22a979edbfaa564170a5e615b698092a6356cb1aaa017182e4aba56cb2"
    ),
    "src/cells/processes/betse_tissue_profiles.py": (
        "840482d6612a4f0502eac9214acc1d90559345cb757d847f72f4dc8843502be1"
    ),
}
PRIOR_RECEIPTS = {
    "betse-tissue-cut-handoff-20261028-01": (
        "5f25661a6d3af158984f3e968805c6e4bfdc3f076790e1d6392c562d17219e9e"
    ),
    "betse-deformation-handoff-20261028-01": (
        "fd1a6f3dae09711623f7e4c247907691356e01e33b612f809d00769fb824ca7e"
    ),
    "betse-tissue-profiles-handoff-20261028-01": (
        "241773286cd2f10b47f9a70e47a952743e940b0eff265380d3e557225dac4226"
    ),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and inputs["phase"] == "complete-component"
    assert report["tests"] == dict(tests=66, errors=0, failures=0, skipped=0)
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
    for name, count in (("host", 62), ("jax", 4)):
        suites = list(ET.parse(component / (name + "-tests.xml")).getroot().iter("testsuite"))
        assert sum(int(s.get("tests", "0")) for s in suites) == count
        assert all(
            int(s.get(key, "0")) == 0 for s in suites for key in ("errors", "failures", "skipped")
        )
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {k: v for k, v in report["source_sha256"].items() if "betse_geometry" in k}
    assert len(owned) == 7
    for relative, sha in owned.items():
        assert digest(ROOT / relative) == sha
    native = read(component / "native-source/source-manifest.json")
    assert native["status"] == "passed" and native["geometry_cases"] == 12
    assert native["grid_cases"] == 4 and native["limitations"] == 12
    assert len(native["records"]) == 28
    assert native["geometry_generation_executed"]
    assert not any(
        native[k]
        for k in (
            "production_cells_imported",
            "jax_imported",
            "solver_or_cut_executed",
            "full_simulator",
            "yaml_or_full_make_world",
            "production_random_stream_claim",
        )
    )
    assert sum(r["status"] == "passed" for r in native["records"]) == 16
    assert inputs["affinity"] == [7]
    guards = {
        name: read(component / (name + "-guard/result.json")) for name in ("native", "host", "jax")
    }
    for guard in guards.values():
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 1024**3
    evidence = {}
    for p in sorted((component / "evidence").glob("*.json")):
        assert read(p)["status"] == "passed"
        evidence[p.name] = dict(path=str(p), sha256=digest(p))
    assert len(evidence) == 22
    frozen = {}
    for relative, sha in DEPENDENCIES.items():
        path = ROOT / relative
        assert digest(path) == sha
        target = output / "frozen_dependencies" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        frozen[str(path)] = dict(sha256=sha, capsule_path=str(target.relative_to(output)))
    for directory, sha in PRIOR_RECEIPTS.items():
        path = component.parent / directory / "result.json"
        assert digest(path) == sha and read(path)["status"] == "passed"
        target = output / "frozen_dependencies" / (directory + ".json")
        shutil.copyfile(path, target)
        frozen[str(path)] = dict(sha256=sha, capsule_path=str(target.relative_to(output)))
    shutil.copyfile(ROOT / CONTRACT, output / "integration-contract.md")
    shutil.copyfile(Path(__file__), output / "finalize.py")
    summary = dict(
        status="passed",
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=digest(component / "result.json"),
        tests=report["tests"],
        host_tests=62,
        cpu_jax_tests=4,
        native_geometry_cases=12,
        native_grid_cases=4,
        observed_native_limit_cases=12,
        verified_component_artifact_count=len(report["output_sha256"]),
        native_source_manifest_sha256=digest(component / "native-source/source-manifest.json"),
        owned_source_sha256=owned,
        frozen_dependencies=frozen,
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        source_revision=native["revision"],
        source_version=native["version"],
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
        refinement=read(component / "evidence/betse-geometry-refinement.json"),
        source_vs_density_gauge=read(component / "evidence/betse-geometry-gauge.json"),
        environment_inverse_panels=[
            read(component / (f"evidence/betse-geometry-environment-refinement-{n}.json"))
            for n in (4, 8, 16)
        ],
        disconnected=read(component / "evidence/betse-geometry-disconnected-gauges.json"),
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
                phase=read(p / "inputs.json")["phase"],
            )
            for p in sorted(component.parent.glob("betse-geometry-development-202610*"))
            if (p / "result.json").is_file()
        ],
        scope=(
            "Actual small native generation and explicit bounded owner/operator binding; "
            "source inverse/missing-dual-walk defects retained; no physical remap/cut/solver "
            "continuation/checkpoint/full-tissue/mechanical-energy claim"
        ),
        automatic_followup=False,
    )
    summary["handoff_payload_sha256"] = {
        str(p.relative_to(output)): digest(p) for p in sorted(output.rglob("*")) if p.is_file()
    }
    (output / "result.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                path=str(output / "result.json"),
                sha256=digest(output / "result.json"),
                artifacts=summary["verified_component_artifact_count"],
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.component, args.output)
