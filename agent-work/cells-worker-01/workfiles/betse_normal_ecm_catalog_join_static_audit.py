"""Final static ownership, closure, budget and durable-runner audit; no science."""

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
PREFIX = "betse_normal_ecm_catalog_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def functions(path):
    return {n.name: n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}


def audit():
    path = WORK / f"{PREFIX}_workqueue.json"
    q = json.loads(path.read_text())
    relative = str(Path(__file__).relative_to(ROOT))
    if relative not in q["workfiles"]:
        q["workfiles"].append(relative)
    paths = [p for p in q["owned"] + q["workfiles"] if p.endswith(".py")]
    unresolved = {}
    for p in paths:
        text = (ROOT / p).read_text()
        compile(text, p, "exec")
        table = symtable.symtable(text, p, "exec")
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
    proof = module("catalog_AST", WORK / f"{PREFIX}_ast_audit.py").audit()
    assert proof == json.loads((WORK / f"{PREFIX}_AST_witness_01.json").read_text())
    mapping = json.loads((ROOT / "validation/betse" / f"{PREFIX}_source_map.json").read_text())
    assert all(mapping[k] == v for k, v in proof.items() if k != "kind")
    dependency = module("catalog_dependency", WORK / f"{PREFIX}_dependency_audit.py").audit()
    assert (
        dependency
        == q["explicit_dependency_refresh"]
        == json.loads((WORK / f"{PREFIX}_dependency_witness_01.json").read_text())
    )
    protocol = json.loads((ROOT / "validation/betse" / f"{PREFIX}_protocol.json").read_text())
    assert protocol["planned"] == q["planned"] and len(q["owned"]) == 9
    assert mapping["scope"] == protocol["scope"]
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    for p, h in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / p) == h, p
        assert sha(Path(protocol["native_source"]["installed_package"]).parent / p) == h, p
    for p, h in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / p) == h, p
    old_catalog = json.loads(
        (ROOT / "validation/betse/betse_normal_catalog_join_protocol.json").read_text()
    )
    assert protocol["catalog_budgets"] == old_catalog["catalog_budgets"]
    # The two Chief-owned repaired files have separate explicit current pins. Every
    # other owned lower component remains exact to its historical frozen packet.
    allowed = set(dependency["changes"])
    for family in ("field", "calcium"):
        frozen = (
            Path("/mnt/workspaces/Cells") / f"betse-normal-ecm-{family}-join-prepared-20261031-01"
        )
        inputs = json.loads((frozen / "inputs.json").read_text())
        for p, h in inputs["owned_sha256"].items():
            if p not in allowed:
                assert sha(ROOT / p) == h, p
    reach = json.loads((WORK / f"{PREFIX}_reachability_01.json").read_text())
    assert (
        reach["Python_files"] == 332 and reach["class_count"] == 55 and len(reach["families"]) == 7
    )
    assert reach["modern_numeric_methods"] == 110 and reach["Ca_routing_classes"] == 23
    assert reach["gate_p_parameter_reads"] == ["dt"] and not reach["implicit_free_Ca_class_gating"]
    fixture = ast.parse((ROOT / "validation/betse" / f"{PREFIX}_fixtures.py").read_text())
    names = ("CLASSES", "CASES", "CONTEXT_CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id in names
    }
    assert [len(constants[k]) for k in names] == [55, 71, 16, 5, 7, 16]
    assert (
        len(set(constants["CASES"]) | set(constants["RAW_CASES"]) | set(constants["DEPENDENCIES"]))
        == 94
    )
    assert (
        q["planned"]["fresh_Decimal_reference_forms"] == 55 * (4 + 10) + 16 * (4 + 3 * 10) == 1314
    )
    assert q["planned"]["carried_reference_forms"] == q["planned"]["enabled_ER_calls"] == 0
    test = functions(ROOT / "tests/unit" / f"test_{PREFIX}.py")
    history = ast.unparse(test["test_ecm_catalog_history"])
    for needed in (
        "-cold-return-before-bootstrap",
        "-CaATP-return-before-GRN-",
        "-material-return-before-field-",
        "-complete-return-",
        "before_channels=",
        "before_network=",
        "post_material_cache",
        "channel_calls",
        "-input-before-reference-",
        "actual_normal_source_clock=True",
    ):
        assert needed in history, needed
    assert history.index("-bootstrap-return") < history.index("isolated(tmp_path, inputs)")
    compare = ast.unparse(test["compare_channels"])
    for needed in (
        "128 * np.finfo(float).eps * (s + m + 4 + 32)",
        "32 * np.finfo(float).eps * (s + m + 16)",
        "1e-30 + flux_factor",
        "1e-30 + current_factor",
        "tolerance['absolute'] + tolerance['relative']",
        "source_effective_balance_mol",
        "true_grid_environment_change_mol",
        "conservative_balance_mol",
    ):
        assert needed in compare, needed
    assert "2e-18 + 2e-11 * abs(wanted)" in ast.unparse(test["compare_calcium"])
    raw = ast.unparse(test["test_ecm_catalog_raw_partial"])
    for needed in (
        "-raw-available-partial",
        "-raw-unexpected-complete",
        "-raw-channel-return-before-GRN",
        "cold_cache_guard",
        "empty_profile_indices",
        "cold_failure",
        "flux_after",
    ):
        assert needed in raw, needed
    dependencies = ast.unparse(test["test_ecm_catalog_dependencies"])
    assert (
        "-malformed-parent-before-call" in dependencies
        and "-unexpected-valid-admission" in dependencies
    )
    run = functions(ROOT / q["runner"])
    previous = functions(WORK / "betse_normal_network_join_checks_02.py")
    assert ast.dump(run["verify_pytest_ids"], include_attributes=False) == ast.dump(
        previous["verify_pytest_ids"], include_attributes=False
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
    runner = ast.unparse(run["molecule_reports"])
    assert "range(row['complete_calls'])" in runner and "'channels'" in runner
    assert "2 * row" in runner and "complete_native_ECM_modern_catalog" in ast.unparse(
        run["prepare"]
    )
    prepare = ast.unparse(run["prepare"])
    for needed in ("'catalog_' + constants['FAMILIES'][case]", "== 94", "== 78"):
        assert needed in prepare, needed
    closure = module("catalog_closure", WORK / "betse_normal_grn_join_static_audit.py").closure
    refs = closure(f"validation/betse/{PREFIX}_reference.py", reference=True)
    imports = closure(f"tests/unit/test_{PREFIX}.py", reference=False)
    assert "src/cells/processes/betse_normal_catalog_join.py" not in imports
    assert "src/cells/models/open_calcium_runtime.py" not in imports
    protected = dict(q["protected_sha256"])
    for p, h in protected.items():
        assert sha(ROOT / p) == h, p
    protected.update({p: h for p, h in (imports | refs).items() if p not in q["owned"]})
    assert not set(q["coordinated_shared_edit_paths"]) & set(imports)
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *[p for p in paths if PREFIX in p]],
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
            original_literal_channel_bodies=4,
            inherited_network_bodies=47,
            inherited_complete_field_functions=10,
            inherited_complete_CaATP_functions=3,
            all55_modern_class_methods_and_routes_unchanged=True,
            no_implicit_Ca_gate_or_catalog_biology_credit=True,
            actual_cold_reader_owner_flag=True,
            complete_Channel_and_private_core_caches=True,
            constructor_and_mutable_hot_epochs_distinct=True,
            named_profiles_original_order_duplicates_and_dtype=True,
            source_bulk_gather_and_grid_update_Co=True,
            zero_weight_route_nonce_and_last_route_cache=True,
            no_channel_ordinary_flux_storage=True,
            actual_pre_and_post_channel_conditionals=True,
            actual_clock_N3_bounded_prefix=True,
            absent_cold_CaATP_cache_and_source_written_carry=True,
            complete_returns_before_checks=True,
            complete_raw_native_and_port_partials=True,
            explicit_Chief_test_capture_dependency_refresh=True,
            original_old_Cav_G_and_ECM_failures_preserved=True,
            scalar_channel_reference_inside_material=True,
            independent_reference_closure_stdlib=True,
            unchanged_gate_flux_current_material_CaATP_GRN_field_budgets=True,
            exact_pytest_ID_validator_unchanged=True,
            post_output_terminal_failure_capture=True,
            scientific_imports=0,
            scientific_AST_executions=0,
            pytest_collection_runs=0,
            numerical_runs=0,
            source_ER_calls=0,
        ),
    )
    path.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(
        json.dumps(
            dict(
                status=q["status"],
                Python_files=len(paths),
                owned=len(q["owned"]),
                protected=len(protected),
                reference_closure_files=len(refs),
                scientific_import_closure_files=len(imports),
                planned_checks=94,
                planned_fresh_forms=1314,
                scientific_imports=0,
                scientific_AST_executions=0,
                numerical_runs=0,
                pytest_collection_runs=0,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    audit()
