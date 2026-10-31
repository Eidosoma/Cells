"""Compile, ownership, stdlib closure and durable-runner checks; no collection."""

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
PREFIX = "betse_normal_ecm_field_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def audit():
    queue_path = WORK / f"{PREFIX}_workqueue.json"
    q = json.loads(queue_path.read_text())
    self_path = str(Path(__file__).relative_to(ROOT))
    if self_path not in q["workfiles"]:
        q["workfiles"].append(self_path)
    paths = [p for p in q["owned"] + q["workfiles"] if p.endswith(".py")]
    unresolved = {}
    for p in paths:
        source = (ROOT / p).read_text()
        compile(source, p, "exec")
        table = symtable.symtable(source, p, "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__name__", "__file__"}

        def missing(scope, known=known):
            values = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                values |= missing(child)
            return values

        if value := missing(table):
            unresolved[p] = sorted(value)
    assert not unresolved, unresolved
    proof = module("field_AST", WORK / f"{PREFIX}_ast_audit.py").audit()
    source_map = json.loads((ROOT / "validation/betse" / f"{PREFIX}_source_map.json").read_text())
    assert all(source_map[k] == v for k, v in proof.items() if k != "kind")
    witness = json.loads((WORK / f"{PREFIX}_AST_witness_01.json").read_text())
    assert proof == witness
    dependency = module("coordinated_input_audit", WORK / f"{PREFIX}_dependency_audit.py").audit()
    assert dependency == q["coordinated_dependency_inputs"]
    assert dependency == json.loads((WORK / f"{PREFIX}_dependency_witness_01.json").read_text())
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    protocol = json.loads((ROOT / "validation/betse" / f"{PREFIX}_protocol.json").read_text())
    for p, h in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / p) == h, p
        assert sha(Path(protocol["native_source"]["installed_package"]).parent / p) == h, p
    for p, h in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / p) == h, p
    fixture = ast.parse((ROOT / "validation/betse" / f"{PREFIX}_fixtures.py").read_text())
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
        and t.id in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    }
    assert [
        len(constants[k]) for k in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    ] == [16, 4, 5, 10]
    assert (
        len(set(constants["CASES"]) | set(constants["RAW_CASES"]) | set(constants["DEPENDENCIES"]))
        == 31
    )
    planned = protocol["planned"]
    assert (
        planned == q["planned"]
        and planned["fresh_Decimal_reference_forms"] == 16 * (2 + 2 + 3 * (2 + 2 + 2)) == 352
    )
    tests = functions(ast.parse((ROOT / "tests/unit" / f"test_{PREFIX}.py").read_text()))
    code = ast.unparse(tests["test_normal_ecm_field_history"])
    assert code.index("-cold-return-before-bootstrap") < code.index("joined.initialize(")
    assert code.index("archive(tmp_path, case + '-bootstrap-return'") < code.index(
        "isolated(tmp_path, inputs)"
    )
    for needed in (
        "before_material=",
        "before_network=",
        "before_field=",
        "after_material=",
        "-complete-return-",
        "post_material_cache",
    ):
        assert needed in code, needed
    raw = ast.unparse(tests["test_normal_ecm_field_raw_partial"])
    for needed in (
        "-raw-material-return-",
        "-raw-complete-return-",
        "-raw-available-partial",
        "-raw-unexpected-complete",
        "strict_finite_guard_distinct_from_native_exception",
    ):
        assert needed in raw, needed
    dependencies = ast.unparse(tests["test_normal_ecm_field_dependencies"])
    assert (
        "-malformed-parent-before-call" in dependencies
        and "-unexpected-valid-admission" in dependencies
    )
    compare = ast.unparse(tests["compare_field"])
    assert "target[section]['gross']" in compare and "factor * np.asarray(gross[key])" in compare
    assert "actual[section]['gross']" not in compare
    ordinary = ast.unparse(tests["compare_material"])
    assert "material_checks.budget(" in ordinary and "source_voltage_nonce_delta_V" in ordinary
    runner = functions(ast.parse((ROOT / q["runner"]).read_text()))
    old = functions(ast.parse((WORK / "betse_normal_network_join_checks_02.py").read_text()))
    assert ast.dump(runner["verify_pytest_ids"], include_attributes=False) == ast.dump(
        old["verify_pytest_ids"], include_attributes=False
    )
    run = runner["run"]
    start = next(
        i
        for i, n in enumerate(run.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "target.mkdir(exist_ok=False)"
    )
    assert len(run.body) == start + 3 and isinstance(run.body[-1], ast.Try)
    assert ast.unparse(run.body[-1].handlers[0].type) == "BaseException"
    assert "live_hashes_before_computation" in ast.unparse(
        run
    ) and "live_hashes_after_computation" in ast.unparse(run)
    closure = module("stdlib_closure", WORK / "betse_normal_grn_join_static_audit.py").closure
    refs = closure(f"validation/betse/{PREFIX}_reference.py", reference=True)
    imports = closure(f"tests/unit/test_{PREFIX}.py", reference=False)
    provenance = {
        "validation/betse/betse_normal_voltage_reference.py": sha(
            ROOT / "validation/betse/betse_normal_voltage_reference.py"
        )
    }
    protected = {p: h for p, h in (imports | refs | provenance).items() if p not in q["owned"]}
    assert not any(
        any(
            x in p
            for x in ("betse_ecm_charged_grn", "betse_ecm_sim_grn", "betse_normal_transporter")
        )
        for p in imports
    )
    for p, h in q["protected_sha256"].items():
        assert sha(ROOT / p) == h, p
    for p, h in protected.items():
        assert sha(ROOT / p) == h, p
    assert "src/cells/models/open_calcium_runtime.py" not in imports
    check_paths = [p for p in paths if PREFIX in p or p.endswith("record_static_freeze_receipt.py")]
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *check_paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    q.update(
        status="static_audits_passed_ready_to_freeze_no_numerics",
        owned_sha256={p: sha(ROOT / p) for p in q["owned"]},
        protected_sha256=protected,
        reference_closure=refs,
        scientific_import_closure=imports,
        static_checks=dict(
            compile_without_import="passed",
            global_name_resolution="passed",
            ruff_check="passed",
            ruff_format="passed",
            inherited_network_literal_bodies=47,
            complete_native_field_functions=10,
            actual_bootstrap_and_suffix_order=True,
            original_get_current_unsubstituted=True,
            original_NaN_only_check_v=True,
            geometry_operator_cache_derived=True,
            previous_reconstructed_E_feedback_only=True,
            stale_GJ_cache_preserved=True,
            complete_return_before_later_work_capture=True,
            actual_post_material_cache_separate=True,
            full_raw_partial_buffers=True,
            independent_reference_closure_stdlib=True,
            independent_geometry_current_environment_voltage=True,
            reference_fixed_gross_budgets=True,
            material_legacy_budgets_unchanged=True,
            optional_new_material_diagnostic_unclaimed=True,
            coordinated_dependency_inverse_AST_equal=True,
            exact_pytest_ID_validator_unchanged=True,
            post_output_terminal_failure_capture=True,
            retained_ECM_panel_accepted=False,
            retained_ECM_panel_checks=[39, 40],
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
                protected=len(protected),
                reference_closure_files=len(refs),
                scientific_import_closure_files=len(imports),
                network_bodies=47,
                field_functions=10,
                planned_checks=31,
                planned_fresh_forms=352,
                scientific_imports=0,
                scientific_AST_executions=0,
                pytest_collection_runs=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    audit()
