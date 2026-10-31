"""Seal/freeze the completed source and bounded metadata handoff only."""
# ruff: noqa: E501 -- Complete handoff provenance strings.

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
PREFIX = "betse_normal_ecm_molecule_transport"
PACKAGE = WORK / (PREFIX + "_prepared_01")
METADATA = WORK / (PREFIX + "_metadata_01")
DEST = Path("/mnt/workspaces/Cells/betse-normal-ecm-molecule-transport-prepared-20261031-01")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-molecule-dispatch-prepared-20261031-01")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def verify(root):
    manifest = json.loads((root / "MANIFEST.json").read_text())
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    assert actual == set(manifest["files"]) | {"MANIFEST.json"}
    for name, pin in manifest["files"].items():
        path = root / name
        assert not path.is_symlink() and sha(path) == pin, name
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    verify(PACKAGE)
    assert (
        sha(PARENT / "MANIFEST.json")
        == "e51f7eead8d6bfe3a0e4f669005386e6f4271632f0531084754320025b1ed922"
    )
    if not args.freeze:
        if (PACKAGE / "preparation-manifest.json").exists():
            raise ValueError("Preparation is already sealed")
        metadata = json.loads((METADATA / "result.json").read_text())
        assert metadata["status"] == "passed" and len(metadata["controls"]) == 10
        assert all(c["passed"] for c in metadata["controls"])
        shutil.copyfile(PACKAGE / "MANIFEST.json", PACKAGE / "preparation-manifest.json")
        shutil.copytree(METADATA, PACKAGE / "metadata-01", copy_function=shutil.copyfile)
        for attempt in (1, 2, 3):
            source = WORK / (PREFIX + "_regenerated_" + str(attempt).zfill(2))
            shutil.copytree(
                source,
                PACKAGE / ("source-regeneration-" + str(attempt).zfill(2)),
                copy_function=shutil.copyfile,
            )
        tools = PACKAGE / "preparation-scripts"
        tools.mkdir()
        shutil.copyfile(Path(__file__), tools / Path(__file__).name)
        shutil.copyfile(
            WORK / (PREFIX + "_package_preparation_01.log"), PACKAGE / "preparation.log"
        )
        receipt = json.loads((PACKAGE / "SOURCE_STATIC_REVIEW.json").read_text())
        receipt.update(
            metadata=dict(
                path="metadata-01/result.json",
                sha256=sha(METADATA / "result.json"),
                controls_passed=10,
                max_rss_bytes=metadata["max_rss_bytes"],
                large_archive_constructed=False,
            ),
            static_checks=dict(
                Ruff_without_cache=True, compile_without_execution=True, AST_proofs=55
            ),
            source_boundary=dict(
                path="source/agent-work/cells-worker-01/workfiles/" + PREFIX + "_boundary_01.json",
                sha256=sha(WORK / (PREFIX + "_boundary_01.json")),
                methods=14,
                native_files_installed_exact=332,
            ),
            capture_profile="ordinary_ecm_molecule_transport_01",
            capture_format_member_limit=310689,
            capture_case_maximum_claim=False,
            capture_all_cases_fit_claim=False,
            initial_static_failures_preserved=True,
            all_numerical_cases_and_forms_unrun=True,
            arbitrary_pump_weight_activation=False,
            dormant_redistribution_activated=False,
            inherited_failure="signed_environment 39/40 remains failed; catalog05 82 passed/one Nav reference refusal/11 unrun. No prior scientific pass transferred.",
            shared_frozen_or_PROGRESS_edits=False,
            no_transition_dependency_adopted=True,
        )
        (PACKAGE / "SOURCE_STATIC_REVIEW.json").unlink()
        write(PACKAGE / "SOURCE_STATIC_REVIEW.json", receipt)
        (PACKAGE / "MANIFEST.json").unlink()
        write(
            PACKAGE / "MANIFEST.json",
            dict(
                kind="cells.held_general_ECM_transporter_manifest@1",
                status="held_unrun",
                scientific_evaluations=0,
                files={
                    str(p.relative_to(PACKAGE)): sha(p)
                    for p in sorted(PACKAGE.rglob("*"))
                    if p.is_file() and p != PACKAGE / "MANIFEST.json"
                },
            ),
        )
        manifest = verify(PACKAGE)
        print(
            json.dumps(
                dict(
                    status="sealed_held",
                    artifacts=len(manifest["files"]),
                    manifest_sha256=sha(PACKAGE / "MANIFEST.json"),
                    inputs_sha256=sha(PACKAGE / "inputs.json"),
                    receipt_sha256=sha(PACKAGE / "SOURCE_STATIC_REVIEW.json"),
                )
            )
        )
    else:
        if DEST.exists():
            raise ValueError("Never replace an immutable handoff")
        shutil.copytree(PACKAGE, DEST, copy_function=shutil.copyfile)
        manifest = verify(DEST)
        receipt = json.loads((DEST / "SOURCE_STATIC_REVIEW.json").read_text())
        inputs = json.loads((DEST / "inputs.json").read_text())
        handoff = dict(
            kind="cells.held_general_ECM_transporter_handoff@1",
            status="source_static_complete_held_for_Chief_review",
            package=str(DEST),
            manifest_sha256=sha(DEST / "MANIFEST.json"),
            inputs_sha256=sha(DEST / "inputs.json"),
            source_static_receipt_sha256=sha(DEST / "SOURCE_STATIC_REVIEW.json"),
            parent_manifest_sha256=sha(PARENT / "MANIFEST.json"),
            transporter_inputs_sha256="8f0f502049d62344c36df591da920314c54f26b78a1ea6f36f34ea9936af45cd",
            artifacts=len(manifest["files"]),
            source_files=receipt["source_files"],
            runtime_modules=receipt["runtime_modules"],
            reference_modules=receipt["reference_modules"],
            resource_files=receipt["resource_files"],
            pending_reads=0,
            AST_proofs=55,
            native_methods_audited=14,
            native_files_installed_exact=332,
            capture_metadata_controls=10,
            prospective=inputs["planned"],
            notes="source/agent-work/cells-worker-01/workfiles/" + PREFIX + "_implementation.md",
            driver_metadata_only=True,
            arbitrary_pump_weight_activation=False,
            shared_and_frozen_sources_edited=False,
            oracle_domains_or_existing_budgets_changed=False,
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_model_reference_evaluations=0,
            pytest_collections=0,
            numerical_runs=0,
            active_job_queries=0,
            inherited_scientific_passes=0,
            automatic_launch=False,
            automatic_followup=False,
        )
        write(WORK / (PREFIX + "_handoff_01.json"), handoff)
        print(json.dumps(handoff, sort_keys=True))
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )


if __name__ == "__main__":
    main()
