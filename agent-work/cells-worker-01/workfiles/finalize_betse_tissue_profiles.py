"""Freeze existing qualified profile/target evidence and ownership metadata only."""

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "agent-work/cells-worker-01/workfiles/BETSE_TISSUE_PROFILES_HANDOFF.md"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and inputs["phase"] == "complete-component"
    assert report["tests"] == dict(tests=81, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"] and report["error"] is None
    assert [v["name"] for v in report["checks"]] == [
        "imports",
        "format",
        "lint",
        "native",
        "host",
        "jax",
    ]
    assert all(v["exit_code"] == 0 for v in report["checks"])
    for name, count in (("host", 77), ("jax", 4)):
        suites = list(ET.parse(component / (name + "-tests.xml")).getroot().iter("testsuite"))
        assert sum(int(s.get("tests", "0")) for s in suites) == count
        assert all(
            int(s.get(key, "0")) == 0 for s in suites for key in ("errors", "failures", "skipped")
        )
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {
        relative: sha
        for relative, sha in report["source_sha256"].items()
        if "betse_tissue_profiles" in relative
    }
    assert len(owned) == 7
    for relative, sha in owned.items():
        assert digest(ROOT / relative) == sha
    native = read(component / "native-source/source-manifest.json")
    assert native["status"] == "passed"
    assert native["component_cases"] == 38 and native["limitations"] == 19
    assert not any(
        native[key]
        for key in (
            "production_cells_imported",
            "jax_imported",
            "geometry_or_cut_executed",
            "production_random_stream_claim",
            "full_simulator",
        )
    )
    assert len(native["records"]) == 57
    assert sum(r["status"] == "passed" for r in native["records"]) == 38
    assert all(
        r["status"] in ("passed", "captured_failure", "captured_limitation")
        for r in native["records"]
    )
    assert "Pillow" in native["versions"] and inputs["affinity"] == [7]
    guards = {
        name: read(component / (name + "-guard/result.json")) for name in ("native", "host", "jax")
    }
    for guard in guards.values():
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 1024**3
    evidence = {}
    for path in sorted((component / "evidence").glob("*.json")):
        record = read(path)
        assert record["status"] == "passed"
        evidence[path.name] = dict(path=str(path), sha256=digest(path))
    shutil.copyfile(ROOT / CONTRACT, output / "integration-contract.md")
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=digest(component / "result.json"),
        tests=report["tests"],
        host_tests=77,
        cpu_jax_tests=4,
        native_valid_cases=38,
        observed_native_limit_cases=19,
        verified_component_artifact_count=len(report["output_sha256"]),
        native_source_manifest_sha256=digest(component / "native-source/source-manifest.json"),
        owned_source_sha256=owned,
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        source_revision=native["revision"],
        source_version=native["version"],
        source_files=native["files"],
        executed_bodies=native["executed_bodies"],
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
        stable_ID_carry=read(component / "evidence/betse-tissue-profiles-stable-ID-carry.json"),
        prescribed_control_restart=read(
            component / "evidence/betse-tissue-profiles-jax-control-carry.json"
        ),
        pressure_clock_gradient=read(
            component / "evidence/betse-tissue-profiles-jax-clock-gradient.json"
        ),
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
                phase=read(p / "inputs.json")["phase"],
            )
            for p in sorted(component.parent.glob("betse-tissue-profiles-development-20261028-*"))
            if (p / "result.json").is_file()
        ],
        scope=(
            "Native profile/target/component arithmetic; explicit stable-ID carry is separate "
            "from native reselection; no geometry/cut/solver/checkpoint/full-tissue or "
            "material/energy parity"
        ),
        automatic_followup=False,
    )
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
    parser.add_argument("--component", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    finalize(args.component, args.output)
