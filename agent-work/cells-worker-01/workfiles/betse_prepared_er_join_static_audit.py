"""AST, JSON, hash and lint checks only; never import the scientific modules."""

import ast
import builtins
import copy
import hashlib
import json
import subprocess
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def functions(path):
    return {
        node.name: node
        for node in ast.parse(Path(path).read_text()).body
        if isinstance(node, ast.FunctionDef)
    }


def reference_closure(starts):
    pending, seen = list(starts), {}
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    while pending:
        rel = pending.pop()
        if rel in seen:
            continue
        path = ROOT / rel
        tree = ast.parse(path.read_text())
        seen[rel] = sha(path)
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            if isinstance(node, ast.ImportFrom):
                assert not node.level, (rel, node.lineno)
                names = [node.module] + [node.module + "." + item.name for item in node.names]
            for name in names:
                assert name.split(".")[0] not in blocked, (rel, name)
                if name.startswith("validation."):
                    candidate = name.replace(".", "/") + ".py"
                    if (ROOT / candidate).is_file():
                        pending.append(candidate)
    return seen


queue_path = WORK / "betse_prepared_er_join_workqueue.json"
queue = json.loads(queue_path.read_text())
queue["workfiles"] = [
    queue["runner"],
    queue["notes"],
    "agent-work/cells-worker-01/workfiles/prepare_prepared_er_native.py",
    "agent-work/cells-worker-01/workfiles/prepare_prepared_er_package.py",
    "agent-work/cells-worker-01/workfiles/betse_prepared_er_join_static_audit.py",
    "agent-work/cells-worker-01/workfiles/betse_prepared_er_array_boundary_saved_witness.py",
    "agent-work/cells-worker-01/workfiles/betse_prepared_er_array_boundary_saved_witness_01.json",
]
paths = [rel for rel in queue["owned"] + queue["workfiles"] if rel.endswith(".py")]
missing = {}
for rel in paths:
    text = (ROOT / rel).read_text()
    compile(text, rel, "exec")
    table = symtable.symtable(text, rel, "exec")
    known = set(table.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__"}
    unresolved = set()

    def visit(t, known=known, unresolved=unresolved):
        for symbol in t.get_symbols():
            if symbol.is_referenced() and symbol.is_global() and symbol.get_name() not in known:
                unresolved.add(symbol.get_name())
        for child in t.get_children():
            visit(child)

    visit(table)
    if unresolved:
        missing[rel] = sorted(unresolved)
assert not missing, missing
for rel, digest in queue["protected_sha256"].items():
    assert sha(ROOT / rel) == digest, rel
for row in queue["binding_evidence"].values():
    assert sha(row["path"]) == row["sha256"], row["path"]
original = functions(ROOT / "validation/betse/betse_normal_er_join_native.py")["evaluate"]
captured = copy.deepcopy(
    functions(ROOT / "validation/betse/betse_prepared_er_join_native.py")["_whole_join"]
)
captured.name = "evaluate"
changes = []
for node in ast.walk(captured):
    if (
        isinstance(node, ast.Assign)
        and ast.unparse(node.targets[0]) == "er_state_cache"
        and ast.unparse(node.value)
        == "restore_supplied_fields(inputs['prepared_er_input']['fields'])"
    ):
        node.value = ast.Constant(value=None)
        changes.append("initial_supplied_state")
    if (
        isinstance(node, ast.keyword)
        and node.arg == "kind"
        and isinstance(node.value, ast.Constant)
        and node.value.value == "cells.native_prepared_er_join_capture@1"
    ):
        node.value = ast.Constant(value="cells.native_normal_er_join_capture@1")
        changes.append("capture_label")
assert sorted(changes) == ["capture_label", "initial_supplied_state"]
assert ast.dump(original, include_attributes=False) == ast.dump(captured, include_attributes=False)
driver = functions(ROOT / queue["runner"])
network_driver = functions(
    ROOT / "agent-work/cells-worker-01/workfiles/betse_normal_network_join_checks_02.py"
)
assert ast.dump(driver["verify_pytest_ids"], include_attributes=False) == ast.dump(
    network_driver["verify_pytest_ids"], include_attributes=False
)
run = driver["run"]
index = next(
    i
    for i, node in enumerate(run.body)
    if isinstance(node, ast.Expr) and ast.unparse(node) == "target.mkdir(exist_ok=False)"
)
assert (
    isinstance(run.body[index + 1], ast.Assign)
    and isinstance(run.body[index + 2], ast.Try)
    and len(run.body) == index + 3
)
assert ast.unparse(run.body[-1].handlers[0].type) == "BaseException"
fixture_tree = ast.parse((ROOT / "validation/betse/betse_prepared_er_join_fixtures.py").read_text())
constants = {
    target.id: ast.literal_eval(node.value)
    for node in fixture_tree.body
    if isinstance(node, ast.Assign)
    for target in node.targets
    if isinstance(target, ast.Name)
    and target.id in {"CASES", "SIGN_CASES", "REFINEMENT_CASES", "REFUSALS", "SUBDIVISIONS"}
}
assert tuple(
    map(
        len,
        (
            constants["CASES"],
            constants["SIGN_CASES"],
            constants["REFINEMENT_CASES"],
            constants["REFUSALS"],
        ),
    )
) == (13, 2, 2, 6)
assert constants["SUBDIVISIONS"] == (1, 2, 4)
protocol = json.loads((ROOT / "validation/betse/betse_prepared_er_join_protocol.json").read_text())
assert protocol["planned"]["checks"] == 23 and protocol["planned"]["actual_pre_ER_points"] == 83
for rel, digest in protocol["acceptance"]["inherited_budget_source_sha256"].items():
    assert sha(ROOT / rel) == digest, rel
closure = reference_closure(
    [
        "validation/betse/betse_prepared_er_join_reference.py",
        "validation/betse/betse_normal_er_join_reference.py",
    ]
)
for args in (["check"], ["format", "--check"]):
    result = subprocess.run(
        ["/mnt/workspaces/Cells/venv-cpu/bin/ruff", *args, *paths],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, (args, result.stdout, result.stderr)
queue.update(
    owned_sha256={rel: sha(ROOT / rel) for rel in queue["owned"]},
    reference_closure=closure,
    status="static_audits_passed_ready_to_freeze_no_ER_numerics",
    static_checks=dict(
        compile_without_import="passed",
        global_names="passed",
        unresolved=missing,
        ruff_check="passed",
        ruff_format="passed",
        reference_closure_stdlib_only=True,
        native_capture_inverse_AST="passed",
        exact_pytest_ID_validator_AST_unchanged=True,
        post_output_failure_capture_AST="passed",
        planned_schema_and_source_pins="passed",
        scientific_AST_executions=0,
    ),
)
queue_path.write_text(json.dumps(queue, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(
    json.dumps(
        dict(
            status=queue["status"],
            Python_files=len(paths),
            owned=len(queue["owned"]),
            protected=len(queue["protected_sha256"]),
            reference_closure_files=len(closure),
            scientific_imports=0,
            pytest_collection_runs=0,
            numerical_runs=0,
        )
    )
)
