"""Seal/freeze the held transition snapshot using bounded stdlib file operations."""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_init_sim_transition"
PACKAGE = WORK / (PREFIX + "_prepared_01")
METADATA = WORK / (PREFIX + "_metadata_01")
DEST = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-sim-transition-prepared-20261031-01")
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
            raise ValueError("Never replace a frozen handoff")
        shutil.copytree(PACKAGE, DEST, copy_function=shutil.copyfile)
        verify(DEST)
        assert (
            sha(PARENT / "MANIFEST.json")
            == "528a1c7d1df0be152919b9dd446f3247676856585652f2c2924d82840c27d36f"
        )
        handoff = dict(
            kind="cells.held_INIT_SIM_transition_handoff@1",
            status="source_static_complete_held_for_Chief_review",
            package=str(DEST),
            manifest_sha256=sha(DEST / "MANIFEST.json"),
            inputs_sha256=sha(DEST / "inputs.json"),
            source_static_receipt_sha256=sha(DEST / "SOURCE_STATIC_REVIEW.json"),
            parent_manifest_sha256=sha(PARENT / "MANIFEST.json"),
            AST_proofs=29,
            capture_hold_metadata_controls=10,
            source_files=2745,
            runtime_modules=133,
            reference_modules=24,
            resource_files=28,
            pending_reads=0,
            prospective=json.loads((DEST / "inputs.json").read_text())["planned"],
            notes="source/agent-work/cells-worker-01/workfiles/" + PREFIX + "_implementation.md",
            shared_and_frozen_sources_edited=False,
            source_scientific_domains_or_budgets_changed=False,
            scientific_imports=0,
            scientific_AST_executions=0,
            pytest_collections=0,
            fixture_reference_model_evaluations=0,
            numerical_runs=0,
            active_job_queries=0,
            inherited_scientific_passes=0,
            automatic_launch=False,
            automatic_followup=False,
            driver_metadata_only=True,
        )
        write(WORK / (PREFIX + "_handoff_01.json"), handoff)
        print(json.dumps(handoff))
    else:
        if (PACKAGE / "preparation-manifest.json").exists():
            raise ValueError("Already sealed; leave preparation untouched")
        value = json.loads((METADATA / "result.json").read_text())
        assert value["status"] == "passed" and len(value["controls"]) == 10
        assert all(r["passed"] for r in value["controls"])
        shutil.copyfile(PACKAGE / "MANIFEST.json", PACKAGE / "preparation-manifest.json")
        shutil.copytree(METADATA, PACKAGE / "metadata-01", copy_function=shutil.copyfile)
        for number in ("01", "02"):
            shutil.copytree(
                WORK / (PREFIX + "_regenerated_" + number),
                PACKAGE / ("static-failure-regeneration-" + number),
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
                max_rss_bytes=value["max_rss_bytes"],
                no_large_archive_constructed=True,
            ),
            static_checks=dict(
                Ruff_without_cache=True,
                compile_without_execution=True,
                source_regeneration_and_inverse_AST_proofs=29,
            ),
            failed_static_attempts_preserved=True,
            capture_profile="ordinary_ecm_init_sim_transition_01",
            capture_format_limit=310689,
            capture_case_maximum_claim=False,
            capture_all_cases_fit_claim=False,
        )
        (PACKAGE / "SOURCE_STATIC_REVIEW.json").unlink()
        write(PACKAGE / "SOURCE_STATIC_REVIEW.json", receipt)
        (PACKAGE / "MANIFEST.json").unlink()
        write(
            PACKAGE / "MANIFEST.json",
            dict(
                kind="cells.held_INIT_SIM_transition_manifest@1",
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
