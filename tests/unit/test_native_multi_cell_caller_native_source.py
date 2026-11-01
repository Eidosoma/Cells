"""Independent-source metadata controls; no source body or science executes."""

import ast
import hashlib
import importlib.abc
import sys
from pathlib import Path

import pytest

from validation.betse import native_multi_cell_caller_native_source as native

ROOT = Path("/mnt/workspaces/Cells/betse-v1.5.0")


@pytest.fixture(autouse=True)
def no_science(monkeypatch):
    attempted = []

    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"cells", "betse", "numpy", "scipy", "PIL", "jax"}:
                attempted.append(fullname)
                raise AssertionError("Scientific import forbidden: " + fullname)

    def forbidden(*args, **kwargs):
        raise AssertionError("Original source evaluation forbidden")

    blocker = Block()
    sys.meta_path.insert(0, blocker)
    monkeypatch.setattr(native.shared, "evaluate", forbidden)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
    assert not attempted


def dump(node):
    return ast.dump(node, include_attributes=False)


def original(relative, name):
    tree = ast.parse((ROOT / relative).read_bytes())
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)


def selected(groups, relative, name):
    return next(
        node
        for file, nodes in groups
        if file == relative
        for node in nodes
        if getattr(node, "name", None) == name
    )


def test_world_stops_at_literal_cell_index_with_no_geometry_or_callback_suffix():
    groups, sites = native.source_nodes(ROOT)
    caller = selected(groups, native.CELLS_FILE, "Cells")
    old = original(native.CELLS_FILE, "Cells")
    methods = {node.name: node for node in old.body if isinstance(node, ast.FunctionDef)}
    assert [node.name for node in caller.body] == list(native.METHODS)
    for method in caller.body:
        if method.name != "make_world":
            assert dump(method) == dump(methods[method.name])
    world = next(node for node in caller.body if node.name == "make_world")
    expected = ast.parse("self.cell_index(phase.p)").body[0]
    assert dump(world.body[-1]) == dump(expected)
    assert [dump(node) for node in world.body] == [
        dump(node) for node in methods["make_world"].body[: len(world.body)]
    ]
    assert world.end_lineno == world.body[-1].end_lineno
    assert "cellVerts" not in ast.unparse(world) and "progressed_next" not in ast.unparse(world)
    assert (
        sites[native.CELLS_FILE + ":Cells.make_world"]["ast_sha256"]
        == hashlib.sha256(dump(world).encode()).hexdigest()
    )


def test_complete_parameter_branches_and_twenty_stores_preserve_original_order():
    groups, sites = native.source_nodes(ROOT)
    stores = selected(groups, native.PARAMETER_FILE, "store_parameters")
    source = {
        node.lineno: node
        for node in ast.walk(original(native.PARAMETER_FILE, "Parameters"))
        if isinstance(node, (ast.Assign, ast.If))
    }
    assert len(stores.body) == 20
    assert [node.lineno for node in stores.body] == list(native.STORE_LINES)
    for node in stores.body:
        assert dump(node) == dump(source[node.lineno])
        record = sites[native.PARAMETER_FILE + ":statement_" + str(node.lineno)]
        assert (
            record["ast_sha256"] == hashlib.sha256(dump(source[node.lineno]).encode()).hexdigest()
        )
    branches = [node for node in stores.body if isinstance(node, ast.If)]
    assert [node.lineno for node in branches] == [546, 560]
    assert all(node.body and node.orelse for node in branches)
    assert "maximum_voronoi_steps = 10" in ast.unparse(branches[0])
    assert "svg_cells_fname" in ast.unparse(branches[1])


def test_mesh_picker_helpers_are_literal_and_only_expected_ast_groups_differ():
    before, _ = native.shared.source_nodes(ROOT)
    after, _ = native.source_nodes(ROOT)
    assert [file for file, _ in before] == [file for file, _ in after[: len(before)]]
    assert [file for file, _ in after[len(before) :]] == list(native.CLIPPING_FUNCTIONS)
    changed = []
    for (file, left), (_, right) in zip(before, after[: len(before)], strict=True):
        if [dump(node) for node in left] != [dump(node) for node in right]:
            changed.append(file)
    assert changed == [native.CELLS_FILE, native.PARAMETER_FILE]
    mesh = selected(after, "betse/science/math/mesh.py", "DECMesh")
    assert dump(mesh) == dump(original("betse/science/math/mesh.py", "DECMesh"))
    for file, nodes in after:
        # Compile checks syntax only; there is deliberately no exec/eval.
        compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), file, "exec")


