"""Seal locally, then copy/hash a new held handoff; no scientific execution."""

import argparse
import json
import shutil
import sys
from pathlib import Path

from finalize_betse_normal_ecm_molecule_transport_package import sha, verify, write

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
PREFIX = "betse_normal_ecm_molecule_lifecycle"
PACKAGE = WORK / (PREFIX + "_prepared_02")
METADATA = WORK / (PREFIX + "_metadata_01")
DEST = Path("/mnt/workspaces/Cells/betse-normal-ecm-molecule-lifecycle-prepared-20261031-01")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    verify(PACKAGE)
    inputs = json.loads((PACKAGE / "inputs.json").read_text())
    for item in inputs["explicit_dependencies"]["parents"].values():
        folder = Path(item["path"])
        assert sha(folder / "MANIFEST.json") == item["manifest_sha256"]
        assert sha(folder / "inputs.json") == item["inputs_sha256"]
    if args.freeze:
        if DEST.exists():
            raise ValueError("Never replace a frozen handoff")
        shutil.copytree(PACKAGE, DEST, copy_function=shutil.copyfile)
        manifest = verify(DEST)
        receipt = json.loads((DEST / "SOURCE_STATIC_REVIEW.json").read_text())
        handoff = dict(
            kind="cells.held_molecule_lifecycle_handoff@1",
            status="source_static_complete_held_for_Chief_review",
            package=str(DEST),
            manifest_sha256=sha(DEST / "MANIFEST.json"),
            inputs_sha256=sha(DEST / "inputs.json"),
            source_static_receipt_sha256=sha(DEST / "SOURCE_STATIC_REVIEW.json"),
            artifacts=len(manifest["files"]),
            source_files=receipt["source_files"],
            runtime_modules=receipt["runtime_modules"],
            reference_modules=receipt["reference_modules"],
            resource_files=receipt["resource_files"],
            pending_reads=0,
            AST_proofs=70,
            native_methods_audited=27,
            native_files_installed_exact=332,
            capture_metadata_controls=10,
            prospective=inputs["planned"],
            explicit_dependencies=inputs["explicit_dependencies"],
            failure_capture_dependency=inputs["failure_capture_dependency"],
            historical_parents_unchanged=True,
            notes="source/agent-work/cells-worker-01/workfiles/" + PREFIX + "_implementation.md",
            driver_metadata_only=True,
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_model_reference_evaluations=0,
            pytest_collections=0,
            numerical_runs=0,
            active_job_queries=0,
            inherited_scientific_passes=0,
            automatic_launch=False,
            automatic_polling=False,
            automatic_followup=False,
        )
        write(WORK / (PREFIX + "_handoff_01.json"), handoff)
        print(json.dumps(handoff, sort_keys=True))
    else:
        if (PACKAGE / "preparation-manifest.json").exists():
            raise ValueError("Local packet already sealed")
        metadata = json.loads((METADATA / "result.json").read_text())
        assert metadata["status"] == "passed" and len(metadata["controls"]) == 10
        assert all(c["passed"] for c in metadata["controls"])
        shutil.copyfile(PACKAGE / "MANIFEST.json", PACKAGE / "preparation-manifest.json")
        shutil.copyfile(
            PACKAGE / "SOURCE_STATIC_REVIEW.json", PACKAGE / "preparation-author-receipt.json"
        )
        shutil.copytree(METADATA, PACKAGE / "metadata-01", copy_function=shutil.copyfile)
        for attempt in (1, 2, 3, 4):
            shutil.copytree(
                WORK / (PREFIX + "_regenerated_" + str(attempt).zfill(2)),
                PACKAGE / ("source-regeneration-" + str(attempt).zfill(2)),
                copy_function=shutil.copyfile,
            )
        scripts = PACKAGE / "preparation-scripts"
        scripts.mkdir()
        shutil.copyfile(Path(__file__), scripts / Path(__file__).name)
        shutil.copyfile(
            WORK / (PREFIX + "_package_preparation_02.log"), PACKAGE / "preparation.log"
        )
        receipt = json.loads((PACKAGE / "SOURCE_STATIC_REVIEW.json").read_text())
        receipt.update(
            metadata=dict(
                path="metadata-01/result.json",
                sha256=sha(METADATA / "result.json"),
                controls_passed=10,
                measured_process_VmHWM_bytes=metadata["measured_process_VmHWM_bytes"],
                large_archive_constructed=False,
            ),
            static_checks=dict(
                Ruff_without_cache=True, compile_without_execution=True, AST_proofs=70
            ),
            source_boundary=dict(
                path="source/agent-work/cells-worker-01/workfiles/" + PREFIX + "_boundary_01.json",
                sha256=sha(WORK / (PREFIX + "_boundary_01.json")),
                methods=27,
                native_files_installed_exact=332,
            ),
            capture_profile="ordinary_ecm_molecule_lifecycle_01",
            capture_format_member_limit=310689,
            capture_case_maximum_claim=False,
            capture_all_cases_fit_claim=False,
            previous_static_sources_and_logs_preserved=True,
            all_numerical_cases_and_forms_unrun=True,
            raw_partial_owner_fields_and_original_exception_chains_retained=True,
            event_loop_or_physical_initializer_claim=False,
            shared_frozen_or_PROGRESS_edits=False,
            no_scientific_qualification_or_launch=True,
        )
        (PACKAGE / "SOURCE_STATIC_REVIEW.json").unlink()
        write(PACKAGE / "SOURCE_STATIC_REVIEW.json", receipt)
        (PACKAGE / "MANIFEST.json").unlink()
        write(
            PACKAGE / "MANIFEST.json",
            dict(
                kind="cells.held_molecule_lifecycle_manifest@1",
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
    assert not any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for name in sys.modules
    )


if __name__ == "__main__":
    main()
