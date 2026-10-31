"""Assemble a new source-only packet from exact explicit frozen dependencies."""
# ruff: noqa: E501 -- Complete source provenance and review statements.

import ast
import hashlib
import json
import sys
from pathlib import Path

from betse_normal_ecm_reviewed_successors_resources import audit, manual_review
from prepare_betse_normal_ecm_molecule_transport_package import copy, sha, write

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-transport-prepared-20261031-01"
TRANSITION = BASE / "betse-normal-ecm-init-sim-transition-prepared-20261031-02"
INIT = BASE / "betse-normal-ecm-init-phase-prepared-20261031-04"
PREFIX = "betse_normal_ecm_molecule_lifecycle"
OUT = WORK / (PREFIX + "_prepared_02")
DEST = BASE / "betse-normal-ecm-molecule-lifecycle-prepared-20261031-01"


def classify(resources):
    reviewed = manual_review(resources)
    outputs = {
        "tests/unit/test_betse_normal_ecm_init_phase.py",
        "tests/unit/test_betse_normal_ecm_init_sim_transition.py",
        "tests/unit/test_betse_normal_ecm_molecule_transport.py",
        "tests/unit/test_" + PREFIX + "_capture.py",
    }
    for rows in (reviewed["reviewed_unresolved_reads"], reviewed["pending_manual_reads"]):
        for row in rows:
            if row.get("classification") != "manual_resolution_pending":
                continue
            if (
                row.get("module") in outputs
                and row.get("containing_function") == "references"
                and row.get("expression") == "output.read_text()"
            ):
                row.update(
                    classification="future_fresh_reference_output",
                    rationale="Read the output JSON of the just-completed checked fresh conditional subprocess; not a packaged scientific input",
                )
            elif (
                row.get("module")
                in {
                    "validation/betse/betse_normal_ecm_init_phase_reference.py",
                    "validation/betse/" + PREFIX + "_reference.py",
                }
                and row.get("containing_function") == "file_record"
                and row.get("expression") == "path.open('rb')"
            ):
                row.update(
                    classification="hash_failure_input_or_already_written_output",
                    rationale="Reviewed file_record is called only for the explicit input/output paths and already-created raw reference files during refusal capture; it verifies regular-file status and hashes bytes without evaluating science.",
                )
    reviewed["pending_manual_reads"] = [
        r
        for r in reviewed["pending_manual_reads"]
        if r.get("classification") == "manual_resolution_pending"
    ]
    return reviewed


