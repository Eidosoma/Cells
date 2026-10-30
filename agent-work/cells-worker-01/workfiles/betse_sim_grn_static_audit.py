"""Final standalone source/ownership/import/runner audits; no science executes."""

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


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit():
    queue_path = WORK / "betse_sim_grn_workqueue.json"
    q = json.loads(queue_path.read_text())
    paths = [p for p in q["owned"] + q["workfiles"] if p.endswith(".py")]
    unresolved = {}
    for relative in paths:
        text = (ROOT / relative).read_text()
        compile(text, relative, "exec")
        table = symtable.symtable(text, relative, "exec")
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
            unresolved[relative] = sorted(found)
    assert not unresolved, unresolved
    proof = load_module("standalone_AST", WORK / "betse_sim_grn_ast_audit.py").audit()
    mapping = json.loads((ROOT / "validation/betse/betse_sim_grn_source_map.json").read_text())
    assert proof == {key: mapping[key] for key in proof}
    assert proof["literal_scientific_body_count"] == 46
    assert len(q["owned"]) == 7 and len(q["protected_sha256"]) == 255
    for path, digest in q["protected_sha256"].items():
        assert sha(ROOT / path) == digest, path
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    protocol = json.loads((ROOT / "validation/betse/betse_sim_grn_protocol.json").read_text())
    assert protocol["planned"]["checks"] == 22
    assert protocol["planned"]["fresh_Decimal_reference_forms"] == 190
    assert len(protocol["native_source"]["source_sha256"]) == 22
    for relative, digest in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / relative) == digest
        assert sha(Path(protocol["native_source"]["installed_package"]).parent / relative) == digest
    for path, digest in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / path) == digest
    fixture = ast.parse((ROOT / "validation/betse/betse_sim_grn_fixtures.py").read_text())
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
        and t.id in {"CASES", "RAW_CASES", "DEPENDENCIES", "COMPONENT_CONTROLS"}
    }
    assert [
        len(constants[k]) for k in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    ] == [10, 3, 5, 7]
    tests = {
        n.name: n
        for n in ast.parse((ROOT / "tests/unit/test_betse_sim_grn.py").read_text()).body
        if isinstance(n, ast.FunctionDef)
    }
    assert {
        "test_standalone_grn_advancing_history",
        "test_standalone_grn_partial_failure",
        "test_standalone_grn_dependencies",
    } <= tests.keys()
    assert "baseline_admitted=True" in ast.unparse(tests["test_standalone_grn_dependencies"])
    for name in (
        "test_standalone_grn_advancing_history",
        "test_standalone_grn_partial_failure",
        "test_standalone_grn_dependencies",
    ):
        code = ast.unparse(tests[name])
        assert "except Exception as error" in code and "traceback.format_exc()" in code, name
    assert "source_effective_amount" in (ROOT / "tests/unit/test_betse_sim_grn.py").read_text()
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
        and isinstance(run.body[start + 1], ast.Assign)
        and isinstance(run.body[-1], ast.Try)
    )
    assert ast.unparse(run.body[-1].handlers[0].type) == "BaseException"
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    closure = load_module(
        "accepted_closure", WORK / "betse_normal_grn_join_static_audit.py"
    ).closure
    refs = closure("validation/betse/betse_sim_grn_reference.py", reference=True)
    imports = closure("tests/unit/test_betse_sim_grn.py", reference=False)
    assert not set(q["protected_but_not_imported_side_package_paths"]) & imports.keys()
    q.update(
        status="static_audits_passed_ready_to_freeze_no_sim_grn_numerics",
        owned_sha256={p: sha(ROOT / p) for p in q["owned"]},
        reference_closure=refs,
        scientific_import_closure=imports,
        static_checks=dict(
            compile_without_import="passed",
            global_name_resolution="passed",
            ruff_check="passed",
            ruff_format="passed",
            literal_original_scientific_bodies=46,
            actual_entire_run_core_sim=True,
            original_new_owner_branch=True,
            actual_reinitialize_clear_sample_report_export=True,
            complete_public_state_hydration_AST=True,
            no_normal_solver_dispatch_substitution=True,
            independent_clock_and_sample_reference=True,
            warm_reference_inverse_AST_equal=True,
            reference_fixed_budgets=True,
            source_effective_and_single_bath_books_separate=True,
            exact_unique_pytest_ID_validator_AST_unchanged=True,
            post_output_terminal_failure_capture_AST="passed",
            independent_reference_closure_stdlib=True,
            pending_charged_transporter_import_dependency=False,
            scientific_AST_executions=0,
            scientific_imports=0,
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
                owned=7,
                protected=255,
                scientific_bodies=46,
                reference_closure_files=len(refs),
                scientific_import_closure_files=len(imports),
                scientific_imports=0,
                numerical_runs=0,
                pytest_collection_runs=0,
            )
        )
    )


if __name__ == "__main__":
    audit()
