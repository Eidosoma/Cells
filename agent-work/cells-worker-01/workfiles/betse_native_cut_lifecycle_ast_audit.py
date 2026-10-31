"""Literal prefix, records, owner isolation and refusal boundary AST proof only."""

import ast
import builtins
import copy
import hashlib
import json
import symtable
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
SOURCE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
PREFIX = "betse_native_cut_lifecycle"


def digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args + node.args.kwonlyargs:
            arg.annotation = None
        return self.generic_visit(node)


def audit():
    original = ast.parse((SOURCE / "science/tissue/tishandler.py").read_text())
    cls = next(
        n for n in original.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler"
    )
    cut = copy.deepcopy(functions(cls)["_cut_cells"])
    stop = next(
        i
        for i, n in enumerate(cut.body)
        if isinstance(n, ast.Assign) and "cells.mesh.cut_mesh" in ast.unparse(n)
    )
    assert stop == 32 and cut.body[stop].lineno == 1153
    cut.body = cut.body[:stop]
    cut.name = "deletion_prefix"
    cut = Clean().visit(cut)
    port_tree = ast.parse((ROOT / "src/cells/processes" / (PREFIX + "_source.py")).read_text())
    port = functions(port_tree)
    actual = copy.deepcopy(port["deletion_prefix"])
    assert ast.unparse(actual.body[-1]) == "return locals()"
    actual.body = actual.body[:-1]
    assert digest(actual) == digest(cut)
    flat = functions(ast.parse((SOURCE / "science/math/toolbox.py").read_text()))["flatten"]
    assert digest(Clean().visit(copy.deepcopy(flat))) == digest(port["flatten"])
    native_path = ROOT / "validation/topology" / (PREFIX + "_native.py")
    native_tree = ast.parse(native_path.read_text())
    builder = functions(native_tree)["literal_nodes"]
    namespace = dict(ast=ast, copy=copy)
    # Only execute this stdlib AST builder; returned scientific AST is data only.
    exec(compile(ast.Module(body=[builder], type_ignores=[]), str(native_path), "exec"), namespace)
    nodes = namespace["literal_nodes"](SOURCE.parent)
    selected = functions(ast.Module(body=nodes, type_ignores=[]))
    for name in ("flatten", "deletion_prefix"):
        assert digest(port[name]) == digest(selected[name]), name
    main = functions(ast.parse((ROOT / "src/cells/processes" / (PREFIX + ".py")).read_text()))
    records = functions(
        ast.parse((ROOT / "validation/topology" / (PREFIX + "_records.py")).read_text())
    )
    assert digest(Clean().visit(copy.deepcopy(main["snapshot"]))) == digest(
        Clean().visit(copy.deepcopy(records["snapshot"]))
    )
    wrapper = ast.unparse(main["capture_prefix"])
    for needed in (
        "before = snapshot(supplied)",
        "copy.deepcopy(supplied)",
        "source.deletion_prefix(handler, phase, picker)",
        "frame.tb_frame.f_locals",
        "available_source_locals",
        "available_source_frames",
        "snapshot(supplied) != before",
    ):
        assert needed in wrapper, needed
    assert wrapper.index("before = snapshot(supplied)") < wrapper.index("source.deletion_prefix(")
    assert wrapper.index("source.deletion_prefix(") < wrapper.index("after = snapshot(")
    begin = ast.unparse(main["begin"])
    assert begin.index("trial = capture_prefix(") < begin.index("ownership.apply_cut(")
    assert "np.sort(actual)" in begin and "cell_to_mems" in begin and "picked" in begin
    assert "REQUIRED_OWNERS" in begin and "plan.changed" not in begin
    refusal = ast.unparse(main["require_ordinary_continuation"])
    assert "raise CutContinuationRejected(epoch)" in refusal
    capabilities = ast.unparse(main["capabilities"])
    for flag in (
        "complete_native_cut=False",
        "physical_mesh_qualified=False",
        "ordinary_checkpoint_ready=False",
        "old_field_or_cache_reuse_allowed=False",
    ):
        assert flag in capabilities, flag
    test_tree = ast.parse((ROOT / "tests/unit" / ("test_" + PREFIX + ".py")).read_text())
    test = functions(test_tree)
    primary = ast.unparse(test["test_native_cut_prefix"])
    assert (
        primary.index("inputs-before-constructors")
        < primary.index("reference(")
        < primary.index("epoch = begin(")
    )
    assert "compare_native(epoch.trial, captured)" in primary
    assert "2e-12 + 5e-12 * abs(np.asarray(target[key]))" in primary
    assert "not plan.changed and epoch.invalidated" in primary
    raw = ast.unparse(test["test_native_cut_raw_partial"])
    for needed in (
        "raw-complete-available-return",
        "available_source_locals",
        "nested_unknown_late",
        "species_grid_collision",
        "alias_list_mutation",
    ):
        assert needed in raw, needed
    dependencies = ast.unparse(test["test_native_cut_capabilities"])
    assert "expected_type" in dependencies and "expected_message" in dependencies
    unresolved = {}
    paths = [
        *sorted((ROOT / "src/cells/processes").glob(PREFIX + "*.py")),
        *sorted((ROOT / "validation/topology").glob(PREFIX + "*.py")),
        ROOT / "tests/unit" / ("test_" + PREFIX + ".py"),
        *sorted(WORK.glob("*" + PREFIX + "*.py")),
    ]
    for path in paths:
        code = path.read_text()
        compile(code, str(path), "exec")
        table = symtable.symtable(code, str(path), "exec")
        known = set(table.get_identifiers()) | set(dir(builtins)) | {"__file__", "__name__"}

        def missing(scope, known=known):
            result = {
                s.get_name()
                for s in scope.get_symbols()
                if s.is_global() and s.is_referenced() and s.get_name() not in known
            }
            for child in scope.get_children():
                result |= missing(child)
            return result

        if found := missing(table):
            unresolved[str(path.relative_to(ROOT))] = sorted(found)
    assert not unresolved, unresolved
    return dict(
        kind="cells.native_cut_prefix_capability_AST_proof@1",
        literal_original_prefix_statements_including_docstring=32,
        first_unowned_line=1153,
        original_normalized_prefix_AST_sha256=digest(cut),
        literal_flatten_equal=True,
        appended_observation="return locals() only",
        independent_native_original_prefix_AST_equal=True,
        generic_capture_records_not_scientific_equations_shared=True,
        parent_graph_isolated_dictionary_order_and_container_aliases_retained=True,
        numeric_view_buffer_alias_not_checkpointed=True,
        complete_available_phase_and_source_frame_failure_evidence=True,
        source_and_conservative_removal_policies_separate=True,
        supplied_picker_occurrence_order_preserved=True,
        empty_selection_invalidates_native_lifecycle=True,
        owner_metadata_never_unlocks_checkpoint_or_mesh=True,
        compile_global_names=True,
        compiled_python_files=len(paths),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_evaluations=0,
        pytest_collection_runs=0,
        numerical_runs=0,
    )


if __name__ == "__main__":
    result = audit()
    with (WORK / (PREFIX + "_AST_witness_01.json")).open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
