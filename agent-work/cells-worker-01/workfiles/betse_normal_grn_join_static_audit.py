"""Final original-source, ownership and runner audits; no scientific execution."""

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
PREFIX = "betse_normal_grn_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def closure(start, *, reference):
    pending, closed = [start], {}
    while pending:
        relative = pending.pop()
        if relative in closed:
            continue
        path = ROOT / relative
        tree = ast.parse(path.read_text())
        closed[relative] = sha(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level
                names = [node.module] + [node.module + "." + item.name for item in node.names]
            else:
                continue
            for name in names:
                if reference:
                    assert name.split(".")[0] not in {"cells", "betse", "numpy", "jax", "jaxlib"}, (
                        relative,
                        name,
                    )
                assert "betse_normal_transporter" not in name, (relative, name)
                candidates = [
                    name.replace(".", "/") + ".py",
                    "src/" + name.replace(".", "/") + ".py",
                ]
                for candidate in candidates:
                    if (
                        name.startswith(("cells.", "validation.", "tests."))
                        and (ROOT / candidate).is_file()
                    ):
                        pending.append(candidate)
    return closed


def audit():
    queue_path = WORK / (PREFIX + "_workqueue.json")
    q = json.loads(queue_path.read_text())
    paths = [name for name in q["owned"] + q["workfiles"] if name.endswith(".py")]
    missing = {}
    for relative in paths:
        text = (ROOT / relative).read_text()
        compile(text, relative, "exec")
        table = symtable.symtable(text, relative, "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__name__", "__file__"}

        def unresolved(scope, known=known):
            result = {
                symbol.get_name()
                for symbol in scope.get_symbols()
                if symbol.is_global() and symbol.is_referenced() and symbol.get_name() not in known
            }
            for child in scope.get_children():
                result |= unresolved(child)
            return result

        if values := unresolved(table):
            missing[relative] = sorted(values)
    assert not missing, missing
    spec = importlib.util.spec_from_file_location(
        "grn_AST_audit", WORK / (PREFIX + "_ast_audit.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    proof = module.audit()
    key_spec = importlib.util.spec_from_file_location(
        "native_GRN_key_schema", WORK / "betse_normal_grn_key_schema_audit.py"
    )
    key_module = importlib.util.module_from_spec(key_spec)
    key_spec.loader.exec_module(key_module)
    key_proof = key_module.audit()
    assert key_proof == json.loads(
        (WORK / "betse_normal_grn_key_schema_witness_02.json").read_text()
    )
    mapping = json.loads((ROOT / ("validation/betse/" + PREFIX + "_source_map.json")).read_text())
    assert mapping["literal_numeric_bodies"] == proof["literal_numeric_bodies"]
    assert (
        proof["literal_scientific_body_count"] == 41 and len(proof["unchanged_outer_helpers"]) == 5
    )
    assert proof["source_default_hydration_audit"]["required_runtime_attributes"] == 42
    assert proof["source_default_hydration_audit"]["missing_runtime_attributes"] == {}
    assert len(q["protected_sha256"]) == 235
    for relative, digest in q["protected_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    for row in q["binding_evidence"].values():
        assert sha(row["path"]) == row["sha256"], row["path"]
    protocol = json.loads((ROOT / ("validation/betse/" + PREFIX + "_protocol.json")).read_text())
    assert (
        protocol["planned"]["checks"] == 19
        and protocol["planned"]["fresh_Decimal_reference_forms"] == 80
    )
    assert len(protocol["native_source"]["source_sha256"]) == 21
    assert mapping["source_sha256"] == protocol["native_source"]["source_sha256"]
    for relative, digest in protocol["native_source"]["source_sha256"].items():
        assert sha(Path(protocol["native_source"]["checkout"]) / relative) == digest, relative
        assert (
            sha(Path(protocol["native_source"]["installed_package"]).parent / relative) == digest
        ), relative
    for relative, digest in protocol["acceptance"]["inherited_budget_source_sha256"].items():
        assert sha(ROOT / relative) == digest, relative
    fixture = ast.parse((ROOT / ("validation/betse/" + PREFIX + "_fixtures.py")).read_text())
    constants = {
        target.id: ast.literal_eval(node.value)
        for node in fixture.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id in {"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES"}
    }
    assert tuple(
        len(constants[name])
        for name in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
    ) == (10, 3, 4, 5)
    test = ast.parse((ROOT / "tests/unit/test_betse_normal_grn_join.py").read_text())
    tests = {node.name: node for node in test.body if isinstance(node, ast.FunctionDef)}
    assert {
        "test_genuine_grn_owner_and_conditional_reference",
        "test_genuine_grn_partial_failure",
        "test_complete_grn_dependencies",
    } <= tests.keys()
    assert "valid_binding, valid_parent = seed(inputs)" in ast.unparse(
        tests["test_complete_grn_dependencies"]
    )
    assert "while leaf.__cause__ is not None" in ast.unparse(
        tests["test_complete_grn_dependencies"]
    )
    seed_guards = []

    def guarded_seeds(node, guarded=False):
        if isinstance(node, ast.Try):
            has_archive = any(
                isinstance(child, ast.Call) and ast.unparse(child.func) == "archive_refusal"
                for handler in node.handlers
                for child in ast.walk(handler)
            )
            has_raise = any(
                isinstance(child, ast.Raise) and child.exc is None
                for handler in node.handlers
                for child in ast.walk(handler)
            )
            for child in node.body:
                guarded_seeds(child, guarded or (has_archive and has_raise))
            return
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "seed"
        ):
            seed_guards.append(guarded)
        for child in ast.iter_child_nodes(node):
            guarded_seeds(child, guarded)

    for name in ("test_genuine_grn_partial_failure", "test_complete_grn_dependencies"):
        guarded_seeds(tests[name])
    assert len(seed_guards) == 2 and all(seed_guards)
    runner = ast.parse((ROOT / q["runner"]).read_text())
    functions = {node.name: node for node in runner.body if isinstance(node, ast.FunctionDef)}
    previous = {
        node.name: node
        for node in ast.parse((WORK / "betse_normal_network_join_checks_02.py").read_text()).body
        if isinstance(node, ast.FunctionDef)
    }
    assert ast.dump(functions["verify_pytest_ids"], include_attributes=False) == ast.dump(
        previous["verify_pytest_ids"], include_attributes=False
    )
    run = functions["run"]
    start = next(
        i
        for i, node in enumerate(run.body)
        if isinstance(node, ast.Expr) and ast.unparse(node) == "target.mkdir(exist_ok=False)"
    )
    assert (
        isinstance(run.body[start + 1], ast.Assign)
        and isinstance(run.body[start + 2], ast.Try)
        and len(run.body) == start + 3
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
    refs = closure("validation/betse/" + PREFIX + "_reference.py", reference=True)
    imports = closure("tests/unit/test_betse_normal_grn_join.py", reference=False)
    assert not set(q["protected_but_not_imported_side_package_paths"]) & imports.keys()
    q.update(
        owned_sha256={name: sha(ROOT / name) for name in q["owned"]},
        reference_closure=refs,
        scientific_import_closure=imports,
        status="static_audits_passed_ready_to_freeze_no_grn_numerics",
        static_checks=dict(
            compile_without_import="passed",
            global_name_resolution="passed",
            unresolved=missing,
            ruff_check="passed",
            ruff_format="passed",
            literal_original_scientific_bodies=41,
            unchanged_outer_helpers=5,
            genuine_original_initialization_and_dispatch_guards=True,
            complete_public_field_bridge_AST=True,
            cold_reader_not_repeated_on_hot_restore=True,
            source_default_hydration_required_attributes=42,
            source_default_missing_attributes={},
            native_growth_decay_regulator_key_schema=16,
            symbolic_validator_reference_groups=8,
            unexpected_valid_constructor_guards=2,
            side_pin_refresh_exact_paths=list(
                q["native_key_retention_repair02"]["controlled_side_pin_refresh"]
            ),
            independent_reference_closure_stdlib=True,
            no_pending_transporter_import_dependency=True,
            exact_unique_pytest_ID_validator_AST_unchanged=True,
            post_output_terminal_failure_capture_AST="passed",
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
                owned=10,
                protected=235,
                scientific_bodies=41,
                reference_closure_files=len(refs),
                scientific_import_closure_files=len(imports),
                scientific_imports=0,
                pytest_collection_runs=0,
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    audit()
