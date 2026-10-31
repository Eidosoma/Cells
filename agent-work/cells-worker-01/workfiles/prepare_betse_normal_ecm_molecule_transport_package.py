"""Copy/hash/parse a held source package; never import or execute science."""
# ruff: noqa: E501 -- Complete provenance and resource classifications.

import ast
import hashlib
import json
import shutil
import sys
from pathlib import Path

from betse_normal_ecm_reviewed_successors_resources import audit, manual_review

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01"
TRANSPORTER = BASE / "betse-normal-transporter-prepared-20261030-03"
PREFIX = "betse_normal_ecm_molecule_transport"
OUT = WORK / (PREFIX + "_prepared_01")
DEST = BASE / "betse-normal-ecm-molecule-transport-prepared-20261031-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def copy(source, target, pin=None):
    if source.is_symlink() or not source.is_file() or pin is not None and sha(source) != pin:
        raise ValueError("Wrong immutable source " + str(source))
    if target.exists():
        raise ValueError("Never overwrite an existing evidence member " + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(source) == sha(target)


def classify(resources):
    reviewed = manual_review(resources)
    for rows in (reviewed["reviewed_unresolved_reads"], reviewed["pending_manual_reads"]):
        for row in rows:
            if row.get("classification") != "manual_resolution_pending":
                continue
            module = row.get("module", "")
            function = row.get("containing_function")
            expression = row.get("expression")
            if (
                module == "tests/unit/test_" + PREFIX + ".py"
                and function == "references"
                and expression == "output.read_text()"
            ):
                row.update(
                    classification="future_fresh_reference_output",
                    rationale="Output of a checked fresh subprocess, not a packaged scientific input",
                )
            elif module == "validation/betse/" + PREFIX + "_native_network.py" and function in (
                "science",
                "literal_nodes",
            ):
                row.update(
                    classification="authenticated_native_source_or_protocol",
                    rationale="Literal native networks/toolbox source and catalog protocol only; checkout/installed equality and explicit SHA256 are checked before compilation. Frozen parent binds the protocol and complete native pins.",
                )
    reviewed["pending_manual_reads"] = [
        r
        for r in reviewed["pending_manual_reads"]
        if r.get("classification") == "manual_resolution_pending"
    ]
    return reviewed


def main():
    if OUT.exists() or DEST.exists():
        raise ValueError("Use exclusive preparation/freeze paths")
    assert (
        sha(PARENT / "MANIFEST.json")
        == "e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922"
    )
    assert (
        sha(TRANSPORTER / "inputs.json")
        == "8f0f502049d62344c36df591da920314c54f26b78a1ea6f36f34ea9936af45cd"
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
    for name, pin in parent["source_sha256"].items():
        assert sha(source / name) == pin, name
    component_files = {}
    for name in (
        "src/cells/processes/betse_normal_transporter_source.py",
        "src/cells/processes/betse_network_transport.py",
        "validation/betse/betse_normal_transporter_join_reference.py",
        "validation/transport/betse_network_transport_protocol.json",
    ):
        assert (TRANSPORTER / "source" / name).read_bytes() == (source / name).read_bytes(), name
        component_files[name] = sha(source / name)
    for name, pin in parent["native_snapshot_sha256"].items():
        copy(PARENT / name, OUT / name, pin)
    for parent_file in ("MANIFEST.json", "inputs.json", "SOURCE_STATIC_REVIEW.json"):
        copy(PARENT / parent_file, OUT / "lineage" / ("MOLECULE01-" + parent_file))
    copy(TRANSPORTER / "inputs.json", OUT / "lineage/transporter03-inputs.json")
    copy(WORK / (PREFIX + "_driver.py"), OUT / "driver.py")
    (OUT / ".execution_hold").write_text(
        "Source-only configured general-owner ECM transport. Metadata-only driver cannot launch science. Chief owns independent review and any separately requested release controller.\n"
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
    accounting["scope_profiles"] = ["ordinary_ecm_molecule_transport_01"]
    accounting["status"] = "general_transporter_format_profile_held_for_Chief_review"
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
    for key in ("INIT_archive_call_sites", "general_molecule_archive_call_sites"):
        accounting.pop(key, None)
    accounting["general_transporter_archive_call_sites"] = sites
    write(tools / "accounting.json", accounting)
    write(
        tools / "inputs.json",
        dict(
            kind="cells.held_general_ECM_transporter_capture_profile@1",
            profiles=dict(
                ordinary_ecm_molecule_transport_01=dict(
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
        kind="cells.held_general_ECM_transporter_package@1",
        status="source_static_prepared_unrun",
        execution_hold=True,
        driver_metadata_only=True,
        execution_hold_reasons=[
            "Chief independent source/resource/capture review",
            "Separate requested release controller and coordinated scientific round",
            "No inherited or new numerical pass",
        ],
        parent=dict(
            path=str(PARENT),
            manifest_sha256=sha(PARENT / "MANIFEST.json"),
            inputs_sha256=sha(PARENT / "inputs.json"),
        ),
        transporter_dependency=dict(
            path=str(TRANSPORTER),
            inputs_sha256=sha(TRANSPORTER / "inputs.json"),
            common_files_sha256=component_files,
            pass_credit=False,
        ),
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
            kind="cells.held_general_ECM_transporter_author_receipt@1",
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
            transporter_component_dependencies_exact=True,
            strict_metadata_only_driver=True,
            prospective=queue["planned"],
            inherited_oracle_domains_and_failures_preserved=True,
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
            kind="cells.held_general_ECM_transporter_preparation_manifest@1",
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
