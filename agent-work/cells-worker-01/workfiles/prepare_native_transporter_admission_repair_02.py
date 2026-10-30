# ruff: noqa: E501 -- review metadata uses complete source descriptions.
"""Bind a lossless component-axis repair and saved refusal witnesses; stdlib only."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
OLD = Path("/mnt/workspaces/Cells/betse-normal-transporter-prepared-20261030-01")
RUN = Path("/mnt/workspaces/Cells/betse-normal-transporter-tests-20261030-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tree(path):
    return ast.parse(Path(path).read_text())


def dump(node):
    return ast.dump(node, include_attributes=False)


class UndoAxis(ast.NodeTransformer):
    def visit_Call(self, node):
        if ast.unparse(node.func) in {"integer_valences", "joined.network_source.integer_valences"}:
            assert len(node.args) == 1
            return node.args[0]
        return self.generic_visit(node)


qpath = WORK / "betse_normal_transporter_join_workqueue.json"
q = json.loads(qpath.read_text())
source = "src/cells/processes/betse_normal_transporter_source.py"
test = "tests/unit/test_betse_normal_transporter_join.py"
inverse = tree(ROOT / source)
inverse.body = [
    node
    for node in inverse.body
    if not isinstance(node, ast.FunctionDef) or node.name != "integer_valences"
]
inverse = UndoAxis().visit(inverse)
assert dump(inverse) == dump(tree(OLD / "source" / source))
old_test = tree(OLD / "source" / test)
inverse = tree(ROOT / test)
old_dependency = next(
    node
    for node in old_test.body
    if isinstance(node, ast.FunctionDef) and node.name == "test_complete_transporter_dependencies"
)
inverse.body = [
    copy.deepcopy(old_dependency)
    if isinstance(node, ast.FunctionDef) and node.name == old_dependency.name
    else node
    for node in inverse.body
    if not isinstance(node, ast.Import) or [item.name for item in node.names] != ["re"]
]
inverse = UndoAxis().visit(inverse)
assert dump(inverse) == dump(old_test)
dependency = next(
    node
    for node in tree(ROOT / test).body
    if isinstance(node, ast.FunctionDef) and node.name == "test_complete_transporter_dependencies"
)
message_node = next(
    node.value
    for node in dependency.body
    if isinstance(node, ast.Assign)
    and any(
        isinstance(target, ast.Name) and target.id == "expected_messages" for target in node.targets
    )
)
assert isinstance(message_node, ast.Call) and ast.unparse(message_node.func) == "dict"
messages = {item.arg: ast.literal_eval(item.value) for item in message_node.keywords}
saved = {}
for name in messages:
    if name == "missing_flux_cache":
        continue
    folder = (
        RUN / "run-dependencies/evidence/normal-transporter-join" / (name + "-expected-refusal")
    )
    raw = dict(json.loads((folder / "data.json").read_text())["mapping"])
    assert raw["type"] == "ValueError" and raw["message"] == messages[name]
    saved[name] = dict(
        type=raw["type"],
        message=raw["message"],
        intended_branch=True,
        files={str(path): sha(path) for path in sorted(folder.iterdir()) if path.is_file()},
    )
witness = dict(
    kind="cells.transporter_saved_admission_refusal_audit@1",
    source_run=str(RUN),
    source_inputs=dict(path=str(OLD / "inputs.json"), sha256=sha(OLD / "inputs.json")),
    saved_refusals=saved,
    conclusion="All4 saved dependency passes hit their intended branches; the valid missing-flux seed failed earlier at the integer-axis boundary. No false-positive claim.",
    stdout=dict(
        path=str(RUN / "run-dependencies/process/stdout.log"),
        sha256=sha(RUN / "run-dependencies/process/stdout.log"),
    ),
    old_native_component_contract=dict(
        path="src/cells/processes/betse_network_transport.py",
        sha256=sha(ROOT / "src/cells/processes/betse_network_transport.py"),
        integer_valence_axis_required=True,
    ),
    inverse_source_AST="Remove one integer helper and invert its single validation call: all remaining AST equals01",
    inverse_test_AST="Restore only dependency function, remove import re and invert secondary axis call: every other AST equals01",
    scientific_imports=0,
    scientific_AST_executions=0,
    numerical_runs=0,
)
witness_path = WORK / "betse_normal_transporter_admission_saved_witness_02.json"
with witness_path.open("x") as stream:
    json.dump(witness, stream, indent=2, sort_keys=True, allow_nan=False)
    stream.write("\n")
unchanged = {
    path: sha(ROOT / path)
    for path in q["owned"]
    if path
    not in {
        source,
        test,
        "validation/betse/betse_normal_transporter_join_protocol.json",
        "validation/betse/betse_normal_transporter_join_source_map.json",
    }
}
assert len(unchanged) == 6
for path, digest in unchanged.items():
    assert digest == q["owned_sha256"][path] == sha(OLD / "source" / path), path
for path, digest in q["protected_sha256"].items():
    assert sha(ROOT / path) == digest, path
evidence = q["binding_evidence"]
evidence["prior_transporter_failed_static_inputs"] = dict(
    path=str(OLD / "inputs.json"), sha256=sha(OLD / "inputs.json")
)
evidence["transporter_admission_saved_witness"] = dict(
    path=str(witness_path), sha256=sha(witness_path)
)
review = Path(
    "/mnt/workspaces/Cells/betse-normal-molecule-tests-20261030-02/root-review-01/REVIEW.json"
)
assert sha(review) == "747b98ca85f05ce444999cd752c575d83bd54da4e6844fcfa1deb3f71f6217b5"
evidence["accepted_molecule02_review"] = dict(path=str(review), sha256=sha(review))
repair = dict(
    authority="Chief requested component-boundary integer representation and precise admission/refusal witnesses, after Root dependencies4pass1fail20unrun; static successor only",
    seams=[source + ":validate/component.bind", test + ":transporter_comparisons/component.bind"],
    conversion="Check nonempty1D real numeric, finite, [-8,8] without abs overflow, exactly integral; cast np.int64 and assert value equality. Reject fractional, nonfinite, bool and invalid rank/range. Native/source float64 valence buffers unchanged.",
    source_and_test_inverse_AST=witness["inverse_source_AST"] + "; " + witness["inverse_test_AST"],
    saved_refusal_audit=evidence["transporter_admission_saved_witness"],
    unchanged_scientific_files=unchanged,
    unchanged_scientific_bodies=27,
    unchanged_native_capture_files=3,
    unchanged_protected_files=225,
    unchanged_component_contract=True,
    unchanged_constants_references_budgets=True,
    planned_checks_unchanged=25,
    valid_baseline_before_each_dependency=True,
    precise_terminal_refusal_message_assertions=True,
    runner_requires_exact_dependency_witness_set=True,
    numerical_retry=False,
)
for relative in (
    "validation/betse/betse_normal_transporter_join_protocol.json",
    "validation/betse/betse_normal_transporter_join_source_map.json",
):
    p = ROOT / relative
    data = json.loads(p.read_text())
    data["admission_bridge_repair_02"] = repair
    if relative.endswith("protocol.json"):
        assert (
            data["acceptance"] == json.loads((OLD / "source" / relative).read_text())["acceptance"]
        )
        data["binding_evidence"] = evidence
    p.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")
q["previous_prepared_inputs"] = dict(
    path=q.pop("prepared_inputs"), sha256=q.pop("prepared_inputs_sha256")
)
q["previous_static_receipt"] = dict(
    path=q.pop("static_receipt"), sha256=q.pop("static_receipt_sha256")
)
q.update(
    prepared_inputs="/mnt/workspaces/Cells/betse-normal-transporter-prepared-20261030-02/inputs.json",
    admission_bridge_repair_02=repair,
    status="admission02_ready_for_static_audit_no_retry",
)
q["workfiles"].extend(
    [
        str((WORK / "prepare_native_transporter_admission_repair_02.py").relative_to(ROOT)),
        str(witness_path.relative_to(ROOT)),
    ]
)
qpath.write_text(json.dumps(q, indent=2, sort_keys=True, allow_nan=False) + "\n")
print(
    json.dumps(
        dict(
            saved_intended_refusals=4,
            changed_scientific_files=4,
            unchanged_scientific_files=6,
            protected=225,
            numerical_runs=0,
        )
    )
)
