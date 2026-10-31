"""Resolve every used event01/mechanics02 overlap and reviewed catalog04 guard delta."""

import argparse
import ast
import copy
import json
from pathlib import Path

from betse_normal_ecm_event_mechanics_audit_tools import (
    ROOT,
    closure,
    functions,
    sha,
    signature,
    write,
)

PREFIX = "betse_normal_ecm_event_mechanics"
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
EVENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-event-join-prepared-20261031-01")
MECH = Path("/mnt/workspaces/Cells/betse-normal-ecm-mechanics-join-prepared-20261031-02")
CATALOG = Path("/mnt/workspaces/Cells/betse-normal-ecm-catalog-join-prepared-20261031-04")
REVIEW = Path(
    "/mnt/workspaces/Cells/ecm-catalog-hot-cache-repair-20261031-01/root-review-01/REVIEW.json"
)
GUARD = "src/cells/processes/betse_normal_ecm_catalog_join_source.py"


def audit():
    event = json.loads((EVENT / "inputs.json").read_text())
    mechanics = json.loads((MECH / "manifest.json").read_text())
    m = {
        p.removeprefix("source/"): h
        for p, h in mechanics["file_sha256"].items()
        if p.startswith("source/")
    }
    imports = closure("tests/unit/test_" + PREFIX + ".py")
    refs = closure("validation/betse/" + PREFIX + "_reference.py", reference=True)
    used = imports | refs
    # Runtime source captures read these contracts as data, rather than Python imports.
    for relative in list(used):
        for node in ast.walk(ast.parse((ROOT / relative).read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "with_name"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.endswith(".json")
            ):
                candidate = Path(relative).with_name(node.args[0].value)
                if (ROOT / candidate).is_file():
                    used[str(candidate)] = sha(ROOT / candidate)
    oldtree = ast.parse((EVENT / "source" / GUARD).read_text())
    newtree = ast.parse((ROOT / GUARD).read_text())
    old = functions(EVENT / "source" / GUARD)["validate_cached_channels"]
    current = next(
        n
        for n in newtree.body
        if isinstance(n, ast.FunctionDef) and n.name == "validate_cached_channels"
    )
    original = {
        n.targets[0].id: n
        for n in ast.walk(old)
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in {"warm", "dynamic"}
    }

    class Inverse(ast.NodeTransformer):
        def __init__(self):
            self.count = 0

        def visit_Assign(self, node):
            if isinstance(node.targets[0], ast.Name) and node.targets[0].id in original:
                self.count += 1
                return copy.deepcopy(original[node.targets[0].id])
            return self.generic_visit(node)

    inverse = Inverse()
    restored = inverse.visit(copy.deepcopy(current))
    assert inverse.count == 2 and signature(restored) == signature(old)
    newtree.body = [
        restored if isinstance(n, ast.FunctionDef) and n.name == "validate_cached_channels" else n
        for n in newtree.body
    ]
    assert signature(newtree) == signature(oldtree)
    reviewed = json.loads(REVIEW.read_text())
    assert (
        reviewed["status"] == "clear_for_fresh_full_catalog_qualification_preparation"
        and reviewed["blockers"] == []
    )
    delta = reviewed["source_delta"]
    assert delta["before_sha256"] == event["source_hashes"][GUARD] == sha(EVENT / "source" / GUARD)
    assert (
        delta["after_sha256"]
        == sha(ROOT / GUARD)
        == json.loads((CATALOG / "inputs.json").read_text())["owned_sha256"][GUARD]
    )
    assert (
        delta["exact_inverse_AST"]
        and delta["numerical_equations_native_reference_and_budgets_unchanged"]
    )
    pins, origins, overlap = {}, {}, {}
    mechanical_prefixes = (
        "src/cells/processes/betse_mechanics_join",
        "src/cells/processes/betse_deformation",
        "src/cells/processes/betse_fluid_flow",
        "validation/betse/betse_mechanics_join",
        "validation/betse/betse_normal_ecm_mechanics_join",
        "tests/unit/test_betse_mechanics_join",
        "tests/unit/test_betse_normal_ecm_mechanics_join",
    )
    for relative, digest in sorted(used.items()):
        if PREFIX in relative:
            continue
        eh = event["source_hashes"].get(relative)
        mh = m.get(relative)
        if relative == GUARD:
            expected = delta["after_sha256"]
            origin = "reviewed_catalog04_guard_only"
        elif relative.startswith(mechanical_prefixes) and mh is not None:
            expected = mh
            origin = "mechanics02_explicit_qualified_dependency_snapshot"
        elif eh is not None:
            expected = eh
            origin = "event01_callback03_snapshot"
        elif mh is not None:
            expected = mh
            origin = "mechanics02_additional_dependency"
        else:
            raise ValueError("Used dependency has no reviewed ancestor pin: " + relative)
        if digest != expected:
            raise ValueError(
                "Unresolved source overlap: "
                + relative
                + " actual="
                + digest
                + " expected="
                + expected
            )
        pins[relative] = expected
        origins[relative] = origin
        if eh is not None and mh is not None:
            overlap[relative] = dict(
                event01=eh,
                mechanics02=mh,
                selected=expected,
                authority=origin,
                ancestors_equal=eh == mh,
            )
    update = json.loads((MECH / "dependency-update02.json").read_text())
    assert (
        sha(MECH / "manifest.json")
        == "7ed2fb1bb6e0afca8a9419d44aed74980561a9ceadde17fc542e023eb24e09ea"
    )
    assert (
        update["divergence_category_change"]["before"] == 3e-20
        and update["divergence_category_change"]["after"] == 3e-14
    )
    assert (
        sha(ROOT / "validation/betse/betse_mechanics_join_checks.py")
        == "6841f8f33a1492f0a67e794a127a7f1d8566727dbe6013a76ad920b062f0389f"
    )
    return dict(
        kind="cells.event_mechanics_explicit_dependency_binding@1",
        status="all_used_dependencies_resolved_static_only",
        event01_inputs=dict(path=str(EVENT / "inputs.json"), sha256=sha(EVENT / "inputs.json")),
        mechanics02_manifest=dict(
            path=str(MECH / "manifest.json"), sha256=sha(MECH / "manifest.json")
        ),
        mechanics02_update=dict(
            path=str(MECH / "dependency-update02.json"),
            sha256=sha(MECH / "dependency-update02.json"),
        ),
        catalog04_inputs=dict(
            path=str(CATALOG / "inputs.json"), sha256=sha(CATALOG / "inputs.json")
        ),
        catalog04_review=dict(path=str(REVIEW), sha256=sha(REVIEW)),
        catalog04_guard=dict(
            path=GUARD,
            before_sha256=delta["before_sha256"],
            after_sha256=delta["after_sha256"],
            only_inverse_assignments=["warm", "dynamic"],
            whole_module_inverse_AST_exact=True,
            equations_and_budgets_unchanged=True,
        ),
        overlap_resolution=overlap,
        selected_pin_authority=origins,
        protected_sha256=pins,
        reference_closure=refs,
        scientific_import_closure=imports,
        explicit_prior_mechanics_divergence_category_change=update["divergence_category_change"],
        new_budget_changes=False,
        no_scientific_qualification_inherited=True,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=WORK / (PREFIX + "_dependency_witness_01.json")
    )
    args = parser.parse_args()
    result = audit()
    path = args.output
    write(path, result)
    print(
        json.dumps(
            dict(
                status=result["status"],
                protected=len(result["protected_sha256"]),
                imports=len(result["scientific_import_closure"]),
                references=len(result["reference_closure"]),
                overlaps=len(result["overlap_resolution"]),
                sha256=sha(path),
            )
        )
    )
