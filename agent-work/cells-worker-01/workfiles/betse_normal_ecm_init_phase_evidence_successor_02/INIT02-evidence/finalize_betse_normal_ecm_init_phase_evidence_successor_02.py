"""Seal or exclusively copy the held INIT02 snapshot; stdlib metadata only."""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PACKAGE = WORK / "betse_normal_ecm_init_phase_evidence_successor_02"
METADATA = WORK / "betse_normal_ecm_init_phase_successor_02_metadata"
DEST = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02")
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-01")


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
    if args.freeze:
        verify(PACKAGE)
        if DEST.exists():
            raise ValueError("Never replace a prepared snapshot")
        shutil.copytree(PACKAGE, DEST, copy_function=shutil.copyfile)
        verify(DEST)
        assert sha(PACKAGE / "MANIFEST.json") == sha(DEST / "MANIFEST.json")
        assert sha(PARENT / "MANIFEST.json") == (
            "33e09b2c908ab9d03cabed4d5f485ae29cba702d6f454397fa2b2a0fa3fe99bf"
        )
        handoff = dict(
            kind="cells.INIT02_held_source_handoff@1",
            status="held_for_Chief_review_no_science_run",
            package=str(DEST),
            manifest_sha256=sha(DEST / "MANIFEST.json"),
            inputs_sha256=sha(DEST / "inputs.json"),
            source_static_review_sha256=sha(DEST / "SOURCE_STATIC_REVIEW.json"),
            parent_manifest_sha256=sha(PARENT / "MANIFEST.json"),
            repaired_findings=["INIT-CAPTURE-01", "INIT-SAMPLING-02"],
            evidence_metadata_controls=18,
            capture_metadata_controls=10,
            runtime_modules=124,
            reference_modules=23,
            resource_files=28,
            fixture_protocol_equations_ids_budgets_unchanged=True,
            prospective=json.loads((DEST / "inputs.json").read_text())["planned"],
            historical_and_failed_evidence_preserved=True,
            oracle_domain_changes=False,
            driver_changes=False,
            scientific_imports=0,
            scientific_AST_executions=0,
            fixture_model_reference_evaluations=0,
            pytest_collections=0,
            numerical_runs=0,
            active_job_queries=0,
            inherited_scientific_passes=0,
        )
        write(WORK / "betse_normal_ecm_init_phase_handoff_02.json", handoff)
        print(json.dumps(handoff))
    else:
        verify(PACKAGE)
        if (PACKAGE / "INIT02-preparation-manifest.json").exists():
            raise ValueError("Already finalized; do not mutate sealed preparation")
        result = json.loads((METADATA / "result.json").read_text())
        assert result["status"] == "passed"
        assert len(result["controls"]) == 10 and all(r["passed"] for r in result["controls"])
        shutil.copyfile(PACKAGE / "MANIFEST.json", PACKAGE / "INIT02-preparation-manifest.json")
        shutil.copytree(METADATA, PACKAGE / "INIT02-metadata", copy_function=shutil.copyfile)
        shutil.copyfile(Path(__file__), PACKAGE / "INIT02-evidence" / Path(__file__).name)
        receipt = json.loads((PACKAGE / "SOURCE_STATIC_REVIEW.json").read_text())
        receipt["capture_and_hold_metadata_controls"] = dict(
            path="INIT02-metadata/result.json",
            sha256=sha(METADATA / "result.json"),
            controls_passed=10,
            max_rss_bytes=result["max_rss_bytes"],
            changed_profile_pins_checked=True,
            large_archive_generated=False,
        )
        (PACKAGE / "SOURCE_STATIC_REVIEW.json").unlink()
        write(PACKAGE / "SOURCE_STATIC_REVIEW.json", receipt)
        (PACKAGE / "MANIFEST.json").unlink()
        write(
            PACKAGE / "MANIFEST.json",
            dict(
                kind="cells.held_INIT02_evidence_successor_manifest@1",
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
                    source_static_review_sha256=sha(PACKAGE / "SOURCE_STATIC_REVIEW.json"),
                )
            )
        )
    assert not any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for name in sys.modules
    )


if __name__ == "__main__":
    main()
