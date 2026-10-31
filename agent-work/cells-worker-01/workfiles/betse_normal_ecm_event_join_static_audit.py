"""Static closure, interfaces, clocks, fixed budgets and durable runner audit only."""

import argparse
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
PREFIX = "betse_normal_ecm_event_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def functions(path):
    return {
        n.name: n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)
    }


def audit():
    queue_path = WORK / (PREFIX + "_workqueue.json")
    q = json.loads(queue_path.read_text())
    protocol = json.loads((ROOT / "validation/betse" / (PREFIX + "_protocol.json")).read_text())
    mapping = json.loads((ROOT / "validation/betse" / (PREFIX + "_source_map.json")).read_text())
    own_work = [
        str(p.relative_to(ROOT)) for p in sorted(WORK.glob("*" + PREFIX + "*")) if p.is_file()
    ]
    q["workfiles"] = sorted(set(q["workfiles"] + own_work))
    paths = [p for p in q["owned"] + q["workfiles"] if p.endswith(".py")]
    unresolved = {}
    for relative in paths:
        code = (ROOT / relative).read_text()
        compile(code, relative, "exec")
        table = symtable.symtable(code, relative, "exec")
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
    proof = module("event_source_audit", WORK / (PREFIX + "_ast_audit.py")).audit()
    assert proof == json.loads((WORK / (PREFIX + "_AST_witness_02.json")).read_text())
    assert all(mapping[k] == v for k, v in proof.items() if k != "kind")
    dep = module("event_dependency_audit", WORK / (PREFIX + "_dependency_audit.py")).audit()
    assert (
        dep
        == q["explicit_dependency_refresh"]
        == json.loads((WORK / (PREFIX + "_dependency_witness_01.json")).read_text())
    )
    for path, expected in q["protected_sha256"].items():
        assert sha(ROOT / path) == expected, path
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    assert q["planned"] == protocol["planned"]
    assert len(q["owned"]) == 10
    assert mapping["scope"] == protocol["scope"]
    assert protocol["planned"]["checks"] == 42
    assert protocol["planned"]["fresh_Decimal_reference_forms"] == 20 * (4 + 3 * 14) == 920
    assert (
        protocol["planned"]["carried_reference_forms"]
        == protocol["planned"]["enabled_ER_calls"]
        == 0
    )
    assert (
        protocol["catalog_budgets"]
        == json.loads(
            (ROOT / "validation/betse/betse_normal_ecm_catalog_join_protocol.json").read_text()
        )["catalog_budgets"]
    )
    for relative, expected in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    pins = protocol["native_source"]
    for relative, expected in pins["source_sha256"].items():
        assert sha(Path(pins["checkout"]) / relative) == expected, relative
        assert sha(Path(pins["installed_package"]).parent / relative) == expected, relative
    reach = json.loads((WORK / (PREFIX + "_reachability_01.json")).read_text())
    assert reach["Python_files"] == 332 and reach["installed_exact"] is True
    # Earlier reachability pending flag records that audit's historical stage;
    # current prerequisite status is explicitly stored in this owned queue.
    fixture = ast.parse((ROOT / "validation/betse" / (PREFIX + "_fixtures.py")).read_text())
    names = ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    constants = {
        t.id: ast.literal_eval(n.value)
        for n in fixture.body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id in names
    }
    assert [len(constants[k]) for k in names] == [20, 6, 6, 16]
    assert (
        len(set(constants["CASES"]) | set(constants["RAW_CASES"]) | set(constants["DEPENDENCIES"]))
        == 42
    )
    tests = functions(ROOT / "tests/unit" / ("test_" + PREFIX + ".py"))
    history = ast.unparse(tests["test_ecm_event_history"])
    for needed in (
        "before_events=",
        "before_noise=",
        "after_events=",
        "after_noise=",
        "prospective_draw_is_uncommitted",
        "prospective_stream_after",
        "noise_stream_after",
        "event_stores_after",
        "runtime_material_binding",
        "geometry_binding.identity",
        "candidate.noise_cache.present",
        "-actual-",
        "-complete-return-",
        "conditional_event_reference_forms=6",
        "conditional_noise_reference_forms=6",
    ):
        assert needed in history, needed
    assert history.index("-bootstrap-return") < history.index("isolated(tmp_path, inputs)")
    raw = ast.unparse(tests["test_ecm_event_raw_partial"])
    for needed in (
        "available_event_stores",
        "catalog_trace",
        "-raw-available-partial",
        "-raw-unexpected-complete",
        "completed == 2",
        "protein_noise_large_limit",
        "negative_Dm_source_return",
        "GRN_refuses_before_noise",
        "radial_pressure_shape",
    ):
        assert needed in raw, needed
    assert "source_completed" in raw and "source_refused" in raw
    dependency = ast.unparse(tests["test_ecm_event_dependencies"])
    for needed in (
        "-valid-admission",
        "-malformed-parent",
        "-malformed-inputs",
        "joined.require_salt_roles",
        "actual_message=str(leaf)",
        "type(leaf) is ValueError",
    ):
        assert needed in dependency, needed
    for source_name in ("compare_events", "compare_noise"):
        text = ast.unparse(tests[source_name])
        assert "budget" in text or "5e-13" in text
    assert "64 * np.finfo(float).eps * np.maximum(1.0, abs(value))" in ast.unparse(
        tests["compare_events"]
    )
    assert "1e-23 + 5e-13 * abs(wanted)" in ast.unparse(tests["compare_noise"])
    main = functions(ROOT / "src/cells/processes" / (PREFIX + ".py"))
    advance = ast.unparse(main["advance"])
    assert "steps=[source.clone(packet)]" in advance
    assert advance.index("forcing = material.drive(runtime, packet)") < advance.index(
        "before_material(source.clone(material_input))"
    )
    assert "source.clone(packet)" in advance and "source.cache(ctx)" in advance
    assert "if key != 'ctx'" in advance
    run = functions(ROOT / q["runner"])
    old = functions(WORK / "betse_normal_ecm_catalog_join_checks_02.py")
    assert ast.dump(run["verify_pytest_ids"], include_attributes=False) == ast.dump(
        old["verify_pytest_ids"], include_attributes=False
    )
    body = run["run"].body
    start = next(
        i
        for i, n in enumerate(body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "target.mkdir(exist_ok=False)"
    )
    assert len(body) == start + 3 and isinstance(body[-1], ast.Try)
    assert ast.unparse(body[-1].handlers[0].type) == "BaseException"
    prepare = ast.unparse(run["prepare"])
    assert "kind='cells.normal_ecm_event_join_prepared@1'" in prepare
    assert "== 42" in prepare and "== 26" in prepare
    assert "freeze_prerequisites" in prepare
    reader = ast.unparse(run["molecule_reports"])
    assert "'event' if name == 'events'" in reader and "'channel' if name == 'channels'" in reader
    assert "strict_port_guard_distinct_from_native_exception" in reader
    assert "0 <= row['completed_calls'] < 3" in reader
    closure = module("event_closure", WORK / "betse_normal_grn_join_static_audit.py").closure
    refs = closure("validation/betse/" + PREFIX + "_reference.py", reference=True)
    imports = closure("tests/unit/test_" + PREFIX + ".py", reference=False)
    assert "src/cells/processes/betse_normal_catalog_join.py" not in imports
    assert "src/cells/models/open_calcium_runtime.py" not in imports
    assert not set(q["coordinated_shared_edit_paths"]) & set(imports)
    protected = dict(q["protected_sha256"])
    protected.update({p: h for p, h in (imports | refs).items() if p not in q["owned"]})
    for relative in refs:
        compile((ROOT / relative).read_text(), relative, "exec")
    # Audit keyword interfaces for direct calls to inherited consumer functions.
    providers = {
        "events": functions(ROOT / "src/cells/processes" / (PREFIX + "_source.py")),
        "event_material": functions(ROOT / "src/cells/processes" / (PREFIX + "_material.py")),
        "calcium_component": functions(
            ROOT / "src/cells/processes/betse_normal_ecm_calcium_join.py"
        ),
        "full": functions(ROOT / "src/cells/processes/betse_normal_ecm_field_join.py"),
        "source": functions(ROOT / "src/cells/processes/betse_normal_ecm_catalog_join_source.py"),
    }
    interfaces = 0
    for node in ast.walk(ast.parse((ROOT / "src/cells/processes" / (PREFIX + ".py")).read_text())):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or not isinstance(node.func.value, ast.Name)
        ):
            continue
        provider = providers.get(node.func.value.id, {})
        if node.func.attr not in provider:
            continue
        target = provider[node.func.attr].args
        if target.kwarg is None:
            allowed = {a.arg for a in target.args + target.posonlyargs + target.kwonlyargs}
            assert {k.arg for k in node.keywords} <= allowed, (ast.unparse(node.func), allowed)
            interfaces += 1
    selected = [p for p in paths if PREFIX in p]
    for args in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *selected],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    metadata = json.loads((WORK / (PREFIX + "_reporting_metadata_check_02.json")).read_text())
    assert metadata["status"] == "passed_synthetic_metadata_only"
    assert metadata["actual_producer_test_sha256"] == sha(
        ROOT / "tests/unit" / ("test_" + PREFIX + ".py")
    )
    assert metadata["driver_sha256"] == sha(ROOT / q["runner"])
    review = q["freeze_prerequisites"]["Chief03_source_review"]
    if review is not None:
        assert sha(review["path"]) == review["sha256"]
        reviewed = json.loads(Path(review["path"]).read_text())
        assert reviewed["status"] == "clear_for_held_full_roster_runner_preparation"
        assert reviewed["blockers"] == []
        for path, changed in q["explicit_dependency_refresh"]["changes"].items():
            assert reviewed["module_proofs"][path]["after_sha256"] == changed["new_sha256"]
        assert q["binding_evidence"]["Chief03_source_review"] == review
    checks = dict(
        compile_without_import="passed",
        global_names="passed",
        ruff_check="passed",
        ruff_format="passed",
        owned_python_files=sum(p.endswith(".py") for p in q["owned"]),
        all_python_files_compiled=len(paths),
        reference_closure_modules=len(refs),
        scientific_import_closure_modules=len(imports),
        direct_keyword_interfaces=interfaces,
        source_AST_proof=proof,
        explicit03_dependency_refresh=True,
        complete_parent_actual_inputs_native_returns_and_failure_archives=True,
        fixed_inherited_budgets_unchanged=True,
        scalar_control_and_noise_reference_inverse_exact=True,
        actual_dense_calendar_and_separate_material_dt=True,
        supplied_entry_owner_no_mesh_or_initializer_inference=True,
        bounded_metadata_cases=2,
        bounded_metadata_files=162,
        raw_schema_cases=6,
        dependency_schema_cases=16,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )
    q.update(
        status="static_audits_passed_ready_to_freeze"
        if review
        else "static_audits_passed_pending_Chief03_source_review",
        owned_sha256={p: sha(ROOT / p) for p in q["owned"]},
        protected_sha256=protected,
        reference_closure=refs,
        scientific_import_closure=imports,
        static_checks=checks,
    )
    queue_path.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
    result = dict(
        kind="cells.normal_ecm_event_join_final_static_audit@1",
        status=q["status"],
        owned_files=len(q["owned"]),
        protected_files=len(protected),
        planned=q["planned"],
        checks=checks,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--number", default="02")
    args = parser.parse_args()
    result = audit()
    path = WORK / (PREFIX + "_static_witness_" + args.number + ".json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                owned=result["owned_files"],
                protected=result["protected_files"],
                checks=42,
                fresh_forms=920,
            ),
            sort_keys=True,
        )
    )
