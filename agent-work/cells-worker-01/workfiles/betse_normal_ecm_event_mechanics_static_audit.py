"""Final static source/pin/closure/interface/schema audit; never run scientific AST."""

import argparse
import ast
import json
import subprocess
from pathlib import Path

from betse_normal_ecm_event_mechanics_ast_audit import audit as source_audit
from betse_normal_ecm_event_mechanics_audit_tools import (
    ROOT,
    compile_names,
    functions,
    sha,
    signature,
    write,
)
from betse_normal_ecm_event_mechanics_dependency_audit import audit as dependency_audit

PREFIX = "betse_normal_ecm_event_mechanics"
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def audit():
    q = json.loads((WORK / (PREFIX + "_workqueue.json")).read_text())
    protocol = json.loads((ROOT / "validation/betse" / (PREFIX + "_protocol.json")).read_text())
    mapping = json.loads((ROOT / "validation/betse" / (PREFIX + "_source_map.json")).read_text())
    source = source_audit()
    dependencies = dependency_audit()
    assert (
        source
        == mapping["source_AST_proof"]
        == json.loads((WORK / (PREFIX + "_AST_witness_01.json")).read_text())
    )
    assert (
        dependencies
        == q["explicit_dependency_binding"]
        == json.loads((WORK / (PREFIX + "_dependency_witness_02.json")).read_text())
    )
    for name, expected in (q["owned_sha256"] | q["protected_sha256"]).items():
        assert sha(ROOT / name) == expected, name
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    assert (
        q["reference_closure"] == dependencies["reference_closure"]
        and q["scientific_import_closure"] == dependencies["scientific_import_closure"]
    )
    controlled = q["owned_sha256"] | q["protected_sha256"]
    assert all(
        controlled.get(p) == h
        for p, h in (q["reference_closure"] | q["scientific_import_closure"]).items()
    )
    assert q["planned"] == protocol["planned"]
    planned = q["planned"]
    assert planned["checks"] == 25 + 7 + 26 + 4 == 62
    assert planned["fresh_Decimal_reference_forms"] == (25 + 4) * (4 + 3 * 8 * 2) == 1508
    assert planned["new_positive_reference_forms"] == 25 * 52 == 1300
    assert planned["duplicate_baseline_reference_forms"] == 4 * 52 == 208
    assert planned["native_captures"] == 25 + 7 + 4 == 36
    assert (
        planned["carried_reference_forms"]
        == planned["retained_qualification_passes"]
        == q["numerical_runs"]
        == 0
    )
    event_contract = json.loads(
        Path(
            "/mnt/workspaces/Cells/betse-normal-ecm-event-join-prepared-20261031-01/source/validation/betse/betse_normal_ecm_event_join_protocol.json"
        ).read_text()
    )
    assert protocol["acceptance"] == event_contract["acceptance"]
    for path, pin in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / path) == pin, path
    assert protocol["mechanics_budget_source_sha256"] == sha(
        ROOT / "validation/betse/betse_mechanics_join_checks.py"
    )
    assert (
        protocol["scope"]["maximum_field_cells"] == 16
        and protocol["scope"]["minimum_quartic_display_cells"] == 25
    )
    assert protocol["scope"]["component_qualification_pending"] is True
    pins = protocol["native_source"]
    for relative, pin in pins["source_sha256"].items():
        assert (
            sha(Path(pins["checkout"]) / relative)
            == sha(Path(pins["installed_package"]).parent / relative)
            == pin
        ), relative
    paths = sorted({p for p in q["owned"] + q["workfiles"] if p.endswith(".py")})
    compile_names(paths)
    runner = functions(ROOT / q["runner"])
    old = functions(
        Path("/mnt/workspaces/Cells/betse-normal-ecm-event-join-prepared-20261031-01/driver.py")
    )
    assert signature(runner["verify_pytest_ids"]) == signature(old["verify_pytest_ids"])
    run = runner["run"]
    created = next(
        i
        for i, n in enumerate(run.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "target.mkdir(exist_ok=False)"
    )
    assert len(run.body) == created + 3 and isinstance(run.body[-1], ast.Try)
    assert ast.unparse(run.body[-1].handlers[0].type) == "BaseException"
    main = ast.unparse(runner["main"])
    assert "requested_round" in main and "cpu_coordinated" in main
    prepare = ast.unparse(runner["prepare"])
    for marker in (
        "freeze_prerequisites",
        "explicit_dependency_binding",
        "snapshot_only_unloaded_paths",
    ):
        assert marker in prepare, marker
    metadata = json.loads((WORK / (PREFIX + "_reporting_metadata_check_02.json")).read_text())
    assert metadata["status"] == "passed_synthetic_metadata_only"
    assert metadata["test_sha256"] == sha(ROOT / "tests/unit" / ("test_" + PREFIX + ".py"))
    assert metadata["driver_sha256"] == sha(ROOT / q["runner"])
    assert metadata["exact_ID_schema_cases"] == 62
    for arguments in (["check"], ["format", "--check"]):
        result = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *arguments, *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (arguments, result.stdout, result.stderr)
    return dict(
        kind="cells.event_mechanics_final_static_witness@1",
        status="passed_static_preparation_only",
        owned_files=len(q["owned"]),
        protected_files=len(q["protected_sha256"]),
        compiled_python_files=len(paths),
        reference_closure_modules=len(q["reference_closure"]),
        scientific_import_closure_modules=len(q["scientific_import_closure"]),
        package_initializers=[
            p for p in q["scientific_import_closure"] if p.endswith("/__init__.py")
        ],
        source_AST_proof=source,
        explicit_dependency_binding=dependencies["catalog04_guard"],
        resolved_ancestor_overlaps=len(dependencies["overlap_resolution"]),
        compile_without_import="passed",
        global_names="passed",
        ruff_check="passed",
        ruff_format="passed",
        exact_unique_planned_IDs=62,
        planned_native_captures=36,
        planned_fresh_reference_forms=1508,
        bounded_metadata_check=metadata,
        all_existing_scientific_and_budget_files_unchanged=True,
        component_qualification_pending=True,
        new_or_retained_qualification_passes=0,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=WORK / (PREFIX + "_static_witness_01.json"))
    args = parser.parse_args()
    result = audit()
    write(args.output, result)
    print(
        json.dumps(
            dict(
                status=result["status"],
                compiled=result["compiled_python_files"],
                sha256=sha(args.output),
            )
        )
    )
