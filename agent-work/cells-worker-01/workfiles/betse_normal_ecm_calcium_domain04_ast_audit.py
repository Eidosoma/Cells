"""Exact-input taxonomy and unchanged RHS/legacy science proof; no equation evaluation."""

import ast
import builtins
import hashlib
import json
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_calcium_domain04"
FROZEN = Path("/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-prepared-20261031-03")
REVIEW = Path(
    "/mnt/workspaces/Cells/ecm-calcium-catalog-failure-review-20261031-01/calcium/REVIEW.json"
)
REVIEW_SHA = "e055aff4ddd73ce47e9977db139812f19b54a7bee110b146432d45c2675d91a2"
EVIDENCE = Path(
    "/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-launch-preparation-20261031-03/qualification-01/run-core/evidence/normal-ecm-calcium-join"
)
INPUT_SHA = "41d5da23526aac015a219e2c7d535998c7181fc40520d5ef1a967034af808606"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def functions(path):
    return {
        n.name: n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)
    }


def constants(path, names):
    return {
        t.id: ast.literal_eval(n.value)
        for n in ast.parse(Path(path).read_text()).body
        if isinstance(n, ast.Assign)
        for t in n.targets
        if isinstance(t, ast.Name) and t.id in names
    }


def audit():
    assert sha(REVIEW) == REVIEW_SHA
    reviewed = json.loads(REVIEW.read_text())
    assert reviewed["status"] == "failed_campaign_confirmed_partial_evidence_verified"
    assert reviewed["full_campaign_pass"] is False and reviewed["originals_unchanged"] is True
    assert reviewed["counts"]["pytest_passes"] == 33 and reviewed["counts"]["pytest_failures"] == 1
    assert reviewed["counts"]["credited_completed_group_ids"] == 29
    assert reviewed["failure"]["owned_hot_loop_reached"] is False
    assert reviewed["counts"]["compared_reference_forms"] == 420
    assert reviewed["counts"]["generated_but_uncompared_reference_forms"] == 4
    old = json.loads((FROZEN / "inputs.json").read_text())
    # Every inherited owned module/test/fixture/protocol stays unchanged to03.
    for path, expected in old["owned_sha256"].items():
        assert sha(ROOT / path) == expected, path
    exact_input = ROOT / "validation/betse" / (PREFIX + "_negative_genes.json")
    assert sha(exact_input) == sha(EVIDENCE / "isolated-negative_genes/inputs.json") == INPUT_SHA
    manifest_path = EVIDENCE / "isolated-negative_genes/native/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["complete"] is True
    for name, expected in manifest["files"].items():
        assert sha(manifest_path.parent / name) == expected, name
    fixture_path = ROOT / "validation/betse" / (PREFIX + "_fixtures.py")
    c = constants(
        fixture_path,
        {"CASES", "RAW_DOMAIN_CASES", "RAW_CASES", "DEPENDENCIES", "COMPONENT_CONTROLS"},
    )
    legacy = constants(
        ROOT / "validation/betse/betse_normal_ecm_calcium_join_fixtures.py",
        {"CASES", "RAW_CASES", "DEPENDENCIES", "COMPONENT_CONTROLS"},
    )
    assert c["CASES"] == tuple(x for x in legacy["CASES"] if x != "negative_genes")
    assert c["RAW_DOMAIN_CASES"] == ("negative_genes",)
    for key in ("RAW_CASES", "DEPENDENCIES", "COMPONENT_CONTROLS"):
        assert c[key] == legacy[key]
    assert (
        len(set().union(c["CASES"], c["RAW_CASES"], c["RAW_DOMAIN_CASES"], c["DEPENDENCIES"])) == 34
    )
    test = functions(ROOT / "tests/unit" / ("test_" + PREFIX + ".py"))
    for name, target in (
        ("test_calcium_domain04_positive", "base.test_ecm_calcium_field_history(tmp_path, case)"),
        ("test_calcium_domain04_raw", "base.test_ecm_calcium_raw_partial(tmp_path, case)"),
        (
            "test_calcium_domain04_dependencies",
            "base.test_ecm_calcium_dependencies(tmp_path, dependency)",
        ),
    ):
        assert len(test[name].body) == 1 and ast.unparse(test[name].body[0]) == target
    history = ast.unparse(test["test_calcium_domain04_observed_history"])
    for needed in (
        "range(2)",
        "source_completed",
        "first[0] == 4",
        "first[1]['stage'] == 'junction_flux'",
        "first[1]['ion_id'] == 'Na'",
        "helper_only=True",
        "set(observed) == {'material', 'calcium'}",
        "positive_credit=False",
        "calcium_specific_cause_claim=False",
        "native_full_history_accepted=False",
        "total_fresh_reference_forms=22",
        "domain-complete-third-refusal",
        "domain-unexpected-third-return",
        "native_stop='GRN_X_transport_no_negs_NaN'",
        "port_stop='existing_CaATP_finite_guard'",
    ):
        assert needed in history, needed
    assert history.index("inputs-before-constructor.json") < history.index("base.references(")
    assert history.index("domain-bootstrap-return") < history.index(
        "base.isolated(tmp_path, inputs)"
    )
    assert "dt_rates_coefficients_or_guards_changed=False" in history
    reference = functions(ROOT / "validation/betse" / (PREFIX + "_reference.py"))[
        "chemistry_prefix"
    ]
    old_warm = functions(ROOT / "validation/betse/betse_ecm_grn_reference.py")["warm"]
    old_block = next(n for n in old_warm.body if isinstance(n, ast.With))
    stop = next(
        i
        for i, n in enumerate(old_block.body)
        if isinstance(n, ast.FunctionDef) and n.name == "ghk"
    )
    new_block = next(n for n in reference.body if isinstance(n, ast.With))
    assert [digest(n) for n in new_block.body[:stop]] == [digest(n) for n in old_block.body[:stop]]
    assert len(new_block.body) == stop + 3
    assert "transport_evaluations=0" in ast.unparse(new_block.body[-1])
    # The new chemical commit/gross equations are the existing list equations,
    # wrapped by name into dictionaries; no changed floating or precision law.
    old_loop = next(
        n
        for n in old_block.body[stop:]
        if isinstance(n, ast.For) and ast.unparse(n.iter) == "configured"
    )
    old_assign = {
        n.targets[0].id: n.value
        for n in old_loop.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
    }
    for node, name in zip(new_block.body[stop : stop + 2], ("cell", "cell_gross"), strict=True):
        assert isinstance(node.value, ast.DictComp)
        assert digest(node.value.value) == digest(old_assign[name]), name
    keys = constants(
        ROOT / "validation/betse" / (PREFIX + "_reference.py"),
        {"CHEMISTRY_INPUT_KEYS", "CHEMISTRY_VALUE_KEYS"},
    )
    read = set()
    for node in ast.walk(reference):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "inputs"
            and isinstance(node.slice, ast.Constant)
        ):
            read.add(node.slice.value)
    assert set(keys["CHEMISTRY_INPUT_KEYS"]) | {"values_before"} == read
    value_read = {
        node.slice.value
        for node in ast.walk(reference)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Subscript)
        and ast.unparse(node.value) == "inputs['values_before']"
        and isinstance(node.slice, ast.Constant)
    }
    assert set(keys["CHEMISTRY_VALUE_KEYS"]) == value_read
    compare = ast.unparse(test["compare_chemistry_prefix"])
    for needed in (
        "2e-14 + 5e-12 * abs(wanted)",
        "6e-14 + 5e-12 * np.asarray",
        "3e-13 + factor * np.asarray",
        "128 * np.finfo(float).eps",
    ):
        assert needed in compare, needed
    paths = [
        ROOT / "tests/unit" / ("test_" + PREFIX + ".py"),
        ROOT / "validation/betse" / (PREFIX + "_fixtures.py"),
        ROOT / "validation/betse" / (PREFIX + "_reference.py"),
        WORK / (PREFIX + "_ast_audit.py"),
        WORK / ("prepare_" + PREFIX + "_reference.py"),
    ]
    unresolved = {}
    for path in paths:
        code = path.read_text()
        compile(code, str(path), "exec")
        tab = symtable.symtable(code, str(path), "exec")
        known = set(tab.get_identifiers()) | set(dir(builtins)) | {"__name__", "__file__"}

        def missing(scope, known=known):
            values = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                values |= missing(child)
            return values

        if found := missing(tab):
            unresolved[str(path.relative_to(ROOT))] = sorted(found)
    assert not unresolved, unresolved
    return dict(
        kind="cells.calcium_domain04_source_classification_AST_proof@1",
        unchanged_legacy_owned_files=len(old["owned_sha256"]),
        original_input_sha256=INPUT_SHA,
        original_native_manifest_sha256=sha(manifest_path),
        saved_failure_review=dict(path=str(REVIEW), sha256=REVIEW_SHA),
        full_roster=34,
        positive_histories=15,
        existing_raw_cases=6,
        observed_raw_domain_histories=1,
        dependency_controls=12,
        planned_native_captures=22,
        planned_fresh_reference_forms=15 * 28 + 22,
        all_legacy_science_fixtures_native_reference_tests_byte_unchanged=True,
        unchanged_legacy_positive_raw_dependency_tests_called=True,
        exact_original_input_metadata_and_coefficients_preserved=True,
        earlier_ordinary_Na_junction_nonfinite_context_retained=True,
        distinct_native_and_strict_owned_endpoints=True,
        no_calcium_specific_cause_or_negative_concentration_claim=True,
        chemistry_prefix_existing_RHS_delta_inverse_exact=True,
        chemical_commit_and_gross_existing_equations_exact=True,
        actual_native_input_read_projection_no_replacement=True,
        raw_common_prefix_and_helper_only_comparison=True,
        original_campaign_still_failed=True,
        historical_owned_hot_credit_for_case=0,
        historical_uncompared_constructor_forms=4,
        retained_new_qualification_passes=0,
        compiled_python_files=len(paths),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / (PREFIX + "_AST_witness_01.json")).open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
