"""Seal or copy the held runner after synthetic metadata controls only."""

import argparse
import json
import os
import resource
import shutil
import sys
from pathlib import Path

from betse_normal_ecm_molecule_qualification_contract import (
    PREFIX,
    read,
    require,
    sha,
    verify_bundle,
    write,
)
from betse_normal_ecm_molecule_qualification_resources import memory_available

WORK = Path(__file__).parent
PACKAGE = WORK / (PREFIX + "_prepared_03")
METADATA = WORK / (PREFIX + "_metadata_02")
DEST = Path("/mnt/workspaces/Cells/ecm-molecule-qualification-runners-20261031-01")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    os.sched_setaffinity(0, {0})
    resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 512 * 2**20))
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    require(memory_available() >= 8 * 2**30, "Metadata host reserve required")
    inputs = verify_bundle(PACKAGE)
    if args.freeze:
        require(not DEST.exists(), "Preserve old handoffs; exclusive destination required")
        shutil.copytree(PACKAGE, DEST, copy_function=shutil.copyfile)
        verify_bundle(DEST)
        receipt = read(DEST / "SOURCE_STATIC_REVIEW.json")
        handoff = dict(
            kind="cells.held_molecule_capture02_runner_handoff@1",
            status="sealed_held_executable_runners_no_release",
            package=str(DEST),
            manifest_sha256=sha(DEST / "MANIFEST.json"),
            inputs_sha256=sha(DEST / "inputs.json"),
            receipt_sha256=sha(DEST / "SOURCE_STATIC_REVIEW.json"),
            controls=len(receipt["controls"]),
            source_proofs=len(receipt["source_proofs"]),
            planned=inputs["planned"],
            libraries=len(inputs["library_pins"]),
            source_packets_unchanged=True,
            exact_profile02_pins_required=True,
            execution_hold=True,
            release_authorized=False,
            scientific_imports=[],
            scientific_AST_executions=0,
            fixture_reference_model_evaluations=0,
            pytest_collections=0,
            scientific_launches=0,
            active_job_queries=0,
            automatic_followup=False,
        )
        write(WORK / (PREFIX + "_handoff_01.json"), handoff)
        print(json.dumps(handoff, sort_keys=True))
    else:
        require(not (PACKAGE / "preparation-manifest.json").exists(), "Already sealed")
        result = read(METADATA / "result.json")
        require(
            result["status"] == "passed" and all(r["passed"] for r in result["controls"]),
            "All synthetic controls required",
        )
        shutil.copyfile(PACKAGE / "MANIFEST.json", PACKAGE / "preparation-manifest.json")
        shutil.copytree(METADATA, PACKAGE / "metadata-01", copy_function=shutil.copyfile)
        for name in (
            PREFIX + "_prepare_01.log",
            PREFIX + "_prepare_02.log",
            PREFIX + "_prepare_03.log",
            PREFIX + "_metadata_01.log",
            PREFIX + "_metadata_02.log",
            PREFIX + "_ruff_01.log",
            PREFIX + "_ruff_02.log",
            PREFIX + "_ruff_03.log",
            PREFIX + "_ruff_04.log",
        ):
            shutil.copyfile(WORK / name, PACKAGE / name)
        write(
            PACKAGE / "SOURCE_STATIC_REVIEW.json",
            dict(
                kind="cells.held_molecule_capture02_runner_author_receipt@1",
                status="source_and_synthetic_metadata_complete_held",
                inputs_sha256=sha(PACKAGE / "inputs.json"),
                metadata_sha256=sha(METADATA / "result.json"),
                controls=result["controls"],
                source_proofs=result["source_proofs"],
                metadata_resources={
                    key: result[key]
                    for key in (
                        "cpu_affinity",
                        "measured_process_VmHWM_bytes",
                        "address_space_cap_bytes",
                        "host_reserve_bytes",
                        "elapsed_seconds",
                    )
                },
                original_budgets_caps_and02_profiles_preserved=True,
                complete_outcomes_and_actual_children_required=True,
                separate_exact_rosters=True,
                scientific_imports=[],
                scientific_AST_executions=0,
                fixture_reference_model_evaluations=0,
                pytest_collections=0,
                scientific_launches=0,
                active_job_queries=0,
                release_authorized=False,
            ),
        )
        (PACKAGE / "MANIFEST.json").unlink()
        write(
            PACKAGE / "MANIFEST.json",
            dict(
                status="sealed_held_unrun",
                files={
                    str(p.relative_to(PACKAGE)): sha(p)
                    for p in sorted(PACKAGE.rglob("*"))
                    if p.is_file() and p != PACKAGE / "MANIFEST.json"
                },
            ),
        )
        verify_bundle(PACKAGE)
        print(
            json.dumps(
                dict(
                    status="sealed_held",
                    manifest_sha256=sha(PACKAGE / "MANIFEST.json"),
                    inputs_sha256=sha(PACKAGE / "inputs.json"),
                    receipt_sha256=sha(PACKAGE / "SOURCE_STATIC_REVIEW.json"),
                    controls=len(result["controls"]),
                    source_proofs=len(result["source_proofs"]),
                )
            )
        )
    require(
        not any(
            n.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
            for n in sys.modules
        ),
        "Scientific import during metadata seal",
    )


if __name__ == "__main__":
    main()
