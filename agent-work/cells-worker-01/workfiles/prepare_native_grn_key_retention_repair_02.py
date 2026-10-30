# ruff: noqa: E501 -- exact boundary and review metadata.
"""Bind native key spellings, constructor evidence guards and three side pins."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
OLD = Path("/mnt/workspaces/Cells/betse-normal-grn-prepared-20261030-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse(path):
    return ast.parse(Path(path).read_text())


def dump(node):
    return ast.dump(node, include_attributes=False)


class UndoKeys(ast.NodeTransformer):
    def visit_Constant(self, node):
        values = {
            "Km decay activators": "decay Km activators",
            "n decay activators": "decay n activators",
            "Km decay inhibitors": "decay Km inhibitors",
            "n decay inhibitors": "decay n inhibitors",
        }
        if isinstance(node.value, str) and node.value in values:
            return ast.copy_location(ast.Constant(value=values[node.value]), node)
        return node

    def visit_Subscript(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "gad":
            for label in ("Km ", "n "):
                expected = ast.parse(repr(label) + " + prefix + sign", mode="eval").body
                if dump(node.slice) == dump(expected):
                    node.slice = ast.parse("prefix + " + repr(label) + " + sign", mode="eval").body
                    return node
        return self.generic_visit(node)


for relative, function in (
    ("src/cells/processes/betse_normal_grn_source.py", "validate"),
    ("validation/betse/betse_normal_grn_join_reference.py", "hill"),
):
    tree = parse(ROOT / relative)
    index = next(
        i
        for i, node in enumerate(tree.body)
        if isinstance(node, ast.FunctionDef) and node.name == function
    )
    tree.body[index] = UndoKeys().visit(tree.body[index])
    assert dump(tree) == dump(parse(OLD / "source" / relative)), relative
relative = "validation/betse/betse_normal_grn_join_fixtures.py"
assert dump(UndoKeys().visit(parse(ROOT / relative))) == dump(parse(OLD / "source" / relative))
test = "tests/unit/test_betse_normal_grn_join.py"


class UndoRetention(ast.NodeTransformer):
    def visit_Try(self, node):
        if any(
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and "unexpected" in child.value
            and "constructor" in child.value
            for handler in node.handlers
            for child in ast.walk(handler)
        ):
            assert len(node.handlers) == 1 and isinstance(node.handlers[0].body[-1], ast.Raise)
            return node.body
        return self.generic_visit(node)


assert dump(UndoRetention().visit(parse(ROOT / test))) == dump(parse(OLD / "source" / test))
spec = importlib.util.spec_from_file_location(
    "GRN_native_key_schema", WORK / "betse_normal_grn_key_schema_audit.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
keys = module.audit()
wpath = WORK / "betse_normal_grn_key_schema_witness_02.json"
with wpath.open("x") as stream:
    json.dump(keys, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
qpath = WORK / "betse_normal_grn_join_workqueue.json"
q = json.loads(qpath.read_text())
trans = json.loads((WORK / "betse_normal_transporter_join_workqueue.json").read_text())
refresh = {
    path: dict(old_sha256=old, new_sha256=trans["owned_sha256"][path])
    for path, old in q["protected_sha256"].items()
    if path in trans["owned_sha256"] and old != trans["owned_sha256"][path]
}
assert set(refresh) == {
    "tests/unit/test_betse_normal_transporter_join.py",
    "validation/betse/betse_normal_transporter_join_protocol.json",
    "validation/betse/betse_normal_transporter_join_source_map.json",
}
for path, row in refresh.items():
    assert sha(ROOT / path) == row["new_sha256"], path
    assert path not in q["scientific_import_closure"], path
    q["protected_sha256"][path] = row["new_sha256"]
for path, digest in q["protected_sha256"].items():
    assert sha(ROOT / path) == digest, path
unchanged = {
    path: sha(ROOT / path)
    for path in q["owned"]
    if path
    not in {
        "src/cells/processes/betse_normal_grn_source.py",
        test,
        "validation/betse/betse_normal_grn_join_reference.py",
        "validation/betse/betse_normal_grn_join_fixtures.py",
        "validation/betse/betse_normal_grn_join_protocol.json",
        "validation/betse/betse_normal_grn_join_source_map.json",
    }
}
assert len(unchanged) == 4
for path, digest in unchanged.items():
    assert digest == sha(OLD / "source" / path) == q["owned_sha256"][path], path
review = Path("/mnt/workspaces/Cells/betse-normal-grn-preflight-20261030-01/REVIEW.json")
assert sha(review) == "d12086bd12fc34ee0f1c87fff4f2b597cd954f5eab3409e0dbb976dc9886b223"
evidence = q["binding_evidence"]
evidence.update(
    held_grn01_inputs=dict(path=str(OLD / "inputs.json"), sha256=sha(OLD / "inputs.json")),
    held_grn01_preflight=dict(path=str(review), sha256=sha(review)),
    native_key_schema_witness02=dict(path=str(wpath), sha256=sha(wpath)),
    authorized_nonimported_transporter03_pin_source=dict(
        path=trans["prepared_inputs"], sha256=trans["prepared_inputs_sha256"]
    ),
)
repair = dict(
    authority="Chief requested native spelling/retention correction and exact3 non-imported transporter side-pin refresh; held01 never ran numerically",
    native_keys="growth/decay x activator/inhibitor list/zone/Km/n:16 actual original lookups audited; correct decay keys are Km decay ... and n decay ...",
    inverse_AST="Reverse key-only validator/reference/fixture changes and unwrap exactly2 unexpected-constructor archive guards: remaining AST equals01",
    source_equations_and_order_unchanged=True,
    scientific_bodies=41,
    unchanged_outer_helpers=5,
    unchanged_scientific_files=unchanged,
    reference_equations_parameters_budgets_unchanged=True,
    unexpected_valid_seed_retention="Raw-runtime and dependency baseline seeds now archive exceptions/partial owner/buffers before re-raising; intended failure paths remain distinct",
    schema_witness=evidence["native_key_schema_witness02"],
    controlled_side_pin_refresh=refresh,
    side_pin_refresh_count=3,
    unchanged_other_protected_files=232,
    all3_excluded_from_scientific_import_closure=True,
    pending_transporter_import_dependency=False,
    numerical_runs=0,
)
for relative in (
    "validation/betse/betse_normal_grn_join_protocol.json",
    "validation/betse/betse_normal_grn_join_source_map.json",
):
    path = ROOT / relative
    data = json.loads(path.read_text())
    if relative.endswith("protocol.json"):
        assert (
            data["acceptance"] == json.loads((OLD / "source" / relative).read_text())["acceptance"]
        )
        data["binding_evidence"] = evidence
    data["native_key_retention_repair02"] = repair
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
q["previous_prepared_inputs01"] = dict(
    path=q.pop("prepared_inputs"), sha256=q.pop("prepared_inputs_sha256")
)
q["previous_static_receipt01"] = dict(
    path=q.pop("static_receipt"), sha256=q.pop("static_receipt_sha256")
)
q.update(
    prepared_inputs="/mnt/workspaces/Cells/betse-normal-grn-prepared-20261030-02/inputs.json",
    native_key_retention_repair02=repair,
    status="keys_and_retention02_ready_for_static_audit_no_launch",
)
q["workfiles"].extend(
    [
        str((WORK / name).relative_to(ROOT))
        for name in (
            "betse_normal_grn_key_schema_audit.py",
            "prepare_native_grn_key_retention_repair_02.py",
            "betse_normal_grn_key_schema_witness_02.json",
        )
    ]
)
qpath.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(
    json.dumps(
        dict(
            changed_scientific_files=6,
            unchanged_scientific_files=4,
            controlled_nonimported_side_pins=3,
            native_regulator_keys=16,
            numerical_runs=0,
        )
    )
)
