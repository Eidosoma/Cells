"""Prove report-key-only successor and audit emitted keys without running tests."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_catalog_join"
FROZEN = Path("/mnt/workspaces/Cells/betse-normal-ecm-catalog-join-prepared-20261031-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def audit():
    inputs = json.loads((FROZEN / "inputs.json").read_text())
    old = WORK / f"{PREFIX}_checks.py"
    new = WORK / f"{PREFIX}_checks_02.py"
    assert sha(old) == sha(FROZEN / "driver.py") == inputs["driver_sha256"]
    old_tree = ast.parse(old.read_text())
    new_tree = ast.parse(new.read_text())
    compile(new.read_text(), str(new), "exec")
    count = 0

    class UndoReportKey(ast.NodeTransformer):
        def visit_IfExp(self, node):
            nonlocal count
            if ast.unparse(node) == "'channel' if name == 'channels' else name":
                count += 1
                return ast.copy_location(ast.Name(id="name", ctx=ast.Load()), node)
            return self.generic_visit(node)

    inverse = UndoReportKey().visit(copy.deepcopy(new_tree))
    assert count == 1 and digest(inverse) == digest(old_tree)
    test = ast.parse((ROOT / "tests/unit" / f"test_{PREFIX}.py").read_text())
    history = next(
        n
        for n in test.body
        if isinstance(n, ast.FunctionDef) and n.name == "test_ecm_catalog_history"
    )
    dictionaries = [
        n
        for n in ast.walk(history)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "dict"
    ]
    emitted = next(
        {k.arg for k in n.keywords}
        for n in dictionaries
        if any(k.arg == "complete_calls" for k in n.keywords)
    )
    modes = ("material", "calcium", "channels", "network", "field")
    expected = {
        mode: "conditional_" + ("channel" if mode == "channels" else mode) + "_reference_forms"
        for mode in modes
    }
    assert set(expected.values()) <= emitted
    assert "conditional_channels_reference_forms" not in emitted
    assert "conditional_channel_reference_forms" in emitted
    for p, h in inputs["owned_sha256"].items():
        assert sha(ROOT / p) == h, p
    return dict(
        kind="cells.ecm_catalog_reporting_only_successor02@1",
        frozen01_inputs_sha256=sha(FROZEN / "inputs.json"),
        old_driver_sha256=sha(old),
        successor_driver_sha256=sha(new),
        original_driver_and_frozen01_unchanged=True,
        reporting_key_inverse_AST_exact=True,
        changed_AST_expressions=1,
        original_report_keys=sorted(emitted),
        corrected_mode_to_report_key=expected,
        all_scientific_owned_files_unchanged=True,
        scientific_equations_order_or_budgets_changed=False,
        awaiting_Chief_final_static_review_before_freeze02=True,
        scientific_imports=0,
        fixture_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / f"{PREFIX}_reporting_witness_02.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
