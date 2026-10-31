"""Authenticate Chief-owned capture/test repairs as explicit new dependency pins."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_catalog_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def definitions(tree):
    return {n.name: n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}


def audit():
    cap = "validation/betse/betse_normal_ecm_calcium_join_native.py"
    fld = "tests/unit/test_betse_normal_ecm_field_join.py"
    prior_calcium = Path(
        "/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-prepared-20261031-01/source"
    )
    prior_field = Path(
        "/mnt/workspaces/Cells/betse-normal-ecm-field-join-prepared-20261031-01/source"
    )
    current = ast.parse((ROOT / cap).read_text())
    old = ast.parse((prior_calcium / cap).read_text())

    class UndoMap(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id == "arithmetic_names":
                node.id = "names"
            return node

    assert digest(UndoMap().visit(copy.deepcopy(current))) == digest(old)
    before = definitions(ast.parse((prior_field / fld).read_text()))
    after = definitions(ast.parse((ROOT / fld).read_text()))
    assert before.keys() == after.keys()
    changed = [name for name in before if digest(before[name]) != digest(after[name])]
    assert changed == ["test_normal_ecm_field_raw_partial"]
    code = ast.unparse(after[changed[0]])
    assert "len(completed) == 2 and actual['stage'] == 'network'" in code
    assert "material_overflow_qualified=False" in code
    return dict(
        kind="cells.ECM_catalog_explicit_dependency_refresh@1",
        authority=(
            "Chief directed water-owned test/capture-only repairs, original failed runs preserved"
        ),
        changes={
            cap: dict(
                old_sha256=sha(prior_calcium / cap),
                new_sha256=sha(ROOT / cap),
                observation_map_inverse_AST_exact=True,
                scientific_equations_or_order_changed=False,
            ),
            fld: dict(
                old_sha256=sha(prior_field / fld),
                new_sha256=sha(ROOT / fld),
                changed_functions=changed,
                actual_call3_network_refusal_after_two_completed_calls=True,
                material_overflow_credit=False,
                scientific_equations_or_order_changed=False,
            ),
        },
        no_old_inputs_or_receipts_refreshed=True,
        qualification_credit=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        numerical_runs=0,
        pytest_collection_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / f"{PREFIX}_dependency_witness_01.json").open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
