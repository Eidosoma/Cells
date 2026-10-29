"""Freeze existing qualified deformation evidence and ownership metadata only."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "agent-work/cells-worker-01/workfiles/BETSE_DEFORMATION_HANDOFF.md"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report = read(component / "result.json")
    assert report["status"] == "passed"
    assert report["tests"] == dict(tests=58, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {
        relative: sha
        for relative, sha in report["source_sha256"].items()
        if "betse_deformation" in relative
    }
    assert len(owned) == 7
    for relative, sha in owned.items():
        assert digest(ROOT / relative) == sha
    native = read(component / "native-source/source-manifest.json")
    assert native["status"] == "passed"
    assert not native["production_cells_imported"] and not native["jax_imported"]
    assert (
        native["component_cases"] == 20
        and native["display_cases"] == 4
        and native["limitations"] == 10
    )
    assert not native["time_deformation_enabled"] and not native["checks_native_geometry_rebuild"]
    guards = {
        name: read(component / (name + "-guard/result.json")) for name in ("native", "host", "jax")
    }
    for guard in guards.values():
        assert guard["status"] == "completed"
        assert guard["sampled_peak_process_tree_rss_bytes"] <= 2**30
        assert guard["minimum_available_host_memory_bytes"] >= 8 * 1024**3
    shutil.copyfile(ROOT / CONTRACT, output / "integration-contract.md")
    shutil.copyfile(Path(__file__), output / "finalize.py")
    result = dict(
        status="passed",
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=digest(component / "result.json"),
        tests=report["tests"],
        host_tests=54,
        cpu_jax_tests=4,
        native_forcing_cases=20,
        native_display_cases=4,
        observed_native_limit_cases=10,
        verified_component_artifact_count=len(report["output_sha256"]),
        native_source_manifest_sha256=digest(component / "native-source/source-manifest.json"),
        owned_source_sha256=owned,
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        source_revision=native["revision"],
        source_version=native["version"],
        source_files=native["files"],
        scipy_version=native["scipy_version"],
        resource_guards=guards,
        peak_process_tree_rss_bytes=max(
            g["sampled_peak_process_tree_rss_bytes"] for g in guards.values()
        ),
        minimum_available_host_memory_bytes=min(
            g["minimum_available_host_memory_bytes"] for g in guards.values()
        ),
        spatial_refinement=read(component / "evidence/betse-deformation-spatial-refinement.json"),
        disabled_time_refinement=read(
            component / "evidence/betse-deformation-disabled-time-refinement.json"
        ),
        display_repeat=read(component / "evidence/betse-deformation-display-repeat.json"),
        initialization_reset=read(component / "native-source/initialization-reset.json"),
        primed_restart=read(component / "evidence/betse-deformation-jax-primed-restart.json"),
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
                phase=read(p / "inputs.json").get("phase"),
            )
            for p in sorted(component.parent.glob("betse-deformation-development-20261028-*"))
            if (p / "result.json").is_file()
        ],
        scope="Actual native arithmetic and bounded mathematical/display checks; time remains disabled and no physical geometry/material/force-energy/tissue parity is inferred",
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
