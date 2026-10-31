"""Resolve dependencies from reviewed immutable successors, never a live ref refresh."""

import ast
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_run_lifecycle"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-event-mechanics-prepared-20261031-02")
OLD = Path("/mnt/workspaces/Cells/betse-normal-ecm-event-mechanics-prepared-20261031-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def locate(relative):
    return ROOT / relative if PREFIX in relative else PARENT / "source" / relative


def closure(start, *, reference=False):
    pending, closed = [start], {}
    while pending:
        relative = pending.pop()
        if relative in closed:
            continue
        path = locate(relative)
        tree = ast.parse(path.read_text())
        compile(tree, relative, "exec")
        closed[relative] = sha(path)
        parts = Path(relative).parts
        for length in range(1, len(parts)):
            candidate = str(Path(*parts[:length]) / "__init__.py")
            if locate(candidate).is_file():
                pending.append(candidate)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert not node.level, (relative, "relative module unresolved")
                names = [node.module] + [node.module + "." + n.name for n in node.names]
            else:
                continue
            for name in names:
                head = name.split(".")[0]
                if reference:
                    assert head in sys.stdlib_module_names | {"validation"}, (relative, name)
                if head not in ("cells", "tests", "validation"):
                    continue
                for prefix in ("", "src/"):
                    for suffix in (".py", "/__init__.py"):
                        candidate = prefix + name.replace(".", "/") + suffix
                        if locate(candidate).is_file():
                            pending.append(candidate)
    return closed


def audit():
    assert (
        sha(PARENT / "inputs.json")
        == "8df92c3695c401dcf42883394a719c93b072a69ddcb3eaf38b1be53f79275b18"
    )
    inputs = json.loads((PARENT / "inputs.json").read_text())
    review = Path(
        "/mnt/workspaces/Cells/betse-normal-ecm-event-mechanics-preflight-20261031-02/REVIEW.json"
    )
    reviewed = json.loads(review.read_text())
    assert reviewed["status"] == "clear_for_held_full_roster_runner_preparation"
    assert sha(review) == "f99c5a713aad0c9b4c33b75f5073ec6a83ff2dd4a03203c6f785c1103cdf4c0d"
    independent = reviewed["independent_calendar_API_review"]
    assert (
        sha(independent["path"])
        == independent["sha256"]
        == "294016b28e8f47aa2a2f9669152dc510a0e8925b0a2b4db03e1dad303f5ef656"
    )
    inverse = {}

    class Rename(ast.NodeTransformer):
        def __init__(self):
            self.count = 0

        def visit_Attribute(self, node):
            node = self.generic_visit(node)
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "calendars"
                and node.attr == "dense"
            ):
                node.attr = "window"
                self.count += 1
            return node

    for relative, count in (
        ("src/cells/processes/betse_normal_ecm_event_join.py", 2),
        ("src/cells/processes/betse_normal_ecm_event_mechanics.py", 3),
    ):
        before = ast.parse((OLD / "source" / relative).read_text())
        after = ast.parse(locate(relative).read_text())
        rename = Rename()
        mapped = rename.visit(copy.deepcopy(before))
        assert rename.count == count and ast.dump(mapped, include_attributes=False) == ast.dump(
            after, include_attributes=False
        )
        assert sha(locate(relative)) == inputs["source_hashes"][relative]
        inverse[relative] = dict(
            before_sha256=sha(OLD / "source" / relative),
            after_sha256=sha(locate(relative)),
            only_dense_to_window_callsite_changes=count,
            entire_module_AST_inverse_exact=True,
        )
    calendar = "src/cells/core/physiology_native_calendar.py"
    assert (
        sha(locate(calendar))
        == sha(OLD / "source" / calendar)
        == "111a3ff8fa0fba75497eab2bf6a0b086a7a4e9c9128909077bc7e366254b19fb"
    )
    refs = closure("validation/betse/" + PREFIX + "_reference.py", reference=True)
    imports = closure("tests/unit/test_" + PREFIX + ".py")
    all_used = refs | imports
    for relative in list(all_used):
        for node in ast.walk(ast.parse(locate(relative).read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "with_name"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.endswith(".json")
            ):
                candidate = str(Path(relative).with_name(node.args[0].value))
                if locate(candidate).is_file():
                    all_used[candidate] = sha(locate(candidate))
    protected = {p: h for p, h in all_used.items() if PREFIX not in p}
    for p, h in protected.items():
        assert h == inputs["source_hashes"][p], p
    absolute_live_reads = {}
    for p in imports | refs:
        values = [
            n.value
            for n in ast.walk(ast.parse(locate(p).read_text()))
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and n.value.startswith("/home/robert/Cells")
        ]
        if values:
            absolute_live_reads[p] = values
    assert not absolute_live_reads, absolute_live_reads
    current_not_adopted = {
        p: dict(frozen_sha256=h, observed_live_sha256=sha(ROOT / p), adopted=False)
        for p, h in protected.items()
        if (ROOT / p).is_file() and sha(ROOT / p) != h
    }
    return dict(
        kind="cells.headless_lifecycle_reviewed_dependency_binding@1",
        status="immutable_reviewed_successors_bound_unrun",
        parent_inputs=dict(path=str(PARENT / "inputs.json"), sha256=sha(PARENT / "inputs.json")),
        parent_manifest=dict(
            path=str(PARENT / "manifest.json"), sha256=sha(PARENT / "manifest.json")
        ),
        parent_preflight=dict(path=str(review), sha256=sha(review)),
        independent_calendar_review=independent,
        event03_inputs=reviewed.get(
            "event03_inputs",
            dict(
                path="/mnt/workspaces/Cells/betse-normal-ecm-event-join-prepared-20261031-03/inputs.json",
                sha256="604eca1502addb301452f3cb8c5889853895c42334392f617b5a5d6f290460c6",
            ),
        ),
        exact_calendar_caller_delta=inverse,
        calendar_implementation_sha256=sha(locate(calendar)),
        reference_closure=refs,
        scientific_import_closure=imports,
        protected_snapshot_sha256=protected,
        frozen_dependency_sources={
            p: dict(path=str(locate(p)), sha256=h) for p, h in protected.items()
        },
        observed_live_differences_not_adopted=current_not_adopted,
        absolute_live_repository_reads_in_closure=absolute_live_reads,
        reference_policy=(
            "Exact event/mechanics02 frozen reference closure. Prospective NaLeak-only live "
            "correction is not adopted without its own reviewed successor."
        ),
        copied_parent_snapshot_is_runtime_authority=True,
        live_own_prefix_pins_still_required=True,
        no_previous_packet_or_shared_live_file_modified=True,
        component_qualification_pending=True,
        new_or_retained_scientific_passes=0,
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        reference_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
        automatic_followup=False,
    )


if __name__ == "__main__":
    result = audit()
    path = WORK / (PREFIX + "_dependency_witness_01.json")
    with path.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                status=result["status"],
                imports=len(result["scientific_import_closure"]),
                references=len(result["reference_closure"]),
                protected=len(result["protected_snapshot_sha256"]),
                live_differences_not_adopted=len(result["observed_live_differences_not_adopted"]),
                sha256=sha(path),
            )
        )
    )
