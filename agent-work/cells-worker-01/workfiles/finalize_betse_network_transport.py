"""Freeze the existing successful native-transporter receipt and handoff metadata."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = "agent-work/cells-worker-01/workfiles/BETSE_NETWORK_TRANSPORT_HANDOFF.md"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report = read(component / "result.json")
    assert report["status"] == "passed"
    assert report["tests"] == dict(tests=123, errors=0, failures=0, skipped=0)
    assert not report["sources_changed_during_checks"]
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {
        relative: sha
        for relative, sha in report["source_sha256"].items()
        if "betse_network_transport" in relative
    }
    for relative, sha in owned.items():
        assert digest(ROOT / relative) == sha
    native = read(component / "native-source/source-manifest.json")
    assert native["status"] == "passed" and native["no_production_or_jax_imports"]
    assert native["successful_cases"] == 39 and native["expected_native_failures"] == 3
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
        host_tests=119,
        cpu_jax_tests=4,
        native_successful_cases=39,
        expected_native_failure_cases=3,
        native_source_manifest_sha256=digest(component / "native-source/source-manifest.json"),
        verified_component_artifact_count=len(report["output_sha256"]),
        owned_source_sha256=owned,
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        source_revision=native["revision"],
        source_version=native["version"],
        source_files=native["files"],
        resource_guards=guards,
        peak_process_tree_rss_bytes=max(
            g["sampled_peak_process_tree_rss_bytes"] for g in guards.values()
        ),
        minimum_available_host_memory_bytes=min(
            g["minimum_available_host_memory_bytes"] for g in guards.values()
        ),
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
            )
            for p in sorted(component.parent.glob("betse-network-transport-development-20261028-*"))
            if (p / "result.json").is_file()
        ],
        scope=(
            "Native generated-source component correspondence; "
            "no tissue integration, physical heat or full native simulation claim"
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
    parser.add_argument("--component", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    finalize(args.component, args.output)
