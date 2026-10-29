"""Freeze already-qualified perturbation evidence and replay contract metadata."""

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "agent-work/cells-worker-01/workfiles/BETSE_PERTURBATIONS_HANDOFF.md"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and inputs["phase"] == "complete-component"
    assert report["tests"] == dict(tests=61, errors=0, failures=0, skipped=0)
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
    for name, count in (("host", 57), ("jax", 4)):
        suites = list(ET.parse(component / (name + "-tests.xml")).getroot().iter("testsuite"))
        assert sum(int(s.get("tests", "0")) for s in suites) == count
        assert all(
            int(s.get(k, "0")) == 0 for s in suites for k in ("errors", "failures", "skipped")
        )
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {k: v for k, v in report["source_sha256"].items() if "betse_perturbations" in k}
    assert len(owned) == 7
    for relative, sha in owned.items():
        assert digest(ROOT / relative) == sha
    native = read(component / "native-source/source-manifest.json")
    assert (
        native["status"] == "passed"
        and native["component_cases"] == 21
        and native["limitations"] == 14
    )
    assert (
        len(native["records"]) == 35
        and sum(r["status"] == "passed" for r in native["records"]) == 21
    )
    assert native["distribution_samples"] == 32768 and native["boundary_choice_samples"] == 8192
    assert not any(
        native[k]
        for k in (
            "production_cells_imported",
            "jax_imported",
            "microtubules_enabled",
            "geometry_or_full_physiology",
            "full_simulator",
        )
    )
    assert (
        not native["sites"]["microtubules_integrated"]
        and native["sites"]["fast_dynamic_rng_sites"] == []
    )
    assert inputs["versions"]["numpy"] == native["versions"]["numpy"]
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
    assert len(evidence) == 30
    shutil.copyfile(ROOT / CONTRACT, output / "integration-contract.md")
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=digest(component / "result.json"),
        tests=report["tests"],
        host_tests=57,
        cpu_jax_tests=4,
        native_valid_cases=21,
        observed_native_limit_cases=14,
        native_uniform_normal_samples=32768,
        native_boundary_samples=8192,
        stable_samples=8192,
        verified_component_artifact_count=len(report["output_sha256"]),
        owned_source_sha256=owned,
        native_source_manifest_sha256=digest(component / "native-source/source-manifest.json"),
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        source_version=native["version"],
        source_revision=native["revision"],
        source_files=native["files"],
        source_sites=native["sites"],
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
        native_distribution=read(
            component / "evidence/betse-perturbations-native-distributions.json"
        ),
        stable_distribution=read(
            component / "evidence/betse-perturbations-stable-distributions-replay.json"
        ),
        protein_statistics=read(component / "evidence/betse-perturbations-protein-statistics.json"),
        native_gaussian_cache=read(
            component / "evidence/betse-perturbations-native-gaussian-cache.json"
        ),
        source_fast_ECM_defect=read(
            component / "evidence/betse-perturbations-fast-ECM-defect.json"
        ),
        native_replay=read(component / "evidence/betse-perturbations-native-replay.json"),
        stable_order_isolation=read(
            component / "evidence/betse-perturbations-stable-isolation.json"
        ),
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
                phase=read(p / "inputs.json")["phase"],
            )
            for p in sorted(component.parent.glob("betse-perturbations-development-20261029-*"))
            if (p / "result.json").is_file()
        ],
        scope=(
            "Native stochastic-site arithmetic and bounded component replay; "
            "distinct Cells stable-owner law; source fast-ECM/clipping and disabled MT limits "
            "preserved; no full-tissue, physical Brownian, energetic or shared "
            "checkpoint/cut integration claim"
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