def test_ast_mutation_cannot_change_subsequent_source_preparation():
    groups, sites = native.source_nodes(ROOT)
    selected(groups, native.PARAMETER_FILE, "store_parameters").body.clear()
    selected(groups, native.CELLS_FILE, "Cells").body.clear()
    again, new_sites = native.source_nodes(ROOT)
    assert len(selected(again, native.PARAMETER_FILE, "store_parameters").body) == 20
    assert len(selected(again, native.CELLS_FILE, "Cells").body) == 5
    assert sites == new_sites


@pytest.mark.parametrize(
    "relative", [native.CELLS_FILE, native.PARAMETER_FILE, "betse/science/math/mesh.py"]
)
def test_changed_original_pin_refuses_before_any_execution(monkeypatch, relative):
    pins = dict(native.shared.NATIVE_PINS)
    pins[relative] = "0" * 64
    monkeypatch.setattr(native.shared, "NATIVE_PINS", pins)
    with pytest.raises(ValueError, match="Changed original source"):
        native.source_nodes(ROOT)


def test_missing_source_boundary_refuses_instead_of_extending_prefix(monkeypatch):
    original_assembler = native.shared.source_nodes

    def missing(*args, **kwargs):
        groups, sites = original_assembler(*args, **kwargs)
        caller = selected(groups, native.CELLS_FILE, "Cells")
        world = next(node for node in caller.body if node.name == "make_world")
        world.body = [ast.parse("self.near_neigh(phase.p)").body[0]]
        return groups, sites

    monkeypatch.setattr(native.shared, "source_nodes", missing)
    with pytest.raises(ValueError, match="one original cell_index"):
        native.source_nodes(ROOT)


def test_source_change_during_assembly_refuses(monkeypatch):
    original_reader = native._tree

    def read_then_changed(root, relative):
        tree = original_reader(root, relative)
        monkeypatch.setattr(native.shared, "digest", lambda path: "0" * 64)
        return tree

    monkeypatch.setattr(native, "_tree", read_then_changed)
    with pytest.raises(ValueError, match="changed during preparation"):
        native.source_nodes(ROOT)


@pytest.mark.parametrize(
    "relative,name",
    [(relative, name) for relative, names in native.CLIPPING_FUNCTIONS.items() for name in names],
)
def test_clipping_helper_is_the_complete_original_body(relative, name):
    groups, sites = native.source_nodes(ROOT)
    helper = selected(groups, relative, name)
    tree = ast.parse((ROOT / relative).read_bytes())
    original_helper = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    assert dump(helper) == dump(original_helper)
    assert (
        sites[relative + ":" + name]["ast_sha256"]
        == hashlib.sha256(dump(original_helper).encode()).hexdigest()
    )
    assert native.pins_for()[relative] == hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


@pytest.mark.parametrize("relative", list(native.CLIPPING_PINS))
def test_changed_clipping_helper_pin_refuses_without_execution(monkeypatch, relative):
    pins = dict(native.CLIPPING_PINS)
    pins[relative] = "0" * 64
    monkeypatch.setattr(native, "CLIPPING_PINS", pins)
    with pytest.raises(ValueError, match="Changed original source"):
        native.source_nodes(ROOT)


def test_same_named_iterable_helpers_retain_distinct_module_identity():
    groups, sites = native.source_nodes(ROOT)
    array_helper = selected(groups, "betse/lib/numpy/nparray.py", "to_iterable")
    iterable_helper = selected(groups, "betse/util/type/iterable/iterables.py", "to_iterable")
    assert array_helper.name == iterable_helper.name == "to_iterable"
    assert dump(array_helper) != dump(iterable_helper)
    assert "betse/lib/numpy/nparray.py:to_iterable" in sites
    assert "betse/util/type/iterable/iterables.py:to_iterable" in sites
    assert len(native.pins_for()) == 24
