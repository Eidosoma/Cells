"""Final source-only audits; no test collection, scientific import or execution."""

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


def reference_closure(start):
    pending, closed = [start], {}
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    while pending:
        rel = pending.pop()
        if rel in closed:
            continue
        path = ROOT / rel
        tree = ast.parse(path.read_text())
        closed[rel] = sha(path)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [value.name for value in node.names]
            if isinstance(node, ast.ImportFrom):
                assert not node.level
                names = [node.module] + [node.module + "." + value.name for value in node.names]
            for name in names:
                assert name.split(".")[0] not in blocked, (rel, name)
                candidate = name.replace(".", "/") + ".py"
                if name.startswith("validation.") and (ROOT / candidate).is_file():
                    pending.append(candidate)
    return closed


queue_path = WORK / "betse_normal_molecule_join_workqueue.json"
q = json.loads(queue_path.read_text())
q["workfiles"] = [
    q["runner"],
    q["notes"],
    *[
        "agent-work/cells-worker-01/workfiles/" + name
        for name in (
            "prepare_native_molecule_source.py",
            "prepare_native_molecule_join.py",
            "prepare_native_molecule_capture.py",
            "prepare_native_molecule_package.py",
            "betse_normal_molecule_join_ast_audit.py",
            "betse_normal_molecule_join_static_audit.py",
            "betse_normal_molecule_adapter_attribute_audit.py",
            "prepare_native_molecule_adapter_repair_02.py",
            "betse_normal_molecule_adapter_attributes_before_02_complete.json",
            "betse_normal_molecule_adapter_attributes_after_02.json",
        )
    ],
]
paths = [rel for rel in q["owned"] + q["workfiles"] if rel.endswith(".py")]
missing = {}
for rel in paths:
    source = (ROOT / rel).read_text()
    compile(source, rel, "exec")
    table = symtable.symtable(source, rel, "exec")
    known = set(table.get_identifiers()) | set(dir(builtins)) | {"__name__", "__file__"}

    def unresolved(t, known=known):
        names = {
            symbol.get_name()
            for symbol in t.get_symbols()
            if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in known
        }
        for child in t.get_children():
            names |= unresolved(child)
        return names

    names = unresolved(table)
    if names:
        missing[rel] = sorted(names)
assert not missing, missing
spec = importlib.util.spec_from_file_location(
    "molecule_source_AST_audit", WORK / "betse_normal_molecule_join_ast_audit.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
adapter_spec = importlib.util.spec_from_file_location(
    "molecule_adapter_attribute_audit", WORK / "betse_normal_molecule_adapter_attribute_audit.py"
)
adapter_module = importlib.util.module_from_spec(adapter_spec)
adapter_spec.loader.exec_module(adapter_module)
adapter_proof = adapter_module.audit()
assert adapter_proof["missing"] == {"production": {}, "native": {}}
saved_adapter = json.loads(
    (WORK / "betse_normal_molecule_adapter_attributes_after_02.json").read_text()
)
assert adapter_proof == saved_adapter
mapping = json.loads(
    (ROOT / "validation/betse/betse_normal_molecule_join_source_map.json").read_text()
)
for name, row in proof["literal_numeric_bodies"].items():
    assert (
        mapping["literal_numeric_bodies"][name]["numeric_AST_sha256"] == row["numeric_AST_sha256"]
    ), name
assert len(proof["literal_numeric_bodies"]) == 22
for rel, digest in q["protected_sha256"].items():
    assert sha(ROOT / rel) == digest, rel
for row in q["binding_evidence"].values():
    assert sha(row["path"]) == row["sha256"], row["path"]
protocol = json.loads(
    (ROOT / "validation/betse/betse_normal_molecule_join_protocol.json").read_text()
)
for rel, digest in protocol["acceptance"]["inherited_budget_source_sha256"].items():
    assert sha(ROOT / rel) == digest, rel
fixture = ast.parse((ROOT / "validation/betse/betse_normal_molecule_join_fixtures.py").read_text())
constants = {
    target.id: ast.literal_eval(node.value)
    for node in fixture.body
    if isinstance(node, ast.Assign)
    for target in node.targets
    if isinstance(target, ast.Name)
    and target.id in {"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES"}
}
assert tuple(
    len(constants[name]) for name in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
) == (15, 3, 2, 4)
assert (
    protocol["planned"]["checks"] == 21
    and protocol["planned"]["fresh_Decimal_reference_forms"] == 90
)
drivers = {
    node.name: node
    for node in ast.parse((ROOT / q["runner"]).read_text()).body
    if isinstance(node, ast.FunctionDef)
}
accepted = {
    node.name: node
    for node in ast.parse((WORK / "betse_normal_network_join_checks_02.py").read_text()).body
    if isinstance(node, ast.FunctionDef)
}
assert ast.dump(drivers["verify_pytest_ids"], include_attributes=False) == ast.dump(
    accepted["verify_pytest_ids"], include_attributes=False
)
run = drivers["run"]
start = next(
    index
    for index, node in enumerate(run.body)
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
closure = reference_closure("validation/betse/betse_normal_molecule_join_reference.py")
q.update(
    owned_sha256={rel: sha(ROOT / rel) for rel in q["owned"]},
    reference_closure=closure,
    status="static_audits_passed_ready_to_freeze_no_molecule_numerics",
    static_checks=dict(
        compile_without_import="passed",
        global_name_resolution="passed",
        unresolved=missing,
        ruff_check="passed",
        ruff_format="passed",
        literal_numeric_AST_bodies=22,
        exception_class_ASTs=3,
        unchanged_outer_helper_ASTs=5,
        independent_native_observational_AST_builder="passed; stdlib transformation only",
        scientific_AST_executions=0,
        reference_closure_stdlib_only=True,
        exact_unique_pytest_ID_validator_AST_unchanged=True,
        post_output_terminal_failure_capture_AST="passed",
        planned_fixture_and_budget_pins="passed",
        reachable_adapter_attributes=42,
        missing_adapter_attributes=adapter_proof["missing"],
        native_literal_ignore_ECM_pump_default=True,
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
            reference_closure_files=len(closure),
            numeric_AST_bodies=22,
            scientific_imports=0,
            pytest_collection_runs=0,
            numerical_runs=0,
        )
    )
)
