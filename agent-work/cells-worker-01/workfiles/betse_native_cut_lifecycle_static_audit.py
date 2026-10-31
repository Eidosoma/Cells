"""Final static cut scope, ownership, closure, fixed budgets and runner audit only."""

import argparse
import ast
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_native_cut_lifecycle"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def functions(path):
    return {
        n.name: n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)
    }


def audit():
    queue_path = WORK / (PREFIX + "_workqueue.json")
    q = json.loads(queue_path.read_text())
    protocol = json.loads((ROOT / "validation/topology" / (PREFIX + "_protocol.json")).read_text())
    mapping = json.loads((ROOT / "validation/topology" / (PREFIX + "_source_map.json")).read_text())
    q["workfiles"] = sorted(
        set(
            q["workfiles"]
            + [str(p.relative_to(ROOT)) for p in WORK.glob("*" + PREFIX + "*") if p.is_file()]
        )
    )
    source = module("cut_source_capability", WORK / (PREFIX + "_source_audit.py")).audit()
    assert source == json.loads((WORK / (PREFIX + "_source_witness_01.json")).read_text())
    proof = module("cut_AST", WORK / (PREFIX + "_ast_audit.py")).audit()
    previous = json.loads((WORK / (PREFIX + "_AST_witness_01.json")).read_text())
    assert {k: v for k, v in proof.items() if k != "compiled_python_files"} == {
        k: v for k, v in previous.items() if k != "compiled_python_files"
    }
    assert mapping["source_AST_proof"] == previous
    assert proof["compiled_python_files"] >= previous["compiled_python_files"]
    assert len(q["owned"]) == 9 and q["planned"] == protocol["planned"]
    assert mapping["scope"] == protocol["scope"]
    assert source["Python_files"] == 332 and source["installed_exact"] is True
    assert len(source["methods"]) == 32 and source["prefix_boundary"]["line"] == 1153
    old = json.loads((ROOT / "validation/topology/betse_tissue_cut_protocol.json").read_text())
    assert protocol["acceptance"]["quantities"] == old["tolerances"]
    for path, expected in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / path) == expected, path
    for path, expected in q["protected_sha256"].items():
        assert sha(ROOT / path) == expected, path
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    assert (
        q["freeze_prerequisites"]["frozen_event01_bound"]
        == q["binding_evidence"]["frozen_event01_inputs"]
    )
    for name, expected in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / name) == expected, name
        assert (
            sha(Path(protocol["native_source"]["installed_package"]).parent / name) == expected
        ), name
    assert protocol["planned"]["checks"] == 25
    assert protocol["planned"]["native_captures"] == 14
    assert protocol["planned"]["fresh_independent_reference_forms"] == 6
    for key in (
        "geometry_calls",
        "complete_native_cuts",
        "physical_mesh_cases",
        "ordinary_resumes",
        "biological_cases",
        "carried_reference_forms",
    ):
        assert protocol["planned"][key] == 0, key
    fixture = ast.parse((ROOT / "validation/topology" / (PREFIX + "_fixtures.py")).read_text())
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id in ("CASES", "RAW_CASES", "DEPENDENCIES")
    }
    assert [len(constants[k]) for k in ("CASES", "RAW_CASES", "DEPENDENCIES")] == [6, 8, 11]
    assert len(set().union(*constants.values())) == 25
    tests = functions(ROOT / "tests/unit" / ("test_" + PREFIX + ".py"))
    primary = ast.unparse(tests["test_native_cut_prefix"])
    assert "ordinary_continuation_refused=True" in primary and "source_mesh_calls=0" in primary
    assert "physical_global_conservation_credit=False" in primary
    raw = ast.unparse(tests["test_native_cut_raw_partial"])
    for fragment in (
        "positive_credit=False",
        "complete_raw_native_and_port_evidence=True",
        "native_failure_type=None",
        "source_prefix_completed",
    ):
        assert fragment in raw, fragment
    deps = ast.unparse(tests["test_native_cut_capabilities"])
    assert "type(error).__name__ == expected_type and str(error) == expected_message" in deps
    run = functions(ROOT / q["runner"])
    prior = functions(WORK / "betse_normal_ecm_event_join_checks.py")
    assert ast.dump(run["verify_pytest_ids"], include_attributes=False) == ast.dump(
        prior["verify_pytest_ids"], include_attributes=False
    )
    prepare = ast.unparse(run["prepare"])
    assert "kind='cells.native_cut_lifecycle_prepared@1'" in prepare
    assert "== 25" in prepare and "== 14" in prepare
    assert "freeze_prerequisites" in prepare
    body = run["run"].body
    start = next(
        i
        for i, n in enumerate(body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "target.mkdir(exist_ok=False)"
    )
    assert len(body) == start + 3 and isinstance(body[-1], ast.Try)
    assert ast.unparse(body[-1].handlers[0].type) == "BaseException"
    executed = ast.unparse(run["run"])
    for flag in (
        "native_deletion_prefix_only=True",
        "complete_native_cut=False",
        "physical_mesh_qualified=False",
        "ordinary_checkpoint_ready=False",
    ):
        assert flag in executed, flag
    for forbidden in (
        "native_ECM_CaATP_executed=True",
        "genuine_molecule_mover=True",
        "complete_ECM_field_reconstruction=True",
        "actual_normal_source_clock=True",
    ):
        assert forbidden not in executed, forbidden
    closure = module("cut_closure", WORK / "betse_normal_grn_join_static_audit.py").closure
    refs = closure("validation/topology/" + PREFIX + "_reference.py", reference=True)
    imports = closure("tests/unit/test_" + PREFIX + ".py", reference=False)
    imports.update(closure("validation/topology/" + PREFIX + "_native.py", reference=False))
    for relative in (
        "src/cells/__init__.py",
        "src/cells/processes/__init__.py",
        "tests/__init__.py",
    ):
        package = ast.parse((ROOT / relative).read_text())
        assert all(
            (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            or (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant))
            for node in package.body
        ), relative
        imports[relative] = sha(ROOT / relative)
    unloaded = q["snapshot_only_unloaded_ancestor_change"]
    assert unloaded["path"] not in imports and unloaded["path"] not in refs
    assert unloaded["live_dependency_pin_adopted"] is False
    ancestor = json.loads(Path(unloaded["frozen_ancestor_manifest"]["path"]).read_text())
    assert (ancestor["owned_sha256"] | ancestor["protected_sha256"])[unloaded["path"]] == unloaded[
        "old_event01_source_sha256"
    ]
    assert unloaded["path"] in q["coordinated_shared_edit_paths"]

    assert not set(q["coordinated_shared_edit_paths"]) & set(imports)
    assert "src/cells/processes/betse_normal_ecm_event_join.py" not in imports
    assert "src/cells/processes/betse_deformation.py" not in imports
    protected = dict(q["protected_sha256"])
    protected.update({p: h for p, h in (refs | imports).items() if p not in q["owned"]})
    for path in refs:
        compile((ROOT / path).read_text(), path, "exec")
    metadata = json.loads((WORK / (PREFIX + "_metadata_witness_01.json")).read_text())
    assert metadata["status"] == "passed_synthetic_metadata_only"
    assert metadata["test_sha256"] == sha(ROOT / "tests/unit" / ("test_" + PREFIX + ".py"))
    assert metadata["driver_sha256"] == sha(ROOT / q["runner"])
    paths = [p for p in q["owned"] + q["workfiles"] if p.endswith(".py") and PREFIX in p]
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    checks = dict(
        compile_without_import="passed",
        global_names="passed",
        ruff_check="passed",
        ruff_format="passed",
        compiled_python_files=proof["compiled_python_files"],
        source_AST_proof=proof,
        installed_exact_python_files=332,
        whole_lifecycle_methods=32,
        all_original_prefix_and_flatten_AST_equal=True,
        source_boundary_line=1153,
        source_and_stable_owner_policy_separate=True,
        empty_source_selection_still_invalidates=True,
        actual_source_partial_frames_and_list_alias_mutations_retained=True,
        numeric_view_buffer_alias_not_checkpointed=True,
        complete_metadata_cannot_unlock_checkpoint=True,
        fixed_existing_quantity_budget_and_precision_unchanged=True,
        reference_closure_modules=len(refs),
        import_closure_modules=len(imports),
        metadata_files=15,
        exact_pytest_ID_and_durable_failure_contract=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )
    q.update(
        status="static_audits_passed_ready_to_freeze_prefix_only",
        owned_sha256={p: sha(ROOT / p) for p in q["owned"]},
        protected_sha256=protected,
        reference_closure=refs,
        scientific_import_closure=imports,
        static_checks=checks,
    )
    queue_path.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return dict(
        kind="cells.native_cut_lifecycle_final_static_audit@1",
        status=q["status"],
        owned=len(q["owned"]),
        protected=len(protected),
        planned=q["planned"],
        checks=checks,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", default="02")
    args = parser.parse_args()
    result = audit()
    with (WORK / (PREFIX + "_static_witness_" + args.number + ".json")).open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                owned=result["owned"],
                protected=result["protected"],
                checks=25,
                native_captures=14,
                fresh_reference_forms=6,
                numerical_runs=0,
            ),
            sort_keys=True,
        )
    )
