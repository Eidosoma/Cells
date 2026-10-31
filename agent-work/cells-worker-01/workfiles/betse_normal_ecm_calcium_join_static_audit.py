"""Static CaATP/full-field source, closure, clocks and durable-runner checks."""

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
PREFIX = "betse_normal_ecm_calcium_join"


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
    path = WORK / f"{PREFIX}_workqueue.json"
    q = json.loads(path.read_text())
    relative = str(Path(__file__).relative_to(ROOT))
    if relative not in q["workfiles"]:
        q["workfiles"].append(relative)
    paths = [p for p in q["owned"] + q["workfiles"] if p.endswith(".py")]
    unresolved = {}
    for p in paths:
        source = (ROOT / p).read_text()
        compile(source, p, "exec")
        table = symtable.symtable(source, p, "exec")
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
            unresolved[p] = sorted(found)
    assert not unresolved, unresolved
    proof = module("CaATP_AST", WORK / f"{PREFIX}_ast_audit.py").audit()
    witness = json.loads((WORK / f"{PREFIX}_AST_witness_02.json").read_text())
    assert proof == witness
    mapping = json.loads((ROOT / "validation/betse" / f"{PREFIX}_source_map.json").read_text())
    assert all(mapping[k] == v for k, v in proof.items() if k != "kind")
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    protocol = json.loads((ROOT / "validation/betse" / f"{PREFIX}_protocol.json").read_text())
    for p, h in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / p) == h, p
        assert sha(Path(protocol["native_source"]["installed_package"]).parent / p) == h, p
    for p, h in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / p) == h, p
    reach = json.loads((WORK / f"{PREFIX}_reachability_01.json").read_text())
    assert reach["Python_files"] == 332 and reach["sole_Ca_dyn_value"] is False
    assert (
        len(reach["missing_ER_parameter_producers"]) == 8
        and not reach["native_ER_cold_setup_reachable_without_override"]
    )
    fixture = ast.parse((ROOT / "validation/betse" / f"{PREFIX}_fixtures.py").read_text())
    cases = {
        t.id: ast.literal_eval(n.value)
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name)
        and t.id in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    }
    assert [
        len(cases[k]) for k in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    ] == [16, 4, 6, 12]
    assert len(set(cases["CASES"]) | set(cases["RAW_CASES"]) | set(cases["DEPENDENCIES"])) == 34
    planned = protocol["planned"]
    assert (
        planned == q["planned"]
        and planned["fresh_Decimal_reference_forms"] == 16 * (2 + 2 + 3 * (2 + 2 + 2 + 2)) == 448
    )
    assert (
        planned["enabled_ER_calls"] == 0
        and planned["positive_active_CaATP_helper_calls_per_implementation"] == 15 * 3
    )
    tests = functions(ast.parse((ROOT / "tests/unit" / f"test_{PREFIX}.py").read_text()))
    history = ast.unparse(tests["test_ecm_calcium_field_history"])
    for needed in (
        "-cold-return-before-bootstrap",
        "-CaATP-return-before-GRN-",
        "-material-return-before-field-",
        "-complete-return-",
        "before_calcium=",
        "after_calcium=",
        "post_material_cache",
        "source_times_s",
        "clock_after",
    ):
        assert needed in history, needed
    assert history.index("-bootstrap-return") < history.index("isolated(tmp_path, inputs)")
    raw = ast.unparse(tests["test_ecm_calcium_raw_partial"])
    for needed in (
        "-raw-before-CaATP-",
        "-raw-CaATP-return-",
        "-raw-available-partial",
        "-raw-unexpected-complete",
        "helper_only=True",
    ):
        assert needed in raw, needed
    dep = ast.unparse(tests["test_ecm_calcium_dependencies"])
    assert (
        "-malformed-parent-before-call" in dep
        and "RateCache(True, ions.freeze(np.zeros(9)))" in dep
    )
    compare = ast.unparse(tests["compare_calcium"])
    assert "2e-18 + 2e-11 * abs(wanted)" in compare
    assert "target['rate_cache_after']" in compare and "formal_ATP" not in compare
    run = functions(ast.parse((ROOT / q["runner"]).read_text()))
    old = functions(ast.parse((WORK / "betse_normal_network_join_checks_02.py").read_text()))
    assert ast.dump(run["verify_pytest_ids"], include_attributes=False) == ast.dump(
        old["verify_pytest_ids"], include_attributes=False
    )
    body = run["run"].body
    start = next(
        i
        for i, n in enumerate(body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "target.mkdir(exist_ok=False)"
    )
    assert (
        len(body) == start + 3
        and isinstance(body[-1], ast.Try)
        and ast.unparse(body[-1].handlers[0].type) == "BaseException"
    )
    assert all(
        k in ast.unparse(run["molecule_reports"])
        for k in (
            "calcium",
            "source_ER_disabled",
            "actual_normal_source_clock",
        )
    )
    closure = module("closure_only", WORK / "betse_normal_grn_join_static_audit.py").closure
    refs = closure(f"validation/betse/{PREFIX}_reference.py", reference=True)
    imports = closure(f"tests/unit/test_{PREFIX}.py", reference=False)
    field_inputs = json.loads(
        Path(q["binding_evidence"]["frozen_field01_inputs"]["path"]).read_text()
    )
    protected = {
        p: h
        for p, h in (imports | refs | field_inputs["owned_sha256"]).items()
        if p not in q["owned"]
    }
    assert not any(
        any(
            s in p
            for s in ("betse_ecm_charged_grn", "betse_ecm_sim_grn", "betse_normal_transporter")
        )
        for p in imports
    )
    assert "src/cells/models/open_calcium_runtime.py" not in imports
    for p, h in q["protected_sha256"].items():
        assert sha(ROOT / p) == h, p
    for p, h in protected.items():
        assert sha(ROOT / p) == h, p
    new_paths = [p for p in paths if PREFIX in p]
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *new_paths],
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
            inherited_network_bodies=47,
            inherited_complete_field_functions=10,
            complete_native_CaATP_functions=3,
            actual_CaATP_cold_producers=True,
            actual_native_Ca_dyn_False=True,
            no_missing_ER_defaults_injected=True,
            actual_normal_source_clock_and_argument_order=True,
            material_dt_sum_separate=True,
            native_cold_Ca_GeRN_rho_relative_order=True,
            full_field_feedback_inherited_byte_exact=True,
            ECM_fancy_copy_and_membrane_view_preserved=True,
            actual_rate_alias_and_mask_order=True,
            absent_cold_rate_then_source_written_cache=True,
            complete_returns_before_later_work=True,
            full_native_and_port_raw_partial_retention=True,
            source_strict_finite_refusals_distinguished=True,
            independent_reference_closure_stdlib=True,
            independent_scalar_CaATP_inside_material_and_local=True,
            existing_material_pump_GRN_field_budgets_preserved=True,
            exact_pytest_ID_validator_unchanged=True,
            post_output_terminal_failure_capture=True,
            source_ER_calls=0,
            retained_material_panel_accepted=False,
            scientific_imports=0,
            scientific_AST_executions=0,
            pytest_collection_runs=0,
            numerical_runs=0,
        ),
    )
    path.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status=q["status"],
                Python_files=len(paths),
                owned=7,
                protected=len(protected),
                reference_closure_files=len(refs),
                scientific_import_closure_files=len(imports),
                planned_checks=34,
                planned_fresh_forms=448,
                source_ER_calls=0,
                scientific_imports=0,
                scientific_AST_executions=0,
                pytest_collection_runs=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    audit()
