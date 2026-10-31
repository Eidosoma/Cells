# ruff: noqa: E501
"""Apply the authorized ECM handler repair to the held, unrun charged sibling."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
FROZEN = Path("/mnt/workspaces/Cells/betse-ecm-charged-grn-prepared-20261031-01")
ECM02 = Path("/mnt/workspaces/Cells/betse-ecm-grn-prepared-20261031-02")
JOIN = "src/cells/processes/betse_ecm_charged_grn_join.py"
TEST = "tests/unit/test_betse_ecm_charged_grn_join.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def dump(node):
    return ast.dump(node, include_attributes=False)


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


original = json.loads((FROZEN / "inputs.json").read_text())
for path, expected in original["owned_sha256"].items():
    assert sha(ROOT / path) == sha(FROZEN / "source" / path) == expected, path
ecm_text = (ROOT / "src/cells/processes/betse_ecm_grn_join.py").read_text()
helper = ast.get_source_segment(ecm_text, functions(ast.parse(ecm_text))["_failure_snapshot"])
old_join = (ROOT / JOIN).read_text()
join = old_join.replace(
    "\ndef initialize(binding):", "\n\n" + helper + "\n\n\ndef initialize(binding):", 1
)
join = join.replace(
    "                cache=source.cache(ctx),\n",
    "                **_failure_snapshot(ctx, None),\n",
    1,
)
needle = "            cache=None if ctx is None else source.cache(ctx),"
assert needle in join
join = join.replace(needle, "            **_failure_snapshot(ctx, parent.network_cache),", 1)
before, after = ast.parse(old_join), ast.parse(join)
inverse = copy.deepcopy(after)
inverse.body = [n for n in inverse.body if getattr(n, "name", None) != "_failure_snapshot"]
for name in ("initialize", "advance"):
    new_try = next(n for n in functions(inverse)[name].body if isinstance(n, ast.Try))
    old_try = next(n for n in functions(before)[name].body if isinstance(n, ast.Try))
    new_try.handlers = copy.deepcopy(old_try.handlers)
assert dump(inverse) == dump(before)
assert not any(
    isinstance(n, ast.Call) and ast.unparse(n.func) == "source.cache"
    for name in ("initialize", "advance")
    for item in functions(after)[name].body
    if isinstance(item, ast.Try)
    for handler in item.handlers
    for n in ast.walk(handler)
)
(ROOT / JOIN).write_text(join)

old_test = (ROOT / TEST).read_text()
needle = "        changed = joined._state(binding, parent.material, raw, parent.controls)\n"
assert needle in old_test
test = old_test.replace(
    needle,
    needle
    + """        archive(tmp_path, dependency+"-malformed-parent-before-call",
                dict(parent=changed,supplied_cache=raw,inputs=inputs))
""",
    1,
)
needle = "            joined.advance(binding, changed)\n"
assert needle in test
test = test.replace(
    needle,
    needle
    + """        archive(tmp_path, dependency+"-available-partial",dict(partial=caught.value.partial))
        if dependency in ("missing_cache","missing_ionic_cache","missing_balance_events","missing_default"):
            partial=caught.value.partial
            assert partial["cache"] is None
            assert partial["available_context"]["owner_available"] is False
            assert partial["available_context"]["core_available"] is False
            assert partial["available_context"]["complete_owner_cache_claimed"] is False
            assert not partial["capture_errors"]
            old.exact_nested(partial["supplied_cache"],raw)
            assert partial["available_context"]["wire"]["owner_fields"] == {}
