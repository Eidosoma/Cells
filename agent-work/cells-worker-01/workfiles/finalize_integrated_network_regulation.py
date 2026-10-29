"""Freeze complete regulated-calcium evidence and unapplied dispatch metadata."""

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = "agent-work/cells-worker-01/workfiles/"
CONTRACT = WORK + "INTEGRATED_NETWORK_REGULATION_HANDOFF.md"
PATCH = WORK + "integrated_network_regulation_dispatch.patch"
DISPATCH = WORK + "integrated_network_regulation_dispatch.json"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(component, output):
    output.mkdir(exist_ok=False)
    report, inputs = (read(component / name) for name in ("result.json", "inputs.json"))
    assert report["status"] == "passed" and inputs["phase"] == "complete-integrated-model"
    assert report["tests"] == dict(tests=46, errors=0, failures=0, skipped=0)
    assert report["error"] is None and not report["sources_changed_during_checks"]
    assert [r["name"] for r in report["checks"]] == ["imports", "format", "lint", "host", "jax"]
    assert all(r["exit_code"] == 0 for r in report["checks"])
    for name, count in (("host", 43), ("jax", 3)):
        suites = list(ET.parse(component / (name + "-tests.xml")).getroot().iter("testsuite"))
        assert sum(int(s.get("tests", "0")) for s in suites) == count
        assert all(
            int(s.get(k, "0")) == 0 for s in suites for k in ("errors", "failures", "skipped")
        )
    for relative, sha in report["output_sha256"].items():
        assert digest(component / relative) == sha, str(component / relative)
    owned = {
        p: sha
        for p, sha in report["source_sha256"].items()
        if "regulated" in p or "integrated_network_regulation" in p
    }
    assert len(owned) == 7
    for p, sha in owned.items():
        assert digest(ROOT / p) == sha
    protocol = read(ROOT / "validation/regulation/integrated_network_regulation_protocol.json")
    for p, sha in protocol["readonly_source_sha256"].items():
        assert digest(ROOT / p) == sha == report["source_sha256"][p]
    native = protocol["frozen_native_handoff"]
    assert digest(Path(native["path"])) == native["sha256"]
    assert read(Path(native["path"]))["status"] == "passed"
    assert inputs["affinity"] == [7] and inputs["environment"]["JAX_PLATFORMS"] == "cpu"
    assert inputs["environment"]["JAX_ENABLE_COMPILATION_CACHE"] == "false"
    guards = {n: read(component / (n + "-guard/result.json")) for n in ("host", "jax")}
    for name, g in guards.items():
        assert g["status"] == "completed"
        assert g["sampled_peak_process_tree_rss_bytes"] <= (4 if name == "jax" else 1) * 2**30
        assert g["minimum_available_host_memory_bytes"] >= 8 * 2**30
    evidence = {}
    for p in sorted((component / "evidence").glob("*.json")):
        assert read(p)["status"] == "passed"
        evidence[p.name] = dict(path=str(p), sha256=digest(p))
    assert len(evidence) == 42
    dispatch = read(ROOT / DISPATCH)
    assert (
        dispatch["status"] == "prepared-not-applied"
        and digest(ROOT / PATCH) == dispatch["patch_sha256"]
    )
    current_shared = {
        p: dict(
            current_sha256=digest(ROOT / p),
            matches_prepared_before=digest(ROOT / p) == s["before_sha256"],
        )
        for p, s in dispatch["shared_files"].items()
    }
    for source, dest in (
        (CONTRACT, "integration-contract.md"),
        (PATCH, "dispatch.patch"),
        (DISPATCH, "dispatch.json"),
    ):
        shutil.copyfile(ROOT / source, output / dest)
    shutil.copyfile(Path(__file__), output / "finalize.py")
    scipy_metadata = list(
        Path("/mnt/workspaces/Cells/venv-cpu/lib/python3.13/site-packages").glob(
            "scipy-*.dist-info/METADATA"
        )
    )
    assert len(scipy_metadata) == 1
    metadata = scipy_metadata[0]
    version = next(
        v.split(": ", 1)[1] for v in metadata.read_text().splitlines() if v.startswith("Version: ")
    )
    shutil.copyfile(metadata, output / "scipy-METADATA")
    result = dict(
        status="passed",
        model_id=protocol["model_id"],
        parent=protocol["parent"],
        state_fields=38,
        component_receipt=str(component / "result.json"),
        component_receipt_sha256=digest(component / "result.json"),
        tests=report["tests"],
        host_tests=43,
        cpu_jax_tests=3,
        verified_component_artifact_count=len(report["output_sha256"]),
        owned_source_sha256=owned,
        readonly_source_sha256=protocol["readonly_source_sha256"],
        frozen_native_source=native,
        integration_contract=dict(path=CONTRACT, sha256=digest(ROOT / CONTRACT)),
        unapplied_dispatch=dispatch,
        current_shared_patch_inputs=current_shared,
        cpu_runtime_versions=inputs["versions"],
        installed_scipy_metadata=dict(version=version, path=str(metadata), sha256=digest(metadata)),
        resource_guards=guards,
        peak_host_rss_bytes=guards["host"]["sampled_peak_process_tree_rss_bytes"],
        peak_compiled_rss_bytes=guards["jax"]["sampled_peak_process_tree_rss_bytes"],
        minimum_available_host_memory_bytes=min(
            g["minimum_available_host_memory_bytes"] for g in guards.values()
        ),
        evidence=evidence,
        coupled_refinement=read(
            component / "evidence/integrated-network-regulation-coupled-cpu-refinement.json"
        ),
        full_jax_stage=read(
            component / "evidence/integrated-network-regulation-jax-full-stage.json"
        ),
        complete_jax_trajectory=read(
            component / "evidence/integrated-network-regulation-jax-rk4-restart.json"
        ),
        owner_derivatives=read(
            component / "evidence/integrated-network-regulation-jax-owner-derivatives.json"
        ),
        attempts=[
            dict(
                path=str(p / "result.json"),
                sha256=digest(p / "result.json"),
                status=read(p / "result.json")["status"],
            )
            for p in sorted(
                component.parent.glob("integrated-network-regulation-development-20261029-*")
            )
            if (p / "result.json").is_file()
        ],
        scope=(
            "New Cells common-stage, scheduled-times-native-factor Na/K regulation; "
            "existing 38-field physical ownership and ledgers. Native SIM lag/order, "
            "registered CLI/assembly/shared checkpoint and monolithic checked-step "
            "resource claims remain separate."
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
