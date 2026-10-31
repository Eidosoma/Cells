"""Assemble a held INIT02 evidence successor using stdlib copy/hash/AST only."""

import ast
import copy
import difflib
import hashlib
import json
import shutil
import sys
from pathlib import Path

from betse_normal_ecm_reviewed_successors_resources import audit, manual_review

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-01")
REVIEW = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-preflight-20261031-01/REVIEW.json")
PROPOSAL = WORK / "betse_normal_ecm_init_phase_successor_02_proposal"
OUT = WORK / "betse_normal_ecm_init_phase_evidence_successor_02"
DEST = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02")
PREFIX = "betse_normal_ecm_init_phase"
CHANGED = (
    f"validation/betse/{PREFIX}_native.py",
    f"tests/unit/test_{PREFIX}.py",
)
ADDED = f"validation/betse/{PREFIX}_capture.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def replace_json(path, value):
    path.unlink()
    write(path, value)


def main():
    if OUT.exists() or DEST.exists():
        raise ValueError("Exclusive successor preparation and destination required")
    if (
        sha(PARENT / "MANIFEST.json")
        != ("33e09b2c908ab9d03cabed4d5f485ae29cba702d6f454397fa2b2a0fa3fe99bf")
        or sha(REVIEW) != "ab6b07e33489748bdfa75d01a037aa82b0c22e8e8cfb33c0e0a36acca0137c3d"
    ):
        raise ValueError("Wrong frozen parent or final Chief review")
    parent_manifest = json.loads((PARENT / "MANIFEST.json").read_text())
    actual_parent = {str(p.relative_to(PARENT)) for p in PARENT.rglob("*") if p.is_file()}
    assert actual_parent == set(parent_manifest["files"]) | {"MANIFEST.json"}
    for name, pin in parent_manifest["files"].items():
        assert not (PARENT / name).is_symlink() and sha(PARENT / name) == pin, name
    shutil.copytree(PARENT, OUT, copy_function=shutil.copyfile)
    source = OUT / "source"
    lineage = OUT / "lineage/INIT01"
    lineage.mkdir(parents=True)
    for name in (
        "MANIFEST.json",
        "inputs.json",
        "SOURCE_STATIC_REVIEW.json",
        "resource-audit.json",
        "preparation-manifest.json",
        "tools/inputs.json",
        "tools/accounting.json",
    ):
        target = lineage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, target)
    shutil.copyfile(REVIEW, lineage / "independent-REVIEW.json")
    changes = {}
    patch = []
    for name in (*CHANGED, ADDED):
        path = source / name
        candidate = PROPOSAL / "source" / name
        assert candidate.is_file() and not candidate.is_symlink()
        old = path.read_text() if path.exists() else ""
        new = candidate.read_text()
        patch.extend(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile="INIT01/" + name,
                tofile="INIT02/" + name,
            )
        )
        changes[name] = dict(
            before_sha256=sha(path) if path.exists() else None,
            after_sha256=sha(candidate),
        )
        shutil.copyfile(candidate, path)
    evidence = OUT / "INIT02-evidence"
    evidence.mkdir()
    (evidence / "source.delta.patch").write_text("".join(patch))
    for path in (
        PROPOSAL / "proposal.json",
        WORK / "prepare_betse_normal_ecm_init_phase_successor_02.py",
        WORK / "betse_normal_ecm_init_phase_successor_02_check.py",
        WORK / "prepare_betse_normal_ecm_init_phase_evidence_successor_02.py",
        WORK / "betse_normal_ecm_init_phase_successor_02_software_01.json",
        WORK / "betse_normal_ecm_init_phase_successor_02_software_02.json",
        WORK / "betse_normal_ecm_init_phase_successor_02_software_03.json",
    ):
        shutil.copyfile(path, evidence / path.name)
    software = json.loads((WORK / f"{PREFIX}_successor_02_software_03.json").read_text())
    assert software["status"] == "passed" and len(software["controls"]) == 18
    assert software["proposed_native_sha256"] == sha(source / CHANGED[0])
    assert software["proposed_test_sha256"] == sha(source / CHANGED[1])
    assert software["software_helper_sha256"] == sha(source / ADDED)
    old_inputs = json.loads((PARENT / "inputs.json").read_text())
    source_hashes = {
        str(p.relative_to(source)): sha(p) for p in sorted(source.rglob("*")) if p.is_file()
    }
    assert set(source_hashes) == set(old_inputs["source_sha256"]) | {ADDED}
    assert {
        name for name, pin in old_inputs["source_sha256"].items() if source_hashes[name] != pin
    } == set(CHANGED)
    # Recompute closure from source without importing any scientific module.
    resources = audit(source, PREFIX)
    reviewed = manual_review(resources)
    for rows in (reviewed["reviewed_unresolved_reads"], reviewed["pending_manual_reads"]):
        for row in rows:
            if (
                row.get("classification") == "manual_resolution_pending"
                and row.get("module") == CHANGED[1]
                and row.get("containing_function") == "references"
                and row.get("expression") == "output.read_text()"
            ):
                row.update(
                    classification="future_fresh_reference_output",
                    rationale="Checked fresh subprocess output, not packaged input data",
                )
    reviewed["pending_manual_reads"] = [
        row
        for row in reviewed["pending_manual_reads"]
        if row.get("classification") == "manual_resolution_pending"
    ]
    if reviewed["pending_manual_reads"] or resources["literal_resource_audit"]["missing_resources"]:
        write(OUT / "INIT02-resource-unresolved.json", dict(inventory=resources, review=reviewed))
        raise ValueError("Unclassified source reads; preserve preparation for review")
    replace_json(
        OUT / "resource-audit.json",
        dict(
            inventory=resources,
            review=reviewed,
            scientific_imports=0,
            scientific_AST_executions=0,
        ),
    )
    accounting = json.loads((OUT / "tools/accounting.json").read_text())
    external = {
        name: pin for name, pin in accounting["source_sha256"].items() if Path(name).is_absolute()
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
    accounting["INIT_archive_call_sites"] = sites
    accounting["status"] = "INIT02_evidence_successor_profile_held_for_Chief_review"
    replace_json(OUT / "tools/accounting.json", accounting)
    contract = json.loads((OUT / "tools/inputs.json").read_text())
    contract["profiles"]["ordinary_ecm_init_phase_01"] = dict(
        writer_source_sha256={str(DEST / name): pin for name, pin in writers.items()},
        archive_call_sites=sites,
    )
    replace_json(OUT / "tools/inputs.json", contract)
    for name, pin in contract["tool_sha256"].items():
        assert sha(OUT / "tools" / name) == pin
    for path in source.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")
    inputs = copy.deepcopy(old_inputs)
    inputs.update(
        status="INIT02_reviewed_evidence_repair_source_static_unrun",
        evidence_successor_of=dict(path=str(PARENT), manifest_sha256=sha(PARENT / "MANIFEST.json")),
        independent_parent_review_sha256=sha(REVIEW),
        repaired_evidence_findings=["INIT-CAPTURE-01", "INIT-SAMPLING-02"],
        source_sha256=source_hashes,
        own_files=old_inputs["own_files"] + [ADDED],
        tool_sha256={str(p.relative_to(OUT)): sha(p) for p in sorted((OUT / "tools").iterdir())},
        resource_audit_sha256=sha(OUT / "resource-audit.json"),
    )
    for key in (
        "groups",
        "planned",
        "resources",
        "native_snapshot_sha256",
        "live_native_source_sha256",
        "driver_sha256",
    ):
        assert inputs[key] == old_inputs[key], key
    assert (OUT / ".execution_hold").read_bytes() == (PARENT / ".execution_hold").read_bytes()
    assert sha(OUT / "driver.py") == old_inputs["driver_sha256"]
    replace_json(OUT / "inputs.json", inputs)
    receipt = dict(
        kind="cells.INIT02_evidence_repair_held_source_receipt@1",
        status="held_source_static_complete_numerical_suite_unrun",
        parent_manifest_sha256=sha(PARENT / "MANIFEST.json"),
        final_parent_independent_review_sha256=sha(REVIEW),
        inputs_sha256=sha(OUT / "inputs.json"),
        changed_source=changes,
        full_native_evaluator_evidence_inverse_matches_parent=True,
        full_positive_test_sampling_inverse_matches_parent=True,
        fixtures_protocol_reference_equations_roster_budgets_unchanged=True,
        repaired_findings=["INIT-CAPTURE-01", "INIT-SAMPLING-02"],
        evidence_controls=dict(
            path="INIT02-evidence/" + f"{PREFIX}_successor_02_software_03.json",
            sha256=sha(WORK / f"{PREFIX}_successor_02_software_03.json"),
            controls_passed=18,
        ),
        inherited_static_evidence=dict(
            path="lineage/INIT01/SOURCE_STATIC_REVIEW.json",
            note="Historical INIT01 receipt; superseded native/test pins are not current proofs",
        ),
        prospective=inputs["planned"],
        runtime_import_closure_files=len(resources["scientific_import_closure"]),
        reference_import_closure_files=len(resources["reference_closure"]),
        resource_files=len(reviewed["resource_sha256"]),
        classified_source_reads=len(reviewed["reviewed_unresolved_reads"]),
        unclassified_source_reads=0,
        driver_unchanged_and_held=True,
        future_runner_observations_unresolved=json.loads(REVIEW.read_text())[
            "future_runner_observations_not_runner_preparation"
        ],
        oracle_domain_caveat=(
            "INIT-ORACLE-DOMAIN-03 remains: active KLeak/CaLeak standalone references "
            "guard [-0.120,+0.060] V before constant branches. Inactive Nav does not "
            "qualify active Nav. No oracle, fixture or tolerance change."
        ),
        catalog05_failure_preserved=(
            "82 passed/1 failed/11 unrun. no_CaATP second-call Nav1p2 "
            "+0.162 to +0.380 V exceeded inherited reference domain; native completed "
            "three calls. Reference refusal, not tolerance failure. No pass inherited."
        ),
        static_checks=dict(Ruff_no_cache=True, compile_without_execution=True),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        active_job_queries=0,
        inherited_qualification=0,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    replace_json(OUT / "SOURCE_STATIC_REVIEW.json", receipt)
    replace_json(
        OUT / "MANIFEST.json",
        dict(
            kind="cells.held_INIT02_evidence_preparation_manifest@1",
            status="held_unrun",
            files={
                str(p.relative_to(OUT)): sha(p)
                for p in sorted(OUT.rglob("*"))
                if p.is_file() and p != OUT / "MANIFEST.json"
            },
            scientific_evaluations=0,
        ),
    )
    assert not any(
        name.split(".")[0] in {"cells", "betse", "numpy", "scipy", "jax", "jaxlib", "pytest"}
        for name in sys.modules
    )
    print(
        json.dumps(
            dict(
                status="held_prepared",
                inputs_sha256=sha(OUT / "inputs.json"),
                manifest_sha256=sha(OUT / "MANIFEST.json"),
                runtime_modules=len(resources["scientific_import_closure"]),
                reference_modules=len(resources["reference_closure"]),
                resources=len(reviewed["resource_sha256"]),
            )
        )
    )


if __name__ == "__main__":
    main()
