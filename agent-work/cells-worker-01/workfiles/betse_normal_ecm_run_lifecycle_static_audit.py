"""Final source/AST/closure/hash/schema checks without scientific imports or collection."""

import ast
import builtins
import importlib.util
import json
import subprocess
import symtable
from pathlib import Path

from betse_normal_ecm_run_lifecycle_ast_audit import audit as AST_audit
from betse_normal_ecm_run_lifecycle_ast_audit import functions, signature
from betse_normal_ecm_run_lifecycle_dependencies import PARENT, PREFIX, ROOT, audit, sha

WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def compile_names(paths):
    for relative in paths:
        code = (ROOT / relative).read_text()
        compile(code, relative, "exec")
        table = symtable.symtable(code, relative, "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__"}

        def unresolved(scope, known=known):
            missing = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                missing |= unresolved(child)
            return missing

        assert not unresolved(table), (relative, sorted(unresolved(table)))


def check():
    queue_path = WORK / (PREFIX + "_workqueue.json")
    queue = json.loads(queue_path.read_text())
    protocol = json.loads((ROOT / "validation/betse" / (PREFIX + "_protocol.json")).read_text())
    mapping = json.loads((ROOT / "validation/betse" / (PREFIX + "_source_map.json")).read_text())
    proof = AST_audit()
    assert (
        proof
        == mapping["source_AST_proof"]
        == json.loads((WORK / (PREFIX + "_AST_witness_01.json")).read_text())
    )
    dependencies = audit()
    pinned = json.loads((WORK / (PREFIX + "_dependency_witness_02.json")).read_text())
    assert pinned == queue["explicit_dependency_binding"]
    # Live changes are only informational. They are never adopted; the frozen
    # dependency hashes, closure and reviewed ancestry must remain identical.
    informational = "observed_live_differences_not_adopted"
    assert {k: v for k, v in dependencies.items() if k != informational} == {
        k: v for k, v in pinned.items() if k != informational
    }
    for relative, pin in queue["owned_sha256"].items():
        assert sha(ROOT / relative) == pin, relative
    for relative, row in queue["frozen_dependency_sources"].items():
        assert sha(row["path"]) == row["sha256"] == queue["protected_snapshot_sha256"][relative]
        assert Path(row["path"]) == PARENT / "source" / relative
    for row in queue["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    controlled = queue["owned_sha256"] | queue["protected_snapshot_sha256"]
    assert all(
        controlled.get(p) == h
        for p, h in (queue["scientific_import_closure"] | queue["reference_closure"]).items()
    )
    assert queue["planned"] == protocol["planned"]
    planned = protocol["planned"]
    assert planned["checks"] == 12 + 4 + 3 + 22 + 6 + 1 == 48
    assert planned["fresh_Decimal_reference_forms"] == 12 * (4 + 3 * 8 * 2) == 624
    assert planned["native_captures"] == 12 + 4 + 6 == 22
    assert planned["duplicate_baseline_new_case_credit"] == planned["carried_reference_forms"] == 0
    inherited = json.loads(
        (
            PARENT / "source/validation/betse/betse_normal_ecm_event_mechanics_protocol.json"
        ).read_text()
    )
    for key in (
        "acceptance",
        "mechanics_acceptance",
        "mechanics_budget_source_sha256",
        "inherited_mechanics_divergence_category_disclosure",
    ):
        assert protocol[key] == inherited[key], key
    assert protocol["new_budget_changes"] is protocol["new_numerical_equations"] is False
    assert protocol["scope"]["maximum_field_cells"] == 16
    assert protocol["scope"]["minimum_quartic_display_cells"] == 25
    assert protocol["scope"]["component_qualification_pending"] is True
    native = protocol["native_source"]
    for relative, pin in native["source_sha256"].items():
        assert (
            sha(Path(native["checkout"]) / relative)
            == sha(Path(native["installed_package"]).parent / relative)
            == pin
        )
    paths = sorted({p for p in queue["owned"] + queue["workfiles"] if p.endswith(".py")})
    compile_names(paths)
    runner = functions(ROOT / queue["runner"])
    old = functions(PARENT / "driver.py")
    assert signature(runner["verify_pytest_ids"]) == signature(old["verify_pytest_ids"])
    prepare = ast.unparse(runner["prepare"])
    assert "shutil.copytree(parent / 'source'" in prepare
    assert "frozen_dependency_sources" in prepare and "protected_snapshot_sha256" in prepare
    assert "shutil.copytree(ROOT" not in prepare
    run = ast.unparse(runner["run"])
    for marker in (
        "inputs['source_hashes']",
        "inputs['native_snapshot_sha256']",
        "inputs['owned_sha256']",
        "timeout=480",
        "max_rss_bytes=2 ** 30",
        "min_available_bytes=8 * 2 ** 30",
        "except BaseException",
        "automatic_retry=False",
        "failure.json",
    ):
        assert marker in run, marker
    main = ast.unparse(runner["main"])
    assert "requested_round" in main and "cpu_coordinated" in main
    spec = importlib.util.spec_from_file_location(
        "headless_lifecycle_plan_only", ROOT / queue["runner"]
    )
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    groups, required = driver.plan(ROOT, protocol)
    ids = [item for group in groups.values() for item in group]
    assert len(ids) == len(set(ids)) == 48
    assert (
        sum(len(r["positive"]) + len(r["raw"]) + len(r["clocks"]) for r in required.values()) == 22
    )
    metadata = json.loads((WORK / (PREFIX + "_metadata_witness_01.json")).read_text())
    assert metadata["status"] == "passed_synthetic_metadata_only"
    assert metadata["test_sha256"] == sha(ROOT / "tests/unit" / ("test_" + PREFIX + ".py"))
    assert metadata["driver_sha256"] == sha(ROOT / queue["runner"])
    assert metadata["exact_ID_schema_cases"] == 48
    for arguments in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *arguments, *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (arguments, result.stdout, result.stderr)
    return dict(
        kind="cells.headless_ECM_lifecycle_final_static_witness@1",
        status="passed_static_preparation_only_unrun_unreleased",
        owned_files=len(queue["owned"]),
        protected_frozen_dependency_files=len(queue["protected_snapshot_sha256"]),
        compiled_python_files=len(paths),
        scientific_import_closure_modules=len(queue["scientific_import_closure"]),
        reference_closure_modules=len(queue["reference_closure"]),
        reference_closure_stdlib_only=True,
        exact_unique_planned_IDs=len(ids),
        groups={k: len(v) for k, v in groups.items()},
        planned_native_captures=22,
        planned_fresh_reference_forms=624,
        native_source_files=len(native["source_sha256"]),
        native_checkout_and_installed_exact=True,
        source_AST_proof=proof,
        compile_without_import="passed",
        global_names="passed",
        calendar_attribute_and_enum_member_interfaces="passed",
        ruff_check="passed",
        ruff_format="passed",
        metadata_witness=dict(
            path=str(WORK / (PREFIX + "_metadata_witness_01.json")),
            sha256=sha(WORK / (PREFIX + "_metadata_witness_01.json")),
        ),
        owned_live_pins_checked=True,
        frozen_dependency_runtime_authority=True,
        observed_live_changes_not_adopted=dependencies[informational],
        existing_scientific_equations_and_budgets_unchanged=True,
        component_qualification_pending=True,
        new_or_retained_qualification_passes=0,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        active_job_queries=0,
        automatic_followup=False,
    )


if __name__ == "__main__":
    result = check()
    path = WORK / (PREFIX + "_static_witness_01.json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"], compiled=result["compiled_python_files"], sha256=sha(path)
            )
        )
    )
