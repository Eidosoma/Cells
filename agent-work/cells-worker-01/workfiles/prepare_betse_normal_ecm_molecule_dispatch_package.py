"""Copy/hash/compile/resource preparation of a new held general_molecule source tree."""
# ruff: noqa: E501 -- source scope and hold metadata prose.

import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

from betse_normal_ecm_reviewed_successors_resources import audit, manual_review

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02")
OUT = WORK / "betse_normal_ecm_molecule_dispatch_prepared_01"
DEST = Path("/mnt/workspaces/Cells/betse-normal-ecm-molecule-dispatch-prepared-20261031-01")
PREFIX = "betse_normal_ecm_molecule_dispatch"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def copy(source, target, pin=None):
    if source.is_symlink() or not source.is_file() or pin is not None and sha(source) != pin:
        raise ValueError("Wrong immutable source: " + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("Do not replace a parent or existing prepared artifact: " + str(target))
    shutil.copyfile(source, target)
    assert sha(source) == sha(target)


def main():
    if OUT.exists() or DEST.exists():
        raise ValueError("Use exclusive new preparation and freeze destinations")
    assert (
        sha(PARENT / "MANIFEST.json")
        == "528a1c7d1df0be152919b9dd446f3247676856585652f2c2924d82840c27d36f"
    )
    parent = json.loads((PARENT / "inputs.json").read_text())
    OUT.mkdir()
    source = OUT / "source"
    for name, pin in parent["source_sha256"].items():
        copy(PARENT / "source" / name, source / name, pin)
    own = []
    for directory in (
        ROOT / "src/cells/processes",
        ROOT / "validation/betse",
        ROOT / "tests/unit",
        WORK,
    ):
        for path in sorted(directory.glob("*" + PREFIX + "*")):
            if path.is_file():
                relative = str(path.relative_to(ROOT))
                copy(path, source / relative)
                own.append(relative)
    # All existing scientific/common sources stay byte-exact to sealed INIT02.
    for name, pin in parent["source_sha256"].items():
        assert sha(source / name) == pin, name
    for name, pin in parent["native_snapshot_sha256"].items():
        copy(PARENT / name, OUT / name, pin)
    copy(PARENT / "MANIFEST.json", OUT / "lineage/INIT02-MANIFEST.json")
    copy(PARENT / "inputs.json", OUT / "lineage/INIT02-inputs.json")
    review = Path(
        "/mnt/workspaces/Cells/betse-normal-ecm-init-phase-preflight-20261031-02/REVIEW.json"
    )
    assert sha(review) == "09ddb3c75ddef1492744932e16ae7c40890dc1df6ba2c077b3553717190a9fd2"
    copy(review, OUT / "lineage/INIT02-independent-REVIEW.json")
    copy(WORK / f"{PREFIX}_driver.py", OUT / "driver.py")
    (OUT / ".execution_hold").write_text(
        "Source-only general-molecule preparation. No science launch; Chief review and separate explicitly requested release controller required.\n"
    )
    resources = audit(source, PREFIX)
    reviewed = manual_review(resources)
    for rows in (reviewed["reviewed_unresolved_reads"], reviewed["pending_manual_reads"]):
        for row in rows:
            if (
                row.get("classification") == "manual_resolution_pending"
                and row.get("module")
                in (
                    "tests/unit/test_" + PREFIX + ".py",
                    "tests/unit/test_betse_normal_ecm_init_phase.py",
                )
                and row.get("containing_function") == "references"
                and row.get("expression") == "output.read_text()"
            ):
                row.update(
                    classification="future_fresh_reference_output",
                    rationale="Explicit output of checked fresh subprocess, not packaged input",
                )
    reviewed["pending_manual_reads"] = [
        r
        for r in reviewed["pending_manual_reads"]
        if r.get("classification") == "manual_resolution_pending"
    ]
    write(
        OUT / "resource-audit.json",
        dict(
            inventory=resources, review=reviewed, scientific_imports=0, scientific_AST_executions=0
        ),
    )
    if reviewed["pending_manual_reads"] or resources["literal_resource_audit"]["missing_resources"]:
        raise ValueError("Resource classification incomplete; preserve pending evidence")
    tools = OUT / "tools"
    for name in ("capture_binding.py", "archive_binding.py", "qualification_typed_evidence.py"):
        copy(PARENT / "tools" / name, tools / name)
    accounting = json.loads((PARENT / "tools/accounting.json").read_text())
    accounting["scope_profiles"] = ["ordinary_ecm_molecule_dispatch_01"]
    accounting["status"] = "general_molecule_format_profile_held_for_Chief_review"
    external = {
        path: pin for path, pin in accounting["source_sha256"].items() if Path(path).is_absolute()
    }
    assert len(external) == 6
    writers, sites = {}, []
    for relative, pin in resources["scientific_import_closure"].items():
        tree = ast.parse((source / relative).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                ast.unparse(node.func).endswith("write_archive")
                or ast.unparse(node.func) == "archive"
            ):
                writers["source/" + relative] = pin
                sites.append(
                    dict(
                        module=relative,
                        line=node.lineno,
                        callee=ast.unparse(node.func),
                        AST_sha256=hashlib.sha256(
                            ast.dump(node, include_attributes=False).encode()
                        ).hexdigest(),
                    )
                )
    for relative in (
        "validation/betse/betse_normal_current_native.py",
        "validation/betse/betse_fast_solver_native.py",
    ):
        writers["source/" + relative] = sha(source / relative)
    accounting["source_sha256"] = external | writers
    accounting.pop("INIT_archive_call_sites", None)
    accounting["general_molecule_archive_call_sites"] = sites
    write(tools / "accounting.json", accounting)
    write(
        tools / "inputs.json",
        dict(
            kind="cells.held_general_molecule_capture_profile@1",
            profiles=dict(
                ordinary_ecm_molecule_dispatch_01=dict(
                    writer_source_sha256={str(DEST / name): pin for name, pin in writers.items()},
                    archive_call_sites=sites,
                )
            ),
            tool_sha256={
                name: sha(tools / name)
                for name in (
                    "capture_binding.py",
                    "archive_binding.py",
                    "qualification_typed_evidence.py",
                )
            },
            execution_hold=True,
            release_authorized=False,
            member_limit=310689,
            observed_case_maximum_claim=False,
            all_captures_fit_byte_caps_claim=False,
        ),
    )
    for path in source.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")
    hashes = {str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()}
    queue = json.loads((WORK / f"{PREFIX}_workqueue.json").read_text())
    source_audit = json.loads((WORK / f"{PREFIX}_implementation_audit_01.json").read_text())
    for name, pin in source_audit["source_sha256"].items():
        assert hashes[name] == pin, name
    inputs = dict(
        kind="cells.held_general_molecule_dispatch_package@1",
        status="source_static_prepared_unrun",
        execution_hold=True,
        execution_hold_reasons=[
            "Chief independent source/resource/capture review",
            "Separate requested release controller and CPU-coordinated scientific round",
            "No inherited or new numerical pass",
        ],
        parent=dict(
            path=str(PARENT),
            manifest_sha256=sha(PARENT / "MANIFEST.json"),
            inputs_sha256=sha(PARENT / "inputs.json"),
        ),
        own_files=own,
        source_sha256=hashes,
        native_snapshot_sha256=parent["native_snapshot_sha256"],
        live_native_source_sha256=parent["live_native_source_sha256"],
        native_checkout=parent["native_checkout"],
        installed_native_package=parent["installed_native_package"],
        driver_sha256=sha(OUT / "driver.py"),
        driver_metadata_only=True,
        tool_sha256={str(p.relative_to(OUT)): sha(p) for p in sorted(tools.iterdir())},
        resource_audit_sha256=sha(OUT / "resource-audit.json"),
        groups=queue["groups"],
        planned=queue["planned"],
        resources=parent["resources"],
        source_audit=dict(
            path="source/agent-work/cells-worker-01/workfiles/"
            + f"{PREFIX}_implementation_audit_01.json",
            sha256=sha(WORK / f"{PREFIX}_implementation_audit_01.json"),
            proofs=len(source_audit["proofs"]),
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_reference_model_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        active_job_queries=0,
        inherited_qualification=False,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    write(OUT / "inputs.json", inputs)
    write(
        OUT / "SOURCE_STATIC_REVIEW.json",
        dict(
            kind="cells.held_general_molecule_author_static_receipt@1",
            status="held_unrun",
            inputs_sha256=sha(OUT / "inputs.json"),
            source_audit=inputs["source_audit"],
            source_files=len(hashes),
            runtime_modules=len(resources["scientific_import_closure"]),
            reference_modules=len(resources["reference_closure"]),
            resource_files=len(reviewed["resource_sha256"]),
            classified_reads=len(reviewed["reviewed_unresolved_reads"]),
            pending_reads=0,
            parent_common_sources_unchanged=True,
            strict_metadata_only_driver=True,
            source_scope="Supplied ordinary FULL/ECM general and GRN owners, original setup/dispatch and prefix/commit/field conditionals; explicit disabled paths, no whole initializer/trajectory/persistence",
            inherited_oracle_domains_and_failures_preserved=True,
            prospective=queue["planned"],
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_model_reference_evaluations=0,
            pytest_collection=0,
            numerical_runs=0,
            inherited_scientific_passes=0,
        ),
    )
    write(
        OUT / "MANIFEST.json",
        dict(
            kind="cells.held_general_molecule_preparation_manifest@1",
            status="held_unrun",
            scientific_evaluations=0,
            files={str(p.relative_to(OUT)): sha(p) for p in sorted(OUT.rglob("*")) if p.is_file()},
        ),
    )
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )
    print(
        json.dumps(
            dict(
                status="held_prepared",
                source_files=len(hashes),
                runtime_modules=len(resources["scientific_import_closure"]),
                reference_modules=len(resources["reference_closure"]),
                resources=len(reviewed["resource_sha256"]),
                manifest_sha256=sha(OUT / "MANIFEST.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