""",
    1,
)
before, after = ast.parse(old_test), ast.parse(test)
inverse = copy.deepcopy(after)
for i, node in enumerate(inverse.body):
    if getattr(node, "name", None) == "test_ecm_charged_grn_dependencies":
        inverse.body[i] = copy.deepcopy(functions(before)[node.name])
assert dump(inverse) == dump(before)
(ROOT / TEST).write_text(test)

qpath = WORK / "betse_ecm_charged_grn_workqueue.json"
q = json.loads(qpath.read_text())
ecm_inputs = json.loads((ECM02 / "inputs.json").read_text())
allowed = {
    "src/cells/processes/betse_ecm_grn_join.py",
    "tests/unit/test_betse_ecm_grn_join.py",
    "validation/betse/betse_ecm_grn_protocol.json",
    "validation/betse/betse_ecm_grn_source_map.json",
}
changes = {
    path: dict(before=expected, after=sha(ROOT / path))
    for path, expected in q["protected_sha256"].items()
    if sha(ROOT / path) != expected
}
assert set(changes) == allowed, changes
for path, row in changes.items():
    assert path not in q["scientific_import_closure"], path
    assert row["after"] == ecm_inputs["owned_sha256"][path] == sha(ECM02 / "source" / path)
    q["protected_sha256"][path] = row["after"]
for path in original["owned_sha256"]:
    if path.endswith(".py") and path not in (JOIN, TEST):
        assert sha(ROOT / path) == original["owned_sha256"][path]
witness = dict(
    kind="cells.ecm_charged_grn_error_capture_02@1",
    held01=dict(
        inputs=str(FROZEN / "inputs.json"),
        sha256=sha(FROZEN / "inputs.json"),
        status="prepared_not_executed_not_qualified",
        numerical_runs=0,
    ),
    authority="Chief requested narrow ECM02 handler repair then charged sibling continuation; same handler deficiency is statically present in charged01",
    scope="Same source exception-capture plumbing only, plus pre-call durable malformed input archives; no physics, cases, native comparators or budgets change",
    join_inverse_AST_exact=True,
    all_other_test_AST_exact=True,
    five_other_scientific_Python_files_byte_exact=True,
    shared_failure_helper_AST_equal_to_ECM02=True,
    controlled_nonimported_ECM02_pin_refresh=changes,
    remaining_protected_pins_exact=len(q["protected_sha256"]) - len(changes),
    original_exception_chain_preserved=True,
    no_complete_cache_claim_for_absent_owner=True,
    original_ECM_round_still_failed=dict(passed=6, failed=2, unrun=17, accepted=False),
    original_material_panel_still_failed=dict(passed=39, total=40, accepted=False),
    scientific_imports=0,
    scientific_AST_executions=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    automatic_retry=False,
)
wpath = WORK / "betse_ecm_charged_grn_error_capture_witness_02.json"
assert not wpath.exists()
write(wpath, witness)
for label, path in (
    ("held_ecm_charged01_inputs", FROZEN / "inputs.json"),
    ("held_ecm_charged01_receipt", WORK / "betse_ecm_charged_grn_static_receipt_01.json"),
    ("repaired_ecm02_inputs", ECM02 / "inputs.json"),
    ("repaired_ecm02_receipt", WORK / "betse_ecm_grn_static_receipt_02.json"),
    ("ecm_error_capture_witness02", WORK / "betse_ecm_grn_error_capture_witness_02.json"),
    (
        "failed_ecm01_sealed_review",
        Path("/mnt/workspaces/Cells/betse-ecm-grn-tests-20261031-01/root-review-01/REVIEW.json"),
    ),
    ("charged_ecm_error_capture_witness02", wpath),
):
    q["binding_evidence"][label] = dict(path=str(path), sha256=sha(path))
assert (
    q["binding_evidence"]["failed_ecm01_sealed_review"]["sha256"]
    == "51cb27e8b0acbc65842d61826e22ddbdfd7c6f8a3475be33e9148a32e7fea881"
)
q["error_capture_repair_02"] = dict(
    witness=str(wpath),
    sha256=sha(wpath),
    controlled_nonimported_ECM02_pin_refresh=changes,
    join_inverse_AST_exact=True,
    five_other_scientific_Python_files_byte_exact=True,
    held01_not_executed=True,
    automatic_retry=False,
)
q["status"] = "charged_error_capture02_requires_static_audit_no_retry"
q["workfiles"] += [
    "agent-work/cells-worker-01/workfiles/" + name
    for name in (
        "prepare_betse_ecm_charged_grn_error_capture_02.py",
        "betse_ecm_charged_grn_error_capture_audit_02.py",
        "betse_ecm_charged_grn_error_capture_witness_02.json",
    )
]
write(qpath, q)
for relative in (
    "validation/betse/betse_ecm_charged_grn_protocol.json",
    "validation/betse/betse_ecm_charged_grn_source_map.json",
):
    path = ROOT / relative
    data = json.loads(path.read_text())
    data["error_capture_repair_02"] = q["error_capture_repair_02"]
    if "binding_evidence" in data:
        data["binding_evidence"] = q["binding_evidence"]
    write(path, data)
print(
    json.dumps(
        dict(
            held_charged01_untouched=True,
            old_nonimported_ECM_pins_refreshed=4,
            other_protected_exact=witness["remaining_protected_pins_exact"],
            numerical_runs=0,
        )
    )
)
