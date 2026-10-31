"""Static source/ownership/dependency audit for the separate ECM GRN package."""

import ast
import builtins
import hashlib
import importlib.util
import json
import subprocess
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def audit():
    queue_path = WORK / "betse_ecm_grn_workqueue.json"
    q = json.loads(queue_path.read_text())
    paths = [p for p in q["owned"] + q["workfiles"] if p.endswith(".py")]
    unresolved = {}
    for path in paths:
        text = (ROOT / path).read_text()
        compile(text, path, "exec")
        table = symtable.symtable(text, path, "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__name__", "__file__"}

        def missing(scope, known=known):
            result = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                result |= missing(child)
            return result

        if found := missing(table):
            unresolved[path] = sorted(found)
    assert not unresolved, unresolved
    proof = module("ecm_grn_AST", WORK / "betse_ecm_grn_ast_audit.py").audit()
    mapping = json.loads((ROOT / "validation/betse/betse_ecm_grn_source_map.json").read_text())
    assert proof == {key: mapping[key] for key in proof}
    assert proof["literal_scientific_body_count"] == 47
    assert proof["retained_material_accuracy_accepted"] is False
    key_module = module("accepted_native_key_schema", WORK / "betse_normal_grn_key_schema_audit.py")
    schema = key_module.audit()["native_field_lookup_schema"]
    source_tree = ast.parse((ROOT / "src/cells/processes/betse_ecm_grn_source.py").read_text())
    validate = next(
        n
        for n in source_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "validate_definition"
    )
    allowed = next(
        ast.literal_eval(n.value)
        for n in ast.walk(validate)
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Set)
        and any(isinstance(k, ast.Constant) and k.value == "production rate" for k in n.value.elts)
    )
    expected = {row["key"] for field, row in schema.items() if not field.endswith("_zone")} | {
        "production rate",
        "decay rate",
        "decay max",
        "scale factor",
        "apply to",
    }
    assert allowed == expected
    lookups = [
        n.slice
        for n in ast.walk(validate)
        if isinstance(n, ast.Subscript)
        and isinstance(n.value, ast.Name)
        and n.value.id == "gad"
        and any(isinstance(k, ast.Name) and k.id == "prefix" for k in ast.walk(n.slice))
    ]
    assert len(lookups) == 2
    for prefix in ("", "decay "):
        for sign in ("activators", "inhibitors"):
            actual = {key_module.string(node, dict(prefix=prefix, sign=sign)) for node in lookups}
            assert actual == {"Km " + prefix + sign, "n " + prefix + sign}
    for path, digest in q["protected_sha256"].items():
        assert sha(ROOT / path) == digest, path
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    protocol = json.loads((ROOT / "validation/betse/betse_ecm_grn_protocol.json").read_text())
    assert (
        protocol["planned"]["checks"] == 25
        and protocol["planned"]["fresh_Decimal_reference_forms"] == 104
    )
    assert len(protocol["native_source"]["source_sha256"]) == 22
    for path, digest in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / path) == digest
        assert sha(Path(protocol["native_source"]["installed_package"]).parent / path) == digest
    for path, digest in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / path) == digest, path
    fixture = ast.parse((ROOT / "validation/betse/betse_ecm_grn_fixtures.py").read_text())
    counts = {
        t.id: len(ast.literal_eval(n.value))
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
        and t.id in {"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES"}
    }
    assert [counts[k] for k in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")] == [
        13,
        4,
        4,
        8,
    ]
    tests = {
        n.name: n
        for n in ast.parse((ROOT / "tests/unit/test_betse_ecm_grn_join.py").read_text()).body
        if isinstance(n, ast.FunctionDef)
    }
    assert {
        "test_ecm_grn_history",
        "test_ecm_grn_partial_failure",
        "test_ecm_grn_dependencies",
    } <= tests.keys()
    for name in (
        "test_ecm_grn_history",
        "test_ecm_grn_partial_failure",
        "test_ecm_grn_dependencies",
    ):
        code = ast.unparse(tests[name])
        assert "except Exception as error" in code and "traceback.format_exc()" in code, name
    assert "baseline_admitted=True" in ast.unparse(tests["test_ecm_grn_dependencies"])
    runner = ast.parse((ROOT / q["runner"]).read_text())
    fn = {n.name: n for n in runner.body if isinstance(n, ast.FunctionDef)}
    old = {
        n.name: n
        for n in ast.parse((WORK / "betse_normal_network_join_checks_02.py").read_text()).body
        if isinstance(n, ast.FunctionDef)
    }
    assert ast.dump(fn["verify_pytest_ids"], include_attributes=False) == ast.dump(
        old["verify_pytest_ids"], include_attributes=False
    )
    run = fn["run"]
    start = next(
        i
        for i, n in enumerate(run.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "target.mkdir(exist_ok=False)"
    )
    assert (
        len(run.body) == start + 3
        and isinstance(run.body[-1], ast.Try)
        and ast.unparse(run.body[-1].handlers[0].type) == "BaseException"
    )
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    closure = module(
        "accepted_static_closure", WORK / "betse_normal_grn_join_static_audit.py"
    ).closure
    refs = closure("validation/betse/betse_ecm_grn_reference.py", reference=True)
    imports = closure("tests/unit/test_betse_ecm_grn_join.py", reference=False)
    assert not set(q["protected_but_not_imported_side_package_paths"]) & imports.keys()
    # Every imported local dependency joins the controlled static snapshot.
    added = {
        p: d for p, d in imports.items() if p not in q["owned"] and p not in q["protected_sha256"]
    }
    q["protected_sha256"].update(added)
    assert "src/cells/models/open_calcium_runtime.py" not in imports
    q.update(
        status="static_audits_passed_ready_to_freeze_no_ecm_grn_numerics",
        owned_sha256={p: sha(ROOT / p) for p in q["owned"]},
        reference_closure=refs,
        scientific_import_closure=imports,
        new_dependency_sha256=q.get("new_dependency_sha256", {}) | added,
        static_checks=dict(
            compile_without_import="passed",
            global_name_resolution="passed",
            ruff_check="passed",
            ruff_format="passed",
            literal_original_scientific_bodies=47,
            actual_normal_GRN_guards=True,
            original_ECM_FD_NernstPlanck=True,
            original_radius_weight_TJ_context=True,
            retained_material_inverse_AST_equal=True,
            native_network_before_deferred_commit=True,
            complete_common_cache_bridge_AST=True,
            all16_native_regulator_keys=True,
            current_packet_boundary_authoritative=True,
            disabled_ion_aliases_skipped=True,
            reference_closure_stdlib=True,
            reference_fixed_gradient_flux_current_budgets=True,
            source_effective_true_volume_and_conservative_scatter_books_separate=True,
            retained_ECM_panel_accepted=False,
            retained_ECM_panel_checks=[39, 40],
            exact_pytest_ID_validator_unchanged=True,
            post_output_terminal_failure_capture="passed",
            pending_charged_transporter_standalone_import_dependency=False,
            scientific_imports=0,
            scientific_AST_executions=0,
            pytest_collection_runs=0,
            numerical_runs=0,
        ),
    )
    queue_path.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status=q["status"],
                Python_files=len(paths),
                owned=len(q["owned"]),
                protected=len(q["protected_sha256"]),
                literal_bodies=47,
                reference_closure_files=len(refs),
                scientific_import_closure_files=len(imports),
                new_imported_pins=len(added),
                scientific_imports=0,
                pytest_collection_runs=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    audit()
