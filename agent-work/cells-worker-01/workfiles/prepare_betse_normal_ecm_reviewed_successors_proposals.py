# ruff: noqa: E501
"""Create explicit frozen-only reference/test proposals and inverse source proofs."""

import ast
import copy
import hashlib
import json

from betse_normal_ecm_reviewed_successors_resources import BASE, ROOT, WORK, sha

PREFIX = "betse_normal_ecm_reviewed_successors"
PROPOSAL = WORK / (PREFIX + "_proposal_01")
REFERENCE = "validation/betse/betse_normal_ecm_catalog_join_reference.py"
EVENT = "validation/betse/betse_normal_ecm_event_join_reference.py"
TEST = "tests/unit/test_betse_normal_ecm_run_lifecycle.py"
NALEAK_SHA = "6c51cdddbeb166ee33a9000143aad16f003cb9e6d4178cb3993aa62a1538ea70"
EVENT_PARENT = BASE / "betse-normal-ecm-event-join-prepared-20261031-03"
LIFECYCLE_PARENT = BASE / "betse-normal-ecm-run-lifecycle-prepared-20261031-01"


def signature(node):
    return ast.dump(node, include_attributes=False)


def function(tree, name):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def write(relative, data):
    path = PROPOSAL / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(data)
    return path


def prepare():
    promotion = BASE / "ecm-catalog-naleak-reference-repair-20261031-01/promotion.json"
    promoted = json.loads(promotion.read_text())
    assert promoted["status"] == "reviewed_candidate_promoted_byte_exact"
    assert sha(ROOT / REFERENCE) == NALEAK_SHA == promoted["live_source_sha256"][REFERENCE]
    review = promoted["independent_review"]
    assert sha(review["path"]) == review["sha256"]
    PROPOSAL.mkdir(exist_ok=False)
    catalog_text = (ROOT / REFERENCE).read_text()
    catalog_tree = ast.parse(catalog_text)
    kinetics = function(catalog_tree, "kinetics")
    branch = next(
        n
        for n in kinetics.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "name == 'NaLeak'"
    )
    inserted = "".join(
        catalog_text.splitlines(keepends=True)[branch.lineno - 1 : branch.end_lineno]
    )
    before = (EVENT_PARENT / "source" / EVENT).read_text()
    old_tree = ast.parse(before)
    old_kinetics = function(old_tree, "kinetics")
    assert ast.unparse(old_kinetics.body[2].test) == "family == 'Na'"
    lines = before.splitlines(keepends=True)
    position = old_kinetics.body[2].lineno - 1
    after = "".join(lines[:position]) + inserted + "".join(lines[position:])
    assert after.replace(inserted, "", 1) == before
    new_tree = ast.parse(after)
    new_kinetics = function(new_tree, "kinetics")
    assert signature(new_kinetics.body[2]) == signature(branch)
    inverse = copy.deepcopy(new_tree)
    function(inverse, "kinetics").body.pop(2)
    assert signature(inverse) == signature(old_tree)
    event_path = write(EVENT, after)
    write(REFERENCE, catalog_text)
    test_before = (LIFECYCLE_PARENT / "source" / TEST).read_text()
    replacements = [
        (
            '        archive(tmp_path, stage + "-reached-" + name, value)\n',
            """        call_index = (
            value["call"]["call_index"]
            if name == "before_call"
            else value["parent"].cursor - 1
            if name == "accepted_call"
            else value.call_index
        )
        archive(tmp_path, stage + "-reached-" + name + "-" + str(call_index), value)
""",
        ),
        (
            '    archive(tmp_path, stage + "-full-failure", partial)\n',
            """    archive(tmp_path, stage + "-full-failure", partial)
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    assert type(leaf) is RuntimeError and str(leaf) == "Declared observer failure"
""",
        ),
        (
            "                expected_failure_reached=True,\n",
            """                expected_failure_reached=True,
                actual_leaf_type=type(leaf).__name__,
                actual_leaf_message=str(leaf),
""",
        ),
    ]
    test_after = test_before
    for old, new in replacements:
        assert test_after.count(old) == 1
        test_after = test_after.replace(old, new, 1)
    test_inverse = test_after
    for old, new in reversed(replacements):
        assert test_inverse.count(new) == 1
        test_inverse = test_inverse.replace(new, old, 1)
    assert test_inverse == test_before
    before_tree, after_tree = ast.parse(test_before), ast.parse(test_after)
    for old, new in zip(before_tree.body, after_tree.body, strict=True):
        if isinstance(old, ast.FunctionDef) and old.name == "test_headless_observer_failure":
            continue
        assert signature(old) == signature(new)
    test_path = write(TEST, test_after)
    driver_before = (LIFECYCLE_PARENT / "driver.py").read_text()
    anchor = "                expected_failure_reached=True,\n"
    addition = """                expected_failure_reached=True,
                actual_leaf_type="RuntimeError",
                actual_leaf_message="Declared observer failure",
"""
    assert driver_before.count(anchor) == 1
    driver_after = driver_before.replace(anchor, addition, 1)
    assert driver_after.replace(addition, anchor, 1) == driver_before
    driver_path = write("lifecycle-observer-reader.py", driver_after)
    result = dict(
        kind="cells.explicit_ECM_successor_source_proposals@1",
        status="ready_for_independent_static_review_unrun",
        reviewed_catalog_reference=dict(path=str(ROOT / REFERENCE), sha256=NALEAK_SHA),
        catalog_promotion=dict(path=str(promotion), sha256=sha(promotion)),
        catalog_review=review,
        event_NaLeak_only=dict(
            before_path=str(EVENT_PARENT / "source" / EVENT),
            before_sha256=sha(EVENT_PARENT / "source" / EVENT),
            candidate_path=str(event_path),
            after_sha256=sha(event_path),
            inserted_branch_AST=signature(branch),
            inserted_branch_AST_sha256=hashlib.sha256(signature(branch).encode()).hexdigest(),
            exact_reviewed_catalog_branch=True,
            entire_module_inverse_AST_exact=True,
            exact_source_byte_inverse=True,
            other_equations_budgets_and_routes_unchanged=True,
            independent_event_review_pending=True,
        ),
        lifecycle_observer_repair=dict(
            before_path=str(LIFECYCLE_PARENT / "source" / TEST),
            before_sha256=sha(LIFECYCLE_PARENT / "source" / TEST),
            candidate_path=str(test_path),
            after_sha256=sha(test_path),
            only_changed_test="test_headless_observer_failure",
            per_call_paths_for_before_accepted_and_observation=True,
            exact_root_RuntimeError_and_declared_message_required=True,
            exact_source_byte_inverse=True,
            other_test_functions_AST_exact=True,
            reader_candidate_path=str(driver_path),
            reader_sha256=sha(driver_path),
            reader_delta="Require exact RuntimeError/Declared observer failure witness in observer JSON",
            native_production_reference_equations_and_roster_unchanged=True,
        ),
        archive_cap_candidate_adopted=False,
        archive_review_clearance_pending=True,
        old_frozen_and_live_sources_changed=False,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        new_or_retained_qualification_passes=0,
    )
    path = write(
        "source-proposals.json",
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )
    print(
        json.dumps(
            dict(
                proof=str(path),
                sha256=sha(path),
                event_sha256=sha(event_path),
                test_sha256=sha(test_path),
                numerical_runs=0,
            )
        )
    )


if __name__ == "__main__":
    prepare()
