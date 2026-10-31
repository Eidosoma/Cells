"""Static import/name/hash/scope audit; never import or evaluate scientific modules."""

import argparse
import ast
import builtins
import hashlib
import importlib.util
import json
import subprocess
import symtable
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_calcium_domain04"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def functions(path):
    return {
        n.name: n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)
    }


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def closure(start, *, reference):
    pending, closed = [start], {}
    while pending:
        relative = pending.pop()
        if relative in closed:
            continue
        path = ROOT / relative
        tree = ast.parse(path.read_text())
        compile(tree, relative, "exec")
        closed[relative] = sha(path)
        # Include explicit package initializers; namespace packages have no file.
        for parent in path.parents:
            if parent in (ROOT, ROOT / "src") or ROOT not in parent.parents:
                break
            initializer = parent / "__init__.py"
            if initializer.is_file():
                pending.append(str(initializer.relative_to(ROOT)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level, (relative, "relative import not covered")
                names = [node.module] + [node.module + "." + item.name for item in node.names]
            else:
                continue
            for name in names:
                head = name.split(".")[0]
                if reference:
                    assert head in sys.stdlib_module_names | {"validation"}, (relative, name)
                if head not in {"cells", "validation", "tests"}:
                    continue
                for base in (ROOT, ROOT / "src"):
                    module_path = base / (name.replace(".", "/") + ".py")
                    package = base / name.replace(".", "/") / "__init__.py"
                    for candidate in (module_path, package):
                        if candidate.is_file():
                            pending.append(str(candidate.relative_to(ROOT)))
    return closed


def audit():
    q = json.loads((WORK / (PREFIX + "_workqueue.json")).read_text())
    protocol = json.loads((ROOT / "validation/betse" / (PREFIX + "_protocol.json")).read_text())
    mapping = json.loads((ROOT / "validation/betse" / (PREFIX + "_source_map.json")).read_text())
    proof = module("calcium04_ast", WORK / (PREFIX + "_ast_audit.py")).audit()
    assert proof == json.loads((WORK / (PREFIX + "_AST_witness_01.json")).read_text())
    assert mapping["source_classification_AST_proof"] == proof
    for path, expected in (q["owned_sha256"] | q["protected_sha256"]).items():
        assert sha(ROOT / path) == expected, path
    for row in list(q["binding_evidence"].values()) + list(
        q["retained_failure_artifacts"].values()
    ):
        assert sha(row["path"]) == row["sha256"], row["path"]
    assert (
        q["freeze_prerequisites"]["saved_failure_review"]
        == q["binding_evidence"]["saved_failure_review"]
    )
    assert q["planned"] == protocol["planned"]
    assert protocol["planned"]["checks"] == 15 + 6 + 1 + 12 == 34
    assert protocol["planned"]["fresh_Decimal_reference_forms"] == 15 * 28 + 4 + 2 * 8 + 2 == 442
    assert protocol["planned"]["native_captures"] == 22
    assert protocol["planned"]["carried_reference_forms"] == q["numerical_runs"] == 0
    old = Path("/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-prepared-20261031-03")
    legacy_protocol = json.loads(
        (old / "source/validation/betse/betse_normal_ecm_calcium_join_protocol.json").read_text()
    )
    assert protocol["acceptance"] == legacy_protocol["acceptance"]
    assert protocol["accounting"] == legacy_protocol["accounting"]
    for relative, expected in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / relative) == expected, relative
    pins = protocol["native_source"]
    for relative, expected in pins["source_sha256"].items():
        assert sha(Path(pins["checkout"]) / relative) == expected, relative
        assert sha(Path(pins["installed_package"]).parent / relative) == expected, relative
    refs = closure("validation/betse/" + PREFIX + "_reference.py", reference=True)
    # Original subprocess reference entry points also form part of this package.
    refs.update(
        closure("validation/betse/betse_normal_ecm_calcium_join_reference.py", reference=True)
    )
    imports = closure("tests/unit/test_" + PREFIX + ".py", reference=False)
    assert refs == q["reference_closure"]
    assert imports == q["scientific_import_closure"]
    controlled = q["owned_sha256"] | q["protected_sha256"]
    assert all(controlled.get(p) == h for p, h in (imports | refs).items())
    assert "src/cells/processes/betse_normal_ecm_catalog_join_source.py" not in imports
    assert not any(
        "betse_native_cut_lifecycle" in p or "betse_normal_ecm_event_join" in p for p in imports
    )
    paths = sorted({p for p in q["owned"] + q["workfiles"] if p.endswith(".py")})
    for relative in paths:
        code = (ROOT / relative).read_text()
        compile(code, relative, "exec")
        table = symtable.symtable(code, relative, "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__"}

        def missing(scope, known=known):
            found = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                found |= missing(child)
            return found

        assert not missing(table), (relative, missing(table))
    driver = functions(ROOT / q["runner"])
    old_driver = functions(old / "driver.py")
    assert ast.dump(driver["verify_pytest_ids"], include_attributes=False) == ast.dump(
        old_driver["verify_pytest_ids"], include_attributes=False
    )
    run = driver["run"]
    created = next(
        i
        for i, n in enumerate(run.body)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "target.mkdir(exist_ok=False)"
    )
    assert len(run.body) == created + 3 and isinstance(run.body[-1], ast.Try)
    assert ast.unparse(run.body[-1].handlers[0].type) == "BaseException"
    main = ast.unparse(driver["main"])
    assert "requested_round" in main and "cpu_coordinated" in main
    prepare = ast.unparse(driver["prepare"])
    assert "retained_failure_artifacts" in prepare and "freeze_prerequisites" in prepare
    assert "kind='cells.normal_ecm_calcium_domain04_prepared@1'" in prepare
    orchestrator = module("calcium04_driver", ROOT / q["runner"])
    groups, required = orchestrator.plan(ROOT, protocol)
    assert len({i for nodes in groups.values() for i in nodes}) == 34
    assert (
        sum(len(r["positive"]) + len(r["raw"]) + len(r["raw_domain"]) for r in required.values())
        == 22
    )
    metadata = json.loads((WORK / (PREFIX + "_reporting_metadata_check_03.json")).read_text())
    assert metadata["status"] == "passed_synthetic_metadata_only"
    assert metadata["driver_sha256"] == sha(ROOT / q["runner"])
    assert metadata["producer_sha256"]["new"] == sha(ROOT / ("tests/unit/test_" + PREFIX + ".py"))
    for arguments in (["check"], ["format", "--check"]):
        checked = subprocess.run(
            ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *arguments, *paths],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert checked.returncode == 0, (arguments, checked.stdout, checked.stderr)
    return dict(
        kind="cells.calcium_domain04_static_witness@1",
        status="passed_static_only",
        compile_without_import="passed",
        global_names="passed",
        ruff_check="passed",
        ruff_format="passed",
        owned_files=len(q["owned"]),
        protected_files=len(q["protected_sha256"]),
        compiled_python_files=len(paths),
        reference_closure_modules=len(refs),
        scientific_import_closure_modules=len(imports),
        explicit_package_initializers=[p for p in imports if p.endswith("/__init__.py")],
        legacy_science_and_fixed_budgets_unchanged=True,
        source_classification_AST_proof=proof,
        actual_metadata_producer_and_reader_check=metadata,
        exact_full_roster_ids=34,
        group_counts={k: len(v) for k, v in groups.items()},
        complete_raw_artifacts_hashed_without_array_evaluation=True,
        retained_failure_artifacts=len(q["retained_failure_artifacts"]),
        planned_fresh_reference_forms=442,
        planned_native_captures=22,
        original_campaign_still_failed=True,
        retained_or_new_qualification_passes=0,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    result = audit()
    args = parser.parse_args()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                sha256=sha(args.output),
                compiled=result["compiled_python_files"],
            )
        )
    )
