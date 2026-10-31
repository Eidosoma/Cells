"""Seal and exclusively freeze the held general-molecule source proposal."""
# ruff: noqa: E501 -- complete source-findings and handoff metadata strings.

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_molecule_dispatch"
PACKAGE = WORK / (PREFIX + "_prepared_01")
METADATA = WORK / (PREFIX + "_metadata_01")
DEST = Path("/mnt/workspaces/Cells/betse-normal-ecm-molecule-dispatch-prepared-20261031-01")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02")


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
        assert not (root / name).is_symlink() and sha(root / name) == pin, name
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    verify(PACKAGE)
    if args.freeze:
        if DEST.exists():
            raise ValueError("Never replace an immutable source proposal")
        shutil.copytree(PACKAGE, DEST, copy_function=shutil.copyfile)
        verify(DEST)
        assert (
            sha(PARENT / "MANIFEST.json")
            == "528a1c7d1df0be152919b9dd446f3247676856585652f2c2924d82840c27d36f"
        )
        handoff = dict(
            kind="cells.held_general_molecule_handoff@1",
            status="source_static_complete_held_for_Chief_review",
            package=str(DEST),
            manifest_sha256=sha(DEST / "MANIFEST.json"),
            inputs_sha256=sha(DEST / "inputs.json"),
            source_static_receipt_sha256=sha(DEST / "SOURCE_STATIC_REVIEW.json"),
            parent_manifest_sha256=sha(PARENT / "MANIFEST.json"),
            native_methods_audited=22,
            native_files_installed_exact=332,
            AST_proofs=26,
            capture_hold_metadata_controls=10,
            source_files=2742,
            runtime_modules=96,
            reference_modules=25,
            resource_files=25,
            pending_reads=0,
            prospective=json.loads((DEST / "inputs.json").read_text())["planned"],
            notes="source/agent-work/cells-worker-01/workfiles/" + PREFIX + "_implementation.md",
            configuration_obstruction="Parameters.load missing-general-section branch leaves molecules_enabled unwritten; no default False inferred. Native file parsing is unrun.",
            shared_and_frozen_sources_edited=False,
            oracle_domains_or_existing_budgets_changed=False,
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_model_reference_evaluations=0,
            pytest_collections=0,
            numerical_runs=0,
            active_job_queries=0,
            inherited_scientific_passes=0,
            driver_metadata_only=True,
            automatic_launch=False,
            automatic_followup=False,
        )
        write(WORK / (PREFIX + "_handoff_01.json"), handoff)
        print(json.dumps(handoff))
    else:
        if (PACKAGE / "preparation-manifest.json").exists():
            raise ValueError("Preparation already sealed")
        result = json.loads((METADATA / "result.json").read_text())
        assert (
            result["status"] == "passed"
            and len(result["controls"]) == 10
            and all(r["passed"] for r in result["controls"])
        )
        shutil.copyfile(PACKAGE / "MANIFEST.json", PACKAGE / "preparation-manifest.json")
        shutil.copytree(METADATA, PACKAGE / "metadata-01", copy_function=shutil.copyfile)
        shutil.copytree(
            WORK / (PREFIX + "_regenerated_01"),
            PACKAGE / "source-regeneration-01",
            copy_function=shutil.copyfile,
        )
        (PACKAGE / "preparation-scripts").mkdir()
        shutil.copyfile(Path(__file__), PACKAGE / "preparation-scripts" / Path(__file__).name)
        receipt = json.loads((PACKAGE / "SOURCE_STATIC_REVIEW.json").read_text())
        receipt.update(
            metadata=dict(
                path="metadata-01/result.json",
                sha256=sha(METADATA / "result.json"),
                controls_passed=10,
                max_rss_bytes=result["max_rss_bytes"],
                no_large_archive_constructed=True,
            ),
            static_checks=dict(
                Ruff_without_cache=True, compile_without_execution=True, AST_proofs=26
            ),
            capture_profile="ordinary_ecm_molecule_dispatch_01",
            capture_format_limit=310689,
            capture_case_maximum_claim=False,
            capture_all_cases_fit_claim=False,
            native_methods_audited=22,
            native_files_installed_exact=332,
            initial_static_corrections_preserved_in_worker_evidence=True,
            inherited_failure="signed_environment 39/40 remains failed; catalog05 82 passed/1 reference refusal/11 unrun. No prior pass transferred.",
            no_transition_dependency_adopted=True,
        )
        (PACKAGE / "SOURCE_STATIC_REVIEW.json").unlink()
        write(PACKAGE / "SOURCE_STATIC_REVIEW.json", receipt)
        (PACKAGE / "MANIFEST.json").unlink()
        write(
            PACKAGE / "MANIFEST.json",
            dict(
                kind="cells.held_general_molecule_dispatch_manifest@1",
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
                    source_static_receipt_sha256=sha(PACKAGE / "SOURCE_STATIC_REVIEW.json"),
                )
            )
        )
    assert not any(
        n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for n in sys.modules
    )


if __name__ == "__main__":
    main()