def main():
    if OUT.exists() or DEST.exists():
        raise ValueError("Preserve existing source/evidence paths")
    dependencies = json.loads((WORK / (PREFIX + "_dependencies_01.json")).read_text())
    for item in dependencies["parents"].values():
        folder = Path(item["path"])
        assert sha(folder / "MANIFEST.json") == item["manifest_sha256"]
        assert sha(folder / "inputs.json") == item["inputs_sha256"]
    parent = json.loads((PARENT / "inputs.json").read_text())
    transition = json.loads((TRANSITION / "inputs.json").read_text())
    overrides = dependencies["reviewed_reference_overrides"]
    OUT.mkdir()
    source = OUT / "source"
    origins = {}
    for folder, declared in ((PARENT, parent), (TRANSITION, transition)):
        for name, pin in declared["source_sha256"].items():
            if name in overrides:
                assert pin == overrides[name]["historical_INIT02_sha256"]
                continue
            if (source / name).exists():
                assert sha(source / name) == pin, name
            else:
                copy(folder / "source" / name, source / name, pin)
                origins[name] = str(folder)
    for name, item in overrides.items():
        copy(INIT / "source" / name, source / name, item["INIT04_sha256"])
        origins[name] = "explicit reviewed INIT04 reference override for new lifecycle only"
    own = []
    capture_dependency = json.loads((WORK / (PREFIX + "_capture_dependency_01.json")).read_text())
    helper = capture_dependency["helper"]
    copy(Path(helper["path"]), source / helper["relative"], helper["sha256"])
    origins[helper["relative"]] = "explicit Root-reviewed generic failure-capture helper"
    for directory in (
        ROOT / "src/cells/processes",
        ROOT / "validation/betse",
        ROOT / "tests/unit",
        WORK,
    ):
        for path in sorted(directory.glob("*" + PREFIX + "*")):
            if path.is_file():
                if "_package_preparation_" in path.name:
                    continue
                name = str(path.relative_to(ROOT))
                copy(path, source / name)
                own.append(name)
    for declared in (parent, transition):
        for name, pin in declared["source_sha256"].items():
            assert sha(source / name) == (
                overrides[name]["INIT04_sha256"] if name in overrides else pin
            ), name
    for name, pin in parent["native_snapshot_sha256"].items():
        copy(PARENT / name, OUT / name, pin)
    for label, item in dependencies["parents"].items():
        folder = Path(item["path"])
        for name in ("MANIFEST.json", "inputs.json", "SOURCE_STATIC_REVIEW.json"):
            copy(folder / name, OUT / "lineage" / (label + "-" + name))
    for key in ("INIT04_handoff", "INIT04_dependency_review"):
        item = dependencies[key]
        copy(Path(item["path"]), OUT / "lineage" / (key + ".json"), item["sha256"])
    write(
        OUT / "lineage/source-origins.json",
        dict(origins=origins, overrides=overrides, historical_transition02_rebased=False),
    )
    copy(
        WORK / (PREFIX + "_prepared_01/resource-audit.json"),
        OUT / "prior-static/resource-audit-attempt01.json",
    )
    copy(
        WORK / (PREFIX + "_package_preparation_01.log"), OUT / "prior-static/package-attempt01.log"
    )
    copy(
        Path(capture_dependency["review"]["path"]),
        OUT / "lineage/failure-capture-Root-review.json",
        capture_dependency["review"]["sha256"],
    )
    copy(WORK / (PREFIX + "_driver.py"), OUT / "driver.py")
    (OUT / ".execution_hold").write_text(
        "Source-only phase-aware molecule/GRN transporter lifecycle. Metadata-only driver cannot launch science. Chief owns independent review and a separately requested release controller.\n"
    )
    resources = audit(source, PREFIX)
    reviewed = classify(resources)
    write(
        OUT / "resource-audit.json",
        dict(
            inventory=resources, review=reviewed, scientific_imports=0, scientific_AST_executions=0
        ),
    )
    if reviewed["pending_manual_reads"] or resources["literal_resource_audit"]["missing_resources"]:
        print(
            json.dumps(
                dict(
                    status="resource_classification_pending",
                    pending=reviewed["pending_manual_reads"],
                    missing=resources["literal_resource_audit"]["missing_resources"],
                )
            )
        )
        raise ValueError("Preserve unresolved source resource evidence")
    tools = OUT / "tools"
    for name in ("capture_binding.py", "archive_binding.py", "qualification_typed_evidence.py"):
        copy(PARENT / "tools" / name, tools / name)
    accounting = json.loads((PARENT / "tools/accounting.json").read_text())
    accounting["scope_profiles"] = ["ordinary_ecm_molecule_lifecycle_01"]
    accounting["status"] = "phase_aware_molecule_lifecycle_format_profile_held_for_Chief_review"
    external = {
        path: pin for path, pin in accounting["source_sha256"].items() if Path(path).is_absolute()
    }
    assert len(external) == 6
    writers, sites = {}, []
    for name, pin in resources["scientific_import_closure"].items():
        for node in ast.walk(ast.parse((source / name).read_text())):
            if isinstance(node, ast.Call) and (
                ast.unparse(node.func).endswith("write_archive")
                or ast.unparse(node.func) == "archive"
            ):
                writers["source/" + name] = pin
                sites.append(
                    dict(
                        module=name,
                        line=node.lineno,
                        callee=ast.unparse(node.func),
                        AST_sha256=hashlib.sha256(
                            ast.dump(node, include_attributes=False).encode()
                        ).hexdigest(),
                    )
                )
    for name in (
        "validation/betse/betse_normal_current_native.py",
        "validation/betse/betse_fast_solver_native.py",
    ):
        writers["source/" + name] = sha(source / name)
    accounting["source_sha256"] = external | writers
    for key in (
        "INIT_archive_call_sites",
        "general_molecule_archive_call_sites",
        "general_transporter_archive_call_sites",
    ):
        accounting.pop(key, None)
    accounting["molecule_lifecycle_archive_call_sites"] = sites
    write(tools / "accounting.json", accounting)
    write(
        tools / "inputs.json",
        dict(
            kind="cells.held_molecule_lifecycle_capture_profile@1",
            profiles=dict(
                ordinary_ecm_molecule_lifecycle_01=dict(
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
    queue = json.loads((WORK / (PREFIX + "_workqueue.json")).read_text())
    source_audit = json.loads((WORK / (PREFIX + "_implementation_audit_03.json")).read_text())
    for name, pin in source_audit["source_sha256"].items():
        assert hashes[name] == pin, name
    inputs = dict(
        kind="cells.held_molecule_lifecycle_package@1",
        status="source_static_prepared_unrun",
        execution_hold=True,
        driver_metadata_only=True,
        execution_hold_reasons=[
            "Chief independent source/resource/capture review",
            "Separately requested release controller and coordinated scientific round",
            "No inherited or new numerical pass",
        ],
        parent=dict(
            path=str(PARENT),
            manifest_sha256=sha(PARENT / "MANIFEST.json"),
            inputs_sha256=sha(PARENT / "inputs.json"),
        ),
        explicit_dependencies=dependencies,
        failure_capture_dependency=capture_dependency,
        reference_overrides_for_new_packet_only=overrides,
        own_files=own,
        source_sha256=hashes,
        native_snapshot_sha256=parent["native_snapshot_sha256"],
        live_native_source_sha256=parent["live_native_source_sha256"],
        native_checkout=parent["native_checkout"],
        installed_native_package=parent["installed_native_package"],
        driver_sha256=sha(OUT / "driver.py"),
        tool_sha256={str(p.relative_to(OUT)): sha(p) for p in sorted(tools.iterdir())},
        resource_audit_sha256=sha(OUT / "resource-audit.json"),
        resources=parent["resources"],
        groups=queue["groups"],
        planned=queue["planned"],
        source_audit=dict(
            path="source/agent-work/cells-worker-01/workfiles/"
            + PREFIX
            + "_implementation_audit_03.json",
            sha256=sha(WORK / (PREFIX + "_implementation_audit_03.json")),
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
            kind="cells.held_molecule_lifecycle_author_receipt@1",
            status="held_unrun",
            inputs_sha256=sha(OUT / "inputs.json"),
            source_audit=inputs["source_audit"],
            source_files=len(hashes),
            runtime_modules=len(resources["scientific_import_closure"]),
            reference_modules=len(resources["reference_closure"]),
            resource_files=len(reviewed["resource_sha256"]),
            classified_reads=len(reviewed["reviewed_unresolved_reads"]),
            pending_reads=0,
            explicit_parent_union_exact_except_reviewed_reference_overrides=True,
            historical_transition02_unchanged=True,
            strict_metadata_only_driver=True,
            prospective=queue["planned"],
            inherited_oracle_domains_and_failures_preserved=True,
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_model_reference_evaluations=0,
            pytest_collections=0,
            numerical_runs=0,
            inherited_scientific_passes=0,
        ),
    )
    write(
        OUT / "MANIFEST.json",
        dict(
            kind="cells.held_molecule_lifecycle_preparation_manifest@1",
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
                pending_reads=len(reviewed["pending_manual_reads"]),
                manifest_sha256=sha(OUT / "MANIFEST.json"),
            )
        )
    )


if __name__ == "__main__":
    main()
